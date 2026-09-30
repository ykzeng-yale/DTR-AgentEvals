from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from experiments.lead_req030 import req030ag_screen as screen


SUPERVISOR = screen.SUPERVISOR


def run_production_supervisor(tmp_path: Path, code: str, *, seconds: float, cap: int,
                              owner_eof_after: float | None = None) -> tuple[subprocess.Popen, dict, bytes]:
    output = tmp_path / "output.bin"
    receipt = tmp_path / "receipt.json"
    receipt_fd = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(receipt_fd)
    owner_r, owner_w = os.pipe()
    process = subprocess.Popen(
        [sys.executable, str(SUPERVISOR), "--owner-fd", str(owner_r), "--out", str(output),
         "--receipt", str(receipt), "--seconds", str(seconds), "--cap", str(cap),
         "--", sys.executable, "-c", code],
        pass_fds=(owner_r,), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    os.close(owner_r)
    try:
        if owner_eof_after is not None:
            time.sleep(owner_eof_after)
            os.close(owner_w)
            owner_w = -1
        stdout, stderr = process.communicate(timeout=8)
    finally:
        if owner_w >= 0:
            os.close(owner_w)
        if process.poll() is None:
            process.kill()
            process.wait()
    assert process.returncode == 0, (stdout, stderr)
    record = json.loads(receipt.read_text())
    body = output.read_bytes() if output.exists() else b""
    return process, record, body


def fake_apptainer(path: Path) -> Path:
    path.write_text(
        "#!/bin/bash\n"
        "while (($#)); do\n"
        "  if [[ $1 == *.sif ]]; then shift; exec \"$@\"; fi\n"
        "  shift\n"
        "done\n"
        "exit 99\n"
    )
    path.chmod(0o700)
    return path


def test_exact_production_wrapper_and_supervisor_capture_output_privately(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    monkeypatch.setattr(screen.os, "readlink", lambda _path: "net:[test-host-namespace]")
    apptainer = fake_apptainer(tmp_path / "apptainer")
    image = tmp_path / "fixed.sif"
    workspace = tmp_path / "workspace.img"
    image.touch(); workspace.touch()
    output = tmp_path / "normal.out"
    receipt = tmp_path / "normal.receipt.json"

    raw, supervisor = screen.run_supervised(
        str(apptainer), image, workspace, ["/bin/sh", "-c", "printf 'CONTROL_FIXTURE_OK\\n'"],
        output_path=output, receipt_path=receipt, seconds=3,
    )

    assert raw == b"CONTROL_FIXTURE_OK\n"
    assert supervisor["reason"] == "exited" and supervisor["returncode"] == 0
    assert supervisor["error"] is None
    assert output.stat().st_mode & 0o777 == 0o600
    assert receipt.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        screen.run_supervised(
            str(apptainer), image, workspace, ["/bin/true"],
            output_path=output, receipt_path=tmp_path / "duplicate.receipt.json", seconds=3,
        )


def test_exact_production_supervisor_timeout_and_output_cap(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    monkeypatch.setattr(screen.os, "readlink", lambda _path: "net:[test-host-namespace]")
    process, timed, _ = run_production_supervisor(
        tmp_path, "import time;time.sleep(5)", seconds=0.2, cap=32,
    )
    assert timed["reason"] == "deadline"
    assert process.returncode == 0

    monkeypatch.setattr(screen, "MAX_EPISODE_OUTPUT", 32)
    apptainer = fake_apptainer(tmp_path / "apptainer")
    image = tmp_path / "fixed.sif"; workspace = tmp_path / "workspace.img"
    image.touch(); workspace.touch()
    output = tmp_path / "overflow.out"; receipt = tmp_path / "overflow.receipt.json"
    with pytest.raises(RuntimeError, match="output_limit"):
        screen.run_supervised(
            str(apptainer), image, workspace,
            [sys.executable, "-c", "import os,time;os.write(1,b'x'*100000);time.sleep(5)"],
            output_path=output, receipt_path=receipt, seconds=3,
        )
    assert len(output.read_bytes()) == 32
    assert json.loads(receipt.read_text())["reason"] == "output_limit"


def test_exact_production_supervisor_owner_eof_cancels_child(tmp_path):
    marker = tmp_path / "child.pid"
    code = ("import os,subprocess,time; "
            f"p=subprocess.Popen([{sys.executable!r},'-c','import time;time.sleep(20)']); "
            f"open({str(marker)!r},'w').write(str(p.pid)); time.sleep(20)")
    process, record, _ = run_production_supervisor(
        tmp_path, code, seconds=5, cap=64, owner_eof_after=0.2,
    )
    assert record["reason"] == "owner_eof"
    child_pid = int(marker.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(child_pid, 0)
    assert process.returncode == 0


def test_supervisor_records_internal_output_open_error_before_cleanup(tmp_path):
    tmp_path.chmod(0o700)
    output = tmp_path / "output-is-a-directory"
    output.mkdir(mode=0o700)
    receipt = tmp_path / "receipt.json"
    receipt_fd = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(receipt_fd)
    owner_r, owner_w = os.pipe()
    process = subprocess.Popen(
        [sys.executable, str(SUPERVISOR), "--owner-fd", str(owner_r), "--out", str(output),
         "--receipt", str(receipt), "--seconds", "5", "--cap", "64", "--",
         sys.executable, "-c", "import time;time.sleep(20)"],
        pass_fds=(owner_r,), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    os.close(owner_r)
    try:
        stdout, stderr = process.communicate(timeout=8)
    finally:
        os.close(owner_w)
        if process.poll() is None:
            process.kill()
            process.wait()
    assert process.returncode == 1, (stdout, stderr)
    record = json.loads(receipt.read_text())
    assert record["reason"] == "internal_error"
    assert record["error"]["type"] == "FileExistsError"
    assert "File exists" in record["error"]["message"]
    assert str(output) not in record["error"]["message"]
    assert record["error"]["errno"] == 17
    assert record["retained_bytes"] == 0
