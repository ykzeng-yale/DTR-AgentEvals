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
            ROOT / "experiments/lead_req030/seaborn_runner_qualification_b_release.json",
        ))
        batch_path = Path(os.environ.get(
            "DTR_BATCH_SCRIPT",
            ROOT / "experiments/lead_req030/seaborn_runner_qualification_b.sbatch",
        ))
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
        batch = batch_path.read_text()
        self.assertIn(hashlib.sha256(manifest_bytes).hexdigest(), batch)
        workspace_sha = manifest["task"]["workspace_seed_sha256"]
        self.assertIn(f"export DTR_WORKSPACE_SHA256={workspace_sha}", batch)
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


if __name__ == "__main__":
    unittest.main()
