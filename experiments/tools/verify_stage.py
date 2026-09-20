"""Gate that must pass before a stage's artifacts are committed.

Why this exists: on 19 September 2026 the branch stage's `episodes.jsonl` was `git add`-ed, committed and then rebased
onto upstream WHILE the runner still held it open for appending. The rebase replaced the file with a new inode; the
runner's handle pointed at the old, now-unlinked one, so 665 of 800 completed continuations were written into a
deleted file. Writes to an unlinked inode succeed, so the runner reported "800/800, errors 0" and exited 0. The loss
was invisible in the runner's own output and cost about an hour of GPU work.

Two rules follow, and this script enforces both:
  1. never publish a stage while its runner is alive - a stage directory holding a live `run.lock`, or whose
     episodes file was modified in the last `--quiet-seconds`, is refused;
  2. never trust the runner's progress counter - the episodes actually on disk must match the frozen design (or the
     frozen branch plan) exactly.

  python experiments/tools/verify_stage.py log live branch [--quiet-seconds 120]

Exit status is non-zero when any stage fails, so it can gate a commit.
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments' / 'code_routing'))
sys.path.insert(0, str(ROOT / 'experiments' / 'common'))
import common  # noqa: E402


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def expected_ids(stage: str, design: dict, base: Path) -> set:
    if stage in ('log', 'live'):
        return {e['episode_id'] for e in design['%s_episodes' % stage]}
    if stage == 'branch':
        plan = base / 'branch' / 'branch_plan.json'
        if not plan.exists():
            return set()
        return {e['episode_id'] for e in json.loads(plan.read_text())['episodes']}
    return set()


def _design_seeds(design, stage, base):
    """(seed_by_episode, task_by_episode) from the frozen design or branch plan."""
    src = None
    if stage in ('log', 'live'):
        src = design['%s_episodes' % stage]
    elif stage == 'branch':
        pl = base / 'branch' / 'branch_plan.json'
        if pl.exists():
            src = json.loads(pl.read_text())['episodes']
    if src is None:
        return {}, {}
    return ({e['episode_id']: e['seed'] for e in src}, {e['episode_id']: e['task_uid'] for e in src})


def check_records(ep_path, d, stage, res, design, cfg) -> list:
    """Integrity checks the resolver cannot make. Each has a fixture in test_verify_stage.py that fails without it."""
    problems = []
    rows, _ = common.read_jsonl(ep_path)
    completed = [r for r in rows if not r.get('error')]

    seen = {}
    for r in completed:
        seen[r['episode_id']] = seen.get(r['episode_id'], 0) + 1
    dups = sorted(e for e, k in seen.items() if k > 1)      # the resolver silently keeps the last one
    if dups:
        problems.append('%d episode id(s) have more than one completed row, e.g. %s' % (len(dups), dups[:2]))

    # required frozen metadata must be PRESENT, non-null and equal to the frozen value on every completed row
    frozen = dict(config_sha256=cfg['_config_sha256'], tasks_sha256=design['tasks_sha256'])
    vt = base_vt_sha()
    if vt:
        frozen['visible_tests_sha256'] = vt
    for key, want in frozen.items():
        missing = [r['episode_id'] for r in completed if r.get(key) in (None, '')]
        wrong = sorted({r.get(key) for r in completed if r.get(key) not in (None, '', want)})
        if missing:
            problems.append('%d completed row(s) are missing %s, e.g. %s' % (len(missing), key, missing[:2]))
        if wrong:
            problems.append('%s does not match the frozen value on some rows (%s)' % (key, [str(w)[:12] for w in wrong[:2]]))

    seeds, task_of = _design_seeds(design, stage, ep_path.parent.parent)
    if seeds:
        bad = [r['episode_id'] for r in completed if r['episode_id'] in seeds and r.get('seed') != seeds[r['episode_id']]]
        if bad:
            problems.append('%d row(s) carry a seed that differs from the frozen design, e.g. %s' % (len(bad), bad[:2]))
        wrongtask = [r['episode_id'] for r in completed
                     if r['episode_id'] in task_of and r.get('task_uid') != task_of[r['episode_id']]]
        if wrongtask:
            problems.append('%d row(s) are attached to a different task than the frozen design, e.g. %s' % (len(wrongtask), wrongtask[:2]))

    if stage == 'branch':
        lg = ep_path.parent.parent / 'log' / 'episodes.jsonl'
        if not lg.exists():
            problems.append('branch stage cannot be verified: the reference log episodes.jsonl is missing')
            return problems                      # refuse rather than skip the membership check
        lrows, _ = common.read_jsonl(lg)
        parents = {r['episode_id'] for r in lrows if not r.get('error')}
        if not parents:
            problems.append('branch stage cannot be verified: the reference log supplies no completed parent episodes')
            return problems                      # existence of the file is not evidence that it supplies records
        for r in completed:
            rest = r.get('restoration')
            if not isinstance(rest, dict):
                problems.append('completed branch row %s has no restoration evidence' % r['episode_id']); break
            if rest.get('transcript_hash_matches') is not True or rest.get('tool_result_reproduced') is not True:
                problems.append('completed branch row %s is analysed despite a false/absent restoration flag' % r['episode_id']); break
        rc = ep_path.parent.parent / 'analysis' / 'restoration_recheck.json'
        if not rc.exists():
            problems.append('no independent restoration recheck (run experiments/tools/verify_restoration.py)')
        else:
            doc = json.loads(rc.read_text())
            sb = doc.get('source_binding') or {}
            need = {'log/episodes.jsonl': ep_path.parent.parent / 'log' / 'episodes.jsonl',
                    'log/decisions.jsonl': ep_path.parent.parent / 'log' / 'decisions.jsonl',
                    'branch/decisions.jsonl': ep_path.parent / 'decisions.jsonl',
                    'visible_tests.json': ep_path.parent.parent / 'visible_tests.json'}
            absent = sorted(k for k, v in need.items() if not v.exists())
            if absent:      # fail closed: a binding cannot be checked against files that are not there
                problems.append('restoration binding cannot be checked: missing %s' % ', '.join(absent))
                return problems
            want = dict(branch_episodes_sha256=common.sha256_bytes(ep_path.read_bytes()),
                        log_episodes_sha256=common.sha256_bytes(need['log/episodes.jsonl'].read_bytes()),
                        visible_tests_sha256=common.sha256_bytes(need['visible_tests.json'].read_bytes()),
                        covered_episode_ids_sha256=__import__('hashlib').sha256(
                            '\n'.join(sorted(r['episode_id'] for r in completed)).encode()).hexdigest(),
                        tasks_sha256=design['tasks_sha256'],
                        branch_decisions_sha256=common.sha256_bytes(need['branch/decisions.jsonl'].read_bytes()),
                        log_decisions_sha256=common.sha256_bytes(need['log/decisions.jsonl'].read_bytes()))
            for k, v in want.items():
                if sb.get(k) != v:
                    problems.append('restoration recheck is not bound to the current records: %s differs' % k)
            if doc.get('branch_side_transcript_hash_matches') != doc.get('branch_episodes_checked'):
                problems.append('restoration recheck: %s of %s branch-side transcript hashes match'
                                % (doc.get('branch_side_transcript_hash_matches'), doc.get('branch_episodes_checked')))
            if doc.get('branch_episodes_checked', 0) < len(completed):
                problems.append('restoration recheck covers %s of %d completed branch rows'
                                % (doc.get('branch_episodes_checked'), len(completed)))
            if doc.get('disagreements', 1) != 0 or doc.get('missing_parent', 1) != 0:
                problems.append('restoration recheck reports %s disagreement(s) and %s missing parent(s)'
                                % (doc.get('disagreements'), doc.get('missing_parent')))
            if doc.get('recomputed_transcript_hash_matches') != doc.get('branch_episodes_checked'):
                problems.append('restoration recheck: %s of %s transcript hashes recomputed as matching'
                                % (doc.get('recomputed_transcript_hash_matches'), doc.get('branch_episodes_checked')))
        noparent = [r['episode_id'] for r in completed if not r.get('parent_episode_id')]
        if noparent:
            problems.append('%d completed branch row(s) record no parent, e.g. %s' % (len(noparent), noparent[:2]))
        if parents:
            ghost = sorted({r.get('parent_episode_id') for r in completed
                            if r.get('parent_episode_id') and r['parent_episode_id'] not in parents})
            if ghost:
                problems.append('%d branch row(s) name a parent that is not a completed log episode, e.g. %s' % (len(ghost), ghost[:2]))

    man = ep_path.parent / 'run_manifest.jsonl'
    if not man.exists() or not man.read_text().strip():
        problems.append('run_manifest.jsonl is missing or empty')
        invocations = set()
    else:
        mrows, mtorn = common.read_jsonl(man)
        if mtorn:
            problems.append('run_manifest.jsonl has a torn final line')
        invocations = {m.get('invocation') for m in mrows if m.get('invocation')}
        if not invocations:
            problems.append('run_manifest.jsonl carries no invocation identifiers')      # nonempty is not enough
        by_inv = {}
        for m in mrows:
            if m.get('invocation') and m.get('code_sha256'):
                by_inv.setdefault(m['invocation'], set()).add(m['code_sha256'])
        ep_code = {r.get('code_sha256') for r in completed}
        if None in ep_code or '' in ep_code:
            problems.append('completed row(s) are missing code_sha256')
        elif not by_inv:
            problems.append('no manifest row records a code_sha256, so source identity cannot be checked')
        else:
            wrong = [r['episode_id'] for r in completed
                     if r.get('code_sha256') not in by_inv.get(r.get('invocation'), set())]
            if wrong:      # a hash recorded only under a DIFFERENT invocation is not evidence for this one
                problems.append('%d row(s) carry a code_sha256 not recorded by their own invocation, e.g. %s'
                                % (len(wrong), wrong[:2]))

    dec = ep_path.parent / 'decisions.jsonl'
    if not dec.exists() or not dec.read_text().strip():
        problems.append('decisions.jsonl is missing or empty')
        return problems
    drows, dtorn = common.read_jsonl(dec)
    if dtorn:
        problems.append('decisions.jsonl has a torn final line')
    noinv = [x for x in drows if not x.get('invocation')]
    if noinv:
        problems.append('%d durable decision row(s) have a null/absent invocation id' % len(noinv))
    unknown = sorted({x.get('invocation') for x in drows if x.get('invocation') and invocations and x['invocation'] not in invocations})
    if unknown:
        problems.append('%d durable decision row(s) carry an invocation absent from the manifest, e.g. %s' % (len(unknown), unknown[:2]))
    orphan = {x['episode_id'] for x in drows} - set(res['good']) - set(res['exhausted'])
    if orphan:
        problems.append('%d episode id(s) have durable decisions but no resolved episode, e.g. %s' % (len(orphan), sorted(orphan)[:2]))

    # every retained completed decision is matched on episode + invocation + attempt + stage; rows that match no
    # retained completion are historical and must be declared in the recovery ledger, not silently accepted
    retained = {(r['episode_id'], r.get('invocation'), r.get('attempt')) for r in completed}
    nested = {(r['episode_id'], r.get('invocation'), r.get('attempt'), dd['t']): dd.get('a')
              for r in completed for dd in r.get('decisions', []) if dd.get('completed', True)}
    declared, declared_counts, ledger_problems = _ledger(ep_path.parent.parent, stage)
    problems += ledger_problems
    unmatched, mism = set(), []
    for x in drows:
        k3 = (x['episode_id'], x.get('invocation'), x.get('attempt'))
        k4 = k3 + (x.get('t'),)
        if k3 not in retained:
            if k3 not in declared:
                unmatched.add(k3)
            continue
        if k4 in nested and nested[k4] != x.get('a'):
            mism.append(k4)
    if unmatched:
        problems.append('%d durable decision key(s) match no retained completion and are not in the recovery ledger, e.g. %s'
                        % (len(unmatched), sorted(unmatched, key=str)[:2]))
    if declared:
        actual = {}
        for x in drows:
            k3 = (x['episode_id'], x.get('invocation'), x.get('attempt'))
            if k3 in declared:
                actual[k3] = actual.get(k3, 0) + 1
                t = x.get('t')
                if not isinstance(t, int) or not 0 <= t < cfg['horizon']:
                    problems.append('historical decision for %s has stage t=%s outside [0, %d)' % (k3[0], t, cfg['horizon']))
        for k3, want in declared_counts.items():
            if actual.get(k3, 0) != want:
                problems.append('recovery ledger declares %d row(s) for %s but %d are retained' % (want, k3[0], actual.get(k3, 0)))
    if mism:
        problems.append('%d durable decision(s) disagree with the episode record on the action taken, e.g. %s' % (len(mism), mism[:2]))
    missing_nested = [k for k in nested if k not in {(x['episode_id'], x.get('invocation'), x.get('attempt'), x.get('t')) for x in drows}]
    if missing_nested:
        problems.append('%d completed decision(s) have no durable pre-invocation record, e.g. %s' % (len(missing_nested), missing_nested[:2]))
    return problems


def _ledger(base, stage):
    """(declared_keys, declared_counts, problems). A ledger entry exempts historical rows only if its schema, its
    exact per-key row count and its total agree with what is actually retained."""
    led = base / 'recovery_ledger.json'
    if not led.exists():
        return set(), {}, []
    try:
        doc = json.loads(led.read_text())
    except ValueError:
        return set(), {}, ['recovery_ledger.json is not valid JSON']
    if doc.get('stage') != stage:
        return set(), {}, []
    probs_, keys, counts = [], set(), {}
    for r in doc.get('rows', []):
        if not all(k in r for k in ('episode_id', 'invocation', 'attempt', 'durable_decision_rows')):
            probs_.append('recovery ledger row is missing a required field: %s' % str(r)[:80]); continue
        k = (r['episode_id'], r['invocation'], r['attempt'])
        keys.add(k); counts[k] = r['durable_decision_rows']
    total = doc.get('total_rows')
    if total is not None and total != sum(counts.values()):
        probs_.append('recovery ledger total_rows %s does not equal the sum of its declared rows (%d)' % (total, sum(counts.values())))
    if doc.get('total_episode_ids') is not None and doc['total_episode_ids'] != len({k[0] for k in keys}):
        probs_.append('recovery ledger total_episode_ids does not equal its declared episode ids')
    return keys, counts, probs_


def base_vt_sha():
    p = common.RESULTS / 'visible_tests.json'
    return common.sha256_bytes(p.read_bytes()) if p.exists() else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('stages', nargs='+')
    ap.add_argument('--quiet-seconds', type=int, default=120, help='refuse a stage whose episodes file changed this recently')
    a = ap.parse_args()
    cfg = common.load_config(); base = common.RESULTS
    design = json.loads((base / 'design.json').read_text())
    bad = 0
    for stage in a.stages:
        d = base / stage
        ep = d / 'episodes.jsonl'
        if not ep.exists():
            print('%-7s MISSING  no episodes.jsonl' % stage); bad += 1; continue
        lock = d / 'run.lock'
        if lock.exists():
            holder = json.loads(lock.read_text())
            state = 'ALIVE' if alive(holder['pid']) else 'stale'
            print('%-7s REFUSED  run.lock held by pid %s (%s) - do not commit a stage that is still being written'
                  % (stage, holder['pid'], state))
            if state == 'ALIVE':
                bad += 1; continue
        quiet = time.time() - ep.stat().st_mtime
        if quiet < a.quiet_seconds:
            print('%-7s REFUSED  episodes.jsonl was modified %.0fs ago (< %ds): the runner may still be appending'
                  % (stage, quiet, a.quiet_seconds)); bad += 1; continue
        res = common.resolve_episodes(ep, cfg['max_attempts_per_episode'])
        want = expected_ids(stage, design, base)
        have = set(res['good']) | set(res['exhausted'])
        missing, extra = want - have, have - want
        problems = check_records(ep, d, stage, res, design, cfg)
        if res['torn']:
            problems.append('torn final line (%d)' % res['torn'])      # a printed count is not a gate; this fails
        status = 'OK' if (want and not missing and not extra and not res['pending'] and not problems) else 'FAILED'
        print('%-7s %-8s on disk %d/%d  (good %d, intention-to-treat %d, retries owed %d, missing %d, unexpected %d, torn %d)'
              % (stage, status, len(have), len(want), len(res['good']), len(res['exhausted']), len(res['pending']),
                 len(missing), len(extra), res['torn']))
        if missing:
            print('         e.g. missing: %s' % sorted(missing)[:3])
        for pr in problems:
            print('         PROBLEM: %s' % pr)
        if status != 'OK':
            bad += 1
    print('\n%s' % ('ALL STAGES VERIFIED - safe to commit' if not bad else '%d stage(s) NOT safe to commit' % bad))
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main())
