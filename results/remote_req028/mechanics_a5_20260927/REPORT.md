# REQ-028A5 terminal evidence: 8k completed, 24k pressure-aborted

Owner: Yukang Zeng <ykzeng2019@gmail.com>. Exact release b6b9103; source8b8024e; launch evidence64db657. This is the requested04:15UTC terminal inspection and publication. No new job, admission window or inference was launched.

## Outcome and owned cleanup

**Two calls attempted: one completed, one failed; zero retries.** A5 status FAILED. Supervisor exited with returncode1 at **2026-09-27 04:01:28.208703UTC**, before the600-second execution deadline04:09:02UTC. The failure was a measured adverse-pressure abort, not a deadline timeout.

Supervisor44005, driver44752, model44776 and watchdog44778 are all **absent** at actual OS inspection. The watchdog abort receipt says reason=adverse_pressure, owned_stop=true. Lifecycle records released=true, model returncode=-9. Owned TERM/KILL cleanup is preserved; no peers were signalled.

Admission dispatched at03:59:02.477114UTC after9 observations; final admission reading at03:59:02.473500UTC passed with free75%, normal pressure1, swap233.31MiB, no foreign inference. The original admission deadline04:07:01.970975UTC was not renewed. No restart or fallback occurred.

## Exact prompt binding

Both requests were copied from A4 prompts5/6 with only the fresh model alias replaced. Pinned template rendering and tokenization matched exact rendered hashes, token-ID hashes, and counts **8192 / 24576**. Both new bindings froze at **03:59:06.262639UTC**, before generation started03:59:06.265877UTC. Full prompts, rendered strings and token IDs are archived. No prompt search or short calibration request was added.

## Call1: completed

Input8192tokens, output4tokens, cached0, HTTP200, finish_reason stop. Literal response **DTR_READY**, exact format compliance and usage/input binding match.

- Wall response: **30.000959seconds**.
- Runner prefill: **29813.251ms**, **274.777tokens/sec**.
- Runner decode: **174.655ms**, reported **17.177tokens/sec**.
- These are the runner's reported timing conventions; output count divided by prediction time is not substituted for its rate.

Generated text was not executed.

## Call2: failed under pressure

Input binding24576tokens was verified before generation. Started03:59:36.270146UTC; request disconnected after **111.871582seconds** with RemoteDisconnected('Remote end closed connection without response'). No completed response bytes, output-token usage, finish reason, compliance result or final prefill/decode timing receipt exists. Do not infer a zero-token response or calculate completed throughput from the interrupted request.

Final watchdog sample at **04:01:27.555187UTC**: **pressure level2**, free metric**21%**, swap**233.31MiB**, owned RSS**4,888,772,608bytes**, no foreign inference, disk22,235,312,128bytes. The reason was adverse_pressure; free was not below20%.

Across136 watchdog samples: free21–75%, maximum sampled RSS4,917,346,304bytes, pressure levels1/2, swap unchanged233.31MiB, no foreign inference. Sampled peaks do not establish continuous maxima. After cleanup the recorded pressure returned to1 and free53%.

## Load, allocations and verification

Healthy load took **1.077632seconds**. Actual allocator logs: Metal f16 KV**4608.00MiB**, Metal compute**150.63MiB**, CPU compute**2.63MiB**, Metal mapped model2375.91MiB and CPU mapped model304.28MiB. Mapped views are not additive independent physical residency. Mechanics elapsed143.075seconds; dispatch-to-exit about145.732seconds, both within600seconds.

This inspection verified **59 artifact hashes**, both new source snapshots, both A4-to-A5 exact request/rendered/token-ID bindings, freeze-before-generation ordering, and call1 raw response/usage against its receipt. All raw logs, requests, responses, pressure samples, manifests, abort and lifecycle records are published.26 preflight tests passed before launch; fake tests alone do not qualify process hooks.

## Interpretation and continuation

A5 demonstrates bounded8k serving on this pinned32k/f16/batch128/ubatch32 configuration under the observed host state. The24k attempt encountered the unchanged pressure guard. It is not a successful24k serving result, a machine-wide impossibility claim, a routing-target empirical null, or coding-competence evidence. No attribution to peers or swap exhaustion is supported.

A4 remains partial with unqualified restart; A5 does not repair that result. No guard weakening, retry, fallback, cache clearing, peer changes, new weights, Klear, transport, benchmark or CONFIRM occurred.

Previously authorized REQ-028B source/interface planning is already complete in experiments/remote_req028/split_host_proposal.md; its exact host/secure-transport and Klear-provenance choices remain lead gates. Its original one-GiB Qwen compute allowance is historical/provisional; measured values above supersede that estimate for this Qwen configuration only, not Klear. No transport or acquisition has been opened.

Product goal remains **blocked**, separate from this terminated experiment. Readiness **55%, change0, range45–65%**. Lead retains scientific acceptance and selection of the next experiment.
