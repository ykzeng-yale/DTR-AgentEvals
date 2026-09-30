"""Conditional, unreleased full-cohort opportunity audit coordinator.

The CPU coordinator assigns every AH task to each fixed schedule once. Only a
fresh AI worker imports CUDA; evaluator data never enters its specification.
Independent whole-batch supervision is required by ``run_cohort``. This module
does not acquire images or weights, choose tasks, release a job, train H/P, retry
a candidate, or infer an H/P effect from four deterministic schedules.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import shutil
import signal
import stat
import subprocess
import sys
import time
from typing import Any, Callable

from experiments.lead_req030 import req030ag_screen as sandbox
from experiments.lead_req030 import req030ah_controls as controls
from experiments.lead_req030 import req030ai_candidate_grade as grader
from experiments.lead_req030 import req030ai_episode_worker as worker
from experiments.lead_req030 import req030aj_official_grade as official
from experiments.lead_req030.req030ai_schedule_adapter import MODEL_PINS, validate_decision_state

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
SCHEMA = "dtr.req030aj.cohort.v1"
SCHEDULES = ("SS", "SL", "LS", "LL")
REQUIRED_SOURCES = tuple(dict.fromkeys((
    "experiments/lead_req030/req030aj_cohort.py",
    "experiments/lead_req030/req030ai_candidate_grade.py",
    "experiments/lead_req030/req030aj_official_grade.py",
    "experiments/lead_req030/req030ah_controls.py",
    "experiments/lead_req030/bounded_supervisor.py",
    controls.PARSER_REL, *worker.REQUIRED_SOURCES, *official.SOURCE_PINS,
)))
TOKEN_CONTRACT = {"context_limit": 16384, "max_new_tokens": 1536,
                  "logical_call_limit": 24, "decision_calls": [1, 9],
                  "do_sample": False, "physical_retries": 0}
# A slot is started only if this complete component envelope remains. The
# independent batch guardian is the hard final bound, including overruns/faults.
SLOT_RESERVATION_SECONDS = 3600 + 30 + 600 + 60 + 900 + 20 + 7 + 30
MAX_JSON = 16 * 1024 * 1024
INVOCATION_MARKER = "DTR_AJ_INVOCATION="


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hex(value: Any, length: int = 64) -> bool:
    return isinstance(value, str) and re.fullmatch(f"[0-9a-f]{{{length}}}", value) is not None


def read_json(path: Path, cap: int = MAX_JSON) -> dict:
    value = worker.parse_json(worker.read_private(path, cap))
    if not isinstance(value, dict):
        raise ValueError("artifact must be a unique-key JSON object")
    return value


def read_pin(pin: dict, cap: int | None = None) -> tuple[Path, bytes]:
    path = worker._pin(pin, cap=cap)
    data = worker.read_private(path, cap if cap is not None else path.stat().st_size)
    if sha(data) != pin["sha256"]:
        raise ValueError("pinned input changed during admission")
    return path, data


def file_pin(path: Path) -> dict:
    return {"path": str(path.resolve()), "sha256": worker.digest_file(path)}


def frozen_order(release_id: str) -> list[dict]:
    """Each schedule occupies each position twice across the eight tasks."""
    if not isinstance(release_id, str) or re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", release_id) is None:
        raise ValueError("unsafe release identity")
    result = []
    for task_index, tid in enumerate(controls.TASK_IDS):
        rotation = task_index % len(SCHEDULES)
        for position in range(4):
            schedule = SCHEDULES[(rotation + position) % 4]
            result.append({"task_id": tid, "schedule": schedule,
                "task_index": task_index, "within_task_position": position,
                "period": len(result) + 1,
                "invocation_id": f"{release_id}:{tid}:{schedule}:a"})
    return result


def _finite_positive(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def validate_admission(release_path: Path, expected_sha: str) -> tuple[dict, dict]:
    """Replay all controls and admit the entire exact cohort, or no worker."""
    path, raw = read_pin({"path": str(release_path.absolute()), "sha256": expected_sha}, MAX_JSON)
    release = worker.parse_json(raw)
    keys = {"schema", "request", "release_id", "phase", "model_execution_authorized",
            "control_release", "control_acceptance", "models", "runtime", "resource_cap",
            "limits", "source_pins", "model_root", "apptainer", "tasks", "order", "token_contract"}
    if (not isinstance(release, dict) or set(release) != keys or release["schema"] != SCHEMA
            or release["request"] != "DTR-REQ-030AJ" or release["phase"] != "DEVELOPMENT"
            or release["model_execution_authorized"] is not True
            or release["token_contract"] != TOKEN_CONTRACT):
        raise ValueError("complete prospective model release required")
    if release["order"] != frozen_order(release["release_id"]):
        raise ValueError("frozen balanced execution order differs")
    limits = release["limits"]
    if (not isinstance(limits, dict)
            or set(limits) != {"batch_seconds", "storage_bytes", "min_free_bytes", "grade_seconds", "slot_reservation_seconds"}
            or limits["grade_seconds"] != 900 or limits["slot_reservation_seconds"] != SLOT_RESERVATION_SECONDS
            or not _finite_positive(limits["batch_seconds"])
            or any(type(limits[k]) is not int or limits[k] <= 0 for k in ("storage_bytes", "min_free_bytes"))):
        raise ValueError("invalid prospective joint time/storage envelope")
    if not isinstance(release["source_pins"], dict) or set(release["source_pins"]) != set(REQUIRED_SOURCES):
        raise ValueError("complete exact executable source pins required")
    for rel, digest in release["source_pins"].items():
        if not _hex(digest) or worker.digest_file(ROOT / rel) != digest:
            raise ValueError(f"coordinator source identity differs: {rel}")
    if (worker.digest_file(Path(controls.__file__)) != grader.AH_CONTROLS_SHA256
            or controls.PARSER_SHA != grader.PARSER_SHA256):
        raise ValueError("strict candidate grader/control source contract differs")
    if (not isinstance(release["models"], dict) or set(release["models"]) != {"models"}
            or not isinstance(release["models"]["models"], list) or len(release["models"]["models"]) != 2
            or {(m.get("repo"), m.get("revision")) for m in release["models"]["models"]}
            != {(m["repo"], m["revision"]) for m in MODEL_PINS.values()}):
        raise ValueError("frozen real model pair differs")
    for model in release["models"]["models"]:
        if set(model) != {"repo", "revision", "files"} or not isinstance(model["files"], list) or not model["files"]:
            raise ValueError("exact nonempty cached model asset pins required")
        paths = set()
        for asset in model["files"]:
            candidate = Path(asset.get("path", ""))
            if (set(asset) != {"path", "bytes", "sha256"} or not asset["path"] or candidate.is_absolute()
                    or ".." in candidate.parts or asset["path"] in paths
                    or type(asset["bytes"]) is not int or asset["bytes"] <= 0 or not _hex(asset["sha256"])):
                raise ValueError("unsafe or duplicate cached model asset pin")
            paths.add(asset["path"])
    resource = release["resource_cap"]
    if (not isinstance(resource, dict) or set(resource) != {"gpu_model", "gpu_count", "cpu", "memory_bytes", "slurm_seconds"}
            or resource["gpu_count"] != 1 or not isinstance(resource["gpu_model"], str)
            or any(type(resource[k]) is not int or resource[k] <= 0 for k in ("cpu", "memory_bytes", "slurm_seconds"))
            or resource["slurm_seconds"] < limits["batch_seconds"] + 45):
        raise ValueError("allocation does not bound complete batch supervision")
    runtime = release["runtime"]
    if (not isinstance(runtime, dict) or set(runtime) - {"gpu_model_aliases", "versions", "cuda", "python"}
            or runtime.get("cuda") != "12.8" or not isinstance(runtime.get("versions"), dict)
            or set(runtime["versions"]) != worker.RUNTIME_PACKAGES
            or not isinstance(runtime.get("python"), str) or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", runtime["python"]) is None
            or any(not isinstance(version, str) or not version for version in runtime["versions"].values())
            or runtime["versions"].get("torch") != "2.9.1"
            or runtime["versions"].get("transformers") != "4.51.3"):
        raise ValueError("frozen HF/BF16 runtime required")
    apptainer, _ = read_pin(release["apptainer"])
    model_root = Path(release["model_root"])
    if not model_root.is_absolute() or model_root.is_symlink() or not model_root.is_dir():
        raise ValueError("verified cached model root required")
    _, control_raw = read_pin(release["control_release"], MAX_JSON)
    control_release = worker.parse_json(control_raw)
    if (not isinstance(control_release.get("request"), str)
            or re.fullmatch(r"DTR-REQ-[A-Z0-9]+", control_release["request"]) is None
            or not isinstance(control_release.get("release_id"), str)
            or control_release.get("model_execution_authorized") is not False
            or tuple(t["instance_id"] for t in control_release.get("tasks", [])) != controls.TASK_IDS):
        raise ValueError("explicit frozen whole cohort CPU control release required")
    if (not isinstance(release["tasks"], list) or len(release["tasks"]) != 8
            or tuple(t.get("instance_id") for t in release["tasks"]) != controls.TASK_IDS):
        raise ValueError("all eight frozen AH tasks required")
    _, acceptance_raw = read_pin(release["control_acceptance"], MAX_JSON)
    acceptance = worker.parse_json(acceptance_raw)
    if (set(acceptance) != {"schema", "control_release_sha256", "all_controls_accepted", "source_review_accepted", "tasks"}
            or acceptance["schema"] != "dtr.req030aj.control_acceptance.v1"
            or acceptance["control_release_sha256"] != sha(control_raw)
            or acceptance["all_controls_accepted"] is not True or acceptance["source_review_accepted"] is not True
            or tuple(t.get("task_id") for t in acceptance["tasks"]) != controls.TASK_IDS):
        raise ValueError("all-control and independent source acceptance missing")
    parsers = controls.pinned_parsers()
    prepared = {}
    for task, original, receipt in zip(release["tasks"], control_release["tasks"], acceptance["tasks"], strict=True):
        task_keys = {"instance_id", "repo", "base_commit", "public_projection", "evaluator_bundle"}
        if set(task) != task_keys or any(task[k] != original[k] for k in ("instance_id", "repo", "base_commit")):
            raise ValueError("task/input identity differs from frozen controls")
        if grader.TASK_REPOS[task["instance_id"]] != task["repo"] or not _hex(task["base_commit"], 40):
            raise ValueError("frozen task source/family mismatch")
        public_path, public_raw = read_pin(task["public_projection"], 4 * 1024 * 1024)
        public = worker.parse_json(public_raw)
        if (set(public) != {"instance_id", "repo", "base_commit", "problem_statement"}
                or any(public[k] != task[k] for k in ("instance_id", "repo", "base_commit"))
                or sha(public_raw) != original["public_projection_sha256"]
                or len(public_raw) != original["public_projection_bytes"]):
            raise ValueError("public-only task projection identity differs")
        evaluator_path, evaluator_raw = read_pin(task["evaluator_bundle"], grader.MAX_EVALUATOR_BYTES)
        evaluation = grader.parse_unique(evaluator_raw)
        if (sha(evaluator_raw) != original["evaluator_bundle_sha256"]
                or len(evaluator_raw) != original["evaluator_bundle_bytes"]
                or any(evaluation[k] != task[k] for k in ("instance_id", "base_commit"))
                or len(evaluation["fail_to_pass"]) != original["fail_to_pass_count"]
                or len(evaluation["pass_to_pass"]) != original["pass_to_pass_count"]
                or sha(evaluation["stock_eval_script"].encode()) != original["stock_eval_script_sha256"]
                or sha(evaluation["reference_patch"].encode()) != original["reference_patch_sha256"]):
            raise ValueError("exact evaluator identity differs from control release")
        if set(receipt) != {"task_id", "image", "source_tar", "source_acceptance", "controls"}:
            raise ValueError("source/control acceptance schema differs")
        image = worker._pin(receipt["image"], cap=8 * (1 << 30))
        source = worker._pin(receipt["source_tar"], cap=sandbox.MAX_SOURCE_TAR)
        _, source_raw = read_pin(receipt["source_acceptance"], MAX_JSON)
        source_review = worker.parse_json(source_raw)
        source_keys = {"schema", "task_id", "image_sha256", "source_tar_sha256", "head", "tree", "base_tree", "accepted", "model_tree_contract"}
        if (set(source_review) != source_keys or source_review["schema"] != "dtr.req030aj.source_acceptance.v1"
                or source_review["task_id"] != task["instance_id"]
                or source_review["image_sha256"] != receipt["image"]["sha256"]
                or source_review["source_tar_sha256"] != receipt["source_tar"]["sha256"]
                or source_review["accepted"] is not True
                or source_review["model_tree_contract"] != "equal_tree"
                or any(not _hex(source_review[k], 40) for k in ("head", "tree", "base_tree"))
                or source_review["tree"] != source_review["base_tree"]):
            raise ValueError("model source contract requires independently accepted equal trees")
        if set(receipt["controls"]) != {"baseline", "reference"}:
            raise ValueError("every baseline/reference control required")
        replay = {}
        for mode in ("baseline", "reference"):
            arm = receipt["controls"][mode]
            if set(arm) != {"raw", "supervisor"}:
                raise ValueError("complete control raw/supervisor binding required")
            _, arm_raw = read_pin(arm["raw"], sandbox.MAX_EPISODE_OUTPUT)
            _, sup_raw = read_pin(arm["supervisor"], MAX_JSON)
            replay[mode] = controls.assess(arm_raw, worker.parse_json(sup_raw), evaluation, mode, parsers[task["repo"]])
            if replay[mode]["accepted"] is not True:
                raise ValueError(f"whole cohort rejected: {task['instance_id']} {mode}")
        prepared[task["instance_id"]] = {"task": task, "public_path": public_path,
            "evaluator_path": evaluator_path, "evaluation": evaluation,
            "evaluator_raw": evaluator_raw, "image": image, "source": source,
            "head": source_review["head"], "receipt": receipt, "control_replay": replay}
    return release, {"release_sha256": sha(raw), "release_path": str(path),
                     "tasks": prepared, "apptainer": apptainer, "model_root": model_root}


def public_spec(release: dict, admission: dict, task_id: str, schedule: str) -> dict:
    item = admission["tasks"][task_id]
    task = item["task"]
    public_task = {k: task[k] for k in ("instance_id", "repo", "base_commit")}
    public_task["public_projection_sha256"] = task["public_projection"]["sha256"]
    return {"schema": "dtr.req030ai.episode.v1", "release_sha256": admission["release_sha256"],
        "model_release": {"release_id": release["release_id"], "models": release["models"],
            "runtime": release["runtime"], "resource_cap": {"gpu_model": release["resource_cap"]["gpu_model"]},
            "tasks": [public_task]},
        "model_id": MODEL_PINS[schedule[0]]["repo"], "schedule": schedule,
        "public_projection": task["public_projection"], "image": item["receipt"]["image"],
        "source_tar": item["receipt"]["source_tar"], "model_root": str(admission["model_root"]),
        "apptainer": release["apptainer"], "expected_image_head": item["head"],
        "source_pins": {rel: release["source_pins"][rel] for rel in worker.REQUIRED_SOURCES}}


def supervisor_clean(receipt: Any) -> bool:
    return (isinstance(receipt, dict)
        and set(receipt) == {"reason", "pid", "returncode", "retained_bytes", "elapsed", "error"}
        and receipt["reason"] in {"exited", "deadline", "output_limit", "owner_eof"}
        and receipt["error"] is None and type(receipt["pid"]) is int and receipt["pid"] > 0
        and type(receipt["returncode"]) is int and type(receipt["retained_bytes"]) is int
        and 0 <= receipt["retained_bytes"] <= sandbox.MAX_EPISODE_OUTPUT
        and type(receipt["elapsed"]) in (int, float) and math.isfinite(receipt["elapsed"]) and receipt["elapsed"] >= 0)


def execute_grade(*, item: dict, slot: dict, episode_directory: Path, directory: Path,
                  release_sha256: str, apptainer: str, seconds: int = 900) -> dict:
    """One fresh isolated evaluation, with a pre-execution invocation binding."""
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    patch_path = episode_directory / "episode" / "patch.diff"
    patch = worker.read_private(patch_path, grader.MAX_PATCH_BYTES)
    outcome = read_json(episode_directory / "worker_result.json")
    if (outcome.get("agent_exit_status") != "Submitted" or outcome.get("submission_eligible") is not True
            or not patch or sha(patch) != outcome.get("patch_sha256") or len(patch) != outcome.get("patch_bytes")):
        raise ValueError("only exact explicitly submitted candidate may be graded")
    task = item["task"]
    prospective = {"task_id": task["instance_id"], "repo": task["repo"], "base_commit": task["base_commit"],
        "policy_id": slot["schedule"], "invocation_id": slot["invocation_id"],
        "release_sha256": release_sha256, "evaluator_bundle_sha256": sha(item["evaluator_raw"]),
        "patch_sha256": sha(patch), "parser_sha256": grader.PARSER_SHA256}
    worker.write_new(directory / "assignment.json", prospective)
    marker = INVOCATION_MARKER + sha(canonical(prospective))
    image = directory / "workspace.img"
    seed = directory / "seed_temp"
    result = {"cleanup_verified": False, "binding_verified": False, "grade": unknown_grade("evaluation_not_finished"),
              "official_upstream_score": official_score_missing()}
    try:
        workspace = sandbox.make_workspace(item["source"], seed, image, uid=os.getuid(), gid=os.getgid())
        evaluation_directory = directory / "evaluator"
        evaluation_directory.mkdir(mode=0o700)
        for name, data in (("stock_eval.sh", item["evaluation"]["stock_eval_script"].encode()), ("agent.diff", patch)):
            target = evaluation_directory / name
            with target.open("xb") as stream:
                stream.write(data)
            target.chmod(0o400)
        wrapper = evaluation_directory / "run.sh"
        sandbox.evaluation_wrapper(wrapper, mode="agent", expected_image_head=item["head"])
        # The trusted wrapper prints its invocation before touching the candidate.
        text = wrapper.read_text()
        wrapper.chmod(0o600)
        wrapper.write_text(text.replace("set -uo pipefail\n", f"set -uo pipefail\nprintf '%s\\n' '{marker}'\n", 1))
        wrapper.chmod(0o500)
        raw, supervisor = sandbox.run_supervised(apptainer, item["image"], image, ["/bin/bash", "/eval/run.sh"],
            output_path=directory / "candidate.out", receipt_path=directory / "candidate.supervisor.json",
            seconds=seconds, extra_binds=["--bind", f"{evaluation_directory.resolve()}:/eval:ro"])
        result["cleanup_verified"] = supervisor_clean(supervisor)
        if raw.decode("utf-8", "replace").splitlines().count(marker) != 1:
            result["grade"] = unknown_grade("evaluator_invocation_marker_missing_or_duplicated")
            return result
        expected = {**prospective, "raw_sha256": sha(raw), "supervisor_sha256": sha(grader.canonical(supervisor))}
        observed = {**read_json(directory / "assignment.json"),
                    "raw_sha256": sha(worker.read_private(directory / "candidate.out", sandbox.MAX_EPISODE_OUTPUT)),
                    "supervisor_sha256": sha(grader.canonical(read_json(directory / "candidate.supervisor.json")))}
        worker.write_new(directory / "binding.json", observed)
        result["binding_verified"] = expected == observed
        scoring_task = {k: task[k] for k in ("instance_id", "repo", "base_commit")} | {"evaluator_bundle_sha256": prospective["evaluator_bundle_sha256"]}
        result["grade"] = grader.replay_candidate(task=scoring_task,
            evaluator_bundle=item["evaluator_raw"], raw=raw, supervisor=supervisor, patch=patch,
            expected_patch_sha256=outcome["patch_sha256"], expected_binding=expected, observed_binding=observed)
        result["official_upstream_score"] = official.replay_official(task=scoring_task,
            evaluator_bundle=item["evaluator_raw"], raw=raw, patch=patch,
            expected_binding=expected, observed_binding=observed, strict_grade=result["grade"])
        worker.write_new(directory / "strict_grade.json", result["grade"])
        worker.write_new(directory / "official_report.json", result["official_upstream_score"])
        result["workspace"] = workspace
        return result
    finally:
        if not result["cleanup_verified"]:
            receipt_path = directory / "candidate.supervisor.json"
            if receipt_path.exists():
                try:
                    result["cleanup_verified"] = supervisor_clean(read_json(receipt_path))
                except (ValueError, OSError):
                    pass
        # Delete only this invocation's owned disposable work after verified
        # process cleanup. Retain every raw/model/evaluation artifact otherwise.
        if result["cleanup_verified"]:
            if image.exists():
                image.unlink()
            if seed.exists():
                shutil.rmtree(seed)


def unknown_grade(reason: str) -> dict:
    return {"graded": False, "resolved": False, "algorithmic_correctness": "unknown",
            "operational_resolution": 0, "assigned_slot_retained": True, "reason": reason}


def official_score_missing() -> dict:
    # A strict required-status endpoint is not an unmodified upstream report.
    # Preserve this unmet v2 requirement explicitly rather than relabeling it.
    return {"available": False, "reason": "unmodified_official_upstream_report_not_produced",
            "upstream_commit": "f7bbbb2ccdf479001d6467c9e34af59e44a840f9",
            "parser_sha256": grader.PARSER_SHA256, "strict_score_is_official_score": False,
            "protocol_evaluation_gate_complete": False}


def native_measurements(directory: Path, schedule: str, outcome: dict | None) -> dict:
    """Audit durable observations; requests are distinct from returned tokens."""
    result = {"complete_native_accounting": False, "native_requests": None, "native_responses": None,
        "physical_attempts_reported": None, "input_tokens": None, "output_tokens": None,
        "generation_seconds": None, "peak_allocated_bytes": None, "peak_reserved_bytes": None,
        "second_decision_eligible": None, "per_model_requests": {"S": 0, "L": 0}}
    path = directory / "episode" / "agent" / "events.jsonl"
    if not path.exists():
        return result
    raw = worker.read_private(path, worker.MAX_NATIVE)
    if raw and not raw.endswith(b"\n"):
        raise ValueError("partial native ledger")
    events = [worker.parse_json(line) for line in raw.splitlines()]
    if any(e.get("sequence") != i for i, e in enumerate(events, 1)):
        raise ValueError("native ledger sequence differs")
    requests, responses, decisions = [], [], []
    pending = None
    reserved = None
    denied = False
    deadline = None
    decision_calls = set()
    binding_keys = {"messages_sha256", "rendered_sha256", "input_ids", "input_tokens", "max_new_tokens",
                    "context_limit", "reserved_total_tokens", "remaining_input_token_capacity", "admitted"}
    state_keys = {"remaining_episode_wall_seconds", "episode_deadline_monotonic", "measured_at_monotonic", "workspace_fingerprint"}
    for event in events:
        kind = event.get("event")
        if kind in {"routing_decision", "routing_reservation_denied"}:
            call = event.get("logical_call")
            if (pending is not None or call not in (1, 9) or call in decision_calls or call != len(requests) + 1
                    or event.get("schedule") != schedule or event.get("randomized_logger") is not False
                    or event.get("physical_calls_before") != len(requests)
                    or event.get("per_model_physical_calls_before") != result["per_model_requests"]
                    or event.get("decision_index") != (1 if call == 1 else 2)
                    or event.get("remaining_logical_calls_including_current") != 25 - call):
                raise ValueError("invalid actual decision sequence/accounting")
            state = {key: event.get(key) for key in state_keys}
            validate_decision_state(state)
            if state["remaining_episode_wall_seconds"] <= 0:
                raise ValueError("expired decision cannot be assigned")
            if deadline is not None and deadline != state["episode_deadline_monotonic"]:
                raise ValueError("shared episode deadline changed between decisions")
            deadline = state["episode_deadline_monotonic"]
            bindings = event.get("both_action_reservations", {})
            if set(bindings) != {"S", "L"} or bindings["S"] != bindings["L"]:
                raise ValueError("common both-action token binding differs")
            for binding in bindings.values():
                if (set(binding) != binding_keys
                        or any(not _hex(binding[k]) for k in ("messages_sha256", "rendered_sha256"))
                        or not isinstance(binding["input_ids"], list)
                        or any(type(x) is not int or x < 0 for x in binding["input_ids"])
                        or type(binding["input_tokens"]) is not int or binding["input_tokens"] != len(binding["input_ids"])
                        or binding["max_new_tokens"] != 1536 or binding["context_limit"] != 16384
                        or binding["reserved_total_tokens"] != binding["input_tokens"] + 1536
                        or binding["remaining_input_token_capacity"] != 14848 - binding["input_tokens"]
                        or binding["admitted"] is not (binding["reserved_total_tokens"] <= 16384)):
                    raise ValueError("invalid common native reservation")
            action = schedule[0 if call == 1 else 1]
            if kind == "routing_decision":
                if (event.get("probability") != 1.0 or event.get("model_action") != action
                        or event.get("probability_vector") != {a: float(a == action) for a in ("S", "L")}
                        or event.get("model_id") != MODEL_PINS[action]["repo"]
                        or event.get("revision") != MODEL_PINS[action]["revision"]
                        or any(binding["admitted"] is not True for binding in bindings.values())):
                    raise ValueError("invalid fixed assignment or joint eligibility")
                decisions.append(event); reserved = bindings[action]
            else:
                if any(key in event for key in ("probability", "probability_vector", "model_action", "model_id", "revision")) or all(binding["admitted"] for binding in bindings.values()):
                    raise ValueError("denied reservation may not assign an action")
                denied = True
            decision_calls.add(call)
        elif kind in {"request", "response", "generation_error"}:
            call = event.get("logical_call")
            if type(call) is not int or not 1 <= call <= 24:
                raise ValueError("invalid logical call")
            action = schedule[0 if call <= 8 else 1]
            if (event.get("schedule") != schedule or event.get("model_action") != action
                    or kind != "generation_error" and (event.get("model_id") != MODEL_PINS[action]["repo"]
                    or event.get("revision") != MODEL_PINS[action]["revision"])):
                raise ValueError("native model/schedule identity differs")
            if kind == "request":
                if (pending is not None or denied or call != len(requests) + 1
                        or event.get("physical_calls") != len(requests) + 1
                        or event.get("per_model_physical_calls") != result["per_model_requests"][action] + 1
                        or call in (1, 9) and call not in decision_calls):
                    raise ValueError("native request sequence differs")
                if (not isinstance(event.get("input_ids"), list) or any(type(x) is not int or x < 0 for x in event["input_ids"])
                        or type(event.get("input_tokens")) is not int or not 0 <= event["input_tokens"] <= 14848
                        or event["input_tokens"] != len(event["input_ids"])
                        or not _hex(event.get("messages_sha256")) or not isinstance(event.get("rendered"), str)
                        or sha(event["rendered"].encode()) != event.get("rendered_sha256")):
                    raise ValueError("invalid native input binding")
                if reserved is not None and any(event.get(key) != reserved[key] for key in ("messages_sha256", "rendered_sha256", "input_ids", "input_tokens")):
                    raise ValueError("native request differs from accepted reservation")
                reserved = None; pending = event; requests.append(event)
                result["per_model_requests"][action] += 1
            else:
                if pending is None or any(event.get(k) != pending[k] for k in ("logical_call", "physical_calls", "per_model_physical_calls", "model_action")):
                    raise ValueError("unmatched/duplicate native terminal receipt")
                if type(event.get("elapsed_seconds")) not in (int, float) or not math.isfinite(event["elapsed_seconds"]) or event["elapsed_seconds"] < 0:
                    raise ValueError("invalid native elapsed measurement")
                if kind == "response":
                    if (any(event.get(k) != pending[k] for k in ("model_id", "revision", "messages_sha256", "rendered_sha256", "input_tokens"))
                            or not isinstance(event.get("output_ids"), list)
                            or any(type(x) is not int or x < 0 for x in event["output_ids"])
                            or type(event.get("output_tokens")) is not int or not 0 <= event["output_tokens"] <= 1536
                            or event["output_tokens"] != len(event["output_ids"])):
                        raise ValueError("response input/output binding differs")
                    responses.append(event)
                pending = None
    result.update(native_requests=len(requests), native_responses=len(responses),
        input_tokens=sum(e["input_tokens"] for e in requests), output_tokens=sum(e["output_tokens"] for e in responses),
        generation_seconds=sum(e["elapsed_seconds"] for e in responses),
        event_log_sha256=sha(raw), event_log_bytes=len(raw),
        second_decision_eligible=bool(any(e["logical_call"] == 9 for e in decisions)) if outcome is not None else
            True if any(e["logical_call"] == 9 for e in decisions) else None)
    if outcome is not None:
        if (pending is not None or outcome.get("physical_calls") != len(requests) or len(requests) != len(responses)
                or outcome.get("event_log_sha256") != sha(raw)):
            raise ValueError("terminal accounting disagrees with durable native ledger")
        result["complete_native_accounting"] = True
        result["physical_attempts_reported"] = outcome["physical_calls"]
        for metric in ("peak_allocated_bytes", "peak_reserved_bytes"):
            if type(outcome.get(metric)) is not int or outcome[metric] < 0:
                raise ValueError("invalid measured memory")
            result[metric] = outcome[metric]
    return result


def summarize(slots: list[dict]) -> dict:
    if len(slots) != 32 or {(s["task_id"], s["schedule"]) for s in slots} != {(t, p) for t in controls.TASK_IDS for p in SCHEDULES}:
        raise ValueError("all 32 unique assigned slots must remain")
    for cell in slots:
        validate_grade(cell["grade"])
    schedule_stats = {}
    for schedule in SCHEDULES:
        cells = [s for s in slots if s["schedule"] == schedule]
        resolved = sum(s["grade"].get("operational_resolution") == 1 for s in cells)
        unknown = sum(s["grade"].get("algorithmic_correctness") == "unknown" for s in cells)
        schedule_stats[schedule] = {"assigned": 8, "resolved": resolved,
            "known_algorithmic_unresolved": sum(s["grade"].get("algorithmic_correctness") == "unresolved" for s in cells),
            "algorithmic_unknown": unknown, "operational_resolution_fraction": resolved / 8,
            "missing_correctness_range": [resolved / 8, (resolved + unknown) / 8]}
        if resolved + unknown + schedule_stats[schedule]["known_algorithmic_unresolved"] != 8:
            raise ValueError("algorithmic r/f/u must cover the complete schedule denominator")
    opportunity = {}
    for name, cells in (("all", slots), ("S_start", [s for s in slots if s["schedule"][0] == "S"]),
                        ("L_start", [s for s in slots if s["schedule"][0] == "L"])):
        values = [s.get("costs", {}).get("second_decision_eligible") for s in cells]
        opportunity[name] = {"assigned": len(cells), "verified_eligible": sum(x is True for x in values),
            "verified_not_eligible": sum(x is False for x in values), "unknown": sum(x is None for x in values),
            "verified_occupancy_fraction": sum(x is True for x in values) / len(cells)}
    resolved = sum(s["grade"].get("operational_resolution") == 1 for s in slots)
    unknown = sum(s["grade"].get("algorithmic_correctness") == "unknown" for s in slots)
    totals = {}
    for metric in ("native_requests", "native_responses", "physical_attempts_reported", "input_tokens", "output_tokens", "generation_seconds"):
        known = [s.get("costs", {}).get(metric) for s in slots]
        totals[metric] = {"observed_sum": sum(v for v in known if type(v) in (int, float)),
                          "unknown_slots": sum(v is None for v in known)}
    return {"assigned_slots": 32, "task_count": 8, "family_count": 8,
        "by_schedule": schedule_stats, "second_decision_opportunity": opportunity,
        "infrastructure_unknown_slots": sum(s.get("infrastructure_unknown") is True for s in slots),
        "unstarted_slots": sum(s["status"] == "NOT_ATTEMPTED" for s in slots),
        "operational_resolution_fraction": resolved / 32, "missing_correctness_range": [resolved / 32, (resolved + unknown) / 32],
        "official_upstream_score_missing_slots": sum(s.get("official_upstream_score", {}).get("available") is not True for s in slots),
        "costs": totals, "inference": "descriptive purposive eight-task DEVELOPMENT audit; no confidence interval, population, randomized OPE or H/P effect claim"}


def validate_grade(grade: Any) -> None:
    if (not isinstance(grade, dict) or type(grade.get("graded")) is not bool
            or type(grade.get("resolved")) is not bool
            or type(grade.get("operational_resolution")) is not int
            or grade["operational_resolution"] not in (0, 1)
            or grade.get("algorithmic_correctness") not in {"resolved", "unresolved", "unknown"}
            or grade.get("assigned_slot_retained") is not True):
        raise ValueError("malformed assigned strict endpoint/correctness grade")
    if grade["operational_resolution"] == 1:
        if grade["graded"] is not True or grade["resolved"] is not True or grade["algorithmic_correctness"] != "resolved":
            raise ValueError("resolution cannot be unknown or ungraded")
    elif grade["resolved"] is not False or grade["algorithmic_correctness"] == "resolved":
        raise ValueError("operational/correctness resolution disagree")
    if grade["algorithmic_correctness"] == "unresolved" and grade["graded"] is not True:
        raise ValueError("unverified grade cannot establish algorithmic failure")


def seed_cohort(release: dict, admission: dict, output: Path) -> dict:
    """Persist every assignment before the independent guardian can start."""
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    slots = [{**cell, "status": "NOT_ATTEMPTED", "assigned_slot_retained": True,
              "grade": unknown_grade("not_started"), "infrastructure_unknown": False,
              "official_upstream_score": official_score_missing(),
              "costs": {"second_decision_eligible": None}, "episode_directory": None,
              "grade_directory": None, "cleanup_verified": None} for cell in release["order"]]
    summary = {"schema": SCHEMA, "release_id": release["release_id"], "release_sha256": admission["release_sha256"],
        "status": "RESERVED", "job_id": os.environ.get("SLURM_JOB_ID"), "slots": slots,
        "limits": release["limits"], "stop_reason": None, "all_controls_accepted": True,
        "source_review_accepted": True, "real_model_worker_started": False,
        "assignment": "four deterministic fixed schedules; no randomized logger or H/P policy"}
    summary.update(elapsed_seconds=0, descriptive=summarize(slots))
    worker.write_new(output / "summary.json", summary)
    return summary


def execute_cohort(release: dict, admission: dict, output: Path, *, episode_runner=None,
                   grade_runner=None, clock=None) -> dict:
    """CPU worker implementation; use run_cohort for independent hard caps."""
    episode_runner = worker.run_episode if episode_runner is None else episode_runner
    grade_runner = execute_grade if grade_runner is None else grade_runner
    clock = time.monotonic if clock is None else clock
    if not output.exists():
        summary = seed_cohort(release, admission, output)
    else:
        info = output.stat()
        summary = read_json(output / "summary.json")
        if (output.is_symlink() or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700
                or summary.get("status") != "RESERVED"
                or summary.get("release_sha256") != admission["release_sha256"]
                or [{k: cell[k] for k in release["order"][0]} for cell in summary["slots"]] != release["order"]
                or any(cell["status"] != "NOT_ATTEMPTED" for cell in summary["slots"])):
            raise ValueError("batch output is not a fresh exact preseeded assignment")
    summary["status"] = "RUNNING"
    slots = summary["slots"]
    started = clock()

    def save():
        summary["elapsed_seconds"] = clock() - started
        summary["descriptive"] = summarize(slots)
        sandbox._atomic_json(output / "summary.json", summary)

    save()
    for cell in slots:
        if release["limits"]["batch_seconds"] - (clock() - started) < SLOT_RESERVATION_SECONDS:
            summary["stop_reason"] = "joint_budget_no_complete_slot_envelope"
            break
        if controls.scoped_bytes(output) >= release["limits"]["storage_bytes"]:
            summary["stop_reason"] = "private_storage_cap"
            break
        directory = output / "episodes" / f"{cell['period']:02d}-{cell['task_id']}-{cell['schedule']}"
        cell.update(status="EPISODE_RUNNING", episode_directory=str(directory), cleanup_verified=False)
        summary["real_model_worker_started"] = True; save()
        try:
            guardian = episode_runner(public_spec(release, admission, cell["task_id"], cell["schedule"]), directory)
            cell["guardian"] = guardian
            cell["cleanup_verified"] = guardian.get("cleanup_verified") is True and guardian.get("worker_reaped") is True
            if guardian.get("abort_batch") is True or not cell["cleanup_verified"]:
                cell.update(status="CLEANUP_UNKNOWN", infrastructure_unknown=True,
                            grade=unknown_grade("worker_cleanup_unknown"))
                summary["stop_reason"] = "worker_cleanup_unknown"; save(); break
            outcome = guardian.get("outcome") if guardian.get("status") == "episode_complete" else None
            cell["costs"] = native_measurements(directory, cell["schedule"], outcome)
            if guardian.get("status") != "episode_complete":
                cell.update(status="EPISODE_UNKNOWN" if guardian.get("status") == "infrastructure_unknown" else "OPERATIONAL_STOP",
                    infrastructure_unknown=guardian.get("status") == "infrastructure_unknown",
                    grade=unknown_grade(guardian.get("reason", "missing_episode_outcome")))
                save(); continue
            cell["agent_exit_status"] = outcome.get("agent_exit_status")
            if guardian.get("submission_eligible") is not True or outcome.get("submission_eligible") is not True or outcome.get("agent_exit_status") != "Submitted":
                cell.update(status="OPERATIONAL_STOP", grade=unknown_grade("no_explicit_eligible_submission"))
                save(); continue
            grade_directory = output / "grades" / f"{cell['period']:02d}-{cell['task_id']}-{cell['schedule']}"
            cell.update(status="GRADE_RUNNING", grade_directory=str(grade_directory)); save()
            graded = grade_runner(item=admission["tasks"][cell["task_id"]], slot=cell,
                episode_directory=directory, directory=grade_directory, release_sha256=admission["release_sha256"],
                apptainer=str(admission["apptainer"]), seconds=release["limits"]["grade_seconds"])
            cell["grade_evidence"] = graded
            cell["official_upstream_score"] = graded.get("official_upstream_score", official_score_missing())
            cell["grade"] = graded.get("grade", unknown_grade("grade_evidence_missing"))
            if graded.get("cleanup_verified") is not True:
                cell.update(status="CLEANUP_UNKNOWN", infrastructure_unknown=True, cleanup_verified=False,
                            grade=unknown_grade("evaluation_cleanup_unknown"))
                summary["stop_reason"] = "evaluation_cleanup_unknown"; save(); break
            validate_grade(cell["grade"])
            cell.update(status="GRADED" if cell["grade"].get("graded") is True else "EVALUATION_UNKNOWN",
                        infrastructure_unknown=cell["grade"].get("graded") is not True)
        except BaseException as exc:
            cell.update(status="INFRASTRUCTURE_UNKNOWN", infrastructure_unknown=True,
                grade=unknown_grade(type(exc).__name__), error_type=type(exc).__name__)
            # Exceptional paths must prove the owner-pipe guardians finished;
            # incomplete/missing evidence aborts untouched future assignments.
            clean = cleanup_for_slot(cell)
            cell["cleanup_verified"] = clean
            if not clean:
                summary["stop_reason"] = "exceptional_cleanup_unknown"; save(); break
        save()
    if summary["stop_reason"]:
        for cell in slots:
            if cell["status"] == "NOT_ATTEMPTED":
                cell["grade"] = unknown_grade(summary["stop_reason"])
    summary["status"] = "INCOMPLETE_ASSIGNED_COHORT" if summary["stop_reason"] else "COMPLETED_ASSIGNED_COHORT"
    save()
    return summary


def cleanup_for_slot(cell: dict) -> bool:
    episode = Path(cell["episode_directory"]) if cell.get("episode_directory") else None
    if episode is None:
        return True
    try:
        guardian = read_json(episode / "guardian_result.json")
        if guardian.get("worker_reaped") is not True or guardian.get("cleanup_verified") is not True or guardian.get("abort_batch") is True:
            return False
        if cell.get("grade_directory"):
            grade_directory = Path(cell["grade_directory"])
            assignment = grade_directory / "assignment.json"
            workspace = grade_directory / "workspace.img"
            if assignment.exists() or workspace.exists():
                return supervisor_clean(read_json(grade_directory / "candidate.supervisor.json"))
        return True
    except (ValueError, OSError):
        return False


def finalize_interrupted(output: Path, reason: str) -> tuple[dict | None, bool]:
    if not (output / "summary.json").exists():
        return None, False
    summary = read_json(output / "summary.json")
    started = [cell for cell in summary["slots"] if cell["episode_directory"] is not None]
    clean = all(cleanup_for_slot(cell) for cell in started)
    for cell in summary["slots"]:
        if cell["episode_directory"] is not None:
            cell["cleanup_verified"] = cleanup_for_slot(cell)
        if cell["status"] in {"EPISODE_RUNNING", "GRADE_RUNNING"}:
            cell.update(status="INFRASTRUCTURE_UNKNOWN", infrastructure_unknown=True,
                cleanup_verified=cleanup_for_slot(cell), grade=unknown_grade(reason))
        elif cell["status"] == "NOT_ATTEMPTED":
            cell["grade"] = unknown_grade(reason)
    summary.update(status="INTERRUPTED_ASSIGNED_COHORT", stop_reason=reason,
                   cleanup_verified=clean, descriptive=summarize(summary["slots"]))
    sandbox._atomic_json(output / "summary.json", summary)
    return summary, clean


def guard_batch(*, command: list[str], owner_fd: int, output: Path,
                batch_seconds: float, storage_bytes: int, storage_scope: Path | None = None,
                cleanup_validator: Callable[[Path], bool] | None = None) -> dict:
    """Independent CPU guardian; owner death still closes nested owner pipes."""
    if not _finite_positive(batch_seconds) or type(storage_bytes) is not int or storage_bytes <= 0:
        raise ValueError("invalid independent batch limits")
    storage_scope = output if storage_scope is None else storage_scope
    if storage_scope.absolute() not in {output.absolute(), output.parent.absolute()}:
        raise ValueError("storage supervision must cover only the owned output or run directory")
    started = time.monotonic()
    proc = None
    reason = "guardian_error"
    error = None
    peak = 0
    selectors_owner = selectors.DefaultSelector()
    os.set_blocking(owner_fd, False)
    selectors_owner.register(owner_fd, selectors.EVENT_READ)
    try:
        # Readable EOF before launch never creates another model worker.
        if selectors_owner.select(0) and os.read(owner_fd, 4096) == b"":
            reason = "owner_eof_before_batch"
        else:
            proc = subprocess.Popen(command, start_new_session=True, close_fds=True,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            while True:
                now = time.monotonic()
                if proc.poll() is not None:
                    reason = "exited"; break
                if now - started >= batch_seconds:
                    reason = "batch_deadline"; break
                used = controls.scoped_bytes(storage_scope)
                peak = max(peak, used)
                if used > storage_bytes:
                    reason = "storage_limit"; break
                if selectors_owner.select(.05) and os.read(owner_fd, 4096) == b"":
                    reason = "owner_eof"; break
    except BaseException as exc:
        error = type(exc).__name__
    finally:
        selectors_owner.close(); os.close(owner_fd)
        group_kill_sent = False
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                # An exited CPU child may have left descendants in its group.
                # Always stop that owned group, even when the child is reaped.
                try:
                    try:
                        proc.wait(timeout=.1)
                    except subprocess.TimeoutExpired:
                        pass
                    os.killpg(proc.pid, signal.SIGKILL); group_kill_sent = True
                except ProcessLookupError:
                    pass
                proc.wait(timeout=3)
            except ProcessLookupError:
                proc.wait(timeout=3)
            except (OSError, subprocess.TimeoutExpired) as exc:
                error = type(exc).__name__
        reaped = proc is None or proc.poll() is not None
        clean = False
        until = time.monotonic() + 20
        summary = None
        while reaped and output.exists():
            try:
                if reason == "exited" and (output / "summary.json").exists():
                    summary = read_json(output / "summary.json")
                    if proc.returncode != 0 or summary.get("status") not in {"COMPLETED_ASSIGNED_COHORT", "INCOMPLETE_ASSIGNED_COHORT"}:
                        summary, clean = finalize_interrupted(output, f"coordinator_exit_{proc.returncode}_before_completion")
                    else:
                        clean = all(cleanup_for_slot(cell) for cell in summary["slots"] if cell["episode_directory"] is not None)
                else:
                    summary, clean = finalize_interrupted(output, reason)
            except (ValueError, OSError):
                clean = False
            if clean and cleanup_validator is not None:
                try:
                    clean = cleanup_validator(output) is True
                except (ValueError, OSError):
                    clean = False
            if clean or time.monotonic() >= until:
                break
            time.sleep(.05)
        receipt = {"schema": "dtr.req030aj.batch_guardian.v1", "reason": reason,
            "coordinator_pid": proc.pid if proc else None, "returncode": proc.returncode if proc else None,
            "coordinator_reaped": reaped, "cleanup_verified": clean and error is None,
            "coordinator_group_kill_sent": group_kill_sent,
            "abort_future_execution": not (reaped and clean and error is None), "error": error,
            "elapsed_seconds": time.monotonic() - started, "batch_seconds": batch_seconds,
            "peak_observed_private_bytes": peak, "storage_bytes": storage_bytes,
            "storage_enforcement": "sampled termination; transient overshoot possible",
            "all_assigned_slots_retained": bool(summary and len(summary["slots"]) == 32)}
        worker.write_new(output.parent / (output.name + ".batch_guardian.json"), receipt)
    return receipt


def run_cohort(release_path: Path, expected_sha: str, output: Path) -> dict:
    """Only production entry: validate, independent guardian, CPU cohort exec."""
    if "torch" in sys.modules:
        raise RuntimeError("cohort parent must not import Torch")
    release, admission = validate_admission(release_path, expected_sha)
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError("cohort output already exists; no retries")
    sandbox.require_disk_floor(output.parent, release["limits"]["min_free_bytes"])
    seed_cohort(release, admission, output)
    command = [sys.executable, "-m", "experiments.lead_req030.req030aj_cohort", "guard",
        "--release", str(release_path.absolute()), "--release-sha256", expected_sha, "--output", str(output)]
    rfd, wfd = os.pipe()
    guard = None
    try:
        guard = subprocess.Popen(command + ["--owner-fd", str(rfd)], pass_fds=(rfd,), close_fds=True,
            start_new_session=True, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(rfd); rfd = None
        guard.wait(timeout=release["limits"]["batch_seconds"] + 45)
    finally:
        if rfd is not None:
            os.close(rfd)
        os.close(wfd)
        if guard is not None and guard.poll() is None:
            try:
                guard.wait(timeout=30)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("batch guardian cleanup unknown; no later execution") from exc
    receipt = read_json(output.parent / (output.name + ".batch_guardian.json"))
    if guard.returncode != 0 or receipt.get("abort_future_execution") is True:
        raise RuntimeError("whole-batch cleanup unverified; retain all artifacts and assignments")
    return read_json(output / "summary.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("run", "guard", "worker"))
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--owner-fd", type=int)
    args = parser.parse_args()
    if args.mode == "run":
        run_cohort(args.release, args.release_sha256, args.output)
        return
    release, admission = validate_admission(args.release, args.release_sha256)
    if args.mode == "worker":
        execute_cohort(release, admission, args.output)
    else:
        if args.owner_fd is None:
            raise ValueError("independent batch owner pipe required")
        guard_batch(command=[sys.executable, "-m", "experiments.lead_req030.req030aj_cohort", "worker",
            "--release", str(args.release), "--release-sha256", args.release_sha256, "--output", str(args.output)],
            owner_fd=args.owner_fd, output=args.output, batch_seconds=release["limits"]["batch_seconds"],
            storage_bytes=release["limits"]["storage_bytes"])


if __name__ == "__main__":
    main()
