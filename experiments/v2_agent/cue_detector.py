"""DTR-REQ-005 (P0) recovery-cue detector: repeated-action detection over exact
(command, returncode, rendered observation) triples, exactly as specified by the lead review
docs/theory_feedback_20260923_completed_pilots.md ("Prioritized requests and acceptance criteria").

PURE / SIDE-EFFECT FREE. This module runs no model, server, container, evaluator or network call, writes
no file and mutates no caller object. It only decides WHETHER the single fixed cue is owed and records the
landmark; a caller in the NEW version/cohort namespace appends CUE_TEXT to the next normally budgeted
model call's messages. The detector never adds a model call, forces submission, terminates early, resets
context, alters tool output, or changes H=24, context, temperature or model pins. The frozen yaml-v1
execution sources (pilot_episode.py, pilot_runner.py, pilot_cohort.py) are NOT touched or imported here,
so results/v2_agent/pilot_20260922_yaml_v1/cohort_binding.json stays valid.

Detection contract (lead):
  * a record is an exact triple (command, returncode, rendered observation); it is COMPLETE only when all
    three are present and parsable AND the record's logical call id is a positive integer. A missing or
    unparsable observation, a missing return code, or an unusable call id makes the record INCOMPLETE.
  * 'AAA'    - three identical consecutive COMPLETE triples on three CONSECUTIVE logical calls.
  * 'ABABAB' - three repetitions of an ordered pair of two DISTINCT complete triples (A,B,A,B,A,B) on six
    CONSECUTIVE logical calls.
  * an INCOMPLETE record never compares equal to anything and is never skipped over: it breaks adjacency,
    so no window that needs its position can match.
  * CONSECUTIVE means consecutive in the recorded logical call ids, not merely adjacent in the list handed
    to the detector. A caller that drops an unparsable row (calls 1,2,4) therefore does NOT trigger, and
    the gap is published in `call_id_discontinuities`; duplicate ids (5,5,5) do not trigger either.
  * AT MOST ONE cue per episode, ever. Only the FIRST pattern completion in the sequence can trigger; the
    detector is silent for the rest of the episode afterwards.
  * the cue is owed to the NEXT normally budgeted call (trigger_call_id + 1). If no next call is allowed
    under the call horizon (H=24), the trigger is recorded WITHOUT delivery and NO cue text is ever handed
    out for that episode.
  * trigger means repeated VISIBLE feedback, not proven unchanged filesystem state.

Planned vs actual delivery are separate fields, because the lead's report is per pair on actual
"cue delivery" (docs:175-176) and on explicit no-delivery recording (docs:151):
  delivery_call_id   the call the single cue is SCHEDULED for (null when no next call remains)
  delivery_planned   mode delivers AND a scheduled call exists  -- a PLAN, not an observation
  delivered          the cue was ACTUALLY handed out by this detector instance (always false for the pure
                     scan(), which emits nothing by construction, and false on every instance landmark
                     taken before the emission)
  cue_emissions / cue_emitted / cue_emitted_call_ids   what was actually handed out, and to which call

Two modes over the SAME logic, so the baseline arm can run the detector silently (lead: "Run the same
detector silently in baseline and record its would-trigger landmark"):
  MODE_LIVE    - the landmark is recorded AND cue_for_call() hands CUE_TEXT out exactly once.
  MODE_OBSERVE - the identical landmark is recorded and NOTHING is ever emitted; model-visible messages
                 and endpoint bytes are unchanged.

No detector input can raise out of this module into an episode driver (lead: diagnostic instrumentation
must not alter or block the episode, docs:84). Malformed records degrade to INCOMPLETE and malformed cue
requests return None and are counted in `cue_requests_refused`. Only a programmer error in the detector's
own construction arguments (mode/horizon) raises, and that happens before any episode work.

Usage (retrospective fixtures or a silent baseline arm):
    landmark = cue_detector.scan(records, mode=cue_detector.MODE_OBSERVE)
Usage (live arm, one instance per episode):
    det = cue_detector.RepeatedActionCueDetector(mode=cue_detector.MODE_LIVE)
    det.observe(record)                     # after each recorded (command, returncode, observation)
    cue = det.cue_for_call(next_call_id)    # CUE_TEXT exactly once, or None
    det.landmark()                          # the record to publish for this episode
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

DETECTOR_ID = 'repeated-action-cue-v1'
MODE_LIVE = 'live'
MODE_OBSERVE = 'observe'
MODES = (MODE_LIVE, MODE_OBSERVE)
PATTERN_AAA = 'AAA'
PATTERN_ABABAB = 'ABABAB'
PATTERN_WIDTH = {PATTERN_AAA: 3, PATTERN_ABABAB: 6}
H_DEFAULT = 24           # mirrors the frozen pilot_episode.H; this module never changes the horizon
FIRST_LOGICAL_CALL = 1   # the frozen driver numbers logical calls from 1 (pilot_episode.py:165-174)

# The lead's cue, verbatim, as ONE text block (no internal line breaks, no reflowed words). The lead
# review renders the same words wrapped inside a markdown blockquote; the delivered text is this single
# block. Task-independent: no solution/file hint, no gold patch, no hidden-test information.
CUE_TEXT = 'Recent actions returned the same visible feedback repeatedly. Use the existing /testbed checkout. Choose a different action that will provide useful new evidence, or explain why repeating the action is necessary. Check the current working directory and the existing submission instructions.'
CUE_SHA256 = hashlib.sha256(CUE_TEXT.encode('utf-8')).hexdigest()
DETECTOR_SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

CALL_ID_KEYS = ('call_id', 'call')
OBSERVATION_ERROR_KEYS = ('observation_error', 'observation_parse_error', 'parse_error')

NO_PATTERN_REASON = 'no repeated-action pattern in the complete records observed'
TRIGGER_NOTE = 'trigger means repeated visible feedback, not proven unchanged state'

_ABSENT = object()


class _Unparsable:
    """Sentinel for an observation the harness could not parse/render (never equal to any observation)."""

    __slots__ = ()

    def __repr__(self):
        return 'UNPARSABLE'


UNPARSABLE = _Unparsable()


def _as_bytes(value):
    """Byte-exact identity: a str and its UTF-8 encoding are the same value; anything else is unparsable."""
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, str):
        return value.encode('utf-8')
    return None


def _positive_int(value):
    return not isinstance(value, bool) and isinstance(value, int) and value >= FIRST_LOGICAL_CALL


def record_triple(record):
    """(key, reason). key = (command bytes, returncode int, observation bytes) for a COMPLETE record;
    (None, reason) for an INCOMPLETE one. No whitespace normalisation, no shell parsing, no timestamp
    normalisation: identity is exact on the command and the rendered observation bytes the agent was
    shown, matching the frozen repetition-analysis convention."""
    if isinstance(record, Mapping):
        if any(record.get(key) for key in OBSERVATION_ERROR_KEYS):
            return None, 'observation recorded as unparsable'
        command = record.get('command', _ABSENT)
        returncode = record.get('returncode', _ABSENT)
        observation = record.get('observation', _ABSENT)
    elif isinstance(record, (tuple, list)) and len(record) == 3:
        command, returncode, observation = record
    else:
        return None, 'record is not a (command, returncode, observation) triple'
    if command is _ABSENT or command is None:
        return None, 'missing command'
    command_bytes = _as_bytes(command)
    if command_bytes is None:
        return None, 'unparsable command'
    if returncode is _ABSENT or returncode is None:
        return None, 'missing returncode'
    if isinstance(returncode, bool) or not isinstance(returncode, int):
        return None, 'non-integer returncode treated as missing'
    if observation is _ABSENT or observation is None or observation is UNPARSABLE:
        return None, 'missing or unparsable observation'
    observation_bytes = _as_bytes(observation)
    if observation_bytes is None:
        return None, 'missing or unparsable observation'
    return (command_bytes, returncode, observation_bytes), None


def record_call_id(record, position):
    """(call_id, reason). The record's own logical call id when it carries a usable one, else its 1-based
    position in the sequence. An unusable declared call id NEVER raises: it returns (None, reason) and the
    record degrades to INCOMPLETE, because instrumentation must not block the episode."""
    if isinstance(record, Mapping):
        for key in CALL_ID_KEYS:
            if key in record:
                value = record[key]
                if not _positive_int(value):
                    return None, ('unusable logical call id %r: the frozen driver numbers logical calls '
                                  'from %d' % (value, FIRST_LOGICAL_CALL))
                return value, None
    return position, None


def first_pattern(keys, ids):
    """(pattern, end_index) of the FIRST completion in key order, else (None, None).

    keys[i] is None for an INCOMPLETE record: such a position can neither match nor be skipped, so it
    breaks adjacency. ids[i] is the record's logical call id (None when unusable). A window matches only
    when its call ids are CONSECUTIVE integers, so a dropped record or a duplicate id cannot fabricate a
    pattern out of nonadjacent calls."""
    def window(start, end):
        if any(keys[j] is None or ids[j] is None for j in range(start, end + 1)):
            return None
        if any(ids[j + 1] != ids[j] + 1 for j in range(start, end)):
            return None
        return [keys[j] for j in range(start, end + 1)]

    for i in range(len(keys)):
        w = window(i - 2, i) if i >= 2 else None
        if w is not None and w[0] == w[1] == w[2]:
            return PATTERN_AAA, i                          # checked first; it needs the fewest records
        w = window(i - 5, i) if i >= 5 else None
        if w is not None and w[0] == w[2] == w[4] and w[1] == w[3] == w[5] and w[0] != w[1]:
            return PATTERN_ABABAB, i
    return None, None


def call_id_discontinuities(ids, positions=None):
    """Every place where the recorded logical call ids are not consecutive. Published so a landmark can
    never silently present 'three consecutive surviving records' as three consecutive calls."""
    out = []
    for i in range(1, len(ids)):
        previous, current = ids[i - 1], ids[i]
        if previous is None or current is None or current != previous + 1:
            out.append(dict(after_position=i, next_position=i + 1, after_call_id=previous,
                            next_call_id=current))
    return out


def scan(records, *, mode=MODE_LIVE, horizon=H_DEFAULT):
    """Pure recorder/planner over an ordered sequence of records. Returns the episode landmark; emits
    nothing, writes nothing and does not mutate `records`.

    `delivered` is always False here: scan() hands nothing out. The PLAN is `delivery_call_id` /
    `delivery_planned`; the single cue itself is handed out (once) by
    RepeatedActionCueDetector.cue_for_call in live use.

    Raises ValueError only for a bad mode or horizon, which are the detector's own construction
    arguments. No record content can raise."""
    if mode not in MODES:
        raise ValueError('mode must be one of %r, got %r' % (MODES, mode))
    if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon < 1:
        raise ValueError('horizon must be a positive integer, got %r' % (horizon,))
    records = list(records)
    keys, ids, incomplete = [], [], []
    for position, record in enumerate(records, start=FIRST_LOGICAL_CALL):
        key, reason = record_triple(record)
        call_id, id_reason = record_call_id(record, position)
        if id_reason is not None:
            key, reason = None, id_reason
        keys.append(key)
        ids.append(call_id)
        if key is None:
            incomplete.append(dict(call_id=call_id, position=position, reason=reason))
    pattern, end = first_pattern(keys, ids)
    landmark = dict(detector=DETECTOR_ID, detector_source_sha256=DETECTOR_SOURCE_SHA256, mode=mode,
                    horizon=horizon, records_observed=len(records), triggered=pattern is not None,
                    pattern=pattern, trigger_call_id=None, trigger_position=None, delivery_call_id=None,
                    delivery_planned=False, delivered=False, cue_emissions=0, cue_emitted=False,
                    cue_emitted_call_ids=[], cue_requests_refused=[],
                    cue_text=None, cue_sha256=None, pattern_call_ids=[],
                    incomplete_call_ids=[row['call_id'] for row in incomplete], incomplete_records=incomplete,
                    call_id_discontinuities=call_id_discontinuities(ids),
                    reason=NO_PATTERN_REASON, note=TRIGGER_NOTE)
    if pattern is None:
        return landmark
    width = PATTERN_WIDTH[pattern]
    trigger_call_id = ids[end]
    next_call_id = trigger_call_id + 1
    delivery_call_id = next_call_id if FIRST_LOGICAL_CALL <= next_call_id <= horizon else None
    if delivery_call_id is None:
        reason = ('no next normally budgeted model call remains: trigger on call %d of horizon H=%d; '
                  'trigger recorded without delivery and no cue text is handed out'
                  % (trigger_call_id, horizon))
    elif mode == MODE_OBSERVE:
        reason = ('observe-only baseline: would-trigger landmark recorded, no cue emitted and no '
                  'model-visible message changed')
    else:
        reason = ('one cue scheduled for call %d, the next normally budgeted model call; delivery is '
                  'recorded separately when it actually happens' % delivery_call_id)
    landmark.update(pattern=pattern, trigger_call_id=trigger_call_id, trigger_position=end + 1,
                    delivery_call_id=delivery_call_id,
                    delivery_planned=mode == MODE_LIVE and delivery_call_id is not None,
                    cue_text=CUE_TEXT, cue_sha256=CUE_SHA256,
                    pattern_call_ids=ids[end - width + 1:end + 1], reason=reason)
    return landmark


class RepeatedActionCueDetector:
    """One instance per episode. Stateful only in the sequence it was shown and in whether the single cue
    was already handed out; all detection is delegated to scan(). Never performs I/O."""

    def __init__(self, *, mode=MODE_LIVE, horizon=H_DEFAULT):
        scan((), mode=mode, horizon=horizon)          # validate the arguments before any episode work
        self.mode = mode
        self.horizon = horizon
        self._records = []
        self._emitted_call_ids = []
        self._refused = []

    def observe(self, record):
        """Record one (command, returncode, observation) triple in order; returns the current landmark."""
        self._records.append(record)
        return self.landmark()

    def observe_all(self, records):
        for record in records:
            self.observe(record)
        return self.landmark()

    def _refuse(self, call_id, reason):
        self._refused.append(dict(requested_call_id=call_id if _positive_int(call_id) else str(call_id)[:64],
                                  reason=reason))
        return None

    def cue_for_call(self, call_id):
        """CUE_TEXT exactly once, and only in live mode for the scheduled delivery call; otherwise None.

        Never raises. A refused request is counted in the landmark's `cue_requests_refused`."""
        if self.mode != MODE_LIVE:
            return None                                # observe-only baseline emits nothing, ever
        if self._emitted_call_ids:
            return None                                # at most one cue per episode, ever
        if not _positive_int(call_id):
            return self._refuse(call_id, 'a cue is only ever handed to a positive integer logical call id')
        landmark = scan(self._records, mode=self.mode, horizon=self.horizon)
        if not landmark['triggered']:
            return None
        if landmark['delivery_call_id'] is None:
            return self._refuse(call_id, 'trigger recorded without delivery: no next normally budgeted '
                                         'model call remains under the horizon')
        if landmark['delivery_call_id'] != call_id:
            return None
        self._emitted_call_ids.append(call_id)
        return CUE_TEXT

    def landmark(self):
        """The scan() landmark plus what this instance ACTUALLY emitted."""
        landmark = scan(self._records, mode=self.mode, horizon=self.horizon)
        landmark.update(cue_emissions=len(self._emitted_call_ids), cue_emitted=bool(self._emitted_call_ids),
                        cue_emitted_call_ids=list(self._emitted_call_ids),
                        cue_requests_refused=[dict(row) for row in self._refused],
                        delivered=bool(self._emitted_call_ids))
        return landmark
