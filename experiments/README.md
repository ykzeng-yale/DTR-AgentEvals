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
| L1–L3 | Code-routing study on MBPP + HumanEval, Qwen2.5-3B vs 7B, K=3 routing decisions | real open-weight inference | **running from 19 September** (environment construction, then pilot); no result yet |
| A4 | Branch audit: 200 restored first-failure prefixes × {small, large} × 2 fresh continuations, with transcript-hash and tool-result restoration checks | real inference | **implemented, NOT run**; mock dry run restores 800/800 |

Nothing in this directory is a result from a real language model yet.

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
reported only for uncontended episodes. Sandbox wall-clock limits (10 s) are the one timing-dependent path into an
outcome, so validation/verification timeouts are counted by contention status.

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
$PY run.py --stage tests                 # frozen visible tests (environment construction)
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
