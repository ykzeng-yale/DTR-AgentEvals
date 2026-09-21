# Lead acceptance of the structural branch control

**21 September 2026, 07:49 UTC cycle.** Reviewed worker
`9202019f9cb790d4c0c79e7c792854e1c04087bf`. **DTR-REQ-003 verdict: accept the structural branch specification
and exact means; correct probability/restoration labels and proceed to the queued shared-log covariance work.**
Keep the current initial-action kernel. It is a structural development control, not a validated reproduction
of the archive's execution or prefix-occupancy law.

## Independent validation and boundaries

Twelve affected tests pass locally. The separate [audit script](../scripts/audit_branch_module_9202019.py)
imports no worker code and reconstructs the two-repair success probabilities in closed form. All **16 rows
and 80 exact target comparisons** agree, including the calibrated population Delta=0, drifted-law differences,
arm log ratios and expected prefix counts. The [audit record](audits/branch_module_audit_9202019.json) pins the
inputs and independently checks arm-denominator and small-frame probabilities. Separate internal mathematical
review accepts the target alignment and frame rule. The reported broader 156-test suite was not rerun.

The initial 4/4 assignment sets the source-prefix distribution; the continuation target requires no extra
initial-action intervention weight. Ratios of expected totals retain every fixed task, including zero-prefix
tasks. Calibrated restored and source continuation laws give E[W_a | full prefix]=1 and matching conditional
success means, hence Delta=0. This is a population calibration identity, not zero realized-frame discrepancy
or unbiasedness of finite-sample ratio estimates. Drift is a designed alternative with a nonzero mean gap;
it does not establish that the eventual test detects it.

The model restores the latent error state U. Label it an **ideal full-state restoration control**. Conditional
fresh-execution independence must condition on the complete simulator state, including U; merely conditioning
on recorded feedback can leave shared latent-state dependence. For the proposed implementation, use independent
source and fresh continuation noise and independent branch arm draws conditional on that full state, with
independent draws across prefixes and replicate indices. This is a simulator design choice, not evidence that
historical recovery runs or transcript-only restoration satisfy it. Two replicate pairs and the existing
frame rules remain unchanged. No sampling/execution pipeline or coverage study has yet been delivered here.

Feedback-quality invariance of these stay-policy means is expected: the stay policies ignore exception versus
assertion feedback, and the total non-pass probability is fixed. It does not show that feedback is useless
for adaptive routing in the earlier model.

## Probability-reporting correction

The saved arithmetic for means is accepted; probability names/precision claims need correction in the next
version or accompanying report, preserving v1:

- P(N=0) can be represented exactly as a product of rational powers. Its reported logarithm is a floating-point
  approximation, not an exact number. The -546.4767 log10 value applies to n=250; n=1000 gives -2185.9069.
- At n=1000, saved P(N<=200)=0.0 is numerical underflow/pruning, not impossibility. An independent truncated
  polynomial convolution at 90-decimal-digit precision gives log10 P(N<=200) approximately **-1786.226251**,
  or **5.94e-1787**. At n=250 it gives approximately **2.30344e-272**, agreeing with the saved nonzero value.
  These are deterministic high-precision approximations, not exact probabilities or simulation results.
- P(N<=200) is the probability of a small source frame, **not** the probability the census rule is used.
  The whole-range fallback takes precedence at N=0 or either zero arm denominator. Use the appropriate
  label; do not change the frame rule or silently treat a numerical zero as a structural zero.

The six deterministic cases validate the decision rule, not an interval implementation or coverage. Retain
empty-frame and zero-denominator fallback even where their probability is tiny under this particular model.

## Decision on archive-like occupancy

**Do not retune the accepted baseline.** Its expected 895 prefixes from 2,000 source episodes is sufficient
for structural checks. It does not reproduce the archived 564 prefixes from 2,640 episodes, and its n=250/1000
fixed lists differ from the archived 330 tasks. Structural matching alone will not support archive-facing
precision/coverage claims.

Before such claims, include **one separately labeled expected-occupancy sensitivity**, outside the 32-cell
core: n=330, the same balanced synthetic strata and 4/4 source allocation, and

    alpha = (564/(8*330)) / (895/(8*250)) = 940/1969,
    P0A_new[S,A] = 1 - alpha*(1-P0A_baseline[S,A]).

The resulting easy small/large probabilities are 1593/1969 and 1687/1969; hard probabilities are 1217/1969
and 1358/1969. Every expected prefix, branch-effect total and arm-weighted total scales by alpha relative
to the same n baseline, preserving theta, nu_small, nu_large and Delta while E[N]=564 exactly. This invariance
has been independently reviewed. The audit checks the expected count and lists the parameters; worker
acceptance must additionally verify the scaled task totals and unchanged ratios in a separate artifact.

This uses the archived *count* as a retrospective design diagnostic, not CONFIRM outcomes for policy/metric
tuning. It matches expected occupancy to one observed count; it does not match task heterogeneity, dependence,
the distribution of N, or E[min(200,N)/N]. In particular, 200/E[N] is not the expected realized sampling fraction.
No claim of empirical calibration follows, and no new Monte Carlo is requested. Keep this queued after the
already promised covariance calculation rather than delaying it with another grid expansion.

## Next steps, same request IDs

**Late-arriving covariance delivery `b4b074d` is acknowledged.** Its source and committed reply were inspected
during this run; the worker reports exact shared-log checks, negative as well as positive frozen-rule contrasts,
and seven tests. These numerical results/tests have not been independently reproduced by this review. Do not
duplicate or re-deliver that work: its independent moment audit is the lead's next review item. The explicit
distinction between a fixed catalog history rule and the unattainable known-kernel optimum is appropriate;
retain the unfavorable contrasts. The simple sum of two marginal IPW variances is a hypothetical independent
IPW-score comparator, not yet the variance of a fresh on-policy reference. REQ-003 remains running. The
worker can proceed to the one separately labeled occupancy sensitivity while the lead checks the delivered
covariances. This supersedes the future-delivery wording below where the artifact has now arrived.

**DTR-REQ-003, P1, running:** next deliver the already queued exact shared-log covariance/contrast calculations
for history versus prompt-only and best fixed. Require agreement with direct score-difference moments,
zero identical-policy variance and a positive semidefinite covariance matrix. Include independent-reference
variance separately where used; marginal policy standard errors do not close this gate. Then supply the one
occupancy sensitivity above and a consolidated list of unresolved estimator/coverage/sampler assumptions.
Correct the probability and full-state-restoration wording in the next committed reply; do not regenerate
accepted means or overwrite archived outputs. Acknowledge these existing-ID decisions and statuses.

**DTR-REQ-002 qualification remains queued; DTR-REQ-001 completed.** No model/verifier/Monte Carlo or duplicate
workload started by this review; separately authorized jobs are not interrupted. Direct main commits remain
Yukang Zeng <ykzeng2019@gmail.com> as author and committer.

**FULL-project readiness: 55%, change 0 percentage points, judgment range 45–65%.** Weights/stages unchanged.
Structural mean checks advanced, but no empirical outcomes, useful validated interval, manuscript pages or
submission were added. Top milestones: useful validated inference/adequate comparisons; statistical validation
and final empirical synthesis; independent reproducibility, author metadata and submission package.
