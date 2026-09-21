"""Independent second moments for the fixed-task design; exact sums, no sampling or worker imports."""
import hashlib
import json
import math
import subprocess
from fractions import Fraction as F
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = '655663a38bbb438d54c65f258661ade505251650'


def read(path):
    return subprocess.check_output(['git', 'show', f'{REF}:{path}'], cwd=ROOT)


raw = read('experiments/v2_sim/fixed_task_blocks_v1.json')
rep = json.loads(raw)
genraw = read('experiments/v2_sim/repair_generator_v1.json')
generator = json.loads(genraw)
T = generator['tables']
checks = 0


def equal(saved, value):
    global checks
    assert F(saved['exact']) == value
    assert saved['decimal'] == float(value)
    checks += 1


@lru_cache(None)
def moments(K, effect, feedback, logger, policy, s):
    p0, deep, fp = [F(T[k][str(s)]) for k in ('P0','DEEP0','FALSE_PASS')]
    kappa = F(T['KAPPA'][feedback])
    repair = {(u,a): F(T['REPAIR'][effect][f'U{u}_A{a}']) for u in (0,1) for a in (0,1)}
    stay = {(u,a): F(T['STAY_DEEP'][f'U{u}_A{a}']) for u in (0,1) for a in (0,1)}
    costs = [F(T['COST'][str(a)]) for a in (0,1)]
    first = p0*(1-costs[0])-(1-p0)*fp*costs[0]
    second = p0*(1-costs[0])**2+(1-p0)*fp*costs[0]**2

    def observe(mass, o):
        return tuple(mass[u]*(1-fp)*(kappa if (u == 1) == (o == 'exc') else 1-kappa)
                     for u in (0,1))

    def rec(t, mass, o, cost, inverse_assignment):
        nonlocal first, second
        if policy.startswith('fixed_'):
            a = int(policy[6+t-1] == 'L')
        elif policy == 'history_large_after_exception':
            a = int(o == 'exc')
        else:
            assert policy == 'prompt_only_large_if_hard'
            a = s
        p1 = F(1,2) if logger == 'uniform_floor_0.5' else F(4,5) if o == 'exc' else F(1,5)
        inverse_assignment /= p1 if a else 1-p1
        cost += costs[a]
        success = sum(mass[u]*repair[u,a] for u in (0,1))
        failure = tuple(mass[u]*(1-repair[u,a]) for u in (0,1))
        nxt = (sum(failure[u]*(1-stay[u,a]) for u in (0,1)),
               sum(failure[u]*stay[u,a] for u in (0,1)))
        terminal_failure = sum(nxt)*(1 if t == K else fp)
        first += success*(1-cost)-terminal_failure*cost
        # Under the logger E[(W*Z)^2] = sum target_path_prob * Z^2 / assignment_path_prob.
        second += inverse_assignment*(success*(1-cost)**2+terminal_failure*cost**2)
        if t < K:
            for obs in ('exc','asr'):
                rec(t+1,observe(nxt,obs),obs,cost,inverse_assignment)

    initial = ((1-p0)*(1-deep),(1-p0)*deep)
    for o in ('exc','asr'):
        rec(1,observe(initial,o),o,costs[0],F(1))
    return first,second


digests = {}
for key, saved in rep['task_lists'].items():
    n = int(key)
    payload = '\n'.join(f't{g:04d},{g%2}' for g in range(n)).encode()
    digests[n] = hashlib.sha256(payload).hexdigest()
    assert saved['sha256'] == digests[n] and saved['easy'] == saved['hard'] == n//2

ratios = {}
for row in rep['rows']:
    K,e,f,l,p = [row[k] for k in ('K','action_effect','feedback','logger','policy')]
    n,r = row['n'],row['r']
    assert r == 4 and row['task_list_sha256'] == digests[n]
    per = [moments(K,e,f,l,p,s) for s in (0,1)]
    mu = [x[0] for x in per]
    variance = [x[1]-x[0]**2 for x in per]
    truth = next(c for c in generator['cells'] if (c['K'],c['action_effect'],c['feedback']) == (K,e,f))['policies'][p]
    for s,label in enumerate(('easy','hard')):
        assert mu[s] == F(truth['by_stratum'][label]['utility'])
        equal(row['per_episode_ipw_variance'][label],variance[s])
    theta = sum(mu)/2
    var = sum(variance)/(2*r*n)
    excess = (mu[1]-mu[0])**2/(4*(n-1))
    equal(row['target_theta'],theta)
    equal(row['exact_var_V_hat'],var)
    equal(row['expected_within_block_estimator'],var)
    equal(row['iid_formula_excess_between_task'],excess)
    equal(row['expected_iid_task_formula'],var+excess)
    assert row['theta_equals_kernel_mixture'] and theta == F(truth['utility']['exact'])
    assert math.isclose(row['exact_se_V_hat'],math.sqrt(float(var)),rel_tol=1e-14)
    ratio = math.sqrt(float((var+excess)/var))
    assert math.isclose(row['iid_formula_se_ratio'],ratio,rel_tol=1e-14)
    if p == 'history_large_after_exception':
        ratios.setdefault(n,[]).append(ratio)

assert len(rep['rows']) == 96
print(json.dumps(dict(reviewed_commit=REF,source_sha256=hashlib.sha256(raw).hexdigest(),
                     generator_sha256=hashlib.sha256(genraw).hexdigest(),
                     method='Independent exact target-mass and inverse-assignment second moments; no worker imports',
                     rows=96,distinct_policy_logger_stratum_moment_pairs=moments.cache_info().currsize,
                     exact_numeric_comparisons=checks,task_list_hashes=digests,all_checks_pass=True,
                     history_sqrt_expected_variance_to_true_sd_ratio_ranges={n:[min(v),max(v)] for n,v in ratios.items()},
                     scope='Fixed-task first/second moments, independent episodes/blocks; not coverage or contrast validation'),indent=2))
