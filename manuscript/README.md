**28 September 2026, Matplotlib synthesis validated:**42-page PDF rebuilt with verified officialTectonic0.17.0; pages36–42 rendered/visually checked, first35 text-identical. Controls, Qwen infrastructure abort and Klear admission expiry remain distinct, no competence/routing-benefit claim. Earlier compiler-unavailable record preserved as superseded. Readiness55%,Δ0,45–65%; empirical comparison/inference and final package remain incomplete.

**28 September 2026, pending source synthesis:** Matplotlib controls and infrastructure/admission outcomes added to source. Build executable unavailable; this revision is NOT rendered/validated and the previous PDF is unchanged. See validation_20260928_matplotlib_pending.json. Readiness55%,Δ0,45–65%; core empirical/inference and final reproducibility remain.

**27 September 2026, scaffold/evidence synthesis:**42-page draft now distinguishes the incomplete Django pair (Qwen format failure; Klear unattempted),74 within-task evaluator controls, and omitted upstream format recovery. No recovery benefit or model ranking claimed; old outcomes retained. Build passed; pages35–42 visually checked, first34 text-identical. [Validation](validation_20260927_scaffold.json). Readiness55%,Δ0,45–65%; competent comparisons/valid inference, synthesis, independent reproducibility/author package remain.

**27 September 2026, reference-control synthesis:** the41-page manuscript now reports176/176 reference-patch passes in the same offline evaluator, retaining the initial setup failure, no-change175/1 and model-patch174/2 outcomes. These remain within-task controls, not model baselines or routing evidence. Build passed; changed pages35–41 rendered and visually checked, first34pages text-identical. [Validation](validation_20260927_reference_control.json). Readiness55%,change0points,range45–65%; competent comparison/valid inference,synthesis,reproducibility/approved package remain.

**27 September 2026, 41-page synthesis:** integrated the split-host single-model attempts and separate evaluator controls, explicitly distinguishing 175 within-task regression passes from a model baseline. Added the absent positive-control and routing-opportunity/feedback limitations. REQ-007's previously completed matched-policy collapse remains unchanged; the mistakenly proposed REQ-029B repeat was stopped before preparation/execution. Tectonic build passed; pages34–41 rendered and inspected, first33 pages text-identical. [Validation](validation_20260927_synthesis.json). Readiness55%,change0points,range45–65%; adequate comparison/inference, final synthesis and independent reproducibility/approved package remain.

# Dynamic Agent Regimes — full theory-first manuscript

**26 September 2026, manuscript synthesis:** the current 40-page draft integrates the separately preserved REQ-011/012/014 coding probes and REQ-016/017 browser screens, makes the held primary history-aware versus matched prompt-only comparison explicit, and states fixed-task execution-unit and precision limitations. No formal theorem, frozen outcome, endpoint or stage authorization changed. All 40 pages were rendered and visually inspected after a successful Tectonic build; the sole reported package warning is benign UTF-8 `inputenc` handling. [Validation](validation_20260926_synthesis.json). Full-project readiness **55%, change 0 percentage points, range 45–65%**; competent fixed-target comparison with valid inference, final empirical synthesis, and independent reproducibility/author-approved metadata/package remain incomplete.

**Prior revision, 24 September 2026:** 38-page draft, with the retrospective matched-class
routing diagnostic integrated in Section 11 and the discussion; both failed repository-repair DEV
cohorts remain separate in Section 12.3. QA at that revision:
[validation_20260924_req007.json](validation_20260924_req007.json); previous dated snapshots below
are historical. Formal results and primary target unchanged. Readiness **55%, 0 points, 45–65%**;
validated inference/comparisons, final synthesis and reproducibility/metadata/package remain.


**Working draft, updated 22 September 2026 (37 pages).** [Read the current PDF](DTR_Agent_Regimes_Theory_Draft.pdf), [edit the source](main.tex), or read the [validation and status record](STATUS.md).

The current paper develops the theory, complete proofs for its stated results, introduction, related-work positioning, discussion, and prospective empirical methods. The archived coding experiment is now integrated as a descriptive case study, including all six live-policy comparisons, limited feedback/repair opportunities, the fixed learned schedule, unfavorable replay comparison and unresolved calibration/inference. The empirical section, abstract and discussion also report scoped synthetic development, fixed-score coverage, replication sensitivity, honest-split repeated-training and five-fixed-fit diagnostics; the two unsuccessful repository-repair DEV cohorts, configuration deviations, and later bounded coding/browser probes are integrated in Section 12.3. Broader inference validation and prospective routing evaluation remain incomplete. Historical arithmetic pilots are not treated as confirmatory evidence.

## Mathematical content

- Versioned model interventions, sequential identification, routing probability ratios, fixed-policy influence function, exact doubly robust drift, cross-fitting, and honest policy comparisons.
- Replay operation boundaries: a supported adaptive donor counterexample with unlimited donors and a narrow constant-action positive control.
- Task-level inference conditions, resource outcomes, supported stochastic interventions, and the distinction between a frozen reference and an unknown-behavior-dependent target.
- Exact reduction to prospectively eligible routing opportunities, including decisions to keep the current model.
- Target-prefix transport of selected live branches, augmentation, exact one-sample and two-sample variance, and oracle branch-cost allocation with selection floors and saturation cases.
- Fixed-size sampling of a recorded prefix frame: conditional variance, an unbiased variance estimator with replicated continuations, and the remaining source-frame/log component needed for a joint comparison. This result does not establish empirical interval coverage.
- Conditional recovery of latent full-frame quadratic moments using pair inclusion and continuation-noise subtraction, applied to pooled task derivatives. An iid source-population expectation-level variance link is proved separately; its applicability to the fixed benchmark and joint interval coverage remain open.
- A coupling sensitivity bound for changed execution kernels and a deployment-adjusted policy-improvement certificate.

The paper attributes the classical methods it adapts. Correct proofs and a complete draft do not establish sufficient novelty for a particular venue, empirical superiority, or submission readiness. Author names, affiliations, venue formatting, remaining statistical validation and final empirical synthesis remain to be finalized. General optimal sequential exploration and the other limitations listed in the discussion remain open.

## Edit and build

The section files in `sections/` are native, editable LaTeX. The manuscript is self-contained within the repository; no model server or GPU is required to build it.

```sh
sh manuscript/build.sh
```

Requirements: Python 3.10+ and either `latexmk` with pdfLaTeX/BibTeX or Tectonic. The build prefers `latexmk` when available. The fallback was validated with official Tectonic 0.17.0 on ARM macOS; the existing pdfLaTeX branch was not rerun on this host. Set `DTR_TECTONIC_BIN=/absolute/path/to/tectonic sh manuscript/build.sh` to locate the fallback binary. Its first build may fetch TeX support files; prewarm its cache before offline use. See the [official installation instructions](https://tectonic-typesetting.github.io/book/latest/getting-started/install.html) and [composite license](https://github.com/tectonic-typesetting/tectonic/blob/tectonic%400.17.0/LICENSE): Tectonic is MIT, with derived components under their respective licenses. No compiler binaries or fetched packages are redistributed here. The build regenerates `manuscript/references.bib` from the canonical `references/references.bib`, omitting internal source-audit notes. Edit the canonical bibliography to change citations. Temporary LaTeX files go to ignored `manuscript/build/`; the final PDF is copied here.

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

**22 September, 06:48 UTC cycle:** Section 12.3 retains all pilot operational failures and the undefined
algorithmic-success rate, with a scoped retrospective configuration diagnosis. Independent scientific and visual
review completed; formal theory unchanged. The current 37-page build and sources are recorded in
[validation_20260922_pilot.json](validation_20260922_pilot.json); `validation.json` remains the historical snapshot.
Readiness 55% (0 points; 45–65%); the corrected cohort is planned, not completed.
