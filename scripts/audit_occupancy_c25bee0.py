"""Independent exact totals for the requested occupancy sensitivity; no worker imports or sampling."""
import hashlib
import json
import math
import subprocess
from decimal import Decimal as D, localcontext
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = 'c25bee027564c34aaee44d826048a67ec50d83b9'


def read(path):
    return subprocess.check_output(['git','show',f'{REF}:{path}'],cwd=ROOT)


raw = read('experiments/v2_sim/branch_occupancy_sensitivity_v1.json')
rep = json.loads(raw)
genraw = read('experiments/v2_sim/repair_generator_v1.json'); T = json.loads(genraw)['tables']
alpha = F(rep['alpha']); assert alpha == F(940,1969)
assert rep['n_tasks'] == 330 and rep['strata'] == {'easy':165,'hard':165}
baseline, sensitive = rep['P0A_baseline'], rep['P0A_sensitivity']
for s in baseline:
    for a,p in baseline[s].items():
        assert F(sensitive[s][a]) == 1-alpha*(1-F(p))


def totals(effect, table):
    R = {(u,a):F(T['REPAIR'][effect][f'U{u}_A{a}']) for u in (0,1) for a in (0,1)}
    tr = {(u,a):F(T['STAY_DEEP'][f'U{u}_A{a}']) for u in (0,1) for a in (0,1)}
    out = dict.fromkeys(('M','T','U0','U1','D0','D1'),F(0))
    for s,label in enumerate(('easy','hard')):
        fp,deep = F(T['FALSE_PASS'][str(s)]),F(T['DEEP0'][str(s)])
        values = [sum(pr*(R[u,a]+(1-R[u,a])*(1-fp)*((1-tr[u,a])*R[0,a]+tr[u,a]*R[1,a]))
                      for u,pr in ((0,1-deep),(1,deep))) for a in (0,1)]
        count = sum(165*4*(1-F(p))*(1-fp) for p in table[label].values())
        out['M'] += count; out['T'] += count*(values[1]-values[0])
        for a in (0,1):
            out[f'U{a}'] += count*values[a]; out[f'D{a}'] += count
    return out


def logs(table):
    with localcontext() as ctx:
        ctx.prec = 90
        pmf = [D(1)]; zero_log = D(0)
        for s,label in enumerate(('easy','hard')):
            for p0 in table[label].values():
                q = (1-F(p0))*(1-F(T['FALSE_PASS'][str(s)]))
                p = D(q.numerator)/D(q.denominator); m = 660
                zero_log += m*(1-p).log10()
                b = [(1-p)**m]
                for k in range(1,201):
                    b.append(b[-1]*(m-k+1)/k*p/(1-p))
                nxt = [D(0)]*201
                for i,x in enumerate(pmf):
                    for j in range(201-i):
                        nxt[i+j] += x*b[j]
                pmf = nxt
        return [str(zero_log),str(sum(pmf).log10())]


checked = 0; records = []
for row in rep['rows']:
    base,sens = [totals(row['action_effect'],tab) for tab in (baseline,sensitive)]
    assert all(sens[k] == alpha*base[k] for k in base); checked += len(base)
    assert F(row['E_N_baseline']) == base['M'] == F(5907,5)
    assert F(row['E_N_sensitivity']) == sens['M'] == 564
    for t in (base,sens):
        ratios = dict(theta=t['T']/t['M'],nu_large=t['U1']/t['D1'],nu_small=t['U0']/t['D0'])
        ratios['Delta'] = ratios['theta']-ratios['nu_large']+ratios['nu_small']
        for key,value in ratios.items():
            assert F(row[key]) == value; checked += 1
    assert row['totals_scale_by_alpha'] and row['ratios_unchanged']
    records.append(dict(effect=row['action_effect'],feedback=row['feedback'],
                        baseline={k:str(v) for k,v in base.items()},sensitivity={k:str(v) for k,v in sens.items()}))
lp = {name:logs(tab) for name,tab in (('baseline',baseline),('sensitivity',sensitive))}
for name in lp:
    for actual,expected in zip(rep['rows'][0]['log10_P_N0_and_P_N_le_200'][name],lp[name]):
        assert math.isclose(actual,float(expected),abs_tol=1e-11)
print(json.dumps(dict(reviewed_commit=REF,source_sha256=hashlib.sha256(raw).hexdigest(),
                     generator_sha256=hashlib.sha256(genraw).hexdigest(),rows=4,
                     exact_scaling_and_ratio_checks=checked,all_checks_pass=True,
                     method='Independent two-repair closed forms and 90-digit truncated convolution',
                     log10_probabilities=lp,totals=records,
                     scope='Expected occupancy and calibrated target invariance only; no empirical or inference validation'),indent=2))
