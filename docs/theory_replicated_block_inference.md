# Prospective inference from replicated complete fixed-benchmark studies

**26 September 2026; prospective mathematical design, independently reviewed internally.** The [review and exact finite checks](audits/scientific_resumption_20260926.json) found no blocking algebra issue after clarifying the restored/source mean assumption. This is not external peer review. This note supplies a prospective observation law for the fixed-benchmark whole-policy contrast and its offline/fresh calibration comparison. A secondary corollary retains the original branch/log ratio-of-expected-totals target. It does not validate archived intervals, release an experiment, or change an endpoint, policy, benchmark, or frozen result. The probability tools are the classical multivariate central limit theorem, delta method, and Hoeffding inequality; no new general inference theorem or empirical coverage result is claimed.

The motivation is the unresolved design-specific covariance and precision gate in [protocol v2, Section 5](experiment_protocol_v2.md), not a request to repeat the archived branch analysis. Complete-study replication may be expensive. Its feasibility and numerical precision must be assessed before a run is proposed.

## 1. Observation law and the independent unit

Condition on a prespecified fixed list of tasks, task weights, all externally trained and frozen policies and outcome regressions, model/harness/verifier versions, resource rules, and the complete randomized execution design. Denote these fixed objects by $\mathcal A$. They are not refitted using the evaluation blocks below. A target conditional on $\mathcal A$ differs from performance averaged over retraining or newly sampled tasks.

A **complete study block** contains every logging and fresh-policy execution required by the design for that same fixed task list. If included, it also contains the complete source prefix frame, prefix sampling, and branch continuations. A block is a prospective experimental unit, not a grouping retrospectively chosen after seeing outcomes. Let

$$
Z_1,\ldots,Z_B\mid\mathcal A\quad\text{be independent and identically distributed vectors in }\mathbb R^p,
\qquad \mu=E(Z_b\mid\mathcal A),\quad \Sigma=\operatorname{Cov}(Z_b\mid\mathcal A).
\tag{1}
$$

All probabilities and expectations below condition on $\mathcal A$. The independent sample size is $B$, not the number of tasks, episodes, calls, prefixes, or branches inside a block. The fixed tasks may have different laws and means. Dependence inside a complete block is unrestricted **except for the marginal and conditional-mean requirements explicitly used for identification below**. For example, shared execution-period effects may correlate all tasks, log and fresh observations inside a block. Cross-block dependence, a changing distribution of period effects, adaptive cross-block training, or policy-dependent missing blocks violates (1). Merely naming independent RNG streams or assigning new block IDs does not establish (1).

Known bounds $\ell_j\le Z_{bj}\le u_j$ hold almost surely, with $c_j=u_j-\ell_j<\infty$. Counts, truncation rules, outcomes, and complete-block retention are frozen in advance. Do not discard blocks with failed infrastructure, zero denominators, or unfavorable results. Operational failure may already have a prespecified outcome; an unobserved required block vector is instead an observation failure that needs its own justified treatment. This note does not supply a missing-data repair.

## 2. General vector inference

Write

$$
\bar Z=B^{-1}\sum_{b=1}^B Z_b,\qquad
S_B=(B-1)^{-1}\sum_{b=1}^B(Z_b-\bar Z)(Z_b-\bar Z)^\top\quad(B\ge2).
\tag{2}
$$

**Proposition 1 (linear contrasts and smooth functionals).** Under (1), $E\bar Z=\mu$, $\operatorname{Cov}(\bar Z)=\Sigma/B$, and $ES_B=\Sigma$. Thus $a^\top\bar Z$ is unbiased for $a^\top\mu$, with unbiased variance estimate $a^\top S_Ba/B$. If $g$ is continuously differentiable on a neighborhood of $\mu$, then, as the number of complete blocks $B\to\infty$,

$$
\sqrt B\{g(\bar Z)-g(\mu)\}\ \rightsquigarrow
N(0,\sigma_g^2),\qquad
\sigma_g^2=\nabla g(\mu)^\top\Sigma\nabla g(\mu).
\tag{3}
$$

When $\sigma_g^2>0$, a consistent plug-in estimate is

$$
\widehat{\operatorname{Var}}\{g(\bar Z)\}
=\frac{\nabla g(\bar Z)^\top S_B\nabla g(\bar Z)}{B}.
\tag{4}
$$

Equation (4) yields a studentized asymptotic normal limit when its arguments are defined. For ratio functionals it is not asserted to be a finite-$B$ unbiased variance estimator, and the ratio estimator itself need not be unbiased.

**Proof.** Independence gives the covariance of the mean. Expanding the centered sum of outer products around $\mu$ gives $E\sum_b(Z_b-\bar Z)(Z_b-\bar Z)^\top=(B-1)\Sigma$. Bounded coordinates imply finite second moments, so the iid multivariate CLT gives $\sqrt B(\bar Z-\mu)\rightsquigarrow N(0,\Sigma)$. Differentiability gives
$g(\bar Z)-g(\mu)=\nabla g(\mu)^\top(\bar Z-\mu)+o_p(B^{-1/2})$. The law of large numbers gives $S_B\to_p\Sigma$; continuity of the gradient and Slutsky's lemma give (3), (4), and studentization when $\sigma_g^2>0$. For denominators positive at $\mu$, the required positive-denominator neighborhood is reached with probability tending to one. A fixed bounded fallback outside that neighborhood does not alter this limit. $\square$

This is an asymptotic theorem in **complete blocks**. $B=2$ permits a sample covariance calculation but does not justify normal approximation. An implementation must refuse a Wald report when $B<2$, the required denominators or covariance calculations are invalid, or its estimated contrast variance is nonpositive. It must additionally enforce a prespecified minimum block count and validated operating-characteristic gate before presenting Wald intervals as an empirical inference procedure. Neither that minimum nor validation is supplied here; no finite threshold automatically follows from the CLT. A positive sample variance does not prove the population nondegeneracy or adequacy of the normal approximation. Degenerate limits require a separate argument; they are not repaired by reporting a zero-width Wald interval.

**Proposition 2 (finite-sample confidence rectangle).** Fix $0<\alpha<1$ and nonrandom $\alpha_j>0$ with $\sum_{j=1}^p\alpha_j\le\alpha$, and put

$$
\epsilon_j=c_j\sqrt{\frac{\log(2/\alpha_j)}{2B}},\qquad
I_j=[\bar Z_j-\epsilon_j,\bar Z_j+\epsilon_j]\cap[\ell_j,u_j].
\tag{5}
$$

For $B\ge1$, the rectangle $\mathcal R=\prod_j I_j$ satisfies $P(\mu\in\mathcal R)\ge1-\alpha$. Known restrictions on the parameter can also be intersected with $\mathcal R$. Any set containing the image $\{g(x):x\in\mathcal R\}$ over the valid parameter domain has coverage at least $1-\alpha$. Returning the entire parameter range when inversion is undefined or the restricted rectangle is empty is a conservative fallback.

**Proof.** Apply the two-sided bounded-variable Hoeffding inequality to each independent scalar sequence $Z_{1j},\ldots,Z_{Bj}$ and then take a union bound. No independence between coordinates is used. On the resulting joint event the true parameter and its image belong to the corresponding sets. Replacing any reported set by the full parameter range cannot remove the true value. $\square$

These coordinate bounds preserve coverage without estimating covariance, but may be substantially wider than joint covariance-based procedures. Their width is a design diagnostic, not evidence that a feasible experiment has useful precision.

## 3. Primary application: whole-policy comparison and calibration

### 3.1 Fixed-task mean target and valid scores

Retain the v2 primary pair: a frozen history-aware router $\pi_H$ and a frozen initial-task-only router $\pi_P$, both with initial small-model action, the same allowed second decision and the same operational terminal-resolution endpoint. Let $J$ be the fixed task count. The target for policy $\pi$ is the equal-task mean $J^{-1}\sum_g v_g^\pi$, not a new-task-population mean. A separately frozen nonuniform weighting convention could be treated in the same way, but is not introduced here.

For terminal success $Y\in[0,1]$, write the known-propensity longitudinal score as

$$
\phi^\pi=\widehat V_1^\pi(H_1)
+\sum_{t=1}^{K}W_t^\pi\{\widehat V_{t+1}^\pi(H_{t+1})-\widehat Q_t^\pi(H_t,A_t)\},
\quad \widehat V_{K+1}^\pi=Y,
\quad \widehat V_t^\pi=\sum_a\pi_t(a\mid H_t)\widehat Q_t^\pi(H_t,a).
\tag{6}
$$

This is the terminal-payoff convention: intermediate rewards are zero and the terminal outcome is retained through padding. It is equivalent to evaluating that terminal outcome directly; it must not double-count an earlier success reward. Missing opportunities use the same absorbing no-op convention for target and logger.

For every task and every scored logging episode, require its marginal trajectory law to be the declared sequential logger law, with actual recorded assignment probabilities, sequential target support and a common execution kernel for the target intervention. Outcome regressions in (6) are fitted outside **all** scored blocks and are frozen, measurable and bounded in $[0,1]$. Then the established known-propensity score identity gives $E(\phi^\pi\mid\text{task }g)=v_{g,\mathrm{log}}^\pi$, even if the outcome regressions are misspecified. These marginal assumptions cannot be replaced by “arbitrary within-block dependence”; the latter permits dependence between otherwise valid observations, not invalid routing probabilities or selection-biased trajectories. Ordinary cross-fitting using other evaluation blocks is not covered by this frozen-score version.

For the proposed two-decision logger with both eligible actions assigned probability $1/2$, $0\le W_1\le2$ and $0\le W_2\le4$, and (6) has the sufficient bound

$$
-6\le\phi^\pi\le7.
\tag{7}
$$

Indeed the initial term lies in $[0,1]$, each residual in $[-1,1]$, and the two weighted residuals lie in $[-2,2]$ and $[-4,4]$. This bound is deliberately coarse and is not an optimal range claim. If a different logger or number of opportunities is used, replace it by a proved bound for that design; do not keep (7) after changing the probabilities. Common hard-budget and absorption rules remain part of the intervention.

### 3.2 One four-vector per complete study block

Within each complete block, average each policy's scores over a fixed number of logging episodes within task and then equally over tasks. Denote these two means by $O_{bH},O_{bP}$. Similarly let $F_{bH},F_{bP}$ be equal-task means of a fixed number of actual fresh terminal outcomes under the two respective frozen policies. Every fresh execution must have its declared policy/harness marginal. Define

$$
Z_b=(O_{bH},O_{bP},F_{bH},F_{bP})^\top,
\qquad
\mu=(V_{\mathrm{log},H},V_{\mathrm{log},P},V_{\mathrm{fresh},H},V_{\mathrm{fresh},P})^\top.
\tag{8}
$$

The component observation ranges are $[-6,7],[-6,7],[0,1],[0,1]$. All four component means are in $[0,1]$ under the stated score/marginal assumptions. Arbitrary covariance inside a block, including covariance between both offline scores and between log and fresh observations, is retained in $S_B$. This mathematical allowance does not change the protocol's existing assignment and execution-stream requirements.

The main linear functionals are

$$
\begin{aligned}
\Delta_{\mathrm{fresh}}&=\mu_3-\mu_4, & a_{\mathrm{fresh}}&=(0,0,1,-1)^\top,\\
\Delta_{\mathrm{log}}&=\mu_1-\mu_2, & a_{\mathrm{log}}&=(1,-1,0,0)^\top,\\
\Gamma&=\Delta_{\mathrm{log}}-\Delta_{\mathrm{fresh}},
&a_{\mathrm{cal}}&=(1,-1,-1,1)^\top.
\end{aligned}
\tag{9}
$$

$\Delta_{\mathrm{fresh}}$ is the fixed-task history-versus-prompt success contrast. $\Gamma$ is the offline-minus-fresh discrepancy for that contrast. Equality of source and fresh policy-specific execution laws implies $\Gamma=0$; inference for $\Gamma$ does not assume that equality. A zero contrast discrepancy could also conceal equal drift in both policies, so report policy-specific discrepancies $\mu_1-\mu_3$ and $\mu_2-\mu_4$ as prespecified calibration quantities if desired. Neither a nonrejection nor a confidence interval containing zero proves equivalence: an equivalence decision requires a scientific tolerance fixed before evaluation.

Apply Proposition 1 with these vectors $a$. The estimators are unbiased, and $a^\top S_Ba/B$ estimates the full execution variance, preserving within-block covariance. Joint inference for several contrasts requires a prespecified multiplicity procedure; marginal Wald intervals alone do not supply it.

For a finite-sample simultaneous alternative, use Proposition 2 with widths $(13,13,1,1)$ and intersect the component-mean intervals with $[0,1]$. If the resulting intervals are $[L_j,U_j]$, use

$$
\begin{aligned}
\mathcal C_{\mathrm{fresh}}&=[L_3-U_4,U_3-L_4]\cap[-1,1],\\
\mathcal C_{\mathrm{log}}&=[L_1-U_2,U_1-L_2]\cap[-1,1],\\
\mathcal C_{\mathrm{cal}}&=[L_1-U_2-U_3+L_4,U_1-L_2-L_3+U_4]\cap[-2,2].
\end{aligned}
\tag{10}
$$

On the one confidence-rectangle event all these sets cover simultaneously. If a required restricted interval is empty, return the full respective parameter ranges. These bounds can be very wide, especially because the offline-score range is coarse. They do not establish that OPE is cheaper or more precise than direct evaluation.

## 4. Secondary application: preserve the original branch/log target

### 4.1 One complete block and its observable totals

Retain the original fixed-benchmark design in [the fixed-benchmark note](theory_branch_fixed_benchmark_bound.md): $J$ fixed tasks, $R$ source episodes per task, the original balanced initial assignments and the specified later routing law. Put $L=JR$; for the archive, $J=330,R=8,L=2640$. Each source episode contributes at most one eligible first-failure prefix. Let $\mathcal F_b$ be the complete realized source frame in block $b$, $N_b\le L$ its prefix count, and $d_{bi}\in[-1,1]$ the mean fresh stay-large-minus-stay-small continuation contrast at prefix $i$. Define the latent total $T_b=\sum_{i=1}^{N_b}d_{bi}$, with empty sum zero.

Conditional on $\mathcal F_b$ and $N_b>0$, select $m_b=\min(m_0,N_b)$ prefixes uniformly without replacement, with fixed $m_0\ge1$. For each selected prefix observe $r\ge1$ fresh paired contrasts $D_{bij}\in[-1,1]$ satisfying

$$
E(D_{bij}\mid\mathcal F_b,S_b)=d_{bi},\qquad i\in S_b.
\tag{11}
$$

Here $S_b$ is the selected prefix set. Equation (11) is the selection-invariant restoration/execution assumption. It is not implied by matching seed labels, source hashes, observed completion times, or successful recovery of files. Pair and prefix noises may be dependent within a complete block; (11), rather than their conditional independence, suffices for the mean identity below.

For $N_b>0$, let $\widehat B_b=(m_br)^{-1}\sum_{i\in S_b,j\le r}D_{bij}$ and $\widehat T_b=N_b\widehat B_b$. If $N_b=0$, define $\widehat T_b=0$ directly; no nonexistent branch mean need be computed. Let $U_{ba},D_{ba}$ be the source-log weighted success and weight totals for stay-$a$ after the first failure, using the actual target/logger routing ratios and absorption convention in the original note. With $W_{ia}\le4$,

$$
|\widehat T_b|\le N_b\le L,\qquad 0\le U_{ba}\le D_{ba}\le4N_b\le4L.
\tag{12}
$$

Define the observable vector

$$
Z_b=(\widehat T_b,N_b,U_{b1},D_{b1},U_{b0},D_{b0})^\top.
\tag{13}
$$

**Proposition 3 (unbiased latent-total recovery).** Under the conditional simple-random-sampling design and (11), $E(\widehat T_b\mid\mathcal F_b)=T_b$, including $N_b=0$. Consequently the mean of (13) is

$$
\mu=(ET_b,EN_b,EU_{b1},ED_{b1},EU_{b0},ED_{b0})^\top.
\tag{14}
$$

**Proof.** For $N_b>0$, iterating (11) first over continuation outcomes gives
$E(\widehat B_b\mid\mathcal F_b,S_b)=m_b^{-1}\sum_{i\in S_b}d_{bi}$. Each prefix has conditional inclusion probability $m_b/N_b$. Therefore
$E(\widehat T_b\mid\mathcal F_b)=N_bm_b^{-1}\sum_i(m_b/N_b)d_{bi}=T_b$. For $N_b=0$, both totals are zero by definition. Integrate over the source frame to obtain (14). $\square$

### 4.2 Pool totals, then form ratios

Assume $\mu_2,\mu_4,\mu_6>0$. The original primary branch/log target is

$$
\Delta_{\mathrm{branch}}
=g(\mu)=\frac{\mu_1}{\mu_2}-\frac{\mu_3}{\mu_4}+\frac{\mu_5}{\mu_6}\in[-2,2].
\tag{15}
$$

It is the ratio-of-expected-totals target conditional on the same fixed tasks. Estimate it by $g(\bar Z)$, equivalently

$$
\widehat\Delta_{\mathrm{branch}}
=\frac{\sum_b\widehat T_b}{\sum_bN_b}
-\frac{\sum_bU_{b1}}{\sum_bD_{b1}}
+\frac{\sum_bU_{b0}}{\sum_bD_{b0}},
\tag{16}
$$

when the three observed denominators are positive. Do **not** average $\widehat B_b$ across blocks or average each block's log ratios. Those operations generally target different quantities; dropping zero-prefix or zero-arm blocks also changes the design. Individual tasks or entire blocks may contribute zero prefixes or arm weights. No finite-$B$ unbiasedness is claimed for (16).

The gradient is

$$
\nabla g(\mu)=
\left(
\frac1{\mu_2},-\frac{\mu_1}{\mu_2^2},
-\frac1{\mu_4},\frac{\mu_3}{\mu_4^2},
\frac1{\mu_6},-\frac{\mu_5}{\mu_6^2}
\right)^\top.
\tag{17}
$$

Proposition 1 gives the asymptotic variance $\nabla g(\mu)^\top\Sigma\nabla g(\mu)/B$ and its plug-in version. The complete-block covariance $\Sigma$ includes source-frame variation, prefix sampling, fresh continuation noise, both log arms, and all their dependence permitted by the observation law. None of these covariance terms is removed by separately estimating the component means. Positive population denominators make $g$ smooth locally; they do not justify normal intervals when realized denominators are near zero or the number of independent blocks is small.

An additional sufficient calibration contract requires valid source randomization and $d_{bi}=q_1(H_{bi})-q_0(H_{bi})$ almost surely, where $q_a(H)$ is the source law's stay-$a$ target-continuation mean at the same eligible pre-repair history $H$. Thus the restored conditional mean in (11) must agree with the corresponding source target-continuation contrast; (11) alone, conditioning on the complete source frame, does not establish this equality. Under that additional contract, the policy-weight identities imply $ED_{b1}=ED_{b0}=EN_b$ and $ET_b=EU_{b1}-EU_{b0}$, hence (15) equals zero. This calibration restriction is not assumed for inference about (15); without it the log ratios are statistical weighted-mean parameters unless their causal interpretation is separately justified.

### 4.3 A finite-sample confidence set with denominator refusal

Apply Proposition 2 to (13) with coordinate supports

$$
[-L,L],\ [0,L],\ [0,4L],\ [0,4L],\ [0,4L],\ [0,4L],
\quad\text{and widths }(2L,L,4L,4L,4L,4L).
\tag{18}
$$

Use six nonrandom error budgets summing to at most $\alpha$. Let $I_j=[L_j,U_j]$ be the resulting intervals. If any of $L_2,L_4,L_6$ is nonpositive, return $[-2,2]$. This rule also applies when any observed denominator is zero. It makes no favorable conditioning on observed support.

Otherwise, for a numerator interval $I=[l,u]$ and positive denominator interval $J=[v,w]$, define

$$
\operatorname{Rat}(I,J)=
[\min\{l/v,l/w,u/v,u/w\},\max\{l/v,l/w,u/v,u/w\}].
\tag{19}
$$

The four-corner rule includes negative branch numerators correctly. Intersect $\operatorname{Rat}(I_1,I_2)$ with $[-1,1]$ to obtain $[L_\theta,U_\theta]$, and intersect $\operatorname{Rat}(I_3,I_4)$ and $\operatorname{Rat}(I_5,I_6)$ with $[0,1]$ to obtain $[L_1^\nu,U_1^\nu]$ and $[L_0^\nu,U_0^\nu]$. Report

$$
\mathcal C_{\mathrm{branch}}=
[L_\theta-U_1^\nu+L_0^\nu,\ U_\theta-L_1^\nu+U_0^\nu]\cap[-2,2].
\tag{20}
$$

If a required intersection is empty, return $[-2,2]$. On the confidence-rectangle event, all true ratios and their signed sum belong to (19)–(20). Therefore this procedure has finite-sample coverage at least $1-\alpha$ under the full observation law, including denominator fallbacks. Coordinate dependence does not affect this proof. It is deliberately conservative and may return the entire range even with many blocks.

## 5. What this changes, and what it does not

This design supplies an observable covariance unit for prospective whole-policy calibration under a fixed task list. The branch corollary demonstrates how replication can preserve the existing ratio convention while retaining shared-source dependence; it is secondary to qualifying the primary whole-policy comparison.

The archive supplies **one** realized complete source block, not $B$ independent complete studies. The 330 tasks, 564 eligible prefixes, 200 sampled prefixes and 800 continuations cannot be relabeled as complete-study replicates. Moreover, the archive's lost/recovered continuations leave (11) unverified. This note cannot validate its exploratory derivative band or retroactively manufacture valid source/execution assumptions. The earlier [range-only bound](theory_branch_fixed_benchmark_bound.md) and [REQ-018 limitation](theory_feedback_20260926_req018_review.md) remain unchanged.

Replication is not a free variance repair: a branch-containing complete block requires $JR$ source trajectories and up to $2r m_0$ branch continuations; a whole-policy block also needs its prespecified fresh-policy executions. Independent nuisance training has its own cost. The asymptotic regime increases complete-block count, rather than just increasing task or branch count inside one block. A feasible resource envelope, competent executor pair, untouched task split, explicit useful effect/tolerance, and precision assessment remain open. No new run, model download, Monte Carlo batch, live stage or CONFIRM stage is authorized by this note.

Before implementation or execution, independent review should check the marginal score laws, complete-block independence/stationarity, conditional restoration means, target definitions, exact coordinate bounds, gradient, confidence-set inversion and refusal behavior. Tiny deterministic finite-support fixtures can check mean/covariance identities, target-preserving pooling, zero-denominator fallback, positive and negative numerators, and shared-noise covariance. Such fixtures are algebra/implementation checks, not empirical coverage validation. A later simulator study must reproduce the declared complete-block law and preserve failed cases before any practical interval claim is made.

## Attribution

The identification and known-propensity score identity are inherited from longitudinal causal inference and off-policy evaluation, as cited in [the core theory](theory.md): Robins (1986), Bang and Robins (2005), and Jiang and Li (2016). The multivariate CLT, sample covariance identity, and delta method are standard probability/statistical tools; see van der Vaart, *Asymptotic Statistics*, [Chapter 3, Delta Method](https://www.cambridge.org/core/books/abs/asymptotic-statistics/delta-method/85F4D7D90259A601942FDB034A8DC703) (publisher chapter record checked 26 September 2026). Equation (5) uses Hoeffding (1963), *Probability Inequalities for Sums of Bounded Random Variables*, [publisher record](https://doi.org/10.1080/01621459.1963.10500830), already recorded in the repository bibliography/audit. The project-specific work is the explicit prospective observation unit and its target-preserving application to these agent experiments; novelty of the generic tools is not claimed.
