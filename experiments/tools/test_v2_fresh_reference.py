"""Checks for experiments/v2_sim/fresh_reference.py: two exact on-policy paths and an independently derived invariant."""
import json, sys
from fractions import Fraction as Fr
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import fresh_reference as F  # noqa: E402


@pytest.fixture(scope='module')
def rep():
    return F.build()


def test_two_paths_agree_and_row_count(rep):
    assert rep['checks']['both_paths_agree_exactly'] and len(rep['rows']) == 24


def test_ipw_variance_never_below_on_policy_variance(rep):
    # On matched paths W = 1/P_log(path | policy actions) >= 1, so E_log[W^2 Z^2] = E_pi[W Z^2] >= E_pi[Z^2]; same mean.
    ratios = [v for r in rep['rows'] for k, d in r.items() if k.startswith('ipw_to_on_policy') for v in d.values()]
    assert len(ratios) == 96 and min(ratios) >= 1


def test_fresh_se_formula(rep):
    for r in rep['rows']:
        t = {k: Fr(v['exact']) for k, v in r['on_policy_per_episode_variance'].items()}
        for n in (250, 1000):
            want = float((t['easy'] + t['hard']) / (2 * F.R_FRESH * n)) ** .5
            assert abs(r['n%d' % n]['fresh_se'] - want) < 1e-15


def test_committed_output_matches_generator(rep):
    assert json.loads(F.OUT.read_text()) == json.loads(json.dumps(rep))
