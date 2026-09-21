"""Prerequisite checks for the fixed-score coverage batch (lead f0b4fa2): exact reference variances re-derived by an
independent route (exhaustive branch enumeration of one episode, not the stored tables), the independent-reference sum,
interval/failure rules, and the writer lock / atomic-finalize completion check."""
import json, math, sys
from fractions import Fraction as Fr
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import coverage_batch as C  # noqa: E402
import dev_batch as D  # noqa: E402
import repair_generator as G  # noqa: E402
import repair_logger as L  # noqa: E402
import sampler as S  # noqa: E402
import writer_lock as W  # noqa: E402


def moments(pairs):
    m1 = sum(p * x for p, x in pairs)
    return m1, sum(p * x * x for p, x in pairs) - m1 * m1


@pytest.fixture(scope='module')
def table():
    return C.exact_table()


def test_twelve_rows_and_new_namespace(table):
    assert len(table) == 12 and len(C.cells()) == 4
    assert all(c['config'].startswith('cov-') for c in C.cells())
    assert C.ROOT_SEED != D.ROOT_SEED and C.R_REPS == 2000 and C.WORKERS == 4 and C.CAP_S == 900
    assert C.Z == 1.959963984540054


def test_ipw_reference_variance_equals_enumerated_per_episode_variance(table):
    # Var(V_hat) for the balanced n = 250 list with r = 4 independent episodes per task is n^-2 sum_g sigma^2(S_g) / r
    # = (sigma_easy^2 + sigma_hard^2) / (2 r n); sigma^2 enumerated here from the sampler's own branches.
    for c in C.cells():
        cell = G.Cell(2, 'crossing', c['feedback'])
        br = {s: list(S.exhaustive(lambda d, s=s: S.run_episode(cell, s, d, 'x', logger=L.LOGGERS[c['logger']]))) for s in (0, 1)}
        cat = {p.name: p for p in G.catalog(2)}
        for name in c['policies']:
            mv = [moments([(p, S.ipw_weight(e, cat[name]) * e['utility']) for p, e in br[s]]) for s in (0, 1)]
            ex = table[(c['config'], name)]['exact']
            assert (mv[0][1] + mv[1][1]) / (2 * D.R_LOG * D.N_TASKS) == Fr(ex['ipw_var']), (c['config'], name)
            assert (mv[0][0] + mv[1][0]) / 2 == Fr(ex['truth']), (c['config'], name)   # IPW exactly unbiased on the list


def test_fresh_reference_variance_and_independent_sum(table):
    fref = json.loads((D.HERE / 'fresh_reference_v1.json').read_text())
    for c in C.cells():
        cell = G.Cell(2, 'crossing', c['feedback'])
        cat = {p.name: p for p in G.catalog(2)}
        for name in c['policies']:
            mv = [moments([(p, e['utility']) for p, e in S.exhaustive(lambda d, s=s: S.run_episode(cell, s, d, 'x', policy=cat[name]))])
                  for s in (0, 1)]
            ex = table[(c['config'], name)]['exact']
            assert (mv[0][1] + mv[1][1]) / (2 * D.R_FRESH * D.N_TASKS) == Fr(ex['fresh_var'])
            assert (mv[0][0] + mv[1][0]) / 2 == Fr(ex['truth'])
            assert Fr(ex['d_var']) == Fr(ex['ipw_var']) + Fr(ex['fresh_var'])
            row = next(x for x in fref['rows'] if (x['K'], x['action_effect'], x['feedback'], x['policy']) == (2, 'crossing', c['feedback'], name))
            # the accepted reference's own sqrt(Var_IPW + Var_fresh) and fresh SE (computed there independently)
            assert math.isclose(math.sqrt(float(Fr(ex['d_var']))), row['n250']['calibration_discrepancy_se_' + c['logger']], rel_tol=1e-12)
            assert math.isclose(math.sqrt(float(Fr(ex['fresh_var']))), row['n250']['fresh_se'], rel_tol=1e-12)


def test_job_is_deterministic_and_complete():
    c = C.cells()[1]
    a, b = C.job((c, 7)), C.job((c, 7))
    a.pop('cpu_seconds'); b.pop('cpu_seconds')
    assert a == b and a['namespace'] == 'cfg=%s|rep=7' % c['config']
    for name in c['policies']:
        p = a['policies'][name]
        assert p['error'] is None
        assert all(math.isfinite(p[k]) for k in ('ipw', 'ipw_var', 'fresh', 'fresh_var')) and p['ipw_var'] > 0 < p['fresh_var']
    assert C.job((c, 8))['policies'] != a['policies']


def test_interval_rules_failures_zero_variance_and_coverage():
    # target 0, z*sqrt(1) = 1.96: covered / not covered / None var / nan est / negative var / zero var exact / zero var off
    est = [1.0, 3.0, 0.0, float('nan'), 0.0, 0.0, 0.5]
    var = [1.0, 1.0, None, 1.0, -1.0, 0.0, 0.0]
    s = C.interval_stats(est, var, 0.0, 1.0, requested=10)
    assert s['wald_covered'] == 2                        # 1.0 and the exact zero-variance point interval
    assert s['failed_intervals'] == 3 and s['zero_variance_point_intervals'] == 2
    assert s['wald_coverage'] == 2 / 7 and s['wald_coverage_over_requested'] == 2 / 10
    assert s['finite_estimates'] == 6
    assert s['exact_variance_covered'] == 5              # nan estimate cannot cover; 3.0 is outside 1.96
    assert C.diff(1.0, None) is None and C.vsum(float('inf'), 1.0) is None


def test_wilson_reference_values():
    lo, hi = C.wilson(95, 100)                           # Wilson score interval for 95/100 at 95%: (0.8882, 0.9785)
    assert abs(lo - 0.8882) < 1e-4 and abs(hi - 0.9785) < 1e-4
    lo, hi = C.wilson(0, 50)
    assert lo == 0 or abs(lo) < 1e-15
    assert hi < 0.08


def test_writer_lock_is_exclusive_and_released(tmp_path, monkeypatch):
    monkeypatch.setattr(W, 'LOCKS', tmp_path / 'locks')
    with W.WriterLock('x'):
        assert W.held() == ['x.lock']
        with pytest.raises(W.LockHeld):
            W.WriterLock('x').__enter__()
    assert W.held() == []
    with pytest.raises(RuntimeError):
        with W.WriterLock('y'):
            raise RuntimeError('boom')
    assert W.held() == []


def test_finalize_refuses_duplicates_and_unexpected_and_reports_missing(tmp_path):
    part, final = tmp_path / 'p.jsonl', tmp_path / 'out' / 'f.jsonl'
    key = lambda r: (r['c'], r['b'])
    exp = [('a', 0), ('a', 1), ('a', 2)]
    part.write_text('{"c": "a", "b": 1}\n{"c": "a", "b": 0}\n')
    assert W.finalize(part, final, exp, key) == dict(records=2, unique=2, missing=1, expected=3)
    assert [key(json.loads(x)) for x in final.read_text().splitlines()] == [('a', 0), ('a', 1)]
    assert not Path(str(final) + '.tmp').exists()
    part.write_text('{"c": "a", "b": 1}\n{"c": "a", "b": 1}\n')
    with pytest.raises(ValueError):
        W.finalize(part, final, exp, key)
    part.write_text('{"c": "a", "b": 9}\n')
    with pytest.raises(ValueError):
        W.finalize(part, final, exp, key)
    assert len(final.read_text().splitlines()) == 2      # a refused finalize leaves the previous output untouched


def _small_manifest(tmp_path, monkeypatch, reps):
    for attr, p in (('OUT', tmp_path / 'out'), ('WORK', tmp_path / 'work')):
        monkeypatch.setattr(C, attr, p)
    monkeypatch.setattr(C, 'MANIFEST', tmp_path / 'out' / 'manifest.json')
    monkeypatch.setattr(C, 'PART', tmp_path / 'work' / 'reps.part.jsonl')
    monkeypatch.setattr(C, 'FINAL', tmp_path / 'out' / 'reps.jsonl')
    monkeypatch.setattr(W, 'LOCKS', tmp_path / 'locks')
    (tmp_path / 'out').mkdir()
    m = dict(repetitions_per_cell=reps, cells=[C.cells()[0]], workers=2, cpu_wall_cap_seconds=600,
             source_sha256={rel: D.sha(rel) for rel in C.HASHED})
    C.MANIFEST.write_text(json.dumps(m))


def test_run_writes_under_work_finalizes_exact_ids_and_releases_lock(tmp_path, monkeypatch):
    _small_manifest(tmp_path, monkeypatch, 2)
    C.run()
    st = json.loads((C.OUT / 'run_status.json').read_text())
    assert st['persisted'] == dict(records=2, unique=2, missing=0, expected=2) and not st['stopped_by_cap']
    ids = [(r['config'], r['repetition']) for r in map(json.loads, C.FINAL.read_text().splitlines())]
    assert ids == [(C.cells()[0]['config'], 0), (C.cells()[0]['config'], 1)]
    assert W.held() == []
    C.run()                                              # resume: nothing to do, same two records, no duplicates
    assert len(C.FINAL.read_text().splitlines()) == 2


def test_run_refuses_while_lock_held_or_sources_changed(tmp_path, monkeypatch):
    _small_manifest(tmp_path, monkeypatch, 1)
    with W.WriterLock(C.NAME):
        with pytest.raises(W.LockHeld):
            C.run()
    assert not C.PART.exists()
    m = json.loads(C.MANIFEST.read_text()); m['source_sha256'][C.HASHED[0]] = '0' * 64
    C.MANIFEST.write_text(json.dumps(m))
    with pytest.raises(SystemExit):
        C.run()
