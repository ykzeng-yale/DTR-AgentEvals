"""Read-only independent receipt replay for the prospective AL development cohort.

No model is loaded, no task command is executed and no outcome is selected. The
strict and upstream parser kernels are the frozen existing code; independence
means raw-artifact acquisition and re-execution, not a second scoring definition.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from experiments.lead_req030 import req030aj_cohort as joined
from experiments.lead_req030 import req030ai_candidate_grade as strict
from experiments.lead_req030 import req030aj_official_grade as upstream

TASK_IDS = tuple(joined.controls.TASK_IDS)
SCHEDULES = ("SS", "SL", "LS", "LL")
ENVIRONMENT_STAGES = ("isolation", "source", "runtime", "candidate", "test_checkout", "test_patch", "test_run")
TASK_MODULES = dict(zip(TASK_IDS, (("django",), ("matplotlib", "matplotlib._path"),
    ("requests",), ("xarray",), ("pylint",), ("pytest", "_pytest"),
    ("sklearn", "sklearn.__check_build._check_build"), ("sphinx",))))


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def replay_environment_stages(*, raw: bytes, supervisor: dict, task_id: str) -> dict:
    """Independent complete setup/runtime/stage admission from fixed raw lines."""
    result = {"schema": "dtr.req030al.independent_environment_replay.v1", "accepted": False,
              "reason": "incomplete_or_invalid_environment_evidence", "task_id": task_id, "raw_sha256": sha(raw)}
    try:
        stages, runtimes = [], []
        text = raw.decode("utf-8", "strict")
        for line in text.splitlines():
            if line.startswith("DTR_AL_STAGE\t"):
                fields = line.split("\t")
                if len(fields) != 3 or not fields[2].isdigit():
                    return result
                stages.append((fields[1], int(fields[2])))
            elif line.startswith("DTR_AL_RUNTIME\t"):
                runtimes.append(strict.parse_unique(line.removeprefix("DTR_AL_RUNTIME\t").encode()))
        result["stages"] = [{"stage": stage, "returncode": rc} for stage, rc in stages]
        if ([stage for stage, _ in stages] != list(ENVIRONMENT_STAGES)
                or any(rc != 0 for _, rc in stages[:-1]) or stages[-1][1] not in (0, 1)
                or len(runtimes) != 1 or "DTR_SETUP_FAILURE" in text
                or supervisor.get("reason") != "exited" or supervisor.get("error") is not None
                or type(supervisor.get("retained_bytes")) is not int or supervisor["retained_bytes"] != len(raw)
                or type(supervisor.get("returncode")) is not int or supervisor["returncode"] != stages[-1][1]):
            return result
        runtime = runtimes[0]
        if (set(runtime) != {"python", "executable", "modules", "localhost", "interfaces", "routes", "packages"}
                or not isinstance(runtime["python"], str) or not runtime["python"]
                or runtime["executable"] != "/opt/miniconda3/envs/testbed/bin/python"
                or not isinstance(runtime["localhost"], list) or not runtime["localhost"]
                or not set(runtime["localhost"]) <= {"127.0.0.1", "::1"}
                or runtime["interfaces"] != ["lo"] or runtime["routes"] != []
                or not isinstance(runtime["modules"], list)
                or tuple(m.get("module") for m in runtime["modules"]) != TASK_MODULES[task_id]
                or any(set(m) != {"module", "file"} or not isinstance(m["file"], str)
                       or not m["file"].startswith("/testbed/") or ".." in Path(m["file"]).parts
                       for m in runtime["modules"])
                or not isinstance(runtime["packages"], list) or not runtime["packages"]
                or any(set(p) != {"name", "version"} or any(not isinstance(p[k], str) or not p[k] for k in p)
                       for p in runtime["packages"])
                or runtime["packages"] != sorted(runtime["packages"], key=lambda p: (p["name"], p["version"]))):
            return result
        result.update(accepted=True, reason="all_setup_stages_and_runtime_verified", runtime=runtime,
                      runtime_sha256=sha(canonical(runtime)))
    except (KeyError, TypeError, ValueError, UnicodeError):
        pass
    return result


def replay_control_artifacts(*, task_id: str, repo: str, evaluation: dict,
                             raw: bytes, supervisor: dict, mode: str) -> dict:
    """Re-execute frozen strict control parsing plus independent stage audit."""
    if task_id not in TASK_IDS or strict.TASK_REPOS.get(task_id) != repo or mode not in ("baseline", "reference"):
        raise ValueError("frozen task and exact control arm required")
    environment = replay_environment_stages(raw=raw, supervisor=supervisor, task_id=task_id)
    assessed = joined.controls.assess(raw, supervisor, evaluation, mode, joined.controls.pinned_parsers()[repo])
    return {"schema": "dtr.req030al.independent_control_replay.v1", "task_id": task_id,
            "mode": mode, "accepted": environment["accepted"] and assessed["accepted"],
            "environment": environment, "strict": assessed, "raw_sha256": sha(raw)}


def summarize_control_replays(replays: list[dict]) -> dict:
    """No passing subset; require every control and stable prepatch runtime."""
    if (len(replays) != 16 or {(r.get("task_id"), r.get("mode")) for r in replays}
            != {(tid, mode) for tid in TASK_IDS for mode in ("baseline", "reference")}):
        raise ValueError("all sixteen unique unchanged/reference control arms required")
    runtime_stable = {}
    for tid in TASK_IDS:
        arms = [r for r in replays if r["task_id"] == tid]
        identities = [r.get("environment", {}).get("runtime_sha256") for r in arms]
        runtime_stable[tid] = identities[0] is not None and identities[0] == identities[1]
    accepted = all(r.get("accepted") is True for r in replays) and all(runtime_stable.values())
    return {"schema": "dtr.req030al.independent_control_summary.v1", "task_count": 8,
            "assigned_control_arms": 16, "accepted_arms": sum(r.get("accepted") is True for r in replays),
            "all_controls_accepted": accepted, "prepatch_runtime_stable_by_task": runtime_stable,
            "model_admission_environment_gate": "PASS" if accepted else "HOLD_ALL_MODELS",
            "official_docker_execution_verified": False}


def summarize_slots(slots: list[dict]) -> dict:
    """Recount the fixed assignment; missing correctness bounds are not CIs."""
    assignments = {(task, schedule) for task in TASK_IDS for schedule in SCHEDULES}
    if (not isinstance(slots, list) or len(slots) != 32
            or any(not isinstance(cell, dict) for cell in slots)
            or {(c.get("task_id"), c.get("schedule")) for c in slots} != assignments):
        raise ValueError("exactly all 32 unique assigned task-schedule slots required")
    invocations = [c.get("invocation_id") for c in slots]
    if any(not isinstance(i, str) or not i for i in invocations) or len(set(invocations)) != 32:
        raise ValueError("unique immutable invocation IDs required")
    states = []
    for cell in slots:
        if cell.get("assigned_slot_retained") is not True:
            raise ValueError("assigned slot may not be removed")
        grade = cell.get("grade")
        joined.validate_grade(grade)
        status = cell.get("status")
        if not isinstance(status, str):
            raise ValueError("actual slot state required")
        opportunity = cell.get("costs", {}).get("second_decision_eligible")
        if opportunity is not None and type(opportunity) is not bool:
            raise ValueError("opportunity must be verified true, false or unknown")
        if type(cell.get("infrastructure_unknown")) is not bool:
            raise ValueError("infrastructure classification must be explicit")
        if status == "NOT_ATTEMPTED" and (grade["operational_resolution"] != 0
                or grade["algorithmic_correctness"] != "unknown" or opportunity is not None):
            raise ValueError("unstarted slot cannot supply outcome or opportunity")
        states.append((cell, grade, opportunity))

    def counts(group):
        resolved = sum(g["operational_resolution"] for _, g, _ in group)
        failed = sum(g["algorithmic_correctness"] == "unresolved" for _, g, _ in group)
        unknown = sum(g["algorithmic_correctness"] == "unknown" for _, g, _ in group)
        if resolved + failed + unknown != len(group):
            raise ValueError("resolution/correctness counts do not cover assignments")
        denominator = len(group)
        return {"assigned": denominator, "verified_resolved": resolved,
                "known_algorithmic_unresolved": failed, "algorithmic_unknown": unknown,
                "operational_fraction": resolved / denominator,
                "missing_correctness_bounds": [resolved / denominator, (resolved + unknown) / denominator]}

    def opportunities(group):
        return {"assigned": len(group), "verified_eligible": sum(o is True for _, _, o in group),
                "verified_not_eligible": sum(o is False for _, _, o in group),
                "unknown": sum(o is None for _, _, o in group)}

    by_schedule = {s: counts([row for row in states if row[0]["schedule"] == s]) for s in SCHEDULES}
    s_start = [row for row in states if row[0]["schedule"][0] == "S"]
    infra = sum(c["infrastructure_unknown"] for c, _, _ in states)
    complete = all(c["status"] not in {"NOT_ATTEMPTED", "RESERVED", "EPISODE_RUNNING", "GRADE_RUNNING"}
                   for c, _, _ in states)
    floors = {"SS_at_least_2_of_8": by_schedule["SS"]["verified_resolved"] >= 2,
              "LL_at_least_2_of_8": by_schedule["LL"]["verified_resolved"] >= 2,
              "S_start_at_least_8_of_16_eligible": opportunities(s_start)["verified_eligible"] >= 8,
              "fewer_than_4_of_32_infrastructure_failures": infra < 4}
    decision = ("PASS_DISCRETIONARY_FEASIBILITY_FLOORS" if complete and all(floors.values())
                else "INCOMPLETE_NO_FUNDING_CONCLUSION" if not complete
                else "DO_NOT_EXPAND_THIS_CONFIGURATION")
    return {"schema": "dtr.req030al.independent_summary.v1", "task_count": 8,
            "assigned_slots": 32, "by_schedule": by_schedule, "overall": counts(states),
            "opportunity_all": opportunities(states), "opportunity_S_start": opportunities(s_start),
            "infrastructure_unknown_slots": infra,
            "unstarted_slots": sum(c["status"] == "NOT_ATTEMPTED" for c, _, _ in states),
            "all_slots_terminal": complete, "spending_floors": floors, "decision": decision,
            "inference": "Descriptive purposive eight-task DEVELOPMENT audit. Fixed schedules are not an H/P contrast or randomized OPE data. Bounds are not confidence intervals.",
            "automatic_further_compute_authorized": False}


def replay_native(*, episode_directory: Path, schedule: str, outcome: dict | None,
                  tokenizer=None, public_projection: dict | None = None) -> dict:
    """Replay durable counts, then optional CPU tokenizer/history/decode equality.

    A supplied tokenizer must already come from the frozen verified files. This
    function never downloads one. With no tokenizer, token/render/decode replay
    remains explicitly unverified; recorded integers are not tokenizer evidence.
    """
    result = joined.native_measurements(episode_directory, schedule, outcome)
    result.update(tokenizer_replay_verified=False, trajectory_prefix_replay_verified=False,
                  decoded_output_replay_verified=False, native_replay_request_count=0,
                  public_initial_context_verified=False,
                  replay_scope="durable binding/accounting only; no tokenizer supplied")
    ledger = episode_directory / "episode" / "agent" / "events.jsonl"
    if tokenizer is None or not ledger.exists():
        return result
    raw = joined.worker.read_private(ledger, joined.worker.MAX_NATIVE)
    events = [joined.worker.parse_json(line) for line in raw.splitlines()]
    requests = [e for e in events if e.get("event") == "request"]
    responses = {e["physical_calls"]: e for e in events if e.get("event") == "response"}
    for request in requests:
        encoded = tokenizer(request["rendered"], add_special_tokens=False)
        ids = encoded["input_ids"]
        if ids and isinstance(ids[0], list):
            if len(ids) != 1:
                raise ValueError("tokenizer replay must have one sequence")
            ids = ids[0]
        if list(ids) != request["input_ids"]:
            raise ValueError("native rendered-to-token replay differs")
    result.update(tokenizer_replay_verified=True, native_replay_request_count=len(requests),
                  replay_scope="all recorded rendered prompts retokenized with supplied frozen tokenizer")

    trajectory_path = episode_directory / "episode" / "agent" / "trajectory.json"
    if not trajectory_path.exists():
        trajectory_path = trajectory_path.with_name("trajectory.partial.json")
    if not trajectory_path.exists():
        if responses:
            raise ValueError("returned native calls require full or partial trajectory")
        return result
    trajectory_raw = joined.worker.read_private(trajectory_path, 256 * 1024 * 1024)
    if outcome is not None and sha(trajectory_raw) != outcome.get("trajectory_sha256"):
        raise ValueError("terminal trajectory hash differs")
    trajectory = joined.worker.parse_json(trajectory_raw)
    messages = trajectory.get("messages")
    if not isinstance(messages, list):
        raise ValueError("trajectory messages required for prefix replay")
    if public_projection is not None:
        if (not isinstance(public_projection, dict) or set(public_projection) != {
                "instance_id", "repo", "base_commit", "problem_statement"}
                or strict.TASK_REPOS.get(public_projection["instance_id"]) != public_projection["repo"]
                or not joined.worker._hex(public_projection["base_commit"], 40)
                or not isinstance(public_projection["problem_statement"], str)
                or not public_projection["problem_statement"].strip()):
            raise ValueError("exact four-field public projection required")
        expected_initial = [{"role": "system", "content": joined.sandbox.SYSTEM_TEMPLATE},
            {"role": "user", "content": joined.sandbox.INSTANCE_TEMPLATE.replace(
                "{{task}}", public_projection["problem_statement"])}]
        if (len(messages) < 2 or [{k: m.get(k) for k in ("role", "content")} for m in messages[:2]]
                != expected_initial):
            raise ValueError("initial context differs from frozen public-only task/prompt")
        result["public_initial_context_verified"] = True
    seen = set()
    for index, message in enumerate(messages):
        binding = message.get("extra", {}).get("native_binding")
        if not isinstance(binding, dict):
            continue
        call = binding.get("physical_calls")
        if call in seen or call not in responses:
            raise ValueError("trajectory has duplicate or unmatched native response")
        request = requests[call - 1]
        response = responses[call]
        seen.add(call)
        visible = []
        for prior in messages[:index]:
            if prior.get("role") not in {"system", "user", "assistant"} or not isinstance(prior.get("content"), str):
                raise ValueError("unexpected visible pre-generation trajectory message")
            visible.append({"role": prior["role"], "content": prior["content"]})
        message_sha = sha(json.dumps(visible, ensure_ascii=False, separators=(",", ":")).encode())
        rendered = tokenizer.apply_chat_template(visible, tokenize=False, add_generation_prompt=True)
        if message_sha != request["messages_sha256"] or rendered != request["rendered"]:
            raise ValueError("native request differs from actual trajectory prefix")
        for key in ("model_id", "revision", "messages_sha256", "rendered_sha256", "input_tokens",
                    "physical_calls", "output_ids", "output_tokens", "finish_reason"):
            if binding.get(key) != response.get(key):
                raise ValueError("trajectory-native response binding differs")
        decoded = tokenizer.decode(response["output_ids"], skip_special_tokens=False)
        observed = message["content"] if message.get("role") == "assistant" else message.get("extra", {}).get("raw_model_output")
        if decoded != observed:
            raise ValueError("native output decode differs from trajectory text")
        expected_finish = "eos" if response["output_ids"] and response["output_ids"][-1] == tokenizer.eos_token_id else "length_or_stop"
        if response.get("finish_reason") != expected_finish:
            raise ValueError("finish reason differs from exact output token IDs")
    if seen != set(responses):
        raise ValueError("trajectory omits a returned native response")
    result.update(trajectory_prefix_replay_verified=True, decoded_output_replay_verified=True,
                  trajectory_sha256=sha(trajectory_raw), returned_calls_replayed=len(seen),
                  replay_scope="all recorded prompt tokens, actual trajectory prefixes, returned decode and finish reasons")
    return result


def replay_candidate_artifacts(*, task: dict, evaluator_bundle: bytes, slot: dict,
                               episode_directory: Path, grade_directory: Path,
                               release_sha256: str, expected_prepatch_runtime_sha256: str | None = None) -> dict:
    """Bind retrieved candidate artifacts to the prospectively assigned slot."""
    outcome = joined.read_json(episode_directory / "worker_result.json")
    guardian = joined.read_json(episode_directory / "guardian_result.json")
    if (guardian.get("cleanup_verified") is not True or guardian.get("worker_reaped") is not True
            or guardian.get("submission_eligible") is not True or outcome.get("submission_eligible") is not True
            or outcome.get("agent_exit_status") != "Submitted"):
        raise ValueError("only independently cleaned explicit submission may be scored")
    patch = joined.worker.read_private(episode_directory / "episode" / "patch.diff", strict.MAX_PATCH_BYTES)
    raw = joined.worker.read_private(grade_directory / "candidate.out", joined.sandbox.MAX_EPISODE_OUTPUT)
    supervisor = joined.read_json(grade_directory / "candidate.supervisor.json")
    assignment = joined.read_json(grade_directory / "assignment.json")
    observed = joined.read_json(grade_directory / "binding.json")
    prospective = {"task_id": task["instance_id"], "repo": task["repo"], "base_commit": task["base_commit"],
                   "policy_id": slot["schedule"], "invocation_id": slot["invocation_id"],
                   "release_sha256": release_sha256, "evaluator_bundle_sha256": sha(evaluator_bundle),
                   "patch_sha256": sha(patch), "parser_sha256": strict.PARSER_SHA256}
    if assignment != prospective or outcome.get("patch_sha256") != sha(patch) or outcome.get("patch_bytes") != len(patch):
        raise ValueError("assigned invocation/submitted patch differs")
    marker = joined.INVOCATION_MARKER + sha(canonical(prospective))
    if raw.decode("utf-8", "replace").splitlines().count(marker) != 1:
        raise ValueError("exact evaluator invocation marker required once")
    environment = replay_environment_stages(raw=raw, supervisor=supervisor, task_id=task["instance_id"])
    if expected_prepatch_runtime_sha256 is not None and not joined.worker._hex(expected_prepatch_runtime_sha256):
        raise ValueError("exact accepted baseline prepatch runtime identity required")
    runtime_identity_verified = (expected_prepatch_runtime_sha256 is not None
        and environment.get("runtime_sha256") == expected_prepatch_runtime_sha256)
    if expected_prepatch_runtime_sha256 is not None and not runtime_identity_verified:
        environment.update(accepted=False, reason="candidate_prepatch_runtime_differs_from_accepted_controls")
    expected = {**prospective, "raw_sha256": sha(raw), "supervisor_sha256": sha(strict.canonical(supervisor))}
    scoring_task = {k: task[k] for k in ("instance_id", "repo", "base_commit")} | {"evaluator_bundle_sha256": sha(evaluator_bundle)}
    grade = strict.replay_candidate(task=scoring_task, evaluator_bundle=evaluator_bundle, raw=raw,
        supervisor=supervisor, patch=patch, expected_patch_sha256=outcome["patch_sha256"],
        expected_binding=expected, observed_binding=observed)
    official = upstream.replay_official(task=scoring_task, evaluator_bundle=evaluator_bundle, raw=raw,
        patch=patch, expected_binding=expected, observed_binding=observed, strict_grade=grade)
    if not environment["accepted"]:
        grade = joined.unknown_grade("independent_environment_stage_replay_failed")
    return {"schema": "dtr.req030al.independent_candidate_replay.v1", "task_id": task["instance_id"],
            "schedule": slot["schedule"], "invocation_id": slot["invocation_id"], "grade": grade,
            "environment": environment,
            "prepatch_runtime_identity_verified": runtime_identity_verified,
            "official_upstream_score": official, "raw_sha256": sha(raw), "patch_sha256": sha(patch),
            "cleanup_verified": joined.supervisor_clean(supervisor),
            "official_docker_execution_verified": False}
