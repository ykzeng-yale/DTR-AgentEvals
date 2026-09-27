# REQ-029C1 — diff metadata binding correction; source/inert only

Status: DONE for the scoped source correction and inert verification; STOP for independent lead review and any new exact execution decision. No Docker, evaluator, model, relay, retry or resume was launched. The actual ref029c-20260927-a failure remains counted and unchanged; it has not been rescored.

Release read in full: d23b7955f915a5b5762617e8203c3e488f928323, docs/req029c1_diff_binding_20260927.md.
Published source: **bb6a24191e0857e9f74c1d05084af1046e217474**.
Only two source files changed: reference_contract.py (normalized only) and reference_tests.py (regressions). Backend, resource limits, input contract, parser, grader, test selection and all historical sources/results are unchanged.

## Root cause and narrow fix

The exact original reference has SHA256 867bc2472fb6f36b4bb180ae83d94b99533948f51c0f16f1e666dd87c9d4c396. The exact observed prepared diff has SHA256 c15fa8fbe16ba95236c30449fdbe8d9aafe0a29dde97fd326413c848d8502819. Original bytes were also verified against reference.original.diff in the archived actual runtime package.

Read-only reproduction confirmed that the old normalization rejected the archived pair. After index metadata removal, the only difference is the trailing hunk-859 annotation: reference def _split(self) versus Git class Card(_Verify). This is an implementation binding defect, not a test failure or passing evaluator result.

The normalizer now recognizes syntactically valid unified-diff hunk headers and removes only trailing annotations following the closing @@. Exact old/new coordinates and optional counts remain; so do line endings, paths, modes, context and added/deleted bytes. Malformed headers are preserved. Existing valid index-line normalization is unchanged. No broad whitespace trimming or content normalization was introduced. Original/prepared bytes and their distinct SHA256 digests remain separate.

## Evidence

The investigate skill imposed reproduction before fixing, a two-file scope, and fresh before/after verification. Its unrelated home setup/telemetry was excluded by the release/filesystem scope.

Before fix, the suite ran 38 methods in 28.262479708 seconds: expected regression failure, nine metadata-annotation subtest failures and one archived-binding error. Existing 34 tests and the new negative cases passed. Full output is retained, not discarded.
After fix, **39/39 methods passed**, including the exact archived pair, metadata-only variants, path/coordinate/count/context/add/delete/mode/whitespace mutations, malformed headers and an additional old-approval rejection test.
The old actual approval is tested with its clock mocked back inside its former validity period; it still rejects the changed source inventory. This does not reuse or renew its authority.

Cumulative recorded suite time: **57.311396791 seconds**, plus the separately recorded 0.0033375-second read-only reproduction; below 300 seconds.
Peak sampled descendant RSS: **133988352 bytes**, below 2 GiB.
Raw fixture bytes before packaging: **21584793**; complete package remains below 100 MiB.
One serial driver and one math thread; macOS CPU affinity is not enforced. RSS and artifact caps are sampled rather than hard OS limits.
Both runs have stable before/after source fingerprints. No actual Docker operation, Astropy evaluation, model generation or hidden-test rerun occurred. Fake subprocesses and fabricated test logs are inert infrastructure evidence only.

Exact executed final test command from repository root:

```sh
python3 experiments/remote_req029/reference_test_suite.py results/remote_req029/reference_binding_c1_20260927/inert_after_fix
```

The directory is immutable; a separately justified test reproduction must use a new inert_* child under this parent for cumulative accounting.

## Package and execution boundary

- inert_evidence.tar.gz: 796760 bytes, 2264 regular members.
- Archive SHA256: 8ef71d68795b1e3aa0d77e83f032c19f878d3e119e31b8d5621bf9d692da69c5.
- member_hashes.json pins all members.
- source_hashes.json pins 157 source/input files at the published source commit.
- archived_input_hashes.json separately pins the actual original/observed inputs, prior approval, failure terminal receipt and original 80-member runtime archive/map.
- Archive includes both inert runs, final source snapshots and exact historical regression inputs. No historical artifact was modified.

No new executable approval is produced. Changed source invalidates old approval a7804c4. Lead must review the new inventory and decide whether to issue a new, unexpired exact-source approval with a fresh immutable reference-only run ID. The failed attempt stays counted, without retry/resume under its identity.

Held candidate command, on the lead's host only after that explicit decision:

```sh
python3 experiments/remote_req029/reference_evaluate.py --commit <NEW_LEAD_APPROVAL_COMMIT> --path docs/req029c_source_c1_approval_20260927.json --pin <NEW_APPROVAL_FILE_SHA256>
```

These placeholders are deliberately unresolved; no execution authority was inferred. No baseline/candidate repeat or model attempt is authorized.

Readiness **55%, change 0 points, range 45–65%**; competent comparison/valid inference, synthesis, reproducibility/approved package remain.
