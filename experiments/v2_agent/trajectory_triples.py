"""DTR-REQ-005 retrospective adapter: archived mini-swe-agent trajectory -> exact
(command, returncode, rendered observation) triples for cue_detector.

The lead directs that `4927adc`'s 32 archived episodes be used as RETROSPECTIVE FIXTURES for the
repeated-action detector (docs/theory_feedback_20260923_completed_pilots.md:136). This module is the only
bridge between those archives and the detector, and it is read-only: it opens archived
`results/v2_agent/<cohort>/<run>/trajectory.json` files, never writes, never reruns anything, and imports
no frozen execution source.

Linking rule, exactly the lead's frozen shared definition (docs:119-122, answer Q8):
  * one record per LOGICAL model call, reconciled with episode and attempt-ledger counts. A parsed
    assistant and a typed FormatError each consume a call. Assistant ordinals alone are NOT call ids.
    A final context-rejected call is recovered only with matching terminal and failed-ledger evidence.
    Any other count/alignment discrepancy is refused rather than assigned invented call ids.
  * the command is the single parsed action of that assistant message.
  * the observation is linked ONLY to that call's IMMEDIATE ordinary recorded return-code observation --
    the very next message, when it is a user message carrying a recorded `returncode`. Anything else
    (an exit message, a format-error message with no return code, a missing message, a reported executor
    exception) means the observation is MISSING for that call, and the record stays INCOMPLETE. No
    proximate earlier or later observation is substituted.
  * the rendered observation is the exact message content the agent was shown, byte for byte, with no
    timestamp normalisation and no whitespace normalisation.

An INCOMPLETE record is handed to the detector as a record the detector itself rejects (so the detector's
own contract decides, not this adapter), and the adapter's own reason is returned alongside for publication.
"""
from __future__ import annotations

import json
from pathlib import Path

TRAJECTORY_FILE = 'trajectory.json'
SUPPORTED_FORMATS = ('mini-swe-agent-1.1',)
ADAPTER_ID = 'trajectory-triples-v2'


def _actions(message):
    extra = message.get('extra')
    return (extra.get('actions') or []) if isinstance(extra, dict) else []


def _command(message):
    """(command, reason). Exactly one parsed action is required; a format error has none."""
    actions = _actions(message)
    if not actions:
        return None, 'no parsed action in the model response (format error or no command)'
    if len(actions) != 1:
        return None, 'the response carried %d parsed actions; exactly one is required' % len(actions)
    action = actions[0]
    command = action.get('command') if isinstance(action, dict) else None
    if not isinstance(command, str):
        return None, 'the parsed action carries no command string'
    return command, None


def _observation(message):
    """(returncode, rendered observation, reason) for the IMMEDIATE next message, else a reason."""
    if message is None:
        return None, None, 'no message follows this call: no ordinary recorded return-code observation'
    if message.get('role') != 'user':
        return None, None, ('the next message is %r, not an ordinary observation' % message.get('role'))
    extra = message.get('extra')
    if not isinstance(extra, dict) or extra.get('returncode') is None:
        return None, None, 'the next message records no return code (ordinary observation missing)'
    if extra.get('exception_info'):
        return None, None, 'the executor reported an exception for this observation'
    returncode = extra['returncode']
    if isinstance(returncode, bool) or not isinstance(returncode, int):
        return None, None, 'the recorded return code is not an integer'
    content = message.get('content')
    if not isinstance(content, str):
        return None, None, 'the rendered observation is not recorded as text'
    return returncode, content, None


def _call_evidence(episode, attempts):
    """Require a complete legacy or durable ledger matching the recorded logical-call count."""
    count = episode.get('n_model_calls') if isinstance(episode, dict) else None
    if type(count) is not int or count < 0 or not isinstance(attempts, list):
        raise ValueError('logical call alignment requires episode and attempt-ledger evidence')
    starts, results = {}, {}
    legacy = bool(attempts) and all(isinstance(r, dict) and 'event' not in r for r in attempts)
    for row in attempts:
        if not isinstance(row, dict):
            raise ValueError('malformed attempt-ledger record')
        key = (row.get('call'), row.get('attempt'))
        if any(type(n) is not int or n < 1 for n in key):
            raise ValueError('invalid attempt-ledger logical call or attempt id')
        event = row.get('event')
        if not legacy and event not in ('start', 'result'):
            raise ValueError('mixed or unknown attempt-ledger format')
        destinations = (starts, results) if legacy else (starts if event == 'start' else results,)
        for target in destinations:
            if key in target:
                raise ValueError('duplicate attempt-ledger event')
            target[key] = row
    if starts.keys() != results.keys() or {call for call, _ in starts} != set(range(1, count + 1)):
        raise ValueError('incomplete attempt ledger or logical count disagreement; alignment is ambiguous')
    if any(type(r.get('ok')) is not bool for r in results.values()):
        raise ValueError('attempt result lacks an observed success/failure status')
    return count, {call: [row for (c, _), row in results.items() if c == call]
                   for call in range(1, count + 1)}


def episode_records(trajectory, *, episode=None, attempts=None):
    """(records, notes) for one archived trajectory dict.

    Each record is a Mapping carrying `call` (the logical call id), and `command` / `returncode` /
    `observation` when they exist. An incomplete record omits what is missing and carries
    `observation_error` when the observation itself is the missing part, so the DETECTOR classifies it.
    `notes` lists this adapter's own reason per incomplete call, for publication next to the landmark.
    Nonempty trajectories require episode/ledger evidence. This archived-format crosswalk is not a live
    driver: live instrumentation must supply the driver's actual logical ids, including failed calls."""
    if not isinstance(trajectory, dict):
        raise ValueError('an archived trajectory must be a JSON object')
    fmt = trajectory.get('trajectory_format')
    if fmt not in SUPPORTED_FORMATS:
        raise ValueError('unsupported archived trajectory format %r; expected one of %r'
                         % (fmt, SUPPORTED_FORMATS))
    messages = trajectory.get('messages')
    if not isinstance(messages, list):
        raise ValueError('an archived trajectory must carry a messages list')
    if not messages and episode is None and attempts is None:
        return [], []
    expected_calls, outcomes = _call_evidence(episode, attempts)
    records, notes, call = [], [], 0
    for index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue
        extra = message.get('extra') if isinstance(message.get('extra'), dict) else {}
        if message.get('role') == 'user' and extra.get('interrupt_type') == 'FormatError':
            # The pinned agent records the parser exception instead of an assistant. Never infer this
            # from words in ordinary user/tool text, and refuse malformed typed exception records.
            if not isinstance(extra.get('response'), dict) or 'returncode' in extra:
                raise ValueError('malformed FormatError event; logical alignment is ambiguous')
            call += 1
            reason = 'logical call returned a FormatError; no parsed action or ordinary observation'
            records.append(dict(call=call, observation_error=reason))
            notes.append(dict(call=call, reason=reason))
            continue
        if message.get('role') != 'assistant':
            continue
        call += 1
        command, command_reason = _command(message)
        following = messages[index + 1] if index + 1 < len(messages) else None
        returncode, observation, observation_reason = _observation(
            following if isinstance(following, dict) else None)
        record = dict(call=call)
        if command is not None:
            record['command'] = command
        if observation_reason is None:
            record['returncode'] = returncode
            record['observation'] = observation
        else:
            record['observation_error'] = observation_reason
        records.append(record)
        for reason in (command_reason, observation_reason):
            if reason is not None:
                notes.append(dict(call=call, reason=reason))
    # Known final API rejection leaves no assistant or ordinary observation. Recover only this
    # narrow, evidenced case; counts alone cannot locate an arbitrary missing successful call.
    if call + 1 == expected_calls:
        last = messages[-1] if messages and isinstance(messages[-1], dict) else {}
        status = (last.get('extra') or {}).get('exit_status')
        final = outcomes[expected_calls]
        if (episode.get('exit_status') != 'ContextWindowExceededError' or last.get('role') != 'exit' or
                status != 'ContextWindowExceededError' or not final or any(
                    r['ok'] is not False or r.get('error') != 'ContextWindowExceededError' for r in final)):
            raise ValueError('unlocated missing logical call; alignment is ambiguous')
        call += 1
        reason = 'terminal context-rejected logical call; no assistant or ordinary observation'
        records.append(dict(call=call, observation_error=reason))
        notes.append(dict(call=call, reason=reason))
    if call != expected_calls:
        raise ValueError('trajectory/episode logical count disagreement; alignment is ambiguous')
    # Both parsed and format-rejected responses require an observed successful physical response.
    for record in records:
        if not record.get('observation_error', '').startswith('terminal context-rejected') and not any(
                r['ok'] is True for r in outcomes[record['call']]):
            raise ValueError('trajectory response has no successful attempt at its logical call id')
    return records, notes


def read_episode(run_dir):
    """(records, notes) for an archived run directory. Read-only."""
    path = Path(run_dir) / TRAJECTORY_FILE
    episode = json.loads((Path(run_dir) / 'episode.json').read_text())
    attempts = [json.loads(line) for line in (Path(run_dir) / 'attempts.jsonl').read_text().splitlines() if line.strip()]
    records, notes = episode_records(json.loads(path.read_text()), episode=episode, attempts=attempts)
    return records, notes


def archived_runs(cohort_dir):
    """Every archived run directory under a cohort directory that holds a trajectory, in sorted order."""
    return sorted(p.parent for p in Path(cohort_dir).glob('*/' + TRAJECTORY_FILE))
