# REQ-028A: 32k Qwen mechanics interrupted by memory pressure

**Worker result: capacity interruption; mechanics acceptance not met.** This is actual model-serving evidence under released REQ-028A, not a coding competence result. REQ-028B source/interface planning is complete in experiments/remote_req028/split_host_proposal.md; transport release, Klear acquisition and task competence remain lead-gated. The continuing experimental goal is active at a lead decision checkpoint.

## What actually ran

On the 16-GiB Apple M4 mini, source commit 4fea119de30f6a923992780f6fd5ccb0bee5d47d of official llama.cpp built successfully using two build jobs and an isolated, checksum-verified CMake 3.31.8. No global packages were replaced.

The selected Qwen3-4B-Instruct-2507-Q4_K_M.gguf was downloaded from unsloth/Qwen3-4B-Instruct-2507-GGUF revision a06e946bb6b655725eafa393f4a9745d460374c9. Its 2,497,281,120 bytes and SHA256 3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597 match the released specification exactly. No alternate weights were loaded.

The inference manifest was frozen before serving. Server PID 36336 bound only 127.0.0.1:58898 with one slot, context 32,768, f16 K/V, prompt-cache RAM 0, per-request cache disabled, temperature 0, seed 20260927028 and output cap 128. The exact command, prompts, binary/dynamic-library/source/template hashes and expected response schema are in mechanics_20260927/manifest.json. Flash attention was explicitly on; two CPU generation/batch threads and two HTTP threads were set. Warmup was explicitly disabled to avoid an extra unrecorded empty generation.

At 2026-09-27T02:52:31.002671Z the mechanics phase began. The server became healthy in 2.100213 seconds and /props confirmed one 32k slot. The first exact DTR_READY request began at 02:52:33.150845Z. The independent watchdog observed adverse system memory pressure and terminated the owned process group. The request ended 0.644925 seconds later with RemoteDisconnected and no response body. Mechanics phase ended at 02:52:33.802842Z. The server's return code was -9 following the bounded TERM/KILL cleanup; release is confirmed. Watchdog PID 36338 also exited. No own server remains.

| Measurement | Admission | First load sample | Abort sample |
|---|---:|---:|---:|
| macOS system-wide free metric | 79% | 23% | 20% |
| Pressure level | 1 (normal) | 1 (normal) | 2 (adverse) |
| Swap used | 233.31 MiB | 233.31 MiB | 233.31 MiB |
| Owned process-group RSS | 0 | 3,426,615,296 B | 4,905,304,064 B |

The abort was triggered by adverse pressure, not by swap growth, the 11-GiB RSS limit, or strictly-less-than-20% free metric. No foreign inference workload was detected. Metal memory is not fully characterized by the RSS sample; these observations do not identify a precise buffer decomposition. The nominal 11.026-GiB planning sum and admission metric did not guarantee sufficient capacity at generation.

| Logical call | Recorded disposition |
|---|---|
| 1: exact DTR_READY | Started; interrupted by owned resource watchdog; no response |
| 2: command fence | Not attempted after resource abort |
| 3: restarted DTR_READY | Not attempted; no second load |
| 4: restarted command fence | Not attempted; no second load |

Token counts, generation tokens/sec and format compliance are unavailable because no terminal response was received. Missing outcomes are retained explicitly. No generated command was executed. A successful health response does not satisfy the four-call acceptance gate. No context/KV/model fallback, repeat load, retry or additional experiment followed the abort.

## Setup supervision deviation and correction

The initial independent setup watchdog exited early because its exact full-command identity comparison did not tolerate the macOS Python launcher's expansion of its executable path. The build and early download therefore lack continuous original-watchdog samples; they must not be presented as fully supervised. Admission was recorded. The failed record and the 32661 watchdog identity are preserved in setup_watchdog_20260927 and setup_watchdog_recovery_20260927/deviation.json.

The implementation was corrected to validate process group, birth time and owned argv suffix (or unique server ownership token). A corrected watchdog (PID 35426) was attached only after verifying the existing setup process PID 32659. Subsequent samples are retained. Setup completed with return code 0 and owned release. Before inference, final fake tests exercised deadline expiry, controller death and the Python-launch transition, while checking that a separate decoy remained alive. Mechanics additionally requires the independent watchdog's verified-identity handshake before proceeding. All inference resource samples are present; its actual adverse-pressure abort demonstrated owned cleanup.

No evidence proves resource limits held during the original setup supervision gap. This deviation remains for lead assessment even though later observations were normal and the actual inference watchdog worked. The simple process-birth check has one-second ps timestamp granularity; PID/group/argv/token checks reduce reuse risk, but do not provide a kernel-level process handle.

Setup stayed below the released limits by observed duration and retained byte inventory: started approximately 02:44:31 UTC including checkout; completed 02:52:23.82 UTC; model transfer took 239.31 seconds. Isolated assets occupied approximately 3.0 GiB on disk and about 20.7 GiB remained free. Pinned model plus dependency archives total less than 3 GiB downloaded, below the 5-GiB cap; added disk including the separate checkout is below 8 GiB. Continuous setup enforcement was impaired as disclosed above.

## Interpretation and next decision

The mini has built a pinned runner and has the selected verified small-model artifact. It demonstrated initial 32k serving health but failed the released mechanics resource gate during its first real request. It has not qualified a four-call restart cycle, coding competence, general determinism, full-context throughput, or routing benefit.

The existing shared Ollama service, Kimina artifact and Lean work were untouched. No VM or benchmark task ran on the mini. Klear public file metadata was inspected for the authorized proposal, but its weights were not downloaded. The split-host proposal identifies the source-bound adapter, full-history/attempt/deadline contract, absent configured inference tunnel, canonical Klear conversion disk requirement and a separately provenance-gated community artifact candidate.

Lead decision needed: assess this exact capacity interruption and setup deviation; choose a versioned feasible next serving envelope or host allocation, plus secure benchmark-host transport and exact stronger-model provenance. The worker does not infer permission to lower context, change KV quantization, load Klear, or release 028C.

## Reproduction and audit

All commands below are descriptive; mechanics.py refuses an existing run directory and must not be rerun without the lead's next release.

- Build/download entry: python3 experiments/remote_req028/guard.py run results/remote_req028/setup_watchdog_20260927 2400 python3 -u experiments/remote_req028/setup.py
- Unit fake tests: python3 experiments/remote_req028/test_guard.py
- Final independent-watchdog fake tests: python3 experiments/remote_req028/test_watchdog_integration.py final
- Mechanics entry: python3 experiments/remote_req028/mechanics.py
- Pre-inference source/test receipt: pre_inference_validation_20260927.json.
- Frozen mechanics manifest SHA256: 5ad363ab0f80f00db8bc556386fa45762f1ed553b4e7380941f9939fd9498427.
- Embedded template SHA256: c979e0e71a3e21b8f208e6ab120d5cb29327885f29d2a8b18fda67a723798e18.
- Runner executable SHA256: fd4de7db51a60ad4710725b5e2d2da9060a0b56bf7759767ba81ac719abc4222.
- mechanics_20260927/sha256.json verifies the saved inference artifacts; source hashes match the recorded pre-inference source.

Only owned source and results are published. Weights, dependency binaries, credentials and unrelated process arguments are excluded. Worker validation is distinct from lead scientific acceptance.

Full-project readiness **55%, change 0 points, judgment range 45–65%**. Competent fixed-target comparison and valid inference, final empirical/manuscript synthesis, independent reproducibility and approved submission package remain open.
