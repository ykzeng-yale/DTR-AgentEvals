"""DTR-REQ-011 competence-pair fixtures (lead a0e8379, docs/theory_feedback_20260924_req010_decision.md): source/config
binding (manifest values, and fail-closed source digests at admission, in the entry and in the grader), the exact
two-arm queue, all-exit capture including failure and timeout, receipt accounting (also chained through the real entry),
immutable resume, deadline cleanup, the grading retry rule, process containment with real processes (the evaluator
inside the grader's group at its wall budget and at the pair cap; the server watchdog after the parent is SIGKILLed),
schedule gates, sanitization and the always-written summary.

No model, llama-server, container, evaluator or network: fakes and stubs only. The all-exit fixtures run the entry,
unmodified, in the pinned mini-swe-agent venv through experiments/tools/req011_integration_harness.py (a stub sender,
a fake `docker` running commands in a disposable Git repository), and the frozen yaml-v1 driver on the same scripts
through the unedited experiments/tools/v2_cue_integration_harness.py (mode 'frozen') for byte parity; they skip when
that venv or the dataset is absent. Expected values are literals from the lead decision, pilot_runner and the REQ-010
records, not computed by the code under test.
"""
import getpass
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from collections import OrderedDict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments/v2_agent'))
import req011_pair as P  # noqa: E402
import req011_grade as G  # noqa: E402

S = P.S
MANIFEST_PATH = ROOT / 'configs/v2_req011_competence_pair_20260924.json'
MANIFEST = json.loads(MANIFEST_PATH.read_text())
CONV = json.loads((ROOT / 'results/v2_agent/coder_conversion_20260922.json').read_text())
REQ010 = json.loads((ROOT / 'results/v2_adapter/req010_sentinel_20260924/sentinel_summary.json').read_text())
IID = 'astropy__astropy-14598'
PIN = 'sha256:ff1716c2ea207eeb3b717cd5deb3213f923f4d445234edd9a53d035dce834997'
LARGE_SHA = 'b179f09d5f73776e68623384d95a0dbd73ccf038e34db50b508e9c3baf468066'
SMALL_SHA = '87a3665ca3247c54dfa198010f6e1f48d41611029bbcb5ed185a5ad05fcd3b81'
LARGE_ALIAS, SMALL_ALIAS = 'qwen2.5-coder-14b-instruct-aedcc2d-q4_k_m', 'qwen2.5-coder-7b-instruct-c03e6d3-q4_k_m'
CID = 'c' * 64


def assignments():
    return json.loads(json.dumps(MANIFEST['assignments']))


# ---------------------------------------------------------------- source/config binding

def test_manifest_carries_the_lead_values_exactly():
    assert (MANIFEST['request'], MANIFEST['lead_commit'], MANIFEST['source_commit'], MANIFEST['instance_id']) == (
        'DTR-REQ-011', 'a0e8379', '10be146', IID)
    assert [(a['order'], a['backend'], a['arm'], a['port'], a['alias'], a['gguf_sha256'], a['model'])
            for a in MANIFEST['assignments']] == [
        (1, 'large', 'baseline', 8293, LARGE_ALIAS, LARGE_SHA, 'Qwen/Qwen2.5-Coder-14B-Instruct'),
        (2, 'small', 'baseline', 8291, SMALL_ALIAS, SMALL_SHA, 'Qwen/Qwen2.5-Coder-7B-Instruct')]
    assert {k: v['id'] for k, v in MANIFEST['images'].items()} == dict(
        instance=PIN, env='sha256:ee4f7d3a3ec176acd95cadc6aaa7712e047f347091f3536784933dfffe9d9cfa',
        base='sha256:f7d1dba08fbc14f5232016debb02d9ace25c84e2a088ec8ec6c776fc3c2f07d5')
    s, c = MANIFEST['settings'], MANIFEST['caps']
    assert (s['step_limit'], s['temperature'], s['max_tokens'], s['context_per_slot'], s['command_timeout_s'],
            s['physical_attempts_per_call_max'], s['wall_time_limit_seconds']) == (24, 0.0, 1536, 16384, 60, 2, 1800)
    assert (c['pair_wall_s'], c['episode_wall_s'], c['evaluator_attempt_max_s'], c['evaluator_max_attempts'],
            c['max_logical_requests'], c['max_physical_requests']) == (7200, 1800, 1800, 2, 48, 96)
    assert MANIFEST['serving']['non_task_generation_probes'] == 0
    assert all(MANIFEST[k] for k in ('declared_rules', 'interpretations', 'inherited_labels', 'semantics_differences',
                                     'scope'))


def test_manifest_binds_to_code_conversion_record_and_req010():
    assert P.manifest_problems(MANIFEST, CONV, REQ010) == []
    ok, detail = P.probe_manifest(ROOT)
    assert ok and detail['problems'] == []
    assert detail['manifest_sha256'] == hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()


def _swap(m):
    m['assignments'].reverse()


def _third(m):
    m['assignments'].append(dict(m['assignments'][1], order=3))


MUTATIONS = dict(
    swapped_order=_swap, third_arm=_third, one_arm=lambda m: m['assignments'].pop(),
    cue_arm=lambda m: m['assignments'][0].update(arm='cue'),
    other_model=lambda m: m['assignments'][1].update(gguf_sha256=LARGE_SHA),
    other_port=lambda m: m['assignments'][0].update(port=8291),
    other_task=lambda m: m.update(instance_id='astropy__astropy-12907'),
    image=lambda m: m['images']['instance'].update(id='sha256:' + '0' * 64),
    cap=lambda m: m['caps'].update(pair_wall_s=7201),
    settings=lambda m: m['settings'].update(step_limit=25),
    probes=lambda m: m['serving'].update(non_task_generation_probes=4),
    watchdog=lambda m: m['watchdog'].update(poll_s=60),
    text=lambda m: m.pop('inherited_labels'))


@pytest.mark.parametrize('name', sorted(MUTATIONS))
def test_any_manifest_mismatch_fails_closed(name):
    m = json.loads(json.dumps(MANIFEST))
    MUTATIONS[name](m)
    assert P.manifest_problems(m, CONV, REQ010) != []


def test_admission_is_blocked_by_a_crashing_or_failing_probe_and_the_namespace_is_single_shot(tmp_path):
    (tmp_path / 'configs').mkdir()
    (tmp_path / P.MANIFEST_REL).write_bytes(MANIFEST_PATH.read_bytes())
    probes = OrderedDict(passing=lambda root: (True, {}), crashing=lambda root: 1 / 0,
                         manifest=lambda root: (False, {'why': 'fixture'}))
    assert P.main([], root=tmp_path, probes=probes) == 2
    raw, pub = tmp_path / P.OUTPUTS['raw'], tmp_path / P.OUTPUTS['published']
    adm = json.loads((raw / 'admission.json').read_text())
    assert (adm['admitted'], adm['passing']['ok'], adm['crashing']['ok'], adm['manifest']['ok']) == (
        False, True, False, False)
    assert adm['manifest_file'] == P.MANIFEST_REL
    assert adm['crashing']['detail']['error'].startswith('ZeroDivisionError')
    summary = json.loads((pub / 'pair_summary.json').read_text())
    assert (summary['status'], summary['executed'], summary['failed_admission_checks']) == (
        'BLOCKED', False, ['crashing', 'manifest'])
    assert [(a['order'], a['state']) for a in summary['assignments']] == [
        (1, 'not_started: pair blocked'), (2, 'not_started: pair blocked')]
    assert (pub / 'admission.json').exists() and (pub / 'publication_manifest.json').exists()
    assert not (raw / 'ledger.jsonl').exists()                                    # nothing was dispatched
    assert P.main([], root=tmp_path, probes=probes) == 3                          # a second launch refuses


def fake_git(fail=None):
    """git stand-in: ls-files/diff succeed for every source except the one named by fail=(kind, path)."""
    def run(cmd, env=None, timeout=60):
        kind = {'ls-files': 'untracked', 'diff': 'dirty'}[cmd[3]]
        return (1 if fail == (kind, cmd[-1]) else 0), '', ''
    return run


def test_the_source_binding_fails_closed_on_an_untracked_or_changed_source():
    base_ok = lambda root: (True, {})                                              # noqa: E731
    binding_ok = lambda root: (dict(binding_sha256='b' * 64, runtime=dict(sdk_traced_files=[],  # noqa: E731
                                                                          mini_swe_agent_sources=[])), [])
    ok, detail = P.probe_sources(ROOT, run=fake_git(), base=base_ok, compute_binding=binding_ok)
    assert ok and list(detail['req011_sources']) == list(P.SOURCES)
    assert {'experiments/v2_agent/req011_entry.py', 'experiments/v2_agent/cue_transport.py', P.MANIFEST_REL,
            'experiments/v2_adapter/req010_sentinel.py'} <= set(P.SOURCES)
    for fail in (('untracked', 'experiments/v2_agent/req011_entry.py'), ('dirty', 'experiments/v2_agent/cue_transport.py'),
                 ('dirty', P.MANIFEST_REL), ('untracked', 'experiments/v2_agent/req011_grade.py')):
        ok, detail = P.probe_sources(ROOT, run=fake_git(fail), base=base_ok, compute_binding=binding_ok)
        row = detail['req011_sources'][fail[1]]
        assert not ok and (row['tracked'], row['unchanged_from_head']) == (
            (False, True) if fail[0] == 'untracked' else (True, False))
    assert not P.probe_sources(ROOT, run=fake_git(), base=lambda root: (False, {}), compute_binding=binding_ok)[0]
    assert not P.probe_sources(ROOT, run=fake_git(), base=base_ok,
                               compute_binding=lambda root: (dict(runtime={}), ['sdk file differs']))[0]


# ---------------------------------------------------------------- exact two-arm queue, gates, schedule

class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


def fake_run_one(log, outcomes):
    def run_one(a, counted_before, rec):
        log.append((a['backend'], counted_before, P.request_limit(counted_before)))
        state, episode, gate = outcomes[a['backend']]
        rec.update(state=state, request_accounting=P.account(episode))
        return gate
    return run_one


def test_the_queue_is_exactly_large_then_small_with_their_ports_and_models():
    served, log, records = [], [], []
    stop = P.run_episodes(assignments(), 10000.0, lambda a: served.append((a['backend'], a['port'])),
                          fake_run_one(log, dict(large=('completed', {'physical_requests': 7}, None),
                                                 small=('completed', {'physical_requests': 5}, None))),
                          records, clock=Clock(0.0))
    assert stop is None
    assert served == [('large', 8293), ('small', 8291)]
    assert [(r['order'], r['backend'], r['alias'], r['state']) for r in records] == [
        (1, 'large', LARGE_ALIAS, 'completed'), (2, 'small', SMALL_ALIAS, 'completed')]
    assert log == [('large', 0, 48), ('small', 7, 48)]


def test_a_gate_failure_stops_the_pair_without_substitution():
    served, log, records = [], [], []

    def serve(a):
        served.append(a['backend'])
        raise P.Gate('served identity check failed')
    stop = P.run_episodes(assignments(), 10000.0, serve, fake_run_one(log, {}), records, clock=Clock(0.0))
    assert served == ['large'] and log == []
    assert stop == 'gate: served identity check failed'
    assert [r['state'] for r in records] == ['not_started: gate: served identity check failed'] * 2


def test_an_unresolved_or_killed_episode_does_not_stop_the_pair_and_unknown_requests_reserve_48():
    served, log, records = [], [], []
    stop = P.run_episodes(assignments(), 10000.0, lambda a: served.append(a['backend']),
                          fake_run_one(log, dict(large=('killed', None, None),
                                                 small=('completed', {'physical_requests': 48}, None))),
                          records, clock=Clock(0.0))
    assert stop is None and served == ['large', 'small']
    assert log == [('large', 0, 48), ('small', 48, 48)]
    assert [r['request_accounting']['accounting'] for r in records] == ['unknown_reserved', 'reported']
    assert sum(r['request_accounting']['counted'] for r in records) == 96


def test_a_host_gate_after_an_episode_stops_the_remaining_assignment():
    log, records = [], []
    stop = P.run_episodes(assignments(), 10000.0, lambda a: None,
                          fake_run_one(log, dict(large=('killed', None, 'episode process-group termination unconfirmed'))),
                          records, clock=Clock(0.0))
    assert stop == 'gate: episode process-group termination unconfirmed' and [x[0] for x in log] == ['large']
    assert records[1]['state'] == 'not_started: gate: episode process-group termination unconfirmed'


def test_schedule_gate_is_time_based_with_a_grading_floor():
    deadline = 100000.0
    # 600 load + 1800 episode + 120 child grace + 30 wait slack + 90 server reserve before deadline - 900 grading floor
    assert P.fits(deadline - 3540, deadline, 600) and not P.fits(deadline - 3539, deadline, 600)
    assert P.fits(deadline - 2940, deadline, 0) and not P.fits(deadline - 2939, deadline, 0)
    served, records = [], []
    stop = P.run_episodes(assignments(), deadline, served.append, fake_run_one([], {}), records,
                          clock=Clock(deadline - 3539))
    assert stop == 'pair cap' and served == []
    assert [r['state'] for r in records] == ['not_started: pair cap'] * 2
    clock, records = Clock(deadline - 3600), []

    def slow_load(a):
        clock.t = deadline - 2900                                  # the load itself used the allowance
    stop = P.run_episodes(assignments(), deadline, slow_load, fake_run_one([], {}), records, clock=clock)
    assert stop == 'pair cap (after load)' and [r['state'] for r in records] == ['not_started: pair cap (after load)'] * 2


def test_the_pause_file_stops_before_any_serving(tmp_path):
    (tmp_path / 'REQ011_PAUSE').write_text('hold\n')
    served, records = [], []
    stop = P.run_episodes(assignments(), 10000.0, served.append, fake_run_one([], {}), records, clock=Clock(0.0),
                          pause=tmp_path / 'REQ011_PAUSE')
    assert stop == 'paused (REQ011_PAUSE present)' and served == []


def test_request_accounting_rules():
    assert [P.account(e)['counted'] for e in ({'physical_requests': 0}, {'physical_requests': 7}, None, {},
                                               {'physical_requests': True}, {'physical_requests': 49},
                                               {'physical_requests': '3'})] == [0, 7, 48, 48, 48, 48, 48]
    assert [P.account(e)['accounting'] for e in ({'physical_requests': 7}, None, {'physical_requests': 49})] == [
        'reported', 'unknown_reserved', 'invalid']
    assert [P.request_limit(c) for c in (0, 7, 48, 60, 96)] == [48, 48, 48, 36, 0]


# ---------------------------------------------------------------- ledger and immutable resume

def test_ledger_never_redispatches_and_marks_a_start_without_end_interrupted(tmp_path):
    ledger = P.Ledger(tmp_path / 'ledger.jsonl')
    ledger.start(1, run_id='r1')
    assert ledger.states() == {1: dict(run_id='r1', state='interrupted')}
    with pytest.raises(P.Gate):
        ledger.start(1, run_id='r1-again')
    ledger.end(1, state='killed', run_id='r1')
    assert ledger.states() == {1: dict(run_id='r1', state='killed')}
    assert [e['event'] for e in ledger.events()] == ['start', 'end']
    with pytest.raises(P.Gate):
        ledger.start(1, run_id='r1-again')


STUB_CHILD = r'''
import json, subprocess, sys, time
from pathlib import Path
control = Path(sys.argv[1])
entry = json.loads(control.read_text())
ns = entry['namespace']
Path(ns['run_dir'], 'container_ownership.json').write_text(json.dumps(dict(container_id='c' * 64, run_id=ns['run_id'])))
grandchild = subprocess.Popen(['sleep', '120'])
control.parent.joinpath('pids.json').write_text(json.dumps(dict(grandchild=grandchild.pid)))
time.sleep(120)
'''


def fake_docker(listing):
    calls = []

    def run(cmd, env=None, timeout=60):
        calls.append(cmd)
        if cmd[:2] == ['docker', 'ps']:
            return 0, '\n'.join('%s %s' % (i, n) for i, n in listing) + '\n', ''
        if cmd[:3] == ['docker', 'rm', '-f']:
            listing[:] = [(i, n) for i, n in listing if i not in cmd[3:] and n not in cmd[3:]]
            return 0, '', ''
        return 1, '', 'unexpected'
    return run, calls


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    out = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)], capture_output=True, text=True).stdout.strip()
    return bool(out) and 'Z' not in out


def episode_ctx(tmp_path, run, **extra):
    stub = tmp_path / 'stub_child.py'
    stub.write_text(STUB_CHILD)
    ctx = dict(root=tmp_path, raw=tmp_path / 'raw', clock=time.time, popen=subprocess.Popen, run=run,
               env=dict(os.environ), python=sys.executable, entry=stub, image_id=PIN, pair_deadline=time.time() + 7200,
               served_arg=dict(model_sha256=LARGE_SHA), manifest_sha256='m' * 64, sources={}, runtime={},
               ledger=P.Ledger(tmp_path / 'ledger.jsonl'))
    ctx['raw'].mkdir()
    ctx.update(extra)
    return ctx


def test_deadline_cleanup_kills_the_whole_group_and_removes_only_the_recorded_container(tmp_path):
    listing = [(CID, 'minisweagent-1234abcd'), ('d' * 64, 'someone-elses-container')]
    run, calls = fake_docker(listing)
    ctx = episode_ctx(tmp_path, run)
    caps = dict(P.CAPS, episode_wall_s=2, child_cleanup_grace_s=0, child_wait_slack_s=1)
    rec = OrderedDict(order=1)
    gate = P.make_episode_runner(ctx, caps)(assignments()[0], 0, rec)
    assert gate is None                                            # a killed episode is not a gate
    assert rec['state'] == 'killed' and rec['process_group_gone'] is True
    grandchild = json.loads((ctx['raw'] / 'control' / rec['run_id'] / 'pids.json').read_text())['grandchild']
    assert not alive(grandchild)
    assert [c for c in calls if c[:2] == ['docker', 'rm']] == [['docker', 'rm', '-f', CID]]
    assert listing == [('d' * 64, 'someone-elses-container')]
    assert rec['container_removal']['complete'] is True
    assert (rec['request_accounting']['counted'], rec['request_accounting']['accounting']) == (48, 'unknown_reserved')
    entry = json.loads((ctx['raw'] / 'control' / rec['run_id'] / 'entry.json').read_text())['namespace']
    assert (entry['arm'], entry['instance'], entry['port'], entry['alias'], entry['expected_image'],
            entry['counted_before'], entry['request_limit'], entry['host_reserve_bytes']) == (
        'baseline', IID, 8293, LARGE_ALIAS, PIN, 0, 48, 1073741824)
    assert entry['block_deadline'] == ctx['pair_deadline'] - 900
    assert [(e['event'], e['order'], e.get('state')) for e in ctx['ledger'].events()] == [
        ('start', 1, None), ('end', 1, 'killed')]


SLEEPER = 'import time; time.sleep(300)'
STUB_PARENT = r'''
import json, os, subprocess, sys, time
from pathlib import Path
sys.path.insert(0, %(module_dir)r)
import req011_pair as P
base = Path(sys.argv[1])
server_cmd = [sys.executable, '-c', %(sleeper)r, '-m', str(base / 'work/models/fixture.gguf'), '--alias', 'fixture',
              '--host', '127.0.0.1', '--port', '8293', '-ngl', '99', '-np', '1', '-c', '16384']
server = subprocess.Popen(server_cmd, start_new_session=True)          # as pilot_runner.Servers.serve starts it
decoy = subprocess.Popen([sys.executable, '-c', %(sleeper)r, 'decoy'], start_new_session=True)
record = dict(holder=P.HOLDER, release_confirmed=False, unconfirmed_episode_pids=[], unconfirmed_container_runs=[],
              events=[], servers=[
                  dict(role='large', pid=server.pid, port=8293,
                       cmd=' '.join(c.replace(str(base) + '/', '') for c in server_cmd)),
                  dict(role='small', pid=decoy.pid, port=8291, cmd='llama-server -m other.gguf --port 8291')])
(base / 'servers.json').write_text(json.dumps(record))
(base / 'raw').mkdir()
wd, ready = P.spawn_watchdog(base / 'raw', time.time() + 3600, dict(os.environ), servers_record=base / 'servers.json',
                             root=base, poll_s=0.2, grace_s=5)
(base / 'pids.json').write_text(json.dumps(dict(server=server.pid, decoy=decoy.pid, watchdog=wd.pid, ready=ready)))
time.sleep(300)
'''


def wait_until(predicate, seconds):
    end = time.time() + seconds
    while time.time() < end:
        if predicate():
            return True
        time.sleep(0.2)
    return predicate()


def test_the_server_watchdog_stops_the_recorded_server_after_the_parent_is_sigkilled(tmp_path):
    script = tmp_path / 'stub_parent.py'
    script.write_text(STUB_PARENT % dict(module_dir=str(ROOT / 'experiments/v2_agent'), sleeper=SLEEPER))
    parent = subprocess.Popen([sys.executable, str(script), str(tmp_path)], start_new_session=True)
    pids = {}
    try:
        assert wait_until(lambda: (tmp_path / 'pids.json').exists(), 60)
        pids = json.loads((tmp_path / 'pids.json').read_text())
        assert pids['ready'] is True and alive(pids['server']) and alive(pids['watchdog'])
        time.sleep(1.0)
        assert alive(pids['server'])                                    # nothing happens while the parent lives
        os.kill(parent.pid, signal.SIGKILL)                             # no handler, no finally in the parent
        parent.wait(timeout=10)
        assert wait_until(lambda: not alive(pids['server']), 30)
        assert wait_until(lambda: not alive(pids['watchdog']), 30)
        assert alive(pids['decoy'])                                     # recorded PID, other command: never signalled
        action = json.loads((tmp_path / 'raw' / 'watchdog_action.json').read_text())
        assert (action['reason'], action['action'], action['record_released']) == (
            'parent process gone', 'stopped', False)
        assert [(s['pid'], s['matched'], s['signals'], s['recorded_command_still_running'])
                for s in action['servers']] == [(pids['server'], True, ['SIGTERM'], False),
                                                (pids['decoy'], False, [], False)]
        assert json.loads((tmp_path / 'servers.json').read_text())['release_confirmed'] is False   # not all ours
    finally:
        for pid in [parent.pid] + [pids[k] for k in ('server', 'decoy', 'watchdog') if k in pids]:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def test_the_watchdog_acts_only_on_its_own_record_and_releases_it_only_after_the_parent_is_gone(tmp_path):
    import threading
    cmd = [sys.executable, '-c', SLEEPER, '-m', str(tmp_path / 'work/models/fixture.gguf'), '--port', '8293']

    def case(name, holder, parent_gone, deadline_passed):
        server = subprocess.Popen(cmd, start_new_session=True)
        threading.Thread(target=server.wait, daemon=True).start()       # reap at once, as launchd would
        out = tmp_path / name
        out.mkdir()
        record = dict(holder=holder, release_confirmed=False, events=[], servers=[dict(
            role='large', pid=server.pid, port=8293, cmd=' '.join(c.replace(str(tmp_path) + '/', '') for c in cmd))])
        (out / 'servers.json').write_text(json.dumps(record))
        cfg = dict(parent_pid=4242, deadline=time.time() + (-1 if deadline_passed else 3600), holder=P.HOLDER,
                   out=str(out), servers_record=str(out / 'servers.json'), root=str(tmp_path), poll_s=0.05, grace_s=5)
        (out / 'cfg.json').write_text(json.dumps(cfg))
        assert P.watchdog(out / 'cfg.json', getppid=lambda: 1 if parent_gone else 4242) == 0
        gone = wait_until(lambda: server.poll() is not None, 10 if holder == P.HOLDER else 1.5)
        server.kill()
        return (gone, json.loads((out / 'watchdog_action.json').read_text()),
                json.loads((out / 'servers.json').read_text()))
    gone, action, record = case('foreign', 'DTR-AgentEvals worker (REQ-002 pilot)', True, False)
    assert not gone and action['action'].startswith('none') and record['release_confirmed'] is False
    gone, action, record = case('deadline', P.HOLDER, False, True)
    assert gone and (action['reason'], action['action'], action['record_released']) == (
        'pair deadline passed', 'stopped', False)
    assert record['servers'] and record['release_confirmed'] is False    # the live parent's own stop releases it
    gone, action, record = case('parent_gone', P.HOLDER, True, False)
    assert gone and (action['reason'], action['record_released']) == ('parent process gone', True)
    assert (record['servers'], record['release_confirmed'], record['events'][-1]['event']) == (
        [], True, 'stopped_by_watchdog')


def test_cleanup_cut_short_by_a_first_signal_is_left_for_the_outer_retry(tmp_path):
    exits = tmp_path / 'exits.py'
    exits.write_text('import sys\nsys.exit(0)\n')
    listing, calls = [], []

    def interrupting_docker(cmd, env=None, timeout=60):
        calls.append(cmd)
        if len(calls) == 1:
            raise S.Interrupted('SIGTERM')                     # the first signal lands inside settle()
        return 0, 'd%s someone-elses-container\n' % ('0' * 63), ''
    ctx = episode_ctx(tmp_path, interrupting_docker, entry=exits)
    rec = OrderedDict(order=1)
    with pytest.raises(S.Interrupted):
        P.make_episode_runner(ctx)(assignments()[0], 0, rec)
    assert list(ctx['backstops']) == ['settle episode 1'] and 'minisweagent_containers_listed_after' not in rec
    ctx['backstops']['settle episode 1']()                     # what run_pair's outer finally does, once
    assert (rec['settle_backstop'], rec['process_group_gone'], rec['minisweagent_containers_listed_after']) == (
        True, True, [])
    assert [e['event'] for e in ctx['ledger'].events()] == ['start']      # still 'interrupted' in the ledger


def test_a_started_assignment_is_never_dispatched_again(tmp_path):
    run, calls = fake_docker([])

    def no_spawn(*a, **k):
        raise AssertionError('must not spawn')
    ctx = episode_ctx(tmp_path, run, popen=no_spawn)
    ctx['ledger'].start(1, run_id='earlier')
    rec = OrderedDict(order=1)
    gate = P.make_episode_runner(ctx)(assignments()[0], 0, rec)
    assert gate.startswith('a record could not be written durably before dispatch')
    assert rec['state'] == 'not_started: gate: record not written'


# ---------------------------------------------------------------- grading retry classification

class FakeProc:
    def __init__(self, clock, hang=False):
        self.clock, self.hang, self.pid, self.returncode, self.signals = clock, hang, 2 ** 22 + 12345, None, []

    def poll(self):
        return None if self.hang else 0

    def send_signal(self, sig):                                     # a hanging fake evaluator dies on SIGTERM
        self.signals.append(sig)
        self.hang = False

    def wait(self, timeout=None):
        if self.hang:
            self.clock.t += timeout
            raise subprocess.TimeoutExpired('fake', timeout)
        self.returncode = 0
        return 0


def fake_harness(work, alias, submission, plan, clock, spawned):
    """plan: one scenario per spawned attempt: timeout / missing_report / setup_failure / report / bad_report / hang."""
    def popen(cmd, **_k):
        rid = cmd[cmd.index('--run_id') + 1]
        spawned.append(rid)
        kind = plan[len(spawned) - 1]
        logd = Path(work) / 'logs/run_evaluation' / rid / alias / IID
        if kind != 'hang':
            logd.mkdir(parents=True)
        if kind in ('timeout', 'missing_report', 'report', 'bad_report'):
            (logd / 'patch.diff').write_text(submission)
            (logd / 'test_output.txt').write_text('tests ran\n' + ('Timeout error: 1800 seconds exceeded.'
                                                                   if kind == 'timeout' else ''))
        if kind == 'report':
            (logd / 'report.json').write_text(json.dumps({IID: {'resolved': True}}))
        if kind == 'bad_report':
            (logd / 'report.json').write_text('{not json')
        return FakeProc(clock, hang=kind == 'hang')
    return popen


def grade_case(tmp_path, plan, now=0.0, pair_deadline=100000.0):
    submission = 'diff --git a/x b/x\n'
    episode = dict(instance_id=IID, backend='large', run_id='run-1', exit_status='Submitted',
                   submission_sha256=hashlib.sha256(submission.encode()).hexdigest(), pins=dict(image_id=PIN))
    work, clock, spawned, log = tmp_path / 'grading', Clock(now), [], []
    work.mkdir(parents=True)
    run, calls = fake_docker([])
    harness = G.make_run_harness(IID, LARGE_ALIAS, work, pair_deadline, P.CAPS, log, {}, clock=clock,
                                 popen=fake_harness(work, LARGE_ALIAS, submission, plan, clock, spawned), run=run)
    try:
        result = G.GI.grade_flow(episode, submission, PIN, work, tmp_path / 'grade.json', harness,
                                 lambda logd: ('resolved', {}), LARGE_ALIAS)
    except (G.NoRetry, G.Ungraded) as e:
        result = e
    return result, [x['classification'] for x in log], spawned, calls, work


def test_timeout_and_missing_report_are_retried_once(tmp_path):
    result, classes, spawned, _, _ = grade_case(tmp_path / 'a', ['timeout', 'report'])
    assert classes == ['timeout', 'report_present'] and len(spawned) == 2
    assert (result['classification'], result['strict_outcome'], len(result['attempts'])) == ('evaluated', 'resolved', 2)
    result, classes, _, _, _ = grade_case(tmp_path / 'b', ['missing_report', 'missing_report'])
    assert classes == ['missing_report', 'missing_report']
    assert (result['classification'], result['operational_resolved']) == ('unknown_evaluator_failure', 0)


def test_a_setup_failure_or_an_unusable_report_is_a_diagnosis_not_a_retry(tmp_path):
    result, classes, spawned, _, work = grade_case(tmp_path / 'a', ['setup_failure'])
    assert isinstance(result, G.NoRetry) and classes == ['setup_failure'] and len(spawned) == 1
    assert not (tmp_path / 'a' / 'grade.json').exists()
    assert sorted(p.name for p in work.glob('*.preds.json')) == ['eval-run-1-%s-a1.preds.json' % hashlib.sha256(
        b'diff --git a/x b/x\n').hexdigest()[:16]]
    result, classes, spawned, _, _ = grade_case(tmp_path / 'b', ['bad_report'])
    assert isinstance(result, G.NoRetry) and classes == ['report_present'] and len(spawned) == 1


def test_an_attempt_killed_at_its_wall_budget_is_cleaned_up_and_retried_only_if_it_fits(tmp_path):
    result, classes, spawned, calls, _ = grade_case(tmp_path / 'a', ['hang', 'report'])
    assert classes == ['wall_timeout', 'report_present'] and result['classification'] == 'evaluated'
    assert all(c[:2] == ['docker', 'ps'] for c in calls)           # nothing listed, nothing removed
    # 1800 s + 300 s end reserve + 599 s: the first attempt runs (1800 s), the retry cannot start (599 s < 600 s)
    result, classes, spawned, _, _ = grade_case(tmp_path / 'b', ['hang'], now=0.0, pair_deadline=1800 + 300 + 599)
    assert classes == ['wall_timeout'] and isinstance(result, G.Ungraded) and len(spawned) == 1
    assert not (tmp_path / 'b' / 'grade.json').exists()                         # never imputed


def test_an_evaluator_that_cannot_start_inside_the_pair_cap_is_ungraded(tmp_path):
    result, classes, spawned, _, _ = grade_case(tmp_path, ['report'], now=0.0, pair_deadline=300 + 599)
    assert isinstance(result, G.Ungraded) and spawned == [] and classes == []


def test_grading_refuses_a_changed_image_and_zeros_a_non_submitted_episode_without_the_evaluator(tmp_path):
    run_dir = tmp_path / 'run'
    run_dir.mkdir()
    (run_dir / 'submission.diff').write_text('')
    (run_dir / 'episode.json').write_text(json.dumps(dict(
        instance_id=IID, backend='small', run_id='run-2', exit_status='EpisodeDeadline', backend_alias=SMALL_ALIAS,
        submission_sha256=hashlib.sha256(b'').hexdigest(), pins=dict(image_id=PIN))))
    control = dict(run_dir=str(run_dir), work=str(tmp_path / 'grading'), pair_deadline=1e12, image_pin=PIN,
                   caps=P.CAPS)

    def docker(image_id):
        return lambda cmd, env=None, timeout=60: (0, image_id + '\n', '')

    def no_popen(*a, **k):
        raise AssertionError('the evaluator must not run')
    out = G.grade(control, run=docker('sha256:' + '1' * 64), popen=no_popen)
    assert out['status'] == 'refused: instance image differs from the pin before grading'
    assert not (run_dir / 'grade.json').exists()
    out = G.grade(control, run=docker(PIN), popen=no_popen)
    assert (out['status'], out['image_after_equals_pin']) == ('graded: operational_zero', True)
    grade = json.loads((run_dir / 'grade.json').read_text())
    assert (grade['classification'], grade['evaluated'], grade['operational_resolved']) == ('operational_zero', False, 0)


def test_grader_command_is_the_stock_grade_submission_command():
    cmd = G.harness_cmd(IID, 'eval-r-a1', '/w/p.json', '/w', python='py')
    assert cmd == ['py', '-m', 'swebench.harness.run_evaluation', '--dataset_name', str(G.GS.DATA), '--split', 'train',
                   '--predictions_path', '/w/p.json', '--instance_ids', IID, '--run_id', 'eval-r-a1', '--namespace',
                   'none', '--max_workers', '1', '--timeout', '1800', '--cache_level', 'instance', '--report_dir', '/w']


def test_the_grader_refuses_changed_sources_before_grading_or_spawning(tmp_path, monkeypatch):
    def forbidden(*a, **k):
        raise AssertionError('nothing may run after a source mismatch')
    monkeypatch.setattr(G, 'grade', forbidden)
    monkeypatch.setattr(G.subprocess, 'Popen', forbidden)
    good = 'experiments/v2_agent/grade_submission.py'
    control = dict(admitted_sources={good: hashlib.sha256((ROOT / good).read_bytes()).hexdigest(),
                                     'experiments/v2_agent/grade_identity.py': '0' * 64},
                   run_dir=str(tmp_path / 'run'), work=str(tmp_path / 'grading'), pair_deadline=1e12, image_pin=PIN,
                   caps=P.CAPS)
    (tmp_path / 'grade_control.json').write_text(json.dumps(control))
    before = {sig: signal.getsignal(sig) for sig in G.SIGNALS}
    assert G.main([str(tmp_path / 'grade_control.json')]) == 3
    assert {sig: signal.getsignal(sig) for sig in G.SIGNALS} == before
    result = json.loads((tmp_path / 'grade_result.json').read_text())
    assert (result['status'], result['changed']) == ('refused: sources changed since admission',
                                                     ['experiments/v2_agent/grade_identity.py'])


# ---------------------------------------------------------------- grading containment with real processes

GRADER_WRAPPER = r'''
import json, os, sys
from pathlib import Path
sys.path.insert(0, %(module_dir)r)
import req011_grade as G                       # the real grader; only the evaluator command and docker are stand-ins
control_path = Path(sys.argv[1])
state = control_path.parent
(state / 'grader_pid.json').write_text(json.dumps(os.getpid()))
EVALUATOR = """
import json, os, subprocess, sys, time
child = subprocess.Popen(['sleep', '300'])
with open(sys.argv[1], 'a') as fh:
    fh.write(json.dumps(dict(evaluator=os.getpid(), grandchild=child.pid, pgid=os.getpgid(0))) + '\\n')
time.sleep(300)
"""
G.harness_cmd = lambda iid, run_id, preds, work, python=sys.executable: [
    python, '-c', EVALUATOR, str(state / 'evaluator_pids.jsonl')]
listing = json.loads((state / 'docker_listing.json').read_text())


def fake_sh(cmd, env=None, timeout=60):
    with open(state / 'grader_docker_calls.jsonl', 'a') as fh:
        fh.write(json.dumps(cmd) + '\n')
    if cmd[:3] == ['docker', 'image', 'inspect']:
        return 0, listing['image'] + '\n', ''
    if cmd[:2] == ['docker', 'ps']:
        return 0, '\n'.join(listing['names']) + '\n', ''
    if cmd[:3] == ['docker', 'rm', '-f']:
        listing['names'] = [n for n in listing['names'] if n not in cmd[3:]]
        return 0, '', ''
    return 1, '', 'unexpected'


sys.exit(G.main([str(control_path)], run=fake_sh))
'''
DECOYS = ['sweb.eval.%s.eval-someone-else-a1' % IID, 'dtr-qual-astropy-astropy-14598-reference-1', 'minisweagent-1234abcd']


def grading_case(tmp_path, exit_status='Submitted', submission='diff --git a/x b/x\n'):
    wrapper = tmp_path / 'grader_wrapper.py'
    wrapper.write_text(GRADER_WRAPPER % dict(module_dir=str(ROOT / 'experiments/v2_agent')))
    run_id = IID + '__large__req011__fixture-grading'
    raw = tmp_path / 'raw'
    (raw / run_id).mkdir(parents=True)
    (raw / 'control' / run_id).mkdir(parents=True)
    episode = dict(instance_id=IID, backend='large', backend_alias=LARGE_ALIAS, run_id=run_id, exit_status=exit_status,
                   submission_sha256=hashlib.sha256(submission.encode()).hexdigest(), pins=dict(image_id=PIN))
    (raw / run_id / 'episode.json').write_text(json.dumps(episode))
    (raw / run_id / 'submission.diff').write_text(submission)
    root_id = 'eval-%s-%s' % (run_id, hashlib.sha256(submission.encode()).hexdigest()[:16])
    own = ['sweb.eval.%s.%s-a%d' % (IID, root_id, n) for n in (1, 2)]
    (raw / 'control' / run_id / 'docker_listing.json').write_text(json.dumps(dict(image=PIN, names=own + DECOYS)))
    listing = [('%064x' % n, name) for n, name in enumerate(own + DECOYS)]
    run, calls = fake_docker(listing)
    ctx = dict(root=tmp_path, raw=raw, clock=time.time, popen=subprocess.Popen, run=run, env=dict(os.environ),
               grader_python=sys.executable, grader=wrapper, image_id=PIN, sources={})
    return ctx, dict(run_id=run_id), own, listing, calls, raw / 'control' / run_id


def evaluator_processes(control):
    path = control / 'evaluator_pids.jsonl'
    return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []


def test_the_grader_stops_each_evaluator_at_its_wall_budget_and_the_parent_kills_what_is_left(tmp_path):
    ctx, rec, own, listing, calls, control = grading_case(tmp_path)
    ctx['pair_deadline'] = time.time() + 600
    caps = dict(P.CAPS, evaluator_attempt_max_s=2, evaluator_min_start_budget_s=1)
    out = P.make_grader(ctx, caps)(rec)
    procs = evaluator_processes(control)
    grader_pid = json.loads((control / 'grader_pid.json').read_text())
    assert len(procs) == 2 and all(x['pgid'] == grader_pid != os.getpgid(0) for x in procs)   # inside the grader group
    assert not any(alive(x['evaluator']) or alive(x['grandchild']) for x in procs)
    assert (out['status'], out['grader_killed'], out['grader_group_gone']) == (
        'graded: unknown_evaluator_failure', False, True)
    attempts = out['grader']['attempts']
    assert [(a['classification'], a['evaluator_stopped'], a['container_cleanup']['name']) for a in attempts] == [
        ('wall_timeout', True, own[0]), ('wall_timeout', True, own[1])]
    grader_rm = [json.loads(x) for x in (control / 'grader_docker_calls.jsonl').read_text().splitlines()
                 if json.loads(x)[:2] == ['docker', 'rm']]
    assert grader_rm == [['docker', 'rm', '-f', own[0]], ['docker', 'rm', '-f', own[1]]]
    assert [c for c in calls if c[:2] == ['docker', 'rm']] == [['docker', 'rm', '-f'] + own]      # the parent's pass
    assert [n for _, n in listing] == DECOYS                                    # only this run's evaluator containers


def test_a_grader_killed_at_the_pair_cap_takes_its_evaluator_group_with_it(tmp_path):
    ctx, rec, own, listing, calls, control = grading_case(tmp_path)
    ctx['pair_deadline'] = time.time() + 12
    # the parent stops waiting at deadline - 5 - 2 (about 5 s from now); the grader's own budget would end later
    caps = dict(P.CAPS, evaluator_end_reserve_s=5, grader_wait_slack_s=-2, evaluator_min_start_budget_s=1)
    out = P.make_grader(ctx, caps)(rec)
    procs = evaluator_processes(control)
    assert len(procs) == 1 and not alive(procs[0]['evaluator']) and not alive(procs[0]['grandchild'])
    assert (out['status'], out['grader_killed'], out['grader_group_gone']) == (
        'ungraded: pair cap (grader killed at the pair cap)', True, True)
    assert out['grader']['status'] == 'ungraded: interrupted (SIGTERM)'         # the grader's own record
    assert out['grader']['attempts'][0]['container_cleanup']['name'] == own[0]
    assert [c for c in calls if c[:2] == ['docker', 'rm']] == [['docker', 'rm', '-f'] + own]
    assert [n for _, n in listing] == DECOYS
    assert 'classification' not in out                                           # never imputed


def test_a_non_submitted_episode_gets_its_operational_zero_even_late_and_runs_no_evaluator(tmp_path):
    ctx, rec, own, listing, calls, control = grading_case(tmp_path, exit_status='LimitsExceeded', submission='')
    ctx['pair_deadline'] = time.time() + 3                  # past deadline - evaluator_end_reserve_s already
    caps = dict(P.CAPS, evaluator_end_reserve_s=5, grader_wait_slack_s=60)
    out = P.make_grader(ctx, caps)(rec)
    assert (out['status'], out['evaluable'], out['classification'], out['operational_resolved']) == (
        'graded: operational_zero', False, 'operational_zero', 0)
    assert evaluator_processes(control) == [] and out['evaluator_container_cleanup']['refs'] == []


# ---------------------------------------------------------------- served identity and sandbox

def test_served_identity_checks_are_get_only_and_exact():
    gguf = str(ROOT / MANIFEST['assignments'][0]['gguf'])
    props = dict(model_path=gguf, model_alias=LARGE_ALIAS, build_info='b11041-4fea119de', total_slots=1,
                 default_generation_settings=dict(n_ctx=16384))
    models = dict(data=[dict(id=LARGE_ALIAS)])
    assert P.served_problems(props, models, 4242, 4242, gguf=gguf, alias=LARGE_ALIAS) == []
    bad = [dict(props, model_path=gguf.replace('converted_4fea119/', '')), dict(props, model_alias='other'),
           dict(props, build_info='b1-deadbee'), dict(props, total_slots=2),
           dict(props, default_generation_settings=dict(n_ctx=32768))]
    assert all(P.served_problems(b, models, 4242, 4242, gguf=gguf, alias=LARGE_ALIAS) for b in bad)
    assert P.served_problems(props, dict(data=[]), 4242, 4242, gguf=gguf, alias=LARGE_ALIAS)
    assert P.served_problems(props, models, 999, 4242, gguf=gguf, alias=LARGE_ALIAS)


def test_the_post_load_check_uses_get_only_requests_and_timed_host_probes():
    a = assignments()[0]
    gguf = str(ROOT / a['gguf'])
    props = dict(model_path=gguf, model_alias=LARGE_ALIAS, build_info='b11041-4fea119de', total_slots=1,
                 default_generation_settings=dict(n_ctx=16384), chat_template='{{ x }}')
    gets, probes = [], []

    def get(url):
        gets.append(url)
        return props if url.endswith('/props') else dict(data=[dict(id=LARGE_ALIAS)])

    def host(listener, free):
        def run(cmd, env=None, timeout=60):
            probes.append((cmd[0], timeout))
            return {'lsof': (0, '%d\n' % listener, ''),
                    'memory_pressure': (0, 'System-wide memory free percentage: %d%%\n' % free, ''),
                    'sysctl': (0, 'total = 12288.00M  used = 1.00M  free = 12287.00M\n', ''),
                    'ps': (0, '  123456\n', '')}[cmd[0]]
        return run
    servers = type('Live', (), dict(live=dict(pid=4242)))()
    checks, problems = P.check_served(servers, a, ROOT, get=get, run=host(4242, 45))
    assert problems == [] and gets == ['http://127.0.0.1:8293/props', 'http://127.0.0.1:8293/v1/models']
    assert (checks['memory_free_pct'], checks['rss_kb'], checks['server_pid']) == (45, 123456, 4242)
    assert all(timeout is not None and timeout <= 30 for _, timeout in probes)
    assert P.check_served(servers, a, ROOT, get=get, run=host(999, 45))[1]           # another listener
    assert P.check_served(servers, a, ROOT, get=get, run=host(4242, 9))[1]           # post-load memory below 10 %


def test_agent_sandbox_rule():
    good = dict(env=dict(PAGER='cat', MANPAGER='cat', LESS='-R', PIP_PROGRESS_BAR='off', TQDM_DISABLE='1'),
                image=PIN, cwd='/testbed', executable='docker', timeout=60, run_args=['--rm', '--platform', 'linux/amd64'])
    assert P.sandbox_problems(good) == []
    for bad in (dict(good, forward_env=['HOME']), dict(good, env=dict(good['env'], GITHUB_TOKEN='x')),
                dict(good, run_args=['--rm', '--platform', 'linux/amd64', '-v', '/:/host']),
                dict(good, run_args=['--rm', '--network', 'host']), dict(good, volumes=['/x'])):
        assert P.sandbox_problems(bad)


# ---------------------------------------------------------------- sanitization, username guard, summary

def test_publication_sanitizes_hashes_and_guards_the_username(tmp_path):
    raw, pub = tmp_path / 'raw', tmp_path / 'pub'
    (raw / 'run-1' / 'receipts').mkdir(parents=True)
    (raw / 'control' / 'run-1').mkdir(parents=True)
    pub.mkdir()
    (raw / 'admission.json').write_text(json.dumps(dict(path=str(P.ROOT / 'work/x'), home=str(Path.home() / 'y'))))
    (raw / 'run-1' / 'episode.json').write_text('{}')
    (raw / 'run-1' / 'receipts' / 'call001_attempt01.outcome.json').write_text('{}')
    (raw / 'control' / 'run-1' / 'child_stdout.txt').write_text('owner ' + getpass.getuser() + '\n')
    (raw / 'server_large_x.log').write_text('loaded\n')
    manifest, hits = P.publish(raw, pub, ['run-1'])
    assert json.loads((pub / 'admission.json').read_text()) == dict(path='./work/x', home='~/y')
    assert manifest['admission.json']['sanitized'] is True
    assert manifest['admission.json']['raw_sha256'] == hashlib.sha256((raw / 'admission.json').read_bytes()).hexdigest()
    assert sorted(manifest) == ['admission.json', 'run-1/control/child_stdout.txt', 'run-1/episode.json',
                                'run-1/receipts/call001_attempt01.outcome.json', 'server_large_x.log.txt']
    if len(getpass.getuser()) >= 3:
        assert hits == ['run-1/control/child_stdout.txt'] and (pub / 'USERNAME_FOUND.json').exists()


def test_the_summary_is_always_written_even_when_the_pair_is_interrupted(tmp_path):
    (tmp_path / 'configs').mkdir()
    (tmp_path / P.MANIFEST_REL).write_bytes(MANIFEST_PATH.read_bytes())
    before = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}

    def runner(ctx):
        ctx['ledger'].start(1, run_id='run-1')
        (ctx['raw'] / 'run-1').mkdir()
        raise S.Interrupted('SIGTERM')
    assert P.main([], root=tmp_path, probes=OrderedDict(ok=lambda root: (True, {})), runner=runner) == 0
    assert {sig: signal.getsignal(sig) for sig in before} == before              # handlers restored
    summary = json.loads((tmp_path / P.OUTPUTS['published'] / 'pair_summary.json').read_text())
    assert (summary['status'], summary['interrupted_or_error']) == ('INTERRUPTED', 'SIGTERM')
    rows = summary['assignments']
    assert [(r['order'], r['state'], r.get('run_id')) for r in rows] == [
        (1, 'interrupted', 'run-1'), (2, 'not_started: pair interrupted', None)]
    assert rows[0]['request_accounting']['counted'] == 48 and rows[0]['episode_record_present'] is False
    assert rows[0]['grade']['status'] == 'no grade: grading not reached (INTERRUPTED)'
    assert summary['requests']['physical_counted_total'] == 48 and summary['within_cap'] is True
    assert summary['inherited_labels'] == MANIFEST['inherited_labels']


def test_an_error_in_the_pair_still_writes_the_summary(tmp_path):
    (tmp_path / 'configs').mkdir()
    (tmp_path / P.MANIFEST_REL).write_bytes(MANIFEST_PATH.read_bytes())

    def runner(ctx):
        raise ValueError('fixture')
    assert P.main([], root=tmp_path, probes=OrderedDict(ok=lambda root: (True, {})), runner=runner) == 0
    summary = json.loads((tmp_path / P.OUTPUTS['raw'] / 'pair_summary.json').read_text())
    assert (summary['status'], summary['interrupted_or_error']) == ('ERROR', 'ValueError: fixture')
    assert [r['state'] for r in summary['assignments']] == ['not_started: pair error'] * 2
    assert summary['outcome_sources'] == dict(eligible_submission=0, agent=0, time_limit=0,
                                              infrastructure_or_supervision=2)


def test_an_unreadable_episode_record_never_costs_the_summary(tmp_path):
    (tmp_path / 'configs').mkdir()
    (tmp_path / P.MANIFEST_REL).write_bytes(MANIFEST_PATH.read_bytes())

    def runner(ctx):
        ctx['ledger'].start(1, run_id='run-1')
        run_dir = ctx['raw'] / 'run-1'
        (run_dir / 'receipts').mkdir(parents=True)
        (run_dir / 'submission.diff').write_bytes(b'\xff\xfe not utf-8\n')
        (run_dir / 'receipts' / 'call001_attempt01.outcome.json').write_text(json.dumps(dict(
            server_reported_usage=dict(usage_known=True))))                  # malformed: no token fields
        ctx['ledger'].end(1, state='completed', run_id='run-1')
        return None
    assert P.main([], root=tmp_path, probes=OrderedDict(ok=lambda root: (True, {})), runner=runner) == 0
    summary = json.loads((tmp_path / P.OUTPUTS['published'] / 'pair_summary.json').read_text())
    row = summary['assignments'][0]
    assert row['state'] == 'completed' and row['episode_facts_error'].startswith('KeyError')
    assert row['outcome_source'] == 'infrastructure_or_supervision'


def test_outcome_source_separates_infrastructure_from_agent_endings():
    assert [P.outcome_source(*x) for x in (
        ('completed', 'Submitted', True), ('completed', 'Submitted', False), ('completed', 'LimitsExceeded', False),
        ('completed', 'RepeatedFormatError', False), ('completed', 'EpisodeDeadline', False),
        ('completed', 'TimeExceeded', False), ('completed', 'InfrastructureStop', False),
        ('completed', 'StartPreflightRefused', False), ('completed', 'InternalServerError', False),
        ('killed', 'LimitsExceeded', False), ('interrupted', None, False), ('not_started: pair cap', None, False),
        ('exited_without_episode_record', None, False))] == [
        'eligible_submission', 'agent', 'agent', 'agent', 'time_limit', 'time_limit'] + [
        'infrastructure_or_supervision'] * 7


def test_call9_pre_action_resources_are_derived_from_the_records(tmp_path):
    run_dir, control = tmp_path / 'run', tmp_path / 'control'
    run_dir.mkdir()
    control.mkdir()
    assert P.call9_facts(run_dir, control) is None
    (run_dir / 'call9_history.json').write_text(json.dumps(dict(call=9, messages=[{}] * 17, captured_at=1000.0)))
    starts = [dict(call=c, attempt=1, t_start=900.0 + c) for c in range(1, 9)] + [dict(call=3, attempt=2, t_start=950.0)]
    (run_dir / 'attempts.jsonl').write_text(''.join(json.dumps(dict(s, event=e)) + '\n' for s in starts
                                                    for e in ('start', 'result')) + '{torn')
    (control / 'entry.json').write_text(json.dumps(dict(namespace=dict(request_limit=48, episode_deadline=2500.0))))
    facts = P.call9_facts(run_dir, control)
    assert (facts['message_count'], facts['logical_calls_before'], facts['physical_attempts_before'],
            facts['request_budget_remaining'], facts['seconds_since_first_request'],
            facts['seconds_to_episode_deadline']) == (17, 8, 9, 39, 99.0, 1500.0)


# ---------------------------------------------------------------- all-exit capture through the real entry (pinned venv)

MSWEA_PY = ROOT / 'work/venvs/minisweagent_04d809c/bin/python'
HARNESS = ROOT / 'experiments/tools/req011_integration_harness.py'
DATA = ROOT / 'work/benchmark_inputs/swebench_verified_c104f840/test-00000-of-00001.parquet'
FROZEN_HARNESS = ROOT / 'experiments/tools/v2_cue_integration_harness.py'   # unedited REQ-005 harness, mode 'frozen'
FAKE_IMAGE = PIN                  # the fake docker reports the pinned instance image (the entry checks the manifest)
MANIFEST_SHA = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
CUE_TEXT = b'Recent actions returned the same visible feedback repeatedly.'
MOD_NEW_DIFF = (b'diff --git a/mod.py b/mod.py\n'
                b'index 7d4290a117a4ddcc11daae7ea675841033830c8f..407de3068e7b5950585d5abed9776d104235a85d 100644\n'
                b'--- a/mod.py\n'
                b'+++ b/mod.py\n'
                b'@@ -1 +1 @@\n'
                b'-x = 1\n'
                b'+x = 2\n'
                b'diff --git a/new_file.py b/new_file.py\n'
                b'new file mode 100644\n'
                b'index 0000000000000000000000000000000000000000..4a3f3148a6563c03794f7e788da042e0d5214f98\n'
                b'--- /dev/null\n'
                b'+++ b/new_file.py\n'
                b'@@ -0,0 +1 @@\n'
                b'+n = 1\n')
MOD_NEW_SHA = '27788b1f35a18178bf79d7f78cd17bbe50897761c99112455ec5abce4467335b'


def act(command):
    return dict(content='THOUGHT: next step\n\n```mswea_bash_command\n%s\n```' % command)


LS, SUBMIT = act('ls'), act('echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT')
EDIT = act("printf 'x = 2\\n' > mod.py && printf 'n = 1\\n' > new_file.py")
TAMPERED = ('experiments/v2_agent/cue_transport.py', 'experiments/v2_agent/grade_submission.py',
            'experiments/v2_agent/req011_entry.py')
SCENARIOS = dict(
    submitted=dict(script=[LS, EDIT, SUBMIT], deadline_in=600),
    retry=dict(script=[LS, dict(status=500), EDIT, SUBMIT], deadline_in=600),
    unsubmitted=dict(script=[EDIT, dict(status=500), dict(status=500)], deadline_in=600),
    deadline=dict(script=[LS, dict(LS, sleep=120)], deadline_in=12),
    refused=dict(script=[LS], deadline_in=600, arm='cue', occupied=True),
    tampered=dict(script=[LS], deadline_in=600, tamper=TAMPERED, namespace=dict(port=8291)),
    budget=dict(script=[LS, LS, LS, LS], deadline_in=600, namespace=dict(counted_before=94, request_limit=2)))
PARITY = ('submitted', 'retry', 'unsubmitted')      # also run through the frozen yaml-v1 driver

FAKE_DOCKER = r'''#!/bin/bash
# fake docker for DTR-REQ-011 entry fixtures: no container; exec commands run in a disposable Git repository
STATE="$(cd "$(dirname "$0")" && pwd)/state"
REPO="$(cat "$STATE/repo")"
printf '%s %s\n' "$1" "$2" >> "$STATE/calls.log"
case "$1" in
  image) cat "$STATE/image_id"; exit 0 ;;
  run) cat "$STATE/container_id"; exit 0 ;;
  stop) exit 0 ;;
  rm) exit 0 ;;
  container) echo false; exit 0 ;;
  exec)
    shift
    envs=()
    while [ "$#" -gt 0 ]; do
      case "$1" in
        -w) shift 2 ;;
        -e) envs+=("$2"); shift 2 ;;
        *) break ;;
      esac
    done
    shift
    interp=()
    while [ "$#" -gt 1 ]; do interp+=("$1"); shift; done
    cmd="${1//\/testbed/$REPO}"
    cd "$REPO" && exec env "${envs[@]}" "${interp[@]}" "$cmd"
    ;;
esac
exit 2
'''


def git(repo, *args):
    env = dict(os.environ, GIT_AUTHOR_DATE='2026-09-23T00:00:00Z', GIT_COMMITTER_DATE='2026-09-23T00:00:00Z')
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True, env=env)


def workspace(base):
    home = base / 'home'
    bindir = home / '.local/dtr-runtime/bin'
    bindir.mkdir(parents=True)
    (bindir / 'docker').write_text(FAKE_DOCKER)
    (bindir / 'docker').chmod(0o755)
    state = bindir / 'state'
    state.mkdir()
    repo = base / 'testbed'
    repo.mkdir()
    git(repo, 'init', '-q')
    git(repo, 'config', 'user.email', 'f@x')
    git(repo, 'config', 'user.name', 'f')
    (repo / 'keep.py').write_text('a = 1\n')
    (repo / 'mod.py').write_text('x = 1\n')
    (repo / '.gitignore').write_text('*.pyc\n')
    git(repo, 'add', '-A')
    git(repo, 'commit', '-qm', 'base')
    (state / 'repo').write_text(str(repo))
    (state / 'image_id').write_text(FAKE_IMAGE + '\n')
    (state / 'container_id').write_text(CID + '\n')
    return home, state


def run_scenario(base, name, sources, runtime):
    scenario = SCENARIOS[name]
    home, state = workspace(base)
    run_id = '%s__large__req011__fixture-%s' % (IID, name)
    run_dir, control_dir, layout_root = base / 'raw' / run_id, base / 'raw' / 'control' / run_id, base / 'layout'
    run_dir.mkdir(parents=True)
    control_dir.mkdir(parents=True)
    (layout_root / 'work').mkdir(parents=True)
    if scenario.get('occupied'):
        (run_dir / 'leftover.txt').write_text('x\n')
    sources = dict(sources, **{rel: '0' * 64 for rel in scenario.get('tamper', ())})
    control = dict(request='DTR-REQ-011', binding_sha256=MANIFEST_SHA, assignment_id='req011-1-large',
                   model_sha256=LARGE_SHA, admitted_sources=sources, runtime=runtime, namespace=dict(
                       instance=IID, backend='large', arm=scenario.get('arm', 'baseline'), position=1, port=8293,
                       alias=LARGE_ALIAS, run_dir=str(run_dir), run_id=run_id, expected_image=FAKE_IMAGE,
                       served=json.dumps(dict(model_file='fixture.gguf', model_sha256=LARGE_SHA)), counted_before=0,
                       request_limit=48, host_reserve_bytes=1 << 30))
    control['namespace'].update(scenario.get('namespace', {}))
    config = dict(out=str(base / 'out'), script=scenario['script'], alias=LARGE_ALIAS, model_file='fixture.gguf',
                  module_dir=str(ROOT / 'experiments/v2_agent'), layout_root=str(layout_root), control=control,
                  control_path=str(control_dir / 'entry.json'), deadline_in=scenario['deadline_in'])
    (base / 'config.json').write_text(json.dumps(config))
    env = {k: v for k, v in os.environ.items()
           if not k.lower().endswith('_proxy') and not k.startswith(('LITELLM_', 'EXPERIMENTAL_OPENAI', 'MSWEA_'))}
    env.update(HOME=str(home), LITELLM_LOCAL_MODEL_COST_MAP='True', MSWEA_SILENT_STARTUP='1',
               MSWEA_GLOBAL_CONFIG_DIR=str(base / 'mswea_config'))
    proc = subprocess.run([str(MSWEA_PY), str(HARNESS), str(base / 'config.json')], capture_output=True, text=True,
                          env=env, timeout=600, cwd=str(base))
    assert proc.returncode == 0, proc.stderr[-4000:]
    harness = json.loads((base / 'out' / 'harness.json').read_text())
    return dict(harness=harness, run_dir=run_dir, control=control_dir, run_id=run_id, state=state,
                private=layout_root / 'work/req005_request_receipts/cue-v1' / run_id,
                bodies=[p.read_bytes() for p in sorted((base / 'out' / 'terminal').glob('*.body'))], stderr=proc.stderr)


@pytest.fixture(scope='module')
def entry_runs(tmp_path_factory):
    if not MSWEA_PY.exists() or not DATA.exists():
        pytest.skip('pinned mini-swe-agent venv or the pinned SWE-bench Verified parquet is absent')
    sources = {rel: hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() for rel in P.SOURCES}
    binding, problems = P.A.compute_binding(P.A.Layout(ROOT))
    assert problems == []
    runtime = {k: binding['runtime'][k] for k in ('sdk_traced_files', 'mini_swe_agent_sources')}
    work = tmp_path_factory.mktemp('req011_entry')
    return {name: run_scenario(work / name, name, sources, runtime) for name in SCENARIOS}


def run_frozen(base, name):
    """The same stub script through the frozen yaml-v1 driver (pilot_episode.main, unedited) via the unedited REQ-005
    harness in mode 'frozen'."""
    home, _ = workspace(base)
    run_dir = base / 'run'
    run_dir.mkdir()
    now = time.time()
    argv = ['--instance', IID, '--backend', 'large', '--port', '8293', '--alias', LARGE_ALIAS, '--run-dir', str(run_dir),
            '--run-id', 'frozen-reference-' + name, '--expected-image', FAKE_IMAGE, '--served',
            json.dumps(dict(model_file='fixture.gguf', model_sha256=LARGE_SHA)), '--episode-deadline',
            repr(now + 600.0), '--block-deadline', repr(now + 3000.0)]
    config = dict(mode='frozen', out=str(base / 'out'), script=SCENARIOS[name]['script'], alias=LARGE_ALIAS,
                  model_file='fixture.gguf', frozen_module_dir=str(ROOT / 'experiments/v2_agent'), argv=argv)
    (base / 'config.json').write_text(json.dumps(config))
    env = {k: v for k, v in os.environ.items()
           if not k.lower().endswith('_proxy') and not k.startswith(('LITELLM_', 'EXPERIMENTAL_OPENAI', 'MSWEA_'))}
    env.update(HOME=str(home), LITELLM_LOCAL_MODEL_COST_MAP='True', MSWEA_SILENT_STARTUP='1',
               MSWEA_GLOBAL_CONFIG_DIR=str(base / 'mswea_config'))
    proc = subprocess.run([str(MSWEA_PY), str(FROZEN_HARNESS), str(base / 'config.json')], capture_output=True,
                          text=True, env=env, timeout=600, cwd=str(base))
    assert proc.returncode == 0, proc.stderr[-4000:]
    return dict(harness=json.loads((base / 'out' / 'harness.json').read_text()), run_dir=run_dir,
                bodies=[p.read_bytes() for p in sorted((base / 'out' / 'terminal').glob('*.body'))])


@pytest.fixture(scope='module')
def frozen_runs(entry_runs, tmp_path_factory):
    work = tmp_path_factory.mktemp('req011_frozen')
    return {name: run_frozen(work / name, name) for name in PARITY}


def records(result, name):
    return json.loads((result['run_dir'] / name).read_text())


def messages(run_dir):
    return [(m['role'], m['content']) for m in json.loads((run_dir / 'trajectory.json').read_text())['messages']]


def effective(run_dir):
    """constructor_arguments and resolved of effective_config.json; the fake docker path (per-scenario HOME) is the
    only field allowed to differ and is replaced by a placeholder after checking its shape."""
    cfg = json.loads((run_dir / 'effective_config.json').read_text())
    out = {}
    for part in ('constructor_arguments', 'resolved'):
        section = json.loads(json.dumps(cfg[part]))
        assert section['environment']['executable'].endswith('/home/.local/dtr-runtime/bin/docker')
        section['environment']['executable'] = '<fixture HOME>/.local/dtr-runtime/bin/docker'
        out[part] = section
    return out


@pytest.mark.parametrize('name', PARITY)
def test_the_entry_sends_byte_identical_requests_to_the_frozen_yaml_v1_driver(entry_runs, frozen_runs, name):
    r, f = entry_runs[name], frozen_runs[name]
    assert (f['harness']['mode'], f['harness']['exit_code'], f['harness']['network_attempts']) == ('frozen', 0, [])
    assert r['harness']['exit_code'] == 0
    assert len(r['bodies']) == dict(submitted=3, retry=4, unsubmitted=3)[name]
    assert r['bodies'] == f['bodies']                                                    # byte for byte
    ours, frozen = records(r, 'episode.json'), json.loads((f['run_dir'] / 'episode.json').read_text())
    assert (ours['exit_status'], ours['physical_requests']) == (frozen['exit_status'], frozen['physical_requests'])
    assert messages(r['run_dir']) == messages(f['run_dir'])
    assert (r['run_dir'] / 'submission.diff').read_bytes() == (f['run_dir'] / 'submission.diff').read_bytes()
    assert effective(r['run_dir']) == effective(f['run_dir'])


def test_the_effective_configuration_is_the_frozen_yaml_v1_one(entry_runs):
    cfg = effective(entry_runs['submitted']['run_dir'])
    for part in ('constructor_arguments', 'resolved'):
        agent, model, environment = (cfg[part][k] for k in ('agent', 'model', 'environment'))
        assert (agent['step_limit'], agent['cost_limit'], agent['wall_time_limit_seconds']) == (24, 0.0, 1800)
        assert model['model_kwargs'] == dict(drop_params=True, api_base='http://127.0.0.1:8293/v1', api_key='none',
                                             temperature=0.0, max_tokens=1536, timeout=900, num_retries=0)
        assert model['model_name'] == 'openai/' + LARGE_ALIAS
        assert (environment['timeout'], environment['image'], environment['cwd'], environment['run_args']) == (
            60, PIN, '/testbed', ['--rm', '--platform', 'linux/amd64'])
    assert cfg['resolved']['environment']['forward_env'] == []
    raw = records(entry_runs['submitted'], 'effective_config.json')
    assert (raw['configuration_binding'], raw['mini_swe_agent'], raw['default_yaml_sha256']) == (
        'yaml-v1', '04d809ceab9df28f9adaed044884180159172930',
        '112aa58328f478a41cc2630702a4b89ef459e912870e05065157ed221f56701f')


def test_entry_submitted_episode_runs_baseline_with_receipts_and_all_exit_capture(entry_runs):
    r = entry_runs['submitted']
    assert (r['harness']['exit_code'], r['harness']['network_attempts']) == (0, [])
    assert json.loads((r['control'] / 'entry_admitted.json').read_text())['admitted'] is True
    ep = records(r, 'episode.json')
    assert (ep['exit_status'], ep['arm'], ep['logical_calls'], ep['physical_requests']) == ('Submitted', 'baseline', 3, 3)
    assert (r['run_dir'] / 'submission.diff').read_bytes() == MOD_NEW_DIFF
    assert ep['submission_sha256'] == MOD_NEW_SHA and ep['binding_sha256'] == MANIFEST_SHA
    assert all(CUE_TEXT not in body for body in r['bodies']) and len(r['bodies']) == 3
    assert records(r, 'cue_delivery.json')['cue_emissions'] == 0
    diag = records(r, 'exit_diagnostic.json')
    assert diag['exit_status'] == 'Submitted' and diag['endpoint']['graded'] is False
    terminal = records(r, 'terminal_phase.json')
    assert (terminal['cleanup']['state'], terminal['endpoint_check_after_cleanup']['state']) == ('returned', 'unchanged')
    assert sorted(p.name for p in (r['run_dir'] / 'receipts').iterdir()) == [
        'call00%d_attempt01.%s.json' % (n, kind) for n in (1, 2, 3) for kind in ('outcome', 'request')]
    assert [(r['private'] / ('call%03d_attempt01.request.raw' % n)).read_bytes() for n in (1, 2, 3)] == r['bodies']
    facts = P.episode_facts(r['run_dir'], r['run_id'], root=r['private'].parents[3])
    assert (facts['eligible'], facts['call9_reached'], facts['receipts_completeness']['complete']) == (True, False, True)
    assert (facts['server_reported_tokens']['prompt_tokens'], facts['server_reported_tokens']['completion_tokens'],
            facts['server_reported_tokens']['outcomes_with_unknown_usage']) == (101 + 102 + 103, 30, 0)


def test_entry_unsubmitted_episode_writes_an_empty_submission_and_captures_the_workspace(entry_runs):
    r = entry_runs['unsubmitted']
    assert (r['harness']['exit_code'], r['harness']['network_attempts']) == (0, [])
    ep = records(r, 'episode.json')
    assert ep['exit_status'] not in (None, 'Submitted') and (ep['logical_calls'], ep['physical_requests']) == (2, 3)
    assert (r['run_dir'] / 'submission.diff').read_bytes() == b''                  # no salvage
    diag = records(r, 'exit_diagnostic.json')
    assert diag['changes_observed'] is True and diag['sections']['diff']['state'] == 'captured'
    assert records(r, 'terminal_phase.json')['cleanup']['state'] == 'returned'
    facts = P.episode_facts(r['run_dir'], r['run_id'], root=r['private'].parents[3])
    assert facts['eligible'] is False and facts['submission_nonempty'] is False


def test_entry_sigalrm_deadline_mid_inference_ends_in_episode_deadline_with_capture_and_cleanup(entry_runs):
    r = entry_runs['deadline']
    assert (r['harness']['exit_code'], r['harness']['network_attempts']) == (0, [])
    ep = records(r, 'episode.json')
    assert ep['exit_status'] == 'EpisodeDeadline'
    assert (r['run_dir'] / 'submission.diff').read_bytes() == b''
    diag = records(r, 'exit_diagnostic.json')
    assert diag['exit_status'] == 'EpisodeDeadline' and diag['sections']['tree']['state'] == 'captured'
    terminal = records(r, 'terminal_phase.json')
    assert (terminal['cleanup']['state'], terminal['cleanup']['reserve_intact']) == ('returned', True)
    assert ep['receipt_integrity']['deadline_reached'] is True
    assert len(r['bodies']) == 2                                                    # the second send was cut


def test_entry_refuses_a_cue_arm_and_an_occupied_run_dir_before_any_work(entry_runs):
    r = entry_runs['refused']
    assert r['harness']['exit_code'] == 3 and r['bodies'] == []
    reasons = json.loads((r['control'] / 'entry_refused.json').read_text())['reasons']
    assert "arm 'cue': DTR-REQ-011 runs the baseline arm only (no cue)" in reasons
    assert 'run_dir must exist, be a real directory and be empty' in reasons
    assert sorted(p.name for p in r['run_dir'].iterdir()) == ['leftover.txt']
    assert not (r['state'] / 'calls.log').exists()                                 # no docker command


def test_entry_refuses_changed_sources_and_a_non_manifest_assignment_before_any_work(entry_runs):
    r = entry_runs['tampered']
    assert r['harness']['exit_code'] == 3 and r['bodies'] == [] and r['harness']['network_attempts'] == []
    reasons = json.loads((r['control'] / 'entry_refused.json').read_text())['reasons']
    assert 'running cue_transport.py is not the admitted source' in reasons
    assert 'running req011_entry.py is not the admitted source' in reasons
    assert 'sources changed since admission: %s' % list(TAMPERED) in reasons
    assert ('the assignment (id, order, backend, port, alias, model sha256) is not a manifest assignment'
            in reasons)                                                       # port 8291 for the large model
    assert not (r['control'] / 'entry_admitted.json').exists() and list(r['run_dir'].iterdir()) == []
    assert not (r['state'] / 'calls.log').exists()                                 # no docker command


def test_entry_request_budget_chains_from_counted_before_and_refuses_past_the_pair_cap(entry_runs):
    r = entry_runs['budget']
    assert (r['harness']['exit_code'], r['harness']['network_attempts']) == (0, [])
    assert len(r['bodies']) == 2                                                    # 94 counted before + 2 = 96
    ep = records(r, 'episode.json')
    assert ep['physical_requests'] == 2 and ep['exit_status'] != 'Submitted'
    sends = [json.loads((r['run_dir'] / 'receipts' / ('call%03d_attempt01.request.json' % n)).read_text())['send']
             for n in (1, 2)]
    assert [(x['cohort_request_ordinal'], x['cohort_request_limit']) for x in sends] == [(95, 96), (96, 96)]
    assert not (r['run_dir'] / 'receipts' / 'call003_attempt01.request.json').exists()
