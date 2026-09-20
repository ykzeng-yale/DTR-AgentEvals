# Scientific diagnosis and revised priorities

**20 September 2026; reviewed source and archived observations at `338425b468cb301f785b0b5daef4a796951f8f55`.**
The author asked the lead agent to own the scientific judgment because the experiment workstream largely
implements the lead's designs. This response changes our interpretation and next steps, rather than asking that
workstream to obtain more favorable results. The primary reviewer reproduced three deterministic diagnostics;
separate reviewers examined learning/feedback, calibration, and theory/estimand alignment. No new observations,
model/tool/candidate executions, bootstrap or Monte Carlo runs were made. Hidden-test outcomes are archived
measurements, not freshly executed validations. All analyses below are **retrospective diagnostics**.

## Decisions by the scientific lead

1. **Do not claim demonstrated history-adaptive improvement.** The fitted policy deploys a fixed repair schedule.
   Passing the original always-small comparison does not isolate the value of learning or adaptation.
2. **Treat feedback/eligibility and the restricted learner as design limitations.** Our pilot gate checked
   feasibility and nondegenerate success, but did not require informative feedback or enough consequential
   routing opportunities. We should have identified this before freezing the study.
3. **Keep the original metrics and unfavorable results.** The learned-versus-large result is inconclusive;
   retrospective penalty changes cannot rescue the prespecified improvement claim. A future objective needs
   a justified resource unit and an acceptable success loss chosen before evaluation.
4. **Keep the observed calibration discrepancy as an open scientific question.** Reproduction finds no mismatch in the inspected
   class-tailored actions, probabilities or estimator calculations. The observed discrepancy remains; finite
   execution variation and changes in the execution mechanism have not been separated.
5. **Retain the fixed-benchmark primary inferential target.** The lead owns its unresolved joint-inference
   argument. Further iid-population extensions and repetitive checker fixtures are lower priority than solving
   that target, interpreting these findings, and integrating the empirical case study.

This narrows the current paper's empirical claim to an evaluation design and a critical coding-agent case study.
The long-term routing question remains in scope. A positive improvement finding is not a completion requirement;
adequately testing the question and honestly reporting the result are.

## What the existing evidence actually says

### 1. The learned policy does not tailor actions within reachable stages

Independent reconstruction reproduces all **17 frozen policy entries** from TRAIN. Both benchmark-specific
initial cells select large. Every reachable first-repair cell after large selects small, including the missing-cell
fallback; every reachable second-repair cell after small selects large. Off-path table differences do not create
on-policy tailoring. All **660** live paths are consistent with **large → small → large**, with visible-pass
absorption: **542** stop after large, **16** after large/small, and **102** reach large/small/large.

The initial key has only benchmark identity, so the learner cannot choose the initial model by task difficulty
within either benchmark. Later keys omit most of the transcript and all but the last action. Correct implementation
of the tabular backward recursion does not establish that this summary is sufficient to optimize full-history
value. Known-randomization evaluation and restricted-policy learning have different requirements.

The randomized CONFIRM log also shows substantially stronger average first-candidate performance for large:
**917/1,320 versus 746/1,320** successes. This is evidence about average initial performance, not universal
dominance at every history. Using large initially is therefore a plausible major source of the learned policy's
advantage over always-small; the baseline comparison cannot attribute that advantage to adaptation.

**What argues against a simple instability explanation:** some cells are very sparse (one reachable HumanEval
cell has 1 small versus 3 large observations), and seven live decisions use a missing policy-cell fallback.
However, exhaustive deletion of each TRAIN task in turn leaves both initial choices and all reachable first-repair
choices unchanged. One deletion changes one reachable second-repair choice. These are 231 deterministic TRAIN-only
sensitivity refits, not a bootstrap interval or policy-selection exercise. Sparse-cell optimism and insufficient
state representation remain plausible limitations, not established causes of the live contrast.

### 2. Visible-pass stopping hides failures from the routing policy

Certification leaves **94/591** tasks with zero visible checks, including **60/330** CONFIRM tasks. On those
60 tasks, all **120 learned** and **120 always-large** live runs stop after the first call; **61** and **65**,
respectively, fail hidden tests. Passing the remaining load/parse check is not evidence of semantic correctness.
The reference-certification procedure controls one kind of false alarm; it does not guarantee useful coverage.

Across all learned live episodes, **542/660 (82.1%)** stop at the first call. **104** of those visible-pass
submissions fail hidden tests: **54.2% of all 192 learned-policy failures**. The policy has no later decision at
those histories. Only **118/660 (17.9%)** episodes reach a first repair. Thus this setting permits some repair
evaluation but is a weak test of rich sequential adaptation.

These counts demonstrate a limitation of eligibility, not the counterfactual claim that continuing would fix
the failures. Hidden-test results must remain outside the deployed routing rule. We will retain all zero-check
tasks in the original analysis. Better visible checks or a different stopping rule would define a **new harness**,
requiring a prospective protocol and fresh evaluation rather than retrospective correction of this archive.

### 3. The utility result is a trade-off, not a metric bug

The following means were independently reconstructed from all six live policy cohorts and checked against the
saved success/utility summaries. Each policy has 660 episodes on the same 330 tasks.

| Quantity | Learned fixed schedule | Always-large | Learned minus large |
|---|---:|---:|---:|
| Hidden-test success | .709091 | .716667 | −.007576 |
| Original utility | .672667 | .677667 | −.005000 |
| Small calls per episode | .178788 | 0 | +.178788 |
| Large calls per episode | 1.154545 | 1.300000 | −.145455 |
| Total calls per episode | 1.333333 | 1.300000 | +.033333 |
| Completion tokens per episode | 118.8288 | 122.5682 | −3.7394 |
| Recorded model wall seconds per episode | 12.9594 | 13.8040 | −.8446 |

The archived nominal success interval for learned-minus-large is approximately **[−.0292, .0141]** and the
utility interval **[−.0271, .0171]**. These indicate an unresolved comparison, not equal performance. Their
sampling justification remains part of the inference review. Both policies have **451 first-candidate successes**;
their final counts are **468 versus 473**, corresponding to net repair gains of 17 versus 22. These are separate
realized trajectories, not matched continuations from identical generated prefixes.

Under the original unitless penalties (.01 small, .03 large), the learned schedule saves **1.7/660** penalty units
while losing **5/660** successes. Scaling both penalties by s gives the retrospective equality
`learned-minus-large utility = (−5 + 1.7s)/660`, crossing zero at **s = 50/17 ≈ 2.9412**. Holding the small
penalty at .01 instead gives an empirical large-penalty crossing of **.064375**. These are descriptive
revaluations of two frozen policies, not an optimized frontier, a new primary endpoint, or the policy that would
be learned at those penalties. Tokens, latency, money and energy remain distinct.

As a separate TRAIN-only diagnostic, removing call penalties changes only one unreachable policy cell; the
reachable large/small/large schedule stays unchanged. Thus the chosen penalty alone does not explain the
learned policy's lack of adaptation. Future studies should compare success and measured resources explicitly,
including a prespecified acceptable success loss or common hard budget and competent fixed-schedule controls.

### 4. The class-tailored discrepancy survives independent IPW reconstruction

For class-tailored success, **IPW = .610606, DR = .614871, live = .651515**. Independent reconstruction of the
original three-fold tabular fit, IPW, task-paired means and saved standard errors agrees within **1.1×10⁻¹⁶**.
There are zero failures in the inspected policy/state/action/draw/probability/model checks across **2,640 log**
and **660 class-tailored live** episodes. This establishes agreement with the recorded design and calculations;
it does not verify an unobserved server state or prove interval validity.

The DR adjustment narrows the success gap by **.004265** relative to IPW. Therefore misspecified Q fitting
alone cannot explain the disagreement with fresh live outcomes. Estimated IPW call penalties also match the
live mean exactly. The two recorded timeout/truncation exceptions are failed live outcomes and cannot explain
an artificially inflated live success rate.

| Contribution to total success | Terminal at stage 0 | Terminal at stage 1 | Terminal at stage 2 | Total |
|---|---:|---:|---:|---:|
| Log IPW | .540909 | .051515 | .018182 | .610606 |
| Live | .557576 | .074242 | .019697 | .651515 |
| Log minus live | −.016667 | −.022727 | −.001515 | −.040909 |

About **41%** of the IPW discrepancy occurs in outcomes that terminate before adaptive repair. A different
diagnostic using the hidden score of every first candidate finds log-initial-small **.565152** versus
class-tailored live **.590909**, a **2.576 percentage-point** gap before routing diverges. These two diagnostics
have different outcome definitions and are not interchangeable causal decompositions: terminal stage-0 success
requires stopping after the first call, while first-candidate success also counts initially correct candidates
that fail visible validation and continue.

HumanEval contributes **−2.111 percentage points** and MBPP **−1.553 points** to the overall DR success gap.
No single task explains it: deleting any one task leaves the DR gap between **−4.116 and −3.356 points**.
These localizations are retrospective descriptions; they do not identify serving drift, causal mediation, or bias.
The nominal class-tailored discrepancy is a useful warning, but one pointwise exclusion among six correlated
policy comparisons and two related endpoints does not establish systematic miscalibration or estimate coverage.

**Lead judgment:** keep this as an unresolved observed calibration discrepancy. Do not choose an estimator
because it agrees with this live cohort. A discriminating future test needs independent, time-interleaved
log/reference repetitions, with shared configuration and a common initial-action diagnostic, prespecified
discrepancy tolerance, and valid uncertainty in both quantities. If disagreement persists beyond that criterion,
the practical calibration claim fails until the discrepancy and the relevant estimation, execution or inference
assumptions are resolved.

### 5. Replay and branches test narrower questions than our headline

The prior replay reconstruction finds common-five mean absolute discrepancies **.016061** for donor replay and
**.018235** for DR against noisy live means. This is not a demonstrated DR accuracy advantage. Four of those
five deterministic live targets are fixed schedules; only class-tailored varies its action by failure class.
Most episodes absorb early. The comparison therefore provides limited evidence about the particular error from
substituting histories under adaptive routing. Its finite donor fallback remains a limitation. The exact adaptive
counterexample proves that replay *can* fail, not that it caused the observed empirical discrepancies. Retain the
positive control and this unfavorable/non-superiority empirical comparison.

The branch intervention and log numerator agree on **stay-large versus stay-small after a logger-reached first
failure**. The log uses a global normalized ratio; its numerator requires the forced model at both remaining
eligible stages. The branch point is **.120000**, the log point **.134654**. These do not evaluate class-tailored,
the learned small-then-large repair sequence, or whole-policy occupancy. Fresh seeds do not eliminate dependence
on the shared source frame. The exploratory derivative scale remains unvalidated as a standard error.

Our additional iid source-population theorem is a scoped mathematical result, but its positive-per-task arm and
prefix conditions do not hold for this fixed benchmark. Developing it did not settle the primary analysis.
**The lead now fixes the primary target as repeated execution conditional on the original benchmark tasks**,
preserving the initial 4/4 blocks, all zero-prefix/zero-arm tasks, prefix selection, and shared-log dependence.
The complete source/selection/execution variance argument remains open and belongs to the theory lead.
Conditioning instead on the entire realized prefix frame can support a separately labeled local branch-mean
analysis, with the realized log estimate fixed; it cannot silently replace the primary calibration question.

## Concrete next work and acceptance criteria

**Concurrent experiment reply reviewed before publication.** Commit `4f9abe49925060cb551d6cbb4900348f65984d68`
arrived during this review with a separate `why_null.py` diagnosis. Its point arithmetic was independently
reconstructed, and two independent reviewers agree that its strongest explanations are unsupported:

- The claimed .000278/0 **oracle ceilings** use estimated terminal-success cell contrasts, positive-part
  selection and logger occupancy. At stage 1 the logger still determines the later action. These are neither
  true effects nor upper bounds on whole-policy utility gains against always-large. The aggregation omits
  benchmark identity, which the actual learner can use. A simple logical counterexample shows the problem:
  with two equally likely benchmark strata, large succeeding only in the first and small only in the second,
  the pooled action contrast and this statistic are zero, yet benchmark tailoring succeeds with probability 1
  against always-large's .5. This is an exact illustration, not an assertion about the observed tasks.
- The approximate .024 marginal value standard error is not the paired gain's precision. It cannot establish
  that no good router could have produced a detectable benefit. No detected heterogeneity likewise does not
  prove the absence of effect modification or vindicate the theoretical assumptions.
- The stage effects concern different logger-selected populations. Their episode-independent standard errors
  omit task dependence, and adding their squared standard errors omits shared-task/episode covariance. The
  stage gradient is not a validated contrast at common histories.
- Its .088235 large-penalty crossing is algebraically correct **when both penalties scale at 1:3**, making small
  .029412. It does not contradict the .064375 fixed-small crossing above. The diagnostic uses the live frontier
  as well as the log, despite its original log-only label.
- Hidden-test success cannot be a deployable stopping signal. Such a change would leak held-out verification
  information through eligibility and would need to be identified as an oracle-only environment.

The lead has corrected A6 in `experiments/README.md` and `docs/experiment_results.md`, preserving the original
script/output and commit for auditability. **The historical output's oracle-ceiling/power and theory-vindication
interpretations are rejected.** The worker's next reporting task also includes correcting these generator labels
and explicit cost-scaling/resource units in a new derived output, without overwriting the archived diagnosis.
This review demonstrates why agreement with a convenient explanation is insufficient scientific validation.

| Priority and owner | Next work | Acceptance and decision consequence |
|---|---|---|
| P0, theory/manuscript lead, no new model or Monte Carlo runs | Integrate the diagnostic claims and empirical nulls; supply the fixed-benchmark source/selection/execution argument, or clearly delimit the claims it cannot support. | Every reported interval names its random units and conditioning set; initial blocking, nuisance fitting, shared source log, prefix selection and zero contributions are accounted for. Independent review must accept the argument before a joint interval is called validated. If it cannot be justified, retain descriptive comparisons and state the inferential limit. |
| P1, experiment agent, deterministic reporting only | Add the reachable-policy classification, visible-check/eligibility counts, and success/resource table to the current study summary, using the pinned diagnostics below. | Reproduce all counts/means, preserve the original objective/cohorts and label retrospective work. Call the learned policy a learned fixed repair schedule; make no adaptive-benefit, equality, DR-superiority or validated-coverage claim. Report contradictory evidence to the lead rather than selecting a favorable subset. |
| P2, lead designs; worker prepares only | Write a prospective amendment for informative feedback, explicit zero-check handling, task/failure features, competent fixed and published-router controls, and interleaved calibration. No collection yet. | On development data only, establish consequential repair opportunities, supported actions and reproducible feedback; specify feature availability, sparse-cell fallback, task partitions, endpoint/resource margin, multiplicity and achievable precision before collecting new evaluation data. If those conditions are infeasible, narrow the empirical contribution instead of seeking a favorable benchmark. |

For a targeted future repair study, the interventions of interest are **large/large, small/large and small/small**
continuations on a common development first-large-failure prefix frame, with replicated outcomes and explicit
costs. This would distinguish the learned repair choice from always-large more directly than the current
stay-small/stay-large branches. It remains a local intervention study, not proof of global policy value.
Model execution and repeated statistical operating-characteristic studies stay queued under the existing compute
deferral. The current CONFIRM outcomes cannot be reused to select a new policy and then count as its independent test.

## Reproduction and evidence boundary

Run from the repository root; the scripts read pinned Git blobs and write only the requested new output file:

```sh
python3 docs/audits/diagnose_routing_338425b.py --output work/routing_diagnosis_338425b.json
uv run python docs/audits/diagnose_class_tailored_338425b.py --output work/class_tailored_diagnosis_338425b.json
python3 docs/audits/diagnose_utility_338425b.py --output work/utility_diagnosis_338425b.json
python3 docs/audits/check_why_null_4f9abe4.py --output work/why_null_audit_4f9abe4.json
```

Committed outputs: [routing/feedback](audits/routing_diagnosis_338425b.json),
[class-tailored calibration](audits/class_tailored_diagnosis_338425b.json), and
[utility sensitivity](audits/utility_diagnosis_338425b.json). The primary reviewer reran all three scripts;
routing and calibration outputs match the independent reviewers' reports exactly. The utility derivation was
independently checked. These are analysis reproductions of existing records; they do not add independent outcome
observations or establish repeated-sampling coverage. Earlier replay and branch reconstructions remain linked
through [replay feedback](theory_feedback_20260920_replay.md) and [source-model feedback](theory_feedback_20260920_source_model.md).
The frozen experiment protocol, raw archives and 31-page PDF remain unchanged in this diagnostic update.

The additional [concurrent-A6 audit](audits/why_null_audit_4f9abe4.json) pins `4f9abe4`. The primary reviewer
reran its separate arithmetic reconstruction and exactly matched the independent report. The no-bound
counterexample above was also checked by direct two-stratum enumeration. No substitute interval was derived.

**Full-project readiness is now about 55% (change: −5 percentage points from the last issue #4 checkpoint;
judgment range 45–65%).** Weights remain 25/20/30/15/10. The lead conservatively lowers independent validation
and reproducibility from 50 to 25; stages **75/75/50/25/25** give **55.00** before rounding. The concurrent
`8382b3c` report discloses a provenance-writing defect and a repair previously claimed but not fully applied;
combined with A6's invalid upper-bound and inference claims, accepted result-level validation is too incomplete
for the previous assessment. Completed independent reconstructions remain valid evidence. This reduction is not
because a router failed to win, not a count of audit items, and not an automatic endorsement of the workstream's
reported 116-item audit, which has not been independently reconciled. The workstream's written weighted total
54.25 is an arithmetic error; its category scores actually total 55.00, giving the same rounded estimate.

The `8382b3c` source diff separates offline task checks from the download-backed report, clarifies replay-cohort
wording, removes the remaining timeout assertion and renames a superseded figure without changing its bytes.
These changes are integrated and source-inspected, not independently runtime-tested in this diagnostic turn;
the report's 101 tests and 116 open items remain workstream-reported. We preserve both of its derived artifacts
and the raw archives. The three largest gaps are valid inference and scientifically adequate comparisons, full
empirical manuscript integration, and independent final reproduction/metadata/submission packaging. No submission made.
