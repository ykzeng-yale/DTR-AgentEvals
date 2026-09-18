"""Four-state longitudinal simulator with exact dynamic-programming truth.

State (X,L): baseline difficulty and current failure. A=1 selects the costly
stronger model. L is affected by prior actions and predicts routing and reward.
This is synthetic data, never an approximation passed off as model inference.
"""
from dataclasses import dataclass
import numpy as np


def sigmoid(x):
    return 1 / (1 + np.exp(-np.asarray(x)))


@dataclass(frozen=True)
class Environment:
    horizon: int = 3
    cost: float = 0.06
    overlap: float = 0.15

    def __post_init__(self):
        if self.horizon < 1 or self.cost < 0 or not 0 < self.overlap <= .5:
            raise ValueError("Require horizon >= 1, nonnegative cost, and overlap in (0,.5]")

    def failure_probability(self, x, l, a):
        return sigmoid(-0.7 + 1.2*x + 1.6*l - 1.35*a - 0.35*a*l)

    def behavior_probability(self, x, l, t):
        raw = sigmoid(-1.1 + 1.35*l + 0.55*x + 0.25*t)
        return np.clip(raw, self.overlap, 1-self.overlap)

    def initial_failure_probability(self, x):
        return sigmoid(-0.8 + 1.2*x)

    def reward(self, next_failure, a, t):
        return -self.cost*a + ((1-next_failure) if t == self.horizon-1 else 0)


POLICIES = ("always_small", "always_large", "fixed_switch", "failure_escalation", "soft_escalation")


def policy_probability(name, x, l, t, horizon=3):
    shape = np.broadcast(np.asarray(x), np.asarray(l)).shape
    if name == "always_small":
        p = np.zeros(shape)
    elif name == "always_large":
        p = np.ones(shape)
    elif name == "fixed_switch":
        p = np.full(shape, float(t >= horizon//2))
    elif name == "failure_escalation":
        p = np.asarray(l, dtype=float)
    elif name == "soft_escalation":
        p = 0.1 + 0.8*np.asarray(l)
    else:
        raise ValueError(f"Unknown policy {name}")
    return p


@dataclass
class Trajectories:
    x: np.ndarray
    l: np.ndarray
    a: np.ndarray
    b: np.ndarray
    r: np.ndarray

    def subset(self, indices):
        return Trajectories(*(getattr(self, k)[indices] for k in ("x", "l", "a", "b", "r")))

    def __len__(self):
        return len(self.x)


def simulate(n, rng, env=Environment(), policy=None):
    if n < 1:
        raise ValueError("n must be positive")
    x = rng.binomial(1, .5, n)
    l = np.zeros((n, env.horizon+1), dtype=int)
    a = np.zeros((n, env.horizon), dtype=int)
    b = np.zeros_like(a, dtype=float)
    r = np.zeros_like(b)
    l[:,0] = rng.binomial(1, env.initial_failure_probability(x))
    for t in range(env.horizon):
        p = (env.behavior_probability(x, l[:,t], t) if policy is None else
             policy_probability(policy, x, l[:,t], t, env.horizon))
        a[:,t] = rng.binomial(1,p)
        b[:,t] = np.where(a[:,t] == 1,p,1-p)
        l[:,t+1] = rng.binomial(1, env.failure_probability(x, l[:,t], a[:,t]))
        r[:,t] = env.reward(l[:,t+1], a[:,t], t)
    return Trajectories(x,l,a,b,r)


def exact_q(env, policy):
    """Return Q[t,x,l,a], V[t,x,l]; V[H] is zero by convention."""
    q = np.zeros((env.horizon,2,2,2))
    v = np.zeros((env.horizon+1,2,2))
    for t in reversed(range(env.horizon)):
        for x in (0,1):
            for l in (0,1):
                for a in (0,1):
                    pf = env.failure_probability(x,l,a)
                    q[t,x,l,a] = sum((pf if ln else 1-pf) *
                        (env.reward(ln,a,t)+v[t+1,x,ln]) for ln in (0,1))
                pa = policy_probability(policy,x,l,t,env.horizon)
                v[t,x,l] = (1-pa)*q[t,x,l,0]+pa*q[t,x,l,1]
    return q,v


def exact_value(env, policy):
    _,v = exact_q(env,policy)
    return float(sum(.5*((1-env.initial_failure_probability(x))*v[0,x,0]
                     + env.initial_failure_probability(x)*v[0,x,1]) for x in (0,1)))
