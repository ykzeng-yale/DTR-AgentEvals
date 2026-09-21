"""Checks for DTR-REQ-003 slice 4 (experiments/v2_sim/repair_logger.py): exact IPW, support status, invariance."""
import json, sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import repair_logger as L  # noqa: E402
import repair_generator as G  # noqa: E402


@pytest.fixture(scope='module')
def rep():
    return L.build()


def rows(rep):
    for c in rep['cells']:
        for p, pr in c['policies'].items():
            for l, r in pr['loggers'].items():
                yield c, p, l, r


def test_all_checks(rep):
    assert all(v for v in rep['checks'].values() if isinstance(v, bool))
    assert rep['checks']['supported_rows'] == 348 and rep['checks']['unsupported_rows'] == 120


def test_supported_loggers_recover_every_component_exactly(rep):
    for c, p, l, r in rows(rep):
        if l != 'zero_support_negative_control':
            assert r['status'] == dict(success='supported', utility='supported', cost='supported')
            assert r['ipw_success_equals_truth'] and r['ipw_cost_equals_truth'] and r['ipw_utility_equals_truth']


def test_cost_status_is_per_component_and_ipw_is_not_claimed(rep):
    for c, p, l, r in rows(rep):
        if r['status']['success'] == 'supported':
            continue
        final_only = max(r['unsupported_at_opportunities']) == c['K']
        assert r['status']['cost'].startswith('identified') is final_only
        assert not r['ipw_cost_equals_truth']      # plain IPW drops the unsupported branch either way


def test_truth_unchanged_by_logger_only_change():
    import inspect
    assert 'logger' not in inspect.signature(G.enumerate_value).parameters   # the target cannot see the logger
    other = lambda s, t, o: G.Fr(3, 10) if o == 'asr' else G.Fr(7, 10)          # a new supported logger
    for cfg in [(2, 'crossing', 'informative'), (4, 'no_crossing', 'weak')]:
        cell = G.Cell(*cfg)
        for pol in G.catalog(cell.K):
            for s in (0, 1):
                acc, unsup = L.logged_expectations(pol, cell, s, other)
                truth = G.enumerate_value(pol, cell, s)[0]
                assert not unsup and acc['ipw_success'] == truth['success'] and acc['ipw_cost'] == truth['cost']


def test_committed_output_matches_generator(rep):
    assert json.loads(L.OUT.read_text()) == json.loads(json.dumps(rep))
