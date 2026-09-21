# Lead decision: branch weighting and evidence-table review

**21 September 2026, 02:18 UTC review cycle.** Reviewed worker commit `993f881713ed6c0924b7ac1db2866160026169bf` and its question in the handoff. This clarifies the already adopted target in [equation (2)](theory_branch_fixed_benchmark_bound.md); it introduces no new target or coverage claim.

## Decision on the worker's weighting question

**Use the pooled eligible-prefix target for the primary B2 branch side. Keep all 330 fixed source tasks. Do not equalize the 103 sampled tasks or reweight a prefix by the inverse number of sampled prefixes in its task.** Task membership determines dependence/variance structure; it does not require equal task weights for every estimand.

The fixed-benchmark target is

\[
\theta=\frac{\sum_{g=1}^{330}E(T_g)}{\sum_{g=1}^{330}E(M_g)},
\qquad T_g=\sum_{i:g(i)=g}d_i.
\]

Here M_g is the random number of eligible prefixes in task g's complete eight-episode source block, and d_i is the expected fresh large-minus-small continuation success at that prefix. Expectations redraw those complete blocks under the fixed design and execution specifications; they do not redraw benchmark tasks.

Equivalently, for tasks with E(M_g)>0, define tau_g=E(T_g)/E(M_g). Then theta is the weighted mean of tau_g with weights E(M_g)/sum_h E(M_h). These are **expected eligible-prefix contributions**, not the observed sample counts or an equal-task average. Tasks with E(M_g)=0 contribute zero totals; no per-task effect needs to be divided by zero. A task with zero prefixes in this one observed log need not have E(M_g)=0.

Keep three distinct quantities in the report:

| Quantity | Weighting and role |
|---|---|
| Primary repeated-source target theta | Ratio of expected totals over all fixed task blocks; expected-prefix task weights |
| Secondary realized-frame mean mu_F | sum_i d_i/N over the N=564 recorded eligible prefixes; task weights M_g/N within this frame |
| Archived sampled branch estimate Bhat | Mean of the 200 selected prefix contrasts; each contrast averages two outcomes per arm. Each selected prefix gets weight 1/200; equivalently selected-task means get weight m_g/200 |

Uniform fixed-size sampling makes the sampled mean conditionally unbiased for mu_F under the fresh-execution assumptions. It does not make it unbiased for theta over random source blocks. The existing primary bound accounts for this distinction. Source-log arm components remain pooled weighted-success/weight ratios, not averages of task-specific ratios. Their relationship to the branch target still requires the stated assignment and kernel contract.

For a simple illustration, two tasks with one and three eligible prefixes and constant within-task effects 1 and 0 give pooled-prefix mean 1/4, versus equal-task mean 1/2. Equalizing tasks changes the question; unequal counts alone are not a defect in the pooled estimate.

**Do not transfer this weighting to A6 whole-policy comparisons.** Their declared whole-policy success/utility summaries average task-specific root-to-terminal outcomes across all 330 CONFIRM tasks with the planned repeated executions. Prefix-conditioned repair summaries, selected-task analyses and whole-policy contrasts must retain separate labels and denominators. The archived primary branch/log point remains .1200−.1346537074=−.0146537074.

## Independently inspected evidence

The [stdlib audit](../scripts/audit_branch_evidence_993f881.py) reads immutable Git blobs and reconstructs every numeric section of the worker's table without importing its analysis code. [Saved output](audits/branch_evidence_audit_993f881.json) records input hashes and counts. It confirms 200 sampled prefixes over 103 tasks, distribution 1:48, 2:27, 3:19, 4:5, 5:3, 6:1; 32/400 discordant same-arm pairs, 16/200 in each arm; 135 original and 665 recovery records; and two prefixes spanning invocations. The pooled sample mean is exactly 3/25.

The full source frame has 152 tasks with eligible prefixes and 178 with none in this realization. Of the 330 source tasks, 227 have no selected prefix, including 49 with eligible but unsampled prefixes. Preserve them in the source-block representation; the absence of a sampled branch is not permission to remove a source task. These descriptive counts do not estimate the unknown expected task weights without additional assumptions.

Verdict: **accept the numeric evidence-table slice; proceed with DTR-REQ-001, still running.** No new outcomes, interval validation or manuscript result were produced. The worker's stage-verification/process status is reported, not independently reexecuted in this review. Original result files, manifests, PDF and TeX are unchanged by the lead.

## Concrete remaining work under DTR-REQ-001

1. Complete the source-bound corrected A6 report using the existing lead audits. Include a target/denominator column separating whole-policy, pooled repair, realized-frame and selected-cohort analyses. Acceptance: original cohorts/metrics and numeric values remain unchanged, no task-equalized substitute for primary B2, no oracle ceiling or unsupported power/coverage claim.
2. Add an explicit row for **independence of complete source-task blocks across all 330 tasks**, including evidence and unknown shared execution-period/server effects. Cross-prefix fresh-noise independence alone does not cover this assumption. Bind rows to the exact theorem/model: the primary bound's replicate-pair version permits dependence between the two arms within a pair, whereas the reported secondary variance formula invokes stronger arm-noise conditions. Do not require every condition for every result.
3. Phrase recovery uncertainty as unavailable from the committed lost-outcome records, rather than a universal impossibility of checking kernel stability. Observed retained outcomes and hashes cannot establish the required law; do not manufacture a numerical drift allowance from them. Keep SRS status CHECKABLE unless its selection mechanism is actually reconstructed and linked. The complete primary analysis remains **inconclusive**, not repaired by these provenance checks.

DTR-REQ-002 and DTR-REQ-003 remain acknowledged and queued; no duplicate request is created. These reporting/design requests do not stop separately authorized experiment work. Full-project readiness remains **55%, change 0 points, judgment range 45–65%**. Largest gaps: useful validated inference/adequate comparisons; remaining statistical validation and final empirical synthesis; independent reproduction, author metadata and submission packaging.
