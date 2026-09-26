# DTR-REQ-019: source-only qualification inventory for a fresh repository-repair executor pair

Lead request: [`e6a1670`](../../../docs/theory_feedback_20260926_req018_review.md) (section "P0 DTR-REQ-019").

This is feasibility evidence only. No model weights were downloaded (the competence research only read public web
pages and metadata); no model was called, no server or container was started,
no paid service was used, and no archive was changed. Built by `experiments/v2_adapter/req019_executor_inventory.py`,
with tests in `tests/test_req019_executor_inventory.py`.

> **Erratum (lead `d0b905a`, [decision](../../../docs/theory_feedback_20260926_req019_decision.md)).** The inventory
> is accepted, and so is the hold on the current local pair. But C8's demand for published success under identical
> 16k/24-call conditions was the worker's operationalization, not a v2 gate: v2 section 3 calls that setup a
> development candidate and allows a versioned revision.
> - The leaderboard mean of 27.6 calls is not a bound on any model's chance of success within 24 calls.
> - The "cannot currently be met" and "BLOCKED follows from the contract itself" statements below overstate the case,
>   and the lead rejects them.
> - The hold rests instead on three things: missing same-harness capability, no defensible local
>   resource-differentiated pair, and the frozen endpoint and opportunity gates.
> - C8 is external-validity information, not an eligibility rule.
>
> `inventory.json` is left as published.

## Verdict: BLOCKED under the frozen v2 contract

The frozen contract comes from `configs/v2_req014_14b_capacity_probe_20260924.json`: mini-swe-agent `04d809c` with
bash text actions, a 16384-token slot, 24 steps, `max_tokens` 1536, the REQ-014 memory and disk rules, and
llama.cpp `4fea119`.

**Why BLOCKED:** no locally present, non-closed checkpoint has independent published SWE-bench Verified evidence
under a comparable contract (criterion C8). A fresh pair needs one checkpoint that meets C1–C8 (the stronger
executor) and a second checkpoint, of a different model, that meets C1–C7.

**Disclosure:** C8 as operationalized cannot currently be met by any published evidence, local or not.
- No published open-weight SWE-bench Verified result reports a run under a 24-step cap at 16384 tokens.
- On the swebench.com Verified board, the fewest mean mini-SWE-agent calls per instance among the 15 open-weight
  entries is 27.6.
- REQ-014 already ended in a context-limit operational zero under this contract.

BLOCKED therefore follows from the frozen contract itself. Qualifying any pair needs a lead decision on the
contract.

**What does qualify on C1–C7:** five fresh local checkpoints are present and servable. Each has a license, a
context of at least 16k and a memory fit, but none meets C8:

| Checkpoint | Revision | License | Independent repository-repair evidence |
|---|---|---|---|
| `Qwen/Qwen2.5-3B-Instruct-GGUF` (Q4_K_M) | `7dabda4` | qwen-research (public card) | none found |
| `Qwen/Qwen2.5-7B-Instruct-GGUF` (Q4_K_M) | `bb5d59e` | apache-2.0 (public card) | SWE-bench Lite only: 0.67 % raw, 2.67 % EffGen |
| `Qwen/Qwen3-4B-Instruct-2507` (safetensors, all 3 shards, index-complete) and `unsloth/Qwen3-4B-Instruct-2507-GGUF` (Q4_K_M) | `cdbee75` / `a06e946` | apache-2.0 | see below |
| `ibm-granite/granite-3.3-8b-instruct-GGUF` (Q4_K_M) | `e40e9dd` | apache-2.0 | none found |

The Qwen3-4B-Instruct-2507 evidence is the only independent SWE-bench Verified evidence for any of these, all under
OpenHands:
- 11.2 % on 466 tasks at 64K context with up to 100 interactions;
- 5.2 % at 32k and 7.0 % at 128k context.

**Relaxed alternative (not a verdict).** If the lead accepted evidence from a different scaffold and a larger budget,
Qwen3-4B-Instruct-2507 would be the only candidate for the stronger executor. It is the only fresh local model with
any evidence. That would change the frozen contract, which is a lead decision.

Memory under the REQ-014 static rule (weights + f16 KV + 16 GiB VM allowance ≤ 30 GiB). The rule checks each model
alone, and the frozen setup serves one model at a time; the pair rows are a joint extension of the rule, with the VM
counted once:
- Each candidate fits alone at 32768 tokens (19–26 GiB).
- Two different models served concurrently all fit at the frozen 16384 tokens (23.1–28.3 GiB).
- At 32768 tokens all fit except the pairs with granite-3.3-8b and either Qwen2.5-7B or Qwen3-4B (31.7 and 32.4 GiB).
  Qwen3-4B with Qwen2.5-3B is 25.9 GiB; with Qwen2.5-7B it is 28.9 GiB. Under the per-model rule every candidate
  fits.

In the relaxed pairs, the admitted "small" models have no Verified evidence and some are larger than the 4B model.

**Everything else is excluded:**

| Excluded | Reason |
|---|---|
| Qwen2.5-Coder-7B/14B, all copies | closed by the lead |
| DeepSeek-Prover-V2-7B and its MLX copy, Kimina-Prover-RL-1.7B, the LeanDojo byT5 models | theorem provers |
| gte-large, byT5 | encoders; T5 encoder-decoders are also not servable by the pinned llama-server |
| 14 checkpoints outside the HF cache and this repository | provenance cannot be bound to a public release; published anonymously as `other-local-NN` (one is byte-identical to another) |

MLX-quantized weights are not convertible by the pinned converter.

Every checkpoint lists all its weight shards. Where a shard index exists, it is checked for completeness.

## Files

- **`inventory.json`:**
  - host envelope (live readings at build time, see `inventory.json` host): Apple M5, 32 GiB, memory free 59 %, swap 14.4 of 15.0 GiB used, host disk 67 GiB free, running Colima VM `dtr` with 16 GiB memory and 81 GiB VM disk free;
  - peers: no model server running; port 8770 is macOS `sharingd`, not touched;
  - harness, dataset and evaluator pins, with harness licenses (all MIT) and source/venv presence;
  - builder and evidence sha256;
  - every local checkpoint with sha256 of each weight file, license and its source, architecture, context, KV at 16384 tokens, servability basis and memory projection;
  - the exclusion list, the per-criterion matrix and the verdict.
- **`candidate_matrix.csv`:** criteria C1–C8 per checkpoint, plus the any-independent-evidence column.
- **`competence_evidence.json`:**
  - read-only web research (three research agents and a citation verifier, 2026-09-26), with URLs;
  - per-model flags;
  - not-local reference models with public configs and memory projections.

## Excluded tasks

70 SWE-bench Verified IDs are excluded from future untouched evaluation:
- REQ-008's 64 model-outcome-exposed IDs (conservative definition, lead `0fe40b8`);
- its 5 qualification-or-inspection IDs;
- `astropy__astropy-14598`: REQ-010 sentinel, and model episodes in REQ-011, REQ-012 and REQ-014 (REQ-013 ran no model
  episode).

The lead's REQ-009 rules exclude 19 more, bringing the total to 89 (`exclude_including_lead_rules`, with an ID-list
sha256):
- 11 component-mates of exposed or qualification-only tasks;
- 8 tasks with an empty PASS_TO_PASS.

A scan of every `configs/v2_*.json` finds no pinned ID outside the list. The REQ-009 design queue has 23 remaining
unexposed IDs.

## Not local (context only; any use needs a download)

These projections use Q4_K_M at 4.97 bits per weight and 16 GiB for the VM:

| Model | Evidence | Projection | Fits? |
|---|---|---|---|
| Devstral-Small-2-24B-2512 | independent 56.4 % mini-SWE-agent bash-only | about 32.4 GiB | no |
| Qwen3-Coder-30B-A3B | vendor 51.6 % OpenHands | about 35.2 GiB | no |
| gpt-oss-20b | vendor 60.7 % internal scaffold; no independent mini-SWE-agent result | about 28.9 GiB | yes |

## Criteria (the worker's operationalization, for the lead to accept or change)

- C1: present locally.
- C2: servable by the pinned llama.cpp or its converter.
- C3: license recorded locally or on the cited public card.
- C4: not closed.
- C5: a public general or code instruct release.
- C6: context of at least 16384 tokens.
- C7: fits the REQ-014 memory projection.
- C8: independent SWE-bench Verified evidence above zero under a comparable contract.

The lead selects and freezes any pair.
