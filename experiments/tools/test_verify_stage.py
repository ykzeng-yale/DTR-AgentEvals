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
          invocation='inv1', attempt=1, decisions=[dict(t=0, a=1, completed=True)], **META)
DEC = dict(episode_id='e1', invocation='inv1', attempt=1, t=0, a=1)
MAN = dict(invocation='inv1', started_utc='2026-09-20T00:00:00Z')


def build(tmp, stage='log', episodes=(EP,), decisions=(DEC,), manifest=(MAN,), torn=False, log_parents=None, ledger=None):
    d = tmp / stage; d.mkdir(parents=True, exist_ok=True)
    body = ''.join(json.dumps(e) + '\n' for e in episodes)
    if torn:
        body += '{"episode_id": "e9", "tru'
    (d / 'episodes.jsonl').write_text(body)
    if decisions is not None:
        (d / 'decisions.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in decisions))
    if manifest is not None:
        (d / 'run_manifest.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in manifest))
    if ledger is not None:
        (tmp / 'recovery_ledger.json').write_text(json.dumps(ledger))
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


def test_historical_rows_without_a_ledger_fail(tmp_path):
    """A durable row from an invocation whose episode result was lost must not be silently accepted."""
    hist = dict(DEC, invocation='lost_inv')
    man = (MAN, dict(MAN, invocation='lost_inv'))
    assert_flags(build(tmp_path, decisions=(DEC, hist), manifest=man), 'not in the recovery ledger')


def test_positive_recovery_fixture_passes_with_a_ledger(tmp_path):
    """The historical row is accepted once it is declared in the recovery ledger AND its invocation is a real one
    that wrote a manifest entry - the retained 135-survivor / 665-recovery pattern, where the lost invocation did
    write a manifest row. It is NOT required to match a later invocation."""
    hist = dict(DEC, invocation='lost_inv')
    led = dict(stage='log', rows=[dict(episode_id='e1', invocation='lost_inv', attempt=1, durable_decision_rows=1)])
    man = (MAN, dict(MAN, invocation='lost_inv'))
    assert probs(build(tmp_path, decisions=(DEC, hist), manifest=man, ledger=led)) == []


def test_ledger_cannot_launder_an_invocation_absent_from_the_manifest(tmp_path):
    """Declaring a row in the ledger does not excuse an invocation that never wrote a manifest entry."""
    hist = dict(DEC, invocation='never_ran')
    led = dict(stage='log', rows=[dict(episode_id='e1', invocation='never_ran', attempt=1, durable_decision_rows=1)])
    assert_flags(build(tmp_path, decisions=(DEC, hist), ledger=led), 'absent from the manifest')


def test_ledger_for_another_stage_does_not_excuse_rows(tmp_path):
    hist = dict(DEC, invocation='lost_inv')
    led = dict(stage='branch', rows=[dict(episode_id='e1', invocation='lost_inv', attempt=1, durable_decision_rows=1)])
    man = (MAN, dict(MAN, invocation='lost_inv'))
    assert_flags(build(tmp_path, decisions=(DEC, hist), manifest=man, ledger=led), 'not in the recovery ledger')


def test_decision_attempt_mismatch_is_not_matched(tmp_path):
    """Matching is on episode + invocation + attempt: a row with a different attempt is historical, not a match."""
    assert_flags(build(tmp_path, decisions=(DEC, dict(DEC, attempt=2))), 'not in the recovery ledger')


def test_completed_decision_without_a_durable_record_fails(tmp_path):
    """Every retained completed decision must have its pre-invocation row."""
    two = dict(EP, decisions=[dict(t=0, a=1, completed=True), dict(t=1, a=0, completed=True)])
    assert_flags(build(tmp_path, episodes=(two,), decisions=(DEC,)), 'no durable pre-invocation record')


def test_task_identity_differing_from_design_fails(tmp_path):
    real = DESIGN['log_episodes'][0]
    ep = build(tmp_path, episodes=(dict(EP, episode_id=real['episode_id'], seed=real['seed'], task_uid='not-the-frozen-task'),),
               decisions=(dict(DEC, episode_id=real['episode_id']),))
    assert_flags(ep, 'different task than the frozen design')


def test_branch_without_reference_log_is_refused(tmp_path):
    bad = dict(EP, parent_episode_id='p1', restoration=dict(transcript_hash_matches=True, tool_result_reproduced=True))
    ep = build(tmp_path, stage='branch', episodes=(bad,), decisions=(DEC,))
    assert_flags(ep, 'reference log episodes.jsonl is missing', stage='branch')


def test_real_stages_still_pass():
    for stage in ('log', 'live', 'branch'):
        ep = common.RESULTS / stage / 'episodes.jsonl'
        assert probs(ep, stage) == [], stage
