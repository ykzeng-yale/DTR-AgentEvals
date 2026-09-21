# Lead selection of the compatible evaluator

**21 September 2026, 04:48 UTC review cycle.** Reviewed worker
[`81128ee8ad3d7ad1c4190355ce19d54d23661408`](https://github.com/ykzeng-yale/DTR-AgentEvals/commit/81128ee8ad3d7ad1c4190355ce19d54d23661408).
**Decision: select `SWE-bench/SWE-bench@f7bbbb2ccdf479001d6467c9e34af59e44a840f9` for v2 development qualification.**
Use this candidate rather than v4.1.0. The choice is made; the worker need not wait for another version decision.
The [separate selection record](../configs/v2_evaluator_selection_20260921.json) keeps the original dataset and
preserves the earlier source-pin manifest. This is a source-level selection, not a tested evaluator or a frozen
confirmation configuration.

## Evidence for the choice

The lead independently inspected the [11-commit comparison](https://github.com/SWE-bench/SWE-bench/compare/v4.1.0...f7bbbb2ccdf479001d6467c9e34af59e44a840f9),
individual relevant patches and candidate source. The [audit record](audits/evaluator_selection_audit_81128ee.json)
contains exact revisions, source hashes and inspection scope.

- [#492's commit](https://github.com/SWE-bench/SWE-bench/commit/2f106b56ffc9e73f7179a962d4d0f45673319ac5)
  changes README retrieval-dataset links only; [#489's commit](https://github.com/SWE-bench/SWE-bench/commit/737efd9ba02b7016feaf25660b5b14d46c0eb592)
  changes a documentation contribution link. They add no evaluator behavior and no longer block this choice.
- The total delta is eight documentation/blog commits and three runtime-related commits, including the candidate
  itself. The other two runtime changes concern multilingual image construction and Java evaluation. The Python
  log-parser file is byte-identical between v4.1.0 and the candidate. This is not a claim of equivalence with v5
  or of runtime correctness on every Python repository.
- The [candidate's checkout fix](https://github.com/SWE-bench/SWE-bench/commit/f7bbbb2ccdf479001d6467c9e34af59e44a840f9)
  handles newly added test files separately, avoiding a file-less checkout that can reset unrelated setup changes.
  The tag lacks this fix. Candidate utilities also add local parquet loading; dataset bytes must therefore be
  revision-bound and hashed rather than loaded by a mutable remote name. These are inspected source changes;
  upstream-reported gold-patch successes were not rerun here.
- The [test-spec builder](https://github.com/SWE-bench/SWE-bench/blob/f7bbbb2ccdf479001d6467c9e34af59e44a840f9/swebench/harness/test_spec/test_spec.py)
  uses original-schema fields and repository/version constants. The [grading source](https://github.com/SWE-bench/SWE-bench/blob/f7bbbb2ccdf479001d6467c9e34af59e44a840f9/swebench/harness/grading.py)
  confirms the empty-required-test hazard. Schema compatibility is supported; successful construction for all
  500 original rows and correct parsing of real execution logs remain untested.

The 35-fixture plan is inspected, with unique IDs and the lead's parameter decisions incorporated. It remains
planned. No upstream evaluator function, model, test patch or container was executed during this review.

## Next work and acceptance criteria

**DTR-REQ-002: selection/design repair accepted; qualification remains running.** Use the selected commit for
M01–M03. M01 must cover all 500 original rows, preserve task/base-commit/test-patch/F2P/P2P content, and record
metadata and generated-script hashes. Record and pin any external inputs needed to construct those scripts;
repeatability cannot rely on mutable setup downloads. This is metadata construction, not permission to execute
those scripts or launch the benchmark.

For M02, explicitly test missing PASS_TO_PASS as well as missing FAIL_TO_PASS; reject malformed test-list types
and empty FAIL_TO_PASS before sampling. An explicitly empty PASS_TO_PASS remains allowed with the documented
regression-coverage limitation. Missing tests or unparsable output must not silently count as passing.

For M03, check grading against the declared required-test outcomes and report version differences. Do not force
agreement with a comparator's bug: justify each discrepancy before acceptance. Add a planned new-file-only
patch regression case for the selected checkout fix, including preservation of an unrelated setup change.
Later isolated no-change/reference-patch execution controls, image/dependency locks, host/resource limits and
the v2 precision gates remain required. Do not treat the presence of an arm64 path as evidence that this host
can execute the benchmark. No system installation, paid service or duplicate run is requested.

**Prioritize DTR-REQ-003's scientific design next:** the acknowledged supplemental cost-dominated control,
then explicit finite repair transition/observation tables and complete fixed-task blocks. Those do not depend
on container availability or M03's future logs. Preserve the six-cell artifact and use the exact acceptance
values in the [previous review](theory_feedback_20260921_exact_control.md). DTR-REQ-001 remains completed.
Acknowledge the selected evaluator and these statuses in the next committed reply. Direct main commits retain
Yukang Zeng <ykzeng2019@gmail.com> as both author and committer.

**FULL-project readiness: 55%, change 0 percentage points, judgment range 45–65%.** The source-level design
blocker is narrowed, with no new empirical outcomes, interval validation or manuscript changes. Weights and
stages remain unchanged. Top milestones: useful validated inference/adequate comparisons; remaining statistical
validation and final empirical synthesis; independent reproducibility, author metadata and submission packaging.
Nothing submitted.
