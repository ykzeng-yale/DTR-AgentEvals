"""Exact backward utility moments; no worker imports, sampling, or model execution."""
import hashlib
import json
import math
import subprocess
from fractions import Fraction as F
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = '57baf69696ef9c4907657b8265c2aa3881cb4ed8'


def read(path):
    return subprocess.check_output(['git', 'show', f'{REF}:{path}'], cwd=ROOT)


raw = read('experiments/v2_sim/fresh_reference_v1.json')
report = json.loads(raw)
genraw = read('experiments/v2_sim/repair_generator_v1.json')
T = json.loads(genraw)['tables']
blocks = json.loads(read('experiments/v2_sim/fixed_task_blocks_v1.json'))
checks = 0


def reconstruct(row, s):
    K, effect, feedback, policy = [row[k] for k in ('K', 'action_effect', 'feedback', 'policy')]
    p0, deep, fp = [F(T[k][str(s)]) for k in ('P0', 'DEEP0', 'FALSE_PASS')]
    kappa = F(T['KAPPA'][feedback])
    costs = [F(T['COST'][str(a)]) for a in (0, 1)]

    def obs_probability(u, o):
        return (1 - fp) * (kappa if (u == 1) == (o == 'exc') else 1 - kappa)

    @lru_cache(None)
    def continuation(t, u, o):
        a = (int(policy[6+t-1] == 'L') if policy.startswith('fixed_') else
             s if policy == 'prompt_only_large_if_hard' else int(o == 'exc'))
        repair = F(T['REPAIR'][effect][f'U{u}_A{a}'])
        stay = F(T['STAY_DEEP'][f'U{u}_A{a}'])
        future1 = future2 = F(0)
        if t < K:
            for v in (0, 1):
                for next_o in ('exc', 'asr'):
                    prob = (stay if v else 1 - stay) * obs_probability(v, next_o)
                    m1, m2 = continuation(t + 1, v, next_o)
                    future1 += prob * m1
                    future2 += prob * m2
        c = costs[a]
        return (repair * (1-c) + (1-repair) * (future1-c),
                repair * (1-c)**2 + (1-repair) * (future2 - 2*c*future1 + c*c))

    future1 = future2 = F(0)
    for u in (0, 1):
        for o in ('exc', 'asr'):
            prob = (deep if u else 1-deep) * obs_probability(u, o)
            m1, m2 = continuation(1, u, o)
            future1 += prob*m1
            future2 += prob*m2
    c = costs[0]
    mean = p0*(1-c) + (1-p0)*(future1-c)
    second = p0*(1-c)**2 + (1-p0)*(future2-2*c*future1+c*c)
    return mean, second-mean*mean


ratios, fresh, calibration = [], {}, {}
for row in report['rows']:
    values = [reconstruct(row, s) for s in (0, 1)]
    assert F(row['value']['exact']) == sum(m for m, v in values)/2
    checks += 1
    for s, label in enumerate(('easy', 'hard')):
        saved = row['on_policy_per_episode_variance'][label]
        assert F(saved['exact']) == values[s][1] and saved['decimal'] == float(values[s][1])
        checks += 1
    for logger in ('uniform_floor_0.5', 'feedback_dependent_floor_0.2'):
        for n in (250, 1000):
            block = next(b for b in blocks['rows'] if all(b[k] == row[k] for k in
                         ('K', 'action_effect', 'feedback', 'policy')) and b['logger'] == logger and b['n'] == n)
            vf = sum(v for m, v in values)/(8*n)
            vl = F(block['exact_var_V_hat']['exact'])
            want_f, want_c = math.sqrt(float(vf)), math.sqrt(float(vf+vl))
            assert math.isclose(row[f'n{n}']['fresh_se'], want_f, abs_tol=1e-14)
            assert math.isclose(row[f'n{n}']['calibration_discrepancy_se_'+logger], want_c, abs_tol=1e-14)
            checks += 2
            fresh.setdefault(n, []).append(want_f)
            calibration.setdefault(n, []).append(want_c)
            if n == 250:
                for s, label in enumerate(('easy', 'hard')):
                    ratio = F(block['per_episode_ipw_variance'][label]['exact'])/values[s][1]
                    assert ratio >= 1
                    assert math.isclose(row['ipw_to_on_policy_variance_ratio_'+logger][label], float(ratio), rel_tol=1e-14)
                    ratios.append(float(ratio)); checks += 1

assert len(report['rows']) == 24 and len(ratios) == 96
print(json.dumps(dict(reviewed_commit=REF, source_sha256=hashlib.sha256(raw).hexdigest(),
    generator_sha256=hashlib.sha256(genraw).hexdigest(), rows=24, checks=checks, all_pass=True,
    method='Independent backward first/second utility recursion; accepted fixed-task IPW moments used for comparisons; no worker imports',
    ipw_to_fresh_variance_ratio_range=[min(ratios), max(ratios)],
    fresh_se_ranges={n:[min(v),max(v)] for n,v in fresh.items()},
    calibration_se_ranges={n:[min(v),max(v)] for n,v in calibration.items()},
    scope='Fixed 50/50 strata, independent episodes/tasks and fresh/log blocks, r_log=r_fresh=4; exact synthetic moments only'), indent=2))
