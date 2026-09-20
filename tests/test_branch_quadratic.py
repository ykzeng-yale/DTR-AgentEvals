"""Exact inclusion-probability checks for a latent quadratic moment, not a CI test."""
from fractions import Fraction as F
from itertools import combinations, product
from math import comb


def quadratic(d, C, b, c):
    return sum(C[i][j] * d[i] * d[j] for i in range(len(d)) for j in range(len(d))) + 2 * sum(x * y for x, y in zip(b, d)) + c


def estimate(z, vhat, selected, n, C, b, c):
    m = len(selected)
    p1, p2 = F(m, n), F(m * (m - 1), n * (n - 1))
    diag = sum(C[i][i] * (z[i] ** 2 - vhat[i]) / p1 for i in selected)
    off = sum(C[i][j] * z[i] * z[j] / p2 for i in selected for j in selected if i != j)
    return diag + off + 2 * sum(b[i] * z[i] / p1 for i in selected) + c


def enumerate_mean(d, noise, m, C, b, c, correct_noise=True):
    total = F(0)
    n = len(d)
    for selected in combinations(range(n), m):
        for signs in product((-1, 1), repeat=2 * m):
            z, vhat = {}, {}
            for k, i in enumerate(selected):
                # Two independent unbiased replicates; vhat is sample variance / 2.
                x, y = d[i] + noise[i] * signs[2*k], d[i] + noise[i] * signs[2*k+1]
                z[i], vhat[i] = (x+y)/2, (x-y)**2/4 if correct_noise else F(0)
            total += estimate(z, vhat, selected, n, C, b, c) / (comb(n, m) * 2**(2*m))
    return total


def test_quadratic_unbiased_with_heterogeneous_replicate_noise():
    d, noise = [F(1, 4), F(-1, 3), F(2, 5)], [F(1, 4), F(1, 2), F(1, 3)]
    C = [[F(2), F(1, 3), F(-1, 5)], [F(1, 3), F(1), F(1, 4)], [F(-1, 5), F(1, 4), F(3)]]
    b, c = [F(1, 6), F(-1, 7), F(1, 8)], F(2, 9)
    assert enumerate_mean(d, noise, 2, C, b, c) == quadratic(d, C, b, c)
    assert enumerate_mean(d, noise, 2, C, b, c, False) > quadratic(d, C, b, c)
    assert enumerate_mean(d, [F(0)]*3, 2, C, b, c) == quadratic(d, C, b, c)


def test_census_still_requires_fresh_noise_subtraction():
    d, noise = [F(1, 4), F(1, 2)], [F(1, 4), F(1, 2)]
    C, b, c = [[F(1), F(0)], [F(0), F(1)]], [F(0), F(0)], F(0)
    assert enumerate_mean(d, noise, 2, C, b, c) == quadratic(d, C, b, c)
    assert enumerate_mean(d, noise, 2, C, b, c, False) == quadratic(d, C, b, c) + sum(x*x/2 for x in noise)


def test_full_frame_derivative_expansion_preserves_unequal_prefix_counts():
    groups, counts, n = [0, 0, 1], [2, 1, 0], 3
    d, ell = [F(1, 4), F(1, 2), F(-1, 4)], [F(1, 10), F(-1, 10), F(0)]
    A = [[(F(int(groups[i] == g)) - F(counts[g], n))/n for i in range(n)] for g in range(3)]
    C = [[sum(A[g][i]*A[g][j] for g in range(3)) for j in range(n)] for i in range(n)]
    b = [-sum(A[g][i]*ell[g] for g in range(3)) for i in range(n)]
    c = sum(x*x for x in ell)
    direct = sum(((sum(d[i] for i in range(n) if groups[i] == g)-F(counts[g], n)*sum(d))/n-ell[g])**2 for g in range(3))
    assert quadratic(d, C, b, c) == direct
    assert enumerate_mean(d, [F(1, 4)]*3, 2, C, b, c) == direct


def test_nonnegative_quadratic_can_have_negative_unbiased_estimate():
    C, b, c = [[F(1), F(0)], [F(0), F(1)]], [F(0), F(0)], F(0)
    # Both latent means are zero; opposite-sign replicate pairs give z=0, vhat=1.
    out = estimate({0:F(0), 1:F(0)}, {0:F(1), 1:F(1)}, (0, 1), 2, C, b, c)
    assert quadratic([F(0), F(0)], C, b, c) == 0
    assert out == -2
