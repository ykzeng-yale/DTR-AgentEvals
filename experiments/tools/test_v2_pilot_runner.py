"""Deterministic fixtures for the fixed-backend pilot runner's declared queue/restart/block rules (no model, server or
container): frozen order with per-task backend order, terminal episodes skipped by hash, interrupted run directories
retained and re-run in a new directory, conflicting records refused before ANY execution, the time-based block cap
(never outcome-based) with unstarted IDs preserved, serial serving only on backend change, and the pause file."""
import json, sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_agent'))
import pilot_runner as PR  # noqa: E402

FRAME = dict(pilot=dict(tasks=[
    dict(position=2, instance_id='b__2', backend_order=['large', 'small'], instance_image='sha256:b'),
    dict(position=1, instance_id='a__1', backend_order=['small', 'large'], instance_image='sha256:a'),
    dict(position=3, instance_id='c__3', backend_order=['large', 'small'], instance_image='sha256:c')]))


def terminal(out, iid, be, run_id, **kw):
    d = out / run_id
    d.mkdir(parents=True)
    (d / 'episode.json').write_text(json.dumps(dict(dict(instance_id=iid, backend=be, run_id=run_id, exit_status='Submitted',
                                                         physical_requests=10), **kw)))
    return d


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def fakes(clock, per_episode=600.0):
    served, ran = [], []

    def serve(be):
        served.append(be)

    def run(it):
        ran.append((it['instance_id'], it['backend']))
        clock.t += per_episode
        return dict(run_id='%s__%s__x' % (it['instance_id'], it['backend']), exit_status='LimitsExceeded', wall_seconds=per_episode,
                    physical_requests=24)
    return serve, run, served, ran


def test_queue_is_frozen_position_order_with_each_tasks_backend_order():
    q = PR.episode_queue(FRAME)
    assert [(x['instance_id'], x['backend'], x['order']) for x in q] == [
        ('a__1', 'small', 1), ('a__1', 'large', 2), ('b__2', 'large', 1), ('b__2', 'small', 2), ('c__3', 'large', 1), ('c__3', 'small', 2)]
    assert q[0]['image'] == 'sha256:a'


def test_completed_skipped_incomplete_retained_and_serving_switches_only_on_change(tmp_path):
    out = tmp_path / 'out'
    terminal(out, 'a__1', 'small', 'a__1__small__pilot-cp2-wc2__T0-aaaaaa')
    (out / 'a__1__large__pilot-cp2-wc2__T0-bbbbbb').mkdir()                    # interrupted: no episode.json
    clock = Clock()
    serve, run, served, ran = fakes(clock)
    st = PR.run_block(PR.episode_queue(FRAME), out, serve, run, {}, clock=clock, block_start=clock())
    assert [s['instance_id'] + '/' + s['backend'] for s in st['skipped_completed']] == ['a__1/small']
    assert st['retained_incomplete'] == [dict(position=1, order=2, instance_id='a__1', backend='large', run_dirs=['a__1__large__pilot-cp2-wc2__T0-bbbbbb'])]
    assert ran == [('a__1', 'large'), ('b__2', 'large'), ('b__2', 'small'), ('c__3', 'large'), ('c__3', 'small')]
    assert served == ['large', 'small', 'large', 'small']                        # one switch per backend change
    assert (out / 'a__1__large__pilot-cp2-wc2__T0-bbbbbb').is_dir()              # never deleted or reused
    assert st['physical_requests_total'] == 10 + 5 * 24 and st['stopped'] is None


def test_conflicting_or_duplicate_records_refuse_before_any_execution(tmp_path):
    for bad in (dict(instance_id='zzz'), dict(backend='large'), dict(exit_status=None)):
        out = tmp_path / ('o%d' % len(list(tmp_path.iterdir())))
        terminal(out, 'c__3', 'small', 'c__3__small__pilot-cp2-wc2__T0-cccccc', **bad)
        clock = Clock()
        serve, run, served, ran = fakes(clock)
        with pytest.raises(PR.Conflict):
            PR.run_block(PR.episode_queue(FRAME), out, serve, run, {}, clock=clock)
        assert ran == [] and served == []
    out = tmp_path / 'dup'
    terminal(out, 'a__1', 'small', 'a__1__small__pilot-cp2-wc2__T0-000001')
    terminal(out, 'a__1', 'small', 'a__1__small__pilot-cp2-wc2__T0-000002')
    with pytest.raises(PR.Conflict):
        PR.run_block(PR.episode_queue(FRAME), out, *fakes(Clock())[:2], {}, clock=Clock())


def test_block_cap_is_time_based_and_preserves_unstarted_ids(tmp_path):
    clock = Clock(0.0)
    serve, run, served, ran = fakes(clock, per_episode=1500.0)
    st = PR.run_block(PR.episode_queue(FRAME), tmp_path / 'out', serve, run, {}, clock=clock, block_start=0.0)
    # start needs now + 1800 + 300 (+300 on a switch) <= 7200: t=0 ok, 1500 ok (switch: 3900), 3000 ok (switch: 5400),
    # 4500: 4500+2400=6900 ok, 6000: stop
    assert ran == [('a__1', 'small'), ('a__1', 'large'), ('b__2', 'large'), ('b__2', 'small')]
    assert st['stopped'].startswith('block time cap')
    assert [(u['instance_id'], u['backend']) for u in st['unstarted']] == [('c__3', 'large'), ('c__3', 'small')]
    assert PR.plan_start(0, 0, False) and not PR.plan_start(5101, 0, False) and not PR.plan_start(4801, 0, True)


def test_pause_file_stops_before_the_next_start(tmp_path):
    clock = Clock()
    pause = tmp_path / 'PAUSE'
    serve, run0, served, ran = fakes(clock)

    def run(it):
        r = run0(it)
        pause.write_text('coordination')
        return r
    st = PR.run_block(PR.episode_queue(FRAME), tmp_path / 'out', serve, run, {}, clock=clock, pause=pause)
    assert len(ran) == 1 and st['stopped'].startswith('paused') and len(st['unstarted']) == 5
