"""DESCRIPTIVE cross-cohort divergence analysis for the two REQ-002 block-1 pilot cohorts.

Read-only over committed artifacts. Runs no model, server, container or evaluator.

Pairs each of the 16 assignments (instance_id, backend) between
  legacy  : results/v2_agent/pilot_20260922/
  yaml-v1 : results/v2_agent/pilot_20260922_yaml_v1/
and reports, per pair, where the two episodes first diverge in (a) issued command
text and (b) the observation text that preceded that call, plus a classification of
the most proximate preceding-observation difference.

Worker scope: COUNTS and CLASSIFICATIONS only. No causal or efficacy claims.

Model-call reconstruction (mini-swe-agent 04d809c, trajectory_format mini-swe-agent-1.1):
  - An "action" call appends one assistant message (extra.actions == [{command}]) and,
    when the action executed, one user observation message (extra.returncode present).
  - A "format_error" call appends NO assistant message; DefaultAgent.run() adds only
    FormatError.messages, i.e. the single user message carrying
    extra.interrupt_type == "FormatError". It still consumes one logical model call.
  Both kinds are therefore counted in the logical call index, in message order.

Template markup that lives in trajectory info.config (e.g. <output_head>) is never read
here; only message CONTENT and message extra fields are inspected.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
COHORTS = {
    "legacy": "results/v2_agent/pilot_20260922",
    "yaml_v1": "results/v2_agent/pilot_20260922_yaml_v1",
}
OUT_REL = "results/v2_agent/analysis_20260922/cross_cohort_divergence.json"
SCRIPT_REL = "experiments/v2_agent/analysis/cross_cohort_divergence.py"

EXCERPT = 200

# Markers emitted only by the yaml-v1 pinned observation_template's >=10000-char branch.
TRUNCATION_MARKERS = (
    "The output of your last command was too long.",
    "<output_head>",
    "<elided_chars>",
    "characters elided",
    "<output_tail>",
)
# Artifacts that the pinned environment env vars (LESS/PAGER/MANPAGER/PIP_PROGRESS_BAR/
# TQDM_DISABLE) would suppress or alter if they were present in a command's output.
ENV_VAR_ARTIFACTS = {
    "carriage_return": "\r",
    "ansi_escape": "\x1b[",
    "tqdm_block_glyph": "█",
    "tqdm_rate_suffix": "it/s]",
    "tqdm_bar_separator": "%|",
    "pip_downloading_line": "Downloading ",
    "pip_eta": "eta 0:",
}
CLOCK_RE = re.compile(r"\d{2}:\d{2}")


def parse_run_id(run_id: str) -> dict:
    """instance_id itself contains '__'; parse from the END, never by index."""
    parts = run_id.split("__")
    if len(parts) < 4:
        raise ValueError("unparseable run_id: %s" % run_id)
    return {
        "run_id": run_id,
        "timestamp_segment": parts[-1],
        "binding": parts[-2],
        "backend": parts[-3],
        "instance_id": "__".join(parts[:-3]),
    }


def message_kind(index: int, msg: dict) -> str:
    extra = msg.get("extra") or {}
    role = msg.get("role")
    if role == "system":
        return "system"
    if role == "assistant":
        return "assistant"
    if role == "exit":
        return "exit"
    if role == "user":
        if index == 1:
            return "task_prompt"
        if "returncode" in extra:
            return "observation"
        if extra.get("interrupt_type") == "FormatError":
            return "format_error"
        return "other_user"
    return "other"


def build_calls(messages: list) -> tuple[list, list]:
    """Return (calls, anomalies). calls[k] is logical model call k+1."""
    calls: list = []
    anomalies: list = []
    i = 0
    n = len(messages)
    while i < n:
        msg = messages[i]
        kind = message_kind(i, msg)
        if kind in ("system", "task_prompt", "exit"):
            i += 1
            continue
        if kind == "assistant":
            actions = (msg.get("extra") or {}).get("actions") or []
            if len(actions) != 1:
                anomalies.append("assistant message %d carries %d actions" % (i, len(actions)))
            command = actions[0]["command"] if len(actions) == 1 else None
            response = None
            nxt = messages[i + 1] if i + 1 < n else None
            if nxt is not None and message_kind(i + 1, nxt) == "observation":
                response = nxt
                i += 2
            else:
                i += 1
            calls.append(
                {
                    "kind": "action",
                    "command": command,
                    "response_kind": "observation" if response is not None else "none",
                    "response_content": None if response is None else response["content"],
                    "response_raw_output": None
                    if response is None
                    else ((response.get("extra") or {}).get("raw_output") or ""),
                    "response_returncode": None
                    if response is None
                    else (response.get("extra") or {}).get("returncode"),
                }
            )
            continue
        if kind == "format_error":
            calls.append(
                {
                    "kind": "format_error",
                    "command": None,
                    "response_kind": "format_error",
                    "response_content": msg["content"],
                    "response_raw_output": None,
                    "response_returncode": None,
                }
            )
            i += 1
            continue
        anomalies.append("unexpected message %d of kind %s" % (i, kind))
        i += 1
    for idx, call in enumerate(calls, start=1):
        call["call_index"] = idx
    return calls, anomalies


def load_episode(cohort_dir: Path, run_dir: Path) -> dict:
    ident = parse_run_id(run_dir.name)
    traj = json.loads((run_dir / "trajectory.json").read_text())
    episode = json.loads((run_dir / "episode.json").read_text())
    messages = traj.get("messages", [])
    calls, anomalies = build_calls(messages)
    system_prompt = messages[0]["content"] if messages and messages[0].get("role") == "system" else None
    task_prompt = messages[1]["content"] if len(messages) > 1 and message_kind(1, messages[1]) == "task_prompt" else None
    exits = [m for m in messages if m.get("role") == "exit"]
    grade_path = run_dir / "grade.json"
    grade = json.loads(grade_path.read_text()) if grade_path.exists() else None
    submission = (run_dir / "submission.diff").read_bytes() if (run_dir / "submission.diff").exists() else b""
    return {
        **ident,
        "run_dir_repo_relative": str(run_dir.relative_to(ROOT)),
        "exit_status": episode.get("exit_status"),
        "n_model_calls_recorded": episode.get("n_model_calls"),
        "n_calls_reconstructed": len(calls),
        "n_action_calls": sum(1 for c in calls if c["kind"] == "action"),
        "n_format_error_calls": sum(1 for c in calls if c["kind"] == "format_error"),
        "submission_bytes": len(submission),
        "grade_label": None if grade is None else grade.get("classification"),
        "system_prompt": system_prompt,
        "task_prompt": task_prompt,
        "exit_content": exits[0]["content"] if exits else None,
        "calls": calls,
        "reconstruction_anomalies": anomalies,
    }


def preceding_message(episode: dict, call_index: int) -> dict:
    """The message immediately preceding logical call `call_index` (1-based)."""
    if call_index <= 1:
        return {"kind": "task_prompt", "content": episode["task_prompt"], "raw_output": None}
    prev = episode["calls"][call_index - 2] if call_index - 2 < len(episode["calls"]) else None
    if prev is None:
        return {"kind": "absent", "content": None, "raw_output": None}
    return {
        "kind": prev["response_kind"],
        "content": prev["response_content"],
        "raw_output": prev["response_raw_output"],
    }


def excerpt(text, limit: int = EXCERPT):
    if text is None:
        return None
    return text[:limit]


def first_char_difference(a: str, b: str):
    limit = min(len(a), len(b))
    for i in range(limit):
        if a[i] != b[i]:
            return i
    return None if len(a) == len(b) else limit


def window(text: str, at: int, before: int = 60, after: int = 140) -> str:
    return text[max(0, at - before) : at + after]


def line_diff_pairs(a: str, b: str):
    la, lb = a.splitlines(), b.splitlines()
    removed = [line for line in la if line not in set(lb)]
    added = [line for line in lb if line not in set(la)]
    return removed, added


def clock_artifact_only(a: str, b: str) -> dict:
    """True when every differing line becomes identical after blanking HH:MM fields."""
    removed, added = line_diff_pairs(a, b)
    if not removed or len(removed) != len(added):
        return {"clock_artifact_only": False, "differing_line_count": max(len(removed), len(added)),
                "example_legacy_line": excerpt(removed[0]) if removed else None,
                "example_yaml_v1_line": excerpt(added[0]) if added else None}
    for x, y in zip(removed, added):
        if CLOCK_RE.sub("<TIME>", x) != CLOCK_RE.sub("<TIME>", y):
            return {"clock_artifact_only": False, "differing_line_count": len(removed),
                    "example_legacy_line": excerpt(x), "example_yaml_v1_line": excerpt(y)}
    return {"clock_artifact_only": True, "differing_line_count": len(removed),
            "example_legacy_line": excerpt(removed[0]), "example_yaml_v1_line": excerpt(added[0])}


def truncation_evidence(text):
    if text is None:
        return []
    return [m for m in TRUNCATION_MARKERS if m in text]


def env_var_evidence(a, b):
    found = []
    for name, token in ENV_VAR_ARTIFACTS.items():
        in_a = token in (a or "")
        in_b = token in (b or "")
        if in_a != in_b:
            found.append({"artifact": name, "present_in_legacy": in_a, "present_in_yaml_v1": in_b})
    return found


def classify_preceding(prec_a: dict, prec_b: dict) -> dict:
    """Classify the most proximate difference in the preceding observation."""
    ka, kb = prec_a["kind"], prec_b["kind"]
    if ka != "observation" or kb != "observation":
        return {
            "classification": "no_preceding_observation",
            "evidence": {
                "legacy_preceding_message_kind": ka,
                "yaml_v1_preceding_message_kind": kb,
                "legacy_excerpt": excerpt(prec_a["content"]),
                "yaml_v1_excerpt": excerpt(prec_b["content"]),
            },
        }
    ca, cb = prec_a["content"], prec_b["content"]
    if ca == cb:
        return {
            "classification": "observation_identical_but_command_differs",
            "evidence": {
                "rendered_observation_identical": True,
                "raw_output_identical": prec_a["raw_output"] == prec_b["raw_output"],
                "rendered_length": len(ca),
                "shared_excerpt": excerpt(ca),
            },
        }
    trunc_a, trunc_b = truncation_evidence(ca), truncation_evidence(cb)
    at = first_char_difference(ca, cb)
    base = {
        "rendered_observation_identical": False,
        "raw_output_identical": prec_a["raw_output"] == prec_b["raw_output"],
        "legacy_rendered_chars": len(ca),
        "yaml_v1_rendered_chars": len(cb),
        "legacy_raw_output_chars": len(prec_a["raw_output"] or ""),
        "yaml_v1_raw_output_chars": len(prec_b["raw_output"] or ""),
        "first_differing_char_index": at,
        "legacy_excerpt_at_difference": excerpt(window(ca, at or 0)),
        "yaml_v1_excerpt_at_difference": excerpt(window(cb, at or 0)),
    }
    if trunc_b and not trunc_a:
        base["yaml_v1_truncation_markers_present"] = trunc_b
        base["legacy_truncation_markers_present"] = trunc_a
        return {"classification": "observation_truncated_in_yaml_v1", "evidence": base}
    env = env_var_evidence(prec_a["raw_output"], prec_b["raw_output"])
    if env:
        base["env_var_artifacts"] = env
        return {"classification": "observation_text_differs_env_vars", "evidence": base}
    base.update(clock_artifact_only(ca, cb))
    base["ambiguity_note"] = (
        "Observations differ but the difference matches none of the supported mechanisms "
        "(no yaml-v1 truncation markers, no progress-bar/pager artifact present on exactly one side). "
        "Mechanism not determined from the artifacts."
    )
    if trunc_a and not trunc_b:
        base["unexpected"] = "truncation markers present on the legacy side only"
    return {"classification": "unclassified", "evidence": base}


def compare_pair(inst: str, backend: str, a: dict, b: dict) -> dict:
    calls_a, calls_b = a["calls"], b["calls"]
    cmds_a = [c["command"] for c in calls_a if c["kind"] == "action"]
    cmds_b = [c["command"] for c in calls_b if c["kind"] == "action"]
    seq_a = [(c["kind"], c["command"]) for c in calls_a]
    seq_b = [(c["kind"], c["command"]) for c in calls_b]
    n = min(len(calls_a), len(calls_b))

    first_cmd_diff = None
    length_mismatch_only = False
    for i in range(n):
        if seq_a[i] != seq_b[i]:
            first_cmd_diff = i + 1
            break
    if first_cmd_diff is None and len(calls_a) != len(calls_b):
        first_cmd_diff = n + 1
        length_mismatch_only = True

    first_obs_diff = None
    for i in range(1, n + 1):
        pa, pb = preceding_message(a, i), preceding_message(b, i)
        if pa["kind"] != pb["kind"] or pa["content"] != pb["content"]:
            first_obs_diff = i
            break

    # Response sequence comparison (catches a differing response that no compared call follows).
    first_resp_diff = None
    for i in range(n):
        if (calls_a[i]["response_kind"] != calls_b[i]["response_kind"]
                or calls_a[i]["response_content"] != calls_b[i]["response_content"]):
            first_resp_diff = i + 1
            break

    prefix = 0
    for x, y in zip(cmds_a, cmds_b):
        if x == y:
            prefix += 1
        else:
            break

    record = {
        "instance_id": inst,
        "backend": backend,
        "legacy": {
            "run_id": a["run_id"], "run_dir_repo_relative": a["run_dir_repo_relative"],
            "exit_status": a["exit_status"], "n_model_calls_recorded": a["n_model_calls_recorded"],
            "n_calls_reconstructed": a["n_calls_reconstructed"], "n_action_calls": a["n_action_calls"],
            "n_format_error_calls": a["n_format_error_calls"], "submission_bytes": a["submission_bytes"],
        },
        "yaml_v1": {
            "run_id": b["run_id"], "run_dir_repo_relative": b["run_dir_repo_relative"],
            "exit_status": b["exit_status"], "n_model_calls_recorded": b["n_model_calls_recorded"],
            "n_calls_reconstructed": b["n_calls_reconstructed"], "n_action_calls": b["n_action_calls"],
            "n_format_error_calls": b["n_format_error_calls"], "submission_bytes": b["submission_bytes"],
        },
        "system_prompt_identical": a["system_prompt"] == b["system_prompt"],
        "task_prompt_identical": a["task_prompt"] == b["task_prompt"],
        "command_sequence_legacy": cmds_a,
        "command_sequence_yaml_v1": cmds_b,
        "identical_command_sequences": cmds_a == cmds_b,
        "identical_command_prefix_length": prefix,
        "first_divergent_call_index_command": first_cmd_diff,
        "first_divergent_call_index_command_is_length_mismatch_only": length_mismatch_only,
        "first_divergent_call_index_preceding_observation": first_obs_diff,
        "first_call_index_with_differing_response": first_resp_diff,
        "compared_call_depth": n,
    }

    if first_cmd_diff is None:
        record["first_divergence"] = None
    else:
        ca = calls_a[first_cmd_diff - 1] if first_cmd_diff - 1 < len(calls_a) else None
        cb = calls_b[first_cmd_diff - 1] if first_cmd_diff - 1 < len(calls_b) else None
        prec_a = preceding_message(a, first_cmd_diff)
        prec_b = preceding_message(b, first_cmd_diff)
        cls = classify_preceding(prec_a, prec_b)
        earlier = None
        if first_resp_diff is not None and first_resp_diff < first_cmd_diff - 1:
            ea = {"kind": calls_a[first_resp_diff - 1]["response_kind"],
                  "content": calls_a[first_resp_diff - 1]["response_content"],
                  "raw_output": calls_a[first_resp_diff - 1]["response_raw_output"]}
            eb = {"kind": calls_b[first_resp_diff - 1]["response_kind"],
                  "content": calls_b[first_resp_diff - 1]["response_content"],
                  "raw_output": calls_b[first_resp_diff - 1]["response_raw_output"]}
            ecls = classify_preceding(ea, eb)
            earlier = {
                "exists": True,
                "response_of_call_index": first_resp_diff,
                "classification": ecls["classification"],
                "clock_field_only": ecls["evidence"].get("clock_artifact_only"),
                "legacy_line": ecls["evidence"].get("example_legacy_line"),
                "yaml_v1_line": ecls["evidence"].get("example_yaml_v1_line"),
                "note": "The two prompt contexts were NOT byte-identical at this call: an EARLIER message "
                        "in the shared history already differed. The proximate classification above "
                        "describes only the immediately preceding message.",
            }
        else:
            earlier = {"exists": False, "note": "No earlier message in the shared history differed before "
                                                "the immediately preceding one."}
        record["first_divergence"] = {
            "call_index": first_cmd_diff,
            "legacy_call_kind": None if ca is None else ca["kind"],
            "yaml_v1_call_kind": None if cb is None else cb["kind"],
            "legacy_call_present": ca is not None,
            "yaml_v1_call_present": cb is not None,
            "legacy_command_excerpt": None if ca is None else excerpt(ca["command"]),
            "yaml_v1_command_excerpt": None if cb is None else excerpt(cb["command"]),
            "preceding_observation_classification": cls["classification"],
            "preceding_observation_evidence": cls["evidence"],
            "earlier_context_difference": earlier,
            "terminal_co_occurrence": {
                "legacy_exit_status": a["exit_status"],
                "yaml_v1_exit_status": b["exit_status"],
                "legacy_calls": a["n_calls_reconstructed"],
                "yaml_v1_calls": b["n_calls_reconstructed"],
                "note": "Exit statuses are reported as co-occurring facts about the two episodes. "
                        "No causal relation between the configuration binding and the exit is asserted here.",
            },
        }

    if first_resp_diff is None:
        record["first_response_divergence"] = None
    else:
        pa = {"kind": calls_a[first_resp_diff - 1]["response_kind"],
              "content": calls_a[first_resp_diff - 1]["response_content"],
              "raw_output": calls_a[first_resp_diff - 1]["response_raw_output"]}
        pb = {"kind": calls_b[first_resp_diff - 1]["response_kind"],
              "content": calls_b[first_resp_diff - 1]["response_content"],
              "raw_output": calls_b[first_resp_diff - 1]["response_raw_output"]}
        cls = classify_preceding(pa, pb)
        record["first_response_divergence"] = {
            "response_of_call_index": first_resp_diff,
            "classification": cls["classification"],
            "evidence": cls["evidence"],
        }
    return record


def aggregate(records: list, subset_name: str) -> dict:
    n = len(records)
    identical = [r for r in records if r["identical_command_sequences"]]
    divergent = [r for r in records if not r["identical_command_sequences"]]
    cls_counts: dict = {}
    for r in records:
        fd = r["first_divergence"]
        if fd is not None:
            key = fd["preceding_observation_classification"]
            cls_counts[key] = cls_counts.get(key, 0) + 1
    resp_cls_counts: dict = {}
    clock_only = 0
    for r in records:
        frd = r["first_response_divergence"]
        if frd is not None:
            resp_cls_counts[frd["classification"]] = resp_cls_counts.get(frd["classification"], 0) + 1
            if frd["evidence"].get("clock_artifact_only"):
                clock_only += 1
    prefixes = sorted(r["identical_command_prefix_length"] for r in records)
    return {
        "subset": subset_name,
        "n_pairs": n,
        "n_pairs_identical_command_sequences": len(identical),
        "n_pairs_divergent_command_sequences": len(divergent),
        "n_pairs_with_any_first_divergent_call": sum(1 for r in records if r["first_divergence"] is not None),
        "n_pairs_with_any_differing_response": sum(1 for r in records if r["first_response_divergence"] is not None),
        "n_pairs_whose_first_differing_response_is_clock_field_only": clock_only,
        "first_divergent_call_preceding_observation_classification_counts": cls_counts,
        "first_differing_response_classification_counts": resp_cls_counts,
        "identical_command_prefix_lengths_sorted": prefixes,
        "identical_command_prefix_length_min": prefixes[0] if prefixes else None,
        "identical_command_prefix_length_max": prefixes[-1] if prefixes else None,
        "identical_command_prefix_length_sum": sum(prefixes),
        "first_divergent_call_indices": sorted(
            r["first_divergence"]["call_index"] for r in records if r["first_divergence"] is not None
        ),
    }


def main() -> None:
    episodes: dict = {}
    for tag, rel in COHORTS.items():
        cohort_dir = ROOT / rel
        for run_dir in sorted(p for p in cohort_dir.iterdir() if p.is_dir() and "__" in p.name):
            ep = load_episode(cohort_dir, run_dir)
            key = (ep["instance_id"], ep["backend"])
            if key in episodes.get(tag, {}):
                raise RuntimeError("duplicate assignment %s in cohort %s" % (key, tag))
            episodes.setdefault(tag, {})[key] = ep

    keys_legacy = set(episodes["legacy"])
    keys_yaml = set(episodes["yaml_v1"])
    if keys_legacy != keys_yaml:
        raise RuntimeError("cohort assignment sets differ: %s" % (keys_legacy ^ keys_yaml))
    keys = sorted(keys_legacy)

    records = [compare_pair(inst, be, episodes["legacy"][(inst, be)], episodes["yaml_v1"][(inst, be)])
               for inst, be in keys]

    anomalies = []
    for tag in COHORTS:
        for key, ep in episodes[tag].items():
            for a in ep["reconstruction_anomalies"]:
                anomalies.append({"cohort": tag, "instance_id": key[0], "backend": key[1], "anomaly": a})

    call_accounting = []
    for tag in COHORTS:
        for key, ep in sorted(episodes[tag].items()):
            call_accounting.append({
                "cohort": tag, "instance_id": key[0], "backend": key[1],
                "exit_status": ep["exit_status"],
                "n_model_calls_recorded": ep["n_model_calls_recorded"],
                "n_calls_reconstructed": ep["n_calls_reconstructed"],
                "delta_recorded_minus_reconstructed":
                    (ep["n_model_calls_recorded"] or 0) - ep["n_calls_reconstructed"],
            })

    by_backend = {be: aggregate([r for r in records if r["backend"] == be], "backend=%s" % be)
                  for be in sorted({r["backend"] for r in records})}

    grading_check = {}
    for tag in COHORTS:
        eps = list(episodes[tag].values())
        grading_check[tag] = {
            "episodes": len(eps),
            "episodes_with_empty_submission": sum(1 for e in eps if e["submission_bytes"] == 0),
            "grade_label_counts": {
                label: sum(1 for e in eps if e["grade_label"] == label)
                for label in sorted({e["grade_label"] for e in eps})
            },
            "exit_status_counts": {
                status: sum(1 for e in eps if e["exit_status"] == status)
                for status in sorted({e["exit_status"] for e in eps})
            },
        }

    env_artifact_scan = {}
    for tag in COHORTS:
        counts = {name: 0 for name in ENV_VAR_ARTIFACTS}
        total_obs = 0
        for ep in episodes[tag].values():
            for c in ep["calls"]:
                if c["response_kind"] == "observation":
                    total_obs += 1
                    raw = c["response_raw_output"] or ""
                    for name, token in ENV_VAR_ARTIFACTS.items():
                        if token in raw:
                            counts[name] += 1
        env_artifact_scan[tag] = {"observations_scanned": total_obs, "observations_containing_artifact": counts}

    payload = {
        "analysis": "cross_cohort_divergence",
        "request": "DTR-REQ-002 / REQ-004 descriptive analysis of already-completed block-1 pilot episodes",
        "kind": "DESCRIPTIVE worker analysis over committed artifacts; counts and classifications only; "
                "no causal claim, no efficacy claim, no study-design recommendation",
        "generated_by_script_repo_relative": SCRIPT_REL,
        "inputs": {
            "legacy_cohort_dir_repo_relative": COHORTS["legacy"],
            "yaml_v1_cohort_dir_repo_relative": COHORTS["yaml_v1"],
            "legacy_report_repo_relative": "results/v2_agent/pilot_20260922/report_block1_final.json",
            "yaml_v1_report_repo_relative":
                "results/v2_agent/pilot_20260922_yaml_v1/report_yaml_v1_block1_final.json",
            "episodes_read": sum(len(v) for v in episodes.values()),
            "pairs": len(records),
        },
        "definitions": {
            "logical_call_index": "1-based ordinal of a logical model call, counting BOTH calls that "
                                  "produced an executed action (one assistant message with extra.actions) "
                                  "AND calls that produced a harness format error (one user message with "
                                  "extra.interrupt_type=='FormatError' and no assistant message). Both "
                                  "consume one of the H=24 logical calls.",
            "command_sequence": "commands taken from assistant extra.actions[0].command in message order; "
                                "format-error calls contribute no command",
            "identical_command_prefix_length": "number of leading entries of the two command sequences that "
                                               "are byte-identical",
            "first_divergent_call_index_command": "smallest logical call index at which the (kind, command) "
                                                  "pair differs; when the two episodes agree over the shorter "
                                                  "episode's whole length but differ in length, this is "
                                                  "shorter_length+1 and the flag "
                                                  "'..._is_length_mismatch_only' is true; null if identical",
            "first_divergent_call_index_preceding_observation": "smallest logical call index (within the "
                                                                "compared depth) whose immediately preceding "
                                                                "message differs; null if identical",
            "first_call_index_with_differing_response": "smallest logical call index whose own response "
                                                        "message (observation or format-error text) differs; "
                                                        "this can be later than the compared call depth's "
                                                        "preceding-observation index because the last "
                                                        "response of a truncated episode precedes no "
                                                        "compared call",
            "classification_vocabulary": [
                "observation_truncated_in_yaml_v1",
                "observation_text_differs_env_vars",
                "observation_identical_but_command_differs",
                "no_preceding_observation",
                "unclassified",
            ],
        },
        "cohort_binding_difference_as_declared": {
            "legacy": "mini-swe-agent 04d809c in-code defaults for the model/environment sections "
                      "(observation_template with no length branch; format_error_template '{{ error }}'; "
                      "no environment env vars)",
            "yaml_v1": "pinned default.yaml model+environment sections: observation_template with a "
                       ">=10000-char head/tail elision branch, a longer format_error_template, "
                       "model_kwargs.drop_params, and env PAGER/MANPAGER/LESS/PIP_PROGRESS_BAR/TQDM_DISABLE",
            "source": "results/v2_agent/pilot_20260922_yaml_v1/<run_id>/effective_config.json and "
                      "work/upstream/mini-swe-agent-04d809c.../src/minisweagent/models/litellm_model.py",
        },
        "aggregate_all_pairs": aggregate(records, "all"),
        "aggregate_by_backend": by_backend,
        "env_var_artifact_scan": {
            "note": "Scan of every observation's extra.raw_output in both cohorts for the byte patterns the "
                    "pinned env vars would suppress or change. A zero count on both sides means the "
                    "'observation_text_differs_env_vars' classification had no support anywhere in this data.",
            "per_cohort": env_artifact_scan,
        },
        "grading_and_submission_check": {
            "note": "Recomputed from each episode's own submission.diff byte length and grade.json "
                    "classification, as a consistency anchor for the pairing.",
            "per_cohort": grading_check,
        },
        "call_accounting": call_accounting,
        "reconstruction_anomalies": anomalies,
        "pairs": records,
    }

    out_path = ROOT / OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Never emit the local account name or home path; derive the forbidden strings at runtime
    # so this source file does not contain them either.
    forbidden = [s for s in (Path.home().name, str(Path.home())) if s]
    text = json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=False)
    for bad in forbidden:
        if bad in text:
            raise RuntimeError("refusing to write: payload leaks the local account name or home path")
    payload["output_sha256_excluding_this_field"] = hashlib.sha256(text.encode()).hexdigest()
    final = json.dumps(payload, indent=1, ensure_ascii=False, sort_keys=False)
    for bad in forbidden:
        if bad in final:
            raise RuntimeError("refusing to write: payload leaks the local account name or home path")
    with open(out_path, "x", encoding="utf-8") as handle:
        handle.write(final + "\n")
    print("wrote", OUT_REL)
    print(json.dumps(payload["aggregate_all_pairs"], indent=1))


if __name__ == "__main__":
    main()
