"""DTR-REQ-005 'cue-v1' episode driver: ONE fixed-order DEV episode, derived from (never editing) the frozen yaml-v1
driver pilot_episode.py, with the lead's integration contract (docs/theory_feedback_20260923_req005_review.md,
"Concrete integration contract") wired in:

  * Model-visible intervention: authoritative logical call ids (every model.query, including parse failures and
    rejected or refused queries); exactly one complete or incomplete detector record per logical call; the fixed
    290-byte cue appended as ONE user message only before the next permitted logical query after the first trigger
    (live arm), or the same would-trigger landmark recorded silently (baseline arm). A FormatError breaks adjacency.
    A physical retry re-sends the same messages and never consumes a second cue. Delivery is recorded as the distinct
    states message_appended / transport_attempted / response_received; no-next-call and early-exit cases stay
    explicitly undelivered, and a pre-dispatch storage refusal after insertion is not delivery.
  * Transport: cue_transport's capture installed at litellm.client_session before the first completion, wrapping the
    real terminal transport litellm would build (the path traced in docs/req005_transport_map_20260923.md). Every
    physical send is receipted before it leaves, within the cohort's 576-request budget.
  * Endpoint, then diagnostic, then cleanup: the frozen Submitted-only artifact is determined inside the inference
    window exactly where the frozen driver determines it; cue_terminal then runs the supervised all-exit diagnostic
    and the container cleanup from a `finally` path on every terminal path.
  * Admission: nothing (no alarm, container, model, receipt or request) happens before cue_admission.admit_episode
    has validated the whole frozen queue, the open runner session, this run's frozen assignment row and the bytes of
    every module this process runs; the pinned SDK and mini-swe-agent files actually imported are checked too.

Unchanged from the frozen driver, and taken from it rather than restated: the pinned default.yaml and its digest
check, build_effective_config (H24, T=0, max_tokens 1,536, command timeout 60 s, wall 1,800 s, num_retries 0), the
two physical attempts per logical call (MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT=2, set by importing pilot_episode), the
request timeout min(900 s, time left), the one-shot SIGALRM inference deadline, the attempt ledger, the cp2
container-platform template binding, the wc2 capture and the owned-container cleanup. The baseline arm's
model-visible messages and request bodies are therefore those of the frozen driver for the same history, and the
cue arm differs only by the one inserted cue message (experiments/tools/test_v2_cue_integration.py).

The live comparison is HELD by the lead. `run_assignment`, the only episode function cue_runner admits in the real
checkout, refuses with LiveReleaseHeld: there is no host/server step here. This module runs no model by itself.

    work/venvs/minisweagent_04d809c/bin/python experiments/v2_agent/cue_episode.py --instance ... (see --help)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import pilot_episode as PE  # noqa: E402  frozen yaml-v1 driver, imported read-only (its import sets MSWEA_* as frozen)
import workspace_capture as WC  # noqa: E402  frozen wc2 rule, reused unmodified
import cue_admission as A  # noqa: E402
import cue_cohort as CC  # noqa: E402
import cue_detector as CD  # noqa: E402
import cue_terminal as T  # noqa: E402
import cue_transport as CT  # noqa: E402

SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
REQUEST = 'DTR-REQ-005'
DRIVER = 'cue-v1 episode driver (cue_episode.py)'
CUE_ROLE = 'user'
EXIT_ADMISSION_REFUSED = 3
DETAIL_CHARS = 300
RUNNING_MODULES = ('cue_episode', 'cue_admission', 'cue_transport', 'cue_terminal', 'cue_detector', 'cue_cohort',
                   'exit_capture', 'request_receipt', 'workspace_capture', 'pilot_episode')
TOKENIZER_SOURCE = ('server-side only: llama-server tokenizes with the served GGUF\'s own tokenizer; no worker-side '
                    'preflight token count is made')

# delivery states (strongest reached); the lead's three states plus the explicit undelivered/baseline outcomes
NOT_TRIGGERED = 'not_triggered'
TRIGGER_WITHOUT_NEXT_CALL = 'trigger_without_next_call'
UNDELIVERED_NO_NEXT_QUERY = 'undelivered_no_next_query'
BASELINE_SILENT = 'baseline_silent_landmark'
MESSAGE_APPENDED = 'message_appended'
TRANSPORT_ATTEMPTED = 'transport_attempted'
RESPONSE_RECEIVED = 'response_received'
DELIVERY_NOTE = ('message_appended: the cue message was appended to the model-visible messages of the delivery call; '
                 'transport_attempted: at least one physical request carrying it was handed to the transport; '
                 'response_received: an HTTP response came back for such a request. Only response_received confirms '
                 'that the server received the cue; a pre-dispatch refusal after insertion is not delivery')


class LiveReleaseHeld(RuntimeError):
    """The cue-v1 live comparison is held by the lead; no host/server step exists in this checkout."""


def sha256_text(text):
    return hashlib.sha256(text.encode('utf-8', 'surrogateescape')).hexdigest()


def _append_jsonl(path, record):
    if path is not None:
        PE.append_attempt(path, record)          # the frozen durable append (flush + fsync)


# ---------------------------------------------------------------- logical calls and the intervention (pure)

class LogicalCalls:
    """The authoritative logical-call ledger of ONE episode and its model-visible intervention.

    One id per model.query, in order, whatever happens to the query. Before a query is dispatched, every earlier
    call's record is handed to the detector exactly once, complete or incomplete. Pure except for the optional
    `log_path` (calls.jsonl), which never holds rendered observation text, only its digest and length."""

    def __init__(self, *, arm, horizon=CC.H, log_path=None, clock=time.time):
        if arm not in CC.MODE_BY_ARM:
            raise ValueError('arm must be one of %r' % (tuple(CC.MODE_BY_ARM),))
        self.arm, self.mode, self.horizon = arm, CC.MODE_BY_ARM[arm], horizon
        self.detector = CD.RepeatedActionCueDetector(mode=self.mode, horizon=horizon)
        self.calls, self.current, self.fed = {}, 0, 0
        self.fed_records = []
        self.log_path, self.clock = log_path, clock
        self.cue_call_id = None
        self.cue_message_index = None
        self.baseline_landmark_call_reached = None
        self.cue_sends = []

    def _log(self, event, call_id, **fields):
        _append_jsonl(self.log_path, dict(fields, event=event, call=call_id, t=self.clock()))

    # -- the query side --------------------------------------------------
    def open_call(self):
        """A new logical id, at the start of model.query. Every earlier call's record is fed first."""
        self.current += 1
        call_id = self.current
        self.calls[call_id] = dict(call_id=call_id, state='opened', command=None, returncode=None, observation=None,
                                   observation_error=None, query_outcome=None, cue_appended=False)
        self.feed_until(call_id - 1)
        self._log('open', call_id)
        return call_id

    def feed_until(self, last):
        for call_id in range(self.fed + 1, last + 1):
            record = self.record(call_id)
            self.detector.observe(record)
            self.fed_records.append(record)
            self.fed = call_id

    def record(self, call_id):
        """Exactly the detector record of one logical call: complete only with a parsed command and an ordinary
        observation; otherwise incomplete with the reason."""
        call = self.calls.get(call_id)
        if call is None:
            return dict(call=call_id, observation_error='no logical call with this id was opened')
        if call['observation_error'] is None and call['command'] is not None and call['returncode'] is not None \
                and call['observation'] is not None:
            return dict(call=call_id, command=call['command'], returncode=call['returncode'],
                        observation=call['observation'])
        return dict(call=call_id, observation_error=call['observation_error'] or (
            'no ordinary observation was recorded for this logical call (query state %s)' % call['state']))

    def cue_for(self, call_id):
        """The cue text for this call (live arm, the scheduled delivery call, once), else None. In the baseline arm
        the same landmark is noted silently when its would-be delivery call is reached."""
        text = self.detector.cue_for_call(call_id)
        if self.mode == CD.MODE_OBSERVE:
            landmark = self.detector.landmark()
            if landmark['triggered'] and landmark['delivery_call_id'] == call_id:
                self.baseline_landmark_call_reached = call_id
                self._log('baseline_silent_landmark', call_id, trigger_call_id=landmark['trigger_call_id'],
                          pattern=landmark['pattern'])
        return text

    def note_cue_appended(self, call_id, message_index):
        self.calls[call_id]['cue_appended'] = True
        self.cue_call_id, self.cue_message_index = call_id, message_index
        self._log('cue_appended', call_id, message_index=message_index, cue_sha256=CD.CUE_SHA256)

    def note_refused_before_dispatch(self, call_id, reason):
        self.calls[call_id].update(state='refused_before_dispatch', observation_error=reason,
                                   query_outcome='refused_before_dispatch')
        self._log('refused_before_dispatch', call_id, reason=reason)

    def note_parsed(self, call_id, command):
        self.calls[call_id].update(state='parsed_action', command=command, query_outcome='parsed_action')
        self._log('parsed_action', call_id, command_sha256=sha256_text(command), command_chars=len(command))

    def note_format_error(self, call_id):
        self.calls[call_id].update(state='format_error', query_outcome='FormatError',
                                   observation_error='the logical call returned a FormatError: no parsed action '
                                                     'and no ordinary observation')
        self._log('format_error', call_id)

    def note_query_raised(self, call_id, error_class):
        self.calls[call_id].update(state='query_raised', query_outcome=error_class,
                                   observation_error='the logical query raised %s: no parsed action' % error_class)
        self._log('query_raised', call_id, error_class=error_class)

    def note_transport(self, call_id, attempts):
        """The capture's query-attempt summaries for this call (physical sends, responses)."""
        sends = [dict(attempt_keys=a['attempt_keys'], http_statuses=a['http_statuses'],
                      response_received=a['response_received'], refused_before_dispatch=a['refused_before_dispatch'])
                 for a in attempts]
        self.calls[call_id]['transport'] = sends
        if call_id == self.cue_call_id:
            self.cue_sends = sends
        self._log('transport', call_id, attempts=sends)

    # -- the observation side --------------------------------------------
    def note_observation(self, call_id, outputs, rendered):
        """The ordinary observation of the call's single parsed action, exactly as the agent is shown it."""
        call = self.calls.get(call_id)
        if call is None:
            return
        if len(outputs) != 1 or len(rendered) != 1:
            call['observation_error'] = 'the observation did not render exactly one output message'
        elif outputs[0].get('exception_info'):
            call['observation_error'] = 'the executor reported an exception for this observation'
        elif isinstance(outputs[0].get('returncode'), bool) or not isinstance(outputs[0].get('returncode'), int):
            call['observation_error'] = 'the observation records no integer return code'
        elif not isinstance(rendered[0].get('content'), str):
            call['observation_error'] = 'the rendered observation is not text'
        else:
            call.update(returncode=outputs[0]['returncode'], observation=rendered[0]['content'])
        call['state'] = 'observed' if call['observation_error'] is None else 'observation_incomplete'
        text = rendered[0].get('content') if len(rendered) == 1 and isinstance(rendered[0].get('content'), str) else ''
        self._log('observation', call_id, returncode=call['returncode'], observation_sha256=sha256_text(text),
                  observation_chars=len(text), observation_error=call['observation_error'])

    # -- the end of the episode ------------------------------------------
    def finish(self):
        """Feed the remaining records and return the published intervention record."""
        for call in self.calls.values():
            if call['state'] == 'parsed_action':
                call['observation_error'] = ('the parsed action produced no ordinary observation (the episode ended '
                                             'on it, e.g. Submitted, or the executor raised)')
                call['state'] = 'no_observation'
        self.feed_until(self.current)
        landmark = self.detector.landmark()
        planned = landmark['delivery_call_id'] if landmark['triggered'] else None
        appended = self.cue_call_id is not None
        attempted = any(any(send['attempt_keys']) for send in self.cue_sends)
        received = any(send['response_received'] for send in self.cue_sends)
        statuses = [status for send in self.cue_sends for status in send['http_statuses']]
        if not landmark['triggered']:
            state, reason = NOT_TRIGGERED, landmark['reason']
        elif planned is None:
            state, reason = TRIGGER_WITHOUT_NEXT_CALL, landmark['reason']
        elif self.mode == CD.MODE_OBSERVE:
            state = BASELINE_SILENT
            reason = ('baseline arm: the would-trigger landmark is recorded silently; its would-be delivery call %d '
                      '%s' % (planned, 'was reached' if self.baseline_landmark_call_reached == planned
                              else 'was never queried (the episode ended first)'))
        elif not appended:
            state = UNDELIVERED_NO_NEXT_QUERY
            reason = ('the cue was scheduled for logical call %d, but the episode ended before that query was '
                      'permitted; nothing was appended' % planned)
        elif received:
            state, reason = RESPONSE_RECEIVED, 'a response came back for a request carrying the cue'
        elif attempted:
            state, reason = TRANSPORT_ATTEMPTED, 'a request carrying the cue reached the transport; no response'
        else:
            state = MESSAGE_APPENDED
            reason = ('the cue message was appended, but no physical request carrying it was sent (for example a '
                      'pre-dispatch storage refusal or the deadline): not delivered to the model')
        incomplete = [dict(call_id=r['call'], reason=r['observation_error']) for r in self.fed_records
                      if 'observation_error' in r]
        return dict(
            arm=self.arm, detector_mode=self.mode, horizon=self.horizon, logical_calls=self.current,
            records_fed=len(self.fed_records), records_fed_call_ids_consecutive=[r['call'] for r in self.fed_records]
            == list(range(1, len(self.fed_records) + 1)), incomplete_records=incomplete,
            triggered=landmark['triggered'], pattern=landmark['pattern'], trigger_call_id=landmark['trigger_call_id'],
            pattern_call_ids=landmark['pattern_call_ids'], planned_delivery_call_id=planned, state=state,
            reason=reason, message_appended=appended, message_appended_call_id=self.cue_call_id,
            message_index=self.cue_message_index, transport_attempted=attempted, response_received=received,
            cue_http_statuses=statuses, cue_send_attempt_keys=[k for s in self.cue_sends for k in s['attempt_keys']],
            cue_emissions=landmark['cue_emissions'], baseline_landmark_call_reached=self.baseline_landmark_call_reached,
            cue_sha256=CD.CUE_SHA256, cue_role=CUE_ROLE, note=DELIVERY_NOTE, landmark=landmark)


def cue_message(call_id, calls):
    """The one model-visible cue message. Only role and content reach the model; `extra` is stripped by
    mini-swe-agent's _prepare_messages_for_api and is kept for the trajectory reader."""
    landmark = calls.detector.landmark()
    return dict(role=CUE_ROLE, content=CD.CUE_TEXT,
                extra=dict(cue_v1=dict(request=REQUEST, cue_sha256=CD.CUE_SHA256, delivery_call_id=call_id,
                                       trigger_call_id=landmark['trigger_call_id'], pattern=landmark['pattern'])))


# ---------------------------------------------------------------- the model class (built at run time)

def make_model_class(base, format_error, *, deadline, capture, calls, attempts_path, attempts, run_dir):
    """The frozen AccountedModel's accounting (attempts.jsonl, request_timeout, the call-9 history), plus the capture
    dispatch, the authoritative logical ids and the one cue. `base` is LitellmTextbasedModel."""

    class CueModel(base):
        abort_exceptions = base.abort_exceptions + [PE.EpisodeDeadline, CT.InfrastructureStop]

        def __init__(self, **kw):
            super().__init__(**kw)
            self.logical = 0
            self.attempt = 0

        def query(self, messages, **kw):
            call_id = calls.open_call()                    # every query consumes an id, even a refused one
            self.logical, self.attempt = call_id, 0
            try:
                PE.request_timeout(deadline)
            except PE.EpisodeDeadline:
                calls.note_refused_before_dispatch(call_id, 'the episode inference deadline was reached before the '
                                                            'query: no request was dispatched')
                raise
            text = calls.cue_for(call_id)                  # only after the query is permitted
            if text is not None:
                messages.append(cue_message(call_id, calls))
                calls.note_cue_appended(call_id, len(messages) - 1)
            if call_id == 9:
                WC.write_once(run_dir / 'call9_history.json',
                              json.dumps(dict(call=9, messages=messages, captured_at=time.time())) + '\n')
            try:
                message = super().query(messages, **kw)
            except format_error:
                calls.note_format_error(call_id)
                raise
            except BaseException as e:
                calls.note_query_raised(call_id, type(e).__name__)
                raise
            finally:
                calls.note_transport(call_id, [a for a in capture.attempts if a['logical_call_id'] == call_id])
            actions = message.get('extra', {}).get('actions') or []
            command = actions[0].get('command') if len(actions) == 1 and isinstance(actions[0], dict) else None
            if isinstance(command, str):
                calls.note_parsed(call_id, command)
            else:
                calls.note_query_raised(call_id, 'UnparsedAction')
            return message

        def _query(self, messages, **kw):
            timeout = PE.request_timeout(deadline)
            self.attempt += 1
            rec = dict(call=self.logical, attempt=self.attempt, t_start=time.time(), request_timeout_s=timeout)
            PE.append_attempt(attempts_path, dict(rec, event='start'))
            attempts.append(rec)
            try:
                r = capture.dispatch(logical_call_id=self.logical, query_attempt=self.attempt,
                                     call=lambda: base._query(self, messages, **dict(kw, timeout=PE.request_timeout(
                                         deadline))))
            except BaseException as e:  # noqa: BLE001  logged, then re-raised to the unmodified retry/agent logic
                rec.update(t_end=time.time(), ok=False, error=type(e).__name__, detail=str(e)[:DETAIL_CHARS])
                PE.append_attempt(attempts_path, dict(rec, event='result'))
                raise
            u = getattr(r, 'usage', None)
            rec.update(t_end=time.time(), ok=True, prompt_tokens=getattr(u, 'prompt_tokens', None),
                       completion_tokens=getattr(u, 'completion_tokens', None),
                       finish_reason=r.choices[0].finish_reason)
            PE.append_attempt(attempts_path, dict(rec, event='result'))
            return r

        def format_observation_messages(self, message, outputs, template_vars=None):
            rendered = super().format_observation_messages(message, outputs, template_vars)
            calls.note_observation(self.logical, outputs, rendered)
            return rendered

    return CueModel


# ---------------------------------------------------------------- admission of this process

def running_module_digests():
    """sha256 of the file bytes of every bound module THIS process has loaded from this directory. This driver's
    own digest is the one taken when it was loaded, also when it runs as __main__."""
    out = {'cue_episode.py': SOURCE_SHA256}
    for name in RUNNING_MODULES:
        if name == 'cue_episode':
            continue
        module = sys.modules.get(name)
        source = getattr(module, '__file__', None)
        if source is not None and Path(source).resolve().parent == HERE:
            out[name + '.py'] = hashlib.sha256(Path(source).read_bytes()).hexdigest()
    return out


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description='cue-v1 episode (DTR-REQ-005); admitted only inside a cue-v1 runner '
                                             'session')
    ap.add_argument('--instance', required=True)
    ap.add_argument('--backend', choices=('small', 'large'), required=True)
    ap.add_argument('--arm', choices=('baseline', 'cue'), required=True)
    ap.add_argument('--position', type=int, required=True)
    ap.add_argument('--port', type=int, required=True)
    ap.add_argument('--alias', required=True)
    ap.add_argument('--run-dir', required=True)
    ap.add_argument('--run-id', required=True)
    ap.add_argument('--expected-image', required=True)
    ap.add_argument('--served', required=True, help='JSON: served model file name/sha256/load record from the runner')
    ap.add_argument('--episode-deadline', required=True, type=float)
    ap.add_argument('--block-deadline', required=True, type=float)
    ap.add_argument('--counted-before', required=True, type=int,
                    help='physical requests counted for the cohort before this assignment (every earlier session)')
    ap.add_argument('--request-limit', required=True, type=int, help='this assignment\'s limit, min(48, 576 - counted)')
    ap.add_argument('--host-reserve-bytes', required=True, type=int,
                    help='the host disk reserve the free-space preflight keeps free (declared by the launcher)')
    return ap.parse_args(argv)


def admit(args, layout):
    """Everything that must hold before ANY episode work. Returns (binding, row) or raises AdmissionRefused."""
    frozen, row, _report = A.admit_episode(layout, run_id=args.run_id, position=args.position,
                                           instance_id=args.instance, backend=args.backend, arm=args.arm,
                                           port=args.port, alias=args.alias, expected_image=args.expected_image)
    if Path(args.run_dir).resolve() != (layout.out / args.run_id).resolve():
        raise A.AdmissionRefused(['--run-dir is not the namespace directory of run %s' % args.run_id])
    limit = min(frozen['settings']['max_physical_requests_per_assignment'],
                frozen['settings']['max_physical_requests'] - args.counted_before)
    if args.counted_before < 0 or args.request_limit != limit:
        raise A.AdmissionRefused(['request budget arguments differ from the frozen rule min(48, 576 - counted)'])
    if args.host_reserve_bytes < 0:
        raise A.AdmissionRefused(['the host reserve must be a non-negative number of bytes'])
    A.check_running_sources(frozen, running_module_digests())
    return frozen, row


# ---------------------------------------------------------------- the episode

def _usage_totals(receipts_dir):
    """Server-reported usage summed over the outcome records that know it; unknown stays counted, never 0."""
    known = dict(prompt_tokens=0, completion_tokens=0)
    unknown = 0
    for path in sorted(Path(receipts_dir).glob('*.outcome.json')) if Path(receipts_dir).is_dir() else []:
        try:
            usage = json.loads(path.read_text())['server_reported_usage']
        except (OSError, ValueError, KeyError, TypeError):
            unknown += 1
            continue
        if usage.get('usage_known'):
            known['prompt_tokens'] += usage['prompt_tokens']
            known['completion_tokens'] += usage['completion_tokens']
        else:
            unknown += 1
    return dict(known, outcomes_with_unknown_usage=unknown,
                note='summed over outcome records whose server reported usage; unknown usage is never counted as 0')


def main(argv=None):
    args = parse_args(argv)
    layout = A.Layout()
    run_dir = Path(args.run_dir)
    try:
        frozen, plan_row = admit(args, layout)
        import httpx
        import minisweagent
        A.check_running_runtime(frozen, site_packages=Path(httpx.__file__).resolve().parents[1],
                                mswea_package=Path(minisweagent.__file__).resolve().parent)
    except A.AdmissionRefused as exc:
        print(json.dumps(dict(admitted=False, run_id=args.run_id, reasons=exc.reasons)), file=sys.stderr)
        return EXIT_ADMISSION_REFUSED
    WC.write_once(run_dir / 'admission.json', json.dumps(dict(
        admitted=True, request=REQUEST, cohort=A.COHORT, run_id=args.run_id, position=args.position,
        assignment_id=plan_row['assignment_id'], arm=args.arm, binding_sha256=frozen['binding_sha256'],
        episode_source_sha256=SOURCE_SHA256, validated_utc=A.utc()), indent=1) + '\n')
    deadline = min(args.episode_deadline, args.block_deadline)

    def alarm(_signum, _frame):
        raise PE.EpisodeDeadline('absolute inference deadline reached; cleanup only')
    signal.signal(signal.SIGALRM, alarm)
    PE.request_timeout(deadline)
    signal.setitimer(signal.ITIMER_REAL, max(1e-6, deadline - time.time()))
    return run_episode(args, layout, frozen, plan_row, deadline)


def run_episode(args, layout, frozen, plan_row, deadline):
    import litellm
    import pandas as pd
    import requests
    import yaml
    from minisweagent.agents.default import DefaultAgent
    from minisweagent.environments.docker import DockerEnvironment
    from minisweagent.exceptions import FormatError
    from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel

    run_dir = Path(args.run_dir)
    existing_cap = T.existing_cleanup_cap(args.episode_deadline, args.block_deadline)
    attempts_path, calls_path = run_dir / 'attempts.jsonl', run_dir / 'calls.jsonl'
    attempts = []
    calls = LogicalCalls(arm=args.arm, log_path=calls_path)
    state = dict(env=None, agent=None, capture=None, session=None, install=None, props={}, image_id=None,
                 image_ref='sweb.eval.x86_64.%s:latest' % args.instance, config_record=None, base_tree=None,
                 capture_error=None,
                 runtime_check='the running SDK and mini-swe-agent files are the bound bytes (checked at admission)')
    exit_status, err, abort = None, None, None
    endpoint = dict(exit_status=None, submission='', final_tree=None, capture_error=None, error=None)
    t0 = time.time()
    try:
        WC.write_once(attempts_path, '')
        WC.write_once(calls_path, '')
        cfg_path = PE.MSWEA / 'src/minisweagent/config/default.yaml'
        if PE.sha(cfg_path.read_bytes()) != PE.DEFAULT_YAML_SHA:
            raise SystemExit('default.yaml differs from the lead pin')
        cfg = yaml.safe_load(cfg_path.read_text())
        row = next(r for r in pd.read_parquet(PE.DATA).to_dict('records') if r['instance_id'] == args.instance)
        state['image_id'] = subprocess.run(
            [PE.DOCKER, 'image', 'inspect', '--format', '{{.Id}}', state['image_ref']], capture_output=True,
            text=True, check=True).stdout.strip()
        if state['image_id'] != args.expected_image:
            raise SystemExit('image %s is %s, frozen frame pins %s' % (state['image_ref'], state['image_id'],
                                                                     args.expected_image))
        effective_cfg = PE.build_effective_config(cfg, alias=args.alias, port=args.port, image_id=state['image_id'])
        state['props'] = requests.get('http://127.0.0.1:%d/props' % args.port, timeout=10).json()
        # receipts and the capture BEFORE the container and before the first completion
        identity = dict(model=dict(alias=args.alias, model_sha256=plan_row['model_sha256'], backend=args.backend),
                        decoding=dict(temperature=0.0, max_tokens=PE.MAX_TOKENS),
                        server=dict(endpoint='http://127.0.0.1:%d/v1' % args.port, served=json.loads(args.served)),
                        tokenizer=dict(source=TOKENIZER_SOURCE))
        store = CT.BoundedReceiptStore(layout.root / A.PRIVATE_RECEIPTS_REL / args.run_id, run_dir / A.RECEIPTS_SUBDIR,
                                       cohort=A.COHORT, identity=identity, run_id=args.run_id, root=layout.root)
        state['capture'] = capture = CT.CueTransportCapture(
            store, budget=CT.RequestBudget(used=args.counted_before, limit=args.counted_before + args.request_limit),
            host_reserve_bytes=args.host_reserve_bytes)
        state['session'], state['install'] = CT.install_litellm_session(litellm, capture)
        model_class = make_model_class(LitellmTextbasedModel, FormatError, deadline=deadline, capture=capture,
                                       calls=calls, attempts_path=attempts_path, attempts=attempts, run_dir=run_dir)
        model = model_class(**effective_cfg['model'])

        class CueDockerEnvironment(DockerEnvironment):
            """The frozen cp2 environment; cleanup goes through the terminal phase with its computed deadline."""

            def _start_container(self):
                super()._start_container()
                WC.write_once(run_dir / 'container_ownership.json',
                              json.dumps(dict(container_id=self.container_id, run_id=args.run_id)) + '\n')

            def cleanup_until(self, cleanup_deadline):
                if not hasattr(self, '_cleanup_receipt'):
                    self._cleanup_receipt = PE.cleanup_owned_container(getattr(self, 'container_id', None),
                                                                       cleanup_deadline)
                    WC.write_once(run_dir / 'container_cleanup.json', json.dumps(self._cleanup_receipt) + '\n')
                return self._cleanup_receipt

            def cleanup(self):
                return self.cleanup_until(existing_cap)       # upstream __del__ never launches an async shell

            def container_platform(self):
                if not hasattr(self, '_cplat'):
                    self._cplat = {k: self.execute({'command': 'uname -%s' % f}).get('output', '').strip()
                                   for k, f in (('system', 's'), ('release', 'r'), ('version', 'v'), ('machine', 'm'))}
                return self._cplat

            def get_template_vars(self, **kwargs):
                return {**super().get_template_vars(**kwargs), **self.container_platform()}

        state['env'] = env = CueDockerEnvironment(**effective_cfg['environment'])
        ex = lambda cmd: (lambda o: (o.get('returncode'), o.get('output', '')))(env.execute({'command': cmd}))  # noqa
        state['ex'] = ex
        try:
            state['base_tree'] = WC.tree(ex)
        except WC.CaptureError as e:
            state['capture_error'] = 'base: %s' % e
        agent_cfg = effective_cfg['agent']
        state['agent'] = agent = DefaultAgent(model, env, **agent_cfg)
        state['config_record'] = config_receipt(effective_cfg, agent, model, env)
        WC.write_once(run_dir / 'effective_config.json', json.dumps(state['config_record'], indent=1) + '\n')
        t0 = time.time()
        info = agent.run(row['problem_statement'])
        exit_status = info.get('exit_status')
        # the frozen Submitted-only rule, determined INSIDE the inference window as the frozen driver does
        endpoint = T.submitted_only_endpoint(exit_status, state['base_tree'], ex,
                                             base_capture_error=state['capture_error'])
        exit_status, err = endpoint['exit_status'], endpoint['error']
    except Exception as e:  # noqa: BLE001  retained, never dropped (the frozen outer handler)
        exit_status, err = type(e).__name__, str(e)[:500]
        endpoint = dict(exit_status=exit_status, submission='', final_tree=None,
                        capture_error=state['capture_error'], error=err)
    except BaseException as e:  # noqa: BLE001  an operator abort or a frozen SystemExit refusal: the terminal phase
        abort = e               # (endpoint, diagnostic, cleanup) and the records still run, then it is re-raised
        exit_status, err = type(e).__name__, str(e)[:500]
        endpoint = dict(exit_status=exit_status, submission='', final_tree=None,
                        capture_error=state['capture_error'], error=err)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)       # no inference remains; the terminal phase has its own bounds
    inference_end = time.time()
    wall = inference_end - t0
    env = state['env']
    argv_for = None
    if env is not None:
        try:
            argv_for = T.docker_exec_argv(env.config.executable, getattr(env, 'container_id', None),
                                          cwd=env.config.cwd, env=env.config.env, interpreter=env.config.interpreter)
        except ValueError:
            argv_for = None

    def cleanup(cleanup_deadline):
        if env is None:
            return dict(confirmed=False, state='unknown', reason='the environment was never created, so no '
                                                                 'episode-owned container id exists')
        return env.cleanup_until(cleanup_deadline)
    terminal = T.run_terminal_phase(endpoint=endpoint, inference_end=inference_end, existing_cap=existing_cap,
                                    cleanup=cleanup, argv_for=argv_for, base_tree=state['base_tree'],
                                    out_dir=run_dir, submission_path=run_dir / 'submission.diff')
    result = write_records(args, layout, frozen, plan_row, state, calls, attempts, terminal, exit_status, err, wall,
                           litellm)
    if abort is not None:
        raise abort
    return result


def config_receipt(effective_cfg, agent, model, env):
    payload = dict(configuration_binding=PE.CONFIGURATION_BINDING, driver=DRIVER, mini_swe_agent=PE.MINI_SWE_AGENT_PIN,
                   default_yaml_sha256=PE.DEFAULT_YAML_SHA, episode_source_sha256=SOURCE_SHA256,
                   frozen_driver_source_sha256=PE.EPISODE_SOURCE_SHA256, constructor_arguments=effective_cfg,
                   resolved=dict(agent=agent.config.model_dump(mode='json'), model=model.config.model_dump(mode='json'),
                                 environment=env.config.model_dump(mode='json')))
    digest = PE.sha(json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False))
    return dict(payload, effective_config_sha256=digest)


def write_records(args, layout, frozen, plan_row, state, calls, attempts, terminal, exit_status, err, wall, litellm):
    run_dir = Path(args.run_dir)
    agent, env, capture = state['agent'], state['env'], state['capture']
    if state['session'] is not None:
        litellm.client_session = None
        state['session'].close()
    delivery = calls.finish()
    WC.write_once(run_dir / 'cue_delivery.json', json.dumps(delivery, indent=1) + '\n')
    if agent is not None:
        agent.save(run_dir / 'trajectory.json', {'info': {'exit_status': exit_status, 'error': err}})
    integrity = capture.integrity() if capture is not None else dict(
        receipt_integrity='incomplete', reasons=['the transport capture was never constructed'],
        queue_may_continue=False, infrastructure_stop=False, stop_reason=None, frozen_path_parity=None,
        deadline_reached=None, budget=None, store=None)
    frozen_endpoint = terminal['endpoint']
    record = terminal['record']
    per_call = {}
    for a in attempts:
        per_call[a['call']] = per_call.get(a['call'], 0) + 1
    storage_resolved = bool(integrity.get('queue_may_continue'))
    props = state['props'] or {}
    episode = dict(
        kind='cue-v1 fixed-order DEV episode (DTR-REQ-005); descriptive, not a causal effect, not CONFIRM',
        request=REQUEST, cohort=A.COHORT, driver=DRIVER, run_id=args.run_id, position=args.position,
        assignment_id=plan_row['assignment_id'], arm=args.arm, detector_mode=CC.MODE_BY_ARM[args.arm],
        instance_id=args.instance, backend=args.backend, backend_alias=args.alias, served=json.loads(args.served),
        server=dict(port=args.port, total_slots=props.get('total_slots'),
                    n_ctx_per_slot=props.get('default_generation_settings', {}).get('n_ctx'),
                    model_file=Path(props.get('model_path') or '').name),
        pins=dict(mini_swe_agent=PE.MINI_SWE_AGENT_PIN, default_yaml_sha256=PE.DEFAULT_YAML_SHA,
                  image_ref=state['image_ref'], image_id=state['image_id']),
        binding_sha256=frozen['binding_sha256'], episode_source_sha256=SOURCE_SHA256,
        frozen_driver_source_sha256=PE.EPISODE_SOURCE_SHA256, configuration_binding=PE.CONFIGURATION_BINDING,
        effective_config_sha256=(state['config_record'] or {}).get('effective_config_sha256'),
        runtime_check=state['runtime_check'], transport_install=state['install'],
        settings=dict(step_limit=PE.H, cost_limit=0.0, wall_time_limit_seconds=PE.WALL_S, temperature=0.0,
                      max_tokens=PE.MAX_TOKENS, command_timeout_s=PE.CMD_TIMEOUT,
                      physical_attempts_per_call_max=PE.ATTEMPTS_PER_CALL, request_timeout_s=PE.REQUEST_TIMEOUT_S),
        workspace_binding='wc2', template_platform_binding='cp2',
        container_platform=env.container_platform() if env is not None and hasattr(env, '_cplat') else None,
        base_tree=state['base_tree'], final_tree=frozen_endpoint.get('final_tree'),
        capture_error=frozen_endpoint.get('capture_error'),
        exit_status=frozen_endpoint.get('exit_status'), error=frozen_endpoint.get('error') or err,
        submission_sha256=frozen_endpoint.get('submission_sha256'),
        submission_bytes=frozen_endpoint.get('submission_utf8_bytes'),
        submission_empty=frozen_endpoint.get('submission_empty'),
        endpoint_file=record.get('endpoint_write'), endpoint_check_after_cleanup=record.get(
            'endpoint_check_after_cleanup'),
        n_model_calls=getattr(agent, 'n_calls', None), logical_calls=calls.current, wall_seconds=wall,
        physical_requests=len(capture.sends) if capture is not None else 0,
        attempt_ledger_rows=len(attempts), max_attempts_on_one_call=max(per_call.values()) if per_call else 0,
        failed_attempts=sum(a.get('ok') is False for a in attempts),
        incomplete_attempt_results=sum('ok' not in a for a in attempts),
        server_reported_usage=_usage_totals(run_dir / A.RECEIPTS_SUBDIR),
        cue={k: delivery[k] for k in ('state', 'triggered', 'pattern', 'trigger_call_id', 'planned_delivery_call_id',
                                      'message_appended', 'message_appended_call_id', 'transport_attempted',
                                      'response_received', 'cue_emissions', 'baseline_landmark_call_reached',
                                      'records_fed', 'records_fed_call_ids_consecutive', 'cue_sha256')},
        receipt_integrity=dict((k, integrity.get(k)) for k in (
            'receipt_integrity', 'reasons', 'infrastructure_stop', 'stop_reason', 'queue_may_continue',
            'deadline_reached', 'frozen_path_parity', 'budget')),
        storage_integrity='resolved' if storage_resolved else 'unresolved',
        storage_integrity_detail=None if storage_resolved else '; '.join(
            (integrity.get('reasons') or []) + ([('infrastructure stop: %s' % integrity.get('stop_reason'))]
                                                if integrity.get('infrastructure_stop') else []))[:DETAIL_CHARS],
        terminal_phase=dict(plan_state=(record.get('plan') or {}).get('state'),
                            diagnostic_status=(record.get('diagnostic') or {}).get('status'),
                            cleanup_state=(record.get('cleanup') or {}).get('state'),
                            cleanup_reserve_intact=(record.get('cleanup') or {}).get('reserve_intact'),
                            timing=record.get('timing')),
        container_cleanup=getattr(env, '_cleanup_receipt', None) if env is not None else None)
    WC.write_once(run_dir / 'episode.json', json.dumps(episode, indent=1) + '\n')
    print(json.dumps({k: episode[k] for k in ('run_id', 'arm', 'exit_status', 'logical_calls', 'physical_requests',
                                               'storage_integrity')}))
    return 0


# ---------------------------------------------------------------- the runner's episode function

def episode_argv(row, context, *, python, port, alias, expected_image, served, episode_deadline, block_deadline,
                 host_reserve_bytes):
    """The argv a live runner would launch for one assignment (in the pinned interpreter). Pure."""
    return [str(python), str(Path(__file__).resolve()), '--instance', row['instance_id'], '--backend', row['backend'],
            '--arm', row['arm'], '--position', str(row['position']), '--port', str(port), '--alias', alias,
            '--run-dir', str(context['run_dir']), '--run-id', context['run_id'], '--expected-image', expected_image,
            '--served', json.dumps(served, sort_keys=True), '--episode-deadline', repr(float(episode_deadline)),
            '--block-deadline', repr(float(block_deadline)),
            '--counted-before', str(context['counted_physical_requests_before']),
            '--request-limit', str(context['assignment_request_limit']),
            '--host-reserve-bytes', str(int(host_reserve_bytes))]


def run_assignment(row, context):
    """The only episode function cue_runner admits in the real checkout. The live comparison is held."""
    raise LiveReleaseHeld('cue-v1 live release is held by the lead (docs/theory_feedback_20260923_req005_review.md): '
                          'no host/server step exists here, and no episode is launched for %s' % row['assignment_id'])


if __name__ == '__main__':
    sys.exit(main())
