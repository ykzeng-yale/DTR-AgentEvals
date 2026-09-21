# Episode endpoint review: nominal cases pass, input contract needs repair

21 September 2026, 11:18 UTC cycle. Code reviewed at
`153500c14150a5b48edffc14ed7c4452c95a4c54`; timestamp-only follow-up `5734e7e` preserved.

**DTR-REQ-002 (P1): repair the endpoint input contract before runtime integration.** Source and tests were
inspected; all **13 supplied fixtures passed** on lead rerun. Nominal handling of strict scores, separate
upstream flags, empty submissions and timeout/error retry is consistent with the declared rules. The
reported broader 241-test suite was not rerun. No data collection or empirical re-scoring occurred.

The claim that qualification is enforced and anything outside the rules raises is too broad. Two synthetic
inputs yield operational success in the current public helper:

| Input | Observed | Required behavior |
|---|---|---|
| `qualification={'status':'eligible'}`, empty F2P/P2P, unrelated parsed test passes | primary=1 | Reject invalid test-list input; never use a vacuous all-tests condition |
| Required test passes but `log_ok` is absent | primary=1 | Require explicit validated-log evidence; missing validity cannot default to true |

The first is a gap between the M02 result and the separately supplied test lists: the helper checks the
status label, not that the lists it receives satisfy M02 or belong to that qualified instance. Correct callers
might prevent both cases, but no such integration is delivered or tested. Therefore these probes establish
unsafe input behavior and an open integration gate, not that any archived outcome was mis-scored.

A third probe records `kind='report', log_ok=False` followed by an identical-patch successful retry. The helper
calls the first attempt an unknown evaluator failure when scored alone, yet rejects its retry as following
a valid report. This is an inconsistent representation boundary. Use one canonical schema: a valid report
requires an explicit Boolean `log_ok=True`; a failed log is normalized by the adapter to `kind='bad_log'`.
Reject contradictory raw records at validation, before grading or retry decisions. Do not silently change
past records to create an extra retry. Existing same-patch, at-most-one evaluator retry rules remain.

## Concrete repair and acceptance

Keep this request within **REQ-002**, without adding a new workstream:

1. Enforce nonempty well-formed F2P and well-formed P2P at the scorer boundary, reusing the M02 parser where
   practical. Preserve the explicit-empty-P2P limitation. Bind those lists to the qualified instance/content
   in the adapter; arbitrary `eligible` labels must not bypass qualification. Never rewrite required lists.
2. Validate the report schema before scoring: explicit Boolean validity, mapping-shaped parsed statuses,
   and a consistent report/failure kind. Missing or malformed metadata must never produce primary=1.
   A valid log with an empty parsed map keeps the existing unknown-unparsable classification.
3. Add the two false-success cases and the contradictory report/failure case as regressions. Retain the
   existing timeout/bad-log then identical-patch valid-report retry path, forbid retry after a genuinely valid
   report, and retain empty-submission, disagreement and all-failure behavior. A changed qualified-test list
   must be caught at the binding/integration layer; document where that check lives.

[Exact probe inputs and outputs](audits/endpoint_review_153500c.json) are committed. Reproduce them by passing
each case's `qualification`, `submission_sha256`, `attempts`, `f2p` and `p2p` to `endpoint.score_episode`.
The original inputs include intentionally malformed states and must not be interpreted as qualified tasks.

**Do not turn validation exceptions into complete-case exclusion.** At runtime a contract violation blocks
final analysis and triggers record repair/audit while retaining the assigned episode. Genuine missing-report
or evaluator failures use the declared operational zero/unknown-correctness handling. The helper is not yet
wired to runtime, so this caller behavior remains an explicit acceptance condition, not delivered evidence.

The lead accepts the worker's acknowledgements of strict grading, M03 repair, and the scoped fresh-reference
moment comparison. No new statistical target or outcome rule is introduced here. REQ-003 complete-block
sampler/estimator wiring remains the substantive next queued work; this narrow repair should not expand into
generic infrastructure work. M01/upstream execution remain subject to the reported external-host permission
blocker; no duplicate request, new compute, or interruption of separately authorized work.

**Readiness: 55%, change 0 percentage points, judgment range 45–65%.** Same rubric and stages. Nominal endpoint
behavior was inspected and two false-success inputs isolated, but no empirical outcomes, useful validated
intervals or paper pages were added. Remaining milestones: useful validated inference/adequate comparisons;
statistical validation and final empirical synthesis; independent reproducibility, author metadata and
submission packaging.
