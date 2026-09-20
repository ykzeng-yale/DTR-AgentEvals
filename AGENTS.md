# Research and experiment collaboration

This repository studies causal evaluation of dynamic model routing. Read README.md, docs/research_proposal.md, docs/theory.md and docs/experiment_protocol.md before changing scientific claims.

## Publication workflow: direct updates to main

The author explicitly requested direct integration into `main`, without pull requests. All project agents and the recurring monitor must validate their changes, synchronize with the latest remote `main`, preserve concurrent work, and commit/push directly to `main`. Do not create a PR, draft PR, or PR-based handoff unless the author later changes this instruction. If an isolated branch is needed for local work, integrate its reviewed changes locally and publish to `main` directly. Never force-push or overwrite another agent's work. Continue mathematical/code review and appropriate checks before publishing; direct publication does not remove validation requirements. Use issues and committed handoff files for coordination.

## Research rules

- The lead agent owns the scientific judgment, including the estimand, design, metrics, comparators, interpretation and next discriminating study. The experiment agent largely implements that design; do not shift responsibility for an inconclusive or unfavorable finding back to it.
- Diagnose weak or failed results before requesting more experiments. Compare plausible design, metric, learner, implementation, inference and theory explanations against existing evidence; record evidence against the preferred explanation and what would change the conclusion. Distinguish an implementation defect, a violated assumption, an inadequate test and an empirical null. Revise the lead's own design and claims when warranted.
- Use bounded deterministic retrospective diagnostics while compute is deferred; preserve frozen outputs and label these analyses. Do not tune on CONFIRM to obtain a favorable result, change a primary endpoint retrospectively, or treat a new proof or passing infrastructure check as evidence of practical improvement. Prioritize the declared scientific target over peripheral extensions. The current lead decisions and concrete worker requests are in `docs/scientific_diagnosis_20260920.md`.
- Preserve raw run artifacts and immutable configurations. Never overwrite a completed experiment; use a new run directory.
- Distinguish synthetic simulation, real model inference, pilot evidence, confirmatory results and planned experiments.
- Do not call known DTR/OPE theory novel. Attach assumptions and primary citations to mathematical claims.
- Use actual target/behavior routing-probability ratios. Unsupported policies are not repaired by a fitted outcome model.
- Split and infer at task/family level; keep branches and repeated seeds together.
- Pin model digests, harness/environment versions and decoding parameters. Record third-party licenses.
- Do not execute model-generated code outside an isolated benchmark sandbox. The local arithmetic pilot parses a restricted tool protocol instead.
- Keep tokens, latency, money and energy distinct. Do not invent prices or claim token counts measure dollars.
- Do not publish credentials, personal messages or private datasets. Inspect staged files before a push.
- Add tests when changing estimators, randomization, task validation or inference. Run the documented test suite and a small deterministic simulation.
- Update docs/experiment_results.md with the exact run, observed results and limitations. Update docs/experiment_handoff.md with reproducible next steps.
- A proposed extension is not an implemented experiment. Keep the status table current.

## Current phase (19 September 2026)

The author has prioritized completing the theory and full manuscript while GPU capacity is limited. Defer new model inference, GPU jobs, Monte Carlo sweeps, and manuscript empirical results until that work is resumed. Deterministic CPU algebra checks and manuscript compilation are in scope. Preserve existing experiments unchanged. Read `manuscript/README.md`, `docs/theory_extensions.md`, and the internal theory review when continuing the paper. This phase instruction overrides the general request above to run a small simulation for a paper-only change.

## Progress reporting

Every user-facing project completion/progress summary and scheduled GitHub update must include the estimated percentage readiness of the full project for an arXiv/preprint submission, its change since the previous checkpoint, and the largest remaining milestones. Follow the stable weighted rubric in `docs/readiness.md`, using current evidence and distinguishing reported from independently validated results. A completed local task or theory draft is not 100% full-project readiness. This is a planning estimate, not an acceptance probability or a time estimate.
