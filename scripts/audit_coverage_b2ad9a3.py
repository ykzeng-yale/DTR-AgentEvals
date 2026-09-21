"""Retrospective persisted-record audit and tail diagnosis; no simulation."""
import json,hashlib,math,statistics as st
from pathlib import Path
R=Path(__file__).resolve().parents[1];p=R/'results/v2_sim/coverage_fixed_score_20260921'
m=json.loads((p/'manifest.json').read_text());s=json.loads((p/'summary.json').read_text());a=[json.loads(x) for x in (p/'reps.jsonl').read_text().splitlines()]
assert len(a)==8000 and {(x['config'],x['repetition']) for x in a}=={(c['config'],i) for c in m['cells'] for i in range(2000)}
for f,h in m['source_sha256'].items():assert hashlib.sha256((R/f).read_bytes()).hexdigest()==h,f
for n,e in [('manifest','json'),('reps','jsonl')]:assert hashlib.sha256((p/f'{n}.{e}').read_bytes()).hexdigest()==s[f'{n}_sha256']
rows=[];checks=0;z=m['z']
for row in s['rows']:
 rr=[x['policies'][row['policy']] for x in a if x['config']==row['config']]
 for k in ['ipw','fresh','ipw_minus_fresh']:
  e=[x[k]-row['truth'] if k!='ipw_minus_fresh' else x['ipw']-x['fresh'] for x in rr]
  v=[x[k+'_var'] if k!='ipw_minus_fresh' else x['ipw_var']+x['fresh_var'] for x in rr]
  q=row[k];ex=q['exact_variance'];assert all(math.isfinite(t) and t>0 for t in v)
  cov=[abs(t)<=z*math.sqrt(w) for t,w in zip(e,v)];ec=[abs(t)<=z*math.sqrt(ex) for t in e]
  assert sum(cov)==q['wald_covered'] and sum(ec)==q['exact_variance_covered'];checks+=2
  for name,val in [('bias',st.mean(e)),('mean_estimated_variance',st.mean(v)),('mse',st.mean([t*t for t in e])),('empirical_sd',st.stdev(e))]:assert abs(val-q[name])<1e-12;checks+=1
  d=[int(x)-int(y) for x,y in zip(cov,ec)]
  rows.append(dict(config=row['config'],policy=row['policy'],method=k,coverage=st.mean(cov),exact_coverage=st.mean(ec),lower_tail_miss=sum(t < -z*math.sqrt(w) for t,w in zip(e,v))/2000,upper_tail_miss=sum(t>z*math.sqrt(w) for t,w in zip(e,v))/2000,error_variance_correlation=st.correlation(e,v),variance_cv=st.stdev(v)/st.mean(v),paired_coverage_difference=st.mean(d),paired_difference_mcse=st.stdev(d)/math.sqrt(2000)))
print(json.dumps(dict(records=8000,checks=checks,scope='Independent saved-estimate coverage audit; tail analysis is retrospective, not new validation.',rows=rows),indent=2))
