"""DTR-REQ-006: retrospective DEVELOPMENT-only decision-opportunity table for the archived code-routing study.

Scope (worker, not scientific lead). Deterministic, read-only analysis of committed records. No model inference, no
server, no GPU, no network, no Monte Carlo. It reports counts, verified logged probabilities and the lead's predeclared
conclusion category; it fits no router and predicts no counterfactual success.

Inputs used for outcomes (and only these; lead request DTR-REQ-006, source commit f954e9e):
  results/code_routing/design.json (+ design.sha256)
  results/code_routing/log/{episodes,decisions}.jsonl     -> TRAIN-task records only
  results/code_routing/pilot/{episodes,decisions}.jsonl   -> pilot-task records
Context only (no outcome use): results/code_routing/learned_policy.json.
Never read: results/code_routing/live/, branch/, or any CONFIRM-task outcome. The randomized log covers TRAIN and
CONFIRM tasks by design (design.py builds log episodes for every non-pilot task); every log/decision record whose task
is in design.json confirm_tasks is dropped immediately after its task id is parsed, and only its count is reported.

Outputs (write-once, mode 'x'): <out>/decision_opportunity_table.json and <out>/REQ006_SUMMARY.md, with
<out> = results/code_routing/analysis/req006 by default. All recorded paths are repository-relative.

Usage:  .venv/bin/python experiments/v2_agent/analysis/req006_decision_opportunity.py [--out-dir DIR]
Standard library only, except numpy (optional) to re-derive the pilot's pre-drawn uniforms; without numpy that one
check is reported as "not checked". The committed outputs were generated with the repository .venv (numpy 2.5.3).
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import subprocess
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CR = 'results/code_routing'
SCRIPT_REL = 'experiments/v2_agent/analysis/req006_decision_opportunity.py'
DEFAULT_OUT = CR + '/analysis/req006'
SOURCE_COMMIT = 'f954e9e'
OUTCOME_INPUTS = ['design.json', 'design.sha256', 'log/episodes.jsonl', 'log/decisions.jsonl',
                  'pilot/episodes.jsonl', 'pilot/decisions.jsonl']
CONTEXT_INPUTS = ['learned_policy.json']
PILOT_RUNS = 4                      # run.py --pilot-runs default; checked against the records below
ACTIONS = ('small', 'large')

# Protocol constants (copied, not chosen here)
Z = 1.96                            # docs/experiment_protocol.md section 4.3
H_PROTOCOL = 0.05                   # half-width in the section 4.3 illustration
S2_ILLUSTRATIVE = 0.20              # "s_D^2 = 0.20 ... about 308 independent tasks"
S2_WORST = 1.0                      # "worst bound s_D^2 <= 1 gives about 1,537"
REACH2_FLAG = 0.50                  # docs/experiment_protocol_v2.md section 5: "<50% reaching decision 2" redesign flag

CONCLUSION_RULE = (
    "Rule R006-v1, fixed in this script before its first complete run over TRAIN outcomes; its thresholds are copied "
    "from existing protocol text, not chosen from these data. "
    "Step 0 (acceptance): INCONCLUSIVE if split IDs or episode/decision denominators fail to reconcile with design.json, "
    "if any reported probability or action fails to match decisions.jsonl, or if any CONFIRM-task record would enter "
    "the table. "
    "Step 1 (REPAIR): REPAIR if (1a) fewer than 50% of E2-relevant TRAIN log episodes (initial action small, the matched "
    "initial action of the primary history contrast; this subset has the higher occupancy, so using it is conservative "
    "against REPAIR) reach an eligible second decision, i.e. the '<50% reaching decision 2' development redesign flag of "
    "docs/experiment_protocol_v2.md section 5 fires; or (1b) the model-free disagreement upper bound is negligible: zero "
    "supported E2-relevant second/third decisions lie in prompt cells whose history takes more than one value. "
    "Step 2 (PROCEED): PROCEED only if Step 1 does not fire AND both same-class depth-two candidate rules have been "
    "trained on TRAIN/DEV AND they disagree at a supported common observed history in at least one TRAIN task AND a "
    "task-level precision plan at the protocol's stated half-width (0.05) is feasible within an available untouched task "
    "pool. "
    "Step 3: otherwise INCONCLUSIVE (in particular when Step 1 does not fire but the candidate rules are untrained, so "
    "realized disagreement is unknown). "
    "A model-free upper bound can establish sparsity but never sufficiency, so an untrained pair can yield REPAIR or "
    "INCONCLUSIVE, never PROCEED."
)
RULE_DISCLOSURE = (
    "Known to the worker before the rule was written: the pilot gate (results/code_routing/pilot/pilot_gate.md, "
    "P(t=1 eligible)=0.225), the CONFIRM-log occupancy already published in the A6 report (D-logger-occupancy, 564 of "
    "2640 reach a second decision), and, from a record-integrity pass over the TRAIN log made before this script existed, "
    "the TRAIN distribution of decisions per episode (1531 one, 81 two, 236 three of 1848). The 50% threshold is the v2 "
    "protocol's, written on 21 September 2026, before DTR-REQ-006."
)


# ------------------------------------------------------------------ helpers
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'), ensure_ascii=True)


def ids_hash(ids) -> str:
    return sha256_bytes(canonical(sorted(ids)).encode())


def task_of(episode_id: str) -> str:
    """'log:mbpp/441#0' -> 'mbpp/441'; 'pilot:humaneval/112#3' -> 'humaneval/112'."""
    return episode_id.split(':', 1)[1].rsplit('#', 1)[0]


def family_of(task_uid: str) -> str:
    return task_uid.split('/', 1)[0]


def frac_bin(ff: float) -> str:
    return 'all_checks_failed' if ff == 1.0 else 'partial'


def read_lines(rel: str):
    with open(REPO / rel, 'r') as f:
        for i, line in enumerate(f, 1):
            if line.strip():
                yield i, line


def rate(k, n):
    return None if not n else k / n


def git_blob_sha256(rel: str):
    try:
        out = subprocess.run(['git', '-C', str(REPO), 'show', '%s:%s' % (SOURCE_COMMIT, rel)], capture_output=True, timeout=120)
        return sha256_bytes(out.stdout) if out.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


# ------------------------------------------------------------------ loading with CONFIRM exclusion
def load_partition(part: str, confirm: set):
    """Episode and decision records of one stage directory, with every CONFIRM-task record dropped as soon as its task
    id is parsed (its outcome fields are never used)."""
    eps, n_conf_eps, conf_eps_ids = [], 0, set()
    for _, line in read_lines('%s/%s/episodes.jsonl' % (CR, part)):
        r = json.loads(line)
        if r['task_uid'] in confirm or task_of(r['episode_id']) in confirm:
            n_conf_eps += 1; conf_eps_ids.add(r['episode_id']); continue
        eps.append(r)
    decs, n_conf_decs = [], 0
    for _, line in read_lines('%s/%s/decisions.jsonl' % (CR, part)):
        r = json.loads(line)
        if task_of(r['episode_id']) in confirm:
            n_conf_decs += 1; continue
        decs.append(r)
    return eps, decs, dict(confirm_episode_records_excluded=n_conf_eps, confirm_episode_ids_excluded=len(conf_eps_ids),
                           confirm_decision_records_excluded=n_conf_decs)


def pilot_draws(design: dict):
    """Re-derive the pilot's pre-drawn uniforms exactly as experiments/code_routing/run.py --stage pilot does."""
    try:
        import numpy as np
    except ImportError:
        return None, None
    rng = np.random.default_rng(design['design_seed'] + 1)
    out = {}
    for u in design['pilot_tasks']:
        for r in range(PILOT_RUNS):
            us = rng.random(design['horizon']).tolist(); seed = int(rng.integers(1, 2**31 - 1))
            out['pilot:%s#%d' % (u, r)] = dict(u=us, seed=seed)
    return out, np.__version__


# ------------------------------------------------------------------ main analysis
def analyse():
    notes = []
    # ---------- inputs and provenance
    inputs = OrderedDict()
    for rel in OUTCOME_INPUTS + CONTEXT_INPUTS:
        p = REPO / CR / rel; raw = p.read_bytes()
        blob = git_blob_sha256('%s/%s' % (CR, rel))
        inputs['%s/%s' % (CR, rel)] = dict(sha256=sha256_bytes(raw), bytes=len(raw), lines=raw.count(b'\n'),
                                           use='outcomes' if rel in OUTCOME_INPUTS else 'context only (no outcomes)',
                                           equals_blob_at_source_commit=(None if blob is None else blob == sha256_bytes(raw)))
    design_raw = (REPO / CR / 'design.json').read_bytes()
    design = json.loads(design_raw)
    design_sha_ok = sha256_bytes(design_raw) == (REPO / CR / 'design.sha256').read_text().strip()

    pilot, train, confirm = set(design['pilot_tasks']), set(design['train_tasks']), set(design['confirm_tasks'])
    all_tasks = pilot | train | confirm
    K = int(design['horizon'])

    # ---------- 1. split reconciliation
    fam = lambda S: dict(sorted(Counter(family_of(u) for u in S).items()))
    design_log = design['log_episodes']
    design_log_split_mismatch = sum(1 for e in design_log if (e['split'] == 'train') != (e['task_uid'] in train)
                                    or (e['split'] == 'confirm') != (e['task_uid'] in confirm))
    design_log_train = {e['episode_id']: e for e in design_log if e['task_uid'] in train}
    runs_per_task = Counter(e['task_uid'] for e in design_log)
    a0_block_balance = Counter()
    for u in train:
        blk = [e['a0_block'] for e in design_log if e['task_uid'] == u]
        a0_block_balance['%d_large_of_%d' % (sum(blk), len(blk))] += 1

    split = OrderedDict(
        design_sha256=sha256_bytes(design_raw), design_sha256_matches_design_sha256_file=design_sha_ok,
        design_seed=design['design_seed'], horizon=K, p_large_design=design['p_large'],
        tasks_sha256_frozen=design['tasks_sha256'],
        counts=OrderedDict(pilot=len(pilot), train=len(train), confirm=len(confirm), union=len(all_tasks)),
        pairwise_disjoint=(not (pilot & train) and not (pilot & confirm) and not (train & confirm)),
        ids_sha256=OrderedDict(pilot=ids_hash(pilot), train=ids_hash(train), confirm=ids_hash(confirm)),
        ids_sha256_definition='sha256 of the canonical JSON (sorted keys, separators "," ":", ASCII) of the sorted task-id list',
        family_definition=('family = benchmark, the prefix of the task id before "/" (mbpp or humaneval); it equals the '
                           'episode "benchmark" field and state.x_humaneval (checked below). No near-duplicate or variant '
                           'grouping is recorded in the committed inputs, so each task id is its own independent '
                           'cluster; the two benchmarks are strata, too few to serve as inference clusters.'),
        family_counts=OrderedDict(pilot=fam(pilot), train=fam(train), confirm=fam(confirm)),
        design_log_episodes=OrderedDict(total=len(design_log), train=sum(e['task_uid'] in train for e in design_log),
                                        confirm=sum(e['task_uid'] in confirm for e in design_log),
                                        split_field_disagreements_with_task_lists=design_log_split_mismatch,
                                        runs_per_task=dict(Counter(runs_per_task.values())),
                                        train_a0_block_balance=dict(a0_block_balance)),
    )

    # ---------- load, excluding CONFIRM
    parts = OrderedDict()
    for part in ('log', 'pilot'):
        eps, decs, excl = load_partition(part, confirm)
        parts[part] = dict(eps=eps, decs=decs, excl=excl)
    pd, np_version = pilot_draws(design)

    recon = OrderedDict()
    split_of_task = {**{u: 'train' for u in train}, **{u: 'pilot' for u in pilot}}
    for part, P in parts.items():
        eps, decs = P['eps'], P['decs']
        by_split = Counter(split_of_task.get(r['task_uid'], 'NOT_IN_DESIGN') for r in eps)
        field_disagree = [r['episode_id'] for r in eps if r.get('split') != split_of_task.get(r['task_uid'])]
        bench_disagree = [r['episode_id'] for r in eps if r.get('benchmark') != family_of(r['task_uid'])]
        eid_task_disagree = [r['episode_id'] for r in eps if task_of(r['episode_id']) != r['task_uid']]
        ids = [r['episode_id'] for r in eps]
        if part == 'log':
            expected = set(design_log_train)
        else:
            expected = {'pilot:%s#%d' % (u, r) for u in pilot for r in range(PILOT_RUNS)}
        recon[part] = OrderedDict(
            episode_records_kept=len(eps), decision_records_kept=len(decs), **P['excl'],
            kept_episodes_by_design_split=dict(by_split),
            episode_split_field_disagreements=len(field_disagree), benchmark_field_disagreements=len(bench_disagree),
            episode_id_task_disagreements=len(eid_task_disagree),
            duplicate_episode_ids=len(ids) - len(set(ids)),
            expected_episode_ids=len(expected), missing_expected=len(expected - set(ids)), unexpected=len(set(ids) - expected),
            error_records=sum(bool(r.get('error')) for r in eps),
            attempts=dict(Counter(r.get('attempt') for r in eps)),
            independent_tasks=len({r['task_uid'] for r in eps}),
            independent_tasks_by_family=dict(sorted(Counter(family_of(u) for u in {r['task_uid'] for r in eps}).items())),
            ids_sha256_of_tasks_present=ids_hash({r['task_uid'] for r in eps}),
        )
    recon['log']['tasks_present_equal_design_train'] = {r['task_uid'] for r in parts['log']['eps']} == train
    recon['pilot']['tasks_present_equal_design_pilot'] = {r['task_uid'] for r in parts['pilot']['eps']} == pilot
    split['episode_mapping'] = recon

    # ---------- 2. decisions: verify against decisions.jsonl, design draws and state derivation
    ver = OrderedDict(); rows = []; per_task = {}
    CMP = ('t', 'eligible', 'available_actions', 'state', 'a', 'action', 'p_large', 'b_obs', 'draw', 'source', 'penalty',
           'transcript_sha256')
    for part, P in parts.items():
        sp = 'train' if part == 'log' else 'pilot'
        dmap, dup = {}, 0
        for d in P['decs']:
            k = (d['episode_id'], d['attempt'], d['t'])
            dup += k in dmap; dmap[k] = d
        used = set(); c = Counter()
        for e in sorted(P['eps'], key=lambda r: r['episode_id']):
            if e.get('error'):
                continue
            eid, att = e['episode_id'], e['attempt']
            decs = e['decisions']
            c['episodes'] += 1
            c['n_decisions_field_mismatch'] += int(e['n_decisions'] != len(decs))
            c['actions_field_mismatch'] += int(e['actions'] != [d['action'] for d in decs])
            last_val = decs[-1]['validation'] if decs else None
            c['stop_reason_mismatch'] += int(e['stop_reason'] != ('validated' if last_val and last_val['passed'] else 'horizon'))
            for i, d in enumerate(decs):
                c['decisions'] += 1
                j = dmap.get((eid, att, d['t']))
                if j is None:
                    c['missing_in_decisions_jsonl'] += 1; continue
                used.add((eid, att, d['t']))
                c['field_mismatch_vs_decisions_jsonl'] += int(any(j[k] != d[k] for k in CMP))
                p, a = j['p_large'], j['a']
                c['t_index_mismatch'] += int(j['t'] != i or j['state']['t'] != i)
                c['action_code_mismatch'] += int(ACTIONS[a] != j['action'])
                c['b_obs_identity_mismatch'] += int(abs(j['b_obs'] - (p if a == 1 else 1 - p)) > 1e-15)
                c['action_not_threshold_of_draw'] += int(a != int(j['draw'] < p))
                if part == 'log':
                    de = design_log_train.get(eid)
                    c['draw_not_design_u'] += int(de is None or j['draw'] != de['u'][i])
                    if i == 0:
                        c['a0_not_design_block'] += int(de is None or a != de['a0_block'])
                    c['seed_not_design'] += int(i == 0 and (de is None or e['seed'] != de['seed']))
                elif pd is not None:
                    c['draw_not_rederived_pilot_u'] += int(eid not in pd or j['draw'] != pd[eid]['u'][i])
                    c['seed_not_rederived_pilot'] += int(i == 0 and (eid not in pd or e['seed'] != pd[eid]['seed']))
                st = j['state']
                c['state_prev_actions_mismatch'] += int(st['prev_actions'] != [x['a'] for x in decs[:i]])
                c['state_x_humaneval_mismatch'] += int(st['x_humaneval'] != int(family_of(e['task_uid']) == 'humaneval'))
                if i == 0:
                    c['t0_state_not_start'] += int(st['fail_class'] != 'start' or st['frac_fail'] != 0.0)
                else:
                    pv = decs[i - 1]['validation']
                    c['decision_after_passed_validation'] += int(bool(pv['passed']))
                    c['state_feedback_not_previous_validation'] += int(st['fail_class'] != pv['fail_class'] or st['frac_fail'] != pv['frac_fail'])
                supported = (0.0 < p < 1.0) and set(j['available_actions']) == set(ACTIONS)
                a0 = decs[0]['a']
                rows.append([sp, eid, e['task_uid'], family_of(e['task_uid']), e['run'], j['t'], j['action'], p, j['b_obs'],
                             supported, ACTIONS[a0], st['fail_class'], st['frac_fail'], ''.join('SL'[x] for x in st['prev_actions']),
                             int(e['n_visible_checks'] == 0)])
            pt = per_task.setdefault(e['task_uid'], dict(split=sp, family=family_of(e['task_uid']), episodes=0, eligible_t=[0] * K,
                                                         eligible_t_initial_small=[0] * K, episodes_initial_small=0,
                                                         successes=0, successes_initial_small=0, n_visible_checks=set()))
            pt['episodes'] += 1; pt['successes'] += int(e['success'])
            pt['n_visible_checks'].add(e['n_visible_checks'])
            for d in decs:
                pt['eligible_t'][d['t']] += 1
            if decs[0]['a'] == 0:
                pt['episodes_initial_small'] += 1; pt['successes_initial_small'] += int(e['success'])
                for d in decs:
                    pt['eligible_t_initial_small'][d['t']] += 1
        c['decisions_jsonl_records_without_episode'] = len(set(dmap) - used)
        c['duplicate_decision_keys'] = dup
        if part == 'pilot':
            c['pilot_draw_rederivation'] = ('numpy %s, default_rng(design_seed + 1), run.py pilot order' % np_version) if pd is not None else 'numpy unavailable: not checked'
        ver[part] = dict(c)

    # ---------- decision-opportunity counts
    def opp_counts(sp: str):
        R = [r for r in rows if r[0] == sp]
        eps_n = sum(1 for u, t in per_task.items() if t['split'] == sp for _ in range(t['episodes']))
        eps_s = sum(t['episodes_initial_small'] for t in per_task.values() if t['split'] == sp)
        tasks = [u for u, t in per_task.items() if t['split'] == sp]
        out = OrderedDict(episodes=eps_n, episodes_initial_small=eps_s, tasks=len(tasks))
        for label, sel in (('all_histories', lambda r: True), ('E2_relevant_initial_small', lambda r: r[10] == 'small')):
            block = OrderedDict()
            for t in range(K):
                Rt = [r for r in R if r[5] == t and sel(r)]
                tk = Counter(r[2] for r in Rt)
                block['t%d' % t] = OrderedDict(
                    decision_index='%s decision' % ('first', 'second', 'third')[t],
                    eligible=len(Rt), supported=sum(r[9] for r in Rt), assigned=dict(sorted(Counter(r[6] for r in Rt).items())),
                    logged_p_large_values=dict(Counter(str(r[7]) for r in Rt)),
                    tasks_with_at_least_one=len(tk),
                    tasks_with_at_least_one_by_family=dict(sorted(Counter(family_of(u) for u in tk).items())),
                    per_task_count_distribution={str(k): v for k, v in sorted(Counter(tk.get(u, 0) for u in tasks).items())},
                    share_of_episodes_reaching=rate(len(Rt), eps_n if label == 'all_histories' else eps_s))
            out[label] = block
        return out

    opp = OrderedDict(train=opp_counts('train'), pilot=opp_counts('pilot'))

    # ---------- 3. pre-action feedback categories (second/third decisions)
    def feedback(sp: str):
        R = [r for r in rows if r[0] == sp and r[5] >= 1]
        zero_chk = {u for u, t in per_task.items() if t['split'] == sp and t['n_visible_checks'] == {0}}
        out = OrderedDict()
        for label, sel in (('all_histories', lambda r: True), ('E2_relevant_initial_small', lambda r: r[10] == 'small')):
            b = OrderedDict()
            for t in (1, 2):
                Rt = [r for r in R if r[5] == t and sel(r)]
                b['t%d' % t] = OrderedDict(
                    n=len(Rt),
                    remaining_decisions_including_current=K - t,
                    fail_class=dict(sorted(Counter(r[11] for r in Rt).items())),
                    fail_class_x_frac_bin=dict(sorted(Counter('%s|%s' % (r[11], frac_bin(r[12])) for r in Rt).items())),
                    frac_fail_values=dict(sorted(Counter('%.4f' % r[12] for r in Rt).items())),
                    prev_actions=dict(sorted(Counter(r[13] for r in Rt).items())),
                    by_family_fail_class=dict(sorted(Counter('%s|%s' % (r[3], r[11]) for r in Rt).items())),
                    from_tasks_with_zero_visible_checks=sum(r[2] in zero_chk for r in Rt))
            # joint feedback path at the third decision: class at decision 2 -> class at decision 3
            first = {r[1]: r[11] for r in R if r[5] == 1}
            b['t2_feedback_path'] = dict(sorted(Counter('%s->%s' % (first.get(r[1]), r[11]) for r in R if r[5] == 2 and sel(r)).items()))
            out[label] = b
        out['tasks_with_zero_visible_checks'] = len(zero_chk)
        return out

    fb = OrderedDict(
        field_definitions=OrderedDict(
            source='decisions.jsonl "state" of each eligible decision (identical to the copy embedded in episodes.jsonl; verified)',
            t='decision index; t=0 first, t=1 second, t=2 third',
            fail_class=('class of the most recent VISIBLE-test validation: "assertion" if every failing visible check raised '
                        'AssertionError, "exception" if the candidate failed to load, crashed, timed out, produced no code, or any '
                        'failing check raised a non-assertion exception ("start" only at t=0). Hidden tests never enter state.'),
            frac_fail='n_fail / max(n_visible_checks, 1) of the most recent validation; frac_bin = "all_checks_failed" if 1.0 else "partial"',
            prev_actions='actions already taken in the episode, S=small, L=large',
            remaining_budget=('K - t decisions including the current one (K=3). It is a deterministic function of t: the '
                              'harness has no token or time budget in the routing state, so it adds no within-stage variation.'),
            b_obs='logged probability of the realized action (p_large if large else 1 - p_large); verified identity',
            zero_visible_checks='task whose frozen certified visible-test set is empty (episode n_visible_checks = 0): validation is a load check only'),
        train=feedback('train'), pilot=feedback('pilot'))

    # ---------- 4. outcome variation and resources (frozen endpoints as recorded)
    def outcomes(sp: str):
        E = [e for P in parts.values() for e in P['eps'] if split_of_task.get(e['task_uid']) == sp and not e.get('error')]
        res = OrderedDict()
        for label, sel in (('all_episodes', lambda e: True), ('initial_small', lambda e: e['decisions'][0]['a'] == 0),
                           ('reached_second_decision', lambda e: len(e['decisions']) >= 2),
                           ('initial_small_reached_second_decision', lambda e: e['decisions'][0]['a'] == 0 and len(e['decisions']) >= 2)):
            Es = [e for e in E if sel(e)]
            by_task = defaultdict(list)
            for e in Es:
                by_task[e['task_uid']].append(int(e['success']))
            multi = {u: v for u, v in by_task.items() if len(v) >= 2}
            res[label] = OrderedDict(
                episodes=len(Es), successes=sum(e['success'] for e in Es), success_rate=rate(sum(e['success'] for e in Es), len(Es)),
                tasks=len(by_task), tasks_with_2plus_episodes=len(multi),
                tasks_with_within_task_success_variation=sum(0 < sum(v) < len(v) for v in multi.values()),
                tasks_all_success=sum(sum(v) == len(v) for v in by_task.values()),
                tasks_all_failure=sum(sum(v) == 0 for v in by_task.values()),
                mean_task_success_equal_task_weight=rate(sum(sum(v) / len(v) for v in by_task.values()), len(by_task)))
        stop = OrderedDict()
        for label, sel in (('all_episodes', lambda e: True), ('initial_small', lambda e: e['decisions'][0]['a'] == 0)):
            Es = [e for e in E if sel(e)]
            one = [e for e in Es if len(e['decisions']) == 1]
            stop[label] = OrderedDict(
                episodes=len(Es),
                stopped_after_first_call_visible_pass=len(one),
                of_which_hidden_success=sum(e['success'] for e in one),
                of_which_hidden_failure_visible_false_pass=sum(1 - e['success'] for e in one),
                of_which_on_zero_visible_check_tasks=sum(e['n_visible_checks'] == 0 for e in one),
                reached_second_decision=len(Es) - len(one))
        res['why_episodes_stop_before_decision_2'] = OrderedDict(
            note=('descriptive DEVELOPMENT counts; a first-call visible pass ends the episode (absorbing stop). A hidden '
                  'failure after a visible pass is a stop that visible feedback could not flag; it is not evidence that a '
                  'further call would have repaired it.'), **stop)
        res['resources_all_episodes'] = OrderedDict(
            note='kept distinct; call penalties are the frozen unitless design values (0.01 small, 0.03 large), not dollars',
            mean_model_calls=rate(sum(len(e['decisions']) for e in E), len(E)),
            mean_large_calls=rate(sum(sum(d['a'] for d in e['decisions']) for e in E), len(E)),
            mean_small_calls=rate(sum(sum(1 - d['a'] for d in e['decisions']) for e in E), len(E)),
            mean_frozen_call_penalty=rate(sum(e['penalty'] for e in E), len(E)),
            mean_frozen_utility=rate(sum(e['utility'] for e in E), len(E)),
            mean_completion_tokens=rate(sum(e['completion_tokens'] for e in E), len(E)),
            mean_prompt_tokens=rate(sum(sum(d['prompt_tokens'] for d in e['decisions']) for e in E), len(E)),
            mean_llm_wall_seconds=rate(sum(e['llm_wall_seconds'] for e in E), len(E)),
            episodes_with_hack_flags=sum(bool(e['hack_flags']) for e in E),
            episodes_with_verify_timeout=sum(bool(e['verify_timed_out']) for e in E))
        return res

    outc = OrderedDict(endpoint_definitions=OrderedDict(
        success='episode "success": the submitted final candidate passes the HIDDEN tests (frozen primary endpoint of code_routing_v1)',
        utility='episode "utility" = success - sum of frozen call penalties (0.03 large, 0.01 small); the archived learning objective'),
        train=outcomes('train'), pilot=outcomes('pilot'))

    # ---------- 5. candidate rules: status of training and model-free disagreement opportunity
    lp = json.loads((REPO / CR / 'learned_policy.json').read_text())
    table = {tuple(k): v for k, v in lp['table']}
    # on-policy path of the archived table, from its own first action
    onpol = []
    for x in (0, 1):
        a0 = int(table[(0, x, 'start', -1)])
        path = ['SL'[a0]]
        for fc1 in ('assertion', 'exception'):
            a1 = int(table.get((1, x, fc1, a0), 0.0))
            for fc2 in ('assertion', 'exception'):
                a2 = int(table.get((2, x, fc2, a1), 0.0))
                onpol.append(dict(x_humaneval=x, feedback=[fc1, fc2], actions=''.join('SL'[z] for z in (a0, a1, a2))))
    realized_schedules = sorted({o['actions'] for o in onpol})
    archived = OrderedDict(
        file=CR + '/learned_policy.json', created_utc=lp['created_utc'], objective=lp['objective'],
        n_train_episodes=lp['n_train_episodes'], n_train_tasks=lp['n_train_tasks'],
        learner=('tabular fitted-Q with the optimal (max) continuation over state_key = (t, x_humaneval, fail_class, '
                 'previous action), greedy P(large) in {0,1} (experiments/code_routing/analysis.py --learn -> '
                 'estimators_absorbing.learn_greedy_table). It is NOT a depth-two tree, has no matched initial small '
                 'action, and has no prompt-only counterpart fitted in the same class.'),
        n_table_entries=len(table), initial_action_by_x=OrderedDict((str(x), 'SL'[int(table[(0, x, 'start', -1)])]) for x in (0, 1)),
        on_policy_schedules_over_all_feedback_paths=realized_schedules,
        on_policy_note=('on its own histories the archived table takes the same action sequence for every benchmark and '
                        'feedback path' if len(realized_schedules) == 1 else 'on-policy actions vary with state'))
    trained = OrderedDict(
        prompt_only_depth_two_tree_trained=False, history_aware_depth_two_tree_trained=False,
        statement=('Neither same-class candidate router of the primary history contrast (docs/experiment_protocol_v2.md '
                   'section 4) has been trained anywhere in the repository on the code-routing data. The only learned '
                   'code-routing policy is the archived tabular fitted-Q table below. The v2 simulator rules named '
                   'history_large_after_exception and prompt_only_large_if_hard (experiments/v2_sim/) are hand-specified '
                   'rules of a synthetic generator, not trees trained on these records. Per the request, no rule is fitted '
                   'here and no counterfactual success is predicted.'),
        search_evidence=('case-insensitive repository search for depth-two / DecisionTree / max_depth / prompt-only / '
                         'history-aware across experiments/, results/ and docs/ (working tree at commit 51d14cb) found no '
                         'trained tree or trained prompt-only/history-aware router for results/code_routing; matches are the '
                         'v2 protocol text, lead feedback, the synthetic v2_sim generator rules and their audits.'),
        archived_learned_policy=archived)

    def upper_bounds(sp: str):
        R = [r for r in rows if r[0] == sp and r[5] >= 1 and r[9]]
        defs = OrderedDict(
            U_A=('cell = (t, family, zero_visible_checks) = the stage plus the prompt-only feature set of the specification; '
                 'history = (fail_class, frac_bin, prev_actions)', lambda r: (r[5], r[3], r[14]), lambda r: (r[11], frac_bin(r[12]), r[13])),
            U_B=('cell = (t, family, zero_visible_checks, prev_actions); history = (fail_class, frac_bin) [path-conditional, feedback only]',
                 lambda r: (r[5], r[3], r[14], r[13]), lambda r: (r[11], frac_bin(r[12]))),
            U_raw=('cell = (t, family, zero_visible_checks); history = (fail_class, raw frac_fail, prev_actions) [finest recorded state]',
                   lambda r: (r[5], r[3], r[14]), lambda r: (r[11], r[12], r[13])),
            U_bench=('cell = (t, family) only [benchmark as the sole prompt feature]; history = (fail_class, frac_bin, prev_actions)',
                     lambda r: (r[5], r[3]), lambda r: (r[11], frac_bin(r[12]), r[13])))
        out = OrderedDict()
        for label, sel in (('E2_relevant_initial_small', lambda r: r[10] == 'small'), ('all_histories', lambda r: True)):
            Rs = [r for r in R if sel(r)]
            blk = OrderedDict(supported_eligible_second_third_decisions=len(Rs), tasks=len({r[2] for r in Rs}))
            for name, (desc, cell_f, hist_f) in defs.items():
                cells = defaultdict(list)
                for r in Rs:
                    cells[cell_f(r)].append(r)
                multi = {c: v for c, v in cells.items() if len({hist_f(r) for r in v}) > 1}
                in_multi = [r for v in multi.values() for r in v]
                tk = Counter(r[2] for r in in_multi)
                blk[name] = OrderedDict(
                    definition=desc, cells=len(cells), cells_with_more_than_one_history_value=len(multi),
                    decisions_in_multi_valued_cells=len(in_multi),
                    by_t=dict(sorted(Counter('t%d' % r[5] for r in in_multi).items())),
                    distinct_tasks=len(tk), distinct_tasks_by_family=dict(sorted(Counter(family_of(u) for u in tk).items())),
                    per_task_decision_count_distribution={str(k): v for k, v in sorted(Counter(tk.values()).items())},
                    bound_vs_closest_prompt_only_rule=sum(len(v) // 2 for v in multi.values()),
                    cell_detail=[OrderedDict(cell=list(c), n=len(v), tasks=len({r[2] for r in v}),
                                             history_values=OrderedDict(sorted(((canonical(list(h)), n) for h, n in Counter(hist_f(r) for r in v).items()))))
                                 for c, v in sorted(cells.items(), key=lambda kv: canonical(list(kv[0])))])
            out[label] = blk
        return out

    disagreement = OrderedDict(
        definition=('MODEL-FREE UPPER BOUND on disagreement opportunity. Among supported eligible second/third decisions '
                    '(p_large strictly between 0 and 1 and both actions available), count the decisions that lie in '
                    'prompt-feature cells in which the history features take more than one observed value: only there can '
                    'a history-aware rule choose differently from every prompt-only rule of the same class. This is an upper '
                    'bound: trained rules may agree on some or all of these decisions. bound_vs_closest_prompt_only_rule '
                    'sums floor(n_cell/2): a rule that is non-constant within a cell differs from the nearest constant '
                    '(prompt-only) choice there on at most half of the cell. E2-relevant = initial action small, the '
                    'matched initial action of the primary contrast; only these histories are shared with both candidates.'),
        train=upper_bounds('train'), pilot=upper_bounds('pilot'))

    spec = OrderedDict(
        id='REQ006-E2DEV-TREE-v0', status='SPECIFIED, NOT EXECUTED. No tree has been fitted; fitting requires lead acceptance.',
        data=OrderedDict(
            fit_and_validation='TRAIN partition only: results/code_routing/log/episodes.jsonl restricted to design.json train_tasks (231 tasks, 1848 episodes, 8 per task, blocked a0 4S/4L).',
            pilot='30 pilot tasks (120 episodes): not used for fitting or complexity selection; optional descriptive DEV report only.',
            never='results/code_routing/live/, branch/, any CONFIRM-task record (including CONFIRM-task log episodes), any new inference.'),
        common_structure=('Both routers fix the first action to small (a0 = S), matching the primary history contrast. Only '
                          'TRAIN log episodes with a0 = S carry nonzero target weight (target probability 1, logged 0.5).'),
        decision_points=OrderedDict(t1='second decision; 2 decisions remain including the current one',
                                    t2='third decision; 1 remains', remaining_budget='deterministic in t (K=3); represented by using one tree per stage'),
        features=OrderedDict(
            prompt_only=['x_humaneval = 1{benchmark == humaneval}', 'zero_visible_checks = 1{n_visible_checks == 0} (frozen task environment, known before the first action)'],
            history_aware=['all prompt_only features', 'exc_last = 1{state.fail_class == exception}',
                           'allfail_last = 1{state.frac_fail == 1.0}', 't2 only: prev_large = 1{state.prev_actions[-1] == 1}'],
            note=('Every feature is binary and read from the recorded pre-action state or task identity; no hidden-test '
                  'quantity (success, success_first_candidate) is a feature. The lead may drop zero_visible_checks for '
                  'the smallest class; it is given to both routers so that the history-aware router cannot gain task '
                  'information through feedback that the prompt-only router lacks.')),
        learner_class=('For each stage t in {1,2}, a binary decision tree of depth d <= 2 whose internal nodes split on one '
                       'binary feature and whose leaves assign small or large; d = 0 gives the constant rules. A candidate '
                       'router is (a0 = S, tree_t1, tree_t2) using a common depth d for both stages. Prompt-only and '
                       'history-aware routers differ only in the feature set.'),
        objective=OrderedDict(
            endpoint=('frozen utility = success - 0.03 x large calls - 0.01 x small calls, the archived learning objective '
                      '(learned_policy.json objective = utility); success, large/small calls and tokens are reported '
                      'separately for every selected rule. Substituting the success endpoint is a lead decision, not made here.'),
            estimator=('self-normalized inverse-probability-weighted value V(pi) = sum_e W_e U_e / sum_e W_e over the '
                       'episodes of the task set, W_e = prod over the realized eligible decisions t of 1{A_et = pi_t(H_et)} / '
                       'b_et with b_et the logged probability from decisions.jsonl (all 0.5); task-clustered standard '
                       'errors from task-level linearized contributions'),
            search=('exhaustive enumeration of all (tree_t1, tree_t2) pairs in the class (joint value search, not stagewise); '
                    'deterministic tie-break: higher value, then fewer leaves, then lower IPW-estimated large-call rate, then '
                    'lexicographic order of the canonical tree string'),
            references=['Murphy (2003), JRSS-B 65(2):331-355 (dynamic treatment regimes)',
                        'Zhang, Tsiatis, Laber and Davidian (2013), Biometrika 100(3):681-694 (value search over a restricted regime class)',
                        'Laber and Zhao (2015), Biometrika 102(3):501-514 (tree-based treatment regimes)',
                        'Breiman, Friedman, Olshen and Stone (1984), Classification and Regression Trees (one-standard-error rule)']),
        split=OrderedDict(
            unit='task (all 8 runs of a task stay together)',
            procedure=('within each benchmark, sort the TRAIN task ids, permute them with numpy.random.default_rng(20260923).permutation, '
                       'and assign the first round(2/3 x n_benchmark) to FIT and the rest to VALIDATION (mbpp first, then humaneval, one generator)'),
            seed=20260923,
            expected_sizes=OrderedDict((f, OrderedDict(fit=int(round(2 * n / 3)), validation=n - int(round(2 * n / 3))))
                                       for f, n in fam(train).items())),
        complexity_selection=('for d in {0,1,2} fit on FIT and estimate the value on VALIDATION; choose the smallest d whose '
                              'validation value is at least the best validation value minus one task-clustered standard '
                              'error of that best value; select separately for each router class; then refit the chosen '
                              'depth on all TRAIN tasks and freeze. Record the FIT-only trees as well.'),
        frozen_record=('write-once JSON with both final trees, selected depths, FIT/VALIDATION task ids and their hash, all '
                       'tie-breaks, the script and input hashes, BEFORE any E2 execution; no refit after any E2 outcome is seen'),
        required_report_after_fitting=[
            'action of each router at every supported common observed history (the U_A cells) and the number of supported decisions and distinct TRAIN tasks where they disagree',
            'whether either router collapses to a fixed schedule (reported as such)',
            'validation values labelled DEVELOPMENT-only and not confirmatory; no counterfactual success prediction for CONFIRM'])

    cand = OrderedDict(training_status=trained, disagreement_opportunity=disagreement, frozen_training_specification=spec)

    # ---------- 6. precision
    ub = disagreement['train']['E2_relevant_initial_small']['U_A']
    n_opp = ub['distinct_tasks']
    m_req = lambda s2, h: int(math.ceil(Z * Z * s2 / (h * h)))
    half = lambda s2, m: Z * math.sqrt(s2 / m)
    # DEV planning quantities from TRAIN initial-small log episodes (logger continuation after a0 = S)
    v_i, q_i, q2_i = [], [], []
    by_task_s = defaultdict(list)
    for e in parts['log']['eps']:
        if e['decisions'][0]['a'] == 0:
            by_task_s[e['task_uid']].append((int(e['success']), int(len(e['decisions']) >= 2)))
    for u, L in by_task_s.items():
        n = len(L); ys = [y for y, _ in L]; k = sum(ys); rch = sum(z for _, z in L)
        v_i.append(k * (n - k) / (n * (n - 1)))                  # unbiased within-task Bernoulli variance
        q_i.append(rch / n); q2_i.append(rch * (rch - 1) / (n * (n - 1)))   # unbiased estimate of q_i^2
    s0 = 2 * sum(v_i) / len(v_i)
    qbar = sum(q_i) / len(q_i); tau2_max = sum(q2_i) / len(q2_i)
    plan = []
    for r in (1, 2, 4, 8):
        for tau_label, tau2 in (('tau2=0', 0.0), ('tau2=upper_bound', tau2_max)):
            s2 = s0 / r + tau2
            plan.append(OrderedDict(replicates_per_arm_per_task=r, heterogeneity=tau_label, planning_s2=s2,
                                    tasks_for_h_0p05=m_req(s2, 0.05), tasks_for_h_0p10=m_req(s2, 0.10),
                                    half_width_at_231_tasks=half(s2, 231), half_width_at_330_tasks=half(s2, 330),
                                    physical_episodes_at_330_tasks=330 * 2 * r))
    precision = OrderedDict(
        protocol_formula='m = 1.96^2 s_D^2 / h^2 for paired task-level differences D_i (docs/experiment_protocol.md section 4.3); a planning approximation, not a coverage guarantee',
        m_required_h0p05_s2_0p20=m_req(S2_ILLUSTRATIVE, H_PROTOCOL), m_required_h0p05_worst_s2_1=m_req(S2_WORST, H_PROTOCOL),
        train_tasks_total=len(train), train_tasks_with_supported_disagreement_opportunity=n_opp,
        enough_for_h0p05_at_s2_0p20=n_opp >= m_req(S2_ILLUSTRATIVE, H_PROTOCOL),
        half_width_at_s2_0p20_with_opportunity_tasks=half(S2_ILLUSTRATIVE, n_opp) if n_opp else None,
        half_width_at_s2_0p20_all_train_tasks=half(S2_ILLUSTRATIVE, len(train)),
        retrospective_caveat=('A retrospective TRAIN estimate of the router contrast would be IPW-weighted (weight 2 per '
                              'matched decision, up to 8 for three decisions) and, after FIT/VALIDATION splitting, rests on '
                              'about 77 validation tasks; its task-level variance exceeds the paired-binary planning variance, '
                              'so these half-widths are optimistic for DEV validation.'),
        dev_planning_quantities=OrderedDict(
            source='TRAIN log episodes with a0 = small (924 episodes expected, 4 per task), logger continuation after a0; DEVELOPMENT-only',
            s0_squared=s0, s0_definition='2 x mean over tasks of the unbiased within-task success variance: the null-contrast variance of one fresh execution per arm',
            qbar=qbar, qbar_definition=('mean over TRAIN tasks of the share of initial-small episodes that reach a second decision; '
                                        'it estimates q = P(reach decision 2 | a0 = S). Both routers make the same first call (small, same '
                                        'prompt and decoding), so the success contrast satisfies |V_H - V_P| <= P(reach a history where '
                                        'they disagree) <= q, because terminal success lies in [0, 1].'),
            tau2_upper_bound=tau2_max, tau2_definition='task-effect heterogeneity bound: Var(Delta_i) <= E[Delta_i^2] <= E[q_i^2], estimated unbiasedly per task'),
        prospective_plan_table=plan,
        task_pool_facts=OrderedDict(
            benchmark_tasks=len(all_tasks), pilot_tasks_executed=len(pilot), train_tasks_used_for_learning=len(train),
            confirm_tasks_observed=len(confirm), untouched_tasks_in_benchmark=len(all_tasks - pilot - train - confirm),
            note=('The E2 row of docs/experiment_protocol_v2.md asks for fresh executions on untouched issues, and existing '
                  'MBPP/HumanEval CONFIRM observations are permanently excluded from new tuning/confirmation. Every task of '
                  'this 591-task benchmark has been executed. Whether a prospective E2 reuses the 330 CONFIRM task identities '
                  'for new executions, or uses a new task pool, is a lead decision; the 330-task columns are size arithmetic only.')))

    # ---------- acceptance and conclusion
    vt, vp = ver['log'], ver['pilot']
    zero_keys = [k for k in vt if isinstance(vt[k], int) and k not in ('episodes', 'decisions')] + \
                [k for k in vp if isinstance(vp[k], int) and k not in ('episodes', 'decisions')]
    mismatches = sum(vt[k] for k in vt if isinstance(vt[k], int) and k not in ('episodes', 'decisions')) + \
        sum(vp[k] for k in vp if isinstance(vp[k], int) and k not in ('episodes', 'decisions'))
    reconciles = (design_sha_ok and split['pairwise_disjoint'] and design_log_split_mismatch == 0
                  and recon['log']['tasks_present_equal_design_train'] and recon['pilot']['tasks_present_equal_design_pilot']
                  and all(recon[p][k] == 0 for p in recon for k in ('episode_split_field_disagreements', 'benchmark_field_disagreements',
                                                                    'episode_id_task_disagreements', 'duplicate_episode_ids',
                                                                    'missing_expected', 'unexpected', 'error_records')))
    confirm_rows = sum(1 for r in rows if r[2] in confirm)
    acceptance = OrderedDict(split_ids_and_denominators_reconcile=reconciles,
                             probability_action_state_mismatches=mismatches, checks_counted=len(zero_keys),
                             confirm_task_rows_in_table=confirm_rows,
                             inputs_equal_source_commit_blobs=all(v['equals_blob_at_source_commit'] for v in inputs.values()))
    acceptance['passes'] = reconciles and mismatches == 0 and confirm_rows == 0

    e2t = opp['train']['E2_relevant_initial_small']
    reach2_e2 = e2t['t1']['share_of_episodes_reaching']
    reach2_all = opp['train']['all_histories']['t1']['share_of_episodes_reaching']
    flag_1a = reach2_e2 < REACH2_FLAG
    flag_1b = ub['decisions_in_multi_valued_cells'] == 0
    rules_trained = trained['prompt_only_depth_two_tree_trained'] and trained['history_aware_depth_two_tree_trained']
    if not acceptance['passes']:
        concl, step = 'INCONCLUSIVE', 'Step 0 (acceptance failed)'
    elif flag_1a or flag_1b:
        concl, step = 'REPAIR', 'Step 1 (%s)' % ' and '.join(x for x, f in (('1a', flag_1a), ('1b', flag_1b)) if f)
    elif rules_trained:
        concl, step = 'INCONCLUSIVE', 'Step 3 (trained-rule disagreement and pool feasibility not evaluated in this script)'
    else:
        concl, step = 'INCONCLUSIVE', 'Step 3 (Step 1 did not fire; candidate rules untrained)'
    conclusion = OrderedDict(
        rule=CONCLUSION_RULE, rule_disclosure=RULE_DISCLOSURE, category=concl, decided_at=step,
        decisive_counts=OrderedDict(
            train_E2_relevant_episodes=e2t['t0']['eligible'],
            train_E2_relevant_reaching_second_decision=e2t['t1']['eligible'],
            train_E2_relevant_share_reaching_second_decision=reach2_e2, flag_threshold=REACH2_FLAG, flag_1a_fires=flag_1a,
            train_all_share_reaching_second_decision=reach2_all,
            train_E2_relevant_supported_second_third_decisions=disagreement['train']['E2_relevant_initial_small']['supported_eligible_second_third_decisions'],
            train_E2_relevant_upper_bound_decisions_U_A=ub['decisions_in_multi_valued_cells'],
            train_E2_relevant_upper_bound_tasks_U_A=n_opp, flag_1b_fires=flag_1b,
            candidate_rules_trained=rules_trained,
            tasks_needed_h0p05_protocol_s2_0p20=precision['m_required_h0p05_s2_0p20'],
            untouched_tasks_in_benchmark=precision['task_pool_facts']['untouched_tasks_in_benchmark']),
        what_would_change_it=[
            'Flag 1a is far from its threshold: 50%% of %d E2-relevant episodes is %d, against %d observed; the all-history share '
            '(%.3f) and the pilot initial-small share (%.3f) are also below 0.50.' % (
                e2t['t0']['eligible'], int(math.ceil(0.5 * e2t['t0']['eligible'])), e2t['t1']['eligible'], reach2_all,
                opp['pilot']['E2_relevant_initial_small']['t1']['share_of_episodes_reaching']),
            'If the lead judges the v2 section 5 flag inapplicable to this archived MBPP/HumanEval harness, Step 1 does not fire '
            '(flag 1b is false) and the rule gives INCONCLUSIVE at Step 3, because the candidate rules are untrained.',
            'PROCEED would additionally need both depth-two routers fitted under the frozen specification, supported disagreement '
            'at common observed histories, and an untouched task pool of the size in the precision section; this benchmark has '
            'no untouched task.'])

    limitations = [
        'Retrospective DEVELOPMENT analysis of an archived study; nothing here is confirmatory or an effect estimate.',
        'Disagreement is a model-free upper bound; the depth-two candidate routers were not trained, so realized disagreement is unknown.',
        'Occupancy is law-dependent: it is realized under the uniform randomized logger (p_large = 0.5) and could differ under other routers.',
        'Prompt features are limited to what the records carry (benchmark and visible-check availability); richer task text features were not used.',
        'Family = benchmark; no near-duplicate grouping exists in the inputs, so independence of task ids is assumed, not verified.',
        'Pilot draws were not blocked on a0 and were run before the design freeze; pilot is reported separately and never pooled with TRAIN.',
        'Planning variances come from logger-continued episodes, not from the candidate routers; the section 4.3 formula is a planning approximation.',
    ]

    table_json = OrderedDict(
        request='DTR-REQ-006 (P0)', lead_source='docs/theory_feedback_20260923_req005_integration_decision.md',
        source_commit=SOURCE_COMMIT, script=SCRIPT_REL, script_sha256=sha256_bytes((REPO / SCRIPT_REL).read_bytes()),
        scope=('retrospective DEVELOPMENT-only; TRAIN/log and pilot partitions; no CONFIRM or live outcome; no model inference, '
               'server, GPU, network or Monte Carlo; frozen success/utility endpoints as recorded; no rule fitted'),
        inputs=inputs, acceptance=acceptance, conclusion=conclusion,
        split_reconciliation=split, probability_and_state_verification=ver,
        decision_opportunities=opp, pre_action_feedback=fb, outcome_variation=outc, candidate_rules=cand,
        precision=precision, limitations=limitations,
        per_task_columns=['task_uid', 'split', 'family', 'episodes', 'eligible_t0', 'eligible_t1', 'eligible_t2',
                          'episodes_initial_small', 'eligible_t1_initial_small', 'eligible_t2_initial_small', 'successes',
                          'successes_initial_small', 'n_visible_checks'],
        per_task=[[u, t['split'], t['family'], t['episodes'], *t['eligible_t'], t['episodes_initial_small'],
                   t['eligible_t_initial_small'][1], t['eligible_t_initial_small'][2], t['successes'],
                   t['successes_initial_small'], sorted(t['n_visible_checks'])]
                  for u, t in sorted(per_task.items(), key=lambda kv: (kv[1]['split'], kv[0]))],
        per_decision_columns=['split', 'episode_id', 'task_uid', 'family', 'run', 't', 'action', 'p_large', 'b_obs', 'supported',
                              'initial_action', 'fail_class', 'frac_fail', 'prev_actions', 'zero_visible_checks'],
        per_decision_source='every field from results/code_routing/{log,pilot}/decisions.jsonl, cross-checked against episodes.jsonl',
        per_decision=rows)
    return table_json


# ------------------------------------------------------------------ summary
def fmt(x, nd=3):
    return '-' if x is None else ('%.*f' % (nd, x) if isinstance(x, float) else str(x))


def summary_md(T: dict) -> str:
    C = T['conclusion']; dc = C['decisive_counts']; S = T['split_reconciliation']; A = T['acceptance']
    O = T['decision_opportunities']; F = T['pre_action_feedback']; Y = T['outcome_variation']
    D = T['candidate_rules']['disagreement_opportunity']; st = T['candidate_rules']['training_status']
    P = T['precision']; V = T['probability_and_state_verification']
    L = []
    w = L.append
    w('# DTR-REQ-006 decision-opportunity table (retrospective, DEVELOPMENT-only)')
    w('')
    w('Generated by `%s` (sha256 `%s`) from the inputs pinned below. The inputs are byte-identical to source commit `%s`. '
      'Written once; do not edit by hand. Machine-readable table: `decision_opportunity_table.json`.' % (T['script'], T['script_sha256'][:16], T['source_commit']))
    w('')
    w('**Scope.** %s.' % T['scope'])
    w('')
    w('## Conclusion')
    w('')
    w('**Rule applied (stated before the answer).** ' + C['rule'])
    w('')
    w('*Disclosure.* ' + C['rule_disclosure'])
    w('')
    w('**Category: %s** (decided at %s).' % (C['category'], C['decided_at']))
    w('')
    w('| Decisive count (TRAIN) | Value |')
    w('|---|---:|')
    w('| E2-relevant log episodes (initial action small) | %d |' % dc['train_E2_relevant_episodes'])
    w('| ... reaching an eligible second decision | %d (%.1f%%; flag threshold %.0f%%) |' % (dc['train_E2_relevant_reaching_second_decision'], 100 * dc['train_E2_relevant_share_reaching_second_decision'], 100 * dc['flag_threshold']))
    w('| all TRAIN log episodes reaching a second decision | %.1f%% |' % (100 * dc['train_all_share_reaching_second_decision']))
    w('| supported E2-relevant second/third decisions | %d |' % dc['train_E2_relevant_supported_second_third_decisions'])
    w('| ... in prompt cells with more than one history value (upper bound U_A) | %d decisions in %d distinct tasks |' % (dc['train_E2_relevant_upper_bound_decisions_U_A'], dc['train_E2_relevant_upper_bound_tasks_U_A']))
    w('| candidate depth-two routers trained | %s |' % ('yes' if dc['candidate_rules_trained'] else 'no'))
    w('| tasks needed for half-width 0.05 at the protocol s_D^2 = 0.20 | %d |' % dc['tasks_needed_h0p05_protocol_s2_0p20'])
    w('| untouched tasks left in the 591-task benchmark | %d |' % dc['untouched_tasks_in_benchmark'])
    w('')
    w('Flag 1a fires: **%s**. Flag 1b fires: **%s**.' % (dc['flag_1a_fires'], dc['flag_1b_fires']))
    w('')
    w('What would change the category:')
    for x in C['what_would_change_it']:
        w('- ' + x)
    w('')
    w('## Acceptance checks')
    w('')
    w('- Split IDs and denominators reconcile to `design.json`: **%s**' % A['split_ids_and_denominators_reconcile'])
    w('- Eligible decisions verified field by field against `decisions.jsonl`: %d TRAIN, %d pilot; mismatches (probability, action, `b_obs`, draw, design draw/block, seed, derived state): **%d** summed over %d check counters (log + pilot)' % (
      V['log']['decisions'], V['pilot']['decisions'], A['probability_action_state_mismatches'], A['checks_counted']))
    w('- CONFIRM-task rows in the table: **%d**' % A['confirm_task_rows_in_table'])
    w('- Inputs equal the blobs at `%s`: **%s**' % (T['source_commit'], A['inputs_equal_source_commit_blobs']))
    w('')
    w('## 1. Split reconciliation')
    w('')
    c = S['counts']
    w('`design.json` sha256 `%s` (matches `design.sha256`: %s). Splits are pairwise disjoint: %s.' % (S['design_sha256'][:16], S['design_sha256_matches_design_sha256_file'], S['pairwise_disjoint']))
    w('')
    w('| Split | Tasks | MBPP | HumanEval | Task-ID list sha256 |')
    w('|---|---:|---:|---:|---|')
    for sp in ('pilot', 'train', 'confirm'):
        fc = S['family_counts'][sp]
        w('| %s | %d | %d | %d | `%s` |' % (sp, c[sp], fc.get('mbpp', 0), fc.get('humaneval', 0), S['ids_sha256'][sp][:16]))
    w('')
    w('Family definition: ' + S['family_definition'])
    w('')
    for part in ('log', 'pilot'):
        m = S['episode_mapping'][part]
        w('- `%s/`: kept %d episode and %d decision records; excluded CONFIRM-task records: %d episodes, %d decisions. '
          'Mapped via `design.json`: %s. Split-field disagreements %d, missing expected episodes %d, unexpected %d, '
          'infrastructure-error records %d. Independent tasks %d (%s).' % (
              part, m['episode_records_kept'], m['decision_records_kept'], m['confirm_episode_records_excluded'],
              m['confirm_decision_records_excluded'], m['kept_episodes_by_design_split'], m['episode_split_field_disagreements'],
              m['missing_expected'], m['unexpected'], m['error_records'], m['independent_tasks'], m['independent_tasks_by_family']))
    w('')
    w('The randomized log was designed over TRAIN and CONFIRM tasks (8 runs each); its %d CONFIRM-task episodes are excluded '
      'by task id before any outcome field is used.' % S['episode_mapping']['log']['confirm_episode_records_excluded'])
    w('')
    w('## 2. Decision opportunities')
    w('')
    w('Every eligible decision in both partitions logged p_large = 0.5 with both actions available, so every one is supported. '
      'Probabilities, actions, `b_obs`, draws and states were matched field by field between `decisions.jsonl` and the '
      'episode copies. Log draws were also matched to the `design.json` pre-drawn uniforms and the blocked first action. '
      'Pilot draws were re-derived with %s.' % V['pilot'].get('pilot_draw_rederivation'))
    w('')
    w('| Partition | Histories | Decision | Eligible (= supported) | small / large | Tasks with >= 1 | Share of episodes |')
    w('|---|---|---|---:|---|---:|---:|')
    for sp in ('train', 'pilot'):
        for lab in ('all_histories', 'E2_relevant_initial_small'):
            for t in ('t0', 't1', 't2'):
                b = O[sp][lab][t]
                w('| %s | %s | %s | %d (%d) | %d / %d | %d | %s |' % (sp, 'all' if lab == 'all_histories' else 'initial small', b['decision_index'],
                  b['eligible'], b['supported'], b['assigned'].get('small', 0), b['assigned'].get('large', 0), b['tasks_with_at_least_one'], fmt(b['share_of_episodes_reaching'])))
    w('')
    w('Per-task distributions of eligible counts are in the JSON (`decision_opportunities`); per-decision rows are in `per_decision`.')
    w('')
    w('## 3. Pre-action feedback before second/third decisions')
    w('')
    w('Field definitions:')
    for k, v in F['field_definitions'].items():
        w('- `%s`: %s' % (k, v))
    w('')
    w('| Partition | Histories | Decision | n | fail_class x frac_bin | previous actions | from zero-check tasks |')
    w('|---|---|---|---:|---|---|---:|')
    for sp in ('train', 'pilot'):
        for lab in ('all_histories', 'E2_relevant_initial_small'):
            for t in ('t1', 't2'):
                b = F[sp][lab][t]
                w('| %s | %s | %s | %d | %s | %s | %d |' % (sp, 'all' if lab == 'all_histories' else 'initial small', t, b['n'],
                  '; '.join('%s %d' % kv for kv in b['fail_class_x_frac_bin'].items()), '; '.join('%s %d' % kv for kv in b['prev_actions'].items()),
                  b['from_tasks_with_zero_visible_checks']))
    w('')
    w('TRAIN tasks with zero certified visible checks: %d; pilot: %d. Their only feedback is a load check.' % (F['train']['tasks_with_zero_visible_checks'], F['pilot']['tasks_with_zero_visible_checks']))
    w('')
    w('## 4. Outcome variation (frozen success endpoint)')
    w('')
    w('| Partition | Episodes | Success rate | Tasks | Tasks with within-task variation | all-success / all-failure tasks |')
    w('|---|---|---:|---:|---:|---|')
    for sp in ('train', 'pilot'):
        for lab in ('all_episodes', 'initial_small', 'reached_second_decision', 'initial_small_reached_second_decision'):
            b = Y[sp][lab]
            w('| %s | %s (%d) | %s | %d | %d of %d with >= 2 episodes | %d / %d |' % (sp, lab.replace('_', ' '), b['episodes'], fmt(b['success_rate']), b['tasks'],
              b['tasks_with_within_task_success_variation'], b['tasks_with_2plus_episodes'], b['tasks_all_success'], b['tasks_all_failure']))
    w('')
    for sp in ('train', 'pilot'):
        wb = Y[sp]['why_episodes_stop_before_decision_2']
        for lab in ('all_episodes', 'initial_small'):
            b = wb[lab]
            w('- %s, %s: %d episodes; %d stopped after a first-call visible pass (%d hidden success, %d hidden failure = visible false pass, %d on zero-check tasks); %d reached a second decision.' % (
                sp, lab.replace('_', ' '), b['episodes'], b['stopped_after_first_call_visible_pass'], b['of_which_hidden_success'],
                b['of_which_hidden_failure_visible_false_pass'], b['of_which_on_zero_visible_check_tasks'], b['reached_second_decision']))
    w('')
    w(Y['train']['why_episodes_stop_before_decision_2']['note'])
    w('')
    r = Y['train']['resources_all_episodes']
    w('TRAIN resources per episode (kept distinct): %.3f calls (%.3f large, %.3f small), frozen call penalty %.4f, '
      '%.1f completion tokens, %.1f prompt tokens, %.2f s LLM wall time. %s.' % (r['mean_model_calls'], r['mean_large_calls'], r['mean_small_calls'],
      r['mean_frozen_call_penalty'], r['mean_completion_tokens'], r['mean_prompt_tokens'], r['mean_llm_wall_seconds'], r['note']))
    w('')
    w('## 5. Candidate rules')
    w('')
    w('**(a) Not trained.** ' + st['statement'])
    a = st['archived_learned_policy']
    w('')
    w('Archived learner (context only): %s Objective `%s`, %d TRAIN episodes / %d tasks. Initial action by benchmark '
      '(mbpp, humaneval): %s. On its own histories, over every feedback path, it takes: %s. %s.' % (
          a['learner'], a['objective'], a['n_train_episodes'], a['n_train_tasks'],
          ', '.join(a['initial_action_by_x'].values()), ', '.join(a['on_policy_schedules_over_all_feedback_paths']), a['on_policy_note']))
    w('')
    w('**(b) Model-free disagreement opportunity (upper bound).** ' + D['definition'])
    w('')
    w('| Partition | Histories | Bound | Cells (multi-valued) | Decisions in multi-valued cells | by stage | Distinct tasks | vs closest prompt-only rule |')
    w('|---|---|---|---|---:|---|---:|---:|')
    for sp in ('train', 'pilot'):
        for lab in ('E2_relevant_initial_small', 'all_histories'):
            blk = D[sp][lab]
            for nm in ('U_A', 'U_B', 'U_raw', 'U_bench'):
                u = blk[nm]
                w('| %s | %s (%d supported) | %s | %d (%d) | %d | %s | %d | %d |' % (sp, 'initial small' if lab.startswith('E2') else 'all', blk['supported_eligible_second_third_decisions'],
                  nm, u['cells'], u['cells_with_more_than_one_history_value'], u['decisions_in_multi_valued_cells'],
                  ', '.join('%s %d' % kv for kv in u['by_t'].items()), u['distinct_tasks'], u['bound_vs_closest_prompt_only_rule']))
    w('')
    w('Bound definitions: ' + ' '.join('%s: %s.' % (nm, D['train']['E2_relevant_initial_small'][nm]['definition']) for nm in ('U_A', 'U_B', 'U_raw', 'U_bench')))
    ua = D['train']['E2_relevant_initial_small']['U_A']
    w('')
    w('TRAIN E2-relevant U_A: distinct tasks by family %s; per-task count of opportunity decisions %s (count: tasks).' % (ua['distinct_tasks_by_family'], ua['per_task_decision_count_distribution']))
    w('')
    sp_ = T['candidate_rules']['frozen_training_specification']
    w('**(c) Smallest frozen TRAIN/DEV-only specification (%s), not executed.**' % sp_['id'])
    w('')
    w('- Data: %s %s Never: %s' % (sp_['data']['fit_and_validation'], sp_['data']['pilot'], sp_['data']['never']))
    w('- Common structure: ' + sp_['common_structure'])
    w('- Prompt-only features: %s.' % '; '.join(sp_['features']['prompt_only']))
    w('- History-aware features: %s. %s' % ('; '.join(sp_['features']['history_aware']), sp_['features']['note']))
    w('- Class: ' + sp_['learner_class'])
    w('- Objective: %s Estimator: %s. Search: %s.' % (sp_['objective']['endpoint'], sp_['objective']['estimator'], sp_['objective']['search']))
    w('- Split: by %s; %s; seed %d; expected sizes %s.' % (sp_['split']['unit'], sp_['split']['procedure'], sp_['split']['seed'],
      {k: dict(v) for k, v in sp_['split']['expected_sizes'].items()}))
    w('- Complexity selection: ' + sp_['complexity_selection'])
    w('- Freeze: ' + sp_['frozen_record'])
    w('- Report after fitting: ' + '; '.join(sp_['required_report_after_fitting']) + '.')
    w('- References: ' + '; '.join(sp_['objective']['references']) + '.')
    w('')
    w('## 6. Precision')
    w('')
    w('%s. Half-width 0.05 needs **%d** independent tasks at the protocol\'s illustrative s_D^2 = 0.20 (%d at the worst bound). '
      'TRAIN has %d tasks, %d of them with a supported E2-relevant disagreement opportunity: enough for 0.05 at s_D^2 = 0.20: **%s**. '
      'At s_D^2 = 0.20 the half-width would be %s on those %d tasks and %s on all %d TRAIN tasks. %s' % (
          P['protocol_formula'], P['m_required_h0p05_s2_0p20'], P['m_required_h0p05_worst_s2_1'], P['train_tasks_total'],
          P['train_tasks_with_supported_disagreement_opportunity'], P['enough_for_h0p05_at_s2_0p20'],
          fmt(P['half_width_at_s2_0p20_with_opportunity_tasks']), P['train_tasks_with_supported_disagreement_opportunity'],
          fmt(P['half_width_at_s2_0p20_all_train_tasks']), P['train_tasks_total'], P['retrospective_caveat']))
    w('')
    dq = P['dev_planning_quantities']
    w('DEV planning quantities (%s): s0^2 = %.4f (%s); qbar = %.4f (%s); tau^2 bound = %.4f (%s).' % (dq['source'], dq['s0_squared'], dq['s0_definition'],
      dq['qbar'], dq['qbar_definition'], dq['tau2_upper_bound'], dq['tau2_definition']))
    w('')
    w('| Replicates per arm per task | Heterogeneity | Planning s^2 | Tasks for h = 0.05 | Tasks for h = 0.10 | h at 231 tasks (size arithmetic) | h at 330 tasks (size arithmetic) | Episodes at 330 tasks |')
    w('|---:|---|---:|---:|---:|---:|---:|---:|')
    for p in P['prospective_plan_table']:
        w('| %d | %s | %.4f | %d | %d | %.4f | %.4f | %d |' % (p['replicates_per_arm_per_task'], p['heterogeneity'], p['planning_s2'], p['tasks_for_h_0p05'],
          p['tasks_for_h_0p10'], p['half_width_at_231_tasks'], p['half_width_at_330_tasks'], p['physical_episodes_at_330_tasks']))
    w('')
    tp = P['task_pool_facts']
    w('Task pool: %d benchmark tasks; %d pilot, %d TRAIN, %d CONFIRM; untouched %d. %s' % (tp['benchmark_tasks'], tp['pilot_tasks_executed'],
      tp['train_tasks_used_for_learning'], tp['confirm_tasks_observed'], tp['untouched_tasks_in_benchmark'], tp['note']))
    w('')
    w('## Limitations')
    w('')
    for x in T['limitations']:
        w('- ' + x)
    w('')
    w('## Inputs')
    w('')
    w('| Path | sha256 | Use | Equals `%s` blob |' % T['source_commit'])
    w('|---|---|---|---|')
    for k, v in T['inputs'].items():
        w('| `%s` | `%s` | %s | %s |' % (k, v['sha256'][:16], v['use'], v['equals_blob_at_source_commit']))
    w('')
    return '\n'.join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-dir', default=DEFAULT_OUT, help='repository-relative or absolute output directory (write-once files)')
    a = ap.parse_args()
    out = Path(a.out_dir)
    out = out if out.is_absolute() else REPO / out
    T = analyse()
    body = json.dumps(T, indent=1, sort_keys=False, allow_nan=False) + '\n'
    md = summary_md(T) + '\n'
    out.mkdir(parents=True, exist_ok=True)
    with open(out / 'decision_opportunity_table.json', 'x') as f:      # write-once
        f.write(body)
    with open(out / 'REQ006_SUMMARY.md', 'x') as f:
        f.write(md)
    print(json.dumps(OrderedDict(conclusion=T['conclusion']['category'], decided_at=T['conclusion']['decided_at'],
                                 acceptance=T['acceptance'], decisive=T['conclusion']['decisive_counts']), indent=1))


if __name__ == '__main__':
    main()
