"""DTR-REQ-005 cohort registry for the next controlled DEV comparison ('cue-v1').

A NEW version/cohort namespace, exactly as the lead requires (docs/theory_feedback_20260923_completed_pilots.md,
"Next controlled DEV comparison, planned and held"). pilot_cohort.py is NOT touched or imported: it hashes
pilot_episode/pilot_runner/pilot_cohort into results/v2_agent/pilot_20260922_yaml_v1/cohort_binding.json, so
yaml-v1's frozen execution sources and archives stay exactly as published.

This module is a registry and nothing else. It creates no directory, writes no episode record, dispatches
nothing and imports no runtime: it only states the cohort name, its output directory and the FROZEN
12-assignment frame so the list and its order can be reviewed before release.

The frame, verbatim from the lead:
  * the three already exposed diagnostic tasks `psf__requests-1142`, `scikit-learn__scikit-learn-10297`,
    `sympy__sympy-11618` -- a deliberately selected diagnostic frame, not a new benchmark sample;
  * both existing pinned backends (small, large);
  * one instrumentation-only (baseline) episode and one cue episode per task/backend: 12 total, with no
    replacement, repeat or extension;
  * order fixed lexicographically by task and then small/large, with the within-pair order
    B,C,C,B,B,C (B = baseline first, C = cue first), which balances overall order without making it
    identical to backend;
  * the same detector runs in BOTH arms; the baseline arm runs it silently (observe) and records its
    would-trigger landmark, so baseline model-visible messages and endpoint bytes are unchanged;
  * all 12 assignments stay in operational endpoint accounting, not only triggered pairs;
  * maximum 576 physical requests (12 x H24 x two attempts). H=24, context, temperature and the model pins
    are unchanged; this module changes none of them.

It is a fixed-order DESCRIPTIVE comparison, not a randomized causal effect estimate, and no episode may run
before the lead reviews the frozen list, sources, limits and fixtures.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COHORT = 'cue-v1'
COHORTS = {COHORT: 'pilot_20260923_cue_v1'}
DETECTOR_BINDING = 'repeated-action-cue-v1'
CAPTURE_BINDING = 'xc1'                      # exit_capture.py, the all-exit diagnostic
RECEIPT_REQUEST = 'DTR-REQ-005'

# Lexicographic by task, exactly as the lead fixed it; asserted in the fixtures rather than sorted here.
TASKS = ('psf__requests-1142', 'scikit-learn__scikit-learn-10297', 'sympy__sympy-11618')
BACKENDS = ('small', 'large')
ARM_BASELINE = 'baseline'
ARM_CUE = 'cue'
ARMS = (ARM_BASELINE, ARM_CUE)
MODE_BY_ARM = {ARM_BASELINE: 'observe', ARM_CUE: 'live'}
BASELINE_FIRST = 'B'
CUE_FIRST = 'C'
PAIR_ORDER = (BASELINE_FIRST, CUE_FIRST, CUE_FIRST, BASELINE_FIRST, BASELINE_FIRST, CUE_FIRST)

H = 24                                       # unchanged; a different H would be a new version/cohort
ATTEMPTS_PER_CALL = 2
MAX_PHYSICAL_REQUESTS = 576                  # 12 assignments x H24 x two physical attempts
N_ASSIGNMENTS = 12

ARM_DECLARATIONS = {
    ARM_BASELINE: ('instrumentation only: the detector runs silently and its would-trigger landmark is '
                   'recorded; no cue is emitted and no model-visible message or endpoint byte changes'),
    ARM_CUE: ('one fixed cue appended before the next normally budgeted model call after the first trigger; '
              'nothing else about the episode changes'),
}
PLAN_NOTES = (
    'a deliberately selected diagnostic frame of already exposed tasks, not a new benchmark sample',
    'a fixed-order descriptive comparison, not a randomized causal effect estimate and not a power claim',
    'no replacement, repeat or extension; unfinished assignments stay incomplete',
    'all 12 assignments are retained in operational endpoint accounting, not only triggered pairs',
    'H=24, context, temperature, the endpoint and the model pins are unchanged by this cohort',
    'held: no episode runs before the lead reviews this frozen list, the sources, the limits and the fixtures',
)


def cohort_output(name=COHORT):
    """The cohort's output directory. This function never creates it and never writes anything."""
    return ROOT / 'results/v2_agent' / COHORTS[name]


def output_dir_relative(name=COHORT):
    return 'results/v2_agent/' + COHORTS[name]


def arms_for_pair(letter):
    """The within-pair order: 'B' runs baseline first, 'C' runs the cue episode first."""
    if letter == BASELINE_FIRST:
        return (ARM_BASELINE, ARM_CUE)
    if letter == CUE_FIRST:
        return (ARM_CUE, ARM_BASELINE)
    raise ValueError('within-pair order must be %r or %r, got %r' % (BASELINE_FIRST, CUE_FIRST, letter))


def assignment_id(instance_id, backend, arm):
    return '%s__%s__%s__%s' % (instance_id, backend, COHORT, arm)


def assignments():
    """The 12 assignments in FROZEN order, each with its arm label.

    Order: lexicographic by task, then small before large, then the pair's own B/C order."""
    if len(PAIR_ORDER) != len(TASKS) * len(BACKENDS):
        raise ValueError('the within-pair order must carry one letter per task/backend pair')
    rows, position, pair_index = [], 0, 0
    for instance_id in TASKS:
        for backend in BACKENDS:
            pair_index += 1
            letter = PAIR_ORDER[pair_index - 1]
            for within_pair_position, arm in enumerate(arms_for_pair(letter), start=1):
                position += 1
                rows.append(dict(position=position, instance_id=instance_id, backend=backend, arm=arm,
                                 assignment_id=assignment_id(instance_id, backend, arm),
                                 detector_mode=MODE_BY_ARM[arm], pair_index=pair_index, pair_order=letter,
                                 within_pair_position=within_pair_position,
                                 arm_declaration=ARM_DECLARATIONS[arm]))
    if len(rows) != N_ASSIGNMENTS:
        raise ValueError('the frozen frame is %d assignments, not %d' % (N_ASSIGNMENTS, len(rows)))
    return tuple(rows)


def frozen_plan():
    """The whole reviewable plan plus its own digest, so the lead can freeze this exact list and order."""
    payload = dict(request=RECEIPT_REQUEST, cohort=COHORT, output_dir=output_dir_relative(),
                   tasks=list(TASKS), backends=list(BACKENDS), arms=list(ARMS), pair_order=list(PAIR_ORDER),
                   n_assignments=N_ASSIGNMENTS, horizon_h=H, attempts_per_call=ATTEMPTS_PER_CALL,
                   max_physical_requests=MAX_PHYSICAL_REQUESTS, detector=DETECTOR_BINDING,
                   exit_capture_binding=CAPTURE_BINDING, arm_declarations=dict(ARM_DECLARATIONS),
                   notes=list(PLAN_NOTES), status='planned and held pending lead review; no episode has run',
                   assignments=[dict(row) for row in assignments()])
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'),
                                       ensure_ascii=False).encode()).hexdigest()
    return dict(payload, plan_sha256=digest)
