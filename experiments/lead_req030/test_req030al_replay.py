"""Authored deterministic replay mutations; no model or task command executes."""
import copy
import json

import pytest

from experiments.lead_req030 import req030al_replay as replay
from experiments.lead_req030 import req030aj_cohort as joined
from experiments.lead_req030.test_req030aj_cohort import admitted, authored_episode, inert_sandbox, native_events


def assigned():
    return [{**cell, "status": "NOT_ATTEMPTED", "assigned_slot_retained": True,
             "grade": joined.unknown_grade("not_started"), "infrastructure_unknown": False,
             "costs": {"second_decision_eligible": None}}
            for cell in joined.frozen_order("inert-al-replay")]


def known(cell, correctness="resolved"):
    cell.update(status="GRADED", grade={"graded": True, "resolved": correctness == "resolved",
        "operational_resolution": int(correctness == "resolved"), "assigned_slot_retained": True,
        "algorithmic_correctness": correctness}, costs={"second_decision_eligible": True})


def test_all_unknown_assignments_retained_and_no_passing_funding_claim():
    result = replay.summarize_slots(assigned())
    assert result["task_count"] == 8 and result["assigned_slots"] == 32
    assert result["overall"]["missing_correctness_bounds"] == [0, 1]
    assert result["opportunity_S_start"] == {"assigned": 16, "verified_eligible": 0, "verified_not_eligible": 0, "unknown": 16}
    assert result["decision"] == "INCOMPLETE_NO_FUNDING_CONCLUSION"
    assert result["automatic_further_compute_authorized"] is False


@pytest.mark.parametrize("removed", range(32))
def test_each_assigned_slot_omission_rejected(removed):
    cells = assigned(); del cells[removed]
    with pytest.raises(ValueError, match="32 unique"):
        replay.summarize_slots(cells)


def test_duplicate_slot_and_invocation_rejected():
    cells = assigned(); cells[-1] = copy.deepcopy(cells[0])
    with pytest.raises(ValueError): replay.summarize_slots(cells)
    cells = assigned(); cells[-1]["invocation_id"] = cells[0]["invocation_id"]
    with pytest.raises(ValueError, match="invocation"): replay.summarize_slots(cells)


@pytest.mark.parametrize("mutation", [
    {"assigned_slot_retained": False}, {"grade": {"graded": True, "resolved": True,
     "operational_resolution": True, "algorithmic_correctness": "resolved", "assigned_slot_retained": True}},
    {"costs": {"second_decision_eligible": "yes"}}, {"infrastructure_unknown": None},
])
def test_invalid_assigned_state_rejected(mutation):
    cells = assigned(); cells[0].update(mutation)
    with pytest.raises(ValueError): replay.summarize_slots(cells)


def test_s_start_denominator_and_floor_are_not_aggregate_opportunity():
    cells = assigned()
    for cell in cells: known(cell, "unresolved")
    for schedule in ("SS", "LL"):
        selected = [c for c in cells if c["schedule"] == schedule]
        for cell in selected[:2]: known(cell)
    for cell in cells:
        if cell["schedule"][0] == "S": cell["costs"]["second_decision_eligible"] = False
    result = replay.summarize_slots(cells)
    assert result["opportunity_all"]["verified_eligible"] == 16
    assert result["opportunity_S_start"]["verified_eligible"] == 0
    assert result["decision"] == "DO_NOT_EXPAND_THIS_CONFIGURATION"
    for cell in [c for c in cells if c["schedule"][0] == "S"][:8]:
        cell["costs"]["second_decision_eligible"] = True
    result = replay.summarize_slots(cells)
    assert result["decision"] == "PASS_DISCRETIONARY_FEASIBILITY_FLOORS"
    assert "not an H/P" in result["inference"]


def test_unknown_and_skipped_correctness_do_not_become_verified_success():
    cells = assigned()
    for cell in cells: known(cell, "unknown")
    known(cells[0]); known(cells[1], "unresolved")
    result = replay.summarize_slots(cells)
    assert result["overall"]["verified_resolved"] == 1
    assert result["overall"]["missing_correctness_bounds"] == [1 / 32, 31 / 32]
    assert result["decision"] == "DO_NOT_EXPAND_THIS_CONFIGURATION"


class InertTokenizer:
    eos_token_id = 0

    def apply_chat_template(self, messages, *, tokenize, add_generation_prompt):
        assert tokenize is False and add_generation_prompt is True
        return json.dumps(messages, ensure_ascii=False, separators=(",", ":")) + "<assistant>"

    def __call__(self, text, *, add_special_tokens):
        assert add_special_tokens is False
        return {"input_ids": [ord(char) for char in text]}

    def decode(self, ids, *, skip_special_tokens):
        assert skip_special_tokens is False
        return "".join("<EOS>" if i == 0 else chr(i) for i in ids)


def native_fixture(tmp_path, public_projection=None):
    tokenizer = InertTokenizer()
    messages = [{"role": "system", "content": "inert system"}, {"role": "user", "content": "inert public issue"}]
    if public_projection is not None:
        messages = [{"role": "system", "content": joined.sandbox.SYSTEM_TEMPLATE}, {"role": "user",
            "content": joined.sandbox.INSTANCE_TEMPLATE.replace("{{task}}", public_projection["problem_statement"])}]
    rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    binding = {"messages_sha256": replay.sha(json.dumps(messages, ensure_ascii=False, separators=(",", ":")).encode()),
               "rendered_sha256": replay.sha(rendered.encode()), "input_ids": [ord(c) for c in rendered],
               "input_tokens": len(rendered)}
    events = native_events("SS", calls=1)
    for event in events:
        if event["event"] == "routing_decision":
            for native in event["both_action_reservations"].values():
                native.update(binding, reserved_total_tokens=len(rendered) + 1536,
                              remaining_input_token_capacity=14848 - len(rendered))
        elif event["event"] == "request": event.update(binding, rendered=rendered)
        else: event.update({k: binding[k] for k in ("messages_sha256", "rendered_sha256", "input_tokens")},
                           output_ids=[ord("x"), 0], output_tokens=2)
    response = events[-1]
    message = {"role": "assistant", "content": "x<EOS>", "extra": {"native_binding": copy.deepcopy(response)}}
    messages.append(message)
    trajectory = replay.canonical({"messages": messages})
    directory = tmp_path / "native"; agent = directory / "episode" / "agent"; agent.mkdir(parents=True)
    ledger = b"".join(replay.canonical(e) for e in events)
    (agent / "events.jsonl").write_bytes(ledger); (agent / "trajectory.json").write_bytes(trajectory)
    outcome = {"physical_calls": 1, "event_log_sha256": replay.sha(ledger), "trajectory_sha256": replay.sha(trajectory),
               "peak_allocated_bytes": 1, "peak_reserved_bytes": 2}
    return directory, tokenizer, outcome


def test_all_native_input_output_history_bindings_independently_replay(tmp_path):
    directory, tokenizer, outcome = native_fixture(tmp_path)
    result = replay.replay_native(episode_directory=directory, schedule="SS", outcome=outcome, tokenizer=tokenizer)
    assert result["native_requests"] == 1 and result["returned_calls_replayed"] == 1
    assert result["tokenizer_replay_verified"] and result["trajectory_prefix_replay_verified"]
    assert result["decoded_output_replay_verified"]
    no_tokenizer = replay.replay_native(episode_directory=directory, schedule="SS", outcome=outcome)
    assert no_tokenizer["tokenizer_replay_verified"] is False


def test_exact_public_initial_context_required_when_projection_supplied(tmp_path):
    public = {"instance_id": replay.TASK_IDS[0], "repo": "django/django", "base_commit": "b" * 40,
              "problem_statement": "Public authored inert issue with literal {{task}} text"}
    directory, tokenizer, outcome = native_fixture(tmp_path, public)
    result = replay.replay_native(episode_directory=directory, schedule="SS", outcome=outcome,
                                 tokenizer=tokenizer, public_projection=public)
    assert result["public_initial_context_verified"] is True
    changed = {**public, "problem_statement": public["problem_statement"] + " hidden evaluator hint"}
    with pytest.raises(ValueError, match="public-only"):
        replay.replay_native(episode_directory=directory, schedule="SS", outcome=outcome,
                             tokenizer=tokenizer, public_projection=changed)
    changed = {**public, "reference_patch": "forbidden evaluator input"}
    with pytest.raises(ValueError, match="four-field"):
        replay.replay_native(episode_directory=directory, schedule="SS", outcome=outcome,
                             tokenizer=tokenizer, public_projection=changed)


@pytest.mark.parametrize("mutation, expected", [
    (lambda t: t["messages"][0].update(content="changed system"), "prefix"),
    (lambda t: t["messages"][-1].update(content="changed decode"), "decode"),
    (lambda t: t["messages"][-1]["extra"]["native_binding"].update(revision="c" * 40), "binding"),
    (lambda t: t["messages"].pop(), "omits"),
])
def test_native_trajectory_mutations_rejected(tmp_path, mutation, expected):
    directory, tokenizer, outcome = native_fixture(tmp_path)
    path = directory / "episode" / "agent" / "trajectory.json"
    trajectory = json.loads(path.read_bytes()); mutation(trajectory)
    raw = replay.canonical(trajectory); path.write_bytes(raw); outcome["trajectory_sha256"] = replay.sha(raw)
    with pytest.raises(ValueError, match=expected):
        replay.replay_native(episode_directory=directory, schedule="SS", outcome=outcome, tokenizer=tokenizer)


def test_candidate_raw_and_prospective_slot_replay(admitted, monkeypatch, tmp_path):
    release, admission, _ = admitted
    inert_sandbox(monkeypatch, admission)
    slot = release["order"][0]
    item = admission["tasks"][slot["task_id"]]
    original = joined.sandbox.run_supervised
    def with_stages(*args, **kwargs):
        raw, receipt = original(*args, **kwargs)
        raw += environment_raw(slot["task_id"])
        receipt["retained_bytes"] = len(raw)
        kwargs["output_path"].write_bytes(raw)
        kwargs["receipt_path"].write_bytes(joined.canonical(receipt))
        return raw, receipt
    monkeypatch.setattr(joined.sandbox, "run_supervised", with_stages)
    episode = tmp_path / "episode"; grade = tmp_path / "grade"
    authored_episode(joined.public_spec(release, admission, slot["task_id"], slot["schedule"]), episode)
    generated = joined.execute_grade(item=item, slot=slot, episode_directory=episode, directory=grade,
                                    release_sha256=admission["release_sha256"], apptainer=str(admission["apptainer"]))
    result = replay.replay_candidate_artifacts(task=item["task"], evaluator_bundle=item["evaluator_raw"],
        slot=slot, episode_directory=episode, grade_directory=grade, release_sha256=admission["release_sha256"])
    assert result["grade"] == generated["grade"] and result["grade"]["resolved"]
    assert result["prepatch_runtime_identity_verified"] is False
    baseline_identity = result["environment"]["runtime_sha256"]
    qualified = replay.replay_candidate_artifacts(task=item["task"], evaluator_bundle=item["evaluator_raw"],
        slot=slot, episode_directory=episode, grade_directory=grade, release_sha256=admission["release_sha256"],
        expected_prepatch_runtime_sha256=baseline_identity)
    assert qualified["prepatch_runtime_identity_verified"] is True
    mismatch = replay.replay_candidate_artifacts(task=item["task"], evaluator_bundle=item["evaluator_raw"],
        slot=slot, episode_directory=episode, grade_directory=grade, release_sha256=admission["release_sha256"],
        expected_prepatch_runtime_sha256="e" * 64)
    assert not mismatch["grade"]["graded"] and mismatch["grade"]["algorithmic_correctness"] == "unknown"
    assert result["official_docker_execution_verified"] is False
    changed = {**slot, "invocation_id": slot["invocation_id"] + ":changed"}
    with pytest.raises(ValueError, match="invocation"):
        replay.replay_candidate_artifacts(task=item["task"], evaluator_bundle=item["evaluator_raw"],
            slot=changed, episode_directory=episode, grade_directory=grade, release_sha256=admission["release_sha256"])
    out = grade / "candidate.out"; out.write_bytes(out.read_bytes() + b"tampered trailing output\n")
    result = replay.replay_candidate_artifacts(task=item["task"], evaluator_bundle=item["evaluator_raw"],
        slot=slot, episode_directory=episode, grade_directory=grade, release_sha256=admission["release_sha256"])
    assert result["grade"]["resolved"] is False and result["grade"]["algorithmic_correctness"] == "unknown"


def environment_raw(task_id):
    runtime = {"python": "3.9.20 inert", "executable": "/opt/miniconda3/envs/testbed/bin/python",
        "modules": [{"module": m, "file": "/testbed/" + m.replace(".", "/") + ".py"}
                    for m in replay.TASK_MODULES[task_id]],
        "localhost": ["127.0.0.1", "::1"], "interfaces": ["lo"], "routes": [],
        "packages": [{"name": "inert", "version": "1"}]}
    lines = ["DTR_AL_RUNTIME\t" + json.dumps(runtime)]
    lines += ["DTR_AL_STAGE\t" + stage + "\t0" for stage in replay.ENVIRONMENT_STAGES]
    return ("\n".join(lines) + "\n").encode()


@pytest.mark.parametrize("task_id", replay.TASK_IDS)
def test_complete_environment_stage_and_runtime_replay(task_id):
    result = replay.replay_environment_stages(raw=environment_raw(task_id),
        supervisor={"reason": "exited", "error": None, "returncode": 0, "retained_bytes": len(environment_raw(task_id))}, task_id=task_id)
    assert result["accepted"] and len(result["stages"]) == 7


@pytest.mark.parametrize("stage", replay.ENVIRONMENT_STAGES)
def test_environment_stage_omission_and_duplication_rejected(stage):
    tid = replay.TASK_IDS[0]; raw = environment_raw(tid)
    marker = ("DTR_AL_STAGE\t" + stage + "\t0\n").encode()
    for changed in (raw.replace(marker, b""), raw + marker):
        result = replay.replay_environment_stages(raw=changed,
            supervisor={"reason": "exited", "error": None, "returncode": 0, "retained_bytes": len(changed)}, task_id=tid)
        assert result["accepted"] is False


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(localhost=["192.0.2.1"]),
    lambda r: r["modules"][0].update(file="/opt/wrong_module.py"),
    lambda r: r.update(executable="/usr/bin/python"),
    lambda r: r.update(packages=[]),
    lambda r: r.update(interfaces=["lo", "eth0"]),
    lambda r: r.update(routes=["external route"]),
])
def test_runtime_mismatch_rejected(mutation):
    tid = replay.TASK_IDS[0]; lines = environment_raw(tid).decode().splitlines()
    runtime = json.loads(lines[0].split("\t", 1)[1]); mutation(runtime)
    lines[0] = "DTR_AL_RUNTIME\t" + json.dumps(runtime)
    raw = ("\n".join(lines) + "\n").encode()
    result = replay.replay_environment_stages(raw=raw,
        supervisor={"reason": "exited", "error": None, "returncode": 0, "retained_bytes": len(raw)}, task_id=tid)
    assert result["accepted"] is False


def test_environment_failure_cannot_be_promoted_by_shell_exit_zero():
    tid = replay.TASK_IDS[0]; raw = environment_raw(tid)
    for changed, rc in ((raw.replace(b"candidate\t0", b"candidate\t87"), 0),
                        (raw + b"DTR_SETUP_FAILURE\n", 0), (raw, 1)):
        assert not replay.replay_environment_stages(raw=changed,
            supervisor={"reason": "exited", "error": None, "returncode": rc, "retained_bytes": len(changed)}, task_id=tid)["accepted"]


def control_replays():
    return [{"task_id": tid, "mode": mode, "accepted": True,
             "environment": {"runtime_sha256": str(index)}}
            for index, tid in enumerate(replay.TASK_IDS) for mode in ("baseline", "reference")]


def test_control_all_arm_acceptance_and_stable_runtime():
    assert replay.summarize_control_replays(control_replays())["all_controls_accepted"] is True
    records = control_replays(); records[-1]["accepted"] = False
    assert replay.summarize_control_replays(records)["model_admission_environment_gate"] == "HOLD_ALL_MODELS"
    records = control_replays(); records[-1]["environment"]["runtime_sha256"] = "changed"
    assert not replay.summarize_control_replays(records)["all_controls_accepted"]


@pytest.mark.parametrize("omission", range(16))
def test_each_control_arm_omission_rejects_full_admission(omission):
    records = control_replays(); del records[omission]
    with pytest.raises(ValueError, match="sixteen"):
        replay.summarize_control_replays(records)
