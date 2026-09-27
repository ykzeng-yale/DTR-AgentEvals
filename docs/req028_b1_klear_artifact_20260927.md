# REQ-028B1: acquire and audit a precisely identified Klear candidate

## Lead acceptance and next scientific decision

A6R3482ed1 establishes bounded q8-cache Qwen serving for both synthetic prompts:
8192tokens/32.699seconds and24576tokens/158.882seconds, both exact DTR_READY.
Lead independently verified29 mechanics artifact hashes, both rendered/token-ID
bindings and raw response/usage receipts,184 normal-pressure samples, and passed
37 focused tests. ObservedKV2448MiB matches the nominal allocation. Owned driver,
model and watchdog are reported absent. These are real-model serving results,
not coding competence, restart qualification or proof of causal cache effects.

Further literal Qwen repetitions would not address the missing stronger-model
pair. REQ-028B identified a pinned community Klear GGUF and a canonical local
conversion whose35.25GiB peak does not fit mini disk. The lead selects a bounded
acquisition/metadata audit of the community candidate as the next prerequisite.
It avoids installing conversion infrastructure or silently pretending an unverified
community conversion is the canonical artifact. This choice does NOT adopt the
candidate for benchmark evaluation; that requires review of actual metadata and
subsequent competence evidence. No author-reported canonical score transfers.

## Exact released asset and provenance boundary

Repository mradermacher/Klear-AgentForge-8B-GGUF, revision
0626423882f502d6fe113bd0ddc61970b19d942b, filename
Klear-AgentForge-8B.Q4_K_M.gguf, bytes5027783808, SHA256
9c0909b89b518283ded8ca415694743bd922e8844356db4f26957e37047142ae.
Download only the pinned Hugging Face resolve URL; no main alias/substitution.
The pinned publisher card declares Kwai-Klear/Klear-AgentForge-8B as base and
Apache-2.0 licensing. It does not establish exact canonical source revision,
converter version or weight equivalence. Preserve that unresolved provenance;
byte integrity proves reproducibility of this community artifact only.
Source-card receipt: audits/req028_b1_source_receipt_20260927.json.

One streamed download to an owned assets partial file, no model loading/inference.
Rename verified file in place; no duplicate full copy. If an exact verified file
already exists, reuse it and record provenance instead of downloading again.
No automatic whole-file retries or extra variants. Cap20minutes,6GiB network
(including metadata),5GiB new disk, one connection at<=20MiB/sec; hash/metadata
work one CPU process with monitoredRSS<=2GiB. Enforce deadline and record actual
bytes/time/handles; preserve a failed partial without renewing. No system packages,
cache clearing, peer/Lean changes or removal of other assets.
Before download confirm A6R50009/50544/50546 absent, normal pressure, no foreign
inference, and measured free disk minus all remaining planned bytes>=12GiB.
During work sample at most every5seconds: stop own work on adverse pressure,
free<20%,swapgrowth>512MiB,RSS>2GiB,disk<12GiB,peer inference or deadline.
Do not treat file download as model execution or infer reserved memory from
nominal RAM. No permission to stop unrelated tasks.

## Deliverable and checks

Publish tested acquisition/verification source before launch. Tests must cover
size/hash mismatch rejection, existing-valid-file reuse, deadline/disk admission,
and interrupted partial retention without duplicate launch. Guard the owned
process and record its identity/deadline. Keep weights outside Git. Publish only
sanitized receipts, metadata, hashes and license/source URLs.

After integrity verification, parse GGUF metadata with the existing bounded reader
without loading tensor weights. Record architecture/layers/heads/KV dimensions,
context, quantization, tensor inventory, tokenizer IDs/vocabulary and chat template
hashes. Retrieve <=30MiB of pinned canonical metadata (config.json,
tokenizer_config.json, tokenizer.json, special_tokens_map.json when present,
README/license) from Kwai-Klear/Klear-AgentForge-8B revision
fa3d41e92e9ce7a5b4a52a3e7439aa00521f40c9. Missing optional files are reported,
not substituted with main. Compare architecture and tokenizer/template fields
explicitly, identifying exact matches, representation differences and unresolved
weight/converter provenance. Do not edit template or weights to force a match.
Keep original metadata immutable. No canonical weight shards or conversion.

Report an artifact/interface compatibility table and updated q8_0/32k single-model
memory estimate using actual dimensions and bytes. Do not claim measured Klear
allocations or competence. The next lead release will specify a bounded Klear
mechanics/competence step only after this receipt is reviewed. Transport/VM,
benchmark/CONFIRM and both-model residency remain held. No more Qwen inference
is requested in this stage. Continue acquisition/audit/publication without waiting
between authorized steps; report actual process state and product goal separately.

Readiness55%, change0points, range45–65%. Remaining competent fixed-target
comparison/valid inference, final empirical/manuscript synthesis, independent
reproducibility and author-approved submission package.
