# REQ-028A5: isolate long-input serving from restart admission

## Lead review and diagnosis

Reviewed worker commit d2da330. Lead independently verified 60 artifact hashes,
all six rendered/token-ID bindings and both raw responses against usage receipts;
21 focused guard/admission/A4 tests passed locally. A4 froze prompts before its
first generation. Two short calls returned exact requested text (33/4 and 49/15
prompt/completion tokens). Recovery recorded 12 readings at 69–74% free, normal
pressure, unchanged swap, and no foreign inference. The 180-second recovery
window expired. No second server or long-input request ran. Remote OS inspection
reports supervisor41825, driver42512, model42530 and watchdog42532 absent.

This is a partial serving result and a restart-admission failure, not a long-input
failure or routing null. The lead design unnecessarily put restart admission
before the unanswered long-input question. More short-call replications would
not discriminate capacity from this sequencing limitation. Normal pressure and
no foreign inference argue against attributing the failure to another agent;
the free metric alone does not identify reclamation behavior or a memory leak.
Successful long calls would establish bounded serving feasibility only. A resource
abort or timeout would instead bound feasibility under this precise envelope.

## Exact new DEVELOPMENT release

Authorize one A5 single-load run, exactly two logical generation calls: the A4
8,192-token prompt followed by its 24,576-token prompt. No short calibration calls,
restart, retry, fallback or new model. Preserve A4 as failed/partial; A5 cannot
qualify its restart or turn A4 into a six-call success.

Reuse the A4 exact model SHA3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597,
runner4fea119de30f6a923992780f6fd5ccb0bee5d47d and verified binary/source pins.
Same32,768 context, f16 K/V, batch128/ubatch32, one slot, two threads, Metal,
loopback, no warmup, no prompt cache, no context shift, temperature0,
seed20260927028, output128. The changed call order is a new prospective diagnostic,
not a change to benchmark interventions or the primary target.

Copy A4 prompt5 and prompt6 request bodies, with only the fresh ownership/model
alias replaced. Preserve messages and all decoding fields. Verify A4 artifact
hashes first. After guarded load, render/tokenize both using the same pinned
endpoints and require exact rendered hash, token-ID hash and counts8192/24576
against A4. Freeze both new request bindings before either generation. Any mismatch
stops before generation; no token search or alternate prompt. Generated text is
never executed. Persist response bytes, usage, finish reason, cache count, prefill
and decode times, wall time, allocator/pressure/swap/RSS and cleanup evidence.
Score literal DTR_READY separately from serving completion. A terminal noncompliant
response remains observed evidence, not a reason to retry.

Verify all four old PIDs absent before one new initial15-minute admission window.
Unchanged75% free, normal pressure, no foreign inference,12GiB disk; two qualifying
readings at least60seconds apart plus final prelaunch check. No self-renewal.
One server only; execution deadline600seconds from dispatch (including setup),
load and each generation at most180seconds. Guard all loaded tokenization with
an independent watchdog; preserve the1-second sampling and abort thresholds
(free<20%, adverse pressure, swap growth>512MiB, RSS>11GiB, foreign inference,
ownership loss and deadlines). Do not weaken gates or alter peer/cache state.

Create new immutable source/manifest/output paths owned by the remote worker.
Before launch, run existing relevant guard tests and deterministic fake regressions
for exact two-call order, copied prompt bindings, mismatch-before-generation,
no retry, deadline/owned cleanup, and no restart. Publish source before execution,
then actual supervisor/driver/model/watchdog handles and terminal raw artifacts.
Do not claim fake tests qualify process hooks. If admission expires, publish expiry
and stop; if call1 aborts, call2 is unattempted. No extra requests to obtain success.

## Continuation and holds

Continue setup, this bounded run and publication without waiting for another tick.
Return actual state; product goal status is separate. After terminal publication,
finish the already-authorized REQ-028B source/interface planning if incomplete,
without opening transport or acquiring Klear. Lead will review long-input timing
before releasing a specific sandboxed competence or transport step. No benchmark,
Klear download, VM, network listener exposure, model substitution or CONFIRM is
released here. No duplicate monitor, peer interruption or Lean changes.

Readiness55%, change0points, range45–65%. Remaining: competent fixed-target
comparison with valid inference; final empirical/manuscript synthesis; independent
reproducibility and author-approved submission package.
