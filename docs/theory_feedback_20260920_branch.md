# Completed-branch review and response to the experiment handoff

**20 September 2026, 04:24 UTC review cycle; reviewed through `d4997c68ca93a4d5835bcc578470af472be311b2`.** This responds to the new commits `f984f15`, `0e5a1e2` and `d4997c6` and the workstream's committed reply. No new model inference, candidate-code execution or Monte Carlo sweep is performed here. The manuscript PDF remains unchanged.

## Accepted progress and current evidence

The complete 800-continuation branch dataset is now published, together with the recovery manifest and a publication-checking utility. The [independent artifact audit](audits/code_routing_completed_branch_audit_d4997c6.json) reconciles all frozen IDs, seeds, assignments and parent-prefix hashes; all 800 recorded restoration flags are true. This verifies saved records, not fresh runtime restoration. The earlier 135 completed rows and 243 durable-decision rows remain preserved byte-for-byte; a second invocation adds 665 completed rows. Original source and generated outputs remain available in Git history.

Several requested reporting fixes are accepted: the combined improvement rule is limited to three live-evaluated policies; the learned-versus-large result no longer establishes equivalence; training and confirmation calls are distinguished; the figure uses the success contrast on the success panel and no longer clips the calibration intervals; and Theorem 5 is described as a hypothetical scale calculation rather than a certificate for the cross-fitted scores. The generator/analysis core has not changed, and a restored-state enforcement check is still not implemented there.

## The linked comparison does not preserve the original target

The original branch estimate averages continuation differences over **200 sampled prefixes**; the log estimate is a **pooled Hájek contrast over 564 eligible source prefixes**. Both concern the logger's first-failure continuation population under the specified sampling and execution assumptions.

`experiments/tools/linked_branch_uncertainty.py` instead averages within each task, requires a positive realized log denominator for **both** arms in that task, retains only **42 tasks**, and averages their task-specific contrasts equally. This changes weights and selects a subset using realized compatible trajectories, including assignments and stopping. A zero arm denominator within a small task does not imply structural lack of support for the pooled estimator. The resulting −0.091 comparison is an exploratory selected-task summary, not a covariance correction for the original −0.0147 difference.

The original pooled point estimates remain 0.1200 and approximately 0.1347. Correcting their joint standard error alone must leave their difference unchanged. Neither the original independence-based interval nor the selected-task interval is accepted as a validated full-prefix comparison. The current third figure panel plots the original points while annotating the selected-task difference; this must be corrected before manuscript use.

Independent numerical reconstruction gives the following audit trail. The 42-task restriction retains only 98/200 sampled branch prefixes and 240/564 eligible log prefixes; the full source contains 152 eligible tasks, and the 200 sampled prefixes span 103 tasks.

| Calculation | Branch estimate | Log estimate | Difference |
|---|---:|---:|---:|
| Original prefix mean and pooled log ratios | 0.120000 | 0.134654 | −0.014654 |
| Original weighting, restricted to the 42 tasks | 0.086735 | 0.143393 | −0.056659 |
| New equal-task weighting on those tasks | 0.096825 | 0.188265 | −0.091440 |

### Algebra required for a target-preserving repair

Let `A_g` be the sum of sampled-prefix branch contrasts in source task `g`, and `m_g` its sampled-prefix count. Let `N_ga` and `D_ga` be the log weighted-success and weight totals for continuation arm `a`. Use **all source tasks**, permitting zero contributions from tasks without sampled branches or without observed compatible log continuations. Define

\[
\widehat B=\frac{\sum_g A_g}{m},\quad m=\sum_g m_g,\qquad
\widehat v_a=\frac{\sum_g N_{ga}}{D_a},\quad D_a=\sum_g D_{ga},\qquad
\widehat\Delta=\widehat B-(\widehat v_1-\widehat v_0).
\]

For globally positive denominators, the derivative when **both sources** receive common task weights `1 + epsilon h_g` is

\[
\left.\frac{d\widehat\Delta(\epsilon)}{d\epsilon}\right|_{0}
=\sum_g h_g U_g,\qquad
U_g=\frac{A_g-\widehat Bm_g}{m}
-\frac{N_{g1}-\widehat v_1D_{g1}}{D_1}
+\frac{N_{g0}-\widehat v_0D_{g0}}{D_0},\qquad \sum_g U_g=0.
\]

This follows directly by differentiating each ratio. It is an algebraic identity, **not** a completed variance theorem for this design. In particular, the fixed-size sampling of 200/564 prefixes without replacement introduces a second sampling stage; finite-prefix versus population targets, selection probabilities, continuation replication and cross-task selection dependence must be treated explicitly before claiming an interval. Merely applying an ordinary task bootstrap to the selected 42 tasks does not supply that justification.

A separate mathematical review confirmed the identity; deterministic central-difference checks over all 330 source-task multipliers have maximum error below `7e-12`. The [reproducible audit](audits/check_branch_linkage_d4997c6.py) and [saved numerical record](audits/theory_branch_linkage_audit_20260920.json) use pinned inputs and assert no new standard error or interval.

Even without log estimation, prefix weighting and equal task weighting differ: one task with one prefix of contrast 0 and another with three prefixes of contrast 1 has prefix mean 3/4 and equal-task mean 1/2. Dropping tasks based on their realized arm denominators changes the target again. Preserve the target first; then derive and validate its uncertainty.

## Recovery provenance and resource accounting

Protocol §11 reports that 665 original completions were lost when publishing/rebasing replaced files still open in the runner, and were rerun with the frozen IDs/seeds. The preserved manifests and rows are consistent with a 135-survivor/665-recovery split. The missing original outcomes, their invisibility to operators and exact original execution costs are not recoverable from the committed data; these remain operator-reported facts. Do not state that the incident could not affect inference merely because outcomes were reportedly not inspected. Identical seeds do not independently establish identical missing outcomes or stable execution. State the required loss/recovery and execution-stability assumptions and retain the incident as a limitation.

Records from the two invocations must be distinguished by invocation as well as episode, attempt and stage: `attempt=1` is reused in the recovery run. A technical count of zero infrastructure-error retries does not mean no execution was repeated. The observed branch calls describe retained completed records and exclude unrecovered execution. Resource comparisons must distinguish prefix acquisition, useful retained continuations, recovery overhead and any unknown cost. The observed 8% disagreement is a sample statistic for two fresh seeds, not an irreducible noise bound. Matching transcript hashes and selected tool-result fields is evidence about those recorded checks, not universal replayability of the entire environment.

There are 1,439 durable branch rows: 1,434 match retained completed episodes and five belong to the earlier invocation for four recovered episode IDs. Do not silently discard those five rows or count them as five additional completed calls. The reported 13,001 calls are **log + live + retained branch**; adding the 163-call pilot gives **13,164 calls attached to retained completions across all four stages**. Both totals exclude unrecovered executions and environment-construction calls. Total physical execution cost is not reconstructible from these records alone.

## Required next changes and acceptance criteria

1. **Repair branch inference for the original target.** Keep the pooled point estimates and all source tasks, declare finite-prefix versus population inference, and account for prefix sampling, fresh continuations and shared records jointly. Add deterministic unequal-prefix and missing-within-task-arm examples, plus an exact or justified design-aware variance check. Label the 42-task result exploratory; do not substitute it for the planned comparison.
2. **Strengthen publication and recovery checks.** The new verifier improves ID accounting, but a printed torn-line count does not currently fail the gate; duplicate completed IDs are collapsed by the resolver, and invocation-aware durable decisions, frozen metadata and restoration flags are not checked. Add fixtures that fail for a torn tail, duplicate success row, metadata mismatch and false restoration flag. Check invocation-linked decisions and archive retained recovery evidence. Refuse publication while the actual host writer is active; a cloned checkout cannot attest remote process status.
3. **Finish reporting corrections before paper integration.** Remove the remaining calibration/causal-call-count and generic ESS-efficiency claims. The 2.19 variance ratio is at unequal recorded costs and is not replication of an equal-compute simulation result; the 39% call ratio omits prefix acquisition and lost-run overhead. Fix the third-panel estimand mismatch and preserve distinguishable figure versions. Then complete the outstanding comparator, independent validation and manuscript/package work. New model/GPU and Monte Carlo studies remain queued for later in this monitoring task.

**Overall readiness remains about 60% (change: 0 percentage points from the last issue #4 checkpoint; judgment range 50–65%).** Category stages remain 75/75/50/50/25 under the same weights. Completed branch records and accepted reporting repairs are real progress, but target-preserving inference, recovery accounting, required comparisons and manuscript integration are still unfinished. This is five points below the workstream's provisional 65% judgment; it does not change the rubric or claim a submission has occurred.
