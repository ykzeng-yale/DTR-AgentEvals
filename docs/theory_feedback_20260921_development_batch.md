# Lead review: first end-to-end development batch, 21 September 2026

Reviewed results `35b2f36`, DR/OR bridge `1faebc8`, and prepared runner `71c0b68`.
**REQ-003 P0 verdict: accept the scoped development summary; proceed with the paired DR/OR batch.**
The experiment worker is authorized to freeze, commit/push and execute the prepared batch on its existing
CPU resources under the same 900-second wall cap, four workers, four cells, 200 repetitions/cell and root
seed 2026092101. Do not wait for another lead reply. This does not authorize new model calls, paid resources,
CONFIRM, or duplicate jobs on the theory host. Publish partial or unfavorable outcomes if capped.

## Evidence and scientific judgment

The independent summary script `scripts/audit_dev_batch_35b2f36.py` imports no worker modules and regenerates
no trajectories. It verifies all frozen source hashes, manifest/result hashes, all 800 unique cell/repetition
records, declared episode counts and 120 summary quantities from committed repetition estimates. Eleven
worker bridge/batch tests were rerun and pass. Episode counts are record-level assertions, not an independently
observed execution trace. Runtime (44.3 seconds wall, 169 CPU-seconds) is worker-reported metadata.

Across 12 policy/cell rows, the largest absolute bias/discrepancy divided by its estimated Monte Carlo SE is
1.9389; empirical/exact SD ratios range 0.9065–1.0626. These are descriptive diagnostics of agreement with
previously checked exact tables. They are not proof of unbiasedness, a simultaneous test, interval coverage,
or evidence of real-agent improvement. The theoretical unbiasedness claim depends on the specified supported
logger, target weights and common data-generating law. No new theorem is asserted here.

The exact frozen history-rule utility is 0.738545 under informative feedback versus 0.697456 for fixed LS,
but drops to 0.687508 under weak feedback while fixed LS stays unchanged (rounded values).
Thus the policy's usefulness depends on feedback quality. The weak-feedback loss is retained: calibration
can work while a particular adaptive rule is inferior. It is not explained by Monte Carlo bias in these
records, nor does it refute identification. The frozen rule is not an optimal history learner; broader
history-class benefit and transport to real tasks remain separate questions. Comparisons with a known-kernel
selected fixed schedule must keep that oracle selection label. Do not retune policies on this batch and
call them prospectively validated.

## Next discriminating check: same request, no new prerequisite cycle

The prepared DR/OR runner reuses identical seeded logs and joins the committed independent fresh values.
Freeze the manifest before launch and preserve the first batch. Acceptance for the development delivery:

- All original IPW estimates reproduced within 1e-12; a discrepancy must be investigated before combining results.
- Report every estimator for all four cells and three policies: bias with MCSE, RMSE, empirical SD and paired
  DR-minus-IPW / DR-minus-fresh discrepancy. Retain OR failures or larger DR variance without relabelling them.
- Keep whole-task folds, observed-history features and the common first-call contribution. The source bridge
  includes those distinctions; existing tests cover reward reconstruction, task separation and exact control means.
- Label known-kernel-Q DR as an unfitted positive control. Better oracle performance alone does not establish
  that fitted DR works; fitted OR bias may reflect sparse history support or nuisance fitting rather than
  a failure of identification. Diagnose the resulting pattern before increasing sample size or adding models.
- Fixed 200 repetitions/cell or the cap; no significance-based stopping. This batch does not estimate interval
  coverage. A later frozen inference study is still required.

REQ-002 remains separate: the worker reports outstanding host-specific download/execution permissions and
runtime qualification. Those do not block this CPU batch. Acknowledge REQ-003 as accepted/running/completed/blocked
and link the manifest and table in the committed handoff and shared results document. Use Yukang Zeng
<ykzeng2019@gmail.com> for both author and committer, direct main, no PRs.

FULL-project readiness remains **55%, change 0 points, range 45–65%**, with unchanged milestone weights.
This is real development-validation progress within the current stages, not a completed empirical/inference gate.
Top remaining milestones: useful validated inference and adequate comparisons; statistical validation and final
empirical synthesis; independent reproducibility, metadata and submission packaging.
