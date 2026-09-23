"""DTR-REQ-005 'cue-v1' queue skeleton: walks the frozen 12 assignments in their B,C,C,B,B,C pair order and calls an
INJECTED episode function. No live dispatch is wired here.

This skeleton starts no server, container, model, evaluator or network call and imports no runtime SDK. The live
host/server step (serial llama-server ownership, preflight probes, block timing) is out of scope and is held by the
lead (docs/theory_feedback_20260923_req005_review.md: "HOLD only the first live comparison until its integrated
source binding, deadline/transport fixtures, coding guide and current host conditions are reviewed"). The command
line therefore offers only --dry-run and --validate and refuses a live launch.

Declared before any launch (no outcome exists):
  * run_queue refuses unless cue_admission.validate_queue passes for the ENTIRE fixed queue: every bound input
    unchanged since the write-once freeze, the whole hash-chained ledger valid, only runtime state in the namespace,
    no unresolved integrity issue and at least one assignment still unstarted;
  * assignments are dispatched strictly by position; a started assignment is never re-dispatched, replaced or
    repeated, and nothing beyond the 12 is ever dispatched;
  * before each dispatch: the binding is recomputed and compared, the injected host gate and storage preflight are
    asked, and the 576-request cohort total (counted across every earlier session) must leave room for a full 48;
  * the episode function receives the cohort request total counted before it (across every earlier session) and
    its own limit min(48, 576 - that total), plus an AssignmentRequestBudget; cue_transport's cohort RequestBudget
    is built from the same numbers (used=counted_before, limit=counted_before + limit), never reset to 0;
  * the queue stops ONLY on a predeclared stop code (cue_admission.STOP_CODES); no stop reads an episode outcome.
    exit_status is recorded verbatim for accounting and never inspected;
  * an infrastructure stop records the affected assignment and every remaining assignment state explicitly, and no
    further dispatch happens until an explicit reconciliation record exists;
  * the namespace contents (and the ledger head) are re-checked before EVERY dispatch, so a report, projection or
    symlink written into the namespace mid-session stops the queue instead of riding along;
  * in the real checkout the only admitted episode function is the bound cue_episode.run_assignment, whose source
    must be the frozen bytes; an in-process fixture function is admitted only in a disposable copy (fixture=True),
    and the session records which one it dispatched.

  .venv/bin/python experiments/v2_agent/cue_runner.py --dry-run     # list the frozen 12; creates/writes nothing
  .venv/bin/python experiments/v2_agent/cue_runner.py --validate    # read-only admission report
"""
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cue_admission as A  # noqa: E402

SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
LIVE_HELD = ('live launch refused: the cue-v1 live release is held by the lead '
             '(docs/theory_feedback_20260923_req005_review.md). This skeleton starts no server, container or model '
             'and has no episode function wired; use --dry-run or --validate.')
DETAIL_CHARS = 300


def _run_id(assignment_id, clock, token):
    return '%s__run-%s-%s' % (assignment_id, time.strftime('%Y%m%dT%H%M%SZ', time.gmtime(clock())), token())


def _stop(session, code, reason, affected=()):
    ledger = session.ledger
    return session.append('queue_stop', session=ledger.open_session, stop_id='stop-%d' % (ledger.seq + 1), code=code,
                          kind=A.STOP_CODES[code], reason=reason, outcome_driven=False,
                          next_position=ledger.next_position(), affected=[ledger.row(p) for p in affected],
                          remaining=ledger.unstarted(), assignment_states=ledger.snapshot(),
                          counted_physical_requests=ledger.counted_total())


def episode_function_label(episode_fn, layout, binding, *, fixture):
    """The label the ledger records for the dispatched episode function, or AdmissionRefused.

    Real checkout: only cue_episode.run_assignment, loaded from the bound cue_episode.py bytes. A disposable copy of
    the bound inputs may dispatch an in-process fixture function, and only when the caller says fixture=True."""
    real_checkout = layout.root.resolve() == A.ROOT.resolve()
    if fixture:
        if real_checkout:
            raise A.AdmissionRefused(['a fixture episode function is never dispatched from the real checkout'])
        return 'fixture:%s' % getattr(episode_fn, '__qualname__', type(episode_fn).__name__)
    module = sys.modules.get(getattr(episode_fn, '__module__', None) or '')
    source = getattr(module, '__file__', None)
    if (getattr(episode_fn, '__name__', None) != 'run_assignment' or source is None
            or Path(source).resolve() != (layout.module_dir / 'cue_episode.py').resolve()
            or hashlib.sha256(Path(source).read_bytes()).hexdigest() != binding['modules'].get('cue_episode.py')):
        raise A.AdmissionRefused(['the episode function is not the bound cue_episode.run_assignment of %s'
                                  % A.MODULE_DIR_REL])
    return 'cue_episode.run_assignment'


def _end_assignment(session, row, run_id, record, budget):
    """Record the episode's end. Returns the stop code this end requires, or None. Never reads exit_status."""
    position, assignment_id = row['position'], row['assignment_id']
    if not isinstance(record, dict) or record.get('run_id', run_id) != run_id:
        session.append('assignment_error', session=session.ledger.open_session, position=position,
                       assignment_id=assignment_id, run_id=run_id, error_class='EpisodeRecordInvalid',
                       detail='the episode function returned %s' % ('a record naming another run id'
                                                                    if isinstance(record, dict) else
                                                                    type(record).__name__),
                       counted_requests=session.ledger.per_assignment, run_dir_created=True)
        return 'episode_function_error', 'the episode function returned no valid terminal record'
    reported, raw, counted, accounting = A.account_requests(record.get('physical_requests'), budget.consumed,
                                                            session.ledger.per_assignment)
    storage = record.get('storage_integrity')
    detail = record.get('storage_integrity_detail')
    if storage != A.STORAGE_RESOLVED:
        detail = detail if isinstance(detail, str) and detail else (
            'missing or unrecognized storage_integrity %r; treated as unresolved' % (storage,))
        storage = A.STORAGE_UNRESOLVED
    exit_status = record.get('exit_status')
    session.append('assignment_terminal', session=session.ledger.open_session, position=position,
                   assignment_id=assignment_id, run_id=run_id, physical_requests_reported=reported,
                   physical_requests_reported_raw=raw, budget_consumed=budget.consumed, counted_requests=counted,
                   request_accounting=accounting, storage_integrity=storage,
                   storage_integrity_detail=None if detail is None else str(detail)[:DETAIL_CHARS],
                   exit_status=None if exit_status is None else str(exit_status)[:DETAIL_CHARS])
    if storage != A.STORAGE_RESOLVED:
        return 'storage_integrity_unresolved', 'storage integrity unresolved after assignment %d' % position
    if accounting != A.ACCOUNTING_CLEAN:
        return ('request_accounting_unresolved',
                'physical-request accounting %s after assignment %d (reported %r, budget consumed %d)'
                % (accounting, position, reported if raw is None else raw, budget.consumed))
    return None


def run_queue(episode_fn, *, layout=None, storage_check=None, gate=None, clock=time.time, token=None,
              fixture=False):
    """Launch or resume the fixed cue-v1 queue and dispatch unstarted assignments in frozen order.

    episode_fn(assignment, context) -> terminal record dict with at least
        physical_requests  int 0..48 (the physical sends of this assignment), or None when unknown
        storage_integrity  'resolved' | 'unresolved'  (anything else is treated as unresolved)
      and optionally storage_integrity_detail, exit_status (recorded, never inspected) and run_id.
      context = dict(cohort, run_id, run_dir, position, session, binding_sha256, budget,
                     counted_physical_requests_before, assignment_request_limit, settings, deadlines, storage)
      An episode whose transport raised cue_transport.InfrastructureStop should still return its terminal record with
      storage_integrity='unresolved' and its known physical_requests; an exception out of episode_fn is recorded as
      an episode_error that reserves the full 48 and stops the queue for reconciliation.
    storage_check(assignment) -> None | reason   predeclared storage preflight, e.g.
        lambda row: A.free_space_check(layout.out.parent, host_reserve_bytes=<launcher-supplied reserve>)
    gate(assignment) -> None | reason            host/time/pause gate; a reason stops without any reconciliation
    """
    layout = layout if isinstance(layout, A.Layout) else A.Layout(layout)
    token = token or (lambda: secrets.token_hex(3))
    report = A.validate_queue(layout, require_dispatchable=True)
    binding, problems = A.compute_binding(layout)
    if problems:
        raise A.AdmissionRefused(['current source inconsistency: %s' % p for p in problems], problems=problems)
    A.check_running_sources(binding, {'cue_admission.py': A.SOURCE_SHA256, 'cue_runner.py': SOURCE_SHA256})
    label = episode_function_label(episode_fn, layout, binding, fixture=fixture)
    session = (A.resume_session(layout, clock, episode_function=label) if report['launched']
               else A.launch_session(layout, clock, episode_function=label))
    status = dict(session=None, dispatched=[], stop=None)
    with session:
        ledger = session.ledger
        frozen = session.binding
        status['session'] = ledger.open_session
        rows = {row['position']: row for row in A.plan_rows(frozen)}
        while ledger.next_position() is not None:
            row = dict(rows[ledger.next_position()])
            current, now_problems = A.compute_binding(layout)
            changed = A.diff_bindings(frozen, current)
            if changed or now_problems:
                status['stop'] = _stop(session, 'bound_input_changed', 'bound input changed during the session: %s'
                                       % ', '.join((changed + now_problems)[:8]))
                break
            contents = A._check_head(layout, ledger) + A._check_entries(layout, ledger)
            if contents:
                status['stop'] = _stop(session, 'namespace_contents_invalid', 'namespace contents changed during the '
                                       'session: %s' % '; '.join(contents[:4])[:DETAIL_CHARS])
                break
            reason = gate(dict(row)) if gate is not None else None
            if reason is not None:
                status['stop'] = _stop(session, 'host_gate', str(reason)[:DETAIL_CHARS])
                break
            counted_before = ledger.counted_total()
            if counted_before + ledger.per_assignment > ledger.cap:
                status['stop'] = _stop(session, 'request_cap', 'cohort total %d leaves no room for a full %d-request '
                                       'assignment under %d' % (counted_before, ledger.per_assignment, ledger.cap))
                break
            reason = storage_check(dict(row)) if storage_check is not None else None
            if reason is not None:
                status['stop'] = _stop(session, 'storage_preflight_unresolved', str(reason)[:DETAIL_CHARS])
                break
            position = row['position']
            run_id = _run_id(row['assignment_id'], clock, token)
            session.append('assignment_start', session=ledger.open_session, position=position,
                           assignment_id=row['assignment_id'], run_id=run_id,
                           request_reservation=ledger.per_assignment, counted_physical_requests_before=counted_before)
            status['dispatched'].append(position)
            try:
                run_dir = layout.out / run_id
                run_dir.mkdir(parents=False, exist_ok=False)
            except OSError as exc:
                session.append('assignment_error', session=ledger.open_session, position=position,
                               assignment_id=row['assignment_id'], run_id=run_id, error_class=type(exc).__name__,
                               detail='run directory not created: %s' % str(exc)[:DETAIL_CHARS],
                               counted_requests=ledger.per_assignment, run_dir_created=run_dir.is_dir())
                status['stop'] = _stop(session, 'run_directory_error', 'run directory for assignment %d not created'
                                       % position, affected=[position])
                break
            budget = A.AssignmentRequestBudget(row['assignment_id'], counted_before=counted_before,
                                               per_assignment=ledger.per_assignment, cap=ledger.cap)
            context = dict(cohort=A.COHORT, run_id=run_id, run_dir=run_dir, position=position,
                           session=ledger.open_session, binding_sha256=frozen['binding_sha256'], budget=budget,
                           counted_physical_requests_before=counted_before, assignment_request_limit=budget.limit,
                           settings=json.loads(json.dumps(frozen['settings'])),
                           deadlines=json.loads(json.dumps(frozen['deadlines'])),
                           storage=json.loads(json.dumps(frozen['storage'])))
            try:
                record = episode_fn(dict(row), context)
            except BaseException as exc:  # noqa: BLE001  recorded, then the queue stops (and interrupts re-raise)
                session.append('assignment_error', session=ledger.open_session, position=position,
                               assignment_id=row['assignment_id'], run_id=run_id, error_class=type(exc).__name__,
                               detail=str(exc)[:DETAIL_CHARS], counted_requests=ledger.per_assignment,
                               run_dir_created=True)
                status['stop'] = _stop(session, 'episode_function_error', 'the episode function raised %s'
                                       % type(exc).__name__, affected=[position])
                if not isinstance(exc, Exception):
                    raise
                break
            outcome = _end_assignment(session, row, run_id, record, budget)
            if outcome is not None:
                code, reason = outcome
                status['stop'] = _stop(session, code, reason, affected=[position])
                break
        session.append('session_end', session=ledger.open_session,
                       dispatched_positions=sorted(p for p, s in ledger.starts.items()
                                                   if s['session'] == ledger.open_session),
                       counted_physical_requests=ledger.counted_total(), complete=ledger.complete())
        status.update(complete=ledger.complete(), counted_physical_requests=ledger.counted_total(),
                      assignments=ledger.snapshot(), blocking=ledger.issues())
    return status


# ------------------------------------------------------------------ read-only command line

def dry_run_lines(layout=None):
    """(lines, admitted). Lists the frozen 12 assignments in order with their current state. Creates nothing."""
    layout = layout if isinstance(layout, A.Layout) else A.Layout(layout)
    rows = A.bound_plan(layout)
    states, admission = {}, None
    try:
        report = A.validate_queue(layout)
        states = {row['position']: row['state'] for row in report['assignments']}
        admission = ('admissible: %s; %d/%d physical requests counted; blocking %s'
                     % (report['binding_status'], report['counted_physical_requests'],
                        report['max_physical_requests'], [issue['id'] for issue in report['blocking']] or 'none'))
    except A.AdmissionRefused as exc:
        admission = 'refused: ' + ' | '.join(exc.reasons)
    pair_order = ','.join(row['pair_order'] for row in rows if row['within_pair_position'] == 1)
    lines = ['cue-v1 dry run: %d frozen assignments in position order (pair order %s); nothing is dispatched, '
             'created or written' % (len(rows), pair_order)]
    for row in rows:
        lines.append('%d %s %s %s %s %s' % (row['position'], row['instance_id'], row['backend'], row['arm'],
                                           row['pair_order'], states.get(row['position'], 'unvalidated')))
    lines.append('namespace: %s (%s)' % (A.NAMESPACE_REL, 'present' if layout.out.exists()
                                         else 'absent; created only by a live launch'))
    lines.append('admission: %s' % admission)
    return lines, not admission.startswith('refused')


def main(argv=None):
    ap = argparse.ArgumentParser(description='cue-v1 queue skeleton (read-only commands only)')
    ap.add_argument('--dry-run', action='store_true', help='list the frozen 12 assignments; writes nothing')
    ap.add_argument('--validate', action='store_true', help='print the read-only admission report')
    ap.add_argument('--root', default=None, help='repository root (default: this checkout)')
    args = ap.parse_args(argv)
    layout = A.Layout(args.root)
    if args.dry_run:
        lines, admitted = dry_run_lines(layout)
        print('\n'.join(lines))
        return 0 if admitted else 1
    if args.validate:
        try:
            report = A.validate_queue(layout)
        except A.AdmissionRefused as exc:
            print(json.dumps(dict(admitted=False, reasons=exc.reasons), indent=1))
            return 1
        print(json.dumps(dict(admitted=True, report=report), indent=1))
        return 0
    print(LIVE_HELD, file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main())
