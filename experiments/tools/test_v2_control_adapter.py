"""Fake-runtime boundary tests for the control adapter (lead 7f9673a): call order, no prediction application in no_change,
exactly one eval-script invocation per attempt with the identical script, retry only on timeout/missing report, and the
qualification rule (a false strict score alone never qualifies a negative control). No upstream code, no containers."""
import ast, sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_adapter'))
import control_adapter as A  # noqa: E402

SCRIPT = '#!/bin/bash\n# generated eval script (fake)\n'
INST = dict(instance_id='x__y-1', eval_script_sha256=A.sha(SCRIPT), FAIL_TO_PASS=['t::f1', 't::f2'], PASS_TO_PASS=['t::p1'])
DIG = dict(instance='sha256:' + '1' * 64, env='sha256:' + '2' * 64, base='sha256:' + '3' * 64)
P, F, S, E, X = A.PASSED, A.FAILED, A.SKIPPED, A.ERROR, A.XFAIL


class FakeRuntime(A.Runtime):
    def __init__(self, logs, patch_ok=True):
        self.calls, self.logs, self.patch_ok, self.scripts = [], list(logs), patch_ok, []

    def start(self, image_digest):
        self.calls.append(('start', image_digest)); return 'h%d' % len(self.calls)

    def repo_state(self, h):
        self.calls.append(('repo_state',)); return 'state'

    def apply_patch(self, h, patch_text):
        self.calls.append(('apply_patch', A.sha(patch_text))); return self.patch_ok, 'out'

    def run_eval_script(self, h, script_text, timeout):
        self.calls.append(('run_eval_script',)); self.scripts.append(script_text)
        return self.logs.pop(0)

    def stop(self, h):
        self.calls.append(('stop',))


def parser(log):
    """Fake pinned-parser binding: (statuses, completion_ok, note). 'EVALFAIL|' prefix = evaluator-failure marker."""
    if log in (None, 'garbage'):
        return None, False, 'unparsable'
    ok = not log.startswith('EVALFAIL|')
    body = log.split('|', 1)[1] if not ok else log
    st = {}
    for item in body.split(';'):
        k, v = item.split('=')
        st[k] = None if v == 'None' else v
    return st, ok, 'ok' if ok else 'evaluator failure marker'


def log(**st):
    return ';'.join('t::%s=%s' % kv for kv in st.items())


def test_module_imports_nothing_that_executes():
    tree = ast.parse(Path(A.__file__).read_text())
    mods = {a.name.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module.split('.')[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not mods & {'subprocess', 'docker', 'swebench', 'os', 'shutil', 'requests'}, mods


def test_no_change_never_applies_a_prediction_and_runs_the_script_once():
    rt = FakeRuntime([(1, log(f1=F, f2=P, p1=P), False)])
    rec = A.run_control('no_change', INST, rt, SCRIPT, parser, DIG)
    assert [c[0] for c in rt.calls] == ['start', 'repo_state', 'run_eval_script', 'repo_state', 'stop']
    assert rec['attempts'][0]['patch_application'] == 'not_applicable' and rec['patch_sha256'] is None
    assert rec['prediction_identity'] == 'no_prediction' and 'not an official submission' in rec['report_scope']
    assert rec['qualification'] == 'qualified' and rec['strict_verified_resolved'] is False


def test_reference_applies_the_patch_then_the_identical_script_once():
    rt = FakeRuntime([(0, log(f1=P, f2=P, p1=P), False)])
    rec = A.run_control('reference', INST, rt, SCRIPT, parser, DIG, reference_patch='diff --git a b')
    assert [c[0] for c in rt.calls] == ['start', 'repo_state', 'apply_patch', 'run_eval_script', 'repo_state', 'stop']
    assert rt.scripts == [SCRIPT] and rec['eval_script_sha256'] == INST['eval_script_sha256']
    assert rec['qualification'] == 'qualified' and rec['strict_verified_resolved'] is True
    nc = FakeRuntime([(1, log(f1=F, f2=F, p1=P), False)])
    A.run_control('no_change', INST, nc, SCRIPT, parser, DIG)
    assert nc.scripts == rt.scripts                                  # both modes invoke the identical script


def test_reference_patch_failure_is_setup_failure_without_running_the_script():
    rt = FakeRuntime([], patch_ok=False)
    rec = A.run_control('reference', INST, rt, SCRIPT, parser, DIG, reference_patch='bad')
    assert 'run_eval_script' not in [c[0] for c in rt.calls] and rec['attempts'][0]['evaluation_status'] == 'setup_failure'
    assert rec['qualification'] == 'diagnose' and rec['strict_verified_resolved'] is None


@pytest.mark.parametrize('attempts,expected_calls', [
    ([(124, None, True), (124, None, True)], 2),                    # timeout twice
    ([(0, None, False), (0, 'garbage', False)], 2),                 # missing, then unparsable report
])
def test_timeouts_and_missing_reports_retry_once_and_never_qualify(attempts, expected_calls):
    for mode, patch in (('no_change', None), ('reference', 'diff')):
        rt = FakeRuntime(list(attempts))
        rec = A.run_control(mode, INST, rt, SCRIPT, parser, DIG, reference_patch=patch)
        assert [c[0] for c in rt.calls].count('run_eval_script') == expected_calls and len(rec['attempts']) == 2
        assert rec['qualification'] == 'diagnose' and rec['strict_verified_resolved'] is None


def test_a_completed_retry_is_used_and_both_attempts_are_recorded():
    rt = FakeRuntime([(124, None, True), (1, log(f1=F, f2=F, p1=P), False)])
    rec = A.run_control('no_change', INST, rt, SCRIPT, parser, DIG)
    assert [a['evaluation_status'] for a in rec['attempts']] == ['timeout', 'completed'] and rec['qualification'] == 'qualified'


@pytest.mark.parametrize('statuses,qualification', [
    (dict(f1=F, f2=P, p1=P), 'qualified'),                          # valid baseline failure
    (dict(f1=P, f2=P, p1=P), 'diagnose'),                           # F2P passes at baseline: negative control not shown
    (dict(f1=F, f2=P), 'diagnose'),                                 # missing required P2P identity
    (dict(f1=F, f2=P, p1=F), 'diagnose'),                           # P2P broken at baseline
    (dict(f1=E, f2=F, p1=P), 'diagnose'),                           # F2P ERROR retained for diagnosis
    (dict(f1=S, f2=F, p1=P), 'diagnose'),                           # F2P SKIPPED ambiguity
    (dict(f1=X, f2=F, p1=P), 'diagnose'),                           # F2P XFAIL ambiguity
])
def test_no_change_qualification_rule(statuses, qualification):
    rt = FakeRuntime([(1, log(**statuses), False)])
    rec = A.run_control('no_change', INST, rt, SCRIPT, parser, DIG)
    assert rec['qualification'] == qualification, rec['reason']
    if qualification == 'diagnose' and statuses != dict(f1=P, f2=P, p1=P):
        assert rec['strict_verified_resolved'] is False              # a false strict score alone did not qualify


def test_empty_p2p_needs_the_declared_limitation_and_reference_needs_all_passed():
    inst = dict(INST, PASS_TO_PASS=[])
    assert A.run_control('no_change', inst, FakeRuntime([(1, log(f1=F, f2=F), False)]), SCRIPT, parser, DIG)['qualification'] == 'diagnose'
    inst['empty_p2p_declared'] = True
    assert A.run_control('no_change', inst, FakeRuntime([(1, log(f1=F, f2=F), False)]), SCRIPT, parser, DIG)['qualification'] == 'qualified'
    rec = A.run_control('reference', INST, FakeRuntime([(0, log(f1=P, f2=S, p1=P), False)]), SCRIPT, parser, DIG, reference_patch='d')
    assert rec['qualification'] == 'diagnose' and rec['strict_verified_resolved'] is False


def test_refusals_before_any_runtime_call():
    for kw in (dict(mode='no_change', eval_script=SCRIPT + 'x'), dict(mode='reference', eval_script=SCRIPT),
               dict(mode='no_change', eval_script=SCRIPT, reference_patch='d'), dict(mode='bogus', eval_script=SCRIPT),
               dict(mode='no_change', eval_script=SCRIPT, image_digests={})):
        rt = FakeRuntime([])
        with pytest.raises(A.ControlRefused):
            A.run_control(kw['mode'], INST, rt, kw['eval_script'], parser, kw.get('image_digests', DIG), reference_patch=kw.get('reference_patch'))
        assert rt.calls == []


@pytest.mark.parametrize('raw', ['BOGUS', None, 'XPASS'])
def test_f2p_status_outside_the_allowlist_never_qualifies_and_is_retained_raw(raw):
    # lead c85173a probes: qualify('no_change', ['a','b'], ['c'], {'a':'FAILED','b':<raw>,'c':'PASSED'}, False)
    q, why, _ = A.qualify('no_change', ['a', 'b'], ['c'], {'a': 'FAILED', 'b': raw, 'c': 'PASSED'}, False)
    assert q == 'diagnose' and repr(raw) in why
    rt = FakeRuntime([(1, log(f1=F, f2=raw, p1=P), False)])
    rec = A.run_control('no_change', INST, rt, SCRIPT, parser, DIG)
    assert rec['qualification'] == 'diagnose' and rec['attempts'][-1]['per_test_status']['t::f2'] == raw


def test_invalid_completion_marker_blocks_qualification_even_with_parseable_tests():
    bad = 'EVALFAIL|' + log(f1=F, f2=P, p1=P)
    rt = FakeRuntime([(1, bad, False), (1, bad, False)])
    rec = A.run_control('no_change', INST, rt, SCRIPT, parser, DIG)
    assert [a['evaluation_status'] for a in rec['attempts']] == ['invalid_completion', 'invalid_completion']
    assert rec['qualification'] == 'diagnose' and rec['strict_verified_resolved'] is None


def test_nonzero_exit_alone_is_not_an_evaluator_failure():
    rt = FakeRuntime([(2, log(f1=F, f2=F, p1=P), False)])
    rec = A.run_control('no_change', INST, rt, SCRIPT, parser, DIG)
    assert rec['attempts'][0]['exit_code'] == 2 and rec['qualification'] == 'qualified'
