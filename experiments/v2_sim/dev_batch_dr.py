"""DTR-REQ-003: DR/OR development batch PAIRED on the identical seeded logs of dev_batch (35b2f36).

PREPARED, NOT RUN: launching needs the lead's explicit authorization (protocol section 7 says "wire ... check" for DR/OR).
Design: the same 4 cells, root seed 2026092101 and stream namespaces as dev_batch, so every logged block is regenerated
bit-for-bit. Each repetition first recomputes the trajectory IPW and records its absolute difference from the committed
dev_batch reps.jsonl (a reproduction check). It then adds, on the same log, the per-decision IPW ('pdis'), cross-fitted
task-split DR, the OR plug-in (3 task folds, fold seed = repetition index), and the known-kernel-Q DR, a separately
labelled POSITIVE CONTROL that is never fitted. No fresh blocks are rerun: fresh values are joined from dev_batch.

  python dev_batch_dr.py freeze | run | analyze        (run refuses without a frozen manifest or if hashed files changed)
"""
from __future__ import annotations
import hashlib, json, math, sys, time
from multiprocessing import Pool
from pathlib import Path

import numpy as np

import dev_batch as D
import dr_bridge as DB
import fixed_task_blocks as B
import repair_generator as G
import repair_logger as L
import sampler as S

OUT = D.ROOT / 'results' / 'v2_sim' / 'dev_batch_dr_20260921'
MANIFEST, REPS = OUT / 'manifest.json', OUT / 'reps.jsonl'
FOLDS = 3
HASHED = D.HASHED + ['experiments/v2_sim/dev_batch_dr.py', 'experiments/v2_sim/dr_bridge.py',
                     'experiments/code_routing/estimators_absorbing.py', 'results/v2_sim/dev_batch_20260921/reps.jsonl',
                     'results/v2_sim/dev_batch_20260921/manifest.json']


def freeze():
    m = dict(request='DTR-REQ-003 DR/OR development batch paired on the dev_batch logs (requires lead authorization)',
             paired_with='results/v2_sim/dev_batch_20260921 (35b2f36)', root_seed=D.ROOT_SEED,
             repetitions_per_cell=D.R_REPS, logged_per_task=D.R_LOG, n_tasks=D.N_TASKS, cells=D.cells(), folds=FOLDS,
             fold_seed='repetition index', cpu_wall_cap_seconds=D.CAP_S, workers=D.WORKERS,
             estimators=['trajectory IPW (reproduction check)', 'per-decision IPW (pdis)', 'cross-fitted task-split DR',
                         'OR plug-in (g-computation)', 'known-kernel-Q DR (POSITIVE CONTROL, not fitted)'],
             not_claimed=['interval coverage', 'adaptation benefit', 'resource efficiency', 'real-agent evidence'],
             source_sha256={rel: D.sha(rel) for rel in HASHED})
    OUT.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=1) + '\n')
    return m


def job(arg):
    cell_spec, b, original = arg
    t0 = time.process_time()
    cell = G.Cell(2, 'crossing', cell_spec['feedback'])
    tasks, _ = B.task_list(D.N_TASKS)
    cat = {p.name: p for p in G.catalog(2)}
    ns = S.stream_namespace(cell_spec['config'], b)
    log = S.run_blocks(tasks, cell, D.R_LOG, S.SeededDraws(D.ROOT_SEED), ns, 'log',
                       logger=L.LOGGERS[cell_spec['logger']], logger_name=cell_spec['logger'])
    logs = DB.to_logs(log, cell.K)
    pre = np.array([float(DB.z_pre(e)) for e in log])
    rec = dict(config=cell_spec['config'], repetition=b, namespace=ns, policies={})
    for name in cell_spec['policies']:
        pol = cat[name]
        ipw = float(S.ipw_estimate(log, pol, tasks, D.R_LOG))
        est = DB.estimates(log, pol, tasks, D.R_LOG, cell.K, folds=FOLDS, seed=b)
        Q, fb = DB.known_kernel_q(cell, pol)
        drk, _ = DB.EA.dr_scores(logs, DB.prob_policy(pol), Q, fb)
        _, kk = DB.EA.cluster_means(logs.task, pre + drk)
        rec['policies'][name] = dict(ipw=ipw, pdis=est['pdis'], dr=est['dr'], or_plugin=est['or_plugin'],
                                     dr_known_kernel=float(kk.mean()),
                                     ipw_reproduction_abs_diff=(abs(ipw - original[name]) if original else None))
    rec['cpu_seconds'] = time.process_time() - t0
    return rec


def run():
    if not MANIFEST.exists():
        raise SystemExit('no frozen manifest: this batch needs lead authorization, then `freeze`, commit and push first')
    m = json.loads(MANIFEST.read_text())
    changed = [rel for rel, h in m['source_sha256'].items() if D.sha(rel) != h]
    if changed:
        raise SystemExit('refusing to run: files changed since the manifest was frozen: %s' % changed)
    orig = {(r['config'], r['repetition']): {k: v['ipw'] for k, v in r['policies'].items()}
            for r in map(json.loads, D.REPS.read_text().splitlines())}
    done = {(r['config'], r['repetition']) for r in map(json.loads, REPS.read_text().splitlines())} if REPS.exists() else set()
    todo = [(c, b, orig[(c['config'], b)]) for b in range(m['repetitions_per_cell']) for c in m['cells']
            if (c['config'], b) not in done]
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
    fresh = {(r['config'], r['repetition']): r for r in map(json.loads, D.REPS.read_text().splitlines())}
    kernel = json.loads(G.OUT.read_text())
    rows = []
    for c in m['cells']:
        rs = [r for r in reps if r['config'] == c['config']]
        if len({r['repetition'] for r in rs}) != len(rs):
            raise SystemExit('duplicate repetition records for %s' % c['config'])
        kc = next(k for k in kernel['cells'] if (k['K'], k['action_effect'], k['feedback']) == (2, 'crossing', c['feedback']))
        for name in c['policies']:
            truth = float(G.Fr(kc['policies'][name]['utility']['exact']))
            R = len(rs)
            row = dict(config=c['config'], policy=name, repetitions_complete=R, exact_truth=truth,
                       ipw_reproduction_max_abs_diff=max(r['policies'][name]['ipw_reproduction_abs_diff'] for r in rs))
            for est in ('ipw', 'pdis', 'dr', 'or_plugin', 'dr_known_kernel'):
                v = np.array([r['policies'][name][est] for r in rs])
                row[est] = dict(bias=float(v.mean() - truth), bias_mcse=float(v.std(ddof=1) / math.sqrt(R)),
                                rmse=float(math.sqrt(((v - truth) ** 2).mean())), empirical_sd=float(v.std(ddof=1)))
            d = np.array([r['policies'][name]['dr'] - r['policies'][name]['ipw'] for r in rs])
            row['dr_minus_ipw'] = dict(mean=float(d.mean()), mcse=float(d.std(ddof=1) / math.sqrt(R)))
            f = np.array([r['policies'][name]['dr'] - fresh[(c['config'], r['repetition'])]['policies'][name]['fresh'] for r in rs])
            row['dr_minus_fresh'] = dict(mean=float(f.mean()), mcse=float(f.std(ddof=1) / math.sqrt(R)))
            rows.append(row)
    summary = dict(manifest_sha256=hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
                   reps_sha256=hashlib.sha256(REPS.read_bytes()).hexdigest(), rows=rows, not_claimed=m['not_claimed'],
                   run_status=json.loads((OUT / 'run_status.json').read_text()) if (OUT / 'run_status.json').exists() else {})
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    lines = ['# DR/OR development batch paired on the dev_batch logs (DTR-REQ-003)', '',
             '| Cell | Policy | Truth | IPW bias (MCSE) / RMSE | DR bias (MCSE) / RMSE | OR bias / RMSE | known-Q DR RMSE | DR - IPW (MCSE) |',
             '|---|---|---|---|---|---|---|---|']
    for r in rows:
        lines.append('| %s | %s | %.5f | %+.5f (%.5f) / %.5f | %+.5f (%.5f) / %.5f | %+.5f / %.5f | %.5f | %+.5f (%.5f) |' % (
            r['config'].replace('K2-crossing-', ''), r['policy'], r['exact_truth'], r['ipw']['bias'], r['ipw']['bias_mcse'],
            r['ipw']['rmse'], r['dr']['bias'], r['dr']['bias_mcse'], r['dr']['rmse'], r['or_plugin']['bias'],
            r['or_plugin']['rmse'], r['dr_known_kernel']['rmse'], r['dr_minus_ipw']['mean'], r['dr_minus_ipw']['mcse']))
    (OUT / 'summary.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    {'freeze': freeze, 'run': run, 'analyze': analyze}[sys.argv[1]]()
