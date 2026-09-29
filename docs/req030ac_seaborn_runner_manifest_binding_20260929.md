# REQ030AC — bind the qualification release separately from the model manifest

## Scientific gate and terminal diagnosis

The relevant gate remains execution integrity for the exact pinned Seaborn runner. REQ030AB job `27858023` actually started on `pi_gt353/devel` (2 CPU, 8 GiB) at 11:41:54 ET and ended `FAILED 1:0` at 11:42:54, MaxRSS 2,780,200 KiB. All 15 source/manifest hash checks and the task SIF, workspace-seed, and Qwen tokenizer-manifest checks passed. The four bootstrap tests passed. The driver then raised `KeyError: release_id` before calling `run_pinned_agent`: the variable named `manifest` held the Qwen `coder_model.json`, which intentionally has repository/revision/tokenizer-file fields but no qualification `release_id`. Thus no Apptainer preflight/action, fake model call, official receipt, evaluator input, or task score exists. The exception contradicts memory-capacity as this failure cause; it is a lead-owned implementation defect.

Private raw evidence is retained at `results/local_req030/seaborn_runner_e_failure_20260929/evidence.tar` (SHA-256 `30e6f0a206a054c7ca2830798c612284b0ed3be6f20cdae8b17a630d64d97e59`). The archive contains host path/log metadata and is not committed. A sanitized lead replay is at `results/local_req030/seaborn_runner_e_failure_20260929/lead_replay.json` (SHA-256 `e73f4e7fa2bb4c7c0fc9ea5018505ad61edc5cd2abfda917d9d4159d58996b6b`).

## Correction and local checks

The driver now loads `DTR_RELEASE_MANIFEST` separately, verifies its bytes against `DTR_RELEASE_SHA256`, and passes that release's ID/SHA into runner events. The Qwen model manifest is retained under `model_manifest_data` only for model repository, revision, license and tokenizer file receipts. A new regression loads a qualification release and verifies that a coder-like model manifest without `release_id` is rejected as a qualification manifest. The exact terminal-marker-only command regression remains.

Focused validation: 26 runner bootstrap, native adapter, public-input, bounded-supervisor and control-replay tests pass. Python compilation, `bash -n`, staged hashes, and `git diff --check` must be confirmed against this immutable release before submission.

## Frozen run

Release ID: `req030-seaborn-runner-qualification-20260929-f`.

- Account/partition/QOS: `pi_gt353/devel/normal`.
- Resources: 2 CPUs, 8 GiB, 15 minutes.
- Manifest SHA-256: `3c9000850d468f72a7776871f04f5557c4fa9c93e7f3d7757ef49b3fa5d3ff60`.
- Batch SHA-256: `b2ad18f53ed1751f445dcdd12a07efa7ffc232a6d668448bf6a04f5be6721bdf`.
- Checksum-file SHA-256: `e8c71ac636566188f93f64bd986489bc86b69f2b48b9d0e150c20511a6b989ad`.
- Driver SHA-256: `9512fd0adb460f542eb90b6337f94ece21a538f6930d9378dfc19508733e2c11`.
- Regression source SHA-256: `19aa2cc00db517f5d0fe59f5230dc0e1b547da5573d875e63f09a2fcf32df52a`.
- Task SIF SHA-256: `9da1f51cb8c01a6ad9e0db4d1969742fbec995021e78150a9623d4f4719a8a47`.
- Workspace seed SHA-256: `3cc8a60a720e00816e2853bce4e47d58705443cf6f4e8a4531ca69ae458b8100`.
- Qwen tokenizer revision: `381fc969f78efac66bc87ff7ddeadb7e73c218a7`; no weights are loaded.

Only the qualification correction changes. The run remains inert: authored fake output, two harmless fixed commands, the public task projection, pinned tokenizer and the established no-home/no-hostfs/no-network Apptainer contract. No benchmark tests, reference/evaluator manifest, model weights, downloads, GPU, or model-generated action are included. A pass would clear only the narrow runtime receipt gate.

Readiness remains55%,change0points,range45–65%. Competent fixed-target comparison/valid task-family inference, empirical and manuscript synthesis, independent reproducibility and author-approved packaging remain.
