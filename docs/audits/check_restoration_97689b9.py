"""Read-only stdlib audit of pinned records; never imports experiment code or executes candidate programs."""
import argparse,hashlib,json,subprocess
from pathlib import Path
ap=argparse.ArgumentParser()
ap.add_argument('--repo',type=Path)
ap.add_argument('--output',type=Path)
ap.add_argument('--include-linkage',action='store_true')
args=ap.parse_args()
ROOT=args.repo or Path(__file__).resolve().parents[2]
REF='97689b94ce8f49bf6b12ff6d77ec35573b495493'; PREV='a02ffb01b62726e21f1b5206ca4bf0a1097f9170'; BASE='results/code_routing/'
def git(*args): return subprocess.check_output(['git','-C',str(ROOT),*args])
def raw(path,ref=REF): return git('show',f'{ref}:{path}')
def obj(path): return json.loads(raw(path))
def rows(path): return [json.loads(x) for x in raw(path).splitlines() if x.strip()]
def sha(data): return hashlib.sha256(data).hexdigest()
def key(e,t): return (e['episode_id'],e['invocation'],e.get('attempt',1),t)
log=rows(BASE+'log/episodes.jsonl'); br=rows(BASE+'branch/episodes.jsonl')
parents={e['episode_id']:e for e in log if not e.get('error')}
ld=rows(BASE+'log/decisions.jsonl'); bd=rows(BASE+'branch/decisions.jsonl')
li={key(d,d['t']):d for d in ld}; bi={key(d,d['t']):d for d in bd}
counts={k:0 for k in ['branches','missing_parent','parent_stage1_missing','branch_first_stage_not1','parent_branch_hash_match','parent_hash_durable_match','branch_hash_durable_match','same_task','stored_hash_flag_true','stored_tool_flag_true']}
unique=set(); details=[]
for e in br:
 if e.get('error'): continue
 counts['branches']+=1; p=parents.get(e.get('parent_episode_id'))
 if p is None: counts['missing_parent']+=1; continue
 unique.add(p['episode_id']); pd=next((d for d in p['decisions'] if d['t']==1),None)
 if pd is None: counts['parent_stage1_missing']+=1; continue
 d=e['decisions'][0]; counts['branch_first_stage_not1']+=d['t']!=1
 ph=pd['transcript_sha256']; bh=d['transcript_sha256']
 counts['parent_branch_hash_match']+=ph==bh
 counts['parent_hash_durable_match']+=li.get(key(p,1),{}).get('transcript_sha256')==ph
 counts['branch_hash_durable_match']+=bi.get(key(e,d['t']),{}).get('transcript_sha256')==bh
 counts['same_task']+=e['task_uid']==p['task_uid']
 counts['stored_hash_flag_true']+=(e.get('restoration') or {}).get('transcript_hash_matches') is True
 counts['stored_tool_flag_true']+=(e.get('restoration') or {}).get('tool_result_reproduced') is True
 details.append({'episode_id':e['episode_id'],'parent_episode_id':p['episode_id'],'task_uid':p['task_uid'],'parent_stage1_hash':ph,'branch_first_hash':bh})
files=[p for p in git('ls-tree','-r','--name-only',REF,BASE).decode().splitlines() if not p.startswith(BASE+'analysis/')]
changed=[p for p in files if raw(p)!=raw(p,PREV)]
vt=raw(BASE+'visible_tests.json'); expected_vt=sorted({e.get('visible_tests_sha256') for e in br+log})
cfg=obj('experiments/code_routing/config.json'); tp=ROOT/cfg['tasks_path']; expected_task=obj(BASE+'design.json')['tasks_sha256']
report={'ref':git('rev-parse',REF).decode().strip(),'previous_ref':git('rev-parse',PREV).decode().strip(),'scope':'Pinned immutable record linkage only; no experiment imports, model calls, candidate/tool execution, or Monte Carlo. Transcript reconstruction is outside this record-linkage audit; local frozen-input availability is reported separately.', 'counts':counts,'unique_parents':len(unique),'unique_parent_tasks':len({parents[u]['task_uid'] for u in unique}), 'nonanalysis_files':{'count':len(files),'changed':changed,'sha256':{p:sha(raw(p)) for p in files}},'inputs':{'tasks_path':cfg['tasks_path'],'tasks_exists_locally':tp.exists(),'tasks_expected_sha256':expected_task,'tasks_current_sha256':sha(tp.read_bytes()) if tp.exists() else None,'visible_tests_pinned_sha256':sha(vt),'visible_tests_recorded_hashes':expected_vt,'visible_tests_match_recorded':expected_vt==[sha(vt)],'visible_tests_covers_parent_tasks':all(parents[u]['task_uid'] in json.loads(vt)['tests'] for u in unique),'recheck_report_sha256':sha(raw(BASE+'analysis/restoration_recheck.json'))},'reconstruction_status':('Not independently reproduced. Frozen task input is missing locally.' if not tp.exists() else 'Not independently reproduced by this script; task input availability/hash is reported separately.')+' Hash linkage between stored parent/branch/durable records is fully checkable but is not recomputation of transcript bytes.','recheck_source_scope':['Compares reconstructed parent transcript against parent stage-1 hash, then against branch stored boolean. Does not compare reconstructed hash to branch first decision hash.','Uses current common/agent/analysis imports and current task/visible-test files, without matching input/code hashes to frozen design/record manifests.','Report has counts only: no covered episode IDs, parent IDs, input hashes, script/template version, generated time, or source-frame digest.','Tool restoration remains a stored boolean; no runtime-state reexecution is performed.']}
checks={
 'all_800_branches_linked':counts['branches']==800 and counts['missing_parent']==0 and counts['parent_stage1_missing']==0,
 'first_branch_stage_is_one':counts['branch_first_stage_not1']==0,
 'all_hash_links_match':all(counts[k]==800 for k in ('parent_branch_hash_match','parent_hash_durable_match','branch_hash_durable_match')),
 'all_task_links_match':counts['same_task']==800,
 'parent_inventory':len(unique)==200 and report['unique_parent_tasks']==103,
 'archive_unchanged':len(files)==20 and not changed,
 'visible_tests_consistent':report['inputs']['visible_tests_match_recorded'] and report['inputs']['visible_tests_covers_parent_tasks'],
 'available_task_input_hash_matches':not tp.exists() or report['inputs']['tasks_current_sha256']==expected_task,
}
report['record_checks']=checks
report['failed_record_checks']=[k for k,v in checks.items() if not v]
out=args.output or ROOT/'work/restoration_audit_97689b9.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps(report,indent=2)+'\n')
if args.include_linkage:
 out.with_name(out.stem+'_linkage.json').write_text(json.dumps(details,indent=2)+'\n')
print(json.dumps({'ref':REF,'counts':counts,'failed_record_checks':report['failed_record_checks'],'task_input_available':tp.exists(),'unchanged_nonanalysis_files':len(files),'output':str(out)},indent=2))
raise SystemExit(bool(report['failed_record_checks']))
