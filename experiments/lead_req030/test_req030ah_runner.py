"""Inert production-runner checks; these do not qualify real container isolation.

The fake executable only recognizes fixed authored fixtures. It never executes
the command string it receives. The real pinned AG supervisor, receipt parser,
owner-pipe cleanup, event log and runner lifecycle are exercised together.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.lead_req030 import req030ag_seaborn_apptainer_runner as runner


SUPERVISOR = Path(__file__).with_name("req030ag_bounded_supervisor.py")
BASE = "a" * 40
TREE = "b" * 40
HEAD = "c" * 40
NORMAL = "DTR_FIXED_AUTHOR_NORMAL"
EXIT7 = "DTR_FIXED_AUTHOR_EXIT7"
SLOW = "DTR_FIXED_AUTHOR_SLOW"
OVERFLOW = "DTR_FIXED_AUTHOR_OVERFLOW"
PREFLIGHT = f"DTR_PREFLIGHT\t{HEAD}\t{BASE}\t{TREE}\t{TREE}\t134217728\t67108864\n"


def fake_apptainer(path: Path) -> Path:
    source = f'''#!{sys.executable}
import os, sys, time
args = sys.argv[1:]
if args == ["--version"]:
    print("apptainer INERT_AUTHOR_FIXTURE"); raise SystemExit(0)
assert args[:5] == ["exec", "--containall", "--cleanenv", "--no-home", "--no-mount"]
assert args[5:10] == ["hostfs,bind-paths", "--net", "--network", "none", "--pwd"]
assert args[10] == "/testbed" and args[-3:-1] == ["/bin/bash", "-lc"]
command = args[-1]
if command == {NORMAL!r}:
    print("INERT_TOOL_OK")
elif command == {EXIT7!r}:
    print("INERT_TOOL_FAILURE"); raise SystemExit(7)
elif command == {SLOW!r}:
    print(os.getpid(), flush=True); time.sleep(30)
elif command == {OVERFLOW!r}:
    os.write(1, b"x" * 65536); time.sleep(30)
elif command.startswith("set -euo pipefail\\n") and "DTR_PREFLIGHT" in command:
    # Emit a fixed receipt, never run a preflight shell on the host.
    print({PREFLIGHT!r}, end="")
else:
    raise SystemExit("unapproved inert fixture")
'''
    path.write_text(source)
    path.chmod(0o700)
    return path


@pytest.fixture
def assets(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    readlink = os.readlink
    monkeypatch.setattr(runner.os, "readlink", lambda path, *a, **kw:
        "net:[inert-host]" if str(path) == "/proc/self/ns/net" else readlink(path, *a, **kw))
    apptainer = fake_apptainer(tmp_path / "apptainer")
    image = tmp_path / "task.sif"; image.write_bytes(b"inert task image")
    workspace = tmp_path / "workspace.img"; workspace.write_bytes(b"inert workspace")
    return {"apptainer": str(apptainer), "image": image, "image_sha256": runner.sha256_file(image),
            "workspace_image": workspace, "workspace_sha256": runner.sha256_file(workspace),
            "supervisor": SUPERVISOR, "supervisor_sha256": runner.sha256_file(SUPERVISOR)}


@pytest.fixture
def environment(tmp_path, assets):
    directory = tmp_path / "receipts"; directory.mkdir(mode=0o700)
    journal = runner.DurableEventLog(directory)
    env = runner.ApptainerToolEnvironment(**assets, run_dir=directory, event_log=journal,
        tool_timeout_seconds=3, output_cap_bytes=1024, action_cap_bytes=8192,
        expected_base_commit=BASE)
    try:
        yield env
    finally:
        env.close()
        journal.close()


def test_real_supervisor_and_runner_accept_explicit_no_error(environment):
    env = environment
    result = env.preflight()
    assert result["source_tree"] == result["base_tree"] == TREE
    normal = env.execute({"command": NORMAL})
    failed_tool = env.execute({"command": EXIT7})
    assert normal["output"] == "INERT_TOOL_OK\n"
    assert normal["returncode"] == 0 and normal["exception_info"] == ""
    assert failed_tool["returncode"] == 7 and failed_tool["exception_info"] == ""
    receipt = json.loads((env.run_dir / "action-0001.json").read_text())
    assert receipt["error"] is None and receipt["reason"] == "exited"
    assert env.action_count == 2
    assert (env.run_dir / "action-0001.out").stat().st_mode & 0o777 == 0o600
    assert (env.run_dir / "action-0001.json").stat().st_mode & 0o777 == 0o600


def test_real_supervisor_bounds_timeout_and_output(environment):
    env = environment
    env.preflight()
    timed = env.execute({"command": SLOW}, timeout=0.2)
    assert timed["exception_info"] == "deadline"
    overflow = env.execute({"command": OVERFLOW})
    assert overflow["exception_info"] == "output_limit"
    assert len(overflow["output"]) == env.output_cap_bytes


def test_execution_requires_preflight_and_lifetime(environment):
    env = environment
    with pytest.raises(RuntimeError, match="before isolated workspace preflight"):
        env.execute({"command": NORMAL})
    env.preflight()
    with pytest.raises(RuntimeError, match="single-use"):
        env.preflight()
    env.close()
    with pytest.raises(RuntimeError, match="closed"):
        env.execute({"command": NORMAL})


def test_caller_interruption_closes_owner_pipe_and_reaps_real_command(environment, monkeypatch):
    env = environment
    env.preflight()
    original_popen = subprocess.Popen
    output = env.run_dir / "action-0001.out"

    class InterruptedWait:
        def __init__(self, process):
            self.process = process
            self.interrupted = False

        def wait(self, timeout):
            if not self.interrupted:
                deadline = time.monotonic() + 3
                while not output.exists() or not output.stat().st_size:
                    if time.monotonic() >= deadline:
                        raise AssertionError("inert command did not start")
                    time.sleep(0.01)
                self.interrupted = True
                raise KeyboardInterrupt("fixed caller-cancellation fixture")
            return self.process.wait(timeout=timeout)

        def __getattr__(self, name):
            return getattr(self.process, name)

    monkeypatch.setattr(runner.subprocess, "Popen", lambda *a, **kw:
                        InterruptedWait(original_popen(*a, **kw)))
    with pytest.raises(KeyboardInterrupt, match="caller-cancellation"):
        env.execute({"command": SLOW})
    record = json.loads((env.run_dir / "action-0001.json").read_text())
    assert record["reason"] == "owner_eof" and record["error"] is None
    with pytest.raises(ProcessLookupError):
        os.kill(record["pid"], 0)


def valid_record():
    return {"reason": "exited", "pid": 123, "returncode": 0,
            "retained_bytes": 3, "elapsed": 0.01, "error": None}


@pytest.mark.parametrize("updates", [
    {"unknown": None}, {"error": {}}, {"error": "failure"}, {"reason": "owner_eof"},
    {"reason": "owner_absent_before_start"}, {"reason": "internal_error"},
    {"reason": "unrecognized"}, {"pid": None}, {"pid": 0}, {"pid": True},
    {"returncode": None}, {"returncode": False}, {"retained_bytes": -1},
    {"retained_bytes": True}, {"retained_bytes": 33}, {"elapsed": float("nan")},
    {"elapsed": float("inf")}, {"elapsed": -1}, {"elapsed": False},
    {"reason": "output_limit"},
])
def test_receipt_schema_and_unknown_or_inconsistent_states_fail_closed(updates):
    record = {**valid_record(), **updates}
    with pytest.raises(ValueError):
        runner._supervisor_record(json.dumps(record).encode(), cap=32)


def test_receipt_requires_error_field_and_rejects_duplicate_keys():
    record = valid_record(); del record["error"]
    with pytest.raises(ValueError, match="schema"):
        runner._supervisor_record(json.dumps(record).encode(), cap=32)
    duplicated = json.dumps(valid_record())[:-1] + ', "error": null}'
    with pytest.raises(ValueError, match="duplicate"):
        runner._supervisor_record(duplicated.encode(), cap=32)


@pytest.mark.parametrize("kind", ["symlink", "public", "oversized", "missing"])
def test_private_receipt_reader_rejects_unsafe_or_missing_artifacts(tmp_path, kind):
    artifact = tmp_path / "receipt"
    if kind != "missing":
        artifact.write_bytes(b"private")
        artifact.chmod(0o600)
    if kind == "symlink":
        link = tmp_path / "link"; link.symlink_to(artifact); artifact = link
    if kind == "public":
        artifact.chmod(0o644)
    with pytest.raises((OSError, ValueError)):
        runner._read_private_artifact(artifact, 1 if kind == "oversized" else 32)


@pytest.mark.parametrize("marker", [
    PREFLIGHT.replace(TREE, "d" * 40, 1),  # An image setup child with a different tree.
    PREFLIGHT.replace(HEAD, "z" * 40),
    PREFLIGHT.replace(BASE, "d" * 40),
    PREFLIGHT.replace("134217728", "1"),
    PREFLIGHT + PREFLIGHT,
])
def test_preflight_retains_exact_base_tree_policy(environment, monkeypatch, marker):
    env = environment
    seen = []

    def fixed_preflight(command, **kwargs):
        seen.append(command)
        return {"returncode": 0, "exception_info": ""}, marker.encode()

    monkeypatch.setattr(env, "_bounded_command", fixed_preflight)
    with pytest.raises(ValueError):
        env.preflight()
    assert env.preflight_result is None
    with pytest.raises(RuntimeError, match="single-use"):
        env.preflight()
    with pytest.raises(RuntimeError, match="before isolated workspace preflight"):
        env.execute({"command": NORMAL})
    assert 'test "$head_tree" = "$base_tree"' in seen[0]


def test_full_inert_runner_uses_production_supervisor_and_seals_trajectory(tmp_path, assets):
    """Tests the join only: the fake emits authored preflight evidence, not isolation."""
    task = SimpleNamespace(base_commit=BASE, instance_id="inert__fixture-1",
                           problem_statement="Fixed author fixture", source_sha256="d" * 64)
    model_config = {"action_regex": "fixed", "observation_template": "fixed",
                    "format_error_template": "fixed"}

    class InertModel:
        n_calls = 0
        def query(self, *a, **kw):
            raise AssertionError("the inert fixture must not request model inference")
        def format_message(self, *a, **kw): return {}
        def format_observation_messages(self, *a, **kw): return []
        def get_template_vars(self, *a, **kw): return {}
        def serialize(self): return {"fixture": "no-model"}

    class InertAgent:
        def __init__(self, model, env, **config):
            self.model, self.env = model, env
        def run(self, task):
            self.observation = self.env.execute({"command": NORMAL})
            return {"exit_status": "FixtureComplete", "submission": ""}
        def serialize(self):
            return {"observation": self.observation, "environment": self.env.serialize()}

    result = runner.run_pinned_agent(agent_class=InertAgent,
        model_factory=lambda *_: InertModel(), public_projection=b"fixed-public-fixture",
        run_directory=tmp_path / "joined", **assets, release_id="inert-author-fixture",
        release_sha256="e" * 64, step_limit=1, wall_time_limit_seconds=5,
        model_context_limit=128, model_max_new_tokens=16, tool_timeout_seconds=3,
        output_cap_bytes=1024, action_cap_bytes=8192,
        public_task_parser=lambda _: task,
        agent_preparer=lambda *a, **kw: SimpleNamespace(task=task, model_config=model_config,
            agent_config={}, template_source_sha256="f" * 64))
    directory = Path(result["run_directory"])
    events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert {"workspace_preflight_accepted", "action_finish", "workspace_sealed", "agent_run_finish"} <= {
        event["event"] for event in events}
    assert events[-1]["physical_model_calls"] == 0
    assert result["trajectory_sha256"] == runner.sha256_file(directory / "trajectory.json")
