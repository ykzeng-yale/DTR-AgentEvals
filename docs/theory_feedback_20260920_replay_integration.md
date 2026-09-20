# Replay controls and manuscript integration

**20 September 2026, 11:15 UTC review cycle.** Reviewed
`8ab7fb577cb3879b706ebc0c931517e0bfca4ae7` and the committed experiment-agent reply after `d13d5a5`.

## Accepted repairs

The revised A5 README now uses the same five deterministic policies for the headline summaries, reports later
fallback, distinguishes visible validation from hidden-test success, and withdraws the statistical-null and
short-horizon explanations. These are substantive reporting repairs. The dated post-hoc specification and saved
donor diagnostics make the analysis easier to reproduce. This remains a descriptive comparison against finite
live estimates, not a prespecified known-truth simulation or evidence of equal accuracy.

The eight new fixtures exercise donor choice, stopping, fallback and stochastic thresholding. They pass under an
environment with the experiment dependencies; the repository's minimal root environment lacks pandas and cannot
collect this suite by itself. The workstream's reported 73-test run is separate from this review's 30 passing root
tests and the eight inspected replay fixtures. Preserve that environment distinction in reproduction instructions.

The fixture called an adaptive negative control uses a single donor and missing-prefix fallback. It checks the
implementation's behavior but supplies neither a live-policy value nor the no-fallback failure in the theory note.
The separate [pinned audit](audits/check_replay_controls_8ab7fb5.py) bridges that gap by exercising the production
function on exact known-value controls; its [report](audits/replay_controls_audit_8ab7fb5.json) records the scope.
This does not replace the broader planned operating-characteristic study.

The primary reviewer reproduced **71 audit checks with zero failures**, including agreement of the saved donor
diagnostics and five-policy summaries with the prior independent reconstruction. All **19 non-analysis artifacts**,
the per-policy comparison CSV and the replay-rule implementation are unchanged. Eight equally weighted triples
\((U,A,U')\) encode the current donor and first later opposite-action donor after rejected rows are integrated out;
they are not two unconditional iid donor rows. Calling the pinned production function for three targets gives
24 exact evaluations with no fallback: adaptive mean 3/4 versus truth 1, and each constant second-action mean 1/2
versus truth 1/2. The check executes reviewed pure functions extracted from source, without experiment imports.

## Theory now in the paper

The reviewed [replay note](theory_replay_boundaries.md) is integrated into **Section 8.2, page 14** of the
**28-page manuscript**. Section 8.1 distinguishes copying an outcome from recomputing a reward with a frozen state.
Section 8.2 proves that an adaptive target has value 1 while the specified donor replay has mean 3/4, even with
an unlimited ordered iid donor bank and no missing prefixes. The donor order is fixed before observing records.
In the same toy, constant second-action targets have value and replay mean 1/2. These are scoped constructions,
not empirical estimates or a new general replay-validity theorem.

The prospective empirical plan now requires both positive and adaptive-negative known-value controls and makes
clear that replay need not perform worse on every benchmark. Independent mathematical review confirms proof
preservation. The build retains 13 numbered results, 21 cited references, 82 unique labels and 56 symbolic
references, without undefined references or LaTeX warnings. All 28 pages were rendered and visually reviewed;
the final donor-order wording changed only page 14, which was rechecked. Empirical performance results remain
outside the paper. Source/PDF hashes and the previous delivery are recorded in `manuscript/validation.json`.

## Remaining coordination requests

1. **Maintain the corrected replay specification and controls.** Promote the archived production-function exact
   controls into the workstream's normal regression suite if desired. Clarify that `rule_b` expects donors sorted
   by run index; the normal `by_task` caller supplies this order. Replace residual module labels such as
   “DELIBERATELY INVALID” and “hold-the-future-fixed” with the specified operation names, and label legacy JSON
   `bias` and `stitching_engages` fields as discrepancies and logger continuation. Keep explicitly suffixed all-six
   summaries separate from five-target headline comparisons. Acceptance is coherent source/reporting terminology
   and reproducible controls, not a particular observed ranking.
2. **Prioritize the unresolved inference and provenance work.** The original target-preserving branch comparison
   still requires its full sampling model and source-frame variance contribution. Publication-gate acceptance is
   unchanged from the [earlier review](theory_feedback_20260920_integration.md), including valid historical recovery,
   required parent/source evidence and atomic publication. A5 repairs do not close those separate requirements.
3. **Queue later empirical validation and final integration.** Competitive-router comparisons and repeated-dataset
   operating-characteristic work remain deferred for this monitor. Resume with the agreed acceptance criteria when
   capacity permits; then independently reproduce final analyses, integrate results and finalize author metadata
   and the submission package. No new GPU/model, candidate-code execution or Monte Carlo work was launched here.

**Full-project readiness remains about 60% (change 0 percentage points; judgment range 50–65%).** Unchanged
25/20/30/15/10 weights and stages 75/75/50/50/25 give 58.75 before rounding. Verified reporting repairs and theory
integration advance existing milestones; valid joint inference/comparators, complete result integration, and final
reproducibility/metadata/packaging remain the three largest gaps. The score is independent of the direction of the
replay comparison and does not imply submission or acceptance.
