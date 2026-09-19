# Pilot gate

episodes 120, tasks 30, infrastructure errors 0

| first model | n | validated at t=0 | first candidate passes HIDDEN tests | final success | mean completion tokens at t=0 |
|---|---:|---:|---:|---:|---:|
| small | 57 | 0.702 | 0.667 | 0.842 | 73 |
| large | 63 | 0.841 | 0.762 | 0.810 | 67 |

decisions per episode: {1: 93, 2: 11, 3: 16}  ->  P(t=1 eligible) = 0.225, P(t=2 eligible) = 0.133
visible-test FALSE ALARM rate, P(first candidate hidden-correct | failed validation) = 0.074 (n=27)
visible-test FALSE PASS rate, P(hidden-wrong | validated at t=0) = 0.097 (n=93)
failure classes at t>=1: {'assertion': 38, 'exception': 5}
truncated generations (finish=length): 0.000; validation timeouts: 0; hidden-test timeouts: 0; episodes with hack flags: 0
episodes that began under foreign GPU load: 0 of 120

throughput: 1.36 calls/episode, 104 completion tokens/episode, 8.7 agent-seconds/episode (sum over 4 workers)
projected wall-clock at this rate: randomized log 4488 episodes = 2.7 h; live 3960 episodes = 2.4 h; branch 800 continuations = 0.5 h

## Gate

first-call hidden-test success within 15-85% for both models: True  (small 0.667, large 0.762)
large better than small on first call: True (size is a descriptor, not a claim; the pair is frozen either way)
