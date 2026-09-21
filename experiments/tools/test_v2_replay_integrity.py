"""Checks for the deterministic replay integrity script: detectors catch planted defects, the exact stratum expectations
agree with the frozen sensitivity table, and the committed replay artifact reports exact agreement."""
import json, math, sys
from fractions import Fraction as Fr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import fixed_task_blocks as B  # noqa: E402
import repair_generator as G  # noqa: E402
import replay_integrity as P  # noqa: E402
import replication_sensitivity as R  # noqa: E402
import sampler as S  # noqa: E402


def small_block():
    cell = G.Cell(2, 'crossing', 'weak')
    pol = {p.name: p for p in G.catalog(2)}['fixed_LS']
    tasks = [('t0000', 0), ('t0001', 1)]
    ns = S.stream_namespace(P.CONFIG, 3)
    return S.run_blocks(tasks, cell, 2, S.SeededDraws(R.ROOT_SEED), ns, 'fresh', policy=pol), ns, tasks


def test_stream_checks_pass_clean_and_catch_planted_defects():
    eps, ns, tasks = small_block()
    assert P.check_streams(eps, ns, 'fixed_LS', tasks, 2) == []
    assert P.check_streams(eps + [eps[0]], ns, 'fixed_LS', tasks, 2)                       # duplicate stream id
    assert P.check_streams(eps, ns, 'prompt_only_large_if_hard', tasks, 2)                 # wrong policy field
    assert P.check_streams(eps, S.stream_namespace(P.CONFIG, 4), 'fixed_LS', tasks, 2)    # wrong repetition namespace
    bad = [dict(e) for e in eps]; bad[1]['stratum'] = 1 - bad[1]['stratum']
    assert P.check_streams(bad, ns, 'fixed_LS', tasks, 2)                                  # stratum mismatch
    assert P.check_streams(eps[:-1], ns, 'fixed_LS', tasks, 2)                             # missing replicate


def test_utility_identity_detector():
    eps, _, _ = small_block()
    assert P.check_utility(eps) == 0
    bad = [dict(e) for e in eps]; bad[0]['utility'] += Fr(1, 100)
    assert P.check_utility(bad) == 1


def test_stratum_expectations_agree_with_frozen_r16_table():
    cell = G.Cell(2, 'crossing', 'weak')
    pol = {p.name: p for p in G.catalog(2)}['fixed_LS']
    ex = P.stratum_expectations(cell, pol)
    frozen = json.loads((R.OUT / 'manifest.json').read_text())['exact_table'][P.CONFIG + '|fixed_LS']
    assert (ex[0]['utility'] + ex[1]['utility']) / 2 == Fr(frozen['16']['exact']['truth'])
    assert (ex[0]['utility_var'] + ex[1]['utility_var']) / (2 * 16 * 250) == Fr(frozen['16']['exact']['fresh_var'])
    for s in (0, 1):
        assert ex[s]['utility'] == ex[s]['success'] - ex[s]['cost']


def test_committed_replay_reports_exact_agreement():
    out = json.loads((P.OUT / 'summary.json').read_text())
    assert out['repetitions'] == [0, 1, 933] and out['all_match'] and out['all_streams_ok']
    assert out['utility_identity_violations'] == 0 and out['sensitivity_sources_unchanged_since_freeze']
    committed = {json.loads(x)['repetition']: json.loads(x)['policies']['fixed_LS']
                 for x in (R.OUT / 'reps.jsonl').read_text().splitlines() if json.loads(x)['config'] == P.CONFIG}
    for r in out['replays']:
        assert r['episodes'] == r['unique_task_replicate_keys'] == r['unique_stream_ids'] == 4000
        assert all(c['abs_diff'] <= 1e-12 for c in r['comparisons']) and len(r['comparisons']) == 4
        assert r['comparisons'][0]['committed'] == committed[r['repetition']]['16']['fresh']
        assert math.isclose(r['task_contributions']['sum'], r['error_r16'], abs_tol=1e-12)
