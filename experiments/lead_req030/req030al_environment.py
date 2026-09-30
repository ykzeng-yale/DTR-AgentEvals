"""Prospectively revised offline source/evaluator contract for REQ030AL.

This is a new execution variant, not a claim of official Docker equivalence.
The original task inputs, image digests and declared test identities are kept.
All model and evaluator workspaces start at the actual public base commit;
preinstalled dependencies/native extensions remain in the immutable task image.
No reference or test-patch bytes enter source normalization or model launch.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tarfile
from typing import Any

from experiments.lead_req030 import req030ag_screen as shared

ROOT = Path(__file__).resolve().parents[2]
AK_SHA256 = "7dea2cec3e0ef2a141ef91cb1f799a2a31820ba96b8b37e133625fb8832d7a9c"
SCHEMA = "dtr.req030al.offline_environment.v1"
TESTBED_PYTHON = "/opt/miniconda3/envs/testbed/bin/python"
HOSTS_BYTES = b"127.0.0.1 localhost\n::1 localhost ip6-localhost ip6-loopback\n"
HOSTS_SHA256 = hashlib.sha256(HOSTS_BYTES).hexdigest()
SPHINX_TASK = "sphinx-doc__sphinx-8593"
SPHINX_DELTA_SHA256 = "71dbabe891e7add5c0a2dad354e65b233ac74aef3fd5888532515acee48872d9"
MODULES = {
    "django__django-12039": ("django",),
    "matplotlib__matplotlib-26208": ("matplotlib", "matplotlib._path"),
    "psf__requests-6028": ("requests",),
    "pydata__xarray-6461": ("xarray",),
    "pylint-dev__pylint-6386": ("pylint",),
    "pytest-dev__pytest-10081": ("pytest", "_pytest"),
    "scikit-learn__scikit-learn-25102": ("sklearn", "sklearn.__check_build._check_build"),
    "sphinx-doc__sphinx-8593": ("sphinx",),
}
STAGES = ("isolation", "source", "runtime", "candidate", "test_checkout", "test_patch", "test_run")
STAGE_PREFIX = "DTR_AL_STAGE\t"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def frozen_tasks() -> dict[str, dict]:
    raw = (ROOT / "configs/req030ak_controls_20260930.json").read_bytes()
    if sha(raw) != AK_SHA256:
        raise ValueError("original complete cohort identity changed")
    doc = json.loads(raw)
    tasks = {task["instance_id"]: task for task in doc["tasks"]}
    if set(tasks) != set(MODULES):
        raise ValueError("original eight-task denominator changed")
    return tasks


def hosts_binds(directory: Path) -> list[str]:
    """Exactly one authored, immutable loopback-only hosts file; no host copy."""
    path = directory / "localhost.hosts"
    with path.open("xb") as out:
        out.write(HOSTS_BYTES); out.flush(); os.fsync(out.fileno())
    path.chmod(0o400)
    return ["--bind", f"{path.resolve()}:/etc/hosts:ro"]


def container_environment_args() -> list[str]:
    """The evaluator receives exactly the model tool environment before Bash."""
    from experiments.lead_req030.req030ag_seaborn_apptainer_runner import FIXED_TOOL_ENVIRONMENT
    return [part for key, value in sorted(FIXED_TOOL_ENVIRONMENT.items())
            for part in ("--env", f"{key}={value}")]


def _git_command(tree: Path, *args: str) -> tuple[list[str], dict]:
    # Task repository config cannot invoke a hook/fsmonitor/external diff.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL="/dev/null", GIT_NO_REPLACE_OBJECTS="1")
    return ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
        "-c", "core.untrackedCache=false", "-C", str(tree), *args], env


def _git(tree: Path, *args: str) -> bytes:
    argv, variables = _git_command(tree, *args)
    return subprocess.check_output(argv, env=variables, stderr=subprocess.PIPE, timeout=180)


def _retain_base_git_only(tree: Path, base: str) -> dict:
    """Fresh Git metadata contains only objects reachable from immutable base.

    Removing refs alone would leave solutions recoverable through old packs or
    dangling objects. Export one non-thin reachable pack, import it into a new
    repository, then discard all original refs/config/hooks/reflogs/alternates.
    """
    fresh = tree.parent / (tree.name + ".base_git")
    pack = tree.parent / (tree.name + ".base.pack")
    old = tree.parent / (tree.name + ".old_git")
    try:
        argv, variables = _git_command(tree, "pack-objects", "--revs", "--stdout", "--no-reuse-delta")
        with pack.open("xb") as out:
            subprocess.run(argv, input=(base + "\n").encode(), stdout=out, stderr=subprocess.PIPE,
                env=variables, timeout=180, check=True)
            out.flush(); os.fsync(out.fileno())
        _git(tree, "init", "--bare", "--quiet", str(fresh))
        argv, variables = _git_command(tree, "--git-dir", str(fresh), "index-pack", "--stdin")
        with pack.open("rb") as source:
            subprocess.run(argv, stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=variables, timeout=180, check=True)
        _git(tree, "--git-dir", str(fresh), "config", "core.bare", "false")
        _git(tree, "--git-dir", str(fresh), "config", "core.logAllRefUpdates", "false")
        (fresh / "HEAD").write_text(base + "\n")
        # Preserve only actual base-reachable shallow boundaries if the source
        # clone is shallow; never include an unrelated branch boundary.
        shallow = tree / ".git" / "shallow"
        if shallow.exists():
            reachable = set(_git(tree, "rev-list", base).decode().splitlines())
            boundaries = [line for line in shallow.read_text().splitlines() if line in reachable]
            if boundaries:
                (fresh / "shallow").write_text("\n".join(boundaries) + "\n")
        shutil.rmtree(fresh / "hooks", ignore_errors=True)
        (tree / ".git").rename(old)
        fresh.rename(tree / ".git")
        _git(tree, "reset", "--hard", base)
        if _git(tree, "rev-list", "--all", "--not", base):
            raise ValueError("non-base future Git history retained")
        fsck = _git(tree, "fsck", "--full", "--no-reflogs", "--unreachable")
        if fsck.strip():
            raise ValueError("unreachable or dangling Git objects retained")
        forbidden = [tree / ".git" / x for x in ("logs", "hooks", "objects/info/alternates", "refs/remotes", "refs/replace")]
        if any(p.exists() for p in forbidden):
            raise ValueError("original external/history Git metadata retained")
        refs = _git(tree, "for-each-ref").decode().strip()
        if refs:
            raise ValueError("original branch/tag refs retained")
        return {"policy": "only public base-reachable object closure; detached HEAD; no future/unreachable objects",
            "all_refs_removed": True, "future_history_empty": True, "fsck_unreachable_empty": True,
            "git_replace_disabled": True, "exported_pack_sha256": shared.sha_file(pack),
            "exported_pack_bytes": pack.stat().st_size}
    finally:
        if pack.exists(): pack.unlink()
        for directory in (fresh, old):
            if directory.exists(): shutil.rmtree(directory)


def prepare_source_archive(source_tar: Path, destination_tar: Path, *, base_commit: str,
                           task_id: str) -> dict:
    """Audit setup-only delta, then normalize all eight tasks to public base.

    Native ignored build products are retained unchanged for the fixed installed
    environment. A source or test delta outside the exact Sphinx setup delta is
    rejected before mutation. Original source/SIF artifacts are never changed.
    """
    task = frozen_tasks().get(task_id)
    if task is None or base_commit != task["base_commit"]:
        raise ValueError("source normalization task/base mismatch")
    if destination_tar.exists() or destination_tar.is_symlink():
        raise FileExistsError(destination_tar)
    temp = destination_tar.parent / (destination_tar.name + ".seed")
    receipt = {"schema": SCHEMA, "task_id": task_id, "base_commit": base_commit,
        "original_source_sha256": shared.sha_file(source_tar),
        "normalization": "all tracked source and HEAD restored to public base; installed dependencies unchanged"}
    try:
        extracted = shared._safe_extract_source_tar(source_tar, temp)
        if (temp / ".git").is_symlink() or not (temp / ".git").is_dir():
            raise ValueError("ordinary task Git directory required")
        head = _git(temp, "rev-parse", "HEAD").decode().strip()
        base_tree = _git(temp, "rev-parse", f"{base_commit}^{{tree}}").decode().strip()
        old_tree = _git(temp, "rev-parse", "HEAD^{tree}").decode().strip()
        paths = _git(temp, "diff", "--no-ext-diff", "--no-textconv", "--name-only", base_commit, "HEAD").decode().splitlines()
        delta = _git(temp, "diff", "--no-ext-diff", "--no-textconv", base_commit, "HEAD")
        if paths:
            if (task_id != SPHINX_TASK or sorted(paths) != ["setup.py", "tox.ini"]
                    or sha(delta) != SPHINX_DELTA_SHA256):
                raise ValueError("unreviewed implementation/test/setup tree delta")
        elif old_tree != base_tree:
            raise ValueError("empty diff does not establish base tree equality")
        if _git(temp, "status", "--porcelain", "--untracked-files=all"):
            raise ValueError("source archive not initially clean")
        _git(temp, "reset", "--hard", base_commit)
        history_boundary = _retain_base_git_only(temp, base_commit)
        if (_git(temp, "rev-parse", "HEAD").decode().strip() != base_commit
                or _git(temp, "rev-parse", "HEAD^{tree}").decode().strip() != base_tree
                or _git(temp, "status", "--porcelain", "--untracked-files=all")):
            raise ValueError("normalized source is not clean public base")
        with destination_tar.open("xb") as stream:
            with tarfile.open(fileobj=stream, mode="w", format=tarfile.PAX_FORMAT) as archive:
                archive.add(temp, arcname="testbed", recursive=True)
            stream.flush(); os.fsync(stream.fileno())
        destination_tar.chmod(0o400)
        receipt.update(original_head=head, original_tree=old_tree, original_delta_paths=paths,
            original_delta_sha256=sha(delta), head=base_commit, tree=base_tree, base_tree=base_tree,
            source_tar_sha256=shared.sha_file(destination_tar), source_tar_bytes=destination_tar.stat().st_size,
            accepted=True, model_tree_contract="equal_tree", extraction=extracted)
        receipt["git_history_boundary"] = history_boundary
        return receipt
    except BaseException:
        if destination_tar.exists():
            destination_tar.unlink()
        raise
    finally:
        if temp.exists():
            shutil.rmtree(temp)


def offline_script(evaluation: dict) -> tuple[str, dict]:
    """Transform exactly frozen stock bytes, keeping patch/check identities.

    No package installation, locale generation, global Git trust change or final
    command that masks the test exit code is executed. All such divergences are
    recorded as this new fixed-dependency variant before any model outcome.
    """
    task = frozen_tasks().get(evaluation.get("instance_id"))
    script = evaluation.get("stock_eval_script")
    if (task is None or not isinstance(script, str) or sha(script.encode()) != task["stock_eval_script_sha256"]
            or evaluation.get("base_commit") != task["base_commit"]):
        raise ValueError("stock evaluator/task identity mismatch")
    lines = script.splitlines()
    start = lines.index(": '>>>>> Start Test Output'")
    end = lines.index(": '>>>>> End Test Output'")
    if end != start + 2 or lines.count(": '>>>>> Start Test Output'") != 1 or lines.count(": '>>>>> End Test Output'") != 1:
        raise ValueError("stock test framing differs")
    apply_start = next(i for i, line in enumerate(lines) if line == "git apply -v - <<'EOF_114329324912'")
    apply_end = lines.index("EOF_114329324912", apply_start + 1)
    # Upstream appends a newline before its delimiter; the preserved final
    # empty splitline already carries the original patch's terminating newline.
    patch = "\n".join(lines[apply_start + 1:apply_end])
    if sha(patch.encode()) != task["test_patch_sha256"] or evaluation.get("test_patch_sha256") != sha(patch.encode()):
        raise ValueError("stock test patch identity differs")
    checkout = lines[apply_start - 1]
    expected_prefix = f"git checkout {task['base_commit']} "
    if not checkout.startswith(expected_prefix):
        raise ValueError("test checkout is not declared base")
    test_paths = shlex.split(checkout[len(expected_prefix):])
    if not test_paths or any(p.startswith("/") or ".." in Path(p).parts for p in test_paths):
        raise ValueError("test checkout paths invalid")
    install = [line for line in lines[:apply_start] if line.startswith("python -m pip install ")]
    if len(install) != 1:
        raise ValueError("exactly one frozen scoring-time installation expected")
    original_command = lines[start + 1]
    if original_command.startswith("pytest -rA "):
        command = TESTBED_PYTHON + " -m " + original_command
    elif task["instance_id"] == "django__django-12039" and original_command.startswith("./tests/runtests.py "):
        command = TESTBED_PYTHON + " " + original_command[2:]
    elif task["instance_id"] == SPHINX_TASK and original_command.startswith("tox --current-env -epy39 -v -- "):
        # Public base tox.ini uses the same python -Xdev -m pytest command but
        # lacks -rA. Add reporting-only -rA via its existing posargs interface.
        command = "/opt/miniconda3/envs/testbed/bin/tox " + original_command[4:] + " -rA"
    else:
        raise ValueError("unrecognized frozen test invocation")
    return patch, {"schema": SCHEMA, "task_id": task["instance_id"], "base_commit": task["base_commit"],
        "stock_eval_script_sha256": sha(script.encode()), "test_patch_sha256": sha(patch.encode()),
        "test_paths": test_paths, "test_command": command, "original_test_command": original_command,
        "omitted_install_command": install[0], "installed_dependency_policy": "immutable SIF; no installs during scoring",
        "official_docker_execution_verified": False, "hosts_sha256": HOSTS_SHA256}


def _runtime_code(task_id: str) -> str:
    return "\n".join([
        "import importlib, importlib.metadata as md, json, pathlib, socket, sys",
        "records = []",
        f"for name in {MODULES[task_id]!r}:",
        "    m = importlib.import_module(name)",
        "    path = pathlib.Path(m.__file__).resolve()",
        "    if not str(path).startswith('/testbed/'): raise RuntimeError('task module outside bound public source: ' + name)",
        "    records.append({'module': name, 'file': str(path)})",
        "addresses = sorted({v[4][0] for v in socket.getaddrinfo('localhost', 0)})",
        "if not addresses or not set(addresses) <= {'127.0.0.1', '::1'}: raise RuntimeError('localhost resolution invalid')",
        "sock = socket.socket(); sock.bind(('localhost', 0)); sock.close()",
        "interfaces = [line.split(':', 1)[0].strip() for line in pathlib.Path('/proc/net/dev').read_text().splitlines()[2:]]",
        "if interfaces != ['lo']: raise RuntimeError('non-loopback network interface')",
        "routes = pathlib.Path('/proc/net/route').read_text().splitlines()[1:]",
        "if routes: raise RuntimeError('IPv4 route present under network-none')",
        "packages = sorted([{'name': d.metadata['Name'], 'version': d.version} for d in md.distributions()], key=lambda x: (x['name'] or '', x['version']))",
        "print('DTR_AL_RUNTIME\\t' + json.dumps({'python': sys.version, 'executable': sys.executable, 'modules': records, 'localhost': addresses, 'interfaces': interfaces, 'routes': routes, 'packages': packages}, sort_keys=True))",
    ])


def evaluation_wrapper(path: Path, evaluation: dict, *, mode: str, expected_base_commit: str,
                       invocation_marker: str | None = None) -> dict:
    patch, design = offline_script(evaluation)
    if expected_base_commit != design["base_commit"] or mode not in ("baseline", "reference", "agent"):
        raise ValueError("wrapper mode/base mismatch")
    if (invocation_marker is not None and re.fullmatch(r"[A-Za-z0-9_:.-]{1,256}", invocation_marker) is None
            and re.fullmatch(r"DTR_AJ_INVOCATION=[0-9a-f]{64}", invocation_marker) is None):
        raise ValueError("invocation marker unsafe")
    base = expected_base_commit
    lines = ["#!/bin/bash", "set -euo pipefail", "umask 077",
        "export PATH=/opt/miniconda3/envs/testbed/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
        "export PIP_NO_INDEX=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PYTHONDONTWRITEBYTECODE=1",
        "export LANG=C.UTF-8 LANGUAGE=C LC_ALL=C.UTF-8",
        "stage() { printf 'DTR_AL_STAGE\\t%s\\t%s\\n' \"$1\" \"$2\"; }",
        "fail() { stage \"$1\" \"$2\"; printf 'DTR_SETUP_FAILURE\\n'; exit \"$2\"; }"]
    if invocation_marker:
        lines.append(f"printf '%s\\n' {shlex.quote(invocation_marker)}")
    lines += [
        'test "$(readlink /proc/self/ns/net)" != "$DTR_HOST_NET_ID" || fail isolation 80',
        "test ! -e /home/yz2324 || fail isolation 81",
        "test ! -e /nfs/roberts || fail isolation 82",
        "if touch /DTR_ROOT_WRITE_TEST 2>/dev/null; then rm -f /DTR_ROOT_WRITE_TEST; fail isolation 83; fi",
        f"test \"$(sha256sum /etc/hosts | cut -d' ' -f1)\" = {HOSTS_SHA256} || fail isolation 85",
        "stage isolation 0", "cd /testbed", "test -d .git || fail source 84",
        f"test \"$(git rev-parse HEAD)\" = '{base}' || fail source 90",
        f"test \"$(git rev-parse HEAD^{{tree}})\" = \"$(git rev-parse '{base}^{{tree}}')\" || fail source 90",
        "test -z \"$(git status --porcelain --untracked-files=all)\" || fail source 90",
        "stage source 0", f"if {TESTBED_PYTHON} - <<'DTR_AL_RUNTIME_PY'",
        _runtime_code(design["task_id"]), "DTR_AL_RUNTIME_PY", "then stage runtime 0; else fail runtime 87; fi"]
    if mode != "baseline":
        candidate = "/eval/reference.diff" if mode == "reference" else "/eval/agent.diff"
        lines += [f"git apply --check {candidate} || fail candidate 91",
                  f"git apply {candidate} || fail candidate 92"]
    lines += ["stage candidate 0", f"git checkout {base} -- {' '.join(shlex.quote(p) for p in design['test_paths'])} || fail test_checkout 93",
        "stage test_checkout 0", "if git apply -v - <<'EOF_114329324912'", patch.rstrip("\n"),
        "EOF_114329324912", "then stage test_patch 0; else fail test_patch 94; fi",
        "printf 'DTR_TEST_START\\n'", "printf '>>>>> Start Test Output\\n'", "set +e",
        design["test_command"], "test_rc=$?", "set -e", "printf '>>>>> End Test Output\\n'",
        'stage test_run "$test_rc"', "printf 'DTR_TEST_END\\n'", 'exit "$test_rc"']
    data = ("\n".join(lines) + "\n").encode()
    with path.open("xb") as file:
        file.write(data); file.flush(); os.fsync(file.fileno())
    path.chmod(0o500)
    subprocess.run(["bash", "-n", str(path)], check=True, timeout=10, capture_output=True)
    return {**design, "wrapper_sha256": sha(data), "wrapper_bytes": len(data), "mode": mode}


def assess_stages(raw: bytes, supervisor: dict, *, task_id: str | None = None) -> dict:
    """Fail closed: setup0+unique stages+actual test0/1+matching supervisor rc."""
    text = raw.decode("utf-8", "replace")
    records = []
    for line in text.splitlines():
        if line.startswith(STAGE_PREFIX):
            fields = line.split("\t")
            if len(fields) != 3 or not fields[2].isdigit():
                return {"accepted": False, "reason": "malformed_stage", "stages": records}
            records.append({"stage": fields[1], "returncode": int(fields[2])})
    runtime_lines = [line.split("\t", 1)[1] for line in text.splitlines() if line.startswith("DTR_AL_RUNTIME\t")]
    runtime = None
    try:
        if len(runtime_lines) != 1:
            raise ValueError("one runtime receipt required")
        def unique(pairs):
            values = {}
            for key, value in pairs:
                if key in values:
                    raise ValueError("duplicate runtime key")
                values[key] = value
            return values
        runtime = json.loads(runtime_lines[0], object_pairs_hook=unique)
        if (set(runtime) != {"python", "executable", "modules", "localhost", "interfaces", "routes", "packages"}
                or runtime["executable"] != TESTBED_PYTHON or not isinstance(runtime["python"], str)
                or not runtime["python"] or runtime["interfaces"] != ["lo"] or runtime["routes"] != []
                or not isinstance(runtime["localhost"], list) or not runtime["localhost"]
                or not set(runtime["localhost"]) <= {"127.0.0.1", "::1"}
                or not isinstance(runtime["modules"], list) or not runtime["modules"]
                or any(set(v) != {"module", "file"} or not isinstance(v["module"], str)
                       or not isinstance(v["file"], str) or not v["file"].startswith("/testbed/") for v in runtime["modules"])
                or not isinstance(runtime["packages"], list) or not runtime["packages"]
                or any(set(v) != {"name", "version"} or not isinstance(v["name"], str) or not v["name"]
                       or not isinstance(v["version"], str) or not v["version"] for v in runtime["packages"])):
            raise ValueError("runtime receipt contract mismatch")
        modules = tuple(v["module"] for v in runtime["modules"])
        if task_id is not None:
            if MODULES.get(task_id) != modules:
                raise ValueError("runtime module/task mismatch")
        elif modules not in MODULES.values():
            raise ValueError("unknown task module set")
    except (ValueError, KeyError, TypeError, AttributeError):
        return {"schema": SCHEMA, "accepted": False, "reason": "runtime_receipt_invalid", "stages": records}
    accepted = ([x["stage"] for x in records] == list(STAGES)
        and all(x["returncode"] == 0 for x in records[:-1])
        and records[-1]["returncode"] in (0, 1)
        and supervisor.get("reason") == "exited" and supervisor.get("error") is None
        and supervisor.get("returncode") == records[-1]["returncode"]
        and len(raw) == supervisor.get("retained_bytes")
        and "DTR_SETUP_FAILURE" not in text)
    return {"schema": SCHEMA, "accepted": accepted, "reason": "complete_stage_receipts" if accepted else "stage_or_process_failure",
        "stages": records, "runtime": runtime, "raw_sha256": sha(raw), "hosts_sha256": HOSTS_SHA256}
