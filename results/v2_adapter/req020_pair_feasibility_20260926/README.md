# DTR-REQ-020: source-only feasibility of Klear-AgentForge-8B (stronger) with Qwen3-4B-Instruct-2507 (smaller)

Lead request: [`d0b905a`](../../../docs/theory_feedback_20260926_req019_decision.md) (section "P0 DTR-REQ-020").

This is feasibility evidence only. No model weights were downloaded, no model was run, and no server, container or
compute reservation was made. No task was exposed and no v2 source pin changed. Built by
`experiments/v2_adapter/req020_pair_feasibility.py`, with tests in `tests/test_req020_pair_feasibility.py`.

## Verdict: BLOCKED — NO for both prelisted envelopes

**The failing gate is G4, simultaneous memory.** Call-level routing needs both models served at once. G4 is checked two
ways, and both fail:
- the REQ-019 joint extension of the per-model REQ-014 static rule (both Q4 weights + both f16 KV caches + one 16 GiB
  evaluator-VM allowance ≤ 32 GiB − 2 GiB);
- the REQ-014 post-load reserve, which requires at least 20 % memory free after loading, projected from the current
  host reading.

Both models have 36 layers × 8 KV heads × head dim 128. G4's inputs are mixed: Klear's geometry is source-inspected,
Qwen3-4B's file size and the host memory are host-measured, and the rule constants are frozen.

| Envelope | Klear Q4 (est.) | Qwen3-4B Q4 (local) | KV large | KV small | VM | Total | Limit | Verdict |
|---|---|---|---|---|---|---|---|---|
| 32k context, 48 calls | 4.739 | 2.326 | 4.500 | 4.500 | 16 | **32.065 GiB** | 30 GiB | NO (2.07 GiB over) |
| 64k context, 100 calls | 4.739 | 2.326 | 9.000 | 9.000 | 16 | **41.065 GiB** | 30 GiB | NO (11.07 GiB over) |

The Klear Q4 figure is an estimate at 4.97 bits per weight from its 8,190,735,360 parameters. The published community
Q4_K_M (5,027,783,808 bytes) gives 32.008 and 41.008 GiB, also NO.

**Post-load reserve** (host-measured at 2026-09-26T09:22:27Z; the running Colima VM is already counted in free memory): free memory after
loading both models' weights and f16 KV would be 9.8 % at 32k and -18.3 % at 64k, against the 20 % required. Both fail.

Sequential serving is not treated as evidence that call-level routing is feasible.

**Sensitivities (lead decisions, not the verdict):**
- **q8_0 KV cache at 32k:** 27.846 GiB under the static rule, and 23.0 % free after load. Both pass, but only
  narrowly, before two compute buffers and the pinned llama-server's default prompt cache of up to 8,192 MiB per
  server.
- **q8_0 KV cache at 64k:** 32.627 GiB and 8.0 % free. Both fail.
- **Smaller VM:** with f16 KV, 32k fits the static rule only with a VM allowance of 13.93 GiB or less.

The static rule's model side omits compute buffers and prompt cache, so it is optimistic. Its 16 GiB VM charge is a
fixed allowance.

**All other gates pass:**

| Gate | Result | Basis |
|---|---|---|
| G1 source pin | `Kwai-Klear/Klear-AgentForge-8B` revision `fa3d41e9…`, Apache-2.0, 4 safetensors shards (16,381,516,824 B) with LFS sha256, complete against the index; the model card is empty | source-inspected |
| G2 architecture | `Qwen3ForCausalLM`, which the pinned llama.cpp `4fea119` supports and its converter registers | code-inspected |
| G3 context | Klear's maximum context is 65,536 tokens, so the 64k envelope sits exactly at the limit | source-inspected |
| G5 disk | download + bf16 GGUF + Q4 peak 37.9 GB leaves about 30.1 GiB, at least the 25 GiB host minimum; VM disk 81 GiB free | host-measured |
| G6 admission now | 60 % memory free (≥ 50 %); no model server or stage process running. Swap is 14.4 of 15.0 GiB used; recorded, not gated | host-measured |

## Risks recorded, not gates

**Action and submission protocol mismatch** (code- and source-inspected). The frozen harness is `yaml-v1-repair1`,
built on the pinned `default.yaml` (sha `112aa583`, `yaml-v1`); the three differences hold under both bindings. Klear
was trained differently:

| | Frozen harness | Klear training |
|---|---|---|
| Fence | ```mswea_bash_command | ```bash |
| Submit sentinel | `COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT`, hard-coded in the pinned DockerEnvironment | `MINI_SWE_AGENT_FINAL_OUTPUT` |
| Edit tool | none | str-replace helper |

Whether Klear follows the frozen prompt is not identifiable from source (compare the REQ-016 format failure).
Qwen3-4B's training data are unpublished, so there is no public evidence either way about its exposure to either
protocol.

**Chat-template path.** The pinned llama-server renders with jinja by default. The Klear template matches no
specialized handler and falls through to the differential autoparser, whose behaviour for this template is unverified
without running it.

**Budget differences.** The 48 and 100 calls are read as logical agent calls; each keeps up to 2 physical attempts. The
frozen per-call settings are temperature 0, `max_tokens` 1536, a 1,800 s episode wall and a 60 s command timeout.

**Published competence is not comparable** (`klear_evidence.json`):
- The authors report 39.4 % SWE-bench Verified, a single figure with temperature and run count not stated. It used
  mini-swe-agent-plus with 200 steps, 64k context, the edit tool and a matching prompt.
- The only independent figure found is 26.6 % (ContextRL). It is most likely for the SFT checkpoint rather than the
  merged model, under another mini-SWE-agent setup.
- Neither figure establishes competence under the frozen harness or either envelope.

**Exposure:**
- Klear's SWE SFT data comes only from SWE-smith (12k problems, about 66k trajectories). The released set holds 0 rows
  from the 12 SWE-bench Verified repositories; 11 of 12 were re-queried by the verifier, and matplotlib is unresolved.
- **Near-duplicates and selection:** SWE-smith covers neighbour repositories of SWE-bench projects (e.g. astroid,
  django/channels), and its toolkit profiles flag SWE-bench_Verified eval sets. The Klear runner carries undocumented
  verified100/verified236 subsets and an unnamed RL validation set, so selection on Verified cannot be excluded.
- The SWE RL data is unreleased, the decontamination is repository-level only, and base-model pretraining exposure is
  not addressed. Contamination therefore cannot be excluded.
- The REQ-019 70/89-ID exclusion lists are unchanged.

## Files

- **`feasibility.json`:** the per-envelope memory rows (f16, q8_0, and community-GGUF size), the post-load reserve,
  gates, verdict, protocol comparison, budget comparison, exposure summary, disk, host admission and peers.
  - Each observation is labelled source-inspected, code-inspected or host-measured.
  - The host readings carry `host_measured_utc`, and the builder refuses to overwrite them without `--force`.
- **`klear_evidence.json`:** 59 cited facts from read-only web research (three agents and a citation verifier). Names
  and internal paths are replaced by role labels.
- **`source/`:** the public files read at revision `fa3d41e9`: HF API metadata, `config.json`,
  `generation_config.json`, `tokenizer_config.json`, the shard index, the card, and a redacted `merge_config` summary
  with the original's sha256.
