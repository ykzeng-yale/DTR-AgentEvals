# DTR-REQ-018: source-bound design ledger for the archived fixed-benchmark primary contrast

Lead request: [`9e6c1ac`](../../../../docs/theory_feedback_20260926_req017_decision.md). This is a deterministic
retrospective diagnostic. No model, no Monte Carlo, no archive change.

- Built by `experiments/tools/req018_design_ledger.py`.
- Checked by `check_req018_ledger.py`. The checker uses the standard library and git, plus numpy for the stage-2
  redraw. It fails closed on:
  - any of the 18 sources that differs from its pinned frozen bytes or from its HEAD blob;
  - a config or code hash that differs from the one recorded in every frozen record;
  - duplicate JSON keys or a non-canonical layout;
  - a must-be-true fact that is not true;
  - point values other than the archived ones;
  - any CSV cell, row or column mismatch, including ragged rows;
  - any numeric or boolean JSON field it does not recompute;
  - an identification status other than the declared one;
  - any change to the remaining text, which is pinned by one hash.

  Without numpy it fails unless `--allow-skip-repro` is given, and then it lists the skipped fields.

## Target

The target is eq. (2) of [the fixed-benchmark bound note](../../../../docs/theory_branch_fixed_benchmark_bound.md),
adopted by the lead, with the weighting fixed in
[the 21 Sep weighting decision](../../../../docs/theory_feedback_20260921_weighting.md):

- θ = Σ_g E T_g / Σ_g E M_g
- ν_a = Σ_g E U_ga / Σ_g E D_ga
- Δ = θ − ν₁ + ν₀

The expectations run over repeated designs of the **330 fixed CONFIRM task blocks**. The tasks are fixed, not sampled
from a superpopulation.

The estimators are those of eq. (3):
- B̂ is the mean over sampled prefixes and replicate pairs;
- ν̂_a = U_a/D_a, pooled over all eligible prefixes.

The realized-frame mean μ_F = Σ_{i∈F} d_i / N is **secondary**. Under assumptions 2–3 of the note (the
fresh-execution assumptions), E(B̂ | F) = μ_F. Uniform sampling does not make B̂ unbiased for θ: in general
E(T/N) ≠ Σ E T_g / Σ E M_g.

The lead's 20 Sep reweighting derivative U_g is kept as a labelled column. It is an algebraic identity, and a6 calls
√(Σ U_g²) = 0.048386 an exploratory scale. It is not an eq. (2) influence function.

## Files

| File | Rows | Content |
|---|---|---|
| `design_ledger.json` | | See the list below. |
| `prefix_ledger.csv` | 564 | Each eligible first-failure prefix: task, benchmark, log run order and start time; a₀ block, realized a₀ and u₀; first-candidate visible pass and hidden success; stop reason; decisions 1–2 with design uniforms and propensities; log success; eq. (1) weights W_i1, W_i0 (both 0 on the 225 paths that switch arm at decision 2); sampled flag and π; replicates in run-index order; contrast D_p; invocation per arm. |
| `task_ledger.csv` | 330 | Every CONFIRM task, zeros kept: M_g, split by a₀ into two counts of at most 4 each; m_g; A_g; U_g1, D_g1, U_g0, D_g0; the lead derivative. |
| `continuation_ledger.csv` | 800 | Each branch continuation in plan order: arm, run, plan run order, seed, t=1 model-call seed (seed + 101), invocation, attempt, start time, success, restoration flags, and the numbers of durable pre-call rows written by the lost and by the recovery invocation. |

`design_ledger.json` contains:
- the target;
- the sources, with hashes, HEAD blobs and a working-tree check;
- a cross-check against `branch_evidence_table.json`;
- the reconciliation, including zero-arm counts;
- the point values;
- the three design stages and the git code binding;
- shared records and provenance;
- a 12-row identification map with an acceptance statement;
- the labelled lead derivative.

## Design facts

This README is a summary and is not itself checked. The `design_ledger.json` fields behind every number here are
recomputed by the checker, and the precommitment ordering and plan-invocation binding are checked as booleans.

**Stage 1: source blocks.**
- Per task, a₀ is a uniform arrangement of four 0s and four 1s. For two episodes of one task, P(same a₀) = 3/7 and
  P(both large) = 3/14.
- The realized a₀ equals the block in 2640/2640 episodes. a_t = 1{u_t < 0.5} holds with the design uniform in
  3662/3662 decisions, 1022 of them with t ≥ 1.
- A prefix is eligible iff the first candidate failed the frozen **visible** validation. 69 eligible prefixes had a
  hidden-correct first candidate.
- Frame by a₀: 332 small / 232 large. Sample: 111 / 89.
- One log invocation (`8d491c3`, git `c1de983`, code `b697d39`) ran CONFIRM interleaved with 1848 TRAIN episodes,
  19:04–21:54Z.
- The runner's foreign-server check was negative in all 5288 log and branch records. It is narrow: it looks only for
  another llama-server on a non-study port with a busy slot, once at each episode start.

**Stage 2: prefix sample.**
- SRSWOR of n = min(200, N) = 200 from N = 564, with π = 200/564 and π_ij = 200·199/(564·563), both conditional on
  the frame F.
- The draw is reproduced exactly from the seed. The seed is in `design.json`, which is unchanged since the freeze
  `cb9481d`. The order holds: design created (19:03:52Z) ≤ freeze commit (19:04:34Z) ≤ first log episode (19:04:44Z).
- The plan was drawn at the start of the first branch invocation, `0445024c72d2` (git `f3aa436`).
- `code_sha256` recomputed from git equals `b697d39` at the freeze, the log commit, the plan-invocation commit and the
  plan commit. The sampling and design blocks are byte-identical at all of these commits and at HEAD.

**Stage 3: continuations.**
- 2 continuations per arm at fork_t = 1.
- 800 distinct seeds, disjoint from every log and live seed and model-call seed.
- The replicate index pairs the arms by label only. Distinct seeds do not by themselves make executions independent.
- The 4 continuations of every prefix sit at adjacent plan run orders. For the 198 prefixes run in one invocation,
  they started a median of 9 s and at most 56 s apart. A time-local shock would reach all four.
- Replicate disagreement (32 of 400 arm pairs, 16 per arm) reflects sampling variation across distinct seeds, and
  possibly shared execution shocks. It is not evidence about seed determinism.
- The transcript hashes were recomputed 800/800, and the recheck's source binding matches the current records.
  `tool_result_reproduced` is a stored flag only.

**Provenance.**
- 135 continuations were retained from the lost invocation (run_order 0–136, without 134–135). 665 are from the
  recovery (134–799), which includes all 592 MBPP continuations.
- Prefixes by invocation: 33 lost-only, 165 recovery-only, 2 spanning (`humaneval/4#3` and `humaneval/46#3`).
- **Retention cutoff.**
  - The lost invocation reportedly ran all 800 continuations (operator report, protocol §11), but its episode records
    were written only on completion.
  - Only what had been written when the `ac3ca83` snapshot was captured survived. That is between the last snapshot
    decision row (01:27:04Z) and the commit (01:27:06Z): exactly the 135 retained continuations, with 243 decision
    rows.
  - 139 continuations had started before the capture.
  - 18 of them (run orders 121–138) started within the start-to-record bound of the capture. The bound is 117.8 s: the
    longest observed agent loop, 92.8 s, plus the 20 s hidden-test wall limit and the 5 s kill wait.
  - Retention selection can move B̂ by at most 18/400 = 0.045 if two conditions hold. First, no potential
    start-to-record time, under either outcome, exceeded this empirical bound; the code does not guarantee it. Second,
    start times do not depend on a continuation's own outcome.
  - Otherwise the records give only the trivial bound of 139/400.
- One same-seed repeat is visible at hash level (`46#3:small#1`, t=1 call). It agrees but is non-discriminating.

## Reconciliation and point values

- 330 tasks with 8 log episodes each.
- 564 eligible prefixes on 152 tasks; 200 sampled prefixes on 103 tasks; 800 continuations.
- Zero contributions are kept: 178 tasks have no eligible prefix and 49 have eligible but no sampled prefixes.
- Among the 152 eligible tasks: 64 have D_g1 = 0, 56 have D_g0 = 0, 20 have both zero, and 52 have both positive.
- The `branch_evidence_table.json` counts all agree.
- Point values: B = 0.12, ν̂₁ − ν̂₀ = 0.134654, Δ̂ = −0.014654.

## Identification (see `identification` in the JSON)

**Identified (mechanism):**
- the stage-1 arrangement and assignment;
- the stage-2 SRSWOR selection.

**Observed:**
- the replicate design;
- the restored transcript hashes;
- the branch/log shared-record map.

**Assumed:**

| Assumption | a6 status |
|---|---|
| Cross-task independence of complete source blocks | UNKNOWN |
| No execution shocks shared across prefixes | UNKNOWN |
| Replicate conditional independence and a selection-invariant law | UNKNOWN |
| Prefix selection independent of fresh noise | REPRODUCED draw; fresh-noise independence an assumption |
| Recovery-law invariance (the effect itself is not identified; see below) | UNAVAILABLE from committed records |
| Retention independent of the potential outcomes (lost and recovered) of every continuation started before the snapshot capture | — |
| Tool-result reproduction (stored flag) | — |

**Not identified:**
- the per-task block laws, even under assumptions 1–3. The exact variance of the task totals and the branch/log
  covariance are therefore not identified; between-task spread is conservative only;
- the recovery/invocation effect;
- seed-conditional determinism.

**Implied:** positive eq. (2) denominators (N = 564, D₁ = 570, D₀ = 574).

**No standard error, interval or bootstrap is asserted.**
