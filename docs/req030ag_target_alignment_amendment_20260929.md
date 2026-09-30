# REQ030AG downstream target-alignment amendment

**30 September correction:** the [investment review](investment_evidence_review_20260930.md#correction-of-the-leads-target-interpretation) retracts this note's conflation of the archived MBPP/HumanEval estimand with the sole prospective H/P target. The governing v2 protocol separately specifies SWE-bench H/P. No-transport boundaries remain correct; SWE-bench development is not inherently off-target for that prospective question. Historical release/status records below remain unchanged.

**Lead design clarification — 29 September 2026.** This is an outcome-independent interpretation constraint for the already frozen REQ030AG v3 queue submission. It changes neither that release nor its tasks, models, endpoint, resource request, or run authorization. No new experiment is released here.

## Question and evidence

Does passing REQ030AG qualify its model pair for the paper's original fixed-target history-aware versus prompt-only comparison?

No. REQ030AG's eight tasks are SWE-bench repository issues (`psf/requests`, `xarray`, `pylint`, `pytest`, `scikit-learn`, `sphinx`, `sympy`, and `astropy`) run through a repository-repair agent, isolated source workspaces, and patch/test grading. Protocol v2 likewise describes its selected mini-swe-agent/SWE-bench design as software-repair work. The archived primary study instead contains MBPP/HumanEval code-generation tasks and branch/log continuations; the source-bound diagnosis treats its target as fixed-benchmark repeated execution. These task semantics, interaction opportunities, state, feedback, and endpoint differ. A shared model snapshot or “coding” label does not establish exchangeability or executor competence transport across them.

The contrary possibility is that the same broadly capable executors will work in both settings. That is plausible but unobserved: current REQ030AG has not started, and even a valid 8-task pass would be purposive SWE-bench evidence with one episode per model/task. It cannot test the MBPP/HumanEval execution contract, estimate either benchmark's population rate, or identify an H/P effect. The historical MBPP/HumanEval CONFIRM identities remain unavailable for new tuning or confirmation, and the old GGUF results remain a different treatment.

## Decision boundary

1. Keep the single queued REQ030AG v3 job unchanged. Its release may answer only the prespecified HF/BF16 SWE-bench development feasibility question, after its controls and receipts validate.
2. Even if the screen is complete and within its feasibility band, treat that as permission to **design-review** a subsequent study, not automatic pair acceptance, router training, H/P inference, or CONFIRM.
3. Before claiming competence for the original MBPP/HumanEval target, require a separately frozen, public-input, family-safe development qualification under the executor and verification contract that matches that target. Exclude all held CONFIRM identities. If instead the project elects to study SWE-bench H/P behavior, label it prospectively as a distinct benchmark-specific study; do not replace, pool with, or claim it resolves the archived MBPP/HumanEval estimand.
4. Any later H/P study still needs the common initial-small action, a genuine consequential second decision, observable feedback variation, actual randomized assignment propensities, a strict independent endpoint, and an inference/precision plan tied to the declared task-family target. The eight-task screen supplies none of these router-effect observations.

This is a construct-validity and transportability boundary, not evidence that the models will fail on either benchmark. It narrows the consequence of a favorable screen and prevents the present queue wait or a future feasibility pass from being misreported as progress on the original causal estimand.

## Current run status and remaining dependency

At 19:17 ET, direct verified SSH showed Slurm job `27903827` still `PENDING (Reason=Priority)`. Its projected `21:09 ET` `StartTime` was about 1 h 52 min ahead at that observation; the earlier status note calling it past was an incorrect lead time-zone interpretation. At the 21:18 ET check the job remained pending, elapsed `00:00:00`, with projected `StartTime=2026-09-30 01:10 ET` and no allocation, stdout log, or run directory. Scheduler start times are moving estimates, not guarantees. No controls or real model episodes have run. Preserve that one job and do not switch accounts or duplicate it. On allocation, first verify staged/runtime identity, all eight controls, complete raw receipts, resource use, and cleanup. Only then assess the feasibility screen under its frozen rule; the target-alignment boundary above remains in force.

Full-project readiness remains **55%, change 0 points, range 45–65%**. Remaining milestones: (1) a competent executor and valid fixed-target/task-family H/P inference under a target-matched contract, (2) empirical and manuscript synthesis preserving adverse/null evidence, and (3) independent reproduction and author-approved submission packaging.
