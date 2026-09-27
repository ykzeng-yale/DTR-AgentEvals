# REQ-028B3 terminal: serving completed, formatting0/3

Owner: Yukang Zeng <ykzeng2019@gmail.com>. Release5fd335d; source07b1580; launch evidencefd5b8c1. This05:45UTC checkpoint inspected the existing final cache candidate only. No new launch, renewal, inference or cache search.

## Outcome

**Infrastructure COMPLETE:3 attempted,3 terminal HTTP200,0 infrastructure failures,0 unattempted,0 retries. Formatting:0/3 compliant.** All prompt usage matched frozen counts; all cache-hit counts0. Native exact raw/served hash-singleLF binding and q4 allocation checks passed before generation.

Driver61372, model61917 and watchdog61920 are all **absent** at actual OS inspection. Owned lifecycle released=true, model returncode0. Terminal timestamp **2026-09-27 05:40:07.756079UTC**.

| Call | Input/output tokens | Wall sec | Prefill ms | Decode ms | Finish reason | Exact format |
|---|---:|---:|---:|---:|---|---|
|1 literal|33 /115|5.952914|221.276|5723.875|stop|failed|
|2 fence|49 /128|6.675540|330.450|6329.163|length|failed|
|3 original8k|8192 /128|57.111051|49370.510|7710.679|length|failed|

Every response's content contains literal **<think>** text. Call1 includes the requested DTR_READY only after additional text. Calls2/3 exhaust the128-token output cap while still in that text; no completed requested fence or exact literal response appears. Separate reasoning_content and reasoning fields are null. These raw contents are preserved without stripping, postprocessing or score repair. No generated text was executed.

Runner-reported prefill rates149.135/148.283/165.929tokens/sec; decode rates19.917/20.066/16.471tokens/sec. Rates retain runner conventions. A terminal length response counts as serving completion, not successful task/format completion.

## Timelines and bindings

Static setup ran once05:36:50.768851–05:36:55.782177UTC (5.013sec), under300-second cap. One admission window began05:36:55.783062UTC with unchanged deadline05:51:55.783062UTC. Four observations; final passing check05:38:55.979003UTC had free75%, normal pressure1, swap233.31MiB, no foreign inference.

Model phase began **05:38:55.979138UTC**, deadline **05:48:55.979138UTC**, elapsed through final status71.777sec. Healthy load1.074454sec. All three actual native-template prompts/tokenIDs/counts/hashes froze **05:38:57.119487UTC**, before first generation05:38:57.123311UTC. Counts33,49,8192;8k window/headroom and subsequent usage checks passed. status.json.started denotes admission, not model execution origin.

## Allocations and resource evidence

Actual **q4_0K/V648MiB each, total1296MiB KV**, matching the nominal component estimate;1152MiB less than observed q8 KV, not proof of equal system saving. Metal compute148.83MiB; CPU compute3.08MiB. Metal mapped model4789.19MiB and CPU mapped model333.84MiB are mapped views, not additive independent residency.

Across68 watchdog samples: pressure always1, free30–75%, swap constant233.31MiB, maximum sampled owned RSS1,456,177,152bytes, no foreign inference or abort. No abort receipt. Samples are not continuous extrema. After cleanup: free73%, normal pressure, no foreign inference.

## Coordinated stop evidence

Stop journal identifies driver61372, reason finally cleanup, durable claim at05:40:06.891122UTC; **one TERM** at05:40:06.897807UTC. No KILL, second TERM or competing stop request. Owned absence confirmed05:40:07.013911UTC; parent reaped model with returncode0 and reconfirmed at05:40:07.742138UTC. The raw log contains neither the prior second-interrupt message nor the prior GGML assertion.

This actual normal cleanup was successful. Race/dead-owner/pressure-abort/stale-PID cases were executed on inert children before launch, with8 archived receipts and58 total passing tests. They do not establish graceful Metal behavior under every abort. Prior B2R pressure/secondary teardown failure remains unchanged.

## Verification and scientific boundary

Verified **39 mechanics artifact hashes**, both launcher/run source snapshots, all5 archived source-trace hashes, all three rendered/token-ID/count bindings and pre-generation freeze ordering, and all raw response contents/usage against receipts. Raw outputs (including inline thinking text), request/binding manifests, pressure samples, allocations, stop journal and lifecycle are published.

This establishes bounded three-request serving for this exact community Klear q4-cache configuration under observed host conditions. It does **not** establish command-interface compatibility under the released128-token/native-template contract: exact formatting failed0/3, with2 length truncations. No task competence, routing benefit, output-quality equivalence or causal cache effect follows. Community canonical weight/converter derivation remains unresolved; no canonical scores transfer.

This was the **last released cache candidate**; no further configuration search or repeat was started. Lead must choose any next host/interface/competence step. No new weights, transport/VM, benchmark, CONFIRM or peer/cache/Lean changes. Product goal remains **blocked** separately from this completed run. Readiness **55%, change0, range45–65%**.
