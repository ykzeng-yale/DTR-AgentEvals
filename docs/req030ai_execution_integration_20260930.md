# REQ030AI: complete episode execution integration

This is validated implementation for a future prospectively frozen DEVELOPMENT
run, **not a model release or a new model result**. CPU control job **27950747**
is already running under source `594cf2c6`; these changes do not modify its
immutable staging or payload. Read the [conditional scientific design](req030ai_opportunity_design_review_20260930.md)
and the [whole-cohort CPU release](req030ah_whole_cohort_controls_20260930.md).

## Question resolved by deterministic evidence

Can the actual pinned agent execute both routing decisions, preserve native
receipts and terminate a stuck native worker without depending on the driver's
continued life? The new CPU caller starts an independent guardian and a fresh
exec worker. Only that worker loads the pinned model pair/CUDA. The guardian
enforces 600 seconds for startup/loading, 600 seconds per native call, 2,700
seconds from model readiness through episode completion, and 3,600 seconds
overall. A native call spans durable request acceptance through durable response
acceptance, including output conversion and decoding. Termination uses TERM,
then KILL and reaping; an owner pipe remains effective after actual caller SIGKILL.

Cleanup acceptance requires the existing bounded tool-supervisor receipts and,
if harvesting began, the separate harvest-supervisor receipt. A timeout cannot
promote an intermediate workspace into an eligible submission. Unverifiable
cleanup aborts further workers; missing/corrupt receipts are infrastructure
unknown. Assigned slots remain in the operational denominator with zero verified
resolution; algorithmic correctness stays unknown. An eligible completed
submission still requires the separately executed strict evaluator.

The fixed-schedule adapter preserves one history and uses S/L at logical calls
1 and 9 for SS, SL, LS and LL. It checks both token reservations before each
decision, rejects changed native bindings, caps logical queries at 24, and
records global and per-model physical-attempt counts. Deterministic assignment
probabilities are explicitly 1 for the assigned action and 0 for the other;
these records are **not** observations from a randomized 1/2 logger and cannot
be relabeled for OPE. The common pinned tokenizer/model revisions, 16,384-token
context and 1,536-token response limit are checked in source.

The worker accepts an allowlisted one-task public specification, rechecks source,
image, archive, executable and public-projection hashes, and constructs a bundle
containing only the public task file. Evaluator/reference bundles are absent from
the worker API. Generated commands still enter only the existing isolated
Apptainer tool path. The launcher gained only an explicit adapter-factory hook;
the existing bounded journal now retains routing and per-model receipt fields.
Both unique model repo/revision identities are also rejected before loading if
they differ from the frozen S/L pair, including the constant-model mode.

Review found a concrete evaluator integration defect: the old shared candidate
grader's abbreviated parser map omitted Django and Matplotlib. A new pure CPU
candidate-replay helper uses AH's complete exact upstream parser map and strict
framing/supervisor checks. It binds a candidate to its task, policy, invocation,
release, evaluator, patch and raw evidence; it does not execute a model or test,
apply a reference patch or regrade historical outcomes. Missing required statuses,
required errors and invalid process evidence remain unknown/operational zero.
Observed required nonpasses cannot resolve a task. Undeclared statuses are retained
for review without silently enlarging the frozen strict endpoint. The future
cohort coordinator must call this helper, not the obsolete abbreviated parser path.

## Validation and limits

The lead independently ran:

```sh
uv run python -m pytest -q \
  experiments/lead_req030/test_req030ai_episode_worker.py \
  experiments/lead_req030/test_req030ai_schedule_adapter.py \
  experiments/lead_req030/test_req030ai_candidate_grade.py \
  experiments/lead_req030/test_req030ah_native_limits.py \
  experiments/lead_req030/test_req030ah_runner.py \
  experiments/lead_req030/test_req030ag_screen.py \
  experiments/lead_req030/test_req030ah_controls.py
```

The final joined run passed **195 tests and 7 subtests in 13.33 seconds**, including
38 worker tests and 65 candidate-grader tests. Those grader tests exercise all
1,398 frozen AH declared identities in authored synthetic logs, with each identity
individually omitted and rejected; no actual task test was run. The final receipt
also covers pre-load model-identity rejection and candidate replay across all eight
repositories. Four schedule
fixtures traverse `execute_worker` → existing launcher → pinned `DefaultAgent`
→ schedule adapter → existing production supervisor/runner. The external model
and Apptainer edges are authored inert fixtures; they do not execute supplied
task commands. Real subprocess fault fixtures cover driver SIGKILL, ignored TERM,
load/generation/decode/episode stalls, corrupt or missing evidence, retained final
stderr, unreapable-worker rejection, and harvest owner-EOF cleanup. A next
untouched episode proceeds only after verified cleanup. The earlier documented
repository suite passed 812 tests before these new changes; that is a separate
test population. An initial bare `uv run pytest` targeted invocation failed
collection because the repository root was absent from its module path; the
documented `python -m pytest` command above resolved invocation, without a code or
test change. Source hashes and the exact successful command are in the
[implementation receipt](../results/local_req030/req030ai_integration_20260930/validation.json).

These tests establish process/control behavior on the local host. They do not
measure CUDA throughput, model memory, task competence, remote container behavior
of these new bytes, or an H/P effect. Interrupted predispatch receipt windows do
not establish an exact hardware invocation count; preserve request, response,
error and lifecycle records separately. The current routing receipt has exact
token reservations and common enforced deadlines, but does not yet record a
measured remaining-wall-time value or a predecision workspace identity. Do not
claim prefix coupling or a frozen primary H/P logging contract from it.

## Decision and next dependency

The implementation is available for one coherent future cohort entrypoint and
immutable release. It does not require recycling a sequence of generic probes.
Before that release, independently replay all 16 AH controls, resolve every
source-tree contract, reconcile recent public-input exposure, finish cohort
aggregation/strict grading and freeze order, budget, retry semantics and source
pins. A source discrepancy or an invalid control cannot be rescued with a
passing subset or hidden-output tuning. The proposed 32-cell opportunity study
has a 37h20 component ceiling before additional setup/cleanup; the allocation
and joint-budget rule must reflect that calculation.

There is no new evidence that the executor pair solves tasks or that history
improves routing. Existing weak/null findings remain unchanged. Full-project
readiness is **55%, change 0 points, range 45–65%**. Remaining milestones are
competent fixed-target comparisons with valid inference; empirical/manuscript
synthesis; independent reproduction and the author-approved submission package.
