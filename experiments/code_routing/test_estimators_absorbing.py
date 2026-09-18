"""Tests for estimators_absorbing.py.

1. Agreement with the repository's reference estimators (src/dtr_agent_evals) on
   its own fixed-horizon simulator: identical per-trajectory IPW and DR scores.
2. Absorbing variable horizon: unbiasedness of IPW and DR against on-policy truth
   in a small absorbing environment, for deterministic, tailored and stochastic targets.
3. No-op padding equivalence, cluster-mean inference guard, certificate arithmetic.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[1] / 'src'))
import estimators_absorbing as EA  # noqa: E402
import policies as P  # noqa: E402
from dtr_agent_evals import estimators as REF  # noqa: E402
from dtr_agent_evals.simulator import Environment, policy_probability, simulate  # noqa: E402


def _logs_from_reference(data):
    n, h = data.a.shape
    key = np.empty((n, h), object); state = np.empty((n, h), object)
    for i in range(n):
        for t in range(h):
            state[i, t] = dict(t=t, x=int(data.x[i]), l=int(data.l[i, t]), h=h)
            key[i, t] = (t, int(data.x[i]), int(data.l[i, t]))
    return EA.Logs(np.arange(n).astype(object), np.ones((n, h), bool), data.a.copy(), data.b.copy(), key, state, data.r.copy())


@pytest.mark.parametrize('name', ['always_small', 'always_large', 'fixed_switch', 'failure_escalation', 'soft_escalation'])
def test_matches_reference_estimators(name):
    data = simulate(3000, np.random.default_rng(3), Environment())
    L = _logs_from_reference(data)
    pol = lambda s: float(policy_probability(name, np.array([s['x']]), np.array([s['l']]), s['t'], s['h'])[0])
    assert np.allclose(EA.weights(L, pol), REF.weights(data, name))
    q_ref = REF.fit_q(data, name, 'correct')
    ref_scores, ref_plug = REF.dr_scores(data, name, q_ref)
    Q, fb, _ = EA.fit_q(L, pol)
    my_scores, my_plug = EA.dr_scores(L, pol, Q, fb)
    assert np.allclose(my_scores, ref_scores, atol=1e-10)
    assert np.allclose(my_plug, ref_plug, atol=1e-10)


# ---------------------------------------------------------------- absorbing toy environment
def _rollout(n, rng, policy=None, K=3, runs=1):
    eps = []
    for j in range(n):
        x = int(rng.random() < 0.3); hard = rng.random() < (0.55 if x else 0.35)
        for run in range(runs):
            decs, prev, fc, succ = [], [], 'start', 0
            for t in range(K):
                s = dict(t=t, x_humaneval=x, fail_class=fc, prev_actions=tuple(prev), frac_fail=0.0)
                pl = 0.5 if policy is None else policy(s)
                a = int(rng.random() < pl)
                decs.append(dict(t=t, a=a, b_obs=pl if a else 1 - pl, state=dict(s, prev_actions=list(prev)), penalty=0.03 if a else 0.01))
                prev.append(a)
                p_fix = (0.75 if a else 0.55) - (0.35 if hard else 0.0) + (0.15 if fc == 'exception' else 0.0) - (0.2 if (fc == 'assertion' and not a) else 0.0)
                ok = rng.random() < p_fix
                if ok:
                    succ = int(rng.random() < 0.9); break          # validated; visible tests are imperfect
                fc = 'exception' if rng.random() < 0.4 else 'assertion'
                succ = int(rng.random() < 0.15)                     # false alarm: fails validation yet hidden tests pass
            eps.append(dict(task_uid='t%d' % j, decisions=decs, success=succ))
    return eps


def _truth(policy, seed=11, n=250_000):
    eps = _rollout(n, np.random.default_rng(seed), policy)
    return float(np.mean([e['success'] - sum(d['penalty'] for d in e['decisions']) for e in eps]))


@pytest.mark.parametrize('name', ['always_small', 'always_large', 'escalate_after_first_failure', 'class_tailored', 'soft_escalation_d2'])
def test_unbiased_under_absorption(name):
    pol = P.PRESPECIFIED[name]
    truth = _truth(pol)
    ipw, dr = [], []
    for rep in range(120):
        L = EA.from_episodes(_rollout(250, np.random.default_rng(1000 + rep), runs=2), 3, P.state_key)
        out = EA.evaluate(L, pol, seed=rep)
        ipw.append(out['ipw']['estimate']); dr.append(out['dr']['estimate'])
    for est in (ipw, dr):
        mc_se = np.std(est, ddof=1) / np.sqrt(len(est))
        assert abs(np.mean(est) - truth) < 3.5 * mc_se + 0.002, (name, np.mean(est), truth, mc_se)
    assert np.std(dr) <= np.std(ipw) * 1.05          # DR should not be noticeably noisier than IPW here


def test_padding_equivalence_and_cluster_guard():
    eps = _rollout(300, np.random.default_rng(5), runs=2)
    L3 = EA.from_episodes(eps, 3, P.state_key); L5 = EA.from_episodes(eps, 5, P.state_key)   # two extra no-op stages
    pol = P.PRESPECIFIED['escalate_after_first_failure']
    a, b = EA.evaluate(L3, pol, seed=1), EA.evaluate(L5, pol, seed=1)
    assert a['ipw']['estimate'] == pytest.approx(b['ipw']['estimate']) and a['dr']['estimate'] == pytest.approx(b['dr']['estimate'])
    with pytest.raises(ValueError):
        EA.cluster_means(np.array(['a', 'a', 'b'], object), np.ones(3))


def test_learned_table_and_certificate():
    L = EA.from_episodes(_rollout(4000, np.random.default_rng(9)), 3, P.state_key)
    table = EA.learn_greedy_table(L)
    v_learned, v_small = _truth(P.table_policy(table)), _truth(P.always_small)
    assert v_learned >= v_small - 0.005
    c = EA.hoeffding_certificate(K_policies=7, n_tasks=330, T=3, r=1.0, c=2.0, alpha=0.05)
    assert c['M'] == pytest.approx(3 + 2 * (2 * 3 + 4 * 2 + 8 * 1))


def test_history_compression_breaks_plugin_but_not_dr():
    """Issue #2: drop benchmark, failure class and previous action from the Q-table state. The plug-in (g-computation)
    is then biased for a policy that depends on the dropped failure class; DR with KNOWN propensities is not."""
    pol = P.PRESPECIFIED['class_tailored']; truth = _truth(pol); g, d = [], []
    for rep in range(100):
        L = EA.from_episodes(_rollout(400, np.random.default_rng(5000 + rep), runs=2), 3, lambda s: (int(s['t']),))
        out = EA.evaluate(L, pol, seed=rep); g.append(out['gcomp']['estimate']); d.append(out['dr']['estimate'])
    g_se, d_se = np.std(g, ddof=1) / 10, np.std(d, ddof=1) / 10
    assert abs(np.mean(g) - truth) > 6 * g_se and abs(np.mean(g) - truth) > 0.015        # plug-in: clearly biased
    assert abs(np.mean(d) - truth) < 3.5 * d_se + 0.002                                   # DR: still unbiased
