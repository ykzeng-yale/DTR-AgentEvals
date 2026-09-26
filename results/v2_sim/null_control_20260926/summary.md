# DTR-REQ-022 null-control DEVELOPMENT cell: K2-no_crossing-informative-feedback_dependent_floor_0.2

Root seed 2026092622; 200 of 200 repetitions complete; manifest `d8ec4c72287c`. Wiring check only: no coverage, adaptation, optimality or real-agent claim. Exact truths and SDs are the accepted exact computations.

| Policy | Class | Truth | IPW bias (MCSE) | IPW RMSE | IPW SD emp / exact | Fresh bias (MCSE) | Fresh SD emp / exact | max weight |
|---|---|---|---|---|---|---|---|---|
| fixed_LL | fixed | 0.72275 | -0.00445 (0.00264) | 0.03752 | 0.03735 / 0.04075 | +0.00076 (0.00087) | 0.01230 / 0.01320 | 25.00 |
| fixed_LS | fixed | 0.68781 | -0.00199 (0.00216) | 0.03054 | 0.03055 / 0.03168 | +0.00133 (0.00098) | 0.01382 / 0.01372 | 25.00 |
| fixed_SL | fixed | 0.65416 | +0.00381 (0.00260) | 0.03682 | 0.03671 / 0.03610 | +0.00009 (0.00100) | 0.01421 / 0.01403 | 25.00 |
| fixed_SS | fixed | 0.58944 | +0.00181 (0.00203) | 0.02863 | 0.02864 / 0.02933 | +0.00005 (0.00104) | 0.01475 / 0.01435 | 25.00 |
| history_S_or_exception | history | 0.71228 | -0.00170 (0.00213) | 0.03016 | 0.03018 / 0.03085 | +0.00027 (0.00089) | 0.01259 / 0.01355 | 25.00 |
| history_large_after_exception | history | 0.69633 | +0.00209 (0.00120) | 0.01699 | 0.01691 / 0.01711 | -0.00077 (0.00095) | 0.01349 / 0.01372 | 1.56 |
| prompt_only_large_if_hard | prompt_only | 0.68841 | -0.00134 (0.00231) | 0.03267 | 0.03273 / 0.03340 | -0.00050 (0.00104) | 0.01470 / 0.01413 | 25.00 |

Flags: none
