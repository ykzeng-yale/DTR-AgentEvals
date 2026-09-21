"""DTR-REQ-003: complete-block sampler wiring, slice 2 - the archive 4/4 branch source design and the Delta estimator.

Distinct from the common-initial-small model (sampler.py). Every random step uses the same draws.choose interface with
stream-prefixed labels; every stream starts with the configuration/repetition namespace, then the role:
'<ns>|bsrc:<task>:alloc' (allocation), '<ns>|bsrc:<task>:<e>' (source episode), '<ns>|bsel' (prefix selection),
'<ns>|bfresh:<prefix>:<arm>:<j>' (fresh restored continuations).
  source block   8 episodes; A0 is a uniformly random arrangement of EXACTLY 4 small and 4 large (sequential draws with
                 remaining-count probabilities); first call by A0 correct w.p. P0A[S][A0]; a first-failure PREFIX exists
                 iff the first feedback is not a pass; zero-prefix tasks are retained. Source continuation: up to 2
                 repairs, each large w.p. 1/2 (recorded), W_a as in theory_branch_fixed_benchmark_bound.md eq. (1).
  frame/selection  N prefixes over all tasks; frame_rule decides: whole range [-2, 2] if N = 0 or an observed D_a = 0,
                 census if N <= m_max, else SRSWOR of m_max by sequential uniform draws.
  branch         for each selected prefix, r = 2 fresh replicate pairs of stay-large and stay-small continuations from the
                 restored full state (latent U included: ideal full-state restoration, a simulator choice).
  estimator      Delta_hat = B_hat - nu_hat_1 + nu_hat_0 (bound doc eq. 3), or the whole range under the fallback.
Checks: scripted fixtures for each branch of the frame rule; an exhaustive (non-Monte-Carlo) driver through the same
code reproduces branch_module's exact per-episode expectations and stay values.
"""
from __future__ import annotations
from fractions import Fraction as Fr

import branch_module as BM
import repair_generator as G

R_PAIRS = 2


def allocation(draws, task_id, namespace):
    remaining, order = {0: BM.ALLOC[0], 1: BM.ALLOC[1]}, []
    for i in range(BM.R_EPISODES):
        tot = remaining[0] + remaining[1]
        a0 = draws.choose(('%s|bsrc:%s:alloc' % (namespace, task_id), i),
                          [(1, Fr(remaining[1], tot)), (0, Fr(remaining[0], tot))])
        remaining[a0] -= 1; order.append(a0)
    return order


def source_episode(cell, s, a0, draws, stream):
    rec = dict(stream=stream, a0=a0, prefix=None)
    if draws.choose((stream, 'first_call'), [(1, BM.P0A[s][a0]), (0, 1 - BM.P0A[s][a0])]):
        return dict(rec, y=1)
    u0 = draws.choose((stream, 'U0'), [(1, G.DEEP0[s]), (0, 1 - G.DEEP0[s])])
    o0 = draws.choose((stream, 'O0'), [(x, cell.p_obs(x, u0, s)) for x in G.OBS])
    if o0 == 'pass':
        return dict(rec, y=0)
    rec['prefix'] = dict(stratum=s, u0=u0, o0=o0)              # restored full state for the branch
    u, actions = u0, []
    for t in (1, 2):
        a = draws.choose((stream, 'A', t), [(1, Fr(1, 2)), (0, Fr(1, 2))])
        actions.append(a)
        if draws.choose((stream, 'repair', t), [(1, cell.repair[u, a]), (0, 1 - cell.repair[u, a])]):
            return dict(rec, y=1, actions=actions)
        u = draws.choose((stream, 'U', t), [(1, cell.stay[u, a]), (0, 1 - cell.stay[u, a])])
        o = draws.choose((stream, 'O', t), [(x, cell.p_obs(x, u, s)) for x in G.OBS])
        if o == 'pass':
            return dict(rec, y=0, actions=actions)
    return dict(rec, y=0, actions=actions)


def log_weight(rec, arm):
    """W_a: 1{A1=a}/.5 if absorbed after the first repair, else 1{A1=a}1{A2=a}/.25; zero without a prefix."""
    acts = rec.get('actions') or []
    if rec['prefix'] is None or not acts:
        return Fr(0)
    w = Fr(1)
    for a in acts:
        w = w * 2 if a == arm else Fr(0)
    return w


def stay_continuation(cell, prefix, arm, draws, stream):
    s, u = prefix['stratum'], prefix['u0']
    for t in (1, 2):
        if draws.choose((stream, 'repair', t), [(1, cell.repair[u, arm]), (0, 1 - cell.repair[u, arm])]):
            return 1
        u = draws.choose((stream, 'U', t), [(1, cell.stay[u, arm]), (0, 1 - cell.stay[u, arm])])
        o = draws.choose((stream, 'O', t), [(x, cell.p_obs(x, u, s)) for x in G.OBS])
        if o == 'pass':
            return 0
    return 0


def run_branch_study(tasks, cell, draws, namespace, m_max=BM.M_MAX):
    """tasks: [(task_id, stratum)]. Returns the source records (all retained) and the Delta estimate or fallback."""
    source, frame = [], []
    for task_id, s in tasks:
        for e, a0 in enumerate(allocation(draws, task_id, namespace)):
            rec = source_episode(cell, s, a0, draws, '%s|bsrc:%s:%d' % (namespace, task_id, e))
            rec.update(task_id=task_id, episode=e)
            source.append(rec)
            if rec['prefix'] is not None:
                frame.append(rec)
    N = len(frame)
    D = {a: sum(log_weight(r, a) for r in frame) for a in (0, 1)}
    U = {a: sum(log_weight(r, a) * r['y'] for r in frame) for a in (0, 1)}
    action, m = BM.frame_rule(N, D[0], D[1], m_max)
    out = dict(source=source, N=N, D_small=D[0], D_large=D[1], action=action, m=m,
               tasks_retained=len({r['task_id'] for r in source}),
               zero_prefix_tasks=len({t for t, _ in tasks} - {r['task_id'] for r in frame}))
    if action.startswith('whole_range'):
        return dict(out, delta=None, delta_range=(-2, 2))
    pool = list(range(N))
    if action == 'srswor':
        chosen = []
        for k in range(m):
            idx = draws.choose(('%s|bsel' % namespace, k), [(i, Fr(1, len(pool))) for i in range(len(pool))])
            chosen.append(pool.pop(idx))
    else:
        chosen = pool
    z = []
    for i in chosen:
        pid = '%s:%d' % (frame[i]['task_id'], frame[i]['episode'])
        for j in range(R_PAIRS):
            y1 = stay_continuation(cell, frame[i]['prefix'], 1, draws, '%s|bfresh:%s:1:%d' % (namespace, pid, j))
            y0 = stay_continuation(cell, frame[i]['prefix'], 0, draws, '%s|bfresh:%s:0:%d' % (namespace, pid, j))
            z.append(y1 - y0)
    B = Fr(sum(z), len(z))
    nu = {a: U[a] / D[a] for a in (0, 1)}
    return dict(out, selected=[frame[i]['stream'] for i in chosen], B_hat=B, nu_large=nu[1], nu_small=nu[0],
                delta=B - nu[1] + nu[0], delta_range=None)
