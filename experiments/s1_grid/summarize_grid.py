"""Collect the S1 grid into one long table and a compact report. Reads results/s1_grid/<cell>/ only."""
from __future__ import annotations
import json, re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'results' / 's1_grid'


def main():
    rows, diag = [], []
    for cell in sorted(p for p in SRC.iterdir() if (p / 'summary.json').exists()):
        m = re.match(r'n(\d+)_T(\d+)_eps(\dp\d+)', cell.name)
        n, T, eps = int(m.group(1)), int(m.group(2)), float(m.group(3).replace('p', '.'))
        for r in json.loads((cell / 'summary.json').read_text()):
            rows.append(dict(n=n, horizon=T, floor=eps, **r))
        rep = pd.read_csv(cell / 'replicates.csv')
        keep = [c for c in rep.columns if c in ('policy', 'q_spec', 'behavior', 'zero_weight_fraction', 'ess_terminal', 'max_weight_terminal')]
        d = json.loads((cell / 'diagnostics.json').read_text())
        diag.append(dict(n=n, horizon=T, floor=eps, cell=cell.name, diagnostics_keys=','.join(sorted(d[0].keys())) if isinstance(d, list) and d else str(type(d).__name__),
                         replicate_columns=','.join(rep.columns)))
    long = pd.DataFrame(rows); long.to_csv(SRC / 'grid_summary_long.csv', index=False)
    pd.DataFrame(diag).to_csv(SRC / 'grid_cells.csv', index=False)
    main_spec = long[(long.q_spec == 'correct') & (long.behavior == 'known')]
    out = ['# S1 crossed grid: n x horizon x overlap floor (reference simulator, 1,000 replicates per cell)', '',
           'Cells found: %d of 27. Known propensities and correctly specified tabular Q unless stated. Coverage Monte Carlo SE is about 0.007 at 0.95.' % long[['n', 'horizon', 'floor']].drop_duplicates().shape[0], '']
    for method in ('dr', 'ipw'):
        sub = main_spec[main_spec.method == method]
        cov = sub.groupby(['horizon', 'floor', 'n'])['coverage_95'].agg(['min', 'mean']).round(3).unstack('n')
        out += ['## %s: 95%% interval coverage across the five policies (min / mean), by horizon x floor x n' % method.upper(), '', cov.to_markdown(), '']
        rm = sub.groupby(['horizon', 'floor', 'n'])['rmse'].mean().round(4).unstack('n')
        out += ['### %s: mean RMSE over policies' % method.upper(), '', rm.to_markdown(), '']
    bad = main_spec[(main_spec.method == 'dr') & (main_spec.coverage_95 < 0.92)].sort_values('coverage_95')
    out += ['## DR cells with coverage below 0.92 (correct Q, known propensities)', '',
            (bad[['n', 'horizon', 'floor', 'policy', 'bias', 'rmse', 'coverage_95']].round(4).to_markdown(index=False) if len(bad) else '_none_'), '']
    rob = long[(long.method == 'dr')].groupby(['q_spec', 'behavior', 'horizon'])[['bias', 'coverage_95']].agg(lambda s: float(np.mean(np.abs(s))) if s.name == 'bias' else float(np.mean(s))).round(4)
    out += ['## DR under nuisance misspecification: mean |bias| and mean coverage by horizon (all n, floors, policies)', '', rob.to_markdown(), '']
    (SRC / 'grid_report.md').write_text('\n'.join(out)); print('\n'.join(out))


if __name__ == '__main__':
    main()
