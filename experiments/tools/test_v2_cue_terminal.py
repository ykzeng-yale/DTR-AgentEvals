"""Deterministic fixtures for the DTR-REQ-005 cue-v1 terminal phase (experiments/v2_agent/cue_terminal.py): the
Submitted-only endpoint first, then the supervised all-exit diagnostic, then cleanup from a `finally` path, under the
lead's deadline contract (docs/theory_feedback_20260923_req005_review.md, "Endpoint then diagnostic then cleanup").

No model, llama-server, container, network or benchmark-generated code. The executor fixtures run real `bash`/`git`
in disposable temporary Git repositories this file creates, and the "hung executor" is a bash process that ignores
SIGTERM and leaves a SIGTERM-ignoring grandchild holding its output pipe.

Every expected value is written out BY HAND as a literal: deadlines, budgets, per-subprocess bounds, reason strings,
blob SHAs, the exact expected submission diffs and their sha256 digests. The literals below were produced
independently with git and `shasum -a 256` in a scratch repository, not through the module:
    MOD_ONLY_DIFF  177 bytes  91f6f9970ea8dbd983e8472dd0e73663b591532e19a1f63c726913b82945b175
    MOD_NEW_DIFF   379 bytes  27788b1f35a18178bf79d7f78cd17bbe50897761c99112455ec5abce4467335b
    ''               0 bytes  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
    'n = 1\\n'        6 bytes  df31c7f4ef3af48aafd4e8c743ab41d6592018b90fd7913cf82284d50bd18a5b
Where a git-computed tree SHA is needed, this file computes it with its OWN git commands through a private index,
never through the module's or workspace_capture's command templates. The frozen yaml-v1 sources are hashed and read
as text, never imported.
"""
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/v2_agent'))
import cue_terminal as T  # noqa: E402
import exit_capture as XC  # noqa: E402

EPOCH = 1_000_000.0
EMPTY_SHA = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
N_EQ_1_SHA = 'df31c7f4ef3af48aafd4e8c743ab41d6592018b90fd7913cf82284d50bd18a5b'
MOD_ONLY_DIFF = (b'diff --git a/mod.py b/mod.py\n'
                 b'index 7d4290a117a4ddcc11daae7ea675841033830c8f..407de3068e7b5950585d5abed9776d104235a85d 100644\n'
                 b'--- a/mod.py\n'
                 b'+++ b/mod.py\n'
                 b'@@ -1 +1 @@\n'
                 b'-x = 1\n'
                 b'+x = 2\n')
MOD_ONLY_SHA = '91f6f9970ea8dbd983e8472dd0e73663b591532e19a1f63c726913b82945b175'
MOD_NEW_DIFF = MOD_ONLY_DIFF + (b'diff --git a/new_file.py b/new_file.py\n'
                                b'new file mode 100644\n'
                                b'index 0000000000000000000000000000000000000000..'
                                b'4a3f3148a6563c03794f7e788da042e0d5214f98\n'
                                b'--- /dev/null\n'
                                b'+++ b/new_file.py\n'
                                b'@@ -0,0 +1 @@\n'
                                b'+n = 1\n')
MOD_NEW_SHA = '27788b1f35a18178bf79d7f78cd17bbe50897761c99112455ec5abce4467335b'

NO_TIME_REASON = ('no diagnostic time remains: the diagnostic deadline min(start + 30 s, absolute cleanup deadline '
                  '- 90 s - 4 s hand-off) is not after the diagnostic start; the diagnostic was skipped so cleanup '
                  'keeps its reserve')
NO_EXECUTOR_REASON = ('no supervised executor was supplied (no verified episode-owned container): the diagnostic '
                      'is unavailable, not empty')
END_INVALID_REASON = ('the actual inference end is not a finite epoch time: the phase cannot be anchored, so no '
                      'diagnostic time is granted and cleanup keeps the existing cap')
CAP_INVALID_REASON = 'the existing absolute cleanup cap is not a finite epoch time'
START_INVALID_REASON = 'the diagnostic start (clock) is not a finite epoch time'
ANCHOR_NOTE = ('the reported inference end is later than the diagnostic start; the independent 30-s maximum still '
               'bounds the diagnostic and the cleanup deadline never exceeds the existing cap')
FOUR_LABELS = ['tree', 'status', 'diff', 'untracked_list']
ALL_SECTIONS = ('tree', 'status', 'diff', 'untracked')

# Frozen yaml-v1 execution sources and their bound sha256 (docs/req005_instrumentation_spec_20260923.md section 7,
# agreeing with results/v2_agent/pilot_20260922_yaml_v1/cohort_binding.json).
FROZEN = {
    'experiments/v2_agent/pilot_episode.py': '164b7878f7a720a74ba913b97ee07ba287a556cb3ac6310aa95d2f2c91dbe6f5',
    'experiments/v2_agent/pilot_runner.py': '974df398415db22ed6676e04f0be5c1d93a7599d725f43f03fb989d77cbba10c',
    'experiments/v2_agent/pilot_cohort.py': '59d271bd32217bd3c3a56c3dd4c20fd8eadd441377db7334c0932a325100851a',
    'experiments/v2_agent/pilot_report.py': '1afa9002344557f4fd518044313f2fd277528a06a5fef667966175804711e10f',
    'experiments/v2_agent/pilot_grade.py': '0c2a5a5da861a42fd1dbc79c01ff4b031bff8d0a3cbcda8b90e869161f70e7f1',
}


# ---------------------------------------------------------------- fixtures

def git(repo, *a, **kw):
    return subprocess.run(['git', '-C', str(repo), *a], check=True, capture_output=True, text=True, **kw)


def make_repo(tmp_path):
    r = tmp_path / 'testbed'
    r.mkdir()
    git(r, 'init', '-q')
    git(r, 'config', 'user.email', 'f@x')
    git(r, 'config', 'user.name', 'f')
    (r / 'keep.py').write_text('a = 1\n')
    (r / 'mod.py').write_text('x = 1\n')
    (r / '.gitignore').write_text('*.pyc\n')
    git(r, 'add', '-A')
    git(r, 'commit', '-qm', 'base')
    return r


def whole_worktree_tree(repo, index_name='independent-index'):
    """The whole working tree's SHA through a private index, with this file's own git commands."""
    index = Path(repo).parent / index_name
    env = dict(os.environ, GIT_INDEX_FILE=str(index))
    try:
        git(repo, 'read-tree', 'HEAD', env=env)
        git(repo, 'add', '-A', env=env)
        return git(repo, 'write-tree', env=env).stdout.strip()
    finally:
        if index.exists():
            index.unlink()


def frozen_ex(repo):
    """The frozen driver's adapter shape: (returncode, merged output decoded as DockerEnvironment does)."""
    def ex(cmd):
        p = subprocess.run(['bash', '-c', cmd], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return p.returncode, p.stdout.decode('utf-8', errors='replace')
    return ex


def bash_argv(cmd):
    return ['bash', '-c', cmd]


def constant(t):
    return lambda: t


def shifted_real_clock(epoch):
    m0 = time.monotonic()
    return lambda: epoch + (time.monotonic() - m0)


class Cleanup:
    def __init__(self):
        self.calls = []

    def __call__(self, deadline):
        self.calls.append(deadline)
        return dict(confirmed=True, state='stopped', fixture='no container exists in this test')


def gone(pid, within):
    """True once `pid` no longer exists (reaped), polling for up to `within` seconds."""
    end = time.monotonic() + within
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        if time.monotonic() >= end:
            return False
        time.sleep(0.02)


def section_states(diag):
    return {name: diag['sections'][name]['state'] for name in ALL_SECTIONS}


def hang_argv(pidfile):
    """A leader that ignores TERM/HUP/INT and a TERM-ignoring grandchild that inherits (and holds) the stdout pipe."""
    return ['bash', '-c', 'trap "" TERM HUP INT; sleep 30 & echo $! > "$0"; wait; sleep 30', str(pidfile)]


def read_pid(pidfile, within=5.0):
    end = time.monotonic() + within
    while time.monotonic() < end:
        text = pidfile.read_text().strip() if pidfile.exists() else ''
        if text:
            return int(text)
        time.sleep(0.02)
    raise AssertionError('the fixture never wrote its grandchild pid')


# ---------------------------------------------------------------- frozen reference, untouched

def test_the_frozen_yaml_v1_sources_are_byte_identical_to_their_bound_hashes():
    for rel, digest in FROZEN.items():
        assert hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() == digest, rel


def test_the_existing_cleanup_cap_is_the_frozen_drivers_deadline_plus_120():
    text = (ROOT / 'experiments/v2_agent/pilot_episode.py').read_text()
    assert 'deadline = min(args.episode_deadline, args.block_deadline)' in text
    assert "cleanup_owned_container(getattr(self, 'container_id', None), deadline + 120)" in text
    assert T.existing_cleanup_cap(5000.0, 4800.0) == 4920.0
    assert T.existing_cleanup_cap(4800.0, 5000.0) == 4920.0
    assert T.existing_cleanup_cap(1_001_500.0, 1_003_000.0) == 1_001_620.0


def test_the_module_imports_no_frozen_driver_and_carries_no_private_path():
    source = (ROOT / 'experiments/v2_agent/cue_terminal.py').read_text()
    for name in ('pilot_episode', 'pilot_runner', 'pilot_cohort', 'pilot_report', 'pilot_grade'):
        assert 'import %s' % name not in source
        assert 'from %s' % name not in source
    private = 'yukang' + 'zengcmac'
    assert private not in source
    assert private not in Path(__file__).read_text()


# ---------------------------------------------------------------- deadlines (pure)

def test_an_early_finished_episode_is_anchored_at_its_actual_end_not_at_its_unused_deadline():
    # Inference ended at 1000.0 although its deadline was 2800.0 (existing cap 2920.0); the diagnostic starts at 1002.
    plan = T.phase_plan(1000.0, 2920.0, 1002.0)
    assert plan['state'] == 'runnable'
    assert plan['anchored_deadline'] == 1120.0
    assert plan['absolute_cleanup_deadline'] == 1120.0                 # not 2920.0
    assert plan['absolute_cleanup_binding'] == 'inference_end + 120'
    assert plan['cleanup_reserve_start'] == 1030.0
    assert plan['diagnostic_deadline'] == 1026.0                       # 1030 - the 4-s hand-off margin
    assert plan['diagnostic_deadline_binding'] == 'cleanup_reserve_90s'
    assert plan['diagnostic_budget_s'] == 24.0                         # not 1918 s of leftover inference time
    assert plan['handoff_margin_s'] == 4.0
    assert plan['anchor_consistent'] is True
    assert plan['anchor_note'] is None
    assert plan['reason'] is None
    assert plan['existing_absolute_cleanup_cap'] == 2920.0


def test_the_existing_cap_binds_when_inference_ran_up_to_its_deadline():
    plan = T.phase_plan(2805.0, 2920.0, 2805.5)
    assert plan['state'] == 'runnable'
    assert plan['anchored_deadline'] == 2925.0
    assert plan['absolute_cleanup_deadline'] == 2920.0                 # never enlarged past the existing cap
    assert plan['absolute_cleanup_binding'] == 'existing_cap'
    assert plan['cleanup_reserve_start'] == 2830.0
    assert plan['diagnostic_deadline'] == 2826.0
    assert plan['diagnostic_budget_s'] == 20.5


def test_a_cap_leaving_less_than_ninety_seconds_grants_no_diagnostic_time():
    plan = T.phase_plan(2800.0, 2920.0, 2840.0)                        # 80 s to the cap at the diagnostic start
    assert plan['state'] == 'no_time'
    assert plan['reason'] == NO_TIME_REASON
    assert plan['diagnostic_budget_s'] == 0.0
    assert plan['diagnostic_deadline'] == 2826.0
    assert plan['absolute_cleanup_deadline'] == 2920.0


def test_an_inference_end_reported_after_the_start_is_still_bounded_by_the_independent_30s_maximum():
    plan = T.phase_plan(1100.0, 5000.0, 1000.0)
    assert plan['state'] == 'runnable'
    assert plan['absolute_cleanup_deadline'] == 1220.0
    assert plan['cleanup_reserve_start'] == 1130.0
    assert plan['diagnostic_deadline'] == 1030.0
    assert plan['diagnostic_deadline_binding'] == 'diagnostic_max_30s'
    assert plan['diagnostic_budget_s'] == 30.0
    assert plan['anchor_consistent'] is False
    assert plan['anchor_note'] == ANCHOR_NOTE


@pytest.mark.parametrize('inference_end,cap,start,reason,absolute,binding', [
    (None, 2920.0, 1000.0, END_INVALID_REASON, 2920.0, 'existing_cap (unanchored)'),
    (float('nan'), 2920.0, 1000.0, END_INVALID_REASON, 2920.0, 'existing_cap (unanchored)'),
    (True, 2920.0, 1000.0, END_INVALID_REASON, 2920.0, 'existing_cap (unanchored)'),
    (1000.0, float('nan'), 1000.0, CAP_INVALID_REASON, None, None),
    (1000.0, None, 1000.0, CAP_INVALID_REASON, None, None),
    (1000.0, 2920.0, float('inf'), START_INVALID_REASON, 1120.0, 'inference_end + 120'),
])
def test_an_input_that_is_not_a_finite_epoch_time_grants_no_diagnostic_time(inference_end, cap, start, reason,
                                                                             absolute, binding):
    plan = T.phase_plan(inference_end, cap, start)
    assert plan['state'] == 'invalid'
    assert plan['reason'] == reason
    assert plan['diagnostic_budget_s'] is None
    assert plan['diagnostic_deadline'] is None
    assert plan['absolute_cleanup_deadline'] == absolute
    assert plan['absolute_cleanup_binding'] == binding
    json.dumps(plan, allow_nan=False)                                   # non-finite inputs are recorded as text


@pytest.mark.parametrize('inference_end,cap,start,now,remaining,to_reserve,timeout,dispatch', [
    # the diagnostic deadline is min(start + 30, reserve start - 4), so the remaining diagnostic time binds
    (1000.0, 2920.0, 1000.0, 1000.0, 26.0, 30.0, 26.0, True),       # early finish, diagnostic start
    (1000.0, 2920.0, 1000.0, 1017.25, 8.75, 12.75, 8.75, True),     # mid-diagnostic
    (2805.0, 2920.0, 2805.5, 2806.0, 20.0, 24.0, 20.0, True),       # the existing cap binds
    (1000.0, 1100.0, 1000.0, 1000.0, 6.0, 10.0, 6.0, True),         # a block deadline cuts the phase to 100 s
    (1100.0, 5000.0, 1000.0, 1000.0, 30.0, 130.0, 30.0, True),      # the 30-s maximum binds independently
    (1100.0, 5000.0, 1000.0, 1029.5, 0.5, 100.5, 0.5, True),
    (1000.0, 2920.0, 1000.0, 1026.0, 0.0, 4.0, 0.0, False),         # exhausted: never started
    (1000.0, 2920.0, 1000.0, 1031.5, -5.5, -1.5, -5.5, False),      # past the reserve: never started
])
def test_each_subprocess_bound_is_the_hand_computed_minimum(inference_end, cap, start, now, remaining, to_reserve,
                                                             timeout, dispatch):
    bound = T.subprocess_timeout(T.phase_plan(inference_end, cap, start), now)
    assert bound['remaining_diagnostic_s'] == remaining
    assert bound['to_cleanup_reserve_s'] == to_reserve
    assert bound['subprocess_max_s'] == 60
    assert bound['timeout_s'] == timeout
    assert bound['binding'] == 'remaining_diagnostic_time'
    assert bound['dispatch'] is dispatch


@pytest.mark.parametrize('plan', [None, {'state': 'no_time'}, {'state': 'invalid'}])
def test_a_plan_that_is_not_runnable_never_dispatches(plan):
    bound = T.subprocess_timeout(plan, 1000.0)
    assert bound['dispatch'] is False
    assert bound['timeout_s'] is None


# ---------------------------------------------------------------- the supervised executor

def test_the_executor_returns_the_exact_bytes_and_return_code_of_the_command():
    ex = T.SupervisedExecutor(bash_argv, T.phase_plan(1000.0, 2920.0, 1000.0), clock=constant(1000.0))
    rc, out = ex("printf 'a\\377b\\n'; exit 3")
    assert rc == 3
    assert out.encode('utf-8', 'surrogateescape') == b'a\xffb\n'
    entry = ex.log[0]
    assert entry['outcome'] == 'exited'
    assert entry['timeout_s'] == 26.0                                   # 1030 - 4 s hand-off - 1000
    assert entry['killed'] is False
    assert entry['group_sweep'] == 'no_lingering_members'
    assert entry['output_bytes'] == 4
    assert entry['output_dropped_bytes'] == 0
    assert ex.counts['spawned'] == 1
    assert ex.counts['exited'] == 1


def test_a_detached_descendant_is_swept_after_a_normal_exit(tmp_path):
    pidfile = tmp_path / 'detached.pid'
    ex = T.SupervisedExecutor(bash_argv, T.phase_plan(1000.0, 2920.0, 1000.0), clock=constant(1000.0))
    t0 = time.monotonic()
    rc, out = ex('sleep 30 >/dev/null 2>&1 & echo $! > %s; exit 0' % pidfile)
    assert time.monotonic() - t0 < 5.0
    assert (rc, out) == (0, '')
    assert ex.log[0]['group_sweep'] == 'killed_lingering_members'
    assert gone(read_pid(pidfile), within=5.0)


def test_output_beyond_the_supervisor_cap_is_an_overflow_not_an_observation():
    ex = T.SupervisedExecutor(bash_argv, T.phase_plan(1000.0, 2920.0, 1000.0), clock=constant(1000.0),
                              output_cap_bytes=1000)
    with pytest.raises(T.DiagnosticOutputOverflow):
        ex("head -c 5000 /dev/zero | tr '\\0' x")
    entry = ex.log[0]
    assert entry['outcome'] == 'output_overflow'
    assert entry['output_bytes'] == 1000
    assert entry['output_dropped_bytes'] == 4000
    assert entry['returncode'] == 0
    assert ex.counts['output_overflow'] == 1


def test_a_command_without_remaining_time_is_never_started():
    started = []

    def popen(*a, **k):
        started.append(a)
        raise AssertionError('must not be started')
    ex = T.SupervisedExecutor(bash_argv, T.phase_plan(1000.0, 2920.0, 1000.0), clock=constant(1026.0), popen=popen)
    with pytest.raises(T.DiagnosticNotDispatched):
        ex('true')
    assert started == []
    assert ex.log[0]['outcome'] == 'not_dispatched'
    assert ex.log[0]['timeout_s'] == 0.0
    assert ex.counts == dict(requested=1, not_dispatched=1, argv_errors=0, spawn_errors=0, supervisor_errors=0,
                             spawned=0, exited=0, killed=0, kill_unconfirmed=0, group_not_empty=0,
                             escaped_descendant_suspected=0, output_overflow=0)


def test_an_interrupted_supervisor_still_kills_the_whole_process_group(tmp_path):
    pidfile = tmp_path / 'grandchild.pid'

    class StdoutRaises:
        def __init__(self, real):
            self.real = real

        def fileno(self):
            read_pid(pidfile)                        # the grandchild exists before the supervisor is interrupted
            raise KeyboardInterrupt

        def close(self):
            self.real.close()

    def popen(argv, **kw):
        proc = subprocess.Popen(argv, **kw)
        proc.stdout = StdoutRaises(proc.stdout)
        return proc
    ex = T.SupervisedExecutor(lambda cmd: hang_argv(pidfile), T.phase_plan(1000.0, 2920.0, 1000.0),
                              clock=constant(1000.0), popen=popen)
    t0 = time.monotonic()
    with pytest.raises(KeyboardInterrupt):
        ex('ignored')
    assert time.monotonic() - t0 < 8.0
    entry = ex.log[0]
    assert entry['outcome'] == 'supervisor_error'
    assert entry['error'] == 'KeyboardInterrupt: '
    assert entry['killed'] is True
    assert entry['kill_signal'] == 'SIGKILL'
    assert entry['kill_confirmed'] is True
    assert entry['returncode'] == -9
    assert ex.counts['supervisor_errors'] == 1
    assert ex.counts['killed'] == 1
    assert gone(read_pid(pidfile), within=5.0)
    assert gone(entry['pid'], within=1.0)


# ---------------------------------------------------------------- the terminal phase

def test_a_hung_executor_subprocess_is_killed_at_the_computed_bound_and_cleanup_still_runs(tmp_path):
    r = make_repo(tmp_path)
    base = whole_worktree_tree(r)
    run_dir = tmp_path / 'run'
    run_dir.mkdir()
    pidfile = tmp_path / 'grandchild.pid'
    requested = []

    def argv_for(cmd):
        requested.append(cmd)
        return hang_argv(pidfile)
    cleanup = Cleanup()
    # Inference ended 24.5 s before the phase starts, so the anchored cleanup deadline is EPOCH + 95.5, the reserve
    # starts at EPOCH + 5.5 and the diagnostic (and each subprocess) is bounded 4 s earlier, at EPOCH + 1.5.
    t0 = time.monotonic()
    out = T.run_terminal_phase(
        endpoint=lambda: T.submitted_only_endpoint('LimitsExceeded', base, frozen_ex(r), wd=str(r)),
        inference_end=EPOCH - 24.5, existing_cap=EPOCH + 5000.0, cleanup=cleanup, argv_for=argv_for,
        base_tree=base, out_dir=run_dir, wd=str(r), clock=shifted_real_clock(EPOCH))
    wall = time.monotonic() - t0
    rec = out['record']
    assert rec['plan']['absolute_cleanup_deadline'] == 1_000_095.5
    assert rec['plan']['cleanup_reserve_start'] == 1_000_005.5
    assert rec['plan']['diagnostic_deadline'] == 1_000_001.5
    assert cleanup.calls == [1_000_095.5]
    assert rec['cleanup']['state'] == 'returned'
    assert rec['steps'] == ['endpoint', 'diagnostic', 'cleanup']
    sup = rec['supervisor']
    assert sup['state'] == 'completed'
    assert sup['counts']['spawned'] == 1
    assert sup['counts']['killed'] == 1
    assert sup['counts']['kill_unconfirmed'] == 0
    assert len(requested) == 1                                         # nothing else was started after the kill
    first = sup['log'][0]
    assert first['outcome'] == 'timeout_killed'
    assert first['kill_signal'] == 'SIGKILL'
    assert first['kill_confirmed'] is True
    assert first['returncode'] == -9
    assert first['binding'] == 'remaining_diagnostic_time'
    assert 1.0 < first['timeout_s'] <= 1.5                             # EPOCH + 1.5 minus the phase's own start-up
    assert first['elapsed_s'] >= round(first['timeout_s'], 6) - 1e-6  # never killed before its bound
    assert first['elapsed_s'] < first['timeout_s'] + 1.5               # killed at the bound, not after 30 s
    assert wall < 6.0
    assert gone(read_pid(pidfile), within=5.0)                         # the pipe-holding grandchild is gone too
    assert gone(first['pid'], within=1.0)
    diag = out['diagnostic']
    assert diag['status'] == 'timeout'
    assert diag['changes_observed'] is None
    assert section_states(diag) == {'tree': 'timeout', 'status': 'timeout', 'diff': 'timeout', 'untracked': 'timeout'}
    assert diag['sections']['diff']['text'] is None
    assert diag['sections']['untracked']['paths'] is None
    assert diag['commands'][0]['error'].startswith(
        'DiagnosticSubprocessTimeout: the supervisor killed the command process group at its ')
    assert rec['timing']['diagnostic_seconds'] < 3.0
    assert rec['cost_accounting']['diagnostic_seconds'] == rec['timing']['diagnostic_seconds']
    assert rec['cleanup']['time_available_s'] > 90.0 and rec['cleanup']['reserve_intact'] is True
    assert json.loads((run_dir / 'exit_diagnostic.json').read_text())['status'] == 'timeout'
    assert json.loads((run_dir / 'terminal_phase.json').read_text())['cleanup']['deadline'] == 1_000_095.5


@pytest.mark.parametrize('mode', ['argv_for raises', 'spawn raises'])
def test_an_executor_that_raises_still_reaches_cleanup(mode):
    def argv_for(cmd):
        raise RuntimeError('container executor broke')

    def popen(*a, **k):
        raise OSError(24, 'Too many open files')
    cleanup = Cleanup()
    out = T.run_terminal_phase(endpoint=dict(exit_status='ContextWindowExceeded', submission=''),
                               inference_end=EPOCH, existing_cap=EPOCH + 1920.0, cleanup=cleanup,
                               argv_for=argv_for if mode == 'argv_for raises' else bash_argv, base_tree='0' * 40,
                               clock=constant(EPOCH + 1.0),
                               popen=popen if mode == 'spawn raises' else subprocess.Popen)
    rec, diag = out['record'], out['diagnostic']
    assert cleanup.calls == [1_000_120.0]
    assert rec['cleanup']['state'] == 'returned'
    assert rec['terminal_error'] is None
    assert rec['interrupted'] is None
    assert diag['status'] == 'failed'
    assert diag['changes_observed'] is None
    assert section_states(diag) == {'tree': 'failed', 'status': 'failed', 'diff': 'failed', 'untracked': 'failed'}
    assert [c['label'] for c in diag['commands']] == FOUR_LABELS
    expected = ('RuntimeError: container executor broke' if mode == 'argv_for raises'
                else 'OSError: [Errno 24] Too many open files')
    assert [c['error'] for c in diag['commands']] == [expected] * 4
    counts = rec['supervisor']['counts']
    assert counts['spawned'] == 0
    assert counts['argv_errors' if mode == 'argv_for raises' else 'spawn_errors'] == 4
    assert rec['plan']['diagnostic_budget_s'] == 25.0


def test_an_operator_abort_inside_the_diagnostic_is_re_raised_only_after_cleanup(tmp_path):
    run_dir = tmp_path / 'run'
    run_dir.mkdir()
    events = []

    def argv_for(cmd):
        events.append('diagnostic')
        raise KeyboardInterrupt

    def cleanup(deadline):
        events.append(('cleanup', deadline))
        return dict(confirmed=True)
    with pytest.raises(KeyboardInterrupt):
        T.run_terminal_phase(endpoint=dict(exit_status='LimitsExceeded', submission=''), inference_end=EPOCH,
                             existing_cap=EPOCH + 1920.0, cleanup=cleanup, argv_for=argv_for, base_tree='0' * 40,
                             out_dir=run_dir, clock=constant(EPOCH))
    assert events == ['diagnostic', ('cleanup', 1_000_120.0)]
    written = json.loads((run_dir / 'terminal_phase.json').read_text())
    assert written['interrupted'] == 'KeyboardInterrupt: '
    assert written['steps'] == ['endpoint', 'diagnostic', 'cleanup']
    assert written['supervisor']['state'] == 'interrupted'
    assert written['supervisor']['counts']['argv_errors'] == 1
    assert written['cleanup']['state'] == 'returned'
    assert written['cleanup']['deadline'] == 1_000_120.0


@pytest.mark.parametrize('inference_end,existing_cap,now,budget,deadline,available', [
    # Early finish: the episode deadline is EPOCH + 1500 (existing cap EPOCH + 1620) but inference ended at EPOCH.
    (EPOCH, 1_001_620.0, EPOCH + 2.0, 24.0, 1_000_120.0, 118.0),
    # Timeout path, phase entered late: 100 s remain to the cap, so 6 s of diagnostic, 4 s of hand-off margin and
    # 90 s of cleanup.
    (EPOCH, 1_000_120.0, EPOCH + 20.0, 6.0, 1_000_120.0, 100.0),
    # Inference ran 5 s past its deadline: the existing cap, not inference_end + 120, is the cleanup deadline.
    (EPOCH + 5.0, 1_000_120.0, EPOCH + 5.5, 20.5, 1_000_120.0, 114.5),
])
def test_the_diagnostic_gets_at_most_thirty_seconds_and_never_the_leftover_inference_time(
        tmp_path, inference_end, existing_cap, now, budget, deadline, available):
    r = make_repo(tmp_path)
    base = whole_worktree_tree(r)
    (r / 'mod.py').write_text('x = 2\n')
    run_dir = tmp_path / 'run'
    run_dir.mkdir()
    cleanup = Cleanup()
    out = T.run_terminal_phase(
        endpoint=lambda: T.submitted_only_endpoint('LimitsExceeded', base, frozen_ex(r), wd=str(r)),
        inference_end=inference_end, existing_cap=existing_cap, cleanup=cleanup, argv_for=bash_argv,
        base_tree=base, out_dir=run_dir, wd=str(r), clock=constant(now))
    rec, diag = out['record'], out['diagnostic']
    assert rec['plan']['diagnostic_budget_s'] == budget
    assert rec['plan']['absolute_cleanup_deadline'] == deadline
    assert rec['plan']['existing_absolute_cleanup_cap'] == existing_cap
    assert [e['timeout_s'] for e in rec['supervisor']['log']] == [budget] * 4
    assert [e['outcome'] for e in rec['supervisor']['log']] == ['exited'] * 4
    assert diag['total_budget_s'] == budget                            # never exit_capture's 300-s default
    assert diag['per_command_timeout_s'] == 60
    assert json.loads((run_dir / 'exit_diagnostic.json').read_text())['total_budget_s'] == budget
    assert cleanup.calls == [deadline]
    assert rec['cleanup']['time_available_s'] == available
    assert rec['cleanup']['deadline_within_existing_cap'] is True
    assert diag['status'] == 'changed'
    assert diag['changes_observed'] is True
    assert [c['label'] for c in diag['commands']] == FOUR_LABELS
    assert rec['timing']['diagnostic_overrun_s'] == 0.0


def test_when_the_cap_leaves_less_than_ninety_seconds_the_diagnostic_is_skipped_and_cleanup_keeps_the_rest(
        tmp_path):
    run_dir = tmp_path / 'run'
    run_dir.mkdir()
    requested, started = [], []

    def argv_for(cmd):
        requested.append(cmd)
        return bash_argv(cmd)

    def popen(*a, **k):
        started.append(a)
        raise AssertionError('must not be started')
    cleanup = Cleanup()
    out = T.run_terminal_phase(endpoint=dict(exit_status='EpisodeDeadline', submission=''), inference_end=EPOCH,
                               existing_cap=EPOCH + 120.0, cleanup=cleanup, argv_for=argv_for, base_tree='0' * 40,
                               out_dir=run_dir, clock=constant(EPOCH + 40.0), popen=popen)
    rec, diag = out['record'], out['diagnostic']
    assert requested == []
    assert started == []
    assert rec['plan']['state'] == 'no_time'
    assert rec['supervisor']['state'] == 'skipped'
    assert rec['supervisor']['reason'] == NO_TIME_REASON
    assert diag['status'] == 'timeout'
    assert diag['skipped'] is True
    assert diag['skip_reason'] == NO_TIME_REASON
    assert diag['changes_observed'] is None                            # unknown, never an empty workspace
    assert section_states(diag) == {'tree': 'timeout', 'status': 'timeout', 'diff': 'timeout', 'untracked': 'timeout'}
    for name in ALL_SECTIONS:
        assert diag['sections'][name]['text'] is None
        assert diag['sections'][name]['full_bytes'] is None
    assert diag['sections']['untracked']['n_paths'] is None
    assert diag['total_budget_s'] == 0.0
    assert diag['write']['state'] == 'written'
    written = json.loads((run_dir / 'exit_diagnostic.json').read_text())
    assert written['skip_reason'] == NO_TIME_REASON
    assert written['endpoint']['writes_submission_diff'] is False
    assert cleanup.calls == [1_000_120.0]
    assert rec['cleanup']['time_available_s'] == 80.0                  # all remaining time goes to cleanup


def test_the_submitted_only_artifact_bytes_are_identical_before_and_after_the_diagnostic(tmp_path):
    r = make_repo(tmp_path)
    base = whole_worktree_tree(r)
    (r / 'mod.py').write_text('x = 2\n')
    (r / 'new_file.py').write_text('n = 1\n')
    final = whole_worktree_tree(r, 'independent-final-index')
    run_dir = tmp_path / 'run'
    run_dir.mkdir()
    submission = run_dir / 'submission.diff'
    seen = []

    def argv_for(cmd):
        seen.append(submission.read_bytes())    # the endpoint is already on disk whenever the diagnostic dispatches
        return bash_argv(cmd)
    cleanup = Cleanup()
    out = T.run_terminal_phase(
        endpoint=lambda: T.submitted_only_endpoint('Submitted', base, frozen_ex(r), wd=str(r)),
        inference_end=EPOCH, existing_cap=EPOCH + 1620.0, cleanup=cleanup, argv_for=argv_for, base_tree=base,
        out_dir=run_dir, submission_path=submission, wd=str(r), clock=constant(EPOCH + 1.0))
    rec, diag, endpoint = out['record'], out['diagnostic'], out['endpoint']
    assert submission.read_bytes() == MOD_NEW_DIFF
    assert len(seen) == 5                                              # tree, status, diff, list, one file
    assert all(b == MOD_NEW_DIFF for b in seen)
    assert endpoint['exit_status'] == 'Submitted'
    assert endpoint['submission'] == MOD_NEW_DIFF.decode()
    assert endpoint['final_tree'] == final
    assert rec['endpoint']['submission_sha256'] == MOD_NEW_SHA
    assert rec['endpoint']['submission_utf8_bytes'] == 379
    assert rec['endpoint']['submission_chars'] == 379
    assert rec['endpoint']['submission_empty'] is False
    assert 'submission' not in rec['endpoint']
    assert rec['endpoint_write'] == dict(state='written', file='submission.diff')
    for key in ('endpoint_check_after_diagnostic', 'endpoint_check_after_cleanup'):
        assert rec[key] == dict(in_memory_sha256=MOD_NEW_SHA, file_sha256=MOD_NEW_SHA, file_present=True,
                                state='unchanged'), key
    # the diagnostic observed the same change separately, in its own file, never in submission.diff
    assert diag['exit_status'] == 'Submitted'
    assert diag['status'] == 'changed'
    assert diag['sections']['diff']['text'] == MOD_NEW_DIFF.decode()
    assert diag['sections']['diff']['mode'] == 'tree_to_tree'
    assert diag['sections']['tree']['sha'] == final
    assert [p['path'] for p in diag['sections']['untracked']['paths']] == ['new_file.py']
    assert diag['sections']['untracked']['paths'][0]['sha256'] == N_EQ_1_SHA
    assert diag['endpoint'] == dict(writes_submission_diff=False, marks_submitted=False, graded=False,
                                    changes_eligibility=False, changes_endpoint_bytes=False,
                                    output_file='exit_diagnostic.json')
    assert sorted(os.listdir(run_dir)) == ['exit_diagnostic.json', 'submission.diff', 'terminal_phase.json']
    assert cleanup.calls == [1_000_120.0]


@pytest.mark.parametrize('exit_status,expected', [
    ('Submitted', MOD_ONLY_DIFF),
    ('LimitsExceeded', b''),
    ('ContextWindowExceeded', b''),
    ('FormatError', b''),
    ('EpisodeDeadline', b''),
    ('ReceiptError', b''),
])
def test_every_terminal_path_runs_the_diagnostic_and_only_submitted_submits(tmp_path, exit_status, expected):
    r = make_repo(tmp_path)
    base = whole_worktree_tree(r)
    (r / 'mod.py').write_text('x = 2\n')
    run_dir = tmp_path / 'run'
    run_dir.mkdir()
    cleanup = Cleanup()
    out = T.run_terminal_phase(
        endpoint=lambda: T.submitted_only_endpoint(exit_status, base, frozen_ex(r), wd=str(r)),
        inference_end=EPOCH, existing_cap=EPOCH + 1620.0, cleanup=cleanup, argv_for=bash_argv, base_tree=base,
        out_dir=run_dir, submission_path=run_dir / 'submission.diff', wd=str(r), clock=constant(EPOCH))
    rec, diag = out['record'], out['diagnostic']
    assert (run_dir / 'submission.diff').read_bytes() == expected      # no salvage on a non-Submitted exit
    assert rec['endpoint']['exit_status'] == exit_status               # the diagnostic never relabels the exit
    assert rec['endpoint']['submission_sha256'] == (MOD_ONLY_SHA if expected else EMPTY_SHA)
    assert rec['endpoint_check_after_cleanup']['state'] == 'unchanged'
    assert diag['exit_status'] == exit_status
    assert [c['label'] for c in diag['commands']] == FOUR_LABELS
    assert diag['status'] == 'changed'
    assert diag['changes_observed'] is True
    assert diag['sections']['diff']['text'] == MOD_ONLY_DIFF.decode()  # observed, but only as a diagnostic
    assert cleanup.calls == [1_000_120.0]


@pytest.mark.parametrize('variant', ['capture raises', 'out_dir missing', 'diagnostic exists', 'write raises'])
def test_a_capture_error_never_escapes_the_wrapper_and_cleanup_still_runs(tmp_path, monkeypatch, variant):
    r = make_repo(tmp_path)
    base = whole_worktree_tree(r)
    run_dir = tmp_path / 'run'
    run_dir.mkdir()
    out_dir = run_dir
    if variant == 'capture raises':
        def broken(*a, **k):
            raise RuntimeError('capture bug')
        monkeypatch.setattr(XC, 'capture_exit_diagnostic', broken)
    elif variant == 'out_dir missing':
        out_dir = tmp_path / 'not-created'
    elif variant == 'diagnostic exists':
        (run_dir / 'exit_diagnostic.json').write_text('earlier record\n')
    else:
        def refuse(*a, **k):
            raise OSError(28, 'No space left on device')
        monkeypatch.setattr(XC, 'write_diagnostic', refuse)
    cleanup = Cleanup()
    out = T.run_terminal_phase(endpoint=dict(exit_status='LimitsExceeded', submission=''), inference_end=EPOCH,
                               existing_cap=EPOCH + 1620.0, cleanup=cleanup, argv_for=bash_argv, base_tree=base,
                               out_dir=out_dir, wd=str(r), clock=constant(EPOCH))
    rec, diag = out['record'], out['diagnostic']
    assert cleanup.calls == [1_000_120.0]
    assert rec['cleanup']['state'] == 'returned'
    assert rec['terminal_error'] is None
    assert rec['interrupted'] is None
    if variant == 'capture raises':
        assert rec['supervisor']['state'] == 'capture_error'
        assert rec['supervisor']['reason'] == 'the capture raised past its own containment: RuntimeError: capture bug'
        assert diag['status'] == 'failed'
        assert diag['skipped'] is False
        assert diag['changes_observed'] is None
        assert section_states(diag) == {'tree': 'failed', 'status': 'failed', 'diff': 'failed', 'untracked': 'failed'}
        assert json.loads((run_dir / 'exit_diagnostic.json').read_text())['status'] == 'failed'
    elif variant == 'out_dir missing':
        assert diag['write']['state'] == 'refused_missing_out_dir'
        assert rec['record_write']['state'] == 'refused_missing_out_dir'
        assert diag['status'] == 'no_change'
        assert not (tmp_path / 'not-created').exists()
    elif variant == 'diagnostic exists':
        assert diag['write']['state'] == 'refused_existing'
        assert (run_dir / 'exit_diagnostic.json').read_text() == 'earlier record\n'
    else:
        assert diag['write']['state'] == 'failed'
        assert diag['write']['reason'] == 'OSError: [Errno 28] No space left on device'
    assert not (run_dir / 'submission.diff').exists()                  # the diagnostic never writes the endpoint


def test_no_verified_container_makes_the_diagnostic_unavailable_not_empty(tmp_path):
    cleanup = Cleanup()
    out = T.run_terminal_phase(endpoint=dict(exit_status='LimitsExceeded', submission=''), inference_end=EPOCH,
                               existing_cap=EPOCH + 1620.0, cleanup=cleanup, argv_for=None, base_tree=None,
                               clock=constant(EPOCH))
    diag = out['diagnostic']
    assert diag['status'] == 'unavailable'
    assert diag['skip_reason'] == NO_EXECUTOR_REASON
    assert diag['changes_observed'] is None
    assert section_states(diag) == {'tree': 'unavailable', 'status': 'unavailable', 'diff': 'unavailable',
                                    'untracked': 'unavailable'}
    assert diag['write'] == dict(state='not_requested', file=None)
    assert cleanup.calls == [1_000_120.0]


def test_an_unanchorable_phase_skips_the_diagnostic_and_cleanup_keeps_the_existing_cap():
    cleanup = Cleanup()
    out = T.run_terminal_phase(endpoint=dict(exit_status='LimitsExceeded', submission=''), inference_end=None,
                               existing_cap=EPOCH + 1620.0, cleanup=cleanup, argv_for=bash_argv, base_tree=None,
                               clock=constant(EPOCH))
    assert out['diagnostic']['status'] == 'unavailable'
    assert out['diagnostic']['skip_reason'] == END_INVALID_REASON
    assert out['record']['supervisor']['counts'] is None
    assert cleanup.calls == [1_001_620.0]


def test_an_endpoint_that_raises_still_gets_the_diagnostic_and_cleanup_and_submits_nothing(tmp_path):
    r = make_repo(tmp_path)
    base = whole_worktree_tree(r)
    run_dir = tmp_path / 'run'
    run_dir.mkdir()

    def endpoint():
        raise RuntimeError('endpoint bug')
    cleanup = Cleanup()
    out = T.run_terminal_phase(endpoint=endpoint, inference_end=EPOCH, existing_cap=EPOCH + 1620.0, cleanup=cleanup,
                               argv_for=bash_argv, base_tree=base, out_dir=run_dir,
                               submission_path=run_dir / 'submission.diff', wd=str(r), clock=constant(EPOCH))
    rec = out['record']
    assert rec['endpoint']['state'] == 'error'
    assert rec['endpoint']['exit_status'] == 'RuntimeError'
    assert rec['endpoint']['error'] == 'RuntimeError: endpoint bug'
    assert rec['endpoint']['submission_sha256'] == EMPTY_SHA
    assert (run_dir / 'submission.diff').read_bytes() == b''
    assert out['diagnostic']['exit_status'] == 'RuntimeError'
    assert [c['label'] for c in out['diagnostic']['commands']] == FOUR_LABELS
    assert cleanup.calls == [1_000_120.0]


@pytest.mark.parametrize('endpoint', [dict(exit_status='Submitted', submission=b'bytes'),
                                      dict(exit_status=7, submission=''), dict(exit_status='Submitted'),
                                      'not a mapping'])
def test_a_malformed_endpoint_is_recorded_as_an_error_and_submits_nothing(endpoint):
    cleanup = Cleanup()
    out = T.run_terminal_phase(endpoint=endpoint, inference_end=EPOCH, existing_cap=EPOCH + 1620.0,
                               cleanup=cleanup, argv_for=None, base_tree=None, clock=constant(EPOCH))
    assert out['record']['endpoint']['state'] == 'error'
    assert out['record']['endpoint']['exit_status'] == 'TypeError'
    assert out['endpoint']['submission'] == ''
    assert cleanup.calls == [1_000_120.0]


def test_a_cleanup_that_raises_is_recorded_and_the_records_are_still_written(tmp_path):
    run_dir = tmp_path / 'run'
    run_dir.mkdir()

    def cleanup(deadline):
        raise RuntimeError('docker is gone')
    out = T.run_terminal_phase(endpoint=dict(exit_status='LimitsExceeded', submission=''), inference_end=EPOCH,
                               existing_cap=EPOCH + 1620.0, cleanup=cleanup, argv_for=None, base_tree=None,
                               out_dir=run_dir, clock=constant(EPOCH))
    assert out['record']['cleanup']['state'] == 'raised'
    assert out['record']['cleanup']['error'] == 'RuntimeError: docker is gone'
    assert out['record']['record_write'] == dict(state='written', file='terminal_phase.json')
    written = json.loads((run_dir / 'terminal_phase.json').read_text())
    assert written['cleanup']['state'] == 'raised'


def test_the_terminal_record_is_write_once(tmp_path):
    run_dir = tmp_path / 'run'
    run_dir.mkdir()
    (run_dir / 'terminal_phase.json').write_text('earlier\n')
    cleanup = Cleanup()
    out = T.run_terminal_phase(endpoint=dict(exit_status='LimitsExceeded', submission=''), inference_end=EPOCH,
                               existing_cap=EPOCH + 1620.0, cleanup=cleanup, argv_for=None, base_tree=None,
                               out_dir=run_dir, clock=constant(EPOCH))
    assert out['record']['record_write']['state'] == 'refused_existing'
    assert (run_dir / 'terminal_phase.json').read_text() == 'earlier\n'
    assert cleanup.calls == [1_000_120.0]


# ---------------------------------------------------------------- the frozen endpoint rule, composed

def test_a_non_submitted_exit_submits_nothing_and_runs_no_command():
    calls = []

    def ex(cmd):
        calls.append(cmd)
        return 0, ''
    out = T.submitted_only_endpoint('LimitsExceeded', '1' * 40, ex, base_capture_error=None)
    assert calls == []
    assert out['exit_status'] == 'LimitsExceeded'
    assert out['submission'] == ''
    assert out['final_tree'] is None


def test_submitted_without_a_starting_tree_is_a_capture_failure_that_keeps_the_base_error():
    calls = []
    out = T.submitted_only_endpoint('Submitted', None, lambda cmd: calls.append(cmd),
                                    base_capture_error='base: tree capture failed (rc=1)')
    assert calls == []
    assert out['exit_status'] == 'SubmissionCaptureFailed'
    assert out['submission'] == ''
    assert out['capture_error'] == 'base: tree capture failed (rc=1)'


def test_a_failed_final_capture_is_a_capture_failure_never_an_empty_submission():
    out = T.submitted_only_endpoint('Submitted', '1' * 40, lambda cmd: (128, 'fatal: not a git repository'))
    assert out['exit_status'] == 'SubmissionCaptureFailed'
    assert out['submission'] == ''
    assert out['capture_error'] == "final: tree capture failed (rc=128): 'fatal: not a git repository'"


def test_any_other_exception_names_the_exit_as_the_frozen_outer_handler_does():
    def ex(cmd):
        raise TimeoutError('absolute inference deadline reached; cleanup only')
    out = T.submitted_only_endpoint('Submitted', '1' * 40, ex)
    assert out['exit_status'] == 'TimeoutError'
    assert out['error'] == 'absolute inference deadline reached; cleanup only'
    assert out['submission'] == ''


def test_an_operator_abort_passes_through_the_endpoint_rule():
    def ex(cmd):
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        T.submitted_only_endpoint('Submitted', '1' * 40, ex)


def test_a_submitted_exit_submits_the_whole_tree_diff_from_the_recorded_start(tmp_path):
    r = make_repo(tmp_path)
    base = whole_worktree_tree(r)
    (r / 'mod.py').write_text('x = 2\n')
    (r / 'new_file.py').write_text('n = 1\n')
    (r / 'junk.pyc').write_text('ignored')
    out = T.submitted_only_endpoint('Submitted', base, frozen_ex(r), wd=str(r))
    assert out['exit_status'] == 'Submitted'
    assert out['submission'].encode() == MOD_NEW_DIFF
    assert out['final_tree'] == whole_worktree_tree(r, 'independent-final-index')
    assert out['capture_error'] is None


# ---------------------------------------------------------------- the live argv

def test_docker_exec_argv_mirrors_the_pinned_environment_execute():
    cid = 'ab' * 32
    argv_for = T.docker_exec_argv('/opt/docker', cid, cwd='/testbed', env={'PAGER': 'cat', 'TQDM_DISABLE': '1'})
    assert argv_for('git status') == ['/opt/docker', 'exec', '-w', '/testbed', '-e', 'PAGER=cat',
                                      '-e', 'TQDM_DISABLE=1', cid, 'bash', '-lc', 'git status']


@pytest.mark.parametrize('bad', [None, 12, 'abc', 'AB' * 32, 'ab' * 32 + '\n', 'ab' * 33])
def test_docker_exec_argv_refuses_anything_but_a_full_container_id(bad):
    with pytest.raises(ValueError):
        T.docker_exec_argv('/opt/docker', bad)


# ---------------------------------------------------------------- repairs after the adversarial review

def test_an_interrupt_after_the_leader_exited_still_kills_the_same_group_descendant(tmp_path):
    """The leader exits at once; its same-group grandchild keeps the pipe. An operator abort in the read loop must
    still SIGKILL the group, although the leader has already exited."""
    pidfile = tmp_path / 'grandchild.pid'

    def handler(_signum, _frame):
        raise KeyboardInterrupt('operator abort')
    previous = signal.signal(signal.SIGALRM, handler)
    ex = T.SupervisedExecutor(bash_argv, T.phase_plan(1000.0, 2920.0, 1000.0), clock=constant(1000.0))
    signal.setitimer(signal.ITIMER_REAL, 1.0)
    try:
        with pytest.raises(KeyboardInterrupt):
            ex('sleep 30 & echo $! > %s; exit 0' % pidfile)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
    entry = ex.log[0]
    assert (entry['outcome'], entry['killed'], entry['kill_signal'], entry['group_empty_confirmed']) == (
        'supervisor_error', True, 'SIGKILL', True)
    assert gone(read_pid(pidfile), within=2.0)


def test_a_descendant_that_leaves_the_group_and_keeps_the_pipe_is_recorded_as_escaped(tmp_path):
    pidfile = tmp_path / 'escaped.pid'
    script = 'import os, sys, time; os.setsid(); open(sys.argv[1], "w").write(str(os.getpid())); time.sleep(30)'
    command = "%s -c '%s' %s & wait" % (sys.executable, script, pidfile)
    plan = T.phase_plan(1000.0 - 24.0, 5000.0, 1000.0)                   # a 2-s diagnostic budget
    ex = T.SupervisedExecutor(bash_argv, plan, clock=shifted_real_clock(1000.0))
    try:
        with pytest.raises(T.DiagnosticSubprocessTimeout):
            ex(command)
        entry = ex.log[0]
        assert (entry['outcome'], entry['killed'], entry['group_empty_confirmed'],
                entry['escaped_descendant_suspected']) == ('timeout_killed', True, True, True)
        assert ex.counts['escaped_descendant_suspected'] == 1
    finally:
        if pidfile.exists() and pidfile.read_text().strip():
            try:
                os.kill(int(pidfile.read_text()), signal.SIGKILL)       # the fixture's own escapee
            except ProcessLookupError:
                pass


def test_a_killed_group_whose_pipe_closes_is_not_reported_as_escaped(tmp_path):
    pidfile = tmp_path / 'grandchild.pid'
    plan = T.phase_plan(1000.0 - 25.0, 5000.0, 1000.0)                   # a 1-s diagnostic budget
    ex = T.SupervisedExecutor(lambda cmd: hang_argv(pidfile), plan, clock=shifted_real_clock(1000.0))
    with pytest.raises(T.DiagnosticSubprocessTimeout):
        ex('ignored')
    entry = ex.log[0]
    assert (entry['group_empty_confirmed'], entry['escaped_descendant_suspected']) == (True, False)
    assert gone(read_pid(pidfile), within=2.0)


def test_time_spent_building_the_argv_is_charged_to_the_command_bound():
    plan = T.phase_plan(EPOCH - 24.0, EPOCH + 5000.0, EPOCH)            # diagnostic deadline EPOCH + 2.0
    clock = shifted_real_clock(EPOCH)

    def argv_for(cmd):
        time.sleep(1.5)
        return ['bash', '-c', 'trap "" TERM; sleep 30']
    ex = T.SupervisedExecutor(argv_for, plan, clock=clock)
    with pytest.raises(T.DiagnosticSubprocessTimeout):
        ex('x')
    ended = clock()
    entry = ex.log[0]
    assert entry['timeout_s'] < 0.6                                     # 2.0 - 1.5 s already spent on the argv
    assert ended - plan['diagnostic_deadline'] < 0.5                    # killed at the deadline, not 1.5 s after


def test_each_command_gets_only_the_remaining_diagnostic_time():
    plan = T.phase_plan(EPOCH - 23.0, EPOCH + 5000.0, EPOCH)            # a 3-s diagnostic budget
    ex = T.SupervisedExecutor(bash_argv, plan, clock=shifted_real_clock(EPOCH))
    assert ex('sleep 1.2; echo done') == (0, 'done\n')
    with pytest.raises(T.DiagnosticSubprocessTimeout):
        ex('trap "" TERM; sleep 30')
    first, second = ex.log
    assert (first['binding'], second['binding']) == ('remaining_diagnostic_time', 'remaining_diagnostic_time')
    assert first['timeout_s'] > 2.9 and second['timeout_s'] < 1.85     # 3.0 - the 1.2 s the first command used
    assert second['elapsed_s'] < 2.0                                    # killed at the remaining time, not at 3 s


def test_the_sixty_second_term_binds_when_a_plan_leaves_more_time():
    """phase_plan caps a diagnostic at 30 s, so through it the 60-s per-command term can never bind; it is still
    enforced for any runnable plan, checked here with a hand-built one."""
    plan = dict(state='runnable', diagnostic_deadline=1100.0, cleanup_reserve_start=1200.0)
    assert T.subprocess_timeout(plan, 1000.0) == dict(
        now=1000.0, remaining_diagnostic_s=100.0, to_cleanup_reserve_s=200.0, subprocess_max_s=60, timeout_s=60,
        binding='subprocess_max_60s', dispatch=True)


def test_a_pre_existing_endpoint_file_with_other_bytes_is_a_conflict_not_unchanged(tmp_path):
    sub = tmp_path / 'submission.diff'
    sub.write_bytes(b'STALE DIFF FROM SOMEWHERE ELSE\n')
    out = T.run_terminal_phase(endpoint=dict(exit_status='Submitted', submission='diff --git a/x b/x\n'),
                               inference_end=1000.0, existing_cap=2920.0, cleanup=Cleanup(), argv_for=None,
                               base_tree=None, out_dir=tmp_path, submission_path=sub, clock=constant(1000.0))
    rec = out['record']
    assert rec['endpoint_write']['state'] == 'refused_existing'
    for key in ('endpoint_check_after_diagnostic', 'endpoint_check_after_cleanup'):
        assert (rec[key]['state'], rec[key]['file_present'], rec[key]['file_sha256']) == (
            'file_conflict', True, 'd59192383130e3b82b65c66aa8e938b951c5cb254880444adf41e9276dbe5541'), key
    assert sub.read_bytes() == b'STALE DIFF FROM SOMEWHERE ELSE\n'      # never overwritten


def test_a_partial_endpoint_file_left_by_a_failed_write_is_a_conflict(tmp_path, monkeypatch):
    import workspace_capture as WC

    def partial(path, text):
        with open(path, 'x') as fh:
            fh.write(text[:7])
            fh.flush()
            raise OSError(28, 'No space left on device')
    monkeypatch.setattr(WC, 'write_once', partial)
    sub = tmp_path / 'submission.diff'
    out = T.run_terminal_phase(endpoint=dict(exit_status='Submitted', submission='diff --git a/x b/x\n+full\n'),
                               inference_end=1000.0, existing_cap=2920.0, cleanup=Cleanup(), argv_for=None,
                               base_tree=None, submission_path=sub, clock=constant(1000.0))
    rec = out['record']
    assert rec['endpoint_write']['state'] == 'failed'
    assert (rec['endpoint_check_after_cleanup']['state'], rec['endpoint_check_after_cleanup']['file_sha256']) == (
        'file_conflict', '3a36bc3044421d237f06463d903834b039da94ae12d7d1edfbfa72665db209b9')
    assert sub.read_bytes() == b'diff --'


def test_an_endpoint_evaluated_inside_the_phase_is_recorded_when_it_breaks_the_cleanup_reserve():
    now = [EPOCH]

    def slow_endpoint():
        now[0] += 40.0                          # e.g. two frozen wc2 commands under the 60-s command timeout
        return dict(exit_status='Submitted', submission='diff --git a/x b/x\n')
    cleanup = Cleanup()
    rec = T.run_terminal_phase(endpoint=slow_endpoint, inference_end=EPOCH, existing_cap=EPOCH + 1620.0,
                               cleanup=cleanup, argv_for=None, base_tree='0' * 40, clock=lambda: now[0])['record']
    assert rec['endpoint_mode'] == 'callable evaluated inside the phase: its time counts against the cleanup window'
    assert (rec['plan']['state'], rec['cleanup']['time_available_s'], rec['cleanup']['reserve_intact']) == (
        'no_time', 80.0, False)
    # the frozen order: the endpoint is determined before the phase and passed in
    rec = T.run_terminal_phase(endpoint=dict(exit_status='Submitted', submission='diff --git a/x b/x\n'),
                               inference_end=EPOCH, existing_cap=EPOCH + 1620.0, cleanup=Cleanup(), argv_for=None,
                               base_tree='0' * 40, clock=constant(EPOCH))['record']
    assert rec['endpoint_mode'] == "determined before the phase (the frozen driver's order)"
    assert (rec['cleanup']['time_available_s'], rec['cleanup']['reserve_intact']) == (120.0, True)
