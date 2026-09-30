"""Conditional allocation-local acquisition storage; never pulls an image.

The caller supplies the exact owned job and an explicit local parent. There is
no shared-filesystem fallback. Receipts contain private paths and stay private
unless the lead independently sanitizes them. This helper is not a run release.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import socket
import stat
import subprocess
import sys
from typing import Callable

SCHEMA = "dtr.req030aj.acquisition.v1"
ALLOWED_FILESYSTEMS = {"ext4", "xfs"}


class AcquisitionRejected(ValueError):
    pass


class CleanupRejected(RuntimeError):
    pass


def _scheduler_record(job_id: str) -> str:
    executable = shutil.which("scontrol")
    if executable is None:
        raise AcquisitionRejected("scontrol unavailable inside allocation")
    result = subprocess.run([executable, "show", "job", "-o", job_id],
        check=True, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=10)
    if len(result.stdout) > 256 * 1024:
        raise AcquisitionRejected("scheduler receipt exceeds bound")
    return result.stdout.decode("utf-8", "strict")


def allocation_identity(*, expected_job_id: str, environment: dict[str, str],
                        uid: int, hostname: str, record: str) -> dict:
    """Check scheduler ownership independently of the process environment."""
    if not isinstance(expected_job_id, str) or re.fullmatch(r"[1-9][0-9]{0,15}", expected_job_id) is None:
        raise AcquisitionRejected("expected job ID must be canonical")
    if environment.get("SLURM_JOB_ID") != expected_job_id:
        raise AcquisitionRejected("not running inside the declared Slurm job")
    if type(uid) is not int or uid < 0 or not isinstance(record, str):
        raise AcquisitionRejected("invalid allocation identity")
    fields = {}
    for token in record.split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        if key in fields:
            raise AcquisitionRejected("duplicate scheduler field")
        fields[key] = value
    user = re.fullmatch(r"([^()\s]+)\(([0-9]+)\)", fields.get("UserId", ""))
    if (fields.get("JobId") != expected_job_id or fields.get("JobState") != "RUNNING"
            or user is None or int(user.group(2)) != uid):
        raise AcquisitionRejected("scheduler does not confirm the running owned job")
    if "SLURM_JOB_USER" in environment and environment["SLURM_JOB_USER"] != user.group(1):
        raise AcquisitionRejected("job-user environment differs from scheduler")
    if "SLURM_JOB_UID" in environment and environment["SLURM_JOB_UID"] != str(uid):
        raise AcquisitionRejected("job-uid environment differs from scheduler")
    # This helper is deliberately single-node. A peer node or login node cannot
    # be accepted merely because a copied SLURM_JOB_ID exists in its environment.
    batch_host = fields.get("BatchHost", "")
    if (not hostname or not batch_host or batch_host == "(null)"
            or hostname.split(".", 1)[0] != batch_host.split(".", 1)[0]):
        raise AcquisitionRejected("current host is not the owned batch host")
    return {"job_id": expected_job_id, "job_state": "RUNNING", "owner_uid": uid,
            "batch_host": batch_host, "ownership_verified": True}


def _unescape_mount(value: str) -> str:
    return re.sub(r"\\(040|011|012|134)",
        lambda match: {"040": " ", "011": "\t", "012": "\n", "134": "\\"}[match.group(1)], value)


def local_mount(path: Path, mountinfo: str) -> dict:
    """Select the longest containing Linux mount, not a substring match."""
    if not path.is_absolute() or not isinstance(mountinfo, str) or len(mountinfo.encode()) > 1024 * 1024:
        raise AcquisitionRejected("invalid or excessive mount inventory")
    matches = []
    for line in mountinfo.splitlines():
        try:
            left, right = line.split(" - ", 1)
            before, after = left.split(), right.split()
            if len(before) < 6 or len(after) < 3:
                raise ValueError("short mount record")
            mountpoint = Path(_unescape_mount(before[4]))
            if not mountpoint.is_absolute():
                raise ValueError("nonabsolute mount")
            if path == mountpoint or mountpoint in path.parents:
                matches.append((len(mountpoint.parts), {
                    "mount_point": str(mountpoint), "filesystem": after[0],
                    "device_major_minor": before[2], "mount_options": before[5]}))
        except (ValueError, IndexError) as exc:
            raise AcquisitionRejected("malformed mount inventory") from exc
    if not matches:
        raise AcquisitionRejected("no containing mount found")
    depth = max(x[0] for x in matches)
    deepest = [record for length, record in matches if length == depth]
    if len(deepest) != 1:
        raise AcquisitionRejected("ambiguous containing mount")
    selected = deepest[0]
    if selected["filesystem"] not in ALLOWED_FILESYSTEMS:
        raise AcquisitionRejected("build parent is not ext4 or xfs")
    if "rw" not in selected["mount_options"].split(","):
        raise AcquisitionRejected("build mount is not writable")
    return selected


def _open_directory_without_links(path: Path) -> int:
    if not path.is_absolute() or ".." in path.parts:
        raise AcquisitionRejected("parent must be an absolute path without traversal")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open("/", flags)
    try:
        for part in path.parts[1:]:
            next_descriptor = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


@dataclass
class AcquisitionContext:
    parent: Path
    private_dir: Path
    tmp_dir: Path
    cache_dir: Path
    receipt: dict
    _parent_device_inode: tuple[int, int]
    _child_device_inode: tuple[int, int]
    _uid: int
    _cleaned: bool = False

    def cleanup(self) -> dict:
        """Delete this saved owned inode only; never follow an external symlink."""
        if self._cleaned:
            return {"cleaned": True, "already_cleaned": True}
        descriptor = None
        try:
            descriptor = _open_directory_without_links(self.parent)
            parent_state = os.fstat(descriptor)
            if (parent_state.st_dev, parent_state.st_ino) != self._parent_device_inode:
                raise CleanupRejected("acquisition parent identity changed")
            child_state = os.stat(self.private_dir.name, dir_fd=descriptor, follow_symlinks=False)
            if (not stat.S_ISDIR(child_state.st_mode) or child_state.st_uid != self._uid
                    or (child_state.st_dev, child_state.st_ino) != self._child_device_inode
                    or child_state.st_mode & 0o077):
                raise CleanupRejected("private acquisition directory identity or permissions changed")
            if not shutil.rmtree.avoids_symlink_attacks:
                raise CleanupRejected("descriptor-safe cleanup is unavailable")
            shutil.rmtree(self.private_dir.name, dir_fd=descriptor)
            self._cleaned = True
            return {"cleaned": True, "already_cleaned": False,
                    "private_device_inode": list(self._child_device_inode)}
        except (OSError, AcquisitionRejected) as exc:
            raise CleanupRejected("cannot verify or clean private acquisition directory") from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.cleanup()


def prepare_acquisition(*, temp_parent: Path, run_id: str, expected_job_id: str,
                        min_free_bytes: int, environment: dict[str, str] | None = None,
                        scheduler_reader: Callable[[str], str] | None = None,
                        mountinfo: str | None = None, hostname: str | None = None,
                        platform: str | None = None,
                        capacity_reader: Callable[[int], object] | None = None) -> AcquisitionContext:
    """Create private tmp/cache only after current allocation/local-disk checks.

    Injectable readers are deterministic test seams; a future immutable launcher
    calls runtime defaults and must pin this source. The function does not set
    global environment variables, download, launch or modify a shared cache.
    """
    if (platform or sys.platform) != "linux":
        raise AcquisitionRejected("allocation-local acquisition requires Linux")
    if not isinstance(run_id, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", run_id) is None:
        raise AcquisitionRejected("invalid immutable run ID")
    if type(min_free_bytes) is not int or min_free_bytes <= 0:
        raise AcquisitionRejected("positive free-capacity floor required")
    if not isinstance(expected_job_id, str) or re.fullmatch(r"[1-9][0-9]{0,15}", expected_job_id) is None:
        raise AcquisitionRejected("expected job ID must be canonical")
    parent = Path(temp_parent)
    if not parent.is_absolute() or ".." in parent.parts:
        raise AcquisitionRejected("parent must be an absolute path without traversal")
    allocation = allocation_identity(expected_job_id=expected_job_id,
        environment=dict(os.environ) if environment is None else environment,
        uid=os.getuid(), hostname=socket.gethostname() if hostname is None else hostname,
        record=(scheduler_reader or _scheduler_record)(expected_job_id))
    if mountinfo is None:
        with Path("/proc/self/mountinfo").open("r", encoding="utf-8") as stream:
            mountinfo = stream.read(1024 * 1024 + 1)
    mount = local_mount(parent, mountinfo)
    descriptor = None
    private_name = f"dtr-{run_id}-{expected_job_id}"
    child_state = None
    try:
        descriptor = _open_directory_without_links(parent)
        parent_state = os.fstat(descriptor)
        device = f"{os.major(parent_state.st_dev)}:{os.minor(parent_state.st_dev)}"
        if mount["device_major_minor"] != device:
            raise AcquisitionRejected("mount inventory differs from opened parent device")
        capacity = (capacity_reader or os.fstatvfs)(descriptor)
        if (type(capacity.f_bavail) is not int or type(capacity.f_frsize) is not int
                or capacity.f_bavail < 0 or capacity.f_frsize <= 0):
            raise AcquisitionRejected("invalid filesystem capacity receipt")
        free_bytes = capacity.f_bavail * capacity.f_frsize
        if type(free_bytes) is not int or free_bytes < min_free_bytes:
            raise AcquisitionRejected("allocation-local free-capacity floor failed")
        os.mkdir(private_name, mode=0o700, dir_fd=descriptor)
        child_state = os.stat(private_name, dir_fd=descriptor, follow_symlinks=False)
        if child_state.st_uid != os.getuid() or child_state.st_mode & 0o077:
            raise AcquisitionRejected("new directory is not private and owned")
        child_descriptor = os.open(private_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
        try:
            os.mkdir("tmp", mode=0o700, dir_fd=child_descriptor)
            os.mkdir("cache", mode=0o700, dir_fd=child_descriptor)
        finally:
            os.close(child_descriptor)
    except BaseException as exc:
        if descriptor is not None and child_state is not None:
            current = os.stat(private_name, dir_fd=descriptor, follow_symlinks=False)
            if (not stat.S_ISDIR(current.st_mode) or current.st_uid != os.getuid()
                    or (current.st_dev, current.st_ino) != (child_state.st_dev, child_state.st_ino)
                    or not shutil.rmtree.avoids_symlink_attacks):
                raise CleanupRejected("partially created child cannot be safely cleaned") from exc
            shutil.rmtree(private_name, dir_fd=descriptor)
        if isinstance(exc, OSError):
            raise AcquisitionRejected("local parent or exclusive private child unavailable") from exc
        raise
    finally:
        if descriptor is not None:
            os.close(descriptor)
    private = parent / private_name
    receipt = {"schema": SCHEMA, **allocation, **mount,
        "temp_parent": str(parent), "private_dir": str(private),
        "tmp_dir": str(private / "tmp"), "cache_dir": str(private / "cache"),
        "available_bytes": free_bytes, "required_free_bytes": min_free_bytes,
        "parent_device_inode": [parent_state.st_dev, parent_state.st_ino],
        "private_device_inode": [child_state.st_dev, child_state.st_ino],
        "private_mode": "0700", "fallback_used": False,
        "qualification": "conditional implementation; no acquisition or model outcome"}
    return AcquisitionContext(parent, private, private / "tmp", private / "cache", receipt,
        (parent_state.st_dev, parent_state.st_ino), (child_state.st_dev, child_state.st_ino), os.getuid())
