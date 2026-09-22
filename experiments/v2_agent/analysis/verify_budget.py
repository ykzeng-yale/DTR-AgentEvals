#!/usr/bin/env python3
"""Independent re-derivation of the "context and budget profile" claims.

This is an ADVERSARIAL CHECKER for results/v2_agent/analysis_20260922/budget_profile.json.
It does not import or reuse experiments/v2_agent/analysis/budget_profile.py.

Deliberately different route from the artifact's own script:
  * every ledger record is reduced by (call, attempt) into ONE merged dict, so
    the two on-disk ledger shapes collapse to a single shape BEFORE any
    arithmetic; no per-cohort format branch appears in the counting code.
  * ledger format is detected by comparing raw line count to merged attempt
    count (2x -> start/result pairs, 1x -> one record per attempt), not by
    probing for an 'event' key.
  * logical call counts are re-derived three ways -- distinct 'call' ids in the
    ledger, episode.json n_model_calls, and trajectory.json message walk -- and
    the three are compared.
  * run_id is parsed with rsplit("__", 1) so the timestamp always comes from
    the LAST "__" segment, never from a positional index.

DESCRIPTIVE only: counts and classifications. No model/server/container/evaluator
is run. Reads only; writes one new JSON with mode 'x'.
"""
import json
import os
import re
import statistics
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

# Resolved at runtime so the local account name is never written into this file.
LOCAL_USER = os.path.basename(os.path.expanduser("~"))

COHORTS = {
    "legacy": "results/v2_agent/pilot_20260922",
    "yaml-v1": "results/v2_agent/pilot_20260922_yaml_v1",
}
ARTIFACT = "results/v2_agent/analysis_20260922/budget_profile.json"
OUT_REL = "results/v2_agent/analysis_20260922/budget_profile_verification.json"

CTX = 16384
H = 24
WALL = 1800
MAXRESP = 1536

ERR_RE = re.compile(
    r"request \((\d+) tokens\) exceeds the available context size \((\d+) tokens\)")


def load_ledger(path):
    """Merge ledger rows by (call, attempt). Format-agnostic by construction."""
    merged, order = {}, []
    starts, results = set(), set()
    n_lines = 0
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            n_lines += 1
            rec = json.loads(line)
            key = (rec["call"], rec["attempt"])
            ev = rec.get("event")
            if ev == "start":
                starts.add(key)
            elif ev == "result":
                results.add(key)
            else:
                starts.add(key)
                results.add(key)
            if key not in merged:
                merged[key] = {}
                order.append(key)
            merged[key].update(rec)
    return [merged[k] for k in order], starts, results, n_lines


def walk_trajectory(path):
    """Count model turns from the message list.

    A logical call can land in the trajectory either as a role='assistant'
    message or, when the harness interrupted the step, as a role='user'
    message carrying extra.interrupt_type / extra.model_response. Counting only
    'assistant' therefore UNDERCOUNTS; both are reported so the gap is visible.
    """
    t = json.load(open(path))
    msgs = t.get("messages", [])
    assistant = sum(1 for m in msgs if m.get("role") == "assistant")
    interrupts = sum(1 for m in msgs
                     if m.get("role") == "user"
                     and isinstance(m.get("extra"), dict)
                     and "interrupt_type" in m["extra"])
    return assistant, interrupts


def collect():
    episodes = []
    fmt_counts = {"legacy_one_record_per_attempt": 0,
                  "yaml_v1_start_result_pairs": 0,
                  "unrecognised": 0}
    starts_without_result = 0
    unparsed_details = 0

    for cohort, rel in COHORTS.items():
        base = os.path.join(REPO, rel)
        for name in sorted(os.listdir(base)):
            d = os.path.join(base, name)
            if not os.path.isdir(d) or not os.path.exists(os.path.join(d, "episode.json")):
                continue
            ep = json.load(open(os.path.join(d, "episode.json")))
            recs, starts, results, n_lines = load_ledger(os.path.join(d, "attempts.jsonl"))
            starts_without_result += len(starts - results)

            if n_lines == 2 * len(recs):
                fmt = "yaml_v1_start_result_pairs"
            elif n_lines == len(recs):
                fmt = "legacy_one_record_per_attempt"
            else:
                fmt = "unrecognised"
            fmt_counts[fmt] += 1

            rid = ep["run_id"]
            head, _, last = rid.rpartition("__")       # LAST "__" segment
            ts, _, hexid = last.partition("-")
            parts = head.split("__")
            binding, backend = parts[-1], parts[-2]
            instance = "__".join(parts[:-2])

            answered = [r for r in recs if r.get("ok") is True]
            failed = [r for r in recs if r.get("ok") is not True]
            ptoks = [r["prompt_tokens"] for r in answered]
            ctoks = [r["completion_tokens"] for r in answered]

            overflow, err_types = [], defaultdict(int)
            for r in failed:
                err_types[r.get("error", "<no error key>")] += 1
                m = ERR_RE.search(r.get("detail") or "")
                if m:
                    overflow.append({"requested_tokens": int(m.group(1)),
                                     "available_tokens": int(m.group(2))})
                else:
                    unparsed_details += 1

            constraint = {"LimitsExceeded": "step_limit_H24",
                          "ContextWindowExceededError": "context_window",
                          "Submitted": "submitted"}.get(
                              ep["exit_status"], "other:" + str(ep["exit_status"]))

            growth = ((ptoks[-1] - ptoks[0]) / (len(ptoks) - 1)) if len(ptoks) >= 2 else None
            steps = [b - a for a, b in zip(ptoks, ptoks[1:])]
            assistant_msgs, interrupt_msgs = walk_trajectory(os.path.join(d, "trajectory.json"))

            episodes.append(dict(
                cohort=cohort,
                run_dir=os.path.join(rel, name),
                run_id=rid,
                instance_id=instance,
                backend_from_run_id=backend,
                backend_from_episode_json=ep["backend"],
                binding=binding,
                started_timestamp_utc=ts,
                ledger_format=fmt,
                ledger_raw_lines=n_lines,
                exit_status=ep["exit_status"],
                terminating_constraint=constraint,
                logical_calls_episode_json=ep["n_model_calls"],
                logical_calls_distinct_in_ledger=len(set(r["call"] for r in recs)),
                trajectory_assistant_messages=assistant_msgs,
                trajectory_interrupt_messages=interrupt_msgs,
                physical_attempts_ledger=len(recs),
                physical_requests_episode_json=ep["physical_requests"],
                answered_attempts=len(answered),
                failed_attempts_ledger=len(failed),
                failed_attempts_episode_json=ep["failed_attempts"],
                max_attempts_on_one_call=ep["max_attempts_on_one_call"],
                prompt_token_series=ptoks,
                max_answered_prompt_tokens=max(ptoks) if ptoks else None,
                final_answered_prompt_tokens=ptoks[-1] if ptoks else None,
                prompt_sum=sum(ptoks),
                completion_sum=sum(ctoks),
                max_completion_tokens=max(ctoks) if ctoks else None,
                calls_at_response_cap=sum(1 for c in ctoks if c >= MAXRESP),
                finish_reasons=dict((k, sum(1 for r in answered if r.get("finish_reason") == k))
                                    for k in set(r.get("finish_reason") for r in answered)),
                mean_per_call_growth=round(growth, 4) if growth is not None else None,
                max_per_call_growth=max(steps) if steps else None,
                overflow_records=overflow,
                failed_error_type_counts=dict(err_types),
                wall_seconds=ep["wall_seconds"],
                wall_time_limit_seconds=ep["settings"]["wall_time_limit_seconds"],
                step_limit_setting=ep["settings"]["step_limit"],
                max_response_tokens_setting=ep["settings"]["max_tokens"],
                n_ctx_per_slot=ep["server"]["n_ctx_per_slot"],
                episode_json_prompt_tokens=ep.get("prompt_tokens"),
                episode_json_completion_tokens=ep.get("completion_tokens"),
                episode_json_known_prompt_tokens=ep.get("known_prompt_tokens"),
                episode_json_known_completion_tokens=ep.get("known_completion_tokens"),
            ))
    return episodes, fmt_counts, starts_without_result, unparsed_details


def grouped(episodes, keyfn):
    buckets = defaultdict(list)
    for e in episodes:
        buckets[keyfn(e)].append(e)
    out = {}
    for k in sorted(buckets):
        es = buckets[k]
        sl = [x for x in es if x["terminating_constraint"] == "step_limit_H24"]
        out[k] = dict(
            episodes=len(es),
            step_limit=len(sl),
            context_window=sum(1 for x in es if x["terminating_constraint"] == "context_window"),
            submitted=sum(1 for x in es if x["terminating_constraint"] == "submitted"),
            logical_calls=sum(x["logical_calls_episode_json"] for x in es),
            prompt_tokens_over_answered_calls=sum(x["prompt_sum"] for x in es),
            completion_tokens_over_answered_calls=sum(x["completion_sum"] for x in es),
            failed_physical_attempts=sum(x["failed_attempts_ledger"] for x in es),
            step_limit_max_prompt_median=(
                statistics.median([x["max_answered_prompt_tokens"] for x in sl]) if sl else None),
            step_limit_episodes_below_half_context=sum(
                1 for x in sl if x["max_answered_prompt_tokens"] < 0.5 * CTX),
        )
    return out


def main():
    episodes, fmt_counts, starts_wo_result, unparsed = collect()
    art = json.load(open(os.path.join(REPO, ARTIFACT)))

    sl = [e for e in episodes if e["terminating_constraint"] == "step_limit_H24"]
    cw = [e for e in episodes if e["terminating_constraint"] == "context_window"]
    sub = [e for e in episodes if e["terminating_constraint"] == "submitted"]

    slmax = sorted(e["max_answered_prompt_tokens"] for e in sl)
    slgrow = sorted(e["mean_per_call_growth"] for e in sl)

    # cross-cohort cells, with truncation separated from value divergence
    by = {(e["cohort"], e["instance_id"], e["backend_from_run_id"]): e for e in episodes}
    cells = sorted(set((e["instance_id"], e["backend_from_run_id"]) for e in episodes))
    pairs = []
    for inst, bk in cells:
        a, b = by.get(("legacy", inst, bk)), by.get(("yaml-v1", inst, bk))
        pa, pb = a["prompt_token_series"], b["prompt_token_series"]
        pref = 0
        for x, y in zip(pa, pb):
            if x != y:
                break
            pref += 1
        shorter_is_prefix = pref == min(len(pa), len(pb))
        pairs.append(dict(
            instance_id=inst, backend=bk,
            legacy_answered_calls=len(pa), yaml_v1_answered_calls=len(pb),
            identical_prompt_token_series=(pa == pb),
            common_prefix_length=pref,
            differs_in_value_at_a_shared_index=not shorter_is_prefix,
            shorter_series_is_a_strict_prefix_of_the_longer=(
                shorter_is_prefix and len(pa) != len(pb)),
            legacy_terminating_constraint=a["terminating_constraint"],
            yaml_v1_terminating_constraint=b["terminating_constraint"],
        ))

    dis = dict(prompt=[], completion=[], physical_requests=[], failed_attempts=[])
    for e in episodes:
        rp = e["episode_json_prompt_tokens"]
        rp = e["episode_json_known_prompt_tokens"] if rp is None else rp
        rc = e["episode_json_completion_tokens"]
        rc = e["episode_json_known_completion_tokens"] if rc is None else rc
        if rp != e["prompt_sum"]:
            dis["prompt"].append([e["run_dir"], rp, e["prompt_sum"]])
        if rc != e["completion_sum"]:
            dis["completion"].append([e["run_dir"], rc, e["completion_sum"]])
        if e["physical_requests_episode_json"] != e["physical_attempts_ledger"]:
            dis["physical_requests"].append(
                [e["run_dir"], e["physical_requests_episode_json"], e["physical_attempts_ledger"]])
        if e["failed_attempts_episode_json"] != e["failed_attempts_ledger"]:
            dis["failed_attempts"].append(
                [e["run_dir"], e["failed_attempts_episode_json"], e["failed_attempts_ledger"]])

    allfr = defaultdict(int)
    for e in episodes:
        for k, v in e["finish_reasons"].items():
            allfr[k] += v
    allerr = defaultdict(int)
    for e in episodes:
        for k, v in e["failed_error_type_counts"].items():
            allerr[k] += v

    allmax = sorted(e["max_answered_prompt_tokens"] for e in episodes)

    # artifact self-audit
    blob = open(os.path.join(REPO, ARTIFACT)).read()
    art_ts_bad = [e["run_id"] for e in art["episodes"]
                  if e["started_timestamp_utc"] != e["run_id"].rpartition("__")[2].partition("-")[0]]
    art_cohort_bad = [e["run_id"] for e in art["episodes"]
                      if e["cohort"] != ("legacy" if "/pilot_20260922/" in e["run_dir"] else "yaml-v1")]

    out = {
        "artifact": OUT_REL,
        "script": "experiments/v2_agent/analysis/verify_budget.py",
        "request": "DTR-REQ-002",
        "role": "INDEPENDENT VERIFIER of results/v2_agent/analysis_20260922/budget_profile.json",
        "kind": "DESCRIPTIVE re-derivation: counts and classifications only. No model, "
                "server, container or evaluator was run. Contains no causal claim, no "
                "efficacy claim and no study-design recommendation.",
        "method_note": "Ledger rows merged by (call, attempt) so both on-disk shapes become "
                       "one shape before any arithmetic; format detected by raw-line-count "
                       "ratio, not by probing for an 'event' key; logical calls re-derived "
                       "from ledger, episode.json and trajectory.json independently; run_id "
                       "timestamp taken from the LAST '__' segment.",
        "integrity": {
            "episodes_found": len(episodes),
            "expected": 32,
            "per_cohort": {c: sum(1 for e in episodes if e["cohort"] == c) for c in COHORTS},
            "distinct_tasks_per_cohort_backend": {
                f"{c}|{b}": len(set(e["instance_id"] for e in episodes
                                    if e["cohort"] == c and e["backend_from_run_id"] == b))
                for c in COHORTS for b in ("large", "small")},
            "ledger_format_counts": fmt_counts,
            "starts_without_result": starts_wo_result,
            "unparsed_error_details": unparsed,
            "backend_from_run_id_matches_episode_json": all(
                e["backend_from_run_id"] == e["backend_from_episode_json"] for e in episodes),
            "logical_calls_distinct_in_ledger_matches_episode_json": all(
                e["logical_calls_distinct_in_ledger"] == e["logical_calls_episode_json"]
                for e in episodes),
            "harness_settings_observed": {
                "step_limit": sorted(set(e["step_limit_setting"] for e in episodes)),
                "wall_time_limit_seconds": sorted(set(e["wall_time_limit_seconds"] for e in episodes)),
                "max_response_tokens": sorted(set(e["max_response_tokens_setting"] for e in episodes)),
                "n_ctx_per_slot": sorted(set(e["n_ctx_per_slot"] for e in episodes)),
            },
        },
        "recomputed_summary_all_32": {
            "episodes": len(episodes),
            "terminating_constraint_counts": {
                "step_limit_H24": len(sl), "context_window": len(cw),
                "submitted": len(sub), "wall_clock": 0,
                "other": sum(1 for e in episodes
                             if e["terminating_constraint"].startswith("other:"))},
            "logical_calls_total_episode_json": sum(e["logical_calls_episode_json"] for e in episodes),
            "logical_calls_total_distinct_in_ledger": sum(
                e["logical_calls_distinct_in_ledger"] for e in episodes),
            "physical_attempts_total": sum(e["physical_attempts_ledger"] for e in episodes),
            "answered_calls_total": sum(e["answered_attempts"] for e in episodes),
            "failed_physical_attempts_total": sum(e["failed_attempts_ledger"] for e in episodes),
            "failed_attempt_error_type_counts": dict(allerr),
            "episodes_with_retried_calls": sum(
                1 for e in episodes if e["max_attempts_on_one_call"] > 1),
            "prompt_tokens_total_over_answered_calls": sum(e["prompt_sum"] for e in episodes),
            "completion_tokens_total_over_answered_calls": sum(e["completion_sum"] for e in episodes),
            "step_limit_episodes": {
                "count": len(sl),
                "max_answered_prompt_tokens_min": slmax[0],
                "max_answered_prompt_tokens_median": statistics.median(slmax),
                "max_answered_prompt_tokens_max": slmax[-1],
                "median_as_fraction_of_context": round(statistics.median(slmax) / CTX, 4),
                "median_headroom_tokens": CTX - statistics.median(slmax),
                "below_50pct_of_context": sum(1 for v in slmax if v < 0.50 * CTX),
                "below_75pct_of_context": sum(1 for v in slmax if v < 0.75 * CTX),
                "below_90pct_of_context": sum(1 for v in slmax if v < 0.90 * CTX),
                "mean_per_call_growth_min": slgrow[0],
                "mean_per_call_growth_median": statistics.median(slgrow),
                "mean_per_call_growth_max": slgrow[-1],
            },
            "context_window_episodes": {
                "count": len(cw),
                "logical_calls_used": sorted(e["logical_calls_episode_json"] for e in cw),
                "also_at_step_limit_on_the_overflowing_call": sum(
                    1 for e in cw if e["logical_calls_episode_json"] == H),
                "logical_calls_below_50pct_of_H24": sum(
                    1 for e in cw if e["logical_calls_episode_json"] < 0.5 * H),
                "overflow_request_tokens": sorted(
                    r["requested_tokens"] for e in cw for r in e["overflow_records"]),
                "available_context_reported": sorted(set(
                    r["available_tokens"] for e in cw for r in e["overflow_records"])),
                "per_episode": [dict(
                    run_dir=e["run_dir"],
                    logical_calls=e["logical_calls_episode_json"],
                    final_answered_prompt_tokens=e["final_answered_prompt_tokens"],
                    requested_tokens=[r["requested_tokens"] for r in e["overflow_records"]],
                    jump_from_final_answered_to_request=[
                        r["requested_tokens"] - e["final_answered_prompt_tokens"]
                        for r in e["overflow_records"]],
                    max_per_call_growth_among_answered_calls=e["max_per_call_growth"],
                    mechanism_note="the record set fixes the SIZE of the jump but not its "
                                   "cause; the ledger does not carry the content appended "
                                   "before the failed request, so the mechanism is AMBIGUOUS "
                                   "from these artifacts alone",
                ) for e in cw],
            },
            "submitted_episodes": {
                "count": len(sub),
                "logical_calls_used": sorted(e["logical_calls_episode_json"] for e in sub)},
            "wall_clock": {
                "episodes_reaching_wall_limit": sum(
                    1 for e in episodes if e["wall_seconds"] >= e["wall_time_limit_seconds"]),
                "wall_seconds_max": max(e["wall_seconds"] for e in episodes),
                "wall_seconds_max_as_fraction_of_limit": round(
                    max(e["wall_seconds"] for e in episodes) / WALL, 6)},
            "response_cap": {
                "calls_at_max_response_tokens_cap": sum(
                    e["calls_at_response_cap"] for e in episodes),
                "finish_reason_counts": dict(allfr),
                "largest_single_completion_tokens": max(
                    e["max_completion_tokens"] for e in episodes
                    if e["max_completion_tokens"] is not None)},
            "context_utilisation_all_episodes": {
                "max_answered_prompt_tokens_min": allmax[0],
                "max_answered_prompt_tokens_max": allmax[-1],
                "episodes_whose_max_answered_prompt_exceeded_half_the_context": sum(
                    1 for v in allmax if v > 0.5 * CTX)},
        },
        "recomputed_per_cohort": grouped(episodes, lambda e: e["cohort"]),
        "recomputed_per_backend": grouped(episodes, lambda e: e["backend_from_run_id"]),
        "recomputed_per_cohort_and_backend": grouped(
            episodes, lambda e: e["cohort"] + "|" + e["backend_from_run_id"]),
        "recomputed_cross_cohort_task_pairs": {
            "cells": len(pairs),
            "identical_prompt_token_series": sum(
                1 for p in pairs if p["identical_prompt_token_series"]),
            "not_identical": sum(1 for p in pairs if not p["identical_prompt_token_series"]),
            "of_which_differ_in_value_at_a_shared_index": sum(
                1 for p in pairs if p["differs_in_value_at_a_shared_index"]),
            "of_which_are_pure_length_truncation_shorter_is_strict_prefix": sum(
                1 for p in pairs if p["shorter_series_is_a_strict_prefix_of_the_longer"]),
            "common_prefix_lengths_of_non_identical_cells": sorted(
                p["common_prefix_length"] for p in pairs
                if not p["identical_prompt_token_series"]),
            "pairs": pairs,
        },
        "episode_json_agreement": {
            "prompt_sums_agree": len(episodes) - len(dis["prompt"]),
            "completion_sums_agree": len(episodes) - len(dis["completion"]),
            "physical_request_counts_agree": len(episodes) - len(dis["physical_requests"]),
            "failed_attempt_counts_agree": len(episodes) - len(dis["failed_attempts"]),
            "disagreements": dis,
        },
        "trajectory_cross_check": {
            "note": "a logical call appears in trajectory.json either as a role='assistant' "
                    "message or, when the harness interrupted the step, as a role='user' "
                    "message carrying extra.interrupt_type; counting only 'assistant' "
                    "undercounts. Reported so the gap is visible rather than silent.",
            "assistant_messages_total": sum(e["trajectory_assistant_messages"] for e in episodes),
            "interrupt_messages_total": sum(e["trajectory_interrupt_messages"] for e in episodes),
            "logical_calls_total_episode_json": sum(
                e["logical_calls_episode_json"] for e in episodes),
            "episodes_where_assistant_count_is_below_n_model_calls": [
                dict(run_dir=e["run_dir"],
                     assistant_messages=e["trajectory_assistant_messages"],
                     interrupt_messages=e["trajectory_interrupt_messages"],
                     n_model_calls=e["logical_calls_episode_json"],
                     failed_attempts=e["failed_attempts_ledger"])
                for e in episodes
                if e["trajectory_assistant_messages"] < e["logical_calls_episode_json"]],
        },
        "artifact_self_audit": {
            "artifact_episode_entries": len(art["episodes"]),
            "artifact_unique_run_ids": len(set(e["run_id"] for e in art["episodes"])),
            "run_id_timestamp_parse_errors": art_ts_bad,
            "cohort_label_errors": art_cohort_bad,
            "contains_local_username_literal": LOCAL_USER in blob,
            "contains_absolute_user_paths": "/Users/" in blob,
            "run_dirs_that_do_not_exist": [
                e["run_dir"] for e in art["episodes"]
                if not os.path.isdir(os.path.join(REPO, e["run_dir"]))],
            "episodes_carrying_an_ambiguity_note": sum(
                1 for e in art["episodes"] if e["ambiguities"]),
        },
        "per_episode": episodes,
    }

    path = os.path.join(REPO, OUT_REL)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "x") as fh:
        json.dump(out, fh, indent=1, sort_keys=False)
    print("wrote", OUT_REL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
