"""Pre-specified analysis of the code-routing study (protocol.md section 5).

  python analysis.py --learn         fitted-Q greedy routing table from TRAIN-task logs; frozen to learned_policy.json
  python analysis.py --ope           off-policy values of the frozen policy class on CONFIRM-task logs
  python analysis.py --calibration   OPE vs fresh live executions (needs the live stage)
  add --mock to analyse a dry run under work/ (labelled; never reported)

All inference is at task level (theory eq. 13). Known behaviour probabilities only.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

import numpy as np
import pandas as pd

from common import RESULTS, ROOT, load_config, now_iso, sha256_bytes
import estimators_absorbing as EA
import policies as P


def read(path: Path) -> list:
    rows = [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    return [r for r in rows if not r.get('error')], sum(1 for r in rows if r.get('error'))


def policy_class(base: Path) -> dict:
    cls = dict(P.PRESPECIFIED)
    lp = base / 'learned_policy.json'
    if lp.exists():
        cls['learned'] = P.table_policy({tuple(k): v for k, v in json.loads(lp.read_text())['table']})
    return cls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--learn', action='store_true'); ap.add_argument('--ope', action='store_true')
    ap.add_argument('--calibration', action='store_true'); ap.add_argument('--mock', action='store_true')
    a = ap.parse_args()
    cfg = load_config(); K = cfg['horizon']
    base = (ROOT / 'work' / 'code_routing_mock') if a.mock else RESULTS
    out = base / 'analysis'; out.mkdir(exist_ok=True)
    tag = '**[MOCK DRY RUN: numbers are meaningless]** ' if a.mock else ''
    eps, n_err = read(base / 'log' / 'episodes.jsonl')
    train = [e for e in eps if e['split'] == 'train']; conf = [e for e in eps if e['split'] == 'confirm']

    if a.learn:
        lp = base / 'learned_policy.json'
        if lp.exists():
            raise SystemExit('%s already frozen' % lp)
        table = EA.learn_greedy_table(EA.from_episodes(train, K, P.state_key, 'utility'))
        lp.write_text(json.dumps(dict(created_utc=now_iso(), objective='utility', n_train_episodes=len(train),
                                      n_train_tasks=len({e['task_uid'] for e in train}), table=[[list(k), v] for k, v in sorted(table.items(), key=str)]), indent=1))
        print('learned table (state_key -> P(large)):'); [print('  ', k, v) for k, v in sorted(table.items(), key=str)]
        print('frozen ->', lp, sha256_bytes(lp.read_bytes()))

    if a.ope or a.calibration:
        cls = policy_class(base); names = list(cls); rows = []; scores = {}
        for outcome in ('utility', 'success'):
            L = EA.from_episodes(conf, K, P.state_key, outcome)
            for nm in names:
                s = EA.cluster_scores(L, cls[nm]); scores[(outcome, nm)] = s
                d = s['diagnostics']
                rows.append(dict(outcome=outcome, policy=nm, **{'dr_' + k: v for k, v in EA.summary(s['dr']).items()},
                                 ipw=float(s['ipw'].mean()), ipw_se=EA.summary(s['ipw'])['se'], gcomp=float(s['plugin'].mean()),
                                 ess_last_stage=d['ess_by_stage'][-1], max_weight=d['max_weight_by_stage'][-1],
                                 zero_weight_fraction=d['zero_weight_fraction'], tasks_with_support=d['n_tasks_with_positive_weight'],
                                 missing_q_cells=d['missing_q_cells_in_training']))
        ope = pd.DataFrame(rows); ope.to_csv(out / 'ope_confirm.csv', index=False)
        ncmp = len(names) - 1; z = float(abs(np.quantile(np.random.default_rng(0).standard_normal(2_000_000), cfg['alpha'] / (2 * ncmp))))
        crow = []
        for outcome in ('utility', 'success'):
            b = scores[(outcome, P.BASELINE)]['dr']
            for nm in names:
                if nm == P.BASELINE:
                    continue
                s = EA.summary(scores[(outcome, nm)]['dr'] - b)
                crow.append(dict(outcome=outcome, contrast='%s - %s' % (nm, P.BASELINE), estimate=s['estimate'], se=s['se'], lower95=s['lower'], upper95=s['upper'],
                                 lower_bonferroni=s['estimate'] - z * s['se'], upper_bonferroni=s['estimate'] + z * s['se']))
        con = pd.DataFrame(crow); con.to_csv(out / 'ope_contrasts_confirm.csv', index=False)
        cert = EA.hoeffding_certificate(ncmp, len({e['task_uid'] for e in conf}), K, 1.0 + max(cfg['call_penalty'].values()), 1 / min(cfg['p_large'], 1 - cfg['p_large']), cfg['alpha'])
        (out / 'theorem5_certificate.json').write_text(json.dumps(cert, indent=1))
        rep = ['# Code-routing: off-policy evaluation on CONFIRM tasks', '', tag + 'log episodes %d (infrastructure errors excluded: %d); confirm tasks %d; train tasks %d' % (
            len(eps), n_err, len({e['task_uid'] for e in conf}), len({e['task_uid'] for e in train})), '',
            '## Policy values (cross-fitted DR, task-level SE)', '', ope.round(4).to_markdown(index=False), '',
            '## Paired contrasts vs %s (DR); Bonferroni over %d comparisons, z=%.3f' % (P.BASELINE, ncmp, z), '', con.round(4).to_markdown(index=False), '',
            '## Theorem 5 (Hoeffding) simultaneous half-width at this sample size', '',
            'M = %.1f, epsilon_n = %.3f (utility range is about 1.1, so the certificate is %s); tasks needed for half-width 0.05: %.3g' % (
                cert['M'], cert['epsilon'], 'VACUOUS' if cert['epsilon'] > 1 else 'informative', cert['n_tasks_for_half_width_0p05']), '']
        (out / 'report_ope.md').write_text('\n'.join(rep)); print('\n'.join(rep))

    if a.calibration:
        live, n_err_l = read(base / 'live' / 'episodes.jsonl'); rows = []
        calls_log = sum(e['n_decisions'] for e in conf)
        for outcome in ('utility', 'success'):
            for nm in sorted({e['policy'] for e in live}):
                le = [e for e in live if e['policy'] == nm]
                lt, lv = EA.cluster_means(np.array([e['task_uid'] for e in le], object), np.array([e[outcome] for e in le], float))
                s = scores[(outcome, nm)]; common = np.intersect1d(s['tasks'], lt)
                dr = pd.Series(s['dr'], index=s['tasks'])[common].to_numpy(); lv = pd.Series(lv, index=lt)[common].to_numpy()
                d = EA.summary(dr - lv); L_ = EA.summary(lv); O_ = EA.summary(dr)
                rows.append(dict(outcome=outcome, policy=nm, n_tasks=len(common), live=L_['estimate'], live_se=L_['se'], ope_dr=O_['estimate'], ope_se=O_['se'],
                                 ope_minus_live=d['estimate'], diff_se_paired=d['se'], diff_lower=d['lower'], diff_upper=d['upper'],
                                 covers_zero=bool(d['lower'] <= 0 <= d['upper']), live_model_calls=sum(e['n_decisions'] for e in le),
                                 shared_log_model_calls=calls_log, se_ratio_ope_over_live=O_['se'] / L_['se'] if L_['se'] else np.nan))
        cal = pd.DataFrame(rows); cal.to_csv(out / 'calibration_ope_vs_live.csv', index=False)
        u = cal[cal.outcome == 'utility']
        rank = float(pd.Series(u['live'].to_numpy()).corr(pd.Series(u['ope_dr'].to_numpy()), method='spearman'))
        rep = ['# Code-routing: OPE vs fresh live executions (CONFIRM tasks)', '', tag + 'live infrastructure errors excluded: %d' % n_err_l, '',
               cal.round(4).to_markdown(index=False), '', 'Spearman rank agreement of policy utilities, OPE vs live: %.3f' % rank, '',
               'Evaluation cost: ONE randomized log of %d model calls supports every policy above; the live arm spent %d calls in total (%d policies).' % (
                   calls_log, int(u['live_model_calls'].sum()), len(u)), '']
        (out / 'report_calibration.md').write_text('\n'.join(rep)); print('\n'.join(rep))


if __name__ == '__main__':
    main()
