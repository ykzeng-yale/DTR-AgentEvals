"""Exact finite enumeration of fixed-size prefix sampling; no random draws."""
from fractions import Fraction as F
from itertools import combinations, product
from math import comb


def mean(xs):
    return sum(xs, F(0)) / len(xs)


def sample_variance(xs):
    center = mean(xs)
    return sum((x - center) ** 2 for x in xs) / (len(xs) - 1)


def prefix_outcomes(p0, p1):
    """Two independent Bernoulli continuations per arm, exhaustively enumerated."""
    result = []
    for ys in product((F(0), F(1)), repeat=4):
        probability = F(1)
        for y, p in zip(ys, (p0, p0, p1, p1)):
            probability *= p if y else 1 - p
        if probability:
            result.append((probability, mean(ys[2:]) - mean(ys[:2]),
                           sample_variance(ys[:2]) / 2 + sample_variance(ys[2:]) / 2))
    assert sum(row[0] for row in result) == 1
    return result


def enumerate_design(probabilities, m):
    n = len(probabilities)
    f = F(m, n)
    outcomes = [prefix_outcomes(*ps) for ps in probabilities]
    rows = []
    for selected in combinations(range(n), m):
        for draw in product(*(outcomes[i] for i in selected)):
            probability = F(1, comb(n, m))
            for row in draw:
                probability *= row[0]
            contrasts = [row[1] for row in draw]
            estimate = mean(contrasts)
            vhat = (1 - f) * sample_variance(contrasts) / m + f * mean([row[2] for row in draw]) / m
            rows.append((probability, estimate, vhat))
    assert sum(row[0] for row in rows) == 1
    target = mean([p1 - p0 for p0, p1 in probabilities])
    within = mean([p0 * (1 - p0) / 2 + p1 * (1 - p1) / 2 for p0, p1 in probabilities])
    between = sample_variance([p1 - p0 for p0, p1 in probabilities])
    expected_var = (1 - f) * between / m + within / m
    observed_mean = sum(p * b for p, b, _ in rows)
    observed_var = sum(p * (b - target) ** 2 for p, b, _ in rows)
    mean_vhat = sum(p * v for p, _, v in rows)
    assert observed_mean == target
    assert observed_var == expected_var
    assert mean_vhat == expected_var
    return rows, target, expected_var


def test_fixed_size_prefix_sampling_with_heterogeneous_noise():
    enumerate_design([(F(1, 4), F(3, 4)), (F(1, 2), F(1, 4)), (F(3, 4), F(1, 2))], 2)


def test_census_retains_continuation_noise():
    _, _, variance = enumerate_design([(F(1, 4), F(3, 4)), (F(1, 2), F(1, 4)), (F(3, 4), F(1, 2))], 3)
    assert variance > 0


def test_noiseless_prefix_sampling_and_census_boundaries():
    probabilities = [(F(0), F(1)), (F(1), F(0)), (F(0), F(0))]
    _, _, partial = enumerate_design(probabilities, 2)
    _, _, census = enumerate_design(probabilities, 3)
    assert partial > 0
    assert census == 0


def test_random_frame_comparison_needs_between_frame_variance():
    frames = [([(F(1, 4), F(3, 4)), (F(1, 2), F(1, 4)), (F(3, 4), F(1, 2))], F(1, 10)),
              ([(F(0), F(1)), (F(1), F(0)), (F(0), F(1))], F(-1, 5))]
    all_rows, conditional_targets, conditional_variances = [], [], []
    for ps, log_value in frames:
        rows, target, variance = enumerate_design(ps, 2)
        conditional_targets.append(target - log_value)
        conditional_variances.append(variance)
        all_rows.extend((p / 2, b - log_value) for p, b, _ in rows)
    overall_mean = sum(p * d for p, d in all_rows)
    overall_var = sum(p * (d - overall_mean) ** 2 for p, d in all_rows)
    between = mean([(d - mean(conditional_targets)) ** 2 for d in conditional_targets])
    assert between > 0
    assert overall_var == mean(conditional_variances) + between
