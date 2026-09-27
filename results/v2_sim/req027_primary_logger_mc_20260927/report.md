# DTR-REQ-027: primary logger DEVELOPMENT score experiment

Status: **COMPLETE**, 2,000 independent complete studies in each of the two frozen cells; 4,000 study records retained. Each study averages 4 independent score repetitions on each of 40 fixed tasks. These are marginal contrast-score draws, not agent trajectories. No model, VM, container, package installation, or network access was used for this experiment.

The deterministic common-S score had approximately half the execution variance of the half-initial-S score in this declared generator, consistent with the exact predictions. Wald operating-characteristic estimates ranged from 93.95% to 94.75%; this experiment does not establish real-agent competence, validated inference, practical savings, or protocol adoption.

## Frozen design and exact checks

The 40 tasks comprise 20 with p=1/4 and 20 with p=3/4. In each episode, U is Bernoulli(p), E is Bernoulli(1/4), F=U xor E, A2 is Bernoulli(1/2), and Y is Bernoulli(1/2+eta(2A2-1)(2U-1)). A further independent I is Bernoulli(1/2). The loggers share U,E,A2,Y within an episode, and D_half=2 I D_fixed. The policies take second action F and 0, respectively. Both nuisance predictions are frozen at 1/2.

Exact Fraction enumeration independently confirmed each task's score means, second moments, and the expected four-replicate sample variance. The task target is 2 eta(p-1/4); fixed-task averages are 0 and 1/10. The estimator averages task means equally. Its variance estimate is sum_g s_g²/(40²×4), using within-task sample variances; between-task dispersion is never substituted.

The exact average task variances are (.5,1) at eta=0 and (.48,.98) at eta=1/5 for (fixed,half), giving estimator variances (.003125,.00625) and (.003,.006125). Task heterogeneity at eta=1/5 is therefore included correctly without treating tasks as a random population.

Root seed: 20260927027. Each cell's independent Python random.Random stream is seeded by the integer SHA256 of UTF-8 `20260927027|DTR-REQ-027|eta=<canonical fraction>`. Canonical cell strings are `0` and `1/5`. Studies, tasks, and repetitions consume consecutive independent pseudo-random draws within that stream, in U,E,A2,Y,I order. Code, config, exact truths, test receipt, seeds, and manifest were frozen before sampling.

## Numerical results

Bias MCSE uses empirical study variance divided by 2,000. Variances below concern the fixed-task estimator. All intervals are untruncated.

| eta | Logger | Bias (MCSE) | Empirical variance | Exact variance | RMSE | Mean estimated variance |
|---|---|---:|---:|---:|---:|---:|
| 0 | fixed | −0.0004375 (0.0012824) | 0.00328930 | 0.003125 | 0.0573398 | 0.00313207 |
| 0 | half | 0.0010750 (0.0017861) | 0.00638063 | 0.006250 | 0.0798661 | 0.00625365 |
| 1/5 | fixed | −0.0012656 (0.0012062) | 0.00290972 | 0.003000 | 0.0539431 | 0.00299795 |
| 1/5 | half | −0.0014563 (0.0017403) | 0.00605708 | 0.006125 | 0.0778214 | 0.00611018 |

The paired empirical variance differences (half minus fixed) are 0.00309132, paired delete-one-study jackknife MCSE 0.00017545, at eta=0; and 0.00314736, MCSE 0.00016464, at eta=1/5. The exact difference is 0.003125 in each cell. Descriptive 95% Monte Carlo intervals are [0.00274745,0.00343520] and [0.00282468,0.00347004]. These calculations preserve the pairing between candidate loggers. Empirical variance ratios half/fixed are 1.9398 and 2.0817. The paired mean differences are 0.0015125 (MCSE 0.0012302) and −0.000190625 (MCSE 0.0012720).

| eta | Logger | Wald coverage (MCSE) | Mean Wald length | Variance failures | Hoeffding coverage | Hoeffding width |
|---|---|---:|---:|---:|---:|---:|
| 0 | fixed | 94.25% (0.52 pp) | 0.219085 | 0 | 100% | 0.858939 |
| 0 | half | 94.50% (0.51 pp) | 0.309100 | 0 | 100% | 1.717878 |
| 1/5 | fixed | 93.95% (0.53 pp) | 0.214314 | 0 | 100% | 0.858939 |
| 1/5 | half | 94.75% (0.50 pp) | 0.305542 | 0 | 100% | 1.717878 |

Wald coverage and lengths are marginal 95% operating-characteristic diagnostics. The eta=1/5 fixed-score result is about 1.97 estimated Monte Carlo standard errors below 95%; the four diagnostics do not establish calibration or a general undercoverage theorem. No selection, rerun, or optional extension followed the results. A zero/nonfinite variance would count as noncoverage; there were none.

Hoeffding uses the requested conservative score supports [-2,2] and [-4,4] and 160 independent score draws per study: h=w sqrt(log(40)/(2×160)), where w is 4 or 8. These are marginal guarantees for this frozen design, not a simultaneous guarantee across all cells and loggers. Observed 100% coverage reflects wide intervals and does not establish practical precision. Because frozen q=1/2 makes the actual score supports even narrower, the requested supports are conservative; this run retains them exactly as specified.

## Execution and provenance

The initial command failed before any random draw because this macOS host rejected setting a finite RLIMIT_AS. `pre_sampling_failure.json` preserves that failure. The original frozen `run.py`, config, truths, and manifest remain unchanged. A separately hashed `run_macos.py` wrapper omits only the unsupported AS call. Its compatibility manifest was frozen before sampling. The process retained its CPU limit and low priority, with RSS, system memory pressure, load, and output-size checks every 100 studies. There was no OS-enforced memory ceiling; measured peak RSS was 21,757,952 bytes (about 20.75 MiB), comfortably below the 2 GiB cap.

Simulation began 2026-09-27 01:43:43.756533 UTC and finished at 01:43:44.362811 UTC; recorded simulation wall time was 0.60628 seconds. All 40 resource checks passed. The task setup began at approximately 01:42:12 UTC, within the 15-minute total cap. Output is approximately 0.5 MiB, below 20 MiB. The host had no observed contention requiring a stop. The raw CSV contains 4,000 studies plus its header. No partial study or failed variance report was discarded.

Files: `studies.csv` retains estimates, variance estimates, interval coverage/length, and failure flags for both loggers per study; `summary.json` retains full-precision statistics; `exact_truths.json`, `deterministic_tests.json`, `manifest.json`, `compatibility_manifest.json`, `pre_sampling_failure.json`, `resource_observations.json`, `status.json`, and `sha256.json` retain the execution record. `verify.py` checks source hashes, run hashes, all study IDs, recorded empirical variances, variance-estimate means, coverage, and resource gates without resampling.

Reproduce only in a new empty directory: copy `run.py`, `run_macos.py`, and `config.json`; run `python3 run.py prepare`, then `python3 run_macos.py` on this macOS host (or `python3 run.py simulate` where RLIMIT_AS is supported). Files are created exclusively and an existing run refuses overwrite. For this retained run, execute `python3 verify.py` from its directory to verify without sampling.

Scientific acceptance and publication remain with the local lead. Readiness remains **55%, change 0 points, judgment range 45–65%**. Real-agent competence and inference, final synthesis, reproducibility, and submission packaging remain open.
