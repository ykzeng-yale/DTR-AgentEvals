# Accepted artifacts and open gates, 21 September 2026 (worker, DTR-REQ-003 handoff)

Compiled at worker commit after `13c1b91`. Commit references come from `git log` on each file. "Independent audit" means the lead's no-worker-import reconstruction in `docs/audits/`.

**Ownership:** the worker implements, executes and reports; the lead owns target, design, metric, comparator, inference and interpretation decisions; the user owns host software installation and any compute purchase.

## Accepted artifacts

| Req | Artifact | Path | Worker commit | Lead review (commit) | Independent audit | Status and boundary |
|---|---|---|---|---|---|---|
| 001 | Corrected A6 report | `results/code_routing/analysis/a6_report.{json,md}`, `experiments/tools/a6_report.py` | `4024a23` (labels repaired by lead in `8ecdfde`) | `theory_feedback_20260921_a6_report.md` (`8ecdfde`) | `why_null_audit_4f9abe4.json`, `why_null_audit_aac69b5.json` (pinned inputs) | **Completed.** Reproduction of archived numbers only; no interval, power or oracle claim |
| 001 | Branch evidence table | `results/code_routing/analysis/branch_evidence_table.json` | `993f881`, `1d5cdb6` | `theory_feedback_20260921_weighting.md` (`a62ccf2`); accepted `ac1d89e` | `branch_evidence_audit_993f881.json` | **Completed.** Descriptive; execution assumptions labelled, not validated |
| 002 | Adapter contract and fixture plan | `docs/adapter_contract_20260921.md`, `experiments/v2_adapter/fixtures_planned.json` (35) | `6982f5d`, `81128ee` | `theory_feedback_20260921_adapter.md` (`8ecdfde`) | source lines re-read by lead | **Accepted as design.** Fixtures are PLANNED, not implemented or executed |
| 002 | Evaluator selection | `docs/evaluator_compatibility_20260921.md`, `configs/v2_evaluator_selection_20260921.json` | `81128ee` | `theory_feedback_20260921_evaluator_selection.md` (`91c8bcc`) | `evaluator_selection_audit_81128ee.json` | **Selected** (`f7bbbb2`) for development qualification only; pins unchanged; no runtime acceptance |
| 003 | Exact one-decision control | `experiments/v2_sim/exact_control_truth.json` | `72edb47` | `theory_feedback_20260921_exact_control.md` (`54e1621`) | `exact_control_audit_72edb47.json` | **Accepted.** Analytic diagnostic |
| 003 | Supplemental cost-dominated cell | `experiments/v2_sim/exact_control_supplemental_v1.json` | `9a1412a` | `theory_feedback_20260921_supplement.md` (`4f76701`) | `exact_supplement_audit_9a1412a.json` | **Accepted.** No further control cells requested |
| 003 | Repair kernel tables (fixed artifact) | `experiments/v2_sim/repair_generator_v1.json` | `da34fd9` | `theory_feedback_20260921_repair_generator.md` (`935fabd`) | `repair_generator_audit_da34fd9.json` | **Accepted.** 8 core + 4 auxiliary cells; the DP optimum is a known-kernel oracle, not a learner |
| 003 | Logger layer | `repair_logger_v2.json` (v1 `6b2cb71` preserved, defective cost labels) | `facd4a8` | `theory_feedback_20260921_logger_repair.md` (`c847751`) | `repair_logger_audit_facd4a8.json`, `repair_logger_support_audit_6b2cb71.json` | **v2 accepted.** Support labels are per component |
| 003 | Fixed-task blocks | `experiments/v2_sim/fixed_task_blocks_v1.json` | `655663a` | `theory_feedback_20260921_fixed_tasks.md` (`dd898b5`) | `fixed_task_blocks_audit_655663a.json` | **Accepted** (r=4, homogeneous strata). Marginal moments only |
| 003 | Archive branch module | `experiments/v2_sim/branch_module_v1.json` | `9202019` | `theory_feedback_20260921_branch_design.md` (`7e04762`) | `branch_module_audit_9202019.json` | **Accepted** (structural; baseline P0A). Ideal full-state restoration |
| 003 | Shared-log contrast covariances | `experiments/v2_sim/contrast_covariance_v1.json` | `b4b074d` | `theory_feedback_20260921_covariance.md` (`9d31341`) | `contrast_covariance_audit_b4b074d.json` | **Accepted.** Ratio range 0.704513–1.005759 (7 rows > 1); not a fresh-reference or two-log design |
| 003 | n=330 occupancy sensitivity | `experiments/v2_sim/branch_occupancy_sensitivity_v1.json` | `c25bee0` | `theory_feedback_20260921_occupancy.md` (`13c1b91`) | `occupancy_audit_c25bee0.json` | **Accepted.** Log values are serialized floats from 60-digit intermediates |

## Open gates (explicitly undelivered)

| Req | Gate | Owner | Acceptance / dependency | State |
|---|---|---|---|---|
| 003 | Full sampler generating complete repetitions from the accepted kernels, blocks and branch module | worker implements; lead authorizes any Monte Carlo | Sample moments consistent with the exact moments above within Monte Carlo error; **no Monte Carlo is authorized** | OPEN |
| 003 | DR, outcome-regression and failure controls (coarsened outcome fits, misspecified propensities; protocol section 2) | worker implements; lead sets the method list | Known-truth comparison on the accepted kernels | OPEN |
| 003 | Interval coverage (protocol plans 2,000 complete repetitions) | lead decides; worker executes if authorized | Needs the sampler and Monte Carlo authorization | OPEN |
| 003 | Independent fresh on-policy reference uncertainty, and a resource-matched two-log design | worker computes; lead specifies the design | Per-policy on-policy variance under separate fresh blocks; the shared-log covariance above does **not** cover this | OPEN |
| 003 | Belief-dependent oracle in catalog-level checks | worker | Currently only via DP value; not in the logger, block or covariance catalogs | OPEN (noted by lead) |
| 003 | Stress cells beyond delivered controls (severe overlap, hidden confounding, non-Markov coarsening, execution drift beyond the restoration control) | lead | The lead has asked for no more peripheral controls now | DEFERRED |
| 003 | Precision/resource choices: margins, target precision, real-study n and r | lead | Protocol section 5 precision gate | OPEN |
| 002 | M01–M03 qualification fixtures: all 500 rows' metadata/script construction with pinned external inputs; missing/malformed test lists; grading equivalence and a new-file-only regression case | worker | Specified in the fixture plan; **next worker priority** | OPEN (not implemented) |
| 002 | Runtime host: container runtime and an x86_64 execution host | **user** (installation/compute), lead (plan) | This host is arm64 with no container runtime; no installation will be performed by the worker | BLOCKED |
| 002 | Image digests and dependency locks; no-change and reference-patch execution controls; wall-time, evaluator-time and resource limits | worker executes after host exists; lead sets limits | Protocol section 5 infrastructure gate | OPEN |
| 002 | RouteLLM threshold calibration on a versioned development split | lead (split), worker (calibration) | Must precede CONFIRM | OPEN |
| 001 | Fixed-benchmark interval for the primary branch target θ | lead (theory) | Not a worker deliverable; primary B2 coverage remains open | OPEN (scientific) |
