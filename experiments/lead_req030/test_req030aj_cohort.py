"""Authored inert full-32 coordinator/fault fixtures; no models or containers."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

from experiments.lead_req030 import req030aj_cohort as cohort


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(cohort.canonical(value))
    return cohort.file_pin(path)


def test_guard_storage_scope_can_include_owned_model_cache(admitted, tmp_path, monkeypatch):
    release, admission, _ = admitted
    output = tmp_path / "run" / "results"
    output.parent.mkdir()
    cohort.seed_cohort(release, admission, output)
    (output.parent / "models").mkdir()
    (output.parent / "models" / "inert.asset").write_bytes(b"x" * 4096)
    scopes = []
    original = cohort.controls.scoped_bytes
    def measured(path):
        scopes.append(path)
        return original(path)
    monkeypatch.setattr(cohort.controls, "scoped_bytes", measured)
    rfd, wfd = os.pipe()
    try:
        receipt = cohort.guard_batch(command=[sys.executable, "-c", "import time; time.sleep(60)"],
            owner_fd=rfd, output=output, batch_seconds=5, storage_bytes=4095, storage_scope=output.parent)
    finally:
        os.close(wfd)
    assert receipt["reason"] == "storage_limit"
    assert receipt["cleanup_verified"] is True
    assert scopes and all(scope == output.parent for scope in scopes)
    assert receipt["all_assigned_slots_retained"] is True


def test_guard_refuses_storage_scope_outside_owned_run(tmp_path):
    with pytest.raises(ValueError, match="owned output or run"):
        cohort.guard_batch(command=[sys.executable, "-c", "pass"], owner_fd=-1,
            output=tmp_path / "run" / "results", batch_seconds=5, storage_bytes=1,
            storage_scope=tmp_path)


def test_guard_waits_for_qualification_cleanup_even_when_no_model_slot_started(admitted, tmp_path):
    release, admission, _ = admitted
    output = tmp_path / "run" / "results"
    cohort.seed_cohort(release, admission, output)
    checks = []
    def qualified_cleanup(path):
        checks.append(path)
        return len(checks) >= 2
    rfd, wfd = os.pipe()
    try:
        receipt = cohort.guard_batch(command=[sys.executable, "-c", "pass"], owner_fd=rfd,
            output=output, batch_seconds=5, storage_bytes=1 << 20,
            cleanup_validator=qualified_cleanup)
    finally:
        os.close(wfd)
    assert checks == [output, output]
    assert receipt["cleanup_verified"] is True
    assert receipt["all_assigned_slots_retained"] is True


def framed(repo, required, statuses):
    lines = []
    for node, status in zip(required, statuses, strict=True):
        if repo == "django/django":
            lines.append(node + " ... " + {"PASSED": "ok", "FAILED": "FAIL", "SKIPPED": "skipped 'inert'"}[status])
        elif repo in {"scikit-learn/scikit-learn", "sphinx-doc/sphinx"}:
            lines.append(node + " " + status)
        else:
            lines.append(status + " " + node)
    return ("DTR_TEST_START\n>>>>> Start Test Output\n" + "\n".join(lines) +
            "\n>>>>> End Test Output\nDTR_TEST_END\n").encode()


def supervisor(raw, **extra):
    return {"reason": "exited", "pid": 123, "returncode": 0, "retained_bytes": len(raw), "elapsed": .1, "error": None, **extra}


@pytest.fixture
def admitted(tmp_path):
    """Synthetic byte-pinned controls use all eight real official parsers."""
    tasks, original_tasks, receipts = [], [], []
    for index, (tid, repo) in enumerate(cohort.grader.TASK_REPOS.items()):
        base = f"{index + 1:040x}"
        public = {"instance_id": tid, "repo": repo, "base_commit": base,
                  "problem_statement": "Public authored inert issue; not a model outcome"}
        nodes = (["test_target (inert.FixtureCase)", "test_preserved (inert.FixtureCase)"]
                 if repo == "django/django" else ["inert/test.py::test_target", "inert/test.py::test_preserved"])
        evaluation = {"instance_id": tid, "repo": repo, "base_commit": base,
            "fail_to_pass": nodes[:1], "pass_to_pass": nodes[1:],
            "stock_eval_script": "# EVALUATOR_ONLY_INERT_SENTINEL\n",
            "reference_patch": "REFERENCE_ONLY_INERT_SENTINEL",
            "test_patch": "TEST_ONLY_INERT_SENTINEL"}
        public_pin = save(tmp_path / "inputs" / "public" / (tid + ".json"), public)
        evaluator_pin = save(tmp_path / "inputs" / "evaluator" / (tid + ".json"), evaluation)
        tasks.append({"instance_id": tid, "repo": repo, "base_commit": base,
                      "public_projection": public_pin, "evaluator_bundle": evaluator_pin})
        original_tasks.append({"instance_id": tid, "repo": repo, "base_commit": base,
            "public_projection_sha256": public_pin["sha256"], "public_projection_bytes": len(cohort.canonical(public)),
            "evaluator_bundle_sha256": evaluator_pin["sha256"], "evaluator_bundle_bytes": len(cohort.canonical(evaluation)),
            "stock_eval_script_sha256": cohort.sha(evaluation["stock_eval_script"].encode()),
            "reference_patch_sha256": cohort.sha(evaluation["reference_patch"].encode()),
            "fail_to_pass_count": 1, "pass_to_pass_count": 1})
        image = tmp_path / "sources" / (tid + ".sif")
        source = tmp_path / "sources" / (tid + ".tar")
        image.parent.mkdir(exist_ok=True)
        image.write_bytes(b"authored inert SIF identity only")
        source.write_bytes(b"authored inert source identity only")
        source_review = {"schema": "dtr.req030aj.source_acceptance.v1", "task_id": tid,
            "image_sha256": cohort.worker.digest_file(image), "source_tar_sha256": cohort.worker.digest_file(source),
            "head": base, "tree": "a" * 40, "base_tree": "a" * 40, "accepted": True, "model_tree_contract": "equal_tree"}
        review_pin = save(tmp_path / "sources" / (tid + ".source_review.json"), source_review)
        arms = {}
        for mode in ("baseline", "reference"):
            raw = framed(repo, nodes, ["FAILED" if mode == "baseline" else "PASSED", "PASSED"])
            out = tmp_path / "controls" / tid / (mode + ".out")
            out.parent.mkdir(parents=True, exist_ok=True); out.write_bytes(raw)
            arms[mode] = {"raw": cohort.file_pin(out), "supervisor": save(out.with_suffix(".json"), supervisor(raw, returncode=1 if mode == "baseline" else 0))}
        receipts.append({"task_id": tid, "image": cohort.file_pin(image), "source_tar": cohort.file_pin(source),
                         "source_acceptance": review_pin, "controls": arms})
    control_release = {"request": "DTR-REQ-030AH", "release_id": "authored-inert-controls",
                       "model_execution_authorized": False, "tasks": original_tasks}
    control_pin = save(tmp_path / "inputs" / "control_release.json", control_release)
    acceptance = {"schema": "dtr.req030aj.control_acceptance.v1", "control_release_sha256": control_pin["sha256"],
                  "all_controls_accepted": True, "source_review_accepted": True, "tasks": receipts}
    acceptance_pin = save(tmp_path / "inputs" / "control_acceptance.json", acceptance)
    apptainer = tmp_path / "inert_apptainer"; apptainer.write_bytes(b"no executable fixture")
    model_root = tmp_path / "inert_models"; model_root.mkdir()
    release = {"schema": cohort.SCHEMA, "request": "DTR-REQ-030AJ", "release_id": "authored-inert-32-slot-fixture",
        "phase": "DEVELOPMENT", "model_execution_authorized": True, "control_release": control_pin,
        "control_acceptance": acceptance_pin, "tasks": tasks, "order": cohort.frozen_order("authored-inert-32-slot-fixture"),
        "models": {"models": [{**pin, "files": [{"path": "inert.asset", "bytes": 1, "sha256": "a" * 64}]} for pin in cohort.MODEL_PINS.values()]},
        "runtime": {"python": "3.11.11", "cuda": "12.8", "versions": {
            **{p: "inert" for p in cohort.worker.RUNTIME_PACKAGES}, "torch": "2.9.1", "transformers": "4.51.3"}},
        "resource_cap": {"gpu_model": "inert-unexecuted", "gpu_count": 1, "cpu": 4, "memory_bytes": 32 << 30, "slurm_seconds": 200000},
        "limits": {"batch_seconds": 180000, "storage_bytes": 80 << 30, "min_free_bytes": 1,
            "grade_seconds": 900, "slot_reservation_seconds": cohort.SLOT_RESERVATION_SECONDS},
        "source_pins": {rel: cohort.worker.digest_file(cohort.ROOT / rel) for rel in cohort.REQUIRED_SOURCES},
        "model_root": str(model_root), "apptainer": cohort.file_pin(apptainer), "token_contract": copy.deepcopy(cohort.TOKEN_CONTRACT)}
    release_path = tmp_path / "prospective_inert_release.json"
    pin = save(release_path, release)
    doc, admission = cohort.validate_admission(release_path, pin["sha256"])
    return doc, admission, release_path


def native_events(schedule, calls=10, *, eligible9=True):
    events, counts = [], {"S": 0, "L": 0}
    binding = {"messages_sha256": "b" * 64, "rendered_sha256": cohort.sha(b"inert rendered"),
        "input_ids": [1, 2, 3], "input_tokens": 3, "max_new_tokens": 1536, "context_limit": 16384,
        "reserved_total_tokens": 1539, "remaining_input_token_capacity": 14845, "admitted": True}
    def emit(event): events.append({"sequence": len(events) + 1, **event})
    for call in range(1, calls + 1):
        action = schedule[0 if call <= 8 else 1]
        if call in (1, 9):
            assert call != 9 or eligible9
            emit({"event": "routing_decision", "schedule": schedule, "logical_call": call,
                "decision_index": 1 if call == 1 else 2, "physical_calls_before": call - 1,
                "per_model_physical_calls_before": copy.deepcopy(counts), "model_action": action,
                "model_id": cohort.MODEL_PINS[action]["repo"], "revision": cohort.MODEL_PINS[action]["revision"],
                "remaining_logical_calls_including_current": 25 - call, "probability": 1.0,
                "probability_vector": {a: float(a == action) for a in counts}, "randomized_logger": False,
                "both_action_reservations": {a: copy.deepcopy(binding) for a in counts},
                "remaining_episode_wall_seconds": 2700 - call, "episode_deadline_monotonic": 2800,
                "measured_at_monotonic": 100 + call, "workspace_fingerprint": {
                    "method": "sha256_raw_workspace_image", "sha256": "a" * 64, "bytes": 64,
                    "hash_elapsed_seconds": .01, "semantic_content_identity": False}})
        counts[action] += 1
        request = {"event": "request", "schedule": schedule, "logical_call": call,
            "model_action": action, "model_id": cohort.MODEL_PINS[action]["repo"],
            "revision": cohort.MODEL_PINS[action]["revision"], "physical_calls": call,
            "per_model_physical_calls": counts[action], "rendered": "inert rendered",
            **{k: binding[k] for k in ("messages_sha256", "rendered_sha256", "input_ids", "input_tokens")}}
        emit(request)
        emit({**{k: v for k, v in request.items() if k not in {"event", "input_ids", "rendered"}},
            "event": "response", "output_ids": [42, 2], "output_tokens": 2,
            "finish_reason": "eos", "elapsed_seconds": .01})
    return events


def authored_episode(spec, directory, *, calls=10, submitted=True, cleanup=True, status="episode_complete"):
    # No worker, model, CUDA, shell tool, container or generated action runs.
    directory.mkdir(parents=True, mode=0o700)
    agent = directory / "episode" / "agent"; agent.mkdir(parents=True)
    events = native_events(spec["schedule"], calls)
    raw = b"".join(cohort.canonical(event) for event in events)
    (agent / "events.jsonl").write_bytes(raw)
    patch = b"authored inert candidate; never applied by a real container"
    (directory / "episode" / "patch.diff").write_bytes(patch)
    outcome = {"agent_exit_status": "Submitted" if submitted else "LimitsExceeded", "submission_eligible": submitted,
        "physical_calls": calls, "event_log_sha256": cohort.sha(raw), "patch_sha256": cohort.sha(patch),
        "patch_bytes": len(patch), "peak_allocated_bytes": 1, "peak_reserved_bytes": 2}
    save(directory / "worker_result.json", outcome)
    result = {"status": status, "cleanup_verified": cleanup, "worker_reaped": cleanup,
              "abort_batch": not cleanup, "submission_eligible": submitted,
              "reason": "exited" if status == "episode_complete" else "call_deadline",
              "outcome": outcome if status == "episode_complete" else None}
    save(directory / "guardian_result.json", result)
    return result


def inert_sandbox(monkeypatch, admission, fault=None):
    made, executed = [], []
    def make(source, seed, workspace, **kwargs):
        assert not workspace.exists()
        workspace.write_bytes(b"inert independent workspace")
        made.append(str(workspace))
        return {"image_bytes": workspace.stat().st_size, "image_sha256": cohort.worker.digest_file(workspace)}
    def run(apptainer, image, workspace, command, *, output_path, receipt_path, seconds, extra_binds):
        assert command == ["/bin/bash", "/eval/run.sh"] and seconds == 900
        assignment = cohort.read_json(output_path.parent / "assignment.json")
        item = admission["tasks"][assignment["task_id"]]
        evdir = Path(extra_binds[1].removesuffix(":/eval:ro"))
        assert sorted(p.name for p in evdir.iterdir()) == ["agent.diff", "run.sh", "stock_eval.sh"]
        assert "DTR_AJ_INVOCATION=" + cohort.sha(cohort.canonical(assignment)) in (evdir / "run.sh").read_text()
        evaluation = item["evaluation"]
        nodes = evaluation["fail_to_pass"] + evaluation["pass_to_pass"]
        marker = cohort.INVOCATION_MARKER + cohort.sha(cohort.canonical(assignment))
        raw = (marker + "\n").encode() + framed(item["task"]["repo"], nodes, ["PASSED"] * len(nodes))
        receipt = supervisor(raw)
        case = fault(assignment) if fault else None
        if case == "missing_grade":
            raw = raw.replace(b">>>>> End Test Output", b"MISSING_END")
        elif case == "timeout":
            raw = (marker + "\nDTR_TEST_START\n").encode(); receipt["reason"] = "deadline"; receipt["returncode"] = -15
        elif case == "cleanup":
            receipt["error"] = "inert cleanup failure"
        elif case == "duplicate_binding":
            raw = (marker + "\n").encode() + raw
        receipt["retained_bytes"] = len(raw)
        output_path.write_bytes(raw); save(receipt_path, receipt)
        executed.append(assignment)
        return raw, receipt
    monkeypatch.setattr(cohort.sandbox, "make_workspace", make)
    monkeypatch.setattr(cohort.sandbox, "run_supervised", run)
    return made, executed


def rerun_admission(release, release_path):
    save(release_path, release)
    return cohort.validate_admission(release_path, cohort.worker.digest_file(release_path))


def test_frozen_latin_assignment_exact_all_32_no_repeated_cell():
    order = cohort.frozen_order("inert")
    assert len({cell["invocation_id"] for cell in order}) == 32
    assert {(cell["task_id"], cell["schedule"]) for cell in order} == {(t, s) for t in cohort.controls.TASK_IDS for s in cohort.SCHEDULES}
    for position in range(4):
        assert {s: sum(c["schedule"] == s and c["within_task_position"] == position for c in order) for s in cohort.SCHEDULES} == {s: 2 for s in cohort.SCHEDULES}


def test_admission_replays_all_16_and_worker_spec_has_only_public_inputs(admitted):
    release, admission, _ = admitted
    assert sum(len(t["control_replay"]) for t in admission["tasks"].values()) == 16
    for slot in release["order"]:
        spec = cohort.public_spec(release, admission, slot["task_id"], slot["schedule"])
        text = json.dumps(spec)
        assert all(s not in text for s in ("evaluator", "reference", "stock_eval", "fail_to_pass", "pass_to_pass", "TEST_ONLY", "REFERENCE_ONLY"))
        cohort.worker.validate_spec(spec)


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(model_execution_authorized=False),
    lambda r: r["order"].reverse(),
    lambda r: r["tasks"].pop(),
    lambda r: r["models"]["models"].append(copy.deepcopy(r["models"]["models"][0])),
    lambda r: r["runtime"]["versions"].pop("numpy"),
    lambda r: r["source_pins"].update({cohort.REQUIRED_SOURCES[0]: "0" * 64}),
    lambda r: r["token_contract"].update(physical_retries=1),
    lambda r: r["tasks"][0].update(hidden="forbidden"),
    lambda r: r["resource_cap"].update(gpu_count=2),
])
def test_missing_or_changed_prospective_contract_never_admits(admitted, mutation):
    release, _, path = admitted
    mutation(release)
    with pytest.raises((ValueError, KeyError)):
        rerun_admission(release, path)


def test_explicit_new_cpu_control_release_retains_same_cohort_admission(admitted):
    release, _, path = admitted
    control_path = Path(release["control_release"]["path"])
    control = cohort.read_json(control_path); control.update(request="DTR-REQ-030AJ", release_id="inert-corrected-private-storage")
    release["control_release"] = save(control_path, control)
    acceptance_path = Path(release["control_acceptance"]["path"])
    acceptance = cohort.read_json(acceptance_path); acceptance["control_release_sha256"] = release["control_release"]["sha256"]
    release["control_acceptance"] = save(acceptance_path, acceptance)
    assert rerun_admission(release, path)[0]["control_release"]["sha256"] == release["control_release"]["sha256"]


@pytest.mark.parametrize("field", ["all_controls_accepted", "source_review_accepted"])
def test_acceptance_false_rejects_entire_cohort(admitted, field):
    release, _, path = admitted
    acceptance_path = Path(release["control_acceptance"]["path"])
    acceptance = cohort.read_json(acceptance_path); acceptance[field] = False
    release["control_acceptance"] = save(acceptance_path, acceptance)
    with pytest.raises(ValueError): rerun_admission(release, path)


def test_one_missing_required_control_status_or_source_delta_rejects_all(admitted):
    release, _, path = admitted
    acceptance_path = Path(release["control_acceptance"]["path"])
    acceptance = cohort.read_json(acceptance_path)
    arm = acceptance["tasks"][4]["controls"]["reference"]
    out = Path(arm["raw"]["path"]); raw = out.read_bytes().replace(b"PASSED inert/test.py::test_target\n", b"")
    out.write_bytes(raw); arm["raw"] = cohort.file_pin(out)
    arm["supervisor"] = save(Path(arm["supervisor"]["path"]), supervisor(raw))
    release["control_acceptance"] = save(acceptance_path, acceptance)
    with pytest.raises(ValueError, match="whole cohort rejected"): rerun_admission(release, path)


def test_equal_tree_source_receipt_cannot_accept_setup_delta(admitted):
    release, _, path = admitted
    acceptance_path = Path(release["control_acceptance"]["path"]); acceptance = cohort.read_json(acceptance_path)
    item = acceptance["tasks"][0]; source_path = Path(item["source_acceptance"]["path"])
    source = cohort.read_json(source_path); source["tree"] = "c" * 40
    item["source_acceptance"] = save(source_path, source); release["control_acceptance"] = save(acceptance_path, acceptance)
    with pytest.raises(ValueError, match="equal trees"): rerun_admission(release, path)


def test_actual_grade_api_fresh_workspace_all_32_full_cohort(admitted, monkeypatch, tmp_path):
    release, admission, _ = admitted
    made, invoked = inert_sandbox(monkeypatch, admission)
    summary = cohort.execute_cohort(release, admission, tmp_path / "batch", episode_runner=authored_episode)
    assert summary["status"] == "COMPLETED_ASSIGNED_COHORT" and len(made) == len(set(made)) == len(invoked) == 32
    assert all(cell["status"] == "GRADED" and cell["grade"]["resolved"] for cell in summary["slots"])
    assert summary["descriptive"]["operational_resolution_fraction"] == 1
    assert summary["descriptive"]["second_decision_opportunity"]["S_start"] == {
        "assigned": 16, "verified_eligible": 16, "verified_not_eligible": 0, "unknown": 0, "verified_occupancy_fraction": 1}
    assert summary["descriptive"]["costs"]["native_requests"] == {"observed_sum": 320, "unknown_slots": 0}
    assert summary["descriptive"]["official_upstream_score_missing_slots"] == 32
    for cell in summary["slots"]:
        directory = Path(cell["grade_directory"])
        assert not (directory / "workspace.img").exists()
        assert all((directory / p).is_file() for p in ("assignment.json", "binding.json", "candidate.out", "candidate.supervisor.json"))
        assert cell["grade_evidence"]["binding_verified"]


@pytest.mark.parametrize("fault", ["missing_grade", "timeout", "duplicate_binding"])
def test_unknown_grade_or_timeout_continues_exactly_once_only_after_cleanup(admitted, monkeypatch, tmp_path, fault):
    release, admission, _ = admitted
    _, invoked = inert_sandbox(monkeypatch, admission, lambda a: fault if a["invocation_id"] == release["order"][0]["invocation_id"] else None)
    summary = cohort.execute_cohort(release, admission, tmp_path / "batch", episode_runner=authored_episode)
    assert len(invoked) == 32 and len({a["invocation_id"] for a in invoked}) == 32
    first = summary["slots"][0]
    assert first["status"] == "EVALUATION_UNKNOWN" and first["grade"]["algorithmic_correctness"] == "unknown"
    assert first["cleanup_verified"] and first["grade"]["operational_resolution"] == 0
    assert summary["descriptive"]["operational_resolution_fraction"] == 31 / 32


def test_uncertain_evaluator_cleanup_aborts_untouched_future_slots(admitted, monkeypatch, tmp_path):
    release, admission, _ = admitted
    _, invoked = inert_sandbox(monkeypatch, admission, lambda a: "cleanup")
    summary = cohort.execute_cohort(release, admission, tmp_path / "batch", episode_runner=authored_episode)
    assert len(invoked) == 1 and summary["stop_reason"] == "evaluation_cleanup_unknown"
    assert summary["slots"][0]["grade"]["operational_resolution"] == 0
    assert len(summary["slots"]) == 32 and summary["descriptive"]["unstarted_slots"] == 31
    assert all(not Path(c["episode_directory"]).exists() for c in summary["slots"][1:] if c["episode_directory"])


def test_uncertain_model_cleanup_never_starts_second_assigned_worker(admitted, tmp_path):
    release, admission, _ = admitted; started = []
    def run(spec, directory):
        started.append(spec); return authored_episode(spec, directory, cleanup=False)
    summary = cohort.execute_cohort(release, admission, tmp_path / "batch", episode_runner=run)
    assert len(started) == 1 and summary["stop_reason"] == "worker_cleanup_unknown"
    assert summary["descriptive"]["unstarted_slots"] == 31


def test_time_limit_is_retained_without_patch_salvage_or_evaluation(admitted, tmp_path):
    release, admission, _ = admitted
    def grade(**kwargs): raise AssertionError("non-Submitted episode may not be salvaged")
    summary = cohort.execute_cohort(release, admission, tmp_path / "batch", grade_runner=grade,
        episode_runner=lambda spec, directory: authored_episode(spec, directory, submitted=False, status="operational_time_limit"))
    assert all(c["grade"]["operational_resolution"] == 0 and c["grade_directory"] is None for c in summary["slots"])
    assert summary["descriptive"]["by_schedule"]["SS"]["algorithmic_unknown"] == 8


def test_joint_reservation_cap_retains_unstarted_slots(admitted, monkeypatch, tmp_path):
    release, admission, _ = admitted
    release["limits"]["batch_seconds"] = cohort.SLOT_RESERVATION_SECONDS + 1
    clock = type("Clock", (), {"now": 0, "__call__": lambda self: self.now})()
    inert_sandbox(monkeypatch, admission)
    def run(spec, directory):
        result = authored_episode(spec, directory); clock.now += 2; return result
    summary = cohort.execute_cohort(release, admission, tmp_path / "batch", episode_runner=run, clock=clock)
    assert summary["stop_reason"] == "joint_budget_no_complete_slot_envelope"
    assert summary["descriptive"]["unstarted_slots"] == 31 and len(summary["slots"]) == 32


def test_no_passing_subset_or_repeated_output_directory(admitted, tmp_path):
    release, admission, _ = admitted
    release["limits"]["batch_seconds"] = 1
    out = tmp_path / "batch"
    summary = cohort.execute_cohort(release, admission, out, episode_runner=lambda *a: (_ for _ in ()).throw(AssertionError("no capacity")))
    assert summary["descriptive"]["unstarted_slots"] == 32
    with pytest.raises(ValueError, match="fresh exact preseeded"):
        cohort.execute_cohort(release, admission, out)


def test_summary_r_f_u_and_skip_unknown_are_not_confidence_intervals(admitted, tmp_path):
    release, admission, _ = admitted
    summary = cohort.seed_cohort(release, admission, tmp_path / "batch")
    cells = summary["slots"]
    ss = [c for c in cells if c["schedule"] == "SS"]
    for c, correctness in zip(ss[:3], ["resolved", "unresolved", "unknown"], strict=True):
        c["grade"] = {"graded": True, "resolved": correctness == "resolved",
            "operational_resolution": int(correctness == "resolved"), "algorithmic_correctness": correctness, "assigned_slot_retained": True}
    result = cohort.summarize(cells)
    assert result["by_schedule"]["SS"]["missing_correctness_range"] == [1 / 8, 7 / 8]
    assert result["by_schedule"]["SS"]["algorithmic_unknown"] == 6
    assert result["second_decision_opportunity"]["S_start"]["assigned"] == 16
    assert "no confidence interval" in result["inference"]
    for mutation in ({"operational_resolution": True}, {"operational_resolution": 1}, {"algorithmic_correctness": "unresolved"}):
        changed = copy.deepcopy(cells); changed[-1]["grade"].update(mutation)
        with pytest.raises(ValueError): cohort.summarize(changed)


@pytest.mark.parametrize("change", [
    lambda e: e[2].update(physical_calls=2),
    lambda e: e[2].update(logical_call=25),
    lambda e: e[2].update(model_action="L"),
    lambda e: e[2].update(rendered_sha256="c" * 64),
    lambda e: e[0].update(remaining_episode_wall_seconds="decorative"),
    lambda e: e[0]["workspace_fingerprint"].update(semantic_content_identity=True),
    lambda e: e.insert(1, copy.deepcopy(e[0])),
    lambda e: e.insert(3, copy.deepcopy(e[2])),
    lambda e: e.__setitem__(slice(1, 3), [e[2], e[1]]),
    lambda e: next(x for x in e if x.get("event") == "routing_decision" and x["logical_call"] == 9).update(episode_deadline_monotonic=2801),
])
def test_independent_cost_replay_rejects_malformed_native_accounting(admitted, tmp_path, change):
    release, admission, _ = admitted
    spec = cohort.public_spec(release, admission, cohort.controls.TASK_IDS[0], "SL")
    directory = tmp_path / "episode"; result = authored_episode(spec, directory)
    path = directory / "episode" / "agent" / "events.jsonl"
    events = [json.loads(line) for line in path.read_bytes().splitlines()]; change(events)
    for seq, e in enumerate(events, 1): e["sequence"] = seq
    raw = b"".join(cohort.canonical(e) for e in events); path.write_bytes(raw)
    result["outcome"]["event_log_sha256"] = cohort.sha(raw)
    with pytest.raises(ValueError): cohort.native_measurements(directory, "SL", result["outcome"])


def test_decision_9_eligibility_is_distinct_from_request_9_started(admitted, tmp_path):
    release, admission, _ = admitted
    spec = cohort.public_spec(release, admission, cohort.controls.TASK_IDS[0], "SL")
    directory = tmp_path / "episode"; authored_episode(spec, directory, calls=10)
    path = directory / "episode" / "agent" / "events.jsonl"
    events = [json.loads(line) for line in path.read_bytes().splitlines()]
    cut = next(i for i, e in enumerate(events) if e.get("event") == "routing_decision" and e["logical_call"] == 9)
    path.write_bytes(b"".join(cohort.canonical(e) for e in events[:cut + 1]))
    observed = cohort.native_measurements(directory, "SL", None)
    assert observed["second_decision_eligible"] is True and observed["native_requests"] == 8
    assert observed["physical_attempts_reported"] is None


def test_parent_import_has_no_cuda_or_evaluator_execution_path():
    result = subprocess.run([sys.executable, "-c", "import sys; import experiments.lead_req030.req030aj_cohort; assert 'torch' not in sys.modules"],
                            cwd=cohort.ROOT, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def test_batch_guard_deadline_preserves_all_32_preseeded_assignments(admitted, tmp_path):
    release, admission, _ = admitted; output = tmp_path / "guarded"
    cohort.seed_cohort(release, admission, output)
    rfd, wfd = os.pipe()
    try:
        receipt = cohort.guard_batch(command=[sys.executable, "-c", "import time; time.sleep(60)"],
            owner_fd=rfd, output=output, batch_seconds=.05, storage_bytes=1 << 30)
    finally: os.close(wfd)
    assert receipt["reason"] == "batch_deadline" and receipt["coordinator_reaped"] and receipt["cleanup_verified"]
    assert receipt["all_assigned_slots_retained"]
    assert cohort.read_json(output / "summary.json")["descriptive"]["unstarted_slots"] == 32


def test_batch_guard_owner_eof_before_launch_creates_no_cpu_or_model_worker(admitted, tmp_path):
    release, admission, _ = admitted; output = tmp_path / "guarded"
    cohort.seed_cohort(release, admission, output)
    marker = tmp_path / "must_not_exist"; rfd, wfd = os.pipe(); os.close(wfd)
    receipt = cohort.guard_batch(command=[sys.executable, "-c", "from pathlib import Path; Path(" + repr(str(marker)) + ").touch()"],
        owner_fd=rfd, output=output, batch_seconds=1, storage_bytes=1 << 30)
    assert receipt["reason"] == "owner_eof_before_batch" and receipt["cleanup_verified"] and not marker.exists()
    assert receipt["all_assigned_slots_retained"]


def test_actual_caller_sigkill_still_finishes_independent_batch_guardian(admitted, tmp_path):
    release, admission, _ = admitted; output = tmp_path / "guarded"
    cohort.seed_cohort(release, admission, output)
    ready = tmp_path / "caller_ready"
    guard_code = (
        "import sys; from pathlib import Path; from experiments.lead_req030 import req030aj_cohort as c; "
        "c.guard_batch(command=[sys.executable,'-c','import time; time.sleep(60)'], "
        "owner_fd=int(sys.argv[1]), output=Path(sys.argv[2]),batch_seconds=60, storage_bytes=1073741824)"
    )
    caller_code = (
        "import os,subprocess,sys,time; from pathlib import Path; r,w=os.pipe(); "
        "g=subprocess.Popen([sys.executable,'-c'," + repr(guard_code) + ",str(r)," + repr(str(output)) +
        "],pass_fds=(r,),close_fds=True,start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); "
        "os.close(r); Path(" + repr(str(ready)) + ").write_text(str(g.pid));time.sleep(60)"
    )
    caller = subprocess.Popen([sys.executable, "-c", caller_code], cwd=cohort.ROOT,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    until = time.monotonic() + 10
    try:
        while not ready.exists() and time.monotonic() < until: time.sleep(.01)
        assert ready.exists()
        time.sleep(.1)
        caller.kill(); caller.wait(timeout=3)
        receipt_path = output.parent / (output.name + ".batch_guardian.json")
        while not receipt_path.exists() and time.monotonic() < until: time.sleep(.02)
        assert receipt_path.exists()
        receipt = cohort.read_json(receipt_path)
        assert receipt["reason"] == "owner_eof" and receipt["coordinator_reaped"] and receipt["cleanup_verified"]
        assert receipt["all_assigned_slots_retained"] and caller.returncode == -signal.SIGKILL
    finally:
        if caller.poll() is None: caller.kill(); caller.wait(timeout=3)


def test_batch_guard_kills_descendant_after_direct_cpu_child_exits(admitted, tmp_path):
    release, admission, _ = admitted; output = tmp_path / "guarded"
    cohort.seed_cohort(release, admission, output)
    marker = tmp_path / "descendant_ticks"
    child = "import signal,time; from pathlib import Path; signal.signal(signal.SIGTERM, signal.SIG_IGN); p=Path(" + repr(str(marker)) + ");\nwhile True:\n with p.open('ab') as f:f.write(b'x')\n time.sleep(.01)"
    parent = "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c'," + repr(child) + "]); time.sleep(.1)"
    rfd, wfd = os.pipe()
    try:
        receipt = cohort.guard_batch(command=[sys.executable, "-c", parent], owner_fd=rfd,
            output=output, batch_seconds=3, storage_bytes=1 << 30)
    finally: os.close(wfd)
    assert receipt["reason"] == "exited" and receipt["coordinator_group_kill_sent"]
    before = marker.stat().st_size; time.sleep(.1)
    assert marker.stat().st_size == before


def test_batch_guard_storage_cap_and_unknown_cleanup_abort_future_execution(admitted, tmp_path):
    release, admission, _ = admitted; output = tmp_path / "guarded"
    summary = cohort.seed_cohort(release, admission, output)
    summary["slots"][0].update(status="EPISODE_RUNNING", episode_directory=str(output / "unverified_episode"))
    cohort.sandbox._atomic_json(output / "summary.json", summary)
    rfd, wfd = os.pipe()
    import itertools
    authored_clock = itertools.count()
    # Reduce only authored fixture wait; production cleanup wait is 20 seconds.
    original_sleep = cohort.time.sleep
    class InertTime:
        monotonic = staticmethod(lambda: next(authored_clock))
        sleep = staticmethod(original_sleep)
    monkeypatch = pytest.MonkeyPatch(); monkeypatch.setattr(cohort, "time", InertTime)
    try:
        receipt = cohort.guard_batch(command=[sys.executable, "-c", "import time; time.sleep(60)"],
            owner_fd=rfd, output=output, batch_seconds=100, storage_bytes=1)
    finally: os.close(wfd); monkeypatch.undo()
    assert receipt["reason"] == "storage_limit" and receipt["abort_future_execution"]
    assert receipt["all_assigned_slots_retained"]
