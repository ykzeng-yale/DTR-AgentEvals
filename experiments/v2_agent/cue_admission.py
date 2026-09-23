"""DTR-REQ-005 'cue-v1' frozen admission: the write-once source/amendment binding, whole-queue validation, the
runtime queue ledger and the predeclared infrastructure stop state.

Implements the lead's integration contract, bullet "Frozen admission"
(docs/theory_feedback_20260923_req005_review.md, "Concrete integration contract"):

    bind every new/imported execution module, cue/definitions/coding guide, assignment plan, original
    model/conversion/image/YAML/evaluator pins, settings and deadlines. The registry alone does not bind these.
    Validate the entire fixed queue before launch and every resume. Keep 12 assignments / 576 physical requests
    total across resumes, one cohort, no duplicate replacement or outcome-driven extension. Require a new unique
    output namespace; neither a legacy result nor a projection report can satisfy runtime admission.

and answer 1's storage rule: "Stop new queue dispatch while storage integrity is unresolved; preserve the affected
and remaining assignment states explicitly. This is a predeclared infrastructure stop, never an outcome-driven
stopping rule."

What this module does and does not do
  * It READS sources and pin records and hashes them. It runs no model, server, container, evaluator or network
    call. It never imports the frozen yaml-v1 drivers: their constants are read from their source with `ast`, so
    importing them (pilot_episode sets process environment variables at import) never happens here. The two pure
    registries it needs values from (cue_cohort.py, cue_detector.py) are executed from the EXACT bytes it hashed.
  * It writes only inside the cue-v1 namespace results/v2_agent/pilot_20260923_cue_v1, and only through
    `launch_session` / `resume_session` / `record_reconciliation`, which cue_runner.py calls on a live launch.
    `compute_binding` and `validate_queue` never create or write anything.
  * It changes no setting. H24, temperature, max_tokens, context, two physical attempts per logical call, the
    576-request cap, the 12-assignment frame, the model pins and the Submitted-only endpoint are the lead's
    choices; they are restated in CONTRACT_* below only so every source can be checked against them, and a
    disagreement refuses admission instead of being reconciled here.

Runtime state (the ONLY things admitted as runtime state inside the namespace):
  cue_binding.json        write-once binding, self-digested (`binding_sha256`)
  queue_ledger.jsonl      append-only, hash-chained ledger of sessions, assignment starts/ends, stops, reconciliations
  queue_ledger.head.json  the ledger's last sequence number and hash, replaced atomically after every append, so a
                          ledger truncated at a record boundary is detected instead of silently resumed
  <run_id>/               one directory per recorded assignment start, holding only the files the cue-v1 episode
                          writes (RUN_DIR_FILES and its receipts/ directory)
Anything else -- a legacy result directory, a report file, a published projection, a symlink -- is refused, at
validation and again before every dispatch of a session. A write-once launch marker OUTSIDE the namespace
(LAUNCH_MARKER_REL, under the git-ignored work/) records that the cohort was launched, so deleting the namespace
cannot open a second full launch of the same frozen cohort.

Accepted source pins. Every lead-accepted helper, the reused wc2 module, the five frozen yaml-v1 sources and the
coding guide must still carry the digest the lead accepted (docs/audits/req005_component_review_20260923.json) or,
where that audit is silent, the digest the worker published (docs/req005_fixture_landmarks_20260923.json). A
pre-launch edit to any of them therefore refuses the launch instead of being frozen into the binding. The pinned
SDK files on the traced request path are verified against their installed RECORD digests, every .pth file is bound,
and a sitecustomize/usercustomize hook in the pinned interpreter refuses admission. The deadline and storage bounds
are read from the modules that ENFORCE them (cue_terminal, cue_transport), not only restated here.
"""
from __future__ import annotations

import ast
import base64
import csv
import fcntl
import hashlib
import io
import json
import os
import re
import shutil
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()   # the bytes this process runs

REQUEST = 'DTR-REQ-005'
COHORT = 'cue-v1'
BINDING_KIND = 'cue-v1 frozen source/amendment binding (DTR-REQ-005)'
BINDING_VERSION = 'cue-admission-2'
CONTRACT_REF = ('docs/theory_feedback_20260923_req005_review.md, "Concrete integration contract", '
                'bullet "Frozen admission", and answer 1 (storage stop)')

# ------------------------------------------------------------------ repository-relative locations
MODULE_DIR_REL = 'experiments/v2_agent'
NAMESPACE_REL = 'results/v2_agent/pilot_20260923_cue_v1'
BINDING_FILE = 'cue_binding.json'
LEDGER_FILE = 'queue_ledger.jsonl'
CODING_GUIDE_REL = 'docs/req005_visible_evidence_guide_20260923.md'
# The frozen yaml-v1 amendment names the base spec, the frame and the conversion record and pins their digests;
# admission reuses those pin sources instead of restating any pin.
AMENDMENT_REL = 'configs/v2_fixed_backend_development_pilot_yaml_v1_20260922.json'
YAML_V1_BINDING_REL = 'results/v2_agent/pilot_20260922_yaml_v1/cohort_binding.json'
PILOT_EPISODE_REL = MODULE_DIR_REL + '/pilot_episode.py'
PILOT_RUNNER_REL = MODULE_DIR_REL + '/pilot_runner.py'
PINNED_VENV_REL = 'work/venvs/minisweagent_04d809c'          # the frozen pilot's interpreter (pilot_runner.MSWEA_PY)
SDK_DISTRIBUTIONS = ('httpcore', 'httpx', 'litellm', 'openai', 'tenacity')   # the traced outbound request path
# The files on the traced request path (docs/req005_transport_map_20260923.md), verified byte-for-byte against the
# sha256 their installed RECORD states. Relative to the pinned interpreter's site-packages.
TRACED_SDK_FILES = {
    'httpx': ('httpx/_client.py', 'httpx/_models.py', 'httpx/_content.py', 'httpx/_transports/default.py'),
    'httpcore': ('httpcore/_sync/connection_pool.py', 'httpcore/_sync/connection.py', 'httpcore/_sync/http11.py'),
    'openai': ('openai/_base_client.py', 'openai/_client.py', 'openai/_utils/_json.py',
               'openai/resources/chat/completions/completions.py'),
    'litellm': ('litellm/__init__.py', 'litellm/main.py', 'litellm/utils.py', 'litellm/constants.py',
                'litellm/llms/openai/openai.py', 'litellm/llms/openai/common_utils.py',
                'litellm/llms/custom_httpx/http_handler.py', 'litellm/litellm_core_utils/exception_mapping_utils.py'),
    'tenacity': ('tenacity/__init__.py',),
}
EDITABLE_MSWEA_PTH = '__editable__.mini_swe_agent-2.4.6.pth'
FORBIDDEN_SITE_HOOKS = ('sitecustomize.py', 'usercustomize.py')
DATASET_REL = 'work/benchmark_inputs/swebench_verified_c104f840/test-00000-of-00001.parquet'
ACCEPTED_PINS_AUDIT_REL = 'docs/audits/req005_component_review_20260923.json'
ACCEPTED_PINS_LANDMARKS_REL = 'docs/req005_fixture_landmarks_20260923.json'
LAUNCH_MARKER_REL = 'work/req005_cue_v1_launch_marker.json'     # outside the namespace; git-ignored, write-once
HEAD_FILE = 'queue_ledger.head.json'
HEAD_TMP = HEAD_FILE + '.tmp'
TORN_FRAGMENT = re.compile(r'^queue_ledger\.torn-(\d+)\.bin$')
PRIVATE_RECEIPTS_REL = 'work/req005_request_receipts/cue-v1'     # private raw request bodies, per run id
RECEIPTS_SUBDIR = 'receipts'                                     # public bounded receipts inside each run directory
# Every file a cue-v1 episode writes into its run directory; nothing else is runtime state there.
RUN_DIR_FILES = frozenset({
    'admission.json', 'attempts.jsonl', 'call9_history.json', 'calls.jsonl', 'container_cleanup.json',
    'container_ownership.json', 'cue_delivery.json', 'effective_config.json', 'episode.json', 'exit_diagnostic.json',
    'submission.diff', 'terminal_phase.json', 'trajectory.json'})
RUN_DIR_RECEIPT = re.compile(r'^(call\d{3}_attempt\d{2}\.(request|outcome)\.json|refusal\d{3}\.refusal\.json)$')

# ------------------------------------------------------------------ bound execution modules
NEW_MODULES = ('cue_episode.py', 'cue_transport.py', 'cue_terminal.py', 'cue_admission.py', 'cue_runner.py')
ACCEPTED_HELPERS = ('cue_detector.py', 'exit_capture.py', 'request_receipt.py', 'trajectory_triples.py',
                    'cue_cohort.py')
REUSED_MODULES = ('workspace_capture.py',)
REQUIRED_MODULES = NEW_MODULES + ACCEPTED_HELPERS + REUSED_MODULES
FROZEN_REFERENCE = ('pilot_episode.py', 'pilot_runner.py', 'pilot_cohort.py', 'pilot_report.py', 'pilot_grade.py')
ROLE_NEW = 'new cue-v1 execution module'
ROLE_HELPER = 'lead-accepted cue-v1 helper'
ROLE_REUSED = 'reused unmodified execution module'
ROLE_IMPORTED = 'imported by a bound module (import closure)'

# ------------------------------------------------------------------ accepted identities (lead review of ee9a4bc)
ACCEPTED_CUE_SHA256 = '80d52625bd593cd6fecafeb06daca898792979592272d9fadcf0ddd04bd39d9e'
ACCEPTED_CUE_BYTES = 290
ACCEPTED_PLAN_SHA256 = 'dc687c8413d5aa8f81cb498b22cc5fac5f4fcf2535bf0c66aea8db2fb882c1ae'
ACCEPTED_PATTERN_WIDTHS = {'AAA': 3, 'ABABAB': 6}
ACCEPTED_DETECTOR_MODES = ['live', 'observe']

# ------------------------------------------------------------------ the lead's frozen choices, restated for checking
CONTRACT_SETTINGS = dict(horizon_h=24, step_limit=24, temperature=0.0, max_tokens=1536, context_per_slot=16384,
                         physical_attempts_per_logical_call=2, n_assignments=12, max_physical_requests=576,
                         max_physical_requests_per_assignment=48, command_timeout_s=60, request_timeout_s=900,
                         episode_wall_s=1800, cost_limit=0.0, max_cues_per_episode=1)
ENDPOINT = ('Submitted-only: the frozen wc2 capture on an explicit Submitted exit; the all-exit diagnostic is never '
            'written into it, never graded and never changes eligibility')
CONTRACT_DEADLINES = dict(
    # existing frozen pilot bounds, which must not be silently enlarged
    episode_wall_s=1800, block_cap_s=7200, kill_margin_s=300, model_switch_allowance_s=300,
    child_cleanup_grace_s=120, server_cleanup_reserve_s=90, request_timeout_s=900, command_timeout_s=60,
    evaluator_attempt_timeout_s=1800,
    # the lead's diagnostic/cleanup bounds (review, bullet "Endpoint then diagnostic then cleanup")
    diagnostic_max_s=30, post_inference_cleanup_window_s=120, cleanup_reserve_min_s=90,
    diagnostic_subprocess_timeout_max_s=60)
DEADLINE_RULES = dict(
    phase_deadline='min(actual_inference_end + 120 s, existing absolute cleanup cap)',
    diagnostic_deadline=('min(diagnostic start + 30 s, absolute cleanup deadline - 90 s - 4 s hand-off margin); the '
                         'margin covers the supervisor\'s post-kill confirmation and is taken from the diagnostic, '
                         'never from the 90-s cleanup reserve'),
    diagnostic_subprocess_timeout='min(remaining diagnostic time, absolute cleanup deadline - 90 s, 60 s)',
    no_time_left='skip the diagnostic with an explicit unavailable/timeout reason',
    cleanup='runs in a finally path, even after receipt/capture errors; bounded by the supervisor',
    not_used='the exit_capture helper default TOTAL_BUDGET_S=300 is not accepted for live capture')
KiB, MiB, GiB = 1024, 1024 ** 2, 1024 ** 3
CONTRACT_STORAGE = dict(
    request_body_cap_bytes=8 * MiB, cohort_raw_body_reservation_bytes=576 * 8 * MiB,
    start_free_space_above_host_reserve_bytes=6 * GiB, public_request_whole_max_bytes=64 * KiB,
    public_preview_head_bytes=32 * KiB, public_preview_tail_bytes=32 * KiB,
    public_request_receipt_cap_bytes=128 * KiB, public_outcome_record_cap_bytes=128 * KiB,
    host_reserve_bytes='not declared in any repository source: supplied by the live launcher to the free-space '
                       'preflight and recorded there, never invented here',
    oversize_or_failed_write='no truncation and no dispatch without its receipt: a recorded refusal, no physical '
                             'request, no automatic model retry, and a queue stop while storage is unresolved')

# ------------------------------------------------------------------ predeclared stop codes (closed set)
KIND_INFRASTRUCTURE = 'infrastructure'   # needs an explicit reconciliation record before any further dispatch
KIND_ADMISSION = 'admission'             # a bound input or the request cap refused dispatch; fix, then resume
KIND_HOST_GATE = 'host_gate'             # time/pause/host coordination; resume later, nothing to reconcile
STOP_CODES = {
    'namespace_contents_invalid': KIND_ADMISSION,
    'storage_preflight_unresolved': KIND_INFRASTRUCTURE,
    'storage_integrity_unresolved': KIND_INFRASTRUCTURE,
    'request_accounting_unresolved': KIND_INFRASTRUCTURE,
    'episode_function_error': KIND_INFRASTRUCTURE,
    'run_directory_error': KIND_INFRASTRUCTURE,
    'bound_input_changed': KIND_ADMISSION,
    'request_cap': KIND_ADMISSION,
    'host_gate': KIND_HOST_GATE,
}
STOPS_WITH_AFFECTED_ASSIGNMENT = frozenset({'storage_integrity_unresolved', 'request_accounting_unresolved',
                                            'episode_function_error', 'run_directory_error'})

# ------------------------------------------------------------------ assignment states
UNSTARTED = 'unstarted'
INTERRUPTED = 'interrupted'                       # a start with no end record (crash/kill); never re-dispatched
INTERRUPTED_RECONCILED = 'interrupted_reconciled'
TERMINAL = 'terminal'
TERMINAL_UNRESOLVED = 'terminal_integrity_unresolved'
EPISODE_ERROR = 'episode_error'
ACCOUNTING_CLEAN = 'reported'
STORAGE_RESOLVED = 'resolved'
STORAGE_UNRESOLVED = 'unresolved'

RUN_ID = re.compile(r'^(?P<assignment>[A-Za-z0-9_.\-]+?)__run-\d{8}T\d{6}Z-[0-9a-f]{6}$')
LEGACY_RUN_MARKERS = ('__pilot-cp2-wc2', '__smoke', '__pilot-')
REPORT_OR_PROJECTION = re.compile(r'(^report_.*\.json$|^block_\d+\.json$|^preflight_.*\.json$|^cohort_binding\.json$|'
                                  r'\.request\.json$|\.outcome\.json$|^exit_diagnostic\.json$|\.md$|\.csv$)')


class AdmissionRefused(RuntimeError):
    """Admission refused: nothing is dispatched. `reasons` lists every refusal; `changed` lists every bound-input
    path whose frozen value differs from the current one; `problems` lists current-source inconsistencies."""

    def __init__(self, reasons, *, changed=(), problems=()):
        self.reasons = list(reasons)
        self.changed = list(changed)
        self.problems = list(problems)
        super().__init__('; '.join(self.reasons))

    @property
    def changed_classes(self):
        return sorted({path.split('/', 1)[0] for path in self.changed})


class LedgerRefused(AdmissionRefused):
    """The runtime ledger breaks the queue contract (order, duplicates, extension, cap, chain, schema)."""


class RequestCapReached(RuntimeError):
    """A physical request would exceed the assignment's 48 or the cohort's 576; raised BEFORE dispatch."""


# ------------------------------------------------------------------ small utilities

def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def utc(t=None):
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(t))


def _int(value):
    return type(value) is int


def _same(a, b):
    """Equal values, never letting a bool stand in for a number."""
    return type(a) is not bool and type(b) is not bool and a == b


class Layout:
    """Where the bound inputs live. `root` is the repository root; tests pass a disposable copy."""

    def __init__(self, root=None):
        self.root = Path(ROOT if root is None else root)

    @property
    def module_dir(self):
        return self.root / MODULE_DIR_REL

    @property
    def out(self):
        return self.root / NAMESPACE_REL

    @property
    def binding_path(self):
        return self.out / BINDING_FILE

    @property
    def ledger_path(self):
        return self.out / LEDGER_FILE

    def rel(self, path):
        return Path(path).resolve().relative_to(self.root.resolve()).as_posix()


# ------------------------------------------------------------------ source reading helpers

class _Reader:
    def __init__(self, layout):
        self.layout = layout
        self.problems = []
        self.cache = {}

    def problem(self, text):
        if text not in self.problems:
            self.problems.append(text)

    def read(self, rel, label):
        """Exact bytes of a bound regular file (never a symlink), or None with a recorded problem."""
        if rel in self.cache:
            return self.cache[rel]
        path = self.layout.root / rel
        data = None
        try:
            if path.is_symlink():
                self.problem('%s: %s is a symlink; a bound input must be a regular file' % (label, rel))
            elif not path.is_file():
                self.problem('%s: bound input missing: %s' % (label, rel))
            else:
                data = path.read_bytes()
        except OSError as exc:
            self.problem('%s: %s unreadable (%s)' % (label, rel, type(exc).__name__))
        self.cache[rel] = data
        return data

    def json(self, rel, label):
        data = self.read(rel, label)
        if data is None:
            return None
        try:
            value = json.loads(data)
        except ValueError:
            self.problem('%s: %s is not valid JSON' % (label, rel))
            return None
        if not isinstance(value, dict):
            self.problem('%s: %s is not a JSON object' % (label, rel))
            return None
        return value


def _literal(node):
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'dict'
            and not node.args and all(kw.arg for kw in node.keywords)):
        return {kw.arg: _literal(kw.value) for kw in node.keywords}
    return ast.literal_eval(node)


def module_constants(source, names):
    """Top-level literal assignments `NAME = <literal>` / `A, B = <literal>, <literal>` / `NAME = dict(k=<literal>)`
    read from source WITHOUT executing it. Returns {name: value} for the names found."""
    found = {}
    for node in ast.parse(source).body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            pairs = []
            if isinstance(target, ast.Name):
                pairs = [(target, node.value)]
            elif (isinstance(target, ast.Tuple) and isinstance(node.value, ast.Tuple)
                  and len(target.elts) == len(node.value.elts)):
                pairs = list(zip(target.elts, node.value.elts))
            for name_node, value_node in pairs:
                if isinstance(name_node, ast.Name) and name_node.id in names:
                    try:
                        found[name_node.id] = _literal(value_node)
                    except (ValueError, TypeError, SyntaxError):
                        pass
    return found


def _arith(node, env):
    """A restricted evaluator for the enforcing modules' size/time constants: numbers, earlier names, + - * **."""
    if isinstance(node, ast.Constant) and type(node.value) in (int, float):
        return node.value
    if isinstance(node, ast.Name) and node.id in env:
        return env[node.id]
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and \
            '%s.%s' % (node.value.id, node.attr) in env:
        return env['%s.%s' % (node.value.id, node.attr)]
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Pow)):
        left, right = _arith(node.left, env), _arith(node.right, env)
        return {ast.Add: left + right, ast.Sub: left - right, ast.Mult: left * right,
                ast.Pow: left ** right if isinstance(node.op, ast.Pow) else None}[type(node.op)]
    raise ValueError('not a plain arithmetic constant')


def arithmetic_constants(source, names, env=None):
    """Top-level `NAME = <arithmetic>` (and tuple) assignments, evaluated in source order WITHOUT executing the
    module. Returns {name: value} for the requested names that evaluate."""
    env = dict(env or {})
    found = {}
    for node in ast.parse(source).body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        pairs = [(target, node.value)] if isinstance(target, ast.Name) else (
            list(zip(target.elts, node.value.elts)) if isinstance(target, ast.Tuple) and isinstance(
                node.value, ast.Tuple) and len(target.elts) == len(node.value.elts) else [])
        for name_node, value_node in pairs:
            if not isinstance(name_node, ast.Name):
                continue
            try:
                env[name_node.id] = _arith(value_node, env)
            except (ValueError, TypeError, KeyError, ZeroDivisionError):
                continue
            if name_node.id in names:
                found[name_node.id] = env[name_node.id]
    return found


def call_keywords(source, function_name):
    """Keyword names passed to every call of `function_name` (attribute or bare name) anywhere in `source`."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else None
            if name == function_name:
                found.append(sorted(kw.arg for kw in node.keywords if kw.arg))
    return found


def _server_context_arg(source):
    """The literal value following '-c' in the frozen runner's llama-server argument list, if present."""
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.List):
            values = [e.value if isinstance(e, ast.Constant) else None for e in node.elts]
            for i in range(len(values) - 1):
                if values[i] == '-c' and isinstance(values[i + 1], str) and values[i + 1].isdigit():
                    return int(values[i + 1])
    return None


def local_imports(source, module_dir):
    """Sibling modules (FILE names in module_dir) imported anywhere in `source`, including function-local imports.
    Dynamic imports (importlib, __import__) are not visible to this static scan."""
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name.split('.')[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.add(node.module.split('.')[0])
            elif node.level:
                names.update(alias.name for alias in node.names)
    return sorted(name + '.py' for name in names if (Path(module_dir) / (name + '.py')).is_file())


def _exec_bound(reader, name, source):
    """Execute the EXACT hashed bytes of a pure registry module in a fresh namespace (never via sys.modules)."""
    if source is None:
        return None
    path = reader.layout.module_dir / name
    module = types.ModuleType('cue_admission_bound_' + name[:-3])
    module.__file__ = str(path)
    try:
        exec(compile(source, str(path), 'exec', dont_inherit=True), module.__dict__)
    except Exception as exc:  # noqa: BLE001  recorded as a refusal, never raised into the caller
        reader.problem('modules: %s could not be evaluated (%s: %s)' % (name, type(exc).__name__, str(exc)[:200]))
        return None
    return module.__dict__


# ------------------------------------------------------------------ binding sections

def _modules(reader):
    module_dir = reader.layout.module_dir
    roles, sources, queue = {}, {}, []
    for name in REQUIRED_MODULES:
        roles[name] = (ROLE_NEW if name in NEW_MODULES else ROLE_HELPER if name in ACCEPTED_HELPERS else ROLE_REUSED)
        queue.append(name)
    while queue:
        name = queue.pop(0)
        if name in sources:
            continue
        data = reader.read(MODULE_DIR_REL + '/' + name, 'modules')
        sources[name] = data
        if data is None:
            continue
        try:
            imported = local_imports(data, module_dir)
        except SyntaxError:
            reader.problem('modules: %s cannot be parsed' % name)
            continue
        for child in imported:
            if child not in roles:
                roles[child] = ROLE_IMPORTED
            if child not in sources and child not in queue:
                queue.append(child)
    digests = {name: sha256_hex(data) for name, data in sources.items() if data is not None}
    return digests, dict(sorted(roles.items())), sources


def _cue_and_detector(reader, ns):
    if ns is None:
        reader.problem('cue: cue_detector.py unavailable; the cue and detector definitions cannot be bound')
        return None, None
    text = ns.get('CUE_TEXT')
    cue = None
    if not isinstance(text, str):
        reader.problem('cue: cue_detector.CUE_TEXT is not a string')
    else:
        raw = text.encode('utf-8')
        digest = sha256_hex(raw)
        cue = dict(text=text, sha256=digest, utf8_bytes=len(raw), characters=len(text),
                   source=MODULE_DIR_REL + '/cue_detector.py')
        if digest != ACCEPTED_CUE_SHA256 or len(raw) != ACCEPTED_CUE_BYTES:
            reader.problem('cue: text sha256 %s (%d bytes) is not the accepted %d-byte cue %s'
                           % (digest, len(raw), ACCEPTED_CUE_BYTES, ACCEPTED_CUE_SHA256))
        if ns.get('CUE_SHA256') != digest:
            reader.problem('cue: cue_detector.CUE_SHA256 disagrees with its own CUE_TEXT')
    widths = ns.get('PATTERN_WIDTH')
    detector = dict(id=ns.get('DETECTOR_ID'),
                    pattern_widths=dict(widths) if isinstance(widths, dict) else None,
                    modes=list(ns.get('MODES') or ()), first_logical_call=ns.get('FIRST_LOGICAL_CALL'),
                    horizon_default=ns.get('H_DEFAULT'), trigger_note=ns.get('TRIGGER_NOTE'),
                    no_pattern_reason=ns.get('NO_PATTERN_REASON'), call_id_keys=list(ns.get('CALL_ID_KEYS') or ()),
                    observation_error_keys=list(ns.get('OBSERVATION_ERROR_KEYS') or ()),
                    one_cue_maximum=True, source=MODULE_DIR_REL + '/cue_detector.py')
    if detector['pattern_widths'] != ACCEPTED_PATTERN_WIDTHS:
        reader.problem('detector: patterns %r are not the accepted AAA/ABABAB widths' % (detector['pattern_widths'],))
    if detector['modes'] != ACCEPTED_DETECTOR_MODES:
        reader.problem('detector: modes %r are not live/observe' % (detector['modes'],))
    if not _same(detector['first_logical_call'], 1):
        reader.problem('detector: logical calls must be numbered from 1')
    if not _same(detector['horizon_default'], CONTRACT_SETTINGS['horizon_h']):
        reader.problem('detector: default horizon %r is not H24' % (detector['horizon_default'],))
    return cue, detector


def _plan(reader, ns, detector):
    if ns is None or not callable(ns.get('frozen_plan')):
        reader.problem('plan: cue_cohort.frozen_plan unavailable')
        return None
    try:
        fp = ns['frozen_plan']()
        rows = [dict(row) for row in fp['assignments']]
        payload = {k: v for k, v in fp.items() if k != 'plan_sha256'}
        recomputed = sha256_hex(json.dumps(payload, sort_keys=True, separators=(',', ':'),
                                           ensure_ascii=False).encode())
    except Exception as exc:  # noqa: BLE001
        reader.problem('plan: cue_cohort.frozen_plan failed (%s: %s)' % (type(exc).__name__, str(exc)[:200]))
        return None
    plan = dict(source=MODULE_DIR_REL + '/cue_cohort.py', plan_sha256=fp.get('plan_sha256'), cohort=fp.get('cohort'),
                output_dir=fp.get('output_dir'), pair_order=fp.get('pair_order'),
                n_assignments=fp.get('n_assignments'), horizon_h=fp.get('horizon_h'),
                attempts_per_call=fp.get('attempts_per_call'), max_physical_requests=fp.get('max_physical_requests'),
                detector=fp.get('detector'), exit_capture_binding=fp.get('exit_capture_binding'), assignments=rows)
    if plan['plan_sha256'] != recomputed:
        reader.problem('plan: cue_cohort plan_sha256 does not match its own payload')
    if plan['plan_sha256'] != ACCEPTED_PLAN_SHA256:
        reader.problem('plan: plan_sha256 %s is not the accepted 12-assignment frame %s'
                       % (plan['plan_sha256'], ACCEPTED_PLAN_SHA256))
    if plan['cohort'] != COHORT or plan['output_dir'] != NAMESPACE_REL:
        reader.problem('plan: cohort/output %r/%r is not %s/%s' % (plan['cohort'], plan['output_dir'], COHORT,
                                                                    NAMESPACE_REL))
    if [row.get('position') for row in rows] != list(range(1, CONTRACT_SETTINGS['n_assignments'] + 1)):
        reader.problem('plan: positions are not exactly 1..%d' % CONTRACT_SETTINGS['n_assignments'])
    if len({row.get('assignment_id') for row in rows}) != len(rows):
        reader.problem('plan: duplicate assignment ids')
    if detector is not None and plan['detector'] != detector.get('id'):
        reader.problem('plan: detector binding %r differs from cue_detector %r' % (plan['detector'], detector.get('id')))
    return plan


def _pins(reader, plan):
    """Every pin comes from the frozen pilot's own pin sources; nothing is restated."""
    amendment = reader.json(AMENDMENT_REL, 'pins')
    episode_src = reader.read(PILOT_EPISODE_REL, 'pins')
    runner_src = reader.read(PILOT_RUNNER_REL, 'pins')
    ep = module_constants(episode_src, {'H', 'WALL_S', 'MAX_TOKENS', 'CMD_TIMEOUT', 'ATTEMPTS_PER_CALL',
                                        'REQUEST_TIMEOUT_S', 'CONFIGURATION_BINDING', 'MINI_SWE_AGENT_PIN',
                                        'DEFAULT_YAML_SHA'}) if episode_src is not None else {}
    rn = module_constants(runner_src, {'PORTS', 'ALIAS', 'BLOCK_CAP', 'EPISODE_WALL', 'KILL_MARGIN',
                                       'SWITCH_ALLOWANCE', 'CHILD_CLEANUP_GRACE', 'SERVER_CLEANUP_RESERVE',
                                       'HARNESS_PIN', 'DEFAULT_YAML_PIN', 'FROZEN_SETTINGS'}) \
        if runner_src is not None else {}
    server_context = _server_context_arg(runner_src) if runner_src is not None else None
    refs = dict(episode=ep, runner=rn, server_context=server_context, base=None, amendment=amendment)
    pin_sources = {}
    for rel in (AMENDMENT_REL, PILOT_EPISODE_REL, PILOT_RUNNER_REL, YAML_V1_BINDING_REL):
        data = reader.read(rel, 'pins')
        if data is not None:
            pin_sources[rel] = sha256_hex(data)
    pins = dict(pin_sources=pin_sources)
    if amendment is None:
        return pins, refs
    base = frame = conversion = None
    try:
        declared = dict(base_spec=(amendment['base_spec'], amendment['base_spec_sha256']),
                        frame=(amendment['frame'], amendment['frame_sha256']),
                        conversion_record=(amendment['conversion_record'], amendment['conversion_record_sha256']))
    except (KeyError, TypeError):
        reader.problem('pins: the yaml-v1 amendment does not name base_spec/frame/conversion_record with digests')
        return pins, refs
    for key, (rel, digest) in declared.items():
        data = reader.read(rel, 'pins')
        if data is None:
            continue
        pin_sources[rel] = sha256_hex(data)
        if pin_sources[rel] != digest:
            reader.problem('pins: %s differs from the yaml-v1 amendment %s_sha256' % (rel, key))
    base = reader.json(declared['base_spec'][0], 'pins')
    frame = reader.json(declared['frame'][0], 'pins')
    conversion = reader.json(declared['conversion_record'][0], 'pins')
    refs['base'] = base
    harness_pin = ep.get('MINI_SWE_AGENT_PIN')
    yaml_rel = None
    if isinstance(harness_pin, str) and re.fullmatch(r'[0-9a-f]{40}', harness_pin):
        refs['mswea_rel'] = 'work/upstream/mini-swe-agent-' + harness_pin
        yaml_rel = refs['mswea_rel'] + '/src/minisweagent/config/default.yaml'
        data = reader.read(yaml_rel, 'pins')
        if data is not None:
            pin_sources[yaml_rel] = sha256_hex(data)
            if pin_sources[yaml_rel] != ep.get('DEFAULT_YAML_SHA'):
                reader.problem('pins: %s differs from the frozen pilot_episode DEFAULT_YAML_SHA' % yaml_rel)
    else:
        reader.problem('pins: pilot_episode.MINI_SWE_AGENT_PIN is not a 40-hex commit')
    if ep.get('MINI_SWE_AGENT_PIN') != rn.get('HARNESS_PIN') or ep.get('DEFAULT_YAML_SHA') != rn.get('DEFAULT_YAML_PIN'):
        reader.problem('pins: pilot_episode and pilot_runner disagree on the harness/default.yaml pins')
    pins['harness'] = dict(mini_swe_agent=ep.get('MINI_SWE_AGENT_PIN'), default_yaml_sha256=ep.get('DEFAULT_YAML_SHA'),
                           default_yaml=yaml_rel, configuration_binding=ep.get('CONFIGURATION_BINDING'))
    # frozen yaml-v1 reference sources, and their agreement with the published yaml-v1 cohort binding
    reference = {}
    for name in FROZEN_REFERENCE:
        data = reader.read(MODULE_DIR_REL + '/' + name, 'pins')
        if data is not None:
            reference[name] = sha256_hex(data)
    pins['frozen_reference'] = reference
    yaml_v1 = reader.json(YAML_V1_BINDING_REL, 'pins')
    if yaml_v1 is not None:
        sources = yaml_v1.get('sources')
        if yaml_v1.get('cohort') != 'yaml-v1' or not isinstance(sources, dict) or not sources:
            reader.problem('pins: %s is not the yaml-v1 source binding' % YAML_V1_BINDING_REL)
        else:
            for name, digest in sorted(sources.items()):
                if reference.get(name) != digest:
                    reader.problem('pins: frozen reference %s differs from %s' % (name, YAML_V1_BINDING_REL))
        if yaml_v1.get('amendment_sha256') != pin_sources.get(AMENDMENT_REL):
            reader.problem('pins: the yaml-v1 amendment differs from %s amendment_sha256' % YAML_V1_BINDING_REL)
    try:
        if conversion is not None:
            aliases, ports = rn.get('ALIAS') or {}, rn.get('PORTS') or {}
            models = {}
            for backend in ('small', 'large'):
                record = conversion['backends'][backend]
                q4 = record['q4_k_m']
                models[backend] = dict(alias=aliases.get(backend), repository=record.get('repository'),
                                       source_commit=record.get('source_commit'), gguf_file=q4['file'],
                                       gguf_sha256=q4['sha256'], gguf_bytes=q4.get('bytes'), port=ports.get(backend))
                if not isinstance(models[backend]['alias'], str) or not _int(models[backend]['port']):
                    reader.problem('pins: pilot_runner has no alias/port for backend %s' % backend)
            pins['models'] = models
            pins['llama_cpp'] = dict(commit=conversion['llama_cpp']['commit'],
                                     llama_server_sha256=conversion['llama_cpp']['tools']['llama-server']['sha256'])
        if frame is not None:
            images = {task['instance_id']: task['instance_image'] for task in frame['pilot']['tasks']}
            pins['evaluator'] = dict(expected_identity=frame['expected_identity'])
            if plan is not None:
                pins['images'] = {}
                for row in plan['assignments']:
                    if row['instance_id'] not in images:
                        reader.problem('pins: task %s has no frozen image in the frame' % row['instance_id'])
                    else:
                        pins['images'][row['instance_id']] = images[row['instance_id']]
        if base is not None:
            pins.setdefault('evaluator', {}).update(
                attempt_timeout_s=base['episodes']['evaluator_attempt_timeout_seconds'],
                retry_max=base['episodes']['evaluator_retry_max'])
        dataset = reader.read(DATASET_REL, 'pins')
        if dataset is not None:
            pins['dataset'] = dict(path=DATASET_REL, sha256=sha256_hex(dataset), bytes=len(dataset))
            if frame is not None and frame['expected_identity'].get('dataset_sha256') != pins['dataset']['sha256']:
                reader.problem('pins: %s differs from the frame expected_identity.dataset_sha256' % DATASET_REL)
    except (KeyError, TypeError) as exc:
        reader.problem('pins: a frozen pin record lacks an expected field (%s)' % exc)
    if plan is not None and 'models' in pins and 'images' in pins:
        pins['assignment_pins'] = [
            dict(position=row['position'], assignment_id=row['assignment_id'], instance_id=row['instance_id'],
                 backend=row['backend'], image_id=pins['images'].get(row['instance_id']),
                 model_alias=pins['models'].get(row['backend'], {}).get('alias'),
                 model_sha256=pins['models'].get(row['backend'], {}).get('gguf_sha256'),
                 port=pins['models'].get(row['backend'], {}).get('port'))
            for row in plan['assignments']]
    pins['pin_sources'] = dict(sorted(pin_sources.items()))
    return pins, refs


def _record_digests(data):
    """{installed path: hex sha256} from a dist-info RECORD (entries without a sha256 are skipped)."""
    out = {}
    for row in csv.reader(io.StringIO(data.decode('utf-8'))):
        if len(row) >= 2 and row[1].startswith('sha256='):
            b64 = row[1][len('sha256='):]
            try:
                out[row[0]] = base64.urlsafe_b64decode(b64 + '=' * (-len(b64) % 4)).hex()
            except (ValueError, TypeError):
                continue
    return out


def _runtime(reader, refs):
    runtime = dict(pinned_interpreter=PINNED_VENV_REL + '/bin/python',
                   note=('mini-swe-agent source bytes, the dist-info RECORD of each package on the traced request path, '
                         'the traced SDK files themselves (verified against their RECORD digest) and every .pth file '
                         'are bound; other installed files are pinned through their RECORD only'))
    mswea_rel = refs.get('mswea_rel')
    if mswea_rel:
        src_rel = mswea_rel + '/src/minisweagent'
        src = reader.layout.root / src_rel
        runtime['mini_swe_agent_root'] = src_rel
        files = {}
        if src.is_dir() and not src.is_symlink():
            for path in sorted(src.rglob('*')):
                if '__pycache__' in path.parts or path.suffix == '.pyc':
                    continue
                rel = path.relative_to(src).as_posix()
                if path.is_symlink():                        # checked BEFORE is_dir: a symlinked directory too
                    reader.problem('runtime: %s/%s is a symlink' % (src_rel, rel))
                    continue
                if path.is_dir():
                    continue
                data = reader.read(src_rel + '/' + rel, 'runtime')
                if data is not None:
                    files[rel] = sha256_hex(data)
        if not files:
            reader.problem('runtime: pinned mini-swe-agent sources missing under %s' % src_rel)
        runtime['mini_swe_agent_sources'] = files
    venv = reader.layout.root / PINNED_VENV_REL
    sites = sorted(p for p in venv.glob('lib/python*/site-packages'))
    distributions, traced, pth = {}, {}, {}
    if len(sites) != 1:
        reader.problem('runtime: pinned interpreter %s has %d site-packages directories, not exactly one'
                       % (PINNED_VENV_REL, len(sites)))
    else:
        site = sites[0]
        site_rel = site.relative_to(reader.layout.root).as_posix()
        runtime['site_packages'] = site_rel
        for dist in SDK_DISTRIBUTIONS:
            matches = sorted(p for p in site.glob(dist + '-*.dist-info') if p.is_dir())
            if len(matches) != 1:
                reader.problem('runtime: %d installed %s distributions in the pinned interpreter, not exactly one'
                               % (len(matches), dist))
                continue
            data = reader.read('%s/%s/RECORD' % (site_rel, matches[0].name), 'runtime')
            if data is None:
                continue
            distributions[dist] = dict(dist_info=matches[0].name, record_sha256=sha256_hex(data))
            recorded = _record_digests(data)
            for rel in TRACED_SDK_FILES[dist]:
                file_bytes = reader.read('%s/%s' % (site_rel, rel), 'runtime')
                if file_bytes is None:
                    continue
                digest = sha256_hex(file_bytes)
                traced[rel] = digest
                if recorded.get(rel) != digest:
                    reader.problem('runtime: installed %s does not match its %s RECORD digest' % (rel, dist))
        for hook in FORBIDDEN_SITE_HOOKS:
            if (site / hook).exists() or (site / hook).is_symlink():
                reader.problem('runtime: %s in the pinned interpreter would run code at every start' % hook)
        for path in sorted(site.glob('*.pth')):
            data = reader.read('%s/%s' % (site_rel, path.name), 'runtime')
            if data is None:
                continue
            pth[path.name] = sha256_hex(data)
            if path.name == EDITABLE_MSWEA_PTH and mswea_rel:
                lines = [line.strip() for line in data.decode('utf-8', 'replace').splitlines() if line.strip()]
                target = (reader.layout.root / mswea_rel / 'src').resolve()
                if len(lines) != 1 or Path(lines[0]).resolve() != target:
                    reader.problem('runtime: %s does not point at the bound mini-swe-agent source %s/src'
                                   % (EDITABLE_MSWEA_PTH, mswea_rel))
                else:
                    runtime['editable_mini_swe_agent'] = mswea_rel + '/src'
        if EDITABLE_MSWEA_PTH not in pth:
            reader.problem('runtime: the editable mini-swe-agent install %s is missing' % EDITABLE_MSWEA_PTH)
    runtime['sdk_distributions'] = distributions
    runtime['sdk_traced_files'] = dict(sorted(traced.items()))
    runtime['pth_files'] = pth
    return runtime


def _accepted(reader):
    """Lead-accepted (or worker-published) digests of the helpers, the reused wc2 module, the frozen yaml-v1 sources
    and the coding guide. A current file that differs refuses admission, so a pre-launch edit is never frozen."""
    audit = reader.json(ACCEPTED_PINS_AUDIT_REL, 'accepted')
    landmarks = reader.json(ACCEPTED_PINS_LANDMARKS_REL, 'accepted')
    pins = {}
    if audit is not None:
        for rel, digest in sorted((audit.get('source_sha256') or {}).items()):
            if rel.startswith(MODULE_DIR_REL + '/') or rel == CODING_GUIDE_REL:
                pins[rel] = dict(sha256=digest, source=ACCEPTED_PINS_AUDIT_REL + ' source_sha256')
        for rel, digest in sorted(((audit.get('preservation') or {}).get('frozen_runtime_sha256') or {}).items()):
            pins[rel] = dict(sha256=digest, source=ACCEPTED_PINS_AUDIT_REL + ' preservation.frozen_runtime_sha256')
    if landmarks is not None:
        published = landmarks.get('source_pins') or {}
        for rel, digest in sorted((published.get('frozen_yaml_v1_sources_unchanged') or {}).items()):
            pins.setdefault(rel, dict(sha256=digest, source=ACCEPTED_PINS_LANDMARKS_REL +
                                      ' source_pins.frozen_yaml_v1_sources_unchanged'))
        wc = MODULE_DIR_REL + '/workspace_capture.py'
        if (published.get('new_modules') or {}).get(wc):
            pins.setdefault(wc, dict(sha256=published['new_modules'][wc],
                                     source=ACCEPTED_PINS_LANDMARKS_REL + ' source_pins.new_modules'))
    required = [MODULE_DIR_REL + '/' + name for name in ACCEPTED_HELPERS + REUSED_MODULES + FROZEN_REFERENCE]
    for rel in required + [CODING_GUIDE_REL]:
        if rel not in pins:
            reader.problem('accepted: no accepted digest is published for %s' % rel)
    for rel, pin in sorted(pins.items()):
        data = reader.read(rel, 'accepted')
        if data is None:
            continue
        pin['current_sha256'] = sha256_hex(data)
        if pin['current_sha256'] != pin['sha256']:
            reader.problem('accepted: %s is %s, not the accepted %s (%s)'
                           % (rel, pin['current_sha256'], pin['sha256'], pin['source']))
    sources = {rel: sha256_hex(reader.cache[rel]) for rel in (ACCEPTED_PINS_AUDIT_REL, ACCEPTED_PINS_LANDMARKS_REL)
               if reader.cache.get(rel) is not None}
    return dict(sources=sources, pins=pins)


def _settings(reader, refs, cohort_ns):
    ep, rn, base = refs['episode'], refs['runner'], refs['base'] or {}
    fs = rn.get('FROZEN_SETTINGS') or {}
    ns = cohort_ns or {}
    decoding = ((base.get('episodes') or {}).get('decoding') or {})
    episodes = base.get('episodes') or {}
    h, attempts = ep.get('H'), ep.get('ATTEMPTS_PER_CALL')
    settings = dict(
        horizon_h=h, step_limit=fs.get('step_limit'), temperature=fs.get('temperature'), max_tokens=ep.get('MAX_TOKENS'),
        context_per_slot=decoding.get('context_per_slot'), physical_attempts_per_logical_call=attempts,
        n_assignments=ns.get('N_ASSIGNMENTS'), max_physical_requests=ns.get('MAX_PHYSICAL_REQUESTS'),
        max_physical_requests_per_assignment=h * attempts if _int(h) and _int(attempts) else None,
        command_timeout_s=ep.get('CMD_TIMEOUT'), request_timeout_s=ep.get('REQUEST_TIMEOUT_S'),
        episode_wall_s=ep.get('WALL_S'), cost_limit=fs.get('cost_limit'), max_cues_per_episode=1,
        configuration_binding=ep.get('CONFIGURATION_BINDING'), endpoint=ENDPOINT,
        sources=dict(horizon_h='pilot_episode.H', step_limit='pilot_runner.FROZEN_SETTINGS',
                     temperature='pilot_runner.FROZEN_SETTINGS', max_tokens='pilot_episode.MAX_TOKENS',
                     context_per_slot='base spec episodes.decoding.context_per_slot',
                     physical_attempts_per_logical_call='pilot_episode.ATTEMPTS_PER_CALL',
                     n_assignments='cue_cohort.N_ASSIGNMENTS', max_physical_requests='cue_cohort.MAX_PHYSICAL_REQUESTS',
                     max_physical_requests_per_assignment='H x physical attempts per logical call'))
    for key, expected in CONTRACT_SETTINGS.items():
        if not _same(settings.get(key), expected):
            reader.problem('settings: %s is %r, not the frozen %r' % (key, settings.get(key), expected))
    checks = (('pilot_runner.FROZEN_SETTINGS.step_limit', fs.get('step_limit'), h),
              ('pilot_runner.FROZEN_SETTINGS.max_tokens', fs.get('max_tokens'), ep.get('MAX_TOKENS')),
              ('pilot_runner.FROZEN_SETTINGS.physical_attempts_per_call_max', fs.get('physical_attempts_per_call_max'),
               attempts),
              ('pilot_runner.FROZEN_SETTINGS.command_timeout_s', fs.get('command_timeout_s'), ep.get('CMD_TIMEOUT')),
              ('pilot_runner.FROZEN_SETTINGS.wall_time_limit_seconds', fs.get('wall_time_limit_seconds'),
               ep.get('WALL_S')),
              ('pilot_runner.FROZEN_SETTINGS.request_timeout_s', fs.get('request_timeout_s'),
               ep.get('REQUEST_TIMEOUT_S')),
              ('base spec temperature', decoding.get('temperature'), fs.get('temperature')),
              ('base spec max_tokens', decoding.get('max_tokens'), ep.get('MAX_TOKENS')),
              ('base spec logical_call_limit', episodes.get('logical_call_limit'), h),
              ('base spec physical_attempts_per_logical_call_max',
               episodes.get('physical_attempts_per_logical_call_max'), attempts),
              ('base spec episode_wall_seconds', episodes.get('episode_wall_seconds'), ep.get('WALL_S')),
              ('pilot_runner llama-server -c', refs.get('server_context'), decoding.get('context_per_slot')),
              ('cue_cohort.H', ns.get('H'), h), ('cue_cohort.ATTEMPTS_PER_CALL', ns.get('ATTEMPTS_PER_CALL'), attempts))
    for label, found, expected in checks:
        if not _same(found, expected):
            reader.problem('settings: %s is %r, the frozen source says %r' % (label, found, expected))
    if (_int(ns.get('N_ASSIGNMENTS')) and _int(h) and _int(attempts)
            and ns.get('MAX_PHYSICAL_REQUESTS') != ns['N_ASSIGNMENTS'] * h * attempts):
        reader.problem('settings: cue_cohort MAX_PHYSICAL_REQUESTS is not assignments x H x attempts')
    return settings


ENFORCED_TERMINAL = dict(PHASE_WINDOW_S='post_inference_cleanup_window_s', DIAGNOSTIC_MAX_S='diagnostic_max_s',
                         CLEANUP_RESERVE_S='cleanup_reserve_min_s', SUBPROCESS_MAX_S='diagnostic_subprocess_timeout_max_s',
                         EXISTING_CLEANUP_ALLOWANCE_S='child_cleanup_grace_s')
ENFORCED_TRANSPORT = dict(BODY_CAP_BYTES='request_body_cap_bytes',
                          COHORT_RAW_RESERVATION_BYTES='cohort_raw_body_reservation_bytes',
                          START_FREE_ABOVE_RESERVE_BYTES='start_free_space_above_host_reserve_bytes',
                          PUBLIC_WHOLE_MAX_BYTES='public_request_whole_max_bytes',
                          PUBLIC_HEAD_BYTES='public_preview_head_bytes', PUBLIC_TAIL_BYTES='public_preview_tail_bytes',
                          PUBLIC_RECORD_CAP_BYTES='public_request_receipt_cap_bytes')
FORBIDDEN_CAPTURE_KEYWORDS = ('sends_per_query_attempt', 'accounting_fixture', 'horizon', 'attempts_per_call')


def _enforced(reader, sources, cohort_ns):
    """The bounds as the ENFORCING modules state them, checked against the contract (not restated here)."""
    out, env = dict(cue_terminal={}, cue_transport={}, cue_episode_capture_keywords=None), {}
    if cohort_ns is not None:
        env['CC.MAX_PHYSICAL_REQUESTS'] = cohort_ns.get('MAX_PHYSICAL_REQUESTS')
    contract = dict(CONTRACT_DEADLINES, **{k: v for k, v in CONTRACT_STORAGE.items() if _int(v)})
    for module, table in (('cue_terminal', ENFORCED_TERMINAL), ('cue_transport', ENFORCED_TRANSPORT)):
        source = sources.get(module + '.py')
        if source is None:
            continue
        try:
            found = arithmetic_constants(source, set(table), env)
        except SyntaxError:
            reader.problem('enforced: %s.py cannot be parsed' % module)
            continue
        for name, key in sorted(table.items()):
            out[module][name] = found.get(name)
            if not _same(found.get(name), contract[key]):
                reader.problem('enforced: %s.%s is %r, the contract says %s=%r'
                               % (module, name, found.get(name), key, contract[key]))
    transport = sources.get('cue_transport.py')
    if transport is not None:
        sends = arithmetic_constants(transport, {'SENDS_PER_QUERY_ATTEMPT'}).get('SENDS_PER_QUERY_ATTEMPT')
        out['cue_transport']['SENDS_PER_QUERY_ATTEMPT'] = sends
        if not _same(sends, 1):
            reader.problem('enforced: cue_transport.SENDS_PER_QUERY_ATTEMPT is %r, not one send per query attempt'
                           % (sends,))
    episode = sources.get('cue_episode.py')
    if episode is not None:
        try:
            calls = call_keywords(episode, 'CueTransportCapture')
        except SyntaxError:
            calls = None
            reader.problem('enforced: cue_episode.py cannot be parsed')
        out['cue_episode_capture_keywords'] = calls
        for keywords in calls or []:
            for name in FORBIDDEN_CAPTURE_KEYWORDS:
                if name in keywords:
                    reader.problem('enforced: cue_episode passes %s to CueTransportCapture; the frozen values are the '
                                   'only admitted ones' % name)
    return out


def _deadlines(reader, refs):
    ep, rn, base = refs['episode'], refs['runner'], refs['base'] or {}
    deadlines = dict(
        episode_wall_s=ep.get('WALL_S'), block_cap_s=rn.get('BLOCK_CAP'), kill_margin_s=rn.get('KILL_MARGIN'),
        model_switch_allowance_s=rn.get('SWITCH_ALLOWANCE'), child_cleanup_grace_s=rn.get('CHILD_CLEANUP_GRACE'),
        server_cleanup_reserve_s=rn.get('SERVER_CLEANUP_RESERVE'), request_timeout_s=ep.get('REQUEST_TIMEOUT_S'),
        command_timeout_s=ep.get('CMD_TIMEOUT'),
        evaluator_attempt_timeout_s=(base.get('episodes') or {}).get('evaluator_attempt_timeout_seconds'),
        diagnostic_max_s=CONTRACT_DEADLINES['diagnostic_max_s'],
        post_inference_cleanup_window_s=CONTRACT_DEADLINES['post_inference_cleanup_window_s'],
        cleanup_reserve_min_s=CONTRACT_DEADLINES['cleanup_reserve_min_s'],
        diagnostic_subprocess_timeout_max_s=CONTRACT_DEADLINES['diagnostic_subprocess_timeout_max_s'],
        rules=dict(DEADLINE_RULES))
    for key, expected in CONTRACT_DEADLINES.items():
        if not _same(deadlines.get(key), expected):
            reader.problem('deadlines: %s is %r, not the frozen %r' % (key, deadlines.get(key), expected))
    if not _same(rn.get('EPISODE_WALL'), ep.get('WALL_S')):
        reader.problem('deadlines: pilot_runner.EPISODE_WALL disagrees with pilot_episode.WALL_S')
    if not _same((base.get('shared_host') or {}).get('block_elapsed_cap_seconds'), rn.get('BLOCK_CAP')):
        reader.problem('deadlines: base spec block cap disagrees with pilot_runner.BLOCK_CAP')
    return deadlines


def _rules():
    return dict(
        one_cohort=COHORT, namespace=NAMESPACE_REL,
        order='the frozen 12 assignments are walked strictly by position (pair order B,C,C,B,B,C); no reordering, '
              'skipping, duplicate, replacement, repeat or extension',
        request_cap='12 assignments x H24 x 2 physical attempts = 576 physical requests in total across all '
                    'sessions and resumes; 48 per assignment; an unknown count reserves 48',
        stops='only the predeclared stop codes; none reads an episode outcome', stop_codes=dict(STOP_CODES),
        infrastructure_stop='while storage/receipt integrity is unresolved no new assignment is dispatched; the '
                            'affected and remaining assignment states are recorded explicitly and an explicit '
                            'reconciliation record is required before dispatch resumes; nothing is re-dispatched',
        runtime_state=[BINDING_FILE, LEDGER_FILE, 'one run directory per recorded assignment start'],
        not_runtime_state='legacy result directories, report files, published projections and symlinks are refused',
        endpoint=ENDPOINT,
        comparison='fixed-order descriptive DEV comparison on deliberately selected exposed tasks; not a causal '
                   'effect estimate, not confirmation; all 12 assignments stay in operational accounting')


def compute_binding(layout=None):
    """(binding, problems). Read-only: nothing is created or written. A binding with problems can be compared with
    a frozen one, but it is never frozen or admitted."""
    layout = layout if isinstance(layout, Layout) else Layout(layout)
    reader = _Reader(layout)
    modules, roles, sources = _modules(reader)
    detector_ns = _exec_bound(reader, 'cue_detector.py', sources.get('cue_detector.py'))
    cohort_ns = _exec_bound(reader, 'cue_cohort.py', sources.get('cue_cohort.py'))
    cue, detector = _cue_and_detector(reader, detector_ns)
    plan = _plan(reader, cohort_ns, detector)
    guide_bytes = reader.read(CODING_GUIDE_REL, 'coding_guide')
    coding_guide = None if guide_bytes is None else dict(path=CODING_GUIDE_REL, sha256=sha256_hex(guide_bytes),
                                                         bytes=len(guide_bytes))
    if guide_bytes is not None and not guide_bytes.strip():
        reader.problem('coding_guide: %s is empty' % CODING_GUIDE_REL)
    pins, refs = _pins(reader, plan)
    runtime = _runtime(reader, refs)
    settings = _settings(reader, refs, cohort_ns)
    deadlines = _deadlines(reader, refs)
    accepted = _accepted(reader)
    enforced = _enforced(reader, sources, cohort_ns)
    binding = dict(kind=BINDING_KIND, version=BINDING_VERSION, request=REQUEST, cohort=COHORT,
                   namespace=NAMESPACE_REL, contract=CONTRACT_REF, modules=dict(sorted(modules.items())),
                   module_roles=roles, cue=cue, detector=detector, coding_guide=coding_guide, plan=plan, pins=pins,
                   accepted_sources=accepted, runtime=runtime, settings=settings, deadlines=deadlines,
                   storage=dict(CONTRACT_STORAGE), enforced_bounds=enforced, rules=_rules())
    binding = json.loads(canonical(binding))
    binding['binding_sha256'] = sha256_hex(canonical(binding))
    return binding, list(reader.problems)


def binding_digest(binding):
    return sha256_hex(canonical({k: v for k, v in binding.items() if k != 'binding_sha256'}))


def diff_bindings(frozen, current, path=''):
    """Every bound-input path whose value differs, e.g. 'modules/cue_transport.py' or 'coding_guide/sha256'."""
    if isinstance(frozen, dict) and isinstance(current, dict):
        out = []
        for key in sorted(set(frozen) | set(current)):
            if key == 'binding_sha256' and not path:
                continue
            sub = key if not path else path + '/' + key
            if key not in frozen or key not in current:
                out.append(sub)
            else:
                out.extend(diff_bindings(frozen[key], current[key], sub))
        return out
    return [] if frozen == current else [path or '/']


def plan_rows(binding):
    """The frozen assignments with their pins, in position order (what the runner walks)."""
    pins = {row['position']: row for row in binding['pins'].get('assignment_pins', [])}
    return [dict(row, image_id=pins[row['position']]['image_id'], model_alias=pins[row['position']]['model_alias'],
                 model_sha256=pins[row['position']]['model_sha256'], port=pins[row['position']]['port'])
            for row in binding['plan']['assignments']]


def bound_plan(layout=None):
    """The 12 frozen assignments straight from the layout's cue_cohort.py bytes (for listing; no admission)."""
    layout = layout if isinstance(layout, Layout) else Layout(layout)
    reader = _Reader(layout)
    source = reader.read(MODULE_DIR_REL + '/cue_cohort.py', 'plan')
    ns = _exec_bound(reader, 'cue_cohort.py', source)
    try:
        return [dict(row) for row in ns['frozen_plan']()['assignments']]
    except Exception as exc:  # noqa: BLE001
        reasons = reader.problems or ['plan: cue_cohort.frozen_plan failed (%s)' % type(exc).__name__]
        raise AdmissionRefused(reasons, problems=reader.problems) from exc


# ------------------------------------------------------------------ the runtime ledger

COMMON_FIELDS = frozenset({'seq', 'event', 'cohort', 'binding_sha256', 'prev_sha256', 'utc'})
EVENT_FIELDS = {
    'ledger_opened': {'namespace', 'plan_sha256', 'n_assignments', 'max_physical_requests', 'note'},
    'session_start': {'session', 'kind', 'counted_physical_requests_before', 'episode_function'},
    'assignment_start': {'session', 'position', 'assignment_id', 'run_id', 'request_reservation',
                         'counted_physical_requests_before'},
    'assignment_terminal': {'session', 'position', 'assignment_id', 'run_id', 'physical_requests_reported',
                            'physical_requests_reported_raw', 'budget_consumed', 'counted_requests',
                            'request_accounting', 'storage_integrity', 'storage_integrity_detail', 'exit_status'},
    'assignment_error': {'session', 'position', 'assignment_id', 'run_id', 'error_class', 'detail',
                         'counted_requests', 'run_dir_created'},
    'queue_stop': {'session', 'stop_id', 'code', 'kind', 'reason', 'outcome_driven', 'next_position', 'affected',
                   'remaining', 'assignment_states', 'counted_physical_requests'},
    'reconciliation': {'session', 'resolves', 'note'},
    'torn_tail_repair': {'session', 'fragment_file', 'fragment_sha256', 'fragment_bytes', 'note'},
    'session_end': {'session', 'dispatched_positions', 'counted_physical_requests', 'complete'},
}


def account_requests(value, consumed, per_assignment=CONTRACT_SETTINGS['max_physical_requests_per_assignment']):
    """(reported, reported_raw, counted, accounting) for the physical-request count an episode returned. An integer
    is kept as reported; anything else that is not None is kept only as a bounded repr and is invalid."""
    if value is None or _int(value):
        counted, accounting = count_requests(value, consumed, per_assignment)
        return value, None, counted, accounting
    return None, repr(value)[:64], per_assignment, 'invalid'


def count_requests(reported, consumed, per_assignment=CONTRACT_SETTINGS['max_physical_requests_per_assignment']):
    """(counted, accounting) for one ended assignment. Only a valid reported count that agrees with any budget use is
    clean ('reported'); unknown, invalid or disagreeing counts reserve conservatively and are unresolved."""
    if reported is None:
        return per_assignment, 'unknown_reserved'
    if not _int(reported) or not 0 <= reported <= per_assignment:
        return per_assignment, 'invalid'
    if _int(consumed) and consumed > 0 and consumed != reported:
        return min(per_assignment, max(reported, consumed)), 'discrepancy'
    return reported, ACCOUNTING_CLEAN


class QueueLedger:
    """State machine over the ledger events. `apply` validates an event completely before changing any state, so an
    invalid event can neither be loaded nor appended."""

    def __init__(self, binding):
        self.binding_sha256 = binding['binding_sha256']
        self.namespace = binding['namespace']
        self.plan_sha256 = binding['plan']['plan_sha256']
        self.rows = [dict(position=row['position'], assignment_id=row['assignment_id'])
                     for row in binding['plan']['assignments']]
        self.n = len(self.rows)
        self.per_assignment = binding['settings']['max_physical_requests_per_assignment']
        self.cap = binding['settings']['max_physical_requests']
        self.seq = 0
        self.last_sha = None
        self.session = 0
        self.open_session = None
        self.stopped_sessions = set()
        self.starts, self.ends = {}, {}
        self.run_ids = set()
        self.stops = []
        self.reconciled = {}
        self.events = []
        self.line_shas = []

    # ---------------------------------------------------------------- derived state
    def state_of(self, position):
        if position not in self.starts:
            return UNSTARTED
        end = self.ends.get(position)
        if end is None:
            return INTERRUPTED_RECONCILED if ('interrupted-%d' % position) in self.reconciled else INTERRUPTED
        if end['event'] == 'assignment_error':
            return EPISODE_ERROR
        if end['storage_integrity'] == STORAGE_RESOLVED and end['request_accounting'] == ACCOUNTING_CLEAN:
            return TERMINAL
        return TERMINAL_UNRESOLVED

    def counted(self, position):
        if position not in self.starts:
            return 0
        end = self.ends.get(position)
        return self.per_assignment if end is None else end['counted_requests']

    def counted_total(self):
        return sum(self.counted(row['position']) for row in self.rows)

    def row(self, position):
        return dict(position=position, assignment_id=self.rows[position - 1]['assignment_id'],
                    state=self.state_of(position))

    def snapshot(self):
        return [dict(self.row(r['position']), counted_requests=self.counted(r['position'])) for r in self.rows]

    def unstarted(self):
        return [self.row(r['position']) for r in self.rows if r['position'] not in self.starts]

    def next_position(self):
        position = len(self.starts) + 1
        return position if position <= self.n else None

    def issues(self):
        """Unresolved integrity issues; while any exists no assignment may be dispatched."""
        out = []
        for position in sorted(self.starts):
            state = self.state_of(position)
            if state == INTERRUPTED:
                out.append(dict(id='interrupted-%d' % position, position=position,
                                reason='assignment started without an end record (interrupted); it is never '
                                       're-dispatched; reconcile before any further dispatch'))
            elif state in (EPISODE_ERROR, TERMINAL_UNRESOLVED) and ('integrity-%d' % position) not in self.reconciled:
                out.append(dict(id='integrity-%d' % position, position=position,
                                reason='storage/receipt/accounting integrity unresolved for this assignment'))
        for stop in self.stops:
            if (stop['kind'] == KIND_INFRASTRUCTURE and stop['code'] not in STOPS_WITH_AFFECTED_ASSIGNMENT
                    and stop['stop_id'] not in self.reconciled):
                out.append(dict(id=stop['stop_id'], position=None, reason='%s: %s' % (stop['code'], stop['reason'])))
        return out

    def complete(self):
        return self.next_position() is None

    # ---------------------------------------------------------------- validation
    def _refuse(self, ev, text):
        raise LedgerRefused(['ledger seq %s (%s): %s' % (ev.get('seq'), ev.get('event'), text)])

    def apply(self, ev, line_sha):
        if not isinstance(ev, dict):
            raise LedgerRefused(['ledger record %d is not a JSON object' % (self.seq + 1)])
        kind = ev.get('event')
        if kind not in EVENT_FIELDS:
            self._refuse(ev, 'unknown event; a report or projection is not a runtime ledger record')
        expected = COMMON_FIELDS | EVENT_FIELDS[kind]
        if set(ev) != expected:
            self._refuse(ev, 'fields %s differ from the ledger schema' % sorted(set(ev) ^ expected))
        if not _int(ev['seq']) or ev['seq'] != self.seq + 1:
            self._refuse(ev, 'sequence number is not %d' % (self.seq + 1))
        if ev['prev_sha256'] != self.last_sha:
            self._refuse(ev, 'hash chain broken (a record was removed, reordered or edited)')
        if ev['cohort'] != COHORT or ev['binding_sha256'] != self.binding_sha256:
            self._refuse(ev, 'record belongs to another cohort or binding; one cohort only')
        if not isinstance(ev['utc'], str):
            self._refuse(ev, 'utc is not a string')
        if (kind == 'ledger_opened') != (ev['seq'] == 1):
            self._refuse(ev, 'the ledger must open with exactly one ledger_opened record')
        getattr(self, '_apply_' + kind)(ev)
        self.seq = ev['seq']
        self.last_sha = line_sha
        self.events.append(ev)
        self.line_shas.append(line_sha)

    def _in_open_session(self, ev):
        if self.open_session is None or ev['session'] != self.open_session:
            self._refuse(ev, 'not inside the open session')

    def _apply_ledger_opened(self, ev):
        if (ev['namespace'] != self.namespace or ev['plan_sha256'] != self.plan_sha256
                or ev['n_assignments'] != self.n or ev['max_physical_requests'] != self.cap):
            self._refuse(ev, 'ledger header does not match the frozen binding')

    def _apply_session_start(self, ev):
        if ev['session'] != self.session + 1 or ev['kind'] not in ('launch', 'resume'):
            self._refuse(ev, 'sessions must be numbered consecutively')
        if (ev['kind'] == 'launch') != (ev['session'] == 1):
            self._refuse(ev, 'only session 1 is a launch; every later session is a resume')
        if not isinstance(ev['episode_function'], str) or not ev['episode_function']:
            self._refuse(ev, 'a session names the episode function it dispatches')
        if ev['counted_physical_requests_before'] != self.counted_total():
            self._refuse(ev, 'session request accounting disagrees with the ledger')
        self.session = ev['session']
        self.open_session = ev['session']

    def _apply_session_end(self, ev):
        self._in_open_session(ev)
        dispatched = sorted(p for p, start in self.starts.items() if start['session'] == ev['session'])
        if (ev['dispatched_positions'] != dispatched or ev['counted_physical_requests'] != self.counted_total()
                or ev['complete'] is not self.complete()):
            self._refuse(ev, 'session summary disagrees with the ledger')
        self.open_session = None

    def _apply_assignment_start(self, ev):
        self._in_open_session(ev)
        position = ev['position']
        if ev['session'] in self.stopped_sessions:
            self._refuse(ev, 'dispatch after a queue stop in the same session')
        if not _int(position) or not 1 <= position <= self.n:
            self._refuse(ev, 'position %r is outside the frozen 1..%d frame (no extension)' % (position, self.n))
        if position in self.starts:
            self._refuse(ev, 'assignment %d was already dispatched (no duplicate or repeat)' % position)
        if position != self.next_position():
            self._refuse(ev, 'assignment %d dispatched out of the frozen order (next is %s)'
                         % (position, self.next_position()))
        if ev['assignment_id'] != self.rows[position - 1]['assignment_id']:
            self._refuse(ev, 'assignment id %r is not the frozen assignment %r (no replacement)'
                         % (ev['assignment_id'], self.rows[position - 1]['assignment_id']))
        match = RUN_ID.match(ev['run_id']) if isinstance(ev['run_id'], str) else None
        if not match or match.group('assignment') != ev['assignment_id'] or ev['run_id'] in self.run_ids:
            self._refuse(ev, 'run id %r is not a fresh run id of this assignment' % (ev['run_id'],))
        if ev['request_reservation'] != self.per_assignment:
            self._refuse(ev, 'request reservation is not %d' % self.per_assignment)
        if ev['counted_physical_requests_before'] != self.counted_total():
            self._refuse(ev, 'request accounting disagrees with the ledger')
        if self.issues():
            self._refuse(ev, 'dispatch while integrity issues are unresolved: %s'
                         % [issue['id'] for issue in self.issues()])
        if self.counted_total() + self.per_assignment > self.cap:
            self._refuse(ev, 'dispatch would exceed the %d-request cohort cap' % self.cap)
        self.starts[position] = ev
        self.run_ids.add(ev['run_id'])

    def _end_checks(self, ev):
        self._in_open_session(ev)
        position = ev['position']
        start = self.starts.get(position) if _int(position) else None
        if start is None or position in self.ends:
            self._refuse(ev, 'an end record needs exactly one open start')
        if ('interrupted-%d' % position) in self.reconciled:
            self._refuse(ev, 'assignment %d was reconciled as interrupted' % position)
        if (ev['session'] != start['session'] or ev['run_id'] != start['run_id']
                or ev['assignment_id'] != start['assignment_id']):
            self._refuse(ev, 'end record does not match its start')
        counted = ev['counted_requests']
        if not _int(counted) or not 0 <= counted <= self.per_assignment:
            self._refuse(ev, 'counted_requests %r outside 0..%d' % (counted, self.per_assignment))
        if self.counted_total() - self.per_assignment + counted > self.cap:
            self._refuse(ev, 'cohort request total would exceed %d' % self.cap)
        return position

    def _apply_assignment_terminal(self, ev):
        position = self._end_checks(ev)
        if ev['storage_integrity'] not in (STORAGE_RESOLVED, STORAGE_UNRESOLVED):
            self._refuse(ev, 'storage_integrity must be resolved or unresolved')
        consumed = ev['budget_consumed']
        if not _int(consumed) or not 0 <= consumed <= self.per_assignment:
            self._refuse(ev, 'budget_consumed %r outside 0..%d' % (consumed, self.per_assignment))
        reported = ev['physical_requests_reported']
        if reported is not None and not _int(reported):
            self._refuse(ev, 'physical_requests_reported must be an integer or null')
        if ev['physical_requests_reported_raw'] is not None and not isinstance(ev['physical_requests_reported_raw'],
                                                                               str):
            self._refuse(ev, 'physical_requests_reported_raw must be a string or null')
        if ev['physical_requests_reported_raw'] is not None:
            if reported is not None:
                self._refuse(ev, 'a reported integer and a raw invalid value cannot both be present')
            counted, accounting = self.per_assignment, 'invalid'
        else:
            counted, accounting = count_requests(reported, consumed, self.per_assignment)
        if (counted, accounting) != (ev['counted_requests'], ev['request_accounting']):
            self._refuse(ev, 'request accounting %r/%r is not the declared rule (%r/%r)'
                         % (ev['counted_requests'], ev['request_accounting'], counted, accounting))
        self.ends[position] = ev

    def _apply_assignment_error(self, ev):
        position = self._end_checks(ev)
        if ev['counted_requests'] != self.per_assignment:
            self._refuse(ev, 'an episode error reserves the full %d requests' % self.per_assignment)
        if not isinstance(ev['error_class'], str) or not isinstance(ev['detail'], str):
            self._refuse(ev, 'error_class and detail must be strings')
        if type(ev['run_dir_created']) is not bool:
            self._refuse(ev, 'run_dir_created must state whether the run directory exists')
        self.ends[position] = ev

    def _apply_queue_stop(self, ev):
        self._in_open_session(ev)
        code = ev['code']
        if code not in STOP_CODES or ev['kind'] != STOP_CODES[code]:
            self._refuse(ev, 'stop code %r is not a predeclared stop' % (code,))
        if ev['outcome_driven'] is not False:
            self._refuse(ev, 'a queue stop is never outcome-driven')
        if ev['stop_id'] != 'stop-%d' % ev['seq'] or ev['session'] in self.stopped_sessions:
            self._refuse(ev, 'one stop per session, identified by its sequence number')
        if (ev['next_position'] != self.next_position() or ev['remaining'] != self.unstarted()
                or ev['assignment_states'] != self.snapshot()
                or ev['counted_physical_requests'] != self.counted_total()):
            self._refuse(ev, 'the stop record does not preserve the current assignment states exactly')
        affected = ev['affected']
        if not isinstance(affected, list) or any(not isinstance(row, dict) or not _int(row.get('position'))
                                                 or not 1 <= row['position'] <= self.n
                                                 or row != self.row(row['position']) for row in affected):
            self._refuse(ev, 'affected assignments must be current assignment rows')
        if (code in STOPS_WITH_AFFECTED_ASSIGNMENT) != bool(affected):
            self._refuse(ev, 'stop %s must %sname an affected assignment'
                         % (code, '' if code in STOPS_WITH_AFFECTED_ASSIGNMENT else 'not '))
        if not isinstance(ev['reason'], str) or not ev['reason']:
            self._refuse(ev, 'a stop needs its reason')
        self.stops.append(ev)
        self.stopped_sessions.add(ev['session'])

    def _apply_reconciliation(self, ev):
        if ev['session'] is not None:
            self._in_open_session(ev)
        open_ids = {issue['id'] for issue in self.issues()}
        if ev['resolves'] not in open_ids:
            self._refuse(ev, 'reconciliation must resolve an open issue (%s)' % sorted(open_ids))
        if not isinstance(ev['note'], str) or not ev['note'].strip() or len(ev['note']) > 2000:
            self._refuse(ev, 'a reconciliation needs a non-empty note of at most 2000 characters')
        self.reconciled[ev['resolves']] = ev['seq']

    def _apply_torn_tail_repair(self, ev):
        if ev['session'] is not None:
            self._refuse(ev, 'a torn-tail repair is an operator record outside any session')
        match = TORN_FRAGMENT.match(ev['fragment_file']) if isinstance(ev['fragment_file'], str) else None
        if not match or int(match.group(1)) != ev['seq']:
            self._refuse(ev, 'the torn fragment file must be named for this record\'s sequence number')
        if not _int(ev['fragment_bytes']) or ev['fragment_bytes'] < 1 or not isinstance(ev['fragment_sha256'], str):
            self._refuse(ev, 'the torn fragment needs its byte count and digest')
        if not isinstance(ev['note'], str) or not ev['note'].strip() or len(ev['note']) > 2000:
            self._refuse(ev, 'a torn-tail repair needs a non-empty note of at most 2000 characters')
        self.open_session = None                      # the torn write ended its session


def load_ledger(path, binding):
    """Parse and validate the whole ledger. Refuses a torn, edited, reordered or foreign ledger."""
    try:
        data = Path(path).read_bytes()
    except OSError as exc:
        raise LedgerRefused(['ledger unreadable (%s)' % type(exc).__name__]) from exc
    if not data:
        raise LedgerRefused(['ledger is empty: the namespace was not opened by a complete launch'])
    if not data.endswith(b'\n'):
        raise LedgerRefused(['ledger has a torn final record; preserve it with repair_torn_tail(layout, note) '
                             'before any resume'])
    ledger = QueueLedger(binding)
    for number, line in enumerate(data.split(b'\n')[:-1], start=1):
        try:
            ev = json.loads(line)
        except ValueError as exc:
            raise LedgerRefused(['ledger record %d is not JSON' % number]) from exc
        if line != canonical(ev):
            raise LedgerRefused(['ledger record %d is not in canonical form (edited)' % number])
        ledger.apply(ev, sha256_hex(line + b'\n'))
    return ledger


# ------------------------------------------------------------------ namespace contents

def _classify_entry(name, path):
    if path.is_symlink():
        return 'symlink %s: runtime state must be regular files/directories created by the cue-v1 runner' % name
    if path.is_dir():
        if (any(marker in name for marker in LEGACY_RUN_MARKERS)
                or ((path / 'episode.json').exists() and not RUN_ID.match(name))):
            return 'legacy result directory %s cannot be cue-v1 runtime state' % name
        return 'directory %s is not a recorded cue-v1 assignment run' % name
    if REPORT_OR_PROJECTION.search(name):
        return 'report/projection file %s cannot be runtime state' % name
    return 'unrecognized file %s is not cue-v1 runtime state' % name


def _check_run_dir(run_dir):
    """Only the files a cue-v1 episode writes; never a symlink, a report or a legacy result, at any depth."""
    reasons = []
    for path in sorted(run_dir.rglob('*')):
        rel = path.relative_to(run_dir)
        if path.is_symlink():
            reasons.append('symlink %s/%s inside a run directory' % (run_dir.name, rel.as_posix()))
        elif path.is_dir():
            if rel.as_posix() != RECEIPTS_SUBDIR:
                reasons.append('directory %s/%s is not cue-v1 episode output' % (run_dir.name, rel.as_posix()))
        elif len(rel.parts) == 1 and rel.name in RUN_DIR_FILES:
            continue
        elif len(rel.parts) == 2 and rel.parts[0] == RECEIPTS_SUBDIR and RUN_DIR_RECEIPT.match(rel.name):
            continue
        else:
            reasons.append('file %s/%s is not cue-v1 episode output' % (run_dir.name, rel.as_posix()))
    return reasons


def _check_entries(layout, ledger):
    reasons = []
    run_ids = {start['run_id'] for start in ledger.starts.values()}
    fragments = {ev['fragment_file'] for ev in ledger.events if ev['event'] == 'torn_tail_repair'}
    for path in sorted(layout.out.iterdir()):
        name = path.name
        if name in (BINDING_FILE, LEDGER_FILE, HEAD_FILE, HEAD_TMP) and path.is_file() and not path.is_symlink():
            continue
        if name in fragments and path.is_file() and not path.is_symlink():
            continue
        if name in run_ids and path.is_dir() and not path.is_symlink():
            reasons.extend(_check_run_dir(path))
            continue
        reasons.append(_classify_entry(name, path))
    for position, end in ledger.ends.items():
        needed = end['event'] == 'assignment_terminal' or end.get('run_dir_created') is True
        run_dir = layout.out / end['run_id']
        if needed and (not run_dir.is_dir() or run_dir.is_symlink()):
            reasons.append('run directory %s of ended assignment %d is missing' % (end['run_id'], position))
    return reasons


def _check_receipts(layout, ledger):
    """A clean terminal assignment's receipt set must still be complete (corrupt-receipt detection at resume)."""
    import cue_transport as CT      # pure core only; the httpx adapter is not needed to read receipts
    reasons = []
    for position, end in sorted(ledger.ends.items()):
        if ledger.state_of(position) != TERMINAL:
            continue
        public = layout.out / end['run_id'] / RECEIPTS_SUBDIR
        private = layout.root / PRIVATE_RECEIPTS_REL / end['run_id']
        if not public.is_dir():
            continue
        state = CT.read_only_completeness(private, public, cohort=COHORT, run_id=end['run_id'])
        if not state.get('complete'):
            problems = (state.get('invalid_records') or []) + (state.get('invalid_refusal_records') or [])
            reasons.append('the receipt set of clean terminal assignment %d (%s) is no longer complete: %s'
                           % (position, end['run_id'], json.dumps(problems[:4], sort_keys=True)[:600]))
    return reasons


def _check_head(layout, ledger):
    """The head file must name the ledger's last record (or the one before, after a crash between the ledger append
    and the head replacement). A ledger shorter than its head was truncated."""
    path = layout.out / HEAD_FILE
    if path.is_symlink() or not path.is_file():
        return ['%s lacks %s: the ledger cannot be checked for truncation' % (NAMESPACE_REL, HEAD_FILE)]
    try:
        head = json.loads(path.read_bytes())
    except ValueError:
        return ['%s is not valid JSON' % HEAD_FILE]
    if not isinstance(head, dict) or head.get('cohort') != COHORT or head.get('binding_sha256') != ledger.binding_sha256:
        return ['%s does not belong to this cohort binding' % HEAD_FILE]
    seq, sha = head.get('seq'), head.get('last_sha256')
    if seq == ledger.seq and sha == ledger.last_sha:
        return []
    if seq == ledger.seq - 1 and seq >= 1 and sha == ledger.line_shas[seq - 1]:
        return []                                    # a crash between the ledger append and the head replacement
    return ['%s records seq %r, the ledger ends at seq %d: records were removed from the ledger (truncated) or the '
            'head was edited; nothing is dispatched' % (HEAD_FILE, seq, ledger.seq)]


def _write_head(layout, ledger, clock=time.time):
    text = json.dumps(dict(cohort=COHORT, binding_sha256=ledger.binding_sha256, seq=ledger.seq,
                           last_sha256=ledger.last_sha, utc=utc(clock())), sort_keys=True) + '\n'
    tmp = layout.out / HEAD_TMP
    with open(tmp, 'w') as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, layout.out / HEAD_FILE)
    fd = os.open(layout.out, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _read_frozen_binding(layout):
    path = layout.binding_path
    if path.is_symlink() or not path.is_file():
        reasons = ['%s exists without its write-once %s: not created by a complete live launch'
                   % (NAMESPACE_REL, BINDING_FILE)]
        reasons += [_classify_entry(entry.name, entry) for entry in sorted(layout.out.iterdir())
                    if entry.name != LEDGER_FILE]
        raise AdmissionRefused(reasons)
    try:
        frozen = json.loads(path.read_bytes())
    except ValueError as exc:
        raise AdmissionRefused(['%s is not valid JSON' % BINDING_FILE]) from exc
    if not isinstance(frozen, dict) or frozen.get('binding_sha256') != binding_digest(frozen):
        raise AdmissionRefused(['%s does not match its own binding_sha256 (edited)' % BINDING_FILE])
    if (frozen.get('kind') != BINDING_KIND or frozen.get('cohort') != COHORT
            or frozen.get('namespace') != NAMESPACE_REL):
        raise AdmissionRefused(['%s is not the cue-v1 binding of %s' % (BINDING_FILE, NAMESPACE_REL)])
    return frozen


def check_namespace(layout, out=None):
    """Refuse any output directory other than the new unique cue-v1 namespace (legacy results included)."""
    namespace = layout.out
    if out is not None and Path(out).resolve() != namespace.resolve():
        name = Path(out).name
        legacy = name.startswith('pilot_2026092') or name.startswith('smoke_') or 'yaml_v1' in name
        raise AdmissionRefused(['%s is %s; only %s is admitted'
                                % (name, 'a legacy result directory' if legacy else 'not the cue-v1 namespace',
                                   NAMESPACE_REL)])
    if namespace.is_symlink():
        raise AdmissionRefused(['%s is a symlink; the namespace must be created by a live launch' % NAMESPACE_REL])
    if namespace.exists() and not namespace.is_dir():
        raise AdmissionRefused(['%s exists and is not a directory' % NAMESPACE_REL])
    return namespace


def _ledger_locked(path):
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    except BlockingIOError:
        return True
    finally:
        os.close(fd)


def validate_queue(layout=None, *, out=None, require_dispatchable=False):
    """Validate the ENTIRE fixed queue: namespace, frozen binding against every current bound input, the whole ledger
    and the namespace contents. Read-only. Raises AdmissionRefused on any refusal; with require_dispatchable, also
    when an integrity issue is unresolved or nothing remains to dispatch. Returns the queue report otherwise."""
    layout = layout if isinstance(layout, Layout) else Layout(layout)
    namespace = check_namespace(layout, out)
    current, problems = compute_binding(layout)
    report = dict(cohort=COHORT, namespace=NAMESPACE_REL, launched=namespace.exists(),
                  max_physical_requests=CONTRACT_SETTINGS['max_physical_requests'])
    if not namespace.exists():
        marker = layout.root / LAUNCH_MARKER_REL
        if marker.exists() or marker.is_symlink():
            raise AdmissionRefused(['the cue-v1 cohort was already launched (%s exists) but %s is missing; the frozen '
                                    'cohort is never launched a second time' % (LAUNCH_MARKER_REL, NAMESPACE_REL)])
        if problems:
            raise AdmissionRefused(['launch refused: %s' % p for p in problems], problems=problems)
        rows = current['plan']['assignments']
        report.update(binding_sha256=current['binding_sha256'], binding_status='computed; not yet frozen',
                      assignments=[dict(position=r['position'], assignment_id=r['assignment_id'], state=UNSTARTED,
                                        counted_requests=0) for r in rows],
                      counted_physical_requests=0, request_capacity_remaining=report['max_physical_requests'],
                      sessions=0, blocking=[], complete=False, next_position=1, ledger_locked=False)
        return report
    frozen = _read_frozen_binding(layout)
    changed = diff_bindings(frozen, current)
    if problems or changed:
        reasons = ['bound input changed since the freeze: %s' % path for path in changed]
        reasons += ['current source inconsistency: %s' % p for p in problems]
        classes = sorted({path.split('/', 1)[0] for path in changed})
        if classes:
            reasons.insert(0, 'changed bound input classes: %s' % ', '.join(classes))
        raise AdmissionRefused(reasons, changed=changed, problems=problems)
    if not layout.ledger_path.is_file() or layout.ledger_path.is_symlink():
        raise AdmissionRefused(['%s lacks its runtime ledger %s' % (NAMESPACE_REL, LEDGER_FILE)])
    locked = _ledger_locked(layout.ledger_path)
    if locked and require_dispatchable:
        raise AdmissionRefused(['another cue-v1 runner holds the ledger lock'])
    ledger = load_ledger(layout.ledger_path, frozen)
    entry_reasons = _check_head(layout, ledger) + _check_entries(layout, ledger)
    if entry_reasons:
        raise AdmissionRefused(entry_reasons)
    receipt_reasons = _check_receipts(layout, ledger)
    if receipt_reasons:
        raise AdmissionRefused(receipt_reasons)
    report.update(binding_sha256=frozen['binding_sha256'], binding_status='frozen; every bound input unchanged',
                  assignments=ledger.snapshot(), counted_physical_requests=ledger.counted_total(),
                  request_capacity_remaining=ledger.cap - ledger.counted_total(), sessions=ledger.session,
                  blocking=ledger.issues(), complete=ledger.complete(), next_position=ledger.next_position(),
                  ledger_locked=locked, ledger_seq=ledger.seq)
    if require_dispatchable:
        if report['blocking']:
            raise AdmissionRefused(['dispatch refused while integrity is unresolved: %s (%s)'
                                    % (issue['id'], issue['reason']) for issue in report['blocking']])
        if report['complete']:
            raise AdmissionRefused(['all %d frozen assignments were dispatched; no repeat, replacement or extension'
                                    % ledger.n])
    return report


# ------------------------------------------------------------------ writing (live launch / resume / reconciliation)

def clean_text(value):
    """Every string made valid UTF-8 before it is serialized: a lone surrogate (e.g. surrogateescape-decoded
    subprocess output) becomes its backslash escape instead of breaking the ledger write mid-session."""
    if isinstance(value, str):
        return value.encode('utf-8', 'backslashreplace').decode('utf-8')
    if isinstance(value, dict):
        return {clean_text(k): clean_text(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_text(v) for v in value]
    return value


class LedgerSession:
    """Holds the exclusive ledger lock for one runner session and appends validated, fsynced, hash-chained records."""

    def __init__(self, layout, binding, ledger, fd, clock=time.time):
        self.layout, self.binding, self.ledger, self.fd, self.clock = layout, binding, ledger, fd, clock
        self.broken = False

    def append(self, event, **fields):
        if self.broken:
            raise AdmissionRefused(['the ledger session is broken after a failed write; stop'])
        ev = dict(clean_text(fields), event=event, seq=self.ledger.seq + 1, prev_sha256=self.ledger.last_sha,
                  cohort=COHORT, binding_sha256=self.ledger.binding_sha256, utc=utc(self.clock()))
        line = canonical(ev) + b'\n'
        self.ledger.apply(json.loads(line), sha256_hex(line))
        try:
            os.write(self.fd, line)
            os.fsync(self.fd)
            _write_head(self.layout, self.ledger, self.clock)
        except OSError:
            self.broken = True
            raise
        return ev

    def close(self):
        if self.fd is not None:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_UN)
            finally:
                os.close(self.fd)
                self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False


def _lock(fd):
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(fd)
        raise AdmissionRefused(['another cue-v1 runner holds the ledger lock']) from exc


def launch_session(layout, clock=time.time, *, episode_function):
    """LIVE launch only: write the launch marker, create the unique namespace, freeze the binding write-once, open
    the ledger (locked)."""
    layout = layout if isinstance(layout, Layout) else Layout(layout)
    validate_queue(layout, require_dispatchable=True)
    if layout.out.exists():
        raise AdmissionRefused(['%s already exists: resume instead of launching' % NAMESPACE_REL])
    binding, problems = compute_binding(layout)
    if problems:
        raise AdmissionRefused(['launch refused: %s' % p for p in problems], problems=problems)
    marker = layout.root / LAUNCH_MARKER_REL
    marker.parent.mkdir(parents=True, exist_ok=True)
    with open(marker, 'x') as fh:                       # write-once: a second launch of the cohort is refused
        fh.write(json.dumps(dict(cohort=COHORT, namespace=NAMESPACE_REL, binding_sha256=binding['binding_sha256'],
                                 launched_utc=utc(clock())), sort_keys=True) + '\n')
        fh.flush()
        os.fsync(fh.fileno())
    layout.out.mkdir(parents=True, exist_ok=False)
    with open(layout.binding_path, 'x') as fh:
        fh.write(json.dumps(binding, indent=1, sort_keys=True, ensure_ascii=False) + '\n')
        fh.flush()
        os.fsync(fh.fileno())
    fd = os.open(layout.ledger_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND, 0o644)
    _lock(fd)
    session = LedgerSession(layout, binding, QueueLedger(binding), fd, clock)
    session.append('ledger_opened', namespace=NAMESPACE_REL, plan_sha256=binding['plan']['plan_sha256'],
                   n_assignments=len(binding['plan']['assignments']),
                   max_physical_requests=binding['settings']['max_physical_requests'],
                   note='cue-v1 runtime ledger; the only admitted runtime state besides the binding and run dirs')
    session.append('session_start', session=1, kind='launch', counted_physical_requests_before=0,
                   episode_function=episode_function)
    return session


def resume_session(layout, clock=time.time, *, episode_function):
    """LIVE resume only: validate everything, take the exclusive lock, re-read under the lock, open a session."""
    layout = layout if isinstance(layout, Layout) else Layout(layout)
    report = validate_queue(layout, require_dispatchable=True)
    if not report['launched']:
        raise AdmissionRefused(['%s does not exist: launch instead of resuming' % NAMESPACE_REL])
    frozen = _read_frozen_binding(layout)
    fd = os.open(layout.ledger_path, os.O_WRONLY | os.O_APPEND)
    _lock(fd)
    try:
        ledger = load_ledger(layout.ledger_path, frozen)
        if ledger.seq != report['ledger_seq']:
            raise AdmissionRefused(['the ledger changed between validation and locking'])
    except BaseException:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
        raise
    session = LedgerSession(layout, frozen, ledger, fd, clock)
    # A crashed session left no session_end; the next session_start supersedes it (its interrupted assignment, if
    # any, is already an open issue that validation required to be reconciled).
    session.append('session_start', session=ledger.session + 1, kind='resume',
                   counted_physical_requests_before=ledger.counted_total(), episode_function=episode_function)
    return session


def record_reconciliation(layout, resolves, note, clock=time.time):
    """Explicit operator reconciliation of one open integrity issue (never automatic, never outcome-driven). The
    affected assignment keeps its recorded state and is never re-dispatched."""
    layout = layout if isinstance(layout, Layout) else Layout(layout)
    report = validate_queue(layout)
    if resolves not in {issue['id'] for issue in report['blocking']}:
        raise AdmissionRefused(['%r is not an open issue (%s)' % (resolves, [i['id'] for i in report['blocking']])])
    frozen = _read_frozen_binding(layout)
    fd = os.open(layout.ledger_path, os.O_WRONLY | os.O_APPEND)
    _lock(fd)
    with LedgerSession(layout, frozen, load_ledger(layout.ledger_path, frozen), fd, clock) as session:
        return session.append('reconciliation', session=None, resolves=resolves, note=note)


def repair_torn_tail(layout, note, clock=time.time):
    """Explicit operator repair of a torn final ledger record (a write that failed mid-record, which also ended its
    session: the append raised before the record's action ran). The torn bytes are preserved write-once as
    queue_ledger.torn-<seq>.bin, the ledger is cut back to its last complete record, and a torn_tail_repair record
    naming the fragment's digest is appended. Only a head that names the last complete record is accepted."""
    layout = layout if isinstance(layout, Layout) else Layout(layout)
    check_namespace(layout)
    frozen = _read_frozen_binding(layout)
    fd = os.open(layout.ledger_path, os.O_RDWR | os.O_APPEND)
    _lock(fd)
    try:
        data = layout.ledger_path.read_bytes()
        if data.endswith(b'\n') or not data:
            raise AdmissionRefused(['the ledger has no torn final record'])
        complete, fragment = data[:data.rfind(b'\n') + 1], data[data.rfind(b'\n') + 1:]
        ledger = QueueLedger(frozen)
        for line in complete.split(b'\n')[:-1]:
            ev = json.loads(line)
            if line != canonical(ev):
                raise AdmissionRefused(['a complete ledger record is not canonical; not a torn tail'])
            ledger.apply(ev, sha256_hex(line + b'\n'))
        head_reasons = _check_head(layout, ledger)
        if head_reasons:
            raise AdmissionRefused(head_reasons)
        name = 'queue_ledger.torn-%d.bin' % (ledger.seq + 1)
        with open(layout.out / name, 'xb') as fh:
            fh.write(fragment)
            fh.flush()
            os.fsync(fh.fileno())
        os.ftruncate(fd, len(complete))
        os.fsync(fd)
        session = LedgerSession(layout, frozen, ledger, fd, clock)
        ev = session.append('torn_tail_repair', session=None, fragment_file=name,
                            fragment_sha256=sha256_hex(fragment), fragment_bytes=len(fragment), note=note)
        return ev
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


# ------------------------------------------------------------------ episode admission (the cue-v1 driver)

def admit_episode(layout=None, *, run_id, position, instance_id, backend, arm, port, alias, expected_image):
    """Admission for ONE cue-v1 episode process, before any model, container or receipt work.

    The whole queue must validate (every bound input unchanged, ledger, head, namespace, receipts), a runner session
    must hold the ledger lock, and this run id must be the open (started, not ended) assignment of that session at
    the given frozen position, with the frozen instance, backend, arm, port, model alias and image. Returns
    (frozen binding, frozen assignment row, report). Raises AdmissionRefused otherwise."""
    layout = layout if isinstance(layout, Layout) else Layout(layout)
    report = validate_queue(layout)
    if not report['launched']:
        raise AdmissionRefused(['%s has not been launched: an episode runs only inside a runner session'
                                % NAMESPACE_REL])
    if not report['ledger_locked']:
        raise AdmissionRefused(['no runner session holds the ledger lock: an episode runs only inside one'])
    frozen = _read_frozen_binding(layout)
    ledger = load_ledger(layout.ledger_path, frozen)
    start = ledger.starts.get(position) if _int(position) else None
    if (ledger.open_session is None or start is None or start['session'] != ledger.open_session
            or start['run_id'] != run_id or position in ledger.ends or ledger.next_position() != (
                None if position == ledger.n else position + 1)):
        raise AdmissionRefused(['run %r is not the open assignment start of the current runner session' % (run_id,)])
    rows = {row['position']: row for row in plan_rows(frozen)}
    row = rows[position]
    expected = dict(instance_id=row['instance_id'], backend=row['backend'], arm=row['arm'], port=row['port'],
                    alias=row['model_alias'], expected_image=row['image_id'])
    given = dict(instance_id=instance_id, backend=backend, arm=arm, port=port, alias=alias,
                 expected_image=expected_image)
    differs = sorted(k for k in expected if type(expected[k]) is not type(given[k]) or expected[k] != given[k])
    if differs:
        raise AdmissionRefused(['episode arguments differ from the frozen assignment %d: %s'
                                % (position, ', '.join('%s=%r (frozen %r)' % (k, given[k], expected[k])
                                                       for k in differs))])
    run_dir = layout.out / run_id
    if not run_dir.is_dir() or run_dir.is_symlink() or any(run_dir.iterdir()):
        raise AdmissionRefused(['run directory %s must exist, be a real directory and be empty' % run_id])
    return frozen, row, report


def check_running_runtime(binding, *, site_packages, mswea_package):
    """The SDK and mini-swe-agent files THIS process imports must be the bound bytes (the binding describes the
    checkout; this checks the interpreter actually running)."""
    reasons = []
    for rel, digest in sorted(binding['runtime'].get('sdk_traced_files', {}).items()):
        path = Path(site_packages) / rel
        try:
            current = sha256_hex(path.read_bytes())
        except OSError:
            current = None
        if current != digest:
            reasons.append('running SDK file %s differs from the bound bytes' % rel)
    for rel, digest in sorted(binding['runtime'].get('mini_swe_agent_sources', {}).items()):
        try:
            current = sha256_hex((Path(mswea_package) / rel).read_bytes())
        except OSError:
            current = None
        if current != digest:
            reasons.append('running mini-swe-agent file %s differs from the bound bytes' % rel)
    for hook in FORBIDDEN_SITE_HOOKS:
        if (Path(site_packages) / hook).exists():
            reasons.append('running interpreter has %s' % hook)
    if reasons:
        raise AdmissionRefused(reasons)


# ------------------------------------------------------------------ request budget and storage preflight

class AssignmentRequestBudget:
    """Per-assignment physical-request budget, limited by min(48, cohort cap - requests already counted across every
    earlier session). A caller may consume() BEFORE each physical send; a refusal happens before dispatch.

    cue_transport.py keeps its own cohort-wide RequestBudget(used=, limit=). The queue hands the episode the numbers
    to build it without resetting earlier sessions: used=counted_before, limit=counted_before + limit (so the same
    min(48, remaining cohort) bound holds at the transport boundary)."""

    def __init__(self, assignment_id, *, counted_before, per_assignment=CONTRACT_SETTINGS[
            'max_physical_requests_per_assignment'], cap=CONTRACT_SETTINGS['max_physical_requests']):
        self.assignment_id = assignment_id
        self.counted_before = counted_before
        self.limit = max(0, min(per_assignment, cap - counted_before))
        self.consumed = 0
        self.refused = 0

    @property
    def remaining(self):
        return self.limit - self.consumed

    def consume(self):
        if self.consumed >= self.limit:
            self.refused += 1
            raise RequestCapReached('physical request %d of %s refused before dispatch: limit %d (48 per assignment, '
                                    '%d already counted of the 576 cohort cap)'
                                    % (self.consumed + 1, self.assignment_id, self.limit, self.counted_before))
        self.consumed += 1
        return self.consumed


def free_space_check(path, *, host_reserve_bytes, disk_usage=shutil.disk_usage):
    """None when free space covers the host reserve plus the lead's 6 GiB start margin, else the refusal reason.
    The host reserve has no repository-declared value: the live launcher must pass it explicitly."""
    if not _int(host_reserve_bytes) or host_reserve_bytes < 0:
        raise ValueError('host_reserve_bytes must be a non-negative integer supplied by the launcher')
    probe = Path(path)
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    need = host_reserve_bytes + CONTRACT_STORAGE['start_free_space_above_host_reserve_bytes']
    free = disk_usage(probe).free
    if free >= need:
        return None
    return ('free space %d bytes is below the host reserve %d + 6 GiB start margin (%d bytes)'
            % (free, host_reserve_bytes, need))


def check_running_sources(binding, running):
    """The code this process runs must be the bound bytes (a source edited after import cannot be admitted)."""
    bad = [name for name, digest in sorted(running.items()) if binding['modules'].get(name) != digest]
    if bad:
        raise AdmissionRefused(['running %s differs from the bound source bytes' % name for name in bad])
