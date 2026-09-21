"""DTR-REQ-003 P0: RETROSPECTIVE conditional-moment diagnosis of the repeated-training honest-split DR batch (lead
9f9e29d, 20:49 cycle). Informative-feedback / feedback-dependent .2 cell only. No new evaluation or fresh streams, seed,
model call or prospective repetition.

For repetitions 0..999 (index order; a bounded prefix if the 900 s wall budget is reached):
  1. reconstruct the ALREADY-USED training stream of that repetition (seed 2026092104, frozen namespace
     cfg=hsc-...|rep=<b>|cohort=train, from 4ec6831) and refit the three policies with honest_split_dr.fit_frozen_q;
     each Q/fallback-table hash must equal the saved record's q_fallback_table_sha256 before the fit is used
     (a mismatch is preserved and reported as the first divergence; that fit is not used);
  2. enumerate the evaluation-episode branches of both strata once (exact, under the known logging kernel) and score
     them with each frozen fit through the published interface honest_split_dr.episode_scores: per-stratum conditional
     mean, variance and third central moment of the per-episode score;
  3. per fit: conditional DR mean over the evaluation manifest (must equal the exact target within 1e-12), exact
     conditional variance of the task-equal average V_fit = n^-2 sum_g var_{s_g} / r, its third cumulant
     sum_g k3_{s_g} / (r^2 n^3) and skewness; the discrepancy uses V_fit + the exact fresh variance of the fixed policy.
Compared with the ORIGINAL saved DR and DR-fresh errors and estimated variances: mean estimated/exact ratios,
empirical variance vs average exact variance with a leave-one-repetition-out jackknife SE, heterogeneity of V_fit across
fits, and coverage / lower-upper tails standardised by each fit's exact conditional variance vs the unchanged original
Wald intervals (published counts must reproduce). Exact-variance intervals here are a DIAGNOSTIC, not usable intervals.
  python conditional_moment_diagnosis.py
"""
from __future__ import annotations
import hashlib, json, math, os, time
from fractions import Fraction
from multiprocessing import Pool

import numpy as np

import coverage_batch as C
import dev_batch as D
import honest_split_coverage as HC
import honest_split_dr as H
import repair_generator as G
import repair_logger as L
import sampler as S
import writer_lock as W

NAME = 'honest_split_conditional_moments_20260921'
OUT = D.ROOT / 'results' / 'v2_sim' / NAME
WORK = D.ROOT / 'work' / 'runs' / NAME
PART = WORK / 'reps.part.jsonl'
CONFIG = 'hsc-K2-crossing-informative-feedback_dependent_floor_0.2'
WORKERS, CAP_S, TOL = 4, 900, 1e-12
HASHED = sorted(set(HC.HASHED + ['experiments/v2_sim/conditional_moment_diagnosis.py', 'experiments/v2_sim/honest_split_coverage.py',
                                 'results/v2_sim/honest_split_coverage_20260921/manifest.json',
                                 'results/v2_sim/honest_split_coverage_20260921/reps.jsonl',
                                 'results/v2_sim/honest_split_coverage_20260921/summary.json']))
_BRANCHES = {}


def spec():
    return next(c for c in HC.cells() if c['config'] == CONFIG)


def branch_records(cell, logger):
    """Enumerated evaluation-episode branches per stratum, as a one-task manifest each (cached per process)."""
    key = (cell.feedback, id(logger))
    if key not in _BRANCHES:
        out = {}
        for s in (0, 1):
            br = H.branches(cell, s, logger=logger)
            p = np.array([float(q) for q, _ in br])
            recs = [dict(rec, task_id='x%d' % s, replicate=i, stream='x%d|%d' % (s, i)) for i, (_, rec) in enumerate(br)]
            out[s] = (p, recs)
        _BRANCHES[key] = out
    return _BRANCHES[key]


def stratum_moments(cell, pol, logger, nu):
    out = {}
    for s, (p, recs) in branch_records(cell, logger).items():
        x = H.episode_scores(recs, pol, cell.K, nu, [('x%d' % s, s)], len(recs))['score']
        m = float(p @ x); d = x - m
        out[s] = dict(mean=m, var=float(p @ d ** 2), k3=float(p @ d ** 3), prob_sum=float(p.sum()), branches=len(recs))
    return out


def job(arg):
    b, saved = arg
    c = spec()
    cell, logger = G.Cell(2, 'crossing', c['feedback']), L.LOGGERS[c['logger']]
    tr, ev, _, _ = H.cohorts()
    cat = {p.name: p for p in G.catalog(2)}
    train = S.run_blocks(tr, cell, H.R_LOG, S.SeededDraws(HC.ROOT_SEED), H.cohort_namespace(CONFIG, b, 'train'), 'log',
                         logger=logger, logger_name=c['logger'])
    n, r = len(ev), H.R_LOG
    rec = dict(repetition=b, policies={})
    for name in c['policies']:
        pol = cat[name]
        nu = H.fit_frozen_q(train, pol, cell.K, tr, r)
        q = dict(hash_match=nu.sha256 == saved[name], refit_sha256=nu.sha256, saved_sha256=saved[name])
        if q['hash_match']:
            mo = stratum_moments(cell, pol, logger, nu)
            q['conditional_mean'] = sum(mo[s]['mean'] for _, s in ev) / n
            q['exact_var'] = sum(mo[s]['var'] for _, s in ev) / (r * n * n)
            q['exact_k3'] = sum(mo[s]['k3'] for _, s in ev) / (r * r * n ** 3)
            q['strata'] = {('easy', 'hard')[s]: mo[s] for s in (0, 1)}
        rec['policies'][name] = q
    return rec


def jk_var_se(x):
    n = len(x); s2 = x.var(ddof=1); xb = x.mean()
    loo = ((n - 1) * s2 - n / (n - 1) * (x - xb) ** 2) / (n - 2)       # deletion identity (tested against direct)
    return float(math.sqrt((n - 1) / n * np.sum((loo - loo.mean()) ** 2)))


def binom(k, n):
    p = k / n
    return dict(count=int(k), rate=p, mcse=math.sqrt(p * (1 - p) / n))


def compare(e, v_est, v_exact, z):
    """Original Wald (estimated variance) vs per-fit exact conditional variance, on the SAME saved errors."""
    n = len(e)
    hw, hx = z * np.sqrt(v_est), z * np.sqrt(v_exact)
    cw, cx = (np.abs(e) <= hw), (np.abs(e) <= hx)
    d = cw.astype(int) - cx.astype(int)
    emp = float(e.var(ddof=1)); jse = jk_var_se(e)
    return dict(
        repetitions=n, wald_covered=int(cw.sum()), wald_coverage=binom(cw.sum(), n),
        wald_lower_miss=binom((e < -hw).sum(), n), wald_upper_miss=binom((e > hw).sum(), n),
        exact_covered=int(cx.sum()), exact_coverage=binom(cx.sum(), n),
        exact_lower_miss=binom((e < -hx).sum(), n), exact_upper_miss=binom((e > hx).sum(), n),
        paired_wald_minus_exact=dict(mean=float(d.mean()), mcse=float(d.std(ddof=1) / math.sqrt(n))),
        mean_estimated_over_exact_ratio=float(np.mean(v_est / v_exact)), ratio_of_means=float(v_est.mean() / v_exact.mean()),
        estimated_over_exact_ratio_quantiles={q: float(np.quantile(v_est / v_exact, q)) for q in (0.05, 0.5, 0.95)},
        corr_error_with_estimated_over_exact=(float(np.corrcoef(e, v_est / v_exact)[0, 1])
                                             if np.std(v_est / v_exact) > 0 and np.std(e) > 0 else None),
        empirical_variance=emp, empirical_variance_jackknife_se=jse, mean_exact_variance=float(v_exact.mean()),
        empirical_over_mean_exact=emp / float(v_exact.mean()), empirical_minus_mean_exact_z=(emp - float(v_exact.mean())) / jse,
        bias=float(e.mean()), bias_mcse=float(e.std(ddof=1) / math.sqrt(n)))


def main():
    m = json.loads(HC.MANIFEST.read_text())
    changed = [rel for rel, h in m['source_sha256'].items() if D.sha(rel) != h]
    if changed:
        raise SystemExit('frozen batch sources changed since 4ec6831: %s' % changed)
    summ = json.loads((HC.OUT / 'summary.json').read_text())
    raw = HC.FINAL.read_bytes()
    if hashlib.sha256(raw).hexdigest() != summ['reps_sha256']:
        raise SystemExit('saved records do not match the published summary hash')
    saved = {r['repetition']: r for r in map(json.loads, raw.decode().splitlines()) if r['config'] == CONFIG}
    c = spec()
    if sorted(saved) != list(range(m['repetitions_per_cell'])):
        raise SystemExit('saved repetitions are not exactly 0..%d' % (m['repetitions_per_cell'] - 1))
    WORK.mkdir(parents=True, exist_ok=True)
    todo = [(b, {n: saved[b]['policies'][n]['q_fallback_table_sha256'] for n in c['policies']}) for b in range(m['repetitions_per_cell'])]
    with W.WriterLock(NAME):
        if PART.exists():
            PART.unlink()
        start, stopped = time.time(), False
        with Pool(WORKERS) as pool, PART.open('w') as fh:
            for rec in pool.imap(job, todo, chunksize=4):              # ORDERED: a capped run keeps an index prefix
                fh.write(json.dumps(rec) + '\n'); fh.flush()
                if time.time() - start > CAP_S:
                    stopped = True; pool.terminate(); break
        wall = time.time() - start
        recs = [json.loads(x) for x in PART.read_text().splitlines()]
    done = [r['repetition'] for r in recs]
    if done != list(range(len(done))):
        raise SystemExit('completed repetitions are not an index prefix')
    ex = C.exact_table()[('cov-K2-crossing-informative-feedback_dependent_floor_0.2', c['policies'][0])]  # noqa: F841 (shape check)
    tr, ev, _, de = H.cohorts()
    rows, first_div = [], None
    for name in c['policies']:
        truth = Fraction(m['truths']['%s|%s' % (CONFIG, name)]['exact'])
        fresh_var = float(Fraction(C.exact_table()[('cov-K2-crossing-informative-feedback_dependent_floor_0.2', name)]['exact']['fresh_var']))
        Q = [r['policies'][name] for r in recs]
        miss = [(r['repetition'], q['refit_sha256'], q['saved_sha256']) for r, q in zip(recs, Q) if not q['hash_match']]
        if miss and first_div is None:
            first_div = dict(policy=name, repetition=miss[0][0], refit=miss[0][1], saved=miss[0][2])
        ok = [(r['repetition'], q) for r, q in zip(recs, Q) if q['hash_match']]
        cm_err = max(abs(q['conditional_mean'] - float(truth)) for _, q in ok)
        P = [saved[b]['policies'][name] for b, _ in ok]
        vx = np.array([q['exact_var'] for _, q in ok])
        k3 = np.array([q['exact_k3'] for _, q in ok])
        e_dr = np.array([p['dr'] for p in P]) - float(truth)
        e_d = np.array([p['dr'] - p['fresh'] for p in P])
        dr = compare(e_dr, np.array([p['dr_var'] for p in P]), vx, m['z'])
        dd = compare(e_d, np.array([p['dr_var'] + p['fresh_var'] for p in P]), vx + fresh_var, m['z'])
        pub = next(x for x in summ['rows'] if x['config'] == CONFIG and x['policy'] == name)
        reproduced = (len(ok) == pub['completed'] and dr['wald_covered'] == pub['dr']['wald_covered']
                      and dd['wald_covered'] == pub['dr_minus_fresh']['wald_covered']
                      and round(dr['wald_lower_miss']['rate'] * len(ok)) == round(pub['dr']['lower_tail_miss'] * pub['completed'])
                      and round(dr['wald_upper_miss']['rate'] * len(ok)) == round(pub['dr']['upper_tail_miss'] * pub['completed']))
        skew_fit = k3 / vx ** 1.5
        st = {sn: dict(mean_var=float(np.mean([q['strata'][sn]['var'] for _, q in ok])),
                       mean_per_episode_skewness=float(np.mean([q['strata'][sn]['k3'] / q['strata'][sn]['var'] ** 1.5 for _, q in ok])),
                       prob_sum_max_dev=float(max(abs(q['strata'][sn]['prob_sum'] - 1) for _, q in ok))) for sn in ('easy', 'hard')}
        rows.append(dict(policy=name, truth=float(truth), fits_used=len(ok), hash_mismatches=len(miss),
                         max_abs_conditional_mean_minus_truth=cm_err, conditional_means_exact=cm_err <= TOL,
                         original_counts_reproduced=reproduced,
                         exact_variance_heterogeneity=dict(mean=float(vx.mean()), cv=float(vx.std(ddof=1) / vx.mean()),
                                                           min=float(vx.min()), max=float(vx.max())),
                         conditional_third_moment=dict(mean_skewness_task_equal_average=float(skew_fit.mean()),
                                                       min=float(skew_fit.min()), max=float(skew_fit.max()), strata=st),
                         fresh_exact_variance=fresh_var, dr=dr, dr_minus_fresh=dd))
    art = dict(kind='RETROSPECTIVE diagnostic of saved records (lead 9f9e29d); no new evaluation/fresh streams, seed, model or grid',
               config=CONFIG, root_seed=HC.ROOT_SEED, frozen_batch='4ec6831',
               requested_repetitions=m['repetitions_per_cell'], completed_prefix=len(recs), stopped_by_cap=stopped,
               wall_seconds=wall, workers=WORKERS, cap_seconds=CAP_S,
               table_hashes_checked=sum(r['fits_used'] + r['hash_mismatches'] for r in rows),
               table_hashes_matched=sum(r['fits_used'] for r in rows), first_divergence=first_div,
               manifest_weights=dict(eval_task_list_sha256=de, easy=sum(1 for _, s in ev if s == 0), hard=sum(1 for _, s in ev if s == 1),
                                     replicates=H.R_LOG),
               exact_variance_note='per-fit exact conditional variance (frozen fit, known logging); a diagnostic, not a usable interval',
               source_sha256={rel: D.sha(rel) for rel in HASHED}, rows=rows)
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = OUT / 'summary.json.tmp'
    tmp.write_text(json.dumps(art, indent=1) + '\n'); os.replace(tmp, OUT / 'summary.json')
    lines = ['# Conditional-moment diagnosis, informative / .2 cell (RETROSPECTIVE; DTR-REQ-003, lead 9f9e29d)', '',
             'Completed index prefix %d of %d repetitions%s; table hashes matched %d of %d. Per-fit exact conditional variance '
             '(frozen fit, known logging) is a DIAGNOSTIC scale, not a usable interval.' % (
                 len(recs), m['repetitions_per_cell'], ' (CAPPED)' if stopped else '', art['table_hashes_matched'], art['table_hashes_checked']), '',
             '| Policy | Estimand | Wald cov. (lower/upper) | Exact-var cov. (lower/upper) | Wald − exact (MCSE) | Mean est./exact | Emp. var / mean exact (jk z) | Exact-var CV across fits | Skew of avg (mean) |',
             '|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        for key in ('dr', 'dr_minus_fresh'):
            s = r[key]
            lines.append('| %s | %s | %.4f (%.3f/%.3f) | %.4f (%.3f/%.3f) | %+.4f (%.4f) | %.4f | %.4f (%+.2f) | %.3f | %+.4f |' % (
                r['policy'], key, s['wald_coverage']['rate'], s['wald_lower_miss']['rate'], s['wald_upper_miss']['rate'],
                s['exact_coverage']['rate'], s['exact_lower_miss']['rate'], s['exact_upper_miss']['rate'],
                s['paired_wald_minus_exact']['mean'], s['paired_wald_minus_exact']['mcse'], s['mean_estimated_over_exact_ratio'],
                s['empirical_over_mean_exact'], s['empirical_minus_mean_exact_z'], r['exact_variance_heterogeneity']['cv'],
                r['conditional_third_moment']['mean_skewness_task_equal_average']))
    (OUT / 'summary.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
