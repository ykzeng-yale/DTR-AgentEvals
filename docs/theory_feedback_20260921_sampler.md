# Sampler slice 1: transition checks accepted, complete-block analysis gate open

21 September 2026, 12:18 UTC cycle. Reviewed
`f3034c3e461ac7aea23fa522733f234d40c0e215`. No Monte Carlo, model or benchmark execution.

**DTR-REQ-003: accept this bounded episode-generation slice; repair the estimator completeness boundary.**
The lead inspected the sampler and tests and reran all **nine tests successfully**. The reported broader
254-test suite was not rerun. The supplied fixtures cover initial absorption, false passes, exhaustion,
common-first-call cost, recorded assignment probabilities and task/replicate generation.

Additional deterministic checks exercised the sampler's own exhaustive path driver against the previously
independently accepted moment artifacts. For K=2/crossing/informative and K=4/no-crossing/weak, with three
policies per configuration and both strata, **52 checks passed**: path mass, fresh/IPW mean agreement,
fresh variance and feedback-logger IPW variance. This extends the supplied mean checks to second moments.
It is not an independently implemented sampler, an exhaustive audit of every kernel/logger/policy or a
coverage study. [Audit](audits/sampler_audit_f3034c3.json), reproduced by
`python scripts/audit_sampler_f3034c3.py` in the reviewed source checkout.

## Scientific issue: observed rows are not the frozen benchmark

`run_blocks` generates all requested task/replicate rows in its tested use. However, `_task_means` reconstructs
the denominator from whichever rows are passed to the estimator; it has no expected task/replicate manifest.
Both `fresh_estimate` and `ipw_estimate` therefore silently accept incomplete or duplicated inputs. A two-task,
two-replicate toy audit with unit weights gives:

| Supplied rows | Both estimates | Required disposition |
|---|---:|---|
| Complete frozen set | 3/4 | Accept |
| One whole task removed | 1/2 | Reject incomplete analysis input |
| One replicate removed | 1 | Reject incomplete analysis input |
| One replicate duplicated | 2/3 | Reject duplicate key |

These changed values are not statistical uncertainty or a DTR identification failure. They demonstrate an
implementation boundary that can change task weights or select executions if upstream rows are lost. The
current generator was not observed losing rows; the problem appears when assembling/analyzing records.
No archived empirical result is implicated by these synthetic probes.

## Next discriminating check, using the existing REQ-003

Add a validated complete-block entry point using the frozen manifest: expected task IDs and strata,
replicate IDs/count, mode/policy and stream namespace. Require exactly one row per expected key, reject
missing/extra tasks, missing/duplicate replicates and stratum mismatches, and preserve zero-success or
absorbed rows. The public analysis path must invoke this check; a private arithmetic helper may assume it.
Do not normalize over a reduced observed set, fill missing outcomes with fabricated zeros, or filter rows
to make the check pass. Record exceptions as a blocked analysis pending repair, retaining every record.
Acceptance: all three bad probes above fail, manifest-complete input keeps 3/4, and valid generated blocks
retain the exact means/variances already checked. Include an extra-task/stratum mismatch regression.

The supplied `mode:task:replicate` labels distinguish the demonstrated log and fresh collections, but do not
alone prove independent random streams. Before a seeded source is introduced, bind the namespace to the
simulation repetition, kernel/logger configuration, collection role and fresh policy as well as task and
replicate. Distinct labels are a design precondition; independence remains a property of the implemented
draw source and execution law. No seeded sweep is requested now.

Then continue the queued branch sampler slice with its separate 4-small/4-large initial allocation, latent
state-restoration contract and whole-range fallback for global zero denominators. Preserve fixed task blocks
including zero-prefix tasks. DR/OR, per-decision cost, interval/contrast estimation and repeated coverage
validation remain explicitly unwired/open; this review does not mark the full sampler request complete.

REQ-002's prior scorer repair stays accepted within scope; actual qualification and external-host permission
remain open/reported. Acknowledge REQ-001 completed, REQ-002 running/open or blocked, REQ-003 running with this
slice accepted and completeness repair next. Preserve archives and direct-main identity requirements.

**Full-project readiness: 55%, change 0 percentage points, judgment range 45–65%.** Same rubric and stages.
Sampler wiring and exact second-moment checks advanced; no new empirical outcomes, useful validated interval
or paper pages. Remaining milestones: useful validated inference/adequate comparisons; statistical validation
and final empirical synthesis; independent reproducibility, author metadata and submission packaging.
