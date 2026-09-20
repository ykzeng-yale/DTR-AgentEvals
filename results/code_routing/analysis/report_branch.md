# Code-routing: branch audit (restored first-failure prefixes, CONFIRM tasks)

branch continuations scored intention-to-treat (success 0) after exhausting retries: 0

| quantity | value |
|---|---|
| prefixes with both arms / tasks (prefixes dropped for a missing arm: 0) | 200 / 103 |
| restoration: transcript hash matches | 800 / 800 |
| restoration: tool result reproduced | 800 / 800 |
| same-state same-model disagreement between two fresh continuations | 0.080 |
| branch contrast, stay-large minus stay-small (success) | 0.1200 (task-cluster SE 0.0320) |
| same contrast from the randomized log (Hajek IPW, task bootstrap SE) | 0.1347 (SE 0.0474) |
| branch minus log | -0.0147 (SE 0.0572), 95% interval [-0.1268, 0.0975] |

Target: mean continuation effect over the first-failure prefix population reached under the randomized logger. It is NOT the value of any policy that changes how prefixes are reached (protocol section 5).
