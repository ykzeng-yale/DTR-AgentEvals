# REQ030AA — terminal receipt correction for the Seaborn inert runner

## Scientific question and diagnosis

The highest-impact unresolved gate is whether the exact pinned agent loop can complete its fixed inert actions inside the real Apptainer namespace and emit a self-consistent terminal receipt. This is an execution-integrity prerequisite, not evidence of model competence or a DTR effect.

Job `27855136` (`req030-seaborn-runner-qualification-20260929-c`) actually started at 10:31:27 and ended at 10:32:41 ET on 29 September, `FAILED 1:0`, 2 CPUs, 8 GiB requested, batch MaxRSS 2,790,976 KiB. The lead independently replayed all 16 ordered events, both source-bound fake requests/responses, both tool receipts/output hashes, terminal event, workspace seal and serialized trajectory. Both fixed actions exited zero. The terminal trajectory records `Submitted` with an empty submission, matching the frozen exact command `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`: that command prints the terminal marker and no body. The driver instead asserted the nonexistent string `inert-fixture-submission\n`, then exited before writing its official qualification JSON. This is a lead-owned post-execution acceptance defect, not a runner, evaluator, model, or task result.

A second source-integrity mismatch was present: the run's agent event labeled itself release `…-b`, although its bound manifest and Slurm work directory were release `…-c`; the event's SHA-256 did match the manifest. The failure evidence also weighs against basic capacity as the cause of this attempt: the isolated preflight and both bounded actions completed, and the allocation peaked at 2.79 GiB of 8 GiB. This does not establish model/GPU capacity. No weights were loaded, no evaluator/reference/test input was accepted by the runner API, and no task score exists.

The sanitized independent replay is [lead_replay.json](../results/local_req030/seaborn_runner_z_failure_20260929/lead_replay.json), SHA-256 `1a19f5dd228e9502e9bb53b980741ac36334b5b2a4379d4be428236d923fc0ac`. The full raw event stream and host metadata remain in the local-only `results/local_req030/seaborn_runner_z_failure_20260929/evidence.tar`, SHA-256 `4e5c7a5c3364e958c3209b6d88c5d3d467571528d06539271ad3137edd6c7a6a`; it is intentionally not part of this public commit.

## Correction and local acceptance

The inert driver now expects the empty submission produced by the exact frozen terminal action. It derives the event/receipt release ID from the immutable manifest and asserts the event's manifest SHA and final trajectory/submission SHA. A deterministic unit test runs the exact harmless shell command, passes its output through the production terminal branch, and checks the `Submitted` payload and zero-byte terminal event.

Validation passed: four runner-bootstrap tests; 21 focused adapter, public-input, supervisor and control-replay tests; Python compilation; `bash -n`; `git diff --check`; and a temporary staged-release replay verifying all 14 payload hashes plus the manifest (15 entries). This staged check is source integrity only, not remote execution.

## Frozen follow-up

One new immutable CPU-only inert qualification, `req030-seaborn-runner-qualification-20260929-d`, preserves the task SIF (`9da1f51cb8c01a6ad9e0db4d1969742fbec995021e78150a9623d4f4719a8a47`), public projection (`b3fb8c08d74d92279a7caf77bf714c77ac3eee2dbafc996596b786c5484954e9`), Qwen tokenizer revision (`381fc969f78efac66bc87ff7ddeadb7e73c218a7`), workspace seed (`3cc8a60a720e00816e2853bce4e47d58705443cf6f4e8a4531ca69ae458b8100`), exact two harmless scripted actions, isolation flags and limits. It requests `pi_gt353/day/normal`, 2 CPUs, 8 GiB and 15 minutes. It has no GPU, loaded weights, benchmark tests, reference patch, evaluator manifest, downloads, or model-generated commands.

Immutable pins:

- Release manifest: `ad03c440e6a117949616e454b49e31a7f3bcb1299b08edefccfc4764a7fa66ad`.
- Batch script: `a61e6e0cd61cdecb220c11ad81d3be8c648fa5fe14c83dcfb64f7a65fd5e891c`.
- Payload checksum file: `9c6565a657cb1bfad89414452aac9b78bae67ca41e59e9545f367b51aa0ea91a`.
- Driver: `241ca4ac7043b45149c54ee9fe431412e04ab7837584acf56e1769ae1704dd57`.
- Regression source: `d4cec1eac7136117d92a115a7a53459a7cd27cd117c8d4bc5a8eea1f8dae181c`.

Acceptance requires actual terminal job accounting, exact source/SIF/tokenizer/workspace pins, isolated preflight, both fixed action receipts, native prompt/token binding, consistent release ID/SHA, terminal marker and empty submission receipt, workspace seal/trajectory hash, and cleanup. A pass clears only this narrow inert runtime receipt gate. It does not authorize or imply model-task inference, a full benchmark, CONFIRM, or competence. Before any model-task run, the lead still must freeze a competent executor pair, target estimand, task/family sampling, routing opportunities, resource limits, independent evaluation and valid task-level precision plan.

Readiness remains **55% (change 0 points; judgment range 45–65%)**. The major remaining milestones are a competent fixed-target comparison with valid task/family inference, empirical/manuscript synthesis, independent reproducibility, and author-approved submission packaging.


## Routing update

The day-partition test-only estimate for release D projected a next-day start, so D was retained but not submitted. A same-shape `devel` test-only estimate for the identical account predicted immediate eligibility. REQ030AB/E is the new immutable release for that partition; see [REQ030AB](req030ab_seaborn_runner_devel_20260929.md). This is a scheduling choice only and does not alter the qualification's scientific scope.
