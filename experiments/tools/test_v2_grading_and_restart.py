"""Deterministic acceptance fixtures for the lead's grading and restart repairs (e360831, extended in fd5f42c). No model,
container or harness: the evaluator is mocked through grade_flow's run_harness callback.
Grading: distinct episodes/patches never share outputs; genuine operational zeros stay valid zeros; hash/image
integrity refusals are grade_valid=false with an unknown grade; a pre-container evaluator failure leaves a durable
unknown record; an identical-patch retry uses a distinct attempt ID and cannot consume stale logs; nothing is
overwritten. Restart/frame: ID-only and running records stay incomplete; wrong source conflicts before execution;
valid terminal successes AND failures are skipped with hashes preserved; legacy records bind by immutable hash."""
import hashlib, json, sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_agent'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_adapter'))
import grade_identity as GI  # noqa: E402
import qualification_batch as QB  # noqa: E402

IMG = 'sha256:' + 'c' * 64
P1, P2 = 'diff --git a/x b/x\n+1\n', 'diff --git a/x b/x\n+2\n'


def episode(run_id, patch, exit_status='Submitted', image=IMG, iid='t__x'):
    return dict(instance_id=iid, backend='large', run_id=run_id, exit_status=exit_status, submission_sha256=GI.sha(patch),
                pins=dict(image_id=image))


def harness(behaviour):
    """behaviour: list per call of 'pre_container' | 'ok' | 'stale' | 'wrong_instance' | 'malformed' | 'null_payload' |
    'list_payload'; writes what the
    pinned evaluator would write."""
    calls = []

    def run(run_id, preds):
        kind = behaviour[len(calls)]
        calls.append((run_id, kind))
        patch = json.loads(Path(preds).read_text())['t__x']['model_patch']
        d = Path(preds).parent / 'logs/run_evaluation' / run_id / 'alias' / 't__x'
        if kind == 'pre_container':
            return dict(returncode=1)                       # failed before the container: no patch.diff, no report
        d.mkdir(parents=True)
        (d / 'patch.diff').write_text('diff --git a/x b/x\n+STALE\n' if kind == 'stale' else patch)
        report = {('o__y' if kind == 'wrong_instance' else 't__x'): {'resolved': True, 'patch_successfully_applied': True}}
        if kind in ('null_payload', 'list_payload'):
            report['t__x'] = None if kind == 'null_payload' else []
        (d / 'report.json').write_text('{"t__x": {"resolved": tr' if kind == 'malformed' else json.dumps(report))
        (d / 'test_output.txt').write_text('log')
        return dict(returncode=0)
    return run, calls


def strict(logd):
    return 'resolved', {'t::a': 'PASSED'}


def test_two_episodes_same_task_backend_different_patches_never_share_outputs(tmp_path):
    e1, e2 = episode('t__x__large__cp2-wc2__20260922T030000Z-aaaaaa', P1), episode('t__x__large__cp2-wc2__20260922T031000Z-bbbbbb', P2)
    r1, r2 = GI.evaluator_run_id(e1, P1), GI.evaluator_run_id(e2, P2)
    assert r1 != r2 and GI.sha(P1)[:16] in r1 and GI.evaluator_run_id(episode(e1['run_id'], P2), P2) != r1
    for e, p, g in ((e1, P1, 'g1.json'), (e2, P2, 'g2.json')):
        run, calls = harness(['ok'])
        out = GI.grade_flow(e, p, IMG, tmp_path, tmp_path / g, run, strict, 'alias')
        assert out['classification'] == 'evaluated' and out['operational_resolved'] == 1
    assert len(list(tmp_path.glob('*.preds.json'))) == 2


def test_operational_zeros_stay_valid_and_integrity_refusals_are_invalid(tmp_path):
    run, calls = harness([])
    z1 = GI.grade_flow(episode('r1', P1, exit_status='LimitsExceeded'), P1, IMG, tmp_path, tmp_path / 'a.json', run, strict, 'alias')
    z2 = GI.grade_flow(episode('r2', ''), '', IMG, tmp_path, tmp_path / 'b.json', run, strict, 'alias')
    assert z1['classification'] == z2['classification'] == 'operational_zero' and z1['grade_valid'] and z1['operational_resolved'] == 0
    h = GI.grade_flow(episode('r3', P1), P1 + 'tampered', IMG, tmp_path, tmp_path / 'c.json', run, strict, 'alias')
    i = GI.grade_flow(episode('r4', P1), P1, 'sha256:' + 'd' * 64, tmp_path, tmp_path / 'd.json', run, strict, 'alias')
    for g in (h, i):
        assert g['classification'] == 'integrity_refusal' and g['grade_valid'] is False and g['operational_resolved'] is None
    assert calls == []                                                   # no evaluator ran for any of these
    for f in ('a', 'b', 'c', 'd'):
        assert json.loads((tmp_path / (f + '.json')).read_text())['classification']       # durable records


def test_pre_container_failure_is_a_durable_unknown_and_retry_uses_a_distinct_attempt(tmp_path):
    run, calls = harness(['pre_container', 'pre_container'])
    g = GI.grade_flow(episode('r5', P1), P1, IMG, tmp_path, tmp_path / 'g.json', run, strict, 'alias')
    assert g['classification'] == 'unknown_evaluator_failure' and g['algorithmic_correctness'] == 'unknown'
    assert g['grade_valid'] is True and g['operational_resolved'] == 0 and 'strict_outcome' not in g
    assert [c[0][-3:] for c in calls] == ['-a1', '-a2'] and len(g['attempts']) == 2          # one retry, distinct IDs
    with pytest.raises((GI.GradeRefused, FileExistsError)):                                 # never overwritten
        GI.grade_flow(episode('r5', P1), P1, IMG, tmp_path, tmp_path / 'g.json', harness(['ok'])[0], strict, 'alias')
    run2, calls2 = harness(['pre_container', 'ok'])
    g2 = GI.grade_flow(episode('r6', P1), P1, IMG, tmp_path, tmp_path / 'g2.json', run2, strict, 'alias')
    assert g2['classification'] == 'evaluated' and [a['status'] for a in g2['attempts']] == ['unknown_evaluator_failure', 'completed']


def test_stale_logs_cannot_be_consumed_and_mismatched_reports_are_integrity_refusals(tmp_path):
    e = episode('r7', P1)
    rid = GI.evaluator_run_id(e, P1)
    (tmp_path / 'logs/run_evaluation' / (rid + '-a1')).mkdir(parents=True)                  # stale attempt-1 output
    with pytest.raises(GI.GradeRefused):
        GI.grade_flow(e, P1, IMG, tmp_path, tmp_path / 's.json', harness(['ok'])[0], strict, 'alias')
    run, calls = harness(['stale'])
    g = GI.grade_flow(episode('r8', P1), P1, IMG, tmp_path, tmp_path / 't.json', run, strict, 'alias')
    assert g['classification'] == 'integrity_refusal' and g['grade_valid'] is False


EXP = dict(manifest_sha256='m' * 64, source_sha256='s' * 64, dataset_sha256='d' * 64, evaluator_commit=QB.EVALUATOR_COMMIT)


def fake_qualify(calls):
    def q(iid, attempt_dir, stock_run_id):
        calls.append((iid, attempt_dir.name, stock_run_id))
        return dict(instance_id=iid, qualified=True, acceptance=dict(ok=True))
    return q


def terminal(iid, **kw):
    return dict(dict(instance_id=iid, qualified=True, acceptance=dict(ok=True), finished_utc='2026-09-22T03:00:00Z', identity=EXP), **kw)


def write(out, iid, rec):
    (out / iid).mkdir(parents=True, exist_ok=True)
    (out / iid / 'summary.json').write_text(json.dumps(rec) + '\n')
    return hashlib.sha256((out / iid / 'summary.json').read_bytes()).hexdigest()


def test_terminal_success_and_failure_are_skipped_but_id_only_and_running_stay_incomplete(tmp_path):
    out = tmp_path / 'out'; out.mkdir()
    h_ok = write(out, 'a__1', terminal('a__1'))
    h_fail = write(out, 'f__2', dict(instance_id='f__2', stage_failed='stock_gold', finished_utc='x', identity=EXP))
    write(out, 'i__3', dict(instance_id='i__3', qualified=True))                         # matching ID only
    write(out, 'r__4', terminal('r__4', status='running'))                               # running record
    calls, status = [], {}
    QB.run_queue(['a__1', 'f__2', 'i__3', 'r__4'], out, fake_qualify(calls), status, expected=EXP, stamp=lambda: 'T1')
    assert [c[0] for c in calls] == ['i__3', 'r__4']                                     # successes/failures not rerun
    assert {s['instance_id']: s['sha256'] for s in status['skipped_completed']} == {'a__1': h_ok, 'f__2': h_fail}
    assert sorted(x['instance_id'] for x in status['incomplete_prior_attempts']) == ['i__3', 'r__4']
    assert (out / 'i__3' / 'summary.json').exists() and (out / 'i__3' / 'attempt-T1' / 'summary.json').exists()
    new = json.loads((out / 'i__3' / 'attempt-T1' / 'summary.json').read_text())
    assert new['identity'] == EXP and QB.is_terminal(new)


def test_wrong_source_conflicts_before_any_execution(tmp_path):
    out = tmp_path / 'out'; out.mkdir()
    write(out, 'w__1', terminal('w__1', identity=dict(EXP, source_sha256='x' * 64)))
    write(out, 'e__2', dict(instance_id='e__2', qualified=True, acceptance={}, finished_utc='x', platform=dict(evaluator_commit='deadbeef')))
    for iid in ('w__1', 'e__2'):
        calls = []
        with pytest.raises(QB.ConflictingRecord):
            QB.run_queue([iid], out, fake_qualify(calls), {}, expected=EXP)
        assert calls == []
    (out / 'u__3').mkdir(); (out / 'u__3' / 'summary.json').write_text('{not json')
    with pytest.raises(QB.ConflictingRecord):
        QB.run_queue(['u__3'], out, fake_qualify([]), {}, expected=EXP)


def test_legacy_records_bind_by_immutable_hash_without_rewriting(tmp_path):
    out = tmp_path / 'out'; out.mkdir()
    legacy = dict(instance_id='l__1', qualified=False, acceptance=dict(ok=False), finished_utc='x', platform=dict(evaluator_commit=QB.EVALUATOR_COMMIT))
    h = write(out, 'l__1', legacy)
    calls = []
    with pytest.raises(QB.ConflictingRecord):                                               # unbound terminal: reconcile,
        QB.run_queue(['n__0', 'l__1'], out, fake_qualify(calls), {}, expected=EXP)           # never rerun (lead 7cb2062)
    assert calls == [] and not (out / 'n__0').exists()                                       # zero executions, even for new
    out2 = tmp_path / 'out2'; out2.mkdir()
    write(out2, 'l__1', legacy)
    man = QB.build_legacy_manifest(out2, EXP)
    assert man['records'] == [dict(instance_id='l__1', summary='l__1/summary.json', sha256=h, terminal='verdict', qualified=False)]
    for stale in (dict(EXP, source_sha256='x' * 64), dict(EXP, manifest_sha256='y' * 64)):      # hash matches, identity stale
        calls0 = []
        with pytest.raises(QB.ConflictingRecord):
            QB.run_queue(['n__0', 'l__1'], out2, fake_qualify(calls0), {}, expected=EXP, legacy=dict(man, expected_identity=stale))
        assert calls0 == []
    calls2, status = [], {}
    QB.run_queue(['l__1'], out2, fake_qualify(calls2), status, expected=EXP, legacy=man)
    assert calls2 == [] and status['skipped_completed'][0]['sha256'] == h
    assert hashlib.sha256((out2 / 'l__1' / 'summary.json').read_bytes()).hexdigest() == h   # not rewritten
    with pytest.raises(FileExistsError):
        QB.build_legacy_manifest(out2, EXP)                                                  # immutable


def test_wrong_instance_and_malformed_reports_leave_durable_classified_records(tmp_path):
    """lead 7cb2062 case 1: a report keyed to another instance or a non-object payload is integrity-invalid/null; malformed JSON is an
    evaluator-unknown attempt followed by at most one identical-patch retry; raw diagnostics kept; nothing overwritten."""
    run, calls = harness(['wrong_instance'])
    g = GI.grade_flow(episode('w1', P1), P1, IMG, tmp_path, tmp_path / 'w.json', run, strict, 'alias')
    assert g['classification'] == 'integrity_refusal' and g['grade_valid'] is False and g['operational_resolved'] is None
    assert len(calls) == 1 and 'report.json' in g['attempts'][0]['raw'] and 'patch.diff' in g['attempts'][0]['raw']
    for kind in ('null_payload', 'list_payload'):
        run, calls = harness([kind])
        grade_path = tmp_path / (kind + '.json')
        invalid = GI.grade_flow(episode(kind, P1), P1, IMG, tmp_path, grade_path, run,
                                lambda _: pytest.fail('invalid payload reached strict grading'), 'alias')
        assert invalid['classification'] == 'integrity_refusal' and invalid['grade_valid'] is False
        assert invalid['operational_resolved'] is None and invalid['algorithmic_correctness'] is None
        assert len(calls) == len(invalid['attempts']) == 1 and 'report.json' in invalid['attempts'][0]['raw']
        assert json.loads(grade_path.read_text()) == invalid                              # durable, no retry
    run, calls = harness(['malformed', 'malformed'])
    m = GI.grade_flow(episode('m1', P1), P1, IMG, tmp_path, tmp_path / 'm.json', run, strict, 'alias')
    assert m['classification'] == 'unknown_evaluator_failure' and m['algorithmic_correctness'] == 'unknown'
    assert [c[0][-3:] for c in calls] == ['-a1', '-a2'] and len(calls) == 2                  # one retry, distinct IDs
    assert all(a['raw']['report.json']['bytes'] > 0 for a in m['attempts'])
    run, calls = harness(['malformed', 'ok'])
    r = GI.grade_flow(episode('m2', P1), P1, IMG, tmp_path, tmp_path / 'r.json', run, strict, 'alias')
    assert r['classification'] == 'evaluated' and [a['status'] for a in r['attempts']] == ['unknown_evaluator_failure', 'completed']
    for f in ('w', 'm', 'r'):
        with pytest.raises((GI.GradeRefused, FileExistsError)):
            GI.grade_flow(episode(f + '1', P1), P1, IMG, tmp_path, tmp_path / (f + '.json'), harness(['ok'])[0], strict, 'alias')


def test_hash_is_checked_before_the_empty_zero_decision(tmp_path):
    """lead 7cb2062 case 2: a Submitted record hashing a nonempty patch with an empty saved file is invalid/null;
    a genuine matching-hash empty submission stays a valid zero; neither invokes grading."""
    run, calls = harness([])
    tampered = GI.grade_flow(episode('e1', P1), '', IMG, tmp_path, tmp_path / 't.json', run, strict, 'alias')
    assert tampered['classification'] == 'integrity_refusal' and tampered['grade_valid'] is False
    assert tampered['operational_resolved'] is None and tampered['algorithmic_correctness'] is None
    tampered_ns = GI.grade_flow(episode('e2', P1, exit_status='LimitsExceeded'), '', IMG, tmp_path, tmp_path / 'u.json', run, strict, 'alias')
    assert tampered_ns['classification'] == 'integrity_refusal'
    genuine = GI.grade_flow(episode('e3', ''), '', IMG, tmp_path, tmp_path / 'g.json', run, strict, 'alias')
    assert genuine['classification'] == 'operational_zero' and genuine['grade_valid'] is True and genuine['operational_resolved'] == 0
    assert calls == [] and not list(tmp_path.glob('*.preds.json'))


def test_bound_success_and_failure_are_skipped_and_nonterminal_gets_a_new_attempt_under_a_valid_manifest(tmp_path):
    """lead 7cb2062 case 3, positive side: a manifest with the matching identity admits bound terminal success and
    failure (hashes kept, no controls); a nonterminal record keeps the accepted new-attempt behaviour."""
    out = tmp_path / 'out'; out.mkdir()
    ok = dict(instance_id='s__1', qualified=True, acceptance=dict(ok=True), finished_utc='x', platform=dict(evaluator_commit=QB.EVALUATOR_COMMIT))
    bad = dict(instance_id='d__2', qualified=False, acceptance=dict(ok=False), finished_utc='x')
    h1, h2 = write(out, 's__1', ok), write(out, 'd__2', bad)
    man = QB.build_legacy_manifest(out, EXP)
    write(out, 'i__3', dict(instance_id='i__3', status='running'))
    calls, status = [], {}
    QB.run_queue(['s__1', 'd__2', 'i__3'], out, fake_qualify(calls), status, expected=EXP, legacy=man, stamp=lambda: 'T2')
    assert [c[0] for c in calls] == ['i__3'] and calls[0][1] == 'attempt-T2'
    assert {x['instance_id']: x['sha256'] for x in status['skipped_completed']} == {'s__1': h1, 'd__2': h2}
    assert [hashlib.sha256((out / i / 'summary.json').read_bytes()).hexdigest() for i in ('s__1', 'd__2')] == [h1, h2]
