"""Exact upstream score semantics on authored logs; no model/task execution."""
from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

import pytest

from experiments.lead_req030 import req030aj_official_grade as official
from experiments.lead_req030 import req030ai_candidate_grade as strict

BUNDLE = official.ROOT / "work/req030ah_controls_20260930_a"


def line(repo, node, status):
    if repo == "django/django":
        return node + " ... " + {"PASSED": "ok", "FAILED": "FAIL", "ERROR": "ERROR",
                                 "SKIPPED": "skipped 'authored fixture'"}[status]
    if repo == "matplotlib/matplotlib":
        node = node.replace("[1]", "[MouseButton.LEFT]").replace("[3]", "[MouseButton.RIGHT]")
    if repo in {"scikit-learn/scikit-learn", "sphinx-doc/sphinx"}:
        return node + " " + status
    return status + " " + node


def frame(lines):
    return ("DTR_TEST_START\n>>>>> Start Test Output\n" + "\n".join(lines)
            + "\n>>>>> End Test Output\nDTR_TEST_END\n").encode()


def args_for(tid="psf__requests-6028", *, status="PASSED", missing=False, fallback=False, patch=b"authored inert candidate"):
    original = official.frozen_tasks()[tid]
    evaluator = (BUNDLE / "evaluator" / (tid + ".json")).read_bytes()
    evaluation = strict.parse_unique(evaluator)
    required = evaluation["fail_to_pass"] + evaluation["pass_to_pass"]
    nodes = required[1:] if missing else required
    lines = [line(original["repo"], node, status) for node in nodes]
    raw = frame([]) + "\n".join(lines).encode() + b"\n" if fallback else frame(lines)
    supervisor = {"reason": "exited", "pid": 123, "returncode": 0, "retained_bytes": len(raw), "elapsed": .1, "error": None}
    task = {key: original[key] for key in ("instance_id", "repo", "base_commit", "evaluator_bundle_sha256")}
    binding = {"task_id": tid, "repo": task["repo"], "base_commit": task["base_commit"], "policy_id": "SL",
        "invocation_id": tid + ":SL:assigned-a", "release_sha256": "a" * 64,
        "evaluator_bundle_sha256": official.sha(evaluator), "patch_sha256": official.sha(patch or b""),
        "raw_sha256": official.sha(raw), "supervisor_sha256": official.sha(strict.canonical(supervisor)),
        "parser_sha256": strict.PARSER_SHA256}
    strict_grade = strict.replay_candidate(task=task, evaluator_bundle=evaluator, raw=raw, supervisor=supervisor,
        patch=patch or b"", expected_patch_sha256=binding["patch_sha256"], expected_binding=binding, observed_binding=binding)
    return dict(task=task, evaluator_bundle=evaluator, raw=raw, patch=patch,
                expected_binding=binding, observed_binding=copy.deepcopy(binding), strict_grade=strict_grade)


def rebound(args):
    changes = {"raw_sha256": official.sha(args["raw"]), "patch_sha256": official.sha(args["patch"] or b"")}
    args["expected_binding"].update(changes); args["observed_binding"].update(changes)
    args["strict_grade"] = None


@pytest.mark.parametrize("tid", strict.TASK_REPOS)
def test_full_pinned_upstream_report_all_eight_repositories(tid):
    args = args_for(tid)
    result = official.replay_official(**args)
    assert result["available"], result
    report = result["upstream_report_map"]
    assert set(report) == {tid}
    assert report[tid]["resolved"] and report[tid]["patch_successfully_applied"]
    assert report[tid]["patch_exists"] and not report[tid]["patch_is_None"]
    assert set(report[tid]["tests_status"]) == {"FAIL_TO_PASS", "PASS_TO_PASS", "FAIL_TO_FAIL", "PASS_TO_FAIL"}
    assert result["strict_endpoint"]["result"]["resolved"]
    assert result["official_docker_execution_verified"] is False
    assert result["raw_sha256"] == args["expected_binding"]["raw_sha256"]
    assert result["patch_sha256"] == args["expected_binding"]["patch_sha256"]
    assert result["source_pins"] == official.SOURCE_PINS
    assert not any(text in json.dumps(result) for text in ("reference_patch", "stock_eval_script", "authored inert candidate"))


def test_xfail_is_official_pass_while_strict_resolution_is_false():
    result = official.replay_official(**args_for(status="XFAIL"))
    assert result["available"] and result["upstream_report_map"]["psf__requests-6028"]["resolved"]
    assert result["strict_endpoint"]["result"]["resolved"] is False
    assert result["strict_endpoint"]["result"]["algorithmic_correctness"] == "unknown"


def test_missing_required_identity_is_official_failure_and_strict_unknown():
    args = args_for(missing=True)
    result = official.replay_official(**args)
    report = result["upstream_report_map"]["psf__requests-6028"]
    assert result["available"] and report["resolved"] is False
    evaluation = strict.parse_unique(args["evaluator_bundle"])
    assert report["tests_status"]["FAIL_TO_PASS"]["failure"] == evaluation["fail_to_pass"][:1]
    assert result["strict_endpoint"]["result"]["graded"] is False


def test_skipped_omission_and_zero_denominator_upstream_semantics_preserved():
    result = official.replay_official(**args_for(status="SKIPPED"))
    report = result["upstream_report_map"]["psf__requests-6028"]
    assert result["available"] and report["resolved"] is True
    assert all(value == {"success": [], "failure": []} for value in report["tests_status"].values())
    assert result["strict_endpoint"]["result"]["resolved"] is False
    assert result["strict_endpoint"]["result"]["algorithmic_correctness"] == "unknown"


def test_upstream_full_log_fallback_is_preserved_without_changing_strict_score():
    result = official.replay_official(**args_for(fallback=True))
    assert result["available"] and result["upstream_report_map"]["psf__requests-6028"]["resolved"]
    assert result["strict_endpoint"]["result"]["graded"] is False
    assert result["strict_endpoint"]["result"]["reason"] == "required_test_status_missing"


@pytest.mark.parametrize("bad_code", [">>>>> Patch Apply Failed", ">>>>> Reset Failed",
                                     ">>>>> Tests Errored", ">>>>> Tests Timed Out"])
def test_upstream_bad_code_rejection_is_unmodified(bad_code):
    args = args_for(); args["raw"] = bad_code.encode() + b"\n" + args["raw"]; rebound(args)
    result = official.replay_official(**args)
    report = result["upstream_report_map"]["psf__requests-6028"]
    assert result["available"] and not report["resolved"] and not report["patch_successfully_applied"]
    assert "tests_status" not in report


@pytest.mark.parametrize("patch,expected_none", [(None, True), (b"", False)])
def test_original_none_and_empty_prediction_semantics(patch, expected_none):
    result = official.replay_official(**args_for(patch=patch))
    assert result["available"]
    report = result["upstream_report_map"]["psf__requests-6028"]
    assert report["patch_is_None"] is expected_none
    assert report["patch_exists"] is not expected_none
    assert report["resolved"] is not expected_none
    assert result["strict_endpoint"]["result"]["graded"] is False


def test_duplicate_markers_upstream_first_split_behavior_is_retained():
    args = args_for(); args["raw"] += b">>>>> Start Test Output\n>>>>> End Test Output\n"; rebound(args)
    result = official.replay_official(**args)
    assert result["available"] and result["upstream_report_map"]["psf__requests-6028"]["resolved"]


def test_missing_test_markers_do_not_establish_patch_application():
    args = args_for(); args["raw"] = b"PASSED arbitrary\n"; rebound(args)
    result = official.replay_official(**args)
    assert result["available"]
    report = result["upstream_report_map"]["psf__requests-6028"]
    assert not report["resolved"] and not report["patch_successfully_applied"]


@pytest.mark.parametrize("field", sorted(strict.BINDING_FIELDS))
def test_every_binding_mismatch_is_rejected_before_scoring(field):
    args = args_for(); args["observed_binding"][field] = "mismatch"
    result = official.replay_official(**args)
    assert not result["available"] and result["upstream_report_map"] == {}


def test_strict_score_from_different_raw_artifact_is_not_joined():
    args = args_for(); args["strict_grade"]["raw_sha256"] = "0" * 64
    result = official.replay_official(**args)
    assert not result["available"] and result["reason"] == "strict_score_artifact_identity_mismatch"
    assert result["strict_endpoint"]["result"] is None


@pytest.mark.parametrize("source", official.SOURCE_PINS)
def test_every_upstream_and_version_source_is_byte_checked(source, monkeypatch):
    real = official.SOURCE_PINS[source]
    monkeypatch.setitem(official.SOURCE_PINS, source, "0" * 64)
    with pytest.raises(ValueError, match="source pin"):
        official._source(source)
    assert real != "0" * 64


def test_original_function_bodies_and_constant_enum_semantics_are_preserved():
    kernel = official.load_pinned_scoring()
    source = official._source(f"{official.UPSTREAM}/grading.py")
    source_tree = ast.parse(source)
    for function in (node for node in source_tree.body if isinstance(node, ast.FunctionDef)):
        loaded = kernel[function.name]
        assert loaded.__code__.co_filename == f"{official.UPSTREAM}/grading.py"
        assert loaded.__code__.co_firstlineno == function.lineno
    assert {value.value for value in kernel["TestStatus"]} == {"PASSED", "FAILED", "ERROR", "SKIPPED", "XFAIL"}
    assert kernel["test_passed"]("a", {"a": "XFAIL"}) is True
    assert kernel["test_failed"]("missing", {}) is True
    assert kernel["compute_fail_to_pass"]({"FAIL_TO_PASS": {"success": [], "failure": []}}) == 1
    report = kernel["get_eval_tests_report"]({}, {"FAIL_TO_PASS": ["absent"], "PASS_TO_PASS": ["also_absent"]},
                                               eval_type=kernel["EvalType"].FAIL_ONLY)
    assert report["FAIL_TO_PASS"]["success"] == ["absent"]
    assert report["PASS_TO_PASS"]["success"] == ["also_absent"]


def test_exact_pinned_repo_version_commands_and_no_docker_imports():
    import sys
    before = set(sys.modules)
    kernel = official.load_pinned_scoring()
    tasks = official.frozen_tasks()
    for tid, task in tasks.items():
        result = official.replay_official(**args_for(tid))
        command = kernel["MAP_REPO_VERSION_TO_SPECS"][task["repo"]][task["version"]]["test_cmd"]
        assert result["version"] == task["version"] and result["upstream_test_cmd"] == command
        assert result["upstream_test_cmd_sha256"] == official.sha(official.canonical(command))
    assert not any(name.startswith(("docker", "swebench", "torch")) for name in set(sys.modules) - before)
