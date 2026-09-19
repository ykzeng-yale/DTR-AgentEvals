# Dynamic Agent Regimes: causal evaluation and improvement of model-switching agents

**Research specification, updated 19 September 2026.** This is a proposed research program with a mathematical foundation and a runnable pilot. It is not a claim of a new doubly robust estimator, established empirical superiority, or an exhaustive novelty search. See [the literature audit](literature.md), [theory and proofs](theory.md), and [the experiment protocol](experiment_protocol.md).

## 1. Scientific question

For a population of tasks executed by a fixed agent harness, which model should be invoked at each eligible decision, given everything observed so far, to improve final task success subject to resource constraints? Can we estimate the consequences of changing that routing policy from previously randomized trajectories, with uncertainty that agrees with fresh executions?

The running example is a small model that can escalate after a failed tool call and potentially return to a small model after recovery. The intervention is the **model configuration used for the next agent turn**. It is not merely a label attached retrospectively to a completed trajectory. A configuration includes weights, quantization, tokenizer, prompt format, decoding, context processing, tools, and serving behavior. Changing these changes the intervention.

The population is a prespecified distribution of task instances, not every task encountered on the internet. The unit for population inference is an independently sampled task; repeated seeds and branches remain nested within task. A fixed benchmark with repeated executions instead supports an inference target conditional on that benchmark, unless a sampling argument is supplied.

## 2. Positioning and contribution

Stepwise routing is established, including [Budget-Aware Agentic Routing](https://arxiv.org/abs/2602.21227). Causal learning from observational query-routing data is established in [Causal LLM Routing](https://arxiv.org/abs/2505.16037). [The Replay Gap](https://arxiv.org/abs/2608.08239) provides direct motivation for evaluating the downstream consequences of a switch through live continuation. Classical longitudinal causal inference and off-policy evaluation already provide the core identification and estimation machinery.

Our proposed contribution is an **evaluation design and evidence package** that joins those pieces:

1. **A precise intervention contract.** Treat a versioned model configuration as a low-dimensional randomized action inside a fixed harness; allow all resulting generated text, tool actions, and observations to evolve naturally. This permits routing-level probabilities without requiring token-level likelihood reconstruction, provided the conditional generation and environment mechanisms are preserved.
2. **Prospective sequential experimentation.** Record known routing probabilities at eligible decision points and compare fixed, adaptive, and supported stochastic regimes. Use observable triggers and deterministic budget rules that could actually be deployed.
3. **An inferential evaluation standard.** Compare longitudinal IPW, regression, and cross-fitted doubly robust evaluation against independently executed target regimes. Report coverage, estimation error, effective support, and false improvement decisions, alongside task success and cost.
4. **An overlap-aware improvement path.** Begin with small odds shifts or mixtures around a frozen reference router, then validate selected policies independently. A supported intervention answers a narrower question than an unrestricted optimal router.
5. **A branching audit.** Use restored environments, same-model controls, and task-level inference to diagnose when static replay, context compression, serving changes, or hidden router inputs invalidate an evaluation.

None of these points alone establishes a novel theorem. The potential publishable advance is demonstrating when this combined design yields trustworthy, resource-efficient evaluation, and identifying its limits. A stronger methods paper would require a new result beyond the inherited proofs, such as an efficiency-optimal sequential exploration design under a specified resource model. Global optimal sequential exploration remains open. The theory-first manuscript now derives a narrower oracle cost allocation for a fixed reference-prefix population and independently selected paired continuations. It also proves an eligible-opportunity reduction and an execution-kernel sensitivity bound; these specialize established principles rather than establish novelty of the general methods. See [the theory extensions](theory_extensions.md) and [paper positioning](paper_positioning.md).

## 3. Target trial

| Element | Prespecified definition |
|---|---|
| Eligibility | Tasks sampled from the declared benchmark partition, supported model pool, harness and environment version; preflight infrastructure checks pass |
| Time zero | Task initialized before the first routed model call |
| Decision times | Next model call at a fixed set of prospective eligible turns, or observable events such as a failed tool call; eligibility cannot depend on future completion length |
| Treatment | Choice among pinned model configurations; stop/continue may be a separate action only if explicitly included |
| Assignment | Known sequential randomization conditional on recorded pre-action history, with feasible-action probabilities logged before sampling |
| Strategies | Always-small, always-large, prespecified switch, error escalation, progress downgrade, frozen learned policy, supported odds-shift family |
| Follow-up | Until success, terminal failure, or a fixed maximum number of decisions/resources |
| Primary outcome | Objectively verified terminal success under the common resource cap |
| Secondary outcomes | Input/output tokens, measured execution time, tool calls, model transitions, invalid-action rate; monetary or energy cost only if directly measured |
| Primary contrast | Success difference between a frozen adaptive policy and always-small, with cost reported separately |
| Budget analysis | Success under a common hard cap; or a prespecified utility frontier over declared cost penalties |
| Analysis unit | Task; seeds, policies run on the same task, and branch descendants form one cluster |

Budget exhaustion and valid model/harness failure are outcomes of deployment. A missing verification result caused by infrastructure loss is a separate observation problem; neither dropping it nor declaring it a model failure is automatically correct. Record both and perform the prespecified failure-policy sensitivity analysis.

## 4. Estimands and interpretation

Let $H_t$ contain the complete information available before routing decision $t$, $A_t$ be the selected configuration, and $\pi_t(a\mid H_t)$ a possibly stochastic policy. Let $Y^\pi$ be terminal success and $C^\pi$ total measured resource consumption under a genuine execution following $\pi$.

$$V_Y(\pi)=E[Y^\pi],\qquad V_C(\pi)=E[C^\pi],\qquad \Delta_Y(\pi,\pi_0)=V_Y(\pi)-V_Y(\pi_0).$$

These are population average effects of policies. They do not identify the best model for an individual task or the effect of replacing a model checkpoint never explored in the data. The policy may use a compact representation, but confounding adjustment may require a richer history. A learned representation does not automatically preserve exchangeability or make the system Markov.

The fixed-policy value estimand is shared with history-based off-policy evaluation. DTR terminology is useful for specifying adaptive strategies, eligibility, rerandomization and inferential contrasts; it does not create a distinct identification principle that reinforcement learning lacks.

For a utility $U^\pi=Y^\pi-\lambda C^\pi$, choose the unit and $\lambda$ before the confirmatory evaluation. Report $(V_Y,V_C)$ as well, because a chosen utility can obscure reduced success. Expected-cost constraints and per-task hard budgets are different questions. A hard budget belongs in the environment transition and feasible action set.

## 5. Primary hypotheses and falsifiable claims

**H1: calibration.** Under known sequential randomization and adequate overlap, longitudinal estimators track freshly executed policy values. Test bias and coverage against exact simulated truth, then compare to independent live estimates with uncertainty in both quantities.

**H2: history dependence.** Static replay or comparisons among tasks that happened to switch can mis-rank policies when earlier actions affect later errors and routing. Include settings where this problem vanishes. The study must not rely only on a hand-built scenario in which a naive comparator necessarily loses.

**H3: support tradeoff.** Modest supported policy changes can be evaluated more precisely than extreme deterministic regimes at the same logged sample size. Measure the precision–improvement tradeoff and failures as horizon length or probability imbalance grows. A bounded one-step odds ratio does not eliminate the exponential horizon problem.

**H4: useful improvement.** A policy chosen without access to confirmatory outcomes can improve success or reduce measured resources at a prespecified acceptable loss of success. A null result is informative; the evaluation framework must remain valid when no router beats the baselines.

**H5: deployment consistency.** Checkpoint, prompt, quantization or environment changes can break transport of an earlier value estimate. Demonstrate this as a sensitivity analysis, rather than interpreting an observed deployment difference as estimator bias under unchanged conditions.

## 6. Research aims

### Aim 1: establish the estimand and statistical guarantees

Develop the formal observation model, consistency and sequential exchangeability assumptions, positivity, g-formula, routing-level IPW, fixed-policy influence function, doubly robust remainder and cross-fitting conditions. Treat bounded variable horizons through absorbing states. Derive paired policy-contrast uncertainty and a finite-policy independent-evaluation guarantee. Correctly distinguish a frozen stochastic target from a target defined using the same unknown behavior distribution.

**Deliverable:** [theory.md](theory.md), with assumptions attached to every theorem and inherited results identified. Unresolved extensions are listed explicitly.

### Aim 2: identify when evaluation works and fails

Build an exactly enumerable sequential environment with prior-treatment-induced confounding, sparse rewards, budget termination and adjustable overlap. Compare regression, IPW, normalized IPW, doubly robust estimation, and deliberately naive analyses. Vary nuisance misspecification, horizon, sample size, hidden confounding, and deployment drift. Numerical unit tests check algebra and exact truth; Monte Carlo experiments check inferential behavior.

**Deliverable:** deterministic configuration files, seed manifests, full replicate output, diagnostics and plots. The initial implementation may cover a subset; [the protocol](experiment_protocol.md) distinguishes implemented pilots from required expansions.

### Aim 3: validate with actual open-weight agents

Start with a locally runnable tool-use microbenchmark for end-to-end logging and switching. Then use a frozen browser or software-engineering harness with objective task verification and competent models. Collect sequentially randomized logs, reserve fresh tasks for actual target-policy execution, and run a paired branch audit on a separate subset. Model weights and agent software licenses are recorded independently.

**Deliverable:** a reproducible pilot first, then a preregistered benchmark study. Tiny local models and hand-built arithmetic tasks establish feasibility only; they cannot establish broad agent-evaluation validity or state-of-the-art routing.

## 7. What must be true for the paper to be convincing

- Ground-truth simulation properties are known, including error in any Monte Carlo approximation.
- A sufficiently capable real agent has nondegenerate success and genuine model-dependent trajectories.
- The task split precedes policy selection and nuisance tuning; branches never cross folds.
- Evaluation probabilities refer to the actual executed assignment, including budget restrictions, availability, and fallbacks.
- A learned policy is frozen before confirmatory deployment; reported uncertainty is not a naive confidence interval after unrestricted winner selection.
- The analysis reveals low-support failures instead of hiding them through undeclared clipping or selective reporting.
- Fresh-policy execution supports or contradicts the causal estimates; trajectory divergence alone is not evidence of policy-value accuracy.
- The proposed routing method is compared to competent existing sequential routers and simple heuristics, not just always-small.

## 8. Manuscript status

The current priority is the [complete theory-first working manuscript](../manuscript/README.md), including proofs, references, and a prospective empirical section. New GPU/model experiments and manuscript empirical results are deferred at the author's request. The source and compiled draft are available in `manuscript/`. The original shorter concept below is retained as development history; the assembled manuscript is authoritative for current paper wording.

### Original manuscript concept

**Working title:** Dynamic Agent Regimes: Causal Evaluation of Model-Switching Policies in LLM Agents.

**Abstract draft, deliberately without invented results:** Multi-step language-model agents increasingly select different models during task execution. Earlier model choices alter later tool states, failures and routing decisions, making retrospective comparisons of switched and unswitched tasks difficult to interpret. We formulate model routing as a longitudinal intervention on versioned model configurations inside a fixed agent harness. We specify sequentially randomized evaluation designs, policy-value estimands, support diagnostics and doubly robust estimators, together with conditions for uncertainty quantification and independent policy improvement. An evaluation program combines known-truth simulations, prospective open-weight agent rollouts and controlled branch audits. Its central test is whether offline estimates and uncertainty agree with fresh policy executions under declared resource constraints. The resulting framework aims to distinguish reliable routing improvements from unsupported extrapolation and invalid trajectory replay.

Suggested paper structure: motivation and nearest work; intervention and target trial; identification and inference; exploration/support design; simulation; open-model study; limitations and reproducibility. For a methods venue, an application of existing estimators alone is unlikely to suffice. For an agent-evaluation venue, the benchmark, reliable ground truth, and actionable failure analysis may be the principal contribution.
