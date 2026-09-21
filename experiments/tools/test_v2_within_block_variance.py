"""Checks for sampler.within_block_variance: formula, manifest guard, and exact unbiasedness for r = 2."""
import sys
from fractions import Fraction as Fr
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import repair_generator as G  # noqa: E402
import repair_logger as L  # noqa: E402
import sampler as S  # noqa: E402


def ep(t, j, u, s=0):
    return dict(task_id=t, replicate=j, stratum=s, utility=Fr(u), decisions=[], observations=[])


def test_formula_on_known_values():
    tasks = [('a', 0), ('b', 0)]
    eps = [ep('a', 0, 1), ep('a', 1, 0), ep('b', 0, 1), ep('b', 1, 1)]
    # s_a^2 = 1/2, s_b^2 = 0  ->  (1/2 + 0) / (r n^2) = (1/2) / (2 * 4) = 1/16
    assert S.within_block_variance(eps, lambda e: e['utility'], tasks, 2) == Fr(1, 16)


def test_requires_two_replicates_and_complete_manifest():
    with pytest.raises(ValueError):
        S.within_block_variance([ep('a', 0, 1)], lambda e: e['utility'], [('a', 0)], 1)
    with pytest.raises(S.ManifestError):
        S.within_block_variance([ep('a', 0, 1), ep('a', 0, 0)], lambda e: e['utility'], [('a', 0)], 2)


def test_exactly_unbiased_for_one_task_with_r_equal_2():
    # E over all pairs of independent logged episodes of (1/r) s^2 must equal Var(mean of the pair) = sigma^2 / 2 exactly
    cell = G.Cell(2, 'crossing', 'informative')
    pol = {p.name: p for p in G.catalog(2)}['history_large_after_exception']
    br = [(p, S.ipw_weight(e, pol) * e['utility'])
          for p, e in S.exhaustive(lambda d: S.run_episode(cell, 1, d, 'x', logger=L.LOGGERS['feedback_dependent_floor_0.2']))]
    m1 = sum(p * x for p, x in br); m2 = sum(p * x * x for p, x in br)
    expected_est = sum(p * q * S.within_block_variance([ep('t', 0, x, 1), ep('t', 1, y, 1)], lambda e: e['utility'], [('t', 1)], 2)
                       for p, x in br for q, y in br)
    assert expected_est == (m2 - m1 * m1) / 2
