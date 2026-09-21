"""Pre-launch checks for the stage-2-Q intervention: exact reproduction of the committed IPW and standard OR."""
import json, math, sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'v2_sim'))
import dev_batch as D  # noqa: E402
import dev_batch_dr as R  # noqa: E402
import dev_batch_or_stage2 as O  # noqa: E402


def test_refuses_without_manifest(tmp_path, monkeypatch):
    monkeypatch.setattr(O, 'MANIFEST', tmp_path / 'manifest.json')
    with pytest.raises(SystemExit):
        O.run()


def test_one_repetition_reproduces_committed_ipw_and_standard_or_exactly():
    ipw = {(r['config'], r['repetition']): r for r in map(json.loads, D.REPS.read_text().splitlines())}
    dr = {(r['config'], r['repetition']): r for r in map(json.loads, R.REPS.read_text().splitlines())}
    cell = D.cells()[1]                                          # informative / feedback-dependent (the biased cell)
    key = (cell['config'], 5)
    rec = O.job((cell, 5, {k: v['ipw'] for k, v in ipw[key]['policies'].items()},
                 {k: v['or_plugin'] for k, v in dr[key]['policies'].items()}))
    for name, p in rec['policies'].items():
        assert p['ipw_reproduction_abs_diff'] <= 1e-12 and p['or_reproduction_abs_diff'] <= 1e-12, name
        assert math.isfinite(p['or_oracle_stage2'])
