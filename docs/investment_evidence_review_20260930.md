# Scientific evidence and further-investment review — 30 September 2026

The author asked whether the compute investment has produced positive signals, whether design and evaluation were correct, and whether further investment is justified. This is a retrospective evidence review and lead recommendation, not an experimental release, new outcome analysis, confirmation reuse, or scheduler change. Three parallel read-only agent reviews supported the lead review; they are not external peer review.

## Judgment

There are credible synthetic estimation gains and real differences between executor policies. There is no validated demonstration that history-aware routing beats a competent prompt-only/fixed comparator, no established real-agent DR accuracy advantage over replay, and no equal-budget practical savings result. Do not expand compute on the strength of the current evidence. A capped, discriminating development study and a narrower evaluation-methodology paper remain defensible; open-ended infrastructure iteration or searching for a favorable result do not.

The end-to-end design was not adequate. The lead owns the omitted feedback/opportunity checks, comparator weakness, delayed execution-path qualification, and target confusion described below. Independent auditing has made several numerical/evaluator components more defensible, but it does not retroactively validate the whole experiment.

## Evidence that has survived review

| Evidence | Finding | What it does not establish |
|---|---|---|
| Archived real coding executions | Independent recount of raw live records reproduces learned 468/660 = 70.91%, always-small 403/660 = 61.06%, always-large 473/660 = 71.67%, on the same 330 tasks | The +9.85 percentage points against small do not identify adaptation: the learned reachable policy is fixed L-S-L. The -0.76 points against large neither establish equivalence nor noninferiority |
| Resource trade-off | Learned used 1.1545 large calls and 12.9594 recorded model seconds per episode versus 1.3 and 13.8040 for always-large | Roughly 11.2% fewer large calls and 6.1% less recorded model time are descriptive, with slightly lower observed success; not matched-quality monetary/energy savings |
| Known-truth synthetic estimation | DR/IPW RMSE ratios 0.742–0.934 in 12 rows; honest-split repeated-training MSE ratios 0.555–0.922 | Additional fitting/acquisition cost prevents an equal-budget efficiency claim; DR-minus-fresh coverage 0.933–0.957 is not universal nominal calibration |
| REQ027 synthetic logger mechanism | 4,000 study records independently recounted; exact variance reduction 0.003125 agrees with observed reduction | Not agent trajectories or physical execution independence. Nominal 95% Wald coverage 93.95–94.75% remains limited |
| Evaluation controls | Seaborn baseline has 2 declared target failures/248 preserved passes; reference has 250 declared passes. Latest Requests parser rejects two P2P failures despite a masked shell exit 0 | One Seaborn issue is not 250 tasks, and control discrimination is not model competence |

Sources: [scientific diagnosis](scientific_diagnosis_20260920.md), [raw-derived live summary](../results/code_routing/analysis/frontier_live.csv), [synthetic evidence table](../results/v2_sim/evidence_table_20260921.md), [REQ027 review](theory_feedback_20260927_req027_decision.md), [v10 control diagnosis](req030ag_v10_control_failure_decision_20260930.md).

## Negative evidence and design defects

The original pilot checked feasibility and nondegenerate success but omitted informative feedback and consequential routing opportunities. Of 660 learned episodes, 542 stopped after the first call and 104 of those submissions failed hidden tests. The later TRAIN-only H/P tree diagnostic selected identical S-L-L routers under its frozen one-SE rule; the more complex history rule's favorable development value is not a validated effect. These findings limit the tested harness and learners; they do not prove that all history dependence is useless.

The class-tailored DR estimate is 0.614871 versus fresh success 0.651515, a -3.66-point discrepancy. Independent action/probability and arithmetic checks do not resolve sampling variation, execution drift, or inference assumptions. Across the common five deterministic policies, donor replay's mean absolute discrepancy was 0.016061 versus DR's 0.018235; this does not support real DR superiority, nor establish replay superiority from one noisy reference cohort. Primary joint branch/log uncertainty remains unresolved.

Recent failures include avoidable release/integration defects and incompatible controls. Job 27941865 actually obtained an RTX PRO 6000 allocation and passed runtime and all eight image/source checks. Its Requests control requires network behavior prohibited by the frozen sandbox; no model was loaded and none of 16 planned episodes ran. Calling this a resource-access problem or a model failure would be incorrect. Passing isolated local tests did not adequately qualify the full released path.

The archive records 13,164 retained log/live/branch/pilot model calls, excluding environment construction and unrecovered original executions. A reported loss/recovery of 665 original completions prevents certifying the entire original execution/retention law. No complete consumed-compute or monetary ledger was reconstructed in this review. Requested Slurm time, physical GPU time, model calls and money must remain distinct.

## Correction of the lead's target interpretation

The [21 September v2 protocol](experiment_protocol_v2.md), sections 1 and 3–4, and [26 September lead plan](scientific_lead_resumption_20260926.md), “Fixed research questions and current findings,” explicitly distinguish:

1. The archived MBPP/HumanEval fixed-benchmark branch/log inferential target, which cannot be replaced by a selected-prefix or iid-population target.
2. The prospective SWE-bench strict-resolution H/P study, with matched initial action, learner class and resources.

The [29 September amendment](req030ag_target_alignment_amendment_20260929.md) correctly prohibits transporting SWE-bench competence or outcomes into the archived MBPP/HumanEval estimand. It overreaches when treating that archived target as the sole prospective H/P benchmark. The v10 decision's instruction that the next empirical release *must* return to MBPP/HumanEval likewise does not follow from the governing prospective protocol. No cited author instruction in those notes establishes such a replacement.

This review retracts that inference and the corresponding rationale in the handoff/results. SWE-bench development is not intrinsically off-target for the prospective v2 study. The two questions must be named separately, and neither closes the other's evidence gap. The control-blocked classification and closure of v10 remain intact; this correction neither reopens that cohort nor authorizes a replacement or changes either frozen endpoint. Existing no-retry, isolation, and CONFIRM restrictions remain binding.

## Further-investment recommendation

Do not use past expenditure or the manuscript's length as a reason to continue. Before scaling, require one coherent prospective development contract with a fixed total resource cap and stopping rule: exact full-path correct/broken/missing-output evaluator controls; comparable competent executors; informative deployable feedback and consequential decision opportunities; matched H/P and strong fixed comparators; independent terminal scoring; explicit task/family execution units and attainable contrast precision. Qualification results may reject the design; they must not be used to tune exposed outcomes or silently select a favorable task cohort.

If those prerequisites cannot be satisfied within the cap, stop empirical expansion and finish a narrower methodological/critical-case report. If they pass, the next study should discriminate a practically meaningful effect with prespecified uncertainty, not merely generate more calls. An adequately measured null remains a useful result; an inconclusive result is not a mandate for indefinite spending. This is advice to the author, not a new run specification or a decision to pause/delete the existing monitor.

Overall preprint readiness remains **55%, change 0 percentage points, range 45–65%**. It measures package completion, not the chance of a positive effect, acceptance, or investment return. Remaining milestones: coherent competent-agent comparisons with justified uncertainty; empirical/manuscript reconciliation; independent reproduction and author-approved submission package.
