# REQ-028C3R — cleanup correction and concrete fixture integration

Setup-only result: final **44/44 tests pass** (17.395 seconds unittest; 17.473 seconds wrapper). Real-model startup remains explicitly locked. No weights were loaded, model assets downloaded, generated commands executed, existing ports changed, or benchmark/container/peer work performed. Readiness remains **55%, change 0 points, range 45–65%**; the product goal remains blocked pending valid empirical comparison and the remaining lead-owned deliverables.

## Root cause and correction

Before editing, the remote worker independently reproduced the lead's exact failure: after one successful fake request, an OSError writing `/failure.json` escaped `fail()` before owned cleanup. Inert PID 90797 was alive before fixture teardown and absent after explicit teardown. This observation is recorded separately in `reproduction.json`; it was a short interactive reproduction, not one of the archived timed suites.

The investigation skill guided a root-cause-first correction. `fail()` now reaches owned cleanup in `finally`; cancellation failures cannot prevent stop. Primary operation exceptions survive failed cancellation and failed audit writes. Audit errors, cancellation errors, cleanup errors, and successful cleanup outcomes are separately exposed in memory, with failed audit writes marked `durable: false`. Owned absence is established before attempting a cleanup receipt. Audit failure fails closed against further requests. Phase and total-wall audit failures also reach cleanup. No claim is made that a receipt exists when its write failed.

Seven added adapter regression cases inspect owned absence **before generic teardown**: failure-record outage; cancellation plus total audit outage; cleanup-success/receipt-write failure; primary dispatch plus phase-write failure; total-wall write failure; primary poll plus cancellation/audit failure; partial provisional load failure. All 25 prior C3 tests remain included, for 32 adapter tests total. Repeated cleanup retains the shared B3 identity-key, lock, durable TERM-claim protocol. The new bounded arbiter uses the same journal format, and journal failure falls back only to identity-checked KILL, never an unjournaled repeated TERM.

## Concrete integration exercised

Twelve integration tests use only explicitly allowlisted inert executables, temporary local bare Git repositories, and owned ephemeral `127.0.0.1` fixed-JSON servers with a 60-second maximum lifetime.

- Disposable subprocess/socket/Git operation handles enforce remaining operation deadlines and cancellation; Git subprocesses remain in the worker's owned process group. Hanging socket evidence includes a server-side request-received marker, not merely any worker error.
- Actual SIGKILL of an owned driver during idle and during a received, hanging HTTP request. A separate watchdog, with recorded driver birth identity, terminates the owned child without driver `finally` help. The inert control peer remains alive until test teardown. Immediate external observations are archived.
- Native-template hash checking, full message transfer to the fixed template/tokenization endpoints, fixed raw-response capture, and one complete Adapter → concrete HTTP → concrete local Git flow.
- Immutable object reads and publication, explicit allowed commit/path pairs, dirty-checkout rejection, and concurrent-main rejection with one publication attempt and no retry. The C3 fixture publication-path override does not weaken or modify C2's existing path guard.
- Protocol 3 response envelope and consumer bind run/sequence/request ID, request commit/path/SHA, config SHA, transcript SHA, native binding/hash, raw response/hash, and timing fields. Eight mismatches reject; no synthetic C2 flag is substituted. The consumer requires an independently supplied expected native-binding hash.
- Real startup is always rejected; exact pinned asset/source-revision checks and frozen Qwen argv construction exist but no real asset-attestation execution or model launch occurred. A provisional identity-probe failure also proves direct-child absence before teardown.

The inherited tests retain wrong initial config/release/request rejection before load, crash after one physical fake request with no redispatch, unapproved-next-call rejection, no reload, no deadline renewal, context/output binding, and independent resource-guard failures. Release pins remain explicit caller inputs, including each subsequent release; main contents cannot substitute for authorization.

## Evidence and resource accounting

All three immutable run trees are packaged as data-only `.tar.gz` archives, including their temporary Git internals, source snapshots, logs, and hash manifests. Packaging avoids treating nested fixture repositories as source submodules. No original run tree was removed or rewritten.

| Run | Outcome | Wrapper wall | Peak sampled RSS | Verified files |
| --- | --- | ---: | ---: | ---: |
| `c3r_setup_20260927` | 43 tests; 2 failures, 3 errors | 21.011 s | 105,431,040 B | 965 |
| `c3r_setup_second_20260927` | 44 pass | 16.883 s | 97,599,488 B | 1,014 |
| `c3r_setup_final_20260927` | 44 pass | 17.473 s | 100,335,616 B | 1,014 |

Timed suites total **55.367 seconds**, plus the short initial interactive reproduction, safely below 300 seconds. Failed-run causes were an HTTP helper/module name collision, the inherited C2-only publication-path predicate, and missing-parent classification; the in-flight marker failure followed from the HTTP bug. The final run strengthens socket-received and exact Git rejection-reason assertions. All failed evidence is retained.

The package verifier checked 2,993 archived file hashes, rechecked their bytes inside the archives, verified current adapter/integration sources match the final source snapshot, validated 32 final owned-absence receipts, and rejected any external-observer teardown errors. A final process listing found no remaining C3R fixture server, watchdog, HTTP/Git worker, or driver. `verification.json` contains per-run metrics, archive hashes, and immediate observations. New run trees plus archives totaled 2,444,249 logical bytes before the small report/receipt additions, below 100 MiB.

Contract SHA remains `218cf178c46e96a88bf1757f565ad64f57be0efea05adfd2ba5f13fb9353b898`. Exact source/dependency hashes are in each final manifest; the final archive SHA is `e74240c59461bc60648e4eb67284250114c4671a4310f2a905ae2ccdd0631ce0`.

## Qualification limits / handoff

This is not model, benchmark, writable-sandbox, or production qualification. Template rendering/token IDs, admission/resource samples, and setup attestation are deliberately fake; the actual native-template text/hash is checked, but the fixture is not a tokenizer. Real asset hashing is implemented but unexecuted. Production startup remains unconditionally locked pending a future exact release.

Executed concrete Git transport is temporary-local-only and the integrated publication test is one request; sustained live Git relay, multi-call concrete publication advancement, and real server cancellation are not qualified. Actual driver-death tests kill after ownership/watchdog setup; the pre-watchdog startup crash window relies on the inert fixture's 60-second alarm and is not production-qualified. The inherited no-redispatch test is an injected adapter crash, not a physical model crash.

The fixture implementation bounds subprocess/socket/Git waits and identity probes, but ordinary local filesystem calls/fsync are not hard real-time preemptible. Cleanup has a separate finite safety budget rather than skipping cleanup at an expired work deadline. RSS is sampled, not address-space enforced; final sampling retains observed descendants by PID/birth time after reparenting, but may miss very short-lived processes. One compute worker and single-thread library settings were used; macOS CPU affinity was not enforced. The final watchdog consumes fixed fixture resource samples, not production telemetry. These limitations require lead review before any broader release.

No real-model or recurring transport worker is left running. Stop here for lead review; the prospective 24-call/1,800-second contract is **not** execution permission.
