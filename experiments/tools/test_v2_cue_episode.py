"""Deterministic fixtures for the cue-v1 driver's model-visible intervention (experiments/v2_agent/cue_episode.py,
LogicalCalls), the lead's bullet "Model-visible intervention" (docs/theory_feedback_20260923_req005_review.md).

Pure: no model, server, container, subprocess or network. LogicalCalls is driven here exactly as the driver drives
it (open_call at each model.query; cue_for once the query is permitted; note_* as the query, the transport and the
observation report), so every boundary the lead named is exercised call by call: authoritative logical ids including
parse failures and refused or rejected queries, exactly one detector record per logical call, a FormatError breaking
adjacency, a physical retry never consuming a second cue, insertion only before the next permitted query, the silent
baseline landmark, the three delivery states, and the explicitly undelivered no-next-call / early-exit / pre-dispatch
refusal cases. The same boundaries are shown end to end, through the real drivers, in test_v2_cue_integration.py.

Every expected value is a hand-written literal.
"""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'experiments/v2_agent'))
import cue_episode as E  # noqa: E402

CUE_TEXT = ('Recent actions returned the same visible feedback repeatedly. Use the existing /testbed checkout. '
            'Choose a different action that will provide useful new evidence, or explain why repeating the action '
            'is necessary. Check the current working directory and the existing submission instructions.')
LS_OBSERVATION = '<returncode>0</returncode>\n<output>\nkeep.py\nmod.py\n</output>'
FORMAT_ERROR = 'the logical call returned a FormatError: no parsed action and no ordinary observation'
NO_OBSERVATION = ('the parsed action produced no ordinary observation (the episode ended on it, e.g. Submitted, or '
                  'the executor raised)')


class Episode:
    """Drives LogicalCalls the way CueModel does; `cues` records which call ids had the cue appended."""

    def __init__(self, arm):
        self.calls = E.LogicalCalls(arm=arm)
        self.cues = []
        self.appended_index = 10

    def query(self):
        call_id = self.calls.open_call()
        if self.calls.cue_for(call_id) is not None:
            self.cues.append(call_id)
            self.calls.note_cue_appended(call_id, self.appended_index)
        return call_id

    def action(self, command, observation=LS_OBSERVATION, returncode=0, sends=(200,)):
        call_id = self.query()
        self.transport(call_id, sends)
        self.calls.note_parsed(call_id, command)
        self.calls.note_observation(call_id, [dict(returncode=returncode, output='x', exception_info='')],
                                    [dict(content=observation)])
        return call_id

    def format_error(self):
        call_id = self.query()
        self.transport(call_id, (200,))
        self.calls.note_format_error(call_id)
        return call_id

    def transport(self, call_id, statuses, received=True):
        attempts = [dict(attempt_keys=['call%03d_attempt%02d' % (call_id, n)], http_statuses=[status],
                         response_received=received, refused_before_dispatch=[])
                    for n, status in enumerate(statuses, start=1)]
        self.calls.note_transport(call_id, attempts)


def test_a_format_error_breaks_adjacency_so_a_a_fe_a_never_triggers():
    ep = Episode('cue')
    ep.action('ls')
    ep.action('ls')
    ep.format_error()
    ep.action('ls')                                    # A, A, FormatError, A: no AAA across the parse failure
    ep.action('ls')
    assert ep.cues == []
    ep.action('ls')                                    # calls 4, 5, 6: three new consecutive repeats
    ep.query()
    assert ep.cues == [7]
    out = ep.calls.finish()
    assert (out['pattern'], out['trigger_call_id'], out['pattern_call_ids'], out['planned_delivery_call_id']) == (
        'AAA', 6, [4, 5, 6], 7)
    assert out['incomplete_records'] == [dict(call_id=3, reason=FORMAT_ERROR), dict(
        call_id=7, reason='no ordinary observation was recorded for this logical call (query state opened)')]
    assert (out['records_fed'], out['records_fed_call_ids_consecutive']) == (7, True)


def test_one_record_per_logical_call_is_fed_and_the_cue_goes_to_the_next_permitted_query_only():
    ep = Episode('cue')
    for _ in range(3):
        ep.action('ls')
    assert ep.calls.fed == 2                           # call 3's record is fed only when call 4 opens
    call_id = ep.query()
    assert (call_id, ep.cues, ep.calls.fed) == (4, [4], 3)
    assert [r['call'] for r in ep.calls.fed_records] == [1, 2, 3]
    assert ep.calls.detector.cue_for_call(4) is None   # at most one cue per episode, ever


def test_a_physical_retry_of_the_delivery_query_is_one_cue_with_two_sends():
    ep = Episode('cue')
    for _ in range(3):
        ep.action('ls')
    call_id = ep.query()
    ep.transport(call_id, (500, 200))
    ep.calls.note_parsed(call_id, 'git status')
    out = ep.calls.finish()
    assert (ep.cues, out['cue_emissions'], out['cue_http_statuses'], out['cue_send_attempt_keys'], out['state']) == (
        [4], 1, [500, 200], ['call004_attempt01', 'call004_attempt02'], 'response_received')


def test_a_pre_dispatch_refusal_after_insertion_is_not_delivery():
    ep = Episode('cue')
    for _ in range(3):
        ep.action('ls')
    call_id = ep.query()
    ep.calls.note_transport(call_id, [dict(attempt_keys=[], http_statuses=[], response_received=False,
                                           refused_before_dispatch=['insufficient_free_space'])])
    ep.calls.note_query_raised(call_id, 'InfrastructureStop')
    out = ep.calls.finish()
    assert (out['state'], out['message_appended'], out['message_appended_call_id'], out['transport_attempted'],
            out['response_received']) == ('message_appended', True, 4, False, False)


def test_a_transport_attempt_without_a_response_is_its_own_state():
    ep = Episode('cue')
    for _ in range(3):
        ep.action('ls')
    call_id = ep.query()
    ep.transport(call_id, (None,), received=False)
    ep.calls.note_query_raised(call_id, 'APIConnectionError')
    assert ep.calls.finish()['state'] == 'transport_attempted'


def test_an_early_exit_before_the_delivery_query_stays_explicitly_undelivered():
    ep = Episode('cue')
    for _ in range(3):
        ep.action('ls')                                # trigger on call 3; the episode ends (e.g. the deadline)
    out = ep.calls.finish()
    assert (out['state'], out['planned_delivery_call_id'], out['message_appended'], out['cue_emissions']) == (
        'undelivered_no_next_query', 4, False, 0)
    assert out['reason'] == ('the cue was scheduled for logical call 4, but the episode ended before that query was '
                             'permitted; nothing was appended')


def test_a_query_refused_by_the_deadline_consumes_an_id_but_gets_no_cue():
    ep = Episode('cue')
    for _ in range(3):
        ep.action('ls')
    call_id = ep.calls.open_call()                     # the driver opens the id, then the deadline check refuses
    ep.calls.note_refused_before_dispatch(call_id, 'the episode inference deadline was reached before the query: '
                                                   'no request was dispatched')
    out = ep.calls.finish()
    assert (out['logical_calls'], out['state'], out['message_appended']) == (4, 'undelivered_no_next_query', False)
    assert out['incomplete_records'][-1] == dict(call_id=4, reason='the episode inference deadline was reached before '
                                                                   'the query: no request was dispatched')


def test_a_trigger_on_the_final_h24_call_is_recorded_without_delivery():
    ep = Episode('cue')
    for number in range(21):
        ep.action('echo s%02d' % number, observation='<returncode>0</returncode>\n<output>\ns%02d\n</output>' % number)
    for _ in range(3):
        ep.action('ls')
    out = ep.calls.finish()
    assert (out['state'], out['trigger_call_id'], out['planned_delivery_call_id'], out['logical_calls'],
            ep.cues) == ('trigger_without_next_call', 24, None, 24, [])


def test_the_baseline_arm_records_the_same_landmark_silently():
    ep = Episode('baseline')
    for _ in range(3):
        ep.action('ls')
    ep.action('git status')
    out = ep.calls.finish()
    assert (ep.cues, out['state'], out['trigger_call_id'], out['planned_delivery_call_id'],
            out['baseline_landmark_call_reached'], out['cue_emissions']) == (
        [], 'baseline_silent_landmark', 3, 4, 4, 0)
    assert out['reason'] == ('baseline arm: the would-trigger landmark is recorded silently; its would-be delivery '
                             'call 4 was reached')


def test_an_executor_exception_or_a_submitted_action_is_an_incomplete_record():
    ep = Episode('cue')
    call_id = ep.query()
    ep.calls.note_parsed(call_id, 'ls')
    ep.calls.note_observation(call_id, [dict(returncode=-1, output='', exception_info='timed out')],
                              [dict(content='<exception>timed out</exception>')])
    call_id = ep.query()
    ep.calls.note_parsed(call_id, 'echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT')   # Submitted: no observation
    out = ep.calls.finish()
    assert out['incomplete_records'] == [
        dict(call_id=1, reason='the executor reported an exception for this observation'),
        dict(call_id=2, reason=NO_OBSERVATION)]


def test_the_cue_message_is_the_accepted_text_as_one_user_message():
    ep = Episode('cue')
    for _ in range(3):
        ep.action('ls')
    assert ep.query() == 4                             # the delivery call is open, as when the driver builds it
    message = E.cue_message(4, ep.calls)
    assert (message['role'], message['content']) == ('user', CUE_TEXT)
    assert message['extra'] == dict(cue_v1=dict(
        request='DTR-REQ-005', cue_sha256='80d52625bd593cd6fecafeb06daca898792979592272d9fadcf0ddd04bd39d9e',
        delivery_call_id=4, trigger_call_id=3, pattern='AAA'))


def test_the_live_runner_launch_argv_carries_the_frozen_row_and_the_budget():
    row = dict(instance_id='psf__requests-1142', backend='small', arm='cue', position=2)
    context = dict(run_dir='/r/run', run_id='rid', counted_physical_requests_before=5, assignment_request_limit=48)
    argv = E.episode_argv(row, context, python='/py', port=8291, alias='a', expected_image='sha256:i',
                          served={'file': 'f'}, episode_deadline=10.5, block_deadline=20, host_reserve_bytes=7)
    assert argv[0] == '/py' and argv[1].endswith('experiments/v2_agent/cue_episode.py')
    assert argv[2:] == ['--instance', 'psf__requests-1142', '--backend', 'small', '--arm', 'cue', '--position', '2',
                        '--port', '8291', '--alias', 'a', '--run-dir', '/r/run', '--run-id', 'rid',
                        '--expected-image', 'sha256:i', '--served', '{"file": "f"}', '--episode-deadline', '10.5',
                        '--block-deadline', '20.0', '--counted-before', '5', '--request-limit', '48',
                        '--host-reserve-bytes', '7']
    with pytest.raises(E.LiveReleaseHeld):
        E.run_assignment(dict(assignment_id='x'), {})


def test_an_unknown_arm_is_refused_before_any_work():
    with pytest.raises(ValueError):
        E.LogicalCalls(arm='treatment')


# ---------------------------------------------------------------- the model class itself (CueModel)

class FakeFormatError(Exception):
    pass


class Retryable(Exception):
    pass


class Choice:
    def __init__(self, content):
        self.finish_reason = 'stop'
        self.message = type('M', (), dict(content=content))()


class Response:
    def __init__(self, content):
        self.choices = [Choice(content)]
        self.usage = None


class FakeBase:
    """Stands in for LitellmTextbasedModel: query() retries _query once on Retryable (tenacity stop-after-2) and
    parses one ```mswea_bash_command block, raising FakeFormatError otherwise; _query returns the next scripted
    response and records the exact messages it was given."""
    abort_exceptions = []

    def __init__(self, script, sent):
        self.script, self.sent = list(script), sent

    def query(self, messages, **kw):
        for attempt in (1, 2):
            try:
                response = self._query(messages, **kw)
                break
            except Retryable:
                if attempt == 2:
                    raise
        content = response.choices[0].message.content
        if '```mswea_bash_command\n' not in content:
            raise FakeFormatError(content)
        command = content.split('```mswea_bash_command\n', 1)[1].split('\n```', 1)[0]
        return dict(role='assistant', content=content, extra=dict(actions=[dict(command=command)]))

    def _query(self, messages, **kw):
        self.sent.append([dict(role=m['role'], content=m['content']) for m in messages])
        item = self.script.pop(0)
        if item == 'retryable':
            raise Retryable('500')
        return Response(item)

    def format_observation_messages(self, message, outputs, template_vars=None):
        return [dict(role='user', content=LS_OBSERVATION, extra=dict(returncode=outputs[0]['returncode']))]


class FakeCapture:
    def __init__(self):
        self.attempts = []

    def dispatch(self, *, logical_call_id, query_attempt, call):
        try:
            result = call()
        except BaseException:
            self.attempts.append(dict(logical_call_id=logical_call_id, attempt_keys=[
                'call%03d_attempt%02d' % (logical_call_id, query_attempt)], http_statuses=[500],
                response_received=True, refused_before_dispatch=[]))
            raise
        self.attempts.append(dict(logical_call_id=logical_call_id, attempt_keys=[
            'call%03d_attempt%02d' % (logical_call_id, query_attempt)], http_statuses=[200], response_received=True,
            refused_before_dispatch=[]))
        return result


def make_model(tmp_path, script, *, arm='cue', deadline=None):
    sent, calls, capture = [], E.LogicalCalls(arm=arm), FakeCapture()
    (tmp_path / 'attempts.jsonl').write_text('')

    class Base(FakeBase):
        def __init__(self, **kw):
            super().__init__(script, sent)
    model_class = E.make_model_class(Base, FakeFormatError, deadline=deadline or (E.time.time() + 1000.0),
                                     capture=capture, calls=calls, attempts_path=tmp_path / 'attempts.jsonl',
                                     attempts=[], run_dir=tmp_path)
    return model_class(), calls, sent


def act(command):
    return 'THOUGHT: step\n\n```mswea_bash_command\n%s\n```' % command


def converse(model, history, n):
    """Like DefaultAgent: query, then append the assistant message and its observation."""
    for _ in range(n):
        message = model.query(history)
        history.append(dict(role='assistant', content=message['content']))
        history.extend(model.format_observation_messages(message, [dict(returncode=0, output='x',
                                                                        exception_info='')]))


def test_the_model_appends_the_cue_once_and_a_retry_resends_the_same_messages(tmp_path):
    model, calls, sent = make_model(tmp_path, [act('ls')] * 3 + ['retryable', act('git status')])
    history = [dict(role='system', content='s'), dict(role='user', content='task')]
    converse(model, history, 4)
    assert [m['content'] for m in history].count(CUE_TEXT) == 1           # appended to the agent's own history
    assert history[8] == dict(role='user', content=CUE_TEXT, extra=history[8]['extra'])
    assert [sum(m['content'] == CUE_TEXT for m in request) for request in sent] == [0, 0, 0, 1, 1]
    assert sent[3] == sent[4]                                              # the retry re-sends the same messages
    out = calls.finish()
    assert (out['message_appended_call_id'], out['cue_emissions'], out['cue_send_attempt_keys']) == (
        4, 1, ['call004_attempt01', 'call004_attempt02'])


def test_a_query_past_the_deadline_is_refused_before_the_cue_is_appended(tmp_path, monkeypatch):
    model, calls, sent = make_model(tmp_path, [act('ls')] * 3)
    history = [dict(role='system', content='s'), dict(role='user', content='task')]
    converse(model, history, 3)
    # the same model, now past its deadline (the frozen request_timeout pre-check raises): the next logical id is
    # opened and refused, and the cue that was due is NOT appended
    def past_deadline(deadline, now=None):
        raise E.PE.EpisodeDeadline('episode inference deadline reached')
    monkeypatch.setattr(E.PE, 'request_timeout', past_deadline)
    with pytest.raises(E.PE.EpisodeDeadline):
        model.query(history)
    assert CUE_TEXT not in [m['content'] for m in history] and len(sent) == 3
    out = calls.finish()
    assert (out['logical_calls'], out['state'], out['message_appended']) == (4, 'undelivered_no_next_query', False)


def test_a_format_error_is_its_own_logical_call_in_the_model(tmp_path):
    model, calls, sent = make_model(tmp_path, [act('ls'), act('ls'), 'no command block', act('ls')])
    history = [dict(role='system', content='s'), dict(role='user', content='task')]
    converse(model, history, 2)
    with pytest.raises(FakeFormatError):
        model.query(history)
    history.append(dict(role='user', content='format error message'))
    converse(model, history, 1)
    calls.feed_until(calls.current)
    assert [r.get('observation_error') for r in calls.fed_records] == [None, None, FORMAT_ERROR, None]
    assert [r['call'] for r in calls.fed_records] == [1, 2, 3, 4]
    assert calls.detector.landmark()['triggered'] is False                # A, A, FormatError, A
