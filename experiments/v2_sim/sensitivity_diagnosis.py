"""DTR-REQ-003: RETROSPECTIVE EXPLORATORY diagnosis of the saved replication-sensitivity records (lead 4570b3e, 17:18
cycle). No new episodes, seeds or sweeps; reads results/v2_sim/replication_sensitivity_20260921 only.

For every cell x policy x method (IPW, fresh, D = IPW - fresh) x r (4, 16), over ALL 1,000 repetitions (none dropped):
  - bias = mean error with MCSE sd/sqrt(R);
  - MSE = mean squared error about the exact target, with empirical MCSE sd(e^2)/sqrt(R), against the exact variance
    (the MSE target is Var + bias^2; with an unbiased estimator it equals the exact variance);
  - centered empirical variance (ddof 1) about the Monte Carlo mean, a SEPARATE target from MSE, with a
    leave-one-repetition-out jackknife SE (descriptive finite-repetition uncertainty; no normality claim);
  - Wald and exact-variance lower/upper tail misses with binomial MCSE; standardized skewness of the error with a
    leave-one-repetition-out jackknife SE (supplementary);
  - reproduction of the published Wald and exact-variance covered counts (must match summary.json exactly).
The jackknife unit is the repetition, which keeps each repetition's paired policies and methods together.
For the weak / fixed_LS row the five largest squared-error contributions (repetition IDs) are listed per method and r;
they stay in every summary.
  python sensitivity_diagnosis.py
"""
from __future__ import annotations
import hashlib, json, math
from fractions import Fraction
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'results' / 'v2_sim' / 'replication_sensitivity_20260921'
OUT_JSON, OUT_MD = BASE / 'diagnosis_retrospective.json', BASE / 'diagnosis_retrospective.md'
FOCUS = ('rs-K2-crossing-weak-feedback_dependent_floor_0.2', 'fixed_LS')
METHODS = ('ipw', 'fresh', 'ipw_minus_fresh')


def jackknife_se(x, stat):
    """Leave-one-out jackknife SE of stat(x): sqrt((n-1)/n * sum_i (stat(x_-i) - mean)^2), computed directly."""
    n = len(x)
    loo = np.array([stat(np.delete(x, i)) for i in range(n)])
    return float(math.sqrt((n - 1) / n * np.sum((loo - loo.mean()) ** 2)))


def skewness(x):
    d = x - x.mean()
    return float(np.mean(d ** 3) / np.mean(d ** 2) ** 1.5)


def binom(k, n):
    p = k / n
    return dict(count=int(k), rate=p, mcse=math.sqrt(p * (1 - p) / n))


def series(reps, cfg, pol, method, r, ex):
    """Errors about the exact target, estimated variances and repetition ids, in repetition order."""
    rs = sorted((x for x in reps if x['config'] == cfg), key=lambda x: x['repetition'])
    q = [x['policies'][pol][r] for x in rs]
    if method == 'ipw_minus_fresh':
        est = np.array([p['ipw'] - p['fresh'] for p in q]); var = np.array([p['ipw_var'] + p['fresh_var'] for p in q])
        target, xv = Fraction(0), Fraction(ex[r]['exact']['d_var'])
    else:
        est = np.array([p[method] for p in q]); var = np.array([p[method + '_var'] for p in q])
        target, xv = Fraction(ex[r]['exact']['truth']), Fraction(ex[r]['exact'][method + '_var'])
    return est - float(target), var, float(xv), [x['repetition'] for x in rs]


def diagnose(e, v, xv, z):
    n = len(e)
    sq = e ** 2
    mse, mse_mcse = float(sq.mean()), float(sq.std(ddof=1) / math.sqrt(n))
    cvar = float(e.var(ddof=1))
    cvar_se = jackknife_se(e, lambda y: y.var(ddof=1))
    half = z * np.sqrt(v); xhalf = z * math.sqrt(xv)
    sk = skewness(e)
    return dict(
        repetitions=n, exact_variance=xv,
        bias=float(e.mean()), bias_mcse=float(e.std(ddof=1) / math.sqrt(n)),
        mse=mse, mse_mcse=mse_mcse, mse_over_exact=mse / xv, mse_minus_exact_z=(mse - xv) / mse_mcse,
        centered_variance=cvar, centered_variance_jackknife_se=cvar_se, centered_variance_over_exact=cvar / xv,
        centered_variance_minus_exact_z=(cvar - xv) / cvar_se,
        wald_covered=int(np.sum(np.abs(e) <= half)), exact_variance_covered=int(np.sum(np.abs(e) <= xhalf)),
        wald_lower_miss=binom(np.sum(e < -half), n), wald_upper_miss=binom(np.sum(e > half), n),
        exact_lower_miss=binom(np.sum(e < -xhalf), n), exact_upper_miss=binom(np.sum(e > xhalf), n),
        skewness=sk, skewness_jackknife_se=jackknife_se(e, skewness))


def top_contributions(e, v, ids, k=5):
    sq = e ** 2
    order = np.argsort(-sq, kind='stable')[:k]
    tot = float(sq.sum())
    return [dict(repetition=int(ids[i]), error=float(e[i]), squared_error=float(sq[i]), share_of_sum=float(sq[i] / tot),
                 estimated_variance=float(v[i])) for i in order]


def main():
    m = json.loads((BASE / 'manifest.json').read_text())
    summ = json.loads((BASE / 'summary.json').read_text())
    raw = (BASE / 'reps.jsonl').read_bytes()
    if hashlib.sha256(raw).hexdigest() != summ['reps_sha256'] or \
            hashlib.sha256((BASE / 'manifest.json').read_bytes()).hexdigest() != summ['manifest_sha256']:
        raise SystemExit('saved records or manifest do not match the published summary hashes')
    reps = [json.loads(x) for x in raw.decode().splitlines()]
    ids = {(x['config'], x['repetition']) for x in reps}
    expected = {(c['config'], b) for c in m['cells'] for b in range(m['repetitions_per_cell'])}
    if len(reps) != len(ids) or ids != expected:
        raise SystemExit('record ids are not exactly the manifest ids')
    published = {(r['config'], r['policy']): r for r in summ['rows']}
    rows, top = [], {}
    for c in m['cells']:
        for pol in c['policies']:
            ex = m['exact_table']['%s|%s' % (c['config'], pol)]
            row = dict(config=c['config'], policy=pol)
            for method in METHODS:
                for r in ('4', '16'):
                    e, v, xv, rid = series(reps, c['config'], pol, method, r, ex)
                    d = diagnose(e, v, xv, m['z'])
                    pub = published[(c['config'], pol)][method][r]
                    if (d['wald_covered'], d['exact_variance_covered']) != (pub['wald_covered'], pub['exact_variance_covered']):
                        raise SystemExit('published coverage not reproduced: %s %s %s r=%s' % (c['config'], pol, method, r))
                    d['published_coverage_reproduced'] = True
                    row['%s|r%s' % (method, r)] = d
                    if (c['config'], pol) == FOCUS:
                        top['%s|r%s' % (method, r)] = top_contributions(e, v, rid)
            rows.append(row)
    out = dict(kind='RETROSPECTIVE EXPLORATORY DIAGNOSIS of saved records; no new episodes, seeds or sweeps',
               request='DTR-REQ-003 saved-record diagnosis (lead 4570b3e, 17:18 cycle)',
               source=dict(reps_sha256=summ['reps_sha256'], manifest_sha256=summ['manifest_sha256'], records=len(reps)),
               targets=dict(mse='mean of (estimate - exact target)^2; its target is Var + bias^2, compared with exact variance',
                            centered_variance='sample variance (ddof 1) about the Monte Carlo mean; jackknife SE, leave one repetition out'),
               all_ids_retained=True, rows=rows,
               focus_row=dict(config=FOCUS[0], policy=FOCUS[1], largest_five_squared_errors=top,
                              note='listed for inspection; retained in every summary above'))
    OUT_JSON.write_text(json.dumps(out, indent=1) + '\n')
    lines = ['# Saved-record diagnosis, replication-sensitivity batch (RETROSPECTIVE, EXPLORATORY; lead 4570b3e)', '',
             'All 2,000 records, no exclusions; published coverage counts reproduced for all 36 entries. MSE and centered '
             'variance are separate targets. z = (statistic - exact) / its SE (MSE: empirical MCSE; variance: leave-one-'
             'repetition-out jackknife).', '',
             '| Cell | Policy | Method | r | Bias (MCSE) | MSE/exact (z) | Centered var/exact (jk z) | Wald miss lower/upper | Exact-var miss lower/upper | Skew (jk SE) |',
             '|---|---|---|---|---|---|---|---|---|---|']
    for row in rows:
        for method in METHODS:
            for r in ('4', '16'):
                d = row['%s|r%s' % (method, r)]
                lines.append('| %s | %s | %s | %s | %+.5f (%.5f) | %.3f (%+.2f) | %.3f (%+.2f) | %.3f/%.3f | %.3f/%.3f | %+.3f (%.3f) |' % (
                    'informative' if 'informative' in row['config'] else 'weak', row['policy'], method, r, d['bias'], d['bias_mcse'],
                    d['mse_over_exact'], d['mse_minus_exact_z'], d['centered_variance_over_exact'], d['centered_variance_minus_exact_z'],
                    d['wald_lower_miss']['rate'], d['wald_upper_miss']['rate'], d['exact_lower_miss']['rate'], d['exact_upper_miss']['rate'],
                    d['skewness'], d['skewness_jackknife_se']))
    lines += ['', '## Weak / fixed_LS: five largest squared-error contributions (retained in every summary)', '',
              '| Method | r | Repetition IDs (share of sum of squared errors) | Top-5 share |', '|---|---|---|---|']
    for k, lst in top.items():
        method, r = k.split('|')
        lines.append('| %s | %s | %s | %.4f |' % (method, r[1:], ', '.join('%d (%.4f)' % (t['repetition'], t['share_of_sum']) for t in lst),
                                                 sum(t['share_of_sum'] for t in lst)))
    OUT_MD.write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
