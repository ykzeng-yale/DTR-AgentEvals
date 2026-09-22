#!/usr/bin/env python3
"""Independent re-derivation of the command-repetition dimension.

Written as an adversarial cross-check of results/v2_agent/analysis_20260922/
repetition_taxonomy.json. Nothing is imported from repetition_taxonomy.py; every
figure below is recomputed from the committed episode records by a deliberately
different route:

  * episode discovery walks the cohort directories looking for episode.json,
    instead of matching a run_id name pattern;
  * (instance_id, backend) come from the episode.json BODY, and the run_id string
    is parsed separately (rsplit on '__') only so the two can be compared;
  * commands are extracted twice -- once from extra.actions, once by re-parsing
    the ```mswea_bash_command fence out of the assistant message CONTENT -- and
    the two extractions are compared per episode;
  * terminal cycles are found by a reversed-suffix block scan rather than by
    slicing the tail of the forward list;
  * repeat occurrences are counted by a left-to-right seen-set scan, and
    separately as sum(count-1) over a multiset, so the two must agree;
  * model-call totals are re-derived from attempts.jsonl (both ledger dialects)
    as well as read from episode.json.

Descriptive only: counts and classifications, no causal or efficacy claim.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
COHORTS = {
    "legacy": "results/v2_agent/pilot_20260922",
    "yaml-v1": "results/v2_agent/pilot_20260922_yaml_v1",
}
OUT_REL = "results/v2_agent/analysis_20260922/repetition_taxonomy_verification.json"
PEER_REL = "results/v2_agent/analysis_20260922/repetition_taxonomy.json"

FENCE = re.compile(r"```mswea_bash_command\n(.*?)\n```", re.DOTALL)
MAX_PERIOD = 6


# ---------------------------------------------------------------- helpers


def parse_run_id(run_id: str) -> dict:
    """Split <instance_id>__<backend>__<binding>__<tsZ>-<hex> from the RIGHT.

    instance_id itself contains '__', so the only safe anchor is the tail.
    """
    parts = run_id.rsplit("__", 3)
    if len(parts) != 4:
        return {"instance_id": None, "backend": None, "binding": None, "stamp": None}
    instance_id, backend, binding, stamp = parts
    return {
        "instance_id": instance_id,
        "backend": backend,
        "binding": binding,
        "stamp": stamp,
    }


def commands_from_actions(messages: list) -> tuple[list, int, list]:
    """Route A: extra.actions. Returns (first-action commands, n_bad, all_counts)."""
    cmds, bad, counts = [], 0, []
    for m in messages:
        if m.get("role") != "assistant":
            continue
        actions = (m.get("extra") or {}).get("actions") or []
        counts.append(len(actions))
        if len(actions) != 1:
            bad += 1
        if actions:
            cmds.append(actions[0].get("command"))
        else:
            cmds.append(None)
    return cmds, bad, counts


def commands_from_content(messages: list) -> list:
    """Route B: re-parse the fenced command out of the assistant message text."""
    cmds = []
    for m in messages:
        if m.get("role") != "assistant":
            continue
        found = FENCE.findall(m.get("content") or "")
        cmds.append(found[0] if len(found) == 1 else None)
    return cmds


def terminal_cycle(cmds: list) -> tuple[int | None, int | None, int | None]:
    """Smallest period p in 1..MAX_PERIOD whose terminal block repeats k>=2 times.

    Reversed-suffix scan: walk backwards in blocks of p and count how many
    consecutive blocks equal the last block.
    """
    n = len(cmds)
    rev = cmds[::-1]
    for p in range(1, MAX_PERIOD + 1):
        if p * 2 > n:
            break
        block = rev[0:p]
        k = 1
        while (k + 1) * p <= n and rev[k * p : (k + 1) * p] == block:
            k += 1
        if k >= 2:
            return p, k, n - p * k + 1
    return None, None, None


def classify(cmds: list, period: int | None, max_repeat: int) -> str:
    if len(cmds) == 1:
        return "single_call"
    if period == 1:
        return "terminal_1cycle"
    if period == 2:
        return "terminal_2cycle"
    if period is not None:
        return "terminal_longer_cycle"
    if max_repeat >= 2:
        return "repetition_without_terminal_cycle"
    return "no_repetition"


def ledger_calls(path: Path) -> dict:
    """Re-derive logical model calls from attempts.jsonl, both dialects."""
    if not path.exists():
        return {"dialect": None, "records": 0, "logical_calls": None}
    recs = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    has_event = any("event" in r for r in recs)
    if has_event:
        results = [r for r in recs if r.get("event") == "result"]
        starts = [r for r in recs if r.get("event") == "start"]
        calls = {r.get("call") for r in recs}
        return {
            "dialect": "two-record",
            "records": len(recs),
            "start_records": len(starts),
            "result_records": len(results),
            "logical_calls": len(calls),
        }
    calls = {r.get("call") for r in recs}
    return {
        "dialect": "one-record",
        "records": len(recs),
        "logical_calls": len(calls),
    }


# ---------------------------------------------------------------- per episode


def analyse(cohort: str, ep_dir: Path) -> dict:
    ep = json.loads((ep_dir / "episode.json").read_text())
    traj = json.loads((ep_dir / "trajectory.json").read_text())
    messages = traj["messages"]

    run_id = ep_dir.name
    parsed = parse_run_id(run_id)

    cmds_a, bad_action_count, action_counts = commands_from_actions(messages)
    cmds_b = commands_from_content(messages)
    routes_agree = cmds_a == cmds_b

    cmds = cmds_a
    n = len(cmds)

    # observations: the message directly after each assistant message, when it is
    # a tool result (role user carrying a returncode).
    obs_text: list = []
    obs_rc: list = []
    ai = -1
    for i, m in enumerate(messages):
        if m.get("role") != "assistant":
            continue
        ai += 1
        nxt = messages[i + 1] if i + 1 < len(messages) else None
        if nxt and nxt.get("role") == "user" and "returncode" in (nxt.get("extra") or {}):
            obs_text.append(nxt.get("content"))
            obs_rc.append(nxt["extra"]["returncode"])
        else:
            obs_text.append(None)
            obs_rc.append(None)

    counts = Counter(cmds)
    distinct = len(counts)
    max_repeat = max(counts.values()) if counts else 0

    # repeat occurrences, two independent routes
    seen: set = set()
    repeat_idx: list = []
    for i, c in enumerate(cmds):
        if c in seen:
            repeat_idx.append(i)
        seen.add(c)
    repeats_scan = len(repeat_idx)
    repeats_multiset = sum(v - 1 for v in counts.values())

    # identical vs differing observation on each repeat occurrence
    last_pos: dict = {}
    identical = differing = missing = 0
    differing_detail = []
    for i, c in enumerate(cmds):
        if c in last_pos:
            j = last_pos[c]
            if obs_text[i] is None or obs_text[j] is None:
                missing += 1
            elif obs_text[i] == obs_text[j]:
                identical += 1
            else:
                differing += 1
                differing_detail.append(
                    {
                        "command": c,
                        "occurrence_index_1based": i + 1,
                        "previous_occurrence_index_1based": j + 1,
                        "returncode_prev": obs_rc[j],
                        "returncode_this": obs_rc[i],
                        "chars_prev": len(obs_text[j]),
                        "chars_this": len(obs_text[i]),
                    }
                )
        last_pos[c] = i

    # returncode constancy over repeated command strings with full observations
    by_cmd = defaultdict(list)
    for i, c in enumerate(cmds):
        by_cmd[c].append(i)
    checked = varying = with_missing = 0
    for c, idxs in by_cmd.items():
        if len(idxs) < 2:
            continue
        if any(obs_text[i] is None for i in idxs):
            with_missing += 1
            continue
        checked += 1
        if len({obs_rc[i] for i in idxs}) > 1:
            varying += 1

    period, k, start = terminal_cycle(cmds)
    cls = classify(cmds, period, max_repeat)

    # unrecorded model calls and their visible mechanisms
    n_model_calls = ep.get("n_model_calls")
    obs_ids = set()
    for i, m in enumerate(messages):
        if m.get("role") == "assistant" and i + 1 < len(messages):
            nxt = messages[i + 1]
            if nxt.get("role") == "user" and "returncode" in (nxt.get("extra") or {}):
                obs_ids.add(i + 1)
    user_idx = [i for i, m in enumerate(messages) if m.get("role") == "user"]
    task_idx = user_idx[0] if user_idx else None
    format_error_msgs = [
        i for i in user_idx if i not in obs_ids and i != task_idx
    ]
    err = ep.get("error")
    unrecorded = (n_model_calls - n) if n_model_calls is not None else None
    residual = (
        unrecorded - len(format_error_msgs) - (1 if err else 0)
        if unrecorded is not None
        else None
    )

    ledger = ledger_calls(ep_dir / "attempts.jsonl")

    return {
        "cohort": cohort,
        "run_id": run_id,
        "instance_id": ep.get("instance_id"),
        "backend": ep.get("backend"),
        "run_id_parse_matches_episode_body": (
            parsed["instance_id"] == ep.get("instance_id")
            and parsed["backend"] == ep.get("backend")
        ),
        "run_id_timestamp_segment": parsed["stamp"],
        "exit_status": ep.get("exit_status"),
        "error_present": bool(err),
        "n_model_calls": n_model_calls,
        "ledger": ledger,
        "total_commands": n,
        "command_routes_agree": routes_agree,
        "assistant_messages_with_action_count_not_1": bad_action_count,
        "max_actions_on_one_message": max(action_counts) if action_counts else 0,
        "distinct_commands": distinct,
        "max_repeat": max_repeat,
        "repeat_occurrences_seen_set": repeats_scan,
        "repeat_occurrences_multiset": repeats_multiset,
        "repeat_routes_agree": repeats_scan == repeats_multiset,
        "identical_observation_repeats": identical,
        "differing_observation_repeats": differing,
        "repeat_occurrences_missing_observation": missing,
        "differing_observation_detail": differing_detail,
        "repeated_command_strings": sum(1 for v in counts.values() if v >= 2),
        "repeated_commands_checked_for_returncode": checked,
        "repeated_commands_with_varying_returncode": varying,
        "repeated_commands_with_missing_observation": with_missing,
        "terminal_cycle_period": period,
        "terminal_cycle_repeats": k,
        "terminal_cycle_start_call": start,
        "classification": cls,
        "format_error_messages": len(format_error_msgs),
        "unrecorded_model_calls": unrecorded,
        "residual_unexplained_calls": residual,
        "command_sequence_digest": hashlib.sha256(
            json.dumps(cmds, ensure_ascii=False).encode("utf-8")
        ).hexdigest(),
    }


# ---------------------------------------------------------------- main


def main() -> int:
    episodes = []
    for cohort, rel in COHORTS.items():
        base = REPO / rel
        for child in sorted(base.iterdir()):
            if child.is_dir() and (child / "episode.json").exists():
                episodes.append(analyse(cohort, child))

    def agg(rows):
        out = {
            "episodes": len(rows),
            "n_model_calls": sum(r["n_model_calls"] for r in rows),
            "total_commands": sum(r["total_commands"] for r in rows),
            "repeat_occurrences": sum(r["repeat_occurrences_seen_set"] for r in rows),
            "identical_observation_repeats": sum(
                r["identical_observation_repeats"] for r in rows
            ),
            "differing_observation_repeats": sum(
                r["differing_observation_repeats"] for r in rows
            ),
            "repeat_occurrences_missing_observation": sum(
                r["repeat_occurrences_missing_observation"] for r in rows
            ),
            "repeated_command_strings": sum(r["repeated_command_strings"] for r in rows),
            "repeated_commands_checked_for_returncode": sum(
                r["repeated_commands_checked_for_returncode"] for r in rows
            ),
            "repeated_commands_with_varying_returncode": sum(
                r["repeated_commands_with_varying_returncode"] for r in rows
            ),
            "format_error_messages": sum(r["format_error_messages"] for r in rows),
            "unrecorded_model_calls": sum(r["unrecorded_model_calls"] for r in rows),
            "residual_unexplained_calls": sum(
                r["residual_unexplained_calls"] for r in rows
            ),
            "episodes_ending_in_terminal_cycle": sum(
                1 for r in rows if r["terminal_cycle_period"] is not None
            ),
            "episodes_with_max_repeat_ge_5": sum(
                1 for r in rows if r["max_repeat"] >= 5
            ),
            "episodes_with_any_repetition": sum(1 for r in rows if r["max_repeat"] >= 2),
            "max_repeat_max": max(r["max_repeat"] for r in rows),
            "max_repeat_min": min(r["max_repeat"] for r in rows),
            "classification_counts": dict(
                Counter(r["classification"] for r in rows)
            ),
            "terminal_cycle_period_counts": dict(
                Counter(
                    str(r["terminal_cycle_period"])
                    for r in rows
                    if r["terminal_cycle_period"] is not None
                )
            ),
            "terminal_cycle_repeat_counts": dict(
                Counter(
                    str(r["terminal_cycle_repeats"])
                    for r in rows
                    if r["terminal_cycle_repeats"] is not None
                )
            ),
        }
        starts = [
            r["terminal_cycle_start_call"]
            for r in rows
            if r["terminal_cycle_start_call"] is not None
        ]
        out["terminal_cycle_start_call_min"] = min(starts) if starts else None
        out["terminal_cycle_start_call_max"] = max(starts) if starts else None
        return out

    overall = agg(episodes)
    per_cohort = {
        c: agg([r for r in episodes if r["cohort"] == c]) for c in COHORTS
    }
    per_backend = {
        b: agg([r for r in episodes if r["backend"] == b])
        for b in sorted({r["backend"] for r in episodes})
    }
    per_cell = {
        f"{c}/{b}": agg(
            [r for r in episodes if r["cohort"] == c and r["backend"] == b]
        )
        for c in COHORTS
        for b in sorted({r["backend"] for r in episodes})
    }

    # cross-cohort pairing by direct digest comparison
    by_assignment = defaultdict(dict)
    for r in episodes:
        by_assignment[(r["instance_id"], r["backend"])][r["cohort"]] = r
    paired = identical_seq = same_cls = same_period = 0
    divergent = []
    for (inst, backend), d in sorted(by_assignment.items()):
        if len(d) != 2:
            continue
        paired += 1
        a, b = d["legacy"], d["yaml-v1"]
        same_seq = a["command_sequence_digest"] == b["command_sequence_digest"]
        identical_seq += int(same_seq)
        same_cls += int(a["classification"] == b["classification"])
        same_period += int(a["terminal_cycle_period"] == b["terminal_cycle_period"])
        if not same_seq:
            divergent.append(
                {
                    "instance_id": inst,
                    "backend": backend,
                    "legacy": {
                        "total_commands": a["total_commands"],
                        "classification": a["classification"],
                        "terminal_cycle_period": a["terminal_cycle_period"],
                        "exit_status": a["exit_status"],
                    },
                    "yaml-v1": {
                        "total_commands": b["total_commands"],
                        "classification": b["classification"],
                        "terminal_cycle_period": b["terminal_cycle_period"],
                        "exit_status": b["exit_status"],
                    },
                }
            )

    top = max(episodes, key=lambda r: r["max_repeat"])
    top_all = [r for r in episodes if r["max_repeat"] == top["max_repeat"]]

    integrity = {
        "episode_dirs_found": len(episodes),
        "episodes_where_command_routes_disagree": sum(
            1 for r in episodes if not r["command_routes_agree"]
        ),
        "episodes_where_repeat_routes_disagree": sum(
            1 for r in episodes if not r["repeat_routes_agree"]
        ),
        "episodes_where_run_id_parse_mismatches_body": sum(
            1 for r in episodes if not r["run_id_parse_matches_episode_body"]
        ),
        "assistant_messages_with_action_count_not_1": sum(
            r["assistant_messages_with_action_count_not_1"] for r in episodes
        ),
        "episodes_where_ledger_logical_calls_differ_from_n_model_calls": [
            {
                "run_id": r["run_id"],
                "n_model_calls": r["n_model_calls"],
                "ledger_logical_calls": r["ledger"]["logical_calls"],
            }
            for r in episodes
            if r["ledger"]["logical_calls"] != r["n_model_calls"]
        ],
        "ledger_dialects": dict(
            Counter(f"{r['cohort']}:{r['ledger']['dialect']}" for r in episodes)
        ),
        "episodes_with_error_non_null": sum(1 for r in episodes if r["error_present"]),
    }

    doc = {
        "kind": "independent verification re-derivation of the command-repetition dimension",
        "verifies": PEER_REL,
        "artifact": OUT_REL,
        "generated_by": "experiments/v2_agent/analysis/verify_loops.py",
        "scope": (
            "All committed block-1 episodes in both cohorts. Counts and "
            "classifications recomputed from the raw records by a route "
            "independent of the artifact under verification. No causal claim, "
            "no efficacy claim, no recommendation about study design."
        ),
        "source_dirs": COHORTS,
        "method_differences_from_peer": [
            "episodes discovered by presence of episode.json, not by run_id name pattern",
            "instance_id/backend taken from the episode.json body; the run_id string parsed separately (rsplit on '__') and compared",
            "commands extracted twice: from extra.actions and by re-parsing the fenced command out of assistant message content",
            "terminal cycle found by a reversed-suffix block scan",
            "repeat occurrences counted by a seen-set scan and by a multiset sum",
            "model-call totals re-derived from attempts.jsonl in both ledger dialects",
        ],
        "overall": overall,
        "per_cohort": per_cohort,
        "per_backend": per_backend,
        "per_cohort_backend": per_cell,
        "cross_cohort_pairing": {
            "paired_assignments": paired,
            "identical_command_sequence": identical_seq,
            "same_classification": same_cls,
            "same_terminal_cycle_period": same_period,
            "divergent_assignments": divergent,
        },
        "highest_single_command_repeat": {
            "max_repeat": top["max_repeat"],
            "episodes": [
                {
                    "cohort": r["cohort"],
                    "instance_id": r["instance_id"],
                    "backend": r["backend"],
                    "total_commands": r["total_commands"],
                    "terminal_cycle_period": r["terminal_cycle_period"],
                    "terminal_cycle_repeats": r["terminal_cycle_repeats"],
                    "terminal_cycle_start_call": r["terminal_cycle_start_call"],
                }
                for r in top_all
            ],
        },
        "integrity": integrity,
        "ambiguities_and_limitations": [
            "Command identity is byte-exact here as well; a semantically identical command written differently counts as distinct.",
            "A byte-identical observation is a count of identical bytes returned to the agent, not evidence about container state.",
            "Terminal-cycle periods above 6 were not searched, matching the dimension as stated; an episode cycling with a longer period would be recorded as having none.",
            "Mechanisms for model calls that left no command are read off the saved records (a rejected multi-action response, a failed final call); where a record does not distinguish them the artifact says so rather than assigning one.",
        ],
        "episodes": episodes,
    }

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "x", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    print(json.dumps(overall, indent=1))
    print("cross:", json.dumps(doc["cross_cohort_pairing"], indent=1)[:1200])
    print("integrity:", json.dumps(integrity, indent=1))
    print("top:", json.dumps(doc["highest_single_command_repeat"], indent=1))
    print("wrote", OUT_REL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
