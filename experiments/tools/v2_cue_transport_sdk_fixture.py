"""Pinned-SDK observer for experiments/tools/test_v2_cue_transport.py (DTR-REQ-005 cue-v1 transport capture).

Run only by that test, through the pinned mini-swe-agent venv (litellm 1.102.0, openai 2.54.0, httpx 0.28.1):

    work/venvs/minisweagent_04d809c/bin/python experiments/tools/v2_cue_transport_sdk_fixture.py <out_dir>

It observes and records; it asserts nothing. The test holds every expected value as a hand-written literal. It
compares them with the summary printed here and with the files left in <out_dir>: the bytes the terminal received
(terminal/NNN.body) and the private raw bodies and public receipts the capture wrote.

Every scenario goes through the REAL `litellm.completion` path. Most go through the real mini-swe-agent
`LitellmTextbasedModel.query` too (tenacity stop-after-2 from the frozen `pilot_episode` import,
`_prepare_messages_for_api`), with the capture installed at `litellm.client_session` by
`cue_transport.install_litellm_session`. The terminal is an in-process `httpx.MockTransport`. It reads the body by
iterating `request.stream`, which is what `httpx.HTTPTransport` hands to httpcore. No model, llama-server,
container or network is used: a socket tripwire refuses and records any connect/DNS attempt, and
LITELLM_LOCAL_MODEL_COST_MAP is set before import so litellm does not fetch its remote cost map.
"""
from __future__ import annotations

import errno
import os
import sys
from pathlib import Path

OUT = Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
os.environ['MSWEA_SILENT_STARTUP'] = '1'
(OUT / 'mswea_config').mkdir(exist_ok=True)
os.environ['MSWEA_GLOBAL_CONFIG_DIR'] = str(OUT / 'mswea_config')

import socket  # noqa: E402

NETWORK_ATTEMPTS = []


def _tripwire(name):
    def deny(*_a, **_k):
        NETWORK_ATTEMPTS.append(name)
        raise OSError('cue_transport fixture network tripwire: %s refused' % name)
    return deny


socket.socket.connect = _tripwire('socket.connect')
socket.socket.connect_ex = _tripwire('socket.connect_ex')
socket.create_connection = _tripwire('socket.create_connection')
socket.getaddrinfo = _tripwire('socket.getaddrinfo')

import hashlib  # noqa: E402
import json  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/v2_agent'))

import httpx  # noqa: E402
import litellm  # noqa: E402
import yaml  # noqa: E402

import pilot_episode as PE  # noqa: E402  frozen driver, imported read-only (pins, build_effective_config, env)
import cue_detector as CD  # noqa: E402
import cue_transport as CT  # noqa: E402
import request_receipt as RR  # noqa: E402
from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel  # noqa: E402

litellm.suppress_debug_info = True

ALIAS = 'qwen2.5-coder-7b-instruct-c03e6d3-q4_k_m'
PORT = 8291
URL = 'http://127.0.0.1:%d/v1/chat/completions' % PORT
FAKE_HOME = '/Users/example-worker'
EPOCH = 1790150400.0
RESERVE = 20 * CT.GiB
PLENTY = RESERVE + CT.START_FREE_ABOVE_RESERVE_BYTES + CT.GiB
IDENTITY = dict(model=dict(alias=ALIAS, model_sha256='1' * 64), decoding=dict(temperature=0.0, max_tokens=1536),
                server=dict(endpoint='http://127.0.0.1:%d/v1' % PORT), tokenizer=dict(source='fixture'))

cfg_path = PE.MSWEA / 'src/minisweagent/config/default.yaml'
if hashlib.sha256(cfg_path.read_bytes()).hexdigest() != PE.DEFAULT_YAML_SHA:
    raise SystemExit('default.yaml differs from the lead pin')
EFFECTIVE = PE.build_effective_config(yaml.safe_load(cfg_path.read_text()), alias=ALIAS, port=PORT,
                                      image_id='sha256:' + '0' * 64, executable='/nonexistent/docker')
MODEL_CFG = EFFECTIVE['model']
FROZEN_KWARGS = dict(MODEL_CFG['model_kwargs'], timeout=PE.REQUEST_TIMEOUT_S)   # AccountedModel._query override

OK_CONTENT = 'THOUGHT: probe\n\n```mswea_bash_command\necho probe\n```'
OK_BODY = {'id': 'chatcmpl-fixture', 'object': 'chat.completion', 'created': 1790000000, 'model': ALIAS,
           'choices': [{'index': 0, 'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': OK_CONTENT}}],
           'usage': {'prompt_tokens': 123, 'completion_tokens': 7, 'total_tokens': 130}}
OK_200 = (200, OK_BODY, {})
OK_200_NO_USAGE = (200, {k: v for k, v in OK_BODY.items() if k != 'usage'}, {})
E500 = (500, {'error': {'code': 500, 'message': 'fixture canned internal error', 'type': 'server_error'}}, {})
E400_CTX = (400, {'error': {'code': 400, 'type': 'exceed_context_size_error', 'n_prompt_tokens': 16610,
                            'n_ctx': 16384, 'message': 'request (16610 tokens) exceeds the available context '
                                                       'size (16384 tokens), try increasing it'}}, {})
E400_ROLES = (400, {'error': {'code': 400, 'type': 'invalid_request_error',
                              'message': 'Conversation roles must alternate user/assistant/user/assistant/...'}}, {})
R307 = (307, None, {'location': URL})

MESSAGES = [
    {'role': 'system', 'content': 'You are a helpful assistant that can interact with a computer.'},
    {'role': 'user', 'content': 'Fix the bug in /testbed. Non-ASCII check: naïve café — µs.'},
    {'role': 'assistant', 'content': 'THOUGHT: look first\n\n```mswea_bash_command\nls /testbed\n```'},
    {'role': 'user', 'content': '<returncode>0</returncode>\n<output>\nsetup.py\n</output>'},
]
CUE_MESSAGES = MESSAGES + [{'role': 'user', 'content': CD.CUE_TEXT}]
OVERSIZED_MESSAGES = [{'role': 'user', 'content': 'x' * (8 * 1024 * 1024)}]
MULTIBYTE_MESSAGES = [{'role': 'user', 'content': '€' * 30000}]


class Terminal:
    """In-process stand-in for the pinned HTTPTransport: records exactly what it would put on the wire."""

    def __init__(self, directory, script, default=None):
        self.directory, self.script, self.default = directory, list(script), default
        self.received = []
        self.directory.mkdir(parents=True, exist_ok=True)
        self.transport = httpx.MockTransport(self.handle)

    def handle(self, request):
        wire = b''.join(request.stream)
        (self.directory / ('%03d.body' % (len(self.received) + 1))).write_bytes(wire)
        self.received.append(dict(url=str(request.url), bytes=len(wire),
                                  content_length=request.headers.get('content-length'),
                                  retry_count=request.headers.get('x-stainless-retry-count'),
                                  has_authorization='authorization' in request.headers))
        status, body, headers = self.script.pop(0) if self.script else self.default
        content = b'' if body is None else json.dumps(body).encode()
        return httpx.Response(status, content=content, headers={'content-type': 'application/json', **headers})


class CaptureModel(LitellmTextbasedModel):
    """Test harness showing how a cue-v1 driver composes the capture. It is not the driver. Logical ids come from
    query(), and each tenacity attempt is one dispatch."""
    abort_exceptions = LitellmTextbasedModel.abort_exceptions + [CT.InfrastructureStop]

    def __init__(self, capture, **kw):
        super().__init__(**kw)
        self.capture, self.logical, self.attempt = capture, 0, 0

    def query(self, messages, **kw):
        self.logical += 1
        self.attempt = 0
        return super().query(messages, **kw)

    def _query(self, messages, **kw):
        self.attempt += 1
        return self.capture.dispatch(logical_call_id=self.logical, query_attempt=self.attempt,
                                     call=lambda: super(CaptureModel, self)._query(messages, **kw))


def failing_writer(suffix):
    def write(path, data):
        if str(path).endswith(suffix):
            raise OSError(errno.ENOSPC, 'simulated: no space left on device')
        return RR._write_once(path, data)
    return write


def exc_info(e):
    chain, cur = [], e
    while cur is not None and len(chain) < 6:
        chain.append('%s.%s' % (type(cur).__module__, type(cur).__qualname__))
        cur = cur.__cause__ or cur.__context__
    return dict(ok=False, exception=chain[0], chain=chain[1:], status_code=getattr(e, 'status_code', None),
                refusal_reason=getattr(getattr(e, 'refusal', None), 'get', lambda _k: None)('reason_code'))


def listing(directory):
    directory = Path(directory)
    if not directory.exists():
        return {}
    return {p.name: p.stat().st_size for p in sorted(directory.iterdir()) if p.is_file()}


def run(name, script, *, default=None, messages=MESSAGES, via='model', budget_used=0, sends_per_attempt=1,
        free=None, write_once=None, kwargs=None, then=None):
    d = OUT / name
    root = d / 'root'
    private, public = root / 'work' / 'receipts', root / 'published'
    litellm.in_memory_llm_clients_cache.flush_cache()
    store = CT.BoundedReceiptStore(private, public, cohort='cue-v1', run_id='fixture-' + name, identity=IDENTITY,
                                   home=FAKE_HOME, clock=lambda: EPOCH, root=root, write_once=write_once)
    capture = CT.CueTransportCapture(store, budget=CT.RequestBudget(used=budget_used), host_reserve_bytes=RESERVE,
                                     free_space_probe=free or (lambda _path: PLENTY),
                                     sends_per_query_attempt=sends_per_attempt, clock=lambda: EPOCH,
                                     accounting_fixture=sends_per_attempt != 1)
    term = Terminal(d / 'terminal', script, default)
    session, install = CT.install_litellm_session(litellm, capture, inner=term.transport)
    outcomes = []
    model = CaptureModel(capture, **MODEL_CFG)
    calls = 1 if then is None else 2
    for _ in range(calls):
        try:
            if via == 'model':
                msg = model.query(messages, timeout=PE.REQUEST_TIMEOUT_S)
                outcomes.append(dict(ok=True, content=msg['content'], actions=msg['extra']['actions'],
                                     litellm_usage={k: msg['extra']['response']['usage'].get(k) for k in
                                                    ('prompt_tokens', 'completion_tokens', 'total_tokens')}))
            else:
                r = capture.dispatch(logical_call_id=1, query_attempt=1, call=lambda: litellm.completion(
                    model=MODEL_CFG['model_name'], messages=messages, **(kwargs or FROZEN_KWARGS)))
                outcomes.append(dict(ok=True, content=r.choices[0].message.content))
        except BaseException as e:  # noqa: BLE001  observed and recorded
            outcomes.append(exc_info(e))
    bindings = CT.session_binding_violations(litellm, session)
    clients = [dict(max_retries=c.max_retries, wraps_capture_session=c._client is session)
               for c in litellm.in_memory_llm_clients_cache.cache_dict.values() if hasattr(c, 'max_retries')]
    litellm.client_session = None
    session.close()
    integrity = capture.integrity()
    return dict(
        scenario=name, install=install, outcomes=outcomes, terminal=term.received,
        sends=[{k: v for k, v in t.items() if k not in ('response', 'free_space')} for t in capture.sends],
        refusals=[{k: r.get(k) for k in ('refusal_ordinal', 'reason_code', 'classification', 'infrastructure_stop',
                                         'logical_call_id', 'query_attempt_id', 'body_sha256', 'body_bytes',
                                         'free_space', 'detail', 'physical_request', 'record_written')}
                  for r in capture.refusals],
        attempts=[{k: v for k, v in a.items() if k not in ('started_utc', 'ended_utc')} for a in capture.attempts],
        integrity={k: integrity[k] for k in ('receipt_integrity', 'reasons', 'infrastructure_stop', 'stop_reason',
                                             'queue_may_continue', 'physical_sends', 'refusals', 'budget',
                                             'frozen_path_parity', 'deadline_reached')},
        bookkeeping_failures=[{k: f.get(k) for k in ('attempt_key', 'phase', 'error_class', 'secondary_log_written')}
                              for f in capture.bookkeeping_failures],
        store_complete=integrity['store'].get('complete'),
        store_holes={k: integrity['store'].get(k) for k in ('raw_without_published_record',
                                                            'published_record_without_raw',
                                                            'published_record_without_outcome',
                                                            'invalid_records')},
        private_files=listing(private), public_files=listing(public),
        binding_violations=bindings, openai_clients=clients)


def low_space_after_start():
    calls = []

    def probe(_path):
        calls.append(1)
        return PLENTY if len(calls) <= 2 else RESERVE + 1000     # the start preflight probes two directories
    return probe


def install_preflight():
    """The installer refuses when a hidden-send path or a pre-cached client exists."""
    out = []
    for label, setup, undo in (
            ('cached client present', lambda: litellm.in_memory_llm_clients_cache.cache_dict.__setitem__(
                'x', __import__('openai').OpenAI(api_key='none', base_url='http://127.0.0.1:%d/v1' % PORT)),
             lambda: litellm.in_memory_llm_clients_cache.flush_cache()),
            ('global num_retries', lambda: setattr(litellm, 'num_retries', 3),
             lambda: setattr(litellm, 'num_retries', None)),
            ('global drop_params', lambda: setattr(litellm, 'drop_params', True),
             lambda: setattr(litellm, 'drop_params', False))):
        d = OUT / 'install_preflight' / label.replace(' ', '_')
        litellm.in_memory_llm_clients_cache.flush_cache()
        store = CT.BoundedReceiptStore(d / 'work' / 'receipts', d / 'published', cohort='cue-v1',
                                       run_id='fixture-install', identity=IDENTITY, home=FAKE_HOME,
                                       clock=lambda: EPOCH, root=d)
        capture = CT.CueTransportCapture(store, budget=CT.RequestBudget(used=0), host_reserve_bytes=RESERVE,
                                         free_space_probe=lambda _p: PLENTY, clock=lambda: EPOCH)
        setup()
        try:
            CT.install_litellm_session(litellm, capture, inner=httpx.MockTransport(lambda r: httpx.Response(599)))
            result = dict(ok=True)
        except BaseException as e:  # noqa: BLE001
            result = exc_info(e)
        undo()
        out.append(dict(label=label, outcome=result, session_installed=litellm.client_session is not None,
                        stop_reason=None if capture.stopped is None else capture.stopped['reason_code'],
                        detail=None if capture.stopped is None else capture.stopped['detail']))
        litellm.client_session = None
    return out


def bypassed_session():
    """A send that bypasses the capture session is detected after the call and stops the episode."""
    d = OUT / 'bypassed_session'
    litellm.in_memory_llm_clients_cache.flush_cache()
    store = CT.BoundedReceiptStore(d / 'root' / 'work' / 'receipts', d / 'root' / 'published', cohort='cue-v1',
                                   run_id='fixture-bypass', identity=IDENTITY, home=FAKE_HOME, clock=lambda: EPOCH,
                                   root=d / 'root')
    capture = CT.CueTransportCapture(store, budget=CT.RequestBudget(used=0), host_reserve_bytes=RESERVE,
                                     free_space_probe=lambda _p: PLENTY, clock=lambda: EPOCH)
    captured = Terminal(d / 'captured_terminal', [], OK_200)
    other = Terminal(d / 'other_terminal', [], OK_200)
    session, _ = CT.install_litellm_session(litellm, capture, inner=captured.transport)
    litellm.client_session = httpx.Client(transport=other.transport)       # simulated mis-wiring
    try:
        capture.dispatch(logical_call_id=1, query_attempt=1, call=lambda: litellm.completion(
            model=MODEL_CFG['model_name'], messages=MESSAGES, **FROZEN_KWARGS))
        result = dict(ok=True)
    except BaseException as e:  # noqa: BLE001
        result = dict(exc_info(e), result_attached=getattr(e, 'result', None) is not None)
    litellm.client_session.close()
    litellm.client_session = None
    session.close()
    return dict(outcome=result, captured_terminal=len(captured.received), other_terminal=len(other.received),
                stop_reason=None if capture.stopped is None else capture.stopped['reason_code'],
                sends=len(capture.sends))


def non_replayable_body():
    """A streaming (iterator) body is refused unread, before the terminal."""
    d = OUT / 'non_replayable'
    store = CT.BoundedReceiptStore(d / 'root' / 'work' / 'receipts', d / 'root' / 'published', cohort='cue-v1',
                                   run_id='fixture-stream', identity=IDENTITY, home=FAKE_HOME, clock=lambda: EPOCH,
                                   root=d / 'root')
    capture = CT.CueTransportCapture(store, budget=CT.RequestBudget(used=0), host_reserve_bytes=RESERVE,
                                     free_space_probe=lambda _p: PLENTY, clock=lambda: EPOCH)
    term = Terminal(d / 'terminal', [], OK_200)
    client = httpx.Client(transport=CT.CapturingTransport(term.transport, capture), follow_redirects=False)
    consumed = []

    def gen():
        consumed.append(1)
        yield b'{"messages":[]}'
    try:
        capture.dispatch(logical_call_id=1, query_attempt=1, call=lambda: client.post(URL, content=gen()))
        result = dict(ok=True)
    except BaseException as e:  # noqa: BLE001
        result = exc_info(e)
    client.close()
    return dict(outcome=result, terminal=len(term.received), generator_consumed=bool(consumed),
                refusals=[r['reason_code'] for r in capture.refusals], private_files=listing(store.private_dir))


def cached_client_bypass():
    """A cached openai client that does not wrap the capture session is found by the post-call binding check."""
    import openai
    d = OUT / 'cached_client_bypass'
    litellm.in_memory_llm_clients_cache.flush_cache()
    store = CT.BoundedReceiptStore(d / 'root' / 'work' / 'receipts', d / 'root' / 'published', cohort='cue-v1',
                                   run_id='fixture-cached', identity=IDENTITY, home=FAKE_HOME, clock=lambda: EPOCH,
                                   root=d / 'root')
    capture = CT.CueTransportCapture(store, budget=CT.RequestBudget(used=0), host_reserve_bytes=RESERVE,
                                     free_space_probe=lambda _p: PLENTY, clock=lambda: EPOCH)
    captured = Terminal(d / 'captured_terminal', [], OK_200)
    other = Terminal(d / 'other_terminal', [], OK_200)
    session, _ = CT.install_litellm_session(litellm, capture, inner=captured.transport)
    foreign = openai.OpenAI(api_key='none', base_url='http://127.0.0.1:%d/v1' % PORT, max_retries=0,
                            http_client=httpx.Client(transport=other.transport))
    litellm.in_memory_llm_clients_cache.cache_dict['foreign-client'] = foreign
    try:
        capture.dispatch(logical_call_id=1, query_attempt=1, call=lambda: litellm.completion(
            model=MODEL_CFG['model_name'], messages=MESSAGES, **FROZEN_KWARGS))
        result = dict(ok=True)
    except BaseException as e:  # noqa: BLE001
        result = dict(exc_info(e), result_attached=getattr(e, 'result', None) is not None)
    litellm.in_memory_llm_clients_cache.flush_cache()
    litellm.client_session = None
    session.close()
    return dict(outcome=result, captured_terminal=len(captured.received), other_terminal=len(other.received),
                stop_reason=None if capture.stopped is None else capture.stopped['reason_code'],
                detail=None if capture.stopped is None else capture.stopped['detail'], sends=len(capture.sends))


def bytestream_subclass():
    """A ByteStream SUBCLASS (which could yield other bytes to the terminal) is refused unread."""
    d = OUT / 'bytestream_subclass'
    store = CT.BoundedReceiptStore(d / 'root' / 'work' / 'receipts', d / 'root' / 'published', cohort='cue-v1',
                                   run_id='fixture-subclass', identity=IDENTITY, home=FAKE_HOME, clock=lambda: EPOCH,
                                   root=d / 'root')
    capture = CT.CueTransportCapture(store, budget=CT.RequestBudget(used=0), host_reserve_bytes=RESERVE,
                                     free_space_probe=lambda _p: PLENTY, clock=lambda: EPOCH)
    term = Terminal(d / 'terminal', [], OK_200)

    class Stateful(httpx.ByteStream):
        def __init__(self, first, later):
            super().__init__(first)
            self.later, self.reads = later, 0

        def __iter__(self):
            self.reads += 1
            yield self._stream if self.reads <= 2 else self.later
    transport = CT.CapturingTransport(term.transport, capture)
    request = httpx.Request('POST', URL, stream=Stateful(b'{"a":"AAAA"}', b'{"a":"BBBB"}'),
                            headers={'content-type': 'application/json'})
    try:
        capture.dispatch(logical_call_id=1, query_attempt=1, call=lambda: transport.handle_request(request))
        result = dict(ok=True)
    except BaseException as e:  # noqa: BLE001
        result = exc_info(e)
    return dict(outcome=result, terminal=len(term.received), refusals=[r['reason_code'] for r in capture.refusals],
                private_files=listing(store.private_dir))


def default_inner_parity():
    """The live default inner transport (httpx.HTTPTransport built by install_litellm_session with inner=None)
    against litellm's own frozen default client: both reach the SAME HTTPTransport.handle_request, patched here to
    record the request and answer in-process (no socket)."""
    d = OUT / 'default_inner_parity'
    seen = []
    real = httpx.HTTPTransport.handle_request

    def recording(self, request):
        seen.append(dict(transport=type(self).__name__, body=b''.join(request.stream).decode('utf-8'),
                         headers=sorted([k.lower(), '<redacted>' if k.lower() == 'authorization' else v]
                                        for k, v in request.headers.multi_items()),
                         timeout=request.extensions.get('timeout'), url=str(request.url)))
        return httpx.Response(200, content=json.dumps(OK_BODY).encode(), headers={'content-type': 'application/json'})
    httpx.HTTPTransport.handle_request = recording
    session = None
    try:
        litellm.in_memory_llm_clients_cache.flush_cache()
        litellm.client_session = None
        LitellmTextbasedModel(**MODEL_CFG).query(MESSAGES, timeout=PE.REQUEST_TIMEOUT_S)     # frozen default client
        litellm.in_memory_llm_clients_cache.flush_cache()
        store = CT.BoundedReceiptStore(d / 'root' / 'work' / 'receipts', d / 'root' / 'published', cohort='cue-v1',
                                       run_id='fixture-default-inner', identity=IDENTITY, home=FAKE_HOME,
                                       clock=lambda: EPOCH, root=d / 'root')
        capture = CT.CueTransportCapture(store, budget=CT.RequestBudget(used=0), host_reserve_bytes=RESERVE,
                                         free_space_probe=lambda _p: PLENTY, clock=lambda: EPOCH)
        session, install = CT.install_litellm_session(litellm, capture)                   # inner=None: the live one
        CaptureModel(capture, **MODEL_CFG).query(MESSAGES, timeout=PE.REQUEST_TIMEOUT_S)
        private = (store.private_dir / 'call001_attempt01.request.raw').read_bytes().decode('utf-8')
    finally:
        httpx.HTTPTransport.handle_request = real
        litellm.client_session = None
        litellm.in_memory_llm_clients_cache.flush_cache()
        if session is not None:
            session.close()
    return dict(default=seen[0], captured=seen[1], sends=len(seen), inner_transport=install['inner_transport'],
                private_body=private)


def main():
    no_retry_kwargs = {k: v for k, v in FROZEN_KWARGS.items() if k != 'num_retries'}
    scenarios = [
        run('baseline_200', [OK_200]),
        run('cue_200', [OK_200], messages=CUE_MESSAGES),
        run('retry_500_then_200', [E500, OK_200]),
        run('context_400', [E400_CTX]),
        run('oversized_body', [], default=OK_200, messages=OVERSIZED_MESSAGES, then='again'),
        run('durable_write_failed', [], default=OK_200, write_once=failing_writer(RR.RAW_SUFFIX)),
        run('low_free_space', [], default=OK_200, free=low_space_after_start()),
        run('budget_exhausted', [], default=OK_200, budget_used=576),
        run('bookkeeping_failure_success', [OK_200], write_once=failing_writer(RR.OUTCOME_SUFFIX)),
        run('bookkeeping_failure_error', [E400_CTX], write_once=failing_writer(RR.OUTCOME_SUFFIX)),
        run('usage_omitted_by_server', [OK_200_NO_USAGE]),
        run('multibyte_over_64k', [OK_200], messages=MULTIBYTE_MESSAGES),
        run('hidden_second_pass_suppressed', [E400_ROLES], default=E500, via='completion'),
        run('sdk_retry_one_send', [], default=E500, via='completion', kwargs=no_retry_kwargs),
        run('sdk_retry_two_sends_allowed', [], default=E500, via='completion', kwargs=no_retry_kwargs,
            sends_per_attempt=2),
        run('redirect_not_followed', [R307, OK_200], via='completion'),
    ]
    summary = dict(
        fixture='DTR-REQ-005 cue-v1 transport capture through the pinned SDK path (no model/server/network)',
        python=sys.version.split()[0],
        versions={p: __import__('importlib.metadata').metadata.version(p)
                  for p in ('litellm', 'openai', 'httpx', 'tenacity', 'mini-swe-agent')},
        frozen_model_name=MODEL_CFG['model_name'], frozen_call_kwargs=FROZEN_KWARGS,
        scenarios={s['scenario']: s for s in scenarios},
        install_preflight=install_preflight(), bypassed_session=bypassed_session(),
        non_replayable=non_replayable_body(), cached_client_bypass=cached_client_bypass(),
        bytestream_subclass=bytestream_subclass(), default_inner_parity=default_inner_parity(),
        network_attempts=NETWORK_ATTEMPTS)
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=1, default=str) + '\n')
    print(json.dumps(dict(ok=True, scenarios=len(scenarios))))


if __name__ == '__main__':
    main()
