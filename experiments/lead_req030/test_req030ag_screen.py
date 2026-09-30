from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
import sys
import tarfile
import types
from enum import Enum
from pathlib import Path

import pytest

from experiments.lead_req030 import req030ag_screen as screen

ROOT = Path(__file__).resolve().parents[2]
PARSER = ROOT / "work/upstream/SWE-bench-f7bbbb2ccdf479001d6467c9e34af59e44a840f9/swebench/harness/log_parsers/python.py"


def pinned_parser_functions():
    source = PARSER.read_text()
    assert hashlib.sha256(source.encode()).hexdigest() == screen.EXPECTED_SWEBENCH_PARSER_SHA256
    tree = ast.parse(source)
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name in set(screen.PARSER_BY_REPO.values())]
    namespace = {"re": re, "TestStatus": Enum("TestStatus", {x: x for x in screen.STATUS_WORDS}), "TestSpec": object}
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(PARSER), "exec"), namespace)
    return namespace


@pytest.mark.parametrize("name,log", [
    ("parse_log_pytest", "FAILED tests/a.py::test_bad - assertion\nPASSED tests/a.py::test_good"),
    ("parse_log_pytest_options", "FAILED tests/a.py::test_opt[/tmp/data.csv] - bad\nPASSED tests/a.py::test_ok"),
    ("parse_log_pytest_v2", "\x1b[31mFAILED tests/a.py::test_bad - bad\n tests/a.py::test_old PASSED"),
    ("parse_log_sympy", "______ sympy/core/tests/test_a.py:test_bad ______\ntest_good ok\ntest_err E"),
])
def test_parser_matches_pinned_swebench_source(name, log):
    expected = pinned_parser_functions()[name](log, None)
    assert screen.parse_pytest_statuses(log, name) == expected


def test_controls_require_all_markers_and_all_declared_statuses():
    ev = {"fail_to_pass": ["tests/a.py::test_fix"], "pass_to_pass": ["tests/a.py::test_keep"]}
    sup = {"reason": "exited", "returncode": 1}
    good = (b"DTR_TEST_START\n>>>>> Start Test Output\nFAILED tests/a.py::test_fix - bad\n"
            b"PASSED tests/a.py::test_keep\nPASSED tests/a.py::test_extra\n>>>>> End Test Output\nDTR_TEST_END\n")
    result = screen.control_result(good, sup, ev, "baseline", "parse_log_pytest")
    assert result["valid_process"] and result["accepted"]
    for mutated in (good.replace(b"DTR_TEST_END", b""), good + good,
                    good.replace(b"FAILED tests/a.py::test_fix", b"ERROR tests/a.py::test_fix"),
                    good.replace(b"tests/a.py::test_keep", b"tests/a.py::test_missing")):
        result = screen.control_result(mutated, sup, ev, "baseline", "parse_log_pytest")
        assert not result["accepted"]
    result = screen.control_result(good, {**sup, "returncode": 2}, ev, "baseline", "parse_log_pytest")
    assert not result["valid_process"]


@pytest.mark.parametrize("mode,required_marker", [
    ("baseline", "DTR_SETUP_FAILURE"), ("reference", "DTR_SETUP_FAILURE"), ("agent", "DTR_AGENT_PATCH_REJECTED")
])
def test_control_wrapper_is_fail_closed_and_bash_valid(tmp_path, mode, required_marker):
    path = tmp_path / "wrapper.sh"
    screen.evaluation_wrapper(path, mode=mode, base_commit="a" * 40)
    text = path.read_text()
    assert required_marker in text
    assert "DTR_ISOLATION_FAILURE" in text
    subprocess.run(["bash", "-n", str(path)], check=True)


def test_extract_strips_testbed_root_and_rejects_escape(tmp_path):
    archive = tmp_path / "source.tar"
    with tarfile.open(archive, "w") as tar:
        content = b"hello"
        import io
        info = tarfile.TarInfo("testbed/pkg/file.txt")
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))
    dest = tmp_path / "extract"
    screen._safe_extract_source_tar(archive, dest)
    assert (dest / "pkg/file.txt").read_bytes() == b"hello"
    assert not (dest / "testbed").exists()

    bad = tmp_path / "bad.tar"
    with tarfile.open(bad, "w") as tar:
        info = tarfile.TarInfo("testbed/../../outside")
        info.size = 0
        tar.addfile(info)
    with pytest.raises(ValueError, match="unsafe"):
        screen._safe_extract_source_tar(bad, tmp_path / "bad-extract")


def test_harvest_script_includes_uncommitted_and_untracked_patch(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    def git(*args):
        return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
    git("init", "-q")
    git("config", "user.name", "test")
    git("config", "user.email", "test@example.invalid")
    (repo / "tracked.txt").write_text("before\n")
    git("add", "tracked.txt")
    git("commit", "-qm", "base")
    base = git("rev-parse", "HEAD")
    (repo / "tracked.txt").write_text("after\n")
    (repo / "new.txt").write_text("new\n")
    script = tmp_path / "harvest.sh"
    script.write_text(screen.patch_harvest_script(base).replace("cd /testbed", f"cd {repo}"))
    patch = subprocess.run(["bash", str(script)], cwd=repo, check=True, capture_output=True).stdout
    assert b"before" in patch and b"after" in patch and b"new.txt" in patch and b"new" in patch


def test_balanced_pair_order_is_four_each():
    tasks = [{"instance_id": f"repo__issue-{i}"} for i in range(8)]
    ordered = sorted(tasks, key=lambda t: (hashlib.sha256(
        b"DTR-REQ030AG-balanced-order-v1" + t["instance_id"].encode()).digest(), t["instance_id"]))
    first = ["7B"] * 4 + ["14B"] * 4
    mapping = {t["instance_id"]: m for t, m in zip(ordered, first, strict=True)}
    assert list(mapping.values()).count("7B") == list(mapping.values()).count("14B") == 4


def test_disk_floor_records_capacity(tmp_path):
    report = screen.require_disk_floor(tmp_path, 1)
    assert report["free_bytes"] >= 1 and report["required_bytes"] == 1
    with pytest.raises(RuntimeError, match="storage floor"):
        screen.require_disk_floor(tmp_path, report["total_bytes"] + 1)


def test_feasibility_decision_requires_full_frozen_cohort_and_uses_declared_band():
    tasks = [f"repo__issue-{i}" for i in range(8)]
    models = ("7B", "14B")
    episodes = []
    for model in models:
        for index, task in enumerate(tasks):
            episodes.append({"model_id": model, "task_id": task,
                "grade": {"graded": True, "resolved": model == "7B" and index < 3}})
    result = screen.competence_summary(episodes, tasks, models)
    assert result["decision"] == "FEASIBLE_PAIR_FOR_NEXT_DESIGN_ONLY"
    assert result["model_arms"]["7B"]["resolution_fraction"] == 3 / 8
    assert result["model_arms"]["14B"]["resolution_fraction"] == 0
    episodes[-1]["grade"]["graded"] = False
    result = screen.competence_summary(episodes, tasks, models)
    assert result["decision"] == "UNKNOWN_INCOMPLETE_OR_UNGRADED"
    assert result["model_arms"]["14B"]["resolution_fraction"] is None


def test_runtime_preflight_binds_python_wheels_cuda_and_numpy_bridge(tmp_path, monkeypatch):
    wheel_root = tmp_path / "wheels"
    wheel_root.mkdir()
    wheel_bytes = b"pinned-wheel"
    (wheel_root / "one.whl").write_bytes(wheel_bytes)
    wheel_manifest = tmp_path / "wheels.json"
    wheel_manifest.write_text(json.dumps([{"package": "numpy", "version": "1.26.4",
        "filename": "one.whl", "size": len(wheel_bytes),
        "sha256": hashlib.sha256(wheel_bytes).hexdigest()}]))
    manifest_sha = screen.sha_file(wheel_manifest)
    release = {"source_pins": {"experiments/lead_req030/coder_c_wheels.json": manifest_sha},
        "runtime": {"python_minor": [3, 12], "python_version": "3.12.3", "cuda": "12.8", "versions": {
            "numpy": "1.26.4", "torch": "2.9.1", "transformers": "4.51.3",
            "huggingface_hub": "0.30.2", "tokenizers": "0.21.1", "safetensors": "0.5.3",
            "accelerate": "1.6.0", "requests": "2.32.3", "jinja2": "3.1.4"}}}
    fake_numpy = types.SimpleNamespace(__version__="1.26.4", float32=object(), asarray=lambda x, dtype=None: x)
    fake_torch = types.SimpleNamespace(__version__="2.9.1+cu128", version=types.SimpleNamespace(cuda="12.8"),
        cuda=types.SimpleNamespace(is_available=lambda: True, device_count=lambda: 1,
            get_device_name=lambda _: "B200", get_device_properties=lambda _: types.SimpleNamespace(total_memory=192)),
        from_numpy=lambda x: types.SimpleNamespace(tolist=lambda: x))
    fake_transformers = types.SimpleNamespace(__version__="4.51.3")
    for name, module in (("numpy", fake_numpy), ("torch", fake_torch), ("transformers", fake_transformers)):
        monkeypatch.setitem(sys.modules, name, module)
    versions = {"numpy": "1.26.4", "huggingface-hub": "0.30.2", "tokenizers": "0.21.1", "safetensors": "0.5.3",
                "accelerate": "1.6.0", "requests": "2.32.3", "jinja2": "3.1.4"}
    monkeypatch.setattr(screen.importlib.metadata, "version", lambda name: versions[name])
    monkeypatch.setattr(screen.sys, "version_info", (3, 12, 0, "final", 0))
    monkeypatch.setattr(screen.platform, "python_version", lambda: "3.12.3")
    receipt = screen.validate_runtime_environment(release, wheel_manifest, wheel_root)
    assert receipt["numpy_torch_bridge"] == "passed"
    assert receipt["device"] == "B200"
    (wheel_root / "one.whl").write_bytes(b"changed")
    with pytest.raises(ValueError, match="wheel artifact mismatch"):
        screen.validate_runtime_environment(release, wheel_manifest, wheel_root)


def test_cuda_oom_is_classified_as_capacity_failure():
    assert screen.is_cuda_oom(RuntimeError("CUDA out of memory while allocating"))
    assert not screen.is_cuda_oom(RuntimeError("ordinary evaluator error"))


def test_cohort_status_does_not_report_unknown_outcomes_as_complete():
    tasks = [f"repo__issue-{i}" for i in range(8)]
    models = ("7B", "14B")
    episodes = [{"model_id": model, "task_id": task,
                 "grade": {"graded": True, "resolved": False}}
                for model in models for task in tasks]
    assert screen.completion_status(episodes, tasks, models, None)[0] == "COMPLETED"
    episodes[0]["grade"]["graded"] = False
    assert screen.completion_status(episodes, tasks, models, None)[0] == "COMPLETED_WITH_UNKNOWN"
    assert screen.completion_status(episodes, tasks, models, "CUDA_OUT_OF_MEMORY")[0] == "INCOMPLETE_CAPACITY"


def test_batch_launcher_leaves_exclusive_private_run_root_to_python():
    batch = (ROOT / "experiments/lead_req030/req030ag_development_screen.sbatch").read_text()
    python_source = (ROOT / "experiments/lead_req030/req030ag_screen.py").read_text()

    # The scheduler wrapper may own the parent, but only execute_batch may
    # create RESULT itself; pre-creation breaks its fail-closed exclusivity.
    result_mkdirs = [line for line in batch.splitlines()
                     if "mkdir" in line and "$RESULT" in line]
    assert result_mkdirs == []
    assert 'mkdir -m 700 "$RUN/results"' in batch
    assert '--run-root "$RESULT"' in batch
    assert 'BUNDLE="$RUN/payload/work/req030ag_screen_20260930_v4"' in batch
    assert "run_root.mkdir(mode=0o700, parents=True, exist_ok=False)" in python_source


def test_agent_patch_rejection_is_terminal_failure_not_infrastructure_unknown(tmp_path, monkeypatch):
    def fake_supervised(*args, **kwargs):
        return b"DTR_AGENT_PATCH_REJECTED\n", {"reason": "exited", "returncode": 93}
    monkeypatch.setattr(screen, "run_supervised", fake_supervised)
    result = screen.run_control_or_grade(mode="agent", task={"base_commit": "a" * 40,
        "repo": "psf/requests"}, evaluation={"stock_eval_script": "true\n", "reference_patch": ""},
        image=tmp_path / "task.sif", workspace_image=tmp_path / "workspace.img",
        eval_dir=tmp_path / "eval", output_dir=tmp_path, apptainer="/usr/bin/apptainer",
        patch_bytes=b"invalid unified diff\n")
    assert result["graded"] is True
    assert result["resolved"] is False
    assert result["reason"] == "candidate_patch_did_not_apply"
