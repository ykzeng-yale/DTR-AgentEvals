# REQ-028A2R: bounded deferred admission, unchanged resource gates

Lead checkpoint, 27 September 2026 03:15 UTC. Worker `0c3ad95` completed A2
setup but admitted no server: normal pressure, free metric 73% versus required
75%, no foreign inference and no swap growth. Zero calls and zero server
lifecycles. A3 was correctly skipped. Lead verified the A2 archive hash manifest
and independently ran all seven guard/follow-up tests successfully. The generic
FAILED field means admission rejection here, not a model result. There is no
evidence yet comparing batch128/ubatch32 to the original batch configuration.

The earlier one-shot admission rule created an avoidable lead-message dependency
for transient capacity. This release permits one bounded deferred admission job;
it does not lower a guard, reserve capacity, change the target, or touch peer work.

## Released program

Create a new A2R run and source snapshot, preserving all A1/A2 artifacts. Reuse
the exact A2/A3 configurations and conditional-dispatch rule from
`req028_followup_memory_20260927.md`. No new weights, runner, KV alternatives,
context changes, benchmark episodes or transport are released.

One lightweight owned supervisor may check admission immediately and then every
60 seconds for at most 30 minutes (31 checks maximum). Save each reading, UTC
time and reason. Wait without model residency. All existing admission gates
must pass on two consecutive readings at least 60 seconds apart before launch:
normal pressure, free metric >=75%, no foreign model workload, >=12-GiB disk.
Both readings must pass; reset the consecutive count after any failed gate.
Recheck once immediately before launching. A failed final recheck returns to
waiting within the same deadline; it does not start or retry a model.

When admission succeeds, launch exactly one A2R driver using unchanged A2
settings, with a fresh 30-minute execution cap for A2R and conditional A3R.
This extra admission window is outside the mechanics phase and is reported
separately; it is not an episode budget change. Once a model launch occurs,
the original no-retry and A3 conditions apply. There is at most one A2R and one
conditional A3R launch sequence. No model is started after admission expiry.
On expiry, emit ADMISSION_WINDOW_EXPIRED, preserve evidence and exit; do not
start another window or loop the product goal. No user confirmation is needed
for authorized steps in this window.

This is the experiment's bounded resource-admission supervisor, not a new
recurring coordination monitor. Keep the existing lead heartbeat only. Report
the actual supervisor PID/identity, stage status, observation count and deadline.
If a tool session yields while the supervisor runs, retain its handle, continue
independent implementation/reporting work and let the lead's next scheduled
check inspect progress rather than spending continuous goal turns waiting.

Implement in owned `experiments/remote_req028/` paths. Fake-clock tests must
cover the two-reading requirement, resetting after failure, expiry without
launch, final recheck failure, and exactly-once dispatch. Preserve original
driver/source pins; parameterize new output paths explicitly and refuse existing
directories. Publish bounded supervisor/source and status receipts when ready,
then completed immutable records or expiry evidence. The lead retains scientific
acceptance. A running wait supervisor is **waiting for admission**, not inference.

Readiness **55%, change 0 points, range 45–65%**. Remaining milestones:
competent fixed-target comparison and valid inference, final synthesis, and
independent reproducibility/approved submission package.
