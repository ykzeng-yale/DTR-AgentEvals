"""Unreleased process-owned HF episode execution; no evaluator or grading API.

The CPU caller owns a pipe to an independent guardian. The guardian owns a fresh
exec worker and hard monotonic deadlines; only that worker imports Torch/loads
CUDA. Killing the caller closes the pipe and still triggers worker cleanup.
This module is infrastructure, not an experiment release or GPU qualification.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SELF = Path(__file__).resolve()
UPSTREAM = "work/upstream/mini-swe-agent-04d809ceab9df28f9adaed044884180159172930/src/minisweagent"
REQUIRED_SOURCES = (
    "experiments/lead_req030/req030ai_episode_worker.py",
    "experiments/lead_req030/req030ai_schedule_adapter.py",
    "experiments/lead_req030/req030ag_screen.py",
    "experiments/lead_req030/req030ag_seaborn_apptainer_runner.py",
    "experiments/lead_req030/req030ag_bounded_supervisor.py",
    "experiments/lead_req030/native_hf_text_adapter.py",
    "experiments/lead_req030/seaborn_runner_qualification.py",
    "experiments/lead_req030/seaborn_public_input.py",
    "configs/req030ag_prompt_20260929.json",
    "docs/source_snapshots/req030t_miniswe_agent/default.yaml",
    *(f"{UPSTREAM}/{p}" for p in ("agents/default.py", "exceptions.py", "models/utils/actions_text.py", "utils/serialize.py")),
)
MAX_LIFECYCLE = 128 * 1024
MAX_NATIVE = 256 * 1024 * 1024
MAX_STDOUT = 4 * 1024 * 1024


@dataclass(frozen=True)
class Deadlines:
    load: float = 600
    call: float = 600
    episode: float = 2700
    outer: float = 3600
    term_grace: float = 2
    kill_grace: float = 3
    cleanup_grace: float = 7

    def __post_init__(self):
        for key, value in self.__dict__.items():
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"invalid deadline: {key}")
        if self.load + self.episode > self.outer:
            raise ValueError("outer deadline cannot be shorter than load plus episode")


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def parse_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique)


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_private(path: Path, cap: int) -> bytes:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > cap:
            raise ValueError("artifact is not a bounded regular file")
        data = f.read(cap + 1)
    if len(data) > cap:
        raise ValueError("artifact exceeded cap")
    return data


def write_new(path: Path, value: Any):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(canonical(value)); f.flush(); os.fsync(f.fileno())


class Lifecycle:
    def __init__(self, path: Path):
        self.fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
        self.sequence = 0

    def emit(self, event: str, **extra):
        self.sequence += 1
        measured = time.monotonic()
        data = canonical({"sequence": self.sequence, "event": event, "monotonic": measured, **extra})
        if os.write(self.fd, data) != len(data):
            raise OSError("partial lifecycle receipt write")
        os.fsync(self.fd)
        return measured

    def close(self):
        os.close(self.fd)


def _hex(value, length=64):
    return isinstance(value, str) and re.fullmatch(f"[0-9a-f]{{{length}}}", value) is not None


def _pin(pin: dict, *, cap=None) -> Path:
    if not isinstance(pin, dict) or set(pin) != {"path", "sha256"} or not _hex(pin["sha256"]):
        raise ValueError("invalid exact file pin")
    path = Path(pin["path"])
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise ValueError("pinned input must be an absolute regular file")
    if cap is not None and path.stat().st_size > cap:
        raise ValueError("pinned file exceeds bound")
    if digest_file(path) != pin["sha256"]:
        raise ValueError("pinned file hash mismatch")
    return path


def validate_spec(spec: dict) -> dict:
    """Reject evaluator-bearing keys; all task inputs are public projections."""
    keys = {"schema", "release_sha256", "model_release", "model_id", "public_projection",
            "image", "source_tar", "model_root", "apptainer", "expected_image_head", "source_pins", "schedule"}
    if not isinstance(spec, dict) or set(spec) != keys or spec["schema"] != "dtr.req030ai.episode.v1":
        raise ValueError("invalid public-only episode specification")
    if not _hex(spec["release_sha256"]) or not _hex(spec["expected_image_head"], 40):
        raise ValueError("invalid release/image identity")
    release = spec["model_release"]
    if set(release) != {"release_id", "models", "runtime", "resource_cap", "tasks"}:
        raise ValueError("worker release must contain only model/runtime/public task metadata")
    if len(release["tasks"]) != 1:
        raise ValueError("worker receives exactly one public task")
    task = release["tasks"][0]
    if set(task) != {"instance_id", "repo", "base_commit", "public_projection_sha256"}:
        raise ValueError("non-public task metadata")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+", task["instance_id"]):
        raise ValueError("unsafe task identity")
    if not _hex(task["base_commit"], 40):
        raise ValueError("invalid task base commit")
    if not isinstance(release["models"], dict) or set(release["models"]) != {"models"}:
        raise ValueError("unexpected model metadata fields")
    models = release["models"]["models"]
    from experiments.lead_req030.req030ai_schedule_adapter import MODEL_PINS
    if not isinstance(models, list) or len(models) != 2:
        raise ValueError("exactly two unique frozen model identities required")
    for model in models:
        if not isinstance(model, dict) or set(model) != {"repo", "revision", "files"} or not _hex(model["revision"], 40):
            raise ValueError("invalid model identity")
    if ({(model["repo"], model["revision"]) for model in models}
            != {(pin["repo"], pin["revision"]) for pin in MODEL_PINS.values()}):
        raise ValueError("exactly two unique frozen model identities required")
    if spec["model_id"] not in {m["repo"] for m in models}:
        raise ValueError("selected model missing from frozen pair")
    if spec["schedule"] is not None and spec["schedule"] not in {"SS", "SL", "LS", "LL"}:
        raise ValueError("invalid prospective fixed schedule")
    if spec["schedule"] is not None:
        expected = MODEL_PINS[spec["schedule"][0]]["repo"]
        if spec["model_id"] != expected:
            raise ValueError("model_id must identify the schedule's initial model")
    for model in models:
        for file in model["files"]:
            p = Path(file["path"])
            if set(file) != {"path", "bytes", "sha256"} or p.is_absolute() or ".." in p.parts or not _hex(file["sha256"]):
                raise ValueError("unsafe model asset pin")
    # Exact allowlist avoids forwarding an evaluator/reference bundle through
    # seemingly innocuous release metadata. Runtime values remain prospective.
    if set(release["runtime"]) - {"gpu_model_aliases", "versions", "cuda", "python"}:
        raise ValueError("unexpected runtime metadata")
    if set(release["resource_cap"]) != {"gpu_model"}:
        raise ValueError("unexpected worker resource metadata")
    if set(spec["source_pins"]) != set(REQUIRED_SOURCES):
        raise ValueError("complete exact worker dependency pins required")
    for rel, sha in spec["source_pins"].items():
        if not _hex(sha) or digest_file(ROOT / rel) != sha:
            raise ValueError(f"worker source hash mismatch: {rel}")
    public = _pin(spec["public_projection"], cap=4 * 1024 * 1024)
    value = parse_json(public.read_bytes())
    if set(value) != {"instance_id", "repo", "base_commit", "problem_statement"}:
        raise ValueError("non-public projection fields")
    if any(value[k] != task[k] for k in ("instance_id", "repo", "base_commit")):
        raise ValueError("public projection identity mismatch")
    if spec["public_projection"]["sha256"] != task["public_projection_sha256"]:
        raise ValueError("public projection pin mismatch")
    if not isinstance(value["problem_statement"], str) or not value["problem_statement"].strip():
        raise ValueError("empty public problem statement")
    image = _pin(spec["image"])
    source = _pin(spec["source_tar"], cap=8 * 1024 ** 3)
    apptainer = _pin(spec["apptainer"])
    model_root = Path(spec["model_root"])
    if not model_root.is_absolute() or not model_root.is_dir() or model_root.is_symlink():
        raise ValueError("invalid cached model root")
    return {"public": public, "image": image, "source": source, "apptainer": apptainer, "model_root": model_root}


def measure_workspace_decision_state(path: Path, *, episode_deadline: float) -> dict:
    """Read owned raw sandbox image only; no task text or command is executed.

    The independent guardian bounds stalled I/O. Hash time is part of the common
    episode deadline. Ext3 metadata/allocation are included, so this fingerprint
    does not establish semantic content equality or coupled decision prefixes.
    """
    from experiments.lead_req030.req030ai_schedule_adapter import MAX_WORKSPACE_IMAGE_BYTES, _time_exceeded
    if type(episode_deadline) not in (int, float) or not math.isfinite(episode_deadline):
        raise ValueError("invalid common episode deadline")
    started = time.monotonic()
    if started >= episode_deadline:
        _time_exceeded()
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    digest, count = hashlib.sha256(), 0
    try:
        before = os.fstat(fd)
        if (not stat.S_ISREG(before.st_mode) or before.st_uid != os.getuid()
                or not 0 < before.st_size <= MAX_WORKSPACE_IMAGE_BYTES):
            raise ValueError("workspace measurement requires a bounded owned regular image")
        while True:
            if time.monotonic() >= episode_deadline:
                _time_exceeded()
            chunk = os.read(fd, 8 * 1024 * 1024)
            if not chunk:
                break
            count += len(chunk)
            if count > before.st_size or count > MAX_WORKSPACE_IMAGE_BYTES:
                raise ValueError("workspace image changed or exceeded measurement cap")
            digest.update(chunk)
        after = os.fstat(fd)
        path_after = os.stat(path, follow_symlinks=False)
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
        if count != before.st_size or any(getattr(before, key) != getattr(after, key)
                or getattr(before, key) != getattr(path_after, key) for key in fields):
            raise ValueError("workspace image changed during decision measurement")
    finally:
        os.close(fd)
    measured = time.monotonic()
    if measured >= episode_deadline:
        _time_exceeded()
    return {"remaining_episode_wall_seconds": episode_deadline - measured,
            "episode_deadline_monotonic": episode_deadline, "measured_at_monotonic": measured,
            "workspace_fingerprint": {"method": "sha256_raw_workspace_image", "sha256": digest.hexdigest(),
                "bytes": count, "hash_elapsed_seconds": measured - started, "semantic_content_identity": False}}


RUNTIME_PACKAGES = {"numpy", "torch", "transformers", "huggingface_hub", "tokenizers",
                    "safetensors", "accelerate", "requests", "jinja2"}

def verify_declared_worker_runtime(runtime: dict) -> dict:
    """Worker-side full package/Python binding; parent never imports CUDA."""
    import importlib.metadata
    import platform
    if (not isinstance(runtime, dict) or not isinstance(runtime.get("versions"), dict)
            or set(runtime["versions"]) != RUNTIME_PACKAGES
            or not isinstance(runtime.get("python"), str)
            or runtime["python"] != platform.python_version()):
        raise ValueError("complete exact Python/package runtime contract required")
    versions = {}
    for name, expected in runtime["versions"].items():
        if not isinstance(expected, str) or not expected:
            raise ValueError("invalid runtime version pin")
        observed = importlib.metadata.version(name.replace("_", "-"))
        if name == "torch":
            observed = observed.split("+", 1)[0]
        if observed != expected:
            raise ValueError(f"worker package version mismatch: {name}")
        versions[name] = observed
    return {"python": platform.python_version(), "versions": versions,
            "scope": "fresh worker package/Python check before model loading; CUDA/device checked by pinned loader"}


def execute_worker(spec: dict, directory: Path, *, components=None):
    """Worker-only API. The optional components seam is for inert authored tests."""
    os.umask(0o077)
    journal = Lifecycle(directory / "lifecycle.jsonl")
    try:
        journal.emit("worker_start", pid=os.getpid())
        paths = validate_spec(spec)
        release = spec["model_release"]
        if components is None:
            write_new(directory / "runtime_preflight.json", verify_declared_worker_runtime(release["runtime"]))
            from experiments.lead_req030.req030ag_screen import _load_models, launch_agent_episode
            components = (_load_models, launch_agent_episode)
        load, launch = components
        models, tokenizer, receipt = load(release, paths["model_root"], directory)
        model_ready = journal.emit("model_ready", load_receipt_sha256=hashlib.sha256(canonical(receipt)).hexdigest())
        episode_deadline = model_ready + Deadlines().episode
        def builder(record_event, config):
            from experiments.lead_req030.seaborn_runner_qualification import load_pinned_default_agent
            load_pinned_default_agent()
            def observed_event(event):
                # The accepted durable native request starts the independent
                # deadline. Finish only after output conversion/decode AND the
                # durable response, not merely model.generate() returning.
                record_event(event)
                if event.get("event") == "request":
                    journal.emit("call_start", call=event["physical_calls"])
                elif event.get("event") == "response":
                    journal.emit("call_finish", call=event["physical_calls"])
            if spec["schedule"] is not None:
                from experiments.lead_req030.req030ai_schedule_adapter import FixedScheduleHFAdapter, MODEL_PINS
                return FixedScheduleHFAdapter(schedule=spec["schedule"], tokenizer=tokenizer,
                    models={action: models[pin["repo"]] for action, pin in MODEL_PINS.items()},
                    model_info={action: next(m for m in release["models"]["models"] if m["repo"] == pin["repo"])
                                for action, pin in MODEL_PINS.items()}, record_event=observed_event,
                    measure_decision_state=lambda: measure_workspace_decision_state(
                        directory / "episode" / "workspace.img", episode_deadline=episode_deadline), **config)
            from experiments.lead_req030.native_hf_text_adapter import NativeHFTextAdapter
            info = next(m for m in release["models"]["models"] if m["repo"] == spec["model_id"])
            return NativeHFTextAdapter(tokenizer=tokenizer, model=models[spec["model_id"]],
                model_id=info["repo"], revision=info["revision"], context_limit=16384,
                max_new_tokens=1536, record_event=observed_event, device="cuda:0", **config)

        # This newly created bundle has exactly one public file. No evaluator,
        # grading metadata, hidden tests or reference patch path enters launch.
        public_dir = directory / "public_bundle" / "public"
        public_dir.mkdir(mode=0o700, parents=True)
        task = release["tasks"][0]
        public_data = read_private(paths["public"], 4 * 1024 * 1024)
        if hashlib.sha256(public_data).hexdigest() != task["public_projection_sha256"]:
            raise ValueError("public projection changed after admission")
        public_target = public_dir / f"{task['instance_id']}.json"
        with public_target.open("xb") as file:
            file.write(public_data)
        public_target.chmod(0o400)
        episode_dir = directory / "episode"
        episode_dir.mkdir(mode=0o700)
        outcome = launch(model_id=spec["model_id"],
            model_info=next(m for m in release["models"]["models"] if m["repo"] == spec["model_id"]),
            model=models[spec["model_id"]], tokenizer=tokenizer, task=task, release=release,
            bundle=directory / "public_bundle", model_run_dir=episode_dir / "agent",
            image=paths["image"], source_tar=paths["source"], workspace_image=episode_dir / "workspace.img",
            apptainer=str(paths["apptainer"]), release_sha256=spec["release_sha256"],
            event_parent=episode_dir, expected_image_head=spec["expected_image_head"],
            model_factory_builder=builder)
        if spec["schedule"] is not None:
            from experiments.lead_req030.req030ai_schedule_adapter import MODEL_PINS
            outcome.pop("model_id", None); outcome.pop("revision", None)
            outcome.update({"schedule": spec["schedule"], "initial_model_id": spec["model_id"],
                            "model_pins": {a: dict(p) for a, p in MODEL_PINS.items()},
                            "assignment": "deterministic fixed schedule; not randomized/OPE"})
        write_new(directory / "worker_result.json", outcome)
        journal.emit("episode_finish", result_sha256=digest_file(directory / "worker_result.json"))
    except BaseException as exc:
        # Failure to persist this event is itself an unknown outcome.
        journal.emit("worker_error", error_type=type(exc).__name__)
        raise
    finally:
        journal.close()


def lifecycle_state(path: Path, *, final=False) -> dict:
    state = {"started": None, "ready": None, "active_call": None, "calls": 0, "call_durations": [],
             "finished_calls": 0, "finish": None, "error": None, "events": []}
    if not path.exists():
        return state
    raw = read_private(path, MAX_LIFECYCLE)
    if raw and not raw.endswith(b"\n"):
        if final:
            raise ValueError("incomplete lifecycle receipt")
        raw = raw[:raw.rfind(b"\n") + 1] if b"\n" in raw else b""
    previous = -math.inf
    for seq, line in enumerate(raw.splitlines(), 1):
        event = parse_json(line)
        t, kind = event.get("monotonic"), event.get("event")
        if event.get("sequence") != seq or type(t) not in (int, float) or not math.isfinite(t) or t < previous or t > time.monotonic() + 1:
            raise ValueError("invalid lifecycle sequence/time")
        if state["finish"] or state["error"]:
            raise ValueError("event after terminal lifecycle receipt")
        previous = t
        if kind == "worker_start" and seq == 1:
            state["started"] = t
        elif kind == "model_ready" and state["started"] is not None and state["ready"] is None:
            state["ready"] = t
        elif kind == "call_start" and state["ready"] is not None and state["active_call"] is None and event.get("call") == state["calls"] + 1:
            state["calls"] += 1; state["active_call"] = t
        elif kind == "call_finish" and state["active_call"] is not None and event.get("call") == state["calls"]:
            state["call_durations"].append(t - state["active_call"])
            state["finished_calls"] += 1; state["active_call"] = None
        elif kind == "episode_finish" and state["ready"] is not None and state["active_call"] is None:
            state["finish"] = event
        elif kind == "worker_error" and state["started"] is not None:
            state["error"] = event
        else:
            raise ValueError("invalid lifecycle transition")
        state["events"].append(event)
    return state


def native_receipts(directory: Path, lifecycle: dict) -> tuple[list, bool]:
    path = directory / "episode" / "agent" / "events.jsonl"
    if not path.exists():
        if lifecycle["ready"] is None:
            return [], True
        raise ValueError("missing native event log after model readiness")
    raw = read_private(path, MAX_NATIVE)
    if raw and not raw.endswith(b"\n"):
        raise ValueError("incomplete native receipt")
    events = [parse_json(line) for line in raw.splitlines()]
    if not events or any(e.get("sequence") != i for i, e in enumerate(events, 1)):
        raise ValueError("invalid native event sequence")
    requests, responses, pending = 0, 0, False
    for event in events:
        if event.get("event") == "request":
            requests += 1
            if pending or event.get("physical_calls") != requests:
                raise ValueError("invalid native request accounting")
            pending = True
        elif event.get("event") == "response":
            if not pending or event.get("physical_calls") != requests:
                raise ValueError("invalid native response accounting")
            responses += 1; pending = False
        elif event.get("event") == "generation_error":
            if not pending:
                raise ValueError("generation error lacks request")
    if requests != lifecycle["calls"] or responses != lifecycle["finished_calls"]:
        raise ValueError("native and worker call receipts disagree")
    return events, True


def tool_receipts_clean(directory: Path, events: list) -> bool:
    paths = []
    for event in events:
        kind = event.get("event", "")
        if kind not in {"preflight_start", "action_start"}:
            continue
        index = event.get("index")
        if type(index) is not int or index <= 0:
            raise ValueError("invalid tool receipt index")
        paths.append(directory / "episode" / "agent" / f"{kind[:-6]}-{index:04d}.json")
    # Harvest is a separate container operation after agent_run_finish, outside
    # the native tool ledger. Its authored script is the earliest durable marker.
    if (directory / "episode" / "harvest.sh").exists():
        paths.append(directory / "episode" / "patch.supervisor.json")
    for path in paths:
        if not path.exists() or not path.stat().st_size:
            return False
        receipt = parse_json(read_private(path, 16384))
        if (set(receipt) != {"reason", "pid", "returncode", "retained_bytes", "elapsed", "error"}
                or receipt["reason"] not in {"exited", "deadline", "owner_eof", "owner_absent_before_start", "output_limit"}
                or receipt["error"] is not None or type(receipt["retained_bytes"]) is not int
                or not 0 <= receipt["retained_bytes"] <= MAX_STDOUT
                or type(receipt["elapsed"]) not in (int, float) or not math.isfinite(receipt["elapsed"])
                or receipt["elapsed"] < 0):
            raise ValueError("tool supervisor cleanup failure")
        if receipt["pid"] is None:
            if receipt["returncode"] is not None or receipt["reason"] != "owner_absent_before_start":
                raise ValueError("tool supervisor missing child identity")
        elif type(receipt["pid"]) is not int or receipt["pid"] <= 0 or type(receipt["returncode"]) is not int:
            raise ValueError("tool supervisor has no reaped-child receipt")
    return True


def _terminate_reap(proc, deadlines: Deadlines) -> tuple[bool, bool, str | None]:
    killed = False; signal_error = None
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    except OSError as exc:
        signal_error = type(exc).__name__
    try:
        proc.wait(timeout=deadlines.term_grace)
    except subprocess.TimeoutExpired:
        pass
    # Kill remaining members even after the main worker exited on TERM.
    try:
        os.killpg(proc.pid, signal.SIGKILL); killed = True
    except ProcessLookupError:
        pass
    except OSError as exc:
        signal_error = type(exc).__name__
    try:
        proc.wait(timeout=deadlines.kill_grace)
    except subprocess.TimeoutExpired:
        return False, killed, signal_error
    return True, killed, signal_error


def guard_worker(*, owner_fd: int, command: list[str], directory: Path,
                 deadlines: Deadlines = Deadlines()) -> dict:
    """Independent guardian; authored command injection is only a fixture seam."""
    started = time.monotonic(); proc = None; reason = "internal_error"; state = None
    cleanup = False; reaped = False; killed = False; retained = 0; receipt_error = None
    sel = selectors.DefaultSelector()
    sel.register(owner_fd, selectors.EVENT_READ, "owner")
    output_fd = None
    try:
        # No worker may start after an already dead owner.
        if sel.select(0):
            reason = "owner_absent_before_start"
        else:
            output_fd = os.open(directory / "worker.out", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            proc = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, start_new_session=True, close_fds=True)
            os.set_blocking(proc.stdout.fileno(), False)
            sel.register(proc.stdout, selectors.EVENT_READ, "output")
            while True:
                state = lifecycle_state(directory / "lifecycle.jsonl")
                now = time.monotonic()
                if now - started >= deadlines.outer:
                    reason = "outer_deadline"; break
                if (state["ready"] if state["ready"] is not None else now) - started >= deadlines.load:
                    reason = "load_deadline"; break
                episode_end = state["finish"]["monotonic"] if state["finish"] else now
                if state["ready"] is not None and episode_end - state["ready"] >= deadlines.episode:
                    reason = "episode_deadline"; break
                if (any(d >= deadlines.call for d in state["call_durations"])
                        or state["active_call"] is not None and now - state["active_call"] >= deadlines.call):
                    reason = "call_deadline"; break
                if proc.poll() is not None and not any(k.data == "output" for k in sel.get_map().values()):
                    reason = "exited"; break
                for key, _ in sel.select(.02):
                    if key.data == "owner":
                        if os.read(owner_fd, 4096) == b"":
                            reason = "owner_eof"; break
                    else:
                        data = os.read(proc.stdout.fileno(), 65536)
                        if not data:
                            sel.unregister(proc.stdout)
                        else:
                            room = MAX_STDOUT - retained
                            os.write(output_fd, data[:room]); retained += min(len(data), room)
                            if len(data) > room:
                                reason = "output_limit"; break
                if reason in {"owner_eof", "output_limit"}:
                    break
    except BaseException as exc:
        reason = "guardian_error"; receipt_error = type(exc).__name__
    finally:
        if proc is not None:
            reaped, killed, signal_error = _terminate_reap(proc, deadlines)
            if signal_error:
                receipt_error = signal_error
            # Retain bytes already in the pipe even after a deadline/owner EOF.
            while output_fd is not None:
                try:
                    data = os.read(proc.stdout.fileno(), 65536)
                except BlockingIOError:
                    break
                if not data:
                    break
                room = MAX_STDOUT - retained
                os.write(output_fd, data[:room]); retained += min(len(data), room)
        else:
            reaped = True
        if output_fd is not None:
            os.fsync(output_fd); os.close(output_fd)
        sel.close()
        os.close(owner_fd)
        try:
            state = lifecycle_state(directory / "lifecycle.jsonl", final=True)
            if proc is not None and state["started"] is None:
                raise ValueError("missing worker startup receipt")
            events, _ = native_receipts(directory, state)
            until = time.monotonic() + deadlines.cleanup_grace
            while reaped:
                cleanup = tool_receipts_clean(directory, events)
                if cleanup or time.monotonic() >= until:
                    break
                time.sleep(.02)
            if receipt_error is not None:
                cleanup = False
        except Exception as exc:
            receipt_error = type(exc).__name__; cleanup = False
        status = "infrastructure_unknown"
        eligible = False
        outcome = None
        if reason in {"call_deadline", "episode_deadline"} and reaped and cleanup and receipt_error is None:
            status = "operational_time_limit"
            outcome = {"agent_exit_status": "TimeExceeded", "submission_eligible": False,
                       "grade": {"graded": True, "resolved": False, "reason": "hard_deadline_no_submission"}}
        elif reason == "exited" and proc.returncode == 0 and reaped and cleanup and receipt_error is None:
            try:
                if state["finish"] is None:
                    raise ValueError("worker exited without terminal receipt")
                raw = read_private(directory / "worker_result.json", 8 * 1024 * 1024)
                if hashlib.sha256(raw).hexdigest() != state["finish"]["result_sha256"]:
                    raise ValueError("worker result hash mismatch")
                outcome = parse_json(raw)
                eligible = outcome.get("submission_eligible") is True
                status = "episode_complete"
            except Exception as exc:
                receipt_error = type(exc).__name__
        result = {"schema": "dtr.req030ai.guardian.v1", "status": status, "reason": reason,
                  "worker_pid": proc.pid if proc else None, "worker_returncode": proc.returncode if proc else None,
                  "worker_reaped": reaped, "kill_sent": killed, "cleanup_verified": cleanup,
                  "abort_batch": not (reaped and cleanup), "submission_eligible": eligible,
                  "outcome": outcome, "receipt_error": receipt_error,
                  "retained_output_bytes": retained, "elapsed_seconds": time.monotonic() - started,
                  "deadline_seconds": deadlines.__dict__}
        # All invocations correspond to assigned model slots. Infrastructure
        # uncertainty never removes that slot from the operational denominator.
        result.update({"assigned_slot_retained": True,
                       "operational_resolution": 0 if status != "episode_complete" else None,
                       "algorithmic_correctness": "unknown"})
        write_new(directory / "guardian_result.json", result)
    return result


def run_episode(spec: dict, directory: Path) -> dict:
    """CPU-only coordinator; exact default deadlines, no arbitrary worker command."""
    if "torch" in sys.modules and getattr(sys.modules["torch"].cuda, "is_initialized", lambda: True)():
        raise RuntimeError("coordinator must not own an initialized CUDA context")
    directory = Path(directory).absolute()
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    write_new(directory / "spec.json", spec)
    spec_sha = digest_file(directory / "spec.json")
    read_fd, owner_fd = os.pipe()
    guardian = None
    try:
        guardian = subprocess.Popen([sys.executable, str(SELF), "guard", "--owner-fd", str(read_fd),
            "--directory", str(directory), "--spec-sha256", spec_sha], pass_fds=(read_fd,),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            close_fds=True, start_new_session=True)
        os.close(read_fd); read_fd = None
        guardian.wait(timeout=Deadlines().outer + 30)
    finally:
        if read_fd is not None:
            os.close(read_fd)
        os.close(owner_fd)
        if guardian is not None and guardian.poll() is None:
            # Owner EOF is the independent cancellation path; allow cleanup.
            try:
                guardian.wait(timeout=20)
            except subprocess.TimeoutExpired as exc:
                raise RuntimeError("guardian cleanup unknown; abort batch without another worker") from exc
    if guardian.returncode != 0:
        raise RuntimeError("guardian failed; cleanup unknown, abort batch")
    return parse_json(read_private(directory / "guardian_result.json", 8 * 1024 * 1024))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("worker", "guard"))
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--spec-sha256", required=True)
    parser.add_argument("--owner-fd", type=int)
    args = parser.parse_args()
    raw = read_private(args.directory / "spec.json", 8 * 1024 * 1024)
    if hashlib.sha256(raw).hexdigest() != args.spec_sha256:
        raise ValueError("worker specification hash mismatch")
    if args.mode == "worker":
        execute_worker(parse_json(raw), args.directory)
    else:
        if args.owner_fd is None:
            raise ValueError("guardian owner pipe required")
        guard_worker(owner_fd=args.owner_fd, command=[sys.executable, str(SELF), "worker",
            "--directory", str(args.directory), "--spec-sha256", args.spec_sha256], directory=args.directory)


if __name__ == "__main__":
    main()
