# REQ-028A4 terminal result: restart recovery expired

Owner: Yukang Zeng <ykzeng2019@gmail.com>. Source 49a7d30, launch evidence ea85098. One bounded inspection at the requested 03:45 UTC lead checkpoint; no new run/window or renewal.

## Job and cleanup

Supervisor 41825 dispatched driver42512 at **2026-09-27 03:41:59.468158 UTC**. Admission had8 observations; last was a passing final recheck at03:41:59.464693 UTC: free75%, pressure1, swap233.31MiB, no foreign inference, disk22,236,753,920bytes. Original admission deadline03:50:59UTC was unchanged. There is no admission-expiry record because dispatch occurred.

Terminal supervisor status is **EXECUTION_EXITED**, returncode1, finished **03:45:05.464036 UTC**. A4 status is **FAILED**, exception **TimeoutError('restart recovery deadline')**. Model42530 and watchdog42532 served cycle0; model lifecycle confirms released=true, returncode0. Supervisor41825, driver42512, model42530, watchdog42532 are all absent at inspection. No currently owned model handle remains.

## Exact prompt setup and partial inference

Pinned runner template/tokenizer endpoints completed under watchdog protection without generation. Prompt manifest froze at **03:42:04.065849 UTC**, before first generation start03:42:04.068670. All six full requests, rendered strings, token IDs, counts and hashes are preserved.

| Call | Rendered tokens | Repetitions of neutral literal | Outcome |
|---|---:|---:|---|
| 1 | 33 | n/a | HTTP200, exact DTR_READY |
| 2 | 49 | n/a | HTTP200, exact requested fenced command |
| 3 | 33 | n/a | not attempted |
| 4 | 49 | n/a | not attempted |
| 5 | 8192 | 2040 | tokenization only; no inference |
| 6 | 24576 | 6136 | tokenization only; no inference |

Long prompts reached targets exactly, with128-token output headroom satisfied. Query traces include adjacent repetition boundary checks. This verifies prompt construction, **not** long-input model throughput or success.

Call1: prompt/completion33/4, cached0, wall0.215604sec, prefill127.875ms, decode82.138ms. Runner-reported rates: prompt258.065tokens/sec, decode36.524tokens/sec.
Call2: prompt/completion49/15, cached0, wall0.575644sec, prefill184.648ms, decode382.008ms. Runner-reported rates: prompt265.370tokens/sec, decode36.648tokens/sec.
Both finish_reason stop, both raw usage fields equal their receipts and exact frozen prompt bindings. Literal call2 response:

````text
```mswea_bash_command
printf DTR_READY
```
````

Generated text was not executed. Healthy first-server load took1.074960sec. Six-call completion and restart qualification were **not achieved**.

## Recovery and resources

After owned model release, bounded recovery sampled12 times at approximately15-second spacing. Free metric ranged69–74%, never meeting75%; normal pressure1, unchanged swap233.31MiB, and no foreign inference were recorded. First recovery sample03:42:05.442332UTC, final sample03:44:51.118353UTC. The180-second deadline expired at03:45:05.407901UTC. No second server was launched. This wait was inside the fixed900-second mechanics budget; mechanics elapsed183.353sec (plus prelaunch setup recorded separately). Initial admission waiting was about360.427sec and distinct from mechanics.

Loaded watchdog recorded3 samples, free metric24–75%, normal pressure and no abort. No pressure-abort receipt exists. Actual allocator logs: f16 KV4608.00MiB; Metal compute150.63MiB; CPU compute2.63MiB; Metal mapped model2375.91MiB and CPU mapped model304.28MiB (mapped views are not additive physical-residency measurements).

This inspection verified **60 artifact hashes**, both new source snapshots, all six rendered/token-ID bindings, prompt-freeze ordering, and both raw responses/usage against receipts. Twenty-one preflight tests had passed before launch. All original records and guards are preserved; no retries, new configuration, peer/cache intervention, q8, benchmark, Klear, transport or CONFIRM.

The result is **two successful short calls plus recovery-capacity failure**, not a long-context serving failure, routing null, coding-competence result or complete infrastructure qualification. No attribution to peers or swap exhaustion is supported. Lead retains the next scientific decision.

Product goal remains **blocked**, separate from the terminated job. Readiness **55%, change0, range45–65%**.
