"""REQ030AH input preparation: eight fixed tasks, offline export, no execution.

``fetch-registry`` separately acquires only small public OCI manifest/config
metadata. ``prepare`` is an offline, write-once exporter; it never calls AG's
build(), fetches layers, runs task scripts, or releases a model experiment.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import socket
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from experiments.lead_req030 import req030ag_bundle as ag

ROOT = ag.ROOT
SELECTION = tuple(zip(range(13, 21), (
    "django__django-12039", "matplotlib__matplotlib-26208", "psf__requests-6028",
    "pydata__xarray-6461", "pylint-dev__pylint-6386", "pytest-dev__pytest-10081",
    "scikit-learn__scikit-learn-25102", "sphinx-doc__sphinx-8593",
)))
AG_BUILDER_SHA256 = "6d4cf94b79071f4e4f6c111f5ff6c373ebc2ea2131375ba624e1636ba291d8cb"
METADATA_CAP = 4 * 1024 * 1024
ACCEPT = ", ".join(("application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
    "application/vnd.docker.distribution.manifest.v2+json"))
DEFAULT_OUTPUT = ROOT / "work/req030ah_controls_20260930_a"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return ag.canonical(value)


def image_repository(instance_id: str) -> str:
    if instance_id not in dict(SELECTION).values():
        raise ValueError("task outside frozen REQ030AH selection")
    return "swebench/sweb.eval.x86_64." + instance_id.replace("__", "_1776_")


def _get(url: str, headers: dict[str, str] | None = None) -> tuple[bytes, dict[str, str]]:
    with urlopen(Request(url, headers=headers or {}), timeout=30) as response:
        data = response.read(METADATA_CAP + 1)
        if len(data) > METADATA_CAP:
            raise ValueError("public registry metadata exceeds 4 MiB cap")
        return data, {k.lower(): v for k, v in response.headers.items()}


def _verified_digest(raw: bytes, expected: str | None) -> str:
    actual = "sha256:" + sha(raw)
    if expected != actual:
        raise ValueError("registry metadata digest mismatch")
    return actual


def fetch_registry_metadata(output: Path) -> dict[str, Any]:
    """Resolve public tags once; store no token and download no filesystem layer."""
    output = Path(output)
    if output.exists():
        raise FileExistsError(output)
    records = []
    for _, task_id in SELECTION:
        repo = image_repository(task_id)
        auth_url = "https://auth.docker.io/token?" + urlencode({
            "service": "registry.docker.io", "scope": f"repository:{repo}:pull"})
        token_raw, _ = _get(auth_url)
        token = json.loads(token_raw)["token"]
        headers = {"Authorization": "Bearer " + token, "Accept": ACCEPT}
        base = "https://registry-1.docker.io/v2/" + repo
        root_raw, root_headers = _get(base + "/manifests/latest", headers)
        root_digest = _verified_digest(root_raw, root_headers.get("docker-content-digest"))
        root = json.loads(root_raw)
        if "manifests" in root:
            choices = [m for m in root["manifests"] if m.get("platform", {}).get("os") == "linux"
                       and m.get("platform", {}).get("architecture") == "amd64"]
            if len(choices) != 1:
                raise ValueError(f"expected exactly one linux/amd64 leaf: {task_id}")
            leaf_raw, leaf_headers = _get(base + "/manifests/" + choices[0]["digest"], headers)
            leaf_digest = _verified_digest(leaf_raw, choices[0]["digest"])
            _verified_digest(leaf_raw, leaf_headers.get("docker-content-digest"))
        else:
            leaf_raw, leaf_digest = root_raw, root_digest
        leaf = json.loads(leaf_raw)
        config_digest = leaf["config"]["digest"]
        config_raw, _ = _get(base + "/blobs/" + config_digest, headers)
        _verified_digest(config_raw, config_digest)
        records.append({"instance_id": task_id, "repository": repo,
            "root_manifest_digest": root_digest, "root_manifest_utf8": root_raw.decode(),
            "leaf_manifest_digest": leaf_digest, "leaf_manifest_utf8": leaf_raw.decode(),
            "config_digest": config_digest, "config_utf8": config_raw.decode()})
    result = {"schema": "dtr.req030ah.oci_metadata.v1", "registry": "registry-1.docker.io",
        "acquisition": "anonymous public bearer authentication; manifests and config only; no layers",
        "tasks": records}
    validate_registry_metadata(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("xb") as file:
        file.write(canonical(result))
    output.chmod(0o600)
    return result


def validate_registry_metadata(metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
    records = metadata.get("tasks", [])
    if metadata.get("schema") != "dtr.req030ah.oci_metadata.v1" or metadata.get("registry") != "registry-1.docker.io":
        raise ValueError("unexpected registry metadata schema/origin")
    if [r["instance_id"] for r in records] != [t for _, t in SELECTION]:
        raise ValueError("registry task set/order differs from frozen ranks 13–20")
    result = {}
    for record in records:
        task_id = record["instance_id"]
        if record["repository"] != image_repository(task_id):
            raise ValueError("OCI repository/task identity mismatch")
        for name in ("root_manifest", "leaf_manifest", "config"):
            _verified_digest(record[name + "_utf8"].encode(), record[name + "_digest"])
        root = json.loads(record["root_manifest_utf8"])
        leaf = json.loads(record["leaf_manifest_utf8"])
        config = json.loads(record["config_utf8"])
        if config.get("architecture") != "amd64" or config.get("os") != "linux":
            raise ValueError("image config is not linux/amd64")
        if "manifests" in root:
            matches = [m for m in root["manifests"] if m.get("platform", {}).get("os") == "linux"
                       and m.get("platform", {}).get("architecture") == "amd64"]
            if len(matches) != 1 or matches[0]["digest"] != record["leaf_manifest_digest"]:
                raise ValueError("index does not uniquely bind AMD64 leaf")
        elif record["root_manifest_digest"] != record["leaf_manifest_digest"]:
            raise ValueError("single root manifest differs from leaf")
        if leaf.get("schemaVersion") != 2 or "manifests" in leaf:
            raise ValueError("not a schema-2 leaf manifest")
        if leaf["config"]["digest"] != record["config_digest"]:
            raise ValueError("leaf/config binding mismatch")
        if leaf["config"]["size"] != len(record["config_utf8"].encode()):
            raise ValueError("OCI config size mismatch")
        if not leaf.get("layers") or any(not isinstance(x.get("size"), int) or x["size"] <= 0 for x in leaf["layers"]):
            raise ValueError("missing/invalid OCI layer inventory")
        result[task_id] = {"image_ref": "docker.io/" + record["repository"] + "@" + record["leaf_manifest_digest"],
            "oci_amd64_leaf_digest": record["leaf_manifest_digest"],
            "oci_config_digest": record["config_digest"],
            "oci_compressed_layer_bytes": sum(x["size"] for x in leaf["layers"]),
            "oci_layer_count": len(leaf["layers"]), "architecture": "amd64", "os": "linux"}
    return result


def reserve_components(queue: dict[str, Any]) -> dict[str, list[str]]:
    if queue["queue"][12:20] != [t for _, t in SELECTION]:
        raise ValueError("REQ009 queue ranks changed")
    reserved = {}
    for _, task_id in SELECTION:
        component = queue["candidate_component"][task_id]
        members = sorted([task_id] + component["candidate_mates"])
        if len(members) != component["size"]:
            raise ValueError("component membership incomplete")
        reserved[component["component"]] = members
    return reserved


@contextmanager
def no_network():
    """The evaluator exporter must fail instead of obtaining new dependencies."""
    original = socket.socket.connect
    original_ex = socket.socket.connect_ex
    def denied(*_args, **_kwargs):
        raise RuntimeError("network is forbidden during offline bundle export")
    socket.socket.connect = denied
    socket.socket.connect_ex = denied
    try:
        yield
    finally:
        socket.socket.connect = original
        socket.socket.connect_ex = original_ex


def prepare(output: Path, registry_metadata: Path, *, dataset: Path = ag.DATASET,
            m01: Path = ag.M01, queue: Path = ag.QUEUE) -> dict[str, Any]:
    """Write immutable inputs only. The lead separately freezes the run manifest."""
    output, registry_metadata = Path(output), Path(registry_metadata)
    if output.exists():
        raise FileExistsError(output)
    inputs = ((Path(dataset), ag.DATASET_SHA256), (Path(m01), ag.M01_SHA256),
              (Path(queue), ag.QUEUE_SHA256), (Path(ag.__file__), AG_BUILDER_SHA256),
              (ag.PARSER_SOURCE, ag.PARSER_SHA256))
    for path, expected in inputs:
        if sha(path.read_bytes()) != expected:
            raise ValueError("pinned builder input mismatch: " + path.name)
    if importlib.metadata.version("pyarrow") != "19.0.1" or importlib.metadata.version("unidiff") != "0.7.5":
        raise ValueError("builder requires pyarrow 19.0.1 / unidiff 0.7.5")
    import pyarrow.parquet as pq
    registry_bytes = registry_metadata.read_bytes()
    images = validate_registry_metadata(json.loads(registry_bytes))
    queue_data = json.loads(Path(queue).read_bytes())
    reservations = reserve_components(queue_data)
    m01_rows = {r["instance_id"]: r for r in map(json.loads, Path(m01).read_text().splitlines())}
    rows = {r["instance_id"]: r for r in pq.read_table(dataset,
        filters=[("instance_id", "in", [t for _, t in SELECTION])]).to_pylist()}
    if set(rows) != {t for _, t in SELECTION}:
        raise ValueError("dataset selection is incomplete")
    files: dict[str, bytes] = {"registry_metadata.json": registry_bytes}
    tasks = []
    with no_network():
        make_test_spec = ag.load_pinned_make_test_spec()
        for rank, task_id in SELECTION:
            row, meta = rows[task_id], m01_rows[task_id]
            row_sha = sha(json.dumps(row, sort_keys=True, ensure_ascii=False).encode())
            if row_sha != meta["content_sha256"] or meta["qualification"] != "eligible" or not meta["content_unchanged_by_construction"]:
                raise ValueError("M01 content/eligibility mismatch: " + task_id)
            f2p = json.loads(row["FAIL_TO_PASS"])
            p2p = json.loads(row["PASS_TO_PASS"])
            if not f2p or not p2p or not all(isinstance(x, str) and x for x in f2p + p2p) or len(set(f2p + p2p)) != len(f2p + p2p):
                raise ValueError("invalid declared test identity sets: " + task_id)
            spec = make_test_spec(row, namespace="dtr-req030ah")
            script = spec.eval_script.encode()
            if sha(script) != meta["eval_script_sha256"] or (len(f2p), len(p2p)) != (meta["n_fail_to_pass"], meta["n_pass_to_pass"]):
                raise ValueError("stock evaluator differs from M01: " + task_id)
            public = {k: row[k] for k in ("instance_id", "repo", "base_commit", "problem_statement")}
            evaluator = {"instance_id": task_id, "base_commit": row["base_commit"],
                "fail_to_pass": f2p, "pass_to_pass": p2p, "reference_patch": row["patch"],
                "stock_eval_script": script.decode(), "stock_eval_script_sha256": sha(script),
                "reference_patch_sha256": sha(row["patch"].encode()),
                "test_patch_sha256": sha(row["test_patch"].encode()), "evaluator_commit": ag.EVALUATOR_COMMIT}
            pub_bytes, eval_bytes = canonical(public), canonical(evaluator)
            files[f"public/{task_id}.json"] = pub_bytes
            files[f"evaluator/{task_id}.json"] = eval_bytes
            tasks.append({"m01_rank": rank, "instance_id": task_id, "repo": row["repo"],
                "family": row["repo"], "version": row["version"], "base_commit": row["base_commit"],
                "m01_content_sha256": row_sha, "public_projection_sha256": sha(pub_bytes),
                "public_projection_bytes": len(pub_bytes), "evaluator_bundle_sha256": sha(eval_bytes),
                "evaluator_bundle_bytes": len(eval_bytes), "stock_eval_script_sha256": sha(script),
                "reference_patch_sha256": evaluator["reference_patch_sha256"],
                "test_patch_sha256": evaluator["test_patch_sha256"], "fail_to_pass_count": len(f2p),
                "pass_to_pass_count": len(p2p), "image_key": meta["instance_image_key"], **images[task_id]})
    if len({t["repo"] for t in tasks}) != 8:
        raise ValueError("cohort must span eight distinct repositories")
    result = {"request": "DTR-REQ-030AH", "schema": "dtr.req030ah.input_bundle.v1",
        "kind": "pre-outcome CPU-only complete-cohort evaluator qualification inputs; no model release",
        "selection_rule": "exact REQ009 ranks 13–20, no replacements, no retry of ranks 5–12",
        "dataset": {"source_revision": "c104f840cc67f8b6eec6f759ebc8b2693d585d4a", "sha256": ag.DATASET_SHA256},
        "m01_sha256": ag.M01_SHA256, "queue_sha256": ag.QUEUE_SHA256,
        "evaluator_commit": ag.EVALUATOR_COMMIT, "registry_metadata_sha256": sha(registry_bytes),
        "builder_versions": {"pyarrow": "19.0.1", "unidiff": "0.7.5"},
        "development_reserved_components": reservations, "tasks": tasks,
        "caveats": ["Static eligibility is not runtime qualification or model competence.",
            "Queue/exposure inventory is scoped project evidence, not universal nonexposure/pretraining cleanliness.",
            "Full component members are reserved DEVELOPMENT; no member may enter held confirmation.",
            "Public files contain only four allowed task fields; references/tests remain evaluator-only.",
            "All eight assigned tasks remain in denominator; control failure cannot select replacements.",
            "No task image layer or model asset is downloaded or executed by this exporter.",
            "This input receipt is not a complete source-pinned release or execution authorization."],
        "files": {name: {"sha256": sha(body), "bytes": len(body)} for name, body in sorted(files.items())}}
    files["input_manifest.json"] = canonical(result)
    output.mkdir(parents=True, mode=0o700)
    for name, body in files.items():
        path = output / name
        path.parent.mkdir(mode=0o700, exist_ok=True)
        with path.open("xb") as file:
            file.write(body)
        path.chmod(0o600)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser("fetch-registry")
    fetch.add_argument("--output", type=Path, required=True)
    export = sub.add_parser("prepare")
    export.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    export.add_argument("--registry-metadata", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "fetch-registry":
        value = fetch_registry_metadata(args.output)
        print(json.dumps({"metadata_sha256": sha(canonical(value)), "tasks": len(value["tasks"])}))
    else:
        value = prepare(args.output, args.registry_metadata)
        print(json.dumps({"input_manifest_sha256": sha(canonical(value)), "tasks": len(value["tasks"])}))
