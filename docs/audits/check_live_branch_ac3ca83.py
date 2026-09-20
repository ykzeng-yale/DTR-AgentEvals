"""Deterministic artifact audit; no candidate execution, model calls, refitting, or Monte Carlo."""
import collections, hashlib, json, math, pathlib, re, subprocess
import numpy as np
REF='ac3ca8368e0b1b05990f1ef108fe1cc4bfb1251a'
ROOT=pathlib.Path(__file__).resolve().parents[2]
BASE='results/code_routing/'
def blob(p,ref=REF):return subprocess.check_output(['git','show',f'{ref}:{p}'],cwd=ROOT)
def obj(p):return json.loads(blob(p))
def rows(p):return [json.loads(x) for x in blob(p).splitlines()]
def sha(x):return hashlib.sha256(x).hexdigest()
def hist(values):return dict(sorted(collections.Counter(values).items(),key=lambda x:str(x[0])))
counts=collections.Counter(); failures=collections.defaultdict(list)
def check(k,ok,detail=None):
 counts[k]+=1
 if not ok:failures[k].append(detail)
design=obj(BASE+'design.json');cfg=obj('experiments/code_routing/config.json');policy=obj(BASE+'learned_policy.json');vt=obj(BASE+'visible_tests.json')
# Prior logs are read solely to verify branch sampling, prefix identities, and manifest continuity, not re-audited.
parents={e['episode_id']:e for e in rows(BASE+'log/episodes.jsonl') if not e.get('error')}
prior_m=rows(BASE+'log/run_manifest.jsonl')[0]
plan=obj(BASE+'branch/branch_plan.json')
learned={tuple(k):v for k,v in policy['table']}
paths=[BASE+x for x in ['design.json','visible_tests.json','learned_policy.json','branch/branch_plan.json','live/episodes.jsonl','live/decisions.jsonl','live/run_manifest.jsonl','branch/episodes.jsonl','branch/decisions.jsonl','branch/run_manifest.jsonl','redactions.json']]+['experiments/code_routing/config.json']
hashes={p:sha(blob(p)) for p in paths}
check('design_hash_sidecar',hashes[BASE+'design.json']==blob(BASE+'design.sha256').decode().strip())
check('config_hash_design',hashes['experiments/code_routing/config.json']==design['config_sha256'])
check('branch_parent_file_hash',plan['log_sha256']==sha(blob(BASE+'log/episodes.jsonl')))
# Reproduce the one seeded draw used to freeze this sampling plan, not a Monte Carlo experiment.
eligible=sorted((e for e in parents.values() if e['split']=='confirm' and e['n_decisions']>=2),key=lambda e:e['episode_id'])
ba=design['branch_audit'];rng=np.random.default_rng(ba['seed'])
pick=sorted(rng.choice(len(eligible),size=min(ba['n_prefixes'],len(eligible)),replace=False).tolist())
expected_plan=[]
for idx in pick:
 p=eligible[idx]
 for arm in (0,1):
  role=['small','large'][arm]
  for c in range(ba['continuations_per_arm']):
   expected_plan.append(dict(episode_id=f"branch:{p['episode_id']}:{role}#{c}",parent_episode_id=p['episode_id'],task_uid=p['task_uid'],run=c,split='confirm',policy='branch_stay_'+role,forced_arm=arm,seed=int(rng.integers(1,2**31-1)),run_order=len(expected_plan)))
check('branch_sampling_and_seed_exact',expected_plan==plan['episodes'])
check('branch_eligible_count',len(eligible)==plan['n_eligible_prefixes'])
check('branch_sampling_probability',plan['sampling_probability']==len(pick)/len(eligible))
check('branch_plan_count',len(plan['episodes'])==800)
codefiles=subprocess.check_output(['git','ls-tree','-r','--name-only',REF,'experiments/code_routing','experiments/common'],cwd=ROOT).decode().splitlines()
codefiles=[p for p in codefiles if p.endswith('.py') and len(pathlib.PurePosixPath(p).parts)==3]
codefiles=sorted(p for p in codefiles if p.startswith('experiments/code_routing/'))+sorted(p for p in codefiles if p.startswith('experiments/common/'))
code_hash=sha(b''.join(blob(p) for p in codefiles))
def probability(name,s):
 if name=='always_small':return 0.0
 if name=='always_large':return 1.0
 if name=='escalate_after_first_failure':return float(s['t']>0)
 if name=='class_tailored':return float(s['t']>0 and s['fail_class']=='assertion')
 if name=='soft_escalation_d2':return .5 if s['t']==0 else 2/3
 if name=='learned':return float(learned.get((s['t'],s['x_humaneval'],s['fail_class'],s['prev_actions'][-1] if s['prev_actions'] else -1),0))
 raise ValueError(name)
reports={}
for stage in ('live','branch'):
 E=rows(BASE+stage+'/episodes.jsonl');D=rows(BASE+stage+'/decisions.jsonl');M=rows(BASE+stage+'/run_manifest.jsonl');m=M[0]
 P={p['episode_id']:p for p in (design['live_episodes'] if stage=='live' else plan['episodes'])}
 EB={e['episode_id']:e for e in E};DB={(d['episode_id'],d['attempt'],d['t']):d for d in D}
 pre=stage+':'; c=lambda key,ok,detail=None:check(pre+key,ok,detail)
 c('one_manifest',len(M)==1)
 c('manifest_initial_counts',m['n_todo']==len(P) and m['n_ok_before']==m['n_exhausted_before']==m['n_retries_in_todo']==m['torn_bytes_cut']==0)
 c('unique_episodes',len(EB)==len(E));c('unique_durable_decisions',len(DB)==len(D))
 c('episode_ids_within_plan',set(EB)<=set(P));c('decision_ids_within_plan',all(d['episode_id'] in P for d in D))
 c('manifest_design',m['design_sha256']==hashes[BASE+'design.json'])
 c('manifest_config',m['config_sha256']==hashes['experiments/code_routing/config.json'])
 c('manifest_visible_tests',m['visible_tests_sha256']==hashes[BASE+'visible_tests.json'])
 c('manifest_code',m['code_sha256']==code_hash==design['design_code_sha256'])
 c('source_at_recorded_head',m['code_sha256']==sha(b''.join(blob(p,m['git_head']) for p in codefiles)))
 for k in ('gguf','server_facts','tasks_sha256'):
  c('manifest_matches_prior_'+k,m[k]==prior_m[k])
 c('manifest_real',m['mock'] is False)
 if stage=='live':
  c('complete_3960',len(E)==len(P)==3960 and set(EB)==set(P))
  c('exact_330_confirm_tasks',set(e['task_uid'] for e in E)==set(design['confirm_tasks']))
  c('six_policies',set(e['policy'] for e in E)==set(design['live_policies']) and len(design['live_policies'])==6)
  c('two_runs_each_task_policy',all(sorted(e['run'] for e in E if e['task_uid']==t and e['policy']==p)==[0,1] for t in design['confirm_tasks'] for p in design['live_policies']))
  c('manifest_learned_hash',m['learned_policy_sha256']==hashes[BASE+'learned_policy.json'])
  c('policy_frozen_before_live_start',policy['created_utc']<m['started_utc'])
 else:
  c('plan_frozen_by_start',plan['created_utc']<=m['started_utc'])
 matched_keys=set()
 for e in E:
  eid=e['episode_id'];p=P[eid];ds=e['decisions'];offset=int(stage=='branch')
  parent=parents[p['parent_episode_id']] if offset else None
  prev=[parent['decisions'][0]['a']] if offset else []
  previous_val=parent['decisions'][0]['validation'] if offset else None
  for k in ('task_uid','run','split','policy','seed'):c('identity_'+k,e[k]==p[k],eid)
  for k in ('config_sha256','code_sha256','git_head','mock','contention_allowed','tasks_sha256','invocation','visible_tests_sha256')+(('learned_policy_sha256',) if stage=='live' else ()):
   c('episode_manifest_'+k,e[k]==m[k],eid)
  c('attempt_one',e['attempt']==1,eid);c('no_error',e['error'] is None,eid)
  c('confirm_split',e['split']=='confirm',eid)
  c('benchmark',e['benchmark']==e['task_uid'].split('/')[0],eid)
  c('stage_sequence',[d['t'] for d in ds]==list(range(offset,offset+len(ds))) and 1<=len(ds)<=3-offset,eid)
  c('counts',e['n_decisions']==len(ds)+offset and e['n_new_decisions']==len(ds),eid)
  c('visible_checks',e['n_visible_checks']==vt['tests'][e['task_uid']]['certified']['n_checks'],eid)
  c('final_code',e['final_code']==ds[-1]['code'],eid)
  c('absorption',all(not d['validation']['passed'] for d in ds[:-1]) and e['stop_reason']==('validated' if ds[-1]['validation']['passed'] else 'horizon') and (ds[-1]['validation']['passed'] or ds[-1]['t']==2),eid)
  c('penalty',math.isclose(e['penalty'],sum(d['penalty'] for d in ds)),eid)
  c('tokens',e['completion_tokens']==sum(d['completion_tokens'] for d in ds),eid)
  c('model_seconds',math.isclose(e['llm_wall_seconds'],sum(d['wall_seconds'] for d in ds)),eid)
  c('validation_timeout_aggregation',e['validation_timeouts']==sum(d['validation']['timed_out'] for d in ds),eid)
  c('utility_identity',e['success'] in (0,1) and math.isclose(e['utility'],e['success']-e['penalty']),eid)
  if offset:
   c('fork_identifiers',e['parent_episode_id']==p['parent_episode_id'] and e['fork_t']==1 and e['fork_arm']==['small','large'][p['forced_arm']],eid)
   c('parent_is_eligible',parent['split']=='confirm' and len(parent['decisions'])>=2 and not parent['decisions'][0]['validation']['passed'],eid)
   c('restoration_recorded_flags',e['restoration']==dict(transcript_hash_matches=True,tool_result_reproduced=True),eid)
   c('parent_prefix_hash_equal',ds[0]['transcript_sha256']==parent['decisions'][1]['transcript_sha256'],eid)
  prev_time=e['start_utc']
  for d in ds:
   key=(eid,e['attempt'],d['t']);ev=DB.get(key);matched_keys.add(key)
   c('matching_durable_decision',ev is not None and all(ev[k]==d[k] for k in ev if k not in ('episode_id','invocation','attempt','logged_utc')),key)
   if ev:c('episode_time_order',ev['logged_utc']>=prev_time,key);prev_time=ev['logged_utc']
   state=dict(t=d['t'],x_humaneval=int(e['benchmark']=='humaneval'),fail_class='start' if previous_val is None else previous_val['fail_class'],prev_actions=list(prev),frac_fail=0.0 if previous_val is None else previous_val['frac_fail'])
   c('preaction_state',d['state']==state,key)
   c('completed_model_alias',d['completed'] is True and d['model_alias']==d['response_model']==cfg['models'][d['action']]['alias'],key)
   c('validation_nasserts',d['validation']['n_asserts']==e['n_visible_checks'],key)
   prev.append(d['a']);previous_val=d['validation']
  c('full_action_history',e['actions']==[['small','large'][a] for a in prev],eid)
 for d in D:
  eid=d['episode_id'];p=P[eid];key=(eid,d['attempt'],d['t']);s=d['state']
  c('durable_attempt_invocation',d['attempt']==1 and d['invocation']==m['invocation'],key)
  c('durable_available_actions',d['eligible'] is True and d['available_actions']==['small','large'],key)
  c('durable_hash_format',bool(re.fullmatch('[0-9a-f]{64}',d['transcript_sha256'])),key)
  c('durable_timing',d['logged_utc']>=m['started_utc'],key)
  if stage=='live':
   prob=probability(p['policy'],s)
   c('frozen_probability',d['p_large']==prob,key)
   c('frozen_uniform',d['draw']==p['u'][d['t']] and d['source']=='policy:'+p['policy'],key)
   c('frozen_action',d['a']==int(d['draw']<prob),key)
  else:
   c('forced_assignment',d['a']==p['forced_arm'] and d['p_large']==p['forced_arm'] and d['draw'] is None and d['source']=='branch_forced',key)
   if d['t']==1:
    par=parents[p['parent_episode_id']]
    c('durable_branch_parent_hash',d['transcript_sha256']==par['decisions'][1]['transcript_sha256'],key)
    c('durable_branch_parent_state',d['state']==par['decisions'][1]['state'],key)
  c('observed_action_probability',d['b_obs']==(d['p_large'] if d['a']==1 else 1-d['p_large']),key)
  c('action_encoding_cost',d['action']==['small','large'][d['a']] and d['penalty']==cfg['call_penalty'][d['action']],key)
 c('durable_timestamp_order',all(a['logged_utc']<=b['logged_utc'] for a,b in zip(D,D[1:])))
 extras=[d for d in D if (d['episode_id'],d['attempt'],d['t']) not in matched_keys]
 if stage=='live':c('no_unmatched_decisions',not extras)
 else:
  c('unmatched_only_unserialized_episodes',all(d['episode_id'] not in EB for d in extras))
  started={d['episode_id'] for d in D}
  c('started_plan_prefix',sorted(P[e]['run_order'] for e in started)==list(range(len(started))))
 reports[stage]=dict(expected_episodes=len(P),published_episodes=len(E),published_tasks=len({e['task_uid'] for e in E}),published_parent_prefixes=len({e['parent_episode_id'] for e in E}) if stage=='branch' else None,episode_counts_by_policy=hist(e['policy'] for e in E),durable_decisions=len(D),nested_decisions=len(matched_keys),decisions_by_stage=hist(d['t'] for d in D),episodes_by_new_calls=hist(len(e['decisions']) for e in E),stop_reasons=hist(e['stop_reason'] for e in E),errors=sum(bool(e['error']) for e in E),retries=sum(e['attempt']>1 for e in E),validation_timeouts=sum(e['validation_timeouts'] for e in E),hidden_timeouts=sum(e['verify_timed_out'] for e in E),finish_reasons=hist(d['finish'] for e in E for d in e['decisions']),hack_flagged_episodes=sum(bool(e['hack_flags']) for e in E),foreign_gpu_load_episodes=sum(e['foreign_gpu_load_at_start'] for e in E),contention_check_failures=sum(e['contention_check_failed'] for e in E),unmatched_durable_decisions=[{k:d[k] for k in ('episode_id','t','logged_utc')} for d in extras],unstarted_planned_episodes=len(P)-len({d['episode_id'] for d in D}),chronology=dict(manifest_start=m['started_utc'],first_episode_start=min(e['start_utc'] for e in E),last_episode_start=max(e['start_utc'] for e in E),last_durable_decision=max(d['logged_utc'] for d in D)),redaction_affected=[dict(episode_id=e['episode_id'],fields=[f"decision[{d['t']}].{k}" for d in e['decisions'] for k,v in d.items() if isinstance(v,str) and '<HOME>' in v]) for e in E if '<HOME>' in json.dumps(e)])
redactions=obj(BASE+'redactions.json')
for r in redactions:
 if '/live/' in r['file'] and 'sha256_after' in r:
  check('live_redaction_after_hash',sha(blob(r['file']))==r['sha256_after'])
  check('live_redaction_count',blob(r['file']).decode().count('<HOME>')==r['masked']==r['occurrences'])
report=dict(ref=REF,scope='New live/branch artifact consistency only; no candidate execution, model calls, outcome comparisons, model fitting, or Monte Carlo. Prior log read only as parent sampling population and input hash.',numpy_version=np.__version__,hashes=hashes,code_digest=dict(sha256=code_hash,n_files=len(codefiles)),branch_plan=dict(expected_continuations=800,eligible_prefixes=len(eligible),sampled_prefixes=len(pick),distinct_sampled_tasks=len({eligible[i]['task_uid'] for i in pick}),sampling_probability=plan['sampling_probability'],seed=ba['seed'],sampling_and_seed_reconstruction='exact' if not failures.get('branch_sampling_and_seed_exact') else 'mismatch'),stages=reports,checks=dict(distinct=len(counts),individual=sum(counts.values()),failures=dict(failures)),limitations=['Full task source is absent in this checkout: initial prompt hashes cannot be reconstructed; branch first-decision hash equality to its parent is independently checked, while tool reproduction itself is a recorded flag and was not reexecuted.','Original model files, server binaries, and remote runtime are not independently inspected; manifest consistency does not prove physical execution identity.','Live log has one redacted first-stage trace. Pre-redaction bytes are absent; the later transcript hash remains the original hash and cannot be reconstructed from the sanitized trace.','Branch file is a partial concurrent snapshot: unmatched durable decisions are started episodes without a completed episode row, not verified completed executions; the committed run.lock does not establish current remote liveness.','No episode-completion timestamps: observed decision/start times establish chronology only as recorded, not an independent wall-clock execution attestation.','No hidden reward recomputation, model-performance comparison, causal estimation, interval validation, or branch-result analysis was performed.'])
out=ROOT/'work'/'code_routing_live_branch_audit_ac3ca83.json'
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report['checks'],indent=2));print('OUTPUT',out)
raise SystemExit(bool(failures))
