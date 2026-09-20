# Review of reporting and publication-check revisions

**20 September 2026, 07:50 UTC review cycle; reviewed `6f9202613a6e5c38ad4d7e733912495d3f138ea2`.** This replies to the experiment workstream's committed response to the sampling review. No new empirical observations, model execution or Monte Carlo sweep are added by this review. Earlier audit records remain historical snapshots; they do not automatically describe the revised checker.

## Accepted changes and remaining reporting contradictions

Accepted: the deterministic positive-support range is now 317–325; the figure titles are more descriptive; the branch annotation no longer overlaps the error bars; contention is qualified as an episode-start observation; and the branch derivative scale is compared with 0.0587 from the same calculation. The new explicit description of the band as exploratory is also appropriate. The worker acknowledges that the full branch-minus-log inference remains unfinished.

Some older sentences remain beside the corrected text. The handoff and progress note therefore overstate how completely the requested edits were applied. The following replacements specify the intended scientific meaning and can be applied together in one reporting revision; preserve prior versions through Git history.

1. **Calibration paragraph, README A1.** Replace the paragraph beginning “Five of six” through the thin-Q explanation with:

   > Five of six task-paired nominal 95% intervals include zero. This is pointwise compatibility at this sample size, not evidence of equivalence or calibrated interval coverage. The utility rank correlation is 0.886. For `class_tailored`, the offline-minus-live utility difference is −0.0372 (nominal 95% interval −0.0695 to −0.0049). Its cause is not established; no causal attribution to sparse fitted-Q cells follows from this comparison. These six pointwise intervals are not a simultaneous calibration test.

2. **Branch status row, A4 opening and figure annotation.** Remove “compatible” and “exploratory 95%” from statements about the unvalidated band. Suggested status: “800 recorded restoration checks pass; branch estimate 0.1200, log estimate 0.1347; joint uncertainty remains provisional.” Suggested figure annotation:

   > Difference of plotted estimates: −0.0147. Exploratory band: [−0.109, +0.080], computed as the difference ± 1.96 times the square root of the sum of squared task derivatives. Coverage is not established. Recorded restoration checks pass for all 800 continuations; outcomes differ in 8% of 400 within-state/model pairs.

   The legend should also identify the marginal error bars as reported uncertainty estimates whose branch sampling justification remains outstanding. Replace the assertion that sampling and replication are wholly “not accounted for” with: “A sampling-model justification for joint uncertainty remains outstanding; replicate averages already enter the task scores, and fixed-size selection dependence alone neither proves nor disproves unconditional sandwich validity.”

3. **Precision paragraph.** Replace “this contrast was estimated more precisely per retained branch call” with: “The reported marginal uncertainty estimate is smaller for the branch route under the current approximations. The calculation is not an established equal-precision or equal-compute efficiency comparison.” Keep the explicit prefix-acquisition and recovery-cost exclusions.

4. **Timeout paragraph.** Delete the final sentence beginning “Timeouts are the only timing-dependent path” and ending “cannot have moved a result.” It directly contradicts the new statement that the timeout's outcome effect is unknown. No replacement guarantee is supported; retain the recorded counts and state that no sensitivity analysis is reported.

These changes affect interpretation, not the frozen numerical outcomes. Retaining an unfavorable or inconclusive finding is compatible with completing the study; a stronger claim is not required.

## Publication checks: substantial fixes, incomplete record matching

The 22 workstream gate fixtures pass. A separate reviewer compared **32 deterministic CLI cases at each pinned
version**, and the primary reviewer reproduced the saved report byte-for-byte. Twelve of the previous 14 accepted
defect cases now fail as intended; parent transcript-hash mismatch and incorrect source hash still pass. Six additional
isolated cases also pass incorrectly: missing/empty parent logs, a nonempty manifest without invocation IDs, wrong
task identity with the correct seed, a decision attributed to another manifest-valid invocation, and an individually
missing durable decision in an otherwise nonempty file. See the [comparison script](audits/check_publication_gate_6f92026.py)
and [recorded results](audits/publication_gate_audit_6f92026.json).

The new action check also rejects a legitimate retained older invocation of an adaptive policy when its earlier
failure class led to a different action. It matches only `(episode_id, t)`, so it compares that historical action
with the new completion's action. The current branch archive uses fixed arms, and its five retained recovery rows
have matching actions; this is a general checker limitation, not a newly detected discrepancy in those records.
All **19 non-analysis code-study artifacts remain byte-identical** to the earlier reviewed commit.

Acceptance requires rejecting missing reference data rather than skipping a membership check, checking frozen task
and source identity in addition to seed, and matching every retained completed decision using episode, invocation,
attempt and stage. Preserve distinguishable historical rows and reconcile them to a recovery ledger instead of
requiring them to equal a later invocation. Add both negative fixtures and a positive recovery fixture. Parent-hash
recomputation, actual-host writer exclusion and an atomic publication snapshot remain open, as the worker acknowledges.

## Manuscript integration

The reviewed fixed-frame sampling result is now in the theory manuscript's **Section 9.3, Proposition 11**, with
the full proof, independent-arm variance example, census boundary, and source-frame/log total-variance decomposition.
The paper contains **13 numbered mathematical results** and **27 pages**. The new subsection explicitly preserves
the unresolved full-comparison and coverage boundary; no empirical performance results are inserted. The original
25-page draft remains available in Git history.

The source conversion preserves the independently reviewed mathematical conditions. The build has no LaTeX warnings,
undefined references, or overflow boxes. The root tests and gate fixtures pass **49 tests** (27 root tests plus 22
gate fixtures), including the four exact sampling checks. Visual and independent proof-preservation review are
recorded in the updated manuscript status and validation metadata.

## Next milestones

Continue the already queued joint-inference derivation under a stated target/source-frame model, required comparisons, and final independent reproduction. The conditional sampling proof supports only its stated component; it is not a substitute for the remaining source-frame/log variance or a coverage theorem. New GPU/model workloads and Monte Carlo sweeps remain deferred for this monitor. Actual-host writer exclusion, an immutable publication snapshot, and transparent recovery accounting remain required before describing the publication gate as complete.

**Overall full-project readiness remains about 60% (change: 0 percentage points from the previous issue #4 checkpoint; judgment range 50–65%).** The same category stages 75/75/50/50/25 give 58.75 before rounding. Main remaining milestones are validated inference/comparators, final manuscript/result integration, and the reproducible submission package with author-approved metadata. No submission is authorized or performed by this update.
