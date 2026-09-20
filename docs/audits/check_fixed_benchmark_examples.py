"""Deterministic finite checks of the fixed-benchmark concentration memo.

Rational enumeration establishes the finite identities and exact event probabilities.
Exponential inequalities use floating-point arithmetic on a declared finite grid;
these checks are not a general proof, Monte Carlo, or a study-coverage validation.
No experiment modules, models, validators, or archived data are executed or modified.
"""
from collections import defaultdict
from fractions import Fraction as F
from itertools import combinations, permutations, product
import json
import math
from pathlib import Path


LAMBDAS = (-4, -2, -1, -.5, 0, .5, 1, 2, 4)
THRESHOLDS = tuple(map(F, ("0.1", "0.25", "0.5", "0.75", "1", "1.5")))


def close_le(left, right):
    assert left <= right + 1e-12 * max(1.0, abs(right)), (left, right)


def cs(n, m):
    if m == n:
        return F(0)
    return F(4 * (n - m)**2, m*m) * sum((F(1, j*j) for j in range(n-m, n)), F(0))


def mgf(distribution, lam):
    return math.fsum(float(p) * math.exp(lam * float(x)) for x, p in distribution.items())


def check_mgf_tails(distribution, proxy):
    assert sum(distribution.values()) == 1
    assert sum(x*p for x, p in distribution.items()) == 0
    for lam in LAMBDAS:
        close_le(mgf(distribution, lam), math.exp(lam*lam*float(proxy)/8))
    for t in THRESHOLDS:
        tail = sum(p for x, p in distribution.items() if abs(x) > t)
        bound = 0.0 if not proxy else min(1.0, 2*math.exp(-2*float(t*t/proxy)))
        close_le(float(tail), bound)


def check_selection():
    reports = []
    for values in ((F(-1), F(0), F(1)), (F(-1), F(-1, 3), F(1, 2), F(1))):
        n = len(values)
        mu = sum(values)/n
        for m in range(1, n+1):
            orders = list(permutations(range(n), m))
            probability = F(1, len(orders))
            distribution = defaultdict(F)
            n_increments = 0
            for order in orders:
                revealed = []
                previous = mu
                for k, selected in enumerate(order, 1):
                    before = [i for i in range(n) if i not in revealed]
                    mean_before = sum(values[i] for i in before)/len(before)
                    revealed.append(selected)
                    after = [i for i in range(n) if i not in revealed]
                    if k == m:
                        now = sum(values[i] for i in revealed)/m
                    else:
                        now = (sum(values[i] for i in revealed)
                               + (m-k)*sum(values[i] for i in after)/len(after))/m
                    predicted = (F(0) if m == n else
                                 F(n-m, m*(n-k))*(values[selected]-mean_before))
                    assert now-previous == predicted
                    assert abs(predicted) <= (0 if m == n else F(2*(n-m), m*(n-k)))
                    previous = now
                    n_increments += 1
                distribution[previous-mu] += probability
            proxy = cs(n, m)
            check_mgf_tails(distribution, proxy)
            reports.append(dict(n=n, m=m, orders=len(orders), increments=n_increments,
                                range_proxy=str(proxy), mgf_grid=len(LAMBDAS), tail_grid=len(THRESHOLDS)))
    return reports


def check_selection_plus_pair_noise():
    # Within each fresh pair, outcomes are perfectly anticorrelated: (1,0) or (0,1).
    # All pairs are independent given the sample. Thus the weaker pair-noise constant applies.
    p_positive = (F(1, 4), F(1, 2), F(3, 4))
    latent = tuple(2*p-1 for p in p_positive)
    n, m, r = 3, 2, 2
    mu = sum(latent)/n
    subsets = list(combinations(range(n), m))
    joint = defaultdict(F)
    conditional_checks = 0
    enumerated_rows = 0
    for sample in subsets:
        sampled_mean = sum(latent[i] for i in sample)/m
        conditional = defaultdict(F)
        draw_prefix = [i for i in sample for _ in range(r)]
        for bits in product((0, 1), repeat=m*r):
            probability = F(1)
            for i, bit in zip(draw_prefix, bits):
                probability *= p_positive[i] if bit else 1-p_positive[i]
            bhat = F(sum(2*b-1 for b in bits), m*r)
            conditional[bhat-sampled_mean] += probability
            joint[bhat-mu] += probability/len(subsets)
            enumerated_rows += 1
        check_mgf_tails(conditional, F(4, m*r))
        conditional_checks += 1
    total_proxy = cs(n, m)+F(4, m*r)
    check_mgf_tails(joint, total_proxy)
    # Exact independent check of the full finite-frame variance decomposition.
    variance = sum(x*x*p for x, p in joint.items())
    sd2 = sum((d-mu)**2 for d in latent)/(n-1)
    mean_pair_variance = sum(1-d*d for d in latent)/n
    assert variance == (1-F(m, n))*sd2/m + mean_pair_variance/(m*r)
    return dict(enumerated_rows=enumerated_rows, samples=conditional_checks,
                mean=str(sum(x*p for x, p in joint.items())), exact_variance=str(variance),
                selection_proxy=str(cs(n, m)), pair_noise_proxy=str(F(4, m*r)),
                combined_proxy=str(total_proxy),
                note="Uses dependent outcomes within each pair; does not assume independent arms.")


def source_radius(j, cap, denominator, alpha, arm=False):
    if arm:
        return 4*cap*math.sqrt(j/2*math.log(2/alpha))/denominator
    return cap*math.sqrt(2*j*math.log(2/alpha))/denominator


def check_zero_source_blocks():
    # Payload order M,T,U1,D1,U0,D0. Nonidentical independent tasks, R=2.
    # Task0 is always zero. Task1 is eligible with probability1/2, d=1,
    # and its one randomized remaining action succeeds iff large.
    # Task2 has two eligible d=0 prefixes with probability1/4; outcomes are0.
    # Its assignments are perfectly coupled within task, but marginally balanced.
    z = (F(0),)*6
    blocks = [
        [(F(1), z)],
        [(F(1, 2), z), (F(1, 4), (1, 1, 2, 2, 0, 0)),
         (F(1, 4), (1, 1, 0, 0, 0, 2))],
        [(F(3, 4), z), (F(1, 8), (2, 0, 0, 4, 0, 0)),
         (F(1, 8), (2, 0, 0, 0, 0, 4))],
    ]
    frames = []
    expectation = [F(0)]*6
    for realization in product(*blocks):
        probability = math.prod(p for p, _ in realization)
        total = tuple(sum(F(row[k]) for _, row in realization) for k in range(6))
        assert all(abs(row[1]) <= row[0] <= 2 and 0 <= row[2] <= row[3] <= 8
                   and 0 <= row[4] <= row[5] <= 8 for _, row in realization)
        frames.append((probability, total, realization))
        expectation = [e+probability*v for e, v in zip(expectation, total)]
    theta = expectation[1]/expectation[0]
    nu1, nu0 = expectation[2]/expectation[3], expectation[4]/expectation[5]
    delta = theta-nu1+nu0
    nonempty = sum(p for p, total, _ in frames if total[0])
    expected_ratio = sum(p*total[1]/total[0] for p, total, _ in frames if total[0])/nonempty
    assert theta == F(1, 2) and expected_ratio == F(2, 3) and delta == 0
    assert nonempty == F(5, 8)

    fallback_mass = F(0)
    covered_mass = F(0)
    j, cap, component_alpha = 3, 2, .05/4
    source_event_violations = [F(0)]*3
    for p, total, realization in frames:
        n, t, u1, d1, u0, d0 = total
        # Check each per-task centered range and exact cancellation of the summed mean.
        for _, row in realization:
            mm, tt, uu1, dd1, uu0, dd0 = map(F, row)
            assert -cap*(1+theta) <= tt-theta*mm <= cap*(1-theta)
            for nu, uu, dd in ((nu1, uu1, dd1), (nu0, uu0, dd0)):
                assert -4*cap*nu <= uu-nu*dd <= 4*cap*(1-nu)
        if n and abs(float(t/n-theta)) > source_radius(j, cap, n, component_alpha):
            source_event_violations[0] += p
        for a, uu, dd, nu in ((1, u1, d1, nu1), (2, u0, d0, nu0)):
            if dd and abs(float(uu/dd-nu)) > source_radius(j, cap, dd, component_alpha, arm=True):
                source_event_violations[a] += p
        if not n or not d1 or not d0:
            fallback_mass += p
            covered_mass += p  # Explicit whole-range [-2,2] convention, not exclusion.
            continue
        latent = [F(1)]*int(realization[1][1][0]) + [F(0)]*int(realization[2][1][0])
        m = min(2, len(latent))
        samples = list(combinations(range(len(latent)), m))
        for sample in samples:
            bhat = sum(latent[i] for i in sample)/m  # Fresh contrasts are degenerate/noiseless here.
            point = float(bhat-u1/d1+u0/d0)
            radius = (source_radius(j, cap, n, component_alpha)
                      + source_radius(j, cap, d1, component_alpha, arm=True)
                      + source_radius(j, cap, d0, component_alpha, arm=True)
                      + math.sqrt(float(cs(int(n), m)+F(4, m*2))/2*math.log(2/component_alpha)))
            low, high = max(-2, point-radius), min(2, point+radius)
            if low <= delta <= high:
                covered_mass += p/len(samples)
    assert fallback_mass == F(15, 16)
    assert covered_mass >= F(95, 100)
    assert all(float(p) <= component_alpha for p in source_event_violations)
    return dict(source_frames=len(frames), expected_totals=list(map(str, expectation)),
                theta=str(theta), expected_realized_ratio_given_nonempty=str(expected_ratio),
                probability_nonempty=str(nonempty), true_gap=str(delta),
                zero_global_denominator_fallback_mass=str(fallback_mass),
                exact_unconditional_coverage=str(covered_mass),
                component_violation_probabilities=list(map(str, source_event_violations)),
                note="Small example's full set is conservative/vacuous; this is not evidence of sharpness.")


def check_nonzero_source_tails():
    # One identically-zero task plus12 independent signed-prefix tasks. This makes
    # the blocks nonidentical while producing nonzero extreme-event probabilities.
    j, cap, active = 13, 1, 12
    theta = F(0)
    sums = defaultdict(F)
    for signs in product((-1, 1), repeat=active):
        sums[F(sum(signs))] += F(1, 2**active)
    assert sum(s*p for s, p in sums.items()) == theta
    out = []
    for alpha in (.2, .1, .05, .01):
        gamma = cap*math.sqrt(2*j*math.log(2/alpha))
        probability = sum(p for s, p in sums.items() if abs(s) > gamma)
        assert 0 < probability <= alpha
        out.append(dict(alpha=alpha, total_threshold=gamma,
                        exact_violation_probability=str(probability)))
    return out


def actual_constants():
    j, cap, n, m, r, d1, d0 = 330, 8, 564, 200, 2, 570, 574
    alpha, component = .05, .05/4
    selection = float(cs(n, m))
    pair_noise, independent_arms = 4/(m*r), 2/(m*r)
    b_b = source_radius(j, cap, n, component)
    b_1 = source_radius(j, cap, d1, component, arm=True)
    b_0 = source_radius(j, cap, d0, component, arm=True)
    b_f = math.sqrt((selection+pair_noise)/2*math.log(2/component))
    point = F(12, 100)-(F(184, 570)-F(108, 574))
    conditional = math.sqrt((selection+pair_noise)/2*math.log(2/alpha))
    conditional_ind = math.sqrt((selection+independent_arms)/2*math.log(2/alpha))
    full = b_b+b_1+b_0+b_f
    assert full > 4 and abs(float(point)+.014653707439330033) < 1e-15
    assert abs(selection-.012937008479984692) < 1e-15
    assert abs(full-4.300040248129188) < 1e-12
    assert abs(conditional-.20568405300442308) < 1e-12
    assert abs(conditional_ind-.18188933730442114) < 1e-12
    return dict(j=j, per_task_cap=cap, n=n, m=m, replicate_pairs=r,
                alpha=alpha, component_alpha=component, selection_proxy=selection,
                independent_pair_noise_proxy=pair_noise, independent_arm_noise_proxy=independent_arms,
                source_branch_radius=b_b, source_large_radius=b_1, source_small_radius=b_0,
                conditional_branch_radius_in_union=b_f, full_radius=full,
                clipped_full_interval=[-2, 2], point=float(point),
                conditional_frame_radius_pair_independence=conditional,
                conditional_frame_radius_arm_independence=conditional_ind,
                note="Widths under stated assumptions only; execution assumptions not verified for archive.")


def main():
    report = dict(
        status="Deterministic finite identity/inequality checks; not a proof of arbitrary-case coverage.",
        selection=check_selection(),
        selection_plus_pair_noise=check_selection_plus_pair_noise(),
        nonidentical_zero_blocks=check_zero_source_blocks(),
        nonzero_source_tail_probabilities=check_nonzero_source_tails(),
        actual_constants=actual_constants(),
    )
    output = Path(__file__).with_suffix(".json")
    output.write_text(json.dumps(report, indent=2)+"\n")
    print(json.dumps({"status": "all deterministic checks passed", "output": str(output),
                      "source_ratio": report["nonidentical_zero_blocks"]["theta"],
                      "expected_realized_ratio": report["nonidentical_zero_blocks"]["expected_realized_ratio_given_nonempty"],
                      "full_radius": report["actual_constants"]["full_radius"]}, indent=2))


if __name__ == "__main__":
    main()
