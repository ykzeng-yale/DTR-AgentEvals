# C6S source-only interval correction

Status: DONE for scoped source correction and inert verification; no activation approval.
Exact source commit: `1a1aa09dbdaf537af6aa4ad499987a80dda027a6`.

## Diagnosis and minimal correction

The investigate workflow required reproducing the defect before editing. The lead's deterministic fake-clock script ran against archived original `c6_git.py` and reproduced `ValueError('sleep length must be non-negative')` with sleep argument `-0.009999999999999787`. Original source SHA-256: `38e3b0e7c19a6c662e9aad12e1e878f2c5a9aba4bbb7cc19355aff3d2e22a272`.

`Transport.fetch` previously sampled time separately for its loop predicate, deadline and sleep duration. Crossing the interval boundary between those reads produced a negative duration. The correction checks cancellation, samples time once, checks the deadline, computes remaining time from that sample, and sleeps only when remaining time is positive. The same sample records fetch start. No retry is added; production minimum five-second spacing, 360-fetch cap and transport-poison checks remain intact. Only this production method and a new test module changed.

This exact defect is reproducible, but the original live terminal receipt has no traceback. Its causal instruction pointer remains inferred, not measured. Complete original terminal evidence was published first at `8e79db667df68f51cd5d9616fa067aed0fa9b804`; the original run and earlier failures remain unchanged.

## Executed verification

One combined run executed eight new deterministic tests and the existing 33 C6 plus 23 C6R tests. Result:

```text
Ran 64 tests in 116.374s
OK
```

New cases: boundary crossing during cancellation check; exact boundary with no sleep; positive waits and five-second spacing across successive fetches; deadline crossed during check; deadline reached after wait; cancellation at boundary; cancellation after wait; 360-fetch and poisoned-transport rejection. All use fake clock, fake sleep and fake Git dispatch. Existing coverage includes local-only Git integration, no-replay behavior, finite lifecycle, guard failure, process death and sandbox adapter behavior with fake Docker.

The bounded wrapper took 116.649230 seconds, plus 0.067832 seconds for the original reproduction: **116.717062 seconds total**, within 300 seconds. Peak sampled descendant RSS was 152,436,736 bytes, below 2 GiB. One serial test driver and one math-library thread were used. macOS core affinity is not enforced; sampled RSS is not a hard memory limit. Retained artifacts before this report totaled 11,613,441 bytes, below 100 MiB. Before/after source hashes matched. No additional defect appeared; no repeated suite or expanded repair scope was used.

## Evidence and next gate

`inert_evidence.tar.gz` contains all 6,328 test/source/reproduction evidence files with verified per-member mapping in `member_hashes.json`, including full fixture records, archived original code, original reproduction, test logs/receipt and exact source snapshot. There are 130 source pins in `source_hashes.json`.

- Archive SHA-256: `15a9c44a0a3a7cead1a6b1f530f4711cfa320bd5970d2b7f64849df28ef803f8` (1,486,768 bytes).
- Mapping SHA-256: `4c163302109477d9b6ef4ab679116033f9d78a1e9e32337f4619eef3c52274cd`.
- Source mapping SHA-256: `3f65e039427867705c77a96e19c5dc3d6131590c6b2bae7f11793b6e46bdcdb9`.

Reproduction and test commands are retained in the corresponding evidence. The original reproduction intentionally expects the old defect and is not a test to run against corrected production source. The corrected suite command was:

```text
python3 experiments/remote_req028/c6_test_suite.py --out results/remote_req028/c6_s_20260927/tests --seconds 295 c6_s_tests c6_tests c6_r_tests
```

Do not reuse that existing output directory or rerun under this completed release. No real model, Docker, live Git poller, new trajectory, resume, evaluator or prompt change ran. The old source approval cannot authorize changed source. Lead review and a NEW immutable development-run approval are required for any later activation. Publication is followed by STOP.

Readiness **55%, Δ0, range 45–65%**. Remaining: competent fixed-target comparison/valid inference, final empirical/manuscript synthesis, independent reproducibility and author-approved package.
