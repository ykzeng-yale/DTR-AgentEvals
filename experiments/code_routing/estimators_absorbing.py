"""Tabular per-decision IPW, iterated-Q g-computation and cross-fitted DR for
ABSORBING, variable-horizon routing trajectories with task clusters.

Extends src/dtr_agent_evals/estimators.py (fixed horizon, binary state) without
modifying it. Same estimands and formulas (docs/theory.md Prop. 1, eq. 10,
eq. 13); differences:
  * a decision exists only while the episode is not absorbed; an ineligible
    stage contributes ratio 1, reward 0 and continuation value 0 (equivalent
    to no-op padding; tested against the unpadded form);
  * the tabular state is any hashable key;
  * folds are drawn over TASKS and inference uses task-mean scores, eq. (13),
    which requires the same number of runs for every task.
Known behaviour probabilities only. Unsupported targets are reported, not repaired.
"""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass

import numpy as np


@dataclass
class Logs:
    task: np.ndarray      # (n,) cluster label
    elig: np.ndarray      # (n,K) bool
    a: np.ndarray         # (n,K) 0/1, 0 where ineligible
    b: np.ndarray         # (n,K) P(observed action), 1 where ineligible
    key: np.ndarray       # (n,K) object: tabular pre-action state key (None where ineligible)
    state: np.ndarray     # (n,K) object: full pre-action state dict (None where ineligible)
    r: np.ndarray         # (n,K) stage reward; terminal success is added at the last eligible stage

    def __len__(self):
        return len(self.task)

    def subset(self, idx):
        return Logs(*(getattr(self, f)[idx] for f in ('task', 'elig', 'a', 'b', 'key', 'state', 'r')))


def from_episodes(episodes: list, K: int, state_key, outcome: str = 'utility') -> Logs:
    """outcome='utility': r_t = -penalty_t, plus success at the last decision. outcome='success': success only."""
    n = len(episodes)
    elig = np.zeros((n, K), bool); a = np.zeros((n, K), int); b = np.ones((n, K)); r = np.zeros((n, K))
    key = np.empty((n, K), object); state = np.empty((n, K), object)
    for i, e in enumerate(episodes):
        ds = e['decisions']
        for d in ds:
            t = d['t']; elig[i, t] = True; a[i, t] = d['a']; b[i, t] = d['b_obs']
            s = dict(d['state'], prev_actions=tuple(d['state']['prev_actions']))
            state[i, t] = s; key[i, t] = state_key(s)
            if outcome == 'utility':
                r[i, t] -= d['penalty']
        if ds:
            r[i, ds[-1]['t']] += e['success']      # an ITT-scored episode with no decision contributes 0 with weight 1 under every policy
    return Logs(np.array([e['task_uid'] for e in episodes], object), elig, a, b, key, state, r)


def target_prob_observed(L: Logs, policy) -> np.ndarray:
    p = np.ones(L.a.shape)
    for i, t in zip(*np.nonzero(L.elig)):
        pl = policy(L.state[i, t])
        p[i, t] = pl if L.a[i, t] == 1 else 1 - pl
    return p


def weights(L: Logs, policy) -> np.ndarray:
    if np.any(L.b[L.elig] <= 0):
        raise ValueError('behaviour probabilities must be positive on eligible decisions')
    return np.cumprod(target_prob_observed(L, policy) / L.b, axis=1)


def fit_q(train: Logs, policy, optimal: bool = False):
    """Iterated tabular Q. optimal=True uses max_a continuation (fitted-Q policy learning)."""
    K = train.a.shape[1]
    Q = [defaultdict(dict) for _ in range(K)]; fallback = [dict() for _ in range(K)]
    nextv = np.zeros(len(train)); empty = 0
    for t in reversed(range(K)):
        m = train.elig[:, t]
        y = train.r[:, t] + nextv
        for aa in (0, 1):
            ma = m & (train.a[:, t] == aa)
            fallback[t][aa] = float(y[ma].mean()) if ma.any() else (float(y[m].mean()) if m.any() else 0.0)
        cells = defaultdict(list)
        for i in np.nonzero(m)[0]:
            cells[(train.key[i, t], train.a[i, t])].append(y[i])
        for (k, aa), v in cells.items():
            Q[t][k][aa] = float(np.mean(v))
        v_t = np.zeros(len(train))
        for i in np.nonzero(m)[0]:
            q0, q1, e = _q(Q, fallback, t, train.key[i, t])
            empty += e
            pl = policy(train.state[i, t]) if not optimal else float(q1 > q0)
            v_t[i] = (1 - pl) * q0 + pl * q1
        nextv = v_t
    return Q, fallback, empty


def _q(Q, fallback, t, k):
    cell = Q[t].get(k, {})
    miss = int(0 not in cell) + int(1 not in cell)
    return cell.get(0, fallback[t][0]), cell.get(1, fallback[t][1]), miss


def dr_scores(L: Logs, policy, Q, fallback):
    n, K = L.a.shape
    V = np.zeros((n, K + 1)); Qa = np.zeros((n, K))
    for i, t in zip(*np.nonzero(L.elig)):
        q0, q1, _ = _q(Q, fallback, t, L.key[i, t])
        pl = policy(L.state[i, t])
        V[i, t] = (1 - pl) * q0 + pl * q1
        Qa[i, t] = q1 if L.a[i, t] == 1 else q0
    W = weights(L, policy)
    return V[:, 0] + np.sum(W * L.elig * (L.r + V[:, 1:] - Qa), axis=1), V[:, 0]


def cluster_means(task: np.ndarray, scores: np.ndarray):
    labels, inv, counts = np.unique(task, return_inverse=True, return_counts=True)
    if len(set(counts)) != 1:
        raise ValueError('eq. (13) needs the same number of runs per task; got %s' % sorted(set(counts)))
    return labels, np.bincount(inv, weights=scores) / counts


def summary(cm: np.ndarray) -> dict:
    est = float(cm.mean()); se = float(cm.std(ddof=1) / np.sqrt(len(cm)))
    return dict(estimate=est, se=se, lower=est - 1.96 * se, upper=est + 1.96 * se, n_tasks=int(len(cm)))


def cluster_scores(L: Logs, policy, folds: int = 3, seed: int = 0) -> dict:
    """Task-mean score vectors for IPW, DR (cross-fitted by task) and the plug-in, plus diagnostics."""
    tasks = np.unique(L.task)
    fold_of = dict(zip(tasks[np.random.default_rng(seed).permutation(len(tasks))], np.arange(len(tasks)) % folds))
    f = np.array([fold_of[t] for t in L.task])
    dr = np.zeros(len(L)); plug = np.zeros(len(L)); empty = 0
    for k in range(folds):
        te = np.nonzero(f == k)[0]
        Q, fb, e = fit_q(L.subset(np.nonzero(f != k)[0]), policy)
        dr[te], plug[te] = dr_scores(L.subset(te), policy, Q, fb)
        empty += e
    W = weights(L, policy)
    ipw = np.sum(W * L.r, axis=1)
    sw, sw2 = W.sum(0), (W * W).sum(0)
    labels, c_ipw = cluster_means(L.task, ipw)
    diag = dict(ess_by_stage=np.divide(sw ** 2, sw2, out=np.zeros_like(sw), where=sw2 > 0).tolist(),
                max_weight_by_stage=W.max(0).tolist(), zero_weight_fraction=float(np.mean(W[:, -1] == 0)),
                n_tasks_with_positive_weight=int(len(set(L.task[W[:, -1] > 0]))), n_tasks=int(len(labels)),
                min_behavior_probability=float(L.b[L.elig].min()), missing_q_cells_in_training=int(empty))
    return dict(tasks=labels, ipw=c_ipw, dr=cluster_means(L.task, dr)[1], plugin=cluster_means(L.task, plug)[1], diagnostics=diag)


def evaluate(L: Logs, policy, folds: int = 3, seed: int = 0) -> dict:
    s = cluster_scores(L, policy, folds, seed)
    return dict(ipw=summary(s['ipw']), dr=summary(s['dr']), gcomp=dict(estimate=float(s['plugin'].mean())), diagnostics=s['diagnostics'])


def learn_greedy_table(train: Logs) -> dict:
    """Fitted-Q with the OPTIMAL continuation (max over actions); returns {state_key: P(large) in {0,1}}."""
    Q, fb, _ = fit_q(train, policy=None, optimal=True)
    table = {}
    for t in range(train.a.shape[1]):
        for k in Q[t]:
            q0, q1, _ = _q(Q, fb, t, k)
            table[k] = float(q1 > q0)
    return table


def hoeffding_certificate(K_policies: int, n_tasks: int, T: int, r: float, c: float, alpha: float) -> dict:
    """Theorem 5 half-width epsilon_n (eq. 16-17) and the n needed for a target half-width of 0.05."""
    C = np.cumprod(np.full(T, c))
    M = T * r + 2 * r * float(np.sum(C * (T - np.arange(T))))
    eps = M * np.sqrt(8 * np.log(2 * K_policies / alpha) / n_tasks)
    return dict(M=M, epsilon=float(eps), n_tasks_for_half_width_0p05=float(M ** 2 * 8 * np.log(2 * K_policies / alpha) / 0.05 ** 2))
