import json,math,statistics as st,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];p=R/'results/v2_sim/dev_batch_or_stage2_20260921'
s=json.loads((p/'summary.json').read_text());a=[json.loads(x) for x in (p/'reps.jsonl').read_text().splitlines()];b={(x['config'],x['repetition']):x for x in map(json.loads,(R/'results/v2_sim/dev_batch_dr_20260921/reps.jsonl').read_text().splitlines())}
assert len(a)==800 and {(x['config'],x['repetition']) for x in a}==set(b)
for name,ext in [('manifest','json'),('reps','jsonl')]:assert hashlib.sha256((p/f'{name}.{ext}').read_bytes()).hexdigest()==s[f'{name}_sha256']
n=0
for row in s['rows']:
 rr=[x for x in a if x['config']==row['config']];pol=row['policy'];t=row['exact_truth']
 for x in rr:assert abs(x['policies'][pol]['or_standard']-b[x['config'],x['repetition']]['policies'][pol]['or_plugin'])<1e-12
 for key,col in [('or_standard_error','or_standard'),('or_oracle_stage2_error','or_oracle_stage2')]:
  v=[x['policies'][pol][col]-t for x in rr]
  for k,z in [('mean',st.mean(v)),('mcse',st.stdev(v)/math.sqrt(200)),('rmse',math.sqrt(st.mean([y*y for y in v])))]:
   assert abs(z-row[key][k])<1e-12;n+=1
 v=[x['policies'][pol]['or_oracle_stage2']-x['policies'][pol]['or_standard'] for x in rr]
 for k,z in [('mean',st.mean(v)),('mcse',st.stdev(v)/math.sqrt(200))]:assert abs(z-row['paired_difference_oracle_minus_standard'][k])<1e-12;n+=1
print(json.dumps({'unique_records':800,'summary_checks':n,'paired_standard_OR_checks':2400,'scope':'Saved records checked; recovery process and original lost outcomes not independently observed.'},indent=2))
