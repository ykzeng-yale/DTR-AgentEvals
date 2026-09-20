# A source-frame variance link under an explicit iid task model

**20 September 2026.** This companion to
[the quadratic-moment note](theory_branch_quadratic.md) and manuscript Sections 9.3–9.4
supplies one deliberately restrictive source-population model. It is separate from inference conditional on
the archived benchmark tasks. The argument uses the classical iid law of large numbers, central limit
theorem and smooth-function delta method; it is not a new sampling or efficiency theorem. See
[van der Vaart (1998), *Asymptotic Statistics*, Chapter 3](https://doi.org/10.1017/CBO9780511802256.004).

## Model and target

Condition on any external policy-training information, and then keep that information and all policies
fixed. All expectations and limits below refer to the resulting fixed task-population law. Suppose the
source-task payloads

$$
X_g=(M_g,T_g,N_{g1},D_{g1},N_{g0},D_{g0}),\qquad g=1,2,\ldots,
$$

are iid. Here $M_g$ is a task's number of eligible prefixes,
$T_g=\sum_{i:g(i)=g}d_i$ is the sum of their latent conditional continuation contrasts, and
$N_{ga},D_{ga}$ are the recorded log numerator and denominator totals for arm $a$.
Dependence among coordinates within a task is unrestricted and is essential for the branch/log covariance.
When the full task frames contain additional information, their construction must imply this iid payload
model; shared source shocks or policy fitting across evaluation tasks do not satisfy it automatically.

Assume deterministic constants $m_-,m_+,d_-,d_+,K>0$, independent of $g$ and the sample size, such that

$$
1\le m_-\le M_g\le m_+<\infty,\qquad
0<d_-\le D_{ga}\le d_+<\infty,\qquad
|T_g|,|N_{ga}|\le K\quad\text{almost surely}.
\tag{A}
$$

Counts $M_g$ are integers. These bounds are intentionally stronger than positive population denominators:
each task contributes eligible prefixes and positive weight to both log arms. Tasks with no eligible prefix
or no recorded weight in an arm fall outside (A). Restricting the observed cohort or adding artificial
prefixes to force these conditions would change the original target. No such modification is proposed.

Write $\mu_M=E M_g$, $\mu_{Da}=E D_{ga}$,
$\beta=E T_g/\mu_M$ and $\nu_a=E N_{ga}/\mu_{Da}$. The task-population parameter is

$$
r=\beta-\nu_1+\nu_0.
$$

The branch component is a ratio of expected totals and counts: it retains prefix weighting rather than
averaging task-specific ratios. This is a statistical population contrast; neither this source model nor
the following limit theorem implies that it equals zero or identifies agreement between causal policies.
For $J$ source tasks define

$$
N_J=\sum_{g=1}^J M_g,\quad D_{a,J}=\sum_{g=1}^J D_{ga},\quad
\widehat\beta_J=\frac{\sum_g T_g}{N_J},\quad
\widehat\nu_{a,J}=\frac{\sum_g N_{ga}}{D_{a,J}},\quad
r_J=\widehat\beta_J-\widehat\nu_{1,J}+\widehat\nu_{0,J}.
\tag{1}
$$

This $r_J$ is the latent full-frame quantity $\mu_{\mathcal F_J}-L(\mathcal F_J)$ from Section 9.3.
All ratios are defined for every realization under (A).

## Proposition: population variance and the oracle task derivatives

Define the mean-zero task influence

$$
\psi_g=\frac{T_g-\beta M_g}{\mu_M}
-\frac{N_{g1}-\nu_1D_{g1}}{\mu_{D1}}
+\frac{N_{g0}-\nu_0D_{g0}}{\mu_{D0}},\qquad
\sigma^2=E(\psi_g^2).
\tag{2}
$$

Under (A) and iid task sampling,

$$
\sqrt J(r_J-r)\ \Rightarrow\ N(0,\sigma^2),\qquad
J\operatorname{Var}(r_J)\longrightarrow\sigma^2.
\tag{3}
$$

The first limit is degenerate if $\sigma^2=0$. For the exact full-frame task-weight derivative

$$
u_{g,J}=\frac{T_g-\widehat\beta_J M_g}{N_J}
-\frac{N_{g1}-\widehat\nu_{1,J}D_{g1}}{D_{1,J}}
+\frac{N_{g0}-\widehat\nu_{0,J}D_{g0}}{D_{0,J}},\qquad
Q_J=\sum_{g=1}^J u_{g,J}^2,
\tag{4}
$$

one has $\sum_g u_{g,J}=0$ and

$$
JQ_J\longrightarrow\sigma^2\quad\text{almost surely and in }L^1.
\tag{5}
$$

The derivative in (4) is exactly the derivative of (1) when task $g$ receives weight $1+\varepsilon$
and all its numerator and denominator contributions receive that same weight. It is the derivative in
Section 9.4, including its branch/log cross terms, not an equal-task average of individual arm ratios.

**Proof.** Let $\mu=E X_g$, $\overline X_J=J^{-1}\sum_g X_g$, and
$f(m,t,n_1,d_1,n_0,d_0)=t/m-n_1/d_1+n_0/d_0$. Then
$r=f(\mu)$ and $r_J=f(\overline X_J)$. The mean and every sample mean lie in a fixed compact convex set
whose three denominators are bounded away from zero. The Hessian of $f$ is bounded on that set. Taylor's
theorem therefore gives

$$
r_J-r=\frac1J\sum_g\psi_g+R_J,\qquad
|R_J|\le C\|\overline X_J-\mu\|^2.
\tag{6}
$$

For any centered bounded iid scalar coordinate $Z_g$,

$$
E\left(\frac1J\sum_g Z_g\right)^4
=\frac{J E Z_g^4+3J(J-1)(E Z_g^2)^2}{J^4}=O(J^{-2}).
$$

Summing over the six coordinates and using
$(\sum_{k=1}^6 z_k^2)^2\le6\sum_{k=1}^6z_k^4$ yields
$E\|\overline X_J-\mu\|^4=O(J^{-2})$, hence $E R_J^2=O(J^{-2})$.
Thus $\sqrt J R_J\to0$ in $L^2$; the iid scalar CLT for the bounded mean-zero $\psi_g$ proves
the distributional limit in (3). Furthermore,

$$
\left|\operatorname{Var}(r_J)-\frac{\sigma^2}{J}\right|
\le E R_J^2+2\sqrt{\frac{\sigma^2}{J}E R_J^2}
=O(J^{-2})+O(J^{-3/2}),
$$

which proves the variance limit, including when $\sigma^2=0$.

Let $\widehat\psi_{g,J}=J u_{g,J}$. Replacing population means and ratios in (2) by their empirical
counterparts gives exactly $\widehat\psi_{g,J}$. Bounded payloads and uniformly positive denominators imply
a deterministic uniform Lipschitz bound

$$
\max_{g\le J}|\widehat\psi_{g,J}-\psi_g|
\le C'\|\overline X_J-\mu\|,
$$

and a fixed bound on all $|\widehat\psi_{g,J}|$ and $|\psi_g|$. The strong law and this bound imply

$$
JQ_J=\frac1J\sum_g\widehat\psi_{g,J}^2
=\frac1J\sum_g\psi_g^2+o(1)\longrightarrow E\psi_g^2
$$

almost surely. The same fixed bound on $JQ_J$ gives $L^1$ convergence by dominated convergence.
Finally, direct differentiation of the weighted ratios gives (4), and summing their centered numerators
gives $\sum_g u_{g,J}=0$. This completes the proof.

## What conditional quadratic recovery adds

For every $J\ge2$, suppose the complete frame $\mathcal F_J$ also satisfies the conditional branch-sampling
and independent fresh-execution assumptions of Section 9.4. Sample $2\le m_J\le N_J$ prefixes by SRSWOR,
with selection-invariant conditional means and independent fresh noises across prefixes, and use
conditionally unbiased per-prefix noise-variance estimates. Let $\widehat Q_J$ be that section's
inclusion-probability estimator with the frame-measurable coefficients corresponding exactly to (4).
Assume $E|\widehat Q_J|<\infty$ for each $J$; bounded fresh outcomes and bounded per-prefix variance
estimates are one sufficient condition in this bounded-count model. The conditional identity already proved
in Section 9.4 and the tower property give

$$
E(\widehat Q_J\mid\mathcal F_J)=Q_J,\qquad
J E\widehat Q_J=E(JQ_J)\longrightarrow\sigma^2,
\tag{7}
$$

and consequently

$$
J\{E\widehat Q_J-\operatorname{Var}(r_J)\}\longrightarrow0.
\tag{8}
$$

This is asymptotic agreement **in expectation** for the source-frame variance component. It is not exact
finite-sample unbiasedness for $\operatorname{Var}(r_J)$. It does not prove
$J\widehat Q_J\to\sigma^2$ in probability. In particular, (7) places no growth condition on $m_J$;
even fixed $m_J=2$ is sufficient for the expectation identity, which alone cannot provide a concentration
argument. Negative realized estimates remain possible.

For the actually sampled branch-minus-log statistic $\widehat\Delta_J=\widehat B_J-L(\mathcal F_J)$,
provided $E(\widehat B_J^2)<\infty$, the prior total-variance identity remains

$$
\operatorname{Var}(\widehat\Delta_J)
=E\{\operatorname{Var}(\widehat B_J\mid\mathcal F_J)\}
+\operatorname{Var}(r_J).
\tag{9}
$$

The proposition supplies a link for the second component under the stated iid model. A limit theorem for
$\widehat\Delta_J$, concentration of its conditional-variance estimator and of $\widehat Q_J$, and a
joint studentization argument are not proved here. Their requirements may include a growing branch sample,
control of inclusion weights and fourth moments, and a compatible joint source/selection/execution design.
Adding the two estimated components and displaying a normal interval is therefore not justified by this note.

## Fixed benchmark counterexample and an iid contrast

For an even number $J$ of **fixed**, deterministic task types, let half have $y_g=0$ and half $y_g=1$.
Take $M_g=D_{g1}=D_{g0}=1$, $T_g=y_g$, $N_{g1}=y_g/2$, and $N_{g0}=0$.
These are abstract source payloads illustrating a sampling-model distinction; no additional causal
identification conclusion is imposed. Use a complete prefix census and deterministic fresh continuations.
Then the entire reported contrast is deterministic:

$$
r_J=\frac14,\qquad \operatorname{Var}_{\mathrm{repeat}}(r_J)=0,
\qquad u_{g,J}=\frac{y_g-1/2}{2J},\qquad JQ_J=\frac1{16}>0.
\tag{10}
$$

Thus a positive squared-derivative statistic can measure variation across fixed task types even when repeated
execution of that benchmark has zero variance. Assumption (A) alone is not enough; iid task-population
sampling is doing substantive work in (3)–(5).

For comparison, under the iid law with $Y_g\sim\operatorname{Bernoulli}(1/2)$ and the same payload map,
$r_J=\overline Y_J/2$, $\sigma^2=1/16$, and exactly

$$
J\operatorname{Var}(r_J)=\frac1{16},\qquad
J E Q_J=\frac{J-1}{16J}.
\tag{11}
$$

The finite-$J$ discrepancy also shows why the general result is an asymptotic variance link rather than an
exact unbiased-variance identity. Separating the branch and log components as if independent would instead
give $1/4+1/16=5/16$ for the variance scale in this example, omitting their positive covariance.

The restrictive iid model has not been verified for the archived study. Its fixed and stratified benchmark
design, tasks with zero eligible-prefix or arm-weight totals, and restoration/execution assumptions must be
addressed separately. No empirical estimate or interval is changed. This companion note is not yet integrated into the unchanged
29-page manuscript. Independent mathematical review and three exact toy checks are recorded in the
[current response](theory_feedback_20260920_source_model.md). The checks illustrate the identities and sampling
boundary; they do not empirically establish the asymptotic theorem or interval coverage.
