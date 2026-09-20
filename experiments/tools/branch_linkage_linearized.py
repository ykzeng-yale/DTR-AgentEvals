"""Target-preserving uncertainty for the branch-vs-log comparison.

An earlier attempt (branch_vs_log_linked.json) restricted to the 42 tasks where both quantities are estimable AND
switched to equal-task weighting. That changed the ESTIMAND, not just the variance: the theory workstream's review
(docs/theory_feedback_20260920_branch.md) decomposes the shift as
    pooled                                   0.120000 - 0.134654 = -0.014654
    original weighting, 42 tasks             0.086735 - 0.143393 = -0.056659
    equal-task weighting, 42 tasks           0.096825 - 0.188265 = -0.091440
so most of the movement is re-targeting, not linkage. This script keeps the ORIGINAL pooled estimators and all 330
source tasks, and derives the first-order task-cluster influence contribution of their difference, following the
identity supplied in that review:

    B_hat  = sum_g A_g / m,                  m = sum_g m_g          (prefix mean of branch contrasts)
    v_a    = sum_g N_ga / D_a,               D_a = sum_g D_ga       (pooled Hajek log ratio for staying with arm a)
    Delta  = B_hat - (v_1 - v_0)
    U_g    = (A_g - B_hat*m_g)/m - (N_g1 - v_1*D_g1)/D_1 + (N_g0 - v_0*D_g0)/D_0,      sum_g U_g = 0

The identity is verified here by central differences over all source-task multipliers. It is an algebraic identity,
NOT a completed variance theorem for this design: the 200-of-564 prefix sample is a second sampling stage without
replacement, continuations are replicated within a prefix, and prefix selection is dependent across tasks. The
interval printed below is therefore a first-order approximation that ignores those features and is labelled as such.

Post-hoc reporting only; outside the directories hashed into code_sha256; changes no frozen record.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments' / 'code_routing')); sys.path.insert(0, str(ROOT / 'experiments' / 'common'))
import common, analysis as A  # noqa: E402


def gather():
    cfg = common.load_config()
    log, _ = A.read(common.RESULTS / 'log' / 'episodes.jsonl', cfg)
    br, _ = A.read(common.RESULTS / 'branch' / 'episodes.jsonl', cfg)
    plan = {p['episode_id']: p for p in json.loads((common.RESULTS / 'branch' / 'branch_plan.json').read_text())['episodes']}
    tasks = sorted({e['task_uid'] for e in log if e['split'] == 'confirm'})      # ALL source tasks
    idx = {t: i for i, t in enumerate(tasks)}
    G = len(tasks)
    Ag, mg = np.zeros(G), np.zeros(G)
    per_prefix = {}
    for e in br:
        pid = e.get('parent_episode_id') or plan[e['episode_id']]['parent_episode_id']
        arm = e.get('fork_arm') or ('large' if plan[e['episode_id']]['forced_arm'] else 'small')
        per_prefix.setdefault((e['task_uid'], pid), {}).setdefault(arm, []).append(e['success'])
    for (task, _pid), d in per_prefix.items():
        if 'large' in d and 'small' in d:
            Ag[idx[task]] += float(np.mean(d['large']) - np.mean(d['small'])); mg[idx[task]] += 1.0
    N = {0: np.zeros(G), 1: np.zeros(G)}; D = {0: np.zeros(G), 1: np.zeros(G)}
    for e in log:
        if e['split'] != 'confirm' or e['n_decisions'] < 2:
            continue
        ds = e['decisions']; a1 = ds[1]['a']; a2 = ds[2]['a'] if len(ds) > 2 else None
        w = 2.0 * (1.0 if a2 is None else (2.0 if a2 == a1 else 0.0))
        if w == 0:
            continue
        g = idx[e['task_uid']]
        N[a1][g] += w * e['success']; D[a1][g] += w
    return tasks, Ag, mg, N, D


def delta(Ag, mg, N, D, h=None):
    w = 1.0 + (0.0 if h is None else h)
    m = float((w * mg).sum()); B = float((w * Ag).sum()) / m
    v = {a: float((w * N[a]).sum()) / float((w * D[a]).sum()) for a in (0, 1)}
    return B - (v[1] - v[0]), B, v


def main():
    tasks, Ag, mg, N, D = gather()
    G = len(tasks)
    d0, B, v = delta(Ag, mg, N, D)
    m = mg.sum(); D1, D0 = D[1].sum(), D[0].sum()
    U = (Ag - B * mg) / m - (N[1] - v[1] * D[1]) / D1 + (N[0] - v[0] * D[0]) / D0
    # verify the identity by central differences over every source-task multiplier
    eps, errs = 1e-6, []
    for g in range(G):
        h = np.zeros(G); h[g] = 1.0
        num = (delta(Ag, mg, N, D, eps * h)[0] - delta(Ag, mg, N, D, -eps * h)[0]) / (2 * eps)
        errs.append(abs(num - U[g]))
    se = float(np.sqrt((U ** 2).sum()))
    out = dict(n_source_tasks=G, n_prefixes=int(mg.sum()), branch_estimate=B, log_v_large=v[1], log_v_small=v[0],
               log_estimate=v[1] - v[0], difference=d0, sum_U=float(U.sum()), max_identity_error=float(max(errs)),
               linearized_se=se, lower=d0 - 1.96 * se, upper=d0 + 1.96 * se,
               tasks_contributing_branch=int((mg > 0).sum()), tasks_contributing_log=int(((D[1] > 0) & (D[0] > 0)).sum()),
               caveat='first-order task-cluster approximation; ignores without-replacement prefix sampling (200 of 564), '
                      'replication of continuations within a prefix, and cross-task selection dependence; not a design-aware interval')
    (common.RESULTS / 'analysis' / 'branch_vs_log_linearized.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
