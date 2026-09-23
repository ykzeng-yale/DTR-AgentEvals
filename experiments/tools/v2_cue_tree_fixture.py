"""Disposable copies of the cue-v1 bound inputs, shared by test_v2_cue_admission.py and test_v2_cue_integration.py.

A tree is a byte-for-byte copy of exactly what cue_admission binds: the cue-v1 execution modules, the lead-accepted
helpers, the frozen yaml-v1 reference sources, the pin records, the accepted-pin documents, the pinned dataset file,
the pinned mini-swe-agent sources and, from the pinned interpreter's site-packages, the dist-info RECORDs, the SDK
files on the traced request path and the editable mini-swe-agent .pth (rewritten to point at the tree's own copy).
Nothing under this checkout's results/ is created or changed, and results/v2_agent/pilot_20260923_cue_v1 is only
ever created inside a tree.
"""
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'experiments/v2_agent'))
import cue_admission as A  # noqa: E402

MSWEA_SRC = 'work/upstream/mini-swe-agent-04d809ceab9df28f9adaed044884180159172930/src/minisweagent'
SITE = 'work/venvs/minisweagent_04d809c/lib/python3.12/site-packages'
DIST_INFOS = ('httpcore-1.0.9.dist-info', 'httpx-0.28.1.dist-info', 'litellm-1.102.0.dist-info',
              'openai-2.54.0.dist-info', 'tenacity-9.1.4.dist-info')
MODULES = ('cue_episode.py', 'cue_transport.py', 'cue_terminal.py', 'cue_admission.py', 'cue_runner.py',
           'cue_detector.py', 'exit_capture.py', 'request_receipt.py', 'trajectory_triples.py', 'cue_cohort.py',
           'workspace_capture.py', 'pilot_episode.py', 'pilot_runner.py', 'pilot_cohort.py', 'pilot_report.py',
           'pilot_grade.py')
FILES = ('docs/req005_visible_evidence_guide_20260923.md',
         'docs/audits/req005_component_review_20260923.json',
         'docs/req005_fixture_landmarks_20260923.json',
         'configs/v2_fixed_backend_development_pilot_yaml_v1_20260922.json',
         'configs/v2_fixed_backend_development_pilot_20260922.json',
         'results/v2_agent/pilot_frame_20260922.json',
         'results/v2_agent/coder_conversion_20260922.json',
         'results/v2_agent/pilot_20260922_yaml_v1/cohort_binding.json',
         A.DATASET_REL)
TRACED = tuple(rel for rels in A.TRACED_SDK_FILES.values() for rel in rels)


def available():
    """(present, reason). The pinned checkout pieces a tree is built from must exist in this checkout."""
    needed = [REPO / MSWEA_SRC / 'config/default.yaml', REPO / A.DATASET_REL]
    needed += [REPO / SITE / dist / 'RECORD' for dist in DIST_INFOS] + [REPO / SITE / rel for rel in TRACED]
    missing = [str(p.relative_to(REPO)) for p in needed if not p.is_file()]
    return (not missing), ('pinned checkout pieces absent: %s' % ', '.join(missing[:4]) if missing else None)


def build(base):
    """A fresh tree at `base` (which must not exist)."""
    base = Path(base)
    for name in MODULES:
        target = base / 'experiments/v2_agent' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / 'experiments/v2_agent' / name, target)
    for rel in FILES:
        (base / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / rel, base / rel)
    shutil.copytree(REPO / MSWEA_SRC, base / MSWEA_SRC, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for dist in DIST_INFOS:
        (base / SITE / dist).mkdir(parents=True)
        shutil.copy2(REPO / SITE / dist / 'RECORD', base / SITE / dist / 'RECORD')
    for rel in TRACED:
        (base / SITE / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO / SITE / rel, base / SITE / rel)
    point_editable_install(base)
    return base


def point_editable_install(root):
    """The editable mini-swe-agent install of a tree points at the tree's own source copy."""
    pth = Path(root) / SITE / A.EDITABLE_MSWEA_PTH
    pth.write_text(str((Path(root) / MSWEA_SRC).parent) + '\n')
    return pth


def copy(template, target):
    """A per-test copy of a module-scoped template tree, with its editable install repointed."""
    shutil.copytree(template, target)
    point_editable_install(target)
    return Path(target)
