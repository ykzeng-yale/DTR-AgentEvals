# REQ-028A6R terminal: two q8 KV long-input calls completed

Owner: Yukang Zeng <ykzeng2019@gmail.com>. Release f21f0ad; source11e85fb; launch evidence5925d54. This04:45UTC checkpoint inspected the existing run only; no new launch, renewal or inference.

## Terminal status and cleanup

**COMPLETE:2 attempted,2 terminal,0 failed,0 unattempted,0 retries.** Both responses are literal **DTR_READY**, HTTP200, finish_reason stop, with valid frozen input bindings and zero cached prompt tokens. Driver50009, model50544 and watchdog50546 are all absent at actual OS inspection. Model lifecycle records released=true and returncode0. Final status timestamp **2026-09-27 04:40:09.576016UTC**.

## Separate stage timing

Static setup once:04:34:53.517450–04:34:56.099990UTC (2.583sec), before its300-second deadline04:39:53.517450UTC. Source was successfully published and verified against remote main before launcher invocation; no new publication sequencing deviation.

Single admission window:04:34:56.100690UTC, fixed deadline04:49:56.100690UTC. Four reads: free74%,75%,75%,75%; passing scheduled observations at04:35:56.187528 and04:36:56.257575UTC were >=60seconds apart. Final pre-Popen reading04:36:56.284397UTC passed unchanged gates. No final-check reset was needed in this actual run (covered in fake-clock tests).

Execution began **04:36:56.284576UTC**, fixed deadline **04:46:56.284576UTC**; elapsed through terminal status193.291sec. Healthy model load1.073258sec. Both prompts/bindings froze at **04:36:57.456697UTC**, before first request04:36:57.460548UTC. status.json.started denotes admission start, not model execution start; execution_window.json is the authoritative model budget origin.

## Raw-response measurements

| Input tokens | Output | Output tokens | Cache hits | Wall sec | Prefill ms | Prefill tokens/sec | Decode ms | Runner decode tokens/sec |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
|8192|DTR_READY|4|0|32.698598|32488.669|252.149|197.282|15.207|
|24576|DTR_READY|4|0|158.882400|158689.893|154.868|163.411|18.359|

Both wall times are below180seconds. Rates retain the runner's reporting convention; no substituted output-count/time estimate. Generated text was not executed. No extra short calls, token search, restart, retry or fallback.

## Allocation and resource evidence

Effective cache log verified **K(q8_0)=1224MiB, V(q8_0)=1224MiB**, total **2448.00MiB**. This matches the nominal estimate and is2160MiB below the previous f16 KV allocation, not a guarantee of equal system-memory savings. Metal compute148.15MiB; CPU compute2.70MiB. Metal mapped model2375.91MiB and CPU mapped model304.28MiB are mapped views, not additive independent physical residency.

Across184 watchdog samples: pressure always1(normal), free43–75%, swap constant233.31MiB, maximum sampled owned RSS2,722,021,376bytes, no foreign inference, no abort reason. No abort record exists. Sampled maxima do not establish continuous peaks. Final recorded after-cleanup free75%, normal pressure and no foreign inference.

## Verification and interpretation

Verified **29 mechanics artifact hashes**, both launcher/run source snapshots, both exact A5-to-A6R request copies with only alias replaced, rendered/token-ID hashes and8192/24576 counts, freeze-before-generation ordering, and both raw response contents/usage against receipts.37 preflight tests passed before launch. Complete raw requests/responses, token bindings, logs, observations, manifests, deadlines and lifecycle records are preserved.

This establishes bounded serving feasibility for these two synthetic long inputs on this **q8_0 execution configuration** under observed conditions. It does not validate f16, output-quality equivalence, causal quantization effects, restart qualification, task competence or routing benefit. A5/A6R host states and orchestration differ; nonrandomized timing/resource comparisons do not isolate causality. Earlier A4/A5/A6 partial/failed records remain unchanged.

No guard weakening, peer/cache/Lean changes, new model/weights, Klear, transport, VM, benchmark or CONFIRM. Prior028B planning remains available but not execution authorization. Product goal remains **blocked** separately from this completed run, and the scientific objective is not complete. Readiness **55%, change0, range45–65%**. Lead retains scientific acceptance and next competence/transport decision.
