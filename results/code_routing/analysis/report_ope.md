# Code-routing: off-policy evaluation on CONFIRM tasks

log episodes 4488 (scored intention-to-treat after exhausting retries: 0); confirm tasks 330; train tasks 231

## Policy values (cross-fitted DR, task-level SE)

| outcome   | policy                        |   dr_estimate |   dr_se |   dr_lower |   dr_upper |   dr_n_tasks |    ipw |   ipw_se |   gcomp |   ess_last_stage |   max_weight |   zero_weight_fraction |   tasks_with_support |   missing_q_cells |
|:----------|:------------------------------|--------------:|--------:|-----------:|-----------:|-------------:|-------:|---------:|--------:|-----------------:|-------------:|-----------------------:|---------------------:|------------------:|
| utility   | always_small                  |        0.5799 |  0.0249 |     0.5311 |     0.6287 |          330 | 0.5821 |   0.0252 |  0.5787 |          771.267 |       8      |                 0.5883 |                  317 |                 0 |
| utility   | always_large                  |        0.6719 |  0.0245 |     0.6239 |     0.7198 |          330 | 0.6736 |   0.0245 |  0.6746 |          902.606 |       8      |                 0.561  |                  319 |                 0 |
| utility   | escalate_after_first_failure  |        0.6079 |  0.0262 |     0.5566 |     0.6592 |          330 | 0.6106 |   0.0262 |  0.6062 |          832.887 |       8      |                 0.5837 |                  325 |                 0 |
| utility   | escalate_after_second_failure |        0.6187 |  0.0253 |     0.5691 |     0.6683 |          330 | 0.6031 |   0.0265 |  0.6154 |          788.491 |       8      |                 0.5955 |                  318 |                 0 |
| utility   | large_then_small              |        0.6615 |  0.0243 |     0.6138 |     0.7091 |          330 | 0.6593 |   0.0243 |  0.6633 |          888.472 |       8      |                 0.5659 |                  319 |                 0 |
| utility   | class_tailored                |        0.5947 |  0.0248 |     0.546  |     0.6433 |          330 | 0.591  |   0.0249 |  0.5998 |          821.73  |       8      |                 0.5883 |                  321 |                 0 |
| utility   | soft_escalation_d2            |        0.64   |  0.0215 |     0.5979 |     0.682  |          330 | 0.6396 |   0.0214 |  0.6399 |         2527.99  |       1.7778 |                 0      |                  330 |                 0 |
| utility   | soft_escalation_d4            |        0.6407 |  0.0218 |     0.598  |     0.6833 |          330 | 0.6412 |   0.0217 |  0.6408 |         2285.72  |       2.56   |                 0      |                  330 |                 0 |
| utility   | learned                       |        0.6894 |  0.0254 |     0.6396 |     0.7391 |          330 | 0.6865 |   0.0264 |  0.6892 |          886.505 |       8      |                 0.5655 |                  319 |                 0 |
| success   | always_small                  |        0.5946 |  0.0247 |     0.5461 |     0.6431 |          330 | 0.597  |   0.0251 |  0.5935 |          771.267 |       8      |                 0.5883 |                  317 |                 0 |
| success   | always_large                  |        0.7114 |  0.0239 |     0.6646 |     0.7582 |          330 | 0.7136 |   0.024  |  0.7143 |          902.606 |       8      |                 0.561  |                  319 |                 0 |
| success   | escalate_after_first_failure  |        0.6306 |  0.0258 |     0.5801 |     0.6811 |          330 | 0.6333 |   0.026  |  0.6289 |          832.887 |       8      |                 0.5837 |                  325 |                 0 |
| success   | escalate_after_second_failure |        0.6379 |  0.025  |     0.5889 |     0.6869 |          330 | 0.6212 |   0.0265 |  0.6346 |          788.491 |       8      |                 0.5955 |                  318 |                 0 |
| success   | large_then_small              |        0.6948 |  0.0241 |     0.6476 |     0.7421 |          330 | 0.6924 |   0.0241 |  0.6967 |          888.472 |       8      |                 0.5659 |                  319 |                 0 |
| success   | class_tailored                |        0.6149 |  0.0245 |     0.5669 |     0.6628 |          330 | 0.6106 |   0.0247 |  0.6201 |          821.73  |       8      |                 0.5883 |                  321 |                 0 |
| success   | soft_escalation_d2            |        0.6689 |  0.0211 |     0.6275 |     0.7103 |          330 | 0.6686 |   0.0211 |  0.6689 |         2527.99  |       1.7778 |                 0      |                  330 |                 0 |
| success   | soft_escalation_d4            |        0.6705 |  0.0214 |     0.6286 |     0.7124 |          330 | 0.6711 |   0.0213 |  0.6707 |         2285.72  |       2.56   |                 0      |                  330 |                 0 |
| success   | learned                       |        0.726  |  0.0251 |     0.6769 |     0.7751 |          330 | 0.7227 |   0.0263 |  0.7259 |          886.505 |       8      |                 0.5655 |                  319 |                 0 |

## Paired contrasts vs always_small (DR); Bonferroni over 8 comparisons, z=2.734

| outcome   | contrast                                     |   estimate |     se |   lower95 |   upper95 |   lower_bonferroni |   upper_bonferroni |
|:----------|:---------------------------------------------|-----------:|-------:|----------:|----------:|-------------------:|-------------------:|
| utility   | always_large - always_small                  |     0.092  | 0.0225 |    0.0479 |    0.1361 |             0.0305 |             0.1535 |
| utility   | escalate_after_first_failure - always_small  |     0.028  | 0.0162 |   -0.0038 |    0.0599 |            -0.0164 |             0.0725 |
| utility   | escalate_after_second_failure - always_small |     0.0389 | 0.0159 |    0.0078 |    0.0699 |            -0.0045 |             0.0822 |
| utility   | large_then_small - always_small              |     0.0816 | 0.0215 |    0.0394 |    0.1238 |             0.0227 |             0.1405 |
| utility   | class_tailored - always_small                |     0.0148 | 0.0126 |   -0.0099 |    0.0396 |            -0.0197 |             0.0493 |
| utility   | soft_escalation_d2 - always_small            |     0.0601 | 0.0139 |    0.0328 |    0.0874 |             0.022  |             0.0982 |
| utility   | soft_escalation_d4 - always_small            |     0.0608 | 0.0146 |    0.0322 |    0.0895 |             0.0208 |             0.1009 |
| utility   | learned - always_small                       |     0.1095 | 0.0229 |    0.0647 |    0.1543 |             0.047  |             0.172  |
| success   | always_large - always_small                  |     0.1168 | 0.0221 |    0.0735 |    0.1602 |             0.0563 |             0.1774 |
| success   | escalate_after_first_failure - always_small  |     0.036  | 0.0162 |    0.0043 |    0.0677 |            -0.0083 |             0.0802 |
| success   | escalate_after_second_failure - always_small |     0.0433 | 0.0159 |    0.0121 |    0.0745 |            -0.0002 |             0.0868 |
| success   | large_then_small - always_small              |     0.1002 | 0.0213 |    0.0584 |    0.1421 |             0.0419 |             0.1586 |
| success   | class_tailored - always_small                |     0.0203 | 0.0126 |   -0.0044 |    0.045  |            -0.0142 |             0.0548 |
| success   | soft_escalation_d2 - always_small            |     0.0743 | 0.0138 |    0.0472 |    0.1014 |             0.0364 |             0.1121 |
| success   | soft_escalation_d4 - always_small            |     0.0759 | 0.0145 |    0.0475 |    0.1044 |             0.0362 |             0.1157 |
| success   | learned - always_small                       |     0.1314 | 0.0226 |    0.087  |    0.1758 |             0.0695 |             0.1933 |

## Theorem 5 (Hoeffding) simultaneous half-width at this sample size

M = 48.4, epsilon_n = 18.103 (utility range is about 1.1, so the certificate is VACUOUS); tasks needed for half-width 0.05: 4.33e+07

## Negative controls

- association, NOT a policy value: success of episodes with a second ASSIGNED decision minus those with only one (includes any intention-to-treat episodes) = -0.4841 (a second decision is triggered by failure, so those episodes are the hard ones)
- randomized stage-1 contrast among episodes that reached it (large minus small at t=1; valid because assignment there is a coin flip): 0.0306
- IPW with a deliberately WRONG constant propensity (0.8 for large) vs the recorded 0.5: always_small 2.0152 vs 0.5970; always_large 0.4328 vs 0.7136
