# REQ030X — real tokenizer plus inert Seaborn runner qualification

## Scientific question and release boundary

The highest-impact unresolved implementation gate is whether the already-pinned public Seaborn issue and mini-swe-agent prompt can pass through the real Qwen tokenizer, joined native adapter, restricted Apptainer workspace, bounded supervisor, and terminal-submission recorder as one path. REQ030R's control checks validated one issue's evaluator; REQ030W connected the source components only through fake Apptainer. Neither observed an agent outcome. This release asks only whether the runtime path functions and records its boundaries.

REQ030X is a single **CPU-only inert qualification**, not task inference or an evaluator run. It reuses the exact existing Seaborn SIF (`9da1f51cb8c01a6ad9e0db4d1969742fbec995021e78150a9623d4f4719a8a47`) and a fresh per-run copy of the existing 512 MiB workspace image (input SHA `3cc8a60a720e00816e2853bce4e47d58705443cf6f4e8a4531ca69ae458b8100`). No image rebuild, model weight copy/download, test bundle, reference patch, or evaluator manifest is in the release. The only task input is the frozen public projection for `mwaskom__seaborn-3187`, SHA `b3fb8c08d74d92279a7caf77bf714c77ac3eee2dbafc996596b786c5484954e9`.

The qualification loads the **real local Qwen2.5-Coder-32B-Instruct tokenizer only**, revision `381fc969f78efac66bc87ff7ddeadb7e73c218a7`, Apache-2.0, Transformers `4.51.3`. It verifies the pinned model manifest and hashes of `config.json`, `merges.txt`, `tokenizer.json`, `tokenizer_config.json`, and `vocab.json`. Network and HF downloads are disabled. The model adapter receives an authored deterministic fake with no learned parameters; its two fixed outputs are one harmless `printf` inside `/testbed` and the exact terminal sentinel. These outputs exercise one observation and final submission but cannot be counted as model behavior, patch quality, or task success.

## Frozen execution and resource bounds

The joined source uses the pinned mini-swe-agent `DefaultAgent` and text parser hashes audited in REQ030T, the frozen public task projection and default prompt templates, the HF adapter, the previously fault-tested bounded supervisor, and `seaborn_apptainer_runner.py`. The runner checks actual host platform/network namespace against the contained namespace, absent host paths, read-only container root, clean `/testbed` tree and its base Git tree, plus minimum free workspace. It uses only `--containall --cleanenv --no-home --no-mount hostfs,bind-paths --net --network none`, binding the per-run workspace image at `/testbed`. No model action is executed outside the container.

Budgets: Bouchet `day/normal`, `pi_gt353`, 2 CPUs, 8 GiB RAM, 15 minutes; one driver invocation bounded at 720 seconds plus a 15-second Slurm-side kill grace. Per-run copy and output are confined to the existing DTR project directory; local checks found 3.9 TiB filesystem free and no active user jobs. The account's home quota is small but nearly empty; job artifacts are placed in project storage. `quota -g` did not return a project-group limit, so the job independently checks at least 2 GiB free in its run directory before starting. No GPU is requested or initialized. The copied workspace has its own input and final hashes; the prior workspace artifact is not modified.

## Exact release identities

- Run ID: `req030-seaborn-runner-qualification-20260929-a`
- Release manifest: `experiments/lead_req030/seaborn_runner_qualification_release.json`, SHA-256 `3d7e08ccc160054effcf3d01965d2b5702671a9e3e6700b5b02f8b3d3c273783`
- Batch source: `experiments/lead_req030/seaborn_runner_qualification.sbatch`, SHA-256 `3995d185aa529dd504493dbfcd3fb4310a1b7629a6ad136b76e1753632969b8f`
- Source sums: `experiments/lead_req030/seaborn_runner_qualification.SHA256SUMS`, SHA-256 `29b22d20e99d2c40d54e22cfd24b6cc1ba2f794daf565f9d8c9eada6e3f7af7b`
- Driver SHA-256 `ab33fc7e310f07ed2ca2736d42076d8e14c1bbdfe97ef8bb2e1094bc15e2734b`
- Joined runner SHA-256 `b92f5e7d3b71f7a1416fed053613c406421dda1a682e7584b911147589d1bdb3`
- Native adapter SHA-256 `41d21de7526525fa4b07f53e08bb6d6cb86729db1eb77a76d4bf44cc624c0760`
- Supervisor SHA-256 `d39647136d7bb1c8d59d85389ff70f0e980cc6277760455ec773433daface974`
- Existing remote model manifest SHA-256 `27d054c155e7767ca2048d66c900d75131bf9a6c263fdce5180e06ed5fe6bad6`

The standard focused local suite passes **21 tests**; the runner/driver compile, batch `bash -n`, and `git diff --check` pass. Local tests deliberately use a fake Apptainer and do not establish a real namespace. The REQ030X batch job is the first direct test of that joined runtime. Its scientific acceptance is limited to: pinned prompt/render/token IDs are preserved; actual Apptainer preflight and both fixed actions finish with verified receipts; and the private trajectory records terminal submission. Any mismatch, missing receipt, signal, mount or resource failure is a qualification failure/unknown, never a model failure or positive result. Existing owner-SIGKILL evidence remains separate and is not silently substituted for an integrated fault test.

## Dispatch state — 29 September 2026

After publishing source commit `9b5f064e671a73f84edfead5d04b3d25778b7f29`, direct SSH confirmed no owned Slurm jobs. Identical `sbatch --test-only` shapes under `pi_fl426` and `pi_gt353` both estimated start at **22:09:56 UTC** on the same node; test-only IDs `27841114` and `27841115` were not submitted jobs. Both associations were eligible on `day/normal`; `pi_gt353` was selected because its fair-share was modestly better (`0.137735` vs `0.107798`) and its project directory holds the exact cached SIF/assets. A single real job, **27841116**, was submitted as `pi_gt353`, `day/normal`, 2 CPUs, 8 GiB, 15-minute limit. At inspection it was `PENDING` with no specific reason string; the test-only start estimate is not a reservation. The exact workdir is the unique run directory `req030-seaborn-runner-qualification-20260929-a` in the DTR project. No inference has run. Next: inspect this owned job at the next scheduled check; on terminal state, retrieve raw logs, `qualification.json`, trajectory/events, workspace hashes, SIF/tokenizer bindings, exit record, and `sacct` accounting before assigning any gate result.

## Decision after terminal review

Only if raw job logs, hashes, Slurm accounting, tokenizer receipts, namespace/workspace checks, action receipts, trajectory and workspace cleanup independently verify may this narrow runtime path be marked qualified. A failed qualification should be diagnosed at its exact boundary; preserve the raw attempt and do not duplicate it without a concrete correction. Even a pass does not authorize or establish a model task outcome.

The next scientific gate is then to select a prospectively justified competent executor pair and freeze independent task/family sampling, the estimand, exact task eligibility, decoding/token/cost budgets, and independent evaluation before any separate model-task release. REQ030R still has `n=1` task; its 250 declared test statuses are nested checks, not independent units. No CONFIRM/full benchmark, task-outcome retry, or outcome-driven tuning is released here.

**Readiness remains 55%, change 0 points, range 45–65%.** The remaining major milestones are competent fixed-target comparisons and valid task/family-level inference, empirical/manuscript synthesis, independent reproducibility, and the author-approved submission package.
