# Experiments workstream

Owner: the experiments agent (a separate Claude Code session from the theory agent). This
directory and `results/sim/`, `results/code_routing/` are written only by this workstream.
Theory, proposal, literature and the reference library under `src/` belong to the theory
agent and are not edited from here. Rules in [`AGENTS.md`](../AGENTS.md) apply.

## Status (18 September 2026)

| ID | What | Evidence layer | Status |
|---|---|---|---|
| E0 | Design-efficiency simulation: one sequentially randomized experiment vs one arm per scaffold; tailored-regime learning; forking vs randomizing at equal compute | synthetic, known truth | **executed** — 5,000 replicates, `results/sim/` |
| E1 | Absorbing-horizon tabular IPW / g-computation / cross-fitted DR with task-cluster inference | code + tests | **implemented**, 12 tests pass; reproduces `src/dtr_agent_evals` scores to 1e-10 on its simulator |
| L1–L3 | Code-routing study on MBPP + HumanEval, Qwen2.5-3B vs 7B, K=3 routing decisions | real open-weight inference | **harness complete, NOT run.** Only deterministic mock dry runs (gitignored). Blocked, see below |
| A4 | Branch audit (200 restored first-failure prefixes) | real inference | planned; not implemented |

Nothing in this directory is a result from a real language model yet.

### Why L1–L3 has not run

The experiment host (Apple M5, 32 GB, one GPU) is running a sibling project's
pre-registered tau2-bench stream on the same GPU, and that study uses latency as an
outcome tier. Starting inference here would contaminate it. At the time of writing that
run had finished 5 of 98 units of its first of two arms in about 85 minutes, which
extrapolates to roughly two days. `run.py` refuses to start while a foreign llama-server is
generating; overriding is possible and is recorded in every manifest. **This is a
scheduling decision for the author**, not something the harness should decide silently.

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
$PY run.py --servers stop
```

Dry run without any model: append `--mock` to every `run.py` / `analysis.py` call; output goes
to gitignored `work/` and is labelled meaningless.

Host-specific inputs (not in the repository): the 591-task file built by the sibling
project's `data.py` from the public MBPP/HumanEval URLs, GGUF weights in the Hugging Face
cache, and a locally built `llama-server` (set `LLAMA_SERVER`).
