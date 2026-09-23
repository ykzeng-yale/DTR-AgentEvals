"""Deterministic fixtures for the DTR-REQ-005 repeated-action cue detector and its retrospective
trajectory adapter (no model, server, container, evaluator or network call; the archived episodes are read
read-only and never rewritten).

Covers the lead's acceptance list for the detector itself: AAA, ABABAB, nonrepeat, changed return code,
changed observation text, missing/unparsable observations (no trigger and no skipping), one-cue maximum,
final-call trigger WITHOUT delivery, the silent baseline landmark, explicit logical call ids (dropped
records, duplicate ids, unusable ids), planned-vs-actual delivery, and the 32 archived episodes of
`4927adc` as retrospective fixtures.

Every expectation below is written out BY HAND in literal form: pattern names, call ids, booleans, the cue
text, its digest, and the exact reason strings the published landmark will carry. Nothing here recomputes
the module's detection or its digest derivation, so a defect in cue_detector.py cannot be cancelled by the
same defect in this file. The cue text is additionally anchored to the lead review document itself.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/v2_agent'))
import cue_detector as CD  # noqa: E402
import trajectory_triples as TT  # noqa: E402

LEAD_REVIEW = ROOT / 'docs/theory_feedback_20260923_completed_pilots.md'
ARCHIVES = ROOT / 'results/v2_agent'
COHORT_DIRS = ('pilot_20260922', 'pilot_20260922_yaml_v1')

# The lead's cue, typed out independently of the module, and its digest as a hand-written literal
# (`shasum -a 256` over the exact 290 bytes). Neither value is derived from cue_detector here.
LEAD_CUE = 'Recent actions returned the same visible feedback repeatedly. Use the existing /testbed checkout. Choose a different action that will provide useful new evidence, or explain why repeating the action is necessary. Check the current working directory and the existing submission instructions.'
LEAD_CUE_SHA256 = '80d52625bd593cd6fecafeb06daca898792979592272d9fadcf0ddd04bd39d9e'

# The exact reason strings the published landmark carries, written out by hand.
REASON_NO_PATTERN = 'no repeated-action pattern in the complete records observed'
REASON_SCHEDULED_4 = ('one cue scheduled for call 4, the next normally budgeted model call; delivery is '
                      'recorded separately when it actually happens')
REASON_NO_DELIVERY_24 = ('no next normally budgeted model call remains: trigger on call 24 of horizon '
                         'H=24; trigger recorded without delivery and no cue text is handed out')
REASON_OBSERVE = ('observe-only baseline: would-trigger landmark recorded, no cue emitted and no '
                  'model-visible message changed')
REFUSAL_NO_DELIVERY = ('trigger recorded without delivery: no next normally budgeted model call remains '
                       'under the horizon')
REFUSAL_BAD_CALL_ID = 'a cue is only ever handed to a positive integer logical call id'

# One repeated triple as the archived episodes show it: same command, same return code, byte-identical
# rendered observation.
A = dict(command='ls -a', returncode=0, observation='<returncode>0</returncode>\n<output>\n.  ..  setup.py\n</output>')
B = dict(command='cat missing.py', returncode=1, observation='<returncode>1</returncode>\n<output>\ncat: missing.py: No such file or directory\n</output>')


def lead_cue_from_the_review():
    """Rebuild the cue from the lead review's own markdown blockquote, independently of the module."""
    lines, collecting = [], False
    for line in LEAD_REVIEW.read_text().splitlines():
        if line.startswith('> Recent actions returned'):
            collecting = True
        elif collecting and not line.startswith('> '):
            break
        if collecting:
            lines.append(line[2:].strip())
    return ' '.join(lines)


def test_cue_text_is_the_lead_blockquote_and_its_digest_is_a_hand_written_literal():
    assert lead_cue_from_the_review() == LEAD_CUE          # the document says exactly this
    assert CD.CUE_TEXT == LEAD_CUE                         # and the module delivers exactly that
    assert CD.CUE_SHA256 == LEAD_CUE_SHA256                # hand-written digest, not recomputed here
    assert len(CD.CUE_TEXT) == 290                         # hand-counted single text block
    assert len(CD.CUE_TEXT.encode('utf-8')) == 290
    assert '\n' not in CD.CUE_TEXT                         # one block, wording and punctuation unreflowed
    for forbidden in ('gold', 'patch', 'hidden', 'test file', 'submit now'):
        assert forbidden not in CD.CUE_TEXT.lower()        # task-independent: no solution/test hint


# ---------------------------------------------------------------- the lead's acceptance patterns

def test_three_identical_consecutive_triples_trigger_aaa():
    records = [dict(A), dict(A), dict(A)]
    landmark = CD.scan(records, mode='live', horizon=24)
    assert landmark['triggered'] is True
    assert landmark['pattern'] == 'AAA'
    assert landmark['trigger_call_id'] == 3
    assert landmark['delivery_call_id'] == 4
    assert landmark['delivery_planned'] is True            # a PLAN
    assert landmark['delivered'] is False                  # scan() hands nothing out, ever
    assert landmark['cue_emissions'] == 0
    assert landmark['cue_emitted_call_ids'] == []
    assert landmark['pattern_call_ids'] == [1, 2, 3]
    assert landmark['trigger_position'] == 3
    assert landmark['incomplete_call_ids'] == []
    assert landmark['call_id_discontinuities'] == []
    assert landmark['cue_text'] == LEAD_CUE
    assert landmark['cue_sha256'] == LEAD_CUE_SHA256
    assert landmark['reason'] == REASON_SCHEDULED_4
    assert landmark['note'] == 'trigger means repeated visible feedback, not proven unchanged state'

    detector = CD.RepeatedActionCueDetector(mode='live', horizon=24)
    detector.observe_all(records)
    assert detector.landmark()['delivered'] is False       # nothing delivered yet
    assert detector.cue_for_call(3) is None                # never before the trigger's own call
    assert detector.cue_for_call(4) == LEAD_CUE            # exactly the next normally budgeted call
    assert detector.cue_for_call(5) is None
    assert detector.landmark()['cue_emitted_call_ids'] == [4]
    assert detector.landmark()['cue_emissions'] == 1
    assert detector.landmark()['delivered'] is True        # now, and only now
    assert detector.landmark()['delivery_planned'] is True


def test_three_repetitions_of_an_ordered_pair_trigger_ababab():
    records = [dict(A), dict(B), dict(A), dict(B), dict(A), dict(B)]
    landmark = CD.scan(records, mode='live', horizon=24)
    assert landmark['triggered'] is True
    assert landmark['pattern'] == 'ABABAB'
    assert landmark['trigger_call_id'] == 6
    assert landmark['delivery_call_id'] == 7
    assert landmark['delivered'] is False
    assert landmark['delivery_planned'] is True
    assert landmark['pattern_call_ids'] == [1, 2, 3, 4, 5, 6]
    assert landmark['cue_sha256'] == LEAD_CUE_SHA256

    # Two and a half repetitions (A,B,A,B,A) are not three repetitions.
    short = CD.scan([dict(A), dict(B), dict(A), dict(B), dict(A)], mode='live', horizon=24)
    assert short['triggered'] is False
    assert short['pattern'] is None
    assert short['trigger_call_id'] is None
    assert short['reason'] == REASON_NO_PATTERN

    # A pair of two EQUAL triples is AAA, never ABABAB (A != B is required).
    same = CD.scan([dict(A)] * 6, mode='live', horizon=24)
    assert same['pattern'] == 'AAA'
    assert same['trigger_call_id'] == 3

    detector = CD.RepeatedActionCueDetector(mode='live', horizon=24)
    detector.observe_all(records)
    assert detector.cue_for_call(7) == LEAD_CUE
    assert detector.cue_for_call(8) is None
    assert detector.landmark()['delivered'] is True


def test_a_nonrepeating_sequence_never_triggers():
    records = [dict(command='ls -a', returncode=0, observation='listing'),
               dict(command='cat setup.py', returncode=0, observation='setup'),
               dict(command='grep -rn distance .', returncode=0, observation='hits'),
               dict(command='python -c "import sympy"', returncode=0, observation=''),
               dict(command='sed -n 1,20p sympy/geometry/point.py', returncode=0, observation='source'),
               dict(command='echo done', returncode=0, observation='done')]
    landmark = CD.scan(records, mode='live', horizon=24)
    assert landmark['triggered'] is False
    assert landmark['pattern'] is None
    assert landmark['trigger_call_id'] is None
    assert landmark['delivery_call_id'] is None
    assert landmark['delivery_planned'] is False
    assert landmark['delivered'] is False
    assert landmark['cue_text'] is None
    assert landmark['cue_sha256'] is None
    assert landmark['records_observed'] == 6
    assert landmark['reason'] == REASON_NO_PATTERN

    detector = CD.RepeatedActionCueDetector(mode='live', horizon=24)
    detector.observe_all(records)
    assert [detector.cue_for_call(call_id) for call_id in (1, 2, 3, 4, 5, 6, 7)] == [None] * 7
    assert detector.landmark()['cue_emitted'] is False
    assert detector.landmark()['cue_requests_refused'] == []


def test_a_changed_return_code_never_triggers():
    records = [dict(command='python -m pytest -q', returncode=0, observation='same visible output'),
               dict(command='python -m pytest -q', returncode=1, observation='same visible output'),
               dict(command='python -m pytest -q', returncode=2, observation='same visible output')]
    landmark = CD.scan(records, mode='live', horizon=24)
    assert landmark['triggered'] is False
    assert landmark['pattern'] is None
    assert landmark['trigger_call_id'] is None
    assert landmark['delivered'] is False
    assert landmark['incomplete_call_ids'] == []      # all three records are complete, just not identical


def test_a_changed_observation_text_never_triggers():
    records = [dict(command='ls -a', returncode=0, observation='.  ..  setup.py'),
               dict(command='ls -a', returncode=0, observation='.  ..  setup.py  build'),
               dict(command='ls -a', returncode=0, observation='.  ..  setup.py  build  dist')]
    landmark = CD.scan(records, mode='live', horizon=24)
    assert landmark['triggered'] is False
    assert landmark['pattern'] is None
    assert landmark['delivery_call_id'] is None

    # Byte-exactness: a whitespace-only difference is a different observation.
    whitespace = CD.scan([dict(command='ls -a', returncode=0, observation='a b'),
                          dict(command='ls -a', returncode=0, observation='a  b'),
                          dict(command='ls -a', returncode=0, observation='a b')], mode='live', horizon=24)
    assert whitespace['triggered'] is False


def test_a_str_observation_and_its_utf8_bytes_are_the_same_visible_feedback():
    mixed = [dict(command='ls -a', returncode=0, observation='café\n'),
             dict(command='ls -a', returncode=0, observation='café\n'.encode('utf-8')),
             dict(command='ls -a', returncode=0, observation=bytearray('café\n'.encode('utf-8')))]
    landmark = CD.scan(mixed, mode='live', horizon=24)
    assert landmark['pattern'] == 'AAA'
    assert landmark['trigger_call_id'] == 3
    # a byte string that is NOT the same bytes is not the same observation
    other = CD.scan([dict(command='ls -a', returncode=0, observation=b'cafe\n'),
                     dict(command='ls -a', returncode=0, observation='café\n'),
                     dict(command='ls -a', returncode=0, observation=b'cafe\n')], mode='live', horizon=24)
    assert other['triggered'] is False


def test_a_three_element_sequence_is_an_accepted_record_form():
    triple = ('ls -a', 0, 'out A')
    landmark = CD.scan([triple, list(triple), ('ls -a', 0, 'out A')], mode='live', horizon=24)
    assert landmark['pattern'] == 'AAA'
    assert landmark['trigger_call_id'] == 3
    assert landmark['delivery_call_id'] == 4
    assert landmark['incomplete_call_ids'] == []
    two = CD.scan([('ls -a', 0), ('ls -a', 0), ('ls -a', 0)], mode='live', horizon=24)
    assert two['triggered'] is False
    assert two['incomplete_call_ids'] == [1, 2, 3]
    assert [row['reason'] for row in two['incomplete_records']] == [
        'record is not a (command, returncode, observation) triple'] * 3


# ---------------------------------------------------------------- incomplete records

@pytest.mark.parametrize('third,reason', [
    (dict(command='ls -a', returncode=0, observation=None), 'missing or unparsable observation'),
    (dict(command='ls -a', returncode=0, observation=CD.UNPARSABLE), 'missing or unparsable observation'),
    (dict(command='ls -a', returncode=0, observation=17), 'missing or unparsable observation'),
    (dict(command='ls -a', returncode=0, observation='.  ..  setup.py', observation_error='render failed'),
     'observation recorded as unparsable'),
    (dict(command='ls -a', observation='.  ..  setup.py'), 'missing returncode'),
    (dict(command='ls -a', returncode=None, observation='.  ..  setup.py'), 'missing returncode'),
    (dict(command='ls -a', returncode='0', observation='.  ..  setup.py'),
     'non-integer returncode treated as missing'),
    (dict(command='ls -a', returncode=True, observation='.  ..  setup.py'),
     'non-integer returncode treated as missing'),
    (dict(returncode=0, observation='.  ..  setup.py'), 'missing command'),
    (dict(command=17, returncode=0, observation='.  ..  setup.py'), 'unparsable command'),
    ('trajectory row that is not a triple', 'record is not a (command, returncode, observation) triple'),
    (None, 'record is not a (command, returncode, observation) triple'),
])
def test_incomplete_records_never_trigger_and_are_never_skipped(third, reason):
    # Positions 1, 2 and 4 are the identical complete triple A. Skipping position 3 would fabricate AAA;
    # treating position 3 as equal to A would too. Neither is allowed.
    records = [dict(A), dict(A), third, dict(A)]
    landmark = CD.scan(records, mode='live', horizon=24)
    assert landmark['triggered'] is False
    assert landmark['pattern'] is None
    assert landmark['trigger_call_id'] is None
    assert landmark['delivery_call_id'] is None
    assert landmark['delivery_planned'] is False
    assert landmark['delivered'] is False
    assert landmark['cue_text'] is None
    assert landmark['incomplete_call_ids'] == [3]
    assert landmark['incomplete_records'] == [dict(call_id=3, position=3, reason=reason)]
    assert landmark['records_observed'] == 4

    detector = CD.RepeatedActionCueDetector(mode='live', horizon=24)
    detector.observe_all(records)
    assert [detector.cue_for_call(call_id) for call_id in (3, 4, 5)] == [None, None, None]
    assert detector.landmark()['cue_emissions'] == 0


def test_record_triple_and_record_call_id_report_their_own_verdicts():
    assert CD.record_triple(dict(command='ls -a', returncode=0, observation='out')) == (
        (b'ls -a', 0, b'out'), None)
    assert CD.record_triple(dict(command='ls -a', returncode=-9, observation=b'out')) == (
        (b'ls -a', -9, b'out'), None)
    assert CD.record_triple(dict(command='ls -a', returncode=0)) == (None, 'missing or unparsable observation')
    assert CD.record_call_id(dict(call=7, command='ls'), 3) == (7, None)
    assert CD.record_call_id(dict(call_id=7), 3) == (7, None)
    assert CD.record_call_id(dict(command='ls'), 3) == (3, None)
    assert CD.record_call_id(dict(call='1'), 3) == (
        None, "unusable logical call id '1': the frozen driver numbers logical calls from 1")
    assert CD.record_call_id(dict(call=0), 3) == (
        None, 'unusable logical call id 0: the frozen driver numbers logical calls from 1')
    assert CD.record_call_id(dict(call=None), 3) == (
        None, 'unusable logical call id None: the frozen driver numbers logical calls from 1')


# ---------------------------------------------------------------- explicit logical call ids

def test_a_dropped_record_cannot_fabricate_three_consecutive_calls():
    # The caller filtered out call 3 (unparsable feedback). Calls 1, 2 and 4 carry the identical triple.
    # 'Three consecutive calls' must not be read off three consecutive SURVIVING records.
    records = [dict(A, call=1), dict(A, call=2), dict(A, call=4)]
    landmark = CD.scan(records, mode='live', horizon=24)
    assert landmark['triggered'] is False
    assert landmark['pattern'] is None
    assert landmark['delivery_call_id'] is None
    assert landmark['call_id_discontinuities'] == [
        dict(after_position=2, next_position=3, after_call_id=2, next_call_id=4)]
    assert landmark['incomplete_call_ids'] == []        # every surviving record is itself complete

    detector = CD.RepeatedActionCueDetector(mode='live', horizon=24)
    detector.observe_all(records)
    assert [detector.cue_for_call(call_id) for call_id in (4, 5)] == [None, None]

    # with call 3 present and identical, calls 2-4 are three consecutive calls and DO trigger
    complete = CD.scan([dict(A, call=1), dict(A, call=2), dict(A, call=3), dict(A, call=4)],
                       mode='live', horizon=24)
    assert complete['pattern'] == 'AAA'
    assert complete['trigger_call_id'] == 3
    assert complete['delivery_call_id'] == 4
    assert complete['pattern_call_ids'] == [1, 2, 3]
    assert complete['call_id_discontinuities'] == []


def test_duplicate_logical_call_ids_never_trigger():
    records = [dict(A, call=5), dict(A, call=5), dict(A, call=5)]
    landmark = CD.scan(records, mode='live', horizon=24)
    assert landmark['triggered'] is False
    assert landmark['pattern'] is None
    assert landmark['delivery_call_id'] is None
    assert landmark['call_id_discontinuities'] == [
        dict(after_position=1, next_position=2, after_call_id=5, next_call_id=5),
        dict(after_position=2, next_position=3, after_call_id=5, next_call_id=5)]


def test_the_records_own_call_ids_set_the_trigger_and_delivery_calls():
    records = [dict(A, call=5), dict(A, call=6), dict(A, call=7)]
    landmark = CD.scan(records, mode='live', horizon=24)
    assert landmark['pattern'] == 'AAA'
    assert landmark['trigger_call_id'] == 7
    assert landmark['trigger_position'] == 3
    assert landmark['delivery_call_id'] == 8
    assert landmark['pattern_call_ids'] == [5, 6, 7]

    detector = CD.RepeatedActionCueDetector(mode='live', horizon=24)
    detector.observe_all(records)
    assert detector.cue_for_call(3) is None                 # the position, not the logical call id
    assert detector.cue_for_call(8) == LEAD_CUE
    assert detector.landmark()['cue_emitted_call_ids'] == [8]

    # the frozen driver's own field name is 'call'; 'call_id' is accepted identically
    alias = CD.scan([dict(A, call_id=5), dict(A, call_id=6), dict(A, call_id=7)], mode='live', horizon=24)
    assert alias['trigger_call_id'] == 7
    assert alias['delivery_call_id'] == 8


@pytest.mark.parametrize('bad', ['1', 1.0, None, 0, -3, True])
def test_an_unusable_call_id_degrades_to_an_incomplete_record_and_never_raises(bad):
    records = [dict(A, call=1), dict(A, call=2), dict(A, call=bad), dict(A, call=4)]
    landmark = CD.scan(records, mode='live', horizon=24)
    assert landmark['triggered'] is False
    assert landmark['pattern'] is None
    assert landmark['delivered'] is False
    assert landmark['incomplete_call_ids'] == [None]
    assert landmark['incomplete_records'] == [dict(
        call_id=None, position=3,
        reason='unusable logical call id %r: the frozen driver numbers logical calls from 1' % (bad,))]
    assert json.loads(json.dumps(landmark)) == landmark


def test_negative_call_ids_never_schedule_a_cue_for_a_call_that_cannot_exist():
    # Records carrying call ids -3, -2, -1 must never yield a delivery call 0: the frozen driver numbers
    # logical calls from 1.
    landmark = CD.scan([dict(A, call=-3), dict(A, call=-2), dict(A, call=-1)], mode='live', horizon=24)
    assert landmark['triggered'] is False
    assert landmark['delivery_call_id'] is None
    assert landmark['incomplete_call_ids'] == [None, None, None]

    detector = CD.RepeatedActionCueDetector(mode='live', horizon=24)
    detector.observe_all([dict(A, call=-3), dict(A, call=-2), dict(A, call=-1)])
    assert detector.cue_for_call(0) is None
    assert detector.cue_for_call(-1) is None
    assert detector.landmark()['cue_emissions'] == 0
    assert [row['reason'] for row in detector.landmark()['cue_requests_refused']] == [
        REFUSAL_BAD_CALL_ID, REFUSAL_BAD_CALL_ID]


# ---------------------------------------------------------------- one cue, ever

def test_one_cue_maximum_per_episode():
    records = [dict(A), dict(A), dict(A),                                    # first pattern: calls 1-3
               dict(command='cat setup.py', returncode=0, observation='setup'),
               dict(command='grep -rn distance .', returncode=0, observation='hits'),
               dict(command='echo hello', returncode=0, observation='hello'),
               dict(command='pwd', returncode=0, observation='/'),           # second pattern: calls 7-9
               dict(command='pwd', returncode=0, observation='/'),
               dict(command='pwd', returncode=0, observation='/')]
    landmark = CD.scan(records, mode='live', horizon=24)
    assert landmark['pattern'] == 'AAA'
    assert landmark['trigger_call_id'] == 3                                  # the FIRST completion only
    assert landmark['delivery_call_id'] == 4
    assert landmark['pattern_call_ids'] == [1, 2, 3]

    detector = CD.RepeatedActionCueDetector(mode='live', horizon=24)
    detector.observe_all(records)
    emitted = [detector.cue_for_call(call_id) for call_id in range(1, 12)]
    assert emitted == [None, None, None, LEAD_CUE, None, None, None, None, None, None, None]
    assert detector.landmark()['cue_emissions'] == 1
    assert detector.landmark()['cue_emitted_call_ids'] == [4]
    assert detector.landmark()['trigger_call_id'] == 3

    # The second pattern emits nothing even if the detector is asked again, call by call.
    assert [detector.cue_for_call(call_id) for call_id in (10, 11, 12)] == [None, None, None]
    assert detector.landmark()['cue_emissions'] == 1


def test_the_live_arm_asks_call_by_call_as_the_episode_runs():
    """The live ordering: ask at call N, observe the result of call N, ask at call N+1."""
    detector = CD.RepeatedActionCueDetector(mode='live', horizon=24)
    handed = []
    for call_id, record in enumerate([dict(A), dict(A), dict(A), dict(B), dict(B), dict(B)], start=1):
        handed.append(detector.cue_for_call(call_id))       # asked BEFORE this call's own record exists
        detector.observe(record)
    handed.append(detector.cue_for_call(7))
    assert handed == [None, None, None, LEAD_CUE, None, None, None]
    assert detector.landmark()['trigger_call_id'] == 3
    assert detector.landmark()['delivery_call_id'] == 4
    assert detector.landmark()['cue_emitted_call_ids'] == [4]
    assert detector.landmark()['delivered'] is True
    assert detector.landmark()['pattern'] == 'AAA'
    assert detector.landmark()['records_observed'] == 6


@pytest.mark.parametrize('requested', [None, 4.0, '4', True, 0, -1])
def test_a_cue_is_never_handed_to_a_call_id_that_is_not_a_positive_integer(requested):
    detector = CD.RepeatedActionCueDetector(mode='live', horizon=24)
    detector.observe_all([dict(A), dict(A), dict(A)])
    assert detector.cue_for_call(requested) is None
    landmark = detector.landmark()
    assert landmark['cue_emissions'] == 0
    assert landmark['cue_emitted_call_ids'] == []
    assert landmark['delivered'] is False
    assert [row['reason'] for row in landmark['cue_requests_refused']] == [REFUSAL_BAD_CALL_ID]
    # the single-cue budget was not spent on the refused request
    assert detector.cue_for_call(4) == LEAD_CUE
    assert detector.landmark()['cue_emitted_call_ids'] == [4]
    assert json.loads(json.dumps(detector.landmark())) == detector.landmark()


# ---------------------------------------------------------------- final-call trigger, no delivery

def test_trigger_on_the_final_budgeted_call_is_recorded_without_delivery():
    records = [dict(command='sed -n %dp setup.py' % i, returncode=0, observation='line %d' % i)
               for i in range(1, 22)]
    records += [dict(command='python -m pytest -q', returncode=2, observation='ERROR: not found'),
                dict(command='python -m pytest -q', returncode=2, observation='ERROR: not found'),
                dict(command='python -m pytest -q', returncode=2, observation='ERROR: not found')]
    assert len(records) == 24
    landmark = CD.scan(records, mode='live', horizon=24)
    assert landmark['triggered'] is True
    assert landmark['pattern'] == 'AAA'
    assert landmark['trigger_call_id'] == 24
    assert landmark['delivery_call_id'] is None
    assert landmark['delivery_planned'] is False
    assert landmark['delivered'] is False
    assert landmark['pattern_call_ids'] == [22, 23, 24]
    assert landmark['cue_sha256'] == LEAD_CUE_SHA256
    assert landmark['reason'] == REASON_NO_DELIVERY_24         # the exact published wording

    detector = CD.RepeatedActionCueDetector(mode='live', horizon=24)
    detector.observe_all(records)
    assert detector.cue_for_call(24) is None
    assert detector.cue_for_call(25) is None
    assert detector.cue_for_call(None) is None                 # the leak that must never happen
    assert detector.landmark()['cue_emissions'] == 0
    assert detector.landmark()['cue_emitted'] is False
    assert detector.landmark()['cue_emitted_call_ids'] == []
    assert detector.landmark()['delivered'] is False
    assert [row['reason'] for row in detector.landmark()['cue_requests_refused']] == [
        REFUSAL_NO_DELIVERY, REFUSAL_NO_DELIVERY, REFUSAL_BAD_CALL_ID]
    assert detector.landmark()['reason'] == REASON_NO_DELIVERY_24


def test_a_trigger_inside_the_horizon_still_delivers_when_the_horizon_is_smaller():
    landmark = CD.scan([dict(A), dict(A), dict(A)], mode='live', horizon=3)
    assert landmark['trigger_call_id'] == 3
    assert landmark['delivery_call_id'] is None
    assert landmark['reason'] == ('no next normally budgeted model call remains: trigger on call 3 of '
                                  'horizon H=3; trigger recorded without delivery and no cue text is '
                                  'handed out')
    wider = CD.scan([dict(A), dict(A), dict(A)], mode='live', horizon=4)
    assert wider['delivery_call_id'] == 4


# ---------------------------------------------------------------- the silent baseline arm

def test_observe_only_baseline_records_the_same_landmark_without_emitting():
    records = [dict(A), dict(A), dict(A)]
    live = CD.scan(records, mode='live', horizon=24)
    silent = CD.scan(records, mode='observe', horizon=24)
    for key in ('triggered', 'pattern', 'trigger_call_id', 'delivery_call_id', 'pattern_call_ids',
                'cue_text', 'cue_sha256', 'delivered', 'cue_emissions'):
        assert silent[key] == live[key]
    assert silent['triggered'] is True
    assert silent['pattern'] == 'AAA'
    assert silent['trigger_call_id'] == 3
    assert silent['delivery_call_id'] == 4
    assert silent['cue_sha256'] == LEAD_CUE_SHA256
    assert silent['mode'] == 'observe'
    assert silent['delivered'] is False
    assert live['delivered'] is False                 # neither mode DELIVERS from the pure function
    assert silent['delivery_planned'] is False        # and the baseline never even plans one
    assert live['delivery_planned'] is True
    assert silent['reason'] == REASON_OBSERVE

    detector = CD.RepeatedActionCueDetector(mode='observe', horizon=24)
    detector.observe_all(records)
    assert [detector.cue_for_call(call_id) for call_id in (3, 4, 5)] == [None, None, None]
    assert detector.landmark()['cue_emitted'] is False
    assert detector.landmark()['cue_emissions'] == 0
    assert detector.landmark()['delivered'] is False
    assert detector.landmark()['trigger_call_id'] == 3
    assert detector.landmark()['delivery_call_id'] == 4
    assert detector.landmark()['cue_requests_refused'] == []      # a silent arm refuses nothing; it asks nothing


# ---------------------------------------------------------------- API contract

@pytest.mark.parametrize('mode', ['LIVE', 'silent', None, 1, ''])
def test_an_unknown_mode_is_refused_before_any_episode_work(mode):
    with pytest.raises(ValueError):
        CD.scan([dict(A)], mode=mode, horizon=24)
    with pytest.raises(ValueError):
        CD.RepeatedActionCueDetector(mode=mode, horizon=24)


@pytest.mark.parametrize('horizon', [0, -1, 1.5, '24', None, True])
def test_a_nonpositive_or_nonintegral_horizon_is_refused(horizon):
    with pytest.raises(ValueError):
        CD.scan([dict(A)], mode='live', horizon=horizon)
    with pytest.raises(ValueError):
        CD.RepeatedActionCueDetector(mode='live', horizon=horizon)


def test_the_landmark_is_json_serializable_exactly_as_recorded():
    landmark = CD.scan([dict(A), dict(A), dict(A), 'not a triple'], mode='observe', horizon=24)
    assert json.loads(json.dumps(landmark)) == landmark
    assert landmark['detector'] == 'repeated-action-cue-v1'
    assert len(landmark['detector_source_sha256']) == 64


def test_scan_does_not_mutate_or_reorder_the_records_it_is_shown():
    records = [dict(A), dict(A), dict(A)]
    CD.scan(records, mode='live', horizon=24)
    assert len(records) == 3
    assert records[0] == dict(command='ls -a', returncode=0,
                              observation='<returncode>0</returncode>\n<output>\n.  ..  setup.py\n</output>')
    assert records[0] == records[1] == records[2]
    assert 'call' not in records[0]


# ---------------------------------------------------------------- retrospective archived-episode fixtures
#
# The lead directs that `4927adc`'s 32 archived episodes be used as retrospective fixtures (docs:136).
# Expected values below are hand-written per episode. The pattern CONTENT at the reported call ids is
# additionally re-derived in this file straight from the archived messages, without the adapter, so a
# wrong linking rule or a wrong window position cannot pass.

YAML_V1 = ARCHIVES / 'pilot_20260922_yaml_v1'

# (instance, backend): (records, triggered, pattern, trigger_call_id, delivery_call_id)
ARCHIVED_YAML_V1 = {
    ('astropy__astropy-12907', 'large'): (24, True, 'ABABAB', 9, 10),
    ('astropy__astropy-12907', 'small'): (1, False, None, None, None),
    ('matplotlib__matplotlib-13989', 'large'): (24, True, 'AAA', 7, 8),
    ('matplotlib__matplotlib-13989', 'small'): (24, True, 'AAA', 13, 14),
    ('mwaskom__seaborn-3069', 'large'): (24, True, 'AAA', 10, 11),
    ('mwaskom__seaborn-3069', 'small'): (24, True, 'ABABAB', 13, 14),
    ('psf__requests-1142', 'large'): (24, False, None, None, None),
    ('psf__requests-1142', 'small'): (24, True, 'AAA', 6, 7),
    ('pytest-dev__pytest-10051', 'large'): (24, True, 'AAA', 5, 6),
    ('pytest-dev__pytest-10051', 'small'): (24, True, 'ABABAB', 7, 8),
    ('scikit-learn__scikit-learn-10297', 'large'): (24, True, 'ABABAB', 11, 12),
    ('scikit-learn__scikit-learn-10297', 'small'): (24, False, None, None, None),
    ('sphinx-doc__sphinx-10323', 'large'): (24, False, None, None, None),
    ('sphinx-doc__sphinx-10323', 'small'): (24, True, 'AAA', 7, 8),
    ('sympy__sympy-11618', 'large'): (24, False, None, None, None),
    ('sympy__sympy-11618', 'small'): (15, True, 'AAA', 13, 14),
}


def archived_run(cohort_dir, instance, backend):
    runs = [p for p in sorted(cohort_dir.iterdir())
            if p.is_dir() and p.name.startswith(instance + '__' + backend + '__')]
    assert len(runs) == 1, (instance, backend, [p.name for p in runs])
    return runs[0]


def raw_triples(run_dir):
    """Independent archive crosswalk; typed parser failures consume calls without assistant messages."""
    messages = json.loads((run_dir / 'trajectory.json').read_text())['messages']
    out = {}
    call = 0
    for index, message in enumerate(messages):
        if message.get('role') == 'user' and (message.get('extra') or {}).get('interrupt_type') == 'FormatError':
            call += 1
            out[call] = None
        if message.get('role') != 'assistant':
            continue
        call += 1
        following = messages[index + 1] if index + 1 < len(messages) else {}
        extra = following.get('extra') if isinstance(following.get('extra'), dict) else {}
        if following.get('role') != 'user' or extra.get('returncode') is None:
            out[call] = None                      # no ordinary recorded return-code observation
            continue
        actions = (message.get('extra') or {}).get('actions') or []
        command = actions[0].get('command') if len(actions) == 1 else None
        out[call] = (command, extra['returncode'], following.get('content'))
    episode = json.loads((run_dir / 'episode.json').read_text())
    if episode['n_model_calls'] == call + 1:
        assert episode['exit_status'] == 'ContextWindowExceededError'
        out[call + 1] = None
    return out


@pytest.mark.parametrize('instance,backend', sorted(ARCHIVED_YAML_V1))
def test_the_detector_runs_over_every_archived_yaml_v1_episode(instance, backend):
    expected_records, triggered, pattern, trigger_call_id, delivery_call_id = ARCHIVED_YAML_V1[
        (instance, backend)]
    run = archived_run(YAML_V1, instance, backend)
    records, notes = TT.read_episode(run)
    landmark = CD.scan(records, mode='observe', horizon=24)

    assert len(records) == expected_records
    assert landmark['records_observed'] == expected_records
    assert landmark['triggered'] is triggered
    assert landmark['pattern'] == pattern
    assert landmark['trigger_call_id'] == trigger_call_id
    assert landmark['delivery_call_id'] == delivery_call_id
    assert landmark['delivered'] is False                      # observe-only: nothing is ever delivered
    assert landmark['delivery_planned'] is False
    assert landmark['cue_emissions'] == 0
    assert landmark['call_id_discontinuities'] == []           # archived call ids are 1..n, consecutive
    assert json.loads(json.dumps(landmark)) == landmark

    # the claimed pattern really holds at the claimed call ids, checked against the raw archive
    triples = raw_triples(run)
    assert [row['call'] for row in records] == sorted(triples)
    if not triggered:
        return
    ids = landmark['pattern_call_ids']
    assert ids == list(range(trigger_call_id - len(ids) + 1, trigger_call_id + 1))
    window = [triples[call] for call in ids]
    assert all(entry is not None for entry in window)
    if pattern == 'AAA':
        assert len(window) == 3
        assert window[0] == window[1] == window[2]
    else:
        assert len(window) == 6
        assert window[0] == window[2] == window[4]
        assert window[1] == window[3] == window[5]
        assert window[0] != window[1]


def test_twenty_one_of_the_thirty_two_archived_episodes_would_have_triggered():
    landmarks = {}
    for cohort in COHORT_DIRS:
        for run in TT.archived_runs(ARCHIVES / cohort):
            records, _notes = TT.read_episode(run)
            landmarks[(cohort, run.name)] = CD.scan(records, mode='observe', horizon=24)
    assert len(landmarks) == 32
    assert sum(1 for landmark in landmarks.values() if landmark['triggered']) == 21
    assert sum(1 for landmark in landmarks.values() if landmark['pattern'] == 'AAA') == 12
    assert sum(1 for landmark in landmarks.values() if landmark['pattern'] == 'ABABAB') == 9
    # not one archived episode would have received a cue: they are retrospective records, not a live arm
    assert all(landmark['delivered'] is False for landmark in landmarks.values())
    assert all(landmark['cue_emissions'] == 0 for landmark in landmarks.values())
    # every trigger in the archives leaves a next budgeted call, so none is a no-delivery case
    assert [key for key, landmark in landmarks.items()
            if landmark['triggered'] and landmark['delivery_call_id'] is None] == []


def test_the_one_archived_episode_without_any_observation_is_incomplete_not_a_nonrepeat():
    run = archived_run(YAML_V1, 'astropy__astropy-12907', 'small')
    records, notes = TT.read_episode(run)
    assert records == [dict(call=1, command='echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT',
                            observation_error="the next message is 'exit', not an ordinary observation")]
    assert notes == [dict(call=1, reason="the next message is 'exit', not an ordinary observation")]
    landmark = CD.scan(records, mode='observe', horizon=24)
    assert landmark['triggered'] is False
    assert landmark['incomplete_call_ids'] == [1]
    assert landmark['incomplete_records'] == [
        dict(call_id=1, position=1, reason='observation recorded as unparsable')]


def test_the_archived_repeat_that_triggers_aaa_is_the_same_bytes_three_times():
    """psf__requests-1142/small: the same failing `sed -i` and the same shell syntax error three times."""
    run = archived_run(YAML_V1, 'psf__requests-1142', 'small')
    records, _notes = TT.read_episode(run)
    command = ("sed -i '/self.headers\\[\\'Content-Length\\'\\] = length/a if request.method != \\'GET\\':' "
               '/opt/miniconda3/envs/testbed/lib/python3.9/site-packages/requests/models.py')
    observation = ('<returncode>2</returncode>\n<output>\n/usr/bin/bash: -c: line 1: unexpected EOF while '
                   "looking for matching `''\n/usr/bin/bash: -c: line 2: syntax error: unexpected end of "
                   'file\n</output>')
    for call in (4, 5, 6):
        assert records[call - 1] == dict(call=call, command=command, returncode=2, observation=observation)
    landmark = CD.scan(records, mode='observe', horizon=24)
    assert landmark['pattern'] == 'AAA'
    assert landmark['pattern_call_ids'] == [4, 5, 6]
    assert landmark['trigger_call_id'] == 6
    assert landmark['delivery_call_id'] == 7

    # in a live arm this episode would have received exactly one cue, before call 7
    detector = CD.RepeatedActionCueDetector(mode='live', horizon=24)
    handed = []
    for record in records:
        handed.append(detector.cue_for_call(record['call']))
        detector.observe(record)
    assert [call for call, cue in zip(range(1, 25), handed) if cue is not None] == [7]
    assert detector.landmark()['cue_emitted_call_ids'] == [7]
    assert detector.landmark()['delivered'] is True
    assert handed[6] == LEAD_CUE


def test_the_archived_ababab_repeat_alternates_two_distinct_triples():
    """scikit-learn-10297/large: `pip show ... | grep Location` and a `find` alternating three times."""
    run = archived_run(YAML_V1, 'scikit-learn__scikit-learn-10297', 'large')
    records, _notes = TT.read_episode(run)
    first = dict(command='pip show scikit-learn | grep Location', returncode=0,
                 observation='<returncode>0</returncode>\n<output>\nLocation: /testbed\n</output>')
    second = dict(command='cd /testbed && find . -name "*RidgeClassifierCV*"', returncode=0,
                  observation='<returncode>0</returncode>\n<output>\n</output>')
    for call in (6, 8, 10):
        assert records[call - 1] == dict(first, call=call)
    for call in (7, 9, 11):
        assert records[call - 1] == dict(second, call=call)
    landmark = CD.scan(records, mode='observe', horizon=24)
    assert landmark['pattern'] == 'ABABAB'
    assert landmark['pattern_call_ids'] == [6, 7, 8, 9, 10, 11]
    assert landmark['trigger_call_id'] == 11
    assert landmark['delivery_call_id'] == 12


def test_the_adapter_refuses_a_trajectory_it_does_not_understand():
    with pytest.raises(ValueError):
        TT.episode_records({'messages': [], 'trajectory_format': 'some-other-format-2.0'})
    with pytest.raises(ValueError):
        TT.episode_records({'trajectory_format': 'mini-swe-agent-1.1'})
    with pytest.raises(ValueError):
        TT.episode_records([{'role': 'assistant'}])
    empty, notes = TT.episode_records({'messages': [], 'trajectory_format': 'mini-swe-agent-1.1'})
    assert empty == []
    assert notes == []


def test_the_adapter_links_only_the_immediate_ordinary_observation():
    messages = [
        dict(role='system', content='system prompt'),
        dict(role='user', content='problem statement'),
        dict(role='assistant', content='THOUGHT ...', extra=dict(actions=[dict(command='ls -a')])),
        dict(role='user', content='format error: no command found', extra=dict()),
        dict(role='assistant', content='THOUGHT ...', extra=dict(actions=[dict(command='ls -a')])),
        dict(role='user', content='<returncode>0</returncode>\n<output>\n.  ..\n</output>',
             extra=dict(returncode=0, raw_output='.  ..\n', exception_info='')),
        dict(role='assistant', content='THOUGHT ...', extra=dict(actions=[])),
        dict(role='user', content='<returncode>0</returncode>\n<output>\n.  ..\n</output>',
             extra=dict(returncode=0, exception_info='')),
        dict(role='assistant', content='THOUGHT ...', extra=dict(actions=[dict(command='ls -a')])),
        dict(role='user', content='<returncode>0</returncode>\n<output>\n.  ..\n</output>',
             extra=dict(returncode=0, exception_info='Command timed out after 60 seconds')),
        dict(role='exit', content='LimitsExceeded'),
    ]
    records, notes = TT.episode_records(dict(messages=messages, trajectory_format='mini-swe-agent-1.1'),
                                       **call_evidence(4))
    assert records == [
        dict(call=1, command='ls -a',
             observation_error='the next message records no return code (ordinary observation missing)'),
        dict(call=2, command='ls -a', returncode=0,
             observation='<returncode>0</returncode>\n<output>\n.  ..\n</output>'),
        dict(call=3, returncode=0, observation='<returncode>0</returncode>\n<output>\n.  ..\n</output>'),
        dict(call=4, command='ls -a',
             observation_error='the executor reported an exception for this observation'),
    ]
    assert notes == [
        dict(call=1, reason='the next message records no return code (ordinary observation missing)'),
        dict(call=3, reason='no parsed action in the model response (format error or no command)'),
        dict(call=4, reason='the executor reported an exception for this observation'),
    ]
    # calls 2 and 3 show the same observation bytes, but call 3 has no command and call 4 no observation:
    # nothing may be skipped over to build a pattern out of them
    landmark = CD.scan(records, mode='live', horizon=24)
    assert landmark['triggered'] is False
    assert landmark['incomplete_call_ids'] == [1, 3, 4]


def call_evidence(count):
    return dict(episode=dict(n_model_calls=count, exit_status='LimitsExceeded'),
                attempts=[dict(call=n, attempt=1, ok=True) for n in range(1, count + 1)])


def parser_gap_messages():
    action = dict(role='assistant', extra=dict(actions=[dict(command='ls')]))
    observation = dict(role='user', content='same output', extra=dict(returncode=0))
    rejected = dict(role='user', content='Expected one action',
                    extra=dict(interrupt_type='FormatError', response=dict(content='two actions')))
    return [action, observation, action, observation, rejected, action, observation]


def test_format_error_is_an_incomplete_logical_call_and_breaks_false_aaa():
    records, notes = TT.episode_records(dict(messages=parser_gap_messages(), trajectory_format='mini-swe-agent-1.1'),
                                       **call_evidence(4))
    assert [r['call'] for r in records] == [1, 2, 3, 4]
    assert records[2] == dict(call=3, observation_error=
        'logical call returned a FormatError; no parsed action or ordinary observation')
    landmark = CD.scan(records, mode='observe')
    assert landmark['triggered'] is False and landmark['incomplete_call_ids'] == [3]
    assert notes[0]['call'] == 3


def test_format_error_words_in_user_text_are_not_logical_call_evidence():
    messages = parser_gap_messages()
    messages[4] = dict(role='user', content='FormatError: example issue text')
    with pytest.raises(ValueError, match='ambiguous'):
        TT.episode_records(dict(messages=messages, trajectory_format='mini-swe-agent-1.1'), **call_evidence(4))


def test_missing_evidence_does_not_silently_relabel_assistant_positions_as_calls():
    with pytest.raises(ValueError, match='requires episode and attempt-ledger'):
        TT.episode_records(dict(messages=parser_gap_messages(), trajectory_format='mini-swe-agent-1.1'))


@pytest.mark.parametrize('damage', ['count', 'ledger_gap', 'duplicate', 'unsuccessful_response', 'incomplete_attempt',
                                 'malformed_parser_event'])
def test_ambiguous_call_crosswalk_is_refused(damage):
    evidence = call_evidence(4)
    messages = parser_gap_messages()
    if damage == 'count':
        evidence['episode']['n_model_calls'] = 5
    elif damage == 'ledger_gap':
        evidence['attempts'].pop(2)
    elif damage == 'duplicate':
        evidence['attempts'].append(dict(evidence['attempts'][0]))
    elif damage == 'unsuccessful_response':
        evidence['attempts'][0]['ok'] = False
    elif damage == 'incomplete_attempt':
        evidence['attempts'] = [dict(call=n, attempt=1, event='start') for n in range(1, 5)]
    else:
        messages[4]['extra'].pop('response')
    with pytest.raises(ValueError):
        TT.episode_records(dict(messages=messages, trajectory_format='mini-swe-agent-1.1'), **evidence)


def test_legacy_sympy_large_landmark_uses_logical_call_22_not_assistant_21():
    run = archived_run(ARCHIVES / 'pilot_20260922', 'sympy__sympy-11618', 'large')
    records, _ = TT.read_episode(run)
    landmark = CD.scan(records, mode='observe')
    assert len(records) == 24 and landmark['incomplete_call_ids'] == [13]
    assert landmark['pattern'] == 'ABABAB'
    assert landmark['pattern_call_ids'] == [17, 18, 19, 20, 21, 22]
    assert landmark['trigger_call_id'] == 22 and landmark['delivery_call_id'] == 23


def test_all_32_archives_reconcile_682_calls_and_ten_incomplete_records():
    records = [TT.read_episode(run)[0] for cohort in COHORT_DIRS for run in TT.archived_runs(ARCHIVES / cohort)]
    assert len(records) == 32 and sum(map(len, records)) == 682
    landmarks = [CD.scan(rows, mode='observe') for rows in records]
    assert sum(len(row['incomplete_records']) for row in landmarks) == 10
    assert sum(row['triggered'] for row in landmarks) == 21


def test_trailing_context_rejection_requires_matching_failure_and_terminal_evidence():
    messages = parser_gap_messages()[:4]
    messages.append(dict(role='exit', extra=dict(exit_status='ContextWindowExceededError')))
    evidence = call_evidence(3)
    evidence['episode']['exit_status'] = 'ContextWindowExceededError'
    evidence['attempts'][-1].update(ok=False, error='ContextWindowExceededError')
    trajectory = dict(messages=messages, trajectory_format='mini-swe-agent-1.1')
    records, _ = TT.episode_records(trajectory, **evidence)
    assert records[-1] == dict(call=3, observation_error=
        'terminal context-rejected logical call; no assistant or ordinary observation')
    assert CD.scan(records)['triggered'] is False
    evidence['attempts'][-1]['ok'] = True
    with pytest.raises(ValueError, match='ambiguous'):
        TT.episode_records(trajectory, **evidence)
