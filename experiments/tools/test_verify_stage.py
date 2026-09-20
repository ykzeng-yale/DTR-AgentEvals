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
import hashlib  # noqa: E402
import common  # noqa: E402
import verify_stage as V  # noqa: E402

CFG = common.load_config()
DESIGN = json.loads((common.RESULTS / 'design.json').read_text())
VT = V.base_vt_sha()
CODE = 'c' * 64
META = dict(config_sha256=CFG['_config_sha256'], tasks_sha256=DESIGN['tasks_sha256'], visible_tests_sha256=VT,
            code_sha256=CODE)
EP = dict(episode_id='e1', task_uid='t1', split='confirm', error=None, seed=None,
          invocation='inv1', attempt=1, decisions=[dict(t=0, a=1, completed=True)], **META)
DEC = dict(episode_id='e1', invocation='inv1', attempt=1, t=0, a=1)
MAN = dict(invocation='inv1', started_utc='2026-09-20T00:00:00Z', code_sha256=CODE)


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
        (lg / 'decisions.jsonl').write_text(json.dumps(dict(episode_id='p1', invocation='inv1', attempt=1, t=0, a=1)) + '\n')
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
    assert_flags(build(tmp_path, stage='branch', episodes=(bad,), decisions=(DEC,),
                       log_parents=[dict(episode_id='p1', error=None)]), 'record no parent', stage='branch')


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


def test_empty_reference_log_is_refused(tmp_path):
    """A reference file that exists but supplies no completed parents must fail closed."""
    bad = dict(EP, parent_episode_id='p1', restoration=dict(transcript_hash_matches=True, tool_result_reproduced=True))
    ep = build(tmp_path, stage='branch', episodes=(bad,), decisions=(DEC,), log_parents=[dict(episode_id='p1', error='boom')])
    assert_flags(ep, 'supplies no completed parent episodes', stage='branch')


def test_manifest_without_invocation_ids_fails(tmp_path):
    """A nonempty manifest that carries no invocation identifiers is not usable reference data."""
    assert_flags(build(tmp_path, manifest=(dict(started_utc='x'),)), 'carries no invocation identifiers')


def test_missing_code_sha_fails(tmp_path):
    assert_flags(build(tmp_path, episodes=(dict(EP, code_sha256=None),)), 'missing code_sha256')


def test_code_sha_absent_from_manifest_fails(tmp_path):
    """Superseded message: the rule is now per-invocation, so an unrecorded hash fails as 'not recorded by their
    own invocation' rather than merely 'absent from the manifest'."""
    ep = build(tmp_path, episodes=(dict(EP, code_sha256='a' * 64),), manifest=(dict(MAN, code_sha256='b' * 64),))
    assert_flags(ep, 'not recorded by their own invocation')


def test_ledger_with_wrong_declared_count_fails(tmp_path):
    """Declaring more historical rows than are retained must not pass."""
    hist = dict(DEC, invocation='lost_inv')
    led = dict(stage='log', rows=[dict(episode_id='e1', invocation='lost_inv', attempt=1, durable_decision_rows=7)],
               total_rows=7, total_episode_ids=1)
    man = (MAN, dict(MAN, invocation='lost_inv'))
    assert_flags(build(tmp_path, decisions=(DEC, hist), manifest=man, ledger=led), 'declares 7 row(s)')


def test_ledger_total_inconsistent_with_rows_fails(tmp_path):
    hist = dict(DEC, invocation='lost_inv')
    led = dict(stage='log', rows=[dict(episode_id='e1', invocation='lost_inv', attempt=1, durable_decision_rows=1)],
               total_rows=99, total_episode_ids=1)
    man = (MAN, dict(MAN, invocation='lost_inv'))
    assert_flags(build(tmp_path, decisions=(DEC, hist), manifest=man, ledger=led), 'total_rows 99')


def test_impossible_historical_stage_fails(tmp_path):
    """A declared historical decision at t=99 with horizon 3 must fail, not ride the ledger exemption."""
    hist = dict(DEC, invocation='lost_inv', t=99)
    led = dict(stage='log', rows=[dict(episode_id='e1', invocation='lost_inv', attempt=1, durable_decision_rows=1)],
               total_rows=1, total_episode_ids=1)
    man = (MAN, dict(MAN, invocation='lost_inv'))
    assert_flags(build(tmp_path, decisions=(DEC, hist), manifest=man, ledger=led), 'outside [0,')


# --- restoration-report binding (branch stage) ---------------------------------------------------------------
PARENT = dict(episode_id='p1', error=None)
BR = dict(EP, episode_id='b1', parent_episode_id='p1', fork_t=1,
          decisions=[dict(t=1, a=1, completed=True, transcript_sha256='d' * 64)],
          restoration=dict(transcript_hash_matches=True, tool_result_reproduced=True))
BRDEC = dict(episode_id='b1', invocation='inv1', attempt=1, t=1, a=1)


def branch_case(tmp_path, report_overrides=None, episodes=(BR,)):
    d = build(tmp_path, stage='branch', episodes=episodes, decisions=(BRDEC,), log_parents=[PARENT])
    (tmp_path / 'visible_tests.json').write_text('{}')
    ana = tmp_path / 'analysis'; ana.mkdir(exist_ok=True)
    ids = sorted(e['episode_id'] for e in episodes)
    rep = dict(branch_episodes_checked=len(episodes), missing_parent=0, disagreements=0,
               recomputed_transcript_hash_matches=len(episodes), branch_side_transcript_hash_matches=len(episodes),
               source_binding=dict(branch_episodes_sha256=common.sha256_bytes(d.read_bytes()),
                                   log_episodes_sha256=common.sha256_bytes((tmp_path / 'log' / 'episodes.jsonl').read_bytes()),
                                   visible_tests_sha256=common.sha256_bytes((tmp_path / 'visible_tests.json').read_bytes()),
                                   covered_episode_ids_sha256=hashlib.sha256('\n'.join(ids).encode()).hexdigest(),
                                   tasks_sha256=DESIGN['tasks_sha256'],
                                   branch_decisions_sha256=common.sha256_bytes((tmp_path / 'branch' / 'decisions.jsonl').read_bytes()),
                                   log_decisions_sha256=common.sha256_bytes((tmp_path / 'log' / 'decisions.jsonl').read_bytes()),
                                   n_covered=len(ids)))
    rep.update(report_overrides or {})
    (ana / 'restoration_recheck.json').write_text(json.dumps(rep))
    return d


def test_bound_restoration_report_passes(tmp_path):
    assert probs(branch_case(tmp_path), 'branch') == []


def test_restoration_binding_fails_closed_when_a_source_file_is_absent(tmp_path):
    d = branch_case(tmp_path)
    (tmp_path / 'log' / 'decisions.jsonl').unlink()
    assert_flags(d, 'binding cannot be checked: missing', stage='branch')


def test_restoration_report_not_bound_to_current_branch_records_fails(tmp_path):
    """Altering branch records after the report was written must invalidate it (stale source binding)."""
    d = branch_case(tmp_path)
    rows = d.read_text().splitlines()
    rec = json.loads(rows[0]); rec['decisions'][0]['transcript_sha256'] = '0' * 64
    d.write_text(json.dumps(rec) + '\n')
    assert_flags(d, 'not bound to the current records', stage='branch')


def test_restoration_report_with_branch_side_hash_failures_fails(tmp_path):
    d = branch_case(tmp_path, report_overrides=dict(branch_side_transcript_hash_matches=0))
    assert_flags(d, 'branch-side transcript hashes match', stage='branch')


def test_source_hash_only_in_another_invocations_manifest_fails(tmp_path):
    """A code_sha256 recorded under a different invocation is not evidence for this one."""
    ep = build(tmp_path, episodes=(dict(EP, invocation='inv1', code_sha256='a' * 64),),
               decisions=(dict(DEC, invocation='inv1'),),
               manifest=(dict(MAN, invocation='inv1', code_sha256='z' * 64), dict(MAN, invocation='other', code_sha256='a' * 64)))
    assert_flags(ep, 'not recorded by their own invocation')


def test_no_manifest_source_hash_fails_closed(tmp_path):
    """If no manifest row records a source hash the check must fail, not be skipped."""
    man = (dict(invocation='inv1', started_utc='x'),)
    assert_flags(build(tmp_path, manifest=man), 'source identity cannot be checked')


def test_real_stages_still_pass():
    for stage in ('log', 'live', 'branch'):
        ep = common.RESULTS / stage / 'episodes.jsonl'
        assert probs(ep, stage) == [], stage
