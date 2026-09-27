# REQ-028B2R terminal: pressure abort during loaded prompt setup

Owner: Yukang Zeng <ykzeng2019@gmail.com>. Release bf23582; source80bbd6b; launch evidence28578de. This05:30UTC checkpoint inspected only the existing run. No extra inference, job or renewal.

## Actual status and cleanup

**FAILED before generation:0 attempted,0 completed,0 failed generation requests,3 unattempted.** Driver58789, model59336 and watchdog59338 are all absent at actual OS inspection. Lifecycle records released=true, model returncode-6. Terminal timestamp **2026-09-27 05:22:27.974757UTC**.

The driver recorded URLError(ConnectionRefusedError(61,'Connection refused')) during loaded binding setup. The independent watchdog receipt establishes **adverse_pressure**, owned_stop=true. This was a resource abort, not another template mismatch or model-output failure.

Single admission window had4reads. Final pre-Popen read05:22:26.318936UTC: free75%, pressure1, swap233.31MiB, no foreign inference. Execution began05:22:26.319107UTC, deadline05:32:26.319107UTC; ended after1.656sec. Healthy load1.071776sec. Original admission deadline05:35:26.182055UTC was not renewed.

## Template repair and incomplete prompt binding

The repaired source check **passed** at05:22:27.396904UTC:
- Raw3990bytes, SHA f858b0b34b6c89118490c6c087cbbc5df911f56994cc8cb61ee7a619903abcd8.
- Served3989bytes, SHA f2850fd92c68d5375344b9e09b551e3bbc3124b56f8ca58e468b2c91179bdb51.
- Exact raw==served+oneLF, no CR, both pinned hashes verified.
- Both original representations and the recognized lexer transformation are archived, without modifying template/model/check after launch.

Two setup-only prompt artifacts exist: literal prompt33tokens and fenced-command prompt49tokens. The third long-input binding did not complete. **No combined prompt_manifest.json exists and no generation was dispatched.** These tokenizer receipts are not model responses or compliance observations.

Effective-cache receipt before generation confirms **q8_0K/V**,1224MiB each, total2448MiB. Raw load logs report Metal compute148.83MiB and CPU compute3.08MiB. These are load/setup observations, not sustained serving qualification.

## Pressure and teardown evidence

Two watchdog samples:
1.05:22:26.382865UTC: free75%, pressure1, swap233.31MiB, owned RSS13,828,096bytes.
2.**05:22:27.423183UTC: free20%, pressure2**, swap233.31MiB, owned RSS2,639,052,800bytes, no foreign inference, disk17,080,115,200bytes; reason adverse_pressure.

No swap growth or foreign inference was recorded. Free20% was not below the20% floor; pressurelevel2 independently triggered the unchanged guard. After cleanup: pressure1, free67%, swap233.31MiB. Sparse samples are not continuous peak measurements.

The teardown log additionally contains **Received second interrupt, terminating immediately** and **GGML_ASSERT([rsets->data count] == 0)** at pinned ggml/src/ggml-metal/ggml-metal-device.m:1025, with a Metal deallocation backtrace. It is preserved as a secondary cleanup-path failure, consistent with final-6. Both watchdog and driver's finally cleanup can signal the owned process; exact signal interleaving is not separately instrumented. Do not attribute this assertion as the initial cause or call cleanup graceful. OS absence and released=true do confirm the owned process is gone. No cleanup change or rerun was made.

## Verification and interpretation

Verified **25 mechanics artifact hashes**, both launcher/run source snapshots, all5 archived pinned source-trace hashes, and the exact raw/served byte relationship.48 preflight tests had passed. Published raw logs, props, partial prompt artifacts, native/effective-cache receipts, pressure/abort records, manifests, deadlines and lifecycle. No generated response, usage, reasoning or timing receipt exists.

B2R validates the narrow native-source representation check and records an early loaded-setup pressure limit under this host state. It does not establish Klear request serving, formatting accuracy, coding competence, universal infeasibility or a routing-target null. Prior B2 remains an independent template-check failure. Community canonical weight/converter derivation remains unresolved; no canonical score transfers.

No extra call, retry/restart/fallback, renewal, new weights, peer/cache/Lean change, transport/VM, benchmark or CONFIRM. Product goal remains **blocked** separately from the terminated run. Readiness **55%, change0, range45–65%**. Lead retains the next experiment decision.
