# Independent transcript reconstruction and manuscript integration

Review cycle: **20 September 2026, 19:34 UTC**. Reviewed
[`13bad73b586f757463fd1e3e339416155b27ac31`](https://github.com/ykzeng-yale/DTR-AgentEvals/commit/13bad73b586f757463fd1e3e339416155b27ac31)
and its committed reply after the 18:03 UTC issue #4 checkpoint at `35eda5c`.

## The missing-input reconstruction blocker is resolved

An independent reviewer downloaded the public MBPP and HumanEval sources and reconstructed the task file using
reviewed field mappings and canonical serialization. The primary reviewer repeated the downloads and the entire
reconstruction with the archived audit script and reproduced its report byte-for-byte. The **427 MBPP plus 164
HumanEval records** produce exactly **591 tasks** and frozen SHA-256
`23727895971fa4a040198d8770173a4f0c3263a63a9cb1479abc4203bb01c2ce`.
Both source downloads also match the workstream's recorded byte counts and hashes. Task data stays under ignored
`work/`; no third-party data is committed or redistributed by this review.

The audit reconstructs transcript JSON with independently written equivalents of the reviewed prompt functions
and literal constants extracted from pinned source. Reference programs are parsed as syntax to recover signatures,
never executed. All **800 comparisons match in each of the four transcript-hash categories**: parent, branch, parent-durable
and branch-durable, with zero mismatches. These are **200 distinct parent prefixes across 103 tasks**, linked to 800 continuations;
they are not 800 independent prefixes. All task IDs, covered IDs and new report-binding fields also reconcile.

This advances the evidence from workstream-reported reconstruction and independently checked stored links to
**independently reproduced transcript bytes**. It does not rerun models, generated programs, tools, hidden-test
outcomes or runtime-state restoration. Historical pilots remain exploratory. All **20 non-analysis artifacts**
are unchanged, including five historical durable rows across four recovery IDs; those rows remain evidence of
pre-invocation records, not completed lost outcomes. See the [reconstruction audit](audits/reconstruction_audit_13bad73.json)
and [runnable script](audits/check_reconstruction_13bad73.py).

## Accepted checker and reporting changes, with remaining scope stated precisely

The new gate binds both durable decision files and compares the report's task digest to the frozen design digest.
The independent comparison retains the prior 39 cases and adds a missing parent-durable-file case, evaluated at
both pins. All **40 current case expectations** are met, including clean controls and valid ledgered recovery.
The new missing-reference case rejects explicitly. The primary reviewer reproduced the [gate report](audits/publication_gate_audit_13bad73.json)
byte-for-byte. The **43 published gate fixtures** pass. The broader workstream 101-test claim and host-health
statements were not independently rerun here.

Remaining checker boundaries are narrower than the now-resolved reproduction blocker:

- The gate compares the task digest with the design; it does not hash the current task input itself. This review
  independently regenerated and verified those bytes.
- `prompt_helper_revision` hashes four prompt constants. It excludes the prompt/signature/repair functions,
  JSON serialization and Python AST/unparse version; the gate does not check this digest. Record the complete
  reconstruction source/runtime revision if claiming those implementations are bound.
- Durable-file hashes identify snapshots; the production helper/gate still do not compare all per-record
  transcript/state/probability fields. This independent audit checks the actual transcript links. It does not
  claim a complete generic validator or detect new corruption in the saved archive.
- An uncaught `FileNotFoundError` already exits nonzero. Under a workflow that requires successful exit status,
  the intermediate crash was not successful gate acceptance. The new explicit refusal improves diagnostics;
  broader claims about bypassing deletion require evidence of a caller that ignores nonzero exit status.
- The regeneration CLI writes its report to the archived analysis path. The independent audit writes only under
  ignored `work/`; future reproduction commands should similarly use fresh output paths. Moving source URLs
  remain guarded by frozen hashes, which detect drift but cannot restore unavailable old downloads.

The README's retained-call and per-episode GPU-start wording is accepted. The branch hierarchy is clearer, but
“every estimate below” is too broad for raw counts and the disagreement statistic. Previous contradictory claims
about compatibility, replication and timeout harmlessness remain. Exact replacements for the experiments owner:

1. Replace “The two estimates are compatible, which is weaker than agreement” with “The observed point difference
   is −0.0147; the displayed exploratory band does not establish compatibility under a validated sampling model.”
2. Replace the categorical statement that the linearization does not account for replication with “Replicate
   averages enter the statistic; a valid joint variance argument must still justify the source-log, fixed-size
   prefix-selection and continuation-noise components and their dependence.”
3. Replace “every estimate below averages replicates within a prefix and clusters on the task” with “The branch
   contrast averages replicates within prefix and arm; task-level linearization is exploratory. Counts and the
   within-model disagreement statistic are descriptive summaries.”
4. Delete “at this rate they cannot have moved a result”; retain the existing statement that the timeout's effect
   on its episode outcome is not established.

## Theory integrated into the paper

The previously reviewed [source-model note](theory_branch_source_model.md) is now **Section 9.5, Proposition 13**
in the **31-page paper**, with **15 numbered mathematical results and 22 cited references**. It proves a sufficient
bounded iid task-population variance link, retains the branch/log covariance, and gives only an expectation-level
connection for the sampled quadratic estimator. The proof and fixed-benchmark counterexample preserve the distinction
between population sampling and repeated execution conditional on a benchmark.

Independent mathematical review approved the conversion. All 31 pages were rendered and visually reviewed;
the new section, references and later numbering are readable and consistent. Compilation has no warnings or
unresolved references. The selected suite passes **80 tests** (37 root, including 27 exact theoretical cases,
plus 43 gate fixtures). No new theoretical test was needed for the proof-preserving conversion; the existing
three source-model examples were rerun. No empirical performance results are inserted into the PDF.

This result does not establish the archived design's sampling law, handle its zero-prefix/zero-arm tasks by
assumption, prove sampled-quadratic concentration, or validate joint studentization and coverage. Preserve the
protocol's conditional-on-benchmark target as primary; any task-population analysis is a separately justified
secondary claim, not a retrospective relabeling or reason to discard tasks. The next derivation must respect
that target and source-log randomization, branch selection, execution noise and recovery assumptions.

## Priorities and readiness

1. Finish the target-preserving joint variance/limit argument, including concentration and coverage conditions;
   keep the existing empirical band exploratory. Competitive-router and operating-characteristic studies remain
   queued with fixed targets, task-level validation and acceptance criteria from the protocol.
2. Integrate validated empirical comparisons, figures and their limits into the paper, after the corresponding
   inference and analysis gates close; retain null and unfavorable results.
3. Complete remaining reproducibility/source/runtime provenance, reporting repairs, author-approved metadata and
   final source/PDF/supplement packaging. Actual-host writer exclusion and atomic publication remain unverified.

**Overall submission readiness remains about 60% (change: 0 percentage points; judgment range 50–65%).**
Stages **75/75/50/50/25** under unchanged weights **25/20/30/15/10** give **58.75** before rounding. Independent
transcript reconstruction and paper integration are substantive within-milestone advances; the validation category
still lacks independently validated final inference/analyses and reproducibility of the full package. The three
largest gaps remain joint inference/comparators, complete manuscript/result integration, and final reproduction,
metadata and packaging. No new model/candidate/tool execution, Monte Carlo sweep, paid compute or submission occurred.
