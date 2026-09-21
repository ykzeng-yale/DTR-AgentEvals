"""DTR-REQ-003 P0: bounded CPU development batch, IPW versus fresh (experiment_protocol_v2.md section 7, lead 72a771d).

Specification (verbatim scope): the existing common-first-small repair generator, K = 2, crossing effects, informative and
weak feedback, each with the uniform-floor-.5 and feedback-dependent-floor-.2 logger (four existing cells); the frozen
250-task balanced list; 4 logged repetitions per task and 4 independent fresh repetitions per task and policy; policies
history_large_after_exception, prompt_only_large_if_hard and the exact-table best fixed schedule (KNOWN-KERNEL SELECTED,
not learned); exactly 200 complete repetitions per cell; root seed 2026092101; stable namespaces
cfg|rep|role|policy|task|replicate; CPU wall-time cap 15 minutes. No branch execution, no model calls, no GPU.

  python dev_batch.py freeze     write the manifest (code and truth-source hashes) - committed BEFORE the batch
  python dev_batch.py run        run the batch against the committed manifest (refuses if any hashed file changed);
                                 appends one JSON line per complete (cell, repetition) to reps.jsonl
  python dev_batch.py analyze    summary.json / summary.md: exact truth, bias with MCSE, RMSE, empirical SD versus the
                                 accepted exact SD, mean IPW-minus-fresh discrepancy with MCSE, costs, counts
Development wiring check only: no interval coverage, adaptation benefit or resource-efficiency claim.
"""
from __future__ import annotations
import hashlib, json, math, sys, time
from multiprocessing import Pool
from pathlib import Path

import fixed_task_blocks as B
import repair_generator as G
import repair_logger as L
import sampler as S

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / 'results' / 'v2_sim' / 'dev_batch_20260921'
MANIFEST = OUT / 'manifest.json'
REPS = OUT / 'reps.jsonl'
ROOT_SEED, R_REPS, R_LOG, R_FRESH, N_TASKS, CAP_S, WORKERS = 2026092101, 200, 4, 4, 250, 15 * 60, 4
FEEDBACK = ('informative', 'weak')
LOGGERS = ('uniform_floor_0.5', 'feedback_dependent_floor_0.2')
HASHED = ['experiments/v2_sim/dev_batch.py', 'experiments/v2_sim/sampler.py', 'experiments/v2_sim/repair_generator.py',
          'experiments/v2_sim/repair_logger.py', 'experiments/v2_sim/fixed_task_blocks.py',
          'experiments/v2_sim/repair_generator_v1.json', 'experiments/v2_sim/fixed_task_blocks_v1.json',
          'experiments/v2_sim/fresh_reference_v1.json']


def sha(rel):
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def cells():
    kernel = json.loads(G.OUT.read_text())
    out = []
    for fb in FEEDBACK:
        kc = next(c for c in kernel['cells'] if (c['K'], c['action_effect'], c['feedback']) == (2, 'crossing', fb))
        for lg in LOGGERS:
            out.append(dict(config='K2-crossing-%s-%s' % (fb, lg), feedback=fb, logger=lg,
                            policies=['history_large_after_exception', 'prompt_only_large_if_hard', kc['best_fixed']['policy']],
                            best_fixed_label='known-kernel selected (exact table), not learned'))
    return out


def freeze():
    tasks, digest = B.task_list(N_TASKS)
    m = dict(request='DTR-REQ-003 P0 bounded CPU development batch (experiment_protocol_v2.md section 7, lead 72a771d)',
             root_seed=ROOT_SEED, repetitions_per_cell=R_REPS, logged_per_task=R_LOG, fresh_per_task_policy=R_FRESH,
             task_list=dict(n=N_TASKS, sha256=digest, rule="task g = 't%04d' % g, stratum = g mod 2"),
             cells=cells(), cpu_wall_cap_seconds=CAP_S, workers=WORKERS,
             stream_namespace="cfg=<config>|rep=<b>|<log|fresh>|<logger name or policy>|<task>|<replicate>",
             draw_source='sampler.SeededDraws: numpy SeedSequence(root_seed, spawn_key=sha256(stream)[:16] as 4 uint32)',
             estimators=['ipw_estimate (trajectory IPW of utility, shared log per repetition)', 'fresh_estimate'],
             outputs=['reps.jsonl', 'summary.json', 'summary.md'],
             not_claimed=['interval coverage', 'adaptation benefit', 'resource efficiency', 'real-agent evidence'],
             source_sha256={rel: sha(rel) for rel in HASHED})
    OUT.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=1) + '\n')
    return m


def job(arg):
    cell_spec, b = arg
    t0 = time.process_time()
    cell = G.Cell(2, 'crossing', cell_spec['feedback'])
    tasks, _ = B.task_list(N_TASKS)
    cat = {p.name: p for p in G.catalog(2)}
    ns = S.stream_namespace(cell_spec['config'], b)
    draws = S.SeededDraws(ROOT_SEED)
    log = S.run_blocks(tasks, cell, R_LOG, draws, ns, 'log', logger=L.LOGGERS[cell_spec['logger']],
                       logger_name=cell_spec['logger'])
    rec = dict(config=cell_spec['config'], repetition=b, namespace=ns, policies={},
               log_mean_cost=float(sum(e['cost'] for e in log) / len(log)), log_episodes=len(log))
    for name in cell_spec['policies']:
        fresh = S.run_blocks(tasks, cell, R_FRESH, draws, ns, 'fresh', policy=cat[name])
        rec['policies'][name] = dict(ipw=float(S.ipw_estimate(log, cat[name], tasks, R_LOG)),
                                     fresh=float(S.fresh_estimate(fresh, tasks, R_FRESH)),
                                     fresh_mean_cost=float(sum(e['cost'] for e in fresh) / len(fresh)),
                                     fresh_episodes=len(fresh))
    rec['cpu_seconds'] = time.process_time() - t0
    return rec


def run():
    m = json.loads(MANIFEST.read_text())
    changed = [rel for rel, h in m['source_sha256'].items() if sha(rel) != h]
    if changed:
        raise SystemExit('refusing to run: files changed since the manifest was frozen: %s' % changed)
    done = set()
    if REPS.exists():
        done = {(r['config'], r['repetition']) for r in map(json.loads, REPS.read_text().splitlines())}
    todo = [(c, b) for b in range(R_REPS) for c in m['cells'] if (c['config'], b) not in done]
    start, completed, stopped = time.time(), 0, False
    with Pool(WORKERS) as pool, REPS.open('a') as fh:
        it = pool.imap_unordered(job, todo, chunksize=1)
        for rec in it:
            rec['wall_seconds_since_start'] = time.time() - start
            fh.write(json.dumps(rec) + '\n'); fh.flush()
            completed += 1
            if time.time() - start > CAP_S:
                stopped = True
                pool.terminate()
                break
    (OUT / 'run_status.json').write_text(json.dumps(dict(
        wall_seconds=time.time() - start, completed_this_invocation=completed, jobs_requested=len(todo),
        stopped_by_cap=stopped, workers=WORKERS), indent=1) + '\n')
    print('completed %d of %d jobs in %.1f s%s' % (completed, len(todo), time.time() - start, ' (CAP REACHED)' if stopped else ''))


def analyze():
    m = json.loads(MANIFEST.read_text())
    reps = [json.loads(x) for x in REPS.read_text().splitlines()]
    kernel = json.loads(G.OUT.read_text())
    ftb = json.loads(B.OUT.read_text())
    fref = json.loads((HERE / 'fresh_reference_v1.json').read_text())
    rows = []
    for c in m['cells']:
        rs = [r for r in reps if r['config'] == c['config']]
        keys = sorted({r['repetition'] for r in rs})
        if len(keys) != len(rs):
            raise SystemExit('duplicate repetition records for %s' % c['config'])
        kc = next(k for k in kernel['cells'] if (k['K'], k['action_effect'], k['feedback']) == (2, 'crossing', c['feedback']))
        for name in c['policies']:
            truth = float(G.Fr(kc['policies'][name]['utility']['exact']))
            ipw = [r['policies'][name]['ipw'] for r in rs]
            fresh = [r['policies'][name]['fresh'] for r in rs]
            ex_ipw_sd = next(x['exact_se_V_hat'] for x in ftb['rows'] if (x['K'], x['action_effect'], x['feedback'],
                             x['logger'], x['n'], x['policy']) == (2, 'crossing', c['feedback'], c['logger'], N_TASKS, name))
            ex_fresh_sd = next(x['n250']['fresh_se'] for x in fref['rows'] if (x['K'], x['action_effect'], x['feedback'],
                               x['policy']) == (2, 'crossing', c['feedback'], name))
            R = len(rs)

            def stats(v):
                mean = sum(v) / R
                sd = math.sqrt(sum((x - mean) ** 2 for x in v) / (R - 1)) if R > 1 else float('nan')
                return mean, sd
            bias, sd_err = stats([x - truth for x in ipw])
            fbias, fsd_err = stats([x - truth for x in fresh])
            disc, sd_disc = stats([a - b for a, b in zip(ipw, fresh)])
            rows.append(dict(
                config=c['config'], policy=name, policy_label=(c['best_fixed_label'] if name.startswith('fixed_') else 'frozen rule'),
                repetitions_complete=R, exact_truth=truth,
                ipw=dict(bias=bias, bias_mcse=sd_err / math.sqrt(R), rmse=math.sqrt(sum((x - truth) ** 2 for x in ipw) / R),
                         empirical_sd=stats(ipw)[1], exact_sd=ex_ipw_sd),
                fresh=dict(bias=fbias, bias_mcse=fsd_err / math.sqrt(R), rmse=math.sqrt(sum((x - truth) ** 2 for x in fresh) / R),
                           empirical_sd=stats(fresh)[1], exact_sd=ex_fresh_sd),
                ipw_minus_fresh=dict(mean=disc, mcse=sd_disc / math.sqrt(R)),
                mean_cost_per_episode=dict(log=sum(r['log_mean_cost'] for r in rs) / R,
                                           fresh=sum(r['policies'][name]['fresh_mean_cost'] for r in rs) / R)))
    status = json.loads((OUT / 'run_status.json').read_text()) if (OUT / 'run_status.json').exists() else {}
    summary = dict(manifest_sha256=hashlib.sha256(MANIFEST.read_bytes()).hexdigest(), reps_sha256=hashlib.sha256(REPS.read_bytes()).hexdigest(),
                   root_seed=m['root_seed'], repetitions_requested_per_cell=m['repetitions_per_cell'],
                   complete_repetitions_per_cell={c['config']: sum(r['config'] == c['config'] for r in reps) for c in m['cells']},
                   failed_or_missing_per_cell={c['config']: m['repetitions_per_cell'] - sum(r['config'] == c['config'] for r in reps)
                                               for c in m['cells']},
                   total_cpu_seconds=sum(r['cpu_seconds'] for r in reps), run_status=status, rows=rows,
                   not_claimed=m['not_claimed'])
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    lines = ['# Development batch: IPW versus fresh, K=2 crossing cells (DTR-REQ-003 P0)', '',
             'Root seed %d; %s complete repetitions per cell; manifest `%s`. Wiring check only: no coverage, adaptation or '
             'efficiency claim. Truth and exact SDs are the accepted exact artifacts.' % (
                 m['root_seed'], sorted(set(summary['complete_repetitions_per_cell'].values())), summary['manifest_sha256'][:12]), '',
             '| Cell | Policy | Truth | IPW bias (MCSE) | IPW RMSE | IPW SD emp / exact | Fresh bias (MCSE) | Fresh SD emp / exact | IPW - fresh (MCSE) |',
             '|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        i, f, d = r['ipw'], r['fresh'], r['ipw_minus_fresh']
        lines.append('| %s | %s | %.5f | %+.5f (%.5f) | %.5f | %.5f / %.5f | %+.5f (%.5f) | %.5f / %.5f | %+.5f (%.5f) |' % (
            r['config'].replace('K2-crossing-', ''), r['policy'], r['exact_truth'], i['bias'], i['bias_mcse'], i['rmse'],
            i['empirical_sd'], i['exact_sd'], f['bias'], f['bias_mcse'], f['empirical_sd'], f['exact_sd'], d['mean'], d['mcse']))
    (OUT / 'summary.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    {'freeze': freeze, 'run': run, 'analyze': analyze}[sys.argv[1]]()
