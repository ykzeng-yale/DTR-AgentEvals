# REQ-028B1 terminal artifact and interface audit

Owner: Yukang Zeng <ykzeng2019@gmail.com>. Release efdb643; source f70a87a; launch evidence d7b83b6. This05:00UTC checkpoint inspected the existing job only; no new download, model load or inference.

## Acquisition and cleanup

**COMPLETE**, worker returncode0; owned release confirmed. Supervisor52961 and worker52969 are absent at actual OS inspection. Acquisition/audit completed **2026-09-27 04:58:37.106752UTC**; supervisor cleanup receipt04:58:37.596009UTC, before deadline05:11:03.944983UTC.

Exact artifact: mradermacher/Klear-AgentForge-8B-GGUF revision0626423882f502d6fe113bd0ddc61970b19d942b, Klear-AgentForge-8B.Q4_K_M.gguf:
- Size **5,027,783,808bytes**, matched.
- SHA256 **9c0909b89b518283ded8ca415694743bd922e8844356db4f26957e37047142ae**, matched during streamed acquisition.
- Download450.018seconds; no reuse, retry or alternative file.
- Total received payload **5,039,221,984bytes**, including **11,438,176bytes metadata**; below6GiB/30MiB caps. Counts describe response payload, not packet/header overhead.
- Stream was cumulatively paced to20MiB/sec; observed whole-file average approximately10.655MiB/sec. No independent instantaneous bandwidth-peak measurement is claimed.
- Verified partial renamed in place; no remaining partial or duplicate full copy. Final asset remains outside Git at work/req028/assets/Klear-AgentForge-8B.Q4_K_M.gguf.

Across427 resource samples: pressure always1(normal), free74–77%, swap constant233.31MiB, maximum sampled worker RSS64,471,040bytes, minimum disk free17,190,391,808bytes, maximum measured new disk5,045,568,015bytes, no foreign inference or abort. Samples do not prove continuous extrema. Single CPU acquisition/hash/parser worker; no tensors loaded. Seven preflight tests passed.

## Pinned metadata comparison

Canonical metadata is pinned to Kwai-Klear/Klear-AgentForge-8B revisionfa3d41e92e9ce7a5b4a52a3e7439aa00521f40c9. Original bytes and hashes are archived; no main substitution or metadata editing.

| Field | Community GGUF | Pinned canonical | Finding |
|---|---|---|---|
| Architecture | qwen3 | qwen3 | exact label |
| Layers |36|36|match|
| Hidden width |4096|4096|match|
| Attention / KV heads |32 /8|32 /8|match|
| Head dimension |128 (derived)|128 (config)|match|
| Declared context |65536|65536|match; not demonstrated capacity|
| Vocabulary capacity |151936|151936 (config)|match in capacity|
| Base vocabulary |151643 token/ID entries|151643|all strings and IDs match|
| Added tokens |26 entries at canonical IDs|26|all match|
| Remaining GGUF slots |267 [PAD...] slots, token type5|not entries in tokenizer.json|representation/padding difference|
| BPE merges |151387 space-joined strings|151387 pairs|all match after joining each canonical pair with one space|
| BOS / EOS / PAD IDs |151643 /151645 /151643|151643 /151645 /151643|match|
| Chat template |SHA f858b0b34b6c89118490c6c087cbbc5df911f56994cc8cb61ee7a619903abcd8|same SHA|exact bytes match|

GGUF tokenizer metadata labels gpt2/qwen2 describe tokenizer representation and are distinct from model architectureqwen3. add_bos_token=false is preserved. No end-to-end tokenizer or model-output equivalence was tested.

Tensor inventory: **399 tensors**, comprising217 GGML type12(Q4_K),37 type14(Q6_K),145 type0(F32); general.file_type15 and quantization_version2 are recorded. Full names/dimensions/types/offsets are archived without tensor loading. This mixed inventory is consistent with the published Q4_K_M label; it does not prove conversion provenance.

Publisher card and GGUF declare Apache-2.0 and canonical base name. Publisher card hash matches the lead receipt75e9646b251b9d0cf7b1ceb95fcfcca32b1ef0a00e2fdc71c2c730ea9b480c46. Canonical README at the pinned revision is31bytes; separate LICENSE returned404 and is recorded missing, not substituted. All other requested canonical files were retrieved.

## Updated single-model memory estimate (not measured Klear allocation)

Actual artifact bytes: **4.682489GiB**.
Nominal32k q8_0 K/V from actual36layers,8KVheads,head_dim128:
36 *2 *32768 *8 *128 *34/32 = **2,566,914,048bytes =2448MiB =2.390625GiB**.
Weight-file bytes plus nominal KV: **7,594,697,856bytes =7.073114GiB**.

This is a component estimate, not a measured resident footprint or admission guarantee. Compute buffers, runtime/Metal overhead, system reserve and any remote-VM headroom remain separate/unmeasured for Klear. Qwen compute measurements cannot certify Klear. Disk now contains the exact verified candidate plus existing assets; no simultaneous model residency is authorized.

## Verification and provenance boundary

Verified **54 stored artifact hashes** and the frozen source snapshot at this checkpoint. Added-token and normalized-merge comparisons were performed on already acquired local metadata without further network acquisition. Full metadata, tensor inventory, canonical files, hashes, logs, watchdog samples and exit receipt are published; weights are not.

**Exact canonical source revision used for conversion, converter revision/command, and weight equivalence remain unverified.** Matching metadata and exact community bytes establish artifact reproducibility and metadata compatibility only. No canonical reported score transfers; no benchmark adoption, inference feasibility or task competence is established.

No Klear inference, Qwen repetition, further asset, transport, VM, benchmark, CONFIRM or peer/cache/Lean changes. Product goal remains **blocked** separately from this completed acquisition/audit. Readiness **55%, change0, range45–65%**. Lead reviews this receipt before any stronger-model mechanics or competence release.
