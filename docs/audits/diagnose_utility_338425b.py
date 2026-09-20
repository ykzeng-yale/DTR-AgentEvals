"""Retrospective metric sensitivity from frozen live records; no experiment imports.

No model/tool/candidate execution, refitting, resampling, or original-file writes.
The utility grid is descriptive and cannot select a confirmatory objective.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import statistics
import subprocess
from collections import defaultdict
from pathlib import Path

REF = "338425b468cb301f785b0b5daef4a796951f8f55"
BASE = "results/code_routing/"
parser = argparse.ArgumentParser()
parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
parser.add_argument("--output", type=Path)
args = parser.parse_args()


def raw(path):
    return subprocess.check_output(["git", "-C", str(args.repo), "show", f"{REF}:{path}"])


paths = [BASE + "live/episodes.jsonl", BASE + "analysis/frontier_live.csv"]
payloads = {p: raw(p) for p in paths}
rows = [json.loads(line) for line in payloads[paths[0]].splitlines() if line]
assert len(rows) == 3960 and len({r["episode_id"] for r in rows}) == 3960
assert all(not r.get("error") and r["split"] == "confirm" for r in rows)
groups = defaultdict(list)
for r in rows:
    groups[r["policy"]].append(r)
    decisions = r["decisions"]
    cost = sum(0.03 if d["a"] else 0.01 for d in decisions)
    assert math.isclose(cost, r["penalty"], abs_tol=1e-12)
    assert math.isclose(r["success"] - cost, r["utility"], abs_tol=1e-12)
saved = {r["policy"]: r for r in csv.DictReader(io.StringIO(payloads[paths[1]].decode()))}
frontier = {}
for policy, cohort in sorted(groups.items()):
    tasks = defaultdict(list)
    for r in cohort:
        tasks[r["task_uid"]].append(r)
    assert len(cohort) == 660 and len(tasks) == 330
    assert all(len(v) == 2 for v in tasks.values())
    means = {
        "success": statistics.mean(r["success"] for r in cohort),
        "utility": statistics.mean(r["utility"] for r in cohort),
        "calls": statistics.mean(len(r["decisions"]) for r in cohort),
        "large_calls": statistics.mean(sum(d["a"] for d in r["decisions"]) for r in cohort),
        "completion_tokens": statistics.mean(r["completion_tokens"] for r in cohort),
        "wall_seconds": statistics.mean(r["llm_wall_seconds"] for r in cohort),
    }
    # CSV uses the success and utility names; resource names vary by display.
    for metric in ("success", "utility"):
        assert math.isclose(means[metric], float(saved[policy][metric]), abs_tol=1e-12)
    means["small_calls"] = means["calls"] - means["large_calls"]
    frontier[policy] = means

learned, large = frontier["learned"], frontier["always_large"]
delta = {key: learned[key] - large[key] for key in learned}
cost_saving = -(0.01 * delta["small_calls"] + 0.03 * delta["large_calls"])
scale_break_even = -delta["success"] / cost_saving
large_penalty_break_even = (delta["success"] - 0.01 * delta["small_calls"]) / delta["large_calls"]
grid = []
for scale in (0, 0.5, 1, 2, 3, 4):
    values = {
        p: f["success"] - scale * (0.01 * f["small_calls"] + 0.03 * f["large_calls"])
        for p, f in frontier.items()
    }
    grid.append({"penalty_scale": scale, "utilities": values,
                 "learned_minus_large": values["learned"] - values["always_large"]})
report = {
    "ref": REF,
    "status": "Retrospective descriptive metric diagnostic; no new confirmatory inference",
    "input_sha256": {p: hashlib.sha256(v).hexdigest() for p, v in payloads.items()},
    "episodes": len(rows), "policies": len(groups), "tasks_per_policy": 330,
    "checks": "All episode utilities and policy success/utility means reproduce the archive",
    "frontier": frontier, "learned_minus_always_large": delta,
    "original_penalty_cost_saving": cost_saving,
    "penalty_scale_break_even": scale_break_even,
    "large_penalty_break_even_with_small_001": large_penalty_break_even,
    "sensitivity_grid": grid,
    "boundaries": [
        "The scale grid was chosen after observing results; it is not a new primary endpoint.",
        "Break-even values are empirical equalities without inferential or optimization guarantees.",
        "Completion tokens and wall time are separate observed resources, not dollars or energy.",
        "Original unitless penalties and all frozen outcomes remain unchanged.",
        "This grid does not refit the learner or identify what changed-penalty training would learn.",
    ],
}
target = args.output or args.repo / "work/utility_diagnosis_338425b.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
print(json.dumps({"output": str(target), "delta": delta,
                  "scale_break_even": scale_break_even,
                  "large_penalty_break_even": large_penalty_break_even}, indent=2))
