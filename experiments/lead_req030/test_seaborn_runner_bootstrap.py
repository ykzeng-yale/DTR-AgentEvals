"""Regression test for clean-process ordering of pinned runner dependencies."""

from __future__ import annotations

import os
import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class RunnerBootstrapTests(unittest.TestCase):
    def test_release_manifest_binds_payload_workspace_and_batch(self) -> None:
        manifest_path = Path(os.environ.get(
            "DTR_RELEASE_MANIFEST",
            ROOT / "experiments/lead_req030/seaborn_runner_qualification_d_release.json",
        ))
        batch_path = Path(os.environ.get(
            "DTR_BATCH_SCRIPT",
            ROOT / "experiments/lead_req030/seaborn_runner_qualification_d.sbatch",
        ))
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
        batch = batch_path.read_text()
        self.assertIn(hashlib.sha256(manifest_bytes).hexdigest(), batch)
        workspace_sha = manifest["task"]["workspace_seed_sha256"]
        self.assertIn(f"export DTR_WORKSPACE_SHA256={workspace_sha}", batch)
        self.assertEqual(manifest["release_id"], "req030-seaborn-runner-qualification-20260929-d")
        self.assertIn('release_id=manifest["release_id"]', (ROOT / "experiments/lead_req030/seaborn_runner_qualification.py").read_text())
        for entry in manifest["source_files"]:
            relative = Path(entry["path"]).relative_to("payload")
            data = (ROOT / relative).read_bytes()
            self.assertEqual(len(data), entry["bytes"], entry["path"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"], entry["path"])

    def test_clean_process_bootstraps_action_parser_before_native_adapter(self) -> None:
        script = """
import sys
assert not any(name == 'minisweagent' or name.startswith('minisweagent.') for name in sys.modules)
from experiments.lead_req030.seaborn_runner_qualification import load_runner_components
agent, adapter, runner, sha256_file = load_runner_components()
assert agent.__name__ == 'DefaultAgent'
assert adapter.__name__ == 'NativeHFTextAdapter'
assert callable(runner) and callable(sha256_file)
assert 'minisweagent.models.utils.actions_text' in sys.modules
print('runner-bootstrap-ok')
"""
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("runner-bootstrap-ok", result.stdout)

    def test_pinned_agent_trajectory_serialization_accepts_json_mode(self) -> None:
        script = """
import json
import sys
import tempfile
import types
from pathlib import Path
from experiments.lead_req030.seaborn_runner_qualification import load_runner_components
agent_class, _, _, _ = load_runner_components()
model = types.SimpleNamespace(serialize=lambda: {}, get_template_vars=lambda: {})
environment = types.SimpleNamespace(serialize=lambda: {}, get_template_vars=lambda: {})
agent = agent_class(
    model, environment,
    system_template="system", instance_template="instance",
)
with tempfile.TemporaryDirectory() as directory:
    output = Path(directory) / 'trajectory.json'
    serialized = agent.save(output)
    saved = json.loads(output.read_text())
assert serialized['info']['config']['agent']['system_template'] == 'system'
assert serialized['info']['config']['agent']['output_path'] is None
assert saved['info']['config']['agent']['system_template'] == 'system'
print('runner-trajectory-serialization-ok')
"""
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("runner-trajectory-serialization-ok", result.stdout)

    def test_terminal_marker_only_produces_empty_submission(self) -> None:
        script = r"""
import json, subprocess, tempfile
from pathlib import Path
from experiments.lead_req030.seaborn_runner_qualification import load_runner_components
load_runner_components()  # Isolate pinned upstream module bootstrap in this subprocess.
from minisweagent.exceptions import Submitted
from experiments.lead_req030.seaborn_apptainer_runner import ApptainerToolEnvironment, DurableEventLog, TERMINAL_MARKER
command = f"echo {TERMINAL_MARKER}"
output = subprocess.run(["bash", "-lc", command], capture_output=True, check=True, timeout=5).stdout
assert output == f"{TERMINAL_MARKER}\n".encode()
with tempfile.TemporaryDirectory() as temporary:
    run_dir = Path(temporary)
    events = DurableEventLog(run_dir)
    environment = object.__new__(ApptainerToolEnvironment)
    environment.preflight_result = {"accepted": True}
    environment.action_count = 2
    environment.tool_timeout_seconds = 60
    environment.event_log = events
    environment._bounded_command = lambda *_args, **_kwargs: (
        {"returncode": 0, "extra": {"supervisor": {"reason": "exited"}}}, output
    )
    try:
        try:
            environment.execute({"command": command})
        except Submitted as exc:
            message = exc.messages[0]
        else:
            raise AssertionError("terminal marker did not raise Submitted")
    finally:
        events.close()
    assert message["content"] == message["extra"]["submission"] == ""
    record = json.loads((run_dir / "events.jsonl").read_text())
    assert record["event"] == "terminal_submission"
    assert record["submission_bytes"] == 0
    assert record["submission_sha256"] == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
print("terminal-empty-submission-ok")
"""
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        result = subprocess.run(
            [sys.executable, "-c", script], cwd=ROOT, env=env,
            capture_output=True, text=True, timeout=30, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("terminal-empty-submission-ok", result.stdout)


if __name__ == "__main__":
    unittest.main()
