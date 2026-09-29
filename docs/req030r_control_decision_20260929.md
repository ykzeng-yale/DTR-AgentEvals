# REQ030R control decision — Seaborn 3187

**Decision: accept this exact unchanged/reference evaluator control pair, within its stated scope. Do not interpret it as a model result, a 250-task sample, or qualification of other task images.**

## Question and design

The question was whether the frozen strict SWE-bench evaluator distinguishes the no-patch Seaborn state from its known reference fix under the exact offline Seaborn image and test command intended for the prospective task. This is the pre-outcome `mwaskom__seaborn-3187` queue item. The task input is the public projection pinned at SHA-256 `b3fb8c08d74d92279a7caf77bf714c77ac3eee2dbafc996596b786c5484954e9`; the evaluator-only manifest is pinned at `03c8d3a4837ebdd065693d09153555af305144f2857651c8e2aabc8707cf9c54`. The required status set is 2 FAIL_TO_PASS plus 248 PASS_TO_PASS checks, all from **one task**.

The two arms used fresh 512 MiB image-backed workspaces, the same digest-identified Seaborn SIF, root-read-only image, no host home/filesystem mounts, and no network. The baseline arm applied only the frozen test patch. The reference arm applied the known reference diff and then the same test patch. The offline image's stock dependency-install step was omitted before this run and remains a declared environment deviation; this is not a pristine stock-harness result.

## Observed and independently replayed result

Slurm job `27792215` ran as `pi_gt353` on `day`, submitted 2026-09-28 22:14:34 ET, started 22:17:01 ET and ended 22:19:34 ET. Accounting reports `COMPLETED`, exit `0:0`, 2 CPUs, 8 GiB requested memory and 2:33 elapsed. The serial arm receipts report baseline supervised exit 1 in 64.527 seconds and reference supervised exit 0 in 60.728 seconds. These are evaluator timings, not model inference time or task-level sample sizes.

The lead independently verified that the run's six source/config files match their local pins, the raw bytes match each arm's receipt SHA and byte count, each log has exactly one ordered start/end marker, and the frozen parser accepts both results. The archived transfer is `results/local_req030/seaborn_controls_b_20260928/evidence.tar`, SHA-256 `9cf9719ffcf81be7a81bf61653abfbcf51a39369763b11e43dadbbde6a7878a5`.

| Arm | Declared F2P | Declared P2P | Extra parsed status | Whole pytest summary |
|---|---:|---:|---|---|
| No-patch baseline | 2/2 FAILED | 248/248 PASSED | 1 PASSED | 2 failed, 249 passed, 5 xfailed, 207 warnings |
| Reference patch | 2/2 PASSED | 248/248 PASSED | 1 PASSED | 251 passed, 5 xfailed, 207 warnings |

The extra status is `tests/test_relational.py::TestScatterPlotter::test_unfilled_marker_edgecolor_warning`; it is outside the frozen 250-ID strict endpoint and is reported separately. The five xfails are likewise outside that declaration. The whole-suite summaries therefore do not replace the frozen strict rule.

## Interpretation and limits

This resolves the **control/evaluator gate for this one task and this modified offline image environment**: the untouched task state exhibits the two expected target failures while retaining all declared regression passes, and the reference patch makes all 250 declared identities pass. The earlier job `27783854` remains a preserved infrastructure failure (`pytest` was absent from PATH; zero tests ran); job `27792215` is a new valid diagnostic pair, not a same-run retry.

The successful control is evidence against a broken target test or a parser that silently accepts missing declared IDs. It does not establish that any model can solve the task, that the image matches the pristine upstream installation procedure, that the controls generalize to another image, or that adaptive routing improves outcomes. Counting 250 test IDs as 250 independent units would be pseudoreplication: the independent task count here is **one**. No model was loaded and no generated command was executed.

The setup failure was caused by the lead's invocation of bare `pytest`; the corrected source changes only the interpreter invocation to the image's pinned Python `-m pytest`. This operational correction does not explain or alter a model outcome because no model was involved. Capacity was adequate for this bounded CPU control pair; that does not qualify GPU-model memory or agent-task execution.

## Next decision gate

Do not repeat these controls. Before a fresh development model trajectory, finish and source-bind the agent integration against the pinned mini-swe-agent single-action prompt/parser, Qwen's native chat template, the actual `/testbed` Apptainer workspace, a common context/request/action budget, strict submission/evaluation capture, and crash-safe raw-message/assignment logging. Its deterministic fake-model tests must exercise prompt rendering, one-action parsing, observation feedback, malformed output, terminal submission, cap/deadline handling, and prove that no evaluator/reference input can enter model messages. Then select and freeze a feasible small/large executor pair and the development estimand; the 32B deployment probes alone do not establish competence. Any later model run needs its own immutable source approval and exact bounded release. The primary history-aware versus matched prompt-only contrast, CONFIRM, and full benchmark remain held.

**Readiness remains 55% (change: 0 points; judgment range 45–65%).** The evaluator-control subgate advanced, but the largest remaining milestones are a competent fixed-target comparison with valid task-level inference, integrated empirical/manuscript synthesis, and independent reproducibility plus the author-approved submission package.


## Independent second retrieval — 29 September 2026

The lead performed a fresh direct-SSH retrieval and replay at the next scheduled review. Slurm still reconciles as `27792215` COMPLETED/0:0 (2 CPUs, 8 GiB, 2:33; MaxRSS 2,957,168K). The new transfer matches the committed archive byte-for-byte on the manifest, both raw logs, both receipts, both supervisor records, exit record and Slurm log. All six `SHA256SUMS` entries pass; the five experiment/evaluator source artifacts match their current local pins. The strict parser again accepts baseline 2/2 F2P FAILED +248/248 P2P PASSED and reference250/250 PASSED. The fresh transfer is `results/local_req030/seaborn_controls_b_review_20260929/evidence.tar`, SHA-256 `e8b721a76f5a0ae8b848bf3242764cd0d0278a4efd4a1c4e0b40483f958651da`. The machine-readable lead replay is [here](../results/local_req030/seaborn_controls_b_20260928/lead_replay_20260929.json), SHA-256 `7fa62927014deb2a75c8f22aa144f170431f8564b0e999c3648b154804bd7371`. This corroborates the original decision without changing its one-task/offline-environment limits.

## Superseding lead decision — 29 September 2026, after REQ030AE/H

REQ030AE/H subsequently passed the joined inert prompt→agent→tokenizer→isolated-workspace→receipt gate; its bounded evidence is documented in [REQ030AF](req030af_scientific_priority_20260929.md). This does not qualify a real model or resolve the next model pair. Therefore the older “finish integration” language above is historical and superseded: **do not repeat the Seaborn controls or submit another one-task Seaborn competence screen.** Proceed only with a single consolidated pre-outcome, multi-issue DEVELOPMENT competence release after the model pair, family-safe task frame, common real-model execution treatment and independent grading contract are frozen together. No model-task run is started by this evaluator-control result. Full benchmark/CONFIRM remain held. Readiness55%, change0 points, range45–65%.
