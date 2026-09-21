# Lead acceptance of the occupancy sensitivity

**21 September 2026, 08:48 UTC cycle.** Reviewed
`c25bee027564c34aaee44d826048a67ec50d83b9`. **DTR-REQ-003 verdict: accept the requested four-cell calibrated
occupancy sensitivity; finish the already queued consolidated gate table, then resume REQ-002 qualification.**
No further kernel retuning, occupancy cases or covariance controls are requested.

## Checked evidence

All four affected tests pass locally. The separate
[independent audit](../scripts/audit_occupancy_c25bee0.py) uses two-repair closed forms without worker imports
to reconstruct every expected M/T/U/D total and target ratio. **All four cells and 56 exact scaling/ratio
checks pass**. It also checks the initial-action table, expected counts and the four reported log probabilities
against a 90-digit truncated convolution. The [audit record](audits/occupancy_audit_c25bee0.json) includes the
explicit totals, not only success flags. The worker's broader reported 167-test suite was not rerun.

At n=330 the baseline expected prefix count is 5907/5=1181.4. Applying alpha=940/1969 gives exactly 564;
every expected total scales uniformly and theta, both arm log ratios and Delta remain unchanged. The new
artifact implements the earlier independently reviewed invariance, rather than adding a new theoretical
claim. Source inspection and the baseline-restoration test agree that the core initial-action table is
preserved. The source probabilities and empirical archives have not been retuned.

The worker acknowledges all prior corrections: full-artifact covariance ratio range including seven adverse
rows, n-specific probability logs, small-frame versus census-use labels, numerical underflow, and ideal
full-state restoration. Those replies resolve the pending interpretation questions. One minor precision
clarification: the log probabilities are **computed using 60-digit intermediate arithmetic and serialized
as ordinary floating-point numbers**; the JSON itself does not retain 60 digits. Its saved values agree with
the independent high-precision calculation at their displayed precision. No output regeneration is needed
just for that wording.

This checks expected occupancy and exact calibrated means. It does not match the archive's task heterogeneity,
dependence or sampling-fraction distribution, validate historical state restoration, or establish coverage
or power. The four-row sensitivity currently covers the calibrated law; do not imply it is a completed
drifted-law operating-characteristic study. Preserve the baseline and adverse frozen-rule results.

## Concrete next handoff

**DTR-REQ-003, P1:** publish the single consolidated table already queued. For each accepted control/model,
logger, fixed-task, covariance and branch artifact, give its exact commit/path, independent-review status and
remaining limitation. Separately list the undelivered full sampler, estimator adapters (including DR/outcome
regression and failure controls), interval/coverage checks, independent on-policy reference uncertainty and
final precision/resource choices. Attach acceptance criteria and ownership; use existing implementations
where they qualify rather than restarting them. Do not mark a gate complete based only on an exact mean,
second moment, a reported test suite or a planned fixture. A no-new-execution gate table is sufficient for
this next handoff; additional peripheral proofs are not needed.

Then **resume DTR-REQ-002** with the selected evaluator and existing M01–M03 and resource/runtime gates;
the lead will review those concrete qualification artifacts. REQ-003 remains running for its outstanding
implementation/inference work, without blocking that priority switch. **REQ-001 is completed.** Acknowledge
these existing-ID statuses in the next committed reply. No GPU/model/verifier/Monte Carlo or duplicate jobs
are launched by this review, and separately authorized work remains unaffected. Direct-main commits use
Yukang Zeng <ykzeng2019@gmail.com> as both author and committer.

**FULL-project readiness: 55%, change 0 percentage points, judgment range 45–65%.** Stable weights and stages
unchanged. The requested sensitivity is independently validated, but no new empirical outcomes, useful
validated interval, manuscript pages or submission were added. Top milestones: useful validated inference
and adequate comparisons; statistical validation and final empirical synthesis; independent reproducibility,
author metadata and submission packaging.
