"""Collect the S1 grid into one long table and a compact report. Reads results/s1_grid/<cell>/ only."""
from __future__ import annotations
import json, re
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / 'results' / 's1_grid'


def main():
    rows = []
    for cell in sorted(p for p in SRC.iterdir() if (p / 'summary.json').exists()):
        m = re.match(r'n(\d+)_T(\d+)_eps(\dp\d+)', cell.name)
        n, T, eps = int(m.group(1)), int(m.group(2)), float(m.group(3).replace('p', '.'))
        for r in json.loads((cell / 'summary.json').read_text()):
            rows.append(dict(n=n, horizon=T, floor=eps, **r))
    long = pd.DataFrame(rows); long.to_csv(SRC / 'grid_summary_long.csv', index=False)
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
    # ---- evaluation cost: one shared randomized log (DR) vs the same n episodes split across the policies, each run on-policy
    import sys; sys.path.insert(0, str(ROOT / 'src'))
    from dtr_agent_evals.simulator import Environment, simulate
    cost = []
    for (T, eps), g in main_spec[main_spec.method == 'dr'].groupby(['horizon', 'floor']):
        env = Environment(horizon=int(T), cost=0.06, overlap=float(eps)); pols = sorted(g.policy.unique())
        sd = {p: float(np.std(simulate(100_000, np.random.default_rng(7), env, p).r.sum(axis=1), ddof=1)) for p in pols}
        for _, r in g.iterrows():
            separate = sd[r.policy] / np.sqrt(r.n / len(pols))
            cost.append(dict(horizon=T, floor=eps, n=r.n, policy=r.policy, dr_rmse_shared_log=r.rmse, onpolicy_rmse_split_budget=separate,
                             rmse_ratio_separate_over_dr=separate / r.rmse if r.rmse > 0 else np.nan))
    cost = pd.DataFrame(cost); cost.to_csv(SRC / 'evaluation_cost.csv', index=False)
    piv = cost.groupby(['horizon', 'floor', 'policy'])['rmse_ratio_separate_over_dr'].mean().round(2).unstack('policy')
    out += ['## Evaluation cost: RMSE of on-policy evaluation with the budget split across %d policies, divided by DR RMSE from ONE shared randomized log of the same total size' % cost.policy.nunique(), '',
            'Ratio > 1: the shared randomized log is the cheaper way to evaluate that policy; < 1: running the policy directly is cheaper. Averaged over n. On-policy RMSE is sd(return)/sqrt(n/5) with sd from a 100,000-episode rollout.', '',
            piv.to_markdown(), '']
    (SRC / 'grid_report.md').write_text('\n'.join(out)); print('\n'.join(out))


if __name__ == '__main__':
    main()
