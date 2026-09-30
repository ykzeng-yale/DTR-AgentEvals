"""Full worker runtime binding without importing CUDA in the test process."""
import importlib.metadata
import platform

import pytest

from experiments.lead_req030 import req030ai_episode_worker as worker


def contract():
    return {"python": "3.12.3", "versions": {p: "1.0" for p in worker.RUNTIME_PACKAGES}}


def test_complete_package_and_python_binding(monkeypatch):
    monkeypatch.setattr(platform, "python_version", lambda: "3.12.3")
    seen = []
    def version(package):
        seen.append(package)
        return "1.0+cu128" if package == "torch" else "1.0"
    monkeypatch.setattr(importlib.metadata, "version", version)
    receipt = worker.verify_declared_worker_runtime(contract())
    assert receipt["versions"] == contract()["versions"]
    assert set(seen) == {p.replace("_", "-") for p in worker.RUNTIME_PACKAGES}


@pytest.mark.parametrize("package", sorted(worker.RUNTIME_PACKAGES))
def test_any_mismatched_dependency_rejects_before_load(monkeypatch, package):
    monkeypatch.setattr(platform, "python_version", lambda: "3.12.3")
    monkeypatch.setattr(importlib.metadata, "version", lambda p: "2.0" if p == package.replace("_", "-") else "1.0")
    with pytest.raises(ValueError, match="package version mismatch"):
        worker.verify_declared_worker_runtime(contract())


@pytest.mark.parametrize("change", ["missing", "extra", "python"])
def test_incomplete_or_changed_treatment_rejected(monkeypatch, change):
    monkeypatch.setattr(platform, "python_version", lambda: "3.12.3")
    c = contract()
    if change == "missing":
        c["versions"].pop("numpy")
    elif change == "extra":
        c["versions"]["unreleased"] = "1.0"
    else:
        c["python"] = "3.12.4"
    with pytest.raises(ValueError, match="runtime contract"):
        worker.verify_declared_worker_runtime(c)
