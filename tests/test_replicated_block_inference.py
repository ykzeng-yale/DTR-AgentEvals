"""DTR-REQ-024 deterministic exact fixtures for experiments/v2_sim/replicated_block_inference.py (Codex lead request
docs/req024_replicated_inference_setup.md). These are finite algebra and implementation checks: no sampling, Monte
Carlo or coverage claim. Expected values are hand-derived literals or independent computations (scalar contrast
series, population moments, exhaustive enumeration, corner enumeration, central differences), never the module's own
formulas."""
import itertools
import math
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments/v2_sim'))
import replicated_block_inference as R  # noqa: E402

C = 'contract-v1'
PB = R.TWO_DECISION_HALF_LOGGER_SCORE_BOUNDS
FRESH, OFFLINE, CAL = (R.PRIMARY_CONTRASTS[k] for k in ('fresh_gain', 'offline_gain', 'gain_calibration_discrepancy'))


def blocks(rows, contract=C, prefix='b'):
    return [dict(block_id='%s%d' % (prefix, k), contract_id=contract, z=list(z)) for k, z in enumerate(rows)]


# A generic covariance-algebra fixture, not a valid primary OPE law (its offline means exceed 1): e (a period effect
# shared by all four coordinates) and f (a policy effect) are independent fair bits; O_H = 3e + f, O_P = 3e,
# F_H = e, F_P = e(1 - f). One block per equally likely point (e, f).
SHARED = [(0, 0, 0, 0), (1, 0, 0, 0), (3, 3, 1, 1), (4, 3, 1, 0)]


def test_full_covariance_recovers_shared_period_cancellation_and_scales_with_the_block_count():
    s = R.summarize_blocks(blocks(SHARED), R.PRIMARY_COORDS, contract_id=C, bounds=PB)
    assert s['B'] == 4 and s['mean'] == (2, F(3, 2), F(1, 2), F(1, 4))
    # hand: the scalar contrast series are fresh (0, 0, 0, 1), offline (0, 1, 0, 1), calibration (0, 1, 0, 0), with
    # population variances 3/16, 1/4, 3/16; S_B is 4/3 of the population value, so Var-hat(a'Zbar) = variance / 3
    got = {n: R.linear_estimate(s, a)['variance_of_estimate'] for n, a in R.PRIMARY_CONTRASTS.items()}
    assert got == {'fresh_gain': F(1, 16), 'offline_gain': F(1, 12), 'gain_calibration_discrepancy': F(1, 16)}
    # a sum of marginal variances misses the cancellation: population marginals are 5/2, 9/4, 1/4, 3/16 (hand)
    marginal = {'fresh_gain': (F(1, 4) + F(3, 16)) / 3, 'offline_gain': (F(5, 2) + F(9, 4)) / 3,
                'gain_calibration_discrepancy': (F(5, 2) + F(9, 4) + F(1, 4) + F(3, 16)) / 3}
    assert all(marginal[n] > 2 * got[n] for n in got)
    assert [s['covariance'][j][j] for j in range(4)] == [F(10, 3), 3, F(1, 3), F(1, 4)]
    assert s['covariance'][0][2] == s['covariance'][2][0] == 1           # hand: (7/4 - 2 * 1/2) * 4/3 offline/fresh
    assert all(s['covariance_of_mean'][i][j] * 4 == s['covariance'][i][j] for i in range(4) for j in range(4))
    # the same law observed twice (B = 8): S_B is 8/7 of the population value, so Var-hat = variance / 7
    s8 = R.summarize_blocks(blocks(SHARED * 2), R.PRIMARY_COORDS)
    assert R.linear_estimate(s8, FRESH)['variance_of_estimate'] == F(3, 112)
    assert s8['covariance_of_mean'][0][0] == F(5, 2) * F(8, 7) / 8


def test_two_block_enumeration_gives_an_unbiased_variance_estimate_of_the_mean():
    law = [((1, 0, 1, 0), F(1, 2)), ((0, 0, 0, 1), F(1, 3)), ((-2, 3, 1, 1), F(1, 6))]
    # hand: contrast values fresh (1, -1, 0), offline (1, 0, -5), calibration (0, 1, -5) under (1/2, 1/3, 1/6)
    truth_mean = {'fresh_gain': F(1, 6), 'offline_gain': F(-1, 3), 'gain_calibration_discrepancy': F(-1, 2)}
    truth_var = {'fresh_gain': F(29, 36), 'offline_gain': F(41, 9), 'gain_calibration_discrepancy': F(17, 4)}
    e_est, e_var = dict.fromkeys(truth_mean, F(0)), dict.fromkeys(truth_var, F(0))
    e_cov = [[F(0)] * 4 for _ in range(4)]
    for (z1, p1), (z2, p2) in itertools.product(law, repeat=2):     # all 9 ordered pairs, ties included
        s = R.summarize_blocks(blocks([z1, z2]), R.PRIMARY_COORDS, bounds=PB)
        for n, a in R.PRIMARY_CONTRASTS.items():
            lin = R.linear_estimate(s, a)
            e_est[n] += p1 * p2 * lin['estimate']
            e_var[n] += p1 * p2 * lin['variance_of_estimate']
        for i, j in itertools.product(range(4), repeat=2):
            e_cov[i][j] += p1 * p2 * s['covariance'][i][j]
    assert e_est == truth_mean
    assert e_var == {n: v / 2 for n, v in truth_var.items()}          # E[a'S_2 a / 2] = a'Sigma a / 2
    mu = [sum(p * z[i] for z, p in law) for i in range(4)]            # Sigma from population moments of the law
    assert e_cov == [[sum(p * z[i] * z[j] for z, p in law) - mu[i] * mu[j] for j in range(4)] for i in range(4)]


def test_pooled_totals_differ_from_the_mean_of_block_ratios_and_a_zero_prefix_block_is_kept():
    rows = [(1, 1, 1, 2, 0, 2), (0, 3, 3, 6, 3, 6), (0, 0, 0, 0, 0, 0)]
    s = R.summarize_branch_blocks(blocks(rows), n_max=4, contract_id=C)
    assert s['B'] == 3 and s['mean'][1] == F(4, 3)                    # the zero-prefix block is counted
    est = R.branch_estimate(s)
    assert est['status'] == 'available' and est['estimate'] == F(1, 8)  # hand: 1/4 - 4/8 + 3/8
    per_block = [F(t, n) - F(u1, d1) + F(u0, d0) for t, n, u1, d1, u0, d0 in rows[:2]]   # block 3 is 0/0
    assert sum(per_block) / 2 == F(1, 4) != est['estimate']


def g_independent(m):
    return m[0] / m[1] - m[2] / m[3] + m[4] / m[5]


@pytest.mark.parametrize('mu', [(F(1, 5), F(7, 4), 3, 5, 2, F(9, 2)), (F(-3, 2), 2, F(1, 3), F(1, 2), 0, 1)])
def test_branch_gradient_matches_central_finite_differences(mu):
    mu, h = [F(x) for x in mu], F(1, 10 ** 6)
    grad = R.branch_gradient(mu)
    for j in range(6):
        up, down = list(mu), list(mu)
        up[j] += h
        down[j] -= h
        assert abs(grad[j] - (g_independent(up) - g_independent(down)) / (2 * h)) < F(1, 10 ** 8)


def test_branch_gradient_literal():
    assert R.branch_gradient((F(1, 5), F(7, 4), 3, 5, 2, F(9, 2))) == (F(4, 7), F(-16, 245), F(-1, 5), F(3, 25),
                                                                       F(2, 9), F(-8, 81))


def test_latent_total_is_unbiased_by_exhaustive_frame_srs_and_pair_enumeration():
    # source frames (probability, prefix contrasts d_i), including N = 0; m0 = 2 and r = 2
    frames = [(F(1, 4), ()), (F(1, 4), (F(1, 2),)), (F(1, 2), (F(1), F(-1, 2), F(0)))]
    expected_total = F(3, 8)                                           # hand: 1/4 * 1/2 + 1/2 * (1 - 1/2 + 0)
    m0, r = 2, 2
    # D_ij = d_i +/- (1 - |d_i|) has conditional mean d_i and lies in [-1, 1]. Two dependence designs:
    #   'per pair index': coin c_j for pair index j, shared across prefixes -> dependence across prefixes only;
    #   'one coin': a single coin for every prefix and both pair indices -> dependence across prefixes and pairs.
    designs = {'per pair index': [((c1, c2), F(1, 4)) for c1, c2 in itertools.product((0, 1), repeat=2)],
               'one coin': [((c, c), F(1, 2)) for c in (0, 1)]}
    for design, coins in designs.items():
        total = F(0)
        for p_frame, d in frames:
            n = len(d)
            subsets = list(itertools.combinations(range(n), min(m0, n)))  # simple random sampling without replacement
            for sel in subsets:
                for (c1, c2), p_coin in coins:
                    pairs = [[d[i] + (1 - abs(d[i])) * (2 * c1 - 1), d[i] + (1 - abs(d[i])) * (2 * c2 - 1)]
                             for i in sel]
                    est = R.latent_total_estimate(n, pairs, m0=m0, r=r)
                    assert abs(est) <= n
                    total += p_frame * F(1, len(subsets)) * p_coin * est
        assert total == expected_total, design


def test_one_block_gives_a_mean_and_a_rectangle_but_no_covariance_or_wald():
    s = R.summarize_blocks(blocks([(1, 0, 1, 0)]), R.PRIMARY_COORDS)
    assert s['B'] == 1 and s['covariance'] is None and s['covariance_status'].startswith('unavailable')
    lin = R.linear_estimate(s, FRESH)
    assert lin['estimate'] == 1 and lin['variance_of_estimate'] is None
    w = R.wald(s, FRESH, 0.05)
    assert w['status'].startswith('unavailable') and 'lower' not in w and 'se' not in w
    assert R.hoeffding_rectangle(s, PB, 0.05, mean_ranges=[(0, 1)] * 4)['B'] == 1


def test_degenerate_contrast_variance_is_unavailable_not_a_zero_width_interval():
    s = R.summarize_blocks(blocks([(1, 0, 1, 0)] * 3), R.PRIMARY_COORDS)
    w = R.wald(s, FRESH, 0.05)
    assert w['variance_of_estimate'] == 0 and w['status'].startswith('unavailable') and 'lower' not in w
    s2 = R.summarize_blocks(blocks([(1, 1, 0, 0), (2, 2, 1, 1)]), R.PRIMARY_COORDS)
    assert R.wald(s2, OFFLINE)['status'].startswith('unavailable')     # varies per coordinate, cancels exactly
    assert R.wald(s2, (1, 0, 0, 0))['status'] == 'available'


def test_wald_scale_uses_the_full_covariance_and_is_labelled_asymptotic():
    w = R.wald(R.summarize_blocks(blocks(SHARED), R.PRIMARY_COORDS), FRESH, 0.05)
    z = 1.959963984540054
    assert w['status'] == 'available' and w['estimate'] == F(1, 4) and w['se'] == 0.25
    assert w['z'] == pytest.approx(z, rel=1e-12)
    assert (w['lower'], w['upper']) == pytest.approx((0.25 - 0.25 * z, 0.25 + 0.25 * z), rel=1e-12)
    assert w['validated_coverage'] is False and 'not validated coverage' in w['interpretation']
    assert 'not dollars' in w['unit']


def test_branch_delta_scale_literal_and_exact_ratio_cancellation():
    s = R.summarize_branch_blocks(blocks([(0, 2, 2, 4, 1, 4), (2, 2, 2, 4, 1, 4)]), n_max=4)
    w = R.branch_wald(s, 0.05)
    # hand: only T varies (sample variance 2); dg/dT = 1/N = 1/2, so the variance is (1/4) * 2 / 2
    assert w['status'] == 'available' and w['estimate'] == F(1, 4) and w['variance_of_estimate'] == F(1, 4)
    assert w['se'] == 0.5 and w['validated_coverage'] is False and 'delta-method' in w['interpretation']
    # T = N in every block: the ratio is exactly 1 and the full covariance cancels to zero, so Wald is refused
    s2 = R.summarize_branch_blocks(blocks([(1, 1, 0, 1, 0, 1), (3, 3, 0, 1, 0, 1)]), n_max=4)
    w2 = R.branch_wald(s2, 0.05)
    assert w2['estimate'] == 1 and w2['variance_of_estimate'] == 0 and w2['status'].startswith('unavailable')


def test_zero_arm_denominator_makes_point_and_wald_unavailable_and_the_finite_set_whole():
    s = R.summarize_branch_blocks(blocks([(1, 2, 0, 0, 1, 2), (0, 1, 0, 0, 0, 1)]), n_max=4)
    est = R.branch_estimate(s)
    assert est['estimate'] is None and 'D1' in est['status']
    assert R.branch_wald(s, 0.05)['status'].startswith('unavailable')
    fs = R.branch_finite_set(s, 0.05)
    assert fs['interval'] == (-2.0, 2.0) and fs['status'].startswith('whole range')
    with pytest.raises(R.BlockInputError, match='positive'):
        R.branch_gradient((1, 2, 0, 0, 1, 2))


def test_ratio_interval_handles_positive_negative_and_mixed_numerators():
    assert R.ratio_interval((F(1, 4), F(1, 2)), (2, 4)) == (F(1, 16), F(1, 4))
    assert R.ratio_interval((F(-1, 2), F(-1, 4)), (2, 4)) == (F(-1, 4), F(-1, 16))
    assert R.ratio_interval((F(-1, 2), F(1, 4)), (2, 4)) == (F(-1, 4), F(1, 8))
    with pytest.raises(R.BlockInputError, match='positive denominator'):
        R.ratio_interval((0, 1), (0, 2))


def test_hoeffding_width_and_linear_propagation_match_independent_corner_enumeration():
    rows = [(1, 0, 1, 0), (2, -1, 1, 1), (0, 1, 0, 0), (1, 1, 1, 0)] * 2        # B = 8
    s = R.summarize_blocks(blocks(rows), R.PRIMARY_COORDS)
    parts = [2 * math.exp(-4)] * 4               # log(2 / alpha_j) = 4, so eps_j = c_j * sqrt(4 / 16) = c_j / 2
    rect = R.hoeffding_rectangle(s, PB, 0.2, alpha_parts=parts, mean_ranges=[(0, 1)] * 4)
    assert [c['eps'] for c in rect['components']] == pytest.approx([6.5, 6.5, 0.5, 0.5], rel=1e-12)
    # hand: raw offline-history interval 1 +/- 6.5 = (-5.5, 7.5) is capped at the support [-6, 7] before [0, 1]
    assert rect['components'][0]['raw'] == pytest.approx((-5.5, 7.5))
    assert rect['components'][0]['support_capped'] == pytest.approx((-5.5, 7.0))
    assert rect['components'][2]['support_capped'] == pytest.approx((0.25, 1.0))
    ivs = [c['interval'] for c in rect['components']]
    # hand: means 1, 1/4, 3/4, 1/4, capped at the support and then at [0, 1]
    assert ivs == [pytest.approx(x) for x in [(0, 1), (0, 1), (0.25, 1), (0, 0.75)]]
    assert R.linear_set(rect, FRESH, (-1, 1))['interval'] == pytest.approx((-0.5, 1.0))
    for name, a in R.PRIMARY_CONTRASTS.items():
        values = [sum(x * y for x, y in zip(a, corner)) for corner in itertools.product(*ivs)]
        lo, hi = R.PRIMARY_CONTRAST_RANGES[name]
        got = R.linear_set(rect, a, (lo, hi))
        assert got['status'] == 'finite-sample set'
        assert got['interval'] == pytest.approx((max(min(values), lo), min(max(values), hi)))


def test_empty_restricted_component_returns_the_whole_contrast_range():
    rows = [(7, 0, 1, 0), (7, 1, 0, 0)] * 8      # B = 16: the offline-history interval [1.82, 7] misses [0, 1]
    out = R.primary_analysis(blocks(rows), contract_id=C, score_bounds=PB, alpha=0.05)
    fs = {n: c['finite_sample'] for n, c in out['contrasts'].items()}
    assert out['rectangle']['components'][0]['interval'] is None
    assert fs['offline_gain']['interval'] == (-1.0, 1.0) and fs['offline_gain']['status'].startswith('whole range')
    assert fs['gain_calibration_discrepancy']['interval'] == (-2.0, 2.0)
    assert fs['fresh_gain']['status'] == 'finite-sample set'


def test_branch_finite_set_matches_corner_enumeration_and_falls_back_on_a_nonpositive_denominator():
    rows = [(1, 4, 8, 16, 4, 16), (2, 4, 10, 16, 6, 16), (0, 4, 9, 16, 5, 16), (-1, 4, 8, 16, 4, 16)] * 4
    s = R.summarize_branch_blocks(blocks(rows), n_max=4)
    fs = R.branch_finite_set(s, 0.5)
    assert fs['status'] == 'finite-sample set'
    iv = [c['interval'] for c in fs['rectangle']['components']]
    # hand: N and both D coordinates have means at their support maxima (4 and 16), so the raw upper limits exceed the
    # support and are capped there; eps_N = 4 sqrt(log 24 / 32), eps_D = 16 sqrt(log 24 / 32)
    eps = math.sqrt(math.log(24) / 32)
    assert iv[1] == pytest.approx((4 - 4 * eps, 4.0)) and iv[3] == pytest.approx((16 - 16 * eps, 16.0))
    assert iv[5] == pytest.approx((16 - 16 * eps, 16.0)) and iv[0] == pytest.approx((0.5 - 8 * eps, 0.5 + 8 * eps))

    def clip(x, lo, hi):
        return min(max(x, lo), hi)
    values = [clip(c[0] / c[1], -1, 1) - clip(c[2] / c[3], 0, 1) + clip(c[4] / c[5], 0, 1)
              for c in itertools.product(*iv)]                             # all 64 corners
    assert fs['interval'] == pytest.approx((max(min(values), -2), min(max(values), 2)))
    small = R.branch_finite_set(R.summarize_branch_blocks(blocks(rows[:2]), n_max=4), 0.05)   # B = 2
    assert small['interval'] == (-2.0, 2.0) and 'nonpositive denominator lower limit' in small['status']


def test_mapping_records_equal_ordered_records_and_primary_output_is_labelled():
    as_map = [dict(block_id=b['block_id'], contract_id=C, z=dict(zip(R.PRIMARY_COORDS, b['z'])))
              for b in blocks(SHARED)]
    assert R.summarize_blocks(as_map, R.PRIMARY_COORDS)['mean'] == R.summarize_blocks(blocks(SHARED),
                                                                                         R.PRIMARY_COORDS)['mean']
    out = R.primary_analysis(blocks(SHARED), contract_id=C, score_bounds=PB, alpha=0.05)
    assert set(out['contrasts']) == set(R.PRIMARY_CONTRASTS) and 'not dollars' in out['unit']
    assert 'lower' not in out['contrasts']['fresh_gain']['wald']          # no Wald interval unless wald_alpha given
    assert 'simultaneous' in out['multiplicity']


E = R.BlockInputError
GOOD = blocks([(1, 0, 1, 0), (0, 1, 0, 1)])
BAD_INPUTS = [
    ('duplicate id', lambda: R.summarize_blocks(GOOD + [dict(GOOD[0])], R.PRIMARY_COORDS), 'duplicate'),
    ('int and str id', lambda: R.summarize_blocks([dict(block_id=1, contract_id=C, z=(0, 0, 0, 0)),
                                                   dict(block_id='1', contract_id=C, z=(0, 0, 0, 0))],
                                                  R.PRIMARY_COORDS), 'duplicate'),
    ('mixed contract', lambda: R.summarize_blocks(GOOD + blocks([(0, 0, 0, 0)], 'other', 'x'), R.PRIMARY_COORDS),
     'mixed'),
    ('unexpected contract', lambda: R.summarize_blocks(GOOD, R.PRIMARY_COORDS, contract_id='other'), 'expected'),
    ('nan', lambda: R.summarize_blocks(blocks([(float('nan'), 0, 0, 0)]), R.PRIMARY_COORDS), 'not finite'),
    ('inf', lambda: R.summarize_blocks(blocks([(0, 0, float('inf'), 0)]), R.PRIMARY_COORDS), 'not finite'),
    ('bool value', lambda: R.summarize_blocks(blocks([(True, 0, 0, 0)]), R.PRIMARY_COORDS), 'int, Fraction'),
    ('string value', lambda: R.summarize_blocks(blocks([('1', 0, 0, 0)]), R.PRIMARY_COORDS), 'int, Fraction'),
    ('short vector', lambda: R.summarize_blocks(blocks([(1, 0, 1)]), R.PRIMARY_COORDS), 'coordinates'),
    ('string vector', lambda: R.summarize_blocks([dict(block_id='a', contract_id=C, z='1010')], R.PRIMARY_COORDS),
     'sequence'),
    ('wrong mapping keys', lambda: R.summarize_blocks([dict(block_id='a', contract_id=C, z=dict(x=1))],
                                                      R.PRIMARY_COORDS), 'exactly the coordinates'),
    ('missing key', lambda: R.summarize_blocks([dict(block_id='a', z=(0, 0, 0, 0))], R.PRIMARY_COORDS), 'exactly'),
    ('extra key', lambda: R.summarize_blocks([dict(GOOD[0], weight=1)], R.PRIMARY_COORDS), 'exactly'),
    ('bool id', lambda: R.summarize_blocks([dict(block_id=True, contract_id=C, z=(0, 0, 0, 0))], R.PRIMARY_COORDS),
     'block_id'),
    ('empty contract', lambda: R.summarize_blocks(blocks([(0, 0, 0, 0)], ' '), R.PRIMARY_COORDS), 'contract'),
    ('no blocks', lambda: R.summarize_blocks([], R.PRIMARY_COORDS), 'no blocks'),
    ('blocks not a list', lambda: R.summarize_blocks(GOOD[0], R.PRIMARY_COORDS), 'sequence'),
    ('out of bounds is not clipped', lambda: R.summarize_blocks(blocks([(0, 0, F(3, 2), 0)]), R.PRIMARY_COORDS,
                                                                bounds=PB), 'never clipped'),
    ('rectangle checks bounds', lambda: R.hoeffding_rectangle(R.summarize_blocks(blocks([(8, 0, 0, 0)]),
                                                                                 R.PRIMARY_COORDS), PB, 0.05),
     'never clipped'),
    ('reversed bounds', lambda: R.validate_bounds([(1, 0)], 1), 'lower <= upper'),
    ('off a zero-width bound', lambda: R.summarize_blocks(blocks([(0, 0, 0, F(1, 4))]), R.PRIMARY_COORDS,
                                                         bounds=PB[:3] + ((F(1, 2), F(1, 2)),)), 'never clipped'),
    ('unrepresentable wald alpha', lambda: R.wald(R.summarize_blocks(GOOD, R.PRIMARY_COORDS), FRESH,
                                                  F(1, 10 ** 400)), 'too small'),
    ('unrepresentable branch alpha', lambda: R.branch_wald(R.summarize_branch_blocks(
        blocks([(0, 1, 0, 1, 0, 1)] * 2), 4), F(1, 10 ** 400)), 'too small'),
    ('overflowing bound width', lambda: R.hoeffding_rectangle(R.summarize_blocks(GOOD, R.PRIMARY_COORDS),
                                                              [(-1e308, 1e308)] * 4, 0.05), 'finite float'),
    ('bounds count', lambda: R.validate_bounds([(0, 1)], 4), '4'),
    ('nonfinite bound', lambda: R.validate_bounds([(0, float('inf'))], 1), 'not finite'),
    ('alpha 0', lambda: R.validate_alpha(0), 'alpha'),
    ('alpha 1', lambda: R.validate_alpha(1), 'alpha'),
    ('alpha negative', lambda: R.validate_alpha(-0.1), 'alpha'),
    ('alpha nan', lambda: R.validate_alpha(float('nan')), 'not finite'),
    ('alpha parts over budget', lambda: R.validate_alpha(0.05, 2, [0.03, 0.03]), 'more than alpha'),
    ('alpha part zero', lambda: R.validate_alpha(0.05, 2, [0.05, 0]), 'positive'),
    ('alpha parts count', lambda: R.validate_alpha(0.05, 2, [0.01]), 'budgets'),
    ('wald alpha', lambda: R.wald(R.summarize_blocks(GOOD, R.PRIMARY_COORDS), FRESH, 1.5), 'alpha'),
    ('contrast length', lambda: R.linear_estimate(R.summarize_blocks(GOOD, R.PRIMARY_COORDS), (1, -1)), 'coefficients'),
    ('branch |T| > N', lambda: R.summarize_branch_blocks(blocks([(2, 1, 0, 0, 0, 0)]), 4), 'exceeds N'),
    ('branch U > D', lambda: R.summarize_branch_blocks(blocks([(0, 1, 2, 1, 0, 0)]), 4), 'U <= D'),
    ('branch D > 4N', lambda: R.summarize_branch_blocks(blocks([(0, 1, 0, 0, 0, 5)]), 4), 'U <= D <= 4N'),
    ('branch N > n_max', lambda: R.summarize_branch_blocks(blocks([(0, 5, 0, 0, 0, 0)]), 4), 'bounds'),
    ('branch fractional N', lambda: R.summarize_branch_blocks(blocks([(0, 1.5, 0, 0, 0, 0)]), 4), 'integer'),
    ('branch n_max', lambda: R.summarize_branch_blocks(blocks([(0, 0, 0, 0, 0, 0)]), 0), 'positive'),
    ('prefixes for N = 0', lambda: R.latent_total_estimate(0, [[0, 0]], m0=2, r=2), 'selected prefixes'),
    ('too few prefixes', lambda: R.latent_total_estimate(3, [[0, 0]], m0=2, r=2), 'selected prefixes'),
    ('wrong r', lambda: R.latent_total_estimate(1, [[0]], m0=2, r=2), 'r = 2'),
    ('pair outside [-1, 1]', lambda: R.latent_total_estimate(1, [[2, 0]], m0=2, r=2), 'outside'),
    ('m0 zero', lambda: R.latent_total_estimate(1, [], m0=0, r=2), 'positive'),
]


def test_zero_width_bound_is_a_valid_deterministic_coordinate():
    bounds = PB[:3] + ((F(1, 2), F(1, 2)),)            # fresh_prompt fixed at 1/2: c_4 = 0 (Prop. 2)
    rows = [(1, 0, 1, F(1, 2)), (0, 1, 0, F(1, 2)), (1, 1, 1, F(1, 2)), (0, 0, 1, F(1, 2))]
    s = R.summarize_blocks(blocks(rows), R.PRIMARY_COORDS, bounds=bounds)
    assert s['mean'][3] == F(1, 2) and s['covariance'][3] == (0, 0, 0, 0)
    rect = R.hoeffding_rectangle(s, bounds, F(1, 20), mean_ranges=[(0, 1)] * 4)
    c4 = rect['components'][3]
    assert c4['eps'] == 0.0 and c4['interval'] == (0.5, 0.5)
    lo3, hi3 = rect['components'][2]['interval']
    assert R.linear_set(rect, FRESH, (-1, 1))['interval'] == (lo3 - 0.5, hi3 - 0.5)
    assert R.validate_bounds([(0, 0)], 1) == ((0, 0),)


def test_singleton_mean_and_parameter_ranges_are_allowed_and_reversed_ranges_refused():
    s = R.summarize_blocks(blocks([(1, 0, 1, 0), (0, 1, 0, 1)]), R.PRIMARY_COORDS)      # means 1/2 each
    rect = R.hoeffding_rectangle(s, PB, F(1, 20), mean_ranges=[(0, 1), (0, 1), (F(1, 2), F(1, 2)), (0, 0)])
    assert rect['components'][2]['interval'] == (0.5, 0.5)            # the singleton lies inside its capped interval
    assert rect['components'][3]['interval'] == (0.0, 0.0)            # 0 lies inside [1/2 - eps, 1/2 + eps] cap [0, 1]
    assert R.linear_set(rect, FRESH, (-1, 1))['interval'] == (0.5, 0.5)
    assert R.linear_set(rect, FRESH, (F(1, 4), F(1, 4)))['interval'] == (0.25, 0.25)   # singleton parameter range
    with pytest.raises(R.BlockInputError, match='lower <= upper'):
        R.linear_set(rect, FRESH, (1, -1))
    with pytest.raises(R.BlockInputError, match='lower <= upper'):
        R.hoeffding_rectangle(s, PB, F(1, 20), mean_ranges=[(1, 0)] * 4)


def test_tiny_alpha_uses_the_lower_tail_and_unrepresentable_values_are_explicit():
    z = R.normal_upper_quantile(1e-20)                 # 1 - 1e-20 / 2 rounds to 1.0 in floating point
    assert 9.3 < z < 9.4 and 0.5 * math.erfc(z / math.sqrt(2)) == pytest.approx(5e-21, rel=1e-9)
    assert R.normal_upper_quantile(0.05) == pytest.approx(1.959963984540054, rel=1e-12)
    w = R.wald(R.summarize_blocks(blocks(SHARED), R.PRIMARY_COORDS), FRESH, 1e-20)
    assert w['status'] == 'available' and w['upper'] - w['lower'] == pytest.approx(2 * 0.25 * z, rel=1e-12)
    # a variance that overflows a float is explicitly unavailable, not a finite interval
    big = R.summarize_blocks(blocks([(0, 0, 1e200, 0), (0, 0, -1e200, 0)]), R.PRIMARY_COORDS)
    assert R.wald(big, FRESH, 0.05)['status'].startswith('unavailable')
    # a tiny error budget is evaluated from its exact numerator and denominator, not a float that underflows
    parts = [F(1, 10 ** 400), F(1, 100), F(1, 100), F(1, 100)]
    rect = R.hoeffding_rectangle(R.summarize_blocks(blocks(SHARED), R.PRIMARY_COORDS), PB, F(1, 20),
                                 alpha_parts=parts)
    assert rect['components'][0]['eps'] == pytest.approx(13 * math.sqrt((math.log(2) + 400 * math.log(10)) / 8),
                                                         rel=1e-12)


@pytest.mark.parametrize('name,call,match', BAD_INPUTS, ids=[b[0] for b in BAD_INPUTS])
def test_invalid_input_is_refused_explicitly(name, call, match):
    with pytest.raises(E, match=match):
        call()


def test_module_is_pure_arithmetic():
    src = (ROOT / 'experiments/v2_sim/replicated_block_inference.py').read_text()
    for banned in ('import random', 'numpy', 'subprocess', 'open(', 'requests', 'json.dump'):
        assert banned not in src
