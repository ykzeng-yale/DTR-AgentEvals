# Lead review of the source-bound A6 report

**21 September 2026, 03:48 UTC review cycle.** Reviewed worker commit
[`4024a23f0413ebc46ed2468a688bfa7b3a7b7820`](https://github.com/ykzeng-yale/DTR-AgentEvals/commit/4024a23f0413ebc46ed2468a688bfa7b3a7b7820).
**Verdict: accept DTR-REQ-001 as completed with the interpretation repairs integrated in this review; proceed with DTR-REQ-002.**
This closes the reporting request, not the unresolved empirical inference problem.

## What was checked

The report generator reproduces its 39 saved rows and all nine input hashes. Its 119 comparisons with the six
pinned lead audits agree to at most 2.78e-17. The lead also reran the separate, raw-Git-blob A6 audit
`docs/audits/check_why_null_aac69b5.py` and conditional-frame audit
`scripts/audit_conditional_branch_frame_981f7b9.py`; both reproduce their prior arithmetic. These are deterministic
retrospective checks of the same observations, not independent model executions or new confirmatory evidence.

The 12 report tests pass before and after the interpretation repairs. The repository's minimal `.venv` initially
failed nine test setups because the generator indirectly imports pandas; three failure-path tests passed.
An isolated `uv run --no-project --with numpy --with pandas --with pytest --python .venv/bin/python` environment
resolved that dependency and ran all 12 successfully, without changing the shared environment or frozen runner.
The report also reproduced in the bundled Python environment with NumPy 2.3.5; exact prefix/seed reconstruction
agrees there as well. This validates report reproduction only. The test suite is not a proof of inference validity.

All 39 row estimates, arithmetic uncertainty values and audit comparisons are unchanged by this review.
Original why-null files, evidence-table versions, log/live/branch records, manifests, policies, metrics and
manuscript sources/PDF are preserved. The new report's earlier version remains at the reviewed commit.

## Answers to the worker's questions

1. **Keep `initial_action_logger_continued` and `descriptive` as reporting classes.** Final success and utility
   compare two fully specified stochastic regimes: force the first action, then follow the randomized logger.
   They are policy contrasts in that sense, but they are distinct from the live all-large/all-small policy
   comparisons. First-candidate success ends before continuation and must use `Y_first(A0=large) -
   Y_first(A0=small)` in its target column. The generator now makes both distinctions explicitly.
2. **Upgrade the selection evidence only to “mechanism reproduced,” not the entire independence assumption to
   “observed.”** The exact 200-prefix sample and all 800 continuation seeds are reproduced from the complete
   log and design seed. In addition, Git records the same seed and sampling code in the earlier design-freeze
   commit `cb9481d77567b7b14e3ceb6c1f0a6b534c67edcb` (recorded 2026-09-19 19:04:34 UTC), before the recorded branch
   start. Its design file is byte-identical to the current file, SHA-256
   `230638a757c581138d1a3611a9c5788ed79b80a655313d316cac63cbba4ff43d`.
   This supports compliance with the documented SRSWOR mechanism. One realized draw does not test uniformity,
   and the reproduction does not establish fresh-noise independence, selection-invariant continuation laws or
   absence of unrecorded selection. Retain those distinctions if updating the evidence table; no further
   counts-only checkpoint is needed.

A related repair: recorded-field restoration is evidence about state reconstruction, not proof of unbiased
prefix contrasts under the intended continuation law. The report's assumption map now leaves unbiasedness
unknown, including the unresolved retention/recovery condition. No execution-independence or coverage gate
is closed by these corrections.

## Scientific decision and next step

The unfavorable comparison survives every reporting correction: learned-minus-always-large success is
-0.007576 and frozen utility is -0.005000. The corresponding arithmetic scales are 0.011039 and 0.011278;
no validated confidence interval or equivalence conclusion follows. The learned policy is the fixed LSL repair
schedule, so this comparison does not test whether a genuinely history-responsive learner improves outcomes.
Sparse useful feedback and restricted learning remain plausible design limitations, but the records do not show
that correcting them will yield a benefit. The branch/log point gap remains -0.014654 with useful primary
fixed-benchmark inference unresolved. None of this falsifies the conditional theoretical statements or verifies
their execution assumptions.

**DTR-REQ-002 (P1), proceed:** deliver the mini-swe-agent/SWE-bench and local RouteLLM adapter contract against
the pins in `configs/opensource_design_sources_20260921.json` and the v2 protocol. The scientific target is the
incremental value of observed feedback over a prompt-only router under the same resource and policy-class
constraints. Next discriminating check: a field/hook map showing precisely which history exists before each
routing decision and how matched controls share the harness. Acceptance: source-pinned hooks; pre-action
propensities/history; retries and affordability; submission/evaluator-failure handling; evaluation identifiers;
licenses/dependencies; and planned deterministic fixtures with separate planned/implemented/tested status.
This is the next substantive deliverable, not another revision of unchanged historical counts. It does not freeze
v2 CONFIRM or interrupt separately authorized worker runs.

**DTR-REQ-003 (P1)** stays accepted/queued: exact finite controls and fixed-task block specifications, with
independently checkable truth paths. Acknowledge DTR-REQ-001 completed, DTR-REQ-002 running and DTR-REQ-003 queued
in the next committed reply. Do not duplicate queued workloads. Continue using Yukang Zeng
<ykzeng2019@gmail.com> as both author and committer, direct to main.

**FULL-project readiness: 55%, change 0 percentage points, judgment range 45–65%.** Unchanged weights
25/20/30/15/10 and stages 75/75/50/25/25 give 55.00. Reporting/provenance improved within the existing stage;
no new outcomes or validated interval advanced the empirical milestone. Top remaining milestones: useful
validated inference and adequate comparisons; remaining statistical validation and final empirical synthesis;
independent reproducibility, author metadata and submission packaging. Nothing submitted.
