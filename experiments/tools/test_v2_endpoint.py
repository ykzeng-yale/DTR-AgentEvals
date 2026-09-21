"""Deterministic fixtures for experiments/v2_adapter/endpoint.py (decided rules only; nothing executed)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_adapter'))
import endpoint as EP  # noqa: E402

OK = {'status': 'eligible'}
F2P, P2P, SHA = ['t::a'], ['t::b'], 'p' * 64
PASS = {'t::a': 'PASSED', 't::b': 'PASSED'}


def rep(sm, up=None, kind='report', sha=SHA):
    return dict(kind=kind, patch_sha256=sha, status_map=sm, log_ok=True, upstream_resolved=up)


def test_resolved_and_agreement():
    r = EP.score_episode(OK, SHA, [rep(PASS, up=True)], F2P, P2P)
    assert (r['primary'], r['algorithmic'], r['disagreement']) == (1, 'resolved', False)


@pytest.mark.parametrize('status', ['SKIPPED', 'XFAIL'])
def test_skipped_and_xfail_are_zero_and_flag_upstream_disagreement(status):
    r = EP.score_episode(OK, SHA, [rep({**PASS, 't::a': status}, up=True)], F2P, P2P)
    assert (r['primary'], r['algorithmic'], r['disagreement']) == (0, 'unresolved', True)


def test_empty_submission_scores_zero_without_evaluation():
    assert EP.score_episode(OK, None, [], F2P, P2P)['algorithmic'] == 'not_evaluated_empty'
    with pytest.raises(EP.EndpointError):
        EP.score_episode(OK, None, [rep(PASS)], F2P, P2P)


def test_single_retry_after_failure_uses_the_retry():
    r = EP.score_episode(OK, SHA, [rep(None, kind='timeout'), rep(PASS, up=True)], F2P, P2P)
    assert (r['primary'], r['attempts_used']) == (1, 2)


def test_two_failures_are_unknown_with_bounds():
    r = EP.score_episode(OK, SHA, [rep(None, kind='timeout'), rep(None, kind='error')], F2P, P2P)
    assert (r['primary'], r['algorithmic'], r['secondary_bounds']) == (0, 'unknown_evaluator_failure', [0, 1])


def test_empty_parsed_output_is_unknown_not_failure():
    r = EP.score_episode(OK, SHA, [rep({}, up=False)], F2P, P2P)
    assert (r['primary'], r['algorithmic'], r['secondary_bounds']) == (0, 'unknown_unparsable_output', [0, 1])


@pytest.mark.parametrize('qual,sub,attempts', [
    ({'status': 'refused', 'reasons': ['FAIL_TO_PASS empty']}, SHA, [rep(PASS)]),     # refused instance sampled
    (OK, SHA, []),                                                                     # submission never evaluated
    (OK, SHA, [rep(None, kind='timeout')] * 3),                                        # more than one retry
    (OK, SHA, [rep(PASS), rep(PASS)]),                                                 # retry after a valid report
    (OK, SHA, [rep(PASS, sha='q' * 64)]),                                              # different patch evaluated
    (OK, SHA, [rep(PASS, kind='cached')]),                                             # unknown attempt kind
])
def test_rule_violations_raise(qual, sub, attempts):
    with pytest.raises(EP.EndpointError):
        EP.score_episode(qual, sub, attempts, F2P, P2P)
