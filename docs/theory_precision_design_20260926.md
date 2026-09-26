# Precision audit for the prospective fixed-task comparison

**26 September 2026; lead derivation and deterministic planning audit, not run authorization.**
This follows the [complete-block note](theory_replicated_block_inference.md) and keeps the same fixed-task
terminal-resolution target. The bounds below use standard Hoeffding concentration, not a new general
inference theorem. Numerical half-widths are planning illustrations, **not adopted scientific effect,
equivalence or noninferiority margins**. Neither worst-case bounds nor passing algebra fixtures establish
practical precision. No archived inference is repaired.

## 1. A tighter score range for the actual policy pair

Retain the complete-block note's independently frozen, bounded nuisance functions, valid logging marginals,
terminal payoff Y in [0,1], deterministic target routers, common initial action S, and at most two eligible
decisions. The logger chooses each of the two actions with probability 1/2 at every eligible decision.
An absorbed decision is a common no-op with probability one. Policies and nuisance fits remain frozen
outside every scored observation. Stochastic targets, other propensities and other horizons need their
own bounds.

On a nonabsorbed second decision, put I = 1{A1=S}, q1_pi = Q1_pi(H1,S),
q2_pi = Q2_pi(H2,pi2(H2)), and J_pi = 1{A2=pi2(H2)}. Equation (6) of the complete-block note becomes

    phi_pi = q1_pi + 2 I (q2_pi - q1_pi) + 4 I J_pi (Y - q2_pi).

Every q lies in [0,1]. If I=0 the score is q1_pi; if I=1,J_pi=0 it is
2 q2_pi - q1_pi; and if I=1,J_pi=1 it is 4Y - 2q2_pi - q1_pi. Hence

    -3 <= phi_pi <= 4.

With absorption after the common first action, cancellation of the padded nuisance term gives
q1_pi + 2I(Y-q1_pi), which is in [-1,2]. If no first choice is eligible, the common absorbing outcome
has range [0,1]. Thus the bound covers all paths under this contract. It is narrower than the earlier
deliberately coarse [-6,7], which remains valid.

Now evaluate both policy scores on the **same logged trajectory**, as in REQ-024. If I=0 their difference
is q1_H-q1_P in [-1,1]. If I=1 and both select the same second action, their difference has absolute
value at most 3: when that action is observed it is -(q1_H-q1_P)-2(q2_H-q2_P), and otherwise it is
-(q1_H-q1_P)+2(q2_H-q2_P). If the targets disagree, binary A2 matches exactly one of them. When it
matches H, their difference is

    phi_H - phi_P = 4Y - 2(q2_H+q2_P) - (q1_H-q1_P),

and when it matches P it is

    phi_H - phi_P = -4Y + 2(q2_H+q2_P) - (q1_H-q1_P).

Both lie in [-5,5]. Absorption yields absolute difference at most 1. Consequently the block-average
offline contrast lies in [-5,5], the fresh contrast in [-1,1], and their calibration difference in [-6,6].
These bounds do not require the two nuisance fits to be equal or correct. Their mean identities still
require the original marginal/support assumptions. They do require the scores to share the logging
trajectory and targets to share the initial action; unrelated marginal score samples do not get this bound.

The nonabsorbed expressions are affine in the five variables (q1_H,q1_P,q2_H,q2_P,Y) for each discrete
assignment/policy pattern. Checking their binary vertices therefore checks the entire unit cube, not
only binary nuisance estimates. The 512 vertices attain marginal extrema [-3,4] and contrast extrema
[-5,5]; absorption must be checked separately. This is a mathematical support calculation, not coverage
simulation or proof of an execution law.

## 2. What the finite confidence guarantee costs

Let alpha=.05 and jointly report the three contrasts (fresh gain, offline gain, calibration discrepancy).
Apply Hoeffding directly to each complete-block contrast with alpha/3, then take a union bound. With range
width w in (2,10,12), an untruncated half-width bound is

    h(B,w) = w sqrt(log(6/alpha)/(2B)).
    B_sufficient(h,w) = ceil(w^2 log(6/alpha)/(2h^2)).

Intersection with the known parameter ranges preserves coverage and may shorten a reported interval.
These counts guarantee the stated untruncated half-width under the full independence contract. They are
**sufficient worst-case counts, not necessary sample sizes, power calculations, or a lower bound on what
variance-adaptive methods could achieve**. The constants are floating numerical evaluations of an exact
analytic expression, not outward-rounded interval certificates.

| Illustrative half-width | Fresh gain, w=2 | Offline gain, w=10 | Calibration, w=12 |
|---|---:|---:|---:|
| .10 | 958 | 23,938 | 34,470 |
| .05 | 3,830 | 95,750 | 137,880 |
| .02 | 23,938 | 598,437 | 861,749 |

For comparison, the original four-coordinate rectangle with equal alpha/4 allocations and support widths
(13,13,1,1) has untruncated contrast half-width multipliers (2,26,28) times sqrt(log(8/alpha)/(2B)).
At h=.05, its sufficient counts are (4,061,686,164,795,788). Tightening coordinate ranges to (7,7,1,1)
instead gives (4,061,198,947,259,849). Direct contrast bounds exploit shared-score algebra and avoid the
additional loss from separately bounding coordinates. This direct construction covers these three named
contrasts; it does not automatically cover additional policy-specific discrepancies or an entire catalog.

One complete block with J fixed tasks, n_log logging episodes/task and n_H,n_P fresh episodes/task uses
J(n_log+n_H+n_P) trajectories before training, additional baselines, grading retries or restoration work.
For the illustrative minimal n_log=n_H=n_P=1 and J=20, the h=.05 fresh bound alone costs 229,800
trajectories; simultaneous calibration precision costs 8,272,800. J=20 here is arithmetic, not a frozen
task list. These are trajectory counts, not tokens, seconds, prices, dollars or energy. Increasing the
number of tasks inside an arbitrarily dependent complete block does not improve this range-only bound.

**Lead decision:** do not release a complete-panel replication batch merely because REQ-024 passes tests.
The present distribution-free certificate does not supply a feasible real-agent plan. This finding is
against treating complete-block replication as the default practical solution, although the conditional
theory remains correct. A lower-variance real-agent design may be feasible; adequate execution-covariance
evidence on a competent target harness does not yet exist.

## 3. A fixed-task alternative and its stronger execution assumption

For a prospective alternative, partition the fixed task list into prespecified groups g, with fixed
nonnegative task-mass weights lambda_g summing to one. A group may be a single task or an entire family.
Within a group replicate, allow arbitrary dependence among its fixed tasks and among log/fresh scores.
Let C_gr be the weighted within-group contrast, with range width w and mean theta_g. Require all group
replicates to be mutually independent, identically distributed within each group across r=1,...,R_g,
and to have the same valid marginal execution laws as before. The groups may have different distributions
and different means theta_g.

    theta_hat = sum_g lambda_g (sum_r C_gr / R_g)
    E theta_hat = sum_g lambda_g theta_g
    Var(theta_hat) = sum_g lambda_g^2 Var(C_g1) / R_g.

If R_g>=2 and repetitions are identically distributed within group, replacing Var(C_g1) with its
within-group sample variance is unbiased. Between-group dispersion is not a replacement for this execution
variance, and R_g=1 does not produce an unbiased empirical within-group variance estimate. These identities
alone do not justify a Wald interval; an asymptotic regime and its calibration must still be specified.

For the same three-contrast family, weighted Hoeffding gives a simultaneous half-width bound

    h = w sqrt{ log(6/alpha)/2 * sum_g lambda_g^2/R_g }.

Proof: the independent summands lambda_g C_gr/R_g have range widths lambda_g w/R_g;
the sum of squared widths is w^2 sum_g lambda_g^2/R_g. Apply the bounded-sum inequality to each contrast
and union-bound the three errors. No random-task sampling or equal task means are used. For J equally
weighted independent tasks and R replicates/task the factor is 1/(JR), rather than 1/R under arbitrary
dependence of all J tasks inside each complete block. Balanced R must still be an integer: R is the
ceiling of the sufficient total count divided by J. This preserves the fixed-task target; it does not
convert the benchmark into an iid population sample or permit task/family train-test leakage.

The efficiency gain is purchased by the **stronger independence contract**, not by renaming records.
For example, if C_gr=theta_g+U_r with a bounded common period shock, a naive independent-task calculation
understates the common-noise variance by a factor J when weights and R are equal. Independent RNG labels,
task IDs and passing code tests cannot rule out this dependence. Task/family grouping alone does not remove
cross-family server or period shocks. Arbitrary unmodeled cross-group dependence returns the analysis to
a coarser independent block or demands a different justified sampling design.

This is not a new untested idea in the synthetic workstream: the archived
[fixed-score validation](../results/v2_sim/coverage_fixed_score_20260921/summary.md),
[replication sensitivity](../results/v2_sim/replication_sensitivity_20260921/summary.md), and
[honest-split study](../results/v2_sim/honest_split_coverage_20260921/summary.md) already use within-task
replication under their generator's independence assumptions. Their reported coverage departures remain
evidence against assuming that unbiased variance estimation or more repeats automatically calibrates
Wald tails. The present work supplies a conservative concentration comparison and highlights the real
execution contract still missing; it does not supersede those studies or justify repeating their cells.

**Next discriminating design question:** determine which independent execution unit can actually be
enforced under a competent fixed-target harness, then obtain separately authorized development information
about its covariance. Keep groups, all repeated seeds and any branch records together for splitting and
inference; never manufacture independence in the archive. Neither this alternative nor a model run is
frozen or authorized here. A scientific precision/margin and realistic resource cap remain open.

## 4. Verification and status

DTR-REQ-025 assigns Claude only deterministic calculation setup: reproduce the score-corner extrema,
absorption cases, table and weighted independent-group formula with exact finite fixtures and pinned source.
Codex owns the derivation and design decision. No Monte Carlo, model calls or empirical-coverage claim.
This note has lead algebra review; an implementer's fixture verification is not independent mathematical
peer review. It is not yet integrated into the manuscript.

Attribution: the bounded-sum inequality is Hoeffding (1963), as cited in the
[reviewed complete-block note](theory_replicated_block_inference.md#attribution). The score identity is
the established longitudinal DR identity used there. The contract-specific range simplification and
precision arithmetic do not claim a new general estimator or concentration inequality.

Full-project readiness **55%, change 0 percentage points, range 45–65%**. Largest remaining milestones:
competent fixed-target comparison with valid inference; final empirical/manuscript synthesis; independent
reproducibility, author-approved metadata and submission packaging.
