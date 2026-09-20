# Code-routing: OPE vs fresh live executions (CONFIRM tasks)

live episodes scored intention-to-treat after exhausting retries: 0

## A2 decision rule: improvement is claimed only if the Bonferroni OPE interval excludes 0 AND the live contrast agrees in sign

| outcome   | contrast                                    |   live |   live_se |   live_lower |   live_upper |    ope |   ope_lower_bonferroni |   ope_upper_bonferroni | sign_agrees   | improvement_claimed   |
|:----------|:--------------------------------------------|-------:|----------:|-------------:|-------------:|-------:|-----------------------:|-----------------------:|:--------------|:----------------------|
| utility   | always_large - always_small                 | 0.0821 |    0.021  |       0.0409 |       0.1232 | 0.092  |                 0.0305 |                 0.1535 | True          | True                  |
| utility   | class_tailored - always_small               | 0.0363 |    0.0175 |       0.0019 |       0.0706 | 0.0148 |                -0.0197 |                 0.0493 | True          | False                 |
| utility   | escalate_after_first_failure - always_small | 0.0289 |    0.0179 |      -0.0062 |       0.0641 | 0.028  |                -0.0164 |                 0.0725 | True          | False                 |
| utility   | learned - always_small                      | 0.0771 |    0.0202 |       0.0375 |       0.1166 | 0.1095 |                 0.047  |                 0.172  | True          | True                  |
| utility   | soft_escalation_d2 - always_small           | 0.0508 |    0.0195 |       0.0126 |       0.0889 | 0.0601 |                 0.022  |                 0.0982 | True          | True                  |
| success   | always_large - always_small                 | 0.1061 |    0.0206 |       0.0656 |       0.1465 | 0.1168 |                 0.0563 |                 0.1774 | True          | True                  |
| success   | class_tailored - always_small               | 0.0409 |    0.0174 |       0.0069 |       0.0749 | 0.0203 |                -0.0142 |                 0.0548 | True          | False                 |
| success   | escalate_after_first_failure - always_small | 0.0364 |    0.0177 |       0.0016 |       0.0711 | 0.036  |                -0.0083 |                 0.0802 | True          | False                 |
| success   | learned - always_small                      | 0.0985 |    0.0199 |       0.0595 |       0.1375 | 0.1314 |                 0.0695 |                 0.1933 | True          | True                  |
| success   | soft_escalation_d2 - always_small           | 0.0652 |    0.0193 |       0.0274 |       0.1029 | 0.0743 |                 0.0364 |                 0.1121 | True          | True                  |

| outcome   | policy                       |   n_tasks |   live |   live_se |   ope_dr |   ope_se |   ope_minus_live |   diff_se_paired |   diff_lower |   diff_upper | covers_zero   |   live_model_calls |   shared_log_model_calls |   se_ratio_ope_over_live |
|:----------|:-----------------------------|----------:|-------:|----------:|---------:|---------:|-----------------:|-----------------:|-------------:|-------------:|:--------------|-------------------:|-------------------------:|-------------------------:|
| utility   | always_large                 |       330 | 0.6777 |    0.0243 |   0.6719 |   0.0245 |          -0.0058 |           0.0116 |      -0.0286 |       0.0169 | True          |                858 |                     3662 |                   1.0077 |
| utility   | always_small                 |       330 | 0.5956 |    0.0242 |   0.5799 |   0.0249 |          -0.0158 |           0.017  |      -0.049  |       0.0175 | True          |                990 |                     3662 |                   1.0268 |
| utility   | class_tailored               |       330 | 0.6319 |    0.0239 |   0.5947 |   0.0248 |          -0.0372 |           0.0165 |      -0.0695 |      -0.0049 | False         |                934 |                     3662 |                   1.0406 |
| utility   | escalate_after_first_failure |       330 | 0.6245 |    0.0246 |   0.6079 |   0.0262 |          -0.0166 |           0.0179 |      -0.0517 |       0.0185 | True          |                934 |                     3662 |                   1.0645 |
| utility   | learned                      |       330 | 0.6727 |    0.0238 |   0.6894 |   0.0254 |           0.0167 |           0.0145 |      -0.0117 |       0.0452 | True          |                880 |                     3662 |                   1.0668 |
| utility   | soft_escalation_d2           |       330 | 0.6464 |    0.0236 |   0.64   |   0.0215 |          -0.0064 |           0.012  |      -0.03   |       0.0171 | True          |                908 |                     3662 |                   0.909  |
| success   | always_large                 |       330 | 0.7167 |    0.0238 |   0.7114 |   0.0239 |          -0.0052 |           0.0114 |      -0.0276 |       0.0171 | True          |                858 |                     3662 |                   1.005  |
| success   | always_small                 |       330 | 0.6106 |    0.024  |   0.5946 |   0.0247 |          -0.016  |           0.0168 |      -0.049  |       0.017  | True          |                990 |                     3662 |                   1.029  |
| success   | class_tailored               |       330 | 0.6515 |    0.0235 |   0.6149 |   0.0245 |          -0.0366 |           0.0163 |      -0.0687 |      -0.0046 | False         |                934 |                     3662 |                   1.0418 |
| success   | escalate_after_first_failure |       330 | 0.647  |    0.0241 |   0.6306 |   0.0258 |          -0.0164 |           0.0176 |      -0.0509 |       0.0182 | True          |                934 |                     3662 |                   1.0683 |
| success   | learned                      |       330 | 0.7091 |    0.0234 |   0.726  |   0.0251 |           0.0169 |           0.0144 |      -0.0113 |       0.0451 | True          |                880 |                     3662 |                   1.07   |
| success   | soft_escalation_d2           |       330 | 0.6758 |    0.0233 |   0.6689 |   0.0211 |          -0.0069 |           0.0119 |      -0.0302 |       0.0165 | True          |                908 |                     3662 |                   0.9081 |

Spearman rank agreement of policy utilities, OPE vs live: 0.886

Evaluation cost: ONE randomized log of 3662 model calls supports every policy above; the live arm spent 5504 calls in total (6 policies).
