"""Deterministic acceptance fixtures for the two lead e360831 repairs (no model, no container, no harness):
(1) grading identity - distinct episodes/patches never share predictions/reports/grades; stale, mismatched, ineligible
    or pre-existing outputs are refused;
(2) qualification restart - completed tasks are validated and skipped before any execution with hashes preserved, no
    duplicate finished controls, incomplete attempts retained, conflicting metadata fails explicitly."""
import hashlib, json, sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_agent'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_adapter'))
import grade_identity as GI  # noqa: E402
import qualification_batch as QB  # noqa: E402

IMG = 'sha256:' + 'c' * 64


def episode(run_id, patch, exit_status='Submitted', image=IMG):
    return dict(run_id=run_id, exit_status=exit_status, submission_sha256=GI.sha(patch), pins=dict(image_id=image))


def test_two_episodes_same_task_backend_different_patches_never_share_outputs():
    p1, p2 = 'diff --git a/x b/x\n+1\n', 'diff --git a/x b/x\n+2\n'
    e1, e2 = episode('t__x__large__cp2-wc2__20260922T030000Z-aaaaaa', p1), episode('t__x__large__cp2-wc2__20260922T031000Z-bbbbbb', p2)
    r1, r2 = GI.evaluator_run_id(e1, p1), GI.evaluator_run_id(e2, p2)
    assert r1 != r2 and r1.startswith('eval-t__x__large') and GI.sha(p1)[:16] in r1
    e3 = episode(e1['run_id'], p2)                                      # same episode id, different patch -> different id too
    assert GI.evaluator_run_id(e3, p2) != r1
    with pytest.raises(GI.GradeRefused):
        GI.evaluator_run_id(dict(e1, run_id=None), p1)                  # pre-wc2 episodes have no immutable id


def test_eligibility_refuses_non_submitted_empty_hash_or_image_mismatch():
    p = 'diff --git a/x b/x\n+1\n'
    GI.eligibility(episode('r', p), p, IMG)
    for ep, sub, img in ((episode('r', p, exit_status='LimitsExceeded'), p, IMG), (episode('r', ''), '', IMG),
                         (episode('r', p), p + 'tampered', IMG), (episode('r', p), p, 'sha256:' + 'd' * 64)):
        with pytest.raises(GI.GradeRefused):
            GI.eligibility(ep, sub, img)


def test_preflight_and_report_acceptance_reject_stale_or_mismatched_reports(tmp_path):
    p = 'diff --git a/x b/x\n+1\n'
    preds, logs, grade = tmp_path / 'r.preds.json', tmp_path / 'logs/run', tmp_path / 'grade.json'
    GI.preflight(preds, logs, grade)
    for existing in (preds, grade):
        existing.write_text('{}')
        with pytest.raises(GI.GradeRefused):
            GI.preflight(preds, logs, grade)
        existing.unlink()
    logs.mkdir(parents=True)
    with pytest.raises(GI.GradeRefused):
        GI.preflight(preds, logs, grade)                                # an existing harness run dir (cached report) is refused
    d = tmp_path / 'inst'; d.mkdir()
    (d / 'patch.diff').write_text('diff --git a/x b/x\n+OTHER\n'); (d / 'report.json').write_text(json.dumps({'t__x': {'resolved': True}}))
    with pytest.raises(GI.GradeRefused):
        GI.accept_report(d, 't__x', p)                                  # stale report for a different patch
    (d / 'patch.diff').write_text(p)
    assert GI.accept_report(d, 't__x', p)['t__x']['resolved'] is True
    with pytest.raises(GI.GradeRefused):
        GI.accept_report(d, 'other__y', p)


def fake_qualify(calls):
    def q(iid, attempt_dir, stock_run_id):
        calls.append((iid, attempt_dir.name, stock_run_id))
        return dict(instance_id=iid, qualified=True, acceptance=dict(ok=True))
    return q


def test_interrupted_and_resumed_queue_preserves_finished_and_retains_incomplete(tmp_path):
    out = tmp_path / 'out'; out.mkdir()
    (out / 'a__1').mkdir(); (out / 'a__1' / 'summary.json').write_text(json.dumps(dict(instance_id='a__1', qualified=True)) + '\n')
    finished_sha = hashlib.sha256((out / 'a__1' / 'summary.json').read_bytes()).hexdigest()
    (out / 'b__2').mkdir(); (out / 'b__2' / 'stock_stdout_tail.txt').write_text('interrupted')    # incomplete prior attempt
    calls, status = [], {}
    QB.run_queue(['a__1', 'b__2', 'c__3'], out, fake_qualify(calls), status, stamp=lambda: '20260922T040000Z')
    assert [c[0] for c in calls] == ['b__2', 'c__3']                      # no duplicate finished control
    assert status['skipped_completed'] == [dict(instance_id='a__1', summary='a__1/summary.json', sha256=finished_sha)]
    assert hashlib.sha256((out / 'a__1' / 'summary.json').read_bytes()).hexdigest() == finished_sha
    assert (out / 'b__2' / 'stock_stdout_tail.txt').read_text() == 'interrupted'           # incomplete state retained
    assert (out / 'b__2' / 'attempt-20260922T040000Z' / 'summary.json').exists()
    assert calls[0][2] == 'qual-stock-gold-20260922T040000Z' and calls[1][2] == QB.STOCK_RUN_ID   # fresh stock id on resume
    assert status['incomplete_prior_attempts'] == [dict(instance_id='b__2', retained='b__2')]
    calls2, status2 = [], {}
    QB.run_queue(['a__1', 'b__2', 'c__3'], out, fake_qualify(calls2), status2)             # second resume: nothing reruns
    assert calls2 == [] and len(status2['skipped_completed']) == 3


def test_conflicting_metadata_fails_explicitly_and_pause_stops_before_execution(tmp_path):
    out = tmp_path / 'out'; out.mkdir()
    (out / 'a__1').mkdir(); (out / 'a__1' / 'summary.json').write_text(json.dumps(dict(instance_id='WRONG')))
    with pytest.raises(QB.ConflictingRecord):
        QB.run_queue(['a__1'], out, fake_qualify([]), {})
    (out / 'a__1' / 'summary.json').write_text('{not json')
    with pytest.raises(QB.ConflictingRecord):
        QB.run_queue(['a__1'], out, fake_qualify([]), {})
    pause = tmp_path / 'PAUSE'; pause.write_text('')
    calls, status = [], {}
    QB.run_queue(['z__9'], out, fake_qualify(calls), status, pause=pause)
    assert calls == [] and 'paused before z__9' in status['stopped'] and not (out / 'z__9').exists()
