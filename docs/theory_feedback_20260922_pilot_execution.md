# Lead review of the prospective pilot runner and report

04:49 UTC review cycle, 22 September 2026. Worker revisions reviewed: `4d75e5b`, `482ba42`, `c8a87c4`,
`4c4c11d`, with late `5100fea` / `427b743` / `11a7344` reviewed before publication. The frozen eight-task/sixteen-episode development frame and original source pins are unchanged.
At the initial checkpoint no conversion receipt was available; the late publication now records completion
and block start, as detailed below. No Coder task outcome is published. This is
source/mock validation before outcomes, not validation of model performance or a new confidence interval.

## Shared-host release and current work

The [inspected cross-project release record](audits/shared_host_release_544b1e6.json) pins MultiRound's
`544b1e6ad7ecf9f8642ad2c352dfa6073289058d` launch artifact by hash. It records its own server PID 8458 started
04:35:13 and stopped 04:46:01 UTC, zero generation requests, and a readiness-marker error that exhausted its
setup allowance. Its E12 collection did not run. This is inspection of a committed worker record, not an
independent live process observation. DTR's `4c4c11d` reports a fresh ownership check 04:46:15 and resumed
pinned download/BF16 conversion 04:46:38. The lead [acknowledged the release and DTR's next block](https://github.com/ykzeng-yale/DTR-MultiRoundLLM/issues/3#issuecomment-5771387530).
There is no new MultiRound reservation. The agreed next DTR block remains available after source/resource
checks, with actual start S/end S+7200 and owned PIDs published. Do not infer availability solely from an
expired timestamp, start a duplicate job, or signal another project's processes.

## Findings and bounded corrections

The originally supplied runner/report fixtures pass, but independent production-path review found cases they
missed. These are implementation defects found before outcomes, not scientific evidence against the models.

| Existing condition | Reproduced/source-inspected defect | Required corrected behavior |
|---|---|---|
| Host block ends by S+7200 | Admission is checked only before setup, whose load/probe waits can exceed the reserved switch allowance; no absolute outer deadline | Bound setup/probes/episodes by the actual deadline, recheck admission after setup and retain time for owned cleanup. If the remaining full episode allowance no longer fits, leave that assignment unstarted. |
| Episode allowance and physical request accounting | Long requests can run beyond the between-step wall check; attempts persist only on successful episode exit; unknown terminal counts become zero and partial directories are automatically rerun | Bound request waits by remaining episode time, persist physical starts/results durably, conservatively reserve unknown usage, and reconcile interrupted attempts before any further dispatch. No automatic extra episode per selected task/backend. |
| Frozen episode identity at restart | Matching task/backend strings alone do not establish matching image/model, harness, configuration and cp2/wc2 bindings | Refuse mismatched source bindings before reusing a terminal record; preserve it for reconciliation rather than rerunning or relabelling it. |
| All assigned tasks and valid grade identity in reports | A misleading directory name admits another task/backend/run's episode or grade; paired rows omit wholly unstarted tasks | Validate episode/grade/submission linkage, retain every assignment and all eight task rows, and refuse conflicting records. |
| Call-9 decision opportunity | Saved assistant messages need not equal invoked logical calls after format/transport failures; missing history can crash aggregation | Keep issued/invoked-call evidence separate from available history; use a pre-call snapshot when recorded. Report unavailable feedback explicitly and never invent zero feedback. |
| Cost and correctness reporting | Missing usage becomes zero; an evaluated record with unknown strict-parser outcome can produce a falsely exact secondary bound | Report known cost subtotals with missing counts; retain unknown totals. Use the actual endpoint/classification for missingness and expose the denominator of every completion bound. |

The repairs belong to **DTR-REQ-002**, not a new request or an expansion of scientific scope. Pull the integrated
source for the next runner invocation, without replacing files under the already active block. Use the
repaired report/grade code at analysis after release. Preparation and the active authorized block may continue. Passing these
specified source/fixture checks closes the repair step without a further scheduled scientific permission round.

## Scientific interpretation of partial and complete reports

The pilot's primary operational denominator is **all sixteen assigned episodes**. Unstarted, interrupted,
ungraded and invalid records remain visible. A genuine recorded failure to submit is an operational failure
under the existing deployment contract, with infrastructure-suspect exits separately flagged; it is not a
measured failure of the candidate program's algorithmic correctness. An integrity refusal is not a valid zero.
Finite completion bounds for the operational count must include every unknown assignment. They are not
confidence intervals, power statements or population-rate bounds.

The secondary algorithmic endpoint concerns the **locally verified Submitted, nonempty artifacts**. Verify
artifact bytes against the episode before admission. A grading-integrity refusal can leave a valid original
artifact's correctness unknown; it does not justify removing that artifact from the denominator. Evaluator
failure and unusable strict-test parsing widen its completion range. Non-submissions are outside this
conditional algorithmic endpoint rather than declared incorrect programs. Each backend can produce a different
set of eligible artifacts, so these conditional summaries are not a common-population causal contrast. This distinction does not change the
main project's frozen ratio-of-expected-totals scientific target or promote this DEV pilot to CONFIRM.

Call-9 occupancy and feedback availability must be reported together. At pinned mini-swe-agent `04d809c`,
`DefaultAgent.query` increments `n_calls` before calling the model and appends a returned assistant message
only afterward. A ninth invocation can therefore coexist with fewer than nine saved assistant replies.
Missing history or failed calls do not establish no routing opportunity or no useful feedback. Costs with
unobserved tokens/attempts are incomplete; a known subtotal must not be presented as a full matched cost.

After the frozen pilot completes, the next discriminating review remains the original one: distinguish failure
to produce eligible patches, evaluator uncertainty, context/budget/format exits, and insufficient feedback or
call-9 opportunities from failures on graded candidate programs. Report all assigned outcomes and paired
success/cost summaries, retaining unfavorable results. Do not replace tasks, change metrics using outcomes,
launch learned routing or CONFIRM, or claim routing superiority from this fixed-backend feasibility comparison.

## Late publication: conversion completed and block 1 started

Worker `5100fea` publishes the common BF16 conversion receipt; `427b743` records block 1 start at
**05:06:57 UTC**, hard end **07:06:57 UTC**, large Coder server **PID 13026 / port 8293**. A separate
read-only review matches both frozen source pins, 14+16 input verification records, 12 tool hashes, output/served
hash, first-task backend order and the exact 7200-second interval. It does not independently rerun the 30 Hub
comparisons or hash remote served bytes. Model preparation/serving remain worker-reported. Late `11a7344` adds the 14B non-task preflight: 16,384
context/one slot, HTTP200 probes, 436 short-generation tokens in39.9 seconds and a15,930-token long prompt in
107.4 seconds. The worker reports first task episode started05:09:35; no terminal task outcome is published.
The approximate11 tok/s generation rate means long prompts can make the fixed1800-second wall binding. Keep
that limit and report wall-limited failures explicitly; do not infer a pure algorithmic capability deficit. The reported load raises swap usage by about
3.89 GiB, so memory pressure must remain in the measured runtime record, not be dismissed as an established fit.

**Active-run guidance:** block 1 predates this repair. Keep its exact runner/episode source pair stable; do not
pull replacement episode code underneath a live old parent (the new deadline arguments differ). The worker
should supervise its own published 07:06:57 cap, preserve time for owned cleanup, and record any overrun or
unconfirmed release honestly. Apply the repaired runner and episode together at the next natural block boundary;
do not restart/repeat assigned episodes or stop another project's jobs. Preserve block-1 records, conservatively
reserve unknown usage, and label unavailable feedback/attempt telemetry and any protocol deviations. Analysis
repairs can be used after release. The new publication does not reopen the host window to MultiRound. Preflight
contains non-task model generation probes, not a model-free step.

## Validation

Source review also identified two independent mock counterexamples: a server still alive after timed-out
termination was labelled stopped, and a terminal episode with changed harness settings was reused. Both must
refuse a false release/reuse. Pinned upstream `DockerEnvironment.cleanup` launches an asynchronous shell; its
return alone does not verify container release. The integrated wrapper observes cleanup of its exact owned
container and retains uncertainty from failed writes or interrupted cleanup. Pending ownership is registered
at spawn, then cleared only after confirmation. Independent review found these exception paths before
publication. Review and tests use mocked processes and requests only.

Validation: **19 runner/episode fixtures**, **18 report/grade fixtures**, **18 existing grading/capture/conversion
tests** (plus eight conversion subcases), and the **37-test main suite** pass: 92 tests in total. The final
combined runner/report check passes all 37 fixtures. `git diff --check` passes. These are deterministic tests,
not execution validation or empirical evidence. No model, converter,
benchmark container or Monte Carlo was run by the lead.

## Evidence status and next checkpoint

**P1 DTR-REQ-002 — proceed with the authorized active block under its published cap; use the repaired source
at the next block boundary.** Conversion/start artifact consistency is accepted. Next acceptance artifacts:
remaining small-backend preflight, immutable full/partial episode records, observed release and a correctly labelled report. Unknown or failed
records remain in the cohort. **P0 DTR-REQ-004 — release accepted from committed evidence; publish actual DTR
start/release and coordinate any later request explicitly.** No additional user permission round or new workload
is requested. Acknowledge existing IDs as accepted/running/completed/blocked with the processed commit and exact
artifacts. Both author and committer remain Yukang Zeng <ykzeng2019@gmail.com>.

Theory/manuscript results are unchanged. **Full-project readiness 55%, change 0 percentage points, range 45–65%**
under unchanged weights/stages. Remaining milestones: useful validated inference/adequate real-agent
comparisons; final empirical/manuscript synthesis; independent reproducibility, author metadata and packaging.
