# REQ030AD — align bootstrap regression with the staged release layout

## Unresolved gate and cumulative diagnosis

The high-impact gate is the exact source-pinned Seaborn runner completing its inert Apptainer path and writing a self-consistent official receipt. Three actual jobs show separate lead-owned integration defects:

- Z/job27855136 completed both harmless actions but failed the wrong nonempty terminal submission assertion.
- E/job27858023 stopped before runner invocation because qualification `release_id` was read from the Qwen tokenizer manifest.
- F/job27858685 stopped in the fifth bootstrap regression because it looked for the release manifest inside `payload/`, although the actual batch places `release.json` in the run root. Job F ran11:51:17–11:51:55 ET on `pi_gt353/devel`, 2 CPU/8 GiB, `FAILED 1:0`, MaxRSS2,668,196 KiB. The first four tests and artifact pins passed. No container call, actions, fake-model calls, official receipt, evaluator data or score. This is an implementation/test layout defect; neither its traceback nor observed memory supports capacity failure.

The previous REQ030AB/E raw evidence archive is locally preserved at `results/local_req030/seaborn_runner_e_failure_20260929/evidence.tar` (SHA-256 `30e6f0a206a054c7ca2830798c612284b0ed3be6f20cdae8b17a630d64d97e59`). F's raw logs/accounting are also retained locally; host-path-bearing material is not committed. The sanitized [F replay](../results/local_req030/seaborn_runner_f_failure_20260929/lead_replay.json), SHA-256 `23ecc96ad6cf86abc02816157994c012a11be54a0a466abd71dd202347e4132b`, records the independent classification; raw logs remain local-only.

## One consolidated correction

The release-binding test now resolves `DTR_RELEASE_MANIFEST` and `DTR_BATCH_SCRIPT` from its environment, exactly like the production sbatch. The release JSON therefore stays at the run root while all source-pinned files stay below `payload/`. Tests check both the release identity and all source bytes/hashes under the staged payload. Separate Qwen tokenizer-manifest parsing remains in place, and the exact terminal-marker/empty-submission regression remains.

Local validation: focused bootstrap/native adapter/public input/supervisor/control-replay suites pass26/26; `py_compile`, `bash -n`, hash staging and `git diff --check` must all pass on the immutable release bundle before dispatch.

## Frozen release G

Release ID: `req030-seaborn-runner-qualification-20260929-g`.

- Account/partition/QOS: `pi_gt353/devel/normal`.
- Resources: 2 CPU, 8 GiB, 15 minutes.
- Manifest SHA-256: `46ca01639078f16f24504ef46f702d758165750ac79b05da2c2288362d42621a`.
- Batch SHA-256: `6c913a215ea93ed438b5185318bd46ece6c7a1e6c7ed0844a07319fc2f84bae2`.
- Checksum file SHA-256: `c0c87dbd1122f9ffa84194ebcdc5278ed3dd507b9c834c60ee8288302ef1dfda`.
- Driver SHA-256: `9512fd0adb460f542eb90b6337f94ece21a538f6930d9378dfc19508733e2c11`.
- Regression source SHA-256: `668239b5624b0a128d63a73691249a70759643b245483fcb7002dd66d53f2436`.
- Task SIF SHA-256: `9da1f51cb8c01a6ad9e0db4d1969742fbec995021e78150a9623d4f4719a8a47`.
- Workspace seed SHA-256: `3cc8a60a720e00816e2853bce4e47d58705443cf6f4e8a4531ca69ae458b8100`.
- Qwen tokenizer revision: `381fc969f78efac66bc87ff7ddeadb7e73c218a7`; model weights are not loaded.

This is one inert infrastructure qualification: it has only the public task projection, real pinned tokenizer, authored deterministic fake outputs and two harmless fixed actions, inside the same no-home/no-hostfs/no-network container. No model weights, test/reference/evaluator inputs, generated commands, downloads or GPU. A pass qualifies only this runtime receipt gate; it is not model/task competence or a DTR estimate.

Readiness remains55%, change0 points, range45–65%. Major remaining milestones are a competent fixed-target comparison with prospective task/family-level inference, empirical and manuscript synthesis, independent reproduction, and author-approved packaging.
