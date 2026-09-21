"""DTR-REQ-003 P0: fixed-fit conditional DEVELOPMENT coverage (lead 20e186a, 21:49 cycle).

Informative-feedback / feedback-dependent .2 cell only. FROZEN nuisances: original training repetitions 0,1,2,3,4 of the
2026092104 repeated-training study (chosen by index), all three policies = 15 Q/fallback tables. At freeze time their
training streams are reconstructed, refitted ONCE, required to match the saved q_fallback_table_sha256, serialized to
nuisances.json with metadata, and their exact per-fit conditional moments are pinned in the manifest. The study itself
NEVER refits: it deserializes the tables.
For each fit f and evaluation repetition j = 0..1,999 (10,000 jobs; evalrep OUTER, fit INNER so an administrative cap
leaves roughly balanced index prefixes): a new evaluation cohort (250 balanced tasks t0250..t0499 x 4 logged, logger
feedback_dependent_floor_0.2) and an independent fresh reference (x 4 per policy), root seed 2026092105, namespaces
  study=hsf|cfg=<cell>|fit=<f>|evalrep=<j>|cohort=<eval|fresh>|<log|fresh>|<logger or policy>|<task>|<replicate>.
The evaluation log is shared across the three policies within a fit/repetition (paired, intentional).
Per policy: DR (frozen fit) with the within-task variance; D = DR - fresh with summed variance; fresh control; IPW on the
same evaluation records retained (no extra cohort). Wald intervals z = 1.959963984540054 and exact-conditional-variance
DIAGNOSTIC intervals (fixed per fit: V_DR(f); V_DR(f) + V_fresh; V_fresh; V_IPW). Five fits characterise those five
nuisances only, not uniform conditional validity; not CONFIRM, not cross-fitted inference, not interval tuning.
At most 4 processes, 900-second TOTAL wall budget (administrative); a capped batch is INCOMPLETE with explicit
requested/completed denominators. Writer lock + atomic finalize; analysis frozen with the code.
  python fixed_fit_coverage.py freeze | run | analyze
"""
from __future__ import annotations
import hashlib, json, math, sys, time
from fractions import Fraction
from multiprocessing import Pool

import numpy as np

import conditional_moment_diagnosis as X
import coverage_batch as C
import dev_batch as D
import honest_split_coverage as HC
import honest_split_dr as H
import repair_generator as G
import repair_logger as L
import replication_sensitivity as R
import sampler as S
import writer_lock as W

NAME = 'fixed_fit_coverage_20260921'
OUT = D.ROOT / 'results' / 'v2_sim' / NAME
WORK = D.ROOT / 'work' / 'runs' / NAME
MANIFEST, NUIS, PART, FINAL = OUT / 'manifest.json', OUT / 'nuisances.json', WORK / 'reps.part.jsonl', OUT / 'reps.jsonl'
ROOT_SEED, FITS, EVALREPS, WORKERS, CAP_S, Z = 2026092105, (0, 1, 2, 3, 4), 2000, 4, 900, C.Z
CELL_CONFIG = X.CONFIG                                   # hsc-K2-crossing-informative-feedback_dependent_floor_0.2
STUDY_CELL = 'K2-crossing-informative-feedback_dependent_floor_0.2'
HASHED = sorted(set(HC.HASHED + ['experiments/v2_sim/fixed_fit_coverage.py', 'experiments/v2_sim/conditional_moment_diagnosis.py',
                                 'experiments/v2_sim/honest_split_coverage.py',
                                 'results/v2_sim/honest_split_coverage_20260921/manifest.json',
                                 'results/v2_sim/honest_split_coverage_20260921/reps.jsonl']))
ESTIMANDS = ('dr', 'dr_minus_fresh', 'fresh', 'ipw')
_NU = {}


def spec():
    return X.spec()


def namespace(f, j, cohort):
    if cohort not in ('eval', 'fresh'):
        raise ValueError('cohort must be eval or fresh')
    return 'study=hsf|cfg=%s|fit=%d|evalrep=%d|cohort=%s' % (STUDY_CELL, f, j, cohort)


# ---- serialization of frozen nuisances -------------------------------------------------------------------------------
def serialize(nu):
    Q, fb = nu.tables()
    return dict(policy=nu.policy, sha256=nu.sha256, feature_map=nu.feature_map, training_episodes=nu.training_episodes,
                missing_q_cells_in_training=nu.missing_q_cells_in_training, training_tasks=sorted(nu.training_tasks),
                Q=[[[[k[0], k[1], list(k[2]), list(k[3])], {str(a): v for a, v in sorted(q[k].items())}] for k in sorted(q, key=repr)] for q in Q],
                fallback=[{str(a): v for a, v in sorted(f.items())} for f in fb])


def deserialize(d):
    Q = [{(k[0], k[1], tuple(k[2]), tuple(k[3])): {int(a): float(v) for a, v in vals.items()} for k, vals in stage} for stage in d['Q']]
    fb = [{int(a): float(v) for a, v in f.items()} for f in d['fallback']]
    nu = H.freeze(Q, fb, d['policy'], d['training_tasks'], d['training_episodes'], d['missing_q_cells_in_training'], d['feature_map'])
    if nu.sha256 != d['sha256']:
        raise ValueError('deserialized table hash differs from the frozen hash for %s' % d['policy'])
    return nu


def reconstruct_fit(f):
    """Refit ONCE (freeze time only) from the original training stream of repetition f; returns {policy: FrozenNuisance}."""
    c = spec()
    cell, logger = G.Cell(2, 'crossing', c['feedback']), L.LOGGERS[c['logger']]
    tr, _, _, _ = H.cohorts()
    train = S.run_blocks(tr, cell, H.R_LOG, S.SeededDraws(HC.ROOT_SEED), H.cohort_namespace(CELL_CONFIG, f, 'train'), 'log',
                         logger=logger, logger_name=c['logger'])
    cat = {p.name: p for p in G.catalog(2)}
    return {n: H.fit_frozen_q(train, cat[n], cell.K, tr, H.R_LOG) for n in c['policies']}


def freeze():
    c = spec()
    cell, logger = G.Cell(2, 'crossing', c['feedback']), L.LOGGERS[c['logger']]
    _, ev, _, de = H.cohorts()
    hm = json.loads(HC.MANIFEST.read_text())
    saved = {r['repetition']: r for r in map(json.loads, HC.FINAL.read_text().splitlines()) if r['config'] == CELL_CONFIG}
    cat = {p.name: p for p in G.catalog(2)}
    nuis, exact = {}, {}
    for f in FITS:
        fits = reconstruct_fit(f)
        for name, nu in fits.items():
            if nu.sha256 != saved[f]['policies'][name]['q_fallback_table_sha256']:
                raise SystemExit('fit %d %s: refit hash differs from the saved table hash' % (f, name))
            nuis['%d|%s' % (f, name)] = serialize(nu)
            mo = X.stratum_moments(cell, cat[name], logger, nu)
            n, r = len(ev), H.R_LOG
            truth = Fraction(hm['truths']['%s|%s' % (CELL_CONFIG, name)]['exact'])
            cm = sum(mo[s]['mean'] for _, s in ev) / n
            if abs(cm - float(truth)) > 1e-12:
                raise SystemExit('fit %d %s: conditional DR mean differs from the target' % (f, name))
            v_dr = sum(mo[s]['var'] for _, s in ev) / (r * n * n)
            ex = C.exact_table()[('cov-' + STUDY_CELL, name)]['exact']
            v_fresh, v_ipw = float(Fraction(ex['fresh_var'])), float(Fraction(ex['ipw_var']))
            exact['%d|%s' % (f, name)] = dict(truth=float(truth), truth_exact=str(truth), conditional_dr_mean=cm, dr_var=v_dr,
                                              fresh_var=v_fresh, dr_minus_fresh_var=v_dr + v_fresh, ipw_var=v_ipw,
                                              strata={('easy', 'hard')[s]: mo[s] for s in (0, 1)})
    OUT.mkdir(parents=True, exist_ok=True)
    NUIS.write_text(json.dumps(dict(source='training repetitions 0..4 of results/v2_sim/honest_split_coverage_20260921 (seed 2026092104)',
                                    tables=nuis), indent=0) + '\n')
    m = dict(request='DTR-REQ-003 P0 fixed-fit conditional development coverage (lead 20e186a)',
             kind='DEVELOPMENT diagnostic prompted by earlier outcomes; characterises five fixed nuisances; not CONFIRM, not cross-fitted, not interval tuning',
             root_seed=ROOT_SEED, fits=list(FITS), fit_selection='training repetitions 0..4 by index', evaluation_repetitions=EVALREPS,
             jobs=len(FITS) * EVALREPS, order='evalrep outer, fit inner', cell=c, workers=WORKERS, total_wall_budget_seconds=CAP_S, z=Z,
             eval_cohort=dict(tasks='t0250..t0499', sha256=de, replicates=H.R_LOG), fresh_replicates=H.R_FRESH,
             stream_namespace='study=hsf|cfg=<cell>|fit=<f>|evalrep=<j>|cohort=<eval|fresh>|<log|fresh>|<logger or policy>|<task>|<replicate>',
             nuisances=dict(path='results/v2_sim/%s/nuisances.json' % NAME, sha256=hashlib.sha256(NUIS.read_bytes()).hexdigest(),
                            table_hashes={k: v['sha256'] for k, v in nuis.items()}, refit_during_study=False),
             exact=exact, estimands=dict(dr='frozen-fit DR + within-task variance', dr_minus_fresh='summed variance, target 0',
                                         fresh='control', ipw='retained on the same evaluation records'),
             failures='missing/nonfinite/negative variance = failed, noncovering; errors recorded, never dropped',
             not_claimed=['uniform conditional validity', 'every possible training fit', 'CONFIRM', 'cross-fitted inference', 'interval tuning'],
             output_isolation='records under work/runs (git-ignored) with a writer lock; atomic finalize to results/',
             source_sha256={rel: D.sha(rel) for rel in HASHED})
    MANIFEST.write_text(json.dumps(m, indent=1) + '\n')
    return m


# ---- evaluation ------------------------------------------------------------------------------------------------------
def nuisances():
    if not _NU:
        m = json.loads(MANIFEST.read_text())
        raw = NUIS.read_bytes()
        if hashlib.sha256(raw).hexdigest() != m['nuisances']['sha256']:
            raise ValueError('nuisances.json differs from the frozen manifest')
        for k, d in json.loads(raw)['tables'].items():
            _NU[k] = deserialize(d)
    return _NU


def policy_block(evalu, fresh, pol, K, ev, nu):
    p = dict(error=None)
    try:
        dr = H.dr_estimate_and_variance(evalu, pol, K, nu, ev, H.R_LOG)
        p.update(dr=dr['estimate'], dr_var=dr['variance'], or_plugin=dr['or_plugin'],
                 fresh=float(S.fresh_estimate(fresh, ev, H.R_FRESH)),
                 fresh_var=float(S.within_block_variance(fresh, lambda e: e['utility'], ev, H.R_FRESH)),
                 ipw=float(S.ipw_estimate(evalu, pol, ev, H.R_LOG)),
                 ipw_var=float(S.within_block_variance(evalu, lambda e: S.ipw_weight(e, pol) * e['utility'], ev, H.R_LOG)))
    except Exception as e:     # recorded, never dropped: counted as failed, noncovering
        p['error'] = '%s: %s' % (type(e).__name__, str(e)[:200])
    return p


def job(arg, memoize=True):
    if memoize:
        with R.ValidateOncePerBlock():
            return job(arg, memoize=False)
    f, j = arg
    t0 = time.process_time()
    c = spec()
    cell, logger = G.Cell(2, 'crossing', c['feedback']), L.LOGGERS[c['logger']]
    _, ev, _, _ = H.cohorts()
    cat = {p.name: p for p in G.catalog(2)}
    nus = nuisances()
    draws = S.SeededDraws(ROOT_SEED)
    evalu = S.run_blocks(ev, cell, H.R_LOG, draws, namespace(f, j, 'eval'), 'log', logger=logger, logger_name=c['logger'])
    rec = dict(fit=f, evalrep=j, policies={})
    for name in c['policies']:
        pol = cat[name]
        fresh = S.run_blocks(ev, cell, H.R_FRESH, draws, namespace(f, j, 'fresh'), 'fresh', policy=pol)
        rec['policies'][name] = policy_block(evalu, fresh, pol, cell.K, ev, nus['%d|%s' % (f, name)])
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
    expected = [(f, j) for j in range(m['evaluation_repetitions']) for f in m['fits']]
    with W.WriterLock(NAME):
        done = {(r['fit'], r['evalrep']) for r in map(json.loads, PART.read_text().splitlines())} if PART.exists() else set()
        todo = [x for x in expected if x not in done]
        start, completed, stopped = time.time(), 0, False
        with Pool(m['workers']) as pool, PART.open('a') as fh:
            for rec in pool.imap_unordered(job, todo, chunksize=2):
                fh.write(json.dumps(rec) + '\n'); fh.flush(); completed += 1
                if time.time() - start > m['total_wall_budget_seconds']:
                    stopped = True; pool.terminate(); break
        fin = W.finalize(PART, FINAL, expected, key=lambda r: (r['fit'], r['evalrep']))
    status = dict(wall_seconds=time.time() - start, submitted_this_invocation=len(todo), counter_completed=completed,
                  stopped_by_cap=stopped, persisted=fin, requested=len(expected), complete=fin['records'] == len(expected) and fin['missing'] == 0)
    (OUT / 'run_status.json').write_text(json.dumps(status, indent=1) + '\n')
    print(json.dumps(status))


# ---- analysis (frozen with the code) ---------------------------------------------------------------------------------
def binom(k, n):
    p = k / n if n else float('nan')
    return dict(count=int(k), rate=p, mcse=math.sqrt(p * (1 - p) / n) if n else None, wilson=C.wilson(k, n))


def stats(est, var, target, exact_var, requested):
    """Wald (estimated variance) vs exact-conditional-variance diagnostic on the same errors. Failures noncovering."""
    n = len(est)
    ok = [C.finite(e) and C.finite(v) and v >= 0 for e, v in zip(est, var)]
    fe = np.array([e for e in est if C.finite(e)], float)
    hx = Z * math.sqrt(exact_var)
    cw = np.array([1 if g and abs(e - target) <= Z * math.sqrt(v) else 0 for e, v, g in zip(est, var, ok)])
    cx = np.array([1 if C.finite(e) and abs(e - target) <= hx else 0 for e in est])
    lw = sum(1 for e, v, g in zip(est, var, ok) if g and e - target < -Z * math.sqrt(v))
    uw = sum(1 for e, v, g in zip(est, var, ok) if g and e - target > Z * math.sqrt(v))
    lx = sum(1 for e in est if C.finite(e) and e - target < -hx)
    ux = sum(1 for e in est if C.finite(e) and e - target > hx)
    d = cw - cx
    out = dict(completed=n, requested=requested, failed_intervals=n - sum(ok),
               wald_coverage=binom(int(cw.sum()), n), wald_lower_miss=binom(lw, n), wald_upper_miss=binom(uw, n),
               exact_coverage=binom(int(cx.sum()), n), exact_lower_miss=binom(lx, n), exact_upper_miss=binom(ux, n),
               wald_covered_over_requested=int(cw.sum()) / requested, exact_variance=exact_var)
    if len(fe) >= 3:
        err = fe - target
        vv = np.array([v for v, g in zip(var, ok) if g])
        s2 = float(fe.var(ddof=1))
        out.update(paired_wald_minus_exact=dict(mean=float(d.mean()), mcse=float(d.std(ddof=1) / math.sqrt(n))),
                   bias=float(err.mean()), bias_mcse=float(err.std(ddof=1) / math.sqrt(len(err))),
                   empirical_variance=s2, empirical_over_exact=s2 / exact_var,
                   empirical_variance_jackknife_se=X.jk_var_se(fe),
                   empirical_minus_exact_z=(s2 - exact_var) / X.jk_var_se(fe),
                   mean_estimated_variance=float(vv.mean()), mean_estimated_over_exact=float(vv.mean()) / exact_var,
                   average_wald_length=float(np.mean(2 * Z * np.sqrt(vv))), exact_length=2 * hx)
    return out


def analyze():
    m = json.loads(MANIFEST.read_text())
    reps = [json.loads(x) for x in FINAL.read_text().splitlines()]
    ids = [(r['fit'], r['evalrep']) for r in reps]
    if len(ids) != len(set(ids)):
        raise SystemExit('duplicate ids in the finalized records')
    rows = []
    for f in m['fits']:
        rs = sorted((r for r in reps if r['fit'] == f), key=lambda r: r['evalrep'])
        for name in m['cell']['policies']:
            ex = m['exact']['%d|%s' % (f, name)]
            P = [r['policies'][name] for r in rs]
            g = lambda k: [p.get(k) for p in P]
            row = dict(fit=f, policy=name, truth=ex['truth'], requested=m['evaluation_repetitions'], completed=len(rs),
                       recorded_errors=sum(1 for p in P if p['error']), table_sha256=m['nuisances']['table_hashes']['%d|%s' % (f, name)])
            row['dr'] = stats(g('dr'), g('dr_var'), ex['truth'], ex['dr_var'], m['evaluation_repetitions'])
            row['dr_minus_fresh'] = stats([C.diff(p.get('dr'), p.get('fresh')) for p in P], [C.vsum(p.get('dr_var'), p.get('fresh_var')) for p in P],
                                          0.0, ex['dr_minus_fresh_var'], m['evaluation_repetitions'])
            row['fresh'] = stats(g('fresh'), g('fresh_var'), ex['truth'], ex['fresh_var'], m['evaluation_repetitions'])
            row['ipw'] = stats(g('ipw'), g('ipw_var'), ex['truth'], ex['ipw_var'], m['evaluation_repetitions'])
            rows.append(row)
    requested = len(m['fits']) * m['evaluation_repetitions']
    summary = dict(kind=m['kind'], manifest_sha256=hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
                   reps_sha256=hashlib.sha256(FINAL.read_bytes()).hexdigest(), requested=requested, completed=len(reps),
                   completion_fraction=len(reps) / requested, run_status=json.loads((OUT / 'run_status.json').read_text()),
                   rows=rows, not_claimed=m['not_claimed'])
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    fm = lambda x, s: s % x if C.finite(x) else 'n/a'
    lines = ['# Fixed-fit conditional coverage, informative / .2 (DTR-REQ-003 P0; lead 20e186a) — DEVELOPMENT', '',
             'Completed %d of %d requested fit/evaluation jobs (fraction %.4f)%s. Five frozen fits (training repetitions 0-4 by '
             'index), never refitted. Wald = estimated within-task variance; exact = the fit\'s exact conditional variance '
             '(diagnostic). These five fits only; no uniform conditional validity claim.' % (
                 len(reps), requested, summary['completion_fraction'], '' if len(reps) == requested else ' — INCOMPLETE (cap)'), '',
             '| Fit | Policy | Estimand | Wald cov. (MCSE) | Wald lower/upper | Exact-var cov. | Exact lower/upper | Wald − exact (MCSE) | Emp./exact var (jk z) | Mean est./exact | Bias (MCSE) | Fail |',
             '|---|---|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        for key in ESTIMANDS:
            s = r[key]; pw = s.get('paired_wald_minus_exact', {})
            lines.append('| %d | %s | %s | %s (%s) | %s/%s | %s | %s/%s | %s (%s) | %s (%s) | %s | %s (%s) | %d |' % (
                r['fit'], r['policy'], key, fm(s['wald_coverage']['rate'], '%.4f'), fm(s['wald_coverage']['mcse'], '%.4f'),
                fm(s['wald_lower_miss']['rate'], '%.4f'), fm(s['wald_upper_miss']['rate'], '%.4f'), fm(s['exact_coverage']['rate'], '%.4f'),
                fm(s['exact_lower_miss']['rate'], '%.4f'), fm(s['exact_upper_miss']['rate'], '%.4f'), fm(pw.get('mean'), '%+.4f'),
                fm(pw.get('mcse'), '%.4f'), fm(s.get('empirical_over_exact'), '%.4f'), fm(s.get('empirical_minus_exact_z'), '%+.2f'),
                fm(s.get('mean_estimated_over_exact'), '%.4f'), fm(s.get('bias'), '%+.5f'), fm(s.get('bias_mcse'), '%.5f'), s['failed_intervals']))
    (OUT / 'summary.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    {'freeze': freeze, 'run': run, 'analyze': analyze}[sys.argv[1]]()
