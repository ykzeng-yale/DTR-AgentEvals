# Theory-first manuscript status

**Updated 20 September 2026.** This is a complete working draft of the scoped theory paper, with empirical methods prespecified and empirical performance results deliberately deferred. It is not a submission-ready claim, a novelty certification, or external peer review.

## Delivered scope

| Component | Status and boundary |
|---|---|
| Introduction and closest work | Written; 21 cited primary references, with inherited methods explicitly attributed. The canonical repository bibliography includes additional background references. |
| Observation model and identification | Written and proved for versioned macro actions, bounded horizons, sequential support, exchangeability, and stable kernels. |
| Fixed-policy estimation | EIF, exact drift, sufficient cross-fitting conditions, and finite-class improvement guarantee proved. Point consistency is distinguished from valid intervals. |
| Sampling and resources | Root task clusters, paired contrasts, and resource outcomes specified. Arbitrary selected branches are not treated as root episodes. |
| Supported interventions | Fixed versus unknown-behavior-dependent targets distinguished; the behavior-adaptive gradient is derived. A general estimator/rate theorem for the latter remains outside scope. |
| Eligible-opportunity reduction | Exact block factorization and likelihood ratio proved; second-moment bound depends on eligible opportunities, not realized switches. |
| Branch validation and allocation | Prefix transport, exact augmented-score mean/variance, independent two-sample corollary, and clipped oracle cost allocation proved. Global optimal exploration is not claimed. |
| Fixed-size prefix sampling | Conditional fixed-frame variance and an unbiased estimator with replicated continuations proved; the additional source-frame/log variance term for a full joint comparison remains unresolved. |
| Execution drift | Full-history coupling bound and deployment-adjusted improvement certificate proved for externally justified kernel allowances and a common payoff. The allowances are not estimated from ordinary logs. |
| Empirical sections | Prospective methods and reporting targets written. New simulations, GPU/model execution, and empirical results deferred. |
| Discussion and reproducibility | Written, with practical limitations, open questions, build instructions, and this audit record. |

There are 13 numbered theorem/proposition/corollary statements, plus additional derived identities and explicitly scoped corollaries in the prose. All proofs concern their written assumptions; no claim is made that realistic agent systems already satisfy those assumptions.

## Review and validation

- A separate agent reviewed the theory and assembled manuscript. The [full review](../docs/theory_review_20260919.md) records findings and resolutions. A second agent checked source positioning and the rendered latter half of the paper.
- Corrections made during review: valid root marginals for cluster inference; explicit sequential support for every candidate; almost-everywhere support wording; proportional fold sizes; target-null conventions for branch scores; residual-second-moment allocation; complete kernel/payoff conditions; and manuscript conversion/cross-reference repairs.
- The repository root test suite passed: **27 tests**, including **17 exact theorem checks** across the three theory test files. With the 22 publication-gate fixtures, this review ran **49 passing tests**. These checks do not launch a new Monte Carlo sweep or model experiment; the workstream's broader reported test run is separate.
- The compiled PDF has **27 pages**. All pages were rendered and visually reviewed: the primary reviewer inspected pages 1–17, and a separate reviewer checked pages 18–27 and preservation of the new proof. Bibliography, cross-references, equations, margins, and indicator glyphs were checked; the final LaTeX log has no warnings, undefined citations/references or overfull boxes. The final page contains one bibliography entry; this is a minor pagination choice, not missing content.
- The paper build uses the canonical bibliography with audit-only notes removed for display. Source-level audit annotations remain in the canonical file.
- `validation.json` records the PDF/source hashes and reproducibility details. Build intermediates are ignored by Git.

## Integration boundary

This manuscript builds on the original theory package at `40da0d42422611f61f49fdec23dbf2f76a40eb6d`. Its initial publication followed repository checkpoint `66b7488`; the current paper revision follows `6f92026` and integrates the reviewed conditional sampling note from `7d06c2d`. Later experiment audits are recorded below, but no empirical performance numbers are inserted into this theory-first PDF. The update changes no archived experimental outputs and launches no model workload. The prior PDF/source and validation record remain available in Git history.

## Later author and empirical work

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
