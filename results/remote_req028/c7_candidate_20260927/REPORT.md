# C7 executable evaluator candidate, SOURCE ONLY

Status: implementation and inert verification complete; **actual evaluation is NOT released or executed**.
Exact source commit: `adc0c15eaaa4b15946c3854f19f6c3415dfc0c49`.
Only ten new `experiments/remote_req028/c7_*` files were added. No C6 source, earlier release, submitted patch, scientific target, prompt or test body changed.

## Executable boundary and ordering

`c7_evaluate.py` requires a NEW immutable C7 approval commit/path/SHA. It verifies the complete current inventory against the approved source commit, all supplied source snapshots, and the exact 792-byte candidate SHA `c75f2db234217e402628445c66a0e2dfdfb20965bb34b9b6903d9c71462cf171` before creating a runtime or sandbox. A C6 approval is rejected. The included `approval_TEMPLATE_NOT_RELEASED.json` has `execution_authorized: false`, no expiry and an invalid placeholder run ID; it is documentation, not authorization.

Prospective command, only after lead review and a new approval:

```text
python3 experiments/remote_req028/c7_evaluate.py --commit NEW_C7_APPROVAL_COMMIT --path docs/req028_c7_APPROVAL.json --pin NEW_C7_APPROVAL_SHA256
```

The fixed output root is `results/local_req028/c7_runtime/APPROVED_RUN_ID`. An exclusive root and durable run claim prevent restart/resume. Baseline runs first; candidate receives a fresh independently named/labeled sandbox only after confirmed first-sandbox removal. UNKNOWN infrastructure or unconfirmed cleanup stops the pair. A valid but unexpected baseline result is preserved, not repaired. The pair records whether the one F2P was actually FAILED and all 175 P2P were PASSED, separately from generic unresolved status.

Each independent guardian arms its identity/creation intent before create, supervises actual driver identity during setup/test, and owns exact CID/name/label/image reconciliation and removal. Driver death does not depend on the driver's finally block. C6's qualified backend/owner patterns are imported unchanged, with C7-only overrides for fixed evaluation operations, byte-preserving capture and a container lifetime capped to the same 600-second sandbox lease. Each lease includes 15 seconds reserved for cleanup; total serial budget is 1,200 seconds, bounded by absolute release expiry. No renewal or automatic rerun is implemented. A guardian that itself cannot complete cleanup yields UNKNOWN, not a claim of absence.

The exact W2R image/archive and Docker executable hash are rechecked: linux/amd64, one CPU, 1 GiB/no swap, 128 PIDs, network none, read-only root, 512 MiB exec testbed tmpfs and 64 MiB tmp, no host mounts, cap-drop ALL and no-new-privileges. Existing peer containers are rejected; no VM or peer changes, pull, download or package installation occur. Emergency inspect/remove does not depend on successful journal writes. Original cleanup ownership key `dtr.c6.owner` is reused with a fresh C7 namespace and cryptographic label; no prior C6 execution approval is fabricated.

## Exact data-to-sandbox steps

The fixed helper source is passed only to container Python; no generated command or test code executes on the host. It checks original W2R HEAD and clean initial Git state. Baseline applies no candidate; candidate uses the exact frozen patch once, with `git apply --check` and checked apply exit. It then restores only the declared test file from the exact task base and applies the exact dataset test patch once. No patch repair or test editing occurs.

Setup records checked command exits/diagnostics, candidate diff capped at 1 MiB, interpreter/version/import path and installed package inventory. Git diagnostics are captured inside the structured receipt rather than mixed into its JSON. Test execution uses existing testbed Python with `-m pytest -rA astropy/io/fits/tests/test_header.py`, preserving stock selection and start/end marker text.

**This is an explicitly changed execution environment, not the untouched stock harness.** The exact omitted command is `python -m pip install -e .[test] --verbose`. There is no global Git-config write; fixed safe Git arguments/environment and direct testbed interpreter are used. The pinned stock script, grading source, dataset input, parser, constants, strict rule and license remain in the source snapshot. Existing compiled editable imports are reused; actual environment behavior remains for lead's separately released local test.

Raw combined output is streamed with a 4 MiB cap. C7 capture retains original bytes in base64, including invalid UTF-8, and preserves a bounded prefix on timeout/overflow. Reports bind to the retained raw-byte hash and flag incomplete output; partial output cannot become a passing result. A separate unreaped group anchor and private EOF channel keep subprocess cleanup independent of caller loss.

## Strict data-only grading

The hash-pinned concrete Astropy alias/registry is checked, and the exact `parse_log_pytest_v2` function and `TestStatus` class are AST-extracted from supplied upstream snapshots. The exact pinned `declared_outcome` function is likewise used, not reimplemented. Host execution is limited to these reviewed parser/rule definitions; test and model output are data.

Require exactly one correctly ordered marker pair and a nonempty parsed map. Every one of the 176 declared IDs is reported, with absence explicitly `MISSING`. Missing, SKIPPED and XFAIL cannot resolve the task. Exit 1 with valid failed-test logs remains an unresolved test result; timeout, output overflow, setup/apply failure, missing/duplicate/reversed markers, empty map, collection/import error, or unconfirmed cleanup yields UNKNOWN. Exit 1 with an all-PASSED map is treated as inconsistent/UNKNOWN. Parsing is restricted to marker-bounded output, with no upstream whole-log fallback that could promote unrelated text.

Every report binds run/mode, candidate SHA, actually applied patch SHA (empty for baseline), test-input SHA, parser/rule pins, approved full source inventory, raw-byte SHA and cleanup evidence. The driver rejects a substituted patch/report identity. No outcome or hidden tests are forwarded to a model request.

## Executed inert evidence

| Preparation run | Unique methods in that run | Result | Wrapper seconds |
| --- | ---: | --- | ---: |
| Initial implementation | 23 | 23/23 | 24.558348 |
| Byte-preserving capture and approval guards | 27 | 27/27 | 24.713259 |
| Lifetime and partial-output binding | 28 | 28/28 | 24.931998 |
| Final source, structured setup logging | 28 | **28/28** | 24.958150 |

There are **28 final unique tests**, not 106 unique tests; 106 is the number of method executions across four runs. All runs and source fingerprints are preserved, with unchanged before/after sources within each run. Final output:

```text
Ran 28 tests
OK
```

Coverage includes source/patch mismatch before create, nonzero apply preventing test invocation, baseline/candidate isolated identities, test failure versus timeout/setup, all strict status/marker cases, actual inert output overflow, actual host-driver death with independent fake-container removal, no second sandbox after unconfirmed cleanup, journal/terminal write failure cleanup, byte-exact non-UTF-8 capture, parent-exits-first descendant cleanup, no C6 approval reuse, execution hold/wrong inventory, and fixed container lifetime. The container helper is syntax/source inspected; its real Git/pytest execution is **not** claimed from fake-Docker results.

Total test wall budget: **99.161754 seconds**, under 300 seconds. Peak sampled descendant RSS: **123,092,992 bytes**, under 2 GiB. One serial test driver and one math-library thread; macOS one-core affinity is not enforced, and sampled RSS is not a hard limit. Retained evidence before this report: **35,245,938 bytes**, under 100 MiB. No actual Docker/model/evaluator, benchmark, live Git poller, new trajectory or peer change ran on the mini.

## Reproducibility and STOP gate

`inert_evidence.tar.gz` contains all **3,779** evidence/source-snapshot members from the four runs and the final complete source/input snapshot. Every member was verified against `member_hashes.json`. The final inventory has **149** pins, including transitive remote source, source bundle/manifest/license and candidate patch.

- Archive SHA-256: `dd13bd26dde6ce60f0a342e161fe70e7c6070f4f1b6f889425cbc71b45c74315` (875,854 bytes).
- Member mapping SHA-256: `c60b8ebacf8bb07905a6846b5cb7c232f45ba2c2ffe3ca69e47947351d88c7c4`.
- Source mapping SHA-256: `61127e85bf71ed2a5a255ff3d7a5330857591a6c543b9a2188414a3e1d238087`.

The final inert command was `python3 experiments/remote_req028/c7_test_suite.py results/remote_req028/c7_inert_release_20260927`; the existing output is immutable and must not be reused. This implementation publication does not release actual evaluation. Lead review and a NEW exact C7 manifest are next. STOP after publication, no polling loop.

Readiness **55%, Δ0, range 45–65%**. Remaining: competent fixed-target comparison/valid inference, empirical/manuscript synthesis, independent reproducibility and author-approved package.
