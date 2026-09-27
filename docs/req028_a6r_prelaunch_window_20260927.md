# REQ-028A6R: put the bounded admission window at model launch

Lead reviewed5ff207b:45 artifact hashes independently verified;30 focused tests
passed locally, including first-call abort/skip/owned inert-process cleanup.
A6 recorded75% at final supervisor admission, then74% at model prelaunch2.66seconds
later. No model or watchdog launched; zero attempted calls, two unattempted.
Both48041 and48252 are reported absent. This is not a q8 feasibility result.
The cause of the metric change is not identified; normal pressure, unchanged
swap and no foreign inference do not support blaming another job. Source was
published after supervisor startup but before driver dispatch; preserve this
sequencing deviation and immutable source manifest, not a fabricated clean history.

The implementation performs static hashing/setup between the admission window
and actual launch. Its fail-closed final check worked correctly, but ending the
whole study on that prelaunch dip leaves the resource question unanswered.
Move the same bounded admission logic after static setup and immediately before
model Popen, retaining every threshold. This changes orchestration, not model
configuration, targets, prompts or acceptance. It cannot guarantee admission.

## Exact one-shot release

A6R repeats the UNATTEMPTED A6 two-call design as a new immutable run. Read
req028_a6_q8_context_20260927.md in full; its source/model pins, q8_0 K/V,
32k context, batches, decoder, exact8k/24k bindings, call order, no retry/restart,
independent watchdog and all resource limits otherwise remain unchanged.
No A6 directory or manifest may be modified or reused.

Publish source successfully before starting any supervisor, with explicit failure
propagation (separate checked commands; a failed git command must prevent launch).
Verify no old48041/48252 job and no live owned model/watchdog. Perform static
source/model/archive hashing and request-copy preparation ONCE, with a300-second
setup cap, without a resident model. After that start ONE fixed900-second admission
window immediately around model launch. No outer admission window or repeated
expensive setup. Record separate setup, admission and execution timestamps.

Read the same complete admission gates every60seconds; require two consecutive
passes at least60seconds apart and a fresh immediate pre-Popen recheck. Count
all reads including rechecks against31 maximum. If that final check fails and
no model has been launched, reset the passing streak and continue waiting ONLY
inside the original900-second deadline/31-read cap. Never extend the deadline,
renew a window, change thresholds or launch after expiry. This is waiting before
any experiment, not retrying a model request. At expiry record zero model calls
and stop. Once Popen is attempted, no second model launch is allowed even on
startup/ownership/token-binding failure. Setup exceptions also stop.

After qualifying admission, the model execution cap is600seconds from immediately
before Popen, with each load/request<=180seconds and watchdog throughout loaded
setup/inference. This explicitly replaces the prior600seconds from DRIVER dispatch
because this driver now contains admission waiting; total stages remain bounded
by300+900+600seconds. Persist all three deadlines; no hidden unlimited setup.
Retain admission>=75%,normalpressure,nopeer,12GiBdisk and all loaded abort rules.
No sleeping while a model is resident to seek better capacity after an abort.

Before launch test the actual gate/control flow with fake clock/readings:
final check75->74 resets and later qualifies within the SAME deadline; perpetual
74 expires with no Popen; deadline-crossing final check never launches; success
launches once; setup failure and Popen failure never retry; first-call failure
prevents call2 and cleans up. Preserve existing30 tests and source pins. Record
source hashes and tests before supervisor launch, actual process handles/deadlines,
all observations and immutable partial/terminal artifacts. No new downloads,
Klear, transport, VM, benchmark, CONFIRM, peer/cache/Lean changes or new monitor.

Continue through implementation/tests/publication/this bounded run without waiting
for another heartbeat. A6R completion still requires lead interpretation and next
competence/transport decision. Readiness55%, change0points, range45–65%; remaining
competent fixed-target comparison/valid inference, final synthesis, independent
reproducibility and author-approved submission package.
