# Independent adversarial mathematical review

**Project:** `ykzeng-yale/DTR-AgentEvals`  
**Pinned commit:** `3fd6f33f4b33a2450468940f4e731bfd2c68b246`  
**Review date:** 2026-09-27 UTC  
**Primary files:** `docs/theory_primary_logger_candidate_20260926.md` and `docs/theory_precision_design_20260926.md`  
**Context files:** `docs/theory_replicated_block_inference.md`, `docs/theory_extensions.md`, `docs/theory.md`, `docs/experiment_protocol_v2.md`, and `docs/submission_requirements_20260926.md`

## Verdict

I found **no theorem-level algebra error** in the two primary notes under their stated contracts. Independent finite enumeration reproduces:

- the common-first-action score identity and pointwise cancellation of the first-stage nuisance;
- the primary-logger score support `[-1,2]` and shared-trajectory contrast support `[-2,2]`;
- the original two-decision score support `[-3,4]` and separate-nuisance contrast support `[-5,5]`;
- absorption behavior;
- the disagreement second-moment and effect bounds under the shared-prediction convention;
- the stated direct Hoeffding counts and trajectory arithmetic; and
- the weighted independent-group concentration factor.

The primary logger preserves the fixed-task history-aware-versus-prompt-only terminal-success target **only conditionally**: both frozen policies must start with S; all assigned episodes and absorbed outcomes must remain; second-stage assignment must actually be one-half; predictions must be frozen outside evaluation; and eligibility, reservation, stopping, endpoint, and conditional execution kernels must agree with the target/fresh laws. It does not preserve support for the full comparator catalog.

The notes should therefore receive **conditional mathematical acceptance, not protocol adoption**. Four contracts need to be made explicit before implementation: the shared prediction needed by the disagreement-variance bound, exact preservation of original task masses in grouped replication, comparator-specific support, and physical enforcement of cache/period/kernel independence. The smaller bounds are valid planning bounds; they are not evidence of empirical feasibility, interval calibration, useful effect, or coverage.

## Findings and classifications

### F1. Core primary-logger identification is correct — no theorem defect

At an active second decision, with deterministic target action `a_pi`, behavior probability `1/2`, frozen `q(Z,a)` and `J_pi=1{A=a_pi}`,

```
phi_pi = q(Z,a_pi) + 2 J_pi {Y-q(Z,a_pi)}.
```

Conditioning on `Z` and averaging over the actual randomization gives

```
E(phi_pi | Z)
  = q_pi + 2(1/2){E(Y | Z,A=a_pi)-q_pi}
  = mu_pi(Z).
```

The distribution of `Z` is the target distribution because the target and logger execute the same deterministic first S block. The score is therefore unbiased for each fixed policy and their contrast without a correct outcome model. This conclusion is about the fixed externally trained policies and fixed tasks; it does not average over policy retraining or a task population.

The first-stage cancellation is pointwise. Writing the two-stage score after the common first action as

```
q1 + (q2-q1) + 2 J(Y-q2),
```

the `q1` terms cancel, leaving the displayed one-stage score. This remains true under misspecification because the known logging probability, not nuisance correctness, supplies the mean identity.

At absorption after S, the terminal outcome is already observed under both policies. Assigning both scores `Y` gives contrast zero and does not invent a second action. A missing terminal outcome is not absorption and remains outside this argument, consistently with the core theory.

### F2. The disagreement second-moment bound needs the shared-q convention stated locally — missing-assumption clarification

Lines 35–39 of the primary-logger note use `D=0` off active disagreement. That is true under the shared action-value prediction defined at line 15. It is not true for arbitrary separate policy-specific predictions, even though separate predictions preserve unbiasedness and the global `[-2,2]` contrast support.

A finite counterexample has `h=p=0`, `q_H=0`, `q_P=1`, `Y=0`, and the logged action equal to 0. Then `d_g=0` but `D=1` and `D^2=1`, contradicting `E(D^2)<=4d_g` if the shared-q convention is dropped.

**Precise correction:** introduce lines 35–39 with “Under the shared-q convention above.” For separate predictions, a valid replacement is

```
E(D_g^2)
  <= 4 d_g
     + E[(q_H-q_P)^2 1{active agreement}],
```

and the same right-hand side bounds the variance. The true-effect bound `|V_g,H-V_g,P|<=d_g` does not depend on nuisance sharing.

### F3. Comparator support is correctly limited, but the fixed-schedule sentence is overbroad — design limit / harmless conservatism

The deterministic-S logger has behavior probability zero for an initial L action. An initial-L target therefore violates sequential support; no weighting or outcome regression repairs that identification failure. Always-large and any task-level initial router that chooses L on positive target mass need direct fresh evaluation or a separately supported logger.

The strongest development-selected fixed schedule does **not automatically** require a separate logger. If it is frozen as SS or SL, the proposed primary stratum supports it; if it is LS or LL, it does not. Fresh evaluation may still be required by the protocol regardless of OPE support.

**Precise correction to primary-note line 11:** say that the selected fixed schedule needs separately supported logging *when its frozen initial action is L, or when the prespecified provenance/allocation plan otherwise forbids reuse*. This does not change the primary-pair theorem.

### F4. The grouped fixed-task formula needs an explicit task-mass mapping — missing definition

The weighted estimator and Hoeffding factor in precision-note lines 101–128 are correct if the group weights are the masses of the original fixed-task estimand. The note calls them “task-mass weights,” but it should state the mapping formally.

For original fixed-task weights `w_j`, require

```
lambda_g = sum_{j in g} w_j,
C_gr = sum_{j in g} (w_j/lambda_g) C_jgr.
```

Then `sum_g lambda_g theta_g` equals the original target. Without this constraint, regrouping can change the estimand. For example, with three equally weighted tasks and groups `{1}` and `{2,3}`, assigning group weights `(1/2,1/2)` changes task weights from `(1/3,1/3,1/3)` to `(1/2,1/4,1/4)`.

This is a target-definition gap, not an error in the displayed variance or concentration algebra.

### F5. Kernel equality and group independence require an operational cache/period contract — missing assumption / design limit

The notes acknowledge scheduling and common-period effects, but adoption needs an executable rule. Model residency, prompt/result caches, warmup, server queues, memory pressure, hard-timeout clocks, evaluator caches, filesystem state, and concurrent workload can make the next outcome depend on earlier episodes or on the logger stratum. If that state is neither reset nor included in the recorded history and randomized design, the conditional kernel used for identification changes.

Likewise, the group-level factor

```
sum_g lambda_g^2/R_g
```

requires mutual independence of every group replicate. If `C_gr=theta_g+U_r` with the same period/cache shock `U_r` shared across groups at replicate index `r`, equal task weights and equal replication give actual common-shock variance `Var(U)/R`, while a false independent-task calculation gives `Var(U)/(JR)`, understating that component by a factor of `J`.

**Required operational addition:** before adopting the grouped design, freeze the physical execution unit, cache/reset policy, server/evaluator version and state, interleaving/randomization schedule, concurrency rule, timeout origin, and block retention rule. Either isolate group replicates so the mutual-independence claim is credible, record shared periods as coarser blocks, or use a covariance method justified for the resulting dependence. Assignment metadata must not be exposed to the model or environment unless it is part of the target history.

### F6. The range and Hoeffding calculations are correct and sharp for their contracts

Independent enumeration gives the following supports:

| Contract | Score support | Offline contrast support | Width |
|---|---:|---:|---:|
| Original two-decision logger, separate bounded nuisances | `[-3,4]` | `[-5,5]` | 10 |
| Deterministic common-S primary logger, shared action-value prediction | `[-1,2]` | `[-2,2]` | 4 |

For the primary logger, on disagreement the two possible contrast expressions are

```
2Y-q_H-q_P
-2Y+q_H+q_P,
```

which attain `-2` and `2` on unit-cube vertices. On agreement, shared predictions make the two scores identical. Thus `E(D_g^2)<=4d_g`, and `Var(D_g)<=E(D_g^2)`. The true conditional effect is zero on agreement and at most one in magnitude on disagreement, proving `|V_g,H-V_g,P|<=d_g`; weighted fixed-task averaging preserves the corresponding bound.

With three two-sided contrasts and equal error allocation `alpha/3`, Hoeffding gives

```
B = ceil{w^2 log(6/alpha)/(2 h^2)}.
```

At `alpha=.05`, `h=.05`, the independently reproduced counts are:

| Width | Sufficient complete blocks |
|---:|---:|
| 2 | 3,830 |
| 4 | 15,320 |
| 6 | 34,470 |
| 10 | 95,750 |
| 12 | 137,880 |

The primary calibration count implies `34,470 × 20 × 3 = 2,068,200` trajectories under the illustrative one-log/one-fresh-per-policy, 20-task complete-block design. These are valid sufficient range-only counts, not necessary sample sizes or coverage evidence.

### F7. The original precision ranges are valid but not optimal under optional nuisance sharing — harmless looseness

The `[-5,5]` full-logger contrast is sharp when the two policies may use separate bounded `q1` and `q2` fits, as REQ-025 allows. Under known randomization, one could instead deliberately use a common bounded first-stage prediction and one common terminal action-value prediction. Independent enumeration then gives a full-logger contrast support of `[-4,4]`, width 8. This remains unbiased even if the common prediction is misspecified, provided it is frozen independently of evaluation.

This observation does not invalidate REQ-025: its width-10 result is a safe bound for the broader separate-nuisance contract and never claimed optimality. It does mean that the comparison between 95,750 and 15,320 blocks combines a logger change with a nuisance-sharing choice. The deterministic common-S logger still has the smaller width-4 bound. Actual variance can move in either direction, so nuisance sharing should be chosen prospectively rather than from evaluation outcomes.

### F8. Fixed-task, population, and retraining targets remain distinct — design limit correctly retained

The formulas identify a weighted mean over the prespecified fixed tasks, conditional on frozen policies, features, nuisance fits, harness, and resource rules. More tasks inside one arbitrarily dependent complete block do not increase the independent sample size. Treating task identities as iid population draws, averaging over policy retraining, or selecting a new policy after examining this evaluation stratum would define a different target and invalidate the displayed concentration contract.

The grouped alternative can preserve the fixed-task target through the mass mapping in F4. It does not by itself justify new-task-population inference, task/family train-test leakage, Wald calibration, or a practical replication count.

## Target-preserving savings assessment

The proposed logger removes a genuinely avoidable first-stage importance weight for the primary frozen pair. It preserves that pair's fixed-task target because the two policies and the logger all execute S initially and because absorption is retained. It also preserves OPE support for other frozen policies whose first action is S and whose only later action is among the randomized S/L choices.

It does **not** preserve:

- OPE support for initial-L policies;
- the cost or support of the full comparator catalog;
- calibration to fresh executions if caches, period effects, eligibility, reservations, stopping, endpoint extraction, or other kernels differ;
- independence merely by splitting tasks into named groups; or
- inference for a retrained-policy or new-task population target.

Therefore the reduced width and count are legitimate primary-stratum planning results, but the project must budget separate fresh/support strata and enforce the kernel/independence contracts before claiming net savings. No empirical feasibility, effect, equivalence, or interval-coverage conclusion follows.

## Recommended disposition

1. Accept the score identity, sharp supports, disagreement effect bound, Hoeffding arithmetic, and weighted-independent-group formula conditionally.
2. Amend the primary note with F2's shared-q qualifier and F3's comparator-support wording.
3. Amend the precision note with F4's exact original-task-mass equations.
4. Add F5's operational cache/kernel/period contract to any proposed manifest before implementation.
5. Keep the logger candidate unadopted until comparator allocation, scientific margin, competent executor, physical independent unit, and covariance evidence are frozen.
6. Do not treat deterministic checks as empirical coverage validation or manufacture a practical sample-size conclusion from the worst-case table.

Full-project readiness remains **55%, change 0 percentage points, range 45–65%**. A competent fixed-target comparison with valid inference, final empirical synthesis, and independent reproducibility plus author-approved submission packaging remain open.

## Source integrity

All files were retrieved from `raw.githubusercontent.com` at the pinned commit. Total source size was 134,823 bytes, below the 8 MiB cap.

| Source | Bytes | SHA-256 |
|---|---:|---|
| `experiment_protocol_v2.md` | 26,987 | `90630ea9f8b0f6a79d32acb8e8279dab51ae7e360b2a60901f128c223cc698ca` |
| `submission_requirements_20260926.md` | 5,169 | `c3a3c49c8153e822718b9ea25ba050d51be677543340784b24896184b15e06cf` |
| `theory.md` | 42,626 | `471080a6dffe3e7e22b80629e91f1fece09096e39b84a0cac4dd2b6ef496e690` |
| `theory_extensions.md` | 16,531 | `4af3d709c318cf76227875b6b531dc037059f4de1b1ba043fb302f139da7eb44` |
| `theory_precision_design_20260926.md` | 11,519 | `6303403a35b4046e423cf7a5255799b495bd5ea104868d3c6bae91d5fefb2897` |
| `theory_primary_logger_candidate_20260926.md` | 8,674 | `a432fd51ee082ba48b51b40808d93e4a927243ee1a0b1c0d25075587c9eeb031` |
| `theory_replicated_block_inference.md` | 23,317 | `473be9a9a7bebeb3a7c6d2df31bf07a6230b5160d34f10979b7f1a64a7695255` |

The accompanying `check_receipt.json` records exact URLs, commands, hashes, resource observations, and machine-readable findings. `independent_checks.py` is the standalone standard-library finite enumeration used for the algebraic checks; it does not import or rerun project fixtures.
