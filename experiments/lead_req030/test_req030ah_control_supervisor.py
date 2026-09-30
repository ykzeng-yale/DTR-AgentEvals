"""Inert checks of the production control/supervisor join and owner lifetime.

The fake Apptainer recognizes fixed authored tokens and never evaluates its
arguments. The supervisor and child processes are real. These tests establish
process/receipt behavior only; they do not qualify container isolation.
"""
from __future__ import annotations

import errno
import json
import os
import signal
import sys
import threading
import time

import pytest

from experiments.lead_req030 import req030ag_screen as shared


NORMAL = "DTR_AUTHORED_CONTROL_NORMAL"
EXIT7 = "DTR_AUTHORED_CONTROL_EXIT7"
SLOW = "DTR_AUTHORED_CONTROL_SLEEP"


@pytest.fixture
def control(tmp_path, monkeypatch):
    tmp_path.chmod(0o700)
    readlink = os.readlink
    monkeypatch.setattr(shared.os, "readlink", lambda path, *args, **kwargs:
        "net:[inert-host]" if str(path) == "/proc/self/ns/net" else
        readlink(path, *args, **kwargs))
    executable = tmp_path / "apptainer"
    executable.write_text(f'''#!{sys.executable}
import os, sys, time
a = sys.argv[1:]
assert a[:11] == ["exec", "--containall", "--cleanenv", "--no-home", "--no-mount",
    "hostfs,bind-paths", "--net", "--network", "none", "--pwd", "/testbed"]
assert a[11:13] == ["--env", "DTR_HOST_NET_ID=net:[inert-host]"]
assert a[13] == "--bind" and a[14].endswith(":/testbed:image-src=/")
if a[-1] == {NORMAL!r}:
    print("INERT_CONTROL_OK")
elif a[-1] == {EXIT7!r}:
    print("INERT_CONTROL_EXIT7"); raise SystemExit(7)
elif a[-1] == {SLOW!r}:
    print(os.getpid(), flush=True); time.sleep(30)
else:
    raise SystemExit("unapproved inert command")
''')
    executable.chmod(0o700)
    image = tmp_path / "task.sif"; image.write_bytes(b"inert image")
    workspace = tmp_path / "workspace.img"; workspace.write_bytes(b"inert workspace")
    output, receipt = tmp_path / "command.out", tmp_path / "command.json"

    def run(command=NORMAL, seconds=3):
        return shared.run_supervised(str(executable), image, workspace, [command],
            output_path=output, receipt_path=receipt, seconds=seconds)

    return run, output, receipt


def assert_gone(pid):
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


@pytest.mark.parametrize("command,returncode,expected", [
    (NORMAL, 0, b"INERT_CONTROL_OK\n"),
    (EXIT7, 7, b"INERT_CONTROL_EXIT7\n"),
])
def test_real_supervisor_returns_exact_receipt_and_reaps_child(control, command, returncode, expected):
    run, output, receipt_path = control
    raw, receipt = run(command)
    assert raw == expected
    assert set(receipt) == {"reason", "pid", "returncode", "retained_bytes", "elapsed", "error"}
    assert receipt["reason"] == "exited" and receipt["error"] is None
    assert receipt["returncode"] == returncode and receipt["retained_bytes"] == len(raw)
    assert receipt["elapsed"] >= 0
    assert receipt == json.loads(receipt_path.read_bytes())
    assert output.stat().st_mode & 0o777 == receipt_path.stat().st_mode & 0o777 == 0o600
    assert_gone(receipt["pid"])


def test_actual_caller_interruption_closes_owner_and_reaps_real_child(control):
    run, output, receipt_path = control
    stop = threading.Event()
    readiness = []

    def interrupt_after_child_start():
        deadline = time.monotonic() + 4
        while not stop.is_set() and time.monotonic() < deadline:
            if output.exists() and output.stat().st_size:
                readiness.append(int(output.read_bytes().strip()))
                os.kill(os.getpid(), signal.SIGUSR1)
                return
            stop.wait(0.01)

    def interrupted(_signum, _frame):
        raise KeyboardInterrupt("authored control cancellation")

    old_handler = signal.signal(signal.SIGUSR1, interrupted)
    thread = threading.Thread(target=interrupt_after_child_start, daemon=True)
    thread.start()
    try:
        with pytest.raises(KeyboardInterrupt, match="authored control cancellation"):
            run(SLOW, seconds=5)
    finally:
        stop.set(); thread.join(timeout=5)
        signal.signal(signal.SIGUSR1, old_handler)
    assert not thread.is_alive() and len(readiness) == 1
    receipt = json.loads(receipt_path.read_bytes())
    assert receipt["reason"] == "owner_eof" and receipt["error"] is None
    assert receipt["pid"] == readiness[0]
    assert_gone(receipt["pid"])


def test_real_command_deadline_is_unknown_not_clean_control(control):
    run, _output, receipt_path = control
    with pytest.raises(RuntimeError, match="did not complete cleanly"):
        run(SLOW, seconds=0.2)
    receipt = json.loads(receipt_path.read_bytes())
    assert receipt["reason"] == "deadline" and receipt["error"] is None
    assert_gone(receipt["pid"])


@pytest.mark.parametrize("failure", [OSError("authored spawn failure"), KeyboardInterrupt("authored spawn cancellation")])
def test_spawn_failure_closes_both_actual_owner_descriptors(control, monkeypatch, failure):
    run, output, receipt_path = control
    real_pipe = os.pipe
    descriptors = []

    def tracked_pipe():
        pair = real_pipe()
        descriptors.extend(pair)
        return pair

    def rejected_spawn(_command, **kwargs):
        assert kwargs["pass_fds"] == (descriptors[0],)
        assert kwargs["start_new_session"] and kwargs["close_fds"]
        assert os.fstat(descriptors[0]) and os.fstat(descriptors[1])
        raise failure

    # Only this fault test injects spawn failure; all lifetime tests above launch
    # the production supervisor and its real child without process mocks.
    monkeypatch.setattr(shared.os, "pipe", tracked_pipe)
    monkeypatch.setattr(shared.subprocess, "Popen", rejected_spawn)
    with pytest.raises(type(failure), match="authored spawn"):
        run()
    assert len(descriptors) == 2
    for fd in descriptors:
        with pytest.raises(OSError) as exc:
            os.fstat(fd)
        assert exc.value.errno == errno.EBADF
    assert not output.exists()
    assert receipt_path.read_bytes() == b""  # Preserved incomplete evidence, not success.
