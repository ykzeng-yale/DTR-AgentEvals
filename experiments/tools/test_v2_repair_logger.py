"""Checks for DTR-REQ-003 slice 4 v2 (experiments/v2_sim/repair_logger.py), corrected per lead review 935fabd."""
import hashlib, inspect, json, sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import repair_logger as L  # noqa: E402
import repair_generator as G  # noqa: E402

V1_SHA256 = '40f7e8d297b514ec005f2970e5df38bebf9454cc19e72d23d2132b3420de734c'


@pytest.fixture(scope='module')
def rep():
    return L.build()


def rows(rep):
    for c in rep['cells']:
        for p, pr in c['policies'].items():
            for l, r in pr['loggers'].items():
                yield c, p, l, r


def test_classifier_cases_independent_of_data():
    K = 4
    assert L.classify_cost([], K) == 'supported'
    assert L.classify_cost([K], K).startswith('identified')
    assert L.classify_cost([K, K], K).startswith('identified')
    for times in ([1, K], [1], [2], [1, 2, 3]):
        assert L.classify_cost(times, K).startswith('UNSUPPORTED'), times


def test_counts_match_lead_audit(rep):
    c = rep['checks']
    assert (c['supported_rows'], c['unsupported_rows'], c['final_only_rows']) == (348, 120, 12)
    assert all(v for v in c.values() if isinstance(v, bool))


def test_labels_agree_with_set_criterion_recomputed_here(rep):
    for c, p, l, r in rows(rep):
        times = set(r['unsupported_at_opportunities'])
        want = 'supported' if not times else 'identified' if times == {c['K']} else 'UNSUPPORTED'
        assert r['status']['cost'].startswith(want), (c['K'], p, l, sorted(times))


def test_supported_rows_exact_for_every_component(rep):
    for c, p, l, r in rows(rep):
        if r['status']['success'] == 'supported':
            assert r['ipw_success_equals_truth'] and r['ipw_cost_equals_truth'] and r['ipw_utility_equals_truth']
            assert r['per_decision_cost_equals_truth']


def test_final_only_rows_need_the_per_decision_estimator(rep):
    final_only = [r for c, p, l, r in rows(rep) if r['status']['cost'].startswith('identified')]
    assert len(final_only) == 12
    for r in final_only:
        assert r['per_decision_cost_equals_truth'] and not r['ipw_cost_equals_truth']


def test_truth_unchanged_by_logger_only_change():
    assert 'logger' not in inspect.signature(G.enumerate_value).parameters
    other = lambda s, t, o: G.Fr(3, 10) if o == 'asr' else G.Fr(7, 10)
    for cfg in [(2, 'crossing', 'informative'), (4, 'no_crossing', 'weak')]:
        cell = G.Cell(*cfg)
        for pol in G.catalog(cell.K):
            for s in (0, 1):
                acc, unsup = L.logged_expectations(pol, cell, s, other)
                truth = G.enumerate_value(pol, cell, s)[0]
                assert not unsup and acc['ipw_success'] == truth['success'] and acc['ipw_cost'] == truth['cost']
                assert L.per_decision_cost_expectation(pol, cell, s, other) == truth['cost']


def test_v1_output_preserved_byte_for_byte():
    assert hashlib.sha256(L.OUT_V1_PRESERVED.read_bytes()).hexdigest() == V1_SHA256


def test_committed_v2_output_matches_generator(rep):
    assert json.loads(L.OUT.read_text()) == json.loads(json.dumps(rep))
