# REQ-028A4 launch receipt

Owner: Yukang Zeng <ykzeng2019@gmail.com>. Source commit **49a7d30**. Release **1b043f5** read in full from repository baseline b49501d.

## Actual state at launch

Supervisor PID/process group **41825/41825**, birth Sat Sep 26 23:35:59 2026, running Python experiments/remote_req028/admission_a4.py run. Started **2026-09-27 03:35:59 UTC**, single admission-window deadline **03:50:59 UTC**. Job handle is detached local PID 41825; live output path results/remote_req028/admission_a4_20260927.

Initial status **WAITING_FOR_ADMISSION**, observation count **1**. First reading at 03:35:59.069306 UTC: free metric **73%**, normal pressure 1, swap 233.31 MiB, no foreign inference, disk free 22,233,092,096 bytes. Admission failed the unchanged >=75% free gate. No A4 model or generation started at this checkpoint.

Before launching, all prior A2R PIDs 39648,39792,39801,39826,39828 were verified absent; prior_cleanup.json preserves this evidence. No overlapping old window, peer changes or self-renewal.

## Frozen implementation

Twenty-one tests passed before launch. New immutable source snapshot and source manifest preserve all Python source bytes and hashes; previous study files were not changed.

The pinned source exposes /apply-template through the same oaicompat_chat_params_parse formatter used for chat completion. /tokenize uses add_special=true and parse_special=true to match the chat-completion tokenization path. These endpoints perform no generation. The original runner/source/model pins are asserted, including server-common.cpp against the verified source archive.

A4 retains 32k/f16, batch128/ubatch32, one slot, no-warmup, original decoder/cache settings and unchanged independent watchdog. The pre-load manifest records the configuration and pending prompt binding. Once first load is healthy, monitored tokenization deterministically selects repetition counts with exact-token binary search, ordered-query and adjacent-boundary checks. Full common system/user messages are rendered; all six requests, rendered strings, token IDs, counts and hashes are frozen before first generation. Target windows are 8192–8256 and 24576–24640 prompt tokens with >=128 context headroom. Response usage must match each frozen input count.

Exactly six logical calls, no retries: original literal/fence, owned cleanup, bounded restart recovery, repeat literal/fence, then both synthetic long inputs. Recovery samples every15 seconds, requires two passing readings >=15 seconds apart plus final recheck, expires at180 seconds, and is inside the fixed900-second mechanics cap. Every load/request <=180 seconds. A4 has no q8 fallback. All loaded tokenization uses the independent watchdog; restart verifies rendered-template hashes again.

Tests cover six-call order, common system/template use, exact-token target windows/headroom, no generation during prompt setup, one generation dispatch site with failure propagation, recovery success/reset/final-recheck failure/expiry, and unchanged CLI. Prior admission/guard tests also pass. Fake tests do not establish real-model success.

The running job will execute only the released A4 stages if capacity qualifies, otherwise preserve expiry evidence and exit. No new recurring monitor, weights, Klear, transport, benchmark or CONFIRM. Product goal remains **blocked**; job state is separately **waiting for admission**. Readiness remains **55%, change0, range45–65%**.
