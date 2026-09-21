"""Checks for the retrospective conditional-moment diagnosis (lead 9f9e29d): jackknife identity, per-fit moments against
the previously reviewed exact-check path, hand-value comparison statistics, and the committed artifact's acceptance."""
import json, math, sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import conditional_moment_diagnosis as X  # noqa: E402
import honest_split_coverage as HC  # noqa: E402
import honest_split_dr as H  # noqa: E402
import repair_generator as G  # noqa: E402
import repair_logger as L  # noqa: E402
import sampler as S  # noqa: E402
import sensitivity_diagnosis as SD  # noqa: E402


def test_jackknife_deletion_identity_matches_direct_leave_one_out():
    x = np.array([0.4, -1.3, 2.2, 0.0, 5.1, -0.8, 1.7])
    assert math.isclose(X.jk_var_se(x), SD.jackknife_se(x, lambda y: y.var(ddof=1)), rel_tol=1e-12)


def test_job_refits_match_saved_hashes_and_moments_match_the_reviewed_exact_check_path():
    saved = {json.loads(l)['repetition']: json.loads(l) for l in HC.FINAL.read_text().splitlines() if X.CONFIG in l}
    c = X.spec()
    rec = X.job((7, {n: saved[7]['policies'][n]['q_fallback_table_sha256'] for n in c['policies']}))
    cell, logger = G.Cell(2, 'crossing', c['feedback']), L.LOGGERS[c['logger']]
    tr, ev, _, _ = H.cohorts()
    train = S.run_blocks(tr, cell, 4, S.SeededDraws(HC.ROOT_SEED), H.cohort_namespace(X.CONFIG, 7, 'train'), 'log',
                         logger=logger, logger_name=c['logger'])
    truths = json.loads(HC.MANIFEST.read_text())['truths']
    for name in c['policies']:
        q = rec['policies'][name]
        assert q['hash_match']
        nu = H.fit_frozen_q(train, {p.name: p for p in G.catalog(2)}[name], cell.K, tr, 4)
        mom, var_avg, _ = H.conditional_moments(cell, {p.name: p for p in G.catalog(2)}[name], logger, nu, ev, 4)
        assert math.isclose(q['exact_var'], var_avg, rel_tol=1e-12)
        assert abs(q['conditional_mean'] - truths['%s|%s' % (X.CONFIG, name)]['float']) < 1e-12
        for s, sn in ((0, 'easy'), (1, 'hard')):
            assert math.isclose(q['strata'][sn]['var'], mom[s]['variance'], rel_tol=1e-9)


def test_job_flags_a_hash_mismatch_and_does_not_use_that_fit():
    c = X.spec()
    rec = X.job((3, {n: '0' * 64 for n in c['policies']}))
    assert all(not q['hash_match'] and 'exact_var' not in q for q in rec['policies'].values())


def test_compare_on_hand_values():
    z = 1.959963984540054
    e = np.array([-3.0, 0.0, 1.0, 2.5, 0.5])
    s = X.compare(e, np.ones(5), np.full(5, 0.25), z)             # Wald half-width 1.96, exact-variance half-width 0.98
    assert s['wald_covered'] == 3 and s['exact_covered'] == 2
    assert s['wald_lower_miss']['count'] == 1 and s['exact_upper_miss']['count'] == 2
    assert math.isclose(s['paired_wald_minus_exact']['mean'], 1 / 5) and math.isclose(s['mean_estimated_over_exact_ratio'], 4.0)


def test_committed_artifact_meets_the_acceptance_criteria():
    a = json.loads((X.OUT / 'summary.json').read_text())
    assert a['table_hashes_checked'] == a['table_hashes_matched'] == 3000 and a['first_divergence'] is None
    assert a['completed_prefix'] == 1000 and not a['stopped_by_cap']
    assert a['manifest_weights']['easy'] == a['manifest_weights']['hard'] == 125 and a['manifest_weights']['replicates'] == 4
    assert 'RETROSPECTIVE' in a['kind'] and a['source_sha256']
    for r in a['rows']:
        assert r['conditional_means_exact'] and r['original_counts_reproduced'] and r['fits_used'] == 1000
