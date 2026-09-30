# Research and experiment collaboration

This repository studies causal evaluation of dynamic model routing. Read README.md, docs/research_proposal.md, docs/theory.md and docs/experiment_protocol.md before changing scientific claims.

## Direct compute coordination — author update, 27 September 2026

Use verified SSH/SFTP through the private `mac-ssh-compute` skill to allocate,
dispatch, inspect and retrieve authorized work on the owned Mac mini and auxiliary
MacBook. The Mac mini Codex-chat messaging/polling/dispatch path is retired. Do
not send work through that chat or depend on its status. The lead directly owns
implementation and scientific review; historical worker assignments remain archives.
This does not stop separately authorized jobs or change their frozen execution
kernels. Qualify a future replacement for an experiment's internal Git relay before
release; SSH dispatch alone is not such a change. Keep private keys and network
inventory outside this repository. Preserve bounded resource checks, source pins,
immutable run IDs, independent cleanup and no duplicate execution.

The active experiment monitor cadence is SIX HOURS by the author's update on
30 September 2026, superseding the historical two-hour, 30-minute and 15-minute
cadences. Keep one monitor and no continuous goal-token polling. Notify only for
independently validated positive, scientifically interesting and important findings;
archive adverse evidence honestly. Email requires the exact author-supplied recipient
and a verified sending connection. See `docs/six_hour_research_monitor_20260930.md`
and `docs/direct_ssh_coordination_20260927.md` for the current operating contract.

## Publication workflow: direct updates to main

The author explicitly requested direct integration into `main`, without pull requests. All project agents and the recurring monitor must validate their changes, synchronize with the latest remote `main`, preserve concurrent work, and commit/push directly to `main`. Do not create a PR, draft PR, or PR-based handoff unless the author later changes this instruction. If an isolated branch is needed for local work, integrate its reviewed changes locally and publish to `main` directly. Never force-push or overwrite another agent's work. Continue mathematical/code review and appropriate checks before publishing; direct publication does not remove validation requirements. Use issues and committed handoff files for coordination.

## Scientific leadership and experiment implementation

**Author instruction reaffirmed 26 September 2026:** Codex leads theory, scientific design, inference,
interpretation and overall coordination. Claude Code supplies coding capacity for explicitly scoped
experiment setup/implementation. Codex must understand, design, review and iterate those experiments;
do not delegate target, metric, comparator or scientific acceptance decisions to the implementer.
Use stable request IDs with exact sources, acceptance checks and execution scope. An implementation
request is not a model/Monte Carlo/CONFIRM release. See
`docs/scientific_lead_resumption_20260926.md` and the current request in `docs/experiment_handoff.md`.

For a shared checkout, agree file ownership before edits and use a single integration owner while
uncommitted work exists. Never pull over another agent's edits or stage their unfinished files. The
lead integrates reviewed changes directly to `main` with the identity below. The active scientific goal
is unfinished until the complete evidence-backed package meets the rubric; it is not the deleted
recurring lead automation and does not itself promise scheduled reviews.

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
- Prefer bounded deterministic retrospective diagnostics before new compute; preserve frozen outputs and label these analyses. Do not tune on CONFIRM to obtain a favorable result, change a primary endpoint retrospectively, or treat a new proof or passing infrastructure check as evidence of practical improvement. Prioritize the declared scientific target over peripheral extensions. The current lead decisions and concrete worker requests are in `docs/scientific_diagnosis_20260920.md` and the latest `docs/experiment_handoff.md` entry.
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

## Current phase (updated 24 September 2026)

The author prioritizes theory, manuscript and efficient experiments. The prior blanket theory-host deferral of new compute is superseded: bounded local **development** experiments are permitted when the code and exact source pins have been validated, available disk/compute and host isolation checked, a resource cap recorded, and no separately authorized worker job duplicated. Prefer deterministic CPU audits before model/GPU inference or Monte Carlo sweeps. Do not launch a held E2 live/CONFIRM or cue stage, tune on CONFIRM, buy compute, change the fixed primary target, or infer that permission to run means a design gate has passed. Preserve archived experiments unchanged and label retrospective diagnostics separately from prospective validation. Paper-only changes need appropriate algebra/build checks, not an automatic new simulation. Read `manuscript/README.md`, `docs/theory_extensions.md`, and the internal theory review when continuing the paper.

The author removed the recurring theory-lead check on **26 September 2026** for a laptop handoff. Do not assume a scheduled lead review is still running. The experiment worker's separately authorized publication cadence was not changed by this removal; verify its current scheduler and process state. Follow `docs/coordination_30min.md` for the exchange contract when work resumes: inspect new results/questions, use stable request IDs and acknowledgements, preserve confirmation and archives, and retain lead scientific judgment. Publish a material correction promptly when found.

## Progress reporting

Every user-facing project completion/progress summary and scheduled GitHub update must include the estimated percentage readiness of the full project for an arXiv/preprint submission, its change since the previous checkpoint, and the largest remaining milestones. Follow the stable weighted rubric in `docs/readiness.md`, using current evidence and distinguishing reported from independently validated results. A completed local task or theory draft is not 100% full-project readiness. This is a planning estimate, not an acceptance probability or a time estimate.
