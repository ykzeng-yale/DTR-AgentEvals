# REQ-028C3 remote setup: fake adapter execution passed; live integration NOT qualified

Release2f8538b, full C3 specification read. Remote scope only. Owner/committer Yukang Zeng <ykzeng2019@gmail.com>. Lead's separately owned local Docker probe was not duplicated. No Qwen/Klear model load, real inference, download, container, network listener, live Git polling worker, credentials/firewall/peer change or generated command execution.

## Outcome and evidence

**25 final executed tests passed in13.757seconds**, bounded wrapper13.832699seconds, sampled process-tree peak45,137,920bytes. Verified **483 immutable final artifact hashes** and **25 cleanup receipts**, all owned inert children absent. Final evidence: c3_setup_final_20260927. Cumulative test runtime across four development runs:42.316seconds, below300seconds. Combined pre-report output files610,241bytes, below50MiB. One Python compute worker, lightweight independent watchdog/resource-monitor threads and short sequential process-inspection subprocesses; inert children only sleep. Monitored RSS is not an OS hard address-space guarantee.

The first development run failed15/24 cases because the admission event reused the event-kind argument name. No inert model child loaded in those failing paths. Its log/resource receipt is preserved under c3_setup_20260927. After correction,24/24 passed under c3_setup_r2_20260927. Queue/contract completion passed24/24 under c3_setup_verified_20260927. Final cancellation-error cleanup hardening passed25/25; no prior artifact was overwritten. Only the final source hashes below describe the current implementation.

Entry point: python3 experiments/remote_req028/c3_setup.py. It imports fake dependencies, runs tests, archives receipts/source and exits. Exclusive output creation prevents silently overwriting this run. It does not start any serving/relay service or dispatch repository requests.

## Implemented setup contract

Canonical Qwen configuration SHA256 **218cf178c46e96a88bf1757f565ad64f57be0efea05adfd2ba5f13fb9353b898**, JSON bytes use the reviewed C2 canonical encoder. contract.json includes exact model/runner/server/native-template pins, q8_0K/V,32k,batch128/ubatch32,two main/batch/HTTP threads,temperature0,seed20260927028,max1536,parallel1,Metal/flash attention, no warmup/prompt/idle cache/contextshift, cache_ram0, native Jinja and loopback host. Candidate identity and release config are checked BEFORE any durable request/lifecycle claim or load.

Protocol **3**, distinct from synthetic C2. Release manifest has out-of-band expected byte hash, run/config/call cap<=24/absolute deadline, and exact commit/path/envelope-hash allowlist. Initial release contains only the first already-existing request. Subsequent release requires an explicit trusted new manifest pin, the prior release hash, unchanged deadline/config/call cap, exactly one appended allowlist entry and completed prior history/publication. Sequence alone never authorizes new input. Caller authentication/out-of-band release delivery is not implemented by treating main as trusted.

Full role/content arrays are exact-hashed, field/type/size validated, with unknown decoding fields rejected. No tools are injected and no history truncated. Exact fetched commit/path and envelope SHA are checked, not a moving latest-main substitution. Parent response hash binds later requests. Local claims bind request commit/path/hash and config. Native rendered text/token IDs/hashes are stored before each fake generation, native template equality is required,1536-token headroom enforced and returned prompt usage checked. Raw HTTP bytes remain archived on post-response usage failure.

Separate injected lifecycle, HTTP, clock, FileStore journal and Git-object transport interfaces. Only reviewed C2 codec/hash/path/FileStore primitives are reused, not C2 protocol or Relay semantics. No C2 source/archive changes. The C3 publication hook currently transports sealed raw model response bytes; a real protocol-3 response-envelope/consumer binding remains an integration prerequisite below.

Once-only300-second setup; unchanged A6R900-second/31read admission function with75%/normal/no-peer/12GiB gates; one resident fake model. Fixed1800-second model/relay deadline starts immediately before load, and is never renewed. Initial fetch/setup/admission are recorded before that phase and remain inside the release absolute deadline. Later fetch/queue/binding/request/publication/idle/toolwait all consume the existing phase. Load/request<=180seconds, Git operations<=30seconds or smaller remaining deadline. Generation claim and physical-attempt receipt precede dispatch. No reload, fallback, hidden retry or resume after a lifecycle claim. Sealed results can be read without regeneration after publication failure; unsealed claims are indeterminate.

Watchdog thread starts after provisional owned identity exists during load, stays active between requests, and uses unchanged guard.violation thresholds for pressure/free20%/swap512MiB/RSS11GiB/disk/peer plus ownership, parent-alive and injected-clock deadlines. Independent idle callbacks need not be running for it to abort. Cancellation signals an actually blocked fake HTTP/load worker; the worker exits and owned child cleanup uses the unchanged B3 identity-checked stop arbiter. Cancellation-hook exceptions are recorded and do not bypass child cleanup.

Journal records distinct queue, network, setup, admission observations, load, native binding, request, toolwait/idle, publication and cleanup events. Runner prefill/generation subtimings are separately labeled **included in request wall**, not added again. Total wall spans adapter initiation through cleanup. Physical attempts, failure reason, raw response when available and stop receipts survive final fixture failures.

## Executed fixture coverage

Wrong first config and release pin/protocol/path/commit; wrong fetched object identity/hash; oversized/invalid messages and extra fields; expired input before load; context overflow; wrong native template and usage; actual blocked fake HTTP/load cancellation on deadline; idle pressure/peer/parent-death condition and fixed model deadline; setup/admission expiry; crash after dispatch entry with durable claim and no subsequent dispatch/reload; publication conflict retaining sealed raw result; dirty/source-conflict fetch errors and bounded blocked fake Git wait; latest-main changes unable to substitute the approved object; duplicate request denial and local sealed read; explicit next release with same residency and unchanged deadline; cancellation-hook error still releasing owned child. Fake successful second-call fixture uses two distinct approved requests, never a retry.

The final fixtures directory retains per-case durable journals, bound fake prompts/raw output where reached, B3 owned-stop receipts and cleanup_verified.json counters. Invalid first-config cases correctly produce no claim/load; their rejection is recorded in the test transcript and zero-call cleanup receipt. Fake Git failure tests inject adapter-level transport failures; they are not real GitHub conflict tests. The earlier accepted C2 local-repository transport tests remain separate evidence.

## Exact remaining integration gaps and safety limits

1. **No concrete real Qwen lifecycle, asset-attestation, loaded native tokenizer, HTTP or Git hook is installed.** Fake attestation/token IDs prove checks and control flow, not a real server configuration or new tokenization result. Real bindings must preserve these pins and be separately reviewed.
2. **The independent watchdog here is a thread.** It remains active while request handling is idle and reacts to a fake parent-alive failure, but cannot survive termination of the entire adapter interpreter. An external B3-style watchdog/owner-parent monitor must be integrated and tested against actual driver death before live use. The parent-death fixture injects that condition; it is not evidence of whole-process crash survivability.
3. begin/poll/cancel/sample/identity/stop hooks must be bounded and nonblocking as documented. Blocking fake requests use cancellable worker handles and are actually interrupted in tests. Arbitrary stuck synchronous hook code is not preempted by Python's checks; real HTTP/Git/subprocess hooks need enforced process/socket cancellation and remaining-deadline timeouts, not only post-return checks.
4. The future Git adapter must implement C2's clean-checkout/exact fetched-object/owned-path/no-force/conflict-halting rules with deadline-aware cancellation and durable network receipts. Current C3 Git is fake; C2's blocking30-second helpers are not silently presented as this integration. A protocol-3 response envelope must bind raw result, request commit/hash, configuration/native binding and timing, and the local consumer must validate it before any future tool/sandbox action. This source does not install that consumer or execute commands.
5. At-most-one attempt depends on a trusted persistent journal and correct exclusive-write callbacks. It is not production exactly-once delivery or transactional external side effects. Restarted lifecycle claims fail closed, not resume. No permission to retry an indeterminate request or to raise deadlines follows.
6. The initial fetch is bounded by release deadline and precedes the model phase; total elapsed includes it. A later study must freeze the intended overall episode clock and account for all setup/relay/coordination/tool waiting and cleanup. No subspan is claimed as end-to-end real-agent latency.

These gaps prevent claiming production qualification or releasing a24-call phase from these setup tests. No new live request manifest was published. Source/test artifacts are for lead review only.

## Final source pins and handoff

- c3_adapter.py:a3dec3a1b215a9310b32d73f385fd18d04cb4b3f45fa9d2358b67f8d09cbfbd5
- c3_fakes.py:d74425d3951ddcdd07631cc0f32ccdfd7027c9138014eb31bfb87c7f36b8b266
- c3_tests.py:4c26ce6f843b80ebf0ec367db532ac3556bef7227f1c7da51dbdfa6ecf054e91
- c3_setup.py:792c6cbf05334a52902a144ee96bd7576cef52cdf77ecc99f819cda2b6ccd5a2

Stop after publication for lead review. Lead owns docs and local sandbox qualification. Klear C0 remains failed; no Klear work. Qwen remains a future single-model pilot candidate, not competent from setup. Product goal remains blocked; readiness55%,change0,range45–65%. No benchmark or CONFIRM release.
