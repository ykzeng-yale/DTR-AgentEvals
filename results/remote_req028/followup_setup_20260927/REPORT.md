# REQ-028A2 follow-up: admission blocked; A3 not dispatched

Owner: Yukang Zeng <ykzeng2019@gmail.com>. Lead release: adc75d3, read in full from baseline 45a04f03173b50a81ecdf90bf948f5e2411e686e.

## Outcome

A2 setup completed and its manifest was frozen, but admission failed before any model server launch. Free-memory metric was **73%**, below the unchanged **75%** admission minimum. Pressure level was **1 (normal)**, swap **233.31 MiB**, foreign inference list empty, disk free **22,255,489,024 bytes**. No inference process handles, allocations, responses, generated tokens, compliance scores, or load/request timings exist for this attempt. Zero of four calls started. This is neither an inference failure nor evidence of model/host infeasibility.

The dispatcher exited normally after recording the nonqualifying failure. A3 was not dispatched: no A2 adverse-pressure abort or owned server lifecycle existed. No recovery wait or capacity retry occurred. No thresholds changed, downloads, Klear work, transport/VM work, benchmarks or CONFIRM.

## Implementation and checks

New versioned sources preserve A1 unchanged. Seven original source hashes were verified and their bytes archived under followup_setup_20260927/a1_source_snapshot. New sources are archived in setup and stage snapshots. Pinned runner binaries and selected runner source hashes were checked against A1; model size/SHA and server SHA were asserted before admission.

A2 configuration: same original four prompts/order and restart protocol, 32768 context, f16 K/V, one slot, original decoder and cache settings, flash attention on, explicit batch 128/ubatch 32, --verbose allocation logging. Effective uint32 seed recorded as 3081057844. A3 would differ only in K/V q8_0, with an independently frozen manifest; no A3 manifest or run was created.

Seven preflight tests passed: two existing guard tests plus five follow-up tests covering exact CLI, completion skipping A3, qualifying pressure plus cleanup, other failures, and unconfirmed cleanup. Watchdog liveness and ownership checks were added before each request; these paths were not exercised by a real model in this attempt. Existing A1 setup-monitoring gap and its historical repair remain unchanged and preserved; fake tests do not establish complete system assurance.

The generic driver records admission rejection as FAILED; the scientific classification is **SETUP COMPLETE / ADMISSION BLOCKED / INFERENCE NOT STARTED**. No execution deviation from the released caps was taken.

Manifest SHA-256: c3df4f0e652c31b3c40ea62f8f7ee042b6fe42503cf89e79c1d0bc538ea52d79.

## Next lead decision

A new release is needed for a later single admission attempt or another design. This run does not support choosing f16 versus q8 KV because neither configuration performed inference. Do not infer that peers or swap exhaustion caused the unavailable admission margin.

Product goal remains blocked; it was not resumed or marked complete. Scientific readiness **55%, change 0, range 45–65%**. Remaining milestones: competent fixed-target comparison with valid inference, final synthesis, and independent reproducibility with author-approved submission package.
