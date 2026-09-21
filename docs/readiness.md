# Full-project submission-readiness estimate

The author requested an overall percentage after every completed project update, including the scheduled 90-minute GitHub reviews. The target is the complete, evidence-backed paper and reproducible package ready for an arXiv/preprint submission, with the empirical scope intended for this project. A finished theory draft alone does not complete that target. Readiness is separate from actually submitting or being accepted.

## Stable rubric, version 1

This is a planning judgment, not a measurement of elapsed work, time remaining, GPU execution, or acceptance probability. Use the same weights and core scope over time. Score each category at the coarse anchors 0, 25, 50, 75, or 100 based on inspectable evidence. Intermediate work does not require an immediate score increase. Report the weighted overall estimate rounded to the nearest five percentage points; show a plausible judgment range when evidence remains unvalidated. The range is not a statistical confidence interval.

| Category | Weight | What completion requires |
|---|---:|---|
| Theory and scientific contribution | 25% | Claims and estimands scoped; literature positioning checked; all claimed results proved under explicit assumptions; substantive review findings resolved; no unsupported novelty or applicability claims. |
| Manuscript development | 20% | Introduction, methods, proofs, empirical results, discussion, references, tables and figures integrated and mutually consistent; full PDF reviewed. |
| Core simulations and real-agent evidence | 30% | The core studies needed for the final claims completed, including known-truth operating characteristics and fresh-policy validation; relevant comparisons and limitations reported. Null and unfavorable findings count as completed evidence. |
| Independent validation and reproducibility | 15% | Critical analysis and inference independently checked; frozen inputs, versions, raw records, task splits, actual assignment probabilities and failure handling audited; core results reproducible from the package. |
| Final submission package | 10% | Author-approved title, author list/affiliations and metadata; final source/PDF and supplement/archive prepared; permissions and attribution resolved; applicable submission requirements checked. |

The generic anchors mean: **0** not established; **25** initial artifacts/design or pilot available; **50** substantial partial delivery with important checks/components outstanding; **75** most of the category delivered, with identified final integration/review work remaining; **100** its stated acceptance conditions met. Category rationales must explain the evidence rather than rely on the labels alone. Avoid counting an experiment's runtime fraction as its scientific completion fraction.

## Baseline: 19 September 2026

Evidence checkpoint: experiment state at `bd1e3b39ec0b2fe9db512c38da1d36aa7cd013d2`, theory manuscript at `9ce18ecf65860c9c07fe70cc308b6e523f2d2e1d`.

**Overall readiness: approximately 50%, with a judgment range of 45–60%.** This is the first readiness baseline, so change from the previous percentage is **not applicable**. It is not a forecast that half the calendar time or compute remains.

| Category | Current stage | Evidence and principal gap |
|---|---:|---|
| Theory and scientific contribution | 75% | The 25-page draft contains 12 formal results with proofs and internal review. Final scientific positioning, practical scope, and alignment with the eventual empirical claims still need review. |
| Manuscript development | 75% | Full theory-first narrative, bibliography, proofs, discussion, and prospective empirical methods exist; empirical results, figures, and their final interpretation are not integrated. |
| Core simulations and real-agent evidence | 25% | Synthetic outputs and exploratory pilots exist. A frozen coding-study design and pilot artifacts are now committed. The workstream reports randomized logging in progress; completed confirmatory live-policy and branch-validation results have not been verified for this paper. |
| Independent validation and reproducibility | 50% | Exact mathematical checks, the root test-suite record, a prior synthetic rerun, source/PDF hashes and archived manifests exist. New experiment code/results, failure handling, protocol adherence and final analysis still require independent audit. |
| Final submission package | 25% | Editable LaTeX and a compiled PDF are available. Final authorship, metadata, result-integrated source/supplement, and submission checks remain. |

The weighted score is 51.25 percentage points before coarse rounding: 0.25×75 + 0.20×75 + 0.30×25 + 0.15×50 + 0.10×25. This arithmetic makes the judgment reproducible; it does not make the underlying assessment precise.

A separate read-only review checked the committed pilot artifact counts (120 episodes from 30 tasks), the pairwise-disjoint 30/231/330 task partitions, and the frozen design/visible-test hashes. It also checked the paper/source hashes against the paper validation record. These are independent artifact-consistency checks; they do not rerun the model outcomes or validate completed confirmatory conclusions.

**Largest remaining milestones:**

1. Complete and independently validate the core real-agent and statistical studies, including fresh-policy comparisons and the chosen branch estimands. Resolve protocol deviations transparently and retain failures and costs.
2. Integrate validated results, figures, limitations and claim revisions into the manuscript, and reconcile all theory-to-implementation assumptions.
3. Finish the reproducibility and submission package, including author-approved metadata and final source/PDF review.

No new GPU/model workload is started by establishing this score. Separately authorized experiment work can continue; this monitoring task queues new requests rather than launching runs.

## Checkpoint: 19 September 2026, 22:00 UTC review cycle

Reviewed experiment artifacts at `035d245` and progress note `f3aa436`: the completed randomized log now has 4,488 episodes / 561 tasks and a frozen learned policy. Independent artifact checks passed, and a separate reviewer reconstructed its 17 fitted-policy entries from TRAIN records. The workstream reports live collection running, but no live-policy or branch results are committed. Source review found certificate-applicability, cohort-completeness, restoration and shared-prefix inference gates. See [the full feedback and evidence boundaries](theory_feedback_20260919.md).

**Overall readiness remains about 50% (change: 0 percentage points from the last issue #4 checkpoint; judgment range 45–60%).** Category stages remain 75/75/25/50/25 under the unchanged weights. This is 10 points below the experiment workstream's provisional 60% assessment in `f3aa436`: completed logging advances the work, but the primary empirical comparisons and validated analyses remain absent and material analysis gates are open. This review does not change weights or core scope. The three largest milestones remain validated empirical studies, result integration and scientific consistency, and the reproducible submission package with author-approved metadata.

## Checkpoint: 20 September 2026, 02:44 UTC review cycle

Reviewed new experiment commit `ac3ca83`. All 3,960 planned live-policy episodes and their 5,504 decisions are now published; independent checks reconcile exact frozen identities, assignments and provenance. Independent numerical reconstruction reproduces the saved task-paired calibration summaries and the secondary learned-versus-large contrast. The branch plan reconstructs, but only 135/800 completed continuations are published. See [the current review](theory_feedback_20260920.md) for evidence boundaries and required reporting/inference corrections.

**Overall readiness: about 60% (change: +10 percentage points from the prior issue #4 checkpoint; judgment range 50–65%).** The empirical category advances from 25 to 50 because completed fresh-policy comparisons and reproducible numerical summaries now join the randomized log and prior simulations. Null or inconclusive results count as completed evidence; the score does not depend on demonstrating a routing advantage. Category stages are now **75/75/50/50/25**, giving a weighted score of **58.75** before rounding. Weights and intended scope are unchanged.

This is partial delivery, not final empirical validation. The finite-certificate applicability issue, general cohort guards, branch-restoration enforcement/shared-prefix inference, figure/claim corrections, additional required comparisons and independent execution checks remain open. The PDF still lacks integrated results. Top remaining milestones: (1) resolve those empirical and analysis gates, including the complete branch study; (2) integrate reviewed results, figures and appropriately scoped claims into the manuscript; (3) finish reproducibility, author-approved metadata and the final submission package.

## Checkpoint: 20 September 2026, 04:24 UTC review cycle

Reviewed `d4997c6`, including the completed branch cohort, documented recovery invocation and experiment-agent reply. All 800 retained branch episodes reconcile to the frozen plan; independent algebraic reconstruction confirms that the new 42-task comparison changes the target and does not close joint inference for the original prefix-weighted contrast. Several reporting repairs are accepted, and the theory review adds a tested ratio-derivative identity as a starting point for a valid repair. It does not supply a new interval theorem. See [the review](theory_feedback_20260920_branch.md).

**Overall readiness remains about 60% (change: 0 percentage points; judgment range 50–65%).** Stages remain **75/75/50/50/25**, weighted **58.75** before rounding. This is five points below the workstream's provisional 65% assessment: completed retained records advance the work, but the planned full-prefix inference, recovery/total-cost accounting, required comparators and manuscript integration are still unfinished. Weights and intended scope remain unchanged. Top milestones: valid joint branch inference and provenance checks; corrected comparisons/figures integrated into the paper; reproducibility, author metadata and final submission packaging.

## Checkpoint: 20 September 2026, 06:04 UTC review cycle

Reviewed `29ee443`. Target preservation and several reporting repairs are accepted. Independent reconstruction
reproduces the pooled difference and the new derivative scale, without validating its interval. A separately reviewed
[conditional sampling proof](theory_branch_sampling.md) and four exact enumeration checks advance the theory.
Independent publication-gate fixtures expose 14 defective cases still accepted; all 19 non-analysis code-study
artifacts are unchanged. The root suite and nine gate fixtures pass 36 tests. See the [response](theory_feedback_20260920_sampling.md).

**Overall readiness remains about 60% (change: 0 percentage points; judgment range 50–65%).** The same category
stages **75/75/50/50/25** give **58.75** before rounding. These accepted repairs and the conditional proof are
progress within existing milestones; full joint inference, comparators and paper integration remain incomplete.
The experiment workstream now also adopts 60%, reconciling its previous provisional estimate. The three largest
milestones remain validated inference/comparators, consistent manuscript integration, and a reproducible submission
package with author-approved metadata. Weights, scope and the compiled manuscript are unchanged.

## Checkpoint: 20 September 2026, 07:50 UTC review cycle

Reviewed `6f92026` and its committed reply. Independent checks accept 12 of the prior 14 publication-check fixes;
remaining reference-data, identity/linkage and recovery fixtures are documented in the [response](theory_feedback_20260920_integration.md).
All 19 non-analysis code-study artifacts are unchanged. Reporting is narrower but still contains contradictory older
sentences, for which exact replacements are supplied. The reviewed sampling result is now integrated into the
**27-page theory manuscript as Proposition 11**; independent proof preservation, visual QA and the selected 49 tests
pass. Empirical results remain outside the paper.

**Overall readiness remains about 60% (change: 0 percentage points; judgment range 50–65%).** Stages remain
**75/75/50/50/25**, weighted **58.75** before rounding. Manuscript integration and verified repairs are progress
within existing categories, without closing the joint-inference/comparator, complete-result integration or final
reproducibility/metadata gates. Those remain the three largest milestones. Weights and scope are unchanged.

## Checkpoint: 20 September 2026, 09:32 UTC review cycle

Reviewed `560135e`. The post-hoc replay comparison is independently reconstructed from pinned records (119 checks,
zero failures); DR figures are cross-checked against saved outputs, not independently refitted. All 19 non-analysis
code-study artifacts remain unchanged. The [review](theory_feedback_20260920_replay.md) corrects mixed comparison
cohorts, concealed later fallback and unsupported null/causal-explanation wording. A separately reviewed exact
adaptive replay counterexample and constant-action positive control add three passing checks (30 root tests total).
The compiled theory paper remains unchanged; the new note and empirical results are not integrated there.

**Overall readiness remains about 60% (change: 0 percentage points; judgment range 50–65%).** Stages remain
**75/75/50/50/25**, weighted **58.75** before rounding, with unchanged weights and scope. These are substantive
within-milestone advances, but valid joint inference and comparator validation, complete manuscript integration,
and final reproducibility/metadata/packaging remain the three largest gaps. Readiness does not depend on obtaining
an unfavorable replay result or a favorable result for the proposed estimator.

## Checkpoint: 20 September 2026, 11:15 UTC review cycle

Reviewed `8ab7fb5` and accepted its corrected post-hoc A5 reporting. The replay mechanism controls were checked,
and the separate audit connects production replay to exact known-value examples. The reviewed replay note is now
integrated into Section 8.2 of the 28-page paper, with proof review, clean compilation and full visual QA. These are
reporting, validation and theory-paper advances; no new model observations or empirical results were added.

**Overall readiness remains about 60% (change: 0 percentage points; judgment range 50–65%).** Category stages
remain **75/75/50/50/25**, weighted **58.75** before rounding under the same weights and scope. The three largest
remaining milestones are validated joint inference and remaining comparators, complete manuscript/result
integration, and independent reproducibility plus author metadata and final packaging. Progress within a milestone
is real even when it does not move the coarse score.

## Checkpoint: 20 September 2026, 12:55 UTC review cycle

Reviewed `bd1ace8`. Four gate bypasses are repaired and valid historical recovery is accepted. The actual new ledger
reconciles five historical rows; all 19 prior non-analysis artifacts remain unchanged. Remaining checker cases are
recorded in the [response](theory_feedback_20260920_recovery.md). A separately reviewed quadratic-moment identity
and four exact tests advance the branch/log variance derivation without asserting valid interval coverage. The
selected suite passes 64 tests; no new empirical observations or paper-PDF changes were made.

**Overall readiness remains about 60% (change: 0 percentage points; judgment range 50–65%).** Weights and category
stages remain unchanged at **75/75/50/50/25**, weighted **58.75** before rounding. These are advances within current
milestones. The largest gaps remain valid joint inference/comparators, complete manuscript/result integration, and
final independent reproducibility, metadata and submission packaging.

## Checkpoint: 20 September 2026, 16:08 UTC review cycle

Reviewed `97689b9`: five of six earlier publication-check failures are repaired, while report binding and two
invocation/source checks remain open. Independent stored-record reconstruction verifies all 800 branch/parent/durable
hash links; full transcript-byte reconstruction remains unreplicated locally because the frozen task input is
missing. All 20 non-analysis artifacts are unchanged. See the [response](theory_feedback_20260920_restoration.md).
The reviewed quadratic identity is integrated into Section 9.4, Proposition 12 of the **29-page paper**; independent
proof and visual review and **71 selected tests** pass. No new empirical observations or validated intervals are added.

**Overall readiness remains about 60% (change: 0 percentage points; judgment range 50–65%).** The unchanged stages
**75/75/50/50/25** and weights give **58.75** before rounding. Paper integration and independently confirmed repairs
advance the work within current categories. The three largest remaining milestones are valid joint inference and
required comparators; complete manuscript/result integration; and independent reproducibility, author metadata
and the final submission package. Weights and scope are unchanged.

## Checkpoint: 20 September 2026, 17:51 UTC review cycle

Reviewed `3f9000a`: all three previously documented publication-check failures are repaired, and all 39 bounded
case expectations are met. The restoration report's hashes/IDs and actual stored hash links independently reconcile;
all 20 non-analysis artifacts remain unchanged. Full transcript reconstruction remains unreplicated locally because
the frozen task input is missing. The separately reviewed [source-model note](theory_branch_source_model.md) adds an
explicit sufficient iid task-population variance link and fixed-benchmark counterexample. It does not establish
sampled-variance consistency or joint coverage; the 29-page PDF is unchanged. The selected suite passes 79 tests.
See the [response](theory_feedback_20260920_source_model.md).

**Overall readiness remains about 60% (change: 0 percentage points; judgment range 50–65%).** Stages remain
**75/75/50/50/25**, weighted **58.75** before rounding, with unchanged weights and intended empirical scope.
The verified repairs and scoped proof advance existing milestones; the three largest gaps remain valid joint
inference/comparators, complete manuscript/result integration, and independent reproducibility/metadata/final packaging.

## Checkpoint: 20 September 2026, 19:34 UTC review cycle

Reviewed `13bad73`. Independent public-source regeneration reproduces all 591 frozen task records, and full
transcript-byte reconstruction matches all 800 parent/branch/durable hashes. The previous input blocker is resolved;
all 20 non-analysis artifacts are unchanged. All 40 bounded gate cases and 80 selected tests pass. The reviewed
source-model result is integrated into Section 9.5, Proposition 13 of the **31-page paper**, with proof-preservation
and all-page visual review. See the [response](theory_feedback_20260920_reconstruction.md).

**Overall readiness remains about 60% (change: 0 percentage points; judgment range 50–65%).** Stages remain
**75/75/50/50/25**, weighted **58.75** before rounding under unchanged weights and scope. These are substantive
within-category advances, but independent validation still lacks final inferential/analysis reproduction and the
complete package. The three largest gaps remain valid joint inference/comparators, complete manuscript/result
integration, and final independent reproduction, metadata and packaging. Successful transcript reconstruction
alone does not validate runtime restoration, empirical interval coverage or overall submission readiness.

## Required reporting format

Every scheduled GitHub update and user-facing project completion message must include:

> Overall submission readiness: about X% (change: +/−Y percentage points; or initial baseline). Evidence advanced: [completed, inspected milestone]. Main remaining work: [up to three concrete gaps].

Add a judgment range when material uncertainty remains. A no-change update retains the percentage and reports zero change. Scores may decrease when errors or unmet assumptions are found. Identify whether new evidence was reported, inspected, independently validated, or integrated; a commit claiming that a job started does not prove successful completion.

Record new checkpoint scores and the reasons in [GitHub issue #4](https://github.com/ykzeng-yale/DTR-AgentEvals/issues/4). Keep this baseline as a historical entry; append a clearly dated checkpoint here when the rubric, core scope, or a major completion milestone changes. Do not silently change the weights to manufacture progress.

**The 100% gate:** every mandatory category must be complete, with no unresolved material proof, data/analysis, manuscript consistency, reproducibility, authorship, or packaging issue. Rounding must never turn an incomplete project into 100%. Cap the displayed score below 100% while any mandatory gate is open. Actual uploading/submission requires separate author authorization and is not implied by this reporting request.

## Checkpoint: 20 September 2026, author-requested scientific diagnosis

At `338425b`, three deterministic diagnostics were independently reconstructed: the learned policy deploys a
fixed large/small/large schedule, visible-pass stopping and zero-check tasks limit repair opportunities, and the
class-tailored calibration discrepancy persists under IPW without an inspected assignment/calculation mismatch.
The [scientific lead's report](scientific_diagnosis_20260920.md) narrows the empirical claims, retains the original
metric and fixed-benchmark target, and takes responsibility for the design and next discriminating checks.
The 90-minute monitor now explicitly requires this scientific judgment. No new observations were collected;
the 31-page PDF and experiment archives remain unchanged.

Concurrent experiment commit `4f9abe4` added a null diagnosis during this review. Its arithmetic reproduces,
but two independent reviews reject its purported oracle bound, no-power inference and theory-vindication claims.
The lead corrected the current narratives and retained the historical output, with concrete generator/reporting
repairs requested. This prevents those unsupported conclusions from advancing the empirical category.

**Overall readiness is now about 55% (change: −5 percentage points; judgment range 45–65%).** Weights and intended
scope are unchanged. Independent validation/reproducibility is conservatively reduced from 50 to 25; category
stages **75/75/50/25/25** give **55.00** before rounding. The later `8382b3c` report discloses a provenance-writing
defect and a reporting repair that had been claimed but not fully applied. Together with A6's unsupported bound
and inference claims, these expose an insufficiently validated interpretation/reporting layer. Existing independent
reconstructions remain completed evidence. The reduction is not because of unfavorable outcomes, and does not
adopt the unreconciled count of 116 audit items as a measure of readiness. The workstream's category arithmetic
was 55.00, not its stated 54.25; both round to the same 55%.

The latest source fixes and unchanged-byte figure rename are integrated and inspected; the claimed 101 tests
and 116-item inventory remain workstream-reported in this turn. Largest remaining milestones: valid inference
and scientifically adequate comparisons; full empirical manuscript integration; independent final reproduction,
author-approved metadata and submission packaging. Submission remains unperformed.


## Checkpoint: 20 September 2026, 21:54 UTC review cycle

Reviewed `aac69b5` since `7085c77`. Independent reconstruction accepts several retractions and both penalty
conventions, but rejects the remaining partition ceiling, wrong-comparator SE and selected-cohort stage inference.
The original archive is preserved. The 35-page paper now integrates a reviewed critical coding case study with
all six policy comparisons and explicit evidence boundaries; this closes the absence of a descriptive empirical
section but not the final empirical-validation/synthesis milestone. The separately reviewed fixed-benchmark
concentration note provides a sufficient construction under explicit unverified assumptions, currently yielding
the entire [−2, 2] range. It supplies no useful empirical precision. See the [review](theory_feedback_20260920_case_study.md).

**Readiness remains about 55% (change: 0 percentage points; judgment range 45–65%).** Category stages remain
**75/75/50/25/25**, weighted **55.00** under unchanged weights and intended scope. Actual progress is paper
integration, corrected interpretation and an explicit sufficient inferential construction, without new outcomes
or validated intervals. Top three remaining milestones: useful validated inference and adequate comparisons;
remaining statistical validation and final empirical synthesis; independent final reproducibility, author-approved
metadata and submission packaging. New GPU/model and Monte Carlo requests remain deferred. Nothing submitted.

## Checkpoint: 21 September 2026, literature-informed design review

Reviewed new work at `981f7b9872164697ab79e413a50257c011f11e6f`. The [source review](literature_design_review_20260921.md)
and [v2 protocol](experiment_protocol_v2.md) separate evaluation calibration from history-dependent improvement,
select concrete open-source harness/baseline components, and specify task, failure, support and precision gates.
Independent reviews identified and resolved outcome/eligibility/variance wording issues. The [branch audit](theory_feedback_20260921_conditional_frame.md)
reconstructs the new conditional calculation, corrects its component interpretation and retains it as secondary;
it does not replace the primary fixed-benchmark target or validate a confidence interval.

**Overall 55%, change 0 percentage points, judgment range 45–65%.** Unchanged weights 25/20/30/15/10 and stages
75/75/50/25/25 give **55.00**. The improved design and deterministic diagnosis advance work within existing stages;
no new observations or simulation validation were produced. The 35-page PDF remains unchanged. Remaining milestones:
(1) useful validated inference and adequate comparisons; (2) remaining statistical validation and final empirical
synthesis; (3) independent reproducibility, author metadata and submission packaging. Nothing submitted.
