# REQ030: Bouchet GPU runtime qualification

The author authorized use of both project accounts for this research on 28 September 2026 UTC. Both standard-tier B200 test-only requests returned the same predicted start; pi_gt353 was selected. Test-only identifiers are not jobs. Direct local SSH still requires interactive authentication; the already authenticated auxiliary-Mac SSH route works. Authentication material remains outside Git.

## Exact first allocation

Actual Slurm job **27713899**, unique run `req030-gpu-probe-20260928-a`, standard `normal` QoS, `gpu_b200`, one B200, four CPUs, 32 GiB host RAM, ten minutes maximum. First post-submission scheduler inspection: **PENDING**, no allocation or result yet. Submission succeeded once, with remote source SHA-256 verification. No model inference has been dispatched.

Sources: `experiments/lead_req030/bouchet_gpu_probe.py` and `.sbatch`. Installed module: `PyTorch/2.9.1-foss-2024a-CUDA-12.8.0`, Python 3.12.3. Python syntax compilation and batch shell syntax passed locally. The installed module lacks Transformers; no unpinned runtime installation or weight download was performed.

The compute-node probe requires exactly one visible CUDA device and the pinned Torch/CUDA versions, records GPU identity/capability/memory and peak tensor memory, and compares a 1024-square bfloat16 matrix product with its float32 reference (relative norm error <0.02). Slurm owns process termination. No listeners, task data, models, downloads or peer changes. New output is bounded to small JSON and scheduler logs; no model cache is created.

## Acceptance and next work

Retrieve `result.json`, source checksums, Slurm stdout and accounting from the run directory under the affiliated user's project storage. Verify COMPLETED/exit zero, actual allocated resources, numerical assertion and recorded GPU capability. A passing result qualifies only this basic CUDA operation, not Transformers, an LLM service, a model comparison or benchmark sandbox.

Next freeze an exact canonical model revision/license, compatible Transformers dependencies, context/decoding budget, storage cap and GPU-native batch inference pilot. Treat CUDA/BF16 versus previous Metal/GGUF as a changed execution kernel. Do not replay failed exposed tasks to obtain favorable outcomes. Keep primary targets and CONFIRM held. A one-GPU pilot precedes any multi-GPU request; aggregate memory is not automatically usable by an unsharded model.

Check job 27713899 at the existing two-hour review; pending is not failure and must not cause resubmission. If terminal, inspect evidence and continue the next concrete qualification in that cycle. Both prior local admission failures and task failures remain immutable.

Readiness **55%, change 0 points, range 45–65%**. Remaining: competent fixed-target comparisons and valid inference, manuscript synthesis, independent reproducibility and author-approved package. HPC access addresses capacity; it does not establish scientific success.

## Terminal verification

Slurm27713899 COMPLETED/0:0. Submitted27September21:22:01ET, started21:25:01ET, ended21:25:36ET: three-minute queue,35-second allocation (0.00972 GPU-hours). Actual NVIDIA B200 sm100,191502876672 visible bytes, driver580.178.04, pinned Torch2.9.1/CUDA12.8. BF16 relative error0.00165966665 passed0.02 threshold. Eight raw archive member hashes recorded; both remote source files independently matched local committed bytes. Evidence: `results/local_req030/bouchet_gpu_probe_20260928`. No model deployment/inference yet. This job is terminal; do not resubmit. Readiness55%,Δ0,range45–65%; remaining scientific milestones unchanged.
