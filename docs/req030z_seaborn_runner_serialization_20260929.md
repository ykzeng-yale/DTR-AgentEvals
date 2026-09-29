# REQ030Z — inert runner serialization compatibility correction

## Gate and scientific interpretation

The highest-impact unresolved gate remains a real isolated joined execution of the pinned Seaborn agent path, with prompt/token bindings, bounded actions and durable terminal evidence. REQ030Y (`27846930`) did reach the real container boundary: all source/image/workspace checks passed; the Qwen tokenizer and pinned `DefaultAgent` initialized; actual Apptainer preflight accepted namespace separation, absent host paths, read-only root, clean workspace and 405,618,688 bytes free on `/testbed`. One authored fake response and one harmless action were recorded; the action exited 0 with the expected 16-byte output.

The job then failed `FAILED 1:0` after 1:52, with batch MaxRSS 2,899,196 KiB. The traceback identifies an implementation compatibility defect: pinned mini-swe-agent calls `AgentConfig.model_dump(mode="json")` in its per-step `save()` path, while the deliberately minimal Pydantic stub accepted no keyword arguments. That exception escaped from `DefaultAgent.run`'s `finally` save after the first action, so the second scripted response/action and final qualification receipt were not produced. The raw event stream independently confirms one physical fake call, one successful action, workspace sealing and the exact `TypeError`; it contains no terminal-submission event. The lack of a full trajectory/qualification receipt is therefore explained by serialization, not by an evaluator/model result. Resource usage and the successful preflight/action argue against capacity or isolation as causes of this attempt, but do not qualify later steps.

This is one fixed Seaborn issue with a deterministic no-weights fixture, not a task outcome, task retry, or estimate of model competence. REQ030R's 250 nested statuses still represent one issue. The design/inference limitation remains the absence of a competent matched executor comparison and independent task/family-level inference; this infrastructure correction cannot advance a DTR effect estimate.

## Correction and acceptance

The lead's `MinimalBaseModel.model_dump` now accepts the pinned upstream `mode="python"` and `mode="json"` forms, rejecting unsupported modes. The clean-process regression now calls the actual pinned `DefaultAgent.save(Path(...))`, reads the written trajectory JSON, and checks the serialized config fields. This directly exercises the failing method path. The release-consistency regression binds the changed driver/test bytes and the new manifest/batch pins.

The focused local suite passes 23 tests using the documented importlib mode:

```text
.venv/bin/python -m pytest --import-mode=importlib -q \
  experiments/lead_req030/test_native_hf_text_adapter.py \
  experiments/lead_req030/test_seaborn_public_input.py \
  experiments/lead_req030/test_bounded_supervisor.py \
  experiments/lead_req030/test_seaborn_runner_bootstrap.py
23 passed
```

Python compilation, the new batch's `bash -n`, release payload/hash binding, and `git diff --check` also pass. The separate older `test_seaborn_control_replay.py` has a known relative-import collection failure under default pytest mode; it was not needed for this correction and is not counted as passing here.

## Frozen follow-up scope

A single new immutable CPU-only inert qualification uses the same pinned Seaborn SIF (`9da1f51cb8c01a6ad9e0db4d1969742fbec995021e78150a9623d4f4719a8a47`), public projection (`b3fb8c08d74d92279a7caf77bf714c77ac3eee2dbafc996596b786c5484954e9`), tokenizer revision (`381fc969f78efac66bc87ff7ddeadb7e73c218a7`), workspace seed (`3cc8a60a720e00816e2853bce4e47d58705443cf6f4e8a4531ca69ae458b8100`), two scripted outputs, isolation flags, account, and 2-CPU/8-GiB/15-minute cap. It adds only the corrected serialization shim and direct trajectory-save regression. No model weights, evaluator/reference manifest, tests, downloads, generated model actions, GPU, or score are introduced.

- Run ID: `req030-seaborn-runner-qualification-20260929-c`
- Manifest SHA-256: `e51c395810cdd61cbce8c93e9ea71ab04e514c1734327d67ceb0f6ef477438b8`
- Batch SHA-256: `96578d7e95101050cff575b41d179e943e1c81a8e5613ff2dd1f9818376d7f42`
- Payload sums SHA-256: `65985492df352a83c47b0e90556414418ac616210128300f2c945bc6519ecfe3`
- Driver SHA-256: `fda171d1b88ea6a700b451f59a7001d7e7666f618f0d88d046435f33209b8b40`
- Regression SHA-256: `95ad84adb72843cb290a1d22d1acac3bf79a28d19542e06889aa328a4651268a`

## Prior attempt evidence and limits

Raw job `27846930` logs, event stream, action/preflight receipts, output bytes, exit record and `sacct` are preserved in `results/local_req030/seaborn_runner_y_failure_20260929/evidence.tar` (SHA-256 `3c8369c88f954e9afd5d7c8dd119e3b716601fa33d28e38b58b1f83caca0bba3`). The archive is local research evidence; its raw event stream includes host metadata and is not copied into the public source release. The sanitized local README/replay describes the failure without exposing host inventory.

Only a complete receipt with exact bindings, both fixed actions, terminal sentinel/submission, private trajectory/events, workspace final digest and Slurm cleanup/accounting can pass this narrow runtime gate. Even a pass clears runtime integration only. Before any task inference, the lead still must select a competent matched executor pair and freeze task/family sampling, estimand, opportunity/randomization, limits, independent evaluation and precision analysis. No model-task run, CONFIRM, or full benchmark is authorized by REQ030Z.

Readiness remains **55%, change 0 points, range 45–65%**. Major remaining milestones are a competent fixed-target comparison with valid task/family-level inference; empirical/manuscript synthesis; independent reproducibility; and the author-approved submission package.
