"""Read-only numerical/provenance verification; prints JSON, never resamples."""
import csv, hashlib, json, math, statistics
from pathlib import Path
root=Path(__file__).resolve().parent
for receipt in ('manifest.json','sha256.json'):
    obj=json.loads((root/receipt).read_text())
    hashes=obj['sources'] if receipt=='manifest.json' else obj
    for name,expected in hashes.items():
        assert hashlib.sha256((root/name).read_bytes()).hexdigest()==expected, name
rows=list(csv.DictReader((root/'studies.csv').open()))
assert len(rows)==4000
summary=json.loads((root/'summary.json').read_text())
checks=[]
for cell,target in [('0',0.),('1/5',.1)]:
    group=[r for r in rows if r['cell_eta']==cell]
    assert sorted(int(r['study']) for r in group)==list(range(2000))
    for label,width in [('fixed',4),('half',8)]:
        xs=[float(r[label+'_estimate']) for r in group]
        vs=[float(r[label+'_variance_estimate']) for r in group]
        assert all(math.isfinite(v) and v>0 for v in vs)
        expected_coverage=sum(abs(x-target)<=1.959963984540054*math.sqrt(v) for x,v in zip(xs,vs))/2000
        s=summary[cell]['loggers'][label]
        assert abs(expected_coverage-s['wald_coverage'])<1e-14
        assert abs(statistics.variance(xs)-s['empirical_variance'])<1e-14
        assert abs(statistics.mean(vs)-s['mean_estimated_variance'])<1e-14
        assert sum(abs(x-target)<=width*math.sqrt(math.log(40)/320) for x in xs)==2000
        checks.append(cell+':'+label+':PASS')
resources=json.loads((root/'resource_observations.json').read_text())
assert len(resources)==40 and all(r['passed'] for r in resources)
assert json.loads((root/'status.json').read_text())['status']=='COMPLETE'
print(json.dumps({'status':'PASS','checks':checks,'raw_rows':len(rows),'resource_checks':len(resources),'minimum_reported_memory_free_percent':min(r['memory_free_percent'] for r in resources),'maximum_load1':max(r['load1'] for r in resources),'frozen_source_and_run_hashes':'all verified','sampling_performed':False},indent=2))
