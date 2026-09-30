"""Deterministic tests of the full CPU cohort, not benchmark outcomes."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments.lead_req030 import req030ah_controls as ctl


class ControlQualificationTests(unittest.TestCase):
    def frame(self, body):
        return ("DTR_TEST_START\n>>>>> Start Test Output\n" + body +
                "\n>>>>> End Test Output\nDTR_TEST_END\n").encode()

    def check(self, body, mode="baseline", repo="psf/requests", evaluation=None):
        raw = self.frame(body)
        receipt = {"reason": "exited", "pid": 123, "elapsed": 0.1, "returncode": 0, "retained_bytes": len(raw), "error": None}
        return ctl.assess(raw, receipt, evaluation or {"fail_to_pass": ["a"], "pass_to_pass": ["b"]},
                          mode, ctl.pinned_parsers()[repo])

    def test_official_parsers_baseline_reference_and_missing_mutations(self):
        for repo in ("matplotlib/matplotlib", "psf/requests", "pydata/xarray", "pylint-dev/pylint",
                     "pytest-dev/pytest", "scikit-learn/scikit-learn", "sphinx-doc/sphinx"):
            with self.subTest(repo=repo):
                self.assertTrue(self.check("FAILED a\nPASSED b", repo=repo)["accepted"])
                self.assertTrue(self.check("PASSED a\nPASSED b", "reference", repo)["accepted"])
                for mode, lines in (("baseline", ["FAILED a", "PASSED b"]),
                                    ("reference", ["PASSED a", "PASSED b"])):
                    for missing in range(2):
                        self.assertFalse(self.check(lines[1-missing], mode, repo)["accepted"])
                self.assertFalse(self.check("FAILED a\nERROR b", repo=repo)["accepted"])
        ev = {"fail_to_pass": ["test_a (tests.Case)"], "pass_to_pass": ["test_b (tests.Case)"]}
        self.assertTrue(self.check("test_a (tests.Case) ... FAIL\ntest_b (tests.Case) ... ok",
                                   repo="django/django", evaluation=ev)["accepted"])
        self.assertTrue(self.check("test_a (tests.Case) ... ok\ntest_b (tests.Case) ... ok",
                                   "reference", "django/django", ev)["accepted"])

    def test_marker_and_supervisor_errors_rejected(self):
        raw = self.frame("FAILED a\nPASSED b")
        ev = {"fail_to_pass": ["a"], "pass_to_pass": ["b"]}
        parse = ctl.pinned_parsers()["psf/requests"]
        base = {"reason":"exited", "pid":123, "elapsed":0.1, "error":None, "returncode":0, "retained_bytes":len(raw)}
        self.assertTrue(ctl.assess(raw, base, ev, "baseline", parse)["accepted"])
        for extra in (b"DTR_TEST_START\n", b"DTR_SETUP_FAILURE\n"):
            b = raw + extra
            self.assertFalse(ctl.assess(b, {**base, "retained_bytes":len(b)}, ev, "baseline", parse)["accepted"])
        for changed in ({"reason":"timeout"}, {"error":"receipt failure"}, {"retained_bytes":1}, {"returncode":2},
                        {"returncode":True}, {"elapsed":float("nan")}, {"elapsed":float("inf")}, {"unknown":1}):
            receipt = {**base, **changed}
            self.assertFalse(ctl.assess(raw, receipt, ev, "baseline", parse)["accepted"])
        for missing in base:
            self.assertFalse(ctl.assess(raw, {k:v for k,v in base.items() if k != missing}, ev, "baseline", parse)["accepted"])

    def test_early_setup_exit_preserves_all_assigned_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "results"
            with patch.object(ctl.shutil, "which", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "Apptainer absent"):
                    ctl.execute({"tasks":[]}, Path(tmp), output, "a"*64)
            ctl.finalize_interrupted(output, "fixture setup failure")
            summary = json.loads((output / "summary.json").read_bytes())
            self.assertEqual(summary["status"], "INTERRUPTED_UNKNOWN")
            self.assertEqual(len(summary["controls"]), 16)
            self.assertTrue(all(x["status"] == "NOT_ATTEMPTED" and not x["accepted"] for x in summary["controls"]))

    def test_whole_cohort_continues_after_rejection_and_never_loads_models(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp); bundle = p / "bundle"; (bundle / "evaluator").mkdir(parents=True)
            tasks = [{"instance_id":tid,"repo":"psf/requests","base_commit":"a"*40,
                      "image_ref":"docker.io/swebench/task@sha256:"+"b"*64,
                      "oci_amd64_leaf_digest":"sha256:"+"b"*64} for tid in ctl.TASK_IDS]
            for task in tasks:
                (bundle / "evaluator" / (task["instance_id"]+".json")).write_text("{}")
            def fake_run(argv, **kw):
                if "pull" in argv:
                    Path(argv[argv.index("pull")+1]).write_bytes(b"image")
            def export(image, archive, _):
                archive.write_bytes(b"source"); return {"archive_sha256":"x"}
            calls=[]
            def arm(task, *args):
                mode = args[4].name
                calls.append((task["instance_id"],mode))
                return {"accepted":task["instance_id"] != ctl.TASK_IDS[0], "mode":mode}
            with patch.object(ctl.shutil,"which",return_value="/fixed/apptainer"), \
                 patch.object(ctl.subprocess,"check_output",return_value=b"apptainer fixture"), \
                 patch.object(ctl.subprocess,"run",side_effect=fake_run), \
                 patch.object(ctl.shared,"require_disk_floor",return_value={}), \
                 patch.object(ctl.shared,"_tree_for_task",return_value={"head":"a"*40,"tree":"c"*40,"expected_base_tree":"c"*40}), \
                 patch.object(ctl.shared,"export_task_tree",side_effect=export), \
                 patch.object(ctl,"execute_arm",side_effect=arm), \
                 patch.object(ctl.shared,"download_model_assets",side_effect=AssertionError("model path forbidden")), \
                 patch.object(ctl.shared,"_load_models",side_effect=AssertionError("model path forbidden")):
                result=ctl.execute({"tasks":tasks},bundle,p/"run"/"results","d"*64)
            self.assertEqual(len(calls),16)
            self.assertEqual(len(result["controls"]),16)
            self.assertEqual(result["status"],"COHORT_REJECTED_OR_UNKNOWN")
            self.assertFalse(result["models_loaded"])
            self.assertFalse(result["model_execution_authorized"])
            self.assertEqual(result["model_calls"],0)
            self.assertEqual(len({(x["task_id"],x["mode"]) for x in result["controls"]}),16)


if __name__ == "__main__":
    unittest.main()


def test_release_rejects_changed_sources_and_public_input(tmp_path):
    import copy
    import shutil
    import pytest
    source = ctl.ROOT / 'work/req030ah_controls_20260930_a'
    if not source.exists():
        pytest.skip('private frozen input bundle not installed')
    bundle = tmp_path / 'bundle'
    shutil.copytree(source, bundle)
    doc = json.loads((bundle / 'input_manifest.json').read_bytes())
    rels = [ctl.PARSER_REL, 'experiments/lead_req030/req030ah_controls.py',
            'experiments/lead_req030/req030ag_screen.py',
            'experiments/lead_req030/req030ag_bounded_supervisor.py',
            'experiments/lead_req030/bounded_supervisor.py']
    doc.update(release_id=ctl.RELEASE_ID, limits=ctl.LIMITS, model_execution_authorized=False,
               source_pins={r:ctl.shared.sha_file(ctl.ROOT/r) for r in rels})
    manifest = bundle / 'test_release.json'
    def load(data):
        manifest.write_bytes(ctl.shared.canonical(data))
        return ctl.load_release(bundle, manifest, ctl.shared.sha_file(manifest))
    assert load(doc)['tasks'] == doc['tasks']
    mutated = copy.deepcopy(doc); mutated['model_execution_authorized'] = True
    with pytest.raises(ValueError, match='CPU-only'):
        load(mutated)
    mutated = copy.deepcopy(doc); mutated['source_pins'][rels[0]] = 'a'*64
    with pytest.raises(ValueError, match='source identity'):
        load(mutated)
    public = bundle / 'public' / (ctl.TASK_IDS[0]+'.json')
    data = json.loads(public.read_bytes()); data['reference_patch'] = 'forbidden'
    public.write_bytes(ctl.shared.canonical(data))
    mutated = copy.deepcopy(doc)
    mutated['tasks'][0]['public_projection_sha256'] = ctl.shared.sha_file(public)
    mutated['tasks'][0]['public_projection_bytes'] = public.stat().st_size
    with pytest.raises(ValueError, match='allowlist'):
        load(mutated)
