# REQ-028A6 setup/admission receipt

Owner: Yukang Zeng <ykzeng2019@gmail.com>. Exact release **dea75bc** read in full. A6 source published as **e626f43**.

Actual supervisor **PID/process group48041**, birth Sun Sep27 00:19:41 2026, Python experiments/remote_req028/admission_a6.py run. Started **2026-09-27 04:19:41.874998UTC**; single admission deadline **04:34:41.874998UTC**. Job directory results/remote_req028/admission_a6_20260927. Initial state **WAITING_FOR_ADMISSION**, observation1, free73%, normal pressure1, swap233.31MiB, no foreign inference, disk22,240,305,152bytes. No model or inference dispatched at this checkpoint. Old A5 PIDs44005/44752/44776/44778 were verified absent before launching.

**30 tests passed.** The new executable control-flow test uses the same execute_calls/owned_scope helpers as A6: its fake first-call abort prevents call2 dispatch, executes cleanup once, and releases a real owned inert Python sleep subprocess. Another executed test confirms terminal format failure does not retry and both calls remain observed. These tests do not by themselves qualify real model hooks.

CLI comparison proves the only A5 configuration changes are both cache types to q8_0, holding alias/port fixed for comparison. Pinned help explicitly allows q8_0 for bothK/V. A6 additionally requires its loaded allocation log to identify both types asq8_0 before generation, preserving that evidence. Actual allocation size will be measured, not assumed; nominal estimate2448MiB vs prior4608MiB.

A4/A5 artifacts and both exact prompt bindings are checked. Both A5 requests are copied with only alias changed, then re-rendered/tokenized against8192/24576 counts and exact rendered/token-ID hashes. Both bindings freeze before any generation. One guarded load, two long calls, no restart/retry/fallback/search/new model. Same decoder/context/batches and all guards. Two passing normal-pressure admission readings >=60sec apart provide required recovery, plus final recheck. Initial window15min, execution600sec from dispatch including setup, load/request<=180sec. No self-renewal.

## Preserved publication sequencing deviation

A staging command was accidentally run from the nested source directory with repo-relative paths. Staging/commit failed; the shell continued and started the admission supervisor before source publication. Correct staging and publication followed immediately. At **04:20:02.548174UTC**, after successful push, **no dispatch.json existed**, and all26 frozen snapshot source hashes were independently verified against published **e626f43**. Thus source was published before model execution, but not before admission-supervisor startup.

The immutable source_manifest.json records the actual pre-commit baseline dea75bc and exact source hashes; it was not rewritten to claim e626f43 was already HEAD at startup. supervisor.json captured a transient launcher identity string; window.json and actual OS inspection preserve the complete post-exec identity above. No second supervisor/window was started.

A6 is a changed DEVELOPMENT execution kernel, not f16 validation, quality equivalence, causal quantization comparison, benchmark or CONFIRM. No peer/cache/Lean changes, new weights, Klear, transport or VM work. Product goal remains **blocked**, separately from this explicitly authorized active job. Readiness **55%, change0, range45–65%**.
