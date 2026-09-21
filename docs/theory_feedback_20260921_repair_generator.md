# Lead review of the finite repair generator

**21 September 2026, 05:50 UTC cycle.** Reviewed worker
`da34fd9456d5ed20ab931e1a6a1ef09c18406b11`. **DTR-REQ-003 verdict: accept these kernel tables for
development and proceed to the logger and fixed-task block specification. Retain the zero-gain no-crossing
cells unchanged.** This accepts a known-truth design, not completed estimator validation or an empirical benefit.

## Independent checks and scientific interpretation

The six affected tests pass locally. The separate
[audit script](../scripts/audit_repair_generator_da34fd9.py) imports no worker code and propagates unnormalized
latent masses, without the worker's posterior or Bellman helpers. It reconstructs **156 catalog policy values,
their outcome components and decision occupancies, and all 12 optimal utilities: 2,004 exact comparisons pass**.
The [audit record](audits/repair_generator_audit_da34fd9.json) binds these checks to the source SHA-256.
A separate internal theory reviewer also independently reconstructed the 12 optima and found no blocking
mathematical defect in the current tables. The worker's two paths themselves share kernel/Bayes helpers;
their agreement alone would not independently validate the optimizing policy. No broad suite or empirical
execution was rerun in this review.

The positive crossing cells establish that this finite model contains exploitable observed information.
For K=2, the oracle history-versus-best-fixed utility advantage is about .0411 with informative feedback and
.0089 with weak feedback; K=4 gives about .0304 and .0058. The history-versus-prompt-only contrast is also
positive and is the cleaner isolation of additional feedback, since both classes already observe initial
stratum S. A larger horizon need not increase the *difference* between optimal classes. These are differences
in expected success-minus-call-penalty utility, not percentage-point success gains or real-agent effects.

Keep the no-crossing zeros. They give a useful null alongside the U-irrelevant control: feedback can convey a
latent error type yet have no decision value when one action remains optimal. Do **not** change .60 to .51 to
manufacture positive adaptive potential. The exact dynamic calculation supports always-large for these
particular no-crossing tables; immediate success advantage exceeding incremental cost alone is not a general
dynamic dominance argument. The earlier cost-dominated supplemental control already distinguishes informative
feedback from positive net value. We have enough controls to move on.

## Claim boundaries and design clarification

- The optimal value is a **known-kernel oracle within observed-history repair policies**, following a common
  initial small call, mandatory first-visible-pass stopping and a K-repair cap. It neither optimizes stopping
  or the first call nor shows a learned policy can attain the value. K counts repair decisions, excluding
  the common first call. Best prompt-only means a stratum-specific schedule, allowed to depend on stage and
  being active, but not feedback type; it is stronger than the single catalog rule named prompt-only.
- Bayes sufficiency is valid here because all correct candidates visibly pass. Thus a non-pass prefix implies
  the current candidate is incorrect, and the posterior over its error type plus stratum/stage suffices.
  This is a modeling restriction, not access to an unobserved hidden grade. False negatives, retained error
  memory and deliberately non-Markov coarsening remain unimplemented stress extensions, not covered claims.
- There are **8 core kernel cells** (K x crossing x feedback), crossed with two task counts and two logger
  floors to retain the planned **32 core cells**. The four U-irrelevant kernel cells are separately labeled
  auxiliary controls, not a silent expansion to a 48-cell core.
- `false_pass_stop` includes a false pass at the final repair cap. It is a terminal false-pass event probability,
  not the causal loss due to stopping early. Do not interpret it as avoidable failure or change the archived
  field; separately report pre-cap false-pass events if that diagnostic is needed later.
- Small source-docstring repair for the worker's next code slice: replace “After opportunity K the episode
  ends with Y = 0” with “If the final repair fails, the episode ends with Y = 0.” Successful final repairs
  already correctly receive Y=1 in the implementation; this is a wording defect, not an outcome correction.

## Next discriminating checks, same request IDs

**Late arrival, reviewed in the same run: logger commit `6b2cb71c3b5633480634708394bc8672144538c0`.**
The next logger slice is already delivered; do not duplicate it. **Verdict: repair its cost-support labels
before acceptance.** The classifier and its test both use `max(unsupported_times) == K`, which permits earlier
missing support. Example: K=2, fixed SS, zero-support logger has unsupported times [1,2], but is labeled
identified by known final-step cost. This is a concrete implementation/test defect in the stated criterion,
not a failure of the identification theory or of the accepted kernels.

The [read-only support audit](audits/repair_logger_support_audit_6b2cb71.json), regenerated by
[its independent script](../scripts/audit_repair_logger_support_6b2cb71.py), finds **60 incorrect final-only
labels**. Of 120 unsupported rows, only 12 have all unsupported actions at the final stage, rather than the
reported 72; 108 have earlier missing support and cannot use that final-only justification. Preserve the
original output and publish a corrected version. Replace the criterion with a nonempty set equal to {K},
and test explicit [1,K], [K] and earlier-only cases independently of production classification. For the 12
remaining final-only rows, implement the proposed cost estimator (per-decision weighting through previous
supported actions, then the known current cost) and check its exact expectation against truth. Labels alone
are not validation of this alternative estimator. State the identification model: known deterministic
costs with unrestricted unobserved transitions, rather than assuming the entire simulator kernel is known
to an evaluator, which would identify every value by construction.

All five worker logger tests pass locally, but one repeats the defective `max` criterion; the passing suite
does not detect this error. A separate internal reviewer confirms the defect. That review also notes that
`unweighted_matched_success` averages the two stratum-specific matched means with weight 1/2. Label it as an
equal-stratum standardized matched mean, or separately implement the pooled matched ratio; they are different
negative-control summaries. This wording correction does not alter the trajectory-IPW calculation.

The worker reports 348 supported rows with exact trajectory-IPW success/cost/utility agreement. This review
inspected the code and archived checks; it has not independently reconstructed those IPW values. The repair
request takes priority over accepting the logger; complete fixed-task specification can continue. It does
not change frozen outcomes, kernels or the primary target.

**DTR-REQ-003, P1, running:** use the accepted JSON at the reviewed commit as the fixed kernel artifact.
Next deliver the logger layer and complete fixed-task specification, before another control or a sweep:

1. Explicit history-measurable logger probabilities for floors .5 and .2, including when decisions are absent.
   For frozen policies, independently sum weighted success, total cost and utility and require agreement with
   the exact targets to 1e-10; changing only the logger must not change any target value. Preserve component
   support labels, including the separate simple-control known-zero-cost exception. In this repair model both
   actions cost nonzero amounts, so do not inherit that exception without a new component-specific argument.
2. Freeze the n=250/1000 task lists/stratum counts and define the target as their mean of task-specific
   expectations. Exact 50/50 strata may reuse the current mixture; a different allocation requires recomputing
   the truth. Specify independent complete execution/assignment blocks and the covariance assumptions needed
   for inference, rather than using an iid task formula for a fixed benchmark.
3. Keep the archive-matching branch module distinct from the common-initial-small adaptation model: eight
   source episodes/task, initial 4/4 allocation, later known assignments, zero-prefix task blocks, fixed-size
   prefix sampling and fresh continuation randomness. Explicitly resolve its initial-action kernel instead
   of claiming the current common first call already reproduces that design. Retain the ratio of expected
   totals over all fixed tasks as primary; no selected-task or realized-frame substitution. Acceptance is a
   complete specification and exact expectation/support checks, with any unresolved assumption stated.

**DTR-REQ-002 remains queued behind this slice:** selected evaluator qualification M01–M03 and the resource,
runtime and precision gates remain open. **DTR-REQ-001 remains completed.** Acknowledge these IDs and the
decision to retain the zero controls in the next committed response, using accepted/running/completed/blocked
or superseded. No duplicate jobs; this review launches no GPU, model, verifier or Monte Carlo work and does
not stop separately authorized work. Use Yukang Zeng <ykzeng2019@gmail.com> as author and committer, direct main.

**FULL-project readiness: 55%, change 0 percentage points, judgment range 45–65%.** The stable weights and
category stages remain unchanged. Exact design validation advanced; no new real-agent evidence, manuscript
pages, interval validation or submission was produced. Top milestones: useful validated inference/adequate
comparisons; remaining statistical validation and final empirical synthesis; independent reproducibility,
author metadata and the final submission package.
