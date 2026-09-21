"""DTR-REQ-003 item 3: archive-matching branch module on the accepted repair kernels. Exact; no Monte Carlo.

Distinct from the common-initial-small adaptation model. Per task g and repetition (theory_branch_fixed_benchmark_bound.md,
sections 1-2):
  R = 8 source episodes; the INITIAL action A0 is a permuted block of exactly 4 small and 4 large.
  Initial-action kernel (PROPOSED here, for the lead): the first call by model A0 is correct w.p. P0A[S][A0]; if it is
  incorrect, U0 ~ Bern(DEEP0[S]) as in the accepted tables (independent of A0: a stated modeling choice), and feedback
  O0 ~ obs(U0, S). A first-failure PREFIX exists iff O0 is not a pass; M_g counts them (0..8).
  Source continuation: up to K = 2 repairs, each assigned large w.p. 1/2 (known), stopping at the first visible pass.
  Branch: at each prefix, fresh stay-a continuations (A1 = A2 = a) from the restored latent state; d_i is their mean
  success difference, T_g = sum_i d_i.
Targets (bound doc eq. 2):  theta = sum_g E T_g / sum_g E M_g;  nu_a = sum_g E U_ga / sum_g E D_ga;  Delta = theta - nu_1 + nu_0.
Under a calibrated restored-execution law Delta = 0 exactly; a drifted restored law is the positive control.

Frame handling, fixed BEFORE execution (no complete-case deletion, no target substitution):
  zero-prefix tasks stay in every sum with zero contributions;
  N = sum_g M_g; m = min(200, N): SRSWOR when N > 200, a census when 0 < N <= 200;
  N = 0, or an observed arm denominator D_a = 0  ->  report the whole parameter range [-2, 2] for Delta.
Exact support probabilities of those events are computed below for the frozen task lists (fixed_task_blocks).
Output: experiments/v2_sim/branch_module_v1.json
"""
from __future__ import annotations
import itertools, json, math
from fractions import Fraction as Fr
from pathlib import Path

import repair_generator as G

OUT = Path(__file__).resolve().parent / 'branch_module_v1.json'
R_EPISODES, ALLOC, K_BRANCH, M_MAX, REPLICATES = 8, {0: 4, 1: 4}, 2, 200, 2
P0A = {0: {0: Fr('0.6'), 1: Fr('0.7')}, 1: {0: Fr('0.2'), 1: Fr('0.35')}}      # PROPOSED: [S][A0]
DRIFT = Fr('0.9')          # positive control: restored continuations repair with probability scaled by .9


def stay_value(cell, s, u, a, scale=Fr(1)):
    """E[Y] of the stay-a continuation (up to K_BRANCH repairs) from an incorrect candidate of latent type u."""
    def rec(t, u):
        ok = cell.repair[u, a] * scale
        v = ok
        if t < K_BRANCH:
            for u2 in (0, 1):
                pu = cell.stay[u, a] if u2 else 1 - cell.stay[u, a]
                for o in ('exc', 'asr'):
                    v += (1 - ok) * pu * cell.p_obs(o, u2, s) * rec(t + 1, u2)
        return v
    return rec(1, u)


def log_weighted(cell, s, u):
    """Exact E[W_a Y | prefix] and E[W_a | prefix] under the 1/2 source logger, for a in {0, 1}."""
    out = {a: dict(wy=Fr(0), w=Fr(0)) for a in (0, 1)}
    for a1 in (0, 1):
        ok1 = cell.repair[u, a1]
        for a in (0, 1):                                     # repaired after one call: absorbed, W = 1{A1=a}/.5
            w = Fr(2) if a1 == a else Fr(0)
            out[a]['wy'] += Fr(1, 2) * ok1 * w; out[a]['w'] += Fr(1, 2) * ok1 * w
        for u2 in (0, 1):
            pu = cell.stay[u, a1] if u2 else 1 - cell.stay[u, a1]
            for o in G.OBS:
                p = Fr(1, 2) * (1 - ok1) * pu * cell.p_obs(o, u2, s)
                if o == 'pass':                              # false pass after the first repair: absorbed, Y = 0
                    for a in (0, 1):
                        out[a]['w'] += p * (Fr(2) if a1 == a else 0)
                    continue
                for a2 in (0, 1):                            # second repair eligible
                    ok2 = cell.repair[u2, a2]
                    for a in (0, 1):
                        w = Fr(4) if (a1 == a and a2 == a) else Fr(0)
                        out[a]['wy'] += p * Fr(1, 2) * ok2 * w; out[a]['w'] += p * Fr(1, 2) * w
    return out


def per_episode(cell, s, a0, scale):
    """Exact per-episode expectations: P(prefix), E[d 1{prefix}], E[W_a Y 1{prefix}], E[W_a 1{prefix}], P(W_a = 0 | ...)."""
    r = dict(M=Fr(0), T=Fr(0), U={0: Fr(0), 1: Fr(0)}, D={0: Fr(0), 1: Fr(0)})
    for u0 in (0, 1):
        for o0 in ('exc', 'asr'):
            p = (1 - P0A[s][a0]) * (G.DEEP0[s] if u0 else 1 - G.DEEP0[s]) * cell.p_obs(o0, u0, s)
            r['M'] += p
            r['T'] += p * (stay_value(cell, s, u0, 1, scale) - stay_value(cell, s, u0, 0, scale))
            lw = log_weighted(cell, s, u0)
            for a in (0, 1):
                r['U'][a] += p * lw[a]['wy']; r['D'][a] += p * lw[a]['w']
    return r


def p_no_arm_weight(cell, s, a0, a):
    """P(this episode contributes zero weight to arm a): no prefix, or a prefix whose logged actions miss arm a."""
    q = 1 - sum((1 - P0A[s][a0]) * (G.DEEP0[s] if u0 else 1 - G.DEEP0[s]) * cell.p_obs(o0, u0, s)
                for u0 in (0, 1) for o0 in ('exc', 'asr'))
    for u0 in (0, 1):
        for o0 in ('exc', 'asr'):
            p = (1 - P0A[s][a0]) * (G.DEEP0[s] if u0 else 1 - G.DEEP0[s]) * cell.p_obs(o0, u0, s)
            miss = Fr(1, 2)                                      # A1 != a
            ok1 = cell.repair[u0, a]
            p_second = sum((cell.stay[u0, a] if u2 else 1 - cell.stay[u0, a]) * (1 - ok1) * (1 - G.FALSE_PASS[s])
                           for u2 in (0, 1))
            miss += Fr(1, 2) * p_second * Fr(1, 2)               # A1 = a, second repair eligible, A2 != a
            q += p * miss
    return q


def frame_rule(N, D_small, D_large, m_max=M_MAX):
    """Frame handling fixed before execution: returns (action, m). No deletion, no substitute target."""
    if N == 0 or D_small == 0 or D_large == 0:
        return 'whole_range_[-2,2]', 0
    if N <= m_max:
        return 'census', N
    return 'srswor', m_max


def float_binom_pmf(n, p):
    lg = math.lgamma
    return [math.exp(lg(n + 1) - lg(k + 1) - lg(n - k + 1) + k * math.log(p) + (n - k) * math.log1p(-p)) for k in range(n + 1)]


def float_convolve(x, y):
    out = [0.0] * (len(x) + len(y) - 1)
    for i, a in enumerate(x):
        if a > 1e-300:
            for j, b in enumerate(y):
                out[i + j] += a * b
    return out


def build():
    rows = []
    for crossing, feedback in itertools.product(('no_crossing', 'crossing'), tuple(G.KAPPA)):
        cell = G.Cell(K_BRANCH, crossing, feedback)
        for law, scale in (('calibrated', Fr(1)), ('drifted_restoration_positive_control', DRIFT)):
            ep = {(s, a0): per_episode(cell, s, a0, scale) for s in (0, 1) for a0 in (0, 1)}
            task = {s: {k: sum(ALLOC[a0] * ep[s, a0][k] for a0 in (0, 1)) for k in ('M', 'T')} for s in (0, 1)}
            for s in (0, 1):
                for k in ('U', 'D'):
                    task[s][k] = {a: sum(ALLOC[a0] * ep[s, a0][k][a] for a0 in (0, 1)) for a in (0, 1)}
            for n in (250, 1000):
                ns = {0: n // 2, 1: n // 2}
                EM = sum(ns[s] * task[s]['M'] for s in (0, 1)); ET = sum(ns[s] * task[s]['T'] for s in (0, 1))
                EU = {a: sum(ns[s] * task[s]['U'][a] for s in (0, 1)) for a in (0, 1)}
                ED = {a: sum(ns[s] * task[s]['D'][a] for s in (0, 1)) for a in (0, 1)}
                theta, nu = ET / EM, {a: EU[a] / ED[a] for a in (0, 1)}
                row = dict(action_effect=crossing, feedback=feedback, restored_law=law, n=n,
                           theta=str(theta), theta_decimal=float(theta),
                           nu_large=str(nu[1]), nu_small=str(nu[0]), Delta=str(theta - nu[1] + nu[0]),
                           Delta_decimal=float(theta - nu[1] + nu[0]),
                           expected_weight_equals_expected_prefixes=all(ED[a] == EM for a in (0, 1)),
                           E_N=str(EM), E_N_decimal=float(EM))
                if law == 'calibrated':
                    # frame-support probabilities: N is a sum of four independent binomials (stratum x initial arm).
                    # P(N = 0) and E[N] are exact; P(N <= 200) is a float log-gamma convolution (NOT exact arithmetic).
                    p_zero = Fr(1)
                    for s in (0, 1):
                        for a0 in (0, 1):
                            p_zero *= (1 - ep[s, a0]['M']) ** (ns[s] * ALLOC[a0])
                    pmf = [1.0]
                    for s in (0, 1):
                        for a0 in (0, 1):
                            pmf = float_convolve(pmf, float_binom_pmf(ns[s] * ALLOC[a0], float(ep[s, a0]['M'])))
                    lp = {a: sum(ns[s] * ALLOC[a0] * math.log(float(p_no_arm_weight(cell, s, a0, a)))
                                 for s in (0, 1) for a0 in (0, 1)) for a in (0, 1)}
                    row.update(P_N_zero_exact_log10=float(math.log10(p_zero.numerator) - math.log10(p_zero.denominator)),
                               P_census_N_le_200_float=sum(pmf[:M_MAX + 1]),
                               P_D_arm_zero_log10={('small', 'large')[a]: lp[a] / math.log(10) for a in (0, 1)})
                rows.append(row)
    return dict(
        request='DTR-REQ-003 item 3: archive-matching branch module (accepted repair kernels, K = 2 repairs)',
        status='SPECIFICATION with exact expectations; no Monte Carlo, no model. P0A is a PROPOSED initial-action kernel',
        design=dict(episodes_per_task=R_EPISODES, initial_allocation='permuted block: exactly 4 small, 4 large',
                    repairs=K_BRANCH, source_repair_assignment='large w.p. 1/2 at each eligible repair (known)',
                    prefix='first-failure: the first call is not a visible pass', m='min(200, N) SRSWOR; census if N <= 200',
                    replicate_pairs=REPLICATES, restored_continuations='stay-small and stay-large from the restored latent state'),
        initial_action_kernel={'P0A[S][A0]': {('easy', 'hard')[s]: {('small', 'large')[a]: str(P0A[s][a]) for a in (0, 1)}
                                              for s in (0, 1)},
                               'DEEP0[S] given incorrect': 'unchanged from the accepted tables, independent of A0 (modeling choice)'},
        target='theta = sum_g E T_g / sum_g E M_g (ratio of expected totals over ALL fixed tasks); nu_a = sum E U_ga / sum E D_ga; '
               'Delta = theta - nu_1 + nu_0',
        frame_handling=['zero-prefix tasks retained with zero contributions', 'N > 200: SRSWOR of 200', '0 < N <= 200: census',
                        'N = 0 or observed D_a = 0: whole range [-2, 2] for Delta; no deletion, no substitute target'],
        assumptions=['source blocks independent across tasks; episodes independent within a task given the 4/4 allocation '
                     '(true in this simulator; the bound itself allows within-task dependence)',
                     'selection independent of fresh continuation noise', 'replicate pairs independent across prefixes and replicates',
                     'calibrated rows: restored-execution law equals the source law (Delta = 0); drift rows violate it'],
        rows=rows)


def main():
    rep = build()
    for r in rep['rows']:
        if r['restored_law'] == 'calibrated' and (r['Delta'] != '0' or not r['expected_weight_equals_expected_prefixes']):
            raise SystemExit('calibration identity failed: %s' % r)
    OUT.write_text(json.dumps(rep, indent=1) + '\n')
    for r in rep['rows']:
        print('%-11s %-11s %-38s n=%-4d theta=%.5f Delta=%+.5f E[N]=%.1f %s' % (
            r['action_effect'], r['feedback'], r['restored_law'], r['n'], r['theta_decimal'], r['Delta_decimal'],
            r['E_N_decimal'], ('P(N<=200)=%.3g log10P(N=0)=%.1f log10P(D_a=0)=%s' % (r['P_census_N_le_200_float'], r['P_N_zero_exact_log10'],
            {k: round(v, 1) for k, v in r['P_D_arm_zero_log10'].items()})) if 'P_N_zero_exact_log10' in r else ''))


if __name__ == '__main__':
    main()
