"""Lead arithmetic audit of saved honest-split development records; no simulator imports."""
import json, math, hashlib
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
b=ROOT/'results/v2_sim/honest_split_coverage_20260921'
m=json.loads((b/'manifest.json').read_text()); summ=json.loads((b/'summary.json').read_text())
raw=(b/'reps.jsonl').read_bytes(); reps=[json.loads(x) for x in raw.splitlines()]
assert hashlib.sha256(raw).hexdigest()==summ['reps_sha256']
assert hashlib.sha256((b/'manifest.json').read_bytes()).hexdigest()==summ['manifest_sha256']
for p,h in m['source_sha256'].items(): assert hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h,p
ids=[(r['config'],r['repetition']) for r in reps]
assert len(ids)==len(set(ids))==4000
assert set(ids)=={(c['config'],j) for c in m['cells'] for j in range(1000)}
checks=0; diagnostics=[]
def close(a,b):
 global checks
 assert math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-12),(a,b)
 checks+=1
for row in summ['rows']:
 P=[r['policies'][row['policy']] for r in reps if r['config']==row['config']]
 assert len(P)==1000 and all(p['error'] is None for p in P)
 col=lambda k:np.array([p[k] for p in P])
 truth=row['truth']; dr,ipw,fr=col('dr'),col('ipw'),col('fresh')
 for key,e,v,t in [('dr',dr,col('dr_var'),truth),('ipw',ipw,col('ipw_var'),truth),('fresh',fr,col('fresh_var'),truth),('dr_minus_fresh',dr-fr,col('dr_var')+col('fresh_var'),0),('ipw_minus_fresh',ipw-fr,col('ipw_var')+col('fresh_var'),0)]:
  s=row[key]; err=e-t; half=m['z']*np.sqrt(v)
  assert np.all(np.isfinite(e)) and np.all(v>0)
  stats={'bias':err.mean(),'bias_mcse':err.std(ddof=1)/math.sqrt(len(e)),'mse':np.mean(err**2),'empirical_variance':e.var(ddof=1),'mean_estimated_variance':v.mean(),'wald_coverage':np.mean(abs(err)<=half),'lower_tail_miss':np.mean(err < -half),'upper_tail_miss':np.mean(err>half),'variance_cv':v.std(ddof=1)/v.mean(),'error_variance_correlation':np.corrcoef(err,v)[0,1]}
  for k,x in stats.items():close(x,s[k])
  # Retrospective constant-scale diagnostic estimated from the same MC records, NOT an exact variance or deployable CI.
  h=m['z']*err.std(ddof=1)
  diagnostics.append({'config':row['config'],'policy':row['policy'],'estimand':key,'wald':s['wald_coverage'],'retrospective_empirical_sd_coverage':float(np.mean(abs(err)<=h)),'raw_error_skew':float(np.mean((err-err.mean())**3)/np.std(err)**3),'mean_var_over_empirical':float(v.mean()/e.var(ddof=1))})
 delta=(dr-truth)**2-(ipw-truth)**2; paired=row['paired_dr_minus_ipw_squared_error']
 close(delta.mean(),paired['mean']);close(delta.std(ddof=1)/math.sqrt(1000),paired['mcse'])
 close(np.mean((dr-truth)**2)/np.mean((ipw-truth)**2),paired['mse_ratio_dr_over_ipw'])
out={'reviewed_commit':'f532597','records':len(reps),'source_hashes':len(m['source_sha256']),'checks':checks,'all_passed':True,'scope':'Independent saved-record arithmetic and retrospective diagnostics; no independent experiment rerun. Empirical-SD diagnostics use the same Monte Carlo records and are not exact-variance coverage or proposed intervals.','diagnostics':diagnostics}
(ROOT/'docs/audits/honest_split_coverage_f532597.json').write_text(json.dumps(out,indent=2)+'\n')
print('records',len(reps),'checks',checks,'source hashes',len(m['source_sha256']))
for r in diagnostics:
 if 'informative-feedback' in r['config'] and r['estimand'] in ('dr','dr_minus_fresh'):print(json.dumps(r))
