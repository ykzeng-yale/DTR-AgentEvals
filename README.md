# DTR-AgentEvals

**Moving to another laptop?** Start with the [portable project handoff](docs/PORTABLE_HANDOFF_2026-09-26.md). It links the research plan, paper, experiment archives, current scientific verdicts, roadmap, and a sanitized record of decisions from the coordinating chat. The recurring theory-lead check was removed at the author's request on 26 September 2026.

**Dynamic Agent Regimes: causal evaluation and improvement of model-switching agents.**

When an agent changes models during a task, the choice changes future outputs, tool states, errors and routing decisions. This project asks what would happen if tasks followed a specified switching policy, and whether an offline estimate agrees with fresh executions.

$$V(\pi)=E[Y^{\pi}],\qquad \Delta(\pi,\pi_0)=E[Y^{\pi}]-E[Y^{\pi_0}].$$

The proposed contribution is a sequentially randomized evaluation design with versioned model interventions, explicit support diagnostics, honest policy evaluation, and live validation. The underlying DTR and off-policy evaluation theory is established; this repository does **not** claim that renaming routing as a DTR creates a new estimator.

## Current priority: theory and paper

**26 September 2026:** Codex has resumed scientific leadership and an active goal toward an
independently reviewed, evidence-backed preprint package. The existing Claude Code worker implements
bounded experiment specifications under lead review. Read the
[current scientific assessment and roadmap](docs/scientific_lead_resumption_20260926.md).
The 41-page manuscript contains scoped theory, synthetic development evidence and a critical coding-agent
case study. The learned archived router is a fixed schedule; adaptive benefit and useful primary joint
inference remain unestablished. The local coding/browser competence paths are closed, and REQ-020/021
record the configured-worker-host capacity block for the proposed replacement pair.

The [prospective replicated-block inference note](docs/theory_replicated_block_inference.md) addresses
fixed-benchmark policy contrasts and offline/fresh covariance without relabeling tasks as iid population draws.
[REQ-024](docs/req024_replicated_inference_setup.md) supplies reviewed analysis functions and deterministic
fixtures; it releases no model or simulation batch. New live/CONFIRM remains held pending competence,
resource, opportunity and frozen analysis/precision gates. Frozen archives remain unchanged. The subsequent manuscript synthesis integrates the accepted development probes and current inference limitations; see [validation](manuscript/validation_20260926_synthesis.json). The former recurring lead check remains deleted.

The [precision-design audit](docs/theory_precision_design_20260926.md) derives tighter shared-score ranges
and assesses sufficient concentration counts. These remain too large to supply a practical plan from
range bounds alone; a stronger justified independence design and real-target variance evidence are still needed.

**21 September design update:** a [primary-literature and official-code review](docs/literature_design_review_20260921.md)
now informs the [v2 prospective protocol](docs/experiment_protocol_v2.md): separate evaluator calibration from
history-dependent improvement, reuse mini-swe-agent/SWE-bench and a local RouteLLM baseline, and require explicit
feedback, failure, support and precision gates. The new conditional branch analysis is independently reconstructed
and [corrected](docs/theory_feedback_20260921_conditional_frame.md); primary inference remains unresolved.
These are reviewed plans and retrospective checks, with no new model or Monte Carlo execution.

The new [extension proofs](docs/theory_extensions.md) cover prospective routing opportunities, selectively measured branch contrasts, oracle allocation of branch costs, and execution-kernel sensitivity. The [independent internal review](docs/theory_review_20260919.md) records conditions, corrections, and exact checks; the [claim map](docs/paper_positioning.md) separates inherited theory from the project-specific formulation.

[Full-project readiness](docs/readiness.md) is **55% (change 0 percentage points; judgment range 45–65%)** at this checkpoint. Remaining milestones are useful validated inference/adequate comparisons, remaining statistical validation and final empirical synthesis, and independent reproducibility/author metadata/submission packaging. The stable rubric and earlier estimates are recorded in [the coordination issue](https://github.com/ykzeng-yale/DTR-AgentEvals/issues/4).

## Research package

| Start here | Contents |
|---|---|
| [Research proposal](docs/research_proposal.md) | Scientific question, contribution boundary, target trial, aims, hypotheses and manuscript abstract |
| [Literature audit](docs/literature.md) | Original 22-source audit plus a [five-source theory supplement](docs/paper_positioning.md), nearest-work comparisons, corrected source claims, search log and availability audit |
| [Theory and proofs](docs/theory.md) | Identification, policy-ratio IPW, fixed-policy EIF, exact DR remainder, inference, clusters, Bellman recursion, finite-class improvement and incremental routing |
| [Experiment protocol v2](docs/experiment_protocol_v2.md) | Literature-informed prospective design, exact-truth controls, two-decision repair study, baselines, resource and inference gates; [v0.1](docs/experiment_protocol.md) retained |
| [Executed results](docs/experiment_results.md) | What actually ran, numerical results, failed pilot attempts and limitations |
| [Next-agent handoff](docs/experiment_handoff.md) | Commands, owned artifacts, current limitations and concrete next experiments |
| [External data audit](docs/external_data_audit.md) | Direct inspection of 896 released Replay Gap records spanning 56 distinct tasks |
| [Bibliography](references/references.bib) | Verified reference metadata |

**27 September 2026:** the Mac mini completed [4,000 synthetic primary-logger studies](docs/theory_feedback_20260927_req027_decision.md), independently recounted by the lead. Results support the stipulated variance mechanism, with limited Wald coverage and a disclosed macOS memory-limit deviation. A separate agent mathematical review supplies explicit assumption/support corrections. The real-agent comparison and CONFIRM remain held.

## Archived evidence

The following is the original 18 September 2026 baseline, retained as development history. Later experiment records are listed in [executed results](docs/experiment_results.md); this theory-paper update does not rerun or independently validate those newer experimental results. Current manuscript validation is recorded in [the paper status](manuscript/STATUS.md).

Original baseline:

- **Derived and numerically checked:** the core fixed-policy theory, the exact DR drift, and the additional derivative term for an unknown-behavior incremental target. The tests compare influence-function derivatives with finite differences over a fully enumerated history-dependent environment.
- **Executed synthetic experiments:** 400 main Monte Carlo replicates, three 200-replicate stress runs, and a 300-replicate finite-policy selection study. Exact dynamic-programming truth is available. These are synthetic results.
- **Executed real open-weight inference:** 320 trajectories and 960 model calls using Qwen2.5 0.5B and 1.5B through local Ollama, with pinned artifact digests, actual responses, known routing probabilities, objective arithmetic validation and recorded timing/token counts. Failed task calibrations remain in the archive. These are three exploratory pilots, not 320 independent tasks.
- **Verified:** 16 tests pass. A complete independent rerun of the 400-replicate main simulation reproduced all four numerical output files byte for byte; see [the reproduction record](results/reproduction_check.json).
- **Still required for a substantive agent study:** competent browser/coding benchmarks, larger independent live-policy validation, task-cluster inference, learned routing baselines, and the full prespecified stress grid. No claim of broad agent improvement is established.

![Synthetic estimation and overlap diagnostics](results/figures/simulation_overview.png)

The first two panels show the main simulation with known routing probabilities and correctly specified continuation models. The third shows a joint horizon/overlap stress test; it does not isolate horizon alone. Error bars represent Monte Carlo uncertainty in estimated coverage. All run summaries and replicate-level outputs are retained.

## Core idea

```mermaid
flowchart LR
    H[Observed history] --> A[Randomized model choice]
    A --> K[Model output and tool execution]
    K --> N[Updated history and feedback]
    N --> B[Next routing decision]
    B --> Y[Terminal success and resources]
    H --> B
```

For a frozen model pool and harness, the routing action is the model configuration, and text generation is part of the downstream transition. The trajectory ratio is

$$W_t^{\pi}=\prod_{s=1}^{t}\frac{\pi_s(A_s\mid H_s)}{b_s(A_s\mid H_s)}.$$

This avoids token-level likelihood ratios **when the intervention preserves the conditional execution kernels**. It does not create support for an unseen model or changed harness. A deterministic policy has the adherence indicator in the numerator. Holding old downstream states fixed after a model switch evaluates a different intervention.

The longitudinal doubly robust score is

$$\widehat V_1(H_1)+\sum_{t=1}^{T}\widehat W_t\{R_t+\widehat V_{t+1}(H_{t+1})-\widehat Q_t(H_t,A_t)\}.$$

Point-estimate robustness does not automatically imply valid confidence intervals. The proof document states the required sampling, support and nuisance-rate conditions. The current tabular fitting implementation has ordinary all-Q-or-all-behavior robustness; it is not a fully implemented sequentially doubly robust learner or longitudinal TMLE.

## Reproduce

Requires Python 3.10+; the committed lockfile records the Python package environment. Use a new output directory for every run.

```sh
uv sync --extra test
uv run pytest -q
uv run python scripts/run_simulation.py --config configs/simulation.json --output results/simulation_replication
uv run python scripts/run_policy_learning.py --config configs/policy_learning.json --output results/policy_learning_replication
```

For the real model pilot, see [the handoff](docs/experiment_handoff.md). It requires a local Ollama service and the two exact model artifacts; no paid API is used. New runs verify artifact digests. Models are downloaded separately and are not committed to GitHub.

To repeat the public data audit:

```sh
uv run python scripts/audit_replay_gap.py --output results/replay_gap_audit_replication
```

To rebuild the plot from the archived summaries, install the plot extra and run `scripts/plot_simulation.py`. The source release and local raw-model outputs remain distinct from synthetic simulation. Root and branch data are never mixed as independent tasks.

## Collaboration rules

Read [AGENTS.md](AGENTS.md) before continuing experiments. Preserve completed runs, state what has and has not been executed, keep task families together across folds, pin model/harness configurations, and do not publish private data. Third-party model and dataset licenses are documented in the manifests and source audit. The project currently does not grant an additional repository-wide software license.
