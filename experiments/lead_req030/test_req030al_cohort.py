"""Authored inert complete-cohort/gate/parallel/denominator fault tests."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import time

import pytest


def test_private_subprocess_failure_retains_causal_stderr_without_overwrite(tmp_path):
    path = tmp_path / "failure.txt"
    try:
        subprocess.run(["sh", "-c", "printf 'badTimezone: historical commit metadata' >&2; exit 4"],
                       check=True, capture_output=True)
    except subprocess.CalledProcessError:
        cohort.retain_error(path)
        with pytest.raises(FileExistsError):
            cohort.retain_error(path)
    assert b"badTimezone: historical commit metadata" in path.read_bytes()
    assert path.stat().st_mode & 0o777 == 0o600

from experiments.lead_req030 import req030al_cohort as cohort
from experiments.lead_req030.test_req030aj_cohort import admitted, authored_episode, save
from experiments.lead_req030.test_req030aj_cohort import framed, supervisor
from experiments.lead_req030 import req030al_environment as environment


@pytest.fixture
def al_admitted(admitted, monkeypatch):
    prior, prior_admission, prior_path = admitted
    release = copy.deepcopy(prior)
    release.pop("control_acceptance")
    release.update(schema=cohort.SCHEMA, request=cohort.REQUEST)
    release["resource_cap"]["gpu_count"] = 2
    release["models"] = {"models": [{k: m[k] for k in ("repo", "revision", "files")}
        for m in cohort.aj.read_json(cohort.ROOT / cohort.MODEL_ASSETS_REL)["models"]]}
    release["limits"]["batch_seconds"] = 18900
    release["goal"] = {"started_epoch": time.time() - 1, "deadline_epoch": time.time() - 1 + cohort.GOAL_SECONDS,
        "max_iterations": 3, "iteration": 1}
    # Ensure exact subtraction even when time.time() crosses two samples.
    release["goal"]["deadline_epoch"] = release["goal"]["started_epoch"] + cohort.GOAL_SECONDS
    release["source_pins"] = {rel: cohort.worker.digest_file(cohort.ROOT / rel) for rel in cohort.REQUIRED_SOURCES}
    prior_control = cohort.aj.read_json(Path(release["control_release"]["path"]))
    prior_control["request"] = "DTR-REQ-030AK"
    control_path = prior_path.parent / "al_synthetic_control.json"
    release["control_release"] = save(control_path, prior_control)
    release["cached_task_assets"] = [{"task_id": tid, **{k: item["receipt"][k] for k in ("image", "source_tar")}}
        for tid, item in prior_admission["tasks"].items()]
    path = prior_path.parent / "al_release.json"; pin = save(path, release)
    doc, admission = cohort.load_release(path, pin["sha256"])
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "2,3")
    qualification = {"schema": "dtr.req030al.qualification.v1", "all_controls_accepted": True,
        "source_review_accepted": True, "runtime_accepted": True, "model_calls": 0, "tasks": []}
    for tid, item in prior_admission["tasks"].items():
        for mode, arm in item["receipt"]["controls"].items():
            runtime = {"python": "inert Python", "executable": environment.TESTBED_PYTHON,
                "modules": [{"module": name, "file": "/testbed/" + name.replace(".", "/") + "/__init__.py"} for name in environment.MODULES[tid]],
                "localhost": ["127.0.0.1"], "interfaces": ["lo"], "routes": [], "packages": [{"name": "pytest", "version": "inert"}]}
            rc = 1 if mode == "baseline" else 0
            prefix = "DTR_AL_RUNTIME\t" + json.dumps(runtime) + "\n" + "".join(
                "DTR_AL_STAGE\t" + stage + "\t" + str(rc if stage == "test_run" else 0) + "\n" for stage in environment.STAGES)
            rawpath = Path(arm["raw"]["path"])
            raw = prefix.encode() + rawpath.read_bytes(); rawpath.write_bytes(raw)
            arm["raw"] = cohort.aj.file_pin(rawpath)
            arm["supervisor"] = save(Path(arm["supervisor"]["path"]), supervisor(raw, returncode=rc))
        task = {"task_id": tid, "source_accepted": True, "accepted": True,
            **{k: item["receipt"][k] for k in ("image", "source_tar", "source_acceptance")},
            "controls": {mode: {**arm, "accepted": True, "cleanup_verified": True} for mode, arm in item["receipt"]["controls"].items()}}
        qualification["tasks"].append(task)
    return doc, admission, path, qualification


def accepted_grade(**kwargs):
    return {"cleanup_verified": True, "binding_verified": True,
        "grade": {"graded": True, "resolved": True, "algorithmic_correctness": "resolved",
            "operational_resolution": 1, "assigned_slot_retained": True},
        "official_upstream_score": {"available": False, "reason": "authored_inert_test_only"}}


def fake_dispatcher(output, *, clean=True, statuses=None):
    launched = []
    class FakeProcess:
        def __init__(self, command, **kwargs):
            self.command = command; self.env = kwargs["env"]; self.returncode = None
            self.period = int(command[command.index("--period") + 1])
            self.inner_path = Path(command[command.index("--worker-admission") + 1])
            self.inner_sha = command[command.index("--worker-admission-sha256") + 1]
            self.outer_sha = command[command.index("--release-sha256") + 1]
            assert self.env["CUDA_VISIBLE_DEVICES"] in ("2", "3")
            assert "torch" not in cohort.sys.modules
            launched.append(self)
        def poll(self):
            if self.returncode is None:
                result = cohort.run_cell(self.inner_path, self.inner_sha, self.outer_sha, output, self.period,
                    episode_runner=lambda spec, directory: authored_episode(spec, directory, cleanup=clean),
                    grade_runner=accepted_grade)
                if statuses is not None: statuses.append(result)
                self.returncode = 0
            return self.returncode
        def terminate(self): self.returncode = -15
        def kill(self): self.returncode = -9
        def wait(self, timeout=None): return self.poll()
    return FakeProcess, launched


def test_complete_32_slots_two_visible_gpu_workers(al_admitted, tmp_path):
    release, admission, _, qualification = al_admitted
    output = tmp_path / "cohort"; cohort.seed(release, admission, output)
    dispatcher, launched = fake_dispatcher(output)
    result = cohort.execute(release, admission, output, qualifier=lambda *args: qualification, dispatcher=dispatcher)
    assert result["status"] == "COMPLETED_ASSIGNED_COHORT"
    assert len(result["slots"]) == len(launched) == 32
    assert result["descriptive"]["assigned_slots"] == 32
    assert result["descriptive"]["task_count"] == result["descriptive"]["family_count"] == 8
    assert result["descriptive"]["operational_resolution_fraction"] == 1
    assert result["descriptive"]["costs"]["native_requests"]["observed_sum"] == 320
    assert [p.period for p in launched] == [s["period"] for s in cohort.wave_priority(release["order"])]
    assert {p.env["CUDA_VISIBLE_DEVICES"] for p in launched} == {"2", "3"}
    assert all(cell["cleanup_verified"] is True for cell in result["slots"])
    assert all(cell["grade"]["assigned_slot_retained"] is True for cell in result["slots"])


@pytest.mark.parametrize("gate", ["all_controls_accepted", "source_review_accepted", "runtime_accepted"])
def test_any_whole_cohort_gate_blocks_every_model_slot(al_admitted, tmp_path, gate):
    release, admission, _, qualification = al_admitted
    qualification[gate] = False
    output = tmp_path / "gate"; cohort.seed(release, admission, output)
    def prohibited(*args, **kwargs): raise AssertionError("gate failure dispatched a model")
    result = cohort.execute(release, admission, output, qualifier=lambda *args: qualification, dispatcher=prohibited)
    assert result["status"] == "INCOMPLETE_ASSIGNED_COHORT"
    assert result["real_model_worker_started"] is False
    assert result["descriptive"]["unstarted_slots"] == 32
    assert result["descriptive"]["missing_correctness_range"] == [0, 1]


def test_no_complete_time_envelope_keeps_all32_assigned(al_admitted, tmp_path):
    release, admission, _, qualification = al_admitted
    release["goal"]["deadline_epoch"] = 20000
    output = tmp_path / "deadline"; cohort.seed(release, admission, output)
    def prohibited(*args, **kwargs): raise AssertionError("expired reservation started")
    result = cohort.execute(release, admission, output, qualifier=lambda *args: qualification, dispatcher=prohibited,
        clock=lambda: 100, epoch=lambda: 20000 - cohort.aj.SLOT_RESERVATION_SECONDS + 1)
    assert result["stop_reason"] == "joint_budget_no_complete_slot_envelope"
    assert result["descriptive"]["unstarted_slots"] == 32


def test_cleanup_failure_aborts_future_dispatch_and_preserves_denominator(al_admitted, tmp_path):
    release, admission, _, qualification = al_admitted
    output = tmp_path / "cleanup"; cohort.seed(release, admission, output)
    dispatcher, launched = fake_dispatcher(output, clean=False)
    result = cohort.execute(release, admission, output, qualifier=lambda *args: qualification, dispatcher=dispatcher)
    assert len(launched) == 2
    assert result["stop_reason"] == "parallel_cell_cleanup_unknown"
    assert result["descriptive"]["assigned_slots"] == 32
    assert result["descriptive"]["unstarted_slots"] == 30
    assert result["descriptive"]["infrastructure_unknown_slots"] == 2
    assert result["descriptive"]["missing_correctness_range"] == [0, 1]


@pytest.mark.parametrize("value,count", [("", 2), ("0,0", 2), ("0", 2), ("0,1,2", 2), ("0;rm,1", 2), (None, 2)])
def test_allocated_gpu_identity_rejects_wrong_or_duplicate_tokens(value, count, monkeypatch):
    monkeypatch.delenv("CUDA_VISIBLE_DEVICES", raising=False)
    with pytest.raises(ValueError): cohort.visible_gpu_tokens(count, value)


def test_uuid_gpu_tokens_are_supported():
    assert cohort.visible_gpu_tokens(2, "GPU-one,GPU-two") == ["GPU-one", "GPU-two"]


def test_author_wall_deadline_and_monotonic_allocation_both_bound(al_admitted):
    release = al_admitted[0]
    release["goal"]["deadline_epoch"] = 200
    assert cohort.goal_remaining(release, started_monotonic=100, now_monotonic=120, now_epoch=190) == 10
    assert cohort.goal_remaining(release, started_monotonic=100, now_monotonic=19001, now_epoch=150) == 0


@pytest.mark.parametrize("mutate", [
    lambda d: d["goal"].update(max_iterations=4),
    lambda d: d["goal"].update(deadline_epoch=d["goal"]["deadline_epoch"] + 1),
    lambda d: d["resource_cap"].update(gpu_count=0),
    lambda d: d["tasks"].pop(),
    lambda d: d["cached_task_assets"].pop(),
    lambda d: d["order"].pop(),
    lambda d: d["token_contract"].update(physical_retries=1),
    lambda d: d["limits"].update(slot_reservation_seconds=1),
])
def test_invalid_or_incomplete_frozen_release_rejected(al_admitted, mutate):
    release, _, path, _ = al_admitted
    mutated = copy.deepcopy(release); mutate(mutated)
    pin = save(path.with_name("invalid.json"), mutated)
    with pytest.raises(ValueError): cohort.load_release(Path(pin["path"]), pin["sha256"])


def test_cell_public_spec_contains_no_evaluator(al_admitted, tmp_path):
    release, admission, _, qualification = al_admitted
    output = tmp_path / "public"; cohort.seed(release, admission, output); (output / "cells").mkdir()
    path, digest = cohort.create_worker_admission(release, admission, qualification, output)
    seen = []
    def episode(spec, directory):
        text = json.dumps(spec)
        assert "evaluator" not in text and "reference" not in text and "EVALUATOR_ONLY" not in text
        assert "TEST_ONLY_INERT" not in text
        seen.append(spec)
        return authored_episode(spec, directory)
    cell = cohort.run_cell(path, digest, admission["release_sha256"], output, 1, episode_runner=episode, grade_runner=accepted_grade)
    assert len(seen) == 1 and cell["status"] == "GRADED"
    assert seen[0]["release_sha256"] == admission["release_sha256"]


def test_one_shared_exact_size_cache_does_not_download(al_admitted, tmp_path):
    release, admission, _, _ = al_admitted
    for model in release["models"]["models"]:
        dest = admission["model_root"] / model["revision"]; dest.mkdir()
        for asset in model["files"]:
            path = dest / asset["path"]; path.parent.mkdir(exist_ok=True, parents=True)
            with path.open("xb") as file: file.truncate(asset["bytes"])
    result = cohort.acquire_assets(release, admission, tmp_path)
    assert result["download_attempted"] is False and result["expected_bytes"] == sum(a["bytes"] for m in release["models"]["models"] for a in m["files"])


def test_partial_weight_cache_cannot_be_silently_overwritten(al_admitted, tmp_path):
    release, admission, _, _ = al_admitted
    model = release["models"]["models"][0]
    dest = admission["model_root"] / model["revision"]; dest.mkdir()
    path = dest / model["files"][0]["path"]; path.parent.mkdir(exist_ok=True, parents=True)
    path.write_bytes(b"partial")
    with pytest.raises(ValueError, match="partial model cache"):
        cohort.acquire_assets(release, admission, tmp_path)


@pytest.mark.parametrize("mode", ["baseline", "reference"])
@pytest.mark.parametrize("broken_stage", [False, True])
def test_control_reference_file_and_actual_environment_stage_gate(al_admitted, tmp_path, monkeypatch, mode, broken_stage):
    _, admission, _, _ = al_admitted
    tid = cohort.controls.TASK_IDS[0]; item = admission["tasks"][tid]
    directory = tmp_path / mode
    def make(source, seed, workspace, **kwargs):
        workspace.write_bytes(b"authored inert workspace"); return {}
    def wrapper(path, evaluation, **kwargs):
        assert kwargs == {"mode": mode, "expected_base_commit": item["task"]["base_commit"]}
        assert (path.parent / "reference.diff").exists() is (mode == "reference")
        if mode == "reference": assert (path.parent / "reference.diff").read_bytes() == evaluation["reference_patch"].encode()
        path.write_text("authored inert evaluator; no container executed")
    def run(apptainer, image, workspace, command, **kwargs):
        assert command == ["/bin/bash", "/eval/run.sh"]
        hosts = Path(kwargs["extra_binds"][3].removesuffix(":/etc/hosts:ro"))
        assert hosts.read_bytes() == environment.HOSTS_BYTES
        runtime = {"python": "inert Python", "executable": environment.TESTBED_PYTHON,
            "modules": [{"module": "django", "file": "/testbed/django/__init__.py"}],
            "localhost": ["127.0.0.1"], "interfaces": ["lo"], "routes": [], "packages": [{"name": "pytest", "version": "inert"}]}
        rc = 1 if mode == "baseline" else 0
        prefix = "DTR_AL_RUNTIME\t" + json.dumps(runtime) + "\n"
        stages = "".join("DTR_AL_STAGE\t" + stage + "\t" + str(rc if stage == "test_run" else 0) + "\n"
            for stage in environment.STAGES if not (broken_stage and stage == "test_patch"))
        nodes = item["evaluation"]["fail_to_pass"] + item["evaluation"]["pass_to_pass"]
        raw = prefix.encode() + stages.encode() + framed(item["task"]["repo"], nodes, ["FAILED" if rc else "PASSED", "PASSED"])
        receipt = supervisor(raw, returncode=rc)
        kwargs["output_path"].write_bytes(raw); save(kwargs["receipt_path"], receipt)
        return raw, receipt
    monkeypatch.setattr(cohort.sandbox, "make_workspace", make)
    monkeypatch.setattr(cohort.sandbox, "run_supervised", run)
    monkeypatch.setattr(environment, "evaluation_wrapper", wrapper)
    result = cohort.execute_control(item, source=tmp_path / "inert_source.tar", image=tmp_path / "inert.sif",
        directory=directory, apptainer="inert", mode=mode)
    assert result["accepted"] is (not broken_stage)
    assert result["cleanup_verified"] is True
    assert not (directory / "workspace.img").exists()
    assert result["runtime"]["modules"][0]["module"] == "django"


def test_qualification_checks_installed_runtime_identity_between_all16_arms(al_admitted, tmp_path, monkeypatch):
    release, admission, _, _ = al_admitted
    output = tmp_path / "runtime_identity"; output.mkdir()
    def normalize(source, destination, *, base_commit, task_id):
        destination.write_bytes(b"authored inert normalized source")
        return {"accepted": True, "head": base_commit, "tree": "a" * 40, "base_tree": "a" * 40}
    seen = []
    def control(item, *, mode, **kwargs):
        seen.append((item["task"]["instance_id"], mode))
        return {"accepted": True, "cleanup_verified": True, "runtime_sha256": ("a" if mode == "baseline" else "b") * 64}
    monkeypatch.setattr(environment, "prepare_source_archive", normalize)
    monkeypatch.setattr(cohort, "execute_control", control)
    result = cohort.qualify(release, admission, output, runtime_verifier=lambda r: {"authored_inert": True},
        asset_verifier=lambda *args: {"authored_inert": True})
    assert len(seen) == 16 and len(set(seen)) == 16
    assert result["source_review_accepted"] is True and result["runtime_accepted"] is True
    assert result["all_controls_accepted"] is False
    assert all(t["installed_runtime_identical_between_arms"] is False for t in result["tasks"])


def test_independent_control_stage_mutation_blocks_all32_slots(al_admitted, tmp_path):
    release, admission, _, qualification = al_admitted
    control = qualification["tasks"][0]["controls"]["reference"]
    path = Path(control["raw"]["path"])
    raw = path.read_bytes().replace(b"DTR_AL_STAGE\ttest_patch\t0\n", b"")
    path.write_bytes(raw); control["raw"] = cohort.aj.file_pin(path)
    control["supervisor"] = save(Path(control["supervisor"]["path"]), supervisor(raw))
    output = tmp_path / "independent_gate"; cohort.seed(release, admission, output)
    def prohibited(*args, **kwargs): raise AssertionError("independent stage failure dispatched a model")
    result = cohort.execute(release, admission, output, qualifier=lambda *args: qualification, dispatcher=prohibited)
    assert result["stop_reason"] == "independent_whole_control_admission_rejected"
    assert result["all_controls_accepted"] is False
    assert result["descriptive"]["unstarted_slots"] == 32
    assert result["descriptive"]["missing_correctness_range"] == [0, 1]


@pytest.mark.parametrize("kind", ["control", "acquisition", "gpu_runtime"])
@pytest.mark.parametrize("terminal", [False, True])
def test_qualification_cleanup_requires_nonmodel_terminal_receipts(tmp_path, kind, terminal):
    output = tmp_path / "results"; directory = output / "qualification"; directory.mkdir(parents=True)
    if kind == "control":
        arm = directory / cohort.controls.TASK_IDS[0] / "baseline"; arm.mkdir(parents=True)
        if terminal: save(arm / "baseline.supervisor.json", supervisor(b""))
    elif kind == "acquisition":
        (directory / "model_acquisition.out").write_bytes(b"")
        if terminal: save(directory / "model_acquisition_supervisor.json", {"reaped": True, "returncode": 0})
    else:
        (directory / "gpu_runtime_00.out").write_bytes(b"")
        if terminal: save(directory / "gpu_runtime_00.supervisor.json", {"reaped": True, "returncode": 0})
    assert cohort.qualification_cleanup(output) is terminal


def inert_apptainer_version(command, **kwargs):
    assert command[-1] == "--version" and kwargs["timeout"] == 10
    return subprocess.CompletedProcess(command, 0, stdout=b"apptainer version 1.5.3-1.el9\n")


def test_wrong_compute_binary_pin_leaves_private_failure_before_any_seed(al_admitted, tmp_path, monkeypatch):
    release, _, path, _ = al_admitted
    changed = copy.deepcopy(release); changed["apptainer"]["sha256"] = "0" * 64
    pin = save(path.with_name("wrong_binary_release.json"), changed)
    monkeypatch.setattr(cohort.subprocess, "run", inert_apptainer_version)
    monkeypatch.setenv("SLURM_JOB_ID", "authored-inert-fixture")
    monkeypatch.setattr(cohort, "seed", lambda *args: pytest.fail("bad binary started the cohort"))
    output = tmp_path / "results"
    with pytest.raises(ValueError, match="pinned file hash mismatch"):
        cohort.run(Path(pin["path"]), pin["sha256"], output)
    receipt = cohort.aj.read_json(tmp_path / "results.startup_failure.json")
    assert receipt["phase"] == "release_validation" and receipt["status"] == "PRE_ADMISSION_FAILED"
    assert receipt["apptainer"]["observed_sha256"] == cohort.worker.digest_file(Path(release["apptainer"]["path"]))
    assert receipt["apptainer"]["expected_sha256"] == "0" * 64
    assert receipt["apptainer"]["version"] == "apptainer version 1.5.3-1.el9"
    assert receipt["model_calls"] == receipt["controls_started"] == 0
    assert receipt["assigned_slots"] == 32 and receipt["cohort_seeded"] is False
    assert not output.exists() and (tmp_path / "results.startup_error.txt").stat().st_size <= cohort.worker.MAX_STDOUT
    assert (tmp_path / "results.startup_failure.json").stat().st_mode & 0o777 == 0o600


def test_correct_compute_identity_passes_startup_without_launching_models(al_admitted, tmp_path, monkeypatch):
    release, admission, path, _ = al_admitted
    monkeypatch.setattr(cohort.subprocess, "run", inert_apptainer_version)
    monkeypatch.setattr(cohort.sandbox, "require_disk_floor", lambda *args: None)
    actual, checked = cohort.startup_preflight(path, admission["release_sha256"], tmp_path / "results")
    assert actual == release and checked["apptainer"] == admission["apptainer"]
    assert not (tmp_path / "results").exists() and not (tmp_path / "results.startup_failure.json").exists()


def test_wrong_release_hash_never_supplies_a_diagnostic_executable(al_admitted, tmp_path, monkeypatch):
    _, _, path, _ = al_admitted
    def forbidden(*args): pytest.fail("unverified release supplied diagnostic command")
    monkeypatch.setattr(cohort, "observe_apptainer", forbidden)
    with pytest.raises(ValueError): cohort.startup_preflight(path, "0" * 64, tmp_path / "results")
    receipt = cohort.aj.read_json(tmp_path / "results.startup_failure.json")
    assert receipt["apptainer"] is None and receipt["apptainer_diagnostic_error"] == "ValueError"
    assert receipt["model_calls"] == receipt["controls_started"] == 0
