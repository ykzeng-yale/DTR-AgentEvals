# REQ-029C reference-only candidate — STOP for lead approval

Status: source and INERT fake-backend evidence only. No actual Docker, evaluator, model, download, live relay, or poller was launched. C7 baseline/submission results and all old sources/archives remain unchanged.

Release read in full: 81891fc8fbe77229ed43b0a416e8bfd76112881b, docs/req029c_reference_control_20260927.md and its reference manifest. Source published first: **143e94fe69ce56e34a174750c6fac45dcae0b88e**. The 157-entry source_hashes.json matches that Git commit, including unchanged C7 backend/container/process helpers and test/parser/strict-rule snapshots.

## Scope and provenance

Seven new reference_* Python files implement one reference_positive_control arm, a separately launched guardian, new REQ-029C approval validation, reference-bound grading and fake tests. No baseline/candidate repeat and no resume of an existing run directory. Old C6/C7 approval paths cannot activate this driver.

Original reference bytes: 963; SHA256 867bc2472fb6f36b4bb180ae83d94b99533948f51c0f16f1e666dd87c9d4c396.
Manifest SHA256: 0349ca2efe272ebe537706e504f71cd4a8ef26dfda9be04ede19be1943af72b2.
Test-patch SHA256: c790ba338bd320c416771738a49f657b02c2bf4e16dcd0d575d1e55d61c4b150.

The unchanged helper's internal candidate slot carries the reference bytes and reference SHA, never C6B's patch SHA. Its raw internal records remain preserved. New driver/guardian external receipts explicitly identify reference_positive_control and reference_patch_sha256, with applied_patch_sha256 null until preparation is validated, then the SHA of the prepared normalized diff. reference.original.diff and reference.prepared.diff are distinct artifacts. The host independently compares all prepared paths, hunk positions/context and changed bytes to the reference; only Git index metadata lines are ignored. Any other normalization mismatch stops before testing, rather than silently weakening binding. No real prepared diff has yet been observed.

The exact C7 test patch/selection, AST-extracted parser and strict rule remain pinned. Success requires all 176 declared statuses PASSED, valid markers, exit 0, no infrastructure error and confirmed owned cleanup. Failed/skipped/missing/exit-1/timeout/overflow/driver-death/uncertain-cleanup cannot resolve successfully. The guardian checks driver identity and lease again after testing, then cleans up in finally. No repair/retry path is supplied.

The production boundary retains W2R image/archive/Docker pins; 600 seconds total including 15 seconds cleanup reserve; 4 MiB output and 1 MiB patch limits; 1 CPU, 1 GiB/no swap, 128 PIDs, network none, read-only root, 512 MiB exec testbed and 64 MiB tmp, cap-drop ALL, no-new-privileges and no host mounts. This is the same offline environment with stock pip install omitted, not untouched stock harness.

## Inert verification

- Initial: 30/30 tests, 28.459429292 seconds (receipt duration).
- Final: 34/34 tests, 28.355447375 seconds (receipt duration).
- Cumulative recorded duration: **56.814876667 seconds**, below 300 seconds.
- Peak sampled descendant RSS: **127254528 bytes**, below 2 GiB.
- Retained artifact bytes before this report: **22789351**, below 100 MiB.
- Serial unittest driver; math thread variables set to 1. macOS CPU affinity was not enforced; RSS/disk limits are sampled, not hard OS isolation.
- Both runs retained, including raw fake process/container evidence. Source fingerprints stable within each run. Review strengthened receipts, cumulative accounting and four approval/binding failure tests between runs.
- Tests cover reference/test substitution before create; one arm and no resume; distinct original/prepared digests; wrong prepared source rejection; exact inventory/source approval and expiry/old-approval rejection; strict grading; real inert streamed overflow/timeout; independent fake-driver death cleanup; journal/terminal write faults; raw byte capture; guardian timeout with no retry.
- No coverage-percentage claim; actual Docker/backend/environment qualification remains unexecuted and is lead-owned.

Final executed test command, from repository root:

```sh
python3 experiments/remote_req029/reference_test_suite.py results/remote_req029/reference_candidate_20260927/inert_final
```

This directory is immutable. Reproduction must use a new inert_* directory within the same parent to retain cumulative accounting; do not rerun merely to consume budget.

## Candidate configuration and held execution command

approval_candidate.json is **NOT executable approval**: execution_authorized=false and expires_at=0. It fixes source commit/inventory, reference/test bindings, single run ID ref029c-20260927-a, mode and 600-second limits. Docker digest is copied as DATA from the frozen C7 source approval, not adopted as execution authorization. Lead must independently verify the existing binary and assets, review source/config, and commit a new docs/req029c_*.json with explicit authorization, finite expiry and immutable unused run ID. Do not mutate a completed run.

Only after that new exact approval, the candidate command on the lead's local host is:

```sh
python3 experiments/remote_req029/reference_evaluate.py --commit <NEW_LEAD_APPROVAL_COMMIT> --path docs/req029c_source_approval_20260927.json --pin <NEW_APPROVAL_FILE_SHA256>
```

The placeholders are deliberately unresolved: no execution approval was supplied or inferred. Guardian command is launched only by this driver, with its newly created spec.json. No real execution on the mini.

## Evidence package and review

inert_evidence.tar.gz: 715328 bytes, **2250 regular members**.
SHA256: 85443953d1d8d2579335ed0973e328912d1586ee4dfdf464af4ef498a5d30737.
member_hashes.json maps every regular member; source_hashes.json maps 157 source/input files. Archive includes final source/input snapshots, both raw fixture runs, logs/receipts and held approval configuration. Raw fixtures also remain local, unmodified.

Ship skill influenced the fresh-test gate, explicit source/coverage review, privacy/staging checks and logical source/evidence split. Repo direct-main rules superseded PR/version/unrelated-doc steps; explicit no-model and filesystem scope excluded model-review calls and home telemetry/setup. Local two-pass source review found no remaining in-scope issue; independent lead review and real evaluation remain required. Unrelated concurrent lead REQ-029D commit 36059c7 was preserved.

**STOP.** No actual reference evaluation is claimed. This candidate neither demonstrates model competence nor routing benefit and does not alter C7 outcomes.

Readiness **55%, change 0 points, range 45–65%**; remaining milestones: competent comparison/valid inference, synthesis, reproducibility/approved package.
