"""DTR-REQ-005 cue-v1 capture of the exact outbound request body at the pinned client's transport boundary.

Implements the lead's integration contract, bullet **Transport**, and the lead's answers to the worker's open
items 1 (storage and bounded publication) and 2 (post-dispatch bookkeeping), in
docs/theory_feedback_20260923_req005_review.md. The injection point is the one traced in
docs/req005_transport_map_20260923.md. This module is instrumentation only. It never changes model-visible
messages, H24, temperature, context, the model pins, the Submitted-only endpoint, the 576-request cap or the
12-assignment frame. It does not import or edit the frozen yaml-v1 drivers.

Where the bytes are taken
  On the pinned stack (litellm 1.102.0 -> openai 2.54.0 -> httpx 0.28.1), the openai SDK finalizes the body
  (openai/_base_client.py:600). httpx then hands the finished `httpx.Request` to `transport.handle_request(request)`
  (httpx/_client.py:1014). `CapturingTransport` sits exactly there. `install_litellm_session` installs it through
  litellm's own hook, `litellm.client_session`, wrapping the real terminal transport. litellm still builds the openai
  client itself with the frozen api_base, api_key, timeout, max_retries and organization, so the URL, model fields,
  generation settings, response parsing and SDK retry policy are unchanged. The session differs from litellm's
  default client in one way only: `follow_redirects=False`, so a redirect is surfaced, never silently re-sent.

For each physical send, in this order, before anything reaches the terminal:
  1. A latched infrastructure stop, a send outside an open query attempt, and a second send inside one query attempt
     are all refused. The last is litellm's hidden second pass or an SDK retry; one physical send is allowed per
     logical query attempt.
  2. A body that is not an in-memory `httpx.ByteStream` is refused unread. Streaming and non-replayable bodies are
     never buffered here. The body is read with `request.read()`, and the stream the terminal will iterate must
     yield exactly those bytes. A Content-Length that disagrees with them is refused.
  3. The body must fit the 8 MiB per-body cap. The cohort's 576-request budget must have a unit left.
  4. Free space is rechecked for this write. The exact bytes are then persisted durably under work/ (write-once,
     fsync, directory sync), with their sha256 and byte length. A bounded, sanitized public receipt is written with
     them. Authorization and other credential header values are never persisted.
  5. Only then is the SAME request object handed to the inner transport, and one budget unit is consumed.
Any refusal records the digest/length (when the body could be read), the reason and "no physical request". It
never truncates, never sends and never retries. It raises `PreDispatchRefusal`, an `openai.OpenAIError` subclass,
so the SDK neither retries nor wraps it (openai/_base_client.py:1099-1101). `CueTransportCapture.dispatch` turns
every storage, measurement, budget or protocol refusal into `InfrastructureStop`, the predeclared stop. The caller
lists it in its abort exceptions, so mini-swe-agent's tenacity layer does not retry. After an infrastructure stop
the capture is latched, and nothing else is sent.

Post-dispatch bookkeeping (outcome record, response inspection) is nonfatal. The model's original success or
exception is returned or raised unchanged. The failure is recorded separately, in memory and in a compact
secondary log where possible. Usage is taken only from the server's own response body, never from litellm's parsed
object, which reports zeros when the server sent no usage. Nothing is re-sent, and `integrity()` reports the
receipt set as incomplete.

The episode deadline is never swallowed. The frozen driver enforces its absolute inference deadline with a one-shot
SIGALRM that raises `EpisodeDeadline` (a TimeoutError). Every catch-all in this module treats a TimeoutError as the
deadline, not as a bookkeeping or storage failure: it records what was interrupted, latches the capture so nothing
else is sent, and `dispatch` re-raises that same deadline object once its in-memory evidence is recorded. A
deadline outside a dispatch scope is re-raised at once.

Query identity is sequenced. The first dispatch of an episode is logical call 1, query attempt 1. Each later dispatch
is either the next query attempt of the same logical call or query attempt 1 of the next logical call, within H24 and
the two frozen attempts per logical call. Anything else is an infrastructure stop, so no (call, attempt) pair can be
reused and no logical id can go backwards.

Litellm's hidden second pass (and any SDK retry or redirect hop) is refused after the first send of a query attempt.
That is the contract's "disable" option, and it can change what the caller observes compared with litellm's
default client: the caller then sees litellm's mapping of the refusal, while the server's own status stays in the
outcome record. `integrity()` reports every such case as a deviation from the frozen client path
(`frozen_path_parity`), for the lead to review; it is not hidden inside a complete-looking record.
"""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
import cue_cohort as CC  # noqa: E402  registry only: no runtime, no frozen source
import request_receipt as RR  # noqa: E402  lead-accepted receipts; composed here, not edited

try:        # present in the pinned mini-swe-agent venv; absent from the project test venv
    import httpx
except ImportError:  # pragma: no cover - the pure core below is still importable and testable
    httpx = None
try:
    import openai
except ImportError:  # pragma: no cover
    openai = None

KiB, MiB, GiB = 1024, 1024 ** 2, 1024 ** 3
BODY_CAP_BYTES = 8 * MiB                                             # lead answer 1: per-body cap
COHORT_RAW_RESERVATION_BYTES = CC.MAX_PHYSICAL_REQUESTS * BODY_CAP_BYTES   # 576 x 8 MiB = 4.5 GiB
START_FREE_ABOVE_RESERVE_BYTES = 6 * GiB                             # start preflight above the host reserve
PUBLIC_WHOLE_MAX_BYTES = 64 * KiB
PUBLIC_HEAD_BYTES = 32 * KiB
PUBLIC_TAIL_BYTES = 32 * KiB
PUBLIC_RECORD_CAP_BYTES = 128 * KiB                                  # final serialized size of each public record
MAX_LISTED_TRANSFORMATIONS = 32
SENDS_PER_QUERY_ATTEMPT = 1                                          # the contract value
RESPONSE_PARSE_MAX_BYTES = 4 * MiB
BOUNDED_TEXT_CHARS = 256
FINISH_REASON_CHARS = 64
DETAIL_CHARS = RR.ERROR_DETAIL_CHARS
REFUSAL_SUFFIX = '.refusal.json'
REFUSAL_DIGEST_FIELD = 'refusal_record_sha256'
BOOKKEEPING_LOG = 'bookkeeping_errors.jsonl'
BOOKKEEPING_LINE_MAX_BYTES = 4 * KiB                                 # a secondary-log line, rechecked before writing
MAX_WIRE_HEADER_NAMES = 64

CANONICALIZATION = ('json.dumps(sanitized payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) '
                    'encoded as UTF-8')
PUBLICATION_RULE = ('lead answer 1: the sanitized payload is canonicalized and its complete sha256/byte length '
                    'kept; it is published whole when it fits 65536 bytes, otherwise as at most a 32768-byte head '
                    'plus a 32768-byte tail cut at UTF-8 character boundaries with their original byte offsets; the '
                    'final serialized receipt is capped at 131072 bytes, and when the capped record cannot hold the '
                    'preview the preview is omitted entirely with this reason')
PREVIEW_NOTE = ('a head/tail preview is never the complete request; the complete exact bytes are private and only '
                'their digest and length are published here')
USAGE_SOURCE = ('the usage object of the server response body, read after the client read it; litellm\'s parsed '
                'usage is not used because it reports zeros when the server sent none')
NO_USAGE_SOURCE = 'the server response body carried no usable usage object, or it was not read; usage stays unknown'
STORAGE_RULE = ('before every write, free space minus the declared host reserve must cover the bytes about to be '
                'written; a request write also reserves one maximum-size outcome record')
SECONDARY_LOG_NOTE = 'compact worker-local log of post-dispatch bookkeeping failures; never published automatically'

PUBLISHED_HEADERS = ('accept', 'content-type', 'content-length', 'user-agent', 'x-stainless-retry-count',
                     'x-stainless-read-timeout')
SENSITIVE_HEADERS = ('authorization', 'proxy-authorization', 'api-key', 'x-api-key', 'cookie')

# reason code -> (classification, infrastructure stop, meaning)
REFUSALS = {
    'infrastructure_stop_latched': ('protocol', True, 'an earlier infrastructure stop is latched; nothing else is sent'),
    'no_open_query_attempt': ('protocol', True, 'a send arrived outside CueTransportCapture.dispatch, so it has no '
                                                'authoritative logical call id and cannot be receipted'),
    'query_attempt_send_limit': ('hidden_resend_suppressed', False,
                                 'a further physical send inside one logical query attempt (litellm second pass, '
                                 'SDK retry or redirect) was refused; one send per query attempt is enforced'),
    'cohort_request_budget_exhausted': ('budget', True, 'the cohort physical-request budget has no unit left'),
    'non_replayable_body': ('measurement', True, 'the body is not an in-memory byte stream; it is refused unread '
                                                 'rather than buffered'),
    'stream_body_mismatch': ('measurement', True, 'the stream the terminal would read does not yield the bytes read '
                                                  'for persistence'),
    'content_length_mismatch': ('measurement', True, 'the Content-Length header disagrees with the body bytes'),
    'body_over_cap': ('measurement', True, 'the exact body exceeds the per-body cap; it is not truncated or sent'),
    'public_receipt_over_cap': ('measurement', True, 'even a preview-free public receipt exceeds the record cap'),
    'insufficient_free_space': ('storage', True, 'free space above the host reserve does not cover this write'),
    'durable_write_failed': ('storage', True, 'the durable pre-dispatch write failed; the request is not sent'),
    'receipt_contract_refused': ('protocol', True, 'the receipt store refused the pre-dispatch record (for example a '
                                                   'write-once collision); the request is not sent'),
    'receipt_internal_error': ('protocol', True, 'the pre-dispatch receipt could not be built; the request is not '
                                                 'sent'),
    'insufficient_free_space_at_start': ('storage', True, 'the start preflight found less than 6 GiB free above the '
                                                          'host reserve'),
    'install_preflight_failed': ('protocol', True, 'the pinned client path is not in the state the capture requires'),
    'invalid_query_identity': ('protocol', True, 'the logical call id or query attempt is outside the frozen bounds, '
                                                 'reuses an earlier pair or goes backwards'),
    'nested_query_attempt': ('protocol', True, 'a query attempt was opened inside another one'),
    'client_session_bypassed': ('protocol', True, 'a cached client does not use the capture session, so a send may '
                                                  'have bypassed the receipts'),
    'client_session_binding_unverifiable': ('protocol', True, 'the post-call session-binding check raised, so it '
                                                              'cannot be confirmed that every send was captured'),
    'uncaptured_success': ('protocol', True, 'the call returned a result although no physical send was captured'),
    'episode_deadline_latched': ('deadline', False, 'the episode deadline was reached inside the capture; nothing '
                                                    'further is sent'),
    'episode_deadline_during_write': ('deadline', False, 'the episode deadline interrupted the durable pre-dispatch '
                                                         'write; the request is not sent'),
}
DEADLINE_NOTE = ('the episode deadline (a TimeoutError such as the frozen driver\'s EpisodeDeadline) is recorded, '
                 'latches the capture and is re-raised; it is never classified as a storage or bookkeeping failure')


class InfrastructureStop(Exception):
    """The predeclared infrastructure stop. It is never an outcome-driven stopping rule. The caller lists it in its
    abort exceptions, so no automatic model retry follows. `refusal` is the recorded refusal, and `result` holds a
    model result that arrived through an uncaptured path, if one did."""

    def __init__(self, message, *, refusal=None, result=None):
        super().__init__(message)
        self.refusal = refusal
        self.result = result


class StartPreflightRefused(InfrastructureStop):
    """The start preflight failed; no episode work may begin."""


_REFUSAL_BASE = openai.OpenAIError if openai is not None else RuntimeError


class PreDispatchRefusal(_REFUSAL_BASE):
    """Raised inside the transport instead of sending. Nothing reached the terminal."""

    def __init__(self, message, *, refusal):
        super().__init__(message)
        self.refusal = refusal


class _SpaceShortfall(Exception):
    def __init__(self, observation):
        super().__init__('free space above the host reserve does not cover the write')
        self.observation = observation


class _ReceiptOverCap(RR.ReceiptError):
    """Even the preview-free public receipt exceeds PUBLIC_RECORD_CAP_BYTES."""


# ---------------------------------------------------------------- small helpers

def sha256_hex(data):
    return hashlib.sha256(bytes(data)).hexdigest()


def disk_free_bytes(path):
    """Default free-space probe. Tests inject their own."""
    return shutil.disk_usage(path).free


def _serialized(record):
    """The exact published bytes: UTF-8 JSON (multibyte characters stay raw, so they are not tripled by \\uXXXX
    escapes). The cap is always checked on these final encoded bytes, which include every quote, backslash and
    control-character escape. A string that is not encodable as UTF-8 falls back to ASCII escapes."""
    try:
        return (json.dumps(record, indent=1, ensure_ascii=False) + '\n').encode('utf-8')
    except UnicodeEncodeError:
        return (json.dumps(record, indent=1) + '\n').encode('ascii')


def _encoded_len(data):
    return len(data)


def _durable_sync(path):
    """Flush a written file or directory entry to stable storage (F_FULLFSYNC where the OS has it)."""
    fd = os.open(str(path), os.O_RDONLY)
    try:
        full = getattr(fcntl, 'F_FULLFSYNC', None)
        if full is not None:
            try:
                fcntl.fcntl(fd, full)
                return
            except OSError:
                pass
        os.fsync(fd)
    finally:
        os.close(fd)


def _bounded(text, limit):
    """(bounded text, original length, truncated?) for a caller-supplied string."""
    text = str(text)
    return text[:limit], len(text), len(text) > limit


def _utf8_floor(buf, k):
    """Largest UTF-8 character boundary <= k."""
    k = min(max(k, 0), len(buf))
    while 0 < k < len(buf) and (buf[k] & 0xC0) == 0x80:
        k -= 1
    return k


def _utf8_ceil(buf, k):
    """Smallest UTF-8 character boundary >= k."""
    k = min(max(k, 0), len(buf))
    while k < len(buf) and (buf[k] & 0xC0) == 0x80:
        k += 1
    return k


def wire_metadata(method, url, headers):
    """Publishable request-line/header facts. Credential header VALUES are never included. URL userinfo and query
    strings are dropped and their presence is recorded."""
    items = [(str(k), str(v)) for k, v in headers]
    all_names = sorted({k.lower() for k, _ in items})
    names = all_names[:MAX_WIRE_HEADER_NAMES]
    published = {k.lower(): v[:BOUNDED_TEXT_CHARS] for k, v in items if k.lower() in PUBLISHED_HEADERS}
    parts = urllib.parse.urlsplit(str(url))
    host = parts.hostname or ''
    netloc = host if parts.port is None else '%s:%d' % (host, parts.port)
    declared = published.get('content-length')
    try:
        content_length = int(declared) if declared is not None else None
    except ValueError:
        content_length = -1                      # unparsable: never equal to a body length
    return dict(method=str(method)[:16],
                url=urllib.parse.urlunsplit((parts.scheme, netloc, parts.path, '', ''))[:BOUNDED_TEXT_CHARS],
                url_query_present=bool(parts.query), url_userinfo_present=parts.username is not None,
                header_names=names, header_names_total=len(all_names),
                header_names_omitted=len(all_names) - len(names), headers_published=published,
                content_length=content_length,
                sensitive_headers_present=sorted(n for n in all_names
                                                 if n in SENSITIVE_HEADERS or RR.is_secret_key(n))[:MAX_WIRE_HEADER_NAMES],
                sensitive_header_values_persisted=False)


def payload_publication(raw, home):
    """(publication metadata, whole projection object or None, transformations) for one raw body.

    Redaction happens BEFORE excerpting. The sanitized payload is canonicalized, and its complete sha256/length is
    always kept. The whole object is published when it fits PUBLIC_WHOLE_MAX_BYTES. Otherwise a head and a tail are
    cut at UTF-8 character boundaries."""
    projection, status, available, transformations = RR.payload_projection(raw, home)
    base = dict(rule=PUBLICATION_RULE, canonicalization=CANONICALIZATION, whole_limit_bytes=PUBLIC_WHOLE_MAX_BYTES,
                head_limit_bytes=PUBLIC_HEAD_BYTES, tail_limit_bytes=PUBLIC_TAIL_BYTES,
                record_cap_bytes=PUBLIC_RECORD_CAP_BYTES, note=PREVIEW_NOTE)
    empty = dict(published_representation=None, published_sha256=None, published_bytes=0, head=None, tail=None,
                 omitted_middle=None)
    if not available:
        return dict(base, mode='unavailable', complete=False, truncated=False, sanitized_payload_sha256=None,
                    sanitized_payload_bytes=None, reason=status, **empty), None, transformations
    try:
        canon = RR.canonical_bytes(projection)
    except RR.ReceiptError as exc:
        return dict(base, mode='unavailable', complete=False, truncated=False, sanitized_payload_sha256=None,
                    sanitized_payload_bytes=None, **empty,
                    reason='the sanitized payload could not be canonicalized (%s); only the raw digest and length '
                           'are published' % type(exc).__name__), None, transformations
    n, digest = len(canon), sha256_hex(canon)
    common = dict(base, sanitized_payload_sha256=digest, sanitized_payload_bytes=n)
    if n <= PUBLIC_WHOLE_MAX_BYTES:
        return dict(common, mode='whole', complete=True, truncated=False,
                    published_representation='json_object in payload_projection; its canonical form is the '
                                             'sanitized payload itself',
                    published_sha256=digest, published_bytes=n, head=None, tail=None, omitted_middle=None,
                    reason='the canonical sanitized payload fits the whole-publication limit'), projection, \
            transformations
    head_end = _utf8_floor(canon, PUBLIC_HEAD_BYTES)
    tail_start = _utf8_ceil(canon, n - PUBLIC_TAIL_BYTES)
    head, tail = canon[:head_end], canon[tail_start:]
    return dict(common, mode='head_tail', complete=False, truncated=True,
                published_representation='utf8_text_excerpts of the canonical sanitized payload: head.text and '
                                         'tail.text; offsets are byte offsets into that canonical payload',
                published_sha256=None, published_bytes=len(head) + len(tail),
                head=dict(offset_start=0, offset_end=head_end, bytes=len(head), sha256=sha256_hex(head),
                          boundary_adjustment_bytes=PUBLIC_HEAD_BYTES - head_end, text=head.decode('utf-8')),
                tail=dict(offset_start=tail_start, offset_end=n, bytes=len(tail), sha256=sha256_hex(tail),
                          boundary_adjustment_bytes=tail_start - (n - PUBLIC_TAIL_BYTES), text=tail.decode('utf-8')),
                omitted_middle=dict(offset_start=head_end, offset_end=tail_start, bytes=tail_start - head_end),
                reason='the canonical sanitized payload exceeds the whole-publication limit, so only a head and a '
                       'tail are published'), None, transformations


def _omit_preview(publication, reason):
    return dict(publication, mode='omitted', complete=False, truncated=True,
                omitted_preview_mode=publication['mode'], omitted_preview_bytes=publication['published_bytes'],
                published_representation=None, published_sha256=None, published_bytes=0, head=None, tail=None,
                omitted_middle=None, reason=reason)


# ---------------------------------------------------------------- bounded receipt store

class BoundedReceiptStore(RR.RequestReceiptStore):
    """`request_receipt.RequestReceiptStore` with the lead's bounded publication (answer 1).

    The helper module is not edited. This subclass reuses its identity/preflight/usage validation, sanitization,
    write-once files, seals and completeness checks. It overrides only the two record writers, because the helper
    publishes the whole projection unbounded. Every record written here still passes the helper's own
    `completeness()` validation. `write_once` is injectable so storage-failure fixtures are deterministic."""

    def __init__(self, private_dir, public_dir, *, cohort, identity, run_id=None, preflight=None, home=None,
                 clock=time.time, root=RR.ROOT, write_once=None):
        for name, value in (('cohort', cohort), ('run_id', run_id)):
            if isinstance(value, str) and len(value) > BOUNDED_TEXT_CHARS:
                raise RR.ReceiptError('%s longer than %d characters is refused so every record stays bounded'
                                      % (name, BOUNDED_TEXT_CHARS))
        super().__init__(private_dir, public_dir, cohort=cohort, identity=identity, run_id=run_id,
                         preflight=preflight, home=home, clock=clock, root=root)
        self._write_once = RR._write_once if write_once is None else write_once
        # A preview-free receipt must fit the cap, or no request could ever be receipted: refuse now, before work.
        public_identity, transformations = RR.sanitize(self.identity, self.home, field='identity')
        publication = _omit_preview(dict(payload_publication(b'', self.home)[0], published_bytes=0), 'init probe')
        probe = self._request_payload(key='call001_attempt01', logical_call_id=1, physical_attempt_id=1, raw=b'',
                                      public_identity=public_identity,
                                      preflight=RR._validated_preflight(self.default_preflight), projection=None,
                                      publication=publication, send_public={}, transformations=transformations,
                                      listed_limit=0)
        if _encoded_len(_serialized(RR.sealed(probe))) > PUBLIC_RECORD_CAP_BYTES:
            raise _ReceiptOverCap('the declared identity alone makes a public receipt exceed %d bytes'
                                  % PUBLIC_RECORD_CAP_BYTES)

    # -- shared pieces -----------------------------------------------------
    def _bounded_sanitization(self, transformations, listed_limit):
        listed = transformations[:listed_limit]
        by_type = {}
        for entry in transformations:
            kind = by_type.setdefault(entry.get('transformation'), dict(entries=0, occurrences=0))
            kind['entries'] += 1
            kind['occurrences'] += entry.get('occurrences', 1) if isinstance(entry.get('occurrences'), int) else 1
        return dict(self._sanitization(listed), applied=bool(transformations),
                    transformations_total=len(transformations), transformations_listed=len(listed),
                    transformations_omitted=len(transformations) - len(listed),
                    transformation_listing_limit=listed_limit, transformations_by_type=by_type)

    def _request_payload(self, *, key, logical_call_id, physical_attempt_id, raw, public_identity, preflight,
                         projection, publication, send_public, transformations, listed_limit):
        whole = projection is not None
        return dict(
            self._common(key, logical_call_id, physical_attempt_id, 'pre_dispatch'),
            kind='DTR-REQ-005 cue-v1 pre-dispatch request receipt (bounded sanitized projection)',
            dispatch_state='persisted_before_dispatch',
            **{RR.RAW_DIGEST_FIELD: sha256_hex(raw)},
            raw_request_bytes=len(raw),
            raw_request_body_cap_bytes=BODY_CAP_BYTES,
            raw_request_private_file=self.raw_path(key).name,
            raw_request_private_root=self.private_root_label,
            raw_request_private_root_basis=self.private_root_basis,
            raw_request_published=False,
            sensitive_header_values_persisted=False,
            identity=public_identity,
            preflight_token_count=preflight,
            server_reported_usage=None,
            server_reported_usage_status='not dispatched yet; unknown usage is never recorded as 0',
            payload_projection=projection,
            payload_projection_available=whole,
            payload_projection_status=('complete sanitized projection of the serialized request payload' if whole
                                       else 'not published whole: see payload_publication (mode %s)'
                                       % publication['mode']),
            payload_projection_bytes=publication['sanitized_payload_bytes'],
            payload_projection_bound=PUBLICATION_RULE,
            payload_publication=publication,
            send=send_public,
            sanitization=self._bounded_sanitization(transformations, listed_limit),
            digest_semantics=RR.DIGEST_SEMANTICS,
            raw_request_equality=RR.REPORTED_UNVERIFIED,
            raw_bytes_independently_verified=False,
            sanitization_transform_independently_verified=False)

    def _write_public(self, path, text, before_write=None):
        if before_write is not None:
            before_write(raw_bytes=0, public_bytes=_encoded_len(text))
        self._write_once(path, text)
        _durable_sync(path)
        _durable_sync(self.public_dir)

    # -- pre-dispatch -----------------------------------------------------
    def record_request(self, *, logical_call_id, physical_attempt_id, serialized, preflight=RR._UNSET,
                       identity=None, send=None, before_write=None):
        """Persist the exact bytes privately and a bounded public receipt, BEFORE dispatch.

        Both texts are built and size-checked before anything is written. `before_write(raw_bytes=, public_bytes=)`
        runs just before the first write (the free-space recheck) and may raise to refuse."""
        key = RR.attempt_key(logical_call_id, physical_attempt_id)
        if not isinstance(serialized, (bytes, bytearray)):
            raise RR.ReceiptError('the serialized request must be the exact bytes that are dispatched')
        raw = bytes(serialized)
        record_preflight = RR._validated_preflight(self.default_preflight if preflight is RR._UNSET else preflight)
        ident = self.identity if identity is None else RR.validate_identity(identity)
        public_identity, identity_transformations = RR.sanitize(ident, self.home, field='identity')
        publication, projection, payload_transformations = payload_publication(raw, self.home)
        send_public, send_transformations = RR.sanitize(send or {}, self.home, field='send')
        transformations = identity_transformations + payload_transformations + send_transformations
        text = None
        attempts = ((MAX_LISTED_TRANSFORMATIONS, True), (0, True), (0, False))
        for listed_limit, keep_preview in attempts:
            pub = publication if keep_preview or publication['mode'] not in ('whole', 'head_tail') else _omit_preview(
                publication, 'the serialized receipt with this preview exceeded the %d-byte public record cap after '
                             'JSON escaping; the preview is omitted entirely, and the complete sanitized and raw '
                             'digests and lengths are kept' % PUBLIC_RECORD_CAP_BYTES)
            payload = self._request_payload(
                key=key, logical_call_id=logical_call_id, physical_attempt_id=physical_attempt_id, raw=raw,
                public_identity=public_identity, preflight=record_preflight,
                projection=projection if pub['mode'] == 'whole' else None, publication=pub,
                send_public=send_public, transformations=transformations, listed_limit=listed_limit)
            candidate = _serialized(RR.sealed(payload))
            if _encoded_len(candidate) <= PUBLIC_RECORD_CAP_BYTES:
                text, record = candidate, json.loads(candidate)
                break
        if text is None:
            raise _ReceiptOverCap('the public receipt exceeds %d bytes even without a preview'
                                  % PUBLIC_RECORD_CAP_BYTES)
        if before_write is not None:
            before_write(raw_bytes=len(raw), public_bytes=_encoded_len(text))
        self._write_once(self.raw_path(key), raw)            # the private raw bytes exist first
        _durable_sync(self.raw_path(key))
        _durable_sync(self.private_dir)
        self._write_public(self.record_path(key), text)
        return record

    # -- post-dispatch ----------------------------------------------------
    def record_outcome(self, *, logical_call_id, physical_attempt_id, ok, error_class=None, error_detail=None,
                       usage=None, rejected_before_generation=None, finish_reason=None, http_status=None,
                       send=None, before_write=None):
        """Write-once outcome linked to its pre-dispatch receipt, capped at PUBLIC_RECORD_CAP_BYTES.

        The helper's field contract is kept, so its completeness() validates this record. Caller-supplied strings
        are bounded and the bound is stated explicitly. The final serialized size is checked before writing."""
        key = RR.attempt_key(logical_call_id, physical_attempt_id)
        path = self.record_path(key)
        if not isinstance(ok, bool):
            raise RR.ReceiptError('the outcome flag must be a bool; a truthy value is never recorded as success')
        RR.verify_published_projection(path, expect_phase='pre_dispatch')
        pre = json.loads(path.read_text())
        if not ok and not (isinstance(error_class, str) and error_class.strip()):
            raise RR.ReceiptError('a failed or rejected request must record its error class')
        if ok and (error_class is not None or error_detail is not None or rejected_before_generation is True):
            raise RR.ReceiptError('a successful outcome must not carry an error class, an error detail or '
                                  'rejected_before_generation=True; refusing a self-contradictory record')
        if http_status is not None and (type(http_status) is not int):
            raise RR.ReceiptError('http_status must be an int or None (unknown)')
        if finish_reason is not None and not isinstance(finish_reason, str):
            raise RR.ReceiptError('finish_reason must be a string or None (unknown)')
        reported_raw = pre.get(RR.RAW_DIGEST_FIELD)
        raw_path = self.raw_path(key)
        recomputed, agrees = None, None
        if raw_path.exists():
            recomputed = sha256_hex(raw_path.read_bytes())
            agrees = recomputed == reported_raw
            if not agrees:
                raise RR.ReceiptError('the retained raw request bytes for %s hash to %s, not to the digest recorded '
                                      'before dispatch' % (key, recomputed))
        transformations = []
        cls_text = cls_chars = None
        cls_truncated = False
        if not ok:
            masked, cls_transformations = RR.sanitize(error_class.strip(), self.home, field='error_class')
            cls_text, cls_chars, cls_truncated = _bounded(masked, BOUNDED_TEXT_CHARS)
            transformations += cls_transformations
            if cls_truncated:
                transformations.append(dict(transformation='error_class_truncated', field='error_class',
                                            occurrences=1, kept_chars=BOUNDED_TEXT_CHARS, sanitized_chars=cls_chars,
                                            why='the published error class is bounded; the bound is stated'))
        detail = detail_chars = truncated_to = None
        if error_detail is not None:
            masked, detail_transformations = RR.sanitize(str(error_detail), self.home, field='error_detail')
            detail_chars = len(masked)
            detail = masked[:DETAIL_CHARS]
            transformations += detail_transformations
            if detail_chars > DETAIL_CHARS:
                truncated_to = DETAIL_CHARS
                transformations.append(dict(
                    transformation='error_detail_truncated', field='error_detail', occurrences=1,
                    kept_chars=DETAIL_CHARS, sanitized_chars=detail_chars,
                    why='the published error detail is bounded; the transformation is listed so a truncated '
                        'detail is never indistinguishable from a complete one'))
        finish, finish_chars, finish_truncated = (None, None, False) if finish_reason is None else _bounded(
            finish_reason, FINISH_REASON_CHARS)
        send_public, send_transformations = RR.sanitize(send or {}, self.home, field='send')
        transformations += send_transformations
        payload = dict(
            self._common(key, logical_call_id, physical_attempt_id, 'post_dispatch'),
            kind='DTR-REQ-005 cue-v1 request outcome record (write-once, bounded, linked to its pre-dispatch receipt)',
            outcome='ok' if ok else 'error',
            error_class=cls_text,
            error_class_chars=cls_chars,
            error_class_truncated=cls_truncated,
            error_detail=detail,
            error_detail_chars=detail_chars,
            error_detail_complete=None if detail is None else truncated_to is None,
            error_detail_truncated_to=truncated_to,
            rejected_before_generation=rejected_before_generation,
            finish_reason=finish,
            finish_reason_chars=finish_chars,
            finish_reason_truncated=finish_truncated,
            http_status=http_status,
            server_reported_usage=RR._validated_usage(usage),
            preflight_token_count=pre.get('preflight_token_count'),
            pre_dispatch_record_file=path.name,
            pre_dispatch_record_verified='published_projection_verified',
            pre_dispatch_projection_sha256=pre.get(RR.PROJECTION_DIGEST_FIELD),
            **{RR.RAW_DIGEST_FIELD: reported_raw},
            raw_request_recomputed_sha256=recomputed,
            raw_request_digest_agrees=agrees,
            raw_request_retained=raw_path.exists(),
            raw_request_private_file=raw_path.name,
            raw_request_private_root=self.private_root_label,
            raw_request_private_root_basis=self.private_root_basis,
            send=send_public,
            record_cap_bytes=PUBLIC_RECORD_CAP_BYTES,
            sanitization=self._bounded_sanitization(transformations, MAX_LISTED_TRANSFORMATIONS),
            digest_semantics=RR.DIGEST_SEMANTICS,
            raw_request_equality=RR.REPORTED_UNVERIFIED,
            raw_bytes_independently_verified=False,
            sanitization_transform_independently_verified=False)
        record = RR.sealed(payload)
        text = _serialized(record)
        if _encoded_len(text) > PUBLIC_RECORD_CAP_BYTES:
            raise _ReceiptOverCap('the outcome record exceeds %d bytes' % PUBLIC_RECORD_CAP_BYTES)
        self._write_public(self.outcome_path(key), text, before_write)
        return json.loads(text)

    # -- refusals ---------------------------------------------------------
    def refusal_path(self, ordinal):
        return self.public_dir / ('refusal%03d%s' % (ordinal, REFUSAL_SUFFIX))

    def record_refusal(self, refusal, before_write=None):
        """Publish one sanitized, sealed refusal record (no physical request). Best effort for the caller.

        `before_write(raw_bytes=, public_bytes=)` is the free-space recheck; it may raise to refuse the write."""
        public, transformations = RR.sanitize(refusal, self.home, field='refusal')
        payload = dict(request='DTR-REQ-005', cohort=self.cohort, run_id=self.run_id, phase='refused_before_dispatch',
                       kind='DTR-REQ-005 cue-v1 pre-dispatch refusal record (no physical request)',
                       recorded_utc=RR.utc(self.clock()), refusal=public,
                       sanitization=self._bounded_sanitization(transformations, MAX_LISTED_TRANSFORMATIONS))
        text = _serialized(RR.sealed(payload, field=REFUSAL_DIGEST_FIELD))
        if _encoded_len(text) > PUBLIC_RECORD_CAP_BYTES:
            raise _ReceiptOverCap('the refusal record exceeds %d bytes' % PUBLIC_RECORD_CAP_BYTES)
        self._write_public(self.refusal_path(refusal['refusal_ordinal']), text, before_write)
        return json.loads(text)

    # -- completeness -----------------------------------------------------
    def completeness(self):
        """The helper's completeness, plus refusal records, their ordinal sequence and the public record cap.

        Refusal ordinals are consecutive from 1, so a deleted refusal record is a gap, never silence. A published
        pre-dispatch receipt whose attempt a refusal names was never dispatched: it is listed separately and is not
        counted among the dispatched attempts."""
        out = super().completeness()
        refusals, invalid, ordinals, refused_keys = [], [], [], []
        for path in sorted(Path(self.public_dir).glob('*' + REFUSAL_SUFFIX)):
            try:
                record = json.loads(path.read_text())
                digest = record.get(REFUSAL_DIGEST_FIELD)
                body = {k: v for k, v in record.items() if k != REFUSAL_DIGEST_FIELD}
                if digest != RR.canonical_sha256(body):
                    raise RR.ReceiptError('refusal record digest mismatch')
                if record.get('cohort') != self.cohort or record.get('run_id') != self.run_id:
                    raise RR.ReceiptError('refusal record identity does not match its episode')
                refusal = record['refusal']
                ordinal = refusal.get('refusal_ordinal')
                if type(ordinal) is not int or ordinal < 1 or path.name != self.refusal_path(ordinal).name:
                    raise RR.ReceiptError('refusal record ordinal does not match its filename')
                if refusal.get('physical_request') is not False or refusal.get('dispatched_to_terminal') is not False:
                    raise RR.ReceiptError('a refusal record must state that no physical request was made')
                ordinals.append(ordinal)
                if refusal.get('attempt_key'):
                    refused_keys.append(refusal['attempt_key'])
                refusals.append(dict(file=path.name, reason_code=refusal.get('reason_code'),
                                     infrastructure_stop=refusal.get('infrastructure_stop'),
                                     logical_call_id=refusal.get('logical_call_id'),
                                     attempt_key=refusal.get('attempt_key'),
                                     body_sha256=refusal.get('body_sha256'), body_bytes=refusal.get('body_bytes')))
            except Exception as exc:  # noqa: BLE001  a corrupt record is an incomplete set, not a crash
                invalid.append(dict(file=path.name, error='%s: %s' % (type(exc).__name__, str(exc)[:300])))
        present = set(ordinals)
        for path in Path(self.public_dir).glob('refusal*' + REFUSAL_SUFFIX):
            digits = path.name[len('refusal'):-len(REFUSAL_SUFFIX)]
            if digits.isdigit():
                present.add(int(digits))                  # a file that exists is not a gap, valid or not
        missing = sorted(set(range(1, max(present | {0}) + 1)) - present)
        if missing:
            invalid.append(dict(file=None, error='refusal ordinal gap: record(s) %s missing' % missing))
        over_cap = sorted(p.name for p in Path(self.public_dir).iterdir() if p.is_file()
                          and p.name.endswith((RR.PUBLIC_SUFFIX, RR.OUTCOME_SUFFIX, REFUSAL_SUFFIX))
                          and p.stat().st_size > PUBLIC_RECORD_CAP_BYTES)
        not_dispatched = sorted(set(refused_keys) & set(out['attempt_keys']))
        out.update(pre_dispatch_refusals=refusals, invalid_refusal_records=invalid,
                   records_over_public_cap=over_cap, refusal_ordinals_missing=missing,
                   receipts_refused_before_dispatch=not_dispatched,
                   dispatched_attempt_keys=sorted(set(out['attempt_keys']) - set(not_dispatched)),
                   infrastructure_stop_recorded=any(r['infrastructure_stop'] for r in refusals),
                   complete=out['complete'] and not invalid and not over_cap)
        return out


def read_only_completeness(private_dir, public_dir, *, cohort, run_id):
    """BoundedReceiptStore.completeness() over an EXISTING receipt set, without constructing a store (which would
    create directories): for validation and resume-time corrupt-receipt detection. Writes nothing."""
    store = BoundedReceiptStore.__new__(BoundedReceiptStore)
    store.private_dir, store.public_dir = Path(private_dir), Path(public_dir)
    store.cohort, store.run_id = cohort, run_id
    if not store.private_dir.is_dir() or not store.public_dir.is_dir():
        return dict(complete=False, invalid_records=[dict(file=None, error='receipt directory missing')],
                    invalid_refusal_records=[])
    return store.completeness()


# ---------------------------------------------------------------- request budget

class RequestBudget:
    """The cohort's physical-request budget. `used` is required: the queue states what earlier episodes and
    resumes already consumed, and it is never silently reset to 0."""

    def __init__(self, *, used, limit=CC.MAX_PHYSICAL_REQUESTS):
        for name, value in (('used', used), ('limit', limit)):
            if type(value) is not int or value < 0:
                raise ValueError('budget %s must be a non-negative int' % name)
        if limit > CC.MAX_PHYSICAL_REQUESTS:
            raise ValueError('the cohort budget cannot exceed the frozen %d physical requests'
                             % CC.MAX_PHYSICAL_REQUESTS)
        if used > limit:
            raise ValueError('budget used (%d) exceeds its limit (%d)' % (used, limit))
        self.limit, self.used = limit, used

    def remaining(self):
        return self.limit - self.used

    def consume(self):
        if self.used >= self.limit:
            raise ValueError('request budget exhausted')
        self.used += 1
        return self.used


# ---------------------------------------------------------------- the capture (pure core)

def _response_body(response):
    """The body bytes the client read, or None. httpx raises ResponseNotRead when the client never read it."""
    try:
        content = response.content
    except Exception:  # noqa: BLE001
        return None
    return bytes(content) if isinstance(content, (bytes, bytearray)) else None


def _server_reported(content):
    if content is None or len(content) > RESPONSE_PARSE_MAX_BYTES:
        return None
    try:
        parsed = json.loads(content)
    except (ValueError, UnicodeDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _usage_from(parsed):
    usage = parsed.get('usage') if parsed else None
    if not isinstance(usage, dict):
        return RR.server_usage(source=NO_USAGE_SOURCE)

    def pick(name):
        value = usage.get(name)
        return value if type(value) is int and value >= 0 else None
    return RR.server_usage(pick('prompt_tokens'), pick('completion_tokens'), total_tokens=pick('total_tokens'),
                           source=USAGE_SOURCE)


def _finish_reason_from(parsed):
    try:
        value = parsed['choices'][0]['finish_reason']
    except (KeyError, IndexError, TypeError):
        return None
    return value if isinstance(value, str) else None


def _server_error_from(parsed):
    """The error object a server sent (type/code/message), bounded; None when there is none."""
    error = parsed.get('error') if parsed else None
    if not isinstance(error, dict):
        return None
    out = {}
    for key in ('type', 'code', 'message'):
        value = error.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            out[key] = value if isinstance(value, int) else value[:DETAIL_CHARS]
    return out or None


class CueTransportCapture:
    """Per-episode ledger and gate for physical sends. It holds no httpx object; `CapturingTransport` adapts it.

    `host_reserve_bytes` is required. The repository defines no host disk reserve, so the caller must declare it.
    The start preflight runs here, on the private AND the public receipt directory. Unless free space minus the
    reserve is at least 6 GiB on each, or a free-space probe fails, the constructor raises StartPreflightRefused, and
    no episode work can start.

    H24 and the two physical attempts per logical call are the frozen values and cannot be enlarged here. More than
    one send per query attempt is accepted only with `accounting_fixture=True`, which is recorded in every receipt and
    in integrity(); the cue-v1 episode never passes it."""

    def __init__(self, store, *, budget, host_reserve_bytes, free_space_probe=disk_free_bytes,
                 sends_per_query_attempt=SENDS_PER_QUERY_ATTEMPT, horizon=CC.H,
                 attempts_per_call=CC.ATTEMPTS_PER_CALL, on_receipt_error=None, clock=time.time,
                 accounting_fixture=False):
        if not isinstance(store, BoundedReceiptStore):
            raise TypeError('the capture requires a BoundedReceiptStore (bounded public receipts)')
        if not isinstance(budget, RequestBudget):
            raise TypeError('the capture requires a RequestBudget')
        if type(host_reserve_bytes) is not int or host_reserve_bytes < 0:
            raise ValueError('host_reserve_bytes must be declared as a non-negative int')
        if type(horizon) is not int or horizon != CC.H:
            raise ValueError('the call horizon is the frozen H=%d; it cannot be changed here' % CC.H)
        if type(attempts_per_call) is not int or attempts_per_call != CC.ATTEMPTS_PER_CALL:
            raise ValueError('physical attempts per logical call are the frozen %d' % CC.ATTEMPTS_PER_CALL)
        if type(sends_per_query_attempt) is not int or sends_per_query_attempt < 1:
            raise ValueError('sends_per_query_attempt must be a positive int (the contract value is 1)')
        if sends_per_query_attempt != SENDS_PER_QUERY_ATTEMPT and accounting_fixture is not True:
            raise ValueError('more than one send per query attempt is an accounting fixture only; the contract '
                             'value is %d' % SENDS_PER_QUERY_ATTEMPT)
        self.store, self.budget, self.host_reserve_bytes = store, budget, host_reserve_bytes
        self.free_space_probe, self.clock = free_space_probe, clock
        self.sends_per_query_attempt, self.horizon, self.attempts_per_call = (sends_per_query_attempt, horizon,
                                                                              attempts_per_call)
        self.accounting_fixture = accounting_fixture is True
        self.on_receipt_error = on_receipt_error
        self.binding_check = None          # set by install_litellm_session; returns a list of violations
        self.sends, self.refusals, self.attempts, self.bookkeeping_failures = [], [], [], []
        self.interrupted_writes, self.deadline_events = [], []
        self._scope = None
        self._in_dispatch = False
        self._stopped = None
        self._deadline_exc = None
        self._last_query = None
        self._physical_by_call = {}
        self.start_preflight = self._start_preflight()

    # -- the deadline ---------------------------------------------------
    def _note_deadline(self, exc, phase):
        """Record a TimeoutError (the episode deadline) and latch. The first one is the one re-raised."""
        if self._deadline_exc is None:
            self._deadline_exc = exc
        self.deadline_events.append(dict(phase=phase, error_class=type(exc).__name__,
                                         scope=None if self._scope is None else dict(
                                             logical_call_id=self._scope['logical_call_id'],
                                             query_attempt_id=self._scope['query_attempt']),
                                         recorded_utc=RR.utc(self.clock())))

    @property
    def deadline_reached(self):
        return self._deadline_exc is not None

    # -- storage checks ---------------------------------------------------
    def _free(self, path):
        return self.free_space_probe(path)

    def _start_preflight(self):
        required = self.host_reserve_bytes + START_FREE_ABOVE_RESERVE_BYTES
        record = dict(host_reserve_bytes=self.host_reserve_bytes,
                      required_free_above_reserve_bytes=START_FREE_ABOVE_RESERVE_BYTES,
                      required_free_bytes=required, cohort_raw_reservation_bytes=COHORT_RAW_RESERVATION_BYTES,
                      body_cap_bytes=BODY_CAP_BYTES, probed=['private receipt directory', 'public receipt directory'],
                      observed_free_bytes=None, observed_public_free_bytes=None, probe_error=None, passed=False,
                      sends_per_query_attempt=self.sends_per_query_attempt, accounting_fixture=self.accounting_fixture)
        for field, path in (('observed_free_bytes', self.store.private_dir),
                            ('observed_public_free_bytes', self.store.public_dir)):
            try:
                record[field] = int(self._free(path))
            except (KeyboardInterrupt, SystemExit):
                raise
            except TimeoutError:
                raise                              # the episode deadline, before any episode work
            except Exception as exc:  # noqa: BLE001  an unmeasurable disk fails the preflight
                record['probe_error'] = '%s (%s)' % (type(exc).__name__, field)
                break
        record['passed'] = (record['probe_error'] is None and record['observed_free_bytes'] is not None
                            and record['observed_public_free_bytes'] is not None
                            and record['observed_free_bytes'] >= required
                            and record['observed_public_free_bytes'] >= required)
        if not record['passed']:
            refusal = self._register('insufficient_free_space_at_start', free_space=record,
                                     detail='start preflight failed; no episode work may begin')
            raise StartPreflightRefused('DTR-REQ-005 start preflight refused: less than 6 GiB free above the '
                                        'host reserve, or free space could not be measured', refusal=refusal)
        return record

    def _check_space(self, *, raw_bytes, public_bytes):
        """Recheck before a write: free space minus the reserve must cover the bytes about to be written. The
        public side also reserves one maximum-size outcome record when a request is written."""
        private_dir, public_dir = self.store.private_dir, self.store.public_dir
        needs = [(private_dir, raw_bytes), (public_dir, public_bytes)]
        try:
            same = os.stat(private_dir).st_dev == os.stat(public_dir).st_dev
        except OSError:
            same = False
        if same:
            needs = [(private_dir, raw_bytes + public_bytes)]
        observations = []
        for path, needed in needs:
            obs = dict(directory='private' if path == private_dir else 'public', bytes_to_write=needed,
                       host_reserve_bytes=self.host_reserve_bytes, required_free_bytes=self.host_reserve_bytes + needed,
                       observed_free_bytes=None, probe_error=None)
            try:
                obs['observed_free_bytes'] = int(self._free(path))
            except (KeyboardInterrupt, SystemExit, TimeoutError):
                raise
            except Exception as exc:  # noqa: BLE001
                obs['probe_error'] = type(exc).__name__
            observations.append(obs)
            if obs['observed_free_bytes'] is None or obs['observed_free_bytes'] < obs['required_free_bytes']:
                raise _SpaceShortfall(dict(rule=STORAGE_RULE, checks=observations))
        return dict(rule=STORAGE_RULE, checks=observations)

    def _space_for_public(self, *, raw_bytes, public_bytes):
        self._check_space(raw_bytes=raw_bytes, public_bytes=public_bytes)

    # -- refusals ---------------------------------------------------------
    def _register(self, code, *, wire=None, body=None, detail=None, free_space=None, attempt_key=None):
        classification, infra, meaning = REFUSALS[code]
        scope = self._scope
        files_present = None
        if attempt_key is not None:
            try:
                files_present = sorted(p.name for p in (self.store.raw_path(attempt_key),
                                                        self.store.record_path(attempt_key)) if p.exists())
            except OSError:
                files_present = None
        refusal = dict(
            refusal_ordinal=len(self.refusals) + 1, reason_code=code, classification=classification,
            infrastructure_stop=infra, meaning=meaning,
            logical_call_id=scope['logical_call_id'] if scope else None,
            query_attempt_id=scope['query_attempt'] if scope else None,
            send_index_in_query_attempt=len(scope['sends']) + 1 if scope else None,
            attempt_key=attempt_key,
            receipt_files_present=files_present,
            receipt_files_note=(None if attempt_key is None else
                                'files already written under this attempt key belong to a request that was NOT '
                                'dispatched; completeness() lists them as refused before dispatch'),
            body_sha256=sha256_hex(body) if body is not None else None,
            body_bytes=len(body) if body is not None else None,
            body_digest_status=('sha256 and length of the exact finalized body bytes' if body is not None else
                                'no body digest: the body was not read or no body was involved'),
            body_cap_bytes=BODY_CAP_BYTES, wire=wire, free_space=free_space,
            detail=None if detail is None else RR.sanitize(str(detail), self.store.home,
                                                            field='detail')[0][:DETAIL_CHARS],
            physical_request=False, dispatched_to_terminal=False, body_truncated=False, retried_by_capture=False,
            recorded_utc=RR.utc(self.clock()))
        self.refusals.append(refusal)
        if scope is not None:
            scope['refusals'].append(refusal)
        if infra and self._stopped is None:
            self._stopped = refusal
        written, error, deadline = False, None, None
        try:
            self.store.record_refusal(refusal, before_write=self._space_for_public)
            written = True
        except (KeyboardInterrupt, SystemExit):
            raise
        except TimeoutError as exc:
            error, deadline = 'interrupted by the episode deadline (%s)' % type(exc).__name__, exc
            self._note_deadline(exc, 'refusal_record_write')
        except _SpaceShortfall:
            error = 'insufficient_free_space'
        except Exception as exc:  # noqa: BLE001  storage may be the very thing that failed
            error = type(exc).__name__
        refusal['record_written'], refusal['record_error'] = written, error
        if deadline is not None and not self._in_dispatch:
            raise deadline                          # outside a dispatch scope the deadline propagates at once
        return refusal

    def _refuse(self, code, **kw):
        refusal = self._register(code, **kw)
        raise PreDispatchRefusal('DTR-REQ-005 %s refusal before dispatch (%s); no physical request was made'
                                 % (refusal['classification'], code), refusal=refusal)

    def _stop(self, code, *, detail=None, result=None):
        refusal = self._register(code, detail=detail)
        return InfrastructureStop('DTR-REQ-005 infrastructure stop (%s)' % code, refusal=refusal, result=result)

    def refuse_infrastructure(self, code, detail=None):
        """Record a non-send infrastructure refusal (e.g. install preflight) and return the stop to raise."""
        return self._stop(code, detail=detail)

    @property
    def stopped(self):
        return self._stopped

    # -- the send path ----------------------------------------------------
    def forward(self, *, body, wire, replayable, stream_bytes, send):
        """Check, persist, then send ONE physical request; returns send()'s response. Used by CapturingTransport.

        `body` is what request.read() returned, `stream_bytes` what the stream the terminal will iterate yields,
        and `send()` passes the unchanged request object to the inner transport."""
        scope = self._scope
        known = bytes(body) if replayable and isinstance(body, (bytes, bytearray)) else None
        if self._stopped is not None:
            self._refuse('infrastructure_stop_latched', wire=wire, body=known)
        if self._deadline_exc is not None:
            self._refuse('episode_deadline_latched', wire=wire, body=known)
        if scope is None:
            self._refuse('no_open_query_attempt', wire=wire, body=known)
        if known is None:
            self._refuse('non_replayable_body', wire=wire,
                         detail='body stream is not an in-memory byte stream; it was refused unread')
        if stream_bytes is None or bytes(stream_bytes) != known:
            self._refuse('stream_body_mismatch', wire=wire, body=known)
        declared = (wire or {}).get('content_length')
        if declared is not None and declared != len(known):
            self._refuse('content_length_mismatch', wire=wire, body=known)
        if len(scope['sends']) >= self.sends_per_query_attempt:
            self._refuse('query_attempt_send_limit', wire=wire, body=known)
        if self.budget.remaining() <= 0:
            self._refuse('cohort_request_budget_exhausted', wire=wire, body=known)
        if len(known) > BODY_CAP_BYTES:
            self._refuse('body_over_cap', wire=wire, body=known)
        logical = scope['logical_call_id']
        physical = self._physical_by_call.get(logical, 0) + 1
        key = RR.attempt_key(logical, physical)
        ordinal = self.budget.used + 1
        send_meta = dict(query_attempt_id=scope['query_attempt'], send_index_in_query_attempt=len(scope['sends']) + 1,
                         sends_per_query_attempt_limit=self.sends_per_query_attempt,
                         accounting_fixture=self.accounting_fixture,
                         cohort_request_ordinal=ordinal, cohort_request_limit=self.budget.limit,
                         body_cap_bytes=BODY_CAP_BYTES, storage_rule=STORAGE_RULE, wire=wire)
        space = {}

        def before_write(*, raw_bytes, public_bytes):
            space.update(self._check_space(raw_bytes=raw_bytes, public_bytes=public_bytes + PUBLIC_RECORD_CAP_BYTES))
        try:
            self.store.record_request(logical_call_id=logical, physical_attempt_id=physical, serialized=known,
                                      send=send_meta, before_write=before_write)
        except _SpaceShortfall as exc:
            self._refuse('insufficient_free_space', wire=wire, body=known, free_space=exc.observation)
        except _ReceiptOverCap as exc:
            self._refuse('public_receipt_over_cap', wire=wire, body=known, detail=str(exc))
        except (KeyboardInterrupt, SystemExit):
            raise
        except TimeoutError as exc:                 # the episode deadline mid-write is not a storage failure
            self.interrupted_writes.append(dict(attempt_key=key, error_class=type(exc).__name__,
                                                phase='pre_dispatch_write'))
            self._note_deadline(exc, 'pre_dispatch_write')
            self._refuse('episode_deadline_during_write', wire=wire, body=known, attempt_key=key,
                         detail='%s interrupted the durable pre-dispatch write' % type(exc).__name__)
        except RR.ReceiptError as exc:
            self._refuse('receipt_contract_refused', wire=wire, body=known, attempt_key=key,
                         detail='%s: %s' % (type(exc).__name__, exc))
        except OSError as exc:
            self._refuse('durable_write_failed', wire=wire, body=known, attempt_key=key,
                         detail='%s during the durable pre-dispatch write' % type(exc).__name__)
        except Exception as exc:  # noqa: BLE001
            self._refuse('receipt_internal_error', wire=wire, body=known, attempt_key=key,
                         detail='%s while building the pre-dispatch receipt' % type(exc).__name__)
        self._physical_by_call[logical] = physical
        consumed = self.budget.consume()
        ticket = dict(attempt_key=key, logical_call_id=logical,
                      physical_attempt_id=physical, query_attempt_id=scope['query_attempt'],
                      send_index_in_query_attempt=send_meta['send_index_in_query_attempt'],
                      cohort_request_ordinal=consumed, body_sha256=sha256_hex(known), body_bytes=len(known),
                      free_space=space, transport_state='forwarded_to_inner_transport', http_status=None,
                      transport_exception_class=None, response=None)
        scope['sends'].append(ticket)
        self.sends.append(ticket)
        try:
            response = send()
        except BaseException as exc:
            ticket.update(transport_state='transport_exception', transport_exception_class=type(exc).__name__)
            if isinstance(exc, TimeoutError):
                self._note_deadline(exc, 'inner_transport_send')
            raise
        try:
            ticket.update(transport_state='response_received', http_status=int(response.status_code),
                          response=response)
        except (KeyboardInterrupt, SystemExit):
            raise
        except TimeoutError as exc:
            self._note_deadline(exc, 'transport_response_note')
        except Exception as exc:  # noqa: BLE001  never lose the response over bookkeeping
            self._bookkeeping_failure(attempt_key=ticket['attempt_key'], phase='transport_response_note', exc=exc)
        return response

    # -- one logical query attempt ----------------------------------------
    def _query_identity_problem(self, logical_call_id, query_attempt):
        for name, value, upper in (('logical call id', logical_call_id, self.horizon),
                                   ('query attempt', query_attempt, self.attempts_per_call)):
            if type(value) is not int or not 1 <= value <= upper:
                return '%s %r outside 1..%d' % (name, value, upper)
        last = self._last_query
        if last is None:
            expected = [(1, 1)]
        else:
            expected = [(last[0] + 1, 1)] + ([(last[0], last[1] + 1)] if last[1] < self.attempts_per_call else [])
        if (logical_call_id, query_attempt) not in expected:
            return ('query (call %d, attempt %d) after %s; the next dispatch must be one of %s'
                    % (logical_call_id, query_attempt, 'none' if last is None else 'call %d attempt %d' % last,
                       ', '.join('call %d attempt %d' % pair for pair in expected)))
        return None

    def dispatch(self, *, logical_call_id, query_attempt, call):
        """Run ONE logical query attempt (one `litellm.completion` invocation) under the one-send rule.

        Returns call()'s result, or re-raises its original exception. A storage, measurement, budget or protocol
        refusal inside the attempt becomes InfrastructureStop. Outcome bookkeeping never changes the result. The
        episode deadline, once seen anywhere inside the attempt, is re-raised (the same object) after the attempt's
        evidence is recorded."""
        if self._deadline_exc is not None:
            raise self._deadline_exc
        if self._stopped is not None:
            raise InfrastructureStop('DTR-REQ-005 infrastructure stop is latched (%s); no query is dispatched'
                                     % self._stopped['reason_code'], refusal=self._stopped)
        if self._scope is not None or self._in_dispatch:
            raise self._stop('nested_query_attempt')
        problem = self._query_identity_problem(logical_call_id, query_attempt)
        if problem is not None:
            raise self._stop('invalid_query_identity', detail=problem)
        self._last_query = (logical_call_id, query_attempt)
        scope = dict(logical_call_id=logical_call_id, query_attempt=query_attempt, sends=[], refusals=[],
                     started_utc=RR.utc(self.clock()))
        self._in_dispatch = True
        self._scope = scope
        try:
            try:
                result = call()
            except BaseException as exc:
                self._scope = None
                if isinstance(exc, TimeoutError) and self._deadline_exc is None:
                    self._note_deadline(exc, 'query_attempt')
                self._close(scope, exc)
                if isinstance(exc, Exception):
                    stop = self._stop_after(scope, exc)
                    if self._deadline_exc is not None:
                        if self._deadline_exc is exc:
                            raise
                        raise self._deadline_exc from exc
                    if stop is not None:
                        raise stop from exc
                raise
            self._scope = None
            self._close(scope, None)
            stop = self._stop_after(scope, None, result)
            if self._deadline_exc is not None:
                raise self._deadline_exc
            if stop is not None:
                raise stop
            return result
        finally:
            self._scope = None
            self._in_dispatch = False

    def _stop_after(self, scope, exc, result=None):
        infra = [r for r in scope['refusals'] if r['infrastructure_stop']]
        if infra:
            return InfrastructureStop('DTR-REQ-005 infrastructure stop (%s); no physical request was made for it'
                                      % infra[0]['reason_code'], refusal=infra[0], result=result)
        violations, unverifiable = [], None
        try:
            violations = list(self.binding_check()) if self.binding_check is not None else []
        except (KeyboardInterrupt, SystemExit):
            raise
        except TimeoutError as check_exc:           # the deadline, not a binding problem
            self._note_deadline(check_exc, 'session_binding_check')
            return None
        except Exception as check_exc:  # noqa: BLE001
            unverifiable = 'binding check raised %s' % type(check_exc).__name__
        if unverifiable is not None:
            return self._stop('client_session_binding_unverifiable', detail=unverifiable, result=result)
        if violations:
            return self._stop('client_session_bypassed', detail='; '.join(violations), result=result)
        if exc is None and not scope['sends']:
            return self._stop('uncaptured_success', result=result)
        return None

    def _close(self, scope, exc):
        """Outcome records for every captured send of the attempt, then the attempt summary. Raises only an operator
        abort; a deadline is recorded (and latched) and the remaining evidence is still written."""
        failures_before = len(self.bookkeeping_failures)
        for index, ticket in enumerate(scope['sends']):
            last = index == len(scope['sends']) - 1
            try:
                self._record_send_outcome(ticket, scope=scope, last=last, exc=exc)
            except (KeyboardInterrupt, SystemExit):
                raise
            except TimeoutError as record_exc:
                self.interrupted_writes.append(dict(attempt_key=ticket['attempt_key'],
                                                    error_class=type(record_exc).__name__,
                                                    phase='post_dispatch_outcome'))
                self._note_deadline(record_exc, 'post_dispatch_outcome')
            except Exception as record_exc:  # noqa: BLE001  nonfatal by the lead's answer 2
                self._bookkeeping_failure(attempt_key=ticket['attempt_key'], phase='post_dispatch_outcome',
                                          exc=record_exc)
        try:
            self.attempts.append(dict(
                logical_call_id=scope['logical_call_id'], query_attempt_id=scope['query_attempt'],
                attempt_keys=[t['attempt_key'] for t in scope['sends']],
                physical_sends=len(scope['sends']),
                transport_attempted=bool(scope['sends']),
                response_received=any(t['transport_state'] == 'response_received' for t in scope['sends']),
                http_statuses=[t['http_status'] for t in scope['sends']],
                refused_before_dispatch=[r['reason_code'] for r in scope['refusals']],
                infrastructure_stop=any(r['infrastructure_stop'] for r in scope['refusals']),
                call_outcome='returned' if exc is None else 'raised',
                exception_class=None if exc is None else type(exc).__name__,
                bookkeeping_failures=len(self.bookkeeping_failures) - failures_before,
                started_utc=scope['started_utc'], ended_utc=RR.utc(self.clock())))
        except (KeyboardInterrupt, SystemExit):
            raise
        except TimeoutError as summary_exc:
            self._note_deadline(summary_exc, 'attempt_summary')
        except Exception as summary_exc:  # noqa: BLE001
            self._bookkeeping_failure(attempt_key=None, phase='attempt_summary', exc=summary_exc)
        for ticket in scope['sends']:
            ticket['response'] = None          # release the response object once its evidence is recorded

    def _record_send_outcome(self, ticket, *, scope, last, exc):
        content = _response_body(ticket['response']) if ticket['response'] is not None else None
        parsed = _server_reported(content)
        usage = _usage_from(parsed)
        suppressed = [r['refusal_ordinal'] for r in scope['refusals'] if r['reason_code'] == 'query_attempt_send_limit']
        if last and exc is None:
            ok, error_class, detail = True, None, None
        elif last:
            ok, error_class, detail = False, type(exc).__name__, str(exc)
        else:
            ok = False
            error_class = ticket['transport_exception_class'] or 'SupersededBySameAttemptResend'
            detail = ('a later physical send in the same query attempt followed this one; transport-observed http '
                      'status %s' % ticket['http_status'])
        origin = None
        if last and exc is not None:
            origin = ('hidden_resend_suppressed: the caller\'s exception follows the refusal of a further send in '
                      'this query attempt (refusal %s); the server\'s own response to this send is server_http_status'
                      % suppressed) if suppressed else 'the exception observed by the caller of this query attempt'
        send = dict(query_attempt_id=ticket['query_attempt_id'],
                    send_index_in_query_attempt=ticket['send_index_in_query_attempt'],
                    cohort_request_ordinal=ticket['cohort_request_ordinal'],
                    transport_state=ticket['transport_state'],
                    transport_exception_class=ticket['transport_exception_class'],
                    http_status_source='status of the response object returned by the inner transport',
                    server_http_status=ticket['http_status'],
                    server_error=_server_error_from(parsed),
                    caller_exception_origin=origin,
                    hidden_resend_suppressed_refusals=suppressed,
                    superseded_by_later_send=not last,
                    response_body_available=content is not None,
                    response_body_bytes=None if content is None else len(content),
                    response_body_sha256=None if content is None else sha256_hex(content),
                    usage_source=usage['source'],
                    finish_reason_source='choices[0].finish_reason of the server response body')

        def before_write(*, raw_bytes, public_bytes):
            self._check_space(raw_bytes=raw_bytes, public_bytes=public_bytes)
        self.store.record_outcome(logical_call_id=ticket['logical_call_id'],
                                  physical_attempt_id=ticket['physical_attempt_id'], ok=ok, error_class=error_class,
                                  error_detail=detail, usage=usage, finish_reason=_finish_reason_from(parsed),
                                  http_status=ticket['http_status'], send=send, before_write=before_write)

    # -- bookkeeping failures ---------------------------------------------
    def _bookkeeping_failure(self, *, attempt_key, phase, exc):
        failure = dict(attempt_key=attempt_key, phase=phase, error_class=type(exc).__name__,
                       detail=RR.sanitize(str(exc), self.store.home, field='detail')[0][:DETAIL_CHARS],
                       consequence='the evidence for this attempt is incomplete; the model result is unchanged, '
                                   'usage is not fabricated and nothing is re-sent',
                       recorded_utc=RR.utc(self.clock()), secondary_log_written=False, secondary_log_error=None)
        self.bookkeeping_failures.append(failure)
        try:
            line = (json.dumps(dict(failure, note=SECONDARY_LOG_NOTE), sort_keys=True) + '\n').encode('utf-8')
            line = line if len(line) <= BOOKKEEPING_LINE_MAX_BYTES else (json.dumps(dict(
                attempt_key=attempt_key, phase=phase, error_class=type(exc).__name__[:BOUNDED_TEXT_CHARS],
                note='line bounded: detail omitted'), sort_keys=True) + '\n').encode('utf-8')
            self._check_space(raw_bytes=len(line), public_bytes=0)
            path = Path(self.store.private_dir) / BOOKKEEPING_LOG
            with open(path, 'ab') as fh:
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())
            failure['secondary_log_written'] = True
        except (KeyboardInterrupt, SystemExit):
            raise
        except TimeoutError as log_exc:
            failure['secondary_log_error'] = 'interrupted by the episode deadline'
            self._note_deadline(log_exc, 'secondary_log')
        except _SpaceShortfall:
            failure['secondary_log_error'] = 'insufficient_free_space'
        except Exception as log_exc:  # noqa: BLE001
            failure['secondary_log_error'] = type(log_exc).__name__
        if self.on_receipt_error is not None:
            try:
                self.on_receipt_error(dict(failure))
            except (KeyboardInterrupt, SystemExit):
                raise
            except TimeoutError as callback_exc:
                self._note_deadline(callback_exc, 'receipt_error_callback')
            except Exception as callback_exc:  # noqa: BLE001  reporting must not replace the real call result
                self.bookkeeping_failures.append(dict(
                    attempt_key=attempt_key, phase='receipt_error_callback', error_class=type(callback_exc).__name__,
                    detail=str(callback_exc)[:DETAIL_CHARS], consequence='callback failed; result unchanged',
                    recorded_utc=RR.utc(self.clock()), secondary_log_written=None, secondary_log_error=None))

    # -- integrity --------------------------------------------------------
    def frozen_path_parity(self):
        """Where this capture's observable behaviour may differ from litellm's frozen default client: a suppressed
        hidden resend (litellm second pass, SDK retry or redirect hop) and a redirect surfaced instead of followed."""
        suppressed = [dict(refusal_ordinal=r['refusal_ordinal'], logical_call_id=r['logical_call_id'],
                           query_attempt_id=r['query_attempt_id'])
                      for r in self.refusals if r['reason_code'] == 'query_attempt_send_limit']
        redirects = [dict(attempt_key=t['attempt_key'], http_status=t['http_status'])
                     for t in self.sends if isinstance(t['http_status'], int) and 300 <= t['http_status'] < 400]
        return dict(state='deviated' if suppressed or redirects else 'unchanged',
                    suppressed_hidden_resends=suppressed, redirects_surfaced_not_followed=redirects,
                    note='a deviation is reported for lead review; it is not an infrastructure stop by itself')

    def integrity(self):
        """Receipt integrity, kept separate from the episode's operational outcome."""
        try:
            store = self.store.completeness()
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:  # noqa: BLE001
            store = dict(complete=False, error=type(exc).__name__)
        reasons = []
        if self.bookkeeping_failures:
            reasons.append('post-dispatch bookkeeping failure(s): %d' % len(self.bookkeeping_failures))
        if self.interrupted_writes:
            reasons.append('write(s) interrupted by the episode deadline: %d' % len(self.interrupted_writes))
        if not store.get('complete'):
            reasons.append('the receipt set has holes or invalid records')
        unwritten = [r['refusal_ordinal'] for r in self.refusals if not r.get('record_written')]
        if unwritten:
            reasons.append('refusal record(s) not durably written: %s' % unwritten)
        return dict(receipt_integrity='complete' if not reasons else 'incomplete', reasons=reasons,
                    infrastructure_stop=self._stopped is not None,
                    stop_reason=None if self._stopped is None else self._stopped['reason_code'],
                    queue_may_continue=not reasons and self._stopped is None,
                    deadline_reached=self._deadline_exc is not None,
                    deadline_class=None if self._deadline_exc is None else type(self._deadline_exc).__name__,
                    deadline_events=list(self.deadline_events), deadline_note=DEADLINE_NOTE,
                    frozen_path_parity=self.frozen_path_parity(), accounting_fixture=self.accounting_fixture,
                    physical_sends=len(self.sends), refusals=len(self.refusals),
                    budget=dict(limit=self.budget.limit, used=self.budget.used),
                    bookkeeping_failures=[dict(f) for f in self.bookkeeping_failures], store=store)


# ---------------------------------------------------------------- httpx adapter and litellm installation

if httpx is not None:
    class CapturingTransport(httpx.BaseTransport):
        """The pinned client's outbound boundary: reads the finalized body, lets the capture persist it, then passes
        the SAME request object to the inner (terminal) transport."""

        def __init__(self, inner, capture):
            if not isinstance(capture, CueTransportCapture):
                raise TypeError('CapturingTransport requires a CueTransportCapture')
            self.inner, self.capture = inner, capture

        def handle_request(self, request):
            wire = wire_metadata(request.method, str(request.url), request.headers.multi_items())
            # exactly httpx.ByteStream: a subclass could yield different bytes on the terminal's own iteration
            replayable = type(request.stream) is httpx.ByteStream
            body = stream_bytes = None
            if replayable:
                body = request.read()          # read(), not .content: a redirect hop is not pre-read
                stream_bytes = b''.join(request.stream)
            return self.capture.forward(body=body, wire=wire, replayable=replayable, stream_bytes=stream_bytes,
                                        send=lambda: self.inner.handle_request(request))

        def close(self):
            self.inner.close()
else:  # pragma: no cover
    CapturingTransport = None


def _openai_client_types(client_types):
    if client_types is not None:
        return tuple(client_types)
    return (openai.OpenAI, openai.AsyncOpenAI) if openai is not None else ()


def cached_client_entries(litellm, client_types=None):
    """(openai-client keys, other entry type names) in litellm's in-memory client cache. At import litellm itself
    caches async HTTP handlers for other providers (vertex_ai, bedrock, logging); those are not on the traced
    sync openai path. Only a cached openai client would keep its old http client and bypass the session."""
    cache = getattr(getattr(litellm, 'in_memory_llm_clients_cache', None), 'cache_dict', None)
    if cache is None:
        return None, None
    types_ = _openai_client_types(client_types)
    clients = sorted(str(k)[:BOUNDED_TEXT_CHARS] for k, v in cache.items() if types_ and isinstance(v, types_))
    others = sorted({type(v).__name__ for v in cache.values() if not (types_ and isinstance(v, types_))})
    return clients, others


def litellm_preflight_problems(litellm, environ=None, proxies=None, client_types=None):
    """Every reason the pinned litellm path would not make exactly the frozen single send through our session.
    `proxies` defaults to urllib.request.getproxies() (environment first, then the system configuration);
    `client_types` defaults to (openai.OpenAI, openai.AsyncOpenAI)."""
    environ = os.environ if environ is None else environ
    problems = []
    if getattr(litellm, 'num_retries', None) is not None:
        problems.append('litellm.num_retries is %r; a global value overrides the frozen per-call num_retries=0'
                        % litellm.num_retries)
    if getattr(litellm, 'num_retries_per_request', None) is not None:
        problems.append('litellm.num_retries_per_request is set')
    if getattr(litellm, 'drop_params', False) is not False:
        problems.append('litellm.drop_params is not False; it enables the hidden 422 second pass')
    if getattr(litellm, 'network_mock', False):
        problems.append('litellm.network_mock is set')
    if getattr(litellm, 'route_all_chat_openai_to_responses', False):
        problems.append('litellm routes chat completions to the Responses bridge')
    if getattr(litellm, 'client_session', None) is not None:
        problems.append('a litellm client_session is already installed')
    for name in ('EXPERIMENTAL_OPENAI_BASE_LLM_HTTP_HANDLER', 'LITELLM_ROUTE_ALL_CHAT_OPENAI_TO_RESPONSES',
                 'LITELLM_DROP_PARAMS', 'LITELLM_NUM_RETRIES'):
        if environ.get(name):
            problems.append('environment variable %s is set' % name)
    clients, _others = cached_client_entries(litellm, client_types)
    if clients is None:
        problems.append('litellm client cache is not inspectable')
    elif clients:
        problems.append('litellm client cache holds %d openai client%s at install; a cached client keeps its old '
                        'http client' % (len(clients), '' if len(clients) == 1 else 's'))
    found = urllib.request.getproxies() if proxies is None else proxies
    found = sorted(k for k in found if k != 'no')
    if found:
        problems.append('environment/system proxies %s would route the frozen default client differently' % found)
    return problems


def session_binding_violations(litellm, session, client_types=None):
    """Every cached openai client must wrap the capture session, or a send could bypass the receipts.
    `client_types` defaults to (openai.OpenAI, openai.AsyncOpenAI) in the pinned venv."""
    violations = []
    if getattr(litellm, 'client_session', None) is not session:
        violations.append('litellm.client_session is not the capture session')
    cache = getattr(getattr(litellm, 'in_memory_llm_clients_cache', None), 'cache_dict', {}) or {}
    client_types = _openai_client_types(client_types)
    for value in list(cache.values()):
        if client_types and isinstance(value, client_types) and getattr(value, '_client', None) is not session:
            violations.append('a cached %s does not wrap the capture session' % type(value).__name__)
    return violations


def install_litellm_session(litellm, capture, *, inner=None):
    """Install the capture at litellm's own hook, before the first completion of the episode process.

    `inner` defaults to the terminal litellm would have built: httpx.HTTPTransport(verify=get_ssl_configuration()).
    Refuses (InfrastructureStop, recorded) when the preflight finds any hidden-send path or a pre-cached client.
    Returns (session, install receipt)."""
    if httpx is None:
        raise RuntimeError('install_litellm_session needs httpx (the pinned mini-swe-agent venv)')
    problems = litellm_preflight_problems(litellm)
    if problems:
        raise capture.refuse_infrastructure('install_preflight_failed', detail='; '.join(problems))
    if inner is None:
        from litellm.llms.custom_httpx.http_handler import get_ssl_configuration
        inner = httpx.HTTPTransport(verify=get_ssl_configuration())
    receipt = dict(hook='litellm.client_session', follow_redirects=False, inner_transport=type(inner).__name__,
                   sends_per_query_attempt=capture.sends_per_query_attempt, preflight_problems=problems,
                   litellm_num_retries=getattr(litellm, 'num_retries', None),
                   litellm_drop_params=getattr(litellm, 'drop_params', None),
                   environment_proxies=sorted(k for k in urllib.request.getproxies() if k != 'no'),
                   client_cache_entries_at_install=len(litellm.in_memory_llm_clients_cache.cache_dict),
                   client_cache_openai_clients_at_install=cached_client_entries(litellm)[0],
                   client_cache_other_entry_types_at_install=cached_client_entries(litellm)[1])
    session = httpx.Client(transport=CapturingTransport(inner, capture), follow_redirects=False)
    litellm.client_session = session
    capture.binding_check = lambda: session_binding_violations(litellm, session)
    return session, receipt
