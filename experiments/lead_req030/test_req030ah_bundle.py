"""Deterministic adversarial checks; no network or benchmark execution."""
import copy
import json
import socket

import pytest

from experiments.lead_req030 import req030ah_bundle as bundle


def metadata_fixture():
    records = []
    for _, task_id in bundle.SELECTION:
        config = bundle.canonical({"architecture": "amd64", "os": "linux"}).decode()
        config_digest = "sha256:" + bundle.sha(config.encode())
        leaf = bundle.canonical({"schemaVersion": 2,
            "config": {"digest": config_digest, "size": len(config.encode())},
            "layers": [{"digest": "sha256:" + "a" * 64, "size": 100}]}).decode()
        digest = "sha256:" + bundle.sha(leaf.encode())
        records.append({"instance_id": task_id, "repository": bundle.image_repository(task_id),
            "root_manifest_digest": digest, "root_manifest_utf8": leaf,
            "leaf_manifest_digest": digest, "leaf_manifest_utf8": leaf,
            "config_digest": config_digest, "config_utf8": config})
    return {"schema": "dtr.req030ah.oci_metadata.v1", "registry": "registry-1.docker.io", "tasks": records}


def test_exact_selected_amd64_metadata_and_byte_pin_required():
    source = metadata_fixture()
    result = bundle.validate_registry_metadata(source)
    assert list(result) == [t for _, t in bundle.SELECTION]
    assert all(t["oci_compressed_layer_bytes"] == 100 for t in result.values())
    mutated = copy.deepcopy(source)
    mutated["tasks"][0]["config_utf8"] += " "
    with pytest.raises(ValueError, match="digest"):
        bundle.validate_registry_metadata(mutated)


@pytest.mark.parametrize("mutation", ["drop", "duplicate", "reorder", "repo"])
def test_no_implicit_task_replacement_or_repository_misbinding(mutation):
    source = metadata_fixture()
    if mutation == "drop":
        source["tasks"].pop()
    elif mutation == "duplicate":
        source["tasks"][-1] = source["tasks"][0]
    elif mutation == "reorder":
        source["tasks"].reverse()
    else:
        source["tasks"][0]["repository"] += "_other"
    with pytest.raises(ValueError):
        bundle.validate_registry_metadata(source)


def test_architecture_rejected_even_when_bytes_rehashed():
    source = metadata_fixture()
    record = source["tasks"][0]
    config = bundle.canonical({"architecture": "arm64", "os": "linux"}).decode()
    record["config_utf8"] = config
    record["config_digest"] = "sha256:" + bundle.sha(config.encode())
    leaf = json.loads(record["leaf_manifest_utf8"])
    leaf["config"] = {"digest": record["config_digest"], "size": len(config.encode())}
    for prefix in ("root_manifest", "leaf_manifest"):
        record[prefix + "_utf8"] = bundle.canonical(leaf).decode()
        record[prefix + "_digest"] = "sha256:" + bundle.sha(record[prefix + "_utf8"].encode())
    with pytest.raises(ValueError, match="linux/amd64"):
        bundle.validate_registry_metadata(source)


def test_index_must_uniquely_bind_leaf():
    source = metadata_fixture()
    record = source["tasks"][0]
    index = {"manifests": [{"digest": "sha256:" + "b" * 64,
                            "platform": {"os": "linux", "architecture": "amd64"}}]}
    record["root_manifest_utf8"] = bundle.canonical(index).decode()
    record["root_manifest_digest"] = "sha256:" + bundle.sha(record["root_manifest_utf8"].encode())
    with pytest.raises(ValueError, match="uniquely bind"):
        bundle.validate_registry_metadata(source)


def test_reserved_development_components_include_all_mates():
    queue = json.loads(bundle.ag.QUEUE.read_bytes())
    reserved = bundle.reserve_components(queue)
    assert reserved["pydata__xarray-4687"] == ["pydata__xarray-4687", "pydata__xarray-6461", "pydata__xarray-7229"]
    assert reserved["sphinx-doc__sphinx-8035"] == ["sphinx-doc__sphinx-8035", "sphinx-doc__sphinx-8593"]
    assert len({member for members in reserved.values() for member in members}) == 11
    queue["queue"][12] = queue["queue"][4]
    with pytest.raises(ValueError, match="ranks changed"):
        bundle.reserve_components(queue)


def test_exporter_network_guard_and_write_once(tmp_path):
    original = socket.socket.connect
    with bundle.no_network():
        with socket.socket() as sock:
            with pytest.raises(RuntimeError, match="forbidden"):
                sock.connect(("127.0.0.1", 9))
    assert socket.socket.connect is original
    with pytest.raises(FileExistsError):
        bundle.prepare(tmp_path, tmp_path / "absent-registry.json")


def test_fetch_uses_only_public_metadata_and_does_not_persist_bearer(tmp_path, monkeypatch):
    fixture = metadata_fixture()
    records = {r["repository"]: r for r in fixture["tasks"]}
    urls = []
    def fake_get(url, headers=None):
        urls.append(url)
        if url.startswith("https://auth.docker.io/token?"):
            return b'{"token":"TEMPORARY_BEARER_MUST_NOT_PERSIST"}', {}
        prefix = "https://registry-1.docker.io/v2/"
        assert url.startswith(prefix)
        suffix = url[len(prefix):]
        for repository, record in records.items():
            if suffix == repository + "/manifests/latest":
                return record["leaf_manifest_utf8"].encode(), {"docker-content-digest": record["leaf_manifest_digest"]}
            if suffix == repository + "/blobs/" + record["config_digest"]:
                return record["config_utf8"].encode(), {}
        raise AssertionError("unexpected or layer fetch: " + url)
    monkeypatch.setattr(bundle, "_get", fake_get)
    output = tmp_path / "registry.json"
    bundle.fetch_registry_metadata(output)
    assert len(urls) == 24
    assert b"TEMPORARY_BEARER" not in output.read_bytes()
    with pytest.raises(FileExistsError):
        bundle.fetch_registry_metadata(output)
