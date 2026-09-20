"""Bounded independent audit of aac69b5 corrected A6 quantities.
Stdlib only. Git blobs treated as data; no experiment imports, model calls,
validators, fitting, bootstrap/MC, or tracked writes. Does NOT endorse reported SEs.
"""
import argparse, collections as C, csv, hashlib, io, json, math, pathlib, subprocess
REF='aac69b5a634fa3be3ea9c1a26c88e70ef973fe3f';PREV='4f9abe49925060cb551d6cbb4900348f65984d68'
p=argparse.ArgumentParser();p.add_argument('--repo',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path);args=p.parse_args()
ROOT=args.repo or pathlib.Path(subprocess.check_output(['git','rev-parse','--show-toplevel']).decode().strip())
def blob(path,ref=REF):return subprocess.check_output(['git','show',f'{ref}:{path}'],cwd=ROOT)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def jrows(path):return [json.loads(l) for l in blob(path).splitlines()]
def mean(x):return sum(x)/len(x)
def summary(x):
 m=mean(x);return dict(n=len(x),mean=m,se=math.sqrt(sum((y-m)**2 for y in x)/(len(x)-1)/len(x)))
B='results/code_routing/'
L=[e for e in jrows(B+'log/episodes.jsonl') if e['split']=='confirm'];V=jrows(B+'live/episodes.jsonl');S=json.loads(blob(B+'analysis/why_null_corrected.json'));OLD=json.loads(blob(B+'analysis/why_null.json'))
assert len(L)==2640 and len({e['task_uid'] for e in L})==330
# Exact finite-cohort arithmetic of t0, including endpoint controls needed to identify the saved metric.
t0={}
for outcome in ('success','utility','success_first_candidate'):
 t0[outcome]={}
 for b in ('humaneval','mbpp','pooled'):
  z=C.defaultdict(lambda:C.defaultdict(list))
  for e in L:
   if b=='pooled' or e['benchmark']==b:z[e['task_uid']][e['decisions'][0]['a']].append(e[outcome])
  assert all(len(v[0])==len(v[1])==4 for v in z.values())
  t0[outcome][b]=summary([mean(v[1])-mean(v[0]) for v in z.values()])
  if outcome=='success':
   r=S['t0_effect_by_benchmark'][b]
   assert round(t0[outcome][b]['mean'],4)==r['effect'] and round(t0[outcome][b]['se'],4)==r['se'] and t0[outcome][b]['n']==r['n_tasks']
# Identify the 61-task rule from the frozen episodes, without changing that saved rule.
delta={};reached={};botharms={};n_episodes={}
for t in (1,2):
 z=C.defaultdict(lambda:C.defaultdict(list))
 for e in L:
  if len(e['decisions'])>t:z[e['task_uid']][e['decisions'][t]['a']].append(e['success'])
 reached[t]=set(z);delta[t]={g:mean(v[1])-mean(v[0]) for g,v in z.items() if v[0] and v[1]};botharms[t]=set(delta[t]);n_episodes[t]=sum(len(e['decisions'])>t for e in L)
ids=sorted(botharms[1]&botharms[2]);sg=dict(tasks=len(ids),t1=summary([delta[1][g] for g in ids]),t2=summary([delta[2][g] for g in ids]),difference=summary([delta[2][g]-delta[1][g] for g in ids]))
assert len(ids)==61
for field in ('t1','t2'):assert round(sg[field]['mean'],4)==S['stage_gradient_paired'][field]
assert round(sg['difference']['mean'],4)==S['stage_gradient_paired']['difference'] and round(sg['difference']['se'],4)==S['stage_gradient_paired']['se']
# Exact provenance candidates for the otherwise unspecified .0199.
paired={}
for control in ('always_large','always_small'):
 for outcome in ('success','utility'):
  z=C.defaultdict(lambda:C.defaultdict(list))
  for e in V:
   if e['policy'] in ('learned',control):z[e['task_uid']][e['policy']].append(e[outcome])
  assert len(z)==330 and all(len(v['learned'])==len(v[control])==2 for v in z.values())
  paired[f'learned_minus_{control}_{outcome}']=summary([mean(v['learned'])-mean(v[control]) for v in z.values()])
cal=list(csv.DictReader(io.StringIO(blob(B+'analysis/live_contrasts_vs_baseline.csv').decode())))
saved_baseline=next(r for r in cal if r['outcome']=='success' and r['contrast']=='learned - always_small')
assert abs(float(saved_baseline['live_se'])-paired['learned_minus_always_small_success']['se'])<1e-15
assert round(paired['learned_minus_always_small_success']['se'],4)==S['paired_contrast_se']
# Original negative cell directly contradicts the statement no examined stratum favors small.
c={a:[e['success'] for e in L if len(e['decisions'])>1 and e['decisions'][0]['a']==1 and e['decisions'][1]['state']['fail_class']=='assertion' and e['decisions'][1]['a']==a] for a in (0,1)}
negative_cell=mean(c[1])-mean(c[0]);assert abs(negative_cell-OLD['C_theory']['cells_t1']['assertion|prev=L']['effect'])<1e-15
# Crossings use both live cohorts, not just the logger.
metric={}
for pol in ('learned','always_large'):
 es=[e for e in V if e['policy']==pol];metric[pol]=dict(n=len(es),successes=sum(e['success'] for e in es),large=sum(d['a']==1 for e in es for d in e['decisions']),small=sum(d['a']==0 for e in es for d in e['decisions']))
a,b=metric['learned'],metric['always_large'];dS=a['successes']-b['successes'];dL=a['large']-b['large'];dM=a['small']-b['small'];k=dS/(.03*dL+.01*dM);fixed=(dS-.01*dM)/dL
assert (dS,dL,dM)==(-5,-96,118) and round(fixed,6)==S['cost_crossing']['small_fixed_0p01']['large']
assert round(.03*k,6)==S['cost_crossing']['both_scale_1to3']['large'] and round(.01*k,6)==S['cost_crossing']['both_scale_1to3']['small']
# Exact mathematical counterexample; no simulation is involved.
true_delta=-.1;possible_estimates=[-.3,.1];positiveparts=[max(0.,-x) for x in possible_estimates]
assert abs(mean(possible_estimates)-true_delta)<1e-15 and mean(positiveparts)>max(0.,-true_delta) and positiveparts[1]<max(0.,-true_delta)
report=dict(ref=REF,scope='Exact reconstruction of the saved corrected quantities and identification of their endpoints/selection; no new replacement SE, fitting, search over estimators, simulation or outcome execution. Computed SEs only reproduce existing saved arithmetic.',source_hashes={f:sha(blob(f)) for f in (B+'analysis/why_null_corrected.json','experiments/README.md','experiments/PROGRESS.md','docs/experiment_handoff.md',B+'log/episodes.jsonl',B+'live/episodes.jsonl')},historical_source_preserved={f:blob(f)==blob(f,PREV) for f in ('experiments/tools/why_null.py',B+'analysis/why_null.json',B+'log/episodes.jsonl',B+'live/episodes.jsonl')},t0=dict(reconstructed=t0,matched_endpoint='Final hidden-test success, after all eligible decisions',target='Task-weighted contrast E[Y^(A0=large,b_later)-Y^(A0=small,b_later)] within benchmark, including validator-pass absorption. Later actions follow the randomized logger, not always-large or always-small continuation.',not_identified_by_these_numbers=['First-candidate hidden success','Utility gain','Always-large versus always-small whole-policy values','Optimal router gain'],estimation='Four initial-large and four initial-small runs per task; mean of task differences and SD(task differences)/sqrt(task count). Arithmetic reproduction does not validate a fixed-benchmark interval.'),stage_gradient=dict(reproduced=sg,original_eligible_episodes=n_episodes,tasks_reaching_stage={t:len(v) for t,v in reached.items()},tasks_reaching_both=len(reached[1]&reached[2]),tasks_with_both_observed_actions_by_stage={t:len(v) for t,v in botharms.items()},selected_task_ids=ids,selected_id_digest=sha('\n'.join(ids).encode()),selection='At least one observed small AND large action at stage1 AND stage2 in the same task; not merely a task reaching both stages.',weighting='Unweighted average of per-task observed-arm success differences within the selected61 tasks. Original why_null.py uses pooled episode-arm ratios on564 and458 episodes.',limitation='Changes cohort/weights and conditions on realized action support and later eligibility. It is not a covariance repair for the original pooled stage difference. Selecting on later-stage support can also depend on earlier actions/outcomes. Keep exploratory only; no validated stage interaction follows.'),paired_se_provenance=dict(reported=S['paired_contrast_se'],reconstructed_candidates=paired,exact_existing_match='learned minus always_small, SUCCESS, live_contrasts_vs_baseline.csv:0.019912593941486267',relevant_learned_minus_always_large=dict(utility=paired['learned_minus_always_large_utility'],success=paired['learned_minus_always_large_success']),limitation='No committed generator for corrected JSON establishes which calculation authored .0199. Its exact published rounded match is the different baseline/outcome above, and it does not match the live learned-vs-always-large contrasts. It cannot be presented as generic router-gain precision.'),cost_crossings=dict(raw_counts=metric,formula='learned-minus-always-large utility=(-5+96*c_large-118*c_small)/660',fixed_small_0p01_large=fixed,both_scale_factor=k,both_scaled_large=.03*k,both_scaled_small=.01*k),bias_counterexample=dict(true_action_effect=true_delta,unbiased_estimator_values=possible_estimates,equal_probabilities=[.5,.5],true_positivepart_gain=max(0.,-true_delta),realized_gain_values=positiveparts,expected_gain_estimator=mean(positiveparts),failure='On the second outcome the estimated gain is0 despite true gain0.1, although its expectation0.15 exceeds truth. Upward bias is not a realized upper bound.'),negative_original_cell=dict(cell='t1 assertion|prev=L',success_large_minus_small=negative_cell,interpretation='One examined point estimate does favor small slightly; lack of significance is not absence of an effect.'),accepted_corrections=['Universal-router power/vindication claims explicitly withdrawn.','Both penalty-scaling conventions now numerically correct.','Hidden-test-driven eligibility remedy withdrawn.','Source label now acknowledges live frontier use; original script/JSON retained.','Current status row now labels learned comparison inconclusive and calibration coverage unvalidated.'],remaining_scientific_errors=[
 'README says upward bias implies true partition value no larger than observed: false. Jensen gives at most an expectation inequality under additional fixed-weight/unbiased-cell conditions; those conditions themselves are not established for the sampled ratio/selected-cell statistic.',
 'Even partition-scoped oracle terminology remains wrong: current estimated signs, terminal-success endpoint, logger occupancy and logger continuation do not form a dynamic-policy utility gain or an upper confidence bound against always-large.',
 'No examined stratum at any stage favors small contradicts the original negative t1 cell. New t0 strata are point contrasts under randomized future continuation, not evidence that no utility trade-off or adaptive benefit exists.',
 '.0199 is not the inspected learned-minus-always-large live gain SE; its provenance and endpoint are unspecified in corrected JSON. The matching published learned-minus-always-small success value concerns a different comparison.',
 '61-task pairing changes the source population and weighting, and selects on realized support. It repeats the earlier selected-task retargeting problem rather than fixing covariance on the original full cohorts.',
 '78.6% is a realized logger stopping fraction, not a fixed design constant or a universal fraction where dynamic policies can differ. Policies can change the initial action and ensuing occupancy; even for shared-initial policies the fraction is law-dependent.',
 'No generator reproducing why_null_corrected.json is committed; original why_null.py remains unchanged and emits historical output. This independent reconstruction supplies arithmetic provenance but does not certify the new scientific interpretation.'
])
out=args.output or ROOT/'work/aac69b5_review/why_null_corrected_audit.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(t0_final=t0['success'],t0_first=t0['success_first_candidate'],selected_gradient=sg,tasks_reaching_both=report['stage_gradient']['tasks_reaching_both'],botharms=report['stage_gradient']['tasks_with_both_observed_actions_by_stage'],paired=paired,negative_cell=negative_cell,cost=report['cost_crossings']),indent=2));print('OUTPUT',out)
