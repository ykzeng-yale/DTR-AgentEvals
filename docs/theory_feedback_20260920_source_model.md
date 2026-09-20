# Provenance fixes and the source-model boundary

Review cycle: **20 September 2026, 17:51 UTC**. Reviewed experiment commit
[`3f9000a99653e92207545df5c29d6406cf634205`](https://github.com/ykzeng-yale/DTR-AgentEvals/commit/3f9000a99653e92207545df5c29d6406cf634205)
and its handoff after the 16:20 UTC issue #4 checkpoint at `7826c0c`.

## Three previous checker failures are closed

The independent audit accepts all three fixes: a changed branch hash with its old restoration report now rejects;
an episode cannot borrow a source hash from another invocation; and manifests without source hashes fail closed.
All **39 existing case expectations** are met at the new pin, including clean log/branch records and legitimate
ledgered recovery. The audit runs each case against both versions. Its new source-binding baseline is generated
from the clean fixture before mutation at both pins, so refreshing the report does not mask the stale-report case.
The 42 published fixtures also pass. The primary reviewer reproduced the pinned audit report byte-for-byte.

The actual report's branch/log/visible-test byte hashes and covered-ID digest/count match the pinned records.
All **800 unique completed IDs** equal the frozen branch plan; all parent/branch/invocation-specific durable hash
links and task IDs match, covering **200 prefixes across 103 tasks**. All **20 non-analysis artifacts** are unchanged,
including the ledger's five historical durable rows across four episode IDs. No model observations were added.

Source inspection confirms that the helper now compares reconstructed bytes with both the parent and branch
hashes. Full transcript-byte reconstruction remains **workstream-reported**, because the frozen task file is still
absent locally. This is a reproduction limitation, not a failed archived comparison. The new report does not bind
the task-file bytes, prompt/helper revision or durable decision files. The gate checks durable keys/actions but
does not compare all transcript/state/probability fields. These are remaining coverage limits, not a reopening of
the three accepted fixes or an allegation of archive corruption. Actual-host writer exclusion, atomic publication,
runtime/tool restoration and completion of lost calls also remain outside these checks.

The [gate audit](audits/publication_gate_audit_3f9000a.json) and
[record audit](audits/restoration_audit_3f9000a.json) preserve commands, pins, source hashes and limits.
The workstream's broader 97-test result and host-health statements remain reported; this monitor did not rerun
that dependency suite or inspect the remote host. The reply contains no new question.

The earlier request remains: supply a licensed, pinned regeneration procedure or exact frozen task input matching
the design hash, record the prompt/helper versions, and permit independent transcript reconstruction against the
parent/branch/durable records. Preserve the accepted recovery controls. The unchanged older README claims about
branch compatibility, replicate accounting and timeout harmlessness still require the previously supplied wording
repairs; no new experiments are requested to make those edits.

## Theory progress: a deliberately scoped source-population model

The new [source-model note](theory_branch_source_model.md) proves a sufficient iid task-population result, with
bounded task payloads and uniformly positive per-task prefix counts and log-arm denominators. The latent
full-frame ratio contrast has a task influence expansion and central limit theorem; its variance and the oracle
squared task-derivative statistic have the same asymptotic scale. Combining this with the existing conditional
quadratic identity establishes asymptotic agreement **in expectation** for the source-frame variance component.
The delta method and iid limit laws are classical, explicitly attributed; no new general sampling theorem is claimed.

The restrictions are substantive: tasks with no eligible prefix or no weight in an arm are outside this sufficient
model. Do not filter such tasks to force the theorem to apply, or reinterpret the existing fixed benchmark as an
unverified iid sample. An exact fixed-benchmark counterexample gives zero repeated-execution variance despite
positive task-score dispersion. The note does **not** establish concentration of the sampled quadratic estimate,
the conditional branch component's consistency, a joint limit/studentization theorem, or the current band's coverage.

The proof received independent mathematical review; the primary reviewer checked its fourth-moment Taylor bound,
variance limit and bounded-law-of-large-numbers argument. Review also restored an explicit unconditional
second-moment condition before the total-variance decomposition; conditional finite moments alone do not suffice.
Three exact toy checks cover unequal prefix counts and
shared-source derivatives, finite-sample bias in the oracle variance approximation, and the fixed-benchmark boundary.
The selected suite passes **79 tests** (37 root, including 27 exact theoretical cases, plus 42 gate fixtures).
These are deterministic checks, not Monte Carlo evidence. The note remains separate from the unchanged **29-page,
14-result PDF**. Its previous PDF hash and all 31 prior source hashes were verified before the status annotations;
the updated validation record distinguishes those annotations and the new note from compiled manuscript content.

## Next decisions and acceptance criteria

1. Declare the inferential target before using the new source model. For the existing conditional-on-benchmark
   target, derive source-log randomization and branch-selection/execution variance under that design. For a separate
   task-population claim, justify its sampling law without discarding zero-prefix/zero-arm tasks, then prove sampled
   variance concentration and the joint limit. Neither route may promote the exploratory band by algebra alone.
2. Finish reproducible input/provenance delivery and the remaining reporting repairs above. Later competitive-router
   and operating-characteristic studies stay queued with frozen targets, immutable inputs, task-level validation
   and coverage/error criteria; no new GPU/model, candidate-code or Monte Carlo work was launched by this review.
3. Integrate validated empirical comparisons, the final scoped theory and limitations into the paper; complete
   independent reproduction, author-approved metadata and final source/PDF/supplement packaging.

**Overall submission readiness remains about 60% (change: 0 percentage points; judgment range 50–65%).**
The unchanged stages **75/75/50/50/25** under weights **25/20/30/15/10** give **58.75** before rounding. The accepted
checker fixes and reviewed source-model proof are progress within existing milestones. Valid joint inference and
comparators, complete manuscript/result integration, and reproducibility/metadata/final packaging remain the three
largest gaps. No submission is performed or authorized here.
