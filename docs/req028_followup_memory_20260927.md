# REQ-028A lead review and bounded memory discriminator

Reviewed worker `bc1824b`. All 18 mechanics artifact hashes and seven source
hashes match; the lead independently ran the two pure guard tests (passed).
These checks do not independently replay the host or model. The healthy server
reported one 32,768-token slot. One inference request began and disconnected
after 0.645 seconds; no response or generated-token receipt completed. The
watchdog observed pressure level 2, free metric 20%, unchanged swap and owned
RSS 4.568 GiB, then confirmed owned server release. Calls 2–4 were not attempted.
Accept this as an interrupted real-model serving attempt, not successful
inference, competence evidence or a blanket finding that the mini cannot serve.

The initial setup watchdog lost identity across a Python launcher exec. Preserve
that gap, its repair and subsequent integration tests. The inference watchdog
did run and trigger. A passing small fake test is not complete systems assurance.

## Diagnosis before more compute

The lead's provisional one-GiB compute allowance was not measured and did not
adequately predict total system memory. Source/help shows default logical batch
2048 and physical microbatch 512; both were left implicit. The log lacks detailed
KV/Metal/graph allocations. Potential causes include the fixed 4.5-GiB f16 KV,
graph/batch buffers, Metal allocations absent from RSS, and system occupancy.
No foreign inference was recorded and swap did not increase: evidence does not
support blaming a peer task or claiming swap exhaustion. Pressure was already
near the guard immediately after loading; the first short prompt alone is not
evidence of an excessive input history.

The next discriminator keeps the model, context and prompts fixed and reduces
the explicitly declared batch envelope. If pressure still fails, a separately
labelled q8 KV candidate can test the known KV contribution. A successful q8
candidate would define a changed execution kernel, not validate the prior f16
configuration. No guard threshold is weakened.

## Released execution: REQ-028A2, with conditional REQ-028A3

Reuse verified assets; no new model download. Preserve original source snapshot
and all run artifacts. Create new owned implementation paths or a versioned
driver; never overwrite or rerun into `mechanics_20260927`.

**A2:** same pinned runner/model, 32,768 context, f16 K/V, one slot, disabled
prompt caching, flash attention on, original four prompts/order/restart and
decoder. Explicitly set logical batch 128 and physical microbatch 32. Enable
runner verbosity sufficient to retain model/KV/compute/Metal allocation details,
and record effective settings, including the runner's uint32 seed representation
(`20260927028 mod 2^32 = 3081057844`). Keep raw output and token receipts. Never
execute generated text. This is a new batching configuration, not guaranteed
bit-identical output or timing to A1.

**A3 is preauthorized only if A2 terminates for the same measured resource
pressure condition with owned cleanup confirmed:** use the identical A2 settings
except K and V cache `q8_0`. Keep 32k context. Its nominal KV allocation is
4.5 × 34/64 = 2.390625 GiB; the 2.109375-GiB nominal reduction is an estimate
to compare to observed allocator logs, not a guaranteed system saving. Freeze a
separate manifest before A3, retain both failures and do not select favorable
responses retrospectively. If A2 completes, do not run A3. If A2 has another
failure (source, protocol, watchdog, ownership), diagnose/report without A3.

Each configuration has at most four logical calls, no request retry, 180 seconds
per load/request and 15 minutes total. Maximum two configurations/30 minutes,
same admission, one-second pressure monitoring, swap/RSS/free/disk aborts and
peer isolation as REQ-028. Keep at least 60 seconds of normal-pressure recovery
before the conditional A3 admission; no repeated waiting for unavailable capacity.
No Klear acquisition, VM, tunnel, benchmark episode, endpoint change or CONFIRM.

Before execution, test new conditional dispatch and exact CLI settings using
fake outcomes: A2 completion skips A3; pressure+confirmed cleanup permits A3;
other failure or unconfirmed cleanup forbids A3. Verify watchdog remains alive
immediately before each request. Archive original source snapshots, assert pins
and freeze new source/config hashes. Worker may repair implementation defects
within these exact contracts but must disclose any execution deviation.

Report setup/running/completed/failed distinctly, actual process handles, literal
responses, compliance, measured allocations, pressure and timings. Continue the
existing experimental objective; this new release removes the prior lead-decision
block for these stages. Report actual `/goal` status honestly: messaging can
dispatch work even if the product goal remains marked blocked. Do not mark the
overall scientific objective complete after mechanics qualification. Lead will
review the next milestone and choose the benchmark/transport design.

Readiness **55%, change 0 points, range 45–65%**. Largest milestones remain
competent fixed-target comparison with valid inference, final synthesis, and
independent reproducibility with an author-approved submission package.
