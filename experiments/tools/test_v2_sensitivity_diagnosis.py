"""Checks for the retrospective saved-record diagnosis: jackknife against closed forms, statistics on hand values, and
the committed output (all ids retained, published coverage reproduced, MSE and centered variance kept separate)."""
import json, math, sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import sensitivity_diagnosis as X  # noqa: E402


def test_jackknife_of_mean_is_sd_over_sqrt_n():
    x = np.array([0.3, -1.2, 2.5, 0.0, 4.1, -0.7])
    assert math.isclose(X.jackknife_se(x, np.mean), x.std(ddof=1) / math.sqrt(len(x)), rel_tol=1e-12)


def test_jackknife_of_variance_matches_the_deletion_identity():
    # s2_(-i) = ((n-1) s2 - n/(n-1) (x_i - xbar)^2) / (n-2)  (closed form, not the code path under test)
    x = np.array([1.0, 4.0, -2.0, 0.5, 3.5, 7.0, -1.0])
    n, s2, xb = len(x), x.var(ddof=1), x.mean()
    loo = np.array([((n - 1) * s2 - n / (n - 1) * (xi - xb) ** 2) / (n - 2) for xi in x])
    want = math.sqrt((n - 1) / n * np.sum((loo - loo.mean()) ** 2))
    assert math.isclose(X.jackknife_se(x, lambda y: y.var(ddof=1)), want, rel_tol=1e-12)


def test_diagnose_and_top_contributions_on_hand_values():
    z = 1.959963984540054
    e = np.array([-3.0, 0.0, 1.0, 2.5, 0.5])
    v = np.ones(5)
    d = X.diagnose(e, v, 1.0, z)
    assert d['mse'] == np.mean(e ** 2) and d['centered_variance'] == e.var(ddof=1) and d['mse'] != d['centered_variance']
    assert d['wald_lower_miss']['count'] == 1 and d['wald_upper_miss']['count'] == 1 and d['wald_covered'] == 3
    assert d['exact_variance_covered'] == 3
    assert X.skewness(np.array([-1.0, 0.0, 1.0])) == 0.0
    top = X.top_contributions(e, v, [10, 11, 12, 13, 14], k=2)
    assert [t['repetition'] for t in top] == [10, 13]
    assert math.isclose(top[0]['share_of_sum'], 9 / np.sum(e ** 2))


def test_committed_diagnosis_retains_all_ids_and_reproduces_coverage():
    out = json.loads(X.OUT_JSON.read_text())
    summ = json.loads((X.BASE / 'summary.json').read_text())
    assert out['source']['records'] == 2000 and out['all_ids_retained'] and out['source']['reps_sha256'] == summ['reps_sha256']
    pub = {(r['config'], r['policy']): r for r in summ['rows']}
    n = 0
    for row in out['rows']:
        for method in X.METHODS:
            for r in ('4', '16'):
                d = row['%s|r%s' % (method, r)]
                p = pub[(row['config'], row['policy'])][method][r]
                assert d['repetitions'] == 1000 and d['published_coverage_reproduced']
                assert (d['wald_covered'], d['exact_variance_covered']) == (p['wald_covered'], p['exact_variance_covered'])
                assert math.isclose(d['mse'], p['mse'], rel_tol=1e-9)
                n += 1
    assert n == 36 and len(out['focus_row']['largest_five_squared_errors']) == 6
