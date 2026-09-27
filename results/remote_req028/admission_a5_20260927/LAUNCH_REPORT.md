# REQ-028A5 launch receipt

Owner: Yukang Zeng <ykzeng2019@gmail.com>. Exact release b6b9103 was read in full. Source commit **8b8024e** was published before launch.

Supervisor **PID44005**, process group44005, birth Sat Sep26 23:52:01 2026; Python experiments/remote_req028/admission_a5.py run. Started **2026-09-27 03:52:01.970975UTC**; one admission deadline **04:07:01.970975UTC**. Job handle is detached PID44005; output results/remote_req028/admission_a5_20260927.

Initial stage **WAITING_FOR_ADMISSION**, observation1: free74%, normal pressure1, unchanged swap233.31MiB, no foreign inference, disk22,245,785,600bytes. No A5 model/inference had started at this launch checkpoint. All old A4 PIDs41825,42512,42530,42532 were verified absent before this window; receipt archived.

**26 preflight tests passed.** Source snapshot and hashes are frozen. Existing A4 artifact hashes are verified before copying requests5/6. Only model alias changes; every message and decoder field is preserved. After one guarded load, exact rendered hashes, token-ID hashes and counts8192/24576 must match A4; both new bindings freeze before generation. No token search, short calls, restart, retry or fallback. One generation dispatch site propagates failures; the second call is unattempted if the first aborts.

Same32k/f16/batch128/ubatch32/Metal/two threads/no-warmup/cache settings, seed/output cap and guards. One15-minute admission window, two passing readings >=60sec apart plus final check; no renewal. Execution cap600seconds from dispatch includes setup. Load/generation each <=180seconds, with independent watchdog during loaded tokenization and requests. Tests include exact copies/order, mismatch-before-generation, unchanged CLI, no-retry/no-restart and deadline/cleanup structure; fake tests do not qualify real process hooks.

Existing REQ-028B planning is already published in experiments/remote_req028/split_host_proposal.md. Its transport and Klear proposals remain held. This turn rechecked the pinned pilot interface and current pure residency controller; no transport, Klear, benchmark or peer changes were made.

Product goal remains **blocked**, separately from this authorized active job. Readiness **55%, change0, range45–65%**. This is setup/admission evidence, not inference evidence.
