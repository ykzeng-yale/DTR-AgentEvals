"""DTR-REQ-002 fixed-backend DEV pilot: descriptive report (spec "report" list). Written and committed BEFORE any pilot
outcome exists; its rules are declared here and not tuned on results.

Denominator: all 16 assigned task/backend episodes of the frozen frame. Each is terminal (episode.json), unstarted,
or incomplete (a run directory with no terminal record); unstarted and incomplete episodes are listed and never
counted as zeros or dropped. Per terminal episode:
  * exit_status as recorded (Submitted, LimitsExceeded, TimeExceeded, RepeatedFormatError, capture failure,
    transport/context exceptions, RunnerHardKill ...); nonempty_patch = Submitted with a nonempty wc2 submission
  * grade classification from grade.json: operational_zero | evaluated | integrity_refusal | unknown_evaluator_failure,
    or 'ungraded' if absent. operational_resolved = 1 only for an evaluated strict 'resolved'. Integrity refusals are
    invalid (excluded from valid-grade counts and listed); unknown evaluator failures are reported separately, with
    the worst-case 0/1 bounds for the secondary algorithmic endpoint
  * call-9 eligibility: active before logical call 9, i.e. the agent issued its 9th logical call (n_model_calls >= 9)
  * visible feedback before call 9 (history the second decision would condition on): observations in calls 1-8,
    nonzero return codes, whether a test command ran (pytest|unittest|runtests|tox|nose|py.test|manage.py test),
    whether an edit command ran (sed -i|patch|git apply|tee|cat >|> file|python -c writes are not detected), and the
    SHA-256 of that visible history, to count distinct histories per backend
  * logical calls, physical requests, failed attempts, max attempts on one call, prompt/completion tokens, wall time
Paired table: per task, (small, large) operational outcome; counts of (1,1), (1,0), (0,1), (0,0) among tasks with both
valid grades; descriptive differences in resolved counts, tokens and wall time. No efficacy, precision or routing claim.
"""
from __future__ import annotations
import hashlib, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRAME = ROOT / 'results/v2_agent/pilot_frame_20260922.json'
OUT = ROOT / 'results/v2_agent/pilot_20260922'
TEST_RE = re.compile(r'\b(pytest|py\.test|unittest|runtests|tox|nosetests|nose|manage\.py\s+test)\b')
EDIT_RE = re.compile(r"(sed\s+-i|\bpatch\b|git\s+apply|\btee\b|cat\s+>|cat\s+<<|>\s*[\w./-]+\.(py|txt|cfg|toml|rst|ini))")


def visible_before_call(messages, k=9):
    """Messages visible when logical call k would be issued: everything before the k-th assistant message."""
    n, vis = 0, []
    for m in messages:
        if m.get('role') == 'assistant':
            n += 1
            if n == k:
                break
        vis.append(m)
    return vis if n >= k else None


def feedback_features(visible):
    obs = [m for m in visible if m.get('role') in ('user', 'tool') and isinstance(m.get('extra'), dict) and 'returncode' in m['extra']]
    cmds = [a.get('command', '') for m in visible if m.get('role') == 'assistant'
            for a in ((m.get('extra') or {}).get('actions') or []) if isinstance(a, dict)]
    text = json.dumps([dict(role=m.get('role'), content=m.get('content')) for m in visible], sort_keys=True)
    return dict(observations=len(obs), nonzero_returncodes=sum(1 for m in obs if m['extra'].get('returncode') not in (0, '0')),
                ran_tests=any(TEST_RE.search(c or '') for c in cmds), ran_edit=any(EDIT_RE.search(c or '') for c in cmds),
                history_sha256=hashlib.sha256(text.encode()).hexdigest())


def episode_summary(d):
    ep = json.loads((d / 'episode.json').read_text())
    g = json.loads((d / 'grade.json').read_text()) if (d / 'grade.json').exists() else None
    traj = json.loads((d / 'trajectory.json').read_text()) if (d / 'trajectory.json').exists() else {'messages': []}
    n_calls = ep.get('n_model_calls') or 0
    vis = visible_before_call(traj.get('messages') or [], 9)
    cls = g['classification'] if g else 'ungraded'
    return dict(instance_id=ep['instance_id'], backend=ep['backend'], run_id=ep['run_id'], exit_status=ep.get('exit_status'),
                nonempty_patch=ep.get('exit_status') == 'Submitted' and not ep.get('submission_empty', True),
                classification=cls, grade_valid=(g or {}).get('grade_valid'), operational_resolved=(g or {}).get('operational_resolved'),
                algorithmic_correctness=(g or {}).get('algorithmic_correctness'),
                call9_eligible=n_calls >= 9, call9_feedback=feedback_features(vis) if vis is not None else None,
                logical_calls=n_calls, physical_requests=ep.get('physical_requests'), failed_attempts=ep.get('failed_attempts'),
                max_attempts_on_one_call=ep.get('max_attempts_on_one_call'), prompt_tokens=ep.get('prompt_tokens'),
                completion_tokens=ep.get('completion_tokens'), wall_seconds=ep.get('wall_seconds'),
                infrastructure_suspect=bool(ep.get('infrastructure_suspect')))


def collect(frame, out):
    assigned, rows, missing = [], [], []
    for t in sorted(frame['pilot']['tasks'], key=lambda t: t['position']):
        for be in t['backend_order']:
            assigned.append((t['instance_id'], be))
            dirs = sorted(d for d in Path(out).glob('%s__%s__*' % (t['instance_id'], be)) if d.is_dir())
            term = [d for d in dirs if (d / 'episode.json').exists()]
            if len(term) > 1:
                raise SystemExit('two terminal episodes for %s/%s' % (t['instance_id'], be))
            if term:
                rows.append(episode_summary(term[0]))
            else:
                missing.append(dict(instance_id=t['instance_id'], backend=be, state='incomplete' if dirs else 'unstarted',
                                    retained_run_dirs=[d.name for d in dirs]))
    return assigned, rows, missing


def backend_table(rows, be):
    r = [x for x in rows if x['backend'] == be]
    ex = {}
    for x in r:
        ex[x['exit_status']] = ex.get(x['exit_status'], 0) + 1
    cl = {}
    for x in r:
        cl[x['classification']] = cl.get(x['classification'], 0) + 1
    valid = [x for x in r if x['grade_valid'] is True]
    unk = sum(x['classification'] == 'unknown_evaluator_failure' for x in r)
    res = sum(x['operational_resolved'] == 1 for x in valid)
    e9 = [x for x in r if x['call9_eligible']]
    s = lambda k: sum(x[k] or 0 for x in r)
    return dict(terminal=len(r), exit_status=ex, submitted=ex.get('Submitted', 0), nonempty_patch=sum(x['nonempty_patch'] for x in r),
                classification=cl, valid_grades=len(valid), operational_resolved=res,
                algorithmic_bounds=dict(low=res, high=res + unk, unknown=unk),
                integrity_refusals=cl.get('integrity_refusal', 0), infrastructure_suspect=sum(x['infrastructure_suspect'] for x in r),
                call9_eligible=len(e9), call9_distinct_histories=len({x['call9_feedback']['history_sha256'] for x in e9}),
                call9_ran_tests=sum(x['call9_feedback']['ran_tests'] for x in e9), call9_ran_edit=sum(x['call9_feedback']['ran_edit'] for x in e9),
                call9_nonzero_returncodes=sum(x['call9_feedback']['nonzero_returncodes'] for x in e9),
                logical_calls=s('logical_calls'), physical_requests=s('physical_requests'), failed_attempts=s('failed_attempts'),
                max_attempts_on_one_call=max([x['max_attempts_on_one_call'] or 0 for x in r] or [0]),
                prompt_tokens=s('prompt_tokens'), completion_tokens=s('completion_tokens'), wall_seconds=round(s('wall_seconds'), 1))


def paired(rows):
    by = {}
    for x in rows:
        by.setdefault(x['instance_id'], {})[x['backend']] = x
    cells, per_task = {'1,1': 0, '1,0': 0, '0,1': 0, '0,0': 0}, []
    for iid, d in by.items():
        s, l = d.get('small'), d.get('large')
        both = s is not None and l is not None and s['grade_valid'] is True and l['grade_valid'] is True
        per_task.append(dict(instance_id=iid, small=None if s is None else s['operational_resolved'], large=None if l is None else l['operational_resolved'],
                             both_valid=both))
        if both:
            cells['%d,%d' % (s['operational_resolved'], l['operational_resolved'])] += 1
    return dict(cells_small_large=cells, pairs_with_both_valid=sum(cells.values()), per_task=per_task)


def report(frame, out):
    assigned, rows, missing = collect(frame, out)
    return dict(request='DTR-REQ-002', kind='fixed-backend DEVELOPMENT pilot, descriptive only (no efficacy, precision or routing claim)',
                assigned=len(assigned), terminal=len(rows), not_terminal=missing,
                backends={be: backend_table(rows, be) for be in ('small', 'large')}, paired=paired(rows), episodes=rows)


def main():
    rep = report(json.loads(FRAME.read_text()), OUT)
    dst = OUT / ('report_%s.json' % (sys.argv[1] if len(sys.argv) > 1 else 'current'))
    with open(dst, 'x') as fh:
        fh.write(json.dumps(rep, indent=1) + '\n')
    print(json.dumps({k: rep[k] for k in ('assigned', 'terminal')}), json.dumps(rep['paired']['cells_small_large']))


if __name__ == '__main__':
    main()
