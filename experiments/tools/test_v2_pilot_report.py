"""Fixtures for the pilot's pre-declared descriptive report: every assigned episode is in the denominator (unstarted and
incomplete are listed, never zeros), integrity refusals are not valid grades, unknown evaluator failures widen only the
algorithmic bounds, call-9 eligibility means the 9th logical call was issued, and the visible pre-call-9 history is
what the features describe. Expected values are written out by hand, not recomputed with the report's code."""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_agent'))
import pilot_report as RP  # noqa: E402

FRAME = dict(pilot=dict(tasks=[dict(position=1, instance_id='a__1', backend_order=['small', 'large']),
                               dict(position=2, instance_id='b__2', backend_order=['large', 'small']),
                               dict(position=3, instance_id='c__3', backend_order=['large', 'small'])]))


def msgs(n_calls, rc=(0,), cmd='ls'):
    m = [dict(role='system', content='s'), dict(role='user', content='task')]
    for i in range(n_calls):
        m.append(dict(role='assistant', content='c%d' % i, extra=dict(actions=[dict(command=cmd if i else 'python -m pytest -q')])))
        m.append(dict(role='user', content='o%d' % i, extra=dict(returncode=rc[i % len(rc)])))
    return m


def ep(out, iid, be, exit_status, n_calls, grade=None, sub_empty=False, rc=(0,), cmd='ls', **kw):
    d = out / ('%s__%s__pilot-cp2-wc2__T-000000' % (iid, be))
    d.mkdir(parents=True)
    (d / 'episode.json').write_text(json.dumps(dict(dict(instance_id=iid, backend=be, run_id=d.name, exit_status=exit_status, n_model_calls=n_calls,
                                                         submission_empty=sub_empty, physical_requests=n_calls + 1, failed_attempts=1,
                                                         max_attempts_on_one_call=2, prompt_tokens=100 * n_calls, completion_tokens=10 * n_calls,
                                                         wall_seconds=60.0), **kw)))
    (d / 'trajectory.json').write_text(json.dumps(dict(messages=msgs(n_calls, rc, cmd))))
    if grade:
        (d / 'grade.json').write_text(json.dumps(grade))


def test_denominator_classifications_bounds_and_pairs(tmp_path):
    out = tmp_path / 'out'
    ev = lambda r: dict(classification='evaluated', grade_valid=True, operational_resolved=r, algorithmic_correctness='resolved' if r else 'unresolved')
    ep(out, 'a__1', 'small', 'Submitted', 12, ev(1), rc=(0, 1), cmd="sed -i 's/a/b/' x.py")
    ep(out, 'a__1', 'large', 'Submitted', 7, ev(0))
    ep(out, 'b__2', 'large', 'LimitsExceeded', 24, dict(classification='operational_zero', grade_valid=True, operational_resolved=0))
    ep(out, 'b__2', 'small', 'Submitted', 9, dict(classification='unknown_evaluator_failure', grade_valid=True, operational_resolved=0,
                                                   algorithmic_correctness='unknown'))
    ep(out, 'c__3', 'large', 'Submitted', 10, dict(classification='integrity_refusal', grade_valid=False, operational_resolved=None))
    (out / 'c__3__small__pilot-cp2-wc2__T-111111').mkdir()                  # interrupted, no terminal record
    rep = RP.report(FRAME, out)
    assert rep['assigned'] == 6 and rep['terminal'] == 5
    assert rep['not_terminal'] == [dict(instance_id='c__3', backend='small', state='incomplete', retained_run_dirs=['c__3__small__pilot-cp2-wc2__T-111111'])]
    s, l = rep['backends']['small'], rep['backends']['large']
    assert s['terminal'] == 2 and s['valid_grades'] == 2 and s['operational_resolved'] == 1 and s['algorithmic_bounds'] == dict(low=1, high=2, unknown=1)
    assert l['terminal'] == 3 and l['valid_grades'] == 2 and l['integrity_refusals'] == 1 and l['operational_resolved'] == 0
    assert s['call9_eligible'] == 2 and l['call9_eligible'] == 2               # 12, 9 | 24, 10 (7 is not)
    assert l['exit_status'] == {'Submitted': 2, 'LimitsExceeded': 1} and l['nonempty_patch'] == 2
    assert s['call9_ran_tests'] == 2 and s['call9_ran_edit'] == 1 and s['call9_nonzero_returncodes'] == 4   # a__1 small: rc 1 on calls 2,4,6,8
    assert rep['paired']['cells_small_large'] == {'1,1': 0, '1,0': 1, '0,1': 0, '0,0': 1}   # c__3 has no valid pair
    assert rep['paired']['pairs_with_both_valid'] == 2


def test_visible_history_stops_before_the_ninth_assistant_message():
    m = msgs(10)
    vis = RP.visible_before_call(m, 9)
    assert sum(x['role'] == 'assistant' for x in vis) == 8 and vis[-1]['content'] == 'o7'
    assert RP.visible_before_call(msgs(8), 9) is None
