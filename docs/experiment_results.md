# Completed experiments and their interpretation

The original result sections below were generated on 2026-09-18; later checkpoints are dated explicitly. Synthetic results, real open-weight model observations, and remaining publication work are separated. The tests establish implementation identities and numerical correctness; they do not replace statistical assumptions or benchmark validation.

**21 September 2026, 05:18 UTC supplemental review:** [accepted the additional control and component checks](theory_feedback_20260921_supplement.md)
after nine passing tests and 385 independently reconstructed exact quantities across seven cells / 35 policies.
The original six-cell output is preserved. This validates finite-model arithmetic only; no new agent observations,
Monte Carlo, coverage validation or manuscript changes follow.

**21 September 2026, exact development-control review:** the [REQ-003 slice-1 review](theory_feedback_20260921_exact_control.md)
independently reconstructs six finite-model cells / 30 policies and 258 exact quantities; all five worker tests pass.
This is deterministic analytic validation, with no model execution, Monte Carlo, coverage validation or new coding-study
outcome. One additional informative but cost-dominated control is specified separately. The 35-page manuscript is unchanged.

**Earlier scientific review, 20 September 2026:** the [lead's diagnostic report](scientific_diagnosis_20260920.md)
independently reconstructs the learned fixed large/small/large schedule, limited repair opportunities and
zero-check stopping, the unresolved class-tailored calibration discrepancy, and descriptive utility sensitivity.
These retrospective analyses narrow the empirical claims; no original outcomes, objectives or cohorts changed.
The descriptive case study is now integrated into the 35-page manuscript; useful fixed-benchmark joint inference,
remaining statistical validation and final empirical synthesis remain open. The [21:54 UTC review](theory_feedback_20260920_case_study.md)
corrects the worker's revised A6 interpretation and gives a separately reviewed, currently vacuous fixed-benchmark bound.

**Earlier review, 20 September 2026, 04:24 UTC cycle:** all 800 branch completions are now published at `d4997c6` and independently reconciled as saved records. The new 42-task analysis changes the population and weights, so uncertainty for the original full-prefix contrast remains unresolved. See [the completed-branch review](theory_feedback_20260920_branch.md). The earlier live-policy review at `ac3ca83` remains valid within its stated limits; historical snapshots below are dated explicitly.

## Worker results and status — 21 September 2026 (experiments workstream)

*Written by the worker from committed artifacts. Every number below was re-derived from the artifact files, git or test runs.
Two independent checkers reviewed a draft and raised 27 issues, all corrected here. Replies to each lead review are in
[experiment_handoff.md](experiment_handoff.md). From now on, worker commit subjects start with `worker:`, and every tick
that changes a result adds a dated entry to this section.*

**Where things stand.** There have been no new model runs since the archived coding study. Today's worker output falls
into three parts. First, the archived-report correction (DTR-REQ-001, completed). Second, static qualification tooling
for the planned SWE-bench study (DTR-REQ-002); nothing runs until the user permissions below are given. Third, exact
synthetic-design artifacts and the first sampler slices (DTR-REQ-003). **Publishing cadence:** 25 worker commits since
23:00 EDT on 20 September, all pushed to GitHub (latest before this section `e3a76c0`). The gaps between them had a
median of 29.3 minutes and a maximum of 40.1 minutes; 9 of 24 gaps exceeded 30 minutes.

### DTR-REQ-001 — archived coding study (completed; lead `8ecdfde`)
| Artifact | Result | Lead status |
|---|---|---|
| [`a6_report.md`](../results/code_routing/analysis/a6_report.md) | 39 rows in 6 analysis classes. 119 audit comparisons: 118 against six lead audits and 1 against the archived corrected JSON. Largest difference 2.8e-17. 12 tests pass | completed `8ecdfde` |
| Live whole-policy contrast (learned minus always-large) | Success −5/660 = −0.0076 (task-paired arithmetic scale 0.0110); utility −0.0050 (scale 0.0113). No validated interval | `8ecdfde` |
| Archived branch/log point | Branch 0.1200 against log 0.1347, a difference of −0.0147. Exploratory algebraic scale 0.0484, which is not an SE. The secondary realized-frame SE is 0.0235 under unverified assumptions. **No validated estimate or interval exists for the primary target Δ = θ − ν₁ + ν₀** (lead `d3425bf`); the report's `primary_target` field names θ, from the earlier decision | open (lead) |
| [`branch_evidence_table.json`](../results/code_routing/analysis/branch_evidence_table.json) | 330 task blocks; 564 eligible prefixes on 152 tasks; 200 sampled on 103; 32 of 400 same-arm fresh pairs discordant. The frozen sample redraws exactly (a6 report, `branch_plan_reproduction`) | accepted `a62ccf2` / `ac1d89e` (descriptive) |

### DTR-REQ-002 — SWE-bench v2 qualification (running; execution blocked)
| Artifact | Result | Lead status |
|---|---|---|
| [Adapter contract](adapter_contract_20260921.md) and [fixture plan](../experiments/v2_adapter/fixtures_planned.json) | Hook and field map at pinned sources; 35 planned fixtures | design accepted `8ecdfde` |
| [Evaluator selection](evaluator_compatibility_20260921.md) | SWE-bench `f7bbbb2` on SWE-bench_Verified `c104f84`. Status `selected_for_development_qualification_not_execution_qualified`; the config lists 7 open gates, including M02, whose synthetic fixtures were since accepted | selected `91c8bcc` |
| M02 test-list qualification | 29 synthetic cases pass; not yet run on the 500 real rows | accepted `d3425bf` |
| M03 strict grading and reset checker | 11 grading fixtures. In 4 of them the evaluator counts a pass that the strict rule rejects (skipped F2P or P2P; all F2P skipped, resolved vacuously; XFAIL); this comes from reading the source, not executing it. The phase-aware reset checker has 28 cases. **Strict verified resolution** is the primary endpoint | strict rule `d1d9de6`; repair accepted `6b2baca` |
| Episode endpoint mapper | Fail-closed input contract; 17 cases | accepted `0cd1fef` |

### DTR-REQ-003 — synthetic design, exact truth and samplers (running)
| Artifact | Result | Lead status |
|---|---|---|
| One-decision exact control | A=F gain over constant-0: 3/20 and 1/20 in the two informative cells with an action effect, −1/20 in the other four. Best-class advantage: 3/20, 1/20 and 0. The closed form matches enumeration in 30/30 cell×policy entries | accepted `54e1621` |
| Cost-dominated supplemental cell | A=F gain −1/100; best-class advantage 0 | accepted `4f76701` |
| Repair kernels (12 cells) | History advantage over the best fixed schedule is 0 except in the crossing cells: K=2 0.0411 / 0.0089 and K=4 0.0304 / 0.0058 (informative / weak feedback). Two truth paths agree exactly | accepted `935fabd` |
| Logger layer | 468 rows: 348 supported (IPW exact) and 120 unsupported (12 of them final-only). v1 was rejected for 60 wrong cost-support labels and is preserved | v2 accepted `c847751` |
| Fixed-task blocks | Exact SE at n=250 is 0.0169–0.0718 over all 48 rows (history rule 0.0169–0.0352). The iid-formula variance ratio is 1.0028–1.1440 (history rule 1.0195–1.1440) | accepted `dd898b5` |
| Archive branch module | Calibrated Δ = 0 exactly; the drift control gives Δ −0.0174 / −0.0154 | accepted `7e04762` |
| n=330 occupancy sensitivity | E[N] goes from 1181.4 to 564; ratios unchanged | accepted `13c1b91` |
| Shared-log contrast covariance | The contrast-SE ratio over 48 comparisons is 0.7045–1.0058, and 7 are above 1 | accepted `9d31341` |
| Fresh on-policy reference | Fresh SE at n=250 is 0.0117–0.0141. The IPW/on-policy variance ratio is 1.469–71.64, all at least 1 | accepted `6b2baca` |
| Samplers | Slice 1 accepted with a required repair (`76b3199`). The repair and the 4/4 branch sampler are at `e3a76c0`, **awaiting review** | 19 tests |

The eight synthetic-control test files have 58 passing tests; the two sampler files have 19.

### Blocked or open
- **User, two separate permissions.** (a) Download one pinned file, `data/test-00000-of-00001.parquet` (2,096,679 bytes per the Hugging Face API), from `princeton-nlp/SWE-bench_Verified@c104f84`. (b) Import and run SWE-bench `f7bbbb2` Python, limited to test-spec construction and grading parsers, in an isolated environment: no containers, no eval-script execution and no benchmark run. Both were asked in chat and recorded in the handoff; neither has been answered. They block M01, M02 on real rows and the conformance run.
- **User.** A container runtime or a qualified host for any evaluator execution. This host is arm64 with none installed.
- **Lead.** Review `e3a76c0`; the inference design for Δ; precision and resource choices.
- **Worker.** DR and outcome-regression estimators; the sampled per-decision cost estimator; variance, interval and covariance estimators; a manifest check for the branch study's analysis boundary.

### 2026-09-21 09:04 EDT — FIRST END-TO-END DEVELOPMENT RESULTS (DTR-REQ-003 P0, lead-authorized CPU batch)
[Summary table](../results/v2_sim/dev_batch_20260921/summary.md) · [summary.json](../results/v2_sim/dev_batch_20260921/summary.json) ·
[raw repetitions](../results/v2_sim/dev_batch_20260921/reps.jsonl) · manifest frozen and pushed **before** launch in `ffd0e5c`.
- **Design (protocol §7):** 4 K=2 crossing cells (informative or weak feedback × uniform-.5 or feedback-dependent-.2
  logger); the frozen 250-task list; 4 logged and 4 fresh episodes per task and policy; 3 policies (the history rule,
  the prompt rule, and fixed_LS, which was *selected using the known kernel*, not learned); root seed 2026092101.
- **Completion: 800 of 800 repetition jobs** (200 per cell), 0 failed or missing, 44.3 s wall time on 4 workers
  (169 CPU-seconds), well within the 15-minute cap. About 3.2 million simulated episodes; no model calls and no GPU.
- **IPW and fresh estimates are unbiased within Monte Carlo error.** Across all 36 bias and IPW−fresh discrepancy
  z-scores (estimate/MCSE), the largest |z| is 1.94 and none exceeds 2. Empirical sampling SDs match the accepted exact
  SDs (ratio 0.906–1.063 over 24 entries). An independent recompute from the raw file matches the summary to 3.5e-18.
- **Precision (from the table):** IPW RMSE is 0.016–0.037 depending on logger and policy, and fresh SD is about
  0.012–0.015 at 250 tasks × 4 episodes. The logger that favours large after exceptions shrinks IPW error for the
  history rule (RMSE 0.016–0.018) but inflates it for the prompt rule and fixed_LS (0.032–0.037).
- **Scope:** this is a distributional wiring check of the sampler and estimators on known kernels. It says nothing
  about interval coverage, adaptation benefit or resource efficiency. Next (lead §7): task-split DR/OR using the
  existing absorbing estimator.

### 2026-09-21 09:09 EDT — DR/OR wired to the sampler, exactly verified (DTR-REQ-003, awaiting lead review)
[`dr_bridge.py`](../experiments/v2_sim/dr_bridge.py) connects the sampler to the existing
`experiments/code_routing/estimators_absorbing.py`, which is unchanged. The observation mapping is documented: the common
first call is carried with weight 1, and the state key is the observed history only, never the latent error type.
**Exact checks by exhaustive enumeration (no Monte Carlo):**
- DR has **exactly zero bias** for 4 policies × 2 loggers × 2 strata, both with the known-kernel Q and with a deliberately
  wrong zero Q (double robustness).
- The known-kernel outcome-regression plug-in and per-decision IPW are both exact.
- The estimator's weights equal the sampler's on every branch.
- Instrumented folds show no task in both training and test.
The existing estimator's "IPW" is *per-decision* IPW, not the batch's trajectory IPW; both are unbiased, and they differ on
finite samples. Five tests; 272 pass. Next: a sampled DR/OR batch, which awaits lead authorization.

### 2026-09-21 09:49 EDT — DR/OR DEVELOPMENT RESULTS, paired on the same seeded logs (DTR-REQ-003 P0; authorized by lead `c0c39a8`)
[Summary table](../results/v2_sim/dev_batch_dr_20260921/summary.md) · [summary.json](../results/v2_sim/dev_batch_dr_20260921/summary.json) ·
[raw repetitions](../results/v2_sim/dev_batch_dr_20260921/reps.jsonl) · [OR-bias diagnosis](../results/v2_sim/dev_batch_dr_20260921/or_bias_diagnosis.json) ·
manifest frozen and pushed before launch in `34abfa6`.
- **Completion: 800 of 800 repetitions**, 24 s wall time, cap not reached. The logs are identical to the IPW batch: trajectory
  IPW reproduced with **difference 0 over all 2,400 policy-repetitions** (the lead required at most 1e-12). An
  independent recompute matches the summary exactly.
- **Fitted, task-split DR shows no bias beyond Monte Carlo error in all 12 cell×policy rows, and it is more precise than
  trajectory IPW in all 12** (RMSE ratio 0.742–0.934). The known-kernel-Q DR positive control's RMSE ratio to IPW is
  0.697–0.900. Per-decision IPW is about equal to trajectory IPW (1.006–1.019).
- **Adverse result, kept: the fitted OR plug-in is biased in one cell.** With informative feedback and the
  feedback-dependent logger it overestimates the prompt rule by +0.0082 (**z = 4.9**) and fixed_LS by +0.0045
  (z = 2.9). Its RMSE is still lower than IPW's there, 0.646–0.903 overall, because the variance is smaller.
  No other estimator/row has |z| > 2 among 84 bias and discrepancy z-scores.
- **Diagnosis (no new data; logs regenerated bit-for-bit):** first-stage outcome-model cells never fall back (that
  part of the error is exactly 0). The bias sits in the first-stage fitted values and is consistent with sparse
  **second-stage** cells, which fall back in every repetition under this logger, propagating through the iterated
  fit: about +0.007 (≈2.2 MCSE, 40 repetitions) with informative feedback and not significant with weak feedback.
  Not proven. DR is unbiased in the same cells, so identification is not implicated. A targeted confirmation is
  proposed to the lead.
- **Scope:** development check only; no coverage, adaptation or efficiency claim. Lead review pending.

### 2026-09-21 10:49 EDT — Stage-2-Q intervention on the fitted OR (retrospective oracle diagnostic; authorized by lead `9f9308e`)
[Summary](../results/v2_sim/dev_batch_or_stage2_20260921/summary.md) · [summary.json](../results/v2_sim/dev_batch_or_stage2_20260921/summary.json) ·
[incident record](../results/v2_sim/dev_batch_or_stage2_20260921/incident_20260921.json) · manifest frozen before launch in `4927dcb`.
- **Reproduction on the regenerated logs:** IPW difference 0 and standard-OR difference ≤ 3.3e-16 (acceptance 1e-12),
  across all 800 repetitions. No new random data.
- **Result:** replacing the fitted second-stage Q with the exact known-kernel Q, with the first stage fitted identically,
  removes most of the OR bias in the informative/feedback-dependent cell. For the prompt rule the error goes from +0.0082
  to +0.0009, a paired difference of −0.0074 (MCSE 0.0012, **z = −6.1**). For fixed_LS it goes from +0.0045 to +0.0013,
  a paired difference of −0.0032 (z = −2.8). Oracle-stage-2 OR has |z| ≤ 1.57 in all 12 rows; the other cells' paired
  differences are not significant. The oracle version also has lower RMSE everywhere (0.60–0.79× standard OR).
- **Conclusion allowed (lead wording):** second-stage estimation *contributes* to the fitted-OR bias in this
  implementation. This does **not** confirm sparse-cell fallback specifically, because replacing the whole second-stage
  table also changes non-fallback cells. It is an oracle intervention unavailable in deployment.
- **Incident (worker error, recovered):** I ran `git stash`/`pull` while the batch was writing its untracked
  results file. 739 of 800 records were written to a detached file and lost, unseen. Recovery was a deterministic
  resume under unchanged frozen hashes; 5 of 5 regenerated surviving records match bit-for-bit.

### 2026-09-21 10:54 EDT — M01: SWE-bench test specs built for ALL 500 real rows (DTR-REQ-002; author authorized downloads)
[summary.json](../results/v2_adapter/m01_c104f840_f7bbbb2/summary.json) · [per-instance hashes](../results/v2_adapter/m01_c104f840_f7bbbb2/instances.jsonl) ·
[reset check](../results/v2_adapter/m01_c104f840_f7bbbb2/reset_check.json) · [dependency lock](../results/v2_adapter/m01_c104f840_f7bbbb2/dependency_lock.txt)
- **Inputs:** the pinned dataset file was downloaded here; its SHA-256 `a45b1fe4…` matches upstream and the lead's
  receipt. SWE-bench `f7bbbb2` (package 4.1.0) is installed editable in an isolated project venv; its 77-package lock is recorded.
- **Qualification (M02 on real rows):** 500 of 500 eligible; 11 kept with the empty-PASS_TO_PASS limitation.
- **Test-spec construction:** 500 of 500 succeed. Every (repo, version) pair is present in the evaluator constants, no
  FAIL_ONLY repository appears, and all 500 are x86_64. Row content is unchanged by construction, and there are 500
  distinct eval scripts.
- **Repeatability:** no network fetch was needed (upstream ships cached environment files). A replay pass with the
  network replaced rebuilt all 500 byte-identically.
- **Reset check on the real generated scripts:** 500 of 500 pass, including 3 test patches that only add files (the #518
  case). The first pass flagged 3 scripts; those were **false positives from my own checker**, whose parser missed
  empty new files (`new file mode` with no `---`/`+++` lines). The parser is fixed, with a regression test.
- **Not done:** no generated script executed, no container or image, no benchmark run, no image digests. Running the
  evaluator still needs a container runtime and a qualified x86_64 host, which is a user action.

### 2026-09-21 11:16 EDT — Fixed-benchmark variance estimator wired (DTR-REQ-003 implementation; estimator only)
`sampler.within_block_variance` computes n⁻² Σ_g s_g²/r from the replicate scores within each task. An exact check over
every pair of independent logged episodes shows it is **exactly unbiased** (r = 2). It enforces the complete manifest and
needs r ≥ 2. No interval or coverage is computed or claimed; a coverage study remains the lead's decision.

### 2026-09-21 12:00 EDT — FIXED-SCORE COVERAGE RESULTS, all 12 rows (DTR-REQ-003 P0; authorized by lead `f0b4fa2`)
[Summary table](../results/v2_sim/coverage_fixed_score_20260921/summary.md) · [summary.json](../results/v2_sim/coverage_fixed_score_20260921/summary.json) ·
[raw repetitions](../results/v2_sim/coverage_fixed_score_20260921/reps.jsonl) · [run status](../results/v2_sim/coverage_fixed_score_20260921/run_status.json) ·
[independent recompute](../experiments/v2_sim/check_coverage_summary.py) · manifest frozen and pushed **before** launch in `aac1abb`.
- **Design (lead spec):** the four K=2 crossing cells, three policies, the frozen 250-task list, 4 logged and 4 fresh
  episodes per task and policy, 2,000 repetitions per cell, new root seed 2026092102 in `cov-` namespaces. IPW and fresh
  variances come from `within_block_variance` on the fixed per-episode scores, and D = IPW − fresh uses the summed
  variance. Intervals are nominal 95% Wald (z = 1.959963984540054), plus exact-variance intervals as a diagnostic, with
  exact values fixed in the manifest before the run.
- **Completion: 8,000 of 8,000 repetitions (fraction 1.0)**, 460 s wall on 4 processes, cap not reached. No failed
  intervals and no zero-variance intervals in any of the 36 row×estimand combinations. The write-loss fix was in force:
  records were written under git-ignored `work/runs/` with an exclusive writer lock, and after the writers closed, the
  atomic finalize certified 8,000 unique expected ids with 0 missing. An independent numpy recompute from the raw file
  reproduces all coverage counts and 288 summary quantities (max relative difference 4.9e-15).
- **Point estimates:** unbiased within MCSE in all 36 (largest |bias/MCSE| 1.62). The mean estimated variance matches the
  exact variance: ratio 0.987–1.003 for IPW, 0.998–1.001 for fresh and 0.989–1.002 for D. Empirical/exact variance ratio:
  0.945–1.080 overall.
- **Fresh intervals:** coverage 0.9425–0.9615 over the 12 rows (MCSE about 0.005).
- **IPW intervals undercover in some rows (unfavourable, kept):** coverage 0.9300–0.9575. Four IPW rows are more than 2
  MCSE below 0.95. Three are the prompt rule or fixed_LS under the feedback-dependent-.2 logger: 0.9300 (weak, prompt),
  0.9315 (informative, prompt) and 0.9330 (weak, fixed_LS). The fourth is 0.9400 (weak, uniform, fixed_LS).
- **D = IPW − fresh:** coverage 0.9355–0.9585, so the rejection rate at zero is 0.0415–0.0645. Two rows are more than
  2 MCSE below 0.95, both in the weak/feedback-dependent cell: fixed_LS 0.9355 and prompt 0.9375.
- **Across all 36 combinations:** 7 are outside 0.95 ± 2 MCSE, 6 below and 1 above (fresh, 0.9615). Rows share logs
  across policies, so they are not independent tests.
- **Diagnostic (for the lead to interpret):** in the same undercovering rows, exact-variance intervals cover
  0.942–0.953. The mean estimated variance there is 0.987–1.000 of the exact variance. A **post hoc** paired comparison gives Wald
  minus exact-variance coverage of −0.023 (MCSE 0.0059) in the worst row. This is consistent with the shortfall coming
  mainly from the *variability* of the r = 4 within-block variance estimate under heavy IPW weights (and its dependence
  on the estimate), not from its mean or from normality of the estimate. That mechanism is a hypothesis; it was not
  tested.
- **Scope:** a prospective synthetic check of fixed-score estimators only. It makes no DR/OR or learned-policy inference
  claim, no multiplicity-adjusted claim, no real-agent claim, and no threshold chosen after viewing the results.

### 2026-09-21 12:58 EDT — Replication-sensitivity development batch, r=4 versus r=16 (DTR-REQ-003 P0; authorized by lead `9550aa4`)
[Summary table](../results/v2_sim/replication_sensitivity_20260921/summary.md) · [summary.json](../results/v2_sim/replication_sensitivity_20260921/summary.json) ·
[raw repetitions](../results/v2_sim/replication_sensitivity_20260921/reps.jsonl) · [independent recompute](../experiments/v2_sim/check_replication_sensitivity.py) ·
manifest frozen and pushed **before** launch in `f6f450f`. The lead accepted the original validation (`b2ad9a3`),
including its undercoverage, as completed evidence. This batch is a post-design **development sensitivity** check and
changes none of the original results.
- **Design:** the two feedback-dependent-.2 cells, the three policies, n=250, 1,000 repetitions per cell and seed
  2026092103. 16 logged and 16 fresh replicates are generated per task. They are analysed as the nested first-4 block,
  with its own r=4 manifest, and as the full 16 block, on the same streams.
- **Completion:** 2,000 of 2,000 repetitions, 588 s wall on 4 processes, cap not reached; the lock/finalize step
  certified 2,000 unique ids. There are 0 failed intervals, 0 zero-variance intervals and 0 recorded errors.
- **Verification:** the numpy recompute reproduces every coverage and tail count and 324 quantities (max relative
  difference 7.6e-16). Before launch, tests showed:
  - the r=16 exact variances equal r=4/4, by exhaustive enumeration;
  - the first-4 streams are nested bit-for-bit in the 16 block;
  - the first-4 analysis matches an independently generated r=4 block.
- **The r=4 arm replicates the original pattern on a new seed.** IPW coverage for the prompt rule and fixed_LS is
  0.920–0.944, with exact-variance coverage 0.944–0.951.
- **At r=16, for those four IPW rows** (MCSE about 0.007 per row, about 0.01 for paired differences):
  - Wald coverage is 0.932–0.951.
  - The paired r16−r4 coverage difference is +0.007 to +0.021; none is individually beyond 2.2 MCSE.
  - Wald-minus-exact coverage shrinks from −0.024…−0.001 to −0.008…+0.003.
  - The variance CV roughly halves, from 0.30–0.44 to 0.15–0.23.
  - The error–variance correlation is unchanged: 0.62–0.72 at r=16, against 0.62–0.70 at r=4.
  - Lower-tail misses still exceed upper-tail misses: 0.033–0.048 against 0.008–0.020.
  - Interval length is 0.503–0.510 of the r=4 length for 4× the episodes.
- **Adverse row kept (weak / fixed_LS at r=16):** Wald coverage is 0.932 for IPW, 0.935 for fresh and 0.936 for D,
  the only r=16 entries more than 2 MCSE from 0.95. Exact-variance coverage there is 0.940 for IPW and 0.934 for
  fresh. Empirical variance is 1.08–1.11 × exact, while the estimated variance is 0.999–1.000 × exact for IPW and fresh.
- **Scope (lead wording):** any improvement is sensitivity to more execution replication (budget). It is not a
  cost-free interval repair and not an isolated variance-estimation effect. Development evidence only; interpretation
  is the lead's.

### 2026-09-21 13:47 EDT — Saved-record diagnosis of the sensitivity batch (RETROSPECTIVE, EXPLORATORY; DTR-REQ-003, authorized by lead `4570b3e`)
[Diagnosis table](../results/v2_sim/replication_sensitivity_20260921/diagnosis_retrospective.md) · [JSON](../results/v2_sim/replication_sensitivity_20260921/diagnosis_retrospective.json) ·
[code](../experiments/v2_sim/sensitivity_diagnosis.py). Inputs: the 2,000 saved records, checked against the published
hashes. No new episodes, seeds or sweeps; no repetition dropped. All 36 published Wald and exact-variance covered counts
are reproduced exactly.
- **MSE and centered variance** (separate targets; jackknife leaves one repetition out):
  - Across 36 entries, MSE/exact is 0.905–1.104 and centered variance/exact is 0.904–1.105. The bias is negligible, so
    the two nearly coincide.
  - Two entries have |z| > 2, in opposite directions, both D at r=16 in the weak cell: history 0.905 (z −2.43) and
    fixed_LS 1.102 (z +2.10).
  - Weak/fixed_LS at r=16: centered variance/exact is 1.083 for IPW (jackknife SE 0.047), 1.105 for fresh (0.054) and
    1.102 for D (0.049).
- **Tails (prompt/fixed_LS IPW, r=4):** exact-variance intervals miss more on the **upper** side, 0.027–0.040 against
  0.015–0.022 lower. The error is positively skewed at 0.196–0.336, and 8 entries have skewness above 2 jackknife SEs, all
  IPW or D at r=4. Wald intervals miss more on the **lower** side (0.037–0.066 against 0.010–0.019). At r=16, skewness
  is 0.038–0.149 and the exact-variance tails are closer to balanced (upper 0.027–0.034, lower 0.023–0.029).
- **Weak/fixed_LS, five largest squared-error contributions:** each method and r list takes 4.8–6.0% of the summed
  squared error; all are listed with their IDs and kept. One repetition stands out: **933, fresh**, at +4.88 exact SDs
  at r=16 (share 2.2%) and +3.81 at its nested r=4. This is the largest standardized error in all 24 IPW/fresh series.
  Its estimated variance is ordinary (0.93 × exact). Not interpreted.
- **Lead status:** exploratory diagnosis delivered and awaiting review. Interpretation is the lead's.

### 2026-09-21 14:17 EDT — Deterministic replay of repetitions 0, 1 and 933 (DTR-REQ-003; authorized by lead `75017a7`)
[Replay summary](../results/v2_sim/replay_integrity_20260921/summary.md) · [JSON](../results/v2_sim/replay_integrity_20260921/summary.json) ·
[code](../experiments/v2_sim/replay_integrity.py).
- **Scope:** identical replays of the saved weak/.2/fixed_LS fresh streams (seed 2026092103, original namespaces,
  250 tasks × 16 replicates plus the nested first 4). No new seed, no new episodes and no sweep.
- **Integrity:**
  - Every source hash is unchanged since the sensitivity freeze.
  - The regenerated fresh means and within-block variances (r=16 and first-4) equal the committed records **exactly**:
    absolute difference 0 on all 12 comparisons, against a tolerance of 1e-12.
  - 4,000 episodes, 4,000 unique task×replicate keys and 4,000 unique stream ids per repetition, with the correct
    namespace, policy, task and replicate fields and unique spawn keys.
  - 0 violations of utility = success − cost.
- **Repetition 933** (error +0.0334, +4.88 exact SDs, reproduced):
  - Both strata are high. Utility totals are z +3.02 easy and +3.83 hard against their exact expectations; successes
    are 1,738 against 1,688.45 expected (easy) and 1,295 against 1,210.50 (hard).
  - The deviation is spread across tasks, with 163 of 250 contributing positively. The largest single-task
    contribution, 0.00133, is similar to the two controls' maxima.
- **Controls:** repetitions 0 and 1 have errors of −1.12 and −0.25 exact SDs.
- **Lead wording:** agreement supports the integrity of these streams only, not nominal coverage, and identifier
  uniqueness does not prove independence. Repetition 933 stays in every statistic. Awaiting review.

### 2026-09-21 16:15 EDT — Honest sample-split DR: wiring and exact checks (DTR-REQ-003 P0; authorized by lead `f4db0f7`)
[Exact-check table](../results/v2_sim/honest_split_dr_20260921/exact_checks.md) · [JSON](../results/v2_sim/honest_split_dr_20260921/exact_checks.json) ·
[code](../experiments/v2_sim/honest_split_dr.py) · [tests](../experiments/tools/test_v2_honest_split_dr.py).
This is an **additional** honest-split baseline; it does not replace the earlier cross-fitted DR results. No Monte
Carlo study and no model calls.
- **Wiring:**
  - Training cohort: the frozen 250 tasks × 4. Evaluation cohort: 250 **distinct** balanced tasks × 4. Fresh
    reference: × 4. The train/eval/fresh namespaces are disjoint.
  - One observed-history Q is fitted per policy on training data only. It is then frozen, together with its fallback
    and feature map, into an immutable, hashed nuisance.
  - A per-episode DR score interface uses that frozen nuisance, keeps the common first-call term, and exposes the
    target and behaviour probabilities separately.
  - The within-task variance is computed only on the independent evaluation scores; the fresh variance is added for D.
  - Training cost is reported separately (1,000 episodes and 1,766 model calls for one fixture cohort).
- **Exact checks through the published interface:** 4 cells × 3 policies × 4 frozen-Q fixtures (known-Q oracle, zero Q,
  a specified bounded wrong Q that reaches its fallback on 9–15% of probability mass, and a Q fitted on existing
  dev-batch logs with no new seed).
  - The conditional DR mean equals the policy value to within **3.3e-16** for every fixture. This relies on known
    logging probabilities.
  - The OR plug-in is exact only for the oracle. Under the fitted Q it is off by −0.015 to +0.035.
  - The expected within-task variance estimator equals the exact conditional variance of the task-equal average to
    within 2.2e-15 relative. This relies on i.i.d. replicates given the frozen fit.
  - Conditional SE at n=250, r=4: 0.0146–0.0308 with the fitted Q.
- **Leakage and guards:**
  - Instrumented fits see only training tasks, including inside `job()`.
  - Mutating evaluation outcomes leaves every nuisance hash unchanged, and the scores still match an independent DR
    recursion.
  - Empty, duplicate and missing evaluation records fail the manifest guard.
- **Review:** an adversarial review before publication confirmed 9 findings, mostly test gaps; all are fixed. For
  example, the tests had not exercised the production variance path, and a mutated variance still passed; it now
  fails. 11 tests; 319 pass.
- **Lead status:** awaiting review. The lead owns the next coverage design.

### 2026-09-21 16:41 EDT — Honest-split DR, repeated-training coverage (DTR-REQ-003 P0; authorized by lead `3f4dfc2`)
[Summary table](../results/v2_sim/honest_split_coverage_20260921/summary.md) · [summary.json](../results/v2_sim/honest_split_coverage_20260921/summary.json) ·
[raw repetitions](../results/v2_sim/honest_split_coverage_20260921/reps.jsonl) · [independent recompute](../experiments/v2_sim/check_honest_split_coverage.py) ·
code, analysis and manifest frozen and pushed **before** execution in `4ec6831`. A development study of operating
characteristics over **repeated training and evaluation samples**, with Q refitted every repetition. It is not
coverage conditional on a fixed fit.
- **Completion:** 4,000 of 4,000 repetitions (4 cells × 1,000; seed 2026092104) in 213 s on 4 workers, within the
  900 s budget. There are 0 failed intervals, 0 zero-variance intervals and 0 recorded errors, and 1,000 distinct Q
  tables per row. A numpy recompute that does not import the batch code reproduces every coverage and tail count and
  516 quantities (max relative difference 5.3e-16).
- **DR coverage about the truth:** 0.936–0.955 over the 12 rows (MCSE ≈ 0.007). One row is more than 2 MCSE below
  0.95: informative / feedback-dependent / fixed_LS at 0.936. Misses are fairly balanced, 0.018–0.027 below and
  0.020–0.039 above. Mean estimated / empirical variance is 0.95–1.09. |bias/MCSE| ≤ 1.34.
- **DR − fresh about 0:** coverage 0.933–0.957, so the rejection rate at zero is 0.043–0.067. Two rows are more than
  2 MCSE below 0.95, both informative / feedback-dependent: prompt 0.934 and fixed_LS 0.933.
- **Paired comparator** (trajectory IPW on the same evaluation records):
  - IPW coverage is 0.931–0.964, IPW − fresh 0.943–0.956 and fresh 0.938–0.960.
  - **DR has lower MSE than IPW in all 12 rows**: MSE ratio 0.555–0.922, paired squared-error difference z from −12.1
    to −1.7.
  - Training cost is separate: about 1,000 episodes, 1,745 model calls and 25.0 cost units per repetition. This is
    not equal-budget evidence.
- **OR plug-in (descriptive):** biased again in the informative / feedback-dependent cell, by +0.0042 (z 5.0, prompt)
  and +0.0037 (z 5.2, fixed_LS), and by +0.0022 (z 2.7) for weak / feedback-dependent / prompt. There is no OR
  coverage claim.
- **Scope:** development evidence; no uniform or multiplicity-adjusted calibration claim; no cross-fitted inference
  claim. Awaiting lead review.

### Not claimed
No new model runs; Monte Carlo only on known synthetic kernels; no interval validation for DR/OR, learned policies or
the branch study; no power claim; no evidence of real-agent improvement. The
archived learned router did not beat always-large. Lead's readiness estimate (rubric in [readiness.md](readiness.md),
`76b3199`): 55%, change 0 percentage points, range 45–65%.

## Coding-study checkpoint: 19 September 2026, 22:00 UTC review cycle

At commit `035d245`, two independent internal reviewers inspected the committed randomized log: **4,488 unique episodes, 561 tasks, eight episodes per task, and 6,063 durable decision records**. TRAIN has 231 tasks / 1,848 episodes; CONFIRM has 330 tasks / 2,640 episodes, with no task overlap. Episode assignments agree with the frozen design, and no infrastructure-error episode is recorded. The learned-policy artifact is frozen and its source code uses TRAIN only. These are independently checked artifact and source-code properties, not fresh execution or independently rescored hidden-test results.

No completed live-policy or branch results are committed at this checkpoint. The subsequent workstream note at `f3aa436` reports live collection running; that stage is not independently validated here. No new model run, simulation sweep, performance ranking or fitted policy-effect estimate was produced by this review. One TRAIN episode has documented path redaction; the task source is absent from this checkout, so original transcript reconstruction and restoration remain unverified here. See the [theory feedback and analysis gates](theory_feedback_20260919.md) for the finite-certificate, completeness, restoration and shared-prefix variance issues that must be resolved before final interpretation. Earlier mock-only statements below describe their dated historical stage.

## Synthetic longitudinal evaluation

The main run used 400 independent Monte Carlo replicates, 1,500 trajectories per replicate, horizon 3, and three-fold cross-fitting. Baseline difficulty and current failure form four states. Previous model choice changes the next failure state; that state changes both future routing probabilities and future success. The terminal reward is success minus 0.06 per use of the stronger model. Known logging probabilities are bounded away from zero. Five fixed target policies were evaluated against exact Bellman values and separately generated 200,000-trajectory on-policy checks.

| Policy | Exact utility | Independent on-policy mean | Monte Carlo SE |
|---|---:|---:|---:|
| always_small | 0.315901 | 0.315930 | 0.001040 |
| always_large | 0.532492 | 0.532665 | 0.001012 |
| fixed_switch | 0.573582 | 0.574395 | 0.001030 |
| failure_escalation | 0.450386 | 0.450101 | 0.001137 |
| soft_escalation | 0.447130 | 0.447871 | 0.001129 |

`fixed_switch` at horizon 3 is small → large → large; failure-escalation selects the stronger model whenever the current failure indicator is 1. Soft escalation selects it with probability 0.1 after success and 0.9 after failure. These simulator policies are not identical to the pilot initialization rules, which start the failure policy with the small model.

With correct tabular Q models and known logging propensities:

| Policy | IPW RMSE | DR bias | DR RMSE | Nominal DR 95% coverage |
|---|---:|---:|---:|---:|
| always_small | 0.0456 | -0.0013 | 0.0409 | 0.958 |
| always_large | 0.0855 | -0.0019 | 0.0401 | 0.940 |
| fixed_switch | 0.0597 | 0.0006 | 0.0289 | 0.968 |
| failure_escalation | 0.0311 | 0.0033 | 0.0232 | 0.953 |
| soft_escalation | 0.0216 | 0.0025 | 0.0173 | 0.955 |

Nominal coverage near 0.95 has Monte Carlo SE about 0.011 with 400 replicates. Every replicate, summary and diagnostic is saved in [`results/simulation`](../results/simulation/). G-computation point estimates are provided, but no unsupported plug-in confidence intervals are fabricated. Uncertainty for its estimated Q functions was not implemented.

The misspecification experiment omits the evolving failure variable from Q fits and/or replaces the behavior probabilities by an incorrect constant 0.5. The following always-small results illustrate the estimator robustness and its limits:

| Q fit | Propensity | DR bias | DR RMSE | Nominal interval coverage |
|---|---|---:|---:|---:|
| correct | known | -0.0013 | 0.0409 | 0.958 |
| misspecified | known | -0.0013 | 0.0472 | 0.958 |
| correct | misspecified | 0.0021 | 0.0325 | 0.953 |
| misspecified | misspecified | 0.0888 | 0.0946 | 0.258 |

**Inference caveat:** with wrong propensities and consistent estimated Q fits, DR consistency does not imply validity of the empirical score-only standard error. First-order Q estimation can remain in the drift. Coverage in wrong-propensity cells is descriptive, not a claimed confidence-interval theorem. With known propensities and stable, possibly misspecified Q limits, score inference has a different and more favorable justification. The tabular backward regression implemented here claims the all-Q OR all-propensity consistency guarantee; arbitrary stagewise multiple robustness is not established for these fitted nuisances.

## Horizon and overlap stress

Each stress condition uses 200 replicates. The horizon-8 case also lowers the propensity floor from 0.15 to 0.01; evolving stage-dependent routing changes the propensity distribution. These conditions expose practical failures and do not isolate horizon from overlap effects.

| Condition | Policy | Median final-stage ESS | DR RMSE | Nominal coverage | Zero-ESS replicates |
|---|---|---:|---:|---:|---:|
| h3_n250 | always_small | 12.3 | 0.1159 | 0.885 | 0/200 |
| h3_n250 | failure_escalation | 73.2 | 0.0555 | 0.945 | 0/200 |
| h3_n250 | soft_escalation | 128.3 | 0.0416 | 0.960 | 0/200 |
| h6_n1500 | always_small | 4.0 | 0.4292 | 0.905 | 0/200 |
| h6_n1500 | failure_escalation | 88.4 | 0.0494 | 0.975 | 0/200 |
| h6_n1500 | soft_escalation | 268.4 | 0.0303 | 0.940 | 0/200 |
| h8_n1500 | always_small | 1.0 | 0.6359 | 0.860 | 97/200 |
| h8_n1500 | failure_escalation | 21.1 | 0.1107 | 0.950 | 0/200 |
| h8_n1500 | soft_escalation | 89.2 | 0.0533 | 0.950 | 0/200 |

The always-small target has median terminal ESS 1 and no target-compatible terminal trajectories in 97/200 horizon-8 replicates. Its DR RMSE is approximately 0.636 and nominal coverage is 0.86. Correct identification and nuisance specification do not create information where practical trajectory overlap is absent. Stochastic targets help here but are different interventions; they are not interchangeable replacements for unsupported deterministic policies.

![Simulation overview](../results/figures/simulation_overview.png)

## Honest policy selection

A separate 300-replicate simulation selected from the five prespecified policies using 750 training trajectories, then evaluated the selected policy with 1,500 independent trajectories. Mean training optimism was 0.0196; independent evaluation bias was -0.0017, RMSE 0.0342, and nominal coverage 0.940. Mean regret relative to the best policy in this finite menu was 0.0115. The mean true utility gain over always-small was 0.2462 in this constructed environment. This is a demonstration of honest evaluation, not evidence that an actual LLM router has been improved.

Selection counts: `{'always_small': 0, 'always_large': 81, 'fixed_switch': 218, 'failure_escalation': 1, 'soft_escalation': 0}`. Raw results: [`results/policy_learning`](../results/policy_learning/).

## Actual open-weight local-model pilots

Ollama 0.21.2 ran Qwen2.5 0.5B and 1.5B locally on an Apple M2 Max with 32 GB memory. Both selected model cards specify Apache-2.0 weights ([0.5B license](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct/blob/main/LICENSE), [1.5B license](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct/blob/main/LICENSE)). Registry manifests, full model metadata and exact content digests are saved. No upstream Hugging Face source commit is claimed to have been recovered from the quantized registry artifact.

Each trajectory has three model decisions. The logger chooses the large model with probability 0.5 initially, then 0.75 after failure and 0.25 after success. Model history is transferred intact. The validator supplies truthful correctness feedback; after failure it reveals one partial multiplication result. The final endpoint is last-stage correctness. All stages execute, including after success, so switching can spoil an earlier correct answer. Four deterministic policies were run prospectively on evaluation tasks that are disjoint from logging tasks within each run.

The resource proxy is 0.01 per small call and 0.03 per large call; it is not dollars or energy. Recorded token counts and wall times are separate measurements. Loading/caching and task order affect timing. Every raw prompt, response, probability, seed, reward and model digest is retained.

| Pilot | Logged trajectories | Prospective policy trajectories | Actual model calls | Correct stage answers | Purpose/result |
|---|---:|---:|---:|---:|---|
| 1: modular, answer-only | 32 | 48 | 240 | 5/240 | Severe floor effect |
| 2: products, answer-only | 64 | 96 | 480 | 1/480 | Severe floor; retained irrelevant mod definition |
| 3: products, reasoning enabled | 32 | 48 | 240 | 194/240 | Exploratory harness calibration |

The first two pilots had zero final successes under every prospective policy. The second reused the answer-only scaffold and retained an irrelevant definition of mod. Both failures are preserved rather than removed. The third enabled explicit arithmetic reasoning in an unexecuted JSON string and removed the irrelevant definition. Prompt and task changes were driven by observed feasibility results, so these are not prespecified confirmatory experiments.

Some small-products task seeds are reused across the second and third calibrations. Within-run logging/evaluation separation holds, but these samples are not a fresh confirmation after harness selection. A publication study requires newly generated tasks disjoint from all calibration data.

Third-pilot direct prospective outcomes:

| Regime | Final successes | Mean proxy utility | Median trajectory wall seconds |
|---|---:|---:|---:|
| logging | 24/32 | 0.696 | 3.78 |
| always_small | 12/12 | 0.970 | 3.87 |
| always_large | 7/12 | 0.493 | 4.78 |
| fixed_switch | 12/12 | 0.930 | 7.39 |
| failure_escalation | 12/12 | 0.970 | 3.94 |

Pilot off-policy results are especially limited by sample size:

| Target | IPW proxy utility | Terminal ESS | Target-compatible terminal trajectories |
|---|---:|---:|---:|
| always_small | 1.080 | 10.0 | 10/32 |
| always_large | 0.279 | 2.3 | 3/32 |
| fixed_switch | -0.051 | 3.0 | 3/32 |
| failure_escalation | 1.063 | 13.0 | 13/32 |

**Interpretation:** these small pilot samples cannot establish policy superiority or validate asymptotic intervals. One first-pilot target had no compatible terminal trajectories; the summary explicitly flags it. Prospective differences can be noisy, and estimated importance-weight values need not lie in the outcome range. Paired task bootstrap intervals are supplied only as exploratory descriptions, without multiplicity adjustment or small-sample guarantees. No Q or DR result is fit to these tiny, high-dimensional model histories.

The raw-log audit reparses outputs and checks action probabilities, action/model alignment, model digests, stage order, previous correctness, exact reference answers, reward/cost identities, terminal outcomes and within-run task separation. All response content is treated as untrusted text. The collector currently persists events after each complete trajectory; it is not a durable pre-action or crash-safe production logger.

## Verification and remaining scope

The test suite checks complete path enumeration for IPW and both DR robustness branches, the necessity of the target-policy numerator, exact truth against independent policy simulation, reproducibility, positivity validation, strict response parsing, arithmetic answers, sequential feedback, and no reference answer in the initial fixture prompt. Additional theory tests verify finite-difference influence-function identities and the exact drift identity. All 16 tests passed in the final run before reporting.

See [`experiment_handoff.md`](experiment_handoff.md) for runnable commands, metadata interpretation, inference limitations, and concrete publication-scale follow-up. All completed runs are available under [`results`](../results/); none should be labeled a completed external-benchmark study.

An independent final-source rerun repeated all 400 main simulation replicates. The replicate table, summary, exact-truth/on-policy check and diagnostic files were byte-identical to the archived outputs, despite the recorded NumPy versions differing (2.4.1 versus 2.5.3). The [reproduction record](../results/reproduction_check.json) includes output and code hashes. This verifies this run; it is not a guarantee across arbitrary software/hardware changes.

## Experiments workstream: design-efficiency simulation (added 18 September 2026)

*Written by the experiments agent; synthetic evidence only. Full write-up, table, figure and limitations: [`experiments/README.md`](../experiments/README.md). Raw replicates, manifest (seed, arguments, code sha256) and summary: [`results/sim/`](../results/sim/).*

Run: `experiments/sim/run_sim.py --reps 1000 --ci-reps 200 --workers 4` — 5,000 Monte Carlo replicates (1,000 at each of n = 300, 600, 1,200, 2,400, 4,800 episodes), 1,359 s on an Apple M5. The generator is a separate two-stage coding-agent simulator (`experiments/sim/synth_agent.py`) with truth from 400,000-task on-policy rollouts. Three base rates are calibrated to a real 591-task MBPP+HumanEval run; **the treatment-effect mechanism is planted, not observed.**

Observed: (i) IPW and cross-fitted AIPW bias at most 0.0014; task-cluster bootstrap 95% intervals covered 0.925–0.960 over 200 replicates per cell (Monte Carlo SE about 0.015). (ii) At equal total episodes, one sequentially randomized experiment estimated each of 12 embedded scaffolds with 1.67–1.72× lower RMSE than one arm per scaffold, and the scaffold it picked had lower true regret at every n (0.0017 vs 0.0072 at n = 4,800). (iii) A Q-learned tailored regime beat the best fixed scaffold in 41.5% / 62.8% / 81.6% / 91.1% / 94.8% of replicates at the five sample sizes; **at n = 300 it was worse on average.** (iv) At equal compute, forked replay of all feasible rescue arms reduced the variance of a stage-2 contrast by 2.1–2.3×.

Limitations: one mechanism, two stages, no misspecification/drift/weak-overlap cells, exact simulated state restoration. The efficiency factor in (ii) is specific to 12 regimes sharing a 2×2×3 randomization; it is not a general constant. This run does not use `src/dtr_agent_evals/simulator.py` and does not replace the S1 grid in the protocol.

As of this **18 September** entry, the code-routing study on real open-weight models (ladder L1–L3) was **implemented and dry-run with a mock model only**. The dated 19 September checkpoint above supersedes that execution status; it does not convert these synthetic results into real-agent evidence.

## Experiments workstream: S1 crossed grid on the reference simulator (added 18 September 2026)

*Written by the experiments agent; synthetic evidence only. Tables: [`results/s1_grid/grid_report.md`](../results/s1_grid/grid_report.md); interpretation and caveats: [`experiments/README.md`](../experiments/README.md#s1--crossed-grid-on-the-reference-simulator-s1_grid).*

Run: `experiments/s1_grid/run_grid.py --workers 4 --replicates 1000`, which calls the unchanged `scripts/run_simulation.py` once per cell with configs in `configs/s1_grid/` (seed 20260918, n ∈ {250, 1000, 4000} × horizon ∈ {2, 5, 10} × overlap floor ∈ {0.5, 0.2, 0.05}, five policies, four nuisance specifications, 200,000-episode on-policy truth check). 27 of 27 cells completed; no numerical failures; no clipping.

Observed, with known propensities and correct tabular Q: mean DR 95% coverage over policies was 0.94–0.95 at horizon 2, 0.92–0.95 at horizon 5, and 0.76–0.95 at horizon 10; the worst single policy at horizon 10 under confounded logging covered 0.319 (n = 250) to 0.827 (n = 4,000), with DR RMSE up to 5.7 on a return bounded in about [−0.6, 1]. Uniform logging restored horizon-10 coverage to 0.934 / 0.951 at n = 1,000 / 4,000. With both nuisances misspecified mean |bias| was 0.019 / 0.049 / 0.246 at horizons 2 / 5 / 10.

Evaluation cost: on-policy evaluation with the same n episodes split across the five policies had RMSE 1.13–1.43× that of DR from one shared uniform log at horizon 2, but only 0.41–0.70× at horizon 5 and 0.07–0.21× at horizon 10. **The "lower evaluation cost" hypothesis of theory §8 is supported at horizon 2 and contradicted at horizons 5 and 10 for a five-policy class.**

Limitations: one transition law; floors 0.05 and 0.2 are nearly the same logger in this simulator because the clip rarely binds (identical cells at horizon 2), so overlap is effectively varied only as confounded-versus-uniform; non-Markov, censoring, drift and estimated-propensity cells of protocol §3.2 are not run.

## Code-routing study on open-weight models: live results reviewed 20 September 2026

*Results first published by the experiments workstream in `ac3ca83`; interpretation corrected during the 20 September theory review. Raw records, manifests and analysis CSVs remain under [`results/code_routing/`](../results/code_routing/). Protocol and freeze hashes: [`experiments/code_routing/protocol.md`](../experiments/code_routing/protocol.md). Later README/figure repairs are accepted where listed in [the completed-branch review](theory_feedback_20260920_branch.md); remaining claims and the branch comparison still need correction. This section supersedes the original stronger calibration, equivalence and combined-improvement claims.*

The published design and manifests describe Qwen2.5-3B-Instruct and Qwen2.5-7B-Instruct (Q4_K_M, llama.cpp) on MBPP-sanitized + HumanEval with hidden-test scoring in a macOS Seatbelt sandbox. The archives contain **4,488 randomized-log episodes** (561 TRAIN+CONFIRM tasks × 8) and **3,960 live episodes** (6 frozen policies × 330 CONFIRM tasks × 2). Independent checks confirm the complete live episode-ID set and task/policy/run metadata. No infrastructure errors or retries are recorded; the live records include one validation timeout and three truncated generations. These are saved-record checks, not independent reruns of hidden tests, sandbox execution or model serving.

**Offline–live agreement is mixed descriptive evidence.** Independently reconstructed task-paired means, standard errors and intervals agree with the saved calibration table. Five of six nominal 95% utility-difference intervals include zero; this does not establish equivalence, calibrated confidence-interval coverage or the absence of bias. `class_tailored` has a nominal discrepancy of −0.0372 (95% interval −0.0695 to −0.0049), which warrants investigation. No causal explanation for it is established, and the six pointwise intervals are not a simultaneous calibration test. Spearman rank agreement is 0.886, and reported OPE/live standard-error ratios are approximately 0.91–1.07.

**Three policies meet the written primary utility improvement rule versus `always_small`.** `always_large`, `learned`, and `soft_escalation_d2` have positive Bonferroni OPE lower limits and positive live contrasts. `class_tailored` and `escalate_after_first_failure` do not satisfy its OPE criterion. `large_then_small` and `soft_escalation_d4` satisfy the OPE criterion only: neither has a live arm, so the required live-sign check cannot be claimed. The inference uses the stated task-level asymptotic assumptions; it is not finite-sample certification. Success is a secondary outcome.

**The secondary learned-versus-always-large comparison is inconclusive.** The utility contrast is +0.0175 (95% interval −0.0157 to +0.0507) offline and **−0.0050 (−0.0271 to +0.0171)** live. The live success contrast is **−0.0076 (−0.0292 to +0.0141)**. These intervals permit effects of either sign and establish neither superiority, equivalence nor noninferiority. The learned policy made 762 versus 858 large-model calls, an observed 11.19% reduction, with mean success 0.7091 versus 0.7167. Its total calls were higher: 880 versus 858. The resource measures and uncertain outcome differences must be reported together; “same quality” is unsupported. The policy-level success/call plot is descriptive, not a causal dose-response or proven efficient frontier.

**Resource accounting.** CONFIRM logging used 3,662 calls, TRAIN logging 2,401, and the complete randomized log 6,063. Six fresh live-policy arms used 5,504. The 3,662-versus-5,504 comparison excludes common training; adding the observed training cost to both pathways gives 6,063 versus 7,905. These are call counts for specified portions of this study, not complete end-to-end costs or a general equal-precision efficiency result. Development, test generation, fitting and branch costs must also be accounted for. Calls, tokens, latency and dollars are distinct units.

**Diagnostics and controls.** The largest disagreement among IPW, DR and g-computation is below 0.016 for utility and approximately 0.0167 for success. No fitted or held-out Q lookup requires a fallback in the checked folds. Deterministic targets have maximum weight 8 and final padded-stage ESS approximately 771–903; stochastic targets have ESS approximately 2,286–2,528 and maximum weights 1.78–2.56. These ESS values describe weighted episodes, including absorbed trajectories, not independent task counts or the third-stage risk set. Better overlap alone does not prove cheaper evaluation. The −0.484 naive association compares episodes reaching a second decision with episodes stopping after one, irrespective of model switching. The deliberately wrong-propensity estimate 2.015 is for **success**, not utility.

**The Theorem 5 output is a hypothetical scale calculation, not a valid certificate for the reported cross-fitted scores.** The values M = 48.41 and half-width approximately 18.1 use an independent-evaluation argument whose external-fit condition is not supplied by fitting Q on other CONFIRM folds. This applicability issue precedes whether the bound is useful. The asymptotic primary rule is separate. A separately evaluated TRAIN-only nuisance fit or a justified foldwise construction is needed before presenting a finite-sample certificate; a variance-adaptive replacement would require further theory.

**Branch and integration status at the earlier `ac3ca83` snapshot.** Only 135 of 800 planned branch continuations were then committed. The later completed-cohort review follows below; record completeness does not by itself resolve restoration enforcement or joint inference. Other limitations include one coding-benchmark family, one model pair, K = 3 with absorption on **visible-validator pass**, compressed tabular states, benchmark-adapted visible tests and unknown model memorization. Reference-solution certification does not establish validity for every correct candidate. One live trace is redacted; original task inputs, original unredacted bytes and host execution are not independently verified here. Results are not yet integrated into the manuscript PDF.

*(Experiments workstream, 19 September 2026, responding to the review above.)* The three corrections are accepted.
The wrong-propensity control value 2.015 is for **success**, not utility, and the IPW/DR/g-computation disagreement
reaches 0.0167 on success rather than staying below 0.016; both are fixed in `experiments/README.md`. On Theorem 5,
the review is right that applicability precedes usefulness: the reported M = 48.4 and half-width 18.1 assume
nuisances fitted on data independent of the evaluation sample, which cross-fitting **within** CONFIRM does not
supply, so the number is a scale calculation and not a certificate for the scores reported here. It is retained only
as an indication of magnitude, and the improvement decisions rest on the asymptotic Bonferroni rule. The branch
finding was also correct at the time it was written: that snapshot did contain only 135 of 800 continuations. The
cause was an operator error in publishing, not a partial run, and it is documented in protocol section 11; the
completed audit follows.

Limitations: one benchmark family, one model pair, K = 3 with absorbing success, a tabular state, and visible checks certified against reference solutions (so "no false alarms" holds for reference-equivalent code, not for every correct program). The branch audit of restored prefixes was still executing when this section was written and is reported separately.

### Completed branch cohort (workstream report, corrected in the 04:24 UTC review)

200 first-failure prefixes sampled with known probability (0.355) from the completed confirm log, transcripts restored, both models continued from the identical saved state with two fresh seeds each: 800 continuations over 103 tasks, 0 infrastructure errors.

All **800** records contain successful transcript-hash and tool-result restoration flags, and independent checks reconcile their initial prefix hashes with the recorded parents. The monitor has not independently reexecuted restoration or verified the complete runtime state. Observed disagreement between two fresh continuations of the same recorded state/model is **8.0%**; it is not a universal or irreducible noise bound.

The independently reconstructed prefix-weighted branch estimate is **0.120000**; the pooled log Hájek estimate is **0.134654**, giving **−0.014654**. The published standard errors 0.0320 and 0.0474 and the independence-based difference interval are archived outputs; no validated joint interval for the full-prefix comparison is established here. The later 42-task calculation gives −0.091440, but it retains only 98/200 sampled prefixes and 240/564 source prefixes and replaces prefix weighting with equal task weighting. It is an exploratory selected-task comparison, not a correction of the original estimate's covariance. The [review and exact ratio derivative](theory_feedback_20260920_branch.md) give the target-preserving starting point; design-aware uncertainty remains to be completed.

The claimed 2.19 variance ratio compares published estimates at **unequal recorded costs**, so it does not establish replication of an equal-compute simulation result. The 1,434 retained continuation calls are approximately 39% of the 3,662 CONFIRM-log calls, but the comparison omits prefix acquisition and unrecovered execution. Neither general efficiency nor equivalence of the two estimates is established. The target remains a first-failure continuation contrast under the logger's prefix distribution, not a whole-policy value.

The retained records report zero foreign GPU load, one validation timeout, no hidden-test timeouts and three truncated generations. There are **13,001 calls attached to retained log/live/branch episodes**, or **13,164 including the 163-call pilot**. These totals exclude environment-construction calls and unrecovered original executions; they are not total physical compute.

Protocol §11 **reports** loss of 665 original completions during publication/rebase and recovery using the same frozen IDs/seeds. The archive independently confirms preservation of 135 earlier rows and addition of 665 rows under the recovery invocation, but cannot establish the missing outcomes, their invisibility or absence of inferential impact. Five earlier durable decisions across four recovered IDs remain alongside replacement decisions; invocation must be part of the key. Zero recorded error-based retries does not mean zero repeated execution. The new publication verifier improves ID accounting but still needs torn-tail, duplicate, provenance and writer-race checks; see the review's acceptance criteria.

### Corrections to the sections above (experiments workstream, 20 September 2026)

Applied after the review in [`theory_feedback_20260920.md`](theory_feedback_20260920.md). Original records are unchanged; these are analysis and reporting corrections, made after the stages completed and before any manuscript integration.

1. **The improvement claim was overstated.** Only six of the nine frozen policies were executed live, so only those six can satisfy a rule that requires a live contrast. The rule is met by `always_large`, `learned` and `soft_escalation_d2`. `large_then_small`, `soft_escalation_d4` and `escalate_after_second_failure` have offline estimates only; the earlier text wrongly listed the first two as passing. No improvement is claimed for a policy that was never run.
2. **Equivalence wording removed.** The learned regime's failure to beat `always_large` is a failure to detect a difference, not evidence of equality: the live success interval [−0.029, +0.014] is compatible with either being better by up to about 0.03. The call-count difference (1.15 versus 1.30 large calls per episode) is descriptive of what the two policies spent, not an established causal saving at matched quality.
3. **Figure defect fixed.** The success panel annotated the *utility* difference (−0.005) instead of the success difference (−0.008 [−0.029, +0.014]), and fixed axis limits clipped the calibration intervals; limits are now data-driven.
4. **Evaluation cost separated from total collection cost.** The 3,662 calls that support all nine policies are the CONFIRM portion of the log; the complete log cost 6,063 calls, the extra 2,401 being TRAIN calls spent on policy learning rather than evaluation.
5. **Branch/log linkage repair remains incomplete (superseded by the 04:24 UTC review).** The workstream produced a paired 42-task result of **−0.091, nominal interval [−0.208, +0.025]** in `experiments/tools/linked_branch_uncertainty.py`. Independent review found that task selection and weighting changed the target. This output must be labeled exploratory and cannot replace uncertainty for the original pooled contrast. A correlation on the selected subset does not repair the full-prefix comparison.
6. **Theorem 5** remains reported as a scale calculation, not a certificate, for the applicability reason given in the earlier review.

The complete 800-continuation cohort now permits independent record reconciliation. All stored restoration flags are true; those recorded checks should remain distinct from independent runtime restoration or a claim of universal replayability.

### Target-preserving repair reviewed at `29ee443` (06:04 UTC cycle)

The new analysis correctly preserves the full pooled difference **−0.014654**. Independent reconstruction reproduces
its squared-derivative scale **0.048386**, but neither this algebra nor a derivative check validates the displayed band
as a 95% interval. The earlier 42-task result remains exploratory. The [current review](theory_feedback_20260920_sampling.md)
distinguishes the fixed-frame and population targets, checks the covariance explanation using a common calculation,
and lists remaining reporting contradictions. A new [conditional sampling proof](theory_branch_sampling.md) supplies
only the branch component of variance under explicit execution assumptions; the full source-frame/log component
remains open. No new empirical observations or model executions were added.

The publication gate now rejects several earlier defects, including torn tails and duplicate completions. However,
independent fixtures show that false/missing restoration evidence, missing metadata and incomplete invocation/decision
linkage can still pass. These are checker gaps, not new defects found in the actual saved cohort. All 19 non-analysis
code-study artifacts are byte-identical to `d4997c6`; the independent cohort audit remains a separate evidence layer.

### Reporting and gate revision reviewed at `6f92026` (07:50 UTC cycle)

No empirical numbers or raw records changed; only the reporting figure changed under the results directory.
Independent deterministic fixtures confirm that 12 of the earlier 14 publication-check bypasses now reject. Parent
hash/source identity and further isolated reference-data/linkage cases remain open, and invocation-blind matching
can reject valid historical recovery rows. The [review](theory_feedback_20260920_integration.md) records the exact
scope and remaining contradictory README/figure text. All 19 non-analysis artifacts remain unchanged. The conditional
sampling proof is now in the manuscript; this advances the theory paper without validating the empirical joint band
or inserting empirical results into the PDF.

### Static-replay comparator (reviewed 20 September 2026)

The experiments workstream executed a **post-hoc descriptive comparison** at `560135e`: Rule A copies each logged outcome for every policy; Rule B selects the same-task donor with smallest run index matching each requested action prefix, with fallback to the previous donor's eventual outcome if a later match is absent. This is an additional archived-data comparison, not closure of the protocol's planned known-truth replay validation. Rule A also differs from the manuscript's specific frozen-state reward-recomputation counterexample; see the [theory clarification](theory_replay_boundaries.md).

Independent reconstruction reproduces all saved A/B values, live means and paired standard errors. DR figures agree with the saved OPE/calibration outputs without independent refitting. Across the **same five deterministic policies**, mean absolute discrepancies against finite live estimates are **0.036212 for A, 0.016061 for B and 0.018235 for DR**. Spearman correlations are undefined for constant A, **0.872082 for B and 0.800000 for DR**. Previously reported A/rank summaries used six policies. These are observed discrepancies, not repeated-sampling bias; no comparative uncertainty test or equivalence analysis establishes a null or equal accuracy.

Zero `no_donor_tasks` means only that an initial donor exists. Later missing donors cause fallback on **21–35 of 330 tasks per deterministic target**. Only 33 tasks have all four recorded length-two prefixes, and none have all eight length-three prefixes. Absorption is at visible-validator pass; absence of a later recorded prefix alone is not structural positivity failure. The 21.36% continuation statistic concerns logger episodes, not replay donor changes. Neither short horizon nor donor density has been established as the cause of the descriptive method ordering.

Thresholding `soft_escalation_d2` produces a different, always-large replay policy. Its row is excluded consistently from these five-policy summaries and cannot evaluate the intended stochastic target. The largest absolute Rule B discrepancy is class-tailored, −0.039394; the thresholded stochastic comparison is +0.036364. The [review and reproducible audit](theory_feedback_20260920_replay.md) give per-stage donor diagnostics, exact theoretical controls and remaining acceptance criteria. Raw records and workstream analysis outputs are preserved unchanged; no empirical results have been inserted into the manuscript PDF.

### Acceptance of replay reporting repairs (20 September 2026, 11:15 UTC review)

At `8ab7fb5`, the experiments-owned A5 section now adopts the corrected five-target summaries and donor diagnostics
and withdraws the unsupported null, complete-donor-coverage and horizon-explanation claims. The new mechanics
fixtures are useful implementation checks; the independent pinned audit additionally connects the implemented rule
to exact positive/adaptive-negative known-value controls. These validate specified toy behavior and archived
arithmetic, not causal validity or relative accuracy on the benchmark. See the [response](theory_feedback_20260920_replay_integration.md).
The theory constructions are now in the 28-page paper; empirical performance results remain outside it.

### Recovery-ledger review (20 September 2026, 12:55 UTC)

At `bd1ace8`, all prior 19 non-analysis code-study artifacts are unchanged; a new recovery ledger reconciles five
historical durable rows across four episode IDs. This adds provenance documentation, not completed outcomes.
Independent checks confirm four publication-gate repairs and valid invocation-aware recovery, while empty-reference,
parent/source-hash and ledger-detail cases remain unresolved; see the [review](theory_feedback_20260920_recovery.md).
Replay CSV data and summary values are unchanged under column/key renaming. No new empirical estimate or validated
interval is reported. The separate quadratic-moment note advances the variance derivation without establishing the
source-frame sampling model or interval coverage.

### Restoration evidence review (20 September 2026, 16:08 UTC)

At `97689b9`, all 20 non-analysis artifacts remain byte-identical. Independent record checks verify all 800
branch first-decision hashes against parent stage-1 hashes and their respective invocation-specific durable
records, covering 200 prefixes across 103 tasks. The archived visible-test hash and task coverage also reconcile.
Full transcript-byte reconstruction is **reported by the workstream, not independently reproduced here** because
the frozen task input is absent locally. The new aggregate restoration report is not bound to record hashes/IDs;
three publication-gate counterexamples remain despite five accepted fixes. See the [response](theory_feedback_20260920_restoration.md).

No new observations or empirical estimates were added. The existing empirical derivative band remains exploratory.
The reviewed quadratic identity is now in the 29-page theory manuscript as Proposition 12, retaining its explicit
source-model/variance/coverage limits. Empirical performance results remain outside that PDF.

### Acceptance of report-binding repairs (20 September 2026, 17:51 UTC)

At `3f9000a`, the three previously documented checker failures reject and all 39 existing audit cases meet their
expected outcomes. The new restoration report's file hashes and covered IDs match the actual archive, whose 800
branch/parent/durable hash links still reconcile. All 20 non-analysis artifacts are unchanged. These are accepted
provenance-check repairs, not new model observations or an independently reproduced transcript reconstruction:
the frozen task input remains unavailable locally. See the [response](theory_feedback_20260920_source_model.md).

The separate source-model note gives a classical iid-task interpretation for the latent quadratic statistic
under explicit boundedness and positive-denominator assumptions. It does not validate uncertainty conditional on
the current fixed benchmark, prove consistency of the sampled statistic, or promote the exploratory empirical band.
No empirical estimates or PDF performance results changed.

### Independently reproduced task inputs and transcripts (20 September 2026, 19:34 UTC)

At `13bad73`, independent public-source regeneration reproduces the exact frozen 591-task bytes. Independently
implemented transcript reconstruction matches all 800 parent/branch/invocation-specific durable hashes, covering
200 unique prefixes across 103 tasks. The primary reviewer repeated downloads and reconstruction and reproduced
the audit report byte-for-byte. The prior local input blocker is resolved; the evidence is now independently
reconstructed transcript bytes, not only recorded hash linkage or workstream-reported success.

All 20 non-analysis artifacts and all empirical estimates are unchanged. No model, generated program or tool was
executed; hidden-test outcomes and runtime-state restoration are not independently revalidated by this procedure.
The [response](theory_feedback_20260920_reconstruction.md) records accepted reporting/checker changes and remaining
scope. The sufficient iid source-model result is now in the 31-page paper as Proposition 13, without empirical
performance results or validation of the exploratory joint band.

### Scientific correction to the concurrent post-hoc diagnosis at 4f9abe4

The [reviewed diagnosis](scientific_diagnosis_20260920.md) supersedes the original A6 interpretation. Its
.000278/0 empirical positive-part success statistics are **not oracle bounds**, utility gains or a power
calculation; they use noisy pooled-cell contrasts and logger occupancy/continuation. The code reads both log
and live summaries. The .088235 large-penalty crossing requires the small penalty to rise to .029412;
with small fixed at .01 the crossing is .064375. Stage-effect standard errors do not account for task clustering,
and the stage-gradient calculation omits covariance and compares different eligible populations.

The lead has corrected the [current A6 narrative](../experiments/README.md) and withdrawn claims that no router
could have achieved a detectable benefit, that no heterogeneity exists, or that the framework was thereby
vindicated. The observed fixed learned schedule and limited repair opportunities remain independently verified.
The original diagnostic code/output are preserved as historical artifacts with their interpretation explicitly
superseded. A future deployable stopping rule cannot consult hidden-test success. Reporting/generator corrections
are queued in the handoff; the scientific lead owns inference and design decisions.
