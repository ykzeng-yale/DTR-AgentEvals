"""DTR-REQ-003 open gate: independent fresh on-policy reference uncertainty (gate table, "worker computes"). Exact.

A fresh reference executes the frozen policy itself in SEPARATE, independent blocks (no logger, weight 1). For each core
kernel cell and compared policy this computes, per stratum, the exact on-policy per-episode utility variance
    tau^2(S) = E_pi[Z^2] - V_pi(S)^2,  Z = success - total cost,
two ways that must agree exactly: a direct latent-path enumeration under the policy, and the trajectory-IPW second moment
under a DEGENERATE logger that copies the policy (weights identically 1). Fixed-benchmark SE of the fresh mean with
r_fresh episodes per task over the frozen 50/50 lists: sqrt( n^-2 sum_g tau^2(S_g) / r_fresh ).
It also reports the calibration discrepancy (IPW log estimate minus fresh estimate) SE when the log blocks (r = 4,
accepted) and the fresh blocks are independent: sqrt(Var_IPW + Var_fresh).
r_fresh = 4 is a PROPOSAL; the lead specifies the fresh-reference design. Moment calculation only: no power or coverage claim.
Output: experiments/v2_sim/fresh_reference_v1.json
"""
from __future__ import annotations
import itertools, json
from fractions import Fraction as Fr
from pathlib import Path

import fixed_task_blocks as B
import repair_generator as G
import repair_logger as L

OUT = Path(__file__).resolve().parent / 'fresh_reference_v1.json'
R_LOG, R_FRESH = 4, 4
POLICIES = ('history_large_after_exception', 'prompt_only_large_if_hard')


def on_policy_moments(pol, cell, s):
    """Direct enumeration of E[Z], E[Z^2] under the policy itself (latent paths, no logger, no weights)."""
    m = [Fr(0), Fr(0)]

    def term(pr, cost, y):
        z = y - cost
        m[0] += pr * z; m[1] += pr * z * z

    term(G.P0[s], G.C[0], 1)

    def rec(t, u, key, pr, cost):
        a = pol.act(s, t, key)
        cost += G.C[a]
        term(pr * cell.repair[u, a], cost, 1)
        for u2 in (0, 1):
            pu = cell.stay[u, a] if u2 else 1 - cell.stay[u, a]
            for o in G.OBS:
                p = pr * (1 - cell.repair[u, a]) * pu * cell.p_obs(o, u2, s)
                if not p:
                    continue
                if o == 'pass' or t == cell.K:
                    term(p, cost, 0)
                else:
                    rec(t + 1, u2, pol.update(key, a, o, None), p, cost)

    for u0 in (0, 1):
        for o0 in G.OBS:
            p = (1 - G.P0[s]) * (G.DEEP0[s] if u0 else 1 - G.DEEP0[s]) * cell.p_obs(o0, u0, s)
            if o0 == 'pass':
                term(p, G.C[0], 0)
            elif p:
                rec(1, u0, pol.init_key(s, o0, None), p, G.C[0])
    return m


def copying_logger(pol):
    """A logger that takes the policy's action with probability 1 (valid for policies keyed by last feedback or none)."""
    return lambda s, t, o: Fr(pol.act(s, t, o))


def s_(x):
    return dict(exact=str(x), decimal=float(x))


def build():
    kernel = json.loads(G.OUT.read_text())
    rows = []
    for K, crossing, feedback in itertools.product((2, 4), ('no_crossing', 'crossing'), tuple(G.KAPPA)):
        cell = G.Cell(K, crossing, feedback)
        kc = next(c for c in kernel['cells'] if (c['K'], c['action_effect'], c['feedback']) == (K, crossing, feedback))
        cat = {p.name: p for p in G.catalog(K)}
        for pname in POLICIES + (kc['best_fixed']['policy'],):
            pol = cat[pname]
            tau2, agree, V = {}, True, {}
            for s in (0, 1):
                m1, m2 = on_policy_moments(pol, cell, s)
                c1, c2 = B.ipw_moments(pol, cell, s, copying_logger(pol))
                agree &= (m1, m2) == (c1, c2)
                truth = G.enumerate_value(pol, cell, s)[0]
                if m1 != truth['success'] - truth['cost']:
                    raise AssertionError('on-policy mean differs from truth')
                V[s], tau2[s] = m1, m2 - m1 * m1
            row = dict(K=K, action_effect=crossing, feedback=feedback, policy=pname,
                       value=s_(G.mix(lambda s: V[s])), both_paths_agree_exactly=agree,
                       on_policy_per_episode_variance={('easy', 'hard')[s]: s_(tau2[s]) for s in (0, 1)})
            for lname in B.CORE_LOGGERS:
                ipw_var = {}
                for s in (0, 1):
                    a1, a2 = B.ipw_moments(pol, cell, s, L.LOGGERS[lname])
                    ipw_var[s] = a2 - a1 * a1
                row['ipw_to_on_policy_variance_ratio_' + lname] = {
                    ('easy', 'hard')[s]: float(ipw_var[s] / tau2[s]) for s in (0, 1)}
                for n in B.NS:
                    vf = (tau2[0] + tau2[1]) / (2 * R_FRESH * n)
                    vl = (ipw_var[0] + ipw_var[1]) / (2 * R_LOG * n)
                    row.setdefault('n%d' % n, {})['fresh_se'] = float(vf) ** .5
                    row['n%d' % n]['calibration_discrepancy_se_' + lname] = float(vl + vf) ** .5
            rows.append(row)
    return dict(
        request='DTR-REQ-003 open gate: independent fresh on-policy reference uncertainty',
        status='EXACT moments; no Monte Carlo, no model; r_fresh = %d is a proposal; not a power or coverage claim' % R_FRESH,
        design='fresh blocks: r_fresh on-policy episodes per task per policy, independent of the r = %d logged episodes' % R_LOG,
        checks=dict(both_paths_agree_exactly=all(r['both_paths_agree_exactly'] for r in rows)),
        rows=rows)


def main():
    rep = build()
    if not rep['checks']['both_paths_agree_exactly']:
        raise SystemExit('on-policy moment paths disagree')
    OUT.write_text(json.dumps(rep, indent=1) + '\n')
    fs = [r['n250']['fresh_se'] for r in rep['rows']]
    rat = [v for r in rep['rows'] for k, d in r.items() if k.startswith('ipw_to_on_policy') for v in d.values()]
    print('rows', len(rep['rows']), '| fresh SE n=250 range %.5f-%.5f' % (min(fs), max(fs)),
          '| IPW/on-policy per-episode variance ratio range %.3f-%.3f' % (min(rat), max(rat)))


if __name__ == '__main__':
    main()
