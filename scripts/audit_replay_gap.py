#!/usr/bin/env python3
"""Read-only schema audit of a pinned public release; never execute its text.

Source data stay in the ignored cache. Only aggregate audit/provenance are saved.
This is not a rerun of the original paper or an estimate of a routing effect.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import json
from pathlib import Path
import urllib.request

DATASET = "ashritha0907/replay-gap-trajectories"
REVISION = "3f3e9f544819afc7fe7faf4a4f5955554e4a15db"
FILES = ["easy", "easy_rev", "nudge", "nudge_rev", "pilot30", "pilot30_rev"]


def inspect_file(item):
    name, cache = item
    url = f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{name}.jsonl.gz"
    path = cache / f"{name}.jsonl.gz"
    if not path.exists():
        with urllib.request.urlopen(url, timeout=120) as response:
            path.write_bytes(response.read())
    raw = path.read_bytes()
    rows = [json.loads(line) for line in gzip.decompress(raw).splitlines() if line]
    keys = Counter()
    tasks = set()
    pairs = defaultdict(list)
    for row in rows:
        keys.update(row.keys())
        tasks.add(row["instance_id"])
        if row.get("arm") == "branch":
            pairs[(row["instance_id"], row.get("fork_step"))].append(row.get("model_alias"))
    return {
        "file": path.name, "source_url": url,
        "sha256": hashlib.sha256(raw).hexdigest(), "compressed_bytes": len(raw),
        "rows": len(rows), "unique_tasks": len(tasks), "task_ids": sorted(tasks),
        "arms": dict(Counter(r.get("arm") for r in rows)),
        "resolved": {str(k): v for k, v in Counter(r.get("resolved") for r in rows).items()},
        "messages_missing_or_null": sum(r.get("messages") is None for r in rows),
        "top_level_field_counts": dict(sorted(keys.items())),
        "forks_with_small_and_large": sum({"small", "large"}.issubset(v) for v in pairs.values()),
        "forks_total": len(pairs),
        "routing_propensity_field_present": any("propens" in k.lower() or "behavior_prob" in k.lower() for k in keys),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache", default="work/replay_gap_cache")
    parser.add_argument("--output", default="results/replay_gap_audit")
    args = parser.parse_args()
    cache = Path(args.cache)
    out = Path(args.output)
    if out.exists() and any(out.iterdir()):
        raise SystemExit("Output exists and is nonempty; use a new run directory.")
    cache.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        summaries = list(pool.map(inspect_file, [(name, cache) for name in FILES]))
    all_tasks = set().union(*(set(x["task_ids"]) for x in summaries))
    result = {
        "dataset": DATASET, "revision": REVISION, "audited_date": "2026-09-18",
        "scope": "All six compressed trajectory files; index excluded to avoid double counting.",
        "rows_total": sum(x["rows"] for x in summaries), "unique_tasks_total": len(all_tasks),
        "files": summaries,
        "interpretation": "Counts and schema only. No causal value estimate or paper-result replication. No documented top-level sequential assignment propensity was found; full-text messages are not assignment metadata. Fixed model branches do not identify arbitrary dynamic policies.",
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "audit.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"rows": result["rows_total"], "unique_tasks": len(all_tasks), "output": str(out)}))


if __name__ == "__main__":
    main()
