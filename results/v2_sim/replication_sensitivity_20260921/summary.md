# Replication-sensitivity development batch (DTR-REQ-003 P0; lead 9550aa4)

Completion 1.0000. Nested first-4 versus all-16 logged/fresh replicates on the same streams; nominal 95% Wald intervals with within-block variance; exact-variance intervals as diagnostic. Sensitivity to replication (budget), not a cost-free repair.

| Cell | Policy | Estimand | r | Wald cov. (MCSE) | Exact-var cov. | Lower/upper miss | Corr(err,var) | Var CV | Mean est./exact var | Bias (MCSE) | Avg length | Fail/zero |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| informative | history_large_after_exception | ipw | 4 | 0.9420 (0.0074) | 0.9420 | 0.0290/0.0290 | -0.355 | 0.038 | 0.9993 | -0.00060 (0.00055) | 0.0661 | 0/0 |
| informative | history_large_after_exception | ipw | 16 | 0.9440 (0.0073) | 0.9440 | 0.0260/0.0300 | -0.426 | 0.015 | 1.0002 | -0.00034 (0.00028) | 0.0331 | 0/0 |
| informative | history_large_after_exception | fresh | 4 | 0.9480 (0.0070) | 0.9480 | 0.0240/0.0280 | -0.729 | 0.047 | 0.9990 | +0.00035 (0.00041) | 0.0511 | 0/0 |
| informative | history_large_after_exception | fresh | 16 | 0.9530 (0.0067) | 0.9540 | 0.0170/0.0300 | -0.857 | 0.020 | 1.0002 | +0.00021 (0.00020) | 0.0256 | 0/0 |
| informative | history_large_after_exception | ipw_minus_fresh | 4 | 0.9430 (0.0073) | 0.9440 | 0.0330/0.0240 | 0.015 | 0.030 | 0.9992 | -0.00095 (0.00069) | 0.0836 | 0/0 |
| informative | history_large_after_exception | ipw_minus_fresh | 16 | 0.9490 (0.0070) | 0.9490 | 0.0270/0.0240 | 0.062 | 0.012 | 1.0002 | -0.00055 (0.00034) | 0.0418 | 0/0 |
| informative | prompt_only_large_if_hard | ipw | 4 | 0.9360 (0.0077) | 0.9510 | 0.0540/0.0100 | 0.685 | 0.445 | 1.0223 | +0.00124 (0.00097) | 0.1231 | 0/0 |
| informative | prompt_only_large_if_hard | ipw | 16 | 0.9440 (0.0073) | 0.9430 | 0.0480/0.0080 | 0.711 | 0.231 | 1.0056 | +0.00057 (0.00051) | 0.0621 | 0/0 |
| informative | prompt_only_large_if_hard | fresh | 4 | 0.9550 (0.0066) | 0.9570 | 0.0250/0.0200 | -0.708 | 0.041 | 0.9998 | -0.00040 (0.00043) | 0.0546 | 0/0 |
| informative | prompt_only_large_if_hard | fresh | 16 | 0.9570 (0.0064) | 0.9560 | 0.0270/0.0160 | -0.821 | 0.017 | 1.0003 | -0.00046 (0.00021) | 0.0273 | 0/0 |
| informative | prompt_only_large_if_hard | ipw_minus_fresh | 4 | 0.9410 (0.0075) | 0.9430 | 0.0480/0.0110 | 0.635 | 0.374 | 1.0187 | +0.00164 (0.00108) | 0.1351 | 0/0 |
| informative | prompt_only_large_if_hard | ipw_minus_fresh | 16 | 0.9560 (0.0065) | 0.9570 | 0.0320/0.0120 | 0.658 | 0.194 | 1.0048 | +0.00103 (0.00056) | 0.0679 | 0/0 |
| informative | fixed_LS | ipw | 4 | 0.9440 (0.0073) | 0.9450 | 0.0370/0.0190 | 0.616 | 0.301 | 1.0063 | +0.00030 (0.00105) | 0.1250 | 0/0 |
| informative | fixed_LS | ipw | 16 | 0.9510 (0.0068) | 0.9480 | 0.0330/0.0160 | 0.622 | 0.149 | 1.0024 | -0.00016 (0.00051) | 0.0628 | 0/0 |
| informative | fixed_LS | fresh | 4 | 0.9530 (0.0067) | 0.9570 | 0.0160/0.0310 | -0.650 | 0.042 | 0.9977 | +0.00053 (0.00043) | 0.0537 | 0/0 |
| informative | fixed_LS | fresh | 16 | 0.9470 (0.0071) | 0.9490 | 0.0230/0.0300 | -0.807 | 0.018 | 1.0002 | -0.00000 (0.00022) | 0.0269 | 0/0 |
| informative | fixed_LS | ipw_minus_fresh | 4 | 0.9490 (0.0070) | 0.9510 | 0.0350/0.0160 | 0.572 | 0.255 | 1.0050 | -0.00023 (0.00113) | 0.1362 | 0/0 |
| informative | fixed_LS | ipw_minus_fresh | 16 | 0.9550 (0.0066) | 0.9550 | 0.0270/0.0180 | 0.568 | 0.126 | 1.0021 | -0.00016 (0.00055) | 0.0684 | 0/0 |
| weak | history_large_after_exception | ipw | 4 | 0.9370 (0.0077) | 0.9390 | 0.0230/0.0400 | -0.211 | 0.036 | 1.0021 | +0.00045 (0.00055) | 0.0670 | 0/0 |
| weak | history_large_after_exception | ipw | 16 | 0.9580 (0.0063) | 0.9570 | 0.0170/0.0250 | -0.215 | 0.014 | 1.0001 | +0.00046 (0.00026) | 0.0335 | 0/0 |
| weak | history_large_after_exception | fresh | 4 | 0.9500 (0.0069) | 0.9490 | 0.0200/0.0300 | -0.620 | 0.043 | 1.0011 | +0.00050 (0.00043) | 0.0541 | 0/0 |
| weak | history_large_after_exception | fresh | 16 | 0.9440 (0.0073) | 0.9430 | 0.0230/0.0330 | -0.753 | 0.017 | 0.9993 | +0.00010 (0.00021) | 0.0270 | 0/0 |
| weak | history_large_after_exception | ipw_minus_fresh | 4 | 0.9580 (0.0063) | 0.9580 | 0.0270/0.0150 | 0.110 | 0.028 | 1.0017 | -0.00005 (0.00069) | 0.0861 | 0/0 |
| weak | history_large_after_exception | ipw_minus_fresh | 16 | 0.9630 (0.0060) | 0.9630 | 0.0190/0.0180 | 0.161 | 0.011 | 0.9998 | +0.00036 (0.00033) | 0.0430 | 0/0 |
| weak | prompt_only_large_if_hard | ipw | 4 | 0.9270 (0.0082) | 0.9510 | 0.0620/0.0110 | 0.697 | 0.387 | 0.9947 | -0.00106 (0.00111) | 0.1358 | 0/0 |
| weak | prompt_only_large_if_hard | ipw | 16 | 0.9480 (0.0070) | 0.9490 | 0.0370/0.0150 | 0.705 | 0.189 | 1.0059 | +0.00019 (0.00057) | 0.0692 | 0/0 |
| weak | prompt_only_large_if_hard | fresh | 4 | 0.9530 (0.0067) | 0.9550 | 0.0230/0.0240 | -0.687 | 0.043 | 1.0005 | -0.00030 (0.00043) | 0.0546 | 0/0 |
| weak | prompt_only_large_if_hard | fresh | 16 | 0.9620 (0.0060) | 0.9620 | 0.0190/0.0190 | -0.844 | 0.017 | 1.0003 | -0.00007 (0.00022) | 0.0273 | 0/0 |
| weak | prompt_only_large_if_hard | ipw_minus_fresh | 4 | 0.9420 (0.0074) | 0.9480 | 0.0440/0.0140 | 0.656 | 0.335 | 0.9955 | -0.00076 (0.00120) | 0.1467 | 0/0 |
| weak | prompt_only_large_if_hard | ipw_minus_fresh | 16 | 0.9440 (0.0073) | 0.9390 | 0.0360/0.0200 | 0.660 | 0.164 | 1.0052 | +0.00026 (0.00061) | 0.0744 | 0/0 |
| weak | fixed_LS | ipw | 4 | 0.9200 (0.0086) | 0.9440 | 0.0660/0.0140 | 0.704 | 0.374 | 0.9847 | -0.00085 (0.00118) | 0.1393 | 0/0 |
| weak | fixed_LS | ipw | 16 | 0.9320 (0.0080) | 0.9400 | 0.0480/0.0200 | 0.722 | 0.194 | 0.9996 | +0.00020 (0.00060) | 0.0710 | 0/0 |
| weak | fixed_LS | fresh | 4 | 0.9420 (0.0074) | 0.9410 | 0.0240/0.0340 | -0.707 | 0.042 | 0.9981 | +0.00054 (0.00045) | 0.0537 | 0/0 |
| weak | fixed_LS | fresh | 16 | 0.9350 (0.0078) | 0.9340 | 0.0300/0.0350 | -0.819 | 0.018 | 0.9994 | +0.00008 (0.00023) | 0.0269 | 0/0 |
| weak | fixed_LS | ipw_minus_fresh | 4 | 0.9300 (0.0081) | 0.9460 | 0.0560/0.0140 | 0.659 | 0.327 | 0.9864 | -0.00139 (0.00126) | 0.1496 | 0/0 |
| weak | fixed_LS | ipw_minus_fresh | 16 | 0.9360 (0.0077) | 0.9420 | 0.0450/0.0190 | 0.668 | 0.169 | 0.9996 | +0.00012 (0.00065) | 0.0760 | 0/0 |

| Cell | Policy | Estimand | Paired r16−r4 Wald coverage (MCSE) | Paired r16−r4 exact-var coverage (MCSE) | Wald−exact r4 | Wald−exact r16 | Length ratio r16/r4 |
|---|---|---|---|---|---|---|---|
| informative | history_large_after_exception | ipw | +0.0020 (0.0093) | +0.0020 (0.0094) | +0.0000 (0.0020) | +0.0000 (0.0000) | 0.5003 |
| informative | history_large_after_exception | fresh | +0.0050 (0.0085) | +0.0060 (0.0085) | +0.0000 (0.0032) | -0.0010 (0.0017) | 0.5004 |
| informative | history_large_after_exception | ipw_minus_fresh | +0.0060 (0.0091) | +0.0050 (0.0090) | -0.0010 (0.0022) | +0.0000 (0.0000) | 0.5003 |
| informative | prompt_only_large_if_hard | ipw | +0.0080 (0.0097) | -0.0080 (0.0095) | -0.0150 (0.0081) | +0.0010 (0.0071) | 0.5042 |
| informative | prompt_only_large_if_hard | fresh | +0.0020 (0.0085) | -0.0010 (0.0084) | -0.0020 (0.0032) | +0.0010 (0.0017) | 0.5002 |
| informative | prompt_only_large_if_hard | ipw_minus_fresh | +0.0150 (0.0094) | +0.0140 (0.0094) | -0.0020 (0.0077) | -0.0010 (0.0050) | 0.5024 |
| informative | fixed_LS | ipw | +0.0070 (0.0091) | +0.0030 (0.0091) | -0.0010 (0.0062) | +0.0030 (0.0044) | 0.5027 |
| informative | fixed_LS | fresh | -0.0060 (0.0094) | -0.0080 (0.0091) | -0.0040 (0.0024) | -0.0020 (0.0020) | 0.5007 |
| informative | fixed_LS | ipw_minus_fresh | +0.0060 (0.0085) | +0.0040 (0.0085) | -0.0020 (0.0062) | +0.0000 (0.0032) | 0.5019 |
| weak | history_large_after_exception | ipw | +0.0210 (0.0085) | +0.0180 (0.0085) | -0.0020 (0.0014) | +0.0010 (0.0010) | 0.4996 |
| weak | history_large_after_exception | fresh | -0.0060 (0.0099) | -0.0060 (0.0099) | +0.0010 (0.0017) | +0.0010 (0.0017) | 0.4997 |
| weak | history_large_after_exception | ipw_minus_fresh | +0.0050 (0.0078) | +0.0050 (0.0078) | +0.0000 (0.0014) | +0.0000 (0.0000) | 0.4996 |
| weak | prompt_only_large_if_hard | ipw | +0.0210 (0.0096) | -0.0020 (0.0087) | -0.0240 (0.0076) | -0.0010 (0.0052) | 0.5094 |
| weak | prompt_only_large_if_hard | fresh | +0.0090 (0.0083) | +0.0070 (0.0082) | -0.0020 (0.0014) | +0.0000 (0.0014) | 0.5001 |
| weak | prompt_only_large_if_hard | ipw_minus_fresh | +0.0020 (0.0094) | -0.0090 (0.0093) | -0.0060 (0.0066) | +0.0050 (0.0052) | 0.5073 |
| weak | fixed_LS | ipw | +0.0120 (0.0107) | -0.0040 (0.0098) | -0.0240 (0.0087) | -0.0080 (0.0055) | 0.5098 |
| weak | fixed_LS | fresh | -0.0070 (0.0096) | -0.0070 (0.0096) | +0.0010 (0.0022) | +0.0010 (0.0022) | 0.5004 |
| weak | fixed_LS | ipw_minus_fresh | +0.0060 (0.0105) | -0.0040 (0.0092) | -0.0160 (0.0069) | -0.0060 (0.0055) | 0.5079 |
