"""DTR-REQ-018 fixtures: the source-bound design ledger (no model, no Monte Carlo). Expected values are hand-derived
(counts from the lead's audits and the verification of 26 Sep, exact fractions, and small synthetic designs), never
recomputed with the code under test.
"""
import csv
import hashlib
import io
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments/tools'))
import req018_design_ledger as L  # noqa: E402

OUT = ROOT / 'results/code_routing/analysis/req018'
CHECK = OUT / 'check_req018_ledger.py'
CSVS = ('prefix_ledger', 'task_ledger', 'continuation_ledger')


@pytest.fixture(scope='module')
def built():
    return L.build()


def test_reconciliation_counts_match_the_lead_audits(built):
    ledger, prefix_rows, task_rows, cont_rows = built
    r = ledger['reconciliation']
    assert (r['confirm_tasks'], r['confirm_log_episodes'], r['eligible_prefixes'], r['eligible_tasks']) == (330, 2640, 564, 152)
    assert (r['sampled_prefixes'], r['sampled_tasks'], r['branch_continuations']) == (200, 103, 800)
    assert (r['tasks_without_eligible_prefix'], r['tasks_with_eligible_but_no_sampled_prefix']) == (178, 49)
    assert r['episodes_per_task'] == [(8, 330)] and r['continuations_per_prefix'] == [(4, 200)]
    assert (len(prefix_rows), len(task_rows), len(cont_rows)) == (564, 330, 800)
    assert sum(int(x['sampled']) for x in prefix_rows) == 200
    assert sum(1 for t in task_rows if t['M_g'] == 0) == 178      # zero-contribution tasks are kept


def test_zero_arm_counts(built):
    z = built[0]['reconciliation']['zero_arm_counts']
    assert (z['eligible_tasks_D_g1_zero'], z['eligible_tasks_D_g0_zero'], z['eligible_tasks_both_zero'],
            z['eligible_tasks_both_positive']) == (64, 56, 20, 52)
    assert 64 + 56 - 20 + 52 == 152                                  # inclusion-exclusion over the 152 eligible tasks
    assert (z['sampled_tasks_both_positive'], z['sampled_tasks_at_least_one_zero']) == (42, 61)
    assert z['tasks_lead_derivative_exactly_zero'] == 186            # 178 ineligible + 8 eligible with zero terms


def test_point_estimates_are_the_original_pooled_values(built):
    p = built[0]['point_estimates']
    assert p['B'] == 24 / 200 == 0.12
    assert math.isclose(p['log_contrast'], 0.13465370743933003, abs_tol=1e-15)
    assert math.isclose(p['delta'], -0.014653707439330033, abs_tol=1e-15)
    assert p['lead_audit'] == {'B': 0.12, 'log_contrast': 0.13465370743933003, 'delta': -0.014653707439330033}
    assert abs(p['sum_lead_derivative']) < 1e-12


def test_target_is_the_lead_adopted_eq2_with_mu_F_secondary(built):
    t = built[0]['target']
    assert 'eq. (2)' in t['primary'] and 'sum_g E T_g / sum_g E M_g' in t['primary']
    assert 'not sampled from a superpopulation' in t['primary']
    assert 'E(B_hat | F) = mu_F' in t['secondary']['relation']
    assert 'does not make B_hat unbiased for theta' in t['secondary']['relation']
    assert any('theory_branch_fixed_benchmark_bound.md' in b for b in built[0]['builds_on'])
    assert any('theory_feedback_20260921_weighting.md' in b for b in built[0]['builds_on'])
    assert 'It is not an eq. (2) influence function' in built[0]['lead_derivative']['label']
    assert any('branch_evidence_table.json' in b for b in built[0]['builds_on'])


def test_stage1_a0_law_and_eligibility(built):
    s1 = built[0]['design']['stage1_source_blocks']
    assert s1['a0_same_probability'] == 3 / 7 and s1['a0_both_large_probability'] == 3 / 14   # C(4,2)*2/C(8,2), 6/28
    assert s1['a0_block_patterns'] == [[[0, 0, 0, 0, 1, 1, 1, 1], 330]]
    assert s1['a0_realized_equals_block'] == 2640
    assert s1['u0_by_block'] == [[[0, 0.75], 1320], [[1, 0.25], 1320]]
    assert (s1['decisions_checked_all_t'], s1['decisions_checked_t_ge_1'], s1['decisions_mismatching_design_uniform']) \
        == (3662, 564 + 458, 0)                           # t = 1 in all 564 eligible episodes, t = 2 in 458 of them
    el = s1['eligibility']
    assert el['eligible_vs_first_visible_pass'] == [[[False, True], 2076], [[True, False], 564]]
    assert el['eligible_with_hidden_correct_first_candidate'] == 69
    assert el['frame_by_a0'] == {'small': 332, 'large': 232} and el['sample_by_a0'] == {'small': 111, 'large': 89}
    assert el['max_M_g_by_a0'] == 4
    sc = s1['schedule']
    assert sc['log_invocations'] == [[['8d491c364a78', 'confirm', L.LOG_COMMIT, s1['design_code_sha256']], 2640],
                                     [['8d491c364a78', 'train', L.LOG_COMMIT, s1['design_code_sha256']], 1848]]
    assert sum(sc['confirm_by_run_order_decile']) == 2640 and min(sc['confirm_by_run_order_decile']) > 0
    assert sc['start_utc']['confirm'] == ['2026-09-19T19:04:44Z', '2026-09-19T21:54:54Z']
    pc = built[0]['design']['stage2_prefix_sample']['precommitment_checks']
    assert all(pc.values()) and len(pc) == 5


def test_stage2_inclusion_is_reproduced_and_git_bound(built):
    s2 = built[0]['design']['stage2_prefix_sample']
    assert (s2['N'], s2['n'], s2['n_rule_min_200_N']) == (564, 200, 200)
    assert s2['pi'] == 200 / 564 and s2['pi_pair'] == 200 * 199 / (564 * 563)
    assert s2['reproduction']['equal_to_frozen_plan'] is True and s2['plan_log_sha256_equals_log'] is True
    assert s2['seed'] == 1008219474
    assert s2['plan_invocation']['invocation'] == '0445024c72d2' and s2['plan_invocation']['git_head'] == L.PLAN_INVOCATION_COMMIT
    cb = built[0]['design']['code_binding']
    b697 = 'b697d39065697358ff9a33b59f9aa51b4cbfcb3eed3347f05443a79658d24c26'
    assert set(cb['code_sha256_recomputed_from_git'].values()) == {b697}
    assert cb['plan_sampling_block_identical'] is True and cb['design_block_identical'] is True
    assert set(cb['plan_sampling_block_sha256']) == {'design_freeze', 'log_invocation', 'plan_invocation', 'plan_commit', 'head'}


def test_stage3_seeds_replicates_and_restoration(built):
    s3 = built[0]['design']['stage3_continuations']
    assert s3['continuations_per_arm'] == 2 and s3['fork_t'] == [(1, 800)]
    assert (s3['branch_seeds_distinct'], s3['branch_seeds_shared_with_log_or_live_design_seeds'],
            s3['branch_model_call_seeds_shared_with_log_or_live'], s3['replicate_pairs_with_a_shared_seed']) == (800, 0, 0, 0)
    assert s3['replicate_agreement'] == {'agree': 368, 'disagree': 32}
    assert 'possibly shared execution shocks' in s3['replicate_agreement_reading']
    assert s3['restoration']['recheck_recomputed_transcript_hash_matches'] == 800
    assert s3['decoding'] == {'temperature': 0.7, 'top_p': 0.95, 'max_tokens': 1024}
    assert s3['restoration']['recheck_source_binding_matches'] is True
    assert s3['prefixes_with_adjacent_plan_run_orders'] == 200 and s3['start_spread_seconds_within_prefix']['n'] == 198
    assert s3['replicate_disagreement_by_arm'] == {'small': 16, 'large': 16}      # evidence table: 16 + 16 = 32
    assert 'does not by itself make their executions independent' in s3['replicate_pairing']
    sh = built[0]['design']['shared_records']
    assert sh['sampled_prefixes_also_in_log_estimator'] == 200
    assert sum(v for (arm, nonzero), v in sh['sampled_prefixes_by_log_arm_and_nonzero_weight'] if nonzero) == 101


def test_invocation_and_recovery_provenance(built):
    pv = built[0]['design']['provenance']
    assert (pv['retained_from_lost_invocation'], pv['retained_from_recovery']) == (135, 665)
    inv = pv['invocations']
    assert (inv['0445024c72d2']['run_order_min'], inv['0445024c72d2']['run_order_max']) == (0, 136)
    assert (inv['8c343c83afdc']['run_order_min'], inv['8c343c83afdc']['run_order_max']) == (134, 799)
    assert pv['lost_invocation_run_orders_missing_inside_its_range'] == [134, 135]
    assert pv['benchmark_by_invocation'] == [[['humaneval', '0445024c72d2'], 135], [['humaneval', '8c343c83afdc'], 73],
                                             [['mbpp', '8c343c83afdc'], 592]]
    assert pv['prefixes_spanning_invocations'] == {
        'log:humaneval/4#3': {'small': ['0445024c72d2'], 'large': ['8c343c83afdc']},
        'log:humaneval/46#3': {'small': ['0445024c72d2', '8c343c83afdc'], 'large': ['8c343c83afdc']}}
    assert pv['durable_decision_rows'] == 1439 and pv['durable_rows_matching_the_retained_invocation'] == 1434
    assert len(pv['durable_rows_not_matching']) == 5 and pv['recovery_ledger_total_durable_rows'] == 5
    assert pv['continuations_with_lost_invocation_durable_rows'] == pv['recovery_ledger_episode_ids'] == [
        'branch:log:humaneval/4#3:large#0', 'branch:log:humaneval/4#3:large#1', 'branch:log:humaneval/46#3:large#0',
        'branch:log:humaneval/46#3:small#1']
    assert pv['plan_order_task_contiguous'] is True and pv['execution_flags_foreign_gpu_contention'] == [[[False, False], 5288]]
    assert pv['prefixes_by_invocation_class'] == {'lost_only': 33, 'recovery_only': 165, 'spanning': 2}
    rw = pv['retention_window']
    assert rw['snapshot_equals_retained_lost_set'] is True and rw['snapshot_decision_rows'] == 243
    assert (rw['started_before_capture'], rw['started_before_capture_not_retained']) == (139, [134, 135, 137, 138])
    assert math.isclose(rw['max_observed_agent_loop_seconds'], 92.79, abs_tol=0.01)
    assert rw['kill_wait_found_in_sandbox_code'] is True
    assert math.isclose(rw['start_to_record_bound_seconds'], 92.79 + 20 + 5, abs_tol=0.01)   # + wall limit + kill wait
    assert rw['at_risk_run_orders'] == list(range(121, 139))
    assert rw['max_effect_on_B_hat_if_start_to_record_within_bound'] == 18 / 400
    assert rw['max_effect_on_B_hat_trivial'] == 139 / 400
    fb = built[0]['design']['code_binding']['frozen_record_bindings']
    assert fb['config_file_equals_records'] is True and fb['working_tree_code_sha256_equals_records'] is True
    assert all(r['retained_transcript_sha256_equal'] for r in pv['durable_rows_not_matching'])


def test_evidence_table_and_a6_crosschecks(built):
    assert all(built[0]['evidence_table_crosscheck'].values()) and len(built[0]['evidence_table_crosscheck']) == 4
    ld = built[0]['lead_derivative']
    assert math.isclose(ld['sqrt_sum_sq'], 0.04838557358567037, abs_tol=1e-15) and ld['equals_a6_uncertainty_value'] is True
    assert all(s['working_tree_equals_head'] for s in built[0]['sources'].values())


def test_identification_map_and_acceptance(built):
    idf = built[0]['identification']
    status = {c['component']: c['status'] for c in idf['components']}
    assert len(status) == 12
    assert status['stage 1: first-decision arrangement and later-decision assignment'] == 'IDENTIFIED (design mechanism)'
    assert status['stage 1: per-task law of the complete source block (outcomes, M_g, T_g, U_ga, D_ga)'] == \
        'NOT IDENTIFIED (one realization per task, even under assumptions 1-3)'
    assert status['stage 1: independence of complete source-task blocks across the 330 tasks'] == 'ASSUMED (a6: UNKNOWN)'
    assert status['retention of lost-invocation records at the completion-time cutoff'].startswith('ASSUMED')
    assert status['recovery / invocation effect on the 665 re-executed continuations'].startswith('NOT IDENTIFIED')
    assert status['seed-conditional determinism of the serving stack'].startswith('NOT INFORMATIVELY OBSERVED')
    assert status['branch-log cross terms (shared records)'].startswith('OBSERVED')
    a = idf['acceptance']
    assert '(a) Complete under declared assumptions' in a and '(b) Not identified' in a
    assert 'retention independent of the potential outcomes of the continuations started before the snapshot capture' in a
    assert 'conservative only' in a
    assert 'No standard error or interval is asserted' in a
    assert 'no standard error, interval or bootstrap' in built[0]['not_done']


def test_continuation_ledger_rows(built):
    rows = {r['episode_id']: r for r in built[3]}
    assert [r['plan_run_order'] for r in built[3]] == list(range(800))
    r = rows['branch:log:humaneval/46#3:small#1']
    assert (r['invocation'], r['durable_rows_lost_invocation'], r['durable_rows_recovery_invocation']) == ('8c343c83afdc', 2, 2)
    assert all(x['model_call_seed_t1'] == x['seed'] + 101 for x in built[3])
    assert sum(x['durable_rows_lost_invocation'] for x in built[3]) == 243          # 238 retained + 5 re-executed
    assert sum(x['durable_rows_recovery_invocation'] for x in built[3]) == 1196
    p = [x for x in built[1] if x['a_t2'] != '' and x['a_t2'] != x['a_t1']]
    assert len(p) == 225 and all(x['W_i1'] == x['W_i0'] == 0.0 for x in p)   # switching paths: neither log arm


# ------------------------------------------------------------------ the estimator algebra on hand-built designs
def ep(eid, task, arms, success):
    return dict(episode_id=eid, task_uid=task, success=success, decisions=[dict(a=a, p_large=0.5) for a in arms])


def br(parent, task, small, large):
    return [dict(parent_episode_id=parent, task_uid=task, fork_arm='small', run=j, success=s) for j, s in enumerate(small)] + \
           [dict(parent_episode_id=parent, task_uid=task, fork_arm='large', run=j, success=s) for j, s in enumerate(large)]


def test_log_weights_by_hand():
    assert L.log_weight(ep('e', 't', [0, 1], 1)) == (1, 2.0)
    assert L.log_weight(ep('e', 't', [0, 1, 1], 1)) == (1, 4.0)
    assert L.log_weight(ep('e', 't', [1, 0, 1], 0)) == (0, 0.0)


def test_unequal_prefixes_and_a_missing_within_task_arm():
    """Task g1 has three sampled prefixes (contrasts 1, 1, 0) and only arm-1 log mass; task g2 has one sampled prefix
    (contrast 0) and only arm-0 log mass; task g3 has nothing. Hand values: B = 2/4 = 0.5; v1 = 4/4 = 1 (g1: weight 4,
    success 1); v0 = 0/2 = 0 (g2: weight 2, success 0); Delta = 0.5 - (1 - 0) = -0.5."""
    elig = [ep('g1#0', 'g1', [0, 1, 1], 1), ep('g2#0', 'g2', [1, 0], 0)]
    rows = br('p1', 'g1', [0, 0], [1, 1]) + br('p2', 'g1', [0, 0], [1, 1]) + br('p3', 'g1', [1, 1], [1, 1]) + \
        br('p4', 'g2', [0, 1], [0, 1])
    e = L.estimates(['g1', 'g2', 'g3'], elig, rows)
    assert (e['B'], e['v'], e['delta']) == (0.5, [0.0, 1.0], -0.5)
    assert (e['mg']['g1'], e['mg']['g2'], e['mg']['g3']) == (3, 1, 0)
    assert (e['A']['g1'], e['A']['g2'], e['A']['g3']) == (2.0, 0.0, 0.0)
    # U_g1 = (2 - 0.5*3)/4 - (4 - 1*4)/4 + (0 - 0*0)/2 = 0.125; U_g2 = (0 - 0.5)/4 - 0 + (0 - 0*2)/2 = -0.125; U_g3 = 0
    assert e['U'] == {'g1': 0.125, 'g2': -0.125, 'g3': 0.0}
    assert e['B'] != (2 / 3 + 0) / 2            # prefix weighting differs from equal-task weighting (1/3)


def test_replicates_are_ordered_by_run_index_not_file_order():
    rows = br('p1', 'g1', [0, 1], [1, 1])
    e = L.estimates(['g1'], [ep('g1#0', 'g1', [0, 1], 1), ep('g1#1', 'g1', [1, 0], 0)], list(reversed(rows)))
    assert e['runs']['p1']['small'] == [0, 1] and e['runs']['p1']['large'] == [1, 1]


# ------------------------------------------------------------------ published outputs and the standalone checker
def test_published_ledger_equals_a_fresh_build(built):
    ledger = built[0]
    pub = json.loads((OUT / 'design_ledger.json').read_text())
    for k in ('target', 'reconciliation', 'point_estimates', 'design', 'identification', 'lead_derivative'):
        assert json.loads(json.dumps(ledger[k], default=str)) == pub[k], k
    for name, rows in zip(CSVS, built[1:]):
        assert (OUT / (name + '.csv')).read_text() == L.csv_text(rows), name


def run_check(d, *extra, env=None):
    r = subprocess.run([sys.executable, str(CHECK), '--ledger-dir', str(d)] + list(extra), capture_output=True,
                       text=True, env=env)
    return r.returncode, json.loads(r.stdout.strip().splitlines()[-1])


def copy_out(tmp_path, name):
    d = tmp_path / name
    d.mkdir()
    for f in ('design_ledger.json',) + tuple(n + '.csv' for n in CSVS):
        (d / f).write_bytes((OUT / f).read_bytes())
    return d


def test_standalone_checker_passes():
    code, res = run_check(OUT)
    assert code == 0 and res['ok'] is True and res['skipped'] == []
    assert res['checked_csv_cells'] == 564 * 29 + 330 * 13 + 800 * 19


@pytest.mark.parametrize('mutate', [
    lambda l: l['point_estimates'].update(B=0.121),
    lambda l: l['reconciliation'].update(sampled_prefixes=199),
    lambda l: l['reconciliation']['zero_arm_counts'].update(eligible_tasks_both_zero=21),
    lambda l: l['design']['stage2_prefix_sample'].update(pi=0.35),
    lambda l: l['design']['stage1_source_blocks'].update(a0_same_probability=0.5),
    lambda l: l['design']['provenance']['invocations']['8c343c83afdc'].update(run_order_min=137),
    lambda l: l['design']['code_binding']['code_sha256_recomputed_from_git'].update(plan_commit='0' * 64),
    lambda l: l['sources']['log_episodes'].update(sha256='0' * 64),
    lambda l: l['design']['stage3_continuations'].update(extra_unchecked_count=3),       # fail closed on new numbers
    lambda l: l['identification']['components'].pop(),
    lambda l: l['identification']['components'][9].update(status='IDENTIFIED'),                  # status flip
    lambda l: l['identification'].update(acceptance=l['identification']['acceptance'] + ' SE = 0.03.'),
    lambda l: l['target'].update(not_substituted='the 42-task frame replaces the target'),
    lambda l: l.update(lead_commit='007adfa'),
    lambda l: l['design']['provenance']['invocations'].update(phantom={}),                         # empty object
    lambda l: l['design']['provenance']['retention_window'].update(at_risk_run_orders=list(range(127, 139))),
    lambda l: l['point_estimates'].update(D_1=570),                                                # int for float
    lambda l: l['point_estimates'].update(B=0.1200000000009),
    lambda l: l['design']['stage2_prefix_sample']['reproduction'].update(numpy='not reproduced'),
    lambda l: l['design']['provenance']['retention_window'].update(retention_shown_ignorable=None),     # null claim key
    lambda l: l['identification'].update(standard_error_identified={}),                           # empty claim key
    lambda l: l.update(builds_on={str(i): b for i, b in enumerate(l['builds_on'])}),                # list -> dict
    lambda l: l['outputs'].update(task_ledger='results/code_routing/analysis/req017/task_ledger.csv'),
    lambda l: l['reconciliation'].update(eligible_prefixes=564.0000000000001),                    # non-integer count
    lambda l: l['design']['stage2_prefix_sample']['reproduction'].update(equal_to_frozen_plan=False),
    lambda l: l['lead_derivative'].update(sqrt_sum_sq=0.05),
])
def test_checker_fails_on_json_mutation(tmp_path, mutate):
    d = copy_out(tmp_path, 'j')
    bad = json.loads((d / 'design_ledger.json').read_text())
    mutate(bad)
    (d / 'design_ledger.json').write_text(json.dumps(bad, indent=1) + '\n')
    code, res = run_check(d)
    assert code == 1 and res['ok'] is False


@pytest.mark.parametrize('edit', [
    lambda t: t.replace('"B": 0.12,', '"B": 0.5,\n  "B": 0.12,', 1),                          # duplicate key, first wins visibly
    lambda t: t.replace('"request": "DTR-REQ-018",', '"request": "DTR-REQ-018",\n "request": "DTR-REQ-018",', 1),
    lambda t: t.replace('\n "kind"', ' "kind"', 1),                                             # non-canonical layout
])
def test_checker_rejects_duplicate_keys_and_non_canonical_json(tmp_path, edit):
    d = copy_out(tmp_path, 'k')
    t = (d / 'design_ledger.json').read_text()
    assert edit(t) != t
    (d / 'design_ledger.json').write_text(edit(t))
    code, res = run_check(d)
    assert code == 1 and res['ok'] is False


def mutate_cell(d, name, row, col, value):
    """rewrite one CSV cell and re-seal the ledger's sha256 so that only the cell check can catch it."""
    rows = list(csv.reader(io.StringIO((d / (name + '.csv')).read_text())))
    rows[row + 1][rows[0].index(col)] = value
    buf = io.StringIO()
    csv.writer(buf, lineterminator='\n').writerows(rows)
    (d / (name + '.csv')).write_text(buf.getvalue())
    led = json.loads((d / 'design_ledger.json').read_text())
    led['outputs'][name + '_sha256'] = hashlib.sha256(buf.getvalue().encode()).hexdigest()
    (d / 'design_ledger.json').write_text(json.dumps(led, indent=1) + '\n')


@pytest.mark.parametrize('name,row,col,value', [
    ('prefix_ledger', 0, 'W_i1', '2.0'),
    ('prefix_ledger', 563, 'a0_block', '1'),
    ('prefix_ledger', 5, 'inclusion_probability', '0.36'),
    ('task_ledger', 0, 'U_g1', '9.0'),
    ('task_ledger', 329, 'M_g_a0_large', '5'),
    ('task_ledger', 10, 'lead_derivative_U_g', '0.1'),
    ('continuation_ledger', 0, 'seed', '1'),
    ('continuation_ledger', 799, 'invocation', '0445024c72d2'),
    ('continuation_ledger', 400, 'success', '2'),
    ('continuation_ledger', 10, 'durable_rows_lost_invocation', '9'),
    ('task_ledger', 0, 'D_g1', '\uff11\uff10.\uff10'),                     # fullwidth digits for 10.0
    ('task_ledger', 0, 'D_g1', '0.1e2'),                                         # non-canonical spelling of 10.0
    ('prefix_ledger', 0, 'inclusion_probability', '0.354609929078'),             # truncated
    ('prefix_ledger', 0, 'branch_small_runs', '[true, true]'),                   # list cell spelled differently
    ('task_ledger', 1, 'A_g', '0.50'),                                           # trailing zero
])
def test_checker_fails_on_a_single_csv_cell(tmp_path, name, row, col, value):
    d = copy_out(tmp_path, 'c')
    mutate_cell(d, name, row, col, value)
    code, res = run_check(d)
    assert code == 1 and any(name in f and col in f for f in res['failures']), res


@pytest.mark.parametrize('name,cut', [('continuation_ledger', 14), ('task_ledger', 99), ('prefix_ledger', 28)])
def test_checker_fails_on_ragged_rows(tmp_path, name, cut):
    d = copy_out(tmp_path, 'w')
    rows = list(csv.reader(io.StringIO((d / (name + '.csv')).read_text())))
    rows[1:] = [r[:cut] if cut < len(r) else r + ['junk'] for r in rows[1:]]
    buf = io.StringIO()
    csv.writer(buf, lineterminator='\n').writerows(rows)
    (d / (name + '.csv')).write_text(buf.getvalue())
    led = json.loads((d / 'design_ledger.json').read_text())
    led['outputs'][name + '_sha256'] = hashlib.sha256(buf.getvalue().encode()).hexdigest()
    (d / 'design_ledger.json').write_text(json.dumps(led, indent=1) + '\n')
    code, res = run_check(d)
    assert code == 1 and any('cells, expected' in f for f in res['failures'])


def fake_root(tmp_path, mutate=None, commit_mutation=True):
    # a throwaway git repository holding copies of the checker's sources, optionally with one source changed
    sys.path.insert(0, str(OUT))
    import check_req018_ledger as C
    root = tmp_path / 'root'
    for rel in C.SOURCE_PATHS.values():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes((ROOT / rel).read_bytes())
    g = ['git', '-C', str(root), '-c', 'user.name=t', '-c', 'user.email=t@example.invalid']
    subprocess.run(g + ['init', '-q'], check=True)
    if mutate and commit_mutation:
        mutate(root)
    subprocess.run(g + ['add', '-A'], check=True)
    subprocess.run(g + ['commit', '-qm', 'fixture'], check=True)
    if mutate and not commit_mutation:
        mutate(root)
    return root


def flip_first_branch_success(root):
    f = root / 'results/code_routing/branch/episodes.jsonl'
    lines = f.read_text().splitlines()
    r = json.loads(lines[0])
    r['success'] = 1 - r['success']
    lines[0] = json.dumps(r)
    f.write_text('\n'.join(lines) + '\n')


def test_checker_refuses_a_tampered_archive_even_after_a_rebuild(tmp_path):
    root = fake_root(tmp_path, flip_first_branch_success)
    code, res = run_check(OUT, '--root', str(root))
    assert code == 1 and 'differs from the frozen archive' in res['failures'][0]


def test_checker_refuses_uncommitted_source_changes(tmp_path):
    note = 'docs/theory_branch_fixed_benchmark_bound.md'
    edited = fake_root(tmp_path / 'a', lambda r: (r / note).write_text('edited\n'), commit_mutation=False)
    code, res = run_check(OUT, '--root', str(edited))                 # working tree edited: not the frozen bytes
    assert code == 1 and 'differs from the frozen archive' in res['failures'][0]
    committed = fake_root(tmp_path / 'b', lambda r: (r / note).write_text('edited\n'))
    (committed / note).write_bytes((ROOT / note).read_bytes())          # frozen bytes on disk, a different HEAD blob
    code, res = run_check(OUT, '--root', str(committed))
    assert code == 1 and 'working tree differs from HEAD' in res['failures'][0]


def test_checker_fails_on_swapped_replicate_order(tmp_path):
    d = copy_out(tmp_path, 'r')
    rows = list(csv.DictReader(io.StringIO((OUT / 'prefix_ledger.csv').read_text())))
    k = next(i for i, r in enumerate(rows) if r['branch_small_runs'] in ('[0, 1]', '[1, 0]'))
    swapped = '[1, 0]' if rows[k]['branch_small_runs'] == '[0, 1]' else '[0, 1]'
    mutate_cell(d, 'prefix_ledger', k, 'branch_small_runs', swapped)
    code, res = run_check(d)
    assert code == 1 and any('branch_small_runs' in f for f in res['failures'])


def test_checker_without_numpy_fails_unless_skip_is_allowed(tmp_path):
    fake = tmp_path / 'nonumpy'
    fake.mkdir()
    (fake / 'numpy.py').write_text("raise ImportError('numpy hidden for this test')\n")
    env = dict(os.environ, PYTHONPATH=str(fake))
    code, res = run_check(OUT, env=env)
    assert code == 1 and res['ok'] is False and 'numpy absent' in res['failures'][0]
    code, res = run_check(OUT, '--allow-skip-repro', env=env)
    assert code == 0 and res['ok'] is True
    assert res['skipped'] == ['design.stage2_prefix_sample.reproduction.equal_to_frozen_plan']
