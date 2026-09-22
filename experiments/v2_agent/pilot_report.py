"""Finite descriptive DEV report for every frozen task/backend assignment.

Pending, ungraded and invalid records remain explicit. Completion bounds are not
confidence intervals. Algorithmic bounds concern integrity-valid Submitted,
nonempty artifacts only; non-submissions are not algorithmic failures. Usage
totals require complete telemetry, otherwise only known subtotals are reported.
"""
from __future__ import annotations
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRAME = ROOT / 'results/v2_agent/pilot_frame_20260922.json'
OUT = ROOT / 'results/v2_agent/pilot_20260922'
TEST_RE = re.compile(r'\b(pytest|py\.test|unittest|runtests|tox|nosetests|nose|manage\.py\s+test)\b')
EDIT_RE = re.compile(r"(sed\s+-i|\bpatch\b|git\s+apply|\btee\b|cat\s+>|cat\s+<<|>\s*[\w./-]+\.(py|txt|cfg|toml|rst|ini))")
METRICS = ('logical_calls', 'physical_requests', 'failed_attempts', 'prompt_tokens', 'completion_tokens', 'wall_seconds')


class ReportIntegrityError(ValueError):
    pass


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except (ValueError, OSError) as exc:
        raise ReportIntegrityError('cannot read %s: %s' % (path, exc)) from exc


def visible_before_call(messages, k=9):
    """Legacy display helper; assistant ordinals do NOT identify logical calls."""
    n, vis = 0, []
    for message in messages:
        if message.get('role') == 'assistant':
            n += 1
            if n == k:
                return vis
        vis.append(message)
    return None


def feedback_features(visible):
    obs = [m for m in visible if m.get('role') in ('user', 'tool')
           and isinstance(m.get('extra'), dict) and 'returncode' in m['extra']]
    cmds = [a.get('command', '') for m in visible if m.get('role') == 'assistant'
            for a in ((m.get('extra') or {}).get('actions') or []) if isinstance(a, dict)]
    text = json.dumps([dict(role=m.get('role'), content=m.get('content')) for m in visible], sort_keys=True)
    return dict(observations=len(obs), nonzero_returncodes=sum(m['extra'].get('returncode') not in (0, '0') for m in obs),
                test_command_pattern_seen=any(TEST_RE.search(c or '') for c in cmds),
                edit_command_pattern_seen=any(EDIT_RE.search(c or '') for c in cmds),
                history_sha256=hashlib.sha256(text.encode()).hexdigest())


def attempt_telemetry(directory, episode):
    """Prefer durable start/result records; never assign zero tokens to a failed request."""
    values = {k: episode.get('n_model_calls' if k == 'logical_calls' else k) for k in METRICS}
    subtotals = {k: values[k] for k in METRICS}
    for metric in ('prompt_tokens', 'completion_tokens'):
        if values[metric] is None:
            subtotals[metric] = episode.get('known_' + metric)
    detail = dict(source='episode_record', unresolved_attempts=None,
                  prompt_tokens_missing_attempts=None, completion_tokens_missing_attempts=None)
    path = directory / 'attempts.jsonl'
    starts, results = {}, {}
    if path.exists():
        try:
            records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        except ValueError as exc:
            raise ReportIntegrityError('invalid attempt ledger: %s' % path) from exc
        for record in records:
            if record.get('event') not in ('start', 'result'):
                raise ReportIntegrityError('attempt ledger requires durable start/result events: %s' % path)
            key = (record.get('call'), record.get('attempt'))
            if any(type(n) is not int or n < 1 for n in key):
                raise ReportIntegrityError('invalid logical call/attempt in %s' % path)
            target = starts if record['event'] == 'start' else results
            if key in target:
                raise ReportIntegrityError('duplicate %s event in %s' % (record['event'], path))
            target[key] = record
        if not results.keys() <= starts.keys():
            raise ReportIntegrityError('attempt result without durable start: %s' % path)
        if starts and sorted({k[0] for k in starts}) != list(range(1, max(k[0] for k in starts) + 1)):
            raise ReportIntegrityError('noncontiguous dispatched logical calls: %s' % path)
        detail.update(source='durable_attempt_ledger', unresolved_attempts=len(starts.keys() - results.keys()))
        if values['logical_calls'] is None:
            subtotals['logical_calls'] = len({call for call, _ in starts})
        values['physical_requests'] = subtotals['physical_requests'] = len(starts)
        failures = sum(result.get('ok') is False for result in results.values())
        subtotals['failed_attempts'] = failures
        values['failed_attempts'] = failures if not detail['unresolved_attempts'] else None
        for metric in ('prompt_tokens', 'completion_tokens'):
            known = [results[k][metric] for k in starts if k in results and results[k].get('ok') is True
                     and isinstance(results[k].get(metric), (int, float)) and results[k][metric] >= 0]
            detail[metric + '_missing_attempts'] = len(starts) - len(known)
            subtotals[metric] = sum(known)
            values[metric] = sum(known) if len(known) == len(starts) else None
        issued = any(call >= 9 for call, _ in starts)
        max_attempts = max((sum(call == k[0] for k in starts) for call, _ in starts), default=0)
    else:
        issued = None if values['logical_calls'] is None else values['logical_calls'] >= 9
        max_attempts = episode.get('max_attempts_on_one_call')
        # Older summaries sum successful responses. Failed-request usage is unknown.
        if episode.get('failed_attempts'):
            for metric in ('prompt_tokens', 'completion_tokens'):
                values[metric] = None
                detail[metric + '_missing_attempts'] = episode['failed_attempts']
    return values, subtotals, detail, issued, max_attempts


def episode_summary(directory, expected=None):
    directory = Path(directory)
    ep = read_json(directory / 'episode.json')
    expected = expected or dict(instance_id=ep.get('instance_id'), backend=ep.get('backend'))
    if any(ep.get(k) != expected[k] for k in ('instance_id', 'backend')) or ep.get('run_id') != directory.name or not ep.get('exit_status'):
        raise ReportIntegrityError('episode identity/terminal status disagrees with assignment: %s' % directory)
    if expected.get('image') and (ep.get('pins') or {}).get('image_id') != expected['image']:
        raise ReportIntegrityError('episode image disagrees with frozen assignment: %s' % directory)
    patch = directory / 'submission.diff'
    if not patch.exists():
        raise ReportIntegrityError('terminal episode has no submission artifact: %s' % directory)
    raw = patch.read_bytes()
    actual_sha = hashlib.sha256(raw).hexdigest()
    patch_matches = actual_sha == ep.get('submission_sha256')
    if not patch_matches:
        raise ReportIntegrityError('submission artifact disagrees with episode hash: %s' % directory)
    grade_path = directory / 'grade.json'
    grade = read_json(grade_path) if grade_path.exists() else None
    if grade_path.exists():
        required = {'classification', 'grade_valid', 'operational_resolved', 'algorithmic_correctness'}
        if not isinstance(grade, dict) or not required <= grade.keys():
            raise ReportIntegrityError('existing grade is not a complete grade object: %s' % grade_path)
        identities = dict(instance_id=ep['instance_id'], backend=ep['backend'], episode_run_id=ep['run_id'], submission_sha256=actual_sha)
        if any(grade.get(k) != value for k, value in identities.items()):
            raise ReportIntegrityError('grade identity/hash disagrees with episode: %s' % grade_path)
        if grade.get('grade_valid') is True:
            if grade.get('classification') not in ('evaluated', 'operational_zero', 'unknown_evaluator_failure'):
                raise ReportIntegrityError('valid grade has an unknown classification: %s' % grade_path)
            if not patch_matches or grade.get('operational_resolved') not in (0, 1):
                raise ReportIntegrityError('valid grade has mismatched artifact or missing binary outcome: %s' % grade_path)
            if ep['exit_status'] == 'Submitted' and raw.strip() and grade.get('image_id') != (ep.get('pins') or {}).get('image_id'):
                raise ReportIntegrityError('valid grade image disagrees with episode: %s' % grade_path)
        elif grade.get('classification') != 'integrity_refusal' or grade.get('grade_valid') is not False:
            raise ReportIntegrityError('invalid grade must remain an explicit integrity refusal: %s' % grade_path)
    values, subtotals, telemetry, issued, max_attempts = attempt_telemetry(directory, ep)
    trajectory = read_json(directory / 'trajectory.json') if (directory / 'trajectory.json').exists() else None
    completed = None if trajectory is None else sum(m.get('role') == 'assistant' for m in trajectory.get('messages', []))
    feedback = None
    snapshot = directory / 'call9_history.json'
    if issued is True and snapshot.exists():
        snap = read_json(snapshot)
        if snap.get('call') != 9 or not isinstance(snap.get('messages'), list):
            raise ReportIntegrityError('invalid pre-call-9 snapshot: %s' % snapshot)
        feedback = feedback_features(snap['messages'])
    cls = grade['classification'] if grade else ('artifact_integrity_failure' if not patch_matches else 'ungraded')
    valid = (grade or {}).get('grade_valid')
    # An evaluator integrity refusal does not invalidate an intact local candidate.
    eligible = ep['exit_status'] == 'Submitted' and bool(raw.strip()) and patch_matches
    return dict(instance_id=ep['instance_id'], backend=ep['backend'], run_id=ep['run_id'], state='terminal',
                exit_status=ep['exit_status'], nonempty_patch=ep['exit_status'] == 'Submitted' and bool(raw.strip()),
                submission_hash_matches=patch_matches, classification=cls, grade_valid=valid,
                operational_resolved=(grade or {}).get('operational_resolved') if valid is True else None,
                algorithmic_correctness=(grade or {}).get('algorithmic_correctness') if valid is True else None,
                algorithmic_eligible=eligible,
                call9_eligible=issued, call9_eligibility_source=telemetry['source'], call9_feedback=feedback,
                completed_assistant_messages=completed, max_attempts_on_one_call=max_attempts,
                known_subtotals=subtotals, telemetry=telemetry, infrastructure_suspect=bool(ep.get('infrastructure_suspect')), **values)


def incomplete_evidence(directory):
    """Observed usage in an unfinished run is a subtotal, never its final cost."""
    _, subtotals, detail, issued, maximum = attempt_telemetry(directory, {})
    feedback = None
    snapshot = directory / 'call9_history.json'
    if issued is True and snapshot.exists():
        record = read_json(snapshot)
        if record.get('call') != 9 or not isinstance(record.get('messages'), list):
            raise ReportIntegrityError('invalid pre-call-9 snapshot: %s' % snapshot)
        feedback = feedback_features(record['messages'])
    return dict(run_id=directory.name, known_subtotals=subtotals, telemetry=detail,
                call9_eligible=True if issued is True else None, call9_feedback=feedback,
                known_max_attempts_on_one_call=maximum)


def collect(frame, out):
    assigned, rows, missing = [], [], []
    for task in sorted(frame['pilot']['tasks'], key=lambda t: t['position']):
        if sorted(task['backend_order']) != ['large', 'small']:
            raise ReportIntegrityError('frozen task must assign exactly one small and one large episode')
        for backend in task['backend_order']:
            key = (task['instance_id'], backend)
            if key in assigned:
                raise ReportIntegrityError('duplicate frozen assignment: %s/%s' % key)
            assigned.append(key)
            directories = sorted(d for d in Path(out).glob('%s__%s__*' % key) if d.is_dir())
            terminal = [d for d in directories if (d / 'episode.json').exists()]
            if len(terminal) > 1:
                raise ReportIntegrityError('two terminal episodes for %s/%s' % key)
            if terminal:
                row = episode_summary(terminal[0], dict(instance_id=key[0], backend=key[1], image=task.get('instance_image')))
                row['retained_incomplete_run_dirs'] = [d.name for d in directories if d not in terminal]
                row['incomplete_attempt_evidence'] = [incomplete_evidence(d) for d in directories if d not in terminal]
                rows.append(row)
            else:
                pending = dict(instance_id=key[0], backend=key[1], state='incomplete' if directories else 'unstarted',
                               retained_run_dirs=[d.name for d in directories])
                missing.append(pending)
                evidence = [incomplete_evidence(d) for d in directories]
                # Never merge ambiguous histories or costs from separate partial runs.
                single = evidence[0] if len(evidence) == 1 else {}
                rows.append(dict(pending, classification=pending['state'], grade_valid=None, operational_resolved=None,
                                 algorithmic_correctness=None, algorithmic_eligible=False,
                                 call9_eligible=single.get('call9_eligible'), call9_feedback=single.get('call9_feedback'),
                                 incomplete_attempt_evidence=evidence, nonempty_patch=None,
                                 known_subtotals=single.get('known_subtotals', {}), **{k: None for k in METRICS}))
    return assigned, rows, missing


def count_by(rows, key):
    result = {}
    for row in rows:
        value = row.get(key)
        result[value] = result.get(value, 0) + 1
    return result


def metric_summary(rows, metric):
    known = [r[metric] for r in rows if r[metric] is not None]
    subtotal = sum(r.get('known_subtotals', {}).get(metric) or 0 for r in rows)
    return dict(total=sum(known) if len(known) == len(rows) else None,
                known_subtotal=subtotal, complete_episode_count=len(known),
                missing_or_partial_episode_count=len(rows) - len(known), assigned_episode_count=len(rows))


def backend_table(rows, backend):
    assigned = [r for r in rows if r['backend'] == backend]
    terminal = [r for r in assigned if r['state'] == 'terminal']
    valid = [r for r in terminal if r['grade_valid'] is True]
    resolved = sum(r['operational_resolved'] == 1 for r in valid)
    unknown = len(assigned) - len(valid)
    algorithmic = [r for r in terminal if r['algorithmic_eligible']]
    a_res = sum(r['algorithmic_correctness'] == 'resolved' for r in algorithmic)
    a_known = sum(r['algorithmic_correctness'] in ('resolved', 'unresolved') for r in algorithmic)
    eligible = [r for r in assigned if r['call9_eligible'] is True]
    feedback = [r['call9_feedback'] for r in eligible if r['call9_feedback'] is not None]
    costs = {metric: metric_summary(assigned, metric) for metric in METRICS}
    maxima = [r.get('max_attempts_on_one_call') for r in assigned]
    return dict(assigned=len(assigned), terminal=len(terminal), exit_status=count_by(terminal, 'exit_status'),
                classification=count_by(assigned, 'classification'), valid_grades=len(valid),
                submitted=sum(r['exit_status'] == 'Submitted' for r in terminal),
                nonempty_patch=sum(r['nonempty_patch'] for r in terminal),
                submitted_and_patch_denominators=dict(assigned=len(assigned), observed_terminal=len(terminal), pending=len(assigned)-len(terminal)),
                operational_resolved=resolved,
                operational_completion_bounds=dict(kind='finite assignment completion bounds, not confidence intervals',
                                                   denominator=len(assigned), low=resolved, high=resolved+unknown, unknown=unknown),
                algorithmic_bounds=dict(kind='finite completion bounds, not confidence intervals',
                                        target='integrity-valid Submitted nonempty artifacts only', denominator=len(algorithmic),
                                        low=a_res, high=a_res+len(algorithmic)-a_known, unknown=len(algorithmic)-a_known),
                integrity_refusals=sum(r['classification'] in ('integrity_refusal', 'artifact_integrity_failure') for r in terminal),
                infrastructure_suspect=sum(r.get('infrastructure_suspect', False) for r in terminal),
                call9_eligible=len(eligible), call9_eligibility_unknown=sum(r['call9_eligible'] is None for r in assigned),
                call9_feedback_known=len(feedback), call9_feedback_unknown=len(eligible)-len(feedback),
                call9_distinct_histories=len({f['history_sha256'] for f in feedback}),
                call9_test_command_pattern_seen=sum(f['test_command_pattern_seen'] for f in feedback),
                call9_edit_command_pattern_seen=sum(f['edit_command_pattern_seen'] for f in feedback),
                call9_nonzero_returncodes=sum(f['nonzero_returncodes'] for f in feedback),
                max_attempts_on_one_call=max(maxima) if maxima and all(x is not None for x in maxima) else None,
                known_max_attempts_on_one_call=max((x for x in maxima if x is not None), default=None),
                cost_scope='episode telemetry only; includes a single incomplete run as known subtotals; excludes serving/preflight/evaluator overhead; multiple retained runs are listed separately, not merged',
                costs=costs, **{metric: summary['total'] for metric, summary in costs.items()})


def paired(rows):
    by = {}
    for row in rows:
        by.setdefault(row['instance_id'], {})[row['backend']] = row
    cells, per_task = {'1,1': 0, '1,0': 0, '0,1': 0, '0,0': 0}, []
    for iid, models in by.items():
        small, large = models.get('small'), models.get('large')
        if small is None or large is None:
            raise ReportIntegrityError('frozen paired task lacks a backend assignment: %s' % iid)
        both = small['grade_valid'] is True and large['grade_valid'] is True
        costs = {metric: (large[metric] - small[metric] if large[metric] is not None and small[metric] is not None else None)
                 for metric in METRICS}
        per_task.append(dict(instance_id=iid, small=small['operational_resolved'], large=large['operational_resolved'],
                             small_state=small['state'], large_state=large['state'],
                             small_classification=small['classification'], large_classification=large['classification'], both_valid=both,
                             operational_difference_large_minus_small=large['operational_resolved']-small['operational_resolved'] if both else None,
                             cost_differences_large_minus_small=costs))
        if both:
            cells['%d,%d' % (small['operational_resolved'], large['operational_resolved'])] += 1
    differences = {metric: dict(known_pair_count=sum(r['cost_differences_large_minus_small'][metric] is not None for r in per_task),
                               missing_pair_count=sum(r['cost_differences_large_minus_small'][metric] is None for r in per_task),
                               known_pair_sum_large_minus_small=sum(r['cost_differences_large_minus_small'][metric] or 0 for r in per_task))
                   for metric in METRICS}
    return dict(assigned_pairs=len(per_task), cells_small_large=cells, pairs_with_both_valid=sum(cells.values()), per_task=per_task,
                operational_difference_sum_on_valid_pairs=cells['0,1']-cells['1,0'], paired_cost_differences=differences)


def report(frame, out):
    assigned, rows, missing = collect(frame, out)
    backends = {backend: backend_table(rows, backend) for backend in ('small', 'large')}
    bounds = [b['operational_completion_bounds'] for b in backends.values()]
    return dict(request='DTR-REQ-002', kind='fixed-backend DEVELOPMENT pilot, descriptive only (no efficacy, precision or routing claim)',
                frame_content_sha256=hashlib.sha256(json.dumps(frame, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                assigned=len(assigned), terminal=sum(r['state'] == 'terminal' for r in rows), not_terminal=missing,
                operational_completion_bounds=dict(kind='finite assignment completion bounds, not confidence intervals',
                                                   denominator=len(assigned), **{k: sum(b[k] for b in bounds) for k in ('low', 'high', 'unknown')}),
                backends=backends, paired=paired(rows), episodes=rows)


def main():
    rep = report(read_json(FRAME), OUT)
    dst = OUT / ('report_%s.json' % (sys.argv[1] if len(sys.argv) > 1 else 'current'))
    with open(dst, 'x') as fh:
        fh.write(json.dumps(rep, indent=1) + '\n')
    print(json.dumps({k: rep[k] for k in ('assigned', 'terminal')}), json.dumps(rep['paired']['cells_small_large']))


if __name__ == '__main__':
    main()
