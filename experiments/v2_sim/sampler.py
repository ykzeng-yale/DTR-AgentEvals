"""DTR-REQ-003: complete-block sampler and estimator wiring, first bounded slice (lead 0cd1fef / fresh_reference review).

Every random step goes through ONE interface, draws.choose(label, options) with options = [(outcome, probability)], and
the label always starts with the episode's STREAM id. Two draw sources ship with this slice:
  ScriptedDraws   deterministic fixtures: per-stream lists of uniforms, mapped to outcomes by cumulative probability;
  exhaustive()    visits EVERY branch of the same sampler code with its exact probability, so expectations computed
                  through the sampler can be compared exactly with the accepted known-kernel truth. No Monte Carlo.
A seeded pseudo-random source is deliberately NOT included: no Monte Carlo run is authorized.

Wired in this slice (accepted repair kernels, common-initial-small model):
  run_episode       one episode under a LOGGER (records the probability of each logged action) or a frozen POLICY
                    (fresh, deterministic, probability 1); exits: first_call_pass, true_pass, false_pass, K_exhausted;
                    every call cost is retained, including the common first call
  run_blocks        every task of the frozen list x r replicates, each with its own stream id '<mode>:<task>:<rep>';
                    nothing is dropped (absorbed episodes included)
  ipw_estimate      (1/n) sum_g (1/r) sum_j W Z with the trajectory weight recomputed from the recorded history
  fresh_estimate    (1/n) sum_g (1/r) sum_j Z
NOT wired yet (listed explicitly): the 4/4 archive branch source sampler and the Delta estimator with the frame_rule
whole-range fallback (next slice); DR and outcome-regression estimators; per-decision cost estimator in sampled form;
variance, interval and covariance-based contrast estimators; any seeded stream source.
"""
from __future__ import annotations
from fractions import Fraction as Fr

import repair_generator as G


class Branch(Exception):
    def __init__(self, options):
        self.options = options


class ScriptedDraws:
    def __init__(self, script):
        self.script = {k: list(v) for k, v in script.items()}   # stream id -> uniforms in [0, 1)
        self.used = []

    def choose(self, label, options):
        stream = label[0]
        u = self.script[stream].pop(0)
        acc = Fr(0)
        for outcome, p in options:
            if p == 0:
                continue
            acc += p
            if u < acc:
                self.used.append((label, outcome))
                return outcome
        raise ValueError('uniform %r outside the option mass at %r' % (u, label))


class _PathDraws:
    def __init__(self, path):
        self.path, self.i, self.prob = path, 0, Fr(1)

    def choose(self, label, options):
        live = [(o, p) for o, p in options if p]
        if self.i == len(self.path):
            raise Branch(live)
        o, p = live[self.path[self.i]]
        self.i += 1; self.prob *= p
        return o


def exhaustive(run):
    """Yield (probability, result) for every complete branch of run(draws), re-running the same sampler code."""
    stack = [[]]
    while stack:
        path = stack.pop()
        d = _PathDraws(path)
        try:
            result = run(d)
        except Branch as b:
            stack.extend(path + [k] for k in range(len(b.options)))
            continue
        yield d.prob, result


def run_episode(cell, s, draws, stream, logger=None, policy=None):
    if (logger is None) == (policy is None):
        raise ValueError('exactly one of logger or policy')
    rec = dict(stream=stream, stratum=s, decisions=[], observations=[], call_costs=[G.C[0]])

    def done(exit_class, y):
        rec.update(exit=exit_class, success=y, cost=sum(rec['call_costs']))
        rec['utility'] = y - rec['cost']
        return rec

    if draws.choose((stream, 'first_call'), [(1, G.P0[s]), (0, 1 - G.P0[s])]):
        return done('first_call_pass', 1)
    u = draws.choose((stream, 'U0'), [(1, G.DEEP0[s]), (0, 1 - G.DEEP0[s])])
    o = draws.choose((stream, 'O0'), [(x, cell.p_obs(x, u, s)) for x in G.OBS])
    rec['observations'].append(o)
    if o == 'pass':
        return done('false_pass', 0)
    key = policy.init_key(s, o, None) if policy else None
    for t in range(1, cell.K + 1):
        if logger:
            p1 = logger(s, t, o)
            a = draws.choose((stream, 'A', t), [(1, p1), (0, 1 - p1)])
            p_a = p1 if a else 1 - p1
        else:
            a, p_a = policy.act(s, t, key), Fr(1)
        rec['decisions'].append(dict(t=t, action=a, p_logged=p_a))
        rec['call_costs'].append(G.C[a])
        if draws.choose((stream, 'repair', t), [(1, cell.repair[u, a]), (0, 1 - cell.repair[u, a])]):
            return done('true_pass', 1)
        u = draws.choose((stream, 'U', t), [(1, cell.stay[u, a]), (0, 1 - cell.stay[u, a])])
        o = draws.choose((stream, 'O', t), [(x, cell.p_obs(x, u, s)) for x in G.OBS])
        rec['observations'].append(o)
        if o == 'pass':
            return done('false_pass', 0)
        if policy:
            key = policy.update(key, a, o, None)
    return done('K_exhausted', 0)


def ipw_weight(rec, pol):
    """Trajectory weight for target policy pol, recomputed from the recorded observations and logged actions."""
    if not rec['decisions']:
        return Fr(1)
    s, obs = rec['stratum'], rec['observations']
    key, w = pol.init_key(s, obs[0], None), Fr(1)
    for i, d in enumerate(rec['decisions']):
        if pol.act(s, d['t'], key) != d['action']:
            return Fr(0)
        w /= d['p_logged']
        if i + 1 < len(obs):
            key = pol.update(key, d['action'], obs[i + 1], None)
    return w


def run_blocks(tasks, cell, r, draws, mode, logger=None, policy=None):
    """tasks: [(task_id, stratum)]; every task x replicate yields one retained episode with its own stream id."""
    out = []
    for task_id, s in tasks:
        for j in range(r):
            stream = '%s:%s:%d' % (mode, task_id, j)
            rec = run_episode(cell, s, draws, stream, logger=logger, policy=policy)
            rec.update(task_id=task_id, replicate=j)
            out.append(rec)
    return out


def _task_means(episodes, value):
    by = {}
    for e in episodes:
        by.setdefault(e['task_id'], []).append(value(e))
    return [sum(v) / len(v) for v in by.values()]


def ipw_estimate(episodes, pol):
    m = _task_means(episodes, lambda e: ipw_weight(e, pol) * e['utility'])
    return sum(m) / len(m)


def fresh_estimate(episodes):
    m = _task_means(episodes, lambda e: e['utility'])
    return sum(m) / len(m)
