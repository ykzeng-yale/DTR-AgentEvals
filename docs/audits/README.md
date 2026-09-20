# Dated artifact audits

## Independent task/transcript reconstruction and paper integration: `13bad73`

```sh
python3 docs/audits/check_reconstruction_13bad73.py
python3 docs/audits/check_publication_gate_13bad73.py
.venv/bin/python -m pytest -q tests experiments/tools/test_verify_stage.py
sh manuscript/build.sh
```

The reconstruction script downloads the public source bytes into ignored `work/restoration_reconstruction_13bad73`,
rebuilds all 591 task records and verifies the frozen task hash. Pass `--offline` to reuse that directory's downloaded
sources, whose hashes are still checked; `--output-dir` selects another fresh directory. No experiment modules,
reference programs or generated code are executed. Prompt equivalents are independently written, with constants
read as literals from pinned source. All 800 reconstructed parent/branch/durable hash links match, representing
200 prefixes and 103 tasks. All binding fields and 20 unchanged non-analysis artifacts reconcile. The primary
reviewer repeated the downloads and reconstruction and reproduced `reconstruction_audit_13bad73.json` byte-for-byte.
Downloaded data stays ignored; the audit does not rerun models, tools or hidden tests.

The gate script retains the prior 39 cases plus a missing-parent-durable-source case at both pins. New required
bindings and reference files are added to clean fixtures at both versions before mutation. All 40 current outcomes
meet expectations, with legitimate recovery accepted. The primary reviewer reproduced
`publication_gate_audit_13bad73.json` byte-for-byte. This is 80 pinned CLI runs, separate from the selected pytest
suite's **80 tests** (37 root, including 27 exact theory cases; 43 gate fixtures). Task/helper/runtime and semantic
record coverage limits are stated in the [response](../theory_feedback_20260920_reconstruction.md).

The reviewed source-model result is now Section 9.5, Proposition 13 of the **31-page, 15-result paper**. Independent
mathematical review and all-page visual QA passed, with clean compilation and 22 cited references. The result
remains expectation-only for the sampled quadratic statistic and does not validate joint coverage for the fixed
benchmark. Source/PDF provenance is recorded in `manuscript/validation.json`. No new empirical estimates, model
workloads or Monte Carlo sweeps were run.

## Bound restoration report and source identity: `3f9000a`

```sh
python3 docs/audits/check_publication_gate_3f9000a.py
python3 docs/audits/check_restoration_3f9000a.py
.venv/bin/python -m pytest -q tests experiments/tools/test_verify_stage.py
```

The gate audit retains the prior 39 cases and runs them at both pinned versions. A positive source-bound report
is generated from each clean fixture before mutation at both pins. All three previously accepted defective cases
now reject; all 39 current expectations are met, including legitimate ledgered adaptive recovery. The primary
reviewer reproduced `publication_gate_audit_3f9000a.json` byte-for-byte. No broader adversarial search is claimed.

The independent record audit verifies actual source-binding hashes and all 800 completed IDs against the frozen
plan, along with all 800 branch/parent/invocation-specific durable hash links (200 prefixes, 103 tasks). All 20
non-analysis artifacts are unchanged. The primary reviewer reproduced the pinned findings in
`restoration_audit_3f9000a.json`; the archived script checks pinned manuscript objects so later paper revisions do
not invalidate that historical audit. The prior PDF and all 31 working source hashes were also checked before this
cycle's coordination annotations. Full transcript-byte reconstruction remains workstream-reported because the
frozen task file is absent locally. Task/template revision binding, durable transcript checks, runtime restoration
and atomic publication are distinct remaining limits; no archived corruption is alleged.

The selected suite passes **79 tests** (37 root, including 27 exact theoretical cases; 42 gate fixtures). Three
new exact examples check the separately reviewed [source-model note](../theory_branch_source_model.md): task-weight
derivatives, finite-sample oracle bias under an iid toy law, and a fixed-benchmark counterexample. They are not a
Monte Carlo study or a coverage test. The **29-page PDF remains unchanged**. No model/candidate/tool execution was
performed. See the [current response](../theory_feedback_20260920_source_model.md).

## Restoration records and quadratic-moment integration: `97689b9`

```sh
python3 docs/audits/check_restoration_97689b9.py
python3 docs/audits/check_publication_gate_97689b9.py
.venv/bin/python -m pytest -q tests experiments/tools/test_verify_stage.py
sh manuscript/build.sh
```

Both audit scripts read pinned Git records and write only under ignored `work/` or temporary directories. Their
archived reports are `restoration_audit_97689b9.json` and `publication_gate_audit_97689b9.json`. The primary reviewer
reproduced the independent reviewers' results; the final report wording records the local reconstruction limit.
The restoration audit checks stored links, not transcript-byte reconstruction: all 800 branch/parent/durable
hash links match (200 prefixes, 103 tasks). The frozen task file is absent locally, so the workstream's transcript
reconstruction was not independently repeated. Pass `--include-linkage` to generate detailed record links under
`work/`. All 20 non-analysis files remain unchanged.

The gate audit runs 39 cases at each of two pins, including the prior 35 with the newly required positive
restoration summary supplied explicitly at both versions. Five previous defects reject; a stale-summary parent-hash
case and two source-hash binding cases still pass. Missing/negative summaries reject, and valid ledgered adaptive
recovery passes. The actual ledger still reconciles five historical rows across four IDs. These fixture findings
do not establish corruption of the actual cohort or verify actual-host writer exclusion/atomic publication.

The selected suite passes **71 tests** (34 root, including 24 exact theoretical cases; 37 gate fixtures). The four
quadratic-moment checks were introduced in the previous cycle. Their reviewed result is now Section 9.4,
Proposition 12 of the **29-page manuscript**, with 14 numbered results. Independent proof-preservation review,
clean compilation and all-page visual review passed. Source/PDF hashes are in `manuscript/validation.json`.
The [response](../theory_feedback_20260920_restoration.md) supplies acceptance criteria and inference limits.
No model, candidate-code, tool reexecution or Monte Carlo work was performed.

## Recovery ledger and task-quadratic identity: `bd1ace8`

```sh
python3 docs/audits/check_publication_gate_bd1ace8.py
.venv/bin/python -m pytest -q tests experiments/tools/test_verify_stage.py
```

The pinned CLI comparison checks 35 tiny cases at each of two versions: the earlier 32 cases plus one positive
and two negative recovery-ledger cases. The primary reviewer reproduced `publication_gate_audit_bd1ace8.json`
byte-for-byte. Four prior bypasses are fixed, four remain, and both new ledger defects still pass. A properly
ledgered recovery case with a differing historical action now passes. The actual ledger reconciles five rows over
four episode IDs; all 19 earlier non-analysis artifacts are unchanged, and the ledger is the twentieth file.
The [review](../theory_feedback_20260920_recovery.md) distinguishes fixture failures from archive corruption and
pre-invocation evidence from completed execution. Actual-host writer exclusion and atomic publication are not tested.

The selected test command passes **64 tests**: 34 root and 30 gate fixtures. Four new rational-enumeration tests
verify the independently reviewed [quadratic-moment identity](../theory_branch_quadratic.md), including unequal task
sizes, noise subtraction and a census. This supplies a latent quadratic statistic, not a complete variance or
coverage result. No model inference, candidate-code execution or Monte Carlo is performed. The 28-page PDF and
all 22 previously recorded source hashes remain unchanged.

## Replay repair and production-function controls: `8ab7fb5`

```sh
python3 docs/audits/check_replay_controls_8ab7fb5.py
.venv/bin/python -m pytest -q tests
sh manuscript/build.sh
```

The standard-library checker extracts reviewed pure functions from pinned source through the Python AST, without
importing the experiment modules. The primary reviewer reproduced the archived `replay_controls_audit_8ab7fb5.json`
report: **71 checks, zero failures**. It compares saved diagnostics and common-cohort summaries with the prior
independent reconstruction, checks unchanged raw artifacts, and connects the implemented replay rule to exact
known-value controls. All 24 calls over eight equally weighted cases have available donors and zero fallback:
adaptive replay 3/4 versus truth 1; constant second-action replay 1/2 versus truth 1/2. The two represented donors
are the first donor and first later opposite-action match, not an unconditional two-donor iid sample.

All **19 non-analysis artifacts**, the comparison CSV and the production replay rule are unchanged. The report also
records a separate reviewer's successful run of the eight published fixtures and its pinned dependency command;
the stdlib audit does not rerun that command. The root `.venv` lacks pandas, so the experiment fixture suite needs
its experiment dependencies. The 30 root tests pass. No new GPU/model, candidate-code execution or Monte Carlo
work is performed. See the [response](../theory_feedback_20260920_replay_integration.md).

The reviewed replay note is now integrated in Section 8.2 of the **28-page manuscript**. Its proof, prospective-plan
clarification and all rendered pages were reviewed; the build has no warnings or unresolved references. Updated
source/PDF hashes and prior-delivery provenance are in `manuscript/validation.json`.

## Post-hoc replay comparator: `560135e`

```sh
python3 docs/audits/check_static_replay_560135e.py
.venv/bin/python -m pytest -q tests
```

The standard-library checker reconstructs replay paths from pinned Git records without importing experiment code.
Its compact report is `static_replay_audit_560135e.json`; pass `--include-paths` to regenerate per-task details under
ignored `work/`. The primary reviewer reproduced the separate reviewer's arithmetic and diagnostics: **119 checks,
zero failures**, including saved A/B values, live means, paired standard errors and saved DR/calibration agreement.
DR was not independently refitted. All 19 non-analysis artifacts are unchanged. The [review](../theory_feedback_20260920_replay.md)
explains why matched-cohort summaries, later fallback and descriptive interpretation must replace the stronger claims.

The root suite passes **30 tests**, including three new rational-arithmetic checks for the independently reviewed
[replay note](../theory_replay_boundaries.md). These tests check the mathematical constructions rather than directly
executing the workstream's comparator. No model inference, candidate-code execution or Monte Carlo is performed.
The unchanged 27-page PDF and all previously recorded source hashes were checked without rebuilding it.

## Completed branch cohort and target check: `d4997c6`

Two standard-library-only checks read pinned Git objects and write reports under ignored `work/`:

```sh
python3 docs/audits/check_completed_branch_d4997c6.py
python3 docs/audits/check_branch_linkage_d4997c6.py
```

The primary agent reran both and reproduced the archived JSON reports byte-for-byte. The completed-cohort audit passes 80 check types, reconciles all 800 episodes and distinguishes invocation-specific durable records. Its report explicitly separates the documented recovery from unverified operator claims about lost data and lists shortcomings of the publication verifier.

The linkage audit reconstructs the original and selected-task comparisons independently of the experiment analysis code. It checks all 330 common-task ratio derivatives by deterministic finite differences (maximum error below `7e-12`) and a two-task reweighting counterexample. It asserts **no standard error or confidence interval**. The algebra received an independent mathematical review; design-specific uncertainty remains open. Neither check executes candidate programs, model inference, Monte Carlo or runtime restoration. See [the review](../theory_feedback_20260920_branch.md) for interpretations and acceptance criteria.

## Revised publication gate and manuscript integration: `6f92026`

```sh
.venv/bin/python docs/audits/check_publication_gate_6f92026.py
.venv/bin/python -m pytest -q tests experiments/tools/test_verify_stage.py
sh manuscript/build.sh
```

The pinned CLI comparison runs 32 tiny cases against each of the old and new gates, writing only under ignored
`work/` and temporary directories. The primary reviewer reproduced `publication_gate_audit_6f92026.json`
byte-for-byte. Twelve of the prior 14 bypasses are fixed. The expanded suite finds eight accepted defective cases
and one rejected valid historical-recovery case at the new pin; all 19 non-analysis artifacts are unchanged.
The [response](../theory_feedback_20260920_integration.md) distinguishes remaining checker gaps from data corruption.

The selected test command passes **49 tests** (27 root and 22 gate fixtures), without launching experiment sweeps.
The manuscript now integrates the reviewed sampling proposition, builds to **27 pages**, has 13 numbered results,
and received independent proof-preservation and document-wide visual review. Source/PDF hashes and exact scope are
in `manuscript/validation.json`. Rebuilding can change PDF metadata; the hashes identify the delivered artifact.
No new model inference, Monte Carlo sweep, hidden-test rescoring, runtime restoration or remote-liveness validation
is performed by this monitor.

## Target-preserving repair and publication gate: `29ee443`

Reproduce the current independent checks using pinned Git objects:

```sh
.venv/bin/python docs/audits/check_branch_linearization_29ee443.py
.venv/bin/python docs/audits/check_publication_gate_29ee443.py
.venv/bin/python -m pytest -q tests experiments/tools/test_verify_stage.py
```

The first two commands write only under ignored `work/` or temporary directories. Their archived reports are
`branch_linearization_audit_29ee443.json` and `publication_gate_audit_29ee443.json`. The primary reviewer reproduced
the saved numerical results: pooled difference −0.014654, squared-derivative scale 0.048386, and 25 gate fixtures
(two controls accepted, nine defects rejected, 14 defects still accepted). All 19 non-analysis code-study artifacts
are unchanged. The reports distinguish algebra from valid inference and gate counterexamples from archive corruption.

The test command passes **36 tests**: 27 root tests, including four new exact finite-enumeration checks for the
[conditional sampling proof](../theory_branch_sampling.md), and nine workstream gate fixtures. The proof and its
scope received separate mathematical review. No model, candidate-code execution, Monte Carlo sweep, runtime
restoration, or remote liveness check is performed. The [feedback](../theory_feedback_20260920_sampling.md) gives
the remaining inference, record-integrity and reporting requirements.

## Live-policy and partial-branch snapshot: `ac3ca83`

`code_routing_live_branch_audit_ac3ca83.json` records the 20 September 2026 independent artifact review. Reproduce it with the repository environment:

```sh
.venv/bin/python docs/audits/check_live_branch_ac3ca83.py
```

The checker uses NumPy (recorded version 2.5.3) only to reconstruct the frozen seeded branch selection, not to run a Monte Carlo experiment. It reads pinned Git objects and writes under ignored `work/`. The primary agent reran it: all 140 check types passed and its report was byte-identical to the archived JSON. This establishes artifact consistency for the complete live stage and the partial branch snapshot, not hidden-test validity, runtime restoration or current host status. Unmatched branch decisions are explicitly reconciled to in-flight episodes, not treated as complete or silently discarded.

Independent numerical and figure/source reviews additionally checked the task-paired estimates, intervals, resource counts and published interpretation; see [the current feedback](../theory_feedback_20260920.md). Artifact checks alone do not validate these scientific conclusions. The manuscript PDF was not rebuilt or changed.

## Randomized-log snapshot: `035d245`

`code_routing_artifact_audit_035d245.json` records the independent internal artifact review of experiment commit `035d245f6fa10450f7cf89420bc1947d4c54aebc` on 19 September 2026. It preserves the reviewer's scope and limitations. It does not independently execute generated programs, rescore hidden tests or certify causal results.

Reproduce the artifact checks from any full checkout containing that commit:

```sh
python3 docs/audits/check_code_routing_035d245.py
```

The standard-library-only script reads pinned Git objects and writes its report under ignored `work/`; it does not change the archived report or experiment files. A failed consistency check causes a nonzero exit. The primary agent reran this archived script and verified byte-for-byte agreement with the saved report. The audit found zero failures across 75 check types; repeated per-record checks are not independent statistical evidence.

A separate theory reviewer independently reconstructed all 17 learned-policy entries from TRAIN records and checked the mathematical applicability of the planned analyses. That review's findings and acceptance criteria are in [the theory feedback](../theory_feedback_20260919.md); they are broader than the artifact script and should not be inferred from its pass status. The compiled paper was not rebuilt during this cycle; its PDF and all 13 files listed in `manuscript/validation.json` still match the recorded hashes.
