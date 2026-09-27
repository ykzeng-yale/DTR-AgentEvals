# REQ-028C5 terminal: one request completed, owned cleanup confirmed

**TERMINAL_SUCCESS_CLEANUP_CONFIRMED.** One bounded OS inspection at **2026-09-27 08:48:25 UTC** queried launcher68869, driver68870, supervisor69551 and model69660 together. `ps` returned1 with no rows: all four recorded PIDs were absent. This is separate evidence from response publication. No retry, regeneration, source edit or new launch was performed during this check.

The approved invocation exited0 at **08:35:49.625373 UTC**. B3 cleanup confirmed model absence at08:35:49.561178 UTC; the supervisor reaped its direct child. Execution receipt: physical_attempts1, sealedtrue, primarynull, errors[]. A single TERM was recorded, with no KILL needed. Supervisor `failure: Rejected('owner_parent_exited')` is the normal stop path's private-liveness-pipe EOF classification, not evidence that the driver crashed; the driver then exited normally. That label is preserved unchanged.

## Outcome and provenance

- Approved source: `9f8073e974920cb764ab6ec3e2fc21768af85481`.
- Exact approval: `77c306351d6eaae93970bce29301a2f63d79f43c`.
- Response commit: **`1cee7dba5203bd701292242df479141728064f8e`**.
- Response path: `results/remote_req028/c5_execution_20260927/response.json`.
- Response SHA/seal: `bd9e4de23cccd36b9ec5918ed88a66e1499652e370ba86508e248f442cb60487`.
- Native prompt: **1530tokens**, exact independently archived C0 rendered/default-JSON-token hashes match; canonical C3 hash separately labeled in native approval.
- Output: **199tokens**, finish_reason`stop`, cached_tokens0.
- Descriptive C0 interface gate passes. Extracted command text was **not executed**, correctness was not assessed, and this exposed development replay is not independent competence evidence or a latency-improvement claim.

Published Git response bytes were checked against the local sealed bytes before fast-forward. The local original is retained as `response.local_before_sync.json`; syncing main recreated identical bytes at the published path. Source files were not edited. The data-only exact C5 consumer also passed using publication provenance, fresh asset attestation and pre-generation native approval; no replay ledger or tool action was executed.

## Admission, deadlines and timing

Admission readings:73%free rejected, then75% at08:34:33.598 and75% at08:35:33.711, separated by60.113seconds, followed by75% final pre-Popen at08:35:33.791. Normal pressure, no reported foreign inference and disk reserve held. Four total admission observations; no renewal.

| Bound/event | UTC |
| --- | --- |
| Launch |08:33:28.083580|
| Model phase began |08:35:33.797525|
| Load deadline |08:38:33.797525|
| Model-phase deadline |08:45:33.797525|
| Admission deadline |08:48:33.405551|
| Confirmed cleanup |08:35:49.561178|
| Driver exit0 |08:35:49.625373|

Recorded wall spans: load/owned health2.250s; immutable network read0.303s; native binding0.057s; request10.559s; network publication2.390s. Model execution including cleanup15.794s; launch-to-exit141.542s. Server prefill4,553.098ms and generation5,957.132ms are nested within request wall and must not be added again.

Fifteen archived watchdog observations report no guard violations. Minimum free37%, maximum swap233.31MiB (unchanged from baseline), maximum owned RSS2,668,773,376bytes, minimum disk15,356,280,832bytes. These are sampled values, not proof of unsampled maxima. No guard thresholds were weakened.

## Complete evidence publication

`execution_evidence.tar.gz` includes **129 verified files**: raw request/response, fresh asset attestation,102source pins, native binding/approval, HTTP bodies/status logs, physical claim, seal, publication provenance, admission and supervisor telemetry, stdout/stderr, health/identity/deadline/stop/cleanup records, and detached-launch records. Its SHA256 is **`d478665688e933d71b53acfbbc5fffc25edbf3d3e85d52c02081f679bc0fea74`** (665,324bytes).

Only8 reconstructible relay Git object-cache files are omitted from this compact publication archive; their hashes remain in `artifact_hashes.json` and `evidence_manifest.json`. The complete137-file local archive is retained unchanged, SHA`a68131991ab6508290f29a1fb1600a5cd64e0d6a1bc4733cfe25f8458ae0565e`. No raw/native/telemetry/cleanup evidence is excluded. Relay config was inspected and contains only the expected public origin, no credentials.

`os_snapshot.json` preserves the single requested OS check; `terminal_receipt.json` contains machine-readable timing/native/telemetry/outcome details; `consumer_verification.json` records data-only validation. All archived member hashes were rechecked after packing. Main was not advanced by this worker while the job was live; artifact publication occurs only after confirmed terminal cleanup.

Readiness remains **55%, change0points, range45–65%**, pending lead acceptance. Remaining milestones: competent fixed-target comparison with valid inference, separately authorized writable sandbox, final empirical/manuscript synthesis, independent reproducibility and author-approved package. This one activation/transport replay does not authorize additional requests or benchmark work. Stop for lead review.
