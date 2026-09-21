"""DTR-REQ-003: bounded deterministic replay integrity check (lead 75017a7, 17:49 cycle).

Replays EXACTLY repetitions 0, 1 (controls chosen by index, not outcome) and 933 of the weak-feedback / .2-logger cell,
fixed_LS FRESH streams, with the original root seed 2026092103 and namespaces, all 250 fixed tasks x 16 replicates, and
the nested first-4 block. These are identical replays of saved streams: no new seed, no new episodes, no model, no GPU.
Checks per repetition:
  - regenerated fresh mean and within-block variance (r=16 and first-4) against the committed reps.jsonl, |diff| <= 1e-12;
  - manifest counts and unique (task, replicate) keys; every stream id unique, with the expected namespace, role,
    policy, task and replicate fields; SeedSequence spawn keys unique (identifier uniqueness does NOT prove stochastic
    independence);
  - utility == success - cost and cost == sum of call costs on every episode (exact Fractions);
  - success, cost and utility totals and exit classes by task stratum, beside exact per-stratum expectations
    (exhaustive enumeration of one on-policy episode; context only);
  - distribution of task-level contributions (task mean minus its stratum's exact expectation, / n) to the error.
On mismatch the first divergent component is recorded and the artifact is still written (nothing is rerun).
Repetition 933 stays in every published statistic. Agreement supports integrity of these streams only.
  python replay_integrity.py
"""
from __future__ import annotations
import hashlib, json, math
from fractions import Fraction as Fr

import dev_batch as D
import fixed_task_blocks as B
import repair_generator as G
import replication_sensitivity as R
import sampler as S

OUT = D.ROOT / 'results' / 'v2_sim' / 'replay_integrity_20260921'
CONFIG = 'rs-K2-crossing-weak-feedback_dependent_floor_0.2'
POLICY, REPS, TOL = 'fixed_LS', (0, 1, 933), 1e-12
HASHED = ['experiments/v2_sim/replay_integrity.py', 'experiments/v2_sim/replication_sensitivity.py', 'experiments/v2_sim/sampler.py',
          'experiments/v2_sim/repair_generator.py', 'experiments/v2_sim/repair_logger.py', 'experiments/v2_sim/fixed_task_blocks.py',
          'experiments/v2_sim/dev_batch.py', 'experiments/v2_sim/coverage_batch.py', 'experiments/v2_sim/writer_lock.py',
          'experiments/v2_sim/repair_generator_v1.json', 'experiments/v2_sim/fixed_task_blocks_v1.json',
          'experiments/v2_sim/fresh_reference_v1.json', 'results/v2_sim/replication_sensitivity_20260921/manifest.json',
          'results/v2_sim/replication_sensitivity_20260921/reps.jsonl']


def spawn_key(stream):
    h = hashlib.sha256(stream.encode()).digest()
    return tuple(int.from_bytes(h[i:i + 4], 'little') for i in range(0, 16, 4))


def check_streams(episodes, ns, policy_name, tasks, r):
    """Stream-identifier checks: unique ids and spawn keys; each id = <ns>|fresh|<policy>|<task>|<replicate> matching the
    record's own task and replicate. Returns a list of problems (empty if none)."""
    problems = []
    ids = [e['stream'] for e in episodes]
    if len(set(ids)) != len(ids):
        problems.append('duplicate stream ids: %d' % (len(ids) - len(set(ids))))
    keys = [spawn_key(s) for s in ids]
    if len(set(keys)) != len(keys):
        problems.append('duplicate spawn keys')
    strata = dict(tasks)
    for e in episodes:
        want = '%s|fresh|%s|%s|%d' % (ns, policy_name, e['task_id'], e['replicate'])
        if e['stream'] != want:
            problems.append('bad stream id %r (expected %r)' % (e['stream'], want)); break
        if strata.get(e['task_id']) != e['stratum']:
            problems.append('stratum mismatch for %s' % e['task_id']); break
    keyset = {(e['task_id'], e['replicate']) for e in episodes}
    if keyset != {(t, j) for t, _ in tasks for j in range(r)} or len(keyset) != len(episodes):
        problems.append('manifest keys are not exactly tasks x replicates')
    return problems


def check_utility(episodes):
    """utility == success - cost and cost == sum(call_costs), exactly; returns the number of violations."""
    return sum(1 for e in episodes if e['utility'] != e['success'] - e['cost'] or e['cost'] != sum(e['call_costs']))


def stratum_expectations(cell, pol):
    out = {}
    for s in (0, 1):
        br = list(S.exhaustive(lambda d, s=s: S.run_episode(cell, s, d, 'x', policy=pol)))
        m = {k: sum(p * e[k] for p, e in br) for k in ('success', 'cost', 'utility')}
        m['utility_var'] = sum(p * e['utility'] ** 2 for p, e in br) - m['utility'] ** 2
        out[s] = m
    return out


def f(x):
    return float(x)


def replay_one(b, cell, pol, tasks, committed, expect):
    ns = S.stream_namespace(CONFIG, b)
    eps = S.run_blocks(tasks, cell, R.R_BIG, S.SeededDraws(R.ROOT_SEED), ns, 'fresh', policy=pol)
    first4 = [e for e in eps if e['replicate'] < R.R_SMALL]
    regen = {'16': dict(fresh=S.fresh_estimate(eps, tasks, R.R_BIG),
                        fresh_var=S.within_block_variance(eps, lambda e: e['utility'], tasks, R.R_BIG)),
             '4': dict(fresh=S.fresh_estimate(first4, tasks, R.R_SMALL),
                       fresh_var=S.within_block_variance(first4, lambda e: e['utility'], tasks, R.R_SMALL))}
    comparisons, first_divergent = [], None
    for r in ('16', '4'):
        for k in ('fresh', 'fresh_var'):
            d = abs(f(regen[r][k]) - committed[r][k])
            comparisons.append(dict(block='r%s' % r, field=k, regenerated=f(regen[r][k]), committed=committed[r][k], abs_diff=d,
                                    regenerated_exact=str(regen[r][k])))
            if d > TOL and first_divergent is None:
                first_divergent = 'repetition %d r=%s %s' % (b, r, k)
    strata = {}
    for s in (0, 1):
        es = [e for e in eps if e['stratum'] == s]
        n = len(es)
        tot = {k: sum(e[k] for e in es) for k in ('success', 'cost', 'utility')}
        ex = expect[s]
        strata[('easy', 'hard')[s]] = dict(
            episodes=n, tasks=len({e['task_id'] for e in es}),
            totals={k: f(v) for k, v in tot.items()}, expected_totals={k: f(n * ex[k]) for k in ('success', 'cost', 'utility')},
            utility_total_z=f(tot['utility'] - n * ex['utility']) / math.sqrt(f(n * ex['utility_var'])),
            exit_classes={c: sum(1 for e in es if e['exit'] == c) for c in sorted({e['exit'] for e in eps})},
            first4_utility_total=f(sum(e['utility'] for e in es if e['replicate'] < R.R_SMALL)))
    # task-level contributions to the estimate error: (task mean - stratum expectation) / n
    n_tasks = len(tasks)
    by = {}
    for e in eps:
        by.setdefault((e['task_id'], e['stratum']), []).append(e['utility'])
    contrib = sorted(((t, s, f((sum(v) / len(v) - expect[s]['utility']) / n_tasks)) for (t, s), v in by.items()),
                     key=lambda x: x[2])
    c = [x[2] for x in contrib]
    q = lambda p: c[min(len(c) - 1, int(p * (len(c) - 1) + 0.5))]
    truth = (expect[0]['utility'] + expect[1]['utility']) / 2
    return dict(
        repetition=b, namespace=ns, episodes=len(eps), unique_task_replicate_keys=len({(e['task_id'], e['replicate']) for e in eps}),
        unique_stream_ids=len({e['stream'] for e in eps}), stream_problems=check_streams(eps, ns, POLICY, tasks, R.R_BIG),
        first4_stream_problems=check_streams(first4, ns, POLICY, tasks, R.R_SMALL), utility_identity_violations=check_utility(eps),
        comparisons=comparisons, all_match=first_divergent is None, first_divergent_component=first_divergent,
        error_r16=f(regen['16']['fresh'] - truth), error_r16_exact_sd=f(regen['16']['fresh'] - truth) / math.sqrt(f(
            (expect[0]['utility_var'] + expect[1]['utility_var']) / (2 * R.R_BIG * n_tasks))),
        strata=strata,
        task_contributions=dict(sum=sum(c), sum_by_stratum={('easy', 'hard')[s]: sum(x[2] for x in contrib if x[1] == s) for s in (0, 1)},
                                quantiles={str(p): q(p) for p in (0.0, 0.05, 0.25, 0.5, 0.75, 0.95, 1.0)},
                                largest_five=[dict(task=t, stratum=s, contribution=v) for t, s, v in sorted(contrib, key=lambda x: -abs(x[2]))[:5]],
                                positive_tasks=sum(1 for x in c if x > 0), negative_tasks=sum(1 for x in c if x < 0)))


def main():
    m = json.loads((R.OUT / 'manifest.json').read_text())
    frozen = m['source_sha256']
    hashes = {rel: D.sha(rel) for rel in HASHED}
    changed = [rel for rel, h in frozen.items() if D.sha(rel) != h]
    committed = {json.loads(x)['repetition']: json.loads(x)['policies'][POLICY]
                 for x in (R.OUT / 'reps.jsonl').read_text().splitlines() if json.loads(x)['config'] == CONFIG}
    cell = G.Cell(2, 'crossing', 'weak')
    pol = {p.name: p for p in G.catalog(2)}[POLICY]
    tasks, digest = B.task_list(D.N_TASKS)
    expect = stratum_expectations(cell, pol)
    reps = [replay_one(b, cell, pol, tasks, committed[b], expect) for b in REPS]
    out = dict(request='DTR-REQ-003 bounded deterministic replay integrity check (lead 75017a7)',
               scope='identical replays of saved fixed_LS fresh streams; no new seed/episodes/sweep; repetition 933 retained everywhere',
               config=CONFIG, policy=POLICY, repetitions=list(REPS), controls='repetitions 0 and 1 chosen by index, not outcome',
               root_seed=R.ROOT_SEED, task_list_sha256=digest, tolerance=TOL,
               sensitivity_sources_unchanged_since_freeze=not changed, changed_sources=changed, source_sha256=hashes,
               stratum_expectations={('easy', 'hard')[s]: {k: str(v) for k, v in e.items()} for s, e in expect.items()},
               all_match=all(r['all_match'] for r in reps),
               all_streams_ok=all(not r['stream_problems'] and not r['first4_stream_problems'] for r in reps),
               utility_identity_violations=sum(r['utility_identity_violations'] for r in reps),
               note='agreement supports integrity of these streams only; it is not evidence of nominal coverage; '
                    'identifier uniqueness does not prove stochastic independence', replays=reps)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / 'summary.json').write_text(json.dumps(out, indent=1) + '\n')
    L = ['# Deterministic replay integrity check (DTR-REQ-003; lead 75017a7)', '',
         'Weak / .2 logger / fixed_LS fresh streams, seed %d, n=250 x 16 (+ nested first 4). Sources unchanged since freeze: %s. '
         'All regenerated values within %.0e of the committed records: **%s**. Stream checks clean: %s. Utility-identity '
         'violations: %d.' % (R.ROOT_SEED, out['sensitivity_sources_unchanged_since_freeze'], TOL, out['all_match'],
                              out['all_streams_ok'], out['utility_identity_violations']), '',
         '| Rep | Episodes / unique keys / unique streams | Max abs diff (4 values) | r16 error (exact SDs) | Easy utility total (expected; z) | Hard utility total (expected; z) | Task contributions + / − |',
         '|---|---|---|---|---|---|---|']
    for r in reps:
        e, h = r['strata']['easy'], r['strata']['hard']
        L.append('| %d | %d / %d / %d | %.1e | %+.2f | %.2f (%.2f; %+.2f) | %.2f (%.2f; %+.2f) | %d / %d |' % (
            r['repetition'], r['episodes'], r['unique_task_replicate_keys'], r['unique_stream_ids'],
            max(c['abs_diff'] for c in r['comparisons']), r['error_r16_exact_sd'], e['totals']['utility'],
            e['expected_totals']['utility'], e['utility_total_z'], h['totals']['utility'], h['expected_totals']['utility'],
            h['utility_total_z'], r['task_contributions']['positive_tasks'], r['task_contributions']['negative_tasks']))
    L += ['', '| Rep | Stratum | Success total (expected) | Cost total (expected) | Exit classes |', '|---|---|---|---|---|']
    for r in reps:
        for sname in ('easy', 'hard'):
            st = r['strata'][sname]
            L.append('| %d | %s | %.0f (%.2f) | %.3f (%.3f) | %s |' % (r['repetition'], sname, st['totals']['success'],
                     st['expected_totals']['success'], st['totals']['cost'], st['expected_totals']['cost'],
                     ', '.join('%s %d' % kv for kv in st['exit_classes'].items())))
    L += ['', 'Agreement supports integrity of these streams only; it is not evidence of nominal coverage. Identifier '
          'uniqueness does not prove stochastic independence. Repetition 933 remains in every published statistic.']
    (OUT / 'summary.md').write_text('\n'.join(L) + '\n')
    print('\n'.join(L))


if __name__ == '__main__':
    main()
