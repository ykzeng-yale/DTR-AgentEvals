"""DTR-REQ-002 (lead 7f9673a): separately versioned CONTROL ADAPTER boundary for the pre-sampling qualification controls.
NON-EXECUTING preparation: this module defines the call sequence and the qualification rule against an abstract runtime
interface. It imports no container, subprocess or SWE-bench code; a real runtime binding is written only on an approved
x86_64 host. Static tests use a fake runtime; they cannot establish equivalence with the pinned stock gold path, which
the future runtime check must do (reference mode vs unmodified `--predictions_path gold` on the same task/image).

Modes (same digest-pinned instance image and base commit, same M01 hash-checked eval script, invoked EXACTLY ONCE per
attempt; the script performs its own test-patch/reset sequence):
  no_change   bypasses ONLY prediction application (patch_application = 'not_applicable'); no fabricated patch, no
              reliance on empty git-apply behaviour, no second test-patch application, no test edits
  reference   applies the dataset reference patch through the pinned application step before the eval script; an
              application failure is a setup failure (the eval script is not run, as in the pinned sequence)
Qualification (lead 7f9673a; sharpens the infrastructure gate, rescored nothing):
  both        completed, interpretable execution (no timeout, report/log present and parsed, no evaluator/setup failure)
              and every required F2P/P2P identity accounted for; otherwise 'diagnose' (never a silent exclusion)
  no_change   all required P2P observed PASSED (unless the predeclared empty-P2P limitation applies), EVERY required
              F2P status in the allowlist {PASSED, FAILED} (anything else - ERROR, SKIPPED, XFAIL, XPASS, None, unknown
              strings - is retained raw and gives 'diagnose'), and at least one F2P FAILED -> 'qualified'; a false strict
              score alone is NOT sufficient; all-F2P-passing baseline -> 'diagnose' (negative control not demonstrated)
  reference   every required F2P and P2P observed PASSED (M03 strict rule) -> 'qualified'; otherwise 'diagnose'
Completion gate (lead c85173a): the parser binding returns (statuses, completion_ok, note); evaluator/setup-failure or
invalid completion markers make the attempt 'invalid_completion' even if test lines parse - a nonempty status map alone
never establishes completion. A nonzero eval-script exit is NOT by itself an evaluator failure (expected baseline test
failures produce it).
Operational retry rule preserved: a timeout, missing/unparsable report or invalid completion gets exactly one retry with identical inputs;
both attempts are recorded.
"""
from __future__ import annotations
import hashlib
from pathlib import Path

from grading_conformance import declared_outcome, PASSED, FAILED, SKIPPED, ERROR, XFAIL

ADAPTER_VERSION = 'control-adapter-v2 (lead 7f9673a; F2P allowlist and completion gate per c85173a)'
MODES = ('no_change', 'reference')
F2P_ALLOWED = {PASSED, FAILED}          # explicit allowlist (lead c85173a): anything else is ambiguous -> diagnose


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def adapter_source_sha256():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


class Runtime:
    """Abstract boundary implemented only on an approved runtime. Every method is called by run_control in a fixed order."""
    def start(self, image_digest): raise NotImplementedError
    def repo_state(self, handle): raise NotImplementedError             # e.g. hash of `git status --porcelain` + HEAD
    def apply_patch(self, handle, patch_text): raise NotImplementedError  # returns (ok: bool, output: str)
    def run_eval_script(self, handle, script_text, timeout): raise NotImplementedError  # returns (exit_code, log_text | None, timed_out)
    def stop(self, handle): raise NotImplementedError


class ControlRefused(ValueError):
    pass


def qualify(mode, f2p, p2p, statuses, empty_p2p_declared):
    """Qualification of ONE completed, parsed attempt. Returns (qualification, reason, strict_verified_resolved)."""
    strict = declared_outcome(f2p, p2p, statuses) == 'resolved'
    missing = [t for t in list(f2p) + list(p2p) if t not in statuses]
    if missing:
        return 'diagnose', 'missing required test identities: %d' % len(missing), strict
    if mode == 'reference':
        return ('qualified', 'every required test PASSED', strict) if strict else ('diagnose', 'reference not strictly resolved', strict)
    if not p2p and not empty_p2p_declared:
        return 'diagnose', 'empty PASS_TO_PASS without the declared limitation', strict
    if any(statuses[t] != PASSED for t in p2p):
        return 'diagnose', 'a required PASS_TO_PASS test was not PASSED at baseline', strict
    bad = {t: statuses[t] for t in f2p if statuses[t] not in F2P_ALLOWED}
    if bad:
        return 'diagnose', 'FAIL_TO_PASS status outside {PASSED, FAILED} retained raw for diagnosis: %r' % sorted(bad.items(), key=str), strict
    if not any(statuses[t] == FAILED for t in f2p):
        return 'diagnose', 'no FAIL_TO_PASS test observed FAILED: negative control not demonstrated', strict
    return 'qualified', 'baseline F2P failure observed with P2P passing', strict


def run_control(mode, instance, runtime, eval_script, parse_log, image_digests, reference_patch=None, timeout=1800):
    """One control for one instance. `instance` needs instance_id, eval_script_sha256 (M01), FAIL_TO_PASS, PASS_TO_PASS,
    empty_p2p_declared. `parse_log` is the pinned log parser binding:
    log_text -> (statuses {test_id: status} or None, completion_ok: bool, note); completion_ok must be False for
    evaluator/setup-failure or invalid completion markers, even if individual test lines parse."""
    if mode not in MODES:
        raise ControlRefused('mode must be no_change or reference')
    if sha(eval_script) != instance['eval_script_sha256']:
        raise ControlRefused('eval script hash differs from the M01 record for %s' % instance['instance_id'])
    if mode == 'reference' and not reference_patch:
        raise ControlRefused('reference mode needs the dataset reference patch')
    if mode == 'no_change' and reference_patch is not None:
        raise ControlRefused('no_change mode takes no patch')
    if not image_digests.get('instance'):
        raise ControlRefused('instance image digest must be resolved and recorded before a control')
    rec = dict(adapter_version=ADAPTER_VERSION, adapter_source_sha256=adapter_source_sha256(), instance_id=instance['instance_id'],
               control_mode=mode, prediction_identity='no_prediction' if mode == 'no_change' else 'dataset_reference_patch',
               patch_sha256=None if mode == 'no_change' else sha(reference_patch), eval_script_sha256=sha(eval_script),
               image_digests=dict(image_digests), attempts=[],
               report_scope=('qualification control only: no prediction applied; not an official submission or model observation'
                             if mode == 'no_change' else 'qualification control with the dataset reference patch'))
    for attempt in (1, 2):
        a = dict(attempt=attempt)
        h = runtime.start(image_digests['instance'])
        try:
            a['repo_state_pre'] = runtime.repo_state(h)
            if mode == 'no_change':
                a['patch_application'] = 'not_applicable'
            else:
                ok, out = runtime.apply_patch(h, reference_patch)
                a['patch_application'] = 'applied' if ok else 'failed'
                a['patch_output_sha256'] = sha(out or '')
                if not ok:
                    a['evaluation_status'] = 'setup_failure'
                    rec['attempts'].append(a)
                    break                                   # pinned sequence: no eval script after a failed application
            code, log, timed_out = runtime.run_eval_script(h, eval_script, timeout)
            a['exit_code'], a['timed_out'] = code, timed_out
            a['log_sha256'] = sha(log) if log is not None else None
            a['repo_state_post'] = runtime.repo_state(h)
        finally:
            runtime.stop(h)
        statuses, completion_ok, note = parse_log(log) if (log is not None and not timed_out) else (None, False, 'no log')
        a['per_test_status'], a['completion_ok'], a['completion_note'] = statuses, completion_ok, note
        if timed_out:
            a['evaluation_status'] = 'timeout'
        elif not statuses:
            a['evaluation_status'] = 'missing_or_unparsable_report'
        elif not completion_ok:
            a['evaluation_status'] = 'invalid_completion'  # evaluator/setup-failure marker: a nonempty map is not enough
        else:
            a['evaluation_status'] = 'completed'
        rec['attempts'].append(a)
        if a['evaluation_status'] == 'completed':
            break                                          # at most one retry, only for timeout / missing report / invalid completion
    last = rec['attempts'][-1]
    if last['evaluation_status'] != 'completed':
        rec.update(qualification='diagnose', reason='no completed interpretable execution: %s' % last['evaluation_status'],
                   strict_verified_resolved=None)
    else:
        q, why, strict = qualify(mode, instance['FAIL_TO_PASS'], instance['PASS_TO_PASS'], last['per_test_status'],
                                 instance.get('empty_p2p_declared', False))
        rec.update(qualification=q, reason=why, strict_verified_resolved=strict)
    return rec
