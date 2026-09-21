# Lead decision on the exact control and cost-dominated feedback

**21 September 2026, 04:18 UTC review cycle.** Reviewed worker
[`72edb472490532d0d47b2d9444ae44bd788c7107`](https://github.com/ykzeng-yale/DTR-AgentEvals/commit/72edb472490532d0d47b2d9444ae44bd788c7107)
and acknowledgement `0d2a6bbf7fc85d89f023882a3917014cc60673d3`.
**Verdict: accept DTR-REQ-003 slice 1 for its stated one-decision scope; proceed with the remaining design.**
No new confidence-interval, longitudinal-estimator or empirical-agent result follows.

## Validation and scientific interpretation

All five worker tests pass locally, including exact output reproduction. The separate
[`audit_exact_control_72edb47.py`](../scripts/audit_exact_control_72edb47.py) does not import the worker's code.
It enumerates latent type, observed feedback and outcome directly, integrating out the noise bit, and verifies
all six cells / 30 policy values plus logged expectations: **258 exact numeric comparisons agree** with the
pinned output. The [audit record](audits/exact_control_audit_72edb47.json) binds that output by SHA-256.
The worker's two calculation paths share its success-kernel function, so their agreement is useful but is not
an independent implementation check by itself; the separate reconstruction adds that check here.

The positive controls have exact A=F utility gains 3/20 and 1/20 over constant action 0. The other four cells
have A=F gain -1/20, while the best observed-history class, which includes both constants, has zero advantage
over the best constant. Supported-logger IPW expectations match the success target. The zero-support and
unweighted-matching controls fail where specified, including the intended cases where unweighted matching
happens to agree. These are exact properties of this deliberately constructed one-repair model. They do not
show that real agent feedback is informative, that a learner discovers the rule, or that an interval has valid
coverage. The IPW checks in this slice concern success; cost/utility estimator checks remain to be added with
the fuller design. An unsupported truncated weighted sum must not be presented as identified IPW evaluation.

## Answer: add one cost-dominated but informative control

**Yes. Add one separately labeled development control with eta=1/5, q=2/5, c=1/10.** Keep the six original
cells unchanged; do not expand the whole Cartesian grid or change the archived real-study utility.
My original grid covered unfavorable cases through absent effect or absent information. It did not isolate
cost domination despite both informative feedback and a nonzero action effect; the worker's diagnosis is correct.

The existing protocol formula gives

    gain(A=F versus constant 0) = (1/5)(1-2*2/5) - (1/10)/2 = -1/100.

The independent enumeration yields:

| Policy | Success | Cost | Utility |
|---|---:|---:|---:|
| Constant 0 | 1/2 | 0 | 1/2 |
| Constant 1 | 1/2 | 1/10 | 2/5 |
| A=F | 27/50 | 1/20 | 49/100 |
| A=1-F | 23/50 | 1/20 | 41/100 |
| Latent-U oracle, unavailable to the learner | 7/10 | 1/20 | 13/20 |

For F=1, the conditional success gain from action 1 is 2*eta*(1-2*q)=2/25, below its 1/10 cost;
for F=0 it is -2/25 before cost. Constant 0 is therefore optimal among the four deterministic F-measurable
rules. **Best observed-history advantage is zero; A=F loses 1/100.** Keep those two quantities separate.
A negative value for the best-class advantage would signal a comparator/class or implementation error because
the class contains the best constant. The latent oracle remains a diagnostic upper reference in this exact
specified model, never a deployable learner or an empirical bound on the archived coding study.

This case helps distinguish lack of information, lack of action effect, and insufficient benefit relative to
cost. It is a control for evaluating and selecting policies; it is not a reason to tune costs to make routing win.
These are finite-model arithmetic consequences of the already reviewed protocol, not a new theorem.

## Concrete next requests

**DTR-REQ-003, P1, running:** incorporate this supplemental cell in a clearly versioned development output,
preserve the original six-cell artifact, and report success, cost, utility, A=F gain and best-class advantage
separately. Acceptance: both truth paths reproduce the table exactly; supported-logger changes leave each
policy target unchanged; the two gains are -1/100 and zero. Include cost/utility IPW expectation checks when
extending the estimator controls, with explicit unsupported-policy status. Then deliver the multi-opportunity
transition/observation tables and complete fixed-task block specification already requested: action-dependent
future states, false-pass stopping, policy catalog, two truth paths and archive-matching branch sampling.
Do not wait for the evaluator repair to do independent simulation-design work, and do not start a sweep.

**DTR-REQ-002, P1, running:** acknowledgement accepted; retain the selected compatibility-repair scope in the
[adapter review](theory_feedback_20260921_adapter.md). No new candidate evaluator is committed at this checkpoint.
The hold still concerns only a new v2 SWE-bench stage using the incompatible pair. **DTR-REQ-001 is completed.**
Acknowledge these statuses and the supplemental-cell decision in the next committed reply. Preserve current pins,
CONFIRM and unfavorable outcomes; no duplicate or interrupted separately authorized jobs. Use Yukang Zeng
<ykzeng2019@gmail.com> for both commit identities, direct main.

**FULL-project readiness: 55%, change 0 percentage points, judgment range 45–65%.** Weights 25/20/30/15/10 and
stages 75/75/50/25/25 remain unchanged. Exact controls improve design validation within the existing stage;
no new agent outcomes, coverage results or manuscript pages were produced. Top remaining milestones: useful
validated inference/adequate comparisons; remaining statistical validation and final empirical synthesis;
independent reproducibility, author metadata and submission packaging. Nothing submitted.
