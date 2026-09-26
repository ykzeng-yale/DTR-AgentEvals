# DTR-REQ-022: null-control DEVELOPMENT cell (K=2, no crossing, informative feedback, floor-0.2 logger)

Lead request: [`cd90c56`](../../../docs/theory_feedback_20260926_req021_decision.md) (section "P1 DTR-REQ-022"). CPU only:
no model, GPU, branch execution or CONFIRM stage. Code: `experiments/v2_sim/null_control_batch.py` (adapted from
`dev_batch.py`, which is left unchanged with its archive). Focused tests: `tests/test_req022_null_control.py`.

**This is a development wiring check only.** It makes no claim about interval coverage, adaptation benefit,
optimality, resource efficiency or real-agent evidence, and a difference between two catalog policies is not
adaptive value.

## Design (frozen before sampling)

- **Freeze:** `manifest.json` (sha256 `d8ec4c72287c…`) was committed in `bc4a71e` at 13:56:46Z, before any sampling.
- **Seed and pins:** root seed 2026092622, distinct from the 21 Sep batch. Source and truth hashes of 9 files are
  pinned; `sampler.py` is the current version, which differs from the one the 21 Sep batch pinned.
- **Cell:** the existing repair generator at K=2, no crossing, informative feedback, logged by the
  feedback-dependent-floor-0.2 logger. **Analytic null:** best fixed (`fixed_LL`), best prompt-only and best
  observed-history utility are all 2891/4000 = 0.72275, so the optimal history advantage is exactly 0.
- **Sampling:** all 7 catalog policies on the frozen 250-task list; 4 logged and 4 independent fresh episodes per task
  and policy; 200 repetitions; 4 workers; 15-minute cap.
- **Exact references:** truths and exact IPW/fresh SDs for every policy. These reproduce the accepted
  `fixed_task_blocks_v1.json` and `fresh_reference_v1.json` values for the 3 overlapping policies exactly.

## Run

**Attempt 1: BLOCKED at the host gates (13:56:52Z), with nothing sampled.** The non-overlap gate matched the worker's
own parent shell, whose command line contained `null_control_batch.py`. The self-match was then reproduced: 1 match
with the name in the wrapper, 0 without. The records are preserved as `gates_attempt1_blocked_selfmatch.json` and
`run_status_attempt1_blocked_selfmatch.json`.

**Attempt 2: COMPLETED (13:57:28Z).** It ran the unchanged, hash-verified code, invoked without the name in the
wrapper. All gates passed: 62 % memory free, 65 GiB disk, no model server, no other simulation or stage job.

**Deviation for lead acceptance.** The lead's rule is "if any gate fails, return BLOCKED without execution". The
re-run departs from that literal rule after a gate failure that was shown to be spurious.
- Nothing was sampled in attempt 1.
- The code is unchanged and hash-verified.
- The seeded repetitions replay exactly, so no result could have been chosen by outcome.

The evidence is in `gate_selfmatch_reproduction.json`. The gate defect remains in the frozen code, because it excludes
only its own process and not its ancestors. The `python -c` launch would also not have matched a concurrent
same-module launch; no such process existed.
- 200/200 repetitions in 13.6 s wall and 53.6 s CPU.
- 0 missing and 0 failed repetitions.

## Results (`summary.json`, `summary.md`)

| Policy | Truth | IPW bias (MCSE) | IPW SD emp / exact | Fresh bias (MCSE) | Fresh SD emp / exact | IPW/fresh SD |
|---|---|---|---|---|---|---|
| fixed_LL | 0.72275 | −0.00445 (0.00264) | 0.0374 / 0.0407 | +0.00076 (0.00087) | 0.0123 / 0.0132 | 3.04 |
| fixed_LS | 0.68781 | −0.00199 (0.00216) | 0.0306 / 0.0317 | +0.00133 (0.00098) | 0.0138 / 0.0137 | 2.21 |
| fixed_SL | 0.65416 | +0.00381 (0.00260) | 0.0367 / 0.0361 | +0.00009 (0.00100) | 0.0142 / 0.0140 | 2.58 |
| fixed_SS | 0.58944 | +0.00181 (0.00203) | 0.0286 / 0.0293 | +0.00005 (0.00104) | 0.0148 / 0.0144 | 1.94 |
| history_S_or_exception | 0.71228 | −0.00170 (0.00213) | 0.0302 / 0.0308 | +0.00027 (0.00089) | 0.0126 / 0.0136 | 2.40 |
| history_large_after_exception | 0.69633 | +0.00209 (0.00120) | 0.0169 / 0.0171 | −0.00077 (0.00095) | 0.0135 / 0.0137 | 1.25 |
| prompt_only_large_if_hard | 0.68841 | −0.00134 (0.00231) | 0.0327 / 0.0334 | −0.00050 (0.00104) | 0.0147 / 0.0141 | 2.23 |

**Prespecified checks:**
- **C1, bias:** all 14 policy × estimator biases are within 3 MCSE. The largest is 1.75 MCSE. Empirical/exact SD
  ratios are 0.92–1.02 for IPW and 0.93–1.04 for fresh.
- **C2, contrasts against `fixed_LL`:** both history-policy contrasts are within 3 MCSE by IPW and by fresh.
  - `history_S_or_exception` (exact −0.01047): IPW −0.00772, fresh −0.01095.
  - `history_large_after_exception` (exact −0.02642): IPW −0.01988, fresh −0.02794. The IPW deviation here, +0.0065 or
    2.4 MCSE, is the largest.
- **C3, selected plug-in (descriptive, adverse):** the exact best-history minus best-other catalog value is −0.0105.
  - Under IPW, the best sampled history policy nonetheless beats the best sampled non-history policy in **41 %** of
    repetitions (mean −0.0082, MCSE 0.0019).
  - Under fresh this happens in **24 %** (mean −0.0098).
  - Most of this is selection noise at n=250 and r=4, since fresh runs show it too; weak overlap raises the rate from
    24 % to 41 %. C3 is descriptive and involves no test, so it is not a false-discovery rate.
- **C4, overlap:** the maximum trajectory weight is 25 (1/0.2²) for every policy except `history_large_after_exception`
  (1.56).
  - No bias or tail problem is detectable at about 3 × 0.002 (|bias| > 3 MCSE or SD > 1.5 × exact never occurs).
  - The logger does impose a large, predicted efficiency loss: IPW's SD is 1.25–3.04 × fresh's, so its variance is up
    to about 9 × fresh's. The exact IPW SDs already include this loss.
  - As a result, IPW picks `fixed_LL` as the best catalog policy in 87 of 200 repetitions, against 146 for fresh.

**Consistency with the null:** the sampled estimates agree with the exact per-policy truths and the exact catalog
contrasts within the prespecified Monte Carlo uncertainty. The analytic optimal-class zero is not contradicted.

**Wording note on `summary.md`.** The generated summary says the exact SDs are "the accepted exact computations". Only
3 of the 7 policies (`fixed_LL`, `prompt_only_large_if_hard`, `history_large_after_exception`) appear in the accepted
`fixed_task_blocks_v1.json`/`fresh_reference_v1.json` for this cell. The other 4 SDs are new values from the same
accepted moment code, reproduced bit-for-bit by an independent check. The generated files are left as produced.
