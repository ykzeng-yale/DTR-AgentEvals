"""Local-build-filesystem correction of the complete CPU-only AH cohort.

Original AH evidence remains immutable. This is a separately released acquisition
attempt only after all AH controls/model inputs remained unattempted. It changes
no task, image, evaluator, isolation, pull, test or model budget. Never loads models.

The selected tasks and stock evaluator bytes are frozen before execution. Every
assigned arm receives a receipt, including failures and unattempted arms. No
passing subset is released, and this module has no model-download/run branch.
"""
from __future__ import annotations

import argparse
import ast
from enum import Enum
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

from experiments.lead_req030 import req030ag_screen as shared
from experiments.lead_req030 import req030aj_acquisition as acquisition

ROOT = Path(__file__).resolve().parents[2]
REQUEST = "DTR-REQ-030AK"
RELEASE_ID = "req030ak-controls-20260930-a"
TASK_IDS = (
    "django__django-12039", "matplotlib__matplotlib-26208",
    "psf__requests-6028", "pydata__xarray-6461", "pylint-dev__pylint-6386",
    "pytest-dev__pytest-10081", "scikit-learn__scikit-learn-25102",
    "sphinx-doc__sphinx-8593",
)
PARSER_REL = "work/upstream/SWE-bench-f7bbbb2ccdf479001d6467c9e34af59e44a840f9/swebench/harness/log_parsers/python.py"
PARSER_SHA = "42f564edfee3c21751739bbf09d60cf3a3ecdc58ac5cf45717dc6b47a85d7459"
LIMITS = {"evaluation_seconds": 900, "pull_seconds": 900,
          "batch_seconds": 27000, "storage_bytes": 80 * (1 << 30),
          "file_bytes": 8 * (1 << 30), "min_free_bytes": 100 * (1 << 30)}


def load_release(bundle: Path, release: Path, expected_sha: str) -> dict:
    if shared.sha_file(release) != expected_sha:
        raise ValueError("release hash mismatch")
    doc = json.loads(release.read_bytes())
    if (doc.get("request") != REQUEST or doc.get("release_id") != RELEASE_ID
            or doc.get("limits") != LIMITS or doc.get("model_execution_authorized") is not False):
        raise ValueError("CPU-only release identity/limits mismatch")
    correction = doc.get("acquisition_correction")
    if (not isinstance(correction, dict) or set(correction) != {"prior_job_id", "prior_release_sha256", "prior_terminal_receipt", "change"}
            or correction["prior_job_id"] != "27950747"
            or correction["prior_release_sha256"] != "77d7b1b33f221e829aa67f9ce59f928cbbdf0b1453d6661399142827de6e1384"
            or correction["change"] != "build temporary filesystem only: project NFS to verified allocation-local ext4/xfs"):
        raise ValueError("explicit immutable acquisition-only supersession required")
    prior = correction["prior_terminal_receipt"]
    if not isinstance(prior, dict) or set(prior) != {"path", "sha256"}:
        raise ValueError("prior terminal evidence pin required")
    evidence_path = (bundle / prior["path"]).resolve()
    if (not evidence_path.is_relative_to(bundle.resolve()) or not evidence_path.is_file()
            or evidence_path.stat().st_size > 256 * 1024 or shared.sha_file(evidence_path) != prior["sha256"]):
        raise ValueError("prior terminal evidence identity mismatch")
    evidence = json.loads(evidence_path.read_bytes())
    if (evidence.get("actual_job_id") != "27950747" or evidence.get("actual_state") != "FAILED"
            or evidence.get("cohort_status") != "COHORT_REJECTED_OR_UNKNOWN"
            or evidence.get("model_calls") != 0 or evidence.get("models_loaded") is not False
            or evidence.get("controls_attempted") != 0 or evidence.get("usable_sif_count") != 0
            or evidence.get("task_count") != 8 or evidence.get("control_count") != 16
            or any(type(evidence.get(k)) is not int for k in ("model_calls", "controls_attempted", "usable_sif_count", "task_count", "control_count"))):
        raise ValueError("all eight tasks must be acquisition-only, terminal and unexposed")
    if tuple(x["instance_id"] for x in doc["tasks"]) != TASK_IDS:
        raise ValueError("frozen queue cohort differs")
    if len({x["repo"] for x in doc["tasks"]}) != 8:
        raise ValueError("one task per repository required")
    pins = doc.get("source_pins", {})
    needed = {PARSER_REL, "experiments/lead_req030/req030ak_controls.py",
              "experiments/lead_req030/req030aj_acquisition.py",
              "experiments/lead_req030/req030ag_screen.py",
              "experiments/lead_req030/req030ag_bounded_supervisor.py",
              "experiments/lead_req030/bounded_supervisor.py"}
    if not needed <= set(pins):
        raise ValueError("missing executable source pins")
    for rel, digest in pins.items():
        p = (ROOT / rel).resolve()
        if not p.is_relative_to(ROOT) or shared.sha_file(p) != digest:
            raise ValueError(f"source identity mismatch: {rel}")
    for task in doc["tasks"]:
        shared.apptainer_docker_uri(task["image_ref"])
        if (not task["image_ref"].endswith("@" + task["oci_amd64_leaf_digest"])
                or task["architecture"] != "amd64" or task["os"] != "linux"
                or not re.fullmatch(r"[a-f0-9]{40}", task["base_commit"])):
            raise ValueError("task source/image identity mismatch")
        for kind, sha_key, size_key in (("public", "public_projection_sha256", "public_projection_bytes"),
                                        ("evaluator", "evaluator_bundle_sha256", "evaluator_bundle_bytes")):
            p = bundle / kind / (task["instance_id"] + ".json")
            if shared.sha_file(p) != task[sha_key] or p.stat().st_size != task[size_key]:
                raise ValueError(f"{kind} identity mismatch")
            data = json.loads(p.read_bytes())
            if any(data[k] != task[k] for k in ("instance_id", "base_commit")):
                raise ValueError("task input/source binding mismatch")
            if kind == "public":
                if set(data) != {"instance_id", "repo", "base_commit", "problem_statement"} or data["repo"] != task["repo"]:
                    raise ValueError("public projection allowlist mismatch")
            else:
                for field in ("stock_eval_script", "reference_patch"):
                    if shared.sha_bytes(data[field].encode()) != task[field + "_sha256"]:
                        raise ValueError("evaluator content binding mismatch")
                if (len(data["fail_to_pass"]) != task["fail_to_pass_count"]
                        or len(data["pass_to_pass"]) != task["pass_to_pass_count"]):
                    raise ValueError("declared evaluator counts mismatch")
    return doc


def pinned_parsers() -> dict:
    source = (ROOT / PARSER_REL).read_bytes()
    if shared.sha_bytes(source) != PARSER_SHA:
        raise ValueError("official parser source mismatch")
    tree = ast.parse(source, filename=PARSER_REL)
    # These are the only two imports omitted from the exact upstream source:
    # supply their simple annotation/enum interfaces without importing Docker.
    removed = [n.module for n in tree.body if isinstance(n, ast.ImportFrom)]
    if removed != ["swebench.harness.constants", "swebench.harness.test_spec.test_spec"]:
        raise ValueError("unexpected parser dependencies")
    tree.body = [n for n in tree.body if not isinstance(n, ast.ImportFrom)]
    statuses = Enum("TestStatus", {s: s for s in ("FAILED", "PASSED", "SKIPPED", "ERROR", "XFAIL")})
    namespace = {"TestStatus": statuses, "TestSpec": object}
    exec(compile(tree, PARSER_REL, "exec"), namespace)
    return namespace["MAP_REPO_TO_PARSER_PY"]


def assess(raw: bytes, receipt: dict, evaluation: dict, mode: str, parser) -> dict:
    text = raw.decode("utf-8", "replace")
    marks = ("DTR_TEST_START", ">>>>> Start Test Output", ">>>>> End Test Output", "DTR_TEST_END")
    framing = all(text.count(m) == 1 for m in marks)
    framing = framing and [text.index(m) for m in marks] == sorted(text.index(m) for m in marks)
    parsed = parser(text.split(marks[1], 1)[1].split(marks[2], 1)[0], None) if framing else {}
    f2p, p2p = evaluation["fail_to_pass"], evaluation["pass_to_pass"]
    if not f2p or not p2p or len(set(f2p + p2p)) != len(f2p + p2p):
        raise ValueError("invalid declared identity set")
    declared = {x: parsed.get(x, "MISSING") for x in f2p + p2p}
    valid = (framing and set(receipt) == {"reason", "pid", "returncode", "retained_bytes", "elapsed", "error"}
             and receipt.get("reason") == "exited" and receipt.get("error") is None
             and type(receipt.get("pid")) is int and receipt["pid"] > 0
             and type(receipt.get("returncode")) is int and receipt["returncode"] in (0, 1)
             and type(receipt.get("retained_bytes")) is int and receipt["retained_bytes"] == len(raw)
             and type(receipt.get("elapsed")) in (int, float) and math.isfinite(receipt["elapsed"]) and receipt["elapsed"] >= 0
             and len(raw) <= shared.MAX_EPISODE_OUTPUT
             and not any(x in text for x in ("DTR_SETUP_FAILURE", "DTR_EVAL_ERROR", "DTR_ISOLATION_FAILURE")))
    expected_f = "FAILED" if mode == "baseline" else "PASSED" if mode == "reference" else None
    if expected_f is None:
        raise ValueError("only unchanged and reference controls authorized")
    accepted = valid and all(declared[x] == expected_f for x in f2p) and all(declared[x] == "PASSED" for x in p2p)
    return {"mode": mode, "accepted": accepted, "valid_process": valid, "markers_valid": framing,
            "declared_statuses": declared, "undeclared_statuses": {k:v for k,v in parsed.items() if k not in declared},
            "raw_sha256": shared.sha_bytes(raw), "raw_bytes": len(raw), "supervisor": receipt}


def execute_arm(task, evaluation, image, source, head, directory, apptainer, parser):
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    ws = directory / "workspace.img"
    mode = directory.name
    try:
        workspace = shared.make_workspace(source, directory / "seed_temp", ws, uid=os.getuid(), gid=os.getgid())
        ev = directory / "evaluator"; ev.mkdir(mode=0o700)
        (ev / "stock_eval.sh").write_text(evaluation["stock_eval_script"])
        (ev / "stock_eval.sh").chmod(0o400)
        if mode == "reference":
            (ev / "reference.diff").write_text(evaluation["reference_patch"])
            (ev / "reference.diff").chmod(0o400)
        shared.evaluation_wrapper(ev / "run.sh", mode=mode, expected_image_head=head)
        raw, receipt = shared.run_supervised(apptainer, image, ws, ["/bin/bash", "/eval/run.sh"],
            output_path=directory / f"{mode}.out", receipt_path=directory / f"{mode}.supervisor.json",
            seconds=LIMITS["evaluation_seconds"], extra_binds=["--bind", f"{ev.resolve()}:/eval:ro"])
        result = assess(raw, receipt, evaluation, mode, parser)
        result["workspace"] = workspace
        return result
    finally:
        if ws.exists():
            ws.unlink()
        if (directory / "seed_temp").exists():
            shutil.rmtree(directory / "seed_temp")


def scoped_bytes(directory: Path) -> int:
    total = 0
    for p in directory.rglob("*"):
        try:
            if p.is_file() and not p.is_symlink():
                total += p.stat().st_size
        except FileNotFoundError:
            pass  # The worker may remove its own completed workspace/cache.
    return total


def execute(release: dict, bundle: Path, output: Path, release_sha: str) -> dict:
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    summary = {"request": REQUEST, "release_id": RELEASE_ID, "release_sha256": release_sha,
               "job_id": os.environ.get("SLURM_JOB_ID"), "status": "RUNNING",
               "tasks": [{"task_id": tid, "status": "not_attempted", "source_contract_for_model": "UNQUALIFIED"}
                         for tid in TASK_IDS],
               "controls": [{"task_id": tid, "mode": mode, "accepted": False,
                    "status": "NOT_ATTEMPTED", "reason": "not reached"}
                    for tid in TASK_IDS for mode in ("baseline", "reference")],
               "model_calls": 0, "models_loaded": False,
               "planned_tasks": 8, "planned_control_arms": 16, "started_epoch": time.time()}
    summary["supersedes_acquisition_only"] = "27950747"
    summary["build_temp_filesystem"] = "allocation-local ext4/xfs; verified before acquisition"
    save = lambda: shared._atomic_json(output / "summary.json", summary)
    save()
    apptainer = shutil.which("apptainer")
    if not apptainer:
        raise RuntimeError("Apptainer absent inside allocation")
    parsers = pinned_parsers()
    summary["apptainer_version"] = subprocess.check_output([apptainer, "--version"], timeout=15).decode().strip()
    for d in ("images", "sources", "controls"):
        (output / d).mkdir(mode=0o700)
    deadline = time.monotonic() + LIMITS["batch_seconds"]
    stopped = None
    for task in release["tasks"]:
        tid = task["instance_id"]
        item = next(x for x in summary["tasks"] if x["task_id"] == tid)
        image, source = output / "images" / (tid + ".sif"), output / "sources" / (tid + ".tar")
        try:
            if stopped or time.monotonic() >= deadline:
                raise RuntimeError(stopped or "batch deadline")
            used = scoped_bytes(output.parent)
            if used > LIMITS["storage_bytes"]:
                stopped = "storage cap reached"; raise RuntimeError(stopped)
            shared.require_disk_floor(output, LIMITS["min_free_bytes"])
            shared.require_disk_floor(Path(os.environ["APPTAINER_TMPDIR"]), LIMITS["min_free_bytes"])
            with (output / "images" / (tid + ".pull.log")).open("xb") as log:
                subprocess.run(["timeout", "--signal=TERM", "--kill-after=15s", str(LIMITS["pull_seconds"]),
                    apptainer, "pull", str(image), shared.apptainer_docker_uri(task["image_ref"])],
                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, check=True,
                    timeout=LIMITS["pull_seconds"] + 30)
            if image.stat().st_size > LIMITS["file_bytes"]:
                raise ValueError("task image exceeds individual file cap")
            item["image"] = {"sif_sha256": shared.sha_file(image), "bytes": image.stat().st_size,
                             "oci_leaf_digest": task["oci_amd64_leaf_digest"]}
            check = shared._tree_for_task(image, task["base_commit"], apptainer)
            item["source_check"] = check
            item["source_contract_for_model"] = "BASE_TREE_MATCH" if check["tree"] == check["expected_base_tree"] else "REQUIRES_SETUP_DELTA_REVIEW"
            item["source_archive"] = shared.export_task_tree(image, source, apptainer)
            if source.stat().st_size > LIMITS["file_bytes"]:
                raise ValueError("source export exceeds cap")
            item["status"] = "SOURCE_VERIFIED"; save()
        except Exception as exc:
            item.update(status="SETUP_UNKNOWN", error_type=type(exc).__name__, error=str(exc)[:2000])
            if isinstance(exc, shared.TaskImageGateError):
                item["source_check"] = exc.evidence
        evaluation = json.loads((bundle / "evaluator" / (tid + ".json")).read_bytes())
        for mode in ("baseline", "reference"):
            target = next(x for x in summary["controls"] if x["task_id"] == tid and x["mode"] == mode)
            if item["status"] != "SOURCE_VERIFIED" or stopped or time.monotonic() >= deadline:
                result = {"mode": mode, "accepted": False, "status": "NOT_ATTEMPTED", "reason": stopped or item["status"]}
            else:
                target.update(status="RUNNING", reason="control started"); save()
                try:
                    result = execute_arm(task, evaluation, image, source, check["head"],
                        output / "controls" / tid / mode, apptainer, parsers[task["repo"]])
                    result["status"] = "ACCEPTED" if result["accepted"] else "CONTROL_REJECTED"
                except Exception as exc:
                    result = {"mode": mode, "accepted": False, "status": "INFRASTRUCTURE_UNKNOWN",
                              "error_type": type(exc).__name__, "error": str(exc)[:2000]}
            result["task_id"] = tid
            target.clear(); target.update(result); save()
        # Cached OCI layers are not needed after the SIF's identity is recorded.
        # Clear only this job's private acquisition cache, never a shared cache.
        cache = os.environ.get("APPTAINER_CACHEDIR")
        if cache and Path(cache).resolve() == (output.parent / "apptainer-cache").resolve():
            shutil.rmtree(cache, ignore_errors=True)
            Path(cache).mkdir(mode=0o700)
    ok = len(summary["controls"]) == 16 and all(x["accepted"] for x in summary["controls"])
    summary.update(status="CONTROLS_PASS_REVIEW_REQUIRED" if ok else "COHORT_REJECTED_OR_UNKNOWN",
        all_controls_accepted=ok, model_execution_authorized=False, finished_epoch=time.time(),
        source_contract_all_base_trees=all(x["source_contract_for_model"] == "BASE_TREE_MATCH" for x in summary["tasks"]))
    save()
    return summary


def finalize_interrupted(output: Path, reason: str) -> None:
    path = output / "summary.json"
    if not path.exists():
        return
    summary = json.loads(path.read_bytes())
    if summary["status"] != "RUNNING":
        return
    for arm in summary["controls"]:
        if arm["status"] == "RUNNING":
            arm.update(status="INFRASTRUCTURE_UNKNOWN", accepted=False, reason=reason)
        elif arm["status"] == "NOT_ATTEMPTED":
            arm["reason"] = reason
    summary.update(status="INTERRUPTED_UNKNOWN", all_controls_accepted=False,
                   model_execution_authorized=False, stop_reason=reason, finished_epoch=time.time())
    shared._atomic_json(path, summary)


def supervise_local_worker(a):
    output = Path(a.output).resolve()
    context = acquisition.prepare_acquisition(temp_parent=Path("/tmp"), run_id=RELEASE_ID,
        expected_job_id=os.environ["SLURM_JOB_ID"], min_free_bytes=LIMITS["min_free_bytes"])
    try:
        with context:
            local_temp = context.private_dir
            os.environ["APPTAINER_TMPDIR"] = str(context.tmp_dir)
            shared._atomic_json(output.parent / "acquisition_filesystem.json", context.receipt)
            proc = subprocess.Popen([sys.executable, "-m", "experiments.lead_req030.req030ak_controls",
                                     *sys.argv[1:], "--worker"], start_new_session=True)
            begin = time.monotonic()
            reason = None
            peak = 0
            try:
                while proc.poll() is None:
                    used = scoped_bytes(output.parent) + scoped_bytes(local_temp)
                    peak = max(peak, used)
                    if used > LIMITS["storage_bytes"]:
                        reason = "private storage exceeded monitored limit"; break
                    if time.monotonic() - begin > LIMITS["batch_seconds"]:
                        reason = "batch deadline"; break
                    time.sleep(2)
            finally:
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGTERM)
                    try:
                        proc.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        os.killpg(proc.pid, signal.SIGKILL); proc.wait(timeout=5)
                shared._atomic_json(output.parent / "resource_guard.json",
                    {"returncode": proc.returncode, "stop_reason": reason,
                     "peak_observed_private_logical_bytes": peak,
                     "storage_limit_bytes": LIMITS["storage_bytes"],
                     "storage_check_seconds": 2,
                     "storage_enforcement": "joint run + allocation-local build-temp sampled termination; transient overshoot possible",
                     "elapsed_seconds": time.monotonic() - begin})
                finalize_interrupted(output, reason or f"worker exited {proc.returncode} before summary completion")
            result = 3 if reason else proc.returncode
    except BaseException:
        shared._atomic_json(output.parent / "local_temp_cleanup.json",
            {"verified": context._cleaned, "job_id": os.environ["SLURM_JOB_ID"],
             "scope": "owned local acquisition tree only", "exception": True})
        raise
    shared._atomic_json(output.parent / "local_temp_cleanup.json",
        {"verified": context._cleaned, "job_id": os.environ["SLURM_JOB_ID"],
         "scope": "owned local acquisition tree only"})
    return result


def main():
    p = argparse.ArgumentParser()
    for flag in ("bundle", "release", "release-sha256", "output"):
        p.add_argument("--" + flag, required=True)
    p.add_argument("--worker", action="store_true")
    a = p.parse_args()
    bundle = Path(a.bundle).resolve()
    release = load_release(bundle, Path(a.release), a.release_sha256)
    if not a.worker:
        return supervise_local_worker(a)
    result = execute(release, bundle, Path(a.output).resolve(), a.release_sha256)
    return 0 if result["all_controls_accepted"] else 2


if __name__ == "__main__":
    sys.exit(main())
