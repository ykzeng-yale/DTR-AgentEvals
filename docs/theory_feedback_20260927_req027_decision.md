# REQ-027 lead acceptance and primary-logger review addendum

27 September 2026 UTC. Codex accepts REQ-027 as **synthetic DEVELOPMENT
contrast-score evidence**, with the resource-enforcement deviation below. It is
not a full agent-trajectory simulation, real-model execution, CONFIRM release,
logger adoption, or evidence of practical cost savings.

## Provenance and independent validation

The [design](req027_primary_logger_mc_20260927.md) was frozen at `722cba6` before
sampling. The dedicated Mac mini Codex worker completed 2,000 studies in each
of two cells, with 40 fixed tasks and four independent score draws per task.
Both logger comparisons use shared frozen predictions, paired common random
numbers and the same fixed-task target. The [unaltered archive](../results/v2_sim/req027_primary_logger_mc_20260927/)
contains the original source, pre-run manifest, compatibility manifest, exact
truths, deterministic checks, all 4,000 study records, summaries and resource
receipts. The complete transfer archive had SHA-256
`e845b269e43c4e8fa4da783a9f4ac931acc94d0b4b135e4316016127fbe37a1c`.

The lead read the sampler and compatibility wrapper, verified all 12 run-manifest
hashes, ran the read-only worker verifier, and independently reconstructed every
saved summary statistic and row-level coverage/length field. The
[independent recount](audits/req027_lead_recount.py) reports
[8,070 numerical comparisons](audits/req027_lead_recount_20260927.json), maximum
absolute discrepancy below `9e-18`. It also independently derives the exact
estimator variances from the frozen Bernoulli score law. This recount does not
replay individual random score draws; raw records are study-level summaries.

| Synthetic cell | Exact target | Fixed-S variance | Half-S variance | Paired variance difference (MCSE) | Wald coverage, fixed / half |
|---|---:|---:|---:|---:|---:|
| eta = 0 | 0 | 0.00328930 | 0.00638063 | 0.00309132 (0.00017545) | 0.9425 / 0.9450 |
| eta = 0.2 | 0.1 | 0.00290972 | 0.00605708 | 0.00314736 (0.00016464) | 0.9395 / 0.9475 |

The exact variance differences are both 0.003125. Monte Carlo estimates agree
with that prediction at their reported precision. All four bias estimates are
small relative to their Monte Carlo standard errors; that is not an equivalence
test. Nominal 95% Wald coverage ranges from 93.95% to 94.75% (MCSE about 0.5
percentage points). This does not validate nominal coverage in the intended
agent study. Conservative Hoeffding coverage is 1 in all cells, with interval
lengths 0.85894 and 1.71788, illustrating the looseness of the stipulated bounds.
No variance failure occurred. Both fixed-task and within-task repetition rules
are synthetic assumptions, not demonstrated physical independence.

The first launch failed **before sampling** because macOS rejected `RLIMIT_AS`.
The preserved compatibility manifest predates the successful run and pins a
wrapper retaining the CPU limit and low process priority but replacing the
unavailable address-space limit with RSS monitoring every 100 studies. Thus the
2-GiB ceiling was **monitored, not enforced by the OS**. Reported sampling took
0.60628 seconds, peak RSS 20.75 MiB, with 40 passing resource observations. These
are worker records; the lead did not independently monitor the remote host.
The numerical evidence is accepted with this disclosed execution deviation;
future resource qualifications must state the enforcement mechanism in advance.

## Mathematical review disposition and corrections

The [separate Codex mathematical review](audits/primary_logger_remote_20260927/review.md)
is an independent agent review, not external human peer review. Its seven source
pins match the repository at `3fd6f33`. Its standalone finite-check source was
retrieved with its exact SHA-256 and replayed locally, reproducing the recorded
output hash. The original hash-pinned notes and REQ-025 record are retained
unchanged; this addendum governs their interpretation.

1. **Shared predictions (F2):** the bound `E[D_g^2] <= 4 d_g` and zero score
   contrast on target agreement require the shared-q convention. Separate
   predictions add the term `E[(q_H-q_P)^2 1{active agreement}]` to that bound.
   The true-effect bound by disagreement probability does not require shared q.
2. **Comparator support (F3):** the fixed-S logger supports frozen SS and SL
   schedules. LS and LL, and any target choosing L initially on positive target
   mass, need separately supported logging or fresh evaluation. Required fresh
   calibration is distinct from OPE support. The earlier blanket statement about
   a selected fixed schedule needing separate logging was too broad.
3. **Original task masses (F4):** for original weights `w_j`, a partition into
   positive-mass groups must use `lambda_g = sum_{j in g} w_j` and
   `C_gr = sum_{j in g} (w_j/lambda_g) C_jgr`. This preserves the original target;
   assigning equal weights to unequal groups generally does not. Zero-mass
   groups contribute nothing and can be omitted.
4. **Operational law (F5):** a future manifest must specify cache/server state,
   evaluator state, period effects, timeouts, reservations and concurrent-work
   handling. Reset, record or group shared dependencies at an enforceable
   independent unit; RNG namespaces and task labels alone do not prove this.
5. **Fair bound comparison (F7):** the original width-10 full-logger contrast
   permits separate nuisance fits. Sharing both first-stage and terminal action
   predictions permits width 8; the deterministic-S logger has width 4. The
   earlier width-10 versus width-4 comparison combines two design choices.
   REQ-027 shares predictions in both loggers and isolates the initial-action
   randomization in its deliberately simple score law.

F1/F6 algebra and counts are accepted conditionally; F8's fixed-task/frozen-policy
scope remains. Nuisance sharing is not universally variance-optimal. This study
does not select a real-agent logger, margin, comparator allocation or sample size.
It supports the narrow variance mechanism and motivates measuring prospective
variance only after competent execution and the physical inference unit are
qualified. More sampling of these same cells would not resolve those bottlenecks.

## Current execution decision

REQ-027 is closed at this evidence level; no repeat run is requested. REQ-026B's
initial residency implementation failed lead adversarial checks: pressure was
not enforced on reuse, retries could consume mutated history, unloading erased
routing history, and replies after deadline could be accepted. Claude is
correcting only its two owned files. A bounded mechanics probe remains held until
those corrections and hook contracts pass lead review. Existing archives and
CONFIRM remain unchanged.

Full-project readiness **55%, change 0 percentage points, range 45–65%** under
the unchanged rubric. Largest remaining milestones: competent fixed-target
comparison with valid inference; final empirical/manuscript synthesis;
independent reproducibility and author-approved metadata/submission package.
