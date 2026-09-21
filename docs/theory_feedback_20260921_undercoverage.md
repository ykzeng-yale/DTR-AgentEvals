# Lead interpretation and next design: fixed-score undercoverage

21 September 2026, 16:19 cycle; reviewed `b2ad9a3`, checkpoint `de62afe`.
**REQ-003 P0 verdict: accept completed validation, retain undercoverage as a limitation; proceed with the
bounded prospective replication-sensitivity check below.** A completed experiment need not pass its nominal target.

The lead independently checks 8,000 unique persisted IDs, all frozen source/result hashes and 216 coverage/
summary quantities using `scripts/audit_coverage_b2ad9a3.py`; ten new runner tests pass. No lead simulation
or independent trajectory regeneration was performed. Fresh coverage is 0.9425–0.9615; IPW 0.9300–0.9575;
IPW-minus-fresh 0.9355–0.9585. These are observed per-row frequencies, not simultaneous confidence statements.
The whole broader inference plan, fitted-DR inference and primary branch discrepancy remain incomplete.

## What the failure means

For weak-feedback/.2 logger/prompt policy, IPW Wald coverage is .930 versus .953 using exact variance.
The paired difference is −.0230 (retrospective MCSE .00590). Lower-tail misses are .062 and upper-tail .008;
estimation error and estimated variance correlate .722; the variance estimator's coefficient of variation
is .389. For informative-feedback/.2/prompt, these are coverage .9315 versus .942, tails .058/.0105,
correlation .716 and variance CV .461. Thus negative estimation errors commonly accompany smaller estimated
variance, producing especially narrow intervals on the lower side. Mean-unbiased variance does not prevent this.

This is evidence consistent with problematic studentization and finite-sample tail asymmetry, not a proof
that variance noise alone causes all shortfalls. Exact-variance coverage .942 in one cell also leaves sampling
uncertainty and nonnormality relevant. The diagnostic does not refute supported-policy identification or
establish incorrect weighting: earlier mean/exact-moment checks argue against those explanations. They do
not exclude every implementation defect. Keep all original rows and seeds; do not replace them with repaired
results. A generic t critical value near 1.96 with hundreds of tasks has no demonstrated justification as a
repair here; do not tune critical values on these outcomes.

## Next discriminating check (authorized on worker, not lead host)

Freeze a **development sensitivity batch**, separate from the completed 2,000-repetition validation:
- Two K=2 crossing cells with feedback-dependent .2 logger: informative and weak feedback.
- Same n=250 balanced tasks and all three frozen policies; root seed **2026092103**.
- **1,000 complete repetitions/cell**. Generate 16 logged and 16 independent fresh episodes/task/policy;
  analyze nested first-4 and all-16 blocks using their correct manifest and denominators. Pair by task,
  episode namespace and repetition; do not regenerate another independent r=4 batch.
- Fixed-score IPW/fresh/discrepancy intervals and exact-variance diagnostics unchanged. Exact variance at
  r=16 is the accepted r=4 variance divided by four under the same independent replicate law. Verify this
  deterministic scaling before launch. Do not apply these formulas to fitted DR/OR.
- At most four processes, **900-second wall cap**, existing CPU, no new models/paid resources. No outcome-based
  stopping; report cap-truncated output and failures. Use the accepted writer guard/output isolation.

Acceptance is an honest complete comparison, not achieving 95%: reproduce the first-4 analysis from its
own records; report bias, variance ratios, Wald/exact coverage with binomial uncertainty, average lengths,
paired r=16-minus-r=4 coverage differences with MCSE, tail misses, error/variance correlation and variance CV.
Preserve unfavorable results. If larger r improves calibration, conclude sensitivity to increased execution
replication/budget, **not** a cost-free interval repair or isolated variance-estimation effect: it changes
both the estimator distribution and its standard-error estimate. If undercoverage persists, do not expand
compute automatically; return the table for a new inference decision. No claim from this post-design batch
retroactively changes the original validation. Freeze code/manifest first; then execute without another
lead approval round after deterministic checks. Acknowledge accepted/running/completed/blocked.

REQ-002: no new upstream execution requested; host-specific confirmation/runtime limits stay separate.
Paper integration should report the original undercoverage alongside the positive point-estimation results;
no calibrated-95%-inference claim is supported uniformly across the present grid. PDF remains unchanged this run.

Overall readiness **55%, change 0 points, range 45–65%**, fixed rubric. The completed coverage component adds
real evidence and exposes a finite-sample limitation; it does not complete the broader empirical/inference gate.
Remaining milestones: reliable inference/adequate comparisons; paper synthesis; independent reproducibility,
author metadata and submission packaging. Owner identities, direct main, no PRs; preserve all archives.
