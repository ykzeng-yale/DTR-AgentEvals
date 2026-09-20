# Recovering full-frame quadratic moments from sampled branches

**20 September 2026.** This is a bounded algebraic step toward the unresolved branch/log variance argument.
It uses ordinary first- and second-order inclusion probabilities, not a new general sampling method. It does not
establish a standard error, confidence-interval coverage or assumptions for the archived experiment.

## Conditional quadratic-moment identity

Use the source frame and execution assumptions of [the sampling note](theory_branch_sampling.md): condition on
the complete recorded frame $\mathcal F$ with $N\ge2$ eligible prefixes, sample $2\le m\le N$ prefixes by simple
random sampling without replacement, and observe $Z_i$ with conditional mean $d_i$ and variance $v_i$ at sampled
prefixes. Fresh prefix noises are conditionally independent, with laws unchanged by selection. Let $\widehat v_i$
be conditionally unbiased for $v_i$. Independence of $Z_i$ and $\widehat v_i$ within a prefix is unnecessary.
Finite second moments and integrable variance estimates suffice for the conditional expectations below.

Let $C$ be a finite symmetric matrix, $b$ a vector and $c$ a scalar, all **known from the recorded frame** (or
external information included in the conditioning set), not fitted using selected fresh outcomes. Write

$$
Q(d)=d^\top C d+2b^\top d+c,\qquad
\pi_1=m/N,\quad \pi_2=m(m-1)/\{N(N-1)\}.
$$

With $I_i=1\{i\in S\}$, define the off-diagonal sum over **ordered** distinct pairs:

$$
\widehat Q=
\sum_i\frac{I_i}{\pi_1}C_{ii}(Z_i^2-\widehat v_i)
+\sum_{i\ne j}\frac{I_iI_j}{\pi_2}C_{ij}Z_iZ_j
+2\sum_i\frac{I_i}{\pi_1}b_iZ_i+c.
\tag{1}
$$

**Identity.** $E(\widehat Q\mid\mathcal F)=Q(d)$.

**Proof.** Conditional on selecting prefix $i$, $E(Z_i^2-\widehat v_i\mid\mathcal F,I_i=1)=d_i^2$.
Conditional independence and selection-invariant laws give
$E(Z_iZ_j\mid\mathcal F,I_iI_j=1)=d_id_j$ for distinct prefixes. Multiplying by inclusion probabilities
$\pi_1$ and $\pi_2$ cancels the respective denominators in (1). The linear terms similarly average to
$2b^\top d$, proving the identity. For general designs, the same argument uses their positive known
$\pi_i,\pi_{ij}$ and corresponding selection assumptions. Zero pair inclusion cannot be repaired by this identity.

At a census, (1) becomes $Q(Z)-\sum_i C_{ii}\widehat v_i$, retaining the correction for fresh execution noise.
Even for nonnegative $Q(d)$, an unbiased $\widehat Q$ can be negative. Clipping changes its expectation.

## Application to the original pooled contrast

Keep all $G$ source tasks and their unequal eligible-prefix counts $M_g$, with $N=\sum_g M_g$. Let $g(i)$
identify the task of prefix $i$. For the pooled log arm ratios, write
$\widehat v_a=\sum_g N_{ga}/D_a$, $D_a=\sum_g D_{ga}>0$, where $N_{ga}$ and $D_{ga}$ are the recorded weighted
outcome and weight totals. Their frame-measurable task derivative is

$$
\ell_g=\frac{N_{g1}-\widehat v_1D_{g1}}{D_1}
-\frac{N_{g0}-\widehat v_0D_{g0}}{D_0}.
$$

If all latent prefix means were observed, the derivative of the full-frame branch-minus-log contrast under
perturbing task $g$'s weight would be

$$
u_g(d)=\frac{\sum_{i:g(i)=g}d_i-(M_g/N)\sum_i d_i}{N}-\ell_g
=\sum_i A_{gi}d_i-\ell_g,\quad
A_{gi}=\frac{1\{g(i)=g\}-M_g/N}{N}.
\tag{2}
$$

Thus the latent squared-derivative statistic $Q(d)=\sum_g u_g(d)^2$ has
$C=A^\top A$, $b=-A^\top\ell$, $c=\ell^\top\ell$, all known from $\mathcal F$.
Equation (1) estimates it conditionally without substituting a branch-fitted centering mean: the unknown
full-frame mean has been expanded linearly in (2). No task or prefix is discarded and no equal-task target
replaces the pooled contrast. A specified finite-sample multiplier can be included in $C,b,c$; it cannot supply
a missing sampling justification.

## What remains unresolved

This is exact reconstruction of a **latent full-frame squared-derivative statistic**, not exact estimation of
$\operatorname{Var}_{\mathcal F}\{\mu_{\mathcal F}-L(\mathcal F)\}$. The latter requires a source-frame model and
a justified link from task derivatives to population variance. Fixed benchmark tasks with repeated randomized
executions are not automatically iid draws from a task population. The experiment protocol's conditional-on-benchmark
uncertainty and any superpopulation claim must be distinguished explicitly. Shared execution shocks or recovery
selection may also invalidate the conditional noise assumptions.

The earlier conditional variance estimator and (1) provide candidate components for a fuller argument; simply
adding them and reporting a normal interval is not justified here. Variance consistency, any moment/rate conditions
and interval coverage remain to be established. The current empirical derivative band stays exploratory.
[`tests/test_branch_quadratic.py`](../tests/test_branch_quadratic.py) checks the identity by exact rational enumeration,
including heterogeneous noise, unequal task sizes, a census and a negative-estimate example. No Monte Carlo or
model inference is involved. The result is not yet integrated into the compiled manuscript.
