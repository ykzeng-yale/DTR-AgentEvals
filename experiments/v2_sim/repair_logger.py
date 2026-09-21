"""DTR-REQ-003, slice 4: logger layer for the finite repair generator. Exact; no Monte Carlo.

Loggers choose the repair model with KNOWN history-dependent probabilities P(A_t = large | S, t, last feedback).
For each frozen policy the exact expectation of the trajectory IPW estimator,
    E_logger[ Z * prod_t 1{A_t = pi_t(h_t)} / P_logger(A_t | h_t) ],  Z in {success, total cost, utility},
is enumerated over latent paths and logger actions and compared with the logger-free truth from
repair_generator.enumerate_value. The truth functions take no logger argument, so a logger-only change cannot move
the target; the check confirms that IPW recovers it exactly wherever the logger supports the policy.

Support status is reported per component (lead refinement at 4f76701):
  success, utility  UNSUPPORTED if some history the policy reaches gets zero logging probability for its action;
  cost              identified structurally only if every such unsupported action is at the FINAL opportunity
                    (IPW over the earlier, supported steps times the known final-step cost); plain trajectory IPW is
                    still biased there because it drops the unsupported branch. Otherwise later occupancy depends on
                    unlogged repair outcomes, so cost is UNSUPPORTED. In the one-decision control plain IPW happened
                    to match only because the missing action's cost was zero.
Negative controls: a zero-support logger, and the unweighted mean over logged episodes whose actions all match.
Output: experiments/v2_sim/repair_logger_v1.json
"""
from __future__ import annotations
import json
from fractions import Fraction as Fr
from pathlib import Path

import repair_generator as G

OUT = Path(__file__).resolve().parent / 'repair_logger_v1.json'
LOGGERS = {   # P(A = large | S, t, last feedback)
    'uniform_floor_0.5': lambda s, t, o: Fr(1, 2),
    'feedback_dependent_floor_0.2': lambda s, t, o: Fr('0.8') if o == 'exc' else Fr('0.2'),
    'zero_support_negative_control': lambda s, t, o: Fr(1) if o == 'exc' else Fr(1, 2),
}


def logged_expectations(pol, cell, s, logger):
    acc = dict(ipw_success=Fr(0), ipw_cost=Fr(0), match_mass=Fr(0), match_success=Fr(0))
    unsupported_t = []

    def terminal(pr, w, cost, y):
        acc['ipw_success'] += pr * w * y; acc['ipw_cost'] += pr * w * cost
        acc['match_mass'] += pr; acc['match_success'] += pr * y

    terminal(G.P0[s], Fr(1), G.C[0], 1)                                    # first call correct: no decision taken

    def rec(t, u, key, last_o, pr, w, cost):
        a = pol.act(s, t, key)
        p1 = logger(s, t, last_o)
        pa = p1 if a else 1 - p1
        if pa == 0:
            unsupported_t.append(t)
            return
        pr, w, cost = pr * pa, w / pa, cost + G.C[a]
        terminal(pr * cell.repair[u, a], w, cost, 1)                       # repaired: true pass, stop
        for u2 in (0, 1):
            pu = cell.stay[u, a] if u2 else 1 - cell.stay[u, a]
            for o in G.OBS:
                p = pr * (1 - cell.repair[u, a]) * pu * cell.p_obs(o, u2, s)
                if p == 0:
                    continue
                if o == 'pass' or t == cell.K:
                    terminal(p, w, cost, 0)                                # false pass, or opportunities exhausted
                else:
                    rec(t + 1, u2, pol.update(key, a, o, None), o, p, w, cost)

    for u0 in (0, 1):
        pu0 = (1 - G.P0[s]) * (G.DEEP0[s] if u0 else 1 - G.DEEP0[s])
        for o0 in G.OBS:
            p = pu0 * cell.p_obs(o0, u0, s)
            if o0 == 'pass':
                terminal(p, Fr(1), G.C[0], 0)
            else:
                rec(1, u0, pol.init_key(s, o0, None), o0, p, Fr(1), G.C[0])
    return acc, unsupported_t


def logged_reach(cell, s, logger, t_max):
    """P(reach opportunity t) under the LOGGER itself: the logged data law, which does move with the logger."""
    reach = [Fr(0)] * (t_max + 1)

    def rec(t, u, last_o, pr):
        reach[t] += pr
        if t == t_max:
            return
        for a in (0, 1):
            p1 = logger(s, t, last_o); pa = p1 if a else 1 - p1
            for u2 in (0, 1):
                pu = cell.stay[u, a] if u2 else 1 - cell.stay[u, a]
                for o in ('exc', 'asr'):
                    p = pr * pa * (1 - cell.repair[u, a]) * pu * cell.p_obs(o, u2, s)
                    if p:
                        rec(t + 1, u2, o, p)

    for u0 in (0, 1):
        for o0 in ('exc', 'asr'):
            p = (1 - G.P0[s]) * (G.DEEP0[s] if u0 else 1 - G.DEEP0[s]) * cell.p_obs(o0, u0, s)
            rec(1, u0, o0, p)
    return reach[1:]


def build():
    cells = []
    for cfg in [(K, c, f) for K in (2, 4) for c in G.REPAIR for f in G.KAPPA]:
        cell = G.Cell(*cfg)
        pols = {}
        for pol in G.catalog(cell.K):
            truth = {s: G.enumerate_value(pol, cell, s)[0] for s in (0, 1)}
            row = {}
            for lname, lg in LOGGERS.items():
                per = {s: logged_expectations(pol, cell, s, lg) for s in (0, 1)}
                ex = {k: G.mix(lambda s: per[s][0][k]) for k in ('ipw_success', 'ipw_cost')}
                tr = {k: G.mix(lambda s: truth[s][k]) for k in ('success', 'cost')}
                unsup = sorted({t for s in (0, 1) for t in per[s][1]})
                naive = G.mix(lambda s: per[s][0]['match_success'] / per[s][0]['match_mass'])
                row[lname] = dict(
                    status=dict(
                        success='supported' if not unsup else 'UNSUPPORTED',
                        utility='supported' if not unsup else 'UNSUPPORTED',
                        cost=('supported' if not unsup else
                              'identified by known final-step cost (unsupported actions only at the final opportunity), '
                              'but NOT by plain trajectory IPW, which drops that branch' if max(unsup) == cell.K else
                              'UNSUPPORTED: later occupancy depends on unlogged repair outcomes')),
                    unsupported_at_opportunities=unsup,
                    ipw_success=str(ex['ipw_success']), ipw_cost=str(ex['ipw_cost']),
                    ipw_success_equals_truth=ex['ipw_success'] == tr['success'],
                    ipw_cost_equals_truth=ex['ipw_cost'] == tr['cost'],
                    ipw_utility_equals_truth=ex['ipw_success'] - ex['ipw_cost'] == tr['success'] - tr['cost'],
                    unweighted_matched_success=str(naive), unweighted_equals_truth=naive == tr['success'])
            pols[pol.name] = dict(truth_success=str(G.mix(lambda s: truth[s]['success'])),
                                  truth_cost=str(G.mix(lambda s: truth[s]['cost'])), loggers=row)
        reach = {l: [str(G.mix(lambda s, t=t: logged_reach(cell, s, lg, cell.K)[t])) for t in range(cell.K)]
                 for l, lg in LOGGERS.items()}
        cells.append(dict(K=cell.K, action_effect=cell.crossing, feedback=cell.feedback, policies=pols,
                          logged_reach_by_logger=reach))
    rows = [(c, p, l, r) for c in cells for p, pr in c['policies'].items() for l, r in pr['loggers'].items()]
    sup = [r for *_, r in rows if r['status']['success'] == 'supported']
    checks = dict(
        supported_ipw_exact_success_cost_utility=all(r['ipw_success_equals_truth'] and r['ipw_cost_equals_truth']
                                                     and r['ipw_utility_equals_truth'] for r in sup),
        supported_rows=len(sup), unsupported_rows=len(rows) - len(sup),
        unsupported_only_under_zero_support_logger=all(l == 'zero_support_negative_control' for _, _, l, r in rows
                                                       if r['status']['success'] != 'supported'),
        unsupported_success_ipw_fails_somewhere=any(not r['ipw_success_equals_truth'] for *_, r in rows
                                                    if r['status']['success'] != 'supported'),
        unweighted_fails_somewhere_under_feedback_dependent=any(
            not r['unweighted_equals_truth'] for _, _, l, r in rows if l == 'feedback_dependent_floor_0.2'),
        logged_data_law_moves_with_logger=any(len(set(map(tuple, c['logged_reach_by_logger'].values()))) > 1 for c in cells),
        truth_takes_no_logger_argument=True)
    return dict(
        request='DTR-REQ-003 slice 4: logger layer for the finite repair generator (proposed tables of repair_generator_v1)',
        status='EXACT rational enumeration; no Monte Carlo, no model',
        loggers={'uniform_floor_0.5': 'P(large) = 1/2', 'feedback_dependent_floor_0.2': 'P(large) = .8 after exception, .2 otherwise',
                 'zero_support_negative_control': 'P(large) = 1 after exception, 1/2 otherwise'},
        checks=checks, cells=cells,
        not_yet=['complete fixed-task blocks (n in {250, 1000}) and archive-matching branch sampling', 'stress cells'])


def main():
    rep = build()
    c = rep['checks']
    if not all(v for k, v in c.items() if isinstance(v, bool)):
        raise SystemExit('logger checks failed: %s' % c)
    OUT.write_text(json.dumps(rep, indent=1) + '\n')
    print(c)


if __name__ == '__main__':
    main()
