"""DTR-REQ-005 all-exit diagnostic capture, binding `xc1` (lead answer 1 in
docs/theory_feedback_20260923_completed_pilots.md): 30 of 32 yaml-v1 terminal workspace states were
UNOBSERVED, and the retrospective review had to be explicit that unobserved is not observed-empty.
This module removes that gap for the NEW cohort namespace only; yaml-v1 execution sources and archives
stay frozen (cohort_binding.json hashes pilot_episode/pilot_runner/pilot_cohort, so nothing here edits them).

Declared rule:
  * on EVERY exit (Submitted, call limit, context, timeout, error) and BEFORE container cleanup, record a
    BOUNDED diagnostic computed from the container:
        tree      final whole-working-tree SHA through a PRIVATE temporary git index -- WC.TREE_CMD/WC.SHA
                  are reused verbatim, so this tree is constructed exactly like the recorded starting tree
        status    `git status --porcelain --untracked-files=all`, byte-capped
        diff      tracked diff against the RECORDED STARTING TREE: `git diff --binary --full-index base final`
                  (mode `tree_to_tree`); if the final tree snapshot is unavailable it falls back to
                  `git diff --binary --full-index base` against the live working tree (mode `base_to_worktree`),
                  and the mode is always recorded
        untracked `git ls-files --others --exclude-standard -z` paths, each with the sha256 digest of its FULL
                  content plus byte-capped contents when available. The private-index tree already includes
                  new non-ignored paths, so the diff is a SUPERSET of tracked edits and this section adds the
                  per-path digests, sizes and contents that a diff body alone does not give.
  * EVERY bound is explicit in the record: `caps` (byte/path/file caps, each validated and any rejected
    declaration named in `caps_error`), per-section `truncated` flags, `digest_scope` naming what each
    sha256 covers, `per_command_timeout_s`, `total_budget_s`, `exclusions`, and `failures` with a reason per
    degraded OR knowingly incomplete section.
  * ABSENT IS NEVER EMPTY, and INCOMPLETE IS NEVER ABSENT-FREE. Section states are
        captured     a completed nonempty observation
        no_change    a COMPLETED EMPTY observation
        incomplete   the observation ran but is known to be partial (e.g. the untracked listing was
                     byte-truncated, so zero recorded paths does not mean zero paths)
        unavailable  a precondition was missing, or the section was never reached
        failed       the command failed, or its recorded body disagrees with its own declared byte count
        timeout      the command or the total budget timed out
    A section that did not complete has text/bytes `null`. Anything unknown stays `null`, never 0. The
    roll-up `status` is `no_change` only when ALL THREE change signals (status, diff, untracked) completed
    and observed nothing, and `changes_observed` is `null` whenever they leave it unknown.
  * ENDPOINT UNTOUCHED. The diagnostic is never written into `submission.diff` (write_diagnostic refuses
    those names case-insensitively and any `.diff`/`.patch` suffix), never sets/implies Submitted, is never
    graded and never changes eligibility or endpoint bytes. The frozen Submitted-only/no-salvage endpoint
    rule of workspace_capture is unchanged.
  * CLEANUP IS NEVER BLOCKED. capture() and capture_exit_diagnostic() do not raise Exception to the caller
    for ANY argument or executor behaviour: a failing, hanging, refusing or malformed capture becomes a
    recorded state, and every section key is present in the record even when the capture breaks internally.
    Only KeyboardInterrupt/SystemExit pass through (an operator abort must stay an abort). Work is
    additionally bounded by `total_budget_s`, checked against the injected clock before every command, so a
    slow executor cannot delay cleanup indefinitely.

The command executor is INJECTED (`execute(command)`), as in workspace_capture, so fixtures need no container.
It may return `(returncode, output)` or mini-swe-agent's `{'returncode','output','exception_info'}` dict; any
other shape is recorded as an executor-contract failure, distinguishable from a container failure. The
per-command timeout is enforced by that executor (DockerEnvironment `timeout`), and is recorded here as a
declaration. A raised timeout, a `124` return code (coreutils `timeout`) or a timeout `exception_info` are all
recorded as `timeout` rather than as failure.

Every command reads its body through `head -c`, and the body-reading exit status is the status the executor
reports, so a failed read can never be recorded as a clean capture; in addition a recorded body whose byte
count disagrees with the container-reported full byte count degrades the section to `failed`.
"""
from __future__ import annotations
import json
import re
import shlex
import sys
import time
from collections.abc import Mapping
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import workspace_capture as WC  # noqa: E402  reused unmodified (TREE_CMD, SHA, write_once)

REQUEST = 'DTR-REQ-005'
BINDING = 'xc1'
WORKDIR = WC.WORKDIR
OUTPUT_NAME = 'exit_diagnostic.json'
FORBIDDEN_OUTPUT_NAMES = frozenset({'submission.diff', 'submission.patch'})
FORBIDDEN_OUTPUT_SUFFIXES = frozenset({'.diff', '.patch'})
PER_COMMAND_TIMEOUT_S = 60          # declared executor contract (pilot CMD_TIMEOUT), enforced by the executor
TOTAL_BUDGET_S = 300                # enforced here, before every command
DEFAULT_CAPS = dict(status_bytes=65536, diff_bytes=262144, untracked_list_bytes=65536, untracked_paths=64,
                    untracked_content_files=16, untracked_file_bytes=32768, path_chars=512, command_log=64)
CAPS_NOT_A_MAPPING = ('declared caps ignored: not a mapping of cap name to a non-negative integer; '
                      'the defaults above apply')
DEGRADED = ('unavailable', 'failed', 'timeout', 'incomplete')
CHANGE_SECTIONS = ('status', 'diff', 'untracked')
SECTION_NAMES = ('tree', 'status', 'diff', 'untracked')
NOT_REACHED = 'section not reached: the capture did not complete'
DIGEST_SCOPE = 'sha256 over the FULL in-container body before truncation, not over the recorded text'
FILE_DIGEST_SCOPE = 'sha256 over the FULL file content before truncation, not over the recorded content'
EXCLUSIONS = ('gitignored paths (excluded by `git add -A` under the private index and by `--exclude-standard`)',
              'anything outside the container workdir',
              'untracked directories are represented by their files only',
              'untracked non-regular files (sockets, symlinks, directories) get no digest or contents',
              'binary untracked contents are omitted; the full-content digest is still recorded',
              'contents/paths beyond the recorded caps are counted but not recorded')

META = re.compile(r'^DTR-XC1-META bytes=(\d+)(?: sha256=([0-9a-f]{64}))?$')
PREAMBLE_CHARS = 300
_DIGEST = ('h=$(sha256sum "%(f)s" 2>/dev/null | cut -c1-64); '
           'if [ -z "$h" ]; then h=$(shasum -a 256 "%(f)s" | cut -c1-64); fi')
_TMP_META = 'b=$(wc -c <"$t" | tr -d " "); ' + (_DIGEST % dict(f='$t')) + '; echo "DTR-XC1-META bytes=$b sha256=$h"'
# `head`'s own exit status is the compound command's status: a failed body read is never a clean capture.
_TMP_BODY = 'head -c %(limit)d "$t"; hrc=$?; rm -f "$t"; exit $hrc'

STATUS_CMD = ('cd %(wd)s && t="$(mktemp)" && git status --porcelain --untracked-files=all >"$t"; rc=$?; '
              'if [ $rc -ne 0 ]; then rm -f "$t"; exit $rc; fi; ' + _TMP_META + '; ' + _TMP_BODY)
DIFF_TREE_CMD = ('cd %(wd)s && t="$(mktemp)" && git diff --binary --full-index %(base)s %(final)s >"$t"; '
                 'rc=$?; if [ $rc -ne 0 ]; then rm -f "$t"; exit $rc; fi; ' + _TMP_META + '; ' + _TMP_BODY)
DIFF_WORKTREE_CMD = ('cd %(wd)s && t="$(mktemp)" && git diff --binary --full-index %(base)s >"$t"; '
                     'rc=$?; if [ $rc -ne 0 ]; then rm -f "$t"; exit $rc; fi; ' + _TMP_META + '; ' + _TMP_BODY)
LIST_CMD = ('cd %(wd)s && t="$(mktemp)" && git ls-files --others --exclude-standard -z >"$t"; rc=$?; '
            'if [ $rc -ne 0 ]; then rm -f "$t"; exit $rc; fi; b=$(wc -c <"$t" | tr -d " "); '
            'echo "DTR-XC1-META bytes=$b"; ' + _TMP_BODY)
FILE_CMD = ('cd %(wd)s && p=%(path)s; if [ ! -f "$p" ]; then exit 3; fi; b=$(wc -c <"$p" | tr -d " "); '
            + (_DIGEST % dict(f='$p')) + '; echo "DTR-XC1-META bytes=$b sha256=$h"; '
            'head -c %(limit)d "$p"; exit $?')


def _is_tree_sha(value):
    """True only for a 40-hex tree SHA string. Never raises for a non-string, so a caller that hands in an
    int, bytes or Path cannot break the capture (and therefore cannot block cleanup)."""
    return isinstance(value, str) and bool(WC.SHA.match(value))


def _normalize(result):
    """Executor result -> (state, returncode, output, contract_error).

    Accepts (rc, out) or mini-swe-agent's dict. Any other shape is an EXECUTOR CONTRACT failure and says
    so, so the command log can distinguish 'the container failed' from 'the injected executor has the
    wrong shape'."""
    if isinstance(result, Mapping):
        rc, out, info = result.get('returncode'), result.get('output') or '', result.get('exception_info') or ''
        if info:
            # DockerEnvironment reports a subprocess.TimeoutExpired as "... Command '...' timed out after 60 seconds".
            low = str(info).lower()
            return ('timeout' if ('timeout' in low or 'timed out' in low) else 'failed'), rc, out, None
    elif isinstance(result, (tuple, list)) and len(result) == 2:
        rc, out = result[0], (result[1] or '')
    else:
        return 'failed', None, '', ('injected executor returned %s, not (returncode, output) or a '
                                    "{'returncode','output'} mapping" % type(result).__name__)
    if rc == 124:                                   # coreutils `timeout` convention
        return 'timeout', rc, out, None
    return ('ok' if rc == 0 else 'failed'), rc, out, None


def _classify(exc):
    name = type(exc).__name__.lower()
    if isinstance(exc, TimeoutError) or 'timeout' in name or 'expired' in name:
        return 'timeout'
    text = str(exc).lower()
    return 'timeout' if ('timed out' in text or 'timeout' in text) else 'failed'


def _meta(text):
    """Split the DTR-XC1-META header from a bounded body.

    The header is the FIRST line that matches the sentinel, not necessarily the first line of output: an
    executor or container that prefixes a warning line must not demote a successful capture. Anything
    before the header is returned as the preamble (recorded, bounded) rather than silently dropped.
    Returns (full_bytes, sha256, body, preamble) or (None, None, None, None)."""
    text = text or ''
    position = 0
    while True:
        newline = text.find('\n', position)
        if newline < 0:
            return None, None, None, None
        match = META.match(text[position:newline].strip())
        if match:
            return int(match.group(1)), match.group(2), text[newline + 1:], text[:position]
        position = newline + 1


def _bounded(text, cap):
    """Locally clamp a body that the container already byte-capped (defense in depth)."""
    return (text[:cap], True) if len(text) > cap else (text, False)


def _body_bytes(text):
    return len((text or '').encode('utf-8', 'surrogateescape'))


def _body_mismatch(text, full_bytes, cap):
    """A recorded body that disagrees with the container's own byte count is NOT a clean capture."""
    recorded = _body_bytes(text)
    if full_bytes <= cap:
        if recorded != full_bytes:
            return ('recorded body is %d bytes but the container reported %d full bytes; the recorded text '
                    'is not the observation' % (recorded, full_bytes))
    elif recorded > cap:
        return ('recorded body is %d bytes, beyond the declared %d-byte cap' % (recorded, cap))
    return None


def _safe_rel(path, cap_chars):
    if not path or len(path) > cap_chars or path.startswith('/'):
        return False
    if any(c in path for c in ('\x00', '\n', '\r')):
        return False
    return not (path == '..' or path.startswith('../') or '/../' in path or path.endswith('/..'))


def resolve_caps(caps):
    """(limits, caps_error). Every declared bound is validated: a malformed VALUE is ignored and named,
    not published as the declared bound. Unknown cap names are named too."""
    limits, problems = dict(DEFAULT_CAPS), []
    if caps is None:
        return limits, None
    if not isinstance(caps, Mapping):
        return limits, CAPS_NOT_A_MAPPING
    for name in sorted(caps, key=str):
        value = caps[name]
        if name not in DEFAULT_CAPS:
            problems.append('unknown cap %r ignored' % (name,))
        elif isinstance(value, bool) or not isinstance(value, int) or value < 0:
            problems.append('cap %r=%r ignored (a non-negative integer is required); the default %d applies'
                            % (name, value, DEFAULT_CAPS[name]))
        else:
            limits[name] = value
    return limits, ('; '.join(problems) or None)


class _Runner:
    """Bounded command dispatcher: budget check before every command, every command logged, nothing raised."""

    def __init__(self, execute, budget_s, clock, cap_log):
        self.execute, self.clock, self.cap_log = execute, clock, cap_log
        self.deadline = clock() + budget_s
        self.commands, self.dropped_log_entries = [], 0

    def _log(self, entry):
        if len(self.commands) < self.cap_log:
            self.commands.append(entry)
        else:
            self.dropped_log_entries += 1

    def run(self, label, command):
        """Returns (state, returncode, output); state is 'ok', 'failed' or 'timeout'."""
        t0 = self.clock()
        if t0 >= self.deadline:
            self._log(dict(label=label, state='timeout', reason='total diagnostic budget exhausted before dispatch'))
            return 'timeout', None, ''
        try:
            state, rc, out, contract_error = _normalize(self.execute(command))
            reason = contract_error
        except (KeyboardInterrupt, SystemExit):
            raise
        except Exception as e:  # noqa: BLE001  recorded, never propagated: cleanup must not be blocked
            state, rc, out = _classify(e), None, ''
            reason = '%s: %s' % (type(e).__name__, str(e)[:300])
        entry = dict(label=label, state=state, returncode=rc, seconds=round(self.clock() - t0, 6))
        if state != 'ok':
            entry['output_tail'] = (out or '')[-300:]
            if reason:
                entry['error'] = reason
        self._log(entry)
        return state, rc, out


def _degraded_section(state, reason, **extra):
    """A section that did not complete: no text, no byte count -- absent is never an empty observation."""
    return dict(state=state, reason=reason, text=None, full_bytes=None, sha256=None, digest_scope=None,
                truncated=None, recorded_chars=None, container_preamble=None, incomplete_reason=None, **extra)


def _untracked_base(caps):
    return dict(paths=None, n_paths=None, n_recorded=None, n_with_content=None, n_with_digest=None,
                paths_complete=None, cap_list_bytes=caps['untracked_list_bytes'],
                cap_paths=caps['untracked_paths'], cap_content_files=caps['untracked_content_files'],
                cap_file_bytes=caps['untracked_file_bytes'], list_truncated=None, path_cap_reached=None,
                partial_path_dropped=None, n_paths_is_lower_bound=None, incomplete_reason=None,
                container_preamble=None)


def _placeholder_sections(caps):
    """Every section key exists from the start, so a consumer never sees a missing key after an internal
    error -- it sees a degraded state with a reason."""
    return dict(tree=dict(state='unavailable', sha=None, reason=NOT_REACHED, incomplete_reason=None),
                status=_degraded_section('unavailable', NOT_REACHED, cap_bytes=caps['status_bytes']),
                diff=_degraded_section('unavailable', NOT_REACHED, cap_bytes=caps['diff_bytes'], mode=None,
                                       base_tree=None, final_tree=None),
                untracked=dict(_untracked_base(caps), state='unavailable', reason=NOT_REACHED))


def _tree(runner, wd):
    state, rc, out = runner.run('tree', WC.TREE_CMD.format(wd=wd))
    sha = (out or '').strip().splitlines()[-1].strip() if (out or '').strip() else ''
    if state != 'ok':
        return dict(state=state, sha=None, reason='final tree snapshot did not complete (rc=%s)' % rc,
                    incomplete_reason=None)
    if not _is_tree_sha(sha):
        return dict(state='failed', sha=None, reason='tree command returned no 40-hex tree SHA',
                    incomplete_reason=None)
    return dict(state='captured', sha=sha, reason=None, incomplete_reason=None)


def _bounded_section(runner, label, command, cap):
    """Shared shape for status/diff: DTR-XC1-META header (full bytes + digest) plus a byte-capped body."""
    state, rc, out = runner.run(label, command)
    if state != 'ok':
        return _degraded_section(state, '%s did not complete (rc=%s)' % (label, rc), cap_bytes=cap)
    full_bytes, digest, body, preamble = _meta(out)
    if full_bytes is None:
        return _degraded_section('failed', '%s produced no parsable bound header' % label, cap_bytes=cap)
    text, clamped = _bounded(body, cap)
    mismatch = _body_mismatch(text, full_bytes, cap)
    if mismatch is not None:
        return _degraded_section('failed', '%s body is not consistent with its own bound header: %s'
                                 % (label, mismatch), cap_bytes=cap, full_bytes_reported=full_bytes,
                                 sha256_reported=digest)
    return dict(state='no_change' if full_bytes == 0 else 'captured', reason=None, text=text,
                full_bytes=full_bytes, sha256=digest, digest_scope=DIGEST_SCOPE if digest else None,
                truncated=bool(full_bytes > cap or clamped), cap_bytes=cap, recorded_chars=len(text),
                container_preamble=(preamble[:PREAMBLE_CHARS] or None), incomplete_reason=None)


def _diff(runner, base, final_tree, wd, cap):
    if not _is_tree_sha(base):
        return _degraded_section('unavailable', 'no recorded starting tree for this episode', cap_bytes=cap,
                                 mode=None, base_tree=base if isinstance(base, str) else None,
                                 final_tree=final_tree if isinstance(final_tree, str) else None)
    if _is_tree_sha(final_tree):
        mode = 'tree_to_tree'
        cmd = DIFF_TREE_CMD % dict(wd=shlex.quote(wd), base=base, final=final_tree, limit=cap)
    else:
        mode = 'base_to_worktree'
        cmd = DIFF_WORKTREE_CMD % dict(wd=shlex.quote(wd), base=base, limit=cap)
    section = _bounded_section(runner, 'diff', cmd, cap)
    section.update(mode=mode, base_tree=base, final_tree=final_tree if mode == 'tree_to_tree' else None)
    if section['state'] in DEGRADED:
        section['reason'] = 'tracked diff (%s) did not complete: %s' % (mode, section['reason'])
    return section


def _untracked(runner, wd, caps):
    cap_list, cap_paths = caps['untracked_list_bytes'], caps['untracked_paths']
    state, rc, out = runner.run('untracked_list', LIST_CMD % dict(wd=shlex.quote(wd), limit=cap_list))
    base = _untracked_base(caps)
    if state != 'ok':
        return dict(base, state=state, reason='untracked listing did not complete (rc=%s)' % rc)
    full_bytes, _digest, body, preamble = _meta(out)
    if full_bytes is None:
        return dict(base, state='failed', reason='untracked listing produced no parsable bound header')
    truncated = full_bytes > cap_list or _body_bytes(body) > cap_list
    parts = body.split('\x00')
    tail = parts.pop() if parts else ''                       # `-z` terminates every path; a remainder is partial
    paths = [p for p in parts if p]
    complete = not truncated and not tail
    incomplete_reason = None
    if not complete:
        incomplete_reason = ('the untracked listing is incomplete (%s): the recorded paths are a subset and '
                             'n_paths is a lower bound, not an observation of how many exist'
                             % ('; '.join(filter(None, [
                                 'byte-truncated at the %d-byte list cap' % cap_list if truncated else None,
                                 'a partial trailing path was dropped' if tail else None]))))
    recorded, capped = paths[:cap_paths], len(paths) > cap_paths
    entries = []
    for i, path in enumerate(recorded):
        entries.append(_untracked_entry(runner, wd, path, caps, with_content=i < caps['untracked_content_files']))
    if paths:
        section_state = 'captured'
    else:
        section_state = 'no_change' if complete else 'incomplete'
    return dict(base, state=section_state,
                reason=None if section_state != 'incomplete' else incomplete_reason,
                paths=entries, n_paths=len(paths), n_recorded=len(recorded),
                n_with_content=sum(e['content'] is not None for e in entries),
                n_with_digest=sum(e['sha256'] is not None for e in entries),
                paths_complete=complete, list_truncated=truncated, path_cap_reached=capped,
                partial_path_dropped=bool(tail), n_paths_is_lower_bound=not complete,
                incomplete_reason=incomplete_reason,
                container_preamble=(preamble[:PREAMBLE_CHARS] or None))


def _untracked_entry(runner, wd, path, caps, with_content):
    cap = caps['untracked_file_bytes']
    entry = dict(path=None, path_chars=len(path), bytes=None, sha256=None, digest_scope=None, content=None,
                 truncated=None, cap_bytes=cap, content_state='not_requested', reason=None)
    if not _safe_rel(path, caps['path_chars']):
        # No prefix of an unsafe/oversized path is published: a truncated prefix would read as a real path
        # under a claim that nothing was recorded.
        return dict(entry, content_state='unavailable',
                    reason='path not recorded: unsafe or beyond the %d-character path cap'
                           % caps['path_chars'])
    entry['path'] = path
    if not with_content:
        return dict(entry, reason='beyond the recorded content-file cap; path counted only')
    state, rc, out = runner.run('untracked_file', FILE_CMD % dict(wd=shlex.quote(wd), path=shlex.quote('./' + path),
                                                                 limit=cap))
    if state != 'ok':
        return dict(entry, content_state=state if state != 'failed' else ('unavailable' if rc == 3 else 'failed'),
                    reason='content/digest did not complete (rc=%s)' % rc)
    full_bytes, digest, body, _preamble = _meta(out)
    if full_bytes is None:
        return dict(entry, content_state='failed', reason='no parsable bound header for this file')
    text, clamped = _bounded(body, cap)
    truncated = bool(full_bytes > cap or clamped)
    mismatch = _body_mismatch(text, full_bytes, cap)
    if mismatch is not None and '\x00' not in text:
        return dict(entry, bytes=full_bytes, sha256=digest, digest_scope=FILE_DIGEST_SCOPE,
                    content_state='failed', truncated=truncated,
                    reason='recorded content is not consistent with its own bound header: %s' % mismatch)
    if '\x00' in text:
        return dict(entry, bytes=full_bytes, sha256=digest, digest_scope=FILE_DIGEST_SCOPE,
                    truncated=truncated, content_state='binary_omitted',
                    reason='binary content omitted; digest is of the full content')
    return dict(entry, bytes=full_bytes, sha256=digest, digest_scope=FILE_DIGEST_SCOPE, content=text,
                truncated=truncated, content_state='truncated' if truncated else 'recorded')


def _rollup(sections):
    """`no_change` requires ALL THREE change signals to have completed and observed nothing.

    The status snapshot is one of those signals: in `base_to_worktree` mode `git diff <base>` cannot see a
    new untracked file, so ignoring a porcelain line that says `?? new.py` would assert
    changes_observed=False for an episode that created a file -- the 'unobserved is not observed-empty'
    error this request exists to remove."""
    states = {name: sections[name]['state'] for name in SECTION_NAMES}
    signals = [states[name] for name in CHANGE_SECTIONS]
    if 'captured' in signals:
        changes = True
    elif all(s == 'no_change' for s in signals):
        changes = False
    else:
        changes = None
    bad = [name for name in SECTION_NAMES if states[name] in DEGRADED]
    partial = [name for name in SECTION_NAMES if sections[name].get('incomplete_reason')]
    if not bad:
        if partial:
            return 'partial', changes
        return ('changed' if changes else 'no_change'), changes
    if len(bad) == len(SECTION_NAMES):
        distinct = set(states.values())
        return (distinct.pop() if len(distinct) == 1 else 'degraded'), changes
    return 'partial', changes


def _failures(sections):
    out = []
    for name in SECTION_NAMES:
        section = sections[name]
        if section['state'] in DEGRADED:
            out.append(dict(section=name, state=section['state'], reason=section.get('reason')))
        elif section.get('incomplete_reason'):
            out.append(dict(section=name, state=section['state'], reason=section['incomplete_reason']))
    return out


def capture(execute, base_tree, *, exit_status=None, wd=WORKDIR, caps=None, budget_s=TOTAL_BUDGET_S,
            per_command_timeout_s=PER_COMMAND_TIMEOUT_S, clock=time.time):
    """Bounded all-exit diagnostic record. Never raises Exception; every gap is a recorded state, and every
    section key is present even when the capture breaks internally."""
    limits, caps_error = resolve_caps(caps)
    rec = dict(kind='all-exit diagnostic capture: evidence only, never a submission and never graded',
               request=REQUEST, binding=BINDING, exit_status=exit_status, workdir=wd,
               endpoint=dict(writes_submission_diff=False, marks_submitted=False, graded=False,
                             changes_eligibility=False, changes_endpoint_bytes=False, output_file=OUTPUT_NAME),
               base_tree=base_tree if isinstance(base_tree, str) else None,
               base_tree_state='recorded' if _is_tree_sha(base_tree) else 'unavailable',
               caps=limits, caps_error=caps_error, per_command_timeout_s=per_command_timeout_s,
               per_command_timeout_enforced_by='injected executor', total_budget_s=budget_s,
               exclusions=list(EXCLUSIONS), captured_at=None, status='unavailable', changes_observed=None,
               sections=_placeholder_sections(limits), commands=[], failures=[], dropped_log_entries=0,
               capture_error=None)
    runner = None
    try:
        rec['captured_at'] = clock()
        runner = _Runner(execute, budget_s, clock, limits['command_log'])
        sections = rec['sections']
        sections['tree'] = tree = _tree(runner, wd)
        sections['status'] = _bounded_section(runner, 'status', STATUS_CMD % dict(wd=shlex.quote(wd),
                                             limit=limits['status_bytes']), limits['status_bytes'])
        sections['diff'] = _diff(runner, base_tree, tree['sha'], wd, limits['diff_bytes'])
        sections['untracked'] = _untracked(runner, wd, limits)
        rec['status'], rec['changes_observed'] = _rollup(sections)
        rec['failures'] = _failures(sections)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:  # noqa: BLE001  the diagnostic itself must never block cleanup
        rec['capture_error'] = '%s: %s' % (type(e).__name__, str(e)[:300])
        rec.update(status='failed', changes_observed=None,
                   failures=[dict(section='capture', state='failed', reason=rec['capture_error'])]
                   + _failures(rec['sections']))
    finally:
        if runner is not None:
            rec['commands'] = runner.commands
            rec['dropped_log_entries'] = runner.dropped_log_entries
    return rec


def write_diagnostic(path, record):
    """Write-once JSON. Refuses the endpoint filenames outright (case-insensitively, and any `.diff` or
    `.patch` suffix): the diagnostic never enters submission.diff."""
    p = Path(path)
    if p.is_dir():
        p = p / OUTPUT_NAME
    if p.name.lower() in FORBIDDEN_OUTPUT_NAMES or p.suffix.lower() in FORBIDDEN_OUTPUT_SUFFIXES:
        raise ValueError('the exit diagnostic must never be written to the endpoint file %r' % p.name)
    WC.write_once(p, json.dumps(record, indent=1) + '\n')
    return p


def capture_exit_diagnostic(execute, base_tree, exit_status=None, out_dir=None, **kw):
    """Caller entry used before container cleanup on EVERY exit. Never raises Exception; cleanup always proceeds.

    The written file records `write.state == 'attempted'`; the returned record carries the observed outcome
    ('written', 'refused_existing', 'refused_endpoint_path', 'refused_missing_out_dir', 'failed',
    'not_requested'). `out_dir` must be an EXISTING directory: a nonexistent path is refused rather than
    silently written as a file named after the intended directory.
    """
    try:
        record = capture(execute, base_tree, exit_status=exit_status, **kw)
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as e:  # noqa: BLE001  cleanup must proceed even on a programming error above
        return dict(kind='all-exit diagnostic capture: evidence only, never a submission and never graded',
                    request=REQUEST, binding=BINDING, exit_status=exit_status, status='failed',
                    changes_observed=None, sections={}, commands=[],
                    capture_error='%s: %s' % (type(e).__name__, str(e)[:300]),
                    failures=[dict(section='capture', state='failed',
                                   reason='%s: %s' % (type(e).__name__, str(e)[:300]))],
                    write=dict(state='not_requested', file=None))
    if out_dir is None:
        return dict(record, write=dict(state='not_requested', file=None))
    directory = Path(out_dir)
    if not directory.is_dir():
        return dict(record, write=dict(state='refused_missing_out_dir', file=None,
                                       reason='out_dir %r is not an existing directory; the diagnostic is '
                                              'never written as a file named after it' % directory.name))
    target = directory / OUTPUT_NAME
    record['write'] = dict(state='attempted', file=target.name)
    try:
        written = write_diagnostic(target, record)
        return dict(record, write=dict(state='written', file=written.name))
    except (KeyboardInterrupt, SystemExit):
        raise
    except FileExistsError:
        return dict(record, write=dict(state='refused_existing', file=OUTPUT_NAME,
                                       reason='an exit diagnostic already exists; records are write-once'))
    except ValueError as e:
        return dict(record, write=dict(state='refused_endpoint_path', file=None, reason=str(e)[:300]))
    except Exception as e:  # noqa: BLE001
        return dict(record, write=dict(state='failed', file=None,
                                       reason='%s: %s' % (type(e).__name__, str(e)[:300])))
