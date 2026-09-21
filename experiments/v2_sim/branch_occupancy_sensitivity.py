"""DTR-REQ-003: one n = 330 expected-occupancy sensitivity for the branch module (lead decision 7e04762). Exact.

Baseline P0A is retained for the core. This separate sensitivity rescales the first-call FAILURE probabilities,
    P0A_new[S][A0] = 1 - alpha (1 - P0A[S][A0]),   alpha = 940/1969,
on n = 330 fixed tasks (165 easy, 165 hard), so that E[N] = 564, the archive's OBSERVED prefix count. Because the
prefix law given failure is unchanged, every expected total (M, T, U_a, D_a) scales by exactly alpha and every target
ratio (theta, nu_a, Delta) is unchanged; both facts are checked exactly. This matches expected occupancy to one observed
count; it is not the archive's full law or its realized sampling fraction.

Labels (lead, 7e04762): restoration is IDEAL FULL-STATE, including latent U; simulated branch noise is independent
across arms, prefixes and replicates given that full state and separate from source noise. These are simulator
choices; they do not validate historical recovery or feedback-only restoration. A population Delta = 0 does not force
a zero realized-frame gap or unbiased finite-sample ratios.
Small-frame probabilities are 60-digit decimal log10 values (approximations of rational products or sums).
P(N <= 200) is the small-frame probability, not the probability that the census branch is used: the whole-range
fallback (N = 0 or an observed D_a = 0) takes precedence.
Output: experiments/v2_sim/branch_occupancy_sensitivity_v1.json
"""
from __future__ import annotations
import contextlib, json
from decimal import Decimal as D, getcontext
from fractions import Fraction as Fr
from math import comb
from pathlib import Path

import branch_module as B
import repair_generator as G

OUT = Path(__file__).resolve().parent / 'branch_occupancy_sensitivity_v1.json'
ALPHA = Fr(940, 1969)
N_TASKS = 330
NS = {0: N_TASKS // 2, 1: N_TASKS // 2}


@contextlib.contextmanager
def p0a(table):
    saved = B.P0A
    B.P0A = table
    try:
        yield
    finally:
        B.P0A = saved


def totals(cell):
    ep = {(s, a0): B.per_episode(cell, s, a0, Fr(1)) for s in (0, 1) for a0 in (0, 1)}
    tot = dict(M=Fr(0), T=Fr(0), U0=Fr(0), U1=Fr(0), D0=Fr(0), D1=Fr(0))
    for (s, a0), r in ep.items():
        w = NS[s] * B.ALLOC[a0]
        tot['M'] += w * r['M']; tot['T'] += w * r['T']
        for a in (0, 1):
            tot['U%d' % a] += w * r['U'][a]; tot['D%d' % a] += w * r['D'][a]
    return tot, {k: r['M'] for k, r in ep.items()}


def ratios(t):
    theta, nu1, nu0 = t['T'] / t['M'], t['U1'] / t['D1'], t['U0'] / t['D0']
    return dict(theta=theta, nu_large=nu1, nu_small=nu0, Delta=theta - nu1 + nu0)


def log10_small_frame(p_prefix):
    """60-digit log10 of P(N = 0) (exact rational first) and of P(N <= 200) (truncated decimal convolution)."""
    getcontext().prec = 60; getcontext().Emin = -10 ** 7; getcontext().Emax = 10 ** 7
    trials = {(s, a0): NS[s] * B.ALLOC[a0] for s in (0, 1) for a0 in (0, 1)}
    pz = Fr(1)
    for k, t in trials.items():
        pz *= (1 - p_prefix[k]) ** t
    l0 = (D(pz.numerator).ln() - D(pz.denominator).ln()) / D(10).ln()
    pmf = [D(1)]
    for k, t in trials.items():
        pk = D(p_prefix[k].numerator) / D(p_prefix[k].denominator); qk = 1 - pk
        b = [D(comb(t, j)) * pk ** j * qk ** (t - j) for j in range(B.M_MAX + 1)]
        pmf = [sum(pmf[i] * b[j - i] for i in range(max(0, j - len(b) + 1), min(j, len(pmf) - 1) + 1))
               for j in range(B.M_MAX + 1)]
    return float(l0), float(sum(pmf).log10())


def build():
    new = {s: {a0: 1 - ALPHA * (1 - B.P0A[s][a0]) for a0 in (0, 1)} for s in (0, 1)}
    rows = []
    for crossing in ('no_crossing', 'crossing'):
        for feedback in tuple(G.KAPPA):
            cell = G.Cell(B.K_BRANCH, crossing, feedback)
            base, pb = totals(cell)
            with p0a(new):
                sens, ps = totals(cell)
            rb, rs = ratios(base), ratios(sens)
            row = dict(action_effect=crossing, feedback=feedback,
                       E_N_baseline=str(base['M']), E_N_sensitivity=str(sens['M']),
                       totals_scale_by_alpha=all(sens[k] == ALPHA * base[k] for k in base),
                       ratios_unchanged=rb == rs, **{k: str(v) for k, v in rs.items()})
            if crossing == 'no_crossing' and feedback == 'informative':   # prefix law is kernel-independent
                row['log10_P_N0_and_P_N_le_200'] = dict(baseline=log10_small_frame(pb), sensitivity=log10_small_frame(ps))
            rows.append(row)
    return dict(
        request='DTR-REQ-003: n = 330 expected-occupancy sensitivity (lead decision 7e04762); core baseline P0A retained',
        status='EXACT rational totals and ratios; small-frame log10 values are 60-digit approximations; no Monte Carlo',
        alpha=str(ALPHA), n_tasks=N_TASKS, strata=dict(easy=NS[0], hard=NS[1]),
        P0A_baseline={('easy', 'hard')[s]: {('small', 'large')[a]: str(B.P0A[s][a]) for a in (0, 1)} for s in (0, 1)},
        P0A_sensitivity={('easy', 'hard')[s]: {('small', 'large')[a]: str(new[s][a]) for a in (0, 1)} for s in (0, 1)},
        restoration='ideal full-state (including latent U); branch noise independent across arms/prefixes/replicates '
                    'given the full state, separate from source noise. Simulator choice; validates no historical recovery',
        caveats=['matches expected occupancy to one observed count (564), not the archive law or realized sampling fraction',
                 'population Delta = 0 does not force a zero realized-frame gap or unbiased finite-sample ratios',
                 'P(N <= 200) is small-frame probability; the whole-range fallback takes precedence over the census branch'],
        rows=rows)


def main():
    rep = build()
    bad = [r for r in rep['rows'] if not (r['totals_scale_by_alpha'] and r['ratios_unchanged'] and r['E_N_sensitivity'] == '564')]
    if bad:
        raise SystemExit('sensitivity checks failed: %s' % bad)
    OUT.write_text(json.dumps(rep, indent=1) + '\n')
    for r in rep['rows']:
        print(r['action_effect'], r['feedback'], 'E[N]', r['E_N_baseline'], '->', r['E_N_sensitivity'], 'theta', r['theta'][:12],
              r.get('log10_P_N0_and_P_N_le_200', ''))


if __name__ == '__main__':
    main()
