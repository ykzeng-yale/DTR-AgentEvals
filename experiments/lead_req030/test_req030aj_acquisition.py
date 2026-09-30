"""Deterministic acquisition-placement checks; no Slurm/pull/model calls."""
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from experiments.lead_req030 import req030aj_acquisition as acquisition


JOB = "27950747"
HOST = "compute001"


def scheduler_record(**overrides):
    fields = {"JobId": JOB, "JobState": "RUNNING", "UserId": f"researcher({os.getuid()})",
              "BatchHost": HOST, "JobName": "req030aj-controls"}
    fields.update(overrides)
    return " ".join(f"{key}={value}" for key, value in fields.items())


def mount_record(path: Path, fs="ext4", options="rw,relatime", mount_id=35):
    escaped = str(path).replace("\\", "\\134").replace(" ", "\\040")
    device = (path if path.exists() else Path.cwd()).stat().st_dev
    major_minor = f"{os.major(device)}:{os.minor(device)}"
    return f"{mount_id} 20 {major_minor} / {escaped} {options} - {fs} /dev/local {options}\n"


def prepare(parent, **kwargs):
    options = dict(temp_parent=parent, run_id="req030aj-complete-cohort-a",
        expected_job_id=JOB, min_free_bytes=4096, environment={"SLURM_JOB_ID": JOB},
        scheduler_reader=lambda _: scheduler_record(), mountinfo=mount_record(parent),
        hostname=HOST, platform="linux",
        capacity_reader=lambda _: SimpleNamespace(f_bavail=100, f_frsize=4096))
    options.update(kwargs)
    return acquisition.prepare_acquisition(**options)


def test_private_owned_local_receipt_and_own_cleanup(tmp_path):
    peer = tmp_path / "unrelated-shared-cache"
    peer.mkdir(); (peer / "keep").write_text("peer")
    context = prepare(tmp_path)
    assert context.receipt["ownership_verified"] is True
    assert context.receipt["filesystem"] == "ext4"
    assert context.receipt["available_bytes"] == 409600
    assert context.receipt["required_free_bytes"] == 4096
    assert context.receipt["fallback_used"] is False
    assert context.receipt["tmp_dir"] == str(context.tmp_dir)
    assert context.receipt["cache_dir"] == str(context.cache_dir)
    assert context.private_dir.stat().st_mode & 0o777 == 0o700
    assert context.tmp_dir.is_dir() and context.cache_dir.is_dir()
    (context.tmp_dir / "build-part").write_bytes(b"unqualified")
    assert context.cleanup()["cleaned"] is True
    assert not context.private_dir.exists()
    assert (peer / "keep").read_text() == "peer"
    assert context.cleanup() == {"cleaned": True, "already_cleaned": True}


def test_xfs_is_accepted_and_context_exit_cleans(tmp_path):
    with prepare(tmp_path, mountinfo=mount_record(tmp_path, "xfs")) as context:
        assert context.receipt["filesystem"] == "xfs"
    assert not context.private_dir.exists()


@pytest.mark.parametrize("filesystem", ["nfs", "nfs4", "lustre", "gpfs", "tmpfs", "overlay", "fuse", "unknown"])
def test_shared_memory_unknown_filesystems_rejected_without_children(tmp_path, filesystem):
    with pytest.raises(acquisition.AcquisitionRejected):
        prepare(tmp_path, mountinfo=mount_record(tmp_path, filesystem))
    assert list(tmp_path.iterdir()) == []


def test_longest_mount_wins_and_substring_is_not_containment(tmp_path):
    local = mount_record(Path("/"), "ext4", mount_id=1)
    nested = mount_record(tmp_path, "nfs", mount_id=2)
    with pytest.raises(acquisition.AcquisitionRejected):
        prepare(tmp_path, mountinfo=local + nested)
    record = acquisition.local_mount(Path("/tmp-extra/task"),
        local + mount_record(Path("/tmp"), "nfs", mount_id=3))
    assert record["filesystem"] == "ext4"


def test_mount_escape_and_writable_gate(tmp_path):
    spaced = tmp_path / "local disk"
    spaced.mkdir()
    context = prepare(spaced)
    assert context.receipt["mount_point"] == str(spaced)
    context.cleanup()
    with pytest.raises(acquisition.AcquisitionRejected):
        prepare(spaced, mountinfo=mount_record(spaced, options="ro,relatime"))


@pytest.mark.parametrize("inventory", ["", "bad record", "1 2 8:1 / relative rw - ext4 /dev/disk rw\n"])
def test_missing_or_malformed_mount_rejected(tmp_path, inventory):
    with pytest.raises(acquisition.AcquisitionRejected):
        prepare(tmp_path, mountinfo=inventory)


def test_ambiguous_mount_is_rejected(tmp_path):
    inventory = mount_record(tmp_path) + mount_record(tmp_path, "xfs", mount_id=36)
    with pytest.raises(acquisition.AcquisitionRejected):
        prepare(tmp_path, mountinfo=inventory)


@pytest.mark.parametrize("overrides", [
    {"JobId": "27950748"}, {"JobState": "PENDING"}, {"JobState": "COMPLETED"},
    {"UserId": f"other({os.getuid() + 1})"}, {"BatchHost": "login001"}, {"BatchHost": "(null)"},
])
def test_scheduler_job_ownership_and_host_rejected(tmp_path, overrides):
    with pytest.raises(acquisition.AcquisitionRejected):
        prepare(tmp_path, scheduler_reader=lambda _: scheduler_record(**overrides))
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("environment", [
    {}, {"SLURM_JOB_ID": "27950748"}, {"SLURM_JOB_ID": JOB, "SLURM_JOB_USER": "other"},
    {"SLURM_JOB_ID": JOB, "SLURM_JOB_UID": str(os.getuid() + 1)},
])
def test_environment_is_bound_to_verified_job(tmp_path, environment):
    with pytest.raises(acquisition.AcquisitionRejected):
        prepare(tmp_path, environment=environment)
    assert list(tmp_path.iterdir()) == []


def test_hostname_short_and_fqdn_normalize_but_duplicate_fields_fail(tmp_path):
    context = prepare(tmp_path, hostname=HOST + ".bouchet.example")
    context.cleanup()
    with pytest.raises(acquisition.AcquisitionRejected):
        prepare(tmp_path, scheduler_reader=lambda _: scheduler_record() + " JobId=" + JOB)


@pytest.mark.parametrize("job", ["", "0", "00123", "27950747;rm", 27950747, True])
def test_noncanonical_job_ids_rejected(tmp_path, job):
    with pytest.raises(acquisition.AcquisitionRejected):
        prepare(tmp_path, expected_job_id=job,
            scheduler_reader=lambda _: pytest.fail("invalid job must be rejected before scheduler call"))


@pytest.mark.parametrize("run", ["", "../peer", "run/name", "run name", "a" * 97, True])
def test_invalid_run_ids_rejected(tmp_path, run):
    with pytest.raises(acquisition.AcquisitionRejected):
        prepare(tmp_path, run_id=run)


@pytest.mark.parametrize("floor", [0, -1, True, 1.0])
def test_invalid_capacity_floor_rejected(tmp_path, floor):
    with pytest.raises(acquisition.AcquisitionRejected):
        prepare(tmp_path, min_free_bytes=floor)


def test_capacity_and_platform_fail_without_fallback(tmp_path):
    with pytest.raises(acquisition.AcquisitionRejected):
        prepare(tmp_path, capacity_reader=lambda _: SimpleNamespace(f_bavail=0, f_frsize=4096))
    with pytest.raises(acquisition.AcquisitionRejected):
        prepare(tmp_path, platform="darwin")
    assert list(tmp_path.iterdir()) == []


def test_relative_traversal_and_symlink_parent_rejected(tmp_path):
    for parent in (Path("relative"), tmp_path / ".." / tmp_path.name):
        with pytest.raises(acquisition.AcquisitionRejected):
            prepare(parent)
    actual = tmp_path / "actual"; actual.mkdir()
    link = tmp_path / "link"; link.symlink_to(actual, target_is_directory=True)
    with pytest.raises(acquisition.AcquisitionRejected):
        prepare(link)
    assert list(actual.iterdir()) == []


def test_existing_private_name_is_not_reused_or_cleaned(tmp_path):
    first = prepare(tmp_path)
    (first.cache_dir / "owned-first").write_text("preserve")
    with pytest.raises(acquisition.AcquisitionRejected):
        prepare(tmp_path)
    assert (first.cache_dir / "owned-first").read_text() == "preserve"
    first.cleanup()


def test_cleanup_unlinks_nested_symlink_without_touching_peer(tmp_path):
    peer = tmp_path / "peer"; peer.mkdir(); (peer / "keep").write_text("safe")
    context = prepare(tmp_path)
    (context.tmp_dir / "external-link").symlink_to(peer, target_is_directory=True)
    context.cleanup()
    assert (peer / "keep").read_text() == "safe"


def test_cleanup_rejects_replacement_private_inode(tmp_path):
    context = prepare(tmp_path)
    saved = context.private_dir.with_name("saved-original")
    context.private_dir.rename(saved)
    context.private_dir.mkdir(mode=0o700)
    (context.private_dir / "replacement").write_text("must preserve")
    with pytest.raises(acquisition.CleanupRejected):
        context.cleanup()
    assert (context.private_dir / "replacement").exists()


def test_cleanup_rejects_replaced_root_symlink(tmp_path):
    context = prepare(tmp_path)
    saved = context.private_dir.with_name("saved-original")
    context.private_dir.rename(saved)
    peer = tmp_path / "peer"; peer.mkdir(); (peer / "keep").write_text("safe")
    context.private_dir.symlink_to(peer, target_is_directory=True)
    with pytest.raises(acquisition.CleanupRejected):
        context.cleanup()
    assert (peer / "keep").read_text() == "safe"


def test_cleanup_rejects_permissions_widened_after_receipt(tmp_path):
    context = prepare(tmp_path)
    context.private_dir.chmod(0o755)
    with pytest.raises(acquisition.CleanupRejected):
        context.cleanup()
    context.private_dir.chmod(0o700)
    context.cleanup()


def test_cleanup_rejects_changed_parent_and_preserves_replacement(tmp_path):
    parent = tmp_path / "local"; parent.mkdir()
    context = prepare(parent)
    parent.rename(tmp_path / "old-local")
    parent.mkdir()
    replacement = parent / context.private_dir.name; replacement.mkdir(mode=0o700)
    (replacement / "keep").write_text("safe")
    with pytest.raises(acquisition.CleanupRejected):
        context.cleanup()
    assert (replacement / "keep").read_text() == "safe"


def test_partial_creation_failure_cleans_only_just_created_child(tmp_path, monkeypatch):
    peer = tmp_path / "peer"; peer.mkdir(); (peer / "keep").write_text("safe")
    actual_mkdir = os.mkdir
    def fail_cache(path, *args, **kwargs):
        if path == "cache":
            raise PermissionError("authored cache failure")
        return actual_mkdir(path, *args, **kwargs)
    monkeypatch.setattr(acquisition.os, "mkdir", fail_cache)
    with pytest.raises(acquisition.AcquisitionRejected):
        prepare(tmp_path)
    assert list(tmp_path.iterdir()) == [peer]
    assert (peer / "keep").read_text() == "safe"


@pytest.mark.parametrize("capacity", [
    SimpleNamespace(f_bavail=True, f_frsize=4096),
    SimpleNamespace(f_bavail=100, f_frsize=0),
    SimpleNamespace(f_bavail=-1, f_frsize=4096),
])
def test_invalid_capacity_record_is_rejected(tmp_path, capacity):
    with pytest.raises(acquisition.AcquisitionRejected):
        prepare(tmp_path, capacity_reader=lambda _: capacity)
    assert list(tmp_path.iterdir()) == []


def test_mount_device_must_match_opened_parent(tmp_path):
    parts = mount_record(tmp_path).split()
    parts[2] = "999:999"
    with pytest.raises(acquisition.AcquisitionRejected):
        prepare(tmp_path, mountinfo=" ".join(parts))
    assert list(tmp_path.iterdir()) == []
