"""DTR-REQ-007 tree-fit diagnostic: checks against hand-computed cases, not against re-implementations."""
import importlib.util
import itertools
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    'req007', ROOT / 'experiments/v2_agent/analysis/req007_e2dev_tree_fit.py')
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)


def truth_tables(trees, feats):
    points = [dict(zip(feats, bits)) for bits in itertools.product((0, 1), repeat=len(feats))]
    return {tuple(M.apply_tree(t, p) for p in points) for t in trees}


def test_tree_class_expressiveness():
    # depth <= 2 over two binary features represents every one of the 16 Boolean functions
    assert len(truth_tables(M.enumerate_trees(('a', 'b'), 2), ('a', 'b'))) == 16
    # depth <= 1: two constants plus a, not a, b, not b
    assert len(truth_tables(M.enumerate_trees(('a', 'b'), 1), ('a', 'b'))) == 6
    assert len(truth_tables(M.enumerate_trees(('a', 'b', 'c'), 1), ('a', 'b', 'c'))) == 8
    assert len(truth_tables(M.enumerate_trees(('a', 'b'), 0), ('a', 'b'))) == 2
    # no feature is split twice on one path
    for t in M.enumerate_trees(('a', 'b', 'c'), 2):
        if t[0] == 'split':
            for sub in (t[2], t[3]):
                assert sub[0] == 'leaf' or sub[1] != t[1]


def test_tree_helpers_by_hand():
    t = ('split', 'exc_last', ('leaf', 0), ('split', 'x_humaneval', ('leaf', 1), ('leaf', 0)))
    assert M.canon(t) == '[exc_last: 0->S, 1->[x_humaneval: 0->L, 1->S]]'
    assert M.n_leaves(t) == 3 and M.tree_depth(t) == 2
    assert M.apply_tree(t, dict(exc_last=1, x_humaneval=0)) == 1
    assert M.apply_tree(t, dict(exc_last=0, x_humaneval=0)) == 0


def test_snipw_hand_computed():
    rows = [dict(task='A', u=1.0), dict(task='A', u=0.0), dict(task='B', u=1.0)]
    s = M.snipw(rows, [2, 4, 2], lambda r: r['u'])
    # V = (2 + 0 + 2) / 8 = 0.5; psi_A = 2 - 0.5 * 6 = -1, psi_B = 2 - 0.5 * 2 = 1
    # SE = sqrt(2/1 * (1 + 1)) / 8 = 0.25
    assert s['value'] == pytest.approx(0.5)
    assert s['se'] == pytest.approx(0.25)


def row(task, n, u100, t1=None, t2=None, large=0, small=1, success=0):
    decs = {}
    if t1 is not None:
        decs[1] = (t1[0], t1[1], (1,))
    if t2 is not None:
        decs[2] = (t2[0], t2[1], (2,))
    return dict(episode_id=task, task=task, n=n, u100=u100, success=success, large=large, small=small,
                completion_tokens=0, prompt_tokens=0, llm_wall_seconds=0.0, decs=decs)


F0 = dict(x_humaneval=0, zero_visible_checks=0, allfail_last=0, exc_last=0)
F1 = dict(F0, exc_last=1)


def toy_rows():
    # exception history: large repairs, small does not; assertion history: small repairs, large does not
    return [row('e1', 2, 96, t1=(F1, 1), large=1, small=1, success=1),
            row('e2', 2, -2, t1=(F1, 0), large=0, small=2),
            row('e3', 2, 98, t1=(F0, 0), large=0, small=2, success=1),
            row('e4', 2, -4, t1=(F0, 1), large=1, small=1)]


def test_weights_by_hand():
    rows = toy_rows() + [row('e5', 1, 99, success=1)]
    tree = ('split', 'exc_last', ('leaf', 0), ('leaf', 1))
    # e1, e3 follow the tree (2 x 2); e2, e4 do not (0); e5 stopped after a0 (2)
    assert M.weights(rows, tree, ('leaf', 0)) == [4, 0, 4, 0, 2]


def test_search_finds_hand_optimum():
    rows = toy_rows()
    ha = M.Searcher(rows, M.enumerate_trees(M.HIST_T1, 2), M.enumerate_trees(M.HIST_T2, 2))
    b = ha.best(2)
    assert M.canon(b['t1']) == '[exc_last: 0->S, 1->L]'   # the 2-leaf tree wins every exact tie
    assert b['value'] == pytest.approx((96 + 98) / 2 / 100)
    po = M.Searcher(rows, M.enumerate_trees(M.PROMPT, 2), M.enumerate_trees(M.PROMPT, 2))
    p = po.best(2)
    # prompt features are constant here, so the best is constant small: (-2 + 98) / 2 = 48 hundredths
    assert M.canon(p['t1']) == 'S' and p['value'] == pytest.approx(0.48)
    assert ha.best(0)['value'] == pytest.approx(0.48)


def test_one_se_rule_by_hand():
    chosen, best_d, thr = M.one_se_choice({0: (0.50, 0.10), 1: (0.55, 0.02), 2: (0.56, 0.03)})
    assert (chosen, best_d) == (1, 2) and thr == pytest.approx(0.53)
    chosen, best_d, _ = M.one_se_choice({0: (0.50, 0.10), 1: (0.58, 0.01), 2: (0.58, 0.05)})
    assert (chosen, best_d) == (1, 1)


def test_confirm_lines_never_parsed(tmp_path):
    p = tmp_path / 'log.jsonl'
    p.write_text('{"episode_id": "log:mbpp/1#0", "x": 1}\n'
                 '{"episode_id": "log:mbpp/2#0", THIS IS NOT JSON\n'
                 '\n'
                 '{"episode_id": "log:humaneval/3#5", "x": 2}\n')
    kept, pre = M.read_train_lines(p, train={'mbpp/1', 'humaneval/3'}, confirm={'mbpp/2'})
    assert [k['x'] for k in kept] == [1, 2]
    assert pre == dict(nonblank_lines=3, confirm_task_lines_discarded_unparsed=1, lines_parsed=2)
    with pytest.raises(ValueError):
        M.read_train_lines(p, train={'mbpp/1'}, confirm={'mbpp/2'})


def test_split_sizes_match_frozen_text():
    train = {'mbpp/%d' % i for i in range(168)} | {'humaneval/%d' % i for i in range(63)}
    fit, val = M.split_tasks(train)
    assert sum(t.startswith('mbpp/') for t in fit) == 112 and sum(t.startswith('mbpp/') for t in val) == 56
    assert sum(t.startswith('humaneval/') for t in fit) == 42 and sum(t.startswith('humaneval/') for t in val) == 21
    assert not set(fit) & set(val) and set(fit) | set(val) == train
    assert M.split_tasks(train) == (fit, val)


def test_committed_record_is_internally_consistent():
    p = ROOT / 'results/code_routing/analysis/req007/e2dev_tree_fit.json'
    if not p.exists():
        pytest.skip('REQ-007 record not yet written')
    rec = json.loads(p.read_text())
    assert rec['split']['sizes'] == {'mbpp': {'fit': 112, 'validation': 56},
                                     'humaneval': {'fit': 42, 'validation': 21}}
    files = rec['provenance']['confirm_exclusion']['files']
    assert all(v['nonblank_lines'] == v['confirm_task_lines_discarded_unparsed'] + v['lines_parsed']
               for v in files.values())
    assert rec['checks']['assignment_probabilities_verified'] == rec['checks']['train_decisions'] == 2401
    for s in rec['realized_disagreement_final_routers']['summary'].values():
        assert s['disagree_decisions'] == s['t1_disagree'] + s['t2_disagree']
