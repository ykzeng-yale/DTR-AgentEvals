# Correction: conditional-moment diagnosis, informative / .2 (ADDITIVE; lead 20e186a / bc8f057)

Historical `summary.json` unchanged. Per-fit records published: `per_fit_records.jsonl` (SHA-256 `cf7bbd9bf9031ade815dc70192055093965d431f30dd222841065a1ac1bbc9a1`, 1000 rows). z below uses a paired leave-one-repetition-out jackknife of BOTH the empirical error variance and the mean per-fit exact variance (exploratory normal reading).

| Policy | Estimand | Emp. var | Mean exact var | Difference (paired jk SE) | Ratio (paired jk SE) | Corrected z | Historical z (emp. SE only) | Skewness of estimand (mean over fits) | Variance CV across fits |
|---|---|---|---|---|---|---|---|---|---|
| history_large_after_exception | DR | 2.1779e-04 | 2.1251e-04 | +5.280e-06 (9.247e-06) | 1.0248 (0.0435) | +0.57 | +0.57 | -0.0389 | 0.003 |
| history_large_after_exception | DR − fresh | 3.9189e-04 | 3.8276e-04 | +9.128e-06 (1.632e-05) | 1.0238 (0.0426) | +0.56 | +0.56 | -0.0058 | 0.002 |
| prompt_only_large_if_hard | DR | 8.6882e-04 | 8.7919e-04 | -1.036e-05 (4.327e-05) | 0.9882 (0.0492) | -0.24 | -0.24 | +0.0044 | 0.175 |
| prompt_only_large_if_hard | DR − fresh | 1.1054e-03 | 1.0732e-03 | +3.220e-05 (5.280e-05) | 1.0300 (0.0492) | +0.61 | +0.61 | +0.0021 | 0.143 |
| fixed_LS | DR | 6.8880e-04 | 6.4933e-04 | +3.948e-05 (3.450e-05) | 1.0608 (0.0531) | +1.14 | +1.14 | -0.0732 | 0.083 |
| fixed_LS | DR − fresh | 9.1155e-04 | 8.3735e-04 | +7.420e-05 (4.420e-05) | 1.0886 (0.0528) | +1.68 | +1.68 | -0.0483 | 0.065 |

DR − fresh rows use V_DR + V_fresh and k3_DR − k3_fresh (fresh exact by enumeration, equal to the accepted fresh table); the historical table repeated the DR reference values on those rows.
