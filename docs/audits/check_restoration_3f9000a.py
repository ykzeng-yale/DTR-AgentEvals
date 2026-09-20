"""Pinned stdlib-only artifact/record audit; no experiment imports or candidate/model/tool execution."""
import argparse,hashlib,json,subprocess
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path);ap.add_argument('--output',type=Path);args=ap.parse_args()
ROOT=args.repo or Path(__file__).resolve().parents[2]
REF='3f9000a99653e92207545df5c29d6406cf634205';PREV='7826c0c63862d6e309ec549c41695ea8331876cd';BASE='results/code_routing/'
def git(*a): return subprocess.check_output(['git','-C',str(ROOT),*a])
def raw(p,ref=REF): return git('show',f'{ref}:{p}')
def obj(p): return json.loads(raw(p))
def rows(p): return [json.loads(x) for x in raw(p).splitlines() if x.strip()]
def sha(x): return hashlib.sha256(x).hexdigest()
def key(e,t): return (e['episode_id'],e.get('invocation'),e.get('attempt'),t)
log=rows(BASE+'log/episodes.jsonl'); branches=rows(BASE+'branch/episodes.jsonl');br=[e for e in branches if not e.get('error')]
parents={e['episode_id']:e for e in log if not e.get('error')}
li={key(e,e['t']):e for e in rows(BASE+'log/decisions.jsonl')};bi={key(e,e['t']):e for e in rows(BASE+'branch/decisions.jsonl')}
counts=dict(branches=len(br),missing_parent=0,parent_stage1_missing=0,branch_first_stage_not1=0,parent_branch_hash_match=0,parent_hash_durable_match=0,branch_hash_durable_match=0,same_task=0)
unique=set()
for e in br:
 p=parents.get(e.get('parent_episode_id'))
 if p is None: counts['missing_parent']+=1;continue
 unique.add(p['episode_id']);pd=next((d for d in p['decisions'] if d['t']==1),None)
 if pd is None: counts['parent_stage1_missing']+=1;continue
 d=e['decisions'][0];ph=pd['transcript_sha256'];bh=d['transcript_sha256']
 counts['branch_first_stage_not1']+=d['t']!=1
 counts['parent_branch_hash_match']+=ph==bh
 counts['parent_hash_durable_match']+=li.get(key(p,1),{}).get('transcript_sha256')==ph
 counts['branch_hash_durable_match']+=bi.get(key(e,d['t']),{}).get('transcript_sha256')==bh
 counts['same_task']+=p['task_uid']==e['task_uid']
ids=[e['episode_id'] for e in br];plan_ids=[e['episode_id'] for e in obj(BASE+'branch/branch_plan.json')['episodes']]
expected_binding={k:sha(raw(BASE+p)) for k,p in [('branch_episodes_sha256','branch/episodes.jsonl'),('log_episodes_sha256','log/episodes.jsonl'),('visible_tests_sha256','visible_tests.json')]}
expected_binding.update(covered_episode_ids_sha256=sha('\n'.join(sorted(ids)).encode()),n_covered=len(ids))
report=obj(BASE+'analysis/restoration_recheck.json');binding=report.get('source_binding',{})
files=[p for p in git('ls-tree','-r','--name-only',REF,BASE).decode().splitlines() if not p.startswith(BASE+'analysis/')]
changed=[p for p in files if raw(p)!=raw(p,PREV)]
cfg=obj('experiments/code_routing/config.json');tp=ROOT/cfg['tasks_path'];task_expected=obj(BASE+'design.json')['tasks_sha256']
vt=raw(BASE+'visible_tests.json');vt_stamps=sorted({e.get('visible_tests_sha256') for e in log+br})
validation=obj('manuscript/validation.json');vf=validation['files_sha256'];pdf=validation['pdf']['path']
validation_mismatches=[p for p,h in vf.items() if sha(raw(p))!=h]
validation_changed=[p for p in vf if raw(p)!=raw(p,PREV)]
checks={
 'report_file_and_id_binding_matches':binding==expected_binding,
 'report_count_matches_complete_cohort':report.get('branch_episodes_checked')==len(br)==800,
 'report_branch_side_match_count_800':report.get('branch_side_transcript_hash_matches')==800,
 'completed_ids_unique_and_equal_plan':len(ids)==len(set(ids))==800 and set(ids)==set(plan_ids),
 'all_stored_hash_links_match':all(counts[k]==800 for k in ['parent_branch_hash_match','parent_hash_durable_match','branch_hash_durable_match','same_task']),
 'first_branch_stage_and_parent_available':all(counts[k]==0 for k in ['missing_parent','parent_stage1_missing','branch_first_stage_not1']),
 'parent_inventory':len(unique)==200 and len({parents[p]['task_uid'] for p in unique})==103,
 '20_nonanalysis_files_unchanged':len(files)==20 and not changed,
 'visible_tests_matches_stamps':vt_stamps==[sha(vt)],
 '31_pinned_validation_hashes_match':len(vf)==31 and not validation_mismatches,
 '31_validation_files_unchanged':not validation_changed,
 'validation_record_unchanged':raw('manuscript/validation.json')==raw('manuscript/validation.json',PREV),
 'pdf_unchanged_and_matches_validation':raw(pdf)==raw(pdf,PREV) and sha(raw(pdf))==validation['pdf']['sha256'],
 'available_task_input_matches_expected':not tp.exists() or sha(tp.read_bytes())==task_expected,
}
out={'ref':REF,'previous_ref':git('rev-parse',PREV).decode().strip(),'scope':'Pinned read-only record and artifact audit. Does not reconstruct transcript bytes, import experiment modules, execute candidate/tool/model code, or run Monte Carlo.','checks':checks,'failed_checks':[k for k,v in checks.items() if not v],'counts':counts,'unique_parents':len(unique),'unique_parent_tasks':len({parents[p]['task_uid'] for p in unique}),'report_source_binding':binding,'independently_expected_source_binding':expected_binding,'nonanalysis':{'count':len(files),'changed':changed,'sha256':{p:sha(raw(p)) for p in files}},'manuscript':{'pdf_sha256':sha(raw(pdf)),'reported_pages':validation['pdf']['pages'],'validation_hash_count':len(vf),'pinned_hash_mismatches':validation_mismatches,'files_changed_since_previous':validation_changed},'inputs':{'task_path':cfg['tasks_path'],'task_available_locally':tp.exists(),'task_expected_sha256':task_expected,'task_actual_sha256':sha(tp.read_bytes()) if tp.exists() else None,'visible_tests_sha256':sha(vt),'visible_tests_covers_parent_tasks':all(parents[p]['task_uid'] in json.loads(vt)['tests'] for p in unique)},'reconstruction_status':'Full transcript-byte reconstruction remains independently unperformed; required frozen task input is absent locally.' if not tp.exists() else 'Transcript-byte reconstruction is outside this audit; task availability and hash are reported separately.','helper_scope_limits':['New helper compares reconstructed transcript with both parent stage1 and branch fork-stage hashes; these computed outcomes remain workstream-reported here.','Binding covers branch/log episode bytes, visible-test bytes and completed episode ID digest. It does not bind original tasks, template/helper code, frozen configuration, or durable decision files.','Helper loads current tasks/template/test code without validating their hashes against frozen contract. Recorded source-hash membership does not itself reconstruct or validate those input bytes.','Helper does not compare invocation-specific durable transcript hashes. Current gate checks durable action/key linkage but does not compare durable transcript hashes. This audit independently checks the actual archive links.','Tool-result restoration remains stored evidence, not reexecution. Source hashes are read after reconstruction; writer exclusion/atomic publication are separately unresolved.'],'worker_reply':'Latest reply asserts three previous bounded checker failures repaired, accepts that they did not show archived-data corruption, and acknowledges deferred inference/writer/publication/comparator work. No new explicit question. Earlier request for hash-verifiable frozen task inputs remains unfulfilled.'}
dest=args.output or ROOT/'work/restoration_audit_3f9000a.json';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'ref':REF,'checks':checks,'counts':counts,'task_available':tp.exists(),'source_binding':binding,'pdf_sha256':sha(raw(pdf)),'output':str(dest)},indent=2))
raise SystemExit(bool(out['failed_checks']))
