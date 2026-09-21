"""Retrospective summary audit; no sampler imports and no new simulation."""
import hashlib, json, math, statistics
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
p = ROOT / 'results/v2_sim/dev_batch_20260921'
m = json.loads((p/'manifest.json').read_text()); s = json.loads((p/'summary.json').read_text())
rs = [json.loads(x) for x in (p/'reps.jsonl').read_text().splitlines()]
for name in ('manifest','reps'):
    ext = 'json' if name == 'manifest' else 'jsonl'
    assert hashlib.sha256((p/f'{name}.{ext}').read_bytes()).hexdigest() == s[f'{name}_sha256']
for rel,h in m['source_sha256'].items():
    assert hashlib.sha256((ROOT/rel).read_bytes()).hexdigest() == h, rel
expected={(c['config'],b) for c in m['cells'] for b in range(200)}
assert len(rs)==800 and {(r['config'],r['repetition']) for r in rs}==expected
checks=0; zs=[]; ratios=[]
def check(a,b):
    global checks
    assert math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-12),(a,b)
    checks+=1
for row in s['rows']:
    rr=[r for r in rs if r['config']==row['config']]; pol=row['policy']; truth=row['exact_truth']
    assert all(r['log_episodes']==1000 and r['policies'][pol]['fresh_episodes']==1000 for r in rr)
    arrays={k:[r['policies'][pol][k] for r in rr] for k in ('ipw','fresh')}
    for k,v in arrays.items():
        bias=statistics.mean(v)-truth; sd=statistics.stdev(v); mcse=sd/math.sqrt(len(v))
        for metric,value in [('bias',bias),('empirical_sd',sd),('bias_mcse',mcse),('rmse',math.sqrt(statistics.mean([(x-truth)**2 for x in v])))]:
            check(value,row[k][metric])
        zs.append(abs(bias/mcse)); ratios.append(sd/row[k]['exact_sd'])
    d=[a-b for a,b in zip(arrays['ipw'],arrays['fresh'])]
    mean=statistics.mean(d); mcse=statistics.stdev(d)/math.sqrt(len(d))
    check(mean,row['ipw_minus_fresh']['mean']);check(mcse,row['ipw_minus_fresh']['mcse']);zs.append(abs(mean/mcse))
out=dict(source_commit='35b2f36',complete_repetitions=800,summary_checks=checks,max_abs_bias_or_discrepancy_z=max(zs),empirical_exact_sd_ratio_range=[min(ratios),max(ratios)],scope='Recomputed committed repetition summaries and verified manifest hashes/counts; no independent trajectory regeneration, no coverage validation.')
print(json.dumps(out,indent=2))
