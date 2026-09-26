"""DTR-REQ-025 (Codex lead; request in the final section of docs/experiment_handoff.md, derivation
docs/theory_precision_design_20260926.md pinned at its final sha256 6303403a..., amended from the initial
9b1eddd5... with references and wording only): deterministic precision-design audit.
Standard-library arithmetic only: no randomness, sampling, Monte Carlo, model, server or host work, and no change to
an existing estimator. The lead owns the derivation and its interpretation; this module reproduces its arithmetic.

1. Score range (note Sec. 1). The terminal DR score of the complete-block note, eq. 6, with K = 2 decisions, a logger
   choosing each of two actions with probability 1/2 at an eligible decision, deterministic targets and a common
   initial action S: phi = V_1 + sum_t W_t (V_{t+1} - Q_t(H_t, A_t)), V_3 = Y. dr_score evaluates that general
   sum on all 512 nonabsorbed binary vertices (A1, pi_H2, pi_P2, A2 in {0, 1} and q1_H, q1_P, q2_H, q2_P, Y in
   {0, 1}), with BOTH target scores on the same trajectory. It is cross-checked against the note's closed form, the
   off-policy nuisance entries are shown to be irrelevant, and the two absorption cases are enumerated separately.
   For a fixed discrete pattern each expression is affine in the five continuous variables, so the vertex extrema
   are the extrema over the unit cube. That is the note's mathematical argument, not an empirical coverage check.
2. Sufficient complete-block counts (note Sec. 2) for alpha = 0.05 and h in {0.10, 0.05, 0.02}, three methods:
   direct contrast Hoeffding (alpha/3 each; contrast widths 2, 10, 12), and the four-coordinate rectangle (alpha/4
   each) with the original widths (13, 13, 1, 1) or the tightened widths (7, 7, 1, 1). Logs, square roots and
   ceilings use 60-digit Decimal arithmetic. Each count B is checked to straddle its threshold (half-width(B) <= h <
   half-width(B - 1)) and against ordinary floats. The counts are worst-case SUFFICIENT bounds, never necessary
   sample sizes or power requirements. The note's J = 20 costs are counted in trajectories, not tokens, time or
   money.
3. Independent fixed groups (note Sec. 3): the exact concentration factor sum_g lambda_g^2 / R_g, the weighted
   estimate and its variance, the within-group variance estimate (R_g >= 2 only) and the weighted half-width, with
   a finite-distribution check and the common-shock counterexample (an independent-task calculation understates the
   variance by the factor J). These identities rest on a stronger independence contract that no code can verify.
4. write_record: the JSON record (labels, assumptions, exact results and witnesses, tables, source/test/note pins,
   command, Python version, limitations); a new file only, never an overwrite.

    PYTHONPATH=src .venv/bin/python experiments/v2_sim/precision_design_audit.py            # print a summary only
    PYTHONPATH=src .venv/bin/python experiments/v2_sim/precision_design_audit.py --write    # the new record only
"""
from __future__ import annotations

import datetime
import hashlib
import itertools
import json
import math
import platform
import sys
from collections import OrderedDict
from decimal import ROUND_CEILING, Decimal, localcontext
from fractions import Fraction
from pathlib import Path

VERSION = 'precision_design_audit_v1'
ROOT = Path(__file__).resolve().parents[2]
SOURCE = 'experiments/v2_sim/precision_design_audit.py'
TESTS = 'tests/test_precision_design_audit.py'
NOTE = 'docs/theory_precision_design_20260926.md'
NOTE_SHA256 = '6303403a35b4046e423cf7a5255799b495bd5ea104868d3c6bae91d5fefb2897'          # final (lead amendment)
NOTE_INITIAL_SHA256 = '9b1eddd5708cbb596895d93d65e4e17a2eb06796aa7e65bf5f084b429b719731'  # as first requested
OUT = ROOT / 'results/v2_sim/precision_design_20260926/record.json'
COMMAND = 'PYTHONPATH=src .venv/bin/python experiments/v2_sim/precision_design_audit.py --write'

S = 0                                          # the common initial action of both targets
ACTIONS = (0, 1)
NOOP = 'noop'
ELIGIBLE = {0: Fraction(1, 2), 1: Fraction(1, 2)}    # the logger at an eligible decision
ABSORBED = {NOOP: Fraction(1)}                       # an absorbed decision: a common no-op with probability one
PREC = 60
ALPHA = Decimal('0.05')
HALF_WIDTHS = (Decimal('0.10'), Decimal('0.05'), Decimal('0.02'))
CONTRASTS = ('fresh_gain', 'offline_gain', 'gain_calibration_discrepancy')
COEFFICIENTS = {'fresh_gain': (0, 0, 1, -1), 'offline_gain': (1, -1, 0, 0),
                'gain_calibration_discrepancy': (1, -1, -1, 1)}      # over (O_H, O_P, F_H, F_P)
ORIGINAL_COORDINATE_WIDTHS = (13, 13, 1, 1)          # the complete-block note's deliberately coarse [-6, 7] scores
# the note's printed values, transcribed for comparison (Sec. 2 table, rectangle counts at h = .05, J = 20 costs)
NOTE_DIRECT_TABLE = {'0.10': (958, 23938, 34470), '0.05': (3830, 95750, 137880), '0.02': (23938, 598437, 861749)}
NOTE_RECTANGLE_AT_05 = {'rectangle_original': (4061, 686164, 795788), 'rectangle_tightened': (4061, 198947, 259849)}
NOTE_J20 = dict(J=20, n_log=1, n_H=1, n_P=1, fresh_gain_at_05=229800, simultaneous_at_05=8272800)


class AuditInputError(ValueError):
    """invalid input; refused, never repaired."""


def _exact(x, what):
    if isinstance(x, bool) or not isinstance(x, (int, float, Fraction)):
        raise AuditInputError('%s must be an int, Fraction or finite float, got %r' % (what, x))
    if isinstance(x, float) and not math.isfinite(x):
        raise AuditInputError('%s is not finite: %r' % (what, x))
    return Fraction(x)


def _unit(x, what):
    v = _exact(x, what)
    if not 0 <= v <= 1:
        raise AuditInputError('%s = %s lies outside [0, 1]' % (what, v))
    return v


# ------------------------------------------------------------------------------------------ 1. score range

def dr_score(decisions, y):
    """eq. 6 of the complete-block note for a deterministic target: V_t = Q_t(H_t, pi_t), W_t = prod_{s<=t}
    1{A_s = pi_s} / p_s(A_s) and phi = V_1 + sum_t W_t (V_{t+1} - Q_t(H_t, A_t)) with V_{K+1} = Y. Each decision is a
    dict with the logger probabilities p (over the eligible actions), the logged action a, the target action pi and
    the nuisance table q (one bounded value per eligible action)."""
    y = _unit(y, 'Y')
    if not decisions:
        raise AuditInputError('at least one decision is required')
    for t, d in enumerate(decisions):
        p, q = d['p'], d['q']
        if sum(p.values()) != 1 or any(v <= 0 for v in p.values()):
            raise AuditInputError('decision %d: logger probabilities must be positive and sum to one' % t)
        if d['a'] not in p or d['pi'] not in p:
            raise AuditInputError('decision %d: logged and target actions must be in the logger support' % t)
        if set(q) != set(p):
            raise AuditInputError('decision %d: the nuisance table must cover exactly the eligible actions' % t)
        for a, v in q.items():
            _unit(v, 'decision %d Q(%s)' % (t, a))
    v = [Fraction(d['q'][d['pi']]) for d in decisions] + [y]
    phi, w = v[0], Fraction(1)
    for t, d in enumerate(decisions):
        w = w * (1 if d['a'] == d['pi'] else 0) / d['p'][d['a']]
        phi += w * (v[t + 1] - Fraction(d['q'][d['a']]))
    return phi


def closed_form_score(i, j, q1, q2, y):
    """the note's nonabsorbed form phi = q1 + 2 I (q2 - q1) + 4 I J (Y - q2)."""
    return q1 + 2 * i * (q2 - q1) + 4 * i * j * (y - q2)


def closed_form_absorbed_after_first(i, q1, y):
    """the note's absorbed-after-the-first-action form q1 + 2 I (Y - q1)."""
    return q1 + 2 * i * (y - q1)


def nonabsorbed_trajectory(a1, a2, pi2, q1, q1_off, q2, q2_off):
    return [dict(p=ELIGIBLE, a=a1, pi=S, q={S: q1, 1 - S: q1_off}),
            dict(p=ELIGIBLE, a=a2, pi=pi2, q={pi2: q2, 1 - pi2: q2_off})]


def absorbed_after_first_trajectory(a1, q1, q1_off, pad):
    return [dict(p=ELIGIBLE, a=a1, pi=S, q={S: q1, 1 - S: q1_off}), dict(p=ABSORBED, a=NOOP, pi=NOOP, q={NOOP: pad})]


def absorbed_from_start_trajectory(pad1, pad2):
    return [dict(p=ABSORBED, a=NOOP, pi=NOOP, q={NOOP: pad1}), dict(p=ABSORBED, a=NOOP, pi=NOOP, q={NOOP: pad2})]


def case_label(v):
    if v['A1'] != S:
        return 'I=0'
    if v['pi_H2'] == v['pi_P2']:
        return 'I=1, targets agree, A2 %s' % ('observed' if v['A2'] == v['pi_H2'] else 'not observed')
    return 'I=1, targets disagree, A2 matches %s' % ('H' if v['A2'] == v['pi_H2'] else 'P')


def enumerate_nonabsorbed(off=(0, 0, 0, 0)):
    """[(vertex, phi_H, phi_P)] over the 16 discrete patterns x 32 binary nuisance/outcome vertices; off holds the
    off-policy nuisance entries (Q1_H, Q2_H, Q1_P, Q2_P at the actions the targets do not take)."""
    rows = []
    for a1, pi_h, pi_p, a2 in itertools.product(ACTIONS, repeat=4):
        for q1h, q1p, q2h, q2p, y in itertools.product((0, 1), repeat=5):
            v = OrderedDict(A1=a1, A2=a2, pi_H2=pi_h, pi_P2=pi_p, q1_H=q1h, q1_P=q1p, q2_H=q2h, q2_P=q2p, Y=y)
            ph = dr_score(nonabsorbed_trajectory(a1, a2, pi_h, q1h, off[0], q2h, off[1]), y)
            pp = dr_score(nonabsorbed_trajectory(a1, a2, pi_p, q1p, off[2], q2p, off[3]), y)
            rows.append((v, ph, pp))
    return rows


def enumerate_absorbed_after_first(off=(0, 0)):
    rows = []
    for a1, q1h, q1p, padh, padp, y in itertools.product(ACTIONS, (0, 1), (0, 1), (0, 1), (0, 1), (0, 1)):
        v = OrderedDict(A1=a1, q1_H=q1h, q1_P=q1p, pad_H=padh, pad_P=padp, Y=y)
        rows.append((v, dr_score(absorbed_after_first_trajectory(a1, q1h, off[0], padh), y),
                     dr_score(absorbed_after_first_trajectory(a1, q1p, off[1], padp), y)))
    return rows


def enumerate_absorbed_from_start():
    rows = []
    for p1h, p1p, p2h, p2p, y in itertools.product((0, 1), repeat=5):
        v = OrderedDict(pad1_H=p1h, pad1_P=p1p, pad2_H=p2h, pad2_P=p2p, Y=y)
        rows.append((v, dr_score(absorbed_from_start_trajectory(p1h, p2h), y),
                     dr_score(absorbed_from_start_trajectory(p1p, p2p), y)))
    return rows


def extrema(items):
    """min and max of (value, witness) items with every witness attaining each."""
    lo, hi = min(x for x, _ in items), max(x for x, _ in items)
    return OrderedDict(min=lo, max=hi, min_witnesses=[w for x, w in items if x == lo],
                       max_witnesses=[w for x, w in items if x == hi])


def _range_summary(rows):
    marginal = extrema([(ph, OrderedDict(v, policy='H')) for v, ph, _ in rows]
                       + [(pp, OrderedDict(v, policy='P')) for v, _, pp in rows])
    contrast = extrema([(ph - pp, v) for v, ph, pp in rows])
    return OrderedDict(vertices=len(rows), marginal=marginal, contrast=contrast)


FRACTIONAL_FIXTURES = (
    dict(q1_H=Fraction(1, 3), q1_P=Fraction(3, 4), q2_H=Fraction(2, 5), q2_P=Fraction(1, 7), Y=Fraction(5, 6),
         off=(Fraction(1, 2), Fraction(2, 3), Fraction(1, 9), Fraction(7, 8))),
    dict(q1_H=Fraction(0), q1_P=Fraction(1), q2_H=Fraction(1, 2), q2_P=Fraction(1, 2), Y=Fraction(1, 3),
         off=(Fraction(1), Fraction(0), Fraction(1), Fraction(0))),
    dict(q1_H=Fraction(99, 100), q1_P=Fraction(1, 100), q2_H=Fraction(1, 100), q2_P=Fraction(99, 100),
         Y=Fraction(1, 2), off=(Fraction(1, 4), Fraction(3, 4), Fraction(1, 4), Fraction(3, 4))),
)


def score_range_audit():
    base = enumerate_nonabsorbed()
    invariant = all(enumerate_nonabsorbed(off) == base for off in itertools.product((0, 1), repeat=4))
    closed = all(ph == closed_form_score(int(v['A1'] == S), int(v['A2'] == v['pi_H2']), v['q1_H'], v['q2_H'], v['Y'])
                 and pp == closed_form_score(int(v['A1'] == S), int(v['A2'] == v['pi_P2']), v['q1_P'], v['q2_P'],
                                             v['Y']) for v, ph, pp in base)
    cases = OrderedDict()
    for v, ph, pp in base:
        cases.setdefault(case_label(v), []).append((v, ph, pp))
    by_case = OrderedDict((k, OrderedDict(vertices=len(r), marginal_min=min(min(x[1], x[2]) for x in r),
                                          marginal_max=max(max(x[1], x[2]) for x in r),
                                          contrast_min=min(x[1] - x[2] for x in r),
                                          contrast_max=max(x[1] - x[2] for x in r))) for k, r in cases.items())
    fractional = []
    for fx in FRACTIONAL_FIXTURES:
        for a1, pi_h, pi_p, a2 in itertools.product(ACTIONS, repeat=4):
            ph = dr_score(nonabsorbed_trajectory(a1, a2, pi_h, fx['q1_H'], fx['off'][0], fx['q2_H'], fx['off'][1]),
                          fx['Y'])
            pp = dr_score(nonabsorbed_trajectory(a1, a2, pi_p, fx['q1_P'], fx['off'][2], fx['q2_P'], fx['off'][3]),
                          fx['Y'])
            case = case_label(dict(A1=a1, A2=a2, pi_H2=pi_h, pi_P2=pi_p))
            c = by_case[case]
            fractional.append(OrderedDict(
                fixture=OrderedDict((k, fx[k]) for k in ('q1_H', 'q1_P', 'q2_H', 'q2_P', 'Y')), off=fx['off'],
                A1=a1, A2=a2, pi_H2=pi_h, pi_P2=pi_p, phi_H=ph, phi_P=pp,
                closed_form_agrees=(ph == closed_form_score(int(a1 == S), int(a2 == pi_h), fx['q1_H'], fx['q2_H'],
                                                            fx['Y'])
                                    and pp == closed_form_score(int(a1 == S), int(a2 == pi_p), fx['q1_P'],
                                                                fx['q2_P'], fx['Y'])),
                within_case_vertex_range=(c['marginal_min'] <= min(ph, pp) and max(ph, pp) <= c['marginal_max']
                                          and c['contrast_min'] <= ph - pp <= c['contrast_max'])))
    after_first = enumerate_absorbed_after_first()
    after_first_invariant = all(enumerate_absorbed_after_first(off) == after_first
                                for off in itertools.product((0, 1), repeat=2))
    after_first_closed = all(ph == closed_form_absorbed_after_first(int(v['A1'] == S), v['q1_H'], v['Y'])
                             and pp == closed_form_absorbed_after_first(int(v['A1'] == S), v['q1_P'], v['Y'])
                             for v, ph, pp in after_first)
    from_start = enumerate_absorbed_from_start()
    return OrderedDict(
        nonabsorbed=OrderedDict(_range_summary(base), closed_form_agrees_everywhere=closed,
                                off_policy_nuisance_irrelevant=invariant, by_case=by_case),
        fractional_interior_fixtures=fractional,
        absorbed_after_first_action=OrderedDict(_range_summary(after_first), closed_form_agrees_everywhere=
                                                after_first_closed, off_policy_nuisance_irrelevant=
                                                after_first_invariant),
        absorbed_from_start=OrderedDict(_range_summary(from_start),
                                        score_equals_Y_everywhere=all(ph == pp == v['Y'] for v, ph, pp in from_start)))


def contrast_widths(score):
    """(fresh, offline, calibration) range widths: fresh outcomes lie in [0, 1]; the offline per-trajectory contrast
    extrema cover every path (hence any block average); calibration = offline - fresh."""
    lo = min(score[k]['contrast']['min'] for k in ('nonabsorbed', 'absorbed_after_first_action',
                                                     'absorbed_from_start'))
    hi = max(score[k]['contrast']['max'] for k in ('nonabsorbed', 'absorbed_after_first_action',
                                                     'absorbed_from_start'))
    fresh = (Fraction(-1), Fraction(1))
    offline = (lo, hi)
    calibration = (offline[0] - fresh[1], offline[1] - fresh[0])
    return OrderedDict(fresh_gain=fresh, offline_gain=offline, gain_calibration_discrepancy=calibration)


def score_coordinate_width(score):
    lo = min(score[k]['marginal']['min'] for k in ('nonabsorbed', 'absorbed_after_first_action',
                                                     'absorbed_from_start'))
    hi = max(score[k]['marginal']['max'] for k in ('nonabsorbed', 'absorbed_after_first_action',
                                                     'absorbed_from_start'))
    return lo, hi


# ------------------------------------------------------------------------------- 2. sufficient block counts

def _decimal(x, what):
    if isinstance(x, bool) or not isinstance(x, (int, str, Decimal)):
        raise AuditInputError('%s must be an int, decimal string or Decimal, got %r' % (what, x))
    d = Decimal(x)
    if not d.is_finite():
        raise AuditInputError('%s is not finite' % what)
    return d


def log_term(alpha, split):
    """ln(2 split / alpha) at 60 digits: Hoeffding at level alpha / split per bounded quantity."""
    a = _decimal(alpha, 'alpha')
    if not 0 < a < 1:
        raise AuditInputError('alpha must satisfy 0 < alpha < 1')
    with localcontext() as ctx:
        ctx.prec = PREC
        return (2 * Decimal(split) / a).ln()


def half_width(width, blocks, lt):
    """w sqrt(lt / (2 B)) at 60 digits."""
    if isinstance(blocks, bool) or not isinstance(blocks, int) or blocks < 1:
        raise AuditInputError('the block count must be a positive int')
    with localcontext() as ctx:
        ctx.prec = PREC
        return Decimal(width) * (lt / (2 * Decimal(blocks))).sqrt()


def sufficient_count(width, h, lt):
    """ceil(w^2 lt / (2 h^2)) at 60 digits, with the unrounded quotient."""
    h = _decimal(h, 'h')
    if not h > 0:
        raise AuditInputError('h must be positive')
    with localcontext() as ctx:
        ctx.prec = PREC
        q = Decimal(width) ** 2 * lt / (2 * h * h)
        return int(q.to_integral_value(rounding=ROUND_CEILING)), q


def float_sufficient_count(width, h, split, alpha):
    return math.ceil(width * width * math.log(2 * split / alpha) / (2 * h * h))


def _whole(x, what):
    """an exact range width that must be a whole number (the Decimal steps take integer widths)."""
    x = Fraction(x)
    if x.denominator != 1 or x <= 0:
        raise AuditInputError('%s = %s must be a positive whole number' % (what, x))
    return int(x)


def method_specs(widths, score_width):
    """the three methods: widths of each contrast's untruncated half-width multiplier and the alpha split."""
    score_width = _whole(score_width, 'score coordinate width')
    widths = OrderedDict((c, (widths[c][0], widths[c][1])) for c in CONTRASTS)

    def rect(cw):
        return OrderedDict((c, sum(abs(a) * w for a, w in zip(COEFFICIENTS[c], cw))) for c in CONTRASTS)
    tight = (score_width, score_width, 1, 1)
    return OrderedDict([
        ('direct_contrast', OrderedDict(label='Hoeffding on each complete-block contrast, alpha/3 each, union bound',
                                        split=3, widths=OrderedDict((c, _whole(widths[c][1] - widths[c][0],
                                                                               c + ' width')) for c in CONTRASTS))),
        ('rectangle_original', OrderedDict(label='four-coordinate rectangle, alpha/4 each, widths (13, 13, 1, 1), '
                                                 'propagated by coefficient signs', split=4,
                                           coordinate_widths=ORIGINAL_COORDINATE_WIDTHS,
                                           widths=rect(ORIGINAL_COORDINATE_WIDTHS))),
        ('rectangle_tightened', OrderedDict(label='four-coordinate rectangle, alpha/4 each, tightened widths '
                                                  '(%s, %s, 1, 1)' % (score_width, score_width), split=4,
                                            coordinate_widths=tight, widths=rect(tight))),
    ])


def count_tables(specs, alpha=ALPHA, half_widths=HALF_WIDTHS):
    out = OrderedDict()
    for name, spec in specs.items():
        lt = log_term(alpha, spec['split'])
        rows = OrderedDict()
        for h in half_widths:
            cells = OrderedDict()
            for c in CONTRASTS:
                w = spec['widths'][c]
                b, q = sufficient_count(w, h, lt)
                hw_b, hw_prev = half_width(w, b, lt), (half_width(w, b - 1, lt) if b > 1 else None)
                fb = float_sufficient_count(float(w), float(h), spec['split'], float(alpha))
                cells[c] = OrderedDict(width=w, B=b, quotient=q, half_width_at_B=hw_b, half_width_at_B_minus_1=hw_prev,
                                       straddles=hw_b <= h and (hw_prev is None or hw_prev > h), float_B=fb,
                                       float_agrees=fb == b)
            rows[str(h)] = OrderedDict(cells, all_three_B=max(cells[c]['B'] for c in CONTRASTS))
        out[name] = OrderedDict(label=spec['label'], log_term='ln(%d / alpha)' % (2 * spec['split']),
                                log_term_value=lt, rows=rows)
    return out


def block_trajectories(tasks, n_log, n_h, n_p):
    """J (n_log + n_H + n_P): trajectories in one complete block before training, baselines, retries or restoration."""
    for x, what in ((tasks, 'J'), (n_log, 'n_log'), (n_h, 'n_H'), (n_p, 'n_P')):
        if isinstance(x, bool) or not isinstance(x, int) or x < 1:
            raise AuditInputError('%s must be a positive int' % what)
    return tasks * (n_log + n_h + n_p)


def note_comparison(tables):
    direct = OrderedDict((h, tuple(tables['direct_contrast']['rows'][h][c]['B'] for c in CONTRASTS))
                         for h in NOTE_DIRECT_TABLE)
    rect = OrderedDict((m, tuple(tables[m]['rows']['0.05'][c]['B'] for c in CONTRASTS)) for m in NOTE_RECTANGLE_AT_05)
    per_block = block_trajectories(NOTE_J20['J'], NOTE_J20['n_log'], NOTE_J20['n_H'], NOTE_J20['n_P'])
    fresh = tables['direct_contrast']['rows']['0.05']['fresh_gain']['B'] * per_block
    simultaneous = tables['direct_contrast']['rows']['0.05']['all_three_B'] * per_block
    return OrderedDict(
        direct_table=direct, direct_table_matches_note=direct == OrderedDict((h, NOTE_DIRECT_TABLE[h])
                                                                             for h in NOTE_DIRECT_TABLE),
        rectangle_at_05=rect, rectangle_at_05_matches_note=rect == OrderedDict(NOTE_RECTANGLE_AT_05),
        j20=OrderedDict(NOTE_J20, trajectories_per_block=per_block, fresh_gain_at_05_computed=fresh,
                        simultaneous_at_05_computed=simultaneous,
                        matches_note=(fresh, simultaneous) == (NOTE_J20['fresh_gain_at_05'],
                                                               NOTE_J20['simultaneous_at_05'])))


def trajectory_costs(tables, tasks=20, n_log=1, n_h=1, n_p=1):
    per_block = block_trajectories(tasks, n_log, n_h, n_p)
    return OrderedDict(J=tasks, n_log=n_log, n_H=n_h, n_P=n_p, trajectories_per_block=per_block,
                       unit='trajectories (not tokens, seconds, prices, dollars or energy)',
                       costs=OrderedDict((m, OrderedDict((h, OrderedDict([(c, row[c]['B'] * per_block)
                                                                          for c in CONTRASTS]
                                                                         + [('all_three', row['all_three_B']
                                                                             * per_block)]))
                                                         for h, row in t['rows'].items()))
                                         for m, t in tables.items()))


# ---------------------------------------------------------------------------- 3. independent fixed groups

def _sequence(x, what):
    if isinstance(x, (str, bytes, dict)) or not isinstance(x, (list, tuple)):
        raise AuditInputError('%s must be a list or tuple, got %r' % (what, type(x).__name__))
    if not x:
        raise AuditInputError('%s must not be empty' % what)
    return x


def validate_weights(weights):
    """fixed nonnegative task-mass weights lambda_g summing exactly to one (converted exactly; pass Fractions when a
    float decimal such as 0.1 would not sum exactly)."""
    w = tuple(_exact(x, 'weight %d' % g) for g, x in enumerate(_sequence(weights, 'weights')))
    if any(x < 0 for x in w):
        raise AuditInputError('weights must be nonnegative')
    if sum(w) != 1:
        raise AuditInputError('weights must sum exactly to one, got %s' % sum(w))
    return w


def validate_counts(counts, groups):
    c = _sequence(counts, 'replicate counts')
    if len(c) != groups:
        raise AuditInputError('need %d replicate counts, got %d' % (groups, len(c)))
    for g, r in enumerate(c):
        if isinstance(r, bool) or not isinstance(r, int) or r < 1:
            raise AuditInputError('replicate count %d must be a positive int, got %r' % (g, r))
    return tuple(c)


def concentration_factor(weights, counts):
    """sum_g lambda_g^2 / R_g, exact."""
    w = validate_weights(weights)
    r = validate_counts(counts, len(w))
    return sum(x * x / n for x, n in zip(w, r))


def weighted_half_width(width, weights, counts, alpha=ALPHA, split=3):
    """h = w sqrt(ln(2 split / alpha) / 2 * sum_g lambda_g^2 / R_g) at 60 digits (split = 3 for the three contrasts)."""
    f = concentration_factor(weights, counts)
    lt = log_term(alpha, split)
    with localcontext() as ctx:
        ctx.prec = PREC
        return Decimal(width) * (lt / 2 * Decimal(f.numerator) / Decimal(f.denominator)).sqrt()


def _replicates(replicates, groups):
    reps = _sequence(replicates, 'replicates')
    if len(reps) != groups:
        raise AuditInputError('need replicate values for %d groups, got %d' % (groups, len(reps)))
    return tuple(tuple(_exact(x, 'group %d replicate %d' % (g, k)) for k, x in enumerate(_sequence(r, 'group %d' % g)))
                 for g, r in enumerate(reps))


def weighted_estimate(weights, replicates):
    """theta_hat = sum_g lambda_g (sum_r C_gr / R_g)."""
    w = validate_weights(weights)
    reps = _replicates(replicates, len(w))
    return sum(x * sum(r) / len(r) for x, r in zip(w, reps))


def weighted_variance(weights, counts, group_variances):
    """Var(theta_hat) = sum_g lambda_g^2 Var(C_g1) / R_g under independent replicates, identically distributed within
    each group."""
    w = validate_weights(weights)
    r = validate_counts(counts, len(w))
    v = _sequence(group_variances, 'group variances')
    if len(v) != len(w):
        raise AuditInputError('need %d group variances' % len(w))
    v = tuple(_exact(x, 'group variance %d' % g) for g, x in enumerate(v))
    if any(x < 0 for x in v):
        raise AuditInputError('group variances must be nonnegative')
    return sum(x * x * s / n for x, s, n in zip(w, v, r))


def within_group_variance_estimate(weights, replicates):
    """sum_g lambda_g^2 s_g^2 / R_g with the unbiased within-group sample variance s_g^2; refused when any group has
    R_g = 1 (one repetition gives no empirical within-group variance estimate and cannot justify Wald inference;
    between-group spread is not a substitute). The known-bound concentration factor and half-width do permit
    R_g = 1."""
    w = validate_weights(weights)
    reps = _replicates(replicates, len(w))
    if any(len(r) < 2 for r in reps):
        raise AuditInputError('every group needs R_g >= 2 replicates for a within-group variance estimate')
    total = Fraction(0)
    for x, r in zip(w, reps):
        m = sum(r) / len(r)
        total += x * x * (sum((c - m) ** 2 for c in r) / (len(r) - 1)) / len(r)
    return total


def balanced_replicates(total_count, tasks):
    """R = ceil(total / J) for J equally weighted groups, so that 1 / (J R) <= 1 / total."""
    for x, what in ((total_count, 'total count'), (tasks, 'J')):
        if isinstance(x, bool) or not isinstance(x, int) or x < 1:
            raise AuditInputError('%s must be a positive int' % what)
    return -(-total_count // tasks)


FINITE_GROUPS = dict(weights=(Fraction(1, 4), Fraction(3, 4)), counts=(2, 3),
                     laws=(((0, Fraction(1, 2)), (1, Fraction(1, 2))), ((-1, Fraction(2, 3)), (2, Fraction(1, 3)))))


def _law_moments(law):
    m = sum(Fraction(x) * p for x, p in law)
    return m, sum(Fraction(x) ** 2 * p for x, p in law) - m * m


def finite_distribution_check(spec=FINITE_GROUPS):
    """enumerate every replicate outcome of independent groups with heterogeneous means: E theta_hat, Var theta_hat
    and E of the within-group variance estimate against the formulas."""
    w, counts, laws = spec['weights'], spec['counts'], spec['laws']
    outcome_sets = [list(itertools.product(law, repeat=n)) for law, n in zip(laws, counts)]
    e = e2 = e_hat_var = Fraction(0)
    for combo in itertools.product(*outcome_sets):
        prob = Fraction(1)
        values = []
        for group in combo:
            values.append([x for x, _ in group])
            for _, p in group:
                prob *= p
        est = weighted_estimate(w, values)
        e += prob * est
        e2 += prob * est * est
        e_hat_var += prob * within_group_variance_estimate(w, values)
    moments = [_law_moments(law) for law in laws]
    formula_mean = sum(x * m for x, (m, _) in zip(w, moments))
    formula_var = weighted_variance(w, counts, [v for _, v in moments])
    return OrderedDict(weights=w, counts=counts, group_means=tuple(m for m, _ in moments),
                       group_variances=tuple(v for _, v in moments), enumerated_mean=e, formula_mean=formula_mean,
                       enumerated_variance=e2 - e * e, formula_variance=formula_var,
                       expected_within_group_variance_estimate=e_hat_var,
                       agree=(e == formula_mean and e2 - e * e == formula_var == e_hat_var))


def common_shock_counterexample(tasks=3, replicates=2, theta=(0, Fraction(1, 2), 1)):
    """C_gr = theta_g + U_r with one bounded shock U_r in {-1, +1} shared by every group in replicate r, equal
    weights and counts: the true variance is Var(U) / R, the independent-task calculation Var(U) / (J R)."""
    if len(theta) != tasks:
        raise AuditInputError('need one theta per task')
    w = tuple([Fraction(1, tasks)] * tasks)
    e = e2 = Fraction(0)
    for shocks in itertools.product((-1, 1), repeat=replicates):
        prob = Fraction(1, 2 ** replicates)
        est = weighted_estimate(w, [[Fraction(t) + u for u in shocks] for t in theta])
        e += prob * est
        e2 += prob * est * est
    true_var = e2 - e * e
    naive = weighted_variance(w, [replicates] * tasks, [1] * tasks)
    return OrderedDict(J=tasks, R=replicates, shock_values=(-1, 1), true_variance=true_var,
                       independent_task_variance=naive, understatement_factor=true_var / naive)


def independent_groups_audit():
    unequal = OrderedDict(weights=(Fraction(1, 2), Fraction(1, 3), Fraction(1, 6)), counts=(2, 3, 1))
    unequal['factor'] = concentration_factor(unequal['weights'], unequal['counts'])
    identity = []
    for j, r in ((1, 1), (3, 2), (20, 7)):
        f = concentration_factor([Fraction(1, j)] * j, [r] * j)
        identity.append(OrderedDict(J=j, R=r, factor=f, equals_one_over_JR=f == Fraction(1, j * r)))
    single = OrderedDict(weights=(Fraction(1, 2), Fraction(1, 2)), counts=(1, 1), width=2)
    single['factor'] = concentration_factor(single['weights'], single['counts'])
    single['half_width'] = weighted_half_width(single['width'], single['weights'], single['counts'])
    try:
        within_group_variance_estimate(single['weights'], [[0], [1]])
        single['within_group_variance_estimate'] = 'computed (unexpected)'
    except AuditInputError as e:
        single['within_group_variance_estimate'] = 'refused: %s' % e
    return OrderedDict(
        label='weighted Hoeffding over independent fixed groups (note Sec. 3); needs the stronger independence '
              'contract; no count, cost or feasibility comparison is made here',
        unequal_example=unequal, equal_weight_identity=identity, one_replicate_per_group=single,
        finite_distribution=finite_distribution_check(), common_shock=common_shock_counterexample())


# ------------------------------------------------------------------------------------------------ 4. record

ASSUMPTIONS = (
    'complete-block note contract: frozen bounded nuisance functions in [0, 1] fitted outside every scored block, '
    'valid logging marginals, terminal payoff Y in [0, 1]',
    'deterministic target routers sharing the initial action S; at most two eligible decisions; the logger chooses '
    'each of two actions with probability 1/2 at an eligible decision; an absorbed decision is a common no-op with '
    'probability one',
    'both target scores are evaluated on the same logged trajectory (unrelated marginal score samples do not get '
    'the contrast bound)',
    'Sec. 2 counts: independent identically distributed complete blocks (REQ-024 contract)',
    'Sec. 3: mutually independent group replicates, identically distributed within each group, with the same valid '
    'marginal execution laws; groups may differ in distribution and mean',
)
LIMITATIONS = (
    'deterministic analysis only: no empirical coverage, runtime independence, cost saving, practical precision or '
    'new agent result',
    'the vertex enumeration with the affine argument is a mathematical support calculation for this contract; '
    'stochastic targets, other propensities or horizons need their own bounds',
    'counts are worst-case sufficient bounds for untruncated half-widths, not necessary sample sizes, power '
    'calculations or limits on variance-adaptive methods',
    'the 60-digit Decimal values evaluate an exact analytic expression numerically; they are not outward-rounded '
    'interval certificates',
    'illustrative half-widths are not adopted effect, equivalence or noninferiority margins; J = 20 is arithmetic, '
    'not a frozen task list; trajectory counts are not tokens, time, prices, dollars or energy',
    'the independent-group identities need a stronger independence contract that task IDs, RNG labels or passing '
    'tests cannot establish',
    'R_g = 1 cannot estimate the empirical within-group variance or justify Wald inference (the variance estimate is '
    'refused), but the known-bound concentration factor and half-width DO permit R_g = 1',
    'the direct construction covers the three named contrasts only',
)


def sha256(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def audit():
    score = score_range_audit()
    widths = contrast_widths(score)
    lo, hi = score_coordinate_width(score)
    specs = method_specs(widths, hi - lo)
    tables = count_tables(specs)
    return OrderedDict(score_range=score, score_coordinate_range=(lo, hi), contrast_ranges=widths,
                       methods=specs, sufficient_counts=tables, note_comparison=note_comparison(tables),
                       j20_trajectory_costs=trajectory_costs(tables), independent_groups=independent_groups_audit())


def _jsonable(x):
    if isinstance(x, Fraction):
        return str(x)
    if isinstance(x, Decimal):
        return str(x)
    if isinstance(x, dict):
        return OrderedDict((str(k), _jsonable(v)) for k, v in x.items())
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    return x


def build_record():
    note_sha = sha256(NOTE)
    if note_sha != NOTE_SHA256:
        raise AuditInputError('the lead note changed: sha256 %s, pinned %s' % (note_sha, NOTE_SHA256))
    return _jsonable(OrderedDict(
        request='DTR-REQ-025', version=VERSION,
        status='deterministic analysis setup; no empirical coverage, runtime independence, cost saving or agent result',
        generated_utc=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        command=COMMAND, python=sys.version.split()[0], implementation=platform.python_implementation(),
        pins=OrderedDict(source=OrderedDict(path=SOURCE, sha256=sha256(SOURCE)),
                         tests=OrderedDict(path=TESTS, sha256=sha256(TESTS)),
                         note=OrderedDict(path=NOTE, sha256=note_sha, pinned=NOTE_SHA256,
                                          initial_request_sha256=NOTE_INITIAL_SHA256,
                                          amendment='references and real-agent covariance wording only; no '
                                                    'equation, number, test scope or cap changed (lead)')),
        numbers='exact rationals as "p/q" strings; Decimal values as strings at %d significant digits' % PREC,
        assumptions=ASSUMPTIONS, results=audit(), limitations=LIMITATIONS))


def write_record(path=OUT):
    """write the record as a new file; refuse to overwrite an existing one."""
    rec = build_record()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, 'x', encoding='utf-8') as f:
            json.dump(rec, f, indent=2)
            f.write('\n')
    except FileExistsError:
        raise AuditInputError('%s already exists; a completed record is never overwritten' % path) from None
    return rec


def main(argv):
    if argv == ['--write']:
        rec = write_record()
        print('wrote %s' % OUT.relative_to(ROOT))
    elif not argv:
        rec = _jsonable(audit())
    else:
        raise SystemExit('usage: precision_design_audit.py [--write]')
    res = rec['results'] if 'results' in rec else rec
    print(json.dumps(OrderedDict(score_coordinate_range=res['score_coordinate_range'],
                                 contrast_ranges=res['contrast_ranges'],
                                 note_comparison=res['note_comparison']), indent=1))


if __name__ == '__main__':
    main(sys.argv[1:])
