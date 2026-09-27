# REQ-028A2R bounded supervisor launched

Owner: Yukang Zeng <ykzeng2019@gmail.com>.

Source commit: 554f34d (published to main). Release ab5bcab read in full; source baseline 91788c8.

- Supervisor PID / process group: **39648 / 39648**.
- Birth identity: Sat Sep 26 23:18:21 2026; Python process running experiments/remote_req028/admission_window.py run. Both launch identity and post-exec identity are preserved.
- Started: **2026-09-27 03:18:21 UTC**.
- Admission deadline: **2026-09-27 03:48:21 UTC**.
- Job handle: local detached PID 39648; receipts directory results/remote_req028/admission_window_20260927.
- Initial stage: **WAITING_FOR_ADMISSION**, observation count **1**.
- First reading: normal pressure (1), free metric **73%**, swap **233.31 MiB**, no foreign inference, disk free **22,248,415,232 bytes**.
- Failed gate: free metric below unchanged 75% threshold. **No model resident or inference started by this job.**

Fourteen preflight tests passed, including fake-clock two-reading spacing, reset, expiry, final recheck failure, exactly-once dispatch, no dispatch at expiry, and exact unchanged A2/A3 CLI comparisons. Source bytes/hashes and test results are frozen in source_snapshot, source_manifest.json and tests.json. A1/A2 artifacts and drivers are unmodified. A2R/A3R use distinct output paths that refuse preexisting directories.

The supervisor samples every 60 seconds for one nonrenewing 30-minute window. It conservatively counts final rechecks within the maximum 31 observations. Two consecutive passing readings at least 60 seconds apart and one final passing recheck permit one automatic A2R sequence. The driver checks admission again immediately before server launch. Conditional A3R remains restricted to measured adverse pressure plus confirmed cleanup, with normal recovery. A fresh maximum 30-minute execution budget is separate from admission waiting.

No recurring monitor was added, no peer state changed, and no weights, transport, benchmark or CONFIRM work was started. Live status.json and observations.jsonl remain local while being updated; terminal records will be published at a subsequent lead checkpoint. The existing lead monitor can inspect this job without continuous goal-turn polling.

Product goal remains blocked; scientific readiness remains **55%, change 0, range 45–65%**. This receipt is an admission-wait status, not an inference result or scientific completion.
