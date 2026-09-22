# Dynamic Agent Regimes — full theory-first manuscript

**Working draft, updated 22 September 2026 (36 pages).** [Read the current PDF](DTR_Agent_Regimes_Theory_Draft.pdf), [edit the source](main.tex), or read the [validation and status record](STATUS.md).

The current paper develops the theory, complete proofs for its stated results, introduction, related-work positioning, discussion, and prospective empirical methods. The archived coding experiment is now integrated as a descriptive case study, including all six live-policy comparisons, limited feedback/repair opportunities, the fixed learned schedule, unfavorable replay comparison and unresolved calibration/inference. The empirical section, abstract and discussion also report scoped synthetic development, fixed-score coverage, replication sensitivity, honest-split repeated-training and five-fixed-fit diagnostics; broader inference validation and new model evaluation remain incomplete. Historical arithmetic pilots are not treated as confirmatory evidence.

## Mathematical content

- Versioned model interventions, sequential identification, routing probability ratios, fixed-policy influence function, exact doubly robust drift, cross-fitting, and honest policy comparisons.
- Replay operation boundaries: a supported adaptive donor counterexample with unlimited donors and a narrow constant-action positive control.
- Task-level inference conditions, resource outcomes, supported stochastic interventions, and the distinction between a frozen reference and an unknown-behavior-dependent target.
- Exact reduction to prospectively eligible routing opportunities, including decisions to keep the current model.
- Target-prefix transport of selected live branches, augmentation, exact one-sample and two-sample variance, and oracle branch-cost allocation with selection floors and saturation cases.
- Fixed-size sampling of a recorded prefix frame: conditional variance, an unbiased variance estimator with replicated continuations, and the remaining source-frame/log component needed for a joint comparison. This result does not establish empirical interval coverage.
- Conditional recovery of latent full-frame quadratic moments using pair inclusion and continuation-noise subtraction, applied to pooled task derivatives. The source-model variance link and interval coverage remain open.
- A coupling sensitivity bound for changed execution kernels and a deployment-adjusted policy-improvement certificate.

The paper attributes the classical methods it adapts. Correct proofs and a complete draft do not establish sufficient novelty for a particular venue, empirical superiority, or submission readiness. Author names, affiliations, venue formatting, remaining statistical validation and final empirical synthesis remain to be finalized. General optimal sequential exploration and the other limitations listed in the discussion remain open.

## Edit and build

The section files in `sections/` are native, editable LaTeX. The manuscript is self-contained within the repository; no model server or GPU is required to build it.

```sh
sh manuscript/build.sh
```

Requirements: Python 3.10+, `latexmk`, pdfLaTeX/BibTeX, and the LaTeX packages named in `main.tex`. The build regenerates `manuscript/references.bib` from the canonical `references/references.bib`, omitting internal source-audit notes. Edit the canonical bibliography to change citations. Temporary LaTeX files go to ignored `manuscript/build/`; the final PDF is copied here.

## Independent internal review and checks

[The review record](../docs/theory_review_20260919.md) records resolved corrections and the scope of its mathematical audit. [The claim map](../docs/paper_positioning.md) states what is inherited and what this project contributes. These are internal checks, not external peer review or formal proof-assistant certification.

```sh
PYTHONPATH=src .venv/bin/python -m pytest -q
```

The additional paper checks are exact finite-state identities and boundary examples, not a new Monte Carlo or model experiment. The [extension proof notes](../docs/theory_extensions.md) provide a Markdown companion; manuscript source is authoritative for the assembled paper.

## Source-population result integrated in Section 9.5

The [20 September source-model note](../docs/theory_branch_source_model.md) proves a sufficient iid task-population
variance link for the latent quadratic statistic, with explicit boundedness and positive-denominator assumptions.
Its sampled-statistic consequence is in expectation only; concentration and joint interval coverage remain open.
The note received independent mathematical review and three exact illustrative checks. It is now integrated as
Proposition 13 in the 35-page PDF, with proof-preservation and visual review. Its assumptions are not asserted for
the current fixed benchmark, and the expectation-level result does not supply joint interval coverage.


## Descriptive coding case integrated in Section 11

The [21:54 UTC review](../docs/theory_feedback_20260920_case_study.md) records independent numeric and narrative
checks for the new case study. All 35 PDF pages were rendered and reviewed; there are still 15 numbered formal
results, now with 24 cited references. The six-policy tables report observed success, original utility, resource
use and offline/live differences without claiming validated intervals or adaptive superiority. The later
prospective design now requires feedback/opportunity adequacy thresholds and prospective zero-check handling.

The separate [fixed-benchmark concentration note](../docs/theory_branch_fixed_benchmark_bound.md) received an
independent mathematical review and deterministic checks. It makes the pooled-prefix ratio-of-expected-totals
convention explicit, retains zero-contribution tasks and returns the entire possible gap range at the archived
sample size. It is not integrated into the PDF, does not validate the archived execution assumptions or derivative
band, and leaves informative joint inference open. No new model/GPU or Monte Carlo run was made.
