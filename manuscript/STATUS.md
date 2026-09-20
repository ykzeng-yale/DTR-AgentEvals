# Theory-first manuscript status

**19 September 2026.** This is a complete working draft of the scoped theory paper, with empirical methods prespecified and empirical performance results deliberately deferred. It is not a submission-ready claim, a novelty certification, or external peer review.

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
| Execution drift | Full-history coupling bound and deployment-adjusted improvement certificate proved for externally justified kernel allowances and a common payoff. The allowances are not estimated from ordinary logs. |
| Empirical sections | Prospective methods and reporting targets written. New simulations, GPU/model execution, and empirical results deferred. |
| Discussion and reproducibility | Written, with practical limitations, open questions, build instructions, and this audit record. |

There are 12 numbered theorem/proposition/corollary statements, plus additional derived identities and explicitly scoped corollaries in the prose. All proofs concern their written assumptions; no claim is made that realistic agent systems already satisfy those assumptions.

## Review and validation

- A separate agent reviewed the theory and assembled manuscript. The [full review](../docs/theory_review_20260919.md) records findings and resolutions. A second agent checked source positioning and the rendered latter half of the paper.
- Corrections made during review: valid root marginals for cluster inference; explicit sequential support for every candidate; almost-everywhere support wording; proportional fold sizes; target-null conventions for branch scores; residual-second-moment allocation; complete kernel/payoff conditions; and manuscript conversion/cross-reference repairs.
- The full repository test suite passed: **23 tests**, including **13 exact theorem checks** across the existing and new theory test files. These are small CPU algebra checks, not new Monte Carlo or model experiments.
- The compiled PDF has **25 pages**. All pages were rendered and visually reviewed. Bibliography, cross-references, equations, margins, and indicator glyphs were checked; the final LaTeX log has no undefined citations/references or overfull boxes.
- The paper build uses the canonical bibliography with audit-only notes removed for display. Source-level audit annotations remain in the canonical file.
- `validation.json` records the PDF/source hashes and reproducibility details. Build intermediates are ignored by Git.

## Integration boundary

This manuscript builds on the original theory package at `40da0d42422611f61f49fdec23dbf2f76a40eb6d`. The repository was refreshed through `66b7488` before publication, preserving the intervening experiment work. Those newer experiment commits were not independently rerun or validated for this paper and supply no numerical results to it. This update changes no archived experimental outputs and launches no model workload.

## Later author and empirical work

**20 September, 02:44 UTC coordination review:** experiment commit `ac3ca83` now publishes all 3,960 live-policy episodes. Independent artifact checks and numerical reconstruction support the saved arithmetic, with interpretation narrowed in [the current review](../docs/theory_feedback_20260920.md) and [experiment summary](../docs/experiment_results.md). Only 135/800 branch completions are committed; earlier certificate, restoration and inference gates remain open. The secondary learned-versus-always-large comparison establishes neither superiority nor equal quality. These results are not yet integrated into the PDF; no manuscript theorem or compiled artifact changed. Full-project readiness advances to about **60% (+10 percentage points; judgment range 50–65%)** under the unchanged rubric.

**19 September, 22:00 UTC coordination review:** the newer experiment checkpoint `035d245` contains a completed randomized coding log and frozen learned policy. Independent read-only checks of its records and implementation are documented in [theory feedback](../docs/theory_feedback_20260919.md). Live/branch comparisons are not committed, and the review identified analysis gates requiring correction. No numerical effects have been added to the paper; the compiled PDF and its validation record are unchanged. Full-project readiness remains about **50% (0 percentage-point change; judgment range 45–60%)** under [the stable rubric](../docs/readiness.md).

Finalize the author list, affiliations, target venue, and contribution positioning. When experimental work resumes, freeze the final protocol, collect sufficient independent tasks, and add known-truth operating characteristics and fresh-policy validation with uncertainty. Any scientific claim of superior task performance, lower evaluation cost, or successful deployment requires those results. New theory for globally optimal exploration, adaptive branch allocation, unmeasured routing information, unrestricted optimal-policy inference, or unknown deployment drift requires separate assumptions and proofs.
