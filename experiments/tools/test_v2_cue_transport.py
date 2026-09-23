"""Deterministic fixtures for DTR-REQ-005 cue-v1 transport capture (experiments/v2_agent/cue_transport.py).

Lead contract: docs/theory_feedback_20260923_req005_review.md, bullet "Transport" and answers 1-2. No model,
llama-server, container or network is used, and nothing under results/ is touched.

Every expected value below is written out BY HAND. Request bodies are typed as literal bytes following the openai
SDK's documented serialization (compact separators, ensure_ascii=False, insertion order). Canonical payloads are
typed with sorted keys, lengths are counted by hand, and every sha256 was computed with `shasum -a 256` over
those hand-built bytes, never through the module under test. Byte identity is always checked between two
independent observation points: what the in-process terminal received and the private file the capture kept.
Both are compared with the hand-typed literal.

Two layers:
  * the pure core, in this venv (no httpx/openai): bounded publication, caps, refusals and the gate, with a fake
    sender;
  * the pinned SDK path: experiments/tools/v2_cue_transport_sdk_fixture.py runs in
    work/venvs/minisweagent_04d809c through the REAL litellm.completion (and mini-swe-agent query) path, with an
    httpx.MockTransport terminal. Those tests are skipped, with the reason stated, only when that interpreter is
    absent.
"""
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/v2_agent'))
import cue_transport as CT  # noqa: E402
import request_receipt as RR  # noqa: E402

MSWEA_PY = ROOT / 'work/venvs/minisweagent_04d809c/bin/python'
SDK_FIXTURE = ROOT / 'experiments/tools/v2_cue_transport_sdk_fixture.py'

FAKE_HOME = '/Users/example-worker'
EPOCH = 1790150400.0                       # date -u -r 1790150400 -> 2026-09-23T08:00:00Z
UTC = '2026-09-23T08:00:00Z'
RESERVE = 21474836480                      # 20 GiB, a declared host reserve for the fixtures
START_BOUNDARY = 27917287424               # RESERVE + 6 GiB (6442450944)
PLENTY = 28991029248                       # RESERVE + 7 GiB
RUN_ID = 'psf__requests-1142__small__cue-v1__baseline__fixture'
IDENTITY = dict(model=dict(alias='qwen2.5-coder-7b-instruct-c03e6d3-q4_k_m', model_sha256='1' * 64),
                decoding=dict(temperature=0.0, max_tokens=1536),
                server=dict(endpoint='http://127.0.0.1:8291/v1'), tokenizer=dict(source='fixture'))

# ---- hand-typed bodies (shasum -a 256 over exactly these bytes) -------------------------------------------------
ALIAS = 'qwen2.5-coder-7b-instruct-c03e6d3-q4_k_m'
BASELINE_BODY = (
    '{"messages":[{"role":"system","content":"You are a helpful assistant that can interact with a computer."},'
    '{"role":"user","content":"Fix the bug in /testbed. Non-ASCII check: naïve café — µs."},'
    '{"role":"assistant","content":"THOUGHT: look first\\n\\n```mswea_bash_command\\nls /testbed\\n```"},'
    '{"role":"user","content":"<returncode>0</returncode>\\n<output>\\nsetup.py\\n</output>"}],'
    '"model":"qwen2.5-coder-7b-instruct-c03e6d3-q4_k_m","max_tokens":1536,"temperature":0.0}').encode('utf-8')
BASELINE_SHA256 = '62f05697cf23156deb4cb5d17d19f905d83c4dd0633f7aa004533c079e965848'
BASELINE_BYTES = 468          # 13 + 92 + 1 + 91 + 1 + 95 + 1 + 85 + 1 + 88, counted by hand
BASELINE_CANONICAL_SHA256 = 'ab1d4c5494d3e33ca653ee78fecda508b1883c49098855d4c249b62af387bce8'
CUE_TEXT = ('Recent actions returned the same visible feedback repeatedly. Use the existing /testbed checkout. '
            'Choose a different action that will provide useful new evidence, or explain why repeating the action '
            'is necessary. Check the current working directory and the existing submission instructions.')
CUE_SHA256 = '80d52625bd593cd6fecafeb06daca898792979592272d9fadcf0ddd04bd39d9e'
CUE_INSERTION = b',{"role":"user","content":"' + CUE_TEXT.encode() + b'"}'
CUE_BODY_SHA256 = 'bc4c299bb4f2e41ab20a3b5d75186251a9c1060a55d05806196e42b3d7a35928'
CUE_BODY_BYTES = 787          # 468 + 1 + 26 + 290 + 2
BODY_TAIL = b'"}],"model":"qwen2.5-coder-7b-instruct-c03e6d3-q4_k_m","max_tokens":1536,"temperature":0.0}'
OVERSIZED_BYTES = 8388738     # 39 + 8388608 + 91
OVERSIZED_SHA256 = '6b810d83eb2d552610c24617af6b10f1fb4384c458d76e18cb2f84b9233bd2de'
MULTIBYTE_BODY = b'{"messages":[{"role":"user","content":"' + ('€' * 30000).encode('utf-8') + BODY_TAIL
MULTIBYTE_BODY_SHA256 = '36ead466392c64c731af211f4092bad6b52881e81ef7e13e643b15edc6a7678a'
MULTIBYTE_CANONICAL_SHA256 = 'c4c2efc681d2852fc2785a24064b4f792f55b4b7ef3ace8c4b9365f3d092f517'
MULTIBYTE_HEAD_SHA256 = '96eb3c7dac363e42282ab0dd2524b2af1f7e64fa853f95b99ff8ff813b243abf'
MULTIBYTE_TAIL_SHA256 = '8a32220ab78ba2fec8d0ac2e3efcc351be8d1726a129fb1e64188ca70d89e42e'

PLAIN_REQUEST = (b'{"model": "m", "messages": [{"role": "user", "content": "fix the failing test"}], '
                 b'"temperature": 0.0, "max_tokens": 1536}')
PLAIN_SHA256 = '95a92b44dff3ab76a5cb5bb46df2b126a5a3758548f6ef198292f66923fe2572'
PLAIN_CANONICAL = (b'{"max_tokens":1536,"messages":[{"content":"fix the failing test","role":"user"}],"model":"m",'
                   b'"temperature":0.0}')
PLAIN_CANONICAL_SHA256 = '373f7f31f1f7311ad7d0d0eeede2aab436cbff47b56ea8d80305fb39ca06b257'
OK_JSON = (b'{"choices":[{"finish_reason":"stop","index":0,"message":{"content":"ok","role":"assistant"}}],'
           b'"usage":{"completion_tokens":7,"prompt_tokens":123,"total_tokens":130}}')
OK_JSON_SHA256 = 'f1b3098daacfa3cc660e20ae30137f51811b6bb32a6033a0a77577b2c4a6fc56'
X_8MIB_SHA256 = '0c77bc0a0795a93612d45256897456d0fcb24f151c44c150d07ecd03f4ef5168'
X_8MIB_PLUS_1_SHA256 = '942d6013edf5b8bf6c141eadd970afb4d1dec9f2d6d92dbe93f4be90748037ed'
SECRET = 'sk-live0123456789'
USAGE_SOURCE = ("the usage object of the server response body, read after the client read it; litellm's parsed "
                'usage is not used because it reports zeros when the server sent none')
NO_USAGE_SOURCE = 'the server response body carried no usable usage object, or it was not read; usage stays unknown'
URL = 'http://127.0.0.1:8291/v1/chat/completions'


class FakeResponse:
    """Stands in for an httpx.Response: status plus the body the client read (or ResponseNotRead)."""

    def __init__(self, status_code, body=None, read=True):
        self.status_code, self._body, self._read = status_code, body, read

    @property
    def content(self):
        if not self._read:
            raise RuntimeError('ResponseNotRead')
        return self._body


def wire(content_length=None):
    headers = [('Content-Type', 'application/json'), ('Authorization', 'Bearer ' + SECRET)]
    if content_length is not None:
        headers.append(('Content-Length', str(content_length)))
    return CT.wire_metadata('POST', URL, headers)


def make(tmp_path, *, free=None, write_once=None, used=0, sends=1, on_error=None):
    root = tmp_path / 'root'
    store = CT.BoundedReceiptStore(root / 'work' / 'receipts', root / 'published', cohort='cue-v1', run_id=RUN_ID,
                                   identity=IDENTITY, home=FAKE_HOME, clock=lambda: EPOCH, root=root,
                                   write_once=write_once)
    capture = CT.CueTransportCapture(store, budget=CT.RequestBudget(used=used), host_reserve_bytes=RESERVE,
                                     free_space_probe=free or (lambda _p: PLENTY), sends_per_query_attempt=sends,
                                     on_receipt_error=on_error, clock=lambda: EPOCH, accounting_fixture=sends != 1)
    return store, capture


def forward_call(capture, body, sent, *, response=None, replayable=True, stream=None, w=None, times=1):
    def call():
        result = None
        for _ in range(times):
            result = capture.forward(body=body, wire=w or wire(), replayable=replayable,
                                     stream_bytes=body if stream is None else stream,
                                     send=lambda: (sent.append(bytes(body)), response or FakeResponse(200, OK_JSON))[1])
        return result
    return call


def failing(suffix, exc=None):
    def write(path, data):
        if str(path).endswith(suffix):
            raise exc or OSError(28, 'simulated: no space left on device')
        return RR._write_once(path, data)
    return write


def read_json(path):
    return json.loads(Path(path).read_bytes().decode('utf-8'))


# =================================================================== declared bounds

def test_the_declared_bounds_are_the_lead_s_numbers():
    assert CT.BODY_CAP_BYTES == 8388608
    assert CT.COHORT_RAW_RESERVATION_BYTES == 4831838208          # 576 x 8 MiB = 4.5 GiB
    assert CT.START_FREE_ABOVE_RESERVE_BYTES == 6442450944        # 6 GiB
    assert CT.PUBLIC_WHOLE_MAX_BYTES == 65536
    assert (CT.PUBLIC_HEAD_BYTES, CT.PUBLIC_TAIL_BYTES) == (32768, 32768)
    assert CT.PUBLIC_RECORD_CAP_BYTES == 131072
    assert CT.SENDS_PER_QUERY_ATTEMPT == 1
    assert CT.RequestBudget(used=0).limit == 576


def test_the_request_budget_refuses_an_unstated_or_enlarged_cohort_budget():
    with pytest.raises(TypeError):
        CT.RequestBudget()                                        # `used` must be stated by the queue
    with pytest.raises(ValueError):
        CT.RequestBudget(used=0, limit=577)
    with pytest.raises(ValueError):
        CT.RequestBudget(used=5, limit=4)
    budget = CT.RequestBudget(used=574)
    assert (budget.consume(), budget.consume(), budget.remaining()) == (575, 576, 0)
    with pytest.raises(ValueError):
        budget.consume()


def test_wire_metadata_publishes_no_credential_value_query_or_userinfo():
    got = CT.wire_metadata('POST', 'http://user:pw@127.0.0.1:8291/v1/chat/completions?key=abc',
                           [('Authorization', 'Bearer ' + SECRET), ('Content-Type', 'application/json'),
                            ('Content-Length', '468'), ('X-Stainless-Retry-Count', '0'), ('Cookie', 'c=1')])
    assert got == dict(method='POST', url='http://127.0.0.1:8291/v1/chat/completions', url_query_present=True,
                       url_userinfo_present=True,
                       header_names=['authorization', 'content-length', 'content-type', 'cookie',
                                     'x-stainless-retry-count'], header_names_total=5, header_names_omitted=0,
                       headers_published={'content-type': 'application/json', 'content-length': '468',
                                          'x-stainless-retry-count': '0'},
                       content_length=468, sensitive_headers_present=['authorization', 'cookie'],
                       sensitive_header_values_persisted=False)


# =================================================================== bounded public receipts (answer 1)

def test_a_payload_within_64_kib_is_published_whole_with_its_complete_hash_and_length(tmp_path):
    store, _ = make(tmp_path)
    rec = store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=PLAIN_REQUEST)
    pub = rec['payload_publication']
    assert (rec['raw_request_sha256'], rec['raw_request_bytes']) == (PLAIN_SHA256, 121)
    assert (pub['mode'], pub['complete'], pub['truncated']) == ('whole', True, False)
    assert (pub['sanitized_payload_sha256'], pub['sanitized_payload_bytes']) == (PLAIN_CANONICAL_SHA256, 111)
    assert (pub['published_sha256'], pub['published_bytes']) == (PLAIN_CANONICAL_SHA256, 111)
    assert rec['payload_projection'] == {'model': 'm', 'messages': [{'role': 'user', 'content': 'fix the failing test'}],
                                         'temperature': 0.0, 'max_tokens': 1536}
    assert json.dumps(rec['payload_projection'], sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False).encode() == PLAIN_CANONICAL
    assert (pub['head'], pub['tail'], pub['omitted_middle']) == (None, None, None)
    assert (tmp_path / 'root/work/receipts/call001_attempt01.request.raw').read_bytes() == PLAIN_REQUEST
    assert RR.verify_published_projection(tmp_path / 'root/published/call001_attempt01.request.json',
                                          expect_phase='pre_dispatch')['status'] == 'published_projection_verified'


def test_a_payload_over_64_kib_publishes_a_32_kib_head_and_tail_with_original_offsets(tmp_path):
    store, _ = make(tmp_path)
    raw = b'{"messages":[{"role":"user","content":"' + b'a' * 70000 + b'"}]}'
    pub = store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=raw)['payload_publication']
    assert (pub['mode'], pub['complete'], pub['truncated']) == ('head_tail', False, True)
    assert (pub['sanitized_payload_sha256'], pub['sanitized_payload_bytes']) == (
        '82a386efbc1cdcaf41eed60d0e9fd39d7705921ca228ed63e953cd390042c781', 70043)   # 25 + 70000 + 18
    head, tail = pub['head'], pub['tail']
    assert {k: head[k] for k in ('offset_start', 'offset_end', 'bytes', 'boundary_adjustment_bytes', 'sha256')} == dict(
        offset_start=0, offset_end=32768, bytes=32768, boundary_adjustment_bytes=0,
        sha256='732fb0c6c00542b315fdbb583cdf3bbd16db25f78235eda7d9ee796a94d402b7')
    assert {k: tail[k] for k in ('offset_start', 'offset_end', 'bytes', 'boundary_adjustment_bytes', 'sha256')} == dict(
        offset_start=37275, offset_end=70043, bytes=32768, boundary_adjustment_bytes=0,
        sha256='5d904cee4b4780642732d480334571d019a448ae45cef56a10d2f3097d585768')
    assert head['text'] == '{"messages":[{"content":"' + 'a' * 32743
    assert tail['text'] == 'a' * 32750 + '","role":"user"}]}'
    assert pub['omitted_middle'] == dict(offset_start=32768, offset_end=37275, bytes=4507)
    assert (pub['published_sha256'], pub['published_bytes']) == (None, 65536)
    assert pub['note'] == ('a head/tail preview is never the complete request; the complete exact bytes are private '
                           'and only their digest and length are published here')


def test_a_multibyte_payload_is_cut_only_at_utf8_character_boundaries(tmp_path):
    store, _ = make(tmp_path)
    raw = b'{"messages":[{"role":"user","content":"' + ('€' * 30000).encode('utf-8') + b'"}]}'
    pub = store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=raw)['payload_publication']
    assert (pub['mode'], pub['sanitized_payload_bytes'], pub['sanitized_payload_sha256']) == (
        'head_tail', 90043, '8ae3252fc04c8b1a618917fc96295e8eec8894d3d31649b220596c317297f53c')
    # 25 ASCII bytes, then 3-byte characters: 25 + 3*10914 = 32767 <= 32768; 25 + 3*19084 = 57277 >= 90043 - 32768
    assert {k: pub['head'][k] for k in ('offset_end', 'bytes', 'boundary_adjustment_bytes', 'sha256')} == dict(
        offset_end=32767, bytes=32767, boundary_adjustment_bytes=1,
        sha256='d799e063c9f2a729100f79bf957fe305361ab69d9d841de42d77b0268db3e3e5')
    assert {k: pub['tail'][k] for k in ('offset_start', 'bytes', 'boundary_adjustment_bytes', 'sha256')} == dict(
        offset_start=57277, bytes=32766, boundary_adjustment_bytes=2,
        sha256='b8b45a01b308edf8cbf46f717cffc277ae42ecf8fd3124d7fcfd8e6ff7e1dd8e')
    assert pub['head']['text'] == '{"messages":[{"content":"' + '€' * 10914
    assert pub['tail']['text'] == '€' * 10916 + '","role":"user"}]}'
    assert pub['omitted_middle'] == dict(offset_start=32767, offset_end=57277, bytes=24510)
    size = (tmp_path / 'root/published/call001_attempt01.request.json').stat().st_size
    # the UTF-8 excerpts alone are 32767 + 32766 bytes; the whole receipt is pinned as a reviewed literal
    assert size == 71136


def test_redaction_happens_before_the_excerpt_is_cut(tmp_path):
    store, _ = make(tmp_path)
    raw = b'{"messages":[{"role":"user","content":"api_key=' + SECRET.encode() + b' ' + b'b' * 70000 + b'"}]}'
    rec = store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=raw)
    pub = rec['payload_publication']
    assert (rec['raw_request_sha256'], rec['raw_request_bytes']) == (
        '3bf3bf10e625243b7e42867f26ed5a85fb77e4d6e55c65b00173b0ef4f3ed846', 70069)
    assert (pub['sanitized_payload_sha256'], pub['sanitized_payload_bytes']) == (
        '0c3dc49a0aecb778e6ef41e7f725480183c0a40a745f197e8455b1f7fb89157d', 70062)
    assert pub['head']['text'] == '{"messages":[{"content":"api_key=<WITHHELD> ' + 'b' * 32724
    assert pub['head']['sha256'] == 'bc9b4d4103984cf57b073f1a359bad97e3743477f634a40af96c9fdec6aeee9b'
    assert [(t['transformation'], t['field'], t['occurrences'])
            for t in rec['sanitization']['transformations']] == [
        ('secret_value_masked_in_text', 'request_payload.messages[0].content', 1)]
    assert SECRET.encode() not in (tmp_path / 'root/published/call001_attempt01.request.json').read_bytes()
    assert SECRET.encode() in (tmp_path / 'root/work/receipts/call001_attempt01.request.raw').read_bytes()


def test_a_head_tail_preview_that_escapes_past_128_kib_is_omitted_entirely_with_its_reason(tmp_path):
    store, _ = make(tmp_path)
    raw = b'{"messages":[{"role":"user","content":"' + b'\\"' * 40000 + b'"}]}'     # 40000 quote characters
    rec = store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=raw)
    pub = rec['payload_publication']
    assert (pub['mode'], pub['omitted_preview_mode'], pub['omitted_preview_bytes']) == ('omitted', 'head_tail', 65536)
    assert (pub['sanitized_payload_sha256'], pub['sanitized_payload_bytes']) == (
        'de520ca02fc228c437b82f9f8114581849c0f100e34310c91884083403e78843', 80043)
    assert (pub['head'], pub['tail'], pub['published_bytes'], pub['complete']) == (None, None, 0, False)
    assert pub['reason'] == ('the serialized receipt with this preview exceeded the 131072-byte public record cap '
                             'after JSON escaping; the preview is omitted entirely, and the complete sanitized and '
                             'raw digests and lengths are kept')
    assert rec['raw_request_bytes'] == 80043                     # 39 + 80000 + 4
    assert (tmp_path / 'root/published/call001_attempt01.request.json').stat().st_size <= 131072


def test_a_whole_payload_whose_serialized_receipt_exceeds_128_kib_is_omitted_not_truncated(tmp_path):
    store, _ = make(tmp_path)
    raw = b'{"messages":[' + b'"",' * 20999 + b'""]}'      # 63014 canonical bytes; 21000 indented list entries
    rec = store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=raw)
    pub = rec['payload_publication']
    assert (pub['mode'], pub['omitted_preview_mode'], pub['omitted_preview_bytes']) == ('omitted', 'whole', 63014)
    assert pub['sanitized_payload_sha256'] == 'c1b13b5dbd2cc1d57c670322b99b80f67cd6d9ae73ce031c4c6e6d1a6ff58926'
    assert (rec['payload_projection'], rec['payload_projection_available']) == (None, False)
    assert (tmp_path / 'root/published/call001_attempt01.request.json').stat().st_size <= 131072


def test_transformation_metadata_is_bounded_with_an_omitted_entry_count(tmp_path):
    store, _ = make(tmp_path)
    raw = (b'{"messages":[' + b','.join(b'{"role":"user","content":"see /Users/example-worker/x%02d"}' % i
                                          for i in range(40)) + b']}')
    rec = store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=raw)
    san = rec['sanitization']
    assert (san['applied'], san['transformations_total'], san['transformations_listed'],
            san['transformations_omitted'], san['transformation_listing_limit']) == (True, 40, 32, 8, 32)
    assert san['transformations_by_type'] == {'home_path_prefix_masked': {'entries': 40, 'occurrences': 40}}
    assert [t['field'] for t in san['transformations']][::31] == ['request_payload.messages[0].content',
                                                                  'request_payload.messages[31].content']
    assert rec['payload_projection']['messages'][39]['content'] == 'see <HOME>/x39'


def test_an_outcome_record_is_bounded_explicitly_and_stays_under_128_kib(tmp_path):
    store, _ = make(tmp_path)
    store.record_request(logical_call_id=2, physical_attempt_id=1, serialized=PLAIN_REQUEST)
    rec = store.record_outcome(logical_call_id=2, physical_attempt_id=1, ok=False, error_class='E' * 5000,
                               error_detail='€' * 100000, finish_reason='f' * 1000, http_status=500)
    assert (rec['error_class'], rec['error_class_chars'], rec['error_class_truncated']) == ('E' * 256, 5000, True)
    assert (rec['error_detail'], rec['error_detail_chars'], rec['error_detail_complete'],
            rec['error_detail_truncated_to']) == ('€' * 300, 100000, False, 300)
    assert (rec['finish_reason'], rec['finish_reason_chars'], rec['finish_reason_truncated']) == ('f' * 64, 1000, True)
    assert rec['server_reported_usage']['usage_known'] is False and rec['server_reported_usage']['prompt_tokens'] is None
    assert [t['transformation'] for t in rec['sanitization']['transformations']] == [
        'error_class_truncated', 'error_detail_truncated']
    assert (tmp_path / 'root/published/call002_attempt01.outcome.json').stat().st_size <= 131072
    # the accepted helper's own completeness() validates these bounded records unchanged
    state = RR.RequestReceiptStore.completeness(store)
    assert (state['complete'], state['invalid_records'], state['attempt_keys']) == (True, [], ['call002_attempt01'])


def test_an_identity_too_large_for_any_receipt_is_refused_before_any_work(tmp_path):
    big = dict(IDENTITY, server=dict(endpoint='http://127.0.0.1:8291/v1', note='n' * 140000))
    with pytest.raises(RR.ReceiptError):
        CT.BoundedReceiptStore(tmp_path / 'root/work/r', tmp_path / 'root/pub', cohort='cue-v1', run_id=RUN_ID,
                               identity=big, home=FAKE_HOME, root=tmp_path / 'root')


# =================================================================== the gate: storage, cap, refusals

def test_the_start_preflight_needs_6_gib_above_the_declared_host_reserve(tmp_path):
    _, capture = make(tmp_path / 'ok', free=lambda _p: START_BOUNDARY)
    assert {k: capture.start_preflight[k] for k in ('observed_free_bytes', 'required_free_bytes', 'passed')} == dict(
        observed_free_bytes=27917287424, required_free_bytes=27917287424, passed=True)
    with pytest.raises(CT.StartPreflightRefused) as info:
        make(tmp_path / 'short', free=lambda _p: START_BOUNDARY - 1)
    refusal = info.value.refusal
    assert (refusal['reason_code'], refusal['infrastructure_stop'], refusal['physical_request']) == (
        'insufficient_free_space_at_start', True, False)
    assert refusal['free_space']['observed_free_bytes'] == 27917287423
    record = read_json(tmp_path / 'short/root/published/refusal001.refusal.json')
    assert record['refusal']['reason_code'] == 'insufficient_free_space_at_start'
    with pytest.raises(ValueError):
        CT.CueTransportCapture(CT.BoundedReceiptStore(tmp_path / 'r/work/a', tmp_path / 'r/p', cohort='cue-v1',
                                                      identity=IDENTITY, home=FAKE_HOME, root=tmp_path / 'r'),
                               budget=CT.RequestBudget(used=0), host_reserve_bytes=None)


def test_a_normal_send_is_persisted_before_it_is_forwarded_and_its_outcome_linked(tmp_path):
    store, capture = make(tmp_path)
    sent, order = [], []

    def send():
        order.append(sorted(p.name for p in (tmp_path / 'root/work/receipts').iterdir()))
        sent.append(PLAIN_REQUEST)
        return FakeResponse(200, OK_JSON)
    result = capture.dispatch(logical_call_id=1, query_attempt=1, call=lambda: capture.forward(
        body=PLAIN_REQUEST, wire=wire(121), replayable=True, stream_bytes=PLAIN_REQUEST, send=send))
    assert result.status_code == 200 and sent == [PLAIN_REQUEST]
    assert order == [['call001_attempt01.request.raw']]                  # durable BEFORE the send
    outcome = read_json(tmp_path / 'root/published/call001_attempt01.outcome.json')
    usage = outcome['server_reported_usage']
    assert (outcome['outcome'], outcome['http_status'], outcome['finish_reason']) == ('ok', 200, 'stop')
    assert (usage['prompt_tokens'], usage['completion_tokens'], usage['total_tokens'], usage['total_tokens_source'],
            usage['source']) == (123, 7, 130, 'server_reported', USAGE_SOURCE)
    assert (outcome['send']['response_body_sha256'], outcome['send']['response_body_bytes']) == (OK_JSON_SHA256, 165)
    assert capture.attempts == [dict(
        logical_call_id=1, query_attempt_id=1, attempt_keys=['call001_attempt01'], physical_sends=1,
        transport_attempted=True, response_received=True, http_statuses=[200], refused_before_dispatch=[],
        infrastructure_stop=False, call_outcome='returned', exception_class=None, bookkeeping_failures=0,
        started_utc=UTC, ended_utc=UTC)]
    integrity = capture.integrity()
    assert (integrity['receipt_integrity'], integrity['queue_may_continue'], integrity['budget']) == (
        'complete', True, dict(limit=576, used=1))
    receipt = read_json(tmp_path / 'root/published/call001_attempt01.request.json')
    assert receipt['send']['cohort_request_ordinal'] == 1 and receipt['sensitive_header_values_persisted'] is False
    for path in (tmp_path / 'root').rglob('*'):
        if path.is_file():
            assert SECRET.encode() not in path.read_bytes(), path.name


def test_an_oversized_body_is_refused_before_dispatch_and_never_truncated(tmp_path):
    _, capture = make(tmp_path)
    sent = []
    body = b'x' * 8388609
    with pytest.raises(CT.InfrastructureStop) as info:
        capture.dispatch(logical_call_id=1, query_attempt=1, call=forward_call(capture, body, sent))
    refusal = info.value.refusal
    assert (refusal['reason_code'], refusal['classification'], refusal['body_bytes'], refusal['body_sha256']) == (
        'body_over_cap', 'measurement', 8388609, X_8MIB_PLUS_1_SHA256)
    assert (refusal['physical_request'], refusal['body_truncated'], refusal['retried_by_capture']) == (False, False, False)
    assert sent == [] and list((tmp_path / 'root/work/receipts').iterdir()) == []
    assert sorted(p.name for p in (tmp_path / 'root/published').iterdir()) == ['refusal001.refusal.json']
    assert capture.budget.used == 0


def test_a_body_of_exactly_8_mib_is_within_the_cap(tmp_path):
    _, capture = make(tmp_path)
    sent = []
    capture.dispatch(logical_call_id=1, query_attempt=1, call=forward_call(capture, b'x' * 8388608, sent))
    receipt = read_json(tmp_path / 'root/published/call001_attempt01.request.json')
    assert (receipt['raw_request_sha256'], receipt['raw_request_bytes']) == (X_8MIB_SHA256, 8388608)
    assert receipt['payload_publication']['mode'] == 'unavailable'           # not JSON: digest/length only
    assert len(sent) == 1


@pytest.mark.parametrize('suffix', ['.request.raw', '.request.json'])
def test_a_failed_durable_write_refuses_before_dispatch(tmp_path, suffix):
    store, capture = make(tmp_path, write_once=failing(suffix))
    sent = []
    with pytest.raises(CT.InfrastructureStop) as info:
        capture.dispatch(logical_call_id=1, query_attempt=1, call=forward_call(capture, PLAIN_REQUEST, sent))
    refusal = info.value.refusal
    assert (refusal['reason_code'], refusal['classification'], refusal['body_sha256'], refusal['body_bytes'],
            refusal['detail']) == ('durable_write_failed', 'storage', PLAIN_SHA256, 121,
                                   'OSError during the durable pre-dispatch write')
    assert sent == [] and capture.budget.used == 0
    holes = store.completeness()
    expected_holes = ['call001_attempt01'] if suffix == '.request.json' else []
    assert holes['raw_without_published_record'] == expected_holes           # a half-written receipt is a hole
    assert capture.integrity()['queue_may_continue'] is False


def test_a_write_once_collision_is_a_protocol_refusal_not_an_overwrite(tmp_path):
    _, capture = make(tmp_path)
    (tmp_path / 'root/work/receipts/call001_attempt01.request.raw').write_bytes(b'earlier')
    sent = []
    with pytest.raises(CT.InfrastructureStop) as info:
        capture.dispatch(logical_call_id=1, query_attempt=1, call=forward_call(capture, PLAIN_REQUEST, sent))
    refusal = info.value.refusal
    assert (refusal['reason_code'], refusal['classification'], refusal['attempt_key'], sent) == (
        'receipt_contract_refused', 'protocol', 'call001_attempt01', [])
    assert refusal['receipt_files_present'] == ['call001_attempt01.request.raw']
    assert refusal['detail'] == ('ReceiptError: write-once receipt already exists; refusing to overwrite '
                                 'call001_attempt01.request.raw')
    assert (tmp_path / 'root/work/receipts/call001_attempt01.request.raw').read_bytes() == b'earlier'


def test_free_space_is_rechecked_before_each_write(tmp_path):
    calls = []

    def probe(_path):
        calls.append(1)
        # probes 1-2: the start preflight (private and public directory); 3: the first request write
        return PLENTY if len(calls) < 4 else RESERVE + 100        # less than any record, even a log line
    _, capture = make(tmp_path / 'short', free=probe)
    sent = []
    capture.dispatch(logical_call_id=1, query_attempt=1, call=forward_call(capture, PLAIN_REQUEST, sent))
    failure = capture.bookkeeping_failures[0]
    assert len(sent) == 1 and (failure['phase'], failure['error_class'], failure['secondary_log_written'],
                               failure['secondary_log_error']) == (
        'post_dispatch_outcome', '_SpaceShortfall', False, 'insufficient_free_space')
    with pytest.raises(CT.InfrastructureStop) as info:
        capture.dispatch(logical_call_id=2, query_attempt=1, call=forward_call(capture, PLAIN_REQUEST, sent))
    refusal = info.value.refusal
    check = refusal['free_space']['checks'][0]
    # the same request written with plenty of space: its receipt's size on disk is what the recheck had to cover
    _, clean = make(tmp_path / 'clean')
    clean.dispatch(logical_call_id=1, query_attempt=1, call=forward_call(clean, PLAIN_REQUEST, []))
    clean.dispatch(logical_call_id=2, query_attempt=1, call=forward_call(clean, PLAIN_REQUEST, []))
    receipt_size = (tmp_path / 'clean/root/published/call002_attempt01.request.json').stat().st_size
    assert (refusal['reason_code'], check['directory'], check['observed_free_bytes'], check['host_reserve_bytes'],
            check['probe_error']) == ('insufficient_free_space', 'private', 21474836580, RESERVE, None)
    assert check['bytes_to_write'] == 121 + receipt_size + 131072       # raw + receipt + one reserved outcome
    assert check['required_free_bytes'] == RESERVE + 121 + receipt_size + 131072
    assert (refusal['record_written'], refusal['record_error']) == (False, 'insufficient_free_space')
    assert len(sent) == 1                                          # nothing further reached the sender
    assert capture.integrity()['reasons'] == ['post-dispatch bookkeeping failure(s): 1',
                                              'the receipt set has holes or invalid records',
                                              'refusal record(s) not durably written: [1]']


def test_a_failing_free_space_probe_refuses(tmp_path):
    calls = []

    def probe(_path):
        calls.append(1)
        if len(calls) > 2:                                         # after the two start-preflight probes
            raise OSError('statfs failed')
        return PLENTY
    _, capture = make(tmp_path, free=probe)
    with pytest.raises(CT.InfrastructureStop) as info:
        capture.dispatch(logical_call_id=1, query_attempt=1, call=forward_call(capture, PLAIN_REQUEST, []))
    assert (info.value.refusal['reason_code'], info.value.refusal['free_space']['checks'][0]['probe_error'],
            info.value.refusal['free_space']['checks'][0]['observed_free_bytes']) == (
        'insufficient_free_space', 'OSError', None)


def test_non_replayable_mismatched_or_misdeclared_bodies_are_refused_unsent(tmp_path):
    for label, kwargs, code, digest in (
            ('stream', dict(replayable=False), 'non_replayable_body', None),
            ('mismatch', dict(stream=PLAIN_REQUEST + b' '), 'stream_body_mismatch', PLAIN_SHA256),
            ('length', dict(w=wire(120)), 'content_length_mismatch', PLAIN_SHA256)):
        _, capture = make(tmp_path / label)
        sent = []
        with pytest.raises(CT.InfrastructureStop) as info:
            capture.dispatch(logical_call_id=1, query_attempt=1,
                             call=forward_call(capture, PLAIN_REQUEST, sent, **kwargs))
        assert (info.value.refusal['reason_code'], info.value.refusal['body_sha256'], sent) == (code, digest, [])


def test_a_second_send_inside_one_query_attempt_is_refused_and_recorded_but_is_not_a_stop(tmp_path):
    store, capture = make(tmp_path)
    sent = []
    with pytest.raises(CT.PreDispatchRefusal) as info:
        capture.dispatch(logical_call_id=1, query_attempt=1, call=forward_call(capture, PLAIN_REQUEST, sent, times=2))
    assert (info.value.refusal['reason_code'], info.value.refusal['classification'],
            info.value.refusal['infrastructure_stop']) == ('query_attempt_send_limit', 'hidden_resend_suppressed', False)
    assert len(sent) == 1 and capture.stopped is None
    assert capture.attempts[0]['refused_before_dispatch'] == ['query_attempt_send_limit']
    # the next query attempt of the same logical call is its own physical attempt and receipt
    capture.dispatch(logical_call_id=1, query_attempt=2, call=forward_call(capture, PLAIN_REQUEST, sent))
    assert sorted(p.name for p in store.private_dir.iterdir()) == ['call001_attempt01.request.raw',
                                                                   'call001_attempt02.request.raw']
    assert capture.budget.used == 2


def test_with_two_sends_allowed_the_extra_send_consumes_its_own_receipt_and_budget_unit(tmp_path):
    store, capture = make(tmp_path, sends=2)
    sent = []
    capture.dispatch(logical_call_id=1, query_attempt=1, call=forward_call(capture, PLAIN_REQUEST, sent, times=2))
    assert len(sent) == 2 and capture.budget.used == 2
    first = read_json(store.outcome_path('call001_attempt01'))
    second = read_json(store.outcome_path('call001_attempt02'))
    assert (first['outcome'], first['error_class'], first['send']['superseded_by_later_send']) == (
        'error', 'SupersededBySameAttemptResend', True)
    assert (second['outcome'], second['send']['cohort_request_ordinal']) == ('ok', 2)


def test_budget_exhaustion_scope_violations_and_the_latch_all_stop_before_any_send(tmp_path):
    _, capture = make(tmp_path / 'budget', used=576)
    sent = []
    with pytest.raises(CT.InfrastructureStop) as info:
        capture.dispatch(logical_call_id=1, query_attempt=1, call=forward_call(capture, PLAIN_REQUEST, sent))
    assert info.value.refusal['reason_code'] == 'cohort_request_budget_exhausted'
    called = []
    with pytest.raises(CT.InfrastructureStop) as latched:
        capture.dispatch(logical_call_id=2, query_attempt=1, call=lambda: called.append(1))
    assert called == [] and latched.value.refusal['reason_code'] == 'cohort_request_budget_exhausted'
    _, outside = make(tmp_path / 'outside')
    with pytest.raises(CT.PreDispatchRefusal) as info:
        forward_call(outside, PLAIN_REQUEST, sent)()             # a send with no open query attempt
    assert info.value.refusal['reason_code'] == 'no_open_query_attempt' and outside.stopped is not None
    for label, logical, attempt in (('h25', 25, 1), ('a3', 1, 3), ('zero', 0, 1), ('bool', True, 1)):
        _, capture = make(tmp_path / label)
        with pytest.raises(CT.InfrastructureStop) as info:
            capture.dispatch(logical_call_id=logical, query_attempt=attempt, call=lambda: called.append(1))
        assert info.value.refusal['reason_code'] == 'invalid_query_identity'
    assert called == [] and sent == []


def test_a_call_that_returns_without_a_captured_send_is_a_stop_that_keeps_the_result(tmp_path):
    _, capture = make(tmp_path)
    with pytest.raises(CT.InfrastructureStop) as info:
        capture.dispatch(logical_call_id=1, query_attempt=1, call=lambda: 'result from an uncaptured path')
    assert (info.value.refusal['reason_code'], info.value.result) == ('uncaptured_success',
                                                                     'result from an uncaptured path')


# =================================================================== post-dispatch bookkeeping (answer 2)

def test_a_failed_outcome_write_keeps_the_model_success_and_marks_integrity_incomplete(tmp_path):
    seen = []

    def callback(failure):
        seen.append(failure['phase'])
        raise RuntimeError('reporting sink is down')
    store, capture = make(tmp_path, write_once=failing('.outcome.json'), on_error=callback)
    sent = []
    response = FakeResponse(200, OK_JSON)
    result = capture.dispatch(logical_call_id=1, query_attempt=1,
                              call=forward_call(capture, PLAIN_REQUEST, sent, response=response))
    assert result is response and len(sent) == 1                      # the same object; nothing re-sent
    assert [(f['phase'], f['error_class']) for f in capture.bookkeeping_failures] == [
        ('post_dispatch_outcome', 'OSError'), ('receipt_error_callback', 'RuntimeError')]
    assert seen == ['post_dispatch_outcome'] and capture.bookkeeping_failures[0]['secondary_log_written'] is True
    log = [json.loads(line) for line in (store.private_dir / 'bookkeeping_errors.jsonl').read_text().splitlines()]
    assert [(e['attempt_key'], e['phase']) for e in log] == [('call001_attempt01', 'post_dispatch_outcome')]
    integrity = capture.integrity()
    assert (integrity['receipt_integrity'], integrity['queue_may_continue'], integrity['infrastructure_stop']) == (
        'incomplete', False, False)
    assert integrity['store']['published_record_without_outcome'] == ['call001_attempt01']
    assert capture.attempts[0]['bookkeeping_failures'] == 2


def test_a_failed_outcome_write_never_replaces_the_original_model_exception(tmp_path):
    _, capture = make(tmp_path, write_once=failing('.outcome.json'))
    original = ValueError('the model call failed')

    def call():
        capture.forward(body=PLAIN_REQUEST, wire=wire(), replayable=True, stream_bytes=PLAIN_REQUEST,
                        send=lambda: FakeResponse(400, b'{"error":{"message":"bad"}}'))
        raise original
    with pytest.raises(ValueError) as info:
        capture.dispatch(logical_call_id=1, query_attempt=1, call=call)
    assert info.value is original
    assert capture.sends[0]['http_status'] == 400 and len(capture.bookkeeping_failures) == 1


def test_usage_is_never_fabricated_when_the_server_omits_it_or_the_body_was_not_read(tmp_path):
    for label, response in (('omitted', FakeResponse(200, b'{"choices":[{"finish_reason":"stop"}]}')),
                            ('unread', FakeResponse(200, read=False))):
        store, capture = make(tmp_path / label)
        capture.dispatch(logical_call_id=1, query_attempt=1,
                         call=forward_call(capture, PLAIN_REQUEST, [], response=response))
        outcome = read_json(store.outcome_path('call001_attempt01'))
        usage = outcome['server_reported_usage']
        assert (usage['prompt_tokens'], usage['completion_tokens'], usage['total_tokens'], usage['usage_known'],
                usage['source']) == (None, None, None, False, NO_USAGE_SOURCE)
        assert outcome['send']['response_body_available'] is (label == 'omitted')


# =================================================================== repairs after the adversarial review

class EpisodeDeadline(TimeoutError):
    """Stands in for the frozen driver's EpisodeDeadline(TimeoutError); the frozen module is not imported here."""


def raising_writer(suffix, exc_factory, *, times=1, delay=None):
    """write_once that fails for `suffix` the first `times` calls (or sleeps `delay` s, for a real alarm)."""
    seen = []

    def write(path, data):
        if str(path).endswith(suffix) and len(seen) < times:
            seen.append(str(path))
            if delay is not None:
                time.sleep(delay)
            else:
                raise exc_factory()
        return RR._write_once(path, data)
    return write


@pytest.fixture
def alarm():
    """A real one-shot SIGALRM that raises EpisodeDeadline, exactly the frozen driver's mechanism."""
    raised = []

    def handler(_signum, _frame):
        raised.append(EpisodeDeadline('absolute inference deadline reached; cleanup only'))
        raise raised[-1]
    previous = signal.signal(signal.SIGALRM, handler)
    yield raised
    signal.setitimer(signal.ITIMER_REAL, 0)
    signal.signal(signal.SIGALRM, previous)


def test_a_deadline_during_the_outcome_write_is_re_raised_not_swallowed(tmp_path, alarm):
    store, capture = make(tmp_path, write_once=raising_writer('.outcome.json', None, delay=5.0))
    sent = []
    signal.setitimer(signal.ITIMER_REAL, 0.2)
    with pytest.raises(EpisodeDeadline) as info:
        capture.dispatch(logical_call_id=1, query_attempt=1, call=forward_call(capture, PLAIN_REQUEST, sent))
    assert info.value is alarm[0]                                  # the very deadline the alarm raised
    assert len(sent) == 1 and capture.bookkeeping_failures == []   # a deadline is not a bookkeeping failure
    assert capture.interrupted_writes == [dict(attempt_key='call001_attempt01', error_class='EpisodeDeadline',
                                               phase='post_dispatch_outcome')]
    assert [e['phase'] for e in capture.deadline_events] == ['post_dispatch_outcome']
    integrity = capture.integrity()
    assert (integrity['receipt_integrity'], integrity['queue_may_continue'], integrity['deadline_reached'],
            integrity['deadline_class']) == ('incomplete', False, True, 'EpisodeDeadline')
    assert integrity['reasons'] == ['write(s) interrupted by the episode deadline: 1',
                                    'the receipt set has holes or invalid records']
    called = []
    with pytest.raises(EpisodeDeadline) as again:                 # latched: no further query is dispatched
        capture.dispatch(logical_call_id=2, query_attempt=1, call=lambda: called.append(1))
    assert again.value is alarm[0] and called == []


def test_a_deadline_during_the_pre_dispatch_write_latches_and_nothing_is_sent(tmp_path):
    first = EpisodeDeadline('deadline during the raw write')
    _, capture = make(tmp_path, write_once=raising_writer('.request.raw', lambda: first))
    sent = []

    def call():
        try:
            capture.forward(body=PLAIN_REQUEST, wire=wire(), replayable=True, stream_bytes=PLAIN_REQUEST,
                            send=lambda: sent.append(1))
        except CT.PreDispatchRefusal:
            pass                                                   # e.g. an SDK layer that would retry
        capture.forward(body=PLAIN_REQUEST, wire=wire(), replayable=True, stream_bytes=PLAIN_REQUEST,
                        send=lambda: sent.append(2))
    with pytest.raises(EpisodeDeadline) as info:
        capture.dispatch(logical_call_id=1, query_attempt=1, call=call)
    assert info.value is first and sent == []
    assert [(r['reason_code'], r['classification'], r['infrastructure_stop'], r['attempt_key']) for r in
            capture.refusals] == [('episode_deadline_during_write', 'deadline', False, 'call001_attempt01'),
                                  ('episode_deadline_latched', 'deadline', False, None)]
    assert capture.refusals[0]['detail'] == 'EpisodeDeadline interrupted the durable pre-dispatch write'
    assert capture.interrupted_writes == [dict(attempt_key='call001_attempt01', error_class='EpisodeDeadline',
                                               phase='pre_dispatch_write')]
    assert capture.integrity()['reasons'] == ['write(s) interrupted by the episode deadline: 1']
    assert capture.integrity()['queue_may_continue'] is False and capture.budget.used == 0


def test_a_deadline_during_the_binding_check_is_the_deadline_not_a_bypass_claim(tmp_path):
    deadline = EpisodeDeadline('deadline during the binding check')
    _, capture = make(tmp_path)

    def check():
        raise deadline
    capture.binding_check = check
    with pytest.raises(EpisodeDeadline) as info:
        capture.dispatch(logical_call_id=1, query_attempt=1, call=forward_call(capture, PLAIN_REQUEST, []))
    assert info.value is deadline and capture.stopped is None
    assert [r['reason_code'] for r in capture.refusals] == []
    assert [e['phase'] for e in capture.deadline_events] == ['session_binding_check']
    # any other failure of the check is "unverifiable", never a claim that a send bypassed the receipts
    _, other = make(tmp_path / 'other')
    other.binding_check = lambda: (_ for _ in ()).throw(RuntimeError('cache unreadable'))
    with pytest.raises(CT.InfrastructureStop) as stop:
        other.dispatch(logical_call_id=1, query_attempt=1, call=forward_call(other, PLAIN_REQUEST, []))
    assert (stop.value.refusal['reason_code'], stop.value.refusal['detail']) == (
        'client_session_binding_unverifiable', 'binding check raised RuntimeError')


def test_a_deadline_outside_a_dispatch_scope_propagates_at_once(tmp_path):
    deadline = EpisodeDeadline('deadline during a refusal record')
    _, capture = make(tmp_path, write_once=raising_writer('.refusal.json', lambda: deadline))
    with pytest.raises(EpisodeDeadline) as info:
        capture.refuse_infrastructure('install_preflight_failed', detail='x')
    assert info.value is deadline and capture.deadline_reached is True
    assert (capture.refusals[0]['record_written'], capture.refusals[0]['record_error']) == (
        False, 'interrupted by the episode deadline (EpisodeDeadline)')


def test_query_identity_is_sequenced_and_no_pair_is_reused(tmp_path):
    cases = [
        ([(2, 1)], 'query (call 2, attempt 1) after none; the next dispatch must be one of call 1 attempt 1'),
        ([(1, 1), (1, 1)], 'query (call 1, attempt 1) after call 1 attempt 1; the next dispatch must be one of '
                           'call 2 attempt 1, call 1 attempt 2'),
        ([(1, 1), (2, 1), (1, 2)], 'query (call 1, attempt 2) after call 2 attempt 1; the next dispatch must be one '
                                   'of call 3 attempt 1, call 2 attempt 2'),
        ([(1, 1), (3, 1)], 'query (call 3, attempt 1) after call 1 attempt 1; the next dispatch must be one of '
                           'call 2 attempt 1, call 1 attempt 2'),
        ([(1, 1), (1, 2), (1, 2)], 'query (call 1, attempt 2) after call 1 attempt 2; the next dispatch must be one '
                                   'of call 2 attempt 1'),
        ([(1, 1), (1, 2), (1, 3)], 'query attempt 3 outside 1..2'),
    ]
    for number, (pairs, detail) in enumerate(cases):
        _, capture = make(tmp_path / str(number))
        sent = []
        for logical, attempt in pairs[:-1]:
            capture.dispatch(logical_call_id=logical, query_attempt=attempt,
                             call=forward_call(capture, PLAIN_REQUEST, sent))
        called = []
        with pytest.raises(CT.InfrastructureStop) as info:
            capture.dispatch(logical_call_id=pairs[-1][0], query_attempt=pairs[-1][1], call=lambda: called.append(1))
        assert (info.value.refusal['reason_code'], info.value.refusal['detail'], called) == (
            'invalid_query_identity', detail, []), number
        assert len(sent) == len(pairs) - 1 and capture.budget.used == len(pairs) - 1


def test_the_frozen_horizon_attempts_and_single_send_cannot_be_enlarged(tmp_path):
    store, _ = make(tmp_path / 'a')
    for kwargs in (dict(horizon=25), dict(attempts_per_call=3), dict(sends_per_query_attempt=2),
                   dict(sends_per_query_attempt=0)):
        with pytest.raises(ValueError):
            CT.CueTransportCapture(store, budget=CT.RequestBudget(used=0), host_reserve_bytes=RESERVE,
                                   free_space_probe=lambda _p: PLENTY, clock=lambda: EPOCH, **kwargs)
    store, capture = make(tmp_path / 'b', sends=2)
    assert (capture.start_preflight['accounting_fixture'], capture.integrity()['accounting_fixture']) == (True, True)
    capture.dispatch(logical_call_id=1, query_attempt=1, call=forward_call(capture, PLAIN_REQUEST, []))
    assert read_json(store.record_path('call001_attempt01'))['send']['accounting_fixture'] is True


def fake_litellm(**overrides):
    cache = types.SimpleNamespace(cache_dict=overrides.pop('cache_dict', {}))
    values = dict(num_retries=None, num_retries_per_request=None, drop_params=False, network_mock=False,
                  route_all_chat_openai_to_responses=False, client_session=None, in_memory_llm_clients_cache=cache)
    values.update(overrides)
    return types.SimpleNamespace(**values)


def test_the_install_preflight_names_every_hidden_send_path(monkeypatch):
    class FakeClient:
        pass

    def problems(lite, **kw):
        return CT.litellm_preflight_problems(lite, client_types=(FakeClient,), **kw)
    assert problems(fake_litellm(), environ={}, proxies={}) == []
    # entries that are not openai clients (litellm caches async handlers of other providers at import) are no problem
    assert problems(fake_litellm(cache_dict={'async_httpx_clientbedrock': object()}), environ={}, proxies={}) == []
    for overrides, expected in (
            (dict(num_retries=3), 'litellm.num_retries is 3; a global value overrides the frozen per-call '
                                  'num_retries=0'),
            (dict(num_retries_per_request=1), 'litellm.num_retries_per_request is set'),
            (dict(drop_params=True), 'litellm.drop_params is not False; it enables the hidden 422 second pass'),
            (dict(drop_params=None), 'litellm.drop_params is not False; it enables the hidden 422 second pass'),
            (dict(network_mock=True), 'litellm.network_mock is set'),
            (dict(route_all_chat_openai_to_responses=True), 'litellm routes chat completions to the Responses bridge'),
            (dict(client_session=object()), 'a litellm client_session is already installed'),
            (dict(cache_dict={'k': FakeClient(), 'j': FakeClient(), 'x': 1}),
             'litellm client cache holds 2 openai clients at install; a cached client keeps its old http client'),
            (dict(cache_dict={'k': FakeClient()}),
             'litellm client cache holds 1 openai client at install; a cached client keeps its old http client'),
            (dict(in_memory_llm_clients_cache=None), 'litellm client cache is not inspectable')):
        assert problems(fake_litellm(**overrides), environ={}, proxies={}) == [expected]
    for name in ('EXPERIMENTAL_OPENAI_BASE_LLM_HTTP_HANDLER', 'LITELLM_ROUTE_ALL_CHAT_OPENAI_TO_RESPONSES',
                 'LITELLM_DROP_PARAMS', 'LITELLM_NUM_RETRIES'):
        assert problems(fake_litellm(), environ={name: '1'}, proxies={}) == ['environment variable %s is set' % name]
    assert problems(fake_litellm(), environ={}, proxies={'http': 'http://p:3128', 'no': 'x'}) == [
        "environment/system proxies ['http'] would route the frozen default client differently"]
    # the default proxy source is urllib's own discovery, which reads the environment first
    monkeypatch.setenv('https_proxy', 'http://127.0.0.1:9')
    assert problems(fake_litellm(), environ={}) == [
        "environment/system proxies ['https'] would route the frozen default client differently"]


def test_session_binding_names_a_cached_client_that_does_not_wrap_the_session():
    class FakeClient:
        def __init__(self, inner):
            self._client = inner
    session, other = object(), object()
    lite = fake_litellm(client_session=session, cache_dict={'a': FakeClient(session), 'b': FakeClient(other),
                                                            'c': 'not a client'})
    assert CT.session_binding_violations(lite, session, client_types=(FakeClient,)) == [
        'a cached FakeClient does not wrap the capture session']
    lite.client_session = other
    assert CT.session_binding_violations(lite, session, client_types=(FakeClient,)) == [
        'litellm.client_session is not the capture session', 'a cached FakeClient does not wrap the capture session']


def oversized_refusals(capture, n):
    """n refusal records without any send: one oversized body (latches), then n-1 latched attempts."""
    with pytest.raises(CT.InfrastructureStop):
        capture.dispatch(logical_call_id=1, query_attempt=1, call=forward_call(capture, b'x' * 8388609, []))
    for _ in range(n - 1):
        with pytest.raises(CT.PreDispatchRefusal):
            forward_call(capture, PLAIN_REQUEST, [])()


def test_refusal_records_are_sealed_consecutive_and_checked(tmp_path):
    store, capture = make(tmp_path)
    oversized_refusals(capture, 3)
    published = tmp_path / 'root/published'
    assert sorted(p.name for p in published.iterdir()) == ['refusal001.refusal.json', 'refusal002.refusal.json',
                                                           'refusal003.refusal.json']
    state = store.completeness()
    assert (state['complete'], state['invalid_refusal_records'], state['refusal_ordinals_missing']) == (True, [], [])
    assert [r['reason_code'] for r in state['pre_dispatch_refusals']] == [
        'body_over_cap', 'infrastructure_stop_latched', 'infrastructure_stop_latched']
    original = (published / 'refusal002.refusal.json').read_bytes()
    # an edited record fails its own seal
    (published / 'refusal002.refusal.json').write_bytes(original.replace(b'"infrastructure_stop_latched"',
                                                                         b'"infrastructure_stop_lAtched"'))
    state = store.completeness()
    assert (state['complete'], state['invalid_refusal_records']) == (False, [dict(
        file='refusal002.refusal.json', error='ReceiptError: refusal record digest mismatch')])
    # a deleted record is a gap, never silence
    (published / 'refusal002.refusal.json').unlink()
    state = store.completeness()
    assert (state['complete'], state['refusal_ordinals_missing'], state['invalid_refusal_records']) == (
        False, [2], [dict(file=None, error='refusal ordinal gap: record(s) [2] missing')])
    # a record under another ordinal's filename is refused
    (published / 'refusal002.refusal.json').write_bytes((published / 'refusal003.refusal.json').read_bytes())
    state = store.completeness()
    assert state['invalid_refusal_records'] == [dict(
        file='refusal002.refusal.json', error='ReceiptError: refusal record ordinal does not match its filename')]


def test_an_unwritten_refusal_record_makes_integrity_incomplete(tmp_path):
    _, capture = make(tmp_path, write_once=failing('.refusal.json'))
    oversized_refusals(capture, 1)
    assert (capture.refusals[0]['record_written'], capture.refusals[0]['record_error']) == (False, 'OSError')
    integrity = capture.integrity()
    assert (integrity['receipt_integrity'], integrity['reasons'], integrity['store']['complete']) == (
        'incomplete', ['refusal record(s) not durably written: [1]'], True)


def test_a_valid_receipt_file_over_128_kib_makes_the_set_incomplete(tmp_path):
    store, capture = make(tmp_path)
    raw = b'{"messages":[{"role":"user","content":"' + b'q' * 60000 + b'"}]}'
    capture.dispatch(logical_call_id=1, query_attempt=1, call=forward_call(capture, raw, []))
    assert store.completeness()['complete'] is True
    path = store.record_path('call001_attempt01')
    record = read_json(path)
    path.write_text(json.dumps(record, indent=400))       # same content and seal, larger than the cap on disk
    assert RR.verify_published_projection(path)['status'] == 'published_projection_verified'
    state = store.completeness()
    assert (state['records_over_public_cap'], state['invalid_records'], state['complete']) == (
        ['call001_attempt01.request.json'], [], False)


def test_an_outcome_record_over_128_kib_is_refused_and_not_written(tmp_path):
    store, _ = make(tmp_path)
    store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=PLAIN_REQUEST)
    with pytest.raises(CT._ReceiptOverCap):
        store.record_outcome(logical_call_id=1, physical_attempt_id=1, ok=True, send={'pad': 'y' * 140000})
    assert not store.outcome_path('call001_attempt01').exists()


def test_a_refusal_record_over_128_kib_is_refused(tmp_path):
    store, _ = make(tmp_path)
    with pytest.raises(CT._ReceiptOverCap):
        store.record_refusal(dict(refusal_ordinal=1, reason_code='x', pad='z' * 140000))
    assert not store.refusal_path(1).exists()


def test_every_durable_write_is_synced_file_then_directory_before_the_send(tmp_path, monkeypatch):
    order = []
    real = CT._durable_sync
    monkeypatch.setattr(CT, '_durable_sync', lambda path: (order.append(Path(path).name), real(path))[1])
    _, capture = make(tmp_path)
    capture.dispatch(logical_call_id=1, query_attempt=1, call=lambda: capture.forward(
        body=PLAIN_REQUEST, wire=wire(), replayable=True, stream_bytes=PLAIN_REQUEST,
        send=lambda: (order.append('SEND'), FakeResponse(200, OK_JSON))[1]))
    assert order == ['call001_attempt01.request.raw', 'receipts', 'call001_attempt01.request.json', 'published',
                     'SEND', 'call001_attempt01.outcome.json', 'published']


def test_a_failed_directory_sync_after_the_public_receipt_is_a_refusal_linked_to_that_receipt(tmp_path, monkeypatch):
    real, failed = CT._durable_sync, []

    def sync(path):
        if Path(path).name == 'published' and not failed:
            failed.append(1)
            raise OSError(5, 'simulated: directory fsync failed')
        return real(path)
    monkeypatch.setattr(CT, '_durable_sync', sync)
    store, capture = make(tmp_path)
    sent = []
    with pytest.raises(CT.InfrastructureStop) as info:
        capture.dispatch(logical_call_id=1, query_attempt=1, call=forward_call(capture, PLAIN_REQUEST, sent))
    refusal = info.value.refusal
    assert (refusal['reason_code'], refusal['attempt_key'], refusal['receipt_files_present'], sent) == (
        'durable_write_failed', 'call001_attempt01',
        ['call001_attempt01.request.json', 'call001_attempt01.request.raw'], [])
    state = store.completeness()
    assert (state['receipts_refused_before_dispatch'], state['dispatched_attempt_keys'],
            state['published_record_without_outcome'], state['complete']) == (
        ['call001_attempt01'], [], ['call001_attempt01'], False)


def test_the_listed_transformations_are_reduced_before_the_preview_is_dropped(tmp_path):
    store, _ = make(tmp_path)
    messages = b','.join(b'{"role":"user","content":"see /Users/example-worker/x%02d ' % i + b'\\"' * 700 +
                         b'a' * 300 + b'"}' for i in range(40))
    rec = store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=b'{"messages":[' + messages + b']}')
    san = rec['sanitization']
    assert (rec['payload_publication']['mode'], san['transformations_total'], san['transformations_listed'],
            san['transformations_omitted'], san['transformation_listing_limit']) == ('head_tail', 40, 0, 40, 0)
    assert san['transformations_by_type'] == {'home_path_prefix_masked': {'entries': 40, 'occurrences': 40}}
    assert store.record_path('call001_attempt01').stat().st_size <= 131072


def test_a_receipt_of_exactly_128_kib_keeps_its_preview(tmp_path):
    store, _ = make(tmp_path)
    content = b'\\"' * 16384 + b'a' * 40003 + b'\\"' * 13593
    rec = store.record_request(logical_call_id=1, physical_attempt_id=1,
                               serialized=b'{"messages":[{"role":"user","content":"' + content + b'"}]}')
    assert rec['payload_publication']['mode'] == 'head_tail'
    assert store.record_path('call001_attempt01').stat().st_size == 131072


def test_the_start_preflight_refuses_an_unmeasurable_disk_and_probes_both_directories(tmp_path):
    probed = []

    def failing_probe(path):
        probed.append(Path(path).name)
        raise OSError('statfs failed')
    with pytest.raises(CT.StartPreflightRefused) as info:
        make(tmp_path / 'fail', free=failing_probe)
    record = info.value.refusal['free_space']
    assert (record['probe_error'], record['observed_free_bytes'], record['passed']) == (
        'OSError (observed_free_bytes)', None, False)
    probed.clear()

    def public_short(path):
        probed.append(Path(path).name)
        return PLENTY if Path(path).name == 'receipts' else START_BOUNDARY - 1
    with pytest.raises(CT.StartPreflightRefused) as info:
        make(tmp_path / 'public', free=public_short)
    record = info.value.refusal['free_space']
    assert probed[:2] == ['receipts', 'published']
    assert (record['observed_free_bytes'], record['observed_public_free_bytes'], record['passed']) == (
        PLENTY, 27917287423, False)


def test_a_refusal_detail_is_sanitized_before_it_is_recorded(tmp_path):
    _, capture = make(tmp_path)
    stop = capture.refuse_infrastructure('install_preflight_failed',
                                         detail='/Users/example-worker/repo api_key=' + SECRET)
    assert stop.refusal['detail'] == '<HOME>/repo api_key=<WITHHELD>'
    data = (tmp_path / 'root/published/refusal001.refusal.json').read_bytes()
    assert SECRET.encode() not in data and b'/Users/example-worker' not in data


# =================================================================== the pinned SDK path (subprocess)

@pytest.fixture(scope='module')
def sdk(tmp_path_factory):
    if not MSWEA_PY.exists():
        pytest.skip('pinned mini-swe-agent venv work/venvs/minisweagent_04d809c is absent; the SDK-path fixtures '
                    'need its litellm 1.102.0 / openai 2.54.0 / httpx 0.28.1')
    out = tmp_path_factory.mktemp('cue_transport_sdk')
    env = {k: v for k, v in os.environ.items()
           if not k.lower().endswith('_proxy') and not k.startswith(('LITELLM_', 'EXPERIMENTAL_OPENAI'))}
    proc = subprocess.run([str(MSWEA_PY), str(SDK_FIXTURE), str(out)], capture_output=True, text=True,
                          timeout=600, cwd=str(out), env=env)
    assert proc.returncode == 0, proc.stderr[-4000:]
    return out, json.loads((out / 'summary.json').read_text())


def scenario(sdk, name):
    out, summary = sdk
    return out / name, summary['scenarios'][name]


def terminal(d, n):
    return (d / 'terminal' / ('%03d.body' % n)).read_bytes()


def private_raw(d, key):
    return (d / 'root/work/receipts' / (key + '.request.raw')).read_bytes()


def public(d, name):
    return read_json(d / 'root/published' / name)


def test_sdk_the_fixture_ran_on_the_pinned_stack_with_no_network(sdk):
    _, summary = sdk
    assert summary['versions'] == {'litellm': '1.102.0', 'openai': '2.54.0', 'httpx': '0.28.1', 'tenacity': '9.1.4',
                                   'mini-swe-agent': '2.4.6'}
    assert summary['network_attempts'] == []
    assert summary['frozen_call_kwargs'] == {'drop_params': True, 'api_base': 'http://127.0.0.1:8291/v1',
                                             'api_key': 'none', 'temperature': 0.0, 'max_tokens': 1536,
                                             'timeout': 900, 'num_retries': 0}


def test_sdk_baseline_receiver_bytes_equal_the_retained_private_bytes_and_the_literal(sdk):
    d, s = scenario(sdk, 'baseline_200')
    assert terminal(d, 1) == private_raw(d, 'call001_attempt01') == BASELINE_BODY
    assert [(t['bytes'], t['content_length'], t['retry_count'], t['url']) for t in s['terminal']] == [
        (468, '468', '0', URL)]
    receipt = public(d, 'call001_attempt01.request.json')
    assert (receipt['raw_request_sha256'], receipt['raw_request_bytes']) == (BASELINE_SHA256, BASELINE_BYTES)
    assert (receipt['payload_publication']['mode'], receipt['payload_publication']['sanitized_payload_sha256']) == (
        'whole', BASELINE_CANONICAL_SHA256)
    outcome = public(d, 'call001_attempt01.outcome.json')
    usage = outcome['server_reported_usage']
    assert (outcome['outcome'], outcome['http_status'], outcome['finish_reason'], usage['prompt_tokens'],
            usage['completion_tokens'], usage['total_tokens']) == ('ok', 200, 'stop', 123, 7, 130)
    assert s['outcomes'] == [dict(ok=True, content='THOUGHT: probe\n\n```mswea_bash_command\necho probe\n```',
                                  actions=[{'command': 'echo probe'}],
                                  litellm_usage=dict(prompt_tokens=123, completion_tokens=7, total_tokens=130))]
    assert s['openai_clients'] == [dict(max_retries=0, wraps_capture_session=True)]
    assert s['install'] == dict(hook='litellm.client_session', follow_redirects=False, inner_transport='MockTransport',
                                sends_per_query_attempt=1, preflight_problems=[], litellm_num_retries=None,
                                litellm_drop_params=False, environment_proxies=[], client_cache_entries_at_install=0,
                                client_cache_openai_clients_at_install=[],
                                client_cache_other_entry_types_at_install=[])
    assert (s['integrity']['receipt_integrity'], s['store_complete'], s['binding_violations']) == ('complete', True, [])
    # the authorization header reached the sender but was persisted nowhere
    assert s['terminal'][0]['has_authorization'] is True
    for path in (d / 'root').rglob('*'):
        if path.is_file():
            assert b'Bearer' not in path.read_bytes(), path.name


def test_sdk_cue_arm_differs_from_baseline_only_by_the_one_inserted_cue_message(sdk):
    d, s = scenario(sdk, 'cue_200')
    body = terminal(d, 1)
    assert body == private_raw(d, 'call001_attempt01')
    insert_at = BASELINE_BODY.index(b'}],"model"') + 1
    assert body == BASELINE_BODY[:insert_at] + CUE_INSERTION + BASELINE_BODY[insert_at:]
    assert len(body) == CUE_BODY_BYTES
    receipt = public(d, 'call001_attempt01.request.json')
    assert receipt['raw_request_sha256'] == CUE_BODY_SHA256
    assert hashlib.sha256(CUE_TEXT.encode()).hexdigest() == CUE_SHA256        # the cue literal is the lead's cue


def test_sdk_a_retried_call_gets_one_receipt_per_physical_send(sdk):
    d, s = scenario(sdk, 'retry_500_then_200')
    assert terminal(d, 1) == terminal(d, 2) == private_raw(d, 'call001_attempt01') == \
        private_raw(d, 'call001_attempt02') == BASELINE_BODY
    assert [(a['logical_call_id'], a['query_attempt_id'], a['attempt_keys'], a['http_statuses'], a['call_outcome'],
             a['exception_class']) for a in s['attempts']] == [
        (1, 1, ['call001_attempt01'], [500], 'raised', 'InternalServerError'),
        (1, 2, ['call001_attempt02'], [200], 'returned', None)]
    first, second = public(d, 'call001_attempt01.outcome.json'), public(d, 'call001_attempt02.outcome.json')
    assert (first['outcome'], first['error_class'], first['http_status']) == ('error', 'InternalServerError', 500)
    assert (second['outcome'], second['http_status'], second['send']['cohort_request_ordinal']) == ('ok', 200, 2)
    assert s['integrity']['budget'] == dict(limit=576, used=2) and s['outcomes'][0]['ok'] is True


def test_sdk_a_context_rejection_is_one_send_one_receipt_and_no_retry(sdk):
    d, s = scenario(sdk, 'context_400')
    assert terminal(d, 1) == private_raw(d, 'call001_attempt01') == BASELINE_BODY
    assert len(s['terminal']) == 1 and len(s['attempts']) == 1
    assert (s['outcomes'][0]['exception'], s['outcomes'][0]['status_code']) == (
        'litellm.exceptions.ContextWindowExceededError', 400)
    outcome = public(d, 'call001_attempt01.outcome.json')
    assert (outcome['outcome'], outcome['error_class'], outcome['http_status'],
            outcome['server_reported_usage']['usage_known']) == ('error', 'ContextWindowExceededError', 400, False)
    assert 'request (16610 tokens) exceeds the available context size (16384 tokens)' in outcome['error_detail']


def test_sdk_an_oversized_body_is_refused_before_dispatch_with_zero_sends_and_the_stop_latches(sdk):
    d, s = scenario(sdk, 'oversized_body')
    assert s['terminal'] == [] and s['private_files'] == {} and s['sends'] == []
    assert [(r['reason_code'], r['infrastructure_stop'], r['body_bytes'], r['body_sha256'], r['physical_request'])
            for r in s['refusals']] == [('body_over_cap', True, OVERSIZED_BYTES, OVERSIZED_SHA256, False)]
    assert [(o['exception'], o['refusal_reason']) for o in s['outcomes']] == [
        ('cue_transport.InfrastructureStop', 'body_over_cap'), ('cue_transport.InfrastructureStop', 'body_over_cap')]
    assert len(s['attempts']) == 1                             # no mini-swe-agent retry, no later dispatch
    record = public(d, 'refusal001.refusal.json')
    assert (record['refusal']['body_bytes'], record['refusal']['dispatched_to_terminal']) == (OVERSIZED_BYTES, False)


def test_sdk_a_failed_durable_write_and_low_free_space_refuse_with_zero_sends(sdk):
    for name, code in (('durable_write_failed', 'durable_write_failed'),
                       ('low_free_space', 'insufficient_free_space'),
                       ('budget_exhausted', 'cohort_request_budget_exhausted')):
        d, s = scenario(sdk, name)
        assert s['terminal'] == [] and s['sends'] == [] and s['private_files'] == {}, name
        assert [(r['reason_code'], r['body_sha256'], r['body_bytes']) for r in s['refusals']] == [
            (code, BASELINE_SHA256, BASELINE_BYTES)], name
        assert s['outcomes'][0]['exception'] == 'cue_transport.InfrastructureStop'
        assert s['integrity']['queue_may_continue'] is False and len(s['attempts']) == 1
    _, low = scenario(sdk, 'low_free_space')
    assert low['refusals'][0]['free_space']['checks'][0]['observed_free_bytes'] == 21474837480


def test_sdk_a_bookkeeping_failure_preserves_the_original_success_and_exception(sdk):
    d, s = scenario(sdk, 'bookkeeping_failure_success')
    assert s['outcomes'][0]['content'] == 'THOUGHT: probe\n\n```mswea_bash_command\necho probe\n```'
    assert terminal(d, 1) == private_raw(d, 'call001_attempt01') == BASELINE_BODY and len(s['terminal']) == 1
    assert s['bookkeeping_failures'] == [dict(attempt_key='call001_attempt01', phase='post_dispatch_outcome',
                                              error_class='OSError', secondary_log_written=True)]
    assert (s['integrity']['receipt_integrity'], s['store_holes']['published_record_without_outcome']) == (
        'incomplete', ['call001_attempt01'])
    d, s = scenario(sdk, 'bookkeeping_failure_error')
    assert s['outcomes'][0]['exception'] == 'litellm.exceptions.ContextWindowExceededError'
    assert len(s['terminal']) == 1 and s['integrity']['receipt_integrity'] == 'incomplete'


def test_sdk_usage_the_server_omitted_stays_unknown_although_litellm_reports_zeros(sdk):
    d, s = scenario(sdk, 'usage_omitted_by_server')
    assert s['outcomes'][0]['litellm_usage'] == dict(prompt_tokens=0, completion_tokens=0, total_tokens=0)
    usage = public(d, 'call001_attempt01.outcome.json')['server_reported_usage']
    assert (usage['prompt_tokens'], usage['completion_tokens'], usage['total_tokens'], usage['usage_known']) == (
        None, None, None, False)


def test_sdk_a_multibyte_body_over_64_kib_is_retained_exactly_and_published_as_bounded_excerpts(sdk):
    d, s = scenario(sdk, 'multibyte_over_64k')
    assert terminal(d, 1) == private_raw(d, 'call001_attempt01') == MULTIBYTE_BODY
    receipt = public(d, 'call001_attempt01.request.json')
    pub = receipt['payload_publication']
    assert (receipt['raw_request_sha256'], receipt['raw_request_bytes']) == (MULTIBYTE_BODY_SHA256, 90130)
    assert (pub['mode'], pub['sanitized_payload_sha256'], pub['sanitized_payload_bytes']) == (
        'head_tail', MULTIBYTE_CANONICAL_SHA256, 90130)
    # 43 ASCII bytes then 3-byte characters: 43 + 3*10908 = 32767; 43 + 3*19107 = 57364
    assert (pub['head']['offset_end'], pub['head']['sha256'], pub['tail']['offset_start'], pub['tail']['bytes'],
            pub['tail']['sha256']) == (32767, MULTIBYTE_HEAD_SHA256, 57364, 32766, MULTIBYTE_TAIL_SHA256)
    assert s['public_files']['call001_attempt01.request.json'] <= 131072


def test_sdk_litellm_s_hidden_second_pass_and_sdk_retries_are_refused_after_one_send(sdk):
    for name in ('hidden_second_pass_suppressed', 'sdk_retry_one_send'):
        d, s = scenario(sdk, name)
        assert len(s['terminal']) == 1 and terminal(d, 1) == private_raw(d, 'call001_attempt01') == BASELINE_BODY
        assert [(r['reason_code'], r['infrastructure_stop'], r['body_sha256']) for r in s['refusals']] == [
            ('query_attempt_send_limit', False, BASELINE_SHA256)], name
        assert s['outcomes'][0]['exception'] == 'litellm.exceptions.InternalServerError'
    _, hidden = scenario(sdk, 'hidden_second_pass_suppressed')
    assert [t['http_status'] for t in hidden['sends']] == [400]           # the status the server actually sent
    assert hidden['openai_clients'] == [dict(max_retries=0, wraps_capture_session=True),
                                        dict(max_retries=2, wraps_capture_session=True)]


def test_sdk_when_two_sends_are_allowed_each_extra_send_has_its_own_receipt_and_budget_unit(sdk):
    d, s = scenario(sdk, 'sdk_retry_two_sends_allowed')
    assert [t['retry_count'] for t in s['terminal']] == ['0', '1']
    assert terminal(d, 1) == terminal(d, 2) == private_raw(d, 'call001_attempt01') == \
        private_raw(d, 'call001_attempt02') == BASELINE_BODY
    assert [(t['attempt_key'], t['cohort_request_ordinal'], t['http_status']) for t in s['sends']] == [
        ('call001_attempt01', 1, 500), ('call001_attempt02', 2, 500)]
    first = public(d, 'call001_attempt01.outcome.json')
    assert (first['error_class'], first['send']['superseded_by_later_send']) == ('SupersededBySameAttemptResend', True)
    assert [r['reason_code'] for r in s['refusals']] == ['query_attempt_send_limit']


def test_sdk_a_redirect_is_surfaced_not_followed(sdk):
    d, s = scenario(sdk, 'redirect_not_followed')
    assert len(s['terminal']) == 1 and [t['http_status'] for t in s['sends']] == [307]
    assert (s['outcomes'][0]['exception'], s['outcomes'][0]['status_code']) == ('litellm.exceptions.APIError', 307)


def test_sdk_the_installer_refuses_a_pre_cached_client_or_a_hidden_send_global(sdk):
    _, summary = sdk
    assert [(r['label'], r['outcome']['refusal_reason'], r['session_installed'], r['detail'])
            for r in summary['install_preflight']] == [
        ('cached client present', 'install_preflight_failed', False,
         'litellm client cache holds 1 openai client at install; a cached client keeps its old http client'),
        ('global num_retries', 'install_preflight_failed', False,
         'litellm.num_retries is 3; a global value overrides the frozen per-call num_retries=0'),
        ('global drop_params', 'install_preflight_failed', False,
         'litellm.drop_params is not False; it enables the hidden 422 second pass')]


def test_sdk_a_send_that_bypasses_the_capture_session_stops_the_episode(sdk):
    _, summary = sdk
    assert summary['bypassed_session'] == dict(
        outcome=dict(ok=False, exception='cue_transport.InfrastructureStop', chain=[], status_code=None,
                     refusal_reason='client_session_bypassed', result_attached=True),
        captured_terminal=0, other_terminal=1, stop_reason='client_session_bypassed', sends=0)


def test_sdk_a_streaming_body_is_refused_unread_before_the_terminal(sdk):
    _, summary = sdk
    assert summary['non_replayable'] == dict(
        outcome=dict(ok=False, exception='cue_transport.InfrastructureStop', chain=['cue_transport.PreDispatchRefusal'],
                     status_code=None, refusal_reason='non_replayable_body'),
        terminal=0, generator_consumed=False, refusals=['non_replayable_body'], private_files={})


def test_sdk_a_suppressed_hidden_resend_keeps_the_server_s_own_400_and_is_reported_as_a_parity_deviation(sdk):
    d, s = scenario(sdk, 'hidden_second_pass_suppressed')
    outcome = public(d, 'call001_attempt01.outcome.json')
    assert (outcome['error_class'], outcome['http_status'], outcome['send']['server_http_status']) == (
        'InternalServerError', 400, 400)
    assert outcome['send']['server_error'] == {
        'type': 'invalid_request_error', 'code': 400,
        'message': 'Conversation roles must alternate user/assistant/user/assistant/...'}
    assert outcome['send']['caller_exception_origin'] == (
        "hidden_resend_suppressed: the caller's exception follows the refusal of a further send in this query "
        "attempt (refusal [1]); the server's own response to this send is server_http_status")
    assert s['integrity']['frozen_path_parity'] == dict(
        state='deviated', suppressed_hidden_resends=[dict(refusal_ordinal=1, logical_call_id=1, query_attempt_id=1)],
        redirects_surfaced_not_followed=[],
        note='a deviation is reported for lead review; it is not an infrastructure stop by itself')
    _, redirect = scenario(sdk, 'redirect_not_followed')
    assert redirect['integrity']['frozen_path_parity']['redirects_surfaced_not_followed'] == [
        dict(attempt_key='call001_attempt01', http_status=307)]
    _, baseline = scenario(sdk, 'baseline_200')
    assert baseline['integrity']['frozen_path_parity']['state'] == 'unchanged'


def test_sdk_a_cached_openai_client_outside_the_session_is_found_after_the_call(sdk):
    _, summary = sdk
    assert summary['cached_client_bypass'] == dict(
        outcome=dict(ok=False, exception='cue_transport.InfrastructureStop', chain=[], status_code=None,
                     refusal_reason='client_session_bypassed', result_attached=True),
        captured_terminal=1, other_terminal=0, stop_reason='client_session_bypassed',
        detail='a cached OpenAI does not wrap the capture session', sends=1)


def test_sdk_a_bytestream_subclass_is_refused_unread(sdk):
    _, summary = sdk
    assert summary['bytestream_subclass'] == dict(
        outcome=dict(ok=False, exception='cue_transport.InfrastructureStop', chain=['cue_transport.PreDispatchRefusal'],
                     status_code=None, refusal_reason='non_replayable_body'),
        terminal=0, refusals=['non_replayable_body'], private_files={})


def test_sdk_the_live_default_inner_transport_sends_what_litellm_s_frozen_default_client_sends(sdk):
    _, summary = sdk
    parity = summary['default_inner_parity']
    assert (parity['sends'], parity['inner_transport'], parity['default']['transport'],
            parity['captured']['transport']) == (2, 'HTTPTransport', 'HTTPTransport', 'HTTPTransport')
    assert parity['captured'] == parity['default']                  # body, every header, timeout extension, url
    assert parity['captured']['body'].encode('utf-8') == BASELINE_BODY == parity['private_body'].encode('utf-8')
    assert parity['captured']['timeout'] == {'connect': 900.0, 'read': 900.0, 'write': 900.0, 'pool': 900.0}
    assert parity['captured']['url'] == URL
    assert ['content-length', '468'] in parity['captured']['headers']
