"""Deterministic gate counterexamples, isolated under temporary directories.
Copies only the pinned publication gate/common helper, never executes candidate code.
Run from repo root or pass --repo. Writes only an audit JSON under work by default.
"""
import argparse, collections, copy, hashlib, json, pathlib, subprocess, sys, tempfile
REF='97689b94ce8f49bf6b12ff6d77ec35573b495493'; PREV='bd1ace89da2c3b93e437154f03f8eb12b6c0ed63'
ap=argparse.ArgumentParser();ap.add_argument('--repo',type=pathlib.Path);ap.add_argument('--output',type=pathlib.Path);args=ap.parse_args()
ROOT=args.repo or pathlib.Path(subprocess.check_output(['git','rev-parse','--show-toplevel']).decode().strip())
def blob(p,ref=REF):return subprocess.check_output(['git','show',f'{ref}:{p}'],cwd=ROOT)
def sha(b):return hashlib.sha256(b).hexdigest()
SOURCES={ref:(blob('experiments/tools/verify_stage.py',ref),blob('experiments/code_routing/common.py',ref)) for ref in (PREV,REF)}
cfg={'max_attempts_per_episode':3,'horizon':3};cfg_raw=json.dumps(cfg).encode();vt_raw=b'{}'
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

def add_ledger(f,rows):
 f['ledger']=dict(schema=1,stage=f['stage'],rows=rows,total_rows=sum(r['durable_decision_rows'] for r in rows),total_episode_ids=len({r['episode_id'] for r in rows}))
def recovery_with_ledger(f):
 preserved_recovery_different_action(f)
 add_ledger(f,[dict(episode_id='e1',invocation='inv-old',attempt=1,durable_decision_rows=2)])
def simple_history(f):
 old=copy.deepcopy(f['decisions'][0]);old.update(invocation='inv-old',logged_utc='2026-09-19T23:59:01Z')
 f['decisions'].insert(0,old);f['manifest'].insert(0,dict(f['manifest'][0],invocation='inv-old'))
 add_ledger(f,[dict(episode_id='e1',invocation='inv-old',attempt=1,durable_decision_rows=1)])
def wrong_ledger_count(f):
 simple_history(f);f['ledger']['rows'][0]['durable_decision_rows']=2;f['ledger']['total_rows']=2

def wrong_ledger_stage(f):
 simple_history(f);f['ledger']['stage']='branch'
def ledger_without_manifest_invocation(f):
 simple_history(f);f['manifest']=[m for m in f['manifest'] if m['invocation']!='inv-old']
def ledger_extra_historical_stage(f):
 simple_history(f)
 extra=copy.deepcopy(f['decisions'][0]);extra['t']=99
 f['decisions'].insert(1,extra)
 # Counts are accurate here: the defect is the impossible extra stage hidden behind
 # a ledger exemption keyed only by episode/invocation/attempt.
 f['ledger']['rows'][0]['durable_decision_rows']=2;f['ledger']['total_rows']=2
cases.extend([
 ('recovery_ledger_allows_different_old_action','live',False,recovery_with_ledger),
 ('ledger_wrong_declared_row_count','log',True,wrong_ledger_count),
 ('ledger_extra_historical_stage','log',True,ledger_extra_historical_stage),
])
# New contract fixture augmentation: a positive independent-restoration SUMMARY is now
# required. It is deliberately left positive after the existing parent-hash mutation,
# which checks whether the gate binds the summary to records rather than trusting it.
# No claim is made that this synthetic summary was computed by verify_restoration.py.
def source_from_other_invocation(f):
 f['episodes'][0]['code_sha256']='9'*64
 f['manifest'].append(dict(f['manifest'][0],invocation='inv-B',code_sha256='9'*64))
def manifest_no_source_hashes(f):
 for m in f['manifest']:m.pop('code_sha256',None)
def missing_restoration_summary(f):f['summary_mode']='missing'
def negative_restoration_summary(f):f['summary_mode']='disagreement'
cases.extend([
 ('source_hash_from_other_invocation','log',True,source_from_other_invocation),
 ('manifest_without_source_hashes','log',True,manifest_no_source_hashes),
 ('missing_restoration_summary','branch',True,missing_restoration_summary),
 ('restoration_summary_reports_disagreement','branch',True,negative_restoration_summary),
])
results=[]
with tempfile.TemporaryDirectory(prefix='dtr-gate-audit-') as tmp:
 for ref in (PREV,REF):
  V,C=SOURCES[ref]
  for name,stage,expected_reject,change in cases:
   f=fixture(stage);change(f);root=pathlib.Path(tmp)/ref/name
   # The revised contract legitimately requires a ledger for the old recovery-only case.
   reject=expected_reject or name=='preserved_recovery_old_action_differs'
   if ref==PREV and name in ('missing_restoration_summary','restoration_summary_reports_disagreement'):reject=False
   for p in ('experiments/tools','experiments/code_routing','experiments/common','results/code_routing/'+stage):(root/p).mkdir(parents=True,exist_ok=True)
   (root/'experiments/tools/verify_stage.py').write_bytes(V);(root/'experiments/code_routing/common.py').write_bytes(C);(root/'experiments/code_routing/config.json').write_bytes(cfg_raw)
   base=root/'results/code_routing';d=base/stage;(base/'visible_tests.json').write_bytes(vt_raw)
   design=dict(tasks_sha256=taskhash,log_episodes=[f['frozen']] if stage=='log' else [],live_episodes=[f['frozen']] if stage=='live' else [])
   (base/'design.json').write_text(json.dumps(design))
   if stage=='branch':
    (d/'branch_plan.json').write_text(json.dumps(dict(episodes=[f['frozen']])))
    (base/'log').mkdir(exist_ok=True);mode=f.get('parent_mode','present')
    if mode!='missing':
     parent=json.dumps(dict(episode_id='parent1',task_uid='t1',split='confirm',error=None,decisions=[dict(t=0,a=0,validation=dict(passed=False)),dict(t=1,transcript_sha256=transcripthash)]))+'\n'
     (base/'log/episodes.jsonl').write_text('' if mode=='empty' else parent)
    if f.get('summary_mode')!='missing':
     (base/'analysis').mkdir(exist_ok=True)
     summary=dict(branch_episodes_checked=1,missing_parent=0,recomputed_transcript_hash_matches=1,stored_flag_agrees_with_recomputation=1,disagreements=int(f.get('summary_mode')=='disagreement'),examples=[],stored_tool_result_reproduced=1)
     (base/'analysis/restoration_recheck.json').write_text(json.dumps(summary))
   body=''.join(json.dumps(e)+'\n' for e in f['episodes'])+('{"torn":' if f['episode_torn'] else '')
   (d/'episodes.jsonl').write_text(body)
   if f['decisions'] is not None:
    body=''.join(json.dumps(e)+'\n' for e in f['decisions'])+('{"torn":' if f['decision_torn'] else '')
    (d/'decisions.jsonl').write_text(body)
   if f['manifest'] is not None:(d/'run_manifest.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in f['manifest']))
   if 'ledger' in f:(base/'recovery_ledger.json').write_text(json.dumps(f['ledger']))
   proc=subprocess.run([sys.executable,str(root/'experiments/tools/verify_stage.py'),stage,'--quiet-seconds','0'],text=True,capture_output=True,cwd=root)
   results.append(dict(ref=ref,name=name,stage=stage,expected_returncode=1 if reject else 0,returncode=proc.returncode,defect_accepted=reject and proc.returncode==0,valid_case_rejected=not reject and proc.returncode!=0,fixture_note=f.get('fixture_note'),stdout=proc.stdout.strip(),stderr=proc.stderr.strip()))
assert all(r['returncode'] in (0,1) and not r['stderr'] for r in results)
comparison=[]
for name,_,_,_ in cases:
 old=next(r for r in results if r['name']==name and r['ref']==PREV);new=next(r for r in results if r['name']==name and r['ref']==REF)
 comparison.append(dict(name=name,old_returncode=old['returncode'],new_returncode=new['returncode'],new_expected_returncode=new['expected_returncode'],new_defect_accepted=new['defect_accepted'],new_valid_case_rejected=new['valid_case_rejected']))
previous_names={c[0] for c in cases[:35]};previous_accepted={r['name'] for r in results if r['ref']==PREV and r['name'] in previous_names and r['defect_accepted']}
fixed=[c['name'] for c in comparison if c['name'] in previous_accepted and c['new_returncode']!=0];remaining=[c['name'] for c in comparison if c['name'] in previous_accepted and c['new_returncode']==0]
assert len(previous_accepted)==6 and len(fixed)==5 and remaining==['true_flags_parent_hash_mismatch']
# The unchanged actual ledger is checked independently, without running the gate on a process-owning host.
B='results/code_routing/';read=lambda p:[json.loads(l) for l in blob(B+p).splitlines()]
E=read('branch/episodes.jsonl');D=read('branch/decisions.jsonl');M=read('branch/run_manifest.jsonl');ledger=json.loads(blob(B+'recovery_ledger.json'))
k3=lambda x:(x['episode_id'],x['invocation'],x['attempt'])
retained={k3(e) for e in E};nested={(e['episode_id'],e['invocation'],e['attempt'],d['t']) for e in E for d in e['decisions']}
historical=[d for d in D if k3(d) not in retained];observed=collections.Counter(k3(d) for d in historical)
declared={k3(r):r['durable_decision_rows'] for r in ledger['rows']}
ledger_checks=dict(stage=ledger['stage']=='branch',four_unique_declared_keys=len(declared)==len(ledger['rows'])==4,declared_counts_match_actual=declared==dict(observed),total_rows=ledger['total_rows']==len(historical)==5,total_episode_ids=ledger['total_episode_ids']==len({d['episode_id'] for d in historical})==4,old_invocation=all(d['invocation']==ledger['lost_invocation']==M[0]['invocation'] for d in historical),recovery_invocation=ledger['recovery_invocation']==M[1]['invocation'] and all(next(e['invocation'] for e in E if e['episode_id']==d['episode_id'])==ledger['recovery_invocation'] for d in historical),attempt_reused=ledger['attempt_number_reused'] is True and all(d['attempt']==1 for d in historical),all_other_decisions_match_completion_key=all((d['episode_id'],d['invocation'],d['attempt'],d['t']) in nested for d in D if k3(d) in retained))
assert all(ledger_checks.values())
def inventory(ref):return {p for p in subprocess.check_output(['git','ls-tree','-r','--name-only',ref,'results/code_routing'],cwd=ROOT).decode().splitlines() if '/analysis/' not in p}
before,after=inventory(PREV),inventory(REF);same=all(blob(p,PREV)==blob(p) for p in before)
assert len(before)==len(after)==20 and same and before==after
report=dict(
 ref=REF,prior_ref=PREV,
 scope='Prior 35 CLI cases plus four bounded source/report-binding cases, in temporary fixtures. Clean branch fixtures include the newly required positive restoration summary. Pinned ledger/inventory checks only; no models/candidate execution/Monte Carlo/remote PID inference.',
 fixture_contract=dict(previous_case_count=35,new_case_count=4,required_augmentation='All branch baselines for BOTH pinned gate versions receive the same positive one-episode restoration summary; the parent-hash mutation deliberately leaves this summary unchanged. It is synthetic, not claimed independently recomputed.',recovery='The old unledgered recovery case expects rejection in BOTH versions because both already require the ledger. A separate valid ledgered recovery case remains positive.',new_report_cases='Missing/negative restoration summary is permitted by the old contract and expected to be rejected by the new contract.'),
 source_hashes={ref:dict(gate=sha(SOURCES[ref][0]),common=sha(SOURCES[ref][1])) for ref in (PREV,REF)},
 published_tests=dict(command='.venv/bin/python -m pytest -q experiments/tools/test_verify_stage.py',observed_result='37 passed in 9.57s',note='Executed separately against the pinned current gate/test checkout; this audit script does not rerun these tests.',test_sha256=sha(blob('experiments/tools/test_verify_stage.py'))),
 archive_inventory=dict(prior_non_analysis_files=len(before),current_non_analysis_files=len(after),all_prior_files_byte_identical=same,new_files=sorted(after-before),files=[dict(path=p,sha256=sha(blob(p))) for p in sorted(after)]),
 actual_ledger=dict(sha256=sha(blob(B+'recovery_ledger.json')),checks=ledger_checks,observed_rows=[dict(episode_id=k[0],invocation=k[1],attempt=k[2],durable_decision_rows=v) for k,v in sorted(observed.items())],nested_completion_decisions=len(nested),all_durable_decisions=len(D)),
 prior_six_bypasses=dict(fixed=fixed,remaining=remaining),comparison=comparison,counterexamples=results,
 source_findings=dict(
  aggregate_report=dict(gate_lines='114-127',mechanism='Checks only report existence, checked-count >= completed-count, zero disagreements/missing-parent, and matching aggregate transcript count. No input hashes, episode ID set, or per-record linkage is checked.',saved_report_sha256=sha(blob(B+'analysis/restoration_recheck.json')),saved_report=json.loads(blob(B+'analysis/restoration_recheck.json'))),
  helper=dict(path='experiments/tools/verify_restoration.py',sha256=sha(blob('experiments/tools/verify_restoration.py')),mechanism='Rebuilds the parent pre-t=1 transcript from task, frozen visible tests, parent first reply/trace; compares its hash to the parent t=1 hash and compares that boolean with the branch stored flag. It does not compare a branch decision transcript hash to this reconstruction. It reports tool-result restoration as stored; it does not execute candidates.'),
  source_hashes=dict(gate_lines='148-153',mechanism='Completed source hashes are checked against the union of nonempty manifest hashes, not the manifest row for their own invocation. The membership test is skipped when all manifest hashes are absent.')
 ),interpretation=[
  'Five of the prior six bounded defects now reject: empty parent log, manifest without invocation identifiers, single-manifest source-hash mismatch, incorrect historical row count, and historical t=99 outside horizon. The legitimate declared adaptive recovery case passes; undeclared history rejects.',
  'One prior defect remains accepted under the new valid baseline contract: the branch parent-transcript-hash mismatch passes with the same positive aggregate restoration summary. Therefore a gate-only acceptance cannot establish current-input restoration reconstruction or branch-to-parent hash linkage.',
  'Two targeted source-provenance counterexamples pass: an episode source hash appearing only in a different invocation manifest, and a manifest whose source hashes are all absent. The implemented fix establishes union membership only when that union is nonempty.',
  'The new missing-summary and report-disagreement cases reject as intended. A required positive report is useful evidence, but must be tied to pinned input hashes/IDs and relevant per-record comparisons to support a stronger gate claim.',
  'All 20 prior non-analysis artifacts, including the recovery ledger, are byte-identical. Its five historical durable rows across four IDs still reconcile. Recorded pre-invocation assignments are not proof of completed model execution or recovery of the operator-reported 665 lost outcomes.',
  'These are deterministic acceptance-boundary checks and source inspection, not model reruns, atomic-publication proof, actual-host writer exclusion, or independent reproduction of the saved restoration report. A separate pinned record-linkage audit is available; full transcript reconstruction remains unreplicated locally because the frozen task input is absent.'
 ])
new_bad=[c for c in comparison if c['new_defect_accepted'] or c['new_valid_case_rejected']]
assert {c['name'] for c in new_bad}=={'true_flags_parent_hash_mismatch','source_hash_from_other_invocation','manifest_without_source_hashes'}
out=args.output or ROOT/'work/publication_gate_audit_97689b9.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(ref=REF,prior_six_bypasses=report['prior_six_bypasses'],ledger_checks=ledger_checks,archive={k:v for k,v in report['archive_inventory'].items() if k!='files'},new_failures=new_bad,recovery_cases=[c for c in comparison if c['name'].startswith(('ledger_','recovery_'))]),indent=2));print('OUTPUT',out)
