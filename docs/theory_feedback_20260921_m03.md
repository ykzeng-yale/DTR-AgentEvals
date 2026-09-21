# M03 grading decision and reset-checker review

21 September 2026, 10:19 UTC cycle. Reviewed worker commit
`bfed7e1a6f99fa00d9e2278abcb996021f6a5319`. This is prospective endpoint clarification and deterministic
qualification review; no model, evaluator-container or Monte Carlo execution occurred.

## Scientific decision: strict verified resolution, with upstream scores preserved

**DTR-REQ-002 (P1): accept the declared grading rule as the study-specific primary operational endpoint.**
Re-grade from the parsed status map against the original declared required-test lists: every F2P and P2P
test must be observed `PASSED`. M02 must run first; empty F2P is ineligible, while explicitly empty P2P
retains its documented limitation. The grading helper alone does not enforce those input preconditions.

Answers to the worker's two questions:

1. **SKIPPED:** do not count a required skipped test as verified success and do not exclude an assigned
   episode/task because of that outcome. Retain it as zero operational resolution, with the observed status
   and reason. Pre-sampling evaluator qualification may reject an unusable task/image combination based on
   prespecified no-change/reference-patch controls, with reasons and denominators; never select tasks on a
   candidate routing policy's results. Diagnose platform or dependency failures before declaring exclusion.
2. **XFAIL:** also does not meet the strict observed-pass rule, for either F2P or P2P. This is a declared
   measurement choice, not a claim that expected-failure semantics are universally erroneous. Keep the
   pinned upstream resolution report/score separately, identify this endpoint as strict verified resolution,
   and report disagreements. Do not describe it as directly interchangeable with the official benchmark score.

Use the identical mapping for randomized logs, fresh policies and evaluator controls. Preserve status maps,
required lists, raw logs, original reports, patch/invocation identifiers and both scorer versions. Evaluator
failures/empty unparsable output remain zero on the operational endpoint and unknown algorithmic correctness;
do not silently convert them into observed test failures or drop them. Existing identical-patch retry and
secondary worst-case bounds remain unchanged. A non-pass label is not proof that the proposed code is incorrect.
No archived result or CONFIRM endpoint is re-scored by this prospective clarification.

The source-derived discrepancy explanation is supported by re-reading the previously pinned
[upstream grading source](https://github.com/SWE-bench/SWE-bench/blob/f7bbbb2ccdf479001d6467c9e34af59e44a840f9/swebench/harness/grading.py):
`test_passed` accepts XFAIL; `check_pass_and_fail` places SKIPPED in neither success nor failure;
empty report denominators score one. The saved source SHA-256 was reverified as
`88fc500ebaf692a53457149cec24dcf82dfa2d48f98021a894a087d275f61df4`.
This establishes the code path for the synthetic status maps, not its frequency in the real dataset or
end-to-end parser conformance. No upstream code was executed in this review.

## Validation verdict: repair the reset checker before accepting that gate

The lead inspected both implementations and reran `experiments/tools/test_v2_m03.py`: **18 passed**.
The worker's broader 214-test result remains reported, not rerun. Grading-fixture implementation is accepted
within its synthetic-input scope; actual parser/grader conformance and M01 remain open.

Two deterministic adversarial probes expose false acceptance in `check_reset_commands`:

- For a patch adding `tests/new.py` and modifying `tests/old.py`, checking out only the old file before
  patch application and removing only the new file after output returns no problems. The global path union
  is correct, but neither phase has the complete required reset set.
- Complete reset sets with `END_TEST_OUTPUT` before `git apply` also return no problems. R4 checks for some
  reset on each side but never requires the application to precede test completion.

The complete, correctly ordered positive control also passes. Commands were treated as strings, not executed.
[Exact inputs and observed outputs](audits/m03_review_bfed7e1.json) preserve all three probes against the worker
commit. This is an implementation defect in a qualification checker, not a failed routing experiment or
evidence against DTR identification.

**REQ-002 next discriminating check: repair R2–R4.** Check modified-file checkout coverage and new-file removal
coverage separately before application and after test completion. Require application before completion and
fail closed on missing or ambiguous phase markers under the supported generated-command grammar. Reject
resets touching unrelated paths. Add both failing probes as regressions, retain new-only and mixed positive
controls, and report unsupported path/command syntax explicitly rather than claiming general shell safety.
Acceptance: both bad cases rejected, both phases complete for accepted cases, existing no-bare-checkout and
unrelated-setup protections retained. Later M01 must apply the checker to actual pinned generated scripts;
isolated execution controls must establish actual setup preservation. Static checking alone cannot do that.

The reported external-host permission blocker for M01/upstream conformance remains unresolved here; no
duplicate permission request is issued. Acknowledge REQ-002 running/repair, REQ-001 completed and REQ-003
running. Preserve current pins and publish directly to main using Yukang Zeng <ykzeng2019@gmail.com>.

**Full-project readiness: 55%, change 0 percentage points, judgment range 45–65%.** Grading decisions are now
explicit and a checker defect is isolated; no empirical evidence or validated interval was added. Same rubric
and stages. Remaining milestones: useful validated inference/adequate comparisons; statistical validation and
final empirical synthesis; independent reproducibility, author metadata and submission packaging.
