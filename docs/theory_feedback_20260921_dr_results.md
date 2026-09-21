# Lead scientific review of paired DR/OR results — 21 September 2026

Reviewed `8a34f6f` results and `fa4bac2` diagnostic helper. REQ-003 P0: **accept the scoped development
summary and proceed with the proposed retrospective stage-2 intervention**, under the limits below.

## Observed evidence

The independent `scripts/audit_dr_batch_8a34f6f.py` verifies frozen hashes, 800 distinct paired repetitions,
2,400 original IPW estimates and all reported estimator/paired summary statistics: 2,688 numerical checks.
Two supplied diagnostic-helper tests pass. This is independent arithmetic on saved estimates, not independent
regeneration of trajectories or interval-coverage validation. Earlier bridge controls remain relevant;
the new first-40-repetition mechanistic decomposition is worker-reported and has not been independently rerun.

Fitted task-split DR has observed RMSE 0.7424–0.9341 times trajectory IPW across the 12 rows, a 6.6–25.8%
reduction in this development batch. Its largest absolute bias/MCSE is 1.4762. This is encouraging synthetic
evidence for augmentation with observed-history nuisance models, not a general efficiency theorem, proof
of zero bias from nonsignificance, or evidence that adaptive agents outperform fixed agents.

The informative-feedback, feedback-dependent logger produces fitted OR bias +0.00823 for the prompt rule
and +0.00446 for fixed LS (bias/MCSE 4.8869 and 2.8593). Preserve both. Lower OR RMSE does not remove bias;
variance reduction can outweigh squared bias at this sample size. No simultaneous significance claim is
made from scanning these dependent diagnostics.

## Diagnosis and discriminating next step

The primary explanation to test is propagation of fitted second-stage continuation error into the fitted
first-stage regression. Evidence supporting it: known-Q controls and supported-weight estimators calibrate,
while iterated fitted OR departs; the worker's first-stage decomposition locates error outside direct
first-stage fallback cells. Evidence against the narrower claim that *fallback frequency alone* causes it:
weak-feedback cells also use fallback frequently without the same observed bias. Other second-stage fitting
error, history-specific pooling differences and dependence in iterated training targets remain plausible.
Finite Monte Carlo uncertainty and untested implementation behavior are not eliminated by these controls.
These findings do not identify a failure of causal identification; they concern a particular fitted estimator.

**Answer to the 13:49/14:15 question: proceed now, no further lead approval needed for this check.** On the
external experiment worker only, preserve all existing logs, folds, policies and 800 cell/repetition IDs.
Freeze the diagnostic code/manifest and use the existing helper to replace second-stage Q with the exact
known-kernel table while leaving first-stage fitting unchanged. Existing CPU resources, four workers at most,
900-second wall cap; no new random data, model calls, paid resources, or additional seeds/sample sizes.
Write a new diagnostic artifact without replacing the reported fitted estimator or prior diagnosis.

Acceptance/delivery criteria:

1. Verify original IPW and standard OR reproduce on the regenerated logs (tolerance 1e-12); retain all tasks.
2. For each policy/cell, report original OR error, oracle-stage-2 OR error and their **paired difference with
   MCSE**, plus RMSE. Report all cells, not just those with large original bias. Retain null/adverse results.
3. If the paired intervention reduces bias, conclude that second-stage estimation contributes in this
   implementation. Do **not** conclude that sparse-cell fallback specifically is confirmed: replacing the
   whole stage-2 table changes both fallback and non-fallback estimates. Disappearance of significance alone
   is also insufficient. A fallback-specific intervention would be a separate later diagnostic, if needed.
4. If the error persists, inspect first-stage fitting/history mapping and the worker decomposition before
   increasing compute. Preserve the primary protocol and CONFIRM separation.

This is a retrospective development diagnostic, not a “confirmation” study. The known-Q intervention is
an oracle experiment unavailable in deployment. Acknowledge REQ-003 accepted/running/completed/blocked and
publish the result in the shared results document and handoff. REQ-002 host permissions remain separate.
All new commits use Yukang Zeng <ykzeng2019@gmail.com> as author and committer, direct main, no PR.

Overall readiness **55%, change 0 points, range 45–65%** under unchanged weights and stages. Development
calibration and error reduction advanced; useful interval coverage, adequate empirical comparisons and
paper integration remain open. Top milestones: validated inference/comparisons; statistical validation and
empirical synthesis; independent reproducibility, metadata and submission packaging.
