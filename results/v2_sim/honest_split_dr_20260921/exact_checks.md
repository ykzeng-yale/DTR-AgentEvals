# Honest sample-split DR: exact conditional checks (DTR-REQ-003; lead f4db0f7)

Exact enumeration under the known logging kernels, scored through `episode_scores`; no Monte Carlo study. Max |conditional DR mean − truth| over 4 cells × 3 policies × 4 frozen-Q fixtures: 3.3e-16 (tolerance 1e-12). Max relative difference between the enumerated expectation of the within-task variance estimator and the exact conditional variance of the task-equal average (n=250, r=4): 2.2e-15. Known-Q is an oracle control.

| Cell | Policy | Truth | Fixture | DR mean − truth | OR plug-in mean − truth | Fallback mass easy / hard | Score var easy / hard | SE of task-equal avg (n=250, r=4) |
|---|---|---|---|---|---|---|---|---|
| informative-uniform_floor_0.5 | history_large_after_exception | 0.738545 | known_q_ORACLE | +1.1e-16 | +0.00000 | 0.0000 / 0.0000 | 0.2514 / 0.4918 | 0.01928 |
| informative-uniform_floor_0.5 | history_large_after_exception | 0.738545 | zero_q | +1.1e-16 | -0.34855 | 0.3600 / 0.6400 | 0.5304 / 0.9087 | 0.02682 |
| informative-uniform_floor_0.5 | history_large_after_exception | 0.738545 | bounded_wrong_q | -2.2e-16 | +0.01120 | 0.1074 / 0.1272 | 0.3872 / 0.6801 | 0.02310 |
| informative-uniform_floor_0.5 | history_large_after_exception | 0.738545 | fitted_frozen_q_devbatch_rep0 | -1.1e-16 | -0.01488 | 0.0000 / 0.0127 | 0.2593 / 0.5141 | 0.01966 |
| informative-uniform_floor_0.5 | prompt_only_large_if_hard | 0.694388 | known_q_ORACLE | -1.1e-16 | +0.00000 | 0.0000 / 0.0000 | 0.2860 / 0.5175 | 0.02004 |
| informative-uniform_floor_0.5 | prompt_only_large_if_hard | 0.694388 | zero_q | +1.1e-16 | -0.30439 | 0.3600 / 0.6400 | 0.4803 / 0.8537 | 0.02583 |
| informative-uniform_floor_0.5 | prompt_only_large_if_hard | 0.694388 | bounded_wrong_q | +0.0e+00 | +0.03500 | 0.1074 / 0.1272 | 0.4099 / 0.5744 | 0.02218 |
| informative-uniform_floor_0.5 | prompt_only_large_if_hard | 0.694388 | fitted_frozen_q_devbatch_rep0 | +2.2e-16 | -0.00647 | 0.0000 / 0.0127 | 0.3070 / 0.5306 | 0.02046 |
| informative-uniform_floor_0.5 | fixed_LS | 0.697456 | known_q_ORACLE | +2.2e-16 | +0.00000 | 0.0000 / 0.0000 | 0.2980 / 0.4957 | 0.01992 |
| informative-uniform_floor_0.5 | fixed_LS | 0.697456 | zero_q | +0.0e+00 | -0.30746 | 0.3600 / 0.6400 | 0.5403 / 0.8237 | 0.02611 |
| informative-uniform_floor_0.5 | fixed_LS | 0.697456 | bounded_wrong_q | +0.0e+00 | +0.12500 | 0.1074 / 0.1272 | 0.4853 / 0.7213 | 0.02456 |
| informative-uniform_floor_0.5 | fixed_LS | 0.697456 | fitted_frozen_q_devbatch_rep0 | +2.2e-16 | -0.00130 | 0.0000 / 0.0063 | 0.3138 / 0.5102 | 0.02030 |
| informative-feedback_dependent_floor_0.2 | history_large_after_exception | 0.738545 | known_q_ORACLE | +1.1e-16 | +0.00000 | 0.0000 / 0.0000 | 0.1406 / 0.2817 | 0.01453 |
| informative-feedback_dependent_floor_0.2 | history_large_after_exception | 0.738545 | zero_q | +0.0e+00 | -0.34855 | 0.3600 / 0.6400 | 0.2028 / 0.3740 | 0.01698 |
| informative-feedback_dependent_floor_0.2 | history_large_after_exception | 0.738545 | bounded_wrong_q | -3.3e-16 | +0.01120 | 0.0979 / 0.1241 | 0.1639 / 0.3149 | 0.01547 |
| informative-feedback_dependent_floor_0.2 | history_large_after_exception | 0.738545 | fitted_frozen_q_devbatch_rep0 | -3.3e-16 | +0.00704 | 0.0052 / 0.0051 | 0.1425 / 0.2825 | 0.01458 |
| informative-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | 0.694388 | known_q_ORACLE | -1.1e-16 | -0.00000 | 0.0000 / 0.0000 | 0.4397 / 0.9420 | 0.02628 |
| informative-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | 0.694388 | zero_q | +0.0e+00 | -0.30439 | 0.3600 / 0.6400 | 0.5528 / 1.5459 | 0.03239 |
| informative-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | 0.694388 | bounded_wrong_q | +0.0e+00 | +0.03500 | 0.0979 / 0.1241 | 0.5879 / 1.0174 | 0.02833 |
| informative-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | 0.694388 | fitted_frozen_q_devbatch_rep0 | -1.1e-16 | +0.01893 | 0.0091 / 0.0051 | 0.4701 / 0.9638 | 0.02678 |
| informative-feedback_dependent_floor_0.2 | fixed_LS | 0.697456 | known_q_ORACLE | -2.2e-16 | -0.00000 | 0.0000 / 0.0000 | 0.5076 / 0.6456 | 0.02401 |
| informative-feedback_dependent_floor_0.2 | fixed_LS | 0.697456 | zero_q | +0.0e+00 | -0.30746 | 0.3600 / 0.6400 | 1.0302 / 1.0949 | 0.03260 |
| informative-feedback_dependent_floor_0.2 | fixed_LS | 0.697456 | bounded_wrong_q | +0.0e+00 | +0.12500 | 0.0979 / 0.1241 | 0.6922 / 0.8375 | 0.02766 |
| informative-feedback_dependent_floor_0.2 | fixed_LS | 0.697456 | fitted_frozen_q_devbatch_rep0 | +1.1e-16 | +0.01827 | 0.0091 / 0.0041 | 0.5410 / 0.7129 | 0.02504 |
| weak-uniform_floor_0.5 | history_large_after_exception | 0.687508 | known_q_ORACLE | -2.2e-16 | -0.00000 | 0.0000 / 0.0000 | 0.3004 / 0.5434 | 0.02054 |
| weak-uniform_floor_0.5 | history_large_after_exception | 0.687508 | zero_q | -2.2e-16 | -0.29751 | 0.3600 / 0.6400 | 0.5200 / 0.8448 | 0.02612 |
| weak-uniform_floor_0.5 | history_large_after_exception | 0.687508 | bounded_wrong_q | +1.1e-16 | +0.00280 | 0.0949 / 0.1547 | 0.4093 / 0.6885 | 0.02343 |
| weak-uniform_floor_0.5 | history_large_after_exception | 0.687508 | fitted_frozen_q_devbatch_rep0 | +0.0e+00 | +0.02137 | 0.0000 / 0.0000 | 0.3597 / 0.5480 | 0.02130 |
| weak-uniform_floor_0.5 | prompt_only_large_if_hard | 0.694388 | known_q_ORACLE | -2.2e-16 | -0.00000 | 0.0000 / 0.0000 | 0.3136 / 0.5189 | 0.02040 |
| weak-uniform_floor_0.5 | prompt_only_large_if_hard | 0.694388 | zero_q | +1.1e-16 | -0.30439 | 0.3600 / 0.6400 | 0.4803 / 0.8537 | 0.02583 |
| weak-uniform_floor_0.5 | prompt_only_large_if_hard | 0.694388 | bounded_wrong_q | -1.1e-16 | +0.03500 | 0.0949 / 0.1547 | 0.4042 / 0.5784 | 0.02217 |
| weak-uniform_floor_0.5 | prompt_only_large_if_hard | 0.694388 | fitted_frozen_q_devbatch_rep0 | +1.1e-16 | +0.01160 | 0.0000 / 0.0000 | 0.3700 / 0.5744 | 0.02173 |
| weak-uniform_floor_0.5 | fixed_LS | 0.697456 | known_q_ORACLE | +1.1e-16 | +0.00000 | 0.0000 / 0.0000 | 0.3076 / 0.5163 | 0.02030 |
| weak-uniform_floor_0.5 | fixed_LS | 0.697456 | zero_q | +0.0e+00 | -0.30746 | 0.3600 / 0.6400 | 0.5403 / 0.8237 | 0.02611 |
| weak-uniform_floor_0.5 | fixed_LS | 0.697456 | bounded_wrong_q | +1.1e-16 | +0.12500 | 0.0949 / 0.1547 | 0.4425 / 0.6810 | 0.02370 |
| weak-uniform_floor_0.5 | fixed_LS | 0.697456 | fitted_frozen_q_devbatch_rep0 | +0.0e+00 | +0.01310 | 0.0000 / 0.0000 | 0.3276 / 0.5240 | 0.02063 |
| weak-feedback_dependent_floor_0.2 | history_large_after_exception | 0.687508 | known_q_ORACLE | +0.0e+00 | +0.00000 | 0.0000 / 0.0000 | 0.1688 / 0.3056 | 0.01540 |
| weak-feedback_dependent_floor_0.2 | history_large_after_exception | 0.687508 | zero_q | -2.2e-16 | -0.29751 | 0.3600 / 0.6400 | 0.2175 / 0.3719 | 0.01717 |
| weak-feedback_dependent_floor_0.2 | history_large_after_exception | 0.687508 | bounded_wrong_q | +0.0e+00 | +0.00280 | 0.0924 / 0.1506 | 0.1879 / 0.3320 | 0.01612 |
| weak-feedback_dependent_floor_0.2 | history_large_after_exception | 0.687508 | fitted_frozen_q_devbatch_rep0 | +0.0e+00 | +0.00720 | 0.0017 / 0.0024 | 0.1701 / 0.3069 | 0.01544 |
| weak-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | 0.694388 | known_q_ORACLE | -1.1e-16 | -0.00000 | 0.0000 / 0.0000 | 0.5626 / 0.9716 | 0.02770 |
| weak-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | 0.694388 | zero_q | +0.0e+00 | -0.30439 | 0.3600 / 0.6400 | 0.8610 / 1.7286 | 0.03598 |
| weak-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | 0.694388 | bounded_wrong_q | +0.0e+00 | +0.03500 | 0.0924 / 0.1506 | 0.6990 / 1.0740 | 0.02977 |
| weak-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | 0.694388 | fitted_frozen_q_devbatch_rep0 | -2.2e-16 | +0.00971 | 0.0017 / 0.0024 | 0.6240 / 1.2397 | 0.03053 |
| weak-feedback_dependent_floor_0.2 | fixed_LS | 0.697456 | known_q_ORACLE | +1.1e-16 | +0.00000 | 0.0000 / 0.0000 | 0.6042 / 0.9157 | 0.02757 |
| weak-feedback_dependent_floor_0.2 | fixed_LS | 0.697456 | zero_q | -2.2e-16 | -0.30746 | 0.3600 / 0.6400 | 1.1866 / 1.5750 | 0.03716 |
| weak-feedback_dependent_floor_0.2 | fixed_LS | 0.697456 | bounded_wrong_q | +0.0e+00 | +0.12500 | 0.0924 / 0.1506 | 0.7662 / 1.1354 | 0.03084 |
| weak-feedback_dependent_floor_0.2 | fixed_LS | 0.697456 | fitted_frozen_q_devbatch_rep0 | -2.2e-16 | +0.03502 | 0.0017 / 0.0121 | 0.9297 / 0.9640 | 0.03077 |
