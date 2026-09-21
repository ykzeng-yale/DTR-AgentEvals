"""Scripted fixtures and exhaustive wiring checks for experiments/v2_sim/branch_sampler.py (no Monte Carlo)."""
import itertools, sys
from fractions import Fraction as Fr
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import branch_module as BM  # noqa: E402
import branch_sampler as BS  # noqa: E402
import repair_generator as G  # noqa: E402
import sampler as S  # noqa: E402

CELL = G.Cell(2, 'crossing', 'informative')


class Const:
    """Scripted source returning the first/last live option by stream kind; enough for deterministic structure tests."""
    def __init__(self, first_call_pass=True, arm=1, pick_first=True):
        self.fp, self.arm, self.pf, self.used = first_call_pass, arm, pick_first, []

    def choose(self, label, options):
        live = [(o, p) for o, p in options if p]
        kind = label[1] if len(label) > 1 else None
        if kind == 'first_call':
            out = 1 if self.fp else 0
        elif kind == 'A':
            out = self.arm
        elif kind == 'O0' or kind == 'O':
            out = 'exc'
        elif kind == 'repair':
            out = 0
        else:
            out = live[0][0] if self.pf else live[-1][0]
        self.used.append((label, out))
        return out


def test_allocation_is_always_exactly_four_and_four():
    for pick_first in (True, False):
        order = BS.allocation(Const(pick_first=pick_first), 't0', 'ns')
        assert sorted(order) == [0, 0, 0, 0, 1, 1, 1, 1]


def test_all_first_calls_pass_gives_zero_prefix_tasks_and_whole_range():
    res = BS.run_branch_study([('t0', 0), ('t1', 1)], CELL, Const(first_call_pass=True), 'cfg=x|rep=0')
    assert (res['N'], res['action'], res['delta'], res['delta_range']) == (0, 'whole_range_[-2,2]', None, (-2, 2))
    assert res['tasks_retained'] == 2 and res['zero_prefix_tasks'] == 2 and len(res['source']) == 16


def test_zero_arm_denominator_gives_whole_range():
    res = BS.run_branch_study([('t0', 0)], CELL, Const(first_call_pass=False, arm=1), 'cfg=x|rep=0')   # every logged action large
    assert res['N'] == 8 and res['D_small'] == 0 and res['action'].startswith('whole_range') and res['delta'] is None


class Alternate(Const):
    def choose(self, label, options):
        if len(label) > 1 and label[1] == 'A':
            out = int(label[0].split(':')[-1]) % 2      # same arm at both repairs of an episode; arms alternate by episode
            self.used.append((label, out))
            return out
        return super().choose(label, options)


def test_census_and_srswor_paths():
    tasks = [('t0', 0)]
    census = BS.run_branch_study(tasks, CELL, Alternate(first_call_pass=False), 'cfg=x|rep=0')
    assert census['action'] == 'census' and census['m'] == census['N'] == 8 and len(census['selected']) == 8
    assert census['delta'] is not None and census['D_small'] > 0 and census['D_large'] > 0
    d = Alternate(first_call_pass=False)
    sw = BS.run_branch_study(tasks, CELL, d, 'cfg=x|rep=0', m_max=3)
    assert sw['action'] == 'srswor' and sw['m'] == 3 and len(set(sw['selected'])) == 3
    assert [l for l, _ in d.used if l[0].endswith('|bsel')] == [('cfg=x|rep=0|bsel', k) for k in range(3)]


def test_streams_are_distinct_per_role():
    d = Alternate(first_call_pass=False)
    BS.run_branch_study([('t0', 0)], CELL, d, 'cfg=x|rep=0')
    assert all(l[0].startswith('cfg=x|rep=0|') for l, _ in d.used)   # every stream carries the namespace
    roles = {l[0].split('|')[-1].split(':')[0] for l, _ in d.used}
    assert roles == {'bsrc', 'bfresh'}          # census: no selection draws
    fresh = {l[0] for l, _ in d.used if '|bfresh:' in l[0]}
    assert len(fresh) == 8 * 2 * BS.R_PAIRS     # 8 prefixes x 2 arms x 2 replicates, each its own stream


@pytest.mark.parametrize('cfg', [('crossing', 'informative'), ('no_crossing', 'weak')])
def test_exhaustive_source_episode_matches_exact_branch_module(cfg):
    cell = G.Cell(2, *cfg)
    for s, a0 in itertools.product((0, 1), (0, 1)):
        paths = list(S.exhaustive(lambda d: BS.source_episode(cell, s, a0, d, 'e')))
        assert sum(p for p, _ in paths) == 1
        exact = BM.per_episode(cell, s, a0, Fr(1))
        assert sum(p for p, r in paths if r['prefix'] is not None) == exact['M']
        for a in (0, 1):
            assert sum(p * BS.log_weight(r, a) for p, r in paths) == exact['D'][a]
            assert sum(p * BS.log_weight(r, a) * r['y'] for p, r in paths) == exact['U'][a]


def test_exhaustive_stay_continuation_matches_stay_value():
    for s, u, a in itertools.product((0, 1), (0, 1), (0, 1)):
        prefix = dict(stratum=s, u0=u, o0='exc')
        paths = list(S.exhaustive(lambda d: BS.stay_continuation(CELL, prefix, a, d, 'c')))
        assert sum(p * y for p, y in paths) == BM.stay_value(CELL, s, u, a)
