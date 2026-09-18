"""Independent full-enumeration checks of the two-stage influence functions.

These compare pathwise derivatives to finite differences, not one implementation
to a duplicate implementation. The second-stage history includes the first action.
"""
from itertools import product
import numpy as np
import pytest


def parameters():
    rng = np.random.default_rng(219)
    return {
        "p": np.array(.43),
        "b1": rng.uniform(.2, .8, (2,)),
        "l": rng.uniform(.2, .8, (2, 2)),
        "b2": rng.uniform(.2, .8, (2, 2, 2)),
        "m": rng.uniform(.2, .8, (2, 2, 2, 2)),
    }


def target(par, delta=2.):
    return tuple(delta * par[k] / (1 + (delta - 1) * par[k]) for k in ("b1", "b2"))


def value_components(par, pi):
    p1, p2 = pi
    v2 = (1 - p2) * par["m"][..., 0] + p2 * par["m"][..., 1]
    q1 = (1 - par["l"]) * v2[..., 0] + par["l"] * v2[..., 1]
    v1 = (1 - p1) * q1[:, 0] + p1 * q1[:, 1]
    value = (1 - par["p"]) * v1[0] + par["p"] * v1[1]
    return value, v1, q1, v2


def bernoulli(z, p):
    return p if z else 1 - p


def score_expectation(par, pi, key, index, incremental=False, delta=2.):
    value, v1, q1, v2 = value_components(par, pi)
    total, mean_if = 0., 0.
    for x, a1, l, a2, y in product((0, 1), repeat=5):
        b1, b2 = par["b1"][x], par["b2"][x, a1, l]
        pl, pm = par["l"][x, a1], par["m"][x, a1, l, a2]
        probability = (bernoulli(x, par["p"]) * bernoulli(a1, b1)
                       * bernoulli(l, pl) * bernoulli(a2, b2) * bernoulli(y, pm))
        w1 = bernoulli(a1, pi[0][x]) / bernoulli(a1, b1)
        w2 = w1 * bernoulli(a2, pi[1][x, a1, l]) / bernoulli(a2, b2)
        influence = v1[x] - value + w1 * (v2[x, a1, l] - q1[x, a1]) + w2 * (y - pm)
        if incremental:
            influence += delta / (1 + (delta - 1) * b1)**2 * (q1[x, 1] - q1[x, 0]) * (a1 - b1)
            influence += w1 * delta / (1 + (delta - 1) * b2)**2 * (par["m"][x, a1, l, 1] - par["m"][x, a1, l, 0]) * (a2 - b2)
        active, z, p = {
            "p": (True, x, par["p"]),
            "b1": ((x,) == index, a1, b1),
            "l": ((x, a1) == index, l, pl),
            "b2": ((x, a1, l) == index, a2, b2),
            "m": ((x, a1, l, a2) == index, y, pm),
        }[key]
        score = (z - p) / (p * (1 - p)) if active else 0.
        total += probability * influence * score
        mean_if += probability * influence
    assert abs(mean_if) < 1e-12
    return total


@pytest.mark.parametrize("incremental", [False, True])
@pytest.mark.parametrize("delta", [1., 2.])
def test_influence_function_matches_all_coordinate_derivatives(incremental, delta):
    par = parameters()
    frozen = target(par, delta)
    for key, arr in par.items():
        for index in np.ndindex(arr.shape):
            eps = 1e-6
            plus = {k: v.copy() for k, v in par.items()}
            minus = {k: v.copy() for k, v in par.items()}
            plus[key][index] += eps
            minus[key][index] -= eps
            vp = value_components(plus, target(plus, delta) if incremental else frozen)[0]
            vm = value_components(minus, target(minus, delta) if incremental else frozen)[0]
            derivative = (vp - vm) / (2 * eps)
            implied = score_expectation(par, frozen, key, index, incremental, delta)
            assert abs(derivative - implied) < 1e-8, (key, index, derivative, implied)


def test_fixed_target_score_is_wrong_for_unknown_behavior_incremental_target():
    par = parameters()
    pi = target(par)
    fixed_score_derivative = score_expectation(par, pi, "b1", (1,))
    corrected_derivative = score_expectation(par, pi, "b1", (1,), incremental=True)
    assert abs(fixed_score_derivative) < 1e-12
    assert abs(corrected_derivative) > 1e-4


def test_exact_drift_identity_with_all_nuisances_perturbed():
    par = parameters()
    pi = target(par)
    truth, _, q1, _ = value_components(par, pi)
    rng = np.random.default_rng(508)
    qb1, qb2 = rng.uniform(0., 1., (2, 2)), rng.uniform(0., 1., (2, 2, 2, 2))
    bb1, bb2 = rng.uniform(.2, .8, (2,)), rng.uniform(.2, .8, (2, 2, 2))
    vb1 = (1 - pi[0]) * qb1[:, 0] + pi[0] * qb1[:, 1]
    vb2 = (1 - pi[1]) * qb2[..., 0] + pi[1] * qb2[..., 1]
    mean_score, drift = 0., 0.
    for x, a1, l, a2, y in product((0, 1), repeat=5):
        b1, b2 = par["b1"][x], par["b2"][x, a1, l]
        pl, pm = par["l"][x, a1], par["m"][x, a1, l, a2]
        prob = bernoulli(x, par["p"]) * bernoulli(a1, b1) * bernoulli(l, pl) * bernoulli(a2, b2) * bernoulli(y, pm)
        w1 = bernoulli(a1, pi[0][x]) / bernoulli(a1, bb1[x])
        w2 = w1 * bernoulli(a2, pi[1][x, a1, l]) / bernoulli(a2, bb2[x, a1, l])
        phi = vb1[x] + w1 * (vb2[x, a1, l] - qb1[x, a1]) + w2 * (y - qb2[x, a1, l, a2])
        mean_score += prob * phi
    for x in (0, 1):
        px = bernoulli(x, par["p"])
        for a1 in (0, 1):
            pa1, ba1, bba1 = bernoulli(a1, pi[0][x]), bernoulli(a1, par["b1"][x]), bernoulli(a1, bb1[x])
            drift += px * pa1 * (bba1 - ba1) / bba1 * (qb1[x, a1] - q1[x, a1])
            for l in (0, 1):
                ph = px * ba1 * bernoulli(l, par["l"][x, a1])
                for a2 in (0, 1):
                    pa2 = bernoulli(a2, pi[1][x, a1, l])
                    ba2, bba2 = bernoulli(a2, par["b2"][x, a1, l]), bernoulli(a2, bb2[x, a1, l])
                    drift += ph * pa1 / bba1 * pa2 * (bba2 - ba2) / bba2 * (qb2[x, a1, l, a2] - par["m"][x, a1, l, a2])
    assert abs(mean_score - truth - drift) < 1e-12
