"""Independent exact latent-mass check; no worker imports, sampling, or inference."""
import hashlib
import json
import subprocess
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = 'da34fd9456d5ed20ab931e1a6a1ef09c18406b11'
SOURCE = 'experiments/v2_sim/repair_generator_v1.json'
raw = subprocess.check_output(['git', 'show', f'{REF}:{SOURCE}'], cwd=ROOT)
report = json.loads(raw)
tables = report['tables']
checks = 0


def equal(actual, expected):
    global checks
    if isinstance(actual, dict):
        assert F(actual['exact']) == expected
        assert actual['decimal'] == float(expected)
    else:
        assert F(actual) == expected
    checks += 1


def evaluate(cell, s, policy):
    """Propagate unnormalized latent masses per observation history, never Bayes-normalize.

    With policy=None, choose the maximizing action separately at each observable
    prefix. Each action's utility is mass-weighted, so maximization is unchanged
    by omitting the common positive normalization factor.
    """
    K = cell['K']
    p0, deep, fp = [F(tables[k][str(s)]) for k in ('P0', 'DEEP0', 'FALSE_PASS')]
    kappa = F(cell['kappa'])
    repair = {(u, a): F(tables['REPAIR'][cell['action_effect']][f'U{u}_A{a}'])
              for u in (0, 1) for a in (0, 1)}
    stay = {(u, a): F(1, 2) if cell['action_effect'].startswith('U_irrelevant')
            else F(tables['STAY_DEEP'][f'U{u}_A{a}']) for u in (0, 1) for a in (0, 1)}
    costs = [F(tables['COST'][str(a)]) for a in (0, 1)]

    def observe(mass, obs):
        return tuple(mass[u] * (1-fp) * (kappa if (u == 1) == (obs == 'exc') else 1-kappa)
                     for u in (0, 1))

    def action(t, obs):
        if policy.startswith('fixed_'):
            return int(policy[6+t-1] == 'L')
        if policy == 'prompt_only_large_if_hard':
            return s
        if policy == 'history_large_after_exception':
            return int(obs == 'exc')
        assert policy == 'history_S_or_exception'
        return int(s == 1 or obs == 'exc')

    def recurse(t, mass, obs):
        candidates = []
        for a in (0, 1) if policy is None else (action(t, obs),):
            size = sum(mass)
            success = sum(mass[u] * repair[u, a] for u in (0, 1))
            failed = tuple(mass[u] * (1-repair[u, a]) for u in (0, 1))
            nxt = (sum(failed[u]*(1-stay[u, a]) for u in (0, 1)),
                   sum(failed[u]*stay[u, a] for u in (0, 1)))
            # Fields: success, cost, repair calls, false-pass stops, K occupancies.
            value = [success, size*costs[a], size, sum(nxt)*fp] + [F(0)]*K
            value[4+t-1] = size
            if t < K:
                for observation in ('exc', 'asr'):
                    future = recurse(t+1, observe(nxt, observation), observation)
                    value = [x+y for x, y in zip(value, future)]
            candidates.append(value)
        return max(candidates, key=lambda x: x[0]-x[1])

    initial = ((1-p0)*(1-deep), (1-p0)*deep)
    value = [p0, costs[0], F(0), (1-p0)*fp] + [F(0)]*K
    for obs in ('exc', 'asr'):
        value = [x+y for x, y in zip(value, recurse(1, observe(initial, obs), obs))]
    return value


summary = []
policy_count = 0
for cell in report['cells']:
    truth = {}
    for name, saved in cell['policies'].items():
        per = [evaluate(cell, s, name) for s in (0, 1)]
        truth[name] = per
        pooled = [(x+y)/2 for x, y in zip(*per)]
        for key, val in zip(('success', 'cost', 'repair_calls', 'false_pass_stop'), pooled[:4]):
            equal(saved[key], val)
        equal(saved['utility'], pooled[0]-pooled[1])
        for actual, val in zip(saved['reach_opportunity'], pooled[4:]):
            equal(actual, val)
        for s, label in enumerate(('easy', 'hard')):
            equal(saved['by_stratum'][label]['success'], per[s][0])
            equal(saved['by_stratum'][label]['utility'], per[s][0]-per[s][1])
        policy_count += 1
    fixed = {name: per for name, per in truth.items() if name.startswith('fixed_')}
    best_fixed = max(sum(x[0]-x[1] for x in per)/2 for per in fixed.values())
    best_prompt = sum(max(per[s][0]-per[s][1] for per in fixed.values()) for s in (0, 1))/2
    oracle = [evaluate(cell, s, None) for s in (0, 1)]
    best_history = sum(x[0]-x[1] for x in oracle)/2
    for actual, expected in ((cell['best_fixed']['utility'], best_fixed),
                             (cell['best_prompt_only_utility'], best_prompt),
                             (cell['best_observed_history_utility'], best_history),
                             (cell['history_advantage_over_best_fixed'], best_history-best_fixed),
                             (cell['history_advantage_over_best_prompt_only'], best_history-best_prompt)):
        equal(actual, expected)
    summary.append(dict(K=cell['K'], effect=cell['action_effect'], feedback=cell['feedback'],
                        gain_vs_fixed=str(best_history-best_fixed), gain_vs_prompt=str(best_history-best_prompt)))

print(json.dumps(dict(reviewed_commit=REF, source=SOURCE, source_sha256=hashlib.sha256(raw).hexdigest(),
                     method='Exact unnormalized latent-mass recursion; no worker code imported',
                     checks=checks, catalog_policy_values=policy_count, kernel_cells=len(report['cells']),
                     independently_reconstructed_optima=len(summary), all_equal=True,
                     scope='Development known-kernel truth under fixed stopping; no empirical or coverage validation',
                     cells=summary), indent=2))
