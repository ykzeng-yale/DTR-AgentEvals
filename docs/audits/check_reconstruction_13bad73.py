"""Pinned independent stdlib-only task regeneration and transcript reconstruction.
Writes only under --output-dir (default: repository work/restoration_reconstruction_13bad73).
No experiment imports; public references parsed as syntax only, never executed.
"""
import argparse,ast,gzip,hashlib,json,re,subprocess,sys,urllib.request,warnings
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path);ap.add_argument('--output-dir',type=Path);ap.add_argument('--offline',action='store_true');a=ap.parse_args()
ROOT=a.repo or Path(__file__).resolve().parents[2];OUT=a.output_dir or ROOT/'work/restoration_reconstruction_13bad73';OUT.mkdir(parents=True,exist_ok=True)
REF='13bad73b586f757463fd1e3e339416155b27ac31';PREV='35eda5c1bbbeda59e3af688f5fb82d47f522cd0b';BASE='results/code_routing/'
def git(*x):return subprocess.check_output(['git','-C',str(ROOT),*x])
def raw(p,ref=REF):return git('show',f'{ref}:{p}')
def obj(p):return json.loads(raw(p))
def rows(p):return [json.loads(x) for x in raw(p).splitlines() if x.strip()]
def sha(x):return hashlib.sha256(x).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
def key(e,t):return (e['episode_id'],e.get('invocation'),e.get('attempt'),t)
source_manifest=obj(BASE+'analysis/task_regeneration.json');downloads={};errors=[]
for name,suffix in [('mbpp','.json'),('humaneval','.jsonl.gz')]:
 p=OUT/(name+suffix);u=source_manifest['downloads'][name]['url']
 if not a.offline:
  try:
   req=urllib.request.Request(u,headers={'User-Agent':'DTR-AgentEvals-read-only-reproduction'})
   with urllib.request.urlopen(req,timeout=60) as r:data=r.read();resolved=r.url
   p.write_bytes(data)
  except Exception as exc:
   errors.append({'source':name,'error':str(exc)})
   continue
 else:
  if not p.exists():errors.append({'source':name,'error':'offline source cache absent'});continue
  data=p.read_bytes();resolved='cached '+u
 downloads[name]={'url':u,'resolved_url':resolved,'bytes':len(data),'sha256':sha(data),'matches_archived_download':sha(data)==source_manifest['downloads'][name]['sha256']}
 print(name,downloads[name],flush=True)
if errors:
 (OUT/'audit.json').write_text(json.dumps({'ref':REF,'download_errors':errors,'downloads':downloads},indent=2));print(errors);raise SystemExit(1)
mbpp=json.loads((OUT/'mbpp.json').read_bytes());he=[json.loads(x) for x in gzip.decompress((OUT/'humaneval.jsonl.gz').read_bytes()).splitlines() if x.strip()]
# Independent literal translation of reviewed field mapping and entry-point selection, not an experiment import.
assert_name=re.compile(r'assert\s+(?:[A-Za-z_][\w.]*\()*\s*([A-Za-z_]\w*)\s*\(');def_name=re.compile(r'^def\s+([A-Za-z_]\w*)\s*\(',re.M)
tasks=[]
for q in sorted(mbpp,key=lambda r:int(r['task_id'])):
 ep=''
 for test in q.get('test_list',[]):
  m=assert_name.search(test)
  if m and re.search(r'def\s+%s\s*\('%re.escape(m.group(1)),q['code']):ep=m.group(1);break
 if not ep:
  defs=def_name.findall(q['code']);ep=defs[-1] if defs else ''
 tasks.append({'uid':f"mbpp/{int(q['task_id'])}",'benchmark':'mbpp','source_task_id':int(q['task_id']),'prompt':q['prompt'].strip(),'entry_point':ep,'signature_example':q['test_list'][0] if q['test_list'] else '', 'reference':q['code'],'test_imports':list(q.get('test_imports') or []),'test_list':list(q['test_list']),'challenge_test_list':list(q.get('challenge_test_list') or [])})
for q in sorted(he,key=lambda r:int(r['task_id'].split('/')[-1])):
 tasks.append({'uid':f"humaneval/{int(q['task_id'].split('/')[-1])}",'benchmark':'humaneval','source_task_id':q['task_id'],'prompt':q['prompt'],'entry_point':q['entry_point'],'signature_example':'','reference':q['prompt']+q['canonical_solution'],'test':q['test']})
taskbytes=canonical(tasks);expected=obj(BASE+'design.json')['tasks_sha256'];tasksha=sha(taskbytes);(OUT/'tasks.json').write_bytes(taskbytes)
print('task counts',len(mbpp),len(he),len(tasks),'sha256',tasksha,'matches',tasksha==expected,flush=True)
if tasksha!=expected:
 (OUT/'audit.json').write_text(json.dumps({'ref':REF,'downloads':downloads,'task_counts':[len(mbpp),len(he),len(tasks)],'rebuilt_sha256':tasksha,'expected':expected,'status':'frozen task mismatch; transcript reconstruction not attempted'},indent=2));raise SystemExit(1)
# Parse four literal prompt constants from pinned agent source; execute no functions from the module.
agentraw=raw('experiments/code_routing/agent.py');tree=ast.parse(agentraw.decode());names={'SYS_CODE','ASK_REPAIR','SYS_TEST','ASK_TESTS'};const={}
for n in tree.body:
 if isinstance(n,ast.Assign):
  for target in n.targets:
   if isinstance(target,ast.Name) and target.id in names:const[target.id]=ast.literal_eval(n.value)
assert set(const)==names
prompt_digest=sha(''.join(const[x] for x in ['SYS_CODE','ASK_REPAIR','SYS_TEST','ASK_TESTS']).encode())
# Reviewed equivalent of task_prompt/signature_line. AST parsing/unparsing is syntactic, not candidate execution.
def initial_message(t):
 if t['benchmark']!='mbpp':return 'Complete the following Python function.\n\n```python\n'+t['prompt']+'\n```'
 ep=t.get('entry_point') or '';signature='def %s(...):'%(ep or 'solution')
 try:
  with warnings.catch_warnings():
   warnings.simplefilter('ignore',SyntaxWarning);syntax=ast.parse(t['reference'])
  defs=[n for n in ast.walk(syntax) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))]
  chosen=next((d for d in defs if d.name==ep),None) or (defs[0] if defs else None)
  if chosen is not None:signature='def %s(%s):'%(chosen.name,ast.unparse(chosen.args))
 except SyntaxError:pass
 return t['prompt'].rstrip()+'\n\nUse exactly this function signature:\n```python\n'+signature+'\n```'
taskmap={t['uid']:t for t in tasks};vt=obj(BASE+'visible_tests.json')['tests']
log=rows(BASE+'log/episodes.jsonl');br=[e for e in rows(BASE+'branch/episodes.jsonl') if not e.get('error')];parents={e['episode_id']:e for e in log if not e.get('error')}
li={key(e,e['t']):e for e in rows(BASE+'log/decisions.jsonl')};bi={key(e,e['t']):e for e in rows(BASE+'branch/decisions.jsonl')}
counts={'branches':len(br),'missing_parents':0,'reconstructed_parent_hash_matches':0,'reconstructed_branch_hash_matches':0,'reconstructed_parent_durable_matches':0,'reconstructed_branch_durable_matches':0,'matching_task_ids':0,'stored_flags_agree':0};unique={};fail=[]
for e in br:
 p=parents.get(e.get('parent_episode_id'))
 if p is None:counts['missing_parents']+=1;continue
 d0=next(d for d in p['decisions'] if d['t']==0);d1=next(d for d in p['decisions'] if d['t']==1);b1=next(d for d in e['decisions'] if d['t']==e['fork_t'])
 text=vt[p['task_uid']]['certified']['text'] or '# (no visible tests; the solution failed to load)'
 convo=[{'role':'system','content':const['SYS_CODE']},{'role':'user','content':initial_message(taskmap[p['task_uid']])},{'role':'assistant','content':d0['reply']},{'role':'user','content':const['ASK_REPAIR'].format(tests=text,trace=d0['trace'])}]
 h=sha(json.dumps(convo,sort_keys=True).encode());unique[p['episode_id']]=h
 cases={'reconstructed_parent_hash_matches':h==d1['transcript_sha256'],'reconstructed_branch_hash_matches':h==b1['transcript_sha256'],'reconstructed_parent_durable_matches':h==li.get(key(p,1),{}).get('transcript_sha256'),'reconstructed_branch_durable_matches':h==bi.get(key(e,e['fork_t']),{}).get('transcript_sha256'),'matching_task_ids':p['task_uid']==e['task_uid'],'stored_flags_agree':(e.get('restoration') or {}).get('transcript_hash_matches') is True and h==d1['transcript_sha256']}
 for k,v in cases.items():counts[k]+=v
 if not all(cases.values()):fail.append({'episode_id':e['episode_id'],'checks':cases})
ids=[e['episode_id'] for e in br];expected_binding={k:sha(raw(BASE+p)) for k,p in [('branch_episodes_sha256','branch/episodes.jsonl'),('log_episodes_sha256','log/episodes.jsonl'),('visible_tests_sha256','visible_tests.json'),('branch_decisions_sha256','branch/decisions.jsonl'),('log_decisions_sha256','log/decisions.jsonl')]}
expected_binding.update(tasks_sha256=tasksha,prompt_helper_revision=prompt_digest,covered_episode_ids_sha256=sha('\n'.join(sorted(ids)).encode()),n_covered=len(ids));binding=obj(BASE+'analysis/restoration_recheck.json')['source_binding']
files=[p for p in git('ls-tree','-r','--name-only',REF,BASE).decode().splitlines() if not p.startswith(BASE+'analysis/')];changed=[p for p in files if raw(p)!=raw(p,PREV)]
planids={e['episode_id'] for e in obj(BASE+'branch/branch_plan.json')['episodes']}
checks={'public_source_counts':len(mbpp)==427 and len(he)==164,'public_source_bytes_match_archived':all(x['matches_archived_download'] for x in downloads.values()),'frozen_task_bytes_reproduced':tasksha==expected,'all800_reconstructions_and_links_match':len(br)==800 and not fail and counts['missing_parents']==0,'200_unique_prefixes':len(unique)==200,'completed_id_set_matches_plan':len(ids)==len(set(ids))==800 and set(ids)==planids,'all_source_binding_fields_match':binding==expected_binding,'20_nonanalysis_files_unchanged':len(files)==20 and not changed}
report={'ref':REF,'previous_ref':PREV,'scope':'Independent public-source regeneration and full transcript-byte reconstruction with reviewed manual equivalents and literal constant extraction. No experiment-module imports, code execution from dataset references/generated replies, model calls, tool reexecution, or Monte Carlo. Downloads/tasks retained only in ignored work.','downloads':downloads,'task_counts':{'mbpp':len(mbpp),'humaneval':len(he),'total':len(tasks)},'rebuilt_task_sha256':tasksha,'checks':checks,'failed_checks':[k for k,v in checks.items() if not v],'counts':counts,'unique_parent_prefixes':len(unique),'unique_tasks':len({parents[p]['task_uid'] for p in unique}),'mismatches':fail,'source_binding':binding,'nonanalysis_artifacts':{'count':len(files),'changed':changed,'sha256':{p:sha(raw(p)) for p in files}},'reconstruction_implementation':{'python':sys.version,'pinned_agent_source_sha256':sha(agentraw),'pinned_regeneration_source_sha256':sha(raw('experiments/tools/regenerate_tasks.py')),'prompt_constant_digest':prompt_digest,'hash_serialization':'json.dumps(conversation, sort_keys=True).encode(): default ensure_ascii=True, default separators; task archive separately uses ensure_ascii=False and compact separators'},'remaining_limits':['Actual archived transcript bytes and all requested record hashes independently reconstruct, resolving the previous local input blocker. Tool-result rerun, hidden-test outcomes, model serving and runtime state were not reexecuted.','The prompt_helper_revision digest covers only four literal constants; it omits task_prompt, signature_line, repair_message implementations, JSON serialization and Python AST/unparse version.','Gate compares bound task hash with frozen design hash, not current task-file bytes. The reconstruction helper hashes current tasks but does not itself assert frozen-hash equality.','Gate does not recompute/compare prompt_helper_revision. Durable-file hashes are bound, but helper/gate do not themselves compare durable transcript hashes; this independent audit does.','Regeneration source URLs use moving master branches, with expected frozen output/source hashes detecting drift. Original regeneration CLI unconditionally writes a report into results; this independent script writes only under ignored work.']}
(OUT/'audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({'checks':checks,'counts':counts,'unique_prefixes':len(unique),'unique_tasks':report['unique_tasks'],'output':str(OUT/'audit.json')},indent=2));raise SystemExit(bool(report['failed_checks']))
