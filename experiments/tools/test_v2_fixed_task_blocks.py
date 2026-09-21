"""Checks for DTR-REQ-003 item 2 (experiments/v2_sim/fixed_task_blocks.py), with an independent moment enumerator."""
import hashlib, json, sys
from fractions import Fraction as Fr
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import fixed_task_blocks as B  # noqa: E402
import repair_generator as G  # noqa: E402
import repair_logger as L  # noqa: E402


@pytest.fixture(scope='module')
def rep():
    return B.build()


def brute_moments(pol, cell, s, logger):
    """Independent: branch on EVERY logger action, carrying W = prod 1{A = pi}/p (zero once any action mismatches)."""
    m1 = m2 = Fr(0)
    stack = []
    out = [(G.P0[s], Fr(1), G.C[0], 1)]                           # common first call correct: no decision
    for u0 in (0, 1):
        for o0 in G.OBS:
            p = (1 - G.P0[s]) * (G.DEEP0[s] if u0 else 1 - G.DEEP0[s]) * cell.p_obs(o0, u0, s)
            if o0 == 'pass':
                out.append((p, Fr(1), G.C[0], 0))
            elif p:
                stack.append((1, u0, pol.init_key(s, o0, None), o0, p, Fr(1), G.C[0], 0))
    while stack:
        t, u, key, last_o, pr, w, cost, _ = stack.pop()
        p1 = logger(s, t, last_o)
        for a in (0, 1):
            pa = p1 if a else 1 - p1
            w2 = w * (Fr(1) / pa if a == pol.act(s, t, key) else 0)
            pr2, cost2 = pr * pa, cost + G.C[a]
            out.append((pr2 * cell.repair[u, a], w2, cost2, 1))
            for u2 in (0, 1):
                pu = cell.stay[u, a] if u2 else 1 - cell.stay[u, a]
                for o in G.OBS:
                    p = pr2 * (1 - cell.repair[u, a]) * pu * cell.p_obs(o, u2, s)
                    if not p:
                        continue
                    if o == 'pass' or t == cell.K:
                        out.append((p, w2, cost2, 0))
                    else:
                        stack.append((t + 1, u2, pol.update(key, a, o, None), o, p, w2, cost2, 0))
    for p, w, cost, y in out:
        z = w * (y - cost)
        m1 += p * z; m2 += p * z * z
    return m1, m2


@pytest.mark.parametrize('cfg', [(2, 'crossing', 'informative'), (4, 'no_crossing', 'weak')])
@pytest.mark.parametrize('lname', B.CORE_LOGGERS)
def test_ipw_moments_match_independent_enumeration(cfg, lname):
    cell = G.Cell(*cfg)
    for pol in G.catalog(cell.K):
        for s in (0, 1):
            assert B.ipw_moments(pol, cell, s, L.LOGGERS[lname]) == brute_moments(pol, cell, s, L.LOGGERS[lname])


def test_task_lists_frozen():
    for n in B.NS:
        tasks, digest = B.task_list(n)
        assert sum(s for _, s in tasks) == n // 2 and len(tasks) == n
        assert digest == hashlib.sha256('\n'.join('t%04d,%d' % (g, g % 2) for g in range(n)).encode()).hexdigest()


def test_target_equals_mixture_and_between_task_identity(rep):
    assert len(rep['rows']) == 96
    for r in rep['rows']:
        assert r['theta_equals_kernel_mixture']
        v = {k: Fr(x['exact']) for k, x in r['per_episode_ipw_variance'].items()}
        var = (v['easy'] + v['hard']) / 2 / (r['r'] * r['n'])       # n^-2 * sum_g sigma^2 / r with n/2 per stratum
        assert Fr(r['exact_var_V_hat']['exact']) == var
        assert Fr(r['expected_iid_task_formula']['exact']) - var == Fr(r['iid_formula_excess_between_task']['exact'])
        assert Fr(r['iid_formula_excess_between_task']['exact']) >= 0


def test_between_task_term_closed_form(rep):
    # with exact 50/50 strata: sum_g (mu_g - mu_bar)^2 / (n(n-1)) = (V_hard - V_easy)^2 / (4 (n - 1))
    for r in rep['rows'][:12]:
        cell = G.Cell(r['K'], r['action_effect'], r['feedback'])
        pol = next(p for p in G.catalog(r['K']) if p.name == r['policy'])
        V = [G.enumerate_value(pol, cell, s)[0] for s in (0, 1)]
        d = (V[1]['success'] - V[1]['cost']) - (V[0]['success'] - V[0]['cost'])
        assert Fr(r['iid_formula_excess_between_task']['exact']) == d * d / (4 * (r['n'] - 1))


def test_committed_output_matches_generator(rep):
    assert json.loads(B.OUT.read_text()) == json.loads(json.dumps(rep))
