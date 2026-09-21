"""DTR-REQ-003 P0: DEVELOPMENT repeated-training operating characteristics of the honest-split DR (lead 3f4dfc2).

Four existing K=2 crossing cells x the three frozen policies; root seed 2026092104; repetitions 0..999 per cell (4,000
jobs). Each repetition draws its OWN training cohort (250 balanced tasks t0000..t0249 x 4 logged), REFITS Q/fallback per
policy on it (honest_split_dr.fit_frozen_q), freezes them, and evaluates on 250 distinct balanced tasks t0250..t0499 x 4
logged, with an independent fresh reference (evaluation tasks x 4 per policy). Namespaces
cfg=hsc-<cell>|rep=<b>|cohort=<train|eval|fresh>|... are disjoint.
Per repetition and policy (all on the SAME evaluation records):
  DR     task-equal mean of honest_split_dr per-episode scores; within-task variance conditional on that fit
  IPW    trajectory IPW (sampler.ipw_estimate) on the same evaluation records; within-task variance of W*Z (paired
         comparator, no extra episodes)
  OR     plug-in point estimate (descriptive only, no coverage claim)
  fresh  task-equal mean and within-task variance of the fresh block
  D      DR - fresh and IPW - fresh, variances summed (independent cohorts)
Intervals: estimate +/- 1.959963984540054 * sqrt(variance). This measures calibration over repeated training and
evaluation samples; it does NOT establish coverage conditional on every fixed fit. With known correct logging the
conditional DR mean is the fixed target for every fit, so there is no between-fit mean component; that argument does
not transfer to overlapping cross-fitted scores or incorrect logging. No fixed-Q exact variance is used as the exact
variance across random refits. Training cost is reported separately (not equal-total-budget evidence).
At most 4 processes and a 900-second TOTAL wall budget (administrative, not outcome-driven); a capped batch is
INCOMPLETE and reported as such. Writer lock + atomic finalize (writer_lock.py). Analysis frozen with the code.
  python honest_split_coverage.py freeze | run | analyze
"""
from __future__ import annotations
import hashlib, json, math, sys, time
from fractions import Fraction
from multiprocessing import Pool

import coverage_batch as C
import dev_batch as D
import dr_bridge as DB
import honest_split_dr as H
import repair_generator as G
import repair_logger as L
import replication_sensitivity as R
import sampler as S
import writer_lock as W

NAME = 'honest_split_coverage_20260921'
OUT = D.ROOT / 'results' / 'v2_sim' / NAME
WORK = D.ROOT / 'work' / 'runs' / NAME
MANIFEST, PART, FINAL = OUT / 'manifest.json', WORK / 'reps.part.jsonl', OUT / 'reps.jsonl'
ROOT_SEED, R_REPS, WORKERS, CAP_S, Z = 2026092104, 1000, 4, 900, C.Z
HASHED = ['experiments/v2_sim/honest_split_coverage.py', 'experiments/v2_sim/honest_split_dr.py', 'experiments/v2_sim/dr_bridge.py',
          'experiments/code_routing/estimators_absorbing.py', 'experiments/v2_sim/sampler.py', 'experiments/v2_sim/repair_generator.py',
          'experiments/v2_sim/repair_logger.py', 'experiments/v2_sim/fixed_task_blocks.py', 'experiments/v2_sim/dev_batch.py',
          'experiments/v2_sim/coverage_batch.py', 'experiments/v2_sim/replication_sensitivity.py', 'experiments/v2_sim/writer_lock.py',
          'experiments/v2_sim/repair_generator_v1.json', 'experiments/v2_sim/fixed_task_blocks_v1.json',
          'experiments/v2_sim/fresh_reference_v1.json']
ESTIMANDS = ('dr', 'ipw', 'fresh', 'dr_minus_fresh', 'ipw_minus_fresh')


def cells():
    return [dict(c, config='hsc-' + c['config']) for c in D.cells()]


def truths():
    kernel = json.loads(G.OUT.read_text())
    out = {}
    for c in cells():
        kc = next(k for k in kernel['cells'] if (k['K'], k['action_effect'], k['feedback']) == (2, 'crossing', c['feedback']))
        for name in c['policies']:
            out['%s|%s' % (c['config'], name)] = dict(exact=kc['policies'][name]['utility']['exact'],
                                                      float=float(Fraction(kc['policies'][name]['utility']['exact'])))
    return out


def freeze():
    tr, ev, dt, de = H.cohorts()
    m = dict(request='DTR-REQ-003 P0 repeated-training honest-split DR coverage (lead 3f4dfc2)',
             kind='DEVELOPMENT operating characteristics over repeated training/evaluation samples; not fixed-fit conditional coverage',
             root_seed=ROOT_SEED, repetitions_per_cell=R_REPS, workers=WORKERS, total_wall_budget_seconds=CAP_S, z=Z,
             cells=cells(), truths=truths(),
             cohorts=dict(train=dict(tasks='t0000..t0249', sha256=dt, replicates=H.R_LOG),
                          eval=dict(tasks='t0250..t0499', sha256=de, replicates=H.R_LOG),
                          fresh=dict(tasks='evaluation tasks', replicates=H.R_FRESH)),
             stream_namespace='cfg=<hsc-config>|rep=<b>|cohort=<train|eval|fresh>|<log|fresh>|<logger or policy>|<task>|<replicate>',
             nuisance=dict(refit='per repetition and policy, on that repetition\'s training cohort only',
                           fit='estimators_absorbing.fit_q via honest_split_dr.fit_frozen_q',
                           feature_map=H.FEATURE_MAP, policies='catalog policies by name (repair_generator.catalog(2))',
                           table_hash='q_fallback_table_sha256 covers Q/fallback tables ONLY; provenance = this manifest + source hashes'),
             estimands=dict(dr='honest_split_dr.dr_estimate_and_variance', ipw='sampler.ipw_estimate + within_block_variance(W*Z) on the same evaluation records',
                            or_plugin='descriptive only', fresh='sampler.fresh_estimate + within_block_variance',
                            dr_minus_fresh='summed variance, target 0', ipw_minus_fresh='summed variance, target 0'),
             failures='missing/nonfinite/negative variance = failed, noncovering; finite zero variance = point interval; errors recorded, never dropped',
             reported=['coverage + MCSE + Wilson', 'lower/upper misses', 'bias + MCSE', 'RMSE', 'empirical and mean estimated variance',
                       'average length', 'variance CV', 'error-variance correlation', 'failed/zero intervals',
                       'paired DR-minus-IPW squared-error difference + MCSE', 'OR bias/RMSE (descriptive)', 'training resource use',
                       'requested/completed denominators'],
             not_claimed=['fixed-fit conditional coverage', 'cross-fitted inference', 'equal-total-budget superiority',
                          'multiplicity-adjusted or uniform calibration'],
             output_isolation='records under work/runs (git-ignored) with a writer lock; atomic finalize to results/',
             source_sha256={rel: D.sha(rel) for rel in HASHED})
    OUT.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=1) + '\n')
    return m


def policy_block(evalu, fresh, train, pol, K, tr, ev):
    p = dict(error=None)
    try:
        nu = H.fit_frozen_q(train, pol, K, tr, H.R_LOG)
        dr = H.dr_estimate_and_variance(evalu, pol, K, nu, ev, H.R_LOG)
        hits = H.fallback_hits(evalu, pol, K, nu)
        p.update(dr=dr['estimate'], dr_var=dr['variance'], or_plugin=dr['or_plugin'],
                 ipw=float(S.ipw_estimate(evalu, pol, ev, H.R_LOG)),
                 ipw_var=float(S.within_block_variance(evalu, lambda e: S.ipw_weight(e, pol) * e['utility'], ev, H.R_LOG)),
                 fresh=float(S.fresh_estimate(fresh, ev, H.R_FRESH)),
                 fresh_var=float(S.within_block_variance(fresh, lambda e: e['utility'], ev, H.R_FRESH)),
                 q_fallback_table_sha256=nu.sha256, missing_q_cells_in_training=nu.missing_q_cells_in_training,
                 eval_fallback_hit_fraction=float(hits.mean()))
    except Exception as e:   # recorded, never dropped: counted as failed, noncovering
        p['error'] = '%s: %s' % (type(e).__name__, str(e)[:200])
    return p


def job(arg, memoize=True):
    if memoize:
        with R.ValidateOncePerBlock():
            return job(arg, memoize=False)
    c, b = arg
    t0 = time.process_time()
    cell = G.Cell(2, 'crossing', c['feedback'])
    tr, ev, _, _ = H.cohorts()
    cat = {p.name: p for p in G.catalog(2)}
    draws = S.SeededDraws(ROOT_SEED)
    lg = dict(logger=L.LOGGERS[c['logger']], logger_name=c['logger'])
    train = S.run_blocks(tr, cell, H.R_LOG, draws, H.cohort_namespace(c['config'], b, 'train'), 'log', **lg)
    evalu = S.run_blocks(ev, cell, H.R_LOG, draws, H.cohort_namespace(c['config'], b, 'eval'), 'log', **lg)
    rec = dict(config=c['config'], repetition=b, training=H.training_cost(train), policies={})
    for name in c['policies']:
        pol = cat[name]
        fresh = S.run_blocks(ev, cell, H.R_FRESH, draws, H.cohort_namespace(c['config'], b, 'fresh'), 'fresh', policy=pol)
        rec['policies'][name] = policy_block(evalu, fresh, train, pol, cell.K, tr, ev)
    rec['cpu_seconds'] = time.process_time() - t0
    return rec


def run():
    if not MANIFEST.exists():
        raise SystemExit('no frozen manifest')
    m = json.loads(MANIFEST.read_text())
    changed = [rel for rel, h in m['source_sha256'].items() if D.sha(rel) != h]
    if changed:
        raise SystemExit('refusing to run: files changed since the manifest was frozen: %s' % changed)
    WORK.mkdir(parents=True, exist_ok=True)
    expected = [(c['config'], b) for b in range(m['repetitions_per_cell']) for c in m['cells']]
    with W.WriterLock(NAME):
        done = {(r['config'], r['repetition']) for r in map(json.loads, PART.read_text().splitlines())} if PART.exists() else set()
        todo = [(c, b) for b in range(m['repetitions_per_cell']) for c in m['cells'] if (c['config'], b) not in done]
        start, completed, stopped = time.time(), 0, False
        with Pool(m['workers']) as pool, PART.open('a') as fh:
            for rec in pool.imap_unordered(job, todo, chunksize=2):
                fh.write(json.dumps(rec) + '\n'); fh.flush(); completed += 1
                if time.time() - start > m['total_wall_budget_seconds']:
                    stopped = True; pool.terminate(); break
        fin = W.finalize(PART, FINAL, expected, key=lambda r: (r['config'], r['repetition']))
    status = dict(wall_seconds=time.time() - start, submitted_this_invocation=len(todo), counter_completed=completed,
                  stopped_by_cap=stopped, persisted=fin, requested=len(expected),
                  complete=fin['records'] == len(expected) and fin['missing'] == 0)
    (OUT / 'run_status.json').write_text(json.dumps(status, indent=1) + '\n')
    print(json.dumps(status))


def series(P, key, truth):
    if key == 'dr_minus_fresh':
        return [C.diff(p.get('dr'), p.get('fresh')) for p in P], [C.vsum(p.get('dr_var'), p.get('fresh_var')) for p in P], 0.0
    if key == 'ipw_minus_fresh':
        return [C.diff(p.get('ipw'), p.get('fresh')) for p in P], [C.vsum(p.get('ipw_var'), p.get('fresh_var')) for p in P], 0.0
    return [p.get(key) for p in P], [p.get(key + '_var') for p in P], truth


def mean_or_none(x):
    return sum(x) / len(x) if x else None


def mcse_or_none(x):
    if len(x) < 2:
        return None
    m = sum(x) / len(x)
    return math.sqrt(sum((v - m) ** 2 for v in x) / (len(x) - 1)) / math.sqrt(len(x))


def ratio_or_none(a, b):
    return a / b if C.finite(a) and C.finite(b) and b != 0 else None


def fmt(x, spec):
    return spec % x if C.finite(x) else 'n/a'


def estimand_stats(est, var, target, requested):
    """C.interval_stats (exact-variance fields dropped: no fixed-Q exact variance across refits) + tails/correlation/CV."""
    if sum(1 for e in est if C.finite(e)) < 2:      # too few completed records for spread statistics (e.g. capped output)
        n = len(est)
        cov = sum(1 for e, v in zip(est, var) if C.finite(e) and C.finite(v) and v >= 0 and abs(e - target) <= Z * math.sqrt(v))
        return dict(completed=n, finite_estimates=sum(1 for e in est if C.finite(e)), wald_covered=cov,
                    wald_coverage=cov / n if n else None, wald_coverage_over_requested=cov / requested,
                    failed_intervals=sum(1 for e, v in zip(est, var) if not (C.finite(e) and C.finite(v) and v >= 0)),
                    note='fewer than 2 finite estimates: spread statistics not computed')
    s = C.interval_stats(est, var, target, 1.0, requested)
    for k in ('exact_variance', 'mean_estimated_over_exact_variance', 'empirical_over_exact_variance', 'exact_variance_covered',
              'exact_variance_coverage', 'exact_variance_coverage_mcse'):
        s.pop(k)
    s['rmse'] = math.sqrt(s['mse'])
    s.update(R.shape_stats(est, var, target))
    return s


def analyze():
    m = json.loads(MANIFEST.read_text())
    reps = [json.loads(x) for x in FINAL.read_text().splitlines()]
    ids = [(r['config'], r['repetition']) for r in reps]
    if len(ids) != len(set(ids)):
        raise SystemExit('duplicate (config, repetition) ids in the finalized records')
    requested = m['repetitions_per_cell']
    rows = []
    for c in m['cells']:
        rs = sorted((r for r in reps if r['config'] == c['config']), key=lambda r: r['repetition'])
        for name in c['policies']:
            truth = m['truths']['%s|%s' % (c['config'], name)]['float']
            P = [r['policies'][name] for r in rs]
            row = dict(config=c['config'], policy=name, truth=truth, requested=requested, completed=len(rs),
                       recorded_errors=sum(1 for p in P if p['error']))
            for key in ESTIMANDS:
                est, var, tgt = series(P, key, truth)
                row[key] = estimand_stats(est, var, tgt, requested)
                if key.endswith('minus_fresh'):
                    row[key]['rejection_at_zero'] = 1 - row[key]['wald_coverage']
            sq = [(p['dr'] - truth) ** 2 - (p['ipw'] - truth) ** 2 for p in P
                  if C.finite(p.get('dr')) and C.finite(p.get('ipw'))]
            row['paired_dr_minus_ipw_squared_error'] = dict(mean=mean_or_none(sq), mcse=mcse_or_none(sq), n=len(sq),
                                                           mse_ratio_dr_over_ipw=ratio_or_none(row['dr'].get('mse'), row['ipw'].get('mse')))
            orr = [p['or_plugin'] - truth for p in P if C.finite(p.get('or_plugin'))]
            row['or_plugin_descriptive'] = dict(bias=mean_or_none(orr), bias_mcse=mcse_or_none(orr),
                                                rmse=math.sqrt(mean_or_none([x * x for x in orr])) if orr else None, n=len(orr))
            fb = [p['eval_fallback_hit_fraction'] for p in P if C.finite(p.get('eval_fallback_hit_fraction'))]
            row['nuisance'] = dict(distinct_q_fallback_tables=len({p.get('q_fallback_table_sha256') for p in P}),
                                   mean_missing_q_cells_in_training=mean_or_none([p.get('missing_q_cells_in_training', 0) for p in P]),
                                   mean_eval_fallback_hit_fraction=mean_or_none(fb))
            rows.append(row)
    tc = [r['training'] for r in reps]
    summary = dict(kind=m['kind'], manifest_sha256=hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
                   reps_sha256=hashlib.sha256(FINAL.read_bytes()).hexdigest(),
                   requested=len(m['cells']) * requested, completed=len(reps), completion_fraction=len(reps) / (len(m['cells']) * requested),
                   run_status=json.loads((OUT / 'run_status.json').read_text()),
                   training_resources_per_repetition=dict(episodes=sum(t['episodes'] for t in tc) / len(tc),
                                                          model_calls=sum(t['model_calls'] for t in tc) / len(tc),
                                                          total_cost=sum(t['total_cost'] for t in tc) / len(tc)),
                   rows=rows, not_claimed=m['not_claimed'])
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    lines = ['# Honest-split DR, repeated-training coverage (DTR-REQ-003 P0; lead 3f4dfc2) — DEVELOPMENT', '',
             'Completed %d of %d requested repetitions (fraction %.4f)%s. Nominal 95%% Wald intervals; Q refitted per repetition. '
             'Coverage over repeated training/evaluation samples, not conditional on a fixed fit. Training cost separate.' % (
                 len(reps), summary['requested'], summary['completion_fraction'], '' if summary['completion_fraction'] == 1 else ' — INCOMPLETE (cap)'), '',
             '| Cell | Policy | Estimand | Coverage (MCSE) [Wilson] | Lower/upper miss | Bias (MCSE) | RMSE | Emp. var | Mean est. var | Var CV | Corr(err,var) | Avg length | Fail/zero |',
             '|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        for key in ESTIMANDS:
            s = r[key]
            wil = s.get('wald_coverage_wilson') or (None, None)
            lines.append('| %s | %s | %s | %s (%s) [%s, %s] | %s/%s | %s (%s) | %s | %s | %s | %s | %s | %s | %s/%s |' % (
                r['config'].replace('hsc-K2-crossing-', ''), r['policy'], key, fmt(s.get('wald_coverage'), '%.4f'),
                fmt(s.get('wald_coverage_mcse'), '%.4f'), fmt(wil[0], '%.4f'), fmt(wil[1], '%.4f'), fmt(s.get('lower_tail_miss'), '%.4f'),
                fmt(s.get('upper_tail_miss'), '%.4f'), fmt(s.get('bias'), '%+.5f'), fmt(s.get('bias_mcse'), '%.5f'), fmt(s.get('rmse'), '%.5f'),
                fmt(s.get('empirical_variance'), '%.3e'), fmt(s.get('mean_estimated_variance'), '%.3e'), fmt(s.get('variance_cv'), '%.3f'),
                fmt(s.get('error_variance_correlation'), '%.3f'), fmt(s.get('average_length'), '%.4f'), s.get('failed_intervals', 0),
                s.get('zero_variance_point_intervals', 0)))
    lines += ['', '| Cell | Policy | Paired DR−IPW squared error (MCSE) | MSE ratio DR/IPW | OR bias (MCSE) / RMSE (descriptive) | Mean eval fallback fraction |',
              '|---|---|---|---|---|---|']
    for r in rows:
        pq, o = r['paired_dr_minus_ipw_squared_error'], r['or_plugin_descriptive']
        lines.append('| %s | %s | %s (%s) | %s | %s (%s) / %s | %s |' % (
            r['config'].replace('hsc-K2-crossing-', ''), r['policy'], fmt(pq['mean'], '%+.3e'), fmt(pq['mcse'], '%.3e'),
            fmt(pq['mse_ratio_dr_over_ipw'], '%.4f'), fmt(o['bias'], '%+.5f'), fmt(o['bias_mcse'], '%.5f'), fmt(o['rmse'], '%.5f'),
            fmt(r['nuisance']['mean_eval_fallback_hit_fraction'], '%.4f')))
    (OUT / 'summary.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    {'freeze': freeze, 'run': run, 'analyze': analyze}[sys.argv[1]]()
