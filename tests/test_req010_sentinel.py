"""DTR-REQ-010 sentinel driver: binding, admission, peer/conflict checks, attempt/deadline/retry paths and the real
process-group kill (a stub child; no docker, model or evaluator)."""
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location('req010', ROOT / 'experiments/v2_adapter/req010_sentinel.py')
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def stamps():
    n = iter(range(100))
    return lambda: 'T%02d' % next(n)


def no_collect(tag, rid):
    return {}, 'report_present'


# ------------------------------------------------------------------ binding and admission
def test_binding_accepts_the_committed_queue_rank_1():
    ok, d = M.probe_binding(ROOT)
    assert ok and d['rank1'] == 'astropy__astropy-14598' and d['queue_sha256_recomputed'] == M.QUEUE_SHA


def test_binding_rejects_a_reordered_queue(tmp_path):
    rec = json.loads((ROOT / M.REQ009_JSON).read_text())
    rec['queue'] = [rec['queue'][1], rec['queue'][0]] + rec['queue'][2:]
    (tmp_path / M.REQ009_JSON).parent.mkdir(parents=True)
    (tmp_path / M.REQ009_JSON).write_text(json.dumps(rec))
    ok, d = M.probe_binding(tmp_path)
    assert not ok and d['rank1'] != 'astropy__astropy-14598'


def test_admission_fails_closed_on_any_failed_or_crashing_probe():
    ok = lambda root: (True, {'x': 1})

    def boom(root):
        raise RuntimeError('docker socket unreachable')
    assert M.admission(ROOT, {'a': ok})['admitted'] is True
    assert M.admission(ROOT, {'a': ok, 'disk': lambda r: (False, {})})['admitted'] is False
    rec = M.admission(ROOT, {'a': ok, 'runtime': boom})
    assert rec['admitted'] is False and 'docker socket unreachable' in rec['runtime']['detail']['error']


@pytest.mark.parametrize('line, rule', [
    ('/opt/llama/bin/llama-server -m x.gguf --port 8291', 'executable:llama-server'),
    ('ollama serve', 'executable:ollama'),
    ('python3 -u -m swebench.harness.run_evaluation --run_id x', 'module:swebench.harness.run_evaluation'),
    ('/v/bin/python3.12 -X utf8 experiments/v2_adapter/qualification_batch.py', 'script:qualification_batch.py'),
    ('.venv/bin/python experiments/code_routing/run.py --stage live', 'script:run.py --stage'),
    ('Python experiments/v2_adapter/req010_sentinel.py --child a b c d', 'script:req010_sentinel.py'),
    ('.venv/bin/python -c import unittest; llama-server run.py --stage qualification_batch.py', None),
    ('pgrep -fl run.py --stage', None),
    ('vim experiments/v2_adapter/qualification_batch.py', None),
    ('grep -r llama-server .', None),
    ('bash -c curl localhost:8291/health', None),
    ('.venv/bin/python experiments/code_routing/run.py --help', None),
])
def test_conflict_rule_from_realistic_ps_lines(line, rule):
    assert M.conflicting(line.split()) == rule


def test_own_ancestors_are_not_conflicts():
    rows = [(1, 0, ['launchd']), (50, 1, ['python', 'experiments/v2_adapter/req010_sentinel.py']), (60, 50, ['sh']),
            (70, 60, ['python', 'x.py'])]
    assert M.ancestors(rows, 70) == {70, 60, 50, 1}


def test_window_ends_take_the_start_date_for_a_bare_end_time():
    ends, unparsed = M.window_ends('"window_utc": "2026-09-23T06:15:00Z to 07:45:00Z hard end", '
                                   '"recorded": "2026-09-22T05:00Z"')
    assert M.utc(max(ends)) == '2026-09-23T07:45:00Z' and M.utc(min(ends)) == '2026-09-22T05:00:00Z' and unparsed == 0


def test_window_ends_read_fractional_and_offset_timestamps_and_count_unparsed_ones():
    ends, unparsed = M.window_ends('"a": "2026-09-24T12:00:00.000Z", "b": "2026-09-22T05:48:18.996883+00:00"')
    assert sorted(M.utc(e) for e in ends) == ['2026-09-22T05:48:18Z', '2026-09-24T12:00:00Z'] and unparsed == 0
    ends, unparsed = M.window_ends('"hard_end": "2026-09-24T12:00:00-04:00"')    # a non-UTC offset is not parsed
    assert unparsed == 1


def peer_run(lease='none', updated='2026-09-24T10:38:37Z', window='2026-09-23T06:15:00Z to 07:45:00Z', local='abc123'):
    status = '**Last updated: %s** — x. Run/lease: **%s**. E14: **HOLD**' % (updated, lease)

    def run(cmd, env=None, timeout=60):
        s = ' '.join(cmd)
        if 'api.github.com' in s:
            return 0, json.dumps([{'sha': 'abc123'}]), ''
        if 'raw.githubusercontent.com' in s:
            return 0, status, ''
        if 'rev-parse' in s:
            return 0, local + '\n', ''
        if 'ls-tree' in s:
            return 0, 'docs/e13a_window_request_20260923.json\ndocs/notes.md\n', ''
        if 'show' in s:
            return 0, '{"window_utc": "%s"}' % window, ''
        return 1, '', ''
    return run


NOW = M.epoch('2026-09-24', '11:00:00')


def test_peer_status_admits_only_a_fresh_no_lease_status_without_future_windows():
    ok, d = M.peer_status(run=peer_run(), now=NOW)
    assert ok and d['run_lease'] == 'none' and d['status_age_seconds'] == 1283 and not d['window_records_reaching_the_future']
    assert not M.peer_status(run=peer_run(lease='E14 run active'), now=NOW)[0]
    assert not M.peer_status(run=peer_run(updated='2026-09-24T06:00:00Z'), now=NOW)[0]      # 5 h old
    ok, d = M.peer_status(run=peer_run(window='2026-09-24T10:30:00Z to 12:00:00Z'), now=NOW)
    assert not ok and d['window_records_reaching_the_future'][0]['latest_time'] == '2026-09-24T12:00:00Z'
    ok, d = M.peer_status(run=peer_run(local='old999'), now=NOW)                          # stale local clone
    assert not ok and d['local_clone_equals_remote_head'] is False
    ok, d = M.peer_status(run=peer_run(window='2026-09-24T12:00:00-04:00'), now=NOW)      # unreadable timestamp
    assert not ok and d['window_records_with_unparsed_timestamps']


def test_runtime_requires_enabled_rosetta_and_no_active_qemu():
    def run(qemu):
        def r(cmd, env=None, timeout=60):
            s = ' '.join(cmd)
            if 'list' in s:
                return 0, json.dumps({'name': 'dtr', 'status': 'Running', 'arch': 'aarch64'}), ''
            if 'binfmt_misc/rosetta' in s:
                return 0, 'enabled\ninterpreter /mnt/lima-rosetta/rosetta\n', ''
            if 'binfmt_misc/qemu-x86_64' in s:
                return (0, qemu + '\n', '') if qemu else (1, '', 'No such file')
            if 'docker info' in s:
                return 0, json.dumps({'ServerVersion': '29.5.2', 'Architecture': 'aarch64'}), ''
            return 1, '', ''
        return r
    yaml = 'vmType: vz\nrosetta: true\n'
    assert M.probe_runtime(ROOT, run(None), yaml)[0] is True
    assert M.probe_runtime(ROOT, run('disabled'), yaml)[0] is True
    assert M.probe_runtime(ROOT, run('enabled'), yaml)[0] is False
    assert M.probe_runtime(ROOT, run(None), 'vmType: qemu\nrosetta: false\n')[0] is False


def test_disk_threshold_parsing():
    run = lambda cmd, env=None, timeout=60: (0, 'Filesystem 1024-blocks Used Available\n/dev/vda1 1 1 %d /\n'
                                            % (19 * 1024 * 1024), '')
    ok, d = M.probe_disk(ROOT, run)
    assert d['vm_free_gib'] == 19.0 and ok is False


# ------------------------------------------------------------------ attempt loop
def test_single_attempt_when_the_controls_complete(tmp_path):
    calls, cleaned = [], []

    def run(tag, rid, deadline):
        calls.append((tag, rid))
        return {'instance_id': M.TARGET, 'qualified': True, 'acceptance': {'k': True}}
    att = M.run_attempts(tmp_path, run, no_collect, lambda rid: cleaned.append(rid) or {}, Clock(), 1000.0,
                         stamp=stamps())
    assert calls == [('attempt-1-T00', 'req010-stock-gold-attempt-1-T00')] and cleaned == ['req010-stock-gold-attempt-1-T00']
    assert att[0]['qualified'] is True and M.status_of(att) == 'QUALIFIED'
    assert json.loads((tmp_path / att[0]['dir'] / 'summary.json').read_text())['attempt'] == 1


@pytest.mark.parametrize('cls, n_calls', [('timeout', 2), ('missing_report', 2), ('setup_failure', 1),
                                          ('report_present', 1)])
def test_retry_only_for_a_stock_timeout_or_missing_report(tmp_path, cls, n_calls):
    calls = []

    def run(tag, rid, deadline):
        calls.append(rid)
        return {'instance_id': M.TARGET, 'stage_failed': 'stock_gold'}
    att = M.run_attempts(tmp_path, run, lambda tag, rid: ({}, cls), lambda rid: {}, Clock(), 1000.0, stamp=stamps())
    assert len(calls) == n_calls and M.status_of(att) == 'DIAGNOSIS_STOCK_' + cls.upper()
    if n_calls == 2:
        assert att[0]['retry_reason'] == cls


def test_no_retry_after_an_exception_or_a_failed_acceptance(tmp_path):
    for i, result in enumerate(({'stage_failed': 'exception'},
                                {'qualified': False, 'acceptance': {'no_change_meets_rule': False}})):
        calls = []
        M.run_attempts(tmp_path / str(i), lambda t, r, d: calls.append(r) or dict(result, instance_id=M.TARGET),
                       no_collect, lambda rid: {}, Clock(), 1000.0, stamp=stamps())
        assert len(calls) == 1


def test_deadline_is_recorded_cleaned_up_and_not_retried(tmp_path):
    clock, seen, cleaned = Clock(1000.0), [], []

    def run(tag, rid, deadline):
        seen.append(deadline)
        clock.t = deadline
        raise TimeoutError('child group killed; group confirmed gone: True')
    att = M.run_attempts(tmp_path, run, no_collect, lambda rid: cleaned.append(rid) or {'remaining': []}, clock,
                         1000.0, cap=7200, reserve=600, stamp=stamps())
    assert seen == [7600.0] and len(att) == 1 and cleaned and M.status_of(att) == 'INCOMPLETE_DEADLINE'
    rec = json.loads((tmp_path / att[0]['dir'] / 'summary.json').read_text())
    assert rec['stage_failed'] == 'deadline' and 'confirmed gone: True' in rec['kill']


def test_interruption_writes_the_record_cleans_up_and_reraises(tmp_path):
    cleaned = []

    def run(tag, rid, deadline):
        raise M.Interrupted('SIGTERM')
    with pytest.raises(M.Interrupted):
        M.run_attempts(tmp_path, run, no_collect, lambda rid: cleaned.append(rid) or {}, Clock(), 1000.0,
                       stamp=stamps())
    rec = json.loads((tmp_path / M.TARGET / 'attempt-1-T00' / 'summary.json').read_text())
    assert rec['stage_failed'] == 'interrupted' and cleaned


def test_collect_failure_still_cleans_up_and_writes_the_record(tmp_path):
    cleaned = []

    def bad_collect(tag, rid):
        raise FileExistsError('receipt exists')
    att = M.run_attempts(tmp_path, lambda t, r, d: {'instance_id': M.TARGET, 'qualified': True}, bad_collect,
                         lambda rid: cleaned.append(rid) or {'remaining': []}, Clock(), 1000.0, stamp=stamps())
    rec = json.loads((tmp_path / att[0]['dir'] / 'summary.json').read_text())
    assert cleaned and 'FileExistsError' in rec['receipts']['collect_error'] and rec['qualified'] is True


def test_interrupt_during_cleanup_keeps_the_verdict_and_reraises_with_attempts(tmp_path):
    def cleanup(rid):
        raise M.Interrupted('SIGHUP')
    with pytest.raises(M.Interrupted) as e:
        M.run_attempts(tmp_path, lambda t, r, d: {'instance_id': M.TARGET, 'qualified': True,
                                                  'acceptance': {'a': True}}, no_collect, cleanup, Clock(), 1000.0,
                       stamp=stamps())
    assert e.value.attempts[0]['qualified'] is True and M.status_of(e.value.attempts) == 'QUALIFIED'
    rec = json.loads((tmp_path / M.TARGET / 'attempt-1-T00' / 'summary.json').read_text())
    assert rec['interrupted_after_attempt'] == 'SIGHUP' and 'Interrupted' in rec['cleanup']['error']


def test_retry_requires_a_passing_preflight(tmp_path):
    calls = []
    att = M.run_attempts(tmp_path, lambda t, r, d: calls.append(r) or {'instance_id': M.TARGET, 'stage_failed': 'stock_gold'},
                         lambda t, r: ({}, 'timeout'), lambda rid: {}, Clock(), 1000.0, stamp=stamps(),
                         preflight=lambda: (False, {'conflicts_ok': False}))
    assert len(calls) == 1 and att[1]['not_started'] == 'retry preflight failed'


def test_retry_not_started_after_the_attempt_deadline(tmp_path):
    clock = Clock(1000.0)

    def run(tag, rid, deadline):
        clock.t = deadline + 1
        return {'instance_id': M.TARGET, 'stage_failed': 'stock_gold'}
    att = M.run_attempts(tmp_path, run, lambda t, r: ({}, 'timeout'), lambda rid: {}, clock, 1000.0, stamp=stamps())
    assert att[1] == {'attempt': 2, 'not_started': 'global cap reached before the attempt'}
    assert M.status_of(att) == 'INCOMPLETE_CAP_BEFORE_RETRY'


def test_outputs_are_no_clobber(tmp_path):
    (tmp_path / M.TARGET / 'attempt-1-T00').mkdir(parents=True)
    with pytest.raises(FileExistsError):
        M.run_attempts(tmp_path, lambda t, r, d: {}, no_collect, lambda rid: {}, Clock(), 1000.0, stamp=stamps())


def test_classify_stock(tmp_path):
    d = tmp_path / 's'
    d.mkdir()
    assert M.classify_stock(d) == 'setup_failure'
    (d / 'test_output.txt').write_text('ran\n\nTimeout error: 1800 seconds exceeded.')
    assert M.classify_stock(d) == 'timeout'
    (d / 'test_output.txt').write_text('ran all tests')
    assert M.classify_stock(d) == 'missing_report'
    (d / 'report.json').write_text('{}')
    assert M.classify_stock(d) == 'report_present'


# ------------------------------------------------------------------ real runner, cleanup, sanitizing
STUB = '''import subprocess, sys, time
subprocess.Popen(['sleep', '%s'])
open(sys.argv[2] + '/grandchild_started', 'w').close()
time.sleep(60)
'''


def test_real_runner_kills_the_whole_process_group_at_the_deadline(tmp_path, monkeypatch):
    monkeypatch.setattr(M, 'KILL_GRACE_SECONDS', 1)
    marker = '59.%d' % os.getpid()                                     # unique to this test process
    stub = tmp_path / 'stub.py'
    stub.write_text(STUB % marker)
    run = M.real_run_attempt(tmp_path, dict(os.environ), {}, py=sys.executable, script=stub)
    t0 = time.time()
    with pytest.raises(TimeoutError, match='confirmed gone: True'):
        run('attempt-1-T00', 'rid', time.time() + 2)
    assert time.time() - t0 < 20
    raw = tmp_path / M.RUN / 'attempt-1-T00'
    assert (raw / 'grandchild_started').exists()
    time.sleep(0.5)
    live = [l for l in os.popen('ps -axo pid=,stat=,args=').read().splitlines()
            if ('sleep ' + marker in l or str(stub) in l) and 'Z' not in l.split()[1]]
    assert live == []


def test_real_runner_reports_a_child_without_result(tmp_path):
    stub = tmp_path / 'stub.py'
    stub.write_text('import sys; sys.exit(3)\n')
    run = M.real_run_attempt(tmp_path, dict(os.environ), {}, py=sys.executable, script=stub)
    with pytest.raises(RuntimeError, match='exited 3 without a result'):
        run('attempt-1-T00', 'rid', time.time() + 30)


def test_cleanup_removes_only_this_runs_container_names():
    listed = ['sweb.eval.astropy__astropy-14598.req010-stock-gold-attempt-1-T00',
              'sweb.eval.astropy__astropy-14598.other-run', 'dtr-qual-astropy-astropy-14598-reference-1',
              'dtr-qual-astropy-astropy-12907-reference-1', 'peer-container']
    removed = []

    def run(cmd, env=None, timeout=60):
        if cmd[:3] == ['docker', 'rm', '-f']:
            for n in cmd[3:]:
                removed.append(n)
                listed.remove(n)
            return 0, '', ''
        return 0, '\n'.join(listed), ''
    rec = M.real_cleanup({}, run)('req010-stock-gold-attempt-1-T00')
    assert removed == ['dtr-qual-astropy-astropy-14598-reference-1',
                       'sweb.eval.astropy__astropy-14598.req010-stock-gold-attempt-1-T00']
    assert rec['remaining'] == [] and rec['complete'] is True and 'peer-container' in listed


def test_sanitize_replaces_every_occurrence():
    s = '%s/work/x %s/.colima/y and again %s/z' % (M.ROOT, M.HOME, M.ROOT)
    assert M.sanitize({'k': [s]}) == {'k': ['./work/x ~/.colima/y and again ./z']}
    assert M.scrub_env({'PATH': '/bin', 'GITHUB_TOKEN': 'x', 'SSH_AUTH_SOCK': 'y'}) == ({'PATH': '/bin'},
                                                                                       ['GITHUB_TOKEN', 'SSH_AUTH_SOCK'])


# ------------------------------------------------------------------ main
def test_blocked_admission_writes_a_record_and_runs_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(M, 'ROOT', tmp_path)
    monkeypatch.setattr(M, 'PROBES', {'binding': lambda r: (True, {}), 'disk': lambda r: (False, {'vm_free_gib': 3.0})})
    monkeypatch.setattr(M, 'run_attempts', lambda *a, **k: pytest.fail('must not run'))
    with pytest.raises(M.Blocked, match='BLOCKED'):
        M.main([])
    s = json.loads((tmp_path / M.OUT / 'sentinel_summary.json').read_text())
    assert s['status'] == 'BLOCKED' and s['failed_admission_checks'] == ['disk'] and s['executed'] is False
    with pytest.raises(FileExistsError):
        M.main([])


def test_admitted_path_writes_a_hash_bound_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(M, 'ROOT', tmp_path)
    monkeypatch.setattr(M, 'PROBES', {'binding': lambda r: (True, {}), 'sources': lambda r: (True, {'control_sources': {}})})
    monkeypatch.setattr(M.signal, 'signal', lambda *a, **k: None)
    monkeypatch.setattr(M.subprocess, 'Popen', lambda *a, **k: (_ for _ in ()).throw(OSError('no caffeinate in tests')))
    monkeypatch.setattr(M, 'real_run_attempt', lambda root, env, sources: (lambda t, r, d: {'instance_id': M.TARGET,
                                                                                             'qualified': True,
                                                                                             'acceptance': {'a': True}}))
    monkeypatch.setattr(M, 'real_collect', lambda root: no_collect)
    monkeypatch.setattr(M, 'real_cleanup', lambda env: (lambda rid: {'remaining': [], 'complete': True}))
    monkeypatch.setattr(M, 'probe_disk', lambda root: (True, {'vm_free_gib': 80.0}))
    monkeypatch.setattr(M, 'probe_images', lambda root: (True, {'local_images': {}}))
    M.main([])
    s = json.loads((tmp_path / M.OUT / 'sentinel_summary.json').read_text())
    assert s['status'] == 'QUALIFIED' and s['within_cap'] is True and len(s['admission_sha256']) == 64
    assert s['cleanup_complete'] is True and not (tmp_path / M.OUT / 'USERNAME_FOUND.json').exists()
    assert s['attempts'][0]['acceptance'] == {'a': True}


class FakeProc:
    def __init__(self):
        self.waits = 0

    def wait(self, timeout):
        self.waits += 1
        raise M.subprocess.TimeoutExpired('x', timeout)

    def poll(self):
        return None


def test_wait_uses_the_wall_clock_not_the_wait_budget():
    clock = Clock(0.0)
    p = FakeProc()
    orig = p.wait

    def wait(timeout):
        clock.t += 3600                                      # the host slept for an hour during this wait
        return orig(timeout)
    p.wait = wait
    with pytest.raises(M.subprocess.TimeoutExpired):
        M.wait_wall(p, deadline=100.0, clock=clock, step=10.0)
    assert p.waits == 1                                      # the deadline is noticed on the first wake-up


def test_child_watchdog_condition():
    assert M.should_stop(50, 1000.0, getppid=lambda: 50, clock=lambda: 999.0) is False
    assert M.should_stop(50, 1000.0, getppid=lambda: 1, clock=lambda: 999.0) is True        # parent died
    assert M.should_stop(50, 1000.0, getppid=lambda: 50, clock=lambda: 1000.0) is True      # wall deadline


def test_first_signal_disarms_further_signals():
    saved = {s: M.signal.getsignal(s) for s in (M.signal.SIGINT, M.signal.SIGTERM, M.signal.SIGHUP)}
    try:
        with pytest.raises(M.Interrupted, match='SIGTERM'):
            M.raise_interrupted(M.signal.SIGTERM, None)
        assert all(M.signal.getsignal(s) == M.signal.SIG_IGN for s in saved)
    finally:
        for s, h in saved.items():
            M.signal.signal(s, h)
