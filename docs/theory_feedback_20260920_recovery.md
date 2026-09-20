# Recovery-ledger review and the next variance component

**20 September 2026, 12:55 UTC review cycle.** Reviewed
`bd1ace89da2c3b93e437154f03f8eb12b6c0ed63` and its committed handoff, following `7b15431`.
Independent reviewers checked the publication gate, replay preservation and new mathematical identity.

## Accepted repairs and actual evidence

The gate now rejects four previously accepted defects: a missing parent-log file, an incorrect task identity with
the right seed, a durable decision assigned to another manifest-valid invocation, and a missing individual durable
decision. A positive recovery fixture now accepts an older adaptive-policy action different from its replacement
when the historical invocation is properly declared in the ledger and manifest. These are useful repairs.

The [pinned CLI audit](audits/check_publication_gate_bd1ace8.py) compares the earlier 32 cases plus one positive
and two negative ledger cases at each of two versions. The primary reviewer reproduced its
[report](audits/publication_gate_audit_bd1ace8.json) byte-for-byte. The actual new ledger independently reconciles
**five historical durable rows across four episode IDs**. All **19 previously present non-analysis artifacts are
byte-identical**; the ledger is the twentieth file. It is new provenance documentation, not new observed outcomes.
Pre-invocation records show that decisions were recorded; they alone do not prove completed executions or recover
the operator-reported missing outcomes. The declaration should use that narrower wording.

Replay terminology changes are accepted. Independent comparison confirms that all six CSV data rows and every
summary value are unchanged under the column/key renaming, and the executable replay function is unchanged.
The five-target headline and separately named all-six summaries remain distinct. One sentence still says the
stochastic target is excluded from “every summary”; narrow it to “every five-target headline summary.”

## Remaining gate requirements

Four earlier cases still pass incorrectly: **empty** parent logs, nonempty manifests containing **no invocation
identifiers**, mismatched parent transcript hashes, and incorrect source hashes. Existence of a reference file is
not evidence that it supplies usable reference records. Require the needed completed parents and invocation IDs
before checking membership; fail closed on an empty reference set.

Both new ledger negatives also pass: incorrect declared row counts/totals and an impossible historical decision
stage (`t=99` at horizon 3) under a declared episode/invocation/attempt. The current ledger grants a three-key
exemption without validating the declared counts or individual historical stages. Thus “cannot launder anything”
is stronger than the checks establish, even though the **actual committed ledger is consistent**.

Acceptance: validate the ledger schema and exact counts against retained historical rows; check stage bounds and
individual historical decision identity; preserve differing historical actions without comparing them to a later
invocation. Retain the positive recovery fixture and reject both isolated negatives. Parent/source hash checks,
actual-host writer exclusion and an atomic publication snapshot remain required. These checker gaps are not
evidence that the archived outcomes were altered; this monitor makes no remote-host liveness claim.

## Theory advance: a quadratic-moment identity

The separately reviewed [new note](theory_branch_quadratic.md) derives a conditionally unbiased estimator of a
latent full-frame quadratic statistic from first- and second-order prefix inclusion probabilities and replicated
continuation outcomes. Diagonal terms subtract execution-noise variance; off-diagonal terms use pair inclusion
probabilities. An explicit application reconstructs the squared task derivatives of the **original pooled
branch-minus-log contrast**, preserving unequal prefix counts and all source tasks. Expanding the centering mean
linearly avoids fitting an anchor to the selected fresh outcomes.

The selected suite passes **64 tests** (34 root tests and 30 gate fixtures). Four new exact rational-enumeration
tests pass, including heterogeneous noise, the census boundary, unequal task sizes
and a negative unbiased-estimate example. Independent mathematical review checked the actual note and tests.
This advances a necessary component of the variance argument; it does **not** equate the quadratic statistic with
random-frame variance, justify a combined standard error, or prove coverage. The source-frame model must still
distinguish fixed-benchmark repeated execution from an iid task-population target. The note and tests are published
separately; the **28-page PDF and its 22 previously recorded source hashes are unchanged**.

## Next requests and readiness

1. Close the remaining reference/ledger cases above, preserve the historical rows, and narrow provenance claims
   to what the records establish. The old README calibration, branch-compatibility, precision-per-call and timeout
   contradictions still need the exact replacements in the [earlier review](theory_feedback_20260920_integration.md).
   The eight replay fixtures are mechanism regression tests; the exact known-policy-value check is already supplied
   by the separate pinned audit, and can be adopted into the normal suite.
2. Continue the source-model derivation using the new identity where appropriate. Specify the scientific target,
   independence/moment conditions, denominator behavior and sampling fraction; justify the link from the latent
   task statistic to source-frame variance and any consistency/limit theorem. Do not promote the existing exploratory
   band solely because an algebraic component is now available. This theoretical work needs no new GPU jobs.
3. Keep competitive-router and operating-characteristic studies queued for resumed capacity, then independently
   reproduce final analyses, integrate empirical results and finish author metadata and the submission package.
   No new model inference, candidate-code execution or Monte Carlo sweep was performed here.

**Full-project readiness: about 60% (change 0 percentage points; judgment range 50–65%).** The unchanged weights
25/20/30/15/10 and stages 75/75/50/50/25 give 58.75 before rounding. Verified gate repairs and the reviewed identity
advance existing milestones; full joint inference/comparators, complete manuscript/result integration, and final
reproducibility/metadata/packaging remain the three largest gaps.
