"""Freeze the pre-outcome eight-family REQ030AG development-screen inputs.

This builder reads the pinned SWE-bench Verified test split locally. Public task
projections and evaluator-only payloads are written to the ignored ``work/``
tree; evaluator patches and stock test scripts never enter the model runner.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "work/benchmark_inputs/swebench_verified_c104f840/test-00000-of-00001.parquet"
M01 = ROOT / "results/v2_adapter/m01_c104f840_f7bbbb2/instances.jsonl"
M01_SHA256 = "cee2e8760d9a1f3389031c709fd854af7d7a662499bd152ddeb62491f38dec64"
QUEUE = ROOT / "results/v2_adapter/req009_component_queue.json"
QUEUE_SHA256 = "16d634965ee399a88f8b605778ed80dcaf2dc7b0bab4722d3fc0001a9bdfad07"
DATASET_SHA256 = "a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd"
SELECTION = [
    (5, "psf__requests-2931"),
    (6, "pydata__xarray-3151"),
    (7, "pylint-dev__pylint-8898"),
    (8, "pytest-dev__pytest-6202"),
    (9, "scikit-learn__scikit-learn-13328"),
    (10, "sphinx-doc__sphinx-8269"),
    (11, "sympy__sympy-19954"),
    (12, "astropy__astropy-14365"),
]
OCI_LEAF = {
    "psf__requests-2931": "852d3d1ddb3c859675e5bb7d9269cb27c1bf8a6e95965108ad8a38b3495fc1d0",
    "pydata__xarray-3151": "320eea88d5a1b8553e7bf3f51c705b2230936800bac59f9cc0acd920a5d44d6b",
    "pylint-dev__pylint-8898": "6a3950d518eac34eff08f89136006c94526afc1cdf2b34d1a4d8f598faa4eaea",
    "pytest-dev__pytest-6202": "46c4cba4147a424e386808760d3b96fb362388556b00e9257661ac294c52c62b",
    "scikit-learn__scikit-learn-13328": "bf8c3425ac315ced20986def6adcd580ce4536ded6247d80f99d4c4352c85dab",
    "sphinx-doc__sphinx-8269": "a1f5a3dcde6461a718cbb0140c383c05671dec90b570502cc02e746ff76fa320",
    "sympy__sympy-19954": "fd13cef829daf5da790c170634159f461382d51b71dea0cb304d7f55efafd5fe",
    "astropy__astropy-14365": "52047c9299800168ed38a1b98b518a62c32f407f8269362c9f381d93c4e69dfe",
}
SIF_PIN = {
    "psf__requests-2931": ("1aa1561909caee4e83dbbfa9983230f8c760d206e20ec1a0bd68edee1bc3e3dc", 972804096),
    "pydata__xarray-3151": ("588f52cea44e11a89bf7ec83ade23b40a66c38096102848d2bc71e3c831a25db", 2000973824),
    "pylint-dev__pylint-8898": ("2165e40baa3a09ddd95de3c8cb52508a7e78ce583d22db820b1d22e65d539ebd", 1001254912),
    "pytest-dev__pytest-6202": ("f0e8453ee3a035584fbff6b391c38bf255824f39141afe2bdc95e5d60f6480ef", 983150592),
    "scikit-learn__scikit-learn-13328": ("da7190637fff6c3e42103ff8318e28e6641bf3ccaec3712b1759c74aaf372022", 1436348416),
    "sphinx-doc__sphinx-8269": ("56f7c342ae52de726ca10fa8371414886af04b7281c120b164366188cf115e60", 1055059968),
    "sympy__sympy-19954": ("fe21628f25b0c356dce6b5e6a096f74088bedd69df3ef8db4322920f7409409f", 1045823488),
    "astropy__astropy-14365": ("7808291ee0cbd72913000090402624791c7094521f1d149220504f2dec536e03", 1096536064),
}
EVALUATOR_COMMIT = "f7bbbb2ccdf479001d6467c9e34af59e44a840f9"
OUTPUT = ROOT / "work/req030ag_screen_20260930_v10_final2"
OUTPUT = Path(os.environ.get("DTR_REQ030AG_BUNDLE_OUT", str(OUTPUT))).resolve()
PARSER_SOURCE = ROOT / "work/upstream/SWE-bench-f7bbbb2ccdf479001d6467c9e34af59e44a840f9/swebench/harness/log_parsers/python.py"
PARSER_SHA256 = "42f564edfee3c21751739bbf09d60cf3a3ecdc58ac5cf45717dc6b47a85d7459"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def load_pinned_make_test_spec():
    """Load the pinned evaluator script builder without CLI/network dependencies."""
    root = ROOT / "work/upstream/SWE-bench-f7bbbb2ccdf479001d6467c9e34af59e44a840f9/swebench"
    package_paths = {
        "swebench": root,
        "swebench.harness": root / "harness",
        "swebench.harness.test_spec": root / "harness/test_spec",
    }
    for name, path in package_paths.items():
        package = type(sys)(name)
        package.__path__ = [str(path)]
        sys.modules[name] = package
    if importlib.metadata.version("unidiff") != "0.7.5":
        raise ValueError("offline bundle builder requires pinned unidiff 0.7.5")
    from unidiff import PatchSet
    helper = type(sys)("swebench.harness.utils")
    def get_modified_files(patch: str) -> list[str]:
        files = [item.source_file[2:] for item in PatchSet(patch)
                 if item.source_file != "/dev/null" and item.source_file.startswith("a/")]
        return files
    def get_new_files(patch: str) -> list[str]:
        files = []
        for item in PatchSet(patch):
            if item.source_file == "/dev/null":
                target = item.target_file
                files.append(target[2:] if target.startswith("b/") else target)
        return files
    helper.get_modified_files = get_modified_files
    helper.get_new_files = get_new_files
    helper.load_cached_environment_yml = lambda _instance_id: None
    sys.modules["swebench.harness.utils"] = helper
    dockerfiles = type(sys)("swebench.harness.dockerfiles")
    dockerfiles.__path__ = []
    dockerfiles.get_dockerfile_base = lambda *_args, **_kwargs: ""
    dockerfiles.get_dockerfile_env = lambda *_args, **_kwargs: ""
    dockerfiles.get_dockerfile_instance = lambda *_args, **_kwargs: ""
    sys.modules["swebench.harness.dockerfiles"] = dockerfiles
    from swebench.harness.test_spec import create_scripts
    # Only eval_script is exported; environment construction is intentionally
    # suppressed so this frozen offline builder cannot fetch requirements.
    create_scripts.make_env_script_list = lambda *_args, **_kwargs: []
    from swebench.harness.test_spec.test_spec import make_test_spec
    return make_test_spec


def build() -> dict[str, Any]:
    if sha(M01.read_bytes()) != M01_SHA256:
        raise ValueError("M01 candidate source pin mismatch")
    if sha(QUEUE.read_bytes()) != QUEUE_SHA256:
        raise ValueError("REQ009 component queue source pin mismatch")
    if sha(DATASET.read_bytes()) != DATASET_SHA256:
        raise ValueError("SWE-bench Verified parquet pin mismatch")
    if sha(PARSER_SOURCE.read_bytes()) != PARSER_SHA256:
        raise ValueError("pinned SWE-bench Python parser source mismatch")
    fresh = not OUTPUT.exists()

    make_test_spec = load_pinned_make_test_spec()
    if importlib.metadata.version("pyarrow") != "19.0.1":
        raise ValueError("offline bundle builder requires pinned pyarrow 19.0.1")
    import pyarrow.parquet as pq

    columns = ["instance_id", "repo", "version", "base_commit", "problem_statement",
               "test_patch", "patch", "FAIL_TO_PASS", "PASS_TO_PASS"]
    table = pq.read_table(DATASET, columns=columns)
    rows = {r["instance_id"]: r for r in table.to_pylist()}
    m01_rows = [json.loads(line) for line in M01.read_text().splitlines() if line]
    m01_by_id = {row["instance_id"]: row for row in m01_rows}
    queue_data = json.loads(QUEUE.read_bytes())
    if queue_data.get("queue_sha256") != "d19efbc4b14eb249f7cbe69429b4a6e53e962bee77ff6736d05bb20eb000d4cc":
        raise ValueError("REQ009 queue ordered-list digest mismatch")
    queue_rank = {instance_id: rank for rank, instance_id in enumerate(queue_data["queue"], 1)}
    OUTPUT.mkdir(mode=0o700, parents=True, exist_ok=False)
    public_dir, evaluator_dir = OUTPUT / "public", OUTPUT / "evaluator"
    public_dir.mkdir(mode=0o700, exist_ok=True); evaluator_dir.mkdir(mode=0o700, exist_ok=True)
    manifest_tasks = []
    for rank, instance_id in SELECTION:
        if queue_rank.get(instance_id) != rank:
            raise ValueError(f"frozen REQ009 queue rank mismatch: {instance_id}")
        row = rows[instance_id]
        meta = m01_by_id[instance_id]
        if meta["qualification"] != "eligible" or meta["content_unchanged_by_construction"] is not True:
            raise ValueError(f"candidate is not source-bound eligible: {instance_id}")
        f2p = json.loads(row["FAIL_TO_PASS"]) if isinstance(row["FAIL_TO_PASS"], str) else row["FAIL_TO_PASS"]
        p2p = json.loads(row["PASS_TO_PASS"]) if isinstance(row["PASS_TO_PASS"], str) else row["PASS_TO_PASS"]
        if not f2p or not p2p:
            raise ValueError(f"candidate must have nonempty F2P and P2P: {instance_id}")
        if len(set(f2p + p2p)) != len(f2p) + len(p2p):
            raise ValueError(f"declared test IDs overlap: {instance_id}")
        if row["repo"].split("/")[0].replace("-", "_") not in instance_id.split("__")[0].replace("-", "_"):
            raise ValueError(f"repo/family mismatch: {instance_id}")
        spec = make_test_spec(row, namespace="dtr-req030ag")
        expected_image_key = meta["instance_image_key"]
        leaf = OCI_LEAF[instance_id]
        image_repo = "sweb.eval.x86_64." + instance_id.replace("__", "_1776_")
        image_ref = "docker.io/swebench/" + image_repo
        public = {"instance_id": instance_id, "repo": row["repo"], "base_commit": row["base_commit"],
                  "problem_statement": row["problem_statement"]}
        public_bytes = canonical(public)
        public_sha = sha(public_bytes)
        public_path = public_dir / f"{instance_id}.json"
        if fresh:
            public_path.write_bytes(public_bytes)
        elif public_path.read_bytes() != public_bytes:
            raise ValueError(f"existing public bundle changed: {instance_id}")

        test_script = (spec.eval_script.rstrip() + "\n").encode()
        reference = row["patch"].encode("utf-8")
        evaluator = {"instance_id": instance_id, "base_commit": row["base_commit"],
                     "fail_to_pass": f2p, "pass_to_pass": p2p,
                     "reference_patch": reference.decode("utf-8"),
                     "stock_eval_script": test_script.decode("utf-8"),
                     "stock_eval_script_sha256": sha(test_script),
                     "reference_patch_sha256": sha(reference),
                     "test_patch_sha256": sha(row["test_patch"].encode("utf-8")),
                     "evaluator_commit": EVALUATOR_COMMIT}
        evaluator_bytes = canonical(evaluator)
        evaluator_path = evaluator_dir / f"{instance_id}.json"
        if fresh:
            evaluator_path.write_bytes(evaluator_bytes)
        elif evaluator_path.read_bytes() != evaluator_bytes:
            raise ValueError(f"existing evaluator bundle changed: {instance_id}")
        manifest_tasks.append({
            "m01_rank": rank, "instance_id": instance_id, "repo": row["repo"],
            "family": row["repo"].split("/")[0], "version": row["version"],
            "base_commit": row["base_commit"], "m01_content_sha256": meta["content_sha256"],
            "public_projection_sha256": public_sha, "public_projection_bytes": len(public_bytes),
            "evaluator_bundle_sha256": sha(evaluator_bytes), "evaluator_bundle_bytes": len(evaluator_bytes),
            "reference_patch_sha256": sha(reference), "test_patch_sha256": sha(row["test_patch"].encode()),
            "stock_eval_script_sha256": sha(test_script), "fail_to_pass_count": len(f2p),
            "pass_to_pass_count": len(p2p), "image_key": expected_image_key,
            "oci_amd64_leaf_digest": "sha256:" + leaf, "image_ref": image_ref + "@sha256:" + leaf,
            "architecture": "amd64",
            "sif_sha256": SIF_PIN[instance_id][0], "sif_bytes": SIF_PIN[instance_id][1],
        })
    if len({t["family"] for t in manifest_tasks}) != len(SELECTION):
        raise ValueError("development tasks are not one-per-repository family")
    manifest = {
        "request": "DTR-REQ-030AG",
        "release_id": "req030ag-development-20260930-v10",
        "kind": "pre-outcome multi-issue DEVELOPMENT model-pair competence screen",
        "selection_source": "docs/req009_component_queue.md ranks 5-12; M01 source-bound eligible cohort",
        "selection_rule": "exact queue ranks 5-12, one issue per repo family; no substitution or same-task rerun",
        "dataset": {"sha256": DATASET_SHA256, "rows": 500,
                    "source_revision": "c104f840cc67f8b6eec6f759ebc8b2693d585d4a"},
        "bundle_builder": {"pyarrow": "19.0.1", "unidiff": "0.7.5",
                           "purpose": "offline deterministic Parquet/test-script export only; not treatment runtime"},
        "m01": {"path": "results/v2_adapter/m01_c104f840_f7bbbb2/instances.jsonl", "sha256": M01_SHA256},
        "evaluator": {"commit": EVALUATOR_COMMIT, "rule": "all declared F2P and P2P statuses must be exactly PASSED"},
        "models": json.loads((ROOT / "configs/req030ag_model_assets_20260929.json").read_text()),
        "runtime": json.loads((ROOT / "configs/req030ag_development_screen_20260930_v10.json").read_text())["runtime"],
        "source_pins": {},
        "tasks": manifest_tasks,
        "treatment": {
            "runtime": "PyTorch 2.9.1 + Transformers 4.51.3 + CUDA 12.8 on NVIDIA RTX PRO 6000 Blackwell",
            "dtype": "bfloat16", "decoding": {"do_sample": False, "temperature": 0,
                "context_tokens": 16384, "max_new_tokens": 1536},
            "agent": "SWE-agent mini-swe-agent 04d809ceab9df28f9adaed044884180159172930 DefaultAgent",
            "prompt": "req030ag-neutral-action-v1", "logical_call_limit": 24,
            "action_parser": "pinned mswea_bash_command regex; one command per response",
            "task_attempts": 1, "model_attempts": 1,
        },
        "execution": {"per_model_per_task": 1, "task_count": len(manifest_tasks),
                      "planned_model_episodes": 2 * len(manifest_tasks),
                      "order": "Sort task IDs by SHA256('DTR-REQ030AG-balanced-order-v1'||instance_id); first four receive 7B first and last four 14B first; both models exactly once per task",
                      "per_episode_wall_seconds": 2700, "max_steps": 24,
                      "control_gate": "run baseline and reference once for all 8 tasks; any invalid control or image/base mismatch aborts before loading model weights"},
        "endpoint": {"unit": "task-episode", "resolved": "nonempty git patch and every declared F2P/P2P status exactly PASSED",
                     "operational_outcomes": "all assigned episodes retained; setup/capacity/infrastructure failures are unknown, not model zeros",
                     "candidate_feasibility_gate": "provisional 15-85% terminal resolution in at least one model arm; design feasibility gate only, not task exclusion or confirmatory inference",
                     "interpretation": "DEV screening only; eight tasks are one per family, not a representative population sample or H/P causal contrast"},
        "resource_cap": {"slurm_account": "pi_gt353", "partition": "gpu_rtx6000",
                         "gpu": "rtx_pro_6000_blackwell:1", "gpu_model": "NVIDIA RTX PRO 6000 Blackwell",
                         "cpus": 8, "memory_gib": 128, "wall_hours": 36,
                         "asset_storage_gib_cap": 200, "individual_file_cap_gib": 80},
        "security": {"network": "none in task container", "host_mounts": "none except one explicit ext3 /testbed workspace",
                     "reference_and_test_inputs": "evaluator-only; never accepted by model API",
                     "task_code": "executes only within pinned Apptainer task image"},
        "image_reuse": {"source_release": "req030ag-development-20260930-v5 job 27928205",
                        "policy": "reuse exact SIF bytes acquired from each digest-pinned OCI reference; verify size and SHA-256 before inspection",
                        "task_images_are_read_only": True},
        "scope_hold": ["not CONFIRM", "not full benchmark", "not router comparison", "no prompt/budget tuning", "no task substitution"],
    }
    source_paths = [
        "experiments/lead_req030/req030ag_bundle.py", "experiments/lead_req030/req030ag_screen.py",
        "experiments/lead_req030/req030ag_development_screen.sbatch",
        "experiments/lead_req030/req030ag_image_git_diagnostic_replay.py",
        "experiments/lead_req030/test_req030ag_screen.py",
        "experiments/lead_req030/test_req030ag_bounded_supervisor.py",
        "experiments/lead_req030/req030ag_bounded_supervisor.py",
        "experiments/lead_req030/req030ag_seaborn_apptainer_runner.py",
        "experiments/lead_req030/bounded_supervisor.py", "experiments/lead_req030/seaborn_apptainer_runner.py",
        "experiments/lead_req030/native_hf_text_adapter.py", "experiments/lead_req030/seaborn_public_input.py",
        "experiments/lead_req030/seaborn_runner_qualification.py",
        "experiments/lead_req030/coder_c_wheels.json",
        "docs/source_snapshots/req030p_seaborn_public/public_task.json",
        "docs/source_snapshots/req030t_miniswe_agent/default.yaml",
        "docs/source_snapshots/req030t_miniswe_agent/LICENSE.md",
        "configs/req030ag_development_screen_20260930_v10.json",
        "configs/req030ag_model_assets_20260929.json",
        "configs/req030ag_prompt_20260929.json",
        "docs/req030ag_development_screen_20260929.md",
        "docs/req030ag_runroot_bootstrap_correction_20260930.md",
        "docs/req030ag_v5_terminal_diagnosis_20260930.md",
        "docs/req030ag_v6_image_gate_correction_20260930.md",
        "docs/req030ag_v7_rtx6000_route_20260930.md",
        "docs/req030ag_v8_payload_root_correction_20260930.md",
        "docs/req030ag_v9_gpu_name_alias_20260930.md",
        "docs/req030ag_v9_terminal_diagnosis_20260930.md",
        "docs/req030ag_v10_supervisor_output_correction_20260930.md",
        "work/upstream/SWE-bench-f7bbbb2ccdf479001d6467c9e34af59e44a840f9/swebench/harness/log_parsers/python.py",
        "work/upstream/mini-swe-agent-04d809ceab9df28f9adaed044884180159172930/src/minisweagent/agents/default.py",
        "work/upstream/mini-swe-agent-04d809ceab9df28f9adaed044884180159172930/src/minisweagent/models/utils/actions_text.py",
        "work/upstream/mini-swe-agent-04d809ceab9df28f9adaed044884180159172930/src/minisweagent/exceptions.py",
        "work/upstream/mini-swe-agent-04d809ceab9df28f9adaed044884180159172930/src/minisweagent/models/utils/openai_multimodal.py",
        "work/upstream/mini-swe-agent-04d809ceab9df28f9adaed044884180159172930/src/minisweagent/utils/serialize.py",
        "work/upstream/SWE-bench-f7bbbb2ccdf479001d6467c9e34af59e44a840f9/swebench/harness/constants/__init__.py",
        "work/upstream/SWE-bench-f7bbbb2ccdf479001d6467c9e34af59e44a840f9/swebench/harness/test_spec/test_spec.py",
        "work/upstream/SWE-bench-f7bbbb2ccdf479001d6467c9e34af59e44a840f9/swebench/harness/test_spec/create_scripts.py",
        "work/upstream/SWE-bench-f7bbbb2ccdf479001d6467c9e34af59e44a840f9/swebench/harness/test_spec/python.py",
        "work/upstream/SWE-bench-f7bbbb2ccdf479001d6467c9e34af59e44a840f9/swebench/harness/test_spec/utils.py",
        "work/upstream/SWE-bench-f7bbbb2ccdf479001d6467c9e34af59e44a840f9/swebench/harness/test_spec/javascript.py",
        "work/upstream/SWE-bench-f7bbbb2ccdf479001d6467c9e34af59e44a840f9/swebench/harness/utils.py",
    ]
    manifest["source_pins"] = {rel: sha((ROOT / rel).read_bytes()) for rel in source_paths}
    manifest["source_pins"]["experiments/lead_req030/req030ag_bundle.py"] = sha(Path(__file__).read_bytes())
    manifest_bytes = canonical(manifest)
    manifest_path = OUTPUT / "manifest.json"
    if fresh:
        manifest_path.write_bytes(manifest_bytes)
    elif manifest_path.exists() and manifest_path.read_bytes() != manifest_bytes:
        raise ValueError("existing bundle manifest differs from regenerated source")
    elif not manifest_path.exists():
        manifest_path.write_bytes(manifest_bytes)
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
