# Deterministic replay integrity check (DTR-REQ-003; lead 75017a7)

Weak / .2 logger / fixed_LS fresh streams, seed 2026092103, n=250 x 16 (+ nested first 4). Sources unchanged since freeze: True. All regenerated values within 1e-12 of the committed records: **True**. Stream checks clean: True. Utility-identity violations: 0.

| Rep | Episodes / unique keys / unique streams | Max abs diff (4 values) | r16 error (exact SDs) | Easy utility total (expected; z) | Hard utility total (expected; z) | Task contributions + / − |
|---|---|---|---|---|---|---|
| 0 | 4000 / 4000 / 4000 | 0.0e+00 | -1.12 | 1628.92 (1643.15; -0.86) | 1130.31 (1146.67; -0.75) | 125 / 125 |
| 1 | 4000 / 4000 / 4000 | 0.0e+00 | -0.25 | 1634.53 (1643.15; -0.52) | 1148.44 (1146.67; +0.08) | 126 / 124 |
| 933 | 4000 / 4000 / 4000 | 0.0e+00 | +4.88 | 1693.17 (1643.15; +3.02) | 1230.47 (1146.67; +3.83) | 163 / 87 |

| Rep | Stratum | Success total (expected) | Cost total (expected) | Exit classes |
|---|---|---|---|---|
| 0 | easy | 1674 (1688.45) | 45.080 (45.294) | K_exhausted 184, false_pass 142, first_call_pass 1205, true_pass 469 |
| 0 | hard | 1194 (1210.50) | 63.690 (63.827) | K_exhausted 260, false_pass 546, first_call_pass 382, true_pass 812 |
| 1 | easy | 1680 (1688.45) | 45.470 (45.294) | K_exhausted 173, false_pass 147, first_call_pass 1205, true_pass 475 |
| 1 | hard | 1212 (1210.50) | 63.560 (63.827) | K_exhausted 260, false_pass 528, first_call_pass 391, true_pass 821 |
| 933 | easy | 1738 (1688.45) | 44.830 (45.294) | K_exhausted 149, false_pass 113, first_call_pass 1228, true_pass 510 |
| 933 | hard | 1295 (1210.50) | 64.530 (63.827) | K_exhausted 231, false_pass 474, first_call_pass 412, true_pass 883 |

Agreement supports integrity of these streams only; it is not evidence of nominal coverage. Identifier uniqueness does not prove stochastic independence. Repetition 933 remains in every published statistic.
