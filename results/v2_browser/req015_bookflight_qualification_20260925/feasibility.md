# DTR-REQ-015 feasibility verdict (DEVELOPMENT, no model): QUALIFIED

No-model qualification of `browsergym/miniwob.book-flight` (BrowserGym MiniWoB `book-flight`) under manifest `configs/v2_req015_miniwob_bookflight_20260925.json` (sha256 `90979f0fcfade8cc`, copied as `manifest.json`).

Failed checks: none

| Check | Result |
|---|---|
| sources_pinned | True |
| runtime_pinned | True |
| reset_reproducible | True |
| feedback_dependent_decisions | True |
| positive_full_success | True |
| negative_fails_predicate | True |
| noop_fails_predicate | True |
| browser_isolation | True |
| no_harness_error | True |
| resources_within_caps | True |

| Trace | Seed | Actions | Verified feedback-dependent decisions | DONE | RAW reward | Full success |
|---|---:|---:|---:|---|---:|---|
| reset_repeat_a | 0 | 0 | 0 | None | None | False |
| reset_repeat_b | 0 | 0 | 0 | None | None | False |
| reset_other_seed | 1 | 0 | 0 | None | None | False |
| primary_positive | 0 | 8 | 4 | True | 1 | True |
| negative | 0 | 8 | 4 | True | -1 | False |
| noop | 0 | 5 | 0 | False | 0 | False |
| positive_seed1 | 1 | 10 | 6 | True | 1 | True |
| positive_seed2 | 2 | 8 | 4 | True | 1 | True |
| positive_seed3 | 3 | 10 | 6 | True | 1 | True |
| positive_seed4 | 4 | 9 | 5 | True | 1 | True |

Wall 52.4 s (cap 1800 s); peak process-tree RSS 1.02 GiB (cap 8 GiB); raw artifacts 1.5 MiB (cap 2 GiB).

Scope: a scripted, no-model DEVELOPMENT mechanism check of one pinned task. It is not a model result, not a routing result and not a repository-repair claim; the fixed primary target is unchanged.
