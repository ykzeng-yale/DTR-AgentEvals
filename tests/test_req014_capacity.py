"""DTR-REQ-014 fixtures (lead b9ffb29, docs/theory_feedback_20260924_req013_capacity_decision.md).

Covered: (a) the REQ-014 manifest is the REQ-013 live design except the versioned capacity rule (field by field, and
bound to the code); the effective repair1 configuration equals REQ-013's, and REQ-012's apart from the model name and
port; the req014_entry shim sends REQ-013's exact request bytes under the REQ-014 binding (run in the pinned venv);
(b) the admission capacity gates (50 % physical free, 30 GiB VM, 25 GiB host, swap recorded but not gated,
unavailable observations fail closed); (c) the post-load gate (20 %) stops the owned server before any agent request;
(d) the in-episode supervision with a real stub entry child that handles SIGALRM like the frozen deadline path: a
breach (or a missing measurement, or an unrecordable sample) sends SIGALRM, the owned server is stopped at once
(before the settle), the child exits, its process group is gone, only the recorded container is removed and the
assignment is a 'capacity_interruption', never graded or eligible; no breach leaves the episode alone; a child that
exited on its own during a failing sample is not interrupted; a stop that lands while `docker run -d` is in flight
(no ownership record) removes only the new minisweagent-* container of the pinned image; a runner cut short by a
signal is still classified; the time series, its statistics and a record that cannot be built never cost the summary;
the published outcome-rule precedence (B1); (d2) the REAL entry (req014_entry -> req012_entry -> cue_episode ->
mini-swe-agent, pinned venv, unedited REQ-011 harness): a SIGALRM during a container command is swallowed by the pinned
DockerEnvironment.execute, and the latch then refuses the next query (req013_entry, without the latch, sends two more);
a SIGALRM during `docker run -d` leaves no ownership record and the parent's sweep removes that container; the latch
unit (frozen natural deadline, counted-only signal after the inference phase); (e) the REQ-013 manifest, records and
entry are unchanged and the namespaces are disjoint; (f) single shot; (g) the prerequisite watchdog record is
required, and --prereq writes it once under REQ-014.

There is no model, llama.cpp server, container, evaluator or network: only fakes and stubs. The entry fixtures use the
committed, unedited REQ-011 harness through the REQ-013 fixture helper (a one-line shim); they skip when the pinned venv
or the dataset is absent. Expected values are literals from the lead decision and the committed REQ-013 records, not
values computed by the code under test.
"""
import copy
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from collections import OrderedDict, namedtuple
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
for _p in (ROOT / 'experiments/v2_agent', ROOT / 'experiments/tools', Path(__file__).resolve().parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import req014_pair as P  # noqa: E402
import req014_entry as E14  # noqa: E402  imports req012_entry/cue_episode (as tests/test_req012_repair.py does)
import req013_watchdog_check as W  # noqa: E402
import test_req011_pair as T11  # noqa: E402  helpers only; not re-collected
import test_req012_repair as T12  # noqa: E402  helpers only; not re-collected
import test_req013_discriminator as T13  # noqa: E402  helpers only; not re-collected

P13, P12, P11, S, R = P.P13, P.P12, P.P11, P.S, P.R
M14_PATH = ROOT / 'configs/v2_req014_14b_capacity_probe_20260924.json'
M14 = json.loads(M14_PATH.read_text())
M14_SHA = hashlib.sha256(M14_PATH.read_bytes()).hexdigest()
M13, M12 = T13.MANIFEST, T12.MANIFEST
IID, PIN, CID = T11.IID, T11.PIN, T11.CID
LARGE_ALIAS, LARGE_SHA, SMALL_ALIAS = T11.LARGE_ALIAS, T11.LARGE_SHA, T11.SMALL_ALIAS
REPAIR_RUN_ARGS, REPAIR1_TEMPLATE_SHA = T13.REPAIR_RUN_ARGS, T13.REPAIR1_TEMPLATE_SHA
GiB = 1 << 30
REQ013_FILES = {                                     # sha256 at HEAD 3e2398c (REQ-013 step 1, commit 16d1d9b)
    'configs/v2_req013_14b_discriminator_20260924.json':
        'a4d4ec49a87471cf8b14aa339f88a1780751e2eccf91971f48b79ed468abd346',
    'results/v2_agent/req013_14b_discriminator_20260924/reconciliation.json':
        '6ece3f7f402e1dee1749bd38dfee4bcf7b24c56d4b41c06ca0f5d858df433a60',
    'results/v2_agent/req013_14b_discriminator_20260924/watchdog_host_check.json':
        '4cf63b5272e9b58aa33054a6685cc77d0e2f7943ab77785a75aa8e8497953874',
    'experiments/v2_agent/req013_entry.py': '393d2f820d9d6704a7cc21b90c0d46065a2755c57504c3638c34e2fd05c5d8a8'}
GIT_OK = lambda cmd, env=None, timeout=None: (0, '', '')  # noqa: E731


def sha(data):
    return hashlib.sha256(data).hexdigest()


def lines(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


@pytest.fixture(scope='module')
def pinned_cfg():
    if not T12.MSWEA_PY.exists():
        pytest.skip('pinned mini-swe-agent venv is absent')
    code = 'import json, sys, yaml; print(json.dumps(yaml.safe_load(open(sys.argv[1]).read())))'
    return json.loads(subprocess.run([str(T12.MSWEA_PY), '-c', code, str(T12.DEFAULT_YAML)], capture_output=True,
                                     text=True, check=True).stdout)


# ---------------------------------------------------------------- (a) the REQ-013 live design, versioned capacity rule

DIFFERENT_BY_DESIGN = ['assignments', 'declared_rules', 'disk_rule', 'inherited_labels', 'interpretations', 'kind',
                       'lead_commit', 'lead_decision', 'memory_rule', 'outputs', 'prereq', 'request', 'runtime',
                       'scope', 'semantics_differences', 'source_commit', 'supervision', 'swap_record', 'swap_rule']
THRESHOLDS = {'admission': dict(physical_free_pct=50, vm_disk_free_gib=30, host_disk_free_gib=25),
              'post_load': dict(physical_free_pct=20, vm_disk_free_gib=30, host_disk_free_gib=25),
              'episode': dict(physical_free_pct=10, vm_disk_free_gib=20, host_disk_free_gib=15)}


def test_the_manifest_is_the_req013_live_design_except_the_versioned_capacity_rule():
    assert (M14['request'], M14['lead_commit'], M14['source_commit'], M14['lead_decision'], M14['instance_id']) == (
        'DTR-REQ-014', 'b9ffb29', '16d1d9b', 'docs/theory_feedback_20260924_req013_capacity_decision.md', IID)
    assert sorted(k for k in set(M14) | set(M13) if M14.get(k) != M13.get(k)) == DIFFERENT_BY_DESIGN
    for k in ('instance_id', 'images', 'settings', 'repair1', 'prompt_bytes', 'serving', 'evaluator', 'caps',
              'watchdog', 'precondition', 'step1', 'prior_results'):
        assert M14[k] == M13[k], k                                            # field by field
    for k in ('images', 'settings', 'repair1', 'prompt_bytes', 'serving', 'evaluator', 'caps', 'watchdog'):
        assert M14[k] == M12[k], k
    (a14,), (a13,) = M14['assignments'], M13['assignments']
    assert dict(a14, assignment_id=None) == dict(a13, assignment_id=None) and a14['assignment_id'] == 'req014-1-large'
    assert (a14['backend'], a14['arm'], a14['port'], a14['alias'], a14['gguf_sha256'], a14['gguf_bytes']) == (
        'large', 'baseline', 8293, LARGE_ALIAS, LARGE_SHA, 8988110944)
    rt14, rt13 = M14['runtime'], M13['runtime']
    assert {k for k in set(rt14) | set(rt13) if rt14.get(k) != rt13.get(k)} == {'orchestrator', 'entry'}
    assert (rt14['orchestrator'], rt14['entry']) == ('experiments/v2_agent/req014_pair.py',
                                                     'experiments/v2_agent/req014_entry.py')
    assert M14['outputs'] == dict(raw='work/runs/req014_14b_capacity_probe_20260924',
                                  published='results/v2_agent/req014_14b_capacity_probe_20260924',
                                  pause_file='work/REQ014_PAUSE',
                                  private_receipts='work/req005_request_receipts/cue-v1')
    mem, disk = M14['memory_rule'], M14['disk_rule']
    assert (mem['admission_min_free_pct'], mem['post_load_min_free_pct'], mem['episode_min_free_pct']) == (50, 20, 10)
    assert (disk['vm_min_gib'], disk['host_min_gib'], disk['episode_vm_min_gib'], disk['episode_host_min_gib']) == (
        30, 25, 20, 15)
    changed = ('admission_min_free_pct', 'post_load_min_free_pct', 'episode_min_free_pct', 'vm_min_gib', 'host_min_gib',
               'episode_vm_min_gib', 'episode_host_min_gib')
    rest = lambda d: {k: v for k, v in d.items() if k not in changed}  # noqa: E731
    assert rest(mem) == rest(M13['memory_rule']) == dict(kv_gib=dict(large=3.0, small=0.88), vm_gib=16, margin_gib=2)
    assert rest(disk) == rest(M13['disk_rule']) == dict(work_free_min_above_reserve_gib=6)
    sup = M14['supervision']
    assert (sup['version'], sup['thresholds'], sup['sample_interval_s'], sup['max_gap_s']) == (
        'req014-capacity-v1', THRESHOLDS, 5, 10)
    assert sup['measurement_timeouts_s'] == dict(physical_free_pct=3, vm_disk_free_gib=4, swap=1)
    assert sum(sup['measurement_timeouts_s'].values()) < sup['max_gap_s']           # a sample never outlasts the gap
    assert 'swap_rule' not in M14 and (M14['swap_record']['command'], M14['swap_record']['gated']) == (
        ['sysctl', '-n', 'vm.swapusage'], False)
    assert M14['prereq']['watchdog_host_check'] == (
        'results/v2_agent/req014_14b_capacity_probe_20260924/watchdog_host_check.json')
    assert P.manifest_problems(M14, T11.CONV, T11.REQ010, M13) == []
    assert all(M14[k] for k in ('kind', 'declared_rules', 'interpretations', 'inherited_labels',
                                'semantics_differences', 'scope'))


MANIFEST_MUTATIONS = dict(
    admission_memory=lambda m: m['memory_rule'].update(admission_min_free_pct=30),
    post_load_memory=lambda m: m['memory_rule'].update(post_load_min_free_pct=10),
    episode_memory=lambda m: m['memory_rule'].update(episode_min_free_pct=5),
    vm_disk=lambda m: m['disk_rule'].update(vm_min_gib=20),
    episode_host_disk=lambda m: m['disk_rule'].update(episode_host_min_gib=10),
    threshold_table=lambda m: m['supervision']['thresholds']['episode'].update(physical_free_pct=5),
    interval=lambda m: m['supervision'].update(sample_interval_s=30),
    swap_gated=lambda m: m['swap_record'].update(gated=True),
    swap_rule_back=lambda m: m.update(swap_rule=M13['swap_rule']),
    second_model=lambda m: m['assignments'].append(dict(m['assignments'][0], order=2, backend='small')),
    assignment_id=lambda m: m['assignments'][0].update(assignment_id='req013-1-large'),
    port=lambda m: m['assignments'][0].update(port=8291),
    cue_arm=lambda m: m['assignments'][0].update(arm='cue'),
    other_task=lambda m: m.update(instance_id='astropy__astropy-12907'),
    prompt=lambda m: m['repair1'].update(prompt_addition=m['repair1']['prompt_addition'] + ' Edit card.py.'),
    prompt_bytes=lambda m: m['prompt_bytes'].update(inserted_bytes=1),
    network=lambda m: m['repair1'].update(run_args=REPAIR_RUN_ARGS[:3]),
    guard=lambda m: m['repair1'].update(stall_rule='never'),
    output_cap=lambda m: m['settings'].update(max_tokens=4096),
    cap=lambda m: m['caps'].update(pair_wall_s=7200),
    requests=lambda m: m['caps'].update(max_physical_requests=96),
    precondition=lambda m: m['precondition'].update(req012_manifest_sha256='0' * 64),
    req013_entry=lambda m: m['runtime'].update(entry='experiments/v2_agent/req013_entry.py'),
    req013_namespace=lambda m: m.update(outputs=M13['outputs']),
    prereq=lambda m: m['prereq'].update(watchdog_host_check=M13['step1']['watchdog_host_check']),
    prior_results=lambda m: m['prior_results'].popitem(),
    extra_section=lambda m: m.update(cue_v1=True),
    text=lambda m: m.pop('scope'))


@pytest.mark.parametrize('name', sorted(MANIFEST_MUTATIONS))
def test_any_manifest_mismatch_fails_closed(name):
    m = copy.deepcopy(M14)
    MANIFEST_MUTATIONS[name](m)
    assert P.manifest_problems(m, T11.CONV, T11.REQ010, M13) != []


def test_the_effective_repair1_config_equals_req013_and_req012_apart_from_the_model_name_and_port(pinned_cfg):
    def effective(a):
        return json.loads(json.dumps(R.repair_config(R.PE.build_effective_config(
            pinned_cfg, alias=a['alias'], port=a['port'], image_id=PIN))))
    assert effective(M14['assignments'][0]) == effective(M13['assignments'][0])
    problems, proof = P13.config_proof(pinned_cfg, M12['assignments'][0], M14['assignments'][0], PIN,
                                       REPAIR1_TEMPLATE_SHA)
    assert problems == [] and proof['differences'] == {
        'model.model_name': ['openai/' + SMALL_ALIAS, 'openai/' + LARGE_ALIAS],
        'model.model_kwargs.api_base': ['http://127.0.0.1:8291/v1', 'http://127.0.0.1:8293/v1']}
    assert (proof['instance_template_sha256'], proof['run_args'], proof['agent_class']) == (
        REPAIR1_TEMPLATE_SHA, REPAIR_RUN_ARGS, 'req012_entry.RepeatedFailureGuardAgent')


def gate_root(tmp_path):
    T12.copy_root(tmp_path, list(P12.SOURCES) + [P.MANIFEST_REL, P13.MANIFEST_REL] + T13.GATE_FILES)
    raw = tmp_path / P12.OUTPUTS['raw'] / 'gate' / 'gate.json'
    raw.parent.mkdir(parents=True)
    raw.write_bytes((tmp_path / T13.GATE_FILES[0]).read_bytes())
    return tmp_path


def test_the_precondition_is_the_req013_one_applied_to_this_manifest(tmp_path, pinned_cfg):
    root = gate_root(tmp_path)
    ok, d = P.probe_gate(root, load_cfg=lambda: pinned_cfg)
    assert ok and all(d['checks'].values()) and d['configuration_proof']['assignments'] == ['req012-1-small',
                                                                                            'req014-1-large']
    assert P13.MANIFEST_REL == 'configs/v2_req013_14b_discriminator_20260924.json'      # restored after the call
    m = json.loads((root / P.MANIFEST_REL).read_text())
    m['repair1']['run_args'] = REPAIR_RUN_ARGS[:3]
    (root / P.MANIFEST_REL).write_text(json.dumps(m))
    ok, d = P.probe_gate(root, load_cfg=lambda: pinned_cfg)
    assert not ok and d['checks']['repair1'] is False


@pytest.fixture(scope='module')
def entries(tmp_path_factory):
    if not T12.MSWEA_PY.exists() or not T11.DATA.exists():
        pytest.skip('pinned mini-swe-agent venv or the pinned SWE-bench Verified parquet is absent')
    digests = lambda rels: {rel: sha((ROOT / rel).read_bytes()) for rel in rels}  # noqa: E731
    binding, problems = P.A.compute_binding(P.A.Layout(ROOT))
    assert problems == []
    runtime = {k: binding['runtime'][k] for k in ('sdk_traced_files', 'mini_swe_agent_sources')}
    work = tmp_path_factory.mktemp('req014_entry')
    submitted, refused = T12.SCENARIOS['submitted']['script'], [T11.LS]
    s13, s14 = digests(P13.SOURCES), digests(P.SOURCES)
    return dict(
        large13=T13.run_entry(work / 'l13', 'req013_entry', 'large', s13, runtime, T13.MANIFEST_SHA, submitted),
        large14=T13.run_entry(work / 'l14', 'req014_entry', 'large', s14, runtime, M14_SHA, submitted,
                              'req014-1-large'),
        unadmitted=T13.run_entry(work / 'u', 'req014_entry', 'large', s13, runtime, M14_SHA, refused, 'req014-1-large'),
        req013_binding=T13.run_entry(work / 'b', 'req014_entry', 'large', s14, runtime, T13.MANIFEST_SHA, refused))


def test_the_req014_entry_sends_the_req013_request_bytes_under_the_req014_binding(entries):
    a, b = entries['large13'], entries['large14']
    for r in (a, b):
        assert (r['harness']['exit_code'], r['harness']['network_attempts'], len(r['bodies'])) == (0, [], 3)
    assert b['bodies'] == a['bodies']                                        # byte-identical model requests
    for part in ('constructor_arguments', 'resolved'):
        assert T11.effective(b['run_dir'])[part] == T11.effective(a['run_dir'])[part]
    recs = [json.loads((r['control'] / 'repair_record.json').read_text()) for r in (a, b)]
    assert [rec['request'] for rec in recs] == ['DTR-REQ-013', 'DTR-REQ-014']
    for rec in recs:
        assert (rec['configuration'], rec['guard']['agent_type'], rec['guard']['network']['network_mode'],
                rec['guard']['network']['run_args'], rec['effective_config']['verified'],
                rec['effective_config']['instance_template_sha256'], rec['stall_rule']) == (
            'yaml-v1-repair1', 'req012_entry.RepeatedFailureGuardAgent', 'none', REPAIR_RUN_ARGS, True,
            REPAIR1_TEMPLATE_SHA, M14['repair1']['stall_rule'])
    admitted = json.loads((b['control'] / 'entry_admitted.json').read_text())
    assert (admitted['request'], admitted['runtime_overrides']) == ('DTR-REQ-014', M14['repair1']['runtime_overrides'])
    assert admitted['running_sources']['req014_entry.py'] == sha(
        (ROOT / 'experiments/v2_agent/req014_entry.py').read_bytes())
    assert admitted['running_sources']['req013_entry.py'] == REQ013_FILES['experiments/v2_agent/req013_entry.py']
    ep = json.loads((b['run_dir'] / 'episode.json').read_text())
    assert (ep['exit_status'], ep['logical_calls'], ep['binding_sha256'], ep['backend'], ep['assignment_id']) == (
        'Submitted', 3, M14_SHA, 'large', 'req014-1-large')
    assert (b['run_dir'] / 'submission.diff').read_bytes() == (a['run_dir'] / 'submission.diff').read_bytes()


def test_the_req014_entry_refuses_an_unadmitted_shim_and_the_req013_binding(entries):
    for name, reasons in (
            ('unadmitted', ['running req014_entry.py is not the admitted source']),
            ('req013_binding', ['binding_sha256 is not the sha256 of '
                                'configs/v2_req014_14b_capacity_probe_20260924.json',
                                'the assignment (id, order, backend, port, alias, model sha256) is not a manifest '
                                'assignment'])):
        r = entries[name]
        assert (r['harness']['exit_code'], r['bodies'], r['harness']['network_attempts']) == (3, [], []), name
        got = json.loads((r['control'] / 'entry_refused.json').read_text())['reasons']
        assert all(x in got for x in reasons), (name, got)
        assert not (r['control'] / 'entry_admitted.json').exists() and list(r['run_dir'].iterdir()) == []


# ---------------------------------------------------------------- (b) the admission capacity gates

DF = ('Filesystem     1024-blocks     Used Available Capacity Mounted on\n'
      '/dev/vdb1        123266624 31829896  %d      28%% /var/lib/docker\n')
SWAP_LOW = 'total = 15360.00M  used = 15257.60M  free = 102.40M  (encrypted)\n'          # 0.1 GiB unused
MEMSIZE = 34359738368                                                                     # this host: 32 GiB
Usage = namedtuple('Usage', 'total used free')


def host(gib):
    return lambda path: Usage(0, 0, int(gib * GiB))


def shell(pct=66, vm_gib=81.2, swap=SWAP_LOW, fail=()):
    """memory_pressure, sysctl and the colima df, faked; `fail` makes a command fail (nonzero return code)."""
    calls = []

    def run(cmd, env=None, timeout=60):
        calls.append((cmd, timeout))
        if cmd == ['memory_pressure']:
            return (1, '', 'failed') if 'memory' in fail else (
                0, 'The system has 34359738368 (2097152 pages with a page size of 16384).\n'
                   'System-wide memory free percentage: %d%%\n' % pct, '')
        if cmd == ['sysctl', '-n', 'hw.memsize']:
            return 0, '%d\n' % MEMSIZE, ''
        if cmd == ['sysctl', '-n', 'vm.swapusage']:
            return (1, '', '') if 'swap' in fail else (0, swap, '')
        if cmd == [str(S.COLIMA), 'ssh', '--profile', 'dtr', '--', 'df', '-Pk', '/var/lib/docker']:
            return (1, '', 'failed') if 'vm' in fail else (0, DF % int(round(vm_gib * (1 << 20))), '')
        return 1, '', 'unexpected command %s' % cmd
    return run, calls


def test_admission_memory_needs_50_percent_free_and_the_unchanged_projection():
    queue = M14['assignments']
    for pct, ok in ((49, False), (50, True), (66, True)):
        assert P.probe_memory(ROOT, queue, shell(pct=pct)[0])[0] is ok, pct
    ok, d = P.probe_memory(ROOT, queue, shell(fail=('memory',))[0])
    assert ok is False and d['memory_free_pct'] is None
    assert (d['projection_bytes'], d['projection_limit_bytes']) == ({'large': 29389205600}, MEMSIZE - 2 * GiB)
    assert (d['rule']['admission_min_free_pct'], d['replaced_rule']['admission_min_free_pct']) == (50, 30)


def test_admission_disk_needs_30_gib_vm_and_25_gib_host_free_and_fails_closed():
    for vm, hst, ok in ((30, 25, True), (29.9, 25, False), (30, 24.9, False), (81.2, 77.9, True)):
        run, calls = shell(vm_gib=vm)
        assert P.probe_disk(ROOT, run, host(hst))[0] is ok, (vm, hst)
    assert calls[0][0][1:] == ['ssh', '--profile', 'dtr', '--', 'df', '-Pk', '/var/lib/docker']
    ok, d = P.probe_disk(ROOT, shell(fail=('vm',))[0], host(77.9))
    assert ok is False and d['vm_disk_free_gib'] is None
    two_rows = lambda cmd, env=None, timeout=60: (0, DF % 90000000 + DF.splitlines()[1] % 90000000 + '\n', '')  # noqa
    assert P.probe_disk(ROOT, two_rows, host(77.9))[0] is False                       # ambiguous: two data rows
    header = lambda cmd, env=None, timeout=60: (0, DF.splitlines()[0] + '\n', '')  # noqa: E731
    assert P.probe_disk(ROOT, header, host(77.9))[0] is False                         # no data row
    noisy = lambda cmd, env=None, timeout=60: (0, 'Warning: Permanently added 127.0.0.1 (ED25519) to the list of ' \
                                                  'known hosts.\n' + DF % (31 << 20), '')  # noqa: E731
    ok, d = P.probe_disk(ROOT, noisy, host(77.9))                                     # another stdout line is ignored
    assert ok is True and d['vm_disk_free_gib'] == 31.0

    def broken(path):
        raise OSError('statvfs failed')
    adm = S.admission(ROOT, OrderedDict(disk=lambda root: P.probe_disk(root, shell()[0], broken)))
    assert adm['admitted'] is False and adm['disk']['detail'] == {'error': 'OSError: statvfs failed'}


def test_swap_is_recorded_not_gated_but_must_be_observable_at_admission():
    ok, d = P.probe_swap(ROOT, shell(swap=SWAP_LOW)[0])
    assert (ok, d['swap_free_gib'], d['swap_total_gib'], d['gated']) == (True, 0.1, 15.0, False)
    assert P.probe_swap(ROOT, shell(swap=T13.SWAP_NOW)[0])[0] is True        # the REQ-013 refusal reading now passes
    for out in ('', 'garbage', 'total = 1.00G  used = 1.00G', T13.SWAP_40 + T13.SWAP_40,
                'total = 1.00T  used = 1.00G  free = 1.00G'):
        assert P.probe_swap(ROOT, shell(swap=out)[0])[0] is False, out
    assert P.probe_swap(ROOT, shell(fail=('swap',))[0])[0] is False


INHERITED_ZERO_SENTENCE = 'Every non-eligible outcome is an operational zero.'


def assert_precedence(summary, source):
    """B1: the reused rule sentence is published, and so is the capacity precedence over it (manifest-bound)."""
    assert INHERITED_ZERO_SENTENCE in summary['outcome_source_rule']                      # inherited, unedited
    assert summary['assignments'][0]['outcome_source'] == source
    rule = summary['capacity_outcome_rule_precedence']
    assert rule == M14['supervision']['outcome_rule_precedence'] == P.SUPERVISION['outcome_rule_precedence']
    assert INHERITED_ZERO_SENTENCE in rule and 'capacity_interruption' in rule and 'BLOCKED for capacity' in rule
    assert 'infrastructure_or_supervision' in rule and 'never zeros' in rule
    assert [x for x in summary['inherited_labels'] if INHERITED_ZERO_SENTENCE in x and 'does not apply' in x]


def capacity_probes(pct=66, vm=81.2, hst=77.9, swap=SWAP_LOW, fail=()):
    run = shell(pct=pct, vm_gib=vm, swap=swap, fail=fail)[0]
    return OrderedDict(ok=T13.ok_check, memory=lambda root: P.probe_memory(root, M14['assignments'], run),
                       disk=lambda root: P.probe_disk(root, run, host(hst)), swap=lambda root: P.probe_swap(root, run))


def test_a_capacity_failure_at_admission_is_blocked_starts_nothing_and_consumes_the_namespace(tmp_path):
    started = []
    runner = lambda ctx: started.append(ctx) or None  # noqa: E731
    cases = (dict(pct=49), dict(vm=29.9), dict(hst=24.9), dict(fail=('memory',)), dict(fail=('vm',)),
             dict(fail=('swap',)))
    expected = (['memory'], ['disk'], ['disk'], ['memory'], ['disk'], ['swap'])
    for i, (case, failed) in enumerate(zip(cases, expected)):
        root = tmp_path / str(i)
        T12.copy_root(root, [P.MANIFEST_REL])
        assert P.main([], root=root, probes=capacity_probes(**case), runner=runner, precondition=T13.ok_check) == 2
        pub = root / P.OUTPUTS['published'] / 'probe'
        summary = json.loads((pub / 'pair_summary.json').read_text())
        assert (summary['status'], summary['failed_admission_checks'], summary['capacity_checks_failed'],
                summary['executed']) == ('BLOCKED', failed, failed, False), case
        assert summary['assignments'][0]['state'] == 'not_started: probe blocked'
        assert_precedence(summary, 'infrastructure_or_supervision')          # B1: never read as an operational zero
        series = lines(pub / P.SERIES)
        assert [s['phase'] for s in series] == ['admission'] and series[0]['problems'], case
        assert P.main([], root=root, probes=capacity_probes(), runner=runner, precondition=T13.ok_check) == 3
    assert started == []
    root = tmp_path / 'at_the_thresholds'
    T12.copy_root(root, [P.MANIFEST_REL])
    assert P.main([], root=root, probes=capacity_probes(pct=50, vm=30, hst=25), runner=runner,
                  precondition=T13.ok_check) == 0
    assert len(started) == 1                              # 0.1 GiB of unused swap does not block (not gated)
    first = lines(root / P.OUTPUTS['raw'] / 'probe' / P.SERIES)[0]
    assert (first['phase'], first['physical_free_pct'], first['vm_disk_free_gib'], first['host_disk_free_gib'],
            first['swap_free_gib'], first['problems']) == ('admission', 50, 30.0, 25.0, 0.1, [])


def test_each_measurement_has_its_own_timeout_and_fails_closed():
    run, calls = shell(pct=66, vm_gib=81.2)
    s = P.measure(ROOT, run, host(77.9))
    assert (s['physical_free_pct'], round(s['vm_disk_free_gib'], 1), round(s['host_disk_free_gib'], 1),
            s['swap_used_gib'], s['swap_free_gib'], s['measurement_errors']) == (66, 81.2, 77.9, 14.9, 0.1, {})
    assert [t for _, t in calls] == [3, 4, 1] == list(P.MEASURE_TIMEOUTS.values())

    def broken(path):
        raise OSError('statvfs failed')
    s = P.measure(ROOT, shell(fail=('memory', 'vm', 'swap'))[0], broken)
    keys = ('physical_free_pct', 'vm_disk_free_gib', 'host_disk_free_gib', 'swap_used_gib')
    assert [s[k] for k in keys] == [None] * 4
    assert list(s['measurement_errors']) == ['physical_free_pct', 'vm_disk_free_gib', 'host_disk_free_gib', 'swap']
    assert P.capacity_problems(s, 'episode') == ['%s unavailable (fails closed)' % k for k in THRESHOLDS['episode']]


def test_the_thresholds_of_each_phase_at_their_boundaries():
    base = dict(physical_free_pct=66, vm_disk_free_gib=81.0, host_disk_free_gib=77.0, swap_used_gib=14.99)
    for phase, limits in THRESHOLDS.items():
        assert P.capacity_problems(base, phase) == []                           # high swap use is never gated
        for key, at in limits.items():
            below = at - 1 if key == 'physical_free_pct' else round(at - 0.1, 1)
            assert P.capacity_problems(dict(base, **{key: at}), phase) == [], (phase, key)
            assert P.capacity_problems(dict(base, **{key: below}), phase) == ['%s %s is below %s' % (key, below, at)]
            assert P.capacity_problems(dict(base, **{key: None}), phase) == ['%s unavailable (fails closed)' % key]
            assert P.capacity_problems(dict(base, **{key: True}), phase) != []  # a bool is not a measurement
    no_swap = dict(base, swap_used_gib=None)
    assert P.capacity_problems(no_swap, 'episode') == []                  # recorded during the episode, stops nothing
    assert P.capacity_problems(no_swap, 'admission') and P.capacity_problems(no_swap, 'post_load')


# ---------------------------------------------------------------- (c) the post-load gate

OK = (66, 81.0, 77.0)


class FakeServers:
    def __init__(self, log=None):
        self.live, self.events, self.stops, self.log = None, [], 0, [] if log is None else log

    def stop(self):
        self.stops += 1
        self.log.append(('server_stop', self.live is not None))       # True only for the stop of a live server
        self.live = None


def fake_base(ctx, servers, gate=None):
    """req011_pair.make_serve stand-in: a completed load (and, optionally, its inherited gate failure)."""
    def serve(a):
        servers.live = dict(backend=a['backend'], pid=424242)
        ctx['served'][a['backend']] = OrderedDict(load={}, checks={}, problems=[gate] if gate else [])
        if gate:
            raise P11.Gate(gate)
    return serve


def observation(obs):
    pct, vm, hst = obs
    return OrderedDict(physical_free_pct=pct, vm_disk_free_gib=vm, host_disk_free_gib=hst, swap_total_gib=15.0,
                       swap_used_gib=14.6, swap_free_gib=0.4,
                       measurement_errors=OrderedDict((k, 'unavailable or unparsable') for k, v in zip(
                           ('physical_free_pct', 'vm_disk_free_gib', 'host_disk_free_gib'), obs) if v is None),
                       measurement_seconds=OrderedDict())


def post_load_case(base, obs, gate=None):
    base.mkdir()
    servers, dispatched, records = FakeServers(), [], []
    ctx = dict(served=OrderedDict(), summary=OrderedDict())
    sampler = P.make_sampler(base / P.SERIES, lambda: observation(obs))
    serve = P.make_serve(servers, ctx, sampler, fake_base(ctx, servers, gate))

    def run_one(a, counted_before, rec):
        dispatched.append(a)
        rec.update(state='completed', request_accounting=OrderedDict(counted=0, accounting='fixture'))
    stop = P11.run_episodes(M14['assignments'], time.time() + 7200, serve, run_one, records, caps=P.CAPS)
    return stop, ctx, servers, dispatched, records, lines(base / P.SERIES)


def test_a_post_load_capacity_failure_stops_the_owned_server_before_any_agent_request(tmp_path):
    for i, (obs, problem) in enumerate((((19, 81.0, 77.0), 'physical_free_pct 19 is below 20'),
                                        ((66, 29.9, 77.0), 'vm_disk_free_gib 29.9 is below 30'),
                                        ((66, 81.0, 24.9), 'host_disk_free_gib 24.9 is below 25'),
                                        ((None, 81.0, 77.0), 'physical_free_pct unavailable (fails closed)'))):
        stop, ctx, servers, dispatched, records, series = post_load_case(tmp_path / str(i), obs)
        assert stop == 'gate: capacity (post-load): ' + problem
        assert dispatched == [] and servers.stops == 1 and servers.live is None    # no entry, so no agent request
        assert records[0]['state'] == 'not_started: ' + stop
        block = ctx['capacity_block']
        assert (block['stage'], block['breach'], block['server_stopped'], block['inherited_gate']) == (
            'post-load', [problem], True, None)
        assert [(s['phase'], s['problems']) for s in series] == [('post_load', [problem])]
        assert P.status_of(ctx, stop) == 'BLOCKED'
    stop, ctx, servers, dispatched, _, series = post_load_case(tmp_path / 'at_20', (20, 30.0, 25.0))
    assert stop is None and len(dispatched) == 1 and servers.stops == 0 and 'capacity_block' not in ctx
    assert series[0]['problems'] == [] and P.status_of(ctx, stop) == 'COMPLETED'
    inherited = 'served identity/memory check failed for large: post-load memory free 9% is below 10%'
    stop, ctx, servers, dispatched, _, _ = post_load_case(tmp_path / 'inherited', (9, 81.0, 77.0), inherited)
    assert stop == 'gate: capacity (post-load): physical_free_pct 9 is below 20' and dispatched == []
    assert ctx['capacity_block']['inherited_gate'] == inherited and servers.stops == 1
    identity = 'served identity/memory check failed for large: /props model_alias None'
    stop, ctx, servers, dispatched, _, _ = post_load_case(tmp_path / 'identity', OK, identity)
    assert stop == 'gate: ' + identity and 'capacity_block' not in ctx and dispatched == []


# ---------------------------------------------------------------- (d) in-episode supervision (a real stub entry child)

OTHER_IMAGE = 'sha256:' + '0' * 64
STARTED = [('5' * 64, 'minisweagent-5a5a5a5a', PIN),          # the agent container whose `docker run -d` was cut off
           ('6' * 64, 'minisweagent-6b6b6b6b', OTHER_IMAGE),  # new, but not on the pinned image: kept
           ('7' * 64, 'someone-new', PIN)]                    # new, pinned image, but not minisweagent-*: kept
ALARM_CHILD = r'''
import json, os, signal, subprocess, sys, time
from pathlib import Path
MODE = %(mode)r
control = Path(sys.argv[1])
ns = json.loads(control.read_text())['namespace']
run_dir = Path(ns['run_dir'])
if MODE == 'start':                # `docker run -d` in flight: the daemon has the container, no ownership record yet
    with open(%(daemon)r, 'a') as fh:
        fh.write(''.join('%%s %%s %%s\n' %% row for row in %(started)r))
else:
    (run_dir / 'container_ownership.json').write_text(json.dumps(dict(container_id='c' * 64, run_id=ns['run_id'])))
grandchild = subprocess.Popen(['sleep', '120'])
ENDINGS = dict(deadline=('EpisodeDeadline', ''), start=('EpisodeDeadline', ''),
               submitted=('Submitted', 'diff --git a/mod.py b/mod.py\n'),
               exit=('Submitted', 'diff --git a/mod.py b/mod.py\n'))


def records():                     # like the frozen deadline path: the endpoint and the records, then the entry exits
    exit_status, diff = ENDINGS[MODE]
    (run_dir / 'submission.diff').write_text(diff)
    (run_dir / 'episode.json').write_text(json.dumps(dict(exit_status=exit_status, physical_requests=2)))


def alarm(signum, frame):
    (control.parent / 'alarm_marker.json').write_text(json.dumps(dict(signal=signum, pid=os.getpid())))
    records()
    sys.exit(0)


signal.signal(signal.SIGALRM, signal.SIG_IGN if MODE == 'ignore' else alarm)
(control.parent / 'pids.json').write_text(json.dumps(dict(child=os.getpid(), grandchild=grandchild.pid)))
if MODE == 'exit':
    time.sleep(1.0)
    records()
    sys.exit(0)
time.sleep(120)
'''


def daemon_docker(daemon, listing, images):
    """docker ps / container inspect / rm -f over `listing` plus every container a child appended to the `daemon`
    file ('<id> <name> <image>' lines); `images` maps IDs to their image."""
    calls, removed = [], set()

    def rows():
        extra = [x.split() for x in daemon.read_text().splitlines() if x.strip()] if daemon.exists() else []
        images.update((i, image) for i, _, image in extra)
        every = list(listing) + [(i, n) for i, n, _ in extra]
        return [(i, n) for i, n in every if i not in removed and n not in removed]

    def run(cmd, env=None, timeout=60):
        calls.append(cmd)
        if cmd[:2] == ['docker', 'ps']:
            return 0, ''.join('%s %s\n' % r for r in rows()), ''
        if cmd[:3] == ['docker', 'container', 'inspect']:
            rows()
            return (0, images[cmd[-1]] + '\n', '') if cmd[-1] in images else (1, '', 'Error: No such container')
        if cmd[:3] == ['docker', 'rm', '-f']:
            removed.update(cmd[3:])
            return 0, '', ''
        return 1, '', 'unexpected command %s' % cmd
    return run, calls, rows


LISTING = [(CID, 'minisweagent-1234abcd'), ('d' * 64, 'someone-elses-container')]


def supervision_case(tmp_path, mode, observed):
    """The REQ-011 episode fixture context with the ALARM_CHILD entry, a fake docker (the recorded container and a
    decoy, plus what a 'start' child registers) and a sampler over `observed` (post-load first when run through
    supervise; OK once exhausted). A failing observation is returned only after the child has installed its handler;
    ('after_exit', obs) only after the child has exited; 'raise' makes the sample fail. `log` orders the server stops
    and the docker calls."""
    log = []
    run0, calls, rows = daemon_docker(tmp_path / 'daemon.txt', LISTING, {CID: PIN, 'd' * 64: PIN})

    def run(cmd, env=None, timeout=60):
        log.append(tuple(cmd[:3]))
        return run0(cmd, env, timeout)
    ctx = T11.episode_ctx(tmp_path, run)
    stub = tmp_path / ('alarm_child_%s.py' % mode)
    stub.write_text(ALARM_CHILD % dict(mode=mode, daemon=str(tmp_path / 'daemon.txt'), started=STARTED))
    ctx.update(entry=stub, manifest=M14, records=[], summary=OrderedDict(), served=OrderedDict(), pub=tmp_path / 'pub',
               start=time.time())
    ctx['pub'].mkdir()
    control = ctx['raw'] / 'control'

    def measure():
        obs = observed.pop(0) if observed else OK
        if obs != OK:
            assert T11.wait_until(lambda: any(control.glob('*/pids.json')), 30)
        if obs[0] == 'after_exit':
            child = json.loads(next(control.glob('*/pids.json')).read_text())['child']
            assert T11.wait_until(lambda: not T11.alive(child), 30)
            obs = obs[1]
        if obs == 'raise':
            raise OSError('No space left on device')
        return observation(obs)
    sampler = P.make_sampler(ctx['raw'] / P.SERIES, measure)
    return dict(ctx=ctx, servers=FakeServers(log), sampler=sampler, docker_calls=calls, rows=rows, control=control,
                log=log)


def supervised(case):
    graded = []
    stop = P.supervise(case['ctx'], case['servers'], case['sampler'], serve=fake_base(case['ctx'], case['servers']),
                       grader=lambda rec: graded.append(rec) or OrderedDict(status='graded by the fixture'),
                       interval=0.2)
    rec = case['ctx']['records'][0]
    pids = json.loads((case['control'] / rec['run_id'] / 'pids.json').read_text())
    return stop, rec, graded, pids


def assert_interrupted(case, stop, rec, graded, pids, breach, owned=CID, removed=(CID,),
                       remaining=(('d' * 64, 'someone-elses-container'),)):
    ctx, cap = case['ctx'], rec['capacity_interruption']
    assert stop == 'gate: capacity interruption: ' + breach
    assert (rec['state'], rec['grade'], graded) == (P.CAPACITY, {'status': P.NOT_GRADED}, [])
    assert (cap['classification'], cap['breach'], cap['sigalrm_sent'], cap['child_exited_within_grace'],
            cap['server_stopped_after_sigalrm'], cap['server_stopped'], cap['state_reported_by_the_reused_runner'],
            cap['run_id'], cap['order'], cap['owned_container'], cap['entry_latch']) == (
        P.CAPACITY, [breach], True, True, True, True, 'completed', rec['run_id'], 1, owned, None)
    log = case['log']                          # the owned server was stopped right after the SIGALRM, before the settle
    assert log.index(('server_stop', True)) < log.index(('docker', 'rm', '-f'))
    assert log.count(('server_stop', True)) == 1
    marker = json.loads((case['control'] / rec['run_id'] / 'alarm_marker.json').read_text())
    assert (marker['signal'], marker['pid']) == (signal.SIGALRM, pids['child'])     # the entry child's own handler ran
    assert rec['process_group_gone'] is True and not T11.alive(pids['child']) and not T11.alive(pids['grandchild'])
    rm = [c for c in case['docker_calls'] if c[:2] == ['docker', 'rm']]
    assert rm == [['docker', 'rm', '-f', c] for c in removed]
    assert case['rows']() == list(remaining) and rec['container_removal']['complete'] is True
    assert case['servers'].live is None
    assert [(e['event'], e.get('state')) for e in ctx['ledger'].events()] == [
        ('start', None), ('end', 'completed'), ('end', P.CAPACITY)]
    assert ctx['ledger'].states()[1]['state'] == P.CAPACITY
    written = json.loads((case['control'] / rec['run_id'] / 'capacity_interruption.json').read_text())
    assert (written['classification'], written['breach'], written['run_id']) == (P.CAPACITY, [breach], rec['run_id'])
    assert P.S.wait_wall is P.WAIT_WALL and P.status_of(ctx, stop) == 'CAPACITY_INTERRUPTION'


def test_a_breach_at_sample_k_sends_sigalrm_and_ends_in_a_capacity_interruption(tmp_path):
    case = supervision_case(tmp_path, 'deadline', [OK, OK, OK, (9, 81.0, 77.0)])
    stop, rec, graded, pids = supervised(case)
    assert_interrupted(case, stop, rec, graded, pids, 'physical_free_pct 9 is below 10')
    assert 'unrecorded_container_sweep' not in rec['capacity_interruption']         # the ownership record matched
    series = lines(case['ctx']['raw'] / P.SERIES)
    assert [s['phase'] for s in series] == ['post_load', 'episode', 'episode', 'episode']
    assert [s['problems'] for s in series] == [[], [], [], ['physical_free_pct 9 is below 10']]
    gaps = [s['gap_s'] for s in series if s['phase'] == 'episode']
    assert gaps[0] is None and all(0 < g < 2 for g in gaps[1:])
    ep = json.loads((Path(case['ctx']['raw']) / rec['run_id'] / 'episode.json').read_text())
    assert ep['exit_status'] == 'EpisodeDeadline'                  # the child's own label; the assignment is not a zero


def test_a_missing_measurement_or_an_unrecordable_sample_fails_closed_like_a_breach(tmp_path):
    for name, observed, breach in (
            ('missing', [OK, OK, (66, None, 77.0)], 'vm_disk_free_gib unavailable (fails closed)'),
            ('host', [OK, (66, 81.0, 14.9)], 'host_disk_free_gib 14.9 is below 15'),
            ('unrecordable', [OK, 'raise'], 'the episode sample could not be taken or recorded: OSError: No space '
                                            'left on device')):
        (tmp_path / name).mkdir()
        case = supervision_case(tmp_path / name, 'deadline', observed)
        stop, rec, graded, pids = supervised(case)
        assert_interrupted(case, stop, rec, graded, pids, breach)
        if name == 'unrecordable':
            assert rec['capacity_interruption']['breaching_sample'] is None


def test_a_stop_while_the_agent_container_starts_removes_only_the_new_container_of_the_pinned_image(tmp_path):
    case = supervision_case(tmp_path, 'start', [OK, (9, 81.0, 77.0)])
    stop, rec, graded, pids = supervised(case)
    kept = LISTING + [('6' * 64, 'minisweagent-6b6b6b6b'), ('7' * 64, 'someone-new')]
    assert_interrupted(case, stop, rec, graded, pids, 'physical_free_pct 9 is below 10', owned=None,
                       removed=('5' * 64,), remaining=kept)       # the pre-existing minisweagent-1234abcd is kept too
    sweep = rec['capacity_interruption']['unrecorded_container_sweep']
    assert (sweep['listed_before_spawn'], sweep['new_minisweagent_containers'], sweep['images'], sweep['removed_ids'],
            sweep['removal']['complete'], sweep['pinned_image']) == (
        LISTING, [['5' * 64, 'minisweagent-5a5a5a5a'], ['6' * 64, 'minisweagent-6b6b6b6b']],
        {'5' * 64: PIN, '6' * 64: OTHER_IMAGE}, ['5' * 64], True, PIN)
    written = json.loads((case['control'] / rec['run_id'] / 'capacity_interruption.json').read_text())
    assert written['unrecorded_container_sweep']['removed_ids'] == ['5' * 64]


def test_the_unrecorded_container_sweep_removes_nothing_without_both_listings(tmp_path):
    daemon = tmp_path / 'daemon.txt'
    daemon.write_text('%s minisweagent-5a5a5a5a %s\n' % ('5' * 64, PIN))
    run, calls, rows = daemon_docker(daemon, [], {})
    ctx = dict(run=run, env=None, pair_deadline=time.time() + 600, clock=time.time, image_id=PIN)
    out = P.sweep_unrecorded(ctx, None)                                   # no pre-spawn listing
    assert (out['removed_ids'], out['removal'], calls) == ([], None, [])
    down = lambda cmd, env=None, timeout=60: (1, '', 'Cannot connect to the Docker daemon')  # noqa: E731
    out = P.sweep_unrecorded(dict(ctx, run=down), [])                      # no listing after the interruption
    assert (out['removed_ids'], out['listed_now'], out['removal']) == ([], None, None)
    out = P.sweep_unrecorded(ctx, [('5' * 64, 'minisweagent-5a5a5a5a')])   # listed before the spawn: not ours
    assert (out['removed_ids'], [c for c in calls if c[:2] == ['docker', 'rm']]) == ([], [])
    out = P.sweep_unrecorded(ctx, [])
    assert out['removed_ids'] == ['5' * 64] and rows() == []


def test_without_a_breach_the_episode_ends_on_its_own_and_is_graded(tmp_path):
    case = supervision_case(tmp_path, 'exit', [])
    stop, rec, graded, pids = supervised(case)
    ctx = case['ctx']
    assert stop is None and rec['state'] == 'completed' and 'capacity_interruption' not in ctx
    assert graded == [rec] and rec['grade'] == {'status': 'graded by the fixture'}
    assert not (case['control'] / rec['run_id'] / 'alarm_marker.json').exists()
    assert case['servers'].stops == 1                                # only the sequence's own final stop
    assert [(e['event'], e.get('state')) for e in ctx['ledger'].events()] == [('start', None), ('end', 'completed')]
    series = lines(ctx['raw'] / P.SERIES)
    episode = [s for s in series if s['phase'] == 'episode']
    assert series[0]['phase'] == 'post_load' and len(episode) >= 2 and all(s['problems'] == [] for s in series)
    assert all(g <= P.SUPERVISION['max_gap_s'] for g in [s['gap_s'] for s in episode][1:])
    assert P.status_of(ctx, stop) == 'COMPLETED'


def test_a_child_that_exits_on_its_own_during_a_failing_sample_is_not_interrupted(tmp_path):
    case = supervision_case(tmp_path, 'exit', [OK, ('after_exit', (9, 81.0, 77.0))])
    stop, rec, graded, pids = supervised(case)
    ctx = case['ctx']
    assert stop is None and rec['state'] == 'completed' and 'capacity_interruption' not in ctx
    assert graded == [rec] and not (case['control'] / rec['run_id'] / 'alarm_marker.json').exists()
    (after,) = ctx['capacity_breach_after_child_exit']
    assert (after['breach'], after['child_returncode'], after['rule']) == (
        ['physical_free_pct 9 is below 10'], 0, P.SUPERVISION['exited_child'])
    assert case['servers'].stops == 1 and P.status_of(ctx, stop) == 'COMPLETED'
    summary = ctx['summary']
    summary.update(request=P.REQUEST, status='COMPLETED', stop_reason=None)
    out = P.finish(ctx, summary, M14)
    assert (out['assignments'][0]['state'], out['assignments'][0]['outcome_source'],
            out['capacity']['breach_after_child_exit'][0]['breach']) == (
        'completed', 'eligible_submission', ['physical_free_pct 9 is below 10'])


def test_a_child_that_outlives_the_grace_has_its_process_group_killed(tmp_path):
    case = supervision_case(tmp_path, 'ignore', [(5, 81.0, 77.0)])
    case['servers'].live = dict(pid=424242)
    rec = OrderedDict(order=1)
    caps = dict(P.CAPS, child_cleanup_grace_s=1)
    gate = P.make_episode_runner(case['ctx'], case['servers'], case['sampler'], caps, interval=0.2)(
        M14['assignments'][0], 0, rec)
    cap, pids = rec['capacity_interruption'], json.loads((case['control'] / rec['run_id'] / 'pids.json').read_text())
    assert gate == 'capacity interruption: physical_free_pct 5 is below 10'
    assert (cap['sigalrm_sent'], cap['server_stopped_after_sigalrm'], cap['child_exited_within_grace'],
            cap['process_group_gone_after_kill'], cap['state_reported_by_the_reused_runner'],
            cap['server_stopped']) == (True, True, False, True, 'exited_without_episode_record', True)
    assert rec['state'] == P.CAPACITY and not T11.alive(pids['child']) and not T11.alive(pids['grandchild'])
    assert [c for c in case['docker_calls'] if c[:2] == ['docker', 'rm']] == [['docker', 'rm', '-f', CID]]


def test_a_capacity_interruption_is_never_eligible_even_if_the_child_reports_submitted(tmp_path):
    case = supervision_case(tmp_path, 'submitted', [OK, OK, (66, 81.0, 14.9)])
    stop, rec, graded, pids = supervised(case)
    ctx = case['ctx']
    summary = ctx['summary']
    summary.update(request=P.REQUEST, status=P.status_of(ctx, stop), stop_reason=stop)
    out = P.finish(ctx, summary, M14)
    row = out['assignments'][0]
    assert (row['state'], row['outcome_source'], row['exit_status'], row['submission_nonempty'], row['eligible'],
            row['eligible_without_the_capacity_rule'], row['grade']['status']) == (
        P.CAPACITY, P.CAPACITY, 'Submitted', True, False, True, P.NOT_GRADED)
    assert (out['status'], out['outcome_sources']['capacity_interruption'],
            out['outcome_sources']['eligible_submission']) == ('CAPACITY_INTERRUPTION', 1, 0)
    assert_precedence(out, P.CAPACITY)                                    # B1: never read as an operational zero
    cap = out['capacity']
    assert (cap['series']['samples'], cap['series']['samples_by_phase'], cap['series']['unparsable_lines']) == (
        3, {'admission': 0, 'post_load': 1, 'episode': 2}, 0)
    assert (cap['series']['min_physical_free_pct'], cap['series']['min_vm_disk_free_gib'],
            cap['series']['min_host_disk_free_gib'], cap['series']['peak_swap_used_gib'],
            cap['series']['episode_gaps_over_max'], cap['series']['samples_with_problems']) == (
        66, 81.0, 14.9, 14.6, 0, 1)
    assert 0 < cap['series']['max_episode_sampling_gap_s'] < 2
    assert cap['interruption']['breach'] == ['host_disk_free_gib 14.9 is below 15']
    assert cap['breach_after_child_exit'] is None
    files = cap['series_files']
    published = (ctx['pub'] / P.SERIES).read_bytes()
    assert files['published_sha256'] == sha(published) and files['raw_sha256'] == sha(
        (ctx['raw'] / P.SERIES).read_bytes())
    raw_summary = json.loads((ctx['raw'] / 'pair_summary.json').read_text())
    assert raw_summary['capacity']['series']['samples'] == 3
    assert raw_summary['capacity_outcome_rule_precedence'] == M14['supervision']['outcome_rule_precedence']
    assert (P12.OUTPUTS['published'], P12.outcome_source.__module__, P11.episode_facts.__module__) == (
        'results/v2_agent/req012_repair_probe_20260924', 'req012_pair', 'req011_pair')     # restored after finish


def test_a_capacity_interruption_cut_short_by_a_signal_is_still_classified_by_finish(tmp_path):
    T12.copy_root(tmp_path, [P.MANIFEST_REL] + list(P.PRIOR_RESULTS))

    def runner(ctx):                 # the reused runner ended its row; SIGTERM arrived before the reclassification
        a = M14['assignments'][0]
        rec = OrderedDict((k, a[k]) for k in ('order', 'assignment_id', 'backend', 'alias', 'port'))
        ctx['records'].append(rec)
        ctx['ledger'].start(1, run_id='run-1')
        run_dir = ctx['raw'] / 'run-1'
        run_dir.mkdir()
        (run_dir / 'episode.json').write_text(json.dumps(dict(exit_status='Submitted', physical_requests=2)))
        (run_dir / 'submission.diff').write_text('diff --git a/mod.py b/mod.py\n')
        ctx['capacity_interruption'] = OrderedDict(classification=P.CAPACITY, run_id='run-1', order=1,
                                                   breach=['physical_free_pct 9 is below 10'])
        rec.update(run_id='run-1', state='interrupted')
        ctx['ledger'].end(1, state='interrupted', run_id='run-1')
        raise S.Interrupted('SIGTERM')
    assert P.main([], root=tmp_path, probes=OrderedDict(ok=T13.ok_check), runner=runner,
                  precondition=T13.ok_check) == 0
    summary = json.loads((tmp_path / P.OUTPUTS['published'] / 'probe' / 'pair_summary.json').read_text())
    row = summary['assignments'][0]
    assert (summary['status'], row['state'], row['state_reported_by_the_reused_runner'], row['outcome_source'],
            row['exit_status'], row['eligible'], row['eligible_without_the_capacity_rule'], row['grade']['status']) == (
        'INTERRUPTED', P.CAPACITY, 'interrupted', P.CAPACITY, 'Submitted', False, True, P.NOT_GRADED)
    ledger = lines(tmp_path / P.OUTPUTS['raw'] / 'probe' / 'ledger.jsonl')
    assert [(e['event'], e.get('state')) for e in ledger] == [('start', None), ('end', 'interrupted'),
                                                              ('end', P.CAPACITY)]


def test_the_capacity_record_never_costs_the_summary(tmp_path):
    for name, damage in (('torn', 'lines'), ('unbuildable', 'published copy')):
        root = tmp_path / name
        T12.copy_root(root, [P.MANIFEST_REL] + list(P.PRIOR_RESULTS))

        def runner(ctx):
            if damage == 'lines':             # a torn line and a non-object line
                with open(ctx['raw'] / P.SERIES, 'a') as fh:
                    fh.write('{"phase": "episode", "physical_free_pct": 7\n[1, 2]\n')
            else:                             # the published copy exists already: the record cannot be written
                (ctx['pub'] / P.SERIES).write_text('')
            return None
        assert P.main([], root=root, probes=OrderedDict(ok=T13.ok_check), runner=runner,
                      precondition=T13.ok_check) == 0
        summary = json.loads((root / P.OUTPUTS['published'] / 'probe' / 'pair_summary.json').read_text())
        cap = summary['capacity']
        if damage == 'lines':
            assert (cap['series']['samples'], cap['series']['unparsable_lines'], summary['status']) == (
                1, 2, 'COMPLETED')
        else:
            assert cap['error'].startswith('FileExistsError') and cap['outcome_rule'] == P.SUPERVISION[
                'classification']
        assert summary['capacity_outcome_rule_precedence'] == P.SUPERVISION['outcome_rule_precedence']


# ---------------------------------------------------------------- (d2) the real entry: the capacity-stop latch

def test_the_latch_is_declared_in_the_manifest_and_equals_the_entry_code():
    latch = M14['supervision']['entry_latch']
    assert latch['overrides'] == E14.LATCH_OVERRIDES == P.LATCH_OVERRIDES and len(latch['overrides']) == 3
    assert (latch['entry'], latch['record'], E14.LATCH_RECORD, P.LATCH_RECORD) == (
        'experiments/v2_agent/req014_entry.py', 'control/<run_id>/capacity_latch.json', 'capacity_latch.json',
        'capacity_latch.json')
    assert M14['repair1']['runtime_overrides'] == M13['repair1']['runtime_overrides']        # repair1 unchanged
    stop = M14['supervision']['stop']
    for part in ('SIGALRM', 'entry_latch', 'At once the owned 14B server is stopped', 'unrecorded_container',
                 'exited_child', 'returncode -1'):
        assert part in stop, part
    semantics = [x for x in M14['semantics_differences'] if x.startswith('A capacity interruption ends the episode')]
    assert len(semantics) == 1 and 'supervision.entry_latch' in semantics[0] and 'returncode -1' in semantics[0]


def test_the_latch_refuses_every_query_after_a_sigalrm_and_only_counts_one_after_inference():
    PE = E14.E13.R.CE.PE                          # the real pilot_episode; only a stand-in namespace is changed
    frozen_timeout = PE.request_timeout
    ns = SimpleNamespace(EpisodeDeadline=PE.EpisodeDeadline, request_timeout=frozen_timeout)
    terminal = SimpleNamespace(run_terminal_phase=lambda **kw: ('terminal phase', kw))
    module = SimpleNamespace(CE=SimpleNamespace(PE=ns, T=terminal))
    raised = []

    def frozen_alarm(signum, frame):                           # exactly req012_entry.main's alarm handler
        raised.append(signum)
        raise PE.EpisodeDeadline('absolute inference deadline reached; cleanup only')
    old = signal.getsignal(signal.SIGALRM)
    try:
        latch = E14.install_latch(module)
        far = time.time() + 600
        assert 0 < ns.request_timeout(far) <= 900 and latch['installed'] is False        # no handler yet: not chained
        signal.signal(signal.SIGALRM, frozen_alarm)
        assert 0 < ns.request_timeout(far) <= 900 and latch['installed'] is True
        assert signal.getsignal(signal.SIGALRM) is not frozen_alarm
        with pytest.raises(PE.EpisodeDeadline, match='absolute inference deadline reached'):
            signal.raise_signal(signal.SIGALRM)                # the frozen handler still raises (then may be swallowed)
        with pytest.raises(PE.EpisodeDeadline) as refused:
            ns.request_timeout(far)                            # the next query: refused before dispatch
        assert str(refused.value) == E14.LATCH_MESSAGE
        with pytest.raises(PE.EpisodeDeadline, match='^episode inference deadline reached$'):
            ns.request_timeout(time.time() - 1)                # past the deadline the frozen refusal comes first
        assert terminal.run_terminal_phase(endpoint='e') == ('terminal phase', {'endpoint': 'e'})
        signal.raise_signal(signal.SIGALRM)                    # after the inference phase: counted, never raised
        assert raised == [signal.SIGALRM] and PE.request_timeout is frozen_timeout      # the real module is untouched
        assert (latch['sigalrm_received'], latch['sigalrm_counted_only'], latch['queries_refused_by_latch'],
                latch['first_sigalrm_after_inference_end'], latch['inference_end_utc'] is not None) == (
            2, 1, 1, False, True)
    finally:
        signal.signal(signal.SIGALRM, old)


_RUN_LINE = r'''  run) printf '%s\n' "$@" > "$STATE/run_argv"; cat "$STATE/container_id"; exit 0 ;;'''
assert T12.FAKE_DOCKER.count(_RUN_LINE) == 1
IN_FLIGHT_DOCKER = T12.FAKE_DOCKER.replace(_RUN_LINE, (  # `docker run -d`: the daemon registers, the CLI never returns
    r'''  run) printf '%s\n' "$@" > "$STATE/run_argv"; a=("$@"); printf '%s %s %s\n' "$(cat "$STATE/container_id")" '''
    r'''"$(grep -x -A1 -- --name "$STATE/run_argv" | tail -1)" "${a[${#a[@]}-3]}" >> "$STATE/daemon"; '''
    r'''touch "$STATE/run_started"; exec sleep 30 ;;'''))
DECOYS = [('d' * 64, 'minisweagent-decoy001'), ('e' * 64, 'someone-elses-container')]


def start_entry(base, module, sources, runtime, binding, assignment_id, script, docker=None, pre_spawn=None):
    """tests/test_req013_discriminator.run_entry's setup (the unedited REQ-011 harness in the pinned venv, through a
    one-line shim) started in its own session and left running."""
    home, state = T12.workspace(base)
    if docker is not None:
        (home / '.local/dtr-runtime/bin/docker').write_text(docker)
    shim = base / 'shim'
    shim.mkdir()
    (shim / 'req011_entry.py').write_text(T13.SHIM % (str(ROOT / 'experiments/v2_agent'), module))
    run_id = '%s__large__req011__fixture-%s' % (IID, base.name)
    run_dir, control_dir, layout_root = base / 'raw' / run_id, base / 'raw' / 'control' / run_id, base / 'layout'
    for d in (run_dir, control_dir, layout_root / 'work'):
        d.mkdir(parents=True)
    control = dict(request='fixture', binding_sha256=binding, assignment_id=assignment_id, model_sha256=LARGE_SHA,
                   admitted_sources=sources, runtime=runtime, namespace=dict(
                       instance=IID, backend='large', arm='baseline', position=1, port=8293, alias=LARGE_ALIAS,
                       run_dir=str(run_dir), run_id=run_id, expected_image=PIN,
                       served=json.dumps(dict(model_file='fixture.gguf', model_sha256=LARGE_SHA)), counted_before=0,
                       request_limit=48, host_reserve_bytes=1 << 30))
    config = dict(out=str(base / 'out'), script=script, alias=LARGE_ALIAS, model_file='fixture.gguf',
                  module_dir=str(shim), layout_root=str(layout_root), control=control,
                  control_path=str(control_dir / 'entry.json'), deadline_in=600)
    (base / 'config.json').write_text(json.dumps(config))
    before = pre_spawn(state) if pre_spawn else None
    log = open(base / 'harness_output.txt', 'w')
    p = subprocess.Popen([str(T12.MSWEA_PY), str(T12.REQ011_HARNESS), str(base / 'config.json')], stdout=log,
                         stderr=subprocess.STDOUT, env=T12.child_env(home, base), cwd=str(base), start_new_session=True)
    log.close()
    return dict(p=p, base=base, run_dir=run_dir, control=control_dir, state=state, before=before)


def interrupt_when(r, trigger, parent=True, grace=90):
    """Once `trigger` exists (the entry is blocked inside a subprocess.run), stop it: through req014_pair.interrupt with
    a recorded server stop (parent=True), or with a bare SIGALRM. Then collect the harness records."""
    p, stops = r['p'], []
    try:
        assert T11.wait_until(lambda: trigger.exists() or p.poll() is not None, 180), 'the trigger never appeared'
        assert p.poll() is None, (r['base'] / 'harness_output.txt').read_text()[-4000:]
        if parent:
            r['cap'] = P.interrupt(p, time.time() + 600, OrderedDict(), dict(P.CAPS, child_cleanup_grace_s=grace),
                                   time.time, stop_server=lambda: stops.append(time.time()) or True)
        else:
            os.kill(p.pid, signal.SIGALRM)
        p.wait(timeout=grace)
    finally:
        if p.poll() is None:
            p.kill()
            p.wait(timeout=30)
        try:
            os.killpg(p.pid, signal.SIGKILL)                    # anything the fake docker left in the session
        except (ProcessLookupError, PermissionError):
            pass
    out = r['base'] / 'out'
    r.update(stops=stops, returncode=p.returncode, harness=json.loads((out / 'harness.json').read_text()),
             bodies=[x.read_bytes() for x in sorted((out / 'terminal').glob('*.body'))])
    return r


def record(r, name, where='run_dir'):
    path = r[where] / name
    return json.loads(path.read_text()) if path.exists() else None


@pytest.fixture(scope='module')
def alarm_entries(tmp_path_factory):
    if not T12.MSWEA_PY.exists() or not T11.DATA.exists():
        pytest.skip('pinned mini-swe-agent venv or the pinned SWE-bench Verified parquet is absent')
    digests = lambda rels: {rel: sha((ROOT / rel).read_bytes()) for rel in rels}  # noqa: E731
    binding, problems = P.A.compute_binding(P.A.Layout(ROOT))
    assert problems == []
    runtime = {k: binding['runtime'][k] for k in ('sdk_traced_files', 'mini_swe_agent_sources')}
    work = tmp_path_factory.mktemp('req014_alarm')
    s13, s14 = digests(P13.SOURCES), digests(P.SOURCES)
    command = lambda marker: [T11.act('touch %s && exec sleep 30' % marker), T11.LS, T11.SUBMIT]  # noqa: E731
    out = {}
    marker = work / 'command14_started'
    out['command14'] = interrupt_when(start_entry(work / 'command14', 'req014_entry', s14, runtime, M14_SHA,
                                                  'req014-1-large', command(marker)), marker)
    marker = work / 'command13_started'                        # the same stop without the latch: the negative control
    out['command13'] = interrupt_when(start_entry(work / 'command13', 'req013_entry', s13, runtime, T13.MANIFEST_SHA,
                                                  'req013-1-large', command(marker)), marker, parent=False)
    docker = {}

    def pre_spawn(state):
        docker['run'], docker['calls'], docker['rows'] = daemon_docker(state / 'daemon', DECOYS,
                                                                       {'d' * 64: PIN, 'e' * 64: PIN})
        docker['ctx'] = dict(run=docker['run'], env=None, pair_deadline=time.time() + 600, clock=time.time,
                             image_id=PIN)
        return P.container_listing(docker['ctx'])              # the parent's pre-spawn listing
    r = start_entry(work / 'run14', 'req014_entry', s14, runtime, M14_SHA, 'req014-1-large', [T11.LS, T11.SUBMIT],
                    docker=IN_FLIGHT_DOCKER, pre_spawn=pre_spawn)
    out['run14'] = interrupt_when(r, r['state'] / 'run_started')
    out['run14'].update(docker, sweep=P.sweep_unrecorded(docker['ctx'], r['before']))
    return out


SWALLOWED = 'An error occurred while executing the command: absolute inference deadline reached; cleanup only'


def test_a_sigalrm_during_a_container_command_is_latched_and_no_further_request_is_sent(alarm_entries):
    r = alarm_entries['command14']
    cap = r['cap']
    assert (cap['sigalrm_sent'], cap['server_stopped_after_sigalrm'], cap['child_exited_within_grace'],
            cap['child_returncode'], len(r['stops'])) == (True, True, True, 0, 1)
    assert (r['harness']['exit_code'], r['harness']['network_attempts'], len(r['bodies'])) == (0, [], 1)
    trajectory = json.dumps(record(r, 'trajectory.json'))
    assert SWALLOWED in trajectory                           # the pinned execute swallowed it (the LB1 path is real)
    ep = record(r, 'episode.json')
    assert (ep['exit_status'], ep['error'], ep['physical_requests'], ep['logical_calls'], ep['submission_empty']) == (
        'EpisodeDeadline', E14.LATCH_MESSAGE, 1, 2, True)
    assert (r['run_dir'] / 'submission.diff').read_bytes() == b''
    for name in ('terminal_phase.json', 'exit_diagnostic.json', 'container_cleanup.json', 'effective_config.json'):
        assert (r['run_dir'] / name).exists(), name
    latch = record(r, 'capacity_latch.json', 'control')
    assert (latch['request'], latch['installed'], latch['sigalrm_received'], latch['queries_refused_by_latch'],
            latch['first_sigalrm_after_inference_end'], latch['sigalrm_counted_only'], latch['overrides']) == (
        'DTR-REQ-014', True, 1, 1, False, 0, M14['supervision']['entry_latch']['overrides'])
    assert record(r, 'repair_record.json', 'control')['runtime_overrides'] == M14['repair1']['runtime_overrides']


def test_without_the_latch_the_swallowed_sigalrm_lets_the_agent_query_again(alarm_entries):
    r = alarm_entries['command13']                              # req013_entry: the REQ-013 path, no latch
    assert (r['returncode'], r['harness']['exit_code'], len(r['bodies'])) == (0, 0, 3)
    assert SWALLOWED in r['bodies'][1].decode()                # the next request carries the swallowed observation
    assert record(r, 'episode.json')['exit_status'] == 'Submitted'
    assert record(r, 'capacity_latch.json', 'control') is None


def test_a_sigalrm_while_docker_run_is_in_flight_leaves_no_unsupervised_container(alarm_entries):
    r = alarm_entries['run14']
    assert (r['cap']['sigalrm_sent'], r['cap']['child_exited_within_grace'], r['harness']['exit_code'],
            len(r['bodies'])) == (True, True, 0, 0)
    assert record(r, 'container_ownership.json') is None        # the ID was never recorded
    ep = record(r, 'episode.json')
    receipt = record(r, 'terminal_phase.json')['cleanup']['receipt']
    assert (ep['exit_status'], ep['error'], ep['container_cleanup'], ep['terminal_phase']['diagnostic_status'],
            receipt['confirmed'], receipt['state']) == (
        'EpisodeDeadline', 'absolute inference deadline reached; cleanup only', None, 'unavailable', False, 'unknown')
    assert receipt['reason'].startswith('the environment was never created')   # so the child cannot remove it
    latch = record(r, 'capacity_latch.json', 'control')
    assert (latch['sigalrm_received'], latch['queries_refused_by_latch']) == (1, 0)
    sweep = r['sweep']                                          # the parent's rule for a container started unrecorded
    registered = (r['state'] / 'daemon').read_text().split()
    assert registered[0] == CID and registered[1].startswith('minisweagent-') and registered[2] == PIN
    assert (r['before'], sweep['removed_ids'], sweep['removal']['complete']) == (DECOYS, [CID], True)
    assert [c for c in r['calls'] if c[:2] == ['docker', 'rm']] == [['docker', 'rm', '-f', CID]]
    assert r['rows']() == DECOYS                                 # the pre-existing minisweagent decoy is untouched


def test_the_latch_leaves_a_normal_episode_alone(entries):
    b = entries['large14']
    latch = json.loads((b['control'] / 'capacity_latch.json').read_text())
    assert (latch['installed'], latch['sigalrm_received'], latch['queries_refused_by_latch'],
            latch['inference_end_utc'] is not None) == (True, 0, 0, True)
    for name in ('unadmitted', 'req013_binding'):                 # a refused entry installs nothing
        assert not (entries[name]['control'] / 'capacity_latch.json').exists()


# ---------------------------------------------------------------- (e) REQ-013 is preserved

def test_the_req013_manifest_records_and_entry_are_unchanged_and_the_namespaces_are_disjoint():
    for rel, digest in REQ013_FILES.items():
        assert sha((ROOT / rel).read_bytes()) == digest, rel
    assert not (ROOT / 'results/v2_agent/req013_14b_discriminator_20260924/probe').exists()   # REQ-013 was never run
    assert (M13['swap_rule']['min_free_gib'], P13.SWAP['min_free_bytes']) == (4, 4 * GiB)       # its rule is kept
    for key in ('raw', 'published', 'pause_file'):
        assert P.OUTPUTS[key] != P13.OUTPUTS[key] and 'req013' not in P.OUTPUTS[key]
    assert (P.MANIFEST_REL, P.HOLDER, P.REQUEST) != (P13.MANIFEST_REL, P13.HOLDER, P13.REQUEST)
    assert set(P13.SOURCES) < set(P.SOURCES) and P.MANIFEST_REL in P.SOURCES


# ---------------------------------------------------------------- (f) single shot, the summary and the watchdog

def test_the_probe_is_single_shot_and_publishes_under_req014(tmp_path, capsys):
    T12.copy_root(tmp_path, [P.MANIFEST_REL] + list(P.PRIOR_RESULTS))
    calls = []

    def runner(ctx):
        calls.append(ctx['sources'])
        ctx['ledger'].start(1, run_id='run-1')
        (ctx['raw'] / 'run-1').mkdir()
        raise S.Interrupted('SIGTERM')
    probes = OrderedDict(ok=T13.ok_check)
    assert P.main([], root=tmp_path, probes=probes, runner=runner, precondition=T13.ok_check) == 0
    summary = json.loads((tmp_path / P.OUTPUTS['published'] / 'probe' / 'pair_summary.json').read_text())
    assert (summary['request'], summary['status'], summary['interrupted_or_error'], summary['probe_cap_s']) == (
        'DTR-REQ-014', 'INTERRUPTED', 'SIGTERM', 3600)
    assert summary['published'] == 'results/v2_agent/req014_14b_capacity_probe_20260924/probe'
    assert [(x['order'], x['assignment_id'], x['backend'], x['state']) for x in summary['assignments']] == [
        (1, 'req014-1-large', 'large', 'interrupted')]
    assert summary['requests']['physical_counted_total'] == 48 and summary['capacity']['series']['samples'] == 1
    assert all(summary['prior_results'][rel]['unchanged'] for rel in P.PRIOR_RESULTS)
    assert P.main([], root=tmp_path, probes=probes, runner=runner, precondition=T13.ok_check) == 3
    assert len(calls) == 1                                                                 # never re-dispatched
    ro = tmp_path / 'read_only'
    T12.copy_root(ro, [P.MANIFEST_REL])
    capsys.readouterr()
    assert P.main(['--admission-only'], root=ro, probes=capacity_probes(pct=49)) == 1
    adm = json.loads(capsys.readouterr().out)
    assert (adm['admitted'], adm['memory']['ok'], adm['swap']['ok'], adm['mode']) == (False, False, True,
                                                                                       'admission-only')
    assert not (ro / 'work').exists() and not (ro / 'results').exists()
    assert list(P.admission_probes(M14)) == ['manifest', 'sources', 'runtime', 'images', 'conflicts', 'isolation',
                                             'disk', 'models', 'memory', 'swap', 'gate', 'step1', 'prereq']


def test_the_ownership_holder_and_watchdog_launcher_are_req014_and_stop_the_server_after_a_parent_sigkill(
        tmp_path, monkeypatch):
    monkeypatch.setattr(P.PR, 'SERVERS', tmp_path / 'own.json')
    P.Servers({}, dict(hard_deadline_epoch=0, block_start_utc='a', block_hard_end_utc='b'), tmp_path)._record()
    assert json.loads((tmp_path / 'own.json').read_text())['holder'] == (
        'DTR-AgentEvals worker (DTR-REQ-014 14B capacity probe)') == P.HOLDER
    stub = T11.STUB_PARENT.replace('import req011_pair as P', 'import req014_pair as P')
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
        assert (cfg['request'], cfg['holder']) == ('DTR-REQ-014', P.HOLDER)
        assert (P13.REQUEST, P13.HOLDER) == ('DTR-REQ-013', 'DTR-AgentEvals worker (DTR-REQ-013 14B discriminator)')
        args = subprocess.run(['ps', '-ww', '-o', 'args=', '-p', str(pids['watchdog'])], capture_output=True,
                              text=True).stdout
        assert 'req014_pair.py --watchdog' in args and 'req013_pair.py' not in args
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


# ---------------------------------------------------------------- (g) the prerequisite record

def write_prereq(root, **changes):
    rec = dict(request='DTR-REQ-014', passed=True, scenario_source=dict(
        fixture_file_sha256=sha((ROOT / 'tests/test_req011_pair.py').read_bytes()),
        watchdog_source_sha256=sha((ROOT / 'experiments/v2_agent/req011_pair.py').read_bytes())))
    rec.update(changes)
    path = root / P.PREREQ['watchdog_host_check']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec))


def test_the_probe_requires_a_passing_req014_prerequisite_record(tmp_path):
    T12.copy_root(tmp_path, ['experiments/v2_agent/req011_pair.py', 'tests/test_req011_pair.py'])
    git = lambda code: (lambda cmd, env=None, timeout=None: (code, '', ''))  # noqa: E731
    assert P.probe_prereq(tmp_path, git(0))[0] is False                                    # no record
    write_prereq(tmp_path)
    assert P.probe_prereq(tmp_path, git(0))[0] is True
    assert P.probe_prereq(tmp_path, git(1))[0] is False                                    # untracked or changed
    for change in (dict(passed=False), dict(passed='true'), dict(request='DTR-REQ-013'), dict(scenario_source={}),
                   dict(scenario_source=dict(fixture_file_sha256='0' * 64, watchdog_source_sha256='0' * 64))):
        write_prereq(tmp_path, **change)
        assert P.probe_prereq(tmp_path, git(0))[0] is False, change
    write_prereq(tmp_path)
    (tmp_path / 'experiments/v2_agent/req011_pair.py').write_text('# changed watchdog source\n')
    assert P.probe_prereq(tmp_path, git(0))[0] is False


def test_the_launch_refuses_before_its_namespace_without_the_prerequisite(tmp_path, pinned_cfg):
    root = gate_root(tmp_path)
    T12.copy_root(root, [P13.STEP1['reconciliation'], P13.STEP1['watchdog_host_check'], 'tests/test_req011_pair.py'])
    started = []
    runner = lambda ctx: started.append(ctx) or None  # noqa: E731
    pre = lambda r: P.preconditions(r, run=GIT_OK, load_cfg=lambda: pinned_cfg)  # noqa: E731
    ok, d = pre(root)
    assert not ok and d['gate']['checks']['configuration_proof'] is True and d['prereq']['passed'] is False
    assert d['step1']['reconciliation_verified'] is True and d['step1']['watchdog_host_check_passed'] is True
    assert P.main([], root=root, probes=OrderedDict(ok=T13.ok_check), runner=runner, precondition=pre) == 3
    assert not (root / P.OUTPUTS['raw']).exists() and not (root / P.OUTPUTS['published']).exists() and started == []
    write_prereq(root)
    assert P.main([], root=root, probes=OrderedDict(ok=T13.ok_check), runner=runner, precondition=pre) == 0
    assert len(started) == 1


def test_prereq_checks_the_sources_then_writes_the_req014_watchdog_record_once(tmp_path):
    git = lambda code: (lambda cmd, env=None, timeout=None: (code, '', ''))  # noqa: E731
    called = []
    assert P.prereq_main(ROOT, run=git(1), check=lambda root: called.append(root)) == 3 and called == []
    row = dict(pid=11, equal_raw=False, watchdog_rule_match=True)
    good = dict(pids=dict(server=11), watchdog_ready=True, recorded_servers=[row], server_alive_while_parent_lives=True,
                stopped_within_grace=True, decoy_untouched=True, watchdog_exited=True, owned_stub_stopped=True)
    fixture_ok = lambda base: dict(passed=True, returncode=0, summary='1 passed in 2.0s')  # noqa: E731
    check = lambda root: W.main(root=tmp_path, run_scenario=lambda base: good, fixture=fixture_ok)  # noqa: E731
    assert P.prereq_main(ROOT, run=git(0), check=check) == 0
    rec = json.loads((tmp_path / P.PREREQ['watchdog_host_check']).read_text())
    assert (rec['request'], rec['passed']) == ('DTR-REQ-014', True)
    assert rec['raw_dir'].startswith('work/runs/req014_14b_capacity_probe_20260924/watchdog_check/')
    assert (W.OUT, W.RAW, W.REQUEST) == ('results/v2_agent/req013_14b_discriminator_20260924/watchdog_host_check.json',
                                         'work/runs/req013_14b_discriminator_20260924/watchdog_check', 'DTR-REQ-013')
    assert P.prereq_main(ROOT, run=git(0), check=check) == 3                              # write-once
    assert not (tmp_path / 'results/v2_agent/req013_14b_discriminator_20260924').exists()
