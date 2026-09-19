"""Read-only committed-artifact consistency audit. Never runs candidate/model code."""
import collections, hashlib, json, math, pathlib, re, subprocess
REF='035d245f6fa10450f7cf89420bc1947d4c54aebc'
ROOT=pathlib.Path(__file__).resolve().parents[2]
def blob(p,ref=REF):
    return subprocess.check_output(['git','show',f'{ref}:{p}'],cwd=ROOT)
def sha(x):return hashlib.sha256(x).hexdigest()
def obj(p):return json.loads(blob(p))
def rows(p):return [json.loads(x) for x in blob(p).splitlines()]
base='results/code_routing/'
design=obj(base+'design.json'); cfg=obj('experiments/code_routing/config.json')
eps=rows(base+'log/episodes.jsonl'); decs=rows(base+'log/decisions.jsonl')
manifest=rows(base+'log/run_manifest.jsonl'); vt=obj(base+'visible_tests.json')
policy=obj(base+'learned_policy.json'); redactions=obj(base+'redactions.json')
failures=collections.defaultdict(list); totals=collections.Counter()
def check(name,ok,detail=None):
    totals[name]+=1
    if not ok:failures[name].append(detail)
def hist(it):return dict(sorted(collections.Counter(it).items(),key=lambda kv:str(kv[0])))
plans={e['episode_id']:e for e in design['log_episodes']}
ep_by={e['episode_id']:e for e in eps}
events={(d['episode_id'],d['attempt'],d['t']):d for d in decs}
check('expected_episodes',len(eps)==4488==len(plans))
check('episode_ids_unique',len(ep_by)==len(eps))
check('episode_ids_complete',set(ep_by)==set(plans))
check('decision_keys_unique',len(events)==len(decs))
check('decision_count_matches_nested',len(decs)==sum(len(e['decisions']) for e in eps))
check('episode_tasks_561',len({e['task_uid'] for e in eps})==561)
check('runs_8_each',all(n==8 for n in collections.Counter(e['task_uid'] for e in eps).values()))
check('run_orders_permutation',sorted(e['run_order'] for e in plans.values())==list(range(4488)))
splitsets={k:set(design[k+'_tasks']) for k in ('pilot','train','confirm')}
check('split_sizes',list(map(len,(splitsets['pilot'],splitsets['train'],splitsets['confirm'])))==[30,231,330])
check('split_disjoint',all(not splitsets[a]&splitsets[b] for a,b in [('pilot','train'),('pilot','confirm'),('train','confirm')]))
check('split_union_591',len(set.union(*splitsets.values()))==591)
check('episode_split_sets',all({e['task_uid'] for e in eps if e['split']==s}==splitsets[s] for s in ('train','confirm')))
check('manifest_single',len(manifest)==1)
m=manifest[0]
hashes={p:sha(blob(p)) for p in [base+'design.json',base+'visible_tests.json',base+'learned_policy.json',base+'log/episodes.jsonl',base+'log/decisions.jsonl','experiments/code_routing/config.json']}
check('design_hash',hashes[base+'design.json']==blob(base+'design.sha256').decode().strip()==m['design_sha256'])
check('config_hash',hashes['experiments/code_routing/config.json']==design['config_sha256']==m['config_sha256'])
check('visible_hash',hashes[base+'visible_tests.json']==m['visible_tests_sha256'])
check('visible_tasks_cover_design',set(vt['tests'])==set.union(*splitsets.values()))
codefiles=subprocess.check_output(['git','ls-tree','-r','--name-only',REF,'experiments/code_routing','experiments/common'],cwd=ROOT).decode().splitlines()
codefiles=[p for p in codefiles if p.endswith('.py') and len(pathlib.PurePosixPath(p).parts)==3]
codefiles=sorted(p for p in codefiles if p.startswith('experiments/code_routing/'))+sorted(p for p in codefiles if p.startswith('experiments/common/'))
current_codehash=sha(b''.join(blob(p) for p in codefiles))
recorded_codehash=sha(b''.join(blob(p,m['git_head']) for p in codefiles))
check('code_hash_reconstructed_current',current_codehash==m['code_sha256']==design['design_code_sha256'])
check('code_hash_reconstructed_recorded_head',recorded_codehash==m['code_sha256'])
check('policy_train_counts',policy['n_train_episodes']==1848==sum(e['split']=='train' for e in eps) and policy['n_train_tasks']==231)
check('policy_valid_unique_table',len({tuple(k) for k,v in policy['table']})==len(policy['table']) and all(v in (0,1) for k,v in policy['table']))
first=[]
for e in eps:
    eid=e['episode_id']; p=plans[eid]; ds=e['decisions']
    for k in ['task_uid','run','split','policy','seed']:check('episode_identity_'+k,e[k]==p[k],eid)
    check('episode_benchmark',e['benchmark']==e['task_uid'].split('/')[0],eid)
    check('episode_attempt_one',e['attempt']==1,eid)
    check('episode_no_error',e['error'] is None,eid)
    check('episode_real',e['mock'] is False,eid)
    check('episode_horizon',1<=len(ds)<=3 and [d['t'] for d in ds]==list(range(len(ds))),eid)
    check('episode_count_fields',len(ds)==e['n_decisions']==e['n_new_decisions']==len(e['actions']),eid)
    for k in ['config_sha256','code_sha256','git_head','mock','contention_allowed','tasks_sha256','invocation','visible_tests_sha256']:
        check('episode_manifest_'+k,e[k]==m[k],eid)
    check('episode_visible_checks',e['n_visible_checks']==vt['tests'][e['task_uid']]['certified']['n_checks'],eid)
    check('episode_action_history',e['actions']==[d['action'] for d in ds],eid)
    check('episode_final_code',e['final_code']==ds[-1]['code'],eid)
    check('absorption_no_postpass_decisions',all(not d['validation']['passed'] for d in ds[:-1]),eid)
    check('absorption_terminal_rule',e['stop_reason']==('validated' if ds[-1]['validation']['passed'] else 'horizon') and (ds[-1]['validation']['passed'] or len(ds)==3),eid)
    check('aggregate_penalties',math.isclose(e['penalty'],sum(d['penalty'] for d in ds)),eid)
    check('aggregate_tokens',e['completion_tokens']==sum(d['completion_tokens'] for d in ds),eid)
    check('aggregate_llm_seconds',math.isclose(e['llm_wall_seconds'],sum(d['wall_seconds'] for d in ds)),eid)
    check('aggregate_validation_timeouts',e['validation_timeouts']==sum(d['validation']['timed_out'] for d in ds),eid)
    check('outcome_field_internal_identity',e['success'] in (0,1) and math.isclose(e['utility'],e['success']-e['penalty']),eid)
    check('first_block_assignment',ds[0]['a']==p['a0_block'],eid)
    prev_time=e['start_utc']
    for d in ds:
        t=d['t']; key=(eid,e['attempt'],t); ev=events.get(key)
        check('decision_event_exists',ev is not None,key)
        if ev:
            check('decision_nested_matches_durable',all(ev[k]==d[k] for k in ev if k not in ('episode_id','invocation','attempt','logged_utc')),key)
            check('decision_event_invocation',ev['invocation']==e['invocation'],key)
            check('decision_times_after_start_ordered',ev['logged_utc']>=prev_time,key);prev_time=ev['logged_utc']
            check('decision_precedes_policy_freeze',ev['logged_utc']<=policy['created_utc'],key)
        check('decision_eligible',d['eligible'] is True and d['available_actions']==['small','large'],key)
        check('assignment_known_half',d['p_large']==d['b_obs']==design['p_large']==cfg['p_large']==0.5,key)
        check('assignment_frozen_draw',d['draw']==p['u'][t] and d['source']=='design_u',key)
        check('assignment_draw_action',d['a']==int(d['draw']<0.5) and d['action']==['small','large'][d['a']],key)
        check('assignment_cost',d['penalty']==cfg['call_penalty'][d['action']],key)
        check('assignment_model',d['model_alias']==d['response_model']==cfg['models'][d['action']]['alias'],key)
        check('decision_completed',d['completed'] is True,key)
        check('decision_hash_format',bool(re.fullmatch('[0-9a-f]{64}',d['transcript_sha256'])),key)
        state=dict(t=t,x_humaneval=int(e['benchmark']=='humaneval'),fail_class='start' if t==0 else ds[t-1]['validation']['fail_class'],prev_actions=[x['a'] for x in ds[:t]],frac_fail=0.0 if t==0 else ds[t-1]['validation']['frac_fail'])
        check('decision_state_history',d['state']==state,key)
        check('decision_validation_checks',d['validation']['n_asserts']==e['n_visible_checks'],key)
    first.append((p['run_order'],e['start_utc']))
check('no_orphan_decisions',all(d['episode_id'] in ep_by for d in decs))
check('durable_timestamps_nondecreasing',all(a['logged_utc']<=b['logged_utc'] for a,b in zip(decs,decs[1:])))
check('runorder_start_timestamps_nondecreasing',all(a[1]<=b[1] for a,b in zip(sorted(first),sorted(first)[1:])))
for task in splitsets['train']|splitsets['confirm']:
    es=[e for e in eps if e['task_uid']==task]
    check('task_run_indices',sorted(e['run'] for e in es)==list(range(8)),task)
    check('task_first_action_exact_block',sum(e['decisions'][0]['a'] for e in es)==4,task)
for r in redactions:
    raw=blob(r['file']);affected=[e['episode_id'] for e in eps if r['placeholder'] in json.dumps(e)]
    check('redaction_after_hash',sha(raw)==r['sha256_after'])
    check('redaction_occurrences',raw.decode().count(r['placeholder'])==r['occurrences_masked'])
    check('redaction_episode_set',set(affected)==set(r['episodes_affected']))
    check('redaction_split',all(ep_by[e]['split']==r['split'] for e in affected))
report=dict(ref=REF,scope='Artifact consistency only; no candidate execution, model calls, Monte Carlo, policy ranking, or outcome-based scientific analysis.',
 counts=dict(episodes=len(eps),tasks=len({e['task_uid'] for e in eps}),decisions=len(decs),episodes_by_split=hist(e['split'] for e in eps),tasks_by_split={s:len(x) for s,x in splitsets.items()},decisions_by_stage=hist(d['t'] for d in decs),decisions_by_stage_action=hist(f"{d['t']}:{d['action']}" for d in decs),episodes_by_number_decisions=hist(len(e['decisions']) for e in eps),stop_reasons=hist(e['stop_reason'] for e in eps),attempts=hist(e['attempt'] for e in eps),errors=sum(e['error'] is not None for e in eps),mock_episodes=sum(e['mock'] for e in eps),incomplete_decisions=sum(not d['completed'] for e in eps for d in e['decisions']),validation_timeouts=sum(e['validation_timeouts'] for e in eps),hidden_verifier_timeouts=sum(e['verify_timed_out'] for e in eps),finish_reasons=hist(d['finish'] for e in eps for d in e['decisions']),contention_flags=sum(e['foreign_gpu_load_at_start'] for e in eps),contention_check_failures=sum(e['contention_check_failed'] for e in eps)),
 hashes=hashes,code_digest=dict(reconstructed_current=current_codehash,reconstructed_recorded_head=recorded_codehash,n_python_files=len(codefiles)),
 chronology=dict(manifest_start=m['started_utc'],first_start=min(e['start_utc'] for e in eps),last_start=max(e['start_utc'] for e in eps),first_durable_decision=min(d['logged_utc'] for d in decs),last_durable_decision=max(d['logged_utc'] for d in decs),policy_created=policy['created_utc']),
 checks=dict(distinct_checks=len(totals),individual_checks=sum(totals.values()),failures=dict(failures)),
 redactions=redactions,
 limitations=['Task file is not in this checkout or committed; its claimed input hash and full prompt/transcript hashes cannot be reconstructed here.', 'Pre-redaction file is absent. The before-hash and four original strings are declarations, not independently revalidated. All published pre-action hashes remain original hashes, so a redacted repair history will not reconstruct them.', 'Pinned GGUF hashes and server/runtime facts are recorded, but this audit does not reread original model files or prove which server binary/model executed.', 'No completion timestamps or raw HTTP request records: decision timestamps precede learned-policy timestamp but completion-before-fit is supported by recorded counts/code rather than independently measured end timestamps.', 'Learning artifact records counts/objective/table but no input-log/source/config digest; train-only filtering was inspected in source, not independently refit or runtime-proven.', 'Four workers imply completion order need not match randomized dispatch order; order checks use timestamps and design identities.', 'Operational consistency does not independently validate hidden rewards, sandbox execution, model quality, causal estimates, uncertainty intervals, or robustness.'])
out=ROOT/'work'/'code_routing_artifact_audit_035d245.json'
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report['checks'],indent=2))
print('OUTPUT',out)
raise SystemExit(bool(failures))
