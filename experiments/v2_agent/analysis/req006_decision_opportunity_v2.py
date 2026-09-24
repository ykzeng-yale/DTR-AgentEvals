"""DTR-REQ-006, version 2: documentation corrections to the version 1 decision-opportunity table.

Scope (worker, not scientific lead). Deterministic, read-only analysis of committed records; no model inference, server,
GPU, network or Monte Carlo. Version 2 changes no count. It imports the UNCHANGED version 1 script
(experiments/v2_agent/analysis/req006_decision_opportunity.py), runs its analysis with one hardened loader, applies the
documentation corrections listed in CHANGES below, and proves that every other JSON path equals version 1. Version 1's
outputs stay in place as the historical first version.

Why a version 2 (independent reconciliation of version 1, re-derived here from the raw files):
  C1  The prose definition of frac_fail omitted the load-failure case (experiments/code_routing/agent.py validate():
      frac_fail = 1.0 when the reply has no code or the program returns no result, even when the task has zero visible
      checks, where n_fail / max(n, 1) would give 0).
  C2  The planning bound |V_H - V_P| <= q had no assumption list or primary citation (AGENTS.md research rules).
  C3  The archived table's L-S-L on-policy statement did not disclose that one on-path state has no table entry, so its S
      is the lookup default of experiments/code_routing/policies.table_policy (the default deployed by run.py).
  C4  CONFIRM-task lines of the mixed log files are now discarded from their raw episode_id prefix BEFORE JSON parsing
      (version 1 parsed each line, then dropped it by task id without using any outcome field).
  C5  The summary states full sha256 values, the task-ID-list hash definition, and the required statements explicitly.

Outputs (write-once, mode 'x'): <out>/decision_opportunity_table_v2.json and <out>/REQ006_SUMMARY_v2.md, with
<out> = results/code_routing/analysis/req006 by default. Version 1 outputs are always read from that default directory.
All recorded paths are repository-relative.

Usage:  .venv/bin/python experiments/v2_agent/analysis/req006_decision_opportunity_v2.py [--out-dir DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import inspect
import json
import re
from collections import Counter, OrderedDict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
CR = 'results/code_routing'
V1_SCRIPT = 'experiments/v2_agent/analysis/req006_decision_opportunity.py'
V2_SCRIPT = 'experiments/v2_agent/analysis/req006_decision_opportunity_v2.py'
POLICIES = 'experiments/code_routing/policies.py'
RUN_PY = 'experiments/code_routing/run.py'
AGENT_PY = 'experiments/code_routing/agent.py'
OUT_DEFAULT = CR + '/analysis/req006'
V1_JSON, V1_MD = 'decision_opportunity_table.json', 'REQ006_SUMMARY.md'
V2_JSON, V2_MD = 'decision_opportunity_table_v2.json', 'REQ006_SUMMARY_v2.md'
# Version 1 hashes as recorded when version 1 was handed over; version 2 refuses to run if version 1 changed.
V1_EXPECTED_SHA256 = {
    V1_SCRIPT: 'b57c9f9c965e4ddf39df06fbd38be52e5e6ab6e368dae13206c9aafbf815d8e8',
    OUT_DEFAULT + '/' + V1_JSON: '7ba262e592efd4c08d21d0e5d77147ae31c647946f776843039fdbe2a761708a',
    OUT_DEFAULT + '/' + V1_MD: '58a3c935dfe184627b5960a7ab445b78e2ab92b9be9c91b79a0bbabaf79f04a4',
}
# Every line of the four outcome files starts with the episode id; the task id is read from it without parsing.
LINE_ID = re.compile(r'^\{"episode_id": "(?P<eid>(?P<stage>log|pilot):(?P<task>[^"#]+)#(?P<run>\d+))"')


def sha256_file(rel: str) -> str:
    return hashlib.sha256((REPO / rel).read_bytes()).hexdigest()


def load_module(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


v1 = load_module('req006_v1', V1_SCRIPT)
POL = load_module('code_routing_policies', POLICIES)

PREPARSE = OrderedDict()        # per-file line accounting of the hardened loader
KEPT = {}                       # kept (non-CONFIRM) records per partition, for the correction evidence below


# ------------------------------------------------------------------ C4: CONFIRM lines discarded before parsing
def _read_filtered(rel: str, part: str, confirm: set):
    kept, n_lines, n_conf, conf_eids = [], 0, 0, set()
    for _, line in v1.read_lines(rel):
        n_lines += 1
        m = LINE_ID.match(line)
        if m is None or m.group('stage') != part:
            raise SystemExit('%s: a line does not start with a %s episode_id; refusing to parse it to classify it' % (rel, part))
        if m.group('task') in confirm:
            n_conf += 1; conf_eids.add(m.group('eid'))
            continue                                        # CONFIRM-task line: never parsed
        r = json.loads(line)
        if r['episode_id'] != m.group('eid') or ('task_uid' in r and r['task_uid'] != m.group('task')):
            raise SystemExit('%s: parsed episode_id/task_uid disagrees with the raw prefix for %s' % (rel, m.group('eid')))
        kept.append(r)
    PREPARSE[rel] = OrderedDict(nonblank_lines=n_lines, confirm_task_lines_discarded_unparsed=n_conf,
                                lines_parsed=len(kept))
    return kept, n_conf, conf_eids


def load_partition_preparse(part: str, confirm: set):
    """Drop-in replacement for version 1 load_partition with the same return value."""
    eps, n_conf_eps, conf_ids = _read_filtered('%s/%s/episodes.jsonl' % (CR, part), part, confirm)
    decs, n_conf_decs, _ = _read_filtered('%s/%s/decisions.jsonl' % (CR, part), part, confirm)
    KEPT[part] = (eps, decs)
    return eps, decs, dict(confirm_episode_records_excluded=n_conf_eps, confirm_episode_ids_excluded=len(conf_ids),
                           confirm_decision_records_excluded=n_conf_decs)


v1.load_partition = load_partition_preparse     # analyse() resolves load_partition as a module global at call time


# ------------------------------------------------------------------ C1 evidence: frac_fail outside the ratio formula
def frac_fail_exceptions(part: str) -> OrderedDict:
    eps, _ = KEPT[part]
    c = Counter(); tasks = set(); kinds = Counter()
    for e in eps:
        if e.get('error'):
            continue
        decs = e['decisions']
        for i, d in enumerate(decs):
            v = d['validation']
            c['validations'] += 1
            c['n_asserts_not_equal_episode_n_visible_checks'] += int(v['n_asserts'] != e['n_visible_checks'])
            if v['frac_fail'] == v['n_fail'] / max(v['n_asserts'], 1):
                continue
            c['frac_fail_not_equal_n_fail_over_max_n_1'] += 1
            c['of_which_pre_action_state_of_a_later_decision'] += int(i + 1 < len(decs))
            c['of_which_frac_fail_1_with_zero_checks_and_zero_fails'] += int(v['frac_fail'] == 1.0 and v['n_asserts'] == 0 and v['n_fail'] == 0)
            c['of_which_fail_class_exception'] += int(v['fail_class'] == 'exception')
            kinds['%s|%s' % (v['fail_class'], v['err'])] += 1
            tasks.add(e['task_uid'])
    out = OrderedDict((k, c[k]) for k in ('validations', 'n_asserts_not_equal_episode_n_visible_checks',
                                          'frac_fail_not_equal_n_fail_over_max_n_1',
                                          'of_which_pre_action_state_of_a_later_decision',
                                          'of_which_frac_fail_1_with_zero_checks_and_zero_fails',
                                          'of_which_fail_class_exception'))
    out['fail_class_err'] = dict(sorted(kinds.items()))
    out['tasks'] = sorted(tasks)
    return out


FRAC_FAIL_V2 = ('fraction of visible checks failed in the most recent validation, as recorded by '
                'experiments/code_routing/agent.py validate(): 1.0 when the reply contained no code or the validation '
                'program returned no result (load failure, crash or timeout), whatever the number of visible checks, '
                'including tasks with zero visible checks; otherwise n_fail / max(n_visible_checks, 1). '
                'frac_bin = "all_checks_failed" if 1.0 else "partial". All tables use the recorded value.')


# ------------------------------------------------------------------ C2: assumptions and citations of the planning bound
CONTRAST_BOUND = OrderedDict(
    statement=('|V_H - V_P| <= P(the two routers\' executions differ) <= q = P(reach decision 2 | a0 = S), for the terminal '
               'success endpoint, per task and on average over tasks; hence |Delta_i| <= q_i and '
               'Var(Delta_i) <= E[Delta_i^2] <= E[q_i^2] (the tau^2 bound).'),
    assumptions=[
        'A1 common first call: both routers take a0 = S with the same prompt, decoding, model build and harness, so the '
        'law of the first call and of its visible validation is the same under both.',
        'A2 routing-only difference: the routers differ only in the action chosen at decisions 2 and 3, and given the same '
        'history and action the next call and its validation have the same law under both; they cannot differ before '
        'decision 2 is reached, and a first-call visible pass ends the episode (absorbing stop).',
        'A3 bounded endpoint: terminal success lies in [0, 1] (it is binary here).',
        'A4 planning transfer: q is estimated by qbar from TRAIN log episodes with a0 = S, whose first call matches A1 '
        'because the logger blocked a0 independently of outcomes; using qbar for a prospective study additionally assumes '
        'the same task distribution and serving stack. qbar is a DEVELOPMENT estimate, not a guarantee.'],
    argument=('Couple the two executions so that they share every call and validation until the first decision at which '
              'the routers choose differently; by A1-A2 the two laws agree up to that point, so this is a valid coupling. '
              'The paths can differ only if that decision exists, and it is at decision 2 or later, so {paths differ} is '
              'contained in {decision 2 is reached}. For an endpoint in [0, 1] (A3) the coupling inequality gives '
              '|E_H Y - E_P Y| <= P(paths differ) <= q. It is stated for success only.'),
    status='standard coupling inequality applied to this design; not a new result',
    references=['Lindvall (1992), Lectures on the Coupling Method, Wiley (coupling inequality)',
                'Levin, Peres and Wilmer (2017), Markov Chains and Mixing Times, 2nd ed., American Mathematical Society, '
                'chapter 4 (total variation distance and coupling)'])

QBAR_V2 = ('mean over TRAIN tasks of the share of initial-small episodes that reach a second decision; it estimates '
           'q = P(reach decision 2 | a0 = S). Under assumptions A1-A4 of contrast_bound (common first call, routing-only '
           'difference after it, success in [0, 1], planning transfer), the coupling inequality gives '
           '|V_H - V_P| <= P(reach a history where they disagree) <= q for the success endpoint (Lindvall 1992; '
           'Levin, Peres and Wilmer 2017, chapter 4); a standard bound, not a new result.')
TAU2_V2 = ('task-effect heterogeneity bound: Var(Delta_i) <= E[Delta_i^2] <= E[q_i^2], from |Delta_i| <= q_i under the '
           'same assumptions A1-A4, estimated unbiasedly per task')


# ------------------------------------------------------------------ C3: archived table on-policy paths and table defaults
def archived_on_policy(T: dict) -> OrderedDict:
    lp = json.loads((REPO / CR / 'learned_policy.json').read_text())
    table = {tuple(k): v for k, v in lp['table']}
    default = inspect.signature(POL.table_policy).parameters['default'].default
    run_src = (REPO / RUN_PY).read_text()
    run_uses_default = bool(re.search(r"P\.table_policy\(\{tuple\(k\): v for k, v in json\.loads\(lp\.read_text\(\)\)\['table'\]\}\)", run_src))
    # occupancy of each tabular state among the TRAIN decisions of this table (per_decision rows, all histories)
    cols = T['per_decision_columns']
    ix = {c: cols.index(c) for c in ('split', 't', 'family', 'fail_class', 'prev_actions')}
    occ = Counter()
    for r in T['per_decision']:
        if r[ix['split']] != 'train':
            continue
        prev = r[ix['prev_actions']]
        s = dict(t=r[ix['t']], x_humaneval=int(r[ix['family']] == 'humaneval'), fail_class=r[ix['fail_class']],
                 prev_actions=tuple('SL'.index(ch) for ch in prev))
        occ[POL.state_key(s)] += 1
    paths, missing = [], OrderedDict()

    def act(key):
        if key in table:
            return int(table[key]), True
        missing.setdefault(key, OrderedDict(key=list(key), train_decisions_at_state=occ.get(key, 0),
                                            action_from_default='SL'[int(default)]))
        return int(default), False

    for x in (0, 1):
        a0, _ = act((0, x, 'start', -1))
        for fc1 in ('assertion', 'exception'):
            k1 = (1, x, fc1, a0); a1, in1 = act(k1)
            for fc2 in ('assertion', 'exception'):
                k2 = (2, x, fc2, a1); a2, in2 = act(k2)
                paths.append(OrderedDict(x_humaneval=x, feedback=[fc1, fc2], actions=''.join('SL'[z] for z in (a0, a1, a2)),
                                         keys_missing_from_table=[list(k) for k, ok in ((k1, in1), (k2, in2)) if not ok]))
    schedules = sorted({p['actions'] for p in paths})
    if schedules != T['candidate_rules']['training_status']['archived_learned_policy']['on_policy_schedules_over_all_feedback_paths']:
        raise SystemExit('on-policy schedules differ from version 1')
    return OrderedDict(
        paths=paths, missing=list(missing.values()), default=default, run_py_uses_default=run_uses_default,
        n_table_entries=len(table),
        n_train_states_occupied=len(occ), train_states_occupied_not_in_table=sorted(list(k) for k in occ if k not in table))


# ------------------------------------------------------------------ comparison with version 1
def diff_paths(a, b, path=''):
    """Paths at which JSON values a (version 1) and b (version 2) differ; '+' added in b, '-' removed from b."""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a:
            p = '%s.%s' % (path, k) if path else k
            out += diff_paths(a[k], b[k], p) if k in b else ['-' + p]
        out += ['+' + ('%s.%s' % (path, k) if path else k) for k in b if k not in a]
    elif isinstance(a, list) and isinstance(b, list):
        for i in range(min(len(a), len(b))):
            out += diff_paths(a[i], b[i], '%s[%d]' % (path, i))
        out += ['+%s[%d]' % (path, i) for i in range(len(a), len(b))] + ['-%s[%d]' % (path, i) for i in range(len(b), len(a))]
    elif a != b or type(a) is not type(b):
        out.append('~' + path)
    return out


DECLARED = [
    '~script', '~script_sha256', '+version', '+analysis_core_script', '+analysis_core_script_sha256', '+revision',
    '~pre_action_feedback.field_definitions.frac_fail', '+pre_action_feedback.frac_fail_formula_exceptions',
    '~precision.dev_planning_quantities.qbar_definition', '~precision.dev_planning_quantities.tau2_definition',
    '+precision.dev_planning_quantities.contrast_bound',
    '~candidate_rules.training_status.archived_learned_policy.on_policy_note',
    '+candidate_rules.training_status.archived_learned_policy.on_policy_paths',
    '+candidate_rules.training_status.archived_learned_policy.on_policy_table_default',
    '+conclusion.basis_note', '+limitations[7]',
]


# ------------------------------------------------------------------ build version 2
def build():
    for rel, want in V1_EXPECTED_SHA256.items():
        got = sha256_file(rel)
        if got != want:
            raise SystemExit('version 1 file %s changed (sha256 %s, expected %s); refusing to build version 2' % (rel, got, want))
    v1_json = json.loads((REPO / OUT_DEFAULT / V1_JSON).read_text())

    T = v1.analyse()
    if T['script_sha256'] != v1_json['script_sha256']:
        raise SystemExit('version 1 script hash differs from the hash recorded in version 1')
    confirm = set(json.loads((REPO / CR / 'design.json').read_bytes())['confirm_tasks'])
    if any(r[2] in confirm for r in T['per_decision']) or any(r[0] in confirm for r in T['per_task']):
        raise SystemExit('a CONFIRM task entered the table')

    # C1
    ffx = OrderedDict((sp, frac_fail_exceptions(part)) for sp, part in (('train', 'log'), ('pilot', 'pilot')))
    for sp, b in ffx.items():
        n = b['frac_fail_not_equal_n_fail_over_max_n_1']
        if (b['of_which_frac_fail_1_with_zero_checks_and_zero_fails'] != n or b['of_which_fail_class_exception'] != n
                or b['n_asserts_not_equal_episode_n_visible_checks']):
            raise SystemExit('%s: frac_fail exceptions are not all zero-check load failures; revise the note' % sp)
    T['pre_action_feedback']['field_definitions']['frac_fail'] = FRAC_FAIL_V2
    T['pre_action_feedback']['frac_fail_formula_exceptions'] = OrderedDict(
        note=('validations whose recorded frac_fail differs from n_fail / max(n_asserts, 1); all are load-time failures '
              '(no result line) on tasks with zero visible checks (frac_fail = 1.0, n_asserts = n_fail = 0, fail_class = '
              'exception; verified by the counters below). Counts in the tables are unchanged because they use the recorded '
              'state.'), **ffx)
    # C2
    dq = T['precision']['dev_planning_quantities']
    dq['qbar_definition'] = QBAR_V2
    dq['tau2_definition'] = TAU2_V2
    dq['contrast_bound'] = CONTRAST_BOUND
    # C3
    op = archived_on_policy(T)
    alp = T['candidate_rules']['training_status']['archived_learned_policy']
    miss_txt = '; '.join('(t=%d, x_humaneval=%d, fail_class=%s, previous action %s): %d TRAIN decisions, action %s from the default'
                         % (m['key'][0], m['key'][1], m['key'][2], 'SL'[m['key'][3]] if m['key'][3] >= 0 else 'none',
                            m['train_decisions_at_state'], m['action_from_default']) for m in op['missing'])
    alp['on_policy_note'] = (
        alp['on_policy_note'] + '. Disclosure: %d on-path state(s) without a table entry, because no TRAIN decision occupied '
        'it (%s); there the action is the lookup default P(large) = %s of %s table_policy, the same default the live '
        'stage of %s deployed (%s), not a fitted value' % (
            len(op['missing']), miss_txt or 'none', op['default'], POLICIES, RUN_PY,
            'call without a default override found' if op['run_py_uses_default'] else 'call NOT found; check by hand'))
    alp['on_policy_paths'] = op['paths']
    alp['on_policy_table_default'] = OrderedDict(
        default_p_large=op['default'], source='%s table_policy(table, default=%s)' % (POLICIES, op['default']),
        run_py_live_stage_uses_it=op['run_py_uses_default'], missing_on_path_states=op['missing'],
        n_table_entries=op['n_table_entries'], n_train_states_occupied=op['n_train_states_occupied'],
        train_states_occupied_not_in_table=op['train_states_occupied_not_in_table'])
    # conclusion basis (descriptive decomposition of flag 1a; no new decision)
    wb = T['outcome_variation']['train']['why_episodes_stop_before_decision_2']['initial_small']
    dc = T['conclusion']['decisive_counts']
    T['conclusion']['basis_note'] = (
        'The category rests on flag 1a alone (flag 1b is false). Of the %d E2-relevant TRAIN episodes, %d (%.1f%%) ended '
        'after a first-call visible pass (%d hidden success; %d hidden failure = visible false pass; %d on zero-visible-check '
        'tasks) and %d reached a second decision. Rule R006-v1 transfers the section 5 redesign flag of '
        'docs/experiment_protocol_v2.md, written for a prospective 20-issue development pilot, to this archived '
        'MBPP/HumanEval harness; whether that transfer is appropriate is a lead decision (see "What would change the '
        'category"). Descriptive DEVELOPMENT counts only.' % (
            wb['episodes'], wb['stopped_after_first_call_visible_pass'], 100.0 * wb['stopped_after_first_call_visible_pass'] / wb['episodes'],
            wb['of_which_hidden_success'], wb['of_which_hidden_failure_visible_false_pass'], wb['of_which_on_zero_visible_check_tasks'],
            wb['reached_second_decision']))
    if wb['reached_second_decision'] != dc['train_E2_relevant_reaching_second_decision']:
        raise SystemExit('basis note does not reconcile with the decisive count')
    T['limitations'].append(
        'The planning bound |V_H - V_P| <= q and the tau^2 bound need assumptions A1-A4 (precision.dev_planning_quantities.'
        'contrast_bound), in particular the same first-call law and serving stack in a prospective study as in the archived log.')

    changes = [
        OrderedDict(id='C1', where='pre_action_feedback.field_definitions.frac_fail',
                    version_1=v1_json['pre_action_feedback']['field_definitions']['frac_fail'], version_2=FRAC_FAIL_V2,
                    why=('the version 1 prose omitted the load-failure branch of validate() in %s, which records frac_fail = 1.0 '
                         'with n_fail = n_asserts = number of visible checks; on a zero-check task this is 1.0 while the stated '
                         'ratio is 0' % AGENT_PY),
                    evidence=('TRAIN: %d of %d validations (%d of them the pre-action state of a later decision) on tasks %s; '
                              'pilot: %d' % (ffx['train']['frac_fail_not_equal_n_fail_over_max_n_1'], ffx['train']['validations'],
                                             ffx['train']['of_which_pre_action_state_of_a_later_decision'],
                                             ', '.join(ffx['train']['tasks']), ffx['pilot']['frac_fail_not_equal_n_fail_over_max_n_1'])),
                    effect_on_counts='none: every table uses the recorded state'),
        OrderedDict(id='C2', where='precision.dev_planning_quantities (qbar_definition, tau2_definition, contrast_bound)',
                    version_1='bound stated without assumptions or primary citation',
                    version_2='assumptions A1-A4, the coupling argument and primary references added; labelled a standard bound',
                    why='AGENTS.md: attach assumptions and primary citations to mathematical claims; do not call known theory novel',
                    evidence='statement unchanged; see contrast_bound', effect_on_counts='none'),
        OrderedDict(id='C3', where='candidate_rules.training_status.archived_learned_policy',
                    version_1='L-S-L on every feedback path, default lookup not disclosed',
                    version_2='per-path actions with the table keys used; the missing on-path key and its TRAIN occupancy disclosed',
                    why='the S at the missing state comes from the lookup default, not from a fitted value',
                    evidence=miss_txt or 'no missing key', effect_on_counts='none: the L-S-L statement holds under deployment semantics'),
        OrderedDict(id='C4', where='loader (all outcome files)',
                    version_1='each line parsed as JSON, then CONFIRM-task records dropped by task id; outcome fields never used',
                    version_2='task id read from the raw episode_id prefix; CONFIRM-task lines discarded before JSON parsing',
                    why='strengthens the statement that no CONFIRM outcome was read',
                    evidence='; '.join('%s: %d lines, %d CONFIRM-task lines discarded unparsed, %d parsed' % (
                        k, v['nonblank_lines'], v['confirm_task_lines_discarded_unparsed'], v['lines_parsed']) for k, v in PREPARSE.items()),
                    effect_on_counts='none: the same records are kept and the same numbers excluded'),
        OrderedDict(id='C5', where='summary',
                    version_1='16-hex sha256 prefixes; task-ID hash definition only in the JSON; required statements spread over sections',
                    version_2='full sha256 for inputs, scripts and version 1 outputs; hash definition stated; required-statement block; basis note for flag 1a',
                    why='the summary must state the inputs and their sha256 and the required items explicitly',
                    evidence='-', effect_on_counts='none'),
    ]
    no_change = [
        'bound_vs_closest_prompt_only_rule (floor(n_cell/2)) is labelled in version 1 as a distance to the closest constant '
        'rule, not as disagreement with a trained prompt-only rule: correct as written.',
        'The task-ID list hash uses compact separators; version 1 defines it in split_reconciliation.ids_sha256_definition '
        '(now also stated in the summary).',
        'The dependence of REPAIR on transferring the section 5 flag was already disclosed in version 1 ("What would change '
        'the category"); version 2 adds the descriptive basis note.',
        'The workflow reconciler reported reproducing every version 1 count (splits, exclusions, occupancy, feedback, '
        'outcome variation, U_A/U_B/U_raw/U_bench, precision arithmetic); version 2 changes no count, as the path comparison '
        'in revision.comparison_with_version_1 verifies.']

    revision = OrderedDict(
        version=2,
        supersedes=OrderedDict(
            note='version 1 files are kept unchanged as the historical first version; read version 2',
            files=OrderedDict((rel, sha) for rel, sha in V1_EXPECTED_SHA256.items())),
        counts_changed=False,
        confirm_exclusion=OrderedDict(
            method=('task id read from the leading "episode_id" of each raw line; CONFIRM-task lines discarded before JSON '
                    'parsing; kept lines re-checked after parsing; no file under results/code_routing/live/ or branch/ opened; '
                    'whole files hashed for provenance only'),
            files=PREPARSE),
        changes=changes, reconciler_points_without_change=no_change)
    final = OrderedDict(
        request=T['request'], version=2, lead_source=T['lead_source'], source_commit=T['source_commit'],
        script=V2_SCRIPT, script_sha256=sha256_file(V2_SCRIPT),
        analysis_core_script=V1_SCRIPT, analysis_core_script_sha256=T['script_sha256'], revision=revision)
    final.update((k, v) for k, v in T.items() if k not in final)

    # machine check: every JSON path equals version 1 except the declared ones
    diffs = diff_paths(v1_json, json.loads(json.dumps(final)))
    undeclared = [d for d in diffs if d not in DECLARED]
    unused = [d for d in DECLARED if d not in diffs]
    if undeclared or unused:
        raise SystemExit('version comparison failed: undeclared %s; declared but absent %s' % (undeclared, unused))
    revision['comparison_with_version_1'] = OrderedDict(
        method='recursive comparison of every JSON path of version 1 with version 2 (dict keys, list items, scalar values and types)',
        paths_differing=diffs, all_differences_declared=True,
        legend='~ value changed, + added in version 2, - removed',
        numeric_tables_identical=not any(d.lstrip('~+-').startswith(p) for d in diffs for p in (
            'acceptance', 'split_reconciliation', 'probability_and_state_verification', 'decision_opportunities',
            'outcome_variation', 'per_task', 'per_decision', 'candidate_rules.disagreement_opportunity',
            'conclusion.decisive_counts', 'conclusion.category')))
    return final


# ------------------------------------------------------------------ summary
def summary_v2(T: dict) -> str:
    C = T['conclusion']; dc = C['decisive_counts']; A = T['acceptance']; R = T['revision']
    S = T['split_reconciliation']; ua = T['candidate_rules']['disagreement_opportunity']['train']['E2_relevant_initial_small']['U_A']
    L = []
    w = L.append
    w('# DTR-REQ-006 decision-opportunity table, version 2 (retrospective, DEVELOPMENT-only)')
    w('')
    w('Version 2 corrects the documentation of version 1 and changes no count. Generated by `%s` (sha256 `%s`), which '
      'imports the unchanged version 1 script `%s` (sha256 `%s`, equal to the hash recorded in version 1) and runs its '
      'analysis with a hardened CONFIRM filter. A comparison of every JSON path with version 1 finds differences only at '
      'the %d declared paths listed in `revision.comparison_with_version_1`; all numeric tables are identical: **%s**. '
      'Version 1 (`%s`, `%s`) stays unchanged as the historical first version. Written once; do not edit by hand. '
      'Machine-readable table: `%s`.' % (
          T['script'], T['script_sha256'], T['analysis_core_script'], T['analysis_core_script_sha256'],
          len(R['comparison_with_version_1']['paths_differing']), R['comparison_with_version_1']['numeric_tables_identical'],
          V1_JSON, V1_MD, V2_JSON))
    w('')
    w('## Required statements')
    w('')
    w('- **Evidence status.** Retrospective DEVELOPMENT evidence only, from the archived TRAIN-task log and the pilot of '
      'the MBPP/HumanEval code-routing study. Not confirmatory and not an effect estimate. No router was fitted and no '
      'counterfactual success is predicted. No model inference, server, GPU, network or Monte Carlo was used. The frozen '
      'success and resource endpoints are used as recorded.')
    pp = R['confirm_exclusion']['files']
    w('- **No live or CONFIRM outcome was read.** No file under `results/code_routing/live/` or `results/code_routing/branch/` '
      'was opened. The randomized-log files also hold the records of the %d CONFIRM tasks. Each line\'s task id was read from '
      'its leading `episode_id`, and every CONFIRM-task line was discarded before JSON parsing: %s. No field of those lines '
      'was parsed or used. Whole files were hashed for provenance only. `design.json` `confirm_tasks` was used only to '
      'exclude those tasks and to report split sizes. CONFIRM-task rows in the table: **%d**.' % (
          S['counts']['confirm'],
          '; '.join('`%s` %d of %d lines' % (k, v['confirm_task_lines_discarded_unparsed'], v['nonblank_lines']) for k, v in pp.items()),
          A['confirm_task_rows_in_table']))
    w('- **Acceptance (Step 0).** Split IDs and denominators reconcile to `design.json`: %s. Logged probabilities, actions, '
      '`b_obs`, draws and states match `decisions.jsonl`: %d mismatches over %d check counters (%d TRAIN and %d pilot '
      'decisions). Inputs equal the blobs at `%s`: %s.' % (
          A['split_ids_and_denominators_reconcile'], A['probability_action_state_mismatches'], A['checks_counted'],
          T['probability_and_state_verification']['log']['decisions'], T['probability_and_state_verification']['pilot']['decisions'],
          T['source_commit'], A['inputs_equal_source_commit_blobs']))
    w('- **Decisive counts (TRAIN, 231 tasks).** E2-relevant log episodes (initial action small): %d. Of these, %d (%.1f%%) '
      'reach an eligible second decision (flag threshold 50%%, i.e. %d). All TRAIN episodes reaching a second decision: '
      '%.1f%%. Supported E2-relevant second/third decisions: %d. Of these, %d, in %d distinct tasks, lie in prompt cells '
      'with more than one history value (model-free upper bound U_A; %d vs the closest prompt-only rule). Tasks needed '
      'for half-width 0.05 at the protocol s_D^2 = 0.20: %d. Untouched tasks left in the 591-task benchmark: %d.' % (
          dc['train_E2_relevant_episodes'], dc['train_E2_relevant_reaching_second_decision'],
          100 * dc['train_E2_relevant_share_reaching_second_decision'], int(-(-dc['train_E2_relevant_episodes'] // 2)),
          100 * dc['train_all_share_reaching_second_decision'], dc['train_E2_relevant_supported_second_third_decisions'],
          dc['train_E2_relevant_upper_bound_decisions_U_A'], dc['train_E2_relevant_upper_bound_tasks_U_A'],
          ua['bound_vs_closest_prompt_only_rule'], dc['tasks_needed_h0p05_protocol_s2_0p20'], dc['untouched_tasks_in_benchmark']))
    w('- **Are the E2 candidate rules trained?** **No.** Neither the prompt-only nor the history-aware depth-two router of '
      'the primary history contrast has been trained on these records, so realized disagreement is unknown. The only learned '
      'code-routing policy is the archived tabular fitted-Q table. It is not the E2 class, and on its own histories it '
      'takes L-S-L on every feedback path; one of those S actions is a lookup default (section 5(a)). The smallest frozen '
      'TRAIN/DEV-only training specification (`%s`) is in section 5(c) and was not executed.' % T['candidate_rules']['frozen_training_specification']['id'])
    w('- **Conclusion: %s**, produced by Rule R006-v1 at %s. The rule was fixed in the version 1 script before its first '
      'complete TRAIN pass, and its thresholds are copied from protocol text; the full rule and disclosure are in the '
      'Conclusion section. Flag 1a fires: %s. Flag 1b fires: %s.' % (C['category'], C['decided_at'], dc['flag_1a_fires'], dc['flag_1b_fires']))
    w('- **Basis of the category.** ' + C['basis_note'])
    w('- **Limitations.** See the Limitations section. The main ones: realized disagreement is unknown because the rules '
      'are untrained, occupancy depends on the uniform logger, family = benchmark with task ids assumed independent, and '
      'the planning bound needs assumptions A1-A4.')
    w('')
    w('### Inputs and scripts (full sha256)')
    w('')
    w('| Path | sha256 | Use | Equals `%s` blob |' % T['source_commit'])
    w('|---|---|---|---|')
    for k, v in T['inputs'].items():
        w('| `%s` | `%s` | %s | %s |' % (k, v['sha256'], v['use'], v['equals_blob_at_source_commit']))
    w('| `%s` | `%s` | version 2 script | - |' % (T['script'], T['script_sha256']))
    w('| `%s` | `%s` | version 1 analysis core, imported unchanged | - |' % (T['analysis_core_script'], T['analysis_core_script_sha256']))
    for rel, sha in R['supersedes']['files'].items():
        if rel != V1_SCRIPT:
            w('| `%s` | `%s` | version 1 output, kept unchanged | - |' % (rel, sha))
    w('')
    w('Task-ID list hashes (section 1): %s.' % S['ids_sha256_definition'])
    w('')
    w('## Changes from version 1')
    w('')
    w('| Id | Where | Change | Why | Evidence (raw files) | Effect on counts |')
    w('|---|---|---|---|---|---|')
    for c in R['changes']:
        w('| %s | `%s` | %s | %s | %s | %s |' % (c['id'], c['where'], c['version_2'], c['why'], c['evidence'], c['effect_on_counts']))
    w('')
    w('Reconciler points that needed no change:')
    for x in R['reconciler_points_without_change']:
        w('- ' + x)
    w('')
    cb = T['precision']['dev_planning_quantities']['contrast_bound']
    w('**Planning bound (C2).** %s Assumptions: %s Argument: %s Status: %s. References: %s.' % (
        cb['statement'], ' '.join(cb['assumptions']), cb['argument'], cb['status'], '; '.join(cb['references'])))
    w('')
    # version 1 body (from Scope to before its Inputs section), rendered from the version 2 table
    body = v1.summary_md(T).split('\n')
    i0 = next(i for i, l in enumerate(body) if l.startswith('**Scope.**'))
    i1 = next(i for i, l in enumerate(body) if l == '## Inputs')
    w('---')
    w('')
    w('*The sections below are the version 1 report body, rendered from the version 2 table; their counts equal version 1.*')
    w('')
    L.extend(body[i0:i1])
    while L and L[-1] == '':
        L.pop()
    L.append('')
    return '\n'.join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-dir', default=OUT_DEFAULT, help='repository-relative or absolute output directory (write-once files)')
    a = ap.parse_args()
    out = Path(a.out_dir)
    out = out if out.is_absolute() else REPO / out
    T = build()
    body = json.dumps(T, indent=1, sort_keys=False, allow_nan=False) + '\n'
    md = summary_v2(T) + '\n'
    out.mkdir(parents=True, exist_ok=True)
    with open(out / V2_JSON, 'x') as f:      # write-once
        f.write(body)
    with open(out / V2_MD, 'x') as f:
        f.write(md)
    print(json.dumps(OrderedDict(conclusion=T['conclusion']['category'], decided_at=T['conclusion']['decided_at'],
                                 comparison=T['revision']['comparison_with_version_1'],
                                 preparse=T['revision']['confirm_exclusion']['files']), indent=1))


if __name__ == '__main__':
    main()
