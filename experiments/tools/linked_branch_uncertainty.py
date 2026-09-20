"""Branch-vs-log agreement with the two sources treated as LINKED, not independent.

The published branch report compares the forked contrast with the log-based contrast using se = sqrt(se_b^2 + se_l^2),
i.e. assuming independence. They are not independent: branch prefixes are sampled FROM the confirm log episodes, so
both estimates are built on the same tasks. The theory workstream asked for the linkage to be accounted for
(docs/theory_feedback_20260920.md). This recomputes the comparison on the 103 tasks that carry branch data, forming
ONE difference per task and clustering over tasks, so the covariance is handled by construction.

Post-hoc reporting only; lives outside the directories hashed into code_sha256 and changes no frozen record.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments' / 'code_routing')); sys.path.insert(0, str(ROOT / 'experiments' / 'common'))
import common, analysis as A  # noqa: E402


def main():
    cfg = common.load_config()
    log, _ = A.read(common.RESULTS / 'log' / 'episodes.jsonl', cfg)
    br, _ = A.read(common.RESULTS / 'branch' / 'episodes.jsonl', cfg)
    plan = {p['episode_id']: p for p in json.loads((common.RESULTS / 'branch' / 'branch_plan.json').read_text())['episodes']}

    # branch: one stay-large minus stay-small difference per prefix, then per task
    per_prefix = {}
    for e in br:
        pid = e.get('parent_episode_id') or plan[e['episode_id']]['parent_episode_id']
        arm = e.get('fork_arm') or ('large' if plan[e['episode_id']]['forced_arm'] else 'small')
        per_prefix.setdefault((e['task_uid'], pid), {}).setdefault(arm, []).append(e['success'])
    b_task = {}
    for (task, _pid), d in per_prefix.items():
        if 'large' in d and 'small' in d:
            b_task.setdefault(task, []).append(np.mean(d['large']) - np.mean(d['small']))
    b_task = {t: float(np.mean(v)) for t, v in b_task.items()}

    # log: the same contrast, Hajek IPW over episodes that reached a second decision, per task
    l_task = {}
    for e in log:
        if e['split'] != 'confirm' or e['n_decisions'] < 2:
            continue
        ds = e['decisions']
        a1 = ds[1]['a']; a2 = ds[2]['a'] if len(ds) > 2 else None
        w = (1.0 / 0.5) * (1.0 if a2 is None else (1.0 / 0.5 if a2 == a1 else 0.0))
        if w == 0:
            continue
        l_task.setdefault(e['task_uid'], {}).setdefault(a1, []).append((w, e['success']))
    l_hat = {}
    for t, d in l_task.items():
        if 0 in d and 1 in d:
            v = {a: sum(w * s for w, s in d[a]) / sum(w for w, _ in d[a]) for a in (0, 1)}
            l_hat[t] = v[1] - v[0]

    common_tasks = sorted(set(b_task) & set(l_hat))
    b = np.array([b_task[t] for t in common_tasks]); l = np.array([l_hat[t] for t in common_tasks])
    d = b - l
    out = dict(n_tasks_linked=len(common_tasks), branch_mean=float(b.mean()), branch_se=float(b.std(ddof=1) / np.sqrt(len(b))),
               log_mean=float(l.mean()), log_se=float(l.std(ddof=1) / np.sqrt(len(l))),
               paired_difference=float(d.mean()), paired_se=float(d.std(ddof=1) / np.sqrt(len(d))),
               correlation=float(np.corrcoef(b, l)[0, 1]),
               independence_se=float(np.sqrt((b.std(ddof=1) / np.sqrt(len(b))) ** 2 + (l.std(ddof=1) / np.sqrt(len(l))) ** 2)))
    out['paired_lower'] = out['paired_difference'] - 1.96 * out['paired_se']
    out['paired_upper'] = out['paired_difference'] + 1.96 * out['paired_se']
    (common.RESULTS / 'analysis' / 'branch_vs_log_linked.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
