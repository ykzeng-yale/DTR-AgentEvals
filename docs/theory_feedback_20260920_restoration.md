# Restoration evidence and quadratic-moment integration

Review cycle: **20 September 2026, 16:08 UTC**. Reviewed experiment commit
[`97689b94ce8f49bf6b12ff6d77ec35573b495493`](https://github.com/ykzeng-yale/DTR-AgentEvals/commit/97689b94ce8f49bf6b12ff6d77ec35573b495493),
following theory checkpoint `a02ffb0` and the 14:37 UTC no-change checkpoint in issue #4.
Independent reviewers checked the publication gate, restoration records, and preservation of the mathematical
result in the manuscript. The primary reviewer reproduced both artifact audits. This review leaves experiment-owned source unchanged;
all **20 non-analysis artifacts** remain byte-identical to `a02ffb0`. No new empirical observations were collected.

## Accepted repairs and remaining publication checks

Five of the six prior bounded failures are fixed: empty reference logs, manifests without invocation IDs,
a single-manifest source-hash mismatch, incorrect historical-row counts, and an impossible historical stage.
Valid ledgered adaptive recovery remains accepted. The actual ledger still reconciles five historical durable
rows across four episode IDs. These are pre-invocation records, not proof of completed lost outcomes.

The independent CLI audit runs **39 cases at each of two pinned versions**. The previous 35 cases receive the
new positive restoration-summary baseline at both versions, with that adaptation recorded explicitly; four
targeted cases examine report/source binding. Three defective cases remain accepted:

1. Changing both stored branch decision hashes while retaining the parent hash and the positive summary passes.
   The gate trusts aggregate counts; it does not bind the report to the current branch/log contents or covered IDs.
2. An episode source hash present only in another invocation's manifest passes.
3. If every manifest source hash is absent, the source-membership check is skipped.

Missing restoration reports and reports with a disagreement correctly reject. Requiring a positive report is a
useful improvement, but it does not close the parent-hash failure by itself. The 37 published gate fixtures pass;
their passing status and these additional counterexamples concern different acceptance boundaries. None of the
counterexamples establishes corruption of the actual archived cohort.

## What the restoration evidence establishes

The workstream reports reconstructing **800/800 parent transcript hashes** with zero disagreements. Source
inspection confirms that the helper builds the parent's pre-stage-1 transcript, compares its hash with the
parent's recorded hash, and compares that Boolean with the branch's stored flag. It does not directly compare
the reconstructed hash with the branch's first decision hash, verify frozen task/test/template hashes, or include
covered IDs and input hashes in its aggregate report. Tool-result restoration remains a stored claim, as disclosed.

An independent record-linkage audit verifies that **all 800 branch first-decision hashes equal their parent
stage-1 hashes**, and both agree with their own durable records keyed by episode, invocation, attempt and stage.
Task IDs also match. These rows cover **200 unique parent prefixes across 103 tasks**; they are not 800 independent
prefix reconstructions. The archived visible-tests hash matches the episode stamps and covers every parent task.

Full transcript-byte reconstruction was **not independently reproduced**: the configured frozen input
`work/code_routing_data/tasks.json` is absent from this checkout. The design expects SHA-256
`23727895971fa4a040198d8770173a4f0c3263a63a9cb1479abc4203bb01c2ce`.
This local input limitation is distinct from a failed hash comparison. The [record audit](audits/restoration_audit_97689b9.json)
and [gate audit](audits/publication_gate_audit_97689b9.json) retain the exact scope and reproducible sources.

Acceptance for the remaining provenance work:

- Supply the exact frozen input, or a licensed, pinned regeneration procedure that reproduces its expected hash.
  Match task, certified visible-test, parent/branch record and template/helper versions to the recorded contract.
- Report per-prefix reconstruction and per-branch linkage separately. Bind the report to artifact hashes and
  exact episode/parent ID sets; compare reconstructed, parent, branch and invocation-specific durable hashes.
  Recompute or reject when records change, IDs are missing/duplicated, or a same-sized unrelated report is supplied.
- Require nonempty source hashes for the relevant manifest invocation and compare each completion against its
  own invocation. Preserve differing legitimate historical invocations and the positive recovery control.
- Replace the broad claim that all six previous cases are closed. Keep tool/runtime restoration and actual-host
  writer exclusion/atomic publication separate from transcript reconstruction and stored record consistency.

The revised calibration and precision wording is accepted. Earlier README sentences about branch compatibility,
replicate accounting and timeout harmlessness still need the replacements already requested; they are not
reopened scientific claims or a request for new experiments.

## Manuscript progress and inference boundary

The reviewed [quadratic-moment identity](theory_branch_quadratic.md) is now **Section 9.4, Proposition 12** in the
**29-page paper**, with **14 numbered mathematical results**. It reconstructs a latent full-frame quadratic
statistic using individual/pair inclusion probabilities and diagonal continuation-noise subtraction. Its
application preserves all source tasks and the original pooled branch-minus-log target.

Independent mathematical review approved the conversion. All pages were rendered and visually reviewed;
compilation has no warnings or unresolved references. The selected suite passes **71 tests** (34 root,
including 24 exact theoretical cases, plus 37 publication-gate fixtures). Four quadratic-identity tests were
already introduced in the preceding cycle; this revision integrates that result rather than claiming new tests.

The proposition does not identify the source-frame sampling law, justify a variance estimator for the joint
contrast, or establish normal coverage. Fixed benchmark uncertainty and task-population inference remain distinct.
The existing empirical derivative band remains exploratory. No empirical performance results were inserted into
the PDF, and no GPU/model inference, candidate execution or Monte Carlo sweep was started.

## Priorities and readiness

1. Close the deterministic provenance cases above and declare the intended joint-inference target/source model.
   Acceptance for inference remains an independently reviewed variance/limit argument preserving the original
   target and addressing source-log dependence, execution noise and recovery selection. Later operating-characteristic
   and competitive-router studies remain queued; do not replace them with the historical pilots.
2. Integrate validated comparisons, figures and limitations into the manuscript once the corresponding gates are
   resolved. The present paper remains a theory draft with prospective empirical methods.
3. Complete independent reproduction, author-approved metadata and the final source/PDF/supplement package.

**Overall submission readiness remains about 60% (change: 0 percentage points; judgment range 50–65%).**
The unchanged category stages **75/75/50/50/25** under weights **25/20/30/15/10** give **58.75** before rounding.
The paper integration and verified checker repairs advance work within those milestones; they do not close the
joint-inference/comparator, complete-result integration, or reproducibility/metadata/package gates. This is neither
a submission nor authorization to submit.
