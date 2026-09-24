"""DTR-REQ-009 (lead 0fe40b8, docs/theory_feedback_20260924_req008_decision.md): metadata-only near-duplicate
component screen and 24-ID design queue over the pinned princeton-nlp/SWE-bench_Verified@c104f840 frame.

Rules (the lead's, applied as written):
  1. Conservative exposure (REQ-008 record, eb6027d): exclude the 64 model_outcome_exposed IDs; for the first queue
     also exclude the 5 qualification_or_inspection_only IDs and the not-yet-assessed IDs with empty PASS_TO_PASS.
  2. Within each repository, an edge joins two tasks that (a) share an identical declared FAIL_TO_PASS identifier, or
     (b) have the same base_commit and at least one identical path in the reference patch. A shared repository or
     version alone is not an edge. Connected components are formed over all 500 IDs; a whole component is excluded
     if it contains any of the 64 exposed or 5 qualification/inspection-only IDs.
  3. Remaining IDs are sorted within each repository by SHA-256 of UTF-8 'DTR-REQ-009|c104f840|<instance_id>' (ties
     by ID); nonempty repositories are visited in lexicographic round-robin order; the queue is the first 24.
     The complete ordered list is preserved. The queue is a design input only: no container, model or evaluator.

Reads: the committed REQ-008 record and M01 instances.jsonl, and the pinned dataset parquet (git-ignored; verified
against the REQ-008 pin). From the parquet only the instance_id, repo, base_commit, FAIL_TO_PASS and patch columns
are decoded. The patch column is decoded in memory and each line is tested only for the 'diff --git ' prefix; only
header paths are retained, and no other patch text is stored, printed, emitted or inspected. PASS_TO_PASS is not
decoded (empty-P2P status comes from the REQ-008 record). No test outcome or model output is read. Empty-P2P exclusion
is an individual design exclusion and does not spread to the component (only exposed or qualification/inspection-only
IDs taint a component). If a field or column needed for an edge is missing, the queue design stops, the missing field
is named and nothing is written.
Usage: req009_component_queue.py [--out-json P] [--out-md P]   (write-once outputs)
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REQ008_JSON = 'results/v2_adapter/req008_pool_inventory.json'
INSTANCES = 'results/v2_adapter/m01_c104f840_f7bbbb2/instances.jsonl'
PARQUET = 'work/benchmark_inputs/swebench_verified_c104f840/test-00000-of-00001.parquet'   # git-ignored, pinned
READER = 'experiments/v2_adapter/req008_pool_inventory.py'                                # stdlib parquet reader
OUT_JSON = 'results/v2_adapter/req009_component_queue.json'
OUT_MD = 'docs/req009_component_queue.md'
SALT = 'DTR-REQ-009|c104f840|'
CAP = 24
EXCLUDED_CATEGORIES = ('model_outcome_exposed', 'qualification_or_inspection_only')
HEADER = re.compile(r'^diff --git a/(\S+) b/(\S+)$')
HEX40 = re.compile(r'^[0-9a-f]{40}$')


class QueueStopped(Exception):
    """Pinned metadata cannot support an edge deterministically; the queue design stops."""


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def rank_key(iid: str) -> tuple:
    return (hashlib.sha256((SALT + iid).encode('utf-8')).hexdigest(), iid)


def patch_paths(patch: str) -> set:
    paths = set()
    for line in patch.split('\n'):
        if line.startswith('diff --git '):
            m = HEADER.match(line)
            if m is None:
                raise QueueStopped('unparseable diff header')
            paths.update(p for p in m.groups() if p != '/dev/null')
    return paths


def edge_fields(rows: list) -> dict:
    """rows: dicts with instance_id, repo, base_commit, FAIL_TO_PASS (JSON text), patch (text). Returns per-ID
    (repo, base_commit, frozenset of FAIL_TO_PASS identifiers, frozenset of patch paths); raises QueueStopped naming the
    missing or malformed field."""
    out = {}
    for r in rows:
        iid = r.get('instance_id')
        try:
            f2p = json.loads(r['FAIL_TO_PASS'])
        except (KeyError, TypeError, ValueError):
            raise QueueStopped('%s: FAIL_TO_PASS missing or not JSON' % iid)
        if not isinstance(f2p, list) or not f2p or not all(isinstance(x, str) and x for x in f2p):
            raise QueueStopped('%s: FAIL_TO_PASS is not a nonempty list of identifiers' % iid)
        bc = r.get('base_commit')
        if not isinstance(bc, str) or not HEX40.match(bc):
            raise QueueStopped('%s: base_commit missing or not 40 hex' % iid)
        if not isinstance(r.get('patch'), str):
            raise QueueStopped('%s: patch missing' % iid)
        try:
            paths = patch_paths(r['patch'])
        except QueueStopped as e:
            raise QueueStopped('%s: %s' % (iid, e))
        if not paths:
            raise QueueStopped('%s: reference patch has no diff header path' % iid)
        if not isinstance(r.get('repo'), str) or not r['repo']:
            raise QueueStopped('%s: repo missing' % iid)
        out[iid] = (r['repo'], bc, frozenset(f2p), frozenset(paths))
    return out


def build_edges(fields: dict) -> list:
    """Within-repository edges with witnesses, sorted deterministically."""
    by_repo = defaultdict(list)
    for iid in sorted(fields):
        by_repo[fields[iid][0]].append(iid)
    edges = []
    for repo in sorted(by_repo):
        ids = by_repo[repo]
        for i, a in enumerate(ids):
            for b in ids[i + 1:]:
                _, bca, fa, pa = fields[a]
                _, bcb, fb, pb = fields[b]
                shared_tests = sorted(fa & fb)
                shared_paths = sorted(pa & pb) if bca == bcb else []
                if shared_tests or shared_paths:
                    w = OrderedDict(a=a, b=b, repo=repo)
                    if shared_tests:
                        w['shared_fail_to_pass'] = shared_tests
                    if shared_paths:
                        w['same_base_commit'] = bca
                        w['shared_patch_paths'] = shared_paths
                    edges.append(w)
    return edges


def components(ids, edges) -> dict:
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for e in edges:
        ra, rb = find(e['a']), find(e['b'])
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)
    comp = defaultdict(list)
    for i in sorted(ids):
        comp[find(i)].append(i)
    return {min(m): m for m in comp.values()}


def round_robin(remaining_by_repo: dict, cap: int):
    """Complete lexicographic round-robin order over rank-sorted repositories, and its first `cap` IDs."""
    lanes = [sorted(remaining_by_repo[r], key=rank_key) for r in sorted(remaining_by_repo) if remaining_by_repo[r]]
    order, depth = [], 0
    while any(depth < len(lane) for lane in lanes):
        order += [lane[depth] for lane in lanes if depth < len(lane)]
        depth += 1
    return order, order[:cap]


def screen(frame_rows: list, category: dict, empty_p2p: set, parquet_rows: list, cap: int = CAP) -> OrderedDict:
    """Pure core: frame_rows = instances rows (instance_id, repo); category = conservative REQ-008 category per ID."""
    ids = [r['instance_id'] for r in frame_rows]
    repo_of = {r['instance_id']: r['repo'] for r in frame_rows}
    if sorted(r['instance_id'] for r in parquet_rows) != sorted(ids):
        raise QueueStopped('parquet IDs do not equal the pinned frame')
    for r in parquet_rows:
        if r.get('repo') != repo_of[r['instance_id']]:
            raise QueueStopped('%s: parquet repo differs from the frame' % r['instance_id'])
    fields = edge_fields(parquet_rows)
    edges = build_edges(fields)
    same_commit = []
    for repo in sorted(set(repo_of.values())):
        by_commit = defaultdict(list)
        for i in sorted(fields):
            if fields[i][0] == repo:
                by_commit[fields[i][1]].append(i)
        for bc, members in sorted(by_commit.items()):
            for x, a in enumerate(members):
                for b in members[x + 1:]:
                    same_commit.append(OrderedDict(a=a, b=b, repo=repo, base_commit=bc,
                                                   n_shared_header_paths=len(fields[a][3] & fields[b][3]),
                                                   edge=bool(fields[a][3] & fields[b][3])))
    field_audit = OrderedDict(
        rows=len(fields), empty_or_missing=0, unparsed_headers=0,
        tasks_with_more_than_one_header_path=sum(len(f[3]) > 1 for f in fields.values()),
        max_header_paths=max(len(f[3]) for f in fields.values()),
        within_repository_same_base_commit_pairs=len(same_commit))
    comps = components(ids, edges)
    excluded_src = {i for i in ids if category[i] in EXCLUDED_CATEGORIES}
    comp_of = {i: root for root, members in comps.items() for i in members}
    tainted = {root for root, members in comps.items() if excluded_src & set(members)}
    reason = OrderedDict()
    for i in sorted(ids):
        if category[i] in EXCLUDED_CATEGORIES:
            reason[i] = category[i]
        elif category[i] != 'not_yet_assessed':
            raise QueueStopped('%s: unexpected REQ-008 category %r' % (i, category[i]))
        elif i in empty_p2p:
            reason[i] = 'empty_pass_to_pass'
        elif comp_of[i] in tainted:
            reason[i] = 'component_touches_exposed_or_qualification_only'
        else:
            reason[i] = 'candidate'
    remaining = defaultdict(list)
    for i, why in reason.items():
        if why == 'candidate':
            remaining[repo_of[i]].append(i)
    order, queue = round_robin({r: remaining.get(r, []) for r in sorted(set(repo_of.values()))}, cap)
    repos = sorted(set(repo_of.values()))
    multi = [OrderedDict(component=root, repo=repo_of[root], size=len(m), members=m,
                         contains_excluded_source=sorted(excluded_src & set(m)), excluded=root in tainted)
             for root, m in sorted(comps.items()) if len(m) > 1]
    table = OrderedDict()
    for rp in repos:
        mine = [i for i in ids if repo_of[i] == rp]
        c = Counter(reason[i] for i in mine)
        table[rp] = OrderedDict(total=len(mine), model_outcome_exposed=c['model_outcome_exposed'],
                                qualification_or_inspection_only=c['qualification_or_inspection_only'],
                                empty_pass_to_pass=c['empty_pass_to_pass'],
                                component_excluded=c['component_touches_exposed_or_qualification_only'],
                                candidates=c['candidate'], queued=sum(repo_of[i] == rp for i in queue))
    return OrderedDict(
        counts=OrderedDict(frame=len(ids), by_reason=OrderedDict(sorted(Counter(reason.values()).items())),
                           edges=len(edges), edges_by_kind=OrderedDict(
                               fail_to_pass=sum('shared_fail_to_pass' in e for e in edges),
                               base_commit_and_path=sum('shared_patch_paths' in e for e in edges)),
                           components=len(comps), multi_member_components=len(multi),
                           components_containing_exposed_or_qi=len(tainted),
                           multi_member_components_excluded=sum(m['excluded'] for m in multi),
                           largest_component=max(len(m) for m in comps.values()),
                           candidates=len(order), queue=len(queue), queue_is_full=len(queue) == cap),
        by_repository=table,
        queue=queue, queue_by_repository=OrderedDict(sorted(Counter(repo_of[i] for i in queue).items())),
        complete_ordered_list=order,
        complete_ordered_list_sha256=sha256_bytes(''.join(i + '\n' for i in order).encode()),
        queue_sha256=sha256_bytes(''.join(i + '\n' for i in queue).encode()),
        rank_keys=OrderedDict((i, rank_key(i)[0]) for i in order),
        candidate_component=OrderedDict((i, OrderedDict(component=comp_of[i], size=len(comps[comp_of[i]]),
                                                        candidate_mates=sorted(m for m in comps[comp_of[i]]
                                                                               if m != i and reason[m] == 'candidate')))
                                        for i in order),
        same_base_commit_pairs=same_commit, field_audit=field_audit,
        multi_member_components=multi, edges=edges, exclusion_reason=reason)


def columns_to_rows(n, cols, names):
    """Rows from decoded parquet columns; a missing or short column stops the design and names the field."""
    for k in names:
        if k not in cols or len(cols[k]) != n:
            raise QueueStopped('parquet column %s missing or incomplete' % k)
    dec = lambda v: v.decode('utf-8') if isinstance(v, bytes) else v
    return [OrderedDict((k, dec(cols[k][j])) for k in names) for j in range(n)]


def git(*args):
    p = subprocess.run(['git', '-C', str(REPO)] + list(args), capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def load_inputs():
    reader_spec = importlib.util.spec_from_file_location('req008', REPO / READER)
    req008 = importlib.util.module_from_spec(reader_spec)
    reader_spec.loader.exec_module(req008)
    rec_bytes = (REPO / REQ008_JSON).read_bytes()
    rec = json.loads(rec_bytes)
    inst_bytes = (REPO / INSTANCES).read_bytes()
    frame_rows = [json.loads(l) for l in inst_bytes.decode().splitlines() if l.strip()]
    pq_bytes = (REPO / PARQUET).read_bytes()
    checks = OrderedDict(
        instances_sha256_equals_req008_pin=sha256_bytes(inst_bytes) == rec['pins']['source_sha256'],
        parquet_sha256_equals_req008_pin=sha256_bytes(pq_bytes) == rec['pins']['dataset_sha256'],
        frame_is_500_unique=len({r['instance_id'] for r in frame_rows}) == len(frame_rows) == 500,
        req008_rows_equal_frame=[r['instance_id'] for r in rec['rows']] == [r['instance_id'] for r in frame_rows],
        req008_id_set_sha256=sha256_bytes(''.join(i + '\n' for i in sorted(r['instance_id'] for r in frame_rows))
                                          .encode()) == rec['pins']['id_set_sha256'],
        req008_zero_unknown=rec['counts']['conservative']['unknown_ids'] == 0,
        req008_pins_reconciled=rec['pins']['pins_reconciled'] is True,
        dataset_revision_is_c104f840=str(rec['pins']['dataset_revision']).startswith('c104f840'),
        conservative_counts_64_5_431=[rec['counts']['conservative'][k] for k in (
            'model_outcome_exposed', 'qualification_or_inspection_only', 'not_yet_assessed')] == [64, 5, 431],
        not_yet_assessed_list_equals_lead_hash=rec['counts']['conservative']['id_list_sha256']['not_yet_assessed']
        == '7883a5f056bfeb12c0725f39006594b4e79f6a3557981df475354088b9e4d047')
    if not all(checks.values()):
        raise QueueStopped('input pins do not reconcile: %s' % [k for k, v in checks.items() if not v])
    names = ['instance_id', 'repo', 'base_commit', 'FAIL_TO_PASS', 'patch']
    n, cols = req008.read_parquet_columns(pq_bytes, names)
    parquet_rows = columns_to_rows(n, cols, names)
    checks['fail_to_pass_counts_equal_req008'] = all(
        len(json.loads(r['FAIL_TO_PASS'])) == g['metadata_gate']['n_fail_to_pass']
        for r, g in zip(sorted(parquet_rows, key=lambda x: x['instance_id']),
                        sorted(rec['rows'], key=lambda x: x['instance_id'])))
    if not checks['fail_to_pass_counts_equal_req008']:
        raise QueueStopped('FAIL_TO_PASS counts differ from the REQ-008 record')
    category = {r['instance_id']: r['category']['conservative'] for r in rec['rows']}
    empty_p2p = {r['instance_id'] for r in rec['rows'] if r['metadata_gate']['n_pass_to_pass'] == 0}
    inputs = OrderedDict(
        (p, OrderedDict(sha256=sha256_bytes((REPO / p).read_bytes()), git_last_commit=git('log', '-1', '--format=%H',
                                                                                         '--', p)))
        for p in (REQ008_JSON, INSTANCES, READER))
    inputs[PARQUET] = OrderedDict(sha256=sha256_bytes(pq_bytes), git_last_commit=None,
                                  dataset=rec['pins']['dataset'], dataset_revision=rec['pins']['dataset_revision'],
                                  note='git-ignored; pinned by the REQ-008 pin chain (dataset_sha256)',
                                  columns_decoded=names,
                                  patch_use=('decoded in memory; each line tested only for the "diff --git " prefix; '
                                             'only header paths retained; no other patch text stored, printed, '
                                             'emitted or inspected'))
    return frame_rows, category, empty_p2p, parquet_rows, inputs, checks


def render_md(rec: dict) -> str:
    c, L = rec['counts'], []
    w = L.append
    w('# DTR-REQ-009: near-duplicate component screen and 24-ID design queue (metadata only)\n')
    pv = rec['provenance']
    w('Lead decision: `docs/theory_feedback_20260924_req008_decision.md` (`0fe40b8`). Record: `%s`; script `%s` '
      '(sha256 `%s`), HEAD `%s`, script tracked and unchanged: %s, worktree clean: %s. Written once; do not edit.\n'
      % (OUT_JSON, pv['script'], pv['script_sha256'], pv['head_commit'], pv['script_tracked_and_unchanged'],
         pv['worktree_clean']))
    w('**Scope.** %s\n' % rec['scope'])
    w('**Result.** %d candidates remain after the lead\'s exclusions; the queue has **%d IDs** (full: %s). Edges: %d '
      '(%d shared FAIL_TO_PASS, %d same base commit + shared patch path); %d multi-member components, of which %d '
      'contain an exposed or qualification/inspection-only ID and are excluded; largest component %d.\n'
      % (c['candidates'], c['queue'], c['queue_is_full'], c['edges'], c['edges_by_kind']['fail_to_pass'],
         c['edges_by_kind']['base_commit_and_path'], c['multi_member_components'],
         c['multi_member_components_excluded'], c['largest_component']))
    w('Exclusion reasons over the 500-ID frame: %s. Empty-P2P exclusion is individual and does not spread to a '
      'component; only exposed or qualification/inspection-only IDs taint a component.\n'
      % ', '.join('%s %d' % kv for kv in c['by_reason'].items()))
    fa = rec['field_audit']
    w('Field audit: %d rows, 0 missing fields, 0 unparsed headers; %d tasks with more than one patch path (max %d). '
      'Within-repository same-base-commit pairs: %d (%s); none shares a patch path, so the base-commit edge kind is '
      'empty in this frame.\n' % (fa['rows'], fa['tasks_with_more_than_one_header_path'], fa['max_header_paths'],
                                  fa['within_repository_same_base_commit_pairs'],
                                  '; '.join('`%s`/`%s`, %d shared paths' % (p['a'], p['b'], p['n_shared_header_paths'])
                                            for p in rec['same_base_commit_pairs']) or 'none'))
    w('| Repository | total | exposed | qualification/inspection only | empty P2P | component-excluded | '
      'candidates | queued |')
    w('|---|---:|---:|---:|---:|---:|---:|---:|')
    for rp, t in rec['by_repository'].items():
        w('| %s | %d | %d | %d | %d | %d | %d | %d |' % (rp, t['total'], t['model_outcome_exposed'],
                                                         t['qualification_or_inspection_only'], t['empty_pass_to_pass'],
                                                         t['component_excluded'], t['candidates'], t['queued']))
    w('\n## Queue (design input only; not a frozen evaluation sample)\n')
    w('Order: SHA-256 of `%s<instance_id>` within repository, lexicographic round-robin over repositories. Queue '
      'sha256 `%s`; complete ordered list (%d IDs) sha256 `%s`.\n' % (SALT, rec['queue_sha256'], c['candidates'],
                                                                     rec['complete_ordered_list_sha256']))
    for k, i in enumerate(rec['queue'], 1):
        cc = rec['candidate_component'][i]
        w('%d. `%s`%s' % (k, i, '' if cc['size'] == 1 else ' (component of %d; candidate mates: %s)' % (
            cc['size'], ', '.join('`%s`' % m for m in cc['candidate_mates']) or 'none')))
    w('\nAny later split or freeze must keep whole components on one side.')
    w('\n## Multi-member components\n')
    w('| component | repository | size | contains exposed/QI | excluded |')
    w('|---|---|---:|---|---|')
    for m in rec['multi_member_components']:
        w('| `%s` | %s | %d | %s | %s |' % (m['component'], m['repo'], m['size'],
                                             ', '.join('`%s`' % x for x in m['contains_excluded_source']) or '-',
                                             m['excluded']))
    w('\nEdge witnesses (shared FAIL_TO_PASS identifiers or base commit + paths) are in the JSON record.\n')
    w('## Checks\n')
    for k, v in rec['checks'].items():
        w('- %s: %s' % (k, v))
    w('\n## Limits\n')
    for x in rec['limits']:
        w('- ' + x)
    return '\n'.join(L) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-json', default=OUT_JSON)
    ap.add_argument('--out-md', default=OUT_MD)
    a = ap.parse_args(argv)
    try:
        frame_rows, category, empty_p2p, parquet_rows, inputs, checks = load_inputs()
        core = screen(frame_rows, category, empty_p2p, parquet_rows)
    except QueueStopped as e:
        raise SystemExit('DTR-REQ-009 queue design stopped: %s (nothing written)' % e)
    script = Path(__file__).resolve()
    rel = str(script.relative_to(REPO))
    status = git('status', '--porcelain', '--untracked-files=all', '--', ':(exclude)results/code_routing')
    rec = OrderedDict(
        request='DTR-REQ-009 (lead 0fe40b8; source eb6027d)',
        scope=('Metadata-only design screen. No model, evaluator, container, GPU, Monte Carlo or download; no test '
               'outcome or model output read; PASS_TO_PASS not decoded; the patch column is decoded in memory and '
               'each line tested only for the "diff --git " prefix, retaining header paths only (no other patch text '
               'stored, printed, emitted or inspected). The queue is for '
               'later competence/qualification planning; it is not an evaluation sample, a power target or a '
               'release of any stage.'),
        provenance=OrderedDict(script=rel, script_sha256=sha256_bytes(script.read_bytes()),
                               head_commit=git('rev-parse', 'HEAD'),
                               script_tracked_and_unchanged=git('ls-files', rel) == rel
                               and git('diff', '--quiet', 'HEAD', '--', rel) is not None,
                               worktree_clean=status == ''),
        rules=__doc__.split('Rules (the lead\'s, applied as written):')[1].split('Reads:')[0].strip(),
        inputs=inputs, checks=checks)
    rec.update(core)
    rec['limits'] = [
        'Edges use only the two lead-specified relations on pinned metadata; other forms of near-duplication '
        '(similar issue text, overlapping but non-identical tests) are not screened.',
        'Exposure is from this repository\'s committed records (REQ-008); public or pretraining exposure is not measured.',
        'The parquet is git-ignored; reproduction needs the pinned file (sha256 in inputs).',
        'FAIL_TO_PASS identifiers are compared as declared strings; their qualification varies by repository (some '
        'repositories, e.g. sympy, declare bare function names), so the identical-identifier edge is only as specific '
        'as the declared names. The base-commit + path edge is nearly vacuous here (one same-commit pair, no shared '
        'path).',
        'No queued ID is runtime-qualified; qualification, competence and precision are for the lead\'s next plan.']
    text_json = json.dumps(rec, indent=1) + '\n'
    text_md = render_md(rec)
    outs = [Path(x) if Path(x).is_absolute() else REPO / x for x in (a.out_json, a.out_md)]
    default = [REPO / OUT_JSON, REPO / OUT_MD] == outs
    pv = rec['provenance']
    if default and not (pv['script_tracked_and_unchanged'] and pv['worktree_clean']):
        raise SystemExit('refusing the committed output paths: commit the script and use a clean tree first')
    if any(p.exists() for p in outs):
        raise SystemExit('write-once: an output already exists: %s' % [str(p) for p in outs if p.exists()])
    for p, text in zip(outs, (text_json, text_md)):
        with open(p, 'x') as fh:
            fh.write(text)
    print(json.dumps(OrderedDict(counts=rec['counts'], queue_by_repository=rec['queue_by_repository'],
                                 checks=rec['checks'], provenance=rec['provenance']), indent=1))


if __name__ == '__main__':
    main()
