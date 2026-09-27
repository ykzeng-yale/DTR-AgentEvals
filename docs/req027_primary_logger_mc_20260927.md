# DTR-REQ-027 — Mac mini synthetic logging-design experiment

The author explicitly requested experiment execution by the Mac mini's Codex, without Claude Code there. Codex scientific leadership remains in the local DTR chat. The dedicated remote chat is `01a0e05b-a10e-7d42-9101-aa656ef5be5d`; its Mac mini has 16 GiB RAM and needs no model or VM for this experiment. No Lean files/services need removal.

## Design frozen before sampling

This is a new DEVELOPMENT **contrast-score Monte Carlo experiment**, not real model inference, a full agent-trajectory generator, a repeat of an archived cell, or CONFIRM. It asks whether fixing the common initial action changes variance and interval behavior as predicted, under explicit independent generator laws. It cannot establish real-agent competence or host inference performance.

Each cell uses the same fixed 40 tasks: 20 have p=1/4 and 20 have p=3/4. There are four independent repetitions per task and 2,000 independent complete studies. Freeze two cells, eta=0 and eta=1/5, with feedback error q=1/4. Per episode draw U~Bernoulli(p), E~Bernoulli(q), F=U xor E, A~Bernoulli(1/2), and Y~Bernoulli(1/2+eta(2A-1)(2U-1)). Independently draw I~Bernoulli(1/2).

The history target takes second action F; the prompt-only target takes second action zero. Both start with S. Predictions are frozen constants q1_H=q1_P=q2=1/2. Define

    D_fixed = 2 1{A=F}(Y-1/2) - 2 1{A=0}(Y-1/2)
    D_half = 2 I D_fixed.

Reuse latent/outcome draws across logger candidates within each episode as paired common random numbers. Independence holds across generated task/repetition/study observations. The pairing is an efficiency device in this simulator, not a physical common-random-number assumption for LLM calls.

Exact per-task mean is 2 eta(p-q); equal-task targets are zero and 1/10. Second moments are q+p(1-2q) and twice that quantity. Mean within-task variances are .5 and 1 at eta=0, and .48 and .98 at eta=1/5. Divide by160 for the equal-task estimator variance. These identities must be independently enumerated with rational arithmetic before sampling.

Use equal-task means. Estimate execution variance as sum_g (1/40)^2 s_g^2/4, using within-task sample variances. Do not substitute dispersion of heterogeneous task means. Report bias/MCSE, empirical and exact estimator variance, paired uncertainty for variance or squared-error differences, RMSE, mean estimated variance, marginal 95% Wald coverage/length and zero/nonfinite-variance failures. Count Wald failures as noncoverage. These are diagnostic operating characteristics, not validated inference for agents. Also report marginal Hoeffding coverage/width using valid supports [-2,2] and [-4,4] for this shared-prediction contract; no fitted-score generalization. These conservative supports need not be sharp for the constant-half prediction specialization. No data-dependent choice of cell, method, endpoint, repetitions or extension.

## Execution and preservation

Create a new immutable remote run directory `req027_primary_logger_mc_20260927`. Freeze code/config/source hashes, exact truths and root seed20260927027 with documented deterministic cell streams before sampling. Retain all 2,000 study summaries/cell, manifest, tests, status, partial/failure records and commands. Deterministic tests must check score means, variance laws and the within-task variance estimator before launch.

Caps: one CPU process,2GiB working memory,5min simulation wall,15min total setup,20MiB outputs; standard library or already installed NumPy only. Recheck peers and pressure before execution. Stop only this task's own process if needed. No model, GPU, VM, package installation, paid service, Lean intervention, upstream mutation or GitHub publication by the remote worker. Both setup and this bounded simulation are authorized. The lead reviews artifacts before accepting conclusions. No real-agent or CONFIRM stage is released.

Status at dispatch: remote Codex task assigned; execution/result not yet claimed. Readiness **55%, change0points, range45–65%**. Largest milestones: competent fixed-target real-agent comparison with valid inference; final empirical synthesis; independent reproducibility and author-approved package.
