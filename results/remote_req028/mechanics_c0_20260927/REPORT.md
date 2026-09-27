# REQ-028C0 terminal: parser acceptance both arms; boundary gate Klear fail, Qwen pass

Owner: Yukang Zeng <ykzeng2019@gmail.com>. Release6397da7; source2b5e4e18017bc1ff8b8ac6d497550634005c5330; launch049c57c. One bounded OS inspection at06:30:56.996194UTC confirmed terminal records and all five owned PIDs absent. No additional launch, retry, renewed window or inference occurred at this checkpoint.

## Exact counts and predeclared endpoints

Two serial model loads, two attempted logical requests, two terminal HTTP200 responses, zero infrastructure failures, zero unattempted arms, zero retries. No generated commands executed, no benchmark environment or trajectory run, no correctness assessment.

| Endpoint | Klear community / q4_0 KV | Qwen3-4B / q8_0 KV |
|---|---|---|
| HTTP / finish reason | 200 / stop | 200 / stop |
| Input / output tokens |1530 /54|1530 /199|
| Output cap reached |No (1536 cap)|No (1536 cap)|
| Complete matching fences |1|1|
| Pinned parser accepted |Yes|Yes|
| Nonempty extracted command |Yes|Yes|
| Boundary |Inside unclosed thinking; after_unclosed_reasoning|Outside thinking|
| Unclosed think spans |1|0|
| **Combined interface gate** |**FAIL**|**PASS**|
| Response wall seconds |10.668950|10.618794|
| Prompt time / decode time ms |7928.190 /2728.381|4687.335 /5919.840|
| Prompt / decode tokens/sec |192.982257 /19.425439|326.411490 /33.446850|
| Load/health seconds |1.072926|1.079957|

Klear raw content begins with an opening think tag and never closes it. Its single fence at character offsets210–242 extracts ls -la. Parser acceptance does not satisfy the separately frozen thinking-boundary gate. Qwen has no inline thinking span; its fence at747–857 is outside thinking. Its extracted command text is preserved in the raw response and receipt, but never run or assessed for correctness. Both separate reasoning fields are null; cached tokens and runner cache_n are zero.

These findings concern one already-exposed DEVELOPMENT first prompt only. They do not establish task competence, model success rates, a causal weight-only comparison, routing benefit or canonical Klear score transfer. Candidate cache configurations differ. B3/B4 synthetic failures remain unchanged; no rescoring, stripping, budget increase or synthetic retry.

## Frozen input and verification

Frozen document SHA1d99595667cee6fbab3af480eba0ca7ed4c9976abc5530b396c2cf78903d5d8a; REQ011 trajectory sourceSHA478b321f86a9591ff9488e69a90614ba7159ba29eb1176701d155353da7aba06; first-two-role/content message SHA f8178479369ca97aed5c7f836b04da2c679225ddf10807033799c3a2f441b106. Both actual requests exactly match the released request constructor with fresh alias, identical frozen messages and1536 output cap. No later assistant/tool messages, solution, tests or CONFIRM data forwarded.

Verified all **189 program archive hashes**, including arm/source/trace artifacts. Independently replayed raw content/usage against receipts, pinned parser plus independent regex and boundary endpoints, exact request/message identity, rendered/token hashes,1530 usage binding for each arm and prompt-freeze-before-generation ordering. Equal input counts were observed, not assumed. Native template checks retained exact Klear raw/served one-LF relation and Qwen byte equality. Published launcher preflight75 tests passed; launch archive retains source and eight inert cleanup receipts.

## Fixed windows and serial cleanup

Program started06:24:56.232365UTC; deadline07:24:56.232365UTC. Finished06:28:30.920748UTC (214.688383seconds). No cap was renewed.

Klear:
- Setup06:24:56.232591–06:25:01.258691UTC;300-second cap.
- Single admission06:25:01.259651–06:40:01.259651UTC;4 observations, final normal/free75 immediately before launch.
- Model phase06:27:01.443856UTC; fixed deadline06:37:01.443856UTC.
- Call06:27:02.584410–06:27:13.253360UTC. Arm COMPLETE06:27:14.172981UTC.
- Model68989/watchdog68992. Exactly one driver TERM, no KILL; owned absence confirmed; model returncode0; parent confirmation06:27:14.168535UTC.

Qwen:
- Setup began06:27:14.209125UTC, after Klear completion and explicit model/watchdog absence check; completed06:27:17.983982UTC admission start.
- Single admission06:27:17.983982–06:42:17.983982UTC;3 observations, final normal/free75 before launch.
- Model phase06:28:18.094001UTC; fixed deadline06:38:18.094001UTC.
- Call06:28:19.222263–06:28:29.841057UTC. Arm COMPLETE06:28:30.869560UTC.
- Model69164/watchdog69167. Exactly one driver TERM, no KILL; owned absence confirmed; model returncode0; parent confirmation06:28:30.856433UTC.

The single checkpoint OS inspection confirmed supervisor68841, Klear68989/68992 and Qwen69164/69167 all absent. Both arm COMPLETE statuses followed watchdog-exit0 checks; program COMPLETE followed explicit model/watchdog absence and stop-journal checks for both arms. No simultaneous residency.

Each arm has12 watchdog samples, all normal pressure1, swap constant233.31MiB, no foreign inference or abort reason. Klear free35–75%, maximum sampled owned RSS1,537,802,240bytes; Qwen free42–75%, maximum2,730,573,824bytes. Effective KV allocations1296MiB Klear q4_0 and2448MiB Qwen q8_0. These are sampled/component measurements, not total physical memory or general throughput guarantees.

## Hold and handoff

C0 bounded execution is complete; lead owns acceptance and any next sandbox/transport competence decision. No further prompt tuning, new weights, transport/VM, benchmark, CONFIRM, peer or Lean changes were made. Broader product goal remains blocked; readiness55%,change0points,range45–65%. Fixed-target competence/valid inference, synthesis, independent reproducibility and approved package remain.
