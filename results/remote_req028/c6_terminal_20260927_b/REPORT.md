# C6B terminal evidence

Run `c6-dev-20260927-b` reached controller status **submitted**, with four action claims and no controller error. **Submission is not measured task success.** No evaluator or hidden tests ran; diff review and strict evaluation remain the lead's separate responsibility.

The worker preserves status `terminal_or_failure` and error `RuntimeError('peer terminal: submitted')`. This is the generic peer-terminal path after controller submission, not recurrence of run-a's negative-sleep error. The supervisor's `Rejected('owner_parent_exited')` records normal private-pipe closure during owned cleanup. All raw labels are retained without rewriting them as a success score.

## Physical work and costs

One model residency produced four physical generation dispatches and four completed raw responses. Four requests/responses were published. The controller claimed four actions: two source-reading commands, a three-line sed edit command, and the explicit submission echo. Three ordinary observations were published; submission takes the terminal path rather than publishing observation 4. Each completed response stopped normally and passed the unchanged interface gate. The third observation reports returncode 0 and empty output, which does not establish correctness of its edits. Generated commands ran only in the qualified lead sandbox.

| Call | Prompt tokens | Completion tokens | HTTP wall seconds |
| --- | ---: | ---: | ---: |
| 1 | 1,530 | 199 | 10.523611 |
| 2 | 2,287 | 133 | 11.270761 |
| 3 | 4,928 | 393 | 30.403441 |
| 4 | 5,345 | 170 | 24.661779 |
| Total | 14,090 | 895 | 76.859593 |

Total tokens: 14,985, with zero cached prompt tokens reported. Native binding/token counts, raw HTTP bytes, request Git-object provenance, requested/effective seeds and server timings are verified/preserved in the receipt and archive. Server prefill/generation times are nested within HTTP wall time, not additive.

Dispatch: 10:19:14.788024 UTC. Model phase: 10:20:24.582206 UTC. Controller terminal: 10:24:40.610234 UTC. Worker terminal: 10:24:53.408818 UTC. Phase through worker terminal: 268.826612 seconds, including relay/tool waits and cleanup; deadline was 10:50:24.582206 UTC. Worker performed 41 finite relay fetches. Queue and network timing records are included; exact Git wire-byte counts are unavailable. No money/energy estimates are inferred from tokens.

Both attempts must remain counted: runs a+b total two model loads, six physical calls and six controller action claims, 17,907 prompt tokens + 1,227 completion tokens = 19,134 total tokens, and 98.850332 seconds summed HTTP wall time. Run-a remains an archived infrastructure failure, not discarded favorable-result selection. This exposed task cannot estimate independent competence or routing benefit.

## Guards and cleanup

Admission passed three samples (75%, 76%, 76% free memory), with the scheduled passes 60.118594 seconds apart and a final pre-Popen check. All 262 runtime guard samples were violation-free: minimum free memory 40%, maximum owned RSS 2,699,542,528 bytes, minimum disk free 15,484,657,664 bytes, normal pressure level 1, swap unchanged at 233.31 MiB and no foreign inference observed. These are sampled extrema.

Cleanup recorded one TERM, direct-child reaping, owned model absence and no audit errors. The ONE authorized OS inspection at 2026-09-27 10:31:09.315974 UTC found worker 65249, supervisor 65525 and model 65662 all absent; no signals were sent. The published controller terminal records owned container absence. Lead separately reports controller 42201/guardian 42499 absent; this report does not claim a fresh remote inspection of those local-host PIDs.

## Complete immutable package

`runtime_evidence.tar.gz` preserves every file from the worker runtime, launch directory and checked-out run-b wire directory: **4,506 members**, each verified against `member_hashes.json`. No reconstructible cache or failed receipt was omitted. Four accepted requests are separately extracted from their exact accepted Git commits and SHA-checked. All 130 source pins and the exact release SHA were verified. The original run-a package and prior failed artifacts remain untouched.

- Archive SHA-256: `50d937b11c0d3fe3b6905e2f510e41d3efa9087f66e9f931fc6182bf19476f49` (2,695,008 bytes).
- Member mapping SHA-256: `8a7c11f743541c7a045324209929bd7f7a12a99f4ca761a37edddbb949fcf77f`.
- Source commit: `1a1aa09dbdaf537af6aa4ad499987a80dda027a6`.
- Release commit: `0d228d7a56ec0c5ac3232fb35c6224dce7e01af7`.
- Release SHA-256: `3a2ba1e00b6cf59a1dbf1cf080dd510c47768fd1a0b59c108009ab2f2d886669`.

No model/source edit/rerun/resume/evaluator was performed during this terminal packaging. STOP after publication; no polling loop.

Readiness **55%, Δ0, range 45–65%**. Remaining: competent fixed-target comparison/valid inference, final empirical/manuscript synthesis, independent reproducibility and author-approved package.
