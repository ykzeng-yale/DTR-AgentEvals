# REQ030W — inert Seaborn runner join

**Disposition: accept the local source/control-flow integration as a development gate. It is not an Apptainer qualification, model trajectory, model outcome, or new run authorization.**

## Highest-impact unresolved question

After REQ030R accepted the unchanged/reference evaluator controls for one Seaborn issue, the main blocker is whether one production-shaped process can bind the approved public issue, the pinned mini-swe-agent prompt/action parser, the native HF text adapter, and the isolated `/testbed` through the bounded supervisor, while preserving enough durable evidence to tell a task result from a runner failure. Separate passing component fixtures did not establish that joined path. The one-task control result also remains `n=1`; its 250 nested checks are not 250 independent tasks.

## Implementation

`experiments/lead_req030/seaborn_apptainer_runner.py` adds the common runner boundary. It accepts only the hash-checked public projection and no evaluator/reference path. Before model construction it verifies the task SIF, workspace image, and supervisor files; inspects and records the Apptainer executable/version; records actual host `platform.uname()` and network-namespace identity; and runs a fixed preflight through the same bounded supervisor and Apptainer flags used for tool actions. The preflight checks network-namespace separation, absent host paths, read-only image root, clean workspace, available space, and equality of the workspace tree to the public task's base commit. This permits the previously documented metadata-only setup commit while checking that the task source tree is unchanged.

Every command action is passed as an argv element to `/bin/bash -lc` **inside** the pinned SIF with only the fixed image-backed `/testbed` workspace bound. The caller-to-supervisor owner pipe supplies EOF cleanup on driver death. Tool bytes, deadlines, action size, event-log size, trajectory size, and private file modes have explicit caps. The request record is fsynced before the model call; response receipts retain token IDs and refer to the exact request hashes without duplicating the full rendered prompt. Each action has a raw bounded output file plus a hashed supervisor receipt. The workspace image is hashed once at input and once after execution, avoiding a full 512 MiB/1.2 GiB re-hash on every model step. Terminal submission is accepted only on the exact marker, zero tool exit, and normal supervisor exit. Failures preserve a private partial trajectory when one exists.

The code pins the supervisor, image, and initial workspace identities supplied by the exact run manifest. It records the actual Apptainer binary hash/version and checks task-image inode/size/mtime across actions. No host-wide Git trust exception, reference mount, network, or test-evaluator API is introduced.

## Evidence and limits

The combined local focused suite passes **21 tests**:

```text
.venv/bin/python -m pytest --import-mode=importlib -q \
  experiments/lead_req030/test_native_hf_text_adapter.py \
  experiments/lead_req030/test_seaborn_public_input.py \
  experiments/lead_req030/test_seaborn_control_replay.py \
  experiments/lead_req030/test_bounded_supervisor.py
21 passed
```

This set includes a single fake-model `DefaultAgent` trajectory through the adapter/environment API to terminal submission, ordered durable events and private receipt modes; fail-closed behavior before preflight; and timeout/output-cap receipts. The fake Apptainer records the requested argv and emits canned bytes. It does **not** execute the action, use a real Linux namespace, run real Apptainer, load weights, call a model, run tests, or see evaluator/reference input. The previously completed REQ030O Slurm fixture separately verified actual controller SIGKILL and disappearance of an isolated detached child; it did not run this joined module. Local MacOS lacks `/proc/self/ns/net`, so local tests inject a test-only namespace value; only the Bouchet runner can establish the real namespace check.

Source SHA-256: runner `b92f5e7d3b71f7a1416fed053613c406421dda1a682e7584b911147589d1bdb3`; focused test module `2e739af64d61e2397e523dd2e0d8fda76a1564ca874e6f4009c666435c554fca`; bounded supervisor `d39647136d7bb1c8d59d85389ff70f0e980cc6277760455ec773433daface974`. Python byte-compilation, shell syntax, and `git diff --check` pass. This was an implementation/control-flow audit, not new empirical evidence about model or DTR performance.

## Decision and next dependency

REQ030X below extends this local gate with the **real pinned Qwen tokenizer** but retains a fixed scripted model with no weights. It does not alter the interpretation of the 21 local tests.

The evidence still does not identify DTR theory as the blocker. REQ030C showed the 32B weights fit one B200 for two short probes, which argues against basic device memory being the present integration blocker but says nothing about competence or full-task latency. Most important contrary evidence remains that the science still has no competent fixed-target comparison or valid task/family-level inference; runner work only unlocks that work. Evaluator controls remain one issue in an offline-modified image. No CONFIRM or full benchmark is released.

**Readiness remains 55%, change 0 points, range 45–65%.** Remaining major milestones: competent fixed-target comparisons and valid independent-unit inference; empirical/manuscript synthesis; independent reproducibility; author-approved submission package.
