"""DTR-REQ-003 P0: fixed-score coverage component (lead f0b4fa2, theory_feedback_20260921_coverage.md). Authorized batch.

Four K=2 crossing cells (informative/weak x uniform-.5/feedback-.2 logger); policies history_large_after_exception,
prompt_only_large_if_hard and the known-kernel-selected fixed_LS; n=250 balanced fixed tasks; 4 logged and 4 independent
fresh episodes per task and policy; 2,000 complete repetitions per cell; root seed 2026092102 (new); namespaces
'cov-<cell>|rep=<b>|<role>|<logger or policy>|<task>|<replicate>'; at most 4 processes; 900 s wall cap.
Per repetition and policy: trajectory-IPW estimate and fresh estimate (task-equal means of fixed per-episode scores);
variances by sampler.within_block_variance on those FIXED scores; D = IPW - fresh with variance = sum (independent logs).
Nominal 95% Wald intervals estimate +/- 1.959963984540054 * SE, plus exact-variance normal intervals as a diagnostic
(exact values from the accepted tables, fixed before the run). Candidate intervals whose coverage is being TESTED.
Not for fitted DR/OR scores. Output isolation (write-loss fix): records go to work/runs/ under a writer lock and are
published to results/ only by an atomic finalize that verifies the expected unique ids after the writers have closed.
  python coverage_batch.py freeze | run | analyze
"""
from __future__ import annotations
import hashlib, json, math, sys, time
from fractions import Fraction
from multiprocessing import Pool

import dev_batch as D
import fixed_task_blocks as B
import repair_generator as G
import repair_logger as L
import sampler as S
import writer_lock as W

NAME = 'coverage_fixed_score_20260921'
OUT = D.ROOT / 'results' / 'v2_sim' / NAME
WORK = D.ROOT / 'work' / 'runs' / NAME
MANIFEST, PART, FINAL = OUT / 'manifest.json', WORK / 'reps.part.jsonl', OUT / 'reps.jsonl'
ROOT_SEED, R_REPS, WORKERS, CAP_S, Z = 2026092102, 2000, 4, 900, 1.959963984540054
HASHED = ['experiments/v2_sim/coverage_batch.py', 'experiments/v2_sim/writer_lock.py', 'experiments/v2_sim/sampler.py',
          'experiments/v2_sim/repair_generator.py', 'experiments/v2_sim/repair_logger.py', 'experiments/v2_sim/fixed_task_blocks.py',
          'experiments/v2_sim/dev_batch.py', 'experiments/v2_sim/repair_generator_v1.json',
          'experiments/v2_sim/fixed_task_blocks_v1.json', 'experiments/v2_sim/fresh_reference_v1.json']


def cells():
    return [dict(c, config='cov-' + c['config']) for c in D.cells()]


def exact_table():
    """Truth and exact variances for all 12 rows, read from the accepted artifacts (fixed before the run):
    truth = repair_generator_v1 utility; IPW variance = fixed_task_blocks_v1 exact_var_V_hat (n = 250, r = 4);
    fresh variance = n^-2 sum_g tau^2(S_g) / r_fresh from fresh_reference_v1 on-policy per-episode variances (balanced
    50/50 list, r_fresh = 4); D variance = IPW + fresh (independent logs). Exact fractions kept beside the floats."""
    kernel = json.loads(G.OUT.read_text())
    ftb = json.loads(B.OUT.read_text())
    fref = json.loads((D.HERE / 'fresh_reference_v1.json').read_text())
    out = {}
    for c in cells():
        kc = next(k for k in kernel['cells'] if (k['K'], k['action_effect'], k['feedback']) == (2, 'crossing', c['feedback']))
        for name in c['policies']:
            iv = [x for x in ftb['rows'] if (x['K'], x['action_effect'], x['feedback'], x['logger'], x['n'], x['r'], x['policy'])
                  == (2, 'crossing', c['feedback'], c['logger'], D.N_TASKS, D.R_LOG, name)]
            fr = [x for x in fref['rows'] if (x['K'], x['action_effect'], x['feedback'], x['policy']) == (2, 'crossing', c['feedback'], name)]
            if len(iv) != 1 or len(fr) != 1:
                raise ValueError('exact table lookup not unique for %s %s' % (c['config'], name))
            ipw_var = Fraction(iv[0]['exact_var_V_hat']['exact'])
            tau2 = fr[0]['on_policy_per_episode_variance']
            fresh_var = (Fraction(tau2['easy']['exact']) + Fraction(tau2['hard']['exact'])) / (2 * D.R_FRESH * D.N_TASKS)
            truth = Fraction(kc['policies'][name]['utility']['exact'])
            out[(c['config'], name)] = dict(truth=float(truth), ipw_var=float(ipw_var), fresh_var=float(fresh_var),
                                            d_var=float(ipw_var + fresh_var),
                                            exact=dict(truth=str(truth), ipw_var=str(ipw_var), fresh_var=str(fresh_var),
                                                       d_var=str(ipw_var + fresh_var)))
    return out


def freeze():
    m = dict(request='DTR-REQ-003 P0 fixed-score coverage component (lead f0b4fa2)', root_seed=ROOT_SEED,
             repetitions_per_cell=R_REPS, n_tasks=D.N_TASKS, logged_per_task=D.R_LOG, fresh_per_task_policy=D.R_FRESH,
             task_list=dict(n=D.N_TASKS, sha256=B.task_list(D.N_TASKS)[1], rule="task g = 't%04d' % g, stratum = g mod 2"),
             cells=cells(), workers=WORKERS, cpu_wall_cap_seconds=CAP_S, z=Z,
             stream_namespace="cfg=<cov-config>|rep=<b>|<log|fresh>|<logger name or policy>|<task>|<replicate>",
             draw_source='sampler.SeededDraws: numpy SeedSequence(root_seed, spawn_key=sha256(stream)[:16] as 4 uint32)',
             estimators=dict(ipw='sampler.ipw_estimate: task-equal mean of W*Z on the shared log of the repetition',
                             fresh='sampler.fresh_estimate: task-equal mean of Z on independent fresh blocks per policy',
                             variance='sampler.within_block_variance on the fixed per-episode scores W*Z and Z (exact, then float)',
                             ipw_minus_fresh='estimate IPW - fresh, variance = sum of the two (independent logs), target 0',
                             interval='estimate +/- z * sqrt(variance); diagnostic: estimate +/- z * sqrt(exact variance)',
                             failures='missing/nonfinite/negative variance = failed, noncovering; finite zero variance = point interval'),
             exact_table={'%s|%s' % k: v for k, v in exact_table().items()},
             output_isolation='records written under work/runs (git-ignored) with a writer lock; atomic finalize to results/',
             not_for='fitted DR/OR scores; the broader 2,000-repetition protocol beyond this component',
             source_sha256={rel: D.sha(rel) for rel in HASHED})
    OUT.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=1) + '\n')
    return m


def job(arg):
    c, b = arg
    t0 = time.process_time()
    cell = G.Cell(2, 'crossing', c['feedback'])
    tasks, _ = B.task_list(D.N_TASKS)
    cat = {p.name: p for p in G.catalog(2)}
    ns = S.stream_namespace(c['config'], b)
    draws = S.SeededDraws(ROOT_SEED)
    log = S.run_blocks(tasks, cell, D.R_LOG, draws, ns, 'log', logger=L.LOGGERS[c['logger']], logger_name=c['logger'])
    rec = dict(config=c['config'], repetition=b, namespace=ns, policies={})
    for name in c['policies']:
        pol = cat[name]
        fresh = S.run_blocks(tasks, cell, D.R_FRESH, draws, ns, 'fresh', policy=pol)
        p = dict(ipw=None, ipw_var=None, fresh=None, fresh_var=None, error=None)
        try:   # estimators and variances on the FIXED per-episode scores W*Z (IPW) and Z (fresh), computed exactly
            p['ipw'] = float(S.ipw_estimate(log, pol, tasks, D.R_LOG))
            p['ipw_var'] = float(S.within_block_variance(log, lambda e: S.ipw_weight(e, pol) * e['utility'], tasks, D.R_LOG))
            p['fresh'] = float(S.fresh_estimate(fresh, tasks, D.R_FRESH))
            p['fresh_var'] = float(S.within_block_variance(fresh, lambda e: e['utility'], tasks, D.R_FRESH))
        except Exception as e:   # recorded, never dropped: the analysis counts it as a failed, noncovering interval
            p['error'] = '%s: %s' % (type(e).__name__, str(e)[:200])
        rec['policies'][name] = p
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
            for rec in pool.imap_unordered(job, todo, chunksize=4):
                fh.write(json.dumps(rec) + '\n'); fh.flush(); completed += 1
                if time.time() - start > m['cpu_wall_cap_seconds']:
                    stopped = True; pool.terminate(); break
        # writers closed: certify from the persisted file, not from the counter
        fin = W.finalize(PART, FINAL, expected, key=lambda r: (r['config'], r['repetition']))
    status = dict(wall_seconds=time.time() - start, submitted_this_invocation=len(todo), counter_completed=completed,
                  stopped_by_cap=stopped, persisted=fin)
    (OUT / 'run_status.json').write_text(json.dumps(status, indent=1) + '\n')
    print(json.dumps(status))


def wilson(k, n):
    if n == 0:
        return (float('nan'), float('nan'))
    p = k / n; zz = Z * Z; den = 1 + zz / n
    mid = (p + zz / (2 * n)) / den; half = Z * math.sqrt(p * (1 - p) / n + zz / (4 * n * n)) / den
    return (mid - half, mid + half)


def finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def interval_stats(est, var, target, exact_var, requested):
    """Lead rules (f0b4fa2): a missing/nonfinite estimate or variance, or a negative variance, is a FAILED interval and
    counts as noncoverage; a finite zero variance gives a point interval that covers only on exact equality."""
    n = len(est)
    ok = [finite(e) and finite(v) and v >= 0 for e, v in zip(est, var)]
    cov = sum(1 for e, v, g in zip(est, var, ok) if g and abs(e - target) <= Z * math.sqrt(v))
    ex_cov = sum(1 for e in est if finite(e) and abs(e - target) <= Z * math.sqrt(exact_var))
    fe = [e for e in est if finite(e)]
    err = [e - target for e in fe]; sq = [x * x for x in err]
    mean = lambda a: sum(a) / len(a)
    sd = lambda a: math.sqrt(sum((x - mean(a)) ** 2 for x in a) / (len(a) - 1))
    vv = [v for v, g in zip(var, ok) if g]
    p = cov / n
    return dict(completed=n, finite_estimates=len(fe), bias=mean(err), bias_mcse=sd(err) / math.sqrt(len(err)),
                mse=mean(sq), mse_mcse=sd(sq) / math.sqrt(len(sq)), empirical_sd=sd(fe), empirical_variance=sd(fe) ** 2,
                exact_variance=exact_var, mean_estimated_variance=mean(vv) if vv else None,
                mean_estimated_over_exact_variance=mean(vv) / exact_var if vv else None,
                empirical_over_exact_variance=sd(fe) ** 2 / exact_var,
                wald_covered=cov, wald_coverage=p, wald_coverage_mcse=math.sqrt(p * (1 - p) / n), wald_coverage_wilson=wilson(cov, n),
                wald_coverage_over_requested=cov / requested, average_length=2 * Z * mean([math.sqrt(v) for v in vv]) if vv else None,
                failed_intervals=n - sum(ok), zero_variance_point_intervals=sum(1 for v, g in zip(var, ok) if g and v == 0),
                exact_variance_covered=ex_cov, exact_variance_coverage=ex_cov / n,
                exact_variance_coverage_mcse=math.sqrt((ex_cov / n) * (1 - ex_cov / n) / n))


def diff(a, b):
    return a - b if finite(a) and finite(b) else None


def vsum(a, b):
    return a + b if finite(a) and finite(b) else None


def analyze():
    m = json.loads(MANIFEST.read_text())
    reps = [json.loads(x) for x in FINAL.read_text().splitlines()]
    ids = [(r['config'], r['repetition']) for r in reps]
    if len(ids) != len(set(ids)):
        raise SystemExit('duplicate (config, repetition) ids in the finalized records')
    rows = []
    for c in m['cells']:
        rs = [r for r in reps if r['config'] == c['config']]
        for name in c['policies']:
            ex = m['exact_table']['%s|%s' % (c['config'], name)]
            P = [r['policies'][name] for r in rs]
            ipw = interval_stats([p['ipw'] for p in P], [p['ipw_var'] for p in P], ex['truth'], ex['ipw_var'], m['repetitions_per_cell'])
            fr = interval_stats([p['fresh'] for p in P], [p['fresh_var'] for p in P], ex['truth'], ex['fresh_var'], m['repetitions_per_cell'])
            d = interval_stats([diff(p['ipw'], p['fresh']) for p in P], [vsum(p['ipw_var'], p['fresh_var']) for p in P], 0.0,
                               ex['d_var'], m['repetitions_per_cell'])
            d['rejection_at_zero'] = 1 - d['wald_coverage']; d['exact_variance_rejection_at_zero'] = 1 - d['exact_variance_coverage']
            rows.append(dict(config=c['config'], policy=name, truth=ex['truth'], repetitions=len(rs),
                             recorded_errors=sum(1 for p in P if p['error']), ipw=ipw, fresh=fr, ipw_minus_fresh=d))
    summary = dict(manifest_sha256=hashlib.sha256(MANIFEST.read_bytes()).hexdigest(), reps_sha256=hashlib.sha256(FINAL.read_bytes()).hexdigest(),
                   completion_fraction=len(reps) / (len(m['cells']) * m['repetitions_per_cell']),
                   run_status=json.loads((OUT / 'run_status.json').read_text()), rows=rows,
                   not_claimed=['no multiplicity-adjusted superiority claim', 'no DR/OR inference', 'no real-agent evidence'])
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    lines = ['# Fixed-score coverage component (DTR-REQ-003 P0; lead f0b4fa2)', '',
             'Completion %.4f; nominal 95%% Wald intervals with within-block variance; exact-variance intervals as diagnostic.' % summary['completion_fraction'], '',
             '| Cell | Policy | Estimand | Wald coverage (MCSE) [Wilson] | Exact-var coverage | Mean est. var / exact | Emp. var / exact | Bias (MCSE) | Avg length | Fail/zero |',
             '|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        for key in ('ipw', 'fresh', 'ipw_minus_fresh'):
            s = r[key]
            lines.append('| %s | %s | %s | %.4f (%.4f) [%.4f, %.4f] | %.4f | %.4f | %.4f | %+.5f (%.5f) | %.4f | %d/%d |' % (
                r['config'].replace('cov-K2-crossing-', ''), r['policy'], key, s['wald_coverage'], s['wald_coverage_mcse'],
                s['wald_coverage_wilson'][0], s['wald_coverage_wilson'][1], s['exact_variance_coverage'],
                s['mean_estimated_over_exact_variance'], s['empirical_over_exact_variance'], s['bias'], s['bias_mcse'],
                s['average_length'], s['failed_intervals'], s['zero_variance_point_intervals']))
    (OUT / 'summary.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    {'freeze': freeze, 'run': run, 'analyze': analyze}[sys.argv[1]]()
