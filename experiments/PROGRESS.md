# Progress log — experiments workstream

Pushed about every two hours while experiments run. Newest entry first. Interim entries for the log/live stages give
counts, error rates and timing only; outcomes by arm are not looked at before a stage is complete.

## 2026-09-19 16:20 EDT — randomized log 44% done, no errors

**Stage:** `log` (frozen design `cb9481d`). **1,974 of 4,488 episodes**, **0 infrastructure errors**, 0 episodes
owing a retry. 2.26 s per episode; ETA about 96 min (finish ≈ 17:55 EDT). 555 of 561 tasks touched so far;
train 804 / confirm 1,170 episodes.

**Operational only — no outcomes by arm are looked at before the stage completes.**

| quantity | value |
|---|---:|
| model calls / completion tokens | 2,661 / 225,049 |
| decisions per episode (1 / 2 / 3) | 1,590 / 81 / 303 → P(t=1 eligible) 0.195, P(t=2) 0.153 (pilot: 0.225 / 0.133) |
| truncated generations, validation timeouts, hidden-test timeouts, hack flags | 0, 0, 0, 0 |
| episodes begun under foreign GPU load / failed contention checks | 0 of 1,974 / 0 |
| mean call latency (uncontended, so interpretable) | small 4.26 s, large 8.90 s |
| assignment balance at t=0 (design check, not an outcome) | 0.508 large vs 0.500 by design |

**GPU sharing:** still sole occupant. The sibling ICLR project has committed only documents today and has not
started inference; it did finish downloading a coder model, so contention may begin at any time. Every episode
carries `foreign_gpu_load_at_start`, and the runner pauses before an episode while another server is generating.
(Note for anyone reading process lists: this project's two servers run the llama-server *binary* from the sibling's
scratchpad directory, so they look like sibling processes; ownership is by port — 8191 and 8193 are this project's.)

**Problems:** none. **Next:** on completion — `analysis.py --learn`, freeze and push `learned_policy.json`, then
the live stage (3,960 episodes, ≈2.5 h), calibration, branch audit (≈0.5 h).

**Overall submission readiness: about 50% (change: 0 percentage points; judgment range 45–60%).** Evidence
advanced: none that the rubric counts — the randomized log is *running*, and `docs/readiness.md` explicitly says not
to count an experiment's runtime fraction as its scientific completion fraction, so "Core simulations and real-agent
evidence" stays at 25% until confirmatory results exist and are inspected. Main remaining work: (1) complete the
randomized log, live-policy validation and branch audit, and report their outcomes including nulls; (2) integrate
validated results and limitations into the manuscript; (3) independent audit of the new experiment code, protocol
adherence and analysis. *(Scoring rubric added by the theory agent in `docs/readiness.md` at `8041a0e`; it asks for
checkpoints in GitHub issue #4, which this workstream cannot post to — no GitHub CLI or token on the experiment
host — so checkpoints are recorded here instead.)*

## 2026-09-19 15:10 EDT — design FROZEN (`cb9481d`); randomized log running

**Stage:** `log` — 4,488 pre-drawn episodes on 561 train + confirm tasks. 50 done at the time of writing, 0 errors,
2.8 s per episode, ETA about 3.4 h. No foreign GPU load observed.

**Second independent review** (27 agents) of the first round of fixes: 23 findings, **22 confirmed, none critical,
5 major**, all fixed before the freeze. The one that mattered scientifically: after certification, a visible check
whose *input* coincides with a hidden-test input is a hidden assert with its answer, and it was pasted into repair
prompts. The 7B writer has memorised benchmark examples — **514 of 2,977 written checks used a hidden input (43% of
HumanEval checks, 7% of MBPP)**. They are now removed at environment construction together with vacuous checks; the
protocol sentence "hidden tests never enter any prompt" was restated to say exactly where hidden tests are consulted
(once, to remove coinciding checks). Also fixed: a torn final line became fatal on the second resume; analysis could
freeze a learned policy on a log that still owed retries; episodes in flight at an abort were discarded.

**Environment as frozen:** 2,977 written checks → 38 vacuous, 514 hidden-input overlaps, 798 failed by the
reference → **1,627 certified checks**; 94 of 591 tasks fall back to a load check.

**Pilot gate (30 disjoint tasks × 4 runs; descriptive, enters no analysis):** first-call hidden-test success small
0.667 / large 0.762 (inside 15–85%; the 7B is the stronger model here); P(t=1 eligible) 0.225, P(t=2) 0.133;
visible-test false-alarm rate **0.074** (was 0.57 before certification), false-pass rate 0.097; 0 infrastructure
errors, 0 timeouts, 0 truncations. No configuration value was changed after the pilot.

**Next:** when the log completes — `analysis.py --learn` (freeze and push the learned routing table), then the live
stage (3,960 fresh target-policy episodes, ≈2.4 h), OPE-vs-live calibration, branch audit (≈0.5 h).

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
