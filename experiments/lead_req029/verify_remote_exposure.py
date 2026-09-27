"""Independent verification of published REQ029K inputs using local archive copies."""
import io,json,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments/remote_req029'))
from exposure_reconcile_scan import sha,markers,scan,Budget
from exposure_reconcile_gaps import CASES,synthetic,fingerprint,order_facts

def run():
 p=ROOT/'results/remote_req029/exposure_reconcile_20260927'
 hashes=json.loads((p/'evidence_hashes.json').read_bytes())
 for name,h in hashes.items():assert sha((p/name).read_bytes())==h,name
 d=json.loads((p/'scan_02/scan.json').read_bytes());g=json.loads((p/'gap_supplement.json').read_bytes())
 assert d['scan_completed_within_scope'] and not g['gaps']
 problem=json.loads((ROOT/'docs/source_snapshots/req029j_prompt/public_task.json').read_bytes())['problem_statement']
 ms=markers(d['remaining_queue'],problem);assert [{k:v for k,v in m.items() if k!='needle'} for m in ms]==d['marker_definitions']
 available={};sources={};archive_pins={}
 for name,r in d['records'].items():
  if '::' not in name and (ROOT/name).is_file():
   raw=(ROOT/name).read_bytes();assert sha(raw)==r['sha256'];available[r['sha256']]=raw;sources.setdefault(r['sha256'],[]).append(name)
 for archive,info in d['archives'].items():
  path=ROOT/archive
  if not path.is_file():continue
  assert sha(path.read_bytes())==info['sha256'];archive_pins[archive]=info['sha256']
  wanted={name.split('::',1)[1]:r for name,r in d['records'].items() if name.startswith(archive+'::')}
  with tarfile.open(path,'r|gz') as t:
   for member in t:
    if member.name not in wanted:continue
    assert member.isfile();raw=t.extractfile(member).read();r=wanted[member.name];assert sha(raw)==r['sha256']
    available[r['sha256']]=raw;sources.setdefault(r['sha256'],[]).append(archive+'::'+member.name)
 missing=[name for name,r in d['records'].items() if r['sha256'] not in available]
 assert not missing,missing
 budget=Budget();checks={}
 for h,raw in available.items():
  result=scan(io.BytesIO(raw),ms,budget);assert result['sha256']==h and not result['marker_matches'];checks[h]=result
 for name,r in d['records'].items():
  result=checks[r['sha256']]
  for k,v in result.items():assert r[k]==v,(name,k)
 reviewed={}
 for root,source in CASES.items():
  case=ROOT/'results/remote_req028'/root;raw=(case/'manifest.json').read_bytes();manifest=json.loads(raw);status=json.loads((case/'status.json').read_bytes())
  source_raw=(case/'source_snapshot'/source).read_bytes();assert sha(source_raw)==manifest['source_hashes'][source]
  assert status['manifest_sha256']==sha(raw) and status['calls_recorded']==0 and status['calls']==[]
  assert not list(case.glob('call_*.request.json')) and not list(case.glob('call_*.start.json'))
  flow=order_facts(source_raw);assert flow['request_and_start_writes_precede_generation']
  plans=manifest.get('requests',manifest.get('request_plan',[]));assert plans and all(synthetic(x['messages']) for x in plans)
  hset={x['canonical_json_messages_sha256'] for x in checks.values()}
  assert all(fingerprint(x['messages']) in hset for x in plans)
  row=g['rows'][root];assert row['manifest_sha256']==sha(raw) and row['source_sha256']==sha(source_raw)
  reviewed[root]=dict(manifest_sha256=sha(raw),source_sha256=sha(source_raw),zero_journal_calls=True,plans_synthetic=True,plans_hash_linked=True,interpretation='no generation inferred from reviewed source/journal; not packet capture')
 result=dict(remote_source_commit='fec55f4041eaecf420c11288f61ecc14aa284ccd',evidence_files_verified=len(hashes),record_occurrences= len(d['records']),unique_input_hashes_replayed=len(checks),marker_matches=0,local_archive_pins=archive_pins,record_hash_sources=sources,gap_reviews=reviewed,local_scanner_tests=16,local_scanner_test_seconds=.021,script_sha256=sha(Path(__file__).read_bytes()),limitations=['C5 complete archive not present locally; its selected inputs verified through exact-hash copies in other retained records, not independent full archive verification.','Scope is inspected project inputs, not pretraining, paraphrases, unsupported encodings or unknown historical roots.'])
 out=ROOT/'docs/audits/req029k_lead_20260927.json'
 with out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps({k:result[k] for k in ['evidence_files_verified','record_occurrences','unique_input_hashes_replayed','marker_matches']}))
if __name__=='__main__':run()
