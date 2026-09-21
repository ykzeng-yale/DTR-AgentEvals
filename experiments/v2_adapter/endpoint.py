"""DTR-REQ-002: episode endpoint mapper implementing decisions already made (protocol section 5; contract A09-A11;
lead d1d9de6 strict verified resolution). It adds no new rule; anything outside these rules raises instead of guessing.

  qualification  an episode on an M02-refused instance is an error (qualification precedes sampling)
  submission     empty -> primary 0, 'not_evaluated_empty'; evaluation attempts on an empty submission are an error
  attempts       at most 2, all on the IDENTICAL patch hash; the second is allowed only after an evaluator failure
                 (a retry after a valid report would be re-grading shopping)
  strict grade   from the parsed status map: every declared F2P and P2P test observed PASSED (grading_conformance)
  failures       all attempts failed -> primary 0, 'unknown_evaluator_failure', secondary algorithmic bounds [0, 1]
  upstream       the pinned upstream 'resolved' flag is preserved and any disagreement is flagged, never overwritten
Pure function over recorded data; nothing is executed.
"""
from __future__ import annotations

from grading_conformance import declared_outcome

VALID, FAILURE_KINDS = 'report', ('timeout', 'error', 'missing_report', 'bad_log')


class EndpointError(ValueError):
    pass


def score_episode(qualification, submission_sha256, attempts, f2p, p2p):
    """attempts: list of dicts {kind, patch_sha256, status_map?, log_ok?, upstream_resolved?} in execution order."""
    if qualification.get('status') != 'eligible':
        raise EndpointError('episode exists for an instance refused at qualification: %s' % qualification.get('reasons'))
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
    for a in attempts:
        if a['kind'] != VALID and a['kind'] not in FAILURE_KINDS:
            raise EndpointError('unknown attempt kind %r' % a['kind'])
    if len(attempts) == 2 and attempts[0]['kind'] == VALID:
        raise EndpointError('retry after a valid report is not allowed')
    final = attempts[-1]
    if final['kind'] != VALID:
        return dict(primary=0, algorithmic='unknown_evaluator_failure', secondary_bounds=[0, 1], upstream_resolved=None,
                    disagreement=None, attempts_used=len(attempts))
    strict = declared_outcome(f2p, p2p, final.get('status_map') or {}, final.get('log_ok', True))
    up = final.get('upstream_resolved')
    return dict(primary=1 if strict == 'resolved' else 0, algorithmic=strict,
                secondary_bounds=[0, 1] if strict.startswith('unknown') else None,
                upstream_resolved=up, disagreement=None if up is None else (up != (strict == 'resolved')),
                attempts_used=len(attempts))
