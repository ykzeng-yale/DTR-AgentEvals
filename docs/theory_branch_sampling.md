# Fixed-size prefix sampling with replicated continuations

**20 September 2026.** This note supplies the conditional branch component needed by the completed-code-study review. It follows from elementary sampling and total-variance identities; no new general sampling theorem is claimed. It does not validate the currently reported branch-minus-log interval or establish model performance. A separate internal mathematical reviewer checked the result and its scope. **07:50 UTC cycle update:** the theoretical result and full proof are integrated into Section 9.3, Proposition 11 of the [27-page manuscript](../manuscript/README.md), with independent proof-preservation and visual review; empirical numbers in this companion note are not inserted into the paper.

## Target and assumptions

Condition on a complete source frame $\mathcal F$, including all eligible recorded prefixes and the source log. There are $N\ge2$ prefixes, indexed by $i$. At prefix $i$, let $d_i$ be the expected large-minus-small continuation outcome under the specified restored-state execution law. The finite-frame target is

$$
\mu_{\mathcal F}=N^{-1}\sum_{i=1}^N d_i.
$$

Select a simple random sample $S$ of fixed size $2\le m\le N$, without replacement and independently of the fresh continuation randomness given $\mathcal F$. For each selected prefix observe an unbiased contrast $\widehat d_i$, with conditional variance $v_i$. Require the continuation contrasts to be independent across prefixes given the frame and selection, with their conditional laws unchanged by selection. Their second moments are finite. These are assumptions about execution and sampling, not consequences of distinct seed labels or successful restoration flags.

For example, take $r_{ia}\ge2$ independent identically distributed continuation outcomes under arm $a\in\{0,1\}$, with all arms and prefixes conditionally independent. The replicate counts are fixed before selection. Then

$$
\widehat d_i=\overline Y_{i1}-\overline Y_{i0},\quad
v_i=\sigma_{i1}^2/r_{i1}+\sigma_{i0}^2/r_{i0},\quad
\widehat v_i=s_{i1}^2/r_{i1}+s_{i0}^2/r_{i0},
$$

where each $s_{ia}^2$ is the unbiased sample variance. Thus $E(\widehat v_i\mid\mathcal F,i\in S)=v_i$. Coupled arms require their covariance term; shared execution shocks across prefixes require additional covariance terms. Neither independence is established by the saved code-study records alone.

## Conditional variance and an unbiased estimator

Define

$$
\widehat B=m^{-1}\sum_{i\in S}\widehat d_i,\quad f=m/N,\quad
S_d^2=\frac1{N-1}\sum_{i=1}^N(d_i-\mu_{\mathcal F})^2,\quad
\overline v=N^{-1}\sum_{i=1}^N v_i.
$$

**Proposition.** Under the assumptions above,

$$
E(\widehat B\mid\mathcal F)=\mu_{\mathcal F},\qquad
\operatorname{Var}(\widehat B\mid\mathcal F)
=\frac{1-f}{m}S_d^2+\frac{\overline v}{m}.
\tag{1}
$$

Let $s_{\widehat d,S}^2=(m-1)^{-1}\sum_{i\in S}(\widehat d_i-\widehat B)^2$. If the $\widehat v_i$ are conditionally unbiased, then

$$
\widehat V_{\mathcal F}
=\frac{1-f}{m}s_{\widehat d,S}^2
+\frac{f}{m}\left\{m^{-1}\sum_{i\in S}\widehat v_i\right\}
\tag{2}
$$

is unbiased for (1). No independence between $\widehat d_i$ and $\widehat v_i$ within a prefix is needed.

**Proof.** Given $S,\mathcal F$, the conditional mean is $m^{-1}\sum_{i\in S}d_i$, and the variance is $m^{-2}\sum_{i\in S}v_i$. The selection indicators have inclusion probabilities $m/N$ and joint inclusion probabilities $m(m-1)/\{N(N-1)\}$. Expanding the variance of the sampled mean using these probabilities gives $(1-f)S_d^2/m$. Averaging the conditional continuation variance gives $\overline v/m$. Total variance proves (1), and averaging the conditional mean proves unbiasedness.

Write $s_{d,S}^2$ for the sample variance of the fixed $d_i$ in $S$. Expansion around the sample mean gives

$$
E(s_{\widehat d,S}^2\mid S,\mathcal F)
=s_{d,S}^2+m^{-1}\sum_{i\in S}v_i.
$$

The same inclusion probabilities give $E(s_{d,S}^2\mid\mathcal F)=S_d^2$. Therefore $E(s_{\widehat d,S}^2\mid\mathcal F)=S_d^2+\overline v$, while the expected sampled mean of $\widehat v_i$ is $\overline v$. Substitution in (2) gives (1). ∎

The finite-population correction applies to between-prefix heterogeneity, not to all continuation noise. At $m=N$, fresh execution noise remains: the variance is $\overline v/N$. With noiseless continuations it reduces to the usual finite-frame sampling variance. Multiplying the entire observed sample variance by $1-f$ omits $f\overline v/m$.

An unbiased variance estimator alone does not prove that a normal interval has nominal coverage. Such an interval needs an appropriate limit theorem and regularity conditions, or a separately justified finite-sample construction.

## Why this does not finish branch-minus-log inference

Let $L(\mathcal F)$ be the pooled log contrast, measurable with respect to the full source frame, and put $\widehat\Delta=\widehat B-L(\mathcal F)$. Conditional on the frame,

$$
E(\widehat\Delta\mid\mathcal F)=\mu_{\mathcal F}-L(\mathcal F),\qquad
\operatorname{Var}(\widehat\Delta\mid\mathcal F)=\operatorname{Var}(\widehat B\mid\mathcal F).
\tag{3}
$$

Thus (2) concerns uncertainty around this frame-specific difference. It does not establish that its target is zero: the realized log estimate has already been conditioned on. Under a random-frame model with finite second moments, total variance instead gives the exact decomposition

$$
\operatorname{Var}(\widehat\Delta)
=E\{\operatorname{Var}(\widehat B\mid\mathcal F)\}
+\operatorname{Var}\{\mu_{\mathcal F}-L(\mathcal F)\}.
\tag{4}
$$

The second term contains source-task variability and its linkage to the log estimate. It is not supplied by (2). Random eligible-frame sizes and task clustering belong in that source model. A fixed-size sample can still permit a valid unconditional task-population sandwich under suitable assumptions; selection dependence by itself neither proves nor disproves its validity. Replicate averages already contribute to task-score variation. The missing work is a justified sampling argument for the stated target, not a mechanical correction factor applied to the existing squared derivatives.

For the code study, $N=564,m=200$ and two continuations per arm describe the saved plan. Applying these conditional formulas requires the execution assumptions above, including the recovery limitations. The checked pooled difference remains $-0.014654$; this note neither reports a new empirical interval nor repairs the full comparison by changing its target.

## Exact validation and next step

[`tests/test_branch_sampling.py`](../tests/test_branch_sampling.py) exhaustively enumerates every sample and binary continuation outcome in heterogeneous finite examples, using rational arithmetic. It checks the mean, variance, unbiased variance estimate, census boundary, noiseless boundary, and a random-frame example in which the additional term in (4) is nonzero. No Monte Carlo or model inference is involved. These examples complement the proof; they do not establish assumptions for the actual execution system.

For a manuscript-ready full comparison, specify the scientific target and random-frame/task model; derive and validate the remaining term or an equivalent joint influence construction; keep the pooled point estimates and all source tasks; and distinguish variance consistency from interval coverage. Continue to label the existing squared-derivative band exploratory until that work is complete.
