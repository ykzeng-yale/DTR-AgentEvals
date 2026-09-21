"""Independent recompute of the replication-sensitivity summary from the raw finalized records (numpy, separate code)."""
import json
from fractions import Fraction
from pathlib import Path

import numpy as np

base = Path(__file__).resolve().parents[2] / 'results' / 'v2_sim' / 'replication_sensitivity_20260921'
m = json.loads((base / 'manifest.json').read_text())
summ = json.loads((base / 'summary.json').read_text())
reps = [json.loads(x) for x in (base / 'reps.jsonl').read_text().splitlines()]
z = m['z']
ids = {(r['config'], r['repetition']) for r in reps}
assert len(ids) == len(reps) == len(m['cells']) * m['repetitions_per_cell']
assert ids == {(c['config'], b) for c in m['cells'] for b in range(m['repetitions_per_cell'])}
maxrel, checks = 0.0, 0


def close(x, y):
    global maxrel, checks
    checks += 1
    d = abs(float(x) - float(y)) / max(abs(float(x)), 1e-300)
    maxrel = max(maxrel, d)


for row in summ['rows']:
    ex = m['exact_table'][row['config'] + '|' + row['policy']]
    P = [r['policies'][row['policy']] for r in sorted(reps, key=lambda r: r['repetition']) if r['config'] == row['config']]
    assert all(p[k]['error'] is None for p in P for k in ('4', '16'))
    for key in ('ipw', 'fresh', 'ipw_minus_fresh'):
        cov = {}
        for r in ('4', '16'):
            q = [p[r] for p in P]
            if key == 'ipw_minus_fresh':
                e = np.array([x['ipw'] - x['fresh'] for x in q]); v = np.array([x['ipw_var'] + x['fresh_var'] for x in q])
                tgt, xv = 0.0, float(Fraction(ex[r]['exact']['d_var']))
            else:
                e = np.array([x[key] for x in q]); v = np.array([x[key + '_var'] for x in q])
                tgt, xv = float(Fraction(ex[r]['exact']['truth'])), float(Fraction(ex[r]['exact'][key + '_var']))
            s = row[key][r]
            half = z * np.sqrt(v)
            cov[r] = (np.abs(e - tgt) <= half).astype(int)
            assert int(cov[r].sum()) == s['wald_covered'] and int((np.abs(e - tgt) <= z * np.sqrt(xv)).sum()) == s['exact_variance_covered']
            assert s['failed_intervals'] == 0 and s['zero_variance_point_intervals'] == int((v == 0).sum())
            assert int((e - tgt < -half).sum()) == round(s['lower_tail_miss'] * len(e)) and int((e - tgt > half).sum()) == round(s['upper_tail_miss'] * len(e))
            for k, x in dict(bias=np.mean(e - tgt), mse=np.mean((e - tgt) ** 2), empirical_sd=np.std(e, ddof=1),
                             mean_estimated_variance=np.mean(v), average_length=np.mean(2 * half),
                             error_variance_correlation=np.corrcoef(e - tgt, v)[0, 1], variance_cv=np.std(v, ddof=1) / np.mean(v),
                             mean_estimated_over_exact_variance=np.mean(v) / xv).items():
                close(x, s[k])
        d = cov['16'] - cov['4']
        pr = row[key]['paired_r16_minus_r4']['wald_coverage']
        close(d.mean() if d.mean() else 1e-300, pr['mean'] if pr['mean'] else 1e-300)
        close(d.std(ddof=1) / np.sqrt(len(d)), pr['mcse'])
print('records', len(reps), 'checks', checks, 'max relative diff', maxrel)
