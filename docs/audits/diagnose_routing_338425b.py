"""Post-hoc deterministic design diagnosis from pinned saved records; no experiment imports or execution."""
import argparse,collections,hashlib,json,statistics,subprocess
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path);ap.add_argument('--output',type=Path);a=ap.parse_args()
ROOT=a.repo or Path(__file__).resolve().parents[2];OUT=a.output or ROOT/'work/routing_diagnosis_338425b.json';REF='338425b468cb301f785b0b5daef4a796951f8f55';BASE='results/code_routing/'
def raw(p):return subprocess.check_output(['git','-C',str(ROOT),'show',REF+':'+p])
def obj(p):return json.loads(raw(p))
def rows(p):return [json.loads(x) for x in raw(p).splitlines() if x.strip()]
def mean(x):return statistics.mean(x) if x else None
def sk(d):
 s=d['state'];prev=s['prev_actions'];return (int(s['t']),int(s['x_humaneval']),s['fail_class'],prev[-1] if prev else -1)
log=rows(BASE+'log/episodes.jsonl');live=rows(BASE+'live/episodes.jsonl');train=[e for e in log if e['split']=='train'];confirm=[e for e in log if e['split']=='confirm'];frozen={tuple(k):int(v) for k,v in obj(BASE+'learned_policy.json')['table']};vt=obj(BASE+'visible_tests.json')
assert all(not e.get('error') for e in log+live)
# Manual equivalent of the inspected backward tabular optimal-continuation regression.
def learn(eps,outcome):
 nxt=[0.0]*len(eps);table={};info=[];allq={}
 for t in (2,1,0):
  groups=collections.defaultdict(list);tasks=collections.defaultdict(set);aa_values=collections.defaultdict(list);eligible=[]
  for i,e in enumerate(eps):
   ds=e['decisions'];d=next((d for d in ds if d['t']==t),None)
   if d is None:continue
   r=(-d['penalty'] if outcome=='utility' else 0)+(e['success'] if t==ds[-1]['t'] else 0);y=r+nxt[i];k=sk(d);aa=d['a']
   groups[(k,aa)].append(y);tasks[(k,aa)].add(e['task_uid']);aa_values[aa].append(y);eligible.append((i,k))
  fb={aa:mean(aa_values[aa]) if aa_values[aa] else mean([x for vals in aa_values.values() for x in vals]) or 0 for aa in (0,1)}
  Q={ka:mean(v) for ka,v in groups.items()};nxt=[0.0]*len(eps)
  for k in sorted({k for k,aa in groups}):
   q=[Q.get((k,aa),fb[aa]) for aa in (0,1)];table[k]=int(q[1]>q[0]);allq[k]=q
   info.append({'key':list(k),'q_small':q[0],'q_large':q[1],'large_minus_small':q[1]-q[0],'selected':table[k],'n_small':len(groups.get((k,0),[])),'n_large':len(groups.get((k,1),[])),'tasks_small':len(tasks.get((k,0),set())),'tasks_large':len(tasks.get((k,1),set())),'uses_fallback':any((k,aa) not in Q for aa in (0,1))})
  for i,k in eligible:nxt[i]=max(allq[k])
 return table,sorted(info,key=lambda r:tuple(r['key']))
u_table,u_cells=learn(train,'utility');s_table,s_cells=learn(train,'success')
def summary(eps):
 n=len(eps);out={'episodes':n,'tasks':len({e['task_uid'] for e in eps}),'successes':sum(e['success'] for e in eps),'success_rate':mean([e['success'] for e in eps]),'mean_utility':mean([e['utility'] for e in eps]),'stages':[]}
 for t in (0,1,2):
  ds=[d for e in eps for d in e['decisions'] if d['t']==t]
  out['stages'].append({'t':t,'decisions':len(ds),'large':sum(d['a']==1 for d in ds),'small':sum(d['a']==0 for d in ds),'visible_pass':sum(d['validation']['passed'] for d in ds),'by_failure_state':dict(collections.Counter(d['state']['fail_class'] for d in ds))})
 out['action_sequences']=dict(sorted(collections.Counter(''.join(str(d['a']) for d in e['decisions']) for e in eps).items()))
 d0=lambda e:e['decisions'][0]
 for lab,g in [('all',eps),('a0_small',[e for e in eps if d0(e)['a']==0]),('a0_large',[e for e in eps if d0(e)['a']==1])]:
  if not g:continue
  vp=[e for e in g if d0(e)['validation']['passed']];vf=[e for e in g if not d0(e)['validation']['passed']]
  out[lab+'_first_candidate']={'n':len(g),'hidden_success':sum(e['success_first_candidate'] for e in g),'hidden_rate':mean([e['success_first_candidate'] for e in g]),'visible_pass':len(vp),'visible_fail':len(vf),'visible_pass_hidden_fail':sum(e['success_first_candidate']==0 for e in vp),'visible_fail_hidden_pass':sum(e['success_first_candidate']==1 for e in vf),'hidden_given_visible_pass':mean([e['success_first_candidate'] for e in vp]),'hidden_given_visible_fail':mean([e['success_first_candidate'] for e in vf]),'final_hidden_given_first_visible_fail':mean([e['success'] for e in vf]),'repair_gain_count':sum(e['success']==1 and e['success_first_candidate']==0 for e in vf),'repair_loss_count':sum(e['success']==0 and e['success_first_candidate']==1 for e in vf)}
 out['terminal_confusion']={str((vp,y)):sum(e['decisions'][-1]['validation']['passed']==vp and e['success']==y for e in eps) for vp in (False,True) for y in (0,1)}
 return out
live_groups={p:[e for e in live if e['policy']==p] for p in sorted({e['policy'] for e in live})}
policy_live={p:summary(eps) for p,eps in live_groups.items()}
# Unique original task partitions and strength of visible checks; do not treat these partitions as new experiments.
tasksets={'train':{e['task_uid'] for e in train},'confirm':{e['task_uid'] for e in confirm},'all':set(vt['tests'])};testdist={}
for name,uids in tasksets.items():
 testdist[name]={'tasks':len(uids),'by_n_checks':dict(sorted(collections.Counter(vt['tests'][u]['certified']['n_checks'] for u in uids).items())),'zero_check_tasks':sum(vt['tests'][u]['certified']['n_checks']==0 for u in uids)}
zero_checks={}
for group,eps in [('train',train),('confirm',confirm),*[(p,g) for p,g in live_groups.items()]]:
 zero_checks[group]={}
 for label,gg in [('zero',[e for e in eps if vt['tests'][e['task_uid']]['certified']['n_checks']==0]),('positive',[e for e in eps if vt['tests'][e['task_uid']]['certified']['n_checks']>0])]:
  z=summary(gg);zero_checks[group][label]={k:z[k] for k in ['episodes','tasks','success_rate','all_first_candidate','stages','terminal_confusion']}
learned=live_groups['learned'];cells_live=collections.Counter(sk(d) for e in learned for d in e['decisions']);occ=[]
for k,n in sorted(cells_live.items()):
 c=next((c for c in u_cells if tuple(c['key'])==k),None)
 occ.append({'key':list(k),'live_decisions':n,'table_action':frozen.get(k,0),'absent_frozen_cell':k not in frozen,'train_cell':c,'success_objective_action':s_table.get(k,0)})
# Descriptive benchmark partition summaries retain both benchmarks; no selection based on result.
bench={name:{b:summary([e for e in eps if e['benchmark']==b]) for b in ('mbpp','humaneval')} for name,eps in [('train',train),('confirm',confirm),('live_learned',learned),('live_always_large',live_groups['always_large'])]}
# Descriptive randomized second-decision comparison among first-large failures, followed by the logger.
second_after_large={}
for split,eps in [('train',train),('confirm',confirm)]:
 second_after_large[split]={}
 for aa in (0,1):
  g=[e for e in eps if len(e['decisions'])>1 and e['decisions'][0]['a']==1 and e['decisions'][1]['a']==aa]
  second_after_large[split][str(aa)]={'episodes':len(g),'tasks':len({e['task_uid'] for e in g}),'terminal_successes':sum(e['success'] for e in g),'terminal_success_rate':mean([e['success'] for e in g]),'second_visible_pass':sum(e['decisions'][1]['validation']['passed'] for e in g)}
# Exhaustive TRAIN-only single-task deletion sensitivity (deterministic; not a resampling CI).
delete_changes=collections.Counter();initial_schedule_changes=0
for omit in sorted({e['task_uid'] for e in train}):
 reduced,_=learn([e for e in train if e['task_uid']!=omit],'utility')
 for k,v in frozen.items():
  if reduced.get(k,0)!=v:delete_changes[k]+=1
 if any(reduced.get(k,0)!=1 for k in [(0,0,'start',-1),(0,1,'start',-1)]):initial_schedule_changes+=1
delete_sensitivity={'omitted_train_tasks':231,'initial_large_choice_changes':initial_schedule_changes,'cell_action_changes':[{'key':list(k),'deletions_changing_action':delete_changes[k]} for k in sorted(frozen)],'interpretation':'Exhaustive one-task deletion diagnostic on TRAIN only; not a confidence interval, performance evaluation, or prespecified model-selection step.'}
report={'ref':REF,'train_task_deletion_sensitivity':delete_sensitivity,'scope':'Post-hoc deterministic diagnosis, no new observations, experiment imports, model/candidate execution, resampling or Monte Carlo. Conditional strata are descriptive unless assignment comparison is explicitly justified.','second_after_large_failure_logger_continuation':second_after_large,'frozen_policy_reproduced':u_table==frozen,'frozen_policy_states':len(frozen),'utility_train_Q_cells':u_cells,'success_train_Q_cells':s_cells,'objective_action_differences':[{'key':list(k),'utility':v,'success':s_table[k]} for k,v in u_table.items() if s_table[k]!=v],'learned_live_occupancy':occ,'learned_actions_follow_LSL':all(d['a']==(0 if d['t']==1 else 1) for e in learned for d in e['decisions']),'groups':{'train':summary(train),'confirm':summary(confirm)},'live':policy_live,'benchmarks':bench,'visible_check_distribution':testdist,'visible_check_certification':vt['certification'],'zero_check_strata':zero_checks,'input_sha256':{p:hashlib.sha256(raw(p)).hexdigest() for p in [BASE+'log/episodes.jsonl',BASE+'live/episodes.jsonl',BASE+'learned_policy.json',BASE+'visible_tests.json','experiments/code_routing/estimators_absorbing.py','experiments/code_routing/policies.py']}}
assert u_table==frozen and report['learned_actions_follow_LSL']
OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'frozen_policy_reproduced':u_table==frozen,'learned_actions_follow_LSL':report['learned_actions_follow_LSL'],'objective_action_differences':report['objective_action_differences'],'live_learned':policy_live['learned'],'live_always_large':policy_live['always_large'],'visible_check_distribution':testdist,'learned_live_occupancy':occ},indent=2))
