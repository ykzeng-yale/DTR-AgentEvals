"""Fixtures for the DTR-REQ-005 'cue-v1' cohort registry (no model, server, container or network call, and
no directory is created).

The 12 rows below are written out BY HAND, one tuple per line, from the lead's frame: lexicographic by task,
then small before large, with the within-pair order B,C,C,B,B,C (B = baseline first, C = cue first). Nothing
here calls the module's ordering logic to build the expectation, so a wrong order in cue_cohort.py cannot be
cancelled by the same wrong order here.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/v2_agent'))
import cue_cohort as CC  # noqa: E402

# (position, instance_id, backend, arm, pair_index, pair_order, within_pair_position)
FROZEN_12 = [
    (1, 'psf__requests-1142', 'small', 'baseline', 1, 'B', 1),
    (2, 'psf__requests-1142', 'small', 'cue', 1, 'B', 2),
    (3, 'psf__requests-1142', 'large', 'cue', 2, 'C', 1),
    (4, 'psf__requests-1142', 'large', 'baseline', 2, 'C', 2),
    (5, 'scikit-learn__scikit-learn-10297', 'small', 'cue', 3, 'C', 1),
    (6, 'scikit-learn__scikit-learn-10297', 'small', 'baseline', 3, 'C', 2),
    (7, 'scikit-learn__scikit-learn-10297', 'large', 'baseline', 4, 'B', 1),
    (8, 'scikit-learn__scikit-learn-10297', 'large', 'cue', 4, 'B', 2),
    (9, 'sympy__sympy-11618', 'small', 'baseline', 5, 'B', 1),
    (10, 'sympy__sympy-11618', 'small', 'cue', 5, 'B', 2),
    (11, 'sympy__sympy-11618', 'large', 'cue', 6, 'C', 1),
    (12, 'sympy__sympy-11618', 'large', 'baseline', 6, 'C', 2),
]


def test_the_twelve_assignments_are_in_the_lead_s_frozen_order_with_their_arm_labels():
    rows = CC.assignments()
    assert len(rows) == 12
    assert [(r['position'], r['instance_id'], r['backend'], r['arm'], r['pair_index'], r['pair_order'],
             r['within_pair_position']) for r in rows] == FROZEN_12


def test_each_row_carries_its_detector_mode_and_a_unique_assignment_id():
    rows = CC.assignments()
    assert [r['detector_mode'] for r in rows] == [
        'observe', 'live', 'live', 'observe', 'live', 'observe',
        'observe', 'live', 'observe', 'live', 'live', 'observe']
    assert [r['assignment_id'] for r in rows] == [
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
    assert len({r['assignment_id'] for r in rows}) == 12


def test_the_frame_is_balanced_exactly_as_the_lead_specified():
    rows = CC.assignments()
    assert CC.PAIR_ORDER == ('B', 'C', 'C', 'B', 'B', 'C')
    assert sum(1 for r in rows if r['arm'] == 'baseline') == 6
    assert sum(1 for r in rows if r['arm'] == 'cue') == 6
    assert sum(1 for r in rows if r['within_pair_position'] == 1 and r['arm'] == 'baseline') == 3
    assert sum(1 for r in rows if r['within_pair_position'] == 1 and r['arm'] == 'cue') == 3
    # the order is not identical to backend: small goes first in one B pair and one C pair per position
    assert sorted((r['backend'], r['pair_order']) for r in rows if r['within_pair_position'] == 1) == [
        ('large', 'B'), ('large', 'C'), ('large', 'C'), ('small', 'B'), ('small', 'B'), ('small', 'C')]
    # one baseline and one cue episode per task/backend, and exactly six pairs
    seen = {}
    for r in rows:
        seen.setdefault((r['instance_id'], r['backend']), []).append(r['arm'])
    assert len(seen) == 6
    assert all(sorted(arms) == ['baseline', 'cue'] for arms in seen.values())


def test_the_task_list_is_lexicographic_and_holds_only_the_three_exposed_diagnostic_tasks():
    assert CC.TASKS == ('psf__requests-1142', 'scikit-learn__scikit-learn-10297', 'sympy__sympy-11618')
    assert list(CC.TASKS) == sorted(CC.TASKS)
    assert CC.BACKENDS == ('small', 'large')


def test_the_cohort_names_its_own_output_directory_and_creates_nothing():
    assert CC.COHORT == 'cue-v1'
    assert CC.output_dir_relative() == 'results/v2_agent/pilot_20260923_cue_v1'
    out = CC.cohort_output()
    assert out == ROOT / 'results/v2_agent/pilot_20260923_cue_v1'
    assert out.name == 'pilot_20260923_cue_v1'
    assert not out.exists()                     # the registry creates no directory and no episode record
    # the frozen yaml-v1 cohort is a different namespace and is untouched
    assert (ROOT / 'results/v2_agent/pilot_20260922_yaml_v1/cohort_binding.json').exists()


def test_the_declared_limits_are_the_lead_s_numbers():
    plan = CC.frozen_plan()
    assert plan['horizon_h'] == 24
    assert plan['attempts_per_call'] == 2
    assert plan['max_physical_requests'] == 576             # 12 x 24 x 2, hand-checked
    assert plan['n_assignments'] == 12
    assert 12 * 24 * 2 == plan['max_physical_requests']
    assert plan['cohort'] == 'cue-v1'
    assert plan['output_dir'] == 'results/v2_agent/pilot_20260923_cue_v1'
    assert plan['detector'] == 'repeated-action-cue-v1'
    assert plan['exit_capture_binding'] == 'xc1'
    assert plan['status'] == 'planned and held pending lead review; no episode has run'
    assert len(plan['assignments']) == 12
    assert len(plan['plan_sha256']) == 64
    assert json.loads(json.dumps(plan)) == plan


def test_the_plan_digest_is_over_the_plan_itself_and_moves_with_the_order(monkeypatch):
    import hashlib
    plan = CC.frozen_plan()
    payload = {k: v for k, v in plan.items() if k != 'plan_sha256'}
    independent = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'),
                                            ensure_ascii=False).encode()).hexdigest()
    assert plan['plan_sha256'] == independent
    monkeypatch.setattr(CC, 'PAIR_ORDER', ('C', 'B', 'C', 'B', 'B', 'C'))
    assert CC.frozen_plan()['plan_sha256'] != plan['plan_sha256']


def test_the_baseline_arm_is_declared_as_instrumentation_only():
    plan = CC.frozen_plan()
    assert plan['arm_declarations']['baseline'] == (
        'instrumentation only: the detector runs silently and its would-trigger landmark is recorded; '
        'no cue is emitted and no model-visible message or endpoint byte changes')
    assert plan['arm_declarations']['cue'] == (
        'one fixed cue appended before the next normally budgeted model call after the first trigger; '
        'nothing else about the episode changes')
    assert 'held: no episode runs before the lead reviews this frozen list, the sources, the limits and ' \
           'the fixtures' in plan['notes']


@pytest.mark.parametrize('letter,expected', [('B', ('baseline', 'cue')), ('C', ('cue', 'baseline'))])
def test_the_within_pair_letter_decides_which_arm_runs_first(letter, expected):
    assert CC.arms_for_pair(letter) == expected


@pytest.mark.parametrize('letter', ['b', 'c', 'A', '', None, 1])
def test_an_unknown_within_pair_letter_is_refused(letter):
    with pytest.raises(ValueError):
        CC.arms_for_pair(letter)


def test_a_mismatched_pair_order_length_is_refused(monkeypatch):
    monkeypatch.setattr(CC, 'PAIR_ORDER', ('B', 'C'))
    with pytest.raises(ValueError):
        CC.assignments()


def test_this_registry_imports_no_frozen_execution_source():
    import ast
    tree = ast.parse((ROOT / 'experiments/v2_agent/cue_cohort.py').read_text())
    imported = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import)
                for alias in node.names}
    imported |= {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) and node.module}
    assert imported == {'__future__', 'hashlib', 'json', 'pathlib'}
    # and it registers only its own namespace, never a yaml-v1 output directory
    assert CC.COHORTS == {'cue-v1': 'pilot_20260923_cue_v1'}
