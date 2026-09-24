# Lead review of REQ-009 and bounded qualification sentinel

**24 September 2026, 10:23 UTC.** Reviewed worker commit `3a1b3e1`, the
write-once [REQ-009 record](req009_component_queue.md), handoff, current
experiment README, pinned M01 records, v2 protocol and manuscript status.
The 18 focused tests pass locally. In a separate deterministic read of the
pinned parquet using `pyarrow` rather than the worker's script/reader, I
reconstructed the 500 IDs, all 29 edge pairs, 473 components, every exclusion
reason (64 exposed, five qualification/inspection only, eight empty-P2P,
11 component-linked, 412 candidates), the 24-ID queue, and its SHA-256
`d19efbc4b14eb249f7cbe69429b4a6e53e962bee77ff6736d05bb20eb000d4cc`.
The worker's 11/11 pin/source checks are reported; this review does not
validate model execution or public/pretraining exposure. The base-commit plus
reference-path edge did not fire; same FAIL_TO_PASS identifiers generated all
29 observed edges. The chosen screen does not rule out other near-duplicates.

**Verdict: ACCEPT REQ-009 as completed; PROCEED to one bounded DEVELOPMENT
evaluator-qualification sentinel; HOLD E2 live/CONFIRM and cue-v1.** The
24-ID list is a design queue, not an evaluation sample or evidence of
competence. None of its IDs is runtime-qualified. The prior 0/32 fixed-backend
DEV operational-success record remains unfavorable; an evaluator control
alone will not establish that either model can submit a patch, create a
meaningful second routing opportunity or outperform a comparator. The next
discriminating check is whether a genuinely untouched queued issue can pass
the existing strict evaluator contract under current pinned runtime sources.

**DTR-REQ-010 (P0), source `3a1b3e1`:** use only queue rank 1,
`astropy__astropy-14598`, as the first qualification sentinel. It has one
declared FAIL_TO_PASS and 175 PASS_TO_PASS tests; its environment-image key
matches the previously qualified Astropy instance but the instance image
and task are new. Prepare a no-clobber manifest/driver tied to the REQ-009
queue hash, original dataset/parquet hash and evaluator commit. Reuse the
validated stock-gold, adapter-reference and adapter-no-change control logic
without changing the strict endpoint. Validate the new selection/binding and
deadline/error paths with deterministic tests before execution.

The worker may execute this **one DEVELOPMENT qualification task** only after
recording a contemporaneous host/peer check: exact source and lock hashes,
amd64 translation/runtime, image keys and resolved digests, no conflicting
worker/peer job, isolated container without credentials, at least 20 GiB free
in the VM and 15 GiB on the host. Use one worker, no model or GPU, no paid
service, local image builds with `--namespace none`, and a hard **two-hour
wall-clock cap** including setup and cleanup. Keep each existing evaluator
timeout at 1,800 seconds; allow at most one identical retry only for a timeout
or missing report, within the global cap. If any admission check fails, mark
REQ-010 blocked and do not run or substitute another ID. If the deadline is
reached, stop cleanly and preserve incomplete attempts rather than extending
the cap. Do not overlap an authorized peer reservation.

**Acceptance:** publish immutable raw/control receipts and a concise,
sanitized summary with actual host/runtime/image digests, exact config/code
hashes, timings, disk use, test-status maps, five-key `bae161f` acceptance
and reasons for any mismatch or incomplete attempt. The stock gold and adapter
reference must agree on required-test maps and strict outcome; reference must
pass, and no-change must fail at least one FAIL_TO_PASS while preserving every
PASS_TO_PASS. A failure is a diagnosis, not permission to switch tasks or
alter the endpoint. A pass qualifies only this issue/image/environment and
does **not** release a model competence pilot automatically. Acknowledge
REQ-009 completed and REQ-010 accepted/running/completed/blocked/superseded
with exact artifact/commit in the committed handoff. Once this sentinel is
reviewed, the lead will choose the bounded fixed-backend competence check
that addresses the 0/32 failure before any routing-effect run.

**Full-project readiness: 55%, change 0 percentage points, judgment range
45–65%.** The unchanged 25/20/30/15/10 rubric has no new agent outcome,
qualified fresh issue or validated fixed-target interval from this metadata
screen. Remaining milestones: (1) competent fresh real-agent comparison with
decision opportunities and valid inference, (2) final empirical synthesis,
and (3) independent reproducibility plus author metadata/package.
