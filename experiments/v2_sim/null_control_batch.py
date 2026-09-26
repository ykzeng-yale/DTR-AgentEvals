"""DTR-REQ-022 P1 (lead cd90c56, docs/theory_feedback_20260926_req021_decision.md): one bounded CPU DEVELOPMENT
null-control cell for the v2 synthetic evaluation wiring.

Cell: the existing repair generator (repair_generator_v1.json), K = 2, NO-crossing action effect, informative feedback,
logged by the feedback-dependent-floor-0.2 logger (the known weak-overlap setting). Its exact best fixed, best prompt-only
and best observed-history utilities are all 2891/4000 = 0.72275, so the optimal history advantage is exactly zero (an
analytic control). The sampled estimand is each fixed CATALOG policy's task-equal utility on the frozen 250-task list,
estimated by trajectory IPW from a shared log and by independent fresh on-policy runs; a difference between two catalog
policies is not evidence of adaptive value. Adapted from dev_batch.py (which, with its archive
results/v2_sim/dev_batch_20260921/, is left unchanged); the old K = 2 crossing cells are not rerun.

  python null_control_batch.py freeze    write the manifest (source/truth hashes, seed, cell, policies, exact truths and
                                         exact SDs, prespecified checks) - committed BEFORE any sampling
  python null_control_batch.py run       host gates (disk, memory, peers, non-overlap), then the batch against the
                                         committed manifest (refuses if any hashed file changed); 200 repetitions,
                                         4 workers, 15-minute wall cap; one JSON line per complete repetition
  python null_control_batch.py analyze   summary.json / summary.md with the prespecified checks

Development wiring check only: no interval coverage, adaptation benefit, optimality, resource-efficiency or real-agent
claim. No model call, GPU, branch execution or CONFIRM stage.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import fixed_task_blocks as B
import fresh_reference as FR
import repair_generator as G
import repair_logger as L
import sampler as S

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / 'results' / 'v2_sim' / 'null_control_20260926'
REQUEST = 'DTR-REQ-022'
ROOT_SEED, R_REPS, R_LOG, R_FRESH, N_TASKS, CAP_S, WORKERS = 2026092622, 200, 4, 4, 250, 15 * 60, 4
PREVIOUS_SEEDS = (2026092101,)                   # dev_batch_20260921; the new seed must differ
CELL = dict(K=2, action_effect='no_crossing', feedback='informative', logger='feedback_dependent_floor_0.2')
CONFIG = 'K2-no_crossing-informative-feedback_dependent_floor_0.2'
HASHED = ['experiments/v2_sim/null_control_batch.py', 'experiments/v2_sim/sampler.py',
          'experiments/v2_sim/repair_generator.py', 'experiments/v2_sim/repair_logger.py',
          'experiments/v2_sim/fixed_task_blocks.py', 'experiments/v2_sim/fresh_reference.py',
          'experiments/v2_sim/repair_generator_v1.json', 'experiments/v2_sim/fixed_task_blocks_v1.json',
          'experiments/v2_sim/fresh_reference_v1.json']
GATES = dict(host_disk_min_gib=5.0, memory_free_min_pct=50, no_model_server=True, no_other_sim_or_stage_job=True)
CHECK_Z = 3.0


def sha(rel, root=ROOT):
    return hashlib.sha256((root / rel).read_bytes()).hexdigest()


def kernel_cell():
    kernel = json.loads(G.OUT.read_text())
    return next(c for c in kernel['cells']
                if (c['K'], c['action_effect'], c['feedback']) == (CELL['K'], CELL['action_effect'], CELL['feedback']))


def policy_classes():
    out = {}
    for p in G.catalog(CELL['K']):
        out[p.name] = ('fixed' if p.name.startswith('fixed_') else 'prompt_only' if p.name.startswith('prompt_only')
                       else 'history')
    return out


def exact_references():
    """exact truth (kernel) and exact SDs of the IPW and fresh estimators at n = 250, r = 4 for every catalog policy,
    from the existing moment code (fixed_task_blocks.ipw_moments, fresh_reference.on_policy_moments)."""
    cell = G.Cell(CELL['K'], CELL['action_effect'], CELL['feedback'])
    kc = kernel_cell()
    tasks, _ = B.task_list(N_TASKS)
    logger = L.LOGGERS[CELL['logger']]
    out = {}
    for pol in G.catalog(CELL['K']):
        sig2, tau2, V = {}, {}, {}
        for s in (0, 1):
            truth = G.enumerate_value(pol, cell, s)[0]
            V[s] = truth['success'] - truth['cost']
            m1, m2 = B.ipw_moments(pol, cell, s, logger)
            if m1 != V[s]:
                raise AssertionError('IPW first moment differs from truth for %s' % pol.name)
            sig2[s] = m2 - m1 * m1
            f1, f2 = FR.on_policy_moments(pol, cell, s)
            if f1 != V[s]:
                raise AssertionError('on-policy mean differs from truth for %s' % pol.name)
            tau2[s] = f2 - f1 * f1
        theta = sum(V[sg] for _, sg in tasks) / N_TASKS
        if str(theta) != kc['policies'][pol.name]['utility']['exact']:
            raise AssertionError('task-list truth differs from the kernel table for %s' % pol.name)
        ipw_var = sum(sig2[sg] for _, sg in tasks) / (R_LOG * N_TASKS * N_TASKS)
        fresh_var = sum(tau2[sg] for _, sg in tasks) / (R_FRESH * N_TASKS * N_TASKS)
        out[pol.name] = dict(truth_exact=str(theta), truth=float(theta), exact_sd_ipw=float(ipw_var) ** .5,
                             exact_sd_fresh=float(fresh_var) ** .5)
    return out


def freeze(out=OUT):
    if ROOT_SEED in PREVIOUS_SEEDS:
        raise SystemExit('root seed must differ from earlier batches')
    if (out / 'manifest.json').exists():
        raise SystemExit('manifest already frozen at %s; refusing to overwrite' % (out / 'manifest.json'))
    kc = kernel_cell()
    tasks, digest = B.task_list(N_TASKS)
    classes = policy_classes()
    m = dict(
        request=REQUEST + ' P1 null-control DEVELOPMENT cell (lead cd90c56)', config=CONFIG, cell=CELL,
        root_seed=ROOT_SEED, previous_root_seeds=list(PREVIOUS_SEEDS), repetitions=R_REPS, logged_per_task=R_LOG,
        fresh_per_task_policy=R_FRESH, task_list=dict(n=N_TASKS, sha256=digest, rule="task g = 't%04d' % g, stratum = g mod 2"),
        policies=sorted(classes), policy_classes=classes,
        analytic_null=dict(best_fixed=kc['best_fixed'], best_prompt_only_utility=kc['best_prompt_only_utility'],
                           best_observed_history_utility=kc['best_observed_history_utility'],
                           history_advantage_over_best_fixed=kc['history_advantage_over_best_fixed'],
                           history_advantage_over_best_prompt_only=kc['history_advantage_over_best_prompt_only']),
        exact=exact_references(), cpu_wall_cap_seconds=CAP_S, workers=WORKERS, host_gates=GATES,
        stream_namespace="cfg=<config>|rep=<b>|<log|fresh>|<logger name or policy>|<task>|<replicate>",
        draw_source='sampler.SeededDraws: numpy SeedSequence(root_seed, spawn_key=sha256(stream)[:16] as 4 uint32)',
        estimators=['ipw_estimate (trajectory IPW of utility from one shared log per repetition)', 'fresh_estimate'],
        prespecified_checks=dict(
            C1='for every catalog policy and estimator: |mean estimate - exact truth| <= %.0f Monte Carlo SE '
               '(14 checks; about 0.04 flags expected by chance)' % CHECK_Z,
            C2='for each history policy h: contrast V(h) - V(fixed_LL) (exact, negative in this cell) estimated by IPW and '
               'by fresh; |mean - exact| <= %.0f MCSE' % CHECK_Z,
            C3='descriptive only: per repetition, max over history policies minus max over non-history policies of the '
               'estimates (a selected plug-in; biased upward under the null; reported as mean, MCSE and share > 0)',
            C4='overlap: IPW empirical SD versus exact SD per policy, IPW-to-fresh SD ratio, largest trajectory weight; '
               'a material estimator problem is |IPW bias| > 3 MCSE or empirical SD > 1.5 x exact SD'),
        outputs=['gates.json', 'reps.jsonl', 'run_status.json', 'summary.json', 'summary.md'],
        not_claimed=['interval coverage', 'adaptation benefit', 'optimal-policy learning', 'resource efficiency',
                     'real-agent evidence', 'CONFIRM evidence'],
        source_sha256={rel: sha(rel) for rel in HASHED})
    out.mkdir(parents=True, exist_ok=True)
    (out / 'manifest.json').write_text(json.dumps(m, indent=1) + '\n')
    return m


def job(b):
    t0 = time.process_time()
    cell = G.Cell(CELL['K'], CELL['action_effect'], CELL['feedback'])
    tasks, _ = B.task_list(N_TASKS)
    cat = {p.name: p for p in G.catalog(CELL['K'])}
    ns = S.stream_namespace(CONFIG, b)
    draws = S.SeededDraws(ROOT_SEED)
    log = S.run_blocks(tasks, cell, R_LOG, draws, ns, 'log', logger=L.LOGGERS[CELL['logger']], logger_name=CELL['logger'])
    rec = dict(config=CONFIG, repetition=b, namespace=ns, policies={}, log_episodes=len(log),
               log_mean_cost=float(sum(e['cost'] for e in log) / len(log)))
    for name in sorted(cat):
        fresh = S.run_blocks(tasks, cell, R_FRESH, draws, ns, 'fresh', policy=cat[name])
        weights = [float(S.ipw_weight(e, cat[name])) for e in log]
        rec['policies'][name] = dict(ipw=float(S.ipw_estimate(log, cat[name], tasks, R_LOG)),
                                     fresh=float(S.fresh_estimate(fresh, tasks, R_FRESH)),
                                     max_weight=max(weights), nonzero_weight_share=sum(w > 0 for w in weights) / len(weights),
                                     fresh_episodes=len(fresh))
    rec['cpu_seconds'] = time.process_time() - t0
    return rec


def host_gates(root=ROOT):
    free_gib = shutil.disk_usage(str(root)).free / (1 << 30)
    mp = subprocess.run(['memory_pressure'], capture_output=True, text=True).stdout
    m = re.search(r'System-wide memory free percentage:\s*(\d+)%', mp or '')
    mem = int(m.group(1)) if m else None
    ps = subprocess.run(['ps', '-axo', 'pid=,comm=,args='], capture_output=True, text=True).stdout.splitlines()
    me = os.getpid()
    servers = [l for l in ps if 'llama-server' in l or 'mlx_lm' in l or 'ollama' in l]
    sims = [l for l in ps if ('dev_batch' in l or 'coverage_batch' in l or 'run.py --stage' in l or
                              ('null_control_batch.py' in l and str(me) != l.split()[0]))
            and 'grep' not in l and str(me) != l.split()[0]]
    swap = subprocess.run(['sysctl', '-n', 'vm.swapusage'], capture_output=True, text=True).stdout.strip()
    res = dict(measured_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), host_disk_free_gib=round(free_gib, 2),
               memory_free_pct=mem, model_server_processes=len(servers), other_sim_or_stage_processes=len(sims),
               swap=swap, load_average=os.getloadavg(), rules=GATES)
    res['checks'] = dict(disk=free_gib >= GATES['host_disk_min_gib'],
                         memory=mem is not None and mem >= GATES['memory_free_min_pct'],
                         no_model_server=not servers, no_other_sim_or_stage_job=not sims)
    res['passed'] = all(res['checks'].values())
    return res


def run(out=OUT, root=ROOT, gates=None):
    m = json.loads((out / 'manifest.json').read_text())
    changed = [rel for rel, h in m['source_sha256'].items() if sha(rel, root) != h]
    if changed:
        raise SystemExit('refusing to run: files changed since the manifest was frozen: %s' % changed)
    if (out / 'reps.jsonl').exists():
        raise SystemExit('refusing to run: reps.jsonl exists (immutable run directory)')
    g = gates if gates is not None else host_gates(root)
    (out / 'gates.json').write_text(json.dumps(g, indent=1) + '\n')
    if not g['passed']:
        (out / 'run_status.json').write_text(json.dumps(dict(status='BLOCKED', reason='host gate failed',
                                                             checks=g['checks']), indent=1) + '\n')
        raise SystemExit('BLOCKED: host gate failed %s' % g['checks'])
    start, completed, stopped = time.time(), 0, False
    with Pool(WORKERS) as pool, (out / 'reps.jsonl').open('a') as fh:
        for rec in pool.imap_unordered(job, range(R_REPS), chunksize=1):
            rec['wall_seconds_since_start'] = time.time() - start
            fh.write(json.dumps(rec) + '\n'); fh.flush()
            completed += 1
            if time.time() - start > CAP_S:
                stopped = True
                pool.terminate()
                break
    status = dict(status='COMPLETED' if completed == R_REPS and not stopped else 'CAPPED',
                  started_utc=g['measured_utc'], wall_seconds=time.time() - start, completed=completed,
                  requested=R_REPS, stopped_by_cap=stopped, workers=WORKERS)
    (out / 'run_status.json').write_text(json.dumps(status, indent=1) + '\n')
    print(json.dumps(status))
    return status


def _stats(v):
    R = len(v)
    mean = sum(v) / R
    sd = math.sqrt(sum((x - mean) ** 2 for x in v) / (R - 1)) if R > 1 else float('nan')
    return mean, sd, sd / math.sqrt(R)


def analyze(out=OUT):
    m = json.loads((out / 'manifest.json').read_text())
    reps = [json.loads(x) for x in (out / 'reps.jsonl').read_text().splitlines()]
    if len({r['repetition'] for r in reps}) != len(reps):
        raise SystemExit('duplicate repetition records')
    R = len(reps)
    ex = m['exact']
    rows, flags = [], []
    for name in m['policies']:
        truth = ex[name]['truth']
        row = dict(policy=name, policy_class=m['policy_classes'][name], exact_truth=truth,
                   exact_truth_fraction=ex[name]['truth_exact'])
        for est in ('ipw', 'fresh'):
            v = [r['policies'][name][est] for r in reps]
            mean, sd, mcse = _stats(v)
            bias = mean - truth
            row[est] = dict(mean=mean, bias=bias, bias_mcse=mcse, rmse=math.sqrt(sum((x - truth) ** 2 for x in v) / R),
                            empirical_sd=sd, exact_sd=ex[name]['exact_sd_' + est],
                            sd_ratio_empirical_to_exact=sd / ex[name]['exact_sd_' + est],
                            C1_within=abs(bias) <= CHECK_Z * mcse)
            if not row[est]['C1_within']:
                flags.append('C1 %s %s: bias %+.5f, %.1f MCSE' % (name, est, bias, abs(bias) / mcse))
        d, dsd, dmcse = _stats([r['policies'][name]['ipw'] - r['policies'][name]['fresh'] for r in reps])
        row['ipw_minus_fresh'] = dict(mean=d, mcse=dmcse)
        row['max_weight'] = max(r['policies'][name]['max_weight'] for r in reps)
        row['ipw_to_fresh_sd_ratio'] = row['ipw']['empirical_sd'] / row['fresh']['empirical_sd']
        row['C4_material'] = (not row['ipw']['C1_within']) or row['ipw']['sd_ratio_empirical_to_exact'] > 1.5
        if row['C4_material']:
            flags.append('C4 %s: IPW SD %.2f x exact, bias within: %s' % (
                name, row['ipw']['sd_ratio_empirical_to_exact'], row['ipw']['C1_within']))
        rows.append(row)
    contrasts = []
    for h in [p for p in m['policies'] if m['policy_classes'][p] == 'history']:
        exact_c = ex[h]['truth'] - ex['fixed_LL']['truth']
        c = dict(history_policy=h, versus='fixed_LL', exact=exact_c)
        for est in ('ipw', 'fresh'):
            mean, sd, mcse = _stats([r['policies'][h][est] - r['policies']['fixed_LL'][est] for r in reps])
            c[est] = dict(mean=mean, bias=mean - exact_c, mcse=mcse, C2_within=abs(mean - exact_c) <= CHECK_Z * mcse)
            if not c[est]['C2_within']:
                flags.append('C2 %s-fixed_LL %s: bias %+.5f' % (h, est, mean - exact_c))
        contrasts.append(c)
    hist = [p for p in m['policies'] if m['policy_classes'][p] == 'history']
    other = [p for p in m['policies'] if m['policy_classes'][p] != 'history']
    selected = {}
    for est in ('ipw', 'fresh'):
        v = [max(r['policies'][p][est] for p in hist) - max(r['policies'][p][est] for p in other) for r in reps]
        mean, sd, mcse = _stats(v)
        selected[est] = dict(mean=mean, mcse=mcse, share_positive=sum(x > 0 for x in v) / R,
                             exact_catalog_value=max(ex[p]['truth'] for p in hist) - max(ex[p]['truth'] for p in other))
    status = json.loads((out / 'run_status.json').read_text())
    summary = dict(
        request=REQUEST, manifest_sha256=hashlib.sha256((out / 'manifest.json').read_bytes()).hexdigest(),
        reps_sha256=hashlib.sha256((out / 'reps.jsonl').read_bytes()).hexdigest(), root_seed=m['root_seed'],
        repetitions_requested=m['repetitions'], repetitions_complete=R, repetitions_missing=m['repetitions'] - R,
        total_cpu_seconds=sum(r['cpu_seconds'] for r in reps), run_status=status,
        analytic_null=m['analytic_null'], rows=rows, contrasts_versus_best_fixed=contrasts,
        C3_selected_plugin_advantage=selected, flags=flags, n_checks=dict(C1=2 * len(rows), C2=2 * len(contrasts)),
        not_claimed=m['not_claimed'])
    (out / 'summary.json').write_text(json.dumps(summary, indent=1) + '\n')
    lines = ['# DTR-REQ-022 null-control DEVELOPMENT cell: %s' % CONFIG, '',
             'Root seed %d; %d of %d repetitions complete; manifest `%s`. Wiring check only: no coverage, adaptation, '
             'optimality or real-agent claim. Exact truths and SDs are the accepted exact computations.' % (
                 m['root_seed'], R, m['repetitions'], summary['manifest_sha256'][:12]), '',
             '| Policy | Class | Truth | IPW bias (MCSE) | IPW RMSE | IPW SD emp / exact | Fresh bias (MCSE) | Fresh SD emp / exact | max weight |',
             '|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        i, f = r['ipw'], r['fresh']
        lines.append('| %s | %s | %.5f | %+.5f (%.5f) | %.5f | %.5f / %.5f | %+.5f (%.5f) | %.5f / %.5f | %.2f |' % (
            r['policy'], r['policy_class'], r['exact_truth'], i['bias'], i['bias_mcse'], i['rmse'], i['empirical_sd'],
            i['exact_sd'], f['bias'], f['bias_mcse'], f['empirical_sd'], f['exact_sd'], r['max_weight']))
    lines += ['', 'Flags: %s' % ('; '.join(flags) if flags else 'none')]
    (out / 'summary.md').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    return summary


if __name__ == '__main__':
    {'freeze': freeze, 'run': run, 'analyze': analyze}[sys.argv[1]]()
