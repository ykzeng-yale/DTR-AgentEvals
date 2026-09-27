# REQ-028B2R setup/admission receipt

Owner: Yukang Zeng <ykzeng2019@gmail.com>. Exact release **bf23582** and referenced B2 plan read fully. Source **80bbd6b** successfully published through separate checked operations before launch; launcher independently checked remote main and every source byte.

Driver/supervisor **PID58789**, birth Sun Sep27 01:20:21 2026, Python experiments/remote_req028/mechanics_b2r.py. Old57073/57180/57182 and prior owned model/watchdog records were verified absent.

Static setup ran once **05:20:21.196590–05:20:26.181264UTC**,4.985seconds, under deadline05:25:21.196590UTC. Model bytes/SHA and B1 metadata/native raw template were reverified. Five exact pinned runner source files were checked against the existing archive and copied to runner_template_trace, with hashes/line ranges/snippets in template_source_trace.json. No runner rebuild or template edit.

Current stage **WAITING_FOR_ADMISSION**. Single window **05:20:26.182055–05:35:26.182055UTC**, at most31reads. First observation at05:20:26.209985UTC: free74%, normal pressure1, swap233.31MiB, no foreign inference, disk17,082,695,680bytes. No model or inference at this checkpoint. Two passing readings >=60sec apart and final check are required before one Popen. Model deadline starts only immediately before that Popen,600seconds; per-load/request180seconds.

**48 tests passed**, preserving prior43. Added tests accept only the pinned known pair and reject raw/served/internal whitespace changes, extra LF, spaces, tabs, CRLF, and jointly modified strings even if their single-LF relationship still holds. Validation requires BOTH exact SHA values, exact lengths3990/3989, no CR in raw, and raw_bytes==served_bytes+oneLF. No strip/rstrip/general whitespace normalization.

At load, both originals and recognized lexer representation will be recorded before generation. All three actual request/rendered/token-ID bindings then freeze together before any call; long input8192–8256 plus128headroom, no search. Native-source acceptance does not replace rendered-token or subsequent usage checks. Same exact THREE B2 requests, same verified community Klear bytes, q8/32k/batches/decoder/guards; no extra call, retry, restart, renewal, fallback or changed model behavior.

New immutable paths: results/remote_req028/launch_b2r_20260927 and mechanics_b2r_20260927. Prior B2 remains failed with0generation calls; this repaired validation does not retroactively change its evidence. Source-trace evidence identifies the pinned lexer representation change, not a claim of output or weight equivalence. Community canonical derivation/converter provenance remains unresolved; no canonical score transfers.

No new weights, transport/VM, benchmark, CONFIRM, peer/cache/Lean changes. Product goal remains **blocked**, separately from this authorized active job. Readiness **55%, change0, range45–65%**.
