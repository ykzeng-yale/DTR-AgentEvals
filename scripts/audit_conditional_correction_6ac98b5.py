"""Independent saved-record audit; direct paired deletions, no experiment imports or new sampling."""
from pathlib import Path
import hashlib,json,math
import numpy as np
R=Path(__file__).resolve().parents[1]; b=R/'results/v2_sim/honest_split_conditional_moments_20260921'
a=json.loads((b/'correction_20260921.json').read_text()); h=json.loads((b/'summary.json').read_text())
raw=(b/'per_fit_records.jsonl').read_bytes();assert hashlib.sha256(raw).hexdigest()==a['per_fit_records']['sha256']
f=[json.loads(x) for x in raw.splitlines()];assert [x['repetition'] for x in f]==list(range(1000))
saved={x['repetition']:x for x in map(json.loads,(R/'results/v2_sim/honest_split_coverage_20260921/reps.jsonl').read_text().splitlines()) if x['config']==h['config']}
for p,d in a['source_sha256'].items():assert hashlib.sha256((R/p).read_bytes()).hexdigest()==d
checks=0;hashes=0
def close(x,y):
 global checks
 assert math.isclose(float(x),float(y),rel_tol=1e-9,abs_tol=1e-12),(x,y)
 checks+=1
for row in a['rows']:
 name=row['policy'];hist=next(r for r in h['rows'] if r['policy']==name)
 q=[x['policies'][name] for x in f];p=[saved[x['repetition']]['policies'][name] for x in f]
 for x,y in zip(q,p):
  assert x['refit_sha256']==x['saved_sha256']==y['q_fallback_table_sha256'];hashes+=1
  close(x['conditional_mean'],hist['truth'])
 v=np.array([x['exact_var'] for x in q]);k=np.array([x['exact_k3'] for x in q])
 for key in ['dr','dr_minus_fresh']:
  d=key=='dr_minus_fresh';j=row[key]['jackknife']
  e=np.array([x['dr']-x['fresh'] if d else x['dr']-hist['truth'] for x in p]); vx=v+(row[key]['fresh_exact']['variance'] if d else 0)
  diff=[];ratio=[]
  for i in range(1000):
   ev=np.delete(e,i).var(ddof=1);vv=np.delete(vx,i).mean();diff.append(ev-vv);ratio.append(ev/vv)
  se=lambda x:float(np.sqrt(999/1000*np.sum((np.array(x)-np.mean(x))**2)))
  close(se(diff),j['difference_jackknife_se']);close(se(ratio),j['ratio_jackknife_se'])
  close(e.var(ddof=1)-vx.mean(),j['difference']);close(e.var(ddof=1)/vx.mean(),j['ratio'])
  close(j['difference']/se(diff),j['exploratory_difference_z'])
  close(vx.std(ddof=1)/vx.mean(),row[key]['variance_cv_across_fits'])
  skew=(k-(row[key]['fresh_exact']['k3'] if d else 0))/vx**1.5
  close(skew.mean(),row[key]['skewness_of_discrepancy' if d else 'skewness_of_average']['mean'])
  s=hist[key];ve=np.array([x['dr_var']+(x['fresh_var'] if d else 0) for x in p])
  for prefix,vari in [('wald',ve),('exact',vx)]:
   half=1.959963984540054*np.sqrt(vari)
   close(np.sum(abs(e)<=half),s[prefix+'_covered']);close(np.sum(e < -half),s[prefix+'_lower_miss']['count']);close(np.sum(e>half),s[prefix+'_upper_miss']['count'])
out={'reviewed_commit':'6ac98b5','per_fit_rows':len(f),'matched_saved_hashes':hashes,'checks':checks,'source_hashes':len(a['source_sha256']),'tests_passed':3,'scope':'Independent arithmetic from published fit moments and saved errors; direct paired deletions. Does not independently regenerate every fit or enumerate all moments.'}
(R/'docs/audits/conditional_correction_6ac98b5.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out))
