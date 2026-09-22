# Block-1 pilot: cross-cohort diagnostic (32 completed episodes)

Descriptive synthesis of four verified worker analyses of **already-completed** episodes.
Every number here describes **what was executed** by a given harness configuration on a given
day; none of it measures model capability. No causal or efficacy claim is made or implied.
Design: 2 cohorts (`legacy`, `yaml-v1`) x 8 instances x 2 backends = 16 assignments, 32 episodes.
H=24 logical calls, temperature 0, 16384-token server context, 1536 max response tokens.

## Headline

| Quantity | legacy | yaml-v1 | all 32 |
|---|---:|---:|---:|
| Episodes | 16 | 16 | 32 |
| Empty `submission.diff`, all graded `operational_zero` | 16 | 16 | 32 |
| Logical model calls | 330 | 352 | 682 |
| Recorded commands | 326 | 348 | 674 |
| Format-error calls | 1 | 2 | 3 |
| Exits Submitted / LimitsExceeded / ContextWindowExceeded | 1 / 12 / 3 | 1 / 13 / 2 | 2 / 25 / 5 |
| Prompt tokens over answered calls | 1,249,810 | 1,417,803 | 2,667,613 |

Terminating constraint (32 episodes): `step_limit_H24` 25, `context_window` 5, `submitted` 2, `wall_clock` 0, `other` 0. Primary command family over 674 commands: inspect 443, python_eval 94, edit 67, vcs 56, submit 8, other 6, **run_tests 0**, create_file 0, install_env 0.

## Cross-cohort agreement (16 assignments)

- Byte-identical full command sequence **12/16**; the 4 divergent split into 2 length-only and 2 differing at a shared position. Identical command prefixes sum to 292.
- Same exit status 15/16; same terminating constraint 15/16; same repetition pattern 14/16; same any-edit flag 16/16.
- Answered prompt-token series: identical 12/16, pure truncation 2, differing at a shared index 2.

## Per-assignment table

Cells read legacy -> yaml-v1. `div` = 1-based recorded-command index of first divergence (`=` identical, `L` = agree to the shorter run's end).

| instance | backend | exit | terminating | repetition pattern | edit? | div |
|---|---|---|---|---|---|---|
| astropy-12907 | large | LE->LE | step->step | terminal_2cycle -> terminal_2cycle | n->n | = |
| matplotlib-13989 | large | LE->LE | step->step | terminal_1cycle -> terminal_1cycle | n->n | = |
| seaborn-3069 | large | CWEE->LE | ctx->step | no_repetition -> terminal_1cycle | n->n | 5L |
| requests-1142 | large | LE->LE | step->step | terminal_longer_cycle -> terminal_longer_cycle | n->n | 3 |
| pytest-10051 | large | LE->LE | step->step | terminal_1cycle -> terminal_1cycle | n->n | = |
| scikit-learn-10297 | large | LE->LE | step->step | terminal_2cycle -> terminal_2cycle | n->n | = |
| sphinx-10323 | large | LE->LE | step->step | terminal_longer_cycle -> terminal_longer_cycle | n->n | = |
| sympy-11618 | large | LE->LE | step->step | terminal_2cycle -> terminal_2cycle | Y->Y | 12 |
| astropy-12907 | small | Sub->Sub | sub->sub | single_call -> single_call | n->n | = |
| matplotlib-13989 | small | CWEE->CWEE | ctx->ctx | terminal_1cycle -> terminal_1cycle | n->n | = |
| seaborn-3069 | small | LE->LE | step->step | terminal_2cycle -> terminal_2cycle | n->n | = |
| requests-1142 | small | LE->LE | step->step | terminal_1cycle -> terminal_1cycle | Y->Y | = |
| pytest-10051 | small | LE->LE | step->step | terminal_2cycle -> terminal_2cycle | n->n | = |
| scikit-learn-10297 | small | LE->LE | step->step | terminal_longer_cycle -> terminal_longer_cycle | Y->Y | = |
| sphinx-10323 | small | LE->LE | step->step | terminal_1cycle -> terminal_1cycle | Y->Y | = |
| sympy-11618 | small | CWEE->CWEE | ctx->ctx | no_repetition -> terminal_1cycle | Y->Y | 12L |

## Repetition and verification

- 28/32 episodes end in a terminal command cycle; 24/32 contain a command repeated >= 5 times; highest single-command repeat 22. Of 446 repeat occurrences, 443 returned an observation identical to the *previous* occurrence and 437 identical to the *first*; the published headline uses the former, so the figure is baseline-dependent (defect REP-1).
- Of 24 headline claims re-derived here from the committed records: 22 reproduced, 1 reproduced but conflated, 1 not reproduced.
- **NOT REPRODUCED (ACT-2).** `action_profile.json` states in prose that no target-path candidate is derivable for *5 of 8* instances; the correct figure is **4 of 8**, consistent with that artifact's own `episodes_with_target_reference_defined = 16`. Prose only: every computed field is consistent with 4.
- **CONFLATED (BUD-1).** `budget_profile.json` reports 4/16 assignments without an identical prompt-token series; 2 of those are pure truncation, so only **2** genuinely differ at a shared index.
- **NOT SELF-CONTAINED (ACT-1).** The published command-family method omits a quote-masking step; applying the rules as published gives inspect 401 / create_file 42 instead of 443 / 0. The published counts are the correct ones; the gap is reproducibility from the stated method.

No existing file was modified. All 14 registered defects, the four source and four verifier artifacts pinned by sha256, and 8 open questions for the scientific lead are in `results/v2_agent/analysis_20260922/cross_cohort_diagnostic.json`. The four artifacts agree with each other and with the records on exit status, model-call count, recorded-command count and submission size for all 32 episodes (0 field disagreements).
