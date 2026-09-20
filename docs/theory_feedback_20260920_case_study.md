# Scientific review: corrected diagnosis and descriptive paper integration

**20 September 2026, 21:54 UTC coordination cycle.** Reviewed new `main` commit
`aac69b5a634fa3be3ea9c1a26c88e70ef973fe3f` since the issue #4 checkpoint at `7085c77`.
No new observations were published by that commit. The lead and independent reviewers reconstructed the new
quantities from pinned records, reviewed the case-study prose/numbers, and checked the separate fixed-benchmark
bound. This is retrospective diagnosis and paper development, not prospective validation or new model execution.

## What is accepted, and what is corrected

The worker correctly withdrew the universal-router power claim, theory-vindication claim and hidden-test-driven
stopping remedy. Both cost-crossing conventions are now correct. The new commit also uses the requested author
and committer identity. However, its revised A6 interpretation still has material scientific errors:

| Finding | Evidence and scientific decision |
|---|---|
| Upward bias is not an upper bound | Even an unbiased effect estimate taking −.3 or +.1 with equal probability has true effect −.1. Its estimated positive small-over-large gain is .3 or 0; the mean .15 exceeds the true gain .1, yet one realization is below truth. Thus the revised claim “true value ... is no larger” is false even within a fixed partition. The actual cell statistic also mixes estimated ratios, logger occupancy and logger continuation rather than dynamic-policy utility. Remove the ceiling, not merely its universal scope. |
| Wrong precision comparison | The new .0199 matches the archived **learned-minus-always-small success** SE (.01991259). The saved task-paired arithmetic for learned-minus-large is .01103932 for success and .01127754 for utility. These checks identify the comparator error; they do not validate fixed-benchmark confidence intervals. No new replacement interval is requested. |
| Selected 61-task analysis changes the target | 134 tasks reach both later stages. Only 61 have both observed actions at both stages; selection depends on realized assignment and eligibility. Their equal-task stage difference .09371585 reproduces, but changes both cohort and weighting from the original pooled 564/458 eligible episodes. It does not repair the original covariance argument. |
| Initial action endpoint was misinterpreted | HumanEval .145604 and MBPP .072176 are final hidden-success contrasts after randomized initial assignment followed by the logger, including stopping. First-candidate contrasts are instead .189560 and .106695. Neither establishes whole-policy utility dominance or absence of useful heterogeneity. |
| Occupancy is law-dependent | 78.6% is the realized first-call stopping rate under the logger. Policies may change initial actions and subsequent eligibility, so it is not a fixed design limit on any adaptive gain. Informative visible feedback is a legitimate prospective design improvement; held-out verification remains unavailable to deployed stopping. |

The original assertion/previous-large cell has large-minus-small contrast −.003942, directly contradicting
“no examined stratum favors small.” Its small size does not establish a real advantage either. We retain the
original metric, all unfavorable comparisons and every archived result. The current experiments README is
corrected; historical worker entries and both JSON files remain available with this superseding review.
The [audit source](audits/check_why_null_aac69b5.py) and [output](audits/why_null_audit_aac69b5.json) reproduce the
quantities and explicitly distinguish arithmetic reconstruction from interval validity. A committed generator
for the worker's corrected JSON is still absent; numerical agreement alone does not supply its missing provenance.

## Lead decision on the scientific target and inference

The [fixed-benchmark note](theory_branch_fixed_benchmark_bound.md) defines the branch component as
**the ratio of expected eligible-prefix effect totals to expected eligible-prefix counts**, across repetitions
of the original 330 fixed task blocks. The two log components are corresponding ratios of expected weighted
success totals and weighted counts. This is an explicit retrospective clarification of an underspecified ratio
convention, not a claim that the original protocol uniquely prespecified it. The point estimator, task set,
4/4 initial blocking, zero-contribution tasks, branch sampling and original data remain unchanged. The target is
neither an iid task-population mean, an equal-task complete-case effect nor the expected realized ratio.

A separate reviewer found no blocking mathematical issue in the sufficient finite-sample construction. It allows
nonidentical fixed-task laws, arbitrary dependence within each eight-episode block, and dependence between branch
and log estimates. It still requires independent source-task blocks, conditional uniform prefix sampling, complete
planned outcomes, and selection-invariant fresh replicate pairs with the stated conditional independence.
These execution and recovery assumptions are **not established for the archive**.

At the saved sample size the conservative 95% radius is **4.300040**, giving the entire **[−2, 2]** gap range.
The narrower recorded-frame bound addresses a different conditional target. Therefore the note does not validate
the historical .048386 derivative scale or supply useful empirical precision. The next inference step must exploit
justified design structure or variance information under this same target, not discard tasks or quietly impose iid
benchmark sampling. This note does not solve cross-fitted whole-policy DR inference. Its value is identifying the
exact remaining assumptions and width problem; it remains separate from the paper's 15 numbered results.

## Paper integration and evidence status

The **35-page manuscript** now includes the critical coding case study: all six live policies under the original
utility; the full six-policy offline/live table; fixed learned-schedule and stopping diagnostics; both descriptive
penalty-crossing conventions; the unfavorable common-five replay comparison; and local branch points with explicit
unresolved inference/recovery limitations. Only the class-tailored DR fit has been independently reimplemented;
other DR values are labeled as transcribed from pinned saved summaries. No confidence bands, superiority,
equivalence, adaptive-gain or savings claims are added. The primary reviewer reran the A6 audit, bound checks and exact finite source/selection/noise examples; an
independent reviewer checked tables/claims and the rendered latter half of the paper. The original theory sections
and all 15 numbered formal statements are unchanged. New benchmark references have primary-source attribution.

The declared next design now requires development-stage feedback/opportunity adequacy thresholds, prospective
zero-check handling, competent fixed and learned comparators, and prespecified success/resource and precision
criteria. Our prior feasibility gate did inspect eligibility and false alarms, but lacked those adequacy thresholds.
The lead takes responsibility for that design gap. A positive routing result is not a condition for project success.

## Prioritized worker requests and acceptance criteria

1. **Deterministic report repair only.** Publish a generator for a newly named A6 report, preserving both historical
   JSONs. Bind every quantity to source hashes, endpoint, comparator, cohort, weighting and selection rule; label
   the 61-task result exploratory. Acceptance: reproduce the pinned lead audit; omit all oracle ceilings,
   no-heterogeneity/no-power claims, generic .0199 precision and policy-invariant occupancy claims. Do not produce
   another provisional SE or filter the primary cohort as a substitute for inference.
2. **Execution-contract inventory, no reruns.** Map source task blocks, fresh pairs and recovery records to launch
   order, reused process/cache state, RNG and recovery acceptance rules. Mark documented versus unknown facts.
   Acceptance: exact artifact/code references and an explicit assessment of each assumption in the fixed-benchmark
   note; distinct seeds or matching bytes must not be labeled proof of independence. The lead will decide which
   model is defensible and derive any sharper bound.
3. **Prospective draft only; model/Monte Carlo work deferred.** Draft the new feedback, fixed-schedule/router and
   interleaved-calibration design using development data only. Acceptance: prespecified adequacy and precision
   criteria, deployable feedback, original held-out archive retained, and no CONFIRM-based tuning presented as a
   fresh confirmatory result. The lead owns target/comparator/metric choices before freezing or requesting compute.

**Full-project readiness remains about 55% (0 percentage-point change; judgment range 45–65%).** Unchanged weights
25/20/30/15/10 and stages 75/75/50/25/25 give **55.00**. Paper integration and a reviewed sufficient bound advance
existing milestones but do not close useful inference, scientific comparators or independent final validation.
The three largest gaps are (1) valid informative inference and adequate comparisons, (2) remaining statistical
validation and final empirical manuscript synthesis, and (3) independent reproducibility, author-approved metadata
and submission packaging. Nothing submitted; no new model/GPU, candidate execution or Monte Carlo workload launched.
