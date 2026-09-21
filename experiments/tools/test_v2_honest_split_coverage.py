"""Pre-freeze checks for the repeated-training honest-split DR coverage batch (lead 3f4dfc2): declared design, per-repetition
refit, paired IPW on the same evaluation records, disjoint cohorts, recorded failures, the memo, statistics, and the
lock/finalize/analysis path including an incomplete (capped) output."""
import json, math, sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import dev_batch as D  # noqa: E402
import honest_split_coverage as HC  # noqa: E402
import honest_split_dr as H  # noqa: E402
import repair_generator as G  # noqa: E402
import repair_logger as L  # noqa: E402
import sampler as S  # noqa: E402
import writer_lock as W  # noqa: E402

CAT = {p.name: p for p in G.catalog(2)}


def test_declared_design():
    cs = HC.cells()
    assert HC.ROOT_SEED == 2026092104 and HC.R_REPS == 1000 and HC.WORKERS == 4 and HC.CAP_S == 900
    assert HC.Z == 1.959963984540054 and len(cs) == 4 and all(c['config'].startswith('hsc-') for c in cs)
    assert [c['policies'] for c in cs] == [c['policies'] for c in D.cells()]
    assert len(HC.truths()) == 12


def regenerate(c, b):
    cell = G.Cell(2, 'crossing', c['feedback'])
    tr, ev, _, _ = H.cohorts()
    d = S.SeededDraws(HC.ROOT_SEED)
    lg = dict(logger=L.LOGGERS[c['logger']], logger_name=c['logger'])
    train = S.run_blocks(tr, cell, 4, d, H.cohort_namespace(c['config'], b, 'train'), 'log', **lg)
    evalu = S.run_blocks(ev, cell, 4, d, H.cohort_namespace(c['config'], b, 'eval'), 'log', **lg)
    return cell, tr, ev, train, evalu, d


def test_job_matches_independent_regeneration_with_paired_ipw_and_disjoint_cohorts():
    c = HC.cells()[1]
    rec = HC.job((c, 3))
    cell, tr, ev, train, evalu, d = regenerate(c, 3)
    streams = {'train': {e['stream'] for e in train}, 'eval': {e['stream'] for e in evalu}}
    assert not streams['train'] & streams['eval'] and not {e['task_id'] for e in train} & {e['task_id'] for e in evalu}
    assert rec['training'] == H.training_cost(train)
    for name in c['policies']:
        pol = CAT[name]
        fresh = S.run_blocks(ev, cell, 4, d, H.cohort_namespace(c['config'], 3, 'fresh'), 'fresh', policy=pol)
        assert not {e['stream'] for e in fresh} & (streams['train'] | streams['eval'])
        nu = H.fit_frozen_q(train, pol, cell.K, tr, 4)
        dr = H.dr_estimate_and_variance(evalu, pol, cell.K, nu, ev, 4)
        p = rec['policies'][name]
        assert p['error'] is None and p['q_fallback_table_sha256'] == nu.sha256
        assert p['dr'] == dr['estimate'] and p['dr_var'] == dr['variance'] and p['or_plugin'] == dr['or_plugin']
        # paired comparator: trajectory IPW on the SAME evaluation records, no extra episodes
        assert p['ipw'] == float(S.ipw_estimate(evalu, pol, ev, 4))
        assert p['ipw_var'] == float(S.within_block_variance(evalu, lambda e: S.ipw_weight(e, pol) * e['utility'], ev, 4))
        assert p['fresh'] == float(S.fresh_estimate(fresh, ev, 4))


def test_q_is_refitted_per_repetition_and_memo_is_identical():
    c = HC.cells()[3]
    a, b = HC.job((c, 0)), HC.job((c, 1))
    assert all(a['policies'][n]['q_fallback_table_sha256'] != b['policies'][n]['q_fallback_table_sha256'] for n in c['policies'])
    x, y = HC.job((c, 0)), HC.job((c, 0), memoize=False)
    for r in (a, x, y):
        r.pop('cpu_seconds')
    assert a == x == y
    assert S.validate_manifest is HC.R.ValidateOncePerBlock().real


def test_policy_block_records_failures_instead_of_raising():
    c = HC.cells()[0]
    cell, tr, ev, train, evalu, d = regenerate(c, 0)
    pol = CAT[c['policies'][0]]
    fresh = S.run_blocks(ev, cell, 4, d, H.cohort_namespace(c['config'], 0, 'fresh'), 'fresh', policy=pol)
    p = HC.policy_block(evalu, fresh, train[:-1], pol, cell.K, tr, ev)        # incomplete training manifest
    assert p['error'] and 'ManifestError' in p['error'] and 'dr' not in p


def test_estimand_stats_on_hand_values():
    z = HC.Z
    est = [-3 * z, 0.0, 2 * z, 0.5, None]
    var = [1.0, 1.0, 1.0, 4.0, 1.0]
    s = HC.estimand_stats(est, var, 0.0, requested=10)
    assert s['wald_covered'] == 2 and s['failed_intervals'] == 1 and s['completed'] == 5
    assert s['lower_tail_miss'] == 1 / 5 and s['upper_tail_miss'] == 1 / 5
    assert math.isclose(s['rmse'], math.sqrt(sum(e * e for e in est[:4]) / 4))
    assert not any(k.startswith('exact_variance') or 'over_exact' in k for k in s)   # no fixed-Q exact variance across refits
    d, v, t = HC.series([dict(dr=1.0, fresh=0.25, dr_var=0.5, fresh_var=0.25)], 'dr_minus_fresh', 9.0)
    assert (d, v, t) == ([0.75], [0.75], 0.0)


def _small(tmp_path, monkeypatch, reps, cells):
    for attr, p in (('OUT', tmp_path / 'out'), ('WORK', tmp_path / 'work')):
        monkeypatch.setattr(HC, attr, p)
    monkeypatch.setattr(HC, 'MANIFEST', tmp_path / 'out' / 'manifest.json')
    monkeypatch.setattr(HC, 'PART', tmp_path / 'work' / 'reps.part.jsonl')
    monkeypatch.setattr(HC, 'FINAL', tmp_path / 'out' / 'reps.jsonl')
    monkeypatch.setattr(W, 'LOCKS', tmp_path / 'locks')
    (tmp_path / 'out').mkdir()
    m = dict(kind='test', repetitions_per_cell=reps, cells=cells, workers=2, total_wall_budget_seconds=600, truths=HC.truths(),
             not_claimed=['test'], source_sha256={rel: D.sha(rel) for rel in HC.HASHED})
    HC.MANIFEST.write_text(json.dumps(m))


def test_small_run_finalizes_analyzes_and_labels_incomplete_output(tmp_path, monkeypatch):
    cells = HC.cells()[2:]
    _small(tmp_path, monkeypatch, 3, cells)
    with W.WriterLock(HC.NAME):
        with pytest.raises(W.LockHeld):
            HC.run()
    HC.run()
    st = json.loads((HC.OUT / 'run_status.json').read_text())
    assert st['persisted'] == dict(records=6, unique=6, missing=0, expected=6) and st['complete'] and W.held() == []
    HC.analyze()
    s = json.loads((HC.OUT / 'summary.json').read_text())
    assert s['completed'] == s['requested'] == 6 and s['completion_fraction'] == 1.0 and len(s['rows']) == 6
    row = s['rows'][0]
    assert set(HC.ESTIMANDS) <= set(row) and row['dr']['completed'] == 3 and row['nuisance']['distinct_q_fallback_tables'] == 3
    # an incomplete (capped) output keeps the requested denominator and is labelled INCOMPLETE
    lines = HC.FINAL.read_text().splitlines()
    HC.FINAL.write_text('\n'.join(lines[:-1]) + '\n')
    HC.analyze()
    s = json.loads((HC.OUT / 'summary.json').read_text())
    assert s['completed'] == 5 and s['requested'] == 6 and s['completion_fraction'] < 1
    assert 'INCOMPLETE' in (HC.OUT / 'summary.md').read_text()
    short = next(r for r in s['rows'] if r['completed'] == 2)
    assert short['dr']['wald_coverage_over_requested'] == short['dr']['wald_covered'] / 3
