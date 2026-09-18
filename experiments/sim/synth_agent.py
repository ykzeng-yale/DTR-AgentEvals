"""Synthetic two-stage coding-agent episode generator with known ground truth.

Purpose: a test bed where the value of every regime and the optimal regime
are known (by large Monte Carlo), so estimator validity, design efficiency and
regime-learning regret can be measured exactly. The structure mirrors the real
SMART in ``experiments/smart_code`` and is calibrated to base rates measured on
591 MBPP/HumanEval tasks with a 7B open-weight coder (first-attempt success
~0.73, self-test pass ~0.54, P(success | self-test pass) ~0.84).

Latent (never shown to estimators): task difficulty theta, first-attempt
correctness C1, bug depth, self-test validity T.
Observed: x (noisy difficulty proxy), A1, R (self-test pass/fail), O_exc
(1 = failure was a raised exception, 0 = an assertion mismatch), frac (share
of self-test asserts failing), A2, Y, cost.

Planted mechanism (what a good DTR should discover):
  * plan-first helps hard tasks, slightly hurts easy ones;
  * self-tests are a NOISY response signal: a fail is either a shallow bug
    (exception), a deep bug, or a FALSE ALARM (code right, test wrong);
  * repair fixes shallow bugs, rarely fixes deep bugs, and BREAKS correct code
    on false alarms (over-treatment harm); escalation is better on deep bugs
    but costs more; resampling forgets everything;
  * self-review of passing code mostly harms.

Stage-2 action codes: 0 submit, 1 self_review (feasible if R=1);
                      2 repair, 3 resample, 4 escalate (feasible if R=0).
"""
from __future__ import annotations
import numpy as np
import pandas as pd

FEASIBLE = {1: [0, 1], 0: [2, 3, 4]}
A1_SET = [0, 1]  # 0 direct, 1 plan_first
A2_NAMES = {0: 'submit', 1: 'self_review', 2: 'repair', 3: 'resample', 4: 'escalate'}
H1_COLS = ['x']
H2_COLS = ['x', 'A1', 'O_exc', 'frac']

COST_A1 = {0: 1.0, 1: 1.6}
COST_SELFTEST = 0.8
COST_A2 = {0: 0.0, 1: 1.0, 2: 1.2, 3: 1.0, 4: 2.5}
DEFAULT_LAMBDA = 0.03


def _sig(z):
    return 1.0 / (1.0 + np.exp(-z))


def p_correct_first(theta, a1):
    return _sig(1.3 - 1.1 * theta + a1 * (0.6 * theta - 0.1))


def simulate(n_tasks: int, reps: int, seed: int, regime=None, lam: float = DEFAULT_LAMBDA,
             fork: bool = False) -> pd.DataFrame:
    """Generate episodes.

    regime=None -> SMART: A1 uniform on A1_SET, A2 uniform on FEASIBLE[R].
    regime=(d1, d2) -> follow the regime (P1=P2=1).
    fork=True (SMART only) -> additionally return potential utilities
    ``U_a`` for EVERY feasible stage-2 arm from the same stage-2 state, with
    independent post-fork randomness per arm (what replaying an LLM agent from
    a saved state with fresh sampling seeds delivers).
    """
    rng = np.random.default_rng(seed)
    n = n_tasks * reps
    cluster = np.repeat(np.arange(n_tasks), reps)
    theta_t = rng.normal(0, 1, n_tasks)
    x_t = theta_t + rng.normal(0, 0.6, n_tasks)
    theta, x = theta_t[cluster], x_t[cluster]
    df = pd.DataFrame({'cluster': cluster, 'x': x})

    if regime is None:
        A1 = rng.integers(0, 2, n)
        P1 = np.full(n, 0.5)
    else:
        A1 = np.asarray(regime[0](df), dtype=int)
        P1 = np.ones(n)
    df['A1'] = A1
    df['P1'] = P1

    C1 = rng.random(n) < p_correct_first(theta, A1)
    deep = (~C1) & (rng.random(n) < _sig(0.2 + 0.8 * theta))
    shallow = (~C1) & (~deep)
    T = rng.random(n) < _sig(0.45 - 0.6 * theta)
    # response status
    R = np.where(C1, T, False)
    false_pass = deep & (rng.random(n) < 0.6)  # weak self-tests miss most deep bugs
    R = (R | false_pass).astype(int)
    false_alarm = C1 & (~T)
    O_exc = (shallow & (R == 0)).astype(int)
    frac = np.zeros(n)
    fa = false_alarm & (R == 0)
    dp = deep & (R == 0)
    frac[fa] = rng.beta(1.2, 4.0, fa.sum())
    frac[dp] = rng.beta(3.0, 2.0, dp.sum())
    frac[O_exc == 1] = 1.0
    df['R'] = R
    df['O_exc'] = O_exc
    df['frac'] = frac

    # potential final correctness under every stage-2 arm (independent draws per arm)
    u = {a: rng.random(n) for a in A2_NAMES}
    p_first0 = p_correct_first(theta, 0)
    Ya = {
        0: C1.copy(),
        1: np.where(C1, u[1] < 0.93, u[1] < 0.30),
        2: np.where(shallow, u[2] < 0.85, np.where(deep, u[2] < 0.25, u[2] < 0.65)),
        3: u[3] < p_first0,
        4: np.where(shallow, u[4] < 0.92, np.where(deep, u[4] < 0.55, u[4] < 0.88)),
    }

    if regime is None:
        A2 = np.where(R == 1, rng.integers(0, 2, n), rng.integers(2, 5, n))
        P2 = np.where(R == 1, 0.5, 1.0 / 3.0)
    else:
        A2 = np.asarray(regime[1](df), dtype=int)
        P2 = np.ones(n)
    df['A2'] = A2
    df['P2'] = P2

    base_cost = np.vectorize(COST_A1.get)(A1) + COST_SELFTEST
    Yfin = np.zeros(n)
    for a in A2_NAMES:
        m = A2 == a
        Yfin[m] = Ya[a][m]
    cost = base_cost + np.vectorize(COST_A2.get)(A2)
    df['success'] = Yfin
    df['cost'] = cost
    df['Y'] = Yfin - lam * cost
    if fork:
        for a in A2_NAMES:
            feas = np.where(R == 1, a in FEASIBLE[1], a in FEASIBLE[0])
            ua = Ya[a].astype(float) - lam * (base_cost + COST_A2[a])
            df['U_%d' % a] = np.where(feas, ua, np.nan)
    return df


def true_value(regime, n_tasks: int = 400_000, seed: int = 12345, lam: float = DEFAULT_LAMBDA) -> float:
    return float(simulate(n_tasks, 1, seed, regime=regime, lam=lam)['Y'].mean())


def oracle_regime(lam: float = DEFAULT_LAMBDA, n_tasks: int = 400_000, seed: int = 777):
    """Best regime measurable w.r.t. the OBSERVED history, by nonparametric
    backward induction on a huge forked sample (binning x and frac)."""
    big = simulate(n_tasks, 1, seed, regime=None, lam=lam, fork=True)
    xb = np.linspace(-3, 3, 25)
    fb = np.linspace(0, 1, 11)
    big['xb'] = np.clip(np.digitize(big['x'], xb), 0, len(xb))
    big['fb'] = np.clip(np.digitize(big['frac'], fb), 0, len(fb))
    ucols = ['U_%d' % a for a in A2_NAMES]
    key2 = ['xb', 'A1', 'R', 'O_exc', 'fb']
    cell = big.groupby(key2)[ucols].mean()
    best2 = cell.idxmax(axis=1).str.slice(2).astype(int)
    v2 = cell.max(axis=1)
    big = big.join(v2.rename('v2'), on=key2)
    cell1 = big.groupby(['xb', 'A1'])['v2'].mean().unstack('A1')
    best1 = cell1.idxmax(axis=1)
    default2 = {1: 0, 0: 2}

    def d1(df):
        b = np.clip(np.digitize(df['x'], xb), 0, len(xb))
        return pd.Series(b).map(best1).fillna(0).to_numpy(dtype=int)

    def d2(df):
        t = pd.DataFrame({'xb': np.clip(np.digitize(df['x'], xb), 0, len(xb)), 'A1': df['A1'].to_numpy(),
                          'R': df['R'].to_numpy(), 'O_exc': df['O_exc'].to_numpy(),
                          'fb': np.clip(np.digitize(df['frac'], fb), 0, len(fb))})
        a = t.join(best2.rename('a'), on=key2)['a']
        fill = t['R'].map(default2)
        return a.fillna(fill).to_numpy(dtype=int)
    return d1, d2
