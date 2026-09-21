"""Checks for the additive conditional-moment correction (lead 20e186a / bc8f057): paired delete-one jackknife against
direct deletion, discrepancy-specific moments, and the published immutable per-fit records."""
import hashlib, json, math, sys
from fractions import Fraction as Fr
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import conditional_moment_correction as K  # noqa: E402
import conditional_moment_diagnosis as X  # noqa: E402
import coverage_batch as C  # noqa: E402
import honest_split_dr as H  # noqa: E402
import repair_generator as G  # noqa: E402


def direct(e, vx):
    n = len(e)
    d = np.array([np.delete(e, i).var(ddof=1) - np.delete(vx, i).mean() for i in range(n)])
    r = np.array([np.delete(e, i).var(ddof=1) / np.delete(vx, i).mean() for i in range(n)])
    se = lambda t: math.sqrt((n - 1) / n * np.sum((t - t.mean()) ** 2))
    return se(d), se(r)


def test_paired_jackknife_matches_direct_deletion_of_both_functionals():
    e = np.array([0.3, -1.1, 2.4, 0.0, -0.6, 1.9, 0.8])
    vx = np.array([1.0, 1.4, 0.7, 1.1, 0.9, 1.6, 1.2])
    j = K.paired_jackknife(e, vx)
    sd, sr = direct(e, vx)
    assert math.isclose(j['difference_jackknife_se'], sd, rel_tol=1e-12) and math.isclose(j['ratio_jackknife_se'], sr, rel_tol=1e-12)
    assert math.isclose(j['difference'], e.var(ddof=1) - vx.mean()) and math.isclose(j['ratio'], e.var(ddof=1) / vx.mean())
    # with a constant exact variance the paired SE of the difference reduces to the SE of the empirical variance alone
    jc = K.paired_jackknife(e, np.full(7, 1.2))
    assert math.isclose(jc['difference_jackknife_se'], jc['empirical_variance_alone_jackknife_se'], rel_tol=1e-12)
    assert jc['mean_exact_variance_jackknife_se'] < 1e-12


def test_fresh_moments_equal_the_accepted_fresh_table():
    cell = G.Cell(2, 'crossing', 'informative')
    _, ev, _, _ = H.cohorts()
    for pol in (p for p in G.catalog(2) if p.name in X.spec()['policies']):
        st, v, k3 = K.fresh_moments(cell, pol, ev, 4)
        want = Fr(C.exact_table()[('cov-K2-crossing-informative-feedback_dependent_floor_0.2', pol.name)]['exact']['fresh_var'])
        assert v == want and isinstance(k3, Fr)


def test_published_per_fit_records_and_discrepancy_moments():
    art = json.loads(K.OUT_JSON.read_text())
    raw = K.RECORDS.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == art['per_fit_records']['sha256']
    recs = [json.loads(x) for x in raw.decode().splitlines()]
    assert [r['repetition'] for r in recs] == list(range(1000))
    assert all(q['hash_match'] for r in recs for q in r['policies'].values())
    hist = json.loads((X.OUT / 'summary.json').read_text())
    for row in art['rows']:
        vx = np.array([r['policies'][row['policy']]['exact_var'] for r in recs])
        k3 = np.array([r['policies'][row['policy']]['exact_k3'] for r in recs])
        h = next(x for x in hist['rows'] if x['policy'] == row['policy'])
        assert math.isclose(vx.mean(), h['dr']['mean_exact_variance'], rel_tol=1e-12)
        f = row['dr_minus_fresh']['fresh_exact']
        vd, k3d = vx + f['variance'], k3 - f['k3']
        assert math.isclose(row['dr_minus_fresh']['skewness_of_discrepancy']['mean'], float(np.mean(k3d / vd ** 1.5)), rel_tol=1e-12)
        assert math.isclose(row['dr_minus_fresh']['variance_cv_across_fits'], float(vd.std(ddof=1) / vd.mean()), rel_tol=1e-12)
