#!/usr/bin/env python
"""Independent re-derivation of the cross-cohort divergence numbers.

This is a VERIFIER. It does not import or reuse
experiments/v2_agent/analysis/cross_cohort_divergence.py. Every quantity is
recomputed from the raw committed records by a deliberately different route:

  * pairing keys come from each episode's own episode.json {instance_id,
    backend} fields, NOT from splitting the run directory name; the directory
    name is then parsed by a regex ANCHORED ON THE TRAILING
    <YYYYmmdd>T<HHMMSS>Z-<hex> segment and cross-checked against episode.json.
  * command text comes from extra.response.choices[0].message.content (the raw
    provider payload) fence-parsed by a line scanner, NOT from extra.actions
    and NOT by regex over the rendered message content. extra.actions is then
    used only as a cross-check.
  * call counts are cross-checked against the per-episode attempts.jsonl
    ledger (both ledger formats) and episode.json n_model_calls.

Descriptive only: counts and classifications. No causal or efficacy claim.
Read-only with respect to results/; the single output file is opened 'x'.
"""

from __future__ import annotations

import collections
import hashlib
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))

LEGACY_REL = "results/v2_agent/pilot_20260922"
YAML_REL = "results/v2_agent/pilot_20260922_yaml_v1"
OUT_REL = "results/v2_agent/analysis_20260922/cross_cohort_divergence_verification.json"
PEER_REL = "results/v2_agent/analysis_20260922/cross_cohort_divergence.json"
LEGACY_REPORT_REL = "results/v2_agent/pilot_20260922/report_block1_final.json"
YAML_REPORT_REL = "results/v2_agent/pilot_20260922_yaml_v1/report_yaml_v1_block1_final.json"

RUN_DIR_RE = re.compile(r"^(?P<rest>.+)__(?P<ts>\d{8}T\d{6}Z)-(?P<hex>[0-9a-f]+)$")
FENCE_INFO = "mswea_bash_command"
ELISION_MARKERS = [
    "The output of your last command was too long.",
    "<output_head>",
    "<elided_chars>",
    "characters elided",
    "<output_tail>",
]
CLOCK_RE = re.compile(r"\d{2}:\d{2}")
ENV_PROBES = {
    "carriage_return": "\r",
    "ansi_escape": "\x1b[",
    "tqdm_block_glyph": "█",
    "rate_suffix_it_s": "it/s]",
    "percent_bar": "%|",
    "downloading": "Downloading ",
    "eta": "eta 0:",
}


def jload(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


# --------------------------------------------------------------------------
# command extraction: line scanner over the raw provider payload
# --------------------------------------------------------------------------
def commands_from_payload_text(text):
    """Return every fenced mswea_bash_command block body, by line scanning."""
    out = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("```") and stripped[3:].strip() == FENCE_INFO:
            body = []
            i += 1
            closed = False
            while i < len(lines):
                if lines[i].strip().startswith("```"):
                    closed = True
                    break
                body.append(lines[i])
                i += 1
            if closed:
                out.append("\n".join(body))
        i += 1
    return out


def payload_content(extra):
    """choices[0].message.content out of the recorded provider response."""
    resp = extra.get("response")
    if isinstance(resp, dict):
        ch = resp.get("choices")
        if isinstance(ch, list) and ch:
            msg = ch[0].get("message") or {}
            c = msg.get("content")
            if isinstance(c, str):
                return c
    return None


# --------------------------------------------------------------------------
# episode loading
# --------------------------------------------------------------------------
def load_episode(cohort, run_dir_abs, run_dir_name, notes):
    ep = jload(os.path.join(run_dir_abs, "episode.json"))
    grade = jload(os.path.join(run_dir_abs, "grade.json"))
    traj = jload(os.path.join(run_dir_abs, "trajectory.json"))
    msgs = traj["messages"]

    m = RUN_DIR_RE.match(run_dir_name)
    if not m:
        notes.append("run dir name does not match anchored pattern: %s" % run_dir_name)
        dirname_iid = dirname_backend = dirname_binding = dirname_ts = None
    else:
        rest = m.group("rest")
        dirname_ts = m.group("ts")
        head, _, dirname_binding = rest.rpartition("__")
        dirname_iid, _, dirname_backend = head.rpartition("__")

    if ep.get("instance_id") != dirname_iid or ep.get("backend") != dirname_backend:
        notes.append(
            "dirname/episode.json key mismatch for %s: dirname=(%r,%r) episode=(%r,%r)"
            % (run_dir_name, dirname_iid, dirname_backend,
               ep.get("instance_id"), ep.get("backend")))
    if ep.get("run_id") != run_dir_name:
        notes.append("episode.run_id != directory name for %s" % run_dir_name)

    # logical calls, in message order
    calls = []          # (kind, command_or_None, message_index)
    observations = []   # (message_index, rendered, raw_output)
    n_action_msgs = 0
    payload_mismatch = 0
    payload_missing = 0
    multi_fence = 0

    for idx, msg in enumerate(msgs):
        role = msg.get("role")
        extra = msg.get("extra") or {}
        if role == "assistant":
            n_action_msgs += 1
            acts = extra.get("actions") or []
            act_cmd = acts[0].get("command") if len(acts) == 1 else None
            if len(acts) != 1:
                notes.append("assistant message with %d actions in %s idx %d"
                             % (len(acts), run_dir_name, idx))
            txt = payload_content(extra)
            if txt is None:
                payload_missing += 1
                cmd = act_cmd
            else:
                fenced = commands_from_payload_text(txt)
                if len(fenced) != 1:
                    multi_fence += 1
                    cmd = act_cmd
                else:
                    cmd = fenced[0]
                    if cmd != act_cmd:
                        payload_mismatch += 1
                        cmd = act_cmd
            calls.append(("action", cmd, idx))
        elif role == "user":
            if extra.get("interrupt_type"):
                calls.append(("format_error", None, idx))
            elif "returncode" in extra:
                observations.append((idx, msg.get("content"), extra.get("raw_output")))

    # responses: the message that answers each logical call.
    # action call at idx -> next message if it is a user observation.
    # format_error call IS itself the response message.
    responses = []
    for kind, _cmd, idx in calls:
        if kind == "format_error":
            responses.append(msgs[idx].get("content"))
        else:
            nxt = msgs[idx + 1] if idx + 1 < len(msgs) else None
            if nxt is not None and nxt.get("role") == "user":
                responses.append(nxt.get("content"))
            else:
                responses.append(None)

    exit_msgs = [m2 for m2 in msgs if m2.get("role") == "exit"]
    exit_from_traj = exit_msgs[-1].get("content") if exit_msgs else None

    sub_path = os.path.join(run_dir_abs, "submission.diff")
    with open(sub_path, "rb") as fh:
        sub_bytes = fh.read()

    # ledger cross-check, both formats
    ledger_calls = set()
    ledger_results = 0
    with open(os.path.join(run_dir_abs, "attempts.jsonl"), "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            ev = rec.get("event")
            if ev == "start":
                ledger_calls.add(rec["call"])
                continue
            # legacy record (no 'event') or yaml-v1 'result'
            ledger_calls.add(rec["call"])
            ledger_results += 1

    return {
        "cohort": cohort,
        "run_dir": run_dir_name,
        "instance_id": ep.get("instance_id"),
        "backend": ep.get("backend"),
        "binding_from_dirname": dirname_binding,
        "timestamp_from_dirname_last_segment": dirname_ts,
        "exit_status_episode_json": ep.get("exit_status"),
        "exit_status_trajectory": exit_from_traj,
        "grade_classification": grade.get("classification"),
        "submission_bytes": len(sub_bytes),
        "n_model_calls_episode_json": ep.get("n_model_calls"),
        "n_logical_calls_reconstructed": len(calls),
        "n_action_calls": n_action_msgs,
        "n_format_error_calls": sum(1 for c in calls if c[0] == "format_error"),
        "n_observations": len(observations),
        "ledger_distinct_calls": len(ledger_calls),
        "ledger_result_records": ledger_results,
        "payload_derived_command_mismatches_vs_actions": payload_mismatch,
        "payload_missing": payload_missing,
        "multi_fence_responses": multi_fence,
        "_calls": calls,
        "_observations": observations,
        "_responses": responses,
        "_msgs": msgs,
    }


def read_cohort(cohort, rel, notes):
    base = os.path.join(REPO, rel)
    eps = {}
    for name in sorted(os.listdir(base)):
        full = os.path.join(base, name)
        if not os.path.isdir(full):
            continue
        if not os.path.exists(os.path.join(full, "episode.json")):
            notes.append("directory without episode.json skipped: %s/%s" % (rel, name))
            continue
        e = load_episode(cohort, full, name, notes)
        key = (e["instance_id"], e["backend"])
        if key in eps:
            notes.append("DUPLICATE assignment key in %s: %s" % (rel, key))
        eps[key] = e
    return eps


# --------------------------------------------------------------------------
# comparison helpers
# --------------------------------------------------------------------------
def prefix_len(a, b):
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def clock_only_difference(a, b):
    if a is None or b is None:
        return False, None
    la, lb = a.split("\n"), b.split("\n")
    if len(la) != len(lb):
        return False, None
    diffs = [(i, x, y) for i, (x, y) in enumerate(zip(la, lb)) if x != y]
    if not diffs:
        return False, None
    for _i, x, y in diffs:
        if CLOCK_RE.sub("<TIME>", x) != CLOCK_RE.sub("<TIME>", y):
            return False, diffs
    return True, diffs


def classify_observation_pair(leg, yml):
    if leg is None and yml is None:
        return "no_preceding_observation"
    if leg is None or yml is None:
        return "no_preceding_observation"
    if leg == yml:
        return "observation_identical_but_command_differs"
    y_has = [m for m in ELISION_MARKERS if m in yml]
    l_has = [m for m in ELISION_MARKERS if m in leg]
    if len(y_has) == len(ELISION_MARKERS) and not l_has:
        return "observation_truncated_in_yaml_v1"
    clock, _ = clock_only_difference(leg, yml)
    if clock:
        return "observation_text_differs_clock_only"
    for probe in ENV_PROBES.values():
        if (probe in leg) != (probe in yml):
            return "observation_text_differs_env_vars"
    return "unclassified"


def preceding_observation(ep, call_pos, mode="proximate"):
    """Rendered + raw text of the observation most proximate to (i.e. standing
    immediately before) logical call position `call_pos` (0-based).

    Two conventions, both reported:
      mode='strict'    -- if this episode has no call at that position (it
                          terminated earlier), there is no preceding
                          observation; return (None, None).
      mode='proximate' -- if this episode has no call at that position, the
                          most proximate preceding observation is the
                          episode's LAST observation, i.e. the response to its
                          final logical call. This is the convention the peer
                          artifact's 'preceding_observation' label uses.
    """
    if call_pos >= len(ep["_calls"]):
        if mode == "strict":
            return None, None
        obs = ep["_observations"]
        if not obs:
            return None, None
        return obs[-1][1], obs[-1][2]
    _kind, _cmd, midx = ep["_calls"][call_pos]
    j = midx - 1
    while j >= 0:
        m = ep["_msgs"][j]
        extra = m.get("extra") or {}
        if m.get("role") == "user" and "returncode" in extra:
            return m.get("content"), extra.get("raw_output")
        if m.get("role") == "user" and extra.get("interrupt_type"):
            return None, None
        j -= 1
    return None, None


def main():
    notes = []
    legacy = read_cohort("legacy", LEGACY_REL, notes)
    yaml_v1 = read_cohort("yaml_v1", YAML_REL, notes)

    keys_l, keys_y = set(legacy), set(yaml_v1)
    pair_keys = sorted(keys_l & keys_y, key=lambda k: (k[1], k[0]))

    pairs = []
    for key in pair_keys:
        L, Y = legacy[key], yaml_v1[key]
        cl = [c[1] for c in L["_calls"] if c[0] == "action"]
        cy = [c[1] for c in Y["_calls"] if c[0] == "action"]
        kl = [(c[0], c[1]) for c in L["_calls"]]
        ky = [(c[0], c[1]) for c in Y["_calls"]]
        depth = min(len(kl), len(ky))

        first_div = None
        length_only = False
        for i in range(depth):
            if kl[i] != ky[i]:
                first_div = i + 1
                break
        if first_div is None and len(kl) != len(ky):
            first_div = depth + 1
            length_only = True

        ev = None
        cls = None
        cls_strict = None
        if first_div is not None:
            pos = first_div - 1
            lr, lraw = preceding_observation(L, pos, "proximate")
            yr, yraw = preceding_observation(Y, pos, "proximate")
            cls = classify_observation_pair(lr, yr)
            lrs, _ = preceding_observation(L, pos, "strict")
            yrs, _ = preceding_observation(Y, pos, "strict")
            cls_strict = classify_observation_pair(lrs, yrs)
            ev = {
                "convention": ("most proximate preceding observation on each side; for an "
                               "episode that terminated before this index, that is its last "
                               "observation"),
                "legacy_rendered_chars": None if lr is None else len(lr),
                "yaml_v1_rendered_chars": None if yr is None else len(yr),
                "legacy_raw_output_chars": None if lraw is None else len(lraw),
                "yaml_v1_raw_output_chars": None if yraw is None else len(yraw),
                "raw_output_identical": (lraw == yraw) if (lraw is not None and yraw is not None) else None,
                "rendered_observation_identical": (lr == yr) if (lr is not None and yr is not None) else None,
                "yaml_v1_elision_markers_present": [m for m in ELISION_MARKERS if yr and m in yr],
                "legacy_elision_markers_present": [m for m in ELISION_MARKERS if lr and m in lr],
                "legacy_call_kind": kl[pos][0] if pos < len(kl) else None,
                "yaml_v1_call_kind": ky[pos][0] if pos < len(ky) else None,
                "legacy_call_present": pos < len(kl),
                "yaml_v1_call_present": pos < len(ky),
            }
            if length_only:
                ev["note"] = ("length-mismatch-only divergence: the shorter episode has no "
                              "logical call at this index, so its side of the comparison is "
                              "its final observation")

        # response divergence
        rl, ry = L["_responses"], Y["_responses"]
        rdepth = min(len(rl), len(ry))
        first_resp = None
        for i in range(rdepth):
            if rl[i] != ry[i]:
                first_resp = i + 1
                break
        resp_clock_only = None
        resp_diff_lines = None
        if first_resp is not None:
            ok, diffs = clock_only_difference(rl[first_resp - 1], ry[first_resp - 1])
            resp_clock_only = ok
            if diffs is not None:
                resp_diff_lines = [
                    {"line_index": i, "legacy": x[:200], "yaml_v1": y[:200]}
                    for i, x, y in diffs[:3]
                ]

        pairs.append({
            "instance_id": key[0],
            "backend": key[1],
            "legacy_run_dir": L["run_dir"],
            "yaml_v1_run_dir": Y["run_dir"],
            "n_action_calls_legacy": len(cl),
            "n_action_calls_yaml_v1": len(cy),
            "n_logical_calls_legacy": len(kl),
            "n_logical_calls_yaml_v1": len(ky),
            "compared_call_depth": depth,
            "identical_command_sequences": cl == cy,
            "identical_command_prefix_length": prefix_len(cl, cy),
            "first_divergent_logical_call_index": first_div,
            "first_divergent_is_length_mismatch_only": length_only,
            "first_divergence_classification": cls,
            "first_divergence_classification_strict_convention": cls_strict,
            "first_divergence_evidence": ev,
            "first_differing_response_index": first_resp,
            "first_differing_response_is_clock_field_only": resp_clock_only,
            "first_differing_response_diff_lines": resp_diff_lines,
        })

    def agg(subset, sel):
        sub = [p for p in pairs if sel(p)]
        pl = sorted(p["identical_command_prefix_length"] for p in sub)
        return {
            "subset": subset,
            "n_pairs": len(sub),
            "n_pairs_identical_command_sequences": sum(1 for p in sub if p["identical_command_sequences"]),
            "n_pairs_divergent_command_sequences": sum(1 for p in sub if not p["identical_command_sequences"]),
            "n_pairs_with_any_first_divergent_call": sum(1 for p in sub if p["first_divergent_logical_call_index"] is not None),
            "identical_command_prefix_lengths_sorted": pl,
            "identical_command_prefix_length_sum": sum(pl),
            "identical_command_prefix_length_min": min(pl) if pl else None,
            "identical_command_prefix_length_max": max(pl) if pl else None,
            "first_divergent_call_indices": [
                {"instance_id": p["instance_id"], "backend": p["backend"],
                 "index": p["first_divergent_logical_call_index"],
                 "length_mismatch_only": p["first_divergent_is_length_mismatch_only"],
                 "classification": p["first_divergence_classification"]}
                for p in sub if p["first_divergent_logical_call_index"] is not None
            ],
            "first_divergence_classification_counts": dict(collections.Counter(
                p["first_divergence_classification"] for p in sub
                if p["first_divergent_logical_call_index"] is not None)),
            "first_divergence_classification_counts_strict_convention": dict(collections.Counter(
                p["first_divergence_classification_strict_convention"] for p in sub
                if p["first_divergent_logical_call_index"] is not None)),
            "n_pairs_with_any_differing_response": sum(1 for p in sub if p["first_differing_response_index"] is not None),
            "n_pairs_whose_first_differing_response_is_clock_field_only": sum(
                1 for p in sub if p["first_differing_response_is_clock_field_only"] is True),
        }

    # cohort-level scans
    per_cohort = {}
    for cname, eps in (("legacy", legacy), ("yaml_v1", yaml_v1)):
        probes = collections.Counter()
        n_obs = 0
        n_elided = 0
        elided_eps = []
        n_cmds = 0
        pip_cmds = 0
        pager_cmds = 0
        exits = collections.Counter()
        grades = collections.Counter()
        empty = 0
        ledger_mismatch = []
        for key in sorted(eps, key=lambda k: (k[1], k[0])):
            e = eps[key]
            ep_elided = 0
            for _i, rendered, raw in e["_observations"]:
                n_obs += 1
                if rendered and "<elided_chars>" in rendered:
                    n_elided += 1
                    ep_elided += 1
                if isinstance(raw, str):
                    for pname, pat in ENV_PROBES.items():
                        if pat in raw:
                            probes[pname] += 1
            if ep_elided:
                elided_eps.append({"instance_id": key[0], "backend": key[1],
                                   "n_elided_observations": ep_elided})
            for kind, cmd, _idx in e["_calls"]:
                if kind != "action":
                    continue
                n_cmds += 1
                if "pip" in (cmd or ""):
                    pip_cmds += 1
                if re.search(r"(?:^|[|;&\s])(?:less|man|more)(?:\s|$)", cmd or ""):
                    pager_cmds += 1
            exits[e["exit_status_episode_json"]] += 1
            grades[e["grade_classification"]] += 1
            if e["submission_bytes"] == 0:
                empty += 1
            if e["n_model_calls_episode_json"] != e["n_logical_calls_reconstructed"]:
                ledger_mismatch.append({
                    "instance_id": key[0], "backend": key[1],
                    "episode_json": e["n_model_calls_episode_json"],
                    "reconstructed": e["n_logical_calls_reconstructed"]})
            if e["ledger_distinct_calls"] != e["n_model_calls_episode_json"]:
                ledger_mismatch.append({
                    "instance_id": key[0], "backend": key[1],
                    "ledger_distinct_calls": e["ledger_distinct_calls"],
                    "episode_json": e["n_model_calls_episode_json"]})
        per_cohort[cname] = {
            "n_episodes": len(eps),
            "n_observations": n_obs,
            "n_observations_with_elided_chars": n_elided,
            "episodes_with_elided_observations": elided_eps,
            "n_commands_issued": n_cmds,
            "n_commands_containing_pip": pip_cmds,
            "n_commands_invoking_less_man_more": pager_cmds,
            "n_format_error_calls": sum(e["n_format_error_calls"] for e in eps.values()),
            "env_var_probe_counts_over_raw_output": {k: probes.get(k, 0) for k in ENV_PROBES},
            "exit_status_counts": dict(exits),
            "grade_classification_counts": dict(grades),
            "n_empty_submission_diff": empty,
            "call_count_disagreements": ledger_mismatch,
            "payload_derived_command_mismatches_vs_actions": sum(
                e["payload_derived_command_mismatches_vs_actions"] for e in eps.values()),
            "multi_fence_responses": sum(e["multi_fence_responses"] for e in eps.values()),
        }

    # committed reports cross-check
    rep = {}
    for cname, relp in (("legacy", LEGACY_REPORT_REL), ("yaml_v1", YAML_REPORT_REL)):
        d = jload(os.path.join(REPO, relp))
        tot = collections.Counter()
        blocks = {}
        for bname, b in (d.get("backends") or {}).items():
            blocks[bname] = b.get("exit_status")
            tot.update(b.get("exit_status") or {})
        rep[cname] = {
            "report_repo_relative": relp,
            "per_backend_exit_status": blocks,
            "summed_exit_status": dict(tot),
            "matches_my_recomputed_exit_counts":
                dict(tot) == per_cohort[cname]["exit_status_counts"],
        }

    # format-error localisation
    fe_locations = []
    for cname, eps in (("legacy", legacy), ("yaml_v1", yaml_v1)):
        for key, e in eps.items():
            if e["n_format_error_calls"]:
                fe_locations.append({
                    "cohort": cname, "instance_id": key[0], "backend": key[1],
                    "n_format_error_calls": e["n_format_error_calls"],
                    "logical_call_indices": [
                        i + 1 for i, c in enumerate(e["_calls"]) if c[0] == "format_error"],
                })

    out = {
        "analysis": "cross_cohort_divergence_verification",
        "role": "INDEPENDENT VERIFIER of results/v2_agent/analysis_20260922/cross_cohort_divergence.json",
        "kind": ("DESCRIPTIVE recomputation over already-completed committed episodes; "
                 "counts and classifications only; no causal claim, no efficacy claim, "
                 "no study-design recommendation"),
        "generated_by_script_repo_relative": "experiments/v2_agent/analysis/verify_divergence.py",
        "independence_note": (
            "Pairing keys read from episode.json {instance_id,backend}; run-directory names "
            "parsed by a regex anchored on the trailing <YYYYmmdd>T<HHMMSS>Z-<hex> segment and "
            "cross-checked. Command text re-derived by line-scanning fenced blocks in "
            "extra.response.choices[0].message.content (the raw provider payload); "
            "extra.actions used only as a cross-check. Call counts cross-checked against "
            "attempts.jsonl in both ledger formats and against episode.json n_model_calls. "
            "Template markup inside trajectory info.config is never scanned."),
        "inputs": {
            "legacy_cohort_dir_repo_relative": LEGACY_REL,
            "yaml_v1_cohort_dir_repo_relative": YAML_REL,
            "legacy_report_repo_relative": LEGACY_REPORT_REL,
            "yaml_v1_report_repo_relative": YAML_REPORT_REL,
            "peer_artifact_repo_relative": PEER_REL,
            "episodes_read": len(legacy) + len(yaml_v1),
            "legacy_episodes": len(legacy),
            "yaml_v1_episodes": len(yaml_v1),
            "pairs": len(pair_keys),
            "keys_only_in_legacy": sorted("%s|%s" % k for k in (keys_l - keys_y)),
            "keys_only_in_yaml_v1": sorted("%s|%s" % k for k in (keys_y - keys_l)),
        },
        "aggregate_all_pairs": agg("all", lambda p: True),
        "aggregate_by_backend": {
            "large": agg("backend=large", lambda p: p["backend"] == "large"),
            "small": agg("backend=small", lambda p: p["backend"] == "small"),
        },
        "per_cohort_scans": per_cohort,
        "committed_report_cross_check": rep,
        "format_error_locations": fe_locations,
        "pairs": pairs,
        "loader_notes": notes,
    }

    for p in out["pairs"]:
        p.pop("_calls", None)

    out_abs = os.path.join(REPO, OUT_REL)
    os.makedirs(os.path.dirname(out_abs), exist_ok=True)
    body = json.dumps(out, indent=2, sort_keys=False)
    out["output_sha256_excluding_this_field"] = hashlib.sha256(
        body.encode("utf-8")).hexdigest()
    with open(out_abs, "x", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2, sort_keys=False)
        fh.write("\n")
    print("wrote %s" % OUT_REL)

    # console summary for the verifier's own reading
    a = out["aggregate_all_pairs"]
    print(json.dumps({
        "episodes_read": out["inputs"]["episodes_read"],
        "pairs": out["inputs"]["pairs"],
        "identical": a["n_pairs_identical_command_sequences"],
        "divergent": a["n_pairs_divergent_command_sequences"],
        "large_identical": out["aggregate_by_backend"]["large"]["n_pairs_identical_command_sequences"],
        "small_identical": out["aggregate_by_backend"]["small"]["n_pairs_identical_command_sequences"],
        "prefix_sorted": a["identical_command_prefix_lengths_sorted"],
        "prefix_sum": a["identical_command_prefix_length_sum"],
        "large_prefix_sum": out["aggregate_by_backend"]["large"]["identical_command_prefix_length_sum"],
        "small_prefix_sum": out["aggregate_by_backend"]["small"]["identical_command_prefix_length_sum"],
        "first_div": a["first_divergent_call_indices"],
        "cls_counts": a["first_divergence_classification_counts"],
        "resp_any": a["n_pairs_with_any_differing_response"],
        "resp_clock": a["n_pairs_whose_first_differing_response_is_clock_field_only"],
        "legacy_cmds": per_cohort["legacy"]["n_commands_issued"],
        "yaml_cmds": per_cohort["yaml_v1"]["n_commands_issued"],
        "legacy_obs": per_cohort["legacy"]["n_observations"],
        "yaml_obs": per_cohort["yaml_v1"]["n_observations"],
        "legacy_elided": per_cohort["legacy"]["n_observations_with_elided_chars"],
        "yaml_elided": per_cohort["yaml_v1"]["n_observations_with_elided_chars"],
        "legacy_fe": per_cohort["legacy"]["n_format_error_calls"],
        "yaml_fe": per_cohort["yaml_v1"]["n_format_error_calls"],
        "legacy_exits": per_cohort["legacy"]["exit_status_counts"],
        "yaml_exits": per_cohort["yaml_v1"]["exit_status_counts"],
        "notes": notes,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
