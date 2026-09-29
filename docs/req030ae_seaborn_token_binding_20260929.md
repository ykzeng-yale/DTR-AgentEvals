# REQ030AE — preserve the complete native prompt token binding

## Scientific gate and REQ030G result

The highest-impact unresolved scientific milestone remains a competent fixed-target executor contrast with valid task/family-level inference. The immediate prerequisite is narrower: establish that the real pinned public prompt, agent, native tokenizer, isolated tool loop, and durable terminal receipt are bound consistently before any separate model-task release.

Slurm job `27860645` actually ran on `pi_gt353/devel`, requested 2 CPUs/8 GiB/15 minutes, and ended `FAILED 1:0` after 43 seconds (MaxRSS 2,808,140 KiB). Its 16-event record has two request/response pairs, two fixed harmless tool actions (both exit 0), one empty terminal submission, and a trajectory whose digest matches the terminal event. The first request's message and rendered-text hashes match the frozen initial prompt. Its recorded `input_ids` contain 1,129 integer token IDs. The run has no official qualification receipt because the lead driver assertion failed before `qualification.json` was written.

The cause is a lead-owned measurement/assertion bug, not a task or tokenizer mismatch: for an unbatched Hugging Face tokenizer call without `return_tensors`, `tokenizer(text)["input_ids"]` is a flat list of token IDs, so indexing `[0]` selects a scalar first token. The adapter correctly recorded the complete sequence, and the driver compared that list with the scalar. The matching message and rendered hashes argue against an input-content/design mismatch. The allocated job completed its path in 43 seconds with the full inert event/trajectory evidence, which argues against capacity failure for this attempt; the 2.8-GiB MaxRSS alone is not a capacity diagnosis.

Independent replay of the private archive checked its SHA-256 (`c789f439f62c6f5566093fc9117f7f789884d6cc138b81924b918315f225eeea`), matched all 14 release source pins against the frozen G snapshot, matched the trajectory digest, and verified 15 available run-level files against their archive list. The archive's `SHA256SUMS` includes an invalid empty-file self-entry; that entry was excluded, and the archive digest plus individual files were verified separately. Raw prompt/event content remains private at `results/local_req030/seaborn_runner_g_failure_20260929/evidence.tar`; the sanitized [lead replay](../results/local_req030/seaborn_runner_g_failure_20260929/lead_replay.json) contains no rendered prompt or host inventory.

This failed attempt does **not** qualify the runner and produces no model/task result. No Seaborn tests, reference patch, evaluator statuses, model weights, learned generation, or GPU inference were used. The separate REQ030R evaluator control remains valid only for one task in its explicitly modified offline image: baseline 2/2 declared F2P failures plus 248/248 P2P passes; reference 250/250 declared checks pass.

## Correction and regression acceptance

`single_sequence_token_ids` now normalizes a flat tokenizer list, a single batched list, a tensor, and a test tensor-like object to the same complete sequence. It rejects empty input, multiple sequences and non-integer IDs. Both the adapter's durable request event and the driver's independent expected-prompt binding use that helper. The in-job regression exercises flat/batched/tensor-like shapes; it runs together with release/source layout, pinned agent serialization, clean bootstrap and terminal-submission regressions.

The focused native-adapter, public-input, supervisor and bootstrap suites pass 26/26 locally. An isolated staged-bundle replay from the exact `payload/` plus run-root `release.json` layout passes all 6 bootstrap tests. `bash -n`, payload hashes and `git diff --check` pass. These checks establish deterministic code behavior in the local/staged fixtures; only the actual fixed, isolated Bouchet run can validate the joined remote tokenizer/agent/container path.

## Frozen release H

One inert CPU-only qualification is prepared as `req030-seaborn-runner-qualification-20260929-h`:

- Account/partition/QOS: `pi_gt353/devel/normal`; 2 CPUs, 8 GiB, 15 minutes.
- Manifest SHA-256: `8745506aa297a539a10518b411ba1fb45d0b6bd5430f8dd7d71b9d49decd9f05`.
- Batch SHA-256: `16791e915757957f9b31300def9ade90802309dede89c9226e72538b4fbf992a`.
- Payload sums SHA-256: `941f5f31cf8587eb5815daaa30e1f566d9c4f3deb2c7dc4fada62010f3fe3c48`.
- Adapter SHA-256: `7b07d847d7ab933b7aaecb577fb44d30dbfc3b5ea322e9fb9b2c39ce9fff2cfa`.
- Qualification driver SHA-256: `9d6c7474068a560d39156fe51a547710a05b99a7a2126b200a67752530d54c86`.
- Bootstrap regression SHA-256: `7498470cca843855d400ec75993dc62dbd56448c093fa0262ed13636eb2b5df7`.
- Task SIF SHA-256: `9da1f51cb8c01a6ad9e0db4d1969742fbec995021e78150a9623d4f4719a8a47`; workspace seed SHA-256: `3cc8a60a720e00816e2853bce4e47d58705443cf6f4e8a4531ca69ae458b8100`.
- Qwen tokenizer revision: `381fc969f78efac66bc87ff7ddeadb7e73c218a7`; tokenizer only, with model weights not loaded.

The release contains the one public Seaborn projection, a real pinned tokenizer, two authored deterministic fake outputs, two harmless fixed commands, a read-only-root/network-none Apptainer task image and a private bounded workspace. It excludes learned weights, evaluator/reference inputs, benchmark tests, downloads, model-generated commands and GPU work. A pass can clear only this joined inert runtime/receipt gate. It does not authorize or automatically trigger model-task inference.

Readiness remains **55%, change 0 points, range 45–65%**. Largest remaining milestones: a competent fixed-target comparison with prospective task/family-level valid inference; empirical/manuscript synthesis; independent reproduction; and author-approved metadata/submission packaging.
