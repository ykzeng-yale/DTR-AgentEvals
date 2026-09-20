"""Pinned, deterministic class-tailored calibration diagnosis; no experiment imports.
Reads git blobs as data. Reproduces the ONE prespecified three-fold tabular DR fit
and per-decision IPW, not a search over specifications. No models, validators,
bootstrap, Monte Carlo, or raw writes. Requires numpy. Run from repo root.
"""
import argparse, ast, collections as C, csv, hashlib, io, json, math, pathlib, subprocess, sys
import numpy as np
REF='338425b468cb301f785b0b5daef4a796951f8f55'
ap=argparse.ArgumentParser();ap.add_argument('--repo',type=pathlib.Path);ap.add_argument('--output',type=pathlib.Path);ar=ap.parse_args()
ROOT=ar.repo or pathlib.Path(subprocess.check_output(['git','rev-parse','--show-toplevel']).decode().strip())
def blob(p):return subprocess.check_output(['git','show',f'{REF}:{p}'],cwd=ROOT)
def sha(b):return hashlib.sha256(b).hexdigest()
def js(p):return json.loads(blob(p))
def rows(p):return [json.loads(l) for l in blob(p).splitlines()]
B='results/code_routing/'
ALL=rows(B+'log/episodes.jsonl');L=[e for e in ALL if e['split']=='confirm'];VL=rows(B+'live/episodes.jsonl');V=[e for e in VL if e['policy']=='class_tailored']
cfg=js('experiments/code_routing/config.json');design=js(B+'design.json');G=330;N=len(L);NV=len(V)
assert len(L)==2640 and len(V)==660 and len({e['task_uid'] for e in L})==G
assert not any(e.get('error') for e in L+V)
tasks=sorted({e['task_uid'] for e in L});assert set(tasks)=={e['task_uid'] for e in V}
assert set(C.Counter(e['task_uid'] for e in L).values())=={8} and set(C.Counter(e['task_uid'] for e in V).values())=={2}
assert set(C.Counter(e['task_uid'] for e in L if e['decisions'][0]['a']==0).values())=={4}
def mean(x):return float(np.mean(list(x)))
def summary(x):
 a=np.array(list(x),float);return dict(mean=float(a.mean()),sd=float(a.std(ddof=1)),se=float(a.std(ddof=1)/np.sqrt(len(a))),n=len(a))
def pol(s):return int(s['t']>0 and s['fail_class']=='assertion')
def key(d):
 s=d['state'];return (int(s['t']),int(s['x_humaneval']),s['fail_class'],s['prev_actions'][-1] if s['prev_actions'] else -1)
def weights(e):
 w=1.;out=[]
 for d in e['decisions']:w*=int(d['a']==pol(d['state']))/d['b_obs'];out.append(w)
 return out
WL=[weights(e) for e in L]
def reward(e,t,outcome):return ((e['success'] if t==len(e['decisions'])-1 else 0)- (e['decisions'][t]['penalty'] if outcome=='utility' else 0)) if t<len(e['decisions']) else 0.
def taskmeans(es,vals):
 d=C.defaultdict(list)
 for e,v in zip(es,vals):d[e['task_uid']].append(v)
 return {k:mean(v) for k,v in d.items()}
checks=C.Counter();problems=[];stage_counts=C.Counter()
fm={e['episode_id']:e for e in design['log_episodes']+design['live_episodes']}
for cohort,es in [('log',L),('live',V)]:
 for e in es:
  f=fm[e['episode_id']];prev=[]
  assertions={'design_task_seed':e['task_uid']==f['task_uid'] and e['seed']==f['seed'], 'utility_identity':abs(e['utility']-(e['success']-sum(d['penalty'] for d in e['decisions'])))<1e-12}
  for d in e['decisions']:
   t=d['t'];pl=.5 if cohort=='log' else pol(d['state']);past=e['decisions'][t-1]['validation'] if t else None
   assertions.update({f'{t}:stage':t==len(prev),f'{t}:preaction_state':d['state']==dict(t=t,x_humaneval=int(e['benchmark']=='humaneval'),fail_class='start' if past is None else past['fail_class'],prev_actions=prev,frac_fail=0. if past is None else past['frac_fail']),f'{t}:probabilities':d['p_large']==pl and d['b_obs']==(pl if d['a']==1 else 1-pl),f'{t}:design_draw_action':d['draw']==f['u'][t] and d['a']==int(f['u'][t]<pl),f'{t}:model_penalty':d['action']==('large' if d['a'] else 'small') and d['model_alias']==cfg['models'][d['action']]['alias'] and d['penalty']==cfg['call_penalty'][d['action']],f'{t}:absorption':not past or not past['passed']})
   if cohort=='live':assertions[f'{t}:policy_action']=d['a']==pol(d['state'])
   stage_counts[(cohort,t,d['state']['fail_class'],d['action'])]+=1
   prev=prev+[d['a']]
  assertions['stop_rule']=e['n_decisions']==len(e['decisions']) and (len(e['decisions'])==cfg['horizon'] or e['decisions'][-1]['validation']['passed'])
  for k,ok in assertions.items():checks[k.split(':')[-1]]+=1;problems.extend([] if ok else [dict(cohort=cohort,episode=e['episode_id'],check=k)])
assert not problems
# Verify our rule against the actual frozen policy function, extracting ONLY that function.
pt=ast.parse(blob('experiments/code_routing/policies.py'));fn=next(n for n in pt.body if isinstance(n,ast.FunctionDef) and n.name=='class_tailored');env={};exec(compile(ast.Module(body=[fn],type_ignores=[]),'frozen_class_tailored_only','exec'),env)
assert all(env['class_tailored'](d['state'])==pol(d['state']) for e in L+V for d in e['decisions'])
# Independent implementation of the exact published fixed fold assignment and Q recursion.
fold=dict(zip(np.array(tasks,object)[np.random.default_rng(0).permutation(G)],np.arange(G)%3))
qdiag=[]
def fit(train,outcome,k):
 nxt={i:0. for i in train};Q={};FB={}
 for t in range(2,-1,-1):
  cells=C.defaultdict(list);arm=C.defaultdict(list)
  for i in train:
   e=L[i]
   if t<len(e['decisions']):
    d=e['decisions'][t];y=reward(e,t,outcome)+nxt[i];cells[(key(d),d['a'])].append(y);arm[d['a']].append(y)
  for (state,a),ys in cells.items():Q[(t,state,a)]=mean(ys)
  for a in (0,1):FB[(t,a)]=mean(arm[a]) if arm[a] else mean(arm[0]+arm[1]) if arm[0]+arm[1] else 0.
  if outcome=='success':qdiag.append(dict(fold=k,t=t,n_training=sum(map(len,arm.values())),n_cells=len(cells),min_cell=min(map(len,cells.values())),median_cell=float(np.median(list(map(len,cells.values()))))))
  nn={i:0. for i in train}
  for i in train:
   if t<len(L[i]['decisions']):
    d=L[i]['decisions'][t];a=pol(d['state']);nn[i]=Q.get((t,key(d),a),FB[(t,a)])
  nxt=nn
 return Q,FB

def original_dr(outcome):
 scores=[0.]*N;plugins=[0.]*N;fallback=C.Counter();adjs=[0.,0.,0.]
 for k in range(3):
  train=[i for i,e in enumerate(L) if fold[e['task_uid']]!=k];test=[i for i,e in enumerate(L) if fold[e['task_uid']]==k];Q,FB=fit(train,outcome,k)
  for i in test:
   e=L[i];vv=[0.]*4;qq=[0.]*3
   for d in e['decisions']:
    t=d['t'];a=pol(d['state']);vv[t]=Q.get((t,key(d),a),FB[(t,a)]);qq[t]=Q.get((t,key(d),d['a']),FB[(t,d['a'])]);fallback[t]+=int((t,key(d),a) not in Q)
   plugins[i]=vv[0];scores[i]=vv[0]
   for t,w in enumerate(WL[i]):
    scores[i]+=w*(reward(e,t,outcome)+vv[t+1]-qq[t]);adjs[t]+=w*(vv[t+1]-qq[t])/N
 return scores,plugins,dict(fallback),[mean(plugins),*adjs]

saved_ope=list(csv.DictReader(io.StringIO(blob(B+'analysis/ope_confirm.csv').decode())));saved_cal=list(csv.DictReader(io.StringIO(blob(B+'analysis/calibration_ope_vs_live.csv').decode())))
# utility/success original scores, exact saved-output checks and task diagnostics.
results={};arrays={};reproduction=[]
for outcome in ('success','utility'):
 ipw=[sum(w*reward(e,t,outcome) for t,w in enumerate(ws)) for e,ws in zip(L,WL)];dr,plug,fb,adj=original_dr(outcome)
 live=[e[outcome] for e in V];I=taskmeans(L,ipw);D=taskmeans(L,dr);P=taskmeans(L,plug);F=taskmeans(V,live)
 diffi=np.array([I[t]-F[t] for t in tasks]);diffd=np.array([D[t]-F[t] for t in tasks]);saved=next(r for r in saved_ope if r['policy']=='class_tailored' and r['outcome']==outcome);cal=next(r for r in saved_cal if r['policy']=='class_tailored' and r['outcome']==outcome)
 obs={'ipw':mean(I.values()),'ipw_se':summary(I.values())['se'],'dr_estimate':mean(D.values()),'dr_se':summary(D.values())['se'],'gcomp':mean(P.values())}
 errs={k:abs(v-float(saved[k])) for k,v in obs.items()};errs.update(live=abs(mean(F.values())-float(cal['live'])),diff=abs(mean(diffd)-float(cal['ope_minus_live'])),paired_se=abs(summary(diffd)['se']-float(cal['diff_se_paired'])))
 assert max(errs.values())<1e-12;reproduction.append(dict(outcome=outcome,max_absolute_error=max(errs.values())))
 ranked=sorted(range(G),key=lambda i:abs(diffd[i]),reverse=True);centered=diffd-diffd.mean();den=float(sum(centered**2));order_var=sorted(range(G),key=lambda i:centered[i]**2,reverse=True)
 bench={b:[t for t in tasks if t.startswith(b+'/')] for b in ('mbpp','humaneval')}
 results[outcome]=dict(ipw=summary(I.values()),dr=summary(D.values()),plugin=mean(P.values()),live=summary(F.values()),ipw_minus_live=summary(diffi),dr_minus_live=summary(diffd),dr_minus_ipw=mean(dr)-mean(ipw),q_fallback_on_heldout_target_states=fb,dr_augmentation_decomposition=dict(plugin_mean=adj[0],stage_terms=adj[1:],sum= sum(adj)),benchmark=[dict(benchmark=b,n_tasks=len(ts),ipw=mean(I[t] for t in ts),dr=mean(D[t] for t in ts),live=mean(F[t] for t in ts),ipw_minus_live=mean(I[t]-F[t] for t in ts),dr_minus_live=mean(D[t]-F[t] for t in ts),contribution_to_overall_dr_gap=sum(D[t]-F[t] for t in ts)/G) for b,ts in bench.items()],influence=dict(negative_tasks=int(sum(diffd< -1e-12)),positive_tasks=int(sum(diffd>1e-12)),nearzero_tasks=int(sum(abs(diffd)<=1e-12)),largest_abs_task_contribution=max(abs(diffd))/G,max_single_task_centered_variance_share=max(centered**2)/den,top10_centered_variance_share=sum(centered[i]**2 for i in order_var[:10])/den,top10_absolute_gap_contribution=sum(diffd[i] for i in ranked[:10])/G,leave_one_task_out_gap_range=[float((sum(diffd)-max(diffd))/(G-1)),float((sum(diffd)-min(diffd))/(G-1))]),top10_absolute_task_gaps=[dict(task=tasks[i],ipw=I[tasks[i]],dr=D[tasks[i]],live=F[tasks[i]],dr_minus_live=float(diffd[i]),contribution=float(diffd[i])/G) for i in ranked[:10]])
 arrays[outcome]=dict(I=I,D=D,F=F,ipw=ipw,dr=dr)
# Stage/terminal decomposition is descriptive, without conditional causal claims.
terminal=[];stages=[]
for t in range(3):
 ix=[i for i,e in enumerate(L) if len(e['decisions'])==t+1];ve=[e for e in V if len(e['decisions'])==t+1]
 terminal.append(dict(last_stage=t,log_matching_episodes=sum(WL[i][-1]>0 for i in ix),log_weighted_terminal_mass=sum(WL[i][-1] for i in ix)/N,live_terminal_mass=len(ve)/NV,log_ipw_success_contribution=sum(WL[i][-1]*L[i]['success'] for i in ix)/N,live_success_contribution=sum(e['success'] for e in ve)/NV))
 stages.append(dict(t=t,log_ipw_reach_mass=sum(ws[t] for e,ws in zip(L,WL) if len(ws)>t)/N,live_reach_mass=sum(len(e['decisions'])>t for e in V)/NV,log_ipw_penalty=sum(ws[t]*e['decisions'][t]['penalty'] for e,ws in zip(L,WL) if len(ws)>t)/N,live_penalty=sum(e['decisions'][t]['penalty'] for e in V if len(e['decisions'])>t)/NV))
first=[]
for name,es in [('log_initial_small',[e for e in L if e['decisions'][0]['a']==0])]+[(p,[e for e in VL if e['policy']==p]) for p in ('class_tailored','always_small','escalate_after_first_failure')]:
 first.append(dict(cohort=name,n_episodes=len(es),first_candidate_hidden_success=mean(e['success_first_candidate'] for e in es),first_visible_pass=mean(e['decisions'][0]['validation']['passed'] for e in es),final_hidden_success=mean(e['success'] for e in es),benchmark=[dict(benchmark=b,n_episodes=len(z),first_candidate_hidden_success=mean(e['success_first_candidate'] for e in z)) for b in ('mbpp','humaneval') if (z:=[e for e in es if e['benchmark']==b])]))
small=[e for e in L if e['decisions'][0]['a']==0];fsi=taskmeans(small,[e['success_first_candidate'] for e in small]);fsv=taskmeans(V,[e['success_first_candidate'] for e in V]);initialgap=mean(fsi[t]-fsv[t] for t in tasks)
# Comparable initial-state transcripts: same task and initial model means same prompt.
prompthashes=C.defaultdict(set)
for e in small+V:prompthashes[e['task_uid']].add(e['decisions'][0]['transcript_sha256'])
assert all(len(v)==1 for v in prompthashes.values())
# Frozen failure-class strata at decisions. W_t identifies target joint mass at a decision;
# successes conditional on a selected stage/class are descriptive, not a rerouted policy.
strata=[]
for t in (1,2):
 for fc in sorted({d['state']['fail_class'] for e in L+V for d in e['decisions'] if d['t']==t}):
  li=[i for i,e in enumerate(L) if len(e['decisions'])>t and e['decisions'][t]['state']['fail_class']==fc];ve=[e for e in V if len(e['decisions'])>t and e['decisions'][t]['state']['fail_class']==fc]
  strata.append(dict(t=t,fail_class=fc,expected_action='large' if fc=='assertion' else 'small',log_matched_prefixes=sum(WL[i][t]>0 for i in li),log_weighted_reach=sum(WL[i][t] for i in li)/N,live_reach=len(ve)/NV,log_weighted_final_success_joint_mass=sum(WL[i][-1]*L[i]['success'] for i in li)/N,live_final_success_joint_mass=sum(e['success'] for e in ve)/NV))
ops=[]
for cohort,es in [('log',L),('live',V)]:
 for e in es:
  if e.get('validation_timeouts') or e.get('verify_timed_out') or any(d['finish']=='length' for d in e['decisions']):ops.append(dict(cohort=cohort,episode=e['episode_id'],task=e['task_uid'],validation_timeouts=e.get('validation_timeouts'),hidden_timeout=e.get('verify_timed_out'),truncations=sum(d['finish']=='length' for d in e['decisions']),success=e['success']))
identity={k:dict(log=sorted({str(e.get(k)) for e in L}),live=sorted({str(e.get(k)) for e in V})) for k in ('config_sha256','code_sha256','tasks_sha256','visible_tests_sha256')}
for k,v in identity.items():assert v['log']==v['live']
lm=rows(B+'log/run_manifest.jsonl');vm=rows(B+'live/run_manifest.jsonl')
assert len(lm)==len(vm)==1 and lm[0]['gguf']==vm[0]['gguf']
seed_overlap=set(e['seed'] for e in L)&set(e['seed'] for e in V)
assert not seed_overlap
last=np.array([w[-1] for w in WL]);mass=mean(last)
report=dict(ref=REF,scope='Deterministic reconstruction from pinned records, including one exact reproduction of the original 3-fold tabular DR specification; no alternative fits, simulations, models or validators. All subgroup comparisons are post-hoc descriptive, with no multiple-comparison inference.',versions=dict(python=sys.version,numpy=np.__version__),hashes={p:sha(blob(p)) for p in ('experiments/code_routing/policies.py','experiments/code_routing/estimators_absorbing.py',B+'log/episodes.jsonl',B+'live/episodes.jsonl',B+'log/run_manifest.jsonl',B+'live/run_manifest.jsonl',B+'design.json')},cohort=dict(n_tasks=G,log_episodes=N,log_initial_small=1320,live_episodes=NV),policy_validation=dict(check_counts=dict(checks),n_failures=len(problems),problems=problems,actual_production_function_matches_independent_rule=True,initial_prompt_hash_matches_by_task=True,stage_action_counts=[dict(cohort=k[0],t=k[1],fail_class=k[2],action=k[3],n=v) for k,v in sorted(stage_counts.items())],identity=identity,recorded_gguf_hashes_equal=True,recorded_gguf=lm[0]['gguf'],log_live_base_seed_overlap=len(seed_overlap)),reproduction=reproduction,estimates=results,support=dict(terminal_weight_mass=mass,ess_terminal=float(last.sum()**2/(last**2).sum()),max_weight=float(max(last)),matching_episodes=int(sum(last>0)),tasks_with_terminal_support=len({e['task_uid'] for e,w in zip(L,last) if w>0}),weight_counts={str(k):v for k,v in sorted(C.Counter(last).items())}),terminal_stage_decomposition=terminal,stage_penalty_decomposition=stages,first_candidate_comparison=first,first_candidate_gap=dict(log_minus_live=initialgap,paired_task_summary=summary(fsi[t]-fsv[t] for t in tasks),ipw_final_gap=results['success']['ipw_minus_live']['mean'],remaining_after_first_candidate=results['success']['ipw_minus_live']['mean']-initialgap,note='The initial-small comparison precedes adaptive routing and is a useful common-prefix diagnostic. The arithmetic residual is not a mediated causal effect or proof of where estimation bias arose.'),failure_class_strata=strata,original_q_training_cell_counts=qdiag,operational_exceptions=ops,interpretation=[
 'No routing or estimator implementation mismatch found in this bounded diagnosis. The independent policy rule and recorded states, action draws, observed probabilities, penalties, stopping rule and selected model aliases agree. Both cohorts share recorded configuration/source/task/visible-test/GGUF hashes, and initial prompts agree per task; those metadata checks do not prove stationary serving noise.',
 'The success difference exists with unaugmented IPW (-4.091 percentage points) and is slightly smaller after the exact original DR fit (-3.664 points). Hence it is not generated by a Q-model fitting adjustment. There are no heldout target-state fallback uses. Some training cells have only 2-7 observations, but sparse cells alone do not identify the cause; with known randomization and stable harness laws, Q misspecification is not sufficient evidence of asymptotic DR bias.',
 'IPW utility and success gaps are both -4.091 points: the weighted call penalties equal live mean penalties exactly. This discrepancy is driven by the final hidden-success score rather than a utility/penalty coding mismatch.',
 'A -2.576-point log/live difference is already present in the first hidden-validated candidate under the same initial-small action and task prompts. The adaptive decision rule has not yet acted. This is 63 percent of the final IPW gap arithmetically, but not a causal mediation decomposition; the residual reflects both later outcomes and sequential weighting noise.',
 'Terminal-stage contributions locate the difference: -1.667 points among episodes stopping after the first call, -2.273 points among episodes stopping after one repair, and -0.152 points at the third call. The stage-1 assertion/large stratum contributes -2.879 points to later final-success joint mass, partly offset by exception/small; these observed selected strata do not identify conditional treatment effects.',
 'HumanEval represents 91 of 330 tasks but contributes -2.111 points of the overall -3.664-point DR gap; MBPP contributes -1.553 points. The initial HumanEval gap is already 5.769 points in the same direction. These are post-hoc localization summaries, not subgroup hypothesis tests.',
 'The estimate is noisy but not explained by one extreme task: the largest absolute task contribution is 0.439 points, and deleting any one task leaves the success difference between -4.116 and -3.356 points. Terminal support includes 1087 compatible episodes, of which only 44 stop after one repair and 55 reach the third decision, with weights4 and8. Terminal weight mass is0.9818; the finite-sample weight variability is material without demonstrating lack of structural positivity.',
 'The one timeout and three truncations occur in two failed tailored live episodes. They cannot explain a spuriously high live hidden-success mean by adding successes; changing both failures to successes would instead increase that mean by at most2/660=0.303 points. No outcome-changing rerun or exclusion is performed.',
 'Under stable transitions/rewards and correct recorded randomization, these are finite-sample noisy estimates of the same policy value. The nominal DR difference is about2.24 paired standard errors and was selected from six pointwise policy comparisons; it does not diagnose systematic OPE failure. Chance/reference noise remains plausible, and an unrecorded serving-distribution difference cannot be ruled out from one sequential log/live collection. Neither explanation is proved here.'
],discriminating_followup=[
 'Keep the current discrepancy and all failed episodes in the main report. State that the independent code and mapping checks passed, the unaugmented estimate shows the same gap, and much of the mismatch predates routing.',
 'The next queued calibration experiment should predefine paired task contrasts and run randomized-log and class-tailored reference episodes interleaved within time blocks under the same frozen harness. Track initial-candidate hidden success separately as a common-prefix diagnostic; do not tune routing or Q models to erase this discrepancy.',
 'Independent repeated log/reference cohorts, with the evaluation family specified in advance, distinguish persistent directional calibration failure from finite-repetition noise. Repeating only the two failed episodes or selecting an alternative estimator by this live result would not provide that evidence.'
])
out=ar.output or ROOT/'work/class_tailored_diagnosis_338425b.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(reproduction=reproduction,success={k:v for k,v in results['success'].items() if k in ('ipw','dr','live','ipw_minus_live','dr_minus_live','benchmark','influence')},utility={k:v for k,v in results['utility'].items() if k in ('ipw','dr','live','ipw_minus_live','dr_minus_live')},first_gap=report['first_candidate_gap'],terminal=terminal,strata=strata,ops=ops,support=report['support']),indent=2));print('OUTPUT',out)
