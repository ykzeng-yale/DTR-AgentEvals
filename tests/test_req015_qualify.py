"""DTR-REQ-015 fixtures: the no-model MiniWoB book-flight qualification's pure parsing, choice, predicate, verdict,
resource and gate logic, and the scripted policy against a fake page. Expected values are written by hand from the
page text (recorded from a development probe), never recomputed with the code under test. BrowserGym is not needed.
"""
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments/v2_browser'))
import req015_qualify as Q  # noqa: E402

GOAL_DEC = 'Book the shortest one-way flight from: Akuton, AK to: Page, AZ on 12/22/2016.'

RESET = """RootWebArea 'Book Flight Task', focused
\t[17] heading 'Book Your One-Way Flight'
\t[19] textbox 'From:'
\t[21] textbox 'To:'
\tStaticText 'Departure Date'
\t[25] textbox ''
\t[27] button 'Search'
\t[30] status '', live='assertive', atomic, relevant='additions'
\t[32] status '', live='assertive', atomic, relevant='additions'"""

FROM_OPTIONS = """RootWebArea 'Book Flight Task', focused
\t[19] textbox 'From:' value='Akuton', focused
\t\tStaticText 'Akuton'
\t[21] textbox 'To:'
\tStaticText 'Departure Date'
\t[25] textbox ''
\t[27] button 'Search'
\t[29] list 'Akuton, AK (KQA)'
\t\t[34] listitem ''
\t\t\tListMarker ''
\t\t\t\timage ''
\t\t\tStaticText 'Akuton, AK (KQA)'"""

TO_OPTIONS = """RootWebArea 'Book Flight Task', focused
\t[19] textbox 'From:' value='Akuton, AK (KQA)'
\t[21] textbox 'To:' value='Page', focused
\tStaticText 'Departure Date'
\t[25] textbox ''
\t[27] button 'Search'
\t[31] list 'Page, AZ (PGA)'
\t\t[38] listitem ''
\t\t\tListMarker ''
\t\t\t\timage ''
\t\t\tStaticText 'Page, AZ (PGA)'"""

FILLED = """RootWebArea 'Book Flight Task', focused
\t[19] textbox 'From:' value='Akuton, AK (KQA)'
\t[21] textbox 'To:' value='Page, AZ (PGA)', focused
\tStaticText 'Departure Date'
\t[25] textbox ''
\t[27] button 'Search'"""


def calendar(month, prev_bid='43', next_bid=None, first_day_bid=74, n_days=31):
    lines = [FILLED, "\t[%s] link 'Prev'" % prev_bid if prev_bid else "\tStaticText 'Prev'"]
    if prev_bid:
        lines.append("\t\tStaticText 'Prev'")
    lines.append("\t[%s] link 'Next'\n\t\tStaticText 'Next'" % next_bid if next_bid else "\tStaticText 'Next'")
    lines += ["\tStaticText '%s'" % month, "\tStaticText ''", "\tStaticText '2016'", "\t[50] table ''"]
    for d in range(1, n_days + 1):
        lines.append("\t\t\t\t[%d] gridcell '%d'\n\t\t\t\t\t[%d] link '%d'" % (first_day_bid + 2 * d - 3, d,
                                                                             first_day_bid + 2 * d - 2, d))
    return '\n'.join(lines)


RESULTS = """RootWebArea 'Book Flight Task', focused
\t[141] button 'Back'
\tStaticText 'KQA to PGA'
\tStaticText '12/22/2016'
\t[149] LabelText ''
\t\tStaticText 'Depart:'
\tStaticText '4:58 AM'
\t[163] LabelText ''
\t\tStaticText 'Duration:'
\tStaticText '26h 20m'
\t[167] button 'Book flight for $387'
\t[185] LabelText ''
\t\tStaticText 'Duration:'
\tStaticText '17h 45m'
\t[189] button 'Book flight for $237'
\t[207] LabelText ''
\t\tStaticText 'Duration:'
\tStaticText '3h 39m'
\t[211] button 'Book flight for $396'"""


# ------------------------------------------------------------------ goal and axtree parsing
def test_goal_parses_criterion_places_and_date():
    g = Q.parse_goal(GOAL_DEC)
    assert (g['criterion'], g['origin'], g['destination']) == ('shortest', 'Akuton, AK', 'Page, AZ')
    assert (g['month'], g['day'], g['year'], g['date']) == (12, 22, 2016, '12/22/2016')
    g = Q.parse_goal('Book the cheapest one-way flight from: ABR to: Albany, OR - Bus service on 10/03/2016.')
    assert (g['criterion'], g['origin'], g['destination'], g['month'], g['day']) == (
        'cheapest', 'ABR', 'Albany, OR - Bus service', 10, 3)
    assert Q.parse_goal('Click the button.') is None
    assert Q.parse_goal('Book the fastest one-way flight from: A to: B on 12/22/2016.') is None


def test_axtree_lookup_and_autocomplete_options():
    assert Q.find_bid(RESET, 'textbox', 'From:') == '19'
    assert Q.find_bid(RESET, 'textbox', '') == '25'
    assert Q.find_bid(RESET, 'button', 'Search') == '27'
    assert Q.find_bid(RESET, 'button', 'Book') is None
    assert Q.bids(RESET) == {'17', '19', '21', '25', '27', '30', '32'}
    assert Q.autocomplete_options(FROM_OPTIONS) == [('34', 'Akuton, AK (KQA)')]
    assert Q.autocomplete_options(TO_OPTIONS) == [('38', 'Page, AZ (PGA)')]
    assert Q.autocomplete_options(RESET) == []


def test_repr_quoted_names_with_an_apostrophe_are_parsed():
    text = ("\t[40] listitem ''\n\t\tListMarker ''\n\t\tStaticText \"Chicago, IL - O'Hare (ORD)\"\n"
            "\t[41] listitem ''\n\t\tStaticText 'Chicago, IL - Midway (MDW)'\n\tgeneric\n\t[42] button 'it\\'s'")
    assert Q.autocomplete_options(text) == [('40', "Chicago, IL - O'Hare (ORD)"), ('41', 'Chicago, IL - Midway (MDW)')]
    assert Q.choose_option(Q.autocomplete_options(text), "Chicago, IL - O'Hare") == ('40', "Chicago, IL - O'Hare (ORD)", 1)
    assert Q.find_bid(text, 'button', "it's") == '42'


def test_option_choice_by_code_or_city_prefix():
    opts = [('40', 'Albany, NY (ALB)'), ('41', 'Albany, OR - Bus service (CVO)'),
            ('42', 'Albany, OR - Bus service (QWY)'), ('43', "Coeur d'Alene, ID (COE)")]
    assert Q.choose_option(opts, 'Albany, OR - Bus service') == ('41', 'Albany, OR - Bus service (CVO)', 2)
    assert Q.choose_option(opts, 'QWY') == ('42', 'Albany, OR - Bus service (QWY)', 1)
    assert Q.choose_option(opts, 'ALB') == ('40', 'Albany, NY (ALB)', 1)
    assert Q.choose_option(opts, "Coeur d'Alene, ID") == ('43', "Coeur d'Alene, ID (COE)", 1)
    assert Q.choose_option(opts, 'Albany') == (None, None, 0)      # a city must be the whole prefix before ' ('
    assert Q.choose_option([('9', 'Abraham, XX (XYZ)')], 'ABR') == (None, None, 0)


def test_calendar_state_and_month_offsets():
    c = Q.calendar_state(calendar('December'))
    assert (c['month'], c['year'], c['prev_bid'], c['next_bid']) == (12, 2016, '43', None)
    assert len(c['days']) == 31 and c['days'][1] == '74' and c['days'][22] == '116' and c['days'][31] == '134'
    c = Q.calendar_state(calendar('November', next_bid='45', n_days=30))
    assert (c['month'], c['next_bid'], len(c['days'])) == (11, '45', 30)
    c = Q.calendar_state(calendar('October', prev_bid=None, next_bid='45'))
    assert (c['month'], c['prev_bid'], c['next_bid']) == (10, None, '45')
    assert Q.calendar_state(FILLED) is None
    assert Q.month_offset(12, 2016, 10, 2016) == -2
    assert Q.month_offset(10, 2016, 12, 2016) == 2
    assert Q.month_offset(12, 2016, 12, 2016) == 0
    assert Q.month_offset(12, 2016, 1, 2017) == 1


def test_flights_parse_and_choice_from_displayed_values():
    rows = Q.flights(RESULTS)
    assert [(r['duration_minutes'], r['price'], r['book_bid']) for r in rows] == [
        (1580, 387, '167'), (1065, 237, '189'), (219, 396, '211')]
    assert Q.choose_flight(rows, 'shortest') == ('211', False)
    assert Q.choose_flight(rows, 'cheapest') == ('189', False)
    assert Q.choose_flight(rows, 'shortest', worst=True) == ('167', False)
    assert Q.choose_flight(rows, 'cheapest', worst=True) == ('211', False)
    tied = [OrderedDict(duration_minutes=100, price=300, book_bid='a'),
            OrderedDict(duration_minutes=90, price=300, book_bid='b')]
    assert Q.choose_flight(tied, 'cheapest') == ('a', True)
    assert Q.choose_flight(tied, 'shortest') == ('b', False)
    assert Q.choose_flight([], 'cheapest') == (None, False)


# ------------------------------------------------------------------ predicate, verdict, resources, isolation
def test_full_success_needs_done_and_raw_reward_exactly_one():
    assert Q.full_success({'DONE_GLOBAL': True, 'RAW_REWARD_GLOBAL': 1.0})
    assert not Q.full_success({'DONE_GLOBAL': True, 'RAW_REWARD_GLOBAL': -1.0})
    assert not Q.full_success({'DONE_GLOBAL': True, 'RAW_REWARD_GLOBAL': 0.5, 'browsergym_reward': 1.0})
    assert not Q.full_success({'DONE_GLOBAL': False, 'RAW_REWARD_GLOBAL': 1.0})
    assert not Q.full_success({'DONE_GLOBAL': True, 'REWARD_GLOBAL': 1.0})
    assert not Q.full_success({})


def test_verdict_rules():
    all_true = {c: True for c in Q.QUALIFICATION_CHECKS}
    assert Q.verdict(False, all_true) == {'verdict': 'BLOCKED', 'failed_checks': []}
    assert Q.verdict(True, all_true) == {'verdict': 'QUALIFIED', 'failed_checks': []}
    bad = dict(all_true, reset_reproducible=False)
    del bad['browser_isolation']
    assert Q.verdict(True, bad) == {'verdict': 'NOT_QUALIFIED',
                                    'failed_checks': ['reset_reproducible', 'browser_isolation']}
    assert len(Q.QUALIFICATION_CHECKS) == 10


def test_process_tree_rss_sum():
    ps = '1 0 100\n10 1 200\n11 10 300\n12 1 400\n20 0 999\nbad line here\n13 11 5\n'
    assert Q.tree_rss_kb(ps, 10) == 505
    assert Q.tree_rss_kb(ps, 1) == 1005
    assert Q.tree_rss_kb(ps, 99) == 0


def test_monitor_flags_a_breach_and_counts_errors():
    m = Q.Monitor(1000 * 1024, sh=lambda cmd, timeout=None: (0, '%d 1 600\n' % __import__('os').getpid(), ''))
    m.run_once()
    assert (m.peak_kb, m.samples, m.breached.is_set()) == (600, 1, False)
    m.sh = lambda cmd, timeout=None: (0, '%d 1 2000\n' % __import__('os').getpid(), '')
    m.run_once()
    assert (m.peak_kb, m.breached.is_set()) == (2000, True)
    m.sh = lambda cmd, timeout=None: (1, '', 'err')
    m.run_once()
    assert (m.errors, m.samples) == (1, 2)


def test_isolation_accepts_only_local_schemes():
    ok = [{'initial_resources': ['file:///x/book-flight.html', 'file:///x/core.js'], 'requests_after_reset': ['data:image/gif']}]
    assert Q.isolation_ok(ok) == (True, {'n_urls': 3, 'non_local_schemes': []})
    bad = [{'initial_resources': ['file:///x'], 'requests_after_reset': ['https://jqueryui.com/x', 'http://a']}]
    assert Q.isolation_ok(bad) == (False, {'n_urls': 3, 'non_local_schemes': ['http', 'https']})
    assert Q.isolation_ok([{'initial_resources': [], 'requests_after_reset': []}])[0] is False


# ------------------------------------------------------------------ host gates (fakes)
def fake_run(free_pct, extra_ps=''):
    def run(cmd, env=None, timeout=60):
        if cmd[0] == 'memory_pressure':
            return 0, 'System-wide memory free percentage: %d%%\n' % free_pct, ''
        if cmd[:2] == ['sysctl', '-n']:
            return 0, '34359738368\n', ''
        if cmd[0] == 'ps':
            import os
            return 0, '%d 1 python req015_qualify.py\n%s' % (os.getpid(), extra_ps), ''
        return 1, '', 'unexpected'
    return run


class Usage:
    def __init__(self, gib):
        self.free = gib * 2 ** 30


def gates(free_pct, disk_gib=40, peer_ok=True, extra_ps=''):
    manifest = json.loads((ROOT / Q.MANIFEST_REL).read_text())
    return Q.host_gates(manifest, ROOT, run=fake_run(free_pct, extra_ps), peer=lambda run: (peer_ok, {'run_lease': 'none'}),
                        usage=lambda p: Usage(disk_gib))


def test_host_gates_memory_disk_peer_and_other_runner():
    ok, d = gates(40)                                      # 0.40 x 32 GiB = 12.8 GiB >= 10
    assert ok and all(v['ok'] for v in d.values())
    ok, d = gates(30)                                      # 9.6 GiB < 10
    assert not ok and d['memory']['ok'] is False
    ok, d = gates(40, disk_gib=26.9)
    assert not ok and d['disk']['ok'] is False
    ok, d = gates(40, peer_ok=False)
    assert not ok and d['peer']['ok'] is False
    ok, d = gates(40, extra_ps='999999 1 /v/bin/python experiments/v2_browser/req015_qualify.py\n')
    assert not ok and d['no_other_req015']['detail']['other_pids'] == [999999]
    ok, d = gates(40, extra_ps='999998 1 /v/bin/python experiments/v2_browser/req015_qualify.py --admission-only\n')
    assert ok


# ------------------------------------------------------------------ scripted policy against a fake page
class FakeEp:
    """A stand-in for Episode: the page state machine returns canned axtrees for the expected actions."""

    def __init__(self, goal, pages):
        self.goal, self.pages, self.steps, self.actions = goal, pages, [], []

    def reset(self):
        self.steps.append({'step': 0})
        return {'goal': self.goal, 'axtree': RESET}

    def act(self, action, decision):
        self.actions.append(action)
        self.steps.append({'step': len(self.steps), 'decision': decision})
        return {'goal': self.goal, 'axtree': self.pages.get(action, FILLED)}, False


def dec_pages(extra=None):
    pages = {"fill('19', 'Akuton, AK')": FROM_OPTIONS, "click('34')": FILLED, "fill('21', 'Page, AZ')": TO_OPTIONS,
             "click('38')": FILLED, "click('25')": calendar('December'), "click('27')": RESULTS}
    pages.update(extra or {})
    return pages


def test_positive_policy_books_the_shortest_flight_using_revealed_content_only():
    ep = FakeEp(GOAL_DEC, dec_pages())
    notes = Q.run_booking(ep, worst=False)
    assert ep.actions == ["fill('19', 'Akuton, AK')", "click('34')", "fill('21', 'Page, AZ')", "click('38')",
                          "click('25')", "click('116')", "click('27')", "click('211')"]
    kinds = [s['decision']['kind'] for s in ep.steps[1:]]
    assert kinds == ['type_goal_text', 'autocomplete_option', 'type_goal_text', 'autocomplete_option',
                     'open_datepicker', 'calendar_day', 'search', 'flight_choice']
    fb = [s['decision'] for s in ep.steps[1:] if s['decision']['feedback_dependent']]
    assert [d['kind'] for d in fb] == ['autocomplete_option', 'autocomplete_option', 'calendar_day', 'flight_choice']
    assert [d['decided_from_step'] for d in fb] == [1, 3, 5, 7]
    assert fb[-1]['n_visible_alternatives'] == 3 and fb[-1]['consequential'] is True
    assert notes['chosen_bid'] == '211' and notes['visible_tie'] is False and notes['calendar_opened_at'] == '12/2016'


def test_negative_policy_has_the_same_prefix_and_books_the_longest_flight():
    ep = FakeEp(GOAL_DEC, dec_pages())
    Q.run_booking(ep, worst=True)
    assert ep.actions[:-1] == ["fill('19', 'Akuton, AK')", "click('34')", "fill('21', 'Page, AZ')", "click('38')",
                               "click('25')", "click('116')", "click('27')"]
    assert ep.actions[-1] == "click('167')"


def test_positive_policy_navigates_back_two_months_by_the_displayed_month():
    goal = 'Book the cheapest one-way flight from: Akuton, AK to: Page, AZ on 10/05/2016.'
    pages = dec_pages({"click('43')": calendar('November', next_bid='45', n_days=30)})
    ep = FakeEp(goal, pages)
    seq = iter([calendar('November', next_bid='45', n_days=30), calendar('October', prev_bid=None, next_bid='45')])
    orig = ep.act

    def act(action, decision):
        if action == "click('43')":
            ep.actions.append(action)
            ep.steps.append({'step': len(ep.steps), 'decision': decision})
            return {'goal': goal, 'axtree': next(seq)}, False
        return orig(action, decision)
    ep.act = act
    Q.run_booking(ep, worst=False)
    assert ep.actions == ["fill('19', 'Akuton, AK')", "click('34')", "fill('21', 'Page, AZ')", "click('38')",
                          "click('25')", "click('43')", "click('43')", "click('82')", "click('27')", "click('189')"]
    nav = [s['decision'] for s in ep.steps[1:] if s['decision']['kind'] == 'month_navigation']
    assert len(nav) == 2 and 'Prev' in nav[0]['evidence'] and '12/2016' in nav[0]['evidence']


def test_policy_stops_when_no_option_matches_or_no_results():
    ep = FakeEp('Book the cheapest one-way flight from: Nowhere, ZZ to: Page, AZ on 12/22/2016.',
                dec_pages({"fill('19', 'Nowhere, ZZ')": FROM_OPTIONS}))
    notes = Q.run_booking(ep, worst=False)
    assert 'no visible autocomplete option' in notes['stopped'] and ep.actions == ["fill('19', 'Nowhere, ZZ')"]
    ep = FakeEp(GOAL_DEC, dec_pages({"click('27')": FILLED}))
    notes = Q.run_booking(ep, worst=False)
    assert notes['stopped'] == 'no flights visible' and ep.actions[-1] == "click('27')"
    ep = FakeEp('Unparsable goal', dec_pages())
    assert Q.run_booking(ep, worst=False)['stopped'] == 'goal did not parse' and ep.actions == []


# ------------------------------------------------------------------ manifest
def test_manifest_pins_the_task_sources_plan_and_caps():
    m = json.loads((ROOT / Q.MANIFEST_REL).read_text())
    audit = (ROOT / 'docs/literature_harness_design_20260921.md').read_text()
    for name, repo in (('BrowserGym', 'ServiceNow/BrowserGym'), ('AgentLab', 'ServiceNow/AgentLab'),
                       ('miniwob-plusplus', 'Farama-Foundation/miniwob-plusplus')):
        pinned = re.search(r'github\.com/%s/tree/([0-9a-f]{40})' % re.escape(repo), audit).group(1)
        assert m['sources'][name]['commit'] == pinned
    assert (m['sources']['miniwob-plusplus']['license'], m['sources']['BrowserGym']['license']) == ('MIT', 'Apache-2.0')
    assert m['task']['gym_id'] == 'browsergym/miniwob.book-flight' and m['task']['subdomain'] == 'book-flight'
    assert m['caps'] == {'wall_seconds': 1800, 'peak_memory_gib': 8, 'artifact_gib': 2}
    labels = {p['label']: p for p in m['plan']}
    assert (labels['primary_positive']['seed'], labels['negative']['seed'], labels['noop']['seed']) == (0, 0, 0)
    assert labels['reset_repeat_a']['seed'] == labels['reset_repeat_b']['seed'] == 0
    assert labels['reset_other_seed']['seed'] == 1 and labels['noop']['noop_steps'] == 5
    assert 1000 not in [p['seed'] for p in m['plan']]                      # the development-probe seed is excluded
    assert m['environment']['pw_context_kwargs'] == {'offline': True}
    assert m['environment']['locale_override'] is None and m['environment']['timezone_override'] is None
    assert m['min_feedback_dependent_decisions'] == 2
    assert set(m['checks']) == set(Q.QUALIFICATION_CHECKS)
    assert m['outputs']['published'].startswith('results/v2_browser/')


# ------------------------------------------------------------------ measured feedback dependence and checks
def step(axtree, action=None, decision=None, error=''):
    return {'action': action, 'decision': decision,
            'agent_visible': {'axtree': axtree, 'last_action_error': error, 'goal': GOAL_DEC}}


def fb(kind, r, n=1):
    return Q.feedback_decision(kind, r, n, 'test')


def test_feedback_dependence_is_measured_from_the_saved_observations():
    steps = [step(RESET), step(FROM_OPTIONS, "fill('19', 'Akuton, AK')", {'kind': 'type_goal_text', 'feedback_dependent': False}),
             step(FILLED, "click('34')", fb('autocomplete_option', 1)),
             step(RESULTS, "click('27')", {'kind': 'search', 'feedback_dependent': False}),
             step(RESULTS, "click('211')", fb('flight_choice', 3, 3)),
             step(RESET, "click('19')", fb('bogus_present_at_reset', 3)),
             step(RESET, "click('999')", fb('absent_when_chosen', 4))]
    rows = [r for _, r in Q.verify_feedback(steps)]
    assert [(r['kind'], r['verified']) for r in rows] == [('autocomplete_option', True), ('flight_choice', True),
                                                          ('bogus_present_at_reset', False), ('absent_when_chosen', False)]
    assert (rows[0]['target_first_visible_at_step'], rows[1]['target_first_visible_at_step']) == (1, 3)
    assert rows[2]['absent_from_reset_observation'] is False and rows[3]['present_when_chosen'] is False
    steps[3]['agent_visible']['last_action_error'] = 'TimeoutError'          # the revealing action failed
    assert [r['verified'] for _, r in Q.verify_feedback(steps)][:2] == [True, False]


class Mon:
    def __init__(self, samples=10, errors=0, breached=False):
        import threading
        self.samples, self.errors, self.breached = samples, errors, threading.Event()
        if breached:
            self.breached.set()


def summary(label, kind, **kw):
    base = {'label': label, 'kind': kind, 'seed': 0, 'n_actions': 8, 'notes': {'goal': {'criterion': 'shortest'},
            'flights_revealed': [{'duration_text': '3h 39m', 'price': 396}]}, 'feedback_dependent_decisions': 4,
            'feedback_decision_kinds': ['autocomplete_option', 'flight_choice'], 'steps_with_action_error': [],
            'terminal': {'DONE_GLOBAL': True, 'RAW_REWARD_GLOBAL': 1}, 'full_success': True}
    base.update(kw)
    return base


def plan_records(manifest, drop=()):
    recs = []
    for p in manifest['plan']:
        if p['label'] in drop:
            continue
        goal = GOAL_DEC if p['label'] != 'reset_other_seed' else 'Book the cheapest one-way flight from: A to: B on 10/01/2016.'
        steps = [] if (p['label'] == 'reset_repeat_b' and 'empty_b' in drop) else [step(RESET)]
        for st in steps:
            st['agent_visible']['goal'] = goal
        recs.append((p, {'initial_resources': ['file:///x'], 'requests_after_reset': [], 'resource_timing_entries': [],
                         'steps': steps}))
    return recs


def good_summaries():
    return [summary('primary_positive', 'positive'),
            summary('negative', 'negative', terminal={'DONE_GLOBAL': True, 'RAW_REWARD_GLOBAL': -1}, full_success=False),
            summary('noop', 'noop', n_actions=5, feedback_dependent_decisions=0, feedback_decision_kinds=[],
                    terminal={'DONE_GLOBAL': False, 'RAW_REWARD_GLOBAL': 0}, full_success=False)]


def test_compute_checks_all_pass_and_each_condition_fails_closed():
    m = json.loads((ROOT / Q.MANIFEST_REL).read_text())
    checks, repro, iso = Q.compute_checks(m, True, True, good_summaries(), plan_records(m), None, 60.0, Mon(), 10 ** 6)
    assert all(checks[c] is True for c in Q.QUALIFICATION_CHECKS) and all(repro.values())
    s = good_summaries()
    s[0]['notes']['flights_revealed'] = [{'duration_text': '3h 40m', 'price': 396}]          # results differ
    assert Q.compute_checks(m, True, True, s, plan_records(m), None, 60, Mon(), 1)[0]['reset_reproducible'] is False
    s = good_summaries()
    s[2]['n_actions'] = 3                                                                    # no-op cut short
    assert Q.compute_checks(m, True, True, s, plan_records(m), None, 60, Mon(), 1)[0]['noop_fails_predicate'] is False
    s = good_summaries()
    s[0]['feedback_decision_kinds'] = ['autocomplete_option', 'calendar_day']               # no verified flight choice
    assert Q.compute_checks(m, True, True, s, plan_records(m), None, 60, Mon(), 1)[0]['feedback_dependent_decisions'] is False
    c = Q.compute_checks(m, True, True, good_summaries(), plan_records(m), 'cap: wall', 1801, Mon(errors=1), 1)[0]
    assert (c['no_harness_error'], c['resources_within_caps']) == (False, False)
    recs = plan_records(m)
    recs[0][1]['requests_after_reset'] = ['https://example.org/x']
    assert Q.compute_checks(m, True, True, good_summaries(), recs, None, 60, Mon(), 1)[0]['browser_isolation'] is False


def test_compute_checks_survives_missing_or_empty_traces():
    m = json.loads((ROOT / Q.MANIFEST_REL).read_text())
    checks, repro, _ = Q.compute_checks(m, True, True, good_summaries()[:1], plan_records(m, drop=('empty_b',)),
                                        'RuntimeError: reset failed', 30, Mon(), 1)
    assert checks['reset_reproducible'] is False and checks['no_harness_error'] is False
    assert Q.verdict(True, checks)['verdict'] == 'NOT_QUALIFIED'
