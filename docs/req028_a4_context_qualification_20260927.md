# REQ-028A2R review and REQ-028A4 context qualification

Lead reviewed `05bfd08`. The admission supervisor actually dispatched at
03:20:21 UTC and exited at 03:20:27; an idle chat did not imply an active model.
Lead verified the admission/mechanics hash manifests and independently matched
both raw response contents and usage to their receipts. Qwen3-4B at 32k/f16,
batch128/ubatch32 completed two calls: 33/4 and 49/15 prompt/completion tokens,
0.318 and 0.578 seconds wall time, exact requested text/fence. Generated commands
were never executed. One healthy server and confirmed owned cleanup are recorded.
Calls3–4 were not attempted because immediate restart admission read68%<75%.
A3R was correctly skipped; no pressure abort or q8 comparison occurred.

The allocator log reports 4608-MiB KV and150.63-MiB Metal compute, rather than
the former unmeasured one-GiB compute estimate. These settings can serve short
prompts on this mini under observed conditions. They do not establish full-context
throughput, coding competence, deterministic restart or sustained capacity.
The A1/A2R difference cannot be attributed exclusively to batching: host state
also differed. An immediate post-release memory reading need not represent
steady recovered capacity; no peer blame or guarantee of reclamation follows.

## New bounded release: A4

Scientific purpose: distinguish a usable32k serving configuration from one that
only answers tiny prompts, while qualifying one restart under unchanged gates.
Reuse the verified model/runner, f16KV,32k, batch128/ubatch32, decoder/cache,
watchdog and source rules. No q8 stage, new downloads, benchmark, VM or transport.
Create a new immutable A4 manifest, source snapshot and output directory; do not
append to prior studies or count their responses as new observations.

Authorize exactly six logical calls, no retries:

1–2. The original literal/fence prompts, in original order.
Stop the owned server and confirm release. Allow up to180seconds for normal
resource recovery, sampling every15seconds; require all original admission gates
on two readings >=15seconds apart and a final prelaunch recheck. This waiting
counts inside the new A4's fixed900-second mechanics budget. Do not lower gates,
clear system caches, kill peers, or treat timeout as a successful restart.
3–4. Repeat the original two prompts after the one restart.
5–6. On that second server, two synthetic long-input controls at approximately
8192 and24576 rendered prompt tokens. Use the same system message and a user
message consisting of repeated literal `Neutral calibration text. ` followed
by `\nReply with exactly DTR_READY and nothing else.`. Determine repetition
counts deterministically with the pinned tokenizer/chat template, **before
generation**; select the smallest repetition count whose rendered input reaches
each target, allowing at most64-token overshoot and at least128tokens of context
headroom. Record full prompt, rendered-token count and hash. If exact rendered
tokenization is unavailable, stop before inference and report the missing binding;
do not substitute character counts. Output cap128tokens, temperature0, same seed.

Tokenization/template rendering during setup is permitted and produces no model
generation. Freeze counts and prompts before any A4 inference. Preflight tests
must verify six calls/order, no retries, restart recovery expiry, full common
history/template use, long-input token windows and output headroom. Source-bound
tokenization may use the existing runner/library; no new model or package needed.

One initial admission window of at most15minutes, readings every60seconds,
two passing readings before launch, unchanged >=75%/normal/foreign-job/disk
rules. This is a NEW one-shot A4 window, only after verifying all A2R supervisor,
driver/model/watchdog PIDs have exited. It cannot overlap the former window or
renew itself. At most900seconds execution after initial admission, per-request
and per-load180seconds; independent watchdog remains mandatory. Any pressure,
ownership or deadline failure ends this A4; no configuration search or fallback.

Report partial and complete outcomes alike. Primary infrastructure verdict:
all six requests terminal with valid token/context bindings, owned cleanup,
no resource violation, one restart qualified. Report literal/format accuracy,
long-input prefill and decode times, cache hits, observed allocations, pressure
and throughput separately; finite success here is not task competence or routing
benefit. A failed long call identifies a serving limit, not an empirical null for
the routing target. Keep initial admission/recovery/model times distinct.

Worker continues directly through authorized setup/run/publication in owned
remote paths, with owner Git identity. A4 completion opens a lead decision about
the smallest competent fixed-target DEVELOPMENT run, not an automatic CONFIRM
release. Product goal status is reported separately from actual execution.

Readiness **55%, change0points, range45–65%**. Remaining: competent fixed-target
comparison and valid inference, final synthesis, independent reproducibility and
approved submission package.
