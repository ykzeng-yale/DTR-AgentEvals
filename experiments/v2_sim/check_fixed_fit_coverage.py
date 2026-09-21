"""Independent recompute of the fixed-fit coverage summary from the raw finalized records (numpy; does not import the
study code). Every recomputed quantity is ASSERTED within abs-or-rel 1e-12."""
import hashlib, json, math
from pathlib import Path

import numpy as np

TOL = 1e-12
base = Path(__file__).resolve().parents[2] / 'results' / 'v2_sim' / 'fixed_fit_coverage_20260921'
m = json.loads((base / 'manifest.json').read_text())
summ = json.loads((base / 'summary.json').read_text())
raw = (base / 'reps.jsonl').read_bytes()
assert hashlib.sha256(raw).hexdigest() == summ['reps_sha256']
reps = [json.loads(x) for x in raw.decode().splitlines()]
ids = [(r['fit'], r['evalrep']) for r in reps]
assert len(ids) == len(set(ids)) and set(ids) <= {(f, j) for f in m['fits'] for j in range(m['evaluation_repetitions'])}
z = m['z']
checks, maxrel = 0, 0.0


def close(x, y):
    global checks, maxrel
    checks += 1
    a = abs(float(x) - float(y)); r = a / max(abs(float(x)), 1e-300)
    assert a <= TOL or r <= TOL, 'recompute disagrees: %r vs %r' % (x, y)
    maxrel = max(maxrel, r)


for row in summ['rows']:
    ex = m['exact']['%d|%s' % (row['fit'], row['policy'])]
    P = [r['policies'][row['policy']] for r in sorted(reps, key=lambda r: r['evalrep']) if r['fit'] == row['fit']]
    assert all(p['error'] is None for p in P), 'failures present: recompute must treat them as noncovering'
    col = lambda k: np.array([p[k] for p in P])
    series = dict(dr=(col('dr'), col('dr_var'), ex['truth'], ex['dr_var']),
                  dr_minus_fresh=(col('dr') - col('fresh'), col('dr_var') + col('fresh_var'), 0.0, ex['dr_minus_fresh_var']),
                  fresh=(col('fresh'), col('fresh_var'), ex['truth'], ex['fresh_var']),
                  ipw=(col('ipw'), col('ipw_var'), ex['truth'], ex['ipw_var']))
    for key, (e, v, t, xv) in series.items():
        s = row[key]
        err, hw, hx = e - t, z * np.sqrt(v), z * math.sqrt(xv)
        cw, cx = np.abs(err) <= hw, np.abs(err) <= hx
        assert int(cw.sum()) == s['wald_coverage']['count'] and int(cx.sum()) == s['exact_coverage']['count']
        assert int((err < -hw).sum()) == s['wald_lower_miss']['count'] and int((err > hw).sum()) == s['wald_upper_miss']['count']
        assert int((err < -hx).sum()) == s['exact_lower_miss']['count'] and int((err > hx).sum()) == s['exact_upper_miss']['count']
        d = cw.astype(int) - cx.astype(int)
        for k, x in dict(bias=err.mean(), bias_mcse=err.std(ddof=1) / math.sqrt(len(e)), empirical_variance=e.var(ddof=1),
                         empirical_over_exact=e.var(ddof=1) / xv, mean_estimated_variance=v.mean(),
                         average_wald_length=np.mean(2 * hw)).items():
            close(x, s[k])
        close(d.mean() if d.mean() else 1e-300, s['paired_wald_minus_exact']['mean'] if s['paired_wald_minus_exact']['mean'] else 1e-300)
        close(d.std(ddof=1) / math.sqrt(len(d)), s['paired_wald_minus_exact']['mcse'])
print('records', len(reps), 'rows', len(summ['rows']), 'checks', checks, 'max relative diff', maxrel)
