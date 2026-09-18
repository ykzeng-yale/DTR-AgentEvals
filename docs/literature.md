# Literature and claim audit

**Search date:** 2026-09-18. **Scope:** model selection inside a multi-step LLM agent; causal policy value, longitudinal off-policy evaluation (OPE), sequential randomization, and improvement of a routing policy. This is a focused, reproducible scoping review, not an exhaustive systematic review or a claim of priority. The bibliography contains 22 primary research references.

## Assessment

The defensible project is an **agent-specific design, estimation, and validation framework for dynamic model-routing policies**. It is not the invention of sequential routing, causal routing, policy-value estimation, or doubly robust longitudinal estimation. All four already have substantial antecedents. Dynamic treatment regimes (DTRs) and history-based RL OPE share the same policy-value identification problem when their interventions and assumptions coincide. Time-varying confounding is not a capability unique to DTRs.

The potentially useful contribution is the combination of a precisely frozen deployment intervention, randomized and auditable model-choice logging, terminal task outcomes, supported policy comparisons, cluster-aware uncertainty, and validation against newly executed trajectories. Whether that combination supports a publishable methodological advance depends on the completed proofs, comparison with existing estimators, and realistic experiments. Merely renaming a routing policy a DTR is insufficient.

## Evidence labels

- **F:** the paper's relevant full-text methods, limitations, or appendix were inspected.
- **A:** primary abstract/bibliographic record verified; no claim of a complete proof audit.
- **R:** author-linked repository or data page inspected; where stated, file manifest/API metadata inspected. This does not mean the software ran or the data reproduced the paper.
- **P:** proposal or inference made in this repository, not a result established by the cited source.

Paper versions are specified below. Later revisions must be checked before submission. Full-text access failures are reported as access failures, not evidence of paywalls. No third-party article text or datasets are redistributed in this repository.

## Closest work and bounded novelty matrix

| Reference, evidence, version | Verified scope | What our project must add or test |
|---|---|---|
| **Gonuguntla (2026), The Replay Gap** [paper](https://arxiv.org/html/2608.08239v1), F/R; v1 | Live SWE-bench forks demonstrate that model swaps change downstream trajectories. Section 2 discusses importance sampling/DR and leaves estimator design open. | Estimate supported policy values with calibrated uncertainty, and validate at useful success rates. |
| **Zhang et al. (2026), Budget-Aware Agentic Routing** [paper](https://arxiv.org/html/2602.21227v1), F; v1 | Per-step small/large model selection, path dependence, terminal feedback, soft/hard budgets, and boundary-guided RL training. | Independent off-policy evaluation and inferential validation of candidate routers; generic sequential routing is already covered. |
| **Tsiourvas, Sun, Perakis (2025), Causal LLM Routing** [paper](https://arxiv.org/html/2505.16037v2), F; v2; [NeurIPS proceedings](https://proceedings.neurips.cc/paper_files/paper/2025/hash/357774d53e5ee21c5f08ba779e3b5dd9-Abstract-Conference.html) | Observational, single-model-per-query feedback; causal utility estimation and regret-oriented learning. Section 2.1 specifies independent query-level observations. | Sequential decisions whose earlier model choices alter subsequent histories; do not claim causal LLM routing itself is new. |
| **Liu et al. (2026), ADWM** [paper](https://arxiv.org/html/2606.05558v2), F; v2 | Model-based offline agent evaluation using a learned diffusion world model. | Contrast with finite model-choice intervention and logged randomization; audit identification, not only ranking accuracy. See mathematical check below. |
| **Liu et al. (2026), Harness-Native Data Flywheel** [paper](https://arxiv.org/html/2607.11399v1), F/R; v1 | Full-state, step-level singleton/ensemble routing, outcome/cost records, OpenSquilla implementation. | Add assignment probabilities, explicit intervention versions, and inferential validation; state/action/outcome logging itself is already covered. |
| **Zhang, Feng, You (2025), Router-R1** [paper](https://arxiv.org/html/2506.09033v3), F/R; v3 | Sequential model invocation and aggregation using RL; QA evaluation and cost-aware rewards. | Evaluate learned policies on independent trajectories and distinguish model-only intervention from changing the coordinator. |
| **Agarwal et al. (2026), Switchcraft** [paper](https://arxiv.org/html/2605.07112v1), F; v1 | Tool-call routing with per-turn AST scoring. Appendix R explicitly separates this from end-to-end task completion. | Closed-loop terminal outcome evaluation; a per-turn correctness gain is not evidence of a regime-value gain. |
| **Ong et al. (2025), RouteLLM** [ICLR paper](https://proceedings.iclr.cc/paper_files/paper/2025/file/5503a7c69d48a2f86fc00b3dc09de686-Paper-Conference.pdf), A/R | Preference-trained strong/weak query routing. | Useful static-router comparator, not a substitute for longitudinal evaluation. |
| **Basu et al. (2024), SMART patient engagement** [paper](https://www.nature.com/articles/s41746-024-01330-2), F | Microsimulation comparing A/B and SMART designs for LLM-enabled patient outreach. | An actual agent-harness experiment. This is neither an executed model-switching benchmark nor proof SMART universally outperforms A/B. |
| **Liu, Luo, Zhu (2024), Best of Both Worlds** [paper](https://openreview.net/pdf?id=afu9qhp7md), A | An LLM/RL agent chooses clinical treatment in simulated glucose control. | Distinguish an LLM implementing a patient DTR from model identity being the treatment in an agent DTR. |

No exact match combining all proposed design and inference components was identified in the searches below. That bounded observation does not establish that none exists. The nearest papers often use different vocabulary, so DTR-keyword absence alone has little evidentiary value.

### Qualifications for the closest empirical motivation

Replay Gap reports roughly 900 total rollouts, including base and fork trajectories: these are not 900 independent tasks. Its six run pairs use 30 instances each, two quantized Qwen configurations, and low resolution rates (0–3%). Early-swap first-action divergence is 73.9%/76.7%, while replay validity is 3.2%/8.0%; these are setting-specific. Five outcome flips occur across three instances. Forks are selected at 30%/70% of completed base length, a retrospective branching design. A prospective policy must instead use observable time or event triggers. Shared-instance branches require grouped analysis. These data motivate validation but do not supply sequential support for arbitrary routers. [Methods, Tables 1–2, limitations](https://arxiv.org/html/2608.08239v1).

### Mathematical check on ADWM

The latest inspected ADWM version is v2 (2026-07-20). Its Section 4.1 and Appendix C claim exact target-law recovery after multiplying an exact behavior-trajectory law by target action probabilities while omitting the behavior denominator. That identity fails in general. **Our counterexample:** one decision, behavior probability of action 1 equal to 0.8, target probability 0.5, and no varying environment factor. The normalized proposed product gives action-1 probability 0.8, whereas the target is 0.5. Appendix C, Eq. (22), drops a remaining behavior-probability product. Therefore this repository does not inherit that exact-recovery claim. An empirical world-model comparator remains possible, with its actual implementation and bias checked separately. [ADWM v2, Appendix C](https://arxiv.org/html/2606.05558v2#A3).

## Theory and design foundations

| Primary reference | Evidence and contribution to this project | Boundary that must be preserved |
|---|---|---|
| **Robins (1986)**, [original paper DOI](https://doi.org/10.1016/0270-0255(86)90088-6) | A; longitudinal causal identification with treatment-confounder feedback. Original article bibliographic details verified; publisher extraction failed during this audit. | The g-formula is established theory, not a new agent theorem merely by relabeling variables. |
| **Robins, Hernán, Brumback (2000)**, [primary abstract](https://pubmed.ncbi.nlm.nih.gov/10955408/) | A; marginal structural models and inverse treatment weighting for time-varying confounding. | An MSM is a model for marginal counterfactual means; policy-value IPW need not fit an MSM. |
| **Murphy (2003)**, [paper](https://rss.onlinelibrary.wiley.com/doi/abs/10.1111/1467-9868.00389) | A; optimal DTRs, potential outcomes, and sequential decision rules. | Optimal actions depend on an appropriate future continuation, not a greedy observed terminal-mean regression. |
| **Murphy (2005)**, [author manuscript](https://people.seas.harvard.edu/~samurphy/papers/ExperimentalEvidence.pdf) and [record](https://pubmed.ncbi.nlm.nih.gov/15586395/) | A; sequential multiple assignment randomized trials for adaptive strategies. | Re-randomization must be specified among eligible histories; embedded regimes can share observations. |
| **Bang and Robins (2005)**, [primary abstract](https://pubmed.ncbi.nlm.nih.gov/16401269/) | A; doubly robust estimation including longitudinal settings. | Consistency under one correct nuisance family does not guarantee good finite-sample precision. |
| **Luedtke et al. (2017)**, [paper](https://arxiv.org/abs/1705.02459) | A; sequential double robustness in right-censored longitudinal models. | Stagewise robustness is stronger than generic all-outcome-or-all-treatment robustness; name the implemented algorithm accurately. |
| **Chaffee and van der Laan (2012)**, [paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC6084784/) | F; targeted estimation for DTRs in sequential randomized trials. | A one-step DR score is not automatically longitudinal TMLE; targeting and range restrictions matter. |
| **Kennedy (2019)**, [paper](https://arxiv.org/abs/1704.00211), [journal DOI](https://doi.org/10.1080/01621459.2017.1422737) | A; incremental propensity-score interventions and longitudinal inference. | Behavior-adaptive target policies depend on the data law; their influence function is not the fixed-policy influence function. |
| **Jiang and Li (2016)**, [paper](https://proceedings.mlr.press/v48/jiang16.html) | A; sequential doubly robust OPE and policy-improvement application. | RL OPE already estimates values of alternative sequential policies from logged trajectories. |
| **Thomas and Brunskill (2016)**, [paper](https://proceedings.mlr.press/v48/thomasa16.html) | A; weighted DR and combinations of model-based and importance-sampling estimators. | Self-normalization trades finite-sample bias for stability; report it separately from ordinary IS/DR. |
| **Kallus and Uehara (2020)**, [paper](https://www.jmlr.org/papers/v21/19-827.html) | F, relevant non-Markov/Markov efficiency sections; marginalized ratios and cross-fitting. | History-based and Markov models have different efficiency bounds. An arbitrary text embedding does not establish Markov sufficiency. |
| **Klasnja et al. (2015)**, [paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC4732571/) | F; micro-randomized trials with many decision points and proximal effect questions. | Frequent agent-step randomization resembles an MRT operationally; terminal policy value differs from a proximal excursion effect. |

The evidence labels concern this literature pass. The separate theory document derives the project's estimators and assumptions; citations alone do not certify those derivations.

## Audit of the supplied idea transcript

The attachment supplied a strong motivation but needs the following technical corrections before it becomes a paper.

1. **Complete the policy weight.** For a stochastic target policy, use

   $$
   W_T^\pi=\prod_{t=1}^{T}\frac{\pi_t(A_t\mid H_t)}{g_t(A_t\mid H_t)}.
   $$

   For a deterministic regime, the numerator is the indicator of adherence at each step. A denominator-only product does not identify an arbitrary regime value. Absorption after terminal completion and action availability must be encoded consistently.

2. **Correct the optimal-rule formula.** In general,

   $$
   d_t^*(h)=\arg\max_a Q_t^*(h,a),\qquad
   Q_t^*(h,a)=E\{R_t+V_{t+1}^*(H_{t+1})\mid H_t=h,A_t=a\}.
   $$

   The attachment's direct maximization of an observed terminal-outcome conditional mean leaves future routing at its observed distribution. It is not generally the optimal dynamic regime. Backward continuation, positivity, and identification assumptions are necessary.

3. **Use an accurate DTR–RL comparison.** Policy learning and policy evaluation are distinct in both literatures. OPE already addresses distribution changes induced by sequential policies. DTR terminology clarifies interventions and causal assumptions; it does not add a new identification principle absent from history-based OPE. See the foundation table.

4. **Define the intervention fully.** Model identity alone can represent treatment only when its conditional generation kernel and surrounding harness are stable. Checkpoint, quantization, decoding, prompt construction, context truncation, tool versions, and retry/stop rules belong in the intervention specification. Otherwise a nominally identical action hides different treatment versions.

5. **Randomization is the clean starting point.** A heuristic router that switches after failure is confounded in a naive switch/no-switch comparison. Complete histories and sequential exchangeability could identify values observationally, but cannot be presumed from high-dimensional embeddings. A randomized exploration harness with recorded assignment probabilities directly addresses this design problem.

6. **Keep estimands separate.** Terminal success, cumulative latency, tokens, dollar cost, and a chosen scalar utility answer different questions. A value contrast is population-average, not the counterfactual outcome of an individual failed task. Specify the task distribution and termination convention.

7. **Match claims to validation.** The closest-paper matrix and empirical qualifications replace the attachment's broad novelty and data-reuse claims. A released trajectory collection is not automatically a randomized longitudinal dataset. A SMART-like schedule and an MRT-like schedule can both be useful, but neither name guarantees adequate support or statistical power.

These corrections are our methodological analysis of the supplied equations and claims. They are not purported findings from an unperformed experiment.

## Code and data availability audit

| Work | Observed on 2026-09-18 | Reuse decision |
|---|---|---|
| Replay Gap | [Author GitHub](https://github.com/AshrithaG/replay-gap) accessible, MIT metadata; [HF dataset](https://huggingface.co/datasets/ashritha0907/replay-gap-trajectories) accessible, CC-BY-4.0 card. API manifest lists six trajectory `.jsonl.gz` files and `rollouts_index.jsonl.gz`. | Inspect and attribute; preserve instance/run/fork identities. File presence is verified; no claim here that downloaded contents reproduce results. |
| Router-R1 | [Official repository](https://github.com/ulab-uiuc/Router-R1) accessible, Apache-2.0 metadata; README links released models/datasets and training/evaluation scripts. | Useful open implementation; some documented inference configurations use API-served routing models. Replace with explicitly pinned open-weight backends for a fully local study. |
| OpenSquilla | [Author repository](https://github.com/TokenRhythm/opensquilla) accessible, Apache-2.0 metadata; original link redirects here. | Candidate harness only after instrumentation audit. The paper distinguishes the open LightGBM component from accumulated arena records/later policy generations served through its API. |
| RouteLLM | [Official repository](https://github.com/lm-sys/RouteLLM) accessible, Apache-2.0 license displayed; includes local-model guidance. | Static comparator; code execution, exact weights and dataset licenses still require verification. Default matrix-factorization/ranking examples require external embeddings, so audit dependencies for a fully open local comparison. |
| BAAR, Causal LLM Routing, ADWM, Switchcraft | No author implementation link was located in the inspected paper text and bounded title-plus-GitHub searches. | Mark implementation availability **unresolved**, not “closed source.” Do not substitute unrelated similarly named repositories as the authors' implementation. |
| SMART patient-engagement / clinical-treatment LLM papers | Scientific scope verified; no execution or code-reproduction audit conducted. | Background only, not proposed agent-routing data. |

For every downloaded resource used later, record the resolved commit/revision, access date, license, file checksums, row/task counts, and any missing logs before fitting estimators. A mutable `main` branch is not a reproducible experimental version.

**Subsequent repository audit:** the companion [external-data audit](external_data_audit.md) downloaded and inspected the six pinned Replay Gap files. It reports 896 trajectory rows, 56 distinct instance IDs, 179 base trajectories and 717 branches, with no top-level assignment-probability fields. These are our file-level observations, not an independent replication of the paper. Use that audit and its machine-readable results for the concrete import decision; the source-availability table above records the preceding literature check.

## Search log and limitations

All searches below were performed on **2026-09-18** using web search, arXiv primary records/full-text HTML, primary publisher/proceedings records, and author-linked repository/data pages. Search results from summaries, blogs, and literature aggregators were used only to find primary sources, not to support technical claims.

| Search family | Representative exact query / action | Outcome |
|---|---|---|
| Exact topic | `"dynamic treatment regime" "LLM" agent evaluation`; `"SMART" "LLM" "sequential" trial agent`; `"sequential multiple assignment" "language model"` | Clinical DTR/LLM and outreach SMART hits; no exact verified internal model-switching DTR paper in these results. |
| Known nearest papers | Open arXiv `2608.08239`, `2602.21227`, `2505.16037`; inspect full texts and submission histories | Confirmed motivation and scope; later Causal Routing v2 checked. |
| Agentic routing | `"Agentic Routing" "Harness-Native"`; `"Router-R1"`; follow Replay Gap citations to `2605.07112` | OpenSquilla, Router-R1, and Switchcraft inspected; versions noted above. |
| Agent OPE | `"Autoregressive Diffusion World Models" "Off-Policy"`; latest arXiv `2606.05558v2` | ADWM verified; Appendix C identity checked with counterexample. |
| SMART overlap | `"SMART" "LLM" "outreach"`; `"Simulating A/B testing versus SMART designs for LLM-driven patient engagement"` | Original npj Digital Medicine paper inspected; simulation status retained. |
| DTR foundations | `Murphy 2003 optimal dynamic treatment regimes 65 2 331 355`; `Murphy 2005 experimental design development adaptive treatment strategies 1455`; `Robins 1986 new approach causal inference mortality healthy worker survivor effect` | Exact bibliographic identities and primary links resolved. |
| Estimation | `"Sequential Double Robustness" Luedtke Sofrygin Carone`; `"incremental propensity score" intervention Kennedy 2019`; `"Targeted Maximum Likelihood Estimation for Dynamic Treatment Regimes"` | SDR, incremental, and longitudinal targeted-estimation anchors resolved. |
| RL comparison | `"Double Reinforcement Learning" "Non-Markov" Kallus Uehara`; primary PMLR pages for Jiang/Li and Thomas/Brunskill | Existing history-based OPE theory makes broad causal-estimation novelty untenable. |
| Design comparison | `"Micro-randomized trials" 2015 Klasnja Hekler` | MRT distinction added. |
| Reproducibility | Exact paper title + `github`; GitHub repository APIs; Hugging Face file manifest API | Accessible releases separated from unlocated releases; no empirical replication inferred. |

Limitations: this search did not screen every workshop submission, thesis, unpublished implementation, or non-English source; citation snowballing was bounded to closest methods. The OpenReview forum for the clinical-treatment LLM paper encountered a browser challenge, but its PDF and author-institution record were available. Some publisher pages failed extraction; metadata-only verification is labeled. Before manuscript submission, repeat the exact-topic and citation-forward searches, inspect any newer paper versions, and expand the review if a priority claim is proposed.

## Implications for experiments

These are **P**, choices proposed by this project rather than literature-established results:

- Use a small finite pool of frozen open-weight deployment configurations. Intervention probabilities refer to choosing a configuration, not to reproducing an exact generated string.
- Start with two or three prospective decision points and adequate randomization. Escalate to long horizons only after diagnosing support and task-level effective sample size.
- Compare direct on-policy execution, naive historical switching comparisons, valid policy IS, self-normalized IS, sequential outcome regression, and appropriately named DR estimators. Add a static router and a learned sequential router when feasible.
- Separate task-level training, policy selection, and final evaluation. Keep all repeated seeds and branches for one task together; account for shared-prefix dependence.
- Treat live or faithful branched execution as an additional noisy reference estimate, not deterministic individual ground truth. Check same-configuration branches and environment restoration.
- Report value error, interval coverage, policy-ranking error, cost, positivity diagnostics, and computation. A ranking metric alone cannot establish causal calibration.
- Stress-test unrecorded router inputs, state compression, unsupported switches, checkpoint changes, sparse reward, budget-induced termination, and informative failure of the harness.

The publication claim should be stated only after these checks. A negative result—e.g., ordinary DR failing at realistic horizons despite model-level overlap—would still be informative if the design and uncertainty evaluation are credible.
