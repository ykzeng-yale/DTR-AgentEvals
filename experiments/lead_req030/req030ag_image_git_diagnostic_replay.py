"""Independently replay REQ030AG retained-image diagnostic receipts."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def replay(diagnostic_path: Path, v5_manifest_path: Path, image_manifest_path: Path,
           log_path: Path) -> dict:
    diagnostic_raw = diagnostic_path.read_bytes()
    diagnostic = json.loads(diagnostic_raw)
    v5_manifest = json.loads(v5_manifest_path.read_bytes())
    image_manifest = json.loads(image_manifest_path.read_bytes())
    log = log_path.read_text()
    diagnostic_sha = hashlib.sha256(diagnostic_raw).hexdigest()
    match = re.search(r'"report_sha256":\s*"([0-9a-f]{64})"', log)
    if not match or match.group(1) != diagnostic_sha:
        raise ValueError("Slurm completion log does not bind the retrieved diagnostic JSON")
    if diagnostic.get("request") != "DTR-REQ-030AG-IMAGE-GIT-DIAGNOSTIC":
        raise ValueError("unexpected diagnostic request identity")
    if diagnostic.get("release_sha256") != hashlib.sha256(v5_manifest_path.read_bytes()).hexdigest():
        raise ValueError("diagnostic is not bound to the exact frozen v5 manifest")
    if diagnostic.get("slurm_job_id") != "27930700":
        raise ValueError("diagnostic Slurm identity mismatch")
    if (diagnostic.get("task_count") != 8 or len(diagnostic.get("tasks", [])) != 8
            or diagnostic.get("model_calls") != 0 or diagnostic.get("benchmark_tests") != 0
            or diagnostic.get("task_actions") != 0 or diagnostic.get("network") != "none inside each task container"):
        raise ValueError("diagnostic scope/counters differ from the released read-only check")
    expected_v5 = {task["instance_id"]: task for task in v5_manifest["tasks"]}
    expected_v6 = {task["instance_id"]: task for task in image_manifest["tasks"]}
    if set(expected_v5) != set(expected_v6) or set(expected_v5) != {task.get("task_id") for task in diagnostic["tasks"]}:
        raise ValueError("diagnostic task identities do not match the frozen cohort")
    replayed = []
    for task in diagnostic["tasks"]:
        pin = expected_v5[task["task_id"]]
        image_pin = expected_v6[task["task_id"]]
        original, scoped = task["production_check"], task["scoped_safe_directory_check"]
        if not task.get("image_exists") or not re.fullmatch(r"[0-9a-f]{64}", task.get("image_sha256", "")):
            raise ValueError(f"missing or malformed SIF identity: {task['task_id']}")
        if (image_pin["base_commit"] != pin["base_commit"]
                or task["image_sha256"] != image_pin["sif_sha256"]
                or task["image_bytes"] != image_pin["sif_bytes"]):
            raise ValueError(f"retained SIF differs from its new immutable pin: {task['task_id']}")
        if (original.get("timed_out") or scoped.get("timed_out") or original.get("returncode") != 0
                or scoped.get("returncode") != 0 or original.get("stderr") or scoped.get("stderr")):
            raise ValueError(f"container Git inspection failed: {task['task_id']}")
        original_fields = dict(line.split("=", 1) for line in original["stdout"].splitlines() if "=" in line)
        scoped_lines = scoped["stdout"].splitlines()
        if (original_fields.get("CLEAN") != "1" or original_fields.get("HEAD") != scoped_lines[0]
                or original_fields.get("TREE") != scoped_lines[1] or len(scoped_lines) != 2):
            raise ValueError(f"production and scoped Git reads disagree or image is dirty: {task['task_id']}")
        if original_fields["HEAD"] == pin["base_commit"]:
            raise ValueError(f"expected v5's observed post-setup HEAD mismatch: {task['task_id']}")
        replayed.append({"task_id": task["task_id"], "expected_base_commit": pin["base_commit"],
                         "observed_head": original_fields["HEAD"], "tree": original_fields["TREE"],
                         "clean": True, "safe_directory_changed_result": False,
                         "sif_sha256": task["image_sha256"], "sif_bytes": task["image_bytes"]})
    return {"request": "DTR-REQ-030AG-IMAGE-GIT-DIAGNOSTIC-REPLAY", "slurm_job_id": "27930700",
            "diagnostic_sha256": diagnostic_sha, "v5_manifest_sha256": diagnostic["release_sha256"],
            "v6_image_manifest_sha256": hashlib.sha256(image_manifest_path.read_bytes()).hexdigest(),
            "tasks": replayed, "conclusion": "all eight clean; scoped safe.directory changes no result; all image HEADs differ from dataset base_commit",
            "scope": "read-only SIF/Git identity inspection only; no tests, controls, model calls, or actions"}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--diagnostic", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--image-manifest", type=Path, required=True)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = replay(args.diagnostic, args.manifest, args.image_manifest, args.log)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"status": "REPLAY_PASS", "task_count": len(result["tasks"]),
                      "diagnostic_sha256": result["diagnostic_sha256"]}))
