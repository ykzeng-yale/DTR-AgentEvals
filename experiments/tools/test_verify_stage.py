"""Fixtures proving each publication-gate check FAILS on a defect.

Required by docs/theory_feedback_20260920_branch.md: "Add fixtures that fail for a torn tail, duplicate success row,
metadata mismatch and false restoration flag. Check invocation-linked decisions."
A gate that only ever passes is not evidence.  Run: .venv/bin/python -m pytest -q experiments/tools/test_verify_stage.py
"""
import json, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments' / 'tools'))
sys.path.insert(0, str(ROOT / 'experiments' / 'code_routing'))
sys.path.insert(0, str(ROOT / 'experiments' / 'common'))
import common  # noqa: E402
import verify_stage as V  # noqa: E402

CFG = common.load_config()
DESIGN = json.loads((common.RESULTS / 'design.json').read_text())
GOOD = dict(episode_id='e1', task_uid='t1', split='confirm', error=None,
            config_sha256=CFG['_config_sha256'], tasks_sha256=DESIGN['tasks_sha256'],
            visible_tests_sha256=V.base_vt_sha(), decisions=[])


def write(tmp, episodes, decisions=None, torn=False):
    d = tmp / 'log'; d.mkdir(parents=True, exist_ok=True)
    body = ''.join(json.dumps(e) + '\n' for e in episodes)
    if torn:
        body += '{"episode_id": "e2", "tru'
    (d / 'episodes.jsonl').write_text(body)
    if decisions is not None:
        (d / 'decisions.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in decisions))
    return d / 'episodes.jsonl'


def res_of(ep):
    return common.resolve_episodes(ep, CFG['max_attempts_per_episode'])


def test_clean_fixture_has_no_problems(tmp_path):
    ep = write(tmp_path, [GOOD], decisions=[dict(episode_id='e1', invocation='abc', t=0)])
    assert V.check_records(ep, ep.parent, 'log', res_of(ep), DESIGN, CFG) == []


def test_torn_tail_is_detected(tmp_path):
    ep = write(tmp_path, [GOOD], torn=True)
    assert res_of(ep)['torn'] == 1          # main() turns this into a FAILED status, not a printed note


def test_duplicate_completed_row_fails(tmp_path):
    ep = write(tmp_path, [GOOD, dict(GOOD)])
    probs = V.check_records(ep, ep.parent, 'log', res_of(ep), DESIGN, CFG)
    assert any('more than one completed row' in p for p in probs), probs


def test_frozen_metadata_mismatch_fails(tmp_path):
    ep = write(tmp_path, [dict(GOOD, config_sha256='0' * 64)])
    probs = V.check_records(ep, ep.parent, 'log', res_of(ep), DESIGN, CFG)
    assert any('config_sha256' in p for p in probs), probs


def test_tasks_sha_mismatch_fails(tmp_path):
    ep = write(tmp_path, [dict(GOOD, tasks_sha256='1' * 64)])
    probs = V.check_records(ep, ep.parent, 'log', res_of(ep), DESIGN, CFG)
    assert any('tasks_sha256' in p for p in probs), probs


def test_false_restoration_flag_fails(tmp_path):
    bad = dict(GOOD, restoration=dict(transcript_hash_matches=True, tool_result_reproduced=True))
    bad.pop('parent_episode_id', None)
    ep = write(tmp_path, [bad])
    probs = V.check_records(ep, ep.parent, 'branch', res_of(ep), DESIGN, CFG)
    assert any('matching transcript hash with no parent' in p for p in probs), probs


def test_decisions_without_invocation_fail(tmp_path):
    ep = write(tmp_path, [GOOD], decisions=[dict(episode_id='e1', t=0)])
    probs = V.check_records(ep, ep.parent, 'log', res_of(ep), DESIGN, CFG)
    assert any('without an invocation id' in p for p in probs), probs


def test_orphan_decisions_fail(tmp_path):
    ep = write(tmp_path, [GOOD], decisions=[dict(episode_id='ghost', invocation='abc', t=0)])
    probs = V.check_records(ep, ep.parent, 'log', res_of(ep), DESIGN, CFG)
    assert any('durable decisions but no resolved episode' in p for p in probs), probs


def test_real_stages_still_pass():
    for stage in ('log', 'live', 'branch'):
        ep = common.RESULTS / stage / 'episodes.jsonl'
        assert V.check_records(ep, ep.parent, stage, res_of(ep), DESIGN, CFG) == []
