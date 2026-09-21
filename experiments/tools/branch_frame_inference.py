"""A SECONDARY conditional-frame target for the branch-minus-log comparison, with its frame-conditional variance.

STATUS (corrected 21 Sep after review, docs/theory_feedback_20260921_conditional_frame.md): this is NOT the primary
B2 target and does NOT discharge B2. The primary fixed-benchmark target is the ratio-of-expected-source-totals
contrast Delta = theta - nu_1 + nu_0 of docs/theory_branch_fixed_benchmark_bound.md eq. 2, and its source/selection
uncertainty remains open. This module answers a different, secondary question whose point estimate happens to equal
the archived pooled difference. The first version (output preserved as branch_frame_inference_v1_981f7b9.json)
over-claimed on three points corrected below: it said this "settles" the independence objection and "supersedes"
earlier scales, it mislabelled the variance components (7:1), and it said a test of Delta_F = 0 was impossible.

SECONDARY TARGET (finite frame). Condition on the complete source frame F: the realized task set, the realized
randomized log, and the N eligible first-failure prefixes it contains. Let d_i be the expected large-minus-small
continuation outcome at prefix i under the frozen continuation rule, and

    mu_F = N^{-1} sum_i d_i,          Delta_F = mu_F - L(F),

where L(F) is the pooled Hajek log contrast, which is MEASURABLE with respect to F. The estimator is
Delta_hat = B_hat - L(F).

CONDITIONAL VARIANCE. Conditional on F, L(F) is a constant, so Var(Delta_hat | F) = Var(B_hat | F) under the
stated sampling/execution assumptions (that document's eq. 3). This is a property of the SECONDARY target only; it
does not validate or replace the earlier independence-sum or task-derivative scales, which remain unvalidated
calculations for other questions.

VARIANCE (that document's Proposition, eq. 1-2), for simple random sampling of m of N prefixes without replacement,
with r_ia >= 2 continuations per arm drawn independently of the selection:

    Var(B_hat | F) = (1-f)/m * S_d^2 + vbar/m,        f = m/N
    V_hat_F        = (1-f)/m * s^2_{dhat,S} + (f/m) * mean_i vhat_i,     vhat_i = s^2_{i1}/r_i1 + s^2_{i0}/r_i0

V_hat_F is unbiased for Var(B_hat | F); no independence between dhat_i and vhat_i within a prefix is required.

WHAT THIS DOES **NOT** ESTABLISH, stated because the estimate is easy to over-read:
  * a conditional confidence set for Delta_F CAN in principle be inverted to test Delta_F = 0; what is missing is a
    justified interval construction for the stated execution model, not the logic of the test. And even a
    conditional rejection would concern agreement with THIS realized log reference: kernel stability does not force
    Delta_F = 0, because the realized log contrast has its own sampling error;
  * it is not the unconditional task-population claim, which needs Var{mu_F - L(F)} from a source model
    (eq. 4) that is not supplied and remains open;
  * an unbiased variance estimator does not give a normal interval nominal coverage; that needs a limit theorem;
  * it assumes continuations are iid within arm, arms conditionally independent given the prefix, and no execution
    shocks shared across prefixes. None of those is established for this system, and 2 of 200 prefixes draw their
    replicates from two different invocations (the lost run and its recovery), so for those the assumption spans
    two execution epochs.

  python experiments/tools/branch_frame_inference.py
"""
from __future__ import annotations
import json, sys
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
    N = plan_doc['n_eligible_prefixes']
    br, _ = A.read(common.RESULTS / 'branch' / 'episodes.jsonl', cfg)

    per = {}
    for e in br:
        pid = e.get('parent_episode_id') or plan[e['episode_id']]['parent_episode_id']
        arm = e.get('fork_arm') or ('large' if plan[e['episode_id']]['forced_arm'] else 'small')
        per.setdefault(pid, {}).setdefault(arm, []).append((e.get('invocation'), float(e['success'])))

    dhat, vhat, mixed = [], [], 0
    for pid, d in sorted(per.items()):
        if len(d.get('large', [])) < 2 or len(d.get('small', [])) < 2:
            continue
        y1 = np.array([y for _, y in d['large']], float)
        y0 = np.array([y for _, y in d['small']], float)
        dhat.append(y1.mean() - y0.mean())
        vhat.append(y1.var(ddof=1) / len(y1) + y0.var(ddof=1) / len(y0))
        if len({inv for arm in d.values() for inv, _ in arm}) > 1:
            mixed += 1
    dhat, vhat = np.array(dhat), np.array(vhat)
    m = len(dhat); f = m / N
    B = float(dhat.mean())
    s2 = float(dhat.var(ddof=1))
    vbar_hat = float(vhat.mean())
    V = (1 - f) / m * s2 + (f / m) * vbar_hat
    se = float(np.sqrt(V))

    # L(F): the pooled Hajek log contrast, measurable with respect to the frame
    log, _ = A.read(common.RESULTS / 'log' / 'episodes.jsonl', cfg)
    num = {0: 0.0, 1: 0.0}; den = {0: 0.0, 1: 0.0}
    for e in log:
        if e['split'] != 'confirm' or e['n_decisions'] < 2:
            continue
        ds = e['decisions']; a1 = ds[1]['a']; a2 = ds[2]['a'] if len(ds) > 2 else None
        w = 2.0 * (1.0 if a2 is None else (2.0 if a2 == a1 else 0.0))
        if w:
            num[a1] += w * e['success']; den[a1] += w
    L = num[1] / den[1] - num[0] / den[0]
    delta = B - L

    # the first estimator term uses the variance of OBSERVED contrasts, which already contains execution noise; the
    # true split subtracts the mean within-prefix variance to obtain the latent between-prefix variance
    S2_latent = s2 - vbar_hat
    latent_between = (1 - f) / m * S2_latent
    execution_true = vbar_hat / m
    out = dict(
        status='SECONDARY conditional-frame target; NOT the primary B2 target and does NOT discharge B2',
        primary_target='ratio-of-expected-source-totals contrast Delta = theta - nu_1 + nu_0 (theory_branch_fixed_benchmark_bound.md eq. 2); uncertainty OPEN',
        target='secondary finite frame: mu_F - L(F), conditional on the realized task set, randomized log and eligible prefix frame',
        N_eligible_prefixes=N, m_sampled=m, sampling_fraction=f,
        B_hat=B, L_of_F=float(L), delta_hat=float(delta),
        estimator_term_1_observed_between=float((1 - f) / m * s2),
        estimator_term_2=float((f / m) * vbar_hat),
        estimator_terms_note='these are the two TERMS of the unbiased estimator (eq. 2); term 1 uses the variance of '
                             'observed contrasts and so already contains execution noise. They are NOT the variance components.',
        latent_between_prefix_component=float(latent_between),
        execution_component=float(execution_true),
        latent_between_to_execution_ratio=float(latent_between / execution_true),
        var_hat_frame=float(V), se_frame=se,
        interval_95_normal=[float(delta - 1.96 * se), float(delta + 1.96 * se)],
        sample_variance_of_contrasts=s2, mean_within_prefix_variance=vbar_hat,
        prefixes_with_replicates_from_two_invocations=mixed,
        relation_to_earlier_scales=dict(independence_sum_se=0.0572, influence_function_scale=0.0484,
            note='these answered other questions and remain unvalidated; this secondary result neither replaces nor validates them'),
        does_not_establish=['the PRIMARY B2 target or its source/selection uncertainty',
                            'a valid interval: a conditional test of Delta_F=0 is possible in principle but needs a justified construction',
                            'that a conditional rejection would refute kernel stability (it concerns agreement with this realized log only)',
                            'the unconditional task-population claim (needs Var{mu_F - L(F)}, not supplied)',
                            'nominal coverage of the normal interval (needs a limit theorem)',
                            'the iid/independence execution assumptions, which are assumed not shown'])
    (common.RESULTS / 'analysis' / 'branch_frame_inference.json').write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    main()
