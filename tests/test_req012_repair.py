"""DTR-REQ-012 repair-probe fixtures (lead 40b4db2, docs/theory_feedback_20260924_req011_decision.md).

Covered: the yaml-v1-repair1 configuration and its manifest binding; the stall guard (the rule itself, and the real
DefaultAgent firing before the third query, or not firing); no egress and the effective configuration against the
frozen yaml-v1 driver; receipt and endpoint preservation; grading in a fresh evaluator container from the pinned
image; the gate expectations; the gate precondition of the probe; single-shot launches; the 3600 s schedule; the
gate's preflight, check order, signal handling and container cleanup.

There is no model, llama-server, container, evaluator or network: only fakes and stubs. The entry fixtures run
req012_entry.main(), unmodified, in the pinned mini-swe-agent venv. They go through the committed, unedited REQ-011
harness (experiments/tools/req011_integration_harness.py), whose `import req011_entry` is answered by a one-line shim
that imports req012_entry. The harness provides a stub sender, a network tripwire, and a fake `docker` that runs
commands in a disposable Git repository. The frozen yaml-v1 driver runs through the unedited REQ-005 harness in mode
'frozen'. These fixtures skip when the pinned venv or the dataset is absent. Expected values are literals from the
lead decision, the worker specification, pilot_runner and the REQ-010/REQ-011 records. The gate's expected outputs for
G1 and G3 are read from archived real outputs of the pinned image (REQ-010 `git show` and repo_state_pre.head, the
REQ-011 `pip list` line); G5's offline output follows pip's documented offline behaviour (no image output exists yet).
"""
import copy
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from collections import OrderedDict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / 'experiments/v2_agent', Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import req012_pair as P  # noqa: E402
import test_req011_pair as T11  # noqa: E402  helpers only (workspace, fake docker, grading fixture); not re-collected

R, P11, S = P.R, P.P11, P.S
MANIFEST_PATH = ROOT / 'configs/v2_req012_repair_probe_20260924.json'
MANIFEST = json.loads(MANIFEST_PATH.read_text())
MANIFEST_SHA = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
IID, PIN, CID = T11.IID, T11.PIN, T11.CID
SMALL_SHA, SMALL_ALIAS = T11.SMALL_SHA, T11.SMALL_ALIAS
LEAD_ADDITION = ('4. The repository to fix is checked out at /testbed, which is the working directory for every action. '
                 'It is installed in editable (development) mode in the active Python environment, so importing the '
                 'package runs the code in /testbed and your edits there take effect immediately. The environment has '
                 'no network access.')
ANCHOR = ('   However, you can prefix any action with `MY_ENV_VAR=MY_VALUE cd /path/to/working/dir && ...` or '
          'write/load environment variables from files\n')
REPAIR_RUN_ARGS = ['--rm', '--platform', 'linux/amd64', '--network', 'none']
STALL_EXIT = {'role': 'exit', 'content': 'RepeatedFailureStall',
              'extra': {'exit_status': 'RepeatedFailureStall', 'submission': ''}}
MSWEA_PY = T11.MSWEA_PY
DEFAULT_YAML = ROOT / 'work/upstream/mini-swe-agent-04d809ceab9df28f9adaed044884180159172930/src/minisweagent/config/default.yaml'


# ---------------------------------------------------------------- manifest and configuration binding

def test_manifest_carries_the_lead_values_exactly():
    assert (MANIFEST['request'], MANIFEST['lead_commit'], MANIFEST['source_commit'], MANIFEST['instance_id']) == (
        'DTR-REQ-012', '40b4db2', '6074003', IID)
    assert [(a['order'], a['assignment_id'], a['backend'], a['arm'], a['port'], a['alias'], a['gguf_sha256'])
            for a in MANIFEST['assignments']] == [(1, 'req012-1-small', 'small', 'baseline', 8291, SMALL_ALIAS,
                                                   SMALL_SHA)]
    assert MANIFEST['images']['instance']['id'] == PIN
    s, c = MANIFEST['settings'], MANIFEST['caps']
    assert (s['step_limit'], s['temperature'], s['max_tokens'], s['context_per_slot'], s['command_timeout_s'],
            s['physical_attempts_per_call_max'], s['wall_time_limit_seconds'], s['configuration_binding']) == (
        24, 0.0, 1536, 16384, 60, 2, 1800, 'yaml-v1-repair1')
    assert (c['pair_wall_s'], c['episode_wall_s'], c['grading_floor_s'], c['episode_load_allowance_s'],
            c['max_logical_requests'], c['max_physical_requests'], c['per_episode_physical']) == (
        3600, 1800, 900, 300, 24, 48, 48)
    assert (c['evaluator_min_start_budget_s'], c['evaluator_end_reserve_s']) == (600, 300)     # unchanged from REQ-011
    assert MANIFEST['gate']['image_head'] == IMAGE_HEAD
    r = MANIFEST['repair1']
    assert (r['prompt_addition'], r['inserted_after'], r['run_args'], r['stall_exit_message']) == (
        LEAD_ADDITION, ANCHOR, REPAIR_RUN_ARGS, STALL_EXIT)
    assert MANIFEST['prompt_bytes']['inserted_text'] == LEAD_ADDITION + '\n'
    assert MANIFEST['gate']['commands'] == dict(
        G0='pwd',
        G1='cd /testbed && git rev-parse HEAD HEAD^ && git log -1 --format=%s && git diff --name-only HEAD^ HEAD && '
           'git status --porcelain',
        G2='cd / && python -c "import astropy,sys; print(astropy.__file__); print(astropy.__version__)"',
        G3="pip list 2>/dev/null | grep -i '^astropy '",
        G4='python -c "import socket; socket.create_connection((\'pypi.org\', 443), timeout=5)"',
        G5='pip install --upgrade astropy',
        G6='cd /testbed && python -m pytest astropy/io/fits/tests/test_header.py -q -x -k "card" -p no:cacheprovider',
        G7='cd /testbed && echo req012 > req012_gate_scratch.txt && git status --porcelain')
    assert MANIFEST['serving']['non_task_generation_probes'] == 0
    assert all(MANIFEST[k] for k in ('declared_rules', 'interpretations', 'inherited_labels', 'semantics_differences',
                                     'scope'))


def test_manifest_binds_to_the_code():
    assert P.manifest_problems(MANIFEST, T11.CONV, T11.REQ010) == []
    assert R.RULES_ANCHOR == ANCHOR and R.PROMPT_ADDITION == LEAD_ADDITION and R.RUN_ARGS == REPAIR_RUN_ARGS


MUTATIONS = dict(
    second_model=lambda m: m['assignments'].append(dict(m['assignments'][0], order=2, backend='large')),
    large_model=lambda m: m['assignments'][0].update(backend='large', port=8293),
    cue_arm=lambda m: m['assignments'][0].update(arm='cue'),
    other_task=lambda m: m.update(instance_id='astropy__astropy-12907'),
    image=lambda m: m['images']['instance'].update(id='sha256:' + '0' * 64),
    cap=lambda m: m['caps'].update(pair_wall_s=3601),
    requests=lambda m: m['caps'].update(max_physical_requests=96),
    settings=lambda m: m['settings'].update(step_limit=25),
    prompt=lambda m: m['repair1'].update(prompt_addition=LEAD_ADDITION + ' Hint: edit card.py.'),
    network=lambda m: m['repair1'].update(run_args=REPAIR_RUN_ARGS[:3]),
    gate=lambda m: m['gate']['commands'].update(G5='pip install astropy'),
    gate_head=lambda m: m['gate'].update(image_head=BASE_COMMIT),
    gate_g1=lambda m: m['gate']['commands'].update(G1='cd /testbed && git rev-parse HEAD && git status --porcelain'),
    floor=lambda m: m['caps'].update(grading_floor_s=600),
    prior=lambda m: m['prior_results'].update({P.REQ011_SUMMARY: '0' * 64}),
    prompt_bytes=lambda m: m.pop('prompt_bytes'),
    text=lambda m: m.pop('inherited_labels'))


@pytest.mark.parametrize('name', sorted(MUTATIONS))
def test_any_manifest_mismatch_fails_closed(name):
    m = copy.deepcopy(MANIFEST)
    MUTATIONS[name](m)
    assert P.manifest_problems(m, T11.CONV, T11.REQ010) != []


def pinned_template():
    if not MSWEA_PY.exists():
        pytest.skip('pinned mini-swe-agent venv is absent')
    code = 'import json, sys, yaml; print(json.dumps(yaml.safe_load(open(sys.argv[1]).read())["agent"]["instance_template"]))'
    return json.loads(subprocess.run([str(MSWEA_PY), '-c', code, str(DEFAULT_YAML)], capture_output=True, text=True,
                                     check=True).stdout)


def test_the_prompt_bytes_are_those_of_the_pinned_default_yaml():
    assert hashlib.sha256(DEFAULT_YAML.read_bytes()).hexdigest() == (
        '112aa58328f478a41cc2630702a4b89ef459e912870e05065157ed221f56701f')
    frozen = pinned_template()
    assert R.prompt_bytes(frozen) == MANIFEST['prompt_bytes']
    assert P.manifest_problems(MANIFEST, T11.CONV, T11.REQ010, frozen) == []
    changed = dict(MANIFEST, prompt_bytes=dict(MANIFEST['prompt_bytes'], instance_template_repair1_sha256='0' * 64))
    assert P.manifest_problems(changed, T11.CONV, T11.REQ010, frozen) != []
    after = R.repair_template(frozen)
    assert after == frozen.replace(ANCHOR, ANCHOR + LEAD_ADDITION + '\n', 1) and after != frozen
    rules = after[after.index('## Important Rules'):after.index('<system_information>')]
    assert rules.index('3. Directory or environment') < rules.index(LEAD_ADDITION)
    assert rules.rstrip('\n').endswith(LEAD_ADDITION)                          # the last item of the list


def test_repair_config_changes_only_the_template_and_the_run_args():
    base = dict(agent=dict(system_template='s', instance_template='## Important Rules\n\n1. a\n' + ANCHOR +
                           '\n<system_information>\nx\n', step_limit=24),
                model=dict(model_name='openai/m', model_kwargs=dict(temperature=0.0)),
                environment=dict(image=PIN, cwd='/testbed', timeout=60, env=dict(PAGER='cat'),
                                 run_args=['--rm', '--platform', 'linux/amd64']))
    before = copy.deepcopy(base)
    out = R.repair_config(base)
    assert base == before                                                        # the frozen result is not mutated
    assert out['agent'] == dict(base['agent'], instance_template='## Important Rules\n\n1. a\n' + ANCHOR +
                                LEAD_ADDITION + '\n' + '\n<system_information>\nx\n')
    assert out['environment'] == dict(base['environment'], run_args=REPAIR_RUN_ARGS)
    assert out['model'] == base['model']
    for bad in (dict(base, agent=dict(base['agent'], instance_template='## Important Rules\n\n<system_information>')),
                dict(base, agent=dict(base['agent'], instance_template=2 * base['agent']['instance_template'])),
                dict(base, agent=dict(base['agent'], instance_template=ANCHOR + '## Important Rules\n<system_information>')),
                dict(base, environment=dict(base['environment'], run_args=['--rm']))):
        with pytest.raises(ValueError):
            R.repair_config(bad)


def test_the_repair1_sandbox_rule():
    good = dict(env=dict(PAGER='cat', MANPAGER='cat', LESS='-R', PIP_PROGRESS_BAR='off', TQDM_DISABLE='1'),
                image=PIN, cwd='/testbed', executable='docker', timeout=60, run_args=REPAIR_RUN_ARGS)
    assert P.repair_sandbox_problems(good) == []
    for bad in (dict(good, run_args=['--rm', '--platform', 'linux/amd64']),
                dict(good, run_args=REPAIR_RUN_ARGS[:3] + ['--network', 'host']),
                dict(good, run_args=REPAIR_RUN_ARGS + ['-v', '/:/host']), dict(good, forward_env=['HOME']),
                dict(good, env=dict(good['env'], GITHUB_TOKEN='x')), dict(good, volumes=['/x'])):
        assert P.repair_sandbox_problems(bad)


# ---------------------------------------------------------------- the stall rule (pure)

def turn(command, rc, output):
    return R.turn_of({'extra': {'actions': [{'command': command}]}},
                     [{'role': 'user', 'extra': {'returncode': rc, 'raw_output': output}}])


PIP_RETRY = ("WARNING: Retrying (Retry(total=4, connect=None, read=None, redirect=None, status=None)) after connection "
             "broken by 'NewConnectionError('<pip._vendor.urllib3.connection.HTTPSConnection object at %s>: Failed to "
             "establish a new connection: [Errno -3] Temporary failure in name resolution')': /simple/astropy/\n")


def test_normalization_fingerprint_and_recorded_turns():
    assert R.normalize('  ls   -la\n\t/x  ') == 'ls -la /x'
    assert R.fingerprint('No  such\nfile \n') == hashlib.sha256(b'No such file').hexdigest()
    assert R.fingerprint('<obj at 0x7f3A1c>, 1 failed in 3.21s\n') == hashlib.sha256(
        b'<obj at 0x_>, 1 failed in _s').hexdigest()
    assert R.fingerprint(PIP_RETRY % '0x7f3a1c2b4d60') == R.fingerprint(PIP_RETRY % '0x7f99ab01cd10')
    assert R.fingerprint('1 failed, 4 passed in 3.21s') == R.fingerprint('1 failed, 4 passed in 12.07s')
    for a, b in (('1 failed, 4 passed in 3.21s', '2 failed, 3 passed in 3.21s'), ('line 12', 'line 13'),
                 ('commit a4ae7a38', 'commit 80c3854a'), ('took 3s', 'took 4s')):
        assert R.fingerprint(a) != R.fingerprint(b)                  # only the two declared token kinds are masked
    assert turn('ls  /x ', 1, 'e\n') == ('ls /x', 1, hashlib.sha256(b'e').hexdigest())
    obs = [{'extra': {'returncode': 1, 'raw_output': 'e'}}]
    assert R.turn_of({'extra': {'actions': [{'command': 'a'}, {'command': 'b'}]}}, obs) is None   # two actions
    assert R.turn_of({'extra': {'actions': []}}, []) is None                                     # no action
    assert R.turn_of({'extra': {'actions': [{'command': 'a'}]}}, obs + obs) is None
    assert turn('a', None, 'e') is None and turn('a', True, 'e') is None and turn('a', 1, None) is None


def test_the_stall_rule():
    fail = turn('ls /x', 1, 'No such file')
    assert R.stalled([fail, turn('ls    /x', 1, 'No  such file\n')])          # after whitespace normalization
    assert R.stalled([turn('true', 0, ''), fail, fail])
    loop = 'pip install --upgrade astropy\ngit apply fix_fits_cards.patch'          # the REQ-011 7B loop, offline
    patch_error = 'error: patch failed: astropy/io/fits/card.py:100\n'
    assert R.stalled([turn(loop, 1, PIP_RETRY % '0x7f3a1c2b4d60' + patch_error),
                      turn(loop, 1, PIP_RETRY % '0x7f99ab01cd10' + patch_error)])
    for turns in ([], [fail], [turn('true', 0, 'ok')] * 2,                         # identical successes
                  [fail, turn('ls /x', 2, 'No such file')],                         # different return code
                  [fail, turn('ls /x', 1, 'Permission denied')],                    # different output
                  [fail, turn('ls /y', 1, 'No such file')],                         # different command
                  [fail, None, fail], [fail, fail, None], [None, None]):            # a FormatError resets
        assert not R.stalled(turns)
    assert R.stall_message() == STALL_EXIT


# ---------------------------------------------------------------- the real entry in the pinned venv

REQ011_HARNESS = ROOT / 'experiments/tools/req011_integration_harness.py'
FROZEN_HARNESS = T11.FROZEN_HARNESS
SHIM = 'import sys\nsys.path.insert(0, %r)\nfrom req012_entry import A, main  # noqa: E402,F401\n'
_RUN = '  run) cat "$STATE/container_id"; exit 0 ;;'
_CONTAINER = '  container) echo false; exit 0 ;;'
assert T11.FAKE_DOCKER.count(_RUN) == 1 and T11.FAKE_DOCKER.count(_CONTAINER) == 1
FAKE_DOCKER = T11.FAKE_DOCKER.replace(
    _RUN, r'''  run) printf '%s\n' "$@" > "$STATE/run_argv"; cat "$STATE/container_id"; exit 0 ;;''').replace(
    _CONTAINER, r'''  container) case "$*" in *NetworkMode*) if grep -qx none "$STATE/run_argv"; then echo none; '''
                r'''else echo default; fi ;; *) echo false ;; esac; exit 0 ;;''')
MISSING = 'echo "<object at 0x$$> in 0.$$s" && ls /nonexistent_req012_dir'   # $$: a new PID on every run
COUNT = 'echo x >> /testbed/.git/req012_n && cat /testbed/.git/req012_n && false'
RCVAR = 'test -e /testbed/.git/req012_f && exit 3; touch /testbed/.git/req012_f; exit 2'
act = T11.act
SCENARIOS = dict(
    stall=dict(script=[act(MISSING), act('echo "<object at 0x$$> in 0.$$s"  &&  ls    /nonexistent_req012_dir'),
                       act(MISSING), T11.SUBMIT]),
    negative=dict(script=[act('false'), dict(content='THOUGHT: no action this time.'), act('false'), act('exit 1'),
                          act('true'), act('true'), act(COUNT), act(COUNT), act(RCVAR), act(RCVAR), T11.SUBMIT]),
    submitted=dict(script=[T11.LS, T11.EDIT, T11.SUBMIT]),
    refused=dict(script=[T11.LS], arm='cue', namespace=dict(counted_before=1)))


def workspace(base):
    home, state = T11.workspace(base)
    (home / '.local/dtr-runtime/bin/docker').write_text(FAKE_DOCKER)
    return home, state


def child_env(home, base):
    env = {k: v for k, v in os.environ.items()
           if not k.lower().endswith('_proxy') and not k.startswith(('LITELLM_', 'EXPERIMENTAL_OPENAI', 'MSWEA_'))}
    env.update(HOME=str(home), LITELLM_LOCAL_MODEL_COST_MAP='True', MSWEA_SILENT_STARTUP='1',
               MSWEA_GLOBAL_CONFIG_DIR=str(base / 'mswea_config'))
    return env


def run_scenario(base, name, sources, runtime):
    scenario = SCENARIOS[name]
    home, state = workspace(base)
    shim = base / 'shim'
    shim.mkdir()
    (shim / 'req011_entry.py').write_text(SHIM % str(ROOT / 'experiments/v2_agent'))
    run_id = '%s__small__req012__fixture-%s' % (IID, name)
    run_dir, control_dir, layout_root = base / 'raw' / run_id, base / 'raw' / 'control' / run_id, base / 'layout'
    for d in (run_dir, control_dir, layout_root / 'work'):
        d.mkdir(parents=True)
    control = dict(request='DTR-REQ-012', binding_sha256=MANIFEST_SHA, assignment_id='req012-1-small',
                   model_sha256=SMALL_SHA, admitted_sources=sources, runtime=runtime, namespace=dict(
                       instance=IID, backend='small', arm=scenario.get('arm', 'baseline'), position=1, port=8291,
                       alias=SMALL_ALIAS, run_dir=str(run_dir), run_id=run_id, expected_image=PIN,
                       served=json.dumps(dict(model_file='fixture.gguf', model_sha256=SMALL_SHA)), counted_before=0,
                       request_limit=48, host_reserve_bytes=1 << 30))
    control['namespace'].update(scenario.get('namespace', {}))
    config = dict(out=str(base / 'out'), script=scenario['script'], alias=SMALL_ALIAS, model_file='fixture.gguf',
                  module_dir=str(shim), layout_root=str(layout_root), control=control,
                  control_path=str(control_dir / 'entry.json'), deadline_in=600)
    (base / 'config.json').write_text(json.dumps(config))
    proc = subprocess.run([str(MSWEA_PY), str(REQ011_HARNESS), str(base / 'config.json')], capture_output=True,
                          text=True, env=child_env(home, base), timeout=600, cwd=str(base))
    assert proc.returncode == 0, proc.stderr[-4000:]
    return dict(harness=json.loads((base / 'out' / 'harness.json').read_text()), run_dir=run_dir, control=control_dir,
                run_id=run_id, state=state, layout_root=layout_root, raw=base / 'raw',
                private=layout_root / P.A.PRIVATE_RECEIPTS_REL / run_id,
                bodies=[p.read_bytes() for p in sorted((base / 'out' / 'terminal').glob('*.body'))])


def run_frozen(base, script):
    """The same stub script through the frozen yaml-v1 driver (pilot_episode.main, unedited), 7B arguments."""
    home, state = workspace(base)
    run_dir = base / 'run'
    run_dir.mkdir()
    now = time.time()
    argv = ['--instance', IID, '--backend', 'small', '--port', '8291', '--alias', SMALL_ALIAS, '--run-dir', str(run_dir),
            '--run-id', 'frozen-reference', '--expected-image', PIN, '--served',
            json.dumps(dict(model_file='fixture.gguf', model_sha256=SMALL_SHA)), '--episode-deadline',
            repr(now + 600.0), '--block-deadline', repr(now + 3000.0)]
    config = dict(mode='frozen', out=str(base / 'out'), script=script, alias=SMALL_ALIAS, model_file='fixture.gguf',
                  frozen_module_dir=str(ROOT / 'experiments/v2_agent'), argv=argv)
    (base / 'config.json').write_text(json.dumps(config))
    proc = subprocess.run([str(MSWEA_PY), str(FROZEN_HARNESS), str(base / 'config.json')], capture_output=True,
                          text=True, env=child_env(home, base), timeout=600, cwd=str(base))
    assert proc.returncode == 0, proc.stderr[-4000:]
    return dict(harness=json.loads((base / 'out' / 'harness.json').read_text()), run_dir=run_dir, state=state,
                bodies=[p.read_bytes() for p in sorted((base / 'out' / 'terminal').glob('*.body'))])


@pytest.fixture(scope='module')
def runs(tmp_path_factory):
    if not MSWEA_PY.exists() or not T11.DATA.exists():
        pytest.skip('pinned mini-swe-agent venv or the pinned SWE-bench Verified parquet is absent')
    sources = {rel: hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() for rel in P.SOURCES}
    binding, problems = P.A.compute_binding(P.A.Layout(ROOT))
    assert problems == []
    runtime = {k: binding['runtime'][k] for k in ('sdk_traced_files', 'mini_swe_agent_sources')}
    work = tmp_path_factory.mktemp('req012_entry')
    out = {name: run_scenario(work / name, name, sources, runtime) for name in SCENARIOS}
    out['frozen_submitted'] = run_frozen(work / 'frozen_submitted', SCENARIOS['submitted']['script'])
    return out


def records(result, name):
    return json.loads((result['run_dir'] / name).read_text())


def repair_record(result):
    return json.loads((result['control'] / 'repair_record.json').read_text())


def test_the_stall_guard_fires_before_the_third_query_and_preserves_the_artifacts(runs):
    r = runs['stall']
    assert (r['harness']['exit_code'], r['harness']['network_attempts'], r['harness']['script_left']) == (0, [], 2)
    assert len(r['bodies']) == 2                                                # no third request
    ep = records(r, 'episode.json')
    assert (ep['exit_status'], ep['logical_calls'], ep['n_model_calls'], ep['physical_requests']) == (
        'RepeatedFailureStall', 2, 2, 2)
    assert (r['run_dir'] / 'submission.diff').read_bytes() == b'' and ep['submission_empty'] is True
    trajectory = records(r, 'trajectory.json')
    assert trajectory['messages'][-1] == STALL_EXIT
    outputs = [m['extra']['raw_output'] for m in trajectory['messages'] if 'raw_output' in (m.get('extra') or {})]
    assert len(outputs) == 2 and outputs[0] != outputs[1]            # they differ only in the address and duration
    assert [re.sub(r'<object at 0x[0-9]+> in 0\.[0-9]+s', 'V', x) for x in outputs] == [
        re.sub(r'<object at 0x[0-9]+> in 0\.[0-9]+s', 'V', outputs[0])] * 2
    assert (trajectory['info']['exit_status'], trajectory['info']['submission']) == ('RepeatedFailureStall', '')
    assert trajectory['info']['config']['agent_type'] == 'req012_entry.RepeatedFailureGuardAgent'
    diag = records(r, 'exit_diagnostic.json')                                   # the all-exit capture
    assert (diag['exit_status'], diag['endpoint']['graded'], diag['sections']['tree']['state']) == (
        'RepeatedFailureStall', False, 'captured')
    terminal = records(r, 'terminal_phase.json')
    assert (terminal['cleanup']['state'], terminal['endpoint_check_after_cleanup']['state']) == ('returned', 'unchanged')
    assert sorted(p.name for p in (r['run_dir'] / 'receipts').iterdir()) == [
        'call00%d_attempt01.%s.json' % (n, kind) for n in (1, 2) for kind in ('outcome', 'request')]
    assert [(r['private'] / ('call%03d_attempt01.request.raw' % n)).read_bytes() for n in (1, 2)] == r['bodies']
    facts = P11.episode_facts(r['run_dir'], r['run_id'], root=r['layout_root'])
    assert (facts['receipts_completeness']['complete'], facts['eligible']) == (True, False)
    guard = repair_record(r)['guard']
    assert (guard['fired'], guard['fired_before_call'], guard['n_model_calls']) == (True, 3, 2)
    assert len(guard['turns']) == 2 and guard['turns'][0] == guard['turns'][1] and guard['turns'][0]['returncode'] != 0
    assert repair_record(r)['effective_config']['verified'] is True
    facts = P.repair_facts(r['run_dir'], r['control'])
    assert (facts['stall_guard_fired'], facts['stall_guard_fired_before_call'], facts['network_mode_observed']) == (
        True, 3, 'none')
    assert P.outcome_source('completed', ep['exit_status'], False) == 'stall_guard'


def test_the_guard_does_not_fire_for_successes_or_a_different_rc_output_or_command_or_across_a_format_error(runs):
    r = runs['negative']
    assert (r['harness']['exit_code'], r['harness']['network_attempts'], r['harness']['script_left']) == (0, [], 0)
    assert len(r['bodies']) == 11                                               # every scripted query was sent
    ep = records(r, 'episode.json')
    assert (ep['exit_status'], ep['logical_calls']) == ('Submitted', 11)
    guard = repair_record(r)['guard']
    assert (guard['fired'], guard['fired_before_call']) == (False, None)
    t = guard['turns']
    assert [None if x is None else x['returncode'] for x in t] == [1, None, 1, 1, 0, 0, 1, 1, 2, 3]
    assert t[0] == t[2]                                     # identical failures separated by a FormatError turn
    assert t[2]['command_sha256'] != t[3]['command_sha256'] and t[2]['output_fingerprint'] == t[3]['output_fingerprint']
    assert t[4] == t[5]                                     # identical successful turns
    assert t[6]['command_sha256'] == t[7]['command_sha256'] and t[6]['output_fingerprint'] != t[7]['output_fingerprint']
    assert t[8]['command_sha256'] == t[9]['command_sha256'] and t[8]['output_fingerprint'] == t[9]['output_fingerprint']
    assert any('Format error' in m['content'] for m in records(r, 'trajectory.json')['messages'] if m['role'] == 'user')


def escaped(text):
    return json.dumps(text)[1:-1].encode()


def test_repair1_differs_from_the_frozen_driver_only_by_the_prompt_bytes_the_network_and_the_agent_class(runs):
    r, f = runs['submitted'], runs['frozen_submitted']
    assert (f['harness']['mode'], f['harness']['exit_code'], f['harness']['network_attempts']) == ('frozen', 0, [])
    assert len(r['bodies']) == len(f['bodies']) == 3
    for ours, frozen in zip(r['bodies'], f['bodies']):
        assert frozen.count(escaped(ANCHOR)) == 1
        assert ours == frozen.replace(escaped(ANCHOR), escaped(ANCHOR + LEAD_ADDITION + '\n'), 1)
    ours_m, frozen_m = T11.messages(r['run_dir']), T11.messages(f['run_dir'])
    assert len(ours_m) == len(frozen_m) and ours_m[:1] + ours_m[2:] == frozen_m[:1] + frozen_m[2:]
    assert ours_m[1] == (frozen_m[1][0], frozen_m[1][1].replace(ANCHOR, ANCHOR + LEAD_ADDITION + '\n', 1))
    ours_cfg, frozen_cfg = T11.effective(r['run_dir']), T11.effective(f['run_dir'])
    for part in ('constructor_arguments', 'resolved'):
        a, b = copy.deepcopy(ours_cfg[part]), copy.deepcopy(frozen_cfg[part])
        assert a['agent'].pop('instance_template') == b['agent'].pop('instance_template').replace(
            ANCHOR, ANCHOR + LEAD_ADDITION + '\n', 1)
        assert (a['environment'].pop('run_args'), b['environment'].pop('run_args')) == (
            REPAIR_RUN_ARGS, ['--rm', '--platform', 'linux/amd64'])
        assert a == b                                                            # nothing else differs
    assert (records(r, 'trajectory.json')['info']['config']['agent_type'],
            json.loads((f['run_dir'] / 'trajectory.json').read_text())['info']['config']['agent_type']) == (
        'req012_entry.RepeatedFailureGuardAgent', 'minisweagent.agents.default.DefaultAgent')
    argv = (r['state'] / 'run_argv').read_text().splitlines()                    # what `docker run` received
    assert argv[argv.index('--network') + 1] == 'none'
    assert '--network' not in (f['state'] / 'run_argv').read_text().splitlines()
    rec = repair_record(r)
    assert (rec['configuration'], rec['guard']['network']['network_mode'], rec['guard']['network']['run_args']) == (
        'yaml-v1-repair1', 'none', REPAIR_RUN_ARGS)
    assert rec['effective_config']['verified'] is True and rec['effective_config']['problems'] == []
    assert rec['effective_config']['instance_template_sha256'] == MANIFEST['prompt_bytes'][
        'instance_template_repair1_sha256']
    admitted = json.loads((r['control'] / 'entry_admitted.json').read_text())
    assert (admitted['admitted'], admitted['configuration'], admitted['runtime_overrides']) == (
        True, 'yaml-v1-repair1', MANIFEST['repair1']['runtime_overrides'])


def test_receipts_ordinals_and_the_endpoint_are_preserved(runs):
    r, f = runs['submitted'], runs['frozen_submitted']
    ep = records(r, 'episode.json')
    assert (ep['exit_status'], ep['logical_calls'], ep['physical_requests']) == ('Submitted', 3, 3)
    assert (r['run_dir'] / 'submission.diff').read_bytes() == T11.MOD_NEW_DIFF == (
        f['run_dir'] / 'submission.diff').read_bytes()                          # the same bytes as the frozen driver
    assert (ep['submission_sha256'], ep['binding_sha256']) == (T11.MOD_NEW_SHA, MANIFEST_SHA)
    sends = [json.loads((r['run_dir'] / 'receipts' / ('call%03d_attempt01.request.json' % n)).read_text())['send']
             for n in (1, 2, 3)]
    assert [(x['cohort_request_ordinal'], x['cohort_request_limit']) for x in sends] == [(1, 48), (2, 48), (3, 48)]
    assert [(r['private'] / ('call%03d_attempt01.request.raw' % n)).read_bytes() for n in (1, 2, 3)] == r['bodies']
    facts = P11.episode_facts(r['run_dir'], r['run_id'], root=r['layout_root'])
    assert (facts['eligible'], facts['receipts_completeness']['complete']) == (True, True)
    assert (runs['stall']['run_dir'] / 'submission.diff').read_bytes() == b''    # non-Submitted -> ''


def test_the_entry_refuses_a_cue_arm_and_a_wrong_budget_before_any_work(runs):
    r = runs['refused']
    assert r['harness']['exit_code'] == 3 and r['bodies'] == [] and r['harness']['network_attempts'] == []
    reasons = json.loads((r['control'] / 'entry_refused.json').read_text())['reasons']
    assert "arm 'cue': DTR-REQ-012 runs the baseline arm only (no cue)" in reasons
    assert 'request budget arguments differ from min(48, 48 - counted_before)' in reasons
    assert not (r['control'] / 'entry_admitted.json').exists() and not (r['control'] / 'repair_record.json').exists()
    assert list(r['run_dir'].iterdir()) == [] and not (r['state'] / 'calls.log').exists()     # no docker command


def test_the_probe_summary_classifies_a_stall_and_carries_the_repair_facts(runs, tmp_path):
    r = runs['stall']
    ep = records(r, 'episode.json')
    pub = tmp_path / 'pub'
    pub.mkdir()
    ctx = dict(root=r['layout_root'], raw=r['raw'], pub=pub, clock=time.time, start=time.time(),
               ledger=P11.Ledger(tmp_path / 'ledger.jsonl'),
               records=[OrderedDict(order=1, assignment_id='req012-1-small', backend='small', alias=SMALL_ALIAS,
                                    port=8291, run_id=r['run_id'], state='completed',
                                    request_accounting=P11.account(ep, P.CAPS))])
    summary = P.finish(ctx, OrderedDict(status='COMPLETED'), MANIFEST)
    row = summary['assignments'][0]
    assert (row['outcome_source'], row['exit_status'], row['eligible']) == ('stall_guard', 'RepeatedFailureStall', False)
    assert (row['repair1']['stall_guard_fired_before_call'], row['repair1']['network_mode_observed'],
            row['repair1']['effective_config_verified']) == (3, 'none', True)
    assert summary['outcome_sources'] == dict(eligible_submission=0, agent=0, stall_guard=1, time_limit=0,
                                              infrastructure_or_supervision=0)
    assert (summary['requests']['physical_counted_total'], summary['requests']['max_physical'],
            summary['probe_cap_s']) == (2, 48, 3600)
    assert (pub / r['run_id'] / 'control' / 'repair_record.json').exists() and (pub / 'pair_summary.json').exists()


# ---------------------------------------------------------------- schedule, queue, grading

def test_schedule_and_caps_for_the_3600_s_budget():
    deadline = 100000.0
    # 300 load + 1800 episode + 120 child grace + 30 wait slack + 90 server reserve before deadline - 900 floor
    assert P11.fits(deadline - 3240, deadline, 300, P.CAPS) and not P11.fits(deadline - 3239, deadline, 300, P.CAPS)
    assert P11.fits(deadline - 2940, deadline, 0, P.CAPS) and not P11.fits(deadline - 2939, deadline, 0, P.CAPS)
    assert [P11.request_limit(c, P.CAPS) for c in (0, 7, 48)] == [48, 41, 0]
    served, log, recs = [], [], []

    def run_one(a, counted_before, rec):
        log.append((a['backend'], counted_before, P11.request_limit(counted_before, P.CAPS)))
        rec.update(state='completed', request_accounting=P11.account({'physical_requests': 48}, P.CAPS))
    queue = copy.deepcopy(MANIFEST['assignments'])
    assert P11.run_episodes(queue, deadline, lambda a: served.append((a['backend'], a['port'])), run_one, recs,
                            clock=T11.Clock(deadline - 3240), caps=P.CAPS) is None
    assert (served, log) == ([('small', 8291)], [('small', 0, 48)])
    recs = []
    assert P11.run_episodes(queue, deadline, served.append, run_one, recs, clock=T11.Clock(deadline - 3239),
                            caps=P.CAPS) == 'pair cap'
    assert [x['state'] for x in recs] == ['not_started: pair cap']


def test_the_grading_floor_leaves_the_unchanged_evaluator_its_start_budget(tmp_path):
    deadline = 100000.0
    # the latest post-load dispatch, then the full episode wall, the child grace and wait slack and the server reserve
    end = deadline - 2940 + 1800 + 120 + 30 + 90
    assert P11.fits(deadline - 2940, deadline, 0, P.CAPS) and end == deadline - 900

    class Started(Exception):
        pass

    def popen(*args, **kwargs):
        raise Started()

    def harness(now):                                  # the real req011_grade budget rule; docker and popen are fakes
        return T11.G.make_run_harness(IID, SMALL_ALIAS, tmp_path, deadline, P.CAPS, [], {}, clock=lambda: now,
                                      popen=popen, run=lambda *a, **k: (0, '', ''))
    with pytest.raises(Started):                       # budget min(1800, 900 - 300) = 600: the attempt starts
        harness(end)('eval-a1', 'preds.json')
    with pytest.raises(T11.G.Ungraded):                # one second later it would not (the earlier 600 s floor)
        harness(end + 1)('eval-b1', 'preds.json')


def test_grading_uses_a_fresh_evaluator_from_the_pinned_image_never_the_agent_container(tmp_path):
    ctx, rec, own, listing, calls, control = T11.grading_case(tmp_path)
    ctx['pair_deadline'] = time.time() + 600
    caps = dict(P.CAPS, evaluator_attempt_max_s=2, evaluator_min_start_budget_s=1)
    out = P11.make_grader(ctx, caps)(rec)
    grade_control = json.loads((control / 'grade_control.json').read_text())
    assert grade_control['image_pin'] == PIN == MANIFEST['images']['instance']['id']
    grader_calls = [json.loads(x) for x in (control / 'grader_docker_calls.jsonl').read_text().splitlines()]
    assert grader_calls[0] == ['docker', 'image', 'inspect', '--format', '{{.Id}}', 'sweb.eval.x86_64.%s:latest' % IID]
    assert (out['grader']['image_before'], out['grader']['image_after_equals_pin']) == (PIN, True)
    for cmd in grader_calls + calls:                    # nothing ever touches an agent (minisweagent-*) container
        assert 'exec' not in cmd and not any('minisweagent' in x or CID in x for x in cmd)
    assert [a['container_cleanup']['name'] for a in out['grader']['attempts']] == own    # the stock evaluator's own
    stock = T11.G.harness_cmd(IID, 'eval-r-a1', '/w/p.json', '/w', python='py')
    assert stock[stock.index('--cache_level') + 1] == 'instance' and stock[stock.index('--namespace') + 1] == 'none'


def test_the_ownership_holder_and_the_watchdog_launcher_are_req012_and_stop_the_server_after_a_parent_sigkill(
        tmp_path, monkeypatch):
    monkeypatch.setattr(P.PR, 'SERVERS', tmp_path / 'own.json')
    P.Servers({}, dict(hard_deadline_epoch=0, block_start_utc='a', block_hard_end_utc='b'), tmp_path)._record()
    assert json.loads((tmp_path / 'own.json').read_text())['holder'] == (
        'DTR-AgentEvals worker (DTR-REQ-012 repair probe)') == P.HOLDER
    stub = T11.STUB_PARENT.replace('import req011_pair as P', 'import req012_pair as P')
    assert stub != T11.STUB_PARENT
    (tmp_path / 'stub_parent.py').write_text(stub % dict(module_dir=str(ROOT / 'experiments/v2_agent'),
                                                         sleeper=T11.SLEEPER))
    parent = subprocess.Popen([sys.executable, str(tmp_path / 'stub_parent.py'), str(tmp_path)],
                              start_new_session=True)
    pids = {}
    try:
        assert T11.wait_until(lambda: (tmp_path / 'pids.json').exists(), 60)
        pids = json.loads((tmp_path / 'pids.json').read_text())
        assert pids['ready'] is True and T11.alive(pids['server']) and T11.alive(pids['watchdog'])
        cfg = json.loads((tmp_path / 'raw' / 'watchdog_config.json').read_text())
        assert (cfg['request'], cfg['holder']) == ('DTR-REQ-012', P.HOLDER)
        args = subprocess.run(['ps', '-ww', '-o', 'args=', '-p', str(pids['watchdog'])], capture_output=True,
                              text=True).stdout
        assert 'req012_pair.py --watchdog' in args
        os.kill(parent.pid, 9)                                           # SIGKILL: no handler, no finally
        parent.wait(timeout=10)
        assert T11.wait_until(lambda: not T11.alive(pids['server']), 30)
        assert T11.wait_until(lambda: not T11.alive(pids['watchdog']), 30)
        assert T11.alive(pids['decoy'])                                  # recorded PID, other command: untouched
        action = json.loads((tmp_path / 'raw' / 'watchdog_action.json').read_text())
        assert (action['reason'], action['action'], action['record_holder']) == (
            'parent process gone', 'stopped', P.HOLDER)
    finally:
        for pid in [parent.pid] + [pids[k] for k in ('server', 'decoy', 'watchdog') if k in pids]:
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass


# ---------------------------------------------------------------- the gate

REQ010_ATTEMPT = ROOT / 'results/v2_adapter/req010_sentinel_20260924/astropy__astropy-14598/attempt-1-20260924T113537Z'
REQ011_RUNS = ROOT / 'results/v2_agent/req011_competence_20260924'


def archived_image_git():
    """(HEAD, subject, changed files, base commit) of the pinned image, from the archived REQ-010 stock evaluation: the
    `git show` it ran in a container of that image, and the base commit its eval script diffs against."""
    text = (REQ010_ATTEMPT / 'stock_test_output.txt').read_text()
    show = text[text.index('\n+ git show\n'):text.index('\n+ git -c core.fileMode=false diff ')].splitlines()
    head = next(x.split()[1] for x in show if x.startswith('commit '))
    date = next(i for i, x in enumerate(show) if x.startswith('Date:'))
    subject = next(x.strip() for x in show[date + 1:] if x.strip())
    files = [x.split(' b/')[-1] for x in show if x.startswith('diff --git ')]
    script = (REQ010_ATTEMPT / 'stock_eval.sh').read_text().splitlines()
    base = next(x.split()[-1] for x in script if x.startswith('git -c core.fileMode=false diff '))
    return head, subject, files, base


def archived_observation(name, predicate):
    for m in json.loads(next(REQ011_RUNS.glob(name + '/trajectory.json')).read_text())['messages']:
        out = (m.get('extra') or {}).get('raw_output')
        if isinstance(out, str) and predicate(out):
            return out
    raise AssertionError('no archived observation matched')


IMAGE_HEAD, SUBJECT, HEAD_FILES, BASE_COMMIT = archived_image_git()
def pip_list_line(line):
    return line.startswith('astropy ') and line.endswith(' /testbed')


PIP_LIST = next(x for x in archived_observation('*__large__*', lambda o: any(map(pip_list_line, o.splitlines())))
                .splitlines() if pip_list_line(x))                         # REQ-011: `pip list` in the agent container
VERSION = PIP_LIST.split()[1]
PIP_ONLINE = archived_observation('*__large__*', lambda o: 'Successfully installed astropy-6.0.1' in o)
KEPT = PIP_ONLINE.splitlines()[0]          # pip's first line in the image: the installed editable 5.3 dev astropy
PIP_OFFLINE = (KEPT + '\n' + ''.join(PIP_RETRY.replace('total=4', 'total=%d' % n) % ('0x7f3a1c2b%04x' % n)
                                     for n in (4, 3, 2, 1, 0))
               + 'Requirement already satisfied: numpy<2,>=1.22 in /opt/miniconda3/envs/testbed/lib/python3.9/'
                 'site-packages (from astropy) (1.25.2)\n'
                 "WARNING: Running pip as the 'root' user can result in broken permissions.\n")
ORDER = ['G0', 'G1', 'G2', 'G3', 'G4', 'G5', 'G5_then_G2', 'G5_then_G3', 'G6', 'G7']
SITE = '/opt/miniconda3/envs/testbed/lib/python3.9/site-packages/astropy/__init__.py'
GOOD = dict(
    G0=(0, '/testbed\n'), G1=(0, '\n'.join([IMAGE_HEAD, BASE_COMMIT, SUBJECT] + HEAD_FILES) + '\n'),
    G2=(0, '/testbed/astropy/__init__.py\n%s\n' % VERSION), G3=(0, PIP_LIST + '\n'),
    G4=(1, 'Traceback (most recent call last):\nsocket.gaierror: [Errno -3] Temporary failure in name resolution\n'),
    G5=(0, PIP_OFFLINE), G5_then_G2=(0, '/testbed/astropy/__init__.py\n%s\n' % VERSION),
    G5_then_G3=(0, PIP_LIST + '\n'),
    G6=(1, '....F\n1 failed, 4 passed, 130 deselected in 3.21s\n'), G7=(0, '?? req012_gate_scratch.txt\n'))
BAD = dict(
    G0_root=('G0', (0, '/\n')),
    G1_head_only=('G1', (0, BASE_COMMIT + '\n')),                       # the first build's expectation (HEAD = base)
    G1_other_head=('G1', (0, '\n'.join(['b' * 40, BASE_COMMIT, SUBJECT] + HEAD_FILES) + '\n')),
    G1_other_parent=('G1', (0, '\n'.join([IMAGE_HEAD, 'b' * 40, SUBJECT] + HEAD_FILES) + '\n')),
    G1_subject=('G1', (0, '\n'.join([IMAGE_HEAD, BASE_COMMIT, 'fix card'] + HEAD_FILES) + '\n')),
    G1_more_files=('G1', (0, '\n'.join([IMAGE_HEAD, BASE_COMMIT, SUBJECT] + HEAD_FILES + ['astropy/io/fits/card.py'])
                          + '\n')),
    G1_dirty=('G1', (0, GOOD['G1'][1] + ' M astropy/io/fits/card.py\n')), G1_rc=('G1', (128, GOOD['G1'][1])),
    G2_site=('G2', (0, SITE + '\n5.3.dev940\n')), G2_release=('G2', (0, '/testbed/astropy/__init__.py\n6.0.1\n')),
    G3_site=('G3', (0, 'astropy 6.0.1\n')), G3_missing=('G3', (1, '')), G4_egress=('G4', (0, '')),
    G4_unknown=('G4', (None, '')), G5_installed=('G5', (0, PIP_ONLINE)), G5_rc_unknown=('G5', (None, PIP_OFFLINE)),
    G5_replaced=('G5_then_G2', (0, SITE + '\n6.0.1\n')),
    G5_not_editable=('G5_then_G3', (0, 'astropy 6.0.1\n')),
    G6_no_tests=('G6', (5, 'no tests ran in 0.12s\n')), G6_collection=('G6', (2, '1 error in 0.50s\n')),
    G6_timeout=('G6', (-1, '')), G7_invisible=('G7', (0, '')))


def test_the_gate_expectations_are_anchored_to_the_archived_image_outputs():
    summary = json.loads((REQ010_ATTEMPT / 'summary.json').read_text())
    assert summary['image_digests']['instance'] == PIN                          # the same pinned image
    heads = {summary[k]['attempts'][0]['repo_state_pre']['head'] for k in ('adapter_reference', 'adapter_no_change')}
    assert heads == {IMAGE_HEAD} == {P.IMAGE_HEAD}
    assert (SUBJECT, HEAD_FILES, BASE_COMMIT) == ('SWE-bench', ['pyproject.toml'],
                                                  '80c3854a5f4f4a6ab86c03d9db7854767fcd83c1')
    assert PIP_LIST.split()[-1] == '/testbed' and '.dev' in VERSION
    assert KEPT.startswith('Requirement already satisfied: astropy in ') and VERSION in KEPT


def fake_execute(results):
    seen = []

    def execute(command):
        name = ORDER[len(seen)]
        assert command == P.GATE_COMMANDS[name[-2:] if name.startswith('G5_then_') else name]
        seen.append(name)
        return results[name]
    return execute, seen


def test_the_gate_checks_pass_on_the_expected_outputs_in_order():
    execute, seen = fake_execute(GOOD)
    rows, ok = P.gate_checks(execute, BASE_COMMIT)
    assert ok and seen == ORDER and list(rows) == ORDER and all(x['ok'] for x in rows.values())
    assert rows['G6']['observed']['summary_line'] == '1 failed, 4 passed, 130 deselected in 3.21s'
    assert rows['G2']['output_sha256'] == hashlib.sha256(GOOD['G2'][1].encode()).hexdigest()
    assert (rows['G5']['observed']['pip_returncode'], rows['G5']['observed']['successfully_installed_lines']) == (0, [])
    colored = (0, '\x1b[32m\x1b[1m5 passed\x1b[0m, \x1b[33m130 deselected\x1b[0m\x1b[32m in 0.63s\x1b[0m\n')  # REQ-010 style
    rows, ok = P.gate_checks(fake_execute(dict(GOOD, G6=colored))[0], BASE_COMMIT)
    assert ok and rows['G6']['observed']['summary_line'] == '5 passed, 130 deselected in 0.63s'
    for pip in ((1, 'ERROR: Could not find a version that satisfies the requirement astropy (from versions: none)\n'),
                (-1, PIP_OFFLINE[:300])):                                   # any integer rc, including a timeout
        assert P.gate_checks(fake_execute(dict(GOOD, G5=pip))[0], BASE_COMMIT)[1]


@pytest.mark.parametrize('name', sorted(BAD))
def test_each_gate_expectation_fails_closed(name):
    step, result = BAD[name]
    rows, ok = P.gate_checks(fake_execute(dict(GOOD, **{step: result}))[0], BASE_COMMIT)
    assert not ok and rows[step]['ok'] is False
    if step.startswith('G5_then_'):
        assert rows['G5']['ok'] is False                                          # the upgrade replaced the checkout


def test_the_fixture_step_of_the_gate_requires_every_test_to_pass_with_none_skipped(tmp_path):
    for i, (rc, out, expected) in enumerate(((0, '....\n51 passed in 16.00s\n', True),
                                             (0, '\x1b[32m51 passed\x1b[0m in 1.0s\n', True),
                                             (0, '49 passed, 2 skipped in 2.0s\n', False),
                                             (1, '1 failed, 50 passed in 2.0s\n', False), (None, '', False))):
        seen = []
        raw = tmp_path / str(i)
        raw.mkdir()
        ok, detail = P.run_fixtures(ROOT, raw, run=lambda cmd, env=None, timeout=None: (
            seen.append((cmd, env['PYTHONPATH'], timeout)) or (rc, out, '')))
        assert ok is expected and (raw / 'fixtures_stdout.txt').read_text() == out
        assert seen == [([str(ROOT / '.venv/bin/python'), '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                          str(ROOT / 'tests/test_req012_repair.py')], str(ROOT / 'src'), 1800)]


def copy_root(tmp_path, rels):
    for rel in rels:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / rel, tmp_path / rel)


PRE_OK = lambda root: (True, OrderedDict(fixture='preflight passed'))  # noqa: E731


def fake_shell(docker=(0, 'sweb.eval.x86_64.other\n', ''), ls_files=0, diff=0, ps=''):
    def run(cmd, env=None, timeout=None):
        if cmd[0] == 'git':
            return (ls_files if 'ls-files' in cmd else diff), '', ''
        if cmd[0] == 'ps':
            return 0, ps, ''
        assert cmd[:3] == ['docker', 'ps', '-a'] and env['DOCKER_HOST'].startswith('unix://')
        return docker
    return run


def test_the_gate_preflight_is_read_only_and_refuses_on_any_failure():
    ok_manifest = lambda root: (True, OrderedDict(problems=[]))  # noqa: E731
    ok, d = P.gate_preflight(ROOT, fake_shell(), ok_manifest)
    assert ok and d['minisweagent_containers_listed'] == [] and d['sources_not_tracked_or_changed'] == []
    for run, manifest in ((fake_shell(docker=(0, 'minisweagent-1a2b3c4d\n', '')), ok_manifest),
                          (fake_shell(docker=(1, '', 'no daemon')), ok_manifest),
                          (fake_shell(ls_files=1), ok_manifest), (fake_shell(diff=1), ok_manifest),
                          (fake_shell(ps='99999 1 python experiments/v2_agent/req012_pair.py --gate\n'), ok_manifest),
                          (fake_shell(), lambda root: (False, OrderedDict(problems=['caps differ'])))):
        assert P.gate_preflight(ROOT, run, manifest)[0] is False


def test_a_failed_preflight_refuses_the_gate_before_its_namespace(tmp_path):
    copy_root(tmp_path, [P.MANIFEST_REL])
    called = []
    probes = OrderedDict(container=lambda root: called.append(root) or (True, {}))
    refuse = lambda root: (False, OrderedDict(minisweagent_containers_listed=['minisweagent-1a2b3c4d']))  # noqa: E731
    assert P.main(['--gate'], root=tmp_path, probes=probes, preflight=refuse) == 3
    assert called == [] and not (tmp_path / 'work').exists() and not (tmp_path / 'results').exists()
    assert P.main(['--gate'], root=tmp_path, probes=probes, preflight=PRE_OK) == 0 and len(called) == 1


def test_the_gate_is_single_shot_short_circuits_records_digests_and_a_failed_gate_blocks_the_probe(tmp_path):
    copy_root(tmp_path, [P.MANIFEST_REL])
    later = []
    probes = OrderedDict(passing=lambda root: (True, {'fixture': 1}), crashing=lambda root: 1 / 0,
                         container=lambda root: later.append(root) or (True, {}))
    assert P.main(['--gate'], root=tmp_path, probes=probes, preflight=PRE_OK) == 2
    pub = tmp_path / P.OUTPUTS['published']
    rec = json.loads((pub / 'gate.json').read_text())
    assert (rec['passed'], rec['checks_ok'], rec['passing']['ok'], rec['crashing']['ok'], rec['interrupted']) == (
        False, False, True, False, None)
    assert rec['crashing']['detail']['error'].startswith('ZeroDivisionError')
    assert later == [] and rec['container']['ok'] is False and rec['container']['detail']['skipped']
    assert rec['preflight'] == dict(fixture='preflight passed')
    assert (rec['manifest_sha256'], rec['configuration'], rec['sources_stable_during_gate']) == (
        MANIFEST_SHA, 'yaml-v1-repair1', True)
    assert list(rec['source_digests']) == list(P.SOURCES) and rec['source_digests'][P.MANIFEST_REL] == MANIFEST_SHA
    assert json.loads((tmp_path / P.OUTPUTS['raw'] / 'gate' / 'gate.json').read_text())['passed'] is False
    assert P.main(['--gate'], root=tmp_path, probes=probes, preflight=PRE_OK) == 3        # a second gate refuses
    assert P.main([], root=tmp_path, probes=OrderedDict(ok=lambda root: (True, {}))) == 3
    assert not (tmp_path / P.OUTPUTS['raw'] / 'probe').exists() and not (pub / 'probe').exists()


def test_a_signal_during_the_gate_is_recorded_after_the_container_is_removed(tmp_path):
    copy_root(tmp_path, [P.MANIFEST_REL])
    events = []

    def container(root):
        d = OrderedDict()

        def work(env):
            os.kill(os.getpid(), signal.SIGTERM)                                # e.g. a tool timeout or closed terminal
            events.append('not reached')
            return True
        return P.container_session(lambda: events.append('start') or 'env', work,
                                   lambda env: events.append(('cleanup', env)), d), d
    probes = OrderedDict(passing=lambda root: (True, {}), container=container,
                         after=lambda root: events.append('after') or (True, {}))
    def not_armed(signum, frame):
        raise AssertionError('the gate did not arm its own handler')
    previous = signal.signal(signal.SIGTERM, not_armed)
    try:
        handlers = [signal.getsignal(s) for s in P.SIGNALS]
        assert P.main(['--gate'], root=tmp_path, probes=probes, preflight=PRE_OK) == 2
        assert [signal.getsignal(s) for s in P.SIGNALS] == handlers            # restored afterwards
    finally:
        signal.signal(signal.SIGTERM, previous)
    assert events == ['start', ('cleanup', 'env')]
    for rec in (json.loads((tmp_path / P.OUTPUTS['published'] / 'gate.json').read_text()),
                json.loads((tmp_path / P.OUTPUTS['raw'] / 'gate' / 'gate.json').read_text())):
        assert (rec['passed'], rec['interrupted'], rec['container']['ok']) == (False, 'SIGTERM', False)
        assert rec['container']['detail']['interrupted'] == 'SIGTERM' and rec['after']['detail']['skipped']


def test_a_signal_between_gate_checks_is_recorded_and_ends_the_gate(tmp_path):
    copy_root(tmp_path, [P.MANIFEST_REL])

    def fixtures(root):
        raise S.Interrupted('SIGHUP')
    probes = OrderedDict(fixtures=fixtures, container=lambda root: (True, {}))
    assert P.main(['--gate'], root=tmp_path, probes=probes, preflight=PRE_OK) == 2
    rec = json.loads((tmp_path / P.OUTPUTS['published'] / 'gate.json').read_text())
    assert (rec['passed'], rec['interrupted'], rec['fixtures']['detail'], rec['container']['ok']) == (
        False, 'SIGHUP', dict(interrupted='SIGHUP'), False)


def test_the_container_session_always_cleans_up_and_repeats_a_cleanup_cut_short_by_a_signal():
    calls, d = [], OrderedDict()

    def cleanup(env):
        calls.append(env)
        if len(calls) == 1:
            raise S.Interrupted('SIGTERM')                                       # the first signal hits the cleanup
    assert P.container_session(lambda: 'env', lambda env: True, cleanup, d) is False
    assert calls == ['env', 'env'] and d == dict(interrupted='SIGTERM', cleanup_repeated_after_signal=True)
    calls, d = [], OrderedDict()

    def failing_start():
        raise RuntimeError('docker run timed out')
    assert P.container_session(failing_start, lambda env: True, lambda env: calls.append(env), d) is False
    assert calls == [None] and d['error'] == 'RuntimeError: docker run timed out'
    calls, d = [], OrderedDict()
    assert P.container_session(lambda: 'env', lambda env: True, lambda env: calls.append(env), d) is True
    assert calls == ['env'] and d == {}


GATE_DOCKER = r'''#!%(python)s
"""fake docker for the REQ-012 gate container fixture: canned outputs per command; never a real container"""
import json, os, sys
state = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'state')
cfg = json.load(open(os.path.join(state, 'config.json')))
args, names = sys.argv[1:], os.path.join(state, 'names')
with open(os.path.join(state, 'calls.jsonl'), 'a') as fh:
    fh.write(json.dumps(args) + '\n')
listed = [x for x in open(names).read().split() if x] if os.path.exists(names) else list(cfg['preexisting'])
def save(xs):
    open(names, 'w').write(' '.join(xs))
if args[0] == 'run':
    save(listed + [args[args.index('--name') + 1]])
    open(os.path.join(state, 'run_argv.json'), 'w').write(json.dumps(args))
    if cfg['run_fails']:
        sys.stderr.write('docker: error after creating the container\n')
        sys.exit(125)
    print(cfg['cid'])
elif args[:2] == ['ps', '-a']:
    ours = {n: cfg['cid'] for n in listed if n.startswith('minisweagent-') and not cfg['run_fails']}
    print('\n'.join(('%%s %%s' %% (ours.get(n, 'f' * 64), n)) if '{{.ID}} {{.Names}}' in args else n for n in listed))
elif args[:2] == ['container', 'inspect']:
    if not any(n.startswith('minisweagent-') for n in listed):
        sys.stderr.write('Error: No such container: %%s\n' %% args[-1])
        sys.exit(1)
    run = json.load(open(os.path.join(state, 'run_argv.json')))
    print(run[run.index('--network') + 1] if 'NetworkMode' in args[3] else 'false')
elif args[0] == 'stop':
    pass
elif args[:2] == ['rm', '-f']:
    save([n for n in listed if n not in args[2:] and not (args[2:] == [cfg['cid']] and n.startswith('minisweagent-'))])
elif args[0] == 'exec':
    rc, out = cfg['outputs'][args[-1]]
    sys.stdout.write(out)
    sys.exit(rc)
else:
    sys.exit(2)
'''
GATE_HARNESS = '''import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[2])
import req012_pair as P
cfg = json.loads(Path(sys.argv[1]).read_text())
ok, d = P.gate_container(P.ROOT, json.loads((P.ROOT / P.MANIFEST_REL).read_text()), Path(cfg['raw']))
Path(cfg['out']).write_text(json.dumps(dict(ok=ok, detail=d), default=str))
'''


def run_gate_container(base, run_fails=False, preexisting=(), ownership_exists=False):
    if not MSWEA_PY.exists() or not T11.DATA.exists():
        pytest.skip('pinned mini-swe-agent venv or the pinned SWE-bench Verified parquet is absent')
    home = base / 'home'
    bindir = home / '.local/dtr-runtime/bin'
    (bindir / 'state').mkdir(parents=True)
    (bindir / 'docker').write_text(GATE_DOCKER % dict(python=sys.executable))
    (bindir / 'docker').chmod(0o755)
    outputs = {P.GATE_COMMANDS[k]: list(GOOD[k]) for k in P.GATE_COMMANDS}
    (bindir / 'state' / 'config.json').write_text(json.dumps(dict(cid=CID, run_fails=run_fails, outputs=outputs,
                                                                  preexisting=list(preexisting))))
    (base / 'raw').mkdir()
    if ownership_exists:                               # the write-once ownership record fails after the start
        (base / 'raw' / 'container_ownership.json').write_text('{}\n')
    (base / 'cfg.json').write_text(json.dumps(dict(raw=str(base / 'raw'), out=str(base / 'out.json'))))
    (base / 'harness.py').write_text(GATE_HARNESS)
    proc = subprocess.run([str(MSWEA_PY), str(base / 'harness.py'), str(base / 'cfg.json'),
                           str(ROOT / 'experiments/v2_agent')], capture_output=True, text=True,
                          env=child_env(home, base), timeout=300, cwd=str(base))
    assert proc.returncode == 0, proc.stderr[-4000:]
    calls = [json.loads(x) for x in (bindir / 'state' / 'calls.jsonl').read_text().splitlines()]
    return json.loads((base / 'out.json').read_text()), calls, base / 'raw'


def test_the_gate_container_runs_every_check_in_one_no_egress_container_and_removes_it(tmp_path):
    out, calls, raw = run_gate_container(tmp_path)
    d = out['detail']
    assert out['ok'] is True and all(r['ok'] for r in d['checks'].values()) and list(d['checks']) == ORDER
    assert (d['base_commit'], d['network']['network_mode'], d['minisweagent_containers_listed_before']) == (
        BASE_COMMIT, 'none', [])
    run = next(c for c in calls if c[0] == 'run')
    assert run[run.index('-w') + 1] == '/testbed' and run[-3:] == [PIN, 'sleep', '2h']
    assert run[:2] == ['run', '-d'] and run[run.index('-w') + 2:-3] == REPAIR_RUN_ARGS   # exactly the repair1 run_args
    assert [c[-1] for c in calls if c[0] == 'exec'] == [P.GATE_COMMANDS[x[-2:] if x.startswith('G5_then_') else x]
                                                         for x in ORDER]
    assert all(c[c.index('-w') + 1] == '/testbed' and c[-3:-1] == ['bash', '-lc'] for c in calls if c[0] == 'exec')
    assert (d['cleanup']['confirmed'], d['removal']['complete'], d['minisweagent_containers_listed_after']) == (
        True, True, [])
    assert json.loads((raw / 'container_ownership.json').read_text()) == dict(container_id=CID)
    assert d['instance_template_repair1'] == d['instance_template_frozen'].replace(
        ANCHOR, ANCHOR + LEAD_ADDITION + '\n')


def test_a_failed_gate_container_start_is_cleaned_up_by_name_and_a_listed_container_blocks_the_start(tmp_path):
    out, calls, _ = run_gate_container(tmp_path / 'fails', run_fails=True)
    d = out['detail']
    name = next(c for c in calls if c[0] == 'run')[3]
    assert out['ok'] is False and d['error'].startswith('CalledProcessError') and d['checks'] is None
    assert (d['removed_by_name_after_a_failed_start'], d['removal']['complete'],
            d['minisweagent_containers_listed_after']) == ([name], True, [])
    assert ['rm', '-f', name] in calls and not any(c[0] == 'exec' for c in calls)
    out, calls, _ = run_gate_container(tmp_path / 'owned', ownership_exists=True)
    d = out['detail']
    assert out['ok'] is False and d['error'].startswith('FileExistsError') and d['checks'] is None
    assert (d['cleanup']['confirmed'], d['removed_by_name_after_a_failed_start'], d['removal']['refs'],
            d['minisweagent_containers_listed_after']) == (True, [], [CID], [])      # removed by its recorded ID
    out, calls, _ = run_gate_container(tmp_path / 'listed', preexisting=['minisweagent-0000beef'])
    d = out['detail']
    assert out['ok'] is False and d['error'].startswith('RuntimeError: not started')
    assert not any(c[0] in ('run', 'rm', 'stop', 'exec') for c in calls)                   # never touches it
    assert d['minisweagent_containers_listed_after'] == ['minisweagent-0000beef']


def write_gate(root, record, raw_record=None):
    for path, rec in ((root / P.OUTPUTS['published'] / 'gate.json', record),
                      (root / P.OUTPUTS['raw'] / 'gate' / 'gate.json', record if raw_record is None else raw_record)):
        path.parent.mkdir(parents=True, exist_ok=True)
        if rec is None:
            path.unlink(missing_ok=True)
        else:
            path.write_text(json.dumps(rec))


def test_the_probe_needs_a_passing_gate_for_this_manifest_and_these_sources(tmp_path):
    copy_root(tmp_path, P.SOURCES)
    assert P.probe_gate(tmp_path)[0] is False                                     # no gate record
    good = dict(passed=True, interrupted=None, manifest_sha256=MANIFEST_SHA, started_utc='a', finished_utc='b',
                source_digests=dict(P.source_digests(tmp_path)))
    for record, raw, expected in ((good, None, True), (dict(good, passed=False), None, False),
                                  (dict(good, manifest_sha256='0' * 64), None, False),
                                  (dict(good, source_digests=dict(good['source_digests'], **{P.FIXTURES: '0' * 64})),
                                   None, False),
                                  (dict(good, source_digests={}), None, False),
                                  (good, dict(good, passed=False), False),       # the raw copy disagrees
                                  (good, dict(good, finished_utc='c'), False)):
        write_gate(tmp_path, record, raw)
        assert P.probe_gate(tmp_path)[0] is expected
    write_gate(tmp_path, good)
    (tmp_path / P.OUTPUTS['raw'] / 'gate' / 'gate.json').unlink()
    ok, detail = P.probe_gate(tmp_path)
    assert not ok and detail['raw_present'] is False                            # no raw copy
    write_gate(tmp_path, good)
    entry = tmp_path / 'experiments/v2_agent/req012_entry.py'
    entry.write_text(entry.read_text() + '\n# changed after the gate\n')
    ok, detail = P.probe_gate(tmp_path)
    assert not ok and detail['changed_sources'] == ['experiments/v2_agent/req012_entry.py']


def test_the_probe_is_single_shot_and_always_writes_its_summary(tmp_path):
    copy_root(tmp_path, [P.MANIFEST_REL] + list(P.PRIOR_RESULTS))
    gate_ok = lambda root: (True, {'fixture': 'passing gate'})  # noqa: E731

    def runner(ctx):
        ctx['ledger'].start(1, run_id='run-1')
        (ctx['raw'] / 'run-1').mkdir()
        raise S.Interrupted('SIGTERM')
    probes = OrderedDict(ok=lambda root: (True, {}))
    assert P.main([], root=tmp_path, probes=probes, runner=runner, gate_check=gate_ok) == 0
    pub = tmp_path / P.OUTPUTS['published'] / 'probe'
    summary = json.loads((pub / 'pair_summary.json').read_text())
    assert (summary['status'], summary['interrupted_or_error'], summary['probe_cap_s']) == ('INTERRUPTED', 'SIGTERM', 3600)
    assert [(x['order'], x['state'], x.get('run_id')) for x in summary['assignments']] == [(1, 'interrupted', 'run-1')]
    assert summary['requests']['physical_counted_total'] == 48 and summary['requests']['max_logical'] == 24
    prior = summary['prior_results']
    assert all(prior[rel]['unchanged'] for rel in P.PRIOR_RESULTS)
    assert prior['req011_eligible_submissions'] == dict(eligible=0, of=2)
    assert P.main([], root=tmp_path, probes=probes, runner=runner, gate_check=gate_ok) == 3    # a second launch
    blocked = tmp_path / 'blocked'
    copy_root(blocked, [P.MANIFEST_REL])
    assert P.main([], root=blocked, probes=OrderedDict(memory=lambda root: (False, {})), gate_check=gate_ok) == 2
    summary = json.loads((blocked / P.OUTPUTS['published'] / 'probe' / 'pair_summary.json').read_text())
    assert (summary['status'], summary['failed_admission_checks'], summary['assignments'][0]['state']) == (
        'BLOCKED', ['memory'], 'not_started: probe blocked')
    assert not (blocked / P.OUTPUTS['raw'] / 'probe' / 'ledger.jsonl').exists()
