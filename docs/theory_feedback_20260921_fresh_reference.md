# Fresh-reference uncertainty and M03 repair review

21 September 2026, 10:48 UTC cycle. Reviewed worker commit
`57baf69696ef9c4907657b8265c2aa3881cb4ed8`. No new model, benchmark or Monte Carlo run.

## DTR-REQ-002: accept the requested checker repair within its stated grammar

The worker acknowledged the strict endpoint and preserved the separate upstream score. Source inspection
confirms separate before/after path coverage, ordered unique markers and rejection of resets inside the run.
The two prior failing probes are now regression cases loaded from the lead's audit. The lead reran all
**28 M03 cases successfully**, including those probes, new-only/mixed positive controls and unrelated-path
rejection. This closes the specific repair request; it is not general shell-safety assurance, acceptance of
real generated scripts, parser conformance or evidence of actual setup preservation. Those existing M01/M03
and isolated-execution gates remain. No further generic checker expansion is requested now.

## DTR-REQ-003: accept the exact fresh-reference moment artifact

The lead independently reconstructed all 24 policy/cell rows by backward conditional utility-moment
recursion, without importing worker code. The comparison uses previously accepted fixed-task IPW moments.
**360 numerical checks passed**, including exact on-policy variances, policy means, fresh/discrepancy scales
and 96 logger/stratum variance ratios. The four affected worker tests also passed; the reported broader
228-test suite was not rerun. [Audit](audits/fresh_reference_audit_57baf69.json), reproducible with
`python scripts/audit_fresh_reference_57baf69.py`.

Under balanced fixed task strata and independent episodes/tasks, with four fresh episodes per task per policy:

| Quantity | n=250 | n=1000 |
|---|---:|---:|
| Fresh policy-mean SD | 0.011655–0.014127 | 0.005827–0.007064 |
| Independent log-minus-fresh calibration SD | 0.021017–0.072756 | 0.010509–0.036378 |

The raw trajectory-IPW/on-policy per-episode **variance** ratio ranges from **1.469055 to 71.637511**.
These are exact synthetic sampling SDs at fixed parameters, not estimated empirical standard errors,
confidence intervals, power calculations or observed resource savings.

An independent internal mathematical reviewer accepted the formulas with the following restrictions.
For a deterministic supported target, write q(h)>0 for the product of logging probabilities of target
actions along a compatible trajectory. Under the same execution law, raw full-trajectory IPW and fresh
execution have the same mean and

\[
\operatorname{Var}_b(WZ)-\operatorname{Var}_\pi(Z)
=E_\pi[(q(H)^{-1}-1)Z^2]\ge0.
\]

Independent fixed-task averaging preserves the ordering at equal per-task episode counts. Independent
log/fresh blocks justify adding their variances. These statements require the written support, common-law,
frozen-policy, independence and finite-moment assumptions. They do not extend automatically to stochastic
targets, DR/OR, centered or per-decision scores, policy contrasts, or resource-matched designs. The worker's
policy-copying logger is valid for this implemented last-feedback/no-key catalog, not arbitrary belief policies.

**Scientific implication:** the new result limits an efficiency claim rather than proving one. For one fixed
policy and equal episode counts, the raw trajectory-IPW estimator loses precision here. Reusing one log for
several policies may still be useful, and adjusted estimators may help, but neither advantage is established
by these ratios. The large upper ratio is explained by rare target-compatible paths under the logger;
it is not a defect in the DTR identification argument or evidence about actual model improvement. Retain
this unfavorable comparison. Do not infer required sample sizes from the ratios without the chosen contrast,
margin, estimator and resource design.

## Next bounded step and acceptance

**REQ-003: adopt r_fresh=4 only as the fixed synthetic validation baseline**, paired with r_log=4. This
specifies the existing simulation design, not the real-agent sample size, precision decision or permission
to launch a sweep. Freeze independent task/policy/replicate stream identities in its manifest; no sharing
between fresh blocks and the logger. Keep n=250/1000 and the accepted cell/catalog scope.

**REQ-002 remains the next external qualification priority** if its host permission is resolved. Its
reported blocker has not been independently resolved here. Meanwhile, the next useful REQ-003 implementation
is the already queued complete-block sampler and estimator wiring, not more moment/control cells. Provide
deterministic scripted-draw fixtures for initial absorption, false-pass stopping, K exhaustion, logged
propensities, full task/replicate retention and empty branch/arm denominators. The branch calibration module's
source allocation remains its separately accepted four-small/four-large design; do not replace it with this
whole-policy reference design. Acceptance requires matching the frozen schemas/targets, retaining all costs
and task blocks, explicit independent streams, and whole-range fallback for the branch design's zero
denominators. Statistical moment/coverage acceptance still requires later authorized repeated validation;
deterministic fixtures cannot establish it. No new Monte Carlo/model workload is requested by this review.

Please acknowledge REQ-001 completed, REQ-002 running with repair accepted and remaining qualification
blocked/open, and REQ-003 running with reference moments accepted. Direct main commits retain Yukang Zeng
<ykzeng2019@gmail.com> as both author and committer. Do not duplicate queued work.

**Full-project readiness: 55%, change 0 percentage points, judgment range 45–65%.** Same rubric and stages.
Exact reference uncertainty and the checker repair advanced; no empirical outcomes, useful validated
intervals or manuscript pages were added. Remaining milestones: useful validated inference/adequate
comparisons; statistical validation and final empirical synthesis; independent reproducibility, author
metadata and submission packaging.
