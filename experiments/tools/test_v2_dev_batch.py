"""Pre-launch checks for the bounded CPU development batch (experiment_protocol_v2.md section 7)."""
import json, math, sys
from fractions import Fraction as Fr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import dev_batch as D  # noqa: E402
import sampler as S  # noqa: E402


def test_seeded_streams_are_deterministic_and_order_independent():
    opts = [(0, Fr(1, 2)), (1, Fr(1, 2))]
    a, b = S.SeededDraws(7), S.SeededDraws(7)
    seq_a = [a.choose(('x', i), opts) for i in range(50)] + [a.choose(('y', i), opts) for i in range(50)]
    ys = [b.choose(('y', i), opts) for i in range(50)]
    xs = [b.choose(('x', i), opts) for i in range(50)]
    assert seq_a == xs + ys                                  # interleaving/order does not change a stream
    assert [S.SeededDraws(7).choose(('x', i), opts) for i in range(1)] != [None]
    c = S.SeededDraws(8)
    assert [c.choose(('x', i), opts) for i in range(50)] != xs      # a different root seed changes the draws


def test_zero_probability_outcomes_are_never_drawn():
    d = S.SeededDraws(3)
    assert all(d.choose(('z', i), [('never', Fr(0)), ('always', Fr(1))]) == 'always' for i in range(200))


def test_manifest_and_tiny_job(tmp_path, monkeypatch):
    monkeypatch.setattr(D, 'OUT', tmp_path); monkeypatch.setattr(D, 'MANIFEST', tmp_path / 'manifest.json')
    m = D.freeze()
    assert len(m['cells']) == 4 and all(len(c['policies']) == 3 for c in m['cells'])
    assert {c['policies'][2] for c in m['cells']} == {'fixed_LS'}   # exact-table best fixed for both K=2 crossing cells
    assert set(m['source_sha256']) == set(D.HASHED) and m['root_seed'] == 2026092101
    monkeypatch.setattr(D, 'N_TASKS', 4)
    rec = D.job((m['cells'][1], 0))
    assert rec['log_episodes'] == 16 and all(p['fresh_episodes'] == 16 for p in rec['policies'].values())
    assert all(math.isfinite(p['ipw']) and math.isfinite(p['fresh']) for p in rec['policies'].values())
    assert rec['namespace'] == 'cfg=%s|rep=0' % m['cells'][1]['config']
