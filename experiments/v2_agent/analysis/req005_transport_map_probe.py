"""DTR-REQ-005 transport-map probe: where the pinned stack's final request bytes leave the process, and how
many physical sends one ``litellm.completion`` call can make.

Read-only research artifact (no model, no llama-server, no container, no network, nothing under results/).
Run ONLY with the pinned mini-swe-agent venv (litellm 1.102.0, openai 2.54.0, httpx 0.28.1):

    work/venvs/minisweagent_04d809c/bin/python experiments/v2_agent/analysis/req005_transport_map_probe.py

What it does
* Builds the model section exactly as the frozen driver does, by calling the frozen
  ``pilot_episode.build_effective_config`` on the pinned default.yaml (imported read-only, never edited), and
  calls the REAL ``litellm.completion(model=..., messages=..., **(model_kwargs | {'timeout': 900}))`` - the same
  expression as ``LitellmTextbasedModel._query`` with the frozen driver's per-call ``timeout`` override.
* Injects code we control at the pinned path's own hook, ``litellm.client_session`` (an ``httpx.Client``), whose
  transport is ``InterceptTransport`` wrapping an in-process ``httpx.MockTransport`` terminal that returns canned
  OpenAI-style responses. The terminal re-reads the body by iterating ``request.stream`` - what httpx's
  ``HTTPTransport`` hands to httpcore - so "intercepted bytes == received bytes" is checked on the wire iterator.
* A socket tripwire records and refuses any connect/DNS attempt; ``LITELLM_LOCAL_MODEL_COST_MAP=True`` is set
  before import because litellm otherwise GETs a remote cost map at import time.

The expected counts are stated in docs/req005_transport_map_20260923.md from source reading; this script only
prints what it observes. It is a probe, not a test, and asserts nothing about the stack beyond printing.
"""
from __future__ import annotations

import os
import sys
import tempfile

# --- environment that must exist BEFORE litellm / minisweagent are imported ---------------------------------
os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'      # litellm/litellm_core_utils/get_model_cost_map.py:626
os.environ['MSWEA_SILENT_STARTUP'] = '1'                  # minisweagent/__init__.py:30 (banner prints a home path)
_CFG_TMP = tempfile.mkdtemp(prefix='req005_transport_probe_')
os.environ['MSWEA_GLOBAL_CONFIG_DIR'] = _CFG_TMP          # minisweagent/__init__.py:26 (no host config dir touched)

import socket  # noqa: E402

NETWORK_ATTEMPTS: list[str] = []


def _tripwire(name):
    def deny(*_a, **_k):
        NETWORK_ATTEMPTS.append(name)
        raise OSError('req005 probe network tripwire: %s refused' % name)
    return deny


socket.socket.connect = _tripwire('socket.connect')
socket.socket.connect_ex = _tripwire('socket.connect_ex')
socket.create_connection = _tripwire('socket.create_connection')
socket.getaddrinfo = _tripwire('socket.getaddrinfo')

import hashlib  # noqa: E402
import importlib.metadata as md  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments/v2_agent'))

import httpx  # noqa: E402
import openai  # noqa: E402
import litellm  # noqa: E402
import yaml  # noqa: E402

import pilot_episode as PE  # noqa: E402  frozen driver, imported read-only for build_effective_config only
from litellm.llms.openai.common_utils import BaseOpenAILLM  # noqa: E402

litellm.suppress_debug_info = True                        # console noise only; not on the request path

ALIAS = 'qwen2.5-coder-7b-instruct-c03e6d3-q4_k_m'        # archived small-backend alias (yaml-v1 effective_config)
PORT = 8291
URL = 'http://127.0.0.1:%d/v1/chat/completions' % PORT
SITE = Path(litellm.__file__).resolve().parents[1]
PKG_FILES = ('litellm/main.py', 'litellm/utils.py', 'litellm/llms/openai/openai.py',
             'litellm/llms/openai/common_utils.py', 'openai/_base_client.py', 'openai/_client.py',
             'httpx/_client.py', 'httpx/_transports/default.py', 'httpx/_transports/mock.py')


def sha(b):
    return hashlib.sha256(b).hexdigest()


# --- canned terminal responses --------------------------------------------------------------------------------
OK_CONTENT = 'THOUGHT: probe\n\n```mswea_bash_command\necho probe\n```'
OK_200 = (200, {'id': 'chatcmpl-probe', 'object': 'chat.completion', 'created': 1790000000, 'model': ALIAS,
                'choices': [{'index': 0, 'finish_reason': 'stop',
                             'message': {'role': 'assistant', 'content': OK_CONTENT}}],
                'usage': {'prompt_tokens': 123, 'completion_tokens': 7, 'total_tokens': 130}}, {})
E500 = (500, {'error': {'code': 500, 'message': 'probe canned internal error', 'type': 'server_error'}}, {})
# message text is the archived llama-server context rejection; the JSON envelope/type is modelled, not archived
E400_CTX = (400, {'error': {'code': 400, 'type': 'exceed_context_size_error', 'n_prompt_tokens': 16610,
                            'n_ctx': 16384, 'message': 'request (16610 tokens) exceeds the available context '
                                                       'size (16384 tokens), try increasing it'}}, {})
E400_ROLES = (400, {'error': {'code': 400, 'type': 'invalid_request_error',
                              'message': 'Conversation roles must alternate user/assistant/user/assistant/...'}}, {})
E422_TEMP = (422, {'error': {'message': json.dumps({'detail': [{'loc': ['body', 'temperature'],
                                                                'msg': 'probe: unsupported'}]})}}, {})
R307 = (307, None, {'location': URL})


class Terminal:
    """In-process stand-in for the pinned HTTPTransport. Returns scripted responses; records the body bytes it
    receives by iterating request.stream (the iterator HTTPTransport passes to httpcore as content)."""

    def __init__(self, script, default=None):
        self.script = list(script)
        self.default = default
        self.received = []
        self.transport = httpx.MockTransport(self.handle)

    def handle(self, request):
        wire = b''.join(request.stream)
        self.received.append(dict(method=request.method, url=str(request.url), body=wire))
        status, body, headers = self.script.pop(0) if self.script else self.default
        content = b'' if body is None else json.dumps(body).encode()
        return httpx.Response(status, content=content, headers={'content-type': 'application/json', **headers})


class RefusedBeforeDispatch(openai.OpenAIError):
    """Raised by the interceptor INSTEAD of passing a request onward (budget exhausted or storage refusal)."""


class InterceptTransport(httpx.BaseTransport):
    """The code-we-control boundary: sees the finalized httpx.Request, retains its exact body bytes, then hands
    the SAME request object to the existing sender. Optional one-send-per-invocation budget and refuse-all."""

    def __init__(self, inner, *, sends_per_invocation=None, refuse_all=False):
        self.inner = inner
        self.limit = sends_per_invocation
        self.remaining = None
        self.refuse_all = refuse_all
        self.seen = []
        self.refused = []

    def begin_invocation(self):
        self.remaining = self.limit

    def handle_request(self, request):
        replayable = isinstance(request.stream, httpx.ByteStream)
        # read(), not .content: a redirect hop is rebuilt from the same ByteStream without pre-reading
        # (httpx/_client.py:483-490), so .content would raise RequestNotRead there
        body = request.read() if replayable else None
        rec = dict(method=request.method, url=str(request.url), body=body, stream_type=type(request.stream).__name__,
                   retry_count=request.headers.get('x-stainless-retry-count'),
                   content_length=request.headers.get('content-length'))
        if not replayable:
            self.refused.append(dict(rec, reason='non-replayable body'))
            raise RefusedBeforeDispatch('non-replayable request body refused before dispatch')
        if self.refuse_all or (self.remaining is not None and self.remaining <= 0):
            self.refused.append(dict(rec, reason='refuse_all' if self.refuse_all else 'send budget exhausted'))
            raise RefusedBeforeDispatch('probe refusal before dispatch (%s)' % (
                'refuse_all' if self.refuse_all else 'send budget exhausted'))
        if self.remaining is not None:
            self.remaining -= 1
        self.seen.append(rec)
        return self.inner.handle_request(request)

    def close(self):
        self.inner.close()


# --- the frozen model configuration ---------------------------------------------------------------------------
cfg_path = PE.MSWEA / 'src/minisweagent/config/default.yaml'
assert sha(cfg_path.read_bytes()) == PE.DEFAULT_YAML_SHA, 'default.yaml differs from the lead pin'
EFFECTIVE = PE.build_effective_config(yaml.safe_load(cfg_path.read_text()), alias=ALIAS, port=PORT,
                                      image_id='sha256:' + '0' * 64, executable='/nonexistent/docker')
MODEL_CFG = EFFECTIVE['model']
FROZEN_CALL_KWARGS = dict(MODEL_CFG['model_kwargs'], timeout=PE.REQUEST_TIMEOUT_S)  # AccountedModel._query override

MESSAGES = [
    {'role': 'system', 'content': 'You are a helpful assistant that can interact with a computer.'},
    {'role': 'user', 'content': 'Fix the bug. Non-ASCII check: naïve café — µs.'},
    {'role': 'assistant', 'content': OK_CONTENT},
    {'role': 'user', 'content': '<returncode>0</returncode>\n<output>\nprobe\n</output>'},
]


def exc_info(e):
    chain, cur = [], e
    while cur is not None and len(chain) < 6:
        chain.append('%s.%s' % (type(cur).__module__, type(cur).__qualname__))
        cur = cur.__cause__ or cur.__context__
    return dict(ok=False, exception=chain[0], status_code=getattr(e, 'status_code', None), chain=chain[1:])


def summarize(label, icpt, term, session, outcome, seconds):
    clients = [c for c in litellm.in_memory_llm_clients_cache.cache_dict.values() if isinstance(c, openai.OpenAI)]
    pairs = list(zip(icpt.seen, term.received))
    return dict(
        scenario=label,
        intercepted_sends=len(icpt.seen), terminal_received=len(term.received), refused_before_dispatch=len(icpt.refused),
        bytes_identical=(len(icpt.seen) == len(term.received) and all(a['body'] == b['body'] for a, b in pairs)),
        same_url=all(r['url'] == URL for r in term.received),
        body_sha256=[sha(r['body'])[:16] for r in icpt.seen], body_len=[len(r['body']) for r in icpt.seen],
        distinct_bodies=len({sha(r['body']) for r in icpt.seen}),
        retry_count_header=[r['retry_count'] for r in icpt.seen],
        stream_type=sorted({r['stream_type'] for r in icpt.seen + icpt.refused}),
        refusal_reasons=[r['reason'] for r in icpt.refused],
        openai_clients=[dict(max_retries=c.max_retries, wraps_injected_session=c._client is session) for c in clients],
        outcome=outcome, seconds=round(seconds, 2))


def run(label, script, *, default=None, follow_redirects=True, budget=None, refuse_all=False, extra=None,
        messages=MESSAGES, drop=(), global_drop_params=False):
    litellm.in_memory_llm_clients_cache.flush_cache()
    litellm.drop_params = global_drop_params
    term = Terminal(script, default)
    icpt = InterceptTransport(term.transport, sends_per_invocation=budget, refuse_all=refuse_all)
    session = httpx.Client(transport=icpt, follow_redirects=follow_redirects)
    litellm.client_session = session
    kwargs = {k: v for k, v in dict(FROZEN_CALL_KWARGS, **(extra or {})).items() if k not in drop}
    icpt.begin_invocation()
    t0 = time.time()
    try:
        r = litellm.completion(model=MODEL_CFG['model_name'], messages=messages, **kwargs)
        if r is None:
            outcome = dict(ok=True, returned=None)
        else:
            outcome = dict(ok=True, returned=type(r).__name__, finish_reason=r.choices[0].finish_reason,
                           content_equals_canned=r.choices[0].message.content == OK_CONTENT,
                           prompt_tokens=getattr(r.usage, 'prompt_tokens', None))
    except Exception as e:  # noqa: BLE001  observed and printed
        outcome = exc_info(e)
    out = summarize(label, icpt, term, session, outcome, time.time() - t0)
    litellm.client_session = None
    litellm.drop_params = False
    session.close()
    return out, icpt


class ProbeAbort(Exception):
    """Sketch only: what a new driver could raise so mini-swe-agent's tenacity layer does not retry a refusal."""


def main():
    results = dict(
        probe='DTR-REQ-005 transport map (no model/server/container/network)',
        python=sys.version.split()[0],
        versions={p: md.version(p) for p in ('litellm', 'openai', 'httpx', 'tenacity', 'mini-swe-agent')},
        source_sha256={f: sha((SITE / f).read_bytes()) for f in PKG_FILES},
        frozen_model_name=MODEL_CFG['model_name'], frozen_call_kwargs=FROZEN_CALL_KWARGS,
        env_MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT=os.environ.get('MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT'),
        litellm_globals=dict(num_retries=litellm.num_retries, drop_params=litellm.drop_params,
                             client_session_at_import=repr(litellm.client_session), network_mock=litellm.network_mock,
                             route_all_chat_openai_to_responses=litellm.route_all_chat_openai_to_responses))

    # Frozen default sync client (what the pinned path builds when client_session is None). Constructed, never used.
    default_client = BaseOpenAILLM._get_sync_http_client()
    results['frozen_default_http_client'] = dict(
        type='%s.%s' % (type(default_client).__module__, type(default_client).__qualname__),
        transport=type(default_client._transport).__name__, follow_redirects=default_client.follow_redirects,
        trust_env=default_client.trust_env, env_or_system_proxy_mounts=[str(p.pattern) for p in default_client._mounts])
    default_client.close()

    scenarios = []
    # 1. success; body identity; which client/transport is used
    s1, icpt1 = run('200 OK, frozen kwargs', [OK_200])
    scenarios.append(s1)
    body = icpt1.seen[0]['body']
    litellm.in_memory_llm_clients_cache.flush_cache()
    hterm = Terminal([OK_200])
    hcap = []
    hsession = httpx.Client(transport=httpx.MockTransport(lambda req: (hcap.append(req), hterm.handle(req))[1]))
    litellm.client_session = hsession
    litellm.completion(model=MODEL_CFG['model_name'], messages=MESSAGES, **FROZEN_CALL_KWARGS)
    litellm.client_session = None
    hsession.close()
    req = hcap[0]
    results['wire_request'] = dict(
        method=req.method, url=str(req.url), body_equal_to_scenario_1=req.content == body,
        timeout_extension=req.extensions.get('timeout'),
        header_names=[k for k, _ in req.headers.multi_items()],
        headers_except_authorization={k: v for k, v in req.headers.multi_items() if k.lower() != 'authorization'},
        content_length_equals_body_len=req.headers.get('content-length') == str(len(req.content)))
    parsed = json.loads(body)
    results['wire_body'] = dict(
        top_level_keys=list(parsed), non_message_fields={k: v for k, v in parsed.items() if k != 'messages'},
        messages_equal_input=parsed['messages'] == MESSAGES,
        equals_compact_utf8_dumps_of_parsed=body == json.dumps(parsed, ensure_ascii=False, separators=(',', ':')).encode(),
        raw_utf8_non_ascii_on_wire='café'.encode() in body,
        independent_json_dumps_messages_equals_body=json.dumps(MESSAGES).encode() == body,
        independent_json_dumps_messages_is_substring=json.dumps(MESSAGES).encode() in body)
    # 2-4. HTTP 500: frozen config; control without num_retries; explicit max_retries=0
    scenarios.append(run('500 always, frozen kwargs (num_retries=0)', [], default=E500)[0])
    scenarios.append(run('500 always, CONTROL: num_retries omitted', [], default=E500, drop=('num_retries',))[0])
    scenarios.append(run('500 always, frozen kwargs + explicit max_retries=0', [], default=E500,
                         extra=dict(max_retries=0))[0])
    # 5. HTTP 400 context rejection
    scenarios.append(run('400 context error, frozen kwargs', [E400_CTX])[0])
    # 6-8. litellm's hidden second pass (openai.py:709-871) after a role-alternation 400, then 500s
    scenarios.append(run('400 roles-alternate then 500 always, frozen kwargs', [E400_ROLES], default=E500)[0])
    scenarios.append(run('400 roles-alternate then 500 always, + explicit max_retries=0', [E400_ROLES], default=E500,
                         extra=dict(max_retries=0))[0])
    scenarios.append(run('400 roles-alternate then 500 always, + one-send budget in interceptor', [E400_ROLES],
                         default=E500, budget=1)[0])
    # 9-11. 422 second pass (openai.py:837-842): gated on the GLOBAL litellm.drop_params or the handler's own
    #        drop_params argument, which main.py:2636-2655 does not forward; per-call drop_params=True is not enough
    scenarios.append(run('422 names temperature then 200, frozen kwargs', [E422_TEMP, OK_200])[0])
    scenarios.append(run('422 names temperature then 200, CONTROL: global litellm.drop_params=True',
                         [E422_TEMP, OK_200], global_drop_params=True)[0])
    scenarios.append(run('422 names temperature then 200, CONTROL: global drop_params + one-send budget',
                         [E422_TEMP, OK_200], global_drop_params=True, budget=1)[0])
    # 11-12. redirects (litellm's own default client sets follow_redirects=True)
    scenarios.append(run('307 then 200, follow_redirects=True (frozen default)', [R307, OK_200])[0])
    scenarios.append(run('307 then 200, follow_redirects=False', [R307, OK_200], follow_redirects=False)[0])
    # 13. pre-dispatch refusal (e.g. storage/receipt failure) raised inside the interceptor
    scenarios.append(run('refusal before dispatch, frozen kwargs', [OK_200], refuse_all=True)[0])
    # 14. realistic archived prefix (read-only): exact bytes at realistic size
    hist = ROOT / 'results/v2_agent/pilot_20260922_yaml_v1/psf__requests-1142__small__pilot-cp2-wc2-yaml-v1__20260922T080423Z-7ad659/call9_history.json'
    hmsgs = [{k: v for k, v in m.items() if k != 'extra'} for m in json.loads(hist.read_text())['messages']]
    s14 = run('200 OK, archived call-9 prefix (psf__requests-1142 small), frozen kwargs', [OK_200], messages=hmsgs)[0]
    s14['archived_prefix'] = dict(path=str(hist.relative_to(ROOT)), n_messages=len(hmsgs))
    scenarios.append(s14)
    results['scenarios'] = scenarios

    # 15. client cache pitfall: an OpenAI client cached before client_session changes keeps the OLD http client
    litellm.in_memory_llm_clients_cache.flush_cache()
    ta, tb = Terminal([], OK_200), Terminal([], OK_200)
    ia, ib = InterceptTransport(ta.transport), InterceptTransport(tb.transport)
    sa, sb = httpx.Client(transport=ia), httpx.Client(transport=ib)
    litellm.client_session = sa
    litellm.completion(model=MODEL_CFG['model_name'], messages=MESSAGES, **FROZEN_CALL_KWARGS)
    litellm.client_session = sb
    litellm.completion(model=MODEL_CFG['model_name'], messages=MESSAGES, **FROZEN_CALL_KWARGS)
    results['client_cache_pitfall'] = dict(session_A_sends=len(ia.seen), session_B_sends=len(ib.seen),
                                           note='same cache key (api_key hash, timeout, max_retries, api_base, ...)')
    litellm.client_session = None
    sa.close()
    sb.close()

    # 16. the full frozen layering per LOGICAL call: mini-swe-agent LitellmModel.query (tenacity, stop after
    #     MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT=2, set by importing pilot_episode) over litellm.completion
    from minisweagent.models.litellm_textbased_model import LitellmTextbasedModel

    class AbortTranslationSketch(LitellmTextbasedModel):
        """Sketch only (not the cue-v1 driver): a refusal recorded by the interceptor during this _query becomes
        an abort exception, so the unmodified tenacity loop does not make a second attempt."""
        abort_exceptions = LitellmTextbasedModel.abort_exceptions + [ProbeAbort]
        icpt = None

        def _query(self, messages, **kw):
            before = len(self.icpt.refused)
            try:
                return super()._query(messages, **kw)
            except Exception as e:
                if len(self.icpt.refused) > before:
                    raise ProbeAbort('pre-dispatch refusal recorded by the interceptor') from e
                raise

    layer = []
    for label, script, default, refuse_all, cls in (
            ('mswea query: 200 OK', [OK_200], None, False, LitellmTextbasedModel),
            ('mswea query: 500 always', [], E500, False, LitellmTextbasedModel),
            ('mswea query: 400 context error', [E400_CTX], None, False, LitellmTextbasedModel),
            ('mswea query: refusal before dispatch, unmodified model', [], OK_200, True, LitellmTextbasedModel),
            ('mswea query: refusal before dispatch, abort-translation sketch', [], OK_200, True,
             AbortTranslationSketch)):
        litellm.in_memory_llm_clients_cache.flush_cache()
        term = Terminal(script, default)
        icpt = InterceptTransport(term.transport, refuse_all=refuse_all)
        session = httpx.Client(transport=icpt, follow_redirects=True)
        litellm.client_session = session
        model = cls(**MODEL_CFG)
        model.icpt = icpt
        t0 = time.time()
        try:
            msg = model.query(MESSAGES, timeout=PE.REQUEST_TIMEOUT_S)
            outcome = dict(ok=True, actions=msg['extra']['actions'])
        except Exception as e:  # noqa: BLE001
            outcome = exc_info(e)
        layer.append(summarize(label, icpt, term, session, outcome, time.time() - t0))
        litellm.client_session = None
        session.close()
    results['mini_swe_agent_layer'] = layer
    results['network_attempts'] = NETWORK_ATTEMPTS
    print(json.dumps(results, indent=1, default=str))


if __name__ == '__main__':
    main()
