# REQ-026B pure setup review

The local Claude worker acknowledged the second correction request and completed
its two owned files at 02:19 UTC. The lead inspected that acknowledgment and the
actual source, rather than assuming a successful UI submission. No model, VM,
concrete process hooks or mechanics probe was executed by this implementation.

Source SHA-256:
`2691c651d91ba327fcc8c7260cb844beadf1e649829c89e11d250a899956d4d4`.
Test SHA-256:
`d142b664d66b7b9d162aeb80e57388ebe77164357a6670fdb7eb11129731c478`.

The reviewed corrections retain provisional PID/port ownership before reading
identity and block on absent/failed identity without blind signalling. Returned
replies make a call terminal before fallible validation, preventing regeneration
after history/clock failures. Logical routing survives unloading. Reuse and
invocation check foreign jobs. The hooks' own timeout responsibility is explicit.
The original pressure, deadline and mutation regressions are retained.

Lead validation: 63 focused tests passed in 0.07 seconds. The documented full
repository test suite passed **812 tests in 188.80 seconds**; see the
[lead receipt](audits/req026b_lead_20260927.json). A separate deterministic
fake-host episode switched small/large/small across three calls; each generated
once and all three fake processes were released. The receipt records source pins
and exact fake signal events. This is lifecycle simulation, not synthetic
statistical evidence, OS process isolation, model inference or task competence.

Acceptance is limited to a **pure injected-hook setup component**. Before any
use with actual processes, concrete hooks must enforce timeouts, prove
PID-reuse-resistant ownership, cover failures between spawn and return, and have
an independent external watchdog. Caller integration must call `release()` in a
`finally` path: terminal statuses or history failures do not all release a
resident process. `ensure()` is a low-level residency helper; it does not itself
apply logical routing policy or guarantee that a healthy return preceded every
deadline/pressure change. `run_call()` supplies the subsequent invocation and
acceptance gates. Neither API is a hard real-time or concurrency-isolation proof.
No real-hook/model-probe release follows from committing this source.

The worker corrected its earlier mutation-test method for stale Python bytecode
and reports reruns with bytecode disabled. The lead does not treat those private
mutation counts as independently reproduced; ordinary tests and the fake-host
recount above are the independently observed checks.

The active experimental priority is the separate Mac mini REQ-028 program; do
not launch a duplicate local model qualification. Codex retains design and
acceptance responsibility. The separately authorized Claude checkpoint loop
continues; it is not an experiment.

Readiness **55%, change 0 points, range 45–65%**. Remaining milestones:
competent fixed-target comparison with valid inference, final synthesis,
independent reproducibility and approved submission packaging.
