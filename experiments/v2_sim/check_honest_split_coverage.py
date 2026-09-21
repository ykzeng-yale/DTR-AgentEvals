"""Independent recompute of the repeated-training honest-split coverage summary from the raw finalized records (numpy;
does not import the batch code)."""
import hashlib, json, math
from fractions import Fraction
from pathlib import Path

import numpy as np

base = Path(__file__).resolve().parents[2] / 'results' / 'v2_sim' / 'honest_split_coverage_20260921'
m = json.loads((base / 'manifest.json').read_text())
summ = json.loads((base / 'summary.json').read_text())
raw = (base / 'reps.jsonl').read_bytes()
assert hashlib.sha256(raw).hexdigest() == summ['reps_sha256']
reps = [json.loads(x) for x in raw.decode().splitlines()]
ids = [(r['config'], r['repetition']) for r in reps]
assert len(ids) == len(set(ids)) and set(ids) <= {(c['config'], b) for c in m['cells'] for b in range(m['repetitions_per_cell'])}
z = m['z']
maxrel, checks = 0.0, 0


def close(x, y):
    global maxrel, checks
    checks += 1
    maxrel = max(maxrel, abs(float(x) - float(y)) / max(abs(float(x)), 1e-300))


for row in summ['rows']:
    truth = float(Fraction(m['truths'][row['config'] + '|' + row['policy']]['exact']))
    P = [r['policies'][row['policy']] for r in sorted(reps, key=lambda r: r['repetition']) if r['config'] == row['config']]
    assert all(p['error'] is None for p in P), 'recorded failures present: recompute must treat them as noncovering'
    col = lambda k: np.array([p[k] for p in P])
    series = dict(dr=(col('dr'), col('dr_var'), truth), ipw=(col('ipw'), col('ipw_var'), truth),
                  fresh=(col('fresh'), col('fresh_var'), truth),
                  dr_minus_fresh=(col('dr') - col('fresh'), col('dr_var') + col('fresh_var'), 0.0),
                  ipw_minus_fresh=(col('ipw') - col('fresh'), col('ipw_var') + col('fresh_var'), 0.0))
    for key, (e, v, t) in series.items():
        s = row[key]
        err, half = e - t, z * np.sqrt(v)
        assert int(np.sum(np.abs(err) <= half)) == s['wald_covered']
        assert int(np.sum(err < -half)) == round(s['lower_tail_miss'] * len(e)) and int(np.sum(err > half)) == round(s['upper_tail_miss'] * len(e))
        for k, x in dict(bias=err.mean(), bias_mcse=err.std(ddof=1) / math.sqrt(len(e)), rmse=math.sqrt(np.mean(err ** 2)),
                         empirical_variance=e.var(ddof=1), mean_estimated_variance=v.mean(), average_length=np.mean(2 * half),
                         variance_cv=v.std(ddof=1) / v.mean(), error_variance_correlation=np.corrcoef(err, v)[0, 1]).items():
            close(x, s[k])
    d = (col('dr') - truth) ** 2 - (col('ipw') - truth) ** 2
    close(d.mean(), row['paired_dr_minus_ipw_squared_error']['mean'])
    close(d.std(ddof=1) / math.sqrt(len(d)), row['paired_dr_minus_ipw_squared_error']['mcse'])
    close((col('or_plugin') - truth).mean(), row['or_plugin_descriptive']['bias'])
print('records', len(reps), 'rows', len(summ['rows']), 'checks', checks, 'max relative diff', maxrel)
