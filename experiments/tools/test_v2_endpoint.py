"""Fixtures for experiments/v2_adapter/endpoint.py after the fail-closed repair (lead review 8eb727a). Nothing executed."""
import copy, json, sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_adapter'))
import endpoint as EP  # noqa: E402
import qualify_instances as Q  # noqa: E402

INST = dict(instance_id='demo__repo-1', repo='demo/repo', version='1.0', base_commit='abc', test_patch='diff',
            environment_setup_commit='def', FAIL_TO_PASS=json.dumps(['t::a']), PASS_TO_PASS=json.dumps(['t::b']))
OK = Q.qualify(INST)
F2P, P2P = EP.bind_instance(INST, OK)
SHA = 'p' * 64
PASS = {'t::a': 'PASSED', 't::b': 'PASSED'}


def rep(sm, up=None, sha=SHA):
    return dict(kind='report', patch_sha256=sha, status_map=sm, log_ok=True, upstream_resolved=up)


def fail(kind='timeout'):
    return dict(kind=kind, patch_sha256=SHA)


def score(attempts, sub=SHA, qual=OK, f2p=F2P, p2p=P2P):
    return EP.score_episode(qual, sub, attempts, f2p, p2p)


# ---- nominal behaviour retained
def test_resolved_and_agreement():
    assert (lambda r: (r['primary'], r['algorithmic'], r['disagreement']))(score([rep(PASS, up=True)])) == (1, 'resolved', False)


@pytest.mark.parametrize('status', ['SKIPPED', 'XFAIL'])
def test_skipped_and_xfail_zero_with_disagreement(status):
    r = score([rep({**PASS, 't::a': status}, up=True)])
    assert (r['primary'], r['disagreement']) == (0, True)


def test_empty_submission_and_retry_paths():
    assert score([], sub=None)['algorithmic'] == 'not_evaluated_empty'
    assert score([fail('timeout'), rep(PASS)])['primary'] == 1
    assert score([fail('bad_log'), rep(PASS)])['primary'] == 1
    r = score([fail('timeout'), fail('error')])
    assert (r['primary'], r['algorithmic'], r['secondary_bounds']) == (0, 'unknown_evaluator_failure', [0, 1])
    assert score([rep({})])['algorithmic'] == 'unknown_unparsable_output'


def test_explicit_empty_pass_to_pass_is_scored_on_f2p_only():
    inst = dict(INST, PASS_TO_PASS='[]')
    q = Q.qualify(inst)
    f2p, p2p = EP.bind_instance(inst, q)
    assert q['limitations'] and EP.score_episode(q, SHA, [rep({'t::a': 'PASSED'})], f2p, p2p)['primary'] == 1


@pytest.mark.parametrize('attempts,sub', [
    ([], SHA), ([fail()] * 3, SHA), ([rep(PASS), rep(PASS)], SHA), ([rep(PASS, sha='q' * 64)], SHA),
    ([dict(kind='cached', patch_sha256=SHA)], SHA), ([rep(PASS)], None)])
def test_rule_violations_raise(attempts, sub):
    with pytest.raises(EP.EndpointError):
        score(attempts, sub=sub)


# ---- the lead's three probes, read from the committed audit, must now be contract violations (never primary=1)
def _probes():
    a = json.loads((Path(__file__).resolve().parents[2] / 'docs' / 'audits' / 'endpoint_review_153500c.json').read_text())
    return {c.get('id') or c.get('name'): c for c in a['cases']}


@pytest.mark.parametrize('name', ['empty_required_lists', 'missing_log_validity', 'retry_after_explicit_invalid_log'])
def test_lead_probes_now_raise(name):
    c = _probes()[name]
    with pytest.raises(EP.EndpointError):
        EP.score_episode(c['qualification'], c['submission_sha256'], c['attempts'], c['f2p'], c['p2p'])


def test_contradictory_records_rejected_at_validation():
    with pytest.raises(EP.EndpointError, match='bad_log'):
        score([dict(rep(PASS), log_ok=False)])
    with pytest.raises(EP.EndpointError, match='contradictory'):
        score([dict(fail(), log_ok=True)])
    with pytest.raises(EP.EndpointError, match='mapping'):
        score([dict(rep(PASS), status_map=[['t::a', 'PASSED']])])


# ---- binding lives at the integration layer
def test_changed_or_foreign_qualification_is_caught_by_binding():
    changed = dict(INST, FAIL_TO_PASS=json.dumps(['t::other']))
    with pytest.raises(EP.EndpointError):
        EP.bind_instance(changed, OK)
    with pytest.raises(EP.EndpointError):
        score([rep({'t::other': 'PASSED', 't::b': 'PASSED'})], f2p=['t::other'])   # list not the qualified one
    with pytest.raises(EP.EndpointError):
        score([rep(PASS)], qual={'status': 'eligible'})                            # bare label, no hashes


def test_lead_probe_defects_are_caught_on_their_own_with_a_valid_qualification():
    # the audit probes also lack qualification hashes; these isolate the schema defects themselves
    missing_validity = dict(kind='report', patch_sha256=SHA, status_map=PASS)          # no log_ok at all
    with pytest.raises(EP.EndpointError, match='log_ok'):
        score([missing_validity])
    invalid_then_retry = [dict(rep(PASS), log_ok=False), rep(PASS)]                     # contradictory first record
    with pytest.raises(EP.EndpointError, match='bad_log'):
        score(invalid_then_retry)
    with pytest.raises(EP.EndpointError, match='empty FAIL_TO_PASS'):
        score([rep(PASS)], f2p=[])
