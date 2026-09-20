"""Exact toy checks for the source-model boundary; no Monte Carlo or coverage test."""
from fractions import Fraction as F
from itertools import product


def contrast(rows, weights=None):
    # Columns: M, latent T, log numerator/denominator for arms 1 then 0.
    weights = [F(1)] * len(rows) if weights is None else weights
    totals = [sum(w * row[k] for w, row in zip(weights, rows)) for k in range(6)]
    return totals[1] / totals[0] - totals[2] / totals[3] + totals[4] / totals[5]


def derivatives(rows):
    totals = [sum(row[k] for row in rows) for k in range(6)]
    beta, nu1, nu0 = totals[1] / totals[0], totals[2] / totals[3], totals[4] / totals[5]
    return [(t - beta*m)/totals[0] - (n1 - nu1*d1)/totals[3]
            + (n0 - nu0*d0)/totals[5] for m, t, n1, d1, n0, d0 in rows]


def row(y):
    return (F(1), F(y), F(y, 2), F(1), F(0), F(1))


def test_unequal_prefix_ratio_derivative_preserves_source_log_covariance():
    rows = [tuple(map(F, x)) for x in ((1, 0, 1, 2, 0, 1), (2, 2, 0, 1, 1, 2), (3, 1, 2, 3, 1, 1))]
    u = derivatives(rows)
    assert sum(u) == 0
    h = F(1, 10**5)
    for g in range(len(rows)):
        plus, minus = [F(1)]*3, [F(1)]*3
        plus[g] += h
        minus[g] -= h
        numeric = (contrast(rows, plus) - contrast(rows, minus)) / (2*h)
        assert abs(numeric-u[g]) < F(1, 10**10)
    # Independent population delta-method calculation for the uniform three-type law.
    means = [sum(x[k] for x in rows)/3 for k in range(6)]
    grad = (-means[1]/means[0]**2, 1/means[0], -1/means[3],
            means[2]/means[3]**2, 1/means[5], -means[4]/means[5]**2)
    psi = [sum(a*(x[k]-means[k]) for k, a in enumerate(grad)) for x in rows]
    assert psi == [3*x for x in u]
    assert sum(psi) == 0


def test_iid_exact_variance_and_finite_sample_oracle_bias():
    # Y is iid Bernoulli(1/2), T=Y and log numerator=Y/2.
    # Branch/log covariance matters: their difference is Y/2, not independent noises.
    for j in (2, 3, 4):
        values, quadratics = [], []
        for ys in product((0, 1), repeat=j):
            rows = [row(y) for y in ys]
            values.append(contrast(rows))
            quadratics.append(sum(x*x for x in derivatives(rows)))
        mean = sum(values)/len(values)
        var = sum((v-mean)**2 for v in values)/len(values)
        eq = sum(quadratics)/len(quadratics)
        assert mean == F(1, 4)
        assert j*var == F(1, 16)
        assert j*eq == F(j-1, 16*j)  # asymptotic relation is not finite-J equality
        assert F(5, 16) != j*var  # dropping covariance would give 1/4 + 1/16


def test_fixed_benchmark_positive_task_spread_is_not_execution_variance():
    rows = [row(y) for y in (0, 0, 1, 1)]
    j = len(rows)
    # Complete census and deterministic execution: no source or continuation randomness.
    repeat_values = [contrast(rows)]*4
    assert all(v == F(1, 4) for v in repeat_values)
    assert sum((v-repeat_values[0])**2 for v in repeat_values) == 0
    q = sum(x*x for x in derivatives(rows))
    assert j*q == F(1, 16) > 0
