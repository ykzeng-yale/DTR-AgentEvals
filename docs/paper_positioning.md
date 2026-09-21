# Theory-paper positioning and claim map

**Updated 21 September 2026.** The 35-page manuscript contains theory and an archived descriptive coding case,
including unfavorable and unresolved comparisons. It does not claim validated confirmatory improvement, lower
evaluation cost or submission readiness. The [new experimental-design review](literature_design_review_20260921.md)
supplements the broader [literature audit](literature.md); neither is an exhaustive novelty certification.
The [v2 protocol](experiment_protocol_v2.md) is prospective and unrun.

## Scientific contribution and audience

The paper addresses a concrete policy-evaluation problem: infer the value of changing which versioned model configuration is invoked at eligible points in an agent's evolving execution. The proposed contribution combines an explicit intervention contract with results that connect the execution process, logged routing probabilities, branch validation, and changes in execution kernels. The mathematical work should be presented as a self-contained synthesis with carefully specified adaptations. A methods-journal submission would still need an assessment of whether those adaptations constitute a sufficient methodological advance; correctness and a complete manuscript do not establish novelty or acceptance.

Suggested contribution sentence:

> We formulate versioned stochastic model routing as a longitudinal intervention and establish results linking prospective routing opportunities, selection-aware branch validation, and execution-contract sensitivity, within a framework for supported policy evaluation and improvement.

This sentence describes the paper's scope without claiming a new g-formula, influence function, optimal-allocation principle, or simulation lemma.

## Inherited versus project-specific claims

| Component | Established foundation | Project-specific result or design choice | Wording and limits |
|---|---|---|---|
| Sequential model routing | Query routing, multi-round routing, budget-aware agentic routing, and harness-based routers are established; see the closest-work matrix in `literature.md`. | A versioned macro-action contract and an evaluation question about complete policy execution. | Say “we formulate and evaluate”; do not claim to introduce agent routing or causal routing generally. |
| Dynamic regimes and history-based OPE | Robins; Murphy; Jiang and Li; Kallus and Uehara. | A common observation model for model configurations, tool/environment responses, bounded termination, and explicit feasible actions. | DTR and OPE share the relevant identification machinery. Do not claim DTR uniquely handles treatment-affected histories. |
| Fixed-policy value inference | Longitudinal weighting, DR estimation, influence functions, cross-fitting, and product-remainder arguments. | Self-contained proofs for the declared observation model and explicit conditions separating consistency, normality, and efficiency. | Attribute the machinery. Do not describe the implemented estimator as algorithmically sequentially doubly robust without a proof for the fitting procedure. |
| Eligible-decision reduction (A) | Conditional factorization and change of measure for sequential processes. | Exact equivalence of the fine execution and retained boundary-history process when eligibility is determined before assignment, actions change only at eligible points, and intervening kernels agree. | The likelihood-ratio product counts eligible opportunities, not realized model changes. Bounded event times and complete histories suffice; do not advertise an optional-stopping theorem or a generally sufficient compressed state. |
| Supported improvement | Known exploration, finite-class concentration, sample separation, and incremental interventions (Kennedy). | A prespecified supported policy class, independently evaluated with a conservative finite-class certificate. | A population-average certificate under explicit boundedness and overlap conditions; not taskwise improvement or a guarantee for unrestricted post-selection. Fixed-reference and unknown behavior-adaptive targets require different derivatives. |
| Target-prefix branch score (B) | Importance weighting and augmented inverse-probability estimation under selective observation. | For known prefix ratio `w`, known positive branch-selection probability `e`, a frozen augmentation `m`, and paired live contrast `D`, use `U = w[m + S/e (D-m)]` for the target-prefix continuation contrast. | Selection must be conditionally independent of the potential branch contrast given the recorded prefix; moments and prefix support are required. Arbitrary branch collections do not identify full root-to-terminal policy values. |
| Branch variance and allocation (B) | Classical variance/cost allocation (Neyman); prior optimal policy-evaluation data collection (Li et al.); sampling design matters in OPE (Kallus et al.). | Explicit variance `Var(w mu) + E[w²{v/e + (1/e - 1)(mu-m)²}]`, where `mu = E[D|H]` and `v = Var(D|H)`, and constrained selection minimizing it. | Oracle allocation is proportional to `|w| sqrt({v + (mu-m)²}/c)`, clipped to the declared floor/cap; when `m=mu`, this reduces to `|w| sqrt(v/c)`. Do not claim globally optimal sequential exploration or a new efficiency bound for arbitrary branch trees. |
| Execution-kernel sensitivity (C) | Simulation-lemma and coupling arguments (Kearns and Singh; Lobel and Parr). | For a common initial law and target policy, bounded complete-trace payoff range `R`, and stagewise uniform kernel-TV bounds `epsilon_j`, value drift is at most `R[1-product_j(1-epsilon_j)]`. | A finite-horizon full-history adaptation. It propagates specified discrepancies; it does not estimate them or identify unseen model versions. A local empirical discrepancy is not automatically a uniform bound. |
| Empirical usefulness | No theoretical argument alone determines real-agent precision, cost, or performance. | Archived descriptive comparisons are in the paper; revised known-truth and fresh-policy validation remain planned. | Separate observed numbers from validated inference. Preserve adverse results and restrict new claims to the tested class, harness and precision. |

## Closest comparisons to keep visible

- **Sequential agent routing:** BAAR and harness-based routing make sequential model selection a direct antecedent, not a novelty claim. The distinction to test is the inferential evaluation contract and validation against actual policy execution.
- **Causal query routing:** Causal LLM Routing is a direct causal precedent with a per-query decision setting. The current target is a longitudinal regime under treatment-affected histories.
- **Replay and model-based evaluation:** Replay Gap is direct motivation for downstream-state validity. ADWM is adjacent model-based OPE; the earlier audit questions one exact-law derivation, so no theorem here relies on its correctness.
- **Optimal evaluation designs:** Li et al. (2023) already derive allocation designs for efficient sequential policy contrasts. Our selection problem conditions on an available prefix distribution and chooses where to purchase paired continuation measurements.
- **Model mismatch:** Lobel and Parr (2024) sharpen simulation-lemma bounds in discounted MDPs. The present adaptation concerns finite complete-history kernels and a bounded payoff on the entire trace; it is not a new general simulation lemma.

## Targeted primary-source supplement

The following sources were verified on **19 September 2026**. Statements below record what was inspected; an accessible abstract is not labeled a complete paper review.

| BibTeX key | Primary record and verification depth | Relevance and boundary |
|---|---|---|
| `kearns2002near` | [Publisher record](https://link.springer.com/article/10.1023/A:1017984413808); title, authors, journal, volume, pages, and DOI verified. [Author paper copy located](https://ics.uci.edu/~dechter/courses/ics-295/winter-2018/papers/KearnsSinghE3.pdf). | Simulation-lemma lineage. No assertion that the paper proves our exact full-history trace-payoff formula. |
| `lobel2024simulation` | [Official RLJ record](https://rlj.cs.umass.edu/2024/papers/Paper106.html), [full article](https://rlj.cs.umass.edu/2024/papers/RLJ_RLC_2024_106.pdf); model assumptions and Sections 2–3 inspected. | Discounted MDP simulation bound with geometric overlap accumulation. Supports attribution of the coupling/overlap principle, while our theorem states its own finite-horizon assumptions. |
| `neyman1934representative` | [Publisher DOI](https://onlinelibrary.wiley.com/doi/10.1111/j.2397-2335.1934.tb04184.x); bibliographic metadata verified; [original scan located](https://www.stat.cmu.edu/~brian/905-2008/papers/neyman-1934-jrss.pdf). The scanned proof was not reconstructed. | Classical allocation antecedent. Our KKT calculation, not an unverified quotation from the scan, establishes the exact selection rule used here. |
| `kallus2021multiple` | [Official ICML/PMLR record](https://proceedings.mlr.press/v139/kallus21a.html); authors, pages, and abstract inspected; attempted full-PDF retrieval did not succeed in the browsing tool. | Efficient OPE under stratified samples from multiple logging policies; supports the general relevance of sampling design. Does not establish independent observations for shared-prefix branches. |
| `li2023allocation` | [Official NeurIPS record](https://proceedings.neurips.cc/paper_files/paper/2023/hash/98d0ad88db1e51bd0aa341a823290ece-Abstract-Conference.html), [full author manuscript](https://arxiv.org/pdf/2311.02532); Sections 2–3 inspected. | Designs for efficient contrasts between constant-action policies in sequential models, including a non-Markov analysis. This is a strong antecedent against any generic claim to invent optimal sequential data collection. |

Searches included “simulation lemma Kearns Singh 2002,” “An Optimal Tightness Bound for the Simulation Lemma,” “off policy optimal experimental design,” “Optimal Treatment Allocation for Efficient Policy Evaluation in Sequential Decision Making,” “sequential randomization stopping time dynamic regime,” and “Neyman 1934 representative method.” The stopping-time search did not identify a necessary special novelty claim; existing sequential-experiment foundations and the direct bounded-process proof suffice for the intended attribution. Search non-discovery is not evidence that no closer antecedent exists.

## Remaining publication work

1. Independently review all manuscript proofs, including the precise branch-selection model, zero-variance allocation cases, and the meaning of eligibility measurability.
2. Check manuscript and code consistency. A theoretical estimator or design is not implemented merely because it is described in prose; implementation claims must name the corresponding executable path and tests elsewhere in the repository.
3. Complete the prespecified simulation and live-policy validation studies before adding empirical conclusions. GPU studies remain deferred in the current manuscript task.
4. Choose a target venue and assess contribution sufficiency. This draft is journal-neutral; it makes no unsupported claim that the theory alone meets a particular journal's novelty threshold.
