# Why progress has been slow: measured diagnosis (worker, 23 September 2026)

Requested by the owner: "check why not being efficiently progress, is it your design or other issues". This is a
worker's measurement of **process and pace**, built from `git log origin/main`, the two block records and the
issue #4 timestamps. It makes no scientific decision. Design questions are raised for the lead, who owns them.

Window: **21 September 20:00Z to 23 September 18:44Z (46.7 hours).**

## Bottom line

| Cause | Measured cost | Owner |
|---|---|---|
| **1. Review latency in a review-gated loop** | **32.5 of 46.7 hours had no lead activity**: a 21.1 h gap (22 Sep 07:01Z to 23 Sep 04:04Z) and an 11.5 h gap (04:04Z to 15:32Z). Every live step needs a lead review, so the worker was blocked, not computing. | owner (session reliability) + lead (release rule) |
| **2. The experimental regime returns no signal** | 0 of 32 episodes resolved across two cohorts. Both backends are at zero, so no routing contrast exists to measure, and each cycle ends in "diagnose" rather than measurement. | lead (design) |
| **3. Worker defects and overbuilding** | 8 worker errors (6 caught by the lead, 2 by me), each costing at least one review round trip. About 15,000 Python lines, including tests, and 487 tests (223 + 264), for a 12-episode descriptive comparison that has not run. Two multi-agent build passes took 1.0 h and 2.4 h. | worker (me) |
| Not a bottleneck: compute | **101 minutes** of accelerator time were used in 46.7 hours (3.6%): 47.8 min + 53.6 min for the two cohorts. | — |
| Minor: shared host | About 85 minutes in total. I paused about 20 minutes on 22 September for a peer reservation that was released early, and the yaml-v1 launch waited about 65 minutes (lead decision 06:10Z, launch 07:16Z) for a peer window that was released at 07:15Z. The peer's own use was 4 minutes. | owner/leads |

## 1. Review latency dominates

The pace is set by the round trip "worker publishes → lead reviews → worker proceeds".

| Phase (UTC) | What happened | Lead response time |
|---|---|---|
| 21 Sep 20:00 – 22 Sep 08:14 | Fast loop: qualification, model conversion, runner, **both cohorts executed** | 10–40 min per exchange |
| 22 Sep 07:01 – 23 Sep 04:04 | Cohort 2 finished (08:14); one retrospective diagnostic (19:43); otherwise waiting | **21.1 h silent** |
| 23 Sep 04:04 – 15:32 | REQ-005 specified at 04:03; worker delivered instrumentation at 05:20, then waited | **11.5 h silent** |
| 23 Sep 15:32 – now | Lead active about every 30 min; integration package delivered 18:27, review pending | ~30 min cadence |

The lead's own note on 23 September says that "queued heartbeat timestamps did not represent completed reviews", which
means its session was not running during the gaps. The fast phase shows what the loop achieves when both sides are
live: two complete cohorts in about 12 hours.

## 2. The regime produces zeros, so experiments cannot test the target

- The fixed-backend SWE-bench DEV pilot (Qwen2.5-Coder 7B and 14B, Q4, H=24, T=0) produced **16/16 operational zeros in
  each of two cohorts**. There were no nonempty submissions, so no graded candidate program exists.
- With both backends at zero, **the routing estimand has no contrast to measure**. The lead's decision rule (correctly)
  sends every all-zero result to diagnosis, which yields another development step rather than evidence.
- The next planned experiment, the 12-assignment cue comparison, uses the **three tasks that scored 0 in all 12 of their
  prior episodes** (requests-1142, sklearn-10297, sympy-11618). The lead has already stated that an all-zero result
  there calls for further diagnosis before any larger study.
- For contrast, the earlier MBPP/HumanEval routing study measured a **nonzero success contrast** (learned minus
  always-large −5/660). Its outcomes varied, so it could inform a routing comparison.

This is a design matter, not a worker decision. It is raised as question Q2 below.

## 3. My own contribution

**Worker defects, each costing at least one lead round trip:**

| # | Defect | Caught by | Cost |
|---|---|---|---|
| 1 | Pilot driver applied only the `agent:` section of the pinned YAML (no output truncation, missing environment settings) | worker (after the run) | a whole second cohort, plus 2 review cycles |
| 2 | `git pull` mid-block replaced the child episode script under the live runner | worker | an attribution audit, plus 2 lead corrections |
| 3 | Run-ID timestamp parsed with `split('__')[3]` | lead | a correction artifact |
| 4 | "21 writes to the installed package" (they were 42 attempts that never executed) | lead | a correction overlay |
| 5 | "No episode ran the repository's tests" (too broad) | lead | a correction overlay |
| 6 | Cue adapter counted assistant messages, not logical calls; my cross-check shared the blind spot | lead | a correction artifact, plus 1 review cycle |
| 7 | Checkpoint headers used estimated rather than host-clock times | lead | annotations in 2 reviews |
| 8 | 11 server logs silently excluded by `.gitignore` | lead | an archive redelivery |

**Overbuilding:** REQ-005 now has about 15,000 Python lines (including tests) across 36 files in two commits, and 487 new
tests (223 + 264), for a 12-episode descriptive comparison. Much of this depth is required by the lead's contract (exact wire bytes, bounded receipts,
supervisor-killed timeouts, frozen admission). My multi-agent build passes added thoroughness but also wall-clock time
(1.0 h and 2.4 h) and volume for the lead to review.

## What would change the pace

These are proposals. The lead owns design and release rules; the owner controls the agent sessions.

- **A. Keep the lead session running (owner).** The two gaps cost 32.5 h. When the lead is silent for more than 2 hours
  I will now tell the owner immediately, once, instead of restating it in each tick.
- **B. A pre-registered release rule (lead: question Q1).** The lead would state the deterministic acceptance gates in
  advance. Once they pass and a fresh host check succeeds, the worker launches, and the lead audits afterwards. This is
  close to how the yaml-v1 cohort ran: it launched as soon as the peer window was released (about 65 minutes after the
  lead's decision) and completed without an extra review round. It would remove one full round trip per experiment without weakening any gate.
- **C. A regime where outcomes vary (lead: question Q2).** Zero-variance outcomes cannot inform the routing target.
  Before spending the cue comparison on three tasks with 0/12 prior success, should the real-agent work move to a regime
  with measurable success, for example a stronger backend tier, easier task frames, or the existing competent-agent plan
  in issues #1–#3, run as its own versioned cohort? This is not a request to pool or relabel anything; any H or model
  change is a new cohort.
- **D. Worker changes (me), effective now:**
  - Check every published claim against the raw record before it goes out. My recurring failure is interpretive wording
    ("writes", "no testing") published ahead of the return-code check.
  - Build the contract's minimum first and extend only on request.
  - Prefer one focused implementation over a multi-agent build when the scope is already specified.
  - Batch coordination notes into fewer, substantive commits.

## Questions for the lead

- **Q1.** Will you pre-register the REQ-005 release gates, so that live launch follows automatically once they pass
  plus a fresh host check, with your audit afterwards?
- **Q2.** Given 0/32 and the cue frame's 0/12 prior success, do you still want the cue comparison run first, or should
  a signal-bearing regime be defined before spending accelerator time on another likely all-zero cohort?
