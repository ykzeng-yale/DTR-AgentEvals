# Experiment protocol and decision criteria

**Future-design update:** use [v2, 21 September 2026](experiment_protocol_v2.md) for newly planned studies.
This v0.1 text and all previously frozen experiments remain historical; v2 does not retrospectively preregister
old results or authorize new compute.

**Version 0.1 — 18 September 2026.** This is a prospective expansion plan, not a record that every experiment below has run. Actual completed runs, exact commands and limitations belong in [experiment_results.md](experiment_results.md). Freeze this protocol, task manifests, model artifacts and analysis choices before a confirmatory study.

## 1. Two separate questions

1. **Estimator validation:** Does an offline estimator recover the value of a prespecified policy, including calibrated uncertainty?
2. **Policy improvement:** Does a policy selected using development data improve deployment outcomes on untouched tasks?

An accurate fitted outcome model does not by itself answer the first question. A high reward in policy-training data does not answer the second. Report them separately.

## 2. Experimental ladder

| Phase | Purpose | Execution target | Completion gate |
|---|---|---|---|
| S0 | Algebra and implementation | Tiny enumerable environments and automated tests | Exact truth, policy numerator, absorption and contrast calculations pass |
| S1 | Statistical operating characteristics | 1,000 independent Monte Carlo replicates per final design cell | Bias, RMSE, coverage and Monte Carlo uncertainty reported, including failure cells |
| L0 | Open-weight feasibility | Local small-model pair; short objectively scored tool tasks | Genuine inference logs, known propensities, restored histories, model digests and successful rerun |
| L1 | Competent task benchmark | Frozen MiniWoB++/BrowserGym or mini-swe-agent environment | Nondegenerate success, correct logging, no task leakage, viable resource envelope |
| L2 | Causal calibration | Sequentially randomized logs plus fresh target-policy executions | Paired task-level discrepancy estimates with uncertainty in both offline and live values |
| L3 | Improvement study | Learned/frozen router on untouched tasks | Prespecified success/cost criterion with simultaneous or independent-selection inference |

S1 and L1–L3 are required for a substantive empirical paper. L0 is a systems feasibility check. A small pilot does not meet the later completion gates.

## 3. Known-truth simulations

### 3.1 Data-generating mechanism

Use a finite state with task difficulty, progress, recent error, remaining budget and previous configuration. Treatment changes future progress/error and hence the next routing probability. Terminal success depends on the path and resources. Implement at least one non-Markov variant in which a past failure or action has an effect not recoverable from the latest summarized state. Enumerate all paths for short horizons to obtain exact policy truth; use dynamic programming with sufficient state for longer horizons. Compare both computations where they overlap.

Make behavior selection favor the large model on difficult/error states. Include a randomized behavior with known probabilities and an observational behavior whose probabilities must be estimated. In a hidden-confounding cell, allow an unrecorded variable to influence assignment and outcomes; mark failure of causal identification explicitly.

### 3.2 Design grid

The final grid need not be a wasteful full factorial. Use a prespecified core grid and focused stress tests:

- Independent tasks $n\in\{250,1000,4000\}$; horizon $T\in\{2,5,10\}$.
- Eligible binary-action propensity floors $\epsilon\in\{0.5,0.2,0.05\}$. A separate deterministic cell illustrates nonidentification rather than regular asymptotics.
- Target policies: always-small, always-large, fixed observable switch at a prespecified turn, error-trigger escalation, frozen policy learned on separate data, odds shifts $\delta\in\{0.5,1,2,4\}$ around a fixed reference behavior.
- Nuisances: both correct, behavior correct/outcome misspecified, outcome correct/behavior misspecified, both misspecified; additional stagewise patterns only with explicit tests of the corresponding theorem conditions.
- Sparse success, model-dependent stopping, incorrect Markov compression, repeated task seeds, and frozen versus changed deployment configurations as focused sensitivity cells.

For known randomization, use the recorded probabilities as the primary analysis. Estimated propensities may be an efficiency sensitivity analysis, not a substitute for missing records.

### 3.3 Estimators and controls

| Analysis | Role and interpretation |
|---|---|
| Exact enumeration / dynamic programming | Truth oracle, never available to the fitted estimator |
| Fresh on-policy execution | Experimental reference with its own sampling uncertainty |
| Naive switched versus unswitched | Association; has no automatic policy-value interpretation |
| Static log stitching | Deliberately invalid comparator when future states change; specify exact stitching rule |
| Sequential regression / g-computation | Outcome-model-dependent estimate of a specified policy |
| Longitudinal IPW | Uses $\prod_t\pi_t(A_t\mid H_t)/g_t(A_t\mid H_t)$ |
| Self-normalized IPW | Potential variance stabilization, with finite-sample bias disclosed |
| Cross-fitted longitudinal DR | Primary offline estimator; task-level folds and inference |
| Longitudinal TMLE | Optional bounded-outcome comparison; implement with tests before claiming results |
| Appropriate history-based OPE baseline | Necessary comparison to show whether terminology alone changes anything |

Report bias, RMSE, nominal 95% interval coverage, mean interval length, unsupported estimates, numerical failures, and false positive improvement decisions. For 1,000 replicates, coverage near 95% has Monte Carlo standard error about 0.69 percentage points. Give uncertainty for the other Monte Carlo summaries using replicate variability. A 50–100 replicate development run is useful but not a final coverage study.

For each policy, report stage-specific and terminal weight maxima/quantiles, effective sample size $(\sum_iw_i)^2/\sum_iw_i^2$, fraction of zero policy matches, and number of independent contributing tasks. ESS is a diagnostic, not a substitute for assumptions or a universal validity threshold. Report unclipped estimates first; predeclared clipped estimates are a sensitivity analysis with a changed estimating equation and possible bias.

## 4. Actual open-weight experiments

### 4.1 Models and harnesses

L0 uses available local open-weight models, pinned by artifact digest with the model-card license recorded. Record model size as a descriptor, not evidence that one model is stronger on the task. Use a common prompt and tool interface when compatible; any required model-specific formatting is part of the configuration.

For L1, choose one benchmark first:

- **Browser tasks:** [BrowserGym](https://github.com/ServiceNow/BrowserGym) supports MiniWoB++ and other browser environments. Use self-contained task instances with objective completion tests; pin browser/environment versions and reset state between runs.
- **Coding tasks:** [mini-swe-agent](https://github.com/SWE-agent/mini-swe-agent) exposes a compact agent loop suited to inserting routing before generation. Run benchmark repositories and generated commands only in isolated containers, with official verification and frozen images.

The availability and licenses of framework software, benchmark data, model weights and container images are separate. A framework being open source does not imply every bundled asset is unrestricted. Do not republish third-party datasets without checking their terms. A future tau-bench family experiment must also fix or model the user simulator; changing its model is an environment intervention.

Before the main study, use development tasks to select a model pair with meaningfully different cost profiles and nondegenerate success (provisional feasibility band 15–85% in at least one relevant arm). This is a design gate, not an exclusion rule applied after viewing confirmatory outcomes. Freeze the resulting model pair even if final results disappoint.

### 4.2 Decision rules and exploration

Use a maximum of $K$ prospective routing opportunities initially, rather than randomly changing models at every one of 50 unstructured turns. For example: start, first observable tool failure, and first recovery checkpoint, provided each trigger and eligibility rule is fully specified. Event-trigger designs evaluate policies allowed to act at those events only. They do not identify unrestricted per-turn routing.

At every eligible decision, randomize across feasible configurations with a logged probability floor, initially 0.2 when both are available. Outside an eligible decision use the prespecified continuation rule. Model selection happens before generation and before any feedback from that call. The actual RNG draw, probability vector, action feasibility, and chosen model are persisted before execution.

When a resource cap excludes an action, the probability of that action is zero. Target policies must use the same feasibility contract or the target is unsupported. API or model-loading fallbacks are recorded as treatment deviations; silently assigning the intended propensity to the fallback model invalidates the likelihood ratio. Prefer an explicit pre-action retry/availability policy and a separate infrastructure-failure outcome.

Candidate regimes:

1. Always-small; always-large, subject to the same declared cap.
2. Small then large at a fixed observable turn $k$.
3. Escalate after the first failed tool validation and continue with large.
4. Escalate after failure, return to small after two verified progress events.
5. A learned finite-depth routing tree using only pre-action features.
6. A stochastic odds-shift family around the frozen reference behavior.

Rules 3–4 must specify what happens when the trigger never occurs. A retrospectively chosen fraction of eventual trajectory length is not an online-deployable routing policy.

### 4.3 Task splits and sample sizes

Split task identifiers or repository families before execution: development/training, policy selection, and confirmatory evaluation. All seeds, branches, related task variants and task-specific training examples remain in the same partition. Reuse of a task across target-policy arms creates a paired design and can improve precision, but does not create additional independent tasks.

Use the pilot to estimate the variance of the task-level policy contrast, then calculate the final sample size from the prespecified effect and precision goal. For paired binary success differences $D_i\in\{-1,0,1\}$, the mean-difference standard error is $s_D/\sqrt m$. A two-sided 95% interval with half-width $h$ has the planning approximation $m\approx1.96^2s_D^2/h^2$; a power calculation additionally includes the chosen power quantile and must account for policy selection/multiplicity. This is a planning approximation, not a coverage guarantee at tiny samples.

As an illustration, $s_D^2=0.20$ and $h=0.05$ suggest about 308 independent tasks; the worst bound $s_D^2\le1$ gives about 1,537. These are neither observed pilot variances nor a promised budget. Add allowance for variance in the offline estimator, clustered families, and infrastructure attrition. If the benchmark is smaller, report the wider achievable precision and a benchmark-conditional target.

Compute budgets are derived from calls per trajectory × tasks × policies/seeds × token caps. Record actual measured time and memory. Local token counts are resource proxies, not dollar costs or energy. No paid inference or cloud allocation is required by the initial pilot.

### 4.4 Live validation and policy learning

Fit nuisances and learn candidate policies on development data. Lock the policy class, objective, hyperparameters and model configurations before confirmatory runs. Use either a separate selection set plus a confirmatory set or a valid simultaneous bound across the prespecified finite candidates. Reusing the same evaluation data to search indefinitely voids the fixed-policy interval interpretation.

Estimate each target policy from randomized logs and execute it independently on fresh task draws from the same distribution. For separate samples, combine offline and live variances when testing their difference. For paired tasks, estimate the covariance using task-level contributions. Ground truth from finite live rollouts is an estimate, not an exact constant.

Primary empirical output: success and resource frontier, with intervals for each policy; offline-minus-live differences; policy ranking errors; interval calibration across repeated independently generated datasets where feasible; rate of incorrectly declaring improvement. One real benchmark cannot directly establish repeated-sampling coverage from a single interval.

For learning, implement fitted-Q or an interpretable tree against full continuation value, with random, heuristic, always-small/large and a competent published routing method as baselines. A one-step conditional success regression under the behavior continuation does not solve the dynamic optimization problem.

## 5. Branch audit

Select fork histories using only available pre-action information or explicit probability sampling. Restore the environment and full transcript, then execute small and large continuations plus a same-model control. Use at least two independent continuations per arm in a subset to estimate serving noise. Common seeds can reduce variance where meaningful; identical seeds across different tokenizers do not identify an individual-level counterfactual coupling.

Define the target of a branch comparison: expected continuation effect conditional on the chosen reference-prefix distribution. It is not the value of a policy that changes how those prefixes were reached. If forks were sampled with unequal probabilities, incorporate selection weights for the stated prefix-population target.

Measure restoration fidelity using state-relevant checks (files, database state, browser state, tool outputs), not merely command exit codes. Analyze paired outcomes and action/state divergence at task level. Zero outcomes or perfect failure agreement do not demonstrate valid evaluation. Released external branches are useful for auditing and debugging; do not assume they contain sequential propensities or support arbitrary new routers.

## 6. Minimum logging contract

Persist one immutable episode manifest plus ordered decision records. These are publication-study requirements; a pilot must disclose any missing fields.

| Level | Required fields |
|---|---|
| Task | task_id, family, split, environment/image revision, initial-state identifier, verifier revision |
| Episode | episode_id, parent/fork IDs, seed, policy ID/hash, harness commit, maximum horizon and budget, start/end status |
| Before decision | time index, eligibility, transcript hash/reference, observed tool state, remaining resources, available actions, complete actual propensity vector, RNG seed/draw |
| Action | selected configuration, immutable weights/digest, tokenizer/template, decoding, context truncation, service version |
| After action | generated response, parsed tool action, tool result, validation outcome, tokens, duration, retry/fallback records, stop reason |
| Outcome | objective terminal result, verification status, cumulative costs, infrastructure failure category, censoring indicator if applicable |

Judge scores used by the router are pre-action covariates only if computed before that decision. Final answer scores cannot be leaked into earlier histories. Private credentials and real user records never belong in public logs; use synthetic/benchmark tasks and explicit output review.

## 7. Ablations and failure analyses

- Full history versus compressed state, including a compression that intentionally loses a confounder.
- Known versus fitted behavior probabilities and omitted assignment inputs.
- Randomization at every step versus a few prespecified opportunities.
- Stochastic supported targets versus deterministic aggressive switching.
- Same-family versus cross-family models; checkpoint/quantization changes studied separately.
- Objective verifier versus model judge, with judge disagreement and sensitivity reported.
- Absorbing outcomes versus incorrectly deleted terminated trajectories.
- Static replay, true branch execution and fresh whole-policy execution.
- Task-level versus incorrect trajectory-level folds and uncertainty.
- No clipping versus prespecified clipping; report the resulting bias–variance change.

## 8. Go/no-go rules and interpretation

Proceed beyond L0 only after the logging and estimator tests pass and a competent model pair is feasible. Proceed to improvement claims only after a policy is frozen and independent evaluation completed. If overlap collapses, shorten the intervention horizon or narrow the target policy family and collect new exploratory data; do not reinterpret the old study as identifying unsupported interventions.

Report null effects, reversed effects and failed calibration. The framework is useful only if it diagnoses its own invalid settings. Before submission, complete a theorem-to-code audit, independent mathematical review, dataset/license audit, and reproducibility run from the archived manifest. These are work items, not claims that external review has already occurred.
