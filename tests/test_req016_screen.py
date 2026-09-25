"""DTR-REQ-016 fixtures: the restricted adapter (what the model sees and may do), the episode loop with a fake browser
and a fake model transport, the parent's capacity supervision, scoring, admission probes, single-shot behaviour and the
manifest bindings. No browser, no model and no server are started (one optional check runs the pinned BrowserGym venv
to build the restricted action set, and is skipped when that venv is absent). Expected values are written by hand.
"""
import json
import os
import shutil
import subprocess
import sys
import threading
from collections import OrderedDict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / 'experiments/v2_browser', ROOT / 'experiments/v2_agent', ROOT / 'experiments/v2_adapter'):
    sys.path.insert(0, str(p))
import req016_adapter as AD  # noqa: E402
import req016_episodes as EP  # noqa: E402
import req016_screen as R  # noqa: E402


@pytest.fixture(autouse=True)
def clean_stop_state():
    EP.STOP.update(requested=False, reason=None, in_transport=False, parent=None)
    yield
    EP.STOP.update(requested=False, reason=None, in_transport=False, parent=None)

TREE = """RootWebArea 'Book Flight Task', focused
\t[17] heading 'Book Your One-Way Flight'
\t[19] textbox 'From:'
\t[21] textbox 'To:'
\tStaticText 'Departure Date'
\t[25] textbox ''
\t[27] button 'Search'"""
GOAL = 'Book the cheapest one-way flight from: Akuton, AK to: Page, AZ on 12/22/2016.'


# ------------------------------------------------------------------ parser: exactly one allowed action on a current bid
@pytest.mark.parametrize('reply,expected', [
    ("click('19')", ("click('19')", None)),
    ("I will open the From field.\nclick('19')", ("click('19')", None)),
    ("```\nclick('27')\n```", ("click('27')", None)),
    ("```python\nfill('19', 'Akuton, AK')\n```", ("fill('19', 'Akuton, AK')", None)),
    ("Action: fill('21', \"Coeur d'Alene\")", ("fill('21', \"Coeur d'Alene\")", None)),
    ("`noop()`", ('noop()', None)),
    ('fill("19", "Page")', ("fill('19', 'Page')", None)),
])
def test_valid_actions_are_canonicalized(reply, expected):
    action, cause, _ = AD.parse_action(reply, TREE)
    assert (action, cause) == expected


@pytest.mark.parametrize('reply,cause', [
    ('', 'no_action'),
    ('I think the answer is to click the search button.', 'no_action'),
    ("Next action: click('19')", 'no_action'),
    ("click('19'); click('21')", 'no_action'),
    ("click('19')\nclick('21')", 'multiple_actions'),
    ("fill('19', 'A')\nnoop()", 'multiple_actions'),
    ("goto('file:///etc/passwd')", 'forbidden_function'),
    ('new_tab()', 'forbidden_function'),
    ("tab_focus(0)", 'forbidden_function'),
    ("upload_file('19', '/tmp/x')", 'forbidden_function'),
    ("scroll(0, 200)", 'forbidden_function'),
    ("press('19', 'Enter')", 'forbidden_function'),
    ("send_msg_to_user('done')", 'forbidden_function'),
    ("report_infeasible('no')", 'forbidden_function'),
    ("select_option('19', 'x')", 'forbidden_function'),
    ("exec('import os')", 'forbidden_function'),
    ("__import__('os').system('ls')", 'no_action'),
    ("page.click('#search')", 'no_action'),
    ("click('19', button='right')", 'bad_arguments'),
    ('click(19)', 'bad_arguments'),
    ("fill('19')", 'bad_arguments'),
    ('noop(500)', 'bad_arguments'),
    ("click(*['19'])", 'bad_arguments'),
    ("click('99')", 'unknown_bid'),
    ("click('Search')", 'unknown_bid'),
    ("fill('19', '%s')" % ('x' * 201), 'fill_too_long'),
])
def test_invalid_actions_have_declared_causes(reply, cause):
    action, got, _ = AD.parse_action(reply, TREE)
    assert action is None and got == cause
    assert got in AD.CAUSES


def test_bids_come_only_from_line_leading_tokens():
    tree = TREE + "\n\tStaticText 'see [99] below'"
    assert AD.tree_bids(tree) == {'17', '19', '21', '25', '27'}
    assert AD.parse_action("click('99')", tree)[1] == 'unknown_bid'


# ------------------------------------------------------------------ what the model sees
SECRET_OBS = dict(goal=GOAL, axtree_object=TREE, last_action_error='', url='file:///Users/x/miniwob/book-flight.html',
                  dom_object={'strings': ['data-price', '237', 'data-duration', '8700000']}, screenshot=b'PNG-bytes',
                  extra_element_properties={'19': {'visibility': 1}}, open_pages_urls=['file:///secret'],
                  chat_messages=[{'role': 'assistant', 'message': 'hi'}], elapsed_time=1.0)


def test_model_view_keeps_only_goal_tree_and_error():
    view = AD.model_view(SECRET_OBS, flatten=lambda t: t)
    assert set(view) == {'goal', 'axtree', 'last_action_error'}
    msgs = AD.build_messages(view, [{'action': "click('19')", 'error': ''},
                                    {'action': None, 'cause': 'unknown_bid'},
                                    {'action': "fill('19', 'A')", 'error': 'TimeoutError: x'}], 13)
    body = AD.canonical_body('alias-7b', msgs, {'temperature': 0, 'max_tokens': 1536})
    assert AD.leak_problems(body) == []
    for secret in ('file:', 'data-price', 'data-duration', 'PNG-bytes', 'visibility', 'secret', 'elapsed', 'hi'):
        assert secret not in body.replace('this', '')
    user = msgs[1]['content']
    assert user == ('Goal: %s\n\nCurrent page (accessibility tree):\n%s\n\nPrevious actions (oldest first):\n'
                    "1. click('19') -> ok\n2. invalid reply (unknown_bid): not executed\n"
                    "3. fill('19', 'A') -> error: TimeoutError: x\n\nActions remaining: 13\n\n"
                    'Reply with your next action.' % (GOAL, TREE))
    assert msgs[0] == {'role': 'system', 'content': AD.SYSTEM_PROMPT}
    b = json.loads(body)
    assert (b['temperature'], b['max_tokens'], b['stream'], b['model']) == (0, 1536, False, 'alias-7b')


def test_error_excerpt_drops_markup_and_call_logs():
    err = ('TimeoutError: Locator.click: Timeout 500ms exceeded.\nCall log:\n  - locator resolved to '
           '<button data-price="237" class="flight-price">Book flight for $237</button>')
    assert AD.error_excerpt(err) == 'TimeoutError: Locator.click: Timeout 500ms exceeded.'
    assert AD.error_excerpt('Error: <div data-duration="1">x</div> failed') == 'Error: x failed'
    assert AD.error_excerpt('') == '' and len(AD.error_excerpt('E' * 500)) == 160
    assert AD.fill_text("fill('19', \"Coeur d'Alene\")") == "Coeur d'Alene"


def test_leak_guard_ignores_text_the_model_typed_itself():
    typed_page = TREE + "\n\t[19] textbox 'From:' value='file:abc'"
    assert AD.leak_problems(typed_page) == ['file:']
    assert AD.leak_problems(typed_page, typed=['file:abc']) == []
    assert AD.leak_problems(typed_page + ' data-price', typed=['file:abc']) == ['data-price']
    assert AD.leak_problems("url='file:///x'", typed=['e']) == ['file:']          # short typed text exempts nothing
    assert AD.leak_problems("[5] link 'data-price'", typed=['a']) == ['data-price']


def test_leak_guard_names_every_forbidden_marker():
    assert AD.leak_problems('{"x": "file:///a data-price RAW_REWARD_GLOBAL"}') == ['file:', 'data-price', 'RAW_REWARD',
                                                                                  'REWARD_GLOBAL']
    assert AD.history_lines([]) == '(none)'


# ------------------------------------------------------------------ episode loop (fake browser + fake model)
RESULTS = TREE + "\n\t[167] button 'Book flight for $387'\n\t[189] button 'Book flight for $237'"


class FakeEnv:
    """reset -> TREE; each action maps to (tree, error, terminated, task_info)."""

    def __init__(self, script):
        self.script, self.actions = script, []

    def reset(self, seed):
        return dict(SECRET_OBS), {'task_info': {'RAW_REWARD_GLOBAL': 0, 'DONE_GLOBAL': False}}

    def step(self, action):
        self.actions.append(action)
        tree, err, term, ti = self.script.get(action, (TREE, '', False, {'RAW_REWARD_GLOBAL': 0, 'DONE_GLOBAL': False}))
        obs = dict(SECRET_OBS, axtree_object=tree, last_action_error=err)
        return obs, float(ti.get('RAW_REWARD_GLOBAL', 0) > 0), term, False, {'task_info': ti}

    def close(self):
        pass


def reply(text, prompt=100, completion=10):
    return OrderedDict(kind='response', http_status=200, seconds=0.1, body=json.dumps(
        {'choices': [{'message': {'content': text}, 'finish_reason': 'stop'}],
         'usage': {'prompt_tokens': prompt, 'completion_tokens': completion}}))


class FakeTransport:
    """Returns the queued results in order; checks that the request receipt exists before each dispatch."""

    def __init__(self, results, rec_dir_fn):
        self.results, self.rec_dir_fn, self.bodies = list(results), rec_dir_fn, []

    def __call__(self, body, timeout):
        rec = self.rec_dir_fn()
        assert sorted(p.name for p in rec.glob('*.request.json'))[-1:] and \
            len(list(rec.glob('*.request.json'))) == len(self.bodies) + 1
        self.bodies.append(body)
        return self.results.pop(0)


def cfg(tmp, **caps):
    c = dict(logical_per_episode=16, physical_per_episode=32, attempts_per_call=2, request_timeout_s=300, artifact_gib=2)
    c.update(caps)
    return dict(caps=c, settings=dict(temperature=0, max_tokens=1536), alias='alias-7b', deadline_epoch=1e12,
                out_dir=str(tmp), seeds=[200, 201], task={'gym_id': 'x'})


def run(tmp, script, results, **caps):
    env = FakeEnv(script)
    out = tmp / 'seed200'
    t = FakeTransport(results, lambda: out / 'receipts')
    s = EP.run_episode(200, cfg(tmp, **caps), env, t, out, flatten=lambda x: x)
    return s, env, t, out


def test_full_success_episode_with_receipts_and_steps(tmp_path):
    script = {"click('27')": (RESULTS, '', False, {'DONE_GLOBAL': False, 'RAW_REWARD_GLOBAL': 0}),
              "click('189')": (RESULTS, '', True, {'DONE_GLOBAL': True, 'RAW_REWARD_GLOBAL': 1, 'REWARD_GLOBAL': 0.99})}
    s, env, t, out = run(tmp_path, script, [reply("click('27')"), reply('thinking only'), reply("click('189')")])
    assert (s['cause'], s['full_success'], s['logical_calls'], s['physical_attempts']) == ('full_success', True, 3, 3)
    assert (s['executed_actions'], s['invalid_replies'], s['invalid_causes']) == (2, 1, {'no_action': 1})
    assert (s['prompt_tokens'], s['completion_tokens']) == (300, 30)
    assert env.actions == ["click('27')", "click('189')"]
    assert sorted(p.name for p in (out / 'receipts').iterdir()) == [
        'call01_attempt01.outcome.json', 'call01_attempt01.request.json', 'call02_attempt01.outcome.json',
        'call02_attempt01.request.json', 'call03_attempt01.outcome.json', 'call03_attempt01.request.json']
    steps = [json.loads(l) for l in (out / 'steps.jsonl').read_text().splitlines()]
    assert [x['kind'] for x in steps] == ['reset', 'call', 'call', 'call']
    assert steps[2]['executed'] is False and steps[2]['invalid_cause'] == 'no_action'
    assert steps[3]['verifier_only']['task_info']['RAW_REWARD_GLOBAL'] == 1
    for body in t.bodies:                                      # the verifier never reaches the model
        assert 'RAW' not in body and 'DONE' not in body and 'file:' not in body and 'data-price' not in body
    assert 'invalid reply (no_action)' in json.loads(t.bodies[2])['messages'][1]['content']
    assert 'Actions remaining: 14' in json.loads(t.bodies[2])['messages'][1]['content']


def test_wrong_booking_and_page_change_causes(tmp_path):
    wrong = {"click('27')": (RESULTS, '', True, {'DONE_GLOBAL': True, 'RAW_REWARD_GLOBAL': -1, 'REWARD_REASON': None})}
    assert run(tmp_path / 'a', wrong, [reply("click('27')")])[0]['cause'] == 'wrong_booking'
    moved = {"click('27')": (RESULTS, '', True, {'error': 'invalid url, terminating task'})}
    assert run(tmp_path / 'b', moved, [reply("click('27')")])[0]['cause'] == 'page_or_url_changed'
    late = {"click('27')": (RESULTS, '', True, {'DONE_GLOBAL': True, 'RAW_REWARD_GLOBAL': -1, 'REWARD_REASON': 'timed out'})}
    assert run(tmp_path / 'c', late, [reply("click('27')")])[0]['cause'] == 'core_timeout'


def test_logical_budget_counts_invalid_replies(tmp_path):
    s, env, t, _ = run(tmp_path, {}, [reply('no action here')] * 16)
    assert (s['cause'], s['logical_calls'], s['physical_attempts'], s['invalid_replies']) == (
        'logical_budget_exhausted', 16, 16, 16)
    assert env.actions == []


def test_transport_retry_then_success_and_double_failure(tmp_path):
    err = OrderedDict(kind='transport_error', http_status=None, body='URLError: refused', seconds=0.0)
    five = OrderedDict(kind='http_error', http_status=503, body='busy', seconds=0.0)
    s, env, _, out = run(tmp_path / 'a', {}, [err, reply("click('19')")] + [reply('x')] * 15)
    assert (s['logical_calls'], s['physical_attempts']) == (16, 17) and env.actions[0] == "click('19')"
    assert (out / 'receipts' / 'call01_attempt02.request.json').exists()
    s, _, _, _ = run(tmp_path / 'b', {}, [err, five])
    assert (s['cause'], s['logical_calls'], s['physical_attempts']) == ('transport_failure', 1, 2)


def test_context_limit_is_not_retried(tmp_path):
    ctx = OrderedDict(kind='http_error', http_status=400, seconds=0.0,
                      body='request (16959 tokens) exceeds the available context size (16384 tokens)')
    s, _, _, _ = run(tmp_path, {}, [ctx])
    assert (s['cause'], s['physical_attempts']) == ('context_limit', 1)


def test_physical_budget_binds_before_the_logical_budget(tmp_path):
    err = OrderedDict(kind='transport_error', http_status=None, body='timeout', seconds=0.0)
    results = []
    for _ in range(3):
        results += [err, reply('nothing')]
    s, _, t, _ = run(tmp_path, {}, results, physical_per_episode=5)
    assert (s['cause'], s['physical_attempts'], len(t.bodies)) == ('physical_budget_exhausted', 5, 5)


def test_leak_guard_refuses_dispatch(tmp_path):
    env = FakeEnv({})
    env.reset = lambda seed: (dict(SECRET_OBS, axtree_object=TREE + "\n\t[9] link 'file:///x'"), {'task_info': {}})
    t = FakeTransport([], lambda: tmp_path / 's' / 'receipts')
    s = EP.run_episode(200, cfg(tmp_path), env, t, tmp_path / 's', flatten=lambda x: x)
    assert (s['cause'], s['logical_calls'], t.bodies) == ('leak_guard', 0, [])


def test_deadline_stops_before_dispatch(tmp_path):
    c = cfg(tmp_path)
    c['deadline_epoch'] = 0
    t = FakeTransport([], lambda: tmp_path / 's' / 'receipts')
    s = EP.run_episode(200, c, FakeEnv({}), t, tmp_path / 's', flatten=lambda x: x)
    assert (s['cause'], s['logical_calls']) == ('deadline', 0)


def test_batch_continues_after_an_episode_and_stops_on_supervisor_signal(tmp_path):
    calls = []

    def factory(c):
        calls.append(1)
        return FakeEnv({}), ['click', 'fill', 'noop']

    class StopAfterFirst(FakeTransport):
        def __call__(self, body, timeout):
            if len(calls) > 1:
                raise EP.Stopped('signal 15')
            return reply('x')
    c = cfg(tmp_path, logical_per_episode=2)
    c['seeds'] = [200, 201, 202]
    batch = EP.run_batch(c, env_factory=factory, transport=StopAfterFirst([], None), flatten=lambda x: x)
    assert [e['cause'] for e in batch['episodes']] == ['logical_budget_exhausted', 'stopped_by_supervisor',
                                                       'not_started']
    assert (batch['full_success'], batch['denominator'], batch['stop']) == (0, 3, 'stopped_by_supervisor')
    assert json.loads((tmp_path / 'batch_summary.json').read_text())['stop'] == 'stopped_by_supervisor'
    assert (tmp_path / 'episodes' / 'seed200' / 'episode.json').exists()


def test_stop_signal_is_deferred_outside_a_model_request():
    EP.on_stop(15, None)                                      # outside transport: only recorded
    assert EP.STOP['requested'] is True
    with pytest.raises(EP.Stopped):
        EP.check_stop()
    EP.STOP.update(requested=False, in_transport=True)
    with pytest.raises(EP.Stopped):
        EP.on_stop(15, None)                                  # inside a model request: raised at once
    assert EP.STOP['in_transport'] is False
    EP.STOP.update(requested=False, parent=-1)                # the supervising parent is gone
    with pytest.raises(EP.Stopped, match='parent is gone'):
        EP.check_stop()


def test_a_stop_during_env_close_still_stops_the_batch(tmp_path):
    class ClosingEnv(FakeEnv):
        def close(self):
            EP.on_stop(15, None)                              # the signal lands while the browser closes

    c = cfg(tmp_path, logical_per_episode=1)
    c['seeds'] = [200, 201, 202]
    batch = EP.run_batch(c, env_factory=lambda c: (ClosingEnv({}), ['click', 'fill', 'noop']),
                         transport=lambda body, timeout: reply('x'), flatten=lambda x: x)
    assert [e['cause'] for e in batch['episodes']] == ['logical_budget_exhausted', 'not_started', 'not_started']
    assert batch['stop'] == 'stopped_by_supervisor'
    assert [json.loads(l)['seed'] for l in (tmp_path / 'episodes.jsonl').read_text().splitlines()] == [200]


def test_a_stop_before_env_step_is_honoured_at_the_safe_point(tmp_path):
    class StepSignal(FakeEnv):
        def reset(self, seed):
            EP.on_stop(15, None)                              # arrives during reset (a Playwright call): deferred
            return FakeEnv.reset(self, seed)
    env = StepSignal({})
    t = FakeTransport([reply("click('19')")], lambda: tmp_path / 's' / 'receipts')
    with pytest.raises(EP.Stopped):
        EP.run_episode(200, cfg(tmp_path), env, t, tmp_path / 's', flatten=lambda x: x)
    assert env.actions == [] and t.bodies == []


def test_transport_failure_stops_the_batch(tmp_path):
    err = OrderedDict(kind='transport_error', http_status=None, body='refused', seconds=0.0)
    c = cfg(tmp_path)
    c['seeds'] = [200, 201]
    batch = EP.run_batch(c, env_factory=lambda c: (FakeEnv({}), ['click', 'fill', 'noop']),
                         transport=lambda body, timeout: err, flatten=lambda x: x)
    assert [e['cause'] for e in batch['episodes']] == ['transport_failure', 'not_started']
    assert batch['stop'] == 'transport_failure'


def test_classify_transport():
    assert EP.classify_transport(reply('a'))[:2] == ('ok', 'a')
    assert EP.classify_transport(OrderedDict(kind='http_error', http_status=502, body=''))[0] == 'retry'
    assert EP.classify_transport(OrderedDict(kind='http_error', http_status=404, body='nope'))[0] == 'http_error'
    assert EP.classify_transport(OrderedDict(kind='response', http_status=200, body='{}'))[0] == 'http_error'


# ------------------------------------------------------------------ parent: capacity supervision
class Child:
    def __init__(self, alive_polls):
        self.alive, self.signals = alive_polls, []

    def poll(self):
        if self.alive > 0:
            self.alive -= 1
            return None
        return 0

    def wait(self, timeout=None):
        raise subprocess.TimeoutExpired('c', timeout)


class Clock:
    def __init__(self, steps):
        self.t, self.steps = 1000.0, list(steps)

    def __call__(self):
        return self.t

    def advance(self, _seconds):
        self.t += self.steps.pop(0) if self.steps else 5.0


def sampler_from(values):
    vals = list(values)

    def sample(phase):
        v = vals.pop(0)
        if isinstance(v, Exception):
            raise v
        s = OrderedDict(phase=phase, physical_free_pct=v, host_disk_free_gib=70.0)
        s['problems'] = R.capacity_problems(s, {'physical_free_pct': 10, 'host_disk_free_gib': 15})
        return s
    return sample


def supervise(values, alive, steps=(), deadline=None):
    stops, clock = [], Clock(steps)
    out = R.supervise(Child(alive), sampler_from(values), lambda r, d: stops.append((r, d)), clock=clock,
                      wait=clock.advance, interval=5, max_gap=10, deadline=deadline)
    return out, stops


def test_supervision_passes_without_breach():
    out, stops = supervise([40, 35, 30], alive=3)          # three samples, then the child has exited
    assert out['ended'] == 'child_exited' and stops == [] and out['samples'] == 3


def test_supervision_stops_on_low_memory_unavailable_or_failed_sample():
    out, stops = supervise([40, 9, 40], alive=6)
    assert out['ended'] == 'capacity_interruption' and stops[0][0] == 'capacity_interruption'
    assert 'physical_free_pct 9 is below 10' in stops[0][1]['problems'][0]
    out, stops = supervise([40, None], alive=6)
    assert stops and 'unavailable (fails closed)' in stops[0][1]['problems'][0]
    out, stops = supervise([RuntimeError('ps failed')], alive=6)
    assert stops and 'could not be taken' in stops[0][1]['problems'][0]


def test_supervision_fails_closed_on_a_sampling_gap_over_ten_seconds():
    out, stops = supervise([40, 40, 40], alive=6, steps=[5.0, 10.5])
    assert out['ended'] == 'capacity_interruption' and 'sampling gap 10.5 s' in stops[0][1]['problems'][0]
    out, stops = supervise([40, 40, 40], alive=3, steps=[5.0, 5.0])
    assert stops == [] and out['max_gap_s'] == 5.0
    out, stops = supervise([40, 40], alive=2, steps=[10.0])  # exactly 10 s passes (only > 10 s fails)
    assert stops == [] and out['max_gap_s'] == 10.0


def test_supervision_stops_when_the_owned_server_dies():
    stops, clock = [], Clock([])
    health = iter([None, None, 'the owned server exited (code -9)'])
    out = R.supervise(Child(9), sampler_from([40, 40, 40]), lambda r, d: stops.append((r, d)), clock=clock,
                      wait=clock.advance, health=lambda: next(health))
    assert out['ended'] == 'server_failure' and stops[0][0] == 'server_failure' and out['samples'] == 2


def test_supervision_deadline_and_breach_after_child_exit():
    out, stops = supervise([40], alive=6, deadline=999.0)
    assert out['ended'] == 'batch_deadline' and stops[0][0] == 'batch_deadline'

    class ExitsDuringSample(Child):
        def poll(self):
            self.alive -= 1
            return None if self.alive > 0 else 0
    stops, clock = [], Clock([])
    out = R.supervise(ExitsDuringSample(2), sampler_from([5]), lambda r, d: stops.append(r), clock=clock,
                      wait=clock.advance)
    assert out['ended'] == 'child_exited' and 'breach_after_child_exit' in out and stops == []


def test_measure_and_capacity_rule():
    def run(cmd, env=None, timeout=60):
        if cmd[0] == 'memory_pressure':
            return 0, 'System-wide memory free percentage: 23%\n', ''
        return 0, 'total = 15360.00M  used = 14962.44M  free = 397.56M  (encrypted)\n', ''

    class U:
        free = 40 * 2 ** 30
    m = R.measure(ROOT, run=run, usage=lambda p: U)
    assert (m['physical_free_pct'], m['host_disk_free_gib'], m['swap_used_gib'], m['swap_total_gib']) == (
        23, 40.0, 14.612, 15.0)
    th = json.loads((ROOT / R.MANIFEST_REL).read_text())['capacity']['thresholds']
    assert R.capacity_problems(m, th['post_load']) == []
    assert R.capacity_problems(dict(m, physical_free_pct=19), th['post_load']) == ['physical_free_pct 19 is below 20']
    assert R.capacity_problems(dict(m, host_disk_free_gib=14.9), th['episode'])[0].startswith('host_disk_free_gib')
    m = R.measure(ROOT, run=lambda cmd, env=None, timeout=60: (1, '', 'x'), usage=lambda p: U)
    assert m['physical_free_pct'] is None and m['swap_used_gib'] is None
    assert R.capacity_problems(m, th['episode']) == ['physical_free_pct unavailable (fails closed)']


# ------------------------------------------------------------------ scoring
def test_score_counts_all_eight_and_relabels_capacity_rows(tmp_path):
    batch = {'episodes': [dict(seed=200, cause='full_success', full_success=True, logical_calls=5),
                          dict(seed=201, cause='logical_budget_exhausted', full_success=False),
                          dict(seed=202, cause='stopped_by_supervisor', full_success=False),
                          dict(seed=203, cause='not_started', full_success=False)]}
    s = R.score(batch, 'COMPLETED')
    assert (s['full_success'], s['denominator']) == (1, 8)
    assert s['taxonomy'] == {'full_success': 1, 'logical_budget_exhausted': 1, 'stopped_by_supervisor': 1,
                             'not_started': 5}
    s = R.score(batch, 'CAPACITY_INTERRUPTION')
    assert s['taxonomy'] == {'full_success': 1, 'logical_budget_exhausted': 1, 'capacity_interruption': 1,
                             'not_run_capacity': 5}
    assert s['capacity_rows'] == [202, 203, 204, 205, 206, 207]
    (tmp_path / 'episodes' / 'seed200').mkdir(parents=True)
    s = R.score(None, 'CHILD_FAILED', tmp_path)
    assert s['rows'][0]['cause'] == 'not_run: CHILD_FAILED (incomplete_record)'
    assert s['taxonomy']['not_run: CHILD_FAILED (not_started)'] == 7 and s['screen_complete'] is False


def test_truncated_records_do_not_crash_scoring(tmp_path):
    (tmp_path / 'batch_summary.json').write_text('{"episodes": [')
    (tmp_path / 'episodes' / 'seed200').mkdir(parents=True)
    (tmp_path / 'episodes' / 'seed200' / 'episode.json').write_text('{"seed": 200, "cau')
    assert R.load_batch(tmp_path) is None
    s = R.score(R.load_batch(tmp_path), 'CHILD_FAILED', tmp_path)
    assert s['rows'][0]['cause'] == 'not_run: CHILD_FAILED (incomplete_record)'


def test_score_recovers_completed_seeds_without_a_batch_summary(tmp_path):
    (tmp_path / 'episodes' / 'seed201').mkdir(parents=True)
    (tmp_path / 'episodes' / 'seed201' / 'episode.json').write_text(json.dumps(
        dict(seed=201, cause='wrong_booking', full_success=False)))
    (tmp_path / 'episodes.jsonl').write_text(json.dumps(dict(seed=200, cause='full_success', full_success=True)) + '\n')
    (tmp_path / 'episodes' / 'seed202').mkdir()                                      # killed mid-episode
    s = R.score(None, 'CAPACITY_INTERRUPTION', tmp_path)
    assert [r['cause'] for r in s['rows'][:4]] == ['full_success', 'wrong_booking', 'capacity_interruption',
                                                   'not_run_capacity']
    assert s['full_success'] == 1 and s['capacity_rows'] == [202, 203, 204, 205, 206, 207]


def test_screen_status_requires_a_clean_complete_child():
    full = {'stop': None, 'episodes': [{}] * 8}
    assert R.screen_status('child_exited', 0, full, 8) == 'COMPLETED'
    assert R.screen_status('child_exited', 1, full, 8) == 'CHILD_FAILED'
    assert R.screen_status('child_exited', 0, None, 8) == 'CHILD_FAILED'
    assert R.screen_status('child_exited', 0, {'stop': None, 'episodes': [{}] * 7}, 8) == 'CHILD_FAILED'
    assert R.screen_status('child_exited', 0, {'stop': 'transport_failure', 'episodes': [{}] * 8}, 8) == \
        'CHILD_STOPPED_TRANSPORT_FAILURE'
    assert R.screen_status('server_failure', 0, full, 8) == 'SERVER_FAILURE'
    assert R.screen_status('capacity_interruption', None, None, 8) == 'CAPACITY_INTERRUPTION'
    assert R.screen_status('batch_deadline', 0, full, 8) == 'DEADLINE'
    s = R.score({'stop': 'transport_failure', 'episodes': [dict(seed=200, cause='transport_failure')]},
                'CHILD_STOPPED_TRANSPORT_FAILURE')
    assert s['taxonomy'] == {'transport_failure': 1, 'not_run: CHILD_STOPPED_TRANSPORT_FAILURE (not_started)': 7}


# ------------------------------------------------------------------ admission probes
def test_manifest_binding_and_its_failures():
    ok, d = R.probe_manifest(ROOT)
    assert ok, d['problems']
    m = json.loads((ROOT / R.MANIFEST_REL).read_text())
    for mutate, needle in ((lambda x: x['seeds'].append(208), 'seeds'),
                           (lambda x: x['settings'].update(temperature=0.2), 'settings'),
                           (lambda x: x['assignment'].update(gguf_sha256='0' * 64), 'gguf_sha256'),
                           (lambda x: x['caps'].update(logical_per_episode=20), 'caps'),
                           (lambda x: x['adapter'].update(prompt_sha256='x'), 'prompt')):
        bad = json.loads(json.dumps(m))
        mutate(bad)
        ok, d = R.probe_manifest(ROOT, bad)
        assert not ok and any(needle in p for p in d['problems']), (needle, d['problems'])


def test_memory_admission_at_fifty_percent():
    m = json.loads((ROOT / R.MANIFEST_REL).read_text())

    def run_at(pct):
        def run(cmd, env=None, timeout=60):
            if cmd[0] == 'memory_pressure':
                return 0, 'System-wide memory free percentage: %d%%\n' % pct, ''
            if cmd[:3] == ['sysctl', '-n', 'hw.memsize']:
                return 0, '34359738368\n', ''
            return 0, 'total = 15360.00M  used = 1.00M  free = 15359.00M\n', ''
        return run
    assert R.probe_memory(ROOT, m, run_at(49))[0] is False
    ok, d = R.probe_memory(ROOT, m, run_at(50))
    assert ok and d['projection_bytes'] == 4683074208 + int((0.88 + 16 + 2) * 2 ** 30)
    assert d['projection_limit_bytes'] == 34359738368 - 2 * 2 ** 30


def test_sweep_signals_only_the_exclusive_browser_runtime():
    m = json.loads((ROOT / R.MANIFEST_REL).read_text())
    table = ['%d 1 %s' % (11, ROOT / 'work/ms-playwright-req015/chromium-1117/chrome-mac/Chromium.app/x --type=gpu'),
             '%d 1 %s' % (12, ROOT / 'work/venvs/browsergym_9e779f0/lib/python3.12/site-packages/playwright/driver/node'),
             '13 1 /Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
             '14 1 /Users/x/ICLR-WinRatioAgentEvals/.venv/bin/python run.py']
    killed = []
    state = {'n': 0}

    def run(cmd, env=None, timeout=60):
        state['n'] += 1
        rows = table if state['n'] <= 2 else table[2:]
        return 0, '\n'.join(rows) + '\n', ''
    out = R.sweep_browser_processes(ROOT, m, run=run, kill=lambda pid, sig: killed.append(pid), sleep=lambda s: None)
    assert out['found'] == [11, 12] and set(killed) == {11, 12} and out['remaining'] == []
    killed.clear()
    state['n'] = 0
    out = R.sweep_browser_processes(ROOT, m, run=run, kill=lambda pid, sig: killed.append(pid), sleep=lambda s: None,
                                    baseline=[12])                # running before the child started: not ours
    assert out['found'] == [11] and set(killed) == {11}


# ------------------------------------------------------------------ single shot, BLOCKED path and publication
def tmp_root(tmp_path):
    (tmp_path / 'configs').mkdir()
    shutil.copy(ROOT / R.MANIFEST_REL, tmp_path / R.MANIFEST_REL)
    return tmp_path


def probes(**fail):
    return OrderedDict((k, (lambda ok: (lambda root: (ok, {'probe': 'fake'})))(k not in fail)) for k in (
        'manifest', 'sources', 'browser', 'models', 'conflicts', 'memory', 'disk'))


def test_pin_failure_refuses_before_the_namespace(tmp_path):
    root = tmp_root(tmp_path)
    assert R.main([], root=root, probes=probes(sources=1)) == 3
    m = json.loads((ROOT / R.MANIFEST_REL).read_text())
    assert not (root / m['outputs']['raw']).exists() and not (root / m['outputs']['published']).exists()


def test_host_gate_failure_is_blocked_and_published_then_single_shot(tmp_path, capsys):
    root = tmp_root(tmp_path)
    assert R.main([], root=root, probes=probes(memory=1)) == 0
    m = json.loads((ROOT / R.MANIFEST_REL).read_text())
    pub = root / m['outputs']['published']
    s = json.loads((pub / 'screen_summary.json').read_text())
    assert s['status'] == 'BLOCKED' and s['blocked']['failed'] == ['memory'] and s['score']['full_success'] == 0
    assert (pub / 'manifest.json').read_bytes() == (ROOT / R.MANIFEST_REL).read_bytes()
    assert R.main([], root=root, probes=probes()) == 3


def test_main_restores_the_signal_handlers_it_replaced(tmp_path):
    import signal
    before = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)}
    root = tmp_root(tmp_path)
    assert R.main([], root=root, probes=probes(), runner=lambda ctx: ctx['summary'].update(status='COMPLETED')) == 0
    assert {sig: signal.getsignal(sig) for sig in before} == before   # pool workers must not inherit SIG_IGN


def test_completed_runner_path_scores_the_child_batch(tmp_path):
    root = tmp_root(tmp_path)
    m = json.loads((ROOT / R.MANIFEST_REL).read_text())

    def runner(ctx):
        (ctx['raw'] / 'batch_summary.json').write_text(json.dumps({'episodes': [
            dict(seed=s, cause='full_success' if s == 203 else 'wrong_booking', full_success=s == 203)
            for s in range(200, 208)]}))
        ctx['summary']['status'] = 'COMPLETED'
    assert R.main([], root=root, probes=probes(), runner=runner) == 0
    s = json.loads((root / m['outputs']['published'] / 'screen_summary.json').read_text())
    assert (s['status'], s['score']['full_success'], s['score']['taxonomy']) == (
        'COMPLETED', 1, {'wrong_booking': 7, 'full_success': 1})
    pm = json.loads((root / m['outputs']['published'] / 'publication_manifest.json').read_text())
    assert {'manifest.json', 'admission.json', 'batch_summary.json', 'screen_summary.json'} <= set(pm)


# ------------------------------------------------------------------ manifest facts and the pinned action set
def test_manifest_facts():
    m = json.loads((ROOT / R.MANIFEST_REL).read_text())
    assert m['request'] == 'DTR-REQ-016' and m['lead_commit'] == '97656b5' and m['source_commit'] == 'bdd007a'
    assert m['seeds'] == [200, 201, 202, 203, 204, 205, 206, 207]
    assert m['assignment']['gguf_sha256'] == '87a3665ca3247c54dfa198010f6e1f48d41611029bbcb5ed185a5ad05fcd3b81'
    assert m['lead_pins']['llama_cpp_commit'] == '4fea119de30f6a923992780f6fd5ccb0bee5d47d'
    assert m['caps']['batch_wall_s'] == 90 * 60 and m['caps']['artifact_gib'] == 2
    assert m['capacity']['thresholds'] == {'admission': {'physical_free_pct': 50, 'host_disk_free_gib': 25},
                                           'post_load': {'physical_free_pct': 20, 'host_disk_free_gib': 25},
                                           'episode': {'physical_free_pct': 10, 'host_disk_free_gib': 15}}
    assert (m['capacity']['sample_interval_s'], m['capacity']['max_gap_s']) == (5, 10)
    assert m['task']['gym_id'] == 'browsergym/miniwob.book-flight'
    assert m['adapter']['system_prompt'] == AD.SYSTEM_PROMPT and m['adapter']['user_template'] == AD.USER_TEMPLATE
    assert m['browser']['action_set'] == ['click', 'fill', 'noop']
    assert not set(m['seeds']) & {0, 1, 2, 3, 4, 1000, 1001}


BG_PY = ROOT / 'work/venvs/browsergym_9e779f0/bin/python'


@pytest.mark.skipif(not BG_PY.exists(), reason='pinned BrowserGym venv absent')
def test_pinned_browsergym_action_set_executes_only_click_fill_noop():
    code = ("from browsergym.core.action.highlevel import HighLevelActionSet\n"
            "from browsergym.core.action.functions import click, fill\n"
            "a = HighLevelActionSet(subsets=['custom'], custom_actions=[click, fill], multiaction=False, strict=True)\n"
            "print(sorted(a.action_set))\n"
            "for bad in (\"goto('file:///x')\", \"click('1')\\nclick('2')\", \"new_tab()\", \"__import__('os')\"):\n"
            "    try:\n        a.to_python_code(bad)\n        print('ACCEPTED', bad)\n"
            "    except Exception as e:\n        print('rejected')\n")
    out = subprocess.run([str(BG_PY), '-c', code], capture_output=True, text=True, timeout=120).stdout.split('\n')
    assert out[0] == "['click', 'fill', 'noop']"
    assert out[1:5] == ['rejected'] * 4
