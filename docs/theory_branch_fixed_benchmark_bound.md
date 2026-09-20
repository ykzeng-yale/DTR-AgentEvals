# Finite-sample inference for the fixed-benchmark branch/log contrast

**20 September 2026; source snapshot `aac69b5a634fa3be3ea9c1a26c88e70ef973fe3f`.** This separately reviewed note is not integrated into the paper and does not validate the archived interval. It specializes classical bounded-variable concentration. The lead adopts (2) below as an explicit retrospective clarification of the fixed-benchmark pooled-prefix target, not as a claim that the original protocol fully specified its ratio convention. Only deterministic arithmetic evaluated the constants below; no model runs, resampling or Monte Carlo were performed.

## 1. The exact target and random experiment

Fix the original $J=330$ benchmark tasks, their composition, the trained policy artifacts, the harness specifications, and the randomization **design**. In a repetition, redraw each task's block of $R=8$ logging episodes using the original 4-small/4-large initial allocation and the specified subsequent .5 assignment mechanism. Outcomes and eligible prefixes evolve under that block's execution law. The realized assignment array, seeds, histories and outcomes are random in this repeated-design statement; it does not condition on their archived realized values. Nothing here assumes iid draws of new tasks from a population.

For task $g$, let $M_g\in\{0,\ldots,R\}$ count first-failure prefixes. At each such prefix $i$, let $d_i\in[-1,1]$ be the mean success difference between fresh stay-large and stay-small continuations under a fixed restored-execution law. Put $T_g=\sum_{i:g(i)=g}d_i$. For the corresponding source-log continuations, let

$$
W_{ia}=\frac{1\{A_{i1}=a\}}{.5}
\begin{cases}
1,&\text{absorbed after the first repair},\\
1\{A_{i2}=a\}/.5,&\text{a second repair is eligible},
\end{cases}
\qquad
U_{ga}=\sum_{i:g(i)=g}W_{ia}Y_i,\quad
D_{ga}=\sum_{i:g(i)=g}W_{ia}.
$$

Here $Y_i\in[0,1]$ is final success, and $U_{ga}$ is the quantity previously denoted $N_{ga}$, renamed here to distinguish it from the total prefix count. In particular,

$$
|T_g|\le M_g\le R,\qquad 0\le U_{ga}\le D_{ga}\le4M_g\le4R.
\tag{1}
$$

All expectations below condition on the fixed benchmark and specifications. Define

$$
\theta=\frac{\sum_g E T_g}{\sum_g E M_g},\qquad
\nu_a=\frac{\sum_g E U_{ga}}{\sum_g E D_{ga}},\qquad
\Delta=\theta-\nu_1+\nu_0.
\tag{2}
$$

Assume only that the three population denominators in (2) are positive. **Individual tasks may have identically zero prefix counts or arm weights.** The branch component is a ratio of expected totals. Equivalently, it weights the fixed benchmark's tasks by their expected contribution of eligible logger prefixes. It is not an equal-task average of conditional repair effects, $E(T/N)$, or the mean of the realized conditional branch/log gap. The lead adopts (2) for the fixed-benchmark pooled-prefix question in the accompanying analysis clarification; conditioning on the benchmark alone did not determine this ratio convention.

With correct sequential randomization and an invariant continuation kernel, conditional on a pre-repair prefix $H_i$, $E(W_{ia}\mid H_i)=1$ and $E(W_{ia}Y_i\mid H_i)$ equals its stay-$a$ continuation mean. Hence $\sum E D_{ga}=\sum E M_g$ and $\Delta=0$ under that additional calibration contract. The concentration argument below does **not** assume equality: it also permits a different fixed restored-execution law, whose mean contrast $d_i$ need not agree with the source-log law. Without causal assignment/kernel assumptions, the log ratios in (2) remain statistical weighted-mean parameters rather than identified policy values.

## 2. Sufficient independence and execution assumptions

1. The full source-task blocks are independent across $g$, but their laws need not be identical. Within a task, dependence among all eight episodes and their coordinates is unrestricted. In particular, initial permuted blocks are not treated as eight independent Bernoulli assignments. Each block's latent $T_g$ is a function of its own recorded prefix states and the fixed branch law; an unmodelled shared execution shock can violate this premise.
2. Given the complete realized source frame $\mathcal F$, with $N=\sum M_g$, select $m=\min(200,N)$ prefixes uniformly without replacement, independently of fresh continuation noise. The stored study has $N=564,m=200$.
3. For each selected prefix, generate $r=2$ independent fresh **replicate pairs**, with pair contrast $Z_{ij}=Y_{i1j}-Y_{i0j}\in[-1,1]$ and $E(Z_{ij}\mid\mathcal F,S)=d_i$. Pairs are conditionally independent across prefixes and replicate indices. The two outcomes within a pair may be dependent. The conditional pair laws are selection-invariant. This is an assumption about execution, not a consequence of seed labels or matched transcript hashes.

The last assumption can be weakened to independence across prefixes only, with a wider bound stated below, or strengthened to independence of all individual arm outcomes, with a narrower one. Neither cross-task nor fresh-execution independence is established by this memo for the archive. The lost-outcome recovery incident remains relevant to whether selection-invariant fresh laws can be defended.

Write the observed quantities

$$
\widehat B=\frac1{mr}\sum_{i\in S,j\le r}Z_{ij},\quad
\widehat\nu_a=\frac{U_a}{D_a},\quad
U_a=\sum_g U_{ga},\ D_a=\sum_gD_{ga},\quad
\widehat\Delta=\widehat B-\widehat\nu_1+\widehat\nu_0.
\tag{3}
$$

This preserves the archived pooled point estimator. If $N=0$ or either observed $D_a=0$, return the whole parameter range $[-2,2]$ for $\Delta$. Do not drop the zero-contribution tasks. The formulas below are evaluated when these global denominators are positive. Coverage nevertheless integrates over all repeated blocks, including the whole-range fallback, and is not asserted conditional on observing positive denominators.

## 3. Source-frame ratio bounds without iid tasks

For fixed unknown $\theta\in[-1,1]$, the independent variables $T_g-\theta M_g$ have sum of expectations zero by (2). Each lies in
$[-R(1+\theta),R(1-\theta)]$, an interval of width $2R$ regardless of $\theta$. The two-sided Hoeffding bound therefore gives, for any fixed $\alpha_B\in(0,1)$,

$$
P\left(\left|\sum_g(T_g-\theta M_g)\right|>
R\sqrt{2J\log(2/\alpha_B)}\right)\le\alpha_B.
$$

On the complement, with $T=\sum_gT_g$,

$$
\left|\frac TN-\theta\right|\le
b_B:=\frac{R\sqrt{2J\log(2/\alpha_B)}}{N}.
\tag{4}
$$

This uses the **observed** positive denominator and does not require it to exceed a separate estimated lower limit. The event bounded before division is an ordinary centered-sum event for the fixed parameter $\theta$.

Similarly $U_{ga}-\nu_aD_{ga}\in[-4R\nu_a,4R(1-\nu_a)]$ has width $4R$, and its summed expectation is zero. Thus, simultaneously up to failure probability $\alpha_a$ for each arm,

$$
|\widehat\nu_a-\nu_a|\le
b_a:=\frac{4R\sqrt{(J/2)\log(2/\alpha_a)}}{D_a}.
\tag{5}
$$

Neither sum requires each task's centered expectation to be zero. Task-specific means and task heterogeneity are allowed. Dependence between the two arm sums, between $T$ and the log totals, and between task coordinates is preserved; it is not discarded by an independence assumption.

## 4. A conditional finite-frame branch bound

The needed elementary fact is: a mean-zero random variable supported in an interval of width $c$ has moment generating function at most $\exp(\lambda^2c^2/8)$. Applying that fact conditionally and iterating yields the same bound with $\sum c_k^2$ for a martingale whose conditional increment widths are bounded by $c_k$.

Condition on $\mathcal F$ and consider a uniform ordering of the $m$ sampled prefixes. Let $L_k$ be the conditional expectation of their eventual sampled mean $m^{-1}\sum_{i\in S}d_i$ after revealing the first $k$ indices. For $m<N$, direct subtraction of the means of the remaining finite population gives

$$
L_k-L_{k-1}
=\frac{N-m}{m(N-k)}\{d_{I_k}-\overline d_{\mathrm{remaining},k-1}\},\qquad k=1,\ldots,m.
$$

The conditional range width is at most $c_k=2(N-m)/\{m(N-k)\}$. Define

$$
C_S(N,m)=\frac{4(N-m)^2}{m^2}\sum_{j=N-m}^{N-1}\frac1{j^2}\quad(m<N),
\qquad C_S(N,N)=0.
\tag{6}
$$

The sampled latent mean minus $T/N$ therefore has conditional mgf bounded by $\exp(\lambda^2 C_S/8)$. Given the sample, the $mr$ independent pair terms in $\widehat B$ have coefficient $1/(mr)$ and range width $2/(mr)$. Their noise about the sampled latent mean has conditional mgf bounded by $\exp(\lambda^2 C_E/8)$, where

$$
C_E=\frac4{mr}.
\tag{7}
$$

Iterating expectation over selection and execution multiplies these bounds, without requiring independence between sample composition and the resulting noise distribution. Chernoff optimization, and its negative-tail counterpart, yield

$$
P\left(\left|\widehat B-\frac TN\right|>b_F\mid\mathcal F\right)\le\alpha_F,
\qquad
b_F=\sqrt{\frac{C_S+C_E}{2}\log(2/\alpha_F)}.
\tag{8}
$$

At a census the selection term is zero; fresh noise remains. If all $2mr$ individual arm outcomes are independent, each signed outcome has width $1/(mr)$, so replace $C_E$ by $2/(mr)$. If only the $m$ prefix-level replicate averages are independent and repetitions within a prefix may be arbitrarily dependent, replace it by $4/m$. Counts of repeated executions alone do not justify the narrower constants.

## 5. The full fixed-benchmark confidence set

Choose four nonrandom error budgets with $\alpha_B+\alpha_1+\alpha_0+\alpha_F\le\alpha$. Combining (4), (5) and (8) by a union bound gives

$$
P\{\Delta\in\mathcal C\}\ge1-\alpha,\qquad
\mathcal C=[\widehat\Delta-b,\widehat\Delta+b]\cap[-2,2],\qquad
b=b_B+b_1+b_0+b_F,
\tag{9}
$$

with the whole-range convention for zero global denominators. Conditional validity of (8) integrates over the random frame; the other three events are unconditional over independent, nonidentically distributed fixed-task blocks. Independence between branch and log estimators is **not** required. This supplies finite-sample coverage for (2) under the explicit assumptions; it is not a sandwich variance, asymptotic approximation, or coverage theorem for the existing derivative band.

The interval accounts for a random number of eligible prefixes. It does not claim $\widehat B$ is unbiased for $\theta$, or that a finite-sample Hájek ratio is unbiased for $\nu_a$. Indeed $E(\widehat B\mid\mathcal F)=T/N$ when $N>0$, and in general $E(T/N)\ne\sum E T_g/\sum E M_g$. Equations (4)–(9) control deviations from the chosen ratio-of-expectations target without equating those parameters.

## 6. Practical width and what this does not repair

For $J=330,R=8,N=564,m=200,r=2,D_1=570,D_0=574$, choose four error budgets $.0125$ to give total $.05$. The deterministic constants are:

| Component | Radius |
|---|---:|
| Source branch ratio, $b_B$ | .820934 |
| Source large log ratio, $b_1$ | 1.624585 |
| Source small log ratio, $b_0$ | 1.613264 |
| Conditional sampled branches, $b_F$ | .241256 |
| Sum | **4.300040** |

Here $C_S=.01293700848$ and $C_E=.010000$. At the archived point $\widehat\Delta=.120000-(184/570-108/574)=-.01465370744$, (9) returns **the entire $[-2,2]$ parameter range**. This fully bounded construction is mathematically available but practically vacuous. The original .048386 squared-derivative scale is not validated by it.

A distinct, secondary conditional question is more informative. Conditioning on the **entire recorded frame**, including its log estimate, (8) with $\alpha_F=.05$ gives radius .205684 for the finite-frame branch mean and for its difference from the fixed log comparator. The corresponding arithmetic ranges are:

- Finite-frame mean $T/N$: $[-.085684,.325684]$.
- Finite-frame gap $T/N-(184/570-108/574)$: $[-.220338,.191030]$.

If all individual arm outcomes are independent, the radius becomes .181889 and the conditional gap range becomes $[-.196543,.167236]$. These are **assumption-indexed theoretical width calculations**, not a claim that the archive has established the required execution independence or a replacement primary empirical interval. Their conditional target is not automatically zero even under an invariant harness, because the log comparator has been fixed at its noisy realized value.

## 7. Scientific decision

There is no remaining mathematical obstacle to a conservative finite-sample set under this explicit fixed-benchmark model. The obstacles to a **useful** inference claim are its width and the execution/dependence assumptions. The range-only source bound deliberately allows extreme dependence inside every eight-episode block; the two weighted log ratios dominate its width. Practical improvement would have to exploit justified design structure, covariance or variance information while retaining the same conditioning and estimand. It cannot come from discarding zero-contribution tasks or replacing the benchmark with iid task sampling.

Independent mathematical review found no blocking issue; the lead has adopted (2) as the retrospective analysis clarification. Next work must assess which independence conditions the execution contract supports. If a sharper fixed-design procedure is pursued, its coverage argument must include initial blocking, random prefix counts and selection, the shared source log, and fresh replication. This memo addresses the branch/log Hájek comparison only; it does not supply inference for the cross-fitted whole-policy DR comparisons. A longer paper is not the objective, and no new model compute is needed to make these decisions.


## Review and attribution

The independent reviewer checked the centered-sum range arguments, observed-denominator division, SRS martingale
increments, selection/execution moment bound and unconditional union bound. The [review check](audits/check_fixed_benchmark_bound_aac69b5.py)
reproduces the constants and enumerates small finite populations. These bounded checks support the written proof;
they are not a universal formal verification or a validation of archive execution assumptions. Additional
[exact finite examples](audits/check_fixed_benchmark_examples.py) check paired continuation noise,
nonidentical source blocks, zero-denominator fallback and the distinction between the two ratio targets.

The concentration tool is classical: W. Hoeffding (1963), *Probability Inequalities for Sums of Bounded Random
Variables*, [primary publisher record](https://www.tandfonline.com/doi/abs/10.1080/01621459.1963.10500830).
Publisher title/author/volume record checked 20 September 2026; the proof and constants here are derived directly
for the stated fixed-task model. No novelty claim is made for concentration or martingale arguments.
