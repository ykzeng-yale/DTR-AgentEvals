# REQ029W terminal control decision and retrospective diagnosis

Run `mpe029w-matplotlib20826-a` is terminal. The frozen control gate FAILED for the reference arm. No model attempt is released, no environment/package changes or rerun are authorized, and the archived gate is not rescored. This is ONE development task with 674 declared checks, not 674 tasks or model successes.

| Observation | Unchanged | Known reference |
|---|---:|---:|
| Declared target | FAILED | PASSED |
| Declared regression checks | 673 PASSED | 673 PASSED |
| Entire selected pytest file | 7 failed / 675 passed / 63 skipped | 6 failed / 676 passed / 63 skipped |
| Process exit | 1 | 1 |
| Frozen control accepted | yes | no |

Independent raw-parser replay, strict declared outcome, exact prepared-source/reference bytes, 163 source/input pins and cleanup bindings matched both receipts. All 194 runtime archive members were hash-verified. OS inspection found driver79235 and guardians79406/82246 absent; Docker inventory was empty. Evidence is results/local_req029/matplotlib_controls_review_20260927. Both test outputs contain valid markers and complete declared statuses. Neither arm timed out or reported an infrastructure exception. The offline install omission and altered archive ownership remain disclosed; this is not an untouched stock harness reproduction.

## Diagnosis owned by the lead

The only parsed declared-status change is test_shared_axes_clear[png], FAILED to PASSED. Every parsed extra-status entry is identical across arms: two passed tests, six failed tests, and two aggregated skip entries. The parser's `[10]` and `[53]` entries encode aggregated skip summaries, NOT two individual skipped tests; raw pytest reports 63 skips. Four extra failures show pandas multidimensional-indexing ValueError; two PDF image comparisons show RMS142.950 and155.125 in both arms. These facts support pre-existing environment/whole-file incompatibilities rather than an observed reference regression. They do not establish the precise dependency versions or prove absence of every possible interaction.

The source of the failed control gate is my additional reference-returncode-zero requirement (matplotlib_eval_grade.py), not failure of the fixed declared-test rule. The frozen baseline permitted extra failures through exit1; the reference required exit0 despite the selected full file containing extras. The pinned upstream grading.py get_eval_tests_report/get_eval_report operates on FAIL_TO_PASS/PASS_TO_PASS and parsed logs, without that returncode-zero condition. Our stricter declared rule additionally rejects missing/skipped/error declared statuses. Retrospective replay therefore reports a passing declared endpoint for the reference while faithfully retaining `control_accepted=false` under the released gate. These are separate quantities.

Alternative explanations considered: wrong task/reference/source/reset (binding checks oppose); parser falsely passing the target (raw PASSED target and independent replay oppose); reference-induced extra regressions (identical extra map/opposing same baseline traces); output loss/timeout (complete markers/statuses and bounded-process receipts oppose). Evidence that would change this diagnosis includes unequal exact extra failure traces/statuses, patch/source mismatch, missing declared tests, or a source-derived grading requirement for whole-file exit0. No model ability or routing conclusion follows.

## Next bounded work

Keep model execution held. Reconcile the positive-control admission rule against the already fixed declared endpoint in a separate, explicitly prospective design/source review. Preserve the old failed gate and show both original and proposed diagnostic results; do not change the primary scientific endpoint or relabel this run as a prospectively passing control. Test any proposed rule against missing statuses, new extra failures, infrastructure markers, partial logs and patch/source mismatches before a new exact approval. Do not repair dependencies, drop declared tests, change task order or rerun merely to obtain exit0. Retrospective diagnostics are sufficient for this reconciliation; no new compute is requested here.

The two disabled Matplotlib manifest-builder files remain uncommitted preparation and do not authorize dispatch. The continuous /goal remains paused as requested; this monitor has reviewed the terminal result and retains the two-hour cadence for the concrete unresolved design review.

Readiness55%, change0points, range45–65%. Remaining: competent fixed-target comparison/valid inference, empirical/manuscript synthesis, independent reproducibility and author-approved package.
