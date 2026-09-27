"""DTR-REQ-026B deterministic fixtures for experiments/v2_agent/on_demand_residency.py (lead decision 3fd6f33). Every
case drives the controller through a fake host (clock, processes, listeners, signals, memory readings); no server,
model, VM, download or agent is started. Expected values are hand-derived literals from the fixture parameters."""
import sys
from dataclasses import asdict, replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments/v2_agent'))
import on_demand_residency as R  # noqa: E402

GiB, MiB = 1 << 30, 1 << 20
T0 = 1000.0


class FakeHost:
    """processes, listeners, signals and memory readings on a manual clock."""

    def __init__(self, load_time=5, free=64 * GiB, pressure='normal'):
        self.now, self.load_time, self.free, self.pressure = T0, load_time, free, pressure
        self.procs, self.listeners, self.signals, self.starts, self.readings, self.foreign = {}, {}, [], [], [], []
        self.behaviour, self.next_pid, self.log = {}, 5000, []
        self.pressure_after = None                    # (time, pressure): the reading turns adverse from that time

    def hooks(self):
        return dict(clock=lambda: self.now, sleep=self.sleep, listener_pid=lambda port: self.listeners.get(port),
                    foreign_jobs=lambda: list(self.foreign), memory_state=self.memory_state,
                    start_server=self.start_server, health=self.health, pid_alive=self.pid_alive,
                    pid_identity=lambda pid: self.procs[pid]['identity'] if pid in self.procs else None,
                    send_signal=self.send_signal)

    def sleep(self, s):
        self.now += s

    def memory_state(self):
        if self.readings:
            return self.readings.pop(0)
        if self.pressure_after and self.now >= self.pressure_after[0]:
            return dict(free_bytes=self.free, pressure=self.pressure_after[1])
        return dict(free_bytes=self.free, pressure=self.pressure)

    def start_server(self, spec, cache):
        b = self.behaviour.get(spec.name, {})
        self.log.append(('start', spec.name, [p for p, v in self.procs.items() if v['alive']]))
        if b.get('spawn_error'):
            raise OSError('spawn failed')
        pid, self.next_pid = self.next_pid, self.next_pid + 1
        ready = None if b.get('never_healthy') else self.now + b.get('load_time', self.load_time)
        self.procs[pid] = dict(alive=True, identity=('id', pid), port=spec.port, backend=spec.name, healthy_at=ready,
                               die_at=None if b.get('die_after') is None else self.now + b['die_after'],
                               ignore_term=b.get('ignore_term', False), ignore_kill=b.get('ignore_kill', False),
                               term_delay=b.get('term_delay', 0), reused_after_term=b.get('reused_after_term', False))
        self.listeners[spec.port] = pid
        self.starts.append((spec.name, cache))
        return pid

    def _reap(self, pid):
        p = self.procs.get(pid)
        if p and p['alive'] and p['die_at'] is not None and self.now >= p['die_at']:
            p['alive'] = False
            if self.listeners.get(p['port']) == pid:
                del self.listeners[p['port']]

    def pid_alive(self, pid):
        self._reap(pid)
        return bool(self.procs.get(pid, {}).get('alive'))

    def health(self, spec):
        pid = self.listeners.get(spec.port)
        if pid is None or not self.pid_alive(pid):
            return False
        at = self.procs[pid]['healthy_at']
        return at is not None and self.now >= at

    def send_signal(self, pid, sig):
        self.signals.append((pid, sig))
        p = self.procs[pid]
        if sig == R.SIGTERM and p.get('reused_after_term'):
            p['identity'] = ('id', 'reused-by-another-process')        # our server exited; its PID was reused
        if sig == R.SIGTERM and not p['ignore_term']:
            p['die_at'] = self.now + p['term_delay']
        if sig == R.SIGKILL and not p['ignore_kill']:
            p['die_at'] = self.now
        self._reap(pid)


LARGE = R.BackendSpec('large', 'klear-8b', 8293, 'a' * 64, weights_bytes=5 * GiB, kv_bytes=4608 * MiB,
                      compute_bytes=1 * GiB, cache_bytes=512 * MiB)
SMALL = R.BackendSpec('small', 'qwen3-4b', 8291, 'b' * 64, weights_bytes=3 * GiB, kv_bytes=4608 * MiB,
                      compute_bytes=1 * GiB, cache_bytes=512 * MiB)
CACHE = R.CacheConvention(prompt_cache_ram_mib=512, cache_prompt=True)


def config(**kw):
    base = dict(backends=(LARGE, SMALL), cache=CACHE, vm_bytes=16 * GiB, vm_headroom_bytes=4 * GiB,
                reserve_bytes=2 * GiB, host_limit_bytes=30 * GiB)
    base.update(kw)
    return R.ResidencyConfig(**base)


def controller(host, cfg=None, start=T0):
    return R.ResidencyController(cfg or config(), host.hooks(), start, 'ep1')


def action(k, backend, opportunity=False, draw='u=0.25'):
    return R.CallAction('ep1', k, 'history_aware', backend, draw, opportunity)


def ok_generate(spec, messages, remaining):
    return 'reply from %s' % spec.name


# ------------------------------------------------------------------------------------------------ configuration

@pytest.mark.parametrize('bad', [
    lambda: R.CacheConvention(512, True, context_tokens=65536),
    lambda: R.CacheConvention(512, True, kv_type='q8_0'),
    lambda: R.CacheConvention(512, True, slots=2),
    lambda: R.CacheConvention(-1, True),
    lambda: R.CacheConvention(True, True),
    lambda: R.CacheConvention(512, 1),
    lambda: config(backends=(LARGE, replace(SMALL, port=8293))),
    lambda: config(backends=(LARGE, replace(LARGE, port=9000))),
    lambda: config(backends=(replace(LARGE, cache_bytes=511 * MiB),)),
    lambda: config(version='candidate64k-v1'),
    lambda: config(episode_deadline_seconds=3600),
    lambda: config(max_generation_attempts=3),
    lambda: config(vm_bytes=-1),
    lambda: config(reserve_bytes=True),
    lambda: R.BackendSpec('x', 'y', 1, 'short'),
    lambda: R.BackendSpec('x', 'y', 1, 'g' * 64),
    lambda: R.BackendSpec('x', 'y', 1, 'A' * 64),
    lambda: config(health_timeout_seconds=float('inf')),
    lambda: config(poll_seconds=float('nan')),
    lambda: config(allowed_pressure=('normal', 'warn')),
    lambda: config(allowed_pressure=()),
    lambda: R.ResidencyController(config(), FakeHost().hooks(), float('inf'), 'ep1'),
    lambda: R.ResidencyController(config(), FakeHost().hooks(), T0, ''),
    lambda: R.ResidencyController(config(), dict(clock=lambda: 0), T0, 'ep1'),
    lambda: R.ResidencyController(config(), FakeHost().hooks(), None, 'ep1'),
], ids=['64k', 'q8 kv', 'two slots', 'unbounded cache', 'bool cache', 'int cache flag', 'duplicate port',
        'duplicate name', 'cache bound below convention', 'other version', 'longer deadline', 'three attempts',
        'negative vm', 'bool reserve', 'short digest', 'non-hex digest', 'uppercase digest', 'infinite timeout',
        'nan poll', 'weaker pressure', 'empty pressure', 'infinite episode start', 'empty episode id',
        'missing hooks', 'no episode start'])
def test_invalid_configuration_is_refused(bad):
    with pytest.raises(R.ConfigError):
        bad()


# ---------------------------------------------------------------------------------------------------- admission

def test_admission_arithmetic_and_exact_boundaries():
    # hand: large static = 16 + 5 + 4.5 + 1 + 0.5 + 2 = 29 GiB; dynamic need = 5 + 4.5 + 1 + 0.5 + 4 + 2 = 17 GiB
    reading = dict(free_bytes=17 * GiB, pressure='normal')
    a = R.admission_check(config(), 'large', reading)
    assert a['admitted'] and a['static_total'] == 29 * GiB and a['dynamic_need'] == 17 * GiB
    assert R.admission_check(config(host_limit_bytes=29 * GiB), 'large', reading)['admitted']
    assert not R.admission_check(config(host_limit_bytes=29 * GiB - 1), 'large', reading)['admitted']
    assert not R.admission_check(config(), 'large', dict(free_bytes=17 * GiB - 1, pressure='normal'))['admitted']
    assert not R.admission_check(config(), 'large', dict(free_bytes=64 * GiB, pressure='warn'))['admitted']


def test_missing_bounds_or_readings_refuse_admission_and_nothing_starts():
    a = R.admission_check(config(backends=(replace(LARGE, compute_bytes=None), SMALL)), 'large',
                          dict(free_bytes=64 * GiB, pressure='normal'))
    assert not a['admitted'] and 'missing bound: compute_bytes' in a['reasons']
    b = R.admission_check(config(vm_headroom_bytes=None), 'large', dict(free_bytes=64 * GiB, pressure='normal'))
    assert 'missing bound: vm_headroom_bytes' in b['reasons']
    assert not R.admission_check(config(), 'large', dict(pressure='normal'))['admitted']
    assert not R.admission_check(config(), 'large', None)['admitted']
    host = FakeHost()
    c = controller(host, config(backends=(replace(LARGE, compute_bytes=None), SMALL)))
    assert c.ensure('large')['status'] == 'refused_admission' and host.starts == [] and host.signals == []
    host2 = FakeHost()                                  # a missing reserve fails the pressure gate even earlier
    assert controller(host2, config(reserve_bytes=None)).ensure('large')['status'] == 'aborted_resource_pressure'
    assert host2.starts == []


# ---------------------------------------------------------------------------------------------------- lifecycle

def test_same_backend_is_reused_without_a_restart():
    host = FakeHost()
    c = controller(host)
    assert c.run_call(action(1, 'large'), [dict(role='user', content='task')], 'repo', ok_generate)['status'] == \
        'generated'
    out = c.run_call(action(2, 'large'), [dict(role='user', content='task')], 'repo', ok_generate)
    assert out['status'] == 'generated' and out['lifecycle']['status'] == 'reused'
    assert len(host.starts) == 1 and host.signals == []


def test_switch_confirms_release_before_the_next_load_with_exact_timings():
    host = FakeHost(load_time=7)
    host.behaviour['large'] = dict(term_delay=3, load_time=7)
    c = controller(host)
    assert c.ensure('large')['load_seconds'] == 7
    large_pid = c.owned['pid']
    out = c.ensure('small')
    assert out['status'] == 'loaded' and out['load_seconds'] == 7 and out['switch_seconds'] == 3 + 7
    assert host.signals == [(large_pid, R.SIGTERM)]
    assert host.log[-1] == ('start', 'small', [])                      # no live process when small started
    kinds = [e['event'] for e in c.events]
    assert kinds[kinds.index('sigterm_sent'):] == ['sigterm_sent', 'stop_confirmed', 'admission', 'load_started',
                                                   'loaded']
    stop = next(e for e in c.events if e['event'] == 'stop_confirmed')
    assert stop['seconds'] == 3 and stop['how'] == 'SIGTERM'


def test_sigterm_ignored_escalates_to_a_verified_sigkill():
    host = FakeHost()
    host.behaviour['large'] = dict(ignore_term=True)
    c = controller(host)
    c.ensure('large')
    pid = c.owned['pid']
    ev = c.stop()
    assert host.signals == [(pid, R.SIGTERM), (pid, R.SIGKILL)] and ev['how'] == 'SIGKILL' and ev['seconds'] == 60
    assert c.owned is None


def test_pid_reused_during_the_grace_period_gets_no_sigkill():
    host = FakeHost()
    host.behaviour['large'] = dict(ignore_term=True, reused_after_term=True)
    c = controller(host)
    c.ensure('large')
    pid = c.owned['pid']
    with pytest.raises(R.OwnershipError, match='no signal sent'):
        c.stop()
    assert host.signals == [(pid, R.SIGTERM)] and c.blocked                  # SIGKILL withheld after re-verification
    with pytest.raises(R.TerminationUnconfirmed):
        c.ensure('small')


def test_death_unconfirmed_retains_ownership_and_refuses_every_later_load():
    host = FakeHost()
    host.behaviour['large'] = dict(ignore_term=True, ignore_kill=True)
    c = controller(host)
    c.ensure('large')
    pid = c.owned['pid']
    with pytest.raises(R.TerminationUnconfirmed):
        c.ensure('small')
    assert c.owned['pid'] == pid and host.signals == [(pid, R.SIGTERM), (pid, R.SIGKILL)]
    assert [s[0] for s in host.starts] == ['large']
    with pytest.raises(R.TerminationUnconfirmed):
        c.ensure('small')
    with pytest.raises(R.TerminationUnconfirmed):
        c.run_call(action(1, 'small', True), [], 'repo', ok_generate)
    ev = [e for e in c.events if e['event'] == 'termination_unconfirmed']
    assert len(ev) == 1 and ev[0]['seconds'] == 60 + 30


def test_identity_or_listener_mismatch_refuses_every_signal():
    host = FakeHost()
    c = controller(host)
    c.ensure('large')
    pid = c.owned['pid']
    host.procs[pid]['identity'] = ('id', 'reused-by-another-process')
    with pytest.raises(R.OwnershipError, match='no signal sent'):
        c.stop()
    assert host.signals == [] and c.blocked
    with pytest.raises(R.TerminationUnconfirmed):
        c.ensure('small')
    host2 = FakeHost()
    c2 = controller(host2)
    c2.ensure('large')
    host2.listeners[8293] = 777                                         # a foreign listener took the port
    with pytest.raises(R.OwnershipError):
        c2.stop()
    assert host2.signals == []


def test_foreign_listener_or_job_refuses_loading_and_is_never_signalled():
    host = FakeHost()
    host.listeners[8293] = 777
    c = controller(host)
    assert c.ensure('large')['status'] == 'refused_foreign_listener' and host.starts == []
    host.listeners.clear()
    host.foreign = [dict(pid=888, comm='llama-server')]
    assert c.ensure('large')['status'] == 'refused_foreign_presence' and host.starts == []
    assert host.signals == []


def test_adverse_pressure_stops_only_the_owned_server():
    host = FakeHost()
    host.procs[888] = dict(alive=True, identity=('peer',), port=9999, backend='peer', healthy_at=0, die_at=None,
                           ignore_term=False, ignore_kill=False, term_delay=0)
    c = controller(host)
    c.ensure('large')
    pid = c.owned['pid']
    assert c.check_pressure()['status'] == 'ok'
    host.readings = [dict(free_bytes=64 * GiB, pressure='critical')]
    assert c.check_pressure()['status'] == 'aborted_resource_pressure'
    assert host.signals == [(pid, R.SIGTERM)] and host.procs[888]['alive'] and c.owned is None
    c.ensure('large')
    host.readings = [dict(free_bytes=2 * GiB - 1, pressure='normal')]           # below the 2 GiB reserve
    assert c.check_pressure()['status'] == 'aborted_resource_pressure'
    assert all(p != 888 for p, _ in host.signals)


def test_fresh_readings_before_load_refuse_on_pressure_or_insufficient_memory():
    host = FakeHost()
    host.readings = [dict(free_bytes=64 * GiB, pressure='warn')]
    assert controller(host).ensure('large')['status'] == 'aborted_resource_pressure' and host.starts == []
    host = FakeHost(free=17 * GiB - 1)                  # above the 2 GiB reserve, below the 17 GiB load need
    assert controller(host).ensure('large')['status'] == 'refused_admission' and host.starts == []


# ------------------------------------------------------------------------------------------ infrastructure/budgets

def test_infrastructure_failures_are_statuses_and_consume_no_generation_attempt():
    for behaviour, status in ((dict(spawn_error=True), 'infrastructure_load_failed'),
                              (dict(die_after=2), 'infrastructure_load_failed'),
                              (dict(never_healthy=True), 'infrastructure_health_timeout')):
        host = FakeHost()
        host.behaviour['large'] = behaviour
        c = controller(host)
        out = c.run_call(action(1, 'large'), [dict(role='user', content='t')], 'repo', ok_generate)
        assert out['status'] == status and out['generation_attempts'] == 0
        if status == 'infrastructure_health_timeout':
            assert out['lifecycle']['load_seconds'] == 600 and host.signals[0][1] == R.SIGTERM and c.owned is None
        host.behaviour['large'] = {}
        retry = c.run_call(action(1, 'large'), [dict(role='user', content='t')], 'repo', ok_generate)
        assert retry['status'] == 'generated' and retry['generation_attempts'] == 1


def test_generation_attempts_are_counted_separately_and_capped_at_two():
    state = dict(n=0)

    def flaky(spec, messages, remaining):
        state['n'] += 1
        if state['n'] == 1:
            raise R.GenerationError('malformed reply')
        return 'ok'
    host = FakeHost()
    c = controller(host)
    out = c.run_call(action(1, 'large'), [], 'repo', flaky)
    assert out['status'] == 'generated' and out['generation_attempts'] == 2 and out['generation_failures'] == \
        ['malformed reply']

    def broken(spec, messages, remaining):
        raise R.GenerationError('timeout')
    out = c.run_call(action(2, 'large'), [], 'repo', broken)
    assert out['status'] == 'generation_attempts_exhausted' and out['generation_attempts'] == 2


def test_the_original_episode_deadline_includes_switching_and_loading():
    host = FakeHost(load_time=5)
    seen = {}

    def record(spec, messages, remaining):
        seen['remaining'] = remaining
        return 'ok'
    c = controller(host, start=T0 - 1790)                   # 10 s of the 1,800 s budget left
    out = c.run_call(action(1, 'large'), [], 'repo', record)
    assert out['status'] == 'generated' and seen['remaining'] == 5          # the 5 s load came out of the budget
    host2 = FakeHost(load_time=30)
    c2 = controller(host2, start=T0 - 1790)
    out = c2.run_call(action(1, 'large'), [], 'repo', record)
    assert out['status'] == 'deadline_expired' and out['generation_attempts'] == 0
    assert host2.signals and host2.signals[0][1] == R.SIGTERM and c2.owned is None      # own load aborted
    host3 = FakeHost()
    c3 = controller(host3, start=T0 - 1800)                 # exactly at the deadline
    assert c3.ensure('large')['status'] == 'deadline_expired' and host3.starts == []
    host4 = FakeHost(load_time=10)
    c4 = controller(host4, start=T0 - 1790)                 # the load ends exactly at the deadline
    out = c4.run_call(action(1, 'large'), [], 'repo', record)
    assert out['status'] == 'deadline_expired' and out['generation_attempts'] == 0


# ---------------------------------------------------------------------------------------------- calls and history

def test_call_actions_are_immutable_across_retries_and_never_regenerated():
    host = FakeHost()
    c = controller(host)
    c.register(action(1, 'large'))
    with pytest.raises(R.CallIdentityError, match='changed across retries'):
        c.register(action(1, 'large', draw='u=0.75'))
    with pytest.raises(R.CallIdentityError, match='changed across retries'):
        c.register(action(1, 'small'))
    assert c.run_call(action(1, 'large'), [], 'repo', ok_generate)['status'] == 'generated'
    with pytest.raises(R.CallIdentityError, match='never regenerated'):
        c.run_call(action(1, 'large'), [], 'repo', ok_generate)
    with pytest.raises(R.CallIdentityError, match='outside a routing opportunity'):
        c.run_call(action(2, 'small', opportunity=False), [], 'repo', ok_generate)
    assert host.signals == []
    with pytest.raises(R.CallIdentityError):
        c.register(R.CallAction('other-episode', 3, 'history_aware', 'large', 'none', False))


def test_full_history_and_repository_handle_pass_through_a_switch_unchanged():
    host = FakeHost()
    c = controller(host)
    messages = [dict(role='system', content='rules'), dict(role='user', content='task')] + \
        [dict(role='assistant' if k % 2 else 'user', content='turn %d' % k) for k in range(6)]
    snapshot = [dict(m) for m in messages]
    repo = object()
    received = []

    def gen(spec, msgs, remaining):
        received.append((spec.name, msgs))
        return 'ok'
    assert c.run_call(action(1, 'large'), messages, repo, gen)['repo_handle'] is repo
    out = c.run_call(action(2, 'small', opportunity=True), messages, repo, gen)
    assert out['status'] == 'generated' and out['lifecycle']['status'] == 'loaded' and out['repo_handle'] is repo
    assert [n for n, _ in received] == ['large', 'small'] and all(m is messages for _, m in received)
    assert messages == snapshot and len(messages) == 8

    def mutating(spec, msgs, remaining):
        msgs.pop()
        return 'ok'
    with pytest.raises(R.CallIdentityError, match='message history'):
        c.run_call(action(3, 'small'), messages, repo, mutating)


def test_the_cache_convention_is_recorded_and_identical_for_every_backend():
    host = FakeHost()
    cfg = config()
    c = controller(host, cfg)
    c.ensure('large')
    c.ensure('small')
    assert [s[1] for s in host.starts] == [CACHE, CACHE]
    assert all(e['cache'] == asdict(CACHE) and e['config_digest'] == cfg.digest() for e in c.events)
    assert R.require_common_convention(cfg, config()) == CACHE
    with pytest.raises(R.ConfigError):
        R.require_common_convention(cfg, config(cache=R.CacheConvention(0, False)))


def test_module_is_a_pure_controller():
    src = (ROOT / 'experiments/v2_agent/on_demand_residency.py').read_text()
    for banned in ('subprocess', 'os.kill', 'Popen', 'import requests', 'socket', "__name__ == '__main__'",
                   'import random'):
        assert banned not in src


# ------------------------------------------------------------------------ regression fixtures for the review defects

def test_defect1_pressure_is_checked_before_reuse():
    host = FakeHost()
    calls = []

    def gen(spec, msgs, remaining):
        calls.append(spec.name)
        return 'ok'
    c = controller(host)
    assert c.run_call(action(1, 'small'), [], 'repo', gen)['status'] == 'generated'
    pid = c.owned['pid']
    host.pressure = 'critical'
    out = c.run_call(action(2, 'small'), [], 'repo', gen)
    assert out['status'] == 'aborted_resource_pressure' and out['generation_attempts'] == 0 and calls == ['small']
    assert host.signals == [(pid, R.SIGTERM)] and c.owned is None
    host.pressure = 'normal'                             # nothing was generated, so a later run is not a regeneration
    assert c.run_call(action(2, 'small'), [], 'repo', gen)['status'] == 'generated' and calls == ['small', 'small']


def test_defect1_pressure_is_checked_before_a_retry():
    host = FakeHost()
    calls = []

    def fail_then_pressure(spec, msgs, remaining):
        calls.append(1)
        host.pressure = 'critical'
        raise R.GenerationError('malformed')
    out = controller(host).run_call(action(1, 'large'), [], 'repo', fail_then_pressure)
    assert out['status'] == 'aborted_resource_pressure' and calls == [1] and out['generation_attempts'] == 1


def test_defect1_pressure_is_checked_during_loading():
    host = FakeHost(load_time=10)
    host.pressure_after = (T0 + 3, 'critical')
    c = controller(host)
    out = c.ensure('large')
    assert out['status'] == 'aborted_resource_pressure' and out['load_seconds'] == 3
    assert [s[1] for s in host.signals] == [R.SIGTERM] and c.owned is None


def test_defect1_pressure_at_acceptance_discards_the_reply_and_ends_the_call():
    host = FakeHost()

    def gen(spec, msgs, remaining):
        host.pressure = 'critical'
        return 'late reply'
    c = controller(host)
    out = c.run_call(action(1, 'large'), [], 'repo', gen)
    assert out['status'] == 'aborted_after_generation' and out['reply_discarded'] and 'reply' not in out
    assert c.owned is None and any(e['event'] == 'reply_discarded' for e in c.events)
    host.pressure = 'normal'
    with pytest.raises(R.CallIdentityError, match='never regenerated'):
        c.run_call(action(1, 'large'), [], 'repo', ok_generate)


def test_defect2_a_failed_attempt_that_mutates_history_is_refused_before_any_retry():
    host = FakeHost()
    calls = []

    def mutate_then_fail(spec, msgs, remaining):
        calls.append(1)
        msgs.append(dict(role='assistant', content='partial'))
        raise R.GenerationError('timeout')
    messages = [dict(role='user', content='task')]
    with pytest.raises(R.CallIdentityError, match='refused before any invocation'):
        controller(host).run_call(action(1, 'large'), messages, 'repo', mutate_then_fail)
    assert calls == [1]
    host2 = FakeHost()                                   # a changed history on a later retry of the same call
    host2.behaviour['large'] = dict(spawn_error=True)
    c2 = controller(host2)
    msgs2 = [dict(role='user', content='task')]
    assert c2.run_call(action(1, 'large'), msgs2, 'repo', ok_generate)['status'] == 'infrastructure_load_failed'
    host2.behaviour['large'] = {}
    msgs2.append(dict(role='user', content='injected'))
    with pytest.raises(R.CallIdentityError, match='refused before any invocation'):
        c2.run_call(action(1, 'large'), msgs2, 'repo', ok_generate)
    assert host2.starts == []


def test_defect3_the_routing_history_survives_an_unload():
    host = FakeHost()
    c = controller(host)
    assert c.run_call(action(1, 'small'), [], 'repo', ok_generate)['status'] == 'generated'
    c.stop()
    with pytest.raises(R.CallIdentityError, match='outside a routing opportunity'):
        c.run_call(action(2, 'large', opportunity=False), [], 'repo', ok_generate)
    assert [s[0] for s in host.starts] == ['small'] and [r['backend'] for r in c.routing] == ['small']
    assert c.run_call(action(2, 'large', opportunity=True), [], 'repo', ok_generate)['status'] == 'generated'
    assert [r['backend'] for r in c.routing] == ['small', 'large']


def test_defect4_a_reply_after_the_deadline_is_not_accepted():
    host = FakeHost()

    def slow(spec, msgs, remaining):
        host.now += remaining + 1                        # returns one second after the episode deadline
        return 'too late'
    c = controller(host, start=T0 - 1000)
    out = c.run_call(action(1, 'large'), [], 'repo', slow)
    assert out['status'] == 'deadline_expired' and out['reply_discarded'] and 'reply' not in out
    with pytest.raises(R.CallIdentityError, match='never regenerated'):
        c.run_call(action(1, 'large'), [], 'repo', ok_generate)
    host2 = FakeHost()                                   # exactly at the deadline is also too late

    def exact(spec, msgs, remaining):
        host2.now += remaining
        return 'on the boundary'
    assert controller(host2, start=T0 - 1000).run_call(action(1, 'large'), [], 'repo', exact)['status'] == \
        'deadline_expired'


def test_calls_are_sequential_and_the_previous_call_must_have_completed():
    host = FakeHost()
    c = controller(host)
    with pytest.raises(R.CallIdentityError, match='out of order'):
        c.register(action(2, 'large'))
    host.behaviour['large'] = dict(spawn_error=True)
    assert c.run_call(action(1, 'large'), [], 'repo', ok_generate)['status'] == 'infrastructure_load_failed'
    with pytest.raises(R.CallIdentityError, match='has not completed'):
        c.register(action(2, 'large'))


def test_hook_contract_violations_are_explicit_and_clean_up_the_owned_server():
    host = FakeHost()
    hooks = host.hooks()
    hooks['start_server'] = lambda spec, cache: None
    c = R.ResidencyController(config(), hooks, T0, 'ep1')
    with pytest.raises(R.HookContractError, match='positive PID'):
        c.ensure('large')
    assert c.blocked
    with pytest.raises(R.TerminationUnconfirmed):
        c.ensure('large')
    host = FakeHost()
    c = controller(host)
    c.ensure('large')
    pid = c.owned['pid']
    host.health = lambda spec: 'yes'
    c.h['health'] = host.health
    with pytest.raises(R.HookContractError, match='not a bool'):
        c.ensure('large')
    assert host.signals == [(pid, R.SIGTERM)] and c.owned is None and not c.blocked
    for name, bad in (('listener_pid', lambda port: 'x'), ('foreign_jobs', lambda: None),
                      ('pid_alive', lambda pid: 1), ('clock', lambda: float('nan'))):
        host = FakeHost()
        hooks = host.hooks()
        hooks[name] = bad
        with pytest.raises(R.HookContractError):
            R.ResidencyController(config(), hooks, T0, 'ep1').ensure('large')
    host = FakeHost()
    host.readings = ['not a reading']                    # an unusable reading is adverse, not an error
    assert controller(host).ensure('large')['status'] == 'aborted_resource_pressure'


def test_wait_loops_are_bounded_even_if_the_clock_stops():
    host = FakeHost()
    host.behaviour['large'] = dict(never_healthy=True)
    hooks = host.hooks()
    hooks['sleep'] = lambda s: None                      # a broken sleep: the clock never advances
    c = R.ResidencyController(config(), hooks, T0, 'ep1')
    out = c.ensure('large')
    assert out['status'] == 'infrastructure_health_timeout' and out['detail'] == 'iteration bound reached'
    host = FakeHost(load_time=0)                         # healthy at once, then ignores every signal
    host.behaviour['large'] = dict(ignore_term=True, ignore_kill=True, load_time=0)
    hooks = host.hooks()
    hooks['sleep'] = lambda s: None
    c = R.ResidencyController(config(), hooks, T0, 'ep1')
    assert c.ensure('large')['status'] == 'loaded'
    with pytest.raises(R.TerminationUnconfirmed):
        c.release()
    assert [s[1] for s in host.signals] == [R.SIGTERM, R.SIGKILL]


def test_release_is_confirmed_and_idempotent():
    host = FakeHost()
    c = controller(host)
    c.ensure('large')
    assert c.release()['event'] == 'stop_confirmed' and c.release() is None and c.owned is None


def test_pressure_arriving_as_the_load_becomes_healthy_is_caught_before_invocation():
    host = FakeHost(load_time=5)
    host.pressure_after = (T0 + 5, 'critical')           # adverse exactly when health first succeeds
    calls = []
    c = controller(host)
    out = c.run_call(action(1, 'large'), [], 'repo', lambda spec, m, r: calls.append(1) or 'ok')
    assert out['status'] == 'aborted_resource_pressure' and out['lifecycle']['status'] == 'loaded'
    assert calls == [] and out['generation_attempts'] == 0 and c.owned is None


def test_history_changed_while_the_backend_loads_is_refused_before_invocation():
    host = FakeHost()
    messages = [dict(role='user', content='task')]
    hooks = host.hooks()
    real_health = hooks['health']

    def health(spec):                                    # a concurrent writer changes the history during the load
        ok = real_health(spec)
        if ok:
            messages.append(dict(role='user', content='injected'))
        return ok
    hooks['health'] = health
    calls = []
    c = R.ResidencyController(config(), hooks, T0, 'ep1')
    with pytest.raises(R.CallIdentityError, match='refused before any invocation'):
        c.run_call(action(1, 'large'), messages, 'repo', lambda spec, m, r: calls.append(1) or 'ok')
    assert calls == [] and c.attempts.get(1, 0) == 0


# --------------------------------------------------------------------- second-review blockers (lead 02:1x UTC)

@pytest.mark.parametrize('failure', ['raises', 'none'])
def test_identity_failure_after_start_retains_ownership_blocks_and_never_signals(failure):
    host = FakeHost()
    hooks = host.hooks()
    real_identity = hooks['pid_identity']

    def identity(pid):
        if failure == 'raises':
            raise OSError('ps unavailable')
        return None
    hooks['pid_identity'] = identity
    c = R.ResidencyController(config(), hooks, T0, 'ep1')
    with pytest.raises(R.HookContractError, match='pid_identity failed'):
        c.ensure('large')
    pid = 5000                                           # the fake host's first PID (start_server succeeded)
    assert c.owned['pid'] == pid and c.owned['port'] == 8293 and c.owned['provisional'] is True
    assert c.blocked and 'ownership retained' in c.blocked and host.procs[pid]['alive']
    assert host.signals == []                            # never a blind signal
    hooks['pid_identity'] = real_identity                # even a recovered hook does not unblock
    for call in (lambda: c.ensure('large'), lambda: c.ensure('small'), c.release,
                 lambda: c.run_call(action(1, 'small'), [], 'repo', ok_generate)):
        with pytest.raises(R.TerminationUnconfirmed):
            call()
    assert host.signals == [] and len(host.starts) == 1


def test_mutate_then_return_ends_the_call_and_restoring_the_input_cannot_regenerate():
    host = FakeHost()
    calls = []

    def mutate_and_return(spec, msgs, remaining):
        calls.append(1)
        msgs.append(dict(role='assistant', content='reply'))
        return 'reply'
    c = controller(host)
    messages = [dict(role='user', content='task')]
    with pytest.raises(R.CallIdentityError, match='detected after the reply'):
        c.run_call(action(1, 'large'), messages, 'repo', mutate_and_return)
    assert c.status[1] == 'refused_history_changed' and c.replies[1]['reply'] == 'reply' and calls == [1]
    messages.pop()                                       # the caller restores the original input
    with pytest.raises(R.CallIdentityError, match='never regenerated'):
        c.run_call(action(1, 'large'), messages, 'repo', mutate_and_return)
    assert calls == [1]


def test_a_failed_attempt_that_mutates_history_ends_the_call_even_after_restoration():
    host = FakeHost()
    calls = []

    def mutate_then_fail(spec, msgs, remaining):
        calls.append(1)
        msgs.append(dict(role='assistant', content='partial'))
        raise R.GenerationError('timeout')
    c = controller(host)
    messages = [dict(role='user', content='task')]
    with pytest.raises(R.CallIdentityError, match='refused before any invocation'):
        c.run_call(action(1, 'large'), messages, 'repo', mutate_then_fail)
    messages.pop()
    with pytest.raises(R.CallIdentityError, match='never regenerated'):
        c.run_call(action(1, 'large'), messages, 'repo', ok_generate)
    assert calls == [1] and c.status[1] == 'refused_history_changed'


def test_a_clock_failure_after_the_reply_is_terminal():
    host = FakeHost()

    def break_clock(spec, msgs, remaining):
        host.now = float('nan')
        return 'reply'
    c = controller(host)
    with pytest.raises(R.HookContractError):
        c.run_call(action(1, 'large'), [], 'repo', break_clock)
    assert c.status[1] == 'reply_received' and c.replies[1]['reply'] == 'reply'
    host.now = T0 + 10
    with pytest.raises(R.CallIdentityError, match='never regenerated'):
        c.run_call(action(1, 'large'), [], 'repo', ok_generate)


def test_foreign_jobs_are_gated_on_reuse_and_before_invocation_without_signals():
    host = FakeHost()
    calls = []

    def gen(spec, msgs, remaining):
        calls.append(1)
        return 'ok'
    c = controller(host)
    assert c.run_call(action(1, 'large'), [], 'repo', gen)['status'] == 'generated'
    own = c.owned['pid']
    host.foreign = [dict(pid=888, comm='ollama')]
    out = c.run_call(action(2, 'large'), [], 'repo', gen)
    assert out['status'] == 'refused_foreign_presence' and out['generation_attempts'] == 0 and calls == [1]
    assert host.signals == [] and c.owned['pid'] == own          # neither the peer nor our server is signalled
    host.foreign = [dict(pid=own, comm='llama-server')]          # the owned PID is never counted as foreign
    assert c.run_call(action(2, 'large'), [], 'repo', gen)['status'] == 'generated' and calls == [1, 1]
    host2 = FakeHost()                                   # a foreign job appearing as the load becomes healthy
    hooks = host2.hooks()
    real_health = hooks['health']

    def health(spec):
        ok = real_health(spec)
        if ok:
            host2.foreign = [dict(pid=999, comm='mlx_lm')]
        return ok
    hooks['health'] = health
    calls2 = []
    c2 = R.ResidencyController(config(), hooks, T0, 'ep1')
    out = c2.run_call(action(1, 'large'), [], 'repo', lambda spec, m, r: calls2.append(1) or 'ok')
    assert out['status'] == 'refused_foreign_presence' and out['lifecycle']['status'] == 'loaded' and calls2 == []
    assert host2.signals == []


def test_ensure_alone_refuses_to_reuse_while_a_foreign_job_is_present():
    host = FakeHost()
    c = controller(host)
    assert c.ensure('large')['status'] == 'loaded'
    host.foreign = [dict(pid=888, comm='ollama')]
    assert c.ensure('large')['status'] == 'refused_foreign_presence' and host.signals == [] and c.owned
