# External trajectory release audit

On 18 September 2026 we downloaded and parsed all six trajectory archives in the [Replay Gap dataset](https://huggingface.co/datasets/ashritha0907/replay-gap-trajectories), pinned to revision `3f3e9f544819afc7fe7faf4a4f5955554e4a15db`. The separate index was excluded to avoid counting the same episodes twice. We did not execute any trajectory commands or republish the raw data.

**Directly observed:** the archives contain **896 rows and 56 distinct task identifiers** across all runs. Thus the release must not be described as 896 independent tasks. [The machine-readable audit](../results/replay_gap_audit/audit.json) records per-file counts, missing outcomes/transcripts, branch availability, observed fields, download URLs and SHA-256 hashes. These counts are our own inspection of the files, not a replication of the paper's outcome analysis.

The inspected top-level schemas contain no sequential assignment-probability field. Fixed small/large continuations at selected forks cannot be assumed to identify arbitrary history-dependent routing policies. Missing outcomes are recorded separately from failure, and all branches from a task must remain in the same analysis cluster.

Use this release for restoration/schema audits, paired continuation analyses with a carefully stated prefix-population target, and external debugging. Collect new prospective randomization logs for general DTR evaluation. The dataset card declares CC BY 4.0; refer to the source release for attribution and asset terms.

Reproduce the audit from the repository root:

```sh
python scripts/audit_replay_gap.py --output results/replay_gap_audit_replication
```

The downloader caches files under ignored `work/replay_gap_cache/` and refuses to overwrite a nonempty output directory.
