"""Checks for DTR-REQ-003 item 3 (experiments/v2_sim/branch_module.py), with an independent episode enumerator."""
import json, sys
from fractions import Fraction as Fr
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import branch_module as B  # noqa: E402
import repair_generator as G  # noqa: E402


def brute_episode(cell, s, a0):
    """Independent full-tree enumeration of one source episode: E[1{prefix}], E[W_a Y], E[W_a], and the calibrated
    E[1{prefix} (V_large - V_small)] computed from explicit stay trees (no helper from the module)."""
    M = Fr(0); WY = {0: Fr(0), 1: Fr(0)}; W = {0: Fr(0), 1: Fr(0)}; T = Fr(0)

    def stay(u, a, t=1):
        ok = cell.repair[u, a]
        if t == 2:
            return ok
        cont = sum((cell.stay[u, a] if u2 else 1 - cell.stay[u, a]) * (1 - G.FALSE_PASS[s]) * stay(u2, a, 2) for u2 in (0, 1))
        return ok + (1 - ok) * cont

    for u0 in (0, 1):
        for o0 in G.OBS:
            p = (1 - B.P0A[s][a0]) * (G.DEEP0[s] if u0 else 1 - G.DEEP0[s]) * cell.p_obs(o0, u0, s)
            if o0 == 'pass' or not p:
                continue
            M += p
            T += p * (stay(u0, 1) - stay(u0, 0))
            for a1 in (0, 1):
                for y1 in (0, 1):
                    q1 = Fr(1, 2) * (cell.repair[u0, a1] if y1 else 1 - cell.repair[u0, a1])
                    if y1:
                        for a in (0, 1):
                            w = 2 if a1 == a else 0
                            WY[a] += p * q1 * w; W[a] += p * q1 * w
                        continue
                    for u1 in (0, 1):
                        for o1 in G.OBS:
                            q2 = q1 * (cell.stay[u0, a1] if u1 else 1 - cell.stay[u0, a1]) * cell.p_obs(o1, u1, s)
                            if o1 == 'pass':
                                for a in (0, 1):
                                    W[a] += p * q2 * (2 if a1 == a else 0)
                                continue
                            for a2 in (0, 1):
                                for a in (0, 1):
                                    w = 4 if a1 == a == a2 else 0
                                    WY[a] += p * q2 * Fr(1, 2) * cell.repair[u1, a2] * w
                                    W[a] += p * q2 * Fr(1, 2) * w
    return M, T, WY, W


@pytest.mark.parametrize('crossing', ['no_crossing', 'crossing'])
@pytest.mark.parametrize('feedback', ['informative', 'weak'])
def test_module_matches_independent_enumeration(crossing, feedback):
    cell = G.Cell(2, crossing, feedback)
    for s in (0, 1):
        for a0 in (0, 1):
            r = B.per_episode(cell, s, a0, Fr(1))
            M, T, WY, W = brute_episode(cell, s, a0)
            assert (r['M'], r['T']) == (M, T)
            assert r['U'] == WY and r['D'] == W
            assert all(W[a] == M for a in (0, 1))                     # E(W_a | prefix) = 1
            assert WY[1] - WY[0] == T                                  # calibration: log contrast total = branch total


def test_calibrated_delta_zero_and_drift_nonzero():
    rep = B.build()
    for r in rep['rows']:
        if r['restored_law'] == 'calibrated':
            assert r['Delta'] == '0' and r['expected_weight_equals_expected_prefixes']
        else:
            assert Fr(r['Delta']) < 0


@pytest.mark.parametrize('N,Ds,Dl,want', [
    (0, 0, 0, ('whole_range_[-2,2]', 0)), (150, 10, 12, ('census', 150)), (200, 5, 5, ('census', 200)),
    (564, 300, 280, ('srswor', 200)), (564, 0, 280, ('whole_range_[-2,2]', 0)), (564, 300, 0, ('whole_range_[-2,2]', 0))])
def test_frame_rule_deterministic_cases(N, Ds, Dl, want):
    assert B.frame_rule(N, Ds, Dl) == want


def test_committed_output_matches_generator():
    assert json.loads(B.OUT.read_text()) == json.loads(json.dumps(B.build()))
