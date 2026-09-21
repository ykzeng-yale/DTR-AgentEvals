"""DTR-REQ-003, slice 3: finite multi-opportunity repair generator (experiment_protocol_v2.md section 2). No Monte Carlo.

All table values below are PROPOSED by the worker for lead review; the lead owns the design.

Episode (per task stratum S, observed at the start; 0 = easy, 1 = hard):
  common first call (small, cost C[0]): candidate correct w.p. P0[S] -> visible pass -> stop, Y = 1.
  otherwise latent error type U0 ~ Bern(DEEP0[S]) (1 = deep, 0 = shallow) and feedback O0 ~ obs(U0, S).
  feedback for an incorrect candidate: 'pass' (FALSE pass) w.p. FALSE_PASS[S], else 'exc' or 'asr' with
  P(exc | U) = kappa if U = 1 else 1 - kappa. A false pass triggers the declared stop with hidden Y = 0.
  repair opportunities t = 1..K while active: action A_t in {0 small, 1 large}, cost C[A_t];
  the new candidate is correct w.p. REPAIR[U, A]; if not, U' ~ Bern(STAY_DEEP[U, A]) (the action moves the
  future state) and new feedback O_t ~ obs(U', S). If the final repair fails, the episode ends with Y = 0.
Visible pass and hidden correctness are distinct: Y is correctness of the final candidate.

Policy truth is derived twice and must agree EXACTLY (the protocol asks for 1e-10):
  path 1  full-history enumeration over latent U paths;
  path 2  Bellman recursion on (S, t, belief b = P(U = deep | observed history), policy key), memoized.
The best observed-history value is exact DP over the belief, which is sufficient for control here.
Output: experiments/v2_sim/repair_generator_v1.json
"""
from __future__ import annotations
import functools, itertools, json
from fractions import Fraction as Fr
from pathlib import Path

OUT = Path(__file__).resolve().parent / 'repair_generator_v1.json'
P_HARD = Fr(1, 2)
P0 = {0: Fr('0.6'), 1: Fr('0.2')}
FALSE_PASS = {0: Fr('0.1'), 1: Fr('0.2')}
DEEP0 = {0: Fr('0.3'), 1: Fr('0.7')}
KAPPA = {'informative': Fr('0.9'), 'weak': Fr('0.6')}
REPAIR = {   # (U, A) -> P(repaired candidate correct)
    'no_crossing': {(0, 0): Fr('0.5'), (0, 1): Fr('0.6'), (1, 0): Fr('0.1'), (1, 1): Fr('0.4')},
    'crossing': {(0, 0): Fr('0.6'), (0, 1): Fr('0.4'), (1, 0): Fr('0.1'), (1, 1): Fr('0.5')},
    'U_irrelevant_negative_control': {(0, 0): Fr('0.3'), (0, 1): Fr('0.4'), (1, 0): Fr('0.3'), (1, 1): Fr('0.4')},
}
STAY_DEEP = {(1, 0): Fr('0.9'), (1, 1): Fr('0.6'), (0, 0): Fr('0.2'), (0, 1): Fr('0.1')}   # (U, A) -> P(U' = deep)
STAY_DEEP_IRRELEVANT = {k: Fr('0.5') for k in STAY_DEEP}
C = {0: Fr('0.01'), 1: Fr('0.03')}          # archived call penalties, unchanged
OBS = ('pass', 'exc', 'asr')


class Cell:
    def __init__(self, K, crossing, feedback):
        self.K, self.crossing, self.feedback = K, crossing, feedback
        self.repair, self.kappa = REPAIR[crossing], KAPPA[feedback]
        self.stay = STAY_DEEP_IRRELEVANT if crossing.startswith('U_irrelevant') else STAY_DEEP

    def p_obs(self, o, u, s):
        fp = FALSE_PASS[s]
        pe = self.kappa if u else 1 - self.kappa
        return fp if o == 'pass' else (1 - fp) * (pe if o == 'exc' else 1 - pe)

    def posterior_after_obs(self, prior_deep, o, s):
        """P(U = deep | o) for an incorrect candidate, and P(o) under the prior."""
        num = prior_deep * self.p_obs(o, 1, s)
        den = num + (1 - prior_deep) * self.p_obs(o, 0, s)
        return (num / den if den else None), den


# ---------------------------------------------------------------------------------------------------- policies
class Policy:
    """act(S, t, key) -> action; key is folded over (a, o) pairs by update(); init_key uses S and O0."""
    def __init__(self, name, act, init_key=lambda s, o0, b: (), update=lambda key, a, o, b: ()):
        self.name, self.act, self.init_key, self.update = name, act, init_key, update


def schedule(seq):
    return Policy('fixed_' + ''.join('L' if a else 'S' for a in seq), lambda s, t, key: seq[t - 1])


def catalog(K):
    pols = [schedule(seq) for seq in itertools.product((0, 1), repeat=K)]
    pols.append(Policy('prompt_only_large_if_hard', lambda s, t, key: s))
    pols.append(Policy('history_large_after_exception', lambda s, t, key: 1 if key == 'exc' else 0,
                       init_key=lambda s, o0, b: o0, update=lambda key, a, o, b: o))
    pols.append(Policy('history_S_or_exception', lambda s, t, key: 1 if (s or key == 'exc') else 0,
                       init_key=lambda s, o0, b: o0, update=lambda key, a, o, b: o))
    return pols


# ------------------------------------------------------------------------------------------- truth path 1
def enumerate_value(pol, cell, s):
    """Full-history enumeration over latent U paths. Returns expected success, cost, calls, false-pass stops, reach[t]."""
    tot = dict(success=Fr(0), cost=Fr(0), repair_calls=Fr(0), false_pass_stop=Fr(0))
    reach = [Fr(0)] * (cell.K + 1)
    tot['cost'] += C[0]                                                  # common first call
    tot['success'] += P0[s]

    def rec(t, u, belief, key, pr):
        reach[t] += pr
        a = pol.act(s, t, key)
        tot['cost'] += pr * C[a]; tot['repair_calls'] += pr
        pr_ok = pr * cell.repair[u, a]
        tot['success'] += pr_ok
        for u2 in (0, 1):
            pu = cell.stay[u, a] if u2 else 1 - cell.stay[u, a]
            for o in OBS:
                p = pr * (1 - cell.repair[u, a]) * pu * cell.p_obs(o, u2, s)
                if p == 0:
                    continue
                if o == 'pass':
                    tot['false_pass_stop'] += p
                elif t < cell.K:
                    nb = belief_update(cell, belief, a, o, s)
                    rec(t + 1, u2, nb, pol.update(key, a, o, nb), p)

    for u0 in (0, 1):
        pu0 = (1 - P0[s]) * (DEEP0[s] if u0 else 1 - DEEP0[s])
        for o0 in OBS:
            p = pu0 * cell.p_obs(o0, u0, s)
            if o0 == 'pass':
                tot['false_pass_stop'] += p
                continue
            b0, _ = cell.posterior_after_obs(DEEP0[s], o0, s)
            rec(1, u0, b0, pol.init_key(s, o0, b0), p)
    return tot, reach


def belief_update(cell, b, a, o, s):
    """P(U' = deep | failed repair with action a from belief b, then feedback o)."""
    fail = {u: (b if u else 1 - b) * (1 - cell.repair[u, a]) for u in (0, 1)}
    prior_next = sum(fail[u] * cell.stay[u, a] for u in (0, 1)) / sum(fail.values())
    return cell.posterior_after_obs(prior_next, o, s)[0]


# ------------------------------------------------------------------------------------------- truth path 2
def bellman_value(pol, cell, s):
    """Recursion on (t, belief, policy key); latent U is integrated out through the belief."""
    @functools.lru_cache(maxsize=None)
    def V(t, b, key):
        """Expected (success, cost, repair_calls, false_pass_stop) from opportunity t onward."""
        a = pol.act(s, t, key)
        p_ok = b * cell.repair[1, a] + (1 - b) * cell.repair[0, a]
        succ, cost, calls, fps = p_ok, C[a], Fr(1), Fr(0)
        if p_ok == 1:
            return succ, cost, calls, fps
        fail = {u: (b if u else 1 - b) * (1 - cell.repair[u, a]) for u in (0, 1)}
        p_fail = sum(fail.values())
        prior_next = sum(fail[u] * cell.stay[u, a] for u in (0, 1)) / p_fail
        for o in OBS:
            nb, po = cell.posterior_after_obs(prior_next, o, s)
            p = p_fail * po
            if p == 0:
                continue
            if o == 'pass':
                fps += p
            elif t < cell.K:
                v = V(t + 1, nb, pol.update(key, a, o, nb))
                succ += p * v[0]; cost += p * v[1]; calls += p * v[2]; fps += p * v[3]
        return succ, cost, calls, fps

    tot = dict(success=P0[s], cost=C[0], repair_calls=Fr(0), false_pass_stop=Fr(0))
    for o0 in OBS:
        b0, po = cell.posterior_after_obs(DEEP0[s], o0, s)
        p = (1 - P0[s]) * po
        if o0 == 'pass':
            tot['false_pass_stop'] += p
            continue
        v = V(1, b0, pol.init_key(s, o0, b0))
        for i, k in enumerate(('success', 'cost', 'repair_calls', 'false_pass_stop')):
            tot[k] += p * v[i]
    return tot


def optimal_utility(cell, s):
    """Exact DP over the belief: best observed-history utility (success - cost); ties go to the small model."""
    @functools.lru_cache(maxsize=None)
    def W(t, b):
        best = None
        for a in (0, 1):
            p_ok = b * cell.repair[1, a] + (1 - b) * cell.repair[0, a]
            val = p_ok - C[a]
            fail = {u: (b if u else 1 - b) * (1 - cell.repair[u, a]) for u in (0, 1)}
            p_fail = sum(fail.values())
            if p_fail and t < cell.K:
                prior_next = sum(fail[u] * cell.stay[u, a] for u in (0, 1)) / p_fail
                for o in ('exc', 'asr'):
                    nb, po = cell.posterior_after_obs(prior_next, o, s)
                    if po:
                        val += p_fail * po * W(t + 1, nb)[0]
            if best is None or val > best[0]:
                best = (val, a)
        return best

    u = P0[s] - C[0]
    for o0 in ('exc', 'asr'):
        b0, po = cell.posterior_after_obs(DEEP0[s], o0, s)
        u += (1 - P0[s]) * po * W(1, b0)[0]
    return u


# ---------------------------------------------------------------------------------------------------- report
def s_(x):
    return dict(exact=str(x), decimal=float(x))


def mix(f):
    return (1 - P_HARD) * f(0) + P_HARD * f(1)


def build():
    cells = []
    for K, crossing, feedback in itertools.product((2, 4), tuple(REPAIR), tuple(KAPPA)):
        cell = Cell(K, crossing, feedback)
        rows, agree = {}, True
        for pol in catalog(K):
            per = {}
            for s in (0, 1):
                e, reach = enumerate_value(pol, cell, s)
                b = bellman_value(pol, cell, s)
                ok = all(e[k] == b[k] for k in e)
                agree &= ok
                per[s] = dict(e, utility=e['success'] - e['cost'], reach=reach[1:], paths_agree_exactly=ok)
            rows[pol.name] = dict(
                success=s_(mix(lambda s: per[s]['success'])), cost=s_(mix(lambda s: per[s]['cost'])),
                utility=s_(mix(lambda s: per[s]['utility'])), repair_calls=s_(mix(lambda s: per[s]['repair_calls'])),
                false_pass_stop=s_(mix(lambda s: per[s]['false_pass_stop'])),
                reach_opportunity=[str(mix(lambda s: per[s]['reach'][t])) for t in range(K)],
                by_stratum={('easy', 'hard')[s]: dict(success=str(per[s]['success']), utility=str(per[s]['utility']))
                            for s in (0, 1)},
                paths_agree_exactly=all(per[s]['paths_agree_exactly'] for s in (0, 1)))
        util = {n: Fr(r['utility']['exact']) for n, r in rows.items()}
        fixed = {n: u for n, u in util.items() if n.startswith('fixed_')}
        best_fixed = max(fixed.items(), key=lambda kv: (kv[1], kv[0]))
        # best prompt-only: the best fixed schedule chosen separately for each stratum
        by_s = {s: max(Fr(rows[n]['by_stratum'][('easy', 'hard')[s]]['utility']) for n in fixed) for s in (0, 1)}
        best_prompt = mix(lambda s: by_s[s])
        best_hist = mix(lambda s: optimal_utility(cell, s))
        catalog_max = max(util.values())
        cells.append(dict(
            K=K, action_effect=crossing, feedback=feedback, kappa=str(cell.kappa), policies=rows,
            both_truth_paths_agree_exactly=agree,
            best_fixed=dict(policy=best_fixed[0], utility=s_(best_fixed[1])),
            best_prompt_only_utility=s_(best_prompt), best_observed_history_utility=s_(best_hist),
            history_advantage_over_best_fixed=s_(best_hist - best_fixed[1]),
            history_advantage_over_best_prompt_only=s_(best_hist - best_prompt),
            dp_dominates_catalog=best_hist >= catalog_max))
    return dict(
        request='DTR-REQ-003 slice 3: finite multi-opportunity repair generator, kernel tables and exact truth',
        status='PROPOSED tables for lead review; exact rational enumeration and DP; no Monte Carlo, no model',
        tables=dict(P_HARD=str(P_HARD), P0={k: str(v) for k, v in P0.items()}, FALSE_PASS={k: str(v) for k, v in FALSE_PASS.items()},
                    DEEP0={k: str(v) for k, v in DEEP0.items()}, KAPPA={k: str(v) for k, v in KAPPA.items()},
                    REPAIR={c: {'U%d_A%d' % k: str(v) for k, v in t.items()} for c, t in REPAIR.items()},
                    STAY_DEEP={'U%d_A%d' % k: str(v) for k, v in STAY_DEEP.items()},
                    STAY_DEEP_for_U_irrelevant='1/2 for every (U, A)', COST={k: str(v) for k, v in C.items()},
                    strata='S observed at start (0 easy, 1 hard); reported values mix strata 1/2 : 1/2',
                    stopping='first visible pass (true or false) or after K repair opportunities',
                    endpoint='hidden correctness of the final candidate; utility = success - total call cost incl. common first call'),
        cells=cells,
        not_yet=['logger layer: floors .5/.2, IPW expectation and logger-invariance checks',
                 'fixed-task block generator (n in {250, 1000}) and archive-matching branch module',
                 'stress cells (severe overlap, zero support, hidden confounding, non-Markov coarsening, drift)'])


def main():
    rep = build()
    bad = [c for c in rep['cells'] if not c['both_truth_paths_agree_exactly'] or not c['dp_dominates_catalog']]
    if bad:
        raise SystemExit('generator checks failed in %d cells' % len(bad))
    OUT.write_text(json.dumps(rep, indent=1) + '\n')
    for c in rep['cells']:
        print('K=%d %-30s %-11s best_fixed=%-10s adv_vs_fixed=%-8.5f adv_vs_prompt=%.5f' % (
            c['K'], c['action_effect'], c['feedback'], c['best_fixed']['policy'],
            c['history_advantage_over_best_fixed']['decimal'], c['history_advantage_over_best_prompt_only']['decimal']))


if __name__ == '__main__':
    main()
