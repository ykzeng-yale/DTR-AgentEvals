# REQ-028A6R launch receipt

Owner: Yukang Zeng <ykzeng2019@gmail.com>. Read exact release **f21f0ad** and referenced A6 contract fully. Source **11e85fb** committed and successfully pushed in separate checked operations BEFORE launcher invocation. Launcher additionally verified HEAD equals remote main and every Python source byte matches that published revision before starting any process.

Actual driver/supervisor **PID50009**, born Sun Sep27 00:34:53 2026, Python experiments/remote_req028/mechanics_a6r.py. Launch receipt at04:34:53.474652UTC. No outer admission supervisor/window exists.

Static setup ran ONCE from **04:34:53.517450** to **04:34:56.099990UTC** (2.583sec); persisted setup deadline **04:39:53.517450UTC**, with300-second alarm protection. Source/model/archive hashes and A4/A5 exact request copies were prepared without model residency.

The ONE admission window then began **04:34:56.100690UTC**, deadline **04:49:56.100690UTC**, at most31 total reads including final checks. Actual initial state **WAITING_FOR_ADMISSION**: observation1 at04:34:56.129545UTC, free74%, normal pressure1, swap233.31MiB, no foreign inference, disk22,248,366,080bytes. No model/watchdog or generation started at this checkpoint. Old48041/48252 PIDs and prior owned model/watchdog records were checked for liveness before launch.

**37 tests passed**, preserving prior30. Actual gate fake-clock regressions cover final75->74 resetting and later qualifying within the same deadline; perpetual74 expiry without Popen; final-check deadline crossing; exactly-once success; setup/Popen failure without retry. Existing real shared-control-flow abort/skip-call2/owned inert-process cleanup test remains passed.

A6R model configuration and both requests remain unchanged from A6: q8_0 K/V,32k,batch128/ubatch32, decoder/cache/guard pins;8192 then24576 input tokens. No search/restart/request retry/fallback. Static setup is not repeated after an admission dip. A failed final gate resets the streak only before any Popen and within the original admission deadline/read cap. Once Popen is attempted, no second launch is possible.

Execution deadline will be recorded as600seconds from immediately before Popen; per-load/request180seconds and independent watchdog apply during all loaded tokenization/generation. No execution deadline is claimed to have started while admission is waiting. Full exact prompt bindings must freeze before generation.

Immutable launcher provenance/tests/source snapshots are under results/remote_req028/launch_a6r_20260927. Static manifest and live admission records are under results/remote_req028/mechanics_a6r_20260927. Source publication sequencing was checked before this launch; prior A6 deviation remains preserved in its original records, not erased.

No renewed window, peer/cache/Lean work, new weights, Klear, transport, VM, benchmark or CONFIRM. Product goal remains **blocked** independently of this authorized active job. Readiness **55%, change0, range45–65%**.
