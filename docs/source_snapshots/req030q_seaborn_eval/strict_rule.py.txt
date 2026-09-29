"""DTR-REQ-002 fixture M03 (part 1): declared-outcome grading rule and conformance fixtures against SWE-bench f7bbbb2.

The DECLARED rule (lead, 91c8bcc): an instance is resolved only if every declared FAIL_TO_PASS and every declared
PASS_TO_PASS test is observed PASSED in the parsed test output. Missing tests, SKIPPED tests and unparsable output
never count as passing. Evaluator failures (patch not applied, reset failure, test error/timeout markers, missing test
markers) are UNKNOWN algorithmic correctness, not unresolved (contract A10); an empty parsed status map is also UNKNOWN.

The UPSTREAM column in FIXTURES is source-derived DATA read from grading.py at f7bbbb2 (line citations below). It is not
a copy of the evaluator, and the evaluator was NOT executed: running upstream code on these fixtures (the conformance run)
awaits the user's permission. Discrepancies are listed for the lead; nothing here decides them.
Upstream facts used (grading.py @ f7bbbb2): test_passed = status in {PASSED, XFAIL} (L27-28); test_failed = missing or
status in {FAILED, ERROR} (L31-35); pass-and-fail mode appends to neither list when neither holds, e.g. SKIPPED (L123-128);
empty list scores 1 (L199-200, L209-211); FULL iff both scores are 1; bad-code or missing-marker logs return found=False
(L61-76); FAIL_ONLY mode (L130-137) applies only to FAIL_ONLY_REPOS = {chartjs/Chart.js, processing/p5.js,
markedjs/marked} (constants/__init__.py L129-133), none of which is a SWE-bench Verified repository.
"""
from __future__ import annotations

PASSED, FAILED, SKIPPED, ERROR, XFAIL = 'PASSED', 'FAILED', 'SKIPPED', 'ERROR', 'XFAIL'


def declared_outcome(f2p, p2p, status_map, log_ok=True):
    """Our contract. Returns 'resolved', 'unresolved' or an 'unknown_*' label; never counts absence as passing."""
    if not log_ok:
        return 'unknown_evaluator_failure'
    if not status_map:
        return 'unknown_unparsable_output'
    ok = all(status_map.get(t) == PASSED for t in list(f2p) + list(p2p))
    return 'resolved' if ok else 'unresolved'


F2P, P2P = ['t::a', 't::b'], ['t::c']
ALL = {'t::a': PASSED, 't::b': PASSED, 't::c': PASSED}
FIXTURES = [   # id, status map, log_ok, declared (computed by the rule above), upstream (source-derived data)
    ('G01-all-pass', ALL, True, 'resolved', 'resolved'),
    ('G02-f2p-failed', {**ALL, 't::a': FAILED}, True, 'unresolved', 'unresolved'),
    ('G03-f2p-missing', {k: v for k, v in ALL.items() if k != 't::a'}, True, 'unresolved', 'unresolved'),
    ('G04-f2p-error', {**ALL, 't::a': ERROR}, True, 'unresolved', 'unresolved'),
    ('G05-one-f2p-skipped', {**ALL, 't::a': SKIPPED}, True, 'unresolved', 'resolved'),
    ('G06-all-f2p-skipped', {**ALL, 't::a': SKIPPED, 't::b': SKIPPED}, True, 'unresolved', 'resolved'),
    ('G07-p2p-skipped', {**ALL, 't::c': SKIPPED}, True, 'unresolved', 'resolved'),
    ('G08-f2p-xfail', {**ALL, 't::a': XFAIL}, True, 'unresolved', 'resolved'),
    ('G09-p2p-missing', {k: v for k, v in ALL.items() if k != 't::c'}, True, 'unresolved', 'unresolved'),
    ('G10-bad-log-marker', ALL, False, 'unknown_evaluator_failure', 'unresolved (found=False; report resolved False)'),
    ('G11-empty-parsed-map', {}, True, 'unknown_unparsable_output', 'unresolved (all tests missing)'),
]
UPSTREAM_REASON = {
    'G05-one-f2p-skipped': 'SKIPPED is neither passed nor failed (L123-128): dropped from the F2P denominator, 1/1 = 1',
    'G06-all-f2p-skipped': 'all F2P dropped: total 0 scores 1 (L199-200) -> vacuously resolved',
    'G07-p2p-skipped': 'SKIPPED P2P dropped: P2P total 0 scores 1 (L209-211)',
    'G08-f2p-xfail': 'XFAIL counts as passed (L27-28); the declared rule requires PASSED',
    'G10-bad-log-marker': 'upstream reports unresolved; the contract maps it to unknown (a label difference, never a pass)',
    'G11-empty-parsed-map': 'upstream: every test missing -> failure; the contract labels it unknown (never a pass)',
}


def discrepancies():
    out = []
    for fid, sm, ok, declared, upstream in FIXTURES:
        up_pass = upstream.startswith('resolved')
        if (declared == 'resolved') != up_pass:
            out.append(dict(id=fid, declared=declared, upstream=upstream, severity='COUNTS AS PASS UPSTREAM',
                            reason=UPSTREAM_REASON[fid]))
        elif declared != upstream.split(' ')[0]:
            out.append(dict(id=fid, declared=declared, upstream=upstream, severity='label only',
                            reason=UPSTREAM_REASON.get(fid, '')))
    return out
