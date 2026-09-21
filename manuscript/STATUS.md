**21 September, 22:49 cycle:** fixed-fit development coverage is integrated (worker `66fb04a`): 10,000
experiments over five index-selected fits, all three policies. Lead audit checks 660 saved-result quantities,
19 source hashes and complete IDs; eight tests pass. Scoped evidence only; no uniform or cross-fitted coverage
claim. Readiness remains 55% (0 points; 45–65%).

**21 September, 20:49 cycle:** the empirical section now includes the completed honest-split repeated-training
study (worker `f532597`, 4,000 repetitions). Lead saved-record audit: 636 quantities, 15 source hashes;
18 affected tests pass. DR coverage 0.936–0.955 and DR-minus-fresh 0.933–0.957 retain finite-sample limitations.
This supersedes the earlier blanket statement that fitted-DR operating characteristics are unavailable;
cross-fitted and joint-branch inference remain unresolved. Readiness 55% (0 points; 45–65%).

**21 September, 17:18 cycle:** the empirical section now integrates scoped synthetic development, the
2,000-repetition-per-cell fixed-score coverage study and subsequent replication sensitivity. It retains OR bias,
IPW undercoverage and the distinction from real-agent benefit. The prior 35-page snapshot statements below
are historical. Fitted-DR and joint-branch inference remain unvalidated. Readiness 55% (0 points; 45–65%).

# Theory-first manuscript status

**Updated 20 September 2026.** This is a working draft of the scoped theory paper, now with an archived descriptive coding case study and a prospective validation plan. New model/Monte Carlo work remains deferred for the theory workstream; the separately authorized experiment worker is producing development simulations. It is not a submission-ready claim, a novelty certification, or external peer review.

**21 September design follow-up:** the [literature/code audit](../docs/literature_design_review_20260921.md) and
[prospective v2 protocol](../docs/experiment_protocol_v2.md) are reviewed repository deliverables, not yet new paper
results. The [conditional-frame audit](../docs/theory_feedback_20260921_conditional_frame.md) reproduces the new
worker arithmetic while correcting its target and variance-component interpretation. No validated interval or
new observation follows. The existing 35-page PDF/TeX are unchanged; `validation.json` records their earlier build
snapshot and should not be read as a hash validation of subsequently updated coordination documents. Readiness
remains 55%, change 0 points, range 45–65%, with the same three gaps listed below.

**21 September, 14:18 cycle:** paired synthetic DR/OR development results are now available and reviewed in
[the scientific feedback](../docs/theory_feedback_20260921_dr_results.md). Saved-estimate arithmetic is independently
checked; fitted DR reduced observed RMSE versus trajectory IPW in all 12 rows, while two fitted OR rows show
positive bias requiring retrospective diagnosis. These results are not yet integrated into the PDF/TeX and do
not validate interval coverage or real-agent benefit. The earlier “prospective” wording describes the paper's
current contents, not the absence of new repository results. Overall readiness remains 55% (0 points; 45–65%).

## Delivered scope

| Component | Status and boundary |
|---|---|
| Introduction and closest work | Written; 24 cited references (primary papers and an explicitly attributed classical asymptotics text), with inherited methods explicitly attributed. The canonical repository bibliography includes additional background references. |
| Observation model and identification | Written and proved for versioned macro actions, bounded horizons, sequential support, exchangeability, and stable kernels. |
| Fixed-policy estimation | EIF, exact drift, sufficient cross-fitting conditions, and finite-class improvement guarantee proved. Point consistency is distinguished from valid intervals. |
| Sampling and resources | Root task clusters, paired contrasts, and resource outcomes specified. Arbitrary selected branches are not treated as root episodes. |
| Supported interventions | Fixed versus unknown-behavior-dependent targets distinguished; the behavior-adaptive gradient is derived. A general estimator/rate theorem for the latter remains outside scope. |
| Eligible-opportunity reduction | Exact block factorization and likelihood ratio proved; second-moment bound depends on eligible opportunities, not realized switches. |
| Branch validation and allocation | Prefix transport, exact augmented-score mean/variance, independent two-sample corollary, and clipped oracle cost allocation proved. Global optimal exploration is not claimed. |
| Fixed-size prefix sampling | Conditional fixed-frame variance and an unbiased estimator with replicated continuations proved; the additional source-frame/log variance term for a full joint comparison remains unresolved. |
| Full-frame quadratic moments | Conditional unbiased reconstruction using pair inclusion and continuation-noise subtraction proved; applying the identity to task derivatives does not establish source-frame variance or coverage. |
| Source-population variance link | A bounded iid task-population CLT, oracle variance link and expectation-only sampled-quadratic corollary are proved; fixed-benchmark inference, sampled-variance concentration and joint coverage remain open. |
| Execution drift | Full-history coupling bound and deployment-adjusted improvement certificate proved for externally justified kernel allowances and a common payoff. The allowances are not estimated from ordinary logs. |
| Replay limits | Outcome copying distinguished from frozen-state reward recomputation; adaptive donor failure and a narrow positive control proved in Section 8.2. |
| Empirical sections | Descriptive coding case integrated, with all six policies and unfavorable/unresolved comparisons; numeric and narrative review complete. Prospective design includes feedback/opportunity thresholds. New simulations and GPU/model execution remain deferred. |
| Discussion and reproducibility | Written, with practical limitations, open questions, build instructions, and this audit record. |

There are 15 numbered theorem/proposition/corollary statements, plus additional derived identities and explicitly scoped corollaries in the prose. All proofs concern their written assumptions; no claim is made that realistic agent systems already satisfy those assumptions.

## Review and validation

- A separate agent reviewed the theory and assembled manuscript. The [full review](../docs/theory_review_20260919.md) records findings and resolutions. A second agent checked source positioning and the rendered latter half of the paper.
- Corrections made during review: valid root marginals for cluster inference; explicit sequential support for every candidate; almost-everywhere support wording; proportional fold sizes; target-null conventions for branch scores; residual-second-moment allocation; complete kernel/payoff conditions; and manuscript conversion/cross-reference repairs.
- **Prior test checkpoint (`13bad73`):** 80 selected tests passed (37 root, including 27 exact theoretical cases, and 43 publication-gate fixtures). That suite and the broader experiment dependency suite were not rerun for this prose-only paper revision. Prior transcript reconstruction remains completed evidence, not fresh outcome verification.
- **Current deterministic checks:** the lead reproduced the pinned A6 audit and fixed-benchmark bound constants/finite-population checks. An independent reviewer checked the new tables against archived values and reviewed the separate bound's proof; no validated empirical confidence interval follows.
- The compiled PDF has **35 pages** and **15 numbered results**. All pages were rendered: the primary reviewer inspected pages 1–20 in contact sheets and an independent reviewer inspected pages 21–35 individually, including both new case-study tables and the bibliography. No clipping, overlaps or missing glyphs were found. All original formal-theory section files are byte-unchanged. The final LaTeX log has no warnings, undefined references/citations or overfull boxes.
- The paper build uses the canonical bibliography with audit-only notes removed for display. Source-level audit annotations remain in the canonical file.
- `validation.json` records the PDF/source hashes and reproducibility details. Build intermediates are ignored by Git.

## Integration boundary

This manuscript builds on the original theory package at `40da0d42422611f61f49fdec23dbf2f76a40eb6d`. The current
revision follows `aac69b5`, integrating reviewed archived findings as a descriptive case study in Section 11 and
aligning the abstract, introduction, future methods and discussion. The independent [A6 correction and paper review](../docs/theory_feedback_20260920_case_study.md)
rejects the worker's remaining bound/precision/selection claims. All original experiment archives are preserved.
No new models, candidate code, verifiers or Monte Carlo workloads were executed. The prior 31-page PDF and its
validation record remain in Git history. The separate fixed-benchmark bound is reviewed but unintegrated; useful
inference and execution/recovery assumptions are still unresolved.

**Current readiness: about 55% (0 percentage-point change; judgment range 45–65%).** Remaining milestones:
useful validated inference and adequate comparisons; remaining statistical validation and final empirical synthesis;
independent reproducibility, author-approved metadata and submission packaging. This is not submission-ready.

## Earlier checkpoints (historical evidence status)

**20 September, author-requested scientific diagnosis:** three independently reconstructed diagnostics identify
the learned policy as a fixed large/small/large repair schedule, document zero visible checks on 60/330 evaluation
tasks and limited repair eligibility, and reproduce the class-tailored IPW/DR/live discrepancy without finding an
inspected assignment or calculation mismatch. The [lead's scientific decisions](../docs/scientific_diagnosis_20260920.md)
retain the original metric, fixed-benchmark target and unfavorable results, and specify concrete reporting and
future-design requests. These retrospective results are not yet integrated into the unchanged 31-page PDF.
Further peripheral theorem extensions are lower priority than resolving the declared inference and empirical claims.
The concurrent A6 diagnosis at `4f9abe4` was also reviewed: its empirical oracle-ceiling, no-power and
theory-vindication claims were rejected, and current result narratives corrected while preserving the old artifact.
The lead also inspected and preserved `8382b3c`'s provenance/reporting fixes. Readiness is conservatively revised
to **about 55% (−5 percentage points; range 45–65%)** because validation remains materially incomplete, not because
the results are unfavorable. Valid inference/adequate comparisons, full empirical integration, and independent
final reproduction/metadata/packaging remain the largest gaps. See the diagnostic report for the unchanged rubric
and the distinction between the workstream's reported audit inventory/tests and independent checks.

**20 September, 19:34 UTC coordination review:** the source-model result is now Section 9.5, Proposition 13 of
the **31-page paper**, with separate mathematical review and all-page visual QA. Independent public-source task
regeneration reproduces all 591 frozen records, and transcript reconstruction matches all 800 parent/branch/durable
hashes. The prior missing-input blocker is resolved; model/tool execution and final inferential validation are
still separate gates. All 20 non-analysis artifacts remain unchanged. All 40 bounded gate cases meet expectations,
and 80 selected tests pass. See the [response](../docs/theory_feedback_20260920_reconstruction.md). Readiness remains
**about 60% (0 percentage-point change; range 50–65%)**. The three largest gaps are valid joint inference/comparators,
complete empirical manuscript integration, and independent reproducibility/metadata/final packaging.

**20 September, 17:51 UTC coordination review:** all three prior checker repairs at `3f9000a` are accepted;
actual report bindings and 800 stored parent/branch/durable links reconcile, with all 20 non-analysis artifacts
unchanged. Full transcript reconstruction still needs the missing frozen task input. The new
[source-model note](../docs/theory_branch_source_model.md) proves a sufficient iid task-population variance link
and expectation-only sampled-quadratic corollary, with independent review and three exact examples. It does not
validate the fixed-benchmark band or prove sampled-variance concentration/joint coverage. The note is not yet
integrated into the unchanged 29-page PDF. The selected suite passes 79 tests; see the
[response](../docs/theory_feedback_20260920_source_model.md). Readiness stays **about 60% (0 percentage-point change;
range 50–65%)**. Valid joint inference/comparators, complete manuscript/result integration, and independent
reproducibility/metadata/final packaging remain the three largest gaps.

**20 September, 16:08 UTC coordination review:** the [response](../docs/theory_feedback_20260920_restoration.md)
accepts five of six prior checker repairs at `97689b9`, documents remaining report/source binding failures, and
independently verifies all 800 stored branch/parent/durable hash links. Full transcript reconstruction remains
workstream-reported because the frozen task input is absent locally. All 20 non-analysis artifacts are unchanged.
The quadratic identity is now Section 9.4, Proposition 12 in the **29-page paper**, with proof and visual review;
**71 selected tests** pass. Empirical results and full joint inference remain unintegrated/unresolved respectively.
Readiness stays **about 60% (0 percentage-point change; range 50–65%)**; the three largest gaps remain valid
joint inference/comparators, complete result integration, and independent reproducibility/metadata/final packaging.

**20 September, 12:55 UTC coordination review:** gate repairs and the actual recovery ledger at `bd1ace8` were
independently checked; remaining reference/hash/ledger-detail requirements are in the [response](../docs/theory_feedback_20260920_recovery.md).
The new [quadratic-moment note](../docs/theory_branch_quadratic.md) supplies a reviewed conditional identity for
recovering the latent full-frame squared-derivative statistic, preserving the pooled target. Four new exact checks
pass; the selected suite passes 64 tests (34 root, 30 gate). The source-model variance link and coverage remain open.
This note is not yet integrated into the unchanged 28-page PDF; its prior validation hashes still match. Readiness
remains **about 60% (0 percentage-point change; range 50–65%)**.

**20 September, 11:15 UTC coordination review:** accepted the A5 reporting repairs and checked the new replay
mechanics fixtures at `8ab7fb5`. The reviewed replay counterexample and positive control are now integrated into
Section 8.2 of the **28-page paper**, with proof review, a clean build and document-wide visual review. A pinned
production-function audit connects the exact construction to the implemented replay rule; empirical performance
results remain deferred. See the [response](../docs/theory_feedback_20260920_replay_integration.md). Full-project
readiness remains **about 60% (0 percentage-point change; range 50–65%)**; joint inference/comparators, complete
result integration and the final reproducible package with author metadata remain open.

**20 September, 09:32 UTC coordination review:** the post-hoc replay comparison at `560135e` is independently
reconstructed and its interpretation corrected in [the response](../docs/theory_feedback_20260920_replay.md).
The separately reviewed [theory note](../docs/theory_replay_boundaries.md) adds an adaptive donor counterexample
and a constant-action positive control, with three exact checks; the root suite now passes 30 tests. This note is
not yet integrated into the 27-page PDF, whose source and validation hashes remain unchanged. Readiness stays
**about 60% (0 percentage-point change; range 50–65%)**; joint inference/comparator validation, full manuscript
integration and reproducible final packaging remain open.

**20 September, 07:50 UTC coordination review:** the conditional sampling proof is integrated into Section 9.3, Proposition 11, with independent proof-preservation review and a clean 27-page build. Exact uncertainty limits remain explicit. At `6f92026`, 12 of the previous 14 checker bypasses are fixed; the new independent audit identifies remaining reference-data, identity/linkage and recovery cases, while all 19 non-analysis code-study artifacts remain unchanged. Accepted reporting fixes and exact replacements for residual contradictions are in the [response](../docs/theory_feedback_20260920_integration.md). Full-project readiness remains **about 60% (0 percentage-point change; range 50–65%)**; manuscript progress does not close empirical inference/comparators or final packaging.

**20 September, 06:04 UTC coordination review:** `29ee443` restores the original pooled branch comparison and narrows several claims. The new [sampling supplement](../docs/theory_branch_sampling.md) proves the conditional fixed-frame branch variance and an unbiased estimator, with independent mathematical review and four exact enumeration tests. The full branch-minus-log sampling justification remains open. Nine publication-gate fixtures pass, but independent CLI counterexamples expose missing checks; see the [response](../docs/theory_feedback_20260920_sampling.md). The repository root suite now has 27 passing tests (36 including the nine gate fixtures). The 25-page PDF and its numbered results are unchanged; the new supplement is not yet integrated there. Readiness stays **about 60% (0 percentage-point change; range 50–65%)**.

**20 September, 04:24 UTC coordination review:** completed branch records through `d4997c6` reconcile to all 800 planned IDs, with recovery provenance retained. The new linked analysis selects 42 tasks and changes weights, so it is not a correction of the original pooled contrast's variance. The [review](../docs/theory_feedback_20260920_branch.md) supplies an independently checked exact ratio derivative and deterministic counterexamples, without asserting a valid design-specific interval. Several earlier prose/figure fixes are accepted; recovery costs, joint inference, remaining comparators and paper integration remain open. Full-project readiness stays about **60% (0 percentage-point change; judgment range 50–65%)**. No PDF or numbered manuscript theorem changed.

**20 September, 02:44 UTC coordination review:** experiment commit `ac3ca83` now publishes all 3,960 live-policy episodes. Independent artifact checks and numerical reconstruction support the saved arithmetic, with interpretation narrowed in [the current review](../docs/theory_feedback_20260920.md) and [experiment summary](../docs/experiment_results.md). Only 135/800 branch completions are committed; earlier certificate, restoration and inference gates remain open. The secondary learned-versus-always-large comparison establishes neither superiority nor equal quality. These results are not yet integrated into the PDF; no manuscript theorem or compiled artifact changed. Full-project readiness advances to about **60% (+10 percentage points; judgment range 50–65%)** under the unchanged rubric.

**19 September, 22:00 UTC coordination review:** the newer experiment checkpoint `035d245` contains a completed randomized coding log and frozen learned policy. Independent read-only checks of its records and implementation are documented in [theory feedback](../docs/theory_feedback_20260919.md). Live/branch comparisons are not committed, and the review identified analysis gates requiring correction. No numerical effects have been added to the paper; the compiled PDF and its validation record are unchanged. Full-project readiness remains about **50% (0 percentage-point change; judgment range 45–60%)** under [the stable rubric](../docs/readiness.md).

Finalize the author list, affiliations, target venue, and contribution positioning. When experimental work resumes, freeze the final protocol, collect sufficient independent tasks, and add known-truth operating characteristics and fresh-policy validation with uncertainty. Any scientific claim of superior task performance, lower evaluation cost, or successful deployment requires those results. New theory for globally optimal exploration, adaptive branch allocation, unmeasured routing information, unrestricted optimal-policy inference, or unknown deployment drift requires separate assumptions and proofs.
