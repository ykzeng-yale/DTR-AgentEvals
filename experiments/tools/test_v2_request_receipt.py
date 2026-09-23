"""Deterministic fixtures for DTR-REQ-005 pre-dispatch request receipts (lead answer 5).

No model, server, container or network call. Every expected value below is written out BY HAND in literal
form: the raw digests were computed with `shasum -a 256` over the exact fixture bytes, independently of the
module under test, and the sanitized strings, counts, field paths, totals and published wordings are spelled
out rather than recomputed, so a bug in the module cannot be cancelled by the same bug here. Where a record's
own digest is checked, this file recomputes it with its OWN json.dumps(sort_keys=True) rather than calling the
module's canonicalisation, so a loss of canonical ordering cannot pass.
"""
import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_agent'))
import request_receipt as RR  # noqa: E402

# Exact fixture bytes. shasum -a 256:
#   87a8d7649bc6f40a9657f532ad14a4b3c038df4033aa2f303fb79ce083177a72  (267 bytes, home path + api_key)
#   95a92b44dff3ab76a5cb5bb46df2b126a5a3758548f6ef198292f66923fe2572  (121 bytes, nothing to sanitize)
HOME_REQUEST = (b'{"model": "qwen2.5-coder-7b-instruct-c03e6d3-q4_k_m", '
                b'"messages": [{"role": "user", "content": "Traceback: File '
                b'\\"/Users/example-worker/DTR-AgentEvals/.venv/lib/python3.11/json/decoder.py\\", line 355"}], '
                b'"temperature": 0.0, "max_tokens": 1536, "api_key": "none-7f3a"}')
HOME_REQUEST_SHA256 = '87a8d7649bc6f40a9657f532ad14a4b3c038df4033aa2f303fb79ce083177a72'
HOME_REQUEST_BYTES = 267
PLAIN_REQUEST = (b'{"model": "m", "messages": [{"role": "user", "content": "fix the failing test"}], '
                 b'"temperature": 0.0, "max_tokens": 1536}')
PLAIN_REQUEST_SHA256 = '95a92b44dff3ab76a5cb5bb46df2b126a5a3758548f6ef198292f66923fe2572'
PLAIN_REQUEST_BYTES = 121
# sha256 of the 13 canonical bytes {"a":2,"b":1}, computed with shasum, not with the module
CANONICAL_AB_SHA256 = 'd3626ac30a87e6f7a6428233b3c68299976865fa5508e4267c5415c76af7a772'

FAKE_HOME = '/Users/example-worker'          # a home-like absolute path; never this host's actual home
CLOCK_EPOCH = 1790150400.0                   # date -u -r 1790150400 -> 2026-09-23T08:00:00Z
CLOCK_UTC = '2026-09-23T08:00:00Z'
COHORT = 'cue-v1'
RUN_ID = 'psf__requests-1142__small__cue-v1__run'

IDENTITY = dict(
    model=dict(alias='qwen2.5-coder-7b-instruct-c03e6d3-q4_k_m', model_sha256='1' * 64),
    decoding=dict(temperature=0.0, max_tokens=1536),
    server=dict(endpoint='http://127.0.0.1:8291/v1', llama_cpp='4fea119de30f6a923992780f6fd5ccb0bee5d47d', n_ctx=16384),
    tokenizer=dict(source='served GGUF tokenizer of the pinned model file', counted_by='llama-server /tokenize'))
SECRET_IDENTITY = dict(
    model=dict(alias='qwen2.5-coder-7b-instruct-c03e6d3-q4_k_m', model_sha256='1' * 64,
               model_file=FAKE_HOME + '/DTR-AgentEvals/work/models/coder-7b-q4_k_m.gguf'),
    decoding=dict(temperature=0.0, max_tokens=1536),
    server=dict(endpoint='http://127.0.0.1:8291/v1', api_key='none-7f3a'),
    tokenizer=dict(source='served GGUF tokenizer of the pinned model file'))

# the private directory is INSIDE the declared repository root, under the git-ignored work/ tree
PRIVATE = 'work/req005/receipts'
PUBLIC = 'published/cue-v1'

# the exact published wording of the digest semantics, typed out by hand
DIGEST_SEMANTICS = {
    'raw_request_sha256':
        'sha256 over the exact serialized request bytes, which are retained privately under work/ and are not '
        'published in this record',
    'published_projection_sha256':
        'sha256 over this published sanitized projection only; sanitization changed the bytes, so this digest '
        'is a different byte sequence and must never be presented as the raw request digest',
    'raw_request_equality':
        'reported_unverified: a reader of the published projection cannot verify equality to the absent raw '
        'bytes, nor that the only transformations applied were the ones listed',
}
UNKNOWN_USAGE_NOTE = ('server-reported usage that the server did not report stays null; it is never coerced to '
                      '0, and a total is not derived from a partially unknown pair')


def make_store(tmp_path, identity=None, preflight=None, home=FAKE_HOME, private=PRIVATE, root=None):
    return RR.RequestReceiptStore(tmp_path / private, tmp_path / PUBLIC, cohort=COHORT, run_id=RUN_ID,
                                  identity=IDENTITY if identity is None else identity, preflight=preflight,
                                  home=home, clock=lambda: CLOCK_EPOCH,
                                  root=tmp_path if root is None else root)


def private_file(tmp_path, name, private=PRIVATE):
    return tmp_path / private / name


def public_file(tmp_path, name):
    return tmp_path / PUBLIC / name


def independent_digest(path):
    """The record's own digest, recomputed here with an independently written canonicalisation."""
    record = json.loads(Path(path).read_text())
    payload = {k: v for k, v in record.items() if k != 'published_projection_sha256'}
    canonical = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    return hashlib.sha256(canonical).hexdigest()


# ---------------------------------------------------------------- successful request

def test_successful_request_writes_private_raw_and_public_records_with_two_distinct_digests(tmp_path):
    store = make_store(tmp_path)
    record = store.record_request(
        logical_call_id=3, physical_attempt_id=1, serialized=PLAIN_REQUEST,
        preflight=RR.preflight_token_count(4211, 'llama-server /tokenize over the serialized prompt'))

    assert private_file(tmp_path, 'call003_attempt01.request.raw').read_bytes() == PLAIN_REQUEST
    published = public_file(tmp_path, 'call003_attempt01.request.json')

    assert record['request'] == 'DTR-REQ-005'
    assert record['cohort'] == 'cue-v1'
    assert record['run_id'] == 'psf__requests-1142__small__cue-v1__run'
    assert record['phase'] == 'pre_dispatch'
    assert record['dispatch_state'] == 'persisted_before_dispatch'
    assert record['recorded_utc'] == '2026-09-23T08:00:00Z'
    assert record['attempt_key'] == 'call003_attempt01'
    assert record['logical_call_id'] == 3
    assert record['physical_attempt_id'] == 1

    # the raw bytes stay private; the record points at them without publishing them
    assert record['raw_request_sha256'] == PLAIN_REQUEST_SHA256
    assert record['raw_request_bytes'] == 121
    assert record['raw_request_private_file'] == 'call003_attempt01.request.raw'
    assert record['raw_request_private_root'] == 'work/req005/receipts'
    assert record['raw_request_private_root_basis'] == 'relative to the declared repository root'
    assert record['raw_request_published'] is False
    assert PLAIN_REQUEST.decode() not in published.read_text()

    # two digests, distinct names, distinct values, with the reported-unverified marker, and the published
    # digest recomputed here rather than by the module
    assert record['published_projection_sha256'] == independent_digest(published)
    assert record['published_projection_sha256'] != record['raw_request_sha256']
    assert record['published_projection_sha256'] != PLAIN_REQUEST_SHA256
    assert record['raw_request_equality'] == 'reported_unverified'
    assert record['raw_bytes_independently_verified'] is False
    assert record['sanitization_transform_independently_verified'] is False
    assert record['digest_semantics'] == DIGEST_SEMANTICS
    assert RR.DIGEST_SEMANTICS == DIGEST_SEMANTICS

    # identity: all four recorded classes survive into the published projection
    assert record['identity']['model']['alias'] == 'qwen2.5-coder-7b-instruct-c03e6d3-q4_k_m'
    assert record['identity']['model']['model_sha256'] == '1' * 64
    assert record['identity']['decoding'] == dict(temperature=0.0, max_tokens=1536)
    assert record['identity']['server']['endpoint'] == 'http://127.0.0.1:8291/v1'
    assert record['identity']['server']['n_ctx'] == 16384
    assert record['identity']['tokenizer']['counted_by'] == 'llama-server /tokenize'

    assert record['payload_projection']['messages'] == [dict(role='user', content='fix the failing test')]
    assert record['payload_projection']['temperature'] == 0.0
    assert record['payload_projection_available'] is True
    assert record['payload_projection_status'] == 'sanitized projection of the serialized request payload'
    # the canonical projection is exactly these 111 bytes, counted by hand:
    # {"max_tokens":1536,"messages":[{"content":"fix the failing test","role":"user"}],"model":"m",
    #  "temperature":0.0}
    assert record['payload_projection_bytes'] == 111
    assert record['sanitization']['applied'] is False
    assert record['sanitization']['transformations'] == []
    assert record['sanitization']['home_prefix_masked'] is True
    assert record['server_reported_usage'] is None

    verdict = RR.verify_published_projection(published, expect_phase='pre_dispatch')
    assert verdict['status'] == 'published_projection_verified'
    assert verdict['raw_request_equality'] == 'reported_unverified'
    assert verdict['raw_bytes_independently_verified'] is False
    assert verdict['reported_raw_request_sha256'] == PLAIN_REQUEST_SHA256


def test_the_published_record_is_sealed_over_canonically_ordered_bytes():
    """A digest over insertion-ordered bytes would agree with itself; this literal does not."""
    assert RR.sealed(dict(b=1, a=2))['published_projection_sha256'] == CANONICAL_AB_SHA256
    assert RR.sealed(dict(a=2, b=1))['published_projection_sha256'] == CANONICAL_AB_SHA256
    assert RR.canonical_bytes(dict(b=1, a=2)) == b'{"a":2,"b":1}'
    with pytest.raises(RR.ReceiptError):
        RR.sealed(dict(published_projection_sha256='0' * 64))


def test_serialized_request_must_be_the_exact_dispatched_bytes(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(RR.ReceiptError):
        store.record_request(logical_call_id=1, physical_attempt_id=1,
                             serialized=PLAIN_REQUEST.decode(), preflight=None)
    assert sorted(p.name for p in (tmp_path / PRIVATE).iterdir()) == []


def test_the_private_raw_bytes_exist_before_the_published_record_is_written(tmp_path, monkeypatch):
    order = []
    real = RR._write_once

    def spy(path, data):
        order.append((Path(path).name, sorted(p.name for p in (tmp_path / PRIVATE).iterdir())))
        return real(path, data)
    monkeypatch.setattr(RR, '_write_once', spy)
    store = make_store(tmp_path)
    store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=PLAIN_REQUEST, preflight=None)
    assert [name for name, _ in order] == ['call001_attempt01.request.raw', 'call001_attempt01.request.json']
    # at the moment the public record is written, the private raw is already durable
    assert order[1][1] == ['call001_attempt01.request.raw']


def test_a_payload_that_cannot_be_canonicalised_refuses_without_burning_the_attempt(tmp_path):
    """Nothing may be written unless BOTH files can be written: a dispatched request always has a receipt."""
    store = make_store(tmp_path)
    surrogate = b'{"messages": [{"role": "user", "content": "\\ud800"}]}'
    with pytest.raises(RR.ReceiptError):
        store.record_request(logical_call_id=2, physical_attempt_id=1, serialized=surrogate, preflight=None)
    assert sorted(p.name for p in (tmp_path / PRIVATE).iterdir()) == []
    assert sorted(p.name for p in (tmp_path / PUBLIC).iterdir()) == []
    # the attempt key is still usable, so the retry publishes a complete receipt
    record = store.record_request(logical_call_id=2, physical_attempt_id=1, serialized=PLAIN_REQUEST,
                                 preflight=None)
    assert record['raw_request_sha256'] == PLAIN_REQUEST_SHA256
    assert store.completeness()['complete'] is False          # the outcome is still missing, and it says so
    assert store.completeness()['published_record_without_outcome'] == ['call002_attempt01']


def test_an_identity_that_cannot_be_serialized_is_refused_before_any_request_is_written(tmp_path):
    identity = {group: dict(section) for group, section in IDENTITY.items()}
    identity['server']['log'] = Path('/testbed/server.log')      # not JSON-serializable
    with pytest.raises(RR.ReceiptError):
        make_store(tmp_path, identity=identity)
    assert not (tmp_path / PRIVATE).exists() or sorted(p.name for p in (tmp_path / PRIVATE).iterdir()) == []


# ---------------------------------------------------------------- failed / rejected request

@pytest.mark.parametrize('error_class,rejected,detail', [
    ('APIConnectionError', False, 'transport failure talking to 127.0.0.1:8291'),
    ('ContextWindowExceededError', True, 'requested 17032 tokens; the slot serves 16384'),
])
def test_failed_or_rejected_request_keeps_a_full_durable_record_with_unknown_usage_null(tmp_path, error_class,
                                                                                        rejected, detail):
    store = make_store(tmp_path)
    store.record_request(logical_call_id=7, physical_attempt_id=2, serialized=PLAIN_REQUEST, preflight=None)
    outcome = store.record_outcome(logical_call_id=7, physical_attempt_id=2, ok=False, error_class=error_class,
                                   error_detail=detail, rejected_before_generation=rejected)

    # nothing is dropped because the call failed: the pre-dispatch record and the private bytes both remain
    assert private_file(tmp_path, 'call007_attempt02.request.raw').read_bytes() == PLAIN_REQUEST
    assert public_file(tmp_path, 'call007_attempt02.request.json').exists()
    assert json.loads(public_file(tmp_path, 'call007_attempt02.outcome.json').read_text()) == outcome

    assert outcome['phase'] == 'post_dispatch'
    assert outcome['outcome'] == 'error'
    assert outcome['error_class'] == error_class
    assert outcome['error_detail'] == detail
    assert outcome['error_detail_chars'] == len(detail)
    assert outcome['error_detail_complete'] is True
    assert outcome['error_detail_truncated_to'] is None
    assert outcome['rejected_before_generation'] is rejected
    assert outcome['raw_request_sha256'] == PLAIN_REQUEST_SHA256
    assert outcome['raw_request_recomputed_sha256'] == PLAIN_REQUEST_SHA256
    assert outcome['raw_request_digest_agrees'] is True
    assert outcome['raw_request_retained'] is True
    assert outcome['pre_dispatch_record_file'] == 'call007_attempt02.request.json'
    assert outcome['pre_dispatch_record_verified'] == 'published_projection_verified'
    assert outcome['pre_dispatch_projection_sha256'] != outcome['raw_request_sha256']
    assert outcome['published_projection_sha256'] == independent_digest(
        public_file(tmp_path, 'call007_attempt02.outcome.json'))

    usage = outcome['server_reported_usage']
    assert usage['prompt_tokens'] is None
    assert usage['prompt_tokens'] != 0
    assert usage['completion_tokens'] is None
    assert usage['completion_tokens'] != 0
    assert usage['total_tokens'] is None
    assert usage['total_tokens'] != 0
    assert usage['usage_known'] is False
    assert usage['total_known'] is False
    assert usage['unknown_fields'] == ['prompt_tokens', 'completion_tokens']
    assert usage['note'] == UNKNOWN_USAGE_NOTE

    assert outcome['preflight_token_count'] == dict(
        value=None, method=None, status='not obtained; no preflight token count exists for this attempt')
    assert RR.verify_published_projection(public_file(tmp_path, 'call007_attempt02.outcome.json'),
                                          expect_phase='post_dispatch')['status'] == 'published_projection_verified'


def test_failed_request_without_an_error_class_is_refused(tmp_path):
    store = make_store(tmp_path)
    store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=PLAIN_REQUEST, preflight=None)
    with pytest.raises(RR.ReceiptError):
        store.record_outcome(logical_call_id=1, physical_attempt_id=1, ok=False, error_class=None)
    assert not public_file(tmp_path, 'call001_attempt01.outcome.json').exists()


@pytest.mark.parametrize('kwargs', [
    dict(ok='no'), dict(ok=1), dict(ok=None), dict(ok=''),
])
def test_an_outcome_flag_that_is_not_a_bool_is_refused(tmp_path, kwargs):
    store = make_store(tmp_path)
    store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=PLAIN_REQUEST, preflight=None)
    with pytest.raises(RR.ReceiptError):
        store.record_outcome(logical_call_id=1, physical_attempt_id=1, error_class='APIError', **kwargs)
    assert not public_file(tmp_path, 'call001_attempt01.outcome.json').exists()


@pytest.mark.parametrize('contradiction', [dict(error_class='APIConnectionError'),
                                           dict(error_detail='transport failure'),
                                           dict(rejected_before_generation=True)])
def test_a_successful_outcome_carrying_error_fields_is_refused(tmp_path, contradiction):
    store = make_store(tmp_path)
    store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=PLAIN_REQUEST, preflight=None)
    with pytest.raises(RR.ReceiptError):
        store.record_outcome(logical_call_id=1, physical_attempt_id=1, ok=True, **contradiction)
    assert not public_file(tmp_path, 'call001_attempt01.outcome.json').exists()


def test_an_outcome_without_a_durable_pre_dispatch_record_is_refused(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(RR.ReceiptError):
        store.record_outcome(logical_call_id=1, physical_attempt_id=1, ok=True)
    assert sorted(p.name for p in (tmp_path / PUBLIC).iterdir()) == []


@pytest.mark.parametrize('damage', ['raw_digest', 'raw_bytes', 'not_an_object'])
def test_an_outcome_never_republishes_a_raw_digest_the_retained_bytes_contradict(tmp_path, damage):
    store = make_store(tmp_path)
    store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=PLAIN_REQUEST, preflight=None)
    path = public_file(tmp_path, 'call001_attempt01.request.json')
    if damage == 'raw_digest':
        record = json.loads(path.read_text())
        record['raw_request_sha256'] = 'ff' * 32
        path.write_text(json.dumps(record))
    elif damage == 'raw_bytes':
        private_file(tmp_path, 'call001_attempt01.request.raw').write_bytes(b'{"model": "tampered"}')
    else:
        path.write_text('[1, 2, 3]')
    with pytest.raises(RR.ReceiptError):
        store.record_outcome(logical_call_id=1, physical_attempt_id=1, ok=True)
    assert not public_file(tmp_path, 'call001_attempt01.outcome.json').exists()


def test_a_missing_raw_file_leaves_the_agreement_unknown_not_true(tmp_path):
    store = make_store(tmp_path)
    store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=PLAIN_REQUEST, preflight=None)
    private_file(tmp_path, 'call001_attempt01.request.raw').unlink()
    outcome = store.record_outcome(logical_call_id=1, physical_attempt_id=1, ok=True)
    assert outcome['raw_request_retained'] is False
    assert outcome['raw_request_recomputed_sha256'] is None
    assert outcome['raw_request_digest_agrees'] is None
    assert outcome['raw_request_sha256'] == PLAIN_REQUEST_SHA256
    assert store.completeness()['raw_without_published_record'] == []
    assert store.completeness()['published_record_without_raw'] == ['call001_attempt01']
    assert store.completeness()['complete'] is False


# ---------------------------------------------------------------- sanitized projection

def test_public_projection_replaces_home_paths_and_withholds_secrets_with_transformation_metadata(tmp_path):
    store = make_store(tmp_path, identity=SECRET_IDENTITY)
    record = store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=HOME_REQUEST, preflight=None)
    published_text = public_file(tmp_path, 'call001_attempt01.request.json').read_text()

    # the published bytes carry neither the home-like path nor the secret value
    assert '/Users/example-worker' not in published_text
    assert 'none-7f3a' not in published_text

    assert record['payload_projection']['messages'][0]['content'] == (
        'Traceback: File "<HOME>/DTR-AgentEvals/.venv/lib/python3.11/json/decoder.py", line 355')
    assert record['payload_projection']['api_key'] == '<WITHHELD>'
    assert record['payload_projection']['max_tokens'] == 1536        # a count field is never withheld
    assert record['identity']['model']['model_file'] == '<HOME>/DTR-AgentEvals/work/models/coder-7b-q4_k_m.gguf'
    assert record['identity']['server']['api_key'] == '<WITHHELD>'

    assert record['sanitization']['applied'] is True
    assert record['sanitization']['placeholder'] == '<HOME>'
    assert record['sanitization']['withheld_marker'] == '<WITHHELD>'
    assert record['sanitization']['home_masking'] == (
        'enabled: the declared home prefix is replaced at path-component boundaries only')
    assert [(t['transformation'], t['field'], t.get('occurrences')) for t in record['sanitization']['transformations']] == [
        ('home_path_prefix_masked', 'identity.model.model_file', 1),
        ('secret_value_withheld', 'identity.server.api_key', None),
        ('home_path_prefix_masked', 'request_payload.messages[0].content', 1),
        ('secret_value_withheld', 'request_payload.api_key', None),
    ]
    assert all(isinstance(t['why'], str) and t['why'].strip() for t in record['sanitization']['transformations'])

    # the private side keeps the exact unsanitized bytes, and its digest is over those bytes
    assert private_file(tmp_path, 'call001_attempt01.request.raw').read_bytes() == HOME_REQUEST
    assert record['raw_request_sha256'] == HOME_REQUEST_SHA256
    assert record['raw_request_bytes'] == 267
    assert record['published_projection_sha256'] != HOME_REQUEST_SHA256


def test_a_credential_in_a_list_or_under_a_token_key_is_withheld(tmp_path):
    store = make_store(tmp_path)
    payload = {'model': 'm',
               'extra_headers': ['Authorization: Bearer sk-live-4f3a9c', 'X-Api-Key: none-7f3a'],
               'Token': 'sk-live-4f3a9c',
               'session': {'TOKEN': 'sk-live-4f3a9c'},
               'max_tokens': 1536,
               'messages': [{'role': 'user', 'content': 'the log says password=hunter2 near the top'}]}
    record = store.record_request(logical_call_id=1, physical_attempt_id=1,
                                 serialized=json.dumps(payload).encode(), preflight=None)
    published_text = public_file(tmp_path, 'call001_attempt01.request.json').read_text()
    assert 'sk-live-4f3a9c' not in published_text
    assert 'hunter2' not in published_text
    assert 'none-7f3a' not in published_text
    projection = record['payload_projection']
    assert projection['extra_headers'] == ['Authorization: <WITHHELD>', 'X-Api-Key: <WITHHELD>']
    assert projection['Token'] == '<WITHHELD>'
    assert projection['session']['TOKEN'] == '<WITHHELD>'
    assert projection['max_tokens'] == 1536
    assert projection['messages'][0]['content'] == 'the log says password=<WITHHELD> near the top'
    assert [(t['transformation'], t['field']) for t in record['sanitization']['transformations']] == [
        ('secret_value_masked_in_text', 'request_payload.extra_headers[0]'),
        ('secret_value_masked_in_text', 'request_payload.extra_headers[1]'),
        ('secret_value_withheld', 'request_payload.Token'),
        ('secret_value_withheld', 'request_payload.session.TOKEN'),
        ('secret_value_masked_in_text', 'request_payload.messages[0].content'),
    ]
    assert RR.is_secret_key('Token') is True
    assert RR.is_secret_key('TOKEN') is True
    assert RR.is_secret_key('access_token') is True
    assert RR.is_secret_key('api_key') is True
    assert RR.is_secret_key('Authorization') is True
    assert RR.is_secret_key('max_tokens') is False
    assert RR.is_secret_key('completion_tokens') is False
    assert RR.is_secret_key('endpoint') is False


def test_the_home_prefix_is_masked_only_at_a_path_component_boundary(tmp_path):
    store = make_store(tmp_path, home='/Users/example')
    payload = {'model': 'm', 'messages': [
        {'role': 'user', 'content': '/Users/example/DTR/x and /Users/example-worker2/DTR/x and /Users/example'}]}
    record = store.record_request(logical_call_id=1, physical_attempt_id=1,
                                 serialized=json.dumps(payload).encode(), preflight=None)
    assert record['payload_projection']['messages'][0]['content'] == (
        '<HOME>/DTR/x and /Users/example-worker2/DTR/x and <HOME>')
    assert [(t['transformation'], t['occurrences']) for t in record['sanitization']['transformations']] == [
        ('home_path_prefix_masked', 2)]


def test_the_default_home_prefix_comes_from_the_environment_and_is_recorded(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', '/Users/example-default')
    store = RR.RequestReceiptStore(tmp_path / PRIVATE, tmp_path / PUBLIC, cohort=COHORT, identity=IDENTITY,
                                   clock=lambda: CLOCK_EPOCH, root=tmp_path)
    assert store.home == '/Users/example-default'
    payload = {'model': 'm', 'messages': [{'role': 'user', 'content': 'see /Users/example-default/DTR/setup.py'}]}
    record = store.record_request(logical_call_id=1, physical_attempt_id=1,
                                 serialized=json.dumps(payload).encode(), preflight=None)
    assert record['payload_projection']['messages'][0]['content'] == 'see <HOME>/DTR/setup.py'
    assert record['sanitization']['home_prefix_masked'] is True


@pytest.mark.parametrize('home', ['/', '//', '/Users', 'relative/path', 12, ['/Users/example']])
def test_a_pathological_home_prefix_is_refused(tmp_path, home):
    with pytest.raises(RR.ReceiptError):
        make_store(tmp_path, home=home)


def test_masking_can_be_disabled_only_explicitly_and_is_recorded_as_disabled(tmp_path):
    store = make_store(tmp_path, home='')
    record = store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=HOME_REQUEST,
                                 preflight=None)
    assert record['sanitization']['home_prefix_masked'] is False
    assert record['sanitization']['home_masking'] == (
        'disabled: no home prefix was declared, so no path prefix was masked')
    # the secret is still withheld; only the home masking is off
    assert record['payload_projection']['api_key'] == '<WITHHELD>'
    assert '/Users/example-worker' in record['payload_projection']['messages'][0]['content']


def test_error_detail_is_sanitized_before_publication(tmp_path):
    store = make_store(tmp_path)
    store.record_request(logical_call_id=2, physical_attempt_id=1, serialized=PLAIN_REQUEST, preflight=None)
    outcome = store.record_outcome(logical_call_id=2, physical_attempt_id=1, ok=False, error_class='JSONDecodeError',
                                   error_detail='failed in ' + FAKE_HOME + '/DTR-AgentEvals/.venv/lib/json/decoder.py')
    assert outcome['error_detail'] == 'failed in <HOME>/DTR-AgentEvals/.venv/lib/json/decoder.py'
    assert '/Users/example-worker' not in public_file(tmp_path, 'call002_attempt01.outcome.json').read_text()
    assert [(t['transformation'], t['field'], t['occurrences']) for t in outcome['sanitization']['transformations']] == [
        ('home_path_prefix_masked', 'error_detail', 1)]


def test_a_truncated_error_detail_says_so_and_a_short_one_does_not(tmp_path):
    store = make_store(tmp_path)
    store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=PLAIN_REQUEST, preflight=None)
    long_detail = 'E' * 496
    outcome = store.record_outcome(logical_call_id=1, physical_attempt_id=1, ok=False,
                                   error_class='APIConnectionError', error_detail=long_detail)
    assert outcome['error_detail'] == 'E' * 300
    assert len(outcome['error_detail']) == 300
    assert outcome['error_detail_chars'] == 496
    assert outcome['error_detail_complete'] is False
    assert outcome['error_detail_truncated_to'] == 300
    assert [(t['transformation'], t.get('kept_chars'), t.get('sanitized_chars'))
            for t in outcome['sanitization']['transformations']] == [('error_detail_truncated', 300, 496)]
    assert RR.ERROR_DETAIL_CHARS == 300

    store.record_request(logical_call_id=2, physical_attempt_id=1, serialized=PLAIN_REQUEST, preflight=None)
    short = store.record_outcome(logical_call_id=2, physical_attempt_id=1, ok=False, error_class='APIError',
                                 error_detail='brief')
    assert short['error_detail'] == 'brief'
    assert short['error_detail_chars'] == 5
    assert short['error_detail_complete'] is True
    assert short['error_detail_truncated_to'] is None
    assert short['sanitization']['transformations'] == []


def test_a_non_json_request_keeps_its_record_and_withholds_the_payload_projection(tmp_path):
    store = make_store(tmp_path)
    record = store.record_request(logical_call_id=4, physical_attempt_id=1, serialized=b'\x80not-json',
                                  preflight=None)
    assert private_file(tmp_path, 'call004_attempt01.request.raw').read_bytes() == b'\x80not-json'
    assert record['raw_request_bytes'] == 9
    assert record['payload_projection'] is None
    assert record['payload_projection_available'] is False          # withheld, not empty
    assert record['payload_projection_bytes'] is None
    assert record['payload_projection_status'].startswith('unavailable:')
    assert [(t['transformation'], t['field']) for t in record['sanitization']['transformations']] == [
        ('payload_projection_withheld', 'request_payload')]

    # a payload that IS the JSON null publishes the same null projection, but says it is available
    literal_null = store.record_request(logical_call_id=5, physical_attempt_id=1, serialized=b'null',
                                        preflight=None)
    assert literal_null['payload_projection'] is None
    assert literal_null['payload_projection_available'] is True
    assert literal_null['payload_projection_status'] == 'sanitized projection of the serialized request payload'
    assert literal_null['sanitization']['transformations'] == []


# ---------------------------------------------------------------- write-once and completeness

@pytest.mark.parametrize('second', ['request', 'outcome'])
def test_a_second_write_to_the_same_record_path_refuses(tmp_path, second):
    store = make_store(tmp_path)
    store.record_request(logical_call_id=5, physical_attempt_id=1, serialized=PLAIN_REQUEST, preflight=None)
    if second == 'request':
        with pytest.raises(RR.ReceiptError):
            store.record_request(logical_call_id=5, physical_attempt_id=1, serialized=HOME_REQUEST, preflight=None)
        assert private_file(tmp_path, 'call005_attempt01.request.raw').read_bytes() == PLAIN_REQUEST
        assert json.loads(public_file(tmp_path, 'call005_attempt01.request.json').read_text())[
            'raw_request_sha256'] == PLAIN_REQUEST_SHA256
    else:
        store.record_outcome(logical_call_id=5, physical_attempt_id=1, ok=True,
                             usage=RR.server_usage(1712, 96, source='llama-server usage field'))
        with pytest.raises(RR.ReceiptError):
            store.record_outcome(logical_call_id=5, physical_attempt_id=1, ok=False, error_class='APIError')
        recorded = json.loads(public_file(tmp_path, 'call005_attempt01.outcome.json').read_text())
        assert recorded['outcome'] == 'ok'
        assert recorded['error_class'] is None


def test_completeness_names_every_hole_in_the_published_set(tmp_path):
    store = make_store(tmp_path)
    store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=PLAIN_REQUEST, preflight=None)
    store.record_outcome(logical_call_id=1, physical_attempt_id=1, ok=True)
    assert store.completeness() == dict(
        cohort='cue-v1', run_id=RUN_ID, attempt_keys=['call001_attempt01'], n_raw=1, n_published=1,
        n_outcomes=1, complete=True, raw_without_published_record=[], published_record_without_raw=[],
        published_record_without_outcome=[], outcome_without_published_record=[],
        invalid_records=[],
        note='A published receipt set with a hole is a pattern formed by skipping incomplete records: '
             'do not report subtotals over it without this list')

    # a private raw with no published receipt is exactly the hole the lead's 'no skipped records' rule forbids
    private_file(tmp_path, 'call002_attempt01.request.raw').write_bytes(PLAIN_REQUEST)
    report = store.completeness()
    assert report['complete'] is False
    assert report['raw_without_published_record'] == ['call002_attempt01']
    assert report['attempt_keys'] == ['call001_attempt01', 'call002_attempt01']
    assert report['n_raw'] == 2
    assert report['n_published'] == 1


# ---------------------------------------------------------------- token counts

def test_preflight_token_count_is_always_published_with_its_method(tmp_path):
    store = make_store(tmp_path, preflight=RR.preflight_token_count(
        15021, 'served GGUF tokenizer via llama-server /tokenize on the rendered chat template'))
    record = store.record_request(logical_call_id=9, physical_attempt_id=1, serialized=PLAIN_REQUEST)
    preflight = record['preflight_token_count']
    assert preflight['value'] == 15021
    assert preflight['method'] == 'served GGUF tokenizer via llama-server /tokenize on the rendered chat template'
    assert preflight['status'] == ('worker-side preflight count; not a server-verified tokenization of the '
                                  'dispatched bytes')

    store.record_outcome(logical_call_id=9, physical_attempt_id=1, ok=True, usage=RR.server_usage())
    outcome = json.loads(public_file(tmp_path, 'call009_attempt01.outcome.json').read_text())
    assert outcome['preflight_token_count']['value'] == 15021
    assert outcome['preflight_token_count']['method'] == (
        'served GGUF tokenizer via llama-server /tokenize on the rendered chat template')
    assert outcome['server_reported_usage']['prompt_tokens'] is None
    assert outcome['server_reported_usage']['prompt_tokens'] != 0


@pytest.mark.parametrize('bare', [15021, '15021', dict(value=15021), dict(value=15021, method=''),
                                  dict(value=15021, method='   '), dict(value=15021, method=None),
                                  dict(method='llama-server /tokenize'),
                                  dict(value=15021, method='llama-server /tokenize', server_verified=True),
                                  dict(value=15021, method='llama-server /tokenize',
                                       raw_request_equality='validated')])
def test_a_preflight_token_count_without_its_method_string_or_with_extra_claims_is_refused(tmp_path, bare):
    store = make_store(tmp_path)
    with pytest.raises(RR.ReceiptError):
        store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=PLAIN_REQUEST, preflight=bare)
    assert sorted(p.name for p in (tmp_path / PRIVATE).iterdir()) == []
    assert sorted(p.name for p in (tmp_path / PUBLIC).iterdir()) == []


def test_preflight_helper_refuses_a_missing_method_and_a_non_integer_count():
    with pytest.raises(RR.ReceiptError):
        RR.preflight_token_count(15021, '')
    with pytest.raises(RR.ReceiptError):
        RR.preflight_token_count(15021, None)
    with pytest.raises(RR.ReceiptError):
        RR.preflight_token_count('15021', 'llama-server /tokenize')


def test_known_usage_totals_and_partially_unknown_usage_stays_unknown():
    known = RR.server_usage(1712, 96, source='llama-server /v1/chat/completions usage field')
    assert known['prompt_tokens'] == 1712
    assert known['completion_tokens'] == 96
    assert known['total_tokens'] == 1808
    assert known['total_tokens_source'] == 'sum_of_reported_pair'
    assert known['reported_total_tokens'] is None
    assert known['total_discrepancy'] is None
    assert known['usage_known'] is True
    assert known['total_known'] is True
    assert known['unknown_fields'] == []
    assert known['source'] == 'llama-server /v1/chat/completions usage field'

    partial = RR.server_usage(1712, None)
    assert partial['prompt_tokens'] == 1712
    assert partial['completion_tokens'] is None
    assert partial['completion_tokens'] != 0
    assert partial['total_tokens'] is None
    assert partial['total_tokens'] != 1712
    assert partial['usage_known'] is False
    assert partial['total_known'] is False
    assert partial['unknown_fields'] == ['completion_tokens']

    with pytest.raises(RR.ReceiptError):
        RR.server_usage(-1, 0)
    with pytest.raises(RR.ReceiptError):
        RR.server_usage(1712, 96, total_tokens='1808')


def test_a_server_reported_total_is_kept_even_when_the_pair_is_unknown(tmp_path):
    only_total = RR.server_usage(total_tokens=1808, source='llama-server usage field')
    assert only_total['total_tokens'] == 1808
    assert only_total['total_tokens_source'] == 'server_reported'
    assert only_total['reported_total_tokens'] == 1808
    assert only_total['total_known'] is True
    assert only_total['usage_known'] is False                  # the SPLIT is still unknown
    assert only_total['unknown_fields'] == ['prompt_tokens', 'completion_tokens']
    assert only_total['prompt_tokens'] is None
    assert only_total['completion_tokens'] is None

    store = make_store(tmp_path)
    store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=PLAIN_REQUEST, preflight=None)
    outcome = store.record_outcome(logical_call_id=1, physical_attempt_id=1, ok=True,
                                   usage=dict(total_tokens=1808, source='llama-server usage field'))
    usage = outcome['server_reported_usage']
    assert usage['total_tokens'] == 1808
    assert usage['total_tokens_source'] == 'server_reported'
    assert usage['usage_known'] is False
    assert usage['source'] == 'llama-server usage field'


def test_a_server_total_that_disagrees_with_the_reported_pair_is_recorded_not_overwritten():
    clash = RR.server_usage(1712, 96, total_tokens=99999, source='llama-server usage field')
    assert clash['total_tokens'] == 99999
    assert clash['total_tokens_source'] == 'server_reported'
    assert clash['reported_total_tokens'] == 99999
    assert clash['total_discrepancy'] == dict(
        server_reported_total=99999, sum_of_reported_pair=1808,
        note='the server-reported total disagrees with the sum of the reported pair; both are retained and '
             'neither is silently replaced')
    # a round trip of a derived total is re-derived, never relabelled as server-reported
    assert RR._validated_usage(RR.server_usage(1712, 96))['total_tokens_source'] == 'sum_of_reported_pair'
    with pytest.raises(RR.ReceiptError):
        RR._validated_usage(dict(prompt_tokens=1, completion_tokens=1, invented_field=3))


# ---------------------------------------------------------------- identity and private-location contract

@pytest.mark.parametrize('damage', ['model', 'decoding', 'server', 'tokenizer', 'model.model_sha256',
                                    'decoding.max_tokens'])
def test_identity_requires_model_decoding_server_and_tokenizer(tmp_path, damage):
    identity = {group: dict(section) for group, section in IDENTITY.items()}
    if '.' in damage:
        group, key = damage.split('.')
        identity[group].pop(key)
    else:
        identity.pop(damage)
    with pytest.raises(RR.ReceiptError):
        make_store(tmp_path, identity=identity)


@pytest.mark.parametrize('private,root', [
    ('results/v2_agent/cue_v1_private', None),          # inside the immutable results tree
    ('results/v2_agent/cue_v1_private', 'repo'),        # ... even when the caller misdeclares the root
    ('published/cue-v1', None),                         # the published directory itself
    ('published/cue-v1/raw', None),                     # nested inside the published directory
    ('work_private/receipts', None),                    # inside the repo root but not under work/
])
def test_raw_request_bytes_may_not_be_stored_inside_the_published_tree(tmp_path, private, root):
    with pytest.raises(RR.ReceiptError):
        RR.RequestReceiptStore(tmp_path / private, tmp_path / PUBLIC, cohort=COHORT, identity=IDENTITY,
                               home=FAKE_HOME, root=tmp_path if root is None else tmp_path / root)
    assert not (tmp_path / private / 'call001_attempt01.request.raw').exists()


def test_a_published_directory_inside_the_private_directory_is_refused(tmp_path):
    with pytest.raises(RR.ReceiptError):
        RR.RequestReceiptStore(tmp_path / 'work/receipts', tmp_path / 'work/receipts/published',
                               cohort=COHORT, identity=IDENTITY, home=FAKE_HOME, root=tmp_path)


def test_a_private_directory_outside_the_declared_root_says_the_label_rests_on_that_declaration(tmp_path):
    outside = tmp_path / 'elsewhere/receipts'
    store = RR.RequestReceiptStore(outside, tmp_path / 'repo' / PUBLIC, cohort=COHORT, identity=IDENTITY,
                                   home=FAKE_HOME, clock=lambda: CLOCK_EPOCH, root=tmp_path / 'repo')
    record = store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=PLAIN_REQUEST,
                                  preflight=None)
    assert record['raw_request_private_root'] == 'worker-local directory outside the repository'
    assert record['raw_request_private_root_basis'] == (
        'the declared repository root does not contain this directory; the label rests on the root declared '
        'by the caller, not on an inspection of the working tree')
    assert (outside / 'call001_attempt01.request.raw').read_bytes() == PLAIN_REQUEST


def test_cohort_namespace_is_required(tmp_path):
    with pytest.raises(RR.ReceiptError):
        RR.RequestReceiptStore(tmp_path / PRIVATE, tmp_path / PUBLIC, cohort='  ', identity=IDENTITY, root=tmp_path)


@pytest.mark.parametrize('logical,physical', [(0, 1), (1, 0), (-1, 1), (1.0, 1), (True, 1)])
def test_call_and_attempt_ids_must_be_positive_integers(logical, physical):
    with pytest.raises(RR.ReceiptError):
        RR.attempt_key(logical, physical)


# ---------------------------------------------------------------- dispatch wrapper

def test_recorded_dispatch_keeps_the_record_when_the_dispatch_raises(tmp_path):
    class ReadTimeout(RuntimeError):
        pass

    store = make_store(tmp_path)
    with pytest.raises(ReadTimeout):
        with RR.recorded_dispatch(store, logical_call_id=24, physical_attempt_id=2, serialized=PLAIN_REQUEST,
                                  preflight=None) as dispatch:
            # a partial stream: the server reported a finish reason, a status and partial usage, then broke
            dispatch.rejected_before_generation = False
            dispatch.finish_reason = 'length'
            dispatch.http_status = 200
            dispatch.usage = RR.server_usage(1712, None, source='llama-server usage field')
            raise ReadTimeout('no response within 900 s')
    assert private_file(tmp_path, 'call024_attempt02.request.raw').read_bytes() == PLAIN_REQUEST
    outcome = json.loads(public_file(tmp_path, 'call024_attempt02.outcome.json').read_text())
    assert outcome['outcome'] == 'error'
    assert outcome['error_class'] == 'ReadTimeout'
    assert outcome['error_detail'] == 'no response within 900 s'
    assert outcome['rejected_before_generation'] is False
    assert outcome['finish_reason'] == 'length'                 # kept on the FAILURE path too
    assert outcome['http_status'] == 200
    assert outcome['raw_request_sha256'] == PLAIN_REQUEST_SHA256
    assert outcome['server_reported_usage']['prompt_tokens'] == 1712
    assert outcome['server_reported_usage']['completion_tokens'] is None
    assert outcome['server_reported_usage']['total_tokens'] is None
    assert outcome['server_reported_usage']['usage_known'] is False
    assert outcome['server_reported_usage']['source'] == 'llama-server usage field'
    assert store.completeness()['complete'] is True


def test_recorded_dispatch_records_a_successful_outcome_with_reported_usage(tmp_path):
    store = make_store(tmp_path)
    with RR.recorded_dispatch(store, logical_call_id=1, physical_attempt_id=1, serialized=PLAIN_REQUEST,
                              preflight=None) as dispatch:
        dispatch.usage = RR.server_usage(1712, 96, source='llama-server /v1/chat/completions usage field')
        dispatch.finish_reason = 'stop'
        dispatch.http_status = 200
    outcome = json.loads(public_file(tmp_path, 'call001_attempt01.outcome.json').read_text())
    assert outcome['outcome'] == 'ok'
    assert outcome['error_class'] is None
    assert outcome['finish_reason'] == 'stop'
    assert outcome['http_status'] == 200
    assert outcome['server_reported_usage']['prompt_tokens'] == 1712
    assert outcome['server_reported_usage']['completion_tokens'] == 96
    assert outcome['server_reported_usage']['total_tokens'] == 1808
    assert dispatch.receipt_errors == []


def test_a_receipt_failure_after_dispatch_never_replaces_or_aborts_the_episode_result(tmp_path):
    """Bookkeeping must not relabel a terminal assignment: the real exception survives, success stays success."""
    class ReadTimeout(RuntimeError):
        pass

    store = make_store(tmp_path)
    # burn both outcome paths, so record_outcome cannot write once the dispatch has happened
    public_file(tmp_path, 'call003_attempt01.outcome.json').write_text('{"pre-existing": true}\n')
    public_file(tmp_path, 'call004_attempt01.outcome.json').write_text('{"pre-existing": true}\n')

    seen = []
    # the failure path: the dispatch exception, not a ReceiptError, reaches the caller
    with pytest.raises(ReadTimeout) as err:
        with RR.recorded_dispatch(store, logical_call_id=3, physical_attempt_id=1, serialized=PLAIN_REQUEST,
                                  preflight=None, on_receipt_error=seen.append) as dispatch:
            raise ReadTimeout('no response within 900 s')
    assert str(err.value) == 'no response within 900 s'
    assert dispatch.receipt_errors[0]['error_class'] == 'ReceiptError'
    assert dispatch.receipt_errors[0]['attempt_key'] == 'call003_attempt01'
    assert dispatch.receipt_errors[0]['phase'] == 'post_dispatch'

    # the success path: a call that actually succeeded is not aborted by the receipt problem
    with RR.recorded_dispatch(store, logical_call_id=4, physical_attempt_id=1, serialized=PLAIN_REQUEST,
                              preflight=None, on_receipt_error=seen.append) as dispatch:
        dispatch.finish_reason = 'stop'
    assert [failure['attempt_key'] for failure in seen] == ['call003_attempt01', 'call004_attempt01']
    assert json.loads(public_file(tmp_path, 'call004_attempt01.outcome.json').read_text()) == {
        'pre-existing': True}
    completeness = store.completeness()
    assert completeness['complete'] is False                   # filenames alone never establish completeness
    assert [r['file'] for r in completeness['invalid_records']] == [
        'call003_attempt01.outcome.json', 'call004_attempt01.outcome.json']


def test_a_pre_dispatch_receipt_failure_still_refuses_before_the_model_is_called(tmp_path):
    store = make_store(tmp_path)
    store.record_request(logical_call_id=8, physical_attempt_id=1, serialized=PLAIN_REQUEST, preflight=None)
    called = []
    with pytest.raises(RR.ReceiptError):
        with RR.recorded_dispatch(store, logical_call_id=8, physical_attempt_id=1, serialized=PLAIN_REQUEST,
                                  preflight=None):
            called.append('dispatched')
    assert called == []                                        # the body never ran: nothing was dispatched


# ---------------------------------------------------------------- read-only verification

@pytest.mark.parametrize('damage', ['payload', 'marker', 'projection_digest_presented_as_raw', 'missing_raw_digest',
                                    'phase', 'not_an_object', 'reworded_equality_semantics'])
def test_verify_refuses_a_tampered_or_mislabelled_published_projection(tmp_path, damage):
    store = make_store(tmp_path)
    store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=PLAIN_REQUEST, preflight=None)
    path = public_file(tmp_path, 'call001_attempt01.request.json')
    record = json.loads(path.read_text())
    if damage == 'payload':
        record['identity']['decoding']['max_tokens'] = 4096
    elif damage == 'marker':
        record.pop('raw_request_equality')
    elif damage == 'projection_digest_presented_as_raw':
        record['published_projection_sha256'] = record['raw_request_sha256']
    elif damage == 'missing_raw_digest':
        record.pop('raw_request_sha256')
    elif damage == 'not_an_object':
        record = [1, 2, 3]
    elif damage == 'reworded_equality_semantics':
        record['digest_semantics']['raw_request_equality'] = 'validated equality to the raw request bytes'
    else:
        record['phase'] = 'post_dispatch'
    path.write_text(json.dumps(record))
    with pytest.raises(RR.ReceiptError):
        RR.verify_published_projection(path, expect_phase='pre_dispatch')


def test_verify_refuses_an_unparsable_or_absent_published_record(tmp_path):
    missing = tmp_path / 'absent.request.json'
    with pytest.raises(RR.ReceiptError):
        RR.verify_published_projection(missing)
    broken = tmp_path / 'broken.request.json'
    broken.write_text('{not json')
    with pytest.raises(RR.ReceiptError):
        RR.verify_published_projection(broken)


@pytest.mark.parametrize('dispatch_fails', [False, True])
def test_a_raising_receipt_callback_never_replaces_the_dispatch_result(tmp_path, monkeypatch, dispatch_fails):
    store = make_store(tmp_path)
    def fail_write(**kwargs):
        raise OSError('receipt disk fixture failure')
    def fail_callback(failure):
        raise ValueError('callback fixture failure')
    monkeypatch.setattr(store, 'record_outcome', fail_write)
    holder = None
    try:
        with RR.recorded_dispatch(store, logical_call_id=1, physical_attempt_id=1, serialized=PLAIN_REQUEST,
                                  on_receipt_error=fail_callback) as holder:
            if dispatch_fails:
                raise TimeoutError('original dispatch failure')
    except TimeoutError as exc:
        assert dispatch_fails
        assert str(exc) == 'original dispatch failure'
    else:
        assert not dispatch_fails
    assert [e['error_class'] for e in holder.receipt_errors] == ['OSError', 'ValueError']
    assert holder.receipt_errors[1]['phase'] == 'receipt_error_callback'
    assert store.completeness()['complete'] is False
    assert store.completeness()['published_record_without_outcome'] == ['call001_attempt01']


@pytest.mark.parametrize('text', ["export API_KEY='fixture-dummy-12345'", 'token="fixture dummy 12345"',
                                'Authorization: "Bearer fixture-dummy-12345"'])
def test_quoted_credential_assignments_in_message_text_are_withheld(text):
    projection, transforms = RR.sanitize({'messages': [{'content': text}]}, '', field='request_payload')
    assert 'fixture' not in projection['messages'][0]['content']
    assert '<WITHHELD>' in projection['messages'][0]['content']
    assert transforms[0]['transformation'] == 'secret_value_masked_in_text'
    assert transforms[0]['field'] == 'request_payload.messages[0].content'
    assert transforms[0]['occurrences'] == 1


@pytest.mark.parametrize('damage', ['invalid_json', 'empty_object', 'bad_seal', 'wrong_link', 'wrong_raw_link',
                                  'wrong_recomputed_raw', 'wrong_attempt', 'wrong_cohort', 'empty_usage',
                                  'raw_proof_claim', 'missing_raw', 'changed_raw'])
def test_completeness_validates_receipts_and_links_instead_of_only_filenames(tmp_path, damage):
    store = make_store(tmp_path)
    store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=PLAIN_REQUEST)
    store.record_outcome(logical_call_id=1, physical_attempt_id=1, ok=True)
    path = public_file(tmp_path, 'call001_attempt01.outcome.json')
    if damage == 'invalid_json':
        path.write_text('{')
    elif damage == 'empty_object':
        path.write_text('{}')
    elif damage == 'missing_raw':
        private_file(tmp_path, 'call001_attempt01.request.raw').unlink()
    elif damage == 'changed_raw':
        private_file(tmp_path, 'call001_attempt01.request.raw').write_bytes(b'changed')
    else:
        record = json.loads(path.read_text())
        if damage == 'bad_seal':
            record['finish_reason'] = 'changed'
        else:
            if damage == 'wrong_link':
                record['pre_dispatch_projection_sha256'] = '0' * 64
            elif damage == 'wrong_raw_link':
                record['raw_request_sha256'] = '0' * 64
            elif damage == 'wrong_recomputed_raw':
                record['raw_request_recomputed_sha256'] = '0' * 64
            elif damage == 'wrong_attempt':
                record['logical_call_id'] = 2
            elif damage == 'wrong_cohort':
                record['cohort'] = 'other'
            elif damage == 'empty_usage':
                record['server_reported_usage'] = {}
            elif damage == 'raw_proof_claim':
                record['raw_bytes_independently_verified'] = True
            payload = {k: v for k, v in record.items() if k != 'published_projection_sha256'}
            record['published_projection_sha256'] = hashlib.sha256(json.dumps(
                payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
        path.write_text(json.dumps(record))
    result = store.completeness()
    assert result['complete'] is False
    assert result['n_published'] == result['n_outcomes'] == 1  # adverse records are never dropped
    if damage == 'missing_raw':
        assert result['published_record_without_raw'] == ['call001_attempt01']
        outcome = json.loads(path.read_text())
        assert outcome['server_reported_usage']['prompt_tokens'] is None
        assert outcome['server_reported_usage']['completion_tokens'] is None
    else:
        assert result['invalid_records']


@pytest.mark.parametrize('missing_group', ['model', 'decoding', 'server', 'tokenizer'])
def test_completeness_requires_identity_groups_even_when_all_hash_links_are_valid(tmp_path, missing_group):
    store = make_store(tmp_path)
    store.record_request(logical_call_id=1, physical_attempt_id=1, serialized=PLAIN_REQUEST)
    path = public_file(tmp_path, 'call001_attempt01.request.json')
    record = json.loads(path.read_text())
    record['identity'].pop(missing_group)
    payload = {k: v for k, v in record.items() if k != 'published_projection_sha256'}
    record['published_projection_sha256'] = hashlib.sha256(json.dumps(
        payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()).hexdigest()
    path.write_text(json.dumps(record))
    # The outcome links to this resealed projection, so mere digest/link checking cannot detect the defect.
    store.record_outcome(logical_call_id=1, physical_attempt_id=1, ok=True)
    result = store.completeness()
    assert result['complete'] is False
    assert result['invalid_records'][0]['file'] == 'call001_attempt01.request.json'
    assert missing_group in result['invalid_records'][0]['error']
