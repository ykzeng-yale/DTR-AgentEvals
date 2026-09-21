"""DTR-REQ-001 slice: source-block / fresh-pair / recovery EVIDENCE table for the branch stage.

Descriptive only. The lead owns target, inference and interpretation decisions (docs/coordination_30min.md); this
tabulates what the archived records establish and labels what they do not, so each execution assumption used by any
branch variance calculation is visibly OBSERVED, CHECKABLE or UNKNOWN. It asserts no coverage or power and substitutes
no primary target. Output: results/code_routing/analysis/branch_evidence_table.json
"""
from __future__ import annotations
import collections, json, sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for sub in ('code_routing', 'common'):
    sys.path.insert(0, str(ROOT / 'experiments' / sub))
import common, analysis as A  # noqa: E402


def main():
    cfg = common.load_config()
    plan_doc = json.loads((common.RESULTS / 'branch' / 'branch_plan.json').read_text())
    plan = {p['episode_id']: p for p in plan_doc['episodes']}
    br, _ = A.read(common.RESULTS / 'branch' / 'episodes.jsonl', cfg)

    per = collections.defaultdict(lambda: collections.defaultdict(list))
    task_of = {}
    for e in br:
        pid = e.get('parent_episode_id') or plan[e['episode_id']]['parent_episode_id']
        arm = e.get('fork_arm') or ('large' if plan[e['episode_id']]['forced_arm'] else 'small')
        per[pid][arm].append(dict(inv=e.get('invocation'), y=int(e['success'])))
        task_of[pid] = e['task_uid']

    # source blocks: prefixes per source task
    blocks = collections.Counter(task_of.values())
    # fresh pairs: the two same-arm continuations of one prefix
    pairs = discord = 0
    disc_by_arm = collections.Counter(); pairs_by_arm = collections.Counter()
    for d in per.values():
        for arm, rows in d.items():
            if len(rows) == 2:
                pairs += 1; pairs_by_arm[arm] += 1
                if rows[0]['y'] != rows[1]['y']:
                    discord += 1; disc_by_arm[arm] += 1
    # recovery: invocation composition per prefix
    inv_sets = [frozenset(r['inv'] for rows in d.values() for r in rows) for d in per.values()]
    comp = collections.Counter(len(s) for s in inv_sets)
    only_lost = sum(1 for s in inv_sets if s == frozenset({'0445024c72d2'}))
    only_rec = sum(1 for s in inv_sets if s == frozenset({'8c343c83afdc'}))

    # full source frame: ALL 330 fixed CONFIRM task blocks, including those with no eligible or no sampled prefix
    log, _ = A.read(common.RESULTS / 'log' / 'episodes.jsonl', cfg)
    conf = [e for e in log if e['split'] == 'confirm']
    all_tasks = {e['task_uid'] for e in conf}
    elig = collections.Counter(e['task_uid'] for e in conf if e['n_decisions'] >= 2)
    sampled_tasks = set(blocks)
    out = dict(
        request='DTR-REQ-001 (P0) slice: source-block / fresh-pair / recovery evidence',
        source_frame=dict(
            n_fixed_task_blocks=len(all_tasks),
            tasks_with_eligible_prefix=len(elig), tasks_with_no_eligible_prefix=len(all_tasks) - len(elig),
            n_eligible_prefixes=sum(elig.values()),
            tasks_with_sampled_prefix=len(sampled_tasks), tasks_with_no_sampled_prefix=len(all_tasks) - len(sampled_tasks),
            tasks_eligible_but_unsampled=len(set(elig) - sampled_tasks),
            note='all 330 task blocks are retained; tasks without a sampled branch are part of the source frame, not dropped'),
        quantities=[
            dict(name='theta', role='PRIMARY repeated-source target (lead decision, theory_feedback_20260921_weighting.md)',
                 weighting='ratio of expected eligible-prefix totals over all 330 fixed task blocks; expected-prefix task weights E(M_g)/sum E(M_h)'),
            dict(name='mu_F', role='SECONDARY realized-frame mean',
                 weighting='sum_i d_i / N over the N=%d recorded eligible prefixes; task weights M_g/N within this frame' % sum(elig.values())),
            dict(name='B_hat', role='ARCHIVED sampled branch estimate',
                 weighting='mean of the 200 selected prefix contrasts, weight 1/200 each; selected-task means weight m_g/200'),
        ],
        weighting_note='equal-task weighting is NOT used for the branch side; it would change the question. '
                       'This weighting does NOT transfer to the A6 whole-policy comparisons, which keep their own equal-task target.',
        status='descriptive evidence only; no interpretation, coverage or power claim; no primary-target substitution',
        source_blocks=dict(n_source_tasks_with_branches=len(blocks), n_prefixes=len(per),
                           prefixes_per_task_distribution=dict(sorted(collections.Counter(blocks.values()).items())),
                           max_prefixes_in_one_task=max(blocks.values()),
                           frame=dict(N_eligible_prefixes=plan_doc['n_eligible_prefixes'],
                                      sampling_probability=plan_doc['sampling_probability'])),
        fresh_pairs=dict(n_same_arm_pairs=pairs, discordant=discord, discordance_rate=discord / pairs,
                         by_arm={a: dict(pairs=pairs_by_arm[a], discordant=disc_by_arm[a],
                                         rate=disc_by_arm[a] / pairs_by_arm[a]) for a in pairs_by_arm}),
        recovery=dict(prefixes_from_one_invocation=comp.get(1, 0), prefixes_spanning_two_invocations=comp.get(2, 0),
                      prefixes_only_original_invocation=only_lost, prefixes_only_recovery_invocation=only_rec,
                      continuations_by_invocation=dict(collections.Counter(r['inv'] for d in per.values()
                                                                          for rows in d.values() for r in rows))),
        assumptions=[
            dict(assumption='prefix sample is SRSWOR of fixed size m from the frame', status='CHECKABLE',
                 evidence='frozen branch_plan.json records N=%d, m=%d and the design seed; selection is reproducible from them'
                          % (plan_doc['n_eligible_prefixes'], len(per))),
            dict(assumption='continuations iid within arm given the prefix', status='UNKNOWN',
                 evidence='only the %.1f%% same-arm discordance is observed; identical distribution is not testable from 2 draws'
                          % (100 * discord / pairs)),
            dict(assumption='arms conditionally independent given the prefix', status='UNKNOWN',
                 evidence='arms share the restored transcript and serving process; no coupling test was designed'),
            dict(assumption='no execution shocks shared across prefixes', status='UNKNOWN',
                 evidence='continuations ran concurrently on shared servers; timing is recorded but shock sharing is not identified'),
            dict(assumption='complete source-task blocks are independent across all 330 tasks', status='UNKNOWN',
                 evidence='the 8 episodes of a task block share a task but ran interleaved with other tasks on the same two '
                          'servers over one execution period; shared execution-period or server effects are neither designed '
                          'against nor identified. Cross-prefix fresh-noise independence does not cover this assumption.'),
            dict(assumption='lost and recovered executions follow the same law', status='UNAVAILABLE from committed records',
                 evidence='the lost outcomes are not in the committed records, so this cannot be checked FROM THEM; retained '
                          'outcomes and hashes cannot establish the required law. This is not a claim that kernel stability '
                          'is uncheckable in principle, and no numerical drift allowance is supplied. %d prefixes span both invocations.'
                          % comp.get(2, 0)),
            dict(assumption='restored prefix equals the logged pre-call state', status='OBSERVED for recorded fields',
                 evidence='800/800 transcript hashes independently recomputed (restoration_recheck.json); '
                          'tool_result_reproduced remains a stored flag, not re-executed'),
        ])
    (common.RESULTS / 'analysis' / 'branch_evidence_table.json').write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ('source_blocks', 'fresh_pairs', 'recovery')}, indent=1))
    for a in out['assumptions']:
        print('  %-24s %s' % (a['status'], a['assumption']))


if __name__ == '__main__':
    main()
