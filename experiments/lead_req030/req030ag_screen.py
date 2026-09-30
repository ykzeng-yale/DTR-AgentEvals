"""Controls-first real-model, eight-family SWE-bench DEVELOPMENT screen.

Evaluator/reference bytes are loaded only by the control/grading functions.
The model runner receives one hash-checked public projection and one isolated
task image/workspace at a time. Any image/control/source gate failure aborts
before the first model weight is loaded.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import posixpath
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SUPERVISOR = ROOT / "experiments/lead_req030/req030ag_bounded_supervisor.py"
ADAPTER = ROOT / "experiments/lead_req030/native_hf_text_adapter.py"
RUNNER = ROOT / "experiments/lead_req030/req030ag_seaborn_apptainer_runner.py"
UPSTREAM = ROOT / "work/upstream/mini-swe-agent-04d809ceab9df28f9adaed044884180159172930/src"
MAX_EVAL_SECONDS = 1800
MAX_EPISODE_OUTPUT = 4 * 1024 * 1024
MAX_AGENT_PATCH = 4 * 1024 * 1024
MAX_SOURCE_TAR = 8 * 1024 * 1024 * 1024
MIN_WORKSPACE_FREE = 128 * 1024 * 1024
MAX_EPISODE_SECONDS = 2700
EXPECTED_SWEBENCH_PARSER_SHA256 = "42f564edfee3c21751739bbf09d60cf3a3ecdc58ac5cf45717dc6b47a85d7459"
STATUS_WORDS = {"FAILED", "PASSED", "SKIPPED", "ERROR", "XFAIL"}
PARSER_BY_REPO = {
    "psf/requests": "parse_log_pytest_options", "pydata/xarray": "parse_log_pytest",
    "pylint-dev/pylint": "parse_log_pytest_options", "pytest-dev/pytest": "parse_log_pytest",
    "scikit-learn/scikit-learn": "parse_log_pytest_v2", "sphinx-doc/sphinx": "parse_log_pytest_v2",
    "sympy/sympy": "parse_log_sympy", "astropy/astropy": "parse_log_pytest_v2",
}
SYSTEM_PROMPT_ID = "req030ag-neutral-action-v1"
SYSTEM_TEMPLATE = (
    "You are a coding assistant operating through a shell tool. Analyze privately; do not reveal hidden chain-of-thought. "
    "In each reply, give at most one short sentence describing the next action, followed by exactly one fenced block "
    "labeled mswea_bash_command containing exactly one shell command (commands may be joined with && or ||). "
    "Do not provide multiple actions. If the task is complete, the command must be exactly: "
    "echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"
)
INSTANCE_TEMPLATE = (
    "Please solve this issue:\n\n{{task}}\n\nYou can inspect and edit the repository using shell commands. "
    "Work incrementally, run relevant checks when useful, and make a focused fix. Every response must contain one action only. "
    "To finish, run exactly `echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT` as a standalone command; "
    "the harness records the working-tree patch independently."
)
ACTION_REGEX = r"```mswea_bash_command\s*\n(.*?)\n```"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


@dataclass(frozen=True)
class ScreenTask:
    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str
    source_sha256: str


@dataclass(frozen=True)
class PreparedScreenAgent:
    task: ScreenTask
    agent_config: dict[str, Any]
    model_config: dict[str, Any]
    template_source_sha256: str


def load_release(bundle: Path, release_path: Path, expected_sha: str) -> tuple[dict, bytes]:
    raw = release_path.read_bytes()
    if sha_bytes(raw) != expected_sha:
        raise ValueError("REQ030AG release SHA-256 mismatch")
    release = json.loads(raw)
    if (release.get("request") != "DTR-REQ-030AG"
            or release.get("release_id") != "req030ag-development-20260930-v10"
            or len(release.get("tasks", [])) != 8):
        raise ValueError("REQ030AG release identity/schema mismatch")
    if len({t["family"] for t in release["tasks"]}) != 8:
        raise ValueError("frozen tasks are not one per repository family")
    if len({t["instance_id"] for t in release["tasks"]}) != 8:
        raise ValueError("duplicate frozen task identity")
    for rel, expected in release.get("source_pins", {}).items():
        candidate = ROOT / rel
        if not candidate.is_file() or sha_file(candidate) != expected:
            raise ValueError(f"REQ030AG source pin mismatch: {rel}")
    for t in release["tasks"]:
        if t["repo"] not in PARSER_BY_REPO:
            raise ValueError(f"no pinned parser for repository: {t['repo']}")
        pub = bundle / "public" / f"{t['instance_id']}.json"
        ev = bundle / "evaluator" / f"{t['instance_id']}.json"
        if len(pub.read_bytes()) != t["public_projection_bytes"] or sha_file(pub) != t["public_projection_sha256"]:
            raise ValueError(f"public projection pin mismatch: {t['instance_id']}")
        if len(ev.read_bytes()) != t["evaluator_bundle_bytes"] or sha_file(ev) != t["evaluator_bundle_sha256"]:
            raise ValueError(f"evaluator bundle pin mismatch: {t['instance_id']}")
    return release, raw


def parse_public_task(data: bytes, allowed: dict[str, dict]) -> ScreenTask:
    value = json.loads(data)
    if not isinstance(value, dict) or set(value) != {"instance_id", "repo", "base_commit", "problem_statement"}:
        raise ValueError("model projection contains unexpected/non-public fields")
    identity = value["instance_id"]
    pin = allowed.get(identity)
    if pin is None or sha_bytes(data) != pin["public_projection_sha256"]:
        raise ValueError("public task is not in the frozen cohort or its hash differs")
    if value["repo"] != pin["repo"] or value["base_commit"] != pin["base_commit"]:
        raise ValueError("public task identity does not match release")
    if not isinstance(value["problem_statement"], str) or not value["problem_statement"].strip():
        raise ValueError("empty/invalid task statement")
    return ScreenTask(identity, value["repo"], value["base_commit"], value["problem_statement"], sha_bytes(data))


def prepare_screen_agent(data: bytes, *, environment: dict[str, str], task_pins: dict[str, dict]) -> PreparedScreenAgent:
    task = parse_public_task(data, task_pins)
    if set(environment) != {"system", "release", "version", "machine"}:
        raise ValueError("only non-task platform fields may enter the system template")
    template_bytes = canonical({"id": SYSTEM_PROMPT_ID, "system": SYSTEM_TEMPLATE,
                                "instance": INSTANCE_TEMPLATE, "action_regex": ACTION_REGEX})
    template_sha = sha_bytes(template_bytes)
    agent_config = {"system_template": SYSTEM_TEMPLATE, "instance_template": INSTANCE_TEMPLATE,
                    "step_limit": 24, "wall_time_limit_seconds": 2700, "cost_limit": 0.0,
                    "max_consecutive_format_errors": 3}
    from experiments.lead_req030.seaborn_public_input import (
        load_pinned_agent_templates,
    )
    original = load_pinned_agent_templates()
    model_config = {"action_regex": ACTION_REGEX,
                    "observation_template": original.observation_template,
                    "format_error_template": original.format_error_template}
    return PreparedScreenAgent(task, agent_config, model_config, template_sha)


def validate_model_assets(release: dict, model_root: Path) -> dict[str, dict]:
    result = {}
    for model in release["models"]["models"]:
        dest = model_root / model["revision"]
        entries = {}
        for item in model["files"]:
            p = dest / item["path"]
            if not p.is_file() or p.stat().st_size != item["bytes"] or sha_file(p) != item["sha256"]:
                raise ValueError(f"model asset hash/size mismatch: {model['repo']}:{item['path']}")
            entries[item["path"]] = {"bytes": item["bytes"], "sha256": item["sha256"]}
        result[model["repo"]] = {"revision": model["revision"], "files": entries,
                                  "total_bytes": sum(x["bytes"] for x in model["files"])}
    return result


def validate_runtime_environment(release: dict, wheel_manifest_path: Path, wheel_root: Path) -> dict:
    """Validate the immutable C-package stack before controls or model loading."""
    runtime = release["runtime"]
    if sys.version_info[:2] != tuple(runtime["python_minor"]):
        raise RuntimeError(f"expected Python {runtime['python_minor']}, got {sys.version_info[:3]}")
    if platform.python_version() != runtime["python_version"]:
        raise RuntimeError(f"expected Python {runtime['python_version']}, got {platform.python_version()}")
    manifest_pin = release["source_pins"]["experiments/lead_req030/coder_c_wheels.json"]
    if sha_file(wheel_manifest_path) != manifest_pin:
        raise ValueError("immutable C wheel manifest pin mismatch")
    wheels = json.loads(wheel_manifest_path.read_bytes())
    if not isinstance(wheels, list) or not wheels:
        raise ValueError("C wheel manifest is empty or invalid")
    wheel_receipts = []
    for item in wheels:
        wheel = wheel_root / item["filename"]
        if (not wheel.is_file() or wheel.stat().st_size != item["size"]
                or sha_file(wheel) != item["sha256"]):
            raise ValueError(f"immutable installed wheel artifact mismatch: {item['package']}")
        installed_version = importlib.metadata.version(item["package"])
        if installed_version != item["version"]:
            raise RuntimeError(f"installed wheel package mismatch {item['package']}: "
                               f"expected {item['version']}, got {installed_version}")
        wheel_receipts.append({"package": item["package"], "version": item["version"],
                               "installed_version": installed_version,
                               "filename": item["filename"], "bytes": item["size"],
                               "sha256": item["sha256"]})
    import numpy
    import torch
    import transformers
    versions = {
        "numpy": numpy.__version__, "torch": torch.__version__.split("+")[0],
        "transformers": transformers.__version__,
        "huggingface_hub": importlib.metadata.version("huggingface-hub"),
        "tokenizers": importlib.metadata.version("tokenizers"),
        "safetensors": importlib.metadata.version("safetensors"),
        "accelerate": importlib.metadata.version("accelerate"),
        "requests": importlib.metadata.version("requests"),
        "jinja2": importlib.metadata.version("jinja2"),
    }
    for package, expected in runtime["versions"].items():
        observed = versions.get(package)
        if observed != expected:
            raise RuntimeError(f"runtime version mismatch {package}: expected {expected}, got {observed}")
    if torch.version.cuda != runtime["cuda"]:
        raise RuntimeError(f"CUDA runtime mismatch: expected {runtime['cuda']}, got {torch.version.cuda}")
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise RuntimeError("expected exactly one allocated CUDA device")
    expected_device = release["resource_cap"]["gpu_model"]
    observed_device = torch.cuda.get_device_name(0)
    device_identity = validate_gpu_device_name(
        observed_device, expected_device, runtime.get("gpu_model_aliases", []))
    # Exercise the compiled NumPy/PyTorch bridge before any benchmark containers run.
    bridge = torch.from_numpy(numpy.asarray([1.0], dtype=numpy.float32))
    if bridge.tolist() != [1.0]:
        raise RuntimeError("NumPy/PyTorch ABI bridge preflight failed")
    return {"python": platform.python_version(), "python_executable": sys.executable,
            "versions": versions, "cuda": torch.version.cuda,
            "device_count": torch.cuda.device_count(), "device": observed_device,
            "gpu_device_identity": device_identity,
            "device_total_bytes": torch.cuda.get_device_properties(0).total_memory,
            "numpy_torch_bridge": "passed", "wheel_manifest_sha256": manifest_pin,
            "wheels": wheel_receipts}


def validate_gpu_device_name(observed: str, expected: str, aliases: list[str]) -> dict[str, Any]:
    """Accept only the canonical GPU name or an explicitly frozen exact alias."""
    if (not isinstance(expected, str) or not expected
            or not isinstance(aliases, list)
            or any(not isinstance(alias, str) or not alias for alias in aliases)
            or len(set(aliases)) != len(aliases)
            or expected in aliases):
        raise ValueError("invalid frozen GPU model identity/alias declaration")
    accepted = [expected, *aliases]
    if observed not in accepted:
        raise RuntimeError(f"GPU model mismatch: expected one of {accepted}, got {observed}")
    return {"expected": expected, "observed": observed,
            "accepted_alias": observed != expected}


def is_cuda_oom(exc: BaseException) -> bool:
    try:
        import torch
        return isinstance(exc, torch.cuda.OutOfMemoryError)
    except Exception:
        return "out of memory" in str(exc).lower()


def download_model_assets(release: dict, model_root: Path, receipt: Path) -> dict:
    from huggingface_hub import snapshot_download
    model_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    for model in release["models"]["models"]:
        target = model_root / model["revision"]
        target.mkdir(mode=0o700, exist_ok=True)
        snapshot_download(repo_id=model["repo"], revision=model["revision"], local_dir=str(target),
                          allow_patterns=[x["path"] for x in model["files"]], max_workers=4)
    assets = validate_model_assets(release, model_root)
    _atomic_json(receipt, {"status": "verified", "models": assets})
    return assets


def _atomic_json(path: Path, value: Any) -> None:
    tmp = path.with_name(path.name + ".tmp")
    data = canonical(value)
    with tmp.open("xb") as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)


def _run(argv: list[str], *, timeout: int, stdout=None, stderr=None, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                          timeout=timeout, check=check, env={**os.environ, "HF_HUB_OFFLINE": "1",
                          "TRANSFORMERS_OFFLINE": "1", "NO_PROXY": "*", "no_proxy": "*"})


def pull_images(release: dict, image_root: Path, *, reuse_image_root: Path | None = None,
                on_image=None) -> dict[str, dict]:
    image_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    receipts = {}
    apptainer = shutil.which("apptainer")
    if not apptainer:
        raise RuntimeError("Apptainer unavailable inside compute allocation")
    for task in release["tasks"]:
        filename = f"{task['instance_id']}.sif"
        image = (reuse_image_root / filename) if reuse_image_root else (image_root / filename)
        if reuse_image_root is None:
            _run([apptainer, "pull", str(image), apptainer_docker_uri(task["image_ref"])], timeout=1800)
        elif not image.is_file():
            raise FileNotFoundError(f"pinned retained task SIF is absent: {task['instance_id']}")
        if image.stat().st_size > 80 * (1 << 30):
            raise RuntimeError("pinned task SIF exceeds frozen 80 GiB file cap")
        digest, size = sha_file(image), image.stat().st_size
        if task.get("sif_sha256") and (digest != task["sif_sha256"] or size != task["sif_bytes"]):
            raise ValueError(f"SIF identity differs from frozen pin: {task['instance_id']}")
        receipt = {"path": str(image), "sif_sha256": digest, "bytes": size,
                   "oci_leaf_digest": task["oci_amd64_leaf_digest"],
                   "reused": reuse_image_root is not None}
        receipts[task["instance_id"]] = receipt
        if on_image is not None:
            on_image(task["instance_id"], receipt)
    return receipts


def apptainer_docker_uri(image_ref: str) -> str:
    """Bind the manifest's digest-pinned Docker Hub name to Apptainer's transport syntax."""
    if not isinstance(image_ref, str) or not re.fullmatch(
            r"docker\.io/[a-z0-9._/-]+@sha256:[0-9a-f]{64}", image_ref):
        raise ValueError("task image reference must be a digest-pinned docker.io name")
    return "docker://" + image_ref


def _safe_extract_source_tar(archive: Path, destination: Path) -> dict:
    if archive.stat().st_size > MAX_SOURCE_TAR:
        raise ValueError("task source tar exceeds frozen cap")
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    symlinks = []
    unpacked = 0
    with tarfile.open(archive, "r:") as tar:
        members = tar.getmembers()
        if not members or len(members) > 1_000_000:
            raise ValueError("task source tar member count invalid")
        for member in members:
            p = PurePosixPath(member.name)
            if p.is_absolute() or any(part in ("", ".", "..") for part in p.parts):
                raise ValueError("unsafe task source path")
            if not p.parts or p.parts[0] != "testbed":
                raise ValueError("task source tar escaped /testbed")
            rel = Path(*p.parts[1:]) if len(p.parts) > 1 else Path()
            target = destination / rel
            if member.isdir():
                target.mkdir(mode=0o700, parents=True, exist_ok=True)
            elif member.isfile():
                if member.size > 512 * 1024 * 1024:
                    raise ValueError("task source member exceeds 512 MiB")
                unpacked += member.size
                if unpacked > 8 * 1024 * 1024 * 1024:
                    raise ValueError("task source unpacked size exceeds 8 GiB")
                target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
                src = tar.extractfile(member)
                if src is None:
                    raise ValueError("task source member has no data")
                fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                             member.mode & 0o777)
                with os.fdopen(fd, "wb") as out:
                    shutil.copyfileobj(src, out, 1024 * 1024)
                    out.flush(); os.fsync(out.fileno())
                os.chmod(target, member.mode & 0o777)
            elif member.issym():
                if not member.linkname or member.linkname.startswith("/"):
                    raise ValueError("absolute/empty source symlink refused")
                resolved = posixpath.normpath(posixpath.join(posixpath.dirname(member.name), member.linkname))
                if resolved != "testbed" and not resolved.startswith("testbed/"):
                    raise ValueError("source symlink escapes /testbed")
                symlinks.append((target, member.linkname))
            else:
                raise ValueError("special/hardlink member in task source tar")
        symlink_paths = {p for p, _ in symlinks}
        for target, linkname in symlinks:
            if any(parent in symlink_paths for parent in target.parents if parent != destination):
                raise ValueError("nested symlink path refused")
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            target.symlink_to(linkname)
    return {"members": len(members), "regular_bytes": unpacked, "symlinks": len(symlinks)}


def parse_task_image_git_state(stdout: str, stderr: str, returncode: int,
                               expected_base: str) -> dict:
    """Validate the source state produced by the pinned SWE-bench image builder."""
    if not re.fullmatch(r"[0-9a-f]{40}", expected_base):
        raise ValueError("task base commit is not a canonical Git SHA")
    record = {"returncode": returncode, "stdout": stdout, "stderr": stderr,
              "expected_base_commit": expected_base, "accepted": False}
    if returncode != 0:
        return record
    fields: dict[str, str] = {}
    for line in stdout.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            if key in fields:
                return record
            fields[key] = value
    if set(fields) != {"HEAD", "TREE", "BASE_TREE", "PARENT_LINE", "SUBJECT", "CLEAN"}:
        return record
    if any(not re.fullmatch(r"[0-9a-f]{40}", fields[key])
           for key in ("HEAD", "TREE", "BASE_TREE")):
        return record
    parent_fields = fields["PARENT_LINE"].split()
    if not parent_fields or parent_fields[0] != fields["HEAD"]:
        return record
    parents = parent_fields[1:]
    direct_base = fields["HEAD"] == expected_base
    stock_setup_child = (len(parents) == 1 and parents[0] == expected_base
                         and fields["SUBJECT"] == "SWE-bench")
    record.update({"head": fields["HEAD"], "tree": fields["TREE"],
                   "expected_base_tree": fields["BASE_TREE"], "parents": parents,
                   "subject": fields["SUBJECT"], "clean": fields["CLEAN"] == "1",
                   "head_relation": "base_commit" if direct_base else
                                   "stock_swebench_setup_child" if stock_setup_child else "mismatch"})
    record["accepted"] = fields["CLEAN"] == "1" and (direct_base or stock_setup_child)
    return record


class TaskImageGateError(RuntimeError):
    def __init__(self, evidence: dict):
        self.evidence = evidence
        super().__init__("task image is not a clean base or pinned SWE-bench setup child")


def _tree_for_task(image: Path, expected_base: str, apptainer: str) -> dict:
    if not re.fullmatch(r"[0-9a-f]{40}", expected_base):
        raise ValueError("task base commit is not a canonical Git SHA")
    shell = ("set -euo pipefail; cd /testbed; "
             "printf 'HEAD='; git rev-parse HEAD; "
             "printf 'TREE='; git rev-parse 'HEAD^{tree}'; "
             f"printf 'BASE_TREE='; git rev-parse '{expected_base}^{{tree}}'; "
             "printf 'PARENT_LINE='; git rev-list --parents -n 1 HEAD; "
             "printf 'SUBJECT='; git show -s --format=%s HEAD; "
             "status=\"$(git status --porcelain --untracked-files=all)\"; "
             "if [[ -z \"$status\" ]]; then echo CLEAN=1; else echo CLEAN=0; fi")
    cmd = [apptainer, "exec", "--containall", "--cleanenv", "--no-home", "--no-mount", "hostfs,bind-paths",
           "--net", "--network", "none", "--pwd", "/", str(image), "/bin/bash", "-lc",
           shell]
    result = _run(cmd, timeout=45, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    check = parse_task_image_git_state(result.stdout.decode("utf-8", "replace"),
                                       result.stderr.decode("utf-8", "replace"),
                                       result.returncode, expected_base)
    if not check["accepted"]:
        raise TaskImageGateError(check)
    return check


def require_disk_floor(path: Path, required_bytes: int) -> dict:
    usage = shutil.disk_usage(path)
    if usage.free < required_bytes:
        raise RuntimeError(f"storage floor failed: free={usage.free}, required={required_bytes}")
    return {"free_bytes": usage.free, "total_bytes": usage.total, "required_bytes": required_bytes}


def competence_summary(episodes: list[dict], expected_task_ids: list[str], model_ids: tuple[str, str]) -> dict:
    arms = {}
    expected = set(expected_task_ids)
    if len(expected) != 8 or len(expected_task_ids) != 8:
        raise ValueError("REQ030AG competence gate requires eight unique frozen tasks")
    for model_id in model_ids:
        cells = [episode for episode in episodes if episode.get("model_id") == model_id]
        counts: dict[str, int] = {}
        for episode in cells:
            tid = episode.get("task_id")
            counts[tid] = counts.get(tid, 0) + 1
        exact_cells = len(cells) == 8 and set(counts) == expected and all(value == 1 for value in counts.values())
        graded = [episode for episode in cells if episode.get("grade", {}).get("graded") is True]
        complete = exact_cells and len(graded) == 8
        resolved = sum(bool(episode.get("grade", {}).get("resolved")) for episode in graded)
        arms[model_id] = {"assigned": len(cells), "exact_cohort_once": exact_cells,
                          "graded": len(graded), "resolved": resolved,
                          "unknown": 8 - len(graded) if exact_cells else None,
                          "resolution_fraction": resolved / 8 if complete else None,
                          "complete_case_gate": complete}
    complete = all(arm["complete_case_gate"] for arm in arms.values())
    band = complete and any(0.15 <= arm["resolution_fraction"] <= 0.85 for arm in arms.values())
    return {"model_arms": arms, "complete_case_gate": complete, "provisional_feasibility_band": [0.15, 0.85],
            "interpretation": "descriptive eight-family development gate; not a population estimate or router effect",
            "decision": "FEASIBLE_PAIR_FOR_NEXT_DESIGN_ONLY" if band else
                        ("NO_PAIR_IN_FEASIBILITY_BAND" if complete else "UNKNOWN_INCOMPLETE_OR_UNGRADED")}


def completion_status(episodes: list[dict], expected_task_ids: list[str], model_ids: tuple[str, str],
                      stop_reason: str | None) -> tuple[str, dict]:
    summary = competence_summary(episodes, expected_task_ids, model_ids)
    if stop_reason:
        return "INCOMPLETE_CAPACITY", summary
    if not summary["complete_case_gate"]:
        return "COMPLETED_WITH_UNKNOWN", summary
    return "COMPLETED", summary


def export_task_tree(image: Path, archive: Path, apptainer: str) -> dict:
    cmd = [apptainer, "exec", "--containall", "--cleanenv", "--no-home", "--no-mount", "hostfs,bind-paths",
           "--net", "--network", "none", "--pwd", "/", str(image), "/bin/tar", "-C", "/", "-cf", "-", "testbed"]
    with archive.open("xb") as out:
        _run(cmd, timeout=600, stdout=out, stderr=subprocess.PIPE)
        out.flush(); os.fsync(out.fileno())
    return {"archive_sha256": sha_file(archive), "archive_bytes": archive.stat().st_size}


def make_workspace(source_tar: Path, workdir: Path, workspace_image: Path, *, uid: int, gid: int) -> dict:
    extracted = workdir / "seed"
    extraction = _safe_extract_source_tar(source_tar, extracted)
    # The safe extractor strips the archive's leading /testbed component.
    tree = extracted
    size = sum(p.stat().st_size for p in tree.rglob("*") if p.is_file() and not p.is_symlink())
    image_bytes = max(2 * (1 << 30), int(size * 2.4) + 512 * 1024 * 1024)
    image_bytes = min(image_bytes, 8 * (1 << 30))
    with workspace_image.open("xb") as f:
        f.truncate(image_bytes)
    _run(["mkfs.ext3", "-F", "-m", "0", "-d", str(tree), str(workspace_image)], timeout=600,
         stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for key, value in (("uid", uid), ("gid", gid)):
        _run(["debugfs", "-w", "-R", f"set_inode_field / {key} {value}", str(workspace_image)],
             timeout=30, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    shutil.rmtree(extracted)
    return {"image_sha256": sha_file(workspace_image), "image_bytes": workspace_image.stat().st_size,
            "source_unpacked_bytes": extraction["regular_bytes"], "source_members": extraction["members"]}


def run_supervised(apptainer: str, image: Path, workspace_image: Path, command: list[str],
                   *, output_path: Path, receipt_path: Path, seconds: int,
                   extra_binds: list[str] | tuple[str, ...] = ()) -> tuple[bytes, dict]:
    if not 0 < seconds <= 3600:
        raise ValueError("supervised command timeout exceeds one hour")
    parent_stat = output_path.parent.stat()
    if (not stat.S_ISDIR(parent_stat.st_mode) or parent_stat.st_uid != os.getuid()
            or stat.S_IMODE(parent_stat.st_mode) != 0o700):
        raise PermissionError("supervisor output directory must be private and owned")
    if receipt_path.parent != output_path.parent:
        raise ValueError("supervisor output and receipt must share one private directory")
    if output_path.exists() or output_path.is_symlink():
        raise FileExistsError(output_path)
    fd = os.open(receipt_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL
                 | getattr(os, "O_NOFOLLOW", 0), 0o600)
    os.close(fd)
    host_net = os.readlink("/proc/self/ns/net")
    argv = [apptainer, "exec", "--containall", "--cleanenv", "--no-home", "--no-mount", "hostfs,bind-paths",
            "--net", "--network", "none", "--pwd", "/testbed", "--env", f"DTR_HOST_NET_ID={host_net}",
            "--bind", f"{workspace_image}:/testbed:image-src=/"] + list(extra_binds) + [str(image), *command]
    rfd, wfd = os.pipe()
    proc_cmd = [sys.executable, str(SUPERVISOR), "--owner-fd", str(rfd), "--out", str(output_path),
                "--receipt", str(receipt_path), "--seconds", str(seconds), "--cap", str(MAX_EPISODE_OUTPUT),
                "--", *argv]
    try:
        proc = subprocess.Popen(proc_cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL, close_fds=True, pass_fds=(rfd,), start_new_session=True)
    except BaseException:
        os.close(rfd); os.close(wfd)
        raise
    os.close(rfd)
    try:
        rc = proc.wait(timeout=seconds + 20)
    except subprocess.TimeoutExpired:
        raise RuntimeError("bounded supervisor exceeded outer deadline")
    finally:
        # The owner pipe is the production cancellation mechanism. Give the
        # supervisor time to kill its container group before stopping it.
        os.close(wfd)
        try:
            proc.wait(timeout=7)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait(timeout=3)
    if rc != 0:
        receipt = json.loads(receipt_path.read_text()) if receipt_path.is_file() else None
        raise RuntimeError(f"bounded supervisor exit {rc}; receipt={receipt}")
    receipt = json.loads(receipt_path.read_text())
    if not output_path.exists():
        raise RuntimeError(f"bounded supervisor output missing; receipt={receipt}")
    output_stat = output_path.lstat()
    if (not stat.S_ISREG(output_stat.st_mode) or output_stat.st_uid != os.getuid()
            or stat.S_IMODE(output_stat.st_mode) != 0o600):
        raise PermissionError("supervisor output must be a private owned regular file")
    output = output_path.read_bytes()
    if receipt["reason"] != "exited" or receipt["retained_bytes"] != len(output) or len(output) > MAX_EPISODE_OUTPUT:
        raise RuntimeError(f"bounded command did not complete cleanly: {receipt}")
    return output, receipt


def parse_pytest_statuses(text: str, parser_name: str) -> dict[str, str]:
    """Source-equivalent subset of the exact f7bbbb2 repository log parser."""
    found = {}
    if parser_name not in set(PARSER_BY_REPO.values()):
        raise ValueError(f"unrecognized pinned parser: {parser_name}")
    option_pattern = re.compile(r"(.*?)\[(.*)\]")
    escapes = "".join(chr(code) for code in range(1, 32))
    for original in text.split("\n"):
        line = original
        if parser_name == "parse_log_sympy":
            m = re.match(r"(_*) (.*)\.py:(.*) (_*)", line)
            if m:
                found[m.group(2) + ".py:" + m.group(3)] = "FAILED"
            stripped = line.strip()
            if stripped.startswith("test_"):
                if stripped.endswith(" E"):
                    found[stripped.split()[0]] = "ERROR"
                if stripped.endswith(" F"):
                    found[stripped.split()[0]] = "FAILED"
                if stripped.endswith(" ok"):
                    found[stripped.split()[0]] = "PASSED"
            continue
        if parser_name == "parse_log_pytest_v2":
            line = re.sub(r"\[(\d+)m", "", line).translate(str.maketrans("", "", escapes))
            if any(line.startswith(s) for s in STATUS_WORDS):
                if line.startswith("FAILED"):
                    line = line.replace(" - ", " ")
                parts = line.split()
                if len(parts) >= 2:
                    found[parts[1]] = parts[0]
            elif any(line.endswith(s) for s in STATUS_WORDS):
                parts = line.split()
                if len(parts) >= 2:
                    found[parts[0]] = parts[1]
            continue
        if not any(line.startswith(s) for s in STATUS_WORDS):
            continue
        if line.startswith("FAILED"):
            line = line.replace(" - ", " ")
        parts = line.split()
        if len(parts) > 1:
            test_id = parts[1]
            if parser_name == "parse_log_pytest_options":
                m = option_pattern.search(test_id)
                if m:
                    main, option = m.groups()
                    if option.startswith("/") and not option.startswith("//") and "*" not in option:
                        option = "/" + option.split("/")[-1]
                    test_id = f"{main}[{option}]"
            found[test_id] = parts[0]
    return found


def control_result(raw: bytes, supervisor: dict, evaluation: dict, mode: str, parser_name: str) -> dict:
    text = raw.decode("utf-8", "replace")
    ids_f, ids_p = evaluation["fail_to_pass"], evaluation["pass_to_pass"]
    markers = (text.count("DTR_TEST_START") == 1 and text.count("DTR_TEST_END") == 1
               and text.count(">>>>> Start Test Output") == 1 and text.count(">>>>> End Test Output") == 1
               and text.index("DTR_TEST_START") < text.index(">>>>> Start Test Output")
               < text.index(">>>>> End Test Output") < text.index("DTR_TEST_END"))
    payload = text.split(">>>>> Start Test Output", 1)[1].split(">>>>> End Test Output", 1)[0] if markers else ""
    status = parse_pytest_statuses(payload, parser_name) if markers else {}
    statuses = {test: status.get(test, "MISSING") for test in ids_f + ids_p}
    valid_process = (markers and supervisor.get("reason") == "exited"
                     and supervisor.get("returncode") in (0, 1)
                     and "DTR_SETUP_FAILURE" not in text and "DTR_EVAL_ERROR" not in text
                     and "DTR_ISOLATION_FAILURE" not in text)
    if mode == "baseline":
        accepted = valid_process and all(statuses[t] == "FAILED" for t in ids_f) and all(statuses[t] == "PASSED" for t in ids_p)
    elif mode == "reference":
        accepted = valid_process and all(statuses[t] == "PASSED" for t in ids_f + ids_p)
    else:
        raise ValueError("unknown control mode")
    return {"mode": mode, "valid_process": valid_process, "markers_valid": markers, "accepted": accepted,
            "declared_statuses": statuses, "observed_status_count": len(status),
            "undeclared_statuses": {k: v for k, v in status.items() if k not in set(ids_f + ids_p)},
            "raw_sha256": sha_bytes(raw), "raw_bytes": len(raw),
            "supervisor": supervisor}


def evaluation_wrapper(path: Path, *, mode: str, expected_image_head: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", expected_image_head):
        raise ValueError("expected initial image HEAD is not a canonical Git SHA")
    lines = ["#!/bin/bash", "set -uo pipefail",
             'if [[ "$(readlink /proc/self/ns/net)" == "$DTR_HOST_NET_ID" ]]; then echo DTR_ISOLATION_FAILURE; exit 80; fi',
             "test ! -e /home/yz2324 || { echo DTR_ISOLATION_FAILURE; exit 81; }",
             "test ! -e /nfs/roberts || { echo DTR_ISOLATION_FAILURE; exit 82; }",
             "if touch /DTR_ROOT_WRITE_TEST 2>/dev/null; then rm -f /DTR_ROOT_WRITE_TEST; echo DTR_ISOLATION_FAILURE; exit 83; fi",
             "cd /testbed", "test -d .git || { echo DTR_SETUP_FAILURE; exit 84; }",
             f"if [[ \"$(git rev-parse HEAD)\" != '{expected_image_head}' ]]; then echo DTR_SETUP_FAILURE; exit 90; fi"]
    if mode == "reference":
        lines += ["if ! git apply --check /eval/reference.diff; then echo DTR_SETUP_FAILURE; exit 91; fi",
                  "if ! git apply /eval/reference.diff; then echo DTR_SETUP_FAILURE; exit 92; fi"]
    elif mode == "agent":
        lines += ["if ! git apply --check /eval/agent.diff; then echo DTR_AGENT_PATCH_REJECTED; exit 93; fi",
                  "if ! git apply /eval/agent.diff; then echo DTR_AGENT_PATCH_REJECTED; exit 94; fi"]
    elif mode != "baseline":
        raise ValueError(mode)
    lines += ["printf 'DTR_TEST_START\\n'", "bash /eval/stock_eval.sh", "rc=$?",
              "printf 'DTR_TEST_END\\n'", "exit \"$rc\""]
    path.write_text("\n".join(lines) + "\n")
    path.chmod(0o500)


def patch_harvest_script(base_commit: str) -> str:
    if len(base_commit) != 40 or any(ch not in "0123456789abcdef" for ch in base_commit):
        raise ValueError("patch base commit is not a canonical Git SHA")
    return ("#!/bin/bash\nset -euo pipefail\ncd /testbed\ngit add -N -A\n"
            f"git diff --no-ext-diff --binary {base_commit}\n")


def run_control_or_grade(*, mode: str, task: dict, evaluation: dict, image: Path,
                         workspace_image: Path, eval_dir: Path, output_dir: Path,
                         apptainer: str, expected_image_head: str,
                         patch_bytes: bytes | None = None) -> dict:
    eval_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
    (eval_dir / "stock_eval.sh").write_text(evaluation["stock_eval_script"])
    (eval_dir / "stock_eval.sh").chmod(0o400)
    if mode == "reference":
        (eval_dir / "reference.diff").write_text(evaluation["reference_patch"])
        (eval_dir / "reference.diff").chmod(0o400)
    if mode == "agent":
        if not patch_bytes:
            return {"mode": "agent", "graded": True, "resolved": False, "reason": "empty_submission"}
        (eval_dir / "agent.diff").write_bytes(patch_bytes)
        (eval_dir / "agent.diff").chmod(0o400)
    wrapper = eval_dir / "run.sh"
    evaluation_wrapper(wrapper, mode=mode, expected_image_head=expected_image_head)
    extra = ["--bind", f"{eval_dir.resolve()}:/eval:ro"]
    raw, sup = run_supervised(apptainer, image, workspace_image, ["/bin/bash", "/eval/run.sh"],
        output_path=output_dir / f"{mode}.out", receipt_path=output_dir / f"{mode}.supervisor.json",
        seconds=MAX_EVAL_SECONDS, extra_binds=extra)
    if (mode == "agent" and raw.strip() == b"DTR_AGENT_PATCH_REJECTED"
            and sup.get("reason") == "exited" and sup.get("returncode") == 93):
        return {"mode": "agent", "graded": True, "resolved": False,
                "reason": "candidate_patch_did_not_apply", "patch_sha256": sha_bytes(patch_bytes),
                "patch_bytes": len(patch_bytes), "supervisor": sup, "raw_sha256": sha_bytes(raw)}
    result = control_result(raw, sup, evaluation, mode="baseline" if mode == "agent" else mode,
                            parser_name=PARSER_BY_REPO[task["repo"]])
    if mode == "agent":
        required = evaluation["fail_to_pass"] + evaluation["pass_to_pass"]
        all_observed = all(result["declared_statuses"][t] != "MISSING" for t in required)
        resolved = (result["valid_process"] and all_observed and
                    all(result["declared_statuses"][t] == "PASSED" for t in required))
        return {"mode": "agent", "graded": result["valid_process"] and all_observed, "resolved": resolved,
                "declared_statuses": result["declared_statuses"], "raw_sha256": result["raw_sha256"],
                "raw_bytes": result["raw_bytes"], "supervisor": sup,
                "patch_sha256": sha_bytes(patch_bytes), "patch_bytes": len(patch_bytes)}
    return result


def launch_agent_episode(*, model_id: str, model_info: dict, model: Any, tokenizer: Any,
                         task: dict, release: dict, bundle: Path, model_run_dir: Path,
                         image: Path, source_tar: Path, workspace_image: Path, apptainer: str, release_sha256: str,
                         event_parent: Path, expected_image_head: str,
                         model_factory_builder: Any = None) -> dict:
    from experiments.lead_req030.seaborn_runner_qualification import load_pinned_default_agent
    DefaultAgent = load_pinned_default_agent()
    import torch
    from experiments.lead_req030.native_hf_text_adapter import NativeHFTextAdapter
    from experiments.lead_req030.req030ag_seaborn_apptainer_runner import run_pinned_agent

    public = (bundle / "public" / f"{task['instance_id']}.json").read_bytes()
    allowed = {x["instance_id"]: x for x in release["tasks"]}
    prompt_raw = (ROOT / "configs/req030ag_prompt_20260929.json").read_bytes()
    prompt = json.loads(prompt_raw)
    if prompt["id"] != SYSTEM_PROMPT_ID or prompt["system_template"] != SYSTEM_TEMPLATE or prompt["instance_template"] != INSTANCE_TEMPLATE:
        raise ValueError("public prompt differs from source-pinned REQ030AG prompt")
    task = parse_public_task(public, allowed)
    task_work = workspace_image
    make_workspace(source_tar, event_parent / "temporary_seed", task_work, uid=os.getuid(), gid=os.getgid())

    def parser(raw: bytes):
        return parse_public_task(raw, allowed)

    def preparer(raw: bytes, *, environment: dict[str, str], **kwargs):
        return prepare_screen_agent(raw, environment=environment, task_pins=allowed)

    def factory(record_event, config):
        if model_factory_builder is not None:
            return model_factory_builder(record_event, config)
        return NativeHFTextAdapter(tokenizer=tokenizer, model=model, model_id=model_info["repo"],
            revision=model_info["revision"], context_limit=16384, max_new_tokens=1536,
            record_event=record_event, device="cuda:0", **config)

    try:
        torch.cuda.synchronize()
        torch.cuda.reset_peak_memory_stats()
        outcome = run_pinned_agent(agent_class=DefaultAgent, model_factory=factory,
            public_projection=public, run_directory=model_run_dir, apptainer=apptainer,
            image=image, image_sha256=sha_file(image), workspace_image=task_work,
            workspace_sha256=sha_file(task_work), supervisor=SUPERVISOR,
            supervisor_sha256=sha_file(SUPERVISOR), release_id=release["release_id"],
            release_sha256=release_sha256,
            step_limit=24, wall_time_limit_seconds=2700, model_context_limit=16384,
            model_max_new_tokens=1536, tool_timeout_seconds=60, output_cap_bytes=4*1024*1024,
            action_cap_bytes=1024*1024, max_consecutive_format_errors=3,
            public_task_parser=parser, agent_preparer=preparer)
        agent_result = outcome["result"]
        events_path = Path(outcome["run_directory"]) / "events.jsonl"
        events = [json.loads(line) for line in events_path.read_text().splitlines() if line]
        response_events = [event for event in events if event.get("event") == "response"]
        request_count = sum(event.get("event") == "request" for event in events)
        finish_events = [event for event in events if event.get("event") == "agent_run_finish"]
        physical_calls = finish_events[-1].get("physical_model_calls") if finish_events else None
        if physical_calls != len(response_events) or request_count != len(response_events):
            raise RuntimeError("physical call count differs from durable request/response events")
        exit_status = agent_result.get("exit_status", "")
        if exit_status not in {"Submitted", "LimitsExceeded", "TimeExceeded", "RepeatedFormatError"}:
            raise RuntimeError(f"unclassified agent exit: {exit_status!r}")
        torch.cuda.synchronize()
        episode = {"task_id": task.instance_id, "model_id": model_info["repo"], "revision": model_info["revision"],
                "agent_exit_status": exit_status,
                "agent_submission_bytes": len(str(agent_result.get("submission", "")).encode()),
                "physical_calls": physical_calls, "trajectory_sha256": outcome["trajectory_sha256"],
                "event_log_sha256": sha_file(events_path),
                "input_tokens": sum(event.get("input_tokens", 0) for event in events if event.get("event") == "request"),
                "output_tokens": sum(event.get("output_tokens", 0) for event in response_events),
                "generation_seconds": sum(event.get("elapsed_seconds", 0) for event in response_events),
                "finish_reasons": [event.get("finish_reason") for event in response_events],
                "tool_action_count": sum(event.get("event") == "action_finish" for event in events),
                "tool_output_bytes": sum(event.get("retained_bytes", 0) for event in events if event.get("event") == "action_finish"),
                "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
                "submission_eligible": exit_status == "Submitted",
                "status": "episode_complete"}
        if exit_status != "Submitted":
            # The frozen endpoint requires explicit submission. Never salvage
            # an intermediate workspace after a normal budget/format stop.
            episode.update({"patch_bytes": 0, "patch_sha256": sha_bytes(b""),
                "patch_harvest_supervisor": None, "workspace_sha256_at_exit": sha_file(task_work),
                "grade": {"mode": "agent", "graded": True, "resolved": False,
                          "reason": "no_eligible_submission", "agent_exit_status": exit_status},
                "outcome_source": "operational_limit"})
            return episode
        # Include added/changed tracked files and untracked non-ignored files in
        # an explicitly submitted patch; never execute model text on the host.
        harvest = event_parent / "harvest.sh"
        with harvest.open("x") as stream:
            stream.write(patch_harvest_script(task.base_commit))
        harvest.chmod(0o500)
        extra = ["--bind", f"{harvest.resolve()}:/tmp/harvest.sh:ro"]
        patch, sup = run_supervised(apptainer, image, task_work, ["/bin/bash", "/tmp/harvest.sh"],
            output_path=event_parent / "patch.out", receipt_path=event_parent / "patch.supervisor.json",
            seconds=30, extra_binds=extra)
        if len(patch) > MAX_AGENT_PATCH:
            raise RuntimeError("agent submission patch exceeds the frozen 4 MiB cap")
        (event_parent / "patch.diff").write_bytes(patch)
        episode.update({"patch_sha256": sha_bytes(patch), "patch_bytes": len(patch),
                        "patch_harvest_supervisor": sup,
                        "workspace_sha256_after_harvest": sha_file(task_work)})
        return episode
    finally:
        if task_work.exists():
            task_work.unlink()


def _load_models(release: dict, model_root: Path, run_dir: Path) -> tuple[dict[str, Any], Any, dict]:
    import torch
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer
    if torch.__version__.split("+")[0] != "2.9.1" or transformers.__version__ != "4.51.3" or torch.version.cuda != "12.8":
        raise RuntimeError("unfrozen PyTorch/Transformers/CUDA runtime")
    if not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise RuntimeError("expected exactly one allocated CUDA device")
    device_name = torch.cuda.get_device_name(0)
    device_identity = validate_gpu_device_name(
        device_name, release["resource_cap"]["gpu_model"],
        release["runtime"].get("gpu_model_aliases", []))
    os.environ["HF_HUB_OFFLINE"] = "1"; os.environ["TRANSFORMERS_OFFLINE"] = "1"
    assets = validate_model_assets(release, model_root)
    infos = {m["repo"]: m for m in release["models"]["models"]}
    tokenizer_info = infos["Qwen/Qwen2.5-Coder-7B-Instruct"]
    tokenizer_dir = model_root / tokenizer_info["revision"]
    tokenizer = AutoTokenizer.from_pretrained(str(tokenizer_dir), local_files_only=True, trust_remote_code=False)
    models = {}
    receipts = {"runtime": {"torch": torch.__version__, "transformers": transformers.__version__,
                "cuda": torch.version.cuda, "device": device_name,
                "gpu_device_identity": device_identity,
                "device_total_bytes": torch.cuda.get_device_properties(0).total_memory}, "loads": []}
    for name in ("Qwen/Qwen2.5-Coder-7B-Instruct", "Qwen/Qwen2.5-Coder-14B-Instruct"):
        info = infos[name]
        start = time.monotonic(); torch.cuda.reset_peak_memory_stats()
        model = AutoModelForCausalLM.from_pretrained(str(model_root / info["revision"]), local_files_only=True,
            trust_remote_code=False, use_safetensors=True, torch_dtype=torch.bfloat16,
            device_map={"": 0}, attn_implementation="sdpa", low_cpu_mem_usage=True)
        model.eval()
        torch.cuda.synchronize()
        receipt = {"repo": name, "revision": info["revision"], "load_seconds": time.monotonic()-start,
                   "allocated_bytes": torch.cuda.memory_allocated(), "reserved_bytes": torch.cuda.memory_reserved(),
                   "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                   "peak_reserved_bytes": torch.cuda.max_memory_reserved()}
        if receipt["allocated_bytes"] > 80 * (1 << 30):
            raise RuntimeError("single model allocation exceeds frozen 80 GiB sanity cap")
        receipts["loads"].append(receipt); models[name] = model
        _atomic_json(run_dir / "model_loads.json", receipts)
    free, total = torch.cuda.mem_get_info()
    receipts["after_both_models"] = {"free_bytes": free, "total_bytes": total}
    # The worker hashes this complete returned receipt at model_ready. Retain
    # those same fields even when the fixed free-memory gate rejects admission.
    _atomic_json(run_dir / "model_loads.json", receipts)
    if free < 20 * (1 << 30):
        raise RuntimeError("less than 20 GiB free after loading both frozen models")
    return models, tokenizer, receipts


def execute_batch(args) -> dict:
    bundle = Path(args.bundle).resolve(strict=True)
    release_path = Path(args.release).resolve(strict=True)
    release, release_raw = load_release(bundle, release_path, args.release_sha256)
    run_root = Path(args.run_root).resolve()
    run_root.mkdir(mode=0o700, parents=True, exist_ok=False)
    if stat.S_IMODE(run_root.stat().st_mode) != 0o700 or run_root.stat().st_uid != os.getuid():
        raise PermissionError("batch evidence directory must be private and owned")
    batch = {"request": "DTR-REQ-030AG", "release_sha256": sha_bytes(release_raw),
             "slurm_job_id": os.environ.get("SLURM_JOB_ID"), "status": "STAGING",
             "task_count": 8, "planned_model_episodes": 16, "tasks": [], "controls": [], "episodes": [],
             "models_loaded": False, "model_episode_started": False, "error": None,
             "started_epoch": time.time(), "runtime": {"host": platform.uname()._asdict()}}
    _atomic_json(run_root / "batch_summary.json", batch)
    batch["storage_preflight"] = require_disk_floor(run_root, 200 * (1 << 30))
    batch["runtime_preflight"] = validate_runtime_environment(
        release, Path(args.wheel_manifest).resolve(strict=True), Path(args.wheel_root).resolve(strict=True))
    _atomic_json(run_root / "batch_summary.json", batch)
    apptainer = shutil.which("apptainer")
    if not apptainer:
        raise RuntimeError("Apptainer not found")
    image_root = run_root / "images"; image_root.mkdir(mode=0o700)
    source_root = run_root / "sources"; source_root.mkdir(mode=0o700)
    batch["images"] = {}
    batch["task_image_heads"] = {}
    def save_image_receipt(task_id, receipt):
        batch["images"][task_id] = receipt
        _atomic_json(run_root / "batch_summary.json", batch)
    images = pull_images(release, image_root,
                         reuse_image_root=Path(args.reuse_image_root).resolve() if args.reuse_image_root else None,
                         on_image=save_image_receipt)
    batch["storage_after_images"] = require_disk_floor(run_root, 100 * (1 << 30))
    _atomic_json(run_root / "batch_summary.json", batch)
    for task in release["tasks"]:
        image = Path(images[task["instance_id"]]["path"])
        try:
            source_check = _tree_for_task(image, task["base_commit"], apptainer)
        except TaskImageGateError as exc:
            batch["tasks"].append({**task, "image": images[task["instance_id"]],
                                   "source_check": exc.evidence, "status": "image_gate_failed"})
            _atomic_json(run_root / "batch_summary.json", batch)
            raise
        batch["task_image_heads"][task["instance_id"]] = source_check["head"]
        _atomic_json(run_root / "batch_summary.json", batch)
        tar_path = source_root / f"{task['instance_id']}.tar"
        export_receipt = export_task_tree(image, tar_path, apptainer)
        batch["tasks"].append({**task, "image": images[task["instance_id"]],
                               "source_check": source_check, "source_archive": export_receipt,
                               "status": "image_and_source_verified"})
        _atomic_json(run_root / "batch_summary.json", batch)

    batch["storage_after_source_exports"] = require_disk_floor(run_root, 80 * (1 << 30))
    _atomic_json(run_root / "batch_summary.json", batch)

    # Controls-first gate: no weights downloaded/loaded and no model call until
    # every exact candidate image and both evaluator arms pass for all 8 tasks.
    control_root = run_root / "controls"; control_root.mkdir(mode=0o700)
    for task in release["tasks"]:
        tid = task["instance_id"]
        image = Path(images[tid]["path"])
        evaluation = json.loads((bundle / "evaluator" / f"{tid}.json").read_bytes())
        public_task = json.loads((bundle / "public" / f"{tid}.json").read_bytes())
        if evaluation["instance_id"] != tid or evaluation["base_commit"] != task["base_commit"]:
            raise ValueError("public/evaluator task identity mismatch")
        for mode in ("baseline", "reference"):
            ctl_dir = control_root / tid / mode; ctl_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
            ws = ctl_dir / "workspace.img"
            make_workspace(source_root / f"{tid}.tar", ctl_dir / "seed_temp", ws, uid=os.getuid(), gid=os.getgid())
            eval_dir = ctl_dir / "evaluator"
            result = run_control_or_grade(mode=mode, task=public_task, evaluation=evaluation, image=image,
                workspace_image=ws, eval_dir=eval_dir, output_dir=ctl_dir, apptainer=apptainer,
                expected_image_head=batch["task_image_heads"][tid])
            result["task_id"] = tid
            batch["controls"].append(result)
            ws.unlink()
            _atomic_json(run_root / "batch_summary.json", batch)
            if not result.get("accepted"):
                batch["status"] = "BLOCKED_CONTROLS"
                batch["error"] = f"{mode} control failed for {tid}; no model weights loaded"
                _atomic_json(run_root / "batch_summary.json", batch)
                return batch

    # Only controls-qualified cohort may download/load the pair and generate.
    batch["status"] = "CONTROLS_QUALIFIED"
    batch["storage_before_model_assets"] = require_disk_floor(run_root, 80 * (1 << 30))
    _atomic_json(run_root / "batch_summary.json", batch)
    model_root = run_root / "models"; model_root.mkdir(mode=0o700)
    download_model_assets(release, model_root, run_root / "model_asset_receipt.json")
    models, tokenizer, load_receipt = _load_models(release, model_root, run_root)
    batch["models_loaded"] = True; batch["model_loads"] = load_receipt["loads"]
    batch["model_memory_after_both"] = load_receipt["after_both_models"]
    _atomic_json(run_root / "batch_summary.json", batch)

    import torch
    run_root_episodes = run_root / "episodes"; run_root_episodes.mkdir(mode=0o700)
    first_models = ["Qwen/Qwen2.5-Coder-7B-Instruct"] * 4 + ["Qwen/Qwen2.5-Coder-14B-Instruct"] * 4
    ordered = sorted(release["tasks"], key=lambda t: (hashlib.sha256(
        b"DTR-REQ030AG-balanced-order-v1" + t["instance_id"].encode()).digest(), t["instance_id"]))
    first_by_id = {task["instance_id"]: first for task, first in zip(ordered, first_models, strict=True)}
    order_manifest = {"algorithm": "sha256-ranked task ids; first four rank 7B, next four rank 14B",
                      "task_order": [t["instance_id"] for t in ordered], "first_model": first_by_id}
    batch["paired_order"] = order_manifest
    _atomic_json(run_root / "batch_summary.json", batch)
    stop_reason = None
    for rank, task in enumerate(release["tasks"], 1):
        tid = task["instance_id"]
        image = Path(images[tid]["path"])
        first = first_by_id[tid]
        second = "Qwen/Qwen2.5-Coder-14B-Instruct" if first.endswith("7B-Instruct") else "Qwen/Qwen2.5-Coder-7B-Instruct"
        for model_id in (first, second):
            model_info = next(m for m in release["models"]["models"] if m["repo"] == model_id)
            ep_dir = run_root_episodes / tid / model_id.rsplit("/", 1)[-1]
            ep_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
            batch["model_episode_started"] = True
            _atomic_json(run_root / "batch_summary.json", batch)
            try:
                episode_started = time.monotonic()
                episode = launch_agent_episode(model_id=model_id, model_info=model_info,
                    model=models[model_id], tokenizer=tokenizer,
                    task={"instance_id": tid, "base_commit": task["base_commit"]}, release=release,
                    bundle=bundle, model_run_dir=ep_dir / "agent", image=image,
                    source_tar=source_root / f"{tid}.tar", workspace_image=ep_dir / "workspace.img", apptainer=apptainer,
                    release_sha256=batch["release_sha256"], event_parent=ep_dir,
                    expected_image_head=batch["task_image_heads"][tid])
                if episode["submission_eligible"]:
                    evaluation = json.loads((bundle / "evaluator" / f"{tid}.json").read_bytes())
                    public_task = json.loads((bundle / "public" / f"{tid}.json").read_bytes())
                    patch_data = (ep_dir / "patch.diff").read_bytes()
                    grade_dir = ep_dir / "grade"; grade_dir.mkdir(mode=0o700)
                    ws = grade_dir / "workspace.img"
                    try:
                        make_workspace(source_root / f"{tid}.tar", grade_dir / "seed_temp", ws,
                                       uid=os.getuid(), gid=os.getgid())
                        grade = run_control_or_grade(mode="agent", task=public_task, evaluation=evaluation,
                            image=image, workspace_image=ws, eval_dir=grade_dir / "evaluator", output_dir=grade_dir,
                            apptainer=apptainer, expected_image_head=batch["task_image_heads"][tid],
                            patch_bytes=patch_data)
                    finally:
                        if ws.exists():
                            ws.unlink()
                    episode["grade"] = grade
                episode["episode_wall_seconds"] = time.monotonic() - episode_started
                torch.cuda.synchronize()
                episode["peak_allocated_bytes"] = torch.cuda.max_memory_allocated()
                episode["peak_reserved_bytes"] = torch.cuda.max_memory_reserved()
            except Exception as exc:
                events_path = ep_dir / "agent" / "events.jsonl"
                raw_events = [json.loads(line) for line in events_path.read_text().splitlines() if line] if events_path.is_file() else []
                requests = [event for event in raw_events if event.get("event") == "request"]
                responses = [event for event in raw_events if event.get("event") == "response"]
                episode = {"task_id": tid, "model_id": model_id,
                           "model_revision": model_info["revision"], "status": "episode_error",
                           "outcome_source": "infrastructure_or_supervision", "error_type": type(exc).__name__,
                           "error": str(exc)[:2000], "physical_calls_attempted": len(requests),
                           "physical_responses": len(responses), "input_tokens": sum(e.get("input_tokens", 0) for e in requests),
                           "output_tokens": sum(e.get("output_tokens", 0) for e in responses),
                           "event_log_sha256": sha_file(events_path) if events_path.is_file() else None}
                try:
                    torch.cuda.synchronize()
                    episode["peak_allocated_bytes"] = torch.cuda.max_memory_allocated()
                    episode["peak_reserved_bytes"] = torch.cuda.max_memory_reserved()
                except Exception:
                    pass
                if is_cuda_oom(exc):
                    stop_reason = "CUDA_OUT_OF_MEMORY"
            batch["episodes"].append(episode)
            _atomic_json(run_root / "batch_summary.json", batch)
            if stop_reason:
                break
        if stop_reason:
            break
    if stop_reason:
        observed = {(e["task_id"], e["model_id"]) for e in batch["episodes"]}
        for task in release["tasks"]:
            for model_id in ("Qwen/Qwen2.5-Coder-7B-Instruct", "Qwen/Qwen2.5-Coder-14B-Instruct"):
                if (task["instance_id"], model_id) not in observed:
                    batch["episodes"].append({"task_id": task["instance_id"], "model_id": model_id,
                        "status": "not_attempted_after_capacity_stop", "outcome_source": "capacity",
                        "grade": {"graded": False, "resolved": None}, "stop_reason": stop_reason})
        batch["capacity_stop"] = stop_reason
    planned_task_ids = [task["instance_id"] for task in release["tasks"]]
    model_ids = ("Qwen/Qwen2.5-Coder-7B-Instruct", "Qwen/Qwen2.5-Coder-14B-Instruct")
    batch["status"], batch["competence_screen"] = completion_status(
        batch["episodes"], planned_task_ids, model_ids, stop_reason)
    batch["finished_epoch"] = time.time()
    batch["outcome_counts"] = {
        "resolved": sum(bool(e.get("grade", {}).get("resolved")) for e in batch["episodes"]),
        "unresolved": sum(e.get("grade", {}).get("graded") is True and e.get("grade", {}).get("resolved") is False for e in batch["episodes"]),
        "unknown_or_ungraded": sum(e.get("grade", {}).get("graded") is not True for e in batch["episodes"]),
    }
    model_root = run_root / "models"
    shutil.rmtree(model_root)
    shutil.rmtree(run_root / "hf-cache", ignore_errors=True)
    batch["model_assets_cleanup"] = {"model_root_removed": not model_root.exists(),
                                     "hf_cache_removed": not (run_root / "hf-cache").exists()}
    _atomic_json(run_root / "batch_summary.json", batch)
    return batch


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--release", required=True)
    parser.add_argument("--release-sha256", required=True)
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--wheel-manifest", required=True)
    parser.add_argument("--wheel-root", required=True)
    parser.add_argument("--reuse-image-root")
    args = parser.parse_args()
    try:
        result = execute_batch(args)
        return 0 if result["status"] == "COMPLETED" else 2
    except Exception as exc:
        run_root = Path(args.run_root)
        if run_root.exists():
            path = run_root / "batch_summary.json"
            current = json.loads(path.read_bytes()) if path.exists() else {"request": "DTR-REQ-030AG"}
            current.update(status="FAILED", error_type=type(exc).__name__, error=str(exc)[:2000],
                           failure_evidence=getattr(exc, "evidence", None), finished_epoch=time.time())
            try:
                model_root = run_root / "models"
                if model_root.exists():
                    shutil.rmtree(model_root)
                hf_cache = run_root / "hf-cache"
                if hf_cache.exists():
                    shutil.rmtree(hf_cache)
                current["model_assets_cleanup"] = {"model_root_removed": not model_root.exists(),
                                                   "hf_cache_removed": not hf_cache.exists()}
                if path.exists():
                    _atomic_json(path, current)
                _atomic_json(run_root / "failure.json", current)
            except Exception:
                pass
        print(json.dumps({"status": "FAILED", "error_type": type(exc).__name__, "error": str(exc)[:2000]}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
