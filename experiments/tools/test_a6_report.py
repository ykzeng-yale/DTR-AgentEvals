"""Controls for the source-bound A6 report: it must fail closed and keep its classes and targets apart."""
import copy, json, sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import a6_report as R  # noqa: E402


@pytest.fixture(scope='module')
def audits():
    return R.load_audits()


@pytest.fixture(scope='module')
def report(audits):
    return R.build(copy.deepcopy(audits))


def test_every_row_has_class_target_comparator_denominator_and_audit(report):
    for r in report['rows']:
        assert r['class'] in R.CLASSES
        for k in ('endpoint', 'target', 'comparator', 'denominator', 'status'):
            assert r[k]
        assert r['audit'] and all(a['abs_diff'] <= R.TOL for a in r['audit'])


def test_the_four_named_classes_are_all_present(report):
    present = {r['class'] for r in report['rows']}
    assert {'whole_policy', 'pooled_repair', 'realized_frame', 'selected_cohort'} <= present


def test_primary_target_is_open_and_not_substituted(report):
    assert report['primary_target']['estimate'] is None and report['primary_target']['interval'] is None
    assert not any('primary' in r['class'] for r in report['rows'])
    b2 = next(r for r in report['rows'] if r['id'] == 'P-B2-branch-minus-log')
    assert 'OPEN' in b2['status'] and 'not a consistent SE' in b2['uncertainty']['label']


def test_no_ceiling_or_power_reading_survives(report):
    for r in report['rows']:
        text = ' '.join(str(r[k]) for k in ('target', 'status')).lower()
        if 'ceiling' in text or 'oracle' in text:
            assert 'withdrawn' in text, r['id']
    assert any('power' in x for x in report['not_claimed'])


def test_perturbed_audit_value_fails_closed(audits):
    bad = copy.deepcopy(audits)
    bad['WN4']['stage_contrasts']['1']['effect'] += 1e-9
    with pytest.raises(R.AuditMismatch):
        R.build(bad)


def test_changed_pinned_input_hash_fails_closed(audits):
    bad = copy.deepcopy(audits)
    bad['CF']['inputs']['branch_episodes']['sha256'] = '0' * 64
    with pytest.raises(R.AuditMismatch):
        R.build(bad)


def test_missing_audit_fails_closed(tmp_path):
    with pytest.raises(R.AuditMismatch):
        R.load_audits(tmp_path)


def _numeric_leaves(obj, path=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _numeric_leaves(v, path + (k,))
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        yield path, obj


def test_every_corrected_json_number_is_reproduced(report):
    """why_null_corrected.json had no generator; each numeric leaf must appear among the report's reproduced values."""
    cor = json.loads((R.RES / 'analysis' / 'why_null_corrected.json').read_text())
    values = [v for r in report['rows'] for _, v in _numeric_leaves({'e': r['estimate'], 'u': r['uncertainty'] or {}})]
    covered = []
    for path, v in _numeric_leaves(cor):
        if path == ('stage_gradient_paired', 'sigmas'):          # withdrawn reading: 0.0937 / 0.0593
            s = next(r for r in report['rows'] if r['id'] == 'S-61-task-stage-gradient')
            assert round(s['estimate']['difference'] / s['uncertainty']['value'], 1) == v
        elif path == ('stage_gradient_paired', 'tasks') or path[-1] == 'n_tasks':
            assert v in (61, 91, 239, 330)
        else:                                                     # the file stores 4- or 6-decimal roundings
            assert any(v in (round(x, 4), round(x, 6)) for x in values), path
        covered.append(path)
    assert len(covered) == 21


def test_every_original_why_null_number_is_reproduced(report):
    old = json.loads((R.RES / 'analysis' / 'why_null.json').read_text())
    values = [v for r in report['rows'] for _, v in _numeric_leaves({'e': r['estimate'], 'u': r['uncertainty'] or {}})]
    skip = {('A_design', 'study_policy_value_se_approx'),                # a literal; listed as withdrawn
            ('B_metric', 'frozen_large_call_penalty'),                   # config value
            ('B_metric', 'large_calls_learned'), ('B_metric', 'large_calls_always_large'),   # per-episode forms below
            ('B_metric', 'flip_multiple_of_frozen'), ('A_design', 'confirm_episodes')}
    per_episode = {r['id']: r['estimate'] for r in report['rows'] if r['id'].startswith('W-calls-')}
    assert abs(per_episode['W-calls-learned']['large_calls'] / 660 - old['B_metric']['large_calls_learned']) < 1e-12
    assert abs(per_episode['W-calls-always_large']['large_calls'] / 660 - old['B_metric']['large_calls_always_large']) < 1e-12
    for path, v in _numeric_leaves(old):
        if path in skip or path[-1] == 'n':
            continue
        assert any(abs(x - v) < 1e-12 for x in values), path


def test_withdrawn_list_names_the_mislabelled_0199(report):
    w = next(x for x in report['withdrawn_interpretations'] if '.0199' in x['claim'])
    assert 'ALWAYS_SMALL' in w['replacement']
    small = next(r for r in report['rows'] if r['id'] == 'W-always_small-success')
    assert round(small['uncertainty']['value'], 4) == 0.0199


def test_branch_plan_redraw_matches_frozen_plan(report):
    p = report['branch_plan_reproduction']
    assert p['redrawn_equals_frozen_plan'] and p['plan_log_sha256_matches_current_log'] and p['n_plan_rows'] == 800


def test_rendered_markdown_is_generated_from_the_report(report):
    md = R.render_md(report)
    for r in report['rows']:
        assert '| %s |' % r['id'].replace('|', '\\|') in md
