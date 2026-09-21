"""Checks for DTR-REQ-003 slice 3 (experiments/v2_sim/repair_generator.py): two exact truth paths and controls."""
import json, sys
from fractions import Fraction as Fr
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import repair_generator as G  # noqa: E402


@pytest.fixture(scope='module')
def rep():
    return G.build()


def cell(rep, K, eff, fb):
    return next(c for c in rep['cells'] if (c['K'], c['action_effect'], c['feedback']) == (K, eff, fb))


def F(x):
    return Fr(x['exact'])


def test_two_truth_paths_agree_exactly_everywhere(rep):
    assert len(rep['cells']) == 12
    for c in rep['cells']:
        assert c['both_truth_paths_agree_exactly']
        assert all(r['paths_agree_exactly'] for r in c['policies'].values())


def test_dp_dominates_catalog_and_ordering(rep):
    for c in rep['cells']:
        assert c['dp_dominates_catalog']
        hist, prompt, fixed = F(c['best_observed_history_utility']), F(c['best_prompt_only_utility']), F(c['best_fixed']['utility'])
        assert hist >= prompt >= fixed


def test_negative_control_has_exactly_zero_advantage(rep):
    for K in (2, 4):
        for fb in ('informative', 'weak'):
            c = cell(rep, K, 'U_irrelevant_negative_control', fb)
            assert F(c['history_advantage_over_best_fixed']) == 0 and F(c['history_advantage_over_best_prompt_only']) == 0


def test_positive_control_orders_by_feedback_quality(rep):
    for K in (2, 4):
        inf, weak = cell(rep, K, 'crossing', 'informative'), cell(rep, K, 'crossing', 'weak')
        assert F(inf['history_advantage_over_best_prompt_only']) > F(weak['history_advantage_over_best_prompt_only']) > 0


def test_first_opportunity_occupancy_is_analytic(rep):
    # reach(1) = (1 - P0[S]) * (1 - FALSE_PASS[S]), mixed 1/2 : 1/2, for every policy (the first call is common)
    want = G.mix(lambda s: (1 - G.P0[s]) * (1 - G.FALSE_PASS[s]))
    for c in rep['cells']:
        for r in c['policies'].values():
            assert Fr(r['reach_opportunity'][0]) == want


def test_committed_output_matches_generator(rep):
    assert json.loads(G.OUT.read_text()) == json.loads(json.dumps(rep))
