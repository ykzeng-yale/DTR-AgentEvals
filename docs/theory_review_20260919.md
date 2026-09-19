# Independent mathematical review — 19 September 2026

**Scope.** This review examines the mathematical observation model, identification, influence functions, remainders, sampling assumptions and decision guarantees. It does not review or extend the archived model experiments. New model/GPU experiments and Monte Carlo sweeps are deferred. The review used the Fan causal-methods workflow and independently inspected `docs/theory.md`, the core estimator implementation, and the theorem-algebra tests. The review is an internal technical assessment, not external peer review or formal proof-assistant verification.

**Overall assessment.** The core fixed-policy g-formula, macro-action likelihood ratio, efficient influence function, exact drift identity, and finite-class concentration constants are correct under the stated model. The distinction between a fixed target and an unknown-behavior-dependent target is especially important and is handled correctly. The primary mathematical risk was overextending task-cluster variance arguments to selected branch data; the revised Section 4.1 now explicitly restricts the claim to valid root-episode marginals. The proposed extensions need their own observation laws and cannot inherit validity solely from the existing episode theorem.

## 1. Exact DR drift: algebra confirmed; rates retain their own assumptions

**Status: resolved; no algebraic correction required.** Equation (10) has the correct sign, previous-stage fitted weight, and true target-continuation regression. Starting with `e_t = Qbar_t - Q_t` and `d_t = sum_a pi_t e_t`, the score bias telescopes into

\[
\sum_t E\{\bar W_{t-1}d_t-\bar W_t e_t(H_t,A_t)\}.
\]

Conditioning the second term on the full pre-action history gives the displayed factor `(bbar_t-b_t)/bbar_t`. The dependence of `Wbar_{t-1}` on earlier fitted propensities is not a missing cross-stage term; it is already present in the exact identity. Outcome regression errors are measured against the true target continuation, not a regression target corrupted by downstream fitting errors.

The Cauchy–Schwarz bound is sufficient under uniform lower bounds for fitted denominators and bounded previous weights. It is deliberately stronger than support needed for identification. Conditional-mean versions on histories/actions that are never reached under the target can be assigned arbitrary bounded extensions; the identities depend only on target-relevant support. A manuscript should make that convention explicit if it uses unweighted behavior-history norms over the entire observed history space.

The code correctly describes ordinary all-Q-or-all-propensity robustness. It does not establish algorithmic sequential multiple robustness for arbitrary patterns of recursively misspecified Q fits.

## 2. Fixed-policy EIF and efficiency with known randomization: confirmed

**Status: resolved.** In the full-history model the baseline term and the weighted transition residuals belong to orthogonal baseline/transition tangent spaces. The fixed-policy functional has zero derivative in the behavior tangent directions. Its canonical gradient consequently remains canonical when the behavior law is fixed by design.

The conclusion is relative to this statistical model. It does not imply the same efficiency bound in a smaller true Markov model, in a cluster model with extra restrictions, or in a model with a known deterministic task list. A compressed embedding is not evidence for a Markov restriction.

A useful boundary check is `delta=1`: fixing the target at the known behavior router and defining the target as the unknown behavior router can give the same numerical value at one law but different derivatives. A one-stage exact example in `tests/test_paper_theory.py` has fixed-known-router EIF variance 0.09 and behavior-adaptive observed-mean EIF variance 0.25. This is a mathematical illustration, not a statistical experiment.

## 3. Cross-fitting and asymptotic intervals: correct conditional claims, not universal guarantees

**Status: resolved for the stated sufficient conditions; application verification remains required.** Theorem 4 separately assumes score convergence in `L2`, negligible drift, and variance consistency. Together with independent evaluation units and a fixed number of nonempty folds, these support the foldwise conditional empirical-process argument. Training includes preprocessing, representation learning, and nuisance tuning; correlated records from one task must remain in one fold.

The warning about a wrong propensity limit and root-n Q estimation is essential: an order-root-n drift can contribute to the limit even while point consistency holds. Cross-fitting does not remove that contribution. The known-randomization corollary is valid when the score converges to a deterministic square-integrable limit, including a misspecified Q limit; efficiency need not follow.

For a policy learned on independent training data, inference concerns its conditional value after freezing that policy. If the paper invokes an unconditional limit while the learned target changes with sample size, it needs an additional stability or triangular-array argument. The present theorem must not be described as generic inference for a population-optimal rule near ties.

## 4. Clusters and branches: substantive sampling correction now made

**Status: resolved in revised Section 4.1; no generic clustered-branch EIF claimed.** The earlier text permitted branch dependence without explicitly requiring a valid root-to-terminal marginal for every score. That was too broad. A cluster sandwich variance can account for dependence but cannot repair an incorrect marginal target or branch-selection bias.

The revised version requires i.i.d. task clusters, fixed replicate count, valid behavior-law root-episode marginals, and nuisance fitting outside the held-out cluster. Under corresponding cluster-scale score-convergence/drift assumptions, the average episode contribution is a valid cluster influence contribution. This is not automatically a claim of semiparametric efficiency in every restricted joint cluster model.

For unequal counts, outcome-selected repeats, or selected continuations, define task- versus episode-weighted population targets and derive the sampling correction first. An exact two-state counterexample in the new tests has root mean 0.5 and selected-branch mean 0.8; averaging or clustering the selected branches does not change 0.8 into the root estimand.

## 5. Held-out finite-policy improvement certificate: constants confirmed

**Status: resolved; explicit support now added.** The score bound in equation (16) follows from the bound `2(T-t+1)r` on each residual. A policy-score difference lies in an interval of width `4M`; Hoeffding therefore gives `2 exp{-n u^2/(8M^2)}`. The union-bound radius in equation (17) is correct.

The theorem needs all of its stated restrictions: known actual assignment probabilities; sequential target support for every candidate and baseline; bounded scores; independently frozen candidates and outcome fits; and independent evaluation episodes or valid bounded independent cluster means. A bound on ratios only along observed actions is insufficient if a target assigns probability to an action with zero logging support. That support requirement is now explicit.

The conclusion is a bound on the probability of falsely certifying positive expected utility. It is not protection of every task, a guarantee for unknown costs, or permission to generate new policies after examining the evaluation sample. Ordinary cross-fitting across the evaluation set does not restore the independent-score finite-sample proof. Estimated-propensity use needs a separately controlled bias term.

## 6. Behavior-adaptive incremental target: EIF confirmed; estimator theorem deliberately incomplete

**Status: derivative resolved; a general unknown-behavior estimator theorem remains outside scope.** The extra term in equation (21) has the correct occupancy weight `W_{t-1}`, derivative `delta/Z^2`, target-continuation action contrast, and centered action `(A-b)`. The policy derivative changes future occupancy through the target continuation, so a second ad hoc downstream correction should not be appended.

The construction agrees with the chain-rule logic for propensity-dependent interventions in [Kennedy's primary paper](https://arxiv.org/html/1704.00211). At structural zero/one propensities, define the centered action contribution as zero and avoid assigning scientific meaning to an unidentified off-support Q contrast. The bounded-delta ratios on realized support remain finite. Bounded payoff and finite horizon supply square integrability under the stated model.

The document correctly distinguishes: a known randomized reference; an independently learned, frozen reference; and a target that depends on the same unknown population behavior law. For the last case, a completed estimator requires a target-specific remainder, nuisance conditions and variance proof; the fixed-policy rate theorem cannot simply be reused. No claim of ordinary robustness to arbitrary misspecification of the behavior law is justified because that law defines the target.

## 7. Prospectively eligible routing opportunities: extension conditions to retain

**Status: reviewed design and proof structure; final extension text subject to the closing addendum.** A likelihood-ratio product can contain at most K nontrivial factors when intervention eligibility is determined from pre-action history, there are at most K eligible decisions, and behavior and target agree at all other decisions. Between-decision model/tool evolution remains part of the unchanged conditional kernel.

The relevant count is the number of routing opportunities at which assignment distributions can differ. It is not the realized number of model-label switches: retaining the same model can still have a nonunit assignment ratio. Eligibility must not depend on a later success, the realized future trajectory length, or whether the proposed switch eventually worked. A policy-dependent eligibility state is allowable if it evolves prospectively as part of history.

A reduction in the number of nontrivial likelihood factors does not by itself bound unbounded costs or prove improved statistical efficiency. Reward ranges, root distributions, support and all inference conditions still require their own statements.

## 8. Transported branch contrast and augmentation: distinct estimand required

**Status: proposed algebra confirmed; observation-law conditions are indispensable.** Let a single prefix H per independent unit have reference law P_b and desired law P_q, with known density ratio w. Let branch selection satisfy `S independent of D given H`, with known probability e positive wherever w is positive; D is the paired difference from actually executed continuation policies. For a frozen m, the proposed score

\[
U=w(H)\left[m(H)+\frac{S}{e(H)}\{D-m(H)\}\right]
\]

has mean `E_q mu`, where `mu=E(D|H)`. This remains true if m is wrong. Common random seeds may alter the conditional variance of D while preserving its mean, provided each continuation marginal is valid.

A routing prefix ratio equals the required w for a properly specified fixed-time or stopping-time prefix experiment. It is not automatically the ratio for a collection restricted to failures, surviving tasks, convenience snapshots, or many variable-count prefixes per root. Such restriction changes the history law and potentially its normalization. A branch continuation contrast is not the value of changing the policy that generated earlier prefixes unless the appropriate target-prefix law is also identified.

Complete observation of D after branch selection and faithful environment restoration are part of this observation model. Missing outcomes after selection need a separate observation correction. Costs of running both experimental branches are experimental design costs, not automatically costs of deploying either continuation policy.

## 9. Branch variance and cost allocation: exact algebra confirmed, oracle scope required

**Status: algebra and interior allocation checked exactly; estimation of the oracle quantities is deferred.** With `v(H)=Var(D|H)`, the proposed variance decomposition is

\[
\operatorname{Var}(U)=\operatorname{Var}_b\{w\mu\}
+E_b\left[w^2\left\{\frac{v}{e}
+\left(\frac1e-1\right)(\mu-m)^2\right\}\right].
\]

The new test enumerates the entire finite `(H,S,D)` space with nonconstant transport weights and incorrect m and matches this expression. Thus variance minimization for a fixed possibly incorrect m uses the residual second moment `v+(mu-m)^2`, not v alone. Under an expected design-cost constraint `E_b[c e] <= B`, the interior rule is proportional to `|w| sqrt{E[(D-m)^2|H]/c}`. With `m=mu`, this reduces to the usual variance-based allocation. Upper truncation at one and any exploration floor are necessary; feasibility of the cost budget and zero-residual strata need explicit cases.

The optimality is conditional/oracle optimality for this score, this prefix population, this cost model and this fixed independent-unit sampling design. It is not an efficiency-optimal global agent experiment, and replacing unknown moments by in-sample estimates requires its own guarantee. Allocation adapted across observed branches moves beyond the simple i.i.d. proof unless fitted on an independent pilot and frozen.

## 10. Conditional-kernel perturbation bound: correct coupling argument with common payoff

**Status: reviewed formula; final extension text subject to the closing addendum.** On a common history/action space, take the same initial law, fixed measurable routing policy and terminal trajectory payoff g. If every relevant one-step conditional kernel has total variation distance at most epsilon_t, using the convention `TV(P,Q)=sup_A |P(A)-Q(A)|`, maximal coupling gives

\[
|E_Pg-E_{P'}g|\le \operatorname{osc}(g)
\left\{1-\prod_t(1-\epsilon_t)\right\}.
\]

The coefficient is the payoff range, not an absolute-value bound that silently loses a factor of two. A deterministic finite-state enumeration in the new test attains this bound for an absorbing perturbation, showing that it is not merely a loose union-bound identity.

A policy improvement robust to changes in both candidate and baseline requires subtracting both transport-error bounds. Small observed divergence in a finite sample does not supply uniform kernel-TV bounds without an additional statistical argument. Different task populations, reward functions, or nonaligned history representations require extra terms or a different theorem. This sensitivity result cannot be presented as causal transport identified from the old logs alone.

## 11. Source implementation and manuscript claim boundary

**Status: resolved by retaining the distinction.** The core implementation matches the additive-reward fixed-policy score and computes the actual target numerator. Its tabular state is sufficient only for its constructed simulator; a generic compressed LLM history is not thereby validated. The existing code has no general estimator for unknown-behavior incremental targets, the new branch design, arbitrary clustered outcome-dependent sampling, or longitudinal missingness.

The paper may present rigorously proved population identities and experimental designs without pretending that every theorem has a deployed estimator or an empirical validation. Existing archived pilots remain archival facts, but the requested manuscript's empirical methods/results should remain deferred. No new computational experiment is needed to assert a proved algebraic result.

## 12. Attribution, regularity and remaining boundaries

**Status: conditions to preserve throughout drafting.** The established fixed-policy results are inherited from longitudinal causal inference and OPE. The opportunity-count argument is a change-of-measure specialization; the branch allocation is a conditional Neyman-type design; the perturbation result is a coupling/simulation bound. Their agent-specific integration can be useful without claiming that these general mathematical ideas are newly invented.

For theorem-ready presentation, state finite action sets, measurable policies/kernels, existence of regular conditional distributions (standard Borel histories suffice), finite horizon, and measurable tie breaking. Keep i.i.d. tasks distinct from fixed benchmark inference, adaptive across-task routers, and shared-environment interference. Distinguish model-use utility costs from resource consumption incurred solely to evaluate policies.

Unresolved scientific questions include unmeasured routing information, high-dimensional nuisance learning at feasible sample sizes, model/harness drift without externally justified bounds, observational branch selection, adaptive-design inference, censoring, unrestricted optimal-policy nonregularity, and empirical usefulness on competent agents. These are outside the proved claims, not gaps that should be filled with confident wording.

## Verification record

Only small deterministic CPU checks were performed for this review. The seven new checks in `tests/test_paper_theory.py`, together with the six existing exact derivative/remainder checks in `tests/test_theory_identities.py`, passed: **13 passed**. The command was:

```sh
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_paper_theory.py tests/test_theory_identities.py
```

No Monte Carlo sweep, model inference, GPU workload, or new benchmark experiment was run. Existing source and results were not modified by this reviewer; only this report and `tests/test_paper_theory.py` were added. The theory author separately made the two resolved wording corrections noted in Sections 4 and 5.

## Closing addendum: exact extension text reviewed

The reviewer subsequently read both `docs/theory_extensions.md` and `manuscript/sections/extensions.tex` in full. The exact eligible-opportunity factorization, the sharper second-moment bound `E(W_K^2) <= c^K`, the selected-branch mean and variance, the independent two-sample corollary, clipped cost allocation including its saturation cases, and the conditional-kernel coupling bound are correct under their written hypotheses. The extensions explicitly resolve the substantive prefix-law, training-independence, residual-moment, and payoff-range concerns above. They correctly avoid claims of global semiparametric efficiency or empirically established improvement.

Two additional deterministic tests verify the independent two-sample branch variance by joint enumeration and show that the opportunity second-moment bound can be sharp even with zero realized model switches. The full theorem-only check now has 13 passing tests.

One minor notation convention was requested from the theory author: because Theorem B permits `e=0` when `w=0`, the score and weighted variance integrands must be defined as zero on target-null prefixes, rather than leaving literal products involving `0/0`. Requiring positive `e` everywhere would be an alternative, but the zero convention preserves the intended design. The explicit zero convention and the restriction of division identities to positive-weight prefixes are now present in both extension files, so this issue is resolved. No unresolved algebraic error was found in these three extensions. Their practical assumptions and empirical usefulness remain unverified and appropriately deferred.

## Final assembled-manuscript consistency pass

The reviewer then read `manuscript/main.tex` and every included section, including the converted foundation proofs and the deployment-adjusted certificate. This was a read-only source review; the coordinating author handled compilation and rendering. The earlier conversion repairs to `o_p(1)` and the continuation contrast `Q_t(1)-Q_t(0)` are present and correct.

Three substantive or reproducibility findings were communicated and resolved in the source:

1. **Continuous-history support.** “Histories with positive probability” could be read literally and become vacuous for continuously valued history components. The manuscript and theory document now state support for `P^pi_{H_t}`-almost every history. This is the appropriate measure-theoretic condition.
2. **Cross-fit proof scaling.** The proof bounds each fold empirical-process term at the total-sample root-n scale. Its clean sufficient condition, now added, is that every fold's size divided by n tends to a strictly positive constant. Alternatively one could retain arbitrary fold sizes and explicitly track weighted fold contributions, but the balanced-fraction condition is adequate here.
3. **Portable bibliography input.** The initial manuscript referred to a bibliography file absent from its own directory. The build script now invokes `prepare_bibliography.py` to generate the manuscript bibliography from the canonical repository bibliography, retaining references while removing internal audit-note fields from the display. This source-path repair was verified by inspection; compilation validation is the coordinating author's separate check.

The author also added the requested global standard-Borel, measurability, finite-action, measurable tie-breaking and null-support-version conventions. The support, cluster and branch hypotheses are now consistent across the foundation and extension sections. The literal theorem-number range in the incremental-reference paragraph is currently numerically correct; symbolic references were recommended to protect it against later renumbering.

The deployment certificate is algebraically and probabilistically correct. On one simultaneous lower-coverage event for all logging-system contrasts, subtracting the candidate and baseline sensitivity allowances gives a simultaneous deployment-system lower bound. Selection on this event does not invalidate coverage. If estimated sensitivity allowances have their own simultaneous coverage event, the stated `1-alpha-beta` union-bound conclusion requires no independence between the two events. It remains conditional on actual validity of those allowances and concerns expected utility, not per-task safety.

A source-level cross-reference audit found 74 distinct labels with no duplicates and all 48 symbolic references resolved. All 21 cited keys were present in the canonical bibliography at the time of checking. The abstract, introduction, empirical-plan section, discussion, and status statement consistently defer empirical performance claims; none presents archived development runs as results of the proposed final study. No further substantive mathematical inconsistency or empirical overclaim was identified in the assembled source after the above corrections.
