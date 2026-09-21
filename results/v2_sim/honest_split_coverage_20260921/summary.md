# Honest-split DR, repeated-training coverage (DTR-REQ-003 P0; lead 3f4dfc2) — DEVELOPMENT

Completed 4000 of 4000 requested repetitions (fraction 1.0000). Nominal 95% Wald intervals; Q refitted per repetition. Coverage over repeated training/evaluation samples, not conditional on a fixed fit. Training cost separate.

| Cell | Policy | Estimand | Coverage (MCSE) [Wilson] | Lower/upper miss | Bias (MCSE) | RMSE | Emp. var | Mean est. var | Var CV | Corr(err,var) | Avg length | Fail/zero |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| informative-uniform_floor_0.5 | history_large_after_exception | dr | 0.9400 (0.0075) [0.9235, 0.9531] | 0.0210/0.0390 | +0.00031 (0.00063) | 0.01984 | 3.937e-04 | 3.930e-04 | 0.105 | -0.513 | 0.0776 | 0/0 |
| informative-uniform_floor_0.5 | history_large_after_exception | ipw | 0.9530 (0.0067) [0.9381, 0.9645] | 0.0280/0.0190 | +0.00080 (0.00084) | 0.02663 | 7.092e-04 | 7.023e-04 | 0.075 | 0.645 | 0.1038 | 0/0 |
| informative-uniform_floor_0.5 | history_large_after_exception | fresh | 0.9600 (0.0062) [0.9460, 0.9705] | 0.0180/0.0220 | +0.00027 (0.00039) | 0.01230 | 1.514e-04 | 1.701e-04 | 0.044 | -0.705 | 0.0511 | 0/0 |
| informative-uniform_floor_0.5 | history_large_after_exception | dr_minus_fresh | 0.9560 (0.0065) [0.9414, 0.9671] | 0.0200/0.0240 | +0.00004 (0.00076) | 0.02393 | 5.734e-04 | 5.631e-04 | 0.074 | -0.352 | 0.0930 | 0/0 |
| informative-uniform_floor_0.5 | history_large_after_exception | ipw_minus_fresh | 0.9450 (0.0072) [0.9291, 0.9575] | 0.0320/0.0230 | +0.00052 (0.00095) | 0.02999 | 8.999e-04 | 8.724e-04 | 0.061 | 0.628 | 0.1157 | 0/0 |
| informative-uniform_floor_0.5 | prompt_only_large_if_hard | dr | 0.9470 (0.0071) [0.9313, 0.9593] | 0.0250/0.0280 | +0.00036 (0.00064) | 0.02028 | 4.117e-04 | 4.181e-04 | 0.090 | -0.389 | 0.0801 | 0/0 |
| informative-uniform_floor_0.5 | prompt_only_large_if_hard | ipw | 0.9590 (0.0063) [0.9449, 0.9696] | 0.0300/0.0110 | -0.00028 (0.00077) | 0.02427 | 5.896e-04 | 6.509e-04 | 0.074 | 0.605 | 0.0999 | 0/0 |
| informative-uniform_floor_0.5 | prompt_only_large_if_hard | fresh | 0.9600 (0.0062) [0.9460, 0.9705] | 0.0210/0.0190 | -0.00089 (0.00043) | 0.01360 | 1.844e-04 | 1.944e-04 | 0.042 | -0.673 | 0.0546 | 0/0 |
| informative-uniform_floor_0.5 | prompt_only_large_if_hard | dr_minus_fresh | 0.9550 (0.0066) [0.9403, 0.9662] | 0.0220/0.0230 | +0.00125 (0.00076) | 0.02396 | 5.732e-04 | 6.125e-04 | 0.063 | -0.225 | 0.0970 | 0/0 |
| informative-uniform_floor_0.5 | prompt_only_large_if_hard | ipw_minus_fresh | 0.9560 (0.0065) [0.9414, 0.9671] | 0.0280/0.0160 | +0.00062 (0.00087) | 0.02741 | 7.517e-04 | 8.453e-04 | 0.057 | 0.561 | 0.1139 | 0/0 |
| informative-uniform_floor_0.5 | fixed_LS | dr | 0.9460 (0.0071) [0.9302, 0.9584] | 0.0180/0.0360 | +0.00035 (0.00065) | 0.02060 | 4.245e-04 | 4.158e-04 | 0.090 | -0.400 | 0.0799 | 0/0 |
| informative-uniform_floor_0.5 | fixed_LS | ipw | 0.9470 (0.0071) [0.9313, 0.9593] | 0.0290/0.0240 | +0.00103 (0.00083) | 0.02615 | 6.833e-04 | 6.627e-04 | 0.077 | 0.627 | 0.1008 | 0/0 |
| informative-uniform_floor_0.5 | fixed_LS | fresh | 0.9380 (0.0076) [0.9213, 0.9513] | 0.0270/0.0350 | +0.00022 (0.00045) | 0.01424 | 2.030e-04 | 1.880e-04 | 0.044 | -0.647 | 0.0537 | 0/0 |
| informative-uniform_floor_0.5 | fixed_LS | dr_minus_fresh | 0.9490 (0.0070) [0.9336, 0.9610] | 0.0240/0.0270 | +0.00014 (0.00078) | 0.02454 | 6.030e-04 | 6.038e-04 | 0.063 | -0.238 | 0.0963 | 0/0 |
| informative-uniform_floor_0.5 | fixed_LS | ipw_minus_fresh | 0.9540 (0.0066) [0.9392, 0.9653] | 0.0280/0.0180 | +0.00081 (0.00092) | 0.02905 | 8.442e-04 | 8.507e-04 | 0.061 | 0.602 | 0.1143 | 0/0 |
| informative-feedback_dependent_floor_0.2 | history_large_after_exception | dr | 0.9450 (0.0072) [0.9291, 0.9575] | 0.0230/0.0320 | +0.00029 (0.00047) | 0.01475 | 2.178e-04 | 2.126e-04 | 0.056 | -0.723 | 0.0571 | 0/0 |
| informative-feedback_dependent_floor_0.2 | history_large_after_exception | ipw | 0.9310 (0.0080) [0.9136, 0.9451] | 0.0250/0.0440 | +0.00042 (0.00055) | 0.01742 | 3.037e-04 | 2.848e-04 | 0.038 | -0.364 | 0.0661 | 0/0 |
| informative-feedback_dependent_floor_0.2 | history_large_after_exception | fresh | 0.9400 (0.0075) [0.9235, 0.9531] | 0.0260/0.0340 | +0.00002 (0.00041) | 0.01307 | 1.711e-04 | 1.702e-04 | 0.048 | -0.738 | 0.0511 | 0/0 |
| informative-feedback_dependent_floor_0.2 | history_large_after_exception | dr_minus_fresh | 0.9510 (0.0068) [0.9358, 0.9627] | 0.0200/0.0290 | +0.00027 (0.00063) | 0.01979 | 3.919e-04 | 3.828e-04 | 0.038 | -0.181 | 0.0767 | 0/0 |
| informative-feedback_dependent_floor_0.2 | history_large_after_exception | ipw_minus_fresh | 0.9490 (0.0070) [0.9336, 0.9610] | 0.0190/0.0320 | +0.00040 (0.00069) | 0.02189 | 4.794e-04 | 4.550e-04 | 0.030 | 0.021 | 0.0836 | 0/0 |
| informative-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | dr | 0.9510 (0.0068) [0.9358, 0.9627] | 0.0230/0.0260 | -0.00099 (0.00093) | 0.02948 | 8.688e-04 | 8.863e-04 | 0.521 | -0.133 | 0.1133 | 0/0 |
| informative-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | ipw | 0.9440 (0.0073) [0.9280, 0.9566] | 0.0520/0.0040 | -0.00052 (0.00097) | 0.03070 | 9.433e-04 | 9.883e-04 | 0.445 | 0.693 | 0.1205 | 0/0 |
| informative-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | fresh | 0.9480 (0.0070) [0.9324, 0.9601] | 0.0260/0.0260 | +0.00056 (0.00044) | 0.01393 | 1.940e-04 | 1.937e-04 | 0.042 | -0.683 | 0.0545 | 0/0 |
| informative-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | dr_minus_fresh | 0.9340 (0.0079) [0.9169, 0.9478] | 0.0290/0.0370 | -0.00156 (0.00105) | 0.03327 | 1.105e-03 | 1.080e-03 | 0.427 | -0.121 | 0.1263 | 0/0 |
| informative-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | ipw_minus_fresh | 0.9430 (0.0073) [0.9269, 0.9557] | 0.0460/0.0110 | -0.00108 (0.00109) | 0.03451 | 1.191e-03 | 1.182e-03 | 0.373 | 0.640 | 0.1327 | 0/0 |
| informative-feedback_dependent_floor_0.2 | fixed_LS | dr | 0.9360 (0.0077) [0.9191, 0.9496] | 0.0260/0.0380 | +0.00025 (0.00083) | 0.02623 | 6.888e-04 | 6.567e-04 | 0.386 | -0.240 | 0.0988 | 0/0 |
| informative-feedback_dependent_floor_0.2 | fixed_LS | ipw | 0.9560 (0.0065) [0.9414, 0.9671] | 0.0340/0.0100 | +0.00059 (0.00099) | 0.03137 | 9.846e-04 | 1.043e-03 | 0.305 | 0.619 | 0.1253 | 0/0 |
| informative-feedback_dependent_floor_0.2 | fixed_LS | fresh | 0.9530 (0.0067) [0.9381, 0.9645] | 0.0190/0.0280 | +0.00018 (0.00043) | 0.01370 | 1.879e-04 | 1.881e-04 | 0.044 | -0.687 | 0.0538 | 0/0 |
| informative-feedback_dependent_floor_0.2 | fixed_LS | dr_minus_fresh | 0.9330 (0.0079) [0.9158, 0.9469] | 0.0340/0.0330 | +0.00007 (0.00095) | 0.03018 | 9.115e-04 | 8.448e-04 | 0.300 | -0.216 | 0.1128 | 0/0 |
| informative-feedback_dependent_floor_0.2 | fixed_LS | ipw_minus_fresh | 0.9540 (0.0066) [0.9392, 0.9653] | 0.0340/0.0120 | +0.00041 (0.00109) | 0.03450 | 1.192e-03 | 1.231e-03 | 0.259 | 0.560 | 0.1365 | 0/0 |
| weak-uniform_floor_0.5 | history_large_after_exception | dr | 0.9550 (0.0066) [0.9403, 0.9662] | 0.0210/0.0240 | +0.00028 (0.00066) | 0.02076 | 4.314e-04 | 4.431e-04 | 0.089 | -0.326 | 0.0824 | 0/0 |
| weak-uniform_floor_0.5 | history_large_after_exception | ipw | 0.9470 (0.0071) [0.9313, 0.9593] | 0.0280/0.0250 | +0.00079 (0.00080) | 0.02536 | 6.432e-04 | 6.652e-04 | 0.077 | 0.645 | 0.1010 | 0/0 |
| weak-uniform_floor_0.5 | history_large_after_exception | fresh | 0.9580 (0.0063) [0.9437, 0.9688] | 0.0240/0.0180 | -0.00049 (0.00042) | 0.01335 | 1.781e-04 | 1.902e-04 | 0.041 | -0.572 | 0.0541 | 0/0 |
| weak-uniform_floor_0.5 | history_large_after_exception | dr_minus_fresh | 0.9540 (0.0066) [0.9392, 0.9653] | 0.0210/0.0250 | +0.00077 (0.00078) | 0.02464 | 6.074e-04 | 6.333e-04 | 0.063 | -0.205 | 0.0986 | 0/0 |
| weak-uniform_floor_0.5 | history_large_after_exception | ipw_minus_fresh | 0.9500 (0.0069) [0.9347, 0.9619] | 0.0210/0.0290 | +0.00128 (0.00092) | 0.02905 | 8.433e-04 | 8.554e-04 | 0.061 | 0.589 | 0.1146 | 0/0 |
| weak-uniform_floor_0.5 | prompt_only_large_if_hard | dr | 0.9520 (0.0068) [0.9369, 0.9636] | 0.0230/0.0250 | +0.00068 (0.00064) | 0.02019 | 4.074e-04 | 4.371e-04 | 0.090 | -0.389 | 0.0819 | 0/0 |
| weak-uniform_floor_0.5 | prompt_only_large_if_hard | ipw | 0.9640 (0.0059) [0.9506, 0.9739] | 0.0160/0.0200 | +0.00114 (0.00077) | 0.02433 | 5.913e-04 | 6.510e-04 | 0.075 | 0.598 | 0.0999 | 0/0 |
| weak-uniform_floor_0.5 | prompt_only_large_if_hard | fresh | 0.9480 (0.0070) [0.9324, 0.9601] | 0.0250/0.0270 | -0.00009 (0.00044) | 0.01381 | 1.909e-04 | 1.944e-04 | 0.041 | -0.673 | 0.0546 | 0/0 |
| weak-uniform_floor_0.5 | prompt_only_large_if_hard | dr_minus_fresh | 0.9460 (0.0071) [0.9302, 0.9584] | 0.0230/0.0310 | +0.00077 (0.00079) | 0.02488 | 6.189e-04 | 6.315e-04 | 0.064 | -0.190 | 0.0985 | 0/0 |
| weak-uniform_floor_0.5 | prompt_only_large_if_hard | ipw_minus_fresh | 0.9520 (0.0068) [0.9369, 0.9636] | 0.0230/0.0250 | +0.00123 (0.00091) | 0.02878 | 8.277e-04 | 8.454e-04 | 0.059 | 0.590 | 0.1139 | 0/0 |
| weak-uniform_floor_0.5 | fixed_LS | dr | 0.9550 (0.0066) [0.9403, 0.9662] | 0.0180/0.0270 | +0.00023 (0.00065) | 0.02066 | 4.271e-04 | 4.326e-04 | 0.092 | -0.363 | 0.0815 | 0/0 |
| weak-uniform_floor_0.5 | fixed_LS | ipw | 0.9400 (0.0075) [0.9235, 0.9531] | 0.0320/0.0280 | +0.00023 (0.00081) | 0.02571 | 6.616e-04 | 6.617e-04 | 0.078 | 0.627 | 0.1008 | 0/0 |
| weak-uniform_floor_0.5 | fixed_LS | fresh | 0.9550 (0.0066) [0.9403, 0.9662] | 0.0240/0.0210 | -0.00003 (0.00042) | 0.01335 | 1.784e-04 | 1.881e-04 | 0.042 | -0.629 | 0.0537 | 0/0 |
| weak-uniform_floor_0.5 | fixed_LS | dr_minus_fresh | 0.9500 (0.0069) [0.9347, 0.9619] | 0.0210/0.0290 | +0.00026 (0.00076) | 0.02409 | 5.810e-04 | 6.207e-04 | 0.065 | -0.239 | 0.0976 | 0/0 |
| weak-uniform_floor_0.5 | fixed_LS | ipw_minus_fresh | 0.9520 (0.0068) [0.9369, 0.9636] | 0.0250/0.0230 | +0.00026 (0.00090) | 0.02831 | 8.024e-04 | 8.498e-04 | 0.061 | 0.586 | 0.1142 | 0/0 |
| weak-feedback_dependent_floor_0.2 | history_large_after_exception | dr | 0.9470 (0.0071) [0.9313, 0.9593] | 0.0210/0.0320 | +0.00008 (0.00049) | 0.01561 | 2.440e-04 | 2.386e-04 | 0.049 | -0.586 | 0.0605 | 0/0 |
| weak-feedback_dependent_floor_0.2 | history_large_after_exception | ipw | 0.9460 (0.0071) [0.9302, 0.9584] | 0.0260/0.0280 | -0.00006 (0.00055) | 0.01734 | 3.008e-04 | 2.915e-04 | 0.037 | -0.201 | 0.0669 | 0/0 |
| weak-feedback_dependent_floor_0.2 | history_large_after_exception | fresh | 0.9460 (0.0071) [0.9302, 0.9584] | 0.0200/0.0340 | +0.00033 (0.00044) | 0.01391 | 1.936e-04 | 1.903e-04 | 0.043 | -0.598 | 0.0541 | 0/0 |
| weak-feedback_dependent_floor_0.2 | history_large_after_exception | dr_minus_fresh | 0.9550 (0.0066) [0.9403, 0.9662] | 0.0260/0.0190 | -0.00025 (0.00065) | 0.02043 | 4.179e-04 | 4.289e-04 | 0.033 | -0.154 | 0.0812 | 0/0 |
| weak-feedback_dependent_floor_0.2 | history_large_after_exception | ipw_minus_fresh | 0.9550 (0.0066) [0.9403, 0.9662] | 0.0220/0.0230 | -0.00039 (0.00069) | 0.02168 | 4.702e-04 | 4.818e-04 | 0.028 | 0.050 | 0.0860 | 0/0 |
| weak-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | dr | 0.9500 (0.0069) [0.9347, 0.9619] | 0.0210/0.0290 | +0.00125 (0.00093) | 0.02952 | 8.708e-04 | 9.523e-04 | 0.446 | -0.079 | 0.1183 | 0/0 |
| weak-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | ipw | 0.9410 (0.0075) [0.9246, 0.9540] | 0.0480/0.0110 | +0.00252 (0.00110) | 0.03501 | 1.221e-03 | 1.264e-03 | 0.378 | 0.686 | 0.1371 | 0/0 |
| weak-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | fresh | 0.9560 (0.0065) [0.9414, 0.9671] | 0.0190/0.0250 | +0.00039 (0.00043) | 0.01367 | 1.870e-04 | 1.937e-04 | 0.040 | -0.695 | 0.0545 | 0/0 |
| weak-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | dr_minus_fresh | 0.9560 (0.0065) [0.9414, 0.9671] | 0.0250/0.0190 | +0.00086 (0.00102) | 0.03213 | 1.033e-03 | 1.146e-03 | 0.370 | -0.078 | 0.1307 | 0/0 |
| weak-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | ipw_minus_fresh | 0.9520 (0.0068) [0.9369, 0.9636] | 0.0410/0.0070 | +0.00213 (0.00116) | 0.03686 | 1.355e-03 | 1.457e-03 | 0.327 | 0.612 | 0.1478 | 0/0 |
| weak-feedback_dependent_floor_0.2 | fixed_LS | dr | 0.9530 (0.0067) [0.9381, 0.9645] | 0.0270/0.0200 | +0.00067 (0.00094) | 0.02959 | 8.761e-04 | 9.310e-04 | 0.459 | -0.045 | 0.1169 | 0/0 |
| weak-feedback_dependent_floor_0.2 | fixed_LS | ipw | 0.9450 (0.0072) [0.9291, 0.9575] | 0.0500/0.0050 | +0.00149 (0.00113) | 0.03584 | 1.284e-03 | 1.355e-03 | 0.366 | 0.707 | 0.1420 | 0/0 |
| weak-feedback_dependent_floor_0.2 | fixed_LS | fresh | 0.9480 (0.0070) [0.9324, 0.9601] | 0.0220/0.0300 | +0.00026 (0.00045) | 0.01427 | 2.037e-04 | 1.880e-04 | 0.043 | -0.667 | 0.0537 | 0/0 |
| weak-feedback_dependent_floor_0.2 | fixed_LS | dr_minus_fresh | 0.9570 (0.0064) [0.9426, 0.9679] | 0.0240/0.0190 | +0.00041 (0.00103) | 0.03263 | 1.066e-03 | 1.119e-03 | 0.382 | -0.042 | 0.1291 | 0/0 |
| weak-feedback_dependent_floor_0.2 | fixed_LS | ipw_minus_fresh | 0.9450 (0.0072) [0.9291, 0.9575] | 0.0460/0.0090 | +0.00123 (0.00121) | 0.03838 | 1.473e-03 | 1.543e-03 | 0.322 | 0.663 | 0.1521 | 0/0 |

| Cell | Policy | Paired DR−IPW squared error (MCSE) | MSE ratio DR/IPW | OR bias (MCSE) / RMSE (descriptive) | Mean eval fallback fraction |
|---|---|---|---|---|---|
| informative-uniform_floor_0.5 | history_large_after_exception | -3.157e-04 (2.615e-05) | 0.5548 | +0.00035 (0.00064) / 0.02014 | 0.0023 |
| informative-uniform_floor_0.5 | prompt_only_large_if_hard | -1.777e-04 (2.240e-05) | 0.6984 | +0.00049 (0.00066) / 0.02089 | 0.0022 |
| informative-uniform_floor_0.5 | fixed_LS | -2.595e-04 (2.398e-05) | 0.6204 | +0.00021 (0.00065) / 0.02061 | 0.0021 |
| informative-feedback_dependent_floor_0.2 | history_large_after_exception | -8.596e-05 (8.986e-06) | 0.7169 | +0.00006 (0.00046) / 0.01463 | 0.0042 |
| informative-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | -7.370e-05 (4.301e-05) | 0.9218 | +0.00421 (0.00084) / 0.02699 | 0.0113 |
| informative-feedback_dependent_floor_0.2 | fixed_LS | -2.958e-04 (4.155e-05) | 0.6994 | +0.00374 (0.00072) / 0.02298 | 0.0099 |
| weak-uniform_floor_0.5 | history_large_after_exception | -2.122e-04 (2.262e-05) | 0.6701 | +0.00120 (0.00067) / 0.02124 | 0.0004 |
| weak-uniform_floor_0.5 | prompt_only_large_if_hard | -1.845e-04 (2.068e-05) | 0.6883 | +0.00110 (0.00066) / 0.02087 | 0.0004 |
| weak-uniform_floor_0.5 | fixed_LS | -2.343e-04 (2.565e-05) | 0.6455 | +0.00074 (0.00064) / 0.02038 | 0.0004 |
| weak-feedback_dependent_floor_0.2 | history_large_after_exception | -5.676e-05 (8.054e-06) | 0.8112 | +0.00032 (0.00048) / 0.01532 | 0.0036 |
| weak-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | -3.543e-04 (5.111e-05) | 0.7109 | +0.00223 (0.00084) / 0.02667 | 0.0100 |
| weak-feedback_dependent_floor_0.2 | fixed_LS | -4.088e-04 (5.044e-05) | 0.6817 | -0.00110 (0.00084) / 0.02671 | 0.0099 |
