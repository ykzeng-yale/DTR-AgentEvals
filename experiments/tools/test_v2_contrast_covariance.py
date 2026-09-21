"""Checks for experiments/v2_sim/contrast_covariance.py: acceptance identities plus an independent joint-moment enumerator."""
import json, sys
from fractions import Fraction as Fr
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import contrast_covariance as CC  # noqa: E402
import repair_generator as G  # noqa: E402
import repair_logger as L  # noqa: E402


@pytest.fixture(scope='module')
def rep():
    return CC.build()


def brute_joint(p1, p2, cell, s, logger):
    """Independent: explicit stack over every logger branch; returns E[X1], E[X2], E[X1 X2], E[(X1 - X2)^2]."""
    acc = [Fr(0)] * 4

    def add(pr, w1, w2, cost, y):
        z = y - cost
        x1, x2 = w1 * z, w2 * z
        acc[0] += pr * x1; acc[1] += pr * x2; acc[2] += pr * x1 * x2; acc[3] += pr * (x1 - x2) ** 2

    add(G.P0[s], Fr(1), Fr(1), G.C[0], 1)
    stack = []
    for u0 in (0, 1):
        for o0 in G.OBS:
            p = (1 - G.P0[s]) * (G.DEEP0[s] if u0 else 1 - G.DEEP0[s]) * cell.p_obs(o0, u0, s)
            if o0 == 'pass':
                add(p, Fr(1), Fr(1), G.C[0], 0)
            elif p:
                stack.append((1, u0, p1.init_key(s, o0, None), p2.init_key(s, o0, None), o0, p, Fr(1), Fr(1), G.C[0]))
    while stack:
        t, u, k1, k2, lo, pr, w1, w2, cost = stack.pop()
        q = logger(s, t, lo)
        for a in (0, 1):
            pa = q if a else 1 - q
            if not pa:
                continue
            v1 = w1 / pa if p1.act(s, t, k1) == a else Fr(0)
            v2 = w2 / pa if p2.act(s, t, k2) == a else Fr(0)
            c2 = cost + G.C[a]
            add(pr * pa * cell.repair[u, a], v1, v2, c2, 1)
            for u2 in (0, 1):
                for o in G.OBS:
                    pp = pr * pa * (1 - cell.repair[u, a]) * (cell.stay[u, a] if u2 else 1 - cell.stay[u, a]) * cell.p_obs(o, u2, s)
                    if not pp:
                        continue
                    if o == 'pass' or t == cell.K:
                        add(pp, v1, v2, c2, 0)
                    else:
                        stack.append((t + 1, u2, p1.update(k1, a, o, None), p2.update(k2, a, o, None), o, pp, v1, v2, c2))
    return acc


def test_acceptance_checks(rep):
    assert rep['checks'] == dict(direct_moment_matches_covariance_formula=True, covariance_psd_everywhere=True,
                                 identical_policy_contrast_zero=True)
    assert len(rep['rows']) == 8 * 2 * 4


@pytest.mark.parametrize('cfg', [(2, 'crossing', 'informative'), (4, 'no_crossing', 'weak')])
@pytest.mark.parametrize('lname', CC.CORE_LOGGERS)
def test_joint_moments_match_independent_enumerator(cfg, lname):
    cell = G.Cell(*cfg)
    cat = {p.name: p for p in G.catalog(cell.K)}
    pols = [cat[CC.HIST], cat[CC.PROMPT], cat['fixed_' + 'L' * cell.K]]
    for s in (0, 1):
        m1, m2, direct = CC.moments(pols, cell, s, L.LOGGERS[lname])
        for j in (1, 2):
            e1, e2, e12, ed = brute_joint(pols[0], pols[j], cell, s, L.LOGGERS[lname])
            assert (m1[0], m1[j], m2[0][j], direct[j]) == (e1, e2, e12, ed)


def test_contrast_variance_scales_with_blocks(rep):
    for r in rep['rows']:
        v = {k: Fr(x['exact']) for k, x in r['per_episode_contrast_variance'].items()}
        for n in (250, 1000):
            assert Fr(r['n%d' % n]['exact_var']['exact']) == (v['easy'] + v['hard']) / (2 * CC.R_BLOCK * n)


def test_committed_output_matches_generator(rep):
    assert json.loads(CC.OUT.read_text()) == json.loads(json.dumps(rep))
