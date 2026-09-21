"""Deterministic M02 fixtures for experiments/v2_adapter/qualify_instances.py (no network, no evaluator)."""
import copy, json, sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_adapter'))
import qualify_instances as Q  # noqa: E402

BASE = dict(instance_id='demo__repo-1', repo='demo/repo', version='1.0', base_commit='abc123', test_patch='diff --git a b',
            environment_setup_commit='def456', FAIL_TO_PASS=json.dumps(['tests/t.py::test_a']),
            PASS_TO_PASS=json.dumps(['tests/t.py::test_b', 'tests/t.py::test_c']))


def with_(**kw):
    d = copy.deepcopy(BASE)
    for k, v in kw.items():
        if v is Ellipsis:
            d.pop(k)
        else:
            d[k] = v
    return d


def test_valid_json_string_lists_are_eligible():
    r = Q.qualify(BASE)
    assert r['status'] == 'eligible' and (r['n_fail_to_pass'], r['n_pass_to_pass']) == (1, 2) and not r['limitations']


def test_native_lists_are_eligible():
    assert Q.qualify(with_(FAIL_TO_PASS=['a'], PASS_TO_PASS=['b']))['status'] == 'eligible'


@pytest.mark.parametrize('key', ['FAIL_TO_PASS', 'PASS_TO_PASS'])
def test_missing_list_key_is_refused_not_defaulted(key):
    r = Q.qualify(with_(**{key: Ellipsis}))
    assert r['status'] == 'refused' and any('%s missing' % key in x for x in r['reasons'])


def test_empty_fail_to_pass_is_refused():
    r = Q.qualify(with_(FAIL_TO_PASS='[]'))
    assert r['status'] == 'refused' and any('vacuously' in x for x in r['reasons'])


def test_explicitly_empty_pass_to_pass_is_kept_with_limitation():
    r = Q.qualify(with_(PASS_TO_PASS='[]'))
    assert r['status'] == 'eligible' and r['n_pass_to_pass'] == 0 and r['limitations']


@pytest.mark.parametrize('bad', [5, None, 'not json', '{"a": 1}', '[1, 2]', ['a', 3], ['a', ''], 'null'])
@pytest.mark.parametrize('key', ['FAIL_TO_PASS', 'PASS_TO_PASS'])
def test_malformed_lists_are_refused(key, bad):
    assert Q.qualify(with_(**{key: bad}))['status'] == 'refused'


@pytest.mark.parametrize('field', Q.REQUIRED_FIELDS)
def test_missing_or_empty_identity_field_is_refused(field):
    assert Q.qualify(with_(**{field: Ellipsis}))['status'] == 'refused'
    assert Q.qualify(with_(**{field: ''}))['status'] == 'refused'


def test_input_is_never_modified_and_hash_is_stable():
    d = copy.deepcopy(BASE)
    r1, r2 = Q.qualify(d), Q.qualify(d)
    assert d == BASE and r1['content_sha256'] == r2['content_sha256']
