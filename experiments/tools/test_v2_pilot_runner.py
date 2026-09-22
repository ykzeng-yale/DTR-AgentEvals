"""Deterministic fixtures for the fixed-backend pilot runner's declared queue/restart/block rules (no model, server or
container): frozen order with per-task backend order, terminal episodes skipped by hash, interrupted run directories
retained for explicit reconciliation, conflicting records refused before ANY execution, the time-based block cap
(never outcome-based) with unstarted IDs preserved, serial serving only on backend change, and the pause file."""
import json, sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_agent'))
import pilot_runner as PR  # noqa: E402
import pilot_episode as PE  # noqa: E402

FRAME = dict(pilot=dict(tasks=[
    dict(position=2, instance_id='b__2', backend_order=['large', 'small'], instance_image='sha256:b'),
    dict(position=1, instance_id='a__1', backend_order=['small', 'large'], instance_image='sha256:a'),
    dict(position=3, instance_id='c__3', backend_order=['large', 'small'], instance_image='sha256:c')]))


def terminal(out, iid, be, run_id, **kw):
    d = out / run_id
    d.mkdir(parents=True)
    (d / 'episode.json').write_text(json.dumps(dict(dict(instance_id=iid, backend=be, run_id=run_id, exit_status='Submitted',
                                                         physical_requests=10), **kw)))
    return d


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def fakes(clock, per_episode=600.0):
    served, ran = [], []

    def serve(be):
        served.append(be)

    def run(it):
        ran.append((it['instance_id'], it['backend']))
        clock.t += per_episode
        return dict(run_id='%s__%s__x' % (it['instance_id'], it['backend']), exit_status='LimitsExceeded', wall_seconds=per_episode,
                    physical_requests=24)
    return serve, run, served, ran


def test_queue_is_frozen_position_order_with_each_tasks_backend_order():
    q = PR.episode_queue(FRAME)
    assert [(x['instance_id'], x['backend'], x['order']) for x in q] == [
        ('a__1', 'small', 1), ('a__1', 'large', 2), ('b__2', 'large', 1), ('b__2', 'small', 2), ('c__3', 'large', 1), ('c__3', 'small', 2)]
    assert q[0]['image'] == 'sha256:a'


def test_completed_skipped_and_serving_switches_only_on_change(tmp_path):
    out = tmp_path / 'out'
    terminal(out, 'a__1', 'small', 'a__1__small__pilot-cp2-wc2__T0-aaaaaa')
    clock = Clock()
    serve, run, served, ran = fakes(clock)
    st = PR.run_block(PR.episode_queue(FRAME), out, serve, run, {}, clock=clock, block_start=clock())
    assert [s['instance_id'] + '/' + s['backend'] for s in st['skipped_completed']] == ['a__1/small']
    assert st['retained_incomplete'] == []
    assert ran == [('a__1', 'large'), ('b__2', 'large'), ('b__2', 'small'), ('c__3', 'large'), ('c__3', 'small')]
    assert served == ['large', 'small', 'large', 'small']                        # one switch per backend change
    assert st['physical_requests_total'] == 10 + 5 * 24 and st['stopped'] is None


def test_conflicting_or_duplicate_records_refuse_before_any_execution(tmp_path):
    for bad in (dict(instance_id='zzz'), dict(backend='large'), dict(exit_status=None)):
        out = tmp_path / ('o%d' % len(list(tmp_path.iterdir())))
        terminal(out, 'c__3', 'small', 'c__3__small__pilot-cp2-wc2__T0-cccccc', **bad)
        clock = Clock()
        serve, run, served, ran = fakes(clock)
        with pytest.raises(PR.Conflict):
            PR.run_block(PR.episode_queue(FRAME), out, serve, run, {}, clock=clock)
        assert ran == [] and served == []
    out = tmp_path / 'dup'
    terminal(out, 'a__1', 'small', 'a__1__small__pilot-cp2-wc2__T0-000001')
    terminal(out, 'a__1', 'small', 'a__1__small__pilot-cp2-wc2__T0-000002')
    with pytest.raises(PR.Conflict):
        PR.run_block(PR.episode_queue(FRAME), out, *fakes(Clock())[:2], {}, clock=Clock())


def test_block_cap_is_time_based_and_preserves_unstarted_ids(tmp_path):
    clock = Clock(0.0)
    serve, run, served, ran = fakes(clock, per_episode=1500.0)
    st = PR.run_block(PR.episode_queue(FRAME), tmp_path / 'out', serve, run, {}, clock=clock, block_start=0.0)
    # start needs now + 1800 + 300 (+300 on a switch) <= 7200: t=0 ok, 1500 ok (switch: 3900), 3000 ok (switch: 5400),
    # 4500: 4500+2400=6900 ok, 6000: stop
    assert ran == [('a__1', 'small'), ('a__1', 'large'), ('b__2', 'large'), ('b__2', 'small')]
    assert st['stopped'].startswith('block time cap')
    assert [(u['instance_id'], u['backend']) for u in st['unstarted']] == [('c__3', 'large'), ('c__3', 'small')]
    assert PR.plan_start(0, 0, False) and not PR.plan_start(5101, 0, False) and not PR.plan_start(4801, 0, True)


def test_pause_file_stops_before_the_next_start(tmp_path):
    clock = Clock()
    pause = tmp_path / 'PAUSE'
    serve, run0, served, ran = fakes(clock)

    def run(it):
        r = run0(it)
        pause.write_text('coordination')
        return r
    st = PR.run_block(PR.episode_queue(FRAME), tmp_path / 'out', serve, run, {}, clock=clock, pause=pause)
    assert len(ran) == 1 and st['stopped'].startswith('paused') and len(st['unstarted']) == 5


def test_late_setup_rechecks_full_episode_and_cleanup_allowance(tmp_path):
    clock = Clock(4800)
    _, run, _, ran = fakes(clock, per_episode=2100)
    def late_serve(_backend):
        clock.t += 601                   # legal load timeout plus overhead exceeds old 300s estimate
    st = PR.run_block(PR.episode_queue(FRAME), tmp_path, late_serve, run, {}, clock=clock, block_start=0)
    assert ran == [] and st['stopped'].startswith('block time cap after setup')
    assert len(st['unstarted']) == 6 and clock() < PR.BLOCK_CAP


def test_interrupted_attempt_ledger_requires_reconciliation_before_any_dispatch(tmp_path):
    d = tmp_path / 'c__3__small__pilot-cp2-wc2__T0-interrupted'
    d.mkdir()
    ledger = d / 'attempts.jsonl'
    ledger.write_text(''.join(json.dumps(dict(event='start', call=i // 2 + 1, attempt=i % 2 + 1)) + '\n' for i in range(48)))
    original = ledger.read_bytes()
    clock = Clock()
    serve, run, served, ran = fakes(clock)
    with pytest.raises(PR.Conflict, match='explicit ledger reconciliation'):
        PR.run_block(PR.episode_queue(FRAME), tmp_path, serve, run, {}, clock=clock)
    assert ran == served == [] and ledger.read_bytes() == original


def test_whole_cohort_unknown_counts_reserve_48_and_invalid_counts_refuse(tmp_path):
    # Put the unknown terminal after the new item: it must still debit admission before any dispatch.
    terminal(tmp_path, 'c__3', 'small', 'c__3__small__pilot-cp2-wc2__old', physical_requests=None)
    clock = Clock()
    serve, run, served, ran = fakes(clock)
    st = PR.run_block(PR.episode_queue(FRAME), tmp_path, serve, run, {}, clock=clock, physical_so_far=720)
    assert st['physical_requests_total'] == 768 and st['stopped'].startswith('all-episode physical request ceiling')
    assert ran == served == []
    for bad in (-1, 49, 1.5, True, '48'):
        with pytest.raises(PR.Conflict):
            PR.request_count({'physical_requests': bad})
    assert PR.request_count({'physical_requests': None}) == 48


def test_missing_or_wrong_resume_image_and_model_identity_refuse_before_dispatch(tmp_path):
    expected = dict(small='smallsha', large='largesha')
    for n, fields in enumerate(({}, dict(pins=dict(image_id='wrong'), served=dict(model_sha256='smallsha')),
                               dict(pins=dict(image_id='sha256:a'), served=dict(model_sha256='wrong')))):
        out = tmp_path / str(n)
        terminal(out, 'a__1', 'small', 'a__1__small__pilot-cp2-wc2__old', **fields)
        serve, run, served, ran = fakes(Clock())
        with pytest.raises(PR.Conflict, match='identity'):
            PR.run_block(PR.episode_queue(FRAME), out, serve, run, {}, expected_models=expected)
        assert ran == served == []


def test_episode_request_timeout_and_durable_start_result_ledger(tmp_path):
    assert PE.request_timeout(1800, now=1750) == 50
    assert PE.request_timeout(1800, now=0) == 900
    with pytest.raises(PE.EpisodeDeadline):
        PE.request_timeout(1800, now=1800)
    path = tmp_path / 'attempts.jsonl'
    start = dict(event='start', call=9, attempt=1, t_start=10)
    PE.append_attempt(path, start)
    assert [json.loads(s) for s in path.read_text().splitlines()] == [start]  # visible even without a result
    result = dict(event='result', call=9, attempt=1, t_start=10, t_end=11, ok=False)
    PE.append_attempt(path, result)
    assert [json.loads(s) for s in path.read_text().splitlines()] == [start, result]


def test_already_exited_owned_server_never_signals_pid(tmp_path, monkeypatch):
    from types import SimpleNamespace
    servers = PR.Servers({}, {'hard_deadline_epoch': 7200}, tmp_path)
    servers.live = dict(pid=123, port=8291, proc=SimpleNamespace(poll=lambda: 0))
    monkeypatch.setattr(servers, '_record', lambda: None)
    monkeypatch.setattr(PR.os, 'kill', lambda *args: pytest.fail('signalled exited PID'))
    monkeypatch.setattr(PR, 'listener_pid', lambda *args: pytest.fail('queried a released port'))
    servers.stop()
    assert servers.live is None


def test_unconfirmed_server_termination_retains_ownership(tmp_path, monkeypatch):
    class Stuck:
        def poll(self):
            return None
        def wait(self, timeout):
            raise PR.subprocess.TimeoutExpired('mock', timeout)
    servers = PR.Servers({}, {'hard_deadline_epoch': 7200}, tmp_path)
    owned = dict(pid=123, port=8291, backend='small', proc=Stuck())
    servers.live = owned
    signals = []
    monkeypatch.setattr(PR.time, 'time', lambda: 7100)
    monkeypatch.setattr(servers, '_record', lambda: None)
    monkeypatch.setattr(PR, 'listener_pid', lambda _: 123)
    monkeypatch.setattr(PR.os, 'kill', lambda pid, sig: signals.append((pid, sig)))
    with pytest.raises(PR.Conflict, match='unconfirmed'):
        servers.stop()
    assert servers.live is owned and servers.events[-1]['event'] == 'termination_unconfirmed'
    assert signals == [(123, PR.signal.SIGTERM), (123, PR.signal.SIGKILL)]


def test_frozen_harness_settings_and_bindings_are_required_on_resume(tmp_path):
    expected = dict(small='smallsha', large='largesha')
    good = dict(pins=dict(image_id='sha256:a', mini_swe_agent=PR.HARNESS_PIN, default_yaml_sha256=PR.DEFAULT_YAML_PIN),
                served=dict(model_sha256='smallsha'), settings=dict(PR.FROZEN_SETTINGS),
                workspace_binding='wc2', template_platform_binding='cp2')
    changes = [('pins', 'mini_swe_agent', 'wrong'), ('pins', 'default_yaml_sha256', 'wrong'),
               ('settings', 'step_limit', 999), (None, 'workspace_binding', 'wc1'), (None, 'template_platform_binding', 'cp1')]
    for n, (section, key, value) in enumerate(changes):
        fields = json.loads(json.dumps(good))
        (fields[section] if section else fields)[key] = value
        out = tmp_path / str(n)
        terminal(out, 'a__1', 'small', 'a__1__small__pilot-cp2-wc2__old', **fields)
        serve, run, served, ran = fakes(Clock())
        with pytest.raises(PR.Conflict, match='harness/settings/binding'):
            PR.run_block(PR.episode_queue(FRAME), out, serve, run, {}, expected_models=expected)
        assert served == ran == []
    out = tmp_path / 'valid'
    terminal(out, 'a__1', 'small', 'a__1__small__pilot-cp2-wc2__old', **good)
    assert PR.episode_state(out, PR.episode_queue(FRAME)[0], expected)[0] == 'completed'


@pytest.mark.parametrize(('cleanup_exits', 'container_confirmed', 'write_failure'),
                         [(True, True, False), (False, True, False), (True, False, False), (True, True, True)])
def test_child_gets_cleanup_grace_inside_existing_reserve(tmp_path, monkeypatch, cleanup_exits, container_confirmed, write_failure):
    from types import SimpleNamespace
    clock, waits, killed = Clock(0), [], []
    run_dir = tmp_path / 'a__1__small__pilot-cp2-wc2__fixture'
    run_dir.mkdir()
    cid = 'c' * 64
    (run_dir / 'container_ownership.json').write_text(json.dumps(dict(run_id=run_dir.name, container_id=cid)))
    (run_dir / 'container_cleanup.json').write_text(json.dumps(dict(container_id=cid, confirmed=container_confirmed, state='absent' if container_confirmed else 'unknown')))
    def unavailable_cleanup(owned_id, deadline):
        assert owned_id == cid and deadline <= 2100 - PR.SERVER_CLEANUP_RESERVE
        return dict(container_id=cid, confirmed=False, state='unknown')
    monkeypatch.setattr(PE, 'cleanup_owned_container', unavailable_cleanup)
    class Child:
        pid, returncode = 99, None
        def poll(self):
            return self.returncode
        def wait(self, timeout):
            waits.append(timeout)
            if len(waits) == 2 and cleanup_exits:
                clock.t += 20
                self.returncode = 0
                return 0
            clock.t += timeout
            raise PR.subprocess.TimeoutExpired('mock child', timeout)
    child = Child()
    servers = SimpleNamespace(work_deadline=1800, hard_deadline=2100, events=[], unconfirmed_episode_pids=[],
                              unconfirmed_container_runs=[],
                              live=dict(model_file='fixture.gguf', model_sha256='smallsha', pid=123, started_utc='fixture'))
    monkeypatch.setattr(PR.time, 'time', clock)
    monkeypatch.setattr(PR.WC, 'new_run_dir', lambda *args: (run_dir.name, run_dir))
    monkeypatch.setattr(PR.subprocess, 'Popen', lambda *args, **kw: child)
    monkeypatch.setattr(PR.os, 'killpg', lambda pid, sig: killed.append((pid, sig)))
    if write_failure:
        write_once = PR.WC.write_once
        def fail_cleanup_write(path, text):
            if Path(path).name == 'runner_cleanup.json':
                raise OSError('mock cleanup receipt failure')
            return write_once(path, text)
        monkeypatch.setattr(PR.WC, 'write_once', fail_cleanup_write)
    runner = PR.make_episode_runner(tmp_path, servers)
    if write_failure:
        with pytest.raises(OSError, match='mock cleanup receipt failure'):
            runner(PR.episode_queue(FRAME)[0])
        assert servers.unconfirmed_episode_pids == []       # exit was observed
        assert servers.unconfirmed_container_runs == [run_dir.name]  # cleanup not yet inspected: cannot claim release
        assert not (run_dir / 'runner_cleanup.json').exists()
    elif cleanup_exits and container_confirmed:
        record = runner(PR.episode_queue(FRAME)[0])
        assert record['exit_status'] == 'EpisodeWallLimit' and killed == []
        assert record['pins']['mini_swe_agent'] == PR.HARNESS_PIN and record['settings'] == PR.FROZEN_SETTINGS
    elif not cleanup_exits:
        with pytest.raises(PR.Conflict, match='PID 99 termination unconfirmed'):
            runner(PR.episode_queue(FRAME)[0])
        assert servers.unconfirmed_episode_pids == [99] and killed == [(99, PR.signal.SIGKILL)]
    else:
        with pytest.raises(PR.Conflict, match='container cleanup unconfirmed'):
            runner(PR.episode_queue(FRAME)[0])
        assert servers.unconfirmed_container_runs == [run_dir.name] and killed == []
    assert waits[:2] == [1800, 120] and clock() + PR.SERVER_CLEANUP_RESERVE <= 2100
    if not write_failure:
        assert json.loads((run_dir / 'runner_cleanup.json').read_text())['termination_confirmed'] is cleanup_exits


def test_owned_container_cleanup_is_synchronous_verified_and_bounded(monkeypatch):
    from types import SimpleNamespace
    cid, calls = 'c' * 64, []
    monkeypatch.setattr(PE.time, 'time', lambda: 10)
    def stopped(cmd, **kw):
        calls.append((cmd, kw['timeout']))
        return SimpleNamespace(returncode=0, stdout='false\n' if 'inspect' in cmd else cid, stderr='')
    rec = PE.cleanup_owned_container(cid, 40, run=stopped)
    assert rec['confirmed'] and rec['state'] == 'stopped'
    assert len(calls) == 2 and all(cmd[-1] == cid and timeout <= 30 for cmd, timeout in calls)
    calls.clear()
    def unavailable(cmd, **kw):
        calls.append(cmd)
        return SimpleNamespace(returncode=1, stdout='', stderr='daemon unavailable')
    assert PE.cleanup_owned_container(cid, 40, run=unavailable)['confirmed'] is False
    assert len(calls) == 4 and all(cmd[-1] == cid for cmd in calls)
    calls.clear()
    assert PE.cleanup_owned_container(None, 40, run=unavailable)['confirmed'] is False and calls == []
    assert PE.cleanup_owned_container(cid, 10, run=unavailable)['confirmed'] is False and calls == []


def test_host_receipt_does_not_claim_release_with_unknown_child_or_container(tmp_path, monkeypatch):
    path = tmp_path / 'host.json'
    monkeypatch.setattr(PR, 'SERVERS', path)
    servers = PR.Servers({}, dict(hard_deadline_epoch=7200, block_start_utc='start', block_hard_end_utc='end'), tmp_path)
    for pids, containers in (([99], []), ([], ['run1'])):
        servers.unconfirmed_episode_pids, servers.unconfirmed_container_runs = pids, containers
        servers._record()
        rec = json.loads(path.read_text())
        assert rec['servers'] == [] and rec['release_confirmed'] is False
        assert rec['unconfirmed_episode_pids'] == pids and rec['unconfirmed_container_runs'] == containers
    servers.unconfirmed_episode_pids, servers.unconfirmed_container_runs = [], []
    servers._record()
    assert json.loads(path.read_text())['release_confirmed'] is True
