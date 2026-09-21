"""Pre-authorization checks for the prepared DR/OR batch: pairing, determinism and refusal to run unfrozen."""
import json, math, sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import dev_batch as D  # noqa: E402
import dev_batch_dr as R  # noqa: E402


def test_run_refuses_without_a_frozen_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(R, 'MANIFEST', tmp_path / 'manifest.json')
    with pytest.raises(SystemExit, match='lead authorization'):
        R.run()


def test_regenerated_log_reproduces_committed_ipw_for_repetition_0():
    # the committed dev_batch record for one cell/repetition must be reproduced bit-for-bit by the paired job
    reps = {(r['config'], r['repetition']): r for r in map(json.loads, D.REPS.read_text().splitlines())}
    cell = D.cells()[1]
    original = {k: v['ipw'] for k, v in reps[(cell['config'], 0)]['policies'].items()}
    rec = R.job((cell, 0, original))
    for name, p in rec['policies'].items():
        assert p['ipw_reproduction_abs_diff'] == 0.0, name
        assert all(math.isfinite(p[k]) for k in ('pdis', 'dr', 'or_plugin', 'dr_known_kernel'))


def test_job_is_deterministic():
    cell = D.cells()[0]
    a, b = R.job((cell, 3, None)), R.job((cell, 3, None))
    assert a['policies'] == b['policies']
