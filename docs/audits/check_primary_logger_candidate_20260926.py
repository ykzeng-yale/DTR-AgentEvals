"""Deterministic lead algebra check, not estimator code or coverage simulation.

Run from repository root with Python 3.10+: prints the checked counts.
"""
from fractions import Fraction as F
from itertools import product
import math

values, contrasts = [], []
for q0, q1, y, h, p, a in product([0, 1], repeat=6):
    q = [q0, q1]
    phi_h = q[h] + 2 * (a == h) * (y - q[h])
    phi_p = q[p] + 2 * (a == p) * (y - q[p])
    values.extend([phi_h, phi_p])
    contrasts.append(phi_h - phi_p)
    assert h != p or phi_h == phi_p
assert (min(values), max(values)) == (-1, 2)
assert (min(contrasts), max(contrasts)) == (-2, 2)

cases = 0
for q0, q1, m0, m1 in product([F(0), F(1, 3), F(1)], repeat=4):
    for h, p in product([0, 1], repeat=2):
        q, mu = [q0, q1], [m0, m1]
        mean, second = F(0), F(0)
        for a, y in product([0, 1], repeat=2):
            probability = F(1, 2) * (mu[a] if y else 1 - mu[a])
            difference = (q[h] + 2 * (a == h) * (y - q[h])
                          - q[p] - 2 * (a == p) * (y - q[p]))
            mean += probability * difference
            second += probability * difference**2
        assert mean == mu[h] - mu[p]
        assert second <= 4 * (h != p)
        cases += 1
counts = [math.ceil(w**2 * math.log(120) / (2 * .05**2)) for w in [2, 4, 6]]
assert counts == [3830, 15320, 34470]
assert 20 * 3 * counts[2] == 2068200
print(f"64 vertices; {cases} exact conditional checks; counts {counts}: passed")
