"""DTR-REQ-003: retrospective stage-2-Q intervention on the fitted OR plug-in (authorized by lead 9f9308e).

A RETROSPECTIVE DEVELOPMENT DIAGNOSTIC, not a confirmation study; the known-Q intervention is an oracle unavailable in
deployment. Same regenerated logs (seed 2026092101, identical namespaces), same task folds (seed = repetition index,
3 folds), same policies and 800 cell/repetition IDs as the paired DR/OR batch. No new random data.
Per repetition, cell and policy:
  - trajectory IPW recomputed and compared with dev_batch reps.jsonl (acceptance: |diff| <= 1e-12);
  - STANDARD fitted OR plug-in recomputed exactly as estimators_absorbing.cluster_scores does it and compared with
    dev_batch_dr reps.jsonl (acceptance: |diff| <= 1e-12);
  - ORACLE-STAGE-2 OR: first stage fitted identically, second-stage Q replaced by the exact known-kernel table
    (dev_batch_dr_diagnose.or_plugin_with_stage2_q; missing values raise).
Interpretation limits (lead): a reduced bias shows that second-stage estimation CONTRIBUTES in this implementation.
It does NOT confirm sparse-cell fallback specifically, because replacing the whole stage-2 table changes non-fallback
estimates too.
  python dev_batch_or_stage2.py freeze | run | analyze
"""
from __future__ import annotations
import hashlib, json, math, sys, time
from multiprocessing import Pool

import numpy as np

import dev_batch as D
import dev_batch_dr as R
import dev_batch_dr_diagnose as X
import dr_bridge as DB
import fixed_task_blocks as B
import repair_generator as G
import repair_logger as L
import sampler as S

OUT = D.ROOT / 'results' / 'v2_sim' / 'dev_batch_or_stage2_20260921'
MANIFEST, REPS = OUT / 'manifest.json', OUT / 'reps.jsonl'
HASHED = sorted(set(R.HASHED + ['experiments/v2_sim/dev_batch_or_stage2.py', 'experiments/v2_sim/dev_batch_dr_diagnose.py',
                                'results/v2_sim/dev_batch_dr_20260921/reps.jsonl',
                                'results/v2_sim/dev_batch_dr_20260921/manifest.json']))


def freeze():
    m = dict(request='DTR-REQ-003 retrospective stage-2-Q OR intervention (authorized by lead 9f9308e)',
             kind='RETROSPECTIVE DEVELOPMENT DIAGNOSTIC (oracle intervention; not a confirmation study)',
             paired_with=['results/v2_sim/dev_batch_20260921', 'results/v2_sim/dev_batch_dr_20260921'],
             root_seed=D.ROOT_SEED, repetitions_per_cell=D.R_REPS, cells=D.cells(), folds=R.FOLDS,
             fold_seed='repetition index', workers=D.WORKERS, cpu_wall_cap_seconds=D.CAP_S,
             reproduction_tolerance=1e-12, no_new_random_data=True,
             interpretation_limit='reduced bias => second-stage estimation contributes; NOT a confirmation of fallback specifically',
             source_sha256={rel: D.sha(rel) for rel in HASHED})
    OUT.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=1) + '\n')
    return m


def or_plugins(logs, pre, pol, seed, stage2):
    """Task-equal standard OR (exactly as cluster_scores) and oracle-stage-2 OR, on identical folds."""
    tasks = np.unique(logs.task)
    fold_of = dict(zip(tasks[np.random.default_rng(seed).permutation(len(tasks))], np.arange(len(tasks)) % R.FOLDS))
    f = np.array([fold_of[t] for t in logs.task])
    std, orc = np.zeros(len(logs.task)), np.zeros(len(logs.task))
    pp = DB.prob_policy(pol)
    for k in range(R.FOLDS):
        te, tr = np.nonzero(f == k)[0], np.nonzero(f != k)[0]
        train, test = logs.subset(tr), logs.subset(te)
        Q, fb, _ = DB.EA.fit_q(train, pp)
        _, std[te] = DB.EA.dr_scores(test, pp, Q, fb)
        orc[te] = X.or_plugin_with_stage2_q(train, test, pol, stage2)
    _, s_std = DB.EA.cluster_means(logs.task, std + pre)
    _, s_orc = DB.EA.cluster_means(logs.task, orc + pre)
    return float(s_std.mean()), float(s_orc.mean())


def job(arg):
    cell_spec, b, orig_ipw, orig_or = arg
    t0 = time.process_time()
    cell = G.Cell(2, 'crossing', cell_spec['feedback'])
    tasks, _ = B.task_list(D.N_TASKS)
    cat = {p.name: p for p in G.catalog(2)}
    log = S.run_blocks(tasks, cell, D.R_LOG, S.SeededDraws(D.ROOT_SEED), S.stream_namespace(cell_spec['config'], b), 'log',
                       logger=L.LOGGERS[cell_spec['logger']], logger_name=cell_spec['logger'])
    logs = DB.to_logs(log, cell.K)
    pre = np.array([float(DB.z_pre(e)) for e in log])
    rec = dict(config=cell_spec['config'], repetition=b, policies={})
    for name in cell_spec['policies']:
        pol = cat[name]
        ipw = float(S.ipw_estimate(log, pol, tasks, D.R_LOG))
        Qk, _ = DB.known_kernel_q(cell, pol)
        or_std, or_orc = or_plugins(logs, pre, pol, b, Qk[1])
        rec['policies'][name] = dict(ipw=ipw, or_standard=or_std, or_oracle_stage2=or_orc,
                                     ipw_reproduction_abs_diff=abs(ipw - orig_ipw[name]) if orig_ipw else None,
                                     or_reproduction_abs_diff=abs(or_std - orig_or[name]) if orig_or else None)
    rec['cpu_seconds'] = time.process_time() - t0
    return rec


def run():
    if not MANIFEST.exists():
        raise SystemExit('no frozen manifest: freeze, commit and push first')
    m = json.loads(MANIFEST.read_text())
    changed = [rel for rel, h in m['source_sha256'].items() if D.sha(rel) != h]
    if changed:
        raise SystemExit('refusing to run: files changed since the manifest was frozen: %s' % changed)
    ipw0 = {(r['config'], r['repetition']): {k: v['ipw'] for k, v in r['policies'].items()} for r in map(json.loads, D.REPS.read_text().splitlines())}
    or0 = {(r['config'], r['repetition']): {k: v['or_plugin'] for k, v in r['policies'].items()} for r in map(json.loads, R.REPS.read_text().splitlines())}
    done = {(r['config'], r['repetition']) for r in map(json.loads, REPS.read_text().splitlines())} if REPS.exists() else set()
    todo = [(c, b, ipw0[(c['config'], b)], or0[(c['config'], b)]) for b in range(m['repetitions_per_cell'])
            for c in m['cells'] if (c['config'], b) not in done]
    start, completed, stopped = time.time(), 0, False
    with Pool(m['workers']) as pool, REPS.open('a') as fh:
        for rec in pool.imap_unordered(job, todo, chunksize=1):
            rec['wall_seconds_since_start'] = time.time() - start
            fh.write(json.dumps(rec) + '\n'); fh.flush(); completed += 1
            if time.time() - start > m['cpu_wall_cap_seconds']:
                stopped = True; pool.terminate(); break
    (OUT / 'run_status.json').write_text(json.dumps(dict(wall_seconds=time.time() - start, completed_this_invocation=completed,
                                                          jobs_requested=len(todo), stopped_by_cap=stopped), indent=1) + '\n')
    print('completed %d of %d jobs in %.1f s%s' % (completed, len(todo), time.time() - start, ' (CAP REACHED)' if stopped else ''))


def analyze():
    m = json.loads(MANIFEST.read_text())
    reps = [json.loads(x) for x in REPS.read_text().splitlines()]
    kernel = json.loads(G.OUT.read_text())
    rows = []
    for c in m['cells']:
        rs = [r for r in reps if r['config'] == c['config']]
        if len({r['repetition'] for r in rs}) != len(rs):
            raise SystemExit('duplicate repetitions for %s' % c['config'])
        kc = next(k for k in kernel['cells'] if (k['K'], k['action_effect'], k['feedback']) == (2, 'crossing', c['feedback']))
        for name in c['policies']:
            truth = float(G.Fr(kc['policies'][name]['utility']['exact'])); n = len(rs)
            std = np.array([r['policies'][name]['or_standard'] for r in rs]) - truth
            orc = np.array([r['policies'][name]['or_oracle_stage2'] for r in rs]) - truth
            d = orc - std

            def s(v):
                return dict(mean=float(v.mean()), mcse=float(v.std(ddof=1) / math.sqrt(n)), rmse=float(math.sqrt((v ** 2).mean())))
            rows.append(dict(config=c['config'], policy=name, repetitions=n, exact_truth=truth,
                             or_standard_error=s(std), or_oracle_stage2_error=s(orc),
                             paired_difference_oracle_minus_standard=dict(mean=float(d.mean()), mcse=float(d.std(ddof=1) / math.sqrt(n))),
                             max_ipw_reproduction_abs_diff=max(r['policies'][name]['ipw_reproduction_abs_diff'] for r in rs),
                             max_or_reproduction_abs_diff=max(r['policies'][name]['or_reproduction_abs_diff'] for r in rs)))
    summary = dict(kind=m['kind'], interpretation_limit=m['interpretation_limit'],
                   manifest_sha256=hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
                   reps_sha256=hashlib.sha256(REPS.read_bytes()).hexdigest(), rows=rows,
                   run_status=json.loads((OUT / 'run_status.json').read_text()) if (OUT / 'run_status.json').exists() else {})
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    lines = ['# Retrospective stage-2-Q intervention on the fitted OR (DTR-REQ-003; oracle diagnostic, not confirmation)', '',
             '| Cell | Policy | Standard OR error (MCSE) / RMSE | Oracle-stage-2 OR error (MCSE) / RMSE | Paired diff (MCSE) |',
             '|---|---|---|---|---|']
    for r in rows:
        a, o, d = r['or_standard_error'], r['or_oracle_stage2_error'], r['paired_difference_oracle_minus_standard']
        lines.append('| %s | %s | %+.5f (%.5f) / %.5f | %+.5f (%.5f) / %.5f | %+.5f (%.5f) |' % (
            r['config'].replace('K2-crossing-', ''), r['policy'], a['mean'], a['mcse'], a['rmse'], o['mean'], o['mcse'], o['rmse'],
            d['mean'], d['mcse']))
    (OUT / 'summary.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    {'freeze': freeze, 'run': run, 'analyze': analyze}[sys.argv[1]]()
