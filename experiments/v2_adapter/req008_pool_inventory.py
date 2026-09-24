"""DTR-REQ-008 (lead c88c90c; docs/experiment_handoff.md, 'Lead reply - 2026-09-24T03:56Z - DTR-REQ-008 P0, read-only
pool inventory'): inventory of the 500 pinned princeton-nlp/SWE-bench_Verified@c104f840 issues for the fixed v2 E2
repository-repair target. Source checkpoint cc88526.

METADATA-ONLY RETROSPECTIVE DIAGNOSIS. No model, evaluator, container, docker, GPU, Monte Carlo, network download or new
task/outcome-based selection. Stdlib only; read-only git commands (ls-files, log HEAD, status, rev-parse, hash-object
without -w, merge-base) give provenance. Nothing under results/code_routing/ is opened, and its paths are excluded from
every git enumeration (pathspec ':(exclude)results/code_routing'; the non-git walk prunes it).
Model-episode directories and model-server logs are never opened: model-outcome exposure is established by the
EXISTENCE of a recorded episode (a cohort-manifest entry and/or an episode directory), never by its outcome. The two DEV
cohort manifests (block_1.json), the DEV2 cohort binding and amendment spec and the third-party audit
(results/replay_gap_audit/audit.json) ARE json-decoded in memory, with an object_pairs_hook that retains only
allow-listed keys (BLOCK_KEYS, REPLAY_KEYS, DEV2_SPEC_KEYS, BINDING_KEYS); no outcome field is accessed or emitted.
Every scanned tracked file is byte-scanned for pinned-ID tokens (per-file ID counts are emitted, plus per-ID mention
paths and counts only for IDs exposed under neither definition); the other
model-outcome-bearing files (DEV reports, grading passes, sanitization records, analyses, lead audits of model episodes)
are never json-decoded. Qualification records are json-decoded; only instance_id, qualified, acceptance, stage_failed
and identity/platform evaluator_commit are accessed. The local dataset parquet (git-ignored) is hashed and, with a
stdlib reader, only its footer and the instance_id, repo and version column chunks are decoded.

Definitions (fixed before the first run; revised before regeneration in two REQ-008 fix rounds):
  pinned frame   the 500 rows of results/v2_adapter/m01_c104f840_f7bbbb2/instances.jsonl. Pin chain: evaluator
                 selection config (revision, evaluator) -> dataset download audit (revision -> parquet sha256) -> M01
                 summary (parquet sha256, rows, evaluator) -> instances.jsonl sha256 -> the source_sha256 cited by the
                 qualification manifest, pilot frame, legacy hash manifest and control-plan template; dataset/evaluator
                 identities in the M01 summary, pilot frame and legacy manifest; the local parquet bytes and its
                 instance_id/repo/version columns when present. ANY failed or missing pin link makes every category
                 count UNKNOWN (naming the artifact). A structured evidence ID outside the 500 ABORTS the run.
  ID lists       identity = sha256 of the UTF-8 bytes of the sorted IDs, each followed by "\n" (empty list: sha256 of
                 the empty string); reported for the frame, every category and every unexposed pool.
  family         repository (`repo`). repo@version groups are reported as a finer alternative. Near-duplicate/family-
                 variant grouping required by the v2 protocol (section 4) is NOT assessed here; it is listed as a
                 required step. The grouping used for any pool is the lead's decision.
  touch kinds    each recorded with its evidence paths
    model_outcome_episode         recorded project model episode: DEV1 cohort pilot-cp2-wc2 and DEV2 cohort yaml-v1
                                  (block_1.json ran / skipped_completed / retained_incomplete / unconfirmed_container_runs
                                  entries and their episode directories) and the agent smoke episodes
                                  (results/v2_agent/smoke_episode_20260922/<id>__<backend>[__variant]/)
    third_party_recorded_episode  task_id of a third-party trajectory release whose files this project downloaded and
                                  audited (results/replay_gap_audit/audit.json; only task_ids and file identity kept)
    evaluator_qualification       stock gold / adapter reference / adapter no_change runtime controls (no model)
    evaluator_other               other evaluator or container use without a model (M03 offline grader fixture run with
                                  the instance's parser; django provenance diagnostic runs)
    source_inspection             targeted static inspection beyond the bulk M01 pass (M01 reset-check first-pass flags;
                                  django provenance image/checkout inspection)
    frame_selection               named in a selection frame (qualification manifest, pilot frame, cue-v1 registry,
                                  cohort `unstarted` queue)
    metadata_static               bulk non-executing construction/checks over all 500 (M01 rows, M01 reset check,
                                  control-plan template)
  categories     mutually exclusive, first match in priority order
                   model_outcome_exposed > qualification_or_inspection_only > third_party_recorded_only >
                   frame_selected_not_run > not_yet_assessed
                 exposure definitions (both reported side by side; exposure_definition: lead decision pending):
                   conservative  model_outcome_episode or third_party_recorded_episode
                   project_only  model_outcome_episode only
                 qualification_or_inspection_only = evaluator_qualification, evaluator_other or source_inspection (sub-
                 counts: evaluator_touched vs source_inspection_only); third_party_recorded_only =
                 third_party_recorded_episode and nothing above (non-empty only under project_only);
                 frame_selected_not_run = frame_selection and nothing above; not_yet_assessed = none of the above.
  explained      a file is explained for an ID when it equals, or lies under, the evidence root of one of the ID's
                 touches (evidence path up to the first ' ' or '#'), or it is a bulk source listing all 500. This
                 script, its test file and its two default output paths are excluded from the mention scan as
                 self-explained (recorded in mention_scan.self_excluded_paths).
  UNKNOWN        per exposure definition d, an ID not model_outcome_exposed under d is UNKNOWN under d when:
                 (a) a record-like tracked file (under results/, configs/ or docs/audits/, any docs/**/*.json, or a
                     run-manifest file name) mentions it without being explained and is not on the sha256-pinned
                     derivative whitelist;
                 (b) any other tracked file mentions it while it has only metadata_static touches;
                 (c) a tracked or historical path (git log HEAD) names it outside registered locations;
                 (d) a cohort directory holds an unlisted episode-like directory for it, or a cohort-level record names
                     it outside that cohort's manifest entries;
                 (e) an uncommitted run path names it outside the mapped committed record roots;
                 (f) global: a missing exposure source, an unattributable cohort entry, or any failed pin link.
                 Counts are then reported as UNKNOWN with known lower bounds and the exact artifact. Uncommitted
                 evidence can only raise UNKNOWN; it never assigns a category.
  metadata gate  M01/M02 static gate (qualify_instances.qualify + make_test_spec at evaluator f7bbbb2): pass iff the M02
                 test lists are valid (instances.jsonl field `qualification` == 'eligible', renamed here to
                 m02_test_list_status = 'test_lists_valid'; a static test-list flag, NOT study eligibility),
                 construction == ok, (repo, version) in the evaluator constants, not a FAIL_ONLY repository and content
                 unchanged by construction. Empty PASS_TO_PASS is a recorded limitation, not a failure.
  runtime gate   bae161f five-key acceptance of qualification_batch.py (stock gold vs adapter reference vs adapter
                 no_change under the M03 strict rule): pass | fail (failed acceptance keys only) | untested | UNKNOWN
                 (record hash or verdict does not reconcile with the pilot frame / legacy hash manifest / status, or
                 the qualification manifest/status is missing, for every manifest, status, legacy and frame ID).
  aborts         wrong row count or duplicate IDs; any structured evidence ID outside the 500; qualification manifest,
                 status, per-ID record and pilot-frame ID sets disagree. Record-hash mismatches are reported
                 explicitly (UNKNOWN), never silently accepted.
  determinism    outputs are a deterministic function of the recorded HEAD commit, working-tree status, script sha256,
                 input sha256 values and the local uncommitted path state (work/), all recorded.
Usage: req008_pool_inventory.py [--out-json PATH] [--out-md PATH]   (both rendered first, then each written once with
open(..., 'x'))
"""
from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import json
import os
import platform
import re
import subprocess
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT_REL = 'experiments/v2_adapter/req008_pool_inventory.py'
TEST_REL = 'tests/test_req008_pool_inventory.py'
OUT_JSON_DEFAULT = 'results/v2_adapter/req008_pool_inventory.json'
OUT_MD_DEFAULT = 'docs/req008_fresh_pool_inventory.md'
REQUEST = 'DTR-REQ-008'
LEAD_REQUEST_COMMIT = 'c88c90c'
SOURCE_CHECKPOINT = 'cc88526'
SCOPE = ('metadata-only retrospective diagnosis: no model, evaluator, container, docker, GPU, Monte Carlo, network '
         'download or new task/outcome-based selection. The two DEV cohort block_1.json manifests, the DEV2 cohort '
         'binding and amendment spec and results/replay_gap_audit/audit.json were json-decoded in memory with an '
         'object_pairs_hook retaining only allow-listed keys; no model or third-party outcome field was accessed or '
         'emitted. Model-outcome-bearing reports, grading passes, analyses and lead audits of model episodes were '
         'byte-scanned for pinned-ID tokens only; episode directories and model-server logs were never opened; nothing under '
         'results/code_routing/ was opened, and its paths were excluded from every git enumeration')
PINS = OrderedDict(
    dataset='princeton-nlp/SWE-bench_Verified',
    dataset_revision='c104f840cc67f8b6eec6f759ebc8b2693d585d4a',
    dataset_file='data/test-00000-of-00001.parquet',
    source_sha256='cee2e8760d9a1f3389031c709fd854af7d7a662499bd152ddeb62491f38dec64',
    dataset_sha256='a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd',
    evaluator_commit='f7bbbb2ccdf479001d6467c9e34af59e44a840f9',
    n_rows=500)
ID_LIST_SERIALIZATION = ('sha256 of the UTF-8 bytes of the instance IDs sorted as strings, each followed by "\\n" '
                         '(an empty list hashes the empty string)')

P = OrderedDict(
    m01_instances='results/v2_adapter/m01_c104f840_f7bbbb2/instances.jsonl',
    m01_summary='results/v2_adapter/m01_c104f840_f7bbbb2/summary.json',
    m01_reset='results/v2_adapter/m01_c104f840_f7bbbb2/reset_check.json',
    m01_code='experiments/v2_adapter/m01_metadata.py',
    m02_code='experiments/v2_adapter/qualify_instances.py',
    download_audit='docs/audits/swebench_verified_download_c104f840.json',
    evaluator_selection='configs/v2_evaluator_selection_20260921.json',
    control_template='results/v2_adapter/control_plan_template_20260921.json',
    runbook='docs/swebench_control_runbook_20260921.md',
    qual_manifest='configs/v2_runtime_smoke_expansion_20260922.json',
    qual_dir='results/v2_adapter/qualification_20260922',
    qual_status='results/v2_adapter/qualification_20260922/status.json',
    qual_legacy='results/v2_adapter/qualification_20260922/legacy_hash_manifest.json',
    qual_code='experiments/v2_adapter/qualification_batch.py',
    control_adapter_code='experiments/v2_adapter/control_adapter.py',
    smoke_flask='results/v2_adapter/smoke_flask_20260922/summary.json',
    m03='results/v2_adapter/m03_upstream_grader_run_20260922/summary.json',
    django_provenance='results/v2_adapter/django_provenance_20260922/provenance.json',
    runtime='results/v2_adapter/runtime_20260922.json',
    pilot_frame='results/v2_agent/pilot_frame_20260922.json',
    pilot_spec='configs/v2_fixed_backend_development_pilot_20260922.json',
    dev2_spec='configs/v2_fixed_backend_development_pilot_yaml_v1_20260922.json',
    pilot_runner='experiments/v2_agent/pilot_runner.py',
    smoke_dir='results/v2_agent/smoke_episode_20260922',
    smoke_audit='docs/audits/episode_diagnosis_82a1194.json',
    replay_gap='results/replay_gap_audit/audit.json',
    cue_registry='experiments/v2_agent/cue_cohort.py',
    protocol='docs/experiment_protocol_v2.md',
    request_text='docs/experiment_handoff.md',
)
DJANGO_PROVENANCE_DIR = 'results/v2_adapter/django_provenance_20260922/'
COHORTS = (
    OrderedDict(key='DEV1', label='DEV cohort 1 (pilot-cp2-wc2)', dir='results/v2_agent/pilot_20260922',
                block='results/v2_agent/pilot_20260922/block_1.json', binding=None, cohort_name=None, spec=None),
    OrderedDict(key='DEV2', label='DEV cohort 2 (yaml-v1)', dir='results/v2_agent/pilot_20260922_yaml_v1',
                block='results/v2_agent/pilot_20260922_yaml_v1/block_1.json',
                binding='results/v2_agent/pilot_20260922_yaml_v1/cohort_binding.json', cohort_name='yaml-v1',
                spec=P['dev2_spec']),
)
DATASET_PARQUET = 'work/benchmark_inputs/swebench_verified_c104f840/test-00000-of-00001.parquet'  # ignored by git
PARQUET_COLUMNS = ('instance_id', 'repo', 'version')
NEVER_OPEN_PREFIXES = ('results/code_routing/',)
# added to every git status / ls-files / log pathspec, BEFORE any positive path (git 2.50 ls-files matches nothing for
# '<deep path> :(exclude)results/code_routing' in that order)
GIT_EXCLUDE = ':(exclude)results/code_routing'
# object_pairs_hook allow-lists (applied at every nesting level; every other key is dropped on decode, never read)
BLOCK_KEYS = frozenset(('frame_sha256', 'cohort', 'amendment_sha256', 'ran', 'skipped_completed', 'retained_incomplete',
                        'unstarted', 'unconfirmed_container_runs', 'unconfirmed_episode_pids', 'instance_id', 'backend',
                        'run_id', 'run_dirs'))
BINDING_KEYS = frozenset(('cohort', 'amendment_sha256'))
DEV2_SPEC_KEYS = frozenset(('cohort', 'frame', 'frame_sha256', 'base_spec', 'base_spec_sha256'))
REPLAY_KEYS = frozenset(('dataset', 'revision', 'unique_tasks_total', 'files', 'file', 'sha256', 'task_ids'))
EPISODE_PARENTS = tuple(c['dir'] for c in COHORTS) + (P['smoke_dir'],)
SERVER_LOG_RE = re.compile(r'^server_[^/]*\.log$')
SELF_PATHS = frozenset((SCRIPT_REL, TEST_REL, OUT_JSON_DEFAULT, OUT_MD_DEFAULT))
BULK_SOURCES = frozenset((P['m01_instances'], P['control_template']))   # list every ID by construction
RECORD_LIKE_PREFIXES = ('results/', 'configs/', 'docs/audits/')
RUN_MANIFEST_NAME_RE = re.compile(r'^(block_\d+(_start)?|report_[^/]*|grading_pass_[^/]*|sanitization_[^/]*|'
                                  r'[^/]*harness_exposure|cohort_binding|episode)\.json$')
# Lead audits of registered qualification/provenance/frame records that name non-exposed IDs. Accepted as derivative
# only while their bytes equal the pinned sha256 (any change re-opens the question and makes the IDs UNKNOWN).
DERIVATIVE_RECORD_WHITELIST = OrderedDict([
    ('docs/audits/django_provenance_109ee5a.json', OrderedDict(
        sha256='b118dbef2afd55e5afa7c33a2706bdb7a323c40611b37b985759d9686bdc194a',
        reason='lead deterministic recount of saved django-10097 full-control logs (scope field: no execution); '
               'derivative of the registered django provenance and qualification records')),
    ('docs/audits/pilot_frame_109ee5a.json', OrderedDict(
        sha256='a3017e85221bad9cbec8a141797f7a0813b695d7b4e9d2889ffb4dd2130a0d19',
        reason='lead audit of the frozen pilot frame (frame_size 12, K 9, N 8); derivative of the registered pilot '
               'frame')),
    ('docs/audits/qualification_600e143.json', OrderedDict(
        sha256='3cb051837e235766a0c7d14927f96aadede889ea2ce6e600cb15f584639c27f3',
        reason='lead saved-log and pinned-row audit of registered qualification records (scope field: no runtime '
               'rerun)')),
    ('docs/audits/qualification_d3bf388.json', OrderedDict(
        sha256='c72dfd542de60943f154c1d7c4153e71c921fc8f236d8fc2d044945a307d498d',
        reason='lead saved-artifact audit of registered qualification records (scope field: no runtime rerun)')),
])
# Manual review of the unexplained narrative (non-record-like) mentions of IDs that have a non-metadata touch and are
# not model_outcome_exposed under project_only (the wider unexposed pool). Manifest = sha256 of the sorted
# '<path>\t<instance_id>' lines (file contents not hashed); lines are listed only for IDs exposed under neither
# definition, the others are counted.
NARRATIVE_REVIEW = OrderedDict(
    reviewed_at_head='0648c8b', manifest_sha256='edef8199bc6873cebccd80546c37a7857ea90373449fee42cfcb3c8da34ff513',
    finding=('each mention was read in context: the M01 reset-check first-pass flags (django-13837, django-14311, '
             'sphinx-10673) in the handoff narrative and two checker docstrings/tests; the django-10097 provenance/'
             'qualification and xarray-2905 frame-rank (not selected) discussion in the handoff, results and '
             'feedback narratives and the lead audit scripts; the qualification-diagnosis narratives of the one ID '
             'exposed only under conservative (counted, not listed). All derive from registered qualification, '
             'provenance, pilot-frame or reset-check records; none indicates an unrecorded model run. A changed '
             'manifest adds a global note to unknowns (categories unchanged).'))
UNCOMMITTED_DIRS = ('work/runs', 'work/logs')
# uncommitted run roots -> the committed touch kind that explains an ID-named path under them
UNCOMMITTED_ROOTS = (('work/runs/pilot_20260922/', 'model_outcome_episode'),
                     ('work/runs/qualification_20260922/', 'evaluator_qualification'),
                     ('work/runs/smoke_flask_20260922/', 'evaluator_qualification'))
UNATTRIBUTED_NAME_RE = re.compile(r'^(agent_smoke_[^/]*\.stdout|llama_[^/]*\.log)$')
SMOKE_STDOUT_RE = re.compile(r'^agent_smoke_[^/]*\.stdout$')
SERVER_LOG_ATTRIBUTION = OrderedDict([
    ('source', P['request_text'] + " section 'DTR-REQ-004 shared-host statement - 2026-09-22T02:34:16Z'"),
    ('cited_phrases', ['DTR-REQ-004 shared-host statement', 'work/llama_{small,large}.log', '02:23 UTC',
                       '4 pipeline smoke episodes']),
    ('attribution', 'The server logs were not opened; their task identity was not established from content. The '
                    'committed narrative attributes work/llama_{small,large}.log to the servers that logged the '
                    'code_routing study traffic (unrelated HumanEval/MBPP study), restarted at about 02:23 UTC for the '
                    '4 REQ-002 pipeline smoke episodes and released at 02:33 UTC; work/llama_{8191,8193}_ctx16k.log '
                    'are attributed, by file name only, to the restarted servers (16,384 tokens per slot). The first '
                    'smoke attempt may predate that restart, so the pre-restart logs may also hold smoke traffic; the '
                    'committed smoke episode IDs (smoke_episode_ids) are model-outcome exposed under both definitions '
                    'anyway.'),
])
WALK_EXCLUDE_TOP = frozenset(('.git', '.venv', 'work', '__pycache__', '.pytest_cache'))

KINDS = ('model_outcome_episode', 'third_party_recorded_episode', 'evaluator_qualification', 'evaluator_other',
         'source_inspection', 'frame_selection', 'metadata_static')
CATEGORIES = ('model_outcome_exposed', 'qualification_or_inspection_only', 'third_party_recorded_only',
              'frame_selected_not_run', 'not_yet_assessed')
DEFINITIONS = OrderedDict(
    conservative=frozenset(('model_outcome_episode', 'third_party_recorded_episode')),
    project_only=frozenset(('model_outcome_episode',)))
QI_KINDS = frozenset(('evaluator_qualification', 'evaluator_other', 'source_inspection'))
EVALUATOR_KINDS = frozenset(('evaluator_qualification', 'evaluator_other'))
ALL_DEFS = tuple(DEFINITIONS)
M02_STATUS = {'eligible': 'test_lists_valid', 'refused': 'test_lists_refused'}


class InventoryAbort(RuntimeError):
    """A structural inconsistency that makes the inventory meaningless (never a silent zero)."""


# ------------------------------------------------------------------ guarded reading
def is_never_open(rel: str) -> bool:
    """True for paths this script must not open: results/code_routing/, anything inside an episode directory, and
    model-server logs in cohort directories."""
    if rel.startswith(NEVER_OPEN_PREFIXES):
        return True
    for parent in EPISODE_PARENTS:
        if rel.startswith(parent + '/'):
            rest = rel[len(parent) + 1:]
            if '/' in rest or SERVER_LOG_RE.match(rest):
                return True
    return False


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def id_list_sha256(ids) -> str:
    return sha256_bytes(b''.join(i.encode() + b'\n' for i in sorted(ids)))


def utc_iso(epoch):
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class Ctx:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.is_git = (self.root / '.git').exists()
        self.registry = OrderedDict()
        self.checks = []
        self.unknowns = []
        self.pin_checks = []
        self.touches = defaultdict(lambda: defaultdict(set))

    # -- files
    def read(self, rel: str) -> bytes:
        if is_never_open(rel):
            raise InventoryAbort('refusing to open a never-open path: %s' % rel)
        with open(self.root / rel, 'rb') as fh:
            return fh.read()

    def exists(self, rel: str) -> bool:
        return not rel.startswith(NEVER_OPEN_PREFIXES) and (self.root / rel).exists()

    def listdir(self, rel: str):
        if rel.startswith(NEVER_OPEN_PREFIXES):
            raise InventoryAbort('refusing to list %s' % rel)
        return sorted(os.listdir(self.root / rel))

    # -- git (read-only)
    def git(self, *args):
        if not self.is_git:
            return None
        try:
            p = subprocess.run(['git', '-C', str(self.root)] + list(args), capture_output=True, text=True, timeout=300)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return p.stdout if p.returncode == 0 else None

    def git_rc(self, *args):
        if not self.is_git:
            return None
        try:
            return subprocess.run(['git', '-C', str(self.root)] + list(args), capture_output=True, timeout=120).returncode
        except (OSError, subprocess.TimeoutExpired):
            return None

    def git_info(self, rel: str):
        info = OrderedDict(git_first_commit=None, git_last_commit=None, tracked=None, working_tree_matches_head=None,
                           last_change_at_or_before_source_checkpoint=None)
        if not self.is_git:
            return info
        added = (self.git('log', '--format=%H', '--diff-filter=A', '--no-renames', 'HEAD', '--', GIT_EXCLUDE, rel)
                 or '').split()
        last = (self.git('log', '-1', '--format=%H', 'HEAD', '--', GIT_EXCLUDE, rel) or '').strip()
        info['git_first_commit'] = added[-1] if added else None
        info['git_last_commit'] = last or None
        info['tracked'] = bool((self.git('ls-files', '--', GIT_EXCLUDE, rel) or '').strip())
        status = self.git('status', '--porcelain', '--', GIT_EXCLUDE, rel)
        info['working_tree_matches_head'] = None if status is None else (status.strip() == '' and info['tracked'])
        if last:
            info['last_change_at_or_before_source_checkpoint'] = self.git_rc(
                'merge-base', '--is-ancestor', last, SOURCE_CHECKPOINT) == 0
        return info

    # -- registry / checks / unknowns
    def register(self, rel: str, role: str, read_as: str):
        entry = OrderedDict(path=rel, role=role, read_as=read_as)
        p = self.root / rel
        if rel.startswith(NEVER_OPEN_PREFIXES):
            raise InventoryAbort('never-open path in the registry: %s' % rel)
        if p.is_dir():
            names = self.listdir(rel)
            entry.update(exists=True, kind='directory', sha256=sha256_bytes('\n'.join(names).encode()),
                         sha256_of='sorted child names joined by newline (no file inside opened)')
        elif p.exists():
            entry.update(exists=True, kind='file', sha256=sha256_bytes(self.read(rel)), sha256_of='file bytes')
        else:
            entry.update(exists=False, kind=None, sha256=None, sha256_of=None)
        entry.update(self.git_info(rel))
        self.registry[rel] = entry
        return entry

    def load_json(self, rel: str, role: str, read_as: str, keep=None):
        """json-decode a file; with `keep`, an object_pairs_hook retains only those keys at every nesting level (the
        other values are decoded by the parser and dropped unread)."""
        if read_as.startswith('parsed: '):
            read_as = read_as[len('parsed: '):]
        if keep is not None:
            read_as = 'json-decoded; object_pairs_hook retains only keys %s; accessed: %s' % (sorted(keep), read_as)
        else:
            read_as = 'json-decoded (all keys); accessed: %s' % read_as
        entry = self.register(rel, role, read_as)
        if not entry['exists']:
            return None
        hook = None if keep is None else (lambda pairs: {k: v for k, v in pairs if k in keep})
        return json.loads(self.read(rel), object_pairs_hook=hook)

    def check(self, name: str, ok: bool, detail: str = ''):
        self.checks.append(OrderedDict(check=name, ok=bool(ok), detail=detail))
        return bool(ok)

    def pin(self, name: str, ok: bool, detail: str, artifact: str):
        """A pin link: recorded as a consistency check and in the pin chain; a failure makes all categories UNKNOWN."""
        ok = self.check('pin:' + name, ok, detail)
        self.pin_checks.append(OrderedDict(check=name, ok=ok, artifact=artifact, detail=detail))
        if not ok:
            self.unknown('global', 'category', artifact, 'pin link failed or missing: %s' % name)
        return ok

    def unknown(self, scope: str, affects: str, artifact: str, reason: str, ids=(), definitions=ALL_DEFS):
        self.unknowns.append(OrderedDict(scope=scope, affects=affects, definitions=list(definitions),
                                         ids=sorted(set(ids)), artifact=artifact, reason=reason))

    def touch(self, iid: str, kind: str, evidence: str, frame: set, source: str):
        if iid not in frame:
            raise InventoryAbort('evidence ID %r from %s is not in the pinned 500-row frame' % (iid, source))
        assert kind in KINDS
        self.touches[iid][kind].add(evidence)


# ------------------------------------------------------------------ ID matching
def id_patterns(ids):
    prefixes = sorted({i.rsplit('-', 1)[0] for i in ids}, key=lambda s: (-len(s), s))
    full = re.compile(rb'(?<![\w-])(' + b'|'.join(re.escape(p.encode()) for p in prefixes) + rb')-(\d+)(?!\d)')
    short_map = defaultdict(set)
    for i in ids:
        owner_repo, num = i.rsplit('-', 1)
        if '__' in owner_repo:
            short_map[(owner_repo.split('__', 1)[1], num)].add(i)
    repos = sorted({k[0] for k in short_map}, key=lambda s: (-len(s), s))
    short = re.compile(rb'(?<![\w./-])(' + b'|'.join(re.escape(r.encode()) for r in repos) + rb')-(\d+)(?!\d)')
    return full, short, short_map


def find_ids(data: bytes, pats, frame):
    full, short, short_map = pats
    found_full = {(m.group(1) + b'-' + m.group(2)).decode() for m in full.finditer(data)} & frame
    found_short = set()
    for m in short.finditer(data):
        cands = short_map.get((m.group(1).decode(), m.group(2).decode()), set())
        if len(cands) == 1:
            found_short |= cands
    return found_full, found_short - found_full


def ids_in_path(rel: str, pats, frame):
    full = pats[0]
    return {(m.group(1) + b'-' + m.group(2)).decode() for m in full.finditer(rel.encode())} & frame


def parse_episode_dirname(name: str):
    """'<owner>__<repo>-<n>__<backend>[__variant...]' -> (instance_id, backend) or None."""
    parts = name.split('__')
    if len(parts) < 3:
        return None
    return parts[0] + '__' + parts[1], parts[2]


def evidence_root(evidence: str) -> str:
    return evidence.split(' ', 1)[0].split('#', 1)[0]


def is_explained(rel: str, roots) -> bool:
    return rel in BULK_SOURCES or any(rel == r or (r.endswith('/') and rel.startswith(r)) for r in roots)


def is_record_like(rel: str) -> bool:
    return (rel.startswith(RECORD_LIKE_PREFIXES) or (rel.startswith('docs/') and rel.endswith('.json'))
            or bool(RUN_MANIFEST_NAME_RE.match(rel.rsplit('/', 1)[-1])))


# ------------------------------------------------------------------ minimal stdlib parquet reader
def _varint(buf, pos):
    shift = result = 0
    while True:
        b = buf[pos]
        pos += 1
        result |= (b & 0x7f) << shift
        if not b & 0x80:
            return result, pos
        shift += 7


def _zigzag(n):
    return (n >> 1) ^ -(n & 1)


class ThriftCompact:
    """Thrift compact-protocol reader; structs decode to {field_id: value}."""

    def __init__(self, buf, pos=0):
        self.buf, self.pos = buf, pos

    def value(self, t):
        b = self.buf
        if t in (1, 2):
            return t == 1
        if t == 3:
            v = b[self.pos]
            self.pos += 1
            return v - 256 if v > 127 else v
        if t in (4, 5, 6):
            v, self.pos = _varint(b, self.pos)
            return _zigzag(v)
        if t == 7:
            self.pos += 8
            return None
        if t == 8:
            n, self.pos = _varint(b, self.pos)
            v = bytes(b[self.pos:self.pos + n])
            self.pos += n
            return v
        if t in (9, 10):
            h = b[self.pos]
            self.pos += 1
            n, et = h >> 4, h & 0x0f
            if n == 15:
                n, self.pos = _varint(b, self.pos)
            out = []
            for _ in range(n):
                if et in (1, 2):
                    out.append(b[self.pos] == 1)
                    self.pos += 1
                else:
                    out.append(self.value(et))
            return out
        if t == 11:
            n, self.pos = _varint(b, self.pos)
            if n == 0:
                return {}
            kv = b[self.pos]
            self.pos += 1
            return {self.value(kv >> 4): self.value(kv & 0x0f) for _ in range(n)}
        if t == 12:
            return self.struct()
        raise ValueError('unsupported thrift compact type %d' % t)

    def struct(self):
        out, last = {}, 0
        while True:
            h = self.buf[self.pos]
            self.pos += 1
            if h == 0:
                return out
            t, delta = h & 0x0f, h >> 4
            if delta:
                fid = last + delta
            else:
                v, self.pos = _varint(self.buf, self.pos)
                fid = _zigzag(v)
            out[fid] = self.value(t)
            last = fid


def snappy_decompress(buf):
    n, pos = _varint(buf, 0)
    out = bytearray()
    while pos < len(buf):
        tag = buf[pos]
        pos += 1
        kind = tag & 3
        if kind == 0:
            ln = tag >> 2
            if ln >= 60:
                nb = ln - 59
                ln = int.from_bytes(buf[pos:pos + nb], 'little')
                pos += nb
            ln += 1
            out += buf[pos:pos + ln]
            pos += ln
            continue
        if kind == 1:
            ln = ((tag >> 2) & 7) + 4
            off = ((tag >> 5) << 8) | buf[pos]
            pos += 1
        elif kind == 2:
            ln = (tag >> 2) + 1
            off = int.from_bytes(buf[pos:pos + 2], 'little')
            pos += 2
        else:
            ln = (tag >> 2) + 1
            off = int.from_bytes(buf[pos:pos + 4], 'little')
            pos += 4
        if off == 0 or off > len(out):
            raise ValueError('bad snappy copy offset')
        start = len(out) - off
        for i in range(ln):
            out.append(out[start + i])
    if len(out) != n:
        raise ValueError('snappy length mismatch %d != %d' % (len(out), n))
    return bytes(out)


def rle_bitpacked_hybrid(buf, pos, bit_width, count):
    out = []
    nb = (bit_width + 7) // 8
    mask = (1 << bit_width) - 1
    while len(out) < count:
        header, pos = _varint(buf, pos)
        if header & 1:
            groups = header >> 1
            nbytes = groups * bit_width
            val = int.from_bytes(buf[pos:pos + nbytes], 'little')
            pos += nbytes
            out.extend((val >> (i * bit_width)) & mask for i in range(groups * 8))
        else:
            run = header >> 1
            v = int.from_bytes(buf[pos:pos + nb], 'little') if nb else 0
            pos += nb
            out.extend([v] * run)
    return out[:count], pos


def _plain_byte_arrays(buf, pos, count):
    out = []
    for _ in range(count):
        n = int.from_bytes(buf[pos:pos + 4], 'little')
        pos += 4
        out.append(bytes(buf[pos:pos + n]))
        pos += n
    return out, pos


_CODECS = {0: bytes, 1: snappy_decompress}


def read_parquet_columns(data: bytes, names):
    """Decode only the footer and the named flat BYTE_ARRAY column chunks (UNCOMPRESSED/SNAPPY; PLAIN or dictionary
    encoding; data page v1/v2). Raises ValueError on anything unsupported."""
    if data[:4] != b'PAR1' or data[-4:] != b'PAR1':
        raise ValueError('not a parquet file (magic)')
    flen = int.from_bytes(data[-8:-4], 'little')
    meta = ThriftCompact(data, len(data) - 8 - flen).struct()
    schema = meta[2]
    root, leaves = schema[0], schema[1:]
    if any(s.get(5) for s in leaves) or root.get(5) != len(leaves):
        raise ValueError('nested parquet schema not supported')
    repetition = {s[4].decode(): s.get(3, 0) for s in leaves}
    cols = OrderedDict((n, []) for n in names)
    for rg in meta[4]:
        for cc in rg[1]:
            md = cc[3]
            name = b'.'.join(md[3]).decode()
            if name not in cols:
                continue
            if md[1] != 6 or repetition.get(name) == 2:
                raise ValueError('column %s is not a flat BYTE_ARRAY column' % name)
            codec = _CODECS.get(md[4])
            if codec is None:
                raise ValueError('unsupported codec %s for %s' % (md[4], name))
            max_def = 1 if repetition[name] == 1 else 0
            pos = min(x for x in (md.get(11), md[9]) if x is not None)
            dictionary, got = None, 0
            while got < md[5]:
                th = ThriftCompact(data, pos)
                ph = th.struct()
                body = data[th.pos:th.pos + ph[3]]
                pos = th.pos + ph[3]
                if ph[1] == 2:
                    dictionary, _ = _plain_byte_arrays(codec(body), 0, ph[7][1])
                    continue
                if ph[1] == 0:
                    n, enc = ph[5][1], ph[5][2]
                    raw, p = codec(body), 0
                    if max_def:
                        ln = int.from_bytes(raw[:4], 'little')
                        defs = rle_bitpacked_hybrid(raw, 4, 1, n)[0]
                        p = 4 + ln
                    else:
                        defs = [0] * n
                elif ph[1] == 3:
                    h2 = ph[8]
                    n, enc, dl, rl = h2[1], h2[4], h2[5], h2[6]
                    raw = codec(body[rl + dl:]) if h2.get(7, True) else bytes(body[rl + dl:])
                    defs = rle_bitpacked_hybrid(body[:rl + dl], rl, 1, n)[0] if max_def else [0] * n
                    p = 0
                else:
                    raise ValueError('unsupported page type %s' % ph[1])
                n_present = sum(1 for d in defs if d == max_def)
                if enc in (2, 8):
                    if dictionary is None:
                        raise ValueError('dictionary-encoded page without a dictionary')
                    idx = rle_bitpacked_hybrid(raw, p + 1, raw[p], n_present)[0]
                    values = [dictionary[i] for i in idx]
                elif enc == 0:
                    values = _plain_byte_arrays(raw, p, n_present)[0]
                else:
                    raise ValueError('unsupported encoding %s' % enc)
                it = iter(values)
                cols[name].extend(next(it).decode() if d == max_def else None for d in defs)
                got += n
    return meta[3], cols


# ------------------------------------------------------------------ cue registry (static parse; never imported)
def parse_cue_registry(src: bytes):
    tree = ast.parse(src)
    strings, tasks, cohorts = {}, None, None
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)):
            continue
        name, val = node.targets[0].id, node.value
        if isinstance(val, ast.Constant) and isinstance(val.value, str):
            strings[name] = val.value
        elif name == 'TASKS':
            tasks = tuple(ast.literal_eval(val))
        elif name == 'COHORTS' and isinstance(val, ast.Dict):
            cohorts = {}
            for k, v in zip(val.keys, val.values):
                key = strings.get(k.id) if isinstance(k, ast.Name) else ast.literal_eval(k)
                cohorts[key] = ast.literal_eval(v)
    return tasks, cohorts, strings.get('COHORT')


# ------------------------------------------------------------------ the inventory
def build(root: Path = REPO, pins=None):
    ctx = Ctx(root)
    pins = OrderedDict(PINS if pins is None else pins)

    # 1. pinned frame -------------------------------------------------------------------------------------------
    ent = ctx.register(P['m01_instances'], 'pinned 500-row source (M01)', 'json-decoded per line; accessed: metadata fields of every row')
    if not ent['exists']:
        raise InventoryAbort('missing pinned source %s' % P['m01_instances'])
    raw = ctx.read(P['m01_instances'])
    rows = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
    ids = [r['instance_id'] for r in rows]
    if len(rows) != pins['n_rows'] or len(set(ids)) != len(ids):
        raise InventoryAbort('pinned source has %d rows / %d unique IDs, expected %d unique'
                             % (len(rows), len(set(ids)), pins['n_rows']))
    frame = set(ids)
    by_id = {r['instance_id']: r for r in rows}
    src_sha = ent['sha256']
    ctx.pin('instances_jsonl_sha256_equals_pin', src_sha == pins['source_sha256'],
            'instances.jsonl %s vs pin %s' % (src_sha, pins['source_sha256']), P['m01_instances'])
    for r in rows:
        if r['instance_id'].rsplit('-', 1)[0] != r['repo'].replace('/', '__'):
            raise InventoryAbort('instance_id %s does not match repo %s' % (r['instance_id'], r['repo']))
    pats = id_patterns(ids)
    for iid in ids:
        ctx.touch(iid, 'metadata_static', P['m01_instances'], frame, 'm01 instances')

    # 1b. dataset revision -> parquet sha256 -> evaluator (committed pin chain) --------------------------------------
    dl = ctx.load_json(P['download_audit'], 'verified pinned dataset download (revision -> parquet sha256)',
                       'parsed: dataset, revision, file, sha256, upstream_lfs_sha256')
    ctx.pin('download_audit_binds_revision_to_parquet_sha256',
            dl is not None and dl.get('dataset') == pins['dataset'] and dl.get('revision') == pins['dataset_revision']
            and dl.get('file') == pins['dataset_file'] and dl.get('sha256') == pins['dataset_sha256']
            and dl.get('upstream_lfs_sha256') == pins['dataset_sha256'],
            'missing' if dl is None else '%s@%s %s sha256 %s (upstream LFS %s)' % (
                dl.get('dataset'), dl.get('revision'), dl.get('file'), dl.get('sha256'), dl.get('upstream_lfs_sha256')),
            P['download_audit'])
    sel = ctx.load_json(P['evaluator_selection'], 'v2 evaluator/dataset selection (revision, evaluator commit)',
                        'parsed: dataset.{repository, revision, expected_instances}, evaluator.commit')
    sel_ds, sel_ev = (sel or {}).get('dataset') or {}, (sel or {}).get('evaluator') or {}
    ctx.pin('evaluator_selection_pins_revision_and_evaluator',
            sel is not None and sel_ds.get('repository') == pins['dataset']
            and sel_ds.get('revision') == pins['dataset_revision'] and sel_ev.get('commit') == pins['evaluator_commit']
            and sel_ds.get('expected_instances') == pins['n_rows'],
            'missing' if sel is None else '%s@%s, evaluator %s, expected %s' % (
                sel_ds.get('repository'), sel_ds.get('revision'), sel_ev.get('commit'), sel_ds.get('expected_instances')),
            P['evaluator_selection'])

    # 2. M01 summary, reset check, gate code, control-plan template ------------------------------------------------
    metadata_gate_unknown = False
    m01s = ctx.load_json(P['m01_summary'], 'M01 summary (dataset/evaluator pins, gate counts, not_done)',
                         'parsed: dataset, evaluator, qualification, empty_pass_to_pass_limitation, construction_ok, '
                         'not_done')
    if m01s is None:
        metadata_gate_unknown = True
        ctx.unknown('global', 'metadata_gate', P['m01_summary'], 'M01 summary missing')
        ctx.pin('m01_summary_dataset_and_evaluator_equal_pins', False, 'missing', P['m01_summary'])
    else:
        ok_pin = ctx.pin('m01_summary_dataset_and_evaluator_equal_pins',
                         m01s['dataset'].get('sha256') == pins['dataset_sha256']
                         and m01s['dataset'].get('rows') == pins['n_rows']
                         and m01s['evaluator'].get('commit') == pins['evaluator_commit'],
                         'dataset %s rows %s evaluator %s' % (m01s['dataset'].get('sha256'), m01s['dataset'].get('rows'),
                                                               m01s['evaluator'].get('commit')), P['m01_summary'])
        ok_rows = ctx.check('m01_row_counts_reconcile',
                            m01s['dataset']['rows'] == len(rows)
                            and m01s['qualification'].get('eligible') == sum(r['qualification'] == 'eligible'
                                                                              for r in rows)
                            and m01s['empty_pass_to_pass_limitation'] == sum(bool(r['limitations']) for r in rows)
                            and m01s['construction_ok'] == sum(r.get('construction') == 'ok' for r in rows),
                            'summary counts vs instances.jsonl rows')
        if not (ok_pin and ok_rows):
            metadata_gate_unknown = True
            ctx.unknown('global', 'metadata_gate', P['m01_summary'], 'M01 summary does not reconcile with the pins/rows')
    ctx.register(P['m01_code'], 'M01 metadata construction code (defines the static gate)', 'hashed only')
    ctx.register(P['m02_code'], 'M02 test-list rule qualify_instances.qualify (eligible/refused = test-list validity)',
                 'hashed only')
    reset = ctx.load_json(P['m01_reset'], 'M01 static reset check of generated eval-script text',
                          'parsed: checked, with_problems, new_file_only_test_patches, note (short IDs)')
    if reset is None:
        ctx.unknown('global', 'category', P['m01_reset'], 'reset-check record missing: source-inspection touches unknown')
    else:
        for iid in ids:
            ctx.touch(iid, 'metadata_static', P['m01_reset'], frame, 'reset check')
        f_ids, s_ids = find_ids(reset.get('note', '').encode(), pats, frame)
        flagged = f_ids | s_ids
        if ctx.check('reset_check_flag_count_reconciles', len(flagged) == reset.get('new_file_only_test_patches'),
                     'note names %d IDs; new_file_only_test_patches=%s' % (len(flagged),
                                                                         reset.get('new_file_only_test_patches'))):
            for iid in flagged:
                ctx.touch(iid, 'source_inspection', P['m01_reset'] + '#note (first-pass flag; static)', frame,
                          'reset check')
        else:
            ctx.unknown('global', 'category', P['m01_reset'], 'flagged reset-check IDs cannot be resolved from the note')
        ctx.check('reset_check_covers_all_rows', reset.get('checked') == len(rows) and reset.get('with_problems') == 0,
                  'checked=%s with_problems=%s' % (reset.get('checked'), reset.get('with_problems')))
    tmpl = ctx.load_json(P['control_template'], 'non-executing control-plan template',
                         'parsed: m01_instances_sha256, records[*].{instance_id, control}, smoke_check.acceptance, '
                         'controls')
    template_controls, template_acceptance = None, None
    if tmpl is None:
        ctx.pin('control_template_cites_instances_sha256', False, 'missing', P['control_template'])
    else:
        t_ids = Counter(r['instance_id'] for r in tmpl['records'])
        for iid in t_ids:
            ctx.touch(iid, 'metadata_static', P['control_template'] + ' (template only; nothing executed)', frame,
                      'control-plan template')
        ctx.pin('control_template_cites_instances_sha256', tmpl.get('m01_instances_sha256') == src_sha,
                str(tmpl.get('m01_instances_sha256')), P['control_template'])
        ctx.check('template_covers_frame_twice', set(t_ids) == frame and set(t_ids.values()) == {2},
                  '%d IDs, per-ID record counts %s' % (len(t_ids), sorted(set(t_ids.values()))))
        template_controls = tmpl.get('controls')
        template_acceptance = tmpl.get('smoke_check', {}).get('acceptance')
    ctx.register(P['runbook'], 'SWE-bench control runbook (governing runtime rules, acceptance record schema)',
                 'hashed only')

    # 3. qualification manifest, status, per-ID records, smoke record, legacy manifest --------------------------------
    manifest = ctx.load_json(P['qual_manifest'], 'lead qualification manifest (12 selected)',
                             'parsed: source_sha256, tasks[*].instance_id')
    status = ctx.load_json(P['qual_status'], 'qualification batch status',
                           'parsed: planned_new, reused, completed[*].{instance_id, qualified, stage_failed, acceptance}')
    legacy = ctx.load_json(P['qual_legacy'], 'immutable hash binding of legacy qualification records',
                           'parsed: expected_identity, records[*].{instance_id, summary, sha256}')
    smoke = ctx.load_json(P['smoke_flask'], 'REQ-002 runtime smoke check record (reused as 12th qualification)',
                          'parsed: instance_id, acceptance, smoke_check_passed')
    ctx.register(P['qual_code'], 'qualification procedure and bae161f acceptance keys', 'hashed only')
    ctx.register(P['control_adapter_code'], 'control adapter v2 qualification rules', 'hashed only')
    for rel, what in ((P['qual_manifest'], 'qualification manifest'), (P['qual_status'], 'qualification status'),
                      (P['smoke_flask'], 'smoke record')):
        if ctx.registry[rel]['exists'] is False:
            ctx.unknown('global', 'category', rel, '%s missing: evaluator-qualification touches cannot be reconciled'
                        % what)
    runtime = {}            # iid -> OrderedDict(status, failed_acceptance_keys, record, ...)
    acceptance_keysets = []
    manifest_ids = []
    if manifest is None:
        ctx.pin('qualification_manifest_cites_instances_sha256', False, 'missing', P['qual_manifest'])
    else:
        manifest_ids = [t['instance_id'] for t in manifest['tasks']]
        ctx.pin('qualification_manifest_cites_instances_sha256', manifest.get('source_sha256') == src_sha,
                str(manifest.get('source_sha256')), P['qual_manifest'])
        for iid in manifest_ids:
            ctx.touch(iid, 'frame_selection', P['qual_manifest'] + ' (qualification selection)', frame, 'manifest')
    if status is not None and manifest is not None:
        planned, reused = list(status['planned_new']), list(status['reused'])
        if set(planned) | set(reused) != set(manifest_ids) or set(planned) & set(reused):
            raise InventoryAbort('qualification status planned_new+reused %s does not reconcile with manifest %s'
                                 % (sorted(set(planned) | set(reused)), sorted(manifest_ids)))
        done = OrderedDict((c['instance_id'], c) for c in status.get('completed', []))
        if not set(done) <= set(planned):
            raise InventoryAbort('status completed IDs outside planned_new: %s' % sorted(set(done) - set(planned)))
        ctx.register(P['qual_dir'], 'qualification record directory listing', 'child names only')
        dirs = [d for d in ctx.listdir(P['qual_dir']) if (ctx.root / P['qual_dir'] / d).is_dir()]
        if set(dirs) != set(planned):
            raise InventoryAbort('qualification record directories %s do not reconcile with planned_new %s'
                                 % (sorted(dirs), sorted(planned)))
        legacy_hash = {}
        if legacy is not None:
            legacy_hash = {r['instance_id']: r['sha256'] for r in legacy['records']}
            if not set(legacy_hash) <= set(planned):
                raise InventoryAbort('legacy hash manifest names IDs outside planned_new: %s'
                                     % sorted(set(legacy_hash) - set(planned)))
            lid = legacy['expected_identity']
            ctx.pin('legacy_manifest_identity_equals_pins',
                    lid.get('source_sha256') == src_sha and lid.get('dataset_sha256') == pins['dataset_sha256']
                    and lid.get('evaluator_commit') == pins['evaluator_commit'],
                    json.dumps(lid, sort_keys=True), P['qual_legacy'])
            for iid in legacy_hash:
                ctx.touch(iid, 'evaluator_qualification', P['qual_legacy'] + '#records (hash binding)', frame, 'legacy')
        else:
            ctx.pin('legacy_manifest_identity_equals_pins', False, 'missing', P['qual_legacy'])
        for iid in planned:
            ctx.touch(iid, 'evaluator_qualification', P['qual_status'] + '#planned_new', frame, 'status')
        for iid in reused:
            ctx.touch(iid, 'evaluator_qualification', P['qual_status'] + '#reused', frame, 'status')
        for iid in planned:
            rel = '%s/%s/summary.json' % (P['qual_dir'], iid)
            e = ctx.register(rel, 'per-ID runtime qualification record',
                             'json-decoded (all keys); accessed: instance_id, qualified, acceptance, stage_failed, '
                             'identity/platform evaluator_commit')
            ctx.touch(iid, 'evaluator_qualification', '%s/%s/' % (P['qual_dir'], iid), frame, 'qualification dir')
            info = OrderedDict(status='untested', failed_acceptance_keys=[], record=rel, record_sha256=e['sha256'],
                               source='qualification_20260922', hash_checks=OrderedDict())
            runtime[iid] = info
            if not e['exists']:
                info['status'] = 'UNKNOWN'
                ctx.unknown('id', 'runtime_gate', rel, 'qualification record missing', ids=[iid])
                continue
            rec = json.loads(ctx.read(rel))
            if rec.get('instance_id') != iid:
                raise InventoryAbort('%s names %r' % (rel, rec.get('instance_id')))
            ev = (rec.get('identity') or {}).get('evaluator_commit') or (rec.get('platform') or {}).get('evaluator_commit')
            acc = rec.get('acceptance')
            if rec.get('stage_failed'):
                verdict, failed = 'fail', ['stage_failed:%s' % rec['stage_failed']]
            elif isinstance(rec.get('qualified'), bool) and isinstance(acc, dict):
                acceptance_keysets.append(tuple(acc))
                failed = [k for k, v in acc.items() if not v]
                verdict = 'pass' if rec['qualified'] and not failed else 'fail'
                if rec['qualified'] != (not failed):
                    verdict = 'UNKNOWN'
                    ctx.unknown('id', 'runtime_gate', rel, 'qualified flag disagrees with acceptance keys', ids=[iid])
            else:
                verdict, failed = 'UNKNOWN', []
                ctx.unknown('id', 'runtime_gate', rel, 'record is not terminal', ids=[iid])
            info.update(status=verdict, failed_acceptance_keys=failed, evaluator_commit=ev)
            if ev != pins['evaluator_commit']:
                info['status'] = 'UNKNOWN'
                ctx.unknown('id', 'runtime_gate', rel, 'record evaluator %r differs from the pin' % ev, ids=[iid])
            st = done.get(iid)
            if st is None or bool(st.get('qualified')) != (verdict == 'pass') or (st.get('acceptance') or {}) != (acc or {}):
                info['status'] = 'UNKNOWN'
                ctx.unknown('id', 'runtime_gate', P['qual_status'], 'status.json entry does not reconcile with %s' % rel,
                            ids=[iid])
            if legacy is not None:
                ok = legacy_hash.get(iid) == e['sha256']
                info['hash_checks']['legacy_hash_manifest'] = ok
                if not ok:
                    info['status'] = 'UNKNOWN'
                    ctx.unknown('id', 'runtime_gate', P['qual_legacy'], 'record sha256 %s != legacy manifest %s'
                                % (e['sha256'], legacy_hash.get(iid)), ids=[iid])
        for iid in reused:
            info = OrderedDict(status='untested', failed_acceptance_keys=[], record=P['smoke_flask'],
                               record_sha256=ctx.registry[P['smoke_flask']]['sha256'], source='smoke_flask_20260922',
                               hash_checks=OrderedDict())
            runtime[iid] = info
            if smoke is None or smoke.get('instance_id') != iid:
                info['status'] = 'UNKNOWN'
                ctx.unknown('id', 'runtime_gate', P['smoke_flask'], 'reused smoke record missing or names another ID',
                            ids=[iid])
                continue
            ctx.touch(iid, 'evaluator_qualification', P['smoke_flask'], frame, 'smoke record')
            acc = smoke.get('acceptance') or {}
            acceptance_keysets.append(tuple(acc))
            failed = [k for k, v in acc.items() if not v]
            passed = bool(smoke.get('smoke_check_passed'))
            info.update(status='pass' if passed and not failed else ('fail' if failed else 'UNKNOWN'),
                        failed_acceptance_keys=failed)
            if passed == bool(failed):
                ctx.unknown('id', 'runtime_gate', P['smoke_flask'], 'smoke_check_passed disagrees with acceptance',
                            ids=[iid])
    else:
        q_ids = set(manifest_ids) | set((status or {}).get('planned_new', [])) | set((status or {}).get('reused', []))
        q_ids |= {r['instance_id'] for r in (legacy or {}).get('records', [])} | {(smoke or {}).get('instance_id')}
        q_ids &= frame
        for iid in q_ids:
            runtime[iid] = unknown_runtime()
        missing = ', '.join(r for r, x in ((P['qual_manifest'], manifest), (P['qual_status'], status)) if x is None)
        ctx.unknown('id', 'runtime_gate', missing, 'qualification manifest or status missing: runtime gate not '
                    'reconcilable', ids=q_ids)
    acceptance_keys = list(acceptance_keysets[0]) if acceptance_keysets else []
    ctx.check('acceptance_key_set_identical_across_records', len(set(acceptance_keysets)) <= 1,
              'distinct key sets: %d' % len(set(acceptance_keysets)))

    # 4. pilot frame and spec -------------------------------------------------------------------------------------
    pf = ctx.load_json(P['pilot_frame'], 'frozen pilot frame (DEV task selection)',
                       'parsed: expected_identity, frame.tasks[*].{instance_id, qualified, failed_acceptance, record, '
                       'record_sha256}, frame.diagnosed_unqualified, pilot.{ranked_eligible, tasks, excluded, '
                       'excluded_reason}, hashes')
    ctx.register(P['pilot_spec'], 'fixed-backend development pilot specification', 'hashed only (spec_sha256 check)')
    pilot_selected, frame_roles = set(), defaultdict(list)
    pf_sha = ctx.registry[P['pilot_frame']]['sha256']
    if pf is None:
        ctx.unknown('global', 'category', P['pilot_frame'], 'pilot frame missing: frame selection not reconcilable')
        ctx.pin('pilot_frame_identity_equals_pins', False, 'missing', P['pilot_frame'])
    else:
        ident = pf['expected_identity']
        ctx.pin('pilot_frame_identity_equals_pins',
                ident.get('source_sha256') == src_sha and ident.get('dataset_sha256') == pins['dataset_sha256']
                and ident.get('evaluator_commit') == pins['evaluator_commit'],
                json.dumps(ident, sort_keys=True), P['pilot_frame'])
        for key, rel in (('manifest_sha256', P['qual_manifest']), ('legacy_hash_manifest_sha256', P['qual_legacy']),
                         ('spec_sha256', P['pilot_spec'])):
            cited = ident.get(key) if key == 'manifest_sha256' else pf.get(key)
            detail = '%s cites %s; disk %s' % (rel, cited, ctx.registry[rel]['sha256'])
            if key == 'manifest_sha256':
                ctx.pin('pilot_frame_manifest_sha256_matches_disk', cited == ctx.registry[rel]['sha256'], detail, rel)
                continue
            ok = ctx.check('pilot_frame_%s_matches_disk' % key, cited == ctx.registry[rel]['sha256'], detail)
            if not ok and key == 'legacy_hash_manifest_sha256':
                q_ids = [i for i, x in runtime.items() if x.get('source') == 'qualification_20260922']
                for iid in q_ids:
                    runtime[iid]['status'] = 'UNKNOWN'
                ctx.unknown('id', 'runtime_gate', rel, 'legacy hash manifest differs from the pilot-frame citation',
                            ids=q_ids)
            elif not ok:
                ctx.unknown('global', 'note', rel, 'pilot spec differs from the pilot-frame citation')
        if legacy is not None:
            same = ctx.pin('legacy_identity_equals_pilot_frame_identity', legacy['expected_identity'] == ident,
                           'legacy expected_identity vs pilot frame expected_identity', P['qual_legacy'])
            if not same:
                q_ids = [i for i, x in runtime.items() if x.get('source') == 'qualification_20260922']
                for iid in q_ids:
                    runtime[iid]['status'] = 'UNKNOWN'
                ctx.unknown('id', 'runtime_gate', P['qual_legacy'], 'legacy identity differs from the pilot frame',
                            ids=q_ids)
        f_tasks = pf['frame']['tasks']
        f_ids = [t['instance_id'] for t in f_tasks]
        if manifest is not None and set(f_ids) != set(manifest_ids):
            raise InventoryAbort('pilot frame tasks %s do not reconcile with the manifest %s'
                                 % (sorted(f_ids), sorted(manifest_ids)))
        ranked = pf['pilot']['ranked_eligible']
        pilot_selected = {t['instance_id'] for t in pf['pilot']['tasks']}
        excluded = list(pf['pilot'].get('excluded', []))
        dq = list(pf['frame'].get('diagnosed_unqualified', []))
        for iid in f_ids + [t['instance_id'] for t in ranked] + list(pilot_selected) + excluded + dq:
            if iid not in set(f_ids):
                raise InventoryAbort('pilot frame lists %s outside its own frame tasks' % iid)
        for t in f_tasks:
            iid = t['instance_id']
            ctx.touch(iid, 'frame_selection', P['pilot_frame'] + '#frame', frame, 'pilot frame')
            frame_roles[iid].append('frame_task(qualified=%s)' % t.get('qualified'))
            info = runtime.get(iid)
            disk = ctx.registry.get(t['record'], {}).get('sha256')
            ok = disk == t['record_sha256']
            if info is None:
                runtime[iid] = unknown_runtime(t.get('record'))
                ctx.unknown('id', 'runtime_gate', P['pilot_frame'], 'frame task has no qualification record', ids=[iid])
                continue
            info['hash_checks']['pilot_frame_record_sha256'] = ok
            if not ok:
                info['status'] = 'UNKNOWN'
                ctx.unknown('id', 'runtime_gate', t['record'], 'record sha256 %s != pilot-frame record_sha256 %s'
                            % (disk, t['record_sha256']), ids=[iid])
            elif info['status'] in ('pass', 'fail') and (
                    bool(t.get('qualified')) != (info['status'] == 'pass')
                    or sorted(t.get('failed_acceptance', [])) != sorted(info['failed_acceptance_keys'])):
                info['status'] = 'UNKNOWN'
                ctx.unknown('id', 'runtime_gate', P['pilot_frame'], 'frame verdict disagrees with the record', ids=[iid])
        for iid in dq:
            frame_roles[iid].append('diagnosed_unqualified')
        for i, t in enumerate(ranked, 1):
            frame_roles[t['instance_id']].append('ranked_eligible#%d(selected=%s)' % (i, t.get('selected')))
        for iid in sorted(pilot_selected):
            frame_roles[iid].append('pilot_selected')
        for iid in excluded:
            frame_roles[iid].append('pilot_excluded: %s' % pf['pilot'].get('excluded_reason'))
        ctx.check('pilot_selection_subset_of_ranked_selected',
                  pilot_selected == {t['instance_id'] for t in ranked if t.get('selected')}, '')
        n_rec_ok = sum(ctx.registry.get(t['record'], {}).get('sha256') == t['record_sha256'] for t in f_tasks)
        ctx.check('pilot_frame_record_sha256_match_disk', n_rec_ok == len(f_tasks),
                  '%d of %d cited qualification-record hashes match the files on disk' % (n_rec_ok, len(f_tasks)))

    # 5. DEV cohorts (existence of episodes only) -----------------------------------------------------------------
    ctx.register(P['pilot_runner'], 'cohort runner defining block manifest keys (ran, skipped_completed, '
                                    'retained_incomplete, unstarted, unconfirmed_*)', 'hashed only')
    cohort_ran, cohort_ids = OrderedDict(), OrderedDict()
    registered_episode_dirs = {}      # rel dir -> instance_id
    for c in COHORTS:
        ctx.register(c['dir'], '%s directory listing' % c['label'], 'child names only')
        ctx.register(c['dir'] + '/block_1_start.json', '%s block start record' % c['label'],
                     'hashed only (ID mentions covered by the mention scan)')
        blk = ctx.load_json(c['block'], '%s manifest' % c['label'],
                            'frame_sha256, cohort, amendment_sha256, ran[*].{instance_id, backend, run_id}, '
                            'skipped_completed, retained_incomplete, unstarted, unconfirmed_*', keep=BLOCK_KEYS)
        b = ctx.load_json(c['binding'], '%s cohort binding' % c['label'], 'cohort, amendment_sha256',
                          keep=BINDING_KEYS) if c['binding'] else None
        if b is not None:
            ctx.check('%s_binding_cohort_matches' % c['key'], b.get('cohort') == c['cohort_name']
                      and (blk or {}).get('cohort') == c['cohort_name'], str(b.get('cohort')))
        if c['spec']:
            sp = ctx.load_json(c['spec'], '%s amendment spec' % c['label'],
                               'cohort, frame, frame_sha256, base_spec, base_spec_sha256', keep=DEV2_SPEC_KEYS) or {}
            sp_sha, base_sha = ctx.registry[c['spec']]['sha256'], ctx.registry[P['pilot_spec']]['sha256']
            ctx.check('%s_spec_cites_pilot_frame_and_base_spec' % c['key'],
                      sp.get('cohort') == c['cohort_name'] and sp.get('frame') == P['pilot_frame']
                      and sp.get('frame_sha256') == pf_sha and sp.get('base_spec') == P['pilot_spec']
                      and sp.get('base_spec_sha256') == base_sha,
                      'frame %s sha256 %s; base spec %s sha256 %s' % (sp.get('frame'), sp.get('frame_sha256'),
                                                                      sp.get('base_spec'), sp.get('base_spec_sha256')))
            ctx.check('%s_amendment_sha256_matches_spec' % c['key'],
                      sp_sha is not None and (blk or {}).get('amendment_sha256') == sp_sha
                      and (b or {}).get('amendment_sha256') == sp_sha,
                      'spec %s; block %s; binding %s' % (sp_sha, (blk or {}).get('amendment_sha256'),
                                                         (b or {}).get('amendment_sha256')))
        if blk is None:
            ctx.unknown('global', 'category', c['block'], '%s manifest missing: its model episodes cannot be enumerated'
                        % c['label'])
            cohort_ran[c['key']] = None
            continue
        run_dirs, named = set(), set()

        def reg_dir(name, iid, why):
            parsed = parse_episode_dirname(name)
            if parsed is None or parsed[0] != iid:
                ctx.unknown('id', 'note', c['block'], '%s directory %s does not start with its instance_id'
                            % (why, name), ids=[iid])
            d = '%s/%s' % (c['dir'], name)
            ctx.touch(iid, 'model_outcome_episode', d + '/', frame, c['key'])
            registered_episode_dirs[d] = iid
            run_dirs.add(name)
            return d

        ran = [OrderedDict((k, r[k]) for k in ('instance_id', 'backend', 'run_id')) for r in blk['ran']]
        for r in ran:
            iid = r['instance_id']
            ctx.touch(iid, 'model_outcome_episode', c['block'] + '#ran', frame, c['key'])
            named.add(iid)
            d = reg_dir(r['run_id'], iid, 'ran')
            if pf is not None and iid not in pilot_selected:
                ctx.unknown('id', 'note', c['block'], 'cohort ran an ID outside the frozen pilot selection', ids=[iid])
            if not (ctx.root / d / 'episode.json').exists():
                ctx.unknown('id', 'note', d, 'listed episode directory or its episode.json is absent (existence only; '
                            'exposure kept from the manifest)', ids=[iid])
        for key in ('skipped_completed', 'retained_incomplete', 'unstarted'):
            for r in blk.get(key) or []:
                iid = r.get('instance_id') if isinstance(r, dict) else None
                if iid is None:
                    ctx.unknown('global', 'category', c['block'], '%s entry without instance_id' % key)
                    continue
                named.add(iid)
                if key == 'unstarted':
                    ctx.touch(iid, 'frame_selection', c['block'] + '#unstarted (queued, never started)', frame, c['key'])
                    continue
                ctx.touch(iid, 'model_outcome_episode', '%s#%s' % (c['block'], key), frame, c['key'])
                if key == 'skipped_completed':
                    if r.get('run_id'):
                        d = reg_dir(r['run_id'], iid, key)
                        if not (ctx.root / d / 'episode.json').exists():
                            ctx.unknown('id', 'note', d, 'skipped_completed episode directory or episode.json absent '
                                        '(existence only)', ids=[iid])
                    else:
                        ctx.unknown('id', 'note', c['block'], 'skipped_completed entry without run_id', ids=[iid])
                else:
                    for rd in r.get('run_dirs') or []:
                        reg_dir(rd, iid, key)
        for rid in blk.get('unconfirmed_container_runs') or []:
            parsed = parse_episode_dirname(rid) if isinstance(rid, str) else None
            if parsed is None or parsed[0] not in frame:
                ctx.unknown('global', 'category', c['block'], 'unattributable unconfirmed container run %r' % (rid,))
                continue
            ctx.touch(parsed[0], 'model_outcome_episode', c['block'] + '#unconfirmed_container_runs', frame, c['key'])
            named.add(parsed[0])
            reg_dir(rid, parsed[0], 'unconfirmed container run')
        if blk.get('unconfirmed_episode_pids'):
            ctx.unknown('global', 'category', c['block'], 'unconfirmed episode PIDs cannot be attributed to IDs')
        cohort_ran[c['key']] = ran
        cohort_ids[c['key']] = named
        if pf_sha is not None and not ctx.check('%s_frame_sha256_matches_pilot_frame' % c['key'],
                                                blk.get('frame_sha256') == pf_sha, str(blk.get('frame_sha256'))):
            ctx.unknown('id', 'note', c['block'], 'cohort frame_sha256 differs from the pilot frame on disk',
                        ids=sorted(named & frame))
        unlisted = []
        for name in ctx.listdir(c['dir']):
            if not (ctx.root / c['dir'] / name).is_dir() or name in run_dirs:
                continue
            unlisted.append(name)
            parsed = parse_episode_dirname(name)
            if parsed and parsed[0] in frame:
                ctx.unknown('id', 'category', '%s/%s' % (c['dir'], name),
                            'episode-like directory not listed in %s' % c['block'], ids=[parsed[0]])
            else:
                ctx.unknown('global', 'category', '%s/%s' % (c['dir'], name), 'unattributable directory in a cohort dir')
        n_present = sum((ctx.root / c['dir'] / r['run_id'] / 'episode.json').exists() for r in ran)
        ctx.check('%s_listed_episodes_present' % c['key'], n_present == len(ran),
                  '%d of %d ran entries have an episode directory with episode.json (existence only)'
                  % (n_present, len(ran)))
        ctx.check('%s_no_unlisted_episode_dirs' % c['key'], not unlisted, '%d unlisted directories' % len(unlisted))
        ctx.check('%s_manifest_has_no_skipped_retained_or_unconfirmed_entries' % c['key'],
                  not any(blk.get(k) for k in ('skipped_completed', 'retained_incomplete', 'unconfirmed_container_runs',
                                               'unconfirmed_episode_pids')),
                  'entries other than ran are counted as exposure (existence only)')
        if pf is not None:
            ctx.check('%s_ran_ids_equal_pilot_selection' % c['key'], {r['instance_id'] for r in ran} == pilot_selected,
                      '%d ran entries over %d IDs' % (len(ran), len({r['instance_id'] for r in ran})))

    # 6. agent smoke episodes (directory names only) ---------------------------------------------------------------
    smoke_episodes = []
    ctx.register(P['smoke_audit'], 'lead audit listing the smoke episode directories',
                 'raw-byte substring check of directory paths only (never parsed)')
    if not ctx.exists(P['smoke_dir']):
        ctx.register(P['smoke_dir'], 'agent smoke episode directories', 'directory names only')
        ctx.unknown('global', 'category', P['smoke_dir'], 'smoke episode directory missing')
    else:
        ctx.register(P['smoke_dir'], 'agent smoke episode directories', 'directory names only; no file opened')
        audit_raw = ctx.read(P['smoke_audit']) if ctx.registry[P['smoke_audit']]['exists'] else b''
        for name in ctx.listdir(P['smoke_dir']):
            d = '%s/%s' % (P['smoke_dir'], name)
            parsed = parse_episode_dirname(name)
            if not (ctx.root / d).is_dir():
                continue
            if parsed is None:
                ctx.unknown('global', 'category', d, 'unattributable smoke directory name')
                continue
            iid, backend = parsed
            ctx.touch(iid, 'model_outcome_episode', d + '/', frame, 'smoke episode dir')
            registered_episode_dirs[d] = iid
            in_audit = ('"%s"' % d).encode() in audit_raw
            smoke_episodes.append(OrderedDict(instance_id=iid, backend=backend, directory=d,
                                              episode_json_present=(ctx.root / d / 'episode.json').exists(),
                                              named_in_lead_audit=in_audit))
            if not in_audit:
                ctx.unknown('id', 'note', P['smoke_audit'], 'smoke directory %s not named in the lead audit' % d,
                            ids=[iid])
        ctx.check('smoke_episode_dirs_named_in_lead_audit', all(s['named_in_lead_audit'] for s in smoke_episodes),
                  '%d smoke episode directories' % len(smoke_episodes))
        ctx.check('smoke_episode_dirs_have_episode_json', all(s['episode_json_present'] for s in smoke_episodes),
                  'existence only')

    # 7. third-party recorded episodes (task_ids and file identity kept; outcome tallies dropped on decode) ----------
    replay = ctx.load_json(P['replay_gap'], 'audit of a third-party SWE-bench trajectory release (its per-file '
                           'aggregate outcome tallies are dropped on decode, never read)',
                           'dataset, revision, unique_tasks_total, files[*].{file, sha256, task_ids}', keep=REPLAY_KEYS)
    third_party = None
    if replay is None:
        ctx.unknown('global', 'category', P['replay_gap'], 'third-party trajectory audit missing',
                    definitions=('conservative',))
    else:
        tp_ids = set()
        for f in replay['files']:
            for iid in f['task_ids']:
                ctx.touch(iid, 'third_party_recorded_episode', '%s#files[%s]' % (P['replay_gap'], f['file']), frame,
                          'third-party audit')
                tp_ids.add(iid)
        third_party = OrderedDict(dataset=replay.get('dataset'), revision=replay.get('revision'),
                                  files=[OrderedDict(file=f['file'], sha256=f.get('sha256'), n_task_ids=len(f['task_ids']))
                                         for f in replay['files']],
                                  n_distinct_task_ids=len(tp_ids),
                                  n_task_ids_in_pinned_frame=len(tp_ids & frame))
        ctx.check('third_party_distinct_task_ids_match_audit_total',
                  len(tp_ids) == replay.get('unique_tasks_total', len(tp_ids)),
                  '%d distinct task_ids, all in the pinned frame' % len(tp_ids))

    # 8. other evaluator use and inspection ------------------------------------------------------------------------
    m03 = ctx.load_json(P['m03'], 'M03 offline upstream-grader fixture run', 'parsed: instance_used, not_done')
    m03_not_done = []
    if m03 is None:
        ctx.unknown('global', 'category', P['m03'], 'M03 record missing')
    else:
        ctx.touch(m03['instance_used']['instance_id'], 'evaluator_other',
                  P['m03'] + ' (synthetic fixtures G01-G11 with this instance parser; no container, no model)', frame,
                  'm03')
        m03_not_done = list(m03.get('not_done', []))
    prov = ctx.load_json(P['django_provenance'], 'django provenance diagnosis (evaluator only)',
                         'parsed: task, scope, verdict')
    prov_verdict = None
    if prov is None:
        ctx.unknown('global', 'category', P['django_provenance'], 'django provenance record missing')
    else:
        ctx.touch(prov['task'], 'evaluator_other', DJANGO_PROVENANCE_DIR + ' (provenance.json and saved diagnostic '
                  'outputs; throwaway --rm diagnostic runs; no model)', frame, 'provenance')
        ctx.touch(prov['task'], 'source_inspection', P['django_provenance'] + ' (image/checkout/template inspection)',
                  frame, 'provenance')
        prov_verdict = OrderedDict(task=prov['task'], scope=prov.get('scope'), verdict=prov.get('verdict'))
    rt = ctx.load_json(P['runtime'], 'container runtime record', 'parsed: amd64_translation_check, vm.profile')
    ctx.register(P['protocol'], 'v2 protocol (infrastructure gate, strict grading rule, grouping rule)', 'hashed only')
    ctx.register(P['request_text'], 'lead request text (DTR-REQ-008) and committed host narrative',
                 'hashed; raw-byte phrase check for the server-log attribution only')

    # 9. planned cue-v1 frame (static AST parse; never imported) --------------------------------------------------
    cue = None
    ctx.register(P['cue_registry'], 'cue-v1 planned frame registry (not run)', 'static AST parse of TASKS/COHORTS')
    if not ctx.registry[P['cue_registry']]['exists']:
        ctx.unknown('global', 'category', P['cue_registry'], 'cue-v1 registry missing: planned frame not reconcilable')
    else:
        tasks, cohorts, cohort_name = parse_cue_registry(ctx.read(P['cue_registry']))
        if tasks is None or not cohorts or cohort_name not in cohorts:
            ctx.unknown('global', 'category', P['cue_registry'], 'cue-v1 TASKS/COHORTS could not be parsed statically')
        out_dir = 'results/v2_agent/%s' % (cohorts or {}).get(cohort_name, '')
        out_exists = bool(cohorts and cohort_name in cohorts) and (ctx.root / out_dir).exists()
        for iid in tasks or ():
            ctx.touch(iid, 'frame_selection', P['cue_registry'] + '#TASKS (planned cue-v1 frame; not run)', frame,
                      'cue registry')
            frame_roles[iid].append('cue_v1_planned')
        cue = OrderedDict(cohort=cohort_name, tasks=list(tasks or ()), output_dir=out_dir, output_dir_exists=out_exists)
        ctx.check('cue_v1_output_dir_absent', not out_exists, out_dir)
        if out_exists:
            ctx.unknown('id', 'category', out_dir, 'cue-v1 output directory exists but is not reconciled', ids=tasks)

    # 10. local dataset parquet (git-ignored): bytes hashed; footer + three columns decoded --------------------------
    parquet = OrderedDict(path=DATASET_PARQUET, present=(ctx.root / DATASET_PARQUET).exists())
    if parquet['present']:
        pdata = ctx.read(DATASET_PARQUET)
        parquet['sha256'] = sha256_bytes(pdata)
        ctx.pin('local_dataset_parquet_sha256_equals_pin', parquet['sha256'] == pins['dataset_sha256'],
                parquet['sha256'], DATASET_PARQUET)
        try:
            n_rows_pq, cols = read_parquet_columns(pdata, PARQUET_COLUMNS)
        except (ValueError, IndexError, KeyError, TypeError, UnicodeDecodeError) as exc:
            parquet['id_reconciliation'] = OrderedDict(status='not_verified', reason='stdlib decoder: %s' % exc)
            ctx.check('local_dataset_parquet_columns_decoded', False, str(exc))
        else:
            p_ids = cols['instance_id']
            same_order = p_ids == ids
            rep_ok = same_order and cols['repo'] == [by_id[i]['repo'] for i in ids]
            ver_ok = same_order and cols['version'] == [by_id[i]['version'] for i in ids]
            ok = n_rows_pq == len(ids) and same_order and rep_ok and ver_ok
            parquet['id_reconciliation'] = OrderedDict(
                status='verified' if ok else 'mismatch', columns_decoded=list(PARQUET_COLUMNS),
                method=('stdlib reader: footer and the instance_id/repo/version column chunks only (thrift compact, '
                        'snappy, dictionary/RLE); no other column decoded'),
                num_rows=n_rows_pq, n_unique_ids=len(set(p_ids)), same_ids_same_order=same_order,
                repo_equal_per_row=rep_ok, version_equal_per_row=ver_ok,
                id_set_sha256=id_list_sha256(x for x in p_ids if x is not None),
                ordered_column_sha256=OrderedDict(
                    (k, sha256_bytes(''.join('%s\n' % v for v in cols[k]).encode())) for k in PARQUET_COLUMNS))
            ctx.pin('local_dataset_parquet_ids_repo_version_equal_instances_jsonl', ok,
                    'rows %s; same order %s; repo %s; version %s' % (n_rows_pq, same_order, rep_ok, ver_ok),
                    DATASET_PARQUET)
    else:
        parquet['id_reconciliation'] = OrderedDict(
            status='not_present_locally',
            reason='git-ignored input absent; the committed pin chain (download audit -> M01 summary -> '
                   'instances.jsonl) is the reconciliation')

    # 11. tracked-file mention scan and path-name scan -------------------------------------------------------------
    scan = mention_scan(ctx, pats, frame)
    since_checkpoint = source_checkpoint_diff_scan(ctx, pats, frame)
    kinds_of = {iid: set(ctx.touches[iid]) for iid in ids}
    exposed_under = {d: {iid for iid in ids if kinds_of[iid] & DEFINITIONS[d]} for d in DEFINITIONS}
    roots_of = {iid: {evidence_root(e) for evs in ctx.touches[iid].values() for e in evs} for iid in ids}
    derivative, whitelist_used = defaultdict(set), OrderedDict()
    for rel, (full_ids, short_ids) in scan['mentions'].items():
        wl = DERIVATIVE_RECORD_WHITELIST.get(rel)
        wl_ok = wl is not None and scan['file_sha256'].get(rel) == wl['sha256']
        if wl is not None:
            whitelist_used[rel] = OrderedDict(sha256_pinned=wl['sha256'], sha256_observed=scan['file_sha256'].get(rel),
                                              accepted=wl_ok, reason=wl['reason'])
        for iid in sorted(full_ids | short_ids):
            if is_explained(rel, roots_of[iid]):
                continue
            derivative[iid].add(rel)
            if is_record_like(rel):
                if wl_ok:
                    continue
                not_exp = [d for d in DEFINITIONS if iid not in exposed_under[d]]
                if not_exp:
                    ctx.unknown('id', 'category', rel, 'record-like file mentions an ID that no registered touch '
                                'explains%s' % (' (whitelist sha256 mismatch)' if wl is not None else ''),
                                ids=[iid], definitions=not_exp)
            elif kinds_of[iid] <= {'metadata_static'}:
                ctx.unknown('id', 'category', rel, 'tracked file mentions an ID that no registered touch explains',
                            ids=[iid])
        for c in COHORTS:
            if rel.startswith(c['dir'] + '/') and cohort_ids.get(c['key']) is not None:
                extra = (full_ids | short_ids) - cohort_ids[c['key']]
                if extra:
                    ctx.unknown('id', 'category', rel, 'cohort-level record names IDs outside %s manifest entries'
                                % c['key'], ids=extra)
    for rel, wl in DERIVATIVE_RECORD_WHITELIST.items():
        if rel not in whitelist_used:
            whitelist_used[rel] = OrderedDict(sha256_pinned=wl['sha256'], sha256_observed=scan['file_sha256'].get(rel),
                                              accepted=None, reason=wl['reason'] + ' [no pinned-ID mention found]')
    exposed_any = set().union(*exposed_under.values())
    narrative = sorted('%s\t%s' % (rel, iid) for iid, rels in derivative.items()      # rule (b) covers metadata-only
                       if iid not in exposed_under['project_only'] and kinds_of[iid] - {'metadata_static'}
                       for rel in rels if not is_record_like(rel))
    listed = [x for x in narrative if x.split('\t')[1] not in exposed_any]
    review = OrderedDict(NARRATIVE_REVIEW, current_manifest_sha256=sha256_bytes('\n'.join(narrative).encode()),
                         current_mentions=listed, n_unlisted_conservative_exposed=len(narrative) - len(listed))
    review['current_matches_review'] = review['current_manifest_sha256'] == NARRATIVE_REVIEW['manifest_sha256']
    if not review['current_matches_review']:
        ctx.unknown('global', 'note', 'narrative mentions', 'unexplained narrative mentions of unexposed IDs changed '
                    'since the manual review (see narrative_mention_review)')
    for rel in scan['paths_with_ids']:
        for iid in ids_in_path(rel, pats, frame):
            if not path_is_registered(rel, iid, registered_episode_dirs, runtime):
                ctx.unknown('id', 'category', rel, 'path names a pinned ID outside registered locations', ids=[iid])

    # 12. uncommitted local run evidence (path names and mtimes only) ----------------------------------------------
    uncommitted = uncommitted_scan(ctx, pats, frame, smoke_episodes)
    for iid, paths in sorted(uncommitted['ids'].items()):
        bad = [p for p in paths if not any(p.startswith(r) and k in kinds_of[iid] for r, k in UNCOMMITTED_ROOTS)]
        not_exp = [d for d in DEFINITIONS if iid not in exposed_under[d]]
        if bad and not_exp:
            ctx.unknown('id', 'category', bad[0], 'uncommitted run path names an ID outside the mapped committed record '
                        'roots (%d such paths)' % len(bad), ids=[iid], definitions=not_exp)

    # 13. rows, categories, counts ---------------------------------------------------------------------------------
    rows_out = []
    for iid in sorted(ids):
        r = by_id[iid]
        kinds = kinds_of[iid]
        m02 = M02_STATUS.get(r.get('qualification'), 'unrecognized_m02_value')
        gate_pass = (m02 == 'test_lists_valid' and r.get('construction') == 'ok'
                     and bool(r.get('repo_version_in_constants')) and not r.get('fail_only_repo')
                     and bool(r.get('content_unchanged_by_construction')))
        mgate = OrderedDict(status='UNKNOWN' if metadata_gate_unknown else ('pass' if gate_pass else 'fail'),
                            m02_test_list_status=m02, reasons=list(r.get('reasons', [])),
                            limitations=list(r.get('limitations', [])), construction=r.get('construction'),
                            repo_version_in_constants=r.get('repo_version_in_constants'),
                            fail_only_repo=r.get('fail_only_repo'),
                            content_unchanged_by_construction=r.get('content_unchanged_by_construction'),
                            n_fail_to_pass=r.get('n_fail_to_pass'), n_pass_to_pass=r.get('n_pass_to_pass'))
        rgate = runtime.get(iid) or OrderedDict(status='untested', failed_acceptance_keys=[], record=None)
        cats = OrderedDict()
        for d, exposed_kinds in DEFINITIONS.items():
            cat = categorize(kinds, exposed_kinds)
            if cat != 'model_outcome_exposed' and id_has_category_unknown(ctx.unknowns, iid, d):
                cat = 'UNKNOWN'
            cats[d] = cat
        rows_out.append(OrderedDict(
            instance_id=iid, family=r['repo'], version=r['version'], repo_version_group='%s@%s' % (r['repo'], r['version']),
            content_sha256=r.get('content_sha256'), eval_script_sha256=r.get('eval_script_sha256'),
            instance_image_key=r.get('instance_image_key'), env_image_key=r.get('env_image_key'),
            base_image_key=r.get('base_image_key'),
            category=cats, metadata_gate=mgate,
            runtime_gate=OrderedDict((k, rgate.get(k)) for k in ('status', 'failed_acceptance_keys', 'record',
                                                                 'record_sha256', 'source', 'hash_checks') if k in rgate),
            frame_roles=frame_roles.get(iid, []),
            touches=OrderedDict((k, sorted(ctx.touches[iid][k])) for k in KINDS if k in ctx.touches[iid]),
            n_derivative_mentions=(None if any(iid in exposed_under[d] for d in DEFINITIONS)
                                   else len(derivative.get(iid, ()))),
            derivative_mentions=(None if any(iid in exposed_under[d] for d in DEFINITIONS)
                                 else sorted(derivative.get(iid, ()))),
            unknowns=[u['reason'] + ' [' + u['artifact'] + ']' for u in ctx.unknowns
                      if u['scope'] == 'id' and iid in u['ids']]))
    counts = OrderedDict((d, count_block(rows_out, d)) for d in DEFINITIONS)
    pins_ok = all(p['ok'] for p in ctx.pin_checks)

    rec = OrderedDict()
    rec['request'] = '%s (lead %s; source checkpoint %s)' % (REQUEST, LEAD_REQUEST_COMMIT, SOURCE_CHECKPOINT)
    rec['scope'] = SCOPE
    rec['provenance'] = provenance(ctx)
    rec['provenance']['source_checkpoint_diff_scan'] = since_checkpoint
    rec['pins'] = OrderedDict(list(pins.items()) + [
        ('source_sha256_observed', src_sha), ('id_set_sha256', id_list_sha256(ids)),
        ('id_list_serialization', ID_LIST_SERIALIZATION), ('pins_reconciled', pins_ok),
        ('pin_chain', ctx.pin_checks)])
    rec['definitions'] = definitions_record()
    rec['inputs'] = list(ctx.registry.values())
    rec['mention_scan'] = OrderedDict((k, scan[k]) for k in ('mode', 'history_scope', 'n_files_scanned',
                                                             'n_files_never_opened', 'self_excluded_paths',
                                                             'scanned_manifest_sha256',
                                                             'outcome_bearing_note', 'files_with_pinned_ids',
                                                             'n_historical_paths', 'historical_paths_available'))
    rec['derivative_record_whitelist'] = whitelist_used
    rec['narrative_mention_review'] = review
    rec['consistency_checks'] = ctx.checks
    rec['counts'] = counts
    rec['headline_caveats'] = headline_caveats(counts, uncommitted['record'], pins_ok)
    rec['runtime_gate_summary'] = runtime_summary(rows_out)
    rec['metadata_gate_summary'] = OrderedDict(
        gate=('M01/M02 static gate at evaluator %s: M02 test lists valid (source field `qualification` value '
              '"eligible", renamed m02_test_list_status="test_lists_valid"; a static test-list flag, not study '
              'eligibility), construction ok, repo/version in constants, not FAIL_ONLY, content unchanged; empty '
              'PASS_TO_PASS recorded as a limitation' % pins['evaluator_commit']),
        counts=dict(Counter(r['metadata_gate']['status'] for r in rows_out)),
        m02_test_list_status_counts=dict(Counter(r['metadata_gate']['m02_test_list_status'] for r in rows_out)),
        empty_pass_to_pass_limitation=[r['instance_id'] for r in rows_out if r['metadata_gate']['limitations']],
        m01_not_done=(m01s or {}).get('not_done'))
    rec['exposure_records'] = OrderedDict(cohorts=cohort_ran, smoke_episodes=smoke_episodes, third_party=third_party,
                                          cue_v1=cue)
    rec['required_before_eligibility'] = required_checks(rows_out, acceptance_keys, template_controls,
                                                         template_acceptance, m03_not_done, prov_verdict, rt)
    rec['unknowns'] = ctx.unknowns
    rec['uncommitted_local_evidence'] = uncommitted['record']
    rec['local_dataset_parquet'] = parquet
    rec['limitations'] = LIMITATIONS
    rec['no_claims'] = NO_CLAIMS
    rec['open_questions_for_lead'] = open_questions(counts)
    rec['rows'] = rows_out
    return rec


def provenance(ctx):
    pv = OrderedDict(script=SCRIPT_REL, script_sha256=sha256_bytes(Path(__file__).read_bytes()),
                     head_commit=(ctx.git('rev-parse', 'HEAD') or '').strip() or None, git_checkout=ctx.is_git)
    if ctx.is_git:
        head_blob = (ctx.git('rev-parse', 'HEAD:' + SCRIPT_REL) or '').strip() or None
        work_blob = (ctx.git('hash-object', '--', SCRIPT_REL) or '').strip() or None
        porcelain = ctx.git('status', '--porcelain=v1', '--untracked-files=all', '--', GIT_EXCLUDE) or ''
        lines = [x for x in porcelain.split('\n') if x]
        pv.update(script_tracked_at_head=head_blob is not None,
                  script_matches_head_blob=head_blob is not None and head_blob == work_blob,
                  worktree_clean=not lines, worktree_status_porcelain=lines,
                  worktree_status_sha256=sha256_bytes('\n'.join(lines).encode()),
                  source_checkpoint_is_ancestor_of_head=ctx.git_rc('merge-base', '--is-ancestor', SOURCE_CHECKPOINT,
                                                                    'HEAD') == 0)
    else:
        pv.update(script_tracked_at_head=None, script_matches_head_blob=None, worktree_clean=None,
                  worktree_status_porcelain=None, worktree_status_sha256=None,
                  source_checkpoint_is_ancestor_of_head=None)
    pv.update(source_checkpoint=SOURCE_CHECKPOINT, python=platform.python_version(),
              determinism=('deterministic given head_commit, worktree_status_porcelain, script_sha256, the input '
                           'sha256 values and the local uncommitted path state recorded under '
                           'uncommitted_local_evidence (work/ is git-ignored and host-specific; it can only raise '
                           'UNKNOWN). Regenerate committed outputs at a commit that contains this script.'))
    return pv


def source_checkpoint_diff_scan(ctx, pats, frame):
    """ID-token scan of the lines added between the lead's source checkpoint and HEAD (results/code_routing and this
    script's own files excluded). The inventory is taken at HEAD, so a pinned ID first named after the checkpoint is
    surfaced: the check fails and those IDs become UNKNOWN."""
    if not ctx.is_git:
        return OrderedDict(status='not_a_git_checkout')
    if ctx.git_rc('rev-parse', '--verify', '--quiet', SOURCE_CHECKPOINT + '^{commit}') != 0:
        ctx.check('no_pinned_id_added_since_source_checkpoint', False,
                  'source checkpoint %s is not in this repository' % SOURCE_CHECKPOINT)
        return OrderedDict(status='source_checkpoint_absent', source_checkpoint=SOURCE_CHECKPOINT)
    out = ctx.git('diff', '--name-only', '-z', SOURCE_CHECKPOINT, 'HEAD', '--', GIT_EXCLUDE)
    if out is None:
        ctx.unknown('global', 'category', SOURCE_CHECKPOINT, 'source checkpoint diff unavailable')
        return OrderedDict(status='UNKNOWN', reason='git diff against the source checkpoint failed')
    files = sorted(n for n in out.split('\0') if n and n not in SELF_PATHS)
    found = OrderedDict()
    for rel in files:
        diff = ctx.git('diff', SOURCE_CHECKPOINT, 'HEAD', '--', rel) or ''
        added = '\n'.join(x[1:] for x in diff.split('\n') if x.startswith('+') and not x.startswith('+++'))
        full, short = find_ids(added.encode(), pats, frame)
        if full | short:
            found[rel] = sorted(full | short)
    ids = sorted({i for v in found.values() for i in v})
    ctx.check('no_pinned_id_added_since_source_checkpoint', not ids,
              '%d changed files scanned since %s (self paths excluded); IDs: %s' % (len(files), SOURCE_CHECKPOINT, ids))
    if ids:
        ctx.unknown('id', 'category', 'git diff %s..HEAD' % SOURCE_CHECKPOINT,
                    'pinned ID first named after the source checkpoint', ids=ids)
    return OrderedDict(status='scanned', source_checkpoint=SOURCE_CHECKPOINT, n_changed_files_scanned=len(files),
                       changed_files_sha256=sha256_bytes('\n'.join(files).encode()), files_with_pinned_ids=found)


def unknown_runtime(record=None):
    return OrderedDict(status='UNKNOWN', failed_acceptance_keys=[], record=record, record_sha256=None, source=None,
                       hash_checks=OrderedDict())


def categorize(kinds, exposed_kinds):
    if kinds & exposed_kinds:
        return 'model_outcome_exposed'
    if kinds & QI_KINDS:
        return 'qualification_or_inspection_only'
    if 'third_party_recorded_episode' in kinds:
        return 'third_party_recorded_only'
    if 'frame_selection' in kinds:
        return 'frame_selected_not_run'
    return 'not_yet_assessed'


def id_has_category_unknown(unknowns, iid, definition):
    for u in unknowns:
        if u['affects'] != 'category' or definition not in u['definitions']:
            continue
        if u['scope'] == 'global' or iid in u['ids']:
            return True
    return False


def path_is_registered(rel, iid, episode_dirs, runtime):
    for d, owner in episode_dirs.items():
        if (rel == d or rel.startswith(d + '/')) and owner == iid:
            return True
    q = '%s/%s' % (P['qual_dir'], iid)
    if iid in runtime and runtime[iid].get('source') == 'qualification_20260922' and (rel == q or rel.startswith(q + '/')):
        return True
    return False


def list_files(ctx):
    """Tracked files (git; results/code_routing excluded by pathspec) or a filesystem walk (non-git fixtures; pruned)."""
    if ctx.is_git:
        out = ctx.git('ls-files', '-z', '--', GIT_EXCLUDE)
        if out is None:
            raise InventoryAbort('git ls-files failed')
        files = [f for f in out.split('\0') if f]
        mode = 'git ls-files (index at HEAD; working-tree bytes read)'
    else:
        files = []
        for dirpath, dirnames, filenames in os.walk(ctx.root):
            rel_dir = os.path.relpath(dirpath, ctx.root).replace(os.sep, '/')
            rel_dir = '' if rel_dir == '.' else rel_dir
            keep = []
            for dn in sorted(dirnames):
                sub = (rel_dir + '/' + dn) if rel_dir else dn
                if (not rel_dir and dn in WALK_EXCLUDE_TOP) or (sub + '/').startswith(NEVER_OPEN_PREFIXES) \
                        or dn == '__pycache__':
                    continue
                keep.append(dn)
            dirnames[:] = keep
            files += [(rel_dir + '/' + fn) if rel_dir else fn for fn in filenames]
        mode = 'filesystem walk (not a git checkout)'
    return sorted(files), mode


def mention_scan(ctx, pats, frame):
    files, mode = list_files(ctx)
    mentions, manifest_lines, never_opened, paths_with_ids, file_sha = OrderedDict(), [], 0, set(), {}
    for rel in files:
        if ids_in_path(rel, pats, frame):
            paths_with_ids.add(rel)
        if is_never_open(rel) or rel in SELF_PATHS:
            never_opened += rel not in SELF_PATHS
            continue
        if not (ctx.root / rel).is_file():
            continue
        data = ctx.read(rel)
        file_sha[rel] = sha256_bytes(data)
        manifest_lines.append('%s %s' % (file_sha[rel], rel))
        if rel.endswith('.gz'):
            try:
                data = gzip.decompress(data)
            except (OSError, EOFError):
                pass
        f_ids, s_ids = find_ids(data, pats, frame)
        if f_ids or s_ids:
            mentions[rel] = (f_ids, s_ids)
    hist = None
    if ctx.is_git:
        out = ctx.git('log', 'HEAD', '--no-renames', '--format=', '--name-only', '-z', '--', GIT_EXCLUDE)
        if out is not None:
            hist = sorted({f.strip('\n') for f in out.split('\0') if f.strip('\n')})
            for rel in hist:
                if ids_in_path(rel, pats, frame):
                    paths_with_ids.add(rel)
    files_with_ids = OrderedDict()
    for rel, (f_ids, s_ids) in mentions.items():
        files_with_ids[rel] = OrderedDict(n_full_ids=len(f_ids), n_short_form_only_ids=len(s_ids))
    return dict(mode=mode, history_scope='git log HEAD (ancestors of HEAD only; no other refs)' if ctx.is_git else None,
                mentions=mentions, file_sha256=file_sha, n_files_scanned=len(manifest_lines),
                n_files_never_opened=never_opened,
                self_excluded_paths=OrderedDict(
                    paths=sorted(SELF_PATHS), present_and_skipped=sorted(set(files) & SELF_PATHS),
                    rule=('this script, its test file and its two default output paths are not opened by the mention '
                          'scan and count as self-explained, so a regeneration at a later commit that contains them '
                          'cannot turn an ID UNKNOWN through them')),
                scanned_manifest_sha256=sha256_bytes('\n'.join(manifest_lines).encode()),
                outcome_bearing_note=('the mention scan read every scanned file, including model-outcome-bearing DEV '
                                      'cohort manifests, reports, grading passes, sanitization records, analyses and '
                                      'lead audits, as raw bytes and matched only pinned-ID patterns; per-file ID counts '
                                      'are emitted, plus per-ID mention paths and counts only for IDs exposed under '
                                      'neither definition. Separately, the two block_1.json manifests, the DEV2 binding '
                                      'and amendment spec and results/replay_gap_audit/audit.json are json-decoded in '
                                      'memory with an object_pairs_hook that retains only allow-listed keys; no outcome '
                                      'field is accessed or emitted'),
                files_with_pinned_ids=files_with_ids, paths_with_ids=sorted(paths_with_ids),
                n_historical_paths=None if hist is None else len(hist), historical_paths_available=hist is not None)


def uncommitted_scan(ctx, pats, frame, smoke_episodes):
    ids_paths, unattributed, present = defaultdict(list), [], []
    for top in UNCOMMITTED_DIRS:
        base = ctx.root / top
        if not base.is_dir():
            continue
        present.append(top)
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames.sort()
            rel_dir = os.path.relpath(dirpath, ctx.root).replace(os.sep, '/')
            for name in sorted(dirnames) + sorted(filenames):
                rel = rel_dir + '/' + name
                found = ids_in_path(rel, pats, frame)
                for iid in found:
                    ids_paths[iid].append(rel)
                if not found and UNATTRIBUTED_NAME_RE.match(name):
                    unattributed.append(rel)
    for name in sorted(os.listdir(ctx.root / 'work')) if (ctx.root / 'work').is_dir() else []:
        if UNATTRIBUTED_NAME_RE.match(name) and (ctx.root / 'work' / name).is_file():
            unattributed.append('work/' + name)
    unattributed = sorted(unattributed)
    mtimes = OrderedDict((p, utc_iso(os.stat(ctx.root / p).st_mtime)) for p in unattributed)
    stdout_logs = [p for p in unattributed if SMOKE_STDOUT_RE.match(p.rsplit('/', 1)[-1])]
    server_logs = [p for p in unattributed if p not in stdout_logs]
    smoke_commit = None
    if ctx.is_git and smoke_episodes:
        out = ctx.git('log', '--diff-filter=A', '--no-renames', '--format=%H %ct', 'HEAD', '--', GIT_EXCLUDE,
                      P['smoke_dir']) or ''
        lines = [x.split() for x in out.split('\n') if x.strip()]
        if lines:
            smoke_commit = OrderedDict(commit=lines[-1][0], committer_time_utc=utc_iso(int(lines[-1][1])),
                                       epoch=int(lines[-1][1]))
    before = None
    if smoke_commit is not None and stdout_logs:
        before = all(os.stat(ctx.root / p).st_mtime <= smoke_commit['epoch'] for p in stdout_logs)
    count_match = len(stdout_logs) == len(smoke_episodes)
    attributed = (not stdout_logs) or (count_match and before is not False)
    narrative_ok = None
    if server_logs and ctx.exists(P['request_text']):
        text = ctx.read(P['request_text']).replace('—'.encode(), b'-')
        narrative_ok = all(ph.encode() in text for ph in SERVER_LOG_ATTRIBUTION['cited_phrases'])
    record = OrderedDict(
        scope=('path names and file mtimes only under %s and work/*.log (git-ignored; no file opened); not part of any '
               'committed hash; can only raise UNKNOWN, never assign a category' % ', '.join(UNCOMMITTED_DIRS)),
        directories_present=present,
        ids_named=OrderedDict((iid, OrderedDict(n_paths=len(v), top_level=sorted({'/'.join(p.split('/')[:3]) for p in v})))
                              for iid, v in sorted(ids_paths.items())),
        path_list_sha256=sha256_bytes('\n'.join(sorted(p for v in ids_paths.values() for p in v)).encode()),
        mapped_committed_roots=[OrderedDict(root=r, explained_by_kind=k) for r, k in UNCOMMITTED_ROOTS],
        unattributed_run_logs_not_opened=unattributed,
        unattributed_run_log_mtimes_utc=mtimes,
        smoke_stdout_reconciliation=OrderedDict(
            method=('metadata only (no content): count of agent_smoke_*.stdout logs vs committed smoke episode '
                    'directories, and log mtimes vs the committer time of the commit that added those directories'),
            n_stdout_logs=len(stdout_logs), n_committed_smoke_episode_dirs=len(smoke_episodes),
            count_match=count_match, smoke_dirs_added_by=smoke_commit and OrderedDict(
                (k, v) for k, v in smoke_commit.items() if k != 'epoch'),
            all_stdout_mtimes_at_or_before_that_commit=before,
            consistent_with_committed_smoke_episodes=attributed,
            lead_audit=P['smoke_audit'] + ' (lead audit of the four agent smoke attempts)'),
        server_logs=OrderedDict(paths=server_logs, attribution=SERVER_LOG_ATTRIBUTION,
                                smoke_episode_ids=sorted({s['instance_id'] for s in smoke_episodes}),
                                cited_phrases_present_in_source=narrative_ok))
    return dict(ids={k: sorted(v) for k, v in ids_paths.items()}, record=record)


def count_block(rows, d):
    cats = [r['category'][d] for r in rows]
    known = Counter(c for c in cats if c != 'UNKNOWN')
    n_unknown = sum(c == 'UNKNOWN' for c in cats)
    blk = OrderedDict()
    for c in CATEGORIES:
        blk[c] = known.get(c, 0) if n_unknown == 0 else 'UNKNOWN'
    blk['unknown_ids'] = n_unknown
    blk['known_lower_bounds'] = OrderedDict((c, known.get(c, 0)) for c in CATEGORIES)
    blk['total_ids'] = len(rows)
    blk['sum_check'] = sum(known.values()) + n_unknown == len(rows)
    fam = OrderedDict()
    for r in sorted(rows, key=lambda x: x['family']):
        f = fam.setdefault(r['family'], OrderedDict([('total', 0)] + [(c, 0) for c in CATEGORIES] +
                                                     [('UNKNOWN', 0), ('not_yet_assessed_with_empty_p2p', 0)]))
        f['total'] += 1
        f[r['category'][d]] += 1
        if r['category'][d] == 'not_yet_assessed' and r['metadata_gate']['limitations']:
            f['not_yet_assessed_with_empty_p2p'] += 1
    exact = n_unknown == 0
    blk['families'] = fam
    blk['n_families'] = len(fam)

    def fam_count(pred):
        n = sum(1 for f in fam.values() if pred(f))
        return n if exact else 'UNKNOWN'
    blk['n_families_with_zero_exposed_ids'] = fam_count(lambda f: f['model_outcome_exposed'] == 0)
    blk['n_families_with_unexposed_ids'] = fam_count(lambda f: f['model_outcome_exposed'] < f['total'])
    blk['n_families_with_not_yet_assessed_ids'] = fam_count(lambda f: f['not_yet_assessed'] > 0)
    rv = Counter(r['repo_version_group'] for r in rows if r['category'][d] == 'not_yet_assessed')
    blk['n_repo_version_groups'] = len({r['repo_version_group'] for r in rows})
    blk['n_repo_version_groups_with_not_yet_assessed_ids'] = len(rv) if exact else 'UNKNOWN'
    blk['n_repo_version_groups_with_unexposed_ids'] = (
        len({r['repo_version_group'] for r in rows if r['category'][d] != 'model_outcome_exposed'}) if exact else 'UNKNOWN')
    unexposed = [r['instance_id'] for r in rows if r['category'][d] not in ('model_outcome_exposed', 'UNKNOWN')]
    blk['unexposed_ids'] = len(unexposed) if exact else 'UNKNOWN'
    blk['not_yet_assessed_with_empty_p2p_limitation'] = (
        sum(1 for r in rows if r['category'][d] == 'not_yet_assessed' and r['metadata_gate']['limitations'])
        if exact else 'UNKNOWN')
    by_cat = OrderedDict((c, [r['instance_id'] for r in rows if r['category'][d] == c]) for c in CATEGORIES + ('UNKNOWN',))
    blk['ids_by_category'] = by_cat
    kinds = {r['instance_id']: set(r['touches']) for r in rows}
    ev = [i for i in by_cat['qualification_or_inspection_only'] if kinds[i] & EVALUATOR_KINDS]
    si = [i for i in by_cat['qualification_or_inspection_only'] if not kinds[i] & EVALUATOR_KINDS]
    blk['qualification_or_inspection_only_split'] = OrderedDict(
        (k, OrderedDict(n=len(v) if exact else 'UNKNOWN', id_list_sha256=id_list_sha256(v), ids=v))
        for k, v in (('evaluator_touched', ev), ('source_inspection_only', si)))
    blk['id_list_sha256'] = OrderedDict([(c, id_list_sha256(v)) for c, v in by_cat.items()] +
                                        [('unexposed', id_list_sha256(unexposed)),
                                         ('all', id_list_sha256(r['instance_id'] for r in rows))])
    blk['id_list_note'] = ('lists are exact only when unknown_ids == 0; unexposed = every category except '
                           'model_outcome_exposed and UNKNOWN')
    return blk


def headline_caveats(counts, uncommitted, pins_ok):
    out = ['Counts are exact only with respect to this repository\'s committed records at the recorded HEAD (tracked '
           'files and paths in the history of HEAD); public or pretraining exposure is not measured.']
    if not pins_ok:
        out.append('Source pins did not reconcile: every category count is UNKNOWN (see pins.pin_chain).')
    if any(counts[d]['unknown_ids'] for d in counts):
        out.append('Some IDs are UNKNOWN; category counts are reported as UNKNOWN with known lower bounds.')
    sr = uncommitted['smoke_stdout_reconciliation']
    if uncommitted['unattributed_run_logs_not_opened']:
        if sr['consistent_with_committed_smoke_episodes']:
            out.append('Uncommitted ID-less logs were attributed by metadata only (%d agent smoke stdout logs match the '
                       '%d committed smoke episode directories in count and predate the commit that added them; server '
                       'logs are attributed by a committed narrative); their contents were not opened, and their task '
                       'identity was not established from content.'
                       % (sr['n_stdout_logs'], sr['n_committed_smoke_episode_dirs']))
        else:
            out.append('CAVEAT: %d uncommitted agent smoke stdout logs could not be reconciled by metadata with the %d '
                       'committed smoke episode directories; a smoke attempt on another ID cannot be excluded from '
                       'committed records.' % (sr['n_stdout_logs'], sr['n_committed_smoke_episode_dirs']))
    return out


def runtime_summary(rows):
    by = Counter(r['runtime_gate']['status'] for r in rows)
    return OrderedDict(
        gate='bae161f five-key acceptance (stock gold vs adapter reference vs adapter no_change; M03 strict rule)',
        counts=OrderedDict(sorted(by.items())),
        passed=[r['instance_id'] for r in rows if r['runtime_gate']['status'] == 'pass'],
        failed=OrderedDict((r['instance_id'], r['runtime_gate']['failed_acceptance_keys']) for r in rows
                           if r['runtime_gate']['status'] == 'fail'),
        unknown=[r['instance_id'] for r in rows if r['runtime_gate']['status'] == 'UNKNOWN'])


def pool_scope(rows):
    return OrderedDict(
        n_ids=len(rows), id_list_sha256=id_list_sha256(r['instance_id'] for r in rows),
        n_instance_images=len({r['instance_image_key'] for r in rows}),
        n_env_images=len({r['env_image_key'] for r in rows}),
        n_base_images=len({r['base_image_key'] for r in rows}),
        empty_pass_to_pass_ids=[r['instance_id'] for r in rows if r['metadata_gate']['limitations']])


def required_checks(rows, acceptance_keys, controls, acceptance_text, m03_not_done, prov_verdict, rt):
    untested = [r for r in rows if r['runtime_gate']['status'] == 'untested']
    scope = OrderedDict()
    for d in DEFINITIONS:
        scope[d] = OrderedDict(
            not_yet_assessed=pool_scope([r for r in rows if r['category'][d] == 'not_yet_assessed']),
            unexposed_runtime_untested=pool_scope([r for r in untested if r['category'][d] not in
                                                   ('model_outcome_exposed', 'UNKNOWN')]))
    scope['all_runtime_untested'] = pool_scope(untested)
    status = ('REQUIRED - NOT RUN for every ID whose runtime gate is untested (%d IDs); recorded pass/fail results '
              'apply only to their recorded platform, images and time; no ID is qualified or made eligible by this '
              'inventory' % len(untested))
    rb = P['runbook']
    items = [OrderedDict(
        key='image_build_and_digest_pin',
        requirement=('build the base, environment and instance images named by the M01 image keys locally on the '
                     'approved runtime (`--namespace none`; the default namespace pulls mutable `latest` tags) and '
                     'record every resolved digest in the acceptance record (M01 recorded keys only)'),
        scope_counts=OrderedDict((d, OrderedDict((pool, OrderedDict(
            (k, v) for k, v in s.items() if k in ('n_ids', 'n_instance_images', 'n_env_images', 'n_base_images')))
            for pool, s in scope[d].items())) for d in DEFINITIONS),
        sources=[P['m01_summary'] + '#not_done', rb + ' (Controls: --namespace none; Acceptance record: resolved '
                 'digests)', P['qual_code'] + ' (image_digests)', P['control_template'] + ' (*_image_digest '
                 '<RESOLVED_ON_HOST>)'], status=status)]
    items.append(OrderedDict(
        key='host_verification_record',
        requirement=('record before any control: host ID; host, VM-kernel and image/userland architecture (pinned '
                     'amd64, no ARM substitution) and translation mode, each separately; fixed resource limits and the '
                     'declared 1800 s timeout (not expanded after failures); runtime name/version; disk, CPU and '
                     'memory; the author approval reference'),
        recorded_runtime=OrderedDict(amd64_translation_check=(rt or {}).get('amd64_translation_check'),
                                     vm_profile=((rt or {}).get('vm') or {}).get('profile')),
        sources=[rb + ' (Host verification)', P['qual_code'] + ' (platform_rec, image_userland_arch)', P['runtime']],
        status=status))
    items.append(OrderedDict(
        key='isolated_workers_network_and_credentials',
        requirement=('disposable isolated workers with no project credentials mounted; network policy: image builds '
                     'only'),
        sources=[P['protocol'] + ' (Infrastructure gate)', rb + ' (Governing rules; Host verification)'],
        status=status))
    for k in acceptance_keys:
        items.append(OrderedDict(key=k, requirement='bae161f acceptance key `%s` must hold' % k,
                                 sources=[P['qual_code'] + ' (acc dict)', P['qual_status'], rb + ' (First execution)'],
                                 status=status))
    items.append(OrderedDict(
        key='control_rules',
        requirement=('stock gold = unmodified `run_evaluation --predictions_path gold`; adapter reference and no_change '
                     'controls as stated in the committed template and runbook (no_change: every required '
                     'PASS_TO_PASS observed PASSED unless the empty-P2P limitation applies, at least one FAIL_TO_PASS '
                     'observed FAILED, none ERROR/SKIPPED/XFAIL; reference: every required test observed PASSED); '
                     'completed interpretable execution with exactly one retry on timeout/missing report'),
        control_rules=controls, acceptance_text=acceptance_text,
        sources=[P['control_adapter_code'], P['control_template'] + '#controls', rb + ' (Qualification)',
                 P['protocol'] + ' (infrastructure gate)'],
        status=status))
    items.append(OrderedDict(
        key='acceptance_record_schema',
        requirement=('per instance x control: run/host/runtime identity, evaluator commit and dataset/lock hashes, '
                     'expected vs observed eval-script sha256, three image keys and resolved digests, patch hash, '
                     'exit/evaluation status, report and log hashes, per-test status map, upstream and strict flags, '
                     'qualification with diagnosis, permission reference; written no-clobber'),
        sources=[rb + ' (Acceptance record)', P['control_template'] + '#record_schema'], status=status))
    items.append(OrderedDict(
        key='empty_pass_to_pass_limitation_declaration',
        requirement='declare the explicit regression-coverage limitation for IDs with empty PASS_TO_PASS',
        ids=OrderedDict((d, OrderedDict((pool, s['empty_pass_to_pass_ids']) for pool, s in scope[d].items()))
                        for d in DEFINITIONS),
        sources=[P['protocol'] + ' (infrastructure gate)', P['m02_code']], status=status))
    items.append(OrderedDict(
        key='near_duplicate_family_variant_screen',
        requirement=('group near-duplicate/family variants before any pool freeze or split (protocol v2 section 4); a '
                     'predeclared, outcome-independent metadata screen of the pinned parquet, e.g. shared FAIL_TO_PASS '
                     'test files or modules or shared edited source files, against every model-outcome-exposed ID; '
                     'NOT assessed by this inventory (families here are repositories only)'),
        scope_counts=OrderedDict((d, OrderedDict(
            exposed_ids_to_screen_against=sum(1 for r in rows if r['category'][d] == 'model_outcome_exposed'),
            candidate_ids=scope[d]['not_yet_assessed']['n_ids'])) for d in DEFINITIONS),
        sources=[P['protocol'] + ' (section 4: group near-duplicate/family variants)'],
        status='REQUIRED - NOT RUN; the grouping rule is the lead\'s decision'))
    items.append(OrderedDict(
        key='outcome_independent_failure_decision',
        requirement=('diagnose every control failure and record a documented, outcome-independent qualification '
                     'decision; no substitution after failures; bind identity (manifest/source/dataset/evaluator) and '
                     'write records no-clobber'),
        sources=[P['protocol'] + ' (prospective grading clarification)', P['qual_manifest'] + '#selection_rule',
                 P['qual_code'] + ' (expected_identity, task_state)', rb + ' (Governing rules)'], status=status))
    open_items = [OrderedDict(item='M03 not_done (recorded, not a per-ID result)', detail=m03_not_done,
                              source=P['m03'])]
    if prov_verdict:
        open_items.append(OrderedDict(item='django-10097 provenance verdict (evaluator only; lead decision pending)',
                                      detail=prov_verdict, source=P['django_provenance']))
    return OrderedDict(status_rule=status, scope=scope, checks=items, open_evaluator_diagnostics=open_items)


def definitions_record():
    return OrderedDict(
        family=('repository (repo field); repo@version groups reported as a finer alternative; near-duplicate/family-'
                'variant grouping (protocol v2 section 4) not assessed'),
        touch_kinds=list(KINDS),
        categories_priority=list(CATEGORIES),
        exposure_definitions=OrderedDict((d, sorted(k)) for d, k in DEFINITIONS.items()),
        exposure_definition='lead decision pending (conservative and project_only reported side by side; neither '
                            'is a default)',
        qualification_or_inspection_kinds=sorted(QI_KINDS),
        qualification_or_inspection_split=('evaluator_touched = any of %s; source_inspection_only = source_inspection '
                                           'without those' % sorted(EVALUATOR_KINDS)),
        third_party_recorded_only_rule=('third_party_recorded_episode and no model or qualification/inspection touch '
                                        '(non-empty only under project_only; under conservative such IDs are exposed)'),
        explained_rule=('a file is explained for an ID when it equals or lies under an evidence root of that ID; this '
                        'script, its test and its default outputs are excluded from the scan as self-explained'),
        derivative_mentions_rule=('rows list derivative_mentions (unexplained non-record mentions) only for IDs not '
                                  'model_outcome_exposed under any definition; exposed IDs carry the count only'),
        record_like_rule=('tracked files under %s, any docs/**/*.json, or named like a run manifest (%s)'
                          % (', '.join(RECORD_LIKE_PREFIXES), RUN_MANIFEST_NAME_RE.pattern)),
        unknown_rule=('per definition, an ID not model_outcome_exposed is UNKNOWN when an unexplained record-like '
                      'mention (not on the sha256-pinned whitelist), an unexplained mention of a metadata-only ID, an '
                      'unregistered ID-named tracked/historical path, an unlisted cohort episode directory, a cohort '
                      'record naming it outside the manifest, an unmapped uncommitted run path, a missing exposure '
                      'source or a failed pin link applies; counts are then UNKNOWN with known lower bounds'),
        id_list_serialization=ID_LIST_SERIALIZATION,
        metadata_gate='M01/M02 static gate (see metadata_gate_summary); not study eligibility',
        runtime_gate='bae161f five-key acceptance; pass | fail(keys) | untested | UNKNOWN')


LIMITATIONS = [
    'Exposure is measured only from this repository\'s committed records (tracked files at HEAD, plus tracked path names '
    'in the history of HEAD). A model run that left no committed record cannot be detected.',
    'SWE-bench Verified issues, their fixes and many public agent trajectories are public. Pretraining or public-web '
    'exposure of the executor models is not measured; "untouched" means untouched in this project\'s records only.',
    'The committed third-party audit (results/replay_gap_audit/audit.json) carries per-file aggregate outcome tallies. '
    'A worker review of key cardinality only (no value read) found that these tallies make the per-trajectory '
    'third-party outcome recoverable for every one of the third-party task IDs in the pinned frame; this script drops '
    'those keys on decode and neither reads nor states any value. That the outcomes are recoverable from a committed '
    'file bears on the choice between the two exposure definitions. Whether the third-party record counts as exposure is the lead\'s decision (both '
    'definitions reported side by side).',
    'Near-duplicate and family-variant grouping (protocol v2 section 4) is not assessed; repository families do not '
    'satisfy that requirement, and variants of exposed issues may remain in the unexposed pools.',
    'Historical git blob contents are not re-scanned by this script; only historical path names (ancestors of HEAD) '
    'are checked, and the diff since the source checkpoint is ID-scanned (see provenance). results/code_routing/ '
    '(including its live/ and branch/ subdirectories) is excluded from every enumeration and was not scanned.',
    'The DEV cohort block_1.json manifests, the DEV2 cohort binding and amendment spec and the third-party audit.json '
    'are json-decoded in memory with an object_pairs_hook that retains only allow-listed keys (other values are '
    'decoded by the parser and dropped unread). Evaluator qualification records are json-decoded and only their '
    'verdict, acceptance, stage_failed and identity fields are accessed. Model-outcome-bearing reports, grading '
    'passes, sanitization records, analyses and lead audits are byte-scanned for ID tokens only. No model or '
    'third-party outcome field is accessed or emitted.',
    'Uncommitted local evidence (work/runs, work/logs, work/*.log) is checked by path names and mtimes only and can only '
    'raise UNKNOWN; ID-less run logs were not opened and are attributed by metadata and a committed narrative; their '
    'task identity was not established from content.',
    'The local dataset parquet is git-ignored and host-specific; when present, its bytes are hashed and its '
    'instance_id/repo/version columns are decoded by a stdlib reader (validated against pyarrow-derived constants in '
    'the tests); no other column is decoded.',
    'Nothing under results/code_routing/ (unrelated HumanEval/MBPP study) is opened; its paths are excluded from every '
    'git enumeration (status, ls-files, log) by the pathspec %s and pruned from the non-git walk.' % GIT_EXCLUDE,
    'Episode directories and model-server logs are never opened; exposure is established by cohort manifests and '
    'directory existence.',
    'Mention detection covers full IDs and repo-NNN short forms; other paraphrases (issue/PR URLs, prose) are not '
    'detected.',
    'The derivative whitelist accepts %d lead audit files by pinned sha256 after name/scope review; their contents '
    'were not re-audited beyond the byte scan.' % len(DERIVATIVE_RECORD_WHITELIST),
    'Families are repositories; issues within a family are not assumed independent or exchangeable.',
    'Runtime qualification results apply to the recorded platform, images and time only and do not transfer to other IDs.',
    'Container images possibly cached in the runtime VM were not listed (no container command is run).',
]
NO_CLAIMS = [
    'No eligibility claim: no metadata-valid issue is labelled qualified or eligible by this inventory; the M02 '
    '"eligible" test-list flag is reported only as m02_test_list_status="test_lists_valid".',
    'No precision, sample-size or power adequacy claim; the lead has not fixed the target margin or precision plan.',
    'No outcome (resolved/unresolved, patch, trajectory, success rate or model output) is reported.',
    'No new task selection. Counts are a deterministic function of the recorded HEAD commit and working-tree status, the '
    'script hash, the listed input hashes and the recorded local uncommitted path state (host-specific; it can only '
    'raise UNKNOWN).',
]


def open_questions(counts):
    cons, proj = counts['conservative'], counts['project_only']
    return [
        'Exposure definition (lead decision pending): should the third-party recorded trajectories (conservative) '
        'exclude an ID? Model-outcome-exposed: conservative %s vs project_only %s (project_only '
        'third_party_recorded_only: %s). The committed results/replay_gap_audit/audit.json carries per-file aggregate '
        'outcome tallies from which the per-trajectory third-party outcome of every third-party task ID in the frame is '
        'recoverable (key cardinality review only; no value read or stated here).' % (cons['model_outcome_exposed'], proj['model_outcome_exposed'],
                                          proj['third_party_recorded_only']),
        'Family unit: repository (%s families) or repo@version (%s groups)?' % (cons['n_families'],
                                                                              cons['n_repo_version_groups']),
        'Same-family exposure: should any model exposure in a family exclude the whole family? Families with zero '
        'exposed IDs: conservative %s, project_only %s.' % (cons['n_families_with_zero_exposed_ids'],
                                                           proj['n_families_with_zero_exposed_ids']),
        'Near-duplicate/family-variant grouping (protocol v2 section 4): which predeclared metadata screen (for example '
        'shared FAIL_TO_PASS test files/modules or shared edited source files against the exposed IDs) defines the '
        'groups, and are variants of exposed issues excluded?',
        'Are qualification-only and source-inspection-only IDs admissible to an untouched pool? (conservative %s, '
        'project_only %s; evaluator-touched / source-inspection-only: conservative %s / %s, project_only %s / %s). '
        'Classification choice: the source-inspection-only IDs here are M01 reset-check first-pass flags of generated '
        'eval-script text; if those static flags are treated as metadata-only, they join not_yet_assessed '
        '(%s under both definitions).'
        % (cons['qualification_or_inspection_only'], proj['qualification_or_inspection_only'],
           cons['qualification_or_inspection_only_split']['evaluator_touched']['n'],
           cons['qualification_or_inspection_only_split']['source_inspection_only']['n'],
           proj['qualification_or_inspection_only_split']['evaluator_touched']['n'],
           proj['qualification_or_inspection_only_split']['source_inspection_only']['n'],
           cons['not_yet_assessed'] + cons['qualification_or_inspection_only_split']['source_inspection_only']['n']
           if isinstance(cons['not_yet_assessed'], int) else 'UNKNOWN'),
        'Empty-PASS_TO_PASS IDs: include with a declared regression-coverage limitation or exclude? (not yet assessed: '
        'conservative %s, project_only %s)' % (cons['not_yet_assessed_with_empty_p2p_limitation'],
                                               proj['not_yet_assessed_with_empty_p2p_limitation']),
        'Family imbalance and the outcome-independent sampling rule (strata, caps, seed) must be fixed before any '
        'runtime qualification of a fresh sample.',
    ]


# ------------------------------------------------------------------ output
def render_md(rec):
    L = []
    w = L.append
    pv, cons, proj = rec['provenance'], rec['counts']['conservative'], rec['counts']['project_only']
    w('# DTR-REQ-008 fresh-pool inventory (metadata-only)\n')
    w('Generated by `%s` (sha256 `%s`; tracked at HEAD: %s; matches HEAD blob: %s) at HEAD `%s` (working tree clean: '
      '%s); source checkpoint `%s`. Machine-readable record: `%s`. Written once; do not edit.\n'
      % (pv['script'], pv['script_sha256'], pv['script_tracked_at_head'], pv['script_matches_head_blob'],
         pv['head_commit'], pv['worktree_clean'], pv['source_checkpoint'], OUT_JSON_DEFAULT))
    if pv.get('worktree_status_porcelain'):
        w('Working-tree status at generation: %s.\n' % ', '.join('`%s`' % x for x in pv['worktree_status_porcelain']))
    w('**Scope.** %s. Model-outcome exposure is established by the existence of a recorded episode, never by its '
      'outcome. %s\n' % (rec['scope'][0].upper() + rec['scope'][1:], pv['determinism']))
    p = rec['pins']
    w('**Pinned frame.** %s@`%s` `%s`; instances.jsonl sha256 `%s` (pin `%s`); dataset parquet sha256 `%s`; evaluator '
      '`%s`; %d rows; ID-set sha256 `%s` (%s). **Pins reconciled: %s.**\n'
      % (p['dataset'], p['dataset_revision'], p['dataset_file'], p['source_sha256_observed'], p['source_sha256'],
         p['dataset_sha256'], p['evaluator_commit'], p['n_rows'], p['id_set_sha256'], p['id_list_serialization'],
         p['pins_reconciled']))
    w('| pin link | ok | artifact |')
    w('|---|---|---|')
    for x in p['pin_chain']:
        w('| %s | %s | `%s` |' % (x['check'], x['ok'], x['artifact']))
    w('')
    lp = rec.get('local_dataset_parquet') or {}
    idr = lp.get('id_reconciliation') or {}
    w('**Local dataset parquet** (git-ignored): `%s` %s; ID reconciliation: **%s**%s.\n'
      % (lp.get('path'), ('sha256 `%s`' % lp.get('sha256')) if lp.get('present') else 'not present', idr.get('status'),
         (' (%s; %s rows, same IDs in the same order: %s, repo equal per row: %s, version equal per row: %s)'
          % (idr['method'], idr['num_rows'], idr['same_ids_same_order'], idr['repo_equal_per_row'],
             idr['version_equal_per_row'])) if 'method' in idr else (': ' + idr.get('reason', ''))))
    w('## Categories\n')
    w('Mutually exclusive, first match in priority order. **conservative** counts a third-party recorded trajectory as '
      'exposure; **project_only** counts only this project\'s model episodes and puts IDs whose only non-metadata '
      'touch is a third-party record in third_party_recorded_only. exposure_definition: **lead decision pending**; '
      'both are reported side by side and neither is a default.\n')
    w('| category | conservative | project_only |')
    w('|---|---:|---:|')
    for c in CATEGORIES:
        w('| %s | %s | %s |' % (c, cons[c], proj[c]))
        if c == 'qualification_or_inspection_only':
            for k in ('evaluator_touched', 'source_inspection_only'):
                w('| - of which %s | %s | %s |' % (k, cons[c + '_split'][k]['n'], proj[c + '_split'][k]['n']))
    w('| UNKNOWN (IDs) | %s | %s |' % (cons['unknown_ids'], proj['unknown_ids']))
    w('| total | %s | %s |' % (cons['total_ids'], proj['total_ids']))
    w('| unexposed IDs (not model-outcome exposed) | %s | %s |' % (cons['unexposed_ids'], proj['unexposed_ids']))
    w('| families (repositories) | %s | %s |' % (cons['n_families'], proj['n_families']))
    w('| families with >=1 unexposed ID | %s | %s |' % (cons['n_families_with_unexposed_ids'],
                                                         proj['n_families_with_unexposed_ids']))
    w('| families with zero exposed IDs | %s | %s |' % (cons['n_families_with_zero_exposed_ids'],
                                                         proj['n_families_with_zero_exposed_ids']))
    w('| families with >=1 not_yet_assessed ID | %s | %s |' % (cons['n_families_with_not_yet_assessed_ids'],
                                                                proj['n_families_with_not_yet_assessed_ids']))
    w('| repo@version groups with >=1 not_yet_assessed ID (of %s) | %s | %s |'
      % (cons['n_repo_version_groups'], cons['n_repo_version_groups_with_not_yet_assessed_ids'],
         proj['n_repo_version_groups_with_not_yet_assessed_ids']))
    w('| repo@version groups with >=1 unexposed ID (of %s) | %s | %s |'
      % (cons['n_repo_version_groups'], cons['n_repo_version_groups_with_unexposed_ids'],
         proj['n_repo_version_groups_with_unexposed_ids']))
    w('| not_yet_assessed with empty PASS_TO_PASS limitation | %s | %s |'
      % (cons['not_yet_assessed_with_empty_p2p_limitation'], proj['not_yet_assessed_with_empty_p2p_limitation']))
    w('')
    w('**Caveats on these counts.**\n')
    for x in rec['headline_caveats']:
        w('- ' + x)
    w('')
    if cons['unknown_ids'] or proj['unknown_ids']:
        w('Known lower bounds (conservative): %s; (project_only): %s.\n'
          % (json.dumps(cons['known_lower_bounds']), json.dumps(proj['known_lower_bounds'])))
    w('**ID-list identities** (%s):\n' % ID_LIST_SERIALIZATION)
    w('| list | conservative (n, sha256) | project_only (n, sha256) |')
    w('|---|---|---|')
    for key in CATEGORIES + ('unexposed', 'UNKNOWN', 'all'):
        def cell(blk):
            n = len(blk['ids_by_category'][key]) if key in blk['ids_by_category'] else (
                blk['total_ids'] if key == 'all' else blk['unexposed_ids'])
            return '%s, `%s`' % (n, blk['id_list_sha256'][key])
        w('| %s | %s | %s |' % (key, cell(cons), cell(proj)))
    for k in ('evaluator_touched', 'source_inspection_only'):
        w('| qualification_or_inspection_only / %s | %s | %s |' % (k, *('%s, `%s`' % (
            len(b['qualification_or_inspection_only_split'][k]['ids']),
            b['qualification_or_inspection_only_split'][k]['id_list_sha256']) for b in (cons, proj))))
    w('')
    w('The not_yet_assessed and other category lists are in `counts.<definition>.ids_by_category` of the JSON record.\n')
    w('## Per family (repository)\n')
    w('Columns: total; conservative exposed / qualification-or-inspection only / frame selected not run / not yet '
      'assessed / UNKNOWN; project_only exposed / third-party recorded only / not yet assessed; conservative '
      'not-yet-assessed IDs with empty PASS_TO_PASS.\n')
    w('| family | total | exp (cons) | qual/insp (cons) | frame not run | not yet assessed (cons) | UNKNOWN | '
      'exp (proj) | third-party only (proj) | not yet assessed (proj) | NYA empty-P2P (cons) |')
    w('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
    for fam, f in cons['families'].items():
        g = proj['families'][fam]
        w('| %s | %d | %d | %d | %d | %d | %d | %d | %d | %d | %d |'
          % (fam, f['total'], f['model_outcome_exposed'], f['qualification_or_inspection_only'],
             f['frame_selected_not_run'], f['not_yet_assessed'], f['UNKNOWN'], g['model_outcome_exposed'],
             g['third_party_recorded_only'], g['not_yet_assessed'], f['not_yet_assessed_with_empty_p2p']))
    w('')
    w('## Exposed and assessed IDs\n')
    proj_exp = proj['ids_by_category']['model_outcome_exposed']
    cons_exp = cons['ids_by_category']['model_outcome_exposed']
    w('**Project model-outcome exposure (%d IDs; existence of recorded episodes):** %s.\n'
      % (len(proj_exp), ', '.join('`%s`' % i for i in proj_exp) or 'none'))
    tp_only = [i for i in cons_exp if i not in set(proj_exp)]
    tp = rec['exposure_records']['third_party']
    if tp:
        w('**Exposed only through third-party recorded trajectories (conservative; %d IDs; `%s`, %s@%s; only task_ids '
          'and file identity kept, per-file outcome tallies dropped on decode and never read):** %s.\n'
          % (len(tp_only), P['replay_gap'], tp['dataset'], tp['revision'], ', '.join('`%s`' % i for i in tp_only)))
    rows = {r['instance_id']: r for r in rec['rows']}
    for d, blk in (('conservative', cons), ('project_only', proj)):
        ids = blk['ids_by_category']['qualification_or_inspection_only']
        w('**Qualification-or-inspection only (%s, %d):** %s.\n'
          % (d, len(ids), '; '.join('`%s` (%s; runtime gate %s%s)'
                                    % (i, ', '.join(k for k in rows[i]['touches'] if k != 'metadata_static'),
                                       rows[i]['runtime_gate']['status'],
                                       (': ' + ', '.join(rows[i]['runtime_gate']['failed_acceptance_keys']))
                                       if rows[i]['runtime_gate']['failed_acceptance_keys'] else '')
                                    for i in ids) or 'none'))
    fsn = cons['ids_by_category']['frame_selected_not_run']
    w('**Frame selected, not run (conservative):** %s.\n' % (', '.join('`%s`' % i for i in fsn) or 'none'))
    w('## Gates\n')
    mg, rg = rec['metadata_gate_summary'], rec['runtime_gate_summary']
    w('**Metadata gate** (%s): %s. Empty PASS_TO_PASS limitation (%d): %s.\n'
      % (mg['gate'], json.dumps(mg['counts']), len(mg['empty_pass_to_pass_limitation']),
         ', '.join('`%s`' % i for i in mg['empty_pass_to_pass_limitation'])))
    w('**Runtime strict gate** (%s): %s. Recorded pass: %s. Recorded fail (failed acceptance keys only): %s. All other '
      'IDs are **untested**.\n'
      % (rg['gate'], json.dumps(rg['counts']), ', '.join('`%s`' % i for i in rg['passed']) or 'none',
         '; '.join('`%s` (%s)' % (i, ', '.join(k)) for i, k in rg['failed'].items()) or 'none'))
    w('## Required before eligibility (not run)\n')
    req = rec['required_before_eligibility']
    w('Status: **%s**.\n' % req['status_rule'])
    w('| pool | IDs | instance images | env images | base images | empty PASS_TO_PASS IDs |')
    w('|---|---:|---:|---:|---:|---|')
    for d in DEFINITIONS:
        for pool, s in req['scope'][d].items():
            w('| %s / %s | %d | %d | %d | %d | %s |' % (d, pool, s['n_ids'], s['n_instance_images'], s['n_env_images'],
                                                        s['n_base_images'],
                                                        ', '.join('`%s`' % x for x in s['empty_pass_to_pass_ids'])
                                                        or 'none'))
    s = req['scope']['all_runtime_untested']
    w('| all runtime-untested IDs | %d | %d | %d | %d | %d IDs |' % (s['n_ids'], s['n_instance_images'],
                                                                  s['n_env_images'], s['n_base_images'],
                                                                  len(s['empty_pass_to_pass_ids'])))
    w('')
    for i, item in enumerate(req['checks'], 1):
        w('%d. `%s`: %s. Sources: %s. **%s**' % (i, item['key'], item['requirement'],
                                                 ', '.join('`%s`' % s for s in item['sources']),
                                                 'REQUIRED - NOT RUN' if item['status'] == req['status_rule']
                                                 else item['status']))
    w('')
    for o in req['open_evaluator_diagnostics']:
        w('- Open evaluator diagnostic, %s (`%s`): %s' % (o['item'], o['source'], json.dumps(o['detail'])))
    w('')
    w('## Consistency checks\n')
    w('| check | ok | detail |')
    w('|---|---|---|')
    for c in rec['consistency_checks']:
        w('| %s | %s | %s |' % (c['check'], c['ok'], c['detail'].replace('|', '/')[:160]))
    w('')
    w('## Unknowns\n')
    if not rec['unknowns']:
        w('None: every exposure source and pin link reconciled.\n')
    else:
        for u in rec['unknowns']:
            w('- [%s/%s/%s] %s: `%s`%s' % (u['scope'], u['affects'], ','.join(u['definitions']), u['reason'],
                                          u['artifact'], (' (IDs: %s)' % ', '.join(u['ids'])) if u['ids'] else ''))
        w('')
    w('## Derivative record whitelist (sha256-pinned)\n')
    for rel, x in rec['derivative_record_whitelist'].items():
        w('- `%s`: accepted %s (pinned `%s`, observed `%s`); %s' % (rel, x['accepted'], x['sha256_pinned'][:16],
                                                                   (x['sha256_observed'] or 'MISSING')[:16], x['reason']))
    w('')
    nr = rec['narrative_mention_review']
    w('Narrative mention review (manual, at `%s`): current manifest `%s` matches the reviewed one: **%s** (%d listed '
      'lines, %d counted only). %s\n' % (nr['reviewed_at_head'], nr['current_manifest_sha256'][:16],
                                         nr['current_matches_review'], len(nr['current_mentions']),
                                         nr['n_unlisted_conservative_exposed'], nr['finding']))
    w('## Uncommitted local evidence (listed separately; can only raise UNKNOWN)\n')
    uc = rec['uncommitted_local_evidence']
    sr = uc['smoke_stdout_reconciliation']
    w('%s. IDs named in path names: %s.\n'
      % (uc['scope'], ', '.join('`%s` (%d paths)' % (i, v['n_paths']) for i, v in uc['ids_named'].items()) or 'none'))
    w('Unattributed run logs (not opened; mtime UTC): %s.\n'
      % (', '.join('`%s` (%s)' % (x, uc['unattributed_run_log_mtimes_utc'][x])
                   for x in uc['unattributed_run_logs_not_opened']) or 'none'))
    w('Smoke stdout reconciliation (%s): %d logs vs %d committed smoke episode directories; added by %s; all mtimes at '
      'or before that commit: %s; consistent: **%s**.\n'
      % (sr['method'], sr['n_stdout_logs'], sr['n_committed_smoke_episode_dirs'],
         json.dumps(sr['smoke_dirs_added_by']), sr['all_stdout_mtimes_at_or_before_that_commit'],
         sr['consistent_with_committed_smoke_episodes']))
    sl = uc['server_logs']
    w('Server logs: %s. Attribution (%s; cited phrases present: %s): %s smoke_episode_ids: %s.\n'
      % (', '.join('`%s`' % x for x in sl['paths']) or 'none', sl['attribution']['source'],
         sl['cited_phrases_present_in_source'], sl['attribution']['attribution'],
         ', '.join('`%s`' % x for x in sl['smoke_episode_ids']) or 'none'))
    w('## Mention scan\n')
    ms = rec['mention_scan']
    w('%s; history: %s. %d files scanned (manifest sha256 `%s`), %d never opened, %d self-excluded (%s); %d files '
      'mention a pinned ID; %s historical path names checked. %s.\n'
      % (ms['mode'], ms['history_scope'], ms['n_files_scanned'], ms['scanned_manifest_sha256'],
         ms['n_files_never_opened'], len(ms['self_excluded_paths']['present_and_skipped']),
         ms['self_excluded_paths']['rule'], len(ms['files_with_pinned_ids']), ms['n_historical_paths'],
         ms['outcome_bearing_note'][0].upper() + ms['outcome_bearing_note'][1:]))
    w('## Limitations\n')
    for x in rec['limitations']:
        w('- ' + x)
    w('')
    w('## No eligibility or precision claim\n')
    for x in rec['no_claims']:
        w('- ' + x)
    w('')
    w('## Open questions for the lead\n')
    for i, q in enumerate(rec['open_questions_for_lead'], 1):
        w('%d. %s' % (i, q))
    w('')
    w('## Inputs\n')
    w('| path | role | read as | sha256 | first / last commit | at or before %s |' % SOURCE_CHECKPOINT)
    w('|---|---|---|---|---|---|')
    for e in rec['inputs']:
        w('| `%s` | %s | %s | `%s` | %s / %s | %s |'
          % (e['path'], e['role'], e['read_as'], (e['sha256'] or 'MISSING')[:16], (e['git_first_commit'] or '-')[:7],
             (e['git_last_commit'] or '-')[:7], e['last_change_at_or_before_source_checkpoint']))
    w('')
    return '\n'.join(L)


def write_outputs(rec, out_json: Path, out_md: Path):
    texts = ((out_json, json.dumps(rec, indent=1) + '\n'), (out_md, render_md(rec)))     # render both before any open
    for path, text in texts:
        with open(path, 'x') as fh:
            fh.write(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--out-json', type=Path, default=REPO / OUT_JSON_DEFAULT)
    ap.add_argument('--out-md', type=Path, default=REPO / OUT_MD_DEFAULT)
    a = ap.parse_args(argv)
    for p in (a.out_json, a.out_md):
        if p.exists():
            raise SystemExit('refusing to overwrite %s (write-once)' % p)
    rec = build(REPO)
    write_outputs(rec, a.out_json, a.out_md)
    print(json.dumps(OrderedDict((d, OrderedDict((k, v) for k, v in b.items()
                                                 if k not in ('families', 'ids_by_category')))
                                 for d, b in rec['counts'].items()), indent=1))
    print('unknowns:', len(rec['unknowns']), '| failed checks:', [c['check'] for c in rec['consistency_checks'] if not c['ok']])


if __name__ == '__main__':
    main()
