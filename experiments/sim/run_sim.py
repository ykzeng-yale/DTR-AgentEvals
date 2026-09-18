"""E0: simulation study with known ground truth (CPU only, no model calls).

Studies (all use the generator in synth_agent.py):
  S1 validity    bias / RMSE of IPW and AIPW for the 12 embedded regimes, and
                 cluster-bootstrap CI coverage for two of them.
  S2 design      SMART with n episodes vs the conventional "one arm per
                 scaffold" evaluation that splits the same n episodes across
                 the 12 regimes: RMSE of each regime's value, probability of
                 selecting the truly best embedded regime, regret of the pick.
  S3 learning    true value of the Q-learned TAILORED regime vs the best
                 embedded regime picked from the same data, vs oracle.
  S4 forking     precision of the stage-2 contrast E[U(escalate)-U(repair)|R=0]
                 from randomised SMART vs forked replay (all feasible arms run
                 from the same saved state) at EQUAL COMPUTE.

Usage:  python run_sim.py --reps 1000 --workers 4 --out ../../results/sim
Every output is written with a manifest (seed, args, code sha256).
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'dtr'))
import synth_agent as S  # noqa: E402
import estimators as E  # noqa: E402

REG_KEYS = [(a1, ap, af) for a1 in S.A1_SET for ap in S.FEASIBLE[1] for af in S.FEASIBLE[0]]
REGS = {k: E.static_regime(k[0], {1: k[1], 0: k[2]}) for k in REG_KEYS}
NS = [300, 600, 1200, 2400, 4800]
REPS_PER_TASK = 2
TRUTH_N = 400_000
EVAL_N = 60_000  # per-replicate true-value evaluation of learned regimes


def _truth():
    return {k: S.true_value(r, n_tasks=TRUTH_N) for k, r in REGS.items()}


def _mean_cost_smart():
    d = S.simulate(200_000, 1, 99)
    c_smart = d['cost'].mean()
    base = d['cost'] - d['A2'].map(S.COST_A2)
    allarms = np.where(d['R'] == 1, sum(S.COST_A2[a] for a in S.FEASIBLE[1]), sum(S.COST_A2[a] for a in S.FEASIBLE[0]))
    return float(c_smart), float((base + allarms).mean())


def one_rep(args):
    rep, n, truth, do_ci, c_smart, c_fork = args
    seed = 1_000_003 * n + rep
    n_tasks = n // REPS_PER_TASK
    sm = S.simulate(n_tasks, REPS_PER_TASK, seed)
    out = {'rep': rep, 'n': n}
    # ---- S1 / S2: embedded regimes
    ipw = {k: E.ipw_value(sm, REGS[k]) for k in REG_KEYS}
    aipw = {k: E.aipw_value(sm, REGS[k], S.H1_COLS, S.H2_COLS, seed=seed) for k in REG_KEYS}
    # conventional: split n episodes equally across the 12 regimes, run each on-policy
    per = max(n // len(REG_KEYS), 2)
    conv = {}
    for j, k in enumerate(REG_KEYS):
        d = S.simulate(max(per // REPS_PER_TASK, 1), REPS_PER_TASK, seed * 13 + j, regime=REGS[k])
        conv[k] = float(d['Y'].mean())
    best_true = max(truth, key=truth.get)
    for name, est in (('ipw', ipw), ('aipw', aipw), ('conv', conv)):
        for k in REG_KEYS:
            out['%s_%d%d%d' % ((name,) + k)] = est[k]
        pick = max(est, key=lambda kk: (est[kk] if est[kk] == est[kk] else -9))
        out[name + '_pick_correct'] = int(pick == best_true)
        out[name + '_pick_regret'] = truth[best_true] - truth[pick]
    # ---- S1 CI coverage (subset of reps; two regimes)
    if do_ci:
        for k in (best_true, (0, 0, 2)):
            tag = '%d%d%d' % k
            lo, hi, _ = E.cluster_bootstrap(sm, lambda d: E.ipw_value(d, REGS[k]), B=200, seed=seed)
            out['ci_ipw_cover_' + tag] = int(lo <= truth[k] <= hi); out['ci_ipw_len_' + tag] = hi - lo
            lo, hi, _ = E.cluster_bootstrap(sm, lambda d: E.aipw_value(d, REGS[k], S.H1_COLS, S.H2_COLS, seed=1), B=200, seed=seed)
            out['ci_aipw_cover_' + tag] = int(lo <= truth[k] <= hi); out['ci_aipw_len_' + tag] = hi - lo
            # naive iid interval ignoring task clustering, for contrast
            c = E.consistent(sm, REGS[k]); yy = sm['Y'].to_numpy()[c]
            se = yy.std(ddof=1) / np.sqrt(len(yy)); m = yy.mean()
            out['ci_naive_cover_' + tag] = int(m - 1.96 * se <= truth[k] <= m + 1.96 * se)
    # ---- S3: learned tailored regime
    ql = E.q_learning(sm, S.H1_COLS, S.H2_COLS, S.FEASIBLE, S.A1_SET)
    out['v_qlearn'] = S.true_value(ql.regime, n_tasks=EVAL_N, seed=4242)
    out['v_best_embedded_true'] = truth[best_true]
    out['v_aipw_pick'] = truth[max(aipw, key=aipw.get)]
    # ---- S4: forking vs randomisation for a stage-2 contrast, equal compute
    nr = sm[sm['R'] == 0]
    e, r = nr[nr['A2'] == 4]['Y'], nr[nr['A2'] == 2]['Y']
    out['s4_rand'] = float(e.mean() - r.mean()) if len(e) and len(r) else np.nan
    m_tasks = max(int(n * c_smart / c_fork) // REPS_PER_TASK, 2)
    fk = S.simulate(m_tasks, REPS_PER_TASK, seed * 7 + 1, fork=True)
    fnr = fk[fk['R'] == 0]
    out['s4_fork'] = float((fnr['U_4'] - fnr['U_2']).mean()) if len(fnr) else np.nan
    out['s4_fork_episodes'] = m_tasks * REPS_PER_TASK
    # stage-2 rule learned from forked data (all arms labelled) at equal compute
    rows = []
    for a in S.A2_NAMES:
        t = fk[['cluster', 'x', 'A1', 'P1', 'R', 'O_exc', 'frac']].copy()
        t['A2'] = a; t['P2'] = 1.0; t['Y'] = fk['U_%d' % a]
        rows.append(t.dropna(subset=['Y']))
    qf = E.q_learning(pd.concat(rows, ignore_index=True), S.H1_COLS, S.H2_COLS, S.FEASIBLE, S.A1_SET)
    out['v_qlearn_fork'] = S.true_value(qf.regime, n_tasks=EVAL_N, seed=4242)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--reps', type=int, default=1000)
    ap.add_argument('--ci-reps', type=int, default=200)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--out', default=str(HERE.parent.parent / 'results' / 'sim'))
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    truth = _truth()
    c_smart, c_fork = _mean_cost_smart()
    oracle_v = S.true_value(S.oracle_regime(), n_tasks=TRUTH_N)
    nr = S.simulate(TRUTH_N, 1, 5, fork=True); nr = nr[nr['R'] == 0]
    s4_truth = float((nr['U_4'] - nr['U_2']).mean())
    jobs = [(rep, n, truth, rep < a.ci_reps and n in (600, 2400), c_smart, c_fork) for n in NS for rep in range(a.reps)]
    with ProcessPoolExecutor(max_workers=a.workers) as ex:
        rows = list(ex.map(one_rep, jobs, chunksize=8))
    df = pd.DataFrame(rows)
    df.to_csv(out / 'replicates.csv', index=False)
    code = b''.join((HERE / f).read_bytes() for f in ('run_sim.py', 'synth_agent.py')) + (HERE.parent / 'dtr' / 'estimators.py').read_bytes()
    manifest = dict(args=vars(a), ns=NS, reps_per_task=REPS_PER_TASK, truth={'%d%d%d' % k: v for k, v in truth.items()},
                    oracle_value=oracle_v, s4_truth=s4_truth, mean_cost_smart=c_smart, mean_cost_fork=c_fork,
                    code_sha256=hashlib.sha256(code).hexdigest(), seconds=round(time.time() - t0, 1),
                    finished_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=1))
    print(json.dumps({k: manifest[k] for k in ('oracle_value', 's4_truth', 'mean_cost_smart', 'mean_cost_fork', 'seconds')}))


if __name__ == '__main__':
    main()
