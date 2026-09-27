# REQ-028A2R completed-job inspection, 2026-09-27

Owner: Yukang Zeng <ykzeng2019@gmail.com>. Source commit 554f34d; launch evidence 2496ef9. This is the scheduled read-only inspection of the existing job, followed by authorized publication. No new window, model run or retry was launched.

## Actual job state

Supervisor PID 39648 is absent. status.json reports EXECUTION_EXITED, returncode 0, observation_count 4, finished_utc 2026-09-27T03:20:27.669799+00:00. This zero supervisor/dispatcher exit is **not** a successful four-call mechanics result.

Admission observations: 03:18:21 UTC free 73% (failed), 03:19:21 free 75% (passed), 03:20:21 free 75% (passed, more than 60 seconds later), then final recheck at 03:20:21.550275 UTC free 75%, pressure 1, swap 233.31 MiB, no foreign inference, disk 22,249,889,792 bytes (passed). Exactly four observations. Original deadline 03:48:21 UTC remained unchanged.

Dispatch record: PID 39792, started 03:20:21.553681 UTC. execution_exit.json reports returncode 0 at 03:20:27.669255 UTC. No expiry record: capacity qualified and execution occurred. A2R driver PID 39801; model PID 39826; watchdog PID 39828. All five owned PIDs (including supervisor and dispatcher) are now absent. Model lifecycle records released=true and returncode=0. No currently owned model handle remains.

## A2R partial mechanics result

One healthy 32768-context slot loaded in 1.614146 seconds. Two calls completed, both HTTP 200 / finish_reason stop, with zero cached prompt tokens:

| Call | Literal response | Prompt / completion tokens | Wall response seconds | Compliance |
|---|---|---|---|---|
| 1 | DTR_READY | 33 / 4 | 0.317582 | exact match |
| 2 | fenced mswea_bash_command block containing printf DTR_READY | 49 / 15 | 0.578167 | format and literal fence match |

Exact call 2 response:

````text
```mswea_bash_command
printf DTR_READY
```
````

Runner timings: call 1 prompt 224.920 ms / prediction 81.615 ms; call 2 prompt 185.004 ms / prediction 382.513 ms. These are short-prompt mechanics receipts, not a benchmark or full-context throughput measurement. Generated text was not executed.

After owned cleanup, the required second-cycle admission was rejected: free metric **68%** versus required 75%, normal pressure 1, swap unchanged at 233.31 MiB, no foreign inference. Calls 3–4 and the second server were never started. Overall A2R status is FAILED (restart admission rejection after two successful calls), not four-call completion.

No watchdog pressure abort occurred. A3R was correctly skipped as a nonqualifying failure; no q8 KV comparison exists.

## Observed allocations and guards

Actual allocation logs (not the earlier zero-size planning entries):
- MTL0 mapped model buffer: 2375.91 MiB; CPU mapped model buffer: 304.28 MiB. Do not sum mapped views as independent physical residency.
- MTL0 f16 KV buffer: **4608.00 MiB**.
- MTL0 compute buffer: **150.63 MiB**; CPU compute buffer: **2.63 MiB**.
- Runner Metal breakdown: self 7134 MiB = model 2375 + context 4608 + compute 150 (rounded).
- Effective seed confirmed in runner log: 3081057844.

One-second monitor samples had free metric 75%, 22%, 23%; pressure stayed normal (1), swap stayed 233.31 MiB, no foreign inference. Maximum sampled owned RSS was 4,913,381,376 bytes. Samples do not guarantee the unobserved continuous peak. No abort receipt exists.

Fourteen preflight tests had passed before launch. This inspection verified **47 artifact hashes** plus all three new source snapshots. A1/A2 records remain unchanged. Raw allocation logs, requests, responses, watchdog samples, and lifecycle records are retained. No guards weakened and no execution deviations taken.

Product goal remains blocked, separately from the terminated background job. Readiness **55%, change 0, range 45–65%**. Lead retains scientific acceptance and the next release decision; two successful formatting calls do not establish coding competence or a competent fixed-target comparison.
