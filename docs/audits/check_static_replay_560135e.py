"""Independent deterministic reconstruction of static replay; stdlib only, no experiment imports.
Reads pinned raw records, reproduces Rules A/B and live means/paired SEs, and checks
saved DR numbers against existing archived outputs without fitting models or Monte Carlo.
"""
import argparse, collections, csv, hashlib, io, itertools, json, math, pathlib, statistics, subprocess
REF='560135e0b85f479d6ee6afd33bd2987115a786ac';PREV='6f9202613a6e5c38ad4d7e733912495d3f138ea2';BASE='results/code_routing/'
ap=argparse.ArgumentParser();ap.add_argument('--repo',type=pathlib.Path);ap.add_argument('--output',type=pathlib.Path);ap.add_argument('--include-paths',action='store_true');args=ap.parse_args()
ROOT=args.repo or pathlib.Path(subprocess.check_output(['git','rev-parse','--show-toplevel']).decode().strip())
def blob(p,ref=REF):return subprocess.check_output(['git','show',f'{ref}:{p}'],cwd=ROOT)
def obj(p):return json.loads(blob(BASE+p))
def rows(p):return [json.loads(x) for x in blob(BASE+p).splitlines()]
def table(p):return list(csv.DictReader(io.StringIO(blob(BASE+p).decode())))
def mean(x):return statistics.mean(x)
def se(x):return statistics.stdev(x)/math.sqrt(len(x))
def hist(x):return {str(k):v for k,v in sorted(collections.Counter(x).items())}
def ranks(values):
 out=[None]*len(values);ordered=sorted(range(len(values)),key=values.__getitem__);i=0
 while i<len(ordered):
  j=i+1
  while j<len(ordered) and values[ordered[j]]==values[ordered[i]]:j+=1
  for k in ordered[i:j]:out[k]=(i+1+j)/2
  i=j
 return out
def spearman(x,y):
 rx,ry=ranks(x),ranks(y)
 return statistics.correlation(rx,ry) if len(set(rx))>1 and len(set(ry))>1 else None
checks=collections.Counter();failures=collections.defaultdict(list)
def check(name,ok,detail=None):
 checks[name]+=1
 if not ok:failures[name].append(detail)
def close(a,b):return math.isclose(float(a),float(b),rel_tol=1e-11,abs_tol=1e-12)
log=rows('log/episodes.jsonl');live=rows('live/episodes.jsonl');conf=[e for e in log if e['split']=='confirm'];design=obj('design.json')
learned={tuple(k):float(v) for k,v in obj('learned_policy.json')['table']}
check('no_unresolved_input_errors',all(not e['error'] for e in log+live))
tasks=collections.defaultdict(list)
for e in conf:tasks[e['task_uid']].append(e)
for es in tasks.values():es.sort(key=lambda e:e['run'])
check('330_confirm_tasks',len(tasks)==330 and set(tasks)==set(design['confirm_tasks']))
check('8_log_runs_each',all(sorted(e['run'] for e in es)==list(range(8)) for es in tasks.values()))
# Prefix lookup is built once in run-index order; each key lists only episodes which reached that decision.
prefixes={}
for task,es in tasks.items():
 idx=collections.defaultdict(list)
 for e in es:
  seq=[]
  for d in e['decisions']:
   seq.append(d['a']);idx[tuple(seq)].append(e)
 prefixes[task]=idx
live_by=collections.defaultdict(list)
for e in live:live_by[(e['policy'],e['task_uid'])].append(e)
names=sorted({e['policy'] for e in live})
for name in names:
 check('2_live_runs_each_task',all(sorted(e['run'] for e in live_by[(name,t)])==[0,1] for t in tasks),name)
def prob(name,t,benchmark,failure,previous):
 if name=='always_small':return 0.0
 if name=='always_large':return 1.0
 if name=='escalate_after_first_failure':return float(t>0)
 if name=='class_tailored':return float(t>0 and failure=='assertion')
 if name=='learned':return learned.get((t,int(benchmark=='humaneval'),failure,previous[-1] if previous else -1),0.0)
 if name=='soft_escalation_d2':return .5 if t==0 else 2/3
 raise ValueError(name)
def replay(task,name):
 chosen=[];last=None;events=[];benchmark=tasks[task][0]['benchmark']
 for t in range(3):
  failure='start' if last is None else last['decisions'][t-1]['validation']['fail_class']
  probability=prob(name,t,benchmark,failure,chosen);a=int(probability>=.5);requested=tuple(chosen+[a])
  available=prefixes[task].get(requested,[])
  event=dict(t=t,requested_prefix=list(requested),probability=probability,prior_donor=None if last is None else last['episode_id'],donor_count=len(available),donor=None,donor_changed=False)
  if not available:
   event['status']='missing_initial_donor' if last is None else 'fallback_to_last_donor_final_outcome';events.append(event)
   return dict(value=None if last is None else float(last['success']),events=events,stop=event['status'],terminal_donor=None if last is None else last['episode_id'])
  donor=available[0];event['donor']=donor['episode_id'];event['donor_changed']=last is not None and last['episode_id']!=donor['episode_id'];chosen.append(a);last=donor
  if donor['decisions'][t]['validation']['passed']:
   event['status']='visible_pass_stop';events.append(event)
   return dict(value=float(donor['success']),events=events,stop=event['status'],terminal_donor=donor['episode_id'])
  terminal=len(donor['decisions'])<=t+1
  event['status']='horizon_stop' if terminal else 'visible_fail_continue';events.append(event)
  if terminal:return dict(value=float(donor['success']),events=events,stop=event['status'],terminal_donor=donor['episode_id'])
 raise AssertionError('Unreachable')
saved={r['policy']:r for r in table('analysis/static_replay_comparison.csv')}
ope={r['policy']:r for r in table('analysis/ope_confirm.csv') if r['outcome']=='success'}
cal={r['policy']:r for r in table('analysis/calibration_ope_vs_live.csv') if r['outcome']=='success'}
A_task={t:mean(e['success'] for e in es) for t,es in tasks.items()};A=mean(A_task.values());policy_results=[];paths={}
for name in names:
 replayed={t:replay(t,name) for t in sorted(tasks)};paths[name]=replayed
 live_task={t:mean(e['success'] for e in live_by[(name,t)]) for t in tasks}
 valid=[t for t,r in replayed.items() if r['value'] is not None]
 b=[replayed[t]['value'] for t in valid];diff=[replayed[t]['value']-live_task[t] for t in valid]
 avdiff=[A_task[t]-live_task[t] for t in sorted(tasks)]
 live_values=[live_task[t] for t in sorted(tasks)]
 r=dict(policy=name,live_success=mean(live_values),live_se=se(live_values),dr_success=float(ope[name]['dr_estimate']),dr_se=float(ope[name]['dr_se']),static_A=A,static_B=mean(b),static_B_tasks=len(b),no_donor_tasks=len(tasks)-len(b),B_minus_live=mean(diff),B_minus_live_se=se(diff),A_minus_live=mean(avdiff),A_minus_live_se=se(avdiff),DR_minus_live=float(ope[name]['dr_estimate'])-mean(live_values),rule_can_represent=name!='soft_escalation_d2')
 for k in ('live_success','dr_success','dr_se','static_A','static_B','static_B_tasks','no_donor_tasks','B_minus_live','B_minus_live_se','A_minus_live','DR_minus_live'):
  check('saved_csv_'+k,close(r[k],saved[name][k]),name)
 for k,savedkey in [('live_success','live'),('live_se','live_se'),('dr_success','ope_dr'),('dr_se','ope_se')]:check('archived_calibration_'+k,close(r[k],cal[name][savedkey]),name)
 check('saved_representability',r['rule_can_represent']==(saved[name]['rule_can_represent']=='True'),name)
 events=[ev for path in replayed.values() for ev in path['events']]
 stage=[]
 for t in range(3):
  evs=[ev for ev in events if ev['t']==t]
  stage.append(dict(t=t,requests=len(evs),matched=sum(bool(e['donor_count']) for e in evs),missing_prefix=sum(not e['donor_count'] for e in evs),donor_changes=sum(e['donor_changed'] for e in evs),visible_pass_stops=sum(e['status']=='visible_pass_stop' for e in evs),visible_fail_continue=sum(e['status']=='visible_fail_continue' for e in evs),horizon_stops=sum(e['status']=='horizon_stop' for e in evs)))
 r['replay_diagnostics']=dict(by_stage=stage,initial_stops=sum(p['events'][0]['status']=='visible_pass_stop' for p in replayed.values()),initial_stop_fraction=sum(p['events'][0]['status']=='visible_pass_stop' for p in replayed.values())/330,initial_failures=sum(p['events'][0]['status']=='visible_fail_continue' for p in replayed.values()),initial_failure_fraction=sum(p['events'][0]['status']=='visible_fail_continue' for p in replayed.values())/330,fallback_tasks=sum(p['stop']=='fallback_to_last_donor_final_outcome' for p in replayed.values()),tasks_with_donor_change=sum(any(e['donor_changed'] for e in p['events']) for p in replayed.values()),donor_change_events=sum(e['donor_changed'] for e in events),matched_postinitial_requests=sum(e['t']>0 and bool(e['donor_count']) for e in events),stop_histogram=hist(p['stop'] for p in replayed.values()))
 r['task_means']={t:dict(rule_A=A_task[t],rule_B=replayed[t]['value'],live=live_task[t]) for t in sorted(tasks)}
 policy_results.append(r)
def summary(rs):
 l=[r['live_success'] for r in rs];a=[r['static_A'] for r in rs];b=[r['static_B'] for r in rs];d=[r['dr_success'] for r in rs]
 return dict(n_policies=len(rs),policies=[r['policy'] for r in rs],MAE_A=mean(abs(x-y) for x,y in zip(a,l)),MAE_B=mean(abs(x-y) for x,y in zip(b,l)),MAE_DR=mean(abs(x-y) for x,y in zip(d,l)),Spearman_A_vs_live=spearman(a,l),Spearman_B_vs_live=spearman(b,l),Spearman_DR_vs_live=spearman(d,l),max_absolute_B= max(abs(x-y) for x,y in zip(b,l)),max_absolute_DR=max(abs(x-y) for x,y in zip(d,l)))
all_s=summary(policy_results);det_s=summary([r for r in policy_results if r['rule_can_represent']])
saved_summary=obj('analysis/static_replay_summary.json')
mapping=dict(rule_A_value=A,stitching_engages_in_share_of_episodes=sum(len(e['decisions'])>1 for e in conf)/len(conf),deterministic_policies=5,mean_abs_bias_static_B_deterministic=det_s['MAE_B'],mean_abs_bias_DR_deterministic=det_s['MAE_DR'],mean_abs_bias_static_B=all_s['MAE_B'],mean_abs_bias_static_A=all_s['MAE_A'],mean_abs_bias_DR=all_s['MAE_DR'],max_abs_bias_static_B=all_s['max_absolute_B'],max_abs_bias_DR=all_s['max_absolute_DR'],spearman_static_B_vs_live=all_s['Spearman_B_vs_live'],spearman_DR_vs_live=all_s['Spearman_DR_vs_live'],n_policies=6)
for k,v in mapping.items():check('saved_summary_'+k,close(v,saved_summary[k]),k)
coverage={}
for n in (1,2,3):
 allpref=list(itertools.product((0,1),repeat=n))
 cnt={task:sum(pref in ix for pref in allpref) for task,ix in prefixes.items()}
 coverage[str(n)]=dict(possible_action_prefixes=2**n,number_observed_prefixes_per_task=hist(cnt.values()),tasks_with_all_prefixes=sum(v==2**n for v in cnt.values()),tasks_with_any_prefix=sum(v>0 for v in cnt.values()),tasks_with_no_prefix=sum(v==0 for v in cnt.values()),observed_task_prefix_pairs=sum(cnt.values()),tasks_by_prefix={''.join(map(str,p)):sum(p in ix for ix in prefixes.values()) for p in allpref})
protected=subprocess.check_output(['git','ls-tree','-r','--name-only',REF,'results/code_routing'],cwd=ROOT).decode().splitlines();protected=[p for p in protected if '/analysis/' not in p]
check('19_raw_artifacts_unchanged',len(protected)==19 and all(blob(p)==blob(p,PREV) for p in protected))
files=[BASE+x for x in ('log/episodes.jsonl','live/episodes.jsonl','design.json','learned_policy.json','analysis/static_replay_comparison.csv','analysis/static_replay_summary.json','analysis/ope_confirm.csv','analysis/calibration_ope_vs_live.csv')]+['experiments/tools/static_replay.py']
report=dict(ref=REF,previous_ref=PREV,scope='Independent stdlib reconstruction from pinned raw records; no experiment imports, model calls, generated-code execution, DR refitting or Monte Carlo.',input_sha256={p:hashlib.sha256(blob(p)).hexdigest() for p in files},checks=dict(distinct=len(checks),individual=sum(checks.values()),failures=dict(failures)),logged_confirm=dict(episodes=len(conf),tasks=len(tasks),first_stage_stops=sum(len(e['decisions'])==1 for e in conf),first_stage_continues=sum(len(e['decisions'])>1 for e in conf),first_stage_continue_fraction=sum(len(e['decisions'])>1 for e in conf)/len(conf)),prefix_coverage=coverage,per_policy=policy_results,matched_five_policy_metrics=det_s,six_policy_metrics=all_s,replay_paths=paths,interpretation=[
 'All published per-policy Rule A/B values, live means, B-minus-live paired standard errors and numeric summary fields reconstruct. DR estimates/SEs are checked against existing saved OPE/calibration outputs, not independently refit.',
 'no_donor_tasks counts only failure to find an initial donor (None return). An intermediate missing prefix falls back to the last donor final outcome and is still counted among all 330 tasks.',
 'The 21.36% number is first-failure eligibility among 2,640 original log episodes, not actual donor-changing or continuation frequency among the six sets of 330 replay paths.',
 'Observed action-prefix coverage counts only prefixes that reached a recorded decision. Missing coverage does not itself establish structural positivity failure; it directly contradicts the stronger descriptive assertion that every action prefix was available per task.',
 'MAE_A=0.03207 and rank correlations 0.8804/0.8857 use six policies, including a stochastic target that Rule B determinizes. Use the five-policy metrics for a matched deterministic comparison.',
 'Mean absolute discrepancy against noisy live estimates is not bias estimated across repeated datasets. No uncertainty/test comparing MAEs, equivalence test, or power analysis is supplied; nominally smaller MAE cannot establish "not detectably worse" or a null scientific conclusion.',
 'This audit reconstructs a post-hoc descriptive comparator on the same archived benchmark. It does not validate static replay as causal policy evaluation or prove which design feature explains the observed discrepancies.'
])
if not args.include_paths:
 report.pop('replay_paths')
 for policy in report['per_policy']:policy.pop('task_means')
 report['detail_note']='Per-task means and replay paths can be regenerated with --include-paths; omitted from this compact archive.'
out=args.output or ROOT/'work/audit_static_replay_560135e.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('ref','checks','logged_confirm','prefix_coverage','matched_five_policy_metrics','six_policy_metrics')},indent=2))
print('PER_POLICY_DIAGNOSTICS',json.dumps([{k:r[k] for k in ('policy','static_B','live_success','B_minus_live_se','replay_diagnostics')} for r in policy_results],indent=2));print('OUTPUT',out)

if failures:raise SystemExit('Independent artifact reconstruction failed; inspect the report.')
