"""Independent covariance reconstruction via pairwise common-action prefixes; no worker imports."""
import hashlib
import itertools
import json
import math
import subprocess
from fractions import Fraction as F
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = 'b4b074d06a47164d3ef76991dda6ee78a70b2e2e'


def read(path):
    return subprocess.check_output(['git','show',f'{REF}:{path}'],cwd=ROOT)


raw = read('experiments/v2_sim/contrast_covariance_v1.json')
rep = json.loads(raw)
genraw = read('experiments/v2_sim/repair_generator_v1.json')
gen = json.loads(genraw); T = gen['tables']; checks = 0


def equal(actual, expected):
    global checks
    assert F(actual['exact']) == expected
    assert actual['decimal'] == float(expected)
    checks += 1


def determinant(matrix):
    # Leibniz formula is independent of the worker's recursive minor expansion.
    total = F(0)
    for perm in itertools.permutations(range(len(matrix))):
        inversions = sum(perm[i] > perm[j] for i in range(len(perm)) for j in range(i+1,len(perm)))
        value = F((-1)**inversions)
        for i,j in enumerate(perm):
            value *= matrix[i][j]
        total += value
    return total


@lru_cache(None)
def reconstruct(K,e,f,logger,s):
    cell = next(c for c in gen['cells'] if (c['K'],c['action_effect'],c['feedback']) == (K,e,f))
    label = ('easy','hard')[s]
    fixed = [name for name in cell['policies'] if name.startswith('fixed_')]
    best_s = max(fixed,key=lambda name:(F(cell['policies'][name]['by_stratum'][label]['utility']),name))
    names = ['history_large_after_exception','prompt_only_large_if_hard',best_s,cell['best_fixed']['policy']]
    means = [F(cell['policies'][name]['by_stratum'][label]['utility']) for name in names]
    p0,deep,fp = [F(T[key][str(s)]) for key in ('P0','DEEP0','FALSE_PASS')]
    kappa = F(T['KAPPA'][f]); costs = [F(T['COST'][str(a)]) for a in (0,1)]
    repair = {(u,a):F(T['REPAIR'][e][f'U{u}_A{a}']) for u in (0,1) for a in (0,1)}
    stay = {(u,a):F(T['STAY_DEEP'][f'U{u}_A{a}']) for u in (0,1) for a in (0,1)}

    def action(name,t,obs):
        if name.startswith('fixed_'):
            return int(name[6+t-1] == 'L')
        return s if name == 'prompt_only_large_if_hard' else int(obs == 'exc')

    def observe(mass,obs):
        return tuple(mass[u]*(1-fp)*(kappa if (u == 1) == (obs == 'exc') else 1-kappa) for u in (0,1))

    def joint(i,j):
        value = p0*(1-costs[0])**2+(1-p0)*fp*costs[0]**2
        def rec(t,mass,obs,spent,inverse):
            nonlocal value
            a = action(names[i],t,obs)
            if a != action(names[j],t,obs):
                return  # At first disagreement, one of the two scores is permanently zero.
            p1 = F(1,2) if logger == 'uniform_floor_0.5' else F(4,5) if obs == 'exc' else F(1,5)
            inverse /= p1 if a else 1-p1
            spent += costs[a]
            success = sum(mass[u]*repair[u,a] for u in (0,1))
            fail = [mass[u]*(1-repair[u,a]) for u in (0,1)]
            nxt = (sum(fail[u]*(1-stay[u,a]) for u in (0,1)),sum(fail[u]*stay[u,a] for u in (0,1)))
            terminal = sum(nxt)*(1 if t == K else fp)
            value += inverse*(success*(1-spent)**2+terminal*spent**2)
            if t < K:
                for o in ('exc','asr'):
                    rec(t+1,observe(nxt,o),o,spent,inverse)
        initial = ((1-p0)*(1-deep),(1-p0)*deep)
        for o in ('exc','asr'):
            rec(1,observe(initial,o),o,costs[0],F(1))
        return value

    covariance = [[joint(i,j)-means[i]*means[j] for j in range(4)] for i in range(4)]
    for size in range(1,5):
        for idx in itertools.combinations(range(4),size):
            assert determinant([[covariance[i][j] for j in idx] for i in idx]) >= 0
    return means,covariance,best_s


ratios = []; diagnostic = []; increases = []
for row in rep['rows']:
    K,e,f,logger = [row[k] for k in ('K','action_effect','feedback','logger')]
    per = [reconstruct(K,e,f,logger,s) for s in (0,1)]
    label = row['contrast']
    j = 0 if label == 'history_minus_itself_control' else 1 if label == 'history_rule_minus_catalog_prompt_rule' else 2 if 'stratum_schedule:' in label else 3
    if j == 2:
        assert label.split(':')[1] == '/'.join(x[2] for x in per)
    diffs = [m[0]-m[j] for m,c,_ in per]
    variances = [c[0][0]+c[j][j]-2*c[0][j] for m,c,_ in per]
    independent = [c[0][0]+c[j][j] for m,c,_ in per]
    equal(row['true_contrast'],sum(diffs)/2)
    for s,stratum in enumerate(('easy','hard')):
        equal(row['per_episode_contrast_variance'][stratum],variances[s])
    for n in (250,1000):
        var = sum(variances)/(8*n); independent_var = sum(independent)/(8*n)
        saved = row[f'n{n}']
        equal(saved['exact_var'],var)
        assert math.isclose(saved['exact_se'],math.sqrt(float(var)),abs_tol=1e-14)
        assert math.isclose(saved['se_if_scores_were_independent'],math.sqrt(float(independent_var)),abs_tol=1e-14)
        ratio = math.sqrt(float(var/independent_var))
        assert math.isclose(saved['shared_log_se_ratio'],ratio,abs_tol=1e-14)
    assert row['covariance_psd'] and row['direct_second_moment_matches_formula']
    if j != 0:
        ratios.append(row['n250']['shared_log_se_ratio'])
        if sum(variances) > sum(independent):
            increases.append(dict(K=K,effect=e,feedback=f,logger=logger,contrast=label,
                                  sd_ratio=row['n250']['shared_log_se_ratio']))
    if j == 2 and logger == 'uniform_floor_0.5':
        cell = next(c for c in gen['cells'] if (c['K'],c['action_effect'],c['feedback']) == (K,e,f))
        opportunity = F(cell['history_advantage_over_best_prompt_only']['exact'])
        achieved = F(row['true_contrast']['exact'])
        diagnostic.append(dict(K=K,effect=e,feedback=f,rule_minus_best_prompt=str(achieved),
                               oracle_history_minus_best_prompt=str(opportunity),
                               oracle_minus_frozen_history_rule=str(opportunity-achieved)))

assert len(rep['rows']) == 64 and reconstruct.cache_info().currsize == 32
print(json.dumps(dict(reviewed_commit=REF,source_sha256=hashlib.sha256(raw).hexdigest(),
                     generator_sha256=hashlib.sha256(genraw).hexdigest(),rows=64,
                     independently_reconstructed_covariance_matrices=32,exact_numeric_comparisons=checks,
                     psd_principal_minors_checked=32*15,all_checks_pass=True,
                     method='Exact pairwise common-action-prefix moments; no worker imports',
                     nontrivial_shared_to_independent_ipw_sd_range=[min(ratios),max(ratios)],
                     nonidentical_rows_with_variance_increase=len(increases),variance_increase_rows=increases,
                     frozen_rule_diagnosis=diagnostic,
                     scope='Synthetic frozen-policy moments and oracle-gap diagnosis; not learning, power or empirical benefit'),indent=2))
