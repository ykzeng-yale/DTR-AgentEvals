"""DTR-REQ-005 cue-v1 terminal phase: the Submitted-only endpoint FIRST, then the bounded all-exit diagnostic, then
container cleanup in a `finally` path. This implements the lead's integration contract bullet "Endpoint then
diagnostic then cleanup" (docs/theory_feedback_20260923_req005_review.md, "Concrete integration contract").

A NEW cue-v1 source. The frozen yaml-v1 drivers (pilot_episode, pilot_runner, pilot_cohort, pilot_report,
pilot_grade) are neither edited nor imported: importing pilot_episode would set MSWEA_* environment variables as
a side effect. The lead-accepted helper exit_capture and the frozen wc2 endpoint rule in workspace_capture are
composed UNMODIFIED.

Order on EVERY terminal path (Submitted, call limit, context, format/receipt error, inference timeout):
  1. endpoint    the frozen Submitted-only / no-salvage artifact (workspace_capture wc2, exactly the frozen driver's
                 rule, see submitted_only_endpoint) is determined and FROZEN (digest and lengths) before anything else.
                 With `submission_path` it is also persisted write-once, before the diagnostic starts.
  2. diagnostic  exit_capture.capture_exit_diagnostic, run separately, through a SUPERVISED subprocess executor. It
                 never writes submission.diff and never changes the endpoint, its exit status or eligibility. The
                 endpoint bytes are re-verified after the diagnostic and again after cleanup.
  3. cleanup     the caller's cleanup(deadline), ALWAYS, from a `finally` path: after endpoint errors, receipt errors,
                 capture errors and even an operator abort, which is re-raised only after cleanup has run.

Deadlines. All are absolute epoch seconds from the injected `clock` (default time.time, the frozen driver's clock).
Nothing here enlarges an episode, block or cleanup deadline.
  existing_cap           = min(episode_deadline, block_deadline) + 120   the frozen driver's cleanup cap
                                                                           (existing_cleanup_cap)
  absolute_cleanup       = min(actual_inference_end + 120, existing_cap)  the phase anchor: an early-finished episode
                                                                           does not inherit its unused inference time
  cleanup_reserve_start  = absolute_cleanup - 90                          at least 90 s are retained for cleanup
  diagnostic_deadline    = min(diagnostic_start + 30, cleanup_reserve_start - 4)   30-s maximum, computed
                                                                           independently; the 4-s hand-off margin
                                                                           (HANDOFF_MARGIN_S) covers the supervisor's
                                                                           post-kill confirmation and the diagnostic
                                                                           record, so cleanup still starts with >= 90 s
  per-subprocess timeout = min(diagnostic_deadline - now, cleanup_reserve_start - now, 60)
If no diagnostic time remains, the diagnostic, or a single command, is skipped with an explicit timeout reason; a
missing precondition is `unavailable`. exit_capture's 300-s default budget is never used: its budget is always the
computed remaining diagnostic time. The cleanup callback receives `absolute_cleanup`, never a later time.

Enforcement by the supervisor rather than the callback. Each diagnostic command runs as a subprocess in its OWN
process group (start_new_session). Its output is read through a bounded non-blocking select loop, so a descendant
that inherits the pipe cannot hold the supervisor open. At the computed bound the WHOLE process group receives
SIGKILL, which cannot be trapped or ignored, the leader is reaped within KILL_GRACE_S and the group is confirmed
empty. A `finally` path does the same whenever the supervisor itself is interrupted, even when the leader already
exited and only a same-group descendant remains, and after a normal exit the group is swept once more for any
detached descendant. So no process that stays in the command's process group outlives the supervisor. A command
that has no time left under its bound is not started at all, and the time spent building its argv is charged to
its bound.

What a process group cannot reach. A descendant that deliberately leaves the group (setsid) is outside any group
signal. When such a process still holds the output pipe after the kill, the supervisor records
`escaped_descendant_suspected`; one that closed the pipe is not observable from here. The diagnostic commands are
exit_capture's own fixed commands (git, head, stat, wc), which do not call setsid. For a `docker exec` argv
(docker_exec_argv) the killed process group is the host-side client. The in-container command is ended by the
container cleanup that always follows. That is the existing cleanup path, and this module adds no second
in-container kill mechanism.

The endpoint is determined before the phase. The frozen driver computes the Submitted-only artifact inside its
inference window, under the inference alarm, before `actual_inference_end`; the cue-v1 driver does the same and
passes the resulting dict. A callable endpoint is still accepted, but its time then counts against the cleanup
window, and the record states whether the 90-s cleanup reserve was still intact when cleanup started.

Unknown stays unknown. A skipped, failed or timed-out capture has `changes_observed=None` and null section bodies,
never an empty observation. Diagnostic time is recorded separately from inference and cleanup for cost accounting,
and tokens, latency, money and energy are not conflated.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import select
import selectors
import signal
import subprocess
import sys
import time
from collections.abc import Mapping
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import exit_capture as XC       # noqa: E402  lead-accepted helper, composed unmodified
import workspace_capture as WC  # noqa: E402  frozen wc2 endpoint rule, reused unmodified

REQUEST = 'DTR-REQ-005'
BINDING = 'cue-v1-terminal-t1'
CONTRACT_SOURCE = ('docs/theory_feedback_20260923_req005_review.md, "Concrete integration contract", '
                   'bullet "Endpoint then diagnostic then cleanup"')

EXISTING_CLEANUP_ALLOWANCE_S = 120   # frozen pilot_episode.py: cleanup_owned_container(..., deadline + 120)
PHASE_WINDOW_S = 120                 # anchor: actual_inference_end + 120 s
DIAGNOSTIC_MAX_S = 30
CLEANUP_RESERVE_S = 90
SUBPROCESS_MAX_S = 60
KILL_GRACE_S = 1.0                   # maximum wait to reap a SIGKILLed group leader and see the group empty
HANDOFF_MARGIN_S = 4.0               # 3 x KILL_GRACE_S (reap, group empty, pipe) + 1 s for the diagnostic record:
                                     # taken from the diagnostic's own time, never from cleanup's 90-s reserve
OUTPUT_CAP_BYTES = 4 * 1024 * 1024   # per command. exit_capture bodies are <= 256 KiB plus a header
READ_CHUNK = 65536
LOG_CAP = 64

TERMINAL_RECORD_NAME = 'terminal_phase.json'
ENDPOINT_RULE = ('Submitted-only, no salvage (workspace_capture wc2): only an explicit Submitted exit with a '
                 'recorded starting tree submits `git diff --binary --full-index <base> <final>`; every other exit '
                 'submits nothing')
CONTAINER_ID = re.compile(r'[0-9a-f]{64}')

PLAN_RUNNABLE, PLAN_NO_TIME, PLAN_INVALID = 'runnable', 'no_time', 'invalid'
NO_TIME_REASON = ('no diagnostic time remains: the diagnostic deadline min(start + 30 s, absolute cleanup deadline '
                  '- 90 s - 4 s hand-off) is not after the diagnostic start; the diagnostic was skipped so cleanup '
                  'keeps its reserve')
CAP_INVALID_REASON = 'the existing absolute cleanup cap is not a finite epoch time'
END_INVALID_REASON = ('the actual inference end is not a finite epoch time: the phase cannot be anchored, so no '
                      'diagnostic time is granted and cleanup keeps the existing cap')
START_INVALID_REASON = 'the diagnostic start (clock) is not a finite epoch time'
NO_EXECUTOR_REASON = ('no supervised executor was supplied (no verified episode-owned container): the diagnostic '
                      'is unavailable, not empty')
ANCHOR_NOTE = ('the reported inference end is later than the diagnostic start; the independent 30-s maximum still '
               'bounds the diagnostic and the cleanup deadline never exceeds the existing cap')
SKIPPED_KIND = ('all-exit diagnostic capture SKIPPED by the terminal supervisor: evidence only, never a submission '
                'and never graded')
ENFORCEMENT = ('cue_terminal.SupervisedExecutor: every command is a subprocess in its own process group; output is '
               'read by a bounded non-blocking loop; at the computed bound the whole group gets SIGKILL and the '
               'leader is reaped within kill_grace_s; a command without remaining time is never started')


class DiagnosticNotDispatched(TimeoutError):
    """No diagnostic time remained at dispatch: the command was never started."""


class DiagnosticSubprocessTimeout(TimeoutError):
    """The supervisor killed the command's whole process group at its computed bound."""


class DiagnosticOutputOverflow(RuntimeError):
    """The command produced more output than the supervisor retains; the body is not an observation."""


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _utf8(text):
    return text.encode('utf-8', 'surrogateescape')


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _jsonable_time(value):
    return value if _finite(value) else repr(value)


def _error_text(exc):
    return '%s: %s' % (type(exc).__name__, str(exc)[:300])


# ---------------------------------------------------------------- deadlines

def existing_cleanup_cap(episode_deadline, block_deadline):
    """The frozen driver's absolute cleanup cap: min(episode, block) inference deadline + 120 s (pilot_episode.py
    passes `deadline + 120` to cleanup_owned_container, where deadline = min(episode, block))."""
    return min(episode_deadline, block_deadline) + EXISTING_CLEANUP_ALLOWANCE_S


def phase_plan(inference_end, existing_cap, diagnostic_start):
    """Terminal-phase deadlines. Pure: no clock, no I/O.

    state `runnable` means diagnostic time remains, `no_time` means none remains and the diagnostic is skipped as
    a timeout, and `invalid` means an input is not a finite epoch time and the diagnostic is skipped as
    unavailable. `absolute_cleanup_deadline` is the deadline the cleanup callback receives. It is never later than
    the existing cap, and when the phase cannot be anchored it is the existing cap itself."""
    plan = dict(inference_end=_jsonable_time(inference_end), existing_absolute_cleanup_cap=_jsonable_time(existing_cap),
                diagnostic_start=_jsonable_time(diagnostic_start), phase_window_s=PHASE_WINDOW_S,
                diagnostic_max_s=DIAGNOSTIC_MAX_S, cleanup_reserve_s=CLEANUP_RESERVE_S,
                handoff_margin_s=HANDOFF_MARGIN_S,
                anchored_deadline=None, absolute_cleanup_deadline=None, absolute_cleanup_binding=None,
                cleanup_reserve_start=None, diagnostic_deadline=None, diagnostic_deadline_binding=None,
                diagnostic_budget_s=None, anchor_consistent=None, anchor_note=None, state=None, reason=None)
    if not _finite(existing_cap):
        return dict(plan, state=PLAN_INVALID, reason=CAP_INVALID_REASON)
    if not _finite(inference_end):
        return dict(plan, state=PLAN_INVALID, reason=END_INVALID_REASON, absolute_cleanup_deadline=existing_cap,
                    absolute_cleanup_binding='existing_cap (unanchored)')
    anchored = inference_end + PHASE_WINDOW_S
    absolute = min(anchored, existing_cap)
    reserve_start = absolute - CLEANUP_RESERVE_S
    plan.update(anchored_deadline=anchored, absolute_cleanup_deadline=absolute,
                absolute_cleanup_binding='inference_end + 120' if anchored <= existing_cap else 'existing_cap',
                cleanup_reserve_start=reserve_start)
    if not _finite(diagnostic_start):
        return dict(plan, state=PLAN_INVALID, reason=START_INVALID_REASON)
    by_max = diagnostic_start + DIAGNOSTIC_MAX_S
    by_reserve = reserve_start - HANDOFF_MARGIN_S
    deadline = min(by_max, by_reserve)
    consistent = inference_end <= diagnostic_start
    plan.update(diagnostic_deadline=deadline,
                diagnostic_deadline_binding='diagnostic_max_30s' if by_max < by_reserve else 'cleanup_reserve_90s',
                anchor_consistent=consistent, anchor_note=None if consistent else ANCHOR_NOTE)
    budget = deadline - diagnostic_start
    if budget <= 0:
        return dict(plan, state=PLAN_NO_TIME, reason=NO_TIME_REASON, diagnostic_budget_s=0.0)
    return dict(plan, state=PLAN_RUNNABLE, diagnostic_budget_s=budget)


def subprocess_timeout(plan, now):
    """One command's bound: min(remaining diagnostic time, time to (absolute cleanup deadline - 90 s), 60 s).
    Pure. `dispatch` is False when the bound is not positive, or when the plan is not runnable."""
    out = dict(now=_jsonable_time(now), remaining_diagnostic_s=None, to_cleanup_reserve_s=None,
               subprocess_max_s=SUBPROCESS_MAX_S, timeout_s=None, binding=None, dispatch=False)
    if not isinstance(plan, Mapping) or plan.get('state') != PLAN_RUNNABLE or not _finite(now):
        return out
    terms = (('remaining_diagnostic_time', plan['diagnostic_deadline'] - now),
             ('time_to_cleanup_reserve', plan['cleanup_reserve_start'] - now),
             ('subprocess_max_60s', SUBPROCESS_MAX_S))
    binding, timeout = min(terms, key=lambda term: term[1])      # ties keep the first term in this order
    out.update(remaining_diagnostic_s=terms[0][1], to_cleanup_reserve_s=terms[1][1], timeout_s=timeout,
               binding=binding, dispatch=timeout > 0)
    return out


# ---------------------------------------------------------------- supervised subprocess executor

def docker_exec_argv(executable, container_id, *, cwd=XC.WORKDIR, env=None, interpreter=('bash', '-lc')):
    """argv builder mirroring the pinned DockerEnvironment.execute: [executable, exec, -w, cwd, -e K=V..., id,
    *interpreter, command]. forward_env is not reproduced: the pinned pilot configuration declares none. Only a full
    64-hex episode-owned container ID is accepted; otherwise ValueError, and the caller passes argv_for=None."""
    if not isinstance(container_id, str) or not CONTAINER_ID.fullmatch(container_id):
        raise ValueError('no verified full episode-owned container ID')
    prefix = [str(executable), 'exec', '-w', str(cwd)]
    for key, value in (env or {}).items():
        prefix.extend(['-e', '%s=%s' % (key, value)])
    prefix.append(container_id)
    prefix.extend(interpreter)

    def argv_for(command):
        return prefix + [command]
    return argv_for


def _killpg(proc, rec):
    """SIGKILL the command's whole process group (pgid == leader pid under start_new_session)."""
    rec['killed'], rec['kill_signal'] = True, 'SIGKILL'
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass                                   # the whole group had already exited
    except OSError as e:
        rec['kill_error'] = _error_text(e)
        try:
            proc.kill()
        except OSError:
            pass


def _sweep_group(pgid):
    """After a normal exit (leader reaped), SIGKILL any member still left in the command's own process group. A
    process-group ID is not reused while that group exists, so this reaches only the command's own descendants;
    once the group is empty the call fails with ESRCH (the residual risk is a pid-counter wraparound between the
    reap and this call)."""
    try:
        os.killpg(pgid, signal.SIGKILL)
        return 'killed_lingering_members'
    except ProcessLookupError:
        return 'no_lingering_members'
    except OSError as e:
        return 'error: %s' % _error_text(e)


def _group_empty(pgid, within):
    """True once no process is left in the group (signal 0 fails with ESRCH), False if members remain after
    `within` seconds, None when it cannot be observed."""
    end = time.monotonic() + within
    while True:
        try:
            os.killpg(pgid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            pass                                   # transient on macOS while a killed orphan is being reaped
        except OSError:
            return None
        if time.monotonic() >= end:
            return False
        time.sleep(0.01)


def _pipe_still_held(fd, within):
    """After the kill: True if some process still holds the output pipe open (no EOF within `within` seconds), i.e.
    a descendant escaped the process group. The bytes read here are discarded; the command already timed out."""
    end = time.monotonic() + within
    try:
        while True:
            left = end - time.monotonic()
            if left <= 0:
                return True
            ready, _, _ = select.select([fd], [], [], left)
            if not ready:
                return True
            try:
                if not os.read(fd, READ_CHUNK):
                    return False
            except BlockingIOError:
                continue
    except (OSError, ValueError):
        return None


SPAWN_KWARGS = dict(stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    start_new_session=True, close_fds=True)


def _supervise(proc, t0, timeout_s, *, kill_grace_s, output_cap_bytes, rec=None):
    """Supervise a started process (its own process group) under a hard bound measured from t0 (monotonic, taken
    before the spawn). Returns (record, output bytes). Never leaves the process group running. A caller-supplied
    `rec` keeps the kill evidence even when the supervisor itself is interrupted."""
    rec = {} if rec is None else rec
    rec.update(outcome=None, pid=proc.pid, returncode=None, elapsed_s=None, killed=False, kill_signal=None,
               kill_confirmed=None, kill_error=None, group_sweep=None, group_empty_confirmed=None,
               escaped_descendant_suspected=None, output_bytes=0, output_dropped_bytes=0)
    kept = bytearray()
    selector = selectors.DefaultSelector()
    try:
        fd = proc.stdout.fileno()
        os.set_blocking(fd, False)
        selector.register(fd, selectors.EVENT_READ)
        deadline = t0 + timeout_s
        eof = False
        while not eof:
            left = deadline - time.monotonic()
            if left <= 0:
                break
            if not selector.select(timeout=left):
                continue
            try:
                data = os.read(fd, READ_CHUNK)
            except BlockingIOError:
                continue
            if not data:
                eof = True
                break
            room = max(0, output_cap_bytes - len(kept))
            kept += data[:room]
            rec['output_dropped_bytes'] += len(data) - min(room, len(data))
        exited = False
        if eof:
            try:
                proc.wait(timeout=max(0.0, deadline - time.monotonic()))
                exited = True
            except subprocess.TimeoutExpired:
                exited = False
        if exited:
            rec['outcome'] = 'exited'
            rec['group_sweep'] = _sweep_group(proc.pid)
            rec['group_empty_confirmed'] = _group_empty(proc.pid, kill_grace_s)
        else:
            rec['outcome'] = 'timeout_killed'
            _killpg(proc, rec)
            try:
                proc.wait(timeout=kill_grace_s)
                rec['kill_confirmed'] = True
            except subprocess.TimeoutExpired:
                rec['kill_confirmed'] = False
            rec['group_empty_confirmed'] = _group_empty(proc.pid, kill_grace_s)
            rec['escaped_descendant_suspected'] = _pipe_still_held(fd, kill_grace_s)
    finally:
        # Interrupted before either path finished (e.g. an operator abort in the read loop): kill the WHOLE group
        # even if the leader has already exited, because a same-group descendant may still be running.
        if not rec['killed'] and (rec['outcome'] is None or proc.poll() is None):
            rec['outcome'] = rec['outcome'] or 'interrupted_killed'
            _killpg(proc, rec)                 # the supervisor itself was interrupted: never leave the group behind
            try:
                proc.wait(timeout=kill_grace_s)
                rec['kill_confirmed'] = True
            except subprocess.TimeoutExpired:
                rec['kill_confirmed'] = False
            rec['group_empty_confirmed'] = _group_empty(proc.pid, kill_grace_s)
        selector.close()
        proc.stdout.close()
        rec['returncode'] = proc.returncode
        rec['elapsed_s'] = round(time.monotonic() - t0, 6)
        rec['output_bytes'] = len(kept)
    return rec, bytes(kept)


class SupervisedExecutor:
    """exit_capture executor contract: execute(command) -> (returncode, output). It enforces the contract bound
    itself instead of trusting the command to return.

    Raises DiagnosticNotDispatched when no time remains, DiagnosticSubprocessTimeout after a kill at the bound and
    DiagnosticOutputOverflow when output exceeded the retained cap. exit_capture records the first two as `timeout`
    and the third as `failed`. Output is decoded with surrogateescape, so its UTF-8/surrogateescape re-encoding is
    the exact byte sequence the command wrote."""

    def __init__(self, argv_for, plan, *, clock=time.time, popen=subprocess.Popen, kill_grace_s=KILL_GRACE_S,
                 output_cap_bytes=OUTPUT_CAP_BYTES, log_cap=LOG_CAP):
        self.argv_for, self.plan, self.clock, self.popen = argv_for, plan, clock, popen
        self.kill_grace_s, self.output_cap_bytes, self.log_cap = kill_grace_s, output_cap_bytes, log_cap
        self.log, self.dropped_log_entries = [], 0
        self.counts = dict(requested=0, not_dispatched=0, argv_errors=0, spawn_errors=0, supervisor_errors=0,
                           spawned=0, exited=0, killed=0, kill_unconfirmed=0, group_not_empty=0,
                           escaped_descendant_suspected=0, output_overflow=0)
        self.subprocess_seconds = 0.0

    def _keep(self, entry):
        if len(self.log) < self.log_cap:
            self.log.append(entry)
        else:
            self.dropped_log_entries += 1

    def __call__(self, command):
        self.counts['requested'] += 1
        text = command if isinstance(command, str) else repr(command)
        entry = dict(index=self.counts['requested'], command_sha256=_sha256(_utf8(text)), command_chars=len(text))
        self._keep(entry)
        early = subprocess_timeout(self.plan, self.clock())
        if not early['dispatch']:
            entry.update(early, outcome='not_dispatched')
            self.counts['not_dispatched'] += 1
            raise DiagnosticNotDispatched('no diagnostic time remains (bound %r s); the command was not started'
                                          % (early['timeout_s'],))
        try:
            argv = self.argv_for(command)
        except BaseException as e:
            entry.update(early, outcome='argv_error', error=_error_text(e))
            self.counts['argv_errors'] += 1
            raise
        # the bound is taken AFTER building the argv, so time spent there is charged to this command
        bound = subprocess_timeout(self.plan, self.clock())
        entry.update(bound)
        if not bound['dispatch']:
            entry['outcome'] = 'not_dispatched'
            self.counts['not_dispatched'] += 1
            raise DiagnosticNotDispatched('no diagnostic time remains (bound %r s); the command was not started'
                                          % (bound['timeout_s'],))
        t0 = time.monotonic()
        try:
            proc = self.popen(argv, **SPAWN_KWARGS)
        except BaseException as e:
            entry.update(outcome='spawn_error', error=_error_text(e))
            self.counts['spawn_errors'] += 1
            raise
        self.counts['spawned'] += 1
        partial = {}
        try:
            rec, output = _supervise(proc, t0, bound['timeout_s'], kill_grace_s=self.kill_grace_s,
                                     output_cap_bytes=self.output_cap_bytes, rec=partial)
        except BaseException as e:
            entry.update(partial)
            entry.update(outcome='supervisor_error', error=_error_text(e))
            if entry.get('elapsed_s') is None:
                entry['elapsed_s'] = round(time.monotonic() - t0, 6)
            self.counts['supervisor_errors'] += 1
            if entry.get('killed'):
                self.counts['killed'] += 1
                if entry.get('kill_confirmed') is not True:
                    self.counts['kill_unconfirmed'] += 1
            if entry.get('group_empty_confirmed') is False:
                self.counts['group_not_empty'] += 1
            self.subprocess_seconds += entry['elapsed_s']
            raise
        entry.update(rec)
        self.subprocess_seconds += rec['elapsed_s']
        if rec['group_empty_confirmed'] is False:
            self.counts['group_not_empty'] += 1
        if rec['escaped_descendant_suspected']:
            self.counts['escaped_descendant_suspected'] += 1
        if rec['outcome'] == 'timeout_killed':
            self.counts['killed'] += 1
            if rec['kill_confirmed'] is not True:
                self.counts['kill_unconfirmed'] += 1
            raise DiagnosticSubprocessTimeout(
                'the supervisor killed the command process group at its %.3f-s bound (%s)'
                % (bound['timeout_s'], bound['binding']))
        self.counts['exited'] += 1
        if rec['output_dropped_bytes']:
            entry['outcome'] = 'output_overflow'
            self.counts['output_overflow'] += 1
            raise DiagnosticOutputOverflow('command output exceeded the %d-byte supervisor cap (%d bytes dropped); '
                                           'the body is not an observation'
                                           % (self.output_cap_bytes, rec['output_dropped_bytes']))
        return rec['returncode'], output.decode('utf-8', 'surrogateescape')

    def summary(self):
        return dict(enforced_by=ENFORCEMENT, subprocess_max_s=SUBPROCESS_MAX_S, kill_grace_s=self.kill_grace_s,
                    output_cap_bytes=self.output_cap_bytes, counts=dict(self.counts),
                    subprocess_seconds=round(self.subprocess_seconds, 6), log=list(self.log),
                    dropped_log_entries=self.dropped_log_entries)


# ---------------------------------------------------------------- endpoint (frozen rule, composed)

def submitted_only_endpoint(exit_status, base_tree, execute, *, wd=WC.WORKDIR, base_capture_error=None):
    """The frozen driver's Submitted-only / no-salvage endpoint, reproduced step for step over the unmodified
    workspace_capture (pilot_episode.py lines 233-244). `execute` is the driver's pinned command adapter
    (DockerEnvironment.execute -> (returncode, output)), so the endpoint bytes are decoded exactly as frozen.

    Non-Submitted exits submit '' without running any command. Submitted without a starting tree becomes
    SubmissionCaptureFailed. A wc2 CaptureError becomes SubmissionCaptureFailed with capture_error 'final: ...'.
    Any other Exception becomes an exit named by its type, as the frozen outer handler does, with submission ''.
    KeyboardInterrupt and SystemExit pass through."""
    out = dict(exit_status=exit_status, submission='', final_tree=None, capture_error=base_capture_error,
               error=None, rule=ENDPOINT_RULE)
    if exit_status != 'Submitted':
        return out
    if base_tree is None:
        out['exit_status'] = 'SubmissionCaptureFailed'
        return out
    try:
        cap = WC.patch(execute, base_tree, wd)
        out.update(submission=cap['patch'], final_tree=cap['final_tree'])
    except WC.CaptureError as e:
        out.update(exit_status='SubmissionCaptureFailed', capture_error='final: %s' % e)
    except Exception as e:  # noqa: BLE001  the frozen outer handler: the exception type names the exit
        out.update(exit_status=type(e).__name__, error=str(e)[:500], submission='', final_tree=None)
    return out


def _freeze_endpoint(endpoint):
    """Validate and freeze an endpoint dict. The submission object is kept for re-verification; the summary
    carries only digests and lengths."""
    if not isinstance(endpoint, Mapping) or not isinstance(endpoint.get('submission'), str) \
            or not (endpoint.get('exit_status') is None or isinstance(endpoint.get('exit_status'), str)):
        raise TypeError('the endpoint must be a mapping with a str (or None) `exit_status` and a str `submission`')
    submission = endpoint['submission']
    raw = _utf8(submission)
    return dict(state='frozen', exit_status=endpoint['exit_status'], submission=submission,
                final_tree=endpoint.get('final_tree'), capture_error=endpoint.get('capture_error'),
                error=endpoint.get('error'), submission_sha256=_sha256(raw), submission_chars=len(submission),
                submission_utf8_bytes=len(raw), submission_empty=not submission.strip())


def _endpoint_error(exc):
    """An endpoint callable that raised: under the frozen no-salvage rule nothing is submitted."""
    raw = b''
    return dict(state='error', exit_status=type(exc).__name__, submission='', final_tree=None, capture_error=None,
                error=_error_text(exc), submission_sha256=_sha256(raw), submission_chars=0,
                submission_utf8_bytes=0, submission_empty=True)


def _endpoint_summary(frozen):
    return {k: v for k, v in frozen.items() if k != 'submission'}


def _verify_endpoint(frozen, submission_path, write_state):
    """Re-derive the endpoint digest from the retained object and from the bytes of ANY file at the endpoint path.

    `unchanged` means the retained object and the file this phase wrote both still carry the frozen digest.
    `changed` means one of them no longer does. `file_conflict` means a file exists at the endpoint path that this
    phase did not completely write (a pre-existing file, or a partial write left by a failed write) and its bytes
    differ from the frozen endpoint; it must never be taken for the submission."""
    check = dict(in_memory_sha256=None, file_sha256=None, file_present=None, state=None)
    if frozen is None:
        return dict(check, state='unverifiable', reason='no frozen endpoint')
    try:
        check['in_memory_sha256'] = _sha256(_utf8(frozen['submission']))
        same = check['in_memory_sha256'] == frozen['submission_sha256']
        if submission_path is not None:
            path = Path(submission_path)
            check['file_present'] = path.exists()
            if check['file_present']:
                check['file_sha256'] = _sha256(path.read_bytes())
            file_same = check['file_sha256'] == frozen['submission_sha256']
            if write_state == 'written':
                same = same and file_same
            elif check['file_present'] and not file_same:
                return dict(check, state='file_conflict',
                            reason='a file at the endpoint path was not completely written by this phase (%s) and '
                                   'its bytes differ from the frozen endpoint' % write_state)
        check['state'] = 'unchanged' if same else 'changed'
    except Exception as e:  # noqa: BLE001  verification must not block cleanup
        check.update(state='unverifiable', reason=_error_text(e))
    return check


# ---------------------------------------------------------------- diagnostic

FAILED_KIND = ('all-exit diagnostic capture FAILED past its own containment: evidence only, never a submission '
               'and never graded')


def _skipped_record(state, reason, exit_status, base_tree, caps, skipped=True):
    """A diagnostic that did not run (or broke): every section has a state and a reason and nothing observed,
    never an empty observation."""
    limits, _caps_error = XC.resolve_caps(caps)
    sections = {}
    for name in XC.SECTION_NAMES:
        sections[name] = dict(state=state, reason=reason, text=None, full_bytes=None, sha256=None)
    sections['tree']['sha'] = None
    sections['untracked'].update(paths=None, n_paths=None, n_recorded=None, paths_complete=None)
    return dict(kind=SKIPPED_KIND if skipped else FAILED_KIND, request=XC.REQUEST, binding=XC.BINDING,
                exit_status=exit_status,
                endpoint=dict(writes_submission_diff=False, marks_submitted=False, graded=False,
                              changes_eligibility=False, changes_endpoint_bytes=False, output_file=XC.OUTPUT_NAME),
                base_tree=base_tree if isinstance(base_tree, str) else None, caps=limits, total_budget_s=0.0,
                status=state, changes_observed=None, sections=sections, commands=[],
                failures=[dict(section='capture', state=state, reason=reason)], capture_error=None,
                skipped=skipped, skip_reason=reason if skipped else None)


def _write_contained(out_dir, record):
    """Write a diagnostic record through exit_capture.write_diagnostic (endpoint names refused); never raises."""
    if out_dir is None:
        return dict(record, write=dict(state='not_requested', file=None))
    try:
        directory = Path(out_dir)
        if not directory.is_dir():
            return dict(record, write=dict(state='refused_missing_out_dir', file=None,
                                           reason='out_dir is not an existing directory'))
        record['write'] = dict(state='attempted', file=XC.OUTPUT_NAME)
        written = XC.write_diagnostic(directory / XC.OUTPUT_NAME, record)
        return dict(record, write=dict(state='written', file=written.name))
    except (KeyboardInterrupt, SystemExit):
        raise
    except FileExistsError:
        return dict(record, write=dict(state='refused_existing', file=XC.OUTPUT_NAME,
                                       reason='an exit diagnostic already exists; records are write-once'))
    except Exception as e:  # noqa: BLE001
        return dict(record, write=dict(state='failed', file=None, reason=_error_text(e)))


def run_diagnostic(*, plan, argv_for, base_tree, exit_status, out_dir=None, wd=XC.WORKDIR, caps=None,
                   clock=time.time, popen=subprocess.Popen, kill_grace_s=KILL_GRACE_S,
                   output_cap_bytes=OUTPUT_CAP_BYTES, supervisor=None):
    """The all-exit diagnostic under the plan. Returns (diagnostic record, supervisor record) and never raises
    Exception. KeyboardInterrupt and SystemExit pass through, and run_terminal_phase still cleans up. A caller
    that passes its own `supervisor` dict keeps the supervisor evidence even when an abort passes through."""
    supervisor = {} if supervisor is None else supervisor
    supervisor.update(state=None, reason=None, enforced_by=ENFORCEMENT, subprocess_max_s=SUBPROCESS_MAX_S,
                      kill_grace_s=kill_grace_s, output_cap_bytes=output_cap_bytes, counts=None,
                      subprocess_seconds=0.0, log=[], dropped_log_entries=0)
    state = (plan or {}).get('state') if isinstance(plan, Mapping) else None
    if state != PLAN_RUNNABLE or argv_for is None:
        if state == PLAN_NO_TIME:
            status, reason = 'timeout', NO_TIME_REASON
        elif state == PLAN_RUNNABLE:
            status, reason = 'unavailable', NO_EXECUTOR_REASON
        else:
            status = 'unavailable'
            reason = (plan.get('reason') if isinstance(plan, Mapping) else None) or 'no terminal-phase plan'
        supervisor.update(state='skipped', reason=reason)
        return _write_contained(out_dir, _skipped_record(status, reason, exit_status, base_tree, caps)), supervisor
    executor = SupervisedExecutor(argv_for, plan, clock=clock, popen=popen, kill_grace_s=kill_grace_s,
                                  output_cap_bytes=output_cap_bytes)
    try:
        budget = max(0.0, plan['diagnostic_deadline'] - clock())
        record = XC.capture_exit_diagnostic(executor, base_tree, exit_status=exit_status, out_dir=out_dir, wd=wd,
                                            caps=caps, budget_s=budget, per_command_timeout_s=SUBPROCESS_MAX_S,
                                            clock=clock)
        supervisor.update(state='completed')
    except (KeyboardInterrupt, SystemExit):
        supervisor.update(executor.summary(), state='interrupted')
        raise
    except Exception as e:  # noqa: BLE001  a capture defect past its own containment must not block cleanup
        reason = 'the capture raised past its own containment: %s' % _error_text(e)
        supervisor.update(state='capture_error', reason=reason)
        record = _write_contained(out_dir, _skipped_record('failed', reason, exit_status, base_tree, caps,
                                                           skipped=False))
    supervisor.update(executor.summary())
    return record, supervisor


def _diagnostic_summary(record):
    if not isinstance(record, Mapping):
        return None
    sections = record.get('sections') or {}
    return dict(status=record.get('status'), changes_observed=record.get('changes_observed'),
                total_budget_s=record.get('total_budget_s'), skipped=bool(record.get('skipped')),
                skip_reason=record.get('skip_reason'), capture_error=record.get('capture_error'),
                section_states={name: (sections.get(name) or {}).get('state') for name in XC.SECTION_NAMES},
                failures=list(record.get('failures') or [])[:16], write=record.get('write'),
                command_labels=[c.get('label') for c in (record.get('commands') or [])][:LOG_CAP])


# ---------------------------------------------------------------- terminal phase

def run_terminal_phase(*, endpoint, inference_end, existing_cap, cleanup, argv_for, base_tree, out_dir=None,
                       submission_path=None, wd=XC.WORKDIR, caps=None, clock=time.time, popen=subprocess.Popen,
                       kill_grace_s=KILL_GRACE_S, output_cap_bytes=OUTPUT_CAP_BYTES):
    """Endpoint, then diagnostic, then cleanup (always). Call it on EVERY terminal path, after the inference alarm
    has been disarmed, as the frozen driver does before cleanup.

      endpoint         zero-argument callable returning the endpoint dict (use submitted_only_endpoint), or that
                       dict itself; `exit_status` and `submission` must be str
      inference_end    actual_inference_end, epoch seconds
      existing_cap     the existing absolute cleanup cap (existing_cleanup_cap(episode_deadline, block_deadline))
      cleanup          callable(deadline) run from `finally`; it receives the absolute cleanup deadline
      argv_for         command -> argv for the supervised executor (docker_exec_argv), or None when there is no
                       verified container; then the diagnostic is `unavailable`
      out_dir          existing run directory for exit_diagnostic.json and terminal_phase.json (write-once)
      submission_path  when given, the frozen endpoint is written there write-once BEFORE the diagnostic

    Returns dict(record=<the JSON-able terminal record>, endpoint=<frozen endpoint including the submission str>,
    diagnostic=<full diagnostic record>). It raises only an operator abort (KeyboardInterrupt/SystemExit), and then
    only after cleanup and the terminal record."""
    started = time.monotonic()
    rec = dict(kind='cue-v1 terminal phase: endpoint, then diagnostic, then cleanup (evidence; never graded)',
               request=REQUEST, binding=BINDING, contract=CONTRACT_SOURCE,
               order=['endpoint', 'diagnostic', 'cleanup'], endpoint_rule=ENDPOINT_RULE,
               constants=dict(phase_window_s=PHASE_WINDOW_S, diagnostic_max_s=DIAGNOSTIC_MAX_S,
                              cleanup_reserve_s=CLEANUP_RESERVE_S, handoff_margin_s=HANDOFF_MARGIN_S,
                              subprocess_max_s=SUBPROCESS_MAX_S,
                              kill_grace_s=kill_grace_s, output_cap_bytes=output_cap_bytes,
                              exit_capture_default_budget_s_used=False),
               steps=[], endpoint=None, endpoint_write=None, endpoint_check_after_diagnostic=None,
               endpoint_check_after_cleanup=None, plan=None, diagnostic=None, supervisor=None, cleanup=None,
               timing=dict(clock='injected epoch clock for deadlines; time.monotonic for durations',
                           endpoint_seconds=None, diagnostic_seconds=None, diagnostic_subprocess_seconds=None,
                           cleanup_seconds=None, terminal_seconds=None, diagnostic_started_at=None,
                           diagnostic_ended_at=None, diagnostic_overrun_s=None, cleanup_started_at=None),
               cost_accounting=dict(diagnostic_seconds=None,
                                    note='diagnostic wall time is terminal-phase overhead, recorded separately from '
                                         'inference and cleanup; it is not tokens, money or energy'),
               interrupted=None, terminal_error=None, record_write=None)
    frozen, plan, diagnostic = None, None, None
    write_state = None
    rec['endpoint_mode'] = ('callable evaluated inside the phase: its time counts against the cleanup window'
                            if callable(endpoint) else 'determined before the phase (the frozen driver\'s order)')
    try:
        # 1. endpoint: frozen before anything else
        rec['steps'].append('endpoint')
        t = time.monotonic()
        try:
            frozen = _freeze_endpoint(endpoint() if callable(endpoint) else endpoint)
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:  # noqa: BLE001
            frozen = _endpoint_error(e)
        rec['endpoint'] = _endpoint_summary(frozen)
        if submission_path is not None:
            try:
                WC.write_once(submission_path, frozen['submission'])
                write_state = 'written'
                rec['endpoint_write'] = dict(state='written', file=Path(submission_path).name)
            except FileExistsError:
                write_state = 'refused_existing'
                rec['endpoint_write'] = dict(state='refused_existing', file=Path(submission_path).name,
                                             reason='the endpoint file already exists; it is write-once')
            except Exception as e:  # noqa: BLE001
                write_state = 'failed'
                rec['endpoint_write'] = dict(state='failed', file=None, reason=_error_text(e))
        else:
            rec['endpoint_write'] = dict(state='not_requested', file=None)
        rec['timing']['endpoint_seconds'] = round(time.monotonic() - t, 6)

        # 2. diagnostic: separately, supervised, never touching the endpoint
        rec['steps'].append('diagnostic')
        t = time.monotonic()
        start = clock()
        plan = phase_plan(inference_end, existing_cap, start)
        rec['plan'] = plan
        rec['timing']['diagnostic_started_at'] = _jsonable_time(start)
        rec['supervisor'] = {}
        try:
            diagnostic, _ = run_diagnostic(plan=plan, argv_for=argv_for, base_tree=base_tree,
                                           exit_status=frozen['exit_status'], out_dir=out_dir, wd=wd, caps=caps,
                                           clock=clock, popen=popen, kill_grace_s=kill_grace_s,
                                           output_cap_bytes=output_cap_bytes, supervisor=rec['supervisor'])
            rec['diagnostic'] = _diagnostic_summary(diagnostic)
        finally:
            seconds = round(time.monotonic() - t, 6)
            rec['timing'].update(diagnostic_seconds=seconds,
                                 diagnostic_subprocess_seconds=rec['supervisor'].get('subprocess_seconds'))
            rec['cost_accounting']['diagnostic_seconds'] = seconds
            try:
                ended = clock()
                rec['timing']['diagnostic_ended_at'] = _jsonable_time(ended)
                if plan.get('state') == PLAN_RUNNABLE and _finite(ended):
                    rec['timing']['diagnostic_overrun_s'] = max(0.0, ended - plan['diagnostic_deadline'])
            except Exception as e:  # noqa: BLE001
                rec['timing']['diagnostic_ended_at'] = 'clock: %s' % _error_text(e)
        rec['endpoint_check_after_diagnostic'] = _verify_endpoint(frozen, submission_path, write_state)
    except (KeyboardInterrupt, SystemExit) as e:
        rec['interrupted'] = _error_text(e)
        raise
    except Exception as e:  # noqa: BLE001  contained: cleanup below must run and nothing ordinary escapes
        rec['terminal_error'] = _error_text(e)
    finally:
        # 3. cleanup: always
        rec['steps'].append('cleanup')
        t = time.monotonic()
        deadline = existing_cap
        try:
            if plan is None:
                plan = phase_plan(inference_end, existing_cap, clock())
                rec['plan'] = plan
            if plan.get('absolute_cleanup_deadline') is not None:
                deadline = plan['absolute_cleanup_deadline']
        except Exception as e:  # noqa: BLE001  a broken clock must not block cleanup
            rec['plan_error'] = _error_text(e)
        cleanup_rec = dict(state=None, deadline=_jsonable_time(deadline), time_available_s=None,
                           deadline_within_existing_cap=(deadline <= existing_cap)
                           if _finite(deadline) and _finite(existing_cap) else None,
                           reserve_s=CLEANUP_RESERVE_S, reserve_intact=None, receipt=None, error=None)
        rec['cleanup'] = cleanup_rec
        try:
            try:
                now = clock()
                rec['timing']['cleanup_started_at'] = _jsonable_time(now)
                if _finite(deadline) and _finite(now):
                    cleanup_rec['time_available_s'] = deadline - now
                    cleanup_rec['reserve_intact'] = deadline - now >= CLEANUP_RESERVE_S
            except Exception as e:  # noqa: BLE001
                cleanup_rec['error'] = 'clock: %s' % _error_text(e)
            try:
                cleanup_rec['receipt'] = cleanup(deadline)
                cleanup_rec['state'] = 'returned'
            except (KeyboardInterrupt, SystemExit) as e:
                cleanup_rec.update(state='interrupted', error=_error_text(e))
                raise
            except Exception as e:  # noqa: BLE001  recorded; the endpoint and diagnostic are already retained
                cleanup_rec.update(state='raised', error=_error_text(e))
        finally:
            rec['timing']['cleanup_seconds'] = round(time.monotonic() - t, 6)
            rec['endpoint_check_after_cleanup'] = _verify_endpoint(frozen, submission_path, write_state)
            rec['timing']['terminal_seconds'] = round(time.monotonic() - started, 6)
            rec['record_write'] = _write_terminal_record(out_dir, rec)
    return dict(record=rec, endpoint=frozen, diagnostic=diagnostic)


def _write_terminal_record(out_dir, rec):
    if out_dir is None:
        return dict(state='not_requested', file=None)
    try:
        directory = Path(out_dir)
        if not directory.is_dir():
            return dict(state='refused_missing_out_dir', file=None, reason='out_dir is not an existing directory')
        rec['record_write'] = dict(state='attempted', file=TERMINAL_RECORD_NAME)
        WC.write_once(directory / TERMINAL_RECORD_NAME, json.dumps(rec, indent=1, default=repr) + '\n')
        return dict(state='written', file=TERMINAL_RECORD_NAME)
    except (KeyboardInterrupt, SystemExit):
        raise
    except FileExistsError:
        return dict(state='refused_existing', file=TERMINAL_RECORD_NAME,
                    reason='a terminal record already exists; records are write-once')
    except Exception as e:  # noqa: BLE001
        return dict(state='failed', file=None, reason=_error_text(e))
