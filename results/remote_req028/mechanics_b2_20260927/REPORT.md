# REQ-028B2 terminal: template representation mismatch before generation

Owner: Yukang Zeng <ykzeng2019@gmail.com>. Release0b1ae39; source89351fd; launch evidence8c24e15. This05:15UTC checkpoint inspected the existing run only; no new job, renewal, inference or patch.

## Actual result and cleanup

**FAILED before generation:0 attempted,0 completed,0 failed generation requests,3 unattempted.** Exact exception: AssertionError('native loaded template mismatch'). One server loaded and returned healthy, then the native-template byte assertion stopped before prompt rendering/tokenization and before any generation.

Driver57073, model57180 and watchdog57182 are all **absent** at actual OS inspection. Owned lifecycle released=true, model returncode0. Terminal time **2026-09-27 05:06:49.918160UTC**. Healthy-load time1.086552sec; no restart/retry/fallback.

Static setup completed once in5.335sec. Admission passed after3 readings (two scheduled passes >=60sec apart and final check); last final reading05:06:47.745379UTC had free76%, normal pressure1, swap233.31MiB, no foreign inference. Model phase began05:06:47.745543UTC, fixed deadline05:16:47.745543UTC; it ended after approximately2.173sec. Original admission deadline05:20:47.616724UTC was unchanged.

## Exact mismatch evidence

| Representation | Length | SHA256 |
|---|---:|---|
| Verified B1/native GGUF template |3990 bytes|f858b0b34b6c89118490c6c087cbbc5df911f56994cc8cb61ee7a619903abcd8|
| Loaded server /props chat_template |3989 bytes|f2850fd92c68d5375344b9e09b551e3bbc3124b56f8ca58e468b2c91179bdb51|

Read-only byte comparison confirms **GGUF template == props template + one final LF byte**. No other difference was found. This is a representation-level discrepancy, not evidence that the model weights or underlying template body changed. Whether removing that final newline changes rendered input was **not tested**: the released fail-closed check stopped first. No template normalization, edited weight, alternative prompt, relaxed check or new inference was applied.

Both original strings are preserved in chat_template.jinja and server_0.props.json. No completed prompt_manifest or generated response/usage/reasoning record exists. All three intended request bodies remain in the frozen preload manifest. Do not score these calls as noncompliant responses.

## Observed load/resource evidence

Raw allocation logs report **2448.00MiB q8 KV**, K(q8_0)1224MiB and V(q8_0)1224MiB; Metal compute148.83MiB and CPU compute3.08MiB. Effective allocation lines exist in raw logs, but the program stopped before writing its separate effective_cache.json receipt.

Two watchdog samples: free76% then21%, pressure1(normal), swap unchanged233.31MiB; maximum sampled owned RSS2,634,432,512bytes. No watchdog abort was recorded. After cleanup: free69%, pressure1, swap233.31MiB, no foreign inference. Sampled values are not continuous peaks or a sustained-load qualification.

This inspection verified **18 mechanics artifact hashes** and both launcher/run source snapshots.43 preflight tests had passed. Raw load logs, /props response, metadata/template, manifests, admission/watchdog samples, failure, deadlines and lifecycle receipts are retained. Exact candidate bytes/metadata were verified before load; canonical source-weight/converter derivation remains unresolved and no canonical score transfers.

## Interpretation and hold

B2 supplies a successful guarded load followed by a strict template-binding stop—not successful Klear request serving, a throughput result, coding competence, routing benefit or a memory-feasibility failure. Lead must decide whether and how to qualify the observed trailing-LF representation before any new attempt. Current release was not extended.

No additional inference,24k request, download, peer/cache/Lean changes, transport, VM, benchmark, primary-target modification or CONFIRM. Product goal remains **blocked** independently of the terminated run. Readiness **55%, change0, range45–65%**.
