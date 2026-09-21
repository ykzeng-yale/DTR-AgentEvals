# Retrospective stage-2-Q intervention on the fitted OR (DTR-REQ-003; oracle diagnostic, not confirmation)

| Cell | Policy | Standard OR error (MCSE) / RMSE | Oracle-stage-2 OR error (MCSE) / RMSE | Paired diff (MCSE) |
|---|---|---|---|---|
| informative-uniform_floor_0.5 | history_large_after_exception | +0.00088 (0.00142) / 0.02005 | +0.00084 (0.00097) / 0.01374 | -0.00004 (0.00098) |
| informative-uniform_floor_0.5 | prompt_only_large_if_hard | +0.00001 (0.00143) / 0.02012 | +0.00005 (0.00105) / 0.01476 | +0.00005 (0.00106) |
| informative-uniform_floor_0.5 | fixed_LS | +0.00083 (0.00149) / 0.02097 | -0.00007 (0.00114) / 0.01603 | -0.00091 (0.00106) |
| informative-feedback_dependent_floor_0.2 | history_large_after_exception | +0.00102 (0.00102) / 0.01439 | +0.00111 (0.00074) / 0.01057 | +0.00009 (0.00066) |
| informative-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | +0.00823 (0.00168) / 0.02514 | +0.00088 (0.00108) / 0.01526 | -0.00735 (0.00121) |
| informative-feedback_dependent_floor_0.2 | fixed_LS | +0.00446 (0.00156) / 0.02247 | +0.00127 (0.00105) / 0.01492 | -0.00320 (0.00113) |
| weak-uniform_floor_0.5 | history_large_after_exception | +0.00111 (0.00150) / 0.02120 | -0.00029 (0.00090) / 0.01265 | -0.00140 (0.00123) |
| weak-uniform_floor_0.5 | prompt_only_large_if_hard | -0.00015 (0.00147) / 0.02069 | -0.00087 (0.00093) / 0.01315 | -0.00071 (0.00116) |
| weak-uniform_floor_0.5 | fixed_LS | -0.00062 (0.00136) / 0.01919 | -0.00134 (0.00086) / 0.01216 | -0.00072 (0.00107) |
| weak-feedback_dependent_floor_0.2 | history_large_after_exception | -0.00069 (0.00103) / 0.01453 | -0.00068 (0.00081) / 0.01146 | +0.00001 (0.00068) |
| weak-feedback_dependent_floor_0.2 | prompt_only_large_if_hard | -0.00081 (0.00173) / 0.02443 | -0.00019 (0.00117) / 0.01645 | +0.00062 (0.00130) |
| weak-feedback_dependent_floor_0.2 | fixed_LS | -0.00203 (0.00169) / 0.02395 | -0.00085 (0.00110) / 0.01557 | +0.00118 (0.00136) |
