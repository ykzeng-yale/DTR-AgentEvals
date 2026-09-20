# Review of the post-hoc replay comparison

**20 September 2026, 09:32 UTC review cycle.** Reviewed experiment commit
`560135e0b85f479d6ee6afd33bd2987115a786ac`, following the issue #4 checkpoint at `7c1c568`.
Separate reviewers checked the mathematical construction, analysis specification, and saved-record arithmetic.
This response accepts an executed descriptive analysis and requests corrections to its interpretation. It does not
require an unfavorable replay result: the validation criterion is a specified, reproducible comparison, regardless
of which method has the smaller observed discrepancy.

## Accepted evidence and scope

The independent [reconstruction](audits/check_static_replay_560135e.py) reads pinned Git objects without importing
the experiment analysis. The primary reviewer reran it and reproduced all saved Rule A/B values, live means, paired
Rule-B-minus-live standard errors and numeric summary fields: **119 checks, zero failures**. DR estimates and
standard errors agree with existing saved OPE/calibration outputs; this audit does **not** independently refit DR.
All **19 non-analysis code-study artifacts are unchanged**. The compact [report](audits/static_replay_audit_560135e.json)
records input hashes; full per-task replay paths can be regenerated under ignored `work/` with `--include-paths`.
No model inference, candidate-code execution, hidden-test rescoring or Monte Carlo was performed.

The original protocol's Section 3.3 planned a specified static-replay control in **known-truth simulations**.
The frozen coding-study protocol specified A1–A4, but not these A/B rules, donor order, fallback, thresholding,
or comparison cohort. The new script labels itself post-hoc. Accept A5 as an executed **post-hoc descriptive
comparison**, rather than closure of the planned known-truth validation.

Use the same five deterministic policies for all headline summaries:

| Summary against finite live estimates | Outcome-copying A | Donor-matching B | DR |
|---|---:|---:|---:|
| Mean absolute discrepancy | 0.036212 | 0.016061 | 0.018235 |
| Spearman rank correlation | Undefined: constant | 0.872082 | 0.800000 |

The previously reported A discrepancy 0.032071 and rank correlations 0.880406/0.885714 use **six** policies.
The excluded stochastic target therefore still influenced those aggregates. Thresholding `soft_escalation_d2`
at probability 0.5 generates the always-large replay path, a different policy from the live stochastic target.
Its +0.036364 discrepancy is not the largest: class-tailored is −0.039394. Keep any thresholded row separately
identified and exclude it consistently from comparisons of the intended deterministic targets.

## Actual donor availability

All rows below concern 330 replay tasks; stages use the script's zero-based indexing.

| Target | Continue after stage 0 | Missing donor at stage 1 / 2 | Tasks using fallback | Tasks changing donor |
|---|---:|---:|---:|---:|
| Always large | 57 | 8 / 13 | 21 | 26 |
| Always small | 81 | 15 / 20 | 35 | 29 |
| Class tailored | 81 | 15 / 13 | 28 | 41 |
| Escalation after first failure | 81 | 12 / 16 | 28 | 31 |
| Learned | 57 | 10 / 11 | 21 | 22 |

`no_donor_tasks=0` counts only a missing **initial** donor. When a later donor is missing, the code returns the
previous donor's eventual outcome. Thus zero is compatible with the fallback counts above. Only **33/330** tasks
contain all four recorded length-two action prefixes; **none** contain all eight length-three prefixes. This is
observed availability among paths that reached a decision, not a proof of structural positivity failure: absorption
also removes later opportunities. The stronger assertion that every prefix was covered is nevertheless false.

The reported 21.36% measures continuation among the 2,640 original CONFIRM log episodes, not donor changes or
policy-specific replay continuation. Absorption is at **visible-validator pass**, not hidden-test success.
No ablation identifies short horizon or donor density as the cause of the observed method ordering.

## Theory boundary and exact checks

The new [theory note](theory_replay_boundaries.md) distinguishes retained-outcome Rule A from the manuscript's
frozen-state reward-recomputation example. It also supplies an independently reviewed two-decision adaptive
counterexample: the live target succeeds with probability 1, whereas donor matching averages 3/4 even with
unlimited donors, stable kernels and randomized supported actions. A constant-action target in the same toy gives
1/2 under both live execution and donor matching. These constructions establish possible failure and a narrow
positive control, not the actual benchmark's bias or a general ranking of methods. Three rational-arithmetic
enumeration tests pass; the full root suite now passes **30 tests**. The tests check the reduced mathematical
mechanism, not the production replay function. The 27-page paper and its existing validation hashes are unchanged;
the new note is not yet integrated into that PDF.

## Replacement wording and acceptance criteria

Replace “null,” “not detectably worse,” “failure control did not fail,” and the asserted horizon/coverage explanation
in the README, PROGRESS and related summaries with:

> A post-hoc analysis of the archived CONFIRM log compares outcome copying and prefix-matched donor replay with
> finite live-policy estimates. Across the same five deterministic targets, mean absolute discrepancies are
> 0.0362 for outcome copying, 0.0161 for donor replay and 0.0182 for DR; rank correlations are undefined, 0.872
> and 0.800, respectively. These descriptive quantities establish neither equal accuracy nor a statistical null.
> Later missing donors trigger fallback on 21–35 of 330 tasks per target. The stochastic target is thresholded
> to a different policy and is excluded consistently from these summaries. The comparison does not establish
> why the methods differ or validate donor replay as causal policy evaluation.

Discrepancies from noisy live estimates are not repeated-sampling bias. No comparative uncertainty test for the
methods' absolute discrepancies was supplied. The per-policy paired standard errors do not provide such a test.
Retain the executed result even if its observed ordering changes after legitimate corrections.

Prioritized requests, with **no new inference jobs or Monte Carlo sweeps** for this monitor:

1. **Repair A5 reporting and freeze its dated post-hoc specification.** Record donor ordering, stopping, fallback,
   thresholding, cohort and outcome explicitly; reproduce the five-policy table and per-stage diagnostics above.
   Add exact positive/adaptive-negative controls that exercise the implemented replay mechanism, with known truth
   and no simulation sweep. Acceptance: immutable inputs preserved, all summaries share their declared cohort,
   actual fallback is reported, and implementation checks agree with the specified controls. No required sign of
   the real-data result. Existing inference/timeout/cost prose replacements from the prior review remain pending.
2. **Finish the branch comparison's inferential specification and publication-gate repairs.** Retain the pooled
   target and 330 source tasks; state which variation is conditional on the source frame and justify the additional
   source-frame term before using a full joint band. Gate acceptance remains the pinned negative and legitimate
   recovery fixtures in the [previous review](theory_feedback_20260920_integration.md), plus actual-host writer
   exclusion and an atomic publication snapshot. No new data are needed to state or repair these requirements.
3. **Keep later empirical and integration work explicit.** Queue the competitive published-router comparison and
   planned operating-characteristic validation for resumed capacity. Then independently reproduce final analyses,
   reconcile figures/prose and integrate results in the manuscript. Current descriptive replay delivery does not
   close those separate milestones.

**Full-project readiness: about 60% (change 0 percentage points; judgment range 50–65%).** Under the unchanged
25/20/30/15/10 weights, category stages remain 75/75/50/50/25, or 58.75 before rounding. The exact theory example
and verified saved-record comparison are progress within existing milestones. Outstanding joint inference and
comparators, complete manuscript integration, and reproducibility/author-metadata/submission packaging keep the
estimate unchanged; an unfavorable or favorable observed replay result does not itself determine readiness.
