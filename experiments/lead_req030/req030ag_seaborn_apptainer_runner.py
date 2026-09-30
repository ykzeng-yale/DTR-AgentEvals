"""Fail-closed join of pinned mini-swe, native HF adapter and Apptainer tools.

This module is an inert-capable runner primitive, not a model/run release.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping

from experiments.lead_req030.seaborn_public_input import parse_public_projection, prepare_seaborn_default_agent

TERMINAL_MARKER = "COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT"
MAX_EVENT_BYTES = 32 * 1024 * 1024
MAX_TRAJECTORY_BYTES = 32 * 1024 * 1024
MAX_TOOL_SECONDS = 600
MAX_OUTPUT_BYTES = 4 * 1024 * 1024
MAX_ACTION_BYTES = 1024 * 1024
MAX_REQUEST_EVENT_BYTES = 8 * 1024 * 1024
MAX_RESPONSE_EVENT_BYTES = 1024 * 1024
MIN_WORKSPACE_FREE_BYTES = 64 * 1024 * 1024
MAX_SUPERVISOR_RECEIPT_BYTES = 16 * 1024


def _read_private_artifact(path: Path, cap: int) -> bytes:
    """Read a bounded owned regular receipt/output without following a symlink."""
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size > cap):
            raise ValueError(f"{path.name} is not a bounded private regular artifact")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(cap + 1)
        if len(data) != info.st_size or len(data) > cap:
            raise ValueError(f"{path.name} changed or exceeded its byte cap")
        return data
    finally:
        os.close(fd)


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key in supervisor receipt")
        result[key] = value
    return result


def _supervisor_record(data: bytes, *, cap: int) -> dict[str, Any]:
    """Accept the production AG supervisor contract, including explicit no-error."""
    record = json.loads(data, object_pairs_hook=_unique_json_object)
    fields = {"reason", "pid", "returncode", "retained_bytes", "elapsed", "error"}
    if not isinstance(record, dict) or set(record) != fields:
        raise ValueError("supervisor receipt schema mismatch")
    if record["error"] is not None:
        raise ValueError("supervisor reported an internal error")
    # Owner loss and startup/internal failures cannot be ordinary tool feedback.
    if record["reason"] not in {"exited", "deadline", "output_limit"}:
        raise ValueError("supervisor did not finish a supervised command")
    if type(record["pid"]) is not int or record["pid"] <= 0:
        raise ValueError("supervisor command PID is malformed")
    if type(record["returncode"]) is not int:
        raise ValueError("supervisor command return code is malformed")
    count = record["retained_bytes"]
    if type(count) is not int or not 0 <= count <= cap:
        raise ValueError("supervisor retained byte count is malformed")
    elapsed = record["elapsed"]
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        raise ValueError("supervisor elapsed time is malformed")
    if record["reason"] == "output_limit" and count != cap:
        raise ValueError("supervisor output limit receipt is inconsistent")
    return record


def _reap_after_owner_close(proc: subprocess.Popen) -> None:
    """Give the pinned supervisor its cleanup window before stopping it."""
    try:
        proc.wait(timeout=7)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _pinned_file(path: str | Path, expected: str, label: str) -> Path:
    source = Path(path)
    if stat.S_ISLNK(source.lstat().st_mode):
        raise ValueError(f"{label} path must not be a symbolic link")
    result = source.resolve(strict=True)
    if not stat.S_ISREG(result.lstat().st_mode) or sha256_file(result) != expected:
        raise ValueError(f"{label} is not the pinned regular file")
    return result


def _new_private_directory(path: str | Path) -> Path:
    target = Path(path)
    parent = target.parent.resolve(strict=True)
    st = parent.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) & 0o077:
        raise ValueError("receipt parent must be an owned private directory")
    target = parent / target.name
    target.mkdir(mode=0o700, exist_ok=False)
    st = target.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) != 0o700:
        raise ValueError("run directory is not private and owned")
    return target.resolve(strict=True)


def _exclusive_write(path: Path, data: bytes, cap: int) -> str:
    if len(data) > cap:
        raise ValueError(f"{path.name} exceeds its byte cap")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        view = memoryview(data)
        while view:
            n = os.write(fd, view)
            if n <= 0:
                raise OSError("short private artifact write")
            view = view[n:]
        os.fsync(fd)
    finally:
        os.close(fd)
    return hashlib.sha256(data).hexdigest()


class DurableEventLog:
    """Append-only bounded JSONL; fsync each record before accepting it."""

    def __init__(self, directory: Path, cap: int = MAX_EVENT_BYTES):
        self.path = directory / "events.jsonl"
        self.cap, self.size, self.sequence = cap, 0, 0
        self.fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)

    def write(self, event: Mapping[str, Any]) -> None:
        data = (json.dumps({"sequence": self.sequence + 1, **dict(event)}, sort_keys=True,
                           separators=(",", ":"), ensure_ascii=False) + "\n").encode()
        if self.size + len(data) > self.cap:
            raise RuntimeError("durable event log byte cap exceeded")
        view = memoryview(data)
        while view:
            n = os.write(self.fd, view)
            if n <= 0:
                raise OSError("short event log write")
            view = view[n:]
        os.fsync(self.fd)
        self.size += len(data)
        self.sequence += 1

    def require_remaining(self, byte_count: int) -> None:
        if byte_count < 0 or self.size + byte_count > self.cap:
            raise RuntimeError("durable event log has insufficient reserved capacity")

    def close(self) -> None:
        if self.fd is not None:
            os.fsync(self.fd)
            os.close(self.fd)
            self.fd = None


class ApptainerToolEnvironment:
    """Execute only inside one pinned image/workspace through bounded_supervisor."""

    def __init__(self, *, apptainer: str, image: str | Path, image_sha256: str,
                 workspace_image: str | Path, workspace_sha256: str,
                 supervisor: str | Path, supervisor_sha256: str, run_dir: Path,
                 event_log: DurableEventLog, tool_timeout_seconds: int,
                 output_cap_bytes: int, action_cap_bytes: int, expected_base_commit: str):
        if not os.path.isabs(apptainer):
            raise ValueError("Apptainer executable must be an absolute path")
        if not 0 < tool_timeout_seconds <= MAX_TOOL_SECONDS:
            raise ValueError("tool timeout must be in 1..600 seconds")
        if not 0 < output_cap_bytes <= MAX_OUTPUT_BYTES or not 0 < action_cap_bytes <= MAX_ACTION_BYTES:
            raise ValueError("output/action cap exceeds hard runner maximum")
        apptainer_path = Path(apptainer).resolve(strict=True)
        apptainer_stat = apptainer_path.lstat()
        if not stat.S_ISREG(apptainer_stat.st_mode) or not os.access(apptainer_path, os.X_OK):
            raise ValueError("Apptainer executable must resolve to an executable regular file")
        version = subprocess.run([str(apptainer_path), "--version"], capture_output=True,
                                 timeout=10, check=True, text=True)
        runtime_version = (version.stdout or version.stderr).strip()
        if not runtime_version or len(runtime_version) > 512:
            raise ValueError("Apptainer runtime version is missing or malformed")
        self.apptainer = str(apptainer_path)
        self.apptainer_sha256 = sha256_file(apptainer_path)
        self.apptainer_version = runtime_version
        self.image = _pinned_file(image, image_sha256, "task image")
        self.workspace_image = _pinned_file(workspace_image, workspace_sha256, "workspace image")
        self.supervisor = _pinned_file(supervisor, supervisor_sha256, "supervisor")
        self.image_sha256 = image_sha256
        self.workspace_initial_sha256 = workspace_sha256
        self.workspace_final_sha256 = None
        self.supervisor_sha256 = supervisor_sha256
        self.image_identity = self.image.stat()
        self.run_dir, self.event_log = run_dir, event_log
        if len(expected_base_commit) != 40 or any(c not in "0123456789abcdef" for c in expected_base_commit):
            raise ValueError("expected task base must be a canonical Git commit")
        self.expected_base_commit = expected_base_commit
        self.tool_timeout_seconds, self.output_cap_bytes, self.action_cap_bytes = (
            tool_timeout_seconds, output_cap_bytes, action_cap_bytes
        )
        self.platform = platform.uname()._asdict()
        self.template_vars = {k: self.platform[k] for k in ("system", "release", "version", "machine")}
        self.host_net_id = os.readlink("/proc/self/ns/net")
        self.action_count = 0
        self.preflight_attempted = False
        self.preflight_result = None
        self.closed = False

    def get_template_vars(self, **kwargs: Any) -> dict[str, Any]:
        if kwargs:
            raise ValueError("environment template overrides are forbidden")
        return dict(self.template_vars)

    def serialize(self) -> dict[str, Any]:
        return {"info": {"config": {
            "environment_type": "SeabornApptainerToolEnvironment",
            "image_sha256": self.image_sha256,
            "workspace_initial_sha256": self.workspace_initial_sha256,
            "workspace_final_sha256": self.workspace_final_sha256,
            "expected_base_commit": self.expected_base_commit,
            "supervisor_sha256": self.supervisor_sha256,
            "tool_timeout_seconds": self.tool_timeout_seconds,
            "output_cap_bytes": self.output_cap_bytes,
            "action_cap_bytes": self.action_cap_bytes,
            "network": "none", "workspace": "/testbed", "host_platform": self.platform,
            "apptainer_sha256": self.apptainer_sha256, "apptainer_version": self.apptainer_version,
        }}}

    def _container_argv(self, command: str, cwd: str) -> list[str]:
        if cwd not in ("", "/testbed"):
            raise ValueError("only the bound /testbed working directory is available")
        return [self.apptainer, "exec", "--containall", "--cleanenv", "--no-home",
                "--no-mount", "hostfs,bind-paths", "--net", "--network", "none",
                "--pwd", "/testbed", "--env", f"DTR_HOST_NET_ID={self.host_net_id}",
                "--bind", f"{self.workspace_image}:/testbed:image-src=/",
                str(self.image), "/bin/bash", "-lc", command]

    def _assert_task_image_unchanged(self) -> None:
        current = self.image.stat()
        if (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) != (
                self.image_identity.st_dev, self.image_identity.st_ino,
                self.image_identity.st_size, self.image_identity.st_mtime_ns):
            raise RuntimeError("task image identity changed during this run")

    def _bounded_command(self, command: str, *, label: str, seconds: int) -> tuple[dict, bytes]:
        if self.closed:
            raise RuntimeError("environment is closed")
        if not isinstance(command, str) or len(command.encode()) > self.action_cap_bytes:
            raise ValueError("command is not text or exceeds the action byte cap")
        if not 0 < seconds <= self.tool_timeout_seconds:
            raise ValueError("per-command timeout exceeds frozen limit")
        self._assert_task_image_unchanged()
        index = self.action_count + 1
        stem = f"{label}-{index:04d}"
        out, receipt = self.run_dir / f"{stem}.out", self.run_dir / f"{stem}.json"
        self.event_log.write({"event": f"{label}_start", "index": index,
            "command_sha256": hashlib.sha256(command.encode()).hexdigest(),
            "command_bytes": len(command.encode()), "timeout_seconds": seconds,
            "output_cap_bytes": self.output_cap_bytes,
            "image_sha256": self.image_sha256, "workspace_initial_sha256": self.workspace_initial_sha256,
            "apptainer_sha256": self.apptainer_sha256, "apptainer_version": self.apptainer_version})
        fd = os.open(receipt, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        os.fsync(fd); os.close(fd)
        read_fd, owner_fd = os.pipe()
        argv = [sys.executable, str(self.supervisor), "--owner-fd", str(read_fd),
                "--out", str(out), "--receipt", str(receipt), "--seconds", str(seconds),
                "--cap", str(self.output_cap_bytes), "--", *self._container_argv(command, "/testbed")]
        started = time.monotonic()
        try:
            proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL, close_fds=True, pass_fds=(read_fd,), start_new_session=True)
        except OSError as exc:
            os.close(read_fd); os.close(owner_fd)
            self.event_log.write({"event": f"{label}_spawn_error", "error_type": type(exc).__name__,
                                  "error": str(exc)[:2048]})
            raise RuntimeError("bounded supervisor spawn failed") from exc
        os.close(read_fd)
        try:
            rc = proc.wait(timeout=seconds + 20)
        except BaseException:
            # Closing this pipe also covers KeyboardInterrupt/caller cancellation.
            # The supervisor owns the command's separate process group.
            os.close(owner_fd)
            _reap_after_owner_close(proc)
            raise
        else:
            os.close(owner_fd)
        elapsed = time.monotonic() - started
        if rc != 0:
            raise RuntimeError(f"bounded supervisor failed: exit={rc}")
        receipt_data = _read_private_artifact(receipt, MAX_SUPERVISOR_RECEIPT_BYTES)
        r = _supervisor_record(receipt_data, cap=self.output_cap_bytes)
        output = _read_private_artifact(out, self.output_cap_bytes)
        if len(output) != r["retained_bytes"] or len(output) > self.output_cap_bytes:
            raise ValueError("supervisor output receipt mismatch")
        if label == "action":
            self.action_count += 1
        finish = {"event": f"{label}_finish", "index": index, "reason": r["reason"],
                  "supervisor_exit": rc, "tool_returncode": r["returncode"],
                  "retained_bytes": len(output), "output_sha256": hashlib.sha256(output).hexdigest(),
                  "supervisor_elapsed_seconds": r["elapsed"], "outer_elapsed_seconds": elapsed,
                  "receipt_sha256": hashlib.sha256(receipt_data).hexdigest()}
        self.event_log.write(finish)
        return ({"output": output.decode("utf-8", errors="replace"),
                 "returncode": r["returncode"] if r["returncode"] is not None else -1,
                 "exception_info": "" if r["reason"] == "exited" else r["reason"],
                 "extra": {"supervisor": finish}}, output)

    def preflight(self) -> dict[str, Any]:
        if self.preflight_attempted:
            raise RuntimeError("workspace preflight is single-use")
        self.preflight_attempted = True
        script = "\n".join([
            "set -euo pipefail",
            'test \"$(readlink /proc/self/ns/net)\" != \"$DTR_HOST_NET_ID\"',
            "test ! -e /home/yz2324",
            "test ! -e /nfs/roberts",
            "if touch /DTR_ROOT_WRITE_TEST 2>/dev/null; then rm -f /DTR_ROOT_WRITE_TEST; exit 90; fi",
            "cd /testbed",
            "test -d .git",
            'test -z \"$(git status --porcelain --untracked-files=all)\"',
            f'expected_base=\"{self.expected_base_commit}\"',
            'head=$(git rev-parse HEAD)',
            'head_tree=$(git rev-parse \"${head}^{tree}\")',
            'base_tree=$(git rev-parse \"${expected_base}^{tree}\")',
            'test \"$head_tree\" = \"$base_tree\"',
            "free=$(df -B1 --output=avail /testbed | tail -n1 | tr -d ' ')",
            'case \"$free\" in ""|*[!0-9]*) exit 91;; esac',
            f"test \"$free\" -ge {MIN_WORKSPACE_FREE_BYTES}",
            'printf \"DTR_PREFLIGHT\\t%s\\t%s\\t%s\\t%s\\t%s\\t%s\\n\" "$head" "$expected_base" "$head_tree" "$base_tree" "$free" "$(df -B1 --output=avail /tmp | tail -n1 | tr -d " \")"',
        ])
        result, raw = self._bounded_command(script, label="preflight", seconds=min(60, self.tool_timeout_seconds))
        if result["returncode"] != 0 or result["exception_info"]:
            raise RuntimeError(f"workspace preflight failed: {result['exception_info'] or result['returncode']}")
        markers = [line for line in raw.decode("utf-8", errors="strict").splitlines()
                   if line.startswith("DTR_PREFLIGHT\t")]
        if len(markers) != 1:
            raise ValueError("workspace preflight marker missing/duplicated")
        fields = markers[0].split("\t")
        if (len(fields) != 7 or fields[2] != self.expected_base_commit
                or any(len(value) != 40 or any(c not in "0123456789abcdef" for c in value)
                       for value in fields[1:5])
                or fields[3] != fields[4] or not fields[5].isdigit() or not fields[6].isdigit()):
            raise ValueError("workspace preflight fields malformed")
        accepted = {"git_head": fields[1], "expected_base_commit": fields[2],
                    "source_tree": fields[3], "base_tree": fields[4],
                    "testbed_free_bytes": int(fields[5]), "tmp_free_bytes": int(fields[6])}
        if accepted["testbed_free_bytes"] < MIN_WORKSPACE_FREE_BYTES:
            raise ValueError("workspace free bytes below minimum")
        self.event_log.write({"event": "workspace_preflight_accepted", **accepted,
            "host_platform": self.platform, "host_net_id": self.host_net_id,
            "image_sha256": self.image_sha256, "workspace_initial_sha256": self.workspace_initial_sha256,
            "apptainer_sha256": self.apptainer_sha256, "apptainer_version": self.apptainer_version})
        self.preflight_result = accepted
        return dict(self.preflight_result)

    def execute(self, action: dict[str, Any], cwd: str = "", *, timeout: int | None = None) -> dict[str, Any]:
        if self.preflight_result is None:
            raise RuntimeError("tool execution forbidden before isolated workspace preflight")
        if cwd not in ("", "/testbed"):
            raise ValueError("requested working directory is outside the bound workspace")
        if not isinstance(action, dict) or set(action) != {"command"}:
            raise ValueError("only a single parsed command action is accepted")
        result, output = self._bounded_command(action["command"], label="action",
            seconds=self.tool_timeout_seconds if timeout is None else timeout)
        lines = output.decode("utf-8", errors="replace").lstrip().splitlines(keepends=True)
        if (lines and lines[0].strip() == TERMINAL_MARKER and result["returncode"] == 0
                and result.get("extra", {}).get("supervisor", {}).get("reason") == "exited"):
            submission = "".join(lines[1:])
            self.event_log.write({"event": "terminal_submission", "action_index": self.action_count,
                "submission_sha256": hashlib.sha256(submission.encode()).hexdigest(),
                "submission_bytes": len(submission.encode())})
            from minisweagent.exceptions import Submitted
            raise Submitted({"role": "exit", "content": submission,
                "extra": {"exit_status": "Submitted", "submission": submission}})
        return result

    def close(self) -> None:
        self.closed = True

    def seal_workspace(self) -> str:
        if self.workspace_final_sha256 is None:
            self.workspace_final_sha256 = sha256_file(self.workspace_image)
            self.event_log.write({"event": "workspace_sealed",
                "workspace_initial_sha256": self.workspace_initial_sha256,
                "workspace_final_sha256": self.workspace_final_sha256,
                "action_count": self.action_count})
        return self.workspace_final_sha256


def run_pinned_agent(*, agent_class: type,
    model_factory: Callable[[Callable[[dict], None], Mapping[str, Any]], Any],
    public_projection: bytes, run_directory: str | Path, apptainer: str,
    image: str | Path, image_sha256: str, workspace_image: str | Path,
    workspace_sha256: str, supervisor: str | Path, supervisor_sha256: str,
    release_id: str, release_sha256: str, step_limit: int,
    wall_time_limit_seconds: int, model_context_limit: int,
    model_max_new_tokens: int, tool_timeout_seconds: int,
    output_cap_bytes: int, action_cap_bytes: int,
    max_consecutive_format_errors: int = 3,
    public_task_parser: Callable[[bytes], Any] | None = None,
    agent_preparer: Callable[..., Any] | None = None) -> dict[str, Any]:
    """Run injected pinned components; no evaluator input path exists in this API."""
    if not release_id or len(release_sha256) != 64 or any(c not in "0123456789abcdef" for c in release_sha256):
        raise ValueError("exact run release identity required")
    if not 0 < model_context_limit <= 32768 or not 0 < model_max_new_tokens < model_context_limit:
        raise ValueError("model token limits invalid or above frozen 32K context")
    if step_limit <= 0 or wall_time_limit_seconds <= 0:
        raise ValueError("finite agent limits required")
    # The default path remains the original closed Seaborn qualification.
    # A prospective multi-task release may inject a separately source-pinned
    # parser/preparer; evaluator payloads are still absent from this API.
    task_parser = parse_public_projection if public_task_parser is None else public_task_parser
    prepare_agent = prepare_seaborn_default_agent if agent_preparer is None else agent_preparer
    task_input = task_parser(public_projection)
    run_dir = _new_private_directory(run_directory)
    journal = DurableEventLog(run_dir)
    env = agent = None
    try:
        env = ApptainerToolEnvironment(apptainer=apptainer, image=image, image_sha256=image_sha256,
            workspace_image=workspace_image, workspace_sha256=workspace_sha256,
            supervisor=supervisor, supervisor_sha256=supervisor_sha256, run_dir=run_dir,
            event_log=journal, tool_timeout_seconds=tool_timeout_seconds,
            output_cap_bytes=output_cap_bytes, action_cap_bytes=action_cap_bytes,
            expected_base_commit=task_input.base_commit)
        preflight = env.preflight()
        prepared = prepare_agent(public_projection, environment=env.get_template_vars(),
            step_limit=step_limit, wall_time_limit_seconds=wall_time_limit_seconds,
            max_consecutive_format_errors=max_consecutive_format_errors, cost_limit=0.0)
        journal.write({"event": "agent_run_start", "release_id": release_id, "release_sha256": release_sha256,
            "public_projection_sha256": prepared.task.source_sha256, "instance_id": prepared.task.instance_id,
            "base_commit": prepared.task.base_commit, "template_source_sha256": prepared.template_source_sha256,
            "action_regex_sha256": hashlib.sha256(prepared.model_config["action_regex"].encode()).hexdigest(),
            "observation_template_sha256": hashlib.sha256(prepared.model_config["observation_template"].encode()).hexdigest(),
            "format_error_template_sha256": hashlib.sha256(prepared.model_config["format_error_template"].encode()).hexdigest(),
            "host_platform": env.platform, "workspace_git_head": preflight["git_head"],
            "workspace_base_tree": preflight["base_tree"],
            "model_context_limit": model_context_limit, "model_max_new_tokens": model_max_new_tokens,
            "agent_step_limit": step_limit, "agent_wall_time_limit_seconds": wall_time_limit_seconds,
            "tool_timeout_seconds": tool_timeout_seconds, "tool_output_cap_bytes": output_cap_bytes,
            "tool_action_cap_bytes": action_cap_bytes, "evaluator_input": "not accepted by runner API"})
        def record_model_event(event: dict) -> None:
            kind = event.get("event")
            routing_fields = ("schedule", "logical_call", "model_action", "per_model_physical_calls")
            if kind in {"routing_decision", "routing_reservation_denied"}:
                required = {"event", "schedule", "logical_call", "decision_index", "physical_calls_before",
                    "per_model_physical_calls_before", "assignment", "randomized_logger", "both_action_reservations",
                    "remaining_logical_calls_including_current", "elapsed_time_eligibility",
                    "remaining_episode_wall_seconds", "episode_deadline_monotonic", "measured_at_monotonic",
                    "workspace_fingerprint"}
                if kind == "routing_decision":
                    required |= {"model_action", "model_id", "revision", "probability", "probability_vector"}
                if set(event) != required:
                    raise ValueError("routing receipt differs from the explicit public ledger schema")
                from experiments.lead_req030.req030ai_schedule_adapter import validate_decision_state
                validate_decision_state({key: event[key] for key in (
                    "remaining_episode_wall_seconds", "episode_deadline_monotonic", "measured_at_monotonic",
                    "workspace_fingerprint")})
                if event["remaining_episode_wall_seconds"] <= 0:
                    raise ValueError("routing acceptance cannot occur after the common episode deadline")
                if (event["schedule"] not in {"SS", "SL", "LS", "LL"}
                        or event["logical_call"] not in {1, 9}
                        or event["decision_index"] != (1 if event["logical_call"] == 1 else 2)
                        or event["assignment"] != "deterministic_fixed_schedule" or event["randomized_logger"] is not False):
                    raise ValueError("invalid fixed-schedule decision receipt")
                reservations = event["both_action_reservations"]
                binding_fields = {"messages_sha256", "rendered_sha256", "input_ids", "input_tokens",
                    "max_new_tokens", "context_limit", "reserved_total_tokens", "admitted", "remaining_input_token_capacity"}
                if set(reservations) != {"S", "L"} or any(set(r) != binding_fields for r in reservations.values()):
                    raise ValueError("both native token reservations are required")
                if kind == "routing_decision":
                    selected = event["schedule"][event["decision_index"] - 1]
                    if (event["model_action"] != selected or event["probability"] != 1.0
                            or event["probability_vector"] != {"S": float(selected == "S"), "L": float(selected == "L")}):
                        raise ValueError("routing receipt is not the assigned deterministic regime")
                encoded = (json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n").encode()
                if len(encoded) > MAX_REQUEST_EVENT_BYTES:
                    raise RuntimeError("routing decision receipt exceeds its 8 MiB cap")
                journal.require_remaining(len(encoded) + MAX_RESPONSE_EVENT_BYTES)
                journal.write(event)
            elif kind == "request":
                encoded = (json.dumps({"sequence": journal.sequence + 1, **event}, sort_keys=True,
                                      separators=(",", ":"), ensure_ascii=False) + "\n").encode()
                if len(encoded) > MAX_REQUEST_EVENT_BYTES:
                    raise RuntimeError("model request receipt exceeds its 8 MiB cap")
                journal.require_remaining(len(encoded) + MAX_RESPONSE_EVENT_BYTES)
                journal.write(event)
            elif kind == "response":
                compact = {key: event[key] for key in (
                    "event", "model_id", "revision", "messages_sha256", "rendered_sha256",
                    "input_tokens", "physical_calls", "output_ids", "output_tokens",
                    "finish_reason", "elapsed_seconds", *routing_fields) if key in event}
                encoded = (json.dumps(compact, sort_keys=True, separators=(",", ":")) + "\n").encode()
                if len(encoded) > MAX_RESPONSE_EVENT_BYTES:
                    raise RuntimeError("model response receipt exceeds its 1 MiB cap")
                journal.write(compact)
            else:
                compact = {key: event[key] for key in ("event", "physical_calls", "error_type", "error",
                                                         "elapsed_seconds", *routing_fields) if key in event}
                journal.write(compact)

        model = model_factory(record_model_event, prepared.model_config)
        protocol = ("query", "format_message", "format_observation_messages", "get_template_vars", "serialize")
        if not all(callable(getattr(model, name, None)) for name in protocol):
            raise TypeError("model factory did not return the pinned mini-swe Model protocol")
        journal.write({"event": "model_factory_ready", "model_serialization": model.serialize()})
        agent = agent_class(model, env, **prepared.agent_config)
        result = agent.run(task=prepared.task.problem_statement)
        env.seal_workspace()
        data = (json.dumps(agent.serialize(), ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
        trajectory_sha = _exclusive_write(run_dir / "trajectory.json", data, MAX_TRAJECTORY_BYTES)
        journal.write({"event": "agent_run_finish", "exit_status": result.get("exit_status", ""),
            "submission_sha256": hashlib.sha256(str(result.get("submission", "")).encode()).hexdigest(),
            "physical_model_calls": getattr(model, "n_calls", None),
            "trajectory_sha256": trajectory_sha, "trajectory_bytes": len(data)})
        return {"result": result, "trajectory_sha256": trajectory_sha, "run_directory": str(run_dir)}
    except BaseException as exc:
        if env is not None and env.workspace_final_sha256 is None:
            try:
                env.seal_workspace()
            except Exception:
                pass
        try:
            journal.write({"event": "agent_run_error", "error_type": type(exc).__name__, "error": str(exc)[:2048]})
        except Exception:
            pass
        if agent is not None:
            try:
                data = (json.dumps(agent.serialize(), ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
                _exclusive_write(run_dir / "trajectory.partial.json", data, MAX_TRAJECTORY_BYTES)
            except Exception:
                pass
        raise
    finally:
        if env is not None:
            env.close()
        journal.close()
