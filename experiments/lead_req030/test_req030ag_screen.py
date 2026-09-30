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
    screen.evaluation_wrapper(path, mode=mode, expected_image_head="b" * 40)
    text = path.read_text()
    assert required_marker in text
    assert "DTR_ISOLATION_FAILURE" in text
    assert "'" + "b" * 40 + "'" in text
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


def test_pull_images_uses_digest_pinned_apptainer_docker_transport(tmp_path, monkeypatch):
    image_ref = "docker.io/swebench/example@sha256:" + "a" * 64
    calls = []

    def fake_run(argv, *, timeout):
        calls.append((argv, timeout))
        Path(argv[2]).write_bytes(b"fake-sif")

    monkeypatch.setattr(screen.shutil, "which", lambda _name: "/usr/bin/apptainer")
    monkeypatch.setattr(screen, "_run", fake_run)
    receipts = screen.pull_images({"tasks": [{
        "instance_id": "swebench__example-1", "image_ref": image_ref,
        "oci_amd64_leaf_digest": "sha256:" + "a" * 64,
    }]}, tmp_path / "images")

    assert calls == [(["/usr/bin/apptainer", "pull",
                       str(tmp_path / "images" / "swebench__example-1.sif"),
                       "docker://" + image_ref], 1800)]
    assert receipts["swebench__example-1"]["bytes"] == len(b"fake-sif")
    with pytest.raises(ValueError, match="digest-pinned docker.io"):
        screen.apptainer_docker_uri("docker.io/swebench/example:latest")


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
        "resource_cap": {"gpu_model": "NVIDIA RTX PRO 6000 Blackwell"},
        "runtime": {"python_minor": [3, 12], "python_version": "3.12.3", "cuda": "12.8", "versions": {
            "numpy": "1.26.4", "torch": "2.9.1", "transformers": "4.51.3",
            "huggingface_hub": "0.30.2", "tokenizers": "0.21.1", "safetensors": "0.5.3",
            "accelerate": "1.6.0", "requests": "2.32.3", "jinja2": "3.1.4"}}}
    fake_numpy = types.SimpleNamespace(__version__="1.26.4", float32=object(), asarray=lambda x, dtype=None: x)
    fake_torch = types.SimpleNamespace(__version__="2.9.1+cu128", version=types.SimpleNamespace(cuda="12.8"),
        cuda=types.SimpleNamespace(is_available=lambda: True, device_count=lambda: 1,
            get_device_name=lambda _: "NVIDIA RTX PRO 6000 Blackwell",
            get_device_properties=lambda _: types.SimpleNamespace(total_memory=96)),
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
    assert receipt["device"] == "NVIDIA RTX PRO 6000 Blackwell"
    fake_torch.cuda.get_device_name = lambda _: "NVIDIA B200"
    with pytest.raises(RuntimeError, match="GPU model mismatch"):
        screen.validate_runtime_environment(release, wheel_manifest, wheel_root)
    fake_torch.cuda.get_device_name = lambda _: "NVIDIA RTX PRO 6000 Blackwell"
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
    assert '#SBATCH --partition=gpu_rtx6000' in batch
    assert '#SBATCH --gres=gpu:rtx_pro_6000_blackwell:1' in batch
    assert 'BUNDLE="$RUN/payload/work/req030ag_screen_20260930_v7_final"' in batch
    assert '--reuse-image-root "$V5_IMAGES"' in batch
    assert "run_root.mkdir(mode=0o700, parents=True, exist_ok=False)" in python_source


def test_agent_patch_rejection_is_terminal_failure_not_infrastructure_unknown(tmp_path, monkeypatch):
    def fake_supervised(*args, **kwargs):
        return b"DTR_AGENT_PATCH_REJECTED\n", {"reason": "exited", "returncode": 93}
    monkeypatch.setattr(screen, "run_supervised", fake_supervised)
    result = screen.run_control_or_grade(mode="agent", task={"base_commit": "a" * 40,
        "repo": "psf/requests"}, evaluation={"stock_eval_script": "true\n", "reference_patch": ""},
        image=tmp_path / "task.sif", workspace_image=tmp_path / "workspace.img",
        eval_dir=tmp_path / "eval", output_dir=tmp_path, apptainer="/usr/bin/apptainer",
        expected_image_head="b" * 40, patch_bytes=b"invalid unified diff\n")
    assert result["graded"] is True
    assert result["resolved"] is False
    assert result["reason"] == "candidate_patch_did_not_apply"


def test_task_image_accepts_only_exact_base_or_stock_swebench_setup_child():
    base = "a" * 40
    head = "b" * 40
    stdout = (f"HEAD={head}\nTREE={'c' * 40}\nBASE_TREE={'d' * 40}\n"
              f"PARENT_LINE={head} {base}\nSUBJECT=SWE-bench\nCLEAN=1\n")
    accepted = screen.parse_task_image_git_state(stdout, "", 0, base)
    assert accepted["accepted"] is True
    assert accepted["head_relation"] == "stock_swebench_setup_child"
    assert accepted["expected_base_tree"] == "d" * 40

    direct = (f"HEAD={base}\nTREE={'d' * 40}\nBASE_TREE={'d' * 40}\n"
              f"PARENT_LINE={base} {'e' * 40}\nSUBJECT=base\nCLEAN=1\n")
    assert screen.parse_task_image_git_state(direct, "", 0, base)["accepted"] is True
    wrong_parent = stdout.replace(f"{head} {base}", f"{head} {'e' * 40}")
    assert screen.parse_task_image_git_state(wrong_parent, "", 0, base)["accepted"] is False
    wrong_subject = stdout.replace("SUBJECT=SWE-bench", "SUBJECT=untrusted")
    assert screen.parse_task_image_git_state(wrong_subject, "", 0, base)["accepted"] is False
    dirty = stdout.replace("CLEAN=1", "CLEAN=0")
    assert screen.parse_task_image_git_state(dirty, "", 0, base)["accepted"] is False
    failed = screen.parse_task_image_git_state("", "dubious ownership", 128, base)
    assert failed["accepted"] is False and failed["stderr"] == "dubious ownership"


def test_retained_sif_reuse_is_hash_and_size_bound(tmp_path, monkeypatch):
    import hashlib

    monkeypatch.setattr(screen.shutil, "which", lambda _name: "/usr/bin/apptainer")
    image_root = tmp_path / "retained"
    image_root.mkdir()
    image = image_root / "repo__task.sif"
    image.write_bytes(b"already acquired image")
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    release = {"tasks": [{"instance_id": "repo__task", "image_ref": "docker.io/x@y",
                           "oci_amd64_leaf_digest": "sha256:" + "a" * 64,
                           "sif_sha256": digest, "sif_bytes": image.stat().st_size}]}
    receipts = screen.pull_images(release, tmp_path / "new", reuse_image_root=image_root)
    assert receipts["repo__task"]["reused"] is True
    assert receipts["repo__task"]["sif_sha256"] == digest
    release["tasks"][0]["sif_bytes"] += 1
    with pytest.raises(ValueError, match="SIF identity differs"):
        screen.pull_images(release, tmp_path / "new2", reuse_image_root=image_root)


def test_image_git_diagnostic_replay_binds_all_eight_scoped_receipts(tmp_path):
    from experiments.lead_req030.req030ag_image_git_diagnostic_replay import replay

    ids = ["psf__requests-2931", "pydata__xarray-3151", "pylint-dev__pylint-8898",
           "pytest-dev__pytest-6202", "scikit-learn__scikit-learn-13328",
           "sphinx-doc__sphinx-8269", "sympy__sympy-19954", "astropy__astropy-14365"]
    manifest = {"tasks": []}
    image_manifest = {"tasks": []}
    diagnostic = {"request": "DTR-REQ-030AG-IMAGE-GIT-DIAGNOSTIC", "release_sha256": "",
                  "slurm_job_id": "27930700", "task_count": 8, "model_calls": 0,
                  "benchmark_tests": 0, "task_actions": 0,
                  "network": "none inside each task container", "tasks": []}
    for idx, task_id in enumerate(ids):
        base, head, tree = f"{idx + 1:040x}", f"{idx + 101:040x}", f"{idx + 201:040x}"
        image_hash = f"{idx + 301:064x}"
        size = 1000 + idx
        manifest["tasks"].append({"instance_id": task_id, "base_commit": base,
                                  "sif_sha256": image_hash, "sif_bytes": size})
        image_manifest["tasks"].append({"instance_id": task_id, "base_commit": base,
                                        "sif_sha256": image_hash, "sif_bytes": size})
        diagnostic["tasks"].append({"task_id": task_id, "expected_base_commit": base,
            "image_exists": True, "image_sha256": image_hash, "image_bytes": size,
            "production_check": {"returncode": 0, "stderr": "", "timed_out": False,
                "stdout": f"HEAD={head}\nTREE={tree}\nCLEAN=1\n"},
            "scoped_safe_directory_check": {"returncode": 0, "stderr": "", "timed_out": False,
                "stdout": f"{head}\n{tree}\n"}})
    manifest_raw = json.dumps(manifest, sort_keys=True).encode()
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_bytes(manifest_raw)
    image_manifest_path = tmp_path / "image-manifest.json"
    image_manifest_path.write_text(json.dumps(image_manifest, sort_keys=True))
    diagnostic["release_sha256"] = hashlib.sha256(manifest_raw).hexdigest()
    diagnostic_path = tmp_path / "diagnostic.json"
    diagnostic_path.write_text(json.dumps(diagnostic, sort_keys=True))
    diagnostic_sha = hashlib.sha256(diagnostic_path.read_bytes()).hexdigest()
    log_path = tmp_path / "job.log"
    log_path.write_text(f'"report_sha256": "{diagnostic_sha}"\n')
    result = replay(diagnostic_path, manifest_path, image_manifest_path, log_path)
    assert len(result["tasks"]) == 8
    assert all(row["clean"] and not row["safe_directory_changed_result"] for row in result["tasks"])

    diagnostic["model_calls"] = 1
    diagnostic_path.write_text(json.dumps(diagnostic, sort_keys=True))
    bad_sha = hashlib.sha256(diagnostic_path.read_bytes()).hexdigest()
    log_path.write_text(f'"report_sha256": "{bad_sha}"\n')
    with pytest.raises(ValueError, match="scope/counters"):
        replay(diagnostic_path, manifest_path, image_manifest_path, log_path)
