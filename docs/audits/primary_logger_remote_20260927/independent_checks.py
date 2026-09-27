#!/usr/bin/env python3
"""Independent finite checks for the DTR primary-logger/precision review.

Uses only the Python standard library.  It does not read project fixtures or
execute any model, VM, container, or experiment.
"""

from fractions import Fraction
from itertools import product
from math import ceil, log
import json


BITS = (Fraction(0), Fraction(1))
HALVES = (Fraction(0), Fraction(1, 2), Fraction(1))


def primary_score(q, target, action, y):
    j = Fraction(action == target)
    q_target = q[target]
    return q_target + 2 * j * (y - q_target)


def full_score(q1, q2, target, action, y, first_matches):
    i = Fraction(first_matches)
    j = Fraction(action == target)
    return q1 + 2 * i * (q2 - q1) + 4 * i * j * (y - q2)


def extrema(values):
    return [str(min(values)), str(max(values))]


def hoeffding_count(width, half_width, alpha=0.05, multiplicity=3):
    return ceil(
        width * width * log(2 * multiplicity / alpha)
        / (2 * half_width * half_width)
    )


def main():
    primary_scores = []
    primary_differences = []
    primary_disagreement_d2 = []
    primary_agreement_d = []
    for q0, q1, h, p, action, y in product(BITS, BITS, (0, 1), (0, 1), (0, 1), BITS):
        q = {0: q0, 1: q1}
        phi_h = primary_score(q, h, action, y)
        phi_p = primary_score(q, p, action, y)
        d = phi_h - phi_p
        primary_scores.extend((phi_h, phi_p))
        primary_differences.append(d)
        if h != p:
            primary_disagreement_d2.append(d * d)
        else:
            primary_agreement_d.append(d)

    # Exact conditional-mean identity on a finite rational grid.
    conditional_mean_failures = []
    for q0, q1, mu0, mu1, target in product(HALVES, HALVES, HALVES, HALVES, (0, 1)):
        q = {0: q0, 1: q1}
        mu = {0: mu0, 1: mu1}
        expected = Fraction(0)
        for action in (0, 1):
            for y in (0, 1):
                py = mu[action] if y else 1 - mu[action]
                expected += Fraction(1, 2) * py * primary_score(q, target, action, Fraction(y))
        if expected != mu[target]:
            conditional_mean_failures.append(
                [str(q0), str(q1), str(mu0), str(mu1), target, str(expected)]
            )

    full_scores = []
    full_differences = []
    for q1h, q1p, q2h, q2p, y, first_matches, h, p, action in product(
        BITS, BITS, BITS, BITS, BITS, (False, True), (0, 1), (0, 1), (0, 1)
    ):
        phi_h = full_score(q1h, q2h, h, action, y, first_matches)
        phi_p = full_score(q1p, q2p, p, action, y, first_matches)
        full_scores.extend((phi_h, phi_p))
        full_differences.append(phi_h - phi_p)

    # Under known randomization one may deliberately use a common arbitrary
    # first-stage prediction and one common terminal action-value prediction.
    # This is not the contract used for REQ-025's [-5,5] bound, but it shows
    # that that valid separate-nuisance bound is not optimal under sharing.
    full_shared_differences = []
    for q1, q20, q21, y, first_matches, h, p, action in product(
        BITS, BITS, BITS, BITS, (False, True), (0, 1), (0, 1), (0, 1)
    ):
        q2 = {0: q20, 1: q21}
        phi_h = full_score(q1, q2[h], h, action, y, first_matches)
        phi_p = full_score(q1, q2[p], p, action, y, first_matches)
        full_shared_differences.append(phi_h - phi_p)

    # Pointwise first-stage cancellation for the deterministic-S logger.
    cancellation_failures = []
    for q1, q2, y, j in product(HALVES, HALVES, HALVES, (False, True)):
        longitudinal = q1 + (q2 - q1) + 2 * Fraction(j) * (y - q2)
        reduced = q2 + 2 * Fraction(j) * (y - q2)
        if longitudinal != reduced:
            cancellation_failures.append([str(q1), str(q2), str(y), j])

    # Separate policy-specific predictions break D=0 on agreement and hence
    # the disagreement-only second-moment bound when d=0.
    separate_prediction_counterexample = {
        "same_target_action": 0,
        "logged_action": 0,
        "outcome": 0,
        "q_H": 0,
        "q_P": 1,
        "D": str(
            (Fraction(0) + 2 * (Fraction(0) - Fraction(0)))
            - (Fraction(1) + 2 * (Fraction(0) - Fraction(1)))
        ),
        "D_squared": "1",
        "disagreement_probability": "0",
    }

    counts_primary = {
        str(w): hoeffding_count(w, 0.05) for w in (2, 4, 6)
    }
    counts_original = {
        str(w): hoeffding_count(w, 0.05) for w in (2, 10, 12)
    }
    all_expected_counts = {
        "primary": {"2": 3830, "4": 15320, "6": 34470},
        "original": {"2": 3830, "10": 95750, "12": 137880},
    }

    # A concrete weighted-replication factor check.
    lambdas = (Fraction(1, 3), Fraction(2, 3))
    replicates = (2, 3)
    weighted_factor = sum(lam * lam / r for lam, r in zip(lambdas, replicates))
    expanded_factor = sum(
        (lam / r) ** 2
        for lam, r in zip(lambdas, replicates)
        for _ in range(r)
    )

    results = {
        "primary_shared_q": {
            "score_extrema": extrema(primary_scores),
            "contrast_extrema": extrema(primary_differences),
            "agreement_contrast_extrema": extrema(primary_agreement_d),
            "max_D_squared_on_disagreement": str(max(primary_disagreement_d2)),
        },
        "full_two_decision_logger": {
            "score_extrema": extrema(full_scores),
            "contrast_extrema": extrema(full_differences),
            "contrast_extrema_with_shared_q1_and_terminal_action_q": extrema(
                full_shared_differences
            ),
        },
        "conditional_mean_grid_failures": conditional_mean_failures,
        "first_stage_cancellation_failures": cancellation_failures,
        "absorbed_primary_contrast": "0",
        "separate_prediction_agreement_counterexample": separate_prediction_counterexample,
        "initial_L_support_under_deterministic_S_logger": {
            "behavior_probability": "0",
            "target_probability": "1",
            "supported": False,
        },
        "hoeffding_counts_h_0.05_alpha_0.05_three_contrasts": {
            "primary_widths": counts_primary,
            "original_widths": counts_original,
        },
        "weighted_replication_example": {
            "sum_lambda_squared_over_R": str(weighted_factor),
            "expanded_sum_of_summand_width_factors": str(expanded_factor),
        },
    }

    assert extrema(primary_scores) == ["-1", "2"]
    assert extrema(primary_differences) == ["-2", "2"]
    assert extrema(primary_agreement_d) == ["0", "0"]
    assert max(primary_disagreement_d2) == 4
    assert not conditional_mean_failures
    assert not cancellation_failures
    assert extrema(full_scores) == ["-3", "4"]
    assert extrema(full_differences) == ["-5", "5"]
    assert extrema(full_shared_differences) == ["-4", "4"]
    assert counts_primary == all_expected_counts["primary"]
    assert counts_original == all_expected_counts["original"]
    assert weighted_factor == expanded_factor == Fraction(11, 54)

    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
