# REQ-005 component review and integration decision

**23 September 2026 UTC; reviewed worker commits `2874246`, `ee9a4bc`, `1ae7cb5`, and
`22c4a82040700ded7fd54ffbf14d9001b2f089c2`, after lead `3cbd524`.** This review concerns
new deterministic instrumentation and retrospective fixtures, not completed cue experiments.
The latest inspected worker host checkpoint is 06:20:32 UTC (commit 06:22:26); no continuous
:13/:43 delivery or current host state is inferred. Intermediate scheduled reviews are not
claimed completed. GitHub issue discussion and open PRs were checked; no open PR was observed.

## Decision

**PROCEED with new `cue-v1` driver/queue integration and deterministic transport/cleanup fixtures
now. Do not wait for another design-permission round. HOLD only the first live comparison until
its integrated source binding, deadline/transport fixtures, coding guide and current host
conditions are reviewed.** The helper modules are not a runnable experiment, and helper test
counts do not establish live readiness. No lead model, container, server, hidden evaluator,
resampling or Monte Carlo job was executed.

The exact 290-byte cue, AAA/ABABAB detector, one-cue maximum, silent baseline landmark and
12-assignment B,C,C,B,B,C frame are accepted in their isolated scope. The planned list/order,
H24, two physical attempts per logical call, 576-request cap, model/context/temperature pins,
Submitted-only endpoint and no-replacement rule remain the lead's choice. The comparison stays
fixed-order descriptive DEV on deliberately selected exposed tasks, not a causal effect estimate
or confirmation. No positive outcome is required for accepting its complete records.

REQ-002's correction overlay is accepted. The sklearn reproducer was executed and failed; a
nonzero return does not imply it never ran, nor does execution establish a successful test.
The manuscript already distinguishes ad hoc testing from an invoked repository test runner;
no new paper edit or mathematical claim is needed for this acknowledgement. REQ-004's peer
window is historical: the worker reports inspecting process start/exit, while peer counts and
authorization remain peer-reported. Neither is lead observation of the current machine.

## Material findings and corrections

1. **Logical-call alignment:** assistant-message ordinals are not logical call IDs. The original
   adapter omitted three FormatError calls and five final context-rejected calls. Independently
   reconstructed archives contain 682 logical calls and 674 saved assistant actions. There are
   ten incomplete detector records, not two. First-trigger totals remain 21/32 (AAA 12, ABABAB 9),
   but legacy SymPy/large triggers on logical call 22, with candidate delivery 23, not 21/22.
   `A,A,FormatError,A` must break AAA adjacency. The corrected adapter uses explicit error events
   and episode/attempt evidence, refusing inconsistent or ambiguous alignment; runtime must use
   the driver's authoritative logical IDs. The [additive correction](req005_fixture_landmarks_correction_20260923.json)
   preserves the original fixture output as historical evidence. These remain would-trigger
   landmarks; zero cues were delivered and they are not an estimate of intervention benefit.
2. **All-exit capture:** a regular-file check followed symlinks despite declared exclusions, and
   an untracked-list header could claim bytes while an empty body was treated as no-change.
   The repair rejects symlinks and missing/inconsistent list bodies. A malformed destination
   must become a recorded capture failure rather than escape the cleanup wrapper. An absent or
   failed measurement stays unknown, not empty. These are diagnostic correctness fixes, not
   changes to submission eligibility.
3. **Receipts:** an error-reporting callback could raise and replace the actual dispatch result;
   completeness inspected filenames rather than validated content. Repairs preserve the original
   model exception/success, separately record callback failure, and validate request/outcome/raw
   identity links before declaring completeness. Quoted credential assignments are now included
   in redaction fixtures. Sanitization remains a documented transformation, not a promise that
   arbitrary secrets are always detected; publication review remains necessary.
4. **Remaining integration gates:** a helper accepting caller-supplied bytes does not prove those
   bytes reached the model transport. A timeout checked only before an injected callback does
   not bound a hanging callback. `TOTAL_BUDGET_S=300` is not accepted for live capture inside the
   existing 120-second cleanup allowance. These are resolved by the explicit binding below,
   not by additional passing standalone helper tests.

The component repairs are source changes reviewed with deterministic regression tests. Frozen
`pilot_episode.py`, `pilot_runner.py`, `pilot_cohort.py`, grader and all published result archives
stay unchanged. Root verification passed **345 focused tests, one pinned-runtime fixture skipped**, plus **37 root
tests**. Independent code/scientific review accepted the bounded repairs and integration choices.
Current validation details and source digests are in
[audit/validation](audits/req005_component_review_20260923.json).

## Answers to the worker's open items

### 1. Storage and published projection volume: bounded publication is selected

Preserve the **complete exact prepared HTTP request body privately** before each physical dispatch,
with its SHA256 and byte length. It must be the actual body passed onward to the same transport,
not a separately serialized approximation to `messages`. Do not persist authorization headers.
For this small DEV cohort use a per-body cap of **8 MiB**, a cohort raw-body reservation of
**4.5 GiB** (576 × 8 MiB), and **6 GiB free space above the existing host reserve** as the start
preflight. Recheck space before each write. Keep trajectories/server logs/other files separately
accounted; 6 GiB is an allocation decision, not a guarantee that all process storage fits.

For public receipts, canonicalize the sanitized payload and retain its complete SHA256/byte
length. If it fits **64 KiB**, publish it whole. Otherwise publish at most a **32 KiB head plus
32 KiB tail** with original offsets, explicit truncation/unavailable fields and hashes of the
actual published representation. Never describe a preview as the complete request. Treat UTF-8
boundaries/JSON escaping explicitly and enforce a **128 KiB serialized public request-receipt
cap** including metadata. Bound transformation metadata with omitted-entry counts; account for
JSON escaping and multibyte characters in the final encoded size. If necessary omit the preview
entirely with the reason and preserve compact identity, raw/full-sanitized/published hashes and
lengths. Apply the same **128 KiB final serialized cap to each outcome record**, bounding error
detail explicitly while preserving outcome identity, usage availability and request links. Apply redaction before excerpting. No private paths or raw files are
published automatically. A digest of a private body remains worker-reported to a public reader.

These bounds are not a token estimate. A bounded retrospective measurement of 674 serialized
trajectory prefixes gives a maximum 366,238 bytes and 100 prefixes over 64 KiB, so full unbounded
public duplication is unnecessary. Those prefixes are a storage proxy, not exact wire bodies or
a guarantee about future requests. All dispatched private bodies, including model-rejected requests, remain
available for later worker-local diagnosis. An oversized body refused before dispatch is recorded
by digest/length/refusal only; it does not evade the storage cap. The response context/H24/model limits are unchanged.

If a body exceeds its cap or a durable pre-dispatch write fails, **do not truncate the actual
request or dispatch it without its receipt**. Record a measurement/storage refusal, no physical
request, and no automatic model retry. Stop new queue dispatch while storage integrity is
unresolved; preserve the affected and remaining assignment states explicitly. This is a
predeclared infrastructure stop, never an outcome-driven stopping rule.

### 2. Post-dispatch bookkeeping failures: nonfatal, with incomplete evidence retained

Accept preserving a successful model return or original model exception after a failed outcome
write. The callback itself must also be exception-safe. Persist a compact secondary error log
where possible, but do not fabricate usage, repeat a physical request, or promote an invalid
outcome file to complete. Classify the episode's receipt integrity separately from its observed
operational outcome. Unresolved receipt holes preclude a complete-telemetry claim and continuation
of the queue until storage/integrity is reconciled; they do not erase the observation or imply
zero usage. A sealed file alone is insufficient if its identity/link disagrees with the request.

### 3. Broad sanitization and 4. retrospective trigger rate

Broad masking is acceptable if its transformations and withheld/truncated fields are explicit
and the full raw body stays private. The quoted-assignment regression closes an identified
omission, not every possible secret pattern. Publish a projection, not a raw-equivalence claim.
The 21/32 trigger total is accepted after alignment repair only as a retrospective implementation
fixture. It supplies no power justification and no expected cue-success rate.

## Concrete integration contract: DTR-REQ-005 stays running

Worker owns implementation in **new** `cue-v1` episode, queue and admission sources. No edits to
the frozen yaml-v1 drivers. No actual model/container work is required to complete this step.

- **Model-visible intervention:** use authoritative logical IDs including parse failures and
  rejected queries. Feed exactly one complete or incomplete record per logical call. Insert the
  cue only before the next permitted logical query after a trigger. In baseline record the same
  would-trigger landmark silently. Failed format parsing interrupts adjacency; physical retry
  of one query does not consume a second logical cue. Distinguish message appended, transport
  attempted and response received. No-next-call/early-exit cases stay explicitly undelivered.
  A pre-dispatch storage refusal after insertion is not delivery to the model.
- **Transport:** intercept the finalized request body at the pinned client's actual outbound
  transport boundary, persist it, then pass those same bytes to the existing sender. Keep URL,
  model fields, generation settings, response parsing and retries unchanged. Mock the transport
  to compare receiver-observed bytes with the retained body for both arms, a retry and a
  context/error response. A wrapper around `super()._query(messages)` plus independent
  `json.dumps(messages)` is insufficient. The actual pinned SDK path must be demonstrated;
  the lead does not assume a particular SDK's transport signature.
  Account for or disable hidden SDK retries/redirects; every physical send consumes its own
  receipt and request budget. Refuse streaming/nonreplayable bodies before sending unless they
  are bounded-buffered once and those exact bytes are passed onward.
- **Endpoint then diagnostic then cleanup:** determine the frozen Submitted-only submission
  artifact first. Run the diagnostic separately on every terminal path, including timeout,
  with an independently enforceable **30-second maximum** inside the existing cleanup window.
  Anchor the phase deadline to `min(actual_inference_end +120 seconds, existing_absolute_cleanup_cap)`;
  an early-finished episode must not inherit unused inference time as extra diagnostic time.
  Retain at least **90 seconds for cleanup**; each diagnostic subprocess timeout is the minimum
  of remaining diagnostic time, time to the absolute cleanup deadline minus 90 seconds, and 60 seconds.
  Skip diagnostics with an explicit unavailable/timeout reason when no time remains. The
  executor must actually enforce that timeout and cleanup must run in a `finally` path, even
  after receipt/capture errors. Do not use the helper's 300-second default or silently enlarge
  episode/block/cleanup deadlines. An uncooperative subprocess must be bounded by the supervisor,
  not trusted to return voluntarily. Cost accounting includes diagnostic time separately.
- **Frozen admission:** bind every new/imported execution module, cue/definitions/coding guide,
  assignment plan, original model/conversion/image/YAML/evaluator pins, settings and deadlines.
  The registry alone does not bind these. Validate the entire fixed queue before launch and
  every resume. Keep 12 assignments / 576 physical requests total across resumes, one cohort, no
  duplicate replacement or outcome-driven extension. Require a new unique output namespace;
  neither a legacy result nor a projection report can satisfy runtime admission.
- **Acceptance artifact:** exact source manifest and integration test output; assert unchanged
  model-visible baseline messages/body and Submitted-only endpoint bytes against the pinned
  reference, cue-arm difference only at the prescribed insertion, correct parse/retry/horizon
  boundaries, hung-executor deadline control, capture-error cleanup, storage refusal before
  dispatch and corrupt-receipt detection. Use a stub sender and disposable temporary Git trees,
  never benchmark-generated code outside its sandbox. Freeze the [visible-evidence coding
  guide](req005_visible_evidence_guide_20260923.md) before collection.

**Next discriminating step:** implement and publish this integrated no-model fixture package.
No new scientific choice or user permission is needed for that reversible preparation. Live
release remains held specifically for inspection of this artifact and fresh host agreement;
that is not a blanket block on another workstream. Once reviewed, the next scientific test is
still the prescribed baseline-versus-one-cue comparison, not more retrospective classifier work.

**REQ-004:** the 06:15–07:45 window has ended and the worker's release record is inspected.
Before any later authorized block, refresh peer ownership/resource checks; do not use the old
06:19 release as proof of current availability. Do not stop peer jobs or purchase compute.

Worker: acknowledge **REQ-002 completed correction**, **REQ-005 running integration**, and
**REQ-004 completed historical window / fresh check required**, with accepted/running/completed/
blocked/superseded statuses and the next observed publication slot. Link already completed
work rather than duplicating it. Both new commit identities must be Yukang Zeng
<ykzeng2019@gmail.com>, verified before push and attributed to `ykzeng-yale` afterward.

## Paper/readiness

Theory and the 38-page manuscript are unchanged this cycle. No new outcome or theorem was added.
The accepted evidence is deterministic component behavior and corrected historical call alignment;
end-to-end experiment readiness and empirical benefit remain unvalidated.

**Full-project readiness 55%, change 0 percentage points, judgment range 45–65%.** Weights 25/20/30/15/10
and category stages 75/75/50/25/25 remain unchanged. Top three remaining milestones: useful
validated inference and adequate real-agent comparisons; final empirical synthesis/statistical
consistency; independent reproducibility, author-approved metadata and submission packaging.
