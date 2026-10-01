"""Six-hour, controls-first parallel DEVELOPMENT cohort.

One independently bounded allocation owns every assigned cell. The coordinator
never imports Torch: only a fresh, one-visible-GPU AI worker loads the frozen
pair. All eight normalized source contracts and all sixteen control arms must
pass before any cell is dispatched. Every untouched/failed cell stays in the
32-cell denominator. This is not randomized logging, H/P validation or CONFIRM.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time
import traceback

from experiments.lead_req030 import req030aj_cohort as aj
from experiments.lead_req030 import req030ag_screen as sandbox
from experiments.lead_req030 import req030ai_episode_worker as worker
from experiments.lead_req030 import req030ah_controls as controls
from experiments.lead_req030 import req030ai_candidate_grade as grader
from experiments.lead_req030 import req030aj_official_grade as official

ROOT = aj.ROOT
SCHEMA = "dtr.req030al.cohort.v1"
REQUEST = "DTR-REQ-030AL"
MODULE = "experiments.lead_req030.req030al_cohort"
ENVIRONMENT_REL = "experiments/lead_req030/req030al_environment.py"
MODEL_ASSETS_REL = "configs/req030ag_model_assets_20260929.json"
REQUIRED_SOURCES = tuple(dict.fromkeys((*aj.REQUIRED_SOURCES,
    "experiments/lead_req030/req030al_cohort.py", ENVIRONMENT_REL,
    "experiments/lead_req030/req030al_replay.py", "configs/req030ak_controls_20260930.json", MODEL_ASSETS_REL, "experiments/lead_req030/source_history_audit.py")))
GOAL_SECONDS = 21600
MAX_GPU = 32
SOURCE_NORMALIZATION = "restore every tracked source path and Git HEAD to exact public base; preserve read-only installed SIF dependencies"
APPTAINER_VERSION = "1.5.3-1.el9"


def retain_error(path: Path) -> None:
    """Private bounded diagnostic; never publish exception task/source contents."""
    data = traceback.format_exc().encode("utf-8", "replace")[:worker.MAX_STDOUT]
    # CalledProcessError's traceback omits captured stderr; retaining that
    # diagnostic distinguishes corrupt objects from historical Git formatting.
    error = sys.exc_info()[1]
    captured = getattr(error, "stderr", None)
    if captured:
        detail = captured if isinstance(captured, bytes) else str(captured).encode("utf-8", "replace")
        data = (data + b"\nCAPTURED_STDERR\n" + detail)[:worker.MAX_STDOUT]
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(data); out.flush(); os.fsync(out.fileno())


def observe_apptainer(pin: dict) -> dict:
    """Bounded fixed binary metadata on compute; never called by load_release."""
    path = Path(pin["path"])
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError("ordinary absolute Apptainer binary required")
    observed = {"path": str(path), "expected_sha256": pin["sha256"],
        "observed_sha256": worker.digest_file(path), "version": None}
    try:
        completed = subprocess.run([str(path), "--version"], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10, check=False)
        if len(completed.stdout) > 4096: raise ValueError("Apptainer version output exceeds diagnostic cap")
        observed.update(returncode=completed.returncode, version=completed.stdout.decode("utf-8", "replace").strip())
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        observed.update(returncode=None, version_diagnostic_error=type(exc).__name__)
    return observed


def startup_preflight(release_path: Path, expected_sha: str, output: Path) -> tuple[dict, dict]:
    """Persist admission failure before cohort output exists; no inference starts."""
    output = output.absolute()
    phase = "release_validation"; observed = None
    try:
        if "torch" in sys.modules: raise RuntimeError("parent must not import CUDA")
        release, admission = load_release(release_path, expected_sha)
        phase = "apptainer_identity"
        observed = observe_apptainer(release["apptainer"])
        if (observed["observed_sha256"] != release["apptainer"]["sha256"]
                or observed["returncode"] != 0 or observed["version"] != "apptainer version " + APPTAINER_VERSION):
            raise ValueError("exact compute Apptainer identity/version required")
        phase = "author_deadline"
        remaining = min(release["limits"]["batch_seconds"], release["goal"]["deadline_epoch"] - time.time())
        if remaining <= 45: raise RuntimeError("original author deadline exhausted before allocation admission")
        phase = "disk_floor"
        sandbox.require_disk_floor(output.parent, release["limits"]["min_free_bytes"])
        return release, admission
    except BaseException as exc:
        error_type = type(exc).__name__
        diagnostic = {"schema": "dtr.req030al.startup_failure.v1", "status": "PRE_ADMISSION_FAILED",
            "phase": phase, "error_type": error_type, "release_sha256": expected_sha,
            "actual_job_id": os.environ.get("SLURM_JOB_ID"), "model_calls": 0, "controls_started": 0,
            "cohort_seeded": False, "assigned_slots": 32, "task_families": 8,
            "apptainer": observed, "expected_apptainer_version": APPTAINER_VERSION}
        # Only inspect an exact hash-bound authored release. Failed input hashes
        # cannot supply an executable path, even for private diagnostics.
        if observed is None:
            try:
                _, raw = aj.read_pin({"path": str(release_path.absolute()), "sha256": expected_sha}, aj.MAX_JSON)
                exact = worker.parse_json(raw)
                diagnostic["apptainer"] = observe_apptainer(exact["apptainer"])
            except (ValueError, OSError, KeyError, subprocess.SubprocessError) as secondary:
                diagnostic["apptainer_diagnostic_error"] = type(secondary).__name__
        # Preserve the original traceback in a separate private bounded file.
        # No exception contents, public issue or evaluator bytes are in JSON.
        retain_error(output.parent / (output.name + ".startup_error.txt"))
        worker.write_new(output.parent / (output.name + ".startup_failure.json"), diagnostic)
        raise


def load_release(path: Path, expected_sha: str) -> tuple[dict, dict]:
    """Validate the complete pre-outcome outer release before creating output."""
    _, raw = aj.read_pin({"path": str(path.absolute()), "sha256": expected_sha}, aj.MAX_JSON)
    release = worker.parse_json(raw)
    required = {"schema", "request", "release_id", "phase", "model_execution_authorized",
        "control_release", "models", "runtime", "resource_cap", "limits", "source_pins",
        "model_root", "apptainer", "tasks", "order", "token_contract", "cached_task_assets", "goal"}
    if (not isinstance(release, dict) or set(release) != required or release["schema"] != SCHEMA
            or release["request"] != REQUEST or release["phase"] != "DEVELOPMENT"
            or release["model_execution_authorized"] is not True
            or release["order"] != aj.frozen_order(release["release_id"])
            or release["token_contract"] != aj.TOKEN_CONTRACT):
        raise ValueError("complete exact prospective AL model release required")
    goal = release["goal"]
    window = 172800 if release["release_id"] == "req030al-ongoing-20261001-d" else GOAL_SECONDS
    if (not isinstance(goal, dict) or set(goal) != {"started_epoch", "deadline_epoch", "max_iterations", "iteration"}
            or any(type(goal[k]) not in (int, float) or not math.isfinite(goal[k]) for k in ("started_epoch", "deadline_epoch"))
            or goal["deadline_epoch"] - goal["started_epoch"] != window
            or goal["max_iterations"] != 3 or type(goal["iteration"]) is not int or not 1 <= goal["iteration"] <= 3):
        raise ValueError("exact prospective queue-inclusive window required")
    limits = release["limits"]
    if (not isinstance(limits, dict) or set(limits) != {"batch_seconds", "storage_bytes", "min_free_bytes", "grade_seconds", "slot_reservation_seconds"}
            or limits["grade_seconds"] != 900 or limits["slot_reservation_seconds"] != aj.SLOT_RESERVATION_SECONDS
            or type(limits["batch_seconds"]) is not int or not 0 < limits["batch_seconds"] <= GOAL_SECONDS
            or any(type(limits[k]) is not int or limits[k] <= 0 for k in ("storage_bytes", "min_free_bytes"))):
        raise ValueError("unchanged complete cell reservation and bounded joint limits required")
    resource = release["resource_cap"]
    if (not isinstance(resource, dict) or set(resource) != {"gpu_model", "gpu_count", "cpu", "memory_bytes", "slurm_seconds"}
            or not isinstance(resource["gpu_model"], str) or not resource["gpu_model"]
            or type(resource["gpu_count"]) is not int or not 1 <= resource["gpu_count"] <= MAX_GPU
            or any(type(resource[k]) is not int or resource[k] <= 0 for k in ("cpu", "memory_bytes", "slurm_seconds"))
            or resource["slurm_seconds"] < limits["batch_seconds"] + 45):
        raise ValueError("complete adequate GPU allocation envelope required")
    if set(release["source_pins"]) != set(REQUIRED_SOURCES):
        raise ValueError("all coordinator, source, guardian, model and evaluator sources required")
    for rel, digest in release["source_pins"].items():
        if not worker._hex(digest) or worker.digest_file(ROOT / rel) != digest:
            raise ValueError(f"executable source pin differs: {rel}")
    _, control_raw = aj.read_pin(release["control_release"], aj.MAX_JSON)
    original = worker.parse_json(control_raw)
    if (original.get("request") != "DTR-REQ-030AK" or original.get("model_execution_authorized") is not False
            or tuple(t.get("instance_id") for t in original.get("tasks", [])) != controls.TASK_IDS):
        raise ValueError("exact prior unexposed eight-task control release required")
    if (not isinstance(release["tasks"], list) or len(release["tasks"]) != 8
            or tuple(t.get("instance_id") for t in release["tasks"]) != controls.TASK_IDS
            or not isinstance(release["cached_task_assets"], list) or len(release["cached_task_assets"]) != 8
            or tuple(t.get("task_id") for t in release["cached_task_assets"]) != controls.TASK_IDS):
        raise ValueError("all eight original tasks and cached assets must remain")
    inputs = {}
    for task, orig, assets in zip(release["tasks"], original["tasks"], release["cached_task_assets"], strict=True):
        if (set(task) != {"instance_id", "repo", "base_commit", "public_projection", "evaluator_bundle"}
                or any(task[k] != orig[k] for k in ("instance_id", "repo", "base_commit"))
                or task["repo"] != grader.TASK_REPOS[task["instance_id"]]
                or set(assets) != {"task_id", "image", "source_tar"}):
            raise ValueError("frozen task/family/source identity differs")
        _, public_raw = aj.read_pin(task["public_projection"], 4 << 20)
        public = worker.parse_json(public_raw)
        if (set(public) != {"instance_id", "repo", "base_commit", "problem_statement"}
                or any(public[k] != task[k] for k in ("instance_id", "repo", "base_commit"))
                or not isinstance(public["problem_statement"], str) or not public["problem_statement"].strip()
                or aj.sha(public_raw) != orig["public_projection_sha256"] or len(public_raw) != orig["public_projection_bytes"]):
            raise ValueError("public-only projection binding differs")
        _, evraw = aj.read_pin(task["evaluator_bundle"], grader.MAX_EVALUATOR_BYTES)
        evaluation = grader.parse_unique(evraw)
        if (aj.sha(evraw) != orig["evaluator_bundle_sha256"] or len(evraw) != orig["evaluator_bundle_bytes"]
                or any(evaluation[k] != task[k] for k in ("instance_id", "base_commit"))
                or any(aj.sha(evaluation[k].encode()) != orig[k + "_sha256"] for k in ("stock_eval_script", "reference_patch"))
                or len(evaluation["fail_to_pass"]) != orig["fail_to_pass_count"]
                or len(evaluation["pass_to_pass"]) != orig["pass_to_pass_count"]):
            raise ValueError("private evaluator binding differs")
        inputs[task["instance_id"]] = {"task": task, "assets": assets, "evaluation": evaluation, "evaluator_raw": evraw}
    if (not isinstance(release["models"], dict) or set(release["models"]) != {"models"}
            or len(release["models"]["models"]) != 2
            or {(m.get("repo"), m.get("revision")) for m in release["models"]["models"]}
            != {(m["repo"], m["revision"]) for m in aj.MODEL_PINS.values()}):
        raise ValueError("same prospectively frozen real HF/BF16 pair required")
    frozen_assets = aj.read_json(ROOT / MODEL_ASSETS_REL)
    frozen_models = [{k: m[k] for k in ("repo", "revision", "files")} for m in frozen_assets["models"]]
    if (release["models"]["models"] != frozen_models
            or any(m["total_bytes"] != sum(a["bytes"] for a in m["files"]) for m in frozen_assets["models"])):
        raise ValueError("full exact original AG model asset manifest required; no partial/adaptive weights")
    for model in release["models"]["models"]:
        if set(model) != {"repo", "revision", "files"} or not isinstance(model["files"], list) or not model["files"]:
            raise ValueError("complete model asset pins required")
        seen = set()
        for asset in model["files"]:
            candidate = Path(asset.get("path", ""))
            if (set(asset) != {"path", "sha256", "bytes"} or not asset["path"] or candidate.is_absolute()
                    or ".." in candidate.parts or asset["path"] in seen or not worker._hex(asset["sha256"])
                    or type(asset["bytes"]) is not int or asset["bytes"] <= 0):
                raise ValueError("unsafe or duplicate exact model asset pin")
            seen.add(asset["path"])
    runtime = release["runtime"]
    if (not isinstance(runtime, dict) or set(runtime) - {"gpu_model_aliases", "versions", "cuda", "python"}
            or runtime.get("cuda") != "12.8" or set(runtime.get("versions", {})) != worker.RUNTIME_PACKAGES
            or runtime["versions"].get("torch") != "2.9.1" or runtime["versions"].get("transformers") != "4.51.3"
            or not isinstance(runtime.get("python"), str) or re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", runtime["python"]) is None):
        raise ValueError("complete unchanged HF runtime required")
    apptainer = worker._pin(release["apptainer"])
    model_root = Path(release["model_root"])
    if not model_root.is_absolute() or model_root.is_symlink() or not model_root.is_dir():
        raise ValueError("cached owned model root required")
    return release, {"release_sha256": aj.sha(raw), "release_path": str(path.absolute()), "original": original,
        "control_raw": control_raw, "tasks": inputs, "apptainer": apptainer, "model_root": model_root}


def goal_remaining(release: dict, *, started_monotonic: float, now_monotonic=None, now_epoch=None) -> float:
    """Both monotonic allocation and original author wall-clock deadline apply."""
    mono = time.monotonic() if now_monotonic is None else now_monotonic
    epoch = time.time() if now_epoch is None else now_epoch
    return max(0.0, min(release["limits"]["batch_seconds"] - (mono - started_monotonic),
                        release["goal"]["deadline_epoch"] - epoch))


def seed(release: dict, admission: dict, output: Path) -> dict:
    summary = aj.seed_cohort(release, admission, output)
    summary.update(schema=SCHEMA, status="QUALIFYING", all_controls_accepted=False,
        source_review_accepted=False, qualification=None, qualification_directory=str(output / "qualification"),
        goal=copy.deepcopy(release["goal"]), resource_cap=copy.deepcopy(release["resource_cap"]),
        model_execution_started=False, cell_worker_dispatched=False, control_arms_assigned=16,
        real_model_worker_started_meaning="fresh cell coordinator dispatched; require native requests/model_ready for actual inference",
        interpretation="Eight task families /32 dependent schedule cells; no randomized H/P or causal effectiveness claim")
    sandbox._atomic_json(output / "summary.json", summary)
    return summary


def execute_control(item: dict, *, source: Path, image: Path, directory: Path, apptainer: str, mode: str) -> dict:
    from experiments.lead_req030 import req030al_environment as environment
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    workspace = directory / "workspace.img"
    clean = False
    try:
        sandbox.make_workspace(source, directory / "seed_temp", workspace, uid=os.getuid(), gid=os.getgid())
        evdir = directory / "evaluator"; evdir.mkdir(mode=0o700)
        if mode == "reference":
            (evdir / "reference.diff").write_bytes(item["evaluation"]["reference_patch"].encode())
            (evdir / "reference.diff").chmod(0o400)
        environment.evaluation_wrapper(evdir / "run.sh", item["evaluation"], mode=mode,
            expected_base_commit=item["task"]["base_commit"])
        raw, supervisor = sandbox.run_supervised(apptainer, image, workspace, ["/bin/bash", "/eval/run.sh"],
            output_path=directory / (mode + ".out"), receipt_path=directory / (mode + ".supervisor.json"),
            seconds=900, extra_binds=["--bind", f"{evdir.resolve()}:/eval:ro", *environment.hosts_binds(directory),
                *environment.container_environment_args()])
        clean = aj.supervisor_clean(supervisor)
        result = controls.assess(raw, supervisor, item["evaluation"], mode, controls.pinned_parsers()[item["task"]["repo"]])
        stages = environment.assess_stages(raw, supervisor, task_id=item["task"]["instance_id"])
        result.update(cleanup_verified=clean, stage_acceptance=stages)
        result["accepted"] = result["accepted"] is True and stages.get("accepted") is True
        worker.write_new(directory / "assessment.json", result)
        return {"raw": aj.file_pin(directory / (mode + ".out")),
            "supervisor": aj.file_pin(directory / (mode + ".supervisor.json")), "accepted": result["accepted"], "cleanup_verified": clean,
            "runtime": stages.get("runtime"), "runtime_sha256": aj.sha(aj.canonical(stages["runtime"])) if stages.get("runtime") is not None else None}
    finally:
        if clean:
            if workspace.exists(): workspace.unlink()
            if (directory / "seed_temp").exists(): shutil.rmtree(directory / "seed_temp")


def qualify(release: dict, admission: dict, output: Path, *, task_qualifier=None, runtime_verifier=None, asset_verifier=None) -> dict:
    """Coherent all-source/all-control/runtime gate; no model load/import."""
    from experiments.lead_req030 import req030al_environment as environment
    if "torch" in sys.modules:
        raise RuntimeError("qualification coordinator cannot import Torch")
    directory = output / "qualification"; directory.mkdir(mode=0o700)
    runtime_verifier = worker.verify_declared_worker_runtime if runtime_verifier is None else runtime_verifier
    asset_verifier = sandbox.validate_model_assets if asset_verifier is None else asset_verifier
    receipt = {"schema": "dtr.req030al.qualification.v1", "all_controls_accepted": False,
        "source_review_accepted": False, "runtime_accepted": False, "model_calls": 0,
        "source_normalization": SOURCE_NORMALIZATION, "tasks": [], "error": None}
    worker.write_new(directory / "assignment.json", {"tasks": list(controls.TASK_IDS), "control_modes": ["baseline", "reference"],
        "release_sha256": admission["release_sha256"], "model_calls_before_gate": 0})
    try:
        receipt["runtime"] = runtime_verifier(release["runtime"])
        if asset_verifier is sandbox.validate_model_assets:
            receipt["gpu_runtime"] = qualify_gpu_runtimes(release, admission, output)
            receipt["asset_acquisition"] = acquire_assets(release, admission, output)
        receipt["model_assets"] = asset_verifier(release, admission["model_root"])
        receipt["runtime_accepted"] = True
    except BaseException as exc:
        receipt["error"] = "runtime_or_asset_gate:" + type(exc).__name__
        retain_error(directory / "qualification_error.txt")
        worker.write_new(directory / "qualification.json", receipt)
        return receipt

    def task_work(tid):
        if task_qualifier is not None:
            return task_qualifier(tid, release, admission, directory)
        item = admission["tasks"][tid]
        taskdir = directory / tid; taskdir.mkdir(mode=0o700)
        answer = {"task_id": tid, "accepted": False, "source_accepted": False,
            "controls": {mode: {"accepted": False, "status": "NOT_ATTEMPTED", "cleanup_verified": None}
                for mode in ("baseline", "reference")}, "error": None}
        try:
            image = worker._pin(item["assets"]["image"], cap=8 << 30)
            original = worker._pin(item["assets"]["source_tar"], cap=sandbox.MAX_SOURCE_TAR)
            source = taskdir / "normalized_source.tar"
            source_receipt = environment.prepare_source_archive(original, source,
                base_commit=item["task"]["base_commit"], task_id=tid)
            worker.write_new(taskdir / "source_normalization.json", source_receipt)
            # The environment must independently replay base HEAD/tree. Model
            # source never includes evaluator patches or setup child deltas.
            if (source_receipt.get("accepted") is not True or source_receipt.get("head") != item["task"]["base_commit"]
                    or source_receipt.get("tree") != source_receipt.get("base_tree")
                    or not worker._hex(source_receipt.get("tree"), 40)):
                raise ValueError("normalized source is not exact base tree")
            review = {"schema": "dtr.req030aj.source_acceptance.v1", "task_id": tid,
                "image_sha256": item["assets"]["image"]["sha256"], "source_tar_sha256": worker.digest_file(source),
                "head": source_receipt["head"], "tree": source_receipt["tree"], "base_tree": source_receipt["base_tree"],
                "accepted": True, "model_tree_contract": "equal_tree"}
            worker.write_new(taskdir / "source_acceptance.json", review)
            from experiments.lead_req030 import source_history_audit
            proof = source_history_audit.audit_task(task_id=tid, base_commit=item["task"]["base_commit"],
                normalized_archive=source, original_archive=original,
                normalization_receipt=taskdir / "source_normalization.json",
                acceptance_receipt=taskdir / "source_acceptance.json",
                expected_original_sha256=item["assets"]["source_tar"]["sha256"])
            worker.write_new(taskdir / "independent_source_history.json", proof)
            if proof.get("accepted") is not True:
                raise ValueError("independent full source proof refused")
            answer.update(source_accepted=True, image=item["assets"]["image"], source_tar=aj.file_pin(source),
                source_acceptance=aj.file_pin(taskdir / "source_acceptance.json"))
            for mode in ("baseline", "reference"):
                answer["controls"][mode]["status"] = "RUNNING"
                answer["controls"][mode] = execute_control(item, source=source, image=image,
                    directory=taskdir / mode, apptainer=str(admission["apptainer"]), mode=mode)
                answer["controls"][mode]["status"] = "COMPLETED"
                if answer["controls"][mode]["cleanup_verified"] is not True:
                    raise RuntimeError("qualification process cleanup unknown")
            runtimes = [answer["controls"][mode].get("runtime_sha256") for mode in ("baseline", "reference")]
            answer["installed_runtime_identical_between_arms"] = all(worker._hex(value) for value in runtimes) and runtimes[0] == runtimes[1]
            answer["accepted"] = (all(arm["accepted"] is True for arm in answer["controls"].values())
                and answer["installed_runtime_identical_between_arms"])
        except BaseException as exc:
            answer["error"] = type(exc).__name__
            retain_error(taskdir / "task_qualification_error.txt")
            for arm in answer["controls"].values():
                if arm.get("status") == "RUNNING": arm.update(status="INFRASTRUCTURE_UNKNOWN", reason=type(exc).__name__)
        worker.write_new(taskdir / "task_qualification.json", answer)
        return answer

    # One task per allotted GPU worker; CPU controls use no GPU. Capped by the
    # exact allocation, so source/control work cannot expand scheduler demand.
    results = {}
    with ThreadPoolExecutor(max_workers=min(8, release["resource_cap"]["gpu_count"])) as pool:
        pending = {pool.submit(task_work, tid): tid for tid in controls.TASK_IDS}
        for future in as_completed(pending):
            tid = pending[future]
            try: results[tid] = future.result()
            except BaseException as exc:
                results[tid] = {"task_id": tid, "accepted": False, "source_accepted": False, "controls": {}, "error": type(exc).__name__}
            receipt["tasks"] = [results[t] for t in controls.TASK_IDS if t in results]
            sandbox._atomic_json(directory / "qualification_progress.json", receipt)
    receipt["tasks"] = [results[t] for t in controls.TASK_IDS]
    receipt["source_review_accepted"] = all(t.get("source_accepted") is True for t in receipt["tasks"])
    receipt["all_controls_accepted"] = all(t.get("accepted") is True and set(t.get("controls", {})) == {"baseline", "reference"}
        and all(a.get("accepted") is True and a.get("cleanup_verified") is True for a in t["controls"].values()) for t in receipt["tasks"])
    worker.write_new(directory / "qualification.json", receipt)
    return receipt


def create_worker_admission(release: dict, admission: dict, qualification: dict, output: Path) -> tuple[Path, str]:
    """Fresh immutable AJ admission within this AL allocation; no new treatment."""
    if not all(qualification.get(k) is True for k in ("all_controls_accepted", "source_review_accepted", "runtime_accepted")):
        raise ValueError("no model admission before every gate passes")
    from experiments.lead_req030 import req030al_replay as replay
    independent = []
    for task in qualification["tasks"]:
        tid = task["task_id"]
        original = admission["tasks"][tid]
        for mode in ("baseline", "reference"):
            arm = task["controls"][mode]
            _, raw = aj.read_pin(arm["raw"], sandbox.MAX_EPISODE_OUTPUT)
            _, supraw = aj.read_pin(arm["supervisor"], aj.MAX_JSON)
            independent.append(replay.replay_control_artifacts(task_id=tid, repo=original["task"]["repo"],
                evaluation=original["evaluation"], raw=raw, supervisor=worker.parse_json(supraw), mode=mode))
    independent_summary = replay.summarize_control_replays(independent)
    worker.write_new(output / "independent_control_replay.json", {"summary": independent_summary, "arms": independent})
    if independent_summary["all_controls_accepted"] is not True:
        raise ValueError("independent complete runtime/control replay rejects model admission")
    tasks = []
    for task in qualification["tasks"]:
        tasks.append({"task_id": task["task_id"], "image": task["image"], "source_tar": task["source_tar"],
            "source_acceptance": task["source_acceptance"], "controls": {mode: {k: arm[k] for k in ("raw", "supervisor")}
                for mode, arm in task["controls"].items()}})
    acceptance = {"schema": "dtr.req030aj.control_acceptance.v1", "control_release_sha256": aj.sha(admission["control_raw"]),
        "all_controls_accepted": True, "source_review_accepted": True, "tasks": tasks}
    worker.write_new(output / "control_acceptance.json", acceptance)
    inner = {k: copy.deepcopy(release[k]) for k in ("release_id", "phase", "model_execution_authorized", "control_release",
        "models", "runtime", "resource_cap", "limits", "source_pins", "model_root", "apptainer", "tasks", "order", "token_contract")}
    inner.update(schema=aj.SCHEMA, request="DTR-REQ-030AJ", control_acceptance=aj.file_pin(output / "control_acceptance.json"))
    inner["resource_cap"]["gpu_count"] = 1  # Exact scope of one fresh isolated cell, not allocation size.
    inner["source_pins"] = {key: release["source_pins"][key] for key in aj.REQUIRED_SOURCES}
    path = output / "worker_admission_manifest.json"; worker.write_new(path, inner)
    digest = worker.digest_file(path)
    aj.validate_admission(path, digest)  # Independent exact raw control replay before any dispatch.
    return path, digest


def execute_grade(*, item, slot, episode_directory, directory, release_sha256, apptainer, seconds=900):
    """Same strict/upstream parsers; fixed offline evaluator execution variant."""
    from experiments.lead_req030 import req030al_environment as environment
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    patch = worker.read_private(episode_directory / "episode" / "patch.diff", grader.MAX_PATCH_BYTES)
    outcome = aj.read_json(episode_directory / "worker_result.json")
    if (outcome.get("agent_exit_status") != "Submitted" or outcome.get("submission_eligible") is not True
            or not patch or aj.sha(patch) != outcome.get("patch_sha256") or len(patch) != outcome.get("patch_bytes")):
        raise ValueError("exact eligible explicit submission required")
    task = item["task"]
    assignment = {"task_id": task["instance_id"], "repo": task["repo"], "base_commit": task["base_commit"],
        "policy_id": slot["schedule"], "invocation_id": slot["invocation_id"], "release_sha256": release_sha256,
        "evaluator_bundle_sha256": aj.sha(item["evaluator_raw"]), "patch_sha256": aj.sha(patch), "parser_sha256": grader.PARSER_SHA256}
    worker.write_new(directory / "assignment.json", assignment)
    marker = aj.INVOCATION_MARKER + aj.sha(aj.canonical(assignment))
    workspace = directory / "workspace.img"; clean = False
    result = {"cleanup_verified": False, "binding_verified": False, "grade": aj.unknown_grade("evaluation_not_finished"),
        "official_upstream_score": aj.official_score_missing()}
    try:
        sandbox.make_workspace(item["source"], directory / "seed_temp", workspace, uid=os.getuid(), gid=os.getgid())
        evdir = directory / "evaluator"; evdir.mkdir(mode=0o700)
        (evdir / "agent.diff").write_bytes(patch); (evdir / "agent.diff").chmod(0o400)
        environment.evaluation_wrapper(evdir / "run.sh", item["evaluation"], mode="agent",
            expected_base_commit=task["base_commit"], invocation_marker=marker)
        raw, supervisor = sandbox.run_supervised(apptainer, item["image"], workspace, ["/bin/bash", "/eval/run.sh"],
            output_path=directory / "candidate.out", receipt_path=directory / "candidate.supervisor.json",
            seconds=seconds, extra_binds=["--bind", f"{evdir.resolve()}:/eval:ro", *environment.hosts_binds(directory),
                *environment.container_environment_args()])
        clean = result["cleanup_verified"] = aj.supervisor_clean(supervisor)
        if raw.decode("utf-8", "replace").splitlines().count(marker) != 1:
            result["grade"] = aj.unknown_grade("evaluator_invocation_marker_missing_or_duplicated")
            return result
        binding = {**assignment, "raw_sha256": aj.sha(raw), "supervisor_sha256": aj.sha(grader.canonical(supervisor))}
        observed = {**aj.read_json(directory / "assignment.json"),
            "raw_sha256": aj.sha(worker.read_private(directory / "candidate.out", sandbox.MAX_EPISODE_OUTPUT)),
            "supervisor_sha256": aj.sha(grader.canonical(aj.read_json(directory / "candidate.supervisor.json")))}
        worker.write_new(directory / "binding.json", observed); result["binding_verified"] = binding == observed
        scoring = {k: task[k] for k in ("instance_id", "repo", "base_commit")} | {"evaluator_bundle_sha256": assignment["evaluator_bundle_sha256"]}
        result["environment_stages"] = environment.assess_stages(raw, supervisor, task_id=task["instance_id"])
        if result["environment_stages"].get("accepted") is not True:
            result["grade"] = aj.unknown_grade("fixed_environment_stage_failure")
            return result
        baseline = item["receipt"]["controls"]["baseline"]
        _, baseline_raw = aj.read_pin(baseline["raw"], sandbox.MAX_EPISODE_OUTPUT)
        _, baseline_supervisor = aj.read_pin(baseline["supervisor"], aj.MAX_JSON)
        baseline_stages = environment.assess_stages(baseline_raw, worker.parse_json(baseline_supervisor), task_id=task["instance_id"])
        if (baseline_stages.get("accepted") is not True
                or baseline_stages.get("runtime") != result["environment_stages"].get("runtime")):
            result["grade"] = aj.unknown_grade("installed_runtime_differs_from_control")
            return result
        result["grade"] = grader.replay_candidate(task=scoring, evaluator_bundle=item["evaluator_raw"], raw=raw,
            supervisor=supervisor, patch=patch, expected_patch_sha256=outcome["patch_sha256"], expected_binding=binding, observed_binding=observed)
        result["official_upstream_score"] = official.replay_official(task=scoring, evaluator_bundle=item["evaluator_raw"], raw=raw,
            patch=patch, expected_binding=binding, observed_binding=observed, strict_grade=result["grade"])
        worker.write_new(directory / "strict_grade.json", result["grade"])
        worker.write_new(directory / "official_report.json", result["official_upstream_score"])
        return result
    finally:
        if clean:
            if workspace.exists(): workspace.unlink()
            if (directory / "seed_temp").exists(): shutil.rmtree(directory / "seed_temp")


def run_cell(inner_path: Path, inner_sha: str, outer_sha: str, output: Path, period: int, *, episode_runner=None, grade_runner=None) -> dict:
    """One immutable assigned cell, no retry and no GPU sharing."""
    inner, admission = aj.validate_admission(inner_path, inner_sha)
    admission["release_sha256"] = outer_sha  # Native/evaluator identity binds actual AL prospective release.
    cell = copy.deepcopy(inner["order"][period - 1])
    cell.update(status="NOT_ATTEMPTED", assigned_slot_retained=True, grade=aj.unknown_grade("not_started"), infrastructure_unknown=False,
        official_upstream_score=aj.official_score_missing(), costs={"second_decision_eligible": None},
        episode_directory=None, grade_directory=None, cleanup_verified=None)
    episode_runner = worker.run_episode if episode_runner is None else episode_runner
    grade_runner = execute_grade if grade_runner is None else grade_runner
    directory = output / "episodes" / f"{period:02d}-{cell['task_id']}-{cell['schedule']}"
    result_path = output / "cells" / f"{period:02d}.json"
    cell.update(status="EPISODE_RUNNING", episode_directory=str(directory), cleanup_verified=False)
    sandbox._atomic_json(result_path, cell)
    try:
        guardian = episode_runner(aj.public_spec(inner, admission, cell["task_id"], cell["schedule"]), directory)
        cell["guardian"] = guardian
        cell["cleanup_verified"] = guardian.get("cleanup_verified") is True and guardian.get("worker_reaped") is True
        if guardian.get("abort_batch") is True or not cell["cleanup_verified"]:
            cell.update(status="CLEANUP_UNKNOWN", infrastructure_unknown=True, grade=aj.unknown_grade("worker_cleanup_unknown"))
        else:
            outcome = guardian.get("outcome") if guardian.get("status") == "episode_complete" else None
            cell["costs"] = aj.native_measurements(directory, cell["schedule"], outcome)
            if outcome is None:
                cell.update(status="EPISODE_UNKNOWN" if guardian.get("status") == "infrastructure_unknown" else "OPERATIONAL_STOP",
                    infrastructure_unknown=guardian.get("status") == "infrastructure_unknown", grade=aj.unknown_grade(guardian.get("reason", "missing_episode_outcome")))
            elif guardian.get("submission_eligible") is not True or outcome.get("submission_eligible") is not True or outcome.get("agent_exit_status") != "Submitted":
                cell.update(status="OPERATIONAL_STOP", agent_exit_status=outcome.get("agent_exit_status"), grade=aj.unknown_grade("no_explicit_eligible_submission"))
            else:
                grade_dir = output / "grades" / f"{period:02d}-{cell['task_id']}-{cell['schedule']}"
                cell.update(status="GRADE_RUNNING", grade_directory=str(grade_dir), agent_exit_status=outcome["agent_exit_status"])
                sandbox._atomic_json(result_path, cell)
                graded = grade_runner(item=admission["tasks"][cell["task_id"]], slot=cell, episode_directory=directory,
                    directory=grade_dir, release_sha256=outer_sha, apptainer=str(admission["apptainer"]), seconds=inner["limits"]["grade_seconds"])
                cell.update(grade_evidence=graded, official_upstream_score=graded.get("official_upstream_score", aj.official_score_missing()),
                    grade=graded.get("grade", aj.unknown_grade("grade_missing")))
                if graded.get("cleanup_verified") is not True:
                    cell.update(status="CLEANUP_UNKNOWN", infrastructure_unknown=True, cleanup_verified=False, grade=aj.unknown_grade("evaluation_cleanup_unknown"))
                else:
                    aj.validate_grade(cell["grade"])
                    cell.update(status="GRADED" if cell["grade"]["graded"] else "EVALUATION_UNKNOWN", infrastructure_unknown=not cell["grade"]["graded"])
    except BaseException as exc:
        clean = aj.cleanup_for_slot(cell)
        cell.update(status="INFRASTRUCTURE_UNKNOWN", infrastructure_unknown=True, cleanup_verified=clean,
            grade=aj.unknown_grade(type(exc).__name__), error_type=type(exc).__name__)
    sandbox._atomic_json(result_path, cell)
    return cell


def visible_gpu_tokens(count: int, value: str | None = None) -> list[str]:
    value = os.environ.get("CUDA_VISIBLE_DEVICES") if value is None else value
    if not isinstance(value, str): raise ValueError("Slurm must provide CUDA_VISIBLE_DEVICES")
    tokens = value.split(",")
    if len(tokens) != count or len(set(tokens)) != count or any(re.fullmatch(r"[A-Za-z0-9_-]+", t) is None for t in tokens):
        raise ValueError("allocated visible GPU tokens differ from exact frozen count")
    return tokens


def acquire_assets(release: dict, admission: dict, output: Path, *, popen=None, clock=None) -> dict:
    """One bounded shared acquisition; never one download per GPU/cell.

    File hashes and sizes are replayed after acquisition. A cache with every
    exact expected path/size is reused; a changed existing path is not silently
    repaired. The download child shares the CPU coordinator's process group,
    which the independent outer guardian owns. Its 900-second bound and 200GiB
    sampled cap also include download staging overhead.
    """
    root = admission["model_root"]
    expected = [(root / m["revision"] / a["path"], a) for m in release["models"]["models"] for a in m["files"]]
    if all(path.is_file() and not path.is_symlink() and path.stat().st_size == asset["bytes"] for path, asset in expected):
        return {"status": "retained_exact_size_cache_pending_hash_replay", "download_attempted": False,
            "expected_bytes": sum(asset["bytes"] for _, asset in expected)}
    if any(path.exists() for path, _ in expected):
        raise ValueError("partial model cache requires separate immutable correction; no silent weight overwrite")
    popen = subprocess.Popen if popen is None else popen
    clock = time.monotonic if clock is None else clock
    path = output / "qualification" / "model_acquisition.out"
    start = clock(); cap = min(200 << 30, release["limits"]["storage_bytes"])
    process = None; reason = "unknown"; peak = 0
    with path.open("xb") as log:
        try:
            process = popen([sys.executable, "-m", MODULE, "assets", "--release", admission["release_path"],
                "--release-sha256", admission["release_sha256"], "--output", str(output)],
                close_fds=True, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
            while process.poll() is None:
                used = controls.scoped_bytes(root); peak = max(peak, used)
                if used > cap: reason = "model_cache_storage_limit"; break
                if path.stat().st_size > worker.MAX_STDOUT: reason = "model_acquisition_output_limit"; break
                if clock() - start >= 900: reason = "model_acquisition_900s_deadline"; break
                time.sleep(.2)
            else:
                reason = "exited"
        finally:
            if process is not None and process.poll() is None:
                process.terminate()
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=3)
    receipt = {"schema": "dtr.req030al.model_acquisition.v1", "download_attempted": True, "reason": reason,
        "returncode": process.returncode if process else None, "reaped": process is not None and process.poll() is not None,
        "elapsed_seconds": clock() - start, "peak_observed_cache_bytes": peak, "cap_bytes": cap,
        "output_sha256": worker.digest_file(path), "output_bytes": path.stat().st_size,
        "expected_bytes": sum(asset["bytes"] for _, asset in expected)}
    worker.write_new(output / "qualification" / "model_acquisition_supervisor.json", receipt)
    if reason != "exited" or process.returncode != 0:
        raise RuntimeError("bounded shared model acquisition did not finish")
    return receipt


def qualification_cleanup(output: Path) -> bool:
    """Conservative receipt audit for non-model work owned by this allocation.

    AJ's model-slot cleanup cannot establish control/acquisition cleanup when
    every model slot is untouched. Any started qualification arm/process with
    missing or partial terminal evidence holds subsequent execution.
    """
    directory = output / "qualification"
    if not directory.exists(): return True
    try:
        for tid in controls.TASK_IDS:
            for mode in ("baseline", "reference"):
                arm = directory / tid / mode
                if not arm.exists(): continue
                if not aj.supervisor_clean(aj.read_json(arm / (mode + ".supervisor.json"))): return False
        acquisition = directory / "model_acquisition.out"
        if acquisition.exists():
            receipt = aj.read_json(directory / "model_acquisition_supervisor.json")
            if receipt.get("reaped") is not True or type(receipt.get("returncode")) is not int: return False
        for path in directory.glob("gpu_runtime_*.out"):
            receipt = aj.read_json(path.with_suffix(".supervisor.json"))
            if receipt.get("reaped") is not True or type(receipt.get("returncode")) is not int: return False
        return True
    except (ValueError, OSError):
        return False


def gpu_runtime_receipt(release: dict) -> dict:
    """Fresh one-GPU runtime/ABI gate; imports CUDA but loads no weights."""
    runtime = worker.verify_declared_worker_runtime(release["runtime"])
    import importlib
    import importlib.metadata
    harness_dependencies = {}
    for name, dist, module_name in (("pydantic", "pydantic", "pydantic"), ("PyYAML", "PyYAML", "yaml")):
        try:
            module = importlib.import_module(module_name)
            harness_dependencies[name] = {"version": importlib.metadata.version(dist), "origin": getattr(module, "__file__", None), "available": True}
        except (ImportError, importlib.metadata.PackageNotFoundError) as exc:
            harness_dependencies[name] = {"version": None, "origin": None, "available": False, "reason": type(exc).__name__}
    import numpy as np
    import torch
    if torch.version.cuda != "12.8" or not torch.cuda.is_available() or torch.cuda.device_count() != 1:
        raise RuntimeError("exact one-visible-device CUDA runtime required")
    name = torch.cuda.get_device_name(0)
    identity = sandbox.validate_gpu_device_name(name, release["resource_cap"]["gpu_model"], release["runtime"].get("gpu_model_aliases", []))
    if torch.from_numpy(np.asarray([1.0], dtype=np.float32)).tolist() != [1.0]:
        raise RuntimeError("NumPy/PyTorch ABI bridge failed")
    total = torch.cuda.get_device_properties(0).total_memory
    if total < 80 << 30: raise RuntimeError("GPU below prospectively required pair/context memory floor")
    return {"schema": "dtr.req030al.gpu_runtime.v1", "runtime": runtime, "cuda": torch.version.cuda,
        "device_identity": identity, "device_total_bytes": total, "numpy_torch_bridge": "passed", "models_loaded": False,
        "harness_dependency_metadata": harness_dependencies, "harness_dependency_version_gate": "recorded, not independently wheel-hash pinned"}


def qualify_gpu_runtimes(release: dict, admission: dict, output: Path) -> list[dict]:
    gpus = visible_gpu_tokens(release["resource_cap"]["gpu_count"])
    results = []
    for index, gpu in enumerate(gpus):
        receipt_path = output / "qualification" / f"gpu_runtime_{index:02d}.json"
        log_path = receipt_path.with_suffix(".out")
        command = [sys.executable, "-m", MODULE, "runtime", "--release", admission["release_path"],
            "--release-sha256", admission["release_sha256"], "--output", str(receipt_path)]
        with log_path.open("xb") as log:
            process = subprocess.Popen(command, env=dict(os.environ, CUDA_VISIBLE_DEVICES=gpu), close_fds=True,
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
            try: code = process.wait(timeout=90)
            except subprocess.TimeoutExpired:
                process.terminate()
                try: process.wait(timeout=3)
                except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=3)
                worker.write_new(receipt_path.with_suffix(".supervisor.json"), {"reaped": process.poll() is not None,
                    "returncode": process.returncode, "reason": "runtime_gate_deadline"})
                raise RuntimeError("bounded GPU runtime gate did not finish")
        worker.write_new(receipt_path.with_suffix(".supervisor.json"), {"reaped": process.poll() is not None,
            "returncode": process.returncode, "reason": "exited"})
        if code != 0 or log_path.stat().st_size > worker.MAX_STDOUT:
            raise RuntimeError("GPU runtime/ABI gate failed")
        results.append({"allocated_gpu_index": index, "receipt": aj.file_pin(receipt_path), "runtime": aj.read_json(receipt_path)})
    return results


def wave_priority(order: list[dict]) -> list[dict]:
    """Preserve Latin positions across task families before progressing waves."""
    return sorted(order, key=lambda cell: (cell["within_task_position"], cell["task_index"]))


def execute(release: dict, admission: dict, output: Path, *, qualifier=None, dispatcher=None, clock=None, epoch=None) -> dict:
    """Qualify all gates, then parallel cells; only true runtime waits stop work."""
    clock = time.monotonic if clock is None else clock
    epoch = time.time if epoch is None else epoch
    started = clock()
    summary = aj.read_json(output / "summary.json")
    if summary.get("status") != "QUALIFYING" or summary.get("release_sha256") != admission["release_sha256"]:
        raise ValueError("fresh exact reserved AL assignment required")
    (output / "cells").mkdir(mode=0o700)
    def save():
        summary["elapsed_seconds"] = clock() - started
        summary["descriptive"] = aj.summarize(summary["slots"])
        summary["model_execution_started"] = summary["descriptive"]["costs"]["native_requests"]["observed_sum"] > 0
        sandbox._atomic_json(output / "summary.json", summary)
    qualifier = qualify if qualifier is None else qualifier
    qualification = qualifier(release, admission, output)
    summary["qualification"] = qualification
    summary["all_controls_accepted"] = qualification.get("all_controls_accepted") is True
    summary["source_review_accepted"] = qualification.get("source_review_accepted") is True
    if not all(qualification.get(k) is True for k in ("all_controls_accepted", "source_review_accepted", "runtime_accepted")):
        summary.update(status="INCOMPLETE_ASSIGNED_COHORT", stop_reason="whole_source_control_runtime_gate_not_met")
        for cell in summary["slots"]: cell["grade"] = aj.unknown_grade(summary["stop_reason"])
        save(); return summary
    try:
        inner_path, inner_sha = create_worker_admission(release, admission, qualification, output)
    except (ValueError, OSError) as exc:
        summary.update(status="INCOMPLETE_ASSIGNED_COHORT", all_controls_accepted=False,
            stop_reason="independent_whole_control_admission_rejected", admission_error=type(exc).__name__)
        for cell in summary["slots"]: cell["grade"] = aj.unknown_grade(summary["stop_reason"])
        save(); return summary
    summary["worker_admission"] = {"path": str(inner_path), "sha256": inner_sha}
    gpus = visible_gpu_tokens(release["resource_cap"]["gpu_count"])
    summary.update(status="RUNNING", visible_gpu_count=len(gpus), execution_order="Latin-position waves across all8families; cell identity unchanged")
    available = list(gpus); active = {}; logs = {}; queue = wave_priority(release["order"])
    assigned = {cell["period"]: cell for cell in summary["slots"]}
    dispatcher = subprocess.Popen if dispatcher is None else dispatcher
    save()
    try:
        while queue or active:
            remaining = goal_remaining(release, started_monotonic=started, now_monotonic=clock(), now_epoch=epoch())
            if queue and remaining < aj.SLOT_RESERVATION_SECONDS:
                summary["stop_reason"] = "joint_budget_no_complete_slot_envelope"; queue = []
            if controls.scoped_bytes(output) > release["limits"]["storage_bytes"]:
                summary["stop_reason"] = "private_storage_cap"; queue = []
            while queue and available and not summary["stop_reason"]:
                slot = queue.pop(0); gpu = available.pop(0); cell = assigned[slot["period"]]
                env = dict(os.environ, CUDA_VISIBLE_DEVICES=gpu)
                command = [sys.executable, "-m", MODULE, "cell", "--release", admission["release_path"],
                    "--release-sha256", admission["release_sha256"], "--output", str(output), "--period", str(slot["period"]),
                    "--worker-admission", str(inner_path), "--worker-admission-sha256", inner_sha]
                cell.update(status="EPISODE_RUNNING", gpu_token=gpu, episode_directory=str(output / "episodes" / f"{slot['period']:02d}-{slot['task_id']}-{slot['schedule']}"), cleanup_verified=False)
                log_path = output / "cells" / f"{slot['period']:02d}.stdout"
                process = dispatcher(command, env=env, close_fds=True, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                logs[slot["period"]] = (log_path.open("xb"), 0)
                if getattr(process, "stdout", None) is not None:
                    os.set_blocking(process.stdout.fileno(), False)
                active[slot["period"]] = (process, gpu)
                summary["real_model_worker_started"] = summary["cell_worker_dispatched"] = True
                save()
            for period, (process, gpu) in list(active.items()):
                log, retained = logs[period]
                pipe = getattr(process, "stdout", None)
                if pipe is not None:
                    while True:
                        try: chunk = os.read(pipe.fileno(), 65536)
                        except BlockingIOError: break
                        if not chunk: break
                        keep = chunk[:max(0, worker.MAX_STDOUT - retained)]
                        log.write(keep); retained += len(keep)
                        if len(keep) != len(chunk):
                            assigned[period]["stdout_overflow"] = True
                            summary["stop_reason"] = "cell_output_limit"; queue = []
                            process.terminate(); break
                    logs[period] = (log, retained)
                code = process.poll()
                result = output / "cells" / f"{period:02d}.json"
                cell = assigned[period]
                if result.exists():
                    observed = aj.read_json(result)
                    if any(observed.get(k) != cell[k] for k in release["order"][0]):
                        raise ValueError("returned cell assignment differs")
                    cell.update(observed)
                if code is None:
                    save(); continue
                if result.exists():
                    pass
                else:
                    cell.update(status="INFRASTRUCTURE_UNKNOWN", infrastructure_unknown=True, grade=aj.unknown_grade("cell_receipt_missing"), cleanup_verified=False)
                if code != 0:
                    cell.update(status="INFRASTRUCTURE_UNKNOWN", infrastructure_unknown=True, grade=aj.unknown_grade("cell_process_nonzero"))
                if cell.get("cleanup_verified") is not True:
                    summary["stop_reason"] = "parallel_cell_cleanup_unknown"; queue = []
                log.flush(); log.close()
                if pipe is not None: pipe.close()
                cell["stdout"] = {"path": str(output / "cells" / f"{period:02d}.stdout"),
                    "sha256": worker.digest_file(output / "cells" / f"{period:02d}.stdout"), "retained_bytes": retained,
                    "cap_bytes": worker.MAX_STDOUT}
                del active[period]; available.append(gpu); save()
            if remaining <= 0:
                summary["stop_reason"] = "author_six_hour_deadline"; break
            if active: time.sleep(.05)
            elif queue and not available: raise RuntimeError("GPU token accounting lost")
    finally:
        # Coordinator remains responsible for its cells. Owner death is also
        # covered by AJ's independent batch guardian and each AI owner pipe.
        for process, _ in active.values():
            if process.poll() is None: process.terminate()
        for process, _ in active.values():
            try: process.wait(timeout=20)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=3)
        for period in active:
            cell = assigned[period]
            cell.update(status="INFRASTRUCTURE_UNKNOWN", infrastructure_unknown=True,
                cleanup_verified=aj.cleanup_for_slot(cell), grade=aj.unknown_grade(summary.get("stop_reason") or "parallel_coordinator_interrupted"))
        for log, _ in logs.values():
            if not log.closed: log.close()
        for cell in summary["slots"]:
            if cell["status"] == "NOT_ATTEMPTED": cell["grade"] = aj.unknown_grade(summary.get("stop_reason") or "not_started")
        summary["status"] = "INCOMPLETE_ASSIGNED_COHORT" if summary["stop_reason"] else "COMPLETED_ASSIGNED_COHORT"
        save()
    return summary


def run(release_path: Path, expected_sha: str, output: Path) -> dict:
    release, admission = startup_preflight(release_path, expected_sha, output)
    remaining = min(release["limits"]["batch_seconds"], release["goal"]["deadline_epoch"] - time.time())
    if remaining <= 45: raise RuntimeError("original author deadline exhausted before allocation admission")
    output = output.absolute()
    seed(release, admission, output)
    rfd, wfd = os.pipe(); guard = None
    try:
        command = [sys.executable, "-m", MODULE, "guard", "--release", str(release_path.absolute()),
            "--release-sha256", expected_sha, "--output", str(output), "--owner-fd", str(rfd)]
        guard = subprocess.Popen(command, pass_fds=(rfd,), close_fds=True, start_new_session=True,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(rfd); rfd = None
        guard.wait(timeout=remaining + 45)
    finally:
        if rfd is not None: os.close(rfd)
        os.close(wfd)
        if guard is not None and guard.poll() is None: guard.wait(timeout=30)
    receipt = aj.read_json(output.parent / (output.name + ".batch_guardian.json"))
    if guard.returncode != 0 or receipt.get("abort_future_execution") is True:
        raise RuntimeError("whole allocation cleanup uncertain; no later execution")
    return aj.read_json(output / "summary.json")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("run", "guard", "worker", "cell", "assets", "runtime"))
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--release-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--owner-fd", type=int)
    parser.add_argument("--period", type=int)
    parser.add_argument("--worker-admission", type=Path)
    parser.add_argument("--worker-admission-sha256")
    args = parser.parse_args()
    if args.mode == "run":
        run(args.release, args.release_sha256, args.output); return
    release, admission = load_release(args.release, args.release_sha256)
    if args.mode == "runtime":
        worker.write_new(args.output, gpu_runtime_receipt(release))
    elif args.mode == "assets":
        sandbox.download_model_assets(release, admission["model_root"], args.output / "qualification" / "model_acquisition_hashes.json")
    elif args.mode == "worker":
        try: execute(release, admission, args.output)
        except BaseException:
            retain_error(args.output / "allocation_worker_error.txt")
            raise
    elif args.mode == "cell":
        if type(args.period) is not int or not 1 <= args.period <= 32 or args.worker_admission is None or args.worker_admission_sha256 is None:
            raise ValueError("exact individual reserved cell required")
        run_cell(args.worker_admission, args.worker_admission_sha256, args.release_sha256, args.output, args.period)
    else:
        if args.owner_fd is None: raise ValueError("independent owner pipe required")
        remaining = min(release["limits"]["batch_seconds"], release["goal"]["deadline_epoch"] - time.time())
        if remaining <= 0: raise RuntimeError("original author six-hour deadline exhausted")
        aj.guard_batch(command=[sys.executable, "-m", MODULE, "worker", "--release", str(args.release),
            "--release-sha256", args.release_sha256, "--output", str(args.output)], owner_fd=args.owner_fd,
            output=args.output, batch_seconds=remaining, storage_bytes=release["limits"]["storage_bytes"],
            storage_scope=args.output.parent, cleanup_validator=qualification_cleanup)


if __name__ == "__main__": main()
