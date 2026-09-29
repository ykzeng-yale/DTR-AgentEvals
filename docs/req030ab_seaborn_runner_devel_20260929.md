# REQ030AB — devel-routed inert Seaborn runner qualification

## Decision and rationale

The highest-impact gate is still whether the exact pinned Seaborn task runner reaches a self-consistent terminal receipt inside the real Apptainer namespace. REQ030AA/D had an appropriate small CPU request, but both account test-only estimates projected a next-day start on `day`. A single same-shape test-only estimate under `pi_gt353` projected immediate eligibility on the UP standard `devel` partition. The actual request remains 2 CPUs, 8 GiB, 15 minutes; only the partition is changed in a new immutable release. The test-only estimate is not a reservation. D was never submitted.

The owner Mac mini and auxiliary MacBook did not expose Apptainer, Singularity, Podman or Docker, so they cannot reproduce this exact Linux namespace. The mini showed 14 GiB free and the auxiliary MacBook 19 GiB, but those capacities do not make a host-native test equivalent. No local runtime was installed or altered.

## Frozen run

Release ID: `req030-seaborn-runner-qualification-20260929-e`.

- Account/partition/QOS: `pi_gt353/devel/normal`.
- Resources: 2 CPUs, 8 GiB, 15 minutes.
- Manifest SHA-256: `64a464252aac9814970d0d55007bde2ec43cb68d4e9903c62010d9bb8ef66e0a`.
- Batch SHA-256: `e52299b963e2e1e628349b717a9e9cb45f04641943ab93daa011832f95c8557d`.
- Checksum-file SHA-256: `42be0954c7266c731bdb84a956226a3e0a657a53bfc52e3eb2cdf0d5a129b971`.
- Driver SHA-256: `241ca4ac7043b45149c54ee9fe43141204ab7837584acf56e1769ae1704dd57`.
- Regression source SHA-256: `ed830c42b9c46a4809ecdf2329e801d003893f6caee59cdfa7d9304537e3dfc5`.
- SIF SHA-256: `9da1f51cb8c01a6ad9e0db4d1969742fbec995021e78150a9623d4f4719a8a47`.
- Qwen tokenizer revision: `381fc969f78efac66bc87ff7ddeadb7e73c218a7`; weights remain unloaded.

The run retains the existing safe public projection, workspace seed, isolated no-network runner and two authored fake responses/actions. No model weights, benchmark tests, reference/evaluator manifest, downloads, GPU or model-generated command are included. Required narrow pass evidence is the official receipt with exact release/SHA, both isolated action receipts, terminal marker/empty submission binding, trajectory/workspace digest, namespace checks, cleanup and actual Slurm accounting. A pass cannot establish model competence, treatment effect or task score.

The immutable release is committed on `main` as the REQ030AB follow-up. Before submission, the exact staged payload and test-only estimate must be verified. This report must be amended with the actual Slurm ID, submission/start/terminal times, raw evidence path/hash, independently checked receipt, and accounting. A pending state is not a started experiment and must not be reported as one.

Readiness remains55%,change0points,range45–65%; competent fixed-target comparison and valid task/family inference, empirical/manuscript synthesis, independent reproduction and author-approved packaging remain.


## Terminal review — actual job 27858023

The job started11:41:54 and ended11:42:54 ET, `FAILED 1:0`, 2 CPUs/8 GiB, batch MaxRSS2,780,200 KiB. All 15 source/manifest entries and the SIF, workspace seed and coder tokenizer manifest hashes passed; the four in-job bootstrap tests passed. The driver then raised `KeyError: release_id`: it loaded the coder tokenizer manifest into `manifest` and incorrectly attempted to read the qualification release ID from it. The failure occurred before the runner call, so there was no Apptainer preflight, tool action, fake-model call, qualification receipt or task score. This is a lead-owned implementation defect, not an outcome or a capacity failure. Raw logs and accounting remain in the local-only archive identified in the experiment handoff.

REQ030AC/F fixes this by loading `DTR_RELEASE_MANIFEST` separately, verifying `DTR_RELEASE_SHA256`, and retaining the model manifest solely for tokenizer/model metadata. The additional focused regression verifies that a model manifest without `release_id` is not used as the run release. See [REQ030AC](req030ac_seaborn_runner_manifest_binding_20260929.md).
