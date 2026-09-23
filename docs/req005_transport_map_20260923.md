# DTR-REQ-005 transport map: where the pinned stack's request bytes leave the process

**23 September 2026 UTC. Worker research note for the cue-v1 transport gate, based on HEAD `98c8dcc`.**
This note is read-only source tracing plus one in-process probe. No model, llama-server, container or
network was used, and nothing under `results/` was created or changed. The probe's mock terminal stands in
for the real HTTP sender, so this is not a live test. It is also not the cue-v1 integration: no driver,
queue or receipt wiring exists yet. The frozen `pilot_episode.py`, `pilot_runner.py`, `pilot_cohort.py`,
`pilot_report.py` and `pilot_grade.py` are unchanged, and none of the lead-accepted helpers were edited.

It answers the lead's transport requirement in
[theory_feedback_20260923_req005_review.md](theory_feedback_20260923_req005_review.md)
("Concrete integration contract", bullet **Transport**): intercept the finalized body at the pinned client's
actual outbound transport boundary, pass those same bytes onward, and account for or disable hidden retries
and redirects.

## Pins and the exact call

| item | value |
|---|---|
| interpreter | `work/venvs/minisweagent_04d809c/bin/python` (CPython 3.12.13) |
| packages | litellm 1.102.0, openai 2.54.0, httpx 0.28.1, tenacity 9.1.4, mini-swe-agent 2.4.6 (editable, `MSWEA` = `work/upstream/mini-swe-agent-04d809ceab9df28f9adaed044884180159172930`) |
| source digests of the traced files | printed by the probe (`source_sha256`, appendix). For example, `litellm/main.py` is `4e5a93d6…76e34` and `openai/_base_client.py` is `5539c83d…3e869` |
| probe | `experiments/v2_agent/analysis/req005_transport_map_probe.py`, sha256 `4cb98ae60438ccf00a8ff8103cf5ee91c0cd3da2a1f27f188c16cf9a2ffcbdfc` |

The package paths below are relative to `work/venvs/minisweagent_04d809c/lib/python3.12/site-packages/`.

The frozen driver's model call is fully determined by frozen code:
- `pilot_episode.build_effective_config` (`experiments/v2_agent/pilot_episode.py:38-49`) sets `model_name='openai/<alias>'` and `model_kwargs = {drop_params: true` (from `MSWEA/src/minisweagent/config/default.yaml:142-143`)`, api_base, api_key:'none', temperature:0.0, max_tokens:1536, timeout:900, num_retries:0}`.
- `AccountedModel._query` (`pilot_episode.py:176-183`) overrides `timeout=request_timeout(deadline)`, which is `min(900, time left)`.
- `LitellmTextbasedModel._query` (`MSWEA/src/minisweagent/models/litellm_textbased_model.py:20-24`) calls `litellm.completion(model=model_name, messages=messages, **(model_kwargs | kwargs))`.

The probe obtains these kwargs by calling the frozen `build_effective_config` on the pinned `default.yaml`, after
checking its sha256. The frozen module is only imported, never edited. Printed values:
`frozen_call_kwargs = {"drop_params": true, "api_base": "http://127.0.0.1:8291/v1", "api_key": "none", "temperature": 0.0, "max_tokens": 1536, "timeout": 900, "num_retries": 0}`.

## 1. Where the final bytes are produced and handed to the network

Sync call chain for `litellm.completion("openai/<alias>", api_base=...)`:

| # | hop | file:line |
|---|---|---|
| 1 | `completion` (decorated with `@client`) | `litellm/main.py:4997-4999` |
| 2 | `num_retries` sets `max_retries` (`elif num_retries is not None: max_retries = num_retries`) | `litellm/main.py:5210-5213`, `5306-5312` |
| 3 | `max_retries` enters `optional_params` | `litellm/main.py:5470`, `5492` (`max_retries` is in `PROVIDER_UNVALIDATED_PARAMS`, `litellm/utils.py:4916`) |
| 4 | provider `openai` goes to `_complete_custom_openai` | `litellm/main.py:5749-5775` |
| 5 | with `EXPERIMENTAL_OPENAI_BASE_LLM_HTTP_HANDLER` unset, `openai_chat_completions.completion(...)` (note: **no `drop_params` argument is forwarded**) | `litellm/main.py:2595`, `2636-2655`; instance at `main.py:281` |
| 6 | `OpenAIChatCompletion.completion`: `data = provider_config.transform_request(...)` | `litellm/llms/openai/openai.py:755-761` |
| 7 | `_get_openai_client(is_async=False, api_key, api_base, timeout, max_retries, organization, client)` | `openai.py:780-789`, `374-462` |
| 8 | **the httpx client**: `BaseOpenAILLM._get_sync_http_client()` returns `litellm.client_session` if one is set. Otherwise it returns a new `httpx.Client(verify=ssl_config, follow_redirects=True)` | `litellm/llms/openai/common_utils.py:331-346` |
| 9 | `openai.OpenAI(api_key, base_url=api_base, http_client=<8>, timeout, max_retries, organization)` | `openai.py:437-444`; SDK stores it as `self._client` (`openai/_base_client.py:950`) |
| 10 | `openai_client.chat.completions.with_raw_response.create(**data, timeout=timeout)` | `openai.py:505-520` |
| 11 | `Completions.create` calls `self._post("/chat/completions", body=maybe_transform(...))` | `openai/resources/chat/completions/completions.py:1248`, `1296-1297` |
| 12 | `SyncAPIClient.request` retry loop, which calls `_build_request` on **every** attempt | `openai/_base_client.py:1036-1063` |
| 13 | **final body bytes are produced here:** `kwargs["content"] = openapi_dumps(json_data)`, i.e. `json.dumps(..., ensure_ascii=False, separators=(",",":"), allow_nan=False).encode()`, then `self._client.build_request(...)` builds an `httpx.Request` whose body is a `ByteStream`, read at construction | `openai/_base_client.py:600`, `615-626`; `openai/_utils/_json.py:11-25`; `httpx/_models.py:420-423` |
| 14 | `_send_request` calls `self._client.send(request, stream=..., **kwargs)` | `openai/_base_client.py:998-1005`, `1080-1084` |
| 15 | `httpx.Client.send`, `_send_handling_auth`, `_send_handling_redirects`, `_send_single_request` | `httpx/_client.py:879-1014` |
| 16 | **hand-off to the transport:** `response = transport.handle_request(request)` | `httpx/_client.py:1014` |
| 17 | default terminal `HTTPTransport.handle_request` builds `httpcore.Request(..., content=request.stream)` and calls `self._pool.handle_request` | `httpx/_transports/default.py:230-250` |

**Answer to question 1.**
- **Body bytes.** The final bytes are produced by the openai SDK's `BaseClient._build_request`
  (`openai/_base_client.py:600`) and carried in an `httpx.Request`.
- **Hand-off point.** The last point in Python that sees the finalized request object is
  `transport.handle_request(request)` at `httpx/_client.py:1014`. The default transport is
  `httpx.HTTPTransport`, which passes `request.stream` to httpcore.
- **Client type.** Yes, this path uses an `openai.OpenAI` client with an `httpx.Client`.
- **Where the httpx client is created.** In litellm's `BaseOpenAILLM._get_sync_http_client`
  (`common_utils.py:331-346`), unless `litellm.client_session` is set.
- **Caching.** litellm caches the **OpenAI client** in `litellm.in_memory_llm_clients_cache` for 3600 s.
  - The key is: hashed api_key, is_async, every `OpenAI.__init__` parameter name, `timeout`, `max_retries`,
    `organization`, `api_base` and `workload_identity_config` (`common_utils.py:237-291`).
  - The key does **not** include the httpx client. Each newly built OpenAI client gets a **new**
    `httpx.Client`, unless `litellm.client_session` is set. In that case every OpenAI client shares that one
    session, and litellm never closes it on eviction (`owns_wrapped_http_client`, `common_utils.py:222-235`).
  - Because `timeout` is in the key, the frozen per-call `timeout=min(900, left)` builds a new cached OpenAI
    client each time its value changes.

**What is on the wire (probe, 200 case).**
- **Body:** `{"messages", "model", "max_tokens", "temperature"}` with
  `model="qwen2.5-coder-7b-instruct-c03e6d3-q4_k_m"`, so the `openai/` prefix is stripped. The body contains
  no timeout, key, `drop_params` or `num_retries`.
- **Byte form:** the parsed `messages` equal the input messages; this is a parsed equality, not a byte
  comparison. The body equals a compact `ensure_ascii=False` dump of itself, and non-ASCII characters are
  sent as raw UTF-8.
- **Headers:** an `authorization` header is present. The probe did not print its value; it is built from
  `api_key='none'`. It must not be persisted.
  - `x-stainless-retry-count` changes per SDK attempt (`openai/_base_client.py:484`).
  - `x-stainless-read-timeout` carries the per-call timeout.
  - `content-length` equals the body length.
- **Why a messages-only dump is not enough:** `json.dumps(messages)` is neither equal to the body nor a
  substring of it. This confirms the lead's point that an independent dump of `messages` is not the request.

## 2. Every retry and resend layer, and effective sends per call

| layer | where | frozen state | what re-sends |
|---|---|---|---|
| L0 mini-swe-agent tenacity (outside `litellm.completion`) | `MSWEA/src/minisweagent/models/utils/retry.py:19-25`; `litellm_model.py:81-84` | `MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT=2` (`pilot_episode.py:14`), so **at most 2 `litellm.completion` invocations per logical call**; wait is exponential with a 4 s minimum | Any exception not in `abort_exceptions` (`litellm_model.py:50-57` plus `EpisodeDeadline`). A `ContextWindowExceededError` aborts. `InternalServerError`, `APIConnectionError`, timeouts and other `BadRequestError`s are retried |
| L1 litellm `@client` wrapper | `litellm/utils.py:1766-1806` | `num_retries = kwargs.get("num_retries") or litellm.num_retries or None`, so with 0 and the global `None` (`litellm/__init__.py:533`) it is `None` and `completion_with_retries` is never entered. No `context_window_fallback_dict` is supplied | nothing. **Caveat:** `0 or litellm.num_retries` means a non-None *global* `litellm.num_retries` would override the per-call 0 |
| L2 litellm `num_retries` becomes SDK `max_retries` | `main.py:5306-5312`, `openai.py:711`, `437-444` | the SDK client is built with `max_retries=0` (probe: cached client `max_retries: 0`) | nothing in pass 1. litellm `DEFAULT_MAX_RETRIES` (`litellm/constants.py:63`, 2 unless env `DEFAULT_MAX_RETRIES`) is only the default argument of `_get_openai_client` (`openai.py:381`). It is never reached on this path because `openai.py:711` always passes an explicit value |
| L3 openai SDK loop | `openai/_base_client.py:1055-1148`; `_should_retry` `821-863`; backoff `797-819`, `_constants.py:10-15` | `max_retries=0`, so exactly 1 SDK attempt | when `max_retries>0`: timeouts (`1085-1095`); other transport exceptions **except `openai.OpenAIError`**, which propagate unretried (`1099-1115`); HTTP 408, 409, 429 and ≥500; any status with header `x-should-retry: true` (and never with `false`); no retry if `Retry-After` exceeds 120 s. Each retry rebuilds and re-serializes the request (`1063`) |
| **L4 litellm hidden second pass** | `openai.py:709` `for _ in range(2)`; triggers at `837-842` and `844-869` | **dormant but reachable** | (a) any exception whose text contains `Conversation roles must alternate user/assistant`, `user and assistant roles should be alternating` (messages re-formatted), ``Last message must have role `user` `` (an empty user message is appended) or `unknown field: parameter index is not a valid field`. (b) HTTP 422 **only if the global `litellm.drop_params` is True**, which env `LITELLM_DROP_PARAMS` can set (`litellm/litellm_core_utils/core_helpers.py:69-82`, `litellm/__init__.py:245`). The per-call yaml `drop_params: true` does not enable it, because `main.py:2636-2655` does not forward it. **In pass 2, `inference_params.pop("max_retries", 2)` returns the literal 2**, because pass 1 already popped the key. That builds a second OpenAI client with `max_retries=2`, so up to 3 more SDK attempts, possibly with a **changed body** |
| L5 httpx redirects | `common_utils.py:343-346` (`follow_redirects=True`); `httpx/_client.py:964-999`, `573-582` | on, `max_redirects=20` | each followed 3xx is another `transport.handle_request`. For 307 and 308 the same body stream is re-sent |
| L6 httpx/httpcore | `httpx/_transports/default.py:147` (`retries: int = 0`) | 0 | nothing (connect retries are off) |

Not on this path, and verified inert in the frozen configuration:
- `completion_with_retries`, fallbacks and the Router.
- The base HTTP handler, which is used only if `EXPERIMENTAL_OPENAI_BASE_LLM_HTTP_HANDLER` is set (`main.py:2595-2634`).
- The Responses-API bridge, used only if `LITELLM_ROUTE_ALL_CHAT_OPENAI_TO_RESPONSES` is set or the model map says `mode: responses` (`main.py:1060-1063`; probe global `false`).
- The output-token-limit 400 converted into a synthetic `length` response (`openai.py:535-538`). This fires only on one exact provider sentence (`common_utils.py:132-144`). The llama-server context rejection does not match it: the probe raised `ContextWindowExceededError` through `litellm/litellm_core_utils/exception_mapping_utils.py:92`.

**Effective physical sends in the frozen configuration.**
- **Per `litellm.completion`:**
  - Normally **1**. This holds for success, for any retryable status (500 gives 1 in the probe), and for a 400 context error.
  - L4 raises it to **4** (demonstrated: 1 + 3, with retry-count headers 0, 0, 1, 2). An explicit `max_retries=0` does **not** prevent this.
  - Each followed redirect adds one more (demonstrated: 307 then 200 gives 2).
  - Code-derived upper bound: `(1 + 3) SDK attempts × (1 + 20 redirects) = 84`. This needs a server that emits redirects and the trigger phrases. Neither was observed.
- **Per logical call (with L0):**
  - A 500 gives **2** sends (demonstrated through `LitellmTextbasedModel.query`, 4.03 s).
  - A 400 context error gives **1** (abort).
  - A success gives **1**.
  - Upper bound: 2 × 84 = 168.
- **Consequence for the frozen yaml-v1 accounting.** `attempts.jsonl` logs one record per `_query`, which is per L0 attempt, not per L3/L4/L5 send.
  - In the archived yaml-v1 attempts, the only failure records are 2 `ContextWindowExceededError`s. Neither can trigger L4 or L3 under the frozen settings.
  - This is a retrospective consistency check, not proof that no redirect ever occurred.

**How to force exactly one physical send per `litellm.completion` without changing request content.**
1. Keep `num_retries=0`. It already disables L1–L3 in pass 1. An explicit `max_retries=0` is redundant (probe S4 is identical to S2) and ineffective against L4 (S7).
2. Put a **one-send budget in the injected transport**. The new driver's `_query` override opens a budget of 1 (and the receipt key) for its `litellm.completion` invocation. Any further `handle_request` in that invocation is refused before it reaches the terminal, and is recorded as not dispatched.
   - Raise the refusal as an `openai.OpenAIError` subclass, so the SDK neither retries nor wraps it (`openai/_base_client.py:1099-1101`).
   - Probe S8: role-phrase 400 followed by 500s. 1 send, 1 refusal, even though the pass-2 client has `max_retries: 2`.
   - Probe S11: global drop_params with 422. 1 send, 1 refusal.
   - The first send's content is unchanged. A modified pass-2 body never leaves the process.
3. Set `follow_redirects=False` on the injected `httpx.Client` (probe S13: a 307 surfaces as litellm `APIError` with status 307 after 1 send). The budget would also catch a followed hop.
4. Leave L0 as frozen. Its 2 attempts are the lead's "two physical attempts per logical call". Each attempt is its own `litellm.completion`, receipt and budget.
5. Add launch preflight assertions:
   - `litellm.num_retries is None` and `litellm.drop_params is False`.
   - `EXPERIMENTAL_OPENAI_BASE_LLM_HTTP_HANDLER` and `LITELLM_ROUTE_ALL_CHAT_OPENAI_TO_RESPONSES` are unset.
   - `litellm.client_session` is the injected client before the first completion.
   - The OpenAI client cache is empty at install time, and afterwards every cached `openai.OpenAI._client` is that session.

## 3. The supported injection point on this path

**Recommended: `litellm.client_session`**, set to
`httpx.Client(transport=InterceptTransport(httpx.HTTPTransport(verify=<litellm get_ssl_configuration()>)), follow_redirects=False)`.

- **It is the pinned path's own hook** (`common_utils.py:332-333`, declared at `litellm/__init__.py:419`).
- **It preserves the frozen settings.** litellm still builds the `openai.OpenAI` client itself with the frozen
  `api_base`, `api_key`, `timeout`, `max_retries` and `organization` (`openai.py:437-444`). URL, model fields,
  generation settings, response parsing and SDK retry policy are therefore unchanged. Only the `httpx.Client`
  underneath is ours.
- **Probe evidence:** in every scenario the cached OpenAI client wrapped the injected session
  (`wraps_injected_session: true`).
- **Caveat: process-global, and a cache hazard.** An OpenAI client cached *before* the session is installed or
  changed keeps its old http client, because the cache key ignores the session. In probe item 15, session B
  saw **0** sends after replacing A without a cache flush. Install the session before the first
  `litellm.completion` in the episode process, and assert the cache contents as above.
- **The terminal:** `httpx.Client(verify=ssl)` would itself construct
  `HTTPTransport(verify, cert=None, trust_env=True, http1=True, http2=False, limits=DEFAULT_LIMITS)`
  (`httpx/_client.py:718-738`).
  - One difference from the frozen default client: passing `transport=` disables environment and system
    proxy mounts (`httpx/_client.py:685`). httpx does not implicitly exempt loopback (`httpx/_utils.py:30-76`).
  - On this host the frozen default client currently has **no** proxy mounts (probe:
    `env_or_system_proxy_mounts: []`), so the two are equivalent now. Record this at each launch preflight.

**Rejected alternatives.**
- **`client=` kwarg** (an `openai.OpenAI(http_client=...)`). litellm returns the supplied client after
  mutating its `max_retries` and `organization` (`openai.py:456-462`, `363-372`). It does **not** apply its
  own `api_base`, `api_key` or `timeout` to that client, so the caller fixes the URL. It would also add a
  `client` entry to the `model_kwargs | kwargs` merge.
- **`litellm.network_mock`** (`common_utils.py:335-338`). It replaces the sender with litellm's own mock
  rather than passing requests through.
- **Monkeypatching SDK internals.** Unnecessary.

**What the interceptor receives.** It receives the finalized `httpx.Request`: method, full URL, all headers
and a `ByteStream` body in every probed case (`stream_type: ["ByteStream"]`).
- Use `request.read()`, not `.content`. A redirect-hop request is rebuilt from the same stream without being
  pre-read (`httpx/_client.py:483-490`). The first probe revision raised `RequestNotRead` there; this was
  fixed before the recorded run.
- Refuse any non-`ByteStream` body before sending. This matches the contract's non-replayable rule.
- Persist-then-pass order inside `handle_request`:
  1. Budget check.
  2. `body = request.read()`, followed by the 8 MiB cap check.
  3. Durable write of those exact bytes, for example `RequestReceiptStore.record_request(serialized=body, ...)`. The accepted helper takes bytes. On failure, raise the refusal without calling the terminal.
  4. `return inner.handle_request(request)` with the **same** request object.
  - The returned `httpx.Response` gives the status, which distinguishes "transport attempted / response received" from a raised connect or timeout error. Parsing and usage come later, from litellm.
  - Reading the response body inside the transport was **not** probed.

**How a refusal surfaces (needed for "no automatic model retry").**
- The interceptor's refusal reaches the caller as `litellm.exceptions.InternalServerError` (status 500). It is
  wrapped at `openai.py:872-887` and then mapped. The refusal class appears only in the `__cause__`/`__context__` chain.
- The **unmodified** mini-swe-agent tenacity layer therefore retries it (probe: 2 refusals, 4.03 s).
- A driver-side translation stops that retry. The probe's sketch compares refusal counts in `_query` and
  raises an abort exception that is listed in `abort_exceptions`: 1 refusal, outcome `ProbeAbort`.
- The same wrapping hides the first send's HTTP error in budget-refusal cases (S8). The receipt for a send
  should therefore take its status from the transport-level response, not from the exception litellm surfaces.
- This is an implementation choice for the new cue-v1 driver. It is not decided here.

## 4. Probe: method and literal results

`work/venvs/minisweagent_04d809c/bin/python experiments/v2_agent/analysis/req005_transport_map_probe.py`
(exit 0, about 10 s wall time).

**Environment.**
- The probe sets `LITELLM_LOCAL_MODEL_COST_MAP=True` before import, because otherwise
  `import litellm` GETs a remote cost map (`get_model_cost_map.py:626`, `636-638`; `litellm/__init__.py:557`).
- `MSWEA_SILENT_STARTUP` is set, and `MSWEA_GLOBAL_CONFIG_DIR` points to a temp directory.
- A socket tripwire refuses and records `connect`, `connect_ex`, `create_connection` and `getaddrinfo`. Result: **`network_attempts: []`**.

**Mechanism.**
- Calls use the real `litellm.completion(model=..., messages=..., **(model_kwargs | {'timeout': 900}))`.
  The final block goes through the real `LitellmTextbasedModel.query`.
- `litellm.client_session` is an `httpx.Client` whose transport is `InterceptTransport`. It records `request.read()` and then delegates the same request object to an `httpx.MockTransport` terminal.
- The terminal re-reads the body by iterating `request.stream`, which is what `HTTPTransport` gives httpcore, and returns canned OpenAI-format JSON.

**Canned responses.**
- The 400 context error text is the archived llama-server message ("request (16610 tokens) exceeds the
  available context size (16384 tokens), try increasing it", from the yaml-v1 attempts). Its JSON envelope
  and `type` field are modelled, not archived.
- The 500, role-phrase 400, 422 and 307 responses are synthetic.
- The messages are a four-message synthetic history with non-ASCII text. One scenario instead uses the
  archived 18-message call-9 prefix of `psf__requests-1142` (small), read-only.

**Column meanings.**
- *icpt*: sends passed on by the interceptor.
- *term*: requests the terminal received.
- *refused*: requests refused before dispatch.
- *identical*: every intercepted body is byte-equal to the corresponding terminal-received body. This is vacuously true when there were 0 sends.
- *retry hdr*: `x-stainless-retry-count` per send.
- *SDK clients*: `max_retries` of the cached OpenAI clients, all wrapping the injected session.

| # | scenario | icpt | term | refused | identical | distinct bodies | retry hdr | SDK clients | outcome | s |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 200 OK, frozen kwargs | 1 | 1 | 0 | True | 1 | 0 | 0 | ok ModelResponse | 0.19 |
| 2 | 500 always, frozen kwargs (num_retries=0) | 1 | 1 | 0 | True | 1 | 0 | 0 | litellm InternalServerError 500 | 0.01 |
| 3 | 500 always, CONTROL: num_retries omitted | 3 | 3 | 0 | True | 1 | 0,1,2 | 2 | litellm InternalServerError 500 | 1.45 |
| 4 | 500 always, frozen + explicit max_retries=0 | 1 | 1 | 0 | True | 1 | 0 | 0 | litellm InternalServerError 500 | 0.01 |
| 5 | 400 context error, frozen kwargs | 1 | 1 | 0 | True | 1 | 0 | 0 | litellm ContextWindowExceededError 400 | 0.01 |
| 6 | 400 roles-alternate then 500 always, frozen | 4 | 4 | 0 | True | 1 | 0,0,1,2 | 0, 2 | litellm InternalServerError 500 | 1.33 |
| 7 | same + explicit max_retries=0 | 4 | 4 | 0 | True | 1 | 0,0,1,2 | 0, 2 | litellm InternalServerError 500 | 1.37 |
| 8 | same + one-send budget in interceptor | 1 | 1 | 1 | True | 1 | 0 | 0, 2 | litellm InternalServerError 500 (cause: refusal) | 0.01 |
| 9 | 422 names temperature then 200, frozen | 1 | 1 | 0 | True | 1 | 0 | 0 | litellm BadRequestError 422 | 0.01 |
| 10 | same, CONTROL: global litellm.drop_params=True | 2 | 2 | 0 | True | **2** (447 then 429 bytes: `,"temperature":0.0` dropped) | 0,0 | 0, 2 | **ok ModelResponse** | 0.0 |
| 11 | same CONTROL + one-send budget | 1 | 1 | 1 | True | 1 | 0 | 0, 2 | litellm InternalServerError 500 (cause: refusal) | 0.01 |
| 12 | 307 then 200, follow_redirects=True (frozen default) | 2 | 2 | 0 | True | 1 | 0,0 | 0 | ok ModelResponse | 0.0 |
| 13 | 307 then 200, follow_redirects=False | 1 | 1 | 0 | True | 1 | 0 | 0 | litellm APIError 307 | 0.01 |
| 14 | refusal before dispatch, frozen kwargs | 0 | 0 | 1 | (vacuous) | 0 | - | 0 | litellm InternalServerError 500 (cause: refusal) | 0.01 |
| 15 | 200 OK, archived call-9 prefix (11,183-byte body) | 1 | 1 | 0 | True | 1 | 0 | 0 | ok ModelResponse | 0.0 |
| 16 | mswea query: 200 OK | 1 | 1 | 0 | True | 1 | 0 | 0 | ok, actions `[{'command': 'echo probe'}]` | 0.0 |
| 17 | mswea query: 500 always | 2 | 2 | 0 | True | 1 | 0,0 | 0 | litellm InternalServerError 500 | 4.03 |
| 18 | mswea query: 400 context error | 1 | 1 | 0 | True | 1 | 0 | 0 | litellm ContextWindowExceededError 400 | 0.01 |
| 19 | mswea query: refusal, unmodified model | 0 | 0 | 2 | (vacuous) | 0 | - | 0 | litellm InternalServerError 500 | 4.03 |
| 20 | mswea query: refusal, abort-translation sketch | 0 | 0 | 1 | (vacuous) | 0 | - | 0 | ProbeAbort | 0.01 |

These rows answer the task's four probe questions:
- **(a)** The injected transport sees exactly one request per call under the frozen config (rows 1, 2, 5, 15).
- **(b)** The bytes it sees equal the bytes the terminal receives in every row with sends, including SDK retries (row 3) and a redirect hop (row 12).
- **(c)** A canned 500 produces 1 send under the frozen config, 3 without `num_retries`, and 1 with explicit `max_retries=0`. At the logical-call level it produces 2 sends through L0. L4 can re-enable 3 extra sends that `max_retries=0` does not stop, but the transport budget does.
- **(d)** A canned 400 context error produces 1 send, `ContextWindowExceededError`, and no L0 retry.

Rows 3, 10 and 12 are controls that show the hidden layers exist. They are not the frozen configuration.
A second full run produced identical scenario records apart from timings.

## Caveats and items not implemented

- **Disclosure: one probable unintended network attempt.** At the start of this task, one version-check
  command imported `litellm` in the pinned venv *without* `LITELLM_LOCAL_MODEL_COST_MAP=True`. Per
  `get_model_cost_map.py:636-638`, that import attempts an HTTP GET of litellm's public cost-map JSON. No
  project data is sent, but it is outbound network use that this task prohibited. I did not verify whether
  it connected. Every later run used the local flag and the tripwire.
- **For the lead: the live yaml-v1 episodes probably made the same import-time GET.** No repository file sets
  `LITELLM_LOCAL_MODEL_COST_MAP` or `LITELLM_MODEL_COST_MAP_URL`, and `pilot_episode.py:140-142` imports
  litellm through mini-swe-agent. This is off the request path and does not change the body (row 1's body
  keys are fixed). It is still network egress, and a possible cost-map/model-info difference between runs.
  Setting the flag in cue-v1 is an environment choice the lead should bind explicitly; I did not decide it.
- The terminal is an in-process `httpx.MockTransport`. httpcore framing (the request line, header encoding,
  socket writes) is not exercised. Byte identity is shown at the `request.stream` iterator that
  `HTTPTransport` hands to httpcore, together with `content-length == len(body)`.
- Only the sync, non-streaming path was probed, because the frozen driver sets no `stream`. Async and
  streaming paths differ (`openai.py:712-776`) and are unused.
- The 400 envelope is modelled. The 422, role-phrase and redirect cases are synthetic stress inputs. There is
  no evidence that the pinned llama-server emits them.
- The one-send budget, receipt writes, refusal-to-abort translation, 8 MiB cap and preflight assertions are
  **described and sketched, not implemented** in any driver. The lead's acceptance artifact (both arms,
  receipts, horizon/parse/retry boundaries, deadline control, cleanup) is still outstanding. The probe
  prints observations; it is not a test and asserts nothing about the stack.
- Nothing here is model inference or evidence about cue effects. Readiness is unchanged from the lead's
  last published estimate (55% at `add36c3`); this note moves no rubric stage.

## Appendix: literal probe stdout (final run)

```json
{
 "probe": "DTR-REQ-005 transport map (no model/server/container/network)",
 "python": "3.12.13",
 "versions": {
  "litellm": "1.102.0",
  "openai": "2.54.0",
  "httpx": "0.28.1",
  "tenacity": "9.1.4",
  "mini-swe-agent": "2.4.6"
 },
 "source_sha256": {
  "litellm/main.py": "4e5a93d6066e1df0b8885d6d083548d1c33155fd181ee84f0aed809c26d76e34",
  "litellm/utils.py": "6c6fdade35376c1f1c5e9cf76ee0b072b1c0e55ac30e2d900547e886a5cd9dcc",
  "litellm/llms/openai/openai.py": "30e9f9fb0d8857b5795236335f190f8de30b7f41b95f8fb08dd47ce863096bc8",
  "litellm/llms/openai/common_utils.py": "2333615d6382f510bc4268f04450d56ed7f7c61ca8394daf654d70e8d7692ac9",
  "openai/_base_client.py": "5539c83d01c27e1bbf1ad34e59cc872202feb6c8bf81b56fadbeeb2b81a3e869",
  "openai/_client.py": "d101a059e5c7632dff8f791ca8480c5cb07623272d421842ab40d348dd940517",
  "httpx/_client.py": "c43f941baefe58c91e96d00039e1868fe719d91453026d7db1647194563bff8d",
  "httpx/_transports/default.py": "03379a454c95c0271c4f2c8d25ec437f49f57457f3cf2769748420bf0ecf2e79",
  "httpx/_transports/mock.py": "3d3a34779ebb4484d7c46ae48ba90deffebbc300317f088c0dcb972626428c4a"
 },
 "frozen_model_name": "openai/qwen2.5-coder-7b-instruct-c03e6d3-q4_k_m",
 "frozen_call_kwargs": {
  "drop_params": true,
  "api_base": "http://127.0.0.1:8291/v1",
  "api_key": "none",
  "temperature": 0.0,
  "max_tokens": 1536,
  "timeout": 900,
  "num_retries": 0
 },
 "env_MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT": "2",
 "litellm_globals": {
  "num_retries": null,
  "drop_params": false,
  "client_session_at_import": "None",
  "network_mock": false,
  "route_all_chat_openai_to_responses": false
 },
 "frozen_default_http_client": {
  "type": "httpx.Client",
  "transport": "HTTPTransport",
  "follow_redirects": true,
  "trust_env": true,
  "env_or_system_proxy_mounts": []
 },
 "wire_request": {
  "method": "POST",
  "url": "http://127.0.0.1:8291/v1/chat/completions",
  "body_equal_to_scenario_1": true,
  "timeout_extension": {
   "connect": 900.0,
   "read": 900.0,
   "write": 900.0,
   "pool": 900.0
  },
  "header_names": [
   "host",
   "accept-encoding",
   "connection",
   "authorization",
   "accept",
   "content-type",
   "user-agent",
   "x-stainless-lang",
   "x-stainless-package-version",
   "x-stainless-os",
   "x-stainless-arch",
   "x-stainless-runtime",
   "x-stainless-runtime-version",
   "x-stainless-async",
   "x-stainless-raw-response",
   "x-stainless-retry-count",
   "x-stainless-read-timeout",
   "content-length"
  ],
  "headers_except_authorization": {
   "host": "127.0.0.1:8291",
   "accept-encoding": "gzip, deflate",
   "connection": "keep-alive",
   "accept": "application/json",
   "content-type": "application/json",
   "user-agent": "OpenAI/Python 2.54.0",
   "x-stainless-lang": "python",
   "x-stainless-package-version": "2.54.0",
   "x-stainless-os": "MacOS",
   "x-stainless-arch": "arm64",
   "x-stainless-runtime": "CPython",
   "x-stainless-runtime-version": "3.12.13",
   "x-stainless-async": "false",
   "x-stainless-raw-response": "true",
   "x-stainless-retry-count": "0",
   "x-stainless-read-timeout": "900.0",
   "content-length": "447"
  },
  "content_length_equals_body_len": true
 },
 "wire_body": {
  "top_level_keys": [
   "messages",
   "model",
   "max_tokens",
   "temperature"
  ],
  "non_message_fields": {
   "model": "qwen2.5-coder-7b-instruct-c03e6d3-q4_k_m",
   "max_tokens": 1536,
   "temperature": 0.0
  },
  "messages_equal_input": true,
  "equals_compact_utf8_dumps_of_parsed": true,
  "raw_utf8_non_ascii_on_wire": true,
  "independent_json_dumps_messages_equals_body": false,
  "independent_json_dumps_messages_is_substring": false
 },
 "scenarios": [
  {
   "scenario": "200 OK, frozen kwargs",
   "intercepted_sends": 1,
   "terminal_received": 1,
   "refused_before_dispatch": 0,
   "bytes_identical": true,
   "same_url": true,
   "body_sha256": [
    "a3af2e372ba7d51c"
   ],
   "body_len": [
    447
   ],
   "distinct_bodies": 1,
   "retry_count_header": [
    "0"
   ],
   "stream_type": [
    "ByteStream"
   ],
   "refusal_reasons": [],
   "openai_clients": [
    {
     "max_retries": 0,
     "wraps_injected_session": true
    }
   ],
   "outcome": {
    "ok": true,
    "returned": "ModelResponse",
    "finish_reason": "stop",
    "content_equals_canned": true,
    "prompt_tokens": 123
   },
   "seconds": 0.19
  },
  {
   "scenario": "500 always, frozen kwargs (num_retries=0)",
   "intercepted_sends": 1,
   "terminal_received": 1,
   "refused_before_dispatch": 0,
   "bytes_identical": true,
   "same_url": true,
   "body_sha256": [
    "a3af2e372ba7d51c"
   ],
   "body_len": [
    447
   ],
   "distinct_bodies": 1,
   "retry_count_header": [
    "0"
   ],
   "stream_type": [
    "ByteStream"
   ],
   "refusal_reasons": [],
   "openai_clients": [
    {
     "max_retries": 0,
     "wraps_injected_session": true
    }
   ],
   "outcome": {
    "ok": false,
    "exception": "litellm.exceptions.InternalServerError",
    "status_code": 500,
    "chain": [
     "litellm.llms.openai.common_utils.OpenAIError",
     "openai.InternalServerError",
     "httpx.HTTPStatusError"
    ]
   },
   "seconds": 0.01
  },
  {
   "scenario": "500 always, CONTROL: num_retries omitted",
   "intercepted_sends": 3,
   "terminal_received": 3,
   "refused_before_dispatch": 0,
   "bytes_identical": true,
   "same_url": true,
   "body_sha256": [
    "a3af2e372ba7d51c",
    "a3af2e372ba7d51c",
    "a3af2e372ba7d51c"
   ],
   "body_len": [
    447,
    447,
    447
   ],
   "distinct_bodies": 1,
   "retry_count_header": [
    "0",
    "1",
    "2"
   ],
   "stream_type": [
    "ByteStream"
   ],
   "refusal_reasons": [],
   "openai_clients": [
    {
     "max_retries": 2,
     "wraps_injected_session": true
    }
   ],
   "outcome": {
    "ok": false,
    "exception": "litellm.exceptions.InternalServerError",
    "status_code": 500,
    "chain": [
     "litellm.llms.openai.common_utils.OpenAIError",
     "openai.InternalServerError",
     "httpx.HTTPStatusError"
    ]
   },
   "seconds": 1.45
  },
  {
   "scenario": "500 always, frozen kwargs + explicit max_retries=0",
   "intercepted_sends": 1,
   "terminal_received": 1,
   "refused_before_dispatch": 0,
   "bytes_identical": true,
   "same_url": true,
   "body_sha256": [
    "a3af2e372ba7d51c"
   ],
   "body_len": [
    447
   ],
   "distinct_bodies": 1,
   "retry_count_header": [
    "0"
   ],
   "stream_type": [
    "ByteStream"
   ],
   "refusal_reasons": [],
   "openai_clients": [
    {
     "max_retries": 0,
     "wraps_injected_session": true
    }
   ],
   "outcome": {
    "ok": false,
    "exception": "litellm.exceptions.InternalServerError",
    "status_code": 500,
    "chain": [
     "litellm.llms.openai.common_utils.OpenAIError",
     "openai.InternalServerError",
     "httpx.HTTPStatusError"
    ]
   },
   "seconds": 0.01
  },
  {
   "scenario": "400 context error, frozen kwargs",
   "intercepted_sends": 1,
   "terminal_received": 1,
   "refused_before_dispatch": 0,
   "bytes_identical": true,
   "same_url": true,
   "body_sha256": [
    "a3af2e372ba7d51c"
   ],
   "body_len": [
    447
   ],
   "distinct_bodies": 1,
   "retry_count_header": [
    "0"
   ],
   "stream_type": [
    "ByteStream"
   ],
   "refusal_reasons": [],
   "openai_clients": [
    {
     "max_retries": 0,
     "wraps_injected_session": true
    }
   ],
   "outcome": {
    "ok": false,
    "exception": "litellm.exceptions.ContextWindowExceededError",
    "status_code": 400,
    "chain": [
     "litellm.llms.openai.common_utils.OpenAIError",
     "openai.BadRequestError",
     "httpx.HTTPStatusError"
    ]
   },
   "seconds": 0.01
  },
  {
   "scenario": "400 roles-alternate then 500 always, frozen kwargs",
   "intercepted_sends": 4,
   "terminal_received": 4,
   "refused_before_dispatch": 0,
   "bytes_identical": true,
   "same_url": true,
   "body_sha256": [
    "a3af2e372ba7d51c",
    "a3af2e372ba7d51c",
    "a3af2e372ba7d51c",
    "a3af2e372ba7d51c"
   ],
   "body_len": [
    447,
    447,
    447,
    447
   ],
   "distinct_bodies": 1,
   "retry_count_header": [
    "0",
    "0",
    "1",
    "2"
   ],
   "stream_type": [
    "ByteStream"
   ],
   "refusal_reasons": [],
   "openai_clients": [
    {
     "max_retries": 0,
     "wraps_injected_session": true
    },
    {
     "max_retries": 2,
     "wraps_injected_session": true
    }
   ],
   "outcome": {
    "ok": false,
    "exception": "litellm.exceptions.InternalServerError",
    "status_code": 500,
    "chain": [
     "litellm.llms.openai.common_utils.OpenAIError",
     "openai.InternalServerError",
     "httpx.HTTPStatusError"
    ]
   },
   "seconds": 1.33
  },
  {
   "scenario": "400 roles-alternate then 500 always, + explicit max_retries=0",
   "intercepted_sends": 4,
   "terminal_received": 4,
   "refused_before_dispatch": 0,
   "bytes_identical": true,
   "same_url": true,
   "body_sha256": [
    "a3af2e372ba7d51c",
    "a3af2e372ba7d51c",
    "a3af2e372ba7d51c",
    "a3af2e372ba7d51c"
   ],
   "body_len": [
    447,
    447,
    447,
    447
   ],
   "distinct_bodies": 1,
   "retry_count_header": [
    "0",
    "0",
    "1",
    "2"
   ],
   "stream_type": [
    "ByteStream"
   ],
   "refusal_reasons": [],
   "openai_clients": [
    {
     "max_retries": 0,
     "wraps_injected_session": true
    },
    {
     "max_retries": 2,
     "wraps_injected_session": true
    }
   ],
   "outcome": {
    "ok": false,
    "exception": "litellm.exceptions.InternalServerError",
    "status_code": 500,
    "chain": [
     "litellm.llms.openai.common_utils.OpenAIError",
     "openai.InternalServerError",
     "httpx.HTTPStatusError"
    ]
   },
   "seconds": 1.37
  },
  {
   "scenario": "400 roles-alternate then 500 always, + one-send budget in interceptor",
   "intercepted_sends": 1,
   "terminal_received": 1,
   "refused_before_dispatch": 1,
   "bytes_identical": true,
   "same_url": true,
   "body_sha256": [
    "a3af2e372ba7d51c"
   ],
   "body_len": [
    447
   ],
   "distinct_bodies": 1,
   "retry_count_header": [
    "0"
   ],
   "stream_type": [
    "ByteStream"
   ],
   "refusal_reasons": [
    "send budget exhausted"
   ],
   "openai_clients": [
    {
     "max_retries": 0,
     "wraps_injected_session": true
    },
    {
     "max_retries": 2,
     "wraps_injected_session": true
    }
   ],
   "outcome": {
    "ok": false,
    "exception": "litellm.exceptions.InternalServerError",
    "status_code": 500,
    "chain": [
     "litellm.llms.openai.common_utils.OpenAIError",
     "__main__.RefusedBeforeDispatch"
    ]
   },
   "seconds": 0.01
  },
  {
   "scenario": "422 names temperature then 200, frozen kwargs",
   "intercepted_sends": 1,
   "terminal_received": 1,
   "refused_before_dispatch": 0,
   "bytes_identical": true,
   "same_url": true,
   "body_sha256": [
    "a3af2e372ba7d51c"
   ],
   "body_len": [
    447
   ],
   "distinct_bodies": 1,
   "retry_count_header": [
    "0"
   ],
   "stream_type": [
    "ByteStream"
   ],
   "refusal_reasons": [],
   "openai_clients": [
    {
     "max_retries": 0,
     "wraps_injected_session": true
    }
   ],
   "outcome": {
    "ok": false,
    "exception": "litellm.exceptions.BadRequestError",
    "status_code": 422,
    "chain": [
     "litellm.llms.openai.common_utils.OpenAIError",
     "openai.UnprocessableEntityError",
     "httpx.HTTPStatusError"
    ]
   },
   "seconds": 0.01
  },
  {
   "scenario": "422 names temperature then 200, CONTROL: global litellm.drop_params=True",
   "intercepted_sends": 2,
   "terminal_received": 2,
   "refused_before_dispatch": 0,
   "bytes_identical": true,
   "same_url": true,
   "body_sha256": [
    "a3af2e372ba7d51c",
    "437be16af8b966bb"
   ],
   "body_len": [
    447,
    429
   ],
   "distinct_bodies": 2,
   "retry_count_header": [
    "0",
    "0"
   ],
   "stream_type": [
    "ByteStream"
   ],
   "refusal_reasons": [],
   "openai_clients": [
    {
     "max_retries": 0,
     "wraps_injected_session": true
    },
    {
     "max_retries": 2,
     "wraps_injected_session": true
    }
   ],
   "outcome": {
    "ok": true,
    "returned": "ModelResponse",
    "finish_reason": "stop",
    "content_equals_canned": true,
    "prompt_tokens": 123
   },
   "seconds": 0.0
  },
  {
   "scenario": "422 names temperature then 200, CONTROL: global drop_params + one-send budget",
   "intercepted_sends": 1,
   "terminal_received": 1,
   "refused_before_dispatch": 1,
   "bytes_identical": true,
   "same_url": true,
   "body_sha256": [
    "a3af2e372ba7d51c"
   ],
   "body_len": [
    447
   ],
   "distinct_bodies": 1,
   "retry_count_header": [
    "0"
   ],
   "stream_type": [
    "ByteStream"
   ],
   "refusal_reasons": [
    "send budget exhausted"
   ],
   "openai_clients": [
    {
     "max_retries": 0,
     "wraps_injected_session": true
    },
    {
     "max_retries": 2,
     "wraps_injected_session": true
    }
   ],
   "outcome": {
    "ok": false,
    "exception": "litellm.exceptions.InternalServerError",
    "status_code": 500,
    "chain": [
     "litellm.llms.openai.common_utils.OpenAIError",
     "__main__.RefusedBeforeDispatch"
    ]
   },
   "seconds": 0.01
  },
  {
   "scenario": "307 then 200, follow_redirects=True (frozen default)",
   "intercepted_sends": 2,
   "terminal_received": 2,
   "refused_before_dispatch": 0,
   "bytes_identical": true,
   "same_url": true,
   "body_sha256": [
    "a3af2e372ba7d51c",
    "a3af2e372ba7d51c"
   ],
   "body_len": [
    447,
    447
   ],
   "distinct_bodies": 1,
   "retry_count_header": [
    "0",
    "0"
   ],
   "stream_type": [
    "ByteStream"
   ],
   "refusal_reasons": [],
   "openai_clients": [
    {
     "max_retries": 0,
     "wraps_injected_session": true
    }
   ],
   "outcome": {
    "ok": true,
    "returned": "ModelResponse",
    "finish_reason": "stop",
    "content_equals_canned": true,
    "prompt_tokens": 123
   },
   "seconds": 0.0
  },
  {
   "scenario": "307 then 200, follow_redirects=False",
   "intercepted_sends": 1,
   "terminal_received": 1,
   "refused_before_dispatch": 0,
   "bytes_identical": true,
   "same_url": true,
   "body_sha256": [
    "a3af2e372ba7d51c"
   ],
   "body_len": [
    447
   ],
   "distinct_bodies": 1,
   "retry_count_header": [
    "0"
   ],
   "stream_type": [
    "ByteStream"
   ],
   "refusal_reasons": [],
   "openai_clients": [
    {
     "max_retries": 0,
     "wraps_injected_session": true
    }
   ],
   "outcome": {
    "ok": false,
    "exception": "litellm.exceptions.APIError",
    "status_code": 307,
    "chain": [
     "litellm.llms.openai.common_utils.OpenAIError",
     "openai.APIStatusError",
     "httpx.HTTPStatusError"
    ]
   },
   "seconds": 0.01
  },
  {
   "scenario": "refusal before dispatch, frozen kwargs",
   "intercepted_sends": 0,
   "terminal_received": 0,
   "refused_before_dispatch": 1,
   "bytes_identical": true,
   "same_url": true,
   "body_sha256": [],
   "body_len": [],
   "distinct_bodies": 0,
   "retry_count_header": [],
   "stream_type": [
    "ByteStream"
   ],
   "refusal_reasons": [
    "refuse_all"
   ],
   "openai_clients": [
    {
     "max_retries": 0,
     "wraps_injected_session": true
    }
   ],
   "outcome": {
    "ok": false,
    "exception": "litellm.exceptions.InternalServerError",
    "status_code": 500,
    "chain": [
     "litellm.llms.openai.common_utils.OpenAIError",
     "__main__.RefusedBeforeDispatch"
    ]
   },
   "seconds": 0.01
  },
  {
   "scenario": "200 OK, archived call-9 prefix (psf__requests-1142 small), frozen kwargs",
   "intercepted_sends": 1,
   "terminal_received": 1,
   "refused_before_dispatch": 0,
   "bytes_identical": true,
   "same_url": true,
   "body_sha256": [
    "6676bfc21722bdbf"
   ],
   "body_len": [
    11183
   ],
   "distinct_bodies": 1,
   "retry_count_header": [
    "0"
   ],
   "stream_type": [
    "ByteStream"
   ],
   "refusal_reasons": [],
   "openai_clients": [
    {
     "max_retries": 0,
     "wraps_injected_session": true
    }
   ],
   "outcome": {
    "ok": true,
    "returned": "ModelResponse",
    "finish_reason": "stop",
    "content_equals_canned": true,
    "prompt_tokens": 123
   },
   "seconds": 0.0,
   "archived_prefix": {
    "path": "results/v2_agent/pilot_20260922_yaml_v1/psf__requests-1142__small__pilot-cp2-wc2-yaml-v1__20260922T080423Z-7ad659/call9_history.json",
    "n_messages": 18
   }
  }
 ],
 "client_cache_pitfall": {
  "session_A_sends": 2,
  "session_B_sends": 0,
  "note": "same cache key (api_key hash, timeout, max_retries, api_base, ...)"
 },
 "mini_swe_agent_layer": [
  {
   "scenario": "mswea query: 200 OK",
   "intercepted_sends": 1,
   "terminal_received": 1,
   "refused_before_dispatch": 0,
   "bytes_identical": true,
   "same_url": true,
   "body_sha256": [
    "a3af2e372ba7d51c"
   ],
   "body_len": [
    447
   ],
   "distinct_bodies": 1,
   "retry_count_header": [
    "0"
   ],
   "stream_type": [
    "ByteStream"
   ],
   "refusal_reasons": [],
   "openai_clients": [
    {
     "max_retries": 0,
     "wraps_injected_session": true
    }
   ],
   "outcome": {
    "ok": true,
    "actions": [
     {
      "command": "echo probe"
     }
    ]
   },
   "seconds": 0.0
  },
  {
   "scenario": "mswea query: 500 always",
   "intercepted_sends": 2,
   "terminal_received": 2,
   "refused_before_dispatch": 0,
   "bytes_identical": true,
   "same_url": true,
   "body_sha256": [
    "a3af2e372ba7d51c",
    "a3af2e372ba7d51c"
   ],
   "body_len": [
    447,
    447
   ],
   "distinct_bodies": 1,
   "retry_count_header": [
    "0",
    "0"
   ],
   "stream_type": [
    "ByteStream"
   ],
   "refusal_reasons": [],
   "openai_clients": [
    {
     "max_retries": 0,
     "wraps_injected_session": true
    }
   ],
   "outcome": {
    "ok": false,
    "exception": "litellm.exceptions.InternalServerError",
    "status_code": 500,
    "chain": [
     "litellm.llms.openai.common_utils.OpenAIError",
     "openai.InternalServerError",
     "httpx.HTTPStatusError"
    ]
   },
   "seconds": 4.03
  },
  {
   "scenario": "mswea query: 400 context error",
   "intercepted_sends": 1,
   "terminal_received": 1,
   "refused_before_dispatch": 0,
   "bytes_identical": true,
   "same_url": true,
   "body_sha256": [
    "a3af2e372ba7d51c"
   ],
   "body_len": [
    447
   ],
   "distinct_bodies": 1,
   "retry_count_header": [
    "0"
   ],
   "stream_type": [
    "ByteStream"
   ],
   "refusal_reasons": [],
   "openai_clients": [
    {
     "max_retries": 0,
     "wraps_injected_session": true
    }
   ],
   "outcome": {
    "ok": false,
    "exception": "litellm.exceptions.ContextWindowExceededError",
    "status_code": 400,
    "chain": [
     "litellm.llms.openai.common_utils.OpenAIError",
     "openai.BadRequestError",
     "httpx.HTTPStatusError"
    ]
   },
   "seconds": 0.01
  },
  {
   "scenario": "mswea query: refusal before dispatch, unmodified model",
   "intercepted_sends": 0,
   "terminal_received": 0,
   "refused_before_dispatch": 2,
   "bytes_identical": true,
   "same_url": true,
   "body_sha256": [],
   "body_len": [],
   "distinct_bodies": 0,
   "retry_count_header": [],
   "stream_type": [
    "ByteStream"
   ],
   "refusal_reasons": [
    "refuse_all",
    "refuse_all"
   ],
   "openai_clients": [
    {
     "max_retries": 0,
     "wraps_injected_session": true
    }
   ],
   "outcome": {
    "ok": false,
    "exception": "litellm.exceptions.InternalServerError",
    "status_code": 500,
    "chain": [
     "litellm.llms.openai.common_utils.OpenAIError",
     "__main__.RefusedBeforeDispatch"
    ]
   },
   "seconds": 4.03
  },
  {
   "scenario": "mswea query: refusal before dispatch, abort-translation sketch",
   "intercepted_sends": 0,
   "terminal_received": 0,
   "refused_before_dispatch": 1,
   "bytes_identical": true,
   "same_url": true,
   "body_sha256": [],
   "body_len": [],
   "distinct_bodies": 0,
   "retry_count_header": [],
   "stream_type": [
    "ByteStream"
   ],
   "refusal_reasons": [
    "refuse_all"
   ],
   "openai_clients": [
    {
     "max_retries": 0,
     "wraps_injected_session": true
    }
   ],
   "outcome": {
    "ok": false,
    "exception": "__main__.ProbeAbort",
    "status_code": null,
    "chain": [
     "litellm.exceptions.InternalServerError",
     "litellm.llms.openai.common_utils.OpenAIError",
     "__main__.RefusedBeforeDispatch"
    ]
   },
   "seconds": 0.01
  }
 ],
 "network_attempts": []
}
```
