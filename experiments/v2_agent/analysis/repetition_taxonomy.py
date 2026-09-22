#!/usr/bin/env python
"""Repetition / loop taxonomy over the committed v2_agent pilot records.

DESCRIPTIVE ONLY. Reads already-committed episode records; runs no model, no
server, no container, no evaluator, and writes nothing under an existing
results subdirectory other than the new analysis output (opened write-once).

Scope: both block-1 cohorts (legacy `pilot_20260922`, `yaml-v1`
`pilot_20260922_yaml_v1`), 8 instances x 2 backends each = 32 episodes.

Usage:
    .venv/bin/python experiments/v2_agent/analysis/repetition_taxonomy.py
    .venv/bin/python experiments/v2_agent/analysis/repetition_taxonomy.py --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, OrderedDict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

COHORTS = OrderedDict(
    [
        ("legacy", "results/v2_agent/pilot_20260922"),
        ("yaml-v1", "results/v2_agent/pilot_20260922_yaml_v1"),
    ]
)

OUT_REL = "results/v2_agent/analysis_20260922/repetition_taxonomy.json"

MAX_PERIOD = 6  # cycle periods searched, per the request: p in 1..6

DEFINITIONS = {
    "unit_of_analysis": (
        "One episode = one committed run directory <cohort_dir>/<run_id>/. run_id is "
        "<instance_id>__<backend>__<binding>__<timestampZ>-<hex>; instance_id itself contains "
        "'__', so backend/binding/timestamp are parsed from the LAST '__'-separated segments "
        "(never by index from the front)."
    ),
    "command": (
        "The string at trajectory.json messages[i].extra.actions[0].command for each message with "
        "role=='assistant', taken in message order. Every recorded assistant message in all 32 "
        "episodes carries exactly one action (verified by the script; see "
        "integrity.assistant_messages_with_action_count_not_1). Command identity is BYTE-EXACT on "
        "the raw string: no whitespace normalisation, no shell parsing, no de-aliasing. Two "
        "commands that differ only in whitespace count as different commands."
    ),
    "observation": (
        "For the command at assistant message index i, the observation is messages[i+1] when that "
        "message has role=='user' and 'returncode' in its extra; otherwise null. The observation "
        "TEXT compared is the message 'content' field, i.e. exactly the bytes the agent was shown "
        "(the <returncode>/<output> wrapper included, and the pinned template's elided head/tail "
        "rendering where it applied). extra.raw_output is the unwrapped command output and is NOT "
        "used for comparison."
    ),
    "total_commands": "Number of recorded commands in the episode (= number of assistant messages).",
    "distinct_commands": "Number of distinct byte-exact command strings in the episode.",
    "max_repeat": "Highest occurrence count of any single byte-exact command string in the episode.",
    "repeated_command_occurrences": (
        "total_commands - distinct_commands, i.e. the number of command occurrences that repeat a "
        "command already issued earlier in the same episode. Same definition as "
        "'repeated_commands' in the committed *_harness_exposure.json artifacts, so the totals are "
        "directly comparable."
    ),
    "terminal_cycle": (
        "Let C = [c_1..c_n] be the episode's commands in order. For a period p, let k be the "
        "largest integer >= 1 such that the final p*k commands consist of k consecutive "
        "byte-identical repetitions of the final p-command block C[n-p+1..n]. The episode has a "
        "terminal cycle iff some p in 1..6 admits k >= 2. terminal_cycle_period is the SMALLEST "
        "such p (as requested), and terminal_cycle_repeats is the maximal k for that p. p*k <= n "
        "always. Note a pure run of one command (p=1, k=m) is also matched by p=2 with k=floor(m/2); "
        "taking the smallest p resolves that to p=1."
    ),
    "terminal_cycle_start_call": (
        "1-based position, within the episode's recorded command list, of the first command of the "
        "terminal cycle's final k repetitions: n - p*k + 1. null when there is no terminal cycle. "
        "This indexes RECORDED COMMANDS, which is not always the same as the model-call index "
        "(see limitations.unrecorded_model_calls)."
    ),
    "classification": (
        "Dominant pattern of the episode, assigned by this precedence, first match wins: "
        "(1) 'single_call' if total_commands == 1; "
        "(2) 'terminal_1cycle' if a terminal cycle exists with period p == 1 (the same command "
        "repeated back-to-back to the end of the episode); "
        "(3) 'terminal_2cycle' if a terminal cycle exists with period p == 2 (two commands "
        "alternating to the end); "
        "(4) 'terminal_longer_cycle' if a terminal cycle exists with period p in 3..6; "
        "(5) 'repetition_without_terminal_cycle' if no terminal cycle but max_repeat >= 2; "
        "(6) 'no_repetition' otherwise (every command in the episode distinct)."
    ),
    "repeated_commands_all_same_returncode": (
        "Over the distinct command strings that occur >= 2 times in the episode AND whose every "
        "occurrence has an observation: true iff each such command returned the same returncode at "
        "every occurrence. null when the episode has no such command. Commands with a missing "
        "observation on any occurrence are excluded and counted in "
        "repeated_commands_with_missing_observation."
    ),
    "identical_observation_repeats": (
        "Count of command OCCURRENCES (not distinct commands) that (a) repeat a byte-exact command "
        "string issued earlier in the episode and (b) whose observation content is byte-identical "
        "to the observation content of the immediately preceding occurrence of that same command "
        "string. This is the count of moments at which the agent re-issued a command and was handed "
        "back exactly the bytes it had already seen. Occurrences where either observation is "
        "missing are excluded and counted in repeat_occurrences_missing_observation."
    ),
    "unrecorded_model_calls": (
        "episode.json n_model_calls minus total_commands. Positive when a model call left no "
        "assistant message in the saved trajectory. Two mechanisms are visible in these records: "
        "(a) a format-error call, where the response carried 2 actions, the harness rejected it, and "
        "only the harness's format-error user message was persisted (counted as "
        "format_error_messages); and (b) a final call that failed outright, e.g. the context-window "
        "error that ended the episode (counted as 1 when episode.json 'error' is non-null). "
        "residual_unexplained_calls is unrecorded_model_calls minus those two, and is 0 in every "
        "one of these 32 episodes; a non-zero value would mark a call whose mechanism is NOT "
        "determined from these artifacts."
    ),
    "command_sequence_sha256": (
        "sha256 of json.dumps(commands, ensure_ascii=False) for the episode's recorded command list. "
        "Two episodes with the same digest issued the byte-identical command sequence."
    ),
}


def parse_run_id(run_id: str) -> dict:
    """Split <instance_id>__<backend>__<binding>__<tsZ>-<hex> from the END."""
    parts = run_id.split("__")
    if len(parts) < 4:
        raise ValueError(f"unparseable run_id: {run_id}")
    stamp = parts[-1]
    binding = parts[-2]
    backend = parts[-3]
    instance_id = "__".join(parts[:-3])
    timestamp = stamp.split("-", 1)[0]
    return {
        "instance_id": instance_id,
        "backend": backend,
        "binding": binding,
        "timestamp": timestamp,
    }


def terminal_cycle(commands: list) -> tuple:
    """Return (period, repeats, start_index_0based) or (None, None, None)."""
    n = len(commands)
    best = None
    for p in range(1, MAX_PERIOD + 1):
        if p * 2 > n:
            break
        block = commands[n - p:]
        k = 1
        while (k + 1) * p <= n and commands[n - (k + 1) * p: n - k * p] == block:
            k += 1
        if k >= 2:
            best = (p, k, n - p * k)
            break  # smallest p wins, per the stated definition
    return best if best is not None else (None, None, None)


def analyse_episode(cohort: str, cohort_rel: str, run_id: str) -> dict:
    run_dir = REPO_ROOT / cohort_rel / run_id
    traj = json.loads((run_dir / "trajectory.json").read_text())
    episode = json.loads((run_dir / "episode.json").read_text())
    msgs = traj["messages"]

    commands = []
    observations = []  # aligned with commands; None when absent
    returncodes = []
    bad_action_counts = 0
    for i, m in enumerate(msgs):
        if m.get("role") != "assistant":
            continue
        actions = (m.get("extra") or {}).get("actions") or []
        if len(actions) != 1:
            bad_action_counts += 1
        if not actions:
            continue
        commands.append(actions[0]["command"])
        nxt = msgs[i + 1] if i + 1 < len(msgs) else None
        if nxt is not None and nxt.get("role") == "user" and "returncode" in (nxt.get("extra") or {}):
            observations.append(nxt.get("content"))
            returncodes.append((nxt.get("extra") or {}).get("returncode"))
        else:
            observations.append(None)
            returncodes.append(None)

    # harness format-error messages: user messages that are neither the task prompt
    # (the first user message) nor a command observation.
    user_idx = [i for i, m in enumerate(msgs) if m.get("role") == "user"]
    task_idx = user_idx[0] if user_idx else None
    format_error_messages = sum(
        1
        for i, m in enumerate(msgs)
        if m.get("role") == "user"
        and i != task_idx
        and "returncode" not in (m.get("extra") or {})
    )

    n = len(commands)
    counts = Counter(commands)
    distinct = len(counts)
    max_repeat = max(counts.values()) if counts else 0
    period, repeats, start0 = terminal_cycle(commands)

    if n == 1:
        klass = "single_call"
    elif period == 1:
        klass = "terminal_1cycle"
    elif period == 2:
        klass = "terminal_2cycle"
    elif period is not None:
        klass = "terminal_longer_cycle"
    elif max_repeat >= 2:
        klass = "repetition_without_terminal_cycle"
    else:
        klass = "no_repetition"

    # returncode stability across repeats
    positions = {}
    for idx, c in enumerate(commands):
        positions.setdefault(c, []).append(idx)
    repeated_cmds = [c for c, ps in positions.items() if len(ps) >= 2]
    rc_checked = 0
    rc_varying = 0
    rc_missing_obs = 0
    for c in repeated_cmds:
        ps = positions[c]
        if any(observations[p] is None for p in ps):
            rc_missing_obs += 1
            continue
        rc_checked += 1
        if len({returncodes[p] for p in ps}) > 1:
            rc_varying += 1
    all_same_rc = None if rc_checked == 0 else (rc_varying == 0)

    # identical-observation repeats (consecutive occurrences of the same command string)
    identical_repeats = 0
    differing_repeats = 0
    repeat_missing_obs = 0
    for c in repeated_cmds:
        ps = positions[c]
        for prev, cur in zip(ps, ps[1:]):
            if observations[prev] is None or observations[cur] is None:
                repeat_missing_obs += 1
            elif observations[prev] == observations[cur]:
                identical_repeats += 1
            else:
                differing_repeats += 1

    n_model_calls = episode.get("n_model_calls")
    error_present = episode.get("error") is not None
    unrecorded = None if n_model_calls is None else n_model_calls - n
    accounted = format_error_messages + (1 if error_present else 0)
    residual = None if unrecorded is None else unrecorded - accounted

    meta = parse_run_id(run_id)
    top = counts.most_common(1)[0] if counts else (None, 0)
    seq_sha = hashlib.sha256(json.dumps(commands, ensure_ascii=False).encode("utf-8")).hexdigest()
    return {
        "cohort": cohort,
        "instance_id": meta["instance_id"],
        "backend": meta["backend"],
        "binding": meta["binding"],
        "run_id": run_id,
        "record_dir": f"{cohort_rel}/{run_id}",
        "exit_status": episode.get("exit_status"),
        "episode_error_present": error_present,
        "n_model_calls": n_model_calls,
        "total_commands": n,
        "command_sequence_sha256": seq_sha,
        "distinct_commands": distinct,
        "repeated_command_occurrences": n - distinct,
        "max_repeat": max_repeat,
        "most_repeated_command": top[0],
        "terminal_cycle": period is not None,
        "terminal_cycle_period": period,
        "terminal_cycle_repeats": repeats,
        "terminal_cycle_start_call": None if start0 is None else start0 + 1,
        "terminal_cycle_commands": None if period is None else commands[n - period:],
        "classification": klass,
        "repeated_command_strings": len(repeated_cmds),
        "repeated_commands_all_same_returncode": all_same_rc,
        "repeated_commands_checked_for_returncode": rc_checked,
        "repeated_commands_with_varying_returncode": rc_varying,
        "repeated_commands_with_missing_observation": rc_missing_obs,
        "identical_observation_repeats": identical_repeats,
        "differing_observation_repeats": differing_repeats,
        "repeat_occurrences_missing_observation": repeat_missing_obs,
        "observations_present": sum(1 for o in observations if o is not None),
        "format_error_messages": format_error_messages,
        "unrecorded_model_calls": unrecorded,
        "residual_unexplained_calls": residual,
        "_assistant_messages_with_action_count_not_1": bad_action_counts,
    }


SUM_FIELDS = [
    "n_model_calls",
    "total_commands",
    "repeated_command_occurrences",
    "identical_observation_repeats",
    "differing_observation_repeats",
    "repeat_occurrences_missing_observation",
    "repeated_command_strings",
    "repeated_commands_checked_for_returncode",
    "repeated_commands_with_varying_returncode",
    "repeated_commands_with_missing_observation",
    "format_error_messages",
    "unrecorded_model_calls",
    "residual_unexplained_calls",
]

CLASSES = [
    "terminal_1cycle",
    "terminal_2cycle",
    "terminal_longer_cycle",
    "repetition_without_terminal_cycle",
    "no_repetition",
    "single_call",
]


def aggregate(rows: list) -> dict:
    out = {"episodes": len(rows)}
    for f in SUM_FIELDS:
        out[f] = sum(r[f] or 0 for r in rows)
    out["episodes_ending_in_terminal_cycle"] = sum(1 for r in rows if r["terminal_cycle"])
    out["classification_counts"] = {c: sum(1 for r in rows if r["classification"] == c) for c in CLASSES}
    out["terminal_cycle_period_counts"] = dict(
        sorted(Counter(r["terminal_cycle_period"] for r in rows if r["terminal_cycle"]).items())
    )
    out["terminal_cycle_repeat_counts"] = dict(
        sorted(Counter(r["terminal_cycle_repeats"] for r in rows if r["terminal_cycle"]).items())
    )
    out["max_repeat_max"] = max((r["max_repeat"] for r in rows), default=0)
    out["max_repeat_min"] = min((r["max_repeat"] for r in rows), default=0)
    out["episodes_with_max_repeat_ge_5"] = sum(1 for r in rows if r["max_repeat"] >= 5)
    out["episodes_with_any_repetition"] = sum(1 for r in rows if r["max_repeat"] >= 2)
    out["episodes_with_all_repeats_same_returncode"] = sum(
        1 for r in rows if r["repeated_commands_all_same_returncode"] is True
    )
    out["episodes_with_some_repeat_varying_returncode"] = sum(
        1 for r in rows if r["repeated_commands_all_same_returncode"] is False
    )
    out["episodes_with_no_checkable_repeat"] = sum(
        1 for r in rows if r["repeated_commands_all_same_returncode"] is None
    )
    out["episodes_with_a_differing_observation_repeat"] = sum(
        1 for r in rows if r["differing_observation_repeats"] > 0
    )
    out["episodes_with_every_repeat_observation_identical"] = sum(
        1
        for r in rows
        if r["repeated_command_occurrences"] > 0 and r["differing_observation_repeats"] == 0
    )
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="compute and print, do not write the artifact")
    args = ap.parse_args()

    rows = []
    for cohort, rel in COHORTS.items():
        cdir = REPO_ROOT / rel
        run_ids = sorted(
            d.name for d in cdir.iterdir() if d.is_dir() and (d / "trajectory.json").is_file()
        )
        for run_id in run_ids:
            rows.append(analyse_episode(cohort, rel, run_id))

    rows.sort(key=lambda r: (r["cohort"], r["instance_id"], r["backend"]))

    bad_actions = sum(r["_assistant_messages_with_action_count_not_1"] for r in rows)
    for r in rows:
        r.pop("_assistant_messages_with_action_count_not_1")

    per_cohort = {c: aggregate([r for r in rows if r["cohort"] == c]) for c in COHORTS}
    backends = sorted({r["backend"] for r in rows})
    per_backend = {b: aggregate([r for r in rows if r["backend"] == b]) for b in backends}
    per_cohort_backend = {
        f"{c}/{b}": aggregate([r for r in rows if r["cohort"] == c and r["backend"] == b])
        for c in COHORTS
        for b in backends
    }

    # cross-cohort pairing on the same (instance_id, backend) assignment
    by_key = {}
    for r in rows:
        by_key.setdefault((r["instance_id"], r["backend"]), {})[r["cohort"]] = r
    paired = [v for v in by_key.values() if len(v) == 2]
    same_class = sum(
        1 for v in paired if v["legacy"]["classification"] == v["yaml-v1"]["classification"]
    )
    same_period = sum(
        1
        for v in paired
        if v["legacy"]["terminal_cycle_period"] == v["yaml-v1"]["terminal_cycle_period"]
    )
    identical_seq = sum(
        1
        for v in paired
        if v["legacy"]["command_sequence_sha256"] == v["yaml-v1"]["command_sequence_sha256"]
    )
    divergent = [
        {
            "instance_id": v["legacy"]["instance_id"],
            "backend": v["legacy"]["backend"],
            "legacy": {
                k: v["legacy"][k]
                for k in ("total_commands", "classification", "terminal_cycle_period",
                          "terminal_cycle_repeats", "exit_status")
            },
            "yaml-v1": {
                k: v["yaml-v1"][k]
                for k in ("total_commands", "classification", "terminal_cycle_period",
                          "terminal_cycle_repeats", "exit_status")
            },
        }
        for v in paired
        if v["legacy"]["command_sequence_sha256"] != v["yaml-v1"]["command_sequence_sha256"]
    ]
    divergent.sort(key=lambda r: (r["instance_id"], r["backend"]))

    artifact = OrderedDict(
        [
            ("request", "DTR-REQ-002"),
            ("artifact", OUT_REL),
            ("kind", "descriptive repetition/loop taxonomy over committed block-1 records"),
            (
                "scope",
                "All 32 committed episodes of the two block-1 cohorts (8 instances x 2 backends x 2 "
                "cohorts). Counts and classifications only: no causal claim, no efficacy claim, no "
                "recommendation about study design.",
            ),
            ("source_dirs", {c: rel for c, rel in COHORTS.items()}),
            ("generated_by", "experiments/v2_agent/analysis/repetition_taxonomy.py"),
            ("definitions", DEFINITIONS),
            ("classification_labels", CLASSES),
            (
                "known_context_not_recomputed_here",
                "All 32 episodes produced an empty submission and were graded operational_zero; step "
                "limit H=24 logical calls, temperature 0, 16384-token server context, 1536 max "
                "response tokens. Carried from the committed reports; not re-derived by this script.",
            ),
            ("per_cohort", per_cohort),
            ("per_backend", per_backend),
            ("per_cohort_backend", per_cohort_backend),
            ("overall", aggregate(rows)),
            (
                "cross_cohort_pairing",
                {
                    "note": (
                        "Same (instance_id, backend) assignment in both cohorts. Agreement counts only. "
                        "The two cohorts differ in harness configuration and in run time; this artifact "
                        "reports how often the recorded command sequence and the taxonomy label agree, "
                        "and does not attribute the agreements or the divergences to any cause."
                    ),
                    "paired_assignments": len(paired),
                    "identical_command_sequence": identical_seq,
                    "same_classification": same_class,
                    "same_terminal_cycle_period": same_period,
                    "divergent_assignments": divergent,
                },
            ),
            (
                "integrity",
                {
                    "episodes_analysed": len(rows),
                    "assistant_messages_with_action_count_not_1": bad_actions,
                    "cohorts": {c: sum(1 for r in rows if r["cohort"] == c) for c in COHORTS},
                    "backends": {b: sum(1 for r in rows if r["backend"] == b) for b in backends},
                },
            ),
            (
                "ambiguities_and_limitations",
                [
                    "Command identity is byte-exact. Two commands that are semantically the same but "
                    "differ in whitespace, quoting or argument order count as distinct, so "
                    "distinct_commands is an upper bound on semantically distinct actions and "
                    "max_repeat is a lower bound on semantic repetition.",
                    "n_model_calls exceeds total_commands in 7 of the 32 episodes: a model call whose "
                    "response carried two actions was rejected by the harness and left no assistant "
                    "message in the saved trajectory, and a final call that failed (the context-window "
                    "error) likewise left none. Those two account for every unrecorded call here "
                    "(residual_unexplained_calls is 0 in all 32 episodes). Cycle periods and start "
                    "indices are therefore indexed on RECORDED COMMANDS, which is the sequence the "
                    "agent actually executed, not on the model-call index.",
                    "Whether an episode 'ends' in a cycle is defined on the recorded command sequence "
                    "only. Episodes that ended on a harness error rather than the step limit stopped "
                    "for a reason outside the command sequence; the taxonomy records the observed "
                    "sequence and does not assert why the episode stopped.",
                    "A byte-identical observation on a repeated command means the agent was shown the "
                    "same bytes again. It does not establish why the command was re-issued, and it "
                    "does not by itself establish that the container state was unchanged: an "
                    "idempotent read of changed state, and a command whose output was truncated or "
                    "elided identically, both produce identical bytes. The count is a count of "
                    "identical observations, not of 'no state change'.",
                    "The smallest period p is reported for a terminal cycle, as requested. A run of m "
                    "identical commands is also consistent with p=2, p=3, ... at lower k; the smallest-p "
                    "rule assigns it p=1. Periods above 6 were not searched, so an episode with a "
                    "period-7-or-longer terminal cycle would be recorded here as having none.",
                    "repeated_commands_all_same_returncode is computed only over repeated commands whose "
                    "every occurrence has an observation; it is null for an episode with no such "
                    "command (single-call episodes, and episodes with no repetition).",
                    "Both cohorts are fixed-backend development pilots, not a routing policy estimate. "
                    "Differences between cohorts or backends reported here are descriptive counts over "
                    "8 assignments per cell.",
                ],
            ),
            ("episodes", rows),
        ]
    )

    payload = json.dumps(artifact, indent=1, sort_keys=False)

    # Guard: the artifact must carry no local account path. Paths must be repo-relative.
    home = Path.home()
    for forbidden in {home.name, str(home), str(REPO_ROOT)}:
        if forbidden and forbidden in payload:
            raise SystemExit(f"refusing to write: artifact contains local path component {forbidden!r}")

    if args.dry_run:
        print(json.dumps({k: artifact[k] for k in ("per_cohort", "per_backend", "overall", "integrity")}, indent=1))
        return 0

    out_path = REPO_ROOT / OUT_REL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "x") as fh:  # write-once
        fh.write(payload + "\n")
    print(f"wrote {OUT_REL} ({len(payload)} bytes, {len(rows)} episodes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
