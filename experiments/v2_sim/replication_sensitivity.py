"""DTR-REQ-003 P0: development replication-sensitivity batch (lead 9550aa4, theory_feedback_20260921_undercoverage.md).

A post-design DEVELOPMENT sensitivity check, separate from the completed 2,000-repetition validation (coverage_batch.py,
b2ad9a3), which it does not change. Two K=2 crossing cells with the feedback-dependent .2 logger (informative, weak);
the same three frozen policies and balanced n=250 list; root seed 2026092103 in 'rs-' namespaces; 1,000 complete
repetitions per cell. Each repetition generates 16 logged episodes per task and 16 independent fresh episodes per task
and policy, and analyses the NESTED first-4 block (replicates 0-3, its own r=4 manifest and denominators) and the full
16 block, paired by task, episode stream and repetition (the first 4 replicates are the same streams in both).
Per block: trajectory-IPW and fresh estimates, within_block_variance on the fixed per-episode scores, D = IPW - fresh
with summed variance; nominal 95% Wald intervals and exact-variance diagnostics. Exact variance at r=16 is the accepted
r=4 variance / 4 (verified before launch). Not for fitted DR/OR. More replication changes the execution budget and both
the estimator distribution and its SE estimate: a larger-r improvement is sensitivity to replication, not a cost-free
repair. At most 4 processes, 900 s wall cap, no outcome-based stopping; writer lock + atomic finalize (writer_lock.py).
  python replication_sensitivity.py freeze | run | analyze
"""
from __future__ import annotations
import hashlib, json, math, sys, time
from fractions import Fraction
from multiprocessing import Pool

import coverage_batch as C
import dev_batch as D
import fixed_task_blocks as B
import repair_generator as G
import repair_logger as L
import sampler as S
import writer_lock as W

NAME = 'replication_sensitivity_20260921'
OUT = D.ROOT / 'results' / 'v2_sim' / NAME
WORK = D.ROOT / 'work' / 'runs' / NAME
MANIFEST, PART, FINAL = OUT / 'manifest.json', WORK / 'reps.part.jsonl', OUT / 'reps.jsonl'
ROOT_SEED, R_REPS, WORKERS, CAP_S, Z = 2026092103, 1000, 4, 900, C.Z
R_SMALL, R_BIG = 4, 16
HASHED = ['experiments/v2_sim/replication_sensitivity.py', 'experiments/v2_sim/coverage_batch.py',
          'experiments/v2_sim/writer_lock.py', 'experiments/v2_sim/sampler.py', 'experiments/v2_sim/repair_generator.py',
          'experiments/v2_sim/repair_logger.py', 'experiments/v2_sim/fixed_task_blocks.py', 'experiments/v2_sim/dev_batch.py',
          'experiments/v2_sim/repair_generator_v1.json', 'experiments/v2_sim/fixed_task_blocks_v1.json',
          'experiments/v2_sim/fresh_reference_v1.json']


def cells():
    return [dict(c, config='rs-' + c['config']) for c in D.cells() if c['logger'] == 'feedback_dependent_floor_0.2']


def exact_table():
    """r=4 exact values from the accepted tables (coverage_batch.exact_table, same derivation as the validation);
    r=16 variances are the r=4 variances / 4 (independent replicates within a task; checked by enumeration in tests)."""
    base = C.exact_table()
    out = {}
    for c in cells():
        for name in c['policies']:
            ex = base[('cov-' + c['config'][3:], name)]['exact']
            t = {}
            for r in (R_SMALL, R_BIG):
                k = Fraction(R_SMALL, r)
                iv, fv = Fraction(ex['ipw_var']) * k, Fraction(ex['fresh_var']) * k
                t[str(r)] = dict(truth=float(Fraction(ex['truth'])), ipw_var=float(iv), fresh_var=float(fv), d_var=float(iv + fv),
                                 exact=dict(truth=ex['truth'], ipw_var=str(iv), fresh_var=str(fv), d_var=str(iv + fv)))
            out[(c['config'], name)] = t
    return out


def freeze():
    m = dict(request='DTR-REQ-003 P0 development replication-sensitivity batch (lead 9550aa4)',
             kind='post-design DEVELOPMENT sensitivity check; does not change the completed validation b2ad9a3',
             root_seed=ROOT_SEED, repetitions_per_cell=R_REPS, n_tasks=D.N_TASKS, replicates_generated=R_BIG,
             nested_blocks=[R_SMALL, R_BIG], nesting='first-4 = replicates 0..3 of the same streams; analysed with its own r=4 manifest',
             task_list=dict(n=D.N_TASKS, sha256=B.task_list(D.N_TASKS)[1], rule="task g = 't%04d' % g, stratum = g mod 2"),
             cells=cells(), workers=WORKERS, cpu_wall_cap_seconds=CAP_S, z=Z,
             stream_namespace="cfg=<rs-config>|rep=<b>|<log|fresh>|<logger name or policy>|<task>|<replicate 0..15>",
             draw_source='sampler.SeededDraws: numpy SeedSequence(root_seed, spawn_key=sha256(stream)[:16] as 4 uint32)',
             estimators=dict(ipw='sampler.ipw_estimate on the block', fresh='sampler.fresh_estimate on the block',
                             variance='sampler.within_block_variance on fixed per-episode scores W*Z and Z (exact, then float)',
                             ipw_minus_fresh='IPW - fresh, summed variance, target 0',
                             interval='estimate +/- z*sqrt(variance); diagnostic: estimate +/- z*sqrt(exact variance)',
                             failures='missing/nonfinite/negative variance = failed, noncovering; finite zero variance = point interval'),
             reported=['bias/MCSE', 'MSE/MCSE', 'empirical SD', 'mean estimated and empirical variance / exact',
                       'Wald and exact-variance coverage with binomial MCSE and Wilson', 'average length',
                       'lower/upper tail misses', 'error-variance correlation', 'variance CV', 'failures/zero variance',
                       'paired r16-minus-r4 coverage differences with MCSE', 'completion fraction'],
             exact_table={'%s|%s' % k: v for k, v in exact_table().items()},
             output_isolation='records written under work/runs (git-ignored) with a writer lock; atomic finalize to results/',
             not_for='fitted DR/OR scores; interval repair claims; changing the completed validation',
             source_sha256={rel: D.sha(rel) for rel in HASHED})
    OUT.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=1) + '\n')
    return m


def block_estimates(log, fresh, pol, tasks, r):
    p = dict(ipw=None, ipw_var=None, fresh=None, fresh_var=None, error=None)
    try:
        p['ipw'] = float(S.ipw_estimate(log, pol, tasks, r))
        p['ipw_var'] = float(S.within_block_variance(log, lambda e: S.ipw_weight(e, pol) * e['utility'], tasks, r))
        p['fresh'] = float(S.fresh_estimate(fresh, tasks, r))
        p['fresh_var'] = float(S.within_block_variance(fresh, lambda e: e['utility'], tasks, r))
    except Exception as e:   # recorded, never dropped: counted as a failed, noncovering interval
        p['error'] = '%s: %s' % (type(e).__name__, str(e)[:200])
    return p


class ValidateOncePerBlock:
    """Runtime-only: the accepted sampler.validate_manifest (O(n^2) duplicate scan) runs ONCE per distinct block object,
    task list and r within a job; the accepted estimators then skip exact repeats of that check. Every block reaching an
    estimator has passed the accepted validator with the same arguments, and blocks are never mutated. sampler.py is not
    edited (its hash is frozen in earlier manifests); estimates are identical to the unmemoized path (tested)."""

    def __init__(self):
        self.seen, self.real = [], S.validate_manifest

    def check(self, episodes, tasks, r):
        if any(e is episodes and t is tasks and rr == r for e, t, rr in self.seen):
            return
        self.real(episodes, tasks, r)
        self.seen.append((episodes, tasks, r))

    def __enter__(self):
        S.validate_manifest = self.check
        return self

    def __exit__(self, *exc):
        S.validate_manifest = self.real
        return False


def job(arg, memoize=True):
    if memoize:
        with ValidateOncePerBlock():
            return job(arg, memoize=False)
    c, b = arg
    t0 = time.process_time()
    cell = G.Cell(2, 'crossing', c['feedback'])
    tasks, _ = B.task_list(D.N_TASKS)
    cat = {p.name: p for p in G.catalog(2)}
    ns = S.stream_namespace(c['config'], b)
    draws = S.SeededDraws(ROOT_SEED)
    log = S.run_blocks(tasks, cell, R_BIG, draws, ns, 'log', logger=L.LOGGERS[c['logger']], logger_name=c['logger'])
    log4 = [e for e in log if e['replicate'] < R_SMALL]
    rec = dict(config=c['config'], repetition=b, namespace=ns, policies={})
    for name in c['policies']:
        pol = cat[name]
        fresh = S.run_blocks(tasks, cell, R_BIG, draws, ns, 'fresh', policy=pol)
        fresh4 = [e for e in fresh if e['replicate'] < R_SMALL]
        rec['policies'][name] = {str(R_SMALL): block_estimates(log4, fresh4, pol, tasks, R_SMALL),
                                 str(R_BIG): block_estimates(log, fresh, pol, tasks, R_BIG)}
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
                if time.time() - start > m['cpu_wall_cap_seconds']:
                    stopped = True; pool.terminate(); break
        fin = W.finalize(PART, FINAL, expected, key=lambda r: (r['config'], r['repetition']))
    status = dict(wall_seconds=time.time() - start, submitted_this_invocation=len(todo), counter_completed=completed,
                  stopped_by_cap=stopped, persisted=fin)
    (OUT / 'run_status.json').write_text(json.dumps(status, indent=1) + '\n')
    print(json.dumps(status))


def shape_stats(est, var, target):
    """Tail misses of the Wald interval, error/variance correlation and variance CV over finite records."""
    n = len(est)
    ok = [(e, v) for e, v in zip(est, var) if C.finite(e) and C.finite(v) and v >= 0]
    lo = sum(1 for e, v in ok if e - target < -Z * math.sqrt(v))
    hi = sum(1 for e, v in ok if e - target > Z * math.sqrt(v))
    if len(ok) < 3:
        return dict(lower_tail_miss=lo / n, upper_tail_miss=hi / n, error_variance_correlation=None, variance_cv=None)
    er, vv = [e - target for e, _ in ok], [v for _, v in ok]
    me, mv = sum(er) / len(er), sum(vv) / len(vv)
    se = math.sqrt(sum((x - me) ** 2 for x in er) / (len(er) - 1)); sv = math.sqrt(sum((x - mv) ** 2 for x in vv) / (len(vv) - 1))
    cor = sum((x - me) * (y - mv) for x, y in zip(er, vv)) / ((len(er) - 1) * se * sv) if se > 0 and sv > 0 else None
    return dict(lower_tail_miss=lo / n, upper_tail_miss=hi / n, lower_tail_miss_mcse=math.sqrt(lo / n * (1 - lo / n) / n),
                upper_tail_miss_mcse=math.sqrt(hi / n * (1 - hi / n) / n), error_variance_correlation=cor,
                variance_cv=sv / mv if mv > 0 else None)


def covered(e, v, target, exact_var=None):
    if not C.finite(e):
        return 0
    if exact_var is not None:
        return int(abs(e - target) <= Z * math.sqrt(exact_var))
    return int(C.finite(v) and v >= 0 and abs(e - target) <= Z * math.sqrt(v))


def paired(a, b):
    d = [x - y for x, y in zip(a, b)]
    n = len(d); mu = sum(d) / n
    sd = math.sqrt(sum((x - mu) ** 2 for x in d) / (n - 1)) if n > 1 else float('nan')
    return dict(mean=mu, mcse=sd / math.sqrt(n), discordant_gain=sum(1 for x in d if x > 0), discordant_loss=sum(1 for x in d if x < 0))


def series(P, r, key, truth):
    q = [p[str(r)] for p in P]
    if key == 'ipw_minus_fresh':
        return [C.diff(x['ipw'], x['fresh']) for x in q], [C.vsum(x['ipw_var'], x['fresh_var']) for x in q], 0.0
    return [x[key] for x in q], [x[key + '_var'] for x in q], truth


def analyze():
    m = json.loads(MANIFEST.read_text())
    reps = [json.loads(x) for x in FINAL.read_text().splitlines()]
    ids = [(r['config'], r['repetition']) for r in reps]
    if len(ids) != len(set(ids)):
        raise SystemExit('duplicate (config, repetition) ids in the finalized records')
    rows = []
    for c in m['cells']:
        rs = sorted((r for r in reps if r['config'] == c['config']), key=lambda r: r['repetition'])
        for name in c['policies']:
            ex = m['exact_table']['%s|%s' % (c['config'], name)]
            P = [r['policies'][name] for r in rs]
            row = dict(config=c['config'], policy=name, truth=ex['4']['truth'], repetitions=len(rs),
                       recorded_errors={str(r): sum(1 for p in P if p[str(r)]['error']) for r in (R_SMALL, R_BIG)})
            for key, vkey in (('ipw', 'ipw_var'), ('fresh', 'fresh_var'), ('ipw_minus_fresh', 'd_var')):
                per_r, cov, excov, lens = {}, {}, {}, {}
                for r in (R_SMALL, R_BIG):
                    est, var, tgt = series(P, r, key, ex[str(r)]['truth'])
                    s = C.interval_stats(est, var, tgt, ex[str(r)][vkey], m['repetitions_per_cell'])
                    s.update(shape_stats(est, var, tgt))
                    if key == 'ipw_minus_fresh':
                        s['rejection_at_zero'] = 1 - s['wald_coverage']
                    per_r[str(r)] = s
                    cov[r] = [covered(e, v, tgt) for e, v in zip(est, var)]
                    excov[r] = [covered(e, v, tgt, ex[str(r)][vkey]) for e, v in zip(est, var)]
                    lens[r] = s['average_length']
                per_r['paired_r16_minus_r4'] = dict(
                    wald_coverage=paired(cov[R_BIG], cov[R_SMALL]), exact_variance_coverage=paired(excov[R_BIG], excov[R_SMALL]),
                    wald_minus_exact_r4=paired(cov[R_SMALL], excov[R_SMALL]), wald_minus_exact_r16=paired(cov[R_BIG], excov[R_BIG]),
                    average_length_ratio=lens[R_BIG] / lens[R_SMALL] if lens[R_BIG] and lens[R_SMALL] else None)
                row[key] = per_r
            rows.append(row)
    summary = dict(kind=m['kind'], manifest_sha256=hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
                   reps_sha256=hashlib.sha256(FINAL.read_bytes()).hexdigest(),
                   completion_fraction=len(reps) / (len(m['cells']) * m['repetitions_per_cell']),
                   run_status=json.loads((OUT / 'run_status.json').read_text()), rows=rows,
                   not_claimed=['no interval repair', 'no change to the completed validation b2ad9a3', 'no DR/OR inference',
                                'no multiplicity-adjusted claim', 'no real-agent evidence'])
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    lines = ['# Replication-sensitivity development batch (DTR-REQ-003 P0; lead 9550aa4)', '',
             'Completion %.4f. Nested first-4 versus all-16 logged/fresh replicates on the same streams; nominal 95%% Wald '
             'intervals with within-block variance; exact-variance intervals as diagnostic. Sensitivity to replication '
             '(budget), not a cost-free repair.' % summary['completion_fraction'], '',
             '| Cell | Policy | Estimand | r | Wald cov. (MCSE) | Exact-var cov. | Lower/upper miss | Corr(err,var) | Var CV | Mean est./exact var | Bias (MCSE) | Avg length | Fail/zero |',
             '|---|---|---|---|---|---|---|---|---|---|---|---|---|']
    for r_ in rows:
        for key in ('ipw', 'fresh', 'ipw_minus_fresh'):
            for r in (str(R_SMALL), str(R_BIG)):
                s = r_[key][r]
                lines.append('| %s | %s | %s | %s | %.4f (%.4f) | %.4f | %.4f/%.4f | %.3f | %.3f | %.4f | %+.5f (%.5f) | %.4f | %d/%d |' % (
                    r_['config'].replace('rs-K2-crossing-', '').replace('-feedback_dependent_floor_0.2', ''), r_['policy'], key, r,
                    s['wald_coverage'], s['wald_coverage_mcse'], s['exact_variance_coverage'], s['lower_tail_miss'],
                    s['upper_tail_miss'], s['error_variance_correlation'], s['variance_cv'], s['mean_estimated_over_exact_variance'],
                    s['bias'], s['bias_mcse'], s['average_length'], s['failed_intervals'], s['zero_variance_point_intervals']))
    lines += ['', '| Cell | Policy | Estimand | Paired r16−r4 Wald coverage (MCSE) | Paired r16−r4 exact-var coverage (MCSE) | Wald−exact r4 | Wald−exact r16 | Length ratio r16/r4 |',
              '|---|---|---|---|---|---|---|---|']
    for r_ in rows:
        for key in ('ipw', 'fresh', 'ipw_minus_fresh'):
            p = r_[key]['paired_r16_minus_r4']
            lines.append('| %s | %s | %s | %+.4f (%.4f) | %+.4f (%.4f) | %+.4f (%.4f) | %+.4f (%.4f) | %.4f |' % (
                r_['config'].replace('rs-K2-crossing-', '').replace('-feedback_dependent_floor_0.2', ''), r_['policy'], key,
                p['wald_coverage']['mean'], p['wald_coverage']['mcse'], p['exact_variance_coverage']['mean'],
                p['exact_variance_coverage']['mcse'], p['wald_minus_exact_r4']['mean'], p['wald_minus_exact_r4']['mcse'],
                p['wald_minus_exact_r16']['mean'], p['wald_minus_exact_r16']['mcse'], p['average_length_ratio']))
    (OUT / 'summary.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    {'freeze': freeze, 'run': run, 'analyze': analyze}[sys.argv[1]]()
