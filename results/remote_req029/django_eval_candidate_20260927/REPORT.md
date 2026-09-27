# REQ-029I — Django evaluator source candidate, execution held

Source: `9de9aeac873da95f6e7c5e23a43323c08cf26280`. Release: `7f4df2b4dfa891adf70eba6f8ccbff9b899cbd04`. The lead's concurrent REQ-029J changes at `1e90991` were preserved. All new commits use Yukang Zeng <ykzeng2019@gmail.com> as author and committer.

Status: implementation and bounded inert tests complete; **STOP for lead review and a new exact execution approval**. No actual Docker, model, official task tests, task evaluator, download, live poller, peer/VM/cache changes, or enabled production approval was executed/authored. This is not task/environment acceptance, model competence, routing benefit, or new inference approval.

## Delivered boundary

Twelve new `experiments/remote_req029/django_eval_*` source/config files. Old C7, REQ-029C and REQ-029E sources/artifacts are unchanged. Production entrypoints have no fixture switch.

- Exact Django16560 task, base/HEAD, dataset/input/test/reference/manifest/strict-rule bytes, stock selected command, model-free modes, qualified image/archive, resource limits, finite expiry/run namespace, source commit and complete inventory are required before create. Old approval namespaces, substitutions, missing pins, and the disabled example fail closed.
- One serial unchanged-code baseline then one gated reference, each fresh W2R sandbox; 600 seconds per arm including 15-second cleanup reserve, 1200-second pair, bounded by absolute approval expiry. Exclusive run directory and durable claim prevent resume/retry. Baseline requires all 66 P2P PASSED and all 8 F2P FAILED/ERROR, with failing runner exit. Unknown/unexpected baseline or uncertain cleanup cannot dispatch reference. Independent reference guardian checks baseline receipt SHA, source/release identity, cleanup and re-grades bound raw baseline bytes.
- Pinned actual Django registry selects `parse_log_django`; pinned stock command-generation functions reconstruct the exact preserved stock script. Pinned strict rule requires every declared outcome PASSED. All 74 unique declared outcomes, full parser map, extra PostgreSQL-selected keys, upstream short failure aliases, and raw runner totals are reported separately. Missing/skipped/xfail is not pass; malformed/missing markers, parser failure/empty map, setup/resource/timeout failure are not promoted.
- Selected command remains `./tests/runtests.py --verbosity 2 --settings=test_sqlite --parallel 1 constraints.tests postgres_tests.test_constraints`. An ordinary reference runner exit 1 can coexist with all 74 declared PASSED if extra selected tests fail: the candidate preserves that exit and all extra statuses, while the declared endpoint stays exactly the lead's 74 IDs. This behavior is explicit for lead review, not a change to the endpoint.
- Offline adaptation omits exactly `python -m pip install -e .`. It replaces global Git configuration with per-command safe.directory and disables external Git hooks/diff configuration; uses the qualified Python on PATH, disabled bytecode writes and one math thread. Stock script is preserved as data, not falsely described as untouched execution.
- Fixed container helper checks HEAD, immediate parent/base, empty initial source diff, exact Django editable import, readonly root and tmpfs/network properties. Test paths alone are reset as stock specifies; reference source edits are not reset. Prepared source must be empty for baseline or match the frozen reference under reviewed normalization limited to Git index metadata and valid hunk annotation. Payload, mode, patch hashes, prepared diff and commands are bound before test dispatch.
- Preflight records **inside-container** `platform.uname()` system/release/version/machine in `preflight.probe.json`, in the same fixed preflight invocation. Inert receipts label these fields INERT; no host/Astropy value is asserted as measured container data. No prompt builder receives tests/reference.
- Readonly root, 512MiB rw/exec/nosuid/nodev testbed + 64MiB tmp, one CPU, 1GiB/no swap, 128 PIDs, network none, no host mount, ALL caps dropped and no-new-privileges are inspected. Exact owned name/label/CID removal is independent of driver lifetime and diagnostic writes. Ambiguous create/cleanup cannot become accepted.
- New capture preserves raw stdout and stderr separately plus a read-order combined log; combined streamed cap is 4MiB, patches each at most 1MiB. Partial raw prefixes survive timeout/overflow in capture receipts. Operation starts/finishes, retained byte counts, return codes, owned subprocess cleanup, resource configuration, patch/prepared hashes and exact container cleanup identities are retained.

## Provenance

Bundle manifest SHA256 `41207b50e9fbec3ac59e2642a2cecee79ce367c9558635b48cb752ee9d32da17`; dataset SHA256 `a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd`. Upstream source path is `f7bbbb2ccdf479001d6467c9e34af59e44a840f9`; bundle byte hashes are authoritative, **not** the parent repository HEAD. Test patch 11,168 bytes; reference 10,747 bytes.

Loaded image `sha256:935eeb9d7c960a90c1275d3d5a143c72173eecdf8098dacb164af1061f0c0a8f`, original configuration SHA `86afcd19b6c56e5e271a1dfc62177cf03157fe9c9643be560db11480b317cb27`, and compressed registry manifest `sha256:0bafff953ce186aa261162d4091549fb4ad49df938900474b5f070d511bb1604` remain distinct fields. Archive 147,826,688 bytes / `36fdef54ff3e0ad4479fdf80e4ec44344e479cd166797bf637456c3bd6023252`. These are lead-qualified inputs; the worker did not download, import or requalify them.

## Executed inert evidence

| Run | Methods | Result | Receipt seconds |
| --- | ---: | --- | ---: |
| inert_initial | 20 | passed | 26.156286042 |
| inert_final | 22 | passed | 33.103496750 |
| inert_verified | 22 | passed | 34.123024541 |
| inert_final_verified | 22 | passed | 32.440083833 |

All four source snapshots/receipts/logs and raw fixtures remain immutable. The initial timeout case stopped during preflight; subsequent suites explicitly require a dispatched fake test and retained timeout capture. Added unknown-baseline and independent-subprocess journal-failure checks. Third run verifies explicit provenance/per-mode digest changes; final run verifies exact whitespace-clean publication bytes.

Final 22 tests cover actual pinned parser/command generation; FAILED/ERROR/PASSED/skipped/missing/multiline duplicate short names; full 74-vs-extra accounting; task/input/source/arm/asset/patch substitution; prepared-diff binding; actual temporary Git preparation for both arms using **synthetic** patches; no global Git writes; full fake pair and raw streams; unexpected/unknown baseline gates; independent OS-level driver kill; independent journal failure; actual 4MiB overflow; dispatched timeout; immutable no-retry claims; and production guardian rejection before backend construction. Official Django test code was never run on the host.

Cumulative test time **125.822891166 seconds** (<300); peak sampled process-tree RSS **186777600 bytes** (<2GiB). One serial driver and math threads=1; macOS CPU affinity is not enforced, RSS is sampled rather than OS-hard-limited. Retained evidence before this report/summary: 80079047 bytes (<100MiB). Production Docker binary/archive/image attestation and actual container helper preflight/tests remain unexecuted; fake backend bypass is confined to test-owned entrypoints.

Archive `inert_evidence.tar.gz`: 3236807 bytes, **5796 regular members**, all individually re-read/hash verified. SHA256 `78d0fab0791da5fee5f1e254bf77401331d039c99e0422bad6bc3b966ff24db5`. `member_hashes.json` and `source_hashes.json` provide all members and **163 exact source pins**, verified against the source commit. `package_evidence.py` reproduces packaging into a fresh evidence copy. Source/archived evidence reviewed for credential/private-key signatures.

Executed final command (do not rerun without a new need/release):
```sh
python3 experiments/remote_req029/django_eval_test_suite.py results/remote_req029/django_eval_candidate_20260927/inert_final_verified
```

## Held production invocation

The full disabled example is `experiments/remote_req029/django_eval_disabled.json`; execution_authorized=false, expiry=0, source/run/binary pins unset. It cannot launch. Lead must author a new exact approval after review; do not use the source-only release as execution authority.

```sh
python3 experiments/remote_req029/django_eval_evaluate.py --commit <NEW_LEAD_APPROVAL_COMMIT> --path docs/req029i_django_control_approval_20260927.json --pin <EXACT_APPROVAL_FILE_SHA256>
```

The lead must bind source commit `9de9aeac873da95f6e7c5e23a43323c08cf26280`, the exact `source_hashes.json` inventory, actual existing Docker binary SHA, fixed qualified sandbox fields, one new immutable `dje029i-...` run ID and finite expiry. No model patch or model message path exists. The lead owns subsequent qualification, diagnosis of unexpected outcomes and any later execution release. No enabled approval is included.

Readiness **55%, change 0 points, range 45–65%**; competent fixed-target comparison/valid inference, empirical/manuscript synthesis, independent reproducibility/author-approved package remain.

