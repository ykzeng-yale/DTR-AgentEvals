"""DTR-REQ-018 (lead 9e6c1ac, docs/theory_feedback_20260926_req017_decision.md): a deterministic, source-bound design
ledger for the archived fixed-benchmark primary contrast of docs/theory_branch_fixed_benchmark_bound.md eq. (2),
Delta = theta - nu_1 + nu_0, with theta = sum_g E T_g / sum_g E M_g and nu_a = sum_g E U_ga / sum_g E D_ga over
repeated designs of the 330 fixed CONFIRM task blocks (lead-adopted target; weighting decision
docs/theory_feedback_20260921_weighting.md).

No model, no browser, no Monte Carlo, no archive change. It reads the frozen code_routing records, reproduces the
branch-prefix sample from the frozen design seed and plan code, rebuilds the original point estimates (eq. 3), and
writes, under results/code_routing/analysis/req018/:

    design_ledger.json        the three design stages, eligibility, inclusion mechanism and probabilities, replicates,
                              shared records, execution schedule and recovery provenance, and a per-component
                              identification map (identified / assumed / not identified) with an acceptance statement
    prefix_ledger.csv         one row per eligible first-failure prefix (the 564 CONFIRM log episodes with >= 2 decisions)
    task_ledger.csv           one row per CONFIRM source task (all 330, zero contributions kept)
    continuation_ledger.csv   one row per branch continuation (800), in plan order

It asserts no standard error, interval or bootstrap: the lead derives the same-target uncertainty.

    .venv/bin/python experiments/tools/req018_design_ledger.py [--out DIR]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import subprocess
import sys
from collections import Counter, OrderedDict, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUEST = 'DTR-REQ-018'
CR = 'results/code_routing'
SOURCES = OrderedDict([
    ('design', CR + '/design.json'),
    ('log_episodes', CR + '/log/episodes.jsonl'),
    ('branch_plan', CR + '/branch/branch_plan.json'),
    ('branch_episodes', CR + '/branch/episodes.jsonl'),
    ('log_decisions', CR + '/log/decisions.jsonl'),
    ('branch_decisions', CR + '/branch/decisions.jsonl'),
    ('branch_run_manifest', CR + '/branch/run_manifest.jsonl'),
    ('recovery_ledger', CR + '/recovery_ledger.json'),
    ('restoration_recheck', CR + '/analysis/restoration_recheck.json'),
    ('branch_evidence_table', CR + '/analysis/branch_evidence_table.json'),
    ('a6_report', CR + '/analysis/a6_report.json'),
    ('lead_linkage_audit', 'docs/audits/theory_branch_linkage_audit_20260920.json'),
    ('target_note', 'docs/theory_branch_fixed_benchmark_bound.md'),
    ('weighting_decision', 'docs/theory_feedback_20260921_weighting.md'),
    ('design_code', 'experiments/code_routing/design.py'),
    ('episode_code', 'experiments/code_routing/agent.py'),
    ('plan_code', 'experiments/code_routing/run.py'),
    ('config', 'experiments/code_routing/config.json'),
])
DESIGN_FREEZE_COMMIT = 'cb9481d77567b7b14e3ceb6c1f0a6b534c67edcb'   # a6 branch_plan_reproduction.design_freeze_commit
LOG_COMMIT = 'c1de983f5152e70688db0b0c8ac198f085ce431e'             # git_head of the CONFIRM log invocation
PLAN_INVOCATION_COMMIT = 'f3aa436abf5101f0170b2030acce7bed70dcf344'  # git_head of the invocation that drew the plan
PLAN_COMMIT = 'ac3ca8368e0b1b05990f1ef108fe1cc4bfb1251a'           # the commit that first added branch_plan.json
CODE_COMMITS = OrderedDict([('design_freeze', DESIGN_FREEZE_COMMIT), ('log_invocation', LOG_COMMIT),
                            ('plan_invocation', PLAN_INVOCATION_COMMIT), ('plan_commit', PLAN_COMMIT)])
P_ARMS = ('small', 'large')
OUT_REL = CR + '/analysis/req018'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args, root=ROOT):
    return subprocess.run(['git', '--no-replace-objects', '-C', str(root)] + list(args), capture_output=True,
                          text=True).stdout.strip()


def git_bytes(commit, rel, root=ROOT):
    return subprocess.run(['git', '--no-replace-objects', '-C', str(root), 'show', '%s:%s' % (commit, rel)],
                          capture_output=True).stdout


def _epoch(iso):
    return int(datetime.fromisoformat(iso.replace('Z', '+00:00')).timestamp())


def fsum_mean(v):
    return math.fsum(v) / len(v)


def load_jsonl(path):
    return [json.loads(l) for l in Path(path).read_text().splitlines() if l.strip()]


# ------------------------------------------------------------------ pure constructions
def eligible_parents(log_rows):
    """run.py's frame: the last non-error record per episode id, confirm split, >= 2 decisions, sorted by id."""
    last = {}
    for r in log_rows:
        if not r.get('error'):
            last[r['episode_id']] = r
    return sorted((r for r in last.values() if r['split'] == 'confirm' and r['n_decisions'] >= 2),
                  key=lambda r: r['episode_id'])


def reproduce_plan(parents, branch_audit):
    """run.py's frozen draw: SRS without replacement of min(n_prefixes, N) of the eligible frame, then per picked
    prefix, per arm, per continuation, one seed from the same generator."""
    import numpy as np
    rng = np.random.default_rng(branch_audit['seed'])
    pick = sorted(rng.choice(len(parents), size=min(branch_audit['n_prefixes'], len(parents)), replace=False).tolist())
    eps = []
    for i in pick:
        for arm in (0, 1):
            for c in range(branch_audit['continuations_per_arm']):
                eps.append(OrderedDict(episode_id='branch:%s:%s#%d' % (parents[i]['episode_id'], P_ARMS[arm], c),
                                       parent_episode_id=parents[i]['episode_id'], task_uid=parents[i]['task_uid'],
                                       run=c, forced_arm=arm, seed=int(rng.integers(1, 2 ** 31 - 1)),
                                       run_order=len(eps)))
    return pick, eps, np.__version__


def log_weight(e):
    """The archived log estimator's weight for the first-failure prefix e (eq. 1 W_ia; lead audit d4997c6): the
    continuation arm is decision 1's arm; weight 2 if the episode stops after decision 1, 4 if decision 2 repeats that
    arm, else 0 (inverse of the recorded 0.5 propensities of decisions 1 and 2)."""
    ds = e['decisions']
    arm = ds[1]['a']
    return arm, (2. if len(ds) == 2 else (4. if ds[2]['a'] == arm else 0.))


def estimates(tasks, eligible, branch_rows):
    """B (branch prefix mean), v_a (pooled Hajek log arm values), Delta, and the per-task components: A_g (sum of the
    sampled prefix contrasts), m_g (sampled prefixes), U_ga / D_ga (eq. 1 weighted successes / weights; N_ga in the
    20 Sep note) and the lead's reweighting derivative (docs/theory_feedback_20260920_branch.md), all source tasks,
    zeros kept. Replicates are ordered by their run index."""
    runs = defaultdict(lambda: defaultdict(list))
    ptask = {}
    for e in sorted(branch_rows, key=lambda r: (r['parent_episode_id'], r['fork_arm'], r['run'])):
        runs[e['parent_episode_id']][e['fork_arm']].append(e['success'])
        ptask[e['parent_episode_id']] = e['task_uid']
    D = {p: fsum_mean(a['large']) - fsum_mean(a['small']) for p, a in runs.items()}
    m = len(D)
    B = fsum_mean(list(D.values()))
    A = defaultdict(float)
    mg = Counter()
    for p, d in D.items():
        A[ptask[p]] += d
        mg[ptask[p]] += 1
    N = {t: [0., 0.] for t in tasks}
    Dn = {t: [0., 0.] for t in tasks}
    for e in eligible:
        arm, w = log_weight(e)
        N[e['task_uid']][arm] += w * e['success']
        Dn[e['task_uid']][arm] += w
    Y = [math.fsum(N[t][a] for t in tasks) for a in (0, 1)]
    Z = [math.fsum(Dn[t][a] for t in tasks) for a in (0, 1)]
    v = [Y[a] / Z[a] for a in (0, 1)]
    U = {t: (A[t] - B * mg[t]) / m - (N[t][1] - v[1] * Dn[t][1]) / Z[1] + (N[t][0] - v[0] * Dn[t][0]) / Z[0]
         for t in tasks}
    return OrderedDict(D=D, m=m, B=B, A=A, mg=mg, N=N, Dn=Dn, Y=Y, Z=Z, v=v, L=v[1] - v[0], delta=B - (v[1] - v[0]),
                       U=U, ptask=ptask, runs=runs)


# ------------------------------------------------------------------ code bindings from git
def sampling_block(text):
    """run.py's branch-plan block (from the stage branch to the plan write)."""
    lines = text.splitlines()
    i = next(k for k, l in enumerate(lines) if l.strip() == "elif a.stage == 'branch':")
    j = next(k for k in range(i, len(lines)) if 'plan_path.write_text' in lines[k])
    return '\n'.join(lines[i:j + 1])


def design_block(text):
    """design.py's CONFIRM/TRAIN log block (the permuted first-decision block and the design uniforms)."""
    lines = text.splitlines()
    i = next(k for k, l in enumerate(lines) if l.strip() == 'log = []')
    j = next(k for k in range(i, len(lines)) if 'a0_block=int(block[r])' in lines[k])
    return '\n'.join(lines[i:j + 1])


def code_sha256_at(commit, root=ROOT):
    """common.code_sha256() recomputed from git: the bytes of experiments/code_routing/*.py then experiments/common/*.py,
    each sorted by path."""
    def ls(d):
        names = git('ls-tree', '--name-only', commit, d + '/', root=root).split()
        return sorted(p for p in names if p.endswith('.py') and p.count('/') == d.count('/') + 1)
    files = ls('experiments/code_routing') + ls('experiments/common')
    return hashlib.sha256(b''.join(git_bytes(commit, f, root) for f in files)).hexdigest(), len(files)


def code_binding(root=ROOT):
    plan_blocks = OrderedDict((k, sampling_block(git_bytes(c, SOURCES['plan_code'], root).decode()))
                              for k, c in CODE_COMMITS.items())
    plan_blocks['head'] = sampling_block((root / SOURCES['plan_code']).read_text())
    design_blocks = OrderedDict((k, design_block(git_bytes(c, SOURCES['design_code'], root).decode()))
                                for k, c in CODE_COMMITS.items())
    design_blocks['head'] = design_block((root / SOURCES['design_code']).read_text())
    shas = OrderedDict((k, code_sha256_at(c, root)[0]) for k, c in CODE_COMMITS.items())
    return OrderedDict(
        commits=CODE_COMMITS,
        code_sha256_recomputed_from_git=shas,
        plan_sampling_block_sha256=OrderedDict((k, hashlib.sha256(b.encode()).hexdigest()) for k, b in plan_blocks.items()),
        plan_sampling_block_identical=len(set(plan_blocks.values())) == 1,
        design_block_sha256=OrderedDict((k, hashlib.sha256(b.encode()).hexdigest()) for k, b in design_blocks.items()),
        design_block_identical=len(set(design_blocks.values())) == 1,
        commit_times=OrderedDict((k, git('show', '-s', '--format=%cI', c, root=root)) for k, c in CODE_COMMITS.items()))


# ------------------------------------------------------------------ the ledger
def build(root=ROOT):
    src = OrderedDict()
    for k, rel in SOURCES.items():
        head_blob = git('rev-parse', 'HEAD:' + rel, root=root) or None
        src[k] = OrderedDict(path=rel, sha256=sha(root / rel), bytes=(root / rel).stat().st_size,
                             git_blob_head=head_blob,
                             working_tree_equals_head=head_blob == git('hash-object', str(root / rel), root=root))
    design = json.loads((root / SOURCES['design']).read_text())
    log_rows = load_jsonl(root / SOURCES['log_episodes'])
    plan = json.loads((root / SOURCES['branch_plan']).read_text())
    branch = load_jsonl(root / SOURCES['branch_episodes'])
    bdec = load_jsonl(root / SOURCES['branch_decisions'])
    manifest = load_jsonl(root / SOURCES['branch_run_manifest'])
    recovery = json.loads((root / SOURCES['recovery_ledger']).read_text())
    recheck = json.loads((root / SOURCES['restoration_recheck']).read_text())
    a6 = json.loads((root / SOURCES['a6_report']).read_text())
    evidence = json.loads((root / SOURCES['branch_evidence_table']).read_text())
    lead_audit = json.loads((root / SOURCES['lead_linkage_audit']).read_text())
    config = json.loads((root / SOURCES['config']).read_text())

    confirm_tasks = list(design['confirm_tasks'])
    confirm_log = [r for r in log_rows if r['split'] == 'confirm']
    design_log = {e['episode_id']: e for e in design['log_episodes']}
    eligible = eligible_parents(log_rows)
    pick, reproduced, numpy_version = reproduce_plan(eligible, design['branch_audit'])
    plan_eps = plan['episodes']
    plan_by_id = {e['episode_id']: e for e in plan_eps}
    keys = ('episode_id', 'parent_episode_id', 'task_uid', 'run', 'forced_arm', 'seed', 'run_order')
    reproduction_equal = len(reproduced) == len(plan_eps) and all(
        all(a[k] == b[k] for k in keys) for a, b in zip(reproduced, plan_eps))
    sampled = sorted({e['parent_episode_id'] for e in plan_eps})
    sampled_set = set(sampled)
    est = estimates(confirm_tasks, eligible, branch)
    by_ep = {r['episode_id']: r for r in branch}
    bench = {r['task_uid']: r['benchmark'] for r in confirm_log}
    lost, rec = recovery['lost_invocation'], recovery['recovery_invocation']

    # ---- stage 1: the randomized source log
    a0_by_task = defaultdict(list)
    for r in confirm_log:
        a0_by_task[r['task_uid']].append(design_log[r['episode_id']]['a0_block'])
    block_patterns = Counter(tuple(sorted(v)) for v in a0_by_task.values())
    a0_realized_equals_block = sum(r['decisions'][0]['a'] == design_log[r['episode_id']]['a0_block'] for r in confirm_log)
    u0_by_block = Counter((design_log[r['episode_id']]['a0_block'], design_log[r['episode_id']]['u'][0])
                          for r in confirm_log)
    draws_checked = draws_bad = later_checked = 0
    for r in confirm_log:
        u = design_log[r['episode_id']]['u']
        for d in r['decisions']:
            draws_checked += 1
            later_checked += d['t'] >= 1
            draws_bad += not (d['draw'] == u[d['t']] and d['a'] == int(d['draw'] < d['p_large']))
    p_values = Counter(d['p_large'] for r in confirm_log for d in r['decisions'])
    sources_of_draw = Counter((d['t'], d['source']) for r in confirm_log for d in r['decisions'])
    per_task_episodes = Counter(r['task_uid'] for r in confirm_log)
    elig_per_task = Counter(e['task_uid'] for e in eligible)
    elig_per_task_a0 = Counter((e['task_uid'], design_log[e['episode_id']]['a0_block']) for e in eligible)
    samp_per_task = Counter(e['task_uid'] for e in eligible if e['episode_id'] in sampled_set)
    elig_vs_visible = Counter((r['n_decisions'] >= 2, r['decisions'][0]['validation']['passed']) for r in confirm_log)
    stop_table = Counter((r['n_decisions'], r['stop_reason']) for r in confirm_log)
    log_inv = Counter((r['invocation'], r['split'], r['git_head'], r['code_sha256']) for r in log_rows)
    starts = defaultdict(list)
    for r in log_rows:
        starts[r['split']].append(r['start_utc'])
    log_run_order = [design_log[r['episode_id']]['run_order'] for r in log_rows]
    decile = Counter((design_log[r['episode_id']]['run_order'] * 10 // len(log_rows), r['split']) for r in log_rows)

    # ---- zero-arm and zero-contribution counts
    zero = Counter()
    for t in confirm_tasks:
        d1, d0 = est['Dn'][t][1], est['Dn'][t][0]
        cls = ('eligible' if elig_per_task[t] else 'not_eligible', 'sampled' if samp_per_task[t] else 'unsampled',
               'D_g1=0' if d1 == 0 else 'D_g1>0', 'D_g0=0' if d0 == 0 else 'D_g0>0')
        zero[cls] += 1

    def zc(pred):
        return sum(v for k, v in zero.items() if pred(k))
    zero_arm = OrderedDict(
        eligible_tasks_D_g1_zero=zc(lambda k: k[0] == 'eligible' and k[2] == 'D_g1=0'),
        eligible_tasks_D_g0_zero=zc(lambda k: k[0] == 'eligible' and k[3] == 'D_g0=0'),
        eligible_tasks_both_zero=zc(lambda k: k[0] == 'eligible' and k[2] == 'D_g1=0' and k[3] == 'D_g0=0'),
        eligible_tasks_both_positive=zc(lambda k: k[0] == 'eligible' and k[2] == 'D_g1>0' and k[3] == 'D_g0>0'),
        sampled_tasks_both_positive=zc(lambda k: k[1] == 'sampled' and k[2] == 'D_g1>0' and k[3] == 'D_g0>0'),
        sampled_tasks_at_least_one_zero=zc(lambda k: k[1] == 'sampled' and (k[2] == 'D_g1=0' or k[3] == 'D_g0=0')),
        tasks_lead_derivative_exactly_zero=sum(1 for t in confirm_tasks if est['U'][t] == 0.0))

    # ---- stage 3: continuations, replication, seeds, restoration
    agree = Counter()
    disagree_by_arm = Counter()
    for p, a in est['runs'].items():
        for arm in P_ARMS:
            agree['agree' if len(set(a[arm])) == 1 else 'disagree'] += 1
            disagree_by_arm[arm] += len(set(a[arm])) > 1
    all_restoration_true = all(r['restoration'] == {'transcript_hash_matches': True, 'tool_result_reproduced': True}
                               for r in branch)
    branch_seeds = [e['seed'] for e in plan_eps]
    source_seeds = [e['seed'] for e in design['log_episodes'] + design['live_episodes']]
    horizon = design['horizon']
    branch_call_seeds = {e['seed'] + 101 * t for e in plan_eps for t in range(1, horizon)}
    source_call_seeds = {e['seed'] + 101 * t for e in design['log_episodes'] + design['live_episodes']
                         for t in range(horizon)}
    arm_seed_shared = sum(1 for p in sampled for c in range(design['branch_audit']['continuations_per_arm'])
                          if plan_by_id['branch:%s:small#%d' % (p, c)]['seed'] ==
                          plan_by_id['branch:%s:large#%d' % (p, c)]['seed'])
    decisions_per_continuation = Counter(len(r['decisions']) for r in branch)
    spread = []
    adjacent = 0
    for p in sampled:
        orders = sorted(plan_by_id[e]['run_order'] for e in plan_by_id if plan_by_id[e]['parent_episode_id'] == p)
        adjacent += orders == list(range(orders[0], orders[0] + len(orders)))
        rows = [x for x in branch if x['parent_episode_id'] == p]
        if len({x['invocation'] for x in rows}) == 1:
            ts = sorted(_epoch(x['start_utc']) for x in rows)
            spread.append(ts[-1] - ts[0])
    spread.sort()
    visible = {x['visible_tests_sha256'] for x in branch + log_rows}
    rb = recheck['source_binding']
    recheck_binding = (rb['branch_episodes_sha256'] == src['branch_episodes']['sha256'] and
                       rb['log_episodes_sha256'] == src['log_episodes']['sha256'] and
                       rb['branch_decisions_sha256'] == src['branch_decisions']['sha256'] and
                       rb['log_decisions_sha256'] == src['log_decisions']['sha256'] and
                       visible == {rb['visible_tests_sha256']} and rb['tasks_sha256'] == design['tasks_sha256'] and
                       rb['n_covered'] == len(branch))

    # ---- provenance: invocations, schedule, recovery
    ro = defaultdict(list)
    for r in branch:
        ro[r['invocation']].append(plan_by_id[r['episode_id']]['run_order'])
    inv_order = OrderedDict((k, OrderedDict(n=len(v), run_order_min=min(v), run_order_max=max(v),
                                            start_utc_min=min(x['start_utc'] for x in branch if x['invocation'] == k),
                                            start_utc_max=max(x['start_utc'] for x in branch if x['invocation'] == k)))
                            for k, v in sorted(ro.items(), key=lambda kv: min(kv[1])))
    lost_orders = set(ro[lost])
    gap_in_lost_range = sorted(set(range(min(lost_orders), max(lost_orders) + 1)) - lost_orders)
    bench_inv = Counter((r['benchmark'], r['invocation']) for r in branch)
    arm_inv = defaultdict(lambda: defaultdict(set))
    for r in branch:
        arm_inv[r['parent_episode_id']][r['fork_arm']].add(r['invocation'])
    spanning = OrderedDict()
    for p in sampled:
        invs = set().union(*arm_inv[p].values())
        if len(invs) > 1:
            spanning[p] = OrderedDict((arm, sorted(arm_inv[p][arm])) for arm in P_ARMS)
    prefix_inv_class = Counter(
        'spanning' if len(set().union(*arm_inv[p].values())) > 1 else
        ('lost_only' if set().union(*arm_inv[p].values()) == {lost} else 'recovery_only') for p in sampled)
    task_contiguous = all(
        max(v) - min(v) + 1 == len(v) for v in
        (lambda g: g.values())(_group(plan_eps, lambda e: e['task_uid'], lambda e: e['run_order'])))
    plan_order_sorted_by_parent = [e['parent_episode_id'] for e in plan_eps] == sorted(
        e['parent_episode_id'] for e in plan_eps)
    dec_rows = Counter((r['episode_id'], r['invocation']) for r in bdec)
    durable_lost_ids = sorted({r['episode_id'] for r in bdec if r['invocation'] == lost and
                               by_ep[r['episode_id']]['invocation'] != lost})
    durable_nonmatching = [OrderedDict(episode_id=r['episode_id'], durable_invocation=r['invocation'], t=r['t'],
                                       retained_invocation=by_ep[r['episode_id']]['invocation'], a=r['a'],
                                       transcript_sha256=r['transcript_sha256'],
                                       retained_transcript_sha256_equal=any(
                                           d['t'] == r['t'] and d['transcript_sha256'] == r['transcript_sha256']
                                           for d in by_ep[r['episode_id']]['decisions']))
                           for r in bdec if by_ep[r['episode_id']]['invocation'] != r['invocation']]
    recovery_ids = sorted({row['episode_id'] for row in recovery.get('rows') or []})
    unretained = sorted(plan_by_id[e]['run_order'] for e in durable_lost_ids)
    snap = [json.loads(l) for l in git_bytes(PLAN_COMMIT, SOURCES['branch_episodes'], root).decode().splitlines()
            if l.strip()]
    snap_rows = [l for l in git_bytes(PLAN_COMMIT, SOURCES['branch_decisions'], root).decode().splitlines() if l.strip()]
    snap_time = git('show', '-s', '--format=%cI', PLAN_COMMIT, root=root)
    lost_start = {}
    for r in bdec:
        if r['invocation'] == lost:
            lost_start[r['episode_id']] = min(lost_start.get(r['episode_id'], r['logged_utc']), r['logged_utc'])
    d_max = max(r['agent_seconds'] for r in branch)
    sandbox_src = (root / 'experiments/common/sandbox.py').read_text()
    kill_wait = 5 if 'out, err = proc.communicate(timeout=5)' in sandbox_src else None
    bound = d_max + config['sandbox_timeout_s'] + (kill_wait or 0)
    capture_after = max(r['logged_utc'] for r in bdec if r['invocation'] == lost)
    at_risk = sorted(plan_by_id[e]['run_order'] for e, t in lost_start.items()
                     if _epoch(t) >= _epoch(capture_after) - bound - 1)
    n_cont = len(sampled) * design['branch_audit']['continuations_per_arm']
    retention = OrderedDict(
        records_written='episode records only on completion (run.py: as_completed, one fsynced append per finished '
                        'episode); decision rows before each model call',
        snapshot_commit=PLAN_COMMIT, snapshot_commit_time=snap_time,
        snapshot_equals_retained_lost_set={r['episode_id'] for r in snap} == {r['episode_id'] for r in branch
                                                                                  if r['invocation'] == lost},
        snapshot_decision_rows=len(snap_rows),
        capture_not_before_utc=capture_after,
        started_before_capture=len(lost_start), started_before_capture_not_retained=unretained,
        max_observed_agent_loop_seconds=d_max, hidden_verification_wall_limit_seconds=config['sandbox_timeout_s'],
        kill_wait_seconds=kill_wait, kill_wait_found_in_sandbox_code=kill_wait == 5,
        start_to_record_bound_seconds=bound,
        at_risk_run_orders=at_risk,
        max_effect_on_B_hat_if_start_to_record_within_bound=len(at_risk) / n_cont,
        max_effect_on_B_hat_trivial=len(lost_start) / n_cont,
        reading='the lost invocation reportedly executed all 800 continuations (operator report, protocol section 11), '
                'but only those whose episode records had been written when the snapshot was captured (not before the '
                'last snapshot decision row, not after the commit) were retained; a continuation started before the '
                'capture was retained iff it had finished. '
                'If duration is associated with outcome, retained outcomes near the cutoff follow a selected law even '
                'when the lost and recovery laws agree. The at-risk set holds the continuations whose first durable row '
                'is within the start-to-record bound (+1 s truncation) of the earliest possible capture. The bound is '
                'empirical, not guaranteed by the code; the bound on B_hat needs every potential start-to-record time '
                '(under either outcome) within it and start times that do not depend on the continuation\'s own '
                'potential outcomes. Each '
                'continuation moves B_hat by at most 1/(m r) = 1/400')
    exec_flags = Counter((bool(r.get('foreign_gpu_load_at_start')), bool(r.get('contention_check_failed')))
                         for r in log_rows + branch)

    # ---- shared records: every sampled prefix is also an eligible log episode entering the log estimator
    shared_nonzero = Counter()
    for p in sampled:
        arm, w = log_weight(next(x for x in eligible if x['episode_id'] == p))
        shared_nonzero[(arm, w > 0)] += 1
    elig_by_a0 = Counter(design_log[e['episode_id']]['a0_block'] for e in eligible)
    samp_by_a0 = Counter(design_log[e['episode_id']]['a0_block'] for e in eligible if e['episode_id'] in sampled_set)
    n_elig, n_samp = len(eligible), len(pick)
    freeze_time = _epoch(git('show', '-s', '--format=%cI', DESIGN_FREEZE_COMMIT, root=root))
    first_log_start = min(r['start_utc'] for r in log_rows)
    design_at_freeze = git('rev-parse', DESIGN_FREEZE_COMMIT + ':' + SOURCES['design'], root=root)
    precommit = OrderedDict(
        design_json_blob_at_freeze_equals_head=design_at_freeze == src['design']['git_blob_head'],
        design_created_before_freeze_commit=_epoch(design['created_utc']) <= freeze_time,
        freeze_commit_before_first_log_episode=freeze_time <= _epoch(first_log_start),
        log_invocation_commit_descends_from_freeze=subprocess.run(
            ['git', '--no-replace-objects', '-C', str(root), 'merge-base', '--is-ancestor', DESIGN_FREEZE_COMMIT,
             LOG_COMMIT]).returncode == 0,
        plan_created_at_first_branch_invocation_start=(plan['created_utc'] == manifest[0]['started_utc'] and
                                                       manifest[0]['n_ok_before'] == 0))
    mechanism = a6['branch_plan_reproduction']
    a6_uncertainty = next(r['uncertainty']['value'] for r in a6['rows']
                          if isinstance(r.get('uncertainty'), dict) and 'sqrt(sum U_g^2)' in r['uncertainty']['label'])
    theorem_map = a6['theorem_assumption_map'][0]['conditions']

    def a6_status(prefix):
        return next(c['status'] for c in theorem_map if c['condition'].startswith(prefix))

    ledger = OrderedDict(
        request=REQUEST, kind='source-bound design ledger (no model, no Monte Carlo, no archive change)',
        lead_commit='9e6c1ac', lead_decision='docs/theory_feedback_20260926_req017_decision.md',
        builds_on=['docs/theory_branch_fixed_benchmark_bound.md (eq. 2 target, sec. 2 assumptions, eq. 3 estimators)',
                   'docs/theory_feedback_20260921_weighting.md (pooled eligible-prefix target; all 330 tasks kept)',
                   'docs/theory_feedback_20260920_branch.md (reweighting derivative)',
                   'results/code_routing/analysis/a6_report.json (theorem_assumption_map, branch_plan_reproduction)',
                   'docs/audits/check_branch_linkage_d4997c6.py', 'docs/audits/theory_branch_linkage_audit_20260920.json',
                   'results/code_routing/analysis/restoration_recheck.json',
                   'results/code_routing/analysis/branch_evidence_table.json (reconciled in evidence_table_crosscheck)'],
        target=OrderedDict(
            primary=('eq. (2) of docs/theory_branch_fixed_benchmark_bound.md, adopted by the lead: theta = sum_g E T_g / '
                     'sum_g E M_g, nu_a = sum_g E U_ga / sum_g E D_ga, Delta = theta - nu_1 + nu_0, with expectations '
                     'over repeated designs of the 330 fixed CONFIRM task blocks (8 episodes each, 4-small/4-large '
                     'first allocation, p_large = 0.5 later) under a fixed restored-execution continuation law; the '
                     'tasks are fixed, not sampled from a superpopulation'),
            components=OrderedDict(
                M_g='number of first-failure (eligible) prefixes of task g, 0..8', T_g='sum over those prefixes of '
                'd_i, the stay-large minus stay-small fresh-continuation success mean', U_ga='sum_i W_ia Y_i (called '
                'N_ga in the 20 Sep note and in earlier ledgers)', D_ga='sum_i W_ia',
                W_ia='1{A_i1=a}/0.5 x (1 if absorbed after the first repair, else 1{A_i2=a}/0.5)'),
            estimators=OrderedDict(
                B_hat='(1/(m r)) sum_{i in S, j<=r} Z_ij, Z_ij = Y_i1j - Y_i0j, m = 200 sampled prefixes, r = 2 '
                      'replicate pairs (the pair index j pairs the arms by label only)',
                nu_hat='U_a / D_a pooled over all eligible prefixes of all 330 tasks (Hajek)',
                delta_hat='B_hat - nu_hat_1 + nu_hat_0 (eq. 3; the archived pooled point estimator)'),
            secondary=OrderedDict(
                mu_F='realized-frame mean sum_{i in F} d_i / N over the N = 564 recorded eligible prefixes (task weights '
                     'M_g/N within this frame)',
                relation='under assumptions 2-3 of the target note, E(B_hat | F) = mu_F; uniform sampling does not make '
                         'B_hat unbiased for theta over random source blocks (in general E(T/N) differs from sum_g E T_g '
                         '/ sum_g E M_g); the sampled mean is not relabelled as theta'),
            weighting='pooled eligible-prefix weights; no equalization of the 103 sampled tasks and no inverse '
                      'per-task sample-size weights (weighting decision)',
            not_substituted='the 42-task equal-weighted frame is exploratory and not used'),
        sources=src,
        evidence_table_crosscheck=OrderedDict(
            source_frame_counts_equal=[evidence['source_frame'][k] for k in (
                'n_fixed_task_blocks', 'tasks_with_eligible_prefix', 'tasks_with_no_eligible_prefix',
                'n_eligible_prefixes', 'tasks_with_sampled_prefix', 'tasks_eligible_but_unsampled')] == [
                len(confirm_tasks), len(elig_per_task), len(confirm_tasks) - len(elig_per_task), n_elig,
                len(samp_per_task), len(elig_per_task) - len(samp_per_task)],
            prefixes_per_task_distribution_equal={int(k): v for k, v in evidence['source_blocks'][
                'prefixes_per_task_distribution'].items()} == dict(Counter(samp_per_task.values())),
            fresh_pair_discordance_equal=(evidence['fresh_pairs']['discordant'] == agree['disagree'] and all(
                evidence['fresh_pairs']['by_arm'][arm]['discordant'] == disagree_by_arm[arm] for arm in P_ARMS)),
            recovery_counts_equal=(evidence['recovery']['continuations_by_invocation'] ==
                                   {k: len(v) for k, v in ro.items()} and
                                   evidence['recovery']['prefixes_spanning_two_invocations'] == prefix_inv_class['spanning']
                                   and evidence['recovery']['prefixes_only_original_invocation'] ==
                                   prefix_inv_class['lost_only'] and
                                   evidence['recovery']['prefixes_only_recovery_invocation'] ==
                                   prefix_inv_class['recovery_only'])),
        reconciliation=OrderedDict(
            confirm_tasks=len(confirm_tasks), confirm_log_episodes=len(confirm_log),
            episodes_per_task=sorted(Counter(per_task_episodes.values()).items()),
            eligible_prefixes=n_elig, eligible_tasks=len(elig_per_task),
            sampled_prefixes=len(sampled), sampled_tasks=len(samp_per_task),
            branch_continuations=len(branch), continuations_per_prefix=sorted(Counter(
                len(a['small']) + len(a['large']) for a in est['runs'].values()).items()),
            tasks_without_eligible_prefix=len(confirm_tasks) - len(elig_per_task),
            tasks_with_eligible_but_no_sampled_prefix=len(elig_per_task) - len(samp_per_task),
            sampled_prefixes_per_task=sorted(Counter(samp_per_task.values()).items()),
            eligible_prefixes_per_task=sorted(Counter(elig_per_task.values()).items()),
            zero_arm_counts=zero_arm),
        point_estimates=OrderedDict(B=est['B'], v1=est['v'][1], v0=est['v'][0], log_contrast=est['L'],
                                    delta=est['delta'], U_1=est['Y'][1], D_1=est['Z'][1], U_0=est['Y'][0],
                                    D_0=est['Z'][0], sum_lead_derivative=math.fsum(est['U'].values()),
                                    lead_audit=OrderedDict(B=lead_audit['full_prefix_branch_mean'],
                                                           log_contrast=lead_audit['global_hajek_log_mean'],
                                                           delta=lead_audit['full_original_difference'])),
        design=OrderedDict(
            stage1_source_blocks=OrderedDict(
                description='per CONFIRM task, 8 randomized-log episodes. Decision 0: design.py draws, per task in '
                            'sorted uid order from one default_rng(design_seed) stream, block = [0,1]*4 permuted by '
                            'rng.shuffle and sets u_0 = 0.25 if block[r] = 1 else 0.75, so a_0 = 1{u_0 < 0.5} = '
                            'block[r]. Decisions t >= 1: a_t = 1{u_t < p_large} with the frozen design uniforms u_t '
                            'and p_large = 0.5',
                a0_law='within a task, a uniform random arrangement of four 0s and four 1s (70 equally likely '
                       'arrangements), independent across tasks under the idealized generator: P(a_0 = 1) = 1/2; for '
                       'two episodes of one task, P(same a_0) = 3/7 and P(both large) = P(both small) = 3/14',
                a0_same_probability=3 / 7, a0_both_large_probability=3 / 14,
                a0_block_patterns=[[list(k), v] for k, v in block_patterns.items()],
                a0_realized_equals_block=a0_realized_equals_block,
                u0_by_block=[[list(k), v] for k, v in sorted(u0_by_block.items())],
                decisions_checked_all_t=draws_checked, decisions_checked_t_ge_1=later_checked,
                decisions_mismatching_design_uniform=draws_bad,
                p_large_values=[[k, v] for k, v in p_values.items()],
                decision_sources=[[list(k), v] for k, v in sorted(sources_of_draw.items())],
                design_seed=design['design_seed'], horizon=design['horizon'], p_large=design['p_large'],
                design_created_utc=design['created_utc'], design_code_sha256=design['design_code_sha256'],
                eligibility=OrderedDict(
                    rule='a prefix is eligible iff its first candidate failed the frozen visible validation (the '
                         'episode then makes >= 2 decisions); hidden-test correctness of the first candidate is '
                         'irrelevant to eligibility',
                    eligible_vs_first_visible_pass=[[list(k), v] for k, v in sorted(elig_vs_visible.items())],
                    eligible_with_hidden_correct_first_candidate=sum(e['success_first_candidate'] for e in eligible),
                    n_decisions_by_stop_reason=[[list(k), v] for k, v in sorted(stop_table.items())],
                    frame_by_a0=OrderedDict(small=elig_by_a0[0], large=elig_by_a0[1]),
                    sample_by_a0=OrderedDict(small=samp_by_a0[0], large=samp_by_a0[1]),
                    decomposition='M_g = M_g(a_0 = small) + M_g(a_0 = large), each between 0 and 4 (task ledger '
                                  'columns); eligibility depends on a_0, so the frame is outcome- and design-dependent '
                                  'and N is random under stage 1',
                    max_M_g_by_a0=max(elig_per_task_a0.values())),
                schedule=OrderedDict(
                    log_invocations=[[list(k), v] for k, v in sorted(log_inv.items())],
                    start_utc=OrderedDict((k, [min(v), max(v)]) for k, v in sorted(starts.items())),
                    order='one invocation ran the TRAIN and CONFIRM episodes interleaved in the design run_order (a '
                          'random permutation of all log episodes), with 4 concurrent workers on shared servers',
                    run_order_is_permutation=sorted(log_run_order) == list(range(len(log_rows))),
                    confirm_by_run_order_decile=[decile[(k, 'confirm')] for k in range(10)],
                    train_by_run_order_decile=[decile[(k, 'train')] for k in range(10)],
                    errors=sum(bool(r.get('error')) for r in log_rows),
                    attempts=sorted(Counter(r['attempt'] for r in log_rows).items()))),
            stage2_prefix_sample=OrderedDict(
                mechanism='given the complete realized frame F (N eligible prefixes sorted by episode id), a simple '
                          'random sample without replacement of fixed size n = min(200, N) (run.py: numpy '
                          'default_rng(branch_audit.seed).choice(N, n, replace=False)); pi and pi_pair are conditional '
                          'on F',
                N=n_elig, n=n_samp, n_rule_min_200_N=min(200, n_elig), pi=n_samp / n_elig,
                pi_pair=n_samp * (n_samp - 1) / (n_elig * (n_elig - 1)),
                seed=design['branch_audit']['seed'],
                precommitment_checks=precommit,
                seed_precommitment='branch_audit.seed is drawn by design.py and stored in design.json (created '
                                   '%s), committed in the design freeze %s before the first log episode started (%s)'
                                   % (design['created_utc'], DESIGN_FREEZE_COMMIT[:7], min(starts['confirm'])),
                plan_sampling_probability=plan['sampling_probability'], plan_n_eligible=plan['n_eligible_prefixes'],
                plan_log_sha256_equals_log=plan['log_sha256'] == src['log_episodes']['sha256'],
                plan_created_utc=plan['created_utc'],
                plan_invocation=OrderedDict(invocation=manifest[0]['invocation'], started_utc=manifest[0]['started_utc'],
                                            git_head=manifest[0]['git_head'], code_sha256=manifest[0]['code_sha256'],
                                            n_todo=manifest[0]['n_todo']),
                reproduction=OrderedDict(numpy=numpy_version, equal_to_frozen_plan=reproduction_equal,
                                         fields_compared=list(keys), n_episodes=len(reproduced)),
                a6_branch_plan_reproduction=OrderedDict(
                    (k, mechanism[k]) for k in ('redrawn_equals_frozen_plan', 'plan_log_sha256_matches_current_log',
                                                'plan_created_not_after_first_start', 'design_freeze_commit')),
                a6_git_order_note=mechanism['git_order_note'],
                task_stratification='none (the frame is the pooled list of eligible prefixes); per-task sample '
                                    'sizes are random'),
            stage3_continuations=OrderedDict(
                description='per sampled prefix and arm (small, large), 2 fresh continuations from the restored '
                            'first-failure state at fork_t = 1, each staying on the forced arm, each with its own '
                            'frozen seed drawn from the plan generator after the prefix sample',
                continuations_per_arm=design['branch_audit']['continuations_per_arm'],
                fork_t=sorted(Counter(r['fork_t'] for r in branch).items()),
                decisions_per_continuation=sorted(decisions_per_continuation.items()),
                decoding=OrderedDict(temperature=config['temperature'], top_p=config['top_p'],
                                     max_tokens=config['max_tokens']),
                model_call_seed='continuation seed + 101 * t (agent.py run_episode: m.chat(convo, ep[seed] + 101 * t))',
                branch_seeds_distinct=len(set(branch_seeds)),
                branch_seeds_shared_with_log_or_live_design_seeds=len(set(branch_seeds) & set(source_seeds)),
                branch_model_call_seeds_shared_with_log_or_live=len(branch_call_seeds & source_call_seeds),
                replicate_pairing='the replicate index j pairs small#j with large#j by label only; the two arms have '
                                  'distinct seeds, which does not by itself make their executions independent (the '
                                  'pair version of the bound permits within-pair dependence)',
                prefixes_with_adjacent_plan_run_orders=adjacent,
                start_spread_seconds_within_prefix=OrderedDict(n=len(spread), median=spread[(len(spread) - 1) // 2],
                                                               max=spread[-1]),
                concurrency_reading='the 4 continuations of every prefix occupy adjacent plan run orders; for the 198 '
                                    'prefixes run in one invocation they started nearly together on the 4 workers, so '
                                    'a time-local execution shock would reach all replicates of such a prefix',
                replicate_pairs_with_a_shared_seed=arm_seed_shared,
                replicate_agreement=dict(sorted(agree.items())),
                replicate_disagreement_by_arm=OrderedDict((arm, disagree_by_arm[arm]) for arm in P_ARMS),
                replicate_agreement_reading='the two replicates of an arm use distinct seeds, so their disagreement '
                                            'reflects sampling variation (and possibly shared execution shocks), not '
                                            'evidence about seed determinism',
                restoration=OrderedDict(
                    recorded_flags_all_true=all_restoration_true,
                    recheck_recomputed_transcript_hash_matches=recheck['recomputed_transcript_hash_matches'],
                    recheck_branch_episodes_checked=recheck['branch_episodes_checked'],
                    recheck_disagreements=recheck['disagreements'],
                    recheck_stored_tool_result_reproduced=recheck['stored_tool_result_reproduced'],
                    recheck_source_binding_matches=recheck_binding,
                    reading='the transcript hash of the restored state was recomputed from the frozen task file, '
                            'certified visible tests and the parent record (800/800); tool_result_reproduced is a '
                            'stored flag, not independently recomputed')),
            clustering=OrderedDict(
                unit='source task (330 CONFIRM tasks); each task block carries its 8 episodes, their eligible '
                     'prefixes, the sampled continuations and the log weights',
                note='prefixes of one task share the task and the stage-1 first-decision arrangement; the stage-2 '
                     'sample is global (not stratified by task)'),
            shared_records=OrderedDict(
                description='every sampled prefix is also an eligible log episode, so the same prefix state enters '
                            'B_hat (through its fresh continuations) and nu_hat (through the logger\'s own continuation '
                            'with its recorded weight): the branch and log estimators share records within prefixes '
                            'and tasks, so the branch-log cross terms must be kept',
                sampled_prefixes_also_in_log_estimator=len(sampled),
                sampled_prefixes_by_log_arm_and_nonzero_weight=[[list(k), v] for k, v in sorted(shared_nonzero.items())]),
            provenance=OrderedDict(
                invocations=inv_order, lost_invocation=lost, recovery_invocation=rec,
                retained_from_lost_invocation=len(ro[lost]), retained_from_recovery=len(ro[rec]),
                lost_invocation_run_orders_missing_inside_its_range=gap_in_lost_range,
                retention_reading='the lost invocation dispatched the plan in run_order with 4 workers; the retained '
                                  'records are those whose episode records had been written when the snapshot was '
                                  'captured, a completion-time cutoff (not a designed split); see retention_window',
                benchmark_by_invocation=[[list(k), v] for k, v in sorted(bench_inv.items())],
                prefixes_spanning_invocations=spanning,
                prefixes_by_invocation_class=OrderedDict((k, prefix_inv_class[k]) for k in
                                                         ('lost_only', 'recovery_only', 'spanning')),
                plan_order_sorted_by_parent=plan_order_sorted_by_parent, plan_order_task_contiguous=task_contiguous,
                attempt_values=sorted(Counter(r['attempt'] for r in branch).items()),
                attempt_number_reused=recovery['attempt_number_reused'],
                durable_decision_rows=len(bdec),
                durable_rows_by_invocation=dict(sorted(Counter(r['invocation'] for r in bdec).items())),
                durable_rows_matching_the_retained_invocation=len(bdec) - len(durable_nonmatching),
                durable_rows_not_matching=durable_nonmatching,
                continuations_with_lost_invocation_durable_rows=durable_lost_ids,
                recovery_ledger_episode_ids=recovery_ids,
                durable_row_reading='these 4 continuations had started but not finished when the snapshot was '
                                    'captured, so only their pre-call decision rows survived (5 rows, t = 1 or 2); the '
                                    'recovery invocation re-executed them with the same seeds; the rows are partial path '
                                    'information about lost executions, not outcomes',
                recovery_ledger_total_durable_rows=recovery['total_rows'],
                execution_flags_foreign_gpu_contention=[[list(k), v] for k, v in sorted(exec_flags.items())],
                execution_flags_reading='the runner flags only another llama-server on a non-study port reporting a '
                                        'busy slot, sampled once at each episode start (all invocations ran with '
                                        '--allow-contention); other GPU workloads and mid-episode load are not '
                                        'observed',
                same_seed_repeat_reading='the durable pre-call rows of 46#3:small#1 at t = 2 hash the same-seed t = 1 '
                                         'reply of the lost execution and equal the recovery hash, so one same-seed '
                                         'call repeated identically; it is non-discriminating (that prefix gives the '
                                         'same t = 1 reply under distinct seeds and both models), and t = 1 pre-call '
                                         'hashes only confirm the restored prefix',
                retention_window=retention,
                lost_outcomes='the original outcomes of the 665 re-run continuations are not in the committed records '
                              '(protocol section 11)',
                recovery_assumption='the recovery re-execution follows the same continuation law as the lost one; its '
                                    'effect, if any, is aliased with benchmark (all 592 MBPP continuations are from the '
                                    'recovery invocation) and with task order')),
        identification=OrderedDict(
            components=[
                OrderedDict(component='stage 1: first-decision arrangement and later-decision assignment',
                            status='IDENTIFIED (design mechanism)',
                            evidence='design.py block bound to git at the freeze, log, plan and HEAD commits; 330/330 '
                                     'tasks with a 4/4 arrangement; realized a_0 equals the block in 2640/2640 episodes; '
                                     'a_t = 1{u_t < 0.5} with the design uniform in %d/%d decisions (%d with t >= 1)'
                                     % (draws_checked - draws_bad, draws_checked, later_checked)),
                OrderedDict(component='stage 1: per-task law of the complete source block (outcomes, M_g, T_g, '
                                      'U_ga, D_ga)',
                            status='NOT IDENTIFIED (one realization per task, even under assumptions 1-3)',
                            evidence='assumption 1 of the target note allows independent blocks with non-identical '
                                     'laws; with one block per task the variance of sum_g (T_g - theta M_g), and the '
                                     'branch-log covariance, are not identified; between-task spread estimates that '
                                     'variance plus the spread of the centred task means, so it is conservative only; '
                                     'the range-based bounds of the target note (sec. 3) need only the recorded ranges'),
                OrderedDict(component='stage 1: independence of complete source-task blocks across the 330 tasks',
                            status='ASSUMED (a6: %s)' % a6_status('independent complete source-task blocks'),
                            evidence='one log invocation at one commit and code hash, TRAIN and CONFIRM interleaved in a '
                                     'random order; the runner\'s foreign-server check (narrow; see provenance) was '
                                     'negative in all 5288 log and branch records; shared execution-period or server '
                                     'effects are not observable'),
                OrderedDict(component='stage 2: SRSWOR prefix selection given F',
                            status='IDENTIFIED (mechanism, reproduced); selection independent of fresh continuation '
                                   'noise ASSUMED',
                            evidence='exact redraw from the pre-committed seed and git-bound plan code; pi = n/N and '
                                     'pi_pair conditional on F'),
                OrderedDict(component='stage 3: replicate pairs (2 per arm, distinct seeds, fork_t = 1)',
                            status='OBSERVED (design); conditional independence across prefixes and replicate indices '
                                   'and a selection-invariant continuation law ASSUMED (a6: %s); within-pair arm '
                                   'dependence PERMITTED by the pair version'
                                   % a6_status('selection-invariant fresh replicate pairs'),
                            evidence='plan seeds, disjoint from all log/live seeds; the 4 continuations of every prefix '
                                     'occupy adjacent plan run orders, and for the %d prefixes run in one invocation '
                                     'they started nearly together (median %d s, max %d s apart), so a time-local shock '
                                     'would reach all replicates of such a prefix'
                                     % (len(spread), spread[(len(spread) - 1) // 2], spread[-1])),
                OrderedDict(component='stage 3: no execution shocks shared across prefixes',
                            status='ASSUMED (a6: %s)' % a6_status('(same) no execution shocks'),
                            evidence='the plan order is deterministic and task-contiguous, so time or server drift is '
                                     'aliased with task order'),
                OrderedDict(component='restored prefix state',
                            status='OBSERVED for the transcript hash; tool-result reproduction ASSUMED (stored flag)',
                            evidence='restoration_recheck.json: 800/800 recomputed transcript hashes, its source '
                                     'binding matching the current records'),
                OrderedDict(component='branch-log cross terms (shared records)',
                            status='OBSERVED (record map); the covariance itself is part of the per-task block law',
                            evidence='prefix and task ledgers carry both sides for every task'),
                OrderedDict(component='retention of lost-invocation records at the completion-time cutoff',
                            status='ASSUMED: retention independent of the potential outcomes (lost and recovered) of '
                                   'every continuation started before the snapshot capture',
                            evidence='episode records were written only on completion; the retained set equals the %s '
                                     'snapshot; %d continuations (run orders %d-%d) started within the start-to-record '
                                     'bound (%.1f s: longest observed agent loop plus the hidden-test wall limit and '
                                     'kill wait) of the capture: at most %s on B_hat if no potential start-to-record '
                                     'time exceeded this empirical bound and start times do not depend on a '
                                     'continuation\'s own outcome, otherwise only the trivial %d/400'
                                     % (PLAN_COMMIT[:7], len(at_risk), at_risk[0], at_risk[-1], bound,
                                        retention['max_effect_on_B_hat_if_start_to_record_within_bound'],
                                        len(lost_start))),
                OrderedDict(component='recovery / invocation effect on the 665 re-executed continuations',
                            status='NOT IDENTIFIED (a6: %s)' % a6_status('(same) lost and recovered'),
                            evidence='lost outcomes unavailable; aliased with benchmark and task order; 4 '
                                     'continuations carry lost-invocation pre-call rows only'),
                OrderedDict(component='seed-conditional determinism of the serving stack',
                            status='NOT INFORMATIVELY OBSERVED (matters only for the same-seed recovery re-execution)',
                            evidence='one hash-level same-seed repeat (46#3:small#1, the t = 1 call) agrees but is '
                                     'non-discriminating; determinism is not established'),
                OrderedDict(component='positive population denominators of eq. (2)',
                            status='IMPLIED (observed N = %d, D_1 = %s, D_0 = %s with nonnegative summands)'
                                   % (n_elig, est['Z'][1], est['Z'][0]),
                            evidence='the only standing assumption of eq. (2)')],
            acceptance=('(a) Complete under declared assumptions: for the eq. (2) target the ledger records every input '
                        'of the eq. (3) estimators and of the task-block sums used by the target note\'s bounds (M_g, '
                        'also by a_0; m_g; A_g; U_ga; D_ga) for all 330 tasks, the exact stage-2 inclusion '
                        'probabilities given F, the replicate and concurrency structure, and the shared-record map. The '
                        'declared assumptions are: assumptions 1-3 of the target note; selection independent of fresh '
                        'continuation noise; recovery-law invariance; retention independent of the potential outcomes '
                        'of the continuations started before the snapshot capture; tool-result reproduction as stored. Under them the lead can derive a same-target, '
                        'design-aware bound or conservative variance. (b) Not identified: the per-task block laws, hence '
                        'the exact variance of the task totals and the branch-log covariance (between-task spread is '
                        'conservative only); the recovery/invocation effect; seed-conditional determinism. The ASSUMED '
                        'rows are assumptions, not checks. No standard error or interval is asserted here.')),
        lead_derivative=OrderedDict(
            name='lead_derivative_U_g (docs/theory_feedback_20260920_branch.md)',
            formula='(A_g - B m_g)/m - (U_g1 - v_1 D_g1)/D_1 + (U_g0 - v_0 D_g0)/D_0',
            label='the derivative of the pooled contrast under common task weights 1 + eps h_g, an algebraic identity; '
                  'a6 labels sqrt(sum_g U_g^2) an exploratory algebraic scale, not a consistent SE. It is not an eq. (2) '
                  'influence function: it treats the realized frame, the 200 sampled prefixes and their replicates as '
                  'fixed, so it ignores the randomness of the source frame, the SRSWOR dependence among sampled '
                  'prefixes and the replicate structure (given F, m_g/m is the Horvitz-Thompson estimate of M_g/N)',
            sqrt_sum_sq=math.sqrt(math.fsum(u * u for u in est['U'].values())),
            equals_a6_uncertainty_value=abs(math.sqrt(math.fsum(u * u for u in est['U'].values())) -
                                            a6_uncertainty) <= 1e-12),
        outputs=OrderedDict(prefix_ledger=OUT_REL + '/prefix_ledger.csv', task_ledger=OUT_REL + '/task_ledger.csv',
                            continuation_ledger=OUT_REL + '/continuation_ledger.csv'),
        not_done=['no standard error, interval or bootstrap', 'no 42-task substitution', 'no model/browser inference',
                  'no Monte Carlo', 'no archive change'])
    ledger['design']['code_binding'] = code_binding(root)
    record_cfg = {r['config_sha256'] for r in log_rows + branch + manifest} | {design['config_sha256']}
    record_code = {r['code_sha256'] for r in log_rows + branch + manifest} | {design['design_code_sha256']}
    here = sorted((root / 'experiments/code_routing').glob('*.py')) + sorted((root / 'experiments/common').glob('*.py'))
    ledger['design']['code_binding']['frozen_record_bindings'] = OrderedDict(
        config_sha256_in_records=sorted(record_cfg), code_sha256_in_records=sorted(record_code),
        config_file_equals_records=record_cfg == {src['config']['sha256']},
        working_tree_code_sha256_equals_records=record_code == {
            hashlib.sha256(b''.join(f.read_bytes() for f in here)).hexdigest()})

    # ---- CSV ledgers
    prefix_rows = []
    for e in eligible:
        arm, w = log_weight(e)
        ds, dl = e['decisions'], design_log[e['episode_id']]
        r = OrderedDict(prefix_episode_id=e['episode_id'], task_uid=e['task_uid'], benchmark=e['benchmark'],
                        run=e['run'], log_run_order=dl['run_order'], log_start_utc=e['start_utc'],
                        a0_block=dl['a0_block'], a0_realized=ds[0]['a'], u0=dl['u'][0],
                        first_visible_passed=int(ds[0]['validation']['passed']),
                        first_hidden_success=e['success_first_candidate'], n_decisions=e['n_decisions'],
                        stop_reason=e['stop_reason'], a_t1=ds[1]['a'], u_t1=dl['u'][1], p_large_t1=ds[1]['p_large'],
                        a_t2=ds[2]['a'] if len(ds) > 2 else '', u_t2=dl['u'][2] if len(ds) > 2 else '',
                        p_large_t2=ds[2]['p_large'] if len(ds) > 2 else '', log_success=e['success'],
                        W_i1=w if arm == 1 else 0.0, W_i0=w if arm == 0 else 0.0,
                        sampled=int(e['episode_id'] in sampled_set),
                        inclusion_probability=n_samp / n_elig)
        if e['episode_id'] in sampled_set:
            runs = est['runs'][e['episode_id']]
            r.update(branch_small_runs=json.dumps(runs['small']), branch_large_runs=json.dumps(runs['large']),
                     prefix_contrast_D=est['D'][e['episode_id']],
                     invocation_small='|'.join(sorted(arm_inv[e['episode_id']]['small'])),
                     invocation_large='|'.join(sorted(arm_inv[e['episode_id']]['large'])))
        else:
            r.update(branch_small_runs='', branch_large_runs='', prefix_contrast_D='', invocation_small='',
                     invocation_large='')
        prefix_rows.append(r)
    task_rows = []
    for t in confirm_tasks:
        task_rows.append(OrderedDict(
            task_uid=t, benchmark=bench[t], log_episodes=per_task_episodes[t], M_g=elig_per_task[t],
            M_g_a0_small=elig_per_task_a0[(t, 0)], M_g_a0_large=elig_per_task_a0[(t, 1)], m_g=est['mg'][t],
            A_g=est['A'][t], U_g1=est['N'][t][1], D_g1=est['Dn'][t][1], U_g0=est['N'][t][0], D_g0=est['Dn'][t][0],
            lead_derivative_U_g=est['U'][t]))
    cont_rows = []
    for pe in plan_eps:
        r = by_ep[pe['episode_id']]
        cont_rows.append(OrderedDict(
            episode_id=pe['episode_id'], prefix_episode_id=pe['parent_episode_id'], task_uid=pe['task_uid'],
            benchmark=r['benchmark'], arm=P_ARMS[pe['forced_arm']], run=pe['run'], plan_run_order=pe['run_order'],
            seed=pe['seed'], model_call_seed_t1=pe['seed'] + 101, invocation=r['invocation'], attempt=r['attempt'],
            start_utc=r['start_utc'], fork_t=r['fork_t'], n_decisions=r['n_decisions'], success=r['success'],
            restoration_transcript_hash_matches=int(r['restoration']['transcript_hash_matches']),
            restoration_tool_result_reproduced_stored=int(r['restoration']['tool_result_reproduced']),
            durable_rows_lost_invocation=dec_rows[(pe['episode_id'], lost)],
            durable_rows_recovery_invocation=dec_rows[(pe['episode_id'], rec)]))
    return ledger, prefix_rows, task_rows, cont_rows


def _group(rows, key, val):
    g = defaultdict(list)
    for r in rows:
        g[key(r)].append(val(r))
    return g


def csv_text(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), lineterminator='\n')
    w.writeheader()
    for r in rows:
        w.writerow({k: (repr(v) if isinstance(v, float) else v) for k, v in r.items()})
    return buf.getvalue()


CSV_NAMES = ('prefix_ledger', 'task_ledger', 'continuation_ledger')


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0], allow_abbrev=False)
    ap.add_argument('--out', default=str(ROOT / OUT_REL))
    args = ap.parse_args(argv)
    out = Path(args.out)
    ledger, *tables = build()
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in zip(CSV_NAMES, tables):
        (out / (name + '.csv')).write_text(csv_text(rows))
        ledger['outputs'][name + '_sha256'] = sha(out / (name + '.csv'))
    (out / 'design_ledger.json').write_text(json.dumps(ledger, indent=1, default=str) + '\n')
    pe = ledger['point_estimates']
    print(json.dumps(OrderedDict(reconciliation=ledger['reconciliation'], B=pe['B'], log_contrast=pe['log_contrast'],
                                 delta=pe['delta'], reproduction=ledger['design']['stage2_prefix_sample']['reproduction'],
                                 code_binding_identical=[ledger['design']['code_binding']['plan_sampling_block_identical'],
                                                         ledger['design']['code_binding']['design_block_identical']]),
                     default=str))
    return 0


if __name__ == '__main__':
    sys.exit(main())
