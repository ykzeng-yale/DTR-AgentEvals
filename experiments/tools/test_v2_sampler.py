"""Scripted-draw fixtures and exhaustive (non-Monte-Carlo) wiring checks for experiments/v2_sim/sampler.py."""
import sys
from fractions import Fraction as Fr
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import repair_generator as G  # noqa: E402
import repair_logger as L  # noqa: E402
import sampler as S  # noqa: E402

CELL = G.Cell(2, 'crossing', 'informative')        # easy stratum: P0=.6, FALSE_PASS=.1, DEEP0=.3, kappa=.9
CAT = {p.name: p for p in G.catalog(2)}
HIST = CAT['history_large_after_exception']
FB = L.LOGGERS['feedback_dependent_floor_0.2']


def ep(script, **kw):
    return S.run_episode(CELL, 0, S.ScriptedDraws({'x': script}), 'x', **kw)


def test_initial_absorption_consumes_one_draw_and_keeps_the_first_call_cost():
    e = ep([Fr(1, 10)], policy=HIST)                     # u < .6 -> first call correct
    assert (e['exit'], e['success'], e['decisions'], e['cost']) == ('first_call_pass', 1, [], G.C[0])


def test_false_pass_at_first_feedback_stops_with_y0():
    e = ep([Fr(7, 10), Fr(1, 2), Fr(1, 20)], policy=HIST)    # incorrect; U0 shallow; obs u < .1 -> false pass
    assert (e['exit'], e['success'], e['decisions']) == ('false_pass', 0, [])


def test_false_pass_after_a_repair():
    # incorrect; U0 deep (u<.3); obs exc; history rule -> large; repair fails; U stays deep; obs false pass
    e = ep([Fr(7, 10), Fr(1, 10), Fr(1, 2), Fr(99, 100), Fr(1, 10), Fr(1, 20)], policy=HIST)
    assert e['exit'] == 'false_pass' and e['decisions'] == [dict(t=1, action=1, p_logged=1)] and e['success'] == 0
    assert e['cost'] == G.C[0] + G.C[1]


def test_K_exhaustion_retains_every_call_cost():
    fail_step = [Fr(99, 100), Fr(1, 10), Fr(1, 2)]        # repair fails; stays deep; obs exc
    e = ep([Fr(7, 10), Fr(1, 10), Fr(1, 2)] + fail_step * 2, policy=HIST)
    assert e['exit'] == 'K_exhausted' and len(e['decisions']) == 2 and e['cost'] == G.C[0] + 2 * G.C[1]


def test_logged_propensities_are_recorded():
    # feedback-dependent logger after 'exc': P(large)=.8; u=.5 -> large (p .8); then repair succeeds
    e = ep([Fr(7, 10), Fr(1, 10), Fr(1, 2), Fr(1, 2), Fr(1, 100)], logger=FB)
    assert e['decisions'] == [dict(t=1, action=1, p_logged=Fr(4, 5))] and e['exit'] == 'true_pass'
    assert S.ipw_weight(e, HIST) == Fr(5, 4) and S.ipw_weight(e, CAT['fixed_SS']) == 0


def test_blocks_retain_every_task_and_replicate_with_distinct_streams():
    tasks = [('t0000', 0), ('t0001', 1), ('t0002', 0)]
    script = {'log:%s:%d' % (t, j): [Fr(1, 100)] for t, _ in tasks for j in range(4)}   # every first call passes
    eps = S.run_blocks(tasks, CELL, 4, S.ScriptedDraws(script), 'log', logger=FB)
    assert len(eps) == 12 and {(e['task_id'], e['replicate']) for e in eps} == {(t, j) for t, _ in tasks for j in range(4)}
    fresh_script = {'fresh:%s:%d' % (t, j): [Fr(1, 100)] for t, _ in tasks for j in range(4)}
    d = S.ScriptedDraws(fresh_script)
    fr = S.run_blocks(tasks, CELL, 4, d, 'fresh', policy=HIST)
    assert not {e['stream'] for e in eps} & {e['stream'] for e in fr}
    assert len({e['stream'] for e in fr}) == 12
    assert sorted(label[0] for label, _ in d.used) == sorted(e['stream'] for e in fr)   # each draw on its own stream
    assert all(not v for v in d.script.values())                                         # every scripted draw consumed


@pytest.mark.parametrize('cfg', [(2, 'crossing', 'informative'), (4, 'no_crossing', 'weak')])
def test_exhaustive_sampler_reproduces_exact_truth_without_monte_carlo(cfg):
    cell = G.Cell(*cfg)
    pols = G.catalog(cell.K) if cell.K == 2 else [p for p in G.catalog(cell.K) if p.name in
                                                   ('history_large_after_exception', 'prompt_only_large_if_hard', 'fixed_LLLL')]
    for pol in pols:
        for s in (0, 1):
            truth = G.enumerate_value(pol, cell, s)[0]
            fresh = list(S.exhaustive(lambda d: S.run_episode(cell, s, d, 'f', policy=pol)))
            assert sum(p for p, _ in fresh) == 1
            assert sum(p * e['success'] for p, e in fresh) == truth['success']
            assert sum(p * e['cost'] for p, e in fresh) == truth['cost']
            logged = list(S.exhaustive(lambda d: S.run_episode(cell, s, d, 'l', logger=FB)))
            assert sum(p * S.ipw_weight(e, pol) * e['utility'] for p, e in logged) == truth['success'] - truth['cost']


def test_estimators_average_tasks_equally_over_replicates():
    tasks = [('a', 0), ('b', 0)]
    eps = [dict(task_id='a', utility=Fr(1), decisions=[], stratum=0, observations=[]),
           dict(task_id='a', utility=Fr(0), decisions=[], stratum=0, observations=[]),
           dict(task_id='b', utility=Fr(1), decisions=[], stratum=0, observations=[]),
           dict(task_id='b', utility=Fr(1), decisions=[], stratum=0, observations=[])]
    assert S.fresh_estimate(eps) == Fr(3, 4) and S.ipw_estimate(eps, HIST) == Fr(3, 4) and len(tasks) == 2
