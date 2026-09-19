"""Pre-specified analysis of the code-routing study (protocol.md section 5).

  python analysis.py --learn         fitted-Q greedy routing table from TRAIN-task logs; frozen to learned_policy.json
  python analysis.py --ope           off-policy values of the frozen policy class on CONFIRM-task logs
  python analysis.py --calibration   OPE vs fresh live executions (needs the live stage)
  python analysis.py --branch        restored-prefix branch audit vs the log-based estimate of the same contrast
  python analysis.py --ops           timeouts, truncation and latency by contention status, per stage
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


def read(path: Path, cfg: dict) -> tuple:
    """One record per episode id: the LAST attempt without an infrastructure error; if every attempt errored the episode
    is scored intention-to-treat (success 0, penalties of the decisions that were assigned) so that every task keeps its
    full set of runs and the randomization is not selected on. Returns (records, info)."""
    rows, torn = [], 0
    lines = [l for l in path.read_text().splitlines() if l.strip()]
    for k, l in enumerate(lines):
        try:
            rows.append(json.loads(l))
        except ValueError:
            if k == len(lines) - 1:
                torn = 1
            else:
                raise
    good, bad = {}, {}
    for r in rows:
        (bad if r.get('error') else good)[r['episode_id']] = r
    out = list(good.values()); itt = 0
    for eid, r in bad.items():
        if eid in good:
            continue
        ds = [d for d in r.get('decisions', [])]
        pen = sum(d.get('penalty', 0.0) for d in ds)
        out.append(dict(r, success=0, penalty=pen, utility=-pen, n_decisions=len(ds), decisions=ds, itt_scored=True)); itt += 1
    info = dict(n_records=len(rows), n_episodes=len(out), n_error_attempts=sum(1 for r in rows if r.get('error')), n_itt_scored=itt,
                n_torn_lines=torn, n_foreign_gpu_load=sum(bool(r.get('foreign_gpu_load_at_start')) for r in out))
    return out, info


def policy_class(base: Path) -> dict:
    cls = dict(P.PRESPECIFIED)
    lp = base / 'learned_policy.json'
    if lp.exists():
        cls['learned'] = P.table_policy({tuple(k): v for k, v in json.loads(lp.read_text())['table']})
    return cls


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--learn', action='store_true'); ap.add_argument('--ope', action='store_true')
    ap.add_argument('--calibration', action='store_true'); ap.add_argument('--branch', action='store_true'); ap.add_argument('--ops', action='store_true'); ap.add_argument('--mock', action='store_true')
    a = ap.parse_args()
    cfg = load_config(); K = cfg['horizon']
    base = (ROOT / 'work' / 'code_routing_mock') if a.mock else RESULTS
    out = base / 'analysis'; out.mkdir(exist_ok=True)
    tag = '**[MOCK DRY RUN: numbers are meaningless]** ' if a.mock else ''
    eps, log_info = read(base / 'log' / 'episodes.jsonl', cfg); n_err = log_info['n_itt_scored']
    train = [e for e in eps if e['split'] == 'train']; conf = [e for e in eps if e['split'] == 'confirm']

    if a.learn:
        lp = base / 'learned_policy.json'
        if lp.exists():
            raise SystemExit('%s already frozen' % lp)
        want = cfg['n_train_tasks'] * cfg['runs_per_task']
        if len(train) != want and not a.mock:
            raise SystemExit('policy learning needs the COMPLETE train log: have %d of %d episodes' % (len(train), want))
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
        from scipy.stats import norm
        ncmp = len(names) - 1      # primary family: utility contrasts of every frozen policy vs the baseline; success contrasts are secondary and use the same z
        z = float(norm.ppf(1 - cfg['alpha'] / (2 * ncmp)))
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
        rep = ['# Code-routing: off-policy evaluation on CONFIRM tasks', '', tag + 'log episodes %d (scored intention-to-treat after exhausting retries: %d); confirm tasks %d; train tasks %d' % (
            len(eps), n_err, len({e['task_uid'] for e in conf}), len({e['task_uid'] for e in train})), '',
            '## Policy values (cross-fitted DR, task-level SE)', '', ope.round(4).to_markdown(index=False), '',
            '## Paired contrasts vs %s (DR); Bonferroni over %d comparisons, z=%.3f' % (P.BASELINE, ncmp, z), '', con.round(4).to_markdown(index=False), '',
            '## Theorem 5 (Hoeffding) simultaneous half-width at this sample size', '',
            'M = %.1f, epsilon_n = %.3f (utility range is about 1.1, so the certificate is %s); tasks needed for half-width 0.05: %.3g' % (
                cert['M'], cert['epsilon'], 'VACUOUS' if cert['epsilon'] > 1 else 'informative', cert['n_tasks_for_half_width_0p05']), '']
        # negative controls (protocol section 5): what the design protects against
        Lu = EA.from_episodes(conf, K, P.state_key, 'success')
        reached = Lu.elig[:, 1]
        naive = float(Lu.r.sum(1)[reached & (Lu.a[:, 1] == 1)].mean() - Lu.r.sum(1)[reached & (Lu.a[:, 1] == 0)].mean()) if reached.any() else float('nan')
        esc_vs_not = float(Lu.r.sum(1)[reached].mean() - Lu.r.sum(1)[~reached].mean()) if reached.any() and (~reached).any() else float('nan')
        wrong = []
        for nm in ('always_small', 'always_large'):
            Lw = EA.from_episodes(conf, K, P.state_key, 'success'); Lw.b = np.where(Lw.elig, np.where(Lw.a == 1, 0.8, 0.2), 1.0)
            W = EA.weights(Lw, cls[nm]); wrong.append((nm, float(np.sum(W * Lw.r, axis=1).mean()), float(scores[('success', nm)]['ipw'].mean())))
        rep += ['## Negative controls', '',
                '- association, NOT a policy value: success of episodes that reached a second decision minus those that validated at once = %.4f (escalation is triggered by failure, so "escalated" episodes are the hard ones)' % esc_vs_not,
                '- randomized stage-1 contrast among episodes that reached it (large minus small at t=1; valid because assignment there is a coin flip): %.4f' % naive,
                '- IPW with a deliberately WRONG constant propensity (0.8 for large) vs the recorded 0.5: ' + '; '.join('%s %.4f vs %.4f' % w for w in wrong), '']
        (out / 'report_ope.md').write_text('\n'.join(rep)); print('\n'.join(rep))

    if a.calibration:
        live, live_info = read(base / 'live' / 'episodes.jsonl', cfg); n_err_l = live_info['n_itt_scored']; rows = []; live_task = {}
        calls_log = sum(e['n_decisions'] for e in conf)
        for outcome in ('utility', 'success'):
            for nm in sorted({e['policy'] for e in live}):
                le = [e for e in live if e['policy'] == nm]
                lt, lv = EA.cluster_means(np.array([e['task_uid'] for e in le], object), np.array([e[outcome] for e in le], float))
                live_task[(outcome, nm)] = pd.Series(lv, index=lt)
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
        lrows = []
        for outcome in ('utility', 'success'):
            b0 = live_task.get((outcome, P.BASELINE))
            for nm in sorted({e['policy'] for e in live}):
                if nm == P.BASELINE or b0 is None:
                    continue
                cm = np.intersect1d(live_task[(outcome, nm)].index, b0.index)
                dl = EA.summary((live_task[(outcome, nm)][cm] - b0[cm]).to_numpy())
                o = con[(con.outcome == outcome) & (con.contrast == '%s - %s' % (nm, P.BASELINE))].iloc[0]
                lrows.append(dict(outcome=outcome, contrast='%s - %s' % (nm, P.BASELINE), live=dl['estimate'], live_se=dl['se'], live_lower=dl['lower'], live_upper=dl['upper'],
                                  ope=o['estimate'], ope_lower_bonferroni=o['lower_bonferroni'], ope_upper_bonferroni=o['upper_bonferroni'], sign_agrees=bool(np.sign(dl['estimate']) == np.sign(o['estimate'])),
                                  improvement_claimed=bool(o['lower_bonferroni'] > 0 and dl['estimate'] > 0)))
        lcon = pd.DataFrame(lrows); lcon.to_csv(out / 'live_contrasts_vs_baseline.csv', index=False)
        rep = ['# Code-routing: OPE vs fresh live executions (CONFIRM tasks)', '', tag + 'live episodes scored intention-to-treat after exhausting retries: %d' % n_err_l, '',
               '## A2 decision rule: improvement is claimed only if the Bonferroni OPE interval excludes 0 AND the live contrast agrees in sign', '', lcon.round(4).to_markdown(index=False), '',
               cal.round(4).to_markdown(index=False), '', 'Spearman rank agreement of policy utilities, OPE vs live: %.3f' % rank, '',
               'Evaluation cost: ONE randomized log of %d model calls supports every policy above; the live arm spent %d calls in total (%d policies).' % (
                   calls_log, int(u['live_model_calls'].sum()), len(u)), '']
        (out / 'report_calibration.md').write_text('\n'.join(rep)); print('\n'.join(rep))

    if a.ops:
        rows = []
        for stage in ('pilot', 'log', 'live', 'branch'):
            pth = base / stage / 'episodes.jsonl'
            if not pth.exists():
                continue
            recs, info = read(pth, cfg)
            for busy in (False, True):
                g = [r for r in recs if bool(r.get('foreign_gpu_load_at_start')) == busy and not r.get('itt_scored')]
                if not g:
                    continue
                dec = [d for r in g for d in r['decisions'] if d.get('completed', True)]
                rows.append(dict(stage=stage, foreign_gpu_load=busy, episodes=len(g), validation_timeouts=sum(r.get('validation_timeouts', 0) for r in g),
                                 hidden_test_timeouts=sum(bool(r.get('verify_timed_out')) for r in g), truncated_generations=sum(d.get('finish') == 'length' for d in dec),
                                 median_wall_s_small=float(np.median([d['wall_seconds'] for d in dec if d['a'] == 0] or [np.nan])),
                                 median_wall_s_large=float(np.median([d['wall_seconds'] for d in dec if d['a'] == 1] or [np.nan])),
                                 error_attempts_in_stage=info['n_error_attempts'], itt_scored_in_stage=info['n_itt_scored']))
        ops = pd.DataFrame(rows); ops.to_csv(out / 'ops_by_contention.csv', index=False)
        txt = ['# Operations by contention status', '', tag + 'Latency is interpretable only in the foreign_gpu_load=False rows. Timeouts are the one timing-dependent path into an outcome.', '', ops.round(3).to_markdown(index=False) if len(ops) else '_no stage has run_', '']
        (out / 'report_ops.md').write_text('\n'.join(txt)); print('\n'.join(txt))

    if a.branch:
        br, br_info = read(base / 'branch' / 'episodes.jsonl', cfg); n_err_b = br_info['n_itt_scored']
        df = pd.DataFrame([dict(parent=e['parent_episode_id'], task=e['task_uid'], arm=e['fork_arm'], run=e['run'], success=e['success'],
                                hash_ok=e['restoration']['transcript_hash_matches'], tool_ok=e['restoration']['tool_result_reproduced']) for e in br])
        per = df.pivot_table(index=['task', 'parent'], columns='arm', values='success', aggfunc='mean').reset_index()
        n_pref = len(per); per = per.dropna(subset=['large', 'small']).reset_index(drop=True); n_incomplete = n_pref - len(per)
        per['d'] = per['large'] - per['small']

        def cluster_se(x, task):                       # prefixes are the units of the target; tasks are the independent clusters
            c = pd.Series(x - x.mean()).groupby(task.to_numpy()).sum()
            return float(np.sqrt((c ** 2).sum()) / len(x))
        est, se = float(per['d'].mean()), cluster_se(per['d'].to_numpy(), per['task'])
        runs = df.pivot_table(index=['parent', 'arm'], columns='run', values='success').dropna()
        disagree = float((runs[0] != runs[1]).mean())   # same state, same model, fresh seed: serving/sampling noise floor
        # the same contrast from the randomized log: prefix population = confirm episodes whose first validation failed
        lp = pd.DataFrame([dict(task=e['task_uid'], success=e['success'], a1=e['decisions'][1]['a'],
                                a2=(e['decisions'][2]['a'] if len(e['decisions']) > 2 else None)) for e in conf if e['n_decisions'] >= 2])

        def log_contrast(x):
            v = {}
            for arm in (0, 1):
                w = (x.a1 == arm) / 0.5 * np.where(x.a2.isna(), 1.0, (x.a2 == arm) / 0.5)
                v[arm] = float((w * x.success).sum() / w.sum()) if w.sum() > 0 else np.nan
            return v[1] - v[0]
        rng = np.random.default_rng(0); groups = [g for _, g in lp.groupby('task')]
        boot = [log_contrast(pd.concat([groups[i] for i in rng.integers(0, len(groups), len(groups))])) for _ in range(500)]
        lc, lse = log_contrast(lp), float(np.nanstd(boot, ddof=1))
        diff, dse = est - lc, float(np.sqrt(se ** 2 + lse ** 2))   # treated as independent: branch outcomes use fresh seeds; conservative if positively dependent through shared prefixes
        rep = ['# Code-routing: branch audit (restored first-failure prefixes, CONFIRM tasks)', '', tag + 'branch infrastructure errors excluded: %d' % n_err_b, '',
               '| quantity | value |', '|---|---|',
               '| prefixes with both arms / tasks (prefixes dropped for a missing arm: %d) | %d / %d |' % (n_incomplete, len(per), per['task'].nunique()),
               '| restoration: transcript hash matches | %d / %d |' % (int(df.hash_ok.sum()), len(df)),
               '| restoration: tool result reproduced | %d / %d |' % (int(df.tool_ok.sum()), len(df)),
               '| same-state same-model disagreement between two fresh continuations | %.3f |' % disagree,
               '| branch contrast, stay-large minus stay-small (success) | %.4f (task-cluster SE %.4f) |' % (est, se),
               '| same contrast from the randomized log (Hajek IPW, task bootstrap SE) | %.4f (SE %.4f) |' % (lc, lse),
               '| branch minus log | %.4f (SE %.4f), 95%% interval [%.4f, %.4f] |' % (diff, dse, diff - 1.96 * dse, diff + 1.96 * dse), '',
               'Target: mean continuation effect over the first-failure prefix population reached under the randomized logger. It is NOT the value of any policy that changes how prefixes are reached (protocol section 5).', '']
        (out / 'report_branch.md').write_text('\n'.join(rep)); print('\n'.join(rep))


if __name__ == '__main__':
    main()
