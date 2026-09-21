# DR/OR development batch paired on the dev_batch logs (DTR-REQ-003)

| Cell | Policy | Truth | IPW bias (MCSE) / RMSE | DR bias (MCSE) / RMSE | OR bias / RMSE | known-Q DR RMSE | DR - IPW (MCSE) |
|---|---|---|---|---|---|---|---|
| informative-uniform_floor_0.5 | history_large_after_exception | 0.73855 | +0.00088 (0.00183) / 0.02588 | +0.00083 (0.00142) / 0.02000 | +0.00088 / 0.02005 | 0.01931 | -0.00005 (0.00127) |
| informative-uniform_floor_0.5 | prompt_only_large_if_hard | 0.69439 | +0.00003 (0.00187) / 0.02633 | -0.00030 (0.00139) / 0.01955 | +0.00001 / 0.02012 | 0.01922 | -0.00033 (0.00118) |
| informative-uniform_floor_0.5 | fixed_LS | 0.69746 | +0.00268 (0.00191) / 0.02711 | +0.00082 (0.00148) / 0.02091 | +0.00083 / 0.02097 | 0.02085 | -0.00186 (0.00113) |
| informative-feedback_dependent_floor_0.2 | history_large_after_exception | 0.73855 | +0.00005 (0.00124) / 0.01746 | +0.00109 (0.00103) / 0.01459 | +0.00102 / 0.01439 | 0.01456 | +0.00104 (0.00061) |
| informative-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | 0.69439 | +0.00175 (0.00239) / 0.03374 | +0.00328 (0.00222) / 0.03152 | +0.00823 / 0.02514 | 0.02572 | +0.00153 (0.00182) |
| informative-feedback_dependent_floor_0.2 | fixed_LS | 0.69746 | +0.00232 (0.00224) / 0.03172 | -0.00035 (0.00178) / 0.02515 | +0.00446 / 0.02247 | 0.02396 | -0.00267 (0.00169) |
| weak-uniform_floor_0.5 | history_large_after_exception | 0.68751 | -0.00005 (0.00186) / 0.02622 | +0.00054 (0.00147) / 0.02075 | +0.00111 / 0.02120 | 0.01986 | +0.00060 (0.00116) |
| weak-uniform_floor_0.5 | prompt_only_large_if_hard | 0.69439 | -0.00145 (0.00180) / 0.02539 | -0.00091 (0.00143) / 0.02018 | -0.00015 / 0.02069 | 0.01975 | +0.00054 (0.00122) |
| weak-uniform_floor_0.5 | fixed_LS | 0.69746 | +0.00052 (0.00172) / 0.02430 | -0.00116 (0.00139) / 0.01968 | -0.00062 / 0.01919 | 0.01880 | -0.00168 (0.00117) |
| weak-feedback_dependent_floor_0.2 | history_large_after_exception | 0.68751 | -0.00079 (0.00114) / 0.01610 | -0.00069 (0.00103) / 0.01452 | -0.00069 / 0.01453 | 0.01450 | +0.00011 (0.00053) |
| weak-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | 0.69439 | -0.00220 (0.00235) / 0.03319 | -0.00211 (0.00199) / 0.02811 | -0.00081 / 0.02443 | 0.02658 | +0.00010 (0.00169) |
| weak-feedback_dependent_floor_0.2 | fixed_LS | 0.69746 | -0.00086 (0.00263) / 0.03710 | +0.00006 (0.00218) / 0.03080 | -0.00203 / 0.02395 | 0.02584 | +0.00092 (0.00196) |
