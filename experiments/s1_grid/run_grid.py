"""S1 core grid (docs/experiment_protocol.md 3.2): n x horizon x overlap floor, CROSSED,
1,000 replicates per cell, using the repository's reference simulator and estimators unchanged
(scripts/run_simulation.py is invoked as a subprocess; nothing under src/ or scripts/ is edited).

Crossing the factors separates horizon from overlap, which the archived stress runs vary jointly
(docs/experiment_handoff.md, work item 6). Configs are written to configs/s1_grid/ and each cell
to its own directory under results/s1_grid/; the reference runner refuses nonempty destinations.

  python experiments/s1_grid/run_grid.py --workers 4
  python experiments/s1_grid/summarize_grid.py
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NS, HORIZONS, FLOORS = (250, 1000, 4000), (2, 5, 10), (0.5, 0.2, 0.05)
POLICIES = ['always_small', 'always_large', 'fixed_switch', 'failure_escalation', 'soft_escalation']
SPECS = [['correct', 'known'], ['misspecified', 'known'], ['correct', 'misspecified'], ['misspecified', 'misspecified']]


def cell_name(n, T, eps):
    return 'n%d_T%d_eps%s' % (n, T, str(eps).replace('.', 'p'))


def run_cell(args):
    n, T, eps, reps = args
    name = cell_name(n, T, eps)
    cfg_path = ROOT / 'configs' / 's1_grid' / (name + '.json'); out = ROOT / 'results' / 's1_grid' / name
    if (out / 'summary.json').exists():
        return name, 'already complete', 0.0
    cfg = dict(seed=20260918, n=n, replicates=reps, folds=3, truth_mc_n=200000,
               environment=dict(horizon=T, cost=0.06, overlap=eps), policies=POLICIES, specifications=SPECS)
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(json.dumps(cfg, indent=2) + '\n')
    t0 = time.time()
    r = subprocess.run([sys.executable, str(ROOT / 'scripts' / 'run_simulation.py'), '--config', str(cfg_path), '--output', str(out)],
                       cwd=ROOT, env=dict(os.environ, PYTHONPATH=str(ROOT / 'src')), capture_output=True, text=True)
    return name, ('ok' if r.returncode == 0 else 'FAILED: ' + r.stderr[-400:]), time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--workers', type=int, default=4); ap.add_argument('--replicates', type=int, default=1000)
    a = ap.parse_args()
    cells = [(n, T, e, a.replicates) for T in HORIZONS for e in FLOORS for n in NS]
    with ThreadPoolExecutor(a.workers) as ex:
        for name, status, sec in ex.map(run_cell, cells):
            print('%-22s %-18s %.0fs' % (name, status[:60], sec), flush=True)


if __name__ == '__main__':
    main()
