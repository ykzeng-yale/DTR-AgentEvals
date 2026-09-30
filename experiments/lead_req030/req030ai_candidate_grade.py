"""Pure CPU replay of an assigned candidate's independently produced test log.

This is a prospective helper, not a historical regrade or an execution API. It
never loads a model, applies a patch, writes an evaluator/reference file, or
executes a task command. All assigned slots remain in the operational denominator.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from experiments.lead_req030 import req030ah_controls as controls

PARSER_SHA256 = "42f564edfee3c21751739bbf09d60cf3a3ecdc58ac5cf45717dc6b47a85d7459"
AH_CONTROLS_SHA256 = "1362dda297de0945d48304e7b13a55a8e6d7a71aec7fe886b1ea01a7b5deeff3"
TASK_REPOS = dict(zip(controls.TASK_IDS, (
    "django/django", "matplotlib/matplotlib", "psf/requests", "pydata/xarray",
    "pylint-dev/pylint", "pytest-dev/pytest", "scikit-learn/scikit-learn", "sphinx-doc/sphinx")))
BINDING_FIELDS = {"task_id", "repo", "base_commit", "policy_id", "invocation_id",
                  "release_sha256", "evaluator_bundle_sha256", "patch_sha256", "raw_sha256",
                  "supervisor_sha256", "parser_sha256"}
MAX_PATCH_BYTES = 4 * 1024 * 1024
MAX_EVALUATOR_BYTES = 16 * 1024 * 1024
KNOWN_OBSERVED = {"PASSED", "FAILED", "SKIPPED", "XFAIL"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def parse_unique(data: bytes) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate evaluator key")
            result[key] = value
        return result
    result = json.loads(data, object_pairs_hook=unique)
    if not isinstance(result, dict):
        raise ValueError("evaluator must be an object")
    return result


def replay_candidate(*, task: dict, evaluator_bundle: bytes, raw: bytes, supervisor: dict,
                     patch: bytes, expected_patch_sha256: str, expected_binding: dict,
                     observed_binding: dict) -> dict:
    """Grade only exact-bound artifacts; missing/invalid evidence is never success.

    The coordinator freezes task/policy/invocation/source identities before
    dispatch, then independently computes expected artifact hashes on retrieval.
    ``observed_binding`` belongs to that evaluator invocation. Artifact hashes
    alone cannot substitute for prospective task/policy/invocation equality.
    Return no evaluator source, reference patch, candidate text or raw log text.
    ``graded`` denotes a known strict endpoint; required SKIPPED/XFAIL imply a
    strict nonresolution, but algorithmic correctness remains unknown unless
    an actual required FAILED status is observed.
    """
    result = {"schema": "dtr.req030ai.candidate_grade.v1", "graded": False, "resolved": False,
              "algorithmic_correctness": "unknown", "operational_resolution": 0,
              "assigned_slot_retained": True, "denominator_unit": "one assigned task-policy invocation",
              "reason": "unverified_artifacts", "declared_statuses": {}, "undeclared_statuses": {},
              "parser_sha256": PARSER_SHA256, "ah_controls_sha256": AH_CONTROLS_SHA256,
              "task_id": task.get("instance_id") if isinstance(task, dict) else None,
              "policy_id": expected_binding.get("policy_id") if isinstance(expected_binding, dict) else None,
              "invocation_id": expected_binding.get("invocation_id") if isinstance(expected_binding, dict) else None}

    def reject(reason: str):
        result["reason"] = reason
        return result

    if not all(type(x) is bytes for x in (evaluator_bundle, raw, patch)) or not isinstance(supervisor, dict):
        return reject("invalid_artifact_types")
    result.update(raw_sha256=sha(raw), raw_bytes=len(raw), patch_sha256=sha(patch), patch_bytes=len(patch),
                  evaluator_bundle_sha256=sha(evaluator_bundle))
    try:
        result["supervisor_sha256"] = sha(canonical(supervisor))
    except (ValueError, TypeError):
        return reject("malformed_supervisor")
    if not patch or len(patch) > MAX_PATCH_BYTES:
        return reject("empty_or_oversized_patch")
    if not isinstance(expected_patch_sha256, str) or re.fullmatch(r"[0-9a-f]{64}", expected_patch_sha256) is None:
        return reject("invalid_expected_patch_identity")
    if result["patch_sha256"] != expected_patch_sha256:
        return reject("candidate_patch_identity_mismatch")
    if len(evaluator_bundle) > MAX_EVALUATOR_BYTES or len(raw) > controls.shared.MAX_EPISODE_OUTPUT:
        return reject("artifact_size_limit")
    if not isinstance(task, dict) or set(task) != {"instance_id", "repo", "base_commit", "evaluator_bundle_sha256"}:
        return reject("invalid_task_identity")
    if (TASK_REPOS.get(task["instance_id"]) != task["repo"]
            or not isinstance(task["base_commit"], str) or re.fullmatch(r"[0-9a-f]{40}", task["base_commit"]) is None
            or task["evaluator_bundle_sha256"] != result["evaluator_bundle_sha256"]):
        return reject("task_evaluator_identity_mismatch")
    if (not isinstance(expected_binding, dict) or not isinstance(observed_binding, dict)
            or set(expected_binding) != BINDING_FIELDS or set(observed_binding) != BINDING_FIELDS):
        return reject("invalid_invocation_binding_schema")
    if expected_binding != observed_binding:
        return reject("task_policy_invocation_binding_mismatch")
    for field in ("policy_id", "invocation_id"):
        if not isinstance(expected_binding[field], str) or re.fullmatch(r"[A-Za-z0-9_.:/-]{1,256}", expected_binding[field]) is None:
            return reject("invalid_policy_or_invocation_identity")
    if not isinstance(expected_binding["release_sha256"], str) or re.fullmatch(r"[0-9a-f]{64}", expected_binding["release_sha256"]) is None:
        return reject("invalid_release_identity")
    identity = {"task_id": task["instance_id"], "repo": task["repo"], "base_commit": task["base_commit"],
                "patch_sha256": result["patch_sha256"], "raw_sha256": result["raw_sha256"],
                "supervisor_sha256": result["supervisor_sha256"], "parser_sha256": PARSER_SHA256,
                "evaluator_bundle_sha256": result["evaluator_bundle_sha256"]}
    if any(expected_binding[key] != value for key, value in identity.items()):
        return reject("invocation_artifact_identity_mismatch")
    result["binding_sha256"] = sha(canonical(expected_binding))
    try:
        evaluation = parse_unique(evaluator_bundle)
        if any(evaluation.get(k) != task[k] for k in ("instance_id", "base_commit")):
            return reject("evaluator_task_identity_mismatch")
        if "repo" in evaluation and evaluation["repo"] != task["repo"]:
            return reject("evaluator_repository_identity_mismatch")
        f2p, p2p = evaluation["fail_to_pass"], evaluation["pass_to_pass"]
        if (not isinstance(f2p, list) or not isinstance(p2p, list) or not f2p or not p2p
                or any(not isinstance(x, str) or not x.strip() for x in f2p + p2p)
                or len(set(f2p + p2p)) != len(f2p + p2p)):
            return reject("invalid_declared_test_identities")
        if (controls.PARSER_SHA != PARSER_SHA256
                or sha(Path(controls.__file__).read_bytes()) != AH_CONTROLS_SHA256):
            return reject("grader_source_identity_mismatch")
        parsers = controls.pinned_parsers()
        # Reuse the complete pinned map, including real Django and Matplotlib
        # parsers. Reference mode supplies all-PASSED acceptance; no reference
        # content is read, returned, applied or executed here.
        assessed = controls.assess(raw, supervisor,
            {"fail_to_pass": f2p, "pass_to_pass": p2p}, "reference", parsers[task["repo"]])
    except (ValueError, TypeError, KeyError, OSError):
        return reject("invalid_evaluator_or_parser_evidence")
    result.update(declared_statuses=assessed["declared_statuses"],
                  undeclared_statuses=assessed["undeclared_statuses"],
                  valid_process=assessed["valid_process"], markers_valid=assessed["markers_valid"],
                  declared_check_count=len(f2p) + len(p2p), task_count=1)
    result["undeclared_error_count"] = sum(s == "ERROR" for s in result["undeclared_statuses"].values())
    result["undeclared_review_required"] = bool(result["undeclared_error_count"])
    if not assessed["valid_process"]:
        return reject("invalid_process_or_framing")
    statuses = result["declared_statuses"]
    if any(status == "MISSING" for status in statuses.values()):
        return reject("required_test_status_missing")
    if any(status not in KNOWN_OBSERVED for status in statuses.values()):
        return reject("test_error_or_unknown_status")
    resolved = all(status == "PASSED" for status in statuses.values())
    correctness = "resolved" if resolved else "unresolved" if "FAILED" in statuses.values() else "unknown"
    result.update(graded=True, resolved=resolved, algorithmic_correctness=correctness,
                  operational_resolution=int(resolved), reason="all_required_passed" if resolved else "observed_required_nonpass")
    return result
