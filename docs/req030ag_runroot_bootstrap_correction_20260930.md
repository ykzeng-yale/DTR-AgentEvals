# REQ030AG v3 launch failure and v4 correction — 30 September 2026

## Scientific question and observed failure

The frozen REQ030AG v3 development cohort asks whether the pinned Qwen2.5-Coder 7B/14B pair can resolve a useful fraction of eight preselected SWE-bench issues from eight repository families under the same HF/BF16/B200 agent contract. The original v3 attempt is Slurm job `27903827`. It allocated one B200, 8 CPUs and 128 GiB on `pi_gt353/gpu_b200/normal`, ran for 38 seconds, and ended `FAILED 1:0`; batch `MaxRSS` was 178,924 KiB.

The raw stdout and `failure.json` agree on `FileExistsError` for the per-job result directory. Payload checksum validation passed, and the staged runner source and manifest hashes match the frozen v3 release. The shell launcher created `$RESULT` before invoking Python, while `execute_batch()` intentionally creates the same directory with `exist_ok=False` to reject stale/colliding evidence roots. This collision occurred before the first `batch_summary.json`, controls, model download/load, or episode. The caught-failure receipt records model/cache cleanup; the low RSS and direct traceback support a deterministic bootstrap defect and contradict OOM as the cause of this attempt. No task outcome is observed or scored.

## Narrow correction and frozen scope

REQ030AG v4 changes only release identity/path plumbing and the single ownership violation: the launcher creates the private `results/` parent but leaves the per-job `$RESULT` leaf absent for Python's exclusive creation. The Python `exist_ok=False` guard is retained. A regression requires that the batch launcher pass the same leaf to Python without creating it, while preserving parent creation and exclusive application ownership.

The eight task IDs/families, two exact model revisions, tokenizer, runtime, BF16/SDPA, prompt, decoding and token limits, randomized balanced order, control-first rule, public-only model inputs, evaluator-only reference/test inputs, endpoint, unknown handling, resource envelope and target-alignment limitation remain byte-for-byte the v3 design. No observed model/control outcome is used to alter that design. v3 remains immutable and archived; v4 receives a new release ID, checksummed payload, Slurm job and run directory. The single replacement is justified because v3 failed before any model or task episode was exposed.

The previously reviewed Seaborn controls remain one-task image/evaluator evidence only. REQ030AG remains a purposive SWE-bench development feasibility screen; even an in-band result cannot qualify the original MBPP/HumanEval executor target or establish a history-aware versus prompt-only effect. Full benchmark and CONFIRM remain held.

## Acceptance and interpretation

Before the one v4 submission, run the focused REQ030AG tests including the new launcher/Python directory-ownership regression, compile Python, validate `bash -n`, rebuild the same eight-task manifest, and verify every release source pin and archive checksum. On allocation, verify the exact run/release binding. Require all eight baseline and eight reference controls to match the frozen declared statuses before any model assets are downloaded. If the control gate passes, execute only the 16 frozen model/task episodes once; preserve every missing/unknown cell and cleanup record. The result remains descriptive feasibility evidence, not an independent-task population estimate, model-superiority claim, router effect, or CONFIRM.

Readiness remains **55%, change 0 points, range 45–65%**. Major remaining milestones: (1) competent executors and valid fixed-target/task-family H/P inference, (2) empirical and manuscript synthesis preserving adverse/null evidence, and (3) independent reproduction and author-approved submission packaging.
