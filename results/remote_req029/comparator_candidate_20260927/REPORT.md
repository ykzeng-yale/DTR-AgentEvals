# REQ-029E — executable comparator candidate, source/inert evidence only

**STOP for lead review.** No real model, Docker, evaluator, download, production listener or live Git polling was invoked. Only test-owned loopback HTTP, inert Docker-shaped subprocesses and temporary local Git were exercised. No task/image execution is released by this package.

Design release read in full: **6beaee9b53092125d0a4c8c12a752c075bcbbcef**, docs/req029e_comparator_integration_20260927.md, together with REQ-029A acceptance/correction and REQ-029D decision/common parser source.
Source published first: **7aded9de243cf2c7271f82607baf2479d7ef7c99**.
There are 24 new comparator_* source/config files. Existing req028 sources, feedback.py, the reviewed lead parser, prior approvals and all prior results/archives are unchanged. Concurrent lead exposure/image-metadata/manuscript changes through 0dae769 were preserved, not treated as task release.

## Implemented production path

Entry point: comparator_launch.py worker|controller. New protocol REQ-029E, run namespace cmp029e-*, relay namespace results/remote_req029/comparator_runs, separate runtime roots and exact docs/req029e_*.json approval allowlist. Approval checks happen before role claims, model load or container action. Old C6/029C paths, disabled manifests, source/inventory mismatch and substitution reject. The adapter carries the SHA of exact approved bytes, including noncanonical/pretty JSON, not a reconstructed serialization.

The complete disabled example/schema is experiments/remote_req029/comparator_disabled.json plus comparator_contract.validate. Task, image/archive, prompt, arm, source commits and expiry remain unset; execution_authorized=false. There is no production enabled approval in this delivery. Test-only serialized releases contain dummy source commits and fake image identities to exercise validation; they are not executable production approvals.

Approval binds:
- exact arm and complete artifact/model/cache/template/runner contract, fixed generation/config budgets;
- task ID/base commit, DEVELOPMENT/untouched declaration and exposure-ledger/queue digests;
- exact qualified image/head/archive path/hash/size and source-import module;
- original initial system/user JSON bytes and SHA, complete source inventory, role ownership, expiry and immutable run ID;
- reviewed parser SHA720799e7fa8f9e346a561b40de7a893e146b209dfbd8273fb4ca045c4338589a and pinned upstream submission semantics.
The exposed astropy__astropy-14598 task is explicitly rejected. Task/order and actual image qualification remain lead-owned. Each released pair must use identical initial message bytes and budgets.

Only the existing c0_protocol.ARMS artifacts are selectable: Qwen3-4B with q8_0 KV and community Klear8B with q4_0 KV. Neither is labeled stronger or competent. comparator_assets.json snapshots the accepted model digests/revisions, both native template bytes and existing llama.cpp4fea119 archive/binary/library pins. No downloads, fallback or template/cache search exists. Read-only setup verifies model bytes/hash/native GGUF template, runner archive/source and all pinned executable/libraries. The gate checks asset identities again and starts the exact arm-specific argv. Served-template binding uses Qwen exact bytes and Klear's exact pinned one-final-LF relation.

Worker/controller use comparator_chain and the exact reviewed action_contract.parse_complete. Complete message.content is retained, including closed/unclosed thinking prose; no separate reasoning concatenation or C0 outside-thinking gate. Every request binds full prior history, arm/task/config, object hashes, source and parent chain. Native rendering/token IDs and 1536-token headroom are checked before claims/dispatch; no context-history truncation. Returned prompt/completion/total usage is checked and raw responses survive parse/length failures.

The independent comparator_guardian imports the reviewed feedback.Guardian ordinary-exit execution operation; both protocol sides use its completed-output semantics and hash-bound observations. Completed exits0–255 with exception_infoNone feed the next request. Nonzero sentinel output cannot submit. The unchanged pinned observation template may elide long tool text as documented in029A; the full output/status/hash is separately retained. This is not silent context truncation.

Controller uses task-bound comparator_backend/container/host at unchanged W2R limits:1CPU,1GiB/no swap,128PIDs,networknone,readonlyroot,512MiBexec testbed and64MiBtmp,nosuid/nodev,capdropALL,no-new-privileges,nohostmount. Exact head/source import is verified; commands are stdin DATA to container Python, never executed on host. Streamed1MiB tool output,60-second action cap,independent driver-death cleanup and diagnostic finaldiff priority remain. No official evaluator is on the agent path.

Worker retains one model residency,300-second setup,one900-second/31-read admission window,two>=75%normal/no-peer/12GiB passes>=60seconds apart plus final pre-Popen check,180-second load/request limits,one-second watchdog,terminal guard latch and coordinated bounded cleanup. Model threads2,context32768,batch128/ubatch32,temperature0,seed20260927028,max_tokens1536,max24calls/actions and1800-second phase including queue/tool/relay waits remain fixed. No restart/resume/retry is provided.

Terminal/event artifacts retain deterministic_always_artifact assignment with propensity=null, first-response receipt, actual sent HTTP generation dispatches, action claims/dispatches, call9 reachability and its measured remaining budget, usage/timings and wall times. Dispatch telemetry is based on persisted HTTP request-sent evidence, not a planned request. Setup/admission, load/health, queue/transport and generation costs remain separately recoverable. Submission beforecall9 stops normally; no padding calls. Evaluator outcome, model competence and routing identification remain unassessed.

## Executed inert evidence

Four serial runs, all preserved with their exact source snapshots:
- inert_initial:14/14 passed,52.847381208s.
- inert_final:19/19 passed,66.580263125s.
- inert_verified:22 methods,one fixture error,66.497522292s. The adapter's resolved-path guard correctly rejected the test's macOS /var alias versus /private/var mock root. No production guard was weakened.
- inert_final_verified:**22/22 passed**,66.273479583s, after resolving the fixture root.

Recorded cumulative suite time: **252.198646208s**, below300s. Peak sampled descendant RSS:**150405120 bytes**, below2GiB. Retained bytes after archive/maps and before this report:**37751779**, below100MiB. Single serial test driver,math thread variables1; CPU affinity is not enforced on macOS and RSS/disk caps are sampled, not hard OS isolation. No additional fixture runs are implied or scheduled.

Executed checks include both arms through fake HTTP/native-tokenization and independent fake-Docker guardian trajectories; exact exit1 next-turn full history; exit0; nonzero sentinel; early submission before9; actual physical fake dispatches9/24 with no25; task/prompt/arm/cache/native/source/approval substitution; parser thinking/multiple-fence/length failures with raw preservation; context/tool-output overflow; HTTP timeout; independent model/sandbox driver death; guard latch; crash after durable action claim; no resume/redispatch; temporary-local-Git immutable objects/role namespace; production adapter/guardian entrypoint bindings; pretty approval bytes; exact arm argv; deterministic admission gating. Archived C6 gate and exit1 behavior differ under unchanged source.

Native token IDs and serving in these tests are explicitly fake, not live qualification. Separate read-only comparison found this renderer exactly reproduces both archived native-rendered prompt strings (native_archive_comparison.json); those exposed archived prompts were DATA only, never new requests or task choices.

Review found and fixed exact approval-byte propagation and an explicit cleanup-reserve import before final verification, and tightened integer usage/HTTP sent-event persistence. The final production entrypoint tests use mocked approval/backend construction while process lifecycle tests execute the actual candidate gate/supervisor/HTTP and guardian paths with test-owned replacements. Actual asset attestation, real image behavior and live model performance are intentionally not exercised.

## Exact candidate commands and stop boundary

From repository root, exact final executed fixture command:

```sh
python3 experiments/remote_req029/comparator_test_suite.py results/remote_req029/comparator_candidate_20260927/inert_final_verified
```

This directory is immutable. Do not rerun existing output paths. Remaining fixture budget is not authorization for additional experiments.

After independent lead review, task/image qualification, frozen untouched DEVELOPMENT selection and a NEW exact source/config/expiry/run-ID release, the two production role commands are:

```sh
python3 experiments/remote_req029/comparator_launch.py controller --release-commit <NEW_LEAD_COMMIT> --release-path docs/req029e_cell_approval_20260927.json --release-sha <EXACT_APPROVAL_SHA256> --relay-repo <LEAD_CONTROLLER_RELAY_CHECKOUT>
python3 experiments/remote_req029/comparator_launch.py worker --release-commit <NEW_LEAD_COMMIT> --release-path docs/req029e_cell_approval_20260927.json --release-sha <EXACT_APPROVAL_SHA256> --relay-repo <WORKER_RELAY_CHECKOUT>
```

These are held candidate commands, not executed instructions. No placeholders may be filled using old Astropy/Qwen/C0 defaults. The one-cell approval selects one arm; the other arm requires its own immutable cell and lead sequencing after confirmed cleanup. No automatic two-model load or switching executor is provided or authorized.

## Reproducibility package

inert_evidence.tar.gz: **6560766 bytes**, **13791 regular members**.
Archive SHA256: **ab7d5c773e40196de10d5fc5ca52905c5ae885b60d1f7b3400326906858e8a61**.
member_hashes.json verifies all members; source_hashes.json pins **166** final source/input files, independently checked against published source7aded9d. Archive includes every run's raw fixtures, logs, receipts and source snapshot, final source/config and frozen dependencies. No symlinks/hardlinks in the archive. Staging was limited to owned candidate/evidence paths; required author and committer identities verified.

This is an executable source candidate with inert evidence, not proof of competence, task resolution, image qualification or a routing effect. Lead owns scientific acceptance and any new exact execution release.

Readiness **55%, change0points, range45–65%**; competent fixed-target comparison/valid inference,final empirical/manuscript synthesis,independent reproducibility and author-approved package remain.
