"""DTR-REQ-003: ADDITIVE correction to the retrospective conditional-moment diagnosis (lead 20e186a / bc8f057).

The historical artifact results/v2_sim/honest_split_conditional_moments_20260921/summary.json is left unchanged.
  1. Publishes the immutable per-fit records (all 1,000 repetitions x 3 policies: refit/saved table hashes, per-stratum
     conditional mean / variance / third central moment, V_fit, k3) as per_fit_records.jsonl, finalized atomically from
     the diagnosis run's work file with the expected repetition ids, plus its SHA-256; the records are tied to the
     published summary by recomputing its mean exact variances.
  2. Corrects the uncertainty of (empirical error variance - mean per-fit exact variance): the historical z divided by
     the jackknife SE of the empirical variance ALONE, ignoring that the mean exact variance is random across refits and
     paired with the same errors. Here each leave-one-repetition-out deletion recomputes BOTH the sample error variance
     and the mean exact variance, then their difference and ratio; jackknife SEs are reported for both functionals.
     Any normal reading of difference / SE is EXPLORATORY; no multiplicity-adjusted conclusion.
  3. Discrepancy-specific shape: for D = DR - fresh with independent fresh evaluation, variance V_D = V_DR + V_fresh and
     third cumulant k3_D = k3_DR - k3_fresh (fresh moments exact by enumeration of the fixed policy), standardized
     skewness k3_D / V_D^1.5 and variance CV across fits of V_D. The historical table's discrepancy rows repeated the DR
     skewness and DR V_fit CV; those are DR reference quantities.
Original coverage counts, point ratios and exact-variance interval arithmetic are unaffected.
  python conditional_moment_correction.py
"""
from __future__ import annotations
import hashlib, json, math
from fractions import Fraction as Fr

import numpy as np

import conditional_moment_diagnosis as X
import coverage_batch as C
import dev_batch as D
import honest_split_coverage as HC
import honest_split_dr as H
import repair_generator as G
import repair_logger as L
import writer_lock as W

RECORDS = X.OUT / 'per_fit_records.jsonl'
OUT_JSON, OUT_MD = X.OUT / 'correction_20260921.json', X.OUT / 'correction_20260921.md'
HASHED = sorted(set(X.HASHED + ['experiments/v2_sim/conditional_moment_correction.py',
                                'results/v2_sim/honest_split_conditional_moments_20260921/summary.json']))


def paired_jackknife(e, vx):
    """Leave-one-repetition-out jackknife of diff = var(e, ddof=1) - mean(vx) and ratio = var(e)/mean(vx), deleting the
    SAME repetition from both. Closed-form deletions (sample-variance deletion identity; mean deletion)."""
    n = len(e)
    s2, eb, mx = e.var(ddof=1), e.mean(), vx.mean()
    s2_loo = ((n - 1) * s2 - n / (n - 1) * (e - eb) ** 2) / (n - 2)
    mx_loo = (n * mx - vx) / (n - 1)
    jk = lambda t: float(math.sqrt((n - 1) / n * np.sum((t - t.mean()) ** 2)))
    d_loo, r_loo = s2_loo - mx_loo, s2_loo / mx_loo
    return dict(empirical_variance=float(s2), mean_exact_variance=float(mx), difference=float(s2 - mx),
                difference_jackknife_se=jk(d_loo), ratio=float(s2 / mx), ratio_jackknife_se=jk(r_loo),
                exploratory_difference_z=float((s2 - mx) / jk(d_loo)), exploratory_ratio_minus_one_z=float((s2 / mx - 1) / jk(r_loo)),
                empirical_variance_alone_jackknife_se=jk(s2_loo), mean_exact_variance_jackknife_se=jk(mx_loo))


def fresh_moments(cell, pol, eval_tasks, r):
    """Exact per-stratum mean/variance/third central moment of the fixed policy's on-policy utility, and the task-equal
    average's variance and third cumulant over the evaluation manifest."""
    st = {}
    for s in (0, 1):
        br = H.branches(cell, s, policy=pol)
        m = sum(p * e['utility'] for p, e in br)
        st[s] = dict(mean=m, var=sum(p * (e['utility'] - m) ** 2 for p, e in br), k3=sum(p * (e['utility'] - m) ** 3 for p, e in br))
    n = len(eval_tasks)
    return st, sum(st[s]['var'] for _, s in eval_tasks) / (r * n * n), sum(st[s]['k3'] for _, s in eval_tasks) / (r * r * n ** 3)


def publish_records():
    expected = list(range(1000))
    fin = W.finalize(X.PART, RECORDS, expected, key=lambda r: r['repetition'])
    if fin['missing']:
        raise SystemExit('per-fit records incomplete: %s' % fin)
    return fin, hashlib.sha256(RECORDS.read_bytes()).hexdigest()


def main():
    fin, rec_sha = publish_records()
    recs = [json.loads(x) for x in RECORDS.read_text().splitlines()]
    hist = json.loads((X.OUT / 'summary.json').read_text())
    m = json.loads(HC.MANIFEST.read_text())
    saved = {r['repetition']: r for r in map(json.loads, HC.FINAL.read_text().splitlines()) if r['config'] == X.CONFIG}
    c = X.spec()
    cell = G.Cell(2, 'crossing', c['feedback'])
    tr, ev, _, _ = H.cohorts()
    cat = {p.name: p for p in G.catalog(2)}
    rows = []
    for name in c['policies']:
        hrow = next(r for r in hist['rows'] if r['policy'] == name)
        truth = float(Fr(m['truths']['%s|%s' % (X.CONFIG, name)]['exact']))
        Q = [r['policies'][name] for r in recs]
        assert all(q['hash_match'] for q in Q) and len(Q) == 1000
        vx = np.array([q['exact_var'] for q in Q]); k3 = np.array([q['exact_k3'] for q in Q])
        # tie the published records to the historical summary
        if not math.isclose(float(vx.mean()), hrow['dr']['mean_exact_variance'], rel_tol=1e-12):
            raise SystemExit('records do not reproduce the historical mean exact variance for %s' % name)
        P = [saved[r['repetition']]['policies'][name] for r in recs]
        e_dr = np.array([p['dr'] for p in P]) - truth
        e_d = np.array([p['dr'] - p['fresh'] for p in P])
        fst, v_fresh, k3_fresh = fresh_moments(cell, cat[name], ev, H.R_LOG)
        exact_fresh = Fr(C.exact_table()[('cov-K2-crossing-informative-feedback_dependent_floor_0.2', name)]['exact']['fresh_var'])
        if v_fresh != exact_fresh:
            raise SystemExit('fresh variance by enumeration differs from the accepted table for %s' % name)
        vf, kf = float(v_fresh), float(k3_fresh)
        vd, k3d = vx + vf, k3 - kf
        rows.append(dict(
            policy=name,
            dr=dict(jackknife=paired_jackknife(e_dr, vx), historical_z_used_empirical_variance_se_alone=hrow['dr']['empirical_minus_mean_exact_z'],
                    skewness_of_average=dict(mean=float(np.mean(k3 / vx ** 1.5)), min=float(np.min(k3 / vx ** 1.5)), max=float(np.max(k3 / vx ** 1.5))),
                    variance_cv_across_fits=float(vx.std(ddof=1) / vx.mean())),
            dr_minus_fresh=dict(jackknife=paired_jackknife(e_d, vd),
                                historical_z_used_empirical_variance_se_alone=hrow['dr_minus_fresh']['empirical_minus_mean_exact_z'],
                                fresh_exact=dict(variance=vf, k3=kf, skewness=kf / vf ** 1.5),
                                skewness_of_discrepancy=dict(mean=float(np.mean(k3d / vd ** 1.5)), min=float(np.min(k3d / vd ** 1.5)),
                                                             max=float(np.max(k3d / vd ** 1.5))),
                                variance_cv_across_fits=float(vd.std(ddof=1) / vd.mean()),
                                historical_table_repeated_dr_reference=dict(skewness=hrow['conditional_third_moment']['mean_skewness_task_equal_average'],
                                                                            variance_cv=hrow['exact_variance_heterogeneity']['cv']))))
    art = dict(kind='ADDITIVE correction to a RETROSPECTIVE diagnostic (lead 20e186a / bc8f057); historical summary.json unchanged',
               per_fit_records=dict(path='results/v2_sim/honest_split_conditional_moments_20260921/per_fit_records.jsonl',
                                    sha256=rec_sha, finalize=fin),
               correction='z now uses a PAIRED leave-one-repetition-out jackknife recomputing both the error variance and the mean per-fit exact variance; normal readings are exploratory',
               source_sha256={rel: D.sha(rel) for rel in HASHED}, rows=rows)
    OUT_JSON.write_text(json.dumps(art, indent=1) + '\n')
    lines = ['# Correction: conditional-moment diagnosis, informative / .2 (ADDITIVE; lead 20e186a / bc8f057)', '',
             'Historical `summary.json` unchanged. Per-fit records published: `per_fit_records.jsonl` (SHA-256 `%s`, %d rows). '
             'z below uses a paired leave-one-repetition-out jackknife of BOTH the empirical error variance and the mean '
             'per-fit exact variance (exploratory normal reading).' % (rec_sha, fin['records']), '',
             '| Policy | Estimand | Emp. var | Mean exact var | Difference (paired jk SE) | Ratio (paired jk SE) | Corrected z | Historical z (emp. SE only) | Skewness of estimand (mean over fits) | Variance CV across fits |',
             '|---|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        for key, sk, lab in (('dr', r['dr']['skewness_of_average']['mean'], 'DR'),
                             ('dr_minus_fresh', r['dr_minus_fresh']['skewness_of_discrepancy']['mean'], 'DR − fresh')):
            j = r[key]['jackknife']
            lines.append('| %s | %s | %.4e | %.4e | %+.3e (%.3e) | %.4f (%.4f) | %+.2f | %+.2f | %+.4f | %.3f |' % (
                r['policy'], lab, j['empirical_variance'], j['mean_exact_variance'], j['difference'], j['difference_jackknife_se'],
                j['ratio'], j['ratio_jackknife_se'], j['exploratory_difference_z'], r[key]['historical_z_used_empirical_variance_se_alone'],
                sk, r[key]['variance_cv_across_fits']))
    lines += ['', 'DR − fresh rows use V_DR + V_fresh and k3_DR − k3_fresh (fresh exact by enumeration, equal to the accepted '
              'fresh table); the historical table repeated the DR reference values on those rows.']
    OUT_MD.write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
