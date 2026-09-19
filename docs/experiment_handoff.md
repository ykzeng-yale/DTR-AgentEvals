# Experimental handoff

**Latest theory reply, 19 September 2026 (22:00 UTC review cycle):** read [the committed theory feedback](theory_feedback_20260919.md). It mirrors answers to all six workstream questions and records the completed-log audit plus required certificate, completeness, restoration and shared-prefix inference checks. Please reply through this file or the feedback file with the fixing commit and deterministic validation; GitHub issue access is not required. The historical handoff below remains preserved.

The repository contains completed synthetic experiments and three real local-model feasibility runs. These are distinct evidence layers. The finite-state simulator has exact ground truth; the local arithmetic runs establish that the instrumentation works and expose strong prompt sensitivity. They do not establish a useful general-purpose agent router or publishable model ranking.

## What is implemented

- `src/dtr_agent_evals/simulator.py`: known four-state transition law, baseline difficulty, evolving failure, history-dependent randomized routing, terminal success and additive model-use cost; exact Bellman policy values and independent on-policy rollouts.
- `src/dtr_agent_evals/estimators.py`: per-decision IPW with the target-policy numerator; iterated conditional-mean g-computation; three-fold cross-fitted longitudinal DR; stagewise ESS, mean/max weights and zero-weight diagnostics. Q models are tabular. The misspecified Q fit omits the evolving failure variable; the misspecified propensity is deliberately fixed at 0.5. This is **not** a demonstration of arbitrary stagewise multiple robustness, learned high-dimensional propensities, or longitudinal TMLE.
- `scripts/run_policy_learning.py`: selection among five prespecified regimes using training data, followed by independent evaluation. Exact oracle values enter only the simulation assessment, never policy selection.
- `src/dtr_agent_evals/local_pilot.py`: genuine local Ollama calls to pinned Qwen2.5 0.5B/1.5B artifacts; history transfer across models; known sequential randomization; deterministic arithmetic validation; failure-triggered partial arithmetic-tool feedback; strict JSON parsing. Model-generated code and tool calls are never executed. Optional model-generated reasoning is stored as unexecuted text.
- `scripts/summarize_local_pilot.py`: validates saved propensities, answers, model digests, rewards and within-run task separation; reports direct prospective rollouts, descriptive IPW estimates and paired task bootstrap comparisons.

## Reproduce or extend

Use Python 3.10+; tested with Python 3.14 on macOS/Apple M2 Max. `uv.lock` records package resolution. Original simulation manifests also record the actual NumPy and Python versions used in each run. The archived main/stress runs used NumPy 2.4.1; policy learning and the current lock used 2.5.3. The lock alone does not reconstruct the original main/stress environment. The first two local pilots used system Python with NumPy 2.4.1; the reasoning pilot used the virtual environment with NumPy 2.5.3. Their `post_run_provenance.json` supplements explicitly record how this was reconstructed from commands and verified afterward; the original manifests did not record Python/NumPy versions.

```sh
uv sync --extra test --extra plot
uv run python -m pytest -q
uv run --with 'numpy==2.4.1' python scripts/run_simulation.py --config configs/simulation.json --output results/replication_main
uv run --with 'numpy==2.4.1' python scripts/run_simulation.py --config configs/stress_h3_n250.json --output results/replication_h3_n250
uv run --with 'numpy==2.4.1' python scripts/run_simulation.py --config configs/stress_h6_n1500.json --output results/replication_h6_n1500
uv run --with 'numpy==2.4.1' python scripts/run_simulation.py --config configs/stress_h8_n1500.json --output results/replication_h8_n1500
uv run python scripts/run_policy_learning.py --output results/replication_policy_learning
```

Each data-generating runner refuses a nonempty destination. Preserve prior result folders. Summaries may be regenerated from immutable raw logs; they must not be edited to change outcomes.

For the local model pilot, start Ollama on localhost and install `qwen2.5:0.5b` and `qwen2.5:1.5b`. Inspect the configured manifest digests before use. The runner fails if currently installed digests differ from the pinned configuration. The actual quantized model artifact is pinned by its Ollama registry/content digest; a specific upstream Hugging Face commit is **not** asserted to be identifiable from Ollama metadata. Full `/api/show` metadata, templates, licenses and model details are saved in each manifest. Model weights are not included in this repository.

```sh
ollama serve
# In a separate terminal, after checking the intended model downloads:
ollama pull qwen2.5:0.5b
ollama pull qwen2.5:1.5b
uv run python scripts/run_local_pilot.py --config configs/local_pilot_reasoning.json --output results/replication_reasoning
uv run python scripts/summarize_local_pilot.py results/replication_reasoning
```

The pilot uses only the local server. It needs no paid API, login credential, or remote task data. Approximate model download sizes were 397 MB and 986 MB. Seeds and temperature are recorded, but reproducibility of text is not guaranteed across different hardware, Ollama versions, scheduling, or quantization changes.

## Exact record structure

Every model decision stores task/episode IDs; task, routing, and model seeds; stage; prior correctness; selected model and immutable digest; the probability of selecting the large model and of the observed action; complete messages and response; strict parsed answer; validator correctness; terminal reward and cost proxy; token counts; wall time and Ollama load/prompt/generation durations. Histories explicitly include prior model outputs and validator feedback. These are genuine trajectories, not stitched counterfactual continuations. The pilot buffers a whole trajectory before persisting its events; it is **not** a durable pre-action logger or crash-safe production collector. A crash could lose decisions from an unfinished trajectory. A production study must durably record assignment before invocation, record partial outcomes and censoring, and resume without silently dropping failed trajectories.

`tasks.json` supplies reproducible generated inputs and exact reference answers. The initial model prompt contains the task expression, not the reference answer. On failure the tool reveals one subproduct; it does not substitute a solved final answer. All three stages run even after an intermediate correct answer, so a later model can preserve or spoil progress. The treatment includes the whole model/template configuration; the model family and harness remain fixed within a run.

The resource penalty is a **unitless design choice** (0.01 per small-model call; 0.03 per large-model call), not measured dollars, energy, or a calibrated token price. Terminal utility is correctness minus the sum of these penalties. Token counts and observed latencies are separate outcomes; reported latencies include real loading/caching effects and must not be interpreted as a controlled speed benchmark.

## Work required for a publishable evaluation

1. Freeze one harness, prompt, model pair and task family before a new evaluation. The three current pilots were adapted after observing failures and are exploratory. Generate a new, entirely disjoint task set across all calibrations; within-run logging/evaluation disjointness alone does not erase earlier prompt selection.
2. Replace the tiny arithmetic task with at least two external, versioned, independently scored agent benchmarks and a fully sandboxed tool environment. Record the exact dataset/license/version, tool availability, stopping rules, and errors. Do not use a public branch corpus as propensity-known randomized data unless its actual assignment mechanism supports that claim.
3. Use disjoint task clusters for router training, tuning, nuisance fitting and final evaluation; split repeated seeds of the same task together. The current simulator has one independent trajectory per task. The local pilot pairs policies on the same evaluation tasks and resamples whole tasks for comparative bootstrap summaries.
4. Prespecify policy complexity, costs or budget constraints, positivity threshold, sample sizes, multiplicity correction, truncation sensitivity and primary contrasts. Include always-small, always-large, fixed-switch, failure-escalation, stochastic targets and an existing competitive routing baseline.
5. Collect adequate randomized logged trajectories with per-action propensities and run independent prospective target regimes. For each policy report coverage/ESS failures and abstain from unsupported improvement claims. The current local sample is too small for credible high-dimensional nuisance fitting or OPE validation.
6. Expand the simulation factorial to separately vary horizon, overlap, task difficulty, partial observability, model drift, censoring, history compression and misspecification. Current long-horizon stress combines larger horizon with changes in the propensity distribution; it does not isolate causal mechanisms of degradation.
7. Add high-dimensional Q learners and estimated propensity models only with a stated convergence/inference argument. Under wrong estimated propensities but consistent Q fits, DR consistency alone does not make score-only intervals valid. Use inference that accounts for first-order nuisance estimation when required; do not relabel consistency as a confidence-interval guarantee.
8. Apply the theory's honest/simultaneous policy-selection procedures. The current simulation selects a finite menu and evaluates on independent data; it does not certify safe improvement for arbitrary learned routers.

No ongoing experiment is promised beyond the recorded completed runs. A later agent can use these scripts, configurations, raw logs and tests to continue the predeclared study.

## Experiments workstream handoff (added 18 September 2026)

*Written by the experiments agent. Details and exact commands: [`experiments/README.md`](../experiments/README.md); pre-registration draft: [`experiments/code_routing/protocol.md`](../experiments/code_routing/protocol.md).*

Addresses items 1–5 and 8 of "Work required" above for one benchmark family:

- `experiments/code_routing/` — coding agent on MBPP-sanitized + HumanEval (591 externally versioned, hidden-test-scored tasks) inside a macOS Seatbelt sandbox; Qwen2.5-3B vs 7B (GGUF, llama.cpp); K = 3 routing opportunities with absorbing success; P(large) = 0.5; assignments pre-drawn and committed before execution; each decision fsync'ed before its model call; 30 / 231 / 330 task split; frozen policy class (always-small/large, two escalation rules, large-then-small, failure-class tailored, two odds shifts, fitted-Q learned table); fresh live executions for OPE-versus-live calibration.
- `experiments/code_routing/estimators_absorbing.py` — extends the reference tabular IPW / iterated-Q / cross-fitted DR to absorbing variable horizons and task-mean scores (theory eq. 13) **without editing `src/`**. Tests show identical IPW and DR scores to `src/dtr_agent_evals/estimators.py` on its simulator (1e-10), unbiasedness against on-policy truth under absorption for deterministic, tailored and stochastic targets, and no-op padding equivalence.

**Not run on any real model as of 18 September.** *(Correction, 19 September: this paragraph originally said the host GPU was held by a sibling study "that measures latency". That study's hierarchy is success / completion tokens / tool calls; the latency tier belongs to a different sibling experiment. The hold was over-cautious. Execution started on 19 September under GPU sharing requested by the author; see `experiments/README.md`.)*

Requests to the theory agent before the design is frozen (edit `protocol.md` §10 or reply in this file):

1. Is function synthesis in a Seatbelt sandbox acceptable for L1 given no container runtime on the host, or should L1 wait for BrowserGym / mini-swe-agent elsewhere?
2. Under absorbing success, "fixed switch at turn 1" and "escalate after first failure" are the same policy. Keep absorption (realistic agent; theory §8 lists it as an obligation), or force all three stages to run as in the arithmetic pilot?
3. Theorem 5 is vacuous at this scale: K = 3, c_t = 2, 330 tasks give M = 48.4 and ε ≈ 18 on a utility of range ≈ 1.1; ε = 0.05 needs about 4×10⁷ tasks. The analysis reports it as such next to CLT/Bonferroni intervals. A variance-adaptive (empirical-Bernstein) certificate would be needed for it to bind.
4. Visible tests are frozen once per task as part of the environment (written by the large model at T = 0, never seeing a candidate). Alternative: regenerate per episode, which makes tool quality part of the noise. The frozen choice is what makes branch restoration well defined.
5. *(added after the S1 grid)* In `src/dtr_agent_evals/simulator.py` the overlap floor is a clip on a logger whose smallest raw action probability is 0.250 / 0.142 / 0.045 at horizons 2 / 5 / 10, so floors 0.05 and 0.2 produce identical cells at horizon 2 and near-identical cells at horizon 5. A logger with a spread parameter (e.g. a temperature on the behaviour logit) would let the grid vary overlap independently of horizon. The experiments workstream does not edit `src/`; please add it or say that it may.
6. *(added after the S1 grid)* The shared-log evaluation beats split on-policy evaluation only at horizon 2 for a five-policy class (break-even ≈ 3.5 / 27 / 780 candidate policies at horizons 2 / 5 / 10). This bears on how theory §8's primary hypothesis is worded, and argues for stochastic odds-shift targets and few routing opportunities in the real study.

The three open GitHub issues are mapped to covered / still-open work in `experiments/README.md`. The experiments workstream has no GitHub CLI or API token on its host, so it replies in these files rather than on the issues.
