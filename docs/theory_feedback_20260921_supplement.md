# Lead acceptance of the supplemental exact control

**21 September 2026, 05:18 UTC cycle.** Reviewed worker `9a1412a258df86a117b8f19defb467e8566ca5dc` and
acknowledgement `6f594d81f2b633bf9eff3a7b2d506465df27040d`. **Verdict: accept the supplemental control and
cost/utility expectation checks; proceed to finite repair tables and complete fixed-task blocks.**

## Checked evidence

All nine exact-control tests pass locally. The separate
[`audit_exact_supplement_9a1412a.py`](../scripts/audit_exact_supplement_9a1412a.py), importing no worker code,
reconstructs the conditional means directly and verifies **385 exact numeric comparisons over seven cells and
35 policy values**, including the three component expectations for every policy/logger pair. The
[hash-bound audit](audits/exact_supplement_audit_9a1412a.json) records the result. The six-cell artifact remains
byte-identical to the prior reviewed file; original empirical results/manifests, source pins and manuscript are unchanged.

The added informative but cost-dominated cell has A=F success 27/50, cost 1/20, utility 49/100 and gain -1/100.
Best-class advantage remains zero, with constant 0 optimal. Both requested quantities are correctly separated.
All supported pairs reproduce success, cost and utility. The 14 unsupported policy/logger rows are flagged;
success and utility fail to reproduce the target there even though cost agrees. These are exact development
controls, not new agent observations, coverage tests or evidence that a real learner finds an adaptive rule.
The reported broader 122-test suite was not rerun; this review ran the nine affected tests and the independent audit.

## Interpretation of cost agreement without full action support

The worker's observation is correct, but calling it only a coincidence understates the known structure.
Here cost is the specified deterministic function c*A, and the missing action is A=0. Every omitted target
contribution to cost is therefore exactly zero. The truncated weighted cost expectation can agree for that
structural reason. Under the fully specified cost model, cost evaluation need not inherit the same support
requirement as an unknown success response. Keep the full-policy support failure explicit for the primary
success/utility comparison; equality of one component is not a test that identifies the others. Conversely, do
not label the known-zero cost component itself unidentified solely because the success target lacks support.
No further control cell is needed for this point, and no general support theorem is claimed here.

## Next scientific deliverable

**DTR-REQ-003 remains running for the finite repair model and fixed-task block design.** The simple one-repair
control and supplemental cell are now accepted; do not expand or re-report them instead of building the remaining
model. Supply explicit transition and observation tables, including action-dependent future states, observed
feedback versus latent correctness, false-pass stopping, and the history needed for a sufficient-state recursion.
For each planned core cell, report exact best-fixed and best-observed-history utility, their difference, decision
occupancy and false-pass termination probability. Require agreement of full-history enumeration and the separate
recursion to the protocol tolerance; changing only the logger must preserve frozen-policy truth. This will expose
whether a cell actually tests sequential adaptation, rather than merely repeating the one-step control.

The archive-matching block specification must separately retain all fixed tasks, eight source episodes/task,
initial 4/4 allocation, later known propensities, zero-prefix task blocks, fixed-size prefix sampling and fresh
continuations. Preserve the ratio-of-expected-totals branch target; neither selected-task averages nor a single
realized-frame target replaces it. Deliver the specification and exact checks before any Monte Carlo sweep.
These requirements are already in v2; this review changes no primary endpoint, cost metric or source pin.

**DTR-REQ-002 qualification is acknowledged as queued behind this design work.** The selected evaluator remains
f7bbbb2 for development qualification, with M01–M03 and runtime/resource/precision gates open. **DTR-REQ-001 is
completed.** Acknowledge supplemental acceptance and the next table/block artifact in the next committed reply.
Do not duplicate workloads or stop separately authorized jobs. All commits remain direct to main as Yukang Zeng
<ykzeng2019@gmail.com>, both author and committer.

**FULL-project readiness: 55%, change 0 percentage points, judgment range 45–65%.** Weights and stages unchanged.
Exact design checks advanced within the existing milestone; useful empirical inference and real-agent benefit
remain unresolved. Top milestones: useful validated inference/adequate comparisons; remaining statistical
validation and final empirical synthesis; independent reproducibility, author metadata and submission packaging.
No new manuscript pages or empirical results; nothing submitted.
