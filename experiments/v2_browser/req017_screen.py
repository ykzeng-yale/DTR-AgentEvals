"""DTR-REQ-017 (lead c648a84, docs/theory_feedback_20260925_req016_decision.md): the REQ-016 supervising parent
(req016_screen.py, imported and never edited) for ONE prospective four-seed 7B DEVELOPMENT pilot (seeds 300-303,
45 min, 2 GiB) whose only change from REQ-016 is the bracket-id adapter (req017_adapter via req017_episodes).

    work/venvs/minisweagent_04d809c/bin/python experiments/v2_browser/req017_screen.py --admission-only
    work/venvs/minisweagent_04d809c/bin/python experiments/v2_browser/req017_screen.py --lead-release <40-hex sha>

NO MODEL CALL WITHOUT THE LEAD'S EXPLICIT RELEASE (release_problems). Arguments are parsed strictly (no abbreviations,
one mode; the user's argv never reaches req016_screen.main). Every run other than --admission-only and the internal
--watchdog <existing file> refuses before its namespace unless --lead-release is the full 40-hex sha of a commit object
that
  * has a subject starting 'lead:' (any case) and exactly one MESSAGE line, outside fenced blocks,
    'RELEASE DTR-REQ-017 manifest_sha256=<sha>' whose sha equals the sha256 of the manifest bytes being run (commit
    messages only, never a diff; git replace objects ignored),
  * is an ancestor of HEAD and of the actual remote main (ls-remote + fetch), descends from the commit that last
    changed the manifest, and is not followed by a lead commit carrying 'REVOKE DTR-REQ-017' or 'HOLD DTR-REQ-017',
  * leaves every manifest source unchanged between the release and HEAD.
The manifest the run then loads must still have the released sha256 (else BLOCKED before serving). The release is
recorded in admission.json (probe 'lead_release'), the summary and the child config; the child refuses a run on the
pilot seeds or the pilot port unless it re-verifies that release and is the direct child of a live req017_screen.py.
The committed manifest configs/v2_req017_7b_bracket_pilot_20260925.json is the specification.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import req016_screen as R  # noqa: E402  frozen REQ-016 parent, imported read-only
import req017_adapter as AD17  # noqa: E402
S, P11 = R.S, R.P11

REQUEST = AD17.REQUEST
MANIFEST_REL = 'configs/v2_req017_7b_bracket_pilot_20260925.json'
REQ016_MANIFEST_REL = 'configs/v2_req016_7b_browser_screen_20260925.json'
HOLDER = 'DTR-AgentEvals worker (DTR-REQ-017 7B bracket-id pilot)'
OWN_SCRIPTS = ('req016_screen.py', 'req016_episodes.py', 'req017_screen.py', 'req017_episodes.py')
CHILD_ENTRY = 'experiments/v2_browser/req017_episodes.py'
SHA40 = re.compile(r'[0-9a-f]{40}')               # used with fullmatch
RELEASE_LINE = re.compile(r'^RELEASE DTR-REQ-017 manifest_sha256=([0-9a-f]{64})$', re.M)
REVOKE_LINE = re.compile(r'^(REVOKE|HOLD) DTR-REQ-017\b', re.M)
FENCED = re.compile(r'^```.*?^```', re.M | re.S)
PILOT_SEEDS = (300, 301, 302, 303)                  # constants (the child's guard trigger never reads a mutable file);
PILOT_PORT = 8291                                   # probe_manifest checks the manifest agrees with them
EXPECTED_ADAPTER_FILES = ('experiments/v2_browser/req016_adapter.py', 'experiments/v2_browser/req017_adapter.py',
                          'experiments/v2_browser/req016_episodes.py', 'experiments/v2_browser/req017_episodes.py',
                          'experiments/v2_browser/req016_screen.py', 'experiments/v2_browser/req017_screen.py')
RELEASE = {}                                        # the verified release of this process (set by main)


def manifest(root=ROOT):
    return json.loads((root / MANIFEST_REL).read_text())


def manifest_sha(root=ROOT):
    return S.sha_file(root / MANIFEST_REL)


# ------------------------------------------------------------------ REQ-017 replacements (rebound into req016_screen)
def probe_manifest(root, m=None):
    """The REQ-017 binding: the REQ-016 7B assignment, pins, settings, task, capacity, accounting and browser (except its
    entry) unchanged; seeds 300-303; caps 16/32/2700 s; the REQ-016 prompt bytes; every bound file hash; the REQ-016
    manifest, verification record, sources and every published REQ-016 archive file unchanged."""
    m = manifest(root) if m is None else m
    m11 = json.loads((root / m['model_source']['manifest']).read_text())
    row = next(a for a in m11['assignments'] if a['backend'] == 'small')
    m16 = json.loads((root / REQ016_MANIFEST_REL).read_text())
    problems = []
    if m.get('request') != REQUEST:
        problems.append('request is not %s' % REQUEST)
    for k in ('backend', 'port', 'alias', 'gguf', 'gguf_sha256', 'gguf_bytes', 'model', 'model_commit'):
        if m['assignment'].get(k) != row.get(k):
            problems.append('assignment %s differs from the REQ-011 7B row' % k)
    for k in ('assignment', 'lead_pins', 'settings', 'task', 'capacity', 'accounting', 'model_source'):
        if m[k] != m16[k]:
            problems.append('%s differs from REQ-016' % k)
    if m['browser'] != dict(m16['browser'], entry=CHILD_ENTRY):
        problems.append('browser differs from REQ-016 other than entry=%s' % CHILD_ENTRY)
    if P11.SERVING['llama_cpp_commit'] != m['lead_pins']['llama_cpp_commit']:
        problems.append('the llama.cpp pin differs from the lead-stated value')
    if m['seeds'] != list(PILOT_SEEDS) or m['assignment'].get('port') != PILOT_PORT:
        problems.append('seeds are not 300-303 in order or the model port is not %d' % PILOT_PORT)
    if sorted(m['adapter']['files']) != sorted(EXPECTED_ADAPTER_FILES):
        problems.append('adapter.files does not bind exactly the six REQ-016/REQ-017 adapter, child and parent files')
    if set(m['seeds']) & set(m16['seeds']):
        problems.append('seeds overlap the spent REQ-016 seeds')
    if m['caps'] != dict(m16['caps'], batch_wall_s=2700):
        problems.append('caps are not the REQ-016 caps with batch_wall_s 2700')
    if set(m['outputs'].values()) & set(m16['outputs'].values()):
        problems.append('outputs overlap the REQ-016 namespace')
    if m['adapter']['prompt_sha256'] != R.prompt_sha256() or m['adapter']['prompt_sha256'] != m16['adapter']['prompt_sha256']:
        problems.append('the prompt sha256 differs from the unchanged REQ-016 prompt')
    for rel, want in m['adapter']['files'].items():
        if S.sha_file(root / rel) != want:
            problems.append('%s sha256 differs from the manifest' % rel)
    q = m['req016']
    for key, rel in (('req016_manifest_sha256', REQ016_MANIFEST_REL),
                     ('req016_archive_publication_manifest_sha256', q['archive_publication_manifest']),
                     ('verification_record_sha256', q['verification_record'])):
        if S.sha_file(root / rel) != q[key]:
            problems.append('%s differs (REQ-016 must stay byte-for-byte)' % key)
    archive = (root / q['archive_publication_manifest']).parent
    pm = json.loads((root / q['archive_publication_manifest']).read_text())
    changed = [k for k, v in pm.items() if S.sha_file(archive / k) != v['published_sha256']]
    if changed:
        problems.append('%d published REQ-016 archive files changed' % len(changed))
    for rel, want in m16['adapter']['files'].items():
        if S.sha_file(root / rel) != want:
            problems.append('frozen REQ-016 source %s changed' % rel)
    if S.sha_file(root / m['model_source']['manifest']) != m['model_source']['manifest_sha256']:
        problems.append('model_source.manifest_sha256 differs from the REQ-011 manifest')
    if S.sha_file(root / m['browser']['req015_manifest']) != m['browser']['req015_manifest_sha256']:
        problems.append('browser.req015_manifest_sha256 differs from the REQ-015 manifest')
    return not problems, OrderedDict(problems=problems, req011_row=row, req016_archive_files_checked=len(pm))


def run_seeds(raw=None):
    """The seeds of the frozen manifest copied into the run (raw/manifest.json), else the committed manifest."""
    p = Path(raw) / 'manifest.json' if raw is not None else None
    return list(json.loads(p.read_text())['seeds'] if p is not None and p.exists() else manifest()['seeds'])


def executed_counts(raw, seed):
    """From the episode's steps.jsonl: executed click/fill actions, executed canonicalized (bracketed) actions and
    executed noop() (noop never satisfies discriminator 1)."""
    p = Path(raw) / 'episodes' / ('seed%d' % seed) / 'steps.jsonl' if raw is not None else None
    out = OrderedDict(executed_click_fill=0, executed_canonicalized=0, executed_noop=0)
    if p is None or not p.exists():
        return out
    for line in p.read_text().splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get('kind') != 'call' or not r.get('executed') or not r.get('parsed_action'):
            continue
        a = r['parsed_action']
        if a.startswith(('click(', 'fill(')):
            out['executed_click_fill'] += 1
            if r.get('invalid_cause') is None and r.get('invalid_detail') == AD17.CANONICALIZED:
                out['executed_canonicalized'] += 1
        elif a == 'noop()':
            out['executed_noop'] += 1
    return out


def score(batch, status, raw=None):
    """req016_screen.score for this pilot's seeds (all in the denominator) plus the predeclared discriminator counts."""
    wanted = run_seeds(raw)
    rows, by_seed = [], R.episode_records(batch, raw)
    for seed in wanted:
        e = by_seed.get(seed)
        if e is None:
            partial = raw is not None and (Path(raw) / 'episodes' / ('seed%d' % seed)).exists()
            e = OrderedDict(seed=seed, cause='incomplete_record' if partial else 'not_started', full_success=False)
        cause = e.get('cause') or 'unknown'
        if status == 'CAPACITY_INTERRUPTION' and cause in R.UNRUN:
            cause = 'capacity_interruption' if cause in ('stopped_by_supervisor', 'incomplete_record') else \
                'not_run_capacity'
        elif status != 'COMPLETED' and cause in R.UNRUN:
            cause = 'not_run: %s (%s)' % (status, cause)
        row = OrderedDict(seed=seed, cause=cause, full_success=bool(e.get('full_success')),
                          **{k: e.get(k) for k in ('logical_calls', 'physical_attempts', 'executed_actions',
                                                   'invalid_replies', 'invalid_causes', 'action_errors',
                                                   'prompt_tokens', 'completion_tokens', 'usage_unknown_calls',
                                                   'wall_seconds', 'terminal', 'error')})
        row.update(executed_counts(raw, seed))
        rows.append(row)
    taxonomy = OrderedDict()
    for r in rows:
        taxonomy[r['cause']] = taxonomy.get(r['cause'], 0) + 1
    with_click_fill = sum(1 for r in rows if r['executed_click_fill'] > 0)
    full = sum(r['full_success'] for r in rows)
    return OrderedDict(full_success=full, denominator=len(wanted), screen_status=status,
                       screen_complete=status == 'COMPLETED', taxonomy=taxonomy,
                       episodes_with_executed_action=sum(1 for r in rows if (r['executed_actions'] or 0) > 0),
                       episodes_with_executed_click_fill=with_click_fill,
                       executed_canonicalized_total=sum(r['executed_canonicalized'] for r in rows),
                       discriminator=OrderedDict(
                           action_executes=with_click_fill >= 1, at_least_one_full_success=full >= 1,
                           rule='(1) at least one executed click/fill (noop does not count); (2) at least one full '
                                'success; zero full successes ends this local 7B browser path'),
                       capacity_rows=[r['seed'] for r in rows if r['cause'] in ('capacity_interruption',
                                                                                'not_run_capacity')],
                       rows=rows)


def spawn_watchdog(raw, deadline, env, popen=subprocess.Popen):
    """req011_pair.spawn_watchdog with the REQ-017 label and holder, started through THIS script."""
    def launch(cmd, **options):
        return popen([cmd[0], str(Path(__file__).resolve())] + list(cmd[2:]), **options)
    with R.rebound(P11, REQUEST=REQUEST, HOLDER=HOLDER):
        return P11.spawn_watchdog(raw, deadline, env, popen=launch)


_BASE_CHILD_CONFIG = R.child_config


def child_config(root, manifest_obj, raw, deadline_epoch):
    """req016_screen.child_config plus the verified lead release (the child re-checks it for pilot seeds/port)."""
    cfg = _BASE_CHILD_CONFIG(root, manifest_obj, raw, deadline_epoch)
    cfg['lead_release'] = RELEASE.get('commit')
    return cfg


REBINDINGS = dict(MANIFEST_REL=MANIFEST_REL, REQUEST=REQUEST, HOLDER=HOLDER, OWN_SCRIPTS=OWN_SCRIPTS,
                  probe_manifest=probe_manifest, score=score, spawn_watchdog=spawn_watchdog, child_config=child_config)


@contextlib.contextmanager
def installed():
    """Rebind req016_screen's module globals for the duration of one call, then restore them (the REQ-016 module is
    left exactly as imported, also inside a shared test process)."""
    old = {name: getattr(R, name) for name in REBINDINGS}
    for name, value in REBINDINGS.items():
        setattr(R, name, value)
    try:
        yield R
    finally:
        for name, value in old.items():
            setattr(R, name, value)


# ------------------------------------------------------------------ the lead-release gate
def release_problems(root, commit, run=S.sh, remote=True):
    """([], verified OrderedDict) when `commit` is the lead's explicit release of this exact manifest; else (problems,
    detail). Only commit MESSAGES are read (never a diff), with git replace objects ignored; the token must stand on
    its own line outside fenced blocks; a later lead REVOKE/HOLD line cancels it; the release must be on the actual
    remote main (ls-remote + fetch), not only on a local origin/main ref."""
    d = OrderedDict(commit=commit)
    if not isinstance(commit, str) or not SHA40.fullmatch(commit):
        return ['--lead-release must be the full 40-hex sha of the lead release commit (REQ-017 makes no model call '
                'until the lead releases it)'], d
    git = lambda *a: run(['git', '--no-replace-objects', '-C', str(root)] + list(a))  # noqa: E731
    rc, peeled, _ = git('rev-parse', '--verify', '--quiet', commit + '^{commit}')
    if rc != 0 or peeled.strip() != commit:
        return ['%s is not a commit object in this repository' % commit], d
    problems = []
    msg = git('log', '-1', '--format=%B', commit)[1]
    subject = msg.strip().splitlines()[0] if msg.strip() else ''
    if not subject.lower().startswith('lead:'):
        problems.append('%s is not a lead commit (subject %r)' % (commit[:12], subject[:80]))
    tokens = RELEASE_LINE.findall(FENCED.sub('', msg))
    want = manifest_sha(root)
    d.update(subject=subject[:200], release_tokens=tokens, manifest_sha256=want)
    if tokens != [want]:
        problems.append('%s has no single unquoted message line "RELEASE DTR-REQ-017 manifest_sha256=%s"'
                        % (commit[:12], want))
    refs = ['HEAD']
    if remote:
        rc, out, _ = git('ls-remote', 'origin', 'refs/heads/main')
        remote_head = out.split()[0] if rc == 0 and out.split() else None
        d['remote_main'] = remote_head
        if not remote_head or not SHA40.fullmatch(remote_head):
            problems.append('the remote main could not be read (ls-remote origin refs/heads/main)')
        else:
            if git('cat-file', '-e', remote_head + '^{commit}')[0] != 0:
                git('fetch', '-q', 'origin', 'main')
            refs.append(remote_head)
    for ref in refs:
        if git('merge-base', '--is-ancestor', commit, ref)[0] != 0:
            problems.append('%s is not an ancestor of %s' % (commit[:12], ref if ref == 'HEAD' else 'the remote main'))
    freeze = git('log', '-1', '--format=%H', '--', MANIFEST_REL)[1].strip()
    d['manifest_freeze_commit'] = freeze
    if not freeze or git('merge-base', '--is-ancestor', freeze, commit)[0] != 0:
        problems.append('the release %s does not descend from the manifest freeze %s' % (commit[:12], freeze[:12]))
    for ref in refs:
        later = git('log', '--format=%s%n%B%x00', '%s..%s' % (commit, ref))[1]
        for m in later.split('\x00'):
            body = m.strip()
            if body and body.splitlines()[0].lower().startswith('lead:') and REVOKE_LINE.search(FENCED.sub('', body)):
                problems.append('a later lead commit revokes or holds the REQ-017 release')
                break
    sources = manifest(root)['sources']
    if git('diff', '--quiet', commit, 'HEAD', '--', *sources)[0] != 0:
        problems.append('a manifest source changed between the release %s and HEAD' % commit[:12])
    return problems, d


def parse_args(argv):
    """Strict: no abbreviations, one mode, canonical forwarding (the user's argv never reaches req016_screen.main)."""
    ap = argparse.ArgumentParser(prog='req017_screen.py', allow_abbrev=False)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument('--admission-only', action='store_true')
    mode.add_argument('--lead-release', default=None)
    mode.add_argument('--watchdog', default=None, help=argparse.SUPPRESS)
    ns = ap.parse_args(argv)
    if ns.watchdog is not None and (not ns.watchdog or not Path(ns.watchdog).is_file()):
        ap.error('--watchdog needs an existing config file')
    return ns


def main(argv=None, root=ROOT, probes=None, runner=None, run=S.sh, remote=True):
    ns = parse_args(list(sys.argv[1:] if argv is None else argv))
    if ns.watchdog:
        with installed():
            return R.main(['--watchdog', ns.watchdog], root=root)
    if ns.admission_only:
        with installed():
            return R.main(['--admission-only'], root=root, probes=probes)
    problems, detail = release_problems(root, ns.lead_release, run, remote=remote)
    if problems:
        print('DTR-REQ-017 refused before its namespace (nothing consumed, no model call): %s' % '; '.join(problems),
              file=sys.stderr)
        return 3
    RELEASE.clear()
    RELEASE.update(detail)
    inner = runner or R.run_screen

    def released(ctx):
        ctx['summary']['lead_release'] = OrderedDict(detail)
        if ctx['summary'].get('manifest_sha256') != detail['manifest_sha256']:     # the file changed after the gate
            raise R.Gate('the manifest loaded by the run (%s) is not the released manifest (%s)'
                         % (ctx['summary'].get('manifest_sha256'), detail['manifest_sha256']))
        return inner(ctx)
    pub = root / manifest(root)['outputs']['published'] / 'screen_summary.json'
    existed = pub.exists()
    with installed():
        base = probes if probes is not None else R.admission_probes(manifest(root))
        gated = OrderedDict(base)
        gated['lead_release'] = lambda r: (True, OrderedDict(detail))   # verified above; recorded in admission.json
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            rc = R.main([], root=root, probes=gated, runner=released)
    if rc != 3 and not existed and pub.exists():      # this process wrote it (the inherited line says denominator 8)
        s = json.loads(pub.read_text())
        sc = s['score']
        inherited = captured.getvalue().strip().splitlines()
        hits = json.loads(inherited[-1]).get('username_hits') if inherited else None
        print(json.dumps(OrderedDict(request=REQUEST, status=s['status'], full_success=sc['full_success'],
                                     denominator=sc['denominator'], taxonomy=sc['taxonomy'],
                                     episodes_with_executed_click_fill=sc.get('episodes_with_executed_click_fill'),
                                     discriminator=sc.get('discriminator'), wall_seconds=s.get('wall_seconds'),
                                     username_hits=hits)))
    else:
        sys.stdout.write(captured.getvalue())
    return rc


if __name__ == '__main__':
    sys.exit(main())
