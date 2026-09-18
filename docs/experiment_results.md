# Completed experiments and their interpretation

All results below were actually generated on 2026-09-18. Synthetic results, real open-weight model observations, and remaining publication work are separated. The tests establish implementation identities and numerical correctness; they do not replace statistical assumptions or benchmark validation.

## Synthetic longitudinal evaluation

The main run used 400 independent Monte Carlo replicates, 1,500 trajectories per replicate, horizon 3, and three-fold cross-fitting. Baseline difficulty and current failure form four states. Previous model choice changes the next failure state; that state changes both future routing probabilities and future success. The terminal reward is success minus 0.06 per use of the stronger model. Known logging probabilities are bounded away from zero. Five fixed target policies were evaluated against exact Bellman values and separately generated 200,000-trajectory on-policy checks.

| Policy | Exact utility | Independent on-policy mean | Monte Carlo SE |
|---|---:|---:|---:|
| always_small | 0.315901 | 0.315930 | 0.001040 |
| always_large | 0.532492 | 0.532665 | 0.001012 |
| fixed_switch | 0.573582 | 0.574395 | 0.001030 |
| failure_escalation | 0.450386 | 0.450101 | 0.001137 |
| soft_escalation | 0.447130 | 0.447871 | 0.001129 |

`fixed_switch` at horizon 3 is small → large → large; failure-escalation selects the stronger model whenever the current failure indicator is 1. Soft escalation selects it with probability 0.1 after success and 0.9 after failure. These simulator policies are not identical to the pilot initialization rules, which start the failure policy with the small model.

With correct tabular Q models and known logging propensities:

| Policy | IPW RMSE | DR bias | DR RMSE | Nominal DR 95% coverage |
|---|---:|---:|---:|---:|
| always_small | 0.0456 | -0.0013 | 0.0409 | 0.958 |
| always_large | 0.0855 | -0.0019 | 0.0401 | 0.940 |
| fixed_switch | 0.0597 | 0.0006 | 0.0289 | 0.968 |
| failure_escalation | 0.0311 | 0.0033 | 0.0232 | 0.953 |
| soft_escalation | 0.0216 | 0.0025 | 0.0173 | 0.955 |

Nominal coverage near 0.95 has Monte Carlo SE about 0.011 with 400 replicates. Every replicate, summary and diagnostic is saved in [`results/simulation`](../results/simulation/). G-computation point estimates are provided, but no unsupported plug-in confidence intervals are fabricated. Uncertainty for its estimated Q functions was not implemented.

The misspecification experiment omits the evolving failure variable from Q fits and/or replaces the behavior probabilities by an incorrect constant 0.5. The following always-small results illustrate the estimator robustness and its limits:

| Q fit | Propensity | DR bias | DR RMSE | Nominal interval coverage |
|---|---|---:|---:|---:|
| correct | known | -0.0013 | 0.0409 | 0.958 |
| misspecified | known | -0.0013 | 0.0472 | 0.958 |
| correct | misspecified | 0.0021 | 0.0325 | 0.953 |
| misspecified | misspecified | 0.0888 | 0.0946 | 0.258 |

**Inference caveat:** with wrong propensities and consistent estimated Q fits, DR consistency does not imply validity of the empirical score-only standard error. First-order Q estimation can remain in the drift. Coverage in wrong-propensity cells is descriptive, not a claimed confidence-interval theorem. With known propensities and stable, possibly misspecified Q limits, score inference has a different and more favorable justification. The tabular backward regression implemented here claims the all-Q OR all-propensity consistency guarantee; arbitrary stagewise multiple robustness is not established for these fitted nuisances.

## Horizon and overlap stress

Each stress condition uses 200 replicates. The horizon-8 case also lowers the propensity floor from 0.15 to 0.01; evolving stage-dependent routing changes the propensity distribution. These conditions expose practical failures and do not isolate horizon from overlap effects.

| Condition | Policy | Median final-stage ESS | DR RMSE | Nominal coverage | Zero-ESS replicates |
|---|---|---:|---:|---:|---:|
| h3_n250 | always_small | 12.3 | 0.1159 | 0.885 | 0/200 |
| h3_n250 | failure_escalation | 73.2 | 0.0555 | 0.945 | 0/200 |
| h3_n250 | soft_escalation | 128.3 | 0.0416 | 0.960 | 0/200 |
| h6_n1500 | always_small | 4.0 | 0.4292 | 0.905 | 0/200 |
| h6_n1500 | failure_escalation | 88.4 | 0.0494 | 0.975 | 0/200 |
| h6_n1500 | soft_escalation | 268.4 | 0.0303 | 0.940 | 0/200 |
| h8_n1500 | always_small | 1.0 | 0.6359 | 0.860 | 97/200 |
| h8_n1500 | failure_escalation | 21.1 | 0.1107 | 0.950 | 0/200 |
| h8_n1500 | soft_escalation | 89.2 | 0.0533 | 0.950 | 0/200 |

The always-small target has median terminal ESS 1 and no target-compatible terminal trajectories in 97/200 horizon-8 replicates. Its DR RMSE is approximately 0.636 and nominal coverage is 0.86. Correct identification and nuisance specification do not create information where practical trajectory overlap is absent. Stochastic targets help here but are different interventions; they are not interchangeable replacements for unsupported deterministic policies.

![Simulation overview](../results/figures/simulation_overview.png)

## Honest policy selection

A separate 300-replicate simulation selected from the five prespecified policies using 750 training trajectories, then evaluated the selected policy with 1,500 independent trajectories. Mean training optimism was 0.0196; independent evaluation bias was -0.0017, RMSE 0.0342, and nominal coverage 0.940. Mean regret relative to the best policy in this finite menu was 0.0115. The mean true utility gain over always-small was 0.2462 in this constructed environment. This is a demonstration of honest evaluation, not evidence that an actual LLM router has been improved.

Selection counts: `{'always_small': 0, 'always_large': 81, 'fixed_switch': 218, 'failure_escalation': 1, 'soft_escalation': 0}`. Raw results: [`results/policy_learning`](../results/policy_learning/).

## Actual open-weight local-model pilots

Ollama 0.21.2 ran Qwen2.5 0.5B and 1.5B locally on an Apple M2 Max with 32 GB memory. Both selected model cards specify Apache-2.0 weights ([0.5B license](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct/blob/main/LICENSE), [1.5B license](https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct/blob/main/LICENSE)). Registry manifests, full model metadata and exact content digests are saved. No upstream Hugging Face source commit is claimed to have been recovered from the quantized registry artifact.

Each trajectory has three model decisions. The logger chooses the large model with probability 0.5 initially, then 0.75 after failure and 0.25 after success. Model history is transferred intact. The validator supplies truthful correctness feedback; after failure it reveals one partial multiplication result. The final endpoint is last-stage correctness. All stages execute, including after success, so switching can spoil an earlier correct answer. Four deterministic policies were run prospectively on evaluation tasks that are disjoint from logging tasks within each run.

The resource proxy is 0.01 per small call and 0.03 per large call; it is not dollars or energy. Recorded token counts and wall times are separate measurements. Loading/caching and task order affect timing. Every raw prompt, response, probability, seed, reward and model digest is retained.

| Pilot | Logged trajectories | Prospective policy trajectories | Actual model calls | Correct stage answers | Purpose/result |
|---|---:|---:|---:|---:|---|
| 1: modular, answer-only | 32 | 48 | 240 | 5/240 | Severe floor effect |
| 2: products, answer-only | 64 | 96 | 480 | 1/480 | Severe floor; retained irrelevant mod definition |
| 3: products, reasoning enabled | 32 | 48 | 240 | 194/240 | Exploratory harness calibration |

The first two pilots had zero final successes under every prospective policy. The second reused the answer-only scaffold and retained an irrelevant definition of mod. Both failures are preserved rather than removed. The third enabled explicit arithmetic reasoning in an unexecuted JSON string and removed the irrelevant definition. Prompt and task changes were driven by observed feasibility results, so these are not prespecified confirmatory experiments.

Some small-products task seeds are reused across the second and third calibrations. Within-run logging/evaluation separation holds, but these samples are not a fresh confirmation after harness selection. A publication study requires newly generated tasks disjoint from all calibration data.

Third-pilot direct prospective outcomes:

| Regime | Final successes | Mean proxy utility | Median trajectory wall seconds |
|---|---:|---:|---:|
| logging | 24/32 | 0.696 | 3.78 |
| always_small | 12/12 | 0.970 | 3.87 |
| always_large | 7/12 | 0.493 | 4.78 |
| fixed_switch | 12/12 | 0.930 | 7.39 |
| failure_escalation | 12/12 | 0.970 | 3.94 |

Pilot off-policy results are especially limited by sample size:

| Target | IPW proxy utility | Terminal ESS | Target-compatible terminal trajectories |
|---|---:|---:|---:|
| always_small | 1.080 | 10.0 | 10/32 |
| always_large | 0.279 | 2.3 | 3/32 |
| fixed_switch | -0.051 | 3.0 | 3/32 |
| failure_escalation | 1.063 | 13.0 | 13/32 |

**Interpretation:** these small pilot samples cannot establish policy superiority or validate asymptotic intervals. One first-pilot target had no compatible terminal trajectories; the summary explicitly flags it. Prospective differences can be noisy, and estimated importance-weight values need not lie in the outcome range. Paired task bootstrap intervals are supplied only as exploratory descriptions, without multiplicity adjustment or small-sample guarantees. No Q or DR result is fit to these tiny, high-dimensional model histories.

The raw-log audit reparses outputs and checks action probabilities, action/model alignment, model digests, stage order, previous correctness, exact reference answers, reward/cost identities, terminal outcomes and within-run task separation. All response content is treated as untrusted text. The collector currently persists events after each complete trajectory; it is not a durable pre-action or crash-safe production logger.

## Verification and remaining scope

The test suite checks complete path enumeration for IPW and both DR robustness branches, the necessity of the target-policy numerator, exact truth against independent policy simulation, reproducibility, positivity validation, strict response parsing, arithmetic answers, sequential feedback, and no reference answer in the initial fixture prompt. Additional theory tests verify finite-difference influence-function identities and the exact drift identity. All 16 tests passed in the final run before reporting.

See [`experiment_handoff.md`](experiment_handoff.md) for runnable commands, metadata interpretation, inference limitations, and concrete publication-scale follow-up. All completed runs are available under [`results`](../results/); none should be labeled a completed external-benchmark study.

An independent final-source rerun repeated all 400 main simulation replicates. The replicate table, summary, exact-truth/on-policy check and diagnostic files were byte-identical to the archived outputs, despite the recorded NumPy versions differing (2.4.1 versus 2.5.3). The [reproduction record](../results/reproduction_check.json) includes output and code hashes. This verifies this run; it is not a guarantee across arbitrary software/hardware changes.
