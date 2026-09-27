# C6 terminal evidence — c6-dev-20260927-a

Status: infrastructure termination, not a task-success assessment. First recorded failure: `ValueError('sleep length must be non-negative')`. Terminal time: 2026-09-27 09:58:18.720160 UTC.

There were **two physical generation dispatches, two completed raw model calls, and two controller action claims with successful observations**, from one model residency. Three requests were published; the third did not become a model claim. Both completed calls stopped normally and passed the interface gate. No submission or evaluation occurred. Generated commands executed only in the lead sandbox, not on the mini.

The likely source is the separate clock reads around `runner.check()` in `experiments/remote_req028/c6_git.py:58`, allowing a negative sleep after crossing the polling boundary. This is source-based localization, not a measured exception instruction pointer: the original terminal receipt has no traceback. No reproduction, fix, or retry was performed during terminal packaging. The lead separately reports a deterministic fake-clock reproduction; that does not change the original evidence provenance.

The model phase started at 09:56:18.246953 UTC and reached terminal after 120.473207 seconds. HTTP request wall times were 10.573475 and 11.417264 seconds; server prompt/generation timings are nested and must not be added to phase or HTTP wall time. Tokens: 3,817 prompt, 332 completion, 4,149 total; zero cached tokens reported. The receipt preserves effective/request seeds, native bindings, queue spans and network events; exact Git wire-byte counts are unavailable.

Admission passed three samples (free-memory percentages 75, 76, 76). All 117 guard samples had no violation: minimum free memory 38%, maximum owned RSS 2,673,344,512 bytes, minimum disk free 16,422,117,376 bytes, swap unchanged at 233.31 MiB, pressure level 1, and no foreign inference observed.

Owned model cleanup recorded TERM, direct-child reaping and confirmed absence, with no audit errors. Supervisor `Rejected('owner_parent_exited')` describes private-pipe EOF during worker cleanup, not the first failure. The single authorized OS inspection at 10:01:38.962332 UTC found worker 34844, supervisor 35107 and model 35245 all absent; no signals were sent. Controller terminal evidence is included. Lead controller/guardian absence and owned-container removal were reported by the lead, not freshly inspected remotely here.

## Reproducibility package

`runtime_evidence.tar.gz` contains all 1,793 files from the worker runtime, launch directory and checked-out run wire directory. Each archive member was verified against `member_hashes.json`. Accepted requests are also extracted separately and checked against the exact accepted Git objects, SHA-256 values, native bindings and raw response bytes. The complete release is included; all 129 approved source pins matched before packaging.

- Archive SHA-256: `a17d87f45b909b761998c10de96db0220d2f976d781f32eb29944e95c2725723` (915,125 bytes).
- Member mapping SHA-256: `cd7a7121c4bebcae507d0c700b0b0834fc9a9482efc1c5f129ac63b0c27643cc`.
- Approved source: `20aa347ff02c1df4eac994cf8ff960cb1a12458d`.
- Release commit: `1dc0c3217ef1f3be1c7c9c1ea8ea5e8eaba41f62`.
- Release SHA-256: `375716bb06e64f1dcfc44443d6d9629f766f42a0b7bae347c8294e2b47a221cc`.

Raw HTTP responses, native payloads, requests, observations, guard samples, process/network receipts and cleanup audits are preserved. Earlier failures remain untouched. This publication authorizes no rerun, resume, source change, model load or evaluator use.

Readiness: **55%, Δ0, range 45–65%**. Remaining: comparison/inference, synthesis, and reproducibility/package.
