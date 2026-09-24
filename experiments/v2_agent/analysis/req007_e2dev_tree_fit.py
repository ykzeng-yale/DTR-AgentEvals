"""DTR-REQ-007 (lead 3911aee): execute the frozen REQ006-E2DEV-TREE-v0 specification (section 5(c) of
results/code_routing/analysis/req006/REQ006_SUMMARY_v2.md, commit 88b3e6b) on TRAIN only.

Retrospective DEVELOPMENT-only feasibility diagnostic. It asks one question: under a matched initial small action and
the frozen utility (success - 0.03 x large calls - 0.01 x small calls), does a depth-at-most-two history-aware tree
trained on TRAIN choose a different supported action from a same-class prompt-only tree? It is not an efficacy or
confirmatory test, predicts no counterfactual success, and selects no endpoint.

Inputs (read only): results/code_routing/design.json and results/code_routing/log/{episodes,decisions}.jsonl.
Every log line whose raw leading episode_id names a CONFIRM task is discarded BEFORE JSON parsing. Nothing under
results/code_routing/live/, branch/ or pilot/ is opened. No model call, server, GPU, network or Monte Carlo.

Implementation choices where the frozen text is silent (stated here, before the first run):
  * class of depth d = all trees of depth AT MOST d (nested classes); a feature is not split twice on one path
    (such a split has an unreachable branch and equals a smaller tree, which the fewer-leaves tie-break prefers anyway)
  * a candidate pair uses the same depth bound d at both stages
  * values are compared exactly (integer numerators in hundredths of utility, integer IPW weights), so ties are exact
  * task-clustered SE of the self-normalized value V = sum_i N_i / sum_i D_i (i = task):
    SE^2 = n/(n-1) * sum_i (N_i - V D_i)^2 / (sum_i D_i)^2  (linearization with the CR1 small-sample factor)
  * one-SE rule: best = highest validation value (smallest d among exact ties); choose the smallest d whose validation
    value >= best - SE(best)
  * TRAIN task ids are sorted as strings before the seeded permutation
Usage: req007_e2dev_tree_fit.py [--out DIR]   (writes e2dev_tree_fit.json and REQ007_SUMMARY.md, write-once)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import re
import time
from collections import Counter, OrderedDict, defaultdict
from fractions import Fraction
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
CR = 'results/code_routing'
OUT_DEFAULT = CR + '/analysis/req007'
SPEC = 'REQ006-E2DEV-TREE-v0'
SPEC_SOURCE = 'results/code_routing/analysis/req006/REQ006_SUMMARY_v2.md section 5(c), commit 88b3e6b'
SEED = 20260923
DEPTHS = (0, 1, 2)
CPU_CAP_SECONDS = 900
LINE_RE = re.compile(r'\{"episode_id": "log:(?P<task>[^#"]+)#\d+"')

PROMPT = ('x_humaneval', 'zero_visible_checks')
HIST_T1 = PROMPT + ('exc_last', 'allfail_last')
HIST_T2 = HIST_T1 + ('prev_large',)
CLASSES = OrderedDict(prompt_only={1: PROMPT, 2: PROMPT}, history_aware={1: HIST_T1, 2: HIST_T2})
ACT = {0: 'S', 1: 'L'}


# ------------------------------------------------------------------ loading (CONFIRM lines never parsed)
def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read_train_lines(path: Path, train: set, confirm: set):
    """Parse only TRAIN-task lines. A CONFIRM-task line is identified from its raw leading episode_id and skipped
    unparsed. Any other task id is an error."""
    kept, n_lines, n_conf = [], 0, 0
    with open(path) as fh:
        for raw in fh:
            if not raw.strip():
                continue
            n_lines += 1
            m = LINE_RE.match(raw)
            if m is None:
                raise ValueError('unrecognized log line prefix in %s: %r' % (path.name, raw[:60]))
            task = m.group('task')
            if task in confirm:
                n_conf += 1
                continue
            if task not in train:
                raise ValueError('log line for a task outside TRAIN and CONFIRM: %s' % task)
            kept.append(json.loads(raw))
    return kept, OrderedDict(nonblank_lines=n_lines, confirm_task_lines_discarded_unparsed=n_conf, lines_parsed=len(kept))


def split_tasks(train: set, seed: int = SEED):
    """Frozen split: within each benchmark sort the ids, permute with ONE default_rng(seed) generator (mbpp first,
    then humaneval), first round(2/3 n) to FIT."""
    rng = np.random.default_rng(seed)
    fit, val = [], []
    for fam in ('mbpp', 'humaneval'):
        ids = sorted(t for t in train if t.split('/')[0] == fam)
        perm = [ids[i] for i in rng.permutation(len(ids))]
        k = int(round(2 * len(ids) / 3))
        fit += perm[:k]
        val += perm[k:]
    return fit, val


# ------------------------------------------------------------------ features and trees
def features(ep: dict, dec: dict) -> dict:
    s = dec['state']
    f = dict(x_humaneval=int(ep['benchmark'] == 'humaneval'), zero_visible_checks=int(ep['n_visible_checks'] == 0),
             exc_last=int(s['fail_class'] == 'exception'), allfail_last=int(s['frac_fail'] == 1.0))
    if dec['t'] == 2:
        f['prev_large'] = int(s['prev_actions'][-1] == 1)
    return f


def history_key(ep: dict, dec: dict) -> tuple:
    """U_A key of REQ-006: (t, family, zero_visible_checks, fail_class, frac_bin, prev_actions)."""
    s = dec['state']
    return (dec['t'], ep['benchmark'], int(ep['n_visible_checks'] == 0), s['fail_class'],
            'all_checks_failed' if s['frac_fail'] == 1.0 else 'partial', tuple(s['prev_actions']))


def enumerate_trees(feats, depth, used=()):
    out = [('leaf', 0), ('leaf', 1)]
    if depth == 0:
        return out
    for f in feats:
        if f in used:
            continue
        subs = enumerate_trees(feats, depth - 1, used + (f,))
        out += [('split', f, lo, hi) for lo in subs for hi in subs]
    return out


def apply_tree(tree, fd: dict) -> int:
    while tree[0] == 'split':
        tree = tree[3] if fd[tree[1]] else tree[2]
    return tree[1]


def n_leaves(tree) -> int:
    return 1 if tree[0] == 'leaf' else n_leaves(tree[2]) + n_leaves(tree[3])


def tree_depth(tree) -> int:
    return 0 if tree[0] == 'leaf' else 1 + max(tree_depth(tree[2]), tree_depth(tree[3]))


def canon(tree) -> str:
    if tree[0] == 'leaf':
        return ACT[tree[1]]
    return '[%s: 0->%s, 1->%s]' % (tree[1], canon(tree[2]), canon(tree[3]))


def leaf_paths(tree, path=()):
    if tree[0] == 'leaf':
        return [(path, tree[1])]
    return leaf_paths(tree[2], path + ((tree[1], 0),)) + leaf_paths(tree[3], path + ((tree[1], 1),))


# ------------------------------------------------------------------ episode table (a0 = small only)
def build_episodes(eps: list) -> list:
    """Episodes with a0 = small, the only ones with nonzero target weight. Utility is held in integer hundredths."""
    rows = []
    for e in eps:
        if e['decisions'][0]['action'] != 'small':
            continue
        nL, nS = e['actions'].count('large'), e['actions'].count('small')
        u100 = 100 * e['success'] - 3 * nL - 1 * nS
        assert abs(u100 / 100 - e['utility']) < 1e-9, e['episode_id']
        decs = {d['t']: (features(e, d), d['a'], history_key(e, d)) for d in e['decisions'] if d['t'] >= 1}
        rows.append(dict(episode_id=e['episode_id'], task=e['task_uid'], n=len(e['decisions']), u100=u100,
                         success=e['success'], large=nL, small=nS, completion_tokens=e['completion_tokens'],
                         prompt_tokens=sum(d['prompt_tokens'] for d in e['decisions']),
                         llm_wall_seconds=e['llm_wall_seconds'], decs=decs))
    return rows


def weights(rows: list, t1, t2) -> list:
    """W_e = prod_t 1{A_et = pi_t(H_et)} / b_et with every b_et = 0.5 (verified), a0 = small matched."""
    out = []
    for r in rows:
        w = 2
        for t, tree in ((1, t1), (2, t2)):
            if t in r['decs']:
                fd, a, _ = r['decs'][t]
                w = w * 2 if apply_tree(tree, fd) == a else 0
        out.append(w)
    return out


def snipw(rows: list, w: list, q) -> dict:
    """Self-normalized IPW mean of q with task-clustered linearized SE (CR1)."""
    N, D = defaultdict(float), defaultdict(float)
    for r, wi in zip(rows, w):
        N[r['task']] += wi * q(r)
        D[r['task']] += wi
    tasks = sorted(D)
    sD = sum(D.values())
    v = sum(N.values()) / sD
    n = len(tasks)
    psi = [N[t] - v * D[t] for t in tasks]
    se = math.sqrt(n / (n - 1) * sum(p * p for p in psi)) / sD if n > 1 else float('nan')
    return dict(value=v, se=se, n_tasks=n, psi={t: p / sD for t, p in zip(tasks, psi)})


# ------------------------------------------------------------------ exhaustive joint search
class Searcher:
    """Exact joint search over (tree_t1, tree_t2) pairs for one router class on one task set."""

    def __init__(self, rows: list, trees1: list, trees2: list):
        self.trees1, self.trees2 = trees1, trees2
        r1 = [r for r in rows if r['n'] == 1]
        r2 = [r for r in rows if r['n'] == 2]
        r3 = [r for r in rows if r['n'] == 3]
        m12 = np.array([[int(apply_tree(tr, r['decs'][1][0]) == r['decs'][1][1]) for r in r2] for tr in trees1],
                       dtype=np.int64).reshape(len(trees1), len(r2))
        m13 = np.array([[int(apply_tree(tr, r['decs'][1][0]) == r['decs'][1][1]) for r in r3] for tr in trees1],
                       dtype=np.int64).reshape(len(trees1), len(r3))
        m23 = np.array([[int(apply_tree(tr, r['decs'][2][0]) == r['decs'][2][1]) for r in r3] for tr in trees2],
                       dtype=np.int64).reshape(len(trees2), len(r3))

        def num(q):
            q1 = sum(2 * q(r) for r in r1)
            q2 = m12 @ np.array([4 * q(r) for r in r2], dtype=np.int64)
            q3 = (m13 * np.array([8 * q(r) for r in r3], dtype=np.int64)) @ m23.T
            return q1 + q2[:, None] + q3

        self.N = num(lambda r: r['u100'])          # hundredths of utility
        self.D = num(lambda r: 1)
        self.L = num(lambda r: r['large'])
        self.leaves = np.array([n_leaves(t) for t in trees1])[:, None] + np.array([n_leaves(t) for t in trees2])[None, :]
        self.depth1 = np.array([tree_depth(t) for t in trees1])
        self.depth2 = np.array([tree_depth(t) for t in trees2])

    def best(self, d: int) -> dict:
        ok = (self.depth1[:, None] <= d) & (self.depth2[None, :] <= d)
        n_cand = int(ok.sum())
        zero_den = int(((self.D == 0) & ok).sum())
        v = np.where(ok & (self.D > 0), self.N / np.maximum(self.D, 1), -np.inf)
        vmax = v.max()
        # distinct rationals with denominators <= 8 x 924 differ by > 1e-8, so this window holds exact ties only
        idx = np.argwhere(v >= vmax - 1e-9)
        cands = []
        for i, j in idx:
            val = Fraction(int(self.N[i, j]), int(self.D[i, j]))
            cands.append((val, i, j))
        top = max(c[0] for c in cands)
        tied = [(i, j) for val, i, j in cands if val == top]

        def key(ij):
            i, j = ij
            return (int(self.leaves[i, j]), Fraction(int(self.L[i, j]), int(self.D[i, j])),
                    canon(self.trees1[i]) + ' | ' + canon(self.trees2[j]))
        tied.sort(key=key)
        i, j = tied[0]
        return dict(t1=self.trees1[i], t2=self.trees2[j], value=float(top) / 100, n_candidates=n_cand,
                    zero_denominator_candidates=zero_den, n_exact_ties=len(tied),
                    tie_break_applied=('none' if len(tied) == 1 else 'fewer leaves / lower large-call rate / lexicographic'),
                    ties_by_leaves=dict(Counter(int(self.leaves[a, b]) for a, b in tied)))


def one_se_choice(val_by_d: dict) -> tuple:
    """val_by_d: d -> (value, se). Returns (chosen d, best d, threshold)."""
    best_v = max(v for v, _ in val_by_d.values())
    best_d = min(d for d, (v, _) in val_by_d.items() if v == best_v)
    thr = best_v - val_by_d[best_d][1]
    chosen = min(d for d, (v, _) in val_by_d.items() if v >= thr)
    return chosen, best_d, thr


# ------------------------------------------------------------------ reporting helpers
COMPONENTS = OrderedDict(
    utility=lambda r: r['u100'] / 100, success=lambda r: r['success'], large_calls=lambda r: r['large'],
    small_calls=lambda r: r['small'], completion_tokens=lambda r: r['completion_tokens'],
    prompt_tokens=lambda r: r['prompt_tokens'], llm_wall_seconds=lambda r: r['llm_wall_seconds'])


def evaluate(rows: list, t1, t2) -> dict:
    w = weights(rows, t1, t2)
    comp = OrderedDict()
    for k, q in COMPONENTS.items():
        s = snipw(rows, w, q)
        comp[k] = OrderedDict(value=round(s['value'], 6), task_clustered_se=round(s['se'], 6))
    tw = defaultdict(int)
    for r, wi in zip(rows, w):
        tw[r['task']] += wi
    sw, sw2 = sum(w), sum(x * x for x in w)
    return OrderedDict(
        components_self_normalized_ipw=comp,
        weights=OrderedDict(episodes_in_set=len(rows), episodes_with_nonzero_weight=sum(x > 0 for x in w),
                            weight_values=dict(Counter(w)), sum_weights=sw,
                            kish_effective_episodes=round(sw * sw / sw2, 2),
                            tasks_in_set=len(tw), tasks_with_nonzero_weight=sum(v > 0 for v in tw.values()),
                            kish_effective_tasks=round(sum(tw.values()) ** 2 / sum(v * v for v in tw.values()), 2)))


def router_desc(t1, t2) -> OrderedDict:
    return OrderedDict(a0='S', tree_t1=canon(t1), tree_t2=canon(t2), depth_t1=tree_depth(t1), depth_t2=tree_depth(t2),
                       leaves=n_leaves(t1) + n_leaves(t2),
                       structurally_fixed_schedule=(t1[0] == 'leaf' and t2[0] == 'leaf'))


def leaf_support(rows: list, tree, t: int) -> list:
    out = []
    for path, act in leaf_paths(tree):
        n = sum(1 for r in rows if t in r['decs'] and all(r['decs'][t][0][f] == v for f, v in path))
        out.append(OrderedDict(stage=t, path=' & '.join('%s=%d' % pv for pv in path) or '(root)', action=ACT[act],
                               supporting_decisions=n, unsupported_default=(n == 0)))
    return out


def disagreement(rows: list, rp: tuple, rh: tuple) -> OrderedDict:
    """Realized action disagreement of two routers at observed supported a0=S TRAIN histories.
    all_observed: every logged t=1/t=2 decision (the U_A cells of REQ-006).
    reachable_by_both: t=1 decisions, plus t=2 decisions whose logged a1 equals BOTH routers' t=1 action."""
    cells = OrderedDict()
    tot = dict(all_observed=Counter(), reachable_by_both=Counter())
    tasks = dict(all_observed=defaultdict(set), reachable_by_both=defaultdict(set))
    behav = {'prompt_only': defaultdict(set), 'history_aware': defaultdict(set)}
    for r in rows:
        for t in (1, 2):
            if t not in r['decs']:
                continue
            fd, a, key = r['decs'][t]
            ap, ah = apply_tree(rp[t - 1], fd), apply_tree(rh[t - 1], fd)
            reach = t == 1 or (apply_tree(rp[0], r['decs'][1][0]) == r['decs'][1][1] ==
                               apply_tree(rh[0], r['decs'][1][0]))
            c = cells.setdefault(key, OrderedDict(t=key[0], family=key[1], zero_visible_checks=key[2], fail_class=key[3],
                                                  frac_bin=key[4], prev_actions=''.join(ACT[x] for x in key[5]),
                                                  prompt_only=ACT[ap], history_aware=ACT[ah], decisions=0,
                                                  tasks=set(), reachable_by_both=0))
            c['decisions'] += 1
            c['tasks'].add(r['task'])
            c['reachable_by_both'] += int(reach)
            for scope, inc in (('all_observed', True), ('reachable_by_both', reach)):
                if not inc:
                    continue
                tot[scope]['t%d_decisions' % t] += 1
                if ap != ah:
                    tot[scope]['t%d_disagree' % t] += 1
                    tasks[scope]['t%d' % t].add(r['task'])
                    tasks[scope]['any'].add(r['task'])
            if reach:
                behav['prompt_only'][t].add(ap)
                behav['history_aware'][t].add(ah)
    table = []
    for c in cells.values():
        c['tasks'] = len(c['tasks'])
        c['disagree'] = c['prompt_only'] != c['history_aware']
        table.append(c)
    table.sort(key=lambda c: (c['t'], c['family'], c['zero_visible_checks'], c['fail_class'], c['frac_bin'], c['prev_actions']))
    summ = OrderedDict()
    for scope in ('all_observed', 'reachable_by_both'):
        s = tot[scope]
        summ[scope] = OrderedDict(
            t1_decisions=s['t1_decisions'], t1_disagree=s['t1_disagree'], t2_decisions=s['t2_decisions'],
            t2_disagree=s['t2_disagree'], disagree_decisions=s['t1_disagree'] + s['t2_disagree'],
            distinct_tasks_with_disagreement=len(tasks[scope]['any']),
            distinct_tasks_t1=len(tasks[scope]['t1']), distinct_tasks_t2=len(tasks[scope]['t2']))
    fixed = OrderedDict((k, OrderedDict(('t%d' % t, ''.join(sorted(ACT[a] for a in v[t]))) for t in (1, 2)))
                        for k, v in behav.items())
    return OrderedDict(summary=summ, cells=table,
                       behaviour_on_reachable_histories=fixed,
                       behaviourally_fixed_schedule={k: all(len(v[t]) <= 1 for t in (1, 2)) for k, v in behav.items()})


# ------------------------------------------------------------------ main
def run(out_dir: Path) -> dict:
    t_start = time.process_time()
    design_p = REPO / CR / 'design.json'
    design = json.loads(design_p.read_bytes())
    train, confirm, pilot = set(design['train_tasks']), set(design['confirm_tasks']), set(design['pilot_tasks'])
    assert not (train & confirm) and not (train & pilot) and not (pilot & confirm)
    eps, pre_e = read_train_lines(REPO / CR / 'log/episodes.jsonl', train, confirm)
    decs, pre_d = read_train_lines(REPO / CR / 'log/decisions.jsonl', train, confirm)

    # ---- provenance checks: every TRAIN assignment probability and action, field by field
    checks = Counter()
    ep_ids = Counter(e['episode_id'] for e in eps)
    assert all(v == 1 for v in ep_ids.values()), 'duplicate episode ids'
    per_task = Counter(e['task_uid'] for e in eps)
    checks['tasks'] = len(per_task)
    assert set(per_task) == train and set(per_task.values()) == {8}, 'TRAIN episode counts'
    for t in train:
        a0 = Counter(e['decisions'][0]['action'] for e in eps if e['task_uid'] == t)
        assert a0 == Counter(small=4, large=4), (t, a0)
    by_key = {(d['episode_id'], d['t']): d for d in decs}
    assert len(by_key) == len(decs), 'duplicate (episode, t) decision rows'
    n_ep_decs = 0
    for e in eps:
        assert e['error'] is None and e['n_decisions'] == len(e['decisions'])
        assert e['actions'] == [d['action'] for d in e['decisions']]
        for d in e['decisions']:
            n_ep_decs += 1
            r = by_key[(e['episode_id'], d['t'])]
            for f in ('p_large', 'action', 'a', 'b_obs', 'eligible', 'available_actions', 'state', 'draw', 'source',
                      'transcript_sha256'):
                if r[f] != d[f]:
                    raise SystemExit('decision mismatch %s t=%d field %s' % (e['episode_id'], d['t'], f))
                checks['field_matches'] += 1
            assert d['eligible'] is True and sorted(d['available_actions']) == ['large', 'small']
            assert d['p_large'] == 0.5 and d['b_obs'] == 0.5, (e['episode_id'], d['t'])
            assert d['a'] == int(d['action'] == 'large')
            assert d['state']['x_humaneval'] == int(e['benchmark'] == 'humaneval')
            checks['assignment_probabilities_verified'] += 1
    assert n_ep_decs == len(decs), (n_ep_decs, len(decs))

    rows = build_episodes(eps)
    fit_ids, val_ids = split_tasks(train)
    fit_s, val_s = set(fit_ids), set(val_ids)
    assert not (fit_s & val_s) and fit_s | val_s == train
    sets = OrderedDict(fit=[r for r in rows if r['task'] in fit_s], validation=[r for r in rows if r['task'] in val_s],
                       all_train=rows)

    trees = {cls: {t: enumerate_trees(f[t], 2) for t in (1, 2)} for cls, f in CLASSES.items()}
    searchers = {(cls, part): Searcher(sets[part], trees[cls][1], trees[cls][2])
                 for cls in CLASSES for part in ('fit', 'all_train')}

    classes = OrderedDict()
    final = {}
    fit_selected = {}
    for cls in CLASSES:
        per_d = OrderedDict()
        val_by_d = {}
        for d in DEPTHS:
            b = searchers[(cls, 'fit')].best(d)
            ev_val = evaluate(sets['validation'], b['t1'], b['t2'])
            u = ev_val['components_self_normalized_ipw']['utility']
            val_by_d[d] = (u['value'], u['task_clustered_se'])
            per_d[d] = OrderedDict(fit_router=router_desc(b['t1'], b['t2']), fit_value_utility=round(b['value'], 6),
                                   search=OrderedDict((k, b[k]) for k in ('n_candidates', 'zero_denominator_candidates',
                                                                          'n_exact_ties', 'tie_break_applied',
                                                                          'ties_by_leaves')),
                                   validation=ev_val)
            if time.process_time() - t_start > CPU_CAP_SECONDS:
                raise SystemExit('CPU cap exceeded during %s d=%d' % (cls, d))
        chosen, best_d, thr = one_se_choice(val_by_d)
        fb = searchers[(cls, 'fit')].best(chosen)
        fit_selected[cls] = (fb['t1'], fb['t2'])
        fin = searchers[(cls, 'all_train')].best(chosen)
        final[cls] = (fin['t1'], fin['t2'])
        classes[cls] = OrderedDict(
            features=OrderedDict(t1=list(CLASSES[cls][1]), t2=list(CLASSES[cls][2])),
            trees_enumerated=OrderedDict(t1=len(trees[cls][1]), t2=len(trees[cls][2])),
            by_depth_fit_on_FIT=per_d,
            one_se_rule=OrderedDict(best_validation_depth=best_d, best_validation_value=val_by_d[best_d][0],
                                    best_validation_se=val_by_d[best_d][1], threshold=round(thr, 6),
                                    chosen_depth=chosen),
            final_router_refit_on_all_TRAIN=router_desc(fin['t1'], fin['t2']),
            final_search=OrderedDict((k, fin[k]) for k in ('n_candidates', 'zero_denominator_candidates', 'n_exact_ties',
                                                           'tie_break_applied', 'ties_by_leaves')),
            final_in_sample_all_TRAIN=evaluate(rows, fin['t1'], fin['t2']),
            final_leaf_support=leaf_support(rows, fin['t1'], 1) + leaf_support(rows, fin['t2'], 2))

    # ---- paired validation contrast of the FIT-selected routers at their chosen depths (DEVELOPMENT only)
    vrows = sets['validation']
    wp = weights(vrows, *fit_selected['prompt_only'])
    wh = weights(vrows, *fit_selected['history_aware'])
    sp = snipw(vrows, wp, COMPONENTS['utility'])
    sh = snipw(vrows, wh, COMPONENTS['utility'])
    n = sp['n_tasks']
    diff_se = math.sqrt(n / (n - 1) * sum((sh['psi'][t] - sp['psi'][t]) ** 2 for t in sp['psi']))
    val_contrast = OrderedDict(history_minus_prompt_utility=round(sh['value'] - sp['value'], 6),
                               task_clustered_paired_se=round(diff_se, 6), validation_tasks=n,
                               label='DEVELOPMENT-only; FIT-selected routers at their one-SE depths; not confirmatory, '
                                     'not fresh-policy superiority')

    # ---- realized disagreement at common observed supported TRAIN histories
    dis_final = disagreement(rows, final['prompt_only'], final['history_aware'])
    dis_by_depth = OrderedDict()
    for d in DEPTHS:
        bp = searchers[('prompt_only', 'all_train')].best(d)
        bh = searchers[('history_aware', 'all_train')].best(d)
        dd = disagreement(rows, (bp['t1'], bp['t2']), (bh['t1'], bh['t2']))
        dis_by_depth[d] = OrderedDict(prompt_only=router_desc(bp['t1'], bp['t2']),
                                      history_aware=router_desc(bh['t1'], bh['t2']),
                                      in_sample_value_prompt_only=round(bp['value'], 6),
                                      in_sample_value_history_aware=round(bh['value'], 6),
                                      summary=dd['summary'],
                                      behaviourally_fixed_schedule=dd['behaviourally_fixed_schedule'])

    script = Path(__file__).resolve()
    rec = OrderedDict(
        request='DTR-REQ-007', lead_decision='docs/theory_feedback_20260924_req006_decision.md (3911aee)',
        specification=SPEC, specification_source=SPEC_SOURCE,
        evidence_status=('retrospective DEVELOPMENT-only feasibility diagnostic on archived TRAIN log records; not '
                         'confirmatory, not an effect estimate, no counterfactual CONFIRM prediction, no endpoint change'),
        implementation_choices=__doc__.split('stated here, before the first run):')[1].split('Usage:')[0].strip(),
        provenance=OrderedDict(
            script=str(script.relative_to(REPO)), script_sha256=sha256_file(script),
            inputs=OrderedDict((p, sha256_file(REPO / CR / p)) for p in ('design.json', 'design.sha256',
                                                                           'log/episodes.jsonl', 'log/decisions.jsonl')),
            design_sha256_matches=(sha256_file(design_p) == (REPO / CR / 'design.sha256').read_text().strip()),
            python=platform.python_version(), numpy=np.__version__,
            not_opened=['results/code_routing/live/', 'results/code_routing/branch/', 'results/code_routing/pilot/'],
            confirm_exclusion=OrderedDict(method='task id from the raw leading episode_id; CONFIRM-task lines skipped '
                                                 'before JSON parsing; input files hashed whole for provenance only',
                                          files=OrderedDict([('log/episodes.jsonl', pre_e),
                                                             ('log/decisions.jsonl', pre_d)]))),
        checks=OrderedDict(checks, train_episodes=len(eps), train_decisions=len(decs),
                           a0_small_episodes=len(rows),
                           a0_small_by_n_decisions=dict(sorted(Counter(r['n'] for r in rows).items()))),
        split=OrderedDict(seed=SEED, method='sorted ids per benchmark, one default_rng(seed), mbpp then humaneval, '
                                            'first round(2/3 n) to FIT',
                          sizes=OrderedDict((fam, OrderedDict(fit=sum(t.startswith(fam + '/') for t in fit_ids),
                                                              validation=sum(t.startswith(fam + '/') for t in val_ids)))
                                            for fam in ('mbpp', 'humaneval')),
                          fit_task_ids=fit_ids, validation_task_ids=val_ids,
                          fit_ids_sha256=hashlib.sha256('\n'.join(sorted(fit_ids)).encode()).hexdigest(),
                          validation_ids_sha256=hashlib.sha256('\n'.join(sorted(val_ids)).encode()).hexdigest()),
        classes=classes,
        validation_contrast=val_contrast,
        realized_disagreement_final_routers=dis_final,
        realized_disagreement_all_TRAIN_refit_by_depth=OrderedDict(
            note='descriptive: the best pair of each class refit on all TRAIN at each depth bound; only the one-SE '
                 'depths above are the pre-specified result',
            by_depth=dis_by_depth),
        cpu_seconds=round(time.process_time() - t_start, 2))
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / 'e2dev_tree_fit.json', 'x') as fh:
        fh.write(json.dumps(rec, indent=1, default=str) + '\n')
    with open(out_dir / 'REQ007_SUMMARY.md', 'x') as fh:
        fh.write(summary_md(rec))
    return rec


def summary_md(rec: dict) -> str:
    L = []
    w = L.append
    C = rec['classes']
    fin = rec['realized_disagreement_final_routers']
    w('# DTR-REQ-007: frozen %s fit on TRAIN (retrospective, DEVELOPMENT-only)\n' % rec['specification'])
    w('Generated by `%s` (sha256 `%s`); machine-readable record `e2dev_tree_fit.json`. Written once; do not edit.\n'
      % (rec['provenance']['script'], rec['provenance']['script_sha256']))
    w('**Evidence status.** %s. Specification: %s. Lead request: %s.\n'
      % (rec['evidence_status'][0].upper() + rec['evidence_status'][1:], rec['specification_source'],
         rec['lead_decision']))
    pe = rec['provenance']['confirm_exclusion']['files']
    w('**Inputs.** `design.json` and `log/{episodes,decisions}.jsonl` only. CONFIRM-task lines discarded unparsed: '
      '%s. Not opened: %s. No model call, server, GPU, network or Monte Carlo.\n'
      % ('; '.join('`%s` %d of %d' % (k, v['confirm_task_lines_discarded_unparsed'], v['nonblank_lines'])
                   for k, v in pe.items()), ', '.join('`%s`' % p for p in rec['provenance']['not_opened'])))
    ck = rec['checks']
    w('**Checks.** %d TRAIN tasks x 8 episodes, a0 blocked 4 small / 4 large in every task; %d decisions matched to '
      '`decisions.jsonl` on %d field comparisons; every assignment probability verified (%d eligible decisions, all '
      'p_large = 0.5 with both actions available). E2-relevant (a0 = small) episodes: %d, by number of decisions %s.\n'
      % (ck['tasks'], ck['train_decisions'], ck['field_matches'], ck['assignment_probabilities_verified'],
         ck['a0_small_episodes'], ck['a0_small_by_n_decisions']))
    sp = rec['split']
    w('**Split.** seed %d; %s; FIT/VALIDATION task-id sha256 `%s` / `%s`.\n'
      % (sp['seed'], ', '.join('%s %d/%d' % (k, v['fit'], v['validation']) for k, v in sp['sizes'].items()),
         sp['fit_ids_sha256'][:16], sp['validation_ids_sha256'][:16]))
    w('## Complexity selection (fit on FIT, value on VALIDATION)\n')
    w('| Class | d | FIT-selected router (t1 / t2) | FIT value | VALIDATION utility (SE) | exact ties |')
    w('|---|---:|---|---:|---:|---:|')
    for cls, c in C.items():
        for d, x in c['by_depth_fit_on_FIT'].items():
            u = x['validation']['components_self_normalized_ipw']['utility']
            w('| %s | %s | `%s` / `%s` | %.4f | %.4f (%.4f) | %d |' % (
                cls, d, x['fit_router']['tree_t1'], x['fit_router']['tree_t2'], x['fit_value_utility'], u['value'],
                u['task_clustered_se'], x['search']['n_exact_ties']))
    w('')
    for cls, c in C.items():
        o = c['one_se_rule']
        w('- **%s:** best validation depth %d (%.4f, SE %.4f); threshold %.4f; **chosen depth %d**.'
          % (cls, o['best_validation_depth'], o['best_validation_value'], o['best_validation_se'], o['threshold'],
             o['chosen_depth']))
    w('')
    w('## Final routers (chosen depth, refit on all 231 TRAIN tasks)\n')
    w('| Class | t1 tree | t2 tree | structurally fixed | in-sample utility | success | large calls | small calls | '
      'completion tokens | prompt tokens | LLM wall s | Kish eff. tasks |')
    w('|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|')
    for cls, c in C.items():
        r = c['final_router_refit_on_all_TRAIN']
        e = c['final_in_sample_all_TRAIN']
        k = e['components_self_normalized_ipw']
        w('| %s | `%s` | `%s` | %s | %.4f | %.4f | %.3f | %.3f | %.1f | %.1f | %.2f | %.1f |' % (
            cls, r['tree_t1'], r['tree_t2'], r['structurally_fixed_schedule'], k['utility']['value'],
            k['success']['value'], k['large_calls']['value'], k['small_calls']['value'],
            k['completion_tokens']['value'], k['prompt_tokens']['value'], k['llm_wall_seconds']['value'],
            e['weights']['kish_effective_tasks']))
    w('\nIn-sample values are optimistic (the same TRAIN tasks chose the trees). Resources are kept distinct; the call '
      'penalty is the frozen unitless design value, not dollars.\n')
    uns = [(cls, s) for cls, c in C.items() for s in c['final_leaf_support'] if s['unsupported_default']]
    w('**Unsupported (default) leaves in the final trees:** %s.\n' % (
        '; '.join('%s stage %d %s -> %s' % (cls, s['stage'], s['path'], s['action']) for cls, s in uns) or 'none'))
    vc = rec['validation_contrast']
    chosen = {k: c['by_depth_fit_on_FIT'][c['one_se_rule']['chosen_depth']]['fit_router'] for k, c in C.items()}
    same = chosen['prompt_only'] == chosen['history_aware']
    w('**Validation contrast** (history-aware minus prompt-only utility, FIT-selected routers): %.4f, paired '
      'task-clustered SE %.4f, %d validation tasks%s. %s.\n' % (
          vc['history_minus_prompt_utility'], vc['task_clustered_paired_se'], vc['validation_tasks'],
          ' (the two FIT-selected routers are identical)' if same else '', vc['label']))
    w('## Realized disagreement of the final routers at observed supported TRAIN histories (a0 = small)\n')
    w('| Scope | t1 disagree / decisions | t2 disagree / decisions | distinct tasks with disagreement |')
    w('|---|---:|---:|---:|')
    for scope, s in fin['summary'].items():
        w('| %s | %d / %d | %d / %d | %d |' % (scope, s['t1_disagree'], s['t1_decisions'], s['t2_disagree'],
                                               s['t2_decisions'], s['distinct_tasks_with_disagreement']))
    w('\n`all_observed` = every logged t=1/t=2 decision (the U_A cells of REQ-006); `reachable_by_both` = t=1 decisions '
      'plus t=2 decisions whose logged a1 equals both routers\' t=1 action. Behaviourally fixed schedule on reachable '
      'histories: %s.\n' % fin['behaviourally_fixed_schedule'])
    w('| t | family | zero checks | fail_class | frac_bin | prev | decisions | tasks | prompt-only | history-aware |')
    w('|---:|---|---:|---|---|---|---:|---:|---|---|')
    for c in fin['cells']:
        w('| %d | %s | %d | %s | %s | %s | %d | %d | %s | %s%s |' % (
            c['t'], c['family'], c['zero_visible_checks'], c['fail_class'], c['frac_bin'], c['prev_actions'],
            c['decisions'], c['tasks'], c['prompt_only'], c['history_aware'], ' **(differs)**' if c['disagree'] else ''))
    w('\n## Descriptive: best pair of each class refit on all TRAIN at each depth bound\n')
    w('Only the one-SE depths above are the pre-specified result.\n')
    w('| d | prompt-only (t1 / t2) | history-aware (t1 / t2) | in-sample utility P / H | disagree decisions '
      '(all observed) | tasks |')
    w('|---:|---|---|---|---:|---:|')
    for d, x in rec['realized_disagreement_all_TRAIN_refit_by_depth']['by_depth'].items():
        s = x['summary']['all_observed']
        w('| %s | `%s` / `%s` | `%s` / `%s` | %.4f / %.4f | %d | %d |' % (
            d, x['prompt_only']['tree_t1'], x['prompt_only']['tree_t2'], x['history_aware']['tree_t1'],
            x['history_aware']['tree_t2'], x['in_sample_value_prompt_only'], x['in_sample_value_history_aware'],
            s['disagree_decisions'], s['distinct_tasks_with_disagreement']))
    w('\n## Implementation choices (fixed before the first run)\n')
    items = []
    for line in rec['implementation_choices'].splitlines():
        line = line.strip()
        if line.startswith('*'):
            items.append(line[1:].strip())
        elif items:
            items[-1] += ' ' + line
    w('\n'.join('- ' + x for x in items))
    w('\n## Limitations\n')
    w('- DEVELOPMENT-only and retrospective; the 231 TRAIN tasks both chose and (in-sample) evaluate the final trees. '
      'The validation contrast rests on %d tasks and one FIT/VALIDATION split.' % vc['validation_tasks'])
    w('- A favorable validation value is not fresh-policy superiority, and no endpoint was selected. Visible-pass '
      'stopping absorbs most a0 = small episodes, so neither router can act after those stops.')
    w('- Realized disagreement is counted on logged histories; a t=2 history is reachable by a router only if its t=1 '
      'action equals the logged one, which the `reachable_by_both` scope applies.')
    w('- No CONFIRM, live, branch or pilot record was used; this benchmark has no untouched task for a prospective test.')
    return '\n'.join(L) + '\n'


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, default=REPO / OUT_DEFAULT)
    args = ap.parse_args(argv)
    rec = run(args.out if args.out.is_absolute() else REPO / args.out)
    fin = rec['realized_disagreement_final_routers']['summary']
    print(json.dumps(OrderedDict(
        chosen_depths={k: v['one_se_rule']['chosen_depth'] for k, v in rec['classes'].items()},
        final={k: v['final_router_refit_on_all_TRAIN'] for k, v in rec['classes'].items()},
        disagreement=fin, validation_contrast=rec['validation_contrast'], cpu_seconds=rec['cpu_seconds']), indent=1))


if __name__ == '__main__':
    main()
