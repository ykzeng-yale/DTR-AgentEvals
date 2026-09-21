"""Deterministic sampler-path checks against previously accepted exact artifacts; no Monte Carlo."""
import hashlib
import json
import subprocess
import sys
from fractions import Fraction as F
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = 'f3034c3e461ac7aea23fa522733f234d40c0e215'


def pinned(path):
    return subprocess.check_output(['git', 'show', f'{REF}:{path}'], cwd=ROOT)


for name in ('sampler.py', 'repair_generator.py', 'repair_logger.py'):
    path = 'experiments/v2_sim/' + name
    assert (ROOT/path).read_bytes() == pinned(path), 'Run in the reviewed source checkout'
sys.path.insert(0, str(ROOT/'experiments/v2_sim'))
import sampler as S
import repair_generator as G
import repair_logger as L

fresh = json.loads(pinned('experiments/v2_sim/fresh_reference_v1.json'))
blocks = json.loads(pinned('experiments/v2_sim/fixed_task_blocks_v1.json'))
logger = 'feedback_dependent_floor_0.2'
checks = 0
cases = []
for cfg in ((2, 'crossing', 'informative'), (4, 'no_crossing', 'weak')):
    cell = G.Cell(*cfg)
    catalog = {p.name:p for p in G.catalog(cfg[0])}
    rows = [r for r in fresh['rows'] if tuple(r[k] for k in ('K','action_effect','feedback')) == cfg]
    for s, label in enumerate(('easy', 'hard')):
        logged = list(S.exhaustive(lambda d:S.run_episode(cell,s,d,'log',logger=L.LOGGERS[logger])))
        assert sum(prob for prob,e in logged) == 1
        checks += 1
        for row in rows:
            pol = catalog[row['policy']]
            fr = list(S.exhaustive(lambda d:S.run_episode(cell,s,d,'fresh',policy=pol)))
            fm = sum(prob*e['utility'] for prob,e in fr)
            fv = sum(prob*e['utility']**2 for prob,e in fr)-fm**2
            lm = sum(prob*S.ipw_weight(e,pol)*e['utility'] for prob,e in logged)
            lv = sum(prob*(S.ipw_weight(e,pol)*e['utility'])**2 for prob,e in logged)-lm**2
            b = next(b for b in blocks['rows'] if tuple(b[k] for k in ('K','action_effect','feedback')) == cfg
                     and b['policy']==pol.name and b['logger']==logger and b['n']==250)
            assert sum(prob for prob,e in fr)==1
            assert fm == lm
            assert fv == F(row['on_policy_per_episode_variance'][label]['exact'])
            assert lv == F(b['per_episode_ipw_variance'][label]['exact'])
            checks += 4
            cases.append(dict(config=cfg,stratum=label,policy=pol.name,fresh_mean=str(fm),
                              fresh_variance=str(fv),ipw_variance=str(lv)))

pol = next(p for p in G.catalog(2) if p.name=='history_large_after_exception')
episodes = [dict(task_id=t,replicate=j,utility=y,decisions=[],observations=[],stratum=0,
                 stream=f'fresh:{t}:{j}')
            for t,ys in [('a',[F(0),F(1)]),('b',[F(1),F(1)])] for j,y in enumerate(ys)]
probes = []
for name, rows in [('complete',episodes),('missing_task',episodes[:2]),
                   ('missing_replicate',episodes[1:]),('duplicated_replicate',episodes+[episodes[0]])]:
    probes.append(dict(case=name,episodes=rows,fresh_estimate=str(S.fresh_estimate(rows)),
                       ipw_estimate=str(S.ipw_estimate(rows,pol)),
                       expectation='accept' if name=='complete' else 'reject against frozen task/replicate manifest'))
print(json.dumps(dict(reviewed_commit=REF, checks=checks, exact_checks_pass=True,cases=cases,
                     method='Worker exhaustive sampler paths compared with previously independently accepted moment tables',
                     scope='Two configurations, three catalog policies each, both strata; no random sweeps or independent sampler implementation',
                     complete_block_boundary_probes=probes),indent=2,default=str))
