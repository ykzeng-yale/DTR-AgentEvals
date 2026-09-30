"""Inspect the already-pulled REQ030AG v5 task SIFs without tests or models."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path


RELEASE_SHA256 = "5f21c08e68d83901790ef70b1f591d367455cd1fe4ba4fde165d03ac9921a085"
RELEASE_ID = "req030ag-development-20260930-v5"
APPTAINER_FLAGS = ["exec", "--containall", "--cleanenv", "--no-home", "--no-mount",
                   "hostfs,bind-paths", "--net", "--network", "none", "--pwd", "/"]
PRODUCTION_CHECK = (
    "cd /testbed && printf 'HEAD=' && git rev-parse HEAD && "
    "printf 'TREE=' && git rev-parse 'HEAD^{tree}' && "
    "test -z \"$(git status --porcelain --untracked-files=all)\" && echo CLEAN=1"
)
SCOPED_SAFE_CHECK = (
    "cd /testbed && git -c safe.directory=/testbed rev-parse HEAD && "
    "git -c safe.directory=/testbed rev-parse 'HEAD^{tree}' && "
    "git -c safe.directory=/testbed status --porcelain --untracked-files=all"
)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 << 20), b""):
            h.update(block)
    return h.hexdigest()


def run_check(apptainer: str, image: Path, shell: str) -> dict:
    command = [apptainer, *APPTAINER_FLAGS, str(image), "/bin/bash", "-lc", shell]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=45, check=False, env=os.environ.copy())
        return {"returncode": result.returncode,
                "stdout": result.stdout.decode("utf-8", "replace"),
                "stderr": result.stderr.decode("utf-8", "replace"),
                "timed_out": False}
    except subprocess.TimeoutExpired as exc:
        return {"returncode": None,
                "stdout": (exc.stdout or b"").decode("utf-8", "replace"),
                "stderr": (exc.stderr or b"").decode("utf-8", "replace"),
                "timed_out": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--images", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = args.manifest.read_bytes()
    if hashlib.sha256(raw).hexdigest() != RELEASE_SHA256:
        raise SystemExit("v5 manifest digest mismatch")
    release = json.loads(raw)
    if release.get("release_id") != RELEASE_ID or len(release.get("tasks", [])) != 8:
        raise SystemExit("unexpected frozen release identity/cohort")
    apptainer = shutil.which("apptainer")
    if not apptainer:
        raise SystemExit("Apptainer unavailable in diagnostic allocation")
    evidence = {"request": "DTR-REQ-030AG-IMAGE-GIT-DIAGNOSTIC",
                "release_sha256": RELEASE_SHA256,
                "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
                "started_epoch": time.time(), "task_count": len(release["tasks"]),
                "model_calls": 0, "benchmark_tests": 0, "task_actions": 0,
                "network": "none inside each task container", "tasks": []}
    for task in release["tasks"]:
        image = args.images / f"{task['instance_id']}.sif"
        record = {"task_id": task["instance_id"], "expected_base_commit": task["base_commit"],
                  "image_exists": image.is_file()}
        if image.is_file():
            record["image_bytes"] = image.stat().st_size
            record["image_sha256"] = sha(image)
            record["production_check"] = run_check(apptainer, image, PRODUCTION_CHECK)
            record["scoped_safe_directory_check"] = run_check(apptainer, image, SCOPED_SAFE_CHECK)
        evidence["tasks"].append(record)
    evidence["finished_epoch"] = time.time()
    args.output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = args.output.with_suffix(args.output.suffix + ".tmp")
    temp.write_text(json.dumps(evidence, sort_keys=True, indent=2) + "\n")
    os.chmod(temp, 0o600)
    temp.replace(args.output)
    print(json.dumps({"status": "DIAGNOSTIC_COMPLETE", "tasks": len(evidence["tasks"]),
                      "production_rcs": [t.get("production_check", {}).get("returncode")
                                         for t in evidence["tasks"]],
                      "safe_rcs": [t.get("scoped_safe_directory_check", {}).get("returncode")
                                   for t in evidence["tasks"]],
                      "report_sha256": sha(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
