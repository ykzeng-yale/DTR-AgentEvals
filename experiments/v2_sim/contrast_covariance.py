"""DTR-REQ-003: exact shared-log score covariances for policy contrasts (lead request dd898b5). No Monte Carlo.

One logged episode yields a trajectory-IPW utility score for EVERY frozen policy, X_pi = W_pi Z with
W_pi = prod_t 1{A_t = pi_t(h_t)} / P_logger(A_t | h_t) and Z = success - total cost. Scores of different policies
computed from the same log are dependent; a contrast estimator must use their covariance.

For each core kernel cell (K x crossing x feedback) and core logger, per stratum S, this enumerates every logger branch
once and accumulates exactly:
    E[X_i], E[X_i X_j]            -> covariance matrix Sigma_S of (history rule, catalog prompt rule,
                                     best stratum-specific schedule, best fixed schedule);
    E[(X_hist - X_other)^2]       -> the DIRECT contrast second moment, accumulated separately.
Acceptance (lead): direct second moment = Sigma_ii + Sigma_jj - 2 Sigma_ij + (V_i - V_j)^2 exactly; the identical-
policy contrast has zero variance; Sigma_S is positive semidefinite (all principal minors >= 0, exact).
Fixed-benchmark contrast variance with r = 4 (accepted) and frozen 50/50 lists: n^-2 sum_g Var_{S_g}(X_i - X_j) / r.
This is a moment calculation for the synthetic design; it is not a power or coverage claim for any real contrast.
Output: experiments/v2_sim/contrast_covariance_v1.json
"""
from __future__ import annotations
import itertools, json
from fractions import Fraction as Fr
from pathlib import Path

import repair_generator as G
import repair_logger as L

OUT = Path(__file__).resolve().parent / 'contrast_covariance_v1.json'
R_BLOCK = 4
CORE_LOGGERS = ('uniform_floor_0.5', 'feedback_dependent_floor_0.2')
HIST, PROMPT = 'history_large_after_exception', 'prompt_only_large_if_hard'
# NOTE: HIST is the frozen catalog history RULE, not the belief-DP optimum (which is outside the catalog); contrasts
# involving it can be negative. PROMPT is the single catalog rule; the stratum-specific best schedule is separate.


def moments(pols, cell, s, logger):
    """Exact first and second moments of the per-episode IPW utility scores of all policies on one shared log."""
    k = len(pols)
    m1 = [Fr(0)] * k
    m2 = [[Fr(0)] * k for _ in range(k)]
    direct = {j: Fr(0) for j in range(1, k)}               # E[(X_0 - X_j)^2], accumulated independently

    def terminal(pr, ws, cost, y):
        z = y - cost
        x = [w * z for w in ws]
        for i in range(k):
            m1[i] += pr * x[i]
            for j in range(k):
                m2[i][j] += pr * x[i] * x[j]
        for j in direct:
            direct[j] += pr * (x[0] - x[j]) ** 2

    terminal(G.P0[s], [Fr(1)] * k, G.C[0], 1)

    def rec(t, u, keys, last_o, pr, ws, cost):
        p1 = logger(s, t, last_o)
        for a in (0, 1):
            pa = p1 if a else 1 - p1
            if pa == 0:
                continue
            ws2 = [w / pa if (w and pol.act(s, t, key) == a) else Fr(0) for pol, key, w in zip(pols, keys, ws)]
            if not any(ws2):
                continue                                    # every score is zero on this branch
            pr2, cost2 = pr * pa, cost + G.C[a]
            terminal(pr2 * cell.repair[u, a], ws2, cost2, 1)
            for u2 in (0, 1):
                pu = cell.stay[u, a] if u2 else 1 - cell.stay[u, a]
                for o in G.OBS:
                    p = pr2 * (1 - cell.repair[u, a]) * pu * cell.p_obs(o, u2, s)
                    if not p:
                        continue
                    if o == 'pass' or t == cell.K:
                        terminal(p, ws2, cost2, 0)
                    else:
                        rec(t + 1, u2, [pol.update(key, a, o, None) for pol, key in zip(pols, keys)], o, p, ws2, cost2)

    for u0 in (0, 1):
        pu0 = (1 - G.P0[s]) * (G.DEEP0[s] if u0 else 1 - G.DEEP0[s])
        for o0 in G.OBS:
            p = pu0 * cell.p_obs(o0, u0, s)
            if o0 == 'pass':
                terminal(p, [Fr(1)] * k, G.C[0], 0)
            elif p:
                rec(1, u0, [pol.init_key(s, o0, None) for pol in pols], o0, p, [Fr(1)] * k, G.C[0])
    return m1, m2, direct


def principal_minors_nonnegative(S):
    k = len(S)
    for size in range(1, k + 1):
        for idx in itertools.combinations(range(k), size):
            sub = [[S[i][j] for j in idx] for i in idx]
            if det(sub) < 0:
                return False
    return True


def det(M):
    if len(M) == 1:
        return M[0][0]
    return sum((-1) ** c * M[0][c] * det([row[:c] + row[c + 1:] for row in M[1:]]) for c in range(len(M)))


def s_(x):
    return dict(exact=str(x), decimal=float(x))


def build():
    kernel = json.loads(G.OUT.read_text())
    rows = []
    for K, crossing, feedback in itertools.product((2, 4), ('no_crossing', 'crossing'), tuple(G.KAPPA)):
        cell = G.Cell(K, crossing, feedback)
        kc = next(c for c in kernel['cells'] if (c['K'], c['action_effect'], c['feedback']) == (K, crossing, feedback))
        best_fixed = kc['best_fixed']['policy']
        cat = {p.name: p for p in G.catalog(K)}
        # best prompt-only as the lead defined it: the best fixed schedule chosen separately per stratum
        fixed = [n for n in kc['policies'] if n.startswith('fixed_')]
        best_s = {s: max(fixed, key=lambda n: (Fr(kc['policies'][n]['by_stratum'][('easy', 'hard')[s]]['utility']), n))
                  for s in (0, 1)}
        seqs = {s: [1 if ch == 'L' else 0 for ch in best_s[s][len('fixed_'):]] for s in (0, 1)}
        cat['best_prompt_only_stratum_schedule'] = G.Policy('best_prompt_only_stratum_schedule',
                                                            lambda s, t, key, q=seqs: q[s][t - 1])
        names = [HIST, PROMPT, 'best_prompt_only_stratum_schedule', best_fixed, HIST]   # last: identical-policy control
        pols = [cat[n] for n in names]
        for lname in CORE_LOGGERS:
            per = {}
            for s in (0, 1):
                m1, m2, direct = moments(pols, cell, s, L.LOGGERS[lname])
                sig = [[m2[i][j] - m1[i] * m1[j] for j in range(5)] for i in range(5)]
                truth = [G.enumerate_value(p, cell, s)[0] for p in pols]
                if any(m1[i] != truth[i]['success'] - truth[i]['cost'] for i in range(5)):
                    raise AssertionError('IPW means differ from truth')
                checks = {j: direct[j] == sig[0][0] + sig[j][j] - 2 * sig[0][j] + (m1[0] - m1[j]) ** 2 for j in (1, 2, 3, 4)}
                per[s] = dict(m1=m1, sig=sig, direct=direct, formula_matches=checks,
                              psd=principal_minors_nonnegative([r[:4] for r in sig[:4]]))
            for j, label in ((1, 'history_rule_minus_catalog_prompt_rule'),
                             (2, 'history_rule_minus_best_prompt_only_stratum_schedule:%s/%s' % (best_s[0], best_s[1])),
                             (3, 'history_rule_minus_best_fixed:' + best_fixed), (4, 'history_minus_itself_control')):
                var_s = {s: per[s]['sig'][0][0] + per[s]['sig'][j][j] - 2 * per[s]['sig'][0][j] for s in (0, 1)}
                indep_s = {s: per[s]['sig'][0][0] + per[s]['sig'][j][j] for s in (0, 1)}
                contrast = G.mix(lambda s: per[s]['m1'][0] - per[s]['m1'][j])
                out = dict(K=K, action_effect=crossing, feedback=feedback, logger=lname, contrast=label,
                           true_contrast=s_(contrast),
                           per_episode_contrast_variance={('easy', 'hard')[s]: s_(var_s[s]) for s in (0, 1)},
                           direct_second_moment_matches_formula=all(per[s]['formula_matches'][j] for s in (0, 1)),
                           covariance_psd=all(per[s]['psd'] for s in (0, 1)))
                for n in (250, 1000):
                    v = (var_s[0] + var_s[1]) / (2 * R_BLOCK * n)          # n^-2 * (n/2)(var_e + var_h) / r
                    vi = (indep_s[0] + indep_s[1]) / (2 * R_BLOCK * n)
                    out['n%d' % n] = dict(exact_var=s_(v), exact_se=float(v) ** .5,
                                          se_if_scores_were_independent=float(vi) ** .5,
                                          shared_log_se_ratio=(float(v) / float(vi)) ** .5 if vi else None)
                rows.append(out)
    checks = dict(
        direct_moment_matches_covariance_formula=all(r['direct_second_moment_matches_formula'] for r in rows),
        covariance_psd_everywhere=all(r['covariance_psd'] for r in rows),
        identical_policy_contrast_zero=all(Fr(r['per_episode_contrast_variance'][k]['exact']) == 0 and
                                           Fr(r['true_contrast']['exact']) == 0
                                           for r in rows if r['contrast'] == 'history_minus_itself_control' for k in ('easy', 'hard')))
    return dict(
        request='DTR-REQ-003: exact shared-log score covariances (lead request dd898b5)',
        status='EXACT moments; no Monte Carlo, no model; not a power or coverage claim',
        estimator='per-episode trajectory-IPW utility scores of all policies computed from the SAME logged episode',
        comparators='history_large_after_exception (catalog history rule, NOT the belief-DP optimum) versus: the catalog '
                    'prompt rule; the best prompt-only stratum-specific schedule (lead definition); the best fixed schedule; '
                    'itself (identical-policy control)',
        block='r = %d logged episodes per task (accepted); frozen 50/50 task lists n = 250, 1000' % R_BLOCK,
        checks=checks, rows=rows)


def main():
    rep = build()
    if not all(rep['checks'].values()):
        raise SystemExit('covariance checks failed: %s' % rep['checks'])
    OUT.write_text(json.dumps(rep, indent=1) + '\n')
    print(rep['checks'])
    for r in rep['rows']:
        if r['K'] == 2 and r['contrast'] != 'history_minus_itself_control':
            print('%-11s %-11s %-29s %-38s C=%+.4f se250=%.4f indep=%.4f ratio=%.3f' % (
                r['action_effect'], r['feedback'], r['logger'], r['contrast'][:38], r['true_contrast']['decimal'],
                r['n250']['exact_se'], r['n250']['se_if_scores_were_independent'], r['n250']['shared_log_se_ratio']))


if __name__ == '__main__':
    main()
