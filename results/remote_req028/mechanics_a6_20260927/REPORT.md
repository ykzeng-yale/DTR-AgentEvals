# REQ-028A6 terminal: prelaunch admission rejection, no model result

Owner: Yukang Zeng <ykzeng2019@gmail.com>. Release dea75bc; source e626f43; launch evidence ff917eb. This04:30UTC checkpoint inspected only the existing job. No renewed window or new inference.

## Actual terminal state

Supervisor48041 dispatched driver48252 at **2026-09-27 04:21:42.058136UTC**, then exited **04:21:44.741103UTC** with returncode1. Both PIDs are absent at actual OS inspection. No model/watchdog ownership record or lifecycle exists because no model was launched. **0 generation calls attempted, 0 completed, 0 failed requests, 2 unattempted.**

The admission window recorded4 observations. Free metrics were73%,75%,75%,75%; all pressure readings normal. Passing scheduled readings04:20:41.964467 and04:21:42.028204UTC were more than60seconds apart, providing the required normal recovery interval. Final recheck04:21:42.054589UTC passed at75%, swap233.31MiB, no foreign inference.

After setup, the additional immediate model-prelaunch check at **04:21:44.711621UTC** read **74% free**, below unchanged75%. Pressure1, swap233.31MiB, no foreign inference, disk22,240,665,600bytes. Driver recorded FAILED with an admission assertion; this is **setup completed / model admission rejected / inference not started**, not a q8 serving result. No retry, fallback or renewal occurred. Original admission deadline04:34:41.874998UTC and600second execution cap were not reached.

## Publication sequencing, precisely qualified

- Admission supervisor started **04:19:41.874998UTC**.
- Source commit e626f43 has local commit timestamp **04:19:46UTC**.
- Local remote-tracking reflog records successful **update by push at04:19:47UTC**, second precision. This is the available exact local push-completion receipt, not a separately observed GitHub-server timestamp.
- At **04:20:02.548174UTC**, all26 frozen source hashes were verified against e626f43 and dispatch.json was absent.
- Driver dispatched **04:21:42.058136UTC**.
- Model dispatch: **never occurred**.

A nested-working-directory staging-path error caused admission startup before source publication. It remains a disclosed sequencing deviation. Source publication preceded driver/model execution; the immutable source manifest retains its true baseline dea75bc and exact hashes rather than being rewritten. All26 sources matched the later published commit. The launch identity's transient truncated string is preserved; full post-exec identity was captured in window.json and OS inspection.

## Evidence and interpretation

Verified **45 artifact hashes** and both new source snapshots. Thirty preflight tests passed, including the actual shared control-flow test where a fake first-call abort prevents call2 and releases a real owned inert subprocess. Frozen pre-load manifest declares q8_0 K/V and exact copies of A5's two long requests; pins and A4/A5 artifacts were checked.

No loaded tokenizer validation, effective q8 allocation receipt, prompt-generation manifest, model response, token usage, throughput, pressure-under-load or compliance measurement exists for A6. No q8-versus-f16 comparison can be inferred. Pinned help support alone does not demonstrate loaded execution feasibility.

All prior records remain unchanged. No peer/cache changes, Lean work, new weights, Klear, transport, VM, benchmark or CONFIRM. Product goal remains **blocked**, separate from the completed background job. Readiness **55%, change0, range45–65%**. Lead retains the next experiment decision.
