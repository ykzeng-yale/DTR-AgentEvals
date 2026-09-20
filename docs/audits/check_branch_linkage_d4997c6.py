"""Read-only deterministic numeric-record audit; no experiment imports or resampling."""
import json, math, subprocess
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
REF='d4997c68ca93a4d5835bcc578470af472be311b2'
def blob(path):
    return subprocess.check_output(['git','show',f'{REF}:results/code_routing/{path}'],cwd=ROOT).decode()

def mean(v):
    return math.fsum(v)/len(v)
def load(stage):
    rows=[json.loads(s) for s in blob(stage+'/episodes.jsonl').splitlines()]
    assert len({r['episode_id'] for r in rows})==len(rows)
    assert all(not r.get('error') for r in rows)
    return rows
log=[e for e in load('log') if e['split']=='confirm']
br=load('branch')
alltasks=sorted({e['task_uid'] for e in log})
elig=[e for e in log if e['n_decisions']>=2]
plan=json.loads(blob('branch/branch_plan.json'))
assert {e['episode_id'] for e in br}=={e['episode_id'] for e in plan['episodes']}
prefix=defaultdict(lambda: defaultdict(list))
ptask={}
for e in br:
    pid=e['parent_episode_id']; ptask[pid]=e['task_uid']
    prefix[pid][e['fork_arm']].append(e['success'])
assert all(set(a)=={'small','large'} and all(len(v)==2 for v in a.values()) for a in prefix.values())
D={p:mean(a['large'])-mean(a['small']) for p,a in prefix.items()}
btask=defaultdict(list)
for p,d in D.items(): btask[ptask[p]].append(d)
lparts={t:{a:[0.,0.] for a in (0,1)} for t in alltasks}
for e in elig:
    ds=e['decisions']; arm=ds[1]['a']
    w=2. if len(ds)==2 else (4. if ds[2]['a']==arm else 0.)
    lparts[e['task_uid']][arm][0]+=w*e['success']
    lparts[e['task_uid']][arm][1]+=w

def pooled(ts):
    vals={a:math.fsum(lparts[t][a][0] for t in ts)/math.fsum(lparts[t][a][1] for t in ts) for a in (0,1)}
    return vals[1]-vals[0]
common=sorted(set(btask)&{t for t in alltasks if all(lparts[t][a][1]>0 for a in (0,1))})
B=mean(list(D.values())); L=pooled(alltasks)
bs=[mean(btask[t]) for t in common]
ls=[lparts[t][1][0]/lparts[t][1][1]-lparts[t][0][0]/lparts[t][0][1] for t in common]
Z={a:math.fsum(lparts[t][a][1] for t in alltasks) for a in (0,1)}
Y={a:math.fsum(lparts[t][a][0] for t in alltasks) for a in (0,1)}
V={a:Y[a]/Z[a] for a in (0,1)}
# Exact derivative of original full-data ratio functional under shared task multipliers.
uB={t:math.fsum(d-B for d in btask[t])/len(D) for t in alltasks}
uL={t:(lparts[t][1][0]-V[1]*lparts[t][1][1])/Z[1]-(lparts[t][0][0]-V[0]*lparts[t][0][1])/Z[0] for t in alltasks}
u={t:uB[t]-uL[t] for t in alltasks}
def weighted_delta(t,z):
    b=(len(D)*B+(z-1)*math.fsum(btask[t]))/(len(D)+(z-1)*len(btask[t]))
    va={a:(Y[a]+(z-1)*lparts[t][a][0])/(Z[a]+(z-1)*lparts[t][a][1]) for a in (0,1)}
    return b-(va[1]-va[0])
h=1e-5
err=max(abs((weighted_delta(t,1+h)-weighted_delta(t,1-h))/(2*h)-u[t]) for t in alltasks)
assert err < 1e-9
assert abs(math.fsum(u.values())) < 1e-12
linked=json.loads(blob('analysis/branch_vs_log_linked.json'))
assert math.isclose(mean([b-l for b,l in zip(bs,ls)]),linked['paired_difference'],abs_tol=1e-14)
# Two-task example: pooled arm ratios and equal task means differ without dropping tasks.
example_denominators=[2,18]; example_large_means=[1,0]
assert math.isclose(sum(d*y for d,y in zip(example_denominators,example_large_means))/sum(example_denominators),0.1)
assert math.isclose(mean(example_large_means),0.5)
old_common_prefix=mean([d for p,d in D.items() if ptask[p] in common])
out={
 'commit_reviewed':'d4997c6',
 'audit_scope':'Numeric parsing and deterministic algebra only; no models, task code, bootstrap, or Monte Carlo executed.',
 'n_confirm_tasks':len(alltasks),'n_eligible_prefixes':len(elig),'n_eligible_tasks':len({e['task_uid'] for e in elig}),
 'n_selected_prefixes':len(D),'n_branch_tasks':sum(bool(btask[t]) for t in alltasks),'n_linked_selected_tasks':len(common),
 'n_selected_prefixes_in_linked_tasks':sum(len(btask[t]) for t in common),'n_log_eligible_prefixes_in_linked_tasks':sum(e['task_uid'] in common for e in elig),
 'full_prefix_branch_mean':B,'global_hajek_log_mean':L,'full_original_difference':B-L,
 'log_arm_weight_denominators':Z,'log_arm_weighted_success_numerators':Y,'log_arm_means':V,
 'linked_equal_task_branch_mean':mean(bs),'linked_equal_task_log_mean':mean(ls),'linked_equal_task_difference':mean([b-l for b,l in zip(bs,ls)]),
 'linked_task_subset_prefix_weighted_branch_mean':old_common_prefix,'linked_task_subset_pooled_log_mean':pooled(common),
 'linked_task_subset_prefix_weighted_difference':old_common_prefix-pooled(common),
 'linearization_derivative_max_error':err,'sum_task_derivatives':math.fsum(u.values()),
 'covariance_se_status':'No new standard error or confidence interval asserted. Task multiplier derivatives preserve original ratios, but inference must specify task-population vs finite-prefix target and account for global SRS without replacement.',
 'selection_design':{'N':plan['n_eligible_prefixes'],'m':len(D),'f':plan['sampling_probability'],'pair_inclusion':len(D)*(len(D)-1)/(len(elig)*(len(elig)-1))},
 'deterministic_counterexample':{'task_arm_denominators':[[2,2],[18,18]],'task_arm_success_means':[[0,1],[0,0]],'pooled_effect':0.1,'equal_task_effect':0.5},
}
path=ROOT/'work/theory_branch_linkage_audit_20260920.json'
path.parent.mkdir(exist_ok=True)
path.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ('full_original_difference','linked_equal_task_difference','linearization_derivative_max_error','covariance_se_status')},indent=2))
