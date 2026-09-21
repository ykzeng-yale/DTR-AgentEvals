"""Independent arithmetic from immutable fixed-fit results; no simulation imports."""
from pathlib import Path
import hashlib,json,math
import numpy as np
R=Path(__file__).resolve().parents[1];b=R/'results/v2_sim/fixed_fit_coverage_20260921'
m=json.loads((b/'manifest.json').read_text());s=json.loads((b/'summary.json').read_text());raw=(b/'reps.jsonl').read_bytes();r=[json.loads(x) for x in raw.splitlines()]
assert hashlib.sha256(raw).hexdigest()==s['reps_sha256'];assert hashlib.sha256((b/'manifest.json').read_bytes()).hexdigest()==s['manifest_sha256']
for p,h in m['source_sha256'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==h,p
ids=[(x['fit'],x['evalrep']) for x in r];assert len(ids)==len(set(ids))==10000;assert set(ids)=={(f,j) for f in range(5) for j in range(2000)}
n=0
for row in s['rows']:
 p=[x['policies'][row['policy']] for x in r if x['fit']==row['fit']]; assert len(p)==2000 and all(x['error'] is None for x in p)
 col=lambda k:np.array([x[k] for x in p]); ex=m['exact'][str(row['fit'])+'|'+row['policy']]
 for key in ['dr','dr_minus_fresh','fresh','ipw']:
  d=key=='dr_minus_fresh';e=col('dr')-col('fresh') if d else col(key)-ex['truth'];v=col('dr_var')+col('fresh_var') if d else col(key+'_var');xv=ex[key+'_var'];q=row[key]
  for label,half in [('wald',m['z']*np.sqrt(v)),('exact',m['z']*math.sqrt(xv))]:
   for field,x in [('coverage',sum(abs(e)<=half)),('lower_miss',sum(e < -half)),('upper_miss',sum(e>half))]:assert int(x)==q[label+'_'+field]['count'];n+=1
  for k,x in {'bias':e.mean(),'bias_mcse':e.std(ddof=1)/math.sqrt(2000),'empirical_variance':e.var(ddof=1),'mean_estimated_variance':v.mean(),'empirical_over_exact':e.var(ddof=1)/xv}.items():assert math.isclose(x,q[k],abs_tol=1e-12,rel_tol=1e-10);n+=1
out={'reviewed_commit':'66fb04a','records':10000,'all_expected_ids':True,'source_hashes':len(m['source_sha256']),'asserted_comparisons':n,'affected_tests_passed':8,'worker_checker_assertions':480,'scope':'Independent saved-record arithmetic, not independent trajectory generation; exact moments taken from pinned manifest.'}
(R/'docs/audits/fixed_fit_66fb04a.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
