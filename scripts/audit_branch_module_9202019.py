"""Independent closed-form branch means and high-precision small-frame probabilities; no sampling."""
import hashlib
import json
import math
import subprocess
from decimal import Decimal as D, localcontext
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = '9202019f9cb790d4c0c79e7c792854e1c04087bf'


def read(path):
    return subprocess.check_output(['git','show',f'{REF}:{path}'],cwd=ROOT)


raw = read('experiments/v2_sim/branch_module_v1.json')
rep = json.loads(raw)
genraw = read('experiments/v2_sim/repair_generator_v1.json')
T = json.loads(genraw)['tables']
P = rep['initial_action_kernel']['P0A[S][A0]']
checks = 0


def dec(x):
    return D(x.numerator)/D(x.denominator)


def small_frame(n, alpha=F(1)):
    # Truncated polynomial convolution, 90 decimal digits, no probability threshold.
    # Coefficients >200 cannot contribute to P(N<=200), since counts are nonnegative.
    with localcontext() as ctx:
        ctx.prec = 90
        pmf = [D(1)]
        log_zero = D(0)
        mean = F(0)
        for s,label in enumerate(('easy','hard')):
            for a,arm in enumerate(('small','large')):
                q = alpha*(1-F(P[label][arm]))*(1-F(T['FALSE_PASS'][str(s)]))
                count = n//2*4
                mean += count*q
                p = dec(q)
                log_zero += count*(1-p).log10()
                terms = [(1-p)**count]
                for k in range(1,201):
                    terms.append(terms[-1]*D(count-k+1)/k*p/(1-p))
                out = [D(0)]*201
                for i,x in enumerate(pmf):
                    for j in range(201-i):
                        out[i+j] += x*terms[j]
                pmf = out
        return dict(expected_N=str(mean), log10_P_N_zero=str(log_zero),
                    log10_P_N_le_200=str(sum(pmf).log10()), P_N_le_200=str(sum(pmf)))


tails = {n:small_frame(n) for n in (250,1000)}
for row in rep['rows']:
    n = row['n']; drift = F(9,10) if row['restored_law'].startswith('drifted') else F(1)
    R = {(u,a):F(T['REPAIR'][row['action_effect']][f'U{u}_A{a}']) for u in (0,1) for a in (0,1)}
    trans = {(u,a):F(T['STAY_DEEP'][f'U{u}_A{a}']) for u in (0,1) for a in (0,1)}
    M = ET = F(0); U = [F(0),F(0)]; logD = [D(0),D(0)]
    for s,label in enumerate(('easy','hard')):
        fp = F(T['FALSE_PASS'][str(s)]); deep = F(T['DEEP0'][str(s)])
        prior = [1-deep,deep]
        def value(u,a,scale):
            first = scale*R[u,a]
            return first+(1-first)*(1-fp)*scale*((1-trans[u,a])*R[0,a]+trans[u,a]*R[1,a])
        for arm in ('small','large'):
            count = n//2*4
            q = (1-F(P[label][arm]))*(1-fp)
            M += count*q
            ET += count*q*sum(prior[u]*(value(u,1,drift)-value(u,0,drift)) for u in (0,1))
            for a in (0,1):
                U[a] += count*q*sum(prior[u]*value(u,a,F(1)) for u in (0,1))
                # Weight is positive if the first repair matches and absorbs, or both repairs match.
                positive = q*sum(prior[u]*(F(1,2)-F(1,4)*(1-R[u,a])*(1-fp)) for u in (0,1))
                with localcontext() as ctx:
                    ctx.prec = 90
                    logD[a] += count*(1-dec(positive)).log10()
    theta = ET/M; nu = [x/M for x in U]; delta = theta-nu[1]+nu[0]
    for key, expected in (('E_N',M),('theta',theta),('nu_small',nu[0]),('nu_large',nu[1]),('Delta',delta)):
        assert F(row[key]) == expected
        checks += 1
    assert row['expected_weight_equals_expected_prefixes']
    assert row['theta_decimal'] == float(theta) and row['Delta_decimal'] == float(delta)
    if row['restored_law'] == 'calibrated':
        assert delta == 0
        assert math.isclose(row['P_N_zero_exact_log10'],float(tails[n]['log10_P_N_zero']),rel_tol=1e-12)
        for a,arm in enumerate(('small','large')):
            assert math.isclose(row['P_D_arm_zero_log10'][arm],float(logD[a]),rel_tol=1e-12)
        if n == 250:
            assert math.isclose(row['P_census_N_le_200_float'],float(tails[n]['P_N_le_200']),rel_tol=1e-9)
        else:
            assert row['P_census_N_le_200_float'] == 0 and D(tails[n]['P_N_le_200']) > 0

alpha = F(940,1969)
auxiliary = small_frame(330,alpha)
assert F(auxiliary['expected_N']) == 564
scaled = {s:{a:str(1-alpha*(1-F(p))) for a,p in arms.items()} for s,arms in P.items()}
print(json.dumps(dict(reviewed_commit=REF,source_sha256=hashlib.sha256(raw).hexdigest(),
                     generator_sha256=hashlib.sha256(genraw).hexdigest(),rows=len(rep['rows']),
                     exact_target_comparisons=checks,all_target_checks_pass=True,
                     small_frame_probabilities_90_digit= tails,
                     numerical_findings=['n=1000 float zero is underflow, not zero probability',
                                         'P(N<=200) is a small-frame probability, not actual census use probability'],
                     proposed_auxiliary=dict(n=330,alpha=str(alpha),P0A=scaled,**auxiliary),
                     scope='Exact means and deterministic probability arithmetic; not coverage, power or historical restoration validation'),indent=2))
