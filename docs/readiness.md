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

## Required reporting format

Every scheduled GitHub update and user-facing project completion message must include:

> Overall submission readiness: about X% (change: +/−Y percentage points; or initial baseline). Evidence advanced: [completed, inspected milestone]. Main remaining work: [up to three concrete gaps].

Add a judgment range when material uncertainty remains. A no-change update retains the percentage and reports zero change. Scores may decrease when errors or unmet assumptions are found. Identify whether new evidence was reported, inspected, independently validated, or integrated; a commit claiming that a job started does not prove successful completion.

Record new checkpoint scores and the reasons in [GitHub issue #4](https://github.com/ykzeng-yale/DTR-AgentEvals/issues/4). Keep this baseline as a historical entry; append a clearly dated checkpoint here when the rubric, core scope, or a major completion milestone changes. Do not silently change the weights to manufacture progress.

**The 100% gate:** every mandatory category must be complete, with no unresolved material proof, data/analysis, manuscript consistency, reproducibility, authorship, or packaging issue. Rounding must never turn an incomplete project into 100%. Cap the displayed score below 100% while any mandatory gate is open. Actual uploading/submission requires separate author authorization and is not implied by this reporting request.
