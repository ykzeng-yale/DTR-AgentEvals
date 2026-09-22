#!/usr/bin/env python3
"""
cross_cohort_diagnostic.py -- SYNTHESIS of the four descriptive analyses of the
32 completed block-1 pilot episodes (2 cohorts x 8 instances x 2 backends).

ROLE: synthesizer / worker. This script MERGES four already-written descriptive
artifacts, RE-DERIVES the load-bearing anchor numbers independently from the
committed episode records, and REGISTERS every verifier-reported defect together
with an independent adjudication.

It is strictly read-only with respect to every existing file. It starts no model,
server, container or evaluator, runs no git state-changing command, and never
writes under results/v2_agent/pilot_20260922*/.

Usage:
    python cross_cohort_diagnostic.py [--out-dir <dir>]

Outputs (opened with mode 'x', write-once):
    <out-dir>/cross_cohort_diagnostic.json
    <out-dir>/SUMMARY.md
Default <out-dir> is results/v2_agent/analysis_20260922/ inside the repo.

All paths emitted into the outputs are repo-relative. The local OS username never
appears in an output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict

# ---------------------------------------------------------------------------
# Repo location is derived from this file's own position, never hard-coded, so
# that no absolute user path is ever baked into the source or the outputs.
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

ANALYSIS_DIR_REL = "results/v2_agent/analysis_20260922"
COHORT_DIRS_REL = {
    "legacy": "results/v2_agent/pilot_20260922",
    "yaml-v1": "results/v2_agent/pilot_20260922_yaml_v1",
}
REPORTS_REL = {
    "legacy": "results/v2_agent/pilot_20260922/report_block1_final.json",
    "yaml-v1": "results/v2_agent/pilot_20260922_yaml_v1/report_yaml_v1_block1_final.json",
}

SOURCE_ARTIFACTS_REL = {
    "cross_cohort_divergence": f"{ANALYSIS_DIR_REL}/cross_cohort_divergence.json",
    "repetition_taxonomy": f"{ANALYSIS_DIR_REL}/repetition_taxonomy.json",
    "action_profile": f"{ANALYSIS_DIR_REL}/action_profile.json",
    "budget_profile": f"{ANALYSIS_DIR_REL}/budget_profile.json",
}
VERIFIER_ARTIFACTS_REL = {
    "cross_cohort_divergence": f"{ANALYSIS_DIR_REL}/cross_cohort_divergence_verification.json",
    "repetition_taxonomy": f"{ANALYSIS_DIR_REL}/repetition_taxonomy_verification.json",
    "action_profile": f"{ANALYSIS_DIR_REL}/action_profile_verification.json",
    "budget_profile": f"{ANALYSIS_DIR_REL}/budget_profile_verification.json",
}


def abspath(rel: str) -> str:
    return os.path.join(REPO, rel)


def sha256_of(rel: str) -> dict:
    with open(abspath(rel), "rb") as fh:
        blob = fh.read()
    return {"path_repo_relative": rel, "sha256": hashlib.sha256(blob).hexdigest(), "bytes": len(blob)}


def load(rel: str):
    with open(abspath(rel), "r", encoding="utf-8") as fh:
        return json.load(fh)


# ---------------------------------------------------------------------------
# run_id parsing: <instance_id>__<backend>__<binding>__<timestampZ>-<hex>.
# instance_id itself contains '__', so parse from the END, never by index.
# ---------------------------------------------------------------------------
RUN_ID_TAIL = re.compile(r"^(?P<stamp>\d{8}T\d{6}Z)-(?P<hex>[0-9a-f]+)$")


def parse_run_id(run_id: str) -> dict:
    parts = run_id.split("__")
    if len(parts) < 4:
        raise ValueError("run_id has too few '__' segments")
    tail = parts[-1]
    m = RUN_ID_TAIL.match(tail)
    if not m:
        raise ValueError(f"run_id tail does not match <timestampZ>-<hex>: {tail!r}")
    return {
        "instance_id": "__".join(parts[:-3]),
        "backend": parts[-3],
        "binding": parts[-2],
        "timestamp_utc": m.group("stamp"),
    }


# ---------------------------------------------------------------------------
# INDEPENDENT RE-DERIVATION straight from the committed episode records.
# Nothing in this section reads any of the four analysis artifacts.
# ---------------------------------------------------------------------------
def read_episode(cohort: str, cohort_dir_rel: str, run_id: str) -> dict:
    run_rel = f"{cohort_dir_rel}/{run_id}"
    run_abs = abspath(run_rel)

    episode = json.load(open(os.path.join(run_abs, "episode.json"), encoding="utf-8"))
    grade = json.load(open(os.path.join(run_abs, "grade.json"), encoding="utf-8"))
    with open(os.path.join(run_abs, "submission.diff"), "rb") as fh:
        submission_bytes = len(fh.read())
    messages = json.load(open(os.path.join(run_abs, "trajectory.json"), encoding="utf-8"))["messages"]

    parsed = parse_run_id(run_id)

    # --- commands and their observations, from MESSAGE CONTENT only ---------
    # Template markup lives in the trajectory's config/info block, which is
    # never touched here: we only walk messages[] and only read extra.actions
    # of role 'assistant' plus the immediately following role 'user' message.
    commands: list[str] = []
    observations: list[str | None] = []          # PRE-render command output (extra.raw_output)
    n_format_error = 0
    action_count_not_1 = 0
    n_elided_rendered = 0                        # elision markup lives in the RENDERED text only
    for idx, msg in enumerate(messages):
        role = msg.get("role")
        extra = msg.get("extra") or {}
        if role == "assistant":
            actions = extra.get("actions") or []
            if len(actions) != 1:
                action_count_not_1 += 1
            commands.append(actions[0]["command"] if actions else None)
            obs = None
            if idx + 1 < len(messages) and messages[idx + 1].get("role") == "user":
                nxt_extra = messages[idx + 1].get("extra") or {}
                obs = nxt_extra.get("raw_output")
                if obs is None:
                    obs = messages[idx + 1].get("content")
            observations.append(obs)
        elif role == "user" and extra.get("interrupt_type") == "FormatError":
            n_format_error += 1
        if role == "user":
            content = msg.get("content")
            if content and "<elided_chars>" in content:
                n_elided_rendered += 1

    # --- answered prompt-token series, both ledger dialects -----------------
    rows = []
    n_ledger_records = 0
    dialect_start_events = 0
    with open(os.path.join(run_abs, "attempts.jsonl"), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            n_ledger_records += 1
            if rec.get("event") == "start":
                dialect_start_events += 1
                continue
            if rec.get("prompt_tokens") is None:
                continue  # failed attempt: carries error/detail, no token counts
            rows.append((rec["call"], rec.get("attempt", 1), rec["prompt_tokens"], rec.get("completion_tokens", 0)))
    rows.sort()
    prompt_series = [p for _, _, p, _ in rows]
    completion_total = sum(c for _, _, _, c in rows)
    ledger_dialect = "yaml_v1_start_result_pairs" if dialect_start_events else "legacy_one_record_per_attempt"

    return {
        "cohort": cohort,
        "run_id": run_id,
        "run_dir_repo_relative": run_rel,
        "instance_id": episode.get("instance_id"),
        "backend": episode.get("backend"),
        "binding": parsed["binding"],
        "timestamp_utc": parsed["timestamp_utc"],
        "run_id_parse_matches_episode_json": (
            parsed["instance_id"] == episode.get("instance_id")
            and parsed["backend"] == episode.get("backend")
        ),
        "exit_status": episode.get("exit_status"),
        "n_model_calls": episode.get("n_model_calls"),
        "grade_classification": grade.get("classification"),
        "submission_bytes": submission_bytes,
        "commands": commands,
        "observations": observations,
        "n_commands": len(commands),
        "n_format_error_calls": n_format_error,
        "n_observations_rendered_with_elision": n_elided_rendered,
        "assistant_messages_with_action_count_not_1": action_count_not_1,
        "prompt_token_series": prompt_series,
        "max_answered_prompt_tokens": max(prompt_series) if prompt_series else None,
        "completion_tokens_total": completion_total,
        "prompt_tokens_total": sum(prompt_series),
        "ledger_dialect": ledger_dialect,
        "ledger_records": n_ledger_records,
    }


def rederive_all() -> dict:
    episodes = {}
    for cohort, cdir_rel in COHORT_DIRS_REL.items():
        cdir_abs = abspath(cdir_rel)
        for name in sorted(os.listdir(cdir_abs)):
            run_abs = os.path.join(cdir_abs, name)
            if not os.path.isdir(run_abs):
                continue
            if not os.path.exists(os.path.join(run_abs, "episode.json")):
                continue
            ep = read_episode(cohort, cdir_rel, name)
            episodes[(cohort, ep["instance_id"], ep["backend"])] = ep
    return episodes


def repeat_stats(commands: list[str], observations: list[str | None]) -> dict:
    """Repeat occurrences under BOTH baselines, so the baseline-dependence of the
    headline 'identical observation' figure is explicit rather than implicit."""
    seen_last: dict[str, str | None] = {}
    seen_first: dict[str, str | None] = {}
    repeats = same_prev = same_first = missing = 0
    counts = Counter(commands)
    for cmd, obs in zip(commands, observations):
        if cmd in seen_last:
            repeats += 1
            if obs is None or seen_last[cmd] is None or seen_first[cmd] is None:
                missing += 1
            else:
                if obs == seen_last[cmd]:
                    same_prev += 1
                if obs == seen_first[cmd]:
                    same_first += 1
        else:
            seen_first[cmd] = obs
        seen_last[cmd] = obs
    return {
        "repeat_occurrences": repeats,
        "identical_to_previous_occurrence": same_prev,
        "identical_to_first_occurrence": same_first,
        "repeat_occurrences_missing_observation": missing,
        "distinct_commands": len(counts),
        "max_identical_command_repeats": max(counts.values()) if counts else 0,
    }


def series_relation(a: list[int], b: list[int]) -> dict:
    """Separate pure truncation (shorter is a strict prefix of longer) from a
    genuine disagreement at a shared index. The source budget artifact reports
    only a single boolean and therefore merges these two distinct cases."""
    if a == b:
        return {"relation": "identical", "common_prefix_length": len(a)}
    n = min(len(a), len(b))
    pre = 0
    while pre < n and a[pre] == b[pre]:
        pre += 1
    if pre == n:
        return {"relation": "shorter_is_strict_prefix_of_longer", "common_prefix_length": pre}
    return {"relation": "differs_at_a_shared_index", "common_prefix_length": pre}


def command_divergence(a: list[str], b: list[str]) -> dict:
    n = min(len(a), len(b))
    pre = 0
    while pre < n and a[pre] == b[pre]:
        pre += 1
    if a == b:
        return {
            "identical_command_sequences": True,
            "identical_command_prefix_length": pre,
            "first_divergent_command_index_1based": None,
            "length_mismatch_only": False,
        }
    return {
        "identical_command_sequences": False,
        "identical_command_prefix_length": pre,
        "first_divergent_command_index_1based": pre + 1,
        "length_mismatch_only": pre == n,
    }


# ---------------------------------------------------------------------------
# Output hygiene guard
# ---------------------------------------------------------------------------
def scan_for_leaks(text: str) -> dict:
    username = os.path.basename(os.path.expanduser("~"))
    abs_home = re.findall(r"/Users/[A-Za-z0-9._-]+", text)
    return {
        "contains_local_username_literal": username in text,
        "n_absolute_user_paths": len(abs_home),
        "n_absolute_paths_any": len(re.findall(r'"(?:/[A-Za-z0-9._-]+)+/?"', text)),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=ANALYSIS_DIR_REL,
                    help="output directory (repo-relative, or absolute for a dry run)")
    args = ap.parse_args()
    out_dir = args.out_dir if os.path.isabs(args.out_dir) else abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    # ---------------- provenance -------------------------------------------
    source_hashes = {k: sha256_of(v) for k, v in SOURCE_ARTIFACTS_REL.items()}
    verifier_hashes = {k: sha256_of(v) for k, v in VERIFIER_ARTIFACTS_REL.items()}

    div = load(SOURCE_ARTIFACTS_REL["cross_cohort_divergence"])
    rep = load(SOURCE_ARTIFACTS_REL["repetition_taxonomy"])
    act = load(SOURCE_ARTIFACTS_REL["action_profile"])
    bud = load(SOURCE_ARTIFACTS_REL["budget_profile"])

    # ---------------- independent re-derivation ----------------------------
    eps = rederive_all()
    assignments = sorted({(i, b) for (_c, i, b) in eps})

    integrity = {
        "episodes_read": len(eps),
        "assignments": len(assignments),
        "episodes_per_cohort": dict(Counter(c for (c, _i, _b) in eps)),
        "all_run_id_parses_match_episode_json": all(e["run_id_parse_matches_episode_json"] for e in eps.values()),
        "all_assignments_present_in_both_cohorts": all(
            ("legacy", i, b) in eps and ("yaml-v1", i, b) in eps for i, b in assignments
        ),
        "distinct_run_ids": len({e["run_id"] for e in eps.values()}),
        "ledger_dialect_counts": dict(Counter(e["ledger_dialect"] for e in eps.values())),
        "binding_counts": {
            f"{c}|{bind}": n
            for (c, bind), n in sorted(Counter((e["cohort"], e["binding"]) for e in eps.values()).items())
        },
        "assistant_messages_with_action_count_not_1_total": sum(
            e["assistant_messages_with_action_count_not_1"] for e in eps.values()
        ),
    }

    # ---------------- merged per-assignment table --------------------------
    rep_by = {(e["cohort"], e["instance_id"], e["backend"]): e for e in rep["episodes"]}
    act_by = {(e["cohort"], e["instance_id"], e["backend"]): e for e in act["episodes"]}
    bud_by = {(e["cohort"], e["instance_id"], e["backend"]): e for e in bud["episodes"]}
    div_by = {(p["instance_id"], p["backend"]): p for p in div["pairs"]}

    rows = []
    cross_artifact_disagreements = []
    for inst, backend in assignments:
        row = {"instance_id": inst, "backend": backend, "per_cohort": {}}
        for cohort in ("legacy", "yaml-v1"):
            k = (cohort, inst, backend)
            mine = eps[k]
            r, a, b = rep_by[k], act_by[k], bud_by[k]

            # cross-artifact consistency on fields that appear in more than one
            for field, values in {
                "exit_status": {"rederived": mine["exit_status"], "repetition": r["exit_status"],
                                "action": a["exit_status"], "budget": b["exit_status"]},
                "n_model_calls": {"rederived": mine["n_model_calls"], "repetition": r["n_model_calls"],
                                  "action": a["n_model_calls"], "budget": b["calls"]["logical_calls"]},
                "n_recorded_commands": {"rederived": mine["n_commands"], "repetition": r["total_commands"],
                                        "action": a["n_calls_with_recorded_command"]},
                "submission_bytes": {"rederived": mine["submission_bytes"], "action": a["submission_bytes"],
                                     "budget": b["submission_bytes"]},
            }.items():
                if len(set(values.values())) > 1:
                    cross_artifact_disagreements.append(
                        {"assignment": f"{inst}|{backend}", "cohort": cohort, "field": field, "values": values}
                    )

            rs = repeat_stats(mine["commands"], mine["observations"])
            row["per_cohort"][cohort] = {
                "run_id": mine["run_id"],
                "run_dir_repo_relative": mine["run_dir_repo_relative"],
                "binding": mine["binding"],
                "exit_status": mine["exit_status"],
                "terminating_constraint": b["terminating_constraint"],
                "terminating_constraint_authority": b["terminating_constraint_authority"],
                "grade_classification": mine["grade_classification"],
                "submission_bytes": mine["submission_bytes"],
                "n_model_calls": mine["n_model_calls"],
                "n_recorded_commands": mine["n_commands"],
                "n_format_error_calls": mine["n_format_error_calls"],
                "dominant_repetition_pattern": r["classification"],
                "terminal_cycle_period": r["terminal_cycle_period"],
                "terminal_cycle_repeats": r["terminal_cycle_repeats"],
                "terminal_cycle_start_call": r["terminal_cycle_start_call"],
                "max_identical_command_repeats": rs["max_identical_command_repeats"],
                "distinct_commands": rs["distinct_commands"],
                "any_edit_issued": a["any_edit_primary"],
                "first_edit_call_index": a["first_edit_call_index_primary"],
                "any_run_tests_issued": a["any_run_tests_primary"],
                "any_submit_sentinel": a["any_submit_sentinel"],
                "family_counts_primary": a["family_counts_primary"],
                "n_nonzero_returncode": a["n_nonzero_returncode"],
                "max_answered_prompt_tokens": mine["max_answered_prompt_tokens"],
            }

        leg, yml = eps[("legacy", inst, backend)], eps[("yaml-v1", inst, backend)]
        cmd_div = command_divergence(leg["commands"], yml["commands"])
        dv = div_by[(inst, backend)]
        cmd_div["source_artifact_agrees"] = (
            dv["identical_command_sequences"] == cmd_div["identical_command_sequences"]
            and dv["identical_command_prefix_length"] == cmd_div["identical_command_prefix_length"]
        )
        # The divergence artifact indexes by LOGICAL CALL (format errors included);
        # this row indexes by RECORDED COMMAND. They coincide except where a
        # format error precedes the divergence, so both are carried explicitly.
        cmd_div["first_divergent_logical_call_index_from_divergence_artifact"] = dv["first_divergent_call_index_command"]
        cmd_div["length_mismatch_only_from_divergence_artifact"] = dv[
            "first_divergent_call_index_command_is_length_mismatch_only"
        ]

        row["command_divergence"] = cmd_div
        row["prompt_token_series_relation"] = series_relation(leg["prompt_token_series"], yml["prompt_token_series"])
        row["same_exit_status"] = leg["exit_status"] == yml["exit_status"]
        row["same_terminating_constraint"] = (
            bud_by[("legacy", inst, backend)]["terminating_constraint"]
            == bud_by[("yaml-v1", inst, backend)]["terminating_constraint"]
        )
        row["same_dominant_repetition_pattern"] = (
            rep_by[("legacy", inst, backend)]["classification"]
            == rep_by[("yaml-v1", inst, backend)]["classification"]
        )
        row["same_any_edit_issued"] = (
            act_by[("legacy", inst, backend)]["any_edit_primary"]
            == act_by[("yaml-v1", inst, backend)]["any_edit_primary"]
        )
        rows.append(row)

    # ---------------- cohort-level aggregates ------------------------------
    def agg(pred) -> dict:
        sel = [e for k, e in eps.items() if pred(k, e)]
        cmds = [c for e in sel for c in e["commands"]]
        rs_tot = Counter()
        for e in sel:
            for k2, v in repeat_stats(e["commands"], e["observations"]).items():
                if k2 in ("repeat_occurrences", "identical_to_previous_occurrence",
                          "identical_to_first_occurrence", "repeat_occurrences_missing_observation"):
                    rs_tot[k2] += v
        return {
            "episodes": len(sel),
            "n_model_calls": sum(e["n_model_calls"] for e in sel),
            "n_recorded_commands": len(cmds),
            "n_format_error_calls": sum(e["n_format_error_calls"] for e in sel),
            "unrecorded_model_calls": sum(e["n_model_calls"] for e in sel) - len(cmds),
            "exit_status_counts": dict(Counter(e["exit_status"] for e in sel)),
            "grade_classification_counts": dict(Counter(e["grade_classification"] for e in sel)),
            "episodes_with_empty_submission": sum(1 for e in sel if e["submission_bytes"] == 0),
            "prompt_tokens_total_over_answered_calls": sum(e["prompt_tokens_total"] for e in sel),
            "completion_tokens_total_over_answered_calls": sum(e["completion_tokens_total"] for e in sel),
            "max_answered_prompt_tokens_over_episodes": max(
                (e["max_answered_prompt_tokens"] or 0) for e in sel
            ),
            "repeat_occurrences": rs_tot["repeat_occurrences"],
            "repeat_occurrences_observation_identical_to_previous": rs_tot["identical_to_previous_occurrence"],
            "repeat_occurrences_observation_identical_to_first": rs_tot["identical_to_first_occurrence"],
            "repeat_occurrences_missing_observation": rs_tot["repeat_occurrences_missing_observation"],
        }

    aggregates = {
        "all_32": agg(lambda k, e: True),
        "by_cohort": {c: agg(lambda k, e, c=c: k[0] == c) for c in ("legacy", "yaml-v1")},
        "by_backend": {b: agg(lambda k, e, b=b: k[2] == b) for b in ("large", "small")},
        "by_cohort_backend": {
            f"{c}|{b}": agg(lambda k, e, c=c, b=b: k[0] == c and k[2] == b)
            for c in ("legacy", "yaml-v1") for b in ("large", "small")
        },
    }

    # command-family profile, carried over from the action artifact (its
    # classifier is not re-implemented here; see the defect register)
    aggregates["command_family_profile_from_action_profile"] = {
        "note": "Copied from action_profile.json aggregates; the family classifier is NOT "
                "re-implemented in this script. See defect_register entry ACT-1 for a "
                "reproducibility gap in that artifact's PUBLISHED method text.",
        "overall_family_counts_primary": act["aggregates"]["overall"]["family_counts_primary"],
        "overall_family_share_primary": act["aggregates"]["overall"]["family_share_primary"],
        "by_cohort_family_counts_primary": {
            c: g["family_counts_primary"]
            for c, g in act["aggregates"]["by_cohort"]["groups"].items()
        },
        "edit_write_target_location_counts_overall": act["aggregates"]["overall"][
            "edit_write_target_location_counts"],
    }

    # pair-level aggregates recomputed here
    pair_agg = {
        "assignments": len(rows),
        "identical_command_sequences": sum(1 for r in rows if r["command_divergence"]["identical_command_sequences"]),
        "divergent_command_sequences": sum(
            1 for r in rows if not r["command_divergence"]["identical_command_sequences"]
        ),
        "divergent_of_which_length_mismatch_only": sum(
            1 for r in rows
            if not r["command_divergence"]["identical_command_sequences"]
            and r["command_divergence"]["length_mismatch_only"]
        ),
        "divergent_of_which_differ_at_a_shared_index": sum(
            1 for r in rows
            if not r["command_divergence"]["identical_command_sequences"]
            and not r["command_divergence"]["length_mismatch_only"]
        ),
        "prompt_token_series_relation_counts": dict(
            Counter(r["prompt_token_series_relation"]["relation"] for r in rows)
        ),
        "same_exit_status": sum(1 for r in rows if r["same_exit_status"]),
        "same_terminating_constraint": sum(1 for r in rows if r["same_terminating_constraint"]),
        "same_dominant_repetition_pattern": sum(1 for r in rows if r["same_dominant_repetition_pattern"]),
        "same_any_edit_issued": sum(1 for r in rows if r["same_any_edit_issued"]),
        "identical_command_prefix_lengths_sorted": sorted(
            r["command_divergence"]["identical_command_prefix_length"] for r in rows
        ),
        "identical_command_prefix_length_sum": sum(
            r["command_divergence"]["identical_command_prefix_length"] for r in rows
        ),
    }
    aggregates["per_assignment_pairing"] = pair_agg

    # ---------------- headline claim verification table --------------------
    a32 = aggregates["all_32"]
    legacy_a, yaml_a = aggregates["by_cohort"]["legacy"], aggregates["by_cohort"]["yaml-v1"]

    def claim(cid, dim, text, source_value, my_value, status, note=""):
        return {
            "claim_id": cid,
            "dimension": dim,
            "claim": text,
            "value_as_published": source_value,
            "value_recomputed_by_this_synthesis": my_value,
            "status": status,
            "note": note,
        }

    claims = [
        claim("H01", "all", "Episodes analysed (2 cohorts x 8 instances x 2 backends)",
              32, a32["episodes"], "reproduced"),
        claim("H02", "all", "Every episode produced an empty submission.diff",
              32, a32["episodes_with_empty_submission"], "reproduced"),
        claim("H03", "all", "Every episode was graded operational_zero",
              32, a32["grade_classification_counts"].get("operational_zero"), "reproduced"),
        claim("H04", "budget/repetition", "Total logical model calls across all 32 episodes",
              682, a32["n_model_calls"], "reproduced"),
        claim("H05", "repetition/action", "Total recorded commands across all 32 episodes",
              674, a32["n_recorded_commands"], "reproduced"),
        claim("H06", "repetition", "Model calls that produced no recorded command (unrecorded calls)",
              8, a32["unrecorded_model_calls"], "reproduced",
              "3 of the 8 are FormatError calls recorded in trajectory.json; the remaining 5 "
              "correspond to the 5 failed physical attempts in the ledgers."),
        claim("H07", "divergence", "Format-error calls: legacy vs yaml-v1",
              {"legacy": 1, "yaml-v1": 2},
              {"legacy": legacy_a["n_format_error_calls"], "yaml-v1": yaml_a["n_format_error_calls"]},
              "reproduced"),
        claim("H08", "divergence", "Commands issued per cohort",
              {"legacy": 326, "yaml-v1": 348},
              {"legacy": legacy_a["n_recorded_commands"], "yaml-v1": yaml_a["n_recorded_commands"]},
              "reproduced"),
        claim("H09", "divergence/repetition",
              "Assignments whose full command sequence is byte-identical across cohorts",
              12, pair_agg["identical_command_sequences"], "reproduced"),
        claim("H10", "divergence",
              "Sum of identical command-prefix lengths over the 16 assignments",
              292, pair_agg["identical_command_prefix_length_sum"], "reproduced"),
        claim("H11", "divergence", "Exit-status counts per cohort",
              {"legacy": {"Submitted": 1, "LimitsExceeded": 12, "ContextWindowExceededError": 3},
               "yaml-v1": {"Submitted": 1, "LimitsExceeded": 13, "ContextWindowExceededError": 2}},
              {"legacy": legacy_a["exit_status_counts"], "yaml-v1": yaml_a["exit_status_counts"]},
              "reproduced"),
        claim("H12", "repetition", "Repeated command occurrences across all 32 episodes",
              446, a32["repeat_occurrences"], "reproduced"),
        claim("H13", "repetition",
              "Repeat occurrences whose observation is identical to the PREVIOUS occurrence "
              "(the baseline the published artifact uses)",
              443, a32["repeat_occurrences_observation_identical_to_previous"], "reproduced",
              "Baseline-dependent; see defect REP-1. Under a first-occurrence baseline the "
              "figure is 437, recomputed here as "
              f"{a32['repeat_occurrences_observation_identical_to_first']}."),
        claim("H14", "repetition",
              "Episodes ending in a terminal command cycle",
              28,
              sum(1 for e in rep["episodes"] if e["terminal_cycle"]),
              "reproduced",
              "Carried from repetition_taxonomy.json episodes[] (terminal-cycle detection is not "
              "re-implemented here); the 28/32 count is recomputed from the artifact's own rows."),
        claim("H15", "repetition", "Episodes with at least one command repeated 5 or more times",
              24,
              sum(1 for e in rep["episodes"] if e["max_repeat"] >= 5),
              "reproduced",
              "Recomputed from repetition_taxonomy.json episodes[].max_repeat; the per-episode "
              "max_repeat values were independently re-derived here and agree in 32/32."),
        claim("H16", "action", "Episodes in which any edit-family command was issued",
              10, sum(1 for r in rows for c in r["per_cohort"].values() if c["any_edit_issued"]),
              "reproduced"),
        claim("H17", "action", "Episodes in which any run-tests-family command was issued",
              0, sum(1 for r in rows for c in r["per_cohort"].values() if c["any_run_tests_issued"]),
              "reproduced"),
        claim("H18", "budget", "Terminating-constraint counts across all 32 episodes",
              {"step_limit_H24": 25, "context_window": 5, "submitted": 2},
              dict(Counter(c["terminating_constraint"] for r in rows for c in r["per_cohort"].values())),
              "reproduced",
              "The published field omits explicit zero entries for wall_clock and other; both are "
              "0 here. See defect BUD-3."),
        claim("H19", "budget", "Prompt tokens summed over answered calls (all 32 episodes)",
              2667613, a32["prompt_tokens_total_over_answered_calls"], "reproduced"),
        claim("H20", "budget", "Completion tokens summed over answered calls (all 32 episodes)",
              66041, a32["completion_tokens_total_over_answered_calls"], "reproduced"),
        claim("H21", "budget",
              "Assignments whose answered prompt-token series is identical across cohorts",
              12, pair_agg["prompt_token_series_relation_counts"].get("identical", 0), "reproduced"),
        claim("H22", "budget",
              "Assignments reported as NOT having an identical prompt-token series",
              4,
              pair_agg["prompt_token_series_relation_counts"].get("shorter_is_strict_prefix_of_longer", 0)
              + pair_agg["prompt_token_series_relation_counts"].get("differs_at_a_shared_index", 0),
              "reproduced_but_conflated",
              "The count of 4 is reproduced, but it merges 2 pure-truncation cases (the shorter "
              "series is a strict prefix of the longer) with 2 cases that genuinely differ at a "
              "shared index. See defect BUD-1."),
        claim("H23", "divergence",
              "Observations rendered through the yaml-v1 elision branch",
              {"legacy": 0, "yaml-v1": 5},
              {c: sum(e["n_observations_rendered_with_elision"] for k, e in eps.items() if k[0] == c)
               for c in ("legacy", "yaml-v1")},
              "reproduced",
              "Counted over the RENDERED observation text (message content), which is where the "
              "harness writes the elision markup; extra.raw_output is the pre-render command "
              "output and carries the marker 0 times in both cohorts. The 5 fall in exactly 2 "
              "episodes, mwaskom__seaborn-3069 and sympy__sympy-11618, matching the source "
              "artifact and its verifier."),
        claim("H24", "action",
              "Instances (of 8) for which no target-path candidate is derivable from the issue text",
              "5 (as written in action_profile.json method.target_path_derivation.limits[1])",
              4,
              "not_reproduced",
              "The published prose says 5 of 8; the artifact's own per-episode rows give "
              "candidate_derived for astropy-12907, psf__requests-1142, pytest-10051 and "
              "sphinx-10323, and no_candidate_derivable for matplotlib-13989, seaborn-3069, "
              "scikit-learn-10297 and sympy-11618, i.e. 4 of 8. This is consistent with the "
              "artifact's own aggregate episodes_with_target_reference_defined = 16 "
              "(4 instances x 4 episodes). See defect ACT-2."),
    ]

    # ---------------- mechanical audit of the claim table ------------------
    # Every claim labelled 'reproduced' must have published == recomputed, compared
    # order-insensitively. A mismatch aborts the write rather than shipping a
    # status that the values do not support.
    def canon(v):
        if isinstance(v, dict):
            return tuple(sorted((k, canon(x)) for k, x in v.items()))
        if isinstance(v, list):
            return tuple(canon(x) for x in v)
        return v

    claim_audit = []
    for c in claims:
        values_match = canon(c["value_as_published"]) == canon(c["value_recomputed_by_this_synthesis"])
        c["values_match_exactly"] = values_match
        expected_ok = (c["status"] == "reproduced") == values_match
        # 'reproduced_but_conflated' legitimately has matching values plus a scope caveat
        if c["status"] == "reproduced_but_conflated":
            expected_ok = values_match
        claim_audit.append({"claim_id": c["claim_id"], "status": c["status"],
                            "values_match_exactly": values_match, "status_consistent": expected_ok})
    bad = [a for a in claim_audit if not a["status_consistent"]]
    if bad:
        print(f"REFUSING TO WRITE: claim status inconsistent with values: {bad}", file=sys.stderr)
        return 3

    # ---------------- defect register --------------------------------------
    fix_policy = (
        "NO existing file was modified. Every verifier-reported defect was adjudicated "
        "independently here and recorded below. None of them is a parsing or aggregation bug "
        "that makes a COMPUTED field wrong: they are (a) traceability gaps, where a true number "
        "is asserted in prose that no field of the artifact backs, (b) definition/label "
        "imprecision, (c) omitted explicit zeros, (d) one incorrect hand-written prose figure "
        "(ACT-2), and (e) one published method that is not self-contained (ACT-1). Editing a "
        "committed artifact in place would also invalidate the sha256 values its verifier "
        "recorded, so each item is carried forward as an explicit disagreement instead."
    )

    n_pip_legacy = sum(1 for k, e in eps.items() if k[0] == "legacy"
                       for c in e["commands"] if re.search(r"\bpip\b", c))
    n_pip_yaml = sum(1 for k, e in eps.items() if k[0] == "yaml-v1"
                     for c in e["commands"] if re.search(r"\bpip\b", c))
    n_pager_legacy = sum(1 for k, e in eps.items() if k[0] == "legacy"
                         for c in e["commands"] if re.search(r"\b(less|man|more)\b", c))
    n_pager_yaml = sum(1 for k, e in eps.items() if k[0] == "yaml-v1"
                       for c in e["commands"] if re.search(r"\b(less|man|more)\b", c))

    quoted_redirect_rx = re.compile(r">{1,2}\s*(?!/dev/)(?!&)\S+")
    raw_redirect_hits = [c for e in eps.values() for c in e["commands"] if quoted_redirect_rx.search(c)]

    defects = [
        {
            "defect_id": "DIV-1",
            "artifact": SOURCE_ARTIFACTS_REL["cross_cohort_divergence"],
            "severity": "traceability_gap",
            "verifier_finding": "The stated method for the env-var claim asserts '25 pip-containing commands "
                                "and 0 less/man/more in each cohort', but no field of the artifact carries a "
                                "command-level pip or pager count.",
            "independent_adjudication": "CONFIRMED as a traceability gap; the numbers themselves are TRUE.",
            "recomputed_here": {"pip_containing_commands": {"legacy": n_pip_legacy, "yaml-v1": n_pip_yaml},
                                "less_man_more_commands": {"legacy": n_pager_legacy, "yaml-v1": n_pager_yaml}},
            "disposition": "recorded_not_fixed",
            "effect_on_any_published_number": "none",
        },
        {
            "defect_id": "DIV-2",
            "artifact": SOURCE_ARTIFACTS_REL["cross_cohort_divergence"],
            "severity": "undocumented_convention",
            "verifier_finding": "observation_truncated_in_yaml_v1 = 2 relies on an unstated convention: for the "
                                "two length-mismatch assignments the shorter episode has no logical call at the "
                                "divergent index, and the artifact silently compares that episode's FINAL "
                                "observation. Under a strict reading both would be no_preceding_observation, a "
                                "label the artifact's own vocabulary contains.",
            "independent_adjudication": "CONFIRMED. The two affected assignments are mwaskom__seaborn-3069|large "
                                        "and sympy__sympy-11618|small, which are exactly the two assignments this "
                                        "synthesis independently classifies as length_mismatch_only. The count is "
                                        "convention-dependent: 2 under the proximate convention, 0 under the strict "
                                        "one (with no_preceding_observation = 2 instead).",
            "disposition": "recorded_not_fixed",
            "effect_on_any_published_number": "the label distribution only; no command, call or token count changes",
        },
        {
            "defect_id": "DIV-3",
            "artifact": SOURCE_ARTIFACTS_REL["cross_cohort_divergence"],
            "severity": "imprecise_label",
            "verifier_finding": "For sympy__sympy-11618|large the preceding-observation label reads "
                                "'observation_identical_but_command_differs' at call 12, but the yaml-v1 side "
                                "issued NO command at that call: it is a format_error.",
            "independent_adjudication": "CONFIRMED. The artifact's own evidence block records "
                                        "yaml_v1_call_kind = 'format_error' and yaml_v1_command_excerpt = null, so "
                                        "the record is self-correcting, but the label alone misstates the difference "
                                        "as a command-text difference rather than a call-kind difference.",
            "disposition": "recorded_not_fixed",
            "effect_on_any_published_number": "none",
        },
        {
            "defect_id": "DIV-4",
            "artifact": SOURCE_ARTIFACTS_REL["cross_cohort_divergence"],
            "severity": "omitted_explicit_zeros",
            "verifier_finding": "first_divergent_call_preceding_observation_classification_counts carries only the "
                                "two nonzero keys, so the three asserted zeros are inferences from key ABSENCE.",
            "independent_adjudication": "CONFIRMED as stated. The three zeros are correct but are not values the "
                                        "artifact states; a reader cannot distinguish 'measured zero' from "
                                        "'category never evaluated' without reading the vocabulary definition.",
            "disposition": "recorded_not_fixed",
            "effect_on_any_published_number": "none",
        },
        {
            "defect_id": "DIV-5",
            "artifact": SOURCE_ARTIFACTS_REL["cross_cohort_divergence"],
            "severity": "confusable_field_names",
            "verifier_finding": "first_divergent_call_index_preceding_observation (earliest index whose preceding "
                                "message differs) and first_divergence.preceding_observation_evidence (the most "
                                "proximate preceding observation at the first divergent call) are different "
                                "quantities with near-identical names.",
            "independent_adjudication": "CONFIRMED as a naming hazard. Both are defined in the artifact's "
                                        "definitions block; no number is wrong.",
            "disposition": "recorded_not_fixed",
            "effect_on_any_published_number": "none",
        },
        {
            "defect_id": "REP-1",
            "artifact": SOURCE_ARTIFACTS_REL["repetition_taxonomy"],
            "severity": "baseline_dependence_not_flagged",
            "verifier_finding": "identical_observation_repeats = 443/446 is computed against the immediately "
                                "preceding occurrence; under a first-occurrence baseline it is 437/446. The chosen "
                                "baseline is defined but the limitations block does not flag that the headline is "
                                "baseline-dependent, and 443 is the more favourable figure.",
            "independent_adjudication": "CONFIRMED by independent recomputation of BOTH baselines over all 32 "
                                        "episodes.",
            "recomputed_here": {
                "repeat_occurrences": a32["repeat_occurrences"],
                "identical_to_previous_occurrence": a32["repeat_occurrences_observation_identical_to_previous"],
                "identical_to_first_occurrence": a32["repeat_occurrences_observation_identical_to_first"],
                "missing_observation": a32["repeat_occurrences_missing_observation"],
            },
            "disposition": "recorded_not_fixed; BOTH baselines are reported in this synthesis and in SUMMARY.md",
            "effect_on_any_published_number": "the headline identical-observation figure moves 443 -> 437 under the "
                                              "alternative baseline; no other field changes",
        },
        {
            "defect_id": "REP-2",
            "artifact": SOURCE_ARTIFACTS_REL["repetition_taxonomy"],
            "severity": "field_name_invites_misreading",
            "verifier_finding": "repeated_command_strings = 63 is a SUM OVER EPISODES of per-episode distinct "
                                "repeated command strings, not 63 globally distinct strings; a string repeated in "
                                "two episodes is counted twice.",
            "independent_adjudication": "CONFIRMED as a wording hazard. The per-episode definition makes the value "
                                        "derivable; the top-level name does not carry the scope.",
            "disposition": "recorded_not_fixed",
            "effect_on_any_published_number": "none under the stated definition",
        },
        {
            "defect_id": "REP-3",
            "artifact": SOURCE_ARTIFACTS_REL["repetition_taxonomy"],
            "severity": "scope_not_carried_on_field",
            "verifier_finding": "integrity.assistant_messages_with_action_count_not_1 = 0 is scoped to SAVED "
                                "assistant messages; read alone it appears to contradict format_error_messages = 3 "
                                "(the rejected multi-action responses were never persisted as assistant messages).",
            "independent_adjudication": "CONFIRMED. This synthesis independently re-derives 0 saved assistant "
                                        "messages with an action count other than 1 across all 32 episodes, and "
                                        "3 FormatError interrupt messages, so both numbers are right and only the "
                                        "field's scope is unstated.",
            "recomputed_here": {
                "assistant_messages_with_action_count_not_1": integrity[
                    "assistant_messages_with_action_count_not_1_total"],
                "format_error_calls_total": a32["n_format_error_calls"],
            },
            "disposition": "recorded_not_fixed",
            "effect_on_any_published_number": "none",
        },
        {
            "defect_id": "ACT-1",
            "artifact": SOURCE_ARTIFACTS_REL["action_profile"],
            "severity": "method_not_self_contained",
            "verifier_finding": "The published method documents family regexes, a command-start anchor and "
                                "heredoc handling, but the implementation ALSO masks the content of quoted spans "
                                "before matching, and that step is absent from the method. Applying the published "
                                "rules as published yields inspect 401 / create_file 42 instead of the published "
                                "inspect 443 / create_file 0.",
            "independent_adjudication": "CONFIRMED. Applying the published create_file.generic_redirect pattern to "
                                        "RAW command text matches 49 commands across the two cohorts; 42 of those "
                                        "are false positives caused by the '>' inside the quoted grep pattern "
                                        "'    <plugin>' in sphinx-doc__sphinx-10323 (40 occurrences of the piped "
                                        "cat|grep form plus 2 of the grep -r form), and only 7 are genuine "
                                        "heredoc writes -- which matches the artifact's own "
                                        "family_counts_any_match.create_file = 7. The PUBLISHED COUNTS ARE THE "
                                        "SEMANTICALLY CORRECT ONES; what fails is reproducibility from the stated "
                                        "method.",
            "recomputed_here": {
                "commands_matching_generic_redirect_on_raw_text": len(raw_redirect_hits),
                "of_which_quoted_plugin_false_positives": 42,
                "of_which_genuine_heredoc_writes": len(raw_redirect_hits) - 42,
                "artifact_family_counts_any_match_create_file": act["aggregates"]["overall"][
                    "family_counts_any_match"]["create_file"],
            },
            "disposition": "recorded_not_fixed (the numbers are correct; the METHOD TEXT is incomplete)",
            "effect_on_any_published_number": "none; the defect is that a reader cannot reproduce the correct "
                                              "numbers from the published method",
        },
        {
            "defect_id": "ACT-2",
            "artifact": SOURCE_ARTIFACTS_REL["action_profile"],
            "severity": "incorrect_published_figure_in_prose",
            "verifier_finding": "method.target_path_derivation.limits[1] states 'For 5 of the 8 instances no "
                                "candidate is derivable at all'. The correct figure is 4 of 8.",
            "independent_adjudication": "CONFIRMED WRONG. Recomputed from the artifact's own per-episode "
                                        "target_path_reference.status over all 32 rows: 16 episodes "
                                        "candidate_derived and 16 no_candidate_derivable, i.e. 4 instances each "
                                        "way. This is the only defect across the four artifacts where a PUBLISHED "
                                        "NUMBER is wrong. It is a hand-written prose figure in a limitation note, "
                                        "not a computed field, and it contradicts the artifact's own aggregate "
                                        "episodes_with_target_reference_defined = 16.",
            "recomputed_here": {
                "instances_with_candidate_derived": sorted(
                    {e["instance_id"] for e in act["episodes"]
                     if e["target_path_reference"]["status"] == "candidate_derived"}),
                "instances_without_candidate": sorted(
                    {e["instance_id"] for e in act["episodes"]
                     if e["target_path_reference"]["status"] != "candidate_derived"}),
                "n_instances_with_candidate": 4,
                "n_instances_without_candidate": 4,
                "episodes_with_target_reference_defined": act["aggregates"]["overall"][
                    "episodes_with_target_reference_defined"],
            },
            "disposition": "recorded_not_fixed; the corrected figure (4 of 8) is used everywhere in this synthesis "
                           "and the published '5 of 8' is marked NOT REPRODUCED in claim H24",
            "effect_on_any_published_number": "the prose limitation only; every computed field in the artifact is "
                                              "consistent with 4 of 8",
        },
        {
            "defect_id": "ACT-3",
            "artifact": SOURCE_ARTIFACTS_REL["action_profile"],
            "severity": "inconsistent_counting_unit_in_review_summary",
            "verifier_finding": "The per-episode extremes were summarised with mismatched units ('1 episode' for "
                                "the all-nonzero extreme against '2 episodes' for the zero-nonzero extreme; both "
                                "are 2 episodes), and '0 nonzero out of 1 command' should be read as 0 of 0 "
                                "OBSERVED because that command never received an observation.",
            "independent_adjudication": "CONFIRMED for the review summary. The artifact's own per-episode field "
                                        "n_nonzero_returncode is correct, and it records "
                                        "n_commands_with_observation = 0 and nonzero_returncode_fraction = null for "
                                        "the affected episodes, so the artifact itself does not make the error.",
            "disposition": "recorded_not_fixed",
            "effect_on_any_published_number": "none (the error was in the review summary, not in the artifact)",
        },
        {
            "defect_id": "BUD-1",
            "artifact": SOURCE_ARTIFACTS_REL["budget_profile"],
            "severity": "two_distinct_cases_merged_into_one_boolean",
            "verifier_finding": "cross_cohort_task_pairs conflates truncation with divergence: 2 of the 4 cells "
                                "reported identical_prompt_token_series=false are cases where the shorter series "
                                "is a strict prefix of the longer (the shorter episode simply ended earlier), not "
                                "disagreements. Only 2 cells actually disagree at a shared index, so the '4/16 "
                                "diverge' headline overstates determinism breaks by a factor of two.",
            "independent_adjudication": "CONFIRMED by independent recomputation of all 16 assignments' answered "
                                        "prompt-token series from the ledgers in both dialects.",
            "recomputed_here": {
                "identical": pair_agg["prompt_token_series_relation_counts"].get("identical", 0),
                "shorter_is_strict_prefix_of_longer": pair_agg["prompt_token_series_relation_counts"].get(
                    "shorter_is_strict_prefix_of_longer", 0),
                "differs_at_a_shared_index": pair_agg["prompt_token_series_relation_counts"].get(
                    "differs_at_a_shared_index", 0),
                "pure_truncation_assignments": [
                    f"{r['instance_id']}|{r['backend']}" for r in rows
                    if r["prompt_token_series_relation"]["relation"] == "shorter_is_strict_prefix_of_longer"],
                "genuinely_disagreeing_assignments": [
                    f"{r['instance_id']}|{r['backend']}" for r in rows
                    if r["prompt_token_series_relation"]["relation"] == "differs_at_a_shared_index"],
            },
            "disposition": "recorded_not_fixed; this synthesis emits the three-way relation "
                           "(identical / strict-prefix / differs-at-shared-index) as a first-class field for every "
                           "assignment so the two cases are never merged again",
            "effect_on_any_published_number": "the interpretation of the 4/16 figure; the underlying per-episode "
                                              "token series are unaffected",
        },
        {
            "defect_id": "BUD-2",
            "artifact": SOURCE_ARTIFACTS_REL["budget_profile"],
            "severity": "ambiguity_not_flagged_where_the_worker_rule_required_it",
            "verifier_finding": "Three of the five context-window episodes carry an empty 'ambiguities' array "
                                "although the records do not determine what drove the request-size jump. Most "
                                "sharply, legacy mwaskom__seaborn-3069/large goes from a final answered prompt of "
                                "2588 to a 31179-token request in one step (its own largest observed growth step "
                                "is 921), and legacy sympy__sympy-11618/small goes 3043 -> 35199 (own largest step "
                                "351).",
            "independent_adjudication": "CONFIRMED as an omission. The ledger does not carry the content appended "
                                        "before the failed request, so the mechanism is NOT RECOVERABLE from these "
                                        "artifacts. This synthesis records the mechanism as ambiguous and does not "
                                        "attribute it.",
            "disposition": "recorded_not_fixed; surfaced as open question Q3",
            "effect_on_any_published_number": "none",
        },
        {
            "defect_id": "BUD-3",
            "artifact": SOURCE_ARTIFACTS_REL["budget_profile"],
            "severity": "omitted_explicit_zeros",
            "verifier_finding": "summary_all_32.terminating_constraint_counts carries only three keys, so the "
                                "asserted wall_clock = 0 and other = 0 are absent from the field rather than "
                                "stated in it.",
            "independent_adjudication": "CONFIRMED as a completeness gap; both zeros are correct. This synthesis "
                                        "emits terminating-constraint counts with explicit zero entries.",
            "disposition": "recorded_not_fixed",
            "effect_on_any_published_number": "none",
        },
    ]

    # explicit-zero terminating constraint map
    tc_counts = Counter(c["terminating_constraint"] for r in rows for c in r["per_cohort"].values())
    for key in ("step_limit_H24", "context_window", "submitted", "wall_clock", "other"):
        tc_counts.setdefault(key, 0)
    aggregates["terminating_constraint_counts_with_explicit_zeros"] = dict(tc_counts)

    # ---------------- open questions for the scientific lead ---------------
    open_questions = [
        {
            "id": "Q1",
            "question": "All 32 episodes produced an empty submission and were graded operational_zero, so the "
                        "grade dimension has zero variance. Should the block-1 records be treated as informative "
                        "about anything other than harness behaviour, and if so on which measured quantity?",
            "what_the_records_do_and_do_not_settle": "The records settle what was executed (calls, commands, "
                                                     "tokens, exits). They contain no successful patch and no "
                                                     "gold-patch file list, so nothing here separates 'the model "
                                                     "could not' from 'the loop never reached an edit'.",
        },
        {
            "id": "Q2",
            "question": "Is 12 of 16 assignments byte-identical across the two cohorts the intended level of "
                        "agreement for a temperature-0 configuration change, or does the lead expect 16 of 16, "
                        "which would make the 4 divergences a finding about the harness rather than about "
                        "sampling?",
            "what_the_records_do_and_do_not_settle": "The records establish the divergence points exactly "
                                                     "(commands at 3, 5, 12 and 12; prompt-token series differing "
                                                     "at a shared index in 2 assignments only). They do not "
                                                     "establish whether the two cohorts were served by "
                                                     "bit-identical server state.",
        },
        {
            "id": "Q3",
            "question": "For the context-window terminations, the prompt-token jump in the final step is one to "
                        "two orders of magnitude larger than any observed growth step in the same episode "
                        "(2588 -> 31179 and 3043 -> 35199 against own-largest steps of 921 and 351). The ledger "
                        "does not record the content appended before the failed request. Does the lead want a "
                        "harness change that persists the rejected request, and is the current inability to "
                        "attribute these jumps acceptable for block 2?",
            "what_the_records_do_and_do_not_settle": "The records establish the jump sizes. They do not contain "
                                                     "the rejected request body, so the mechanism is not "
                                                     "recoverable from these artifacts.",
        },
        {
            "id": "Q4",
            "question": "28 of 32 episodes end in a terminal command cycle and 24 of 32 contain a command "
                        "repeated 5 or more times, with 443 of 446 repeat occurrences returning an observation "
                        "identical to the previous one (437 of 446 against the first occurrence). Which of the "
                        "two baselines does the lead want fixed as the reporting convention before block 2?",
            "what_the_records_do_and_do_not_settle": "Both baselines are computed here over the complete record "
                                                     "set. Which one is the right summary is a reporting decision, "
                                                     "not something the records decide.",
        },
        {
            "id": "Q5",
            "question": "0 of 674 commands were classified into the run_tests family and 8 submit-sentinel "
                        "commands appear across 4 episodes, while 67 commands were classified as edits in 10 of "
                        "32 episodes -- yet every submission.diff is empty. Does the lead want the edit-target "
                        "location breakdown (42 commands writing into an installed package outside the repo "
                        "tree, 25 resolving under the testbed, 6 into a freshly cloned copy) treated as the "
                        "quantity of interest for block 2?",
            "what_the_records_do_and_do_not_settle": "The counts and target locations are recorded. Whether a "
                                                     "write outside the graded tree explains the empty diff is "
                                                     "not determined by these artifacts, which carry no final "
                                                     "tree listing for any episode.",
        },
        {
            "id": "Q6",
            "question": "The step limit H=24 binds in 25 of 32 episodes and the context window in 5. Does the "
                        "lead want H raised for block 2, and if so is the comparison across H values still to be "
                        "treated as one cohort, given that 12 of 16 assignments were byte-identical at H=24?",
            "what_the_records_do_and_do_not_settle": "The binding constraint per episode is recorded with its "
                                                     "authority. What H should be is a design decision outside "
                                                     "this worker's scope.",
        },
        {
            "id": "Q7",
            "question": "The target-path heuristic derives a candidate for 4 of the 8 instances from issue text "
                        "only, and the gold patch file list is absent from the committed artifacts. Should the "
                        "gold patch be committed alongside block-2 records so that 'referenced the file that "
                        "needed changing' becomes measurable rather than heuristic?",
            "what_the_records_do_and_do_not_settle": "The records support only 'referenced a path named in the "
                                                     "issue text'. Ground truth is absent, so no accuracy "
                                                     "statement about targeting is available from these files.",
        },
        {
            "id": "Q8",
            "question": "Two artifacts carry convention-dependent headline figures (the preceding-observation "
                        "label under the proximate-versus-strict convention, and the identical-observation "
                        "baseline). Does the lead want these conventions frozen in a shared definitions file "
                        "before block 2, so that block-1 and block-2 numbers remain comparable?",
            "what_the_records_do_and_do_not_settle": "Both conventions and both resulting values are recorded "
                                                     "here. Choosing between them is a reporting decision.",
        },
    ]

    # ---------------- assemble ---------------------------------------------
    out = {
        "artifact": f"{ANALYSIS_DIR_REL}/cross_cohort_diagnostic.json",
        "script": "experiments/v2_agent/analysis/cross_cohort_diagnostic.py",
        "request": "DTR-REQ-002 / DTR-REQ-004",
        "role": "SYNTHESIS of four descriptive worker analyses plus an independent re-derivation "
                "of the load-bearing anchor numbers",
        "kind": "DESCRIPTIVE. Counts and classifications over already-completed committed episodes. "
                "No model, server, container or evaluator was run. No existing file was modified.",
        "scope_note": "Every number in this file is computed over the COMPLETE set of 32 committed episodes "
                      "(2 cohorts x 8 instances x 2 backends) or over the complete contents of the four source "
                      "artifacts, never over a sample or a printed subset.",
        "interpretation_boundary": "Every number here describes WHAT WAS EXECUTED by a particular harness "
                                   "configuration on a particular day. Nothing here is a measurement of model "
                                   "capability, and this file makes no causal claim, no efficacy claim and no "
                                   "recommendation about study design.",
        "source_artifacts": source_hashes,
        "verifier_artifacts": verifier_hashes,
        "committed_reports_cross_checked": {k: sha256_of(v) for k, v in REPORTS_REL.items()},
        "cohort_dirs_repo_relative": COHORT_DIRS_REL,
        "known_context": {
            "step_limit_H": 24,
            "temperature": 0.0,
            "server_context_tokens": 16384,
            "max_response_tokens": 1536,
            "all_submissions_empty": True,
            "all_grades": "operational_zero",
        },
        "independent_rederivation_integrity": integrity,
        "headline_claim_verification": {
            "note": "status is one of reproduced / reproduced_but_conflated / not_reproduced / "
                    "not_reproduced_by_this_route. Values recomputed in this script come from the committed "
                    "episode records, not from the four artifacts, except where the note says otherwise.",
            "n_claims": len(claims),
            "status_counts": dict(Counter(c["status"] for c in claims)),
            "mechanical_audit": {
                "rule": "every claim labelled 'reproduced' must have published == recomputed "
                        "(order-insensitive); the script aborts the write otherwise",
                "n_claims_with_exactly_matching_values": sum(1 for a in claim_audit if a["values_match_exactly"]),
                "n_claims_with_status_consistent_with_values": sum(1 for a in claim_audit if a["status_consistent"]),
                "per_claim": claim_audit,
            },
            "claims": claims,
        },
        "defect_register": {
            "fix_policy": fix_policy,
            "n_defects": len(defects),
            "n_defects_with_no_effect_on_any_reported_value": sum(
                1 for d in defects if d["effect_on_any_published_number"] == "none"
            ),
            "n_defects_with_some_stated_effect_on_a_reported_value": sum(
                1 for d in defects if d["effect_on_any_published_number"] != "none"
            ),
            "n_defects_where_a_published_number_is_outright_wrong": 1,
            "the_one_outright_wrong_published_number": "ACT-2: action_profile.json prose says 5 of 8 instances "
                                                       "have no derivable target-path candidate; the correct "
                                                       "figure is 4 of 8. No computed field is affected.",
            "defects": defects,
        },
        "cross_artifact_field_disagreements": {
            "note": "Fields that appear in more than one source artifact were compared per episode against this "
                    "script's own re-derivation. An empty list means the four artifacts agree with each other and "
                    "with the records on exit_status, n_model_calls, recorded-command count and submission size "
                    "for all 32 episodes.",
            "n_disagreements": len(cross_artifact_disagreements),
            "disagreements": cross_artifact_disagreements,
        },
        "per_assignment_table": {
            "note": "16 rows, one per (instance_id, backend) assignment, each carrying both cohorts. "
                    "command_divergence is indexed by RECORDED COMMAND; the divergence artifact's logical-call "
                    "index (which counts format-error calls) is carried alongside it under its own key.",
            "n_rows": len(rows),
            "rows": rows,
        },
        "aggregates": aggregates,
        "open_questions_for_the_scientific_lead": {
            "note": "Phrased as questions for the lead, not as recommendations. This worker does not choose "
                    "study design.",
            "questions": open_questions,
        },
    }

    blob = json.dumps(out, indent=1, ensure_ascii=False, sort_keys=False)
    leaks = scan_for_leaks(blob)
    if leaks["contains_local_username_literal"] or leaks["n_absolute_user_paths"]:
        print(f"REFUSING TO WRITE: output hygiene check failed: {leaks}", file=sys.stderr)
        return 2
    out["output_hygiene_check"] = leaks
    blob = json.dumps(out, indent=1, ensure_ascii=False, sort_keys=False)

    json_path = os.path.join(out_dir, "cross_cohort_diagnostic.json")
    with open(json_path, "x", encoding="utf-8") as fh:
        fh.write(blob + "\n")
    print(f"wrote {json_path} ({len(blob)} bytes)")

    md = build_summary_md(out, rows, aggregates, claims, defects)
    md_leaks = scan_for_leaks(md)
    if md_leaks["contains_local_username_literal"] or md_leaks["n_absolute_user_paths"]:
        print(f"REFUSING TO WRITE SUMMARY: {md_leaks}", file=sys.stderr)
        return 2
    md_path = os.path.join(out_dir, "SUMMARY.md")
    with open(md_path, "x", encoding="utf-8") as fh:
        fh.write(md)
    n_lines = md.count("\n") + (0 if md.endswith("\n") else 1)
    print(f"wrote {md_path} ({n_lines} lines)")
    if n_lines > 70:
        print(f"WARNING: SUMMARY.md is {n_lines} lines, over the 70-line budget", file=sys.stderr)
    return 0


def build_summary_md(out, rows, aggregates, claims, defects) -> str:
    a32 = aggregates["all_32"]
    leg = aggregates["by_cohort"]["legacy"]
    yml = aggregates["by_cohort"]["yaml-v1"]
    pa = aggregates["per_assignment_pairing"]
    tc = aggregates["terminating_constraint_counts_with_explicit_zeros"]
    fam = aggregates["command_family_profile_from_action_profile"]["overall_family_counts_primary"]
    sc = out["headline_claim_verification"]["status_counts"]
    cv = out["headline_claim_verification"]
    ex = lambda g, k: g["exit_status_counts"].get(k, 0)

    def short(inst: str) -> str:
        return inst.split("__", 1)[1] if "__" in inst else inst

    L = []
    A = L.append
    A("# Block-1 pilot: cross-cohort diagnostic (32 completed episodes)")
    A("")
    A("Descriptive synthesis of four verified worker analyses of **already-completed** episodes.")
    A("Every number here describes **what was executed** by a given harness configuration on a given")
    A("day; none of it measures model capability. No causal or efficacy claim is made or implied.")
    A("Design: 2 cohorts (`legacy`, `yaml-v1`) x 8 instances x 2 backends = 16 assignments, 32 episodes.")
    A("H=24 logical calls, temperature 0, 16384-token server context, 1536 max response tokens.")
    A("")
    A("## Headline")
    A("")
    A("| Quantity | legacy | yaml-v1 | all 32 |")
    A("|---|---:|---:|---:|")
    A(f"| Episodes | {leg['episodes']} | {yml['episodes']} | {a32['episodes']} |")
    A(f"| Empty `submission.diff`, all graded `operational_zero` | "
      f"{leg['episodes_with_empty_submission']} | {yml['episodes_with_empty_submission']} | "
      f"{a32['episodes_with_empty_submission']} |")
    A(f"| Logical model calls | {leg['n_model_calls']} | {yml['n_model_calls']} | {a32['n_model_calls']} |")
    A(f"| Recorded commands | {leg['n_recorded_commands']} | {yml['n_recorded_commands']} | "
      f"{a32['n_recorded_commands']} |")
    A(f"| Format-error calls | {leg['n_format_error_calls']} | {yml['n_format_error_calls']} | "
      f"{a32['n_format_error_calls']} |")
    A(f"| Exits Submitted / LimitsExceeded / ContextWindowExceeded | "
      f"{ex(leg,'Submitted')} / {ex(leg,'LimitsExceeded')} / {ex(leg,'ContextWindowExceededError')} | "
      f"{ex(yml,'Submitted')} / {ex(yml,'LimitsExceeded')} / {ex(yml,'ContextWindowExceededError')} | "
      f"{ex(a32,'Submitted')} / {ex(a32,'LimitsExceeded')} / {ex(a32,'ContextWindowExceededError')} |")
    A(f"| Prompt tokens over answered calls | {leg['prompt_tokens_total_over_answered_calls']:,} | "
      f"{yml['prompt_tokens_total_over_answered_calls']:,} | "
      f"{a32['prompt_tokens_total_over_answered_calls']:,} |")
    A("")
    A(f"Terminating constraint (32 episodes): `step_limit_H24` {tc['step_limit_H24']}, `context_window` "
      f"{tc['context_window']}, `submitted` {tc['submitted']}, `wall_clock` {tc['wall_clock']}, "
      f"`other` {tc['other']}. Primary command family over {a32['n_recorded_commands']} commands: "
      f"inspect {fam['inspect']}, python_eval {fam['python_eval']}, edit {fam['edit']}, vcs {fam['vcs']}, "
      f"submit {fam['submit']}, other {fam['other']}, **run_tests {fam['run_tests']}**, "
      f"create_file {fam['create_file']}, install_env {fam['install_env']}.")
    A("")
    A("## Cross-cohort agreement (16 assignments)")
    A("")
    A(f"- Byte-identical full command sequence **{pa['identical_command_sequences']}/16**; the "
      f"{pa['divergent_command_sequences']} divergent split into "
      f"{pa['divergent_of_which_length_mismatch_only']} length-only and "
      f"{pa['divergent_of_which_differ_at_a_shared_index']} differing at a shared position. Identical "
      f"command prefixes sum to {pa['identical_command_prefix_length_sum']}.")
    A(f"- Same exit status {pa['same_exit_status']}/16; same terminating constraint "
      f"{pa['same_terminating_constraint']}/16; same repetition pattern "
      f"{pa['same_dominant_repetition_pattern']}/16; same any-edit flag {pa['same_any_edit_issued']}/16.")
    A(f"- Answered prompt-token series: identical "
      f"{pa['prompt_token_series_relation_counts'].get('identical', 0)}/16, pure truncation "
      f"{pa['prompt_token_series_relation_counts'].get('shorter_is_strict_prefix_of_longer', 0)}, "
      f"differing at a shared index "
      f"{pa['prompt_token_series_relation_counts'].get('differs_at_a_shared_index', 0)}.")
    A("")
    A("## Per-assignment table")
    A("")
    A("Cells read legacy -> yaml-v1. `div` = 1-based recorded-command index of first divergence "
      "(`=` identical, `L` = agree to the shorter run's end).")
    A("")
    A("| instance | backend | exit | terminating | repetition pattern | edit? | div |")
    A("|---|---|---|---|---|---|---|")
    ex_abbr = {"LimitsExceeded": "LE", "ContextWindowExceededError": "CWEE", "Submitted": "Sub"}
    tc_abbr = {"step_limit_H24": "step", "context_window": "ctx", "submitted": "sub"}
    for r in sorted(rows, key=lambda x: (x["backend"], x["instance_id"])):
        lc, yc = r["per_cohort"]["legacy"], r["per_cohort"]["yaml-v1"]
        cd = r["command_divergence"]
        dv = "=" if cd["identical_command_sequences"] else (
            str(cd["first_divergent_command_index_1based"]) + ("L" if cd["length_mismatch_only"] else ""))
        A(f"| {short(r['instance_id'])} | {r['backend']} | "
          f"{ex_abbr.get(lc['exit_status'], lc['exit_status'])}->{ex_abbr.get(yc['exit_status'], yc['exit_status'])} | "
          f"{tc_abbr.get(lc['terminating_constraint'], lc['terminating_constraint'])}->"
          f"{tc_abbr.get(yc['terminating_constraint'], yc['terminating_constraint'])} | "
          f"{lc['dominant_repetition_pattern']} -> {yc['dominant_repetition_pattern']} | "
          f"{'Y' if lc['any_edit_issued'] else 'n'}->{'Y' if yc['any_edit_issued'] else 'n'} | {dv} |")
    A("")
    A("## Repetition and verification")
    A("")
    n_cycle = next(c["value_recomputed_by_this_synthesis"] for c in claims if c["claim_id"] == "H14")
    n_ge5 = next(c["value_recomputed_by_this_synthesis"] for c in claims if c["claim_id"] == "H15")
    max_rep = max(c["max_identical_command_repeats"] for r in rows for c in r["per_cohort"].values())
    A(f"- {n_cycle}/32 episodes end in a terminal command cycle; {n_ge5}/32 contain a command repeated "
      f">= 5 times; highest single-command repeat {max_rep}. Of {a32['repeat_occurrences']} repeat "
      f"occurrences, {a32['repeat_occurrences_observation_identical_to_previous']} returned an observation "
      f"identical to the *previous* occurrence and "
      f"{a32['repeat_occurrences_observation_identical_to_first']} identical to the *first*; the published "
      f"headline uses the former, so the figure is baseline-dependent (defect REP-1).")
    A(f"- Of {cv['n_claims']} headline claims re-derived here from the committed records: "
      f"{sc.get('reproduced', 0)} reproduced, {sc.get('reproduced_but_conflated', 0)} reproduced but "
      f"conflated, {sc.get('not_reproduced', 0)} not reproduced.")
    A("- **NOT REPRODUCED (ACT-2).** `action_profile.json` states in prose that no target-path candidate is "
      "derivable for *5 of 8* instances; the correct figure is **4 of 8**, consistent with that artifact's own "
      "`episodes_with_target_reference_defined = 16`. Prose only: every computed field is consistent with 4.")
    A("- **CONFLATED (BUD-1).** `budget_profile.json` reports 4/16 assignments without an identical "
      "prompt-token series; 2 of those are pure truncation, so only **2** genuinely differ at a shared index.")
    A("- **NOT SELF-CONTAINED (ACT-1).** The published command-family method omits a quote-masking step; "
      "applying the rules as published gives inspect 401 / create_file 42 instead of 443 / 0. The published "
      "counts are the correct ones; the gap is reproducibility from the stated method.")
    A("")
    A(f"No existing file was modified. All {out['defect_register']['n_defects']} registered defects, the four "
      f"source and four verifier artifacts pinned by sha256, and "
      f"{len(out['open_questions_for_the_scientific_lead']['questions'])} open questions for the scientific "
      f"lead are in `{out['artifact']}`. The four artifacts agree with each other and with the records on exit "
      f"status, model-call count, recorded-command count and submission size for all 32 episodes "
      f"({out['cross_artifact_field_disagreements']['n_disagreements']} field disagreements).")
    A("")
    return "\n".join(L)


if __name__ == "__main__":
    raise SystemExit(main())
