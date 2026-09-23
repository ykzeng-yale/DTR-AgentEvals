"""DTR-REQ-005 cue-v1 integrated acceptance fixtures (lead contract docs/theory_feedback_20260923_req005_review.md,
"Concrete integration contract", bullet "Acceptance artifact").

NO model, llama-server, container or network. Each episode runs in the pinned mini-swe-agent interpreter through
experiments/tools/v2_cue_integration_harness.py, which executes an UNMODIFIED driver main():

  * the pinned reference: the frozen experiments/v2_agent/pilot_episode.py of this checkout, main() itself, with
    litellm's own default client (nothing re-implemented);
  * the cue-v1 driver: cue_episode.py of a disposable copy of the bound inputs (v2_cue_tree_fixture.py), launched by
    cue_runner.run_queue under cue_admission, so every episode passes the real admission first.

Both see the SAME stand-ins: a scripted in-process sender at httpx.HTTPTransport.handle_request (the terminal the
frozen default client and the capture's inner transport both reach), a fixed /props answer, a fake `docker`
executable that runs the scripted fixture commands (and the frozen capture commands) in a disposable temporary Git
repository created here, and a fixed free-space answer. The scripted commands are this file's own; no
benchmark-generated code is executed.

Every expected value is written out by hand as a literal (bodies' inserted bytes, the cue, digests, call ids, states,
reasons, the Submitted-only diff). The digests of the diff and the cue were produced with `shasum -a 256` over the
literal bytes, and the diff's blob ids with `git hash-object`, never through the modules under test. The only derived
positions are byte offsets located in the frozen driver's own recorded bodies, which is what the comparison is about.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'experiments/v2_agent'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import cue_admission as A  # noqa: E402
import cue_runner as CR  # noqa: E402
import cue_transport as CT  # noqa: E402
import v2_cue_tree_fixture as TREE  # noqa: E402

MSWEA_PY = REPO / 'work/venvs/minisweagent_04d809c/bin/python'
HARNESS = REPO / 'experiments/tools/v2_cue_integration_harness.py'
TREE_OK, TREE_REASON = TREE.available()
pytestmark = [
    pytest.mark.skipif(not MSWEA_PY.exists(), reason='pinned mini-swe-agent venv work/venvs/minisweagent_04d809c is '
                                                     'absent; the integrated driver runs only on its pinned SDK'),
    pytest.mark.skipif(not TREE_OK, reason=TREE_REASON or ''),
]

# ---------------------------------------------------------------- hand-written literals

CUE_TEXT = ('Recent actions returned the same visible feedback repeatedly. Use the existing /testbed checkout. '
            'Choose a different action that will provide useful new evidence, or explain why repeating the action '
            'is necessary. Check the current working directory and the existing submission instructions.')
CUE_SHA256 = '80d52625bd593cd6fecafeb06daca898792979592272d9fadcf0ddd04bd39d9e'
CUE_INSERTION = b',{"role":"user","content":"' + CUE_TEXT.encode() + b'"}'          # 1 + 26 + 290 + 2 = 319 bytes
OBSERVATION_LS = (b'{"role":"user","content":"<returncode>0</returncode>\\n<output>\\nkeep.py\\nmod.py\\n'
                  b'</output>"}')
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
MOD_NEW_SHA = '27788b1f35a18178bf79d7f78cd17bbe50897761c99112455ec5abce4467335b'      # 379 bytes
EMPTY_SHA = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
CONTAINER_ID = 'c' * 64
RESERVE = 1073741824                                                                # 1 GiB, declared for fixtures
PSF_SMALL_ALIAS = 'qwen2.5-coder-7b-instruct-c03e6d3-q4_k_m'
PSF_IMAGE = 'sha256:d461c7c6e50916d9837e81604d8e79efca06af9c063f5477b0086102a96b50cf'
NO_OBSERVATION = ('the parsed action produced no ordinary observation (the episode ended on it, e.g. Submitted, or '
                  'the executor raised)')
FORMAT_ERROR = 'the logical call returned a FormatError: no parsed action and no ordinary observation'


def act(command):
    return dict(content='THOUGHT: next step\n\n```mswea_bash_command\n%s\n```' % command)


EDIT = act("printf 'x = 2\\n' > mod.py && printf 'n = 1\\n' > new_file.py")
SUBMIT = act('echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT')
LS = act('ls')
NO_ACTION = dict(content='THOUGHT: I will think about it without a command block.')
SCENARIOS = {
    'base': dict(script=[LS, LS, LS, EDIT, SUBMIT]),
    'format_error': dict(script=[LS, LS, NO_ACTION, LS, LS, LS, EDIT, SUBMIT]),
    'retry': dict(script=[LS, LS, LS, dict(status=500), EDIT, SUBMIT]),
    'horizon': dict(script=[act('echo s%02d' % i) for i in range(1, 22)] + [LS, LS, LS]),
    'hang': dict(script=[LS, SUBMIT], docker='hang_on_status'),
    'capture_error': dict(script=[LS, SUBMIT], docker='garbage_diagnostic'),
    'storage': dict(script=[LS, SUBMIT], disk=dict(low_after_sends=0)),
    'cue_refused': dict(script=[LS, LS, LS, EDIT, SUBMIT], disk=dict(low_after_sends=3)),
    'abort': dict(script=[LS, {'raise': 'KeyboardInterrupt'}]),
}
# position -> scenario, in the frozen order (1 baseline, 2 cue, 3 cue, 4 baseline, 5 cue, 6 baseline, 7 baseline,
# 8 cue, 9 baseline, 10 cue, 11 cue)
PLAN = {1: 'base', 2: 'base', 3: 'format_error', 4: 'capture_error', 5: 'retry', 6: 'hang', 7: 'storage',
        8: 'cue_refused', 9: 'base', 10: 'horizon', 11: 'abort'}

FAKE_DOCKER = r'''#!/bin/bash
# fake docker for DTR-REQ-005 cue-v1 integration fixtures: no container; commands run in a disposable Git repo
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
    if [ -f "$STATE/hang_on_status" ] && [[ "$cmd" == *"status --porcelain"* ]]; then
      echo $$ > "$STATE/hang_leader.pid"
      (trap '' TERM; sleep 300) &
      echo $! > "$STATE/hang_child.pid"
      trap '' TERM
      wait
      exit 0
    fi
    if [ -f "$STATE/garbage_diagnostic" ] && [[ "$cmd" == *"head -c"* ]]; then
      echo "fixture: not what the capture expects"
      exit 0
    fi
    cd "$REPO" && exec env "${envs[@]}" "${interp[@]}" "$cmd"
    ;;
esac
exit 2
'''


# ---------------------------------------------------------------- building blocks

def git(repo, *args):
    env = dict(os.environ, GIT_AUTHOR_DATE='2026-09-23T00:00:00Z', GIT_COMMITTER_DATE='2026-09-23T00:00:00Z')
    return subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True, text=True, env=env)


def workspace(base, image_id, docker_mode=None):
    """A disposable Git repository standing in for /testbed, and a HOME whose fake docker runs commands in it."""
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
    (state / 'image_id').write_text(image_id + '\n')
    (state / 'container_id').write_text(CONTAINER_ID + '\n')
    if docker_mode:
        (state / docker_mode).write_text('1\n')
    return home, state


def run_harness(base, config, home):
    base.mkdir(parents=True, exist_ok=True)
    (base / 'config.json').write_text(json.dumps(config))
    env = {k: v for k, v in os.environ.items()
           if not k.lower().endswith('_proxy') and not k.startswith(('LITELLM_', 'EXPERIMENTAL_OPENAI', 'MSWEA_'))}
    env.update(HOME=str(home), LITELLM_LOCAL_MODEL_COST_MAP='True', MSWEA_SILENT_STARTUP='1',
               MSWEA_GLOBAL_CONFIG_DIR=str(base / 'mswea_config'))
    started = time.monotonic()
    proc = subprocess.run([str(MSWEA_PY), str(HARNESS), str(base / 'config.json')], capture_output=True, text=True,
                          env=env, timeout=900, cwd=str(base))
    out = Path(config['out'])
    result = dict(returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr[-6000:],
                  seconds=time.monotonic() - started, out=out)
    if (out / 'harness.json').exists():
        result['harness'] = json.loads((out / 'harness.json').read_text())
        result['bodies'] = [p.read_bytes() for p in sorted((out / 'terminal').glob('*.body'))]
        result['received'] = [json.loads(line) for line in (out / 'terminal.jsonl').read_text().splitlines()]
    return result


def driver_argv(*, instance, backend, port, alias, run_dir, run_id, image, extra=()):
    now = time.time()
    return ['--instance', instance, '--backend', backend, '--port', str(port), '--alias', alias,
            '--run-dir', str(run_dir), '--run-id', run_id, '--expected-image', image,
            '--served', json.dumps({'file': 'fixture.gguf'}), '--episode-deadline', repr(now + 1500.0),
            '--block-deadline', repr(now + 3000.0)] + list(extra)


def cue_argv(row, context):
    return driver_argv(instance=row['instance_id'], backend=row['backend'], port=row['port'], alias=row['model_alias'],
                       run_dir=context['run_dir'], run_id=context['run_id'], image=row['image_id'],
                       extra=['--arm', row['arm'], '--position', str(row['position']),
                              '--counted-before', str(context['counted_physical_requests_before']),
                              '--request-limit', str(context['assignment_request_limit']),
                              '--host-reserve-bytes', str(RESERVE)])


def messages(run_dir):
    return [(m['role'], m['content']) for m in json.loads((Path(run_dir) / 'trajectory.json').read_text())['messages']]


def nth_end(data, needle, n):
    """Byte offset just after the n-th occurrence of `needle` in `data`."""
    at = -1
    for _ in range(n):
        at = data.index(needle, at + 1)
    return at + len(needle)


def gone(pid, within=5.0):
    end = time.monotonic() + within
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        if time.monotonic() >= end:
            return False
        time.sleep(0.02)


# ---------------------------------------------------------------- one integrated run, shared by every fixture

@pytest.fixture(scope='module')
def run(tmp_path_factory):
    work = tmp_path_factory.mktemp('cue_integration')
    results = dict(work=work, positions={})
    # 1. the pinned reference: the frozen driver itself, same scenario, same stand-ins
    home, state = workspace(work / 'frozen', PSF_IMAGE)
    run_dir = work / 'frozen' / 'run'
    run_dir.mkdir()
    results['frozen'] = run_harness(work / 'frozen', dict(
        mode='frozen', out=str(work / 'frozen' / 'out'), script=SCENARIOS['base']['script'], alias=PSF_SMALL_ALIAS,
        model_file='fixture.gguf', frozen_module_dir=str(REPO / 'experiments/v2_agent'),
        argv=driver_argv(instance='psf__requests-1142', backend='small', port=8291, alias=PSF_SMALL_ALIAS,
                         run_dir=run_dir, run_id='frozen-reference', image=PSF_IMAGE)), home)
    results['frozen'].update(run_dir=run_dir, state=state)
    # 2. a disposable copy of the bound inputs; the cue driver refuses to run before any launch
    tree = TREE.build(work / 'tree')
    layout = A.Layout(tree)
    results.update(tree=tree, layout=layout)
    home, state = workspace(work / 'unlaunched', PSF_IMAGE)
    (work / 'unlaunched' / 'run').mkdir()
    row = dict(instance_id='psf__requests-1142', backend='small', port=8291, model_alias=PSF_SMALL_ALIAS,
               image_id=PSF_IMAGE, arm='baseline', position=1)
    context = dict(run_dir=work / 'unlaunched' / 'run', run_id='psf__requests-1142__small__cue-v1__baseline__run-'
                   '20260923T000000Z-abcdef', counted_physical_requests_before=0, assignment_request_limit=48)
    results['unlaunched'] = run_harness(work / 'unlaunched', dict(
        mode='cue', out=str(work / 'unlaunched' / 'out'), script=SCENARIOS['base']['script'], alias=PSF_SMALL_ALIAS,
        model_file='fixture.gguf', module_dir=str(tree / 'experiments/v2_agent'), argv=cue_argv(row, context)), home)
    results['unlaunched']['state'] = state
    results['held'] = run_harness(work / 'held', dict(
        mode='cue', out=str(work / 'held' / 'out'), script=[], alias=PSF_SMALL_ALIAS, model_file='fixture.gguf',
        module_dir=str(tree / 'experiments/v2_agent'), argv=[], call_run_assignment=True), home)

    # 3. the integrated queue: runner -> admission -> cue_episode, position by position
    def episode(row, context):
        name = PLAN[row['position']]
        scenario = SCENARIOS[name]
        base = work / ('pos%02d_%s' % (row['position'], name))
        home, state = workspace(base, row['image_id'], scenario.get('docker'))
        config = dict(mode='cue', out=str(base / 'out'), script=scenario['script'], alias=row['model_alias'],
                      model_file='fixture.gguf', module_dir=str(tree / 'experiments/v2_agent'),
                      argv=cue_argv(row, context), disk=dict(scenario.get('disk') or {}, reserve=RESERVE))
        result = run_harness(base, config, home)
        result.update(run_dir=Path(context['run_dir']), state=state, scenario=name, row=dict(row),
                      context={k: v for k, v in context.items() if k != 'budget'})
        results['positions'][row['position']] = result
        episode_record = json.loads((Path(context['run_dir']) / 'episode.json').read_text())
        result['episode'] = episode_record
        return dict(physical_requests=episode_record['physical_requests'],
                    storage_integrity=episode_record['storage_integrity'],
                    storage_integrity_detail=episode_record['storage_integrity_detail'],
                    exit_status=episode_record['exit_status'], run_id=context['run_id'])
    results['session1'] = CR.run_queue(episode, layout=layout, fixture=True)
    A.record_reconciliation(layout, 'integrity-7', 'fixture: the storage refusal was inspected; nothing was sent')
    results['session2'] = CR.run_queue(episode, layout=layout, fixture=True)
    A.record_reconciliation(layout, 'integrity-8', 'fixture: the refused cue request was inspected; nothing was sent')
    results['session3'] = CR.run_queue(episode, layout=layout, fixture=True,
                                       gate=lambda r: 'fixture: hold after position 11' if r['position'] == 12 else None)
    results['ledger'] = [json.loads(line) for line in layout.ledger_path.read_bytes().split(b'\n')[:-1]]
    # 4. corrupt-receipt detection at resume, then the exact bytes restored
    results['validate_clean'] = A.validate_queue(layout)
    outcome = next((results['positions'][1]['run_dir'] / 'receipts').glob('call001_attempt01.outcome.json'))
    original = outcome.read_bytes()
    outcome.write_bytes(original.replace(b'"outcome": "ok"', b'"outcome": "OK"', 1))
    try:
        A.validate_queue(layout)
        results['validate_corrupt'] = None
    except A.AdmissionRefused as exc:
        results['validate_corrupt'] = exc.reasons
    results['store_corrupt'] = CT.read_only_completeness(
        tree / A.PRIVATE_RECEIPTS_REL / results['positions'][1]['run_dir'].name, outcome.parent, cohort='cue-v1',
        run_id=results['positions'][1]['run_dir'].name)
    outcome.write_bytes(original)
    results['validate_restored'] = A.validate_queue(layout)
    return results


def pos(run, position):
    result = run['positions'][position]
    assert result['returncode'] == 0, result['stderr']
    return result


def delivery(result):
    return json.loads((result['run_dir'] / 'cue_delivery.json').read_text())


def terminal_record(result):
    return json.loads((result['run_dir'] / 'terminal_phase.json').read_text())


# ---------------------------------------------------------------- the runs themselves

def test_every_episode_ran_on_the_pinned_stack_with_no_network_and_through_admission(run):
    frozen = run['frozen']
    assert frozen['returncode'] == 0, frozen['stderr']
    assert frozen['harness']['versions'] == {'litellm': '1.102.0', 'openai': '2.54.0', 'httpx': '0.28.1',
                                             'tenacity': '9.1.4', 'mini-swe-agent': '2.4.6'}
    assert sorted(run['positions']) == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    for position, result in sorted(run['positions'].items()):
        assert result['returncode'] == 0, (position, result['stderr'])
        expected_code = dict(raised='KeyboardInterrupt', detail='fixture operator abort inside the send') \
            if position == 11 else 0
        assert result['harness']['exit_code'] == expected_code and result['harness']['network_attempts'] == [], position
        admission = json.loads((result['run_dir'] / 'admission.json').read_text())
        assert (admission['admitted'], admission['position'], admission['arm']) == (True, position,
                                                                                    result['row']['arm'])
    assert frozen['harness']['network_attempts'] == []
    assert [s['dispatched'] for s in (run['session1'], run['session2'], run['session3'])] == [
        [1, 2, 3, 4, 5, 6, 7], [8], [9, 10, 11]]
    assert [s['stop']['code'] for s in (run['session1'], run['session2'], run['session3'])] == [
        'storage_integrity_unresolved', 'storage_integrity_unresolved', 'host_gate']


def test_the_driver_does_nothing_unless_the_whole_queue_is_admitted(run):
    refused = run['unlaunched']
    assert (refused['harness']['exit_code'], refused['harness']['received']) == (3, 0)
    assert json.loads(refused['stderr'].strip().splitlines()[-1]) == dict(
        admitted=False, run_id='psf__requests-1142__small__cue-v1__baseline__run-20260923T000000Z-abcdef',
        reasons=['results/v2_agent/pilot_20260923_cue_v1 has not been launched: an episode runs only inside a '
                 'runner session'])
    assert not (refused['state'] / 'calls.log').exists()                # no docker command, no container
    assert sorted(p.name for p in (run['work'] / 'unlaunched' / 'run').iterdir()) == []
    held = run['held']['harness']['exit_code']
    assert held == dict(live_release_held='cue-v1 live release is held by the lead (docs/theory_feedback_20260923_'
                                          'req005_review.md): no host/server step exists here, and no episode is '
                                          'launched for fixture-row')


# ---------------------------------------------------------------- (a) baseline equals the pinned frozen path

def test_a_baseline_request_bodies_headers_and_model_visible_messages_equal_the_frozen_driver(run):
    frozen, baseline = run['frozen'], pos(run, 1)
    assert len(frozen['bodies']) == len(baseline['bodies']) == 5
    assert baseline['bodies'] == frozen['bodies']                           # byte-identical, request by request
    assert [(r['headers'], r['timeout'], r['url']) for r in baseline['received']] == \
        [(r['headers'], r['timeout'], r['url']) for r in frozen['received']]
    assert [r['transport'] for r in baseline['received']] == ['HTTPTransport'] * 5 == \
        [r['transport'] for r in frozen['received']]
    assert messages(baseline['run_dir']) == messages(frozen['run_dir'])
    assert CUE_TEXT.encode() not in b''.join(baseline['bodies'])
    # the same silent landmark the cue arm acts on
    landmark = delivery(baseline)
    assert (landmark['state'], landmark['pattern'], landmark['trigger_call_id'], landmark['planned_delivery_call_id'],
            landmark['baseline_landmark_call_reached'], landmark['message_appended'], landmark['cue_emissions']) == (
        'baseline_silent_landmark', 'AAA', 3, 4, 4, False, 0)
    # each physical send reached the sender exactly as it was retained privately before dispatch
    private = run['tree'] / A.PRIVATE_RECEIPTS_REL / baseline['run_dir'].name
    assert [(private / ('call%03d_attempt01.request.raw' % n)).read_bytes() for n in range(1, 6)] == baseline['bodies']


# ---------------------------------------------------------------- (b) the cue arm differs only at the insertion

def test_b_the_cue_arm_differs_from_baseline_only_by_the_one_inserted_cue_message(run):
    frozen, cue = run['frozen'], pos(run, 2)
    assert cue['bodies'][:3] == frozen['bodies'][:3]                        # before the delivery call: identical
    for number in (4, 5):                                                   # from the delivery call on: one insertion
        reference = frozen['bodies'][number - 1]
        at = nth_end(reference, OBSERVATION_LS, 3)                          # right after the third `ls` observation
        assert cue['bodies'][number - 1] == reference[:at] + CUE_INSERTION + reference[at:]
        assert len(cue['bodies'][number - 1]) - len(reference) == 319
        assert cue['bodies'][number - 1].count(CUE_TEXT.encode()) == 1
    frozen_messages, cue_messages = messages(frozen['run_dir']), messages(cue['run_dir'])
    assert cue_messages == frozen_messages[:8] + [('user', CUE_TEXT)] + frozen_messages[8:]
    record = delivery(cue)
    assert {k: record[k] for k in ('state', 'pattern', 'trigger_call_id', 'pattern_call_ids',
                                   'planned_delivery_call_id', 'message_appended', 'message_appended_call_id',
                                   'message_index', 'transport_attempted', 'response_received', 'cue_http_statuses',
                                   'cue_send_attempt_keys', 'cue_emissions', 'cue_sha256', 'cue_role')} == dict(
        state='response_received', pattern='AAA', trigger_call_id=3, pattern_call_ids=[1, 2, 3],
        planned_delivery_call_id=4, message_appended=True, message_appended_call_id=4, message_index=8,
        transport_attempted=True, response_received=True, cue_http_statuses=[200],
        cue_send_attempt_keys=['call004_attempt01'], cue_emissions=1, cue_sha256=CUE_SHA256, cue_role='user')
    trajectory = json.loads((cue['run_dir'] / 'trajectory.json').read_text())['messages']
    assert trajectory[8]['extra'] == dict(cue_v1=dict(request='DTR-REQ-005', cue_sha256=CUE_SHA256, delivery_call_id=4,
                                                      trigger_call_id=3, pattern='AAA'))


# ---------------------------------------------------------------- (c) parse-failure, retry and horizon boundaries

def test_c_a_format_error_breaks_adjacency_and_the_cue_waits_for_three_new_repeats(run):
    result = pos(run, 3)
    bodies = result['bodies']
    assert len(bodies) == 8
    assert [CUE_TEXT.encode() in body for body in bodies] == [False] * 6 + [True, True]
    record = delivery(result)
    assert (record['pattern'], record['trigger_call_id'], record['pattern_call_ids'], record['message_appended_call_id'],
            record['state'], record['logical_calls'], record['records_fed']) == (
        'AAA', 6, [4, 5, 6], 7, 'response_received', 8, 8)
    assert record['incomplete_records'] == [dict(call_id=3, reason=FORMAT_ERROR),
                                            dict(call_id=8, reason=NO_OBSERVATION)]
    calls = [json.loads(line) for line in (result['run_dir'] / 'calls.jsonl').read_text().splitlines()]
    assert [(c['event'], c['call']) for c in calls if c['event'] in ('format_error', 'cue_appended')] == [
        ('format_error', 3), ('cue_appended', 7)]


def test_c_a_physical_retry_resends_the_same_single_cue_and_consumes_no_second_one(run):
    result = pos(run, 5)
    bodies = result['bodies']
    assert len(bodies) == 6
    assert bodies[3] == bodies[4]                                           # the retry re-sends the same bytes
    assert [body.count(CUE_TEXT.encode()) for body in bodies] == [0, 0, 0, 1, 1, 1]
    record = delivery(result)
    assert (record['message_appended_call_id'], record['cue_send_attempt_keys'], record['cue_http_statuses'],
            record['cue_emissions'], record['state']) == (
        4, ['call004_attempt01', 'call004_attempt02'], [500, 200], 1, 'response_received')
    attempts = [json.loads(line) for line in (result['run_dir'] / 'attempts.jsonl').read_text().splitlines()]
    assert [(a['call'], a['attempt'], a['event'], a.get('ok')) for a in attempts if a['call'] == 4] == [
        (4, 1, 'start', None), (4, 1, 'result', False), (4, 2, 'start', None), (4, 2, 'result', True)]
    receipts = sorted(p.name for p in (result['run_dir'] / 'receipts').iterdir())
    assert 'call004_attempt01.request.json' in receipts and 'call004_attempt02.request.json' in receipts
    assert result['episode']['physical_requests'] == 6


def test_c_a_trigger_on_the_final_h24_call_stays_explicitly_undelivered(run):
    result = pos(run, 10)
    assert len(result['bodies']) == 24
    assert not any(CUE_TEXT.encode() in body for body in result['bodies'])
    record = delivery(result)
    assert (record['state'], record['trigger_call_id'], record['pattern_call_ids'], record['planned_delivery_call_id'],
            record['message_appended'], record['cue_emissions'], record['logical_calls']) == (
        'trigger_without_next_call', 24, [22, 23, 24], None, False, 0, 24)
    assert record['reason'] == ('no next normally budgeted model call remains: trigger on call 24 of horizon H=24; '
                                'trigger recorded without delivery and no cue text is handed out')
    assert (result['episode']['exit_status'], result['episode']['submission_sha256']) == ('LimitsExceeded', EMPTY_SHA)


def test_c_a_pre_dispatch_storage_refusal_after_insertion_is_not_delivery(run):
    result = pos(run, 8)
    assert len(result['bodies']) == 3                                       # the cue request never left
    record = delivery(result)
    assert (record['state'], record['message_appended'], record['message_appended_call_id'],
            record['transport_attempted'], record['response_received'], record['cue_send_attempt_keys']) == (
        'message_appended', True, 4, False, False, [])
    assert record['reason'] == ('the cue message was appended, but no physical request carrying it was sent (for '
                                'example a pre-dispatch storage refusal or the deadline): not delivered to the model')
    refusal = json.loads((result['run_dir'] / 'receipts' / 'refusal001.refusal.json').read_text())['refusal']
    assert (refusal['reason_code'], refusal['logical_call_id'], refusal['physical_request']) == (
        'insufficient_free_space', 4, False)
    assert result['episode']['exit_status'] == 'InfrastructureStop'


# ---------------------------------------------------------------- (d) hung executor: bounded and actually gone

def test_d_a_hung_diagnostic_executor_is_killed_at_its_bound_and_its_processes_are_gone(run):
    result = pos(run, 6)
    leader = int((result['state'] / 'hang_leader.pid').read_text())
    child = int((result['state'] / 'hang_child.pid').read_text())
    assert gone(leader) and gone(child)
    record = terminal_record(result)
    supervisor = record['supervisor']
    killed = [e for e in supervisor['log'] if e.get('outcome') == 'timeout_killed']
    assert len(killed) == 1 and killed[0]['kill_signal'] == 'SIGKILL' and killed[0]['kill_confirmed'] is True
    assert killed[0]['group_empty_confirmed'] is True and killed[0]['escaped_descendant_suspected'] is False
    assert killed[0]['binding'] == 'remaining_diagnostic_time' and killed[0]['timeout_s'] <= 30.0
    assert record['timing']['diagnostic_seconds'] < 32.0
    assert (record['cleanup']['state'], record['cleanup']['reserve_intact']) == ('returned', True)
    assert record['diagnostic']['section_states']['status'] == 'timeout'
    assert (result['episode']['exit_status'], result['episode']['submission_sha256']) == ('Submitted', EMPTY_SHA)


# ---------------------------------------------------------------- (e) cleanup still runs after capture errors

def test_e_cleanup_runs_after_a_diagnostic_capture_error_and_after_a_receipt_capture_stop(run):
    for position, exit_status in ((4, 'Submitted'), (7, 'InfrastructureStop'), (8, 'InfrastructureStop')):
        result = pos(run, position)
        record = terminal_record(result)
        assert record['steps'] == ['endpoint', 'diagnostic', 'cleanup'], position
        assert record['cleanup']['state'] == 'returned', position
        cleanup = json.loads((result['run_dir'] / 'container_cleanup.json').read_text())
        assert (cleanup['container_id'], cleanup['confirmed'], cleanup['state']) == (CONTAINER_ID, True, 'stopped')
        assert (result['state'] / 'calls.log').read_text().splitlines()[-2:] == ['stop --time', 'container inspect']
        assert result['episode']['exit_status'] == exit_status, position
    # an operator abort inside a send: the driver runs the terminal phase and its records, then re-raises
    aborted = pos(run, 11)
    record = terminal_record(aborted)
    assert (record['steps'], record['cleanup']['state'], aborted['episode']['exit_status']) == (
        ['endpoint', 'diagnostic', 'cleanup'], 'returned', 'KeyboardInterrupt')
    assert json.loads((aborted['run_dir'] / 'container_cleanup.json').read_text())['confirmed'] is True
    assert (aborted['state'] / 'calls.log').read_text().splitlines()[-2:] == ['stop --time', 'container inspect']
    capture_error = terminal_record(pos(run, 4))['diagnostic']
    assert capture_error['status'] != 'captured'
    assert [state for name, state in sorted(capture_error['section_states'].items()) if name != 'tree'] == [
        'failed', 'failed', 'failed']


# ---------------------------------------------------------------- (f) storage refusal before dispatch: zero sends

def test_f_a_storage_refusal_before_dispatch_sends_nothing_and_stops_the_queue(run):
    result = pos(run, 7)
    assert (result['harness']['received'], result['bodies'], result['episode']['physical_requests']) == (0, [], 0)
    assert sorted(p.name for p in (result['run_dir'] / 'receipts').iterdir()) == ['refusal001.refusal.json']
    refusal = json.loads((result['run_dir'] / 'receipts' / 'refusal001.refusal.json').read_text())['refusal']
    assert (refusal['reason_code'], refusal['classification'], refusal['infrastructure_stop'],
            refusal['physical_request'], refusal['dispatched_to_terminal'], refusal['body_truncated']) == (
        'insufficient_free_space', 'storage', True, False, False, False)
    private = run['tree'] / A.PRIVATE_RECEIPTS_REL / result['run_dir'].name
    assert sorted(p.name for p in private.iterdir()) == []                  # not even the raw body was kept
    assert (result['episode']['storage_integrity'], result['episode']['receipt_integrity']['stop_reason']) == (
        'unresolved', 'insufficient_free_space')
    stop = run['session1']['stop']
    assert (stop['code'], stop['affected']) == ('storage_integrity_unresolved', [dict(
        position=7, assignment_id='scikit-learn__scikit-learn-10297__large__cue-v1__baseline',
        state='terminal_integrity_unresolved')])


# ---------------------------------------------------------------- (g) corrupt-receipt detection

def test_g_a_corrupted_receipt_is_detected_and_refuses_the_resume(run):
    assert run['validate_clean']['blocking'] == [] and run['validate_restored']['next_position'] == 12
    reasons = run['validate_corrupt']
    assert len(reasons) == 1 and reasons[0].startswith(
        'the receipt set of clean terminal assignment 1 (%s) is no longer complete: ' % run['positions'][1]['run_dir'].name)
    assert 'ReceiptError: published projection digest mismatch: call001_attempt01.outcome.json' in reasons[0]
    store = run['store_corrupt']
    assert store['complete'] is False
    assert [r['file'] for r in store['invalid_records']] == ['call001_attempt01.outcome.json']
    for position in (1, 2, 3, 5, 9, 10):
        integrity = pos(run, position)['episode']['receipt_integrity']
        assert (integrity['receipt_integrity'], integrity['queue_may_continue']) == ('complete', True), position


# ---------------------------------------------------------------- (h) Submitted-only endpoint bytes unchanged

def test_h_the_submitted_only_endpoint_bytes_are_unchanged_by_instrumentation_and_by_the_cue(run):
    frozen_bytes = (run['frozen']['run_dir'] / 'submission.diff').read_bytes()
    assert frozen_bytes == MOD_NEW_DIFF
    for position in (1, 2, 3, 5, 9):
        result = pos(run, position)
        assert (result['run_dir'] / 'submission.diff').read_bytes() == MOD_NEW_DIFF, position
        assert (result['episode']['exit_status'], result['episode']['submission_sha256'],
                result['episode']['submission_bytes']) == ('Submitted', MOD_NEW_SHA, 379), position
        check = terminal_record(result)['endpoint_check_after_cleanup']
        assert (check['state'], check['file_sha256']) == ('unchanged', MOD_NEW_SHA), position
    frozen_episode = json.loads((run['frozen']['run_dir'] / 'episode.json').read_text())
    assert (frozen_episode['exit_status'], frozen_episode['submission_sha256']) == ('Submitted', MOD_NEW_SHA)
    # the diagnostic never wrote into the endpoint and is never graded
    diagnostic = json.loads((pos(run, 2)['run_dir'] / 'exit_diagnostic.json').read_text())
    assert diagnostic['endpoint'] == dict(writes_submission_diff=False, marks_submitted=False, graded=False,
                                          changes_eligibility=False, changes_endpoint_bytes=False,
                                          output_file='exit_diagnostic.json')


def test_the_ledger_records_every_episode_with_its_true_request_count(run):
    terminals = {e['position']: e for e in run['ledger'] if e['event'] == 'assignment_terminal'}
    assert {p: (terminals[p]['physical_requests_reported'], terminals[p]['request_accounting'],
                terminals[p]['storage_integrity']) for p in sorted(terminals)} == {
        1: (5, 'reported', 'resolved'), 2: (5, 'reported', 'resolved'), 3: (8, 'reported', 'resolved'),
        4: (2, 'reported', 'resolved'), 5: (6, 'reported', 'resolved'), 6: (2, 'reported', 'resolved'),
        7: (0, 'reported', 'unresolved'), 8: (3, 'reported', 'unresolved'), 9: (5, 'reported', 'resolved'),
        10: (24, 'reported', 'resolved'), 11: (2, 'reported', 'resolved')}
    sessions = [e['episode_function'] for e in run['ledger'] if e['event'] == 'session_start']
    assert sessions == ['fixture:run.<locals>.episode'] * 3
    # authoritative logical ids: one per model query, equal to the agent's own call count
    for position in sorted(run['positions']):
        episode = pos(run, position)['episode']
        assert episode['logical_calls'] == episode['n_model_calls'], position
        assert delivery(pos(run, position))['records_fed_call_ids_consecutive'] is True, position
