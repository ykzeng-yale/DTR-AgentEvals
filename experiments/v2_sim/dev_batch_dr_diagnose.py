"""Focused diagnosis of the fitted-OR bias in the paired DR/OR batch (lead c0c39a8: "diagnose the resulting pattern before
increasing sample size or adding models"). No new data: every log is regenerated bit-for-bit from the frozen seeds, and
the task folds are exactly those of estimators_absorbing.cluster_scores (seed = repetition index, 3 folds).

For each repetition, cell and policy it counts the test-fold decisions whose (observed-history key, target action) Q cell
is EMPTY in the training folds. There the tabular fit falls back to a pooled stage/action mean. It then compares the
OR error in repetitions with and without any such fallback. Hypothesis under test: the OR bias comes from sparse-support
fallbacks under the feedback-dependent logger, not from the identification or the bridge.
Output: results/v2_sim/dev_batch_dr_20260921/or_bias_diagnosis.json
"""
from __future__ import annotations
import json
from fractions import Fraction
from pathlib import Path

import numpy as np

import dev_batch as D
import dr_bridge as DB
import fixed_task_blocks as B
import repair_generator as G
import repair_logger as L
import sampler as S

OUT = D.ROOT / 'results' / 'v2_sim' / 'dev_batch_dr_20260921' / 'or_bias_diagnosis.json'


def fallback_count(logs, pol, seed, folds=3):
    tasks = np.unique(logs.task)
    fold_of = dict(zip(tasks[np.random.default_rng(seed).permutation(len(tasks))], np.arange(len(tasks)) % folds))
    f = np.array([fold_of[t] for t in logs.task])
    pp = DB.prob_policy(pol)
    n = 0
    for k in range(folds):
        tr, te = np.nonzero(f != k)[0], np.nonzero(f == k)[0]
        seen = {(t, logs.key[i, t], logs.a[i, t]) for i in tr for t in range(logs.a.shape[1]) if logs.elig[i, t]}
        for i in te:
            for t in range(logs.a.shape[1]):
                if logs.elig[i, t] and (t, logs.key[i, t], int(pp(logs.state[i, t]))) not in seen:
                    n += 1
    return n


def main():
    reps = {(r['config'], r['repetition']): r for r in map(json.loads, (D.ROOT / 'results/v2_sim/dev_batch_dr_20260921/reps.jsonl').read_text().splitlines())}
    kernel = json.loads(G.OUT.read_text())
    tasks, _ = B.task_list(D.N_TASKS)
    cat = {p.name: p for p in G.catalog(2)}
    rows = []
    for c in D.cells():
        cell = G.Cell(2, 'crossing', c['feedback'])
        kc = next(k for k in kernel['cells'] if (k['K'], k['action_effect'], k['feedback']) == (2, 'crossing', c['feedback']))
        per = {p: [] for p in c['policies']}
        for b in range(D.R_REPS):
            log = S.run_blocks(tasks, cell, D.R_LOG, S.SeededDraws(D.ROOT_SEED), S.stream_namespace(c['config'], b), 'log',
                               logger=L.LOGGERS[c['logger']], logger_name=c['logger'])
            logs = DB.to_logs(log, cell.K)
            for p in c['policies']:
                per[p].append((fallback_count(logs, cat[p], b), reps[(c['config'], b)]['policies'][p]['or_plugin']))
        for p, v in per.items():
            truth = float(Fraction(kc['policies'][p]['utility']['exact']))
            cnt = np.array([x for x, _ in v]); err = np.array([o - truth for _, o in v])
            with_fb, without = err[cnt > 0], err[cnt == 0]

            def ms(a):
                return None if len(a) < 2 else dict(n=int(len(a)), mean_error=float(a.mean()), mcse=float(a.std(ddof=1) / np.sqrt(len(a))))
            rows.append(dict(config=c['config'], policy=p, repetitions=len(v),
                             reps_with_any_fallback=int((cnt > 0).sum()), mean_fallback_decisions=float(cnt.mean()),
                             or_error_all=ms(err), or_error_with_fallback=ms(with_fb), or_error_without_fallback=ms(without),
                             corr_fallback_count_vs_error=float(np.corrcoef(cnt, err)[0, 1]) if cnt.std() > 0 else None))
    OUT.write_text(json.dumps(dict(
        purpose='diagnose fitted-OR bias (lead c0c39a8); logs regenerated bit-for-bit from the frozen seeds; no new data',
        fallback_definition='a test-fold decision whose (stage, observed-history key, target action) cell has no training '
                            'observation, so the tabular Q uses the pooled stage/action fallback mean',
        rows=rows), indent=1) + '\n')
    for r in rows:
        w, o = r['or_error_with_fallback'], r['or_error_without_fallback']
        print('%-44s %-30s reps_with_fallback=%3d  err_with=%s  err_without=%s' % (
            r['config'][12:], r['policy'], r['reps_with_any_fallback'],
            'n/a' if not w else '%+.5f(%.5f)' % (w['mean_error'], w['mcse']),
            'n/a' if not o else '%+.5f(%.5f)' % (o['mean_error'], o['mcse'])))


# ---- PREPARED, NOT RUN: targeted confirmation proposed to the lead (checkpoint 13:49 UTC); run only after the lead answers ----
def or_plugin_with_stage2_q(train, test, pol, stage2_q):
    """OR plug-in for stage 0 (the first decision), fitted exactly as estimators_absorbing.fit_q does it, except that
    the stage-1 continuation values come from `stage2_q` (key -> {a: value}) instead of a fitted table. Returns the
    per-test-unit plug-in V_0 (0 for units without a first decision). With stage2_q equal to the fitted stage-1 table
    this reproduces the standard plug-in, which the tests check."""
    pp = DB.prob_policy(pol)
    nextv = np.zeros(len(train))
    for i in np.nonzero(train.elig[:, 1])[0]:
        q = stage2_q.get(train.key[i, 1], {})
        a = int(pp(train.state[i, 1]))
        if a not in q:
            raise KeyError('stage-2 value missing for %r, action %d: no silent default' % (train.key[i, 1], a))
        nextv[i] = q[a]
    m = train.elig[:, 0]
    y = train.r[:, 0] + nextv
    fallback = {aa: (float(y[m & (train.a[:, 0] == aa)].mean()) if (m & (train.a[:, 0] == aa)).any() else float(y[m].mean()))
                for aa in (0, 1)}
    cells = {}
    for i in np.nonzero(m)[0]:
        cells.setdefault((train.key[i, 0], train.a[i, 0]), []).append(y[i])
    q0 = {k: float(np.mean(v)) for k, v in cells.items()}
    v0 = np.zeros(len(test))
    for i in np.nonzero(test.elig[:, 0])[0]:
        a = int(pp(test.state[i, 0]))
        v0[i] = q0.get((test.key[i, 0], a), fallback[a])
    return v0


if __name__ == '__main__':
    main()
