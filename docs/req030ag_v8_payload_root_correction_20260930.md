# REQ030AG v8 correction — 30 September 2026

## V7 terminal diagnosis

Actual v7 Slurm job `27935161` was submitted to `pi_gt353`, `gpu_rtx6000`,
with one RTX PRO 6000 Blackwell, 8 CPUs and 128 GiB. It started at 04:13:45 ET
and failed at 04:15:22 ET (`FAILED 1:0`, elapsed 1:37, batch MaxRSS
178,928 KiB). GPU inventory recorded an RTX PRO 6000 Blackwell with 97,887
MiB and driver 580.178.04. The scheduler confirms the requested GPU was
allocated; the low host RSS and preserved log argue against a host-memory
capacity failure.

The failure occurred before the Python application imported: stdout says
`ModuleNotFoundError: No module named 'experiments'`. No
`batch_summary.json` was created. The outer archive lists files under a
top-level `payload/` directory, but v7 extracted that archive into
`$RUN/payload`, producing `$RUN/payload/payload/experiments` while setting
`PYTHONPATH` to `$RUN/payload/`. Thus the application package was one level
deeper than the import path. This is a deterministic launcher/archive-root
mismatch, not a CUDA, model, evaluator, or task result. There is no evidence
that controls, model weights, or episodes ran; the failure is not scored as a
model zero.

The raw stdout, GPU inventory, and exit receipt are preserved in the private
archive `results/local_req030/req030ag_v7_failure_20260930_private/evidence.tar.gz`
(SHA-256 `03c4ba975641a60880771b5e63f342d92709565d2a788899adc895795c8773d8`).
The sanitized scheduler/application summary is
[`job_27935161_summary.json`](../results/local_req030/req030ag_v7_failure_20260930/job_27935161_summary.json).

## V8 correction and unchanged scientific design

V8 is a new immutable attempt because v7 is terminal. The launcher now lists
the outer archive members, requires the exact `payload/experiments/...` and
`payload/work/.../manifest.json` roots, extracts once at `$RUN`, and checks the
expected files before invoking Python. The Python path, wheel manifest, and
bundle paths consequently all resolve beneath `$RUN/payload/`. A regression
asserts the checked roots and rejects the prior double-nested extraction.

The eight issue IDs and eight distinct repository families, 16 planned model
episodes, SIF/model digests, model revisions, RTX PRO 6000 Blackwell runtime,
prompt, decoding, budgets, controls, evaluator, endpoint, uncertainty rules,
and controls-before-model-load ordering remain identical to v7. V8 reuses
the retained task SIFs and does not repeat image acquisition. It neither
retries any task episode nor changes an outcome. Standard-tier limits and
peer-safe routing remain in force.

This screen remains development feasibility evidence only. It cannot
establish history-aware versus prompt-only router effects, competence on the
archived MBPP/HumanEval fixed target, population inference, full benchmark, or
CONFIRM. Readiness remains 55%, change 0 points, range 45–65%; the major
milestones remain a competent executor pair with valid fixed-target/task-
family inference, empirical/manuscript synthesis, and independent
reproduction plus author-approved submission packaging.
