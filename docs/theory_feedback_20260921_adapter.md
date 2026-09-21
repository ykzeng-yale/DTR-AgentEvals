# Lead review of the v2 adapter contract

**21 September 2026, 03:48 UTC cycle, late-arriving update.** Reviewed
[`6982f5d8b83fcbb0678d251295ac5958f058b928`](https://github.com/ykzeng-yale/DTR-AgentEvals/commit/6982f5d8b83fcbb0678d251295ac5958f058b928),
including the 30 planned fixtures and committed questions. **Verdict: accept the contract as a design deliverable;
repair compatibility before any new SWE-bench stage. Proceed with DTR-REQ-003 independently.** No adapter or fixture
has been executed. The worker's host/runtime inventory remains reported, not independently inspected here.

## Compatibility decision

The lead independently re-read the [pinned evaluator source](https://github.com/SWE-bench/SWE-bench/blob/02e7a74ffd0b707aab73d203fe87bdc7c76afc8e/swebench/harness/utils.py#L255)
and the [pinned dataset card](https://huggingface.co/datasets/princeton-nlp/SWE-bench_Verified/blob/c104f840cc67f8b6eec6f759ebc8b2693d585d4a/README.md).
The evaluator directly indexes four metadata fields absent from the card's declared schema, and its loader does
not add them. This substantiates a source-level incompatibility; it is not an observed evaluator run failure.
Their downloaded SHA-256 values are respectively
`c22f38fdd4ffd34301da7f837b82926cf261d81ca0387d92dd2990b393517c79` and
`6edb58b1b2c44ce858426c4ebc90077827713b75cebc243661e4433c81fd57f5`.

**Choose option (b): retain the original frozen task dataset and audit a compatible upstream evaluator revision.**
Changing datasets merely to satisfy a newer API could also change task/test content and the scientific target.
Do not change any current pin yet. Under **DTR-REQ-002**, provide one exact candidate evaluator commit and a
compatibility delta: required fields, test-spec construction from repo constants, required-test grading semantics,
image/digest resolution, timeout/retry and cache behavior, and license/dependency differences. Use upstream code;
do not invent missing evaluation scripts or copy the evaluator into our project. Acceptance before adoption:
all required fields accounted for on the original schema, unchanged task/test identities, source-audited grading,
and a deterministic metadata-construction fixture specified. Later no-change/reference-patch execution controls
are still required; source compatibility alone will not pass the runtime gate. The current pins remain archived.

This corrects a gap in my earlier component selection: I had not established compatibility of the chosen dataset
and evaluator together. It does not implicate DTR theory or explain the older HumanEval/MBPP results.

## Concrete design decisions for the worker

- Retain the development candidate **K2=9, H=24**, counting format-error calls. Set **P_max=2 total physical attempts
  per logical call**, across every transport layer; retain the assigned model on retry. Parameterized fixtures
  may exercise a cap of three, but must also check the actual candidate cap of two. In A01, clarify zero *new*
  routing draws after resume and one assignment/draw in total. In H06, declare the fixture's cap explicitly.
- Accept `context_window_exceeded` as a separate retained exit: primary operational outcome zero, no salvage or
  backend fallback. Use the same rule for all policies. For the candidate 16,384-token context / 1,536-token
  response caps, preflight the fully rendered prompt for **both** tokenizers, including special tokens, plus the
  response allowance. No silent truncation. Repeat that common check before later calls while retaining the
  assignment. Failure terminates with the recorded reason and does not create another treatment draw.
- At an offered decision, the request reservation must cover two attempts for every remaining logical call in
  the assigned block (calls 1–8 or 9–24); record both backends' checks. Candidate absolute ceiling is 48 requests
  per episode and 73,728 generated tokens across attempts. These are accounting ceilings, not an approved run
  budget or a claim of affordable execution; input tokens, time and evaluator costs remain separate. Lost usage
  must be marked unavailable rather than zero. Final resource limits require a feasible execution host and
  development measurements before collection.
- Reuse the pinned [single-action default prompt configuration](https://github.com/SWE-agent/mini-swe-agent/blob/04d809ceab9df28f9adaed044884180159172930/src/minisweagent/config/default.yaml)
  as the **candidate** prompt basis, not the parallel-tool SWE-bench template. It contains the parser's action
  delimiter and submission instruction; its downloaded SHA-256 is
  `112aa58328f478a41cc2630702a4b89ef459e912870e05065157ed221f56701f`. Bind repository/workspace instructions explicitly
  and use a render/parse fixture before acceptance. That source inspection is not a tested SWE-bench integration.
- Keep at most one evaluator retry on the identical patch. Wall-time and evaluator-time limits remain unfrozen
  until the host/resource plan is assessed; do not inherit an upstream timeout silently. The separately reported
  arm64/no-container host is a feasibility blocker for this candidate, not a reason to install software or buy compute.
- Calibrate the initial-only RouteLLM threshold exclusively on a versioned development split disjoint from TRAIN
  and CONFIRM, using the frozen operational endpoint and budget. The calibration rule and selected threshold must
  precede CONFIRM. Task IDs and the final numerical precision/resource plan remain mandatory protocol gates.

**DTR-REQ-002 remains running only for this compatibility/contract repair; its source map and 30-fixture plan are
accepted as delivered design work. DTR-REQ-003 may proceed now, without waiting for Docker or a new model run.**
Return explicit transition/observation tables, policy catalog, two exact-truth paths and the complete fixed-task
block specification, including positive/negative controls and logger-only target invariance. Acknowledge these
statuses; do not duplicate work or interrupt separately authorized jobs. The hold concerns only a new v2
SWE-bench execution stage with the incompatible pair. This review launches no inference, verifier or sweep.

**FULL-project readiness 55%, change 0 percentage points, range 45–65%.** Rubric unchanged. The new finding is a
repairable defect in an unrun design, not a loss of validated empirical evidence. Remaining milestones: useful
validated inference/adequate comparisons; remaining statistical validation and final empirical synthesis;
independent reproducibility, author metadata and submission packaging. Manuscript/PDF unchanged; nothing submitted.
