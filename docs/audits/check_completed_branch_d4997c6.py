"""Portable, deterministic committed-artifact audit. No candidate execution or model calls.
Run from a repository checkout, or pass --repo; writes only the requested audit JSON.
"""
import argparse, collections, hashlib, json, math, pathlib, re, subprocess
REF='d4997c68ca93a4d5835bcc578470af472be311b2'
OLD='ac3ca8368e0b1b05990f1ef108fe1cc4bfb1251a'
a=argparse.ArgumentParser();a.add_argument('--repo',type=pathlib.Path);a.add_argument('--output',type=pathlib.Path);args=a.parse_args()
ROOT=args.repo or pathlib.Path(subprocess.check_output(['git','rev-parse','--show-toplevel']).decode().strip())
BASE='results/code_routing/';BR=BASE+'branch/'
def blob(p,ref=REF):return subprocess.check_output(['git','show',f'{ref}:{p}'],cwd=ROOT)
def obj(p,ref=REF):return json.loads(blob(p,ref))
def rows(p,ref=REF):return [json.loads(l) for l in blob(p,ref).splitlines()]
def sha(b):return hashlib.sha256(b).hexdigest()
def hist(v):return dict(sorted(collections.Counter(v).items(),key=lambda kv:str(kv[0])))
checks=collections.Counter();failures=collections.defaultdict(list)
def check(k,ok,detail=None):
 checks[k]+=1
 if not ok:failures[k].append(detail)
E=rows(BR+'episodes.jsonl');D=rows(BR+'decisions.jsonl');M=rows(BR+'run_manifest.jsonl')
OE=rows(BR+'episodes.jsonl',OLD);OD=rows(BR+'decisions.jsonl',OLD)
plan=obj(BR+'branch_plan.json');design=obj(BASE+'design.json');cfg=obj('experiments/code_routing/config.json');vt=obj(BASE+'visible_tests.json')
P={p['episode_id']:p for p in plan['episodes']};EB={e['episode_id']:e for e in E};MB={m['invocation']:m for m in M}
parents={e['episode_id']:e for e in rows(BASE+'log/episodes.jsonl') if not e.get('error')}
key=lambda d:(d['episode_id'],d['invocation'],d['attempt'],d['t'])
DB={key(d):d for d in D};fullkeys=set();oldids={e['episode_id'] for e in OE}
paths=[BR+x for x in ('branch_plan.json','episodes.jsonl','decisions.jsonl','run_manifest.jsonl')]+[BASE+x for x in ('design.json','visible_tests.json','redactions.json')]+['experiments/code_routing/config.json','experiments/tools/verify_stage.py','experiments/code_routing/protocol.md']
hashes={p:sha(blob(p)) for p in paths}
for p in ('episodes.jsonl','decisions.jsonl','run_manifest.jsonl'):
 check('snapshot_byte_prefix_'+p,blob(BR+p).startswith(blob(BR+p,OLD)))
check('branch_plan_unchanged',blob(BR+'branch_plan.json')==blob(BR+'branch_plan.json',OLD))
check('complete_unique_800',len(E)==len(EB)==len(P)==800 and set(EB)==set(P))
check('durable_unique_full_key',len(DB)==len(D))
check('two_unique_manifests',len(M)==len(MB)==2)
check('exact_increment_665',len(E)-len(OE)==665)
check('manifest_resume_counts',M[0]['n_todo']==800 and M[0]['n_ok_before']==0 and M[1]['n_todo']==665 and M[1]['n_ok_before']==135)
check('manifest_no_recorded_retries',all(m['n_retries_in_todo']==m['n_exhausted_before']==m['torn_bytes_cut']==0 for m in M))
check('retained_survivor_partition',{e['episode_id'] for e in E if e['invocation']==M[0]['invocation']}==oldids)
check('resume_complement_partition',{e['episode_id'] for e in E if e['invocation']==M[1]['invocation']}==set(P)-oldids)
check('plan_prefix_population_hash',plan['log_sha256']==sha(blob(BASE+'log/episodes.jsonl')))
check('plan_task_confirm',all(p['task_uid'] in design['confirm_tasks'] for p in P.values()))
check('plan_200_parents',len({p['parent_episode_id'] for p in P.values()})==200)
for parent_id in {p['parent_episode_id'] for p in P.values()}:
 pp=[p for p in P.values() if p['parent_episode_id']==parent_id]
 check('four_planned_continuations_per_parent',sorted((p['forced_arm'],p['run']) for p in pp)==[(0,0),(0,1),(1,0),(1,1)],parent_id)
codefiles=subprocess.check_output(['git','ls-tree','-r','--name-only',REF,'experiments/code_routing','experiments/common'],cwd=ROOT).decode().splitlines()
codefiles=[p for p in codefiles if p.endswith('.py') and len(pathlib.PurePosixPath(p).parts)==3]
codefiles=sorted(p for p in codefiles if p.startswith('experiments/code_routing/'))+sorted(p for p in codefiles if p.startswith('experiments/common/'))
code_hash=sha(b''.join(blob(p) for p in codefiles))
for m in M:
 inv=m['invocation']
 check('manifest_config',m['config_sha256']==hashes['experiments/code_routing/config.json']==design['config_sha256'],inv)
 check('manifest_design',m['design_sha256']==hashes[BASE+'design.json']==blob(BASE+'design.sha256').decode().strip(),inv)
 check('manifest_visible',m['visible_tests_sha256']==hashes[BASE+'visible_tests.json'],inv)
 check('manifest_code',m['code_sha256']==code_hash==design['design_code_sha256'],inv)
 check('code_at_recorded_head',sha(b''.join(blob(p,m['git_head']) for p in codefiles))==m['code_sha256'],inv)
 for k in ('tasks_sha256','gguf','server_facts','config_sha256','code_sha256','visible_tests_sha256','design_sha256'):
  check('resume_provenance_'+k,m[k]==M[0][k],inv)
 check('no_code_change_flag',m['code_changed_since_previous_invocation'] is False,inv)
 check('real_records',m['mock'] is False,inv)
for e in E:
 eid=e['episode_id'];p=P[eid];m=MB[e['invocation']];ds=e['decisions'];par=parents[p['parent_episode_id']]
 for k in ('task_uid','run','split','policy','seed','parent_episode_id'):check('episode_identity_'+k,e[k]==p[k],eid)
 for k in ('config_sha256','code_sha256','git_head','mock','contention_allowed','tasks_sha256','invocation','visible_tests_sha256'):check('episode_manifest_'+k,e[k]==m[k],eid)
 check('episode_attempt_one',e['attempt']==1,eid)
 check('episode_no_error',e['error'] is None,eid)
 check('episode_confirm',e['split']=='confirm',eid)
 check('episode_benchmark',e['benchmark']==e['task_uid'].split('/')[0],eid)
 check('fork_fields',e['fork_t']==1 and e['fork_arm']==['small','large'][p['forced_arm']],eid)
 check('parent_eligible',par['split']=='confirm' and len(par['decisions'])>=2 and not par['decisions'][0]['validation']['passed'],eid)
 check('restoration_flags',e['restoration']==dict(transcript_hash_matches=True,tool_result_reproduced=True),eid)
 check('initial_branch_parent_hash',ds[0]['transcript_sha256']==par['decisions'][1]['transcript_sha256'],eid)
 check('stage_order',[d['t'] for d in ds]==list(range(1,1+len(ds))) and len(ds) in (1,2),eid)
 check('episode_counts',e['n_decisions']==1+len(ds) and e['n_new_decisions']==len(ds),eid)
 check('final_code',e['final_code']==ds[-1]['code'],eid)
 check('visible_check_count',e['n_visible_checks']==vt['tests'][e['task_uid']]['certified']['n_checks'],eid)
 check('absorption',all(not d['validation']['passed'] for d in ds[:-1]) and e['stop_reason']==('validated' if ds[-1]['validation']['passed'] else 'horizon') and (ds[-1]['validation']['passed'] or ds[-1]['t']==2),eid)
 check('aggregate_penalty',math.isclose(e['penalty'],sum(d['penalty'] for d in ds)),eid)
 check('aggregate_tokens',e['completion_tokens']==sum(d['completion_tokens'] for d in ds),eid)
 check('aggregate_llm_time',math.isclose(e['llm_wall_seconds'],sum(d['wall_seconds'] for d in ds)),eid)
 check('aggregate_validation_timeout',e['validation_timeouts']==sum(d['validation']['timed_out'] for d in ds),eid)
 prev=[par['decisions'][0]['a']];val=par['decisions'][0]['validation'];last_time=e['start_utc']
 for d in ds:
  k=(eid,e['invocation'],e['attempt'],d['t']);fullkeys.add(k);ev=DB.get(k)
  check('nested_durable_match',ev is not None and all(ev[f]==d[f] for f in ev if f not in ('episode_id','invocation','attempt','logged_utc')),k)
  if ev:check('preaction_timestamps',ev['logged_utc']>=last_time,k);last_time=ev['logged_utc']
  state=dict(t=d['t'],x_humaneval=int(e['benchmark']=='humaneval'),fail_class=val['fail_class'],prev_actions=list(prev),frac_fail=val['frac_fail'])
  check('history_state',d['state']==state,k)
  check('model_alias_and_completion',d['completed'] is True and d['model_alias']==d['response_model']==cfg['models'][d['action']]['alias'],k)
  check('validation_check_count',d['validation']['n_asserts']==e['n_visible_checks'],k)
  prev.append(d['a']);val=d['validation']
 check('full_actions',e['actions']==[['small','large'][x] for x in prev],eid)
for d in D:
 k=key(d);p=P[d['episode_id']];m=MB[d['invocation']]
 check('decision_attempt_one',d['attempt']==1,k)
 check('decision_eligibility',d['eligible'] is True and d['available_actions']==['small','large'],k)
 check('decision_forced_action',d['a']==p['forced_arm'] and d['p_large']==p['forced_arm'] and d['draw'] is None and d['source']=='branch_forced',k)
 check('decision_observed_probability',d['b_obs']==1.0,k)
 check('decision_encoding_cost',d['action']==['small','large'][d['a']] and d['penalty']==cfg['call_penalty'][d['action']],k)
 check('decision_timestamp',d['logged_utc']>=m['started_utc'],k)
 check('decision_hash_syntax',bool(re.fullmatch('[0-9a-f]{64}',d['transcript_sha256'])),k)
 if d['t']==1:
  pd=parents[p['parent_episode_id']]['decisions'][1]
  check('durable_parent_hash_state',d['transcript_sha256']==pd['transcript_sha256'] and d['state']==pd['state'],k)
check('all_durable_timestamp_order',all(x['logged_utc']<=y['logged_utc'] for x,y in zip(D,D[1:])))
extra=[d for d in D if key(d) not in fullkeys]
check('only_retained_snapshot_orphans',len(extra)==5 and all(d in OD and d['invocation']==M[0]['invocation'] and d['episode_id'] not in oldids for d in extra))
check('orphans_have_reexecuted_records',all(EB[d['episode_id']]['invocation']==M[1]['invocation'] for d in extra))
groups=collections.defaultdict(list)
for d in D:groups[(d['episode_id'],d['attempt'],d['t'])].append(d)
duplicates=[]
for k,g in groups.items():
 if len(g)>1:
  changed=[f for f in g[0] if g[0][f]!=g[1][f]]
  check('duplicate_semantics_equal',len(g)==2 and set(changed)=={'invocation','logged_utc'},k)
  duplicates.append(dict(episode_id=k[0],attempt=k[1],t=k[2],changed_fields=changed))
retained_calls={stage:sum(len(e['decisions']) for e in rows(BASE+stage+'/episodes.jsonl')) for stage in ('pilot','log','live','branch')}
check('retained_call_accounting',retained_calls==dict(pilot=163,log=6063,live=5504,branch=1434))
report=dict(ref=REF,prior_ref=OLD,scope='Completed branch artifact consistency and read-only guard review; no candidate/model execution, outcome analysis, Monte Carlo, or new collection.',hashes=hashes,
 retained_call_accounting=dict(by_stage=retained_calls,log_live_branch=sum(retained_calls[s] for s in ('log','live','branch')),all_four_stages=sum(retained_calls.values()),scope='Counts of nested decisions attached to retained completed episodes. Excludes unrecovered original executions and environment-construction test-writer calls; not total physical inference cost.'),
 retry_accounting=dict(error_based_retry_attempts=0,retained_records_with_attempt_above_one=0,second_invocation_complement_episodes=665,scope='Zero error-based retry attempts is verified. The 665 recovery executions are a separate restart/reexecution category; their claimed prior completion is operator-reported.'),
 counts=dict(plan=800,episodes=len(E),distinct_tasks=len({e['task_uid'] for e in E}),distinct_parent_prefixes=len({e['parent_episode_id'] for e in E}),nested_decisions=len(fullkeys),durable_decisions=len(D),durable_decisions_without_retained_completion=len(extra),affected_reexecuted_episode_ids=sorted({d['episode_id'] for d in extra}),episodes_by_invocation=hist(e['invocation'] for e in E),durable_by_invocation=hist(d['invocation'] for d in D),nested_by_stage=hist(d['t'] for e in E for d in e['decisions']),error_rows=sum(bool(e['error']) for e in E),attempts=hist(e['attempt'] for e in E),finish_reasons=hist(d['finish'] for e in E for d in e['decisions']),validation_timeouts=sum(e['validation_timeouts'] for e in E),hidden_timeouts=sum(e['verify_timed_out'] for e in E),foreign_gpu_load=sum(e['foreign_gpu_load_at_start'] for e in E),restoration_both_true=sum(e['restoration']==dict(transcript_hash_matches=True,tool_result_reproduced=True) for e in E)),
 chronology={m['invocation']:dict(manifest_start=m['started_utc'],first_episode_start=min(e['start_utc'] for e in E if e['invocation']==m['invocation']),last_episode_start=max(e['start_utc'] for e in E if e['invocation']==m['invocation']),last_durable_decision=max(d['logged_utc'] for d in D if d['invocation']==m['invocation'])) for m in M},
 duplicate_keys_without_invocation=duplicates,checks=dict(distinct=len(checks),individual=sum(checks.values()),failures=dict(failures)),
 independently_verified_incident_consistency=['The 135 previously published episodes and 243 durable decisions survive as exact byte prefixes.','The second manifest specifies 135 resolved and 665 planned; exactly those 665 complementary plan IDs have new episode rows, with unchanged plan seeds and source/config/model manifest values.','Five old-invocation decision rows over four episode IDs lack an old completion row and are repeated under the second invocation. Invocation is required in the durable-record key because both invocations label attempt=1.'],
 reported_not_independently_verified=['The first invocation completed all 800; 665 original completion records were lost. Only 135 old completion rows plus five pre-action rows of four other episodes are committed.','The causal mechanism was rebase replacement of open inodes, the original runner exited cleanly, and no person observed any lost outcome. No deleted-inode recovery, process exit log, or inode evidence was supplied.','Same seeds and frozen code imply matching requested conditions, not proof of identical generated outputs or outcomes for lost executions.','The sentence "none that can bias a result" requires an outcome-independent loss/reexecution assumption and runtime stability; committed records alone cannot establish it.'],
 verify_stage_static_review=[dict(severity='material',finding='The pass condition ignores res[torn]. An otherwise complete episode file with a tolerated final unparsable line can print torn=1 while returning OK.'),dict(severity='material',finding='It checks resolved ID sets only; successful duplicates collapse to the last row, and a row with the right ID but missing error/content fields can count as good. It does not validate decisions, invocation identity, seeds, frozen plan hashes, model/source provenance, or restoration.'),dict(severity='material',finding='The quiet-period check uses only episodes.jsonl mtime; there is no OS lock or atomic snapshot through commit/rebase. A new writer can start after the check (TOCTOU), and decisions/manifest may still change.'),dict(severity='scope',finding='PID liveness applies to the current host and treats every OSError as dead, including a permission error. A cloned or absent lock cannot prove remote liveness.'),dict(severity='scope',finding='Passing permits exhausted error episodes as intention-to-treat outcomes, so completeness is not equivalent to error-free success. No such error rows occur in this archive.')],
 limitations=['Parent hashes are compared as stored; task source needed to reconstruct initial prompts is absent, and no tool restoration or hidden reward was reexecuted.','Model hashes and runtime metadata are consistent declarations; the physical model/server environment and original lost files were not inspected.','Current retained call counts omit unrecovered original executions. Exact total physical inference cost cannot be reconstructed from the archived branch records.','Restoration checks prove only the recorded transcript/tool-result comparisons, not bitwise full runtime state or identical stochastic continuation.','The new guard improves count checking but does not establish that historical log/live stages were idle when committed; local mtime cannot retrospectively attest that.'])
out=args.output or ROOT/'work'/'code_routing_completed_branch_audit_d4997c6.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report['checks'],indent=2));print('OUTPUT',out)
raise SystemExit(bool(failures))
