#!/usr/bin/env python3
"""Deterministic raw-record check of the worker's evidence table; no execution/import of its code."""
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess

REF = "993f881713ed6c0924b7ac1db2866160026169bf"
ROOT = Path(__file__).resolve().parents[1]
BASE = "results/code_routing/"
PATHS = {
    "log": BASE + "log/episodes.jsonl",
    "branches": BASE + "branch/episodes.jsonl",
    "plan": BASE + "branch/branch_plan.json",
    "design": BASE + "design.json",
    "worker": BASE + "analysis/branch_evidence_table.json",
}


def main():
    blobs = {k: subprocess.check_output(["git", "show", f"{REF}:{p}"], cwd=ROOT)
             for k, p in PATHS.items()}
    log = [json.loads(x) for x in blobs["log"].splitlines()]
    br = [json.loads(x) for x in blobs["branches"].splitlines()]
    plan, design, worker = (json.loads(blobs[k]) for k in ("plan", "design", "worker"))
    assert len({e["episode_id"] for e in log}) == len(log) == 4488
    assert len({e["episode_id"] for e in br}) == len(br) == 800
    assert all(e["error"] is None and e["attempt"] == 1 for e in log + br)
    assert plan["log_sha256"] == hashlib.sha256(blobs["log"]).hexdigest()
    tasks = set(design["confirm_tasks"])
    confirm = [e for e in log if e["split"] == "confirm"]
    assert set(e["task_uid"] for e in confirm) == tasks and len(tasks) == 330
    assert set(Counter(e["task_uid"] for e in confirm).values()) == {8}
    eligible = {e["episode_id"]: e for e in confirm if len(e["decisions"]) >= 2}
    assert all(not e["decisions"][0]["validation"]["passed"] for e in eligible.values())
    assert len(eligible) == plan["n_eligible_prefixes"] == 564
    planned = {e["episode_id"]: e for e in plan["episodes"]}
    assert len(planned) == 800 and set(planned) == {e["episode_id"] for e in br}
    per = defaultdict(lambda: defaultdict(list))
    for e in br:
        p = planned[e["episode_id"]]
        parent, arm = e["parent_episode_id"], e["fork_arm"]
        assert parent == p["parent_episode_id"] and parent in eligible
        assert e["task_uid"] == p["task_uid"] == eligible[parent]["task_uid"]
        assert arm == ("large" if p["forced_arm"] else "small") and e["run"] == p["run"]
        assert e["success"] in (0, 1)
        per[parent][arm].append(e)
    assert len(per) == 200
    blocks = Counter(eligible[parent]["task_uid"] for parent in per)
    pairs, discord, invocations, compositions = Counter(), Counter(), Counter(), Counter()
    contrast = Fraction(0)
    for arms in per.values():
        assert set(arms) == {"small", "large"}
        for arm, es in arms.items():
            assert len(es) == 2 and {e["run"] for e in es} == {0, 1}
            pairs[arm] += 1
            discord[arm] += es[0]["success"] != es[1]["success"]
            invocations.update(e["invocation"] for e in es)
        compositions[frozenset(e["invocation"] for es in arms.values() for e in es)] += 1
        contrast += Fraction(sum(e["success"] for e in arms["large"])
                             - sum(e["success"] for e in arms["small"]), 2)
    reconstructed = {
        "source_blocks": {
            "n_source_tasks_with_branches": len(blocks), "n_prefixes": len(per),
            "prefixes_per_task_distribution": {str(k): v for k, v in sorted(Counter(blocks.values()).items())},
            "max_prefixes_in_one_task": max(blocks.values()),
            "frame": {"N_eligible_prefixes": len(eligible), "sampling_probability": len(per)/len(eligible)},
        },
        "fresh_pairs": {
            "n_same_arm_pairs": sum(pairs.values()), "discordant": sum(discord.values()),
            "discordance_rate": sum(discord.values())/sum(pairs.values()),
            "by_arm": {a: {"pairs": pairs[a], "discordant": discord[a], "rate": discord[a]/pairs[a]}
                       for a in ("small", "large")},
        },
        "recovery": {
            "prefixes_from_one_invocation": sum(n for s, n in compositions.items() if len(s) == 1),
            "prefixes_spanning_two_invocations": sum(n for s, n in compositions.items() if len(s) == 2),
            "prefixes_only_original_invocation": compositions[frozenset({"0445024c72d2"})],
            "prefixes_only_recovery_invocation": compositions[frozenset({"8c343c83afdc"})],
            "continuations_by_invocation": dict(invocations),
        },
    }
    assert all(worker[k] == v for k, v in reconstructed.items())
    full_counts = Counter(e["task_uid"] for e in eligible.values())
    report = {
        "reviewed_commit": REF, "numeric_sections_match": True,
        "input_sha256": {PATHS[k]: hashlib.sha256(v).hexdigest() for k, v in blobs.items()},
        "reconstructed": reconstructed,
        "fixed_frame_tasks": len(tasks),
        "tasks_without_selected_prefix": len(tasks - set(blocks)),
        "eligible_prefix_counts_per_task_including_zeros":
            {str(k): v for k, v in sorted(Counter(full_counts[t] for t in tasks).items())},
        "pooled_sample_branch_mean_exact": str(contrast / len(per)),
        "weighting_example": {"two_tasks_prefix_counts": [1, 3], "effects_by_task": [1, 0],
                              "prefix_mean": "1/4", "equal_task_mean": "1/2"},
        "boundary": "Recorded arithmetic/provenance only; no SRS mechanism, execution independence, kernel stability or CI validation.",
    }
    out = ROOT / "docs/audits/branch_evidence_audit_993f881.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("numeric_sections_match", "fixed_frame_tasks",
          "tasks_without_selected_prefix", "eligible_prefix_counts_per_task_including_zeros",
          "pooled_sample_branch_mean_exact")}, indent=2))


if __name__ == "__main__":
    main()
