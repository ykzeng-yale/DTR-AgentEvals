"""DTR-REQ-025 deterministic fixtures for experiments/v2_sim/precision_design_audit.py (Codex lead request, final
section of docs/experiment_handoff.md; derivation docs/theory_precision_design_20260926.md). Independent oracles:
the score is re-derived here from the original V/W/Q sum (the product of importance ratios is rebuilt from scratch
at every step), the counts are recomputed with ordinary floats from literal widths, and the group identities are
checked by separate enumeration. Expected values are the note's printed numbers or hand-derived literals, never the
audit's own formulas. No sampling, Monte Carlo or coverage claim."""
import hashlib
import itertools
import json
import math
import sys
from fractions import Fraction as F
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments/v2_sim'))
import precision_design_audit as A  # noqa: E402

HALF = F(1, 2)


def oracle_phi(steps, y):
    """the original terminal DR sum: V_t = Q_t(target_t), W_t = prod_{s <= t} 1{logged_s = target_s} / p_s(logged_s),
    phi = V_1 + sum_t W_t (V_{t+1} - Q_t(logged_t)), V_{K+1} = Y. steps: (p of the logged action, logged, target, Q)."""
    values = [q[target] for _, _, target, q in steps] + [y]
    phi = values[0]
    for t in range(len(steps)):
        weight = F(1)
        for prob, logged, target, _ in steps[:t + 1]:
            weight = weight * (F(1) / prob if logged == target else 0)
        phi += weight * (values[t + 1] - steps[t][3][steps[t][1]])
    return phi


def oracle_pair(a1, a2, pi_h, pi_p, q1h, q1p, q2h, q2p, y, off=(0, 0, 0, 0)):
    """both target scores on one logged trajectory; the common initial action is 0."""
    h = oracle_phi([(HALF, a1, 0, {0: q1h, 1: off[0]}), (HALF, a2, pi_h, {pi_h: q2h, 1 - pi_h: off[1]})], y)
    p = oracle_phi([(HALF, a1, 0, {0: q1p, 1: off[2]}), (HALF, a2, pi_p, {pi_p: q2p, 1 - pi_p: off[3]})], y)
    return h, p


def vertices():
    for pattern in itertools.product((0, 1), repeat=4):
        for cont in itertools.product((0, 1), repeat=5):
            yield pattern + cont


def test_512_vertices_give_score_range_minus3_to_4_and_contrast_range_minus5_to_5():
    scores, contrasts = [], []
    for a1, pi_h, pi_p, a2, q1h, q1p, q2h, q2p, y in vertices():
        h, p = oracle_pair(a1, a2, pi_h, pi_p, q1h, q1p, q2h, q2p, y)
        scores += [h, p]
        contrasts.append(h - p)
    assert len(contrasts) == 512
    assert (min(scores), max(scores), min(contrasts), max(contrasts)) == (-3, 4, -5, 5)
    rep = A.score_range_audit()['nonabsorbed']
    assert rep['vertices'] == 512
    assert (rep['marginal']['min'], rep['marginal']['max']) == (-3, 4)
    assert (rep['contrast']['min'], rep['contrast']['max']) == (-5, 5)
    assert rep['closed_form_agrees_everywhere'] and rep['off_policy_nuisance_irrelevant']


def test_audit_witnesses_attain_the_extrema_under_the_oracle():
    rep = A.score_range_audit()['nonabsorbed']
    for key, target in (('min_witnesses', -3), ('max_witnesses', 4)):
        assert rep['marginal'][key]
        for w in rep['marginal'][key]:
            h, p = oracle_pair(w['A1'], w['A2'], w['pi_H2'], w['pi_P2'], w['q1_H'], w['q1_P'], w['q2_H'], w['q2_P'],
                               w['Y'])
            assert (h if w['policy'] == 'H' else p) == target
    for key, target in (('min_witnesses', -5), ('max_witnesses', 5)):
        assert rep['contrast'][key]
        for w in rep['contrast'][key]:
            h, p = oracle_pair(w['A1'], w['A2'], w['pi_H2'], w['pi_P2'], w['q1_H'], w['q1_P'], w['q2_H'], w['q2_P'],
                               w['Y'])
            assert h - p == target
    # hand: +5 needs A1 = S, disagreeing targets and q1_H = 0, q1_P = 1, with either A2 = pi_H2, Y = 1, q2_H = q2_P = 0
    # (4Y - 2(q2_H + q2_P) - (q1_H - q1_P)) or A2 = pi_P2, Y = 0, q2_H = q2_P = 1 (-4Y + 2(q2_H + q2_P) - ...):
    # two target patterns times two observed-action cases = 4 witnesses; -5 is the mirror image
    top = rep['contrast']['max_witnesses']
    assert len(top) == 4 and all(w['A1'] == 0 and w['pi_H2'] != w['pi_P2'] and (w['q1_H'], w['q1_P']) == (0, 1)
                                 for w in top)
    assert all((w['A2'] == w['pi_H2'] and (w['Y'], w['q2_H'], w['q2_P']) == (1, 0, 0))
               or (w['A2'] == w['pi_P2'] and (w['Y'], w['q2_H'], w['q2_P']) == (0, 1, 1)) for w in top)
    assert len(rep['contrast']['min_witnesses']) == 4


def test_case_ranges_match_the_note_statements():
    cases = A.score_range_audit()['nonabsorbed']['by_case']
    assert (cases['I=0']['contrast_min'], cases['I=0']['contrast_max']) == (-1, 1)
    for k in ('I=1, targets agree, A2 observed', 'I=1, targets agree, A2 not observed'):
        assert (cases[k]['contrast_min'], cases[k]['contrast_max']) == (-3, 3)
    for k in ('I=1, targets disagree, A2 matches H', 'I=1, targets disagree, A2 matches P'):
        assert (cases[k]['contrast_min'], cases[k]['contrast_max']) == (-5, 5)
    assert sum(c['vertices'] for c in cases.values()) == 512


def test_audit_score_equals_the_oracle_on_vertices_and_fractional_interior_points():
    grid = (F(0), F(1, 3), F(1))
    for a1, pi_h, pi_p, a2 in itertools.product((0, 1), repeat=4):
        for q1h, q2p, y in itertools.product(grid, repeat=3):
            q1p, q2h, off = F(5, 7), F(2, 9), (F(1, 4), F(3, 5), F(1, 8), F(6, 7))
            h, p = oracle_pair(a1, a2, pi_h, pi_p, q1h, q1p, q2h, q2p, y, off)
            assert A.dr_score(A.nonabsorbed_trajectory(a1, a2, pi_h, q1h, off[0], q2h, off[1]), y) == h
            assert A.dr_score(A.nonabsorbed_trajectory(a1, a2, pi_p, q1p, off[2], q2p, off[3]), y) == p
            assert -3 <= h <= 4 and -3 <= p <= 4 and -5 <= h - p <= 5
    fixtures = A.score_range_audit()['fractional_interior_fixtures']
    assert len(fixtures) == 48 and all(f['closed_form_agrees'] and f['within_case_vertex_range'] for f in fixtures)
    for f in fixtures:
        fx = f['fixture']
        h, p = oracle_pair(f['A1'], f['A2'], f['pi_H2'], f['pi_P2'], fx['q1_H'], fx['q1_P'], fx['q2_H'], fx['q2_P'],
                           fx['Y'], f['off'])
        assert (f['phi_H'], f['phi_P']) == (h, p)


def test_scores_are_affine_in_the_continuous_variables_for_each_pattern():
    x, z = (F(0), F(1), F(1, 2), F(1, 4), F(1)), (F(1), F(1, 3), F(0), F(1), F(2, 5))
    for a1, pi_h, pi_p, a2 in itertools.product((0, 1), repeat=4):
        for t in (F(1, 3), F(1, 2), F(4, 5)):
            mid = tuple(t * u + (1 - t) * v for u, v in zip(x, z))
            hx, px = oracle_pair(a1, a2, pi_h, pi_p, *x)
            hz, pz = oracle_pair(a1, a2, pi_h, pi_p, *z)
            hm, pm = oracle_pair(a1, a2, pi_h, pi_p, *mid)
            assert hm == t * hx + (1 - t) * hz and pm == t * px + (1 - t) * pz


def test_absorption_cases_are_enumerated_separately():
    scores, contrasts = [], []
    for a1, q1h, q1p, padh, padp, y in itertools.product((0, 1), repeat=6):
        h = oracle_phi([(HALF, a1, 0, {0: q1h, 1: 0}), (F(1), 'noop', 'noop', {'noop': padh})], y)
        p = oracle_phi([(HALF, a1, 0, {0: q1p, 1: 0}), (F(1), 'noop', 'noop', {'noop': padp})], y)
        scores += [h, p]
        contrasts.append(h - p)
    assert (min(scores), max(scores), min(contrasts), max(contrasts)) == (-1, 2, -1, 1)
    for pads in itertools.product((0, 1), repeat=2):
        for y in (0, F(1, 3), 1):
            assert oracle_phi([(F(1), 'noop', 'noop', {'noop': pads[0]}),
                               (F(1), 'noop', 'noop', {'noop': pads[1]})], y) == y
    rep = A.score_range_audit()
    after, start = rep['absorbed_after_first_action'], rep['absorbed_from_start']
    assert after['vertices'] == 64 and start['vertices'] == 32
    assert (after['marginal']['min'], after['marginal']['max'], after['contrast']['min'],
            after['contrast']['max']) == (-1, 2, -1, 1)
    assert (start['marginal']['min'], start['marginal']['max'], start['contrast']['min'],
            start['contrast']['max']) == (0, 1, 0, 0)
    assert after['closed_form_agrees_everywhere'] and after['off_policy_nuisance_irrelevant']
    assert start['score_equals_Y_everywhere']


def test_dr_score_refuses_invalid_inputs():
    good = A.nonabsorbed_trajectory(0, 0, 0, F(1, 2), 0, F(1, 2), 0)
    cases = [
        (lambda: A.dr_score(good, F(3, 2)), 'outside'),
        (lambda: A.dr_score(good, float('nan')), 'not finite'),
        (lambda: A.dr_score(good, True), 'int, Fraction'),
        (lambda: A.dr_score([], 0), 'at least one'),
        (lambda: A.dr_score([dict(good[0], p={0: F(1, 2), 1: F(1, 3)})], 0), 'sum to one'),
        (lambda: A.dr_score([dict(good[0], pi=2)], 0), 'support'),
        (lambda: A.dr_score([dict(good[0], q={0: F(1, 2)})], 0), 'exactly the eligible'),
        (lambda: A.dr_score([dict(good[0], q={0: F(3, 2), 1: 0})], 0), 'outside'),
    ]
    for call, match in cases:
        with pytest.raises(A.AuditInputError, match=match):
            call()


# literal widths (the note's direct widths and rectangle multipliers), independent of the audit's derivation
FLOAT_WIDTHS = {'direct_contrast': ((2, 10, 12), 3), 'rectangle_original': ((2, 26, 28), 4),
                'rectangle_tightened': ((2, 14, 16), 4)}


def float_half_width(w, b, split):
    return w * math.sqrt(math.log(2 * split / 0.05) / (2 * b))


def test_sufficient_counts_match_the_note_floats_and_straddle_each_threshold():
    tables = A.audit()['sufficient_counts']
    assert {h: [tables['direct_contrast']['rows'][h][c]['B'] for c in A.CONTRASTS] for h in ('0.10', '0.05', '0.02')} \
        == {'0.10': [958, 23938, 34470], '0.05': [3830, 95750, 137880], '0.02': [23938, 598437, 861749]}
    assert [tables['rectangle_original']['rows']['0.05'][c]['B'] for c in A.CONTRASTS] == [4061, 686164, 795788]
    assert [tables['rectangle_tightened']['rows']['0.05'][c]['B'] for c in A.CONTRASTS] == [4061, 198947, 259849]
    for method, (widths, split) in FLOAT_WIDTHS.items():
        for h in (0.10, 0.05, 0.02):
            for c, w in zip(A.CONTRASTS, widths):
                cell = tables[method]['rows']['%.2f' % h][c]
                b = math.ceil(w * w * math.log(2 * split / 0.05) / (2 * h * h))
                assert cell['width'] == w and cell['B'] == b
                assert float_half_width(w, b, split) <= h < float_half_width(w, b - 1, split)
                assert cell['straddles'] and cell['float_agrees']
                assert float(cell['half_width_at_B']) == pytest.approx(float_half_width(w, b, split), rel=1e-12)


def test_decimal_logs_have_60_digits_and_the_j20_costs_match_the_note():
    lt = A.log_term('0.05', 3)
    assert str(lt).startswith('4.78749174278204599424770093452') and len(str(lt).replace('.', '')) >= 60
    assert float(lt) == pytest.approx(math.log(120), rel=1e-15)
    comp = A.audit()['note_comparison']
    assert comp['direct_table_matches_note'] and comp['rectangle_at_05_matches_note'] and comp['j20']['matches_note']
    assert A.block_trajectories(20, 1, 1, 1) == 60
    assert 3830 * 60 == 229800 and 137880 * 60 == 8272800                       # the note's arithmetic
    costs = A.audit()['j20_trajectory_costs']['costs']['direct_contrast']['0.05']
    assert costs['fresh_gain'] == 229800 and costs['all_three'] == 8272800
    with pytest.raises(A.AuditInputError):
        A.block_trajectories(0, 1, 1, 1)


def test_concentration_factor_literals_and_equal_weight_identity():
    # hand: (1/2)^2 / 2 + (1/3)^2 / 3 + (1/6)^2 / 1 = 1/8 + 1/27 + 1/36 = 41/216
    assert A.concentration_factor([F(1, 2), F(1, 3), F(1, 6)], [2, 3, 1]) == F(41, 216)
    for j, r in ((1, 1), (2, 5), (7, 3), (20, 7)):
        assert A.concentration_factor([F(1, j)] * j, [r] * j) == F(1, j * r)
    assert A.concentration_factor([0.25, 0.75], [1, 3]) == F(1, 16) + F(9, 16) / 3     # exact binary floats
    assert A.concentration_factor([1, 0], [4, 1]) == F(1, 4)                          # a zero weight is allowed


def test_one_replicate_per_group_permits_the_bound_but_refuses_the_variance_estimate():
    # hand: two groups of weight 1/2 with R_g = 1 each: factor (1/2)^2 / 1 + (1/2)^2 / 1 = 1/2. The known-bound
    # concentration formula permits R_g = 1; an empirical within-group variance estimate does not.
    assert A.concentration_factor([F(1, 2), F(1, 2)], [1, 1]) == F(1, 2)
    hw = A.weighted_half_width(2, [F(1, 2), F(1, 2)], [1, 1])
    assert float(hw) == pytest.approx(2 * math.sqrt(math.log(120) / 2 * 0.5), rel=1e-12)
    with pytest.raises(A.AuditInputError, match='R_g >= 2'):
        A.within_group_variance_estimate([F(1, 2), F(1, 2)], [[0], [1]])
    rec = A.audit()['independent_groups']['one_replicate_per_group']
    assert rec['factor'] == F(1, 2) and rec['within_group_variance_estimate'].startswith('refused')


def test_weighted_half_width_equals_the_complete_block_form_for_one_group():
    # one group with R replicates is the complete-block case: w sqrt(log(6/alpha) / (2R))
    for r in (1, 7, 3830):
        assert float(A.weighted_half_width(2, [1], [r])) == pytest.approx(float_half_width(2, r, 3), rel=1e-12)


def test_finite_distribution_mean_variance_and_unbiased_within_group_estimate():
    # group 1: C in {0, 1} each 1/2 (mean 1/2, variance 1/4), R = 2; group 2: C in {-1, 2} with 2/3, 1/3 (mean 0,
    # variance 2), R = 3; weights 1/4, 3/4. Hand: E = 1/8, Var = (1/16)(1/4)/2 + (9/16)(2)/3 = 1/128 + 3/8 = 49/128
    w = [F(1, 4), F(3, 4)]
    g1 = [(0, HALF), (1, HALF)]
    g2 = [(-1, F(2, 3)), (2, F(1, 3))]
    e = e2 = ev = F(0)
    for o1 in itertools.product(g1, repeat=2):
        for o2 in itertools.product(g2, repeat=3):
            prob = math.prod(p for _, p in o1 + o2)
            x1, x2 = [x for x, _ in o1], [x for x, _ in o2]
            est = w[0] * F(sum(x1), 2) + w[1] * F(sum(x2), 3)
            e += prob * est
            e2 += prob * est * est
            ev += prob * A.within_group_variance_estimate(w, [x1, x2])
            assert A.weighted_estimate(w, [x1, x2]) == est
    assert (e, e2 - e * e, ev) == (F(1, 8), F(49, 128), F(49, 128))
    assert A.weighted_variance(w, [2, 3], [F(1, 4), 2]) == F(49, 128)
    chk = A.audit()['independent_groups']['finite_distribution']
    assert chk['agree'] and chk['enumerated_variance'] == F(49, 128)


def test_common_shock_makes_an_independent_task_calculation_miss_a_factor_j():
    for j in (2, 3, 4):
        theta = [F(g, j) for g in range(j)]
        e = e2 = F(0)
        for shocks in itertools.product((-1, 1), repeat=2):          # U_1, U_2 shared by every task
            est = sum(F(1, j) * (t + F(sum(shocks), 2)) for t in theta)
            e += F(1, 4) * est
            e2 += F(1, 4) * est * est
        assert e2 - e * e == F(1, 2)                                   # Var(U) / R with Var(U) = 1, R = 2
        naive = A.weighted_variance([F(1, j)] * j, [2] * j, [1] * j)
        assert naive == F(1, 2 * j) and (e2 - e * e) / naive == j
    cs = A.audit()['independent_groups']['common_shock']
    assert (cs['true_variance'], cs['independent_task_variance'], cs['understatement_factor']) == (F(1, 2), F(1, 6), 3)


E = A.AuditInputError
BAD_GROUP_INPUTS = [
    ('bool weight', lambda: A.concentration_factor([True, 0], [1, 1]), 'int, Fraction'),
    ('bool count', lambda: A.concentration_factor([1], [True]), 'positive int'),
    ('zero count', lambda: A.concentration_factor([1], [0]), 'positive int'),
    ('float count', lambda: A.concentration_factor([1], [2.0]), 'positive int'),
    ('empty weights', lambda: A.concentration_factor([], []), 'empty'),
    ('nan weight', lambda: A.concentration_factor([float('nan'), 1], [1, 1]), 'not finite'),
    ('inf weight', lambda: A.concentration_factor([float('inf')], [1]), 'not finite'),
    ('negative weight', lambda: A.concentration_factor([F(3, 2), F(-1, 2)], [1, 1]), 'nonnegative'),
    ('weights not summing to one', lambda: A.concentration_factor([F(1, 2), F(1, 3)], [1, 1]), 'sum exactly'),
    ('inexact float weights', lambda: A.concentration_factor([0.1] * 10, [1] * 10), 'sum exactly'),
    ('length mismatch', lambda: A.concentration_factor([F(1, 2), F(1, 2)], [1]), 'need 2'),
    ('string weights', lambda: A.concentration_factor('11', [1, 1]), 'list or tuple'),
    ('dict counts', lambda: A.concentration_factor([1], {0: 1}), 'list or tuple'),
    ('replicate shape', lambda: A.weighted_estimate([F(1, 2), F(1, 2)], [[0, 1]]), 'need replicate values'),
    ('empty group', lambda: A.weighted_estimate([1], [[]]), 'empty'),
    ('negative variance', lambda: A.weighted_variance([1], [2], [-1]), 'nonnegative'),
    ('bad alpha', lambda: A.weighted_half_width(2, [1], [1], alpha='1.5'), 'alpha'),
    ('float alpha', lambda: A.log_term(0.05, 3), 'decimal string'),
    ('zero h', lambda: A.sufficient_count(2, '0', A.log_term('0.05', 3)), 'positive'),
    ('zero blocks', lambda: A.half_width(2, 0, A.log_term('0.05', 3)), 'positive int'),
    ('balanced zero J', lambda: A.balanced_replicates(10, 0), 'positive int'),
]


@pytest.mark.parametrize('name,call,match', BAD_GROUP_INPUTS, ids=[b[0] for b in BAD_GROUP_INPUTS])
def test_invalid_group_and_count_inputs_are_refused(name, call, match):
    with pytest.raises(E, match=match):
        call()


def test_balanced_replicates_is_the_ceiling_of_the_total_over_j():
    assert A.balanced_replicates(3830, 20) == 192 and A.balanced_replicates(3840, 20) == 192
    assert A.balanced_replicates(3841, 20) == 193
    r = A.balanced_replicates(3830, 20)
    assert F(1, 20 * r) <= F(1, 3830)


def test_record_is_written_once_with_pins_and_refuses_to_overwrite(tmp_path):
    out = tmp_path / 'record.json'
    rec = A.write_record(out)
    on_disk = json.loads(out.read_text())
    assert on_disk == rec and rec['request'] == 'DTR-REQ-025'
    assert 'no empirical coverage' in rec['status'] and 'cost saving' in rec['status']
    for key, rel in (('source', A.SOURCE), ('tests', A.TESTS), ('note', A.NOTE)):
        assert rec['pins'][key]['sha256'] == hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    assert rec['pins']['note']['sha256'] == A.NOTE_SHA256
    assert any('R_g = 1' in x and 'DO permit' in x for x in rec['limitations'])
    assert rec['results']['note_comparison']['j20']['matches_note'] is True
    with pytest.raises(E, match='never overwritten'):
        A.write_record(out)
    assert json.loads(out.read_text()) == rec


def test_record_refuses_a_changed_lead_note(tmp_path, monkeypatch):
    monkeypatch.setattr(A, 'NOTE_SHA256', '0' * 64)
    with pytest.raises(E, match='lead note changed'):
        A.write_record(tmp_path / 'record.json')
    assert not (tmp_path / 'record.json').exists()


def test_the_committed_record_when_present_is_bound_to_the_current_files():
    if not A.OUT.exists():
        pytest.skip('the final record has not been generated yet')
    rec = json.loads(A.OUT.read_text())
    for key, rel in (('source', A.SOURCE), ('tests', A.TESTS), ('note', A.NOTE)):
        assert rec['pins'][key]['sha256'] == hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    fresh = json.loads(json.dumps(A._jsonable(A.audit())))
    assert rec['results'] == fresh


def test_module_is_pure_standard_library_arithmetic():
    src = (ROOT / A.SOURCE).read_text()
    for banned in ('import random', 'numpy', 'subprocess', 'secrets', 'urllib', 'socket'):
        assert banned not in src
