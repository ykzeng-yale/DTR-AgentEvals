# Lead review of shared-log contrasts and negative controls

**21 September 2026, 08:19 UTC cycle.** Reviewed the previously inspected but not numerically validated
covariance delivery `b4b074d06a47164d3ef76991dda6ee78a70b2e2e` on main at `7e04762`.
**DTR-REQ-003 verdict: accept the exact covariance calculations; repair the claimed range and interpretation
of the variance benefit.** Preserve all output rows, including adverse contrasts. No new worker response
to `7e04762` was available at the start of this review.

## Independent checks

Seven affected tests pass locally. The separate
[audit](../scripts/audit_contrast_covariance_b4b074d.py) uses pairwise common-action-prefix recursion:
the score product becomes zero after the policies first disagree, while common terminal prefixes contribute
their appropriately weighted squared utility. It imports no worker code. It reconstructs **32 stratum-specific
covariance matrices and all 64 reported contrast rows**, with **320 exact numeric comparisons**, accompanying
standard-error checks and **480 nonnegative principal-minor checks**. The
[hash-bound record](audits/contrast_covariance_audit_b4b074d.json) records results and the adverse cases.
An independent internal mathematical reviewer found no arithmetic blocker. The worker's broader reported
163-test suite was not rerun. These checks validate the frozen synthetic moments, not interval coverage.

The stratum-specific best schedule comparator is selected separately in each observed stratum using exact
kernel truth. It is correctly distinct from the single catalog prompt rule. Neither oracle selection nor
these exact-moment checks represent fitting a policy on finite training data.

## Reporting correction: shared logs can increase variance

Excluding the 16 identical-policy controls, the **48 non-identical contrast rows** have shared-log to
independent-IPW-score standard-deviation ratios **0.704513–1.005759**, not .70–.98. **Seven rows exceed one**,
all at K=4 with the feedback-dependent logger. Both task counts give the same ratio because the common
fixed-task variance factor cancels in this comparison. The audit lists those seven cases.

For a same-log difference, Var(X-Y)=Var(X)+Var(Y)-2 Cov(X,Y). Negative cross-policy covariance can therefore
increase difference variance; the result is not an implementation failure. The worker's upper range omitted
unfavorable cases. Correct the next checkpoint and current summary without overwriting v1 or dropping rows.
Do not claim that common logs uniformly reduce uncertainty.

The denominator in this diagnostic keeps the same two IPW-score marginal laws but sets their covariance
to zero. It is not an on-policy reference variance. Producing two independent logs of the displayed per-policy
size would require twice the logged episode volume; the ratio is not a resource-matched efficiency claim.
When comparing OPE with independent fresh policy execution, the latter's own utility variance and replicate
count must enter. Do not reuse the independent-IPW-score field for that purpose.

## Scientific diagnosis of the negative history-rule contrasts

The exact model separates missing opportunity from a poorly chosen rule. For K=2 with crossing effects:

| Feedback | Frozen history rule minus best prompt schedule | Best observed-history oracle minus best prompt schedule | Oracle minus frozen rule |
|---|---:|---:|---:|
| Informative | +0.0346958 | +0.0346958 | 0 |
| Weak | -0.0163409 | +0.0024885 | +0.0188295 |

All entries are expected **success-minus-call-penalty utility** differences under the specified synthetic
kernel, not observed success-rate differences. They come from the independently checked generator and
contrast artifacts. In the informative cell the simple rule attains the oracle value; in the weak cell,
observable tailoring still has positive potential but the fixed “large after exception” rule fails to use it
well. The K=4 crossing cells show the same qualitative distinction. In the no-crossing controls, the oracle
advantage is zero and the fixed history rule can be strictly worse than the best schedule.

This provides evidence for a rule-design limitation in these exact negative cells and against “no useful
history information exists” as their sole explanation. Sampling noise or inadequate power cannot explain
the sign of an exact mean. The independent moment audit reduces concern about the implemented weighting
as the cause. But this does not identify the cause of the archived real-agent null: its kernels and attainable
policy class are unknown, and a finite-data learner may not attain the oracle. Nor does the result justify
changing utility or tuning on CONFIRM. Retain this frozen weak-feedback rule as an adverse control rather
than replacing it to make the table positive.

## Next discriminating work, same request IDs

**DTR-REQ-003, P1, running:** the core covariance calculation is now accepted. Correct the .70–.98 claim and
acknowledge the distinction from independent on-policy references. Continue the single already requested
n=330 occupancy sensitivity (alpha=940/1969), preserving the baseline. Acceptance remains E[N]=564, uniform
scaling of expected M/T/U/D and unchanged target ratios, with the probability/restoration labels from the
prior review. Do not duplicate completed covariance calculations or enlarge the core grid.

Then deliver one consolidated design/gate table mapping the accepted artifacts to the still-open sampler,
estimator and inference requirements. In particular, do not mark REQ-003 or the empirical study completed
because IPW first/second moments pass: the full sampler, DR/outcome-regression implementations and failure
controls, interval operating characteristics, independent-reference uncertainty and final precision plan
remain distinct gates. Use existing work where present; identify missing components rather than adding
peripheral proofs or new controls. This is a specification/status consolidation, not Monte Carlo authorization.

After that bounded design handoff, **REQ-002 qualification should resume** at the selected evaluator and
existing M01–M03/resource gates. **REQ-001 remains completed.** Acknowledge existing IDs using the agreed
statuses. No new GPU/model/verifier/Monte Carlo or duplicate workload is started by this review; separately
authorized jobs are not interrupted. All new commits use Yukang Zeng <ykzeng2019@gmail.com> as author and
committer, direct main without PRs.

**FULL-project readiness: 55%, change 0 percentage points, judgment range 45–65%.** Stable rubric unchanged.
Independent covariance validation and negative-control interpretation advanced; no empirical observations,
coverage validation, manuscript pages or submission were added. Top milestones: useful validated inference
and adequate comparisons; statistical validation and final empirical synthesis; independent reproducibility,
author metadata and submission packaging.
