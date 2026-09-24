"""DTR-REQ-013 fixtures (lead 702e58a, docs/theory_feedback_20260924_req012_decision.md).

Covered: (a) the reconciliation of the published REQ-012 probe, which fails closed on any mutated value; (b) the 14B
repair1 binding. That binding is checked in the manifest (against the REQ-011 and REQ-012 manifests) and in the
configuration proof. It is also checked end to end, by running the unedited req012_entry through req013_entry with a
14B control next to the REQ-012 7B control, in the pinned mini-swe-agent venv; (c) the swap gate; (d) the probe
precondition (the REQ-012 gate record and the configuration match); (e) single-shot launches and the always-written
summary. Also covered: the REQ-013 ownership holder and watchdog launcher, and the fail-closed watchdog host check.

There is no model, llama.cpp server, container, evaluator or network: only fakes and stubs. The entry fixtures use the
committed, unedited REQ-011 harness (experiments/tools/req011_integration_harness.py) through a one-line shim, as the
REQ-012 fixtures do. Those fixtures skip when the pinned venv or the dataset is absent. Expected values are literals from
the lead decision, the REQ-011/REQ-012 manifests and the published REQ-012 records, not values computed by the code
under test.
"""
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / 'experiments/v2_agent', ROOT / 'experiments/tools', Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import req013_pair as P  # noqa: E402
import req013_reconcile as C  # noqa: E402
import req013_watchdog_check as W  # noqa: E402
import test_req011_pair as T11  # noqa: E402  helpers only; not re-collected
import test_req012_repair as T12  # noqa: E402  helpers only; not re-collected

P12, P11, S, R = P.P12, P.P11, P.S, P.R
MANIFEST_PATH = ROOT / 'configs/v2_req013_14b_discriminator_20260924.json'
MANIFEST = json.loads(MANIFEST_PATH.read_text())
MANIFEST_SHA = hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
M11 = json.loads((ROOT / 'configs/v2_req011_competence_pair_20260924.json').read_text())
M12 = T12.MANIFEST
IID, PIN = T11.IID, T11.PIN
LARGE_ALIAS, LARGE_SHA, SMALL_ALIAS, SMALL_SHA = T11.LARGE_ALIAS, T11.LARGE_SHA, T11.SMALL_ALIAS, T11.SMALL_SHA
REPAIR_RUN_ARGS = ['--rm', '--platform', 'linux/amd64', '--network', 'none']
REPAIR1_TEMPLATE_SHA = 'da5fe0813e040399492196027cc45f091ddb7cf76f6df9165d6e189ca32b27f3'
F2P = 'astropy/io/fits/tests/test_header.py::TestHeaderFunctions::test_long_string_value_with_quotes'
SUBMISSION_SHA = 'c50aa65cd1d1c6e3271dd76c6c007ce03270c650db795987ff2a81fc123746a6'
GiB = 1 << 30


def sha(data):
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------- (a) the reconciliation fails closed

PROBE = 'results/v2_agent/req012_repair_probe_20260924/probe'
RUN = 'astropy__astropy-14598__small__req011__20260924T184420Z-7bfc39'
D = PROBE + '/' + RUN
REPORT = (PROBE + '/grading/logs/run_evaluation/eval-%s-c50aa65cd1d1c6e3-a1/%s/%s/report.json' % (RUN, SMALL_ALIAS, IID))
GIT_OK = lambda cmd, env=None, timeout=None: (0, '', '')  # noqa: E731


def reconcile_root(tmp_path):
    shutil.copytree(ROOT / PROBE, tmp_path / PROBE)
    (tmp_path / 'configs').mkdir()
    shutil.copyfile(ROOT / 'configs/v2_req012_repair_probe_20260924.json',
                    tmp_path / 'configs/v2_req012_repair_probe_20260924.json')
    return tmp_path


def rewrite(root, rel, data, republish=True):
    (root / rel).write_bytes(data)
    if republish and rel.startswith(PROBE + '/'):
        pm = root / PROBE / 'publication_manifest.json'
        m = json.loads(pm.read_text())
        m[rel[len(PROBE) + 1:]]['published_sha256'] = sha(data)
        pm.write_text(json.dumps(m))


def edit_json(root, rel, fn, republish=True):
    obj = json.loads((root / rel).read_text())
    fn(obj)
    rewrite(root, rel, json.dumps(obj, indent=1).encode(), republish)


def edit_lines(root, rel, fn):
    rows = fn([json.loads(x) for x in (root / rel).read_text().splitlines() if x.strip()])
    rewrite(root, rel, ''.join(json.dumps(x) + '\n' for x in rows).encode())


def edit_tests_status(root, fn):
    """The same change in the grade record (and its required_status) and in the stock report."""
    def grade(g):
        fn(g['upstream_report'][IID]['tests_status'], g['required_status'])
    edit_json(root, D + '/grade.json', grade)
    edit_json(root, REPORT, lambda r: fn(r[IID]['tests_status'], {}))


def f2p_passes(ts, required):
    ts['FAIL_TO_PASS'] = dict(success=[F2P], failure=[])
    required[F2P] = 'PASSED'


def p2p_fails(ts, required):
    t = ts['PASS_TO_PASS']['success'].pop(0)
    ts['PASS_TO_PASS']['failure'].append(t)
    required[t] = 'FAILED'


def source_diff(root):
    diff = (b'diff --git a/astropy/io/fits/card.py b/astropy/io/fits/card.py\n--- a/astropy/io/fits/card.py\n'
            b'+++ b/astropy/io/fits/card.py\n@@ -1 +1 @@\n-x\n+y\n')
    rewrite(root, D + '/submission.diff', diff)
    edit_json(root, D + '/episode.json', lambda e: e.update(submission_sha256=sha(diff), submission_bytes=len(diff)))
    edit_json(root, D + '/grade.json', lambda g: g.update(submission_sha256=sha(diff)))
    edit_json(root, PROBE + '/pair_summary.json', lambda s: s['assignments'][0].update(submission_sha256=sha(diff)))


def strict_resolved(root):
    edit_json(root, D + '/grade.json', lambda g: g.update(strict_outcome='resolved'))
    edit_json(root, PROBE + '/pair_summary.json', lambda s: s['assignments'][0]['grade'].update(
        strict_outcome='resolved'))


def extra_observation(root):
    edit_json(root, D + '/trajectory.json', lambda t: t['messages'].insert(4, copy.deepcopy(t['messages'][3])))


def format_error_executed(root):
    edit_lines(root, D + '/calls.jsonl', lambda rows: rows[:5] + [dict(event='observation', call=2, returncode=0)]
               + rows[5:])


MUTATIONS = dict(
    model_calls=lambda root: edit_json(root, D + '/episode.json', lambda e: e.update(n_model_calls=4)),
    physical_requests=lambda root: edit_json(root, D + '/episode.json', lambda e: e.update(physical_requests=4)),
    extra_observation=extra_observation,
    format_error_one_action=lambda root: edit_json(root, D + '/trajectory.json', lambda t: t['messages'][4][
        'extra'].update(n_actions=1)),
    format_error_executed=format_error_executed,
    final_action=lambda root: edit_json(root, D + '/trajectory.json', lambda t: t['messages'][5]['extra'][
        'actions'][0].update(command='ls')),
    exit_status=lambda root: edit_json(root, D + '/trajectory.json', lambda t: t['messages'][-1]['extra'].update(
        exit_status='LimitsExceeded')),
    missing_outcome_receipt=lambda root: (root / D / 'receipts/call003_attempt01.outcome.json').unlink(),
    receipt_not_ok=lambda root: edit_json(root, D + '/receipts/call002_attempt01.outcome.json',
                                          lambda o: o.update(outcome='error')),
    diff_byte=lambda root: rewrite(root, D + '/submission.diff', (root / D / 'submission.diff').read_bytes() + b'\n'),
    diff_touches_source=source_diff,
    grade_submission_sha=lambda root: edit_json(root, D + '/grade.json', lambda g: g.update(
        submission_sha256='0' * 64)),
    f2p_passes=lambda root: edit_tests_status(root, f2p_passes),
    p2p_fails=lambda root: edit_tests_status(root, p2p_fails),
    stock_report_differs=lambda root: edit_json(root, REPORT, lambda r: r[IID].update(resolved=True)),
    strict_resolved=strict_resolved,
    image_after=lambda root: edit_json(root, D + '/control/grade_result.json', lambda g: g.update(
        image_after='sha256:' + '1' * 64)),
    image_pin=lambda root: edit_json(root, 'configs/v2_req012_repair_probe_20260924.json', lambda m: m['images'][
        'instance'].update(id='sha256:' + '2' * 64)),
    guard_fired=lambda root: edit_json(root, D + '/control/repair_record.json', lambda r: r['guard'].update(
        fired=True)),
    ledger_without_end=lambda root: edit_lines(root, PROBE + '/ledger.jsonl', lambda rows: rows[:1]),
    unpublished_edit=lambda root: edit_json(root, D + '/episode.json', lambda e: e.update(wall_seconds=1.0),
                                            republish=False))


def test_the_reconciliation_states_the_lead_facts_from_the_committed_records(tmp_path):
    root = reconcile_root(tmp_path)
    record, problems = C.reconcile(root, run=GIT_OK)
    assert problems == []
    obs, f = record['observed'], record['facts']
    assert (obs['model_calls'], obs['executed_tool_commands'], obs['format_error_turns'],
            obs['format_error_proposed_actions'], obs['format_error_actions_executed']) == (3, 1, 1, 2, 0)
    assert (obs['final_action'], obs['exit_status']) == ('echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT', 'Submitted')
    assert (obs['request_receipts'], obs['outcome_receipts']) == (3, 3)
    assert (f['submission']['bytes'], f['submission']['sha256'], f['submission']['files'],
            f['submission']['new_files'], f['submission']['source_files']) == (
        466, SUBMISSION_SHA, ['test_fits_card.py'], ['test_fits_card.py'], [])
    assert (f['grade']['fail_to_pass'], f['grade']['failing_fail_to_pass_tests'], f['grade']['pass_to_pass'],
            f['grade']['strict_outcome']) == ([0, 1], [F2P], [175, 175], 'unresolved')
    assert f['image']['before'] == f['image']['after'] == f['image']['pin'] == PIN
    proposed = f['transcript']['calls'][1]['proposed_actions']
    assert [(p['would_write_files'], p['defines_python_functions'], p['is_submit_command'], p['executed'],
             p['repository_source_paths']) for p in proposed] == [
        (['patch_fits_card.py'], ['fix_fits_card'], False, False, []), ([], [], True, False, [])]
    assert proposed[0]['string_replace_calls'] == ['"\'\'", "\'"']          # '' -> ' in the parsed value only
    assert record['verified'] is True and 'strict unresolved' in record['statement']
    assert C.main(root=root, run=GIT_OK) == 0
    written = json.loads((root / C.OUT).read_text())
    assert written['observed'] == obs and written['verified'] is True
    assert C.main(root=root, run=GIT_OK) == 3                                  # write-once


@pytest.mark.parametrize('name', sorted(MUTATIONS))
def test_the_reconciliation_fails_closed_on_any_mutated_value(tmp_path, name):
    root = reconcile_root(tmp_path)
    MUTATIONS[name](root)
    record, problems = C.reconcile(root, run=GIT_OK)
    assert record is None and problems
    assert C.main(root=root, run=GIT_OK) == 2 and not (root / C.OUT).exists()


def test_the_reconciliation_refuses_uncommitted_inputs(tmp_path):
    root = reconcile_root(tmp_path)
    for run in (lambda cmd, env=None, timeout=None: (1 if 'ls-files' in cmd else 0, '', ''),
                lambda cmd, env=None, timeout=None: (1 if 'diff' in cmd else 0, '', '')):
        assert C.reconcile(root, run=run)[0] is None
        assert C.main(root=root, run=run) == 2 and not (root / C.OUT).exists()


# ---------------------------------------------------------------- (b) the 14B repair1 binding

def test_the_manifest_carries_the_lead_values_and_binds_to_the_code():
    assert (MANIFEST['request'], MANIFEST['lead_commit'], MANIFEST['source_commit'], MANIFEST['instance_id'],
            MANIFEST['lead_decision']) == ('DTR-REQ-013', '702e58a', '8bcca8a', IID,
                                           'docs/theory_feedback_20260924_req012_decision.md')
    assert [(a['order'], a['assignment_id'], a['backend'], a['arm'], a['port'], a['alias'], a['gguf_sha256'],
             a['gguf_bytes'], a['model']) for a in MANIFEST['assignments']] == [
        (1, 'req013-1-large', 'large', 'baseline', 8293, LARGE_ALIAS, LARGE_SHA, 8988110944,
         'Qwen/Qwen2.5-Coder-14B-Instruct')]
    assert dict(MANIFEST['assignments'][0], assignment_id=None) == dict(M11['assignments'][0], assignment_id=None)
    for k in ('images', 'settings', 'repair1', 'prompt_bytes', 'serving', 'evaluator', 'caps', 'memory_rule',
              'disk_rule', 'watchdog'):
        assert MANIFEST[k] == M12[k], k                                       # identical to REQ-012
    c = MANIFEST['caps']
    assert (c['pair_wall_s'], c['episode_load_allowance_s'], c['grading_floor_s'], c['max_logical_requests'],
            c['max_physical_requests']) == (3600, 300, 900, 24, 48)
    assert (MANIFEST['repair1']['run_args'], MANIFEST['prompt_bytes']['instance_template_repair1_sha256']) == (
        REPAIR_RUN_ARGS, REPAIR1_TEMPLATE_SHA)
    s = MANIFEST['swap_rule']
    assert (s['command'], s['min_free_bytes'], s['min_free_gib']) == (['sysctl', '-n', 'vm.swapusage'], 4 * GiB, 4)
    assert 'already allocated' in s['note']
    assert MANIFEST['precondition']['req012_manifest_sha256'] == T12.MANIFEST_SHA
    assert MANIFEST['precondition']['req012_entry_sha256'] == json.loads(
        (ROOT / D / 'control/repair_record.json').read_text())['entry_source_sha256']
    assert P.manifest_problems(MANIFEST, T11.CONV, T11.REQ010, M11, M12) == []
    assert all(MANIFEST[k] for k in ('declared_rules', 'interpretations', 'inherited_labels', 'semantics_differences',
                                     'scope'))


MANIFEST_MUTATIONS = dict(
    second_model=lambda m: m['assignments'].append(dict(m['assignments'][0], order=2, backend='small')),
    small_model=lambda m: m['assignments'][0].update(backend='small', port=8291, alias=SMALL_ALIAS,
                                                     gguf_sha256=SMALL_SHA),
    port=lambda m: m['assignments'][0].update(port=8291),
    cue_arm=lambda m: m['assignments'][0].update(arm='cue'),
    other_task=lambda m: m.update(instance_id='astropy__astropy-12907'),
    prompt=lambda m: m['repair1'].update(prompt_addition=m['repair1']['prompt_addition'] + ' Edit card.py.'),
    prompt_bytes=lambda m: m['prompt_bytes'].update(inserted_bytes=1),
    network=lambda m: m['repair1'].update(run_args=REPAIR_RUN_ARGS[:3]),
    guard=lambda m: m['repair1'].update(stall_rule='never'),
    output_cap=lambda m: m['settings'].update(max_tokens=4096),
    steps=lambda m: m['settings'].update(step_limit=48),
    cap=lambda m: m['caps'].update(pair_wall_s=7200),
    requests=lambda m: m['caps'].update(max_physical_requests=96),
    swap=lambda m: m['swap_rule'].update(min_free_bytes=3 * GiB),
    precondition=lambda m: m['precondition'].update(req012_manifest_sha256='0' * 64),
    text=lambda m: m.pop('scope'))


@pytest.mark.parametrize('name', sorted(MANIFEST_MUTATIONS))
def test_any_manifest_mismatch_fails_closed(name):
    m = copy.deepcopy(MANIFEST)
    MANIFEST_MUTATIONS[name](m)
    assert P.manifest_problems(m, T11.CONV, T11.REQ010, M11, M12) != []


@pytest.fixture(scope='module')
def pinned_cfg():
    if not T12.MSWEA_PY.exists():
        pytest.skip('pinned mini-swe-agent venv is absent')
    assert sha(T12.DEFAULT_YAML.read_bytes()) == '112aa58328f478a41cc2630702a4b89ef459e912870e05065157ed221f56701f'
    code = 'import json, sys, yaml; print(json.dumps(yaml.safe_load(open(sys.argv[1]).read())))'
    return json.loads(subprocess.run([str(T12.MSWEA_PY), '-c', code, str(T12.DEFAULT_YAML)], capture_output=True,
                                     text=True, check=True).stdout)


def test_the_14b_repair1_configuration_equals_the_7b_one_except_the_model_name_and_port(pinned_cfg):
    problems, proof = P.config_proof(pinned_cfg, M12['assignments'][0], MANIFEST['assignments'][0], PIN,
                                     REPAIR1_TEMPLATE_SHA)
    assert problems == []
    assert proof['differences'] == {
        'model.model_name': ['openai/' + SMALL_ALIAS, 'openai/' + LARGE_ALIAS],
        'model.model_kwargs.api_base': ['http://127.0.0.1:8291/v1', 'http://127.0.0.1:8293/v1']}
    assert (proof['instance_template_sha256'], proof['run_args'], proof['agent_class']) == (
        REPAIR1_TEMPLATE_SHA, REPAIR_RUN_ARGS, 'req012_entry.RepeatedFailureGuardAgent')
    assert proof['volatile_patterns'] == ['0x[0-9a-fA-F]+', r'\b[0-9]+\.[0-9]+s\b']     # the fingerprint rule
    frozen = R.PE.build_effective_config

    def port_dependent(cfg, **kw):                  # any other assignment-dependent field fails the proof
        out = frozen(cfg, **kw)
        out['environment']['timeout'] = kw['port']
        return out

    def alias_in_prompt(cfg, **kw):
        out = frozen(cfg, **kw)
        out['agent']['system_template'] += kw['alias']
        return out
    for build in (port_dependent, alias_in_prompt):
        assert P.config_proof(pinned_cfg, M12['assignments'][0], MANIFEST['assignments'][0], PIN,
                              REPAIR1_TEMPLATE_SHA, build)[0]
    assert P.config_proof(pinned_cfg, M12['assignments'][0], MANIFEST['assignments'][0], PIN, '0' * 64)[0]
    with pytest.raises(ValueError):                 # a base config without the frozen run_args cannot be repaired
        P.config_proof(pinned_cfg, M12['assignments'][0], MANIFEST['assignments'][0], PIN, REPAIR1_TEMPLATE_SHA,
                       lambda cfg, **kw: dict(frozen(cfg, **kw), environment=dict(run_args=['--rm'])))


SHIM = ('import sys\nsys.path.insert(0, %r)\nfrom req012_entry import A  # noqa: E402,F401\n'
        'from %s import main  # noqa: E402,F401\n')
ASSIGNMENTS = dict(small=('req012-1-small', SMALL_ALIAS, SMALL_SHA, 8291),
                   large=('req013-1-large', LARGE_ALIAS, LARGE_SHA, 8293))


def run_entry(base, module, backend, sources, runtime, binding, script, assignment_id=None):
    """req012_entry.main (directly, or through req013_entry) in the pinned venv via the unedited REQ-011 harness."""
    default_id, alias, model_sha, port = ASSIGNMENTS[backend]
    home, state = T12.workspace(base)
    shim = base / 'shim'
    shim.mkdir()
    (shim / 'req011_entry.py').write_text(SHIM % (str(ROOT / 'experiments/v2_agent'), module))
    run_id = '%s__%s__req013__fixture-%s' % (IID, backend, base.name)
    run_dir, control_dir, layout_root = base / 'raw' / run_id, base / 'raw' / 'control' / run_id, base / 'layout'
    for d in (run_dir, control_dir, layout_root / 'work'):
        d.mkdir(parents=True)
    control = dict(request='fixture', binding_sha256=binding, assignment_id=assignment_id or default_id,
                   model_sha256=model_sha, admitted_sources=sources, runtime=runtime, namespace=dict(
                       instance=IID, backend=backend, arm='baseline', position=1, port=port, alias=alias,
                       run_dir=str(run_dir), run_id=run_id, expected_image=PIN,
                       served=json.dumps(dict(model_file='fixture.gguf', model_sha256=model_sha)), counted_before=0,
                       request_limit=48, host_reserve_bytes=1 << 30))
    config = dict(out=str(base / 'out'), script=script, alias=alias, model_file='fixture.gguf', module_dir=str(shim),
                  layout_root=str(layout_root), control=control, control_path=str(control_dir / 'entry.json'),
                  deadline_in=600)
    (base / 'config.json').write_text(json.dumps(config))
    proc = subprocess.run([str(T12.MSWEA_PY), str(T12.REQ011_HARNESS), str(base / 'config.json')],
                          capture_output=True, text=True, env=T12.child_env(home, base), timeout=600, cwd=str(base))
    assert proc.returncode == 0, proc.stderr[-4000:]
    return dict(harness=json.loads((base / 'out' / 'harness.json').read_text()), run_dir=run_dir, control=control_dir,
                state=state, bodies=[p.read_bytes() for p in sorted((base / 'out' / 'terminal').glob('*.body'))])


@pytest.fixture(scope='module')
def entries(tmp_path_factory):
    if not T12.MSWEA_PY.exists() or not T11.DATA.exists():
        pytest.skip('pinned mini-swe-agent venv or the pinned SWE-bench Verified parquet is absent')
    digests = lambda rels: {rel: sha((ROOT / rel).read_bytes()) for rel in rels}  # noqa: E731
    binding, problems = P.A.compute_binding(P.A.Layout(ROOT))
    assert problems == []
    runtime = {k: binding['runtime'][k] for k in ('sdk_traced_files', 'mini_swe_agent_sources')}
    work = tmp_path_factory.mktemp('req013_entry')
    submitted, refused = T12.SCENARIOS['submitted']['script'], [T11.LS]
    s12, s13 = digests(P12.SOURCES), digests(P.SOURCES)
    return dict(
        small=run_entry(work / 'small', 'req012_entry', 'small', s12, runtime, T12.MANIFEST_SHA, submitted),
        large=run_entry(work / 'large', 'req013_entry', 'large', s13, runtime, MANIFEST_SHA, submitted),
        small_via_req013=run_entry(work / 'small13', 'req013_entry', 'small', s13, runtime, MANIFEST_SHA, refused),
        large_via_req012=run_entry(work / 'large12', 'req012_entry', 'large', s12, runtime, T12.MANIFEST_SHA,
                                   refused),
        large_unadmitted=run_entry(work / 'large_u', 'req013_entry', 'large', s12, runtime, MANIFEST_SHA, refused))


def test_the_14b_episode_gets_the_identical_repair1_prompt_environment_and_guard(entries):
    s, g = entries['small'], entries['large']
    for r in (s, g):
        assert (r['harness']['exit_code'], r['harness']['network_attempts'], len(r['bodies'])) == (0, [], 3)
    for small, large in zip(s['bodies'], g['bodies']):                  # the same bytes apart from the model alias
        assert small.count(SMALL_ALIAS.encode()) == large.count(LARGE_ALIAS.encode()) == 1
        assert large.replace(LARGE_ALIAS.encode(), SMALL_ALIAS.encode()) == small
        assert large.count(json.dumps(T12.LEAD_ADDITION)[1:-1].encode()) == 1
    for part in ('constructor_arguments', 'resolved'):
        a, b = (P.leaves(T11.effective(r['run_dir'])[part]) for r in (s, g))
        assert sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k)) == [
            'model.model_kwargs.api_base', 'model.model_name']
        assert (b['model.model_name'], b['model.model_kwargs.api_base']) == (
            'openai/' + LARGE_ALIAS, 'http://127.0.0.1:8293/v1')
    for r in (s, g):
        traj = json.loads((r['run_dir'] / 'trajectory.json').read_text())
        assert traj['info']['config']['agent_type'] == 'req012_entry.RepeatedFailureGuardAgent'
        argv = (r['state'] / 'run_argv').read_text().splitlines()      # what `docker run` received
        assert argv[argv.index('--network') + 1] == 'none'
    recs = [json.loads((r['control'] / 'repair_record.json').read_text()) for r in (s, g)]
    for rec in recs:
        assert (rec['configuration'], rec['guard']['agent_type'], rec['guard']['network']['network_mode'],
                rec['guard']['network']['run_args'], rec['effective_config']['verified'],
                rec['effective_config']['instance_template_sha256']) == (
            'yaml-v1-repair1', 'req012_entry.RepeatedFailureGuardAgent', 'none', REPAIR_RUN_ARGS, True,
            REPAIR1_TEMPLATE_SHA)
    assert [rec['request'] for rec in recs] == ['DTR-REQ-012', 'DTR-REQ-013']
    assert recs[0]['stall_rule'] == recs[1]['stall_rule'] == MANIFEST['repair1']['stall_rule']
    assert recs[0]['entry_source_sha256'] == recs[1]['entry_source_sha256'] == MANIFEST['precondition'][
        'req012_entry_sha256']
    admitted = json.loads((g['control'] / 'entry_admitted.json').read_text())
    assert (admitted['request'], admitted['runtime_overrides']) == ('DTR-REQ-013', MANIFEST['repair1'][
        'runtime_overrides'])
    assert admitted['running_sources']['req013_entry.py'] == sha(
        (ROOT / 'experiments/v2_agent/req013_entry.py').read_bytes())
    ep = json.loads((g['run_dir'] / 'episode.json').read_text())
    assert (ep['exit_status'], ep['logical_calls'], ep['binding_sha256'], ep['backend'], ep['assignment_id']) == (
        'Submitted', 3, MANIFEST_SHA, 'large', 'req013-1-large')
    assert (g['run_dir'] / 'submission.diff').read_bytes() == T11.MOD_NEW_DIFF == (
        s['run_dir'] / 'submission.diff').read_bytes()


def test_each_entry_refuses_the_other_requests_assignment_and_an_unadmitted_req013_entry(entries):
    for name, reason in (('small_via_req013', 'the assignment (id, order, backend, port, alias, model sha256) is not '
                                              'a manifest assignment'),
                         ('large_via_req012', 'the assignment (id, order, backend, port, alias, model sha256) is not '
                                              'a manifest assignment'),
                         ('large_unadmitted', 'running req013_entry.py is not the admitted source')):
        r = entries[name]
        assert (r['harness']['exit_code'], r['bodies'], r['harness']['network_attempts']) == (3, [], []), name
        reasons = json.loads((r['control'] / 'entry_refused.json').read_text())['reasons']
        assert reason in reasons, (name, reasons)
        assert not (r['control'] / 'entry_admitted.json').exists() and list(r['run_dir'].iterdir()) == []


# ---------------------------------------------------------------- (c) the swap gate

def swap_run(out, rc=0):
    calls = []

    def run(cmd, env=None, timeout=None):
        calls.append(cmd)
        return rc, out, ''
    return run, calls


SWAP_39 = 'total = 15360.00M  used = 11366.40M  free = 3993.60M  (encrypted)\n'        # 3.9 GiB
SWAP_40 = 'total = 15360.00M  used = 11264.00M  free = 4096.00M  (encrypted)\n'        # 4.0 GiB
SWAP_NOW = 'total = 15360.00M  used = 14994.44M  free = 365.56M  (encrypted)\n'        # the worker's 19:46Z reading


def test_the_swap_gate_reads_unused_swap_and_fails_closed():
    for out, rc, expected, gib in ((SWAP_39, 0, False, 3.9), (SWAP_40, 0, True, 4.0), (SWAP_NOW, 0, False, 0.357),
                                   ('total = 16.00G  used = 11.50G  free = 4.50G  (encrypted)', 0, True, 4.5)):
        run, calls = swap_run(out, rc)
        ok, d = P.probe_swap(ROOT, run)
        assert (ok, d['free_gib']) == (expected, gib) and calls == [['sysctl', '-n', 'vm.swapusage']]
    assert P.probe_swap(ROOT, swap_run(SWAP_40)[0])[1]['free_bytes'] == 4 * GiB
    for out, rc in (('', 0), ('garbage', 0), (SWAP_40, 1), (SWAP_40, None), (SWAP_40 + SWAP_40, 0),
                    ('total = 15360.00M  used = 1.00M  free = 5000.00T', 0), ('free = M', 0)):
        ok, d = P.probe_swap(ROOT, swap_run(out, rc)[0])
        assert ok is False and d['free_bytes'] is None, out


def ok_check(root):
    return True, OrderedDict(fixture='passing')


def test_a_capacity_block_starts_nothing_and_consumes_nothing(tmp_path, capsys):
    T12.copy_root(tmp_path, [P.MANIFEST_REL])
    started = []
    runner = lambda ctx: started.append(ctx) or None  # noqa: E731
    probes = OrderedDict(ok=ok_check)
    swap39 = lambda root: P.probe_swap(root, swap_run(SWAP_39)[0])  # noqa: E731
    assert P.main([], root=tmp_path, probes=probes, runner=runner, precondition=ok_check, swap=swap39) == 4
    printed = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert (printed['status'], printed['started'], printed['namespace_created']) == ('BLOCKED_FOR_CAPACITY', False,
                                                                                     False)
    assert printed['swap']['free_gib'] == 3.9
    assert started == [] and not (tmp_path / 'work').exists() and not (tmp_path / 'results').exists()
    swap40 = lambda root: P.probe_swap(root, swap_run(SWAP_40)[0])  # noqa: E731
    assert P.main([], root=tmp_path, probes=probes, runner=runner, precondition=ok_check, swap=swap40) == 0
    assert len(started) == 1


def test_an_admission_swap_failure_is_blocked_for_capacity_and_starts_nothing(tmp_path):
    T12.copy_root(tmp_path, [P.MANIFEST_REL])
    started = []
    probes = OrderedDict(ok=ok_check, swap=lambda root: P.probe_swap(root, swap_run('unparsable')[0]))
    assert P.main([], root=tmp_path, probes=probes, runner=lambda ctx: started.append(ctx), precondition=ok_check,
                  swap=ok_check) == 2
    summary = json.loads((tmp_path / P.OUTPUTS['published'] / 'probe' / 'pair_summary.json').read_text())
    assert (summary['status'], summary['failed_admission_checks'], summary['executed']) == (
        'BLOCKED_FOR_CAPACITY', ['swap'], False)
    assert summary['assignments'][0]['state'] == 'not_started: probe blocked_for_capacity' and started == []


def test_admission_only_is_read_only_and_includes_the_swap_gate(tmp_path, capsys):
    T12.copy_root(tmp_path, [P.MANIFEST_REL])
    probes = OrderedDict(swap=lambda root: P.probe_swap(root, swap_run(SWAP_NOW)[0]))
    assert P.main(['--admission-only'], root=tmp_path, probes=probes) == 1
    adm = json.loads(capsys.readouterr().out)
    assert (adm['admitted'], adm['swap']['ok'], adm['mode']) == (False, False, 'admission-only')
    assert not (tmp_path / 'work').exists() and not (tmp_path / 'results').exists()
    assert list(P.admission_probes(MANIFEST)) == ['manifest', 'sources', 'runtime', 'images', 'conflicts', 'isolation',
                                                  'disk', 'models', 'memory', 'swap', 'gate', 'step1']


# ---------------------------------------------------------------- (d) the probe precondition

GATE_FILES = [P12.OUTPUTS['published'] + '/gate.json']


def precondition_root(tmp_path):
    T12.copy_root(tmp_path, list(P12.SOURCES) + [P.MANIFEST_REL] + GATE_FILES)
    raw = tmp_path / P12.OUTPUTS['raw'] / 'gate' / 'gate.json'
    raw.parent.mkdir(parents=True)
    shutil.copyfile(tmp_path / GATE_FILES[0], raw)
    return tmp_path


def test_the_precondition_is_the_passing_req012_gate_for_these_bytes_plus_the_configuration_proof(tmp_path, pinned_cfg):
    root = precondition_root(tmp_path)
    cfg = lambda: pinned_cfg  # noqa: E731
    ok, d = P.probe_precondition(root, load_cfg=cfg)
    assert ok and all(d['checks'].values()) and d['configuration_proof_problems'] == []

    def refused(mutate):
        case = precondition_root(tmp_path / ('case%d' % len(list(tmp_path.glob('case*')))))
        mutate(case)
        return P.probe_precondition(case, load_cfg=cfg)[0] is False

    def both_gates(fn):
        def mutate(root):
            for path in (root / GATE_FILES[0], root / P12.OUTPUTS['raw'] / 'gate' / 'gate.json'):
                rec = json.loads(path.read_text())
                fn(rec)
                path.write_text(json.dumps(rec))
        return mutate

    def edit(rel, fn):
        def mutate(root):
            obj = json.loads((root / rel).read_text())
            fn(obj)
            (root / rel).write_text(json.dumps(obj))
        return mutate
    assert refused(lambda root: [(root / GATE_FILES[0]).unlink(),
                                 (root / P12.OUTPUTS['raw'] / 'gate' / 'gate.json').unlink()])    # no gate record
    assert refused(both_gates(lambda g: g.update(passed=False)))
    assert refused(both_gates(lambda g: g['repair1'].update(prompt_addition='x')))
    assert refused(both_gates(lambda g: g['prompt_bytes'].update(inserted_sha256='0' * 64)))
    assert refused(both_gates(lambda g: g['container']['detail']['environment'].update(run_args=REPAIR_RUN_ARGS[:3])))
    assert refused(both_gates(lambda g: g['container']['detail']['network'].update(network_mode='bridge')))
    assert refused(both_gates(lambda g: g['container']['detail']['environment'].update(image='sha256:' + '3' * 64)))
    assert refused(edit(P.MANIFEST_REL, lambda m: m['repair1'].update(prompt_addition='x')))
    assert refused(edit(P.MANIFEST_REL, lambda m: m['images']['instance'].update(id='sha256:' + '4' * 64)))
    assert refused(lambda root: (root / 'experiments/v2_agent/req012_entry.py').write_text(
        (ROOT / 'experiments/v2_agent/req012_entry.py').read_text() + '\n# changed\n'))
    frozen = R.PE.build_effective_config
    ok, d = P.probe_precondition(root, load_cfg=cfg, build=lambda c, **kw: dict(frozen(c, **kw), extra=kw['port']))
    assert not ok and d['checks']['configuration_proof'] is False and d['configuration_proof_problems']
    ok, d = P.probe_precondition(root, load_cfg=lambda: 1 / 0)                     # a proof that cannot run
    assert not ok and d['configuration_proof_problems'][0].startswith('the configuration proof could not run')


def test_the_probe_refuses_before_its_namespace_without_the_gate_or_on_a_mismatch(tmp_path, pinned_cfg):
    started = []
    runner = lambda ctx: started.append(ctx) or None  # noqa: E731
    probes = OrderedDict(ok=ok_check)
    empty = tmp_path / 'no_gate'
    T12.copy_root(empty, list(P12.SOURCES) + [P.MANIFEST_REL])
    pre = lambda root: P.probe_precondition(root, load_cfg=lambda: pinned_cfg)  # noqa: E731
    assert P.main([], root=empty, probes=probes, runner=runner, precondition=pre, swap=ok_check) == 3
    assert not (empty / P.OUTPUTS['raw']).exists() and not (empty / P.OUTPUTS['published']).exists()
    mismatch = precondition_root(tmp_path / 'mismatch')
    m = json.loads((mismatch / P.MANIFEST_REL).read_text())
    m['repair1']['run_args'] = REPAIR_RUN_ARGS[:3]
    (mismatch / P.MANIFEST_REL).write_text(json.dumps(m))
    assert P.main([], root=mismatch, probes=probes, runner=runner, precondition=pre, swap=ok_check) == 3
    assert not (mismatch / P.OUTPUTS['raw']).exists() and started == []
    good = precondition_root(tmp_path / 'good')
    assert P.main([], root=good, probes=probes, runner=runner, precondition=pre, swap=ok_check) == 0
    assert len(started) == 1


def test_step1_requires_both_committed_records_to_have_passed(tmp_path):
    def write(verified, passed):
        for rel, rec in ((P.STEP1['reconciliation'], dict(verified=verified)),
                         (P.STEP1['watchdog_host_check'], dict(passed=passed))):
            (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / rel).write_text(json.dumps(rec))
    git = lambda code: (lambda cmd, env=None, timeout=None: (code, '', ''))  # noqa: E731
    assert P.probe_step1(tmp_path, git(0))[0] is False                            # no records
    for verified, passed, code, expected in ((True, True, 0, True), (True, False, 0, False), (False, True, 0, False),
                                             ('true', True, 0, False), (True, True, 1, False)):
        write(verified, passed)
        assert P.probe_step1(tmp_path, git(code))[0] is expected


# ---------------------------------------------------------------- (e) single shot and the always-written summary

def test_the_probe_is_single_shot_and_publishes_under_req013(tmp_path):
    T12.copy_root(tmp_path, [P.MANIFEST_REL] + [rel for rel in P.PRIOR_RESULTS])
    calls = []

    def runner(ctx):
        calls.append(ctx['sources'])
        ctx['ledger'].start(1, run_id='run-1')
        (ctx['raw'] / 'run-1').mkdir()
        raise S.Interrupted('SIGTERM')
    probes = OrderedDict(ok=ok_check)
    assert P.main([], root=tmp_path, probes=probes, runner=runner, precondition=ok_check, swap=ok_check) == 0
    pub = tmp_path / P.OUTPUTS['published'] / 'probe'
    summary = json.loads((pub / 'pair_summary.json').read_text())
    assert (summary['request'], summary['status'], summary['interrupted_or_error'], summary['probe_cap_s']) == (
        'DTR-REQ-013', 'INTERRUPTED', 'SIGTERM', 3600)
    assert summary['published'] == 'results/v2_agent/req013_14b_discriminator_20260924/probe'
    assert [(x['order'], x['assignment_id'], x['backend'], x['state']) for x in summary['assignments']] == [
        (1, 'req013-1-large', 'large', 'interrupted')]
    assert summary['requests']['physical_counted_total'] == 48 and summary['requests']['max_logical'] == 24
    prior = summary['prior_results']
    assert all(prior[rel]['unchanged'] for rel in P.PRIOR_RESULTS)
    assert 'results/v2_agent/req012_repair_probe_20260924/probe/pair_summary.json' in prior
    assert P12.OUTPUTS['published'] == 'results/v2_agent/req012_repair_probe_20260924'       # restored after finish
    assert P12.PRIOR_RESULTS is not P.PRIOR_RESULTS and len(calls) == 1
    assert P.main([], root=tmp_path, probes=probes, runner=runner, precondition=ok_check, swap=ok_check) == 3
    assert len(calls) == 1                                                                      # never re-dispatched
    blocked = tmp_path / 'blocked'
    T12.copy_root(blocked, [P.MANIFEST_REL])
    assert P.main([], root=blocked, probes=OrderedDict(memory=lambda root: (False, {})), runner=runner,
                  precondition=ok_check, swap=ok_check) == 2
    summary = json.loads((blocked / P.OUTPUTS['published'] / 'probe' / 'pair_summary.json').read_text())
    assert (summary['status'], summary['failed_admission_checks']) == ('BLOCKED', ['memory'])
    assert P.main([], root=blocked, probes=probes, runner=runner, precondition=ok_check, swap=ok_check) == 3
    assert len(calls) == 1


# ---------------------------------------------------------------- the REQ-013 holder, watchdog launcher and host check

def test_the_ownership_holder_and_watchdog_launcher_are_req013_and_stop_the_server_after_a_parent_sigkill(
        tmp_path, monkeypatch):
    monkeypatch.setattr(P.PR, 'SERVERS', tmp_path / 'own.json')
    P.Servers({}, dict(hard_deadline_epoch=0, block_start_utc='a', block_hard_end_utc='b'), tmp_path)._record()
    assert json.loads((tmp_path / 'own.json').read_text())['holder'] == (
        'DTR-AgentEvals worker (DTR-REQ-013 14B discriminator)') == P.HOLDER
    stub = T11.STUB_PARENT.replace('import req011_pair as P', 'import req013_pair as P')
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
        assert (cfg['request'], cfg['holder']) == ('DTR-REQ-013', P.HOLDER)
        args = subprocess.run(['ps', '-ww', '-o', 'args=', '-p', str(pids['watchdog'])], capture_output=True,
                              text=True).stdout
        assert 'req013_pair.py --watchdog' in args
        os.kill(parent.pid, 9)
        parent.wait(timeout=10)
        assert T11.wait_until(lambda: not T11.alive(pids['server']), 30)
        assert T11.wait_until(lambda: not T11.alive(pids['watchdog']), 30)
        assert T11.alive(pids['decoy'])
        action = json.loads((tmp_path / 'raw' / 'watchdog_action.json').read_text())
        assert (action['reason'], action['action'], action['record_holder']) == (
            'parent process gone', 'stopped', P.HOLDER)
    finally:
        for pid in [parent.pid] + [pids[k] for k in ('server', 'decoy', 'watchdog') if k in pids]:
            try:
                os.kill(pid, 9)
            except ProcessLookupError:
                pass


def test_the_watchdog_host_check_fails_closed_and_is_write_once(tmp_path):
    row = dict(pid=11, equal_raw=False, watchdog_rule_match=True)
    good = dict(pids=dict(server=11), watchdog_ready=True, recorded_servers=[row], server_alive_while_parent_lives=True,
                stopped_within_grace=True, decoy_untouched=True, watchdog_exited=True, owned_stub_stopped=True)
    fixture_ok = lambda base: dict(passed=True, returncode=0, summary='1 passed in 2.0s')  # noqa: E731
    cases = ((good, fixture_ok, 0, True), (dict(good, stopped_within_grace=False), fixture_ok, 2, False),
             (dict(good, recorded_servers=[dict(row, watchdog_rule_match=False)]), fixture_ok, 2, False),
             (dict(good, decoy_untouched=False), fixture_ok, 2, False),
             (good, lambda base: dict(passed=False, returncode=1, summary='1 failed in 30.0s'), 2, False))
    for i, (scenario, fixture, code, passed) in enumerate(cases):
        root = tmp_path / str(i)
        assert W.main(root=root, run_scenario=lambda base: scenario, fixture=fixture) == code
        rec = json.loads((root / W.OUT).read_text())
        assert rec['passed'] is passed and rec['owned_stub']['recorded_vs_live_equal_under_the_watchdog_rule'] is (
            scenario['recorded_servers'][0]['watchdog_rule_match'])
        assert W.main(root=root, run_scenario=lambda base: scenario, fixture=fixture) == 3
