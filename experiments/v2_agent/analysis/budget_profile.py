#!/usr/bin/env python3
"""Descriptive budget/context profile for the REQ-002 v2_agent pilot cohorts.

Dimension: context growth and budget exhaustion across all 32 committed episodes
(2 cohorts x 8 tasks x 2 backends), computed from the per-episode attempt ledgers.

This is DESCRIPTIVE ONLY. It reports counts, per-call token series and a
classification of each episode's terminating constraint. It makes no causal,
efficacy or study-design claim. Where a mechanism cannot be settled from the
committed artifacts, the artifact says so explicitly in an "ambiguities" field.

Reads only. Writes exactly one JSON file, opened with mode 'x' (write-once).

Usage:
    .venv/bin/python experiments/v2_agent/analysis/budget_profile.py
"""

from __future__ import annotations

import json
import os
import re
import statistics
from typing import Any

# --- repo-relative layout -------------------------------------------------
# Resolved from this file's location so no absolute host path is baked in and
# no host username can leak into the output artifact.
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

COHORTS = {
    # cohort label -> repo-relative cohort directory
    "legacy": "results/v2_agent/pilot_20260922",
    "yaml-v1": "results/v2_agent/pilot_20260922_yaml_v1",
}
COHORT_REPORTS = {
    "legacy": "results/v2_agent/pilot_20260922/report_block1_final.json",
    "yaml-v1": "results/v2_agent/pilot_20260922_yaml_v1/report_yaml_v1_block1_final.json",
}
OUT_PATH = "results/v2_agent/analysis_20260922/budget_profile.json"

# Frozen harness constants, re-verified per episode against episode.json.
STEP_LIMIT_H = 24
CONTEXT_WINDOW_TOKENS = 16384
WALL_LIMIT_S = 1800
MAX_RESPONSE_TOKENS = 1536

# Analyst-chosen reporting thresholds. These are presentation conventions for
# the phrase "nowhere near <limit>", not harness settings and not inferences.
NEAR_CONTEXT_FRACTIONS = (0.50, 0.75, 0.90)
NEAR_STEP_FRACTIONS = (0.50, 0.75, 0.90)

# Matches the llama.cpp / litellm context-overflow detail text, e.g.
#   "... request (16610 tokens) exceeds the available context size (16384 tokens) ..."
REQUESTED_TOKENS_RE = re.compile(
    r"request \((?P<requested>\d+) tokens\) exceeds the available context size "
    r"\((?P<available>\d+) tokens\)"
)


def rp(*parts: str) -> str:
    """Repo-relative path -> absolute path on disk."""
    return os.path.join(REPO_ROOT, *parts)


def parse_run_id(run_id: str) -> dict[str, str]:
    """Split a run_id of the form <instance_id>__<backend>__<binding>__<tsZ>-<hex>.

    instance_id itself contains '__' (e.g. 'astropy__astropy-12907'), so the
    trailing fields are taken from the END of the split, never by index.
    """
    parts = run_id.split("__")
    if len(parts) < 4:
        raise ValueError(f"unparseable run_id: {run_id!r}")
    tail = parts[-1]  # "<timestampZ>-<hex>"
    if "-" not in tail:
        raise ValueError(f"unparseable run_id tail: {run_id!r}")
    timestamp, _, suffix = tail.partition("-")
    return {
        "instance_id": "__".join(parts[:-3]),
        "backend": parts[-3],
        "binding": parts[-2],
        "timestamp": timestamp,
        "suffix": suffix,
    }


def load_attempts(path: str) -> tuple[list[dict[str, Any]], str, dict[str, int]]:
    """Return (physical attempt records, detected ledger format, ledger stats).

    Legacy format: one record per physical attempt, no "event" key.
    yaml-v1 format: two records per attempt, {"event":"start"} then
    {"event":"result"}. Only the "result" records carry the outcome; a "start"
    with no matching "result" is an incomplete attempt and is counted, not
    silently dropped.
    """
    raw: list[dict[str, Any]] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                raw.append(json.loads(line))

    has_event = any("event" in r for r in raw)
    if not has_event:
        stats = {
            "raw_records": len(raw),
            "start_events": 0,
            "result_events": 0,
            "starts_without_result": 0,
        }
        return raw, "legacy_one_record_per_attempt", stats

    if not all("event" in r for r in raw):
        raise ValueError(f"mixed event/no-event records in {path}")

    starts = [r for r in raw if r["event"] == "start"]
    results = [r for r in raw if r["event"] == "result"]
    other = [r for r in raw if r["event"] not in ("start", "result")]
    if other:
        raise ValueError(f"unexpected event kinds in {path}: "
                         f"{sorted({r['event'] for r in other})}")

    result_keys = {(r["call"], r["attempt"]) for r in results}
    orphan_starts = [r for r in starts if (r["call"], r["attempt"]) not in result_keys]
    stats = {
        "raw_records": len(raw),
        "start_events": len(starts),
        "result_events": len(results),
        "starts_without_result": len(orphan_starts),
    }
    return results, "yaml_v1_start_result_pairs", stats


def pairwise_diffs(series: list[int]) -> list[int]:
    return [b - a for a, b in zip(series, series[1:])]


def classify_terminating_constraint(episode: dict[str, Any]) -> tuple[str, list[str]]:
    """Map episode.json exit_status (the authority) onto the requested taxonomy."""
    notes: list[str] = []
    status = episode.get("exit_status")
    calls = episode.get("n_model_calls")
    wall = episode.get("wall_seconds")

    if status == "LimitsExceeded":
        label = "step_limit_H24"
        if calls != STEP_LIMIT_H:
            notes.append(
                f"exit_status=LimitsExceeded but n_model_calls={calls} != H={STEP_LIMIT_H}; "
                "which limit the harness tripped is AMBIGUOUS from the committed artifacts"
            )
        if wall is not None and wall >= WALL_LIMIT_S:
            notes.append(
                f"wall_seconds={wall} reached the {WALL_LIMIT_S}s wall limit, so "
                "'LimitsExceeded' is AMBIGUOUS between the step and wall budgets"
            )
    elif status == "ContextWindowExceededError":
        label = "context_window"
    elif status == "Submitted":
        label = "submitted"
    else:
        label = "other"
        notes.append(f"exit_status={status!r} is not in the requested taxonomy")
    return label, notes


def profile_episode(cohort: str, run_dir_rel: str) -> dict[str, Any]:
    run_id = os.path.basename(run_dir_rel)
    parsed = parse_run_id(run_id)

    episode = json.load(open(rp(run_dir_rel, "episode.json"), encoding="utf-8"))
    attempts, ledger_format, ledger_stats = load_attempts(
        rp(run_dir_rel, "attempts.jsonl")
    )

    # Cross-check the run_id parse against the episode record's own fields.
    id_agreement = {
        "instance_id_matches_run_id": parsed["instance_id"] == episode.get("instance_id"),
        "backend_matches_run_id": parsed["backend"] == episode.get("backend"),
        "run_id_matches_dirname": episode.get("run_id") == run_id,
    }

    settings = episode.get("settings", {})
    server = episode.get("server", {})
    harness = {
        "step_limit": settings.get("step_limit"),
        "wall_time_limit_seconds": settings.get("wall_time_limit_seconds"),
        "temperature": settings.get("temperature"),
        "max_response_tokens": settings.get("max_tokens"),
        "n_ctx_per_slot": server.get("n_ctx_per_slot"),
        "physical_attempts_per_call_max": settings.get("physical_attempts_per_call_max"),
        "matches_frozen_constants": (
            settings.get("step_limit") == STEP_LIMIT_H
            and settings.get("wall_time_limit_seconds") == WALL_LIMIT_S
            and settings.get("max_tokens") == MAX_RESPONSE_TOKENS
            and server.get("n_ctx_per_slot") == CONTEXT_WINDOW_TOKENS
        ),
    }

    # --- per-attempt split ------------------------------------------------
    answered = [a for a in attempts if a.get("ok") is True]
    failed = [a for a in attempts if a.get("ok") is not True]

    prompt_series = [
        {"call": a["call"], "attempt": a["attempt"], "prompt_tokens": a["prompt_tokens"]}
        for a in answered
        if a.get("prompt_tokens") is not None
    ]
    prompt_values = [p["prompt_tokens"] for p in prompt_series]
    completion_values = [
        a["completion_tokens"] for a in answered if a.get("completion_tokens") is not None
    ]

    diffs = pairwise_diffs(prompt_values)
    mean_growth = (sum(diffs) / len(diffs)) if diffs else None

    finish_reasons: dict[str, int] = {}
    for a in answered:
        fr = a.get("finish_reason")
        key = "null" if fr is None else str(fr)
        finish_reasons[key] = finish_reasons.get(key, 0) + 1

    # --- failed physical attempts ----------------------------------------
    failed_records: list[dict[str, Any]] = []
    error_type_counts: dict[str, int] = {}
    for a in failed:
        etype = a.get("error") or "unknown"
        error_type_counts[etype] = error_type_counts.get(etype, 0) + 1
        detail = a.get("detail")
        rec: dict[str, Any] = {
            "call": a.get("call"),
            "attempt": a.get("attempt"),
            "error_type": etype,
            "detail_present": detail is not None,
            "requested_tokens": None,
            "available_context_tokens": None,
            "parsed_literal_substring": None,
            "parse_note": None,
        }
        if detail:
            m = REQUESTED_TOKENS_RE.search(detail)
            if m:
                rec["requested_tokens"] = int(m.group("requested"))
                rec["available_context_tokens"] = int(m.group("available"))
                # Quote the exact substring the numbers were read from.
                rec["parsed_literal_substring"] = detail[m.start():m.end()]
            else:
                rec["parse_note"] = (
                    "no 'request (N tokens) exceeds the available context size (M tokens)' "
                    "substring found in the error detail"
                )
                rec["detail_text"] = detail
        failed_records.append(rec)

    context_requests = [r["requested_tokens"] for r in failed_records
                        if r["requested_tokens"] is not None]

    # --- terminating constraint + distance to the OTHER limits ------------
    label, notes = classify_terminating_constraint(episode)
    n_calls = episode.get("n_model_calls")
    wall = episode.get("wall_seconds")
    max_prompt = max(prompt_values) if prompt_values else None
    final_prompt = prompt_values[-1] if prompt_values else None

    distance = {
        "logical_calls_issued": n_calls,
        "calls_remaining_before_H24": (
            STEP_LIMIT_H - n_calls if isinstance(n_calls, int) else None
        ),
        "fraction_of_step_budget_used": (
            round(n_calls / STEP_LIMIT_H, 6) if isinstance(n_calls, int) else None
        ),
        "max_answered_prompt_tokens": max_prompt,
        "context_headroom_tokens_at_max_answered": (
            CONTEXT_WINDOW_TOKENS - max_prompt if max_prompt is not None else None
        ),
        "fraction_of_context_used_at_max_answered": (
            round(max_prompt / CONTEXT_WINDOW_TOKENS, 6) if max_prompt is not None else None
        ),
        "final_answered_prompt_tokens": final_prompt,
        "context_headroom_tokens_at_final_answered": (
            CONTEXT_WINDOW_TOKENS - final_prompt if final_prompt is not None else None
        ),
        "wall_seconds": wall,
        "wall_seconds_remaining": (
            WALL_LIMIT_S - wall if isinstance(wall, (int, float)) else None
        ),
        "fraction_of_wall_budget_used": (
            round(wall / WALL_LIMIT_S, 6) if isinstance(wall, (int, float)) else None
        ),
    }
    # Arithmetic extrapolation only: headroom divided by observed mean growth.
    # This is a restatement of the observed series, NOT a prediction of what the
    # episode would have done with a larger step budget.
    if (
        label == "step_limit_H24"
        and final_prompt is not None
        and mean_growth is not None
        and mean_growth > 0
    ):
        distance["extra_calls_to_reach_context_at_observed_mean_growth"] = round(
            (CONTEXT_WINDOW_TOKENS - final_prompt) / mean_growth, 2
        )
        distance["extrapolation_caveat"] = (
            "arithmetic restatement of headroom / observed mean growth; growth was "
            "not uniform in every episode, so this is NOT a forecast"
        )
    if label == "context_window" and context_requests:
        distance["overflow_request_tokens"] = max(context_requests)
        distance["overflow_excess_over_context"] = (
            max(context_requests) - CONTEXT_WINDOW_TOKENS
        )

    # Episodes that hit the step budget and the context ceiling on the same call
    # cannot be attributed to one budget alone from these artifacts.
    simultaneous = (
        label == "context_window"
        and isinstance(n_calls, int)
        and n_calls == STEP_LIMIT_H
    )
    if simultaneous:
        notes.append(
            f"the overflowing call was call {n_calls}, i.e. the last call the H={STEP_LIMIT_H} "
            "step budget allows; this episode was simultaneously at the step limit, so which "
            "budget 'would have' stopped it is AMBIGUOUS"
        )

    # --- episode-level token accounting cross-check -----------------------
    ep_prompt = episode.get("prompt_tokens")
    ep_known_prompt = episode.get("known_prompt_tokens")
    ep_completion = episode.get("completion_tokens")
    ep_known_completion = episode.get("known_completion_tokens")
    recomputed_prompt = sum(prompt_values)
    recomputed_completion = sum(completion_values)
    accounting = {
        "recomputed_prompt_tokens_sum_over_answered_calls": recomputed_prompt,
        "recomputed_completion_tokens_sum_over_answered_calls": recomputed_completion,
        "episode_json_prompt_tokens": ep_prompt,
        "episode_json_known_prompt_tokens": ep_known_prompt,
        "episode_json_completion_tokens": ep_completion,
        "episode_json_known_completion_tokens": ep_known_completion,
        "prompt_agrees_with_episode_json": (
            recomputed_prompt == ep_prompt
            if ep_prompt is not None
            else recomputed_prompt == ep_known_prompt
        ),
        "completion_agrees_with_episode_json": (
            recomputed_completion == ep_completion
            if ep_completion is not None
            else recomputed_completion == ep_known_completion
        ),
        "episode_json_reports_totals_as_null": ep_prompt is None,
        "note": (
            "the two cohorts use different null conventions for an episode containing a "
            "failed attempt: the legacy ledger's episode.json still reports prompt_tokens/"
            "completion_tokens as the sum over answered calls, while yaml-v1 sets those to "
            "null and carries the same sum in known_prompt_tokens/known_completion_tokens"
        ),
    }

    physical_ok = episode.get("physical_requests") == len(attempts)
    failed_ok = episode.get("failed_attempts") == len(failed)

    return {
        "cohort": cohort,
        "run_id": run_id,
        "run_dir": run_dir_rel,
        "instance_id": parsed["instance_id"],
        "backend": parsed["backend"],
        "binding": parsed["binding"],
        "started_timestamp_utc": parsed["timestamp"],
        "ledger_format": ledger_format,
        "ledger_stats": ledger_stats,
        "harness": harness,
        "exit_status": episode.get("exit_status"),
        "terminating_constraint": label,
        "terminating_constraint_authority": "episode.json exit_status",
        "at_step_limit_and_context_overflow_same_call": simultaneous,
        "submission_empty": episode.get("submission_empty"),
        "submission_bytes": episode.get("submission_bytes"),
        "calls": {
            "logical_calls": n_calls,
            "physical_attempts_in_ledger": len(attempts),
            "answered_attempts": len(answered),
            "failed_attempts": len(failed),
            "max_attempts_on_one_call": episode.get("max_attempts_on_one_call"),
            "physical_requests_agrees_with_episode_json": physical_ok,
            "failed_attempts_agrees_with_episode_json": failed_ok,
        },
        "prompt_token_series": prompt_series,
        "prompt_token_stats": {
            "n_answered_calls": len(prompt_values),
            "first": prompt_values[0] if prompt_values else None,
            "final_answered": final_prompt,
            "max": max_prompt,
            "mean_per_call_growth": (
                round(mean_growth, 4) if mean_growth is not None else None
            ),
            "mean_per_call_growth_definition": (
                "mean of consecutive differences over answered calls, i.e. "
                "(final - first) / (n_answered - 1); null when fewer than 2 answered calls"
            ),
            "median_per_call_growth": (
                statistics.median(diffs) if diffs else None
            ),
            "min_per_call_growth": min(diffs) if diffs else None,
            "max_per_call_growth": max(diffs) if diffs else None,
            "per_call_growth_series": diffs,
        },
        "completion_tokens_total": recomputed_completion,
        "completion_token_stats": {
            "n_answered_calls": len(completion_values),
            "max": max(completion_values) if completion_values else None,
            "mean": (
                round(sum(completion_values) / len(completion_values), 4)
                if completion_values
                else None
            ),
            "calls_at_max_response_tokens_cap": sum(
                1 for v in completion_values if v >= MAX_RESPONSE_TOKENS
            ),
            "finish_reason_counts": finish_reasons,
        },
        "failed_attempt_records": failed_records,
        "failed_attempt_error_type_counts": error_type_counts,
        "distance_to_other_limits": distance,
        "token_accounting_cross_check": accounting,
        "run_id_parse_cross_check": id_agreement,
        "ambiguities": notes,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts over an arbitrary group of episodes. Counts only, no inference."""
    by_constraint: dict[str, int] = {}
    by_exit: dict[str, int] = {}
    for r in rows:
        by_constraint[r["terminating_constraint"]] = (
            by_constraint.get(r["terminating_constraint"], 0) + 1
        )
        by_exit[str(r["exit_status"])] = by_exit.get(str(r["exit_status"]), 0) + 1

    step_rows = [r for r in rows if r["terminating_constraint"] == "step_limit_H24"]
    ctx_rows = [r for r in rows if r["terminating_constraint"] == "context_window"]

    step_max_prompts = [
        r["prompt_token_stats"]["max"] for r in step_rows
        if r["prompt_token_stats"]["max"] is not None
    ]
    step_growths = [
        r["prompt_token_stats"]["mean_per_call_growth"] for r in step_rows
        if r["prompt_token_stats"]["mean_per_call_growth"] is not None
    ]
    ctx_calls = [
        r["calls"]["logical_calls"] for r in ctx_rows
        if r["calls"]["logical_calls"] is not None
    ]

    step_far_from_context = {}
    for frac in NEAR_CONTEXT_FRACTIONS:
        thresh = CONTEXT_WINDOW_TOKENS * frac
        step_far_from_context[f"max_prompt_below_{int(frac * 100)}pct_of_context"] = sum(
            1 for v in step_max_prompts if v < thresh
        )
    ctx_far_from_step = {}
    for frac in NEAR_STEP_FRACTIONS:
        thresh = STEP_LIMIT_H * frac
        ctx_far_from_step[f"logical_calls_below_{int(frac * 100)}pct_of_H24"] = sum(
            1 for v in ctx_calls if v < thresh
        )

    all_prompt_maxes = [
        r["prompt_token_stats"]["max"] for r in rows
        if r["prompt_token_stats"]["max"] is not None
    ]
    all_walls = [
        r["distance_to_other_limits"]["wall_seconds"] for r in rows
        if r["distance_to_other_limits"]["wall_seconds"] is not None
    ]

    return {
        "episodes": len(rows),
        "terminating_constraint_counts": by_constraint,
        "exit_status_counts": by_exit,
        "failed_physical_attempts_total": sum(r["calls"]["failed_attempts"] for r in rows),
        "failed_attempt_error_type_counts": {
            k: sum(r["failed_attempt_error_type_counts"].get(k, 0) for r in rows)
            for k in sorted(
                {k for r in rows for k in r["failed_attempt_error_type_counts"]}
            )
        },
        "logical_calls_total": sum(
            r["calls"]["logical_calls"] or 0 for r in rows
        ),
        "physical_attempts_total": sum(
            r["calls"]["physical_attempts_in_ledger"] for r in rows
        ),
        "prompt_tokens_total_over_answered_calls": sum(
            r["token_accounting_cross_check"][
                "recomputed_prompt_tokens_sum_over_answered_calls"
            ]
            for r in rows
        ),
        "completion_tokens_total_over_answered_calls": sum(
            r["completion_tokens_total"] for r in rows
        ),
        "step_limit_episodes": {
            "count": len(step_rows),
            "max_answered_prompt_tokens_min": min(step_max_prompts) if step_max_prompts else None,
            "max_answered_prompt_tokens_max": max(step_max_prompts) if step_max_prompts else None,
            "max_answered_prompt_tokens_median": (
                statistics.median(step_max_prompts) if step_max_prompts else None
            ),
            "context_headroom_tokens_min": (
                CONTEXT_WINDOW_TOKENS - max(step_max_prompts) if step_max_prompts else None
            ),
            "context_headroom_tokens_max": (
                CONTEXT_WINDOW_TOKENS - min(step_max_prompts) if step_max_prompts else None
            ),
            "mean_per_call_growth_min": min(step_growths) if step_growths else None,
            "mean_per_call_growth_max": max(step_growths) if step_growths else None,
            "mean_per_call_growth_median": (
                round(statistics.median(step_growths), 4) if step_growths else None
            ),
            "distance_from_context_limit": step_far_from_context,
        },
        "context_window_episodes": {
            "count": len(ctx_rows),
            "logical_calls_used": sorted(ctx_calls),
            "logical_calls_min": min(ctx_calls) if ctx_calls else None,
            "logical_calls_max": max(ctx_calls) if ctx_calls else None,
            "distance_from_step_limit": ctx_far_from_step,
            "also_at_step_limit_on_the_overflowing_call": sum(
                1 for r in ctx_rows if r["at_step_limit_and_context_overflow_same_call"]
            ),
            "overflow_request_tokens": sorted(
                r["distance_to_other_limits"]["overflow_request_tokens"]
                for r in ctx_rows
                if "overflow_request_tokens" in r["distance_to_other_limits"]
            ),
        },
        "submitted_episodes": {
            "count": sum(1 for r in rows if r["terminating_constraint"] == "submitted"),
            "logical_calls_used": sorted(
                r["calls"]["logical_calls"] for r in rows
                if r["terminating_constraint"] == "submitted"
            ),
        },
        "wall_clock": {
            "episodes_reaching_wall_limit": sum(
                1 for v in all_walls if v >= WALL_LIMIT_S
            ),
            "wall_seconds_max": max(all_walls) if all_walls else None,
            "wall_seconds_max_as_fraction_of_limit": (
                round(max(all_walls) / WALL_LIMIT_S, 6) if all_walls else None
            ),
        },
        "context_utilisation_all_episodes": {
            "max_answered_prompt_tokens_min": min(all_prompt_maxes) if all_prompt_maxes else None,
            "max_answered_prompt_tokens_max": max(all_prompt_maxes) if all_prompt_maxes else None,
            "episodes_whose_max_answered_prompt_exceeded_half_the_context": sum(
                1 for v in all_prompt_maxes if v > CONTEXT_WINDOW_TOKENS / 2
            ),
        },
    }


def main() -> None:
    out_abs = rp(OUT_PATH)
    if os.path.exists(out_abs):
        raise SystemExit(
            f"refusing to overwrite existing write-once artifact: {OUT_PATH}"
        )

    episodes: list[dict[str, Any]] = []
    for cohort, cohort_dir in COHORTS.items():
        base = rp(cohort_dir)
        for name in sorted(os.listdir(base)):
            run_dir = os.path.join(base, name)
            if not os.path.isdir(run_dir):
                continue
            if not os.path.exists(os.path.join(run_dir, "episode.json")):
                continue
            episodes.append(profile_episode(cohort, f"{cohort_dir}/{name}"))

    # --- task-level pairing across cohorts (counts only) ------------------
    pairs: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
    for e in episodes:
        pairs.setdefault((e["instance_id"], e["backend"]), {})[e["cohort"]] = e
    cross_cohort = []
    for (inst, backend), per_cohort in sorted(pairs.items()):
        if set(per_cohort) != set(COHORTS):
            continue
        a, b = per_cohort["legacy"], per_cohort["yaml-v1"]
        cross_cohort.append({
            "instance_id": inst,
            "backend": backend,
            "legacy_terminating_constraint": a["terminating_constraint"],
            "yaml_v1_terminating_constraint": b["terminating_constraint"],
            "same_terminating_constraint": (
                a["terminating_constraint"] == b["terminating_constraint"]
            ),
            "legacy_logical_calls": a["calls"]["logical_calls"],
            "yaml_v1_logical_calls": b["calls"]["logical_calls"],
            "legacy_max_answered_prompt_tokens": a["prompt_token_stats"]["max"],
            "yaml_v1_max_answered_prompt_tokens": b["prompt_token_stats"]["max"],
            "identical_prompt_token_series": (
                [p["prompt_tokens"] for p in a["prompt_token_series"]]
                == [p["prompt_tokens"] for p in b["prompt_token_series"]]
            ),
            "common_prefix_length_of_prompt_series": sum(
                1 for _ in _common_prefix(
                    [p["prompt_tokens"] for p in a["prompt_token_series"]],
                    [p["prompt_tokens"] for p in b["prompt_token_series"]],
                )
            ),
        })

    per_cohort_summary = {
        c: summarize([e for e in episodes if e["cohort"] == c]) for c in COHORTS
    }
    per_backend_summary = {
        b: summarize([e for e in episodes if e["backend"] == b])
        for b in sorted({e["backend"] for e in episodes})
    }
    per_cohort_backend_summary = {
        f"{c}|{b}": summarize(
            [e for e in episodes if e["cohort"] == c and e["backend"] == b]
        )
        for c in COHORTS
        for b in sorted({e["backend"] for e in episodes})
    }

    integrity = {
        "episodes_profiled": len(episodes),
        "expected_episodes": 32,
        "all_run_id_parses_agree_with_episode_json": all(
            all(e["run_id_parse_cross_check"].values()) for e in episodes
        ),
        "all_harness_settings_match_frozen_constants": all(
            e["harness"]["matches_frozen_constants"] for e in episodes
        ),
        "all_physical_request_counts_agree": all(
            e["calls"]["physical_requests_agrees_with_episode_json"] for e in episodes
        ),
        "all_failed_attempt_counts_agree": all(
            e["calls"]["failed_attempts_agrees_with_episode_json"] for e in episodes
        ),
        "all_prompt_token_sums_agree_with_episode_json": all(
            e["token_accounting_cross_check"]["prompt_agrees_with_episode_json"]
            for e in episodes
        ),
        "all_completion_token_sums_agree_with_episode_json": all(
            e["token_accounting_cross_check"]["completion_agrees_with_episode_json"]
            for e in episodes
        ),
        "ledger_format_counts": {
            fmt: sum(1 for e in episodes if e["ledger_format"] == fmt)
            for fmt in sorted({e["ledger_format"] for e in episodes})
        },
        "starts_without_result_total": sum(
            e["ledger_stats"]["starts_without_result"] for e in episodes
        ),
        "episodes_with_unparsed_error_detail": sum(
            1 for e in episodes
            for r in e["failed_attempt_records"]
            if r["error_type"] == "ContextWindowExceededError"
            and r["requested_tokens"] is None
        ),
        "episodes_with_retried_calls": sum(
            1 for e in episodes if (e["calls"]["max_attempts_on_one_call"] or 0) > 1
        ),
    }

    # Cross-check exit_status tallies against the committed cohort reports.
    report_cross_check = {}
    for cohort, rel in COHORT_REPORTS.items():
        rep = json.load(open(rp(rel), encoding="utf-8"))
        rep_counts: dict[str, int] = {}
        for backend, blob in rep.get("backends", {}).items():
            for status, n in blob.get("exit_status", {}).items():
                rep_counts[status] = rep_counts.get(status, 0) + n
        mine = per_cohort_summary[cohort]["exit_status_counts"]
        report_cross_check[cohort] = {
            "committed_report": rel,
            "report_exit_status_counts": rep_counts,
            "recomputed_exit_status_counts": mine,
            "agree": rep_counts == mine,
        }

    artifact = {
        "artifact": OUT_PATH,
        "script": "experiments/v2_agent/analysis/budget_profile.py",
        "request": "DTR-REQ-002",
        "dimension": "context growth and budget exhaustion across all 32 pilot episodes",
        "kind": (
            "DESCRIPTIVE worker analysis of already-completed episodes: counts and "
            "classifications only. No model, server, container or evaluator was run. "
            "Contains no causal claim, no efficacy claim and no study-design recommendation."
        ),
        "scope_note": (
            "Every number is computed over the COMPLETE set of committed attempt ledgers "
            "for both cohorts (32/32 episodes), never over a printed subset or a sample."
        ),
        "constants": {
            "step_limit_H": STEP_LIMIT_H,
            "context_window_tokens": CONTEXT_WINDOW_TOKENS,
            "wall_time_limit_seconds": WALL_LIMIT_S,
            "max_response_tokens": MAX_RESPONSE_TOKENS,
            "temperature": 0.0,
            "source": "re-read from each episode.json settings/server block, not assumed",
        },
        "reporting_thresholds": {
            "note": (
                "'nowhere near limit X' has no harness definition; the fractions below are "
                "ANALYST-CHOSEN presentation conventions reported at several cut points so "
                "the counts do not depend on one arbitrary choice"
            ),
            "context_fractions": list(NEAR_CONTEXT_FRACTIONS),
            "step_fractions": list(NEAR_STEP_FRACTIONS),
        },
        "integrity_checks": integrity,
        "committed_report_cross_check": report_cross_check,
        "summary_all_32": summarize(episodes),
        "summary_per_cohort": per_cohort_summary,
        "summary_per_backend": per_backend_summary,
        "summary_per_cohort_and_backend": per_cohort_backend_summary,
        "cross_cohort_task_pairs": cross_cohort,
        "episodes": episodes,
    }

    os.makedirs(os.path.dirname(out_abs), exist_ok=True)
    with open(out_abs, "x", encoding="utf-8") as fh:
        json.dump(artifact, fh, indent=1, sort_keys=False)
        fh.write("\n")
    print(f"wrote {OUT_PATH}")


def _common_prefix(a: list[int], b: list[int]):
    for x, y in zip(a, b):
        if x != y:
            return
        yield x


if __name__ == "__main__":
    main()
