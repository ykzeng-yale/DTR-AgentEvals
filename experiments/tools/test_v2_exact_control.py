"""Checks for DTR-REQ-003 slice 1 (experiments/v2_sim/exact_control.py): exact truth, two paths, logger invariance."""
import json, sys
from fractions import Fraction as Fr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import exact_control as X  # noqa: E402


def cell(rep, eta, q):
    return next(c for c in rep['cells'] if c['eta'] == eta and c['q'] == q)


def test_all_exact_checks_pass():
    rep = X.build()
    assert all(v for v in rep['checks'].values() if isinstance(v, bool))


def test_protocol_values_rederived():
    rep = X.build()
    assert cell(rep, '1/5', '0')['observe_F_utility_gain_over_const_0']['exact'] == '3/20'
    assert cell(rep, '1/5', '1/4')['observe_F_utility_gain_over_const_0']['exact'] == '1/20'
    for eta, q in [('0', '0'), ('0', '1/4'), ('0', '1/2'), ('1/5', '1/2')]:
        c = cell(rep, eta, q)
        assert c['observe_F_utility_gain_over_const_0']['exact'] == '-1/20'
        assert c['exact_adaptive_advantage']['exact'] == '0'
    for c in rep['cells']:
        for p in ('const_0', 'const_1'):
            assert c['policies'][p]['success']['exact'] == '1/2'


def test_truth_does_not_change_when_only_the_logger_changes(monkeypatch):
    base = {(c['eta'], c['q'], p): r['success']['exact'] for c in X.build()['cells'] for p, r in c['policies'].items()}
    monkeypatch.setattr(X, 'LOGGERS', {'other_supported': {0: Fr(3, 10), 1: Fr(9, 10)},
                                        'zero_support_negative_control': {0: Fr(1, 2), 1: Fr(1)},
                                        'state_dependent_floor_0.2': {0: Fr('0.2'), 1: Fr('0.8')}})
    rep = X.build()
    assert {(c['eta'], c['q'], p): r['success']['exact'] for c in rep['cells'] for p, r in c['policies'].items()} == base
    assert all(r['loggers']['other_supported']['ipw_equals_truth'] for c in rep['cells']
               for r in c['policies'].values() if 'loggers' in r)


def test_negative_controls_fail_exactly_where_expected():
    rep = X.build()
    for c in rep['cells']:
        informative_effect = c['action_effect_present'] and c['feedback_informative']
        for p, r in c['policies'].items():
            if 'loggers' not in r:
                continue
            zs = r['loggers']['zero_support_negative_control']
            needs_unsupported = p in ('const_0', 'observe_not_F')        # need A=0 at F=1, where P(A=0|F=1)=0
            assert zs['ipw_equals_truth'] is (not needs_unsupported)
            unw = r['loggers']['state_dependent_floor_0.2']
            if p in ('observe_F', 'observe_not_F'):
                # this logger matches these two policies with equal probability in both F states (.8/.8 or .2/.2),
                # so the unweighted mean happens to be unbiased for them here; not a general property
                assert unw['unweighted_equals_truth']
            else:
                assert unw['unweighted_equals_truth'] is (not informative_effect)


def test_committed_output_matches_generator():
    assert json.loads(X.OUT.read_text()) == json.loads(json.dumps(X.build()))


# ---- supplemental development output v1 (lead decision 54e1621) ----
SIX_CELL_SHA256 = '5efc714f8323acf7d65df60016ca086a5ae0a4dfeb43bbfe28acf9628df0afb6'


def test_six_cell_artifact_is_byte_identical():
    import hashlib
    assert hashlib.sha256(X.OUT.read_bytes()).hexdigest() == SIX_CELL_SHA256


def test_supplemental_cell_matches_lead_table_exactly():
    rep = X.build_supplemental()
    c = next(c for c in rep['cells'] if c['role'] == 'supplemental_cost_dominated')
    table = {'const_0': ('1/2', '0', '1/2'), 'const_1': ('1/2', '1/10', '2/5'), 'observe_F': ('27/50', '1/20', '49/100'),
             'observe_not_F': ('23/50', '1/20', '41/100'), 'oracle_U': ('7/10', '1/20', '13/20')}
    for p, (su, co, ut) in table.items():
        r = c['policies'][p]
        assert (r['success']['exact'], r['cost']['exact'], r['utility']['exact']) == (su, co, ut)
    assert c['observe_F_gain_over_const_0']['exact'] == '-1/100'          # policy-specific loss
    assert c['best_class_advantage_over_best_fixed']['exact'] == '0'      # best-class advantage, kept separate
    assert c['best_F_measurable']['policy'] == 'const_0'


def test_supplemental_checks_and_unsupported_status():
    rep = X.build_supplemental()
    assert all(v for v in rep['checks'].values() if isinstance(v, bool))
    assert rep['checks']['unsupported_rows_flagged'] == 14                # 7 cells x {const_0, observe_not_F}
    for c in rep['cells']:
        for p, r in c['policies'].items():
            if not r['learnable']:
                continue
            z = r['ipw']['zero_support_negative_control']
            assert (z['status'] == 'supported') is (p in ('const_1', 'observe_F'))
            if z['status'] == 'supported':
                assert all(z[k]['equals_truth'] for k in ('success', 'cost', 'utility'))


def test_supplemental_output_matches_generator():
    assert json.loads(X.OUT_SUPP.read_text()) == json.loads(json.dumps(X.build_supplemental()))
