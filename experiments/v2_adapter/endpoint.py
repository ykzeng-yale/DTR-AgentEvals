"""DTR-REQ-002: episode endpoint mapper implementing decisions already made (protocol section 5; contract A09-A11;
lead d1d9de6 strict verified resolution), with a fail-closed input contract (repaired after lead review 8eb727a).

Two layers:
  bind_instance(instance, qualification)   INTEGRATION-LAYER binding: re-runs M02 on the instance and requires the
                                           recorded qualification to match exactly; returns the parsed, unrewritten
                                           F2P/P2P lists. A changed qualified-test list is caught HERE.
  score_episode(qualification, submission_sha256, attempts, f2p, p2p)
                                           SCORER boundary: the lists must be well formed, F2P non-empty, and hash-equal
                                           to the lists recorded in the qualification (an arbitrary 'eligible' label with
                                           no hashes is rejected); every attempt must match one canonical schema.
Canonical attempt schema: {kind, patch_sha256, ...}. kind 'report' REQUIRES log_ok is True (a Boolean, explicitly) and
a mapping status_map of str -> str; upstream_resolved is a Boolean or None. Failure kinds ('timeout', 'error',
'missing_report', 'bad_log') must not carry log_ok=True or a status map. A report with log_ok False is contradictory:
the adapter must record it as kind 'bad_log'; past records are never rewritten to create an extra retry.
Scoring rules (unchanged): empty submission -> 0 'not_evaluated_empty'; at most one retry, identical patch, only after
an evaluator failure; strict re-grade (every declared F2P and P2P test observed PASSED); valid log with an empty parsed
map -> 0 'unknown_unparsable_output'; all failures -> 0 'unknown_evaluator_failure', bounds [0, 1]; upstream flag kept
and disagreement flagged.
EndpointError means a CONTRACT VIOLATION: at runtime it blocks final analysis and triggers record repair/audit while the
assigned episode is RETAINED. It is never a reason for complete-case exclusion. Pure function; nothing is executed.
"""
from __future__ import annotations

from grading_conformance import declared_outcome
import qualify_instances as Q

VALID, FAILURE_KINDS = 'report', ('timeout', 'error', 'missing_report', 'bad_log')


class EndpointError(ValueError):
    pass


def bind_instance(instance, qualification):
    recomputed = Q.qualify(instance)
    if recomputed != qualification:
        raise EndpointError('qualification record does not match the instance content (changed or foreign record)')
    if recomputed['status'] != 'eligible':
        raise EndpointError('instance refused at qualification: %s' % recomputed['reasons'])
    return Q.parse_test_list(instance, 'FAIL_TO_PASS')[0], Q.parse_test_list(instance, 'PASS_TO_PASS')[0]


def _validate_lists(qualification, f2p, p2p):
    if not isinstance(qualification, dict) or qualification.get('status') != 'eligible':
        raise EndpointError('episode exists for an instance not qualified as eligible')
    parsed = {}
    for key, value in (('FAIL_TO_PASS', f2p), ('PASS_TO_PASS', p2p)):
        lst, why = Q.parse_test_list({key: value}, key)
        if why:
            raise EndpointError('invalid required-test input: %s' % why)
        parsed[key] = lst
    if not parsed['FAIL_TO_PASS']:
        raise EndpointError('empty FAIL_TO_PASS: a vacuous all-tests condition is never scored')
    for key, field in (('FAIL_TO_PASS', 'fail_to_pass_sha256'), ('PASS_TO_PASS', 'pass_to_pass_sha256')):
        if qualification.get(field) is None or Q.list_sha256(parsed[key]) != qualification[field]:
            raise EndpointError('%s is not the list recorded at qualification' % key)
    return parsed['FAIL_TO_PASS'], parsed['PASS_TO_PASS']


def _validate_attempt(a):
    if not isinstance(a, dict) or not isinstance(a.get('patch_sha256'), str):
        raise EndpointError('attempt record malformed: %r' % (a,))
    kind = a.get('kind')
    if kind == VALID:
        if a.get('log_ok') is not True:
            raise EndpointError('report without explicit log_ok=True (a failed log must be recorded as kind bad_log)')
        sm = a.get('status_map')
        if not isinstance(sm, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in sm.items()):
            raise EndpointError('report status_map is not a mapping of test id -> status')
        if a.get('upstream_resolved') not in (None, True, False):
            raise EndpointError('upstream_resolved must be a Boolean or None')
    elif kind in FAILURE_KINDS:
        if a.get('log_ok') is True or a.get('status_map'):
            raise EndpointError('failure record carries a valid log or a status map: contradictory')
    else:
        raise EndpointError('unknown attempt kind %r' % (kind,))


def score_episode(qualification, submission_sha256, attempts, f2p, p2p):
    f2p, p2p = _validate_lists(qualification, f2p, p2p)
    for a in attempts:
        _validate_attempt(a)
    if submission_sha256 is None:
        if attempts:
            raise EndpointError('evaluation attempted on an empty submission')
        return dict(primary=0, algorithmic='not_evaluated_empty', secondary_bounds=None, upstream_resolved=None,
                    disagreement=None, attempts_used=0)
    if not attempts:
        raise EndpointError('non-empty submission without any evaluation attempt recorded')
    if len(attempts) > 2:
        raise EndpointError('more than one evaluator retry')
    if any(a['patch_sha256'] != submission_sha256 for a in attempts):
        raise EndpointError('evaluation attempt on a patch other than the submission')
    if len(attempts) == 2 and attempts[0]['kind'] == VALID:
        raise EndpointError('retry after a valid report is not allowed')
    final = attempts[-1]
    if final['kind'] != VALID:
        return dict(primary=0, algorithmic='unknown_evaluator_failure', secondary_bounds=[0, 1], upstream_resolved=None,
                    disagreement=None, attempts_used=len(attempts))
    strict = declared_outcome(f2p, p2p, final['status_map'], True)
    up = final.get('upstream_resolved')
    return dict(primary=1 if strict == 'resolved' else 0, algorithmic=strict,
                secondary_bounds=[0, 1] if strict.startswith('unknown') else None,
                upstream_resolved=up, disagreement=None if up is None else (up != (strict == 'resolved')),
                attempts_used=len(attempts))
