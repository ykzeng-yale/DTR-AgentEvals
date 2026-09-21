"""Independent retrospective arithmetic on saved estimates; no simulation."""
import json,hashlib,math,statistics as st
from pathlib import Path
R=Path(__file__).resolve().parents[1];p=R/'results/v2_sim/dev_batch_dr_20260921'
m=json.loads((p/'manifest.json').read_text());s=json.loads((p/'summary.json').read_text())
a=[json.loads(x) for x in (p/'reps.jsonl').read_text().splitlines()]
b={(x['config'],x['repetition']):x for x in map(json.loads,(R/'results/v2_sim/dev_batch_20260921/reps.jsonl').read_text().splitlines())}
assert len(a)==800 and {(x['config'],x['repetition']) for x in a}==set(b)
for rel,h in m['source_sha256'].items():assert hashlib.sha256((R/rel).read_bytes()).hexdigest()==h
for name,ext in [('manifest','json'),('reps','jsonl')]:assert hashlib.sha256((p/f'{name}.{ext}').read_bytes()).hexdigest()==s[f'{name}_sha256']
n=0;ratios=[];orz=[];drz=[]
def ck(x,y):
 global n
 assert math.isclose(x,y,abs_tol=1e-12,rel_tol=1e-10),(x,y)
 n+=1
for row in s['rows']:
 rr=[x for x in a if x['config']==row['config']];pol=row['policy'];truth=row['exact_truth']
 for x in rr:ck(x['policies'][pol]['ipw'],b[x['config'],x['repetition']]['policies'][pol]['ipw'])
 for e in ('ipw','pdis','dr','or_plugin','dr_known_kernel'):
  v=[x['policies'][pol][e] for x in rr];z=row[e]
  for k,val in [('bias',st.mean(v)-truth),('bias_mcse',st.stdev(v)/math.sqrt(200)),('rmse',math.sqrt(st.mean([(x-truth)**2 for x in v]))),('empirical_sd',st.stdev(v))]:ck(val,z[k])
 for e,other in [('dr_minus_ipw','ipw'),('dr_minus_fresh','fresh')]:
  v=[x['policies'][pol]['dr']-(x['policies'][pol]['ipw'] if other=='ipw' else b[x['config'],x['repetition']]['policies'][pol]['fresh']) for x in rr]
  ck(st.mean(v),row[e]['mean']);ck(st.stdev(v)/math.sqrt(200),row[e]['mcse'])
 ratios.append(row['dr']['rmse']/row['ipw']['rmse']);drz.append(abs(row['dr']['bias']/row['dr']['bias_mcse']))
 orz.append(dict(config=row['config'],policy=pol,z=row['or_plugin']['bias']/row['or_plugin']['bias_mcse']))
print(json.dumps(dict(checks=n,repetitions=800,dr_ipw_rmse_ratio=[min(ratios),max(ratios)],max_abs_dr_bias_mcse=max(drz),or_abs_z_above_2=[x for x in orz if abs(x['z'])>2],scope='Saved-estimate summary and paired IPW audit, not trajectory reproduction or coverage validation'),indent=2))
