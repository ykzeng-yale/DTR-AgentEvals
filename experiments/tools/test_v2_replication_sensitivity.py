"""Pre-launch checks for the replication-sensitivity batch (lead 9550aa4): r=16 exact-variance scaling re-derived by
exhaustive enumeration, nesting of the first-4 block, the first-4 analysis reproduced from an independently generated
r=4 block, the runtime validation memo, the new tail/correlation/paired statistics, and the lock/finalize run path."""
import json, math, sys
from fractions import Fraction as Fr
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import dev_batch as D  # noqa: E402
import fixed_task_blocks as B  # noqa: E402
import repair_generator as G  # noqa: E402
import repair_logger as L  # noqa: E402
import replication_sensitivity as R  # noqa: E402
import sampler as S  # noqa: E402
import writer_lock as W  # noqa: E402


def var_of(pairs):
    m1 = sum(p * x for p, x in pairs)
    return sum(p * x * x for p, x in pairs) - m1 * m1


def test_design_constants():
    cs = R.cells()
    assert [c['feedback'] for c in cs] == ['informative', 'weak']
    assert all(c['logger'] == 'feedback_dependent_floor_0.2' and c['config'].startswith('rs-') for c in cs)
    assert R.ROOT_SEED == 2026092103 and R.R_REPS == 1000 and (R.R_SMALL, R.R_BIG) == (4, 16)
    assert R.WORKERS == 4 and R.CAP_S == 900


def test_r16_exact_variance_is_r4_over_four_by_enumeration():
    table = R.exact_table()
    frozen = json.loads((D.ROOT / 'results/v2_sim/coverage_fixed_score_20260921/manifest.json').read_text())['exact_table']
    cat = {p.name: p for p in G.catalog(2)}
    for c in R.cells():
        cell = G.Cell(2, 'crossing', c['feedback'])
        logs = {s: list(S.exhaustive(lambda d, s=s: S.run_episode(cell, s, d, 'x', logger=L.LOGGERS[c['logger']]))) for s in (0, 1)}
        for name in c['policies']:
            iv = [var_of([(p, S.ipw_weight(e, cat[name]) * e['utility']) for p, e in logs[s]]) for s in (0, 1)]
            fv = [var_of([(p, e['utility']) for p, e in S.exhaustive(lambda d, s=s: S.run_episode(cell, s, d, 'x', policy=cat[name]))])
                  for s in (0, 1)]
            t = table[(c['config'], name)]
            for r in (4, 16):
                assert Fr(t[str(r)]['exact']['ipw_var']) == (iv[0] + iv[1]) / (2 * r * D.N_TASKS)
                assert Fr(t[str(r)]['exact']['fresh_var']) == (fv[0] + fv[1]) / (2 * r * D.N_TASKS)
            assert Fr(t['16']['exact']['d_var']) * 4 == Fr(t['4']['exact']['d_var'])
            # the r=4 values are the ones frozen for the completed validation
            assert t['4']['exact']['ipw_var'] == frozen['cov-' + c['config'][3:] + '|' + name]['exact']['ipw_var']


def test_first4_block_is_nested_in_the_16_block():
    c = R.cells()[1]
    cell = G.Cell(2, 'crossing', c['feedback'])
    tasks, _ = B.task_list(D.N_TASKS)
    ns = S.stream_namespace(c['config'], 11)
    pol = {p.name: p for p in G.catalog(2)}['fixed_LS']
    for kw in (dict(role='log', logger=L.LOGGERS[c['logger']], logger_name=c['logger']), dict(role='fresh', policy=pol)):
        role = kw.pop('role')
        b16 = S.run_blocks(tasks, cell, 16, S.SeededDraws(R.ROOT_SEED), ns, role, **kw)
        b4 = S.run_blocks(tasks, cell, 4, S.SeededDraws(R.ROOT_SEED), ns, role, **kw)
        assert [e for e in b16 if e['replicate'] < 4] == b4


def test_first4_analysis_reproduced_from_an_independently_generated_r4_block():
    c = R.cells()[0]
    rec = R.job((c, 5))
    cell = G.Cell(2, 'crossing', c['feedback'])
    tasks, _ = B.task_list(D.N_TASKS)
    ns = S.stream_namespace(c['config'], 5)
    log4 = S.run_blocks(tasks, cell, 4, S.SeededDraws(R.ROOT_SEED), ns, 'log', logger=L.LOGGERS[c['logger']], logger_name=c['logger'])
    for name, pol in ((n, p) for p in G.catalog(2) for n in c['policies'] if p.name == n):
        fr4 = S.run_blocks(tasks, cell, 4, S.SeededDraws(R.ROOT_SEED), ns, 'fresh', policy=pol)
        got = rec['policies'][name]['4']
        assert got['ipw'] == float(S.ipw_estimate(log4, pol, tasks, 4))
        assert got['fresh'] == float(S.fresh_estimate(fr4, tasks, 4))
        assert got['ipw_var'] == float(S.within_block_variance(log4, lambda e: S.ipw_weight(e, pol) * e['utility'], tasks, 4))
        assert got['fresh_var'] == float(S.within_block_variance(fr4, lambda e: e['utility'], tasks, 4))
        assert got['error'] is None and rec['policies'][name]['16']['error'] is None


def test_validation_memo_is_identical_restored_and_still_rejects_bad_blocks():
    c = R.cells()[1]
    a, b = R.job((c, 2)), R.job((c, 2), memoize=False)
    a.pop('cpu_seconds'); b.pop('cpu_seconds')
    assert a == b
    real = S.validate_manifest
    with R.ValidateOncePerBlock():
        eps = [dict(task_id='a', stratum=0, replicate=0, utility=Fr(1), decisions=[], observations=[])]
        with pytest.raises(S.ManifestError):
            S.fresh_estimate(eps, [('a', 0)], 2)                 # missing replicate still raises
        with pytest.raises(S.ManifestError):
            S.fresh_estimate(eps + eps, [('a', 0)], 1)           # duplicate still raises
    assert S.validate_manifest is real


def test_shape_and_paired_statistics_on_hand_values():
    z = R.Z
    est = [-3 * z, 0.0, 2 * z, 0.5, float('nan')]              # target 0, variance 1 except the last
    var = [1.0, 1.0, 1.0, 4.0, 1.0]
    s = R.shape_stats(est, var, 0.0)
    assert s['lower_tail_miss'] == 1 / 5 and s['upper_tail_miss'] == 1 / 5
    er = [-3 * z, 0.0, 2 * z, 0.5]; vv = [1.0, 1.0, 1.0, 4.0]
    me, mv = sum(er) / 4, sum(vv) / 4
    cov = sum((x - me) * (y - mv) for x, y in zip(er, vv)) / 3
    sx = math.sqrt(sum((x - me) ** 2 for x in er) / 3); sy = math.sqrt(sum((y - mv) ** 2 for y in vv) / 3)
    assert math.isclose(s['error_variance_correlation'], cov / (sx * sy)) and math.isclose(s['variance_cv'], sy / mv)
    p = R.paired([1, 1, 0, 1], [1, 0, 1, 0])
    assert p['mean'] == 0.25 and p['discordant_gain'] == 2 and p['discordant_loss'] == 1
    # differences [0, 1, -1, 1], mean 1/4: squared deviations 1/16 + 9/16 + 25/16 + 9/16 = 11/4
    assert math.isclose(p['mcse'], math.sqrt((11 / 4) / 3) / 2)
    assert R.covered(float('nan'), 1.0, 0.0) == 0 and R.covered(0.1, None, 0.0) == 0 and R.covered(0.1, None, 0.0, 1.0) == 1


def test_small_run_finalizes_exact_ids_and_analyzes(tmp_path, monkeypatch):
    for attr, p in (('OUT', tmp_path / 'out'), ('WORK', tmp_path / 'work')):
        monkeypatch.setattr(R, attr, p)
    monkeypatch.setattr(R, 'MANIFEST', tmp_path / 'out' / 'manifest.json')
    monkeypatch.setattr(R, 'PART', tmp_path / 'work' / 'reps.part.jsonl')
    monkeypatch.setattr(R, 'FINAL', tmp_path / 'out' / 'reps.jsonl')
    monkeypatch.setattr(W, 'LOCKS', tmp_path / 'locks')
    (tmp_path / 'out').mkdir()
    m = dict(kind='test', repetitions_per_cell=3, cells=[R.cells()[0]], workers=2, cpu_wall_cap_seconds=600,
             exact_table={'%s|%s' % k: v for k, v in R.exact_table().items()}, source_sha256={rel: D.sha(rel) for rel in R.HASHED})
    R.MANIFEST.write_text(json.dumps(m))
    with W.WriterLock(R.NAME):
        with pytest.raises(W.LockHeld):
            R.run()
    R.run()
    st = json.loads((R.OUT / 'run_status.json').read_text())
    assert st['persisted'] == dict(records=3, unique=3, missing=0, expected=3) and W.held() == []
    R.analyze()
    s = json.loads((R.OUT / 'summary.json').read_text())
    assert s['completion_fraction'] == 1.0 and len(s['rows']) == 3
    row = s['rows'][0]
    assert set(row['ipw']) == {'4', '16', 'paired_r16_minus_r4'} and row['ipw']['4']['completed'] == 3
