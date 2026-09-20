# Experiments workstream

Owner: the experiments agent (a separate Claude Code session from the theory agent). This
directory and `results/sim/`, `results/code_routing/` are written only by this workstream.
Theory, proposal, literature and the reference library under `src/` belong to the theory
agent and are not edited from here. Rules in [`AGENTS.md`](../AGENTS.md) apply.

## Status (18 September 2026)

| ID | What | Evidence layer | Status |
|---|---|---|---|
| E0 | Design-efficiency simulation: one sequentially randomized experiment vs one arm per scaffold; tailored-regime learning; forking vs randomizing at equal compute | synthetic, known truth | **executed** — 5,000 replicates, `results/sim/` |
| S1 | Crossed n × horizon × overlap-floor grid on the **reference** simulator and estimators (unchanged), 1,000 replicates × 27 cells × 4 nuisance specifications | synthetic, exact truth | **executed** — `results/s1_grid/`, report in `grid_report.md` |
| E1 | Absorbing-horizon tabular IPW / g-computation / cross-fitted DR with task-cluster inference | code + tests | **implemented**, 12 tests pass; reproduces `src/dtr_agent_evals` scores to 1e-10 on its simulator |
| L1–L3 | Code-routing study on MBPP + HumanEval, Qwen2.5-3B vs 7B, K=3 routing decisions | real open-weight inference | **executed 19 September** — 4,488 randomized + 3,960 live episodes, 0 errors. Estimator calibrated (5/6); tailoring does **not** beat always-large |
| A4 | Branch audit: 200 restored first-failure prefixes × {small, large} × 2 fresh continuations | real inference | **executed 19 September** — 800/800 restorations exact; forked replay agrees with the log and is 2.19× more precise at 39% of the calls |

The L1–L3 study below is executed on real open-weight models; E0 and S1 remain synthetic.

### Mapping to the open GitHub issues

| Issue | Covered here | Still open |
|---|---|---|
| #1 competent open-weight benchmark with randomized routing | `code_routing/`: frozen harness, two licensed open-weight artifacts, prospective randomization with the probability and draw persisted before inference, task-level splits, live always-small / always-large / escalation regimes, infrastructure failures retained | **execution in progress from 19 September**; harness is MBPP+HumanEval in a Seatbelt sandbox rather than BrowserGym / mini-swe-agent — acceptance of that deviation is question 1 in `docs/experiment_handoff.md` |
| #2 real-trace inference | `estimators_absorbing.py`: explicit eligibility and absorption, actual propensities, task identities, known-randomization odds-shift targets, task-level cross-fitting, paired contrasts with task-cluster SEs; tests for padded-vs-unpadded equivalence, target numerator (exact agreement with `src/`), and history-compression failure (plug-in biased by −0.024, DR unbiased) | typed adapter with **missing/censored outcomes**; drift and overlap failure tests against finite truth (the S1 grid below covers overlap/horizon on the reference simulator only); nothing here is sequentially-DR or TMLE and it is not labelled as such |
| #3 independent confirmatory study | `analysis.py --calibration` (offline vs fresh whole-policy executions, paired by task, ranking agreement, calls spent) and `--branch` (controlled live branches with shared-prefix dependence handled by task-cluster SEs) | a **competitive published sequential-router baseline**; an explicit **static-replay** comparator; false-improvement-decision rates need repeated datasets, which one benchmark cannot supply |

### GPU sharing on the experiment host (updated 19 September 2026)

The host (Apple M5, 32 GB, one GPU) is shared with a sibling project. On 18 September this workstream held back
all inference while that project's tau2-bench stream ran, on the stated ground that the stream "uses latency as an
outcome tier". **That ground was wrong for tau2**: its frozen hierarchy is success, agent completion tokens, tool-call
count. The latency tier belongs to the sibling's *other* (local coding) experiment and was generalised without
checking. The caution cost about a day; nothing was run and nothing was contaminated. The tau2 stream finished on
19 September 01:52 EDT.

From 19 September the author asked for both projects to share the GPU. Measured on this host with nothing else
running: Qwen2.5-3B 50.6 tok/s single-stream and 116 tok/s over 4 slots; Qwen2.5-7B 23.8 and 67 tok/s; both
servers resident at 9.4 GB, which leaves room for a second 7B-class server under the default Metal wired limit.
Real runs are started with `--allow-contention`; every manifest records that, and every episode records whether
another llama-server was **actually** generating when it began (`foreign_gpu_load_at_start`). This study's primary
outcomes (hidden-test success, call-count penalty, tokens) do not depend on speed; its latency fields do and are
reported only for uncontended episodes (`analysis.py --ops`). Sandbox limits are the one timing-dependent path into an
outcome (CPU 10 s; wall clock 20 s, deliberately twice the CPU limit), so validation and hidden-test timeouts are
counted by contention status.

## E0 — design-efficiency simulation (`sim/`, `dtr/`)

Question: the theory's primary empirical hypothesis is that randomized logs plus DR
estimation give policy values "at a lower evaluation cost than running every candidate
independently" (theory §8), and it lists "optimal allocation of a fixed branching budget"
as unsolved (§9). E0 quantifies both in a setting with exact truth.

`sim/synth_agent.py` generates two-stage coding-agent episodes: a first attempt
(direct / plan-first), a **noisy** response signal from imperfect self-tests, then a rescue
action (submit / self-review if passing; repair / resample / escalate if failing). Three
base rates are calibrated to a real 591-task MBPP+HumanEval run of a 7B open-weight coder
(first-attempt success 0.74 vs observed 0.73; self-test pass 0.565 vs 0.54;
P(success | pass) 0.833 vs 0.84). **Everything else is planted, not observed** — in
particular that repair breaks correct code on false alarms and that escalation helps deep
bugs. The simulation shows what the estimators and designs do *if* such structure exists;
it is no evidence that it does.

1,000 replicates at each n ∈ {300, 600, 1200, 2400, 4800}, 2 episodes per task:

| n episodes | RMSE, one randomized experiment (AIPW) | RMSE, one arm per scaffold | regret of picked scaffold (randomized / one-arm) | P(tailored regime beats best fixed) | contrast RMSE, randomize / fork |
|---:|---:|---:|---:|---:|---:|
| 300 | 0.0524 | 0.0899 | 0.0188 / 0.0321 | 0.415 | 0.0933 / 0.0635 |
| 600 | 0.0368 | 0.0613 | 0.0117 / 0.0235 | 0.628 | 0.0636 / 0.0437 |
| 1200 | 0.0260 | 0.0438 | 0.0068 / 0.0182 | 0.816 | 0.0461 / 0.0306 |
| 2400 | 0.0181 | 0.0307 | 0.0029 / 0.0116 | 0.911 | 0.0319 / 0.0216 |
| 4800 | 0.0129 | 0.0217 | 0.0017 / 0.0072 | 0.948 | 0.0232 / 0.0159 |

![design efficiency](../results/sim/figures/design_efficiency.png)

- **Validity.** IPW and AIPW bias ≤ 0.0014 at every n. Task-cluster bootstrap 95% intervals
  covered 0.925–0.960 (200 replicates per cell; Monte Carlo SE about 0.015, so these are
  compatible with nominal but do not establish it). An unweighted mean of regime-consistent
  episodes covered only 0.73 at n = 2400 for one regime: responders and non-responders are
  randomized with different probabilities (1/2 vs 1/3), so ignoring the weights is biased.
- **Evaluation cost.** For the same total episodes the randomized design estimates each of
  12 embedded scaffolds with 1.68× lower RMSE than one arm per scaffold — about 2.8× fewer
  episodes for equal precision. The factor is a property of this design (12 regimes sharing
  2×2×3 cells), not a general constant; it shrinks as targets overlap less with the logger.
- **Improvement.** Q-learning with failure-type tailoring closes 6% / 28% / 42% / 51% of the
  gap between the best fixed scaffold and the oracle at n = 600 / 1200 / 2400 / 4800. **At
  n = 300 it is worse than the best fixed scaffold** (−27% of the gap; it wins in only 41.5%
  of replicates). Tailoring is not free at small samples.
- **Forking.** Replaying every feasible rescue arm from the same saved state, with compute
  equalised (4.71 vs 3.06 cost units per episode, so 35% fewer episodes), cut the variance of
  the escalate-minus-repair contrast by 2.1–2.3× and produced better learned regimes at every
  n. The simulator's forks are exact state restorations with independent post-fork noise;
  real restoration fidelity is an empirical question (protocol §5).

Limitations: one data-generating mechanism; two stages; ridge Q-models that are correctly
rich for this mechanism; no misspecification, drift, censoring or weak-overlap cells — those
are covered by the theory agent's `scripts/run_simulation.py` stress runs, not here.

Reproduce (≈23 min on 4 cores; deterministic seeds):

```sh
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python numpy pandas scipy scikit-learn matplotlib tabulate requests pytest
.venv/bin/python experiments/sim/run_sim.py --reps 1000 --ci-reps 200 --workers 4 --out results/replication_sim
.venv/bin/python experiments/sim/plot_sim.py      # reads results/sim/
```

## S1 — crossed grid on the reference simulator (`s1_grid/`)

`docs/experiment_protocol.md` §3.2 asks for n ∈ {250, 1000, 4000} × T ∈ {2, 5, 10} × floor ∈ {0.5, 0.2, 0.05} at 1,000
replicates per cell, and the handoff notes that the archived stress runs change horizon and overlap together.
`s1_grid/run_grid.py` writes one config per cell to `configs/s1_grid/` and calls `scripts/run_simulation.py` unchanged;
27 cells, 0 failures; per-cell runtimes in the manifests sum to 35 minutes (4 cells at a time; slowest cell 229 s). Raw `replicates.csv` / `diagnostics.json` are stored gzip -9;
`raw_files_sha256.json` holds the sha256 of every uncompressed file so a rerun can be checked. Full tables:
[`results/s1_grid/grid_report.md`](../results/s1_grid/grid_report.md), long form `grid_summary_long.csv`.

With known propensities and correctly specified tabular Q (coverage Monte Carlo SE ≈ 0.007):

| horizon | logging | DR coverage, mean over 5 policies (n = 250 / 1000 / 4000) | worst single policy | DR mean RMSE (n = 4000) |
|---:|---|---|---|---:|
| 2 | confounded (floor 0.05 or 0.2) | 0.939 / 0.951 / 0.944 | 0.908 | 0.014 |
| 2 | uniform (floor 0.5) | 0.947 / 0.953 / 0.948 | 0.937 | 0.014 |
| 5 | confounded | 0.92 / 0.93 / 0.93 | 0.895 | 0.050–0.054 |
| 5 | uniform | 0.934 / 0.945 / 0.948 | 0.918 | 0.037 |
| 10 | confounded, floor 0.05 | 0.763 / 0.831 / 0.885 | **0.319** | **0.91** |
| 10 | confounded, floor 0.2 | 0.783 / 0.862 / 0.922 | 0.398 | 1.00 |
| 10 | uniform | 0.759 / 0.934 / 0.951 | 0.636 | 0.19 |

- **Horizon, not the floor, drives the failure.** At T = 10 under confounded logging DR intervals for `always_small`
  covered 0.32–0.83 and its RMSE reached 5.7 at n = 1,000 on a return bounded in about [−0.6, 1]: the estimate leaves the
  feasible range. RMSE *rose* from n = 250 to n = 1,000 before falling, the signature of heavy-tailed weights. Nothing
  is clipped or dropped; these cells are kept as failures. Uniform logging restores coverage at T = 10 once n ≥ 1,000.
- **The floor factor barely varies in this simulator.** The logger's raw P(large) lies in [0.250, 0.741] at T = 2,
  [0.250, 0.858] at T = 5 and [0.250, 0.955] at T = 10, so the smallest raw action probability is 0.250 / 0.142 / 0.045.
  Floors 0.05 and 0.2 therefore give *identical* cells at T = 2, floor 0.2 binds only mildly at T = 5, and floor 0.05
  binds only marginally at T = 10. In practice the grid contrasts a confounded logger with a uniform one (floor 0.5). To study overlap separately, the simulator needs a logger whose spread is
  itself a parameter — a request to the theory agent, not something changed here.
- **Misspecification.** With one nuisance wrong DR stays near-unbiased at T ≤ 5 (mean |bias| ≤ 0.005); with both wrong
  mean |bias| is 0.019 / 0.049 / 0.246 at T = 2 / 5 / 10 and mean coverage 0.82 / 0.86 / 0.73, as the theory predicts.
- **Evaluation cost — the hypothesis in theory §8 holds only at short horizons.** RMSE of on-policy evaluation with n
  episodes split across the 5 policies, divided by DR RMSE from one shared log of n episodes (uniform logging):
  **1.13–1.43 at T = 2, 0.41–0.70 at T = 5, 0.07–0.21 at T = 10**, stable in n. Because split-budget RMSE grows like
  √K, the shared log breaks even at roughly K* = 5 / ratio² candidate policies: **≈ 3.5 at T = 2, ≈ 27 at T = 5,
  ≈ 780 at T = 10**, close to the 2^T variance inflation of a deterministic target under uniform binary logging
  (4, 32, 1,024). K* is this document's back-of-envelope reading of the ratios, not a theorem. Stochastic odds-shift
  targets are consistently cheaper to evaluate (ratio 1.4 / 0.7 / 0.2).

Consequence for the real study: the code-routing design uses T = 3 with absorbing success, so most episodes contain
one decision and the inflation is far below 2³; the mock dry run put break-even near 4 candidate policies, and the
frozen class has 9. That is a prediction to be checked against the real OPE-versus-live comparison, not a result.

## L1–L3 results — code-routing study on real open-weight models (19 September 2026)

Design frozen at [`cb9481d`](https://github.com/ykzeng-yale/DTR-AgentEvals/commit/cb9481d); nothing below was
inspected before the stage that produced it was complete. Raw episode and pre-action decision records, manifests and
analysis CSVs are under `results/code_routing/`.

**Executed:** 4,488 randomized-log episodes (561 train+confirm tasks × 8) and 3,960 live episodes (6 frozen policies
× 330 confirm tasks × 2). **0 infrastructure errors, 0 retries, 0 intention-to-treat scorings** in either stage;
1 validation timeout and 3 truncated generations across 11,567 model calls; 0 episodes under foreign GPU load.

![calibration and frontier](../results/code_routing/analysis/figures/calibration_and_frontier.png)

### A1 — does the offline estimator predict what actually happens? Mostly yes

Paired by task, DR value from the shared randomized log minus the value measured by *running* each policy:

| policy | OPE (DR) | live | OPE − live | 95% CI | covers 0 |
|---|---:|---:|---:|---|:--:|
| always_large | 0.6719 | 0.6777 | −0.006 | [−0.029, +0.017] | yes |
| always_small | 0.5799 | 0.5956 | −0.016 | [−0.049, +0.018] | yes |
| learned | 0.6894 | 0.6727 | +0.017 | [−0.012, +0.045] | yes |
| soft_escalation_d2 | 0.6400 | 0.6464 | −0.006 | [−0.030, +0.017] | yes |
| escalate_after_first_failure | 0.6079 | 0.6245 | −0.017 | [−0.052, +0.019] | yes |
| **class_tailored** | 0.5947 | 0.6319 | **−0.037** | **[−0.070, −0.005]** | **no** |

Five of six agree within noise; Spearman rank agreement of policy utilities is **0.886**. One policy is
**miscalibrated**: `class_tailored` is under-estimated by 3.7 utility points. It is the policy whose action depends on
the failure *class*, the tailoring variable with the coarsest tabular cells, which is where a fitted-Q cell is
thinnest — reported as a failure of the method in this cell, not smoothed away.

Precision per unit of compute: the OPE/live standard-error ratio is 0.91–1.07, i.e. the shared log estimates each
policy about as precisely as dedicated live runs — while **one log of 3,662 model calls supports all nine frozen
policies**, against 5,504 calls to run just six of them live.

### A2 — does any regime beat the baseline? Yes. Does tailoring beat "always use the big model"? **No**

Pre-registered rule: claim improvement over `always_small` only if the Bonferroni-simultaneous OPE interval excludes
0 **and** the live contrast agrees in sign. Claimed for `always_large` (+0.092 utility), `learned` (+0.110),
`soft_escalation_d2/d4` (+0.060) and `large_then_small`. **Not** claimed for `class_tailored` or
`escalate_after_first_failure` — their simultaneous intervals include 0 although their live contrasts are positive.

The comparison that matters was **not** pre-registered and is reported as secondary: **learned vs always_large**.

| | OPE | live |
|---|---|---|
| utility | +0.018 [−0.016, +0.051] | **−0.005 [−0.027, +0.017]** |
| success | +0.015 [−0.018, +0.047] | **−0.008 [−0.029, +0.014]** |

**The learned tailored regime does not beat always-large.** Both intervals cover zero and the live point estimate is
slightly negative. The right-hand panel shows why: on this benchmark and model pair, success is close to a monotone
function of how much large-model compute is spent (0.611 at 0 large calls per episode → 0.717 at 1.30), and every
frozen policy lands near that line. The learned regime reaches 0.709 success with **1.15 large calls per episode
against 1.30 (−11%)** — the same quality slightly cheaper, but not enough to win on the frozen utility, and not a
statistically distinguishable improvement on either outcome.

This is a negative result for the *improvement* half of the DTR hypothesis in this setting, and it is the honest
headline. It does not bear on the *evaluation* half, which A1 supports.

### A3 — support diagnostics

IPW, cross-fitted DR and g-computation agree closely for every policy — the largest disagreement is below 0.016 on
utility and 0.0167 on success — with 0 missing Q cells. Deterministic
targets have the worst-case trajectory weight 8 = 2³ by design, stage-3 effective sample size 771–903 of 2,640
episodes, and 317–330 of 330 tasks contributing. The **stochastic** odds-shift targets are far cheaper to evaluate —
ESS 2,286–2,528 and maximum weight 1.78–2.56 — reproducing the prediction from the synthetic grid that supported
stochastic targets cost less to evaluate than deterministic ones.

### Negative controls — what the design buys

- **Naive association**: success of episodes that got a second decision minus those that stopped at one = **−0.484**.
  A second decision is *triggered by failure*, so the naive contrast is catastrophically misleading about the effect
  of escalating.
- **Wrong propensity**: IPW with a deliberately wrong constant 0.8 (instead of the recorded 0.5) gives
  **2.015** for `always_small` on the **success** outcome — outside the attainable range [0, 1] — and 0.433 for
  `always_large` against a correct 0.714.

### Theorem 5 is not applicable as computed, and would be vacuous anyway

With K = 3, weight bound c = 2 and 330 confirm tasks the finite-class certificate gives M = 48.4 and a half-width of
ε ≈ 18.1 on a utility of range ≈ 1.1, so it would be **vacuous**; ε = 0.05 would need ≈4×10⁷ tasks. An independent
review by the theory workstream raised the prior objection that **applicability fails before usefulness does**: the
theorem assumes outcome regressions fitted on data independent of the evaluation sample, and cross-fitting *within*
CONFIRM does not supply that. The number is therefore reported as a scale calculation, not as a certificate for the
scores here. The improvement decisions rest on the asymptotic Bonferroni intervals. A TRAIN-only nuisance fit, or a
justified foldwise construction, is needed before any finite-sample certificate is claimed; a variance-adaptive
(empirical-Bernstein) replacement needs further theory.

### A4 — branch audit: forked replay agrees with the log, and is cheaper

200 first-failure prefixes were sampled with known probability (0.355) from the completed confirm log, their
transcripts restored, and both models continued from the identical saved state with 2 fresh seeds each — 800
continuations over 103 tasks.

| quantity | value |
|---|---|
| restoration: recomputed transcript hash equals the hash logged before the parent's call | **800 / 800** |
| restoration: re-validated parent candidate reproduces the logged tool result | **800 / 800** |
| same state, same model, two fresh seeds: outcome disagreement (the serving-noise floor) | **0.080** |
| effect of continuing with the large model, from forked replay | 0.1200 (task-cluster SE 0.0320) |
| the same quantity from the randomized log (Hájek IPW, task bootstrap SE) | 0.1347 (SE 0.0474) |
| forked minus log | **−0.015, 95% CI [−0.127, +0.098]** |

Two independent routes to the same causal quantity agree. Restoration is exact: every one of the 800 rebuilt
transcripts hashed identically to what was logged before the original call, and every re-validated parent candidate
reproduced its logged tool result — so the environment really is replayable, which is the assumption the whole branch
estimand rests on. The 8% same-state/same-model disagreement is the irreducible sampling noise of the server at
T = 0.7 and bounds how sharp any single-episode counterfactual claim can be.

**Forking was 2.19× more precise using 39% of the model calls** (1,434 new calls versus 3,662 in the confirm log;
variance × compute 1.47 versus 8.23, a 5.6× efficiency gain for this contrast). The synthetic study E0 predicted a
2.1–2.3× variance reduction from forking at equal compute; the real open-weight system delivered 2.19×. That
prediction transferring from a planted simulator to real models is the most transportable finding here.

The caveat is the estimand, not the precision: this is the mean continuation effect over the prefix population that
the *randomized logger* reached. It is **not** the value of a policy that changes how those prefixes are reached, and
it cannot replace the whole-policy comparison in A2.

### Contention and timing

Every stage ran with **zero foreign GPU load**, so latency is interpretable throughout: median call 3.1–4.2 s (small)
and 6.3–11.0 s (large). Across 13,001 model calls in all four stages there was **1 validation timeout, 0 hidden-test
timeouts and 3 truncated generations**. Timeouts are the only timing-dependent path into an outcome, and at this rate
they cannot have moved a result.

## L1–L3 — code-routing study (`code_routing/`)

Pre-registration draft: [`code_routing/protocol.md`](code_routing/protocol.md). It follows
`docs/experiment_protocol.md` §4–§6: binary small/large routing at ≤3 pre-specified
opportunities, P(large) = 0.5, absorbing success, pre-drawn assignments committed before
execution, every decision fsync'ed before the model call, task-level 30/231/330 split,
frozen policy class including a fitted-Q learned table, fresh live executions of six
policies for OPE-vs-live calibration, and the Theorem 5 certificate reported even if vacuous.

Declared deviation: function-synthesis benchmarks in a macOS Seatbelt sandbox instead of
BrowserGym / mini-swe-agent, because the host has no container runtime. Model-generated
code runs only inside that sandbox; its containment (network, `$HOME`, runaway loops) is
checked on the host.

One number worth the theory agent's attention now: with K = 3, P = 0.5 and 330 confirm
tasks, the Theorem 5 half-width is ε ≈ 18 on a utility of range ≈ 1.1 (M = 48.4), and a
half-width of 0.05 would need about 4×10⁷ tasks. The certificate as stated is vacuous at any
feasible benchmark size; an empirical-Bernstein or variance-adaptive version is needed for it
to bind. The analysis reports CLT/Bonferroni intervals alongside it.

Run order once the GPU is free (each stage refuses to overwrite):

```sh
cd experiments/code_routing && PY=../../.venv/bin/python
$PY -m pytest -q test_estimators_absorbing.py
$PY run.py --servers start
$PY run.py --stage tests                 # visible tests: model-written inputs, certified against the reference, hidden-input overlaps removed
$PY run.py --stage pilot                 # 30 disjoint tasks: gate in protocol §6; may adjust config.json ONLY as §6 allows
$PY design.py                            # freeze config + design; COMMIT + PUSH before any design-task model call
$PY run.py --stage log                   # 4,488 randomized episodes, resumable
$PY analysis.py --learn                  # freeze learned_policy.json; COMMIT + PUSH
$PY run.py --stage live                  # 3,960 fresh target-policy episodes
$PY analysis.py --calibration
$PY run.py --stage branch                # 800 continuations from 200 restored prefixes
$PY analysis.py --branch
$PY run.py --servers stop
```

Dry run without any model: append `--mock` to every `run.py` / `analysis.py` call; output goes
to gitignored `work/` and is labelled meaningless.

Host-specific inputs (not in the repository): the 591-task file built by the sibling
project's `data.py` from the public MBPP/HumanEval URLs, GGUF weights in the Hugging Face
cache, and a locally built `llama-server` (set `LLAMA_SERVER`).
