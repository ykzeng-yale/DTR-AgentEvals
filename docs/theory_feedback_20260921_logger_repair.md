# Lead acceptance of the corrected logger slice

**21 September 2026, 06:50 UTC cycle.** Reviewed
`facd4a87df8af37e22b4df1b36bf579316a0f9ed`. **DTR-REQ-003 verdict: accept the v2 logger correction and
exact first-moment checks; proceed to the complete fixed-task and archive-matching branch specification.**
The earlier 60 incorrect cost-support labels are resolved in v2; the v1 artifact remains preserved.

## Independently checked evidence

Eight affected logger tests pass locally. The new
[independent audit](../scripts/audit_repair_logger_facd4a8.py) imports no worker code and uses latent-vector
masses to reconstruct trajectory-IPW success/cost, per-decision cost, standardized and pooled matched means,
support sets and logger occupancy. **All 468 policy/logger rows pass, with 4,272 exact numeric comparisons**
plus rowwise status/equality checks. The [audit record](audits/repair_logger_audit_facd4a8.json) pins both
input hashes; the accepted generator JSON and original logger v1 hashes are unchanged. The worker reports
136 broader tests passing; this review ran the eight affected tests, not that broader suite.

The counts and numerical conclusions reproduce independently:

- 348 supported rows recover success, cost and utility by trajectory IPW; per-decision cost also equals truth.
- 12 rows lack support only at the final opportunity. The known-cost per-decision estimator equals truth,
  while plain trajectory-IPW cost does not.
- 108 rows have earlier missing support; the proposed per-decision estimator strictly undercounts cost in
  these specific tables. Their labels no longer claim final-only identification.

A separate internal mathematical review accepts the set criterion and cost recursion. The correction
addresses an implementation/test defect. It does not establish interval coverage, finite-sample precision,
learned-policy performance or empirical history-adaptive improvement. No empirical archive or paper result changes.

## Why the cost correction works, and its limits

The target is expected total call cost under a frozen catalog policy and the specified stopping rule. With
known deterministic cost c, the current cost can be evaluated at the target action from the current observed
history before that action is assigned. Consequently, its weight needs supported past actions, not support
for the current action itself. The implementation now adds that contribution before testing current support.

For a deterministic policy, let tau be its first unsupported action along a target-policy trajectory, or
infinity if there is none. The truncated per-decision expectation includes costs through tau and drops
only subsequent active costs. Thus, in this finite model,

    target total cost - expected per-decision estimate
      = E_target[sum over active t > tau of c(policy_t(history_t))].

This follows by cancellation of positive logger probabilities along each matched prefix. At the first
zero-probability target action the current known cost remains included, but that prefix supplies no later
weighted observations. Final-only missing support therefore loses no cost contribution. Strict loss in the
108 earlier-missing rows follows here because both action costs are positive and every such prefix has
positive probability of failed repair followed by non-pass continuation. Replace the worker's phrase
"as it must" with this table-specific explanation: missing support alone does not universally force bias,
for example if all subsequent costs are zero. Coincidental equality would also not establish identification
under unrestricted unseen transitions. The evaluator's stated known-cost/unknown-transition model is appropriate.

The matched-mean labels are now explicit: equal-stratum standardization averages conditional ratios;
the pooled matched ratio divides pooled totals. Neither is a replacement for correctly weighted policy
evaluation. Both are verified as the quantities actually computed.

These logger checks cover the current fixed/prompt/last-feedback catalog. The logger functions pass `None`
as policy belief, so they do not yet evaluate the belief-dependent optimum. Keep that oracle in the exact
truth report. Do not claim its OPE implementation was checked or add such an extension instead of finishing
the task-block design. Costs here are known call penalties, not uncertain realized token, time or monetary costs.

## Next deliverable and acceptance criteria

**DTR-REQ-003, P1, remains running for fixed-task/branch design.** The accepted kernels and logger need no
additional control sweep. Deliver the already queued specification with:

1. Frozen task IDs and explicit stratum counts for n=250/1000; exact targets formed as means of task-specific
   expectations. Equal strata may use the current 1/2 mixture; otherwise recompute the target. Preserve
   complete zero-prefix task blocks. Define which randomization/execution streams are independent and which
   records share randomness, so the covariance model follows the actual study rather than an iid shortcut.
2. A distinct archive-matching module with an explicit initial-action kernel, eight source episodes/task,
   initial 4/4 allocation, later known assignment probabilities, finite-frame prefix sampling and independent
   fresh continuation draws under the proposed model. Keep it separate from the common-initial-small
   adaptation generator; neither silently substitutes for the other.
3. The original primary ratio of expected task totals, its numerator/denominator definitions and handling
   of an empty or insufficient realized prefix frame. Specify the policy when fewer prefixes than the fixed
   sample size exist before any execution; do not discard failed study repetitions or substitute a selected-task
   or conditional-frame target. Include small deterministic expectation/count/support checks and list remaining
   inference assumptions. Acceptance of a simulator specification will not validate historical recovery noise.

**DTR-REQ-002 qualification remains queued after this slice; DTR-REQ-001 is completed.** Acknowledge acceptance
and the next artifact with the existing IDs and accepted/running/completed/blocked/superseded statuses. No
duplicate jobs, new GPU/model/verifier/Monte Carlo execution, or interruption of separately authorized work.
Publish direct to main as Yukang Zeng <ykzeng2019@gmail.com>, author and committer.

**FULL-project readiness: 55%, change 0 percentage points, judgment range 45–65%.** Weights and category stages
are unchanged. The numerical repair is validated, but the next milestone is still open. Top remaining milestones:
useful validated inference/adequate comparisons; statistical validation and final empirical synthesis;
independent reproducibility, author metadata and submission packaging. Manuscript/PDF and empirical observations
are unchanged; no submission made.
