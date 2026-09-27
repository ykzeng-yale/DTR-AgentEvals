# REQ-028C4: pinned hooks, supervised launch fixtures, no model startup

Final result: **63/63 tests pass** in 24.131 seconds (24.220-second wrapper). This includes the 44 C3R regression cases and 19 C4 cases. Read-only existing-asset attestation passed in **2.368 seconds**. Real model startup remains unconditionally locked. No llama executable invocation, model load/generation, asset download, container/benchmark work, generated-command execution, Klear work, peer changes, or live Git polling service occurred.

Readiness remains **55%, change 0 points, range 45–65%**. Largest remaining milestones are a valid exact-release real-Qwen qualification, separately authorized writable sandbox and competent fixed-target evaluation, final empirical/manuscript synthesis, independent reproducibility, and the author-approved package. This is infrastructure evidence, not competence or scientific improvement.

## Actual asset and source attestation

`../c4_attestation_20260927/attestation.json` records actual paths, sizes and hashes. Its SHA256 is `d8183525c107c93ff8fc50ec0a0f7c0844e562a258ad6047b7767fae524e9e6d`.

- Existing Qwen GGUF: **2,497,281,120 bytes**, SHA256 `3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597`.
- Existing runner binary SHA256 `fd4de7db51a60ad4710725b5e2d2da9060a0b56bf7759767ba81ac719abc4222`, plus every binary/library hash from the accepted baseline.
- Existing source archive SHA256 `3321bc787b971a97f6e7f51dfbb3b72119d9194cd7e6088da3810a89d32c1456`. All **3,602 regular archive members** matched their existing source-tree files under revision `4fea119de30f6a923992780f6fd5ccb0bee5d47d`.
- Native template read from GGUF metadata and checked against the archived native template: SHA256 `c979e0e71a3e21b8f208e6ab120d5cb29327885f29d2a8b18fda67a723798e18`. Reading GGUF bytes/metadata is not loading model tensors into an inference runtime.
- Exact prospective argv is recorded but never executed. C4 explicitly uses `--n-predict 1536`, matching the C3 output cap instead of inheriting the older mechanics helper's 128-token CLI default. Other frozen Qwen settings are retained. Contract SHA remains `218cf178c46e96a88bf1757f565ad64f57be0efea05adfd2ba5f13fb9353b898`.

No duplicate asset copies were made. Hashing had a separate 300-second alarm and per-chunk deadline checks.

## Lifecycle and supervision

`ProductionLifecycle` performs cancellable subprocess-backed real `guard.sample` reads, bounded attestation, exact parent birth-identity checks, a caller-pinned asset/request/release launch plan, a nonrenewing model deadline, and the original `a6r_gate.admit` wiring. The real launch method always raises PermissionError. The actual admission wiring was tested with an injected clock/sample: two passing readings separated by 60 seconds plus final pre-launch reading, then the locked launch; repeated admission rejects.

The supervisor now exists **before it creates a child**. Its child waits on a private pipe before exec. The supervisor records exact child identity and checks driver liveness before releasing that gate. Driver death is detected both by its private liveness pipe closing and exact parent identity. A gated child cannot execute after supervisor pipe EOF. The supervisor holds an unreaped direct-child handle throughout the exec transition and owns cleanup even before an ownership file exists. Cleanup does not depend on a driver `finally` block.

Six actual SIGKILL driver tests cover: before spawn, child spawned but not yet recorded, ownership persisted, immediately before exec release, exec released, and running. Each asserts child/supervisor absence before generic teardown and confirms the control peer remains alive. These inert idle children have **no alarm**, so their cleanup does not rely on a fixture timeout. Exact birth-identity mismatch is separately tested without signaling the control peer; this is not a claim to have forced OS PID reuse.

The supervisor supports real telemetry via a separately cancellable sampler; executed resource-abort cases inject explicit fixture samples. All six abort reasons are asserted exactly: pressure, free metric below20%, swap growth above512MiB, RSS above11GiB, foreign inference, disk below12GiB. Supervision covers gate/load transition and the running child. HTTP fixture listeners are owned, ephemeral, `127.0.0.1` only, and additionally bounded to60seconds. The supervisor has a fixed deadline, never renewed.

One actual read-only telemetry sample per suite was executed. The final sample was pressure1, **free metric73%**, swap233.31MiB, no reported foreign inference, disk17,054,724,096bytes. It **does not satisfy 75% admission**. No real admission loop or model launch followed, and the sample must not be reused as future admission evidence.

## HTTP source check and strict regression

The pinned `tools/server/server.cpp` routes GET `/props` at line249 and POST `/props` at line250 to different handlers. `server-context.cpp` lines4804–4830 show GET retrieves properties while POST is the global-properties mutation handler, disabled without `--props`. Thus C3R's POST was not an alternate property-read method. The strict fixture reproduces rejection of the old C3R POST.

C4 reads GET `/props`; POSTs the **same complete generation body** to `/apply-template` and `/v1/chat/completions`; and POSTs `/tokenize` with exact rendered text, `add_special=true`, `parse_special=true`, `with_pieces=false`. The source at `server-context.cpp` lines5060 onward confirms `/apply-template` uses the same `oaicompat_chat_params_parse` path as chat completion. No truncation or additional decode kwargs are added. Body mutation between binding and generation rejects.

The strict fixed-JSON server rejects wrong methods, paths and bodies. Tests verify matching full transcript/chat parameters, five negative HTTP cases, actual received hanging-request cancellation, and byte-preserving base64/raw-SHA/status capture of an HTTP503 body. Real native tokenizer/model behavior remains unexecuted; the strict fixture's rendering/token IDs and response are intentionally fixed.

## Explicit Git transport and noncircular consumer

The production transport accepts only the exact authorized origin `https://github.com/ykzeng-yale/DTR-AgentEvals.git`, rechecks fetch and push origin before operations, and rejects a dirty source checkout. Executed transport tests use explicitly bounded temporary local bare repositories only. No production relay fetch/publication was invoked by these hooks this turn; ordinary source/results publication is separate.

Each authorization requires caller-supplied release bytes/hash, exact run/request/commit/path/SHA/config entry, expected main, and response path. Initial/next release structure, immutable request ancestry, no deadline renewal, and previous response hash are checked. Disposable worker handles bound and cancel operations. Publication uses a private index and commit-tree, never overwrites source HEAD/index/worktree, never force-pushes, and halts after uncertain/conflicting publication without regeneration or hidden retries.

The concrete test publishes response1, creates an independently approved request2 commit on main through a separate writer checkout, explicitly authorizes that advancement and release chain, then publishes response2. The two response commits differ. Original source HEAD/index/worktree stay unchanged throughout. Race, dirty checkout, arbitrary origin and existing immutable response conflicts reject. The immutable-path test explicitly injects a known base to isolate that guard; it is labeled in the observer.

Before publication, a separately pinned native-binding approval binds the approved release, request commit/path/SHA, config, independently pinned asset attestation, exact native-binding hash and request expiry. The consumer requires that approval pin **and** independently approved response commit/path/SHA provenance, revalidates the original request/release and expiry, checks the protocol3 envelope, and optionally atomically claims a consumption ledger. A self-consistent attacker-modified response binding still rejects against the earlier approval. Stale/expired, wrong provenance/pins and replay cases reject. This consumer returns data only; it has no tool or code execution branch. Pins are trusted caller inputs, not signatures or hashes copied from an untrusted response.

## Preserved failures, resources and verification

The investigation skill guided source-first HTTP diagnosis and the exec-transition correction. The first C4 run had **60 cases, one error**: during a resource test the command-token identity probe briefly returned false across exec, despite the same child becoming identity-matchable immediately afterward. Its B3 receipt records successful TERM cleanup. The supervisor now uses its unreaped direct-child handle across that transition, then resumes exact birth/token checks after exec confirmation; ten distinct lifecycle tests exercise this without retrying within any lifecycle. Child stderr is archived. All original failed artifacts remain intact.

| Run | Outcome | Wrapper wall | Peak sampled RSS | Verified members |
| --- | --- | ---: | ---: | ---: |
| `c4_setup_20260927` | 60 cases, 1 error | 21.407s | 114,130,944B | 1,622 |
| `c4_setup_second_20260927` | 62 pass | 23.919s | 117,702,656B | 1,879 |
| `c4_setup_final_20260927` | 63 pass | 24.220s | 109,985,792B | 1,936 |

Total executed suite wall: **69.546seconds**, below300seconds. Read-only attestation separately used2.368seconds. One compute worker and single-thread library settings were used; macOS CPU affinity is not enforced. RSS sampling retains observed descendants by PID/birth identity after reparenting, but remains sampling, not an address-space guarantee.

The three immutable tar archives preserve all run files, including temporary Git internals. Packaging verified **5,437 member hashes** both on disk and inside archives; current tested sources match the final snapshot. The final archive contains **26 successful supervisor cleanup receipts**, 32 inherited adapter cleanup receipts, and immediate external observations without teardown errors. A final process listing found no remaining C4/C3R fixture, gate, supervisor, driver or operation worker. Test trees, archives and attestation totaled7,089,981 logical bytes before this small report/verification addition, below100MiB. Final archive SHA256: `9b2af4d2b4df625b4d457756e3b371fd5c653f44363ffcc1fd669d9b6965d49d`.

## Remaining release prerequisites

Status: **DONE_WITH_CONCERNS, setup evidence only**. Real launch is denied in `ProductionLifecycle`; the tested exec gate accepts only the pinned inert executable, not arbitrary argv or a model. Activating a pinned model through supervision remains a lead-reviewed release-time change, not a `fixture_only` toggle. Real load/health readiness, native tokenization, generation, cancellation and model/GPU resource behavior have not been qualified. The real telemetry branch has a one-shot sample test, not a live model watchdog run. The startup tests cover driver death, not failure of the OS or simultaneous destruction of all supervision.

Local file writes/fsync cannot be made hard real-time preemptible by these Python hooks; cleanup errors remain separately observable. Sampling can miss very short-lived processes. Live authorized-origin Git integration was not run; tests prove two explicit local publications, not a persistent relay service or end-to-end exactly-once execution across every machine failure. The prospective24-call/1800-second limits remain contracts, not execution permission.

Before any Qwen request: lead reviews these source/artifacts, issues the exact bounded prompt/request/native-approval release, explicitly authorizes activation, and obtains fresh successful admission under all original limits. Writable benchmark sandbox and competent-task pilot require separate authorization. No repeated sandbox probe was performed. Stop here for lead review.
