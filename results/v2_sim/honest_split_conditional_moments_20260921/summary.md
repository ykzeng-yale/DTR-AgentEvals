# Conditional-moment diagnosis, informative / .2 cell (RETROSPECTIVE; DTR-REQ-003, lead 9f9e29d)

Completed index prefix 1000 of 1000 repetitions; table hashes matched 3000 of 3000. Per-fit exact conditional variance (frozen fit, known logging) is a DIAGNOSTIC scale, not a usable interval.

| Policy | Estimand | Wald cov. (lower/upper) | Exact-var cov. (lower/upper) | Wald − exact (MCSE) | Mean est./exact | Emp. var / mean exact (jk z) | Exact-var CV across fits | Skew of avg (mean) |
|---|---|---|---|---|---|---|---|---|
| history_large_after_exception | dr | 0.9450 (0.023/0.032) | 0.9470 (0.026/0.027) | -0.0020 (0.0028) | 1.0004 | 1.0248 (+0.57) | 0.003 | -0.0389 |
| history_large_after_exception | dr_minus_fresh | 0.9510 (0.020/0.029) | 0.9560 (0.020/0.024) | -0.0050 (0.0026) | 1.0002 | 1.0238 (+0.56) | 0.003 | -0.0389 |
| prompt_only_large_if_hard | dr | 0.9510 (0.023/0.026) | 0.9450 (0.031/0.024) | +0.0060 (0.0075) | 1.0077 | 0.9882 (-0.24) | 0.175 | +0.0044 |
| prompt_only_large_if_hard | dr_minus_fresh | 0.9340 (0.029/0.037) | 0.9360 (0.034/0.030) | -0.0020 (0.0066) | 1.0062 | 1.0300 (+0.61) | 0.175 | +0.0044 |
| fixed_LS | dr | 0.9360 (0.026/0.038) | 0.9450 (0.031/0.024) | -0.0090 (0.0061) | 1.0122 | 1.0608 (+1.14) | 0.083 | -0.0732 |
| fixed_LS | dr_minus_fresh | 0.9330 (0.034/0.033) | 0.9360 (0.037/0.027) | -0.0030 (0.0050) | 1.0095 | 1.0886 (+1.68) | 0.083 | -0.0732 |
