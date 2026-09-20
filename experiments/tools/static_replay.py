"""Static log replay on archived records: outcome copying and prefix-matched donor replay.

`docs/experiment_protocol.md` section 3.3 asks for "a fully specified static-replay rule" as a failure control, and
`docs/theory.md` section 7.1 gives the counterexample to holding the future history fixed. This implements two exact
rules on the frozen randomized log and scores them against the live executions of the same policies.

RULE A - OUTCOME COPYING. Take each confirm episode's recorded outcome as the outcome under any target policy; the
recorded future is copied while the action is relabelled. It is policy-independent by construction, so it is reported
to show it carries no policy-specific signal.

DECLARED POST-HOC SPECIFICATION (frozen 20 September 2026; this analysis was NOT pre-registered).
  Cohort: the 330 CONFIRM tasks; the five live targets the rule can represent (deterministic). A stochastic target is
  thresholded by the rule to a different policy and is therefore excluded from every summary, its row retained.
  Outcome: hidden-test success. Comparator truth: the finite live-policy task means, themselves noisy estimates.
  Donor ordering: smallest run index among episodes of the SAME task whose recorded action sequence shares the prefix.
  Stopping: the donor's stage-t recorded VISIBLE-VALIDATOR result (absorption is at validator pass, not hidden-test
  success); the donor's own recorded hidden-test success is then the replayed outcome.
  Fallback: if no donor matches the extended prefix, the previous donor's eventual outcome is used; if none exists at
  stage 0, the task contributes nothing. Fallback counts are reported per target and are NOT zero.

RULE B - PREFIX-MATCHED DONOR REPLAY. For each task and target policy, walk t = 0, 1, 2.
At stage t the policy's action a_t is taken; a DONOR is a logged episode of the SAME task whose recorded action
sequence starts with (a_0..a_t). Deterministic choice: the donor with the smallest run index. The donor's stage-t
recorded validation result decides whether the episode stops (validated -> its recorded hidden-test success is the
outcome) or continues. If no donor matches the prefix, the last matching donor's outcome is used. The substitution it makes is explicit: the intermediate STATE - which candidate
code exists, and why it failed - is taken from an episode that may have reached that stage for different reasons.

Neither rule uses randomization probabilities. Both are offline, use only the log, and are compared descriptively
with the cross-fitted DR estimate and with the finite live executions. `rule_b` REQUIRES its donor list sorted by run
index; the `by_task` caller supplies that order.

Post-hoc reporting only; outside the directories hashed into code_sha256; changes no frozen record.
"""
from __future__ import annotations
import json, sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
for sub in ('code_routing', 'common', 'dtr'):
    sys.path.insert(0, str(ROOT / 'experiments' / sub))
import common, analysis as A, policies as P, estimators_absorbing as EA  # noqa: E402


def by_task(episodes):
    out = {}
    for e in episodes:
        out.setdefault(e['task_uid'], []).append(e)
    for t in out:
        out[t].sort(key=lambda e: e.get('run', 0))
    return out


def rule_b(task_eps, pol) -> float | None:
    """Replay a trajectory for `pol` from logged episodes of one task. `task_eps` MUST be sorted by run index, because
    donor selection takes the first match. Returns the replayed success, or None when no initial donor exists."""
    prefix, last = [], None
    for t in range(3):
        state = dict(t=t, x_humaneval=task_eps[0]['benchmark'] == 'humaneval' and 1 or 0,
                     fail_class='start' if last is None else last['decisions'][t - 1]['validation']['fail_class'],
                     prev_actions=tuple(prefix), frac_fail=0.0 if last is None else last['decisions'][t - 1]['validation']['frac_fail'])
        # LIMITATION: the rule reads the target deterministically, so a STOCHASTIC target collapses to its modal
        # action and the rule cannot represent it. Stochastic policies are reported separately for that reason.
        a = 1 if float(pol(state)) >= 0.5 else 0
        cand = [e for e in task_eps if len(e['decisions']) > t and [d['a'] for d in e['decisions'][:t + 1]] == prefix + [a]]
        if not cand:
            return None if last is None else float(last['success'])
        donor = cand[0]
        prefix.append(a); last = donor
        if donor['decisions'][t]['validation']['passed']:
            return float(donor['success'])
        if len(donor['decisions']) <= t + 1:            # donor stopped here without validating (horizon)
            return float(donor['success'])
    return float(last['success'])


def diagnostics(tasks, pol):
    """Per-target donor behaviour: continuation after stage 0, missing donors at stages 1 and 2, tasks that fell back,
    and tasks whose trajectory was stitched from more than one donor."""
    c0 = m1 = m2 = fb = chg = 0
    for _t, eps in tasks.items():
        prefix, last, used = [], None, []
        for st in range(3):
            state = dict(t=st, x_humaneval=1 if eps[0]['benchmark'] == 'humaneval' else 0,
                         fail_class='start' if last is None else last['decisions'][st - 1]['validation']['fail_class'],
                         prev_actions=tuple(prefix),
                         frac_fail=0.0 if last is None else last['decisions'][st - 1]['validation']['frac_fail'])
            a = 1 if float(pol(state)) >= 0.5 else 0
            cand = [e for e in eps if len(e['decisions']) > st and [d['a'] for d in e['decisions'][:st + 1]] == prefix + [a]]
            if not cand:
                m1 += st == 1; m2 += st == 2; fb += last is not None
                break
            donor = cand[0]; used.append(donor['episode_id']); prefix.append(a); last = donor
            if donor['decisions'][st]['validation']['passed'] or len(donor['decisions']) <= st + 1:
                break
            c0 += st == 0
        chg += len(set(used)) > 1
    return dict(continue_after_stage0=c0, missing_donor_stage1=m1, missing_donor_stage2=m2,
                tasks_using_fallback=fb, tasks_changing_donor=chg)


def prefix_coverage(tasks) -> dict:
    c2 = c3 = 0
    for eps in tasks.values():
        seqs = {tuple(d['a'] for d in e['decisions']) for e in eps}
        c2 += len({s[:2] for s in seqs if len(s) >= 2}) == 4
        c3 += len({s[:3] for s in seqs if len(s) >= 3}) == 8
    return dict(tasks_with_all_4_length2_prefixes=c2, tasks_with_all_8_length3_prefixes=c3, n_tasks=len(tasks))


def main():
    cfg = common.load_config(); K = cfg['horizon']
    log, _ = A.read(common.RESULTS / 'log' / 'episodes.jsonl', cfg)
    live, _ = A.read(common.RESULTS / 'live' / 'episodes.jsonl', cfg)
    conf = [e for e in log if e['split'] == 'confirm']
    tasks = by_task(conf)
    cls = A.policy_class(common.RESULTS)
    live_names = sorted({e['policy'] for e in live})
    rule_a = float(np.mean([e['success'] for e in conf]))      # policy-independent by construction

    rows = []
    for nm in live_names:
        pol = cls[nm]
        # RULE B, one stitched value per task, then the task mean
        vals = {t: rule_b(eps, pol) for t, eps in tasks.items()}
        ok = np.array([v for v in vals.values() if v is not None], dtype=float)
        n_nodonor = sum(v is None for v in vals.values())
        # live truth, per task
        le = [e for e in live if e['policy'] == nm]
        lt, lv = EA.cluster_means(np.array([e['task_uid'] for e in le], object), np.array([e['success'] for e in le], float))
        live_s = pd.Series(lv, index=lt)
        # cross-fitted DR on the same confirm log
        L = EA.from_episodes(conf, K, P.state_key, 'success')
        dr = EA.summary(EA.cluster_scores(L, pol)['dr'])
        common_t = np.intersect1d(np.array(sorted(t for t, v in vals.items() if v is not None), dtype=object), lt)
        b_paired = np.array([vals[t] for t in common_t], dtype=float)
        l_paired = live_s[common_t].to_numpy()
        d = b_paired - l_paired
        rows.append(dict(policy=nm, live_success=float(live_s.mean()), dr_success=dr['estimate'], dr_se=dr['se'],
                         static_A=rule_a, static_B=float(ok.mean()), static_B_tasks=int(len(ok)), no_donor_tasks=int(n_nodonor),
                         B_minus_live_discrepancy=float(d.mean()), B_minus_live_discrepancy_se=float(d.std(ddof=1) / np.sqrt(len(d))),
                         A_minus_live_discrepancy=rule_a - float(live_s.mean()), DR_minus_live_discrepancy=dr['estimate'] - float(live_s.mean())))
    df = pd.DataFrame(rows)
    stochastic = {'soft_escalation_d2', 'soft_escalation_d4'}
    df['rule_can_represent'] = ~df.policy.isin(stochastic)
    det = df[df.rule_can_represent]
    engaged = float(np.mean([e['n_decisions'] > 1 for e in conf]))   # logger continuation, NOT replay continuation
    out = common.RESULTS / 'analysis'
    df.to_csv(out / 'static_replay_comparison.csv', index=False)
    diag = {nm: diagnostics(tasks, cls[nm]) for nm in det.policy}
    (out / 'static_replay_diagnostics.json').write_text(json.dumps(dict(prefix_coverage=prefix_coverage(tasks), per_target=diag), indent=1))
    summary = dict(rule_A_value=rule_a,
                   cohort='330 CONFIRM tasks; 5 deterministic live targets; hidden-test success; live task means as comparator',
                   spearman_static_B_vs_live_cohort=float(det.static_B.corr(det.live_success, method='spearman')),
                   spearman_DR_vs_live_cohort=float(det.dr_success.corr(det.live_success, method='spearman')),
                   mean_abs_discrepancy_A_cohort=float(det.A_minus_live_discrepancy.abs().mean()),
                   logger_continuation_share_of_confirm_episodes=engaged,
                   deterministic_policies=int(len(det)),
                   mean_abs_discrepancy_B_cohort5=float(det.B_minus_live_discrepancy.abs().mean()),
                   mean_abs_discrepancy_DR_cohort5=float(det.DR_minus_live_discrepancy.abs().mean()),
                   note_stochastic='rule B reads the policy deterministically, so stochastic targets collapse to their '
                                   'modal action; their rows are reported but excluded from the aggregate',
                   mean_abs_discrepancy_B_all6_mixed_cohort=float(df.B_minus_live_discrepancy.abs().mean()),
                   mean_abs_discrepancy_A_all6_mixed_cohort=float(df.A_minus_live_discrepancy.abs().mean()),
                   mean_abs_discrepancy_DR_all6_mixed_cohort=float(df.DR_minus_live_discrepancy.abs().mean()),
                   max_abs_discrepancy_B_all6_mixed_cohort=float(df.B_minus_live_discrepancy.abs().max()),
                   max_abs_discrepancy_DR_all6_mixed_cohort=float(df.DR_minus_live_discrepancy.abs().max()),
                   n_policies=len(df))
    (out / 'static_replay_summary.json').write_text(json.dumps(summary, indent=1))
    pd.set_option('display.width', 200)
    print(df.round(4).to_string(index=False)); print(); print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
