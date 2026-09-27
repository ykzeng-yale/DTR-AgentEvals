"""Independent saved-study recount. No imports of worker code; no random draws.

Run from repository root: python3 docs/audits/req027_lead_recount.py
"""
import csv
import hashlib
import json
import math
import statistics as st
import subprocess
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'results/v2_sim/req027_primary_logger_mc_20260927'
errors = []


def check(actual, expected):
    error = abs(actual - expected)
    errors.append(error)
    assert error < 1e-12, (actual, expected)


hashes = json.loads((RUN / 'sha256.json').read_text())
for name, digest in hashes.items():
    assert hashlib.sha256((RUN / name).read_bytes()).hexdigest() == digest, name
review = json.loads((ROOT / 'docs/audits/primary_logger_remote_20260927/check_receipt.json').read_text())
for source in review['sources']:
    content = subprocess.check_output(['git', 'show', review['task']['commit'] + ':' + source['path']], cwd=ROOT)
    assert hashlib.sha256(content).hexdigest() == source['sha256']
rows = list(csv.DictReader((RUN / 'studies.csv').open()))
assert len(rows) == 4000
saved = json.loads((RUN / 'summary.json').read_text())
truth = json.loads((RUN / 'exact_truths.json').read_text())
cells = {}
for cell in ('0', '1/5'):
    eta = F(cell)
    group = [r for r in rows if r['cell_eta'] == cell]
    n = len(group)
    assert sorted(int(r['study']) for r in group) == list(range(2000))
    target = float(eta / 2)
    check(target, saved[cell]['target'])
    # Closed-form moments from the frozen Bernoulli score law, independently
    # of the worker's finite enumeration and Monte Carlo implementation.
    task_means = [2 * eta * (p - F(1, 4)) for p in (F(1, 4), F(3, 4))]
    second = [F(1, 4) + p / 2 for p in (F(1, 4), F(3, 4))]
    estimates = {}
    for label, multiplier, width in (('fixed', 1, 4), ('half', 2, 8)):
        theoretical = sum(multiplier * m2 - mu**2 for m2, mu in zip(second, task_means)) / 320
        assert theoretical == F(truth[cell]['estimator_variance'][label])
        x = [float(r[label + '_estimate']) for r in group]
        v = [float(r[label + '_variance_estimate']) for r in group]
        assert all(math.isfinite(z) for z in x + v) and all(z > 0 for z in v)
        coverage = []
        lengths = []
        hc = []
        for row, estimate, variance in zip(group, x, v):
            covered = abs(estimate - target) <= 1.959963984540054 * math.sqrt(variance)
            length = 2 * 1.959963984540054 * math.sqrt(variance)
            hcovered = abs(estimate - target) <= width * math.sqrt(math.log(40) / 320)
            assert int(row[label + '_variance_failure']) == 0
            assert int(row[label + '_wald_cover']) == covered
            assert int(row[label + '_hoeffding_cover']) == hcovered
            check(length, float(row[label + '_wald_length']))
            coverage.append(covered); lengths.append(length); hc.append(hcovered)
        empirical = st.variance(x)
        cv = st.mean(coverage)
        actual = dict(bias=st.mean(x)-target, bias_mcse=math.sqrt(empirical/n),
                      empirical_variance=empirical, exact_predicted_variance=float(theoretical),
                      mean_estimated_variance=st.mean(v), estimated_variance_mean_mcse=st.stdev(v)/math.sqrt(n),
                      wald_coverage=cv, wald_coverage_mcse=math.sqrt(cv*(1-cv)/n),
                      mean_wald_length=st.mean(lengths), hoeffding_coverage=st.mean(hc),
                      hoeffding_width=2*width*math.sqrt(math.log(40)/320),
                      rmse=math.sqrt(st.mean((z-target)**2 for z in x)), zero_nonfinite_variance_failures=0)
        for key, value in actual.items(): check(value, saved[cell]['loggers'][label][key])
        estimates[label] = x
    # Independently derive deleted-observation variances from centered sums.
    x, y = estimates['fixed'], estimates['half']
    vx, vy = st.variance(x), st.variance(y)
    mx, my = st.mean(x), st.mean(y)
    deleted = [((n-1)*(vy-vx)-n/(n-1)*((b-my)**2-(a-mx)**2))/(n-2) for a,b in zip(x,y)]
    se = math.sqrt((n-1)/n * sum((z-st.mean(deleted))**2 for z in deleted))
    diff = vy-vx
    paired = saved[cell]['paired_variance_comparison']
    deltas = [b-a for a,b in zip(x,y)]
    for key,value in dict(half_minus_fixed=diff, paired_jackknife_mcse=se,
                          empirical_half_over_fixed=vy/vx, exact_half_minus_fixed=.003125,
                          paired_mean_difference=st.mean(deltas), paired_mean_difference_mcse=st.stdev(deltas)/math.sqrt(n)).items():
        check(value, paired[key])
    for actual,expected in zip((diff-1.959963984540054*se,diff+1.959963984540054*se),paired['descriptive_mc_95_interval']): check(actual,expected)
    cells[cell] = {'studies':n, 'variance_difference':diff, 'paired_jackknife_mcse':se}
resources = json.loads((RUN/'resource_observations.json').read_text())
assert len(resources)==40 and all(r['passed'] for r in resources)
print(json.dumps({'status':'PASS', 'sampling_performed':False, 'raw_studies':len(rows),
                  'checks':len(errors), 'max_absolute_numeric_error':max(errors),
                  'manifest_hashes_verified':len(hashes), 'review_source_pins_verified':7,
                  'cells':cells, 'limitations':['Saved study-level recount, not a replay of individual score draws.',
                  'Remote resource observations are reported records, not independently monitored host state.',
                  'macOS run used monitored RSS, not an OS-enforced memory ceiling.']},indent=2))
