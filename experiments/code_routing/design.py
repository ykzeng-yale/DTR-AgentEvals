"""Frozen design for the code-routing study. Run ONCE, before any model call on a design task.

Pre-draws, for every episode, the uniform numbers that decide each routing action, so that
assignment cannot depend on anything observed at run time:
  randomized log : a_t = 1{u_t < p_large}; a_0 is permuted-block within task (marginal 0.5).
  live policies  : a_t = 1{u_t < pi_t(large | state)} with the same kind of pre-drawn u_t.
Tasks are split pilot / train / confirm BY TASK, stratified by benchmark; every run of a task
stays in its partition (theory 4.1). Refuses to overwrite an existing design.
"""
from __future__ import annotations
import json

import numpy as np

from common import RESULTS, canonical_json, code_sha256, load_config, load_tasks, now_iso, sha256_bytes

LIVE_POLICIES = ['always_small', 'always_large', 'escalate_after_first_failure', 'class_tailored', 'soft_escalation_d2', 'learned']


def build(cfg: dict, tasks: list) -> dict:
    rng = np.random.default_rng(cfg['design_seed'])
    K, m, pl = cfg['horizon'], cfg['runs_per_task'], cfg['p_large']
    uids = sorted(t['uid'] for t in tasks); bench = {t['uid']: t['benchmark'] for t in tasks}
    perm = [uids[i] for i in rng.permutation(len(uids))]
    pilot, rest = sorted(perm[:cfg['n_pilot_tasks']]), perm[cfg['n_pilot_tasks']:]
    frac = cfg['n_train_tasks'] / len(rest); split = {}
    for bname in sorted(set(bench.values())):
        ub = [u for u in rest if bench[u] == bname]
        k = int(round(frac * len(ub)))
        split.update({u: ('train' if j < k else 'confirm') for j, u in enumerate(ub)})
    if m % 2:
        raise SystemExit('runs_per_task must be even (blocked a_0)')
    log = []
    for u in sorted(rest):
        block = np.array([0, 1] * (m // 2)); rng.shuffle(block)
        for r in range(m):
            us = rng.random(K).tolist()
            us[0] = float(pl / 2 if block[r] == 1 else (1 + pl) / 2)      # forces a_0 = block[r] under a_0 = 1{u_0 < p_large}
            log.append(dict(episode_id='log:%s#%d' % (u, r), task_uid=u, run=r, split=split[u], policy='randomized_log',
                            u=us, a0_block=int(block[r]), seed=int(rng.integers(1, 2**31 - 1))))
    live = []
    for u in sorted(x for x in rest if split[x] == 'confirm'):
        for p in LIVE_POLICIES:
            for r in range(cfg['live_runs_per_task']):
                live.append(dict(episode_id='live:%s:%s#%d' % (p, u, r), task_uid=u, run=r, split='confirm', policy=p,
                                 u=rng.random(K).tolist(), seed=int(rng.integers(1, 2**31 - 1))))
    for name, eps in (('log', log), ('live', live)):
        for k, i in enumerate(rng.permutation(len(eps))):
            eps[int(i)]['run_order'] = int(k)
    return dict(schema=1, experiment=cfg['experiment'], created_utc=now_iso(), config_sha256=cfg['_config_sha256'],
                tasks_sha256=tasks[0]['_tasks_sha256'], design_seed=cfg['design_seed'], p_large=pl, horizon=K,
                pilot_tasks=pilot, train_tasks=sorted(u for u in rest if split[u] == 'train'),
                confirm_tasks=sorted(u for u in rest if split[u] == 'confirm'), live_policies=LIVE_POLICIES,
                branch_audit=dict(seed=int(rng.integers(1, 2**31 - 1)), n_prefixes=200, continuations_per_arm=2),
                log_episodes=log, live_episodes=live)


def main():
    cfg = load_config()
    out = RESULTS / 'design.json'
    if out.exists():
        raise SystemExit('design already frozen at %s; refusing to overwrite' % out)
    RESULTS.mkdir(parents=True, exist_ok=True)
    d = build(cfg, load_tasks(cfg)); d['design_code_sha256'] = code_sha256()
    body = json.dumps(d, indent=0)
    out.write_text(body); (RESULTS / 'design.sha256').write_text(sha256_bytes(body.encode()) + '\n')
    print(json.dumps(dict(n_pilot=len(d['pilot_tasks']), n_train=len(d['train_tasks']), n_confirm=len(d['confirm_tasks']),
                          n_log_episodes=len(d['log_episodes']), n_live_episodes=len(d['live_episodes']))))


if __name__ == '__main__':
    main()
