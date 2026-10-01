"""Deterministic qualification of the prospective offline execution variant."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import tarfile

import pytest

from experiments.lead_req030 import req030al_environment as env
from experiments.lead_req030 import req030ag_seaborn_apptainer_runner as runner
from experiments.lead_req030.test_req030ah_runner import assets, environment


def stock_fixture(monkeypatch, task_id="psf__requests-6028"):
    base = "a" * 40
    patch = "diff --git a/tests/test.py b/tests/test.py\n--- a/tests/test.py\n+++ b/tests/test.py\n@@ -1 +1 @@\n-old\n+new\n"
    command = "pytest -rA tests/test.py"
    if task_id == "sphinx-doc__sphinx-8593":
        command = "tox --current-env -epy39 -v -- tests/test.py"
    if task_id == "django__django-12039":
        command = "./tests/runtests.py --verbosity 2 --settings=test_sqlite --parallel 1 indexes.tests"
    script = ("#!/bin/bash\nset -uxo pipefail\npython -m pip install -e .\n"
        f"git checkout {base} tests/test.py\ngit apply -v - <<'EOF_114329324912'\n{patch}\nEOF_114329324912\n"
        f": '>>>>> Start Test Output'\n{command}\n: '>>>>> End Test Output'\n"
        f"git checkout {base} tests/test.py\n")
    task = {"instance_id": task_id, "base_commit": base,
        "stock_eval_script_sha256": env.sha(script.encode()), "test_patch_sha256": env.sha(patch.encode())}
    monkeypatch.setattr(env, "frozen_tasks", lambda: {task_id: task})
    return {**task, "stock_eval_script": script}


@pytest.mark.parametrize("task_id", tuple(env.MODULES))
@pytest.mark.parametrize("mode", ("baseline", "reference", "agent"))
def test_all_fixed_variants_are_shell_valid_and_preserve_test_patch(tmp_path, monkeypatch, task_id, mode):
    evaluation = stock_fixture(monkeypatch, task_id)
    path = tmp_path / "eval.sh"
    receipt = env.evaluation_wrapper(path, evaluation, mode=mode,
        expected_base_commit=evaluation["base_commit"], invocation_marker="DTR_EVALUATOR_INVOCATION:abc")
    text = path.read_text()
    assert receipt["stock_eval_script_sha256"] == evaluation["stock_eval_script_sha256"]
    assert receipt["test_patch_sha256"] == evaluation["test_patch_sha256"]
    assert receipt["omitted_install_command"] == "python -m pip install -e ."
    assert "pip install" not in text and "safe.directory" not in text and "locale-gen" not in text
    assert 'test_rc=$?' in text and 'exit "$test_rc"' in text
    assert text.count("git checkout") == 1  # no masked final checkout/test rc
    assert "DTR_HOST_NET_ID" in text and env.HOSTS_SHA256 in text
    assert "socket.getaddrinfo('localhost', 0)" in text and "sock.bind(('localhost', 0))" in text
    assert "'/proc/net/dev'" in text and "'/proc/net/route'" in text
    assert receipt["official_docker_execution_verified"] is False
    assert path.stat().st_mode & 0o777 == 0o500
    assert env.sha(path.read_bytes()) == receipt["wrapper_sha256"]


def test_sphinx_reporting_only_change_uses_original_tox_posargs(tmp_path, monkeypatch):
    evaluation = stock_fixture(monkeypatch, env.SPHINX_TASK)
    design = env.evaluation_wrapper(tmp_path / "eval.sh", evaluation, mode="baseline",
        expected_base_commit=evaluation["base_commit"])
    assert design["test_command"] == "/opt/miniconda3/envs/testbed/bin/tox --current-env -epy39 -v -- tests/test.py -rA"


def test_existing_exact_grade_invocation_marker_is_supported(tmp_path, monkeypatch):
    evaluation = stock_fixture(monkeypatch)
    marker = "DTR_AJ_INVOCATION=" + "b" * 64
    env.evaluation_wrapper(tmp_path / "eval.sh", evaluation, mode="agent",
        expected_base_commit=evaluation["base_commit"], invocation_marker=marker)
    assert marker in (tmp_path / "eval.sh").read_text()
    with pytest.raises(ValueError, match="marker unsafe"):
        env.evaluation_wrapper(tmp_path / "bad.sh", evaluation, mode="agent",
            expected_base_commit=evaluation["base_commit"], invocation_marker="DTR_AJ_INVOCATION=$(cat /private)")


@pytest.mark.parametrize("mutation", ("stock", "test_patch", "base", "unknown"))
def test_identity_failure_rejects_before_wrapper_creation(tmp_path, monkeypatch, mutation):
    evaluation = stock_fixture(monkeypatch)
    if mutation == "stock": evaluation["stock_eval_script"] += "echo unbound\n"
    elif mutation == "test_patch": evaluation["test_patch_sha256"] = "0" * 64
    elif mutation == "base": evaluation["base_commit"] = "b" * 40
    else: evaluation["instance_id"] = "unknown__task-1"
    with pytest.raises(ValueError):
        env.evaluation_wrapper(tmp_path / "eval.sh", evaluation, mode="baseline", expected_base_commit="a" * 40)
    assert not (tmp_path / "eval.sh").exists()


def stage_fixture(rc=0):
    runtime = {"python": "3.9.20", "executable": env.TESTBED_PYTHON,
        "modules": [{"module": "requests", "file": "/testbed/requests/__init__.py"}],
        "localhost": ["127.0.0.1", "::1"], "interfaces": ["lo"], "routes": [],
        "packages": [{"name": "requests", "version": "2.27.0"}]}
    raw = ("DTR_AL_RUNTIME\t" + json.dumps(runtime) + "\n" + "".join(
        f"{env.STAGE_PREFIX}{name}\t{rc if name == 'test_run' else 0}\n" for name in env.STAGES)).encode()
    return raw, {"reason": "exited", "error": None, "returncode": rc, "retained_bytes": len(raw)}


@pytest.mark.parametrize("rc", (0, 1))
def test_actual_test_rc_is_accepted_only_with_complete_stage_evidence(rc):
    raw, supervisor = stage_fixture(rc)
    assert env.assess_stages(raw, supervisor, task_id="psf__requests-6028")["accepted"]


@pytest.mark.parametrize("mutation", ("missing", "duplicate", "order", "setup_nonzero", "test2", "masked_rc",
    "timeout", "error", "retained", "bad_runtime", "runtime_duplicate", "task", "external_address", "interface", "route", "module"))
def test_failure_and_measurement_mutations_are_rejected(mutation):
    raw, supervisor = stage_fixture(1)
    task_id = "psf__requests-6028"
    if mutation == "missing": raw = raw.replace(b"DTR_AL_STAGE\tsource\t0\n", b"")
    elif mutation == "duplicate": raw += b"DTR_AL_STAGE\tsource\t0\n"
    elif mutation == "order": raw = raw.replace(b"\tsource\t0", b"\tcandidate\t0")
    elif mutation == "setup_nonzero": raw = raw.replace(b"\tsource\t0", b"\tsource\t1")
    elif mutation == "test2": raw = raw.replace(b"\ttest_run\t1", b"\ttest_run\t2"); supervisor["returncode"] = 2
    elif mutation == "masked_rc": supervisor["returncode"] = 0
    elif mutation == "timeout": supervisor["reason"] = "deadline"
    elif mutation == "error": supervisor["error"] = "failed"
    elif mutation == "retained": supervisor["retained_bytes"] = 0
    elif mutation == "bad_runtime": raw = raw.replace(b'"python": "3.9.20"', b'"python": null')
    elif mutation == "runtime_duplicate": raw = raw.replace(b'"python": "3.9.20"', b'"python": "3.9.20", "python": "3.9.20"')
    elif mutation == "task": task_id = "pydata__xarray-6461"
    elif mutation == "external_address": raw = raw.replace(b"127.0.0.1", b"8.8.8.8")
    elif mutation == "interface": raw = raw.replace(b'"interfaces": ["lo"]', b'"interfaces": ["lo", "eth0"]')
    elif mutation == "route": raw = raw.replace(b'"routes": []', b'"routes": ["route"]')
    elif mutation == "module": raw = raw.replace(b"/testbed/requests", b"/opt/private/requests")
    if mutation != "retained": supervisor["retained_bytes"] = len(raw)
    assert not env.assess_stages(raw, supervisor, task_id=task_id)["accepted"]


def test_hosts_is_authored_exclusive_readonly_and_identical_for_models(tmp_path, environment):
    binds = env.hosts_binds(tmp_path)
    path = tmp_path / "localhost.hosts"
    assert binds == ["--bind", f"{path.resolve()}:/etc/hosts:ro"]
    assert path.read_bytes() == runner.LOCALHOST_HOSTS_BYTES == env.HOSTS_BYTES
    assert path.stat().st_mode & 0o777 == 0o400
    with pytest.raises(FileExistsError): env.hosts_binds(tmp_path)
    argv = environment._container_argv("true", "/testbed")
    assert f"{environment.localhost_hosts}:/etc/hosts:ro" in argv
    assert argv[argv.index("--network") + 1] == "none"
    assert "--no-home" in argv and "hostfs,bind-paths" in argv
    assert argv[-3:] == ["/bin/bash", "-c", "true"]
    for key, value in runner.FIXED_TOOL_ENVIRONMENT.items():
        assert f"{key}={value}" in argv
        assert f"{key}={value}" in env.container_environment_args()
    assert runner.FIXED_TOOL_ENVIRONMENT["PATH"].split(":")[0] == "/opt/miniconda3/envs/testbed/bin"
    assert runner.FIXED_TOOL_ENVIRONMENT["BASH_ENV"] == "/dev/null"
    assert runner.FIXED_TOOL_ENVIRONMENT["PIP_NO_INDEX"] == "1"
    assert environment.serialize()["info"]["config"]["localhost_hosts_sha256"] == env.HOSTS_SHA256
    assert environment.serialize()["info"]["config"]["tool_environment_sha256"] == runner.FIXED_TOOL_ENVIRONMENT_SHA256
    environment.localhost_hosts.chmod(0o600)
    environment.localhost_hosts.write_bytes(b"8.8.8.8 localhost\n")
    with pytest.raises(RuntimeError, match="hosts file changed"):
        environment._container_argv("true", "/testbed")


def toy_source(tmp_path, monkeypatch, *, delta_path=None, allow_sphinx=False):
    tree = tmp_path / "tree"; tree.mkdir()
    subprocess.run(["git", "init", "-q", str(tree)], check=True)
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tree), *args]).decode().strip()
    git("config", "user.name", "Inert fixture"); git("config", "user.email", "fixture@example.invalid")
    (tree / "module.py").write_text("x = 1\n")
    (tree / "setup.py").write_text("base\n"); (tree / "tox.ini").write_text("base\n")
    git("add", "."); git("commit", "-qm", "base"); base = git("rev-parse", "HEAD")
    if allow_sphinx:
        (tree / "setup.py").write_text("pinned installed dependency setup\n")
        (tree / "tox.ini").write_text("reporting setup\n")
    elif delta_path:
        (tree / delta_path).write_text("unreviewed change\n")
    if delta_path or allow_sphinx:
        git("add", "."); git("commit", "-qm", "setup child")
    tid = env.SPHINX_TASK if allow_sphinx else "psf__requests-6028"
    monkeypatch.setattr(env, "frozen_tasks", lambda: {tid: {"base_commit": base}})
    if allow_sphinx:
        delta = subprocess.check_output(["git", "-C", str(tree), "diff", "--no-ext-diff", "--no-textconv", base, "HEAD"])
        monkeypatch.setattr(env, "SPHINX_DELTA_SHA256", env.sha(delta))
    archive = tmp_path / "original.tar"
    with tarfile.open(archive, "w") as t: t.add(tree, arcname="testbed")
    return tree, archive, tid, base


@pytest.mark.parametrize("sphinx", (False, True))
def test_all_source_normalization_is_clean_base_and_original_immutable(tmp_path, monkeypatch, sphinx):
    tree, archive, tid, base = toy_source(tmp_path, monkeypatch, allow_sphinx=sphinx)
    original = archive.read_bytes()
    result = env.prepare_source_archive(archive, tmp_path / "normalized.tar", base_commit=base, task_id=tid)
    assert result["accepted"] and result["head"] == base and result["tree"] == result["base_tree"]
    assert result["model_tree_contract"] == "equal_tree" and archive.read_bytes() == original
    assert sorted(result["original_delta_paths"]) == (["setup.py", "tox.ini"] if sphinx else [])
    extracted = tmp_path / "normalized"
    env.shared._safe_extract_source_tar(tmp_path / "normalized.tar", extracted)
    assert (extracted / "module.py").read_text() == "x = 1\n"
    assert (extracted / "setup.py").read_text() == "base\n"
    assert (extracted / "tox.ini").read_text() == "base\n"
    assert not (tmp_path / "normalized.tar.seed").exists()


@pytest.mark.parametrize("path", ("module.py", "setup.py", "tox.ini"))
def test_unreviewed_source_and_setup_deltas_fail_before_new_archive(tmp_path, monkeypatch, path):
    tree, archive, tid, base = toy_source(tmp_path, monkeypatch, delta_path=path)
    with pytest.raises(ValueError, match="unreviewed"):
        env.prepare_source_archive(archive, tmp_path / "normalized.tar", base_commit=base, task_id=tid)
    assert not (tmp_path / "normalized.tar").exists()
    assert not (tmp_path / "normalized.tar.seed").exists()


def test_future_branch_dangling_solution_replace_refs_and_hooks_are_absent(tmp_path, monkeypatch):
    tree, archive, tid, base = toy_source(tmp_path, monkeypatch)
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tree), *args]).decode().strip()
    (tree / "secret_solution.py").write_text("FUTURE_SOLUTION = 42\n")
    git("add", "."); git("commit", "-qm", "future solution")
    future = git("rev-parse", "HEAD"); git("branch", "future-solution")
    (tree / "secret_solution.py").write_text("DANGLING_FUTURE_SOLUTION = 43\n")
    git("add", "."); git("commit", "-qm", "dangling future solution")
    dangling = git("rev-parse", "HEAD")
    git("checkout", "--detach", "-q", base)
    git("remote", "add", "future-origin", "https://example.invalid/private-future.git")
    git("replace", base, future)
    hook = tree / ".git" / "hooks" / "post-checkout"
    hook.write_text("#!/bin/sh\ntouch SHOULDNTRUN\n"); hook.chmod(0o700)
    archive.unlink()
    with tarfile.open(archive, "w") as t: t.add(tree, arcname="testbed")
    result = env.prepare_source_archive(archive, tmp_path / "normalized.tar", base_commit=base, task_id=tid)
    assert result["git_history_boundary"]["future_history_empty"]
    assert result["git_history_boundary"]["fsck_unreachable_empty"]
    extracted = tmp_path / "normalized"
    env.shared._safe_extract_source_tar(tmp_path / "normalized.tar", extracted)
    for commit in (future, dangling):
        assert subprocess.run(["git", "-C", str(extracted), "cat-file", "-e", commit], capture_output=True).returncode != 0
    assert env._git(extracted, "rev-list", "--all", "--not", base) == b""
    assert env._git(extracted, "fsck", "--full", "--no-reflogs", "--unreachable") == b""
    assert env._git(extracted, "remote") == b""
    assert not (extracted / "secret_solution.py").exists()
    assert not (extracted / "SHOULDNTRUN").exists()
    assert not (extracted / ".git" / "hooks").exists()
    assert not (extracted / ".git" / "refs" / "replace").exists()


@pytest.mark.parametrize('fault', ('known', 'other_commit', 'corruption', 'unreachable', 'wrong_exit'))
def test_legacy_metadata_exception_is_exact_and_never_hides_object_failure(tmp_path, monkeypatch, fault):
    tree, archive, tid, base = toy_source(tmp_path, monkeypatch)
    monkeypatch.setattr(env, 'REQUESTS_LEGACY_BASE', base)
    original = env._git
    ignored = []
    def git(path, *args):
        if args == ('fsck', '--full', '--no-reflogs', '--unreachable'):
            stderr = env.REQUESTS_LEGACY_FSCK
            if fault == 'other_commit': stderr += b'\nerror in commit OTHER: badTimezone'
            if fault == 'corruption': stderr = b'error: hash mismatch in object'
            raise subprocess.CalledProcessError(1 if fault == 'wrong_exit' else 4,
                ['git', 'fsck'], output=b'dangling blob BAD' if fault == 'unreachable' else b'', stderr=stderr)
        if args[:2] == ('-c', 'fsck.badTimezone=ignore'): ignored.append(True)
        return original(path, *args)
    monkeypatch.setattr(env, '_git', git)
    if fault == 'known':
        r = env.prepare_source_archive(archive, tmp_path / 'normalized.tar', base_commit=base, task_id=tid)
        assert r['git_history_boundary']['reviewed_legacy_metadata_diagnostic'] == env.REQUESTS_LEGACY_FSCK.decode()
        assert ignored == [True]
    else:
        with pytest.raises(subprocess.CalledProcessError):
            env.prepare_source_archive(archive, tmp_path / 'normalized.tar', base_commit=base, task_id=tid)
        assert not ignored
        assert not (tmp_path / 'normalized.tar').exists()
