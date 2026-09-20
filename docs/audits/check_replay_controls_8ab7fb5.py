"""Pinned replay update audit, plus exact eight-point mechanism control.
Only vetted pure functions are extracted from repository source with AST; no experiment
imports, candidate-code execution, model calls, resampling, or Monte Carlo.
"""
import argparse, ast, collections, csv, hashlib, io, itertools, json, math, pathlib, statistics, subprocess
REF='8ab7fb577cb3879b706ebc0c931517e0bfca4ae7';OLD='560135e0b85f479d6ee6afd33bd2987115a786ac';B='results/code_routing/'
p=argparse.ArgumentParser();p.add_argument('--repo',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path);a=p.parse_args()
ROOT=a.repo or pathlib.Path(subprocess.check_output(['git','rev-parse','--show-toplevel']).decode().strip())
def blob(path,ref=REF):return subprocess.check_output(['git','show',f'{ref}:{path}'],cwd=ROOT)
def obj(path):return json.loads(blob(path))
def records(path):return [json.loads(l) for l in blob(path).splitlines()]
def digest(x):return hashlib.sha256(x).hexdigest()
def functions(path,names,constants=()):
 tree=ast.parse(blob(path).decode());nodes=[]
 for n in tree.body:
  if isinstance(n,ast.FunctionDef) and n.name in names:nodes.append(n)
  if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in constants for t in n.targets):nodes.append(n)
 scope={};exec(compile(ast.Module(body=nodes,type_ignores=[]),path,'exec'),scope)
 return scope
SR=functions('experiments/tools/static_replay.py',{'by_task','rule_b','diagnostics','prefix_coverage'})
P=functions('experiments/code_routing/policies.py',{'_odds_shift','always_small','always_large','escalate_after_first_failure','class_tailored','soft_escalation_d2','state_key','table_policy'},{'P_BEHAVIOR'})
prior=obj('docs/audits/static_replay_audit_560135e.json');diag=obj(B+'analysis/static_replay_diagnostics.json');summary=obj(B+'analysis/static_replay_summary.json')
checks=collections.Counter();failures=collections.defaultdict(list)
def check(name,ok,detail=None):
 checks[name]+=1
 if not ok:failures[name].append(detail)
def close(x,y):return math.isclose(float(x),float(y),rel_tol=1e-11,abs_tol=1e-12)
raw=records(B+'log/episodes.jsonl');conf=[e for e in raw if e['split']=='confirm'];tasks=SR['by_task'](conf)
cls={n:P[n] for n in ('always_small','always_large','escalate_after_first_failure','class_tailored','soft_escalation_d2')}
cls['learned']=P['table_policy']({tuple(k):v for k,v in obj(B+'learned_policy.json')['table']})
expected={}
for r in prior['per_policy']:
 if not r['rule_can_represent']:continue
 name=r['policy'];d=r['replay_diagnostics'];expected[name]=dict(continue_after_stage0=d['initial_failures'],missing_donor_stage1=d['by_stage'][1]['missing_prefix'],missing_donor_stage2=d['by_stage'][2]['missing_prefix'],tasks_using_fallback=d['fallback_tasks'],tasks_changing_donor=d['tasks_with_donor_change'])
 actual=SR['diagnostics'](tasks,cls[name])
 check('production_diagnostics_match_prior',actual==expected[name],name)
 check('saved_diagnostics_match_prior',diag['per_target'][name]==expected[name],name)
 vals=[SR['rule_b'](es,cls[name]) for es in tasks.values()]
 check('production_rule_B_matches_prior',None not in vals and close(statistics.mean(vals),r['static_B']),name)
coverage=dict(tasks_with_all_4_length2_prefixes=prior['prefix_coverage']['2']['tasks_with_all_prefixes'],tasks_with_all_8_length3_prefixes=prior['prefix_coverage']['3']['tasks_with_all_prefixes'],n_tasks=330)
check('saved_prefix_coverage',diag['prefix_coverage']==coverage)
check('production_prefix_coverage',SR['prefix_coverage'](tasks)==coverage)
check('exact_five_diagnostic_targets',set(diag['per_target'])==set(expected))
five=prior['matched_five_policy_metrics'];six=prior['six_policy_metrics']
want=dict(rule_A_value=prior['per_policy'][0]['static_A'],spearman_static_B_vs_live_cohort=five['Spearman_B_vs_live'],spearman_DR_vs_live_cohort=five['Spearman_DR_vs_live'],mean_abs_discrepancy_A_cohort=five['MAE_A'],deterministic_policies=5,mean_abs_bias_static_B_deterministic=five['MAE_B'],mean_abs_bias_DR_deterministic=five['MAE_DR'],mean_abs_bias_static_B_all6=six['MAE_B'],mean_abs_bias_static_A_all6=six['MAE_A'],mean_abs_bias_DR_all6=six['MAE_DR'],max_abs_bias_static_B=six['max_absolute_B'],max_abs_bias_DR=six['max_absolute_DR'],n_policies=6,stitching_engages_in_share_of_episodes=prior['logged_confirm']['first_stage_continue_fraction'])
for k,v in want.items():check('saved_summary_numeric_field',close(summary[k],v),k)
check('comparison_csv_unchanged',blob(B+'analysis/static_replay_comparison.csv')==blob(B+'analysis/static_replay_comparison.csv',OLD))
def function_ast(ref,name):return next(ast.dump(n,include_attributes=False) for n in ast.parse(blob('experiments/tools/static_replay.py',ref).decode()).body if isinstance(n,ast.FunctionDef) and n.name==name)
check('rule_B_implementation_unchanged',function_ast(REF,'rule_b')==function_ast(OLD,'rule_b'))
check('by_task_implementation_unchanged',function_ast(REF,'by_task')==function_ast(OLD,'by_task'))
protected=subprocess.check_output(['git','ls-tree','-r','--name-only',REF,'results/code_routing'],cwd=ROOT).decode().splitlines();protected=[x for x in protected if '/analysis/' not in x]
check('all_19_raw_artifacts_unchanged',len(protected)==19 and all(blob(x)==blob(x,OLD) for x in protected))
# Exact controls exercise stage 2, ordering, and donor-state substitution without randomness.
def decision(action,passed,kind='assertion'):
 return dict(a=action,completed=True,validation=dict(passed=passed,fail_class='none' if passed else kind,frac_fail=0.0 if passed else .5))
def episode(run,sequence,success,first_kind='assertion'):
 ds=[decision(x,y) for x,y in sequence];ds[0]['validation']['fail_class']=first_kind if not ds[0]['validation']['passed'] else 'none'
 return dict(episode_id=f'e{run}',run=run,task_uid='t',benchmark='mbpp',success=success,decisions=ds)
late_fallback=[episode(0,[(1,False),(1,False),(0,True)],1)]
check('stage2_fallback_value',SR['rule_b'](late_fallback,P['always_large'])==1)
check('stage2_fallback_diagnostics',SR['diagnostics']({'t':late_fallback},P['always_large'])==dict(continue_after_stage0=1,missing_donor_stage1=0,missing_donor_stage2=1,tasks_using_fallback=1,tasks_changing_donor=0))
horizon=[episode(0,[(1,False),(1,False),(1,False)],0)]
check('actual_K3_horizon_value',SR['rule_b'](horizon,P['always_large'])==0)
check('actual_K3_horizon_diagnostics',SR['diagnostics']({'t':horizon},P['always_large'])==dict(continue_after_stage0=1,missing_donor_stage1=0,missing_donor_stage2=0,tasks_using_fallback=0,tasks_changing_donor=0))
unsorted=[episode(1,[(1,True)],1),episode(0,[(1,True)],0)]
check('by_task_orders_unsorted_input',SR['rule_b'](SR['by_task'](unsorted)['t'],P['always_large'])==0)
# Donor0 is the current logged episode. Donor1 is the first later donor with the opposite
# second action, after integrating out rejected same-action rows. These are not two
# unconditional iid rows. Each triple (U,A,U') has exact probability 1/8.
# True environment: both policies begin with small; U is then observed as failure class.
# Stage-two hidden reward is 1{action == U}; validator passes at stage two.
control=[]
targets=dict(class_tailored=P['class_tailored'],fixed_second_small=P['always_small'],fixed_second_large=P['escalate_after_first_failure'])
for u,action,up in itertools.product((0,1),repeat=3):
 donors=[episode(0,[(0,False),(action,True)],int(action==u),'assertion' if u else 'exception'),episode(1,[(0,False),(1-action,True)],int(1-action==up),'assertion' if up else 'exception')]
 for name,policy in targets.items():
  replay=SR['rule_b'](donors,policy);d=SR['diagnostics']({'t':donors},policy)
  state=dict(t=1,x_humaneval=0,fail_class='assertion' if u else 'exception',prev_actions=(0,),frac_fail=.5)
  actual_action=int(policy(state)>=.5);truth=int(actual_action==u)
  check('exact_control_no_fallback',d['tasks_using_fallback']==d['missing_donor_stage1']==d['missing_donor_stage2']==0,(u,action,up,name))
  control.append(dict(U=u,A=action,U_prime=up,weight=1/8,target=name,replayed_success=replay,true_target_success=truth,diagnostics=d))
exact={}
for name in targets:
 rr=[r for r in control if r['target']==name]
 exact[name]=dict(replay_value=sum(r['weight']*r['replayed_success'] for r in rr),true_value=sum(r['weight']*r['true_target_success'] for r in rr),donor_change_cases=sum(r['diagnostics']['tasks_changing_donor'] for r in rr),fallback_cases=sum(r['diagnostics']['tasks_using_fallback'] for r in rr))
 expected_replay=.75 if name=='class_tailored' else .5;expected_truth=1.0 if name=='class_tailored' else .5
 check('exact_control_values',exact[name]['replay_value']==expected_replay and exact[name]['true_value']==expected_truth,name)
 check('exact_control_donor_changes',exact[name]['donor_change_cases']==4,name)
report=dict(ref=REF,prior_ref=OLD,scope='Pinned pure-function diagnostic checks and finite exhaustive control; no experiment imports, models, candidate-code execution or Monte Carlo.',source_hashes={x:digest(blob(x)) for x in ('experiments/tools/static_replay.py','experiments/code_routing/policies.py','experiments/tools/test_static_replay.py')},published_tests=dict(default_venv_result='Collection failed: ModuleNotFoundError: pandas',executed_command='uv run --no-project --python .venv/bin/python --with pandas --with numpy --with pytest python -m pytest -q experiments/tools/test_static_replay.py',reproduce_command='uv run --no-project --python .venv/bin/python --with pandas==3.0.6 --with numpy==2.5.3 --with pytest==9.1.1 python -m pytest -q experiments/tools/test_static_replay.py',successful_observation='8 passed in 8.43s using an ephemeral environment resolving to the recorded versions',versions=dict(python='3.14.4',pandas='3.0.6',numpy='2.5.3',pytest='9.1.1')),checks=dict(distinct=len(checks),individual=sum(checks.values()),failures=dict(failures)),saved_diagnostics=diag,common_five_metrics=five,all_raw_artifacts_unchanged=len(protected)==19 and all(blob(x)==blob(x,OLD) for x in protected),exact_control=dict(bank_definition='Uniform eight triples (U,A,U_prime); current donor (0,A),state U; first later opposite-action donor (0,1-A),state U_prime. Second validation passes; hidden success=1{second action matches that donor state}. Rejected same-action rows are integrated out, not interpreted as two unconditional iid rows.',source_state_distribution='U fair; logging A fair and independent; donor U_prime fair independent',result=exact,enumeration=control),accepted=['Every saved per-target diagnostic and prefix-coverage count matches the prior independent reconstruction and direct production pure-function evaluation.','All five-policy numeric summaries match the corrected prior audit. The six-policy legacy MAEs are explicitly suffixed all6.','The existing replay estimates and 19 raw artifacts are byte-identical; rule_b and by_task function ASTs are unchanged.','Eight published mechanism tests pass with pandas available; independent K=3/fallback/order controls pass.'],limitations=['The eight published fixtures check mechanics rather than causal truth. The independent exhaustive control added here demonstrates exact adaptive replay value 3/4 versus true 1, while both fixed policies reproduce 1/2, without fallback or missing donors. This does not estimate bias of the observed coding benchmark.','The default repository test environment lacks pandas; test reproduction currently needs the experiment dependencies or the recorded ephemeral environment.','Legacy summary keys still use bias terminology and stitching_engages_in_share_of_episodes for the original-log eligibility fraction. Those labels do not turn this post-hoc observed discrepancy into repeated-sampling bias or the actual donor-change rate.'])
out=a.output or ROOT/'work/replay_controls_audit_8ab7fb5.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ('ref','checks','all_raw_artifacts_unchanged','common_five_metrics')},indent=2));print('EXACT_CONTROL',json.dumps(exact,indent=2));print('OUTPUT',out)

if failures:raise SystemExit("Replay audit failed; inspect the report.")
