"""DTR-REQ-017 fixtures (no model, no browser, no server): the single bracket-id change of the versioned adapter, its
equivalence on every saved REQ-015 accessibility tree, the rejections the lead listed, a parser-level replay of the
saved REQ-016 replies (non-evidential: it re-parses text, it scores nothing), the child/parent wrappers and their
restoration of the frozen REQ-016 modules, the lead-release gate, and byte preservation of REQ-016.
"""
import glob
import hashlib
import json
import shutil
import sys
from collections import OrderedDict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / 'experiments/v2_browser', ROOT / 'experiments/v2_agent', ROOT / 'experiments/v2_adapter'):
    sys.path.insert(0, str(p))
import req016_adapter as A16  # noqa: E402
import req017_adapter as A17  # noqa: E402
import req016_episodes as EP  # noqa: E402
import req017_episodes as E17  # noqa: E402
import req016_screen as R  # noqa: E402
import req017_screen as R17  # noqa: E402

M17 = ROOT / 'configs/v2_req017_7b_bracket_pilot_20260925.json'
M16 = ROOT / 'configs/v2_req016_7b_browser_screen_20260925.json'
REQ015 = sorted(glob.glob(str(ROOT / 'results/v2_browser/req015_bookflight_qualification_20260925/trace_*.json')))
REQ016 = ROOT / 'results/v2_browser/req016_7b_browser_screen_20260925'
TREE = """RootWebArea 'Book Flight Task', focused
\t[17] heading 'Book Your One-Way Flight'
\t[19] textbox 'From:'
\t[21] textbox 'To:'
\tStaticText 'Departure Date'
\t[25] textbox ''
\t[27] button 'Search'"""


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ------------------------------------------------------------------ everything but parse_action is the REQ-016 object
def test_only_parse_action_differs_from_req016():
    for name in ('SYSTEM_PROMPT', 'USER_TEMPLATE', 'FORBIDDEN_MARKERS', 'CAUSES', 'ALLOWED', 'MAX_FILL_CHARS',
                 'EXCERPT_CHARS', 'model_view', 'error_excerpt', 'fill_text', 'history_lines', 'build_messages',
                 'leak_problems', 'tree_bids', 'canonical_body'):
        assert getattr(A17, name) is getattr(A16, name), name
    assert A17.parse_action is not A16.parse_action
    m17, m16 = json.loads(M17.read_text()), json.loads(M16.read_text())
    assert m17['adapter']['prompt_sha256'] == m16['adapter']['prompt_sha256'] == R.prompt_sha256()
    assert m17['adapter']['system_prompt'] == m16['adapter']['system_prompt'] == A16.SYSTEM_PROMPT
    assert m17['adapter']['user_template'] == m16['adapter']['user_template'] == A16.USER_TEMPLATE


# ------------------------------------------------------------------ equivalence on every saved REQ-015 tree
def saved_trees():
    trees = []
    for f in REQ015:
        for st in json.load(open(f))['steps']:
            trees.append(st['agent_visible']['axtree'])
    return trees


def test_bracketed_and_bare_current_ids_are_equivalent_on_every_saved_req015_tree():
    trees = saved_trees()
    assert len(REQ015) == 10 and len(trees) == 68
    n = 0
    for tree in trees:
        bids = A16.tree_bids(tree)
        assert bids
        for b in sorted(bids):
            for bare, bracketed in (("click('%s')" % b, "click('[%s]')" % b),
                                    ("fill('%s', 'Page, AZ')" % b, "fill('[%s]', 'Page, AZ')" % b)):
                want = bare
                assert A17.parse_action(bare, tree) == (want, None, '')
                assert A17.parse_action(bracketed, tree) == (want, None, A17.CANONICALIZED)
                assert A16.parse_action(bracketed, tree)[1] == 'unknown_bid'      # the frozen REQ-016 behaviour
                n += 1
    assert n > 1000


@pytest.mark.parametrize('reply,cause', [
    ("click('[99]')", 'unknown_bid'),                 # unknown id, bracketed
    ("click('99')", 'unknown_bid'),
    ("click('[[19]]')", 'unknown_bid'),               # nested
    ("click('[19')", 'unknown_bid'),                  # malformed
    ("click('19]')", 'unknown_bid'),
    ("click('[ 19 ]')", 'unknown_bid'),
    ("click('[]')", 'unknown_bid'),
    ("click('[19][21]')", 'unknown_bid'),
    ("click(' [19]')", 'unknown_bid'),
    ("click('[19] ')", 'unknown_bid'),
    ("click('[19]\\n')", 'unknown_bid'),            # '$' would accept a trailing newline; fullmatch does not
    ("click('[19]\\t')", 'unknown_bid'),
    ("fill('[19]\\n', 'x')", 'unknown_bid'),
    ("click('(19)')", 'unknown_bid'),
    ("goto('[19]')", 'forbidden_function'),
    ("press('[19]', 'Enter')", 'forbidden_function'),
    ("click('[19]', button='right')", 'bad_arguments'),
    ("noop('[19]')", 'bad_arguments'),
    ("fill('[19]')", 'bad_arguments'),
    ("fill('[19]', '%s')" % ('x' * 201), 'fill_too_long'),
    ("fill('[19]', 'A')\nclick('[27]')", 'multiple_actions'),
    ("fill('[19]', 'A')\nfill('[21]', 'B')\nfill('[25]', '12/22/2016')", 'multiple_actions'),
    ("fill('[19]', 'A')\nfill('[21]', 'B')\nfill('[25]', 'C')\nclick('[27]')", 'multiple_actions'),
    ("fill('19', 'A')\nclick('[27]')", 'multiple_actions'),
    ("Next: click('[19]')", 'no_action'),
])
def test_rejections_still_hold(reply, cause):
    action, got, _ = A17.parse_action(reply, TREE)
    assert action is None and got == cause


def test_an_id_seen_only_in_history_is_rejected():
    later_tree = TREE.replace("\t[19] textbox 'From:'\n", '')        # [19] was in an earlier page only
    assert '19' not in A16.tree_bids(later_tree)
    assert A17.parse_action("click('[19]')", later_tree)[1] == 'unknown_bid'
    assert A17.parse_action("click('19')", later_tree)[1] == 'unknown_bid'
    assert A17.canonical_bid('[19]', later_tree) is None and A17.canonical_bid('[21]', later_tree) == '21'


def test_valid_bare_and_noop_replies_are_unchanged():
    for reply in ("click('27')", "fill('19', \"Coeur d'Alene\")", 'noop()', "```\nclick('27')\n```"):
        assert A17.parse_action(reply, TREE) == A16.parse_action(reply, TREE)


# ------------------------------------------------------------------ parser-level replay of the saved REQ-016 replies
def test_req016_replies_reparsed_change_only_the_bracketed_single_action_cases():
    """Non-evidential parser check on saved text: no action is executed and no outcome is rescored."""
    rows = [json.loads(l) for f in sorted(REQ016.glob('episodes/seed*/steps.jsonl')) for l in open(f)
            if json.loads(l)['kind'] == 'call']
    assert len(rows) == 128
    old = [A16.parse_action(r['reply'], r['model_view']['axtree']) for r in rows]
    new = [A17.parse_action(r['reply'], r['model_view']['axtree']) for r in rows]
    assert [o[1] for o in old] == [r['invalid_cause'] for r in rows]              # the frozen record reproduces
    became_valid = [(o, n) for o, n in zip(old, new) if o[1] == 'unknown_bid']
    assert len(became_valid) == 62 and all(n[1] is None and n[2] == A17.CANONICALIZED and n[0].startswith("fill('19', ")
                                           for _, n in became_valid)
    still = [n for o, n in zip(old, new) if o[1] == 'multiple_actions']
    assert len(still) == 66 and all(n == o for o, n in zip([o for o in old if o[1] == 'multiple_actions'], still))


# ------------------------------------------------------------------ child wrapper
class FakeEnv:
    def __init__(self):
        self.actions = []

    def reset(self, seed):
        return dict(goal='Book the cheapest one-way flight from: Akuton, AK to: Page, AZ on 12/22/2016.',
                    axtree_object=TREE, last_action_error=''), {'task_info': {'DONE_GLOBAL': False}}

    def step(self, action):
        self.actions.append(action)
        return dict(goal='g', axtree_object=TREE, last_action_error=''), 0.0, False, False, {'task_info': {}}

    def close(self):
        pass


def reply(text):
    return OrderedDict(kind='response', http_status=200, seconds=0.1, body=json.dumps(
        {'choices': [{'message': {'content': text}, 'finish_reason': 'stop'}],
         'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}))


def test_child_wrapper_rebinds_only_the_adapter_and_label_and_restores_them(tmp_path):
    assert EP.AD is A16 and EP.REQUEST == 'DTR-REQ-016'
    replies = iter([reply("fill('[19]', 'Akuton, AK')"), reply("click('[99]')")])
    bodies = []

    def transport(body, timeout):
        bodies.append(body)
        return next(replies)
    cfg = dict(caps=dict(logical_per_episode=2, physical_per_episode=4, attempts_per_call=2, request_timeout_s=30,
                         artifact_gib=2), settings=dict(temperature=0, max_tokens=1536), alias='a',
               deadline_epoch=1e12)
    env = FakeEnv()
    with E17.installed():
        assert EP.AD is A17 and EP.REQUEST == 'DTR-REQ-017'
        s = EP.run_episode(300, cfg, env, transport, tmp_path / 'seed300', flatten=lambda x: x)
    assert EP.AD is A16 and EP.REQUEST == 'DTR-REQ-016'                        # restored
    assert env.actions == ["fill('19', 'Akuton, AK')"]
    assert (s['executed_actions'], s['invalid_causes'], s['request']) == (1, {'unknown_bid': 1}, 'DTR-REQ-017')
    steps = [json.loads(l) for l in (tmp_path / 'seed300' / 'steps.jsonl').read_text().splitlines()]
    assert steps[1]['parsed_action'] == "fill('19', 'Akuton, AK')" and steps[1]['invalid_detail'] == A17.CANONICALIZED
    first = json.loads(bodies[0])['messages']
    assert first == A16.build_messages(dict(goal=FakeEnv().reset(0)[0]['goal'], axtree=TREE, last_action_error=''),
                                       [], 2)                                     # the unchanged REQ-016 prompt
    rec = json.loads((tmp_path / 'seed300' / 'receipts' / 'call01_attempt01.request.json').read_text())
    assert rec['request'] == 'DTR-REQ-017'


def test_history_only_and_multi_action_replies_never_reach_the_browser(tmp_path):
    """Execution level: after fill('[19]') the page drops [19]; a later click('[19]') and 3- or 4-line replies are
    recorded as invalid and nothing but the first canonical action reaches the environment."""
    class DroppingEnv(FakeEnv):
        def step(self, action):
            self.actions.append(action)
            return dict(goal='g', axtree_object=TREE.replace("\t[19] textbox 'From:'\n", ''), last_action_error=''), \
                0.0, False, False, {'task_info': {}}
    replies = iter([reply("fill('[19]', 'A')"), reply("click('[19]')"),
                    reply("fill('[21]', 'B')\nfill('[25]', 'C')\nclick('[27]')"),
                    reply("fill('[21]', 'B')\nfill('[25]', 'C')\nclick('[27]')\nnoop()")])
    cfg = dict(caps=dict(logical_per_episode=4, physical_per_episode=8, attempts_per_call=2, request_timeout_s=30,
                         artifact_gib=2), settings=dict(temperature=0, max_tokens=1536), alias='a', deadline_epoch=1e12)
    env = DroppingEnv()
    with E17.installed():
        s = EP.run_episode(301, cfg, env, lambda body, timeout: next(replies), tmp_path / 's', flatten=lambda x: x)
    assert env.actions == ["fill('19', 'A')"]
    assert s['invalid_causes'] == {'unknown_bid': 1, 'multiple_actions': 2} and s['executed_actions'] == 1


# ------------------------------------------------------------------ parent wrapper
def test_manifest_binding_and_its_failures():
    ok, d = R17.probe_manifest(ROOT)
    assert ok, d['problems']
    m = json.loads(M17.read_text())
    for mutate, needle in ((lambda x: x.update(seeds=[200, 301, 302, 303]), 'seeds'),
                           (lambda x: x.update(seeds=[300, 301, 302, 304]), 'seeds'),
                           (lambda x: x['caps'].update(batch_wall_s=5400), 'caps'),
                           (lambda x: x['settings'].update(temperature=0.1), 'settings'),
                           (lambda x: x['adapter'].update(prompt_sha256='0' * 64), 'prompt'),
                           (lambda x: x['adapter']['files'].update({'experiments/v2_browser/req017_adapter.py': '0'}),
                            'req017_adapter'),
                           (lambda x: x['req016'].update(req016_archive_publication_manifest_sha256='0'), 'REQ-016')):
        bad = json.loads(json.dumps(m))
        mutate(bad)
        ok, d = R17.probe_manifest(ROOT, bad)
        assert not ok and any(needle in p for p in d['problems']), (needle, d['problems'])


def test_manifest_changes_only_the_declared_sections():
    m17, m16 = json.loads(M17.read_text()), json.loads(M16.read_text())
    for k in ('assignment', 'model_source', 'lead_pins', 'settings', 'capacity', 'task', 'accounting'):
        assert m17[k] == m16[k], k
    assert 'REQ-017 holder label' in m17['serving']['code'] and 'REQ-016 holder' not in m17['serving']['code']
    assert {k for k in m16['statuses'] if m17['statuses'][k] != m16['statuses'][k]} == {'COMPLETED'}
    assert 'every manifest seed (four)' in m17['statuses']['COMPLETED']
    assert 'REQ-016 or REQ-017 process' in m17['host_gates'] and 'lead-release gate' in m17['host_gates']
    assert 'noop() does not count' in m17['discriminator']['predeclared']
    assert m17['release_gate']['token'].startswith('RELEASE DTR-REQ-017 manifest_sha256=')
    assert m17['seeds'] == [300, 301, 302, 303] and m17['caps'] == dict(m16['caps'], batch_wall_s=2700)
    assert m17['browser'] == dict(m16['browser'], entry='experiments/v2_browser/req017_episodes.py')
    assert m17['release_gate']['released_at_freeze'] is False
    assert m17['req016']['req016_manifest_sha256'] == sha(M16)
    assert m17['req016']['req016_archive_publication_manifest_sha256'] == sha(REQ016 / 'publication_manifest.json')


def test_req016_sources_and_archive_are_byte_identical_to_their_bindings():
    m16 = json.loads(M16.read_text())
    for rel, want in m16['adapter']['files'].items():
        assert sha(ROOT / rel) == want, rel
    pm = json.loads((REQ016 / 'publication_manifest.json').read_text())
    assert len(pm) == 292 and all(sha(REQ016 / k) == v['published_sha256'] for k, v in pm.items())


def test_discriminator_counts_come_from_the_steps_and_ignore_noop(tmp_path):
    rows = {300: [dict(kind='call', executed=True, parsed_action="fill('19', 'A')", invalid_cause=None,
                       invalid_detail=A17.CANONICALIZED), dict(kind='call', executed=True, parsed_action='noop()')],
            301: [dict(kind='call', executed=True, parsed_action='noop()'),
                  dict(kind='call', executed=False, parsed_action=None, invalid_cause='multiple_actions')]}
    for seed, lines in rows.items():
        d = tmp_path / 'episodes' / ('seed%d' % seed)
        d.mkdir(parents=True)
        (d / 'steps.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in [dict(kind='reset')] + lines))
    shutil.copy(M17, tmp_path / 'manifest.json')
    batch = {'episodes': [dict(seed=s, cause='logical_budget_exhausted', full_success=False, executed_actions=2)
                          for s in (300, 301, 302, 303)]}
    s = R17.score(batch, 'COMPLETED', tmp_path)
    assert [(r['executed_click_fill'], r['executed_canonicalized'], r['executed_noop']) for r in s['rows']] == [
        (1, 1, 1), (0, 0, 1), (0, 0, 0), (0, 0, 0)]
    assert (s['episodes_with_executed_click_fill'], s['executed_canonicalized_total']) == (1, 1)
    assert s['discriminator']['action_executes'] is True and s['discriminator']['at_least_one_full_success'] is False
    only_noop = R17.score({'episodes': batch['episodes'][1:2]}, 'COMPLETED', tmp_path)
    assert only_noop['rows'][1]['executed_noop'] == 1 and only_noop['rows'][1]['executed_click_fill'] == 0


def test_score_uses_the_four_pilot_seeds():
    batch = {'episodes': [dict(seed=300, cause='full_success', full_success=True, executed_actions=9),
                          dict(seed=301, cause='logical_budget_exhausted', full_success=False, executed_actions=2),
                          dict(seed=302, cause='logical_budget_exhausted', full_success=False, executed_actions=0),
                          dict(seed=303, cause='wrong_booking', full_success=False, executed_actions=8)]}
    s = R17.score(batch, 'COMPLETED')
    assert (s['full_success'], s['denominator'], s['episodes_with_executed_action']) == (1, 4, 3)
    assert s['taxonomy'] == {'full_success': 1, 'logical_budget_exhausted': 2, 'wrong_booking': 1}
    s = R17.score({'episodes': batch['episodes'][:1]}, 'CAPACITY_INTERRUPTION')
    assert [r['cause'] for r in s['rows']] == ['full_success', 'not_run_capacity', 'not_run_capacity',
                                               'not_run_capacity']


SHA = 'a' * 40
FREEZE = 'f' * 40
REMOTE = 'e' * 40


def token(sha=None):
    return 'RELEASE DTR-REQ-017 manifest_sha256=%s' % (sha or hashlib.sha256(M17.read_bytes()).hexdigest())


def fake_git(msg=None, head=True, origin=True, freeze_before=True, diff_clean=True, peel=None, later='',
             remote_ok=True, ps='/v/bin/python experiments/v2_browser/req017_screen.py --lead-release x'):
    msg = msg if msg is not None else 'lead: release REQ-017 pilot\n\n%s\n' % token()

    def run(cmd, env=None, timeout=60):
        if cmd[:2] == ['ps', '-ww']:
            return 0, ps + '\n', ''
        assert cmd[:2] == ['git', '--no-replace-objects'], cmd       # replace objects are always ignored
        a = cmd[4:]
        if a[:3] == ['rev-parse', '--verify', '--quiet']:
            return 0, (peel if peel is not None else SHA) + '\n', ''
        if a[:3] == ['log', '-1', '--format=%B']:
            return 0, msg, ''
        if a[:3] == ['log', '-1', '--format=%H']:
            return 0, FREEZE + '\n', ''
        if a[:2] == ['log', '--format=%s%n%B%x00']:
            return 0, later, ''
        if a[:1] == ['ls-remote']:
            return (0, REMOTE + '\trefs/heads/main\n', '') if remote_ok else (2, '', 'offline')
        if a[:2] == ['cat-file', '-e']:
            return 0, '', ''
        if a[:2] == ['merge-base', '--is-ancestor']:
            y = a[3]
            if y == 'HEAD':
                return (0 if head else 1), '', ''
            if y == REMOTE:
                return (0 if origin else 1), '', ''
            return (0 if freeze_before else 1), '', ''
        if a[:2] == ['diff', '--quiet']:
            return (0 if diff_clean else 1), '', ''
        return 1, '', 'unexpected %s' % a
    return run


def test_release_gate_accepts_only_an_explicit_token_for_this_manifest():
    ok, d = R17.release_problems(ROOT, SHA, run=fake_git())
    assert ok == [] and d['manifest_sha256'] == hashlib.sha256(M17.read_bytes()).hexdigest() and d['remote_main'] == REMOTE
    assert R17.release_problems(ROOT, SHA, run=fake_git(msg='Lead: go\n\n%s\n' % token()))[0] == []
    fenced = 'lead: plan\n\nThe release line will read:\n```\n%s\n```\n' % token()
    for bad, needle in (
            (dict(msg='lead: review REQ-017 source; do not run until released\n'), 'no single unquoted message line'),
            (dict(msg=fenced), 'no single unquoted message line'),
            (dict(msg='lead: x\n%s\n' % token('0' * 64)), 'no single unquoted message line'),
            (dict(msg='lead: x\n%s\n%s\n' % (token(), token())), 'no single unquoted message line'),
            (dict(msg='worker: go\n\n%s\n' % token()), 'not a lead commit'),
            (dict(head=False), 'not an ancestor of HEAD'), (dict(origin=False), 'not an ancestor of the remote main'),
            (dict(remote_ok=False), 'remote main could not be read'),
            (dict(freeze_before=False), 'does not descend from the manifest freeze'),
            (dict(diff_clean=False), 'source changed'),
            (dict(peel='b' * 40), 'not a commit object'),                      # e.g. an annotated tag
            (dict(later='lead: pause\n\nHOLD DTR-REQ-017 pending review\n\x00'), 'revokes or holds'),
            (dict(later='lead: stop\n\nREVOKE DTR-REQ-017\n\x00'), 'revokes or holds')):
        problems, _ = R17.release_problems(ROOT, SHA, run=fake_git(**bad))
        assert problems and any(needle in p for p in problems), (bad, problems)
    assert R17.release_problems(ROOT, SHA, run=fake_git(later='worker: note\n\nREVOKE DTR-REQ-017\n\x00'))[0] == []
    for arg in (None, 'HEAD', 'origin/main~1', 'c648a84', 'A' * 40, '--all', SHA + '\n', ' ' + SHA):
        assert 'full 40-hex' in R17.release_problems(ROOT, arg, run=fake_git())[0][0]


def test_the_lead_hold_commit_c648a84_is_refused_in_the_real_repository():
    full = R17.S.sh(['git', '-C', str(ROOT), 'rev-parse', 'c648a84^{commit}'])[1].strip()
    assert len(full) == 40
    problems, _ = R17.release_problems(ROOT, full, remote=False)
    assert any('no single unquoted message line' in p for p in problems)


@pytest.mark.parametrize('argv', [['--watchdog', ''], ['--watch', 'x'], ['--lead', SHA], ['--lead-release=' + SHA, '--x'],
                                  ['--admission-only', '--lead-release', SHA], ['extra'], ['--watchdog', '/nonexistent']])
def test_parent_arguments_are_parsed_strictly(argv):
    with pytest.raises(SystemExit):
        R17.parse_args(argv)


@pytest.mark.parametrize('argv', [['--run=cfg.json'], ['--ru', 'cfg.json'], ['--r', 'cfg.json'],
                                  ['--run', 'a.json', '--run', 'b.json'], ['--admission', 'a', '--run', 'b'], []])
def test_child_arguments_are_parsed_strictly(argv):
    with pytest.raises(SystemExit):
        E17.parse_args(argv)


def test_child_guard_requires_the_release_and_the_direct_parent_for_pilot_seeds_or_port():
    stub = dict(seeds=[1000, 1001], endpoint='http://127.0.0.1:18292/v1/chat/completions')
    assert E17.guard_problems(stub, root=ROOT, run=fake_git()) == []
    pilot = dict(seeds=[300], endpoint='http://127.0.0.1:18292/v1/chat/completions', parent_pid=4242)
    assert 'full 40-hex' in E17.guard_problems(pilot, root=ROOT, run=fake_git(), getppid=lambda: 4242)[0]
    port = dict(seeds=[1000], endpoint='http://127.0.0.1:8291/v1/chat/completions', lead_release=SHA, parent_pid=4242)
    assert E17.guard_problems(port, root=ROOT, run=fake_git(), getppid=lambda: 4242) == []
    assert 'live req017_screen.py parent' in E17.guard_problems(port, root=ROOT, run=fake_git(), getppid=lambda: 1)[0]
    decoy = fake_git(ps='/bin/sh -c sleep 8; true req017_screen.py')
    assert 'live req017_screen.py parent' in E17.guard_problems(port, root=ROOT, run=decoy, getppid=lambda: 4242)[0]
    assert (R17.PILOT_SEEDS, R17.PILOT_PORT) == (300, 301, 302, 303) or R17.PILOT_SEEDS == (300, 301, 302, 303)


def test_child_main_refuses_a_pilot_config_without_a_release(tmp_path, capsys):
    cfg = tmp_path / 'cfg.json'
    cfg.write_text(json.dumps(dict(seeds=[300], endpoint='http://127.0.0.1:18292/v1/chat/completions')))
    assert E17.main(['--run', str(cfg)]) == 3
    assert 'child refused' in capsys.readouterr().err and not (tmp_path / 'cfg.json.guarded').exists()


def tmp_root(tmp_path):
    (tmp_path / 'configs').mkdir()
    for m in (M17, M16):
        shutil.copy(m, tmp_path / 'configs' / m.name)
    return tmp_path


def probes():
    return OrderedDict((k, (lambda root: (True, {'probe': 'fake'}))) for k in (
        'manifest', 'sources', 'browser', 'models', 'conflicts', 'memory', 'disk'))


def test_no_release_refuses_before_the_namespace_and_restores_req016(tmp_path):
    root = tmp_root(tmp_path)
    assert R17.main([], root=root, probes=probes()) == 3
    assert R17.main(['--lead-release', 'c648a84'], root=root, probes=probes()) == 3
    assert R17.main(['--lead-release', SHA], root=root, probes=probes(), run=fake_git(head=False), remote=True) == 3
    m = json.loads(M17.read_text())
    assert not (root / m['outputs']['raw']).exists() and not (root / m['outputs']['published']).exists()
    assert R.MANIFEST_REL == 'configs/v2_req016_7b_browser_screen_20260925.json' and R.REQUEST == 'DTR-REQ-016'


def test_released_launch_path_scores_four_seeds_and_records_the_release(tmp_path, capsys):
    root = tmp_root(tmp_path)
    m = json.loads(M17.read_text())

    def runner(ctx):
        (ctx['raw'] / 'batch_summary.json').write_text(json.dumps({'stop': None, 'episodes': [
            dict(seed=s, cause='logical_budget_exhausted', full_success=False, executed_actions=1) for s in m['seeds']]}))
        ctx['summary']['status'] = 'COMPLETED'
    assert R17.main(['--lead-release', SHA], root=root, probes=probes(), runner=runner, run=fake_git()) == 0
    s = json.loads((root / m['outputs']['published'] / 'screen_summary.json').read_text())
    assert (s['request'], s['score']['denominator'], s['score']['episodes_with_executed_action']) == ('DTR-REQ-017', 4, 4)
    assert s['lead_release']['commit'] == SHA and s['seeds'] == [300, 301, 302, 303]
    adm = json.loads((root / m['outputs']['published'] / 'admission.json').read_text())
    assert adm['lead_release']['ok'] is True and adm['lead_release']['detail']['commit'] == SHA
    out = capsys.readouterr().out.strip().splitlines()[-1]
    assert json.loads(out)['denominator'] == 4 and json.loads(out)['request'] == 'DTR-REQ-017' 
    assert (root / m['outputs']['published'] / 'manifest.json').read_bytes() == M17.read_bytes()
    assert R.MANIFEST_REL.endswith('req016_7b_browser_screen_20260925.json') and R.score is not R17.score


def test_a_manifest_changed_after_the_gate_is_blocked_before_serving(tmp_path):
    root = tmp_root(tmp_path)
    m = json.loads(M17.read_text())
    called = []
    real = R17.manifest_sha
    R17.manifest_sha = lambda root=ROOT: '0' * 64                     # the gate saw different bytes than the run loads
    try:
        rc = R17.main(['--lead-release', SHA], root=root, probes=probes(), runner=lambda ctx: called.append(1),
                      run=fake_git(msg='lead: go\n\n%s\n' % token('0' * 64)))
    finally:
        R17.manifest_sha = real
    s = json.loads((root / m['outputs']['published'] / 'screen_summary.json').read_text())
    assert rc == 0 and called == [] and s['status'] == 'BLOCKED' and 'not the released manifest' in s['error']


def test_a_second_launch_does_not_print_the_earlier_summary(tmp_path, capsys):
    root = tmp_root(tmp_path)

    def runner(ctx):
        ctx['summary']['status'] = 'COMPLETED'
    assert R17.main(['--lead-release', SHA], root=root, probes=probes(), runner=runner, run=fake_git()) == 0
    first = capsys.readouterr().out
    assert json.loads(first.strip().splitlines()[-1])['denominator'] == 4
    assert R17.main(['--lead-release', SHA], root=root, probes=probes(), runner=runner, run=fake_git()) == 3
    assert 'DTR-REQ-017' not in capsys.readouterr().out
