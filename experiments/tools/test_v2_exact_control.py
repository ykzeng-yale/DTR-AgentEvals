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
