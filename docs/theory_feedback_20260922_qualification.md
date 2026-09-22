# Qualification review — 22 September 2026, 03:19 UTC cycle

Reviewed worker `d3bf38877ca6cc188d038bc92bfbca08d8f39f72` and
`f1be616b408bb8b707ba7f253c1964337e226fbd` after lead `e360831`.
This is development qualification and deterministic retrospective review, not model evidence or CONFIRM.

## Evidence and verdict

**PROCEED with the remaining initial qualification queue.** Two of eleven new tasks are published; together
with the earlier Flask control, three of twelve selected tasks have records, two qualified and one diagnosed.
Matplotlib is worker-reported running. Matplotlib and the other eight outstanding tasks have no inspected completed records.

The [saved-record audit](audits/qualification_d3bf388.json), reproducible with
`python scripts/audit_qualification_d3bf388.py --output docs/audits/qualification_d3bf388.json`, passes 89 checks
against ten immutable source blobs. It independently reconstructs Astropy's 45 raw statuses: stock/reference
pass all 15 required tests; no-change passes 13 and fails two. This supports **task/image-specific qualification**.
It verifies the two adapter log hashes, M01 script pins and image/source consistency per task. Original container
execution is worker-reported and was not repeated by the lead.

**Django remains INCONCLUSIVE as an environment diagnosis and excluded as unqualified.** The inspected stock
summary reports 1,865 PASSED and five ERROR among 1,870 required tests; stock and adapter required maps agree.
The lead has not independently reconstructed that full required-test map. The audit does verify all five named
`generic_inline_admin` error tracebacks in each of stock/reference/no-change. Four fail to locate
`admin/change_form.html`; the deletion test fails to locate `admin/delete_confirmation.html` (correcting the
worker's all-five/change-form shorthand). Tracebacks load a newly installed Django egg. The broader test log
also contains other errors; five is the number of errors in the declared required subset, not the whole run.

This is evidence against an adapter-only fault and against treating the control failure as model inability.
It supports an environment/template lookup problem. It does **not** isolate missing packaged files versus an
import/template-loader path mismatch, mutable dependency drift, or an architecture/translation contribution.
No routing estimand, power, utility metric, learner restriction or theory failure can be adjudicated by this
reference-patch control. Preserve the unfavorable result; do not count it as an agent zero or change its tests.

## P1 DTR-REQ-002: answer to the image-provenance question

**Yes, perform one bounded, separate same-task provenance diagnosis; do not make the initial queue or the
already specified small DEV pilot wait for Django to qualify.** Keep the initial twelve-task frame and all
initial outcomes immutable. A later repair comparison does not silently add Django back to that pilot's frame.

1. First inspect the existing image/build records: record image digest and build scripts, Python/Django and
   dependency versions, imported module paths, presence/hash of both named templates in the checkout and
   installed package, and template search directories. Inspect both missing-file and wrong-search-path
   hypotheses. Do not edit the environment while establishing this baseline.
2. If the cause is not identified by those records, compare only `django__django-10097` against an available
   published `swebench/sweb.eval.x86_64.*` image. Resolve and record its immutable digest, architecture,
   source/base-commit and build provenance before use; a matching task name or `latest` tag alone is insufficient.
   Retain current dataset/evaluator/eval-script pins. If those identities cannot be established, report that
   limitation and stop this comparison rather than silently selecting a new evaluator.
3. Within the worker’s existing author authorization, control execution uses a new diagnostic directory, identical reference/no-change
   rules and the existing 1,800-second per-control cap, with at most one alternate-image stock/reference/no-change
   triplet. Coordinate CPU/VM use after the current serial queue or in an acknowledged quiet-window plan; no new
   model inference is requested. No repeated rebuild search or all-500-image download is requested.

Acceptance: a provenance table distinguishes the two hypotheses, or explicitly leaves them unresolved. If an
alternate image is executed, retain every raw log and all required statuses: reference and stock must agree and
pass all 1,870 required tests; no-change must have all 1,432 P2P passing, every F2P status PASSED/FAILED and at least
one F2P failure. Failure remains a diagnosis. Even a successful alternate is a new runtime-specific qualification,
not proof of the local root cause or permission to replace the initial pilot frame.

## P1 DTR-REQ-002: repair review

Independent read-only review accepts the original stale-cache fix and tested restart behavior. Nine focused
fixtures pass (five grading/restart, four workspace); no evaluator/container/model run occurred. Distinct
immutable episode/patch IDs, no-clobber and patch/report equality address the original contamination risk;
completed records are skipped and interrupted directories preserved in the tested cases.

**REPAIR before the relevant next use:** the pinned evaluator writes `patch.diff` only after container startup.
A deterministic mocked early failure leaves predictions but no grade record because `accept_report` raises on
missing patch; preflight then refuses the same attempt. Preserve an explicit `unknown_evaluator_failure` record
with original episode/submission identity and diagnostics for this path. Keep actual patch mismatches refused.
Any allowed retry gets a distinct attempt ID tied to the identical patch, with the original attempt retained and
the existing one-retry limit. Acceptance: mocked pre-container failure produces a durable unknown record; no
resolution is inferred, no output is overwritten, and an identical-patch retry cannot consume stale logs.

Two further boundaries were independently confirmed with temporary fixtures:

- **Before pilot grading:** hash/image mismatches currently enter the same catch as ordinary empty/non-Submitted
  episodes and are written with `operational_resolved=0`. Those are integrity refusals, not observed model failures.
  Record `grade_valid=false`, an explicit reason and a null/unknown grade; aggregators must not silently count them
  as valid zeros. Preserve the prespecified zero treatment of genuine empty/non-Submitted episodes. Acceptance:
  hash mismatch and image mismatch yield durable invalid/unknown records, while the genuine operational cases
  retain their declared classification. Keep evaluator failure reasons separate from both.
- **Before any actual qualification restart/frame freeze:** `task_state` accepts a matching-ID-only JSON,
  a `status=running` record and a record naming the wrong evaluator as completed. Require a terminal qualification
  or diagnosis record and matching expected manifest/source identity before skipping or admitting a result to the
  frame. Valid unsuccessful diagnoses must also be skipped, without replacement. Existing legacy outputs can be
  linked by an independently checked immutable hash manifest; do not rewrite them. Acceptance: incomplete record
  remains incomplete, wrong source conflicts before execution, and valid terminal success/failure preserve hashes
  and execute no controls. This extends validation of completed records; it does not invalidate the tested
  no-clobber/skip mechanism.

These are corrections before subsequent grading/restart, not an instruction to interrupt the currently running initial qualification batch.
The accepted fixed-backend Coder 7B/14B pilot in `e360831` remains the next scientific experiment once its stated
frame, model/resource and shared-host gates pass; no new lead permission is needed.

## Coordination and readiness

Worker publication at 03:06/03:10 is observed; the nominal :13/:43 cadence is not an exact-delivery claim. The
03:10 committed reply acknowledges the pilot and repair requests. No new ICLR reply follows the lead's 02:57
release relay as of this review. REQ-004 is completed on DTR's reported side; receipt remains pending. Do not
infer host ownership or slot availability from silence or start a duplicate job.

No manuscript claim or PDF changed in this cycle. **Readiness 55%, change 0 percentage points, range 45–65%**,
under the unchanged rubric. Actual advance: one additional qualified runtime task, an inspected negative control
result and actionable diagnosis/repair decisions. Remaining: useful validated inference and adequate real-agent
comparisons; final empirical/manuscript synthesis; independent reproducibility, author metadata and submission
package. Acknowledge REQ-002 substeps and REQ-004 with accepted/running/completed/blocked states and exact artifacts.
All new commits use Yukang Zeng <ykzeng2019@gmail.com> as author and committer, direct main; preserve archives.
