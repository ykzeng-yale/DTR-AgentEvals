"""Source-bound corrected A6 report (DTR-REQ-001, item 1). POST-HOC reporting; not pre-registered.

No model call, candidate execution, fitting, resampling or Monte Carlo. Every row is re-derived from the committed
raw records and then checked against the lead's pinned audits in docs/audits/. A disagreement beyond 1e-12, a missing
audit, or a raw input whose SHA-256 differs from the hash an audit pinned stops the run BEFORE anything is written.

Each row carries an analysis class, endpoint, target, comparator and denominator, so whole-policy contrasts, pooled
repair contrasts, the realized-frame conditional target and selected-cohort analyses are never read as one another.
No row estimates the primary fixed-benchmark branch target; it is listed as open.

Original cohorts, metrics and values are retained. why_null.json and why_null_corrected.json stay byte-identical;
their numbers are reproduced here, so this is also the generator the corrected JSON lacked. Reproducing a number
does not endorse the reading it was given: withdrawn readings are listed with the lead's replacement wording.

Outputs: results/code_routing/analysis/a6_report.json and a6_report.md (the Markdown is rendered from the JSON).
"""
from __future__ import annotations
import collections, csv, hashlib, json, math, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / 'results' / 'code_routing'
AUD = ROOT / 'docs' / 'audits'
OUT_JSON = RES / 'analysis' / 'a6_report.json'
OUT_MD = RES / 'analysis' / 'a6_report.md'
TOL = 1e-12

AUDITS = dict(
    WN4='why_null_audit_4f9abe4.json', WNA='why_null_audit_aac69b5.json', RD='routing_diagnosis_338425b.json',
    CF='conditional_branch_frame_audit_981f7b9.json', LK='theory_branch_linkage_audit_20260920.json',
    LN='branch_linearization_audit_29ee443.json')

# raw input -> (audit, key path to the hash that audit pinned)
PINNED_INPUTS = {
    'results/code_routing/log/episodes.jsonl': ('WN4', ['source_hashes', 'results/code_routing/log/episodes.jsonl']),
    'results/code_routing/live/episodes.jsonl': ('WN4', ['source_hashes', 'results/code_routing/live/episodes.jsonl']),
    'results/code_routing/analysis/frontier_live.csv': ('WN4', ['source_hashes', 'results/code_routing/analysis/frontier_live.csv']),
    'results/code_routing/analysis/why_null.json': ('WN4', ['source_hashes', 'results/code_routing/analysis/why_null.json']),
    'results/code_routing/analysis/why_null_corrected.json': ('WNA', ['source_hashes', 'results/code_routing/analysis/why_null_corrected.json']),
    'results/code_routing/branch/episodes.jsonl': ('CF', ['inputs', 'branch_episodes', 'sha256']),
    'results/code_routing/branch/branch_plan.json': ('CF', ['inputs', 'branch_plan', 'sha256']),
    'results/code_routing/design.json': ('CF', ['inputs', 'design', 'sha256']),
    'results/code_routing/visible_tests.json': ('RD', ['input_sha256', 'results/code_routing/visible_tests.json']),
}

CLASSES = {
    'whole_policy': 'Root-to-terminal outcome of a fixed policy on all 330 CONFIRM tasks; equal task weight over the '
                    'planned repeated executions (2 live runs per task per policy).',
    'initial_action_logger_continued': 'Root-to-terminal contrast of the two initial actions, each followed by the '
                    'randomized logger; all 330 CONFIRM tasks, equal task weight. Final-outcome rows compare two '
                    'stochastic regimes (force the initial action, then use the logger), not the all-large/all-small '
                    'live policies. First-candidate rows end before any continuation.',
    'pooled_repair': 'Contrast at a repair decision among histories the logger reached, pooled over episodes or '
                     'prefixes; weights are realized eligible counts, not tasks.',
    'realized_frame': 'Conditional on the realized 564-prefix frame F and the realized log. SECONDARY target.',
    'selected_cohort': 'Restricted to tasks selected on realized action support or realized denominators; changes '
                       'cohort and weights. Exploratory only.',
    'descriptive': 'Counts or occupancy of realized records; no causal contrast target.',
}


class AuditMismatch(RuntimeError):
    pass


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def jsonl(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


def mean(v):
    return sum(v) / len(v)


def summary(v):
    m = mean(v)
    return dict(n=len(v), mean=m, se=math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1) / len(v)))


def dig(obj, path):
    for k in path:
        obj = obj[k]
    return obj


def load_audits(audit_dir=AUD):
    out = {}
    for key, name in AUDITS.items():
        p = Path(audit_dir) / name
        if not p.exists():
            raise AuditMismatch('pinned audit missing: %s' % p)
        out[key] = json.loads(p.read_text())
    return out


def check_inputs(audits, root=ROOT):
    binding = {}
    for rel, (akey, path) in PINNED_INPUTS.items():
        pinned, actual = dig(audits[akey], path), sha(Path(root) / rel)
        if pinned != actual:
            raise AuditMismatch('%s changed since %s pinned it: %s != %s' % (rel, AUDITS[akey], actual, pinned))
        binding[rel] = dict(sha256=actual, pinned_by=AUDITS[akey])
    return binding


class Matcher:
    """Collects (value, audit path) comparisons for a row; raises on the first disagreement."""

    def __init__(self, audits):
        self.audits = audits

    def __call__(self, row_id, value, akey, path):
        ref = dig(self.audits[akey], path)
        if isinstance(ref, dict) and isinstance(value, dict):
            if set(ref) != set(map(str, value)):
                raise AuditMismatch('%s: keys %s != %s at %s:%s' % (row_id, sorted(value), sorted(ref), AUDITS[akey], path))
            diff = max(abs(float(value[k]) - float(ref[str(k)])) for k in value) if value else 0.0
        else:
            diff = abs(float(value) - float(ref))
        if diff > TOL:
            raise AuditMismatch('%s: %r disagrees with %s:%s = %r' % (row_id, value, AUDITS[akey], '.'.join(map(str, path)), ref))
        return dict(audit=AUDITS[akey], path='.'.join(map(str, path)), abs_diff=diff)


# ----------------------------------------------------------------------------------------------- computations
def arm_contrast(eps, t):
    y = {a: [e['success'] for e in eps if e['decisions'][t]['a'] == a] for a in (0, 1)}
    var = {a: sum((x - mean(y[a])) ** 2 for x in y[a]) / (len(y[a]) - 1) for a in (0, 1)}
    return dict(effect=mean(y[1]) - mean(y[0]), episode_independent_se=math.sqrt(var[1] / len(y[1]) + var[0] / len(y[0])),
                n=len(eps), n_eligible_tasks=len({e['task_uid'] for e in eps}), n_large=len(y[1]), n_small=len(y[0]))


def task_paired(rows, key, arms, outcome, per_arm):
    z = collections.defaultdict(lambda: collections.defaultdict(list))
    for e in rows:
        z[e['task_uid']][key(e)].append(e[outcome])
    if not all(len(v[arms[0]]) == len(v[arms[1]]) == per_arm for v in z.values()):
        raise AuditMismatch('unbalanced task blocks for %s' % outcome)
    return summary([mean(v[arms[0]]) - mean(v[arms[1]]) for v in z.values()])


def branch_prefixes():
    """Per-prefix success lists by arm, grouped as in branch_linkage_linearized.gather()."""
    plan = {p['episode_id']: p for p in json.loads((RES / 'branch' / 'branch_plan.json').read_text())['episodes']}
    out = {}
    for e in jsonl(RES / 'branch' / 'episodes.jsonl'):
        pid = e.get('parent_episode_id') or plan[e['episode_id']]['parent_episode_id']
        arm = e.get('fork_arm') or ('large' if plan[e['episode_id']]['forced_arm'] else 'small')
        out.setdefault((e['task_uid'], pid), {}).setdefault(arm, []).append(e['success'])
    return out


def reproduce_branch_plan(log_raw):
    """Redraw the frozen prefix sample from design.json's seed and the complete log, exactly as run.py drew it."""
    design = json.loads((RES / 'design.json').read_text())['branch_audit']
    plan = json.loads((RES / 'branch' / 'branch_plan.json').read_text())
    last = {}
    for r in log_raw:
        if not r.get('error'):
            last[r['episode_id']] = r
    parents = sorted((r for r in last.values() if r['split'] == 'confirm' and r['n_decisions'] >= 2), key=lambda r: r['episode_id'])
    rng = np.random.default_rng(design['seed'])
    pick = sorted(rng.choice(len(parents), size=min(design['n_prefixes'], len(parents)), replace=False).tolist())
    redrawn = []
    for i in pick:
        for arm in (0, 1):
            for c in range(design['continuations_per_arm']):
                redrawn.append((parents[i]['episode_id'], arm, c, int(rng.integers(1, 2 ** 31 - 1))))
    frozen = [(p['parent_episode_id'], p['forced_arm'], p['run'], p['seed']) for p in plan['episodes']]
    starts = sorted(e['start_utc'] for e in jsonl(RES / 'branch' / 'episodes.jsonl'))
    return dict(
        numpy_version=np.__version__, design_seed=design['seed'], n_eligible_parents=len(parents),
        plan_n_eligible_prefixes=plan['n_eligible_prefixes'],
        plan_log_sha256_matches_current_log=plan['log_sha256'] == sha(RES / 'log' / 'episodes.jsonl'),
        redrawn_equals_frozen_plan=redrawn == frozen, n_plan_rows=len(frozen),
        plan_created_utc=plan['created_utc'], earliest_branch_start_utc=starts[0],
        plan_created_not_after_first_start=plan['created_utc'] <= starts[0],
        git_order_note='branch_plan.json and branch/episodes.jsonl were first committed together (ac3ca83), and the '
                       'plan time equals the first continuation start at one-second resolution, so neither commit order '
                       'nor timestamps strictly order the draw before execution.',
        design_freeze_commit='cb9481d77567b7b14e3ceb6c1f0a6b534c67edcb',
        reading='The design seed and sampling code occur in the earlier design-freeze commit cb9481d; its design.json '
                'is byte-identical to the current pinned design. The exact redraw supports compliance with the '
                'documented SRSWOR mechanism (numpy Generator.choice without replacement). It does not alone prove '
                'execution independence, absence of unrecorded selection, or selection-invariant continuation laws. '
                'Uniformity is a property of the specified randomization mechanism, not an empirical test from one draw.')


def build(audits=None, root=ROOT):
    audits = audits if audits is not None else load_audits()
    binding = check_inputs(audits, root)
    M = Matcher(audits)
    log_raw = jsonl(RES / 'log' / 'episodes.jsonl')
    L = [e for e in log_raw if e['split'] == 'confirm']
    V = jsonl(RES / 'live' / 'episodes.jsonl')
    old = json.loads((RES / 'analysis' / 'why_null.json').read_text())
    cor = json.loads((RES / 'analysis' / 'why_null_corrected.json').read_text())
    if len(L) != 2640 or len({e['task_uid'] for e in L}) != 330:
        raise AuditMismatch('confirm log is not 2640 episodes over 330 tasks')
    rows = []

    def row(**kw):
        for k in ('id', 'cls', 'endpoint', 'target', 'comparator', 'denominator', 'estimate', 'status', 'audit'):
            if kw.get(k) in (None, '', []) and k != 'estimate':
                raise AuditMismatch('row %s lacks %s' % (kw.get('id'), k))
        kw['class'] = kw.pop('cls')
        rows.append(kw)

    # ---- whole-policy (live CONFIRM) -------------------------------------------------------------------------
    live_den = '330 CONFIRM tasks x 2 live runs per policy = 660 episodes each; task-paired; equal task weight'
    pol_key = lambda e: e['policy']
    for comp in ('always_large', 'always_small'):
        for out in ('success', 'utility'):
            rs = [e for e in V if e['policy'] in ('learned', comp)]
            s = task_paired(rs, pol_key, ('learned', comp), out, 2)
            name = 'learned_minus_%s_%s' % (comp, out)
            aud = [M(name, s['mean'], 'WNA', ['paired_se_provenance', 'reconstructed_candidates', name, 'mean']),
                   M(name, s['se'], 'WNA', ['paired_se_provenance', 'reconstructed_candidates', name, 'se'])]
            if comp == 'always_large':
                aud.append(M(name, s['mean'], 'WN4', ['live_metric', 'thresholds',
                             'success_difference' if out == 'success' else 'utility_difference_frozen']))
            status = 'ARCHIVED live contrast; lead-audited'
            if comp == 'always_small' and out == 'success':
                saved = next(r for r in csv.DictReader((RES / 'analysis' / 'live_contrasts_vs_baseline.csv').open())
                             if r['outcome'] == 'success' and r['contrast'] == 'learned - always_small')
                if abs(float(saved['live_se']) - s['se']) > TOL or round(s['se'], 4) != cor['paired_contrast_se']:
                    raise AuditMismatch('.0199 provenance no longer reproduces')
                status = ('ARCHIVED live contrast. This SE (%.6f) is the .0199 in why_null_corrected.json, which that file '
                          'mislabelled as the learned-minus-large paired SE' % s['se'])
            row(id='W-%s-%s' % (comp, out), cls='whole_policy', endpoint='final hidden success' if out == 'success' else
                'frozen utility (success - 0.03 x large calls - 0.01 x small calls)',
                target='E_task[Y(learned) - Y(%s)] over the fixed 330-task CONFIRM benchmark' % comp,
                comparator='%s, live' % comp, denominator=live_den, estimate=s['mean'],
                uncertainty=dict(value=s['se'], label='task-paired SD/sqrt(330) arithmetic; fixed-benchmark interval '
                                 'validity unresolved; no branch theorem applies'),
                status=status, audit=aud)
    met = {}
    for pol in ('learned', 'always_large'):
        es = [e for e in V if e['policy'] == pol]
        large = sum(d['a'] == 1 for e in es for d in e['decisions']); small = sum(d['a'] == 0 for e in es for d in e['decisions'])
        seqs = dict(collections.Counter(''.join('L' if d['a'] else 'S' for d in e['decisions']) for e in es))
        met[pol] = dict(n=len(es), successes=sum(e['success'] for e in es), large=large, small=small, seqs=seqs,
                        mean_success=mean([e['success'] for e in es]), mean_utility=mean([e['utility'] for e in es]))
        base = ['live_metric', pol]
        row(id='W-value-%s' % pol, cls='whole_policy', endpoint='final hidden success; frozen utility',
            target='policy value on the fixed 330-task CONFIRM benchmark', comparator='none (single policy value)',
            denominator='660 live episodes = 330 tasks x 2 runs', estimate=dict(success=met[pol]['mean_success'],
            utility=met[pol]['mean_utility']), uncertainty=None, status='ARCHIVED; lead-audited',
            audit=[M(pol, met[pol]['mean_success'], 'WN4', base + ['mean_success']),
                   M(pol, met[pol]['mean_utility'], 'WN4', base + ['mean_utility']),
                   M(pol, met[pol]['successes'], 'WN4', base + ['successes'])])
        row(id='W-calls-%s' % pol, cls='whole_policy', endpoint='model calls and realized action sequences',
            target='resource use of the policy on its own live histories', comparator='none (tally)',
            denominator='660 live episodes', estimate=dict(large_calls=large, small_calls=small,
            all_calls=large + small, sequences=seqs), uncertainty=None, status='ARCHIVED tally; lead-audited',
            audit=[M(pol, large, 'WN4', base + ['large_calls']), M(pol, small, 'WN4', base + ['small_calls']),
                   M(pol, seqs, 'WN4', base + ['reachable_sequences'])])
    a, b = met['learned'], met['always_large']
    dS, dL, dM = a['successes'] - b['successes'], a['large'] - b['large'], a['small'] - b['small']
    fixed = (dS - .01 * dM) / dL; k = dS / (.03 * dL + .01 * dM)
    if abs(.03 * k - old['B_metric']['flip_point_large_call_penalty']) > TOL:
        raise AuditMismatch('why_null.json flip point no longer reproduces')
    for cid, est, aud, cmp in [
            ('W-cost-small-fixed', dict(large_penalty=fixed),
             [M('fixed', fixed, 'WN4', ['live_metric', 'thresholds', 'fixed_small_penalty_0p01_large_threshold']),
              M('fixed', fixed, 'WNA', ['cost_crossings', 'fixed_small_0p01_large'])],
             round(fixed, 6) == cor['cost_crossing']['small_fixed_0p01']['large']),
            ('W-cost-both-scaled', dict(factor=k, large_penalty=.03 * k, small_penalty=.01 * k),
             [M('both', k, 'WNA', ['cost_crossings', 'both_scale_factor']),
              M('both', .03 * k, 'WN4', ['live_metric', 'thresholds', 'both_scaled_large_threshold']),
              M('both', .01 * k, 'WN4', ['live_metric', 'thresholds', 'both_scaled_small_threshold'])],
             round(.03 * k, 6) == cor['cost_crossing']['both_scale_1to3']['large'] and
             round(.01 * k, 6) == cor['cost_crossing']['both_scale_1to3']['small'])]:
        if not cmp:
            raise AuditMismatch('%s no longer reproduces why_null_corrected.json' % cid)
        row(id=cid, cls='whole_policy', endpoint='frozen-form utility with varied call penalties',
            target='penalty at which the learned-minus-always_large live utility difference, %d/660 successes, %d large '
                   'and %+d small calls, crosses zero' % (dS, dL, dM),
            comparator='always_large, live', denominator='660 live episodes per policy', estimate=est, uncertainty=None,
            status='ARCHIVED post-hoc arithmetic on noisy live means for the TRAIN-learned policy (not class_tailored); '
                   'not a validated break-even point; no cost sensitivity was pre-registered', audit=aud)

    # ---- initial action, logger continuation (log CONFIRM) ------------------------------------------------------
    t0 = {}
    for out in ('success', 'utility', 'success_first_candidate'):
        for bench in ('humaneval', 'mbpp', 'pooled'):
            rs = [e for e in L if bench == 'pooled' or e['benchmark'] == bench]
            s = task_paired(rs, lambda e: e['decisions'][0]['a'], (1, 0), out, 4)
            t0[out, bench] = s
            p = ['t0', 'reconstructed', out, bench]
            aud = [M(bench, s['mean'], 'WNA', p + ['mean']), M(bench, s['se'], 'WNA', p + ['se']),
                   M(bench, s['n'], 'WNA', p + ['n'])]
            src = 'lead audit endpoint control (not previously reported by the worker)'
            if out == 'success':
                r = cor['t0_effect_by_benchmark'][bench]
                if (round(s['mean'], 4), round(s['se'], 4), s['n']) != (r['effect'], r['se'], r['n_tasks']):
                    raise AuditMismatch('t0 %s no longer reproduces why_null_corrected.json' % bench)
                src = 'CORRECTED (why_null_corrected.json t0_effect_by_benchmark, reproduced)'
            row(id='I-%s-%s' % (out, bench), cls='initial_action_logger_continued',
                endpoint={'success': 'final hidden success after all eligible decisions',
                          'utility': 'frozen utility', 'success_first_candidate': 'hidden success of the first candidate'}[out],
                target=(('E_task[Y_first(A0=large) - Y_first(A0=small)], ' if out == 'success_first_candidate' else
                         'E_task[Y(A0=large, logger later) - Y(A0=small, logger later)], ') +
                        ('all 330 tasks' if bench == 'pooled' else 'within ' + bench)),
                comparator=('initial small arm, before any continuation' if out == 'success_first_candidate' else
                            'initial small arm, same logger continuation'),
                denominator='%d tasks x (4 initial-large + 4 initial-small logger episodes); task-paired; equal task weight' % s['n'],
                estimate=s['mean'], uncertainty=dict(value=s['se'], label='SD(task differences)/sqrt(tasks) arithmetic; '
                                                     'interval validity unresolved'),
                status=src, audit=aud)
    pos_pooled = max(0.0, -t0['success', 'pooled']['mean'])
    pos_bench = sum(t0['success', b_]['n'] / 330 * max(0.0, -t0['success', b_]['mean']) for b_ in ('humaneval', 'mbpp'))
    if (pos_pooled, pos_bench) != (cor['oracle_gain_vs_always_large']['partition_pooled_t0'],
                                   cor['oracle_gain_vs_always_large']['partition_benchmark_t0']):
        raise AuditMismatch('corrected oracle_gain fields no longer reproduce')
    row(id='I-positive-part-t0', cls='initial_action_logger_continued', endpoint='final hidden success',
        target='none valid: positive part of estimated small-favouring t0 strata (pooled; by benchmark)',
        comparator='always_large (as mislabelled in the corrected JSON)', denominator='330 tasks; 91 + 239 by benchmark',
        estimate=dict(pooled=pos_pooled, by_benchmark=pos_bench), uncertainty=None,
        status='WITHDRAWN as an "oracle gain" (corrected JSON oracle_gain_vs_always_large). Values reproduced only so '
               'original numbers stay traceable; see withdrawn_interpretations',
        audit=[dict(audit='why_null_corrected.json (archived file; no lead audit pins these two zeros)',
                    path='oracle_gain_vs_always_large', abs_diff=0.0)])

    # ---- pooled repair (log CONFIRM, logger-reached histories) --------------------------------------------------
    st = {}
    for t in (1, 2):
        es = [e for e in L if len(e['decisions']) > t]
        c = st[t] = arm_contrast(es, t)
        if abs(c['effect'] - old['C_theory']['effect_at_t%d' % t]['effect']) > TOL:
            raise AuditMismatch('why_null.json stage %d no longer reproduces' % t)
        p = ['stage_contrasts', str(t)]
        row(id='P-stage%d' % t, cls='pooled_repair', endpoint='final hidden success',
            target='current-action effect at repair decision %d on terminal hidden success, later actions by the '
                   'randomized logger, among logger-reached histories' % t,
            comparator='small arm at decision %d' % t,
            denominator='%d eligible log episodes (%d large, %d small) in %d tasks; pooled episode-arm means' %
                        (c['n'], c['n_large'], c['n_small'], c['n_eligible_tasks']),
            estimate=c['effect'], uncertainty=dict(value=c['episode_independent_se'], label='episode-independent '
                     'arithmetic; ignores repeated task records; not a valid SE'),
            status='ARCHIVED (why_null.json C_theory.effect_at_t%d)' % t,
            audit=[M('st', c['effect'], 'WN4', p + ['effect']), M('st', c['episode_independent_se'], 'WN4', p + ['episode_independent_se']),
                   M('st', c['n'], 'WN4', p + ['n']), M('st', c['n_large'], 'WN4', p + ['n_large'])])
    diff = st[2]['effect'] - st[1]['effect']
    row(id='P-stage-difference', cls='pooled_repair', endpoint='final hidden success',
        target='none common: stage-2 minus stage-1 contrasts on different, selected risk sets', comparator='stage-1 contrast',
        denominator='458 vs 564 overlapping eligible episodes', estimate=diff,
        uncertainty=dict(value=old['C_theory']['stage_gradient']['se'], label='ARCHIVED; adds variances as if '
                         'independent despite shared episodes/tasks; invalid, no replacement derived'),
        status='ARCHIVED descriptive difference; isolates no stage interaction',
        audit=[M('sd', diff, 'WN4', ['stage_difference', 'estimate']),
               M('sd', old['C_theory']['stage_gradient']['se'], 'WN4', ['stage_difference', 'saved_episode_independent_se'])])
    neg = {}
    for t in (1, 2):
        es = [e for e in L if len(e['decisions']) > t]
        groups = collections.defaultdict(list)
        for e in es:
            groups['%s|prev=%s' % (e['decisions'][t]['state']['fail_class'], 'L' if e['decisions'][t - 1]['a'] else 'S')].append(e)
        cells = {kk: arm_contrast(g, t) for kk, g in groups.items()}
        if min(min(c['n_large'], c['n_small']) for c in cells.values()) < 10:
            raise AuditMismatch('a stage-%d cell fell below why_null.py min_arm' % t)
        for kk, c in sorted(cells.items()):
            if abs(c['effect'] - old['C_theory']['cells_t%d' % t][kk]['effect']) > TOL:
                raise AuditMismatch('why_null.json cell %s no longer reproduces' % kk)
            p = ['cell_contrasts', str(t), kk]
            row(id='P-cell%d-%s' % (t, kk), cls='pooled_repair', endpoint='final hidden success',
                target='as P-stage%d, within failure class and previous action %s' % (t, kk),
                comparator='small arm at decision %d, same cell' % t,
                denominator='%d eligible episodes (%d large, %d small) in %d tasks' % (c['n'], c['n_large'], c['n_small'], c['n_eligible_tasks']),
                estimate=c['effect'], uncertainty=dict(value=c['episode_independent_se'], label='episode-independent arithmetic; not a valid SE'),
                status='ARCHIVED (why_null.json C_theory.cells_t%d)' % t + ('; favours small by point estimate' if c['effect'] < 0 else ''),
                audit=[M('cell', c['effect'], 'WN4', p + ['effect']), M('cell', c['episode_independent_se'], 'WN4', p + ['episode_independent_se'])])
        neg[t] = sum(c['n'] * max(0.0, -c['effect']) for c in cells.values()) / len(L)
        if abs(neg[t] - old['A_design']['oracle_tailoring_ceiling_over_always_large_t%d' % t]) > TOL:
            raise AuditMismatch('why_null.json ceiling t%d no longer reproduces' % t)
    row(id='P-negative-cell-statistic', cls='pooled_repair', endpoint='final hidden success',
        target='none valid: in-sample negative-cell terminal-success statistic (estimated signs, logger occupancy and '
               'continuation)', comparator='always_large (as mislabelled in why_null.json)',
        denominator='cell episode counts / 2640 confirm episodes', estimate={'1': neg[1], '2': neg[2]}, uncertainty=None,
        status='WITHDRAWN as an "oracle tailoring ceiling" (why_null.json A_design); neither an upper bound nor a '
               'confidence bound on dynamic-policy gain',
        audit=[M('neg', {'1': neg[1], '2': neg[2]}, 'WN4', ['posthoc_negative_success_cell_statistic'])])
    es = [e for e in L if len(e['decisions']) > 1 and e['decisions'][0]['a'] == 1]
    c = arm_contrast(es, 1)
    row(id='P-stage1-after-large', cls='pooled_repair', endpoint='final hidden success',
        target='as P-stage1, restricted to histories whose initial action was large', comparator='small arm at decision 1',
        denominator='%d eligible episodes (%d large, %d small) in %d tasks' % (c['n'], c['n_large'], c['n_small'], c['n_eligible_tasks']),
        estimate=c['effect'], uncertainty=dict(value=c['episode_independent_se'], label='episode-independent arithmetic; not a valid SE'),
        status='ARCHIVED (cited in README; not in why_null.json)',
        audit=[M('al', c['effect'], 'WN4', ['stage1_after_large', 'effect']),
               M('al', c['episode_independent_se'], 'WN4', ['stage1_after_large', 'episode_independent_se'])])

    sys.path.insert(0, str(ROOT / 'experiments' / 'tools'))
    import branch_linkage_linearized as BL  # noqa: E402  (already lead-audited at 29ee443)
    tasks, Ag, mg, N, D = BL.gather()
    d0, Bh, v = BL.delta(Ag, mg, N, D)
    U = (Ag - Bh * mg) / mg.sum() - (N[1] - v[1] * D[1]) / D[1].sum() + (N[0] - v[0] * D[0]) / D[0].sum()
    scale = float(np.sqrt((U ** 2).sum()))
    row(id='P-B2-branch-minus-log', cls='pooled_repair', endpoint='final hidden success after first failure',
        target='archived point for the primary branch/log comparison: branch prefix mean minus pooled Hajek log '
               'contrast over all 330 source task blocks', comparator='pooled Hajek log contrast v1 - v0',
        denominator='branch: 200 sampled prefixes (prefix mean) in 103 tasks; log: arm weight totals D1=%g, D0=%g over '
                    '564 eligible prefixes in 152 tasks' % (D[1].sum(), D[0].sum()),
        estimate=dict(branch=Bh, log=v[1] - v[0], log_large=v[1], log_small=v[0], difference=d0),
        uncertainty=dict(value=scale, label='exploratory algebraic scale sqrt(sum U_g^2); not a consistent SE; no '
                         'calibrated coverage'),
        status='ARCHIVED point; the primary target theta has no estimate or interval here (OPEN)',
        audit=[M('b2', Bh, 'LN', ['branch_estimate']), M('b2', v[1] - v[0], 'LN', ['log_estimate']),
               M('b2', d0, 'LN', ['difference']), M('b2', {0: N[0].sum(), 1: N[1].sum()}, 'LN', ['log_arm_numerators']),
               M('b2', {0: D[0].sum(), 1: D[1].sum()}, 'LN', ['log_arm_denominators']),
               M('b2', scale, 'LN', ['reported_scale'])])

    # ---- realized frame (SECONDARY) --------------------------------------------------------------------------
    pref = branch_prefixes()
    d = [mean(x['large']) - mean(x['small']) for x in pref.values()]
    vi = [np.var(x['large'], ddof=1) / len(x['large']) + np.var(x['small'], ddof=1) / len(x['small']) for x in pref.values()]
    Nf, m = 564, len(d); f = m / Nf
    s2 = float(np.var(d, ddof=1)); first = (1 - f) / m * s2; second = f / m * float(np.mean(vi))
    se_f = math.sqrt(first + second); nr = ['numeric_reconstruction']
    row(id='R-conditional-frame', cls='realized_frame', endpoint='final hidden success after first failure',
        target='Delta_F = mu_F - L(F): branch mean over the realized 564-prefix frame minus the realized log contrast',
        comparator='realized log contrast L(F), held fixed', denominator='200 of 564 frame prefixes, SRSWOR, 2 replicates per arm',
        estimate=float(mean(d)) - float(v[1] - v[0]),
        uncertainty=dict(value=se_f, label='conditional-frame SE from theory_branch_sampling.md section 1 under its '
                         'independence assumptions; archived normal interval [%.6f, %.6f] is NOT validated' %
                         tuple(dig(audits['CF'], ['archived_normal_interval_not_validated']))),
        status='SECONDARY; covers no source-frame randomness',
        audit=[M('rf', float(mean(d)), 'CF', nr + ['B_hat']), M('rf', float(mean(d)) - float(v[1] - v[0]), 'CF', nr + ['delta_hat']),
               M('rf', s2, 'CF', nr + ['sample_variance_of_contrasts']), M('rf', float(np.mean(vi)), 'CF', nr + ['mean_within_prefix_variance']),
               M('rf', first, 'CF', nr + ['between_prefix_component']), M('rf', second, 'CF', nr + ['execution_component']),
               M('rf', se_f, 'CF', nr + ['se_frame'])])

    # ---- selected cohorts (exploratory) ------------------------------------------------------------------------
    delta, reached = {}, {}
    for t in (1, 2):
        z = collections.defaultdict(lambda: collections.defaultdict(list))
        for e in L:
            if len(e['decisions']) > t:
                z[e['task_uid']][e['decisions'][t]['a']].append(e['success'])
        reached[t] = set(z); delta[t] = {g: mean(x[1]) - mean(x[0]) for g, x in z.items() if x[0] and x[1]}
    ids = sorted(set(delta[1]) & set(delta[2]))
    sg = {kk: summary([fn(g) for g in ids]) for kk, fn in
          [('t1', lambda g: delta[1][g]), ('t2', lambda g: delta[2][g]), ('difference', lambda g: delta[2][g] - delta[1][g])]}
    digest = hashlib.sha256('\n'.join(ids).encode()).hexdigest()
    sgc = cor['stage_gradient_paired']
    if (round(sg['t1']['mean'], 4), round(sg['t2']['mean'], 4), round(sg['difference']['mean'], 4),
            round(sg['difference']['se'], 4), len(ids)) != (sgc['t1'], sgc['t2'], sgc['difference'], sgc['se'], sgc['tasks']):
        raise AuditMismatch('stage_gradient_paired no longer reproduces why_null_corrected.json')
    if digest != audits['WNA']['stage_gradient']['selected_id_digest']:
        raise AuditMismatch('61-task id digest differs from %s' % AUDITS['WNA'])
    p = ['stage_gradient', 'reproduced']
    row(id='S-61-task-stage-gradient', cls='selected_cohort', endpoint='final hidden success',
        target='unweighted mean over selected tasks of per-task observed-arm differences at decisions 1 and 2',
        comparator='per-task small-arm mean at the same decision',
        denominator='61 tasks with both actions observed at BOTH decisions (of 134 reaching both; 87 and 71 with both '
                    'actions at decision 1 and 2 respectively); equal task weight',
        estimate=dict(t1=sg['t1']['mean'], t2=sg['t2']['mean'], difference=sg['difference']['mean']),
        uncertainty=dict(value=sg['difference']['se'], label='SD/sqrt(61) arithmetic on a support-selected cohort; the '
                         'corrected JSON "1.6 sigmas" reading is withdrawn'),
        status='CORRECTED file reproduced; EXPLORATORY selected cohort; not a covariance repair of P-stage-difference',
        audit=[M('sg', sg[kk][q], 'WNA', p + [kk, q]) for kk in ('t1', 't2', 'difference') for q in ('mean', 'se')] +
              [M('sg', len(ids), 'WNA', p + ['tasks']),
               M('sg', len(reached[1] & reached[2]), 'WNA', ['stage_gradient', 'tasks_reaching_both']),
               dict(audit=AUDITS['WNA'], path='stage_gradient.selected_id_digest', abs_diff=0.0)])
    linked = [i for i in range(len(tasks)) if mg[i] > 0 and D[1][i] > 0 and D[0][i] > 0]
    eq_b = mean([Ag[i] / mg[i] for i in linked]); eq_l = mean([N[1][i] / D[1][i] - N[0][i] / D[0][i] for i in linked])
    pw_b = sum(Ag[i] for i in linked) / sum(mg[i] for i in linked)
    pw_l = sum(N[1][i] for i in linked) / sum(D[1][i] for i in linked) - sum(N[0][i] for i in linked) / sum(D[0][i] for i in linked)
    n_log = sum(1 for e in L if len(e['decisions']) > 1 and tasks.index(e['task_uid']) in set(linked))
    row(id='S-42-task-linked', cls='selected_cohort', endpoint='final hidden success after first failure',
        target='branch-minus-log on tasks with sampled prefixes AND positive log weight in both arms',
        comparator='log contrast on the same 42 tasks',
        denominator='42 of 330 tasks; %d of 200 sampled prefixes; %d of 564 eligible log prefixes' % (int(sum(mg[i] for i in linked)), n_log),
        estimate=dict(equal_task_branch=eq_b, equal_task_log=eq_l, equal_task_difference=eq_b - eq_l,
                      prefix_weighted_branch=pw_b, pooled_log=pw_l, prefix_weighted_difference=pw_b - pw_l),
        uncertainty=None, status='ARCHIVED EXPLORATORY; changes target; not a substitute for P-B2-branch-minus-log',
        audit=[M('lk', len(linked), 'LK', ['n_linked_selected_tasks']), M('lk', n_log, 'LK', ['n_log_eligible_prefixes_in_linked_tasks']),
               M('lk', sum(mg[i] for i in linked), 'LK', ['n_selected_prefixes_in_linked_tasks']),
               M('lk', eq_b, 'LK', ['linked_equal_task_branch_mean']), M('lk', eq_l, 'LK', ['linked_equal_task_log_mean']),
               M('lk', eq_b - eq_l, 'LK', ['linked_equal_task_difference']),
               M('lk', pw_b, 'LK', ['linked_task_subset_prefix_weighted_branch_mean']),
               M('lk', pw_l, 'LK', ['linked_task_subset_pooled_log_mean']),
               M('lk', pw_b - pw_l, 'LK', ['linked_task_subset_prefix_weighted_difference'])])

    # ---- descriptive ----------------------------------------------------------------------------------------------
    r1 = sum(len(e['decisions']) > 1 for e in L); r2 = sum(len(e['decisions']) > 2 for e in L)
    share = 1 - r1 / len(L)
    if abs(share - old['A_design']['share_decided_by_first_action_alone']) > TOL:
        raise AuditMismatch('why_null.json absorption share no longer reproduces')
    row(id='D-logger-occupancy', cls='descriptive', endpoint='number of eligible decisions reached',
        target='realized stopping fraction of THIS logger after one decision', comparator='none',
        denominator='2640 confirm log episodes', estimate=dict(reach_second=r1, reach_third=r2, stopped_after_first=share),
        uncertainty=None, status='ARCHIVED; a law-dependent realized occupancy, not a policy-invariant design constant',
        audit=[M('occ', r1, 'WNA', ['stage_gradient', 'original_eligible_episodes', '1']),
               M('occ', r2, 'WNA', ['stage_gradient', 'original_eligible_episodes', '2'])])
    vt = json.loads((RES / 'visible_tests.json').read_text())['tests']
    zero = sum(vt[u]['certified']['n_checks'] == 0 for u in {e['task_uid'] for e in L})
    learned = [e for e in V if e['policy'] == 'learned']
    vphf = sum(e['decisions'][0]['validation']['passed'] and e['success_first_candidate'] == 0 for e in learned)
    row(id='D-feedback', cls='descriptive', endpoint='visible-check coverage; first-candidate visible vs hidden outcome',
        target='deployable-feedback limits cited in README A6', comparator='none',
        denominator='330 CONFIRM tasks; 660 learned live episodes',
        estimate=dict(tasks_without_surviving_visible_checks=zero, learned_first_candidate_visible_pass_hidden_fail=vphf),
        uncertainty=None, status='ARCHIVED counts; they do not show further calls would repair these failures',
        audit=[M('fb', zero, 'RD', ['visible_check_distribution', 'confirm', 'zero_check_tasks']),
               M('fb', vphf, 'RD', ['live', 'learned', 'all_first_candidate', 'visible_pass_hidden_fail'])])

    evidence = {r['assumption']: r['status'] for r in
                json.loads((RES / 'analysis' / 'branch_evidence_table.json').read_text())['assumptions']}

    def ev(text):
        if text not in evidence:
            raise AuditMismatch('evidence-table assumption row missing: %s' % text)
        return dict(evidence_row=text, status=evidence[text])

    plan_check = reproduce_branch_plan(log_raw)
    selection_status = ('REPRODUCED: documented SRSWOR draw; fresh-noise independence and selection-invariant laws remain assumptions'
                        if plan_check['redrawn_equals_frozen_plan'] and plan_check['plan_log_sha256_matches_current_log']
                        else 'NOT REPRODUCED; see branch_plan_reproduction')
    theorem_map = [
        dict(result='Primary fixed-benchmark bound, sections 2-5', doc='docs/theory_branch_fixed_benchmark_bound.md',
             applies_to=['P-B2-branch-minus-log (as the target\'s archived point only)'],
             conditions=[
                 dict(condition='independent complete source-task blocks', **ev('complete source-task blocks are independent across all 330 tasks')),
                 dict(condition='conditional uniform prefix selection independent of fresh noise',
                      evidence_row='prefix sample is SRSWOR of fixed size m from the frame', status=selection_status),
                 dict(condition='selection-invariant fresh replicate pairs independent across prefix/replicate indices',
                      **ev('continuations iid within arm given the prefix')),
                 dict(condition='(same) no execution shocks shared across prefixes', **ev('no execution shocks shared across prefixes')),
                 dict(condition='(same) lost and recovered executions follow one law', **ev('lost and recovered executions follow the same law')),
                 dict(condition='dependence between the two arms within a pair', evidence_row='arms conditionally independent given the prefix',
                      status='PERMITTED by the pair version; not required'),
                 dict(condition='source/log covariance retained', evidence_row='(estimator requirement)',
                      status='structural requirement of the bound, not an execution assumption')],
             boundary='No fixed-benchmark interval for theta is computed here; primary B2 coverage remains OPEN.'),
        dict(result='Secondary conditional-frame variance, section 1', doc='docs/theory_branch_sampling.md',
             applies_to=['R-conditional-frame'],
             conditions=[
                 dict(condition='unbiased prefix contrasts',
                      evidence_row='restored prefix equals the logged pre-call state',
                      status='UNKNOWN for unbiasedness: recorded-field restoration is observed, but alone does not establish '
                             'the intended continuation law or outcome-independent retention/recovery'),
                 dict(condition='independent prefix noise with selection-invariant laws', **ev('continuations iid within arm given the prefix')),
                 dict(condition='(same) no shared prefix shocks; otherwise extra covariance terms', **ev('no execution shocks shared across prefixes')),
                 dict(condition='archived variance estimate: independent within-arm replicates and independent arms',
                      **ev('arms conditionally independent given the prefix')),
                 dict(condition='fixed-size SRSWOR from the frame', evidence_row='prefix sample is SRSWOR of fixed size m from the frame',
                      status=selection_status)],
             boundary='Covers no source-frame randomness and establishes no Wald coverage.'),
        dict(result='Whole-policy A6 contrasts', doc='(none)',
             applies_to=[r['id'] for r in rows if r['class'] == 'whole_policy'],
             conditions=[dict(condition='separate root-to-terminal fixed-task estimands with their own inference requirements',
                              evidence_row='(none)', status='UNRESOLVED: neither branch result supplies their interval justification')],
             boundary='Task-paired SEs are reproduced arithmetic only.'),
        dict(result='Initial-action rows (lead-accepted reporting class)', doc='(none)',
             applies_to=[r['id'] for r in rows if r['class'] == 'initial_action_logger_continued'],
             conditions=[dict(condition='fixed-task endpoint-specific contrasts; final outcomes under logger continuation, first-candidate outcomes before continuation',
                              evidence_row='(none)', status='UNRESOLVED: no branch result supplies interval justification')],
             boundary='Arithmetic only.'),
    ]

    withdrawn = [
        dict(claim='oracle tailoring ceiling over always_large (why_null.json A_design; corrected JSON oracle_gain_vs_always_large)',
             rows=['P-negative-cell-statistic', 'I-positive-part-t0'],
             replacement='in-sample negative-cell terminal-success statistic; neither an upper bound nor a confidence bound '
                         'on dynamic-policy gain, even when scoped to a partition', source=AUDITS['WN4'] + '; ' + AUDITS['WNA']),
        dict(claim='upward bias of the positive part implies the true partition value is no larger than observed',
             rows=[], replacement='false: an upward-biased estimator can realize below the true gain (lead counterexample: '
                                  'expectation 0.15 > truth 0.1, realized 0 on one outcome)', source=AUDITS['WNA']),
        dict(claim='no examined stratum at any stage favours the small model',
             rows=['P-cell1-assertion|prev=L'], replacement='the original stage-1 assertion|prev=L cell favours small by '
                                                            'point estimate; non-significance is not absence', source=AUDITS['WNA']),
        dict(claim='.0199 is the paired learned-minus-always_large SE', rows=['W-always_small-success', 'W-always_large-success'],
             replacement='.0199 is the learned-minus-ALWAYS_SMALL success SE; learned-minus-large is .011039 (success) '
                         'and .011278 (utility)', source=AUDITS['WNA']),
        dict(claim='0.024 policy-value SE as the yardstick for a paired gain', rows=[],
             replacement='a literal in why_null.py, not computed there; a single-policy SE is not a paired-gain SE and '
                         'shows no power deficit', source=AUDITS['WN4']),
        dict(claim='61-task stage gradient at 1.6 sigmas', rows=['S-61-task-stage-gradient'],
             replacement='support-selected cohort with changed weights; exploratory; no validated stage interaction', source=AUDITS['WNA']),
        dict(claim='78.6% of episodes are decided by the first action (as a design property)', rows=['D-logger-occupancy'],
             replacement='realized stopping fraction under this logger; policies can change occupancy', source=AUDITS['WNA']),
        dict(claim='analysis uses the frozen log only', rows=['W-cost-small-fixed', 'W-cost-both-scaled'],
             replacement='the metric section reads frontier_live.csv (live learned and always_large)', source=AUDITS['WN4']),
        dict(claim='framework vindicated / not implicated; hidden-test absorption as a remedy', rows=[],
             replacement='withdrawn in why_null_corrected.json retractions; hidden outcomes must not drive stopping', source='why_null_corrected.json'),
    ]
    row_ids = {r['id'] for r in rows}
    for w in withdrawn:
        if not set(w['rows']) <= row_ids:
            raise AuditMismatch('withdrawn claim cites unknown rows: %s' % (set(w['rows']) - row_ids))

    return dict(
        request='DTR-REQ-001 item 1: source-bound corrected A6 report with target/comparator/denominator columns',
        status='POST-HOC reporting; every numeric row re-derived from raw records and matched to a pinned lead audit '
               '(tolerance %g) or, where no audit pins it, to the archived file it reproduces' % TOL,
        classes=CLASSES,
        primary_target=dict(name='theta = sum_g E(T_g) / sum_g E(M_g) over all 330 source task blocks (expected-prefix task weights)',
                            estimate=None, interval=None, status='OPEN: not estimated in this report; no row substitutes for it',
                            decision='docs/theory_feedback_20260921_weighting.md'),
        weighting_note='Whole-policy rows keep their equal-task, planned-repeat target; the branch expected-prefix '
                       'weighting does not transfer to them (lead decision, theory_feedback_20260921_weighting.md).',
        rows=rows, withdrawn_interpretations=withdrawn, theorem_assumption_map=theorem_map,
        branch_plan_reproduction=plan_check, source_binding=binding,
        archived_files_unchanged=['results/code_routing/analysis/why_null.json', 'results/code_routing/analysis/why_null_corrected.json',
                                  'experiments/tools/why_null.py'],
        not_claimed=['no interval coverage, power or equivalence for any row', 'no oracle ceiling or upper bound',
                     'no estimate of the primary target theta', 'no validated stage interaction',
                     'no new observations, cohorts, endpoints or metrics'])


def fmt(x):
    if x is None:
        return '-'
    if isinstance(x, dict):
        return '; '.join('%s %s' % (k, fmt(v)) for k, v in x.items())
    if isinstance(x, float):
        return '%.6f' % x
    return str(x)


def render_md(rep):
    esc = lambda s: str(s).replace('|', '\\|')
    out = ['# A6 corrected report (source-bound)', '',
           'Generated by `experiments/tools/a6_report.py` from the committed raw records; do not edit by hand. ' + rep['status'] + '.', '',
           '**Primary target:** ' + rep['primary_target']['name'] + ' - ' + rep['primary_target']['status'] + '.', '',
           rep['weighting_note'], '', '## Analysis classes', '']
    out += ['- `%s`: %s' % (k, v) for k, v in rep['classes'].items()]
    for cls in rep['classes']:
        rs = [r for r in rep['rows'] if r['class'] == cls]
        out += ['', '## %s' % cls, '', '| ID | Endpoint | Target | Comparator | Denominator | Estimate | Arithmetic SE/scale | Status | Audits |',
                '|---|---|---|---|---|---|---|---|---|']
        for r in rs:
            u = r['uncertainty']
            out.append('| %s |' % ' | '.join(esc(x) for x in [
                r['id'], r['endpoint'], r['target'], r['comparator'], r['denominator'], fmt(r['estimate']),
                '-' if u is None else '%.6f (%s)' % (u['value'], u['label']), r['status'],
                '%d match; max diff %.1e' % (len(r['audit']), max(a['abs_diff'] for a in r['audit']))]))
    out += ['', '## Withdrawn interpretations', '', '| Withdrawn reading | Rows | Replacement | Source |', '|---|---|---|---|']
    out += ['| %s | %s | %s | %s |' % (esc(w['claim']), esc(', '.join(w['rows']) or '-'), esc(w['replacement']), esc(w['source']))
            for w in rep['withdrawn_interpretations']]
    out += ['', '## Theorem-to-assumption map', '']
    for t in rep['theorem_assumption_map']:
        out += ['**%s** (`%s`); applies to: %s. %s' % (t['result'], t['doc'], ', '.join(t['applies_to']), t['boundary']), '',
                '| Condition | Evidence-table row | Status |', '|---|---|---|']
        out += ['| %s | %s | %s |' % (esc(c['condition']), esc(c['evidence_row']), esc(c['status'])) for c in t['conditions']]
        out.append('')
    p = rep['branch_plan_reproduction']
    out += ['## Branch-plan reproduction', '',
            'Redrawn from design seed %d over %d eligible parents (numpy %s): equals frozen plan = %s; plan log hash matches '
            'current log = %s; plan created %s, first branch start %s.' % (
                p['design_seed'], p['n_eligible_parents'], p['numpy_version'], p['redrawn_equals_frozen_plan'],
                p['plan_log_sha256_matches_current_log'], p['plan_created_utc'], p['earliest_branch_start_utc']),
            p['git_order_note'] + ' ' + p['reading'], '', '## Not claimed', '']
    out += ['- ' + x for x in rep['not_claimed']]
    out += ['', '## Source binding', '', '| Input | SHA-256 | Pinned by |', '|---|---|---|']
    out += ['| `%s` | `%s` | %s |' % (k, v['sha256'][:16], v['pinned_by']) for k, v in rep['source_binding'].items()]
    return '\n'.join(out) + '\n'


def main():
    rep = build()
    OUT_JSON.write_text(json.dumps(rep, indent=1, default=float) + '\n')
    OUT_MD.write_text(render_md(rep))
    print('rows %d; classes %s; plan redraw equals frozen: %s' % (
        len(rep['rows']), dict(collections.Counter(r['class'] for r in rep['rows'])),
        rep['branch_plan_reproduction']['redrawn_equals_frozen_plan']))
    print('wrote', OUT_JSON.relative_to(ROOT), 'and', OUT_MD.relative_to(ROOT))


if __name__ == '__main__':
    main()
