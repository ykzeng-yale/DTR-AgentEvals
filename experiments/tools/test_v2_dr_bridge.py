"""Exact (exhaustive, non-Monte-Carlo) checks for experiments/v2_sim/dr_bridge.py and its task folds."""
import sys
from fractions import Fraction as Fr
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import dr_bridge as DB  # noqa: E402
import repair_generator as G  # noqa: E402
import repair_logger as L  # noqa: E402
import sampler as S  # noqa: E402

CELL = G.Cell(2, 'crossing', 'informative')
CAT = {p.name: p for p in G.catalog(2)}
POLS = ['history_large_after_exception', 'prompt_only_large_if_hard', 'fixed_LS', 'fixed_SS']


def branches(cell, s, logger):
    out = []
    for p, rec in S.exhaustive(lambda d: S.run_episode(cell, s, d, 'x', logger=logger)):
        rec = dict(rec, task_id='x', replicate=0)
        out.append((p, rec))
    return out


@pytest.mark.parametrize('lname', ['uniform_floor_0.5', 'feedback_dependent_floor_0.2'])
def test_mapping_weights_and_state_fields(lname):
    for s in (0, 1):
        br = branches(CELL, s, L.LOGGERS[lname])
        recs = [r for _, r in br]
        logs = DB.to_logs(recs, CELL.K)
        z = np.array([float(DB.z_pre(r)) for r in recs]) + logs.r.sum(1)
        assert np.allclose(z, [float(r['utility']) for r in recs], atol=1e-12)          # z_pre + sum r = utility
        for st in logs.state[logs.elig]:
            assert tuple(sorted(st)) == tuple(sorted(DB.STATE_FIELDS))                   # observed history only
        for name in POLS:
            w = DB.EA.weights(logs, DB.prob_policy(CAT[name]))[:, -1]
            assert np.allclose(w, [float(S.ipw_weight(r, CAT[name])) for r in recs], atol=1e-12)


@pytest.mark.parametrize('lname', ['uniform_floor_0.5', 'feedback_dependent_floor_0.2'])
def test_dr_is_exactly_unbiased_with_known_or_wrong_q_and_or_is_exact_with_known_q(lname):
    for name in POLS:
        pol = CAT[name]
        Qk, fbk = DB.known_kernel_q(CELL, pol)
        Q0, fb0 = [dict() for _ in range(CELL.K)], [{0: 0.0, 1: 0.0} for _ in range(CELL.K)]
        totals = {'dr_known': 0.0, 'dr_zero_q': 0.0, 'or_known': 0.0, 'pdis': 0.0}
        for s in (0, 1):
            br = branches(CELL, s, L.LOGGERS[lname])
            probs = np.array([float(p) for p, _ in br]); recs = [r for _, r in br]
            logs = DB.to_logs(recs, CELL.K); pre = np.array([float(DB.z_pre(r)) for r in recs])
            drk, v0k = DB.EA.dr_scores(logs, DB.prob_policy(pol), Qk, fbk)
            dr0, _ = DB.EA.dr_scores(logs, DB.prob_policy(pol), Q0, fb0)
            totals['dr_known'] += 0.5 * float(probs @ (pre + drk))
            totals['dr_zero_q'] += 0.5 * float(probs @ (pre + dr0))
            totals['or_known'] += 0.5 * float(probs @ (pre + v0k))
            W = DB.EA.weights(logs, DB.prob_policy(pol))
            totals['pdis'] += 0.5 * float(probs @ (pre + (W * logs.r).sum(1)))
        tr = G.mix(lambda s: (lambda v: v['success'] - v['cost'])(G.enumerate_value(pol, CELL, s)[0]))
        for k, v in totals.items():
            assert abs(v - float(tr)) < 1e-12, (name, lname, k, v, float(tr))


def test_estimates_on_a_seeded_block_match_sampler_ipw_and_use_task_folds(monkeypatch):
    tasks = [('t%04d' % g, g % 2) for g in range(12)]
    d = S.SeededDraws(123)
    log = S.run_blocks(tasks, CELL, 4, d, 'cfg=test|rep=0', 'log', logger=L.LOGGERS['uniform_floor_0.5'],
                       logger_name='uniform_floor_0.5')
    seen = []
    real_fit, real_dr = DB.EA.fit_q, DB.EA.dr_scores
    monkeypatch.setattr(DB.EA, 'fit_q', lambda tr, pol, **k: (seen.append(('train', set(tr.task))), real_fit(tr, pol, **k))[1])
    monkeypatch.setattr(DB.EA, 'dr_scores', lambda te, pol, Q, fb: (seen.append(('test', set(te.task))), real_dr(te, pol, Q, fb))[1])
    pol = CAT['history_large_after_exception']
    est = DB.estimates(log, pol, tasks, 4, CELL.K, folds=3, seed=0)
    # independent per-decision IPW: stage reward times the product of 1{match}/p over decisions up to that stage
    def pdis(rec):
        total, w, key = float(DB.z_pre(rec)), 1.0, None
        for j, d in enumerate(rec['decisions']):
            key = pol.init_key(rec['stratum'], rec['observations'][0], None) if j == 0 else \
                pol.update(key, rec['decisions'][j - 1]['action'], rec['observations'][j], None)
            w *= (pol.act(rec['stratum'], d['t'], key) == d['action']) / float(d['p_logged'])
            total += w * (-float(G.C[d['action']]) + (rec['success'] if j == len(rec['decisions']) - 1 else 0))
        return total
    by_task = {}
    for rec in log:
        by_task.setdefault(rec['task_id'], []).append(pdis(rec))
    assert abs(est['pdis'] - np.mean([np.mean(v) for v in by_task.values()])) < 1e-12
    assert np.isfinite(est['dr']) and np.isfinite(est['or_plugin'])
    trains = [t for k, t in seen if k == 'train']; tests = [t for k, t in seen if k == 'test']
    assert len(trains) == len(tests) == 3
    assert all(not (tr & te) for tr, te in zip(trains, tests))                 # no task in both train and test
    assert set().union(*tests) == {t for t, _ in tasks}                         # every task scored exactly once
    with pytest.raises(S.ManifestError):
        DB.estimates(log[:-1], pol, tasks, 4, CELL.K)                          # complete-manifest guard applies
