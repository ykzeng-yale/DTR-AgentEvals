# Fixed-score coverage component (DTR-REQ-003 P0; lead f0b4fa2)

Completion 1.0000; nominal 95% Wald intervals with within-block variance; exact-variance intervals as diagnostic.

| Cell | Policy | Estimand | Wald coverage (MCSE) [Wilson] | Exact-var coverage | Mean est. var / exact | Emp. var / exact | Bias (MCSE) | Avg length | Fail/zero |
|---|---|---|---|---|---|---|---|---|---|
| informative-uniform_floor_0.5 | history_large_after_exception | ipw | 0.9540 (0.0047) [0.9439, 0.9623] | 0.9545 | 1.0020 | 0.9514 | +0.00034 (0.00058) | 0.1038 | 0/0 |
| informative-uniform_floor_0.5 | history_large_after_exception | fresh | 0.9595 (0.0044) [0.9499, 0.9673] | 0.9605 | 0.9995 | 0.9647 | -0.00046 (0.00029) | 0.0511 | 0/0 |
| informative-uniform_floor_0.5 | history_large_after_exception | ipw_minus_fresh | 0.9510 (0.0048) [0.9406, 0.9596] | 0.9510 | 1.0015 | 0.9773 | +0.00081 (0.00065) | 0.1157 | 0/0 |
| informative-uniform_floor_0.5 | prompt_only_large_if_hard | ipw | 0.9515 (0.0048) [0.9412, 0.9601] | 0.9510 | 0.9997 | 1.0072 | -0.00021 (0.00057) | 0.0999 | 0/0 |
| informative-uniform_floor_0.5 | prompt_only_large_if_hard | fresh | 0.9560 (0.0046) [0.9461, 0.9641] | 0.9580 | 0.9991 | 0.9606 | +0.00020 (0.00031) | 0.0546 | 0/0 |
| informative-uniform_floor_0.5 | prompt_only_large_if_hard | ipw_minus_fresh | 0.9475 (0.0050) [0.9368, 0.9564] | 0.9455 | 0.9996 | 1.0104 | -0.00041 (0.00065) | 0.1138 | 0/0 |
| informative-uniform_floor_0.5 | fixed_LS | ipw | 0.9560 (0.0046) [0.9461, 0.9641] | 0.9575 | 0.9995 | 0.9576 | -0.00044 (0.00056) | 0.1007 | 0/0 |
| informative-uniform_floor_0.5 | fixed_LS | fresh | 0.9530 (0.0047) [0.9428, 0.9614] | 0.9570 | 0.9995 | 1.0040 | +0.00007 (0.00031) | 0.0537 | 0/0 |
| informative-uniform_floor_0.5 | fixed_LS | ipw_minus_fresh | 0.9585 (0.0045) [0.9488, 0.9664] | 0.9575 | 0.9995 | 0.9514 | -0.00051 (0.00064) | 0.1142 | 0/0 |
| informative-feedback_dependent_floor_0.2 | history_large_after_exception | ipw | 0.9475 (0.0050) [0.9368, 0.9564] | 0.9470 | 1.0012 | 0.9940 | -0.00037 (0.00038) | 0.0662 | 0/0 |
| informative-feedback_dependent_floor_0.2 | history_large_after_exception | fresh | 0.9470 (0.0050) [0.9363, 0.9560] | 0.9480 | 1.0013 | 1.0440 | -0.00030 (0.00030) | 0.0512 | 0/0 |
| informative-feedback_dependent_floor_0.2 | history_large_after_exception | ipw_minus_fresh | 0.9495 (0.0049) [0.9390, 0.9583] | 0.9490 | 1.0012 | 1.0090 | -0.00007 (0.00048) | 0.0837 | 0/0 |
| informative-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | ipw | 0.9315 (0.0056) [0.9196, 0.9418] | 0.9420 | 0.9996 | 1.0688 | +0.00016 (0.00073) | 0.1216 | 0/0 |
| informative-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | fresh | 0.9530 (0.0047) [0.9428, 0.9614] | 0.9540 | 0.9995 | 0.9949 | +0.00038 (0.00031) | 0.0546 | 0/0 |
| informative-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | ipw_minus_fresh | 0.9440 (0.0051) [0.9330, 0.9533] | 0.9490 | 0.9996 | 1.0230 | -0.00022 (0.00078) | 0.1337 | 0/0 |
| informative-feedback_dependent_floor_0.2 | fixed_LS | ipw | 0.9415 (0.0052) [0.9303, 0.9510] | 0.9440 | 1.0025 | 1.0153 | +0.00017 (0.00072) | 0.1248 | 0/0 |
| informative-feedback_dependent_floor_0.2 | fixed_LS | fresh | 0.9500 (0.0049) [0.9396, 0.9587] | 0.9505 | 1.0005 | 0.9737 | -0.00025 (0.00030) | 0.0538 | 0/0 |
| informative-feedback_dependent_floor_0.2 | fixed_LS | ipw_minus_fresh | 0.9470 (0.0050) [0.9363, 0.9560] | 0.9490 | 1.0022 | 1.0005 | +0.00042 (0.00078) | 0.1360 | 0/0 |
| weak-uniform_floor_0.5 | history_large_after_exception | ipw | 0.9470 (0.0050) [0.9363, 0.9560] | 0.9490 | 0.9993 | 0.9904 | +0.00023 (0.00057) | 0.1010 | 0/0 |
| weak-uniform_floor_0.5 | history_large_after_exception | fresh | 0.9425 (0.0052) [0.9314, 0.9519] | 0.9425 | 1.0007 | 1.0082 | +0.00017 (0.00031) | 0.0540 | 0/0 |
| weak-uniform_floor_0.5 | history_large_after_exception | ipw_minus_fresh | 0.9485 (0.0049) [0.9379, 0.9574] | 0.9515 | 0.9996 | 0.9806 | +0.00007 (0.00065) | 0.1146 | 0/0 |
| weak-uniform_floor_0.5 | prompt_only_large_if_hard | ipw | 0.9575 (0.0045) [0.9477, 0.9655] | 0.9605 | 0.9990 | 0.9449 | -0.00016 (0.00055) | 0.0998 | 0/0 |
| weak-uniform_floor_0.5 | prompt_only_large_if_hard | fresh | 0.9470 (0.0050) [0.9363, 0.9560] | 0.9465 | 0.9986 | 1.0215 | +0.00023 (0.00031) | 0.0545 | 0/0 |
| weak-uniform_floor_0.5 | prompt_only_large_if_hard | ipw_minus_fresh | 0.9520 (0.0048) [0.9417, 0.9605] | 0.9545 | 0.9989 | 0.9645 | -0.00039 (0.00064) | 0.1138 | 0/0 |
| weak-uniform_floor_0.5 | fixed_LS | ipw | 0.9400 (0.0053) [0.9287, 0.9496] | 0.9445 | 0.9968 | 1.0472 | -0.00017 (0.00059) | 0.1006 | 0/0 |
| weak-uniform_floor_0.5 | fixed_LS | fresh | 0.9475 (0.0050) [0.9368, 0.9564] | 0.9500 | 1.0008 | 1.0047 | -0.00016 (0.00031) | 0.0538 | 0/0 |
| weak-uniform_floor_0.5 | fixed_LS | ipw_minus_fresh | 0.9470 (0.0050) [0.9363, 0.9560] | 0.9465 | 0.9977 | 1.0281 | -0.00001 (0.00066) | 0.1141 | 0/0 |
| weak-feedback_dependent_floor_0.2 | history_large_after_exception | ipw | 0.9440 (0.0051) [0.9330, 0.9533] | 0.9435 | 1.0013 | 1.0802 | -0.00014 (0.00040) | 0.0670 | 0/0 |
| weak-feedback_dependent_floor_0.2 | history_large_after_exception | fresh | 0.9490 (0.0049) [0.9385, 0.9578] | 0.9475 | 1.0005 | 0.9925 | +0.00005 (0.00031) | 0.0540 | 0/0 |
| weak-feedback_dependent_floor_0.2 | history_large_after_exception | ipw_minus_fresh | 0.9490 (0.0049) [0.9385, 0.9578] | 0.9495 | 1.0010 | 1.0273 | -0.00019 (0.00050) | 0.0861 | 0/0 |
| weak-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | ipw | 0.9300 (0.0057) [0.9180, 0.9404] | 0.9530 | 0.9870 | 1.0436 | -0.00076 (0.00081) | 0.1353 | 0/0 |
| weak-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | fresh | 0.9445 (0.0051) [0.9336, 0.9537] | 0.9485 | 0.9985 | 1.0598 | +0.00021 (0.00032) | 0.0545 | 0/0 |
| weak-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | ipw_minus_fresh | 0.9375 (0.0054) [0.9260, 0.9473] | 0.9505 | 0.9885 | 1.0177 | -0.00097 (0.00086) | 0.1462 | 0/0 |
| weak-feedback_dependent_floor_0.2 | fixed_LS | ipw | 0.9330 (0.0056) [0.9212, 0.9431] | 0.9425 | 0.9996 | 1.0646 | +0.00014 (0.00084) | 0.1403 | 0/0 |
| weak-feedback_dependent_floor_0.2 | fixed_LS | fresh | 0.9615 (0.0043) [0.9521, 0.9691] | 0.9575 | 0.9994 | 0.9452 | +0.00008 (0.00030) | 0.0537 | 0/0 |
| weak-feedback_dependent_floor_0.2 | fixed_LS | ipw_minus_fresh | 0.9355 (0.0055) [0.9239, 0.9455] | 0.9450 | 0.9995 | 1.0735 | +0.00006 (0.00090) | 0.1505 | 0/0 |
