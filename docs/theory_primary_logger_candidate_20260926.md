# Prospective primary-contrast logger: fix the shared first action

**26 September 2026 — lead design candidate and algebra review only.** This note does not amend the active [v2 protocol](experiment_protocol_v2.md), authorize implementation or collection, repair archives, or replace the fixed-task strict terminal-resolution target. The reviewed [REQ-025 contract](theory_precision_design_20260926.md) remains immutable. Independent mathematical review and competent-harness validation are outstanding. The manuscript is unchanged.

## Motivation and scope

The current v2 logger randomizes both eligible decisions with probability 1/2, while both primary target routers start with S. Its broader support also serves other comparators. For the primary frozen history-aware H versus matched prompt-only P contrast alone, that initial randomization is unnecessary. This is a design tradeoff the lead should have considered before presenting complete-panel replication as the main prospective reference: general-purpose logging spends observations on initial-L trajectories that the primary pair never follows.

A candidate **primary evaluation stratum** instead executes the common S block under exactly the existing eligibility, reservation, budget, stopping and kernel rules. If decision 2 is reached, it randomizes S/L with known probability 1/2. The same initial execution law generates the baseline history for both targets; it is not conditioned on survival, success, feedback informativeness or reaching decision 2. All assigned episodes, including early exits, remain. Policies and bounded action-value predictions are trained outside evaluation and frozen before this stratum begins. This is an evaluation design for a frozen pair, not training data for adaptively choosing that pair.

Initial-L target policies have no support in this stratum. Always-large, initial-only transfer baselines and the strongest development-selected fixed schedule must retain their prescribed independent fresh evaluation and, if their OPE is required, separately supported logging. Fixed quotas, separate provenance and the total resource budget must be specified before collection; post hoc filtering a random mixture is not equivalent to prospectively allocating this stratum. Do not generalize primary-only efficiency arithmetic to the full required study.

## Score, identification and exact ranges

Write Z for the full history after the common S block, including absorption. At an active second decision, let h(Z) and p(Z) be the two deterministic target actions, and q(Z,a) in [0,1] be one frozen prediction of terminal success for each action. Sharing q across the two target policies is natural because no routing decision follows this action. Define q_H=q(Z,h), q_P=q(Z,p), and J_pi=1{A=pi(Z)}. The common-first-action longitudinal score telescopes to

    phi_pi = q_pi + 2 J_pi (Y-q_pi).
    D = phi_H - phi_P.

The initial fitted value cancels exactly because the initial target/logger ratio is one. At an absorbed history set both scores to the same terminal Y, so D=0; no later action or outcome is invented. Missing terminal observations still require the original endpoint/observation rules.

Conditional on active Z, randomization and the common execution kernel imply

    E(phi_pi | Z) = E(Y | Z, A=pi(Z)) = mu_pi(Z).

The marginal distribution of Z is the target distribution after S, including absorbed histories. Thus the equal-task mean of D has expectation V_H-V_P for the same fixed-task target, without a correct outcome model. This proof requires actual assignment probabilities and invariant conditional kernels; a logger-induced resource or scheduling change can violate the latter. It does not establish independence of different episodes.

A marginal score lies in [-1,2]. If h=p, the shared q and shared observation give D=0 exactly. If h differs from p, binary A matches one target and

    D = 2Y-q_H-q_P       when A=h,
    D = -2Y+q_H+q_P      when A=p.

Consequently D lies in [-2,2]. The endpoints are attained on the unit-cube vertices, and the expressions are affine within each action pattern, so these are sharp supports under the bounded-prediction contract. The contrast range remains valid with separate bounded policy predictions, but exact zero on agreement requires the shared prediction convention. Neither statement requires the predictions to be accurate.

Let d_g be the probability, on fixed task g under the common-S history law, of an active disagreement. Then D=0 off that event and |D|<=2 on it, giving

    E(D_g^2) <= 4 d_g,       Var(D_g) <= 4 d_g.

Also the true contrast satisfies |V_g,H-V_g,P|<=d_g, since the conditional success difference is at most one and is zero on agreement. Low disagreement can reduce execution variance but simultaneously limits the attainable success effect. It is not evidence of useful adaptation. These bounds use the unknown population disagreement probability; substituting an observed fraction without uncertainty is not a confidence procedure. The task average obeys the corresponding weighted absolute-effect bound. No task-population sampling assumption is needed.

An optional further logger could execute the common action deterministically on agreement and retain 1/2 randomization only on disagreement. It supports this frozen pair and gives phi_H=phi_P=Y on agreement. It cannot evaluate a subsequently chosen policy that takes the other action there. Because it complicates general comparator support and policy reuse, it is not adopted or needed for the main range reduction above.

## Precision implication and its limits

Under exactly the same independent complete-block assumptions and three-contrast multiplicity allocation as REQ-025, the range widths become 2 for the fresh contrast, 4 for the offline contrast, and 6 for offline-minus-fresh calibration. Fresh runs retain independent execution streams; no restored common-prefix pairing is introduced. For alpha=.05 and illustrative half-width .05, the direct Hoeffding sufficient block counts are respectively **3,830, 15,320, 34,470**. These improve the earlier valid upper-bound counts 3,830, 95,750, 137,880 under its different logger/score contract.

This comparison is between sufficient range-only guarantees, not necessary sample sizes, achieved variance ratios, power or observed cost savings. It still fails to provide a practical complete-panel plan: twenty fixed tasks with one log and one execution of each fresh policy per block would require 2,068,200 trajectories for that illustrative calibration certificate, excluding training and other comparators. The half-width remains illustrative, not an adopted scientific margin. An independently justified fixed-task/group design can replace 1/B by the weighted replication factor in REQ-025, but this note supplies no new physical independence evidence.

## Lead decision and next gate

Retain this as a prospective alternative for independent scientific review, not an active protocol change. It is evidence against treating the earlier very large sufficient counts as an unavoidable property of the primary target. It is not evidence that the full study is feasible. Before adoption, reconcile support and resource allocation for every required comparator, preserve untouched evaluation and operational denominators, demonstrate competent execution and consequential disagreement, and justify the actual execution unit and covariance. Development variance information and a scientific precision/margin are still missing. Do not commission more fixtures or release a model batch merely because this algebra improves a bound.

The calculation specializes established longitudinal doubly robust evaluation and the existing opportunity-reduction theorem, which explicitly permits absorbing a policy-invariant initial block into baseline history. See [Jiang and Li (2016), primary paper](https://proceedings.mlr.press/v48/jiang16.html), [core theory](theory.md), and [extension A](theory_extensions.md). Hoeffding attribution and assumptions are inherited from the [complete-block note](theory_replicated_block_inference.md#attribution). No new general estimator or concentration theorem is claimed. The [exact lead calculation receipt](audits/primary_logger_candidate_20260926.json) checks finite vertices and conditional means; it is not independent peer review or empirical coverage validation.

Full-project readiness **55%, change 0 percentage points, range 45–65%**. Largest milestones remain a competent fixed-target comparison with valid inference, final empirical synthesis, and independent reproducibility plus author-approved metadata/package.
