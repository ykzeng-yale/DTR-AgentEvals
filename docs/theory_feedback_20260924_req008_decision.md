# Lead decision on the REQ-008 fresh-task inventory

**24 September 2026, 07:23 UTC.** Reviewed worker output at `eb6027d` against the
pinned 500-ID `SWE-bench_Verified@c104f840` frame, committed manifest summaries,
handoff, and the v2 protocol. A separate read of the machine-readable record
recounted 500 rows, the two category partitions and the identical 431-ID
not-yet-assessed lists (SHA-256 `7883a5f056bfeb12c0725f39006594b4e79f6a3557981df475354088b9e4d047`).
All 38 focused tests pass in the local repository environment. This is an
inspection and bounded independent count/hash check, **not** independent
reconstruction of the worker's full historical exposure scan or validation
of model execution. The worker reports 39/39 source-consistency checks and
12/12 pin links; those checks are not a runtime qualification.

**Verdict: PROCEED with prospective metadata design; HOLD new E2 live/CONFIRM.**
The 431 candidate IDs, across 11 repositories, resolve the narrow question
whether the separate pinned SWE-bench frame has issue identities absent from
recorded project assessments. They do not change the fact that the archived
coding benchmark's 591-task pool was exhausted. All 431 remain runtime
untested under the strict evaluator gate. Public/pretraining exposure,
near-duplicate variants, serving competence, decision-2 occupancy,
policy disagreement, effect precision and resource adequacy remain unknown.
The existing 0/32 operational-success DEV cohorts make a fresh effect run
premature; neither a positive result nor an empirical null for history
adaptation follows. The fixed endpoint, initial-small matched-class contrast,
unfavorable records, source pins and v2 protocol gates stay in force.

The lead fixes the following design choices before any outcome or model run:

1. Use the **conservative exposure definition**: the 64 IDs with this-project
   or recorded third-party model trajectories are excluded from the proposed
   fresh pool. For the first qualification queue also exclude the five
   qualification/inspection-only IDs and the eight as-yet-untouched IDs with
   empty PASS_TO_PASS. This is a cautious design choice, not proof that
   inspecting metadata causes outcome contamination. The candidate list
   begins with the recorded 431 and can only shrink after the rules below.
2. The scientific target is new issues **within named repositories**. Repository
   is a reporting/stratification factor, not a blanket exclusion unit;
   exposure of one issue does not exclude every issue in that repository.
   Do not claim generalization to new repositories. Before splitting or
   freezing IDs, form connected components within each repository using an
   outcome-independent edge when two tasks have either an identical declared
   FAIL_TO_PASS test identifier or both the same `base_commit` and at least
   one identical path in the reference patch. Extract identifiers/paths only;
   do not inspect test outcomes or reference patch content. Exclude a whole
   component from the fresh queue if it touches any of the 64 exposed or five
   qualification/inspection-only IDs. Report component sizes and reasons;
   do not silently replace excluded tasks. A shared repository or version
   alone is not an edge. If the pinned metadata cannot support either edge
   deterministically, report the missing field and stop the queue design.
3. For a **design-only** first queue, sort remaining IDs within each repository
   by SHA-256 of UTF-8 `DTR-REQ-009|c104f840|<instance_id>`, breaking hash
   ties by ID; visit nonempty repositories in lexicographic round-robin order
   and take at most 24 IDs. Preserve the
   complete ordered list and source hashes. This 24-ID queue is for later
   competence/qualification planning, not a frozen evaluation sample,
   power target or permission to start containers or model inference.

**DTR-REQ-009 (P0), source `eb6027d`:** produce a deterministic, read-only
near-duplicate/component and 24-ID queue record from the pinned metadata and
REQ-008 categories. Acceptance: no outcome reads, no new download or model,
container, GPU or Monte Carlo execution; exact pin and 500-ID reconciliation;
explicit edge witnesses and source hashes; counts by exclusion reason and
repository; reproducible queue ordering; no changed archived result; focused
negative fixtures for missing fields and edge construction. Report whether
the queue contains 24 IDs and its repository distribution. Acknowledge
REQ-008 as completed and REQ-009 as accepted/running/completed/blocked or
superseded with the output commit. After this metadata gate, the lead will
set a bounded qualification/competence plan and a numerical success/resource
margin and precision rule. No queue result itself releases E2 or cue-v1.

**Readiness: 55%, change 0 percentage points, judgment range 45–65%.** The
unchanged 25/20/30/15/10 rubric reflects useful design inventory but no new
qualified task or measured real-agent contrast. The top remaining milestones
are (1) competence/decision-opportunity evidence and a valid fresh comparison
with fixed-target inference, (2) final empirical synthesis, and (3)
independent reproducibility, author metadata and submission packaging.
