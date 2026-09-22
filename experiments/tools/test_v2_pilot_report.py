"""Deterministic report/grading-boundary fixtures; no runtime or model calls."""
import hashlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_agent'))
import pilot_report as RP  # noqa: E402
import pilot_grade as PG  # noqa: E402

IMAGE = 'sha256:fixture-image'
FRAME = dict(pilot=dict(tasks=[dict(position=i + 1, instance_id=iid, backend_order=order, instance_image=IMAGE)
                               for i, (iid, order) in enumerate([
                                   ('a__1', ['small', 'large']), ('b__2', ['large', 'small']), ('c__3', ['large', 'small'])])]))


def msgs(n_calls, rc=(0,), cmd='ls'):
    result = [dict(role='system', content='s'), dict(role='user', content='task')]
    for i in range(n_calls):
        result.append(dict(role='assistant', content='c%d' % i,
                           extra=dict(actions=[dict(command=cmd if i else 'python -m pytest -q')])) )
        result.append(dict(role='user', content='o%d' % i, extra=dict(returncode=rc[i % len(rc)])))
    return result


def evaluated(value):
    return dict(classification='evaluated', grade_valid=True, operational_resolved=value,
                algorithmic_correctness='resolved' if value else 'unresolved')


def write_grade(directory, grade):
    record = json.loads((directory / 'episode.json').read_text())
    bound = dict(instance_id=record['instance_id'], backend=record['backend'], episode_run_id=record['run_id'],
                 submission_sha256=record['submission_sha256'], image_id=IMAGE)
    (directory / 'grade.json').write_text(json.dumps(dict(bound, **grade)))


def ep(out, iid, backend, exit_status, n_calls, grade=None, rc=(0,), cmd='ls', ledger=True, **kw):
    directory = out / ('%s__%s__pilot-cp2-wc2__T-000000' % (iid, backend))
    directory.mkdir(parents=True)
    patch = b'fixture patch\n' if exit_status == 'Submitted' else b''
    (directory / 'submission.diff').write_bytes(patch)
    record = dict(instance_id=iid, backend=backend, run_id=directory.name, exit_status=exit_status, n_model_calls=n_calls,
                  submission_empty=not patch, submission_sha256=hashlib.sha256(patch).hexdigest(), pins=dict(image_id=IMAGE),
                  physical_requests=n_calls, failed_attempts=0, max_attempts_on_one_call=1,
                  prompt_tokens=None if n_calls is None else 100 * n_calls,
                  completion_tokens=None if n_calls is None else 10 * n_calls, wall_seconds=60.0)
    record.update(kw)
    (directory / 'episode.json').write_text(json.dumps(record))
    (directory / 'trajectory.json').write_text(json.dumps(dict(messages=msgs(n_calls or 0, rc, cmd))))
    if ledger:
        attempts = []
        for call in range(1, (n_calls or 0) + 1):
            attempts.extend([dict(event='start', call=call, attempt=1, t_start=call),
                             dict(event='result', call=call, attempt=1, t_start=call, t_end=call + .1,
                                  ok=True, prompt_tokens=100, completion_tokens=10)])
        (directory / 'attempts.jsonl').write_text(''.join(json.dumps(a) + '\n' for a in attempts))
    if n_calls is not None and n_calls >= 9:
        (directory / 'call9_history.json').write_text(json.dumps(dict(call=9, messages=msgs(8, rc, cmd), captured_at=9)))
    if grade is not None:
        write_grade(directory, grade)
    return directory


def test_denominator_classifications_bounds_and_pairs(tmp_path):
    ep(tmp_path, 'a__1', 'small', 'Submitted', 12, evaluated(1), rc=(0, 1), cmd="sed -i 's/a/b/' x.py")
    ep(tmp_path, 'a__1', 'large', 'Submitted', 7, evaluated(0))
    ep(tmp_path, 'b__2', 'large', 'LimitsExceeded', 24,
       dict(classification='operational_zero', grade_valid=True, operational_resolved=0, algorithmic_correctness='not_evaluated'))
    ep(tmp_path, 'b__2', 'small', 'Submitted', 9,
       dict(classification='unknown_evaluator_failure', grade_valid=True, operational_resolved=0, algorithmic_correctness='unknown'))
    ep(tmp_path, 'c__3', 'large', 'Submitted', 10,
       dict(classification='integrity_refusal', grade_valid=False, operational_resolved=None, algorithmic_correctness=None))
    (tmp_path / 'c__3__small__pilot-cp2-wc2__T-111111').mkdir()
    rep = RP.report(FRAME, tmp_path)
    assert (rep['assigned'], rep['terminal'], len(rep['episodes']), len(rep['paired']['per_task'])) == (6, 5, 6, 3)
    assert rep['not_terminal'][0]['state'] == 'incomplete'
    small, large = rep['backends']['small'], rep['backends']['large']
    assert (small['assigned'], small['valid_grades'], small['operational_resolved']) == (3, 2, 1)
    assert {k: small['algorithmic_bounds'][k] for k in ('denominator', 'low', 'high', 'unknown')} == dict(denominator=2, low=1, high=2, unknown=1)
    # Intact local artifact + invalid evaluator grade remains algorithmically unknown.
    assert {k: large['algorithmic_bounds'][k] for k in ('denominator', 'low', 'high', 'unknown')} == dict(denominator=2, low=0, high=1, unknown=1)
    assert {k: rep['operational_completion_bounds'][k] for k in ('denominator', 'low', 'high', 'unknown')} == dict(denominator=6, low=1, high=3, unknown=2)
    assert small['call9_eligible'] == large['call9_eligible'] == 2
    assert small['call9_feedback_known'] == 2 and small['call9_nonzero_returncodes'] == 4
    assert small['call9_test_command_pattern_seen'] == 2 and small['call9_edit_command_pattern_seen'] == 1
    assert rep['paired']['cells_small_large'] == {'1,1': 0, '1,0': 1, '0,1': 0, '0,0': 1}
    assert rep['paired']['paired_cost_differences']['prompt_tokens'] == dict(known_pair_count=2, missing_pair_count=1, known_pair_sum_large_minus_small=1000)
    assert small['prompt_tokens'] is None and small['costs']['prompt_tokens']['known_subtotal'] == 2100
    assert large['prompt_tokens'] == 4100


def test_frozen_eight_task_frame_keeps_every_empty_assignment_and_pair(tmp_path):
    frame = RP.read_json(RP.FRAME)
    rep = RP.report(frame, tmp_path)
    assert rep['assigned'] == len(rep['episodes']) == len(rep['not_terminal']) == 16
    assert rep['paired']['assigned_pairs'] == len(rep['paired']['per_task']) == 8
    assert [r['instance_id'] for r in rep['paired']['per_task']] == [t['instance_id'] for t in frame['pilot']['tasks']]
    assert all(r['small'] is None and r['large'] is None for r in rep['paired']['per_task'])
    assert rep['operational_completion_bounds']['high'] == 16


def test_call9_issued_with_rejected_responses_has_unknown_feedback_not_crash(tmp_path):
    directory = ep(tmp_path, 'a__1', 'small', 'RepeatedFormatError', 9)
    (directory / 'trajectory.json').write_text(json.dumps(dict(messages=msgs(6))))
    (directory / 'call9_history.json').unlink()
    row = RP.report(FRAME, tmp_path)['episodes'][0]
    assert row['call9_eligible'] is True and row['call9_feedback'] is None
    assert row['completed_assistant_messages'] == 6


def test_snapshot_before_deadline_is_not_evidence_of_call9_dispatch(tmp_path):
    directory = ep(tmp_path, 'a__1', 'small', 'TimeExceeded', 8)
    (directory / 'call9_history.json').write_text(json.dumps(dict(call=9, messages=msgs(8))))
    row = RP.report(FRAME, tmp_path)['episodes'][0]
    assert row['call9_eligible'] is False and row['call9_feedback'] is None


def test_hardkill_missing_telemetry_is_null_not_zero(tmp_path):
    ep(tmp_path, 'a__1', 'small', 'RunnerHardKill', None, ledger=False,
       physical_requests=None, failed_attempts=None, prompt_tokens=None, completion_tokens=None, wall_seconds=None)
    rep = RP.report(FRAME, tmp_path)
    row = rep['episodes'][0]
    assert all(row[k] is None for k in RP.METRICS) and row['call9_eligible'] is None
    assert all(rep['backends']['small'][k] is None for k in RP.METRICS)
    assert rep['backends']['small']['costs']['prompt_tokens']['missing_or_partial_episode_count'] == 3


def test_failed_and_unfinished_physical_requests_keep_unknown_tokens(tmp_path):
    directory = ep(tmp_path, 'a__1', 'small', 'RunnerHardKill', 2)
    records = [dict(event='start', call=1, attempt=1),
               dict(event='result', call=1, attempt=1, ok=False, error='Timeout'),
               dict(event='start', call=1, attempt=2),
               dict(event='result', call=1, attempt=2, ok=True, prompt_tokens=13, completion_tokens=7),
               dict(event='start', call=2, attempt=1)]
    (directory / 'attempts.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in records))
    row = RP.report(FRAME, tmp_path)['episodes'][0]
    assert row['physical_requests'] == 3 and row['max_attempts_on_one_call'] == 2
    assert row['prompt_tokens'] is None and row['completion_tokens'] is None and row['failed_attempts'] is None
    assert row['known_subtotals']['prompt_tokens'] == 13 and row['known_subtotals']['completion_tokens'] == 7
    assert row['telemetry']['prompt_tokens_missing_attempts'] == 2 and row['telemetry']['unresolved_attempts'] == 1


def test_secondary_bounds_include_parser_unknown_ungraded_and_invalid_local_candidates(tmp_path):
    ep(tmp_path, 'a__1', 'small', 'Submitted', 1,
       dict(classification='evaluated', grade_valid=True, operational_resolved=0, algorithmic_correctness='unknown_evaluator_failure'))
    ep(tmp_path, 'b__2', 'small', 'Submitted', 1)
    ep(tmp_path, 'c__3', 'small', 'Submitted', 1,
       dict(classification='integrity_refusal', grade_valid=False, operational_resolved=None, algorithmic_correctness='resolved'))
    rep = RP.report(FRAME, tmp_path)
    bounds = rep['backends']['small']['algorithmic_bounds']
    assert (bounds['denominator'], bounds['low'], bounds['high'], bounds['unknown']) == (3, 0, 3, 3)
    assert rep['operational_completion_bounds']['unknown'] == 5  # evaluated parser failure is a known operational zero


def test_single_incomplete_ledger_keeps_known_usage_and_call9_without_final_totals(tmp_path):
    directory = ep(tmp_path, 'a__1', 'small', 'Submitted', 9)
    (directory / 'episode.json').unlink()
    rep = RP.report(FRAME, tmp_path)
    row = rep['episodes'][0]
    assert row['state'] == 'incomplete' and row['physical_requests'] is None and row['prompt_tokens'] is None
    assert row['known_subtotals']['physical_requests'] == 9 and row['known_subtotals']['prompt_tokens'] == 900
    assert row['call9_eligible'] is True and row['call9_feedback']['observations'] == 8
    assert rep['backends']['small']['call9_eligible'] == 1
    assert rep['backends']['small']['costs']['prompt_tokens']['known_subtotal'] == 900
    assert rep['backends']['small']['costs']['prompt_tokens']['missing_or_partial_episode_count'] == 3


@pytest.mark.parametrize('field,value', [('instance_id', 'other-task'), ('backend', 'large'),
                                        ('episode_run_id', 'other-run'), ('submission_sha256', 'wrong')])
def test_mismatched_grade_is_refused_before_counting(tmp_path, field, value):
    directory = ep(tmp_path, 'a__1', 'small', 'Submitted', 1, evaluated(1))
    grade = RP.read_json(directory / 'grade.json')
    grade[field] = value
    (directory / 'grade.json').write_text(json.dumps(grade))
    with pytest.raises(RP.ReportIntegrityError, match='grade identity/hash'):
        RP.report(FRAME, tmp_path)


def test_wrong_episode_assignment_and_tampered_artifact_are_refused(tmp_path):
    directory = ep(tmp_path, 'a__1', 'small', 'Submitted', 1)
    record = RP.read_json(directory / 'episode.json')
    record['instance_id'] = 'not-selected'
    (directory / 'episode.json').write_text(json.dumps(record))
    with pytest.raises(RP.ReportIntegrityError, match='identity'):
        RP.report(FRAME, tmp_path)
    record['instance_id'] = 'a__1'
    (directory / 'episode.json').write_text(json.dumps(record))
    (directory / 'submission.diff').write_text('changed')
    with pytest.raises(RP.ReportIntegrityError, match='artifact disagrees'):
        RP.report(FRAME, tmp_path)


def test_grade_pass_skips_valid_existing_grade_and_preserves_failed_ungraded(tmp_path):
    ep(tmp_path, 'a__1', 'small', 'Submitted', 1, evaluated(1))
    pending = ep(tmp_path, 'a__1', 'large', 'Submitted', 1)
    calls = []
    def fail(directory):
        calls.append(directory)
        return SimpleNamespace(returncode=1, stderr='fixture early failure', stdout='')
    result = PG.grade_pass(FRAME, tmp_path, fail)
    assert calls == [pending]
    assert result[0]['state'] == 'already_graded'
    assert result[1]['state'] == 'ungraded' and result[1]['returncode'] == 1
    assert not (pending / 'grade.json').exists()


def test_grade_pass_prevalidates_all_existing_grades_before_any_execution(tmp_path):
    ep(tmp_path, 'a__1', 'small', 'Submitted', 1)
    bad = ep(tmp_path, 'c__3', 'small', 'Submitted', 1, evaluated(1))
    grade = RP.read_json(bad / 'grade.json')
    grade['episode_run_id'] = 'stale-run'
    (bad / 'grade.json').write_text(json.dumps(grade))
    calls = []
    with pytest.raises(RP.ReportIntegrityError):
        PG.grade_pass(FRAME, tmp_path, lambda directory: calls.append(directory))
    assert calls == []


@pytest.mark.parametrize('invalid_grade', [{}, [], {'classification': 'evaluated'}])
def test_grade_pass_refuses_empty_or_incomplete_existing_grade(tmp_path, invalid_grade):
    ep(tmp_path, 'a__1', 'small', 'Submitted', 1)  # pending grade earlier in queue
    directory = ep(tmp_path, 'c__3', 'small', 'Submitted', 1)
    (directory / 'grade.json').write_text(json.dumps(invalid_grade))
    calls = []
    with pytest.raises(RP.ReportIntegrityError, match='complete grade object'):
        PG.grade_pass(FRAME, tmp_path, lambda directory: calls.append(directory))
    assert calls == []


def test_block1_legacy_exit_attempt_log_is_admitted_labelled_and_derives_call9_only_when_calls_1_8_answered(tmp_path):
    """Block-1 episodes (pre-a64d81e code) wrote one completed-attempt record per line at episode exit, without
    start/result events. They are admitted as a labelled legacy source; call-9 feedback comes from the trajectory
    prefix only when every logical call 1-8 was answered, otherwise it stays unknown. Expected values by hand."""
    out = tmp_path / 'out'
    for iid, backend, fail_call in (('a__1', 'small', None), ('a__1', 'large', 3)):
        ep(out, iid, backend, 'LimitsExceeded', 10, ledger=False, rc=(0, 1),
           grade=dict(classification='operational_zero', grade_valid=True, operational_resolved=0, algorithmic_correctness='not_evaluated'))
        d = out / ('%s__%s__pilot-cp2-wc2__T-000000' % (iid, backend))
        (d / 'call9_history.json').unlink(missing_ok=True)                       # block 1 wrote no snapshot
        lines = []
        for call in range(1, 11):
            if call == fail_call:
                lines.append(dict(call=call, attempt=1, t_start=1.0, t_end=2.0, ok=False, error='APIConnectionError'))
                lines.append(dict(call=call, attempt=2, t_start=2.0, t_end=3.0, ok=False, error='APIConnectionError'))
            else:
                lines.append(dict(call=call, attempt=1, t_start=1.0, t_end=2.0, ok=True, prompt_tokens=50, completion_tokens=5, finish_reason='stop'))
        (d / 'attempts.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in lines))
    rows = {r['backend']: r for r in RP.report(FRAME, out)['episodes'] if r['instance_id'] == 'a__1'}
    s, l = rows['small'], rows['large']
    assert s['telemetry']['source'] == l['telemetry']['source'] == 'block1_exit_attempt_log'
    assert s['physical_requests'] == 10 and l['physical_requests'] == 11 and l['failed_attempts'] == 2
    assert s['prompt_tokens'] == 500 and l['prompt_tokens'] is None                  # failed attempts: usage unknown, not zero
    assert l['known_subtotals']['prompt_tokens'] == 450
    assert s['call9_eligible'] is True and s['call9_feedback_source'] == 'block1_trajectory_prefix_calls_1_8_answered'
    assert s['call9_feedback']['observations'] == 8 and s['call9_feedback']['nonzero_returncodes'] == 4
    assert l['call9_eligible'] is True and l['call9_feedback'] is None and l['call9_feedback_source'] is None
