# Conditional-frame branch variance: target and decomposition review

**Reviewed source:** `981f7b9872164697ab79e413a50257c011f11e6f`. This note reviews the archived [worker calculation](../experiments/tools/branch_frame_inference.py) and [conditional-frame summary](../results/code_routing/analysis/branch_frame_inference.json). The worker source and results archive are preserved. This is a deterministic reconstruction of recorded numeric outcomes and algebra, not a new model run, resampling experiment, hypothesis test, or validation of confidence-interval coverage.

## 1. Independent reconstruction

The [audit script](../scripts/audit_conditional_branch_frame_981f7b9.py) uses only the Python standard library and reads immutable Git blobs at the reviewed SHA. It does not import the worker or experiment modules. The saved source contains 4,488 unique, error-free logging records and 800 unique, error-free branch records, all with attempt 1; the audit therefore needs no ambiguous retry resolution. It reconciles the 800 branch IDs with the plan, the plan's parent-log hash, all 200 selected parent prefixes, two replicates per arm, recorded forced-arm continuations, and the 564 eligible confirm-log prefixes. These checks concern saved data, not the unobserved physical execution process.

From the raw outcomes it independently obtains:

| Quantity | Reconstructed value |
|---|---:|
| Fixed confirm tasks / logging episodes | 330 / 2,640 |
| Eligible / selected prefixes | 564 / 200 |
| Tasks represented among selected prefixes | 103 |
| Branch mean contrast $\widehat B$ | 0.1200000000 |
| Large source weighted successes / weight total | 184 / 570 |
| Small source weighted successes / weight total | 108 / 574 |
| Pooled source contrast $L(\mathcal F)$ | 0.1346537074 |
| Recorded difference $\widehat B-L(\mathcal F)$ | −0.0146537074 |
| Sample variance of observed prefix contrasts $s^2$ | 0.1488442211 |
| Mean estimated within-prefix contrast variance $\widehat{\overline v}$ | 0.0400000000 |
| Conditional variance estimate $\widehat V_{\mathcal F}$ | 0.0005512349 |

All reconstructed scalar fields of the archived worker summary agree within $10^{-12}$. The archived square-root scale is 0.0234783921. The archived normal interval [−0.0606713561, 0.0313639412] remains **unvalidated**; reproducing its ingredients is not a coverage argument. Full hashes, exact rational component values, discrepancies and counts are in the [audit JSON](audits/conditional_branch_frame_audit_981f7b9.json).

Reproduce the numeric audit from the repository root:

```sh
python3 scripts/audit_conditional_branch_frame_981f7b9.py
```

The default output is `docs/audits/conditional_branch_frame_audit_981f7b9.json`. The script reads the pinned commit even if the checkout subsequently advances.

## 2. The primary target remains unchanged

The primary fixed-benchmark target is the ratio-of-expected-source-totals contrast adopted in the [fixed-benchmark note, equation (2)](theory_branch_fixed_benchmark_bound.md). With the original tasks fixed, complete task-specific logging/execution blocks are redrawn under the specified design; the realized source histories, assignments, outcomes and eligible frame remain random. In that notation,

$$
\Delta=\theta-\nu_1+\nu_0,\qquad
\theta=\frac{\sum_g E T_g}{\sum_g E M_g},\qquad
\nu_a=\frac{\sum_g E U_{ga}}{\sum_g E D_{ga}}.
$$

The worker instead conditions on the **entire realized source frame** $\mathcal F$, including the log outcomes, and studies

$$
\Delta_{\mathcal F}=\mu_{\mathcal F}-L(\mathcal F),\qquad
\mu_{\mathcal F}=N^{-1}\sum_{i=1}^N d_i.
$$

This is a useful **secondary conditional-frame target**. It is a different question, even though its point estimate numerically equals the archived pooled branch-minus-log difference. Because $L(\mathcal F)$ is then constant, its conditional variance is exactly the branch conditional variance under the [sampling note's assumptions](theory_branch_sampling.md). That observation does not settle the primary source-randomness problem or supersede its analysis. The primary problem is also not an iid task-population problem: the original fixed benchmark is retained. An iid task-population extension and the realized-frame conditional analysis each have separate scopes.

Accordingly, the worker summary's `supersedes` field and the source's “settles” wording should not be interpreted as replacing the primary target or validating either previous uncertainty calculation. The earlier independence-sum and task-derivative scales remain unsupported for their claimed inferential uses; comparing them to a different conditional target's scale is not an efficiency comparison.

## 3. Correct interpretation of the variance components

Under the assumptions in the sampling note, with $f=m/N$, the true conditional variance is

$$
\operatorname{Var}(\widehat B\mid\mathcal F)
=\frac{1-f}{m}S_d^2+\frac{\overline v}{m}.
$$

The two summands represent latent between-prefix heterogeneity and fresh execution noise. The observed contrast sample variance $s^2$ already includes execution noise: $E(s^2\mid\mathcal F)=S_d^2+\overline v$. Therefore the two displayed terms of the unbiased estimator,

$$
\widehat V_{\mathcal F}
=\frac{1-f}{m}s^2+\frac f m\widehat{\overline v},
$$

are **estimator summands**, not those two scientific variance components. The exact algebraic regrouping is

$$
\widehat V_{\mathcal F}
=\underbrace{\frac{1-f}{m}(s^2-\widehat{\overline v})}_{\text{estimated latent between-prefix component}}
+\underbrace{\frac{\widehat{\overline v}}{m}}_{\text{estimated execution component}}.
$$

For the archived observations:

| Interpretation | Value |
|---|---:|
| First estimator summand $(1-f)s^2/m$ | 0.0004803129121 |
| Second estimator summand $f\widehat{\overline v}/m$ | 0.0000709219858 |
| Estimated latent between-prefix component $(1-f)(s^2-\widehat{\overline v})/m$ | **0.0003512348979** |
| Estimated execution component $\widehat{\overline v}/m$ | **0.0002000000000** |
| Total, unchanged | **0.0005512348979** |
| Estimated latent-between / execution ratio | **1.7561744895** |

The approximately sevenfold comparison divides the first estimator summand by the second, which is about 6.77; it does not compare the latent-between and execution components. The corrected descriptive component ratio is about **1.76**, not seven. Under the stated assumptions the regrouped component estimates are unbiased individually, but their ratio need not be unbiased. The estimated latent component can be negative in other finite samples; truncating it would change its unbiasedness. This decomposition by itself neither determines the optimal allocation of future prefixes and replicates nor validates a normal approximation.

## 4. A conditional test is possible in principle; zero has a different meaning

The worker source says that conditioning on the realized log prevents testing $\Delta_{\mathcal F}=0$. That is too strong. A justified conditional confidence set for $\Delta_{\mathcal F}$ can be inverted to test that frame-specific null. The obstacle here is the absence of a validated interval for the archived execution design, not the fact that $L(\mathcal F)$ is conditioned on.

Kernel stability, however, does **not** force $\Delta_{\mathcal F}=0$. A realized log contrast has sampling error. For example, consider two identical, eligible prefixes, a small arm that always fails and a large arm with success probability $1/2$, with the same law in logs and branches. A possible randomized log assigns one prefix to each arm and observes a large-arm success. Its pooled log contrast is 1, while the frame's mean continuation effect is $1/2$, so $\Delta_{\mathcal F}=-1/2$ despite stable kernels. Conditioning on this realized log retains that nonzero difference.

Thus a conditional rejection of zero would concern agreement with this particular realized reference. It would not, by itself, refute kernel stability or the primary calibration identity. Conversely, the archived normal interval's inclusion of zero establishes neither equivalence nor calibration.

## 5. Remaining assumptions and acceptance criteria

The audit identifies 32 discordant same-arm pairs among 400 pairs (8%), and two selected prefixes whose four retained continuations span both invocations. These are recorded facts. They establish neither iid execution within arm nor conditional independence across arms or prefixes, nor the absence of shared runtime shocks. For the mixed-invocation prefixes, the assumed common conditional law must span the lost run and its recovery. Successful recorded restoration flags, equal seeds, and matching hashes do not prove this law or outcome-independent loss/reexecution. The incident is a limitation requiring assumptions and evidence, not proof of bias.

Before accepting the secondary conditional result as inference, require an explicit execution/sampling model, a valid interval construction or justified asymptotic regime for that model, and a decision about the recovery assumption. Retain the conditional target and all selected prefixes, disclose unavailable evidence, and label the current normal interval exploratory. Before accepting primary inference, retain the fixed-benchmark ratio-of-expected-totals target and account for the random source blocks and their shared relationship with branch selection; the [bounded construction](theory_branch_fixed_benchmark_bound.md) is currently vacuous under its sufficient assumptions and does not validate the archived Wald interval.

This review adds a source-verified decomposition and corrects the target/test interpretation. It does not raise empirical readiness, replace any archived result, or discharge the primary inference requirement.
