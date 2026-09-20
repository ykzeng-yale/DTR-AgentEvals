"""Deterministic, pinned audit of why_null.py; raw JSON is data only.
No experiment imports, model/validator execution, resampling, or raw writes.
"""
import argparse, collections as C, csv, hashlib, io, json, math, pathlib, subprocess
REF='4f9abe49925060cb551d6cbb4900348f65984d68'
ap=argparse.ArgumentParser();ap.add_argument('--repo',type=pathlib.Path);ap.add_argument('--output',type=pathlib.Path);ar=ap.parse_args()
ROOT=ar.repo or pathlib.Path(subprocess.check_output(['git','rev-parse','--show-toplevel']).decode().strip())
def blob(p):return subprocess.check_output(['git','show',f'{REF}:{p}'],cwd=ROOT)
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):return [json.loads(x) for x in blob(p).splitlines()]
def mean(v):return sum(v)/len(v)
def var(v):
 m=mean(v);return sum((x-m)**2 for x in v)/(len(v)-1)
B='results/code_routing/';saved=json.loads(blob(B+'analysis/why_null.json'));L=[e for e in read(B+'log/episodes.jsonl') if e['split']=='confirm'];live=read(B+'live/episodes.jsonl');tasks=sorted({e['task_uid'] for e in L});G=len(tasks)
assert len(L)==2640 and G==330

def contrast(es,t):
 arm={a:[e for e in es if e['decisions'][t]['a']==a] for a in (0,1)}
 y={a:[e['success'] for e in arm[a]] for a in (0,1)};mu={a:mean(y[a]) for a in (0,1)}
 return dict(effect=mu[1]-mu[0],episode_independent_se=math.sqrt(var(y[1])/len(y[1])+var(y[0])/len(y[0])),n=len(es),n_eligible_tasks=len({e['task_uid'] for e in es}),n_large=len(y[1]),n_small=len(y[0]),large_success=mu[1],small_success=mu[0]),None
stages={};U={};cells={};original_plugin={}
for t in (1,2):
 es=[e for e in L if len(e['decisions'])>t];r,u=contrast(es,t);stages[t]=r;U[t]=u
 assert abs(r['effect']-saved['C_theory'][f'effect_at_t{t}']['effect'])<1e-14
 assert abs(r['episode_independent_se']-saved['C_theory'][f'effect_at_t{t}']['se'])<1e-14
 groups=C.defaultdict(list)
 for e in es:groups[e['decisions'][t]['state']['fail_class']+'|prev='+('L' if e['decisions'][t-1]['a'] else 'S')].append(e)
 cells[t]={}
 for k,g in groups.items():
  r0,u0=contrast(g,t)
  assert min(r0['n_large'],r0['n_small'])>=10
  old=saved['C_theory'][f'cells_t{t}'][k]
  assert abs(r0['effect']-old['effect'])<1e-14 and abs(r0['episode_independent_se']-old['se'])<1e-14
  cells[t][k]=r0
 original_plugin[t]=sum(r['n']*max(0.,-r['effect']) for r in cells[t].values())/len(L)
 assert abs(original_plugin[t]-saved['A_design'][f'oracle_tailoring_ceiling_over_always_large_t{t}'])<1e-14
stage_diff=dict(estimate=stages[2]['effect']-stages[1]['effect'],saved_episode_independent_se=saved['C_theory']['stage_gradient']['se'],note='The source adds stage variances as if independent, omitting their shared episodes/tasks. No replacement SE is derived or proposed here; an inferential target and joint sampling argument are required.')
fr={r['policy']:r for r in csv.DictReader(io.StringIO(blob(B+'analysis/frontier_live.csv').decode()))}
met={}
for pol in ('learned','always_large'):
 es=[e for e in live if e['policy']==pol];assert len(es)==660
 large=sum(d['a']==1 for e in es for d in e['decisions']);small=sum(d['a']==0 for e in es for d in e['decisions'])
 met[pol]=dict(n_episodes=len(es),successes=sum(e['success'] for e in es),large_calls=large,small_calls=small,all_calls=large+small,mean_success=mean([e['success'] for e in es]),mean_utility=mean([e['utility'] for e in es]),reachable_sequences=dict(C.Counter(''.join('L' if d['a'] else 'S' for d in e['decisions']) for e in es)))
 for raw,k in [('mean_success','success'),('mean_utility','utility')]:assert abs(met[pol][raw]-float(fr[pol][k]))<1e-14
 assert abs(large/660-float(fr[pol]['large_calls_per_episode']))<1e-14
 assert abs((large+small)/660-float(fr[pol]['calls_per_episode']))<1e-14
le,al=met['learned'],met['always_large'];ds=(le['successes']-al['successes'])/660;dl=(le['large_calls']-al['large_calls'])/660;dsm=(le['small_calls']-al['small_calls'])/660
c_fixed=(ds-.01*dsm)/dl;k_both=ds/(.03*dl+.01*dsm)
assert abs(c_fixed-.064375)<1e-14 and abs(k_both-2.941176470588235)<1e-12
assert abs(.03*k_both-saved['B_metric']['flip_point_large_call_penalty'])<1e-14
met['thresholds']=dict(success_difference=ds,large_call_difference=dl,small_call_difference=dsm,utility_difference_frozen=ds-.03*dl-.01*dsm,utility_difference_formula='(-5 + 96*c_large - 118*c_small)/660',fixed_small_penalty_0p01_large_threshold=c_fixed,both_costs_scale_factor=k_both,both_scaled_large_threshold=.03*k_both,both_scaled_small_threshold=.01*k_both,note='Post-hoc arithmetic crossover of noisy live means, not a statistically validated break-even point. It is the TRAIN-learned policy, not class_tailored.')
# Prefix-specific stage1 contrast cited in README, not present in original summary.
es=[e for e in L if len(e['decisions'])>1 and e['decisions'][0]['a']==1];after_large,_=contrast(es,1)
report=dict(ref=REF,scope='Independent deterministic reconstruction of published stage/cell point estimates, naive SEs, plus live metric counts. No bootstrap, MC, policy search, model or validator execution.',source_hashes={p:sha(blob(p)) for p in ('experiments/tools/why_null.py',B+'analysis/why_null.json',B+'log/episodes.jsonl',B+'live/episodes.jsonl',B+'analysis/frontier_live.csv')},stage_contrasts=stages,cell_contrasts=cells,stage_difference=stage_diff,posthoc_negative_success_cell_statistic=original_plugin,live_metric=met,stage1_after_large=after_large,corrections=[
 'Rename oracle ceiling as an in-sample negative-cell terminal-success statistic, or remove it. It uses estimated signs and logger-reached state frequencies under subsequent logging actions, not true Q values, utility rewards, always-large occupancy or optimal continuation. It is neither an upper confidence bound nor an upper bound on dynamic-policy gain.',
 'The stage1 contrast is the current-action effect on terminal hidden success under subsequent randomized logging, among histories reached by the logger. The stage2 contrast concerns a different, selected risk set. Their difference is descriptive and does not isolate a stage interaction for a common population.',
 'Published SEs treat episodes as independent, despite repeated task records; the stage-gradient SE also treats the overlapping estimates as independent. A valid replacement requires an explicit target and joint source/sampling argument; none is derived here.',
 'Absorption after one decision is78.636% under this logger; it is not evidence78.636% achieved hidden success, not a policy-invariant ceiling, and not evidence the design could detect no tailoring benefit. Initial actions can differ between policies. For learned versus always-large the initial action agrees, but their later histories and continuation laws differ.',
 'A single policy-value SE≈0.024 is not the SE of a paired policy gain and does not prove insufficient power. Estimated cells failing individual null tests do not prove no heterogeneity, nor that no useful policy exists. The framework supplies evaluation conditions, not a guarantee that tailoring must help.',
 'State cost crossover correctly: holding small penalty0.01, large threshold0.064375; scaling both penalties proportionally, multiplier2.941176 gives large0.088235 and small0.029412. The original code computes the latter but the prose suggests the former. Specify this uses learned, not class_tailored.',
 'The source statement frozen-log-only is false for this analysis: the metric section loads frontier_live.csv, independently matched here to660 learned and660 always-large live episodes.',
 'The learned policy really follows L,LS,LSL on its reachable live histories, with zero small third calls. It has96 fewer large but118 more small calls,22 more total calls than always-large. Switching models can save cost; it does not save a model call. The qualitative null-mechanism interpretation remains hypothetical.'
])
out=ar.output or ROOT/'work/why_null_audit_4f9abe4.json';out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(stages=stages,stage_difference=stage_diff,plugin=original_plugin,metric=met,after_large=after_large),indent=2));print('OUTPUT',out)
