# Progress log — experiments workstream

Pushed about every two hours while experiments run. Newest entry first. Interim entries for the log/live stages give
counts, error rates and timing only; outcomes by arm are not looked at before a stage is complete.

## 2026-09-19 14:45 EDT — real execution started; harness hardened before any freeze

**Stage:** environment construction (visible tests), second pass running on the GPU; pilot next. No design task has
been touched by a model. Nothing is frozen yet.

**GPU sharing.** The sibling tau2 stream finished overnight; the author asked for both projects to co-run. Both
llama-servers are up (3B 116 tok/s, 7B 67 tok/s over 4 slots; 9.4 GB resident). No foreign GPU load has been
observed so far today. Correction recorded in `experiments/README.md`: the claim that tau2 "uses latency as an
outcome tier" was wrong (its tiers are success / completion tokens / tool calls).

**Independent pre-freeze review** (48 agents, six lenses, every finding attacked by a second agent): 41 findings,
**38 confirmed, 3 refuted, none critical, 13 major**. Fixed before any episode:
- an errored episode was marked done forever, the promised same-seed rerun had no code path, and the analysis then
  crashed on unequal runs per task → retry with the same pre-drawn randomization (≤3 attempts), last good attempt
  wins, exhausted episodes scored intention-to-treat; both paths exercised with injected failures;
- pre-registered analyses that did not exist: live contrasts vs always-small (the A2 decision rule) and both
  negative controls → implemented; Bonferroni critical value now exact;
- downstream stages did not require a complete upstream log; the branch-audit sample depended on whatever the log
  held at launch → completeness gates; branch plan drawn once from the complete log and frozen;
- a repair reply quoting the old code first re-submitted the OLD code; ```` ```Python ```` and truncated replies were
  mis-parsed → last defining block, case-insensitive, unclosed fences handled;
- HumanEval helpers that exist only in the prompt were missing at verification → shared prelude; **all 591
  reference solutions now pass the hidden-test verifier (591/591)**;
- per-slot context was 4,096 tokens and a third-round transcript can reach ~4.7k → 8,192 per slot;
- single-writer stage lock, torn-line tolerance, task-file sha check (file now pinned locally), per-run sandbox
  read isolation, wall-clock limit 2× the CPU limit, decision log carries draw / eligibility / attempt.

**Finding that changed the environment.** The first visible-test file (7B, T=0) gave zero usable asserts for 111 of
591 tasks (pytest-style wrappers) and, after fixing that, **rejected the correct reference solution in 336 of 588
tasks (57%)**. Visible checks are now certified against the reference (inputs from the model, expected values from
the reference; hidden tests untouched). The unvalidated file was never frozen or used.

**Second review** of these fixes is running now; the pilot waits for the regenerated tests, the freeze waits for
both the review and the pilot gate.

**Problems:** none blocking. A one-day delay was self-inflicted (see the correction above).
