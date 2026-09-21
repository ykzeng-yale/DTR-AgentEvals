# Saved-record diagnosis, replication-sensitivity batch (RETROSPECTIVE, EXPLORATORY; lead 4570b3e)

All 2,000 records, no exclusions; published coverage counts reproduced for all 36 entries. MSE and centered variance are separate targets. z = (statistic - exact) / its SE (MSE: empirical MCSE; variance: leave-one-repetition-out jackknife).

| Cell | Policy | Method | r | Bias (MCSE) | MSE/exact (z) | Centered var/exact (jk z) | Wald miss lower/upper | Exact-var miss lower/upper | Skew (jk SE) |
|---|---|---|---|---|---|---|---|---|---|
| informative | history_large_after_exception | ipw | 4 | -0.00060 (0.00055) | 1.045 (+0.96) | 1.044 (+0.95) | 0.029/0.029 | 0.031/0.027 | +0.009 (0.072) |
| informative | history_large_after_exception | ipw | 16 | -0.00034 (0.00028) | 1.066 (+1.31) | 1.066 (+1.30) | 0.026/0.030 | 0.026/0.030 | +0.171 (0.094) |
| informative | history_large_after_exception | fresh | 4 | +0.00035 (0.00041) | 0.979 (-0.47) | 0.979 (-0.46) | 0.024/0.028 | 0.029/0.023 | -0.109 (0.078) |
| informative | history_large_after_exception | fresh | 16 | +0.00021 (0.00020) | 0.963 (-0.83) | 0.963 (-0.83) | 0.017/0.030 | 0.018/0.028 | -0.013 (0.084) |
| informative | history_large_after_exception | ipw_minus_fresh | 4 | -0.00095 (0.00069) | 1.050 (+1.03) | 1.049 (+1.01) | 0.033/0.024 | 0.033/0.023 | -0.015 (0.079) |
| informative | history_large_after_exception | ipw_minus_fresh | 16 | -0.00055 (0.00034) | 1.024 (+0.50) | 1.022 (+0.46) | 0.027/0.024 | 0.027/0.024 | +0.068 (0.083) |
| informative | prompt_only_large_if_hard | ipw | 4 | +0.00124 (0.00097) | 0.938 (-1.34) | 0.937 (-1.37) | 0.054/0.010 | 0.015/0.034 | +0.285 (0.081) |
| informative | prompt_only_large_if_hard | ipw | 16 | +0.00057 (0.00051) | 1.042 (+0.96) | 1.042 (+0.95) | 0.048/0.008 | 0.023/0.034 | +0.038 (0.062) |
| informative | prompt_only_large_if_hard | fresh | 4 | -0.00040 (0.00043) | 0.954 (-1.10) | 0.954 (-1.10) | 0.025/0.020 | 0.028/0.015 | -0.015 (0.075) |
| informative | prompt_only_large_if_hard | fresh | 16 | -0.00046 (0.00021) | 0.944 (-1.31) | 0.941 (-1.41) | 0.027/0.016 | 0.029/0.015 | -0.145 (0.078) |
| informative | prompt_only_large_if_hard | ipw_minus_fresh | 4 | +0.00164 (0.00108) | 0.962 (-0.83) | 0.961 (-0.87) | 0.048/0.011 | 0.018/0.039 | +0.181 (0.076) |
| informative | prompt_only_large_if_hard | ipw_minus_fresh | 16 | +0.00103 (0.00056) | 1.031 (+0.75) | 1.029 (+0.69) | 0.032/0.012 | 0.019/0.024 | +0.018 (0.063) |
| informative | fixed_LS | ipw | 4 | +0.00030 (0.00105) | 1.070 (+1.38) | 1.071 (+1.41) | 0.037/0.019 | 0.019/0.036 | +0.336 (0.086) |
| informative | fixed_LS | ipw | 16 | -0.00016 (0.00051) | 1.001 (+0.02) | 1.002 (+0.04) | 0.033/0.016 | 0.025/0.027 | +0.149 (0.095) |
| informative | fixed_LS | fresh | 4 | +0.00053 (0.00043) | 0.972 (-0.65) | 0.971 (-0.66) | 0.016/0.031 | 0.017/0.026 | +0.054 (0.073) |
| informative | fixed_LS | fresh | 16 | -0.00000 (0.00022) | 1.017 (+0.38) | 1.018 (+0.40) | 0.023/0.030 | 0.023/0.028 | -0.002 (0.071) |
| informative | fixed_LS | ipw_minus_fresh | 4 | -0.00023 (0.00113) | 1.045 (+0.90) | 1.046 (+0.92) | 0.035/0.016 | 0.015/0.034 | +0.304 (0.092) |
| informative | fixed_LS | ipw_minus_fresh | 16 | -0.00016 (0.00055) | 0.987 (-0.27) | 0.988 (-0.25) | 0.027/0.018 | 0.023/0.022 | +0.114 (0.106) |
| weak | history_large_after_exception | ipw | 4 | +0.00045 (0.00055) | 1.035 (+0.73) | 1.036 (+0.74) | 0.023/0.040 | 0.022/0.039 | +0.028 (0.088) |
| weak | history_large_after_exception | ipw | 16 | +0.00046 (0.00026) | 0.932 (-1.66) | 0.930 (-1.72) | 0.017/0.025 | 0.018/0.025 | +0.084 (0.068) |
| weak | history_large_after_exception | fresh | 4 | +0.00050 (0.00043) | 0.990 (-0.23) | 0.989 (-0.24) | 0.020/0.030 | 0.022/0.029 | -0.003 (0.080) |
| weak | history_large_after_exception | fresh | 16 | +0.00010 (0.00021) | 0.972 (-0.65) | 0.973 (-0.64) | 0.023/0.033 | 0.025/0.032 | -0.016 (0.073) |
| weak | history_large_after_exception | ipw_minus_fresh | 4 | -0.00005 (0.00069) | 0.991 (-0.20) | 0.992 (-0.18) | 0.027/0.015 | 0.027/0.015 | -0.130 (0.098) |
| weak | history_large_after_exception | ipw_minus_fresh | 16 | +0.00036 (0.00033) | 0.905 (-2.43) | 0.904 (-2.43) | 0.019/0.018 | 0.019/0.018 | -0.089 (0.070) |
| weak | prompt_only_large_if_hard | ipw | 4 | -0.00106 (0.00111) | 0.979 (-0.47) | 0.979 (-0.47) | 0.062/0.011 | 0.022/0.027 | +0.196 (0.087) |
| weak | prompt_only_large_if_hard | ipw | 16 | +0.00019 (0.00057) | 1.034 (+0.70) | 1.035 (+0.72) | 0.037/0.015 | 0.023/0.028 | +0.089 (0.088) |
| weak | prompt_only_large_if_hard | fresh | 4 | -0.00030 (0.00043) | 0.934 (-1.60) | 0.934 (-1.58) | 0.023/0.024 | 0.023/0.022 | +0.032 (0.076) |
| weak | prompt_only_large_if_hard | fresh | 16 | -0.00007 (0.00022) | 0.961 (-0.90) | 0.962 (-0.88) | 0.019/0.019 | 0.020/0.018 | +0.015 (0.081) |
| weak | prompt_only_large_if_hard | ipw_minus_fresh | 4 | -0.00076 (0.00120) | 0.990 (-0.23) | 0.990 (-0.22) | 0.044/0.014 | 0.021/0.031 | +0.156 (0.073) |
| weak | prompt_only_large_if_hard | ipw_minus_fresh | 16 | +0.00026 (0.00061) | 1.034 (+0.72) | 1.035 (+0.73) | 0.036/0.020 | 0.025/0.036 | +0.079 (0.079) |
| weak | fixed_LS | ipw | 4 | -0.00085 (0.00118) | 1.053 (+1.07) | 1.053 (+1.07) | 0.066/0.014 | 0.016/0.040 | +0.313 (0.081) |
| weak | fixed_LS | ipw | 16 | +0.00020 (0.00060) | 1.082 (+1.74) | 1.083 (+1.76) | 0.048/0.020 | 0.029/0.031 | +0.090 (0.074) |
| weak | fixed_LS | fresh | 4 | +0.00054 (0.00045) | 1.058 (+1.21) | 1.058 (+1.20) | 0.024/0.034 | 0.027/0.032 | +0.038 (0.084) |
| weak | fixed_LS | fresh | 16 | +0.00008 (0.00023) | 1.104 (+1.94) | 1.105 (+1.96) | 0.030/0.035 | 0.033/0.033 | +0.182 (0.109) |
| weak | fixed_LS | ipw_minus_fresh | 4 | -0.00139 (0.00126) | 1.043 (+0.87) | 1.042 (+0.85) | 0.056/0.014 | 0.024/0.030 | +0.260 (0.084) |
| weak | fixed_LS | ipw_minus_fresh | 16 | +0.00012 (0.00065) | 1.101 (+2.08) | 1.102 (+2.10) | 0.045/0.019 | 0.029/0.029 | +0.094 (0.081) |

## Weak / fixed_LS: five largest squared-error contributions (retained in every summary)

| Method | r | Repetition IDs (share of sum of squared errors) | Top-5 share |
|---|---|---|---|
| ipw | 4 | 539 (0.0124), 12 (0.0118), 597 (0.0114), 802 (0.0105), 954 (0.0092) | 0.0553 |
| ipw | 16 | 902 (0.0124), 975 (0.0095), 12 (0.0090), 332 (0.0089), 232 (0.0083) | 0.0481 |
| fresh | 4 | 933 (0.0137), 272 (0.0108), 862 (0.0106), 202 (0.0098), 6 (0.0095) | 0.0544 |
| fresh | 16 | 933 (0.0216), 272 (0.0121), 648 (0.0101), 579 (0.0089), 394 (0.0078) | 0.0604 |
| ipw_minus_fresh | 4 | 12 (0.0141), 597 (0.0117), 811 (0.0108), 954 (0.0082), 696 (0.0078) | 0.0525 |
| ipw_minus_fresh | 16 | 902 (0.0131), 12 (0.0119), 975 (0.0104), 208 (0.0097), 232 (0.0089) | 0.0539 |
