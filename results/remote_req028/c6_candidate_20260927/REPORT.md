# REQ-028C6 core candidate — production integration still held

Scope: executable finite mini worker and lead controller core, inert children,
loopback fixture HTTP, temporary local Git. No real model, Docker, generated host
commands, live GitHub poller, benchmark, download, or setup monitor was run.
C5 source/results are unchanged. This is implementation evidence, not a task
trajectory, coding-competence result, comparison, or evaluator acceptance.

Source candidate: `3173e87ca8798291847ab745b6147ae5ce91624f`.
Final frozen-source suite: **33/33 unique tests passed** in 35.154 seconds,
with before/after source hashes identical. Four progressive runs total
135.776 seconds and 118 method executions (33 unique, 85 repeat executions,
zero imported prior-test repeats). The second run retained one test-only Python
3.9 annotation-compatibility error; the final suite fixes and passes that test.
Only the final frozen run is the exact-source acceptance receipt; intermediate
runs are development history, not additional independent acceptance evidence.
Peak sampled descendant RSS across runs: 123,846,656 bytes. Raw retained test
files total 21,878,674 bytes; the published archive is 3,864,892 bytes. Archive
members were individually checked against all 14,560 retained files. The
neighboring receipt pins the archive and 117-source inventory. An initial local
archive included macOS AppleDouble metadata; it was retained locally but omitted
from publication, then repackaged without that metadata and fully verified.

## Implemented candidate

- `c6_launch.py worker|controller`: exact immutable lead release and complete
  transitive remote-source inventory; fixed per-run role roots prohibit changing
  an output argument to resume/replay. Both source commits must match this
  candidate's reviewed tree. There is no production fixture switch.
- `c6_engine.py`: finite 24-call/24-action chain, frozen initial messages, exact
  append of accepted assistant and pinned observation, prior-response and
  prior-observation hashes, exact Git objects, exclusive fsynced claims before
  dispatch. Failures end the run; uncertain publication is not retried.
- `c6_model.py`, `c6_supervisor.py`, `c6_gate.py`: new C6 approval gate with C5
  cleanup mechanics, unchanged Qwen/runner/cache/context/decoding, one admission,
  one residency, independent idle watchdog, 1800-second phase and 180-second
  load/request bounds. Requests carry both 20260927028 and its uint32 effective
  seed. Full native binding is saved before generation. Each native render is
  independently checked against the pinned template; turn 1 also checks exact
  archived C0 token IDs. Later token IDs are frozen from the attested native
  server, not independently retokenized on the lead host.
- `c6_protocol.py`: unchanged C0 interface gate; pinned YAML/Jinja observation
  formatting; full transcript with no context-window truncation. Context overflow,
  length finish, malformed fences, or unclosed thinking terminates without repair.
- `c6_git.py`: fixed origin, private index, immutable objects, fresh bounded
  fetch, unrelated main advances accepted, conflicting owned paths rejected,
  ordinary non-force single publication attempt. At most 360 fetches per host,
  at least 5 seconds between production fetches, all inside the fixed deadline.
  A race at push ends indeterminate; it does not need a global main freeze.
  Queue/fetch/publication spans and payload bytes are separate from generation.
  Exact wire bytes are unavailable and recorded as such.
- `c6_process.py`: actual subprocess cancellation and private-EOF guardian;
  bounded streamed output rather than unbounded `communicate()` accumulation.
  The sandbox boundary passes command text only as JSON data to a separately
  source-approved adapter, never as a host shell command or host argv.

## Hard integration gaps — not launch-ready

1. **Lead sandbox adapter absent and intentionally required.**
   `c6_sandbox_host.py` must implement the interface below and be independently
   qualified by the lead. C3 read-only flags do not qualify a writable sandbox.
   The lead reports no established writable-overlay quota; `/work` copy/base
   Python is not qualified. Lead commit `65239b47ec5821ac69c9d3fa95544d1e31eb637a`
   subsequently qualified W2R filesystem/import settings at original `/testbed`,
   activated testbed environment, 512MiB rw/exec/nosuid/nodev workspace tmpfs,
   64MiB `/tmp`, and read-only root. Archive population is 99,788,288 bytes,
   SHA256 `792ffe4a936f4e0561011f13405c134bcda00ece6cdc9a0a57a130040e98de6e`.
   These lead files were merged without rewriting either history. No probe was
   repeated remotely. This implementation
   makes no unbounded-overlay assumption. Storage enforcement, source import,
   host-controller-death cleanup, exact-owned removal and final-diff retention
   remain production-hook qualification gates (the W2R filesystem/import result
   alone does not qualify them). No adapter is downloaded or installed.
2. **Pinned submission implementation unavailable locally.**
   `c6_submission_checker.py` and the exact upstream
   `environments/docker.py` bytes at mini-swe-agent
   `04d809ceab9df28f9adaed044884180159172930` are required. The candidate does NOT
   infer `_check_finished` semantics from the prompt or accept a substring as
   submission. Inert tests use an explicitly injected fixed checker, not a
   claimed upstream submission-conformance test.
3. **Evaluation remains separately held.** `inventory.json` pins the local
   strict rule/config/identity sources, archived upstream evaluator source
   digests at `f7bbbb2ccdf479001d6467c9e34af59e44a840f9`, and Astropy metadata
   manifest/record (1 F2P, 175 P2P, content and eval-script hashes). The subsequent
   lead evaluator candidate supplies test-manifest SHA256
   `9bc3f4c3542d7bcb55ad254a14ecccfadcd1e75f071be204358bec319be5bafa` and
   dataset SHA256 `a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd`.
   Its file digest is bound in the publication receipt. This supersedes the
   inventory's earlier missing-manifest note; the inventory is preserved as
   created. Actual evaluator/context/resource/no-retry qualification remains
   held. No hidden test contents enter the model transcript. Image HEAD is the
   setup commit a4ae7a3; task upstream base is 80c3854a, not the same commit.
4. **Diagnostic capture is best effort at a hard deadline.** The controller
   always preserves its trajectory/artifacts and records an explicit unavailable
   diff if capture cannot finish. Guaranteed final diff after driver death or
   phase expiry requires the lead adapter's independent bounded capture before
   removal; it is not yet qualified. Non-submitted diffs are diagnostic/non-primary.
5. **Test resource statement:** serial unittest driver, one math-library thread,
   sampled aggregate descendant RSS, 300-second cumulative test allowance and
   100MiB artifact bound. macOS one-core CPU affinity is not enforced; inert
   subprocesses/HTTP/Git are primarily waiting on I/O. Do not call this a measured
   hard one-core quota. Production dependency environment and actual two-host
   behavior still require source review/qualification.

Missing adapters cause source authorization to reject on BOTH hosts before
preflight/model admission. Adding them changes the source tree and requires
another exact source review. No launch approval, renewable lease, or expiry is
manufactured by this candidate.

## Adapter interface for the lead

Fixed executable `python3 experiments/remote_req028/c6_sandbox_host.py INPUT.json`.
The input contains operation, payload, absolute deadline, run ID, sandbox contract,
submission contract, output path, and controller PID. The adapter must verify and
persist exact controller identity, own only its exact sandbox, arm independent
death/deadline cleanup, enforce output/storage bounds, and write exclusive JSON.
No arbitrary host command is accepted by the controller boundary.

- `preflight`: return exactly qualified/watchdog_armed/writable/storage_enforced/
  source_import_qualified = true and `contract` equal to the release sandbox.
- `execute`: payload contains `command` as data; return exactly `output` text
  (at most 1MiB), integer `returncode`, and `exception_info`. Dispatch is only
  after a durable action claim and inside the owned isolated sandbox.
- `diff`: return `{"diff":"..."}` from the exact owned sandbox. Do not submit it.
- `close`: return `owned_absent: true` only after exact-owned removal is verified.
- Separate fixed `c6_submission_checker.py INPUT.json`, operation
  `check_submission`: data-only upstream-pinned behavior; return boolean
  `submitted` plus the exact `docker_source_sha256`.

## Prospective commands — DO NOT RUN before new approval

From the reviewed repository on each respective host, using an existing relay
checkout whose fetch and push origin are exactly the approved GitHub repository:

```text
python3 experiments/remote_req028/c6_launch.py controller --release-commit LEAD_APPROVAL_COMMIT --release-path docs/req028_c6_source_approval.json --release-sha APPROVAL_FILE_SHA256 --relay-repo EXISTING_RELAY_CHECKOUT
python3 experiments/remote_req028/c6_launch.py worker --release-commit LEAD_APPROVAL_COMMIT --release-path docs/req028_c6_source_approval.json --release-sha APPROVAL_FILE_SHA256 --relay-repo EXISTING_RELAY_CHECKOUT
```

Fixed local role directories are
`results/remote_req028/c6_runtime/<approved-run-id>/{controller,worker}`; wire
artifacts are under the exact release root
`results/remote_req028/c6_runs/<approved-run-id>`. Neither role can resume a
previously created local role directory. The release schema is enforced by
`c6_protocol.release`; `fake_release` in tests is explicitly NOT an approval.

Test receipts, source pins, unique-test accounting and immutable evidence hashes
are in the neighboring publication receipt/inventory/manifest. Earlier failures
and intermediate runs are retained, not overwritten. No imported C5 test classes
are counted as new tests.

Readiness **55%, change 0 points, range 45–65%**. Remaining: competent fixed-target
comparison with valid inference; final empirical/manuscript synthesis;
independent reproducibility and author-approved package. Sandbox and real
trajectory execution remain separately held. Publish this candidate and STOP.
