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


def check_records(ep_path, d, stage, res, design, cfg) -> list:
    """Integrity checks the resolver cannot make: duplicate completed rows, frozen-metadata drift, restoration flags
    that are recorded as true without the evidence, and durable decisions that no completed episode accounts for."""
    problems = []
    rows, _ = common.read_jsonl(ep_path)
    seen = {}
    for r in rows:
        if not r.get('error'):
            seen[r['episode_id']] = seen.get(r['episode_id'], 0) + 1
    dups = sorted(e for e, k in seen.items() if k > 1)      # the resolver silently keeps the last one
    if dups:
        problems.append('%d episode id(s) have more than one completed row, e.g. %s' % (len(dups), dups[:2]))
    frozen = dict(config_sha256=cfg['_config_sha256'], tasks_sha256=design['tasks_sha256'])
    vt = base_vt_sha()
    if vt:
        frozen['visible_tests_sha256'] = vt
    for key, want in frozen.items():
        got = {r.get(key) for r in rows if r.get(key) is not None}
        if got and got != {want}:
            problems.append('%s in episodes does not match the frozen value (%s)' % (key, sorted(got)[:2]))
    if stage == 'branch':
        bad = [r['episode_id'] for r in rows if not r.get('error') and r.get('restoration')
               and (r['restoration'].get('transcript_hash_matches') is True) and not r.get('parent_episode_id')]
        if bad:
            problems.append('%d branch row(s) claim a matching transcript hash with no parent recorded' % len(bad))
    dec = ep_path.parent / 'decisions.jsonl'
    if dec.exists():
        drows, dtorn = common.read_jsonl(dec)
        if dtorn:
            problems.append('decisions.jsonl has a torn final line')
        if any('invocation' not in x for x in drows):
            problems.append('durable decisions without an invocation id (attempt numbers are reused across invocations)')
        orphan = {x['episode_id'] for x in drows} - set(res['good']) - set(res['exhausted'])
        if orphan:
            problems.append('%d episode id(s) have durable decisions but no resolved episode, e.g. %s'
                            % (len(orphan), sorted(orphan)[:2]))
    return problems


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
