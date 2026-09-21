# Research and experiment collaboration

This repository studies causal evaluation of dynamic model routing. Read README.md, docs/research_proposal.md, docs/theory.md and docs/experiment_protocol.md before changing scientific claims.

## Publication workflow: direct updates to main

The author explicitly requested direct integration into `main`, without pull requests. All project agents and the recurring monitor must validate their changes, synchronize with the latest remote `main`, preserve concurrent work, and commit/push directly to `main`. Do not create a PR, draft PR, or PR-based handoff unless the author later changes this instruction. If an isolated branch is needed for local work, integrate its reviewed changes locally and publish to `main` directly. Never force-push or overwrite another agent's work. Continue mathematical/code review and appropriate checks before publishing; direct publication does not remove validation requirements. Use issues and committed handoff files for coordination.

## Git commit identity

The owner explicitly requires **Yukang Zeng <ykzeng2019@gmail.com>** as both author and committer for all new
project-agent commits. Configure `user.name` and `user.email` in each checkout and check the actual author and
committer before pushing; environment overrides can supersede Git configuration. The verified GitHub account
linked to this address is `ykzeng-yale`. Do not use OpenAI, Codex, an AI vendor/model, a Yale address or a machine
identity as the commit author/committer, and do not append AI/vendor `Co-Authored-By` trailers. This is a Git
attribution instruction, not a change to scientific citations, licenses or acknowledgments.

The repository `.mailmap` canonicalizes the owner's historical name/email aliases in Git views that honor it.
It does not rewrite raw historical commit metadata or remove historical trailers. Preserve published commit IDs
and their scientific provenance links under the existing no-force-push instruction.

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

## Current phase (updated 21 September 2026)

The author has prioritized completing the theory and full manuscript while GPU capacity is limited. For the theory workstream, defer new model inference, GPU jobs and Monte Carlo sweeps. The later author instruction explicitly prioritizes critical retrospective diagnosis and paper integration: bounded deterministic analysis of archived results and a descriptive manuscript case study are now in scope, with unresolved inference and validation stated. Deterministic CPU algebra checks and manuscript compilation are also in scope. Preserve archived experiments unchanged; integrating their observed results does not make them confirmatory or authorize fresh execution. Read `manuscript/README.md`, `docs/theory_extensions.md`, and the internal theory review when continuing the paper. This phase instruction overrides the general request above to run a small simulation for a paper-only change.

The author has separately instructed the experiment worker to accelerate its authorized experiments and exchange GitHub updates/feedback every 30 minutes. Do not apply the theory workstream's compute deferral to that separately authorized work or start duplicate jobs. Follow `docs/coordination_30min.md`: review new batches and questions promptly, use stable request IDs and acknowledgements, preserve frozen confirmation and archive integrity, and retain lead ownership of scientific decisions. The existing theory heartbeat is active every 30 minutes at :18/:48, following the worker-reported :13/:43 publication slots. Distinguish that reported external scheduler state from independent host verification.

## Progress reporting

Every user-facing project completion/progress summary and scheduled GitHub update must include the estimated percentage readiness of the full project for an arXiv/preprint submission, its change since the previous checkpoint, and the largest remaining milestones. Follow the stable weighted rubric in `docs/readiness.md`, using current evidence and distinguishing reported from independently validated results. A completed local task or theory draft is not 100% full-project readiness. This is a planning estimate, not an acceptance probability or a time estimate.
