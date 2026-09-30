# REQ030AG v9 GPU identity correction — 30 September 2026

## V8 terminal evidence

Slurm job `27937235` was submitted once to `pi_gt353/gpu_rtx6000` and reached
one allocated `rtx_pro_6000_blackwell` GPU, 8 CPUs and 128 GiB. It terminated
`FAILED 1:0` after 1:48 (batch MaxRSS 391,512 KiB). The checked runtime and
launcher passed far enough to import the v8 application, verify the pinned
bundle, load the CUDA runtime and capture GPU inventory. The measured device
was `NVIDIA RTX PRO 6000 Blackwell Server Edition`, 97,887 MiB, driver
580.178.04. The strict Python gate expected the scheduler's shorter display
string `NVIDIA RTX PRO 6000 Blackwell` and stopped before controls or model
asset download.

Both `failure.json` and `batch_summary.json` agree: `controls=[]`,
`episodes=[]`, `models_loaded=false`, `model_episode_started=false`, and both
model-root and HF-cache cleanup checks passed. This is a deterministic device
name alias defect, not GPU allocation/capacity failure or an empirical zero.
V7's distinct archive-root failure and this v8 runtime identity failure are
both preserved; neither exposed the cohort to model inference. Raw selected
receipts, stdout and inventory are retained privately at
`results/local_req030/req030ag_v8_failure_20260930_private/evidence.tar.gz`
(SHA-256 `076daaaa90d15ae68b020d771f937b76de353caf88c0b14e56a969252f292fbd`).
The sanitized receipt is
[`job_27937235_summary.json`](../results/local_req030/req030ag_v8_failure_20260930/job_27937235_summary.json).

## V9 exact-identity acceptance

V9 adds one explicit, frozen runtime alias:
`NVIDIA RTX PRO 6000 Blackwell Server Edition`. The runtime gate now accepts
either the canonical expected name or that exact alias; it does not accept a
prefix, substring, arbitrary Server Edition device, or different GPU. The same
exact check runs again immediately before model asset validation/loading. The
receipt retains both canonical expected and observed names and records whether
the explicit alias was used. This matches the requested Slurm GRES to the
actual inventory observed in two allocations while preserving rejection of an
unrelated GPU.

The 8 issues / 8 repository families and 16 planned 7B/14B episodes, model and
SIF hashes, prompt/public input, evaluator, decoding, endpoint, uncertainty
rules, RTX PRO 6000 Blackwell/CUDA treatment, resource caps, controls-before-
model-load gate and no-task-retry rule are unchanged. V9 is a new immutable
attempt after v8 terminated before controls/model inference. Its acceptance
requires tests for canonical-name acceptance, the observed exact alias, and
rejection of B200/other strings, plus the full pinned focused suite, strict
archive-source replay, and remote checks before its single submission.

This executor screen remains purposive DEVELOPMENT feasibility evidence. It
is not an H/P router contrast, fixed-target MBPP/HumanEval inference,
population estimate, full benchmark, or CONFIRM. Readiness remains 55%,
change 0 points, range 45–65%; competent fixed-target comparison/inference,
empirical and manuscript synthesis, independent reproduction and final
submission packaging remain.
