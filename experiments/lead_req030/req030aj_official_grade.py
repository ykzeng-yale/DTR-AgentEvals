"""Exact upstream SWE-bench scoring replay alongside the separate strict score.

This CPU helper executes byte-pinned, unmodified upstream grading/parser bodies.
It does not execute Docker, apply a candidate, run tests, or establish equivalence
of our Apptainer environment to the official Docker execution environment.
"""
from __future__ import annotations

import ast
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
from typing import Any

from experiments.lead_req030 import req030ai_candidate_grade as strict

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = "work/upstream/SWE-bench-f7bbbb2ccdf479001d6467c9e34af59e44a840f9/swebench/harness"
SOURCE_PINS = {
    f"{UPSTREAM}/grading.py": "88fc500ebaf692a53457149cec24dcf82dfa2d48f98021a894a087d275f61df4",
    f"{UPSTREAM}/constants/__init__.py": "c12fe2671fd8b7d8af8f5c711fceb2ca684254e2c1b4cde448422a44b8d04e35",
    f"{UPSTREAM}/constants/python.py": "ce4f0e0f0939745944d84c51356530f5da57f486ac839523556d7ffdb2f9072b",
    f"{UPSTREAM}/log_parsers/python.py": "42f564edfee3c21751739bbf09d60cf3a3ecdc58ac5cf45717dc6b47a85d7459",
    "experiments/lead_req030/req030ai_candidate_grade.py": "cf424527c7367e17da12cd5b15de610c0f3466dc1e0a0e2ea4598b50b73327a0",
    "configs/req030ah_controls_20260930.json": "77d7b1b33f221e829aa67f9ce59f928cbbdf0b1453d6661399142827de6e1384",
}
CONSTANT_NAMES = {
    "APPLY_PATCH_FAIL", "END_TEST_OUTPUT", "FAIL_ONLY_REPOS", "FAIL_TO_FAIL", "FAIL_TO_PASS",
    "KEY_INSTANCE_ID", "KEY_PREDICTION", "PASS_TO_FAIL", "PASS_TO_PASS", "RESET_FAILED",
    "START_TEST_OUTPUT", "TESTS_ERROR", "TESTS_TIMEOUT", "EvalType", "ResolvedStatus", "TestStatus",
}
FUNCTION_NAMES = {
    "test_passed", "test_failed", "get_logs_eval", "get_eval_tests_report",
    "compute_fail_to_pass", "compute_pass_to_pass", "get_resolution_status", "get_eval_report",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _source(relative: str) -> bytes:
    data = (ROOT / relative).read_bytes()
    if sha(data) != SOURCE_PINS[relative]:
        raise ValueError(f"official scoring source pin mismatch: {relative}")
    return data


def load_pinned_scoring() -> dict:
    """Supply exact Python dependencies without importing the Docker harness.

    All scoring/parser function bodies are unchanged. The annotation-only
    TestSpec interface is supplied by SimpleNamespace; scoring consumes only
    repo/version/instance_id/FAIL_TO_PASS/PASS_TO_PASS attributes. The eight
    admitted repositories are Python, so their exact Python spec map suffices.
    """
    constants_path = f"{UPSTREAM}/constants/__init__.py"
    constants_tree = ast.parse(_source(constants_path), filename=constants_path)
    selected = []
    found = set()
    for node in constants_tree.body:
        if isinstance(node, ast.ClassDef) and node.name in CONSTANT_NAMES:
            selected.append(node); found.add(node.name)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in CONSTANT_NAMES:
                selected.append(node); found.add(name)
    if found != CONSTANT_NAMES:
        raise ValueError("upstream scoring constant/enum definitions differ")
    namespace = {"Enum": Enum, "Any": Any, "TestSpec": SimpleNamespace}
    exec(compile(ast.Module(body=selected, type_ignores=[]), constants_path, "exec"), namespace)

    python_path = f"{UPSTREAM}/constants/python.py"
    python_tree = ast.parse(_source(python_path), filename=python_path)
    if any(isinstance(node, (ast.Import, ast.ImportFrom)) for node in python_tree.body):
        raise ValueError("unexpected Python constants dependency")
    python_namespace = {}
    exec(compile(python_tree, python_path, "exec"), python_namespace)
    namespace["MAP_REPO_VERSION_TO_SPECS"] = python_namespace["MAP_REPO_VERSION_TO_SPECS_PY"]

    parser_path = f"{UPSTREAM}/log_parsers/python.py"
    parser_tree = ast.parse(_source(parser_path), filename=parser_path)
    parser_imports = [node.module for node in parser_tree.body if isinstance(node, ast.ImportFrom)]
    if parser_imports != ["swebench.harness.constants", "swebench.harness.test_spec.test_spec"]:
        raise ValueError("unexpected official parser dependencies")
    parser_tree.body = [node for node in parser_tree.body if not isinstance(node, ast.ImportFrom)]
    parser_namespace = {"TestStatus": namespace["TestStatus"], "TestSpec": SimpleNamespace}
    exec(compile(parser_tree, parser_path, "exec"), parser_namespace)
    namespace["MAP_REPO_TO_PARSER"] = parser_namespace["MAP_REPO_TO_PARSER_PY"]

    grading_path = f"{UPSTREAM}/grading.py"
    grading_tree = ast.parse(_source(grading_path), filename=grading_path)
    imports = [(node.module, [alias.name for alias in node.names]) for node in grading_tree.body
               if isinstance(node, ast.ImportFrom)]
    expected_imports = [
        ("typing", ["Any"]),
        ("swebench.harness.constants", [
            "APPLY_PATCH_FAIL", "END_TEST_OUTPUT", "FAIL_ONLY_REPOS", "FAIL_TO_FAIL", "FAIL_TO_PASS",
            "KEY_INSTANCE_ID", "KEY_PREDICTION", "MAP_REPO_VERSION_TO_SPECS", "PASS_TO_FAIL", "PASS_TO_PASS",
            "RESET_FAILED", "START_TEST_OUTPUT", "TESTS_ERROR", "TESTS_TIMEOUT", "EvalType", "ResolvedStatus", "TestStatus"]),
        ("swebench.harness.test_spec.test_spec", ["TestSpec"]),
        ("swebench.harness.log_parsers", ["MAP_REPO_TO_PARSER"]),
    ]
    if imports != expected_imports or {node.name for node in grading_tree.body if isinstance(node, ast.FunctionDef)} != FUNCTION_NAMES:
        raise ValueError("official grading kernel dependency/function contract differs")
    grading_tree.body = [node for node in grading_tree.body if not isinstance(node, ast.ImportFrom)]
    exec(compile(grading_tree, grading_path, "exec"), namespace)
    return namespace


def frozen_tasks() -> dict:
    release = strict.parse_unique(_source("configs/req030ah_controls_20260930.json"))
    return {task["instance_id"]: task for task in release["tasks"]}


def replay_official(*, task: dict, evaluator_bundle: bytes, raw: bytes, patch: bytes | None,
                    expected_binding: dict, observed_binding: dict, strict_grade: dict | None = None) -> dict:
    """Return the full official per-instance map only for exactly bound artifacts.

    Preserve upstream XFAIL, missing, SKIPPED, fallback and zero-denominator
    semantics. Do not replace the declared strict endpoint with this score.
    """
    result = {"schema": "dtr.req030aj.official_scoring_replay.v1", "available": False,
        "kind": "exact upstream scoring replay on isolated evaluator output",
        "official_docker_execution_verified": False, "upstream_report_map": {},
        "source_pins": dict(SOURCE_PINS), "reason": "unverified_artifacts",
        "strict_endpoint": {"provided": strict_grade is not None, "result": strict_grade}}

    def reject(reason):
        result["reason"] = reason
        return result

    if (type(raw) is not bytes or type(evaluator_bundle) is not bytes
            or patch is not None and type(patch) is not bytes
            or len(raw) > strict.controls.shared.MAX_EPISODE_OUTPUT
            or len(evaluator_bundle) > strict.MAX_EVALUATOR_BYTES
            or patch is not None and len(patch) > strict.MAX_PATCH_BYTES):
        return reject("invalid_artifact_types_or_size")
    result.update(raw_sha256=sha(raw), raw_bytes=len(raw), patch_sha256=sha(patch or b""),
                  patch_bytes=len(patch or b""), prediction_patch_is_none=patch is None,
                  evaluator_bundle_sha256=sha(evaluator_bundle))
    if (not isinstance(expected_binding, dict) or not isinstance(observed_binding, dict)
            or set(expected_binding) != strict.BINDING_FIELDS or expected_binding != observed_binding):
        return reject("task_policy_invocation_binding_mismatch")
    if (not isinstance(task, dict)
            or set(task) != {"instance_id", "repo", "base_commit", "evaluator_bundle_sha256"}):
        return reject("invalid_task_identity")
    try:
        _source("experiments/lead_req030/req030ai_candidate_grade.py")
        original = frozen_tasks()[task["instance_id"]]
        if (any(task[key] != original[key] for key in ("instance_id", "repo", "base_commit"))
                or sha(evaluator_bundle) != original["evaluator_bundle_sha256"]
                or task["evaluator_bundle_sha256"] != sha(evaluator_bundle)):
            return reject("frozen_task_evaluator_identity_mismatch")
        identity = {"task_id": task["instance_id"], "repo": task["repo"], "base_commit": task["base_commit"],
            "evaluator_bundle_sha256": sha(evaluator_bundle), "raw_sha256": sha(raw), "patch_sha256": sha(patch or b""),
            "parser_sha256": SOURCE_PINS[f"{UPSTREAM}/log_parsers/python.py"]}
        if any(expected_binding[key] != value for key, value in identity.items()):
            return reject("invocation_artifact_identity_mismatch")
        if (any(not isinstance(expected_binding[key], str) or re.fullmatch(r"[A-Za-z0-9_.:/-]{1,256}", expected_binding[key]) is None
                for key in ("policy_id", "invocation_id"))
                or any(not isinstance(expected_binding[key], str) or re.fullmatch(r"[0-9a-f]{64}", expected_binding[key]) is None
                       for key in ("release_sha256", "supervisor_sha256"))):
            return reject("invalid_invocation_identity")
        if strict_grade is not None:
            if (not isinstance(strict_grade, dict) or strict_grade.get("raw_sha256") != sha(raw)
                    or strict_grade.get("patch_sha256") != sha(patch or b"")
                    or strict_grade.get("evaluator_bundle_sha256") != sha(evaluator_bundle)
                    or strict_grade.get("parser_sha256") != identity["parser_sha256"]):
                result["strict_endpoint"] = {"provided": True, "result": None}
                return reject("strict_score_artifact_identity_mismatch")
        evaluation = strict.parse_unique(evaluator_bundle)
        if (evaluation["instance_id"] != task["instance_id"] or evaluation["base_commit"] != task["base_commit"]
                or len(evaluation["fail_to_pass"]) != original["fail_to_pass_count"]
                or len(evaluation["pass_to_pass"]) != original["pass_to_pass_count"]):
            return reject("declared_test_identity_mismatch")
        kernel = load_pinned_scoring()
        version = original["version"]
        spec = SimpleNamespace(instance_id=task["instance_id"], repo=task["repo"], version=version,
            FAIL_TO_PASS=evaluation["fail_to_pass"], PASS_TO_PASS=evaluation["pass_to_pass"])
        test_cmd = kernel["MAP_REPO_VERSION_TO_SPECS"][task["repo"]][version]["test_cmd"]
        # Upstream get_logs_eval chooses the final command if the spec is a list.
        selected_cmd = test_cmd[-1] if isinstance(test_cmd, list) else test_cmd
        prediction = {kernel["KEY_INSTANCE_ID"]: task["instance_id"],
                      kernel["KEY_PREDICTION"]: None if patch is None else patch.decode("utf-8", errors="strict")}
        raw.decode("utf-8", errors="strict")
        with tempfile.TemporaryDirectory(prefix="dtr-official-scoring-") as directory:
            os.chmod(directory, 0o700)
            log_path = Path(directory) / "test_output.txt"
            with log_path.open("xb") as stream:
                stream.write(raw)
            log_path.chmod(0o600)
            report = kernel["get_eval_report"](spec, prediction, str(log_path), include_tests_status=True)
        result.update(available=True, reason="upstream_scoring_replay_complete", upstream_report_map=report,
            task_id=task["instance_id"], repo=task["repo"], version=version,
            upstream_test_cmd=test_cmd, upstream_selected_test_cmd=selected_cmd,
            upstream_test_cmd_sha256=sha(canonical(test_cmd)), binding_sha256=sha(canonical(expected_binding)),
            environment_scope="scoring kernel replay only; isolated Apptainer log provenance requires separate review")
    except (KeyError, ValueError, TypeError, OSError, UnicodeError):
        return reject("invalid_upstream_source_or_evaluation_evidence")
    return result
