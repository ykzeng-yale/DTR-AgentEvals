"""Estimators for two-stage SMART data on agent episodes.

Conventions
-----------
One row per episode, columns of a pandas DataFrame:

  cluster : task id (episodes on the same task are NOT independent; every
            interval here resamples whole clusters)
  A1, P1  : stage-1 action (int) and the KNOWN probability with which it was
            assigned (randomisation is by design, so propensities are never
            estimated and positivity holds by construction)
  R       : response status observed after stage 1 (int). R determines the
            feasible stage-2 action set via ``feasible[R]``.
  A2, P2  : stage-2 action and its known assignment probability given R
  Y       : outcome / utility (higher is better)

plus arbitrary feature columns. ``h1_cols`` are baseline (pre-A1) features;
``h2_cols`` are features available before A2 (may include post-A1 signals).

A *regime* is a pair of vectorised functions
  d1(df) -> int array of stage-1 actions
  d2(df) -> int array of stage-2 actions (must lie in feasible[R] row-wise)
that read only columns available at that stage.

Estimators
----------
ipw_value   Hajek-normalised inverse-probability-weighted value of a regime.
aipw_value  Sequentially doubly-robust (augmented) value; with known
            propensities it is consistent for ANY outcome model and the
            outcome model only buys variance. Cross-fitted by cluster.
q_learning  Backward-induction Q-learning returning a tailored regime.
cluster_bootstrap  Percentile intervals resampling clusters.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

Regime = tuple  # (d1, d2)


# --------------------------------------------------------------------------
# regimes
# --------------------------------------------------------------------------
def static_regime(a1: int, a2_by_r: Dict[int, int]) -> Regime:
    """Embedded regime: fixed a1, and a fixed a2 for each response status."""
    def d1(df):
        return np.full(len(df), a1, dtype=int)

    def d2(df):
        return df['R'].map(a2_by_r).to_numpy(dtype=int)
    return d1, d2


def consistent(df: pd.DataFrame, regime: Regime) -> np.ndarray:
    d1, d2 = regime
    return (df['A1'].to_numpy() == d1(df)) & (df['A2'].to_numpy() == d2(df))


# --------------------------------------------------------------------------
# IPW
# --------------------------------------------------------------------------
def ipw_value(df: pd.DataFrame, regime: Regime, y: str = 'Y') -> float:
    c = consistent(df, regime).astype(float)
    w = c / (df['P1'].to_numpy() * df['P2'].to_numpy())
    s = w.sum()
    return float((w * df[y].to_numpy()).sum() / s) if s > 0 else float('nan')


# --------------------------------------------------------------------------
# outcome models: ridge on [phi(h), one-hot(a), phi(h) x one-hot(a)]
# --------------------------------------------------------------------------
@dataclass
class ArmwiseRidge:
    """Separate ridge regression of the target on features within each action.

    Arm-wise fitting is the saturated-in-action model, so treatment-by-feature
    interactions (the tailoring signal) are never shrunk toward a common slope.
    Arms unseen in training fall back to the pooled mean.
    """
    alpha: float = 1.0
    models: dict = field(default_factory=dict)
    fallback: float = 0.0

    def fit(self, X: np.ndarray, a: np.ndarray, t: np.ndarray):
        self.fallback = float(np.mean(t)) if len(t) else 0.0
        self.models = {}
        for arm in np.unique(a):
            m = a == arm
            if m.sum() >= max(5, X.shape[1] + 1) and np.ptp(t[m]) > 0:
                self.models[int(arm)] = Ridge(alpha=self.alpha).fit(X[m], t[m])
            else:
                self.models[int(arm)] = float(np.mean(t[m]))
        return self

    def predict(self, X: np.ndarray, a: np.ndarray) -> np.ndarray:
        out = np.full(len(X), self.fallback, dtype=float)
        for arm in np.unique(a):
            m = a == arm
            mod = self.models.get(int(arm))
            if mod is None:
                continue
            out[m] = mod if isinstance(mod, float) else mod.predict(X[m])
        return out


def _feat(df: pd.DataFrame, cols: Sequence[str]) -> np.ndarray:
    if not cols:
        return np.zeros((len(df), 0))
    return df[list(cols)].to_numpy(dtype=float)


def _fit_q2(df, h2_cols, y, alpha):
    """One arm-wise model per response stratum (feasible sets differ by R)."""
    q2 = {}
    for r, g in df.groupby('R'):
        q2[int(r)] = ArmwiseRidge(alpha).fit(_feat(g, h2_cols), g['A2'].to_numpy(), g[y].to_numpy(dtype=float))
    return q2


def _pred_q2(q2, df, h2_cols, a2: np.ndarray) -> np.ndarray:
    out = np.zeros(len(df))
    R = df['R'].to_numpy()
    X = _feat(df, h2_cols)
    for r, mod in q2.items():
        m = R == r
        if m.any():
            out[m] = mod.predict(X[m], a2[m])
    return out


# --------------------------------------------------------------------------
# AIPW (sequentially doubly robust), cross-fitted by cluster
# --------------------------------------------------------------------------
def _folds(clusters: np.ndarray, k: int, rng) -> np.ndarray:
    u = np.unique(clusters)
    perm = rng.permutation(len(u))
    fold_of = {c: i % k for i, c in zip(range(len(u)), u[perm])}
    return np.array([fold_of[c] for c in clusters])


def aipw_value(df: pd.DataFrame, regime: Regime, h1_cols: Sequence[str], h2_cols: Sequence[str],
               y: str = 'Y', k: int = 5, alpha: float = 1.0, seed: int = 0) -> float:
    """V = mean[ Q1(H1,d1) + C1/p1 (Q2(H2,d2) - Q1(H1,d1)) + C1C2/(p1p2) (Y - Q2(H2,d2)) ]."""
    d1, d2 = regime
    rng = np.random.default_rng(seed)
    df = df.reset_index(drop=True)
    fold = _folds(df['cluster'].to_numpy(), k, rng)
    psi = np.zeros(len(df))
    for f in range(k):
        tr, te = df[fold != f], df[fold == f]
        if len(te) == 0:
            continue
        q2 = _fit_q2(tr, h2_cols, y, alpha)
        # regime-specific stage-1 pseudo-outcome on the training fold
        v2_tr = _pred_q2(q2, tr, h2_cols, d2(tr))
        q1 = ArmwiseRidge(alpha).fit(_feat(tr, h1_cols), tr['A1'].to_numpy(), v2_tr)
        a1d, a2d = d1(te), d2(te)
        Q1 = q1.predict(_feat(te, h1_cols), a1d)
        Q2 = _pred_q2(q2, te, h2_cols, a2d)
        C1 = (te['A1'].to_numpy() == a1d).astype(float)
        C2 = (te['A2'].to_numpy() == a2d).astype(float)
        p1, p2 = te['P1'].to_numpy(), te['P2'].to_numpy()
        psi[fold == f] = Q1 + C1 / p1 * (Q2 - Q1) + C1 * C2 / (p1 * p2) * (te[y].to_numpy(dtype=float) - Q2)
    return float(psi.mean())


# --------------------------------------------------------------------------
# Q-learning
# --------------------------------------------------------------------------
@dataclass
class QLearned:
    q2: dict
    q1: ArmwiseRidge
    h1_cols: List[str]
    h2_cols: List[str]
    feasible: Dict[int, List[int]]
    a1_set: List[int]

    def d2(self, df: pd.DataFrame) -> np.ndarray:
        R = df['R'].to_numpy()
        best = np.zeros(len(df), dtype=int)
        bestv = np.full(len(df), -np.inf)
        for r, arms in self.feasible.items():
            m = R == r
            if not m.any():
                continue
            sub = df[m]
            for a in arms:
                v = _pred_q2(self.q2, sub, self.h2_cols, np.full(len(sub), a))
                upd = v > bestv[m]
                idx = np.where(m)[0][upd]
                best[idx] = a
                bestv[idx] = v[upd]
        return best

    def v2(self, df: pd.DataFrame) -> np.ndarray:
        return _pred_q2(self.q2, df, self.h2_cols, self.d2(df))

    def d1(self, df: pd.DataFrame) -> np.ndarray:
        X = _feat(df, self.h1_cols)
        vals = np.stack([self.q1.predict(X, np.full(len(df), a)) for a in self.a1_set], axis=1)
        return np.asarray(self.a1_set)[vals.argmax(axis=1)]

    @property
    def regime(self) -> Regime:
        return self.d1, self.d2


def q_learning(df: pd.DataFrame, h1_cols: Sequence[str], h2_cols: Sequence[str], feasible: Dict[int, List[int]],
               a1_set: Sequence[int], y: str = 'Y', alpha: float = 1.0) -> QLearned:
    q2 = _fit_q2(df, h2_cols, y, alpha)
    tmp = QLearned(q2, ArmwiseRidge(alpha), list(h1_cols), list(h2_cols), feasible, list(a1_set))
    pseudo = tmp.v2(df)
    tmp.q1 = ArmwiseRidge(alpha).fit(_feat(df, h1_cols), df['A1'].to_numpy(), pseudo)
    return tmp


# --------------------------------------------------------------------------
# cluster bootstrap
# --------------------------------------------------------------------------
def cluster_bootstrap(df: pd.DataFrame, stat: Callable[[pd.DataFrame], float], B: int = 500, seed: int = 0,
                      level: float = 0.95) -> tuple:
    rng = np.random.default_rng(seed)
    df = df.reset_index(drop=True)
    rows = [np.asarray(ix) for ix in df.groupby('cluster', sort=False).indices.values()]
    lens = np.array([len(r) for r in rows])
    n = len(rows)
    vals = []
    for _ in range(B):
        pick = rng.integers(0, n, n)
        take = np.concatenate([rows[i] for i in pick])
        b = df.iloc[take].reset_index(drop=True)
        # resampled copies are distinct clusters (matters for cross-fitting folds)
        b['cluster'] = np.repeat(np.arange(n), lens[pick])
        vals.append(stat(b))
    vals = np.asarray(vals, dtype=float)
    lo, hi = np.nanquantile(vals, [(1 - level) / 2, 1 - (1 - level) / 2])
    return float(lo), float(hi), float(np.nanstd(vals, ddof=1))
