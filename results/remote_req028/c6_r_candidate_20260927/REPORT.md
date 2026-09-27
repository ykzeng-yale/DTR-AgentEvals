# REQ-028C6R executable integration candidate

Status: **DONE_WITH_CONCERNS for implementation/inert testing; no production release.**
Source commit: `20aa347ff02c1df4eac994cf8ff960cb1a12458d`.

The lead's original C6 result remains **32/33, with a guard failure**. The earlier
remote 33/33 report does not supersede that independent finding. Both lead
regressions were addressed. C5 source and all prior C6/W1/R1/W2/W2R results remain
unchanged in history. No real model, Docker/container, generated host command,
benchmark, download, live GitHub poller, or setup monitor ran in this preparation.

## Debug findings and corrections

The investigate workflow guided root-cause checks and executed regression tests.

1. **Guard state was not latched.** C6 inherited C5's process-liveness-only check,
   so a terminal receipt could exist while the supervisor still appeared alive.
   `c6_model.Lifecycle.check` now rejects and latches terminal receipts, stop
   requests, recorded guard violations, and unreadable guard records. It is
   checked immediately before claims and by the native HTTP dispatch boundary.
   An actual inert supervisor is held at a controlled post-terminal teardown
   barrier: the test observes `poll() is None`, zero model claims, zero physical
   fake generations, and no second request.
2. **Early parent exit broke group ownership.** The previous guardian reaped its
   direct child and lost a safe group anchor while a grandchild held the pipe.
   `c6_anchor.py` now remains an unreaped session/group leader across payload
   exit. The guardian never polls/reaps this anchor before signaling and checking
   the whole owned group. This prevents PID/PGID reuse during cleanup. Tests
   observe descendant absence before fixture teardown, including driver death.
   `child_reaped` and `owned_group_absent` are separate facts. Escaped arbitrary
   sessions are not claimed as owned; host payloads are fixed trusted Git/HTTP/
   Docker utilities, never generated commands.
3. **Further executed-test findings are preserved.** Initial C6R tests found a
   missing test import and an overflow-error receipt that exceeded the wire JSON
   encoder cap. Runtime process receipts now have their own bounded encoding.
   The combined run then found macOS `EPERM` when signaling an already-dead group.
   Signal errors are recorded, group absence is independently checked, and
   ambiguous/live cleanup fails closed instead of losing the receipt.

## Concrete adapters, no remaining placeholder files

- `c6_sandbox_host.py`: fixed production entrypoint, atomic exclusive file IPC,
  no production fixture flag, exact source approval, fixed per-run directory,
  and actual controller identity binding.
- `c6_sandbox_guardian.py`: independent finite owner, armed before create;
  unique name/label intent persisted before the create request; exact full CID,
  name, label and image revalidated before operations/removal. It survives
  ephemeral adapter exits, watches the actual controller, and never resumes a
  terminal session. Controller death during a bounded create is reconciled after
  create returns, rather than abandoning ownership registration.
- `c6_sandbox_backend.py`: fixed Docker executable
  `/Users/yukangzengcmac/.local/dtr-runtime/bin/docker`, context `colima-dtr`,
  separately supplied exact executable SHA, pinned image and W2R archive. The
  existing archive is hash/size checked, not re-exported. `--pull=never` prevents
  implicit download. All peer containers, including stopped ones, are rejected
  before create. No VM/peer changes, host mount, socket, or host secret forwarding.
- `c6_container_helper.py`: fixed reviewed source passed to isolated container
  Python (`-I`); command text travels only as JSON on stdin. Actual actions use
  container `bash -lc` at `/testbed`, preserving the testbed environment. Combined
  output is streamed and capped at 1MiB; command deadline is at most 60 seconds
  and remaining action lease. Timeout, overflow or command failure terminates the
  sandbox session and removes the whole exact-owned container, not just its client.
- `c6_submission_checker.py`: data-only binding to exact upstream Docker source
  SHA `21d389122b008e7b743d1e640207fda0b08d9010cf6323ddd02f0742b33b96a6`, with MIT
  license pin. It reproduces lstrip, first-line strip equality and returncode=0.
  Embedded/later-line/nonzero near matches do not submit. Tests compare against
  the isolated actual upstream `_check_finished` function without constructing
  DockerEnvironment. Upstream submitted payload/exit message is preserved
  separately from explicit-Submitted workspace-diff capture.

The filesystem contract remains W2R: original `/testbed` on 512MiB
rw/exec/nosuid/nodev tmpfs, 64MiB `/tmp`, read-only root, linux/amd64, 1 CPU,
1GiB/no swap, 128 PIDs, no network, cap-drop ALL, no-new-privileges. Preflight
checks image identity/platform, inspected limits, mount/capacity facts, original
HEAD and Python/import path. Image setup HEAD a4ae7a3 is not upstream task base
80c3854a. No scientific target, model, prompt, decoding or evaluator rule changed.

## Deadlines and cleanup truth

The original setup+admission lease is fixed at creation+1200 seconds or absolute
release expiry. Its operation deadlines do not renew residency. Preflight wire
receipts carry that lease; stale readiness prevents a model load, and admission/
load cannot outlive it. The controller watches local guardian liveness while
waiting for the worker, without a recurring task or new polling service.

One `bind_phase` operation adopts the exact worker-ready Git object and its
phase-start+1800 deadline, bounded by release expiry. Identical adoption is inert;
changed adoption is terminal. A **15-second cleanup reserve is inside each
lease**, so command/idle work ends before that reserve. Fake-clock and live
process tests cover immutable phase adoption, expiry and residency across
adapter-operation returns.

The guardian attempts a bounded diagnostic diff before removal, leaving at least
10 seconds for removal after its initial identity lookup when possible. Cleanup
has priority; unavailable diff is explicit, not fabricated or salvaged as
submission. Diff work and repository contents remain container-contained; host
Git does not execute repository diff/textconv hooks. Journal failure cannot skip
cleanup: fixed bounded inspect/rm have a journal-independent path.

A timed-out daemon create that never yields an inspectable exact identity remains
**indeterminate**, not falsely certified absent. A foreign/reused CID/name/label
is never removed and is reported cleanup-unconfirmed. Tests deliberately exercise
that failure classification with fake metadata; no real foreign container exists
or is modified. An unexpected guardian failure likewise forbids restart/replay.

## Executed tests and immutable evidence

| Run | Methods | Result | Wall seconds |
| --- | ---: | --- | ---: |
| C6R initial | 20 new | 15 pass, 4 test-import errors, 1 overflow-receipt failure | 39.993 |
| Combined | 20 new + 33 prior | 52 pass, 1 macOS cleanup-receipt failure | 121.037 |
| Source-frozen full suite | 23 new + 33 prior | **56/56 pass** | 116.582 |
| Final narrow hardening | 3 repeated new tests | **3/3 pass** | 10.246 |

Total **287.859 seconds**, under the 300-second cumulative allowance. There are
**23 new unique C6R tests**, not 132 new tests: 132 method executions comprise
66 executions of new tests and 66 executions of the 33 prior C6 tests. No test
classes are multiply imported as new coverage. Every run has unchanged
before/after source fingerprints. The final three-test run covers the subsequent
`--pull=never` addition and test guardian-reaping adjustment; it is not claimed
as a second full-suite run on those last three changed files.

The new tests cover full finite controller/worker operation through the concrete
adapter with fake Docker, two linked turns and explicit submission, guard
barriers, parent-exits-first/driver-death descendant cleanup, create/start/
populate/execute controller-death boundaries, phase/identity/expiry conflicts,
output overflow and timeout with no second action, journal-failure cleanup, and
diagnostic classification. The prior local-Git linked-turn/immutable-publication
tests are rerun as prior coverage, not relabeled new.

Peak sampled aggregate descendant RSS: **151,830,528 bytes**. One serial test
driver and one math-library thread were used. macOS one-core affinity is not
enforced; sampled RSS is not a hard memory limit or an assertion about every
orphaned instant. New retained test/package files totaled 26,340,092 bytes before
this report, below 100MiB. No fresh benchmarks were substituted for inert tests.

The package contains **14,427 new raw evidence members** and their full mapping
in `current_member_inventory.json`. Archive SHA256:
`e1e765e92fa9386a1df8ad3eb030877d5178033b18d904dfcbf6212bce3ebe8c`.
It also supplies the missing **14,560-member historical mapping** in
`prior_c6_member_inventory.json`, matching the originally reported mapping digest
`679aa8e90c0e68d70605714168b26c486ec3ef1055bd7977bfab80db222aa5bb` and the unchanged
prior archive. All archive members were hashed against the mappings. `receipt.json`
pins 129 remote source files and the upstream snapshot/lead design/evaluator inputs.

## Next gate and prospective commands

**Lead source review and real sandbox-only qualification come next.** This
candidate implements the actual hooks, but fake Docker does not establish live
Docker cleanup, mounts, import behavior, or command execution. No real trajectory
or evaluation is authorized. The lead must supply the actual Docker executable
SHA and truthful qualification/source pins in a new immutable release. The
constructor-level Guardian/Docker APIs permit a separately source-approved
sandbox-only qualification driver; a full trajectory release must not be
manufactured merely to test those hooks.

After all separate gates and an exact source-bound approval, the prospective
commands remain:

```text
python3 experiments/remote_req028/c6_launch.py controller --release-commit LEAD_APPROVAL_COMMIT --release-path docs/req028_c6_source_approval.json --release-sha APPROVAL_SHA256 --relay-repo EXISTING_RELAY_CHECKOUT
python3 experiments/remote_req028/c6_launch.py worker --release-commit LEAD_APPROVAL_COMMIT --release-path docs/req028_c6_source_approval.json --release-sha APPROVAL_SHA256 --relay-repo EXISTING_RELAY_CHECKOUT
```

Do not run these now. No expiry or execution authorization is invented here.
Publication is followed by STOP, not a token-wait loop.

Readiness **55%, change 0 points, range 45–65%**. Remaining: competent fixed-target
comparison with valid inference; final empirical/manuscript synthesis;
independent reproducibility and author-approved package.
