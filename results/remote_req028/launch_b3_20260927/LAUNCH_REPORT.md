# REQ-028B3 stage1 accepted; stage2 admission launched

Owner: Yukang Zeng <ykzeng2019@gmail.com>. Exact release5fd335d and both parent plans read fully. Source **07b1580** published in separate checked operations before any B3 supervisor/driver. Launcher independently verified remote main and source bytes.

## Stage1 executed acceptance

**58 tests passed**, including eight real owned inert-process cleanup cases, all reaped:
- simultaneous driver/watchdog stops: exactly one TERM sequence, bounded KILL for TERM-ignoring fixture;
- normal stop and pressure-abort stop;
- parent death and deadline;
- stop owner exits while holding arbitration after durable TERM claim: successor sends KILL, never another TERM;
- stale/reused identity refusal: live decoy not signalled; separately owned fixture then cleaned;
- first-call infrastructure abort: later calls skipped and owned process released.

Eight detailed receipts with actors/reasons/signal times/returncodes/exited flags are archived under launch_b3_20260927/cleanup_test_receipts. Normal/pressure/parent/deadline/first-abort/stale-fixture cleanup returncodes0; TERM-ignoring race and dead-owner fallback fixtures returncodes-9, as expected. Prior48 tests remain passing. CLI fixture changes only both cache types versus B2R; resource threshold function and sampling remain the original guard implementation.

New b3_stop.py uses an inter-process flock plus durable exact-identity-keyed stop journal. TERM claim is persisted before signalling. Only lock owner signals; a dead owner's released lock permits successor takeover without repeating TERM. Grace2seconds, KILL wait2seconds, arbitration lock wait<=8seconds. Every signal rechecks owned identity. Driver and watchdog both confirm owned absence; driver records actual child returncode after reaping. Stop requests/initiating actor/reason/signals are preserved. These tests establish process mechanics, not graceful Metal teardown.

## Stage2 actual state

Driver/supervisor **PID61372**, birth Sun Sep27 01:36:50 2026, Python experiments/remote_req028/mechanics_b3.py. Old58789/59336/59338 and prior owned model/watchdog records were checked absent.

Once-only static setup **05:36:50.768851–05:36:55.782177UTC**,5.013sec, before300second deadline05:41:50.768851UTC. Exact model/binary/source/template pins and source trace reverified; pinned help allows q4_0 for bothK/V.

Current stage **WAITING_FOR_ADMISSION**, single window **05:36:55.783062–05:51:55.783062UTC**, max31reads. Observation1: free73%, normal pressure1, swap233.31MiB, no foreign inference, disk17,070,092,288bytes. No model or inference started at this checkpoint. Execution deadline will be600seconds from immediately before Popen, load/request180seconds.

Only released candidate change is both K/V q4_0 plus coordinated cleanup wiring/IDs. Same exact three Klear requests,32k/batches/decoder/native hash-singleLF binding and all guards. Actual q4 allocations must be logged before generation; nominal1296MiB is not a system-saving guarantee. All three rendered/token bindings freeze before generation. No retry,restart,renewal,fallback,24k call or further cache search after this candidate.

Prior B2R pressure abort and secondary teardown assertion remain unchanged. Community exact canonical derivation remains unresolved. No new weights, transport/VM, benchmark, CONFIRM, peer/cache/Lean change. Product goal remains **blocked**, separately from this authorized active run. Readiness **55%, change0, range45–65%**.
