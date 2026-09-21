"""Pre-execution acceptance for the fixed-fit conditional coverage study (lead 20e186a): frozen hashes and serialization
round trip, per-fit exact moments against the published per-fit records, no fitting during evaluation, distinct
fit/evalrep/role namespaces (and from training), failure retention, statistics, and the capped/incomplete path."""
import json, math, sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import conditional_moment_correction as K  # noqa: E402
import dev_batch as D  # noqa: E402
import fixed_fit_coverage as F  # noqa: E402
import honest_split_coverage as HC  # noqa: E402
import honest_split_dr as H  # noqa: E402
import repair_generator as G  # noqa: E402
import repair_logger as L  # noqa: E402
import sampler as S  # noqa: E402
import writer_lock as W  # noqa: E402

CAT = {p.name: p for p in G.catalog(2)}


def test_declared_design():
    assert F.ROOT_SEED == 2026092105 and F.FITS == (0, 1, 2, 3, 4) and F.EVALREPS == 2000
    assert F.WORKERS == 4 and F.CAP_S == 900 and F.Z == 1.959963984540054
    m = json.loads(F.MANIFEST.read_text())
    assert m['jobs'] == 10000 and m['order'] == 'evalrep outer, fit inner' and len(m['nuisances']['table_hashes']) == 15
    assert m['nuisances']['refit_during_study'] is False


def test_serialization_round_trip_matches_saved_hashes_and_rejects_tampering():
    saved = {r['repetition']: r for r in map(json.loads, HC.FINAL.read_text().splitlines()) if r['config'] == F.CELL_CONFIG}
    tables = json.loads(F.NUIS.read_text())['tables']
    for key, d in tables.items():
        f, name = key.split('|')
        nu = F.deserialize(d)
        assert nu.sha256 == saved[int(f)]['policies'][name]['q_fallback_table_sha256']
        assert all(isinstance(k, tuple) and isinstance(k[2], tuple) and isinstance(k[3], tuple) for q in nu.Q for k in q)
        assert F.deserialize(F.serialize(nu)).sha256 == nu.sha256
    bad = json.loads(json.dumps(tables['0|fixed_LS']))
    bad['fallback'][0]['0'] += 1e-9
    with pytest.raises(ValueError):
        F.deserialize(bad)


def test_manifest_exact_moments_equal_the_published_per_fit_records():
    m = json.loads(F.MANIFEST.read_text())
    recs = {r['repetition']: r for r in map(json.loads, K.RECORDS.read_text().splitlines())}
    for f in F.FITS:
        for name in m['cell']['policies']:
            ex, pr = m['exact']['%d|%s' % (f, name)], recs[f]['policies'][name]
            assert math.isclose(ex['dr_var'], pr['exact_var'], rel_tol=1e-12)
            assert abs(ex['conditional_dr_mean'] - ex['truth']) < 1e-12
            assert math.isclose(ex['dr_minus_fresh_var'], ex['dr_var'] + ex['fresh_var'], rel_tol=1e-15)


def test_job_never_fits_and_matches_the_frozen_nuisance_on_a_regenerated_block(monkeypatch):
    monkeypatch.setattr(H.EA, 'fit_q', lambda *a, **k: (_ for _ in ()).throw(AssertionError('fit_q called during evaluation')))
    rec = F.job((2, 5))
    c = F.spec()
    cell, logger = G.Cell(2, 'crossing', c['feedback']), L.LOGGERS[c['logger']]
    _, ev, _, _ = H.cohorts()
    d = S.SeededDraws(F.ROOT_SEED)
    evalu = S.run_blocks(ev, cell, 4, d, F.namespace(2, 5, 'eval'), 'log', logger=logger, logger_name=c['logger'])
    for name in c['policies']:
        nu = F.nuisances()['2|%s' % name]
        dr = H.dr_estimate_and_variance(evalu, CAT[name], cell.K, nu, ev, 4)
        p = rec['policies'][name]
        assert p['error'] is None and p['dr'] == dr['estimate'] and p['dr_var'] == dr['variance']
        assert p['ipw'] == float(S.ipw_estimate(evalu, CAT[name], ev, 4))


def test_namespaces_are_distinct_across_fits_evalreps_roles_and_training():
    c = F.spec()
    cell, logger = G.Cell(2, 'crossing', c['feedback']), L.LOGGERS[c['logger']]
    _, ev, _, _ = H.cohorts()
    tr = H.cohorts()[0]
    d = S.SeededDraws(F.ROOT_SEED)
    sets = {}
    for f, j in ((0, 0), (1, 0), (0, 1)):
        sets[(f, j, 'eval')] = {e['stream'] for e in S.run_blocks(ev[:4], cell, 4, d, F.namespace(f, j, 'eval'), 'log',
                                                                   logger=logger, logger_name=c['logger'])}
        sets[(f, j, 'fresh')] = {e['stream'] for e in S.run_blocks(ev[:4], cell, 4, d, F.namespace(f, j, 'fresh'), 'fresh',
                                                                    policy=CAT['fixed_LS'])}
    sets['train'] = {e['stream'] for e in S.run_blocks(tr[:4], cell, 4, d, H.cohort_namespace(F.CELL_CONFIG, 0, 'train'), 'log',
                                                       logger=logger, logger_name=c['logger'])}
    keys = list(sets)
    for i in range(len(keys)):
        for k in keys[i + 1:]:
            assert not sets[keys[i]] & sets[k], (keys[i], k)
    assert all(s.startswith('study=hsf|cfg=%s|fit=' % F.STUDY_CELL) for k, v in sets.items() if k != 'train' for s in v)
    with pytest.raises(ValueError):
        F.namespace(0, 0, 'train')


def test_policy_block_retains_failures():
    c = F.spec()
    cell, logger = G.Cell(2, 'crossing', c['feedback']), L.LOGGERS[c['logger']]
    _, ev, _, _ = H.cohorts()
    d = S.SeededDraws(F.ROOT_SEED)
    evalu = S.run_blocks(ev, cell, 4, d, F.namespace(0, 0, 'eval'), 'log', logger=logger, logger_name=c['logger'])
    fresh = S.run_blocks(ev, cell, 4, d, F.namespace(0, 0, 'fresh'), 'fresh', policy=CAT['fixed_LS'])
    p = F.policy_block(evalu[:-1], fresh, CAT['fixed_LS'], cell.K, ev, F.nuisances()['0|fixed_LS'])
    assert p['error'] and 'ManifestError' in p['error'] and 'dr' not in p


def test_stats_on_hand_values():
    z = F.Z
    est = [0.0, 2.5, -2.5, 0.5, None]
    s = F.stats(est, [1.0, 1.0, 1.0, 0.01, 1.0], 0.0, 1.0, requested=10)
    # Wald: 0 in, 2.5 out (upper), -2.5 out (lower), 0.5 out (upper, sd 0.1), None failed
    assert s['wald_coverage']['count'] == 1 and s['wald_upper_miss']['count'] == 2 and s['wald_lower_miss']['count'] == 1
    assert s['exact_coverage']['count'] == 2 and s['failed_intervals'] == 1 and s['wald_covered_over_requested'] == 0.1
    assert math.isclose(s['paired_wald_minus_exact']['mean'], -1 / 5)


def test_small_run_finalizes_and_labels_incomplete(tmp_path, monkeypatch):
    real = json.loads(F.MANIFEST.read_text())
    small = dict(real, fits=[0, 1], evaluation_repetitions=2, workers=2)
    for attr, p in (('OUT', tmp_path / 'out'), ('WORK', tmp_path / 'work')):
        monkeypatch.setattr(F, attr, p)
    monkeypatch.setattr(F, 'MANIFEST', tmp_path / 'out' / 'manifest.json')
    monkeypatch.setattr(F, 'PART', tmp_path / 'work' / 'reps.part.jsonl')
    monkeypatch.setattr(F, 'FINAL', tmp_path / 'out' / 'reps.jsonl')
    monkeypatch.setattr(W, 'LOCKS', tmp_path / 'locks')
    (tmp_path / 'out').mkdir()
    F.MANIFEST.write_text(json.dumps(small))
    F.run()
    st = json.loads((F.OUT / 'run_status.json').read_text())
    assert st['persisted'] == dict(records=4, unique=4, missing=0, expected=4) and st['complete'] and W.held() == []
    F.analyze()
    s = json.loads((F.OUT / 'summary.json').read_text())
    assert s['completed'] == s['requested'] == 4 and len(s['rows']) == 6
    lines = F.FINAL.read_text().splitlines()
    F.FINAL.write_text('\n'.join(lines[:-1]) + '\n')
    F.analyze()
    s = json.loads((F.OUT / 'summary.json').read_text())
    assert s['completed'] == 3 and s['requested'] == 4 and 'INCOMPLETE' in (F.OUT / 'summary.md').read_text()
    assert all(r['requested'] == 2 for r in s['rows'])
