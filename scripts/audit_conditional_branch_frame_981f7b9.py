#!/usr/bin/env python3
"""Reconstruct archived branch-frame arithmetic from immutable numeric records.

Standard library only. Reads Git blobs and writes one audit JSON. Does not import
experiment code, run candidates/models, resample data, or validate an interval.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess


REVIEWED_SHA = "981f7b9872164697ab79e413a50257c011f11e6f"
BASE = "results/code_routing/"
INPUTS = {
    "branch_plan": BASE + "branch/branch_plan.json",
    "branch_episodes": BASE + "branch/episodes.jsonl",
    "log_episodes": BASE + "log/episodes.jsonl",
    "design": BASE + "design.json",
    "worker_summary": BASE + "analysis/branch_frame_inference.json",
    "worker_source": "experiments/tools/branch_frame_inference.py",
}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def mean(values: list[Fraction]) -> Fraction:
    return sum(values, Fraction()) / len(values)


def variance(values: list[Fraction]) -> Fraction:
    center = mean(values)
    return sum(((x - center) ** 2 for x in values), Fraction()) / (len(values) - 1)


def numeric(value: Fraction) -> dict:
    return {"exact": str(value), "decimal": float(value)}


def unique_error_free(rows: list[dict], label: str) -> dict[str, dict]:
    indexed = {e["episode_id"]: e for e in rows}
    require(len(indexed) == len(rows), label + ": duplicate episode IDs")
    require(all("error" in e and e["error"] is None for e in rows),
            label + ": this audit requires error-free completed records")
    require(all(e["success"] in (0, 1) for e in rows), label + ": nonbinary outcome")
    require(all(e["attempt"] == 1 for e in rows), label + ": unexpected attempt")
    return indexed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--ref", default=REVIEWED_SHA)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    require(re.fullmatch(r"[0-9a-f]{40}", args.ref) is not None, "--ref must be a full commit SHA")
    repo = args.repo.resolve()
    blobs = {
        name: subprocess.check_output(["git", "show", f"{args.ref}:{path}"], cwd=repo)
        for name, path in INPUTS.items()
    }
    plan = json.loads(blobs["branch_plan"])
    design = json.loads(blobs["design"])
    worker = json.loads(blobs["worker_summary"])
    branch_rows = [json.loads(row) for row in blobs["branch_episodes"].splitlines()]
    log_rows = [json.loads(row) for row in blobs["log_episodes"].splitlines()]
    branches = unique_error_free(branch_rows, "branch")
    logs = unique_error_free(log_rows, "log")
    planned = {p["episode_id"]: p for p in plan["episodes"]}
    require(len(planned) == len(plan["episodes"]), "duplicate plan episode IDs")
    require(set(planned) == set(branches), "planned/recorded branch IDs differ")
    require(plan["log_sha256"] == hashlib.sha256(blobs["log_episodes"]).hexdigest(),
            "branch plan's parent-log hash differs")

    confirm = [e for e in logs.values() if e["split"] == "confirm"]
    task_ids = set(design["confirm_tasks"])
    require({e["task_uid"] for e in confirm} == task_ids, "confirm task membership differs")
    require(all(count == 8 for count in Counter(e["task_uid"] for e in confirm).values()),
            "confirm task does not have eight retained log episodes")
    require(all(e["n_decisions"] == len(e["decisions"]) for e in confirm),
            "log decision count differs from nested records")
    eligible = {e["episode_id"]: e for e in confirm if len(e["decisions"]) >= 2}
    require(all(not e["decisions"][0]["validation"]["passed"] for e in eligible.values()),
            "eligible log parent did not first fail visible validation")
    n = len(eligible)
    require(n == plan["n_eligible_prefixes"], "eligible frame count differs from plan")

    per = defaultdict(lambda: defaultdict(list))
    for eid, e in branches.items():
        p = planned[eid]
        parent = e["parent_episode_id"]
        require(parent == p["parent_episode_id"] and parent in eligible, "invalid parent")
        arm = p["forced_arm"]
        require(e["fork_arm"] == ("large" if arm else "small"), "branch arm differs from plan")
        require(e["task_uid"] == p["task_uid"] == eligible[parent]["task_uid"],
                "branch task differs from parent/plan")
        require(e["run"] == p["run"], "replicate index differs from plan")
        require(all(d["a"] == arm for d in e["decisions"]), "branch changed its forced arm")
        per[parent][arm].append(e)

    d_hat, v_hat = [], []
    mixed = []
    discordant_pairs = 0
    for parent, arms in sorted(per.items()):
        require(set(arms) == {0, 1}, "missing branch arm")
        require(all(len(es) == 2 and {e["run"] for e in es} == {0, 1}
                    for es in arms.values()), "not exactly two planned replicates per arm")
        ys = {a: [Fraction(e["success"]) for e in es] for a, es in arms.items()}
        d_hat.append(mean(ys[1]) - mean(ys[0]))
        v_hat.append(variance(ys[1]) / 2 + variance(ys[0]) / 2)
        discordant_pairs += sum(values[0] != values[1] for values in ys.values())
        invocations = {e["invocation"] for es in arms.values() for e in es}
        if len(invocations) > 1:
            mixed.append({"parent_episode_id": parent, "invocations": sorted(invocations)})

    m = len(d_hat)
    fraction = Fraction(m, n)
    b_hat, s2, vbar = mean(d_hat), variance(d_hat), mean(v_hat)
    estimator_first = (1 - fraction) * s2 / m
    estimator_second = fraction * vbar / m
    latent_between = (1 - fraction) * (s2 - vbar) / m
    execution = vbar / m
    total = estimator_first + estimator_second
    require(total == latent_between + execution, "variance decomposition algebra failed")

    num, den = {0: 0, 1: 0}, {0: 0, 1: 0}
    for e in eligible.values():
        ds = e["decisions"]
        require(len(ds) in (2, 3), "unexpected source horizon")
        require(all(d["b_obs"] == 0.5 for d in ds[1:]), "source repair propensity differs")
        arm = ds[1]["a"]
        weight = 2 if len(ds) == 2 else (4 if ds[2]["a"] == arm else 0)
        num[arm] += weight * e["success"]
        den[arm] += weight
    require(den[0] > 0 and den[1] > 0, "pooled source denominator is zero")
    log_contrast = Fraction(num[1], den[1]) - Fraction(num[0], den[0])
    delta_hat = b_hat - log_contrast
    reconstruction = {
        "N_eligible_prefixes": n,
        "m_sampled": m,
        "sampling_fraction": float(fraction),
        "B_hat": float(b_hat),
        "L_of_F": float(log_contrast),
        "delta_hat": float(delta_hat),
        "sample_variance_of_contrasts": float(s2),
        "mean_within_prefix_variance": float(vbar),
        "between_prefix_component": float(estimator_first),
        "execution_component": float(estimator_second),
        "var_hat_frame": float(total),
        "se_frame": math.sqrt(float(total)),
        "prefixes_with_replicates_from_two_invocations": len(mixed),
    }
    differences = {key: reconstruction[key] - worker[key] for key in reconstruction}
    require(all(abs(value) < 1e-12 for value in differences.values()),
            "numeric reconstruction differs from the archived worker summary")
    report = {
        "reviewed_sha": args.ref,
        "scope": "Deterministic arithmetic from immutable archived numeric outcomes; not algebra-only, not an inference or interval-coverage validation.",
        "command": "python3 scripts/audit_conditional_branch_frame_981f7b9.py",
        "imports_experiment_code": False,
        "executes_candidates_models_resampling_or_monte_carlo": False,
        "inputs": {name: {"path": path, "sha256": hashlib.sha256(blobs[name]).hexdigest()}
                   for name, path in INPUTS.items()},
        "counts": {
            "retained_log_records": len(logs), "confirm_log_records": len(confirm),
            "confirm_tasks": len(task_ids), "eligible_prefixes": n, "selected_prefixes": m,
            "tasks_with_selected_prefixes": len({e["task_uid"] for e in branches.values()}),
            "branch_records": len(branches), "replicates_per_prefix_per_arm": 2,
            "same_arm_replicate_pairs": 2 * m, "discordant_same_arm_pairs": discordant_pairs,
            "discordance_fraction": float(Fraction(discordant_pairs, 2 * m)),
        },
        "source_pooled_totals": {"large_numerator": num[1], "large_denominator": den[1],
                                 "small_numerator": num[0], "small_denominator": den[0]},
        "numeric_reconstruction": reconstruction,
        "difference_from_archived_numeric_fields": differences,
        "all_reconstructed_numeric_fields_match_within_1e_minus_12": True,
        "variance_decomposition": {
            "observed_contrast_sample_variance": numeric(s2),
            "mean_estimated_contrast_execution_variance": numeric(vbar),
            "estimated_latent_prefix_variance": numeric(s2 - vbar),
            "estimator_first_summand": numeric(estimator_first),
            "estimator_second_summand": numeric(estimator_second),
            "estimated_latent_between_component": numeric(latent_between),
            "estimated_execution_component": numeric(execution),
            "estimated_latent_between_to_execution_ratio": numeric(latent_between / execution),
            "first_to_second_summand_ratio": numeric(estimator_first / estimator_second),
            "total": numeric(total),
            "interpretation": "Component estimates use the conditional sampling/independent-execution assumptions; their ratio is descriptive, not an unbiased ratio estimator or a design optimum.",
        },
        "contrast_histogram": dict(sorted(Counter(str(x) for x in d_hat).items())),
        "mixed_invocation_prefixes": mixed,
        "archived_normal_interval_not_validated": worker["interval_95_normal"],
        "scientific_boundaries": [
            "The primary fixed-benchmark ratio-of-expected-source-totals target is unchanged.",
            "The conditional-frame target mu_F-L(F) is secondary and does not supersede primary inference.",
            "A justified conditional confidence set could test the frame-specific null Delta_F=0 by inversion; conditioning on L(F) does not prevent that test.",
            "Kernel stability does not imply the realized frame-specific gap is zero.",
            "The reported normal interval is archived arithmetic, not a validated confidence interval.",
            "Distinct seeds, recorded restoration flags and reconstruction do not establish cross-prefix/arm independence, unchanged execution laws across invocations, or outcome-independent recovery.",
        ],
    }
    output = args.output or repo / "docs/audits/conditional_branch_frame_audit_981f7b9.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"output": str(output), "numeric_fields_match": True,
                      "latent_between": float(latent_between), "execution": float(execution),
                      "component_ratio": float(latent_between / execution)}, indent=2))


if __name__ == "__main__":
    main()
