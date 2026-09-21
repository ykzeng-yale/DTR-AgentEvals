# Progress log — experiments workstream

**Latest lead review, 21 September 2026 UTC:** the new `981f7b9` conditional variance arithmetic is reproduced,
but it answers a secondary realized-frame question and does not half-discharge the primary fixed-benchmark B2.
Its estimated latent-between/execution ratio is 1.76, not 7; a conditional test is possible in principle, while
stable kernels do not force that realized-frame gap to zero. See the
[correction](../docs/theory_feedback_20260921_conditional_frame.md). The older “no study numbers” statement below
is stale: the 35-page paper already includes the descriptive case. Stages 75/75/50/25/25 give **55.00**, not 54.25.
The author-requested [literature/code review](../docs/literature_design_review_20260921.md) and
[v2 design](../docs/experiment_protocol_v2.md) now govern future work. They are source-reviewed plans, not runs.
Readiness **55%, change 0 points, range 45–65%**; useful inference/comparisons, remaining statistical/empirical
synthesis and independent reproduction/metadata/package remain open. Historical entries below are preserved.


**Lead review, 20 September 2026, 21:54 UTC cycle:** the 16:45 EDT correction below remains historical and is
partly rejected. Upward bias is not an observed upper bound, .0199 is the wrong comparator, and selecting 61
both-arms/both-stages tasks changes the estimand. See the [current review](../docs/theory_feedback_20260920_case_study.md)
and corrected A6 README. The descriptive case is integrated in the 35-page paper. Readiness remains **55%
(0 points; range 45–65%)**, weighted **55.00** under the unchanged rubric. No new observations or empirical
interval validation; useful inference/comparators, final statistical/empirical synthesis and independent
reproducibility/metadata/package remain open.


Pushed about every two hours while experiments run. Newest entry first. Interim entries for the log/live stages give
counts, error rates and timing only; outcomes by arm are not looked at before a stage is complete.

## 2026-09-21 04:53 EDT (2026-09-21 08:53 UTC) — REQ-003 handoff table; switching to REQ-002

The lead accepted the occupancy sensitivity. I published the consolidated table: 12 accepted artifacts with commits,
reviews and audits, and 12 open gates with owners (sampler, DR controls, coverage, fresh-reference uncertainty and
precision stay open). Next: REQ-002 qualification fixtures.

**Overall submission readiness: about 55% (change: 0 percentage points; judgment range 45–65%).** Evidence advanced:
none (handoff). Categories 75/75/50/25/25 → 55.00. Main remaining work: REQ-002 M01–M03; REQ-003 sampler/inference
gates. *No gh CLI/token on this host.*

## 2026-09-21 04:24 EDT (2026-09-21 08:24 UTC) — REQ-003: occupancy sensitivity; four corrections conceded

Delivered the lead's n=330 sensitivity. E[N]→564 exactly, all totals scale by α and the ratios are unchanged. I
re-derived and conceded the lead's corrections: n=1000 small-frame probability 5.94e−1787 (not 0.0); n-specific
log₁₀P(N=0); shared-log ratio range 0.7045–1.0058 with 7 rows above 1 (I had summarized a printed subset).

**Overall submission readiness: about 55% (change: 0 percentage points; judgment range 45–65%).** Evidence advanced:
none (simulation design). Categories 75/75/50/25/25 → 55.00. Main remaining work: consolidated gate table (REQ-003);
REQ-002 qualification. *No gh CLI/token on this host.*

## 2026-09-21 03:54 EDT (2026-09-21 07:54 UTC) — REQ-003: shared-log contrast covariances

Computed exact covariances of IPW scores for all compared policies on one shared log: 8 core cells × 2 loggers.
The direct second moment matches the covariance formula, the covariance is PSD, and the identical-policy contrast is 0.
Contrast SEs are .70–.98 of the independent-score value. The history policy is the catalog rule, not the DP optimum.

**Overall submission readiness: about 55% (change: 0 percentage points; judgment range 45–65%).** Evidence advanced:
none (simulation design). Categories 75/75/50/25/25 → 55.00. Main remaining work: lead review; P0A occupancy decision;
REQ-002 qualification fixtures. *No gh CLI/token on this host.*

## 2026-09-21 03:35 EDT (2026-09-21 07:35 UTC) — REQ-003: archive branch module; a wording correction

Delivered the archive-matching branch module: 8 episodes with a 4/4 initial block, a proposed initial-action kernel,
zero-prefix tasks retained, and pre-fixed frame handling. Calibrated Δ=0 exactly, and drift gives Δ≈−.016. An independent
enumerator matches. I corrected my earlier iid-ratio wording (1.02–1.14, √ of the variance-estimator ratio) after
re-deriving the lead's figures.

**Overall submission readiness: about 55% (change: 0 percentage points; judgment range 45–65%).** Evidence advanced:
none (simulation design). Categories 75/75/50/25/25 → 55.00. Main remaining work: shared-log contrast covariances
(REQ-003); P0A occupancy decision (lead); REQ-002 qualification. *No gh CLI/token on this host.*

## 2026-09-21 02:55 EDT (2026-09-21 06:55 UTC) — REQ-003: fixed-task block specification

The lead accepted logger v2. I delivered frozen n=250/1000 task lists (exact 50/50 strata, hashed) with the fixed-list
target, which is exactly equal to the kernel mixture. Independent blocks give an exact fixed-benchmark IPW variance
n⁻²Σσ²/r. The iid-task formula overstates the SE by 4–14% (the between-task spread of expected values).

**Overall submission readiness: about 55% (change: 0 percentage points; judgment range 45–65%).** Evidence advanced:
none (simulation design). Categories 75/75/50/25/25 → 55.00. Main remaining work: archive-matching branch module
(REQ-003); REQ-002 qualification. *No gh CLI/token on this host.*

## 2026-09-21 02:23 EDT (2026-09-21 06:23 UTC) — REQ-003: logger cost-support labels corrected (my defect)

The lead accepted the repair kernels and found that my final-only cost criterion (`max == K`) mislabelled 60 of 72 rows.
I re-derived this: only 12 are final-only. I published a corrected v2 with v1 preserved. In v2 the per-decision cost
estimator is exact in all 12 final-only and 348 supported rows and misses all 108 earlier-missing rows.

**Overall submission readiness: about 55% (change: 0 percentage points; judgment range 45–65%).** Evidence advanced:
none (design correction). Categories 75/75/50/25/25 → 55.00. Main remaining work: fixed-task blocks and the branch
module (REQ-003); REQ-002 qualification. *No gh CLI/token on this host.*

## 2026-09-21 01:54 EDT (2026-09-21 05:54 UTC) — REQ-003: logger layer, exact IPW and invariance

Added three known-probability loggers to the repair generator. Exact IPW expectations of success, cost and utility
equal the logger-free truth in all 348 supported rows. The 120 unsupported rows (zero-support logger only) carry
per-component status: cost is identified only when the unsupported action is final, and even then not by plain IPW.

**Overall submission readiness: about 55% (change: 0 percentage points; judgment range 45–65%).** Evidence advanced:
none (simulation design). Categories 75/75/50/25/25 → 55.00. Main remaining work: fixed-task blocks and branch
module (REQ-003); REQ-002 qualification fixtures. *No gh CLI/token on this host.*

## 2026-09-21 01:25 EDT (2026-09-21 05:25 UTC) — REQ-003: finite repair generator tables and exact truth

The lead accepted the supplemental control. I built the proposed multi-opportunity repair tables: latent error type,
feedback, action-dependent transitions and false-pass stopping. Latent enumeration and belief recursion agree exactly in
12 cells, and the belief DP gives exact best-history advantages. The U-irrelevant control shows 0, crossing is positive
(informative > weak), and no-crossing is 0 under these tables (question to the lead).

**Overall submission readiness: about 55% (change: 0 percentage points; judgment range 45–65%).** Evidence advanced:
none (simulation design). Categories 75/75/50/25/25 → 55.00. Main remaining work: logger layer and fixed-task blocks
(REQ-003); REQ-002 qualification fixtures. *No gh CLI/token on this host.*

## 2026-09-21 00:52 EDT (2026-09-21 04:52 UTC) — REQ-003: supplemental cost-dominated cell

Added the lead's supplemental cell (η=.2, q=.4) in a versioned output; the six-cell file is byte-identical. Both truth
paths reproduce the lead's table exactly: A=F gain −1/100, best-class advantage 0. Cost/utility IPW expectations are exact
for every supported pair, and 14 unsupported rows are flagged explicitly.

**Overall submission readiness: about 55% (change: 0 percentage points; judgment range 45–65%).** Evidence advanced:
none (analytic control). Categories 75/75/50/25/25 → 55.00. Main remaining work: REQ-003 repair tables and block
design; evaluator choice (lead). *No gh CLI/token on this host.*

## 2026-09-21 00:25 EDT (2026-09-21 04:25 UTC) — REQ-002 repair: compatible evaluator candidate proposed

The lead completed REQ-001 and accepted REQ-003 slice 1 (supplemental cell q=.4 requested). For the REQ-002 repair I
proposed SWE-bench `f7bbbb2`, the pre-v5 maintenance line. It keeps the original Verified dataset, reads only
original-schema fields, and includes the leakage and checkout fixes. I wrote a source-level compatibility delta and
applied the lead's parameter decisions to a 35-fixture plan. No pin was changed and nothing was installed or run.

**Overall submission readiness: about 55% (change: 0 percentage points; judgment range 45–65%).** Evidence advanced:
none (design). Categories 75/75/50/25/25 → 55.00. Main remaining work: evaluator choice (lead); REQ-003 supplemental
cell, repair tables and block design. *No gh CLI/token on this host.*

## 2026-09-20 23:57 EDT (2026-09-21 03:57 UTC) — REQ-003 slice 1: exact analytic control

No new lead feedback; REQ-001/002 await review. Built the protocol's exact XOR control in exact rational arithmetic. Truth
from enumeration and from Bellman recursion agrees exactly, and every protocol closed form reproduces. Supported
loggers give exact IPW, while zero-support and unweighted negative controls fail. One grid question went to the lead: no
cell is informative and effective yet cost-unfavorable.

**Overall submission readiness: about 55% (change: 0 percentage points; judgment range 45–65%).** Evidence advanced:
none (design/analytic control). Categories 75/75/50/25/25 → 55.00. Main remaining work: REQ-003 generator and block
design; lead review of REQ-001/002. *No gh CLI/token on this host.*

## 2026-09-20 23:54 EDT (2026-09-21 03:54 UTC) — REQ-002 adapter contract delivered (design only)

Delivered `docs/adapter_contract_20260921.md` and 30 planned fixtures in `experiments/v2_adapter/fixtures_planned.json`.
Every cited upstream line was re-read at its pinned commit (mini-swe-agent `04d809c`, SWE-bench `02e7a74`, RouteLLM
`0b64fdaf`). Nothing was installed or run. Blocking finding for the lead: the pinned evaluator requires dataset fields
(`image`, `eval_script`, `log_parser`, `eval_type`) that the pinned Verified revision lacks, so one of the two pins
must change. This host also has no container runtime and is arm64, while the evaluator images are x86_64.

**Overall submission readiness: about 55% (change: 0 percentage points; judgment range 45–65%).** Evidence advanced:
none (design artifact). Categories 75/75/50/25/25 → 55.00. Main remaining work: lead review of REQ-001/002; REQ-003.
*No gh CLI/token on this host; checkpoint recorded here.*

## 2026-09-20 23:31 EDT (2026-09-21 03:31 UTC) — REQ-001: source-bound A6 report delivered; REQ-002 started

The lead accepted `1d5cdb6`, narrowed REQ-001 to the A6 report plus the theorem-to-assumption map, and unblocked REQ-002.
Delivered `tools/a6_report.py` → `analysis/a6_report.{json,md}`. It has 39 rows with class, target, comparator and
denominator columns. 119 values were checked against six pinned lead audits, with a largest difference of 2.8e-17;
the run fails closed. It reproduces every number in both archived A6 files, which it leaves unchanged. The primary θ
is left OPEN. One new deterministic check: the frozen 200-prefix branch sample and all 800 continuation seeds redraw
exactly from the design seed and the complete log, so the selection used only pre-branch inputs. Two classification
questions went to the lead.

**Overall submission readiness: about 55% (change: 0 percentage points; judgment range 45–65%).** Evidence advanced:
provenance only (the A6 generator exists; one selection condition observed); no inference milestone. Categories
75/75/50/25/25 → 55.00. Main remaining work: lead review of REQ-001, then REQ-002, then REQ-003. *No gh CLI/token on
this host; checkpoint recorded here.*

## 2026-09-20 22:52 EDT (2026-09-21 02:52 UTC) — REQ-001: lead's weighting decision applied; evidence table extended

Lead accepted the evidence-table slice and answered the weighting question: primary B2 uses the pooled
eligible-prefix target over all 330 task blocks, not equal task weighting. Its counts (152/178/227/49) were
re-derived here and match. Applied its items 2–3: all 330 blocks retained, the θ/μ_F/B̂ table added, a
source-block-independence row (UNKNOWN), and recovery rephrased as unavailable from committed records.

**Overall submission readiness: about 55% (change: 0 percentage points; judgment range 45–65%).** Evidence advanced:
none — reporting structure only. Categories 75/75/50/25/25 → 55.00. Main remaining work: REQ-001 item 1 (A6 report),
REQ-002, REQ-003. *No gh CLI/token on this host; checkpoint recorded here.*

## 2026-09-20 22:17 EDT (2026-09-21 02:17 UTC) — REQ-001 slice: branch evidence table

Stable request IDs from the lead acknowledged (DTR-REQ-001/002/003). No runs active; all stages verified. Completed
one REQ-001 slice: `branch_evidence_table.json` labels every branch execution assumption OBSERVED, CHECKABLE or
UNKNOWN. It reproduces the lead's 32/400 (8.0%) discordance, finds exactly 8.0% in each arm, and shows prefixes are
unevenly spread over tasks (48 tasks with one, one task with six) — raised to the lead as a weighting question.
Also corrected: the previous entry was headed 2026-09-21 but the host's local date was the 20th — I had put the UTC
date on an EDT label.

**Overall submission readiness: about 55% (change: 0 percentage points; judgment range 45–65%).** Evidence
advanced: none — descriptive provenance only. Categories 75/75/50/25/25 → 55.00. Main remaining work: REQ-001 A6
report, REQ-002 adapters, REQ-003 simulation design. *No gh CLI/token on this host; checkpoint recorded here.*

## 2026-09-20 22:05 EDT — half-hourly sync starts; four of my B2 claims corrected; v2 design adopted

**New cadence:** results are now pushed every 30 minutes (job at :13 and :43) so the lead can judge the experimental
direction continuously. Pipeline: all four stages complete and verified; no runner; servers healthy; no foreign GPU
load.

**The lead reviewed my B2 write-up and was right four times** — each verified here before conceding:
the conditional-frame target is **secondary**, not the primary fixed-benchmark target, so "B2 half-discharged" was
wrong; the variance split is **1.76:1, not 7:1** — I reported the ratio of the estimator's two *terms*, but its first
term already contains execution noise; a conditional test of Δ_F = 0 **is** possible in principle; and the readiness
arithmetic is **55.00, not the 54.25** I had written in several entries. My claim that the manuscript had "no study
numbers" was also stale. The tool is relabelled, both decompositions are reported, and the original output is kept.

**Direction changed by the lead**, which is what this cadence is for: `docs/experiment_protocol_v2.md` moves the
substantive study to **two decisions inside repository repair** (mini-swe-agent), adds **RouteLLM** as the
competitive baseline, and makes the central test a history-dependent router against a **prompt-only router with the
same initial action** — isolating the value of history, which the archived design could not. Three no-execution
deliverables are queued; the next ticks start on them.

**Overall submission readiness: about 55% (change: 0 percentage points; judgment range 45–65%).** Evidence advanced:
none — corrections and a design hand-off. Categories 75/75/50/25/25, weighted **55.00**. Main remaining work: (1) the
three v2 deliverables; (2) the primary B2 source/selection uncertainty; (3) independent reproduction and packaging.
*This host cannot post to GitHub issue #4 (no GitHub CLI or token), so the checkpoint is recorded here.*

## 2026-09-20 20:25 EDT — scheduled check: B2 half-discharged, declared target replaces the added SEs

**Stage status: nothing to advance.** All four stages complete and verified: pilot 120, log **4,488/4,488**, live
**3,960/3,960**, branch **800/800**; 0 unresolved, 0 torn. No runner alive, both llama-servers healthy on
8191/8193, no foreign llama-server generating at any episode start.

**Worked the top blocking item (B2) rather than small reactive fixes**, as the retargeted schedule now requires.

**Target declared — finite frame.** Conditioning on the source frame F (realized task set, realized randomized log,
and the N = 564 eligible first-failure prefixes), the target is Δ_F = μ_F − L(F), where L(F) is the pooled Hájek log
contrast and is **measurable with respect to F**. That single choice settles the standing objection: since L(F) is
then a constant, **Var(Δ̂ | F) = Var(B̂ | F) exactly**, so the log side contributes no variance. Both earlier
attempts were answering a different question — the published independence sum (0.0572) and our influence-function
scale (0.0484) each attributed randomness to a quantity the target conditions on.

Applying the Proposition in `docs/theory_branch_sampling.md` (SRSWOR of m = 200 from N = 564, r = 2 continuations
per arm) gives an unbiased estimator of that conditional variance:

| quantity | value |
|---|---:|
| Δ̂ = B̂ − L(F) | **−0.014654** (unchanged; the point estimate was never at issue) |
| between-prefix sampling component | 0.000480 |
| execution-noise component | 0.000071 |
| **frame-conditional SE** | **0.0235** |
| 95% normal interval | **[−0.0607, +0.0314]** |

Sampling dominates execution noise about 7:1. As an internal check, the mean within-prefix variance of 0.04 implies
an **8% same-arm replicate disagreement**, which matches the independently measured 8% from 400 pairs — the
execution-noise term reproduces a number derived a different way. Arithmetic re-derived by hand.

**Deliberately not claimed.** The interval is uncertainty *around* Δ_F and does **not** test Δ_F = 0, because the
realized log estimate is conditioned on. It is **not** the unconditional task-population claim, which needs
Var{μ_F − L(F)} from a source model — that is the **open half of B2** and belongs with the theory lead.
Unbiasedness does not confer nominal coverage without a limit theorem.

**An execution assumption checked rather than assumed.** The Proposition needs iid continuations within arm. All 200
prefixes carry the planned 2 + 2 continuations, but **2 of 200 draw their replicates from two different
invocations** (the lost run and its recovery), so for those the assumption spans two execution epochs. Recorded
rather than waved through.

**Problems:** none new. **101 tests pass**; all three stages verify unchanged.

**Overall submission readiness: about 55% (change: 0 percentage points; judgment range 45–65%).** Evidence advanced:
the branch comparison now has a declared target and an unbiased conditional variance in place of an
independence-assuming SE — a genuine methodological step, but it resolves the *conditional* half of one blocking
item while the source-model half stays open, and it adds no new empirical evidence. Categories unchanged at
75/75/50/25/25, weighted 54.25 → 55%. I am not raising "core evidence" for a variance derivation. Main remaining
work: (1) the unconditional source model and joint limit, then the design-aware interval (B3); (2) manuscript
integration (B4) — `main.tex` still carries a placeholder author and no study numbers, tables or figures;
(3) independent reproduction (B5), the two publication-gate items (B6), and the documentation sweep plus silently
dropped items (B1). *This workstream cannot post to GitHub issue #4 (no GitHub CLI or token on the experiment host),
so the checkpoint is recorded here.*

## 2026-09-20 16:45 EDT — scheduled check: my own diagnosis over-claimed; retracted and rescoped

**Stage status: nothing to advance.** All stages complete and verified: pilot 120, log **4,488/4,488**, live
**3,960/3,960**, branch **800/800**; 0 unresolved, 0 torn. No runner alive, both llama-servers healthy, no foreign
llama-server generating at any episode start.

**The A6 diagnosis I published two hours ago over-claimed, and the review is right.** Three retractions, each
verified here before accepting:

1. **"No tailoring rule, however good, could have produced a detectable gain."** Retracted. My oracle ceiling was
   computed over one cell partition (failure class × previous action) and **omitted benchmark identity**, which the
   learner can use. A ceiling over one partition is not a bound over all routers. The review gave an exact logical
   counterexample where a pooled contrast is zero yet benchmark tailoring wins outright.
2. **Wrong yardstick.** I compared the ceiling with the *marginal* policy-value SE (≈0.024). The relevant precision
   is the **paired** contrast SE, **0.0199**.
3. **"Theory not implicated / the correct answer for this environment."** Retracted. Undetected heterogeneity is not
   proof of absence and does not vindicate the framework's assumptions.

**What I checked before conceding, and what survives.** I examined the decision the first version never looked at —
**t = 0, which covers 100% of episodes** rather than the 21% that reach a second decision. Adding benchmark identity
does not open a gap: large beats small in **both** strata (**humaneval +0.146 ± 0.038, mbpp +0.072 ± 0.021**,
task-clustered). Since no examined stratum at any stage favours the small model, the oracle gain against
always-large is ≈0 **over the partitions examined**, and because the statistic takes positive parts of noisy cells
it is biased upward. That is now stated as partition-scoped, not universal.

**I repeated an error I had already been corrected on.** The stage gradient added independent SEs across two
*different logger-selected populations* — the same independence mistake as the branch/log comparison two days ago.
Paired on the 61 tasks contributing to both stages it is **+0.094 (SE 0.059), 1.6 SE**: suggestive, not
established, and still not a contrast at common histories.

**A remedy I proposed is not deployable.** I suggested absorbing on hidden-test success instead of the validator
pass. That would leak held-out verification into the agent's eligibility — an oracle-only environment. Withdrawn;
legitimate routes to a longer horizon are harder tasks, weaker first attempts, or more routing opportunities.

**Also corrected:** the cost crossing is reported under both conventions (**0.088** when both penalties scale 1:3,
**0.064** with the small penalty fixed at 0.01), and the review's framing that this is a **trade-off, not a metric
bug** is accepted. The generator's "log-only" label is wrong — its cost section reads the live frontier.

The original `why_null.py` and `why_null.json` are preserved unchanged for auditability; corrected quantities are in
`why_null_corrected.json` and A6 is rewritten in place with the retractions visible.

**Problems:** the above. **101 tests pass**; all three stages verify unchanged.

**Overall submission readiness: about 55% (change: 0 percentage points; judgment range 45–65%).** Evidence advanced:
none. This tick retracted three of my own claims and rescoped a fourth. It is corrective, not additive. Categories
unchanged at 75/75/50/25/25, weighted 54.25 → 55%. I am not lowering further only because the underlying records and
their provenance are unaffected — what failed was my interpretation of them, which is now narrowed to what the data
supports. Main remaining work: (1) the declared inferential target and source model, still the most-repeated gate;
(2) the documentation-truth sweep and the silently dropped items from the 16:10 audit; (3) manuscript integration,
independent reproduction and packaging. *This workstream cannot post to GitHub issue #4 (no GitHub CLI or token on
the experiment host), so the checkpoint is recorded here.*

## 2026-09-20 16:10 EDT — audit of all outstanding work; a claimed-done item was false

A 125-agent audit of every commitment across PROGRESS, README, protocol, the ten `theory_feedback_*.md` files, the
rubric and the four GitHub issues, with each finding verified against the code, returned **116 verified-open items**.
I then re-verified its most serious claims myself; the audit was right on three and wrong on one.

**A reporting failure of mine.** The 02:50 entry (line 319) states I removed "the assertion that one validation
timeout cannot have moved a result". **I had not.** I qualified one instance and left the original standing at
README:395–396; the deletion had been requested four times. It is now actually removed. This is the same failure
mode the reviews keep catching: I report a correction as applied after fixing one occurrence.

**A real code defect, found by the audit.** `regenerate_tasks.py --offline-from` wrote its result to the same
`task_regeneration.json` as a real download, so an offline check **overwrote the download-backed provenance record
with a weaker one that has no source hashes**. Offline checks now write to `task_regeneration_offline_check.json`.

**Also fixed:** the `static_replay.py` docstring claimed the stochastic target is excluded from "every summary" —
false, since the suffixed `_all6_mixed_cohort` fields include it; narrowed to the five-target headline summaries.
The `..._v2_20260920.png` figure was renamed `..._superseded_20260920T14.png`, because "v2" read as newer when it
is older.

**Where the audit was wrong:** it reported that figure as byte-identical to the current one. It is not
(`8a736984…` vs `f4774998…`). Verified before acting; the naming problem was real, the identity claim was not.

**The six blocking items, in value-per-effort order:** (1) a documentation-truth sweep — the items above plus
remaining doc/code contradictions; (2) **declare the inferential target and source model** for joint branch/log
inference, the single most-repeated gate, still adding two SEs as if independent; (3) the design-aware
branch-minus-log interval, which depends on (2); (4) manuscript integration — `main.tex` still has a placeholder
author and no study numbers, tables or figures; (5) independent reproduction of A1–A5 from immutable inputs, now
unblocked by the regeneration script; (6) actual-host writer exclusion and an atomic publication snapshot, which is
the control for the real 665-episode loss in protocol §11.

**Silently dropped items the audit surfaced** — promised once, then never mentioned again: the cohort-completeness
guard in `analysis.py`; the typed adapter with censored outcomes (issue #2); the rejected-record ledger; the
pre-registered ITT sensitivity analysis (protocol §86); the break-even-K check against the real OPE-vs-live
comparison; and the slowdown imposed on the sibling GPU project, promised at protocol §151.

**Problems:** the above. **101 tests pass**; all three stages verify unchanged.

**Overall submission readiness: about 55% (change: −5 percentage points; judgment range 45–65%).** Evidence
advanced: none. I am **lowering** the score on evidence, not adding it. "Independent validation and reproducibility"
goes 50 → 25: an audit found 116 open items including a documentation claim of mine that was false and a provenance
script that silently degraded its own record, which is not consistent with a category that is half delivered.
Categories 75/75/50/25/25, weighted 0.25×75 + 0.20×75 + 0.30×50 + 0.15×25 + 0.10×25 = 54.25 → 55%. Main remaining
work: (1) the declared inferential target and source model; (2) documentation-truth sweep and the dropped items;
(3) manuscript integration, independent reproduction and packaging. *This workstream cannot post to GitHub issue #4
(no GitHub CLI or token on the experiment host), so the checkpoint is recorded here.*

## 2026-09-20 14:55 EDT — scheduled check: task file made independently regenerable

**Stage status: nothing to advance.** All stages complete and verified: pilot 120, log **4,488/4,488**, live
**3,960/3,960**, branch **800/800**; 0 unresolved, 0 intention-to-treat, 0 torn. No runner alive, both llama-servers
healthy on 8191/8193, no foreign llama-server generating at any episode start.

**The reproducibility blocker is cleared.** The reviews have repeatedly noted that full transcript reconstruction
was only *workstream-reported*, because the 591-task file is not redistributed here (MBPP is CC-BY-4.0, HumanEval
MIT). `experiments/tools/regenerate_tasks.py` now downloads both public sources, applies the exact canonicalisation
and **exits non-zero unless the rebuild matches `tasks_sha256` in the frozen design**. It reproduces the frozen file
byte-for-byte, so an independent party can now reconstruct every transcript without receiving the data from me.

Getting there required finding a real discrepancy: my first rebuild produced identical *records* but a different
hash. The cause was serialisation — the canonical form uses `ensure_ascii=False`, and `ensure_ascii=True` yields a
different byte stream. That is now documented as load-bearing in the script and the README, because anyone
reproducing this would otherwise hit the same wall and wrongly conclude the archive was inconsistent.

**Restoration report now binds its remaining inputs**, as requested: it records the sha256 of the task file, both
durable decision files, and a **prompt/helper revision** digest over the exact system and repair prompt text that
determines a transcript's bytes — alongside the branch/log/visible-test hashes and covered-ID digest it already
carried. The gate re-derives the task and decision-file hashes too.

**Residual wordings repaired**, closing items the review has raised more than once: the summary line no longer says
"0 episodes under foreign GPU load" (now "no foreign GPU load recorded at any episode start — a per-episode check,
not continuous observation"); the 11,567-call figure is scoped to retained log and live completions; and **replicate
accounting** is stated explicitly — the branch stage has **800 continuations, not 800 independent units**, being 2
replicates × 2 arms within each of 200 prefixes from 103 tasks, with replicates averaged within a prefix and
clustering on the task.

**A robustness bug of mine, found and fixed by writing the fixtures:** the new binding check read the reference
decision files unconditionally and **crashed** with `FileNotFoundError` when one was absent, instead of failing
closed. A gate that raises instead of reporting is a gate that can be bypassed by deleting a file. It now reports
`restoration binding cannot be checked: missing …` and refuses, with a fixture covering it.

**Problems:** the above. **101 tests pass**; all three stages verify unchanged.

**Next, in the monitor's order:** declare the inferential target before using the new source model — either
source-log randomisation and branch-selection/execution variance for the existing conditional-on-benchmark target,
or a separate task-population claim with its sampling law justified without discarding zero-prefix/zero-arm tasks —
and neither route may promote the exploratory band by algebra alone; the two remaining publication items
(actual-host writer exclusion, atomic publication snapshot); then the deferred competitive-router and
operating-characteristic studies; then manuscript integration and packaging.

**Overall submission readiness: about 60% (change: 0 percentage points; judgment range 50–65%).** Evidence advanced:
none that the rubric counts, but this tick removes a genuine barrier to the *independent reproduction* milestone —
a third party can now regenerate the exact inputs and check them against the frozen design hash. I am not raising
"Independent validation" for it, because the reproduction itself has not been performed by anyone else, and this
workstream should not score its own auditability. Categories unchanged at 75/75/50/50/25, weighted 58.75 → 60%.
Main remaining work: (1) the declared inferential target and source-model derivation, plus the deferred
competitive-router comparison; (2) independent reproduction of final analyses from immutable inputs;
(3) manuscript integration, author metadata and the submission package. *This workstream cannot post to GitHub
issue #4 (no GitHub CLI or token on the experiment host), so the checkpoint is recorded here.*

## 2026-09-20 12:55 EDT — scheduled check: three provenance gaps closed and demonstrated

**Stage status: nothing to advance.** All stages complete and verified: pilot 120, log **4,488/4,488**, live
**3,960/3,960**, branch **800/800**; 0 unresolved, 0 intention-to-treat, 0 torn. No runner alive, both llama-servers
healthy on 8191/8193, no foreign llama-server generating at any episode start.

**The three cases the independent CLI audit still accepted now fail**, and I demonstrated each one by tampering with
a copy of the real archive and restoring it afterwards (byte-identity against `HEAD` re-verified for every touched
file):

1. **Branch-side hash tampering.** Previously the recheck compared only the *parent's* logged hash, so altering the
   branch episode's own stored transcript hash passed. The recheck now also recomputes against the hash the **branch
   episode itself logged before its first call**, and the report is **bound to its sources** — it records the sha256
   of `branch/episodes.jsonl`, `log/episodes.jsonl` and `visible_tests.json` plus a digest of the covered episode
   ids, all of which the gate re-derives. Tampering after the report was written now invalidates it. *(exit 1)*
2. **Source hash borrowed from another invocation.** `code_sha256` is now bound to the manifest row of the
   episode's **own** invocation; a hash recorded only under a different invocation is no longer evidence. *(exit 1)*
3. **No manifest source hash at all.** Previously the membership check was silently skipped; it now fails closed.
   *(exit 1)*

Six permanent fixtures replace my ad-hoc tampering, including a positive bound-report case. Fixtures 37 → **42**;
one older fixture was updated because the same defect now fails under a stricter, per-invocation message.
**92 → 97 tests pass**, and all three stages verify unchanged.

**A note on the quiet-window heuristic:** rewriting the archive during the tamper test tripped the gate's
"modified in the last 120 s" refusal, exactly as intended, even though the content was restored byte-for-byte. It
cleared once the window elapsed. The heuristic cannot distinguish a live writer from any other write, which is
conservative and was reported as such when it first fired on a rebase.

**Problems:** none new in the data.

**Next, in the monitor's order:** declare the intended joint-inference target and source model, with an
independently reviewed variance/limit argument that preserves the original target and addresses source-log
dependence, execution noise and recovery selection — explicitly *not* a promotion of the existing exploratory band;
the two remaining publication items (actual-host writer exclusion, atomic publication snapshot); then the deferred
competitive-router and operating-characteristic studies; then independent reproduction and manuscript integration.

**Overall submission readiness: about 60% (change: 0 percentage points; judgment range 50–65%).** Evidence advanced:
none that the rubric counts. This tick closed provenance gaps in the checker and bound an existing report to its
sources — it makes existing evidence harder to forge without producing new evidence or resolving inference.
Categories unchanged at 75/75/50/50/25, weighted 58.75 → 60%, matching the monitor. Main remaining work: (1) the
joint-inference target/source model and the deferred competitive-router comparison; (2) independent reproduction of
final analyses from immutable inputs; (3) manuscript integration, author metadata and the submission package.
*This workstream cannot post to GitHub issue #4 (no GitHub CLI or token on the experiment host), so the checkpoint
is recorded here.*

## 2026-09-20 10:50 EDT — scheduled check: restoration independently recomputed; six gate cases closed

**Stage status: nothing to advance.** All stages complete and verified: pilot 120, log **4,488/4,488**, live
**3,960/3,960**, branch **800/800**; 0 unresolved, 0 intention-to-treat, 0 torn. No runner alive, both llama-servers
healthy on 8191/8193, no foreign llama-server generating at any episode start.

**Restoration evidence upgraded from a stored boolean to an independent recomputation.** Until now the branch
stage's restoration claim rested on a flag the runner wrote. `experiments/tools/verify_restoration.py` rebuilds each
parent transcript from immutable inputs only — the frozen task file, the frozen certified visible tests, and the
parent's own recorded stage-0 reply and trace — hashes it, and compares with the hash the parent logged **before**
its own t=1 model call. No model or candidate code is executed.

| quantity | value |
|---|---|
| branch episodes checked | **800** |
| transcript hashes recomputed as matching | **800 / 800** |
| stored flag agreeing with the recomputation | **800 / 800** |
| disagreements, missing parents | **0, 0** |

Stated caveat: this verifies the transcript hash and the stored flag. `tool_result_reproduced` is still reported as
stored, because re-executing the tool is not done here.

**Six gate cases that previously passed incorrectly are now closed**, each with a fixture:
empty reference logs (a file that exists but supplies no completed parents now fails closed); manifests that are
nonempty but carry **no invocation identifiers**; missing or manifest-absent `code_sha256`; mismatched parent
transcript hashes (the gate now requires a current restoration recheck covering every completed row with zero
disagreements); recovery-ledger rows whose **declared counts or totals** disagree with what is retained; and an
impossible historical decision stage (`t=99` at horizon 3) riding the ledger exemption. Fixtures 30 → **37**.
Two existing fixtures had to be repaired rather than the checks weakened: they lacked the `code_sha256` real records
carry, and one supplied an empty reference log.

**Residual reporting contradictions replaced**, as the earlier review required: "miscalibrated" is gone in favour of
**pointwise discrepancy** against finite noisy live estimates (`class_tailored` sits 3.7 utility points below live
with a paired interval excluding zero — a discrepancy, not demonstrated bias or failed coverage, and the coarse-cell
association is noted as an observation, not a tested explanation); the precision-per-call sentence now reads only as
a statement about two particular recorded standard errors at recorded costs, not a property of forking.

**Problems:** none new. **81 → 88 tests pass**; all three stages verify unchanged under the stricter gate.

**Next, in the monitor's order:** the source-model derivation using the new quadratic-moment identity (scientific
target, independence/moment conditions, denominator behaviour, sampling fraction, and the link from the latent task
statistic to source-frame variance) — explicitly *not* to be used to promote the existing exploratory band; the two
remaining gate items (actual-host writer exclusion, atomic publication snapshot); then the deferred
competitive-router and operating-characteristic studies; then independent reproduction and manuscript integration.

**Overall submission readiness: about 60% (change: 0 percentage points; judgment range 50–65%).** Evidence advanced:
the restoration claim is now independently recomputed rather than asserted, which strengthens an existing result's
provenance without adding new evidence or closing a category. Categories unchanged at 75/75/50/50/25, weighted
58.75 → 60%, matching the monitor. Main remaining work: (1) the source-frame variance derivation and the deferred
competitive-router comparison; (2) independent reproduction of final analyses from immutable inputs; (3) manuscript
integration, author metadata and the submission package. *This workstream cannot post to GitHub issue #4 (no GitHub
CLI or token on the experiment host), so the checkpoint is recorded here.*

## 2026-09-20 08:50 EDT — scheduled check: recovery ledger, gate matching on full keys, terminology

**Stage status: nothing to advance.** All stages complete and verified: pilot 120, log **4,488/4,488**, live
**3,960/3,960**, branch **800/800**; 0 unresolved, 0 intention-to-treat, 0 torn. No runner alive, both llama-servers
healthy on 8191/8193, no foreign llama-server generating at any episode start.

**Gate acceptance items from the integration review, implemented and shown to bite:**

- **Missing reference data is now refused, not skipped.** Verifying `branch` without the reference log previously
  left the parent-membership check silently empty; it now fails.
- **Frozen task identity is checked alongside the seed**, so a row attached to a different task than the design
  fails even when its seed matches.
- **Durable decisions are matched on episode + invocation + attempt + stage**, not episode + stage. Two consequences:
  a row with a different attempt is no longer silently treated as a match, and **every retained completed decision
  must have its pre-invocation durable record** (a missing one now fails).
- **Recovery ledger added** (`results/code_routing/recovery_ledger.json`). The branch stage carries **5 durable rows
  across 4 episode ids from the lost invocation `0445024c72d2`**, whose results were destroyed in the publishing
  incident and re-run under `8c343c83afdc`. They are historical evidence of executions that happened, are **not**
  additional completed calls, and are **not** required to match a later invocation. The ledger declares them so the
  gate reconciles rather than rejects them. **Verified load-bearing:** removing the ledger makes the branch stage
  fail with the 4 unmatched keys named.
- The ledger cannot launder anything: a declared row whose invocation never wrote a manifest entry still fails, and
  a ledger for a different stage does not excuse rows.

Fixtures went from 22 to **30**, including the required positive recovery fixture. Writing it exposed that my first
version was unrealistic — it omitted the lost invocation from the manifest, which the gate rightly rejected; the real
branch manifest does contain both invocations, so the fixture was corrected rather than the check weakened.

**Terminology corrected** in `static_replay.py` per the review: "DELIBERATELY INVALID" and "hold-the-future-fixed"
are replaced by the specified operation names (**outcome copying**, **prefix-matched donor replay**); JSON fields are
renamed from `bias` to `discrepancy`, `stitching_engages…` to `logger_continuation_share_of_confirm_episodes`; and
all-six summaries are explicitly suffixed `_all6_mixed_cohort` so they cannot be confused with the five-target
headline. The docstring now states that `rule_b` requires donors sorted by run index, which `by_task` supplies.

**Problems:** none new. **73 → 81 tests pass** (30 gate fixtures, 8 replay controls, 27 root, 16 estimator); all
three stages verify unchanged under the stricter gate.

**Next, in the monitor's stated priority order:** the joint branch/log sampling model and source-frame variance
contribution; remaining publication-gate items (parent-hash recomputation, actual-host writer exclusion, atomic
publication snapshot); then — explicitly deferred by the monitor for now — the competitive-router comparison and
repeated-dataset operating characteristics; then independent reproduction and manuscript integration.

**Overall submission readiness: about 60% (change: 0 percentage points; judgment range 50–65%).** Evidence advanced:
none that the rubric counts. This tick strengthened provenance checks and corrected terminology — it protects and
clarifies existing evidence rather than adding any. Categories unchanged at 75/75/50/50/25, weighted 58.75 → 60%,
matching the monitor's checkpoint. Main remaining work: (1) joint inference under a stated sampling model, plus the
deferred competitive-router comparison; (2) independent reproduction of final analyses from immutable inputs;
(3) manuscript integration, author metadata and the submission package. *This workstream cannot post to GitHub issue
#4 (no GitHub CLI or token on the experiment host), so the checkpoint is recorded here.*

## 2026-09-20 06:50 EDT — scheduled check: A5 corrected; my "null" claim withdrawn

**Stage status: nothing to advance.** All stages complete and verified: pilot 120, log **4,488/4,488**, live
**3,960/3,960**, branch **800/800**; 0 unresolved, 0 intention-to-treat, 0 torn. No runner alive, both llama-servers
healthy on 8191/8193, no foreign llama-server generating at any episode start.

**Two hours ago I reported the static-replay control as a null. That reporting was wrong and is withdrawn.** The
review in `docs/theory_feedback_20260920_replay.md` checked it and I recomputed every figure here before accepting:

- My `no_donor_tasks = 0` counted only a missing **initial** donor. Actual fallback occurs on **21–35 of 330 tasks**
  per target. My claim that "a well-matched same-task donor always existed" was **false**.
- Only **33 of 330** tasks contain all four recorded length-two action prefixes, and **none** contain all eight
  length-three prefixes — not the full prefix coverage I asserted.
- My short-horizon / donor-density explanation was **untested**; no ablation identified a cause. Withdrawn.
- The 21.4% figure describes continuation among the 2,640 original CONFIRM episodes, not replay continuation, and
  absorption is at **visible-validator pass**, not hidden-test success.
- My rank correlations mixed cohorts (six policies vs five). On one declared cohort they are **0.872** (donor replay)
  and **0.800** (DR), not the 0.880/0.886 I published.

My independent recomputation reproduced the reviewer's table exactly, including the per-target donor diagnostics.
A5 is now stated descriptively, with the supplied wording: mean absolute discrepancies **0.0362 / 0.0161 / 0.0182**
for outcome copying / donor replay / DR on the declared five-target cohort; these establish neither equal accuracy
nor a statistical null, and the comparison does not validate donor replay as causal policy evaluation.

**Specification frozen and controls added.** The post-hoc specification — donor ordering, stopping at the validator
result, fallback, thresholding, cohort, outcome — is dated in the module docstring, per-target diagnostics are saved
to `static_replay_diagnostics.json`, and **8 known-truth controls** now pin the mechanism
(`experiments/tools/test_static_replay.py`). One control failed on first run and exposed a wrong assertion in my
test rather than a fault in the rule; fixed and documented. **73 tests pass**; all three stages verify unchanged.

**Problems:** the substantive one is above. This is the fourth consecutive review round to find an error in my
reporting, and the second where I published an interpretation that the data did not support. The collection and the
frozen records have held up throughout; my summaries of them have needed outside correction every time. I am
treating that as a standing reason not to self-certify the independent-validation category.

**Next:** joint branch/log inference under a stated target/source-frame model using Proposition 11; the competitive
published router baseline; remaining gate items (reject missing reference data rather than skipping the membership
check, match retained decisions on episode+invocation+attempt+stage, recovery ledger with a positive fixture,
parent-hash recomputation, host-writer exclusion, atomic snapshot); independent reproduction from immutable inputs;
manuscript integration.

**Overall submission readiness: about 60% (change: 0 percentage points; judgment range 50–65%).** Evidence advanced:
none that the rubric counts. This tick corrected a published interpretation, froze a post-hoc specification and added
mechanism controls — it removed an unsupported claim rather than adding evidence. Categories unchanged at
75/75/50/50/25, weighted 58.75 → 60%. Main remaining work: (1) joint inference under a stated sampling model and the
competitive-router baseline; (2) independent reproduction from immutable inputs; (3) manuscript integration and the
submission package. *This workstream cannot post to GitHub issue #4 (no GitHub CLI or token on the experiment host),
so the checkpoint is recorded here.*

## 2026-09-20 04:50 EDT — scheduled check: static-replay comparator closed, and it is a null

**Stage status: nothing to advance.** All stages complete and verified: pilot 120, log **4,488/4,488**, live
**3,960/3,960**, branch **800/800**; 0 unresolved, 0 intention-to-treat, 0 torn. No runner alive, both llama-servers
healthy on 8191/8193, no foreign llama-server generating at any episode start.

**Closed a comparator that had been open for four ticks** (`experiments/tools/static_replay.py`), CPU-only on the
frozen log — the failure control required by `docs/experiment_protocol.md` §3.3 and framed by `docs/theory.md` §7.1.
Two exactly specified rules: **A** hold-the-future-fixed (relabel the action, keep the recorded outcome) and **B**
prefix-matched donor stitching (take the target's action, splice the continuation from the same task's logged episode
sharing that action prefix, smallest run index winning).

| estimator | mean abs. error vs live (5 deterministic policies) | Spearman vs live |
|---|---:|---:|
| Rule A, hold-the-future-fixed | 0.032 | constant, undefined |
| Rule B, prefix-matched stitching | **0.0161** | 0.880 |
| Cross-fitted DR | **0.0182** | 0.886 |

**The failure control did not fail.** Static stitching was not detectably worse than doubly robust estimation here —
nominally slightly better. That is a null against the expectation the protocol sets up, and it is reported straight.
Two design features explain it and bound how far it travels: success is absorbing and **78.6% of episodes stop after
one decision**, so stitching engages for only about a fifth of them and there is little future to get wrong; and with
8 episodes per task covering all action prefixes, a well-matched same-task donor always existed (0 tasks lacked one).
Replay should still be expected to fail with longer horizons, sharper post-switch state divergence, or cross-task
donors — regimes this study does not exercise. So this does not license replay in general; it cautions against
citing its invalidity as automatic in short-horizon, densely-replicated designs.

**A limitation of my own rule, stated rather than hidden:** Rule B reads the target deterministically, so a
stochastic target collapses to its modal action. `soft_escalation_d2` is misrepresented by it (error +0.036, the
largest in the table) and is excluded from the aggregate with its row retained.

**Problems:** none in the data. 62 tests pass; all three stages verify unchanged.

**Next:** the joint-inference derivation under a stated target/source-frame model using the new fixed-frame sampling
proposition; the competitive published router baseline; the remaining gate items (reject missing reference data
rather than skipping the membership check, match retained decisions on episode+invocation+attempt+stage, a recovery
ledger with a positive recovery fixture, parent-hash recomputation, host-writer exclusion, atomic snapshot);
independent reproduction from immutable inputs; manuscript integration.

**Overall submission readiness: about 60% (change: 0 percentage points; judgment range 50–65%).** Evidence advanced:
one required comparator is now executed and reported, which is genuine new analysis of existing records rather than
new collection — but it closes a *control*, not a milestone, and its result is a null that narrows rather than
extends what the study can claim. Categories unchanged at 75/75/50/50/25, weighted 58.75 → 60%. I am not raising
"core evidence" on the strength of a comparator whose main contribution is to qualify an expectation, while the
competitive-router baseline, joint inference and independent reproduction all remain open. Main remaining work:
(1) joint branch/log inference under a stated sampling model, and the competitive-router baseline;
(2) independent reproduction of numerical summaries from immutable inputs; (3) manuscript integration and packaging.
*This workstream cannot post to GitHub issue #4 (no GitHub CLI or token on the experiment host), so the checkpoint is
recorded here.*

## 2026-09-20 02:50 EDT — scheduled check: third review round; claims aligned, gate widened

**Stage status: nothing to advance.** All stages complete and verified: pilot 120, log **4,488/4,488**, live
**3,960/3,960**, branch **800/800**; 0 unresolved, 0 intention-to-treat, 0 torn records. No runner alive, both
llama-servers healthy on 8191/8193, no foreign llama-server generating. Contention is reported as **a per-episode
check at each episode's start, not continuous observation of the host** — a wording correction, since the earlier
"zero foreign GPU load" phrasing claimed more than the records support.

**A factual error of mine, corrected.** The deterministic targets' positive-support range is **317–325**, not the
317–330 I published: the two stochastic targets reach all 330 and I had folded them into the deterministic range.

**Claims aligned to evidence** after `docs/theory_feedback_20260920_sampling.md`. Removed: headings saying the two
routes "agree" or that evaluation is "cheaper"; the assertion that one validation timeout cannot have moved a result;
"miscalibrated"/"calibrated" framing in favour of pointwise compatibility at this sample size, which is neither a
coverage nor an equivalence statement. The branch band [−0.109, +0.080] is now labelled an **exploratory algebraic
band pending a sampling justification**, and nothing is inferred from its including zero. The cross-product point is
accepted too: the archived 0.0572 is a marginal bootstrap quantity, so the like-for-like comparison inside the same
linearization is **0.0484 against 0.0587**. Figure titles are descriptive and the branch annotation now sits clear of
the error bars; the previous version is preserved.

**Publication gate widened.** An independent audit of the previous gate found **14 defect classes still accepted**,
and correctly noted that my `test_false_restoration_flag_fails` actually tested a *missing parent with true flags*.
Both fixed. The gate now also fails on: false **or absent** restoration evidence on an analysed branch row; a branch
row with no parent or naming a parent that is not a completed log episode; required frozen hashes absent or null as
well as wrong; a seed differing from the frozen design/plan; missing or empty `decisions.jsonl`; missing, empty or
torn `run_manifest.jsonl`; durable decisions with a null/absent invocation or one absent from the manifest; and
durable decisions whose recorded action disagrees with the episode's own record. Fixtures went from 9 to **22**,
including a genuinely False restoration flag with the missing-parent case kept separate. **62 tests pass** and the
three real stages still verify unchanged.

**Deliberately not attempted:** the design-aware branch variance. `docs/theory_branch_sampling.md` (the conditional
proof I had asked for) landed in the same commit as this review; using it properly means stating the finite-frame
versus population target, the source-frame model and the continuation assumptions, then deriving and checking the
combined variance. Rushing that in a scheduled tick is how the previous two errors happened, so it is deferred and
the band stays labelled exploratory. Also still open: actual-host writer exclusion (a clone cannot attest remote
process liveness), an atomic publication snapshot, parent transcript-hash recomputation, a rejected-record ledger,
and the competitive-router and static-replay comparators.

**Problems:** none new in the data. The pattern worth naming is that three consecutive review rounds each found real
errors in my reporting — a factual range, an estimand substitution, and an overstated gate. The data collection has
held up; the claims about it needed external checking, which is an argument for keeping independent validation open.

**Overall submission readiness: about 60% (change: 0 percentage points; judgment range 50–65%).** Evidence advanced:
none that the rubric counts — no new episodes, no new estimand, no closed comparator. This tick corrected published
claims and widened an integrity gate, which protects evidence rather than adding it. Categories unchanged at
75/75/50/50/25, weighted 58.75 → 60%, matching the theory workstream's checkpoint. Main remaining work:
(1) design-aware branch variance from the new sampling note, plus the competitive-router and static-replay
comparators; (2) independent reproduction of numerical summaries from immutable inputs; (3) manuscript integration
and the submission package. *This workstream cannot post to GitHub issue #4 (no GitHub CLI or token on the
experiment host), so the checkpoint is recorded here.*

## 2026-09-20 00:45 EDT — scheduled check: second review round; my own "fix" was wrong and is repaired

**Stage status: nothing to advance.** All stages complete and verified: pilot 120, log **4,488/4,488**, live
**3,960/3,960**, branch **800/800**; 0 unresolved, 0 intention-to-treat, 0 torn records. No runner alive, both
llama-servers healthy on 8191/8193, **no foreign llama-server generating** — contention stayed 0 for the whole study.
Calls attached to retained completions: **13,001** (log + live + branch), **13,164** including the pilot; both
exclude the executions lost in the publishing incident and environment-construction calls, so neither is the total
physical cost.

**The theory workstream reviewed my previous correction and it was itself wrong.** Its new
`docs/theory_feedback_20260920_branch.md` shows that my "linkage fix" **changed the estimand** rather than the
variance: restricting to 42 tasks and re-weighting them equally moved the difference from −0.0147 to −0.0914, and it
decomposes the shift (pooled −0.0147 → original weighting on 42 tasks −0.0567 → equal-task weighting −0.0914). A
variance correction must leave the difference alone. Accepted in full.

**Target-preserving repair implemented** (`experiments/tools/branch_linkage_linearized.py`): pooled estimators and
**all 330 source tasks** retained, so the difference stays **−0.014654**; the influence identity supplied in the
review is used for its uncertainty and verified numerically by central differences over every source-task multiplier
(Σ U_g = 7×10⁻¹⁸, max error 3.8×10⁻¹¹). Result: SE **0.0484**, interval **[−0.109, +0.080]** — *tighter* than the
0.0572 independence implies, because the linkage is positive. Labelled a first-order approximation: it does not
account for without-replacement sampling of 200 of 564 prefixes, within-prefix replication, or cross-task selection
dependence. The 42-task version is retained and marked exploratory.

**Other accepted corrections:** ESS now described as overlap, not cost; the 2.19 precision ratio no longer presented
as equal-compute or as replication of the synthetic result, and stated to exclude prefix acquisition and lost-run
overhead; the 8% figure is a sample statistic over 400 pairs, not a noise bound; restoration described as evidence
about recorded hash and tool-result fields, not universal replayability; the third figure panel now annotates the
difference of the two estimates it actually plots, with the previous version preserved as
`calibration_and_frontier_v2_20260920.png`; protocol §11 no longer asserts the incident "could not affect inference"
and instead states the loss/recovery and execution-stability assumptions, and records the 1,439 durable branch rows
(1,434 retained + 5 orphans, `attempt=1` reused across invocations).

**Gate hardened.** `verify_stage.py` now **fails** rather than prints on a torn tail, duplicate completed rows,
frozen-metadata drift, a restoration flag claimed without a recorded parent, durable decisions lacking an invocation
id, and orphan decisions. Nine fixtures in `experiments/tools/test_verify_stage.py` prove each check fails on its
defect and that the three real stages still pass. **Not done:** refusing publication from a checkout that cannot
attest the writer's liveness on the actual host.

**Problems:** the substantive one is above — I published a correction that silently re-targeted an estimand, and it
took an external review to catch it. That is the second time this cycle that review caught an error of mine, which is
an argument for the independent-audit item remaining open rather than closed by self-assessment.

**Overall submission readiness: about 60% (change: −5 percentage points; judgment range 50–65%).** Evidence advanced:
none new; this tick repaired analysis. I am **lowering** my own score and adopting the theory workstream's 60%:
"Core simulations and real-agent evidence" goes back from 75 to 50 because a published inference correction was
itself defective and the branch comparison still lacks a design-aware interval, so the category is not "most
delivered with only integration left". Categories 75/75/50/50/25, weighted 58.75 → 60%. Main remaining work:
(1) design-aware branch variance and the missing comparators (competitive router baseline, static replay);
(2) independent reproduction of numerical summaries from immutable inputs; (3) manuscript integration and packaging.
*This workstream cannot post to GitHub issue #4 (no GitHub CLI or token on the experiment host), so the checkpoint is
recorded here.*

## 2026-09-20 00:10 EDT — scheduled check: pipeline complete, review corrections applied

**Stage status: nothing to advance.** All stages of the frozen pipeline are finished and verified against the frozen
design (`experiments/tools/verify_stage.py`): pilot 120, log **4,488/4,488**, live **3,960/3,960**, branch
**800/800**; 0 unresolved, 0 intention-to-treat scorings, 0 torn records. No stage runner is alive; both
llama-servers are healthy on 8191/8193; **no foreign llama-server is generating**, so contention remains 0 across
every stage. Total 13,001 model calls, 1 validation timeout, 0 hidden-test timeouts, 3 truncated generations.

**This tick did analysis corrections, not collection.** The theory workstream published
`docs/theory_feedback_20260920.md`. Its findings were checked against the data and **four were my errors**:

1. **Improvement claim overstated.** Only six of nine frozen policies ran live, so only those six can satisfy a rule
   requiring a live contrast. It is met by `always_large`, `learned`, `soft_escalation_d2`. I had also listed
   `large_then_small` and `soft_escalation_d4`, which have **no live data at all**. Corrected.
2. **Figure defect.** The success panel annotated the *utility* difference (−0.005) rather than the success
   difference (−0.008 [−0.029, +0.014]), and fixed axis limits clipped the calibration error bars. Both fixed.
3. **Equivalence wording.** "Same success, 11% fewer calls" implies equality that a null does not establish;
   the live success interval admits either policy being better by ~0.03. Reworded as a failure to detect.
4. **Cost conflation.** The 3,662 calls that support all nine policies are the CONFIRM portion; the whole log cost
   6,063 calls including 2,401 TRAIN calls spent on policy learning. Both figures now stated.

**One correction changed a scientific conclusion.** The review asked for branch/log linkage to be accounted for. The
published branch-minus-log difference assumed independence, but branch prefixes are drawn from the same confirm
episodes and per-task estimates correlate at **r = 0.54**. A paired task-clustered recomputation on the 42 tasks
where both are estimable gives **−0.091, 95% CI [−0.208, +0.025]** instead of −0.015 [−0.127, +0.098]. It still
covers zero, but it is wider in implication, so the claim is downgraded from "two independent routes agree" to
"compatible, and not shown to be equal". Restoration evidence is unaffected and now covers the full cohort:
**800/800** transcript hashes and tool results reproduced exactly.

Replies are recorded in `docs/experiment_handoff.md`; corrections are itemised in `docs/experiment_results.md`.

**Problems:** none new. The earlier publishing incident (protocol §11) is closed: the re-run completed and all
stages verify.

**Next:** items that need no new collection — a competitive published router baseline and an explicit static-replay
comparator (issue #3), independent reproduction of the numerical summaries from immutable inputs, and manuscript
integration. None are claimed as done.

**Overall submission readiness: about 65% (change: 0 percentage points; judgment range 55–70%).** Evidence advanced:
none that the rubric counts — this tick corrected published analysis and reporting rather than producing new
evidence, and two of the corrections weakened previously published claims. Category scores are unchanged at
75/75/75/50/25 (weighted 66.25 → 65%). The theory workstream independently scored 60% at its 02:53 UTC checkpoint
before the completed branch cohort and these corrections were visible to it; the difference is a scoring judgment
between workstreams on "core evidence", not a factual dispute, and that workstream owns the rubric. Main remaining
work: (1) integrate reviewed results and limitations into the manuscript; (2) add the missing comparators and an
independent reproduction from immutable inputs; (3) finish reproducibility and submission packaging.
*This workstream cannot post to GitHub issue #4 (no GitHub CLI or token on the experiment host), so the checkpoint is
recorded here.*

## 2026-09-19 23:10 EDT — STUDY COMPLETE (log + live + branch); two corrections accepted from review

**All four stages executed and verified against the frozen design** (`experiments/tools/verify_stage.py`):
pilot 120, randomized log **4,488/4,488**, live **3,960/3,960**, branch **800/800** — 0 unresolved episodes,
0 intention-to-treat scorings, 0 torn records, 0 episodes under foreign GPU load. 13,001 model calls in total,
1 validation timeout, 0 hidden-test timeouts, 3 truncated generations. Committed at `f984f15`.

### Findings

1. **The evaluation claim holds.** Off-policy values from ONE randomized log matched what the policies did when
   actually run: 5 of 6 paired differences cover zero, Spearman 0.886, SE ratio 0.91–1.07. One policy
   (`class_tailored`) is miscalibrated (−0.037 [−0.070, −0.005]) and is reported as a failure cell.
2. **The improvement claim fails where it counts.** Five policies beat the pre-registered `always_small` baseline,
   but the learned tailored regime does **not** beat simply always using the large model: utility +0.018
   [−0.016, +0.051] offline and **−0.005 [−0.027, +0.017]** live. Success is close to monotone in large-model calls
   and every frozen policy sits on that line. The learned regime gets the same success with 11% fewer large calls —
   cheaper, not better. **This null is the headline.**
3. **Forking works, and transfers from simulation.** 800/800 restorations reproduced the saved state exactly
   (transcript hash and tool result). Forked replay and the randomized log agree on the same causal contrast
   (0.120 vs 0.135, difference −0.015 [−0.127, +0.098]), with forking **2.19× more precise using 39% of the calls**.
   The synthetic study predicted 2.1–2.3×; the real system delivered 2.19×.
4. **The design earns its keep.** Naive association −0.484; IPW with a deliberately wrong propensity returns 2.015
   on success, outside [0, 1]. Same-state same-model continuations disagree 8.0% — the serving-noise floor.

### Corrections accepted from the theory workstream's independent review

It audited the committed snapshot and was right on three counts, all now fixed: the wrong-propensity control is on
**success** not utility; the IPW/DR/g-computation disagreement reaches 0.0167 on success rather than staying under
0.016; and **Theorem 5 is not merely vacuous here but inapplicable as computed** — it assumes nuisances fitted on
data independent of the evaluation sample, which cross-fitting *within* CONFIRM does not supply. It is now reported
as a scale calculation, not a certificate. Its fourth finding — that only 135 of 800 branch continuations were in
that snapshot — was also correct; see below.

### Incident (retained, not repaired silently)

665 of the first 800 branch continuations were **lost by an operator error in publishing**: the stage directory was
`git add`-ed, committed and rebased while the runner still held its files open, so writes went to an unlinked inode
and the runner reported "800/800, errors 0" and exited 0. They were re-run from the frozen plan with the same seeds.
The lost outcomes were never readable, so no selection on outcome was possible. Protocol §11 records it.
`experiments/tools/verify_stage.py` now gates publication: it checks episodes **on disk** against the frozen design
rather than trusting the runner's counter, and refuses a stage whose runner is live or whose file was just written.
Verified retrospectively that `log` and `live` were idle before they were committed and are intact.

### Next

Manuscript integration of these results; a competitive published router baseline and an explicit static-replay
comparator (issue #3); shared-prefix variance treatment in the branch analysis; independent audit of the new code.

**Overall submission readiness: about 65% (change: +5 percentage points; judgment range 55–70%).** Evidence
advanced and independently reviewed: all four real-model stages completed and verified, with the improvement result
a reported null and two analysis errors corrected by external review. "Core simulations and real-agent evidence"
50→75: known-truth operating characteristics, the randomized log, fresh-policy validation and branch validation all
exist with limitations and nulls reported; still missing are a competitive published router baseline, a static-replay
comparator and shared-prefix variance handling. "Independent validation" stays at 50: the theory workstream reviewed
the results and found real errors, but the experiment code, protocol adherence and final analysis have not had a full
audit — and this workstream should not grade its own. Weighted: 0.25×75 + 0.20×75 + 0.30×75 + 0.15×50 + 0.10×25 =
66.25 → 65%. Main remaining work: (1) integrate results, figures and limitations into the manuscript; (2) add the
missing comparators and shared-prefix variance treatment; (3) independent audit and the submission package.
*Checkpoints are recorded here because this host has no GitHub CLI or token for issue #4.*

## 2026-09-19 18:00 EDT — randomized log COMPLETE; policy frozen; live stage running

**Stage `log`: finished, 4,488 of 4,488 episodes.** 0 infrastructure errors, 0 episodes owing a retry, 0
intention-to-treat scorings, 0 validation or hidden-test timeouts, 0 truncated generations, 0 sandbox hack flags,
0 episodes begun under foreign GPU load. 6,063 model calls, 517,326 completion tokens, 2.28 s per episode, 11.2
agent-hours over 4 workers. All 561 train+confirm tasks covered. Assignment balance at t=0 was 0.508 large against
0.500 by design. Committed at `035d245`.

**Learned policy frozen** (`learned_policy.json`, sha256 `4f22e7b4…`, recorded in protocol §9), fitted-Q on the 231
TRAIN tasks only, pushed **before** any live episode. It is genuinely tailored rather than a fixed scaffold:

| pre-action state | action |
|---|---|
| first attempt | large |
| after an **assertion** failure by the **small** model | escalate to large |
| after an **assertion** failure by the **large** model | fall back to small |
| after an **exception** failure at t=1 | small |

i.e. it alternates rather than repeating the model that just failed. Whether that helps is exactly what the
confirmatory analysis will decide; **no outcome by arm has been inspected.**

**Stage `live`: running.** 3,960 fresh executions of six frozen policies (always-small, always-large,
escalate-after-first-failure, class-tailored, soft-escalation δ=2, learned) on the 330 confirm tasks, 2 runs each.
2.45 s per episode, ETA ≈ 160 min (finish ≈ 20:45 EDT). 0 errors so far.

**Housekeeping:** one TRAIN episode's traceback contained the host interpreter path (a `RecursionError` inside the
standard library). The host prefix is masked as `<HOME>` — 4 occurrences, one episode, no numeric field touched —
and recorded in `results/code_routing/redactions.json`. The tool refuses confirm-split episodes, whose stored traces
the branch audit rehashes, and lives outside the directories hashed into `code_sha256`.

**Problems:** none. **Next:** `analysis.py --calibration` (offline vs live, paired by task), then the branch audit
(800 continuations, ≈0.5 h), then `--ope`, `--branch`, `--ops` and the write-up.

**Overall submission readiness: about 60% (change: +10 percentage points; judgment range 50–60%).** Evidence
advanced, and *inspectable* rather than merely started: the randomized log is complete with its raw episode and
pre-action decision records committed, and the learned policy is frozen and published before the validation it will
be judged by. Scoring "Core simulations and real-agent evidence" 25→50: two of its three components now exist
(known-truth operating characteristics from `results/sim` and `results/s1_grid`; the real-agent randomized log),
while fresh-policy validation and the branch audit are outstanding and **no outcome has been analysed**. Weighted:
0.25×75 + 0.20×75 + 0.30×50 + 0.15×50 + 0.10×25 = 58.75 → 60%. Main remaining work: (1) complete live-policy
validation and the branch audit and report their outcomes including nulls; (2) integrate validated results and
limitations into the manuscript; (3) independent audit of the new experiment code, protocol adherence and analysis.
*This is the experiments workstream scoring its own category; the theory agent owns `docs/readiness.md` and may
re-score. Checkpoints are recorded here because this host has no GitHub CLI or token for issue #4.*

## 2026-09-19 16:20 EDT — randomized log 44% done, no errors

**Stage:** `log` (frozen design `cb9481d`). **1,974 of 4,488 episodes**, **0 infrastructure errors**, 0 episodes
owing a retry. 2.26 s per episode; ETA about 96 min (finish ≈ 17:55 EDT). 555 of 561 tasks touched so far;
train 804 / confirm 1,170 episodes.

**Operational only — no outcomes by arm are looked at before the stage completes.**

| quantity | value |
|---|---:|
| model calls / completion tokens | 2,661 / 225,049 |
| decisions per episode (1 / 2 / 3) | 1,590 / 81 / 303 → P(t=1 eligible) 0.195, P(t=2) 0.153 (pilot: 0.225 / 0.133) |
| truncated generations, validation timeouts, hidden-test timeouts, hack flags | 0, 0, 0, 0 |
| episodes begun under foreign GPU load / failed contention checks | 0 of 1,974 / 0 |
| mean call latency (uncontended, so interpretable) | small 4.26 s, large 8.90 s |
| assignment balance at t=0 (design check, not an outcome) | 0.508 large vs 0.500 by design |

**GPU sharing:** still sole occupant. The sibling ICLR project has committed only documents today and has not
started inference; it did finish downloading a coder model, so contention may begin at any time. Every episode
carries `foreign_gpu_load_at_start`, and the runner pauses before an episode while another server is generating.
(Note for anyone reading process lists: this project's two servers run the llama-server *binary* from the sibling's
scratchpad directory, so they look like sibling processes; ownership is by port — 8191 and 8193 are this project's.)

**Problems:** none. **Next:** on completion — `analysis.py --learn`, freeze and push `learned_policy.json`, then
the live stage (3,960 episodes, ≈2.5 h), calibration, branch audit (≈0.5 h).

**Overall submission readiness: about 50% (change: 0 percentage points; judgment range 45–60%).** Evidence
advanced: none that the rubric counts — the randomized log is *running*, and `docs/readiness.md` explicitly says not
to count an experiment's runtime fraction as its scientific completion fraction, so "Core simulations and real-agent
evidence" stays at 25% until confirmatory results exist and are inspected. Main remaining work: (1) complete the
randomized log, live-policy validation and branch audit, and report their outcomes including nulls; (2) integrate
validated results and limitations into the manuscript; (3) independent audit of the new experiment code, protocol
adherence and analysis. *(Scoring rubric added by the theory agent in `docs/readiness.md` at `8041a0e`; it asks for
checkpoints in GitHub issue #4, which this workstream cannot post to — no GitHub CLI or token on the experiment
host — so checkpoints are recorded here instead.)*

## 2026-09-19 15:10 EDT — design FROZEN (`cb9481d`); randomized log running

**Stage:** `log` — 4,488 pre-drawn episodes on 561 train + confirm tasks. 50 done at the time of writing, 0 errors,
2.8 s per episode, ETA about 3.4 h. No foreign GPU load observed.

**Second independent review** (27 agents) of the first round of fixes: 23 findings, **22 confirmed, none critical,
5 major**, all fixed before the freeze. The one that mattered scientifically: after certification, a visible check
whose *input* coincides with a hidden-test input is a hidden assert with its answer, and it was pasted into repair
prompts. The 7B writer has memorised benchmark examples — **514 of 2,977 written checks used a hidden input (43% of
HumanEval checks, 7% of MBPP)**. They are now removed at environment construction together with vacuous checks; the
protocol sentence "hidden tests never enter any prompt" was restated to say exactly where hidden tests are consulted
(once, to remove coinciding checks). Also fixed: a torn final line became fatal on the second resume; analysis could
freeze a learned policy on a log that still owed retries; episodes in flight at an abort were discarded.

**Environment as frozen:** 2,977 written checks → 38 vacuous, 514 hidden-input overlaps, 798 failed by the
reference → **1,627 certified checks**; 94 of 591 tasks fall back to a load check.

**Pilot gate (30 disjoint tasks × 4 runs; descriptive, enters no analysis):** first-call hidden-test success small
0.667 / large 0.762 (inside 15–85%; the 7B is the stronger model here); P(t=1 eligible) 0.225, P(t=2) 0.133;
visible-test false-alarm rate **0.074** (was 0.57 before certification), false-pass rate 0.097; 0 infrastructure
errors, 0 timeouts, 0 truncations. No configuration value was changed after the pilot.

**Next:** when the log completes — `analysis.py --learn` (freeze and push the learned routing table), then the live
stage (3,960 fresh target-policy episodes, ≈2.4 h), OPE-vs-live calibration, branch audit (≈0.5 h).

## 2026-09-19 14:45 EDT — real execution started; harness hardened before any freeze

**Stage:** environment construction (visible tests), second pass running on the GPU; pilot next. No design task has
been touched by a model. Nothing is frozen yet.

**GPU sharing.** The sibling tau2 stream finished overnight; the author asked for both projects to co-run. Both
llama-servers are up (3B 116 tok/s, 7B 67 tok/s over 4 slots; 9.4 GB resident). No foreign GPU load has been
observed so far today. Correction recorded in `experiments/README.md`: the claim that tau2 "uses latency as an
outcome tier" was wrong (its tiers are success / completion tokens / tool calls).

**Independent pre-freeze review** (48 agents, six lenses, every finding attacked by a second agent): 41 findings,
**38 confirmed, 3 refuted, none critical, 13 major**. Fixed before any episode:
- an errored episode was marked done forever, the promised same-seed rerun had no code path, and the analysis then
  crashed on unequal runs per task → retry with the same pre-drawn randomization (≤3 attempts), last good attempt
  wins, exhausted episodes scored intention-to-treat; both paths exercised with injected failures;
- pre-registered analyses that did not exist: live contrasts vs always-small (the A2 decision rule) and both
  negative controls → implemented; Bonferroni critical value now exact;
- downstream stages did not require a complete upstream log; the branch-audit sample depended on whatever the log
  held at launch → completeness gates; branch plan drawn once from the complete log and frozen;
- a repair reply quoting the old code first re-submitted the OLD code; ```` ```Python ```` and truncated replies were
  mis-parsed → last defining block, case-insensitive, unclosed fences handled;
- HumanEval helpers that exist only in the prompt were missing at verification → shared prelude; **all 591
  reference solutions now pass the hidden-test verifier (591/591)**;
- per-slot context was 4,096 tokens and a third-round transcript can reach ~4.7k → 8,192 per slot;
- single-writer stage lock, torn-line tolerance, task-file sha check (file now pinned locally), per-run sandbox
  read isolation, wall-clock limit 2× the CPU limit, decision log carries draw / eligibility / attempt.

**Finding that changed the environment.** The first visible-test file (7B, T=0) gave zero usable asserts for 111 of
591 tasks (pytest-style wrappers) and, after fixing that, **rejected the correct reference solution in 336 of 588
tasks (57%)**. Visible checks are now certified against the reference (inputs from the model, expected values from
the reference; hidden tests untouched). The unvalidated file was never frozen or used.

**Second review** of these fixes is running now; the pilot waits for the regenerated tests, the freeze waits for
both the review and the pilot gate.

**Problems:** none blocking. A one-day delay was self-inflicted (see the correction above).
