"""Independent MSE/variance-jackknife arithmetic on saved estimates."""
import json,math,statistics as st,hashlib
from pathlib import Path
p=Path(__file__).resolve().parents[1]/'results/v2_sim/replication_sensitivity_20260921'
a=[json.loads(x) for x in (p/'reps.jsonl').read_text().splitlines()];d=json.loads((p/'diagnosis_retrospective.json').read_text());m=json.loads((p/'manifest.json').read_text());nchecks=0
assert len(a)==2000 and len({(x['config'],x['repetition']) for x in a})==2000
for k,ext in [('reps','jsonl'),('manifest','json')]:assert hashlib.sha256((p/f'{k}.{ext}').read_bytes()).hexdigest()==d['source'][k+'_sha256']
for row in d['rows']:
 rr=[x['policies'][row['policy']] for x in a if x['config']==row['config']]
 for method in ['ipw','fresh','ipw_minus_fresh']:
  for r in ['4','16']:
   q=row[method+'|r'+r];truth=m['exact_table'][row['config']+'|'+row['policy']][r]['truth']
   e=[x[r][method]-truth if method!='ipw_minus_fresh' else x[r]['ipw']-x[r]['fresh'] for x in rr];n=len(e);avg=st.mean(e);ss=sum((x-avg)**2 for x in e)
   loo=[(ss-n/(n-1)*(x-avg)**2)/(n-2) for x in e];lm=st.mean(loo);jk=math.sqrt((n-1)/n*sum((x-lm)**2 for x in loo))
   for name,v in [('mse',st.mean([x*x for x in e])),('centered_variance',st.variance(e)),('centered_variance_jackknife_se',jk)]:assert math.isclose(v,q[name],rel_tol=1e-10,abs_tol=1e-12);nchecks+=1
print(json.dumps({'checks':nchecks,'records':2000,'scope':'Independent MSE, centered variance and closed-form leave-one-out SE; not skewness jackknife or trajectory regeneration.'},indent=2))
