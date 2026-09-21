"""Checks for experiments/v2_sim/branch_occupancy_sensitivity.py (lead decision 7e04762)."""
import json, sys
from fractions import Fraction as Fr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import branch_occupancy_sensitivity as O  # noqa: E402
import branch_module as B  # noqa: E402
import repair_generator as G  # noqa: E402


def test_expected_prefix_count_is_564_by_direct_formula():
    # independent of per_episode: E[N] = sum_S 165 * sum_A0 4 * (1 - P0A_new) * (1 - FALSE_PASS[S])
    alpha = Fr(940, 1969)
    en = sum(165 * 4 * alpha * (1 - B.P0A[s][a0]) * (1 - G.FALSE_PASS[s]) for s in (0, 1) for a0 in (0, 1))
    assert en == 564


def test_sensitivity_checks_and_probabilities():
    rep = O.build()
    for r in rep['rows']:
        assert r['totals_scale_by_alpha'] and r['ratios_unchanged'] and r['E_N_sensitivity'] == '564'
    for tab in rep['P0A_sensitivity'].values():
        assert all(0 <= Fr(v) <= 1 for v in tab.values())
    lp = rep['rows'][0]['log10_P_N0_and_P_N_le_200']
    assert lp['sensitivity'][0] > lp['baseline'][0] and lp['sensitivity'][1] > lp['baseline'][1]   # fewer prefixes


def test_baseline_p0a_restored_after_sensitivity():
    before = {s: dict(B.P0A[s]) for s in (0, 1)}
    O.build()
    assert {s: dict(B.P0A[s]) for s in (0, 1)} == before


def test_committed_output_matches_generator():
    assert json.loads(O.OUT.read_text()) == json.loads(json.dumps(O.build()))
