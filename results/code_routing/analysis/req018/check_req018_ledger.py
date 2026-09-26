"""DTR-REQ-018 standalone checker (read-only; standard library + git, and numpy for the stage-2 sample reproduction).

Independently recomputes, from the frozen sources and git, every CSV cell of prefix_ledger.csv, task_ledger.csv and
continuation_ledger.csv and every numeric or boolean field of design_ledger.json (exact rational arithmetic for the
estimators), and fails closed:
  - a data source whose sha256 differs from the pinned frozen archive, or any source differing from its HEAD blob;
  - recomputed point values differing from the archived 0.12 / 0.13465370743933003 / -0.014653707439330033;
  - any mismatch, any missing, extra or ragged CSV column or row, and any numeric/boolean JSON field it does not
    recompute;
  - an identification status other than the declared one (a6-derived statuses are filled from a6_report);
  - any change to the remaining text (descriptions, readings, acceptance, labels), pinned by one sha256.
Without numpy the sample reproduction cannot be checked and the checker fails unless --allow-skip-repro is given (the
skipped fields are then listed). It asserts no standard error, interval or bootstrap.

    python3 results/code_routing/analysis/req018/check_req018_ledger.py [--ledger-dir DIR] [--allow-skip-repro]
"""
import argparse
import csv
import hashlib
import itertools
import json
import math
import re
import subprocess
import sys
from collections import Counter, defaultdict
from fractions import Fraction as Fr
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
CR = 'results/code_routing'
SOURCE_PATHS = {
    'design': CR + '/design.json', 'log_episodes': CR + '/log/episodes.jsonl',
    'branch_plan': CR + '/branch/branch_plan.json', 'branch_episodes': CR + '/branch/episodes.jsonl',
    'log_decisions': CR + '/log/decisions.jsonl',
    'branch_decisions': CR + '/branch/decisions.jsonl', 'branch_run_manifest': CR + '/branch/run_manifest.jsonl',
    'recovery_ledger': CR + '/recovery_ledger.json', 'restoration_recheck': CR + '/analysis/restoration_recheck.json',
    'branch_evidence_table': CR + '/analysis/branch_evidence_table.json',
    'a6_report': CR + '/analysis/a6_report.json',
    'lead_linkage_audit': 'docs/audits/theory_branch_linkage_audit_20260920.json',
    'target_note': 'docs/theory_branch_fixed_benchmark_bound.md',
    'weighting_decision': 'docs/theory_feedback_20260921_weighting.md',
    'design_code': 'experiments/code_routing/design.py', 'episode_code': 'experiments/code_routing/agent.py',
    'plan_code': 'experiments/code_routing/run.py', 'config': 'experiments/code_routing/config.json'}
COMMITS = {'design_freeze': 'cb9481d77567b7b14e3ceb6c1f0a6b534c67edcb',
           'log_invocation': 'c1de983f5152e70688db0b0c8ac198f085ce431e',
           'plan_invocation': 'f3aa436abf5101f0170b2030acce7bed70dcf344',
           'plan_commit': 'ac3ca8368e0b1b05990f1ef108fe1cc4bfb1251a'}
# the frozen archive this ledger is bound to (the design, log and branch hashes are also recorded by the frozen
# branch run manifest and restoration recheck); a changed data source fails the check instead of silently re-deriving
ARCHIVE_SHA256 = {
    'design': '230638a757c581138d1a3611a9c5788ed79b80a655313d316cac63cbba4ff43d',
    'log_episodes': 'e643ee44c7ef658fff65efb5e17763ee78c990d21184d060f5823025a100414e',
    'log_decisions': '7ef183d9c75794e9803f5849af7cbd9c860d1fee9eb344bcf8de7ac4a54d4cfd',
    'branch_plan': '59a384ac66c2b8d2e5e42c9828d7cc48757f802be9f4fa050eb22dac34367b35',
    'branch_episodes': '83bf00634fbeeb8af05cdfb546480fb3e72aa440a3b9d6b71f3d22dbc2c98413',
    'branch_decisions': '959a11c40a6bbaccd770895fc04f92ae72382e0f38d4f07e7d5de02a4ff71855',
    'branch_run_manifest': '6809db5554fda641ab8440d7e9f66f6925120b838c8360ac1249026cc206e705',
    'recovery_ledger': '75075ffffc462658e041c132f5800f187985d8dfbc2a818daa072dcc257e879b',
    'restoration_recheck': '0993ec4268cbccac77cba994fb4d9388dbe6a56a7023c7c14743776460a434da',
    'branch_evidence_table': '791dc1337148b8af45ecd85c31a82c53b081c1a448a0b817a7ae881ca9ce357c',
    'a6_report': 'ca75e7c9cdc149a9e3fb99f663a1557dee978f915f089d15e3922838409774e8',
    'lead_linkage_audit': '6bb899e649d4b98380f85f47eea23be32de4b01ba38e774e90c820dfea267aef',
    'target_note': '0f349e6162e3c52124e773d756b1e9231052b8c87eb2b6fe7481ed43f1a91c7b',
    'weighting_decision': '40b1a3a2331121f78bc2f55f3ecb1fef79af3ae0fb9a099b9ea869400f41d712',
    'design_code': '6510103b430ef3960f154fe142b640287d3dc891de61ddc1f975e9e560b28127',
    'episode_code': '9f064073827b297cf550cab1555946f89aac7205530b5e22a131a0a18caa165a',
    'plan_code': 'b88be431181b7cc7255df904c14b6551f991285035aa396108f8c2d271c04f75',
    'config': '3dfa7d53990e6d7832c2b22b6ae2f0bf60a9beac052c1ef7dfe10ec9a96d6177'}
OUT_REL = CR + '/analysis/req018'
# facts the pinned status/README text relies on: they must be true, not merely equal to a recomputation
MUST_TRUE = [
    'design.stage2_prefix_sample.reproduction.equal_to_frozen_plan', 'design.stage2_prefix_sample.plan_log_sha256_equals_log',
    'design.stage1_source_blocks.schedule.run_order_is_permutation', 'design.code_binding.plan_sampling_block_identical',
    'design.code_binding.design_block_identical', 'design.code_binding.frozen_record_bindings.config_file_equals_records',
    'design.code_binding.frozen_record_bindings.working_tree_code_sha256_equals_records',
    'design.stage3_continuations.restoration.recorded_flags_all_true',
    'design.stage3_continuations.restoration.recheck_source_binding_matches',
    'design.provenance.plan_order_sorted_by_parent', 'design.provenance.plan_order_task_contiguous',
    'design.provenance.retention_window.snapshot_equals_retained_lost_set',
    'design.provenance.retention_window.kill_wait_found_in_sandbox_code', 'lead_derivative.equals_a6_uncertainty_value'] + \
    ['design.stage2_prefix_sample.precommitment_checks.' + k for k in (
        'design_json_blob_at_freeze_equals_head', 'design_created_before_freeze_commit',
        'freeze_commit_before_first_log_episode', 'log_invocation_commit_descends_from_freeze',
        'plan_created_at_first_branch_invocation_start')] + \
    ['evidence_table_crosscheck.' + k for k in ('source_frame_counts_equal', 'prefixes_per_task_distribution_equal',
                                                'fresh_pair_discordance_equal', 'recovery_counts_equal')] + \
    ['sources.%s.working_tree_equals_head' % k for k in ARCHIVE_SHA256]
ARCHIVED_POINTS = {'B': 0.12, 'log_contrast': 0.13465370743933003, 'delta': -0.014653707439330033}
# statuses as declared (a6-derived ones are also compared with a6_report theorem_assumption_map)
STATUS = {
    'stage 1: first-decision arrangement and later-decision assignment': 'IDENTIFIED (design mechanism)',
    'stage 1: per-task law of the complete source block (outcomes, M_g, T_g, U_ga, D_ga)':
        'NOT IDENTIFIED (one realization per task, even under assumptions 1-3)',
    'stage 1: independence of complete source-task blocks across the 330 tasks': 'ASSUMED (a6: {independent})',
    'stage 2: SRSWOR prefix selection given F':
        'IDENTIFIED (mechanism, reproduced); selection independent of fresh continuation noise ASSUMED',
    'stage 3: replicate pairs (2 per arm, distinct seeds, fork_t = 1)':
        'OBSERVED (design); conditional independence across prefixes and replicate indices and a selection-invariant '
        'continuation law ASSUMED (a6: {selection}); within-pair arm dependence PERMITTED by the pair version',
    'stage 3: no execution shocks shared across prefixes': 'ASSUMED (a6: {shocks})',
    'restored prefix state': 'OBSERVED for the transcript hash; tool-result reproduction ASSUMED (stored flag)',
    'branch-log cross terms (shared records)':
        'OBSERVED (record map); the covariance itself is part of the per-task block law',
    'retention of lost-invocation records at the completion-time cutoff':
        'ASSUMED: retention independent of the potential outcomes (lost and recovered) of every continuation started '
        'before the snapshot capture',
    'recovery / invocation effect on the 665 re-executed continuations': 'NOT IDENTIFIED (a6: {recovered})',
    'seed-conditional determinism of the serving stack':
        'NOT INFORMATIVELY OBSERVED (matters only for the same-seed recovery re-execution)',
    'positive population denominators of eq. (2)': 'IMPLIED (observed N = {N}, D_1 = {D1}, D_0 = {D0} with '
                                                    'nonnegative summands)'}
# sha256 of the canonical list of every string leaf that no recomputed path covers (descriptions, readings, statuses,
# acceptance, labels): a text change is a deliberate new ledger version, so the checker must be updated with it
TEXT_SHA256 = '653ff5e970e7edf7b9edca553c1bab24d34acb2300809845d2d40cff9b8b7937'
COMPONENTS = list(STATUS)
NOT_DONE = ['no standard error, interval or bootstrap', 'no 42-task substitution', 'no model/browser inference',
            'no Monte Carlo', 'no archive change']
TOL = 1e-14                                                   # float rounding of the builder; truncation is caught
NUMBER = re.compile(r'-?[0-9]+\.[0-9]+(e-?[0-9]+)?')          # the builder's repr(float): ASCII, always with a point
VERSION = re.compile(r'[0-9]+\.[0-9]+\.[0-9]+')                 # reproduction.numpy: the builder's own numpy


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def jl(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def git(root, *args, binary=False):
    r = subprocess.run(['git', '--no-replace-objects', '-C', str(root)] + list(args), capture_output=True,
                       text=not binary)
    return r.stdout if binary else r.stdout.strip()


def leaves(obj, prefix=()):
    if isinstance(obj, dict):
        if not obj:
            yield prefix, {}
        for k, v in obj.items():
            yield from leaves(v, prefix + (k,))
    elif isinstance(obj, (list, tuple)):
        if not obj:
            yield prefix, []
        for i, v in enumerate(obj):
            yield from leaves(v, prefix + (i,))
    else:
        yield prefix, obj


def same(a, b):
    """a expected, b ledger: exact and type-sensitive for str/bool/None/int, tolerance for non-integral numbers."""
    if isinstance(a, bool) or isinstance(b, bool) or a is None or b is None or isinstance(a, str) or isinstance(b, str):
        return type(a) is type(b) and a == b
    if isinstance(a, int) and not isinstance(a, bool):
        return type(b) is int and a == b
    if type(b) is not float:
        return False
    if isinstance(a, (list, dict)) or isinstance(b, (list, dict)):
        return type(a) is type(b) and a == b
    if isinstance(a, int) and isinstance(b, int):
        return a == b
    return math.isfinite(float(b)) and abs(float(a) - float(b)) <= TOL


def block(text, start_marker, end_marker):
    s = text.rfind('\n', 0, text.index(start_marker)) + 1
    return text[s:text.index('\n', text.index(end_marker, s))]


def code_sha_at(root, commit):
    files = []
    for d in ('experiments/code_routing', 'experiments/common'):
        files += sorted(p for p in git(root, 'ls-tree', '--name-only', commit, d + '/').split()
                        if p.endswith('.py') and '/' not in p[len(d) + 1:])
    return hashlib.sha256(b''.join(git(root, 'show', commit + ':' + f, binary=True) for f in files)).hexdigest()


class Unverifiable(Exception):
    pass


def expected_values(root, allow_skip):
    """-> (json expectations {path tuple: value}, csv expectations {name: (columns, rows)}, skipped paths)."""
    S = {k: root / p for k, p in SOURCE_PATHS.items()}
    design = json.loads(S['design'].read_text())
    log = jl(S['log_episodes'])
    plan = json.loads(S['branch_plan'].read_text())
    br = jl(S['branch_episodes'])
    bdec = jl(S['branch_decisions'])
    man = jl(S['branch_run_manifest'])
    rec = json.loads(S['recovery_ledger'].read_text())
    recheck = json.loads(S['restoration_recheck'].read_text())
    a6 = json.loads(S['a6_report'].read_text())
    audit = json.loads(S['lead_linkage_audit'].read_text())
    cfg = json.loads(S['config'].read_text())
    ev = json.loads(S['branch_evidence_table'].read_text())
    E, skipped = {}, []

    def put(path, value):
        E[tuple(path.split('.')) if isinstance(path, str) else path] = value

    put('request', 'DTR-REQ-018')
    for k, p in SOURCE_PATHS.items():
        head = git(root, 'rev-parse', 'HEAD:' + p) or None
        put('sources.' + k, {'path': p, 'sha256': ARCHIVE_SHA256.get(k, sha(S[k])), 'bytes': S[k].stat().st_size,
                             'git_blob_head': head, 'working_tree_equals_head': True})
        if k in ARCHIVE_SHA256 and sha(S[k]) != ARCHIVE_SHA256[k]:
            raise Unverifiable('source %s differs from the frozen archive (sha256 %s)' % (k, sha(S[k])))
        if head != git(root, 'hash-object', str(S[k])):
            raise Unverifiable('source %s: working tree differs from HEAD' % k)

    # ---- frame
    tasks = design['confirm_tasks']
    dlog = {e['episode_id']: e for e in design['log_episodes']}
    final = {}
    for r in log:
        if r.get('error') is None or r.get('error') == '':
            final[r['episode_id']] = r
    conf = [r for r in log if r['split'] == 'confirm']
    frame = sorted((r for r in final.values() if r['split'] == 'confirm' and len(r['decisions']) >= 2),
                   key=lambda r: r['episode_id'])
    N = len(frame)
    plan_by = {e['episode_id']: e for e in plan['episodes']}
    samp = sorted({e['parent_episode_id'] for e in plan['episodes']})
    sset = set(samp)
    n = len(samp)
    brb = {r['episode_id']: r for r in br}

    def dec(r, t):
        return next((d for d in r['decisions'] if d['t'] == t), None)

    def W(r, a):                                     # eq. (1) W_ia
        d1, d2 = dec(r, 1), dec(r, 2)
        return Fr(int(d1['a'] == a), 1) / Fr(1, 2) * (1 if d2 is None else Fr(int(d2['a'] == a), 1) / Fr(1, 2))

    # ---- branch side, replicates in plan run index order
    reps = defaultdict(lambda: {'small': {}, 'large': {}})
    for e in plan['episodes']:
        reps[e['parent_episode_id']][('small', 'large')[e['forced_arm']]][e['run']] = brb[e['episode_id']]['success']
    Dp = {p: Fr(sum(v['large'].values()), len(v['large'])) - Fr(sum(v['small'].values()), len(v['small']))
          for p, v in reps.items()}
    B = sum(Dp.values(), Fr(0)) / len(Dp)
    tk = {e['parent_episode_id']: e['task_uid'] for e in plan['episodes']}
    Ag, mg = defaultdict(Fr), Counter()
    for p, d in Dp.items():
        Ag[tk[p]] += d
        mg[tk[p]] += 1
    Ug = {(t, a): Fr(0) for t in tasks for a in (0, 1)}
    Dg = {(t, a): Fr(0) for t in tasks for a in (0, 1)}
    for r in frame:
        for a in (0, 1):
            Ug[(r['task_uid'], a)] += W(r, a) * r['success']
            Dg[(r['task_uid'], a)] += W(r, a)
    U = [sum((Ug[(t, a)] for t in tasks), Fr(0)) for a in (0, 1)]
    D = [sum((Dg[(t, a)] for t in tasks), Fr(0)) for a in (0, 1)]
    v = [U[a] / D[a] for a in (0, 1)]
    lead = {t: (Ag[t] - B * mg[t]) / len(Dp) - (Ug[(t, 1)] - v[1] * Dg[(t, 1)]) / D[1]
            + (Ug[(t, 0)] - v[0] * Dg[(t, 0)]) / D[0] for t in tasks}
    put('point_estimates', {'B': B, 'v1': v[1], 'v0': v[0], 'log_contrast': v[1] - v[0], 'delta': B - v[1] + v[0],
                            'U_1': U[1], 'D_1': D[1], 'U_0': U[0], 'D_0': D[0], 'sum_lead_derivative': sum(lead.values()),
                            'lead_audit': {'B': audit['full_prefix_branch_mean'],
                                           'log_contrast': audit['global_hajek_log_mean'],
                                           'delta': audit['full_original_difference']}})

    # ---- reconciliation
    elig_t = Counter(r['task_uid'] for r in frame)
    samp_t = Counter(tk[p] for p in samp)
    pos1 = {t for t in tasks if Dg[(t, 1)] > 0}
    pos0 = {t for t in tasks if Dg[(t, 0)] > 0}
    et, st = set(elig_t), set(samp_t)
    put('reconciliation', {
        'confirm_tasks': len(tasks), 'confirm_log_episodes': len(conf),
        'episodes_per_task': [[k, c] for k, c in sorted(Counter(Counter(r['task_uid'] for r in conf).values()).items())],
        'eligible_prefixes': N, 'eligible_tasks': len(et), 'sampled_prefixes': n, 'sampled_tasks': len(st),
        'branch_continuations': len(br),
        'continuations_per_prefix': [[k, c] for k, c in sorted(Counter(
            len(v['small']) + len(v['large']) for v in reps.values()).items())],
        'tasks_without_eligible_prefix': len(tasks) - len(et),
        'tasks_with_eligible_but_no_sampled_prefix': len(et - st),
        'sampled_prefixes_per_task': [[k, c] for k, c in sorted(Counter(samp_t.values()).items())],
        'eligible_prefixes_per_task': [[k, c] for k, c in sorted(Counter(elig_t.values()).items())],
        'zero_arm_counts': {
            'eligible_tasks_D_g1_zero': len(et - pos1), 'eligible_tasks_D_g0_zero': len(et - pos0),
            'eligible_tasks_both_zero': len(et - pos1 - pos0), 'eligible_tasks_both_positive': len(et & pos1 & pos0),
            'sampled_tasks_both_positive': len(st & pos1 & pos0), 'sampled_tasks_at_least_one_zero': len(st - (pos1 & pos0)),
            'tasks_lead_derivative_exactly_zero': sum(1 for t in tasks if float(lead[t]) == 0.0)}})

    # ---- stage 1
    arrangements = set(itertools.permutations([0] * 4 + [1] * 4))
    pairs = [(x[0], x[1]) for x in arrangements]
    s1 = 'design.stage1_source_blocks.'
    put(s1 + 'a0_same_probability', Fr(sum(a == b for a, b in pairs), len(pairs)))
    put(s1 + 'a0_both_large_probability', Fr(sum(a == b == 1 for a, b in pairs), len(pairs)))
    pats = Counter()
    for t in tasks:
        pats[tuple(sorted(dlog[r['episode_id']]['a0_block'] for r in conf if r['task_uid'] == t))] += 1
    put(s1 + 'a0_block_patterns', [[list(k), c] for k, c in pats.items()])
    put(s1 + 'a0_realized_equals_block', sum(dec(r, 0)['a'] == dlog[r['episode_id']]['a0_block'] for r in conf))
    put(s1 + 'u0_by_block', [[list(k), c] for k, c in sorted(Counter(
        (dlog[r['episode_id']]['a0_block'], dlog[r['episode_id']]['u'][0]) for r in conf).items())])
    nd = sum(len(r['decisions']) for r in conf)
    bad = sum(1 for r in conf for d in r['decisions']
              if d['draw'] != dlog[r['episode_id']]['u'][d['t']] or d['a'] != (1 if d['draw'] < d['p_large'] else 0))
    put(s1 + 'decisions_checked_all_t', nd)
    put(s1 + 'decisions_checked_t_ge_1', sum(1 for r in conf for d in r['decisions'] if d['t'] > 0))
    put(s1 + 'decisions_mismatching_design_uniform', bad)
    put(s1 + 'p_large_values', [[k, c] for k, c in Counter(d['p_large'] for r in conf for d in r['decisions']).items()])
    put(s1 + 'decision_sources', [[list(k), c] for k, c in sorted(Counter(
        (d['t'], d['source']) for r in conf for d in r['decisions']).items())])
    for k in ('design_seed', 'horizon', 'p_large'):
        put(s1 + k, design[k])
    put(s1 + 'design_created_utc', design['created_utc'])
    put(s1 + 'design_code_sha256', design['design_code_sha256'])
    el = s1 + 'eligibility.'
    put(el + 'eligible_vs_first_visible_pass', [[list(k), c] for k, c in sorted(Counter(
        (len(r['decisions']) >= 2, dec(r, 0)['validation']['passed']) for r in conf).items())])
    put(el + 'eligible_with_hidden_correct_first_candidate', sum(r['success_first_candidate'] for r in frame))
    put(el + 'n_decisions_by_stop_reason', [[list(k), c] for k, c in sorted(Counter(
        (r['n_decisions'], r['stop_reason']) for r in conf).items())])
    a0 = {r['episode_id']: dlog[r['episode_id']]['a0_block'] for r in frame}
    put(el + 'frame_by_a0', {'small': sum(1 for x in a0.values() if x == 0), 'large': sum(1 for x in a0.values() if x == 1)})
    put(el + 'sample_by_a0', {'small': sum(1 for p in samp if a0[p] == 0), 'large': sum(1 for p in samp if a0[p] == 1)})
    Mga = Counter((r['task_uid'], a0[r['episode_id']]) for r in frame)
    put(el + 'max_M_g_by_a0', max(Mga.values()))
    sc = s1 + 'schedule.'
    put(sc + 'log_invocations', [[list(k), c] for k, c in sorted(Counter(
        (r['invocation'], r['split'], r['git_head'], r['code_sha256']) for r in log).items())])
    put(sc + 'start_utc', {s: [min(r['start_utc'] for r in log if r['split'] == s),
                               max(r['start_utc'] for r in log if r['split'] == s)]
                           for s in sorted({r['split'] for r in log})})
    orders = [dlog[r['episode_id']]['run_order'] for r in log]
    put(sc + 'run_order_is_permutation', sorted(orders) == list(range(len(log))))
    for s in ('confirm', 'train'):
        put(sc + s + '_by_run_order_decile',
            [sum(1 for r in log if r['split'] == s and dlog[r['episode_id']]['run_order'] * 10 // len(log) == k)
             for k in range(10)])
    put(sc + 'errors', sum(1 for r in log if r.get('error')))
    put(sc + 'attempts', [[k, c] for k, c in sorted(Counter(r['attempt'] for r in log).items())])

    # ---- stage 2
    s2 = 'design.stage2_prefix_sample.'
    put(s2 + 'N', N)
    put(s2 + 'n', n)
    put(s2 + 'n_rule_min_200_N', min(200, N))
    put(s2 + 'pi', Fr(n, N))
    put(s2 + 'pi_pair', Fr(n * (n - 1), N * (N - 1)))
    put(s2 + 'seed', design['branch_audit']['seed'])
    from datetime import datetime, timezone

    def ep(x):
        return datetime.fromisoformat(x.replace('Z', '+00:00')).astimezone(timezone.utc)
    fz = COMMITS['design_freeze']
    t_freeze = ep(git(root, 'show', '-s', '--format=%cI', fz))
    put(s2 + 'precommitment_checks', {
        'design_json_blob_at_freeze_equals_head': git(root, 'rev-parse', fz + ':' + SOURCE_PATHS['design']) ==
        git(root, 'rev-parse', 'HEAD:' + SOURCE_PATHS['design']),
        'design_created_before_freeze_commit': ep(design['created_utc']) <= t_freeze,
        'freeze_commit_before_first_log_episode': t_freeze <= min(ep(r['start_utc']) for r in log),
        'log_invocation_commit_descends_from_freeze': subprocess.run(
            ['git', '--no-replace-objects', '-C', str(root), 'merge-base', '--is-ancestor', fz,
             COMMITS['log_invocation']]).returncode == 0,
        'plan_created_at_first_branch_invocation_start': plan['created_utc'] == man[0]['started_utc'] and
        man[0]['n_ok_before'] == 0})
    put(s2 + 'plan_sampling_probability', plan['sampling_probability'])
    put(s2 + 'plan_n_eligible', plan['n_eligible_prefixes'])
    put(s2 + 'plan_log_sha256_equals_log', plan['log_sha256'] == sha(S['log_episodes']))
    put(s2 + 'plan_created_utc', plan['created_utc'])
    m0 = man[0]
    put(s2 + 'plan_invocation', {k: m0[k] for k in ('invocation', 'started_utc', 'git_head', 'code_sha256', 'n_todo')})
    bpr = a6['branch_plan_reproduction']
    put(s2 + 'a6_branch_plan_reproduction', {k: bpr[k] for k in (
        'redrawn_equals_frozen_plan', 'plan_log_sha256_matches_current_log', 'plan_created_not_after_first_start',
        'design_freeze_commit')})
    rp = s2 + 'reproduction.'
    put(rp + 'n_episodes', len(plan['episodes']))
    put(rp + 'fields_compared', ['episode_id', 'parent_episode_id', 'task_uid', 'run', 'forced_arm', 'seed', 'run_order'])
    try:
        import numpy as np
    except ImportError:
        np = None
    if np is None:
        if not allow_skip:
            raise Unverifiable('numpy absent: the stage-2 sample reproduction cannot be checked '
                               '(pass --allow-skip-repro)')
        skipped += [tuple((rp + 'equal_to_frozen_plan').split('.'))]
    else:
        g = np.random.default_rng(design['branch_audit']['seed'])
        idx = sorted(int(i) for i in g.choice(N, size=min(design['branch_audit']['n_prefixes'], N), replace=False))
        redraw = []
        for i in idx:
            for arm in (0, 1):
                for c in range(design['branch_audit']['continuations_per_arm']):
                    redraw.append((frame[i]['episode_id'], frame[i]['task_uid'], arm, c, int(g.integers(1, 2 ** 31 - 1))))
        planned = [(e['parent_episode_id'], e['task_uid'], e['forced_arm'], e['run'], e['seed']) for e in plan['episodes']]
        ids_ok = all(e['episode_id'] == 'branch:%s:%s#%d' % (e['parent_episode_id'], ('small', 'large')[e['forced_arm']],
                                                             e['run']) and e['run_order'] == k
                     for k, e in enumerate(plan['episodes']))
        put(rp + 'equal_to_frozen_plan', redraw == planned and ids_ok)

    # ---- stage 3
    s3 = 'design.stage3_continuations.'
    put(s3 + 'continuations_per_arm', design['branch_audit']['continuations_per_arm'])
    put(s3 + 'fork_t', [[k, c] for k, c in sorted(Counter(r['fork_t'] for r in br).items())])
    put(s3 + 'decisions_per_continuation', [[k, c] for k, c in sorted(Counter(len(r['decisions']) for r in br).items())])
    put(s3 + 'decoding', {k: cfg[k] for k in ('temperature', 'top_p', 'max_tokens')})
    bseeds = [e['seed'] for e in plan['episodes']]
    src_eps = design['log_episodes'] + design['live_episodes']
    put(s3 + 'branch_seeds_distinct', len(set(bseeds)))
    put(s3 + 'branch_seeds_shared_with_log_or_live_design_seeds', len(set(bseeds) & {e['seed'] for e in src_eps}))
    H = design['horizon']
    put(s3 + 'branch_model_call_seeds_shared_with_log_or_live',
        len({s + 101 * t for s in bseeds for t in range(1, H)} & {e['seed'] + 101 * t for e in src_eps for t in range(H)}))
    put(s3 + 'replicate_pairs_with_a_shared_seed', sum(
        1 for e in plan['episodes'] if e['forced_arm'] == 0 and
        plan_by['branch:%s:large#%d' % (e['parent_episode_id'], e['run'])]['seed'] == e['seed']))
    agree = Counter('agree' if len(set(v[arm].values())) == 1 else 'disagree' for v in reps.values()
                    for arm in ('small', 'large'))
    put(s3 + 'replicate_agreement', {k: agree[k] for k in sorted(agree)})
    dis_arm = {arm: sum(1 for v in reps.values() if len(set(v[arm].values())) > 1) for arm in ('small', 'large')}
    put(s3 + 'replicate_disagreement_by_arm', dis_arm)
    adj, spreads = 0, []
    for p in samp:
        ords = sorted(e['run_order'] for e in plan['episodes'] if e['parent_episode_id'] == p)
        adj += ords[-1] - ords[0] == len(ords) - 1
        rows = [r for r in br if r['parent_episode_id'] == p]
        if len({r['invocation'] for r in rows}) == 1:
            ts = [ep(r['start_utc']) for r in rows]
            spreads.append(int((max(ts) - min(ts)).total_seconds()))
    spreads.sort()
    put(s3 + 'prefixes_with_adjacent_plan_run_orders', adj)
    put(s3 + 'start_spread_seconds_within_prefix', {'n': len(spreads), 'median': spreads[(len(spreads) - 1) // 2],
                                                    'max': spreads[-1]})
    rs = s3 + 'restoration.'
    rb = recheck['source_binding']
    put(rs + 'recheck_source_binding_matches', (
        rb['branch_episodes_sha256'], rb['log_episodes_sha256'], rb['branch_decisions_sha256'],
        rb['log_decisions_sha256'], rb['tasks_sha256'], rb['n_covered']) == (
        sha(S['branch_episodes']), sha(S['log_episodes']), sha(S['branch_decisions']), sha(S['log_decisions']),
        design['tasks_sha256'], len(br)) and {r['visible_tests_sha256'] for r in br + log} == {rb['visible_tests_sha256']})
    put(rs + 'recorded_flags_all_true', all(r['restoration'].get('transcript_hash_matches') is True and
                                            r['restoration'].get('tool_result_reproduced') is True and
                                            len(r['restoration']) == 2 for r in br))
    for k in ('recomputed_transcript_hash_matches', 'branch_episodes_checked', 'disagreements',
              'stored_tool_result_reproduced'):
        put(rs + 'recheck_' + k, recheck[k])

    # ---- shared records
    arm_w = Counter()
    fr_by = {r['episode_id']: r for r in frame}
    for p in samp:
        a1 = dec(fr_by[p], 1)['a']
        arm_w[(a1, W(fr_by[p], a1) > 0)] += 1
    put('design.shared_records.sampled_prefixes_also_in_log_estimator', sum(1 for p in samp if p in fr_by))
    put('design.shared_records.sampled_prefixes_by_log_arm_and_nonzero_weight',
        [[list(k), c] for k, c in sorted(arm_w.items())])

    # ---- provenance
    pv = 'design.provenance.'
    lost, recv = rec['lost_invocation'], rec['recovery_invocation']
    invs = sorted({r['invocation'] for r in br}, key=lambda i: min(plan_by[r['episode_id']]['run_order']
                                                                  for r in br if r['invocation'] == i))
    inv_obj = {}
    for i in invs:
        rs = [r for r in br if r['invocation'] == i]
        ro = [plan_by[r['episode_id']]['run_order'] for r in rs]
        inv_obj[i] = {'n': len(rs), 'run_order_min': min(ro), 'run_order_max': max(ro),
                      'start_utc_min': min(r['start_utc'] for r in rs), 'start_utc_max': max(r['start_utc'] for r in rs)}
    put(pv + 'invocations', inv_obj)
    put(pv + 'lost_invocation', lost)
    put(pv + 'recovery_invocation', recv)
    put(pv + 'retained_from_lost_invocation', inv_obj[lost]['n'])
    put(pv + 'retained_from_recovery', inv_obj[recv]['n'])
    lro = {plan_by[r['episode_id']]['run_order'] for r in br if r['invocation'] == lost}
    put(pv + 'lost_invocation_run_orders_missing_inside_its_range', [k for k in range(min(lro), max(lro)) if k not in lro])
    put(pv + 'benchmark_by_invocation', [[list(k), c] for k, c in sorted(Counter(
        (r['benchmark'], r['invocation']) for r in br).items())])
    span = {}
    for p in samp:
        by_arm = {arm: sorted({r['invocation'] for r in br if r['parent_episode_id'] == p and r['fork_arm'] == arm})
                  for arm in ('small', 'large')}
        if len(set(by_arm['small']) | set(by_arm['large'])) > 1:
            span[p] = by_arm
    put(pv + 'prefixes_spanning_invocations', span)
    cls = Counter()
    for p in samp:
        u = {r['invocation'] for r in br if r['parent_episode_id'] == p}
        cls['spanning' if len(u) > 1 else ('lost_only' if u == {lost} else 'recovery_only')] += 1
    put(pv + 'prefixes_by_invocation_class', {k: cls[k] for k in ('lost_only', 'recovery_only', 'spanning')})
    xc = 'evidence_table_crosscheck.'
    sf = ev['source_frame']
    put(xc + 'source_frame_counts_equal', (sf['n_fixed_task_blocks'], sf['tasks_with_eligible_prefix'],
                                           sf['tasks_with_no_eligible_prefix'], sf['n_eligible_prefixes'],
                                           sf['tasks_with_sampled_prefix'], sf['tasks_eligible_but_unsampled']) ==
        (len(tasks), len(et), len(tasks) - len(et), N, len(st), len(et - st)))
    put(xc + 'prefixes_per_task_distribution_equal', {int(k): c for k, c in ev['source_blocks'][
        'prefixes_per_task_distribution'].items()} == dict(Counter(samp_t.values())))
    put(xc + 'fresh_pair_discordance_equal', ev['fresh_pairs']['discordant'] == agree['disagree'] and all(
        ev['fresh_pairs']['by_arm'][arm]['discordant'] == dis_arm[arm] for arm in ('small', 'large')))
    er = ev['recovery']
    put(xc + 'recovery_counts_equal', er['continuations_by_invocation'] == {i: inv_obj[i]['n'] for i in inv_obj}
        and (er['prefixes_spanning_two_invocations'], er['prefixes_only_original_invocation'],
             er['prefixes_only_recovery_invocation']) == (cls['spanning'], cls['lost_only'], cls['recovery_only']))
    parents = [e['parent_episode_id'] for e in plan['episodes']]
    put(pv + 'plan_order_sorted_by_parent', all(a <= b for a, b in zip(parents, parents[1:])))
    first_last = {}
    for k, e in enumerate(plan['episodes']):
        first_last.setdefault(e['task_uid'], [k, k])[1] = k
    put(pv + 'plan_order_task_contiguous', all(
        all(plan['episodes'][k]['task_uid'] == t for k in range(a, b + 1)) for t, (a, b) in first_last.items()))
    put(pv + 'attempt_values', [[k, c] for k, c in sorted(Counter(r['attempt'] for r in br).items())])
    put(pv + 'attempt_number_reused', rec['attempt_number_reused'])
    put(pv + 'durable_decision_rows', len(bdec))
    put(pv + 'durable_rows_by_invocation', {k: c for k, c in sorted(Counter(r['invocation'] for r in bdec).items())})
    nm = [{'episode_id': r['episode_id'], 'durable_invocation': r['invocation'], 't': r['t'],
           'retained_invocation': brb[r['episode_id']]['invocation'], 'a': r['a'],
           'transcript_sha256': r['transcript_sha256'],
           'retained_transcript_sha256_equal': r['transcript_sha256'] in {
               d['transcript_sha256'] for d in brb[r['episode_id']]['decisions'] if d['t'] == r['t']}}
          for r in bdec if brb[r['episode_id']]['invocation'] != r['invocation']]
    put(pv + 'durable_rows_matching_the_retained_invocation', len(bdec) - len(nm))
    put(pv + 'durable_rows_not_matching', nm)
    put(pv + 'continuations_with_lost_invocation_durable_rows', sorted({x['episode_id'] for x in nm
                                                                        if x['durable_invocation'] == lost}))
    notret = sorted(plan_by[x]['run_order'] for x in {y['episode_id'] for y in nm if y['durable_invocation'] == lost})
    pc = COMMITS['plan_commit']
    snap = [json.loads(l) for l in git(root, 'show', pc + ':' + SOURCE_PATHS['branch_episodes']).splitlines() if l.strip()]
    snap_rows = [l for l in git(root, 'show', pc + ':' + SOURCE_PATHS['branch_decisions']).splitlines() if l.strip()]
    snap_time = git(root, 'show', '-s', '--format=%cI', pc)
    first_row = {}
    for r in bdec:
        if r['invocation'] == lost and (r['episode_id'] not in first_row or ep(r['logged_utc']) < first_row[r['episode_id']]):
            first_row[r['episode_id']] = ep(r['logged_utc'])
    dmax = max(r['agent_seconds'] for r in br)
    kill = 5 if 'out, err = proc.communicate(timeout=5)' in (root / 'experiments/common/sandbox.py').read_text() else None
    bound = dmax + cfg['sandbox_timeout_s'] + (kill or 0)
    cap = max(r['logged_utc'] for r in bdec if r['invocation'] == lost)
    risk = sorted(plan_by[e]['run_order'] for e, t in first_row.items() if (t - ep(cap)).total_seconds() >= -bound - 1)
    nc = n * design['branch_audit']['continuations_per_arm']
    rw = pv + 'retention_window.'
    put(rw + 'snapshot_commit', pc)
    put(rw + 'snapshot_commit_time', snap_time)
    put(rw + 'snapshot_equals_retained_lost_set', {r['episode_id'] for r in snap} == {
        r['episode_id'] for r in br if r['invocation'] == lost})
    put(rw + 'snapshot_decision_rows', len(snap_rows))
    put(rw + 'capture_not_before_utc', cap)
    put(rw + 'started_before_capture', len(first_row))
    put(rw + 'started_before_capture_not_retained', notret)
    put(rw + 'max_observed_agent_loop_seconds', dmax)
    put(rw + 'hidden_verification_wall_limit_seconds', cfg['sandbox_timeout_s'])
    put(rw + 'kill_wait_seconds', kill)
    put(rw + 'kill_wait_found_in_sandbox_code', kill == 5)
    put(rw + 'start_to_record_bound_seconds', bound)
    put(rw + 'at_risk_run_orders', risk)
    put(rw + 'max_effect_on_B_hat_if_start_to_record_within_bound', Fr(len(risk), nc))
    put(rw + 'max_effect_on_B_hat_trivial', Fr(len(first_row), nc))
    put(pv + 'recovery_ledger_episode_ids', sorted({x['episode_id'] for x in rec['rows']}))
    put(pv + 'recovery_ledger_total_durable_rows', sum(x['durable_decision_rows'] for x in rec['rows']))
    put(pv + 'execution_flags_foreign_gpu_contention', [[list(k), c] for k, c in sorted(Counter(
        (bool(r.get('foreign_gpu_load_at_start')), bool(r.get('contention_check_failed'))) for r in log + br).items())])

    # ---- code binding recomputed from git
    cb = 'design.code_binding.'
    put(cb + 'commits', COMMITS)
    put(cb + 'code_sha256_recomputed_from_git', {k: code_sha_at(root, c) for k, c in COMMITS.items()})
    pb = {k: block(git(root, 'show', c + ':' + SOURCE_PATHS['plan_code']), "elif a.stage == 'branch':",
                   'plan_path.write_text') for k, c in COMMITS.items()}
    pb['head'] = block(S['plan_code'].read_text(), "elif a.stage == 'branch':", 'plan_path.write_text')
    db = {k: block(git(root, 'show', c + ':' + SOURCE_PATHS['design_code']), 'log = []', 'a0_block=int(block[r])')
          for k, c in COMMITS.items()}
    db['head'] = block(S['design_code'].read_text(), 'log = []', 'a0_block=int(block[r])')
    put(cb + 'plan_sampling_block_sha256', {k: hashlib.sha256(b.encode()).hexdigest() for k, b in pb.items()})
    put(cb + 'plan_sampling_block_identical', len(set(pb.values())) == 1)
    put(cb + 'design_block_sha256', {k: hashlib.sha256(b.encode()).hexdigest() for k, b in db.items()})
    put(cb + 'design_block_identical', len(set(db.values())) == 1)
    rc = {r['config_sha256'] for r in log + br + man} | {design['config_sha256']}
    rk = {r['code_sha256'] for r in log + br + man} | {design['design_code_sha256']}
    wt = hashlib.sha256(b''.join(f.read_bytes() for f in sorted((root / 'experiments/code_routing').glob('*.py')) +
                                 sorted((root / 'experiments/common').glob('*.py')))).hexdigest()
    put(cb + 'frozen_record_bindings', {'config_sha256_in_records': sorted(rc), 'code_sha256_in_records': sorted(rk),
                                        'config_file_equals_records': rc == {sha(S['config'])},
                                        'working_tree_code_sha256_equals_records': rk == {wt}})
    put(cb + 'commit_times', {k: git(root, 'show', '-s', '--format=%cI', c) for k, c in COMMITS.items()})
    put('not_done', NOT_DONE)
    for k in ('prefix_ledger', 'task_ledger', 'continuation_ledger'):
        put(('outputs', k), OUT_REL + '/' + k + '.csv')
    ssq = math.sqrt(float(sum((x * x for x in lead.values()), Fr(0))))
    a6u = [r['uncertainty']['value'] for r in a6['rows'] if isinstance(r.get('uncertainty'), dict) and
           r['uncertainty']['label'].startswith('exploratory algebraic scale sqrt(sum U_g^2)')]
    put('lead_derivative.sqrt_sum_sq', ssq)
    put('lead_derivative.equals_a6_uncertainty_value', len(a6u) == 1 and abs(ssq - a6u[0]) <= TOL)
    recomputed = {'B': B, 'log_contrast': v[1] - v[0], 'delta': B - v[1] + v[0]}
    if any(abs(float(recomputed[k]) - ARCHIVED_POINTS[k]) > TOL for k in ARCHIVED_POINTS):
        raise Unverifiable('recomputed point values differ from the archived values %s' % ARCHIVED_POINTS)
    if [audit['full_prefix_branch_mean'], audit['global_hajek_log_mean'], audit['full_original_difference']] != [
            ARCHIVED_POINTS['B'], ARCHIVED_POINTS['log_contrast'], ARCHIVED_POINTS['delta']]:
        raise Unverifiable('lead linkage audit point values differ from the archived values')
    th = {c['condition']: c['status'] for c in a6['theorem_assumption_map'][0]['conditions']}
    fill = {'independent': th['independent complete source-task blocks'],
            'selection': th['selection-invariant fresh replicate pairs independent across prefix/replicate indices'],
            'shocks': th['(same) no execution shocks shared across prefixes'],
            'recovered': th['(same) lost and recovered executions follow one law'],
            'N': N, 'D1': float(D[1]), 'D0': float(D[0])}
    status = {k: v.format(**fill) for k, v in STATUS.items()}

    # ---- CSV expectations
    def opt(x):
        return '' if x is None else x
    prefix = []
    for r in frame:
        d0, d1, d2, dl = dec(r, 0), dec(r, 1), dec(r, 2), dlog[r['episode_id']]
        a1 = d1['a']
        row = [r['episode_id'], r['task_uid'], r['benchmark'], r['run'], dl['run_order'], r['start_utc'], dl['a0_block'],
               d0['a'], Fr(dl['u'][0]), int(d0['validation']['passed']), r['success_first_candidate'],
               len(r['decisions']), r['stop_reason'], a1, Fr(dl['u'][1]), Fr(d1['p_large']),
               opt(d2 and d2['a']), opt(d2 and Fr(dl['u'][2])), opt(d2 and Fr(d2['p_large'])), r['success'],
               W(r, 1), W(r, 0), int(r['episode_id'] in sset), Fr(n, N)]
        if r['episode_id'] in sset:
            rv = reps[r['episode_id']]
            row += [[rv['small'][c] for c in sorted(rv['small'])], [rv['large'][c] for c in sorted(rv['large'])],
                    Dp[r['episode_id']]] + ['|'.join(sorted({brb[e]['invocation'] for e in brb
                                                             if brb[e]['parent_episode_id'] == r['episode_id'] and
                                                             brb[e]['fork_arm'] == arm})) for arm in ('small', 'large')]
        else:
            row += ['', '', '', '', '']
        prefix.append(row)
    task = [[t, next(r['benchmark'] for r in conf if r['task_uid'] == t), sum(1 for r in conf if r['task_uid'] == t),
             elig_t[t], Mga[(t, 0)], Mga[(t, 1)], mg[t], Ag[t], Ug[(t, 1)], Dg[(t, 1)], Ug[(t, 0)], Dg[(t, 0)], lead[t]]
            for t in tasks]
    dcount = Counter((r['episode_id'], r['invocation']) for r in bdec)
    cont = []
    for e in plan['episodes']:
        r = brb[e['episode_id']]
        cont.append([e['episode_id'], e['parent_episode_id'], e['task_uid'], r['benchmark'],
                     ('small', 'large')[e['forced_arm']], e['run'], e['run_order'], e['seed'], e['seed'] + 101,
                     r['invocation'], r['attempt'], r['start_utc'], r['fork_t'], r['n_decisions'], r['success'],
                     int(r['restoration']['transcript_hash_matches']), int(r['restoration']['tool_result_reproduced']),
                     dcount[(e['episode_id'], lost)], dcount[(e['episode_id'], recv)]])
    cols = {
        'prefix_ledger': ['prefix_episode_id', 'task_uid', 'benchmark', 'run', 'log_run_order', 'log_start_utc',
                          'a0_block', 'a0_realized', 'u0', 'first_visible_passed', 'first_hidden_success',
                          'n_decisions', 'stop_reason', 'a_t1', 'u_t1', 'p_large_t1', 'a_t2', 'u_t2', 'p_large_t2',
                          'log_success', 'W_i1', 'W_i0', 'sampled', 'inclusion_probability',
                          'branch_small_runs', 'branch_large_runs', 'prefix_contrast_D', 'invocation_small',
                          'invocation_large'],
        'task_ledger': ['task_uid', 'benchmark', 'log_episodes', 'M_g', 'M_g_a0_small', 'M_g_a0_large', 'm_g', 'A_g',
                        'U_g1', 'D_g1', 'U_g0', 'D_g0', 'lead_derivative_U_g'],
        'continuation_ledger': ['episode_id', 'prefix_episode_id', 'task_uid', 'benchmark', 'arm', 'run',
                                'plan_run_order', 'seed', 'model_call_seed_t1', 'invocation', 'attempt', 'start_utc',
                                'fork_t', 'n_decisions', 'success', 'restoration_transcript_hash_matches',
                                'restoration_tool_result_reproduced_stored', 'durable_rows_lost_invocation',
                                'durable_rows_recovery_invocation']}
    tables = {'prefix_ledger': prefix, 'task_ledger': task, 'continuation_ledger': cont}
    return E, {k: (cols[k], tables[k]) for k in cols}, skipped, status


def cell_ok(cell, exp):
    if isinstance(exp, list):
        return cell == json.dumps(exp)                          # the builder's json.dumps, byte for byte
    if isinstance(exp, Fr):
        return (bool(NUMBER.fullmatch(cell)) and repr(float(cell)) == cell and abs(float(cell) - float(exp)) <= TOL
                and cell.startswith('-') == (exp < 0))
    if isinstance(exp, bool):
        return False
    return cell == str(exp)


def no_duplicate_keys(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise Unverifiable('duplicate JSON keys: %s' % sorted(k for k in set(keys) if keys.count(k) > 1))
    return dict(pairs)


def main(argv=None):
    ap = argparse.ArgumentParser(allow_abbrev=False)
    ap.add_argument('--ledger-dir', default=str(HERE))
    ap.add_argument('--root', default=str(ROOT))
    ap.add_argument('--allow-skip-repro', action='store_true')
    a = ap.parse_args(argv)
    root, out = Path(a.root), Path(a.ledger_dir)
    fails = []
    try:
        raw = (out / 'design_ledger.json').read_text()
        L = json.loads(raw, object_pairs_hook=no_duplicate_keys)
        if raw != json.dumps(L, indent=1) + '\n':
            raise Unverifiable('design_ledger.json is not in the canonical form written by the builder')
        E, tables, skipped, status = expected_values(root, a.allow_skip_repro)
        for k in ('prefix_ledger', 'task_ledger', 'continuation_ledger'):
            E[('outputs', k + '_sha256')] = sha(out / (k + '.csv'))
    except Unverifiable as e:
        print(json.dumps({'ok': False, 'n_failures': 1, 'failures': [str(e)], 'skipped': []}))
        return 1

    # JSON: every expected path present and equal; every numeric/boolean leaf covered
    covered = []
    for path, exp in E.items():
        node = L
        try:
            for k in path:
                node = node[k]
        except (KeyError, IndexError, TypeError):
            fails.append('missing %s' % '.'.join(map(str, path)))
            continue
        el = dict(leaves(json.loads(json.dumps(exp, default=lambda x: float(x)))))
        al = dict(leaves(node))
        if set(el) != set(al):
            fails.append('structure %s' % '.'.join(map(str, path)))
            continue
        for k in el:
            if not same(el[k], al[k]):
                fails.append('value %s: ledger %r, recomputed %r' % ('.'.join(map(str, path + k)), al[k], el[k]))
        covered.append(path)
    covered += skipped
    npath = ('design', 'stage2_prefix_sample', 'reproduction', 'numpy')       # the builder's numpy: any release
    nv = L.get('design', {}).get('stage2_prefix_sample', {}).get('reproduction', {}).get('numpy')
    if not (isinstance(nv, str) and VERSION.fullmatch(nv)):
        fails.append('reproduction.numpy is not a version string')
    covered.append(npath)
    for path, val in leaves(L):
        if isinstance(val, (bool, int, float)) and not any(path[:len(c)] == c for c in covered):
            fails.append('unchecked numeric/boolean field %s' % '.'.join(map(str, path)))
    for m in MUST_TRUE:
        node = L
        for k in m.split('.'):
            node = node.get(k) if isinstance(node, dict) else None
        if node is not True:
            fails.append('must be true: %s' % m)
    if set(L.get('outputs', {})) != {'prefix_ledger', 'task_ledger', 'continuation_ledger', 'prefix_ledger_sha256',
                                     'task_ledger_sha256', 'continuation_ledger_sha256'}:
        fails.append('outputs keys')
    if set(L) != {'request', 'kind', 'lead_commit', 'lead_decision', 'builds_on', 'target', 'sources',
                  'evidence_table_crosscheck', 'reconciliation',
                  'point_estimates', 'design', 'identification', 'lead_derivative', 'outputs', 'not_done'}:
        fails.append('top-level keys')
    if [c.get('component') for c in L.get('identification', {}).get('components', [])] != COMPONENTS:
        fails.append('identification components')
    for c in L.get('identification', {}).get('components', []):
        if c.get('status') != status.get(c.get('component')) or not c.get('evidence'):
            fails.append('identification status/evidence: %s' % c.get('component'))
    # every leaf of any type outside the recomputed paths, with its typed path (list index vs key kept apart)
    text = sorted([json.dumps([[type(k).__name__, k] for k in pth]), json.dumps(val)] for pth, val in leaves(L)
                  if not any(pth[:len(c)] == c for c in covered))
    text_sha = hashlib.sha256(json.dumps(text).encode()).hexdigest()
    if text_sha != TEXT_SHA256:
        fails.append('pinned text changed (sha256 %s)' % text_sha)
    tgt = json.dumps(L.get('target', {}))
    for needle in ('eq. (2)', 'sum_g E T_g / sum_g E M_g', 'does not make B_hat unbiased for theta', 'mu_F',
                   'not sampled from a superpopulation'):
        if needle not in tgt:
            fails.append('target statement lacks %r' % needle)

    # CSV: header, row count, every cell
    for name, (cols, rows) in tables.items():
        f = out / (name + '.csv')
        if L.get('outputs', {}).get(name + '_sha256') != sha(f):
            fails.append('%s sha256' % name)
        with f.open(newline='') as fh:
            rd = csv.reader(fh)
            header = next(rd)
            got = list(rd)
        if header != cols:
            fails.append('%s header' % name)
            continue
        if len(got) != len(rows):
            fails.append('%s rows %d != %d' % (name, len(got), len(rows)))
        for i, (g, e) in enumerate(zip(got, rows)):
            if len(g) != len(cols) or len(e) != len(cols):
                fails.append('%s row %d has %d cells, expected %d' % (name, i, len(g), len(cols)))
                continue
            for c, x, y in zip(cols, g, e):
                if not cell_ok(x, y):
                    fails.append('%s row %d column %s: %r != %r' % (name, i, c, x, y))
    res = {'ok': not fails, 'n_failures': len(fails), 'failures': fails[:50],
           'checked_json_paths': len(E), 'checked_csv_cells': sum(len(r) * len(c) for c, r in tables.values()),
           'skipped': ['.'.join(map(str, p)) for p in skipped]}
    print(json.dumps(res))
    return 0 if not fails else 1


if __name__ == '__main__':
    sys.exit(main())
