"""Setup-only supersession and unchanged whole-cohort scientific semantics."""
import ast
import copy
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from experiments.lead_req030 import req030ah_controls as old
from experiments.lead_req030 import req030ak_controls as new


def fixture_release(tmp_path):
    source = old.ROOT / "work/req030ah_controls_20260930_a"
    assert source.is_dir(), "frozen private bundle must be installed for release verification"
    bundle = tmp_path / "bundle"
    shutil.copytree(source, bundle)
    evidence = {"actual_job_id": "27950747", "actual_state": "FAILED",
        "cohort_status": "COHORT_REJECTED_OR_UNKNOWN", "model_calls": 0,
        "models_loaded": False, "controls_attempted": 0, "usable_sif_count": 0,
        "task_count": 8, "control_count": 16}
    prior = bundle / "prior_terminal.json"
    prior.write_bytes(new.shared.canonical(evidence))
    rels = [new.PARSER_REL, "experiments/lead_req030/req030ak_controls.py",
        "experiments/lead_req030/req030aj_acquisition.py",
        "experiments/lead_req030/req030ag_screen.py",
        "experiments/lead_req030/req030ag_bounded_supervisor.py",
        "experiments/lead_req030/bounded_supervisor.py"]
    doc = json.loads((bundle / "input_manifest.json").read_bytes())
    doc.update(request=new.REQUEST, release_id=new.RELEASE_ID, limits=new.LIMITS,
        model_execution_authorized=False,
        source_pins={r: new.shared.sha_file(new.ROOT/r) for r in rels},
        acquisition_correction={"prior_job_id": "27950747",
            "prior_release_sha256": "77d7b1b33f221e829aa67f9ce59f928cbbdf0b1453d6661399142827de6e1384",
            "prior_terminal_receipt": {"path": prior.name, "sha256": new.shared.sha_file(prior)},
            "change": "build temporary filesystem only: project NFS to verified allocation-local ext4/xfs"})
    path = bundle / "fixture_release.json"
    def load(value):
        path.write_bytes(new.shared.canonical(value))
        return new.load_release(bundle, path, new.shared.sha_file(path))
    return doc, evidence, prior, load


def test_fixed_controls_and_framing_are_identical():
    def body(module, name):
        return ast.dump(next(n for n in ast.parse(Path(module.__file__).read_text()).body
            if isinstance(n, ast.FunctionDef) and n.name == name), include_attributes=False)
    for name in ("assess", "execute_arm", "pinned_parsers", "finalize_interrupted"):
        assert body(old, name) == body(new, name)
    assert new.TASK_IDS == old.TASK_IDS and new.LIMITS == old.LIMITS
    assert new.PARSER_SHA == old.PARSER_SHA


def test_setup_only_supersession_is_complete_and_bound(tmp_path):
    doc, _, _, load = fixture_release(tmp_path)
    assert load(doc)["tasks"] == doc["tasks"]
    changed = copy.deepcopy(doc)
    changed["tasks"].reverse()
    with pytest.raises(ValueError, match="frozen queue"):
        load(changed)
    changed = copy.deepcopy(doc)
    changed.pop("acquisition_correction")
    with pytest.raises(ValueError, match="supersession"):
        load(changed)


@pytest.mark.parametrize("field,value", [("actual_state", "RUNNING"), ("model_calls", 1),
    ("models_loaded", True), ("controls_attempted", 1), ("usable_sif_count", 1),
    ("task_count", 7), ("control_count", 15), ("model_calls", False),
    ("controls_attempted", False), ("usable_sif_count", False)])
def test_any_exposure_live_owner_or_salvage_invalidates_correction(tmp_path, field, value):
    doc, evidence, prior, load = fixture_release(tmp_path)
    evidence[field] = value
    prior.write_bytes(new.shared.canonical(evidence))
    doc["acquisition_correction"]["prior_terminal_receipt"]["sha256"] = new.shared.sha_file(prior)
    with pytest.raises(ValueError, match="terminal and unexposed"):
        load(doc)


def test_spawn_failure_cleans_only_owned_local_tree(tmp_path, monkeypatch):
    class Context:
        private_dir = tmp_path / "local"
        tmp_dir = private_dir / "tmp"
        receipt = {"fixture": True}
        _cleaned = False
        def __enter__(self):
            self.tmp_dir.mkdir(parents=True)
            return self
        def __exit__(self, *args):
            shutil.rmtree(self.private_dir)
            self._cleaned = True
    context = Context()
    monkeypatch.setenv("SLURM_JOB_ID", "1")
    monkeypatch.setattr(new.acquisition, "prepare_acquisition", lambda **kwargs: context)
    monkeypatch.setattr(new.subprocess, "Popen", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("fixture spawn failure")))
    peer = tmp_path / "peer"
    peer.write_text("preserve")
    with pytest.raises(OSError, match="spawn failure"):
        new.supervise_local_worker(SimpleNamespace(output=str(tmp_path / "results")))
    assert context._cleaned and not context.private_dir.exists() and peer.read_text() == "preserve"
    assert json.loads((tmp_path / "local_temp_cleanup.json").read_bytes())["verified"] is True
