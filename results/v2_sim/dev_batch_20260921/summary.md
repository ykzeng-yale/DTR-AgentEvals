# Development batch: IPW versus fresh, K=2 crossing cells (DTR-REQ-003 P0)

Root seed 2026092101; [200] complete repetitions per cell; manifest `3c35cdc461ca`. Wiring check only: no coverage, adaptation or efficiency claim. Truth and exact SDs are the accepted exact artifacts.

| Cell | Policy | Truth | IPW bias (MCSE) | IPW RMSE | IPW SD emp / exact | Fresh bias (MCSE) | Fresh SD emp / exact | IPW - fresh (MCSE) |
|---|---|---|---|---|---|---|---|---|
| informative-uniform_floor_0.5 | history_large_after_exception | 0.73855 | +0.00088 (0.00183) | 0.02588 | 0.02593 / 0.02646 | +0.00014 (0.00092) | 0.01297 / 0.01305 | +0.00073 (0.00202) |
| informative-uniform_floor_0.5 | prompt_only_large_if_hard | 0.69439 | +0.00003 (0.00187) | 0.02633 | 0.02640 / 0.02550 | -0.00119 (0.00103) | 0.01454 / 0.01393 | +0.00122 (0.00201) |
| informative-uniform_floor_0.5 | fixed_LS | 0.69746 | +0.00268 (0.00191) | 0.02711 | 0.02704 / 0.02572 | -0.00138 (0.00091) | 0.01284 / 0.01371 | +0.00406 (0.00209) |
| informative-feedback_dependent_floor_0.2 | history_large_after_exception | 0.73855 | +0.00005 (0.00124) | 0.01746 | 0.01750 / 0.01687 | -0.00033 (0.00093) | 0.01313 / 0.01305 | +0.00038 (0.00150) |
| informative-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | 0.69439 | +0.00175 (0.00239) | 0.03374 | 0.03378 / 0.03179 | +0.00064 (0.00100) | 0.01413 / 0.01393 | +0.00111 (0.00256) |
| informative-feedback_dependent_floor_0.2 | fixed_LS | 0.69746 | +0.00232 (0.00224) | 0.03172 | 0.03171 / 0.03211 | -0.00006 (0.00088) | 0.01243 / 0.01371 | +0.00238 (0.00238) |
| weak-uniform_floor_0.5 | history_large_after_exception | 0.68751 | -0.00005 (0.00186) | 0.02622 | 0.02629 / 0.02579 | +0.00077 (0.00088) | 0.01250 / 0.01379 | -0.00082 (0.00214) |
| weak-uniform_floor_0.5 | prompt_only_large_if_hard | 0.69439 | -0.00145 (0.00180) | 0.02539 | 0.02541 / 0.02550 | -0.00106 (0.00102) | 0.01448 / 0.01393 | -0.00039 (0.00206) |
| weak-uniform_floor_0.5 | fixed_LS | 0.69746 | +0.00052 (0.00172) | 0.02430 | 0.02435 / 0.02572 | +0.00181 (0.00096) | 0.01352 / 0.01371 | -0.00129 (0.00195) |
| weak-feedback_dependent_floor_0.2 | history_large_after_exception | 0.68751 | -0.00079 (0.00114) | 0.01610 | 0.01612 / 0.01707 | +0.00125 (0.00101) | 0.01432 / 0.01379 | -0.00204 (0.00159) |
| weak-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | 0.69439 | -0.00220 (0.00235) | 0.03319 | 0.03320 / 0.03535 | -0.00063 (0.00102) | 0.01449 / 0.01393 | -0.00158 (0.00260) |
| weak-feedback_dependent_floor_0.2 | fixed_LS | 0.69746 | -0.00086 (0.00263) | 0.03710 | 0.03718 / 0.03642 | -0.00034 (0.00096) | 0.01364 / 0.01371 | -0.00052 (0.00281) |
