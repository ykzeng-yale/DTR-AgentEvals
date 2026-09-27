# REQ-028B1 acquisition launch receipt

Owner: Yukang Zeng <ykzeng2019@gmail.com>. Exact release **efdb643** read fully. Source **f70a87a** successfully published before launcher invocation; launcher independently verified remote main and all source bytes.

Actual supervisor **PID52961**, owned acquisition worker **PID52969**. Started **2026-09-27 04:51:03UTC**; fixed deadline **05:11:03.944983UTC**. Current stage **DOWNLOADING**, with16,515,072bytes received at04:51:08.564755UTC. No model loaded or inference started. Old A6R PIDs50009/50544/50546 were verified absent.

Exact asset: mradermacher/Klear-AgentForge-8B-GGUF revision0626423882f502d6fe113bd0ddc61970b19d942b, Klear-AgentForge-8B.Q4_K_M.gguf, expected5,027,783,808bytes, SHA2569c0909b89b518283ded8ca415694743bd922e8844356db4f26957e37047142ae. Pinned resolve URL only; a successful download is renamed in place after exact streamed hash/size verification. Partial files remain on failure and prevent duplicate attempts.

Seven acquisition/guard tests passed. One streamed connection <=20MiB/s, no whole-file retry. A single CPU worker performs download/hash/metadata work, with independent1-second resource sampling and2GiB RSS cap. Guards cover normal pressure/free>=20%, unchanged swap-growth bound512MiB, no foreign inference,12GiB remaining disk,5GiB new-disk cap and20-minute deadline. Initial admission conservatively reserves all5GiB planned new disk in addition to12GiB reserve. CPU time cap1200seconds. Payload limits:6GiB overall and<=30MiB metadata; no canonical weight shards.

After verified acquisition, the worker automatically parses existing-reader GGUF summary plus bounded vocabulary/tensor-header inventory without tensor loading, retrieves pinned canonical metadata atfa3d41e92e9ce7a5b4a52a3e7439aa00521f40c9, checks publisher-card hash, and writes exact architecture/tokenizer/template comparisons and nominal q8_0/32k KV estimate. Missing optional metadata files remain recorded404s, never substituted with main. No template or weight changes are permitted.

Source snapshots/tests and initial ownership records are immutable. Live progress/samples and terminal metadata will be published after the existing job finishes. Weights/partials stay outside Git in owned assets. This acquisition does not adopt the community artifact for benchmarks: exact canonical source revision, converter and weight equivalence remain **unverified**; no canonical score transfers.

No Klear inference, Qwen repeat, transport, VM, benchmark, CONFIRM, peer/cache/Lean changes or new monitor. Product goal remains **blocked**, separately from this authorized active acquisition. Readiness **55%, change0, range45–65%**.
