"""DTR-REQ-003 P0 next step (protocol section 7): task-split DR / outcome regression for the repair-model sampler, reusing
experiments/code_routing/estimators_absorbing.py unchanged.

Observation/history mapping (documented, as the lead requires):
  pre-decision part   the COMMON first call is not a routing decision. Its cost and the success of first-call-pass
                      episodes are policy-independent, so each episode carries z_pre = 1{first_call_pass} - C[0] with
                      weight 1. estimators_absorbing scores decision-free episodes as 0, so without this term DR/OR would
                      target the wrong value.
  decision stages     sampler decision t = 1..K maps to estimator stage t - 1. b = the recorded logging probability of
                      the chosen action; stage reward r = -C[a], plus the episode's success at its LAST decision (success
                      after a repair can only occur there). Identity checked: z_pre + sum_t r_t = utility.
  observed state      {'S', 't', 'obs', 'prev_actions'}: stratum, stage, every feedback observed so far and every earlier
                      action. The tabular key is the full observed history: no latent error type U is ever used.
  target probability  the frozen catalog policy's action on that observed history (0 or 1).
  task folds          estimators_absorbing.cluster_scores assigns WHOLE TASKS to folds; the Q fit never sees the test
                      fold's tasks. Equal runs per task are required.
  positive control    known_kernel_q: exact Q from the accepted kernels via the Bayes belief on the observed history,
                      labelled separately; it is never a fitted nuisance.
Pure bridge; runs no batch.
"""
from __future__ import annotations
import sys
from pathlib import Path

import numpy as np

import repair_generator as G
import sampler as S

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'code_routing'))
import estimators_absorbing as EA  # noqa: E402

STATE_FIELDS = ('S', 't', 'obs', 'prev_actions')


def observed_state(rec, i):
    return dict(S=rec['stratum'], t=i, obs=tuple(rec['observations'][:i + 1]),
                prev_actions=tuple(d['action'] for d in rec['decisions'][:i]))


def state_key(state):
    return (state['S'], state['t'], state['obs'], state['prev_actions'])


def z_pre(rec):
    return (1 if rec['exit'] == 'first_call_pass' else 0) - G.C[0]


def to_logs(episodes, K):
    n = len(episodes)
    elig = np.zeros((n, K), bool); a = np.zeros((n, K), int); b = np.ones((n, K)); r = np.zeros((n, K))
    key = np.empty((n, K), object); state = np.empty((n, K), object)
    for i, e in enumerate(episodes):
        for j, d in enumerate(e['decisions']):
            st = observed_state(e, j)
            elig[i, j], a[i, j], b[i, j] = True, d['action'], float(d['p_logged'])
            state[i, j], key[i, j] = st, state_key(st)
            r[i, j] -= float(G.C[d['action']])
        if e['decisions']:
            r[i, len(e['decisions']) - 1] += e['success']
    return EA.Logs(np.array([e['task_id'] for e in episodes], object), elig, a, b, key, state, r)


def prob_policy(pol):
    """state -> P(large) for a deterministic catalog policy, rebuilt from the observed history only."""
    def p(state):
        key = pol.init_key(state['S'], state['obs'][0], None)
        for j in range(state['t']):
            key = pol.update(key, state['prev_actions'][j], state['obs'][j + 1], None)
        return float(pol.act(state['S'], state['t'] + 1, key))
    return p


def known_kernel_q(cell, pol):
    """Exact Q_t(h, a) (decision-stage rewards only) for every observed history reachable in K decisions."""
    K = cell.K
    Q = [dict() for _ in range(K)]
    fallback = [{0: 0.0, 1: 0.0} for _ in range(K)]
    pp = prob_policy(pol)

    def value(s, t, obs, acts, belief):
        """V_t(h) = sum_a pi(a|h) Q_t(h, a); fills Q along the way."""
        st = dict(S=s, t=t, obs=obs, prev_actions=acts)
        q = {}
        for a in (0, 1):
            p_ok = belief * cell.repair[1, a] + (1 - belief) * cell.repair[0, a]
            v = p_ok - G.C[a]
            if t + 1 < K:
                fail = {u: (belief if u else 1 - belief) * (1 - cell.repair[u, a]) for u in (0, 1)}
                p_fail = sum(fail.values())
                if p_fail:
                    prior = sum(fail[u] * cell.stay[u, a] for u in (0, 1)) / p_fail
                    for o in ('exc', 'asr'):
                        nb, po = cell.posterior_after_obs(prior, o, s)
                        if po:
                            v += p_fail * po * value(s, t + 1, obs + (o,), acts + (a,), nb)
            q[a] = v
        Q[t][state_key(st)] = {a: float(q[a]) for a in (0, 1)}
        pl = pp(st)
        return (1 - pl) * q[0] + pl * q[1]

    for s in (0, 1):
        for o0 in ('exc', 'asr'):
            b0, po = cell.posterior_after_obs(G.DEEP0[s], o0, s)
            if po:
                value(s, 0, (o0,), (), b0)
    return Q, fallback


def estimates(episodes, pol, tasks, r, K, folds=3, seed=0):
    """Task-equal PER-DECISION IPW ('pdis': stage reward t weighted by the cumulative weight through t, as defined in
    estimators_absorbing), cross-fitted DR and plug-in OR (g-computation), each plus the weight-1 pre-decision part.
    'pdis' is NOT the trajectory IPW of sampler.ipw_estimate (whole-episode utility times the final weight); both are
    unbiased and they differ on finite samples."""
    S.validate_manifest(episodes, tasks, r)
    L = to_logs(episodes, K)
    res = EA.cluster_scores(L, prob_policy(pol), folds=folds, seed=seed)
    labels, pre = EA.cluster_means(L.task, np.array([float(z_pre(e)) for e in episodes]))
    if list(labels) != list(res['tasks']):
        raise ValueError('task label order mismatch')
    return dict(pdis=float((res['ipw'] + pre).mean()), dr=float((res['dr'] + pre).mean()),
                or_plugin=float((res['plugin'] + pre).mean()), diagnostics=res['diagnostics'])
