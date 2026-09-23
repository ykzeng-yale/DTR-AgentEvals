"""DTR-REQ-005 pre-dispatch request receipts (lead answer 5, docs/theory_feedback_20260923_completed_pilots.md).

The two completed DEV cohorts logged attempt *accounting* (pilot_episode.append_attempt) but never the request
itself, so no exact wire payload or tokenizer attribution exists for them. This module implements the lead's
answer 5 for the NEW cohort namespace only; the frozen yaml-v1 sources and archives are untouched, and nothing
here recovers the past missing request bodies.

Declared rule (implemented exactly, nothing more):
  * BEFORE dispatch, the exact serialized request bytes are written to a PRIVATE worker-local file under `work/`
    (git-ignored, never published) together with their raw sha256, the logical call id, the physical attempt id,
    and the model / decoding / server / tokenizer identity. Any preflight token count is recorded ONLY together
    with the method that produced it; a bare number is refused, and so is any extra field that could read as a
    verification claim.
  * A separately hashed SANITIZED projection is published, carrying explicit transformation metadata (which field
    was transformed, how many occurrences, and why). EVERY transformation is listed, including the bounded
    truncation of an error detail. The projection's digest is `published_projection_sha256`; the raw bytes'
    digest is `raw_request_sha256`. They are distinct names over distinct byte sequences, and the record states
    `raw_request_equality = 'reported_unverified'` -- mirroring `published_projection_verified` vs
    `reported_unverified` in publication_manifest.py. The projection digest is NEVER presented as the raw digest.
  * A failed or rejected request (transport error, context-window rejection) keeps the SAME durable pre-dispatch
    record plus a linked write-once outcome record with its error class, its finish reason, its HTTP status and
    whatever usage the server did report. Nothing is dropped because a call failed.
  * Unknown server-side token usage stays explicitly unknown (None/null) and is never coerced to 0. A total the
    server DID report is retained as reported, and a disagreement with the reported pair is recorded rather than
    silently overwritten.
  * Every record is write-once: an existing path is refused, never overwritten. Both files of an attempt are
    fully serialized BEFORE either is written, so a serialization failure cannot burn an attempt key and leave a
    dispatched request with no published receipt. `RequestReceiptStore.completeness()` lists any remaining hole
    so a reader never takes subtotals over a set with skipped records.
  * Receipt bookkeeping never changes an episode's outcome. `recorded_dispatch` persists the request before
    dispatch (a failure there aborts before any model call, which is the point), but a failure while recording
    the OUTCOME neither replaces the real dispatch exception nor aborts a call that already succeeded: it is
    reported through `dispatch.receipt_errors` / `on_receipt_error` and shows up in `completeness()`.

This module records; it does not change model-visible messages, decoding, H, context, the endpoint or any pin.
The cohort/namespace name is supplied by the caller (frozen at release), not chosen here.

Sanitization is deliberately broad on the published side: credential-looking KEYS, credential-looking
assignments inside free text and `sk-` style literals are withheld wherever they appear, including inside
lists. Over-masking a published projection is recoverable (the private raw request keeps the exact bytes);
publishing a credential is not. The published projection is NOT byte-bounded -- its size is recorded in
`payload_projection_bytes`, and the accumulated-transcript volume needs the lead's explicit approval before
live release.
"""
from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import os
import re
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRIVATE_ROOT = ROOT / 'work/req005_request_receipts'      # git-ignored (work/); never created at import time
HOME_PLACEHOLDER = '<HOME>'
WITHHELD = '<WITHHELD>'
# Credential-looking key NAMES. SECRET_KEY matches as a substring; TOKEN_KEY must match the WHOLE key, so
# `token`/`Token`/`TOKEN`/`access_token` are withheld while a count field like `max_tokens` is not.
SECRET_KEY = re.compile(r'api[_-]?key|authoriz|auth[_-]?token|bearer|password|passwd|secret|credential|cookie', re.I)
TOKEN_KEY = re.compile(r'(?:x[-_])?(?:api[-_])?(?:access|refresh|auth|session|bearer|id)?[-_]?token', re.I)
# Credential-looking VALUES inside free text, e.g. a header string in a list. The masked value is the
# assigned token (with an explicit `Bearer ` prefix when present), not the rest of the sentence: withholding
# the credential must not erase the surrounding evidence the lead reads.
SECRET_ASSIGNMENT = re.compile(
    r'(?i)\b((?:proxy[-_])?authorization|x[-_]api[-_]?key|api[-_]?key|auth[-_]?token|access[-_]?token'
    r'|refresh[-_]?token|bearer|password|passwd|secret|credential|cookie|token)'
    r'(\s*[:=]\s*)(?:"[^"\n]*"|\'[^\'\n]*\'|(?:bearer\s+)?[^\s"\',]+)')
SECRET_LITERAL = re.compile(r'\bsk-[A-Za-z0-9][A-Za-z0-9_\-]{5,}')
RAW_SUFFIX = '.request.raw'
PUBLIC_SUFFIX = '.request.json'
OUTCOME_SUFFIX = '.outcome.json'
RAW_DIGEST_FIELD = 'raw_request_sha256'
PROJECTION_DIGEST_FIELD = 'published_projection_sha256'
REPORTED_UNVERIFIED = 'reported_unverified'
ERROR_DETAIL_CHARS = 300
PREFLIGHT_FIELDS = ('value', 'method', 'status')
PROJECTION_BOUND = ('unbounded: the full sanitized payload is published, so a long accumulated transcript is '
                    'published in full; the published volume needs explicit lead approval before live release')

IDENTITY_REQUIRED = (('model', ('alias', 'model_sha256')), ('decoding', ('temperature', 'max_tokens')),
                     ('server', ('endpoint',)), ('tokenizer', ('source',)))

DIGEST_SEMANTICS = {
    RAW_DIGEST_FIELD: 'sha256 over the exact serialized request bytes, which are retained privately under work/ '
                      'and are not published in this record',
    PROJECTION_DIGEST_FIELD: 'sha256 over this published sanitized projection only; sanitization changed the bytes, '
                             'so this digest is a different byte sequence and must never be presented as the raw '
                             'request digest',
    'raw_request_equality': 'reported_unverified: a reader of the published projection cannot verify equality to the '
                            'absent raw bytes, nor that the only transformations applied were the ones listed',
}
UNKNOWN_USAGE_NOTE = ('server-reported usage that the server did not report stays null; it is never coerced to 0, '
                      'and a total is not derived from a partially unknown pair')
SANITIZATION_SCOPE = ('The published projection is derived from the private raw request by the listed '
                      'transformations only. Matching its digest verifies the published bytes; it does not '
                      'authenticate the absent raw bytes or prove the stated transformation.')
COMPLETENESS_NOTE = ('A published receipt set with a hole is a pattern formed by skipping incomplete records: '
                     'do not report subtotals over it without this list')
HOME_MASKING_DISABLED = 'disabled: no home prefix was declared, so no path prefix was masked'
HOME_MASKING_ENABLED = 'enabled: the declared home prefix is replaced at path-component boundaries only'

_UNSET = object()


class ReceiptError(RuntimeError):
    """A receipt contract violation: refuse rather than record something unverifiable."""


# ---------------------------------------------------------------- digests and write-once files

def sha256_hex(data):
    if not isinstance(data, (bytes, bytearray)):
        raise ReceiptError('a raw request digest is computed over exact bytes only')
    return hashlib.sha256(bytes(data)).hexdigest()


def canonical_bytes(payload):
    try:
        return json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    except (TypeError, ValueError) as exc:
        raise ReceiptError('receipt payload is not JSON-serializable: %s' % exc) from exc


def canonical_sha256(payload):
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def sealed(payload, field=PROJECTION_DIGEST_FIELD):
    """payload plus its own canonical digest under `field`; the digest never covers itself."""
    if field in payload:
        raise ReceiptError('receipt payload already carries %s' % field)
    return dict(payload, **{field: canonical_sha256(payload)})


def _write_once(path, data):
    """Durable write-once: refuses an existing path instead of overwriting it."""
    path = Path(path)
    mode = 'xb' if isinstance(data, (bytes, bytearray)) else 'x'
    try:
        fh = open(path, mode)
    except FileExistsError as exc:
        raise ReceiptError('write-once receipt already exists; refusing to overwrite %s' % path.name) from exc
    with fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    return path


def utc(t=None):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t))


def attempt_key(logical_call_id, physical_attempt_id):
    for name, value in (('logical call id', logical_call_id), ('physical attempt id', physical_attempt_id)):
        if type(value) is not int or value < 1:
            raise ReceiptError('%s must be a positive integer; receipt ids are never inferred' % name)
    return 'call%03d_attempt%02d' % (logical_call_id, physical_attempt_id)


# ---------------------------------------------------------------- token counts (never a bare number)

def preflight_token_count(value, method):
    """A preflight count is only ever recorded together with the method that produced it."""
    if not isinstance(method, str) or not method.strip():
        raise ReceiptError('a preflight token count requires the method used to obtain it; a bare number is refused')
    if type(value) is not int or value < 0:
        raise ReceiptError('a preflight token count must be a non-negative integer')
    return dict(value=value, method=method.strip(),
                status='worker-side preflight count; not a server-verified tokenization of the dispatched bytes')


def _validated_preflight(preflight):
    if preflight is None:
        return dict(value=None, method=None, status='not obtained; no preflight token count exists for this attempt')
    if isinstance(preflight, dict):
        if 'value' not in preflight or 'method' not in preflight:
            raise ReceiptError('a preflight token count record requires both its value and its method')
        unexpected = sorted(set(preflight) - set(PREFLIGHT_FIELDS))
        if unexpected:
            raise ReceiptError('a preflight token count record carries only %s; refusing the extra field(s) %s, '
                               'which would be published as if this module had established them'
                               % (', '.join(PREFLIGHT_FIELDS), ', '.join(unexpected)))
        return preflight_token_count(preflight['value'], preflight['method'])
    raise ReceiptError('a preflight token count must carry its method; a bare number is refused')


def server_usage(prompt_tokens=None, completion_tokens=None, *, total_tokens=None, source=None):
    """Server-reported usage. Anything the server did not report stays None, never 0.

    A total the server DID report is retained as reported (`total_tokens_source='server_reported'`) even when
    the pair is unknown; a total that disagrees with the reported pair is recorded in `total_discrepancy`
    instead of being silently replaced."""
    fields = (('prompt_tokens', prompt_tokens), ('completion_tokens', completion_tokens))
    for name, value in fields + (('total_tokens', total_tokens),):
        if value is not None and (type(value) is not int or value < 0):
            raise ReceiptError('%s must be a non-negative integer or None (unknown)' % name)
    unknown = [name for name, value in fields if value is None]
    derived = None if unknown else prompt_tokens + completion_tokens
    discrepancy = None
    if total_tokens is not None:
        published, total_source = total_tokens, 'server_reported'
        if derived is not None and derived != total_tokens:
            discrepancy = dict(server_reported_total=total_tokens, sum_of_reported_pair=derived,
                               note='the server-reported total disagrees with the sum of the reported pair; '
                                    'both are retained and neither is silently replaced')
    elif derived is not None:
        published, total_source = derived, 'sum_of_reported_pair'
    else:
        published, total_source = None, None
    return dict(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens, total_tokens=published,
                total_tokens_source=total_source, reported_total_tokens=total_tokens,
                total_discrepancy=discrepancy, usage_known=not unknown, total_known=published is not None,
                unknown_fields=unknown, source=source, note=UNKNOWN_USAGE_NOTE)


USAGE_FIELDS = frozenset({'prompt_tokens', 'completion_tokens', 'total_tokens', 'total_tokens_source',
                          'reported_total_tokens', 'total_discrepancy', 'usage_known', 'total_known',
                          'unknown_fields', 'source', 'note'})


def _validated_usage(usage):
    if usage is None:
        return server_usage()
    if isinstance(usage, dict):
        unexpected = sorted(set(usage) - USAGE_FIELDS)
        if unexpected:
            raise ReceiptError('unexpected server usage field(s): %s' % ', '.join(unexpected))
        # `reported_total_tokens` is what the server itself reported; a derived `total_tokens` from a previous
        # server_usage() round trip is re-derived rather than re-labelled as server-reported.
        total = usage['reported_total_tokens'] if 'reported_total_tokens' in usage else usage.get('total_tokens')
        return server_usage(usage.get('prompt_tokens'), usage.get('completion_tokens'), total_tokens=total,
                            source=usage.get('source'))
    raise ReceiptError('server-reported usage must be a dict or None (unknown)')


# ---------------------------------------------------------------- sanitized projection

def validated_home(home):
    """The home prefix to mask. '' disables masking (recorded explicitly); a pathological prefix is refused."""
    if home is None:
        home = os.path.expanduser('~')
    if not isinstance(home, str):
        raise ReceiptError('the home prefix to mask must be a string, or the empty string to disable masking')
    if home == '':
        return ''
    trimmed = home.rstrip('/')
    if not trimmed.startswith('/') or trimmed.count('/') < 2:
        raise ReceiptError('refusing the home prefix %r: masking a filesystem root or a single top-level '
                           'component would corrupt every published path' % home)
    return trimmed


def _home_pattern(home):
    """Match the home prefix only at a path-component boundary, so '/Users/example' never mis-masks
    '/Users/example-worker2/...'."""
    return re.compile(re.escape(home) + r'(?![A-Za-z0-9._\-])') if home else None


def _mask_secrets_in_text(text, field, transformations):
    masked, assignments = SECRET_ASSIGNMENT.subn(lambda m: m.group(1) + m.group(2) + WITHHELD, text)
    masked, literals = SECRET_LITERAL.subn(WITHHELD, masked)
    if assignments or literals:
        transformations.append(dict(transformation='secret_value_masked_in_text', field=field,
                                    occurrences=assignments + literals, replacement=WITHHELD,
                                    why='a credential-looking value inside a text value must never appear in a '
                                        'published record, including inside a list; only the private raw '
                                        'request retains it'))
    return masked


def _mask_home(text, pattern, home, field, transformations):
    if pattern is None:
        return text
    masked, occurrences = pattern.subn(HOME_PLACEHOLDER, text)
    if not occurrences:
        return text
    transformations.append(dict(transformation='home_path_prefix_masked', field=field, occurrences=occurrences,
                                placeholder=HOME_PLACEHOLDER,
                                why="the worker's absolute home prefix identifies the host account and is not part "
                                    'of the request payload the model was shown; the private raw request keeps the '
                                    'exact bytes'))
    return masked


def is_secret_key(key):
    return bool(isinstance(key, str) and (SECRET_KEY.search(key) or TOKEN_KEY.fullmatch(key)))


def _sanitize(value, pattern, home, field, transformations):
    if isinstance(value, dict):
        out = {}
        for key, child in value.items():
            path = '%s.%s' % (field, key) if field else str(key)
            if is_secret_key(key):
                out[key] = WITHHELD
                transformations.append(dict(transformation='secret_value_withheld', field=path, replacement=WITHHELD,
                                            why='a credential/authorization value must never appear in a published '
                                                'record; only the private raw request retains it'))
            else:
                out[key] = _sanitize(child, pattern, home, path, transformations)
        return out
    if isinstance(value, (list, tuple)):
        return [_sanitize(item, pattern, home, '%s[%d]' % (field, i), transformations)
                for i, item in enumerate(value)]
    if isinstance(value, str):
        return _mask_home(_mask_secrets_in_text(value, field, transformations), pattern, home, field,
                          transformations)
    return value


def sanitize(value, home, *, field):
    """Return (sanitized value, transformations). Each transformation names the field and why it was applied."""
    transformations = []
    return _sanitize(value, _home_pattern(home), home, field, transformations), transformations


def payload_projection(raw, home, *, field='request_payload'):
    """(projection, status, available, transformations) for the serialized request.

    `available` is False whenever the projection was WITHHELD, so a consumer never has to read a null
    projection as an empty one."""
    try:
        parsed = json.loads(bytes(raw).decode())
    except (UnicodeDecodeError, ValueError):
        return None, ('unavailable: the serialized request is not decodable JSON; only its digest, size and the '
                      'private file reference are published'), False, [
            dict(transformation='payload_projection_withheld', field=field, replacement=None,
                 why='the raw request could not be parsed for sanitization, so no projection of its content is '
                     'published; the private raw request is retained in full')]
    projection, transformations = sanitize(parsed, home, field=field)
    return projection, 'sanitized projection of the serialized request payload', True, transformations


# ---------------------------------------------------------------- identity

def validate_identity(identity):
    """The lead's four identity classes are all required: model, decoding, server, tokenizer."""
    if not isinstance(identity, dict):
        raise ReceiptError('request identity must be a dict')
    required = dict(IDENTITY_REQUIRED)
    out = {}
    for group, keys in IDENTITY_REQUIRED:
        section = identity.get(group)
        if not isinstance(section, dict) or not section:
            raise ReceiptError("request identity requires a nonempty '%s' section (model/decoding/server/tokenizer "
                               'are all recorded before dispatch)' % group)
        missing = [key for key in keys if section.get(key) is None]
        if missing:
            raise ReceiptError('request identity %s is missing %s' % (group, ', '.join(missing)))
        out[group] = copy.deepcopy(section)
    for group in identity:
        if group not in required:
            out[group] = copy.deepcopy(identity[group])
    canonical_bytes(out)      # refuse now, not after the first raw request has been written
    return out


# ---------------------------------------------------------------- store

class RequestReceiptStore:
    """Write-once receipts for one episode: private raw requests under work/, published sanitized projections."""

    def __init__(self, private_dir, public_dir, *, cohort, identity, run_id=None, preflight=None, home=None,
                 clock=time.time, root=ROOT):
        if not isinstance(cohort, str) or not cohort.strip():
            raise ReceiptError('receipts require the cohort/namespace they belong to')
        private_dir, public_dir, root = Path(private_dir), Path(public_dir), Path(root)
        private_resolved, public_resolved, root_resolved = private_dir.resolve(), public_dir.resolve(), root.resolve()
        if private_resolved == public_resolved or private_resolved.is_relative_to(public_resolved) or \
                public_resolved.is_relative_to(private_resolved):
            raise ReceiptError('the private raw request directory must be separate from the published directory')
        if 'results' in private_resolved.parts:
            raise ReceiptError('raw request bytes are never written under a results/ tree: those records are '
                               'immutable published evidence, whatever root is declared')
        if private_resolved.is_relative_to(root_resolved) and not private_resolved.is_relative_to(root_resolved / 'work'):
            raise ReceiptError('raw request bytes stay worker-local under work/ (git-ignored); refusing a private '
                               'directory inside the published tree')
        self.cohort, self.run_id, self.clock = cohort.strip(), run_id, clock
        self.identity = validate_identity(identity)
        self.default_preflight = preflight
        self.home = validated_home(home)
        self.private_dir, self.public_dir = private_dir, public_dir
        self.private_dir.mkdir(parents=True, exist_ok=True)
        self.public_dir.mkdir(parents=True, exist_ok=True)
        inside_root = private_resolved.is_relative_to(root_resolved)
        self.private_root_label = (private_resolved.relative_to(root_resolved).as_posix() if inside_root
                                   else 'worker-local directory outside the repository')
        self.private_root_basis = ('relative to the declared repository root' if inside_root else
                                   'the declared repository root does not contain this directory; the label '
                                   'rests on the root declared by the caller, not on an inspection of the '
                                   'working tree')

    # -- paths ------------------------------------------------------------
    def raw_path(self, key):
        return self.private_dir / (key + RAW_SUFFIX)

    def record_path(self, key):
        return self.public_dir / (key + PUBLIC_SUFFIX)

    def outcome_path(self, key):
        return self.public_dir / (key + OUTCOME_SUFFIX)

    def _sanitization(self, transformations, *, home_applies=True):
        return dict(applied=bool(transformations), placeholder=HOME_PLACEHOLDER, withheld_marker=WITHHELD,
                    home_prefix_masked=bool(self.home) and home_applies,
                    home_masking=(HOME_MASKING_ENABLED if self.home else HOME_MASKING_DISABLED),
                    transformations=transformations, scope=SANITIZATION_SCOPE)

    def _common(self, key, logical_call_id, physical_attempt_id, phase):
        return dict(request='DTR-REQ-005', cohort=self.cohort, run_id=self.run_id, phase=phase,
                    logical_call_id=logical_call_id, physical_attempt_id=physical_attempt_id, attempt_key=key,
                    recorded_utc=utc(self.clock()))

    # -- pre-dispatch -----------------------------------------------------
    def record_request(self, *, logical_call_id, physical_attempt_id, serialized, preflight=_UNSET, identity=None):
        """Persist the exact request BEFORE dispatch: private raw bytes, then the published sanitized projection.

        Both files are fully serialized before either is written, so a serialization failure refuses the
        attempt outright instead of leaving a private raw with no publishable receipt."""
        key = attempt_key(logical_call_id, physical_attempt_id)
        if not isinstance(serialized, (bytes, bytearray)):
            raise ReceiptError('the serialized request must be the exact bytes that are dispatched')
        raw = bytes(serialized)
        record_preflight = _validated_preflight(self.default_preflight if preflight is _UNSET else preflight)
        ident = self.identity if identity is None else validate_identity(identity)
        raw_digest = sha256_hex(raw)
        public_identity, transformations = sanitize(ident, self.home, field='identity')
        projection, projection_status, projection_available, payload_transformations = payload_projection(
            raw, self.home)
        transformations = transformations + payload_transformations
        payload = dict(
            self._common(key, logical_call_id, physical_attempt_id, 'pre_dispatch'),
            kind='DTR-REQ-005 pre-dispatch request receipt (published sanitized projection)',
            dispatch_state='persisted_before_dispatch',
            **{RAW_DIGEST_FIELD: raw_digest},
            raw_request_bytes=len(raw),
            raw_request_private_file=self.raw_path(key).name,
            raw_request_private_root=self.private_root_label,
            raw_request_private_root_basis=self.private_root_basis,
            raw_request_published=False,
            identity=public_identity,
            preflight_token_count=record_preflight,
            server_reported_usage=None,
            server_reported_usage_status='not dispatched yet; unknown usage is never recorded as 0',
            payload_projection=projection,
            payload_projection_available=projection_available,
            payload_projection_status=projection_status,
            payload_projection_bytes=(len(canonical_bytes(projection)) if projection_available else None),
            payload_projection_bound=PROJECTION_BOUND,
            sanitization=self._sanitization(transformations),
            digest_semantics=DIGEST_SEMANTICS,
            raw_request_equality=REPORTED_UNVERIFIED,
            raw_bytes_independently_verified=False,
            sanitization_transform_independently_verified=False)
        record = sealed(payload)
        text = json.dumps(record, indent=1) + '\n'          # canonicalised and serialised before any write
        _write_once(self.raw_path(key), raw)                # the private raw bytes exist first, as declared
        _write_once(self.record_path(key), text)
        return record

    # -- post-dispatch ----------------------------------------------------
    def record_outcome(self, *, logical_call_id, physical_attempt_id, ok, error_class=None, error_detail=None,
                       usage=None, rejected_before_generation=None, finish_reason=None, http_status=None):
        """Write-once outcome linked to its durable pre-dispatch record. Failures keep the same durable record.

        The pre-dispatch record's own seal is re-verified and the retained raw bytes are re-hashed here, so the
        outcome can never carry a raw digest that the retained bytes contradict."""
        key = attempt_key(logical_call_id, physical_attempt_id)
        path = self.record_path(key)
        if not isinstance(ok, bool):
            raise ReceiptError('the outcome flag must be a bool; a truthy value is never recorded as success')
        verify_published_projection(path, expect_phase='pre_dispatch')
        try:
            pre = json.loads(path.read_text())
        except (OSError, ValueError) as exc:
            raise ReceiptError('no durable pre-dispatch record for %s; a request is persisted before dispatch'
                               % key) from exc
        if not isinstance(pre, dict):
            raise ReceiptError('the pre-dispatch record for %s is not an object' % key)
        if not ok and not (isinstance(error_class, str) and error_class.strip()):
            raise ReceiptError('a failed or rejected request must record its error class')
        if ok and (error_class is not None or error_detail is not None or rejected_before_generation is True):
            raise ReceiptError('a successful outcome must not carry an error class, an error detail or '
                               'rejected_before_generation=True; refusing a self-contradictory record')
        reported_raw = pre.get(RAW_DIGEST_FIELD)
        raw_path = self.raw_path(key)
        recomputed, agrees = None, None
        if raw_path.exists():
            recomputed = sha256_hex(raw_path.read_bytes())
            agrees = recomputed == reported_raw
            if not agrees:
                raise ReceiptError('the retained raw request bytes for %s hash to %s, not to the digest recorded '
                                   'before dispatch; refusing to publish a digest the bytes contradict'
                                   % (key, recomputed))
        detail, detail_transformations = (None, [])
        detail_chars, truncated_to = None, None
        if error_detail is not None:
            masked, detail_transformations = sanitize(str(error_detail), self.home, field='error_detail')
            detail_chars = len(masked)
            detail = masked[:ERROR_DETAIL_CHARS]
            if detail_chars > ERROR_DETAIL_CHARS:
                truncated_to = ERROR_DETAIL_CHARS
                detail_transformations = detail_transformations + [dict(
                    transformation='error_detail_truncated', field='error_detail', occurrences=1,
                    kept_chars=ERROR_DETAIL_CHARS, sanitized_chars=detail_chars,
                    why='the published error detail is bounded; the transformation is listed so a truncated '
                        'detail is never indistinguishable from a complete one')]
        payload = dict(
            self._common(key, logical_call_id, physical_attempt_id, 'post_dispatch'),
            kind='DTR-REQ-005 request outcome record (write-once, linked to its pre-dispatch receipt)',
            outcome='ok' if ok else 'error',
            error_class=None if ok else error_class.strip(),
            error_detail=detail,
            error_detail_chars=detail_chars,
            error_detail_complete=None if detail is None else truncated_to is None,
            error_detail_truncated_to=truncated_to,
            rejected_before_generation=rejected_before_generation,
            finish_reason=finish_reason,
            http_status=http_status,
            server_reported_usage=_validated_usage(usage),
            preflight_token_count=pre.get('preflight_token_count'),
            pre_dispatch_record_file=path.name,
            pre_dispatch_record_verified='published_projection_verified',
            pre_dispatch_projection_sha256=pre.get(PROJECTION_DIGEST_FIELD),
            **{RAW_DIGEST_FIELD: reported_raw},
            raw_request_recomputed_sha256=recomputed,
            raw_request_digest_agrees=agrees,
            raw_request_retained=raw_path.exists(),
            raw_request_private_file=raw_path.name,
            raw_request_private_root=self.private_root_label,
            raw_request_private_root_basis=self.private_root_basis,
            sanitization=self._sanitization(detail_transformations),
            digest_semantics=DIGEST_SEMANTICS,
            raw_request_equality=REPORTED_UNVERIFIED,
            raw_bytes_independently_verified=False,
            sanitization_transform_independently_verified=False)
        record = sealed(payload)
        text = json.dumps(record, indent=1) + '\n'
        _write_once(self.outcome_path(key), text)
        return record

    # -- completeness -----------------------------------------------------
    def completeness(self):
        """Presence plus local record integrity; never proof of actual dispatch or public/raw equality.

        Invalid files remain counted and listed, but cannot make a receipt set complete. Available private
        bytes are checked locally; their absence is a hole, never an empty request or known-zero usage.
        """
        def keys(directory, suffix):
            return {p.name[:-len(suffix)] for p in Path(directory).glob('*' + suffix)}
        raws = keys(self.private_dir, RAW_SUFFIX)
        published = keys(self.public_dir, PUBLIC_SUFFIX)
        outcomes = keys(self.public_dir, OUTCOME_SUFFIX)
        holes = dict(raw_without_published_record=sorted(raws - published),
                     published_record_without_raw=sorted(published - raws),
                     published_record_without_outcome=sorted(published - outcomes),
                     outcome_without_published_record=sorted(outcomes - published))
        invalid = []

        def validate(path, key, phase):
            verify_published_projection(path, expect_phase=phase)
            record = json.loads(path.read_text())
            if (record.get('request') != 'DTR-REQ-005' or record.get('cohort') != self.cohort
                    or record.get('run_id') != self.run_id or record.get('attempt_key') != key
                    or attempt_key(record.get('logical_call_id'), record.get('physical_attempt_id')) != key):
                raise ReceiptError('receipt identity does not match its episode and filename')
            if (record.get('raw_bytes_independently_verified') is not False
                    or record.get('sanitization_transform_independently_verified') is not False
                    or record.get('digest_semantics') != DIGEST_SEMANTICS):
                raise ReceiptError('receipt changes the reported/unverified provenance boundary')
            return record

        valid_pre = {}
        for key in sorted(published):
            path = self.record_path(key)
            try:
                pre = validate(path, key, 'pre_dispatch')
                validate_identity(pre.get('identity'))
                if (pre.get('raw_request_private_file') != self.raw_path(key).name
                        or pre.get('dispatch_state') != 'persisted_before_dispatch'
                        or pre.get('raw_request_published') is not False):
                    raise ReceiptError('pre-dispatch record has invalid raw-file or dispatch metadata')
                if key in raws:
                    raw = self.raw_path(key).read_bytes()
                    if (sha256_hex(raw) != pre[RAW_DIGEST_FIELD]
                            or pre.get('raw_request_bytes') != len(raw)):
                        raise ReceiptError('available private bytes disagree with the pre-dispatch digest/size')
                valid_pre[key] = pre
            except Exception as exc:  # noqa: BLE001  corruption is an incomplete set, not a reporting crash
                invalid.append(dict(file=path.name, error='%s: %s' % (type(exc).__name__, str(exc)[:300])))
        for key in sorted(outcomes):
            path = self.outcome_path(key)
            try:
                outcome = validate(path, key, 'post_dispatch')
                pre = valid_pre.get(key)
                if pre is None:
                    raise ReceiptError('outcome lacks a valid pre-dispatch record')
                if (outcome.get('pre_dispatch_record_file') != self.record_path(key).name
                        or outcome.get('pre_dispatch_projection_sha256') != pre[PROJECTION_DIGEST_FIELD]
                        or outcome.get(RAW_DIGEST_FIELD) != pre[RAW_DIGEST_FIELD]):
                    raise ReceiptError('outcome hashes/filename do not link to its pre-dispatch record')
                if outcome.get('raw_request_retained') is True:
                    if (outcome.get('raw_request_recomputed_sha256') != pre[RAW_DIGEST_FIELD]
                            or outcome.get('raw_request_digest_agrees') is not True):
                        raise ReceiptError('outcome raw-digest check contradicts its linked request')
                elif (outcome.get('raw_request_retained') is not False
                      or outcome.get('raw_request_recomputed_sha256') is not None
                      or outcome.get('raw_request_digest_agrees') is not None):
                    raise ReceiptError('missing raw bytes must have an explicitly unknown digest comparison')
                if outcome.get('outcome') not in ('ok', 'error'):
                    raise ReceiptError('outcome classification is missing or invalid')
                if outcome['outcome'] == 'error' and not outcome.get('error_class'):
                    raise ReceiptError('error outcome lacks its error class')
                if outcome['outcome'] == 'ok' and (outcome.get('error_class') is not None
                                                 or outcome.get('error_detail') is not None):
                    raise ReceiptError('successful outcome contradicts its error fields')
                if not isinstance(outcome.get('server_reported_usage'), dict):
                    raise ReceiptError('outcome lacks explicit server usage, including unknown fields')
                if _validated_usage(outcome['server_reported_usage']) != outcome['server_reported_usage']:
                    raise ReceiptError('outcome server usage is incomplete or internally inconsistent')
            except Exception as exc:  # noqa: BLE001
                invalid.append(dict(file=path.name, error='%s: %s' % (type(exc).__name__, str(exc)[:300])))
        return dict(cohort=self.cohort, run_id=self.run_id, attempt_keys=sorted(raws | published | outcomes),
                    n_raw=len(raws), n_published=len(published), n_outcomes=len(outcomes),
                    complete=not any(holes.values()) and not invalid, invalid_records=invalid,
                    note=COMPLETENESS_NOTE, **holes)


class _Dispatch:
    """Mutable holder the caller fills in before the dispatch returns or raises."""

    def __init__(self):
        self.usage = None
        self.finish_reason = None
        self.http_status = None
        self.rejected_before_generation = None
        self.receipt_errors = []


def _record_outcome_safely(store, dispatch, *, logical_call_id, physical_attempt_id, ok, error_class=None,
                           error_detail=None, on_receipt_error=None):
    """Record the outcome without ever changing the episode's own result.

    A bookkeeping failure here must not replace the real dispatch exception, and must not abort a model call
    that already succeeded: it is collected on the holder and handed to `on_receipt_error` if one was given."""
    try:
        return store.record_outcome(logical_call_id=logical_call_id, physical_attempt_id=physical_attempt_id,
                                    ok=ok, error_class=error_class, error_detail=error_detail,
                                    usage=dispatch.usage,
                                    rejected_before_generation=dispatch.rejected_before_generation,
                                    finish_reason=dispatch.finish_reason, http_status=dispatch.http_status)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as exc:  # noqa: BLE001  receipt bookkeeping never relabels or aborts an episode
        failure = dict(attempt_key='call%03d_attempt%02d' % (logical_call_id, physical_attempt_id)
                       if isinstance(logical_call_id, int) and isinstance(physical_attempt_id, int) else None,
                       phase='post_dispatch', error_class=type(exc).__name__, detail=str(exc)[:300],
                       consequence='the outcome record is missing for this attempt; completeness() lists it')
        dispatch.receipt_errors.append(failure)
        if on_receipt_error is not None:
            try:
                on_receipt_error(failure)
            except (KeyboardInterrupt, SystemExit):
                raise
            except Exception as callback_exc:  # noqa: BLE001  reporting must not replace the real call result
                dispatch.receipt_errors.append(dict(
                    attempt_key=failure['attempt_key'], phase='receipt_error_callback',
                    error_class=type(callback_exc).__name__, detail=str(callback_exc)[:300],
                    consequence='callback failed; original dispatch result is unchanged'))
        return None


@contextlib.contextmanager
def recorded_dispatch(store, *, logical_call_id, physical_attempt_id, serialized, preflight=_UNSET,
                      identity=None, on_receipt_error=None):
    """Persist the request, then record its outcome on BOTH the success and the failure path.

    The pre-dispatch persistence happens before any model call and is allowed to refuse (that is the lead's
    requirement). Once the call has been made, no receipt problem changes what the episode reports."""
    store.record_request(logical_call_id=logical_call_id, physical_attempt_id=physical_attempt_id,
                         serialized=serialized, preflight=preflight, identity=identity)
    dispatch = _Dispatch()
    try:
        yield dispatch
    except BaseException as exc:
        _record_outcome_safely(store, dispatch, logical_call_id=logical_call_id,
                               physical_attempt_id=physical_attempt_id, ok=False,
                               error_class=type(exc).__name__, error_detail=str(exc),
                               on_receipt_error=on_receipt_error)
        raise                                  # the REAL dispatch exception, never a receipt error
    _record_outcome_safely(store, dispatch, logical_call_id=logical_call_id,
                           physical_attempt_id=physical_attempt_id, ok=True,
                           on_receipt_error=on_receipt_error)


# ---------------------------------------------------------------- read-only verification

def verify_published_projection(path, *, expect_phase=None):
    """Recompute a published record's own digest. This never establishes the absent raw bytes."""
    path = Path(path)
    try:
        record = json.loads(path.read_text())
    except (OSError, ValueError) as exc:
        raise ReceiptError('published receipt unavailable or unparsable: %s' % path.name) from exc
    if not isinstance(record, dict):
        raise ReceiptError('published receipt must be an object: %s' % path.name)
    published = record.get(PROJECTION_DIGEST_FIELD)
    raw = record.get(RAW_DIGEST_FIELD)
    for value, label in ((published, PROJECTION_DIGEST_FIELD), (raw, RAW_DIGEST_FIELD)):
        if not isinstance(value, str) or not re.fullmatch(r'[0-9a-f]{64}', value):
            raise ReceiptError('missing/invalid %s in %s' % (label, path.name))
    if record.get('raw_request_equality') != REPORTED_UNVERIFIED:
        raise ReceiptError('published receipt must state raw_request_equality=%s: %s' % (REPORTED_UNVERIFIED, path.name))
    if published == raw:
        raise ReceiptError('published projection digest is presented as the raw request digest: %s' % path.name)
    if expect_phase is not None and record.get('phase') != expect_phase:
        raise ReceiptError('published receipt phase is %r, expected %r' % (record.get('phase'), expect_phase))
    payload = {k: v for k, v in record.items() if k != PROJECTION_DIGEST_FIELD}
    if canonical_sha256(payload) != published:
        raise ReceiptError('published projection digest mismatch: %s' % path.name)
    return dict(status='published_projection_verified', published_file=path.name, phase=record.get('phase'),
                published_projection_sha256=published, reported_raw_request_sha256=raw,
                raw_request_equality=REPORTED_UNVERIFIED, raw_bytes_independently_verified=False,
                sanitization_transform_independently_verified=False,
                reason='The published projection matches its own recorded digest. The raw request bytes are private, '
                       'so their equality and the stated transformation remain reported and unverified.')
