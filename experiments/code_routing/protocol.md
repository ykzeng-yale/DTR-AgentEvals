# Code-routing study (ladder phases L1–L3 + branch audit): pre-registration

**Status: DRAFT — not frozen, no real model call made.** Only deterministic mock dry runs
(under gitignored `work/`) have exercised the pipeline. The protocol becomes binding when
`design.py` has been run and the commit containing `results/code_routing/design.json`,
`design.sha256` and `visible_tests.json` is pushed; its id is then recorded in §9.
Until then the theory agent (or the author) may request changes by editing §10.

This instantiates `docs/experiment_protocol.md` §4–§6 for a coding agent. It deviates from
that document in one declared way: instead of BrowserGym or mini-swe-agent (container
infrastructure not available on the experiment host), L1 uses two external, versioned,
independently scored function-synthesis benchmarks inside a macOS Seatbelt sandbox. The
agent loop, routing opportunities, logging contract and analyses follow the protocol.

## 1. Environment (one fixed kernel)

- **Tasks.** MBPP-sanitized (427 tasks; google-research `sanitized-mbpp.json`) and HumanEval
  (164; openai/human-eval `HumanEval.jsonl.gz`). URL, bytes and sha256 of both downloads are
  in the data manifest; the canonical 591-task list is pinned by sha256 in `design.json`.
  Licences: MBPP CC-BY-4.0, HumanEval MIT. Task data are not redistributed here.
- **Scoring.** Benchmark hidden tests, run once on the submitted program, success only if
  the process exits 0 **and** a per-run nonce sentinel printed after the tests is seen
  (defeats early `exit(0)`). Hidden tests never enter any prompt.
- **Sandbox.** `/usr/bin/sandbox-exec`: no network, no reads or writes under `$HOME` except
  the interpreter prefix, writes only in a private temp cwd, no exec of system binaries;
  RLIMIT_CPU/NPROC; process-group SIGKILL at 10 s. Containment is unit-tested on the host.
- **Tool.** "Run the visible tests." Visible tests are written **once per task** by the
  large model at temperature 0 in a context that never contains a candidate solution, then
  frozen (`visible_tests.json`, sha256 stamped on every episode). They are part of the
  environment, not of the treatment. They are imperfect by construction: a candidate can
  fail them and still be correct (false alarm) or pass them and be wrong.
- **Models.** small = Qwen2.5-3B-Instruct Q4_K_M, large = Qwen2.5-7B-Instruct Q4_K_M
  (Qwen licence / Apache-2.0 respectively; GGUF sha256 recorded in the run manifest), served
  by llama.cpp `llama-server`; T = 0.7, top-p 0.95, ≤1024 new tokens, per-call seed logged.
  "Small/large" are size descriptors, not a claim about which is better on these tasks.

## 2. Decision process

Horizon K = 3, absorbing success. t=0: always eligible, the chosen model writes a solution.
t=1 (t=2): eligible iff the first (second) tool validation failed; the chosen model repairs,
seeing the whole transcript (task, earlier attempts by either model, tool feedback). A
validated candidate is submitted immediately; after t=2 the latest candidate is submitted.
The action is binary — which model — and nothing else varies.

Pre-action state: t, benchmark indicator, failure class of the last validation
(`assertion` = only AssertionErrors; `exception` = anything else incl. crash/timeout/empty),
previous actions, fraction of visible asserts failing. Tabular key: (t, benchmark, failure
class, previous action).

Under absorption a t≥1 decision exists only after a failure, so "switch at fixed turn 1"
and "escalate after the first failure" coincide; this is stated rather than double counted.

## 3. Randomization and logging

Behaviour: P(large) = 0.5 at every eligible decision (floor 0.5 ≥ 0.2; largest possible
trajectory weight 8). All uniforms that decide actions are **pre-drawn in `design.json`**
and committed before execution; a_0 is permuted-block within task (4 small, 4 large;
marginal 0.5). Each decision record (state, P(large), draw source, action, transcript hash)
is appended and fsync'ed to `decisions.jsonl` **before** the model is invoked. No fallback
model exists: an HTTP/connection failure ends the episode with `error` set, it is kept in
the raw log, excluded from estimation and counted; >1% triggers a same-seed rerun of those
episodes only.

## 4. Task partitions and sample sizes

Seeded split by task, stratified by benchmark: 30 pilot / 231 train / 330 confirm; all runs
of a task stay together. Randomized log: 8 runs per train and confirm task (4,488 episodes).
Live executions: 6 policies × 330 confirm tasks × 2 runs (3,960 episodes). 330 confirm tasks
follows the protocol's planning example (half-width 0.05 at s_D² = 0.2 needs ≈308 tasks); the
realised precision is reported, not assumed. Uncertainty is conditional on this benchmark.

## 5. Policy class (frozen) and analyses

Targets: always_small (baseline), always_large, escalate_after_first_failure,
escalate_after_second_failure, large_then_small, class_tailored (large iff the last failure
was an assertion failure), soft_escalation δ=2 and δ=4 (odds shift toward large at failure
decisions only), and **learned** = greedy fitted-Q table with the optimal continuation,
fitted on TRAIN logs only and frozen (`learned_policy.json`, sha256) before any live run.

Outcomes: success; utility = success − Σ call penalties (0.01 small, 0.03 large — the
repository's unitless design convention, not dollars). Tokens and wall/server latency are
reported separately and never converted to money or energy.

- **A1 (L2, estimator calibration).** For each live policy: DR value from CONFIRM logs minus
  the live task-mean value, paired by task, with task-level SE; coverage of zero; Spearman
  agreement of the policy ranking; SE ratio OPE/live; model calls spent by each route.
- **A2 (L3, improvement).** Paired DR contrasts of every policy vs always_small on CONFIRM
  logs with 95% and Bonferroni-simultaneous intervals, and the same contrasts from live
  runs. "Improvement" is claimed only if the simultaneous interval excludes 0 **and** the
  live contrast agrees in sign. The Theorem 5 half-width is computed and reported even
  if vacuous.
- **A3 (diagnostics).** Stagewise ESS, maximum weights, zero-weight fraction, tasks with
  support, missing Q cells — reported for every policy before any value is interpreted.
- **A4 (branch audit, protocol §5).** 200 first-failure prefixes sampled with known
  probability from CONFIRM logs using the design's audit seed; transcript restored; small
  and large continuations × 2 fresh seeds each (the logged model's arm doubles as the
  same-model control). Target: mean continuation contrast over that prefix population,
  compared with the log-based stage-1 Q contrast. Restoration check: recomputed transcript
  hash equals the logged hash and the re-validated parent candidate reproduces the logged
  tool result.
- **Negative controls.** Naive "escalated vs not" comparison (association only) and IPW with
  a deliberately wrong constant propensity, to show what the design protects against.

Null, reversed and miscalibrated results are reported as such.

## 6. Pilot gate (pilot tasks only, before freeze)

The pilot runs BEFORE `design.py`, because the design hashes `config.json`. Pilot task ids are a
deterministic function of `design_seed` and `n_pilot_tasks`, neither of which the pilot may change, so
the pilot set is identical before and after the freeze. 4 runs × 30 pilot tasks. Checks: both models' first-call success within 15–85%; tokens and
seconds per episode → runtime projection; rate of t=1/t=2 eligibility; visible-test
false-alarm rate; zero sandbox escapes/flags needing review. The pilot may change only
runs per task, worker count, token cap and server flags. It may not change the policy
class, state definition or analyses. If the large model is not better than the small one
on pilot tasks the pair is still frozen and that fact is reported (size ≠ strength).

## 7. Host constraint

The harness refuses to start while another llama-server on the host is generating, because
a sibling pre-registered experiment on the same GPU measures latency; an override is
recorded in every manifest and episode (`contention_allowed`). Latency from any contended
run is labelled as such and excluded from latency claims.

## 8. What this study cannot show

One benchmark family and one model pair; function synthesis rather than long-horizon tool
use; K = 3; a tabular state. It does not validate unrestricted per-turn routing, estimated
propensities, or transport to other harnesses.

## 9. Freeze record

config.json sha256 — _pending_ · visible_tests.json sha256 — _pending_ · design.json sha256
— _pending_ · freeze commit — _pending_ · learned_policy.json sha256 — _pending_

## 10. Change requests before freeze

_(none yet)_
