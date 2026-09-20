"""Deterministic gate counterexamples, isolated under temporary directories.
Copies only the pinned publication gate/common helper, never executes candidate code.
Run from repo root or pass --repo. Writes only an audit JSON under work by default.
"""
import argparse, copy, hashlib, json, pathlib, subprocess, sys, tempfile
REF='29ee443cc3ba1d00bb7f37e90f8a8915e2a9357c'; PREV='d4997c68ca93a4d5835bcc578470af472be311b2'
ap=argparse.ArgumentParser();ap.add_argument('--repo',type=pathlib.Path);ap.add_argument('--output',type=pathlib.Path);args=ap.parse_args()
ROOT=args.repo or pathlib.Path(__file__).resolve().parents[2]
def blob(p,ref=REF):return subprocess.check_output(['git','show',f'{ref}:{p}'],cwd=ROOT)
def sha(b):return hashlib.sha256(b).hexdigest()
V=blob('experiments/tools/verify_stage.py');C=blob('experiments/code_routing/common.py')
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
results=[]
with tempfile.TemporaryDirectory(prefix='dtr-gate-audit-') as tmp:
 for name,stage,expect_reject,change in cases:
  f=fixture(stage);change(f);root=pathlib.Path(tmp)/name
  for p in ('experiments/tools','experiments/code_routing','experiments/common','results/code_routing/'+stage): (root/p).mkdir(parents=True,exist_ok=True)
  (root/'experiments/tools/verify_stage.py').write_bytes(V)
  (root/'experiments/code_routing/common.py').write_bytes(C)
  (root/'experiments/code_routing/config.json').write_bytes(cfg_raw)
  base=root/'results/code_routing';d=base/stage
  (base/'visible_tests.json').write_bytes(vt_raw)
  design=dict(tasks_sha256=taskhash,log_episodes=[f['frozen']],live_episodes=[])
  (base/'design.json').write_text(json.dumps(design))
  if stage=='branch':
   (d/'branch_plan.json').write_text(json.dumps(dict(episodes=[f['frozen']])))
   # A real parent record is supplied, so the forged-parent/hash examples have an inspectable reference.
   (base/'log').mkdir(exist_ok=True)
   (base/'log/episodes.jsonl').write_text(json.dumps(dict(episode_id='parent1',task_uid='t1',split='confirm',error=None,decisions=[dict(t=0,a=0,validation=dict(passed=False)),dict(t=1,transcript_sha256=transcripthash)]))+'\n')
  body=''.join(json.dumps(e)+'\n' for e in f['episodes'])+('{"torn":' if f['episode_torn'] else '')
  (d/'episodes.jsonl').write_text(body)
  if f['decisions'] is not None:
   body=''.join(json.dumps(e)+'\n' for e in f['decisions'])+('{"torn":' if f['decision_torn'] else '')
   (d/'decisions.jsonl').write_text(body)
  if f['manifest'] is not None:(d/'run_manifest.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in f['manifest']))
  proc=subprocess.run([sys.executable,str(root/'experiments/tools/verify_stage.py'),stage,'--quiet-seconds','0'],text=True,capture_output=True,cwd=root)
  results.append(dict(name=name,stage=stage,expect_reject=expect_reject,returncode=proc.returncode,defect_accepted=expect_reject and proc.returncode==0,stdout=proc.stdout.strip(),stderr=proc.stderr.strip()))
changed=subprocess.check_output(['git','diff','--name-only',PREV,REF,'--','results/code_routing'],cwd=ROOT).decode().splitlines()
protected=subprocess.check_output(['git','ls-tree','-r','--name-only',REF,'results/code_routing'],cwd=ROOT).decode().splitlines()
protected=[p for p in protected if '/analysis/' not in p]
unchanged=all(blob(p,PREV)==blob(p) for p in protected)
assert unchanged
assert len(protected) == 19
assert all(not r['stderr'] for r in results)
assert sum(not r['expect_reject'] and r['returncode']==0 for r in results) == 2
assert sum(r['expect_reject'] and r['returncode']==1 for r in results) == 9
assert sum(r['defect_accepted'] for r in results) == 14
report=dict(ref=REF,prior_ref=PREV,scope='Tiny synthetic CLI fixtures only; no models, candidate execution, Monte Carlo, or remote process-liveness inference.',python=sys.version.split()[0],gate_sha256=sha(V),helper_sha256=sha(C),published_fixtures=dict(command='.venv/bin/python -m pytest -q experiments/tools/test_verify_stage.py',result='9 passed in 0.56s',note='Executed separately at the pinned clean checkout. The supplied torn-tail fixture checks the resolver only; this audit also checks the CLI exit status.'),archive_inventory=dict(changed_result_paths=changed,raw_artifact_paths_compared=len(protected),all_raw_artifacts_byte_identical=unchanged),counterexamples=results,summary=dict(total=len(results),clean_cases_accepted=sum(not r['expect_reject'] and r['returncode']==0 for r in results),defects_rejected=sum(r['expect_reject'] and r['returncode']!=0 for r in results),defects_accepted=sum(r['defect_accepted'] for r in results)),interpretation=['Accepted fixes: torn episode/decision tails, duplicate completed IDs, present incorrect config/tasks/visible hashes, absent invocation key, wholly orphan episode IDs, true transcript flag without parent ID.','Restoration verification is only a narrow presence check: false or absent flags, a nonexistent parent, and a parent-hash mismatch pass. No fresh restoration execution is requested or performed.','Metadata validation ignores absent/null fields; source hashes and plan task/seed identity are not checked.','Invocation validation checks key existence only: null or unrelated values pass, and durable/nested decisions need not match.','Missing or empty decisions files and absent run manifests pass. The checker does not ensure every completed decision has an invocation-linked durable record.','A passing gate and nine passing fixtures therefore do not establish complete publication integrity; the prior independent raw-artifact audit remains a separate evidence layer.','TOCTOU and actual-host liveness remain unresolved by these fixtures; no local PID result is interpreted as remote liveness.'])
out=args.output or ROOT/'work/audit_publication_gate_29ee443.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(ref=REF,summary=report['summary'],raw_artifacts_byte_identical=unchanged,cases=[{k:r[k] for k in ('name','returncode','defect_accepted')} for r in results]),indent=2));print('OUTPUT',out)
