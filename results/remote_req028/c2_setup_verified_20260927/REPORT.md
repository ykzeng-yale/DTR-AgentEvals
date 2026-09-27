# REQ-028C2 setup complete; frozen nonce awaiting lead review

Release90dc752 read fully. Owner/committer Yukang Zeng <ykzeng2019@gmail.com>. This publishes source, executed synthetic fixtures and a request only. No live relay worker, nonce dispatch, inference, model load, container, listener, tunnel, downloads, credentials/firewall/peer changes or generated-payload execution.

## Authoritative request

Use **results/remote_req028/c2_setup_verified_20260927/request.json** from this publication commit. The later response must bind that exact commit, not a moving main ref.

- protocol1; run req028-c2-20260927; sequence1; request req028-c2-20260927-1; parentnull; synthetic_only=true.
- Exact UTF8 body: DTR_C2_NONCE_20260927.
- Body SHA256: cd04386f1d9f183fcc59a7b6634c81ed4c163c4e7ba80f6e61bf155cf9d412d9.
- Config identifier fixture-only-v1; SHA25644cfdb92a1673b41a48fbc0b59c9c55d9a3e2ababbe42518120c70b5dd12afb9.
- Expiry **2026-09-27T08:30:00Z**. No renewal if it expires.
- Exact request-envelope SHA256: **2c546d276ad0c9d50b66e6066472991d3c0fb63bcbd078da6c1dde1c73750f83**.

The earlier c2_setup_20260927 directory preserves the first passing offline test snapshot and its byte-identical nonce candidate. It is not a second request/dispatch or a separate exchange. The verified path above is the sole authoritative exchange path. Lead should not process arbitrary repository requests.

## Implementation and tests

c2_relay.py provides strict, bounded UTF8 JSON envelopes; duplicate/unknown keys rejected; IDs/path components/hash/types/sequence/parent/config/expiry validated;1MiB envelope cap. Injected read/exclusive-write/clock callbacks allow deterministic failure tests. FileStore uses exclusive creation, file fsync and directory fsync. A durable sequence claim precedes dispatch. An existing claim without a sealed response is explicitly indeterminate, including a crash before dispatch, and cannot invoke the callback again. Completed identical reads are idempotent; conflicting duplicate requests/responses and modified response files fail closed. A prior sealed ok response and exact parent hash/config are required before the next serial sequence.

Queue/network accounting is saved after claim, dispatch start is saved before callback, and completed timings or indeterminate observation are saved after it. The optional Git transport records fetch/object-read/main-check/publication phase timing and success/failure through an injected recorder (or its in-memory event list). A future operational caller must durably persist these events, including failed operations, and include all network, queue and dispatch overhead in its deadline.

c2_git.py reads exact objects from fetched-main ancestry and publishes owned c2 paths only through a private index and ordinary non-force push. It rejects dirty worktrees, non-latest checkout, changed immutable records, stale expected main and concurrent main advancement. It never merges conflicts, updates the working checkout, force-pushes or retries publication. Failed publication leaves a local commit/object available for inspection, not permission to repeat dispatch. No GitHub branch/service was created; Git transport fixtures used temporary local bare/working repositories.

Command: **python3 experiments/remote_req028/c2_setup.py**. It runs the actual unittest module in a bounded single compute worker, archives source/tests, and writes the fixed request, never dispatches it. Existing immutable output prevents accidental rerun overwrites.

Final run: **17 tests passed in1.445seconds**; wrapper1.539495seconds; sampled process-tree peak39,780,352bytes. Initial run17/17 in1.454seconds; wrapper1.526466seconds, peak45,907,968bytes. Cumulative measured unittest execution2.899seconds, wrappers3.065960seconds, well below300seconds; new artifacts approximately63KiB before this report, below50MiB. Single-thread compute worker plus lightweight monitoring and short sequential local Git subprocesses; no workload parallelism. Resource guard samples tree RSS against2GiB and enforces a290-second wall stop with owned process-group cleanup; CPU rlimit290seconds applies to the worker. Monitored RSS is not a hard address-space guarantee.

Executed cases include expiry before claim, deadline after claim/during dispatch, crash after claim/before callback and after callback entry, response-write failure, idempotent/conflicting duplicates, modified records, wrong types/unknown or duplicate fields/oversize/path traversal, request/response hash/config/sequence/parent/commit mismatch, serial progression, competing claim reentry, phase accounting, dirty checkout, publication failure, concurrent main advancement before publication and a post-check push race. All callbacks use synthetic strings. No text is interpreted as shell.

Final source SHA256:
- c2_relay.py:a82a582bde87b3a9876faa81d49b75d57a9db3860aad0682efc14b7773a53ea1
- c2_git.py:28e389f2d20f476dbf329809cabf710f15d6dd1aaeb2ec59cf6a69c08b8377e9
- c2_tests.py:aca5eadcb7fbbc2343f147b031c75be46fc7a64ad03eee3340380eb92904f875
- c2_setup.py:bee188b909bdf888fbc864966a3c3d680764f080f3f571b65ec9a021067c0192

## Limits and stop point

This is **not a production exactly-once service**. At-most-one callback invocation relies on the same trusted durable journal and correctly implemented exclusive-write callbacks; deleting/rolling back a journal or adversarially rewriting both data and seals is outside that guarantee. Partial crash writes fail closed. It does not make callback side effects transactional or recover an unknown result. Deadlines are checked before/after the injected synchronous callback; a future real adapter must additionally enforce cancellation/timeouts inside its dispatch mechanism. No such model adapter is supplied or released. Timing receipts are descriptive, not transferred local-inference latency claims.

Git publication uses existing authenticated access; filesystem/Git contents still require exact approved request/commit/path selection. The implementation exposes helpers, not an autonomous request scanner or authorization mechanism. A future caller must authenticate and allowlist the reviewed run/request and preserve durable audit records. No live polling loop is running.

STOP after source/request publication for lead review and later matching response. Klear's frozen C0 gate remains failed; Qwen is only a future single-model sandbox-pilot candidate. Lead's reported Docker/image availability was not reprobed or provisioned here. C0/C1 archives are untouched. Product goal remains blocked; readiness55%,change0,range45–65%. No benchmark or CONFIRM release.
