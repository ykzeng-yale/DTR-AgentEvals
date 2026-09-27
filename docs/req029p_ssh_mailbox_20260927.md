# REQ029P — direct SSH immutable data exchange qualification

A bounded fixed-envelope test ran through verified `mac-mini` SSH (strict host-key checking, noninteractive authentication; keys remained outside the repository). Source helper commitd11bda50, SHA103f11742cb793c36e30f2d6eff2b70907c0bfa0bcb30eb91c33fbf7f8e6636f was verified after transfer. A43-byte public nonce envelope was atomically stored and read back with identical SHA; conflicting overwrite was rejected. Publish0.2686s/read0.2158s/conflict0.2142s; full preparation/transfer/check/cleanup1.6915s. These are single fixture measurements, not a latency distribution or model-speed claim.

The owned temporary directory/helper/envelope were removed and absence checked. No model, generated command, Docker, peer process or persistent service was started. Two local helper tests cover role/path/sequence/size/symlink rejection and immutable identical replay. Exact receipt: `results/local_req029/ssh_mailbox_20260927/result.json`; reproducible bounded driver: `experiments/lead_req029/ssh_mailbox_probe.py`. Do not rerun without a new immutable result path: the current driver result path belongs to this completed fixture.

This is a primitive, NOT production protocol qualification. It exposes explicit fixed artifact keys and1MiB payloads; atomic link prevents a partial final object. Same-account SSH is trusted and is not a malicious-user isolation boundary. Crash may leave a pending temporary file. A caller must never retry an indeterminate publication; inspect/reconcile immutable evidence or terminate. Helper idempotent readback of identical data is not proof of exactly-once model execution.

Next: bounded production caller with source/root/role pinning, a finite deadline-aware inspection schedule, poisoned-state handling, process-surviving cleanup and integrated actual two-role tests. Keep model and sandbox authorization separate. No new task/model release follows from this test.

Preprint readiness55%,Δ0,range45–65%; competent fixed-target comparisons/valid inference, manuscript synthesis, independent reproducibility and author-approved package remain.
