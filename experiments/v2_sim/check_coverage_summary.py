"""Independent recompute of the coverage summary from the raw finalized records (numpy, separate code path)."""
import json, sys
from pathlib import Path
from fractions import Fraction
import numpy as np

base = str(Path(__file__).resolve().parents[2] / 'results' / 'v2_sim' / 'coverage_fixed_score_20260921') + '/'
m = json.load(open(base + 'manifest.json'))
summ = json.load(open(base + 'summary.json'))
reps = [json.loads(x) for x in open(base + 'reps.jsonl')]
z = 1.959963984540054
maxdiff, checks = 0.0, 0
ids = {(r['config'], r['repetition']) for r in reps}
assert len(ids) == len(reps) == 8000, (len(ids), len(reps))
assert ids == {(c['config'], b) for c in m['cells'] for b in range(2000)}
for row in summ['rows']:
    ex = m['exact_table'][row['config'] + '|' + row['policy']]
    truth = float(Fraction(ex['exact']['truth']))
    P = [r['policies'][row['policy']] for r in reps if r['config'] == row['config']]
    assert len(P) == 2000 and all(p['error'] is None for p in P)
    for key, est, var, tgt, xv in (
            ('ipw', [p['ipw'] for p in P], [p['ipw_var'] for p in P], truth, float(Fraction(ex['exact']['ipw_var']))),
            ('fresh', [p['fresh'] for p in P], [p['fresh_var'] for p in P], truth, float(Fraction(ex['exact']['fresh_var']))),
            ('ipw_minus_fresh', [p['ipw'] - p['fresh'] for p in P], [p['ipw_var'] + p['fresh_var'] for p in P], 0.0,
             float(Fraction(ex['exact']['d_var'])))):
        e, v = np.array(est), np.array(var)
        s = row[key]
        cov = int(np.sum(np.abs(e - tgt) <= z * np.sqrt(v)))
        excov = int(np.sum(np.abs(e - tgt) <= z * np.sqrt(xv)))
        assert cov == s['wald_covered'] and excov == s['exact_variance_covered'], (row['config'], row['policy'], key)
        vals = dict(bias=np.mean(e - tgt), bias_mcse=np.std(e - tgt, ddof=1) / np.sqrt(len(e)), mse=np.mean((e - tgt) ** 2),
                    empirical_sd=np.std(e, ddof=1), mean_estimated_variance=np.mean(v), average_length=np.mean(2 * z * np.sqrt(v)),
                    empirical_over_exact_variance=np.var(e, ddof=1) / xv, mean_estimated_over_exact_variance=np.mean(v) / xv)
        for k, x in vals.items():
            d = abs(float(x) - s[k]) / max(1e-300, abs(float(x)))
            maxdiff = max(maxdiff, d); checks += 1
        assert s['failed_intervals'] == 0 and s['zero_variance_point_intervals'] == int(np.sum(v == 0))
print('checks', checks, 'max relative diff', maxdiff)
