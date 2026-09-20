"""Fixtures proving each publication-gate check FAILS on its defect.

A gate that only ever passes is not evidence. An external audit of an earlier version found 14 defective cases still
accepted (docs/theory_feedback_20260920_sampling.md), and correctly noted that the test then named
`test_false_restoration_flag_fails` actually tested a MISSING PARENT with true flags. Both the check and the fixture
are fixed here: `test_restoration_flag_false_fails` sets the flag to False, and the missing-parent case is separate.

Run: .venv/bin/python -m pytest -q experiments/tools/test_verify_stage.py
"""
import json, sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for sub in ('tools', 'code_routing', 'common'):
    sys.path.insert(0, str(ROOT / 'experiments' / sub))
import common  # noqa: E402
import verify_stage as V  # noqa: E402

CFG = common.load_config()
DESIGN = json.loads((common.RESULTS / 'design.json').read_text())
VT = V.base_vt_sha()
META = dict(config_sha256=CFG['_config_sha256'], tasks_sha256=DESIGN['tasks_sha256'], visible_tests_sha256=VT)
EP = dict(episode_id='e1', task_uid='t1', split='confirm', error=None, seed=None,
          decisions=[dict(t=0, a=1, completed=True)], **META)
DEC = dict(episode_id='e1', invocation='inv1', t=0, a=1)
MAN = dict(invocation='inv1', started_utc='2026-09-20T00:00:00Z')


def build(tmp, stage='log', episodes=(EP,), decisions=(DEC,), manifest=(MAN,), torn=False, log_parents=None):
    d = tmp / stage; d.mkdir(parents=True, exist_ok=True)
    body = ''.join(json.dumps(e) + '\n' for e in episodes)
    if torn:
        body += '{"episode_id": "e9", "tru'
    (d / 'episodes.jsonl').write_text(body)
    if decisions is not None:
        (d / 'decisions.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in decisions))
    if manifest is not None:
        (d / 'run_manifest.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in manifest))
    if log_parents is not None:
        lg = tmp / 'log'; lg.mkdir(parents=True, exist_ok=True)
        (lg / 'episodes.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in log_parents))
    return d / 'episodes.jsonl'


def probs(ep, stage='log'):
    return V.check_records(ep, ep.parent, stage, common.resolve_episodes(ep, CFG['max_attempts_per_episode']), DESIGN, CFG)


def assert_flags(ep, needle, stage='log'):
    p = probs(ep, stage)
    assert any(needle in x for x in p), (needle, p)


def test_clean_fixture_passes(tmp_path):
    assert probs(build(tmp_path)) == []


def test_torn_tail_is_detected(tmp_path):
    ep = build(tmp_path, torn=True)
    assert common.resolve_episodes(ep, CFG['max_attempts_per_episode'])['torn'] == 1


def test_duplicate_completed_row_fails(tmp_path):
    assert_flags(build(tmp_path, episodes=(EP, dict(EP))), 'more than one completed row')


@pytest.mark.parametrize('key', ['config_sha256', 'tasks_sha256', 'visible_tests_sha256'])
def test_absent_required_hash_fails(tmp_path, key):
    assert_flags(build(tmp_path, episodes=(dict(EP, **{key: None}),)), 'missing %s' % key)


@pytest.mark.parametrize('key', ['config_sha256', 'tasks_sha256', 'visible_tests_sha256'])
def test_wrong_required_hash_fails(tmp_path, key):
    assert_flags(build(tmp_path, episodes=(dict(EP, **{key: '0' * 64}),)), '%s does not match' % key)


def test_seed_differing_from_design_fails(tmp_path):
    real = DESIGN['log_episodes'][0]
    ep = build(tmp_path, episodes=(dict(EP, episode_id=real['episode_id'], seed=real['seed'] + 1),))
    assert_flags(ep, 'seed that differs from the frozen design')


def test_restoration_flag_false_fails(tmp_path):
    bad = dict(EP, parent_episode_id='p1', restoration=dict(transcript_hash_matches=False, tool_result_reproduced=True))
    assert_flags(build(tmp_path, stage='branch', episodes=(bad,), log_parents=[dict(episode_id='p1', error=None)]),
                 'false/absent restoration flag', stage='branch')


def test_restoration_absent_fails(tmp_path):
    bad = dict(EP, parent_episode_id='p1')
    assert_flags(build(tmp_path, stage='branch', episodes=(bad,), log_parents=[dict(episode_id='p1', error=None)]),
                 'no restoration evidence', stage='branch')


def test_missing_parent_id_fails(tmp_path):
    bad = dict(EP, restoration=dict(transcript_hash_matches=True, tool_result_reproduced=True))
    assert_flags(build(tmp_path, stage='branch', episodes=(bad,), log_parents=[]), 'record no parent', stage='branch')


def test_nonexistent_parent_fails(tmp_path):
    bad = dict(EP, parent_episode_id='ghost', restoration=dict(transcript_hash_matches=True, tool_result_reproduced=True))
    assert_flags(build(tmp_path, stage='branch', episodes=(bad,), log_parents=[dict(episode_id='p1', error=None)]),
                 'not a completed log episode', stage='branch')


def test_missing_decisions_file_fails(tmp_path):
    assert_flags(build(tmp_path, decisions=None), 'decisions.jsonl is missing or empty')


def test_empty_decisions_file_fails(tmp_path):
    assert_flags(build(tmp_path, decisions=()), 'decisions.jsonl is missing or empty')


def test_missing_manifest_fails(tmp_path):
    assert_flags(build(tmp_path, manifest=None), 'run_manifest.jsonl is missing or empty')


def test_null_invocation_fails(tmp_path):
    assert_flags(build(tmp_path, decisions=(dict(DEC, invocation=None),)), 'null/absent invocation id')


def test_invocation_not_in_manifest_fails(tmp_path):
    assert_flags(build(tmp_path, decisions=(dict(DEC, invocation='unrelated'),)), 'absent from the manifest')


def test_orphan_decisions_fail(tmp_path):
    assert_flags(build(tmp_path, decisions=(DEC, dict(DEC, episode_id='ghost'))), 'no resolved episode')


def test_durable_action_disagreeing_with_episode_fails(tmp_path):
    assert_flags(build(tmp_path, decisions=(dict(DEC, a=0),)), 'disagree with the episode record')


def test_real_stages_still_pass():
    for stage in ('log', 'live', 'branch'):
        ep = common.RESULTS / stage / 'episodes.jsonl'
        assert probs(ep, stage) == [], stage
