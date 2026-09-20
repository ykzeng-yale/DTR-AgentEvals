"""Deterministic gate counterexamples, isolated under temporary directories.
Copies only the pinned publication gate/common helper, never executes candidate code.
Run from repo root or pass --repo. Writes only an audit JSON under work by default.
"""
import argparse, copy, hashlib, json, pathlib, subprocess, sys, tempfile
REF='6f9202613a6e5c38ad4d7e733912495d3f138ea2'; PREV='29ee443cc3ba1d00bb7f37e90f8a8915e2a9357c'
ap=argparse.ArgumentParser();ap.add_argument('--repo',type=pathlib.Path);ap.add_argument('--output',type=pathlib.Path);args=ap.parse_args()
ROOT=args.repo or pathlib.Path(__file__).resolve().parents[2]
def blob(p,ref=REF):return subprocess.check_output(['git','show',f'{ref}:{p}'],cwd=ROOT)
def sha(b):return hashlib.sha256(b).hexdigest()
SOURCES={ref:(blob('experiments/tools/verify_stage.py',ref),blob('experiments/code_routing/common.py',ref)) for ref in (PREV,REF)}
cfg={'max_attempts_per_episode':3};cfg_raw=json.dumps(cfg).encode();vt_raw=b'{}'
taskhash='2'*64;sourcehash='3'*64;transcripthash='4'*64
metadata=dict(config_sha256=sha(cfg_raw),tasks_sha256=taskhash,visible_tests_sha256=sha(vt_raw),code_sha256=sourcehash,invocation='inv-A',attempt=1)
def fixture(stage):
 t=int(stage=='branch')
 dec=dict(t=t,eligible=True,available_actions=['small','large'],state=dict(t=t,x_humaneval=0,fail_class='assertion' if t else 'start',prev_actions=[0] if t else [],frac_fail=1.0 if t else 0.0),a=0,action='small',p_large=0.0 if t else .5,b_obs=1.0 if t else .5,draw=None if t else .75,source='branch_forced' if t else 'design_u',penalty=.01,transcript_sha256=transcripthash)
 nested=dict(dec,completed=True,model_alias='small',response_model='small',reply='fixture data only',code='fixture data only',validation=dict(passed=True,fail_class='none',frac_fail=0.0,timed_out=False))
 ep=dict(episode_id='e1',task_uid='t1',split='confirm',run=0,seed=7,policy='branch_stay_small' if t else 'randomized_log',error=None,decisions=[nested],n_new_decisions=1,n_decisions=1+t,**metadata)
 if t:ep.update(parent_episode_id='parent1',fork_t=1,fork_arm='small',restoration=dict(transcript_hash_matches=True,tool_result_reproduced=True))
 durable=dict(episode_id='e1',invocation='inv-A',attempt=1,logged_utc='2026-09-20T00:00:01Z',**dec)
 frozen=dict(episode_id='e1',task_uid='t1',run=0,split='confirm',seed=7,policy=ep['policy'])
 if t:frozen.update(parent_episode_id='parent1',forced_arm=0)
 return dict(stage=stage,episodes=[ep],decisions=[durable],manifest=[dict(invocation='inv-A',**{k:v for k,v in metadata.items() if k not in ('invocation','attempt')})],frozen=frozen,episode_torn=False,decision_torn=False)
def omit_metadata(f):
 for k in ('config_sha256','tasks_sha256','visible_tests_sha256'):f['episodes'][0].pop(k)
def null_metadata(f):
 for k in ('config_sha256','tasks_sha256','visible_tests_sha256'):f['episodes'][0][k]=None
def wrong_inv(f):f['decisions'][0]['invocation']='inv-NOT-IN-EPISODE-OR-MANIFEST'
def no_inv(f):f['decisions'][0].pop('invocation')
def inconsistent_action(f):f['decisions'][0].update(a=1,action='large')
def forged_hash(f):f['episodes'][0]['decisions'][0]['transcript_sha256']='9'*64;f['decisions'][0]['transcript_sha256']='9'*64
def mutate_branch_parent(f):f['episodes'][0]['parent_episode_id']='nonexistent-parent'
def duplicate(f):f['episodes'].append(copy.deepcopy(f['episodes'][0]))
cases=[
 ('clean_log','log',False,lambda f:None),('clean_branch','branch',False,lambda f:None),
 ('torn_episode_tail','log',True,lambda f:f.update(episode_torn=True)),
 ('torn_decision_tail','log',True,lambda f:f.update(decision_torn=True)),
 ('duplicate_completed_episode','log',True,duplicate),
 ('wrong_config_hash','log',True,lambda f:f['episodes'][0].update(config_sha256='9'*64)),
 ('wrong_tasks_hash','log',True,lambda f:f['episodes'][0].update(tasks_sha256='9'*64)),
 ('wrong_visible_hash','log',True,lambda f:f['episodes'][0].update(visible_tests_sha256='9'*64)),
 ('missing_invocation_key','log',True,no_inv),
 ('orphan_episode_id','log',True,lambda f:f['decisions'][0].update(episode_id='ghost')),
 ('claimed_restoration_missing_parent','branch',True,lambda f:f['episodes'][0].pop('parent_episode_id')),
 ('false_restoration_flags','branch',True,lambda f:f['episodes'][0].update(restoration=dict(transcript_hash_matches=False,tool_result_reproduced=False))),
 ('missing_restoration','branch',True,lambda f:f['episodes'][0].pop('restoration')),
 ('true_flags_nonexistent_parent','branch',True,mutate_branch_parent),
 ('true_flags_parent_hash_mismatch','branch',True,forged_hash),
 ('missing_required_metadata','log',True,omit_metadata),
 ('null_required_metadata','log',True,null_metadata),
 ('wrong_source_hash','log',True,lambda f:f['episodes'][0].update(code_sha256='9'*64)),
 ('wrong_frozen_task_and_seed','log',True,lambda f:f['episodes'][0].update(task_uid='wrong-task',seed=999)),
 ('null_invocation_value','log',True,lambda f:f['decisions'][0].update(invocation=None)),
 ('mismatched_invocation','log',True,wrong_inv),
 ('missing_decisions_file','log',True,lambda f:f.update(decisions=None)),
 ('empty_decisions_file','log',True,lambda f:f.update(decisions=[])),
 ('nested_durable_action_mismatch','log',True,inconsistent_action),
 ('missing_run_manifest','log',True,lambda f:f.update(manifest=None)),
]

# Additional cases isolate gaps that the previous combined task/seed and membership checks miss.
def missing_parent(f):f['parent_mode']='missing'
def empty_parent(f):f['parent_mode']='empty'
def manifest_no_invocations(f):f['manifest']=[{'started_utc':'2026-09-20T00:00:00Z'}]
def invocation_valid_but_wrong_episode(f):
 f['manifest'].append(dict(f['manifest'][0],invocation='inv-B'))
 f['decisions'][0]['invocation']='inv-B'
def add_two_decisions(f):
 # A failed first decision followed by a passing second decision in one invocation.
 e=f['episodes'][0];d0=e['decisions'][0]
 d0['validation'].update(passed=False,fail_class='assertion',frac_fail=1.0)
 d1=copy.deepcopy(d0);d1.update(t=1,transcript_sha256='5'*64)
 d1['state'].update(t=1,fail_class='assertion',prev_actions=[0],frac_fail=1.0)
 d1['validation'].update(passed=True,fail_class='none',frac_fail=0.0)
 e['decisions'].append(d1);e.update(n_decisions=2,n_new_decisions=2)
 ev=copy.deepcopy(f['decisions'][0]);ev.update(t=1,state=copy.deepcopy(d1['state']),transcript_sha256='5'*64,logged_utc='2026-09-20T00:00:02Z')
 f['decisions'].append(ev)
def missing_specific_decision(f):
 add_two_decisions(f);f['decisions'].pop()
def preserved_recovery_different_action(f):
 # Two invocations of one adaptive LIVE policy can legitimately take different t=1 actions
 # when fresh stochastic generation yields different failure classes. The old row is retained
 # as historical evidence; it is not the action from the current completed episode.
 add_two_decisions(f)
 e=f['episodes'][0];e['policy']='class_tailored';f['frozen']['policy']='class_tailored'
 f['frozen']['u']=[.75,.75];f['frozen']['run_order']=0
 e['decisions'][0].update(p_large=0.0,b_obs=1.0,source='policy:class_tailored')
 f['decisions'][0].update(p_large=0.0,b_obs=1.0,source='policy:class_tailored')
 e['decisions'][1].update(a=1,action='large',p_large=1.0,b_obs=1.0,source='policy:class_tailored',penalty=.03,model_alias='large',response_model='large')
 f['decisions'][1].update(a=1,action='large',p_large=1.0,b_obs=1.0,source='policy:class_tailored',penalty=.03)
 old=copy.deepcopy(f['decisions'][1]);old.update(invocation='inv-old',a=0,action='small',p_large=0.0,b_obs=1.0,penalty=.01,logged_utc='2026-09-19T23:59:02Z',transcript_sha256='6'*64)
 old['state']['fail_class']='exception'
 old0=copy.deepcopy(f['decisions'][0]);old0.update(invocation='inv-old',logged_utc='2026-09-19T23:59:01Z')
 f['manifest'].insert(0,dict(f['manifest'][0],invocation='inv-old'))
 f['decisions'][0:0]=[old0,old]
 f['fixture_note']='Valid historical row from a prior invocation of adaptive live class_tailored: exception routes small, while the retained current invocation assertion routes large. It is deliberately retained and distinguished by invocation, not presented as a current completion.'
cases.extend([
 ('branch_missing_parent_log','branch',True,missing_parent),
 ('branch_empty_parent_log','branch',True,empty_parent),
 ('manifest_without_invocation_ids','log',True,manifest_no_invocations),
 ('wrong_task_correct_seed','log',True,lambda f:f['episodes'][0].update(task_uid='wrong-task')),
 ('wrong_invocation_present_in_manifest','log',True,invocation_valid_but_wrong_episode),
 ('missing_specific_durable_decision','log',True,missing_specific_decision),
 ('preserved_recovery_old_action_differs','live',False,preserved_recovery_different_action),
])
results=[]
with tempfile.TemporaryDirectory(prefix='dtr-gate-audit-') as tmp:
 for ref in (PREV,REF):
  V,C=SOURCES[ref]
  for name,stage,expect_reject,change in cases:
   f=fixture(stage);change(f);root=pathlib.Path(tmp)/ref/name
   for p in ('experiments/tools','experiments/code_routing','experiments/common','results/code_routing/'+stage):(root/p).mkdir(parents=True,exist_ok=True)
   (root/'experiments/tools/verify_stage.py').write_bytes(V)
   (root/'experiments/code_routing/common.py').write_bytes(C)
   (root/'experiments/code_routing/config.json').write_bytes(cfg_raw)
   base=root/'results/code_routing';d=base/stage
   (base/'visible_tests.json').write_bytes(vt_raw)
   design=dict(tasks_sha256=taskhash,log_episodes=[f['frozen']] if stage=='log' else [],live_episodes=[f['frozen']] if stage=='live' else [])
   (base/'design.json').write_text(json.dumps(design))
   if stage=='branch':
    (d/'branch_plan.json').write_text(json.dumps(dict(episodes=[f['frozen']])))
    (base/'log').mkdir(exist_ok=True)
    mode=f.get('parent_mode','present')
    if mode!='missing':
     parent=json.dumps(dict(episode_id='parent1',task_uid='t1',split='confirm',error=None,decisions=[dict(t=0,a=0,validation=dict(passed=False)),dict(t=1,transcript_sha256=transcripthash)]))+'\n'
     (base/'log/episodes.jsonl').write_text('' if mode=='empty' else parent)
   body=''.join(json.dumps(e)+'\n' for e in f['episodes'])+('{"torn":' if f['episode_torn'] else '')
   (d/'episodes.jsonl').write_text(body)
   if f['decisions'] is not None:
    body=''.join(json.dumps(e)+'\n' for e in f['decisions'])+('{"torn":' if f['decision_torn'] else '')
    (d/'decisions.jsonl').write_text(body)
   if f['manifest'] is not None:(d/'run_manifest.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in f['manifest']))
   proc=subprocess.run([sys.executable,str(root/'experiments/tools/verify_stage.py'),stage,'--quiet-seconds','0'],text=True,capture_output=True,cwd=root)
   results.append(dict(ref=ref,name=name,stage=stage,expected_returncode=1 if expect_reject else 0,returncode=proc.returncode,defect_accepted=expect_reject and proc.returncode==0,valid_case_rejected=not expect_reject and proc.returncode!=0,fixture_note=f.get('fixture_note'),stdout=proc.stdout.strip(),stderr=proc.stderr.strip()))
changed=subprocess.check_output(['git','diff','--name-only',PREV,REF,'--','results/code_routing'],cwd=ROOT).decode().splitlines()
protected=subprocess.check_output(['git','ls-tree','-r','--name-only',REF,'results/code_routing'],cwd=ROOT).decode().splitlines()
protected=[p for p in protected if '/analysis/' not in p]
unchanged=all(blob(p,PREV)==blob(p) for p in protected)
assert unchanged and len(protected) == 19
assert all(not r['stderr'] and r['returncode'] in (0, 1) for r in results)
comparison=[]
for name,stage,expected_reject,_ in cases:
 old=next(r for r in results if r['name']==name and r['ref']==PREV)
 new=next(r for r in results if r['name']==name and r['ref']==REF)
 comparison.append(dict(name=name,expected_returncode=1 if expected_reject else 0,old_returncode=old['returncode'],new_returncode=new['returncode'],new_defect_accepted=new['defect_accepted'],new_valid_case_rejected=new['valid_case_rejected']))
previous_names={case[0] for case in cases[:25]}
previous_accepted={r['name'] for r in results if r['ref']==PREV and r['name'] in previous_names and r['defect_accepted']}
now_rejected=[c['name'] for c in comparison if c['name'] in previous_accepted and c['new_returncode']!=0]
remaining=[c['name'] for c in comparison if c['name'] in previous_accepted and c['new_returncode']==0]
assert len(previous_accepted) == 14 and len(now_rejected) == 12
assert remaining == ['true_flags_parent_hash_mismatch', 'wrong_source_hash']
assert sum(r['ref']==REF and r['defect_accepted'] for r in results) == 8
assert sum(r['ref']==REF and r['valid_case_rejected'] for r in results) == 1
summary={ref:dict(total=sum(r['ref']==ref for r in results),clean_cases_accepted=sum(r['ref']==ref and r['expected_returncode']==0 and r['returncode']==0 for r in results),defects_rejected=sum(r['ref']==ref and r['expected_returncode']==1 and r['returncode']!=0 for r in results),defects_accepted=sum(r['ref']==ref and r['defect_accepted'] for r in results),valid_cases_rejected=sum(r['ref']==ref and r['valid_case_rejected'] for r in results)) for ref in (PREV,REF)}
report=dict(ref=REF,prior_ref=PREV,scope='Tiny synthetic CLI cases at two pinned gate versions, not models/candidate execution/Monte Carlo/remote liveness. Sources copied from the archived earlier audit and extended only in ignored work.',python=sys.version.split()[0],source_hashes={ref:dict(gate=sha(SOURCES[ref][0]),common=sha(SOURCES[ref][1])) for ref in (PREV,REF)},published_fixtures=dict(command='.venv/bin/python -m pytest -q experiments/tools/test_verify_stage.py',observed_result='22 passed in 0.70s',note='Executed separately at clean pinned checkout. This is a recorded observation, not rerun by this script.'),archive_inventory=dict(changed_result_paths=changed,raw_artifact_paths_compared=len(protected),all_raw_artifacts_byte_identical=unchanged),previous_fourteen=dict(reproduced_count=len(previous_accepted),now_rejected_count=len(now_rejected),now_rejected=now_rejected,remaining_accepted=remaining),summary=summary,comparison=comparison,counterexamples=results,interpretation=[
 'Twelve of the fourteen original accepted defective cases now reject. Parent hash mismatch and wrong source hash still pass, as already disclosed open scope for the parent-hash check.',
 'The earlier combined wrong-task-and-seed case now fails because seed is checked; changing only task_uid while keeping the frozen seed still passes.',
 'Missing/empty parent logs disable the parent-membership guard. A nonempty manifest with no invocation identifiers disables the invocation-membership guard. Both fail open.',
 'Invocation membership is not an episode-level join. A decision attributed to a different invocation that appears elsewhere in the manifest still passes while the retained episode has no same-invocation decision.',
 'Nonempty decisions.jsonl is insufficient: removing one specific completed decision while leaving another durable row passes.',
 'The action comparison discards invocation/attempt keys. It falsely rejects a retained historical row from a different invocation of an adaptive live policy whose failure class and action differed. Actual frozen branch arms in this archive are fixed and all five recovery rows have the same action, so this counterexample is a gate generalization issue, not a newly detected archive discrepancy.',
 'Current raw archives remain byte-identical. No finding here demonstrates changed experimental results or independently proves remote host liveness. Atomic publication and actual-host writer exclusion remain outside these checks.'
])
out=args.output or ROOT/'work/audit_publication_gate_6f92026.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(ref=REF,previous_fourteen=report['previous_fourteen'],summary=summary,archive=report['archive_inventory'],comparison=comparison),indent=2));print('OUTPUT',out)
