# Operations by contention status

Latency is interpretable only in the foreign_gpu_load=False rows. Timeouts are the one timing-dependent path into an outcome.

| stage   | foreign_gpu_load   |   episodes |   validation_timeouts |   hidden_test_timeouts |   truncated_generations |   median_wall_s_small |   median_wall_s_large |   error_attempts_in_stage |   itt_scored_in_stage |
|:--------|:-------------------|-----------:|----------------------:|-----------------------:|------------------------:|----------------------:|----------------------:|--------------------------:|----------------------:|
| pilot   | False              |        120 |                     0 |                      0 |                       0 |                 3.185 |                 6.426 |                         0 |                     0 |
| log     | False              |       4488 |                     0 |                      0 |                       0 |                 3.112 |                 6.341 |                         0 |                     0 |
| live    | False              |       3960 |                     1 |                      0 |                       3 |                 4.186 |                 7.699 |                         0 |                     0 |
| branch  | False              |        800 |                     0 |                      0 |                       0 |                 3.974 |                10.977 |                         0 |                     0 |
