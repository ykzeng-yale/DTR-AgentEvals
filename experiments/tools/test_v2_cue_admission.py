"""Fixtures for the DTR-REQ-005 cue-v1 frozen admission (cue_admission.py) and queue skeleton (cue_runner.py).

No model, server, container, evaluator or network call. Every test runs in a DISPOSABLE copy of the bound inputs
under pytest's tmp_path (experiments/tools/v2_cue_tree_fixture.py): the cue-v1 execution modules, the accepted
helpers, the frozen yaml-v1 reference sources, pin records, accepted-pin documents, the pinned dataset file, the pinned
mini-swe-agent sources and the traced SDK files are copied byte-for-byte from this checkout. The episode function is
an in-process fake admitted only in such a copy (fixture=True); nothing it returns is executed. Nothing under this
checkout's results/ is created or changed, and results/v2_agent/pilot_20260923_cue_v1 is never created here.

Every expected value is written out by hand: module lists, changed-class sets, digests published in the yaml-v1
amendment and the cue-v1 spec, the 12 assignment rows, stop records and request totals. The only computed values in
this file are the hash-chain links of deliberately forged ledger records (hashlib over the exact bytes the test
writes), which a forged record needs so that the rule under test, not the chain, is what refuses it.
"""
import collections
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'experiments/v2_agent'))
import cue_admission as A  # noqa: E402
import cue_runner as CR  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
import v2_cue_tree_fixture as TREE  # noqa: E402

MSWEA_SRC, SITE = TREE.MSWEA_SRC, TREE.SITE
WORK_PRESENT, WORK_REASON = TREE.available()
pytestmark = pytest.mark.skipif(not WORK_PRESENT, reason=WORK_REASON or '')

NAMESPACE = 'results/v2_agent/pilot_20260923_cue_v1'
ASSIGNMENT_IDS = [
    'psf__requests-1142__small__cue-v1__baseline',
    'psf__requests-1142__small__cue-v1__cue',
    'psf__requests-1142__large__cue-v1__cue',
    'psf__requests-1142__large__cue-v1__baseline',
    'scikit-learn__scikit-learn-10297__small__cue-v1__cue',
    'scikit-learn__scikit-learn-10297__small__cue-v1__baseline',
    'scikit-learn__scikit-learn-10297__large__cue-v1__baseline',
    'scikit-learn__scikit-learn-10297__large__cue-v1__cue',
    'sympy__sympy-11618__small__cue-v1__baseline',
    'sympy__sympy-11618__small__cue-v1__cue',
    'sympy__sympy-11618__large__cue-v1__cue',
    'sympy__sympy-11618__large__cue-v1__baseline',
]
DRY_RUN_ROWS = [
    '1 psf__requests-1142 small baseline B {}',
    '2 psf__requests-1142 small cue B {}',
    '3 psf__requests-1142 large cue C {}',
    '4 psf__requests-1142 large baseline C {}',
    '5 scikit-learn__scikit-learn-10297 small cue C {}',
    '6 scikit-learn__scikit-learn-10297 small baseline C {}',
    '7 scikit-learn__scikit-learn-10297 large baseline B {}',
    '8 scikit-learn__scikit-learn-10297 large cue B {}',
    '9 sympy__sympy-11618 small baseline B {}',
    '10 sympy__sympy-11618 small cue B {}',
    '11 sympy__sympy-11618 large cue C {}',
    '12 sympy__sympy-11618 large baseline C {}',
]
CUE = ('Recent actions returned the same visible feedback repeatedly. Use the existing /testbed checkout. Choose a '
       'different action that will provide useful new evidence, or explain why repeating the action is necessary. '
       'Check the current working directory and the existing submission instructions.')
HOLD = 'fixture host gate: hold before any dispatch'


# ------------------------------------------------------------------ disposable tree

@pytest.fixture(scope='module')
def template(tmp_path_factory):
    return TREE.build(tmp_path_factory.mktemp('cue_admission_template') / 'repo')


@pytest.fixture
def root(template, tmp_path):
    return TREE.copy(template, tmp_path / 'repo')


def run_queue(episode_fn, **kw):
    """cue_runner.run_queue with an in-process fixture episode function, admitted only in a disposable copy."""
    kw.setdefault('fixture', True)
    return CR.run_queue(episode_fn, **kw)


def change_one_byte(path, old, new):
    data = path.read_bytes()
    assert data.count(old) == 1, 'fixture substring must be unique in %s' % path.name
    assert len(old) == len(new) and sum(a != b for a, b in zip(old, new)) == 1
    path.write_bytes(data.replace(old, new))


def ledger_events(layout):
    return [json.loads(line) for line in layout.ledger_path.read_bytes().split(b'\n')[:-1]]


def episode_returning(requests=7, calls=None, **extra):
    def episode(row, context):
        if calls is not None:
            calls.append(row['position'])
        return dict(dict(physical_requests=requests, storage_integrity='resolved', exit_status='Submitted'), **extra)
    return episode


def never_called(row, context):
    raise AssertionError('the episode function must not be called')


def hold_at(position):
    return lambda row: ('fixture host gate before position %d' % row['position']
                        if row['position'] == position else None)


def launch_and_hold(layout):
    return run_queue(never_called, layout=layout, gate=lambda row: HOLD)


def forge(layout, **fields):
    """Append ONE forged record with a valid chain link (hashlib over the previous line's exact bytes)."""
    data = layout.ledger_path.read_bytes()
    last_line = data.split(b'\n')[:-1][-1]
    last = json.loads(last_line)
    record = dict(seq=last['seq'] + 1, prev_sha256=hashlib.sha256(last_line + b'\n').hexdigest(),
                  cohort='cue-v1', binding_sha256=last['binding_sha256'], utc='2026-09-23T00:00:00Z')
    record.update(fields)
    line = json.dumps(record, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode() + b'\n'
    layout.ledger_path.write_bytes(data + line)
    # the head names the forged record too, so the rule under test (not the truncation check) is what refuses it
    layout.out.joinpath('queue_ledger.head.json').write_text(json.dumps(dict(
        cohort='cue-v1', binding_sha256=last['binding_sha256'], seq=record['seq'],
        last_sha256=hashlib.sha256(line).hexdigest(), utc='2026-09-23T00:00:00Z'), sort_keys=True) + '\n')


# ------------------------------------------------------------------ the binding binds every class

def test_binding_binds_every_required_execution_module_and_the_import_closure(root):
    binding, problems = A.compute_binding(A.Layout(root))
    assert problems == []
    assert sorted(binding['modules']) == [
        'cue_admission.py', 'cue_cohort.py', 'cue_detector.py', 'cue_episode.py', 'cue_runner.py', 'cue_terminal.py',
        'cue_transport.py', 'exit_capture.py', 'pilot_episode.py', 'request_receipt.py', 'trajectory_triples.py',
        'workspace_capture.py']
    assert binding['module_roles'] == {
        'cue_admission.py': 'new cue-v1 execution module',
        'cue_cohort.py': 'lead-accepted cue-v1 helper',
        'cue_detector.py': 'lead-accepted cue-v1 helper',
        'cue_episode.py': 'new cue-v1 execution module',
        'cue_runner.py': 'new cue-v1 execution module',
        'cue_terminal.py': 'new cue-v1 execution module',
        'cue_transport.py': 'new cue-v1 execution module',
        'exit_capture.py': 'lead-accepted cue-v1 helper',
        'pilot_episode.py': 'imported by a bound module (import closure)',
        'request_receipt.py': 'lead-accepted cue-v1 helper',
        'trajectory_triples.py': 'lead-accepted cue-v1 helper',
        'workspace_capture.py': 'reused unmodified execution module',
    }
    # the frozen yaml-v1 episode is bound at the digest its own published cohort binding carries
    assert binding['modules']['pilot_episode.py'] == '164b7878f7a720a74ba913b97ee07ba287a556cb3ac6310aa95d2f2c91dbe6f5'


def test_binding_records_the_accepted_cue_detector_coding_guide_and_plan(root):
    binding, _ = A.compute_binding(A.Layout(root))
    assert binding['cue'] == dict(text=CUE, sha256='80d52625bd593cd6fecafeb06daca898792979592272d9fadcf0ddd04bd39d9e',
                                  utf8_bytes=290, characters=290, source='experiments/v2_agent/cue_detector.py')
    detector = binding['detector']
    assert detector['id'] == 'repeated-action-cue-v1'
    assert detector['pattern_widths'] == {'AAA': 3, 'ABABAB': 6}
    assert detector['modes'] == ['live', 'observe']
    assert (detector['first_logical_call'], detector['horizon_default'], detector['one_cue_maximum']) == (1, 24, True)
    assert detector['trigger_note'] == 'trigger means repeated visible feedback, not proven unchanged state'
    assert binding['coding_guide']['path'] == 'docs/req005_visible_evidence_guide_20260923.md'
    assert binding['plan']['plan_sha256'] == 'dc687c8413d5aa8f81cb498b22cc5fac5f4fcf2535bf0c66aea8db2fb882c1ae'
    assert binding['plan']['pair_order'] == ['B', 'C', 'C', 'B', 'B', 'C']
    assert [row['assignment_id'] for row in binding['plan']['assignments']] == ASSIGNMENT_IDS


def test_binding_reuses_the_frozen_pilot_pin_sources_without_restating_them(root):
    pins = A.compute_binding(A.Layout(root))[0]['pins']
    assert pins['pin_sources'] == {
        'configs/v2_fixed_backend_development_pilot_20260922.json':
            'ab871558c7cbc5feca17477c34164281b90a3d49a17fb3d37f3f1fb1dc3ba8e1',
        'configs/v2_fixed_backend_development_pilot_yaml_v1_20260922.json':
            '468cdf665f8104755e3cc8019e31fa72fbc1901a6bdd8d6c13fef4813e6d475a',
        'experiments/v2_agent/pilot_episode.py': '164b7878f7a720a74ba913b97ee07ba287a556cb3ac6310aa95d2f2c91dbe6f5',
        'experiments/v2_agent/pilot_runner.py': '974df398415db22ed6676e04f0be5c1d93a7599d725f43f03fb989d77cbba10c',
        'results/v2_agent/coder_conversion_20260922.json':
            '7e165c220b2d4f045375a98e3edc35ccc5a0133221bfd8bff18c397cbab61c1f',
        'results/v2_agent/pilot_20260922_yaml_v1/cohort_binding.json':
            '7b37292d9f1aeec14360323855f14f1fcdde2d73cd61188bdf42d6b885b53f0c',
        'results/v2_agent/pilot_frame_20260922.json':
            '3c29e1da8597e4a72fa74951bd5eb194566be69a90e00c6cb78af9c73e5654a7',
        MSWEA_SRC + '/config/default.yaml': '112aa58328f478a41cc2630702a4b89ef459e912870e05065157ed221f56701f',
    }
    assert pins['models'] == {
        'small': dict(alias='qwen2.5-coder-7b-instruct-c03e6d3-q4_k_m', repository='Qwen/Qwen2.5-Coder-7B-Instruct',
                      source_commit='c03e6d358207e414f1eca0bb1891e29f1db0e242',
                      gguf_file='work/models/converted_4fea119/qwen2.5-coder-7b-instruct-c03e6d3-q4_k_m.gguf',
                      gguf_sha256='87a3665ca3247c54dfa198010f6e1f48d41611029bbcb5ed185a5ad05fcd3b81',
                      gguf_bytes=4683074208, port=8291),
        'large': dict(alias='qwen2.5-coder-14b-instruct-aedcc2d-q4_k_m', repository='Qwen/Qwen2.5-Coder-14B-Instruct',
                      source_commit='aedcc2d42b622764e023cf882b6652e646b95671',
                      gguf_file='work/models/converted_4fea119/qwen2.5-coder-14b-instruct-aedcc2d-q4_k_m.gguf',
                      gguf_sha256='b179f09d5f73776e68623384d95a0dbd73ccf038e34db50b508e9c3baf468066',
                      gguf_bytes=8988110944, port=8293),
    }
    assert pins['images'] == {
        'psf__requests-1142': 'sha256:d461c7c6e50916d9837e81604d8e79efca06af9c063f5477b0086102a96b50cf',
        'scikit-learn__scikit-learn-10297': 'sha256:adc94ee4331c08388d2e03862f1a68e2e0ed0ca3b832ba928ef870ed1122b55a',
        'sympy__sympy-11618': 'sha256:c073cca08a52c8cd039b2c015aa19740ef235febbd5080c838c79fe93d905f28',
    }
    assert pins['llama_cpp'] == dict(commit='4fea119de30f6a923992780f6fd5ccb0bee5d47d',
                                     llama_server_sha256='783e0f34f7c08fd41e43a287577fd92b715eef7d7f3b45c380cd8d2338d8ea74')
    assert pins['harness'] == dict(mini_swe_agent='04d809ceab9df28f9adaed044884180159172930',
                                   default_yaml_sha256='112aa58328f478a41cc2630702a4b89ef459e912870e05065157ed221f56701f',
                                   default_yaml=MSWEA_SRC + '/config/default.yaml', configuration_binding='yaml-v1')
    assert pins['evaluator']['expected_identity']['evaluator_commit'] == 'f7bbbb2ccdf479001d6467c9e34af59e44a840f9'
    assert (pins['evaluator']['attempt_timeout_s'], pins['evaluator']['retry_max']) == (1800, 1)
    assert pins['frozen_reference'] == {
        'pilot_episode.py': '164b7878f7a720a74ba913b97ee07ba287a556cb3ac6310aa95d2f2c91dbe6f5',
        'pilot_runner.py': '974df398415db22ed6676e04f0be5c1d93a7599d725f43f03fb989d77cbba10c',
        'pilot_cohort.py': '59d271bd32217bd3c3a56c3dd4c20fd8eadd441377db7334c0932a325100851a',
        'pilot_report.py': '1afa9002344557f4fd518044313f2fd277528a06a5fef667966175804711e10f',
        'pilot_grade.py': '0c2a5a5da861a42fd1dbc79c01ff4b031bff8d0a3cbcda8b90e869161f70e7f1',
    }
    assert [(p['position'], p['backend'], p['port']) for p in pins['assignment_pins']] == [
        (1, 'small', 8291), (2, 'small', 8291), (3, 'large', 8293), (4, 'large', 8293), (5, 'small', 8291),
        (6, 'small', 8291), (7, 'large', 8293), (8, 'large', 8293), (9, 'small', 8291), (10, 'small', 8291),
        (11, 'large', 8293), (12, 'large', 8293)]


def test_binding_settings_deadlines_and_storage_are_the_lead_numbers(root):
    binding = A.compute_binding(A.Layout(root))[0]
    settings = {k: v for k, v in binding['settings'].items() if k not in ('sources', 'endpoint')}
    assert settings == dict(horizon_h=24, step_limit=24, temperature=0.0, max_tokens=1536, context_per_slot=16384,
                            physical_attempts_per_logical_call=2, n_assignments=12, max_physical_requests=576,
                            max_physical_requests_per_assignment=48, command_timeout_s=60, request_timeout_s=900,
                            episode_wall_s=1800, cost_limit=0.0, max_cues_per_episode=1,
                            configuration_binding='yaml-v1')
    assert binding['settings']['endpoint'].startswith('Submitted-only')
    deadlines = {k: v for k, v in binding['deadlines'].items() if k != 'rules'}
    assert deadlines == dict(episode_wall_s=1800, block_cap_s=7200, kill_margin_s=300, model_switch_allowance_s=300,
                             child_cleanup_grace_s=120, server_cleanup_reserve_s=90, request_timeout_s=900,
                             command_timeout_s=60, evaluator_attempt_timeout_s=1800, diagnostic_max_s=30,
                             post_inference_cleanup_window_s=120, cleanup_reserve_min_s=90,
                             diagnostic_subprocess_timeout_max_s=60)
    assert binding['deadlines']['rules']['phase_deadline'] == \
        'min(actual_inference_end + 120 s, existing absolute cleanup cap)'
    assert binding['deadlines']['rules']['diagnostic_subprocess_timeout'] == \
        'min(remaining diagnostic time, absolute cleanup deadline - 90 s, 60 s)'
    storage = binding['storage']
    assert (storage['request_body_cap_bytes'], storage['cohort_raw_body_reservation_bytes'],
            storage['start_free_space_above_host_reserve_bytes'], storage['public_request_whole_max_bytes'],
            storage['public_preview_head_bytes'], storage['public_preview_tail_bytes'],
            storage['public_request_receipt_cap_bytes'], storage['public_outcome_record_cap_bytes']) == (
        8388608, 4831838208, 6442450944, 65536, 32768, 32768, 131072, 131072)


def test_binding_runtime_binds_the_pinned_harness_sources_and_sdk_records(root):
    runtime = A.compute_binding(A.Layout(root))[0]['runtime']
    assert {name: row['dist_info'] for name, row in runtime['sdk_distributions'].items()} == {
        'httpcore': 'httpcore-1.0.9.dist-info', 'httpx': 'httpx-0.28.1.dist-info',
        'litellm': 'litellm-1.102.0.dist-info', 'openai': 'openai-2.54.0.dist-info',
        'tenacity': 'tenacity-9.1.4.dist-info'}
    assert runtime['mini_swe_agent_sources']['config/default.yaml'] == \
        '112aa58328f478a41cc2630702a4b89ef459e912870e05065157ed221f56701f'
    assert 'models/litellm_textbased_model.py' in runtime['mini_swe_agent_sources']
    assert not any('__pycache__' in name or name.endswith('.pyc') for name in runtime['mini_swe_agent_sources'])


def test_the_binding_holds_no_absolute_or_host_path(root):
    binding = A.compute_binding(A.Layout(root))[0]
    text = json.dumps(binding)
    assert str(root) not in text and str(Path.home()) not in text

    def strings(value):
        if isinstance(value, dict):
            for key, item in value.items():
                yield key
                yield from strings(item)
        elif isinstance(value, list):
            for item in value:
                yield from strings(item)
        elif isinstance(value, str):
            yield value
    assert not [s for s in strings(binding) if s.startswith('/')]


# (file, unique old bytes, new bytes differing in exactly one byte, changed classes, one expected changed path)
ONE_BYTE_CASES = [
    ('experiments/v2_agent/cue_episode.py', b"'cue-v1' episode driver:", b"'cue-v1' Episode driver:", ['modules'],
     'modules/cue_episode.py'),
    ('experiments/v2_agent/cue_transport.py', b'DTR-REQ-005 cue-v1 capture of the exact',
     b'DTR-REQ-005 cue-v1 Capture of the exact', ['modules'], 'modules/cue_transport.py'),
    ('experiments/v2_agent/cue_terminal.py', b'DTR-REQ-005 cue-v1 terminal phase:', b'DTR-REQ-005 cue-v1 Terminal phase:',
     ['modules'], 'modules/cue_terminal.py'),
    ('experiments/v2_agent/cue_admission.py', b"'cue-v1' frozen admission:", b"'cue-v1' Frozen admission:",
     ['modules'], 'modules/cue_admission.py'),
    ('experiments/v2_agent/cue_runner.py', b"'cue-v1' queue skeleton:", b"'cue-v1' Queue skeleton:", ['modules'],
     'modules/cue_runner.py'),
    ('experiments/v2_agent/exit_capture.py', b'DTR-REQ-005 all-exit diagnostic', b'DTR-REQ-005 All-exit diagnostic',
     ['accepted_sources', 'modules'], 'modules/exit_capture.py'),
    ('experiments/v2_agent/request_receipt.py', b'DTR-REQ-005 pre-dispatch request receipts',
     b'DTR-REQ-005 Pre-dispatch request receipts', ['accepted_sources', 'modules'], 'modules/request_receipt.py'),
    ('experiments/v2_agent/trajectory_triples.py', b'DTR-REQ-005 retrospective adapter',
     b'DTR-REQ-005 Retrospective adapter', ['accepted_sources', 'modules'], 'modules/trajectory_triples.py'),
    ('experiments/v2_agent/cue_cohort.py', b'DTR-REQ-005 cohort registry', b'DTR-REQ-005 Cohort registry',
     ['accepted_sources', 'modules'], 'modules/cue_cohort.py'),
    ('experiments/v2_agent/cue_detector.py', b'(P0) recovery-cue detector', b'(P0) Recovery-cue detector',
     ['accepted_sources', 'modules'], 'modules/cue_detector.py'),
    ('experiments/v2_agent/workspace_capture.py', b'DTR-REQ-002 workspace-capture binding',
     b'DTR-REQ-002 Workspace-capture binding', ['accepted_sources', 'modules'], 'modules/workspace_capture.py'),
    # the exact cue text
    ('experiments/v2_agent/cue_detector.py', b'feedback repeatedly.', b'feedback repeatedlY.',
     ['accepted_sources', 'cue', 'modules'], 'cue/sha256'),
    # the detector definitions
    ('experiments/v2_agent/cue_detector.py', b'not proven unchanged state', b'not proven unchanged statE',
     ['accepted_sources', 'detector', 'modules'], 'detector/trigger_note'),
    # the visible-evidence coding guide
    ('docs/req005_visible_evidence_guide_20260923.md', b'visible-evidence coding guide',
     b'visible-evidence Coding guide', ['accepted_sources', 'coding_guide'], 'coding_guide/sha256'),
    # the 12-assignment plan
    ('experiments/v2_agent/cue_cohort.py', b'nothing else about the episode changes',
     b'nothing else about the episode changeS', ['accepted_sources', 'modules', 'plan'], 'plan/plan_sha256'),
    # image pin (frame), model pin (conversion), amendment, base spec, YAML, yaml-v1 binding, evaluator-bearing frame
    ('results/v2_agent/pilot_frame_20260922.json',
     b'"instance_image": "sha256:d461c7c6e50916d9837e81604d8e79efca06af9c063f5477b0086102a96b50cf",',
     b'"instance_image": "sha256:e461c7c6e50916d9837e81604d8e79efca06af9c063f5477b0086102a96b50cf",', ['pins'],
     'pins/images/psf__requests-1142'),
    ('results/v2_agent/coder_conversion_20260922.json', b'87a3665ca3247c54', b'97a3665ca3247c54', ['pins'],
     'pins/models/small/gguf_sha256'),
    ('configs/v2_fixed_backend_development_pilot_yaml_v1_20260922.json', b'"stage": "DEVELOPMENT"',
     b'"stage": "DEVELOPMENt"', ['pins'],
     'pins/pin_sources/configs/v2_fixed_backend_development_pilot_yaml_v1_20260922.json'),
    ('results/v2_agent/pilot_20260922_yaml_v1/cohort_binding.json', b'"cohort": "yaml-v1"', b'"cohort": "yaml-v2"',
     ['pins'], 'pins/pin_sources/results/v2_agent/pilot_20260922_yaml_v1/cohort_binding.json'),
    (MSWEA_SRC + '/config/default.yaml', b'You are a helpful assistant that can interact with a computer.',
     b'You are a helpful assistant that can interact with a computeR.', ['pins', 'runtime'],
     'runtime/mini_swe_agent_sources/config/default.yaml'),
    ('experiments/v2_agent/pilot_cohort.py', b'Explicit, disjoint development cohorts',
     b'explicit, disjoint development cohorts', ['accepted_sources', 'pins'], 'pins/frozen_reference/pilot_cohort.py'),
    ('experiments/v2_agent/pilot_report.py', b'Finite descriptive DEV report', b'finite descriptive DEV report',
     ['accepted_sources', 'pins'], 'pins/frozen_reference/pilot_report.py'),
    ('experiments/v2_agent/pilot_grade.py', b'DTR-REQ-002 pilot grading', b'DTR-REQ-002 Pilot grading',
     ['accepted_sources', 'pins'], 'pins/frozen_reference/pilot_grade.py'),
    # settings (H/temperature/max_tokens/context/attempts/cap) and deadlines
    ('configs/v2_fixed_backend_development_pilot_20260922.json', b'"context_per_slot": 16384',
     b'"context_per_slot": 16385', ['pins', 'settings'], 'settings/context_per_slot'),
    ('experiments/v2_agent/pilot_episode.py', b'24, 1800, 1536, 60, 2', b'24, 1800, 1537, 60, 2',
     ['accepted_sources', 'modules', 'pins', 'settings'], 'settings/max_tokens'),
    ('experiments/v2_agent/pilot_runner.py', b'CHILD_CLEANUP_GRACE, SERVER_CLEANUP_RESERVE = 120, 90',
     b'CHILD_CLEANUP_GRACE, SERVER_CLEANUP_RESERVE = 120, 91', ['accepted_sources', 'deadlines', 'pins'],
     'deadlines/server_cleanup_reserve_s'),
    # the pinned runtime the transport runs on
    (MSWEA_SRC + '/models/litellm_textbased_model.py', b'import LitellmModel, LitellmModelConfig',
     b'import LitellmModel, LitellmModelConfiG', ['runtime'],
     'runtime/mini_swe_agent_sources/models/litellm_textbased_model.py'),
    (SITE + '/litellm-1.102.0.dist-info/RECORD', b'../../../bin/lite,', b'../../../bin/litE,', ['runtime'],
     'runtime/sdk_distributions/litellm/record_sha256'),
]


@pytest.mark.parametrize('rel,old,new,classes,path', ONE_BYTE_CASES,
                         ids=['%s:%s' % (case[0].rsplit('/', 1)[-1], case[4]) for case in ONE_BYTE_CASES])
def test_a_one_byte_change_in_each_bound_source_class_refuses_admission(root, rel, old, new, classes, path):
    layout = A.Layout(root)
    launch_and_hold(layout)
    assert A.validate_queue(layout)['binding_status'] == 'frozen; every bound input unchanged'
    change_one_byte(root / rel, old, new)
    with pytest.raises(A.AdmissionRefused) as exc:
        A.validate_queue(layout)
    assert exc.value.changed_classes == classes
    assert path in exc.value.changed
    assert exc.value.reasons[0] == 'changed bound input classes: ' + ', '.join(classes)
    with pytest.raises(A.AdmissionRefused):
        run_queue(never_called, layout=layout)


def test_the_cue_plan_and_settings_changes_also_name_the_violated_frozen_choice(root):
    layout = A.Layout(root)
    change_one_byte(root / 'experiments/v2_agent/cue_detector.py', b'feedback repeatedly.', b'feedback repeatedlY.')
    change_one_byte(root / 'experiments/v2_agent/cue_cohort.py', b'nothing else about the episode changes',
                    b'nothing else about the episode changeS')
    change_one_byte(root / 'experiments/v2_agent/pilot_episode.py', b'24, 1800, 1536, 60, 2', b'24, 1800, 1537, 60, 2')
    problems = A.compute_binding(layout)[1]
    assert any(p.startswith('cue: text sha256 ') and p.endswith(
        '(290 bytes) is not the accepted 290-byte cue 80d52625bd593cd6fecafeb06daca898792979592272d9fadcf0ddd04bd39d9e')
        for p in problems)
    assert any(p.startswith('plan: plan_sha256 ') and p.endswith(
        'is not the accepted 12-assignment frame dc687c8413d5aa8f81cb498b22cc5fac5f4fcf2535bf0c66aea8db2fb882c1ae')
        for p in problems)
    assert 'settings: max_tokens is 1537, not the frozen 1536' in problems
    assert 'pins: frozen reference pilot_episode.py differs from results/v2_agent/pilot_20260922_yaml_v1/' \
           'cohort_binding.json' in problems
    # and a launch is refused before anything is created
    with pytest.raises(A.AdmissionRefused):
        run_queue(never_called, layout=layout)
    assert not layout.out.exists()


def test_the_frozen_binding_file_is_write_once_and_self_verifying(root):
    layout = A.Layout(root)
    launch_and_hold(layout)
    frozen = json.loads(layout.binding_path.read_text())
    frozen['settings']['max_tokens'] = 2048
    layout.binding_path.write_text(json.dumps(frozen, indent=1, sort_keys=True) + '\n')
    with pytest.raises(A.AdmissionRefused) as exc:
        A.validate_queue(layout)
    assert exc.value.reasons == ['cue_binding.json does not match its own binding_sha256 (edited)']


# ------------------------------------------------------------------ resume after a changed input

def test_resume_refuses_after_a_changed_bound_input_and_dispatches_nothing(root):
    layout = A.Layout(root)
    calls = []
    first = run_queue(episode_returning(calls=calls), layout=layout, gate=hold_at(3))
    assert first['dispatched'] == [1, 2] and calls == [1, 2]
    ledger_before = layout.ledger_path.read_bytes()
    entries_before = sorted(p.name for p in layout.out.iterdir())
    change_one_byte(root / 'docs/req005_visible_evidence_guide_20260923.md', b'visible-evidence coding guide',
                    b'visible-evidence Coding guide')
    with pytest.raises(A.AdmissionRefused) as exc:
        run_queue(episode_returning(calls=calls), layout=layout)
    assert exc.value.changed == [
        'accepted_sources/pins/docs/req005_visible_evidence_guide_20260923.md/current_sha256', 'coding_guide/sha256']
    assert calls == [1, 2]
    assert layout.ledger_path.read_bytes() == ledger_before
    assert sorted(p.name for p in layout.out.iterdir()) == entries_before
    # restoring the exact bytes restores admission; the resume continues at position 3, never repeating 1 or 2
    change_one_byte(root / 'docs/req005_visible_evidence_guide_20260923.md', b'visible-evidence Coding guide',
                    b'visible-evidence coding guide')
    second = run_queue(episode_returning(calls=calls), layout=layout, gate=hold_at(5))
    assert second['dispatched'] == [3, 4] and calls == [1, 2, 3, 4]


def test_a_bound_input_changed_mid_session_stops_before_the_next_dispatch(root):
    layout = A.Layout(root)
    calls = []

    def episode(row, context):
        calls.append(row['position'])
        if row['position'] == 2:
            change_one_byte(root / 'docs/req005_visible_evidence_guide_20260923.md',
                            b'visible-evidence coding guide', b'visible-evidence Coding guide')
        return dict(physical_requests=3, storage_integrity='resolved', exit_status='Submitted')
    status = run_queue(episode, layout=layout)
    assert calls == [1, 2]
    assert status['stop']['code'] == 'bound_input_changed'
    assert status['stop']['kind'] == 'admission'
    assert status['stop']['next_position'] == 3
    with pytest.raises(A.AdmissionRefused) as exc:
        A.validate_queue(layout)
    assert exc.value.changed_classes == ['accepted_sources', 'coding_guide']


def test_the_running_runner_must_be_the_bound_runner_bytes(root):
    layout = A.Layout(root)
    change_one_byte(root / 'experiments/v2_agent/cue_runner.py', b"'cue-v1' queue skeleton:",
                    b"'cue-v1' Queue skeleton:")
    with pytest.raises(A.AdmissionRefused) as exc:
        run_queue(never_called, layout=layout)
    assert exc.value.reasons == ['running cue_runner.py differs from the bound source bytes']
    assert not layout.out.exists()


def test_the_runner_refuses_to_launch_unless_validation_passes(root):
    layout = A.Layout(root)
    (root / 'experiments/v2_agent/cue_terminal.py').unlink()
    with pytest.raises(A.AdmissionRefused) as exc:
        run_queue(never_called, layout=layout)
    assert exc.value.reasons == ['launch refused: modules: bound input missing: experiments/v2_agent/cue_terminal.py']
    assert not layout.out.exists()


# ------------------------------------------------------------------ 12 assignments / 576 requests across resumes

def test_the_576_request_cap_holds_across_two_simulated_resumes(root):
    layout = A.Layout(root)
    seen = []

    def episode(row, context):
        seen.append((row['position'], context['session'], context['counted_physical_requests_before'],
                     context['assignment_request_limit']))
        budget = context['budget']
        for _ in range(48):
            budget.consume()
        with pytest.raises(A.RequestCapReached):
            budget.consume()                 # the 49th physical request is refused before any dispatch
        return dict(physical_requests=48, storage_integrity='resolved', exit_status='LimitsExceeded')
    launch = run_queue(episode, layout=layout, gate=hold_at(5))
    resume_1 = run_queue(episode, layout=layout, gate=hold_at(9))
    resume_2 = run_queue(episode, layout=layout)
    assert seen == [(1, 1, 0, 48), (2, 1, 48, 48), (3, 1, 96, 48), (4, 1, 144, 48),
                    (5, 2, 192, 48), (6, 2, 240, 48), (7, 2, 288, 48), (8, 2, 336, 48),
                    (9, 3, 384, 48), (10, 3, 432, 48), (11, 3, 480, 48), (12, 3, 528, 48)]
    assert [(s['session'], s['dispatched'], s['counted_physical_requests'], s['complete'])
            for s in (launch, resume_1, resume_2)] == [(1, [1, 2, 3, 4], 192, False), (2, [5, 6, 7, 8], 384, False),
                                                       (3, [9, 10, 11, 12], 576, True)]
    report = A.validate_queue(layout)
    assert (report['counted_physical_requests'], report['request_capacity_remaining'], report['complete'],
            report['sessions']) == (576, 0, True, 3)
    with pytest.raises(A.AdmissionRefused) as exc:
        run_queue(episode, layout=layout)
    assert exc.value.reasons == ['all 12 frozen assignments were dispatched; no repeat, replacement or extension']
    assert len(seen) == 12


def test_an_unknown_request_count_keeps_its_48_reservation_across_a_resume(root):
    layout = A.Layout(root)
    seen = []

    def episode(row, context):
        seen.append((row['position'], context['counted_physical_requests_before']))
        return dict(physical_requests=None if row['position'] == 1 else 5, storage_integrity='resolved')
    first = run_queue(episode, layout=layout)
    assert first['stop']['code'] == 'request_accounting_unresolved'
    assert first['counted_physical_requests'] == 48
    A.record_reconciliation(layout, 'integrity-1', 'fixture: receipts reconciled; the count stays unknown (48 held)')
    run_queue(episode, layout=layout, gate=hold_at(4))
    assert seen == [(1, 0), (2, 48), (3, 53)]
    assert A.validate_queue(layout)['counted_physical_requests'] == 58


def test_the_assignment_budget_is_the_smaller_of_48_and_the_cohort_remainder():
    budget = A.AssignmentRequestBudget('psf__requests-1142__small__cue-v1__baseline', counted_before=560)
    assert (budget.limit, budget.remaining) == (16, 16)
    assert [budget.consume() for _ in range(16)] == list(range(1, 17))
    with pytest.raises(A.RequestCapReached):
        budget.consume()
    assert (budget.consumed, budget.refused) == (16, 1)


# ------------------------------------------------------------------ no duplicate, replacement, extension or outcome stop

@pytest.fixture
def two_done(root):
    layout = A.Layout(root)
    run_queue(episode_returning(requests=5), layout=layout, gate=hold_at(3))
    forge(layout, event='session_start', session=2, kind='resume', counted_physical_requests_before=10,
          episode_function='fixture:forged')
    return layout


def _start(position, assignment_id, suffix='abcdef'):
    return dict(event='assignment_start', session=2, position=position, assignment_id=assignment_id,
                run_id='%s__run-20260923T000000Z-%s' % (assignment_id, suffix), request_reservation=48,
                counted_physical_requests_before=10)


@pytest.mark.parametrize('record,message', [
    (_start(2, 'psf__requests-1142__small__cue-v1__cue'),
     'assignment 2 was already dispatched (no duplicate or repeat)'),
    (_start(3, 'psf__requests-1142__large__cue-v1__baseline'),
     "assignment id 'psf__requests-1142__large__cue-v1__baseline' is not the frozen assignment "
     "'psf__requests-1142__large__cue-v1__cue' (no replacement)"),
    (_start(4, 'psf__requests-1142__large__cue-v1__baseline'),
     'assignment 4 dispatched out of the frozen order (next is 3)'),
    (_start(13, 'sympy__sympy-11618__large__cue-v1__baseline'),
     'position 13 is outside the frozen 1..12 frame (no extension)'),
    (dict(event='queue_stop', session=2, stop_id='stop-10', code='no_submission_yet', kind='outcome',
          reason='fixture: an outcome-driven stop', outcome_driven=True, next_position=3, affected=[],
          remaining=[], assignment_states=[], counted_physical_requests=10),
     "stop code 'no_submission_yet' is not a predeclared stop"),
])
def test_duplicate_replacement_extension_and_outcome_stops_are_refused(two_done, record, message):
    forge(two_done, **record)
    with pytest.raises(A.LedgerRefused) as exc:
        A.validate_queue(two_done)
    assert exc.value.reasons == ['ledger seq 10 (%s): %s' % (record['event'], message)]


def test_a_record_of_another_cohort_is_refused(two_done):
    forge(two_done, cohort='yaml-v1', **_start(3, 'psf__requests-1142__large__cue-v1__cue'))
    with pytest.raises(A.LedgerRefused) as exc:
        A.validate_queue(two_done)
    assert exc.value.reasons == ['ledger seq 10 (assignment_start): record belongs to another cohort or binding; '
                                 'one cohort only']


def test_a_recorded_dispatch_while_an_integrity_issue_is_open_is_refused(root):
    layout = A.Layout(root)
    run_queue(episode_returning(storage_integrity='unresolved'), layout=layout)
    forge(layout, event='session_start', session=2, kind='resume', counted_physical_requests_before=7,
          episode_function='fixture:forged')
    forge(layout, event='assignment_start', session=2, position=2, assignment_id='psf__requests-1142__small__cue-v1__cue',
          run_id='psf__requests-1142__small__cue-v1__cue__run-20260923T000000Z-abcdef', request_reservation=48,
          counted_physical_requests_before=7)
    with pytest.raises(A.LedgerRefused) as exc:
        A.validate_queue(layout)
    assert exc.value.reasons == ["ledger seq 8 (assignment_start): dispatch while integrity issues are unresolved: "
                                 "['integrity-1']"]


def test_a_second_runner_is_refused_while_a_session_holds_the_ledger(root):
    layout = A.Layout(root)
    launch_and_hold(layout)
    held = A.resume_session(layout, episode_function='fixture:held')
    try:
        with pytest.raises(A.AdmissionRefused) as exc:
            run_queue(never_called, layout=layout)
        assert exc.value.reasons == ['another cue-v1 runner holds the ledger lock']
        assert A.validate_queue(layout)['ledger_locked'] is True
    finally:
        held.close()


STATES_AFTER_TWO = ([dict(position=1, assignment_id=ASSIGNMENT_IDS[0], state='terminal', counted_requests=5),
                     dict(position=2, assignment_id=ASSIGNMENT_IDS[1], state='terminal', counted_requests=5)]
                    + [dict(position=p, assignment_id=ASSIGNMENT_IDS[p - 1], state='unstarted', counted_requests=0)
                       for p in range(3, 13)])


@pytest.mark.parametrize('first_remaining,admitted', [(3, True), (4, False)])
def test_a_stop_record_must_preserve_every_remaining_assignment_state(two_done, first_remaining, admitted):
    remaining = [dict(position=p, assignment_id=ASSIGNMENT_IDS[p - 1], state='unstarted')
                 for p in range(first_remaining, 13)]
    forge(two_done, event='queue_stop', session=2, stop_id='stop-10', code='host_gate', kind='host_gate',
          reason='fixture: host window closed', outcome_driven=False, next_position=3, affected=[],
          remaining=remaining, assignment_states=STATES_AFTER_TWO, counted_physical_requests=10)
    if admitted:
        assert A.validate_queue(two_done)['next_position'] == 3
    else:
        with pytest.raises(A.LedgerRefused) as exc:
            A.validate_queue(two_done)
        assert exc.value.reasons == ['ledger seq 10 (queue_stop): the stop record does not preserve the current '
                                     'assignment states exactly']


def test_a_count_above_48_cannot_be_recorded(two_done):
    forge(two_done, **_start(3, 'psf__requests-1142__large__cue-v1__cue'))
    forge(two_done, event='assignment_terminal', session=2, position=3,
          assignment_id='psf__requests-1142__large__cue-v1__cue',
          run_id='psf__requests-1142__large__cue-v1__cue__run-20260923T000000Z-abcdef',
          physical_requests_reported=49, physical_requests_reported_raw=None, budget_consumed=0, counted_requests=49,
          request_accounting='reported', storage_integrity='resolved', storage_integrity_detail=None,
          exit_status='Submitted')
    with pytest.raises(A.LedgerRefused) as exc:
        A.validate_queue(two_done)
    assert exc.value.reasons == ['ledger seq 11 (assignment_terminal): counted_requests 49 outside 0..48']


def test_an_edited_removed_or_torn_ledger_record_is_refused(root):
    layout = A.Layout(root)
    run_queue(episode_returning(requests=5), layout=layout, gate=hold_at(3))
    original = layout.ledger_path.read_bytes()
    lines = original.split(b'\n')[:-1]
    layout.ledger_path.write_bytes(b'\n'.join(lines[:3] + lines[4:]) + b'\n')        # one record removed
    with pytest.raises(A.LedgerRefused) as exc:
        A.validate_queue(layout)
    assert exc.value.reasons == ['ledger seq 5 (assignment_start): sequence number is not 4']
    layout.ledger_path.write_bytes(original.replace(b'"exit_status":"Submitted"', b'"exit_status":"SubmitteD"', 1))
    with pytest.raises(A.LedgerRefused) as exc:
        A.validate_queue(layout)
    assert exc.value.reasons == ['ledger seq 5 (assignment_start): hash chain broken (a record was removed, '
                                 'reordered or edited)']
    layout.ledger_path.write_bytes(original[:-1])
    with pytest.raises(A.LedgerRefused) as exc:
        A.validate_queue(layout)
    assert exc.value.reasons == ['ledger has a torn final record; preserve it with repair_torn_tail(layout, note) '
                                 'before any resume']


def test_outcomes_never_change_dispatch(root):
    layout = A.Layout(root)
    statuses = ['Submitted', 'LimitsExceeded', 'ContextWindowExceededError', 'FormatError', 'Submitted',
                'EpisodeDeadline', 'SubmissionCaptureFailed', 'Submitted', 'LimitsExceeded', 'FormatError',
                'Submitted', 'ContextWindowExceededError']
    calls = []

    def episode(row, context):
        calls.append(row['position'])
        return dict(physical_requests=row['position'], storage_integrity='resolved',
                    exit_status=statuses[row['position'] - 1])
    status = run_queue(episode, layout=layout)
    assert calls == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    assert status['stop'] is None and status['complete'] is True
    assert status['counted_physical_requests'] == 78
    terminals = [e for e in ledger_events(layout) if e['event'] == 'assignment_terminal']
    assert [e['exit_status'] for e in terminals] == statuses
    assert [e['assignment_id'] for e in terminals] == ASSIGNMENT_IDS


# ------------------------------------------------------------------ legacy results and reports are never runtime state

def test_a_legacy_result_directory_is_refused_as_runtime_state(root):
    layout = A.Layout(root)
    for legacy in (root / 'results/v2_agent/pilot_20260922_yaml_v1', REPO / 'results/v2_agent/pilot_20260922'):
        with pytest.raises(A.AdmissionRefused) as exc:
            A.validate_queue(layout, out=legacy)
        assert exc.value.reasons == ['%s is a legacy result directory; only %s is admitted' % (legacy.name, NAMESPACE)]
    launch_and_hold(layout)
    legacy_run = layout.out / 'sympy__sympy-11618__large__pilot-cp2-wc2-yaml-v1__20260922T074338Z-1b5364'
    legacy_run.mkdir()
    (legacy_run / 'episode.json').write_text('{"configuration_binding": "yaml-v1", "exit_status": "Submitted"}\n')
    with pytest.raises(A.AdmissionRefused) as exc:
        A.validate_queue(layout)
    assert exc.value.reasons == ['legacy result directory sympy__sympy-11618__large__pilot-cp2-wc2-yaml-v1__'
                                 '20260922T074338Z-1b5364 cannot be cue-v1 runtime state']
    shutil.rmtree(legacy_run)
    (layout.out / 'pilot_20260922_yaml_v1').symlink_to(root / 'results/v2_agent/pilot_20260922_yaml_v1')
    with pytest.raises(A.AdmissionRefused) as exc:
        A.validate_queue(layout)
    assert exc.value.reasons == ['symlink pilot_20260922_yaml_v1: runtime state must be regular files/directories '
                                 'created by the cue-v1 runner']


def test_a_report_or_projection_file_is_refused_as_runtime_state(root):
    layout = A.Layout(root)
    # a namespace that holds only an all-unstarted report was not created by a launch and is not admitted
    layout.out.mkdir(parents=True)
    report = json.dumps(dict(cohort='cue-v1', terminal=0, episodes=[dict(state='unstarted')] * 12)) + '\n'
    (layout.out / 'report_block1.json').write_text(report)
    with pytest.raises(A.AdmissionRefused) as exc:
        A.validate_queue(layout)
    assert exc.value.reasons == [
        'results/v2_agent/pilot_20260923_cue_v1 exists without its write-once cue_binding.json: not created by a '
        'complete live launch', 'report/projection file report_block1.json cannot be runtime state']
    with pytest.raises(A.AdmissionRefused):
        run_queue(never_called, layout=layout)
    shutil.rmtree(layout.out)
    launch_and_hold(layout)
    for name in ('report_block1.json', 'psf__requests-1142__small__cue-v1__baseline__c1a1.request.json'):
        (layout.out / name).write_text(report)
        with pytest.raises(A.AdmissionRefused) as exc:
            A.validate_queue(layout)
        assert exc.value.reasons == ['report/projection file %s cannot be runtime state' % name]
        (layout.out / name).unlink()
    # a report substituted for the ledger (even in canonical JSON form) is not a ledger record
    layout.ledger_path.write_text(json.dumps(json.loads(report), sort_keys=True, separators=(',', ':')) + '\n')
    with pytest.raises(A.LedgerRefused) as exc:
        A.validate_queue(layout)
    assert exc.value.reasons == ['ledger seq None (None): unknown event; a report or projection is not a runtime '
                                 'ledger record']


# ------------------------------------------------------------------ the predeclared infrastructure stop

REMAINING_AFTER_3 = [dict(position=p, assignment_id=ASSIGNMENT_IDS[p - 1], state='unstarted') for p in range(4, 13)]


def test_the_infrastructure_stop_preserves_the_affected_and_remaining_assignment_states(root):
    layout = A.Layout(root)
    calls = []

    def episode(row, context):
        calls.append(row['position'])
        if row['position'] == 3:
            return dict(physical_requests=7, storage_integrity='unresolved', exit_status='Submitted',
                        storage_integrity_detail='fixture: durable pre-dispatch write failed; request not sent')
        return dict(physical_requests=7, storage_integrity='resolved', exit_status='Submitted')
    status = run_queue(episode, layout=layout)
    assert calls == [1, 2, 3]
    stop = status['stop']
    assert {k: stop[k] for k in ('code', 'kind', 'outcome_driven', 'next_position', 'reason',
                                 'counted_physical_requests')} == dict(
        code='storage_integrity_unresolved', kind='infrastructure', outcome_driven=False, next_position=4,
        reason='storage integrity unresolved after assignment 3', counted_physical_requests=21)
    assert stop['affected'] == [dict(position=3, assignment_id='psf__requests-1142__large__cue-v1__cue',
                                     state='terminal_integrity_unresolved')]
    assert stop['remaining'] == [
        dict(position=4, assignment_id='psf__requests-1142__large__cue-v1__baseline', state='unstarted'),
        dict(position=5, assignment_id='scikit-learn__scikit-learn-10297__small__cue-v1__cue', state='unstarted'),
        dict(position=6, assignment_id='scikit-learn__scikit-learn-10297__small__cue-v1__baseline', state='unstarted'),
        dict(position=7, assignment_id='scikit-learn__scikit-learn-10297__large__cue-v1__baseline', state='unstarted'),
        dict(position=8, assignment_id='scikit-learn__scikit-learn-10297__large__cue-v1__cue', state='unstarted'),
        dict(position=9, assignment_id='sympy__sympy-11618__small__cue-v1__baseline', state='unstarted'),
        dict(position=10, assignment_id='sympy__sympy-11618__small__cue-v1__cue', state='unstarted'),
        dict(position=11, assignment_id='sympy__sympy-11618__large__cue-v1__cue', state='unstarted'),
        dict(position=12, assignment_id='sympy__sympy-11618__large__cue-v1__baseline', state='unstarted'),
    ]
    assert [(r['position'], r['state'], r['counted_requests']) for r in stop['assignment_states']] == [
        (1, 'terminal', 7), (2, 'terminal', 7), (3, 'terminal_integrity_unresolved', 7), (4, 'unstarted', 0),
        (5, 'unstarted', 0), (6, 'unstarted', 0), (7, 'unstarted', 0), (8, 'unstarted', 0), (9, 'unstarted', 0),
        (10, 'unstarted', 0), (11, 'unstarted', 0), (12, 'unstarted', 0)]
    # the stop is durable in the ledger exactly as returned
    assert [e for e in ledger_events(layout) if e['event'] == 'queue_stop'] == [stop]
    report = A.validate_queue(layout)
    assert report['blocking'] == [dict(id='integrity-3', position=3, reason='storage/receipt/accounting integrity '
                                                                             'unresolved for this assignment')]
    with pytest.raises(A.AdmissionRefused) as exc:
        run_queue(episode, layout=layout)
    assert exc.value.reasons == ['dispatch refused while integrity is unresolved: integrity-3 (storage/receipt/'
                                 'accounting integrity unresolved for this assignment)']
    assert calls == [1, 2, 3]
    A.record_reconciliation(layout, 'integrity-3', 'fixture: storage checked; the affected receipt hole is kept')
    final = run_queue(episode, layout=layout)
    assert calls == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]      # assignment 3 is never re-dispatched
    assert [(r['position'], r['state']) for r in final['assignments']][:4] == [
        (1, 'terminal'), (2, 'terminal'), (3, 'terminal_integrity_unresolved'), (4, 'terminal')]
    assert final['complete'] is True and final['blocking'] == []


def test_a_storage_preflight_failure_stops_before_dispatch_and_touches_no_assignment(root):
    layout = A.Layout(root)
    calls = []
    status = run_queue(episode_returning(calls=calls), layout=layout,
                          storage_check=lambda row: 'fixture: free space below reserve + 6 GiB'
                          if row['position'] == 5 else None)
    assert calls == [1, 2, 3, 4]
    stop = status['stop']
    assert (stop['stop_id'], stop['code'], stop['kind'], stop['affected'], stop['next_position']) == (
        'stop-11', 'storage_preflight_unresolved', 'infrastructure', [], 5)
    assert stop['remaining'] == [dict(position=p, assignment_id=ASSIGNMENT_IDS[p - 1], state='unstarted')
                                 for p in (5, 6, 7, 8, 9, 10, 11, 12)]
    assert A.validate_queue(layout)['blocking'] == [dict(
        id='stop-11', position=None, reason='storage_preflight_unresolved: fixture: free space below reserve + 6 GiB')]
    with pytest.raises(A.AdmissionRefused):
        run_queue(episode_returning(calls=calls), layout=layout)
    A.record_reconciliation(layout, 'stop-11', 'fixture: space freed and rechecked by the operator')
    run_queue(episode_returning(calls=calls), layout=layout, gate=hold_at(6))
    assert calls == [1, 2, 3, 4, 5]


def test_an_episode_exception_is_recorded_reserves_48_and_stops_the_queue(root):
    layout = A.Layout(root)

    def episode(row, context):
        if row['position'] == 2:
            raise RuntimeError('fixture: transport raised before its terminal record')
        return dict(physical_requests=7, storage_integrity='resolved')
    status = run_queue(episode, layout=layout)
    assert (status['stop']['code'], status['stop']['affected']) == (
        'episode_function_error', [dict(position=2, assignment_id='psf__requests-1142__small__cue-v1__cue',
                                        state='episode_error')])
    assert status['counted_physical_requests'] == 55
    errors = [e for e in ledger_events(layout) if e['event'] == 'assignment_error']
    assert [(e['position'], e['error_class'], e['detail'], e['counted_requests']) for e in errors] == [
        (2, 'RuntimeError', 'fixture: transport raised before its terminal record', 48)]
    assert [i['id'] for i in A.validate_queue(layout)['blocking']] == ['integrity-2']


def test_an_interrupted_assignment_needs_reconciliation_and_is_never_redispatched(root, monkeypatch):
    layout = A.Layout(root)
    calls = []
    real_append = A.LedgerSession.append

    def killed_before_the_end_record(self, event, **fields):
        if event == 'assignment_terminal' and fields.get('position') == 3:
            raise KeyboardInterrupt('fixture: runner killed between the episode and its end record')
        return real_append(self, event, **fields)
    monkeypatch.setattr(A.LedgerSession, 'append', killed_before_the_end_record)
    with pytest.raises(KeyboardInterrupt):
        run_queue(episode_returning(calls=calls), layout=layout)
    monkeypatch.setattr(A.LedgerSession, 'append', real_append)
    report = A.validate_queue(layout)
    assert [(r['position'], r['state'], r['counted_requests']) for r in report['assignments']][:4] == [
        (1, 'terminal', 7), (2, 'terminal', 7), (3, 'interrupted', 48), (4, 'unstarted', 0)]
    assert [i['id'] for i in report['blocking']] == ['interrupted-3']
    with pytest.raises(A.AdmissionRefused):
        run_queue(episode_returning(calls=calls), layout=layout)
    A.record_reconciliation(layout, 'interrupted-3', 'fixture: runner kill confirmed; assignment kept incomplete')
    run_queue(episode_returning(calls=calls), layout=layout, gate=hold_at(5))
    assert calls == [1, 2, 3, 4]
    rows = A.validate_queue(layout)['assignments']
    assert [(r['position'], r['state'], r['counted_requests']) for r in rows][:5] == [
        (1, 'terminal', 7), (2, 'terminal', 7), (3, 'interrupted_reconciled', 48), (4, 'terminal', 7),
        (5, 'unstarted', 0)]


def test_a_reconciliation_must_name_an_open_issue(root):
    layout = A.Layout(root)
    run_queue(episode_returning(), layout=layout, gate=hold_at(2))
    with pytest.raises(A.AdmissionRefused) as exc:
        A.record_reconciliation(layout, 'integrity-1', 'fixture: nothing to reconcile')
    assert exc.value.reasons == ["'integrity-1' is not an open issue ([])"]


def test_the_free_space_preflight_needs_6_gib_above_a_supplied_host_reserve(tmp_path):
    usage = collections.namedtuple('usage', 'total used free')
    reserve = 10 * 1024 ** 3
    assert A.free_space_check(tmp_path, host_reserve_bytes=reserve,
                              disk_usage=lambda p: usage(0, 0, 17179869184)) is None
    assert A.free_space_check(tmp_path, host_reserve_bytes=reserve,
                              disk_usage=lambda p: usage(0, 0, 17179869183)) == (
        'free space 17179869183 bytes is below the host reserve 10737418240 + 6 GiB start margin (17179869184 bytes)')
    with pytest.raises(ValueError):
        A.free_space_check(tmp_path, host_reserve_bytes=None)


# ------------------------------------------------------------------ dry run and the held live launch

def test_dry_run_lists_the_exact_twelve_assignments_in_frozen_order(root, capsys):
    layout = A.Layout(root)
    assert CR.main(['--dry-run', '--root', str(root)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == ('cue-v1 dry run: 12 frozen assignments in position order (pair order B,C,C,B,B,C); nothing '
                        'is dispatched, created or written')
    assert lines[1:13] == [row.format('unstarted') for row in DRY_RUN_ROWS]
    assert lines[13] == 'namespace: results/v2_agent/pilot_20260923_cue_v1 (absent; created only by a live launch)'
    assert not layout.out.exists()
    # the copied script run as a program lists the same rows from its own tree, still creating nothing
    proc = subprocess.run([sys.executable, str(root / 'experiments/v2_agent/cue_runner.py'), '--dry-run'],
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.splitlines()[1:13] == [row.format('unstarted') for row in DRY_RUN_ROWS]
    assert not layout.out.exists()
    # after a partial session the listing shows the recorded states in the same frozen order
    run_queue(episode_returning(), layout=layout, gate=hold_at(3))
    assert CR.main(['--dry-run', '--root', str(root)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[1:13] == ([row.format('terminal') for row in DRY_RUN_ROWS[:2]]
                           + [row.format('unstarted') for row in DRY_RUN_ROWS[2:]])


def test_the_command_line_refuses_a_live_launch_and_starts_nothing(root, capsys):
    assert CR.main(['--root', str(root)]) == 2
    assert capsys.readouterr().err.startswith('live launch refused: the cue-v1 live release is held by the lead')
    assert not A.Layout(root).out.exists()


def test_validation_and_dry_run_never_create_this_checkout_s_cue_v1_namespace(capsys):
    namespace = REPO / NAMESPACE
    existed = namespace.exists()
    CR.main(['--dry-run'])
    CR.main(['--validate'])
    capsys.readouterr()
    assert namespace.exists() == existed


# ------------------------------------------------------------------ repairs after the adversarial review

AUDIT = 'docs/audits/req005_component_review_20260923.json'
LANDMARKS = 'docs/req005_fixture_landmarks_20260923.json'


@pytest.mark.parametrize('rel,old,new,accepted,source', [
    ('experiments/v2_agent/exit_capture.py', b'DTR-REQ-005 all-exit diagnostic', b'DTR-REQ-005 All-exit diagnostic',
     '6e4f265759b3dbe22ba161382412cc9cd076dce822d76f4ac844fde987f699b9', AUDIT + ' source_sha256'),
    ('experiments/v2_agent/request_receipt.py', b'DTR-REQ-005 pre-dispatch request receipts',
     b'DTR-REQ-005 Pre-dispatch request receipts', 'a751a43c6a2ef431c7119129308b740caed376536e6b6edcc7568368fde5cc46',
     AUDIT + ' source_sha256'),
    ('experiments/v2_agent/pilot_grade.py', b'DTR-REQ-002 pilot grading', b'DTR-REQ-002 Pilot grading',
     '0c2a5a5da861a42fd1dbc79c01ff4b031bff8d0a3cbcda8b90e869161f70e7f1',
     AUDIT + ' preservation.frozen_runtime_sha256'),
    ('experiments/v2_agent/pilot_report.py', b'Finite descriptive DEV report', b'finite descriptive DEV report',
     '1afa9002344557f4fd518044313f2fd277528a06a5fef667966175804711e10f',
     LANDMARKS + ' source_pins.frozen_yaml_v1_sources_unchanged'),
    ('docs/req005_visible_evidence_guide_20260923.md', b'visible-evidence coding guide',
     b'visible-evidence Coding guide', 'ea7f67d4c1a0cf93d271f30fb1c48d027d8f4f97c28eaed0451c4a554c142625',
     AUDIT + ' source_sha256'),
    ('experiments/v2_agent/workspace_capture.py', b'DTR-REQ-002 workspace-capture binding',
     b'DTR-REQ-002 Workspace-capture binding', '96f194f4854ab75e6235bec7b8289a41928b036cd7bddbe66eff4afbdbd5302f',
     LANDMARKS + ' source_pins.new_modules'),
])
def test_a_pre_launch_edit_of_an_accepted_source_refuses_the_launch(root, rel, old, new, accepted, source):
    layout = A.Layout(root)
    change_one_byte(root / rel, old, new)
    calls = []
    with pytest.raises(A.AdmissionRefused) as exc:
        run_queue(episode_returning(calls=calls), layout=layout)
    prefix, suffix = 'launch refused: accepted: %s is ' % rel, ', not the accepted %s (%s)' % (accepted, source)
    assert [r for r in exc.value.reasons if r.startswith(prefix) and r.endswith(suffix)], exc.value.reasons
    assert calls == [] and not layout.out.exists() and not (root / A.LAUNCH_MARKER_REL).exists()


def test_the_traced_sdk_files_pth_and_site_hooks_are_bound(root):
    layout = A.Layout(root)
    binding, problems = A.compute_binding(layout)
    assert problems == []
    assert sorted(binding['runtime']['sdk_traced_files']) == sorted(
        rel for rels in A.TRACED_SDK_FILES.values() for rel in rels)
    assert binding['runtime']['sdk_traced_files']['httpx/_transports/default.py'] == \
        hashlib.sha256((REPO / SITE / 'httpx/_transports/default.py').read_bytes()).hexdigest()
    assert list(binding['runtime']['pth_files']) == ['__editable__.mini_swe_agent-2.4.6.pth']
    assert binding['runtime']['editable_mini_swe_agent'] == \
        'work/upstream/mini-swe-agent-04d809ceab9df28f9adaed044884180159172930/src'
    launch_and_hold(layout)
    site = root / SITE
    transport = site / 'httpx/_transports/default.py'
    transport.write_bytes(transport.read_bytes() + b'\n# injected: rewrite request.content before send\n')
    (site / 'sitecustomize.py').write_text('import os\n')
    (site / '__editable__.mini_swe_agent-2.4.6.pth').write_text('/some/other/mini-swe-agent/src\n')
    problems = A.compute_binding(layout)[1]
    assert problems == [
        'runtime: installed httpx/_transports/default.py does not match its httpx RECORD digest',
        'runtime: sitecustomize.py in the pinned interpreter would run code at every start',
        'runtime: __editable__.mini_swe_agent-2.4.6.pth does not point at the bound mini-swe-agent source '
        'work/upstream/mini-swe-agent-04d809ceab9df28f9adaed044884180159172930/src']
    with pytest.raises(A.AdmissionRefused) as exc:
        A.validate_queue(layout)
    assert exc.value.changed_classes == ['runtime']


def test_a_symlinked_directory_inside_the_pinned_harness_is_refused(root):
    src = root / MSWEA_SRC
    shutil.move(str(src / 'models'), str(root.parent / 'models_elsewhere'))
    (src / 'models').symlink_to(root.parent / 'models_elsewhere')
    assert 'runtime: %s/models is a symlink' % MSWEA_SRC in A.compute_binding(A.Layout(root))[1]


def test_the_enforcing_modules_state_the_contract_bounds_and_the_driver_passes_no_override(root):
    binding = A.compute_binding(A.Layout(root))[0]
    assert binding['enforced_bounds']['cue_terminal'] == dict(
        CLEANUP_RESERVE_S=90, DIAGNOSTIC_MAX_S=30, EXISTING_CLEANUP_ALLOWANCE_S=120, PHASE_WINDOW_S=120,
        SUBPROCESS_MAX_S=60)
    assert binding['enforced_bounds']['cue_transport'] == dict(
        BODY_CAP_BYTES=8388608, COHORT_RAW_RESERVATION_BYTES=4831838208, PUBLIC_HEAD_BYTES=32768,
        PUBLIC_RECORD_CAP_BYTES=131072, PUBLIC_TAIL_BYTES=32768, PUBLIC_WHOLE_MAX_BYTES=65536,
        SENDS_PER_QUERY_ATTEMPT=1, START_FREE_ABOVE_RESERVE_BYTES=6442450944)
    assert binding['enforced_bounds']['cue_episode_capture_keywords'] == [['budget', 'host_reserve_bytes']]
    change_one_byte(root / 'experiments/v2_agent/cue_terminal.py', b'DIAGNOSTIC_MAX_S = 30\n',
                    b'DIAGNOSTIC_MAX_S = 38\n')
    change_one_byte(root / 'experiments/v2_agent/cue_transport.py', b'BODY_CAP_BYTES = 8 * MiB',
                    b'BODY_CAP_BYTES = 9 * MiB')
    episode = root / 'experiments/v2_agent/cue_episode.py'
    text = episode.read_text()
    assert text.count('host_reserve_bytes=args.host_reserve_bytes)') == 1
    episode.write_text(text.replace('host_reserve_bytes=args.host_reserve_bytes)',
                                    'host_reserve_bytes=args.host_reserve_bytes, accounting_fixture=True)'))
    problems = A.compute_binding(A.Layout(root))[1]
    assert problems == [
        'enforced: cue_terminal.DIAGNOSTIC_MAX_S is 38, the contract says diagnostic_max_s=30',
        'enforced: cue_transport.BODY_CAP_BYTES is 9437184, the contract says request_body_cap_bytes=8388608',
        'enforced: cue_transport.COHORT_RAW_RESERVATION_BYTES is 5435817984, the contract says '
        'cohort_raw_body_reservation_bytes=4831838208',
        'enforced: cue_episode passes accounting_fixture to CueTransportCapture; the frozen values are the only '
        'admitted ones']


def test_a_ledger_truncated_at_a_record_boundary_is_refused_not_resumed(root):
    layout = A.Layout(root)
    calls = []
    status = run_queue(episode_returning(calls=calls), layout=layout,
                       storage_check=lambda row: 'fixture: low space' if row['position'] == 3 else None)
    assert status['stop']['code'] == 'storage_preflight_unresolved'
    lines = layout.ledger_path.read_bytes().split(b'\n')[:-1]
    assert [json.loads(line)['event'] for line in lines[-2:]] == ['queue_stop', 'session_end']
    layout.ledger_path.write_bytes(b'\n'.join(lines[:-2]) + b'\n')      # the unresolved stop disappears
    expected = ['queue_ledger.head.json records seq 8, the ledger ends at seq 6: records were removed from the '
                'ledger (truncated) or the head was edited; nothing is dispatched']
    with pytest.raises(A.AdmissionRefused) as exc:
        A.validate_queue(layout)
    assert exc.value.reasons == expected
    with pytest.raises(A.AdmissionRefused) as exc:
        run_queue(episode_returning(calls=calls), layout=layout)
    assert exc.value.reasons == expected and calls == [1, 2]


def test_a_crash_between_the_ledger_append_and_the_head_update_is_still_admitted(root):
    layout = A.Layout(root)
    run_queue(episode_returning(), layout=layout, gate=hold_at(2))
    events = ledger_events(layout)
    lines = layout.ledger_path.read_bytes().split(b'\n')[:-1]
    head = layout.out / 'queue_ledger.head.json'
    head.write_text(json.dumps(dict(cohort='cue-v1', binding_sha256=events[0]['binding_sha256'], seq=len(lines) - 1,
                                    last_sha256=hashlib.sha256(lines[-2] + b'\n').hexdigest(),
                                    utc='2026-09-23T00:00:00Z'), sort_keys=True) + '\n')
    assert A.validate_queue(layout)['next_position'] == 2


def test_deleting_the_namespace_never_opens_a_second_launch(root):
    layout = A.Layout(root)
    calls = []
    run_queue(episode_returning(requests=48, calls=calls), layout=layout, gate=hold_at(9))
    assert json.loads((root / A.LAUNCH_MARKER_REL).read_text())['namespace'] == NAMESPACE
    shutil.rmtree(layout.out)
    expected = ['the cue-v1 cohort was already launched (work/req005_cue_v1_launch_marker.json exists) but '
                'results/v2_agent/pilot_20260923_cue_v1 is missing; the frozen cohort is never launched a second time']
    with pytest.raises(A.AdmissionRefused) as exc:
        run_queue(episode_returning(requests=48, calls=calls), layout=layout)
    assert exc.value.reasons == expected and calls == [1, 2, 3, 4, 5, 6, 7, 8]
    assert not layout.out.exists()


def test_a_run_directory_error_can_be_reconciled_and_the_queue_resumes(root, monkeypatch):
    layout = A.Layout(root)
    real_mkdir = Path.mkdir

    def mkdir(self, *a, **kw):
        if self.parent == layout.out and '__small__cue-v1__cue__run-' in self.name and 'psf' in self.name:
            raise OSError(13, 'fixture: permission denied')
        return real_mkdir(self, *a, **kw)
    monkeypatch.setattr(Path, 'mkdir', mkdir)
    calls = []
    status = run_queue(episode_returning(calls=calls), layout=layout)
    monkeypatch.setattr(Path, 'mkdir', real_mkdir)
    assert (status['stop']['code'], status['stop']['affected'], calls) == (
        'run_directory_error', [dict(position=2, assignment_id=ASSIGNMENT_IDS[1], state='episode_error')], [1])
    error = [e for e in ledger_events(layout) if e['event'] == 'assignment_error'][0]
    assert (error['run_dir_created'], error['error_class']) == (False, 'PermissionError')   # errno 13
    assert A.validate_queue(layout)['blocking'] == [dict(
        id='integrity-2', position=2, reason='storage/receipt/accounting integrity unresolved for this assignment')]
    A.record_reconciliation(layout, 'integrity-2', 'fixture: run directory could not be created; nothing ran')
    assert run_queue(episode_returning(calls=calls), layout=layout, gate=hold_at(4))['dispatched'] == [3]


def test_surrogate_escaped_text_is_recorded_escaped_and_never_breaks_the_ledger(root):
    layout = A.Layout(root)

    def episode(row, context):
        if row['position'] == 1:
            return dict(physical_requests=7, storage_integrity='unresolved', exit_status='Submitted\udcff',
                        storage_integrity_detail='write failed \udc80')
        raise AssertionError('not reached')
    status = run_queue(episode, layout=layout)
    terminal = [e for e in ledger_events(layout) if e['event'] == 'assignment_terminal'][0]
    assert (terminal['exit_status'], terminal['storage_integrity_detail']) == ('Submitted\\udcff',
                                                                              'write failed \\udc80')
    assert status['stop']['code'] == 'storage_integrity_unresolved'
    A.record_reconciliation(layout, 'integrity-1', 'fixture: reconciled')

    def raising(row, context):
        raise RuntimeError('boom \udcfe')
    status = run_queue(raising, layout=layout)
    error = [e for e in ledger_events(layout) if e['event'] == 'assignment_error'][0]
    assert (error['detail'], status['stop']['code']) == ('boom \\udcfe', 'episode_function_error')


def test_only_the_bound_episode_function_is_dispatched_outside_a_fixture_copy(root, monkeypatch):
    layout = A.Layout(root)
    with pytest.raises(A.AdmissionRefused) as exc:
        CR.run_queue(episode_returning(), layout=layout)            # no fixture flag
    assert exc.value.reasons == ['the episode function is not the bound cue_episode.run_assignment of '
                                 'experiments/v2_agent']
    assert not layout.out.exists()
    with pytest.raises(A.AdmissionRefused) as exc:
        CR.episode_function_label(never_called, A.Layout(REPO), {'modules': {}}, fixture=True)
    assert exc.value.reasons == ['a fixture episode function is never dispatched from the real checkout']
    # the bound function: its module must be the layout's cue_episode.py at its bound bytes
    import types
    module = types.ModuleType('cue_episode_bound_fixture')
    module.__file__ = str(root / 'experiments/v2_agent/cue_episode.py')

    def run_assignment(row, context):
        raise AssertionError('not dispatched here')
    run_assignment.__module__ = module.__name__
    monkeypatch.setitem(sys.modules, module.__name__, module)
    binding = A.compute_binding(layout)[0]
    assert CR.episode_function_label(run_assignment, layout, binding, fixture=False) == 'cue_episode.run_assignment'
    binding['modules']['cue_episode.py'] = '0' * 64
    with pytest.raises(A.AdmissionRefused):
        CR.episode_function_label(run_assignment, layout, binding, fixture=False)


def test_a_report_or_symlink_written_mid_session_stops_before_the_next_dispatch(root):
    layout = A.Layout(root)
    calls = []

    def episode(row, context):
        calls.append(row['position'])
        if row['position'] == 1:
            (layout.out / 'report_block1.json').write_text('{"cohort":"cue-v1"}\n')
        return dict(physical_requests=3, storage_integrity='resolved', exit_status='Submitted')
    status = run_queue(episode, layout=layout)
    assert calls == [1]
    assert (status['stop']['code'], status['stop']['kind'], status['stop']['next_position']) == (
        'namespace_contents_invalid', 'admission', 2)
    assert status['stop']['reason'] == ('namespace contents changed during the session: report/projection file '
                                        'report_block1.json cannot be runtime state')


def test_a_run_directory_may_hold_only_cue_v1_episode_output(root):
    layout = A.Layout(root)
    run_queue(episode_returning(), layout=layout, gate=hold_at(2))
    run_dir = next(p for p in layout.out.iterdir() if p.is_dir())
    (run_dir / 'episode.json').write_text('{}\n')
    (run_dir / 'receipts').mkdir()
    (run_dir / 'receipts' / 'call001_attempt01.request.json').write_text('{}\n')
    assert A._check_run_dir(run_dir) == []
    (run_dir / 'legacy').symlink_to(root / 'results/v2_agent/pilot_20260922_yaml_v1')
    (run_dir / 'report_block1.json').write_text('{}\n')
    with pytest.raises(A.AdmissionRefused) as exc:
        A.validate_queue(layout)
    assert exc.value.reasons == ['symlink %s/legacy inside a run directory' % run_dir.name,
                                 'file %s/report_block1.json is not cue-v1 episode output' % run_dir.name]


def test_a_torn_final_record_is_preserved_repaired_and_the_queue_resumes(root):
    layout = A.Layout(root)
    calls = []
    run_queue(episode_returning(calls=calls), layout=layout, gate=hold_at(3))
    layout.ledger_path.write_bytes(layout.ledger_path.read_bytes() + b'{"event":"assignment_st')
    with pytest.raises(A.AdmissionRefused):
        A.validate_queue(layout)
    event = A.repair_torn_tail(layout, 'fixture: the append failed mid-record; the runner stopped')
    assert (event['event'], event['seq'], event['fragment_file'], event['fragment_bytes'],
            event['fragment_sha256']) == (
        'torn_tail_repair', 9, 'queue_ledger.torn-9.bin', 23,
        '9956bd29ad5e0ce538bf8d3f2d47d4f4af3f1a395457f6a84ac9d85e009d39dd')
    assert (layout.out / 'queue_ledger.torn-9.bin').read_bytes() == b'{"event":"assignment_st'
    assert A.validate_queue(layout)['next_position'] == 3
    assert run_queue(episode_returning(calls=calls), layout=layout, gate=hold_at(4))['dispatched'] == [3]


def test_a_corrupted_receipt_of_a_clean_terminal_assignment_refuses_the_resume(root):
    import cue_transport as CT
    layout = A.Layout(root)
    identity = dict(model=dict(alias='a', model_sha256='1' * 64), decoding=dict(temperature=0.0, max_tokens=1536),
                    server=dict(endpoint='http://127.0.0.1:8291/v1'), tokenizer=dict(source='fixture'))

    def episode(row, context):
        store = CT.BoundedReceiptStore(root / A.PRIVATE_RECEIPTS_REL / context['run_id'],
                                       context['run_dir'] / 'receipts', cohort='cue-v1', identity=identity,
                                       run_id=context['run_id'], home='', root=root)
        store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=b'{"messages":[]}')
        store.record_outcome(logical_call_id=1, physical_attempt_id=1, ok=True)
        return dict(physical_requests=1, storage_integrity='resolved', exit_status='Submitted')
    run_queue(episode, layout=layout, gate=hold_at(2))
    assert A.validate_queue(layout)['next_position'] == 2
    outcome = next(layout.out.glob('*/receipts/call001_attempt01.outcome.json'))
    outcome.write_bytes(outcome.read_bytes().replace(b'"outcome": "ok"', b'"outcome": "OK"'))
    with pytest.raises(A.AdmissionRefused) as exc:
        A.validate_queue(layout)
    assert exc.value.reasons[0].startswith('the receipt set of clean terminal assignment 1 (%s) is no longer complete'
                                           % outcome.parent.parent.name)
    assert 'published projection digest mismatch' in exc.value.reasons[0]


def test_an_episode_is_admitted_only_as_the_open_assignment_of_a_runner_session(root):
    layout = A.Layout(root)
    seen = []

    def args(row, context, **override):
        values = dict(run_id=context['run_id'], position=row['position'], instance_id=row['instance_id'],
                      backend=row['backend'], arm=row['arm'], port=row['port'], alias=row['model_alias'],
                      expected_image=row['image_id'])
        values.update(override)
        return values

    def episode(row, context):
        binding, admitted_row, report = A.admit_episode(layout, **args(row, context))
        seen.append((admitted_row['assignment_id'], report['ledger_locked']))
        for override, message in (
                (dict(arm='cue'), "episode arguments differ from the frozen assignment 1: arm='cue' (frozen "
                                  "'baseline')"),
                (dict(port=8293), 'episode arguments differ from the frozen assignment 1: port=8293 (frozen 8291)'),
                (dict(run_id=context['run_id'] + 'x'), "run %r is not the open assignment start of the current runner "
                                                       "session" % (context['run_id'] + 'x'))):
            with pytest.raises(A.AdmissionRefused) as exc:
                A.admit_episode(layout, **args(row, context, **override))
            assert exc.value.reasons == [message]
        (context['run_dir'] / 'episode.json').write_text('{}\n')
        with pytest.raises(A.AdmissionRefused) as exc:                  # the run directory must still be empty
            A.admit_episode(layout, **args(row, context))
        assert exc.value.reasons == ['run directory %s must exist, be a real directory and be empty'
                                     % context['run_id']]
        return dict(physical_requests=0, storage_integrity='resolved', exit_status='Submitted')
    with pytest.raises(A.AdmissionRefused) as exc:
        A.admit_episode(layout, run_id='x', position=1, instance_id='psf__requests-1142', backend='small',
                        arm='baseline', port=8291, alias='a', expected_image='i')
    assert exc.value.reasons == ['results/v2_agent/pilot_20260923_cue_v1 has not been launched: an episode runs '
                                 'only inside a runner session']
    run_queue(episode, layout=layout, gate=hold_at(2))
    assert seen == [(ASSIGNMENT_IDS[0], True)]
    with pytest.raises(A.AdmissionRefused) as exc:                      # no session holds the ledger any more
        A.admit_episode(layout, run_id='x', position=1, instance_id='psf__requests-1142', backend='small',
                        arm='baseline', port=8291, alias='a', expected_image='i')
    assert exc.value.reasons == ['no runner session holds the ledger lock: an episode runs only inside one']
