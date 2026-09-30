# DTR-REQ-030AH: complete prospective cohort control qualification

## Scientific decision and scope

The unresolved question is whether a complete, prospectively selected multi-issue SWE-bench DEVELOPMENT cohort has usable independent evaluators under the required no-network sandbox. REQ030AG v10 did not answer model competence: its first Requests control was invalid and every model episode remained unstarted. That cohort (REQ009 ranks 5–12) remains closed. This release cannot retry it or promote a passing subset.

Freeze the next contiguous REQ009 ranks **13–20**, one task in each of eight repositories. Selection uses the pre-outcome 24-ID queue, not observed outcomes. The public/evaluator exporter independently reproduced the pinned M01 row identities and exact upstream evaluation scripts. The eight selected components contain 11 task IDs; all 11 are reserved DEVELOPMENT and excluded from held confirmation. Local record/exposure evidence is scoped evidence, not proof of universal or pretraining nonexposure. Recent remote model-input exposure reconciliation remains necessary before any model release.

This is **one CPU-only evaluator qualification**, not a real-model cohort and not a routing experiment. Every task gets unchanged and reference arms, on fresh workspaces, with all 16 slots recorded before setup. Each arm is attempted once in order when setup and the global budget permit. Rejection of an early arm does not abort later independent controls. Missing, crashed, timed-out, or unattempted arms remain unknown/not attempted. Any invalid arm rejects admission of the complete cohort; no replacements, retries, favorable subset, or hidden-output prompt tuning are allowed.

| Queue rank | Task | F2P | P2P |
|---:|---|---:|---:|
| 13 | django__django-12039 | 1 | 11 |
| 14 | matplotlib__matplotlib-26208 | 2 | 813 |
| 15 | psf__requests-6028 | 2 | 185 |
| 16 | pydata__xarray-6461 | 1 | 247 |
| 17 | pylint-dev__pylint-6386 | 1 | 7 |
| 18 | pytest-dev__pytest-10081 | 1 | 63 |
| 19 | scikit-learn__scikit-learn-25102 | 2 | 59 |
| 20 | sphinx-doc__sphinx-8593 | 2 | 1 |

There are **eight tasks**, not 16 tasks or 1,398 independent observations. These purposive development controls support no population resolution rate, H/P effect, or confidence interval. One exact cohort decision is the primary qualification result; task-level diagnostics and all nested statuses remain visible.

## Exact release and evidence boundary

Release ID: `req030ah-controls-20260930-a`. The executable manifest is [configs/req030ah_controls_20260930.json](../configs/req030ah_controls_20260930.json), SHA-256 `77d7b1b33f221e829aa67f9ce59f928cbbdf0b1453d6661399142827de6e1384`. It binds task IDs, source/image/data hashes, all caps, scripts, evaluator projections and component reservations. Source must be committed before actual submission; the submission receipt records that commit and the independently transferred payload hash.

Input manifest SHA-256: `6dd4b059979412ac79750ca62e397df69a19d243a86068f317cfb78a5eef08bc`. Public OCI metadata SHA-256: `7357bb96a74278b6494ca9d84eac47fb2039e0baf6028186beed7d29fc0ddfe7`. Eight digest-pinned Linux/AMD64 manifests/configs were verified without downloading image layers locally. Advertised compressed layers total 12,340,712,094 bytes. Two offline exports were byte-identical across all 18 files. Public projections contain only `instance_id`, `repo`, `base_commit`, `problem_statement`; reference/test material stays evaluator-only. Raw control outputs remain private.

Evaluator source: SWE-bench `f7bbbb2ccdf479001d6467c9e34af59e44a840f9`. The driver executes exact pinned stock scripts, including their installation commands; it does not silently omit or replace commands after failures. A required network installation is an environment incompatibility to retain, not permission to enable networking. The independent parser runs the exact pinned upstream Python parser bodies with only their enum/annotation imports supplied locally. Four ordered unique framing markers, the exact production supervisor receipt, and every declared identity are required. A masked shell exit zero cannot override missing or failing declared statuses. Unchanged requires all 12 assigned F2P statuses failed and all 1,386 P2P statuses passed across the eight tasks; reference requires all declared statuses passed. Undeclared errors/failures are retained and reviewed, without redefining the declared endpoint.

The source gate records a clean declared base or clean direct stock `SWE-bench` setup child and both trees. A differing setup tree is explicitly `REQUIRES_SETUP_DELTA_REVIEW`, not accepted model input. The model runner continues to require equality with the declared base tree. No model execution branch exists in this CPU driver; even all controls passing yields `CONTROLS_PASS_REVIEW_REQUIRED`, not model authorization.

## Runtime and bounded resources

Use Bouchet `pi_gt353/day/normal`, **4 CPUs, 32 GiB RAM, no GPU, eight hours**. Both authorized accounts are eligible. Same-shape test-only estimates were 02:01:24 ET on October 1 for `pi_fl426` (test-only ID 27950474) and 01:57:24 for `pi_gt353` (27950475); neither is a submitted experiment or reserved start. The latter is selected for the earlier estimate and existing project staging. The refreshed day partition showed 433 idle CPUs and the project filesystem approximately 4.1 TB free. The three available Macs are Darwin/ARM64, incompatible with this frozen Linux/AMD64 Apptainer treatment. No other project's job or cache is modified.

Python module `Python/3.12.3-GCCcore-13.3.0`; actual Apptainer version is recorded inside allocation. Each pull has a 900-second TERM + 15-second KILL limit; each control has a 900-second supervisor deadline and 4 MiB retained-output cap. Fresh image-backed workspaces have a 2–8 GiB bound; root is read-only, no host home/default mounts, and network is none. The standard owner-pipe supervisor cancels the container on driver loss. All benchmark execution occurs inside the allocation/container. No generated commands or model assets are requested.

The independent parent terminates the worker after 27,000 seconds or observed private-directory usage above 80 GiB, checked every two seconds. This is sampled termination with possible transient storage overshoot, not a filesystem quota. Bash RLIMIT_FSIZE independently caps each file at 8 GiB and the runtime asserts/records the byte value. An outer 27,500-second timeout and Slurm eight-hour limit remain. The free-space floor is 100 GiB. Budget exhaustion may prevent remaining arms; their preallocated slots remain unattempted/unknown, and the cohort cannot pass. Per-arm workspaces and only this run's private acquisition cache are cleaned; images, source archives, logs and receipts are retained.

## Consolidated corrections and acceptance work

The lead reviewed the entire model/control path rather than releasing another isolated one-line fix. Deterministic regressions identified and corrected source-archive handoff, colliding model directory names, `torch` scope, dataclass access, harvest path collision and improper salvage after non-submission exits. Only explicit `Submitted` exits can be harvested; ordinary step/time/format limits are operational zeros, while infrastructure exceptions remain unknown. The runner now accepts the real six-field supervisor receipt (`error: null`) and rejects malformed/error receipts; preflight is single-use and invalid capacity cannot leave a cached accepted state. Owner-pipe cleanup now covers spawn failure and caller interruption. Inert tests exercise all 16 old-shape model/task cells plus durable runner events, cancellation and strict output bounds. They make **zero real model calls** and do not constitute container/GPU or competence qualification.

Validation before source publication: **88 tests and 7 subtests passed**, including six actual supervisor/process fixtures; `bash -n` passed. These are deterministic qualification tests, not benchmark outcomes.

A hard per-call/episode CUDA watchdog is still a model-admission blocker: a Python thread timeout does not stop native generation. Source setup-state reconciliation, source-bound native prompt/token receipts, recent exposure inventory and a separate complete real-model release remain required. The former any-one-arm 15–85% feasibility band is not evidence of a competent pair. A future common HF/BF16 pair is a distinct treatment from closed GGUF experiments and must prospectively declare both executor competence and actual second-decision opportunity, including SS/SL/LS/LL comparators if used; none is authorized by this CPU manifest.

## Terminal review and next decision

Retrieve the immutable summary, every raw arm log/receipt, source/image hashes, payload/source identity, file/storage limits and Slurm accounting. Independently replay all declared identities against exact bundle/parser bytes. Distinguish control semantics, setup/implementation failure, insufficient measurement and capacity failure. Preserve evidence against the favored explanation: prior memory use argues against resource scarcity; a stock source tree or declared test mismatch would reject the new environment even if infrastructure exits zero. A successful CPU result cannot demonstrate executor competence or history-aware benefit.

If all controls are valid, perform the separate remaining model-admission review without tuning prompts, budgets or selection on evaluator outcomes. If any control is invalid, retain the whole assigned cohort denominator and reject admission. No automatic fallback cohort, changed network boundary, held CONFIRM or full benchmark is released. During queue/runtime wait, continue independent model-lifecycle and fixed-target inference work.

Preprint readiness **55%, change 0 points, range 45–65%**. Major milestones: competent fixed-target comparisons and valid task/family H/P inference; empirical/manuscript synthesis; independent reproduction and author-approved package.
