"""Data-only independent development recount and REQ029A archive verification."""
import hashlib,json,re,tarfile
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[2]
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 out=ROOT/'docs/audits/req029_lead_recount_20260927.json'
 design=json.loads((ROOT/'results/code_routing/design.json').read_bytes())
 allow=set(design['train_tasks']); confirm=set(design['confirm_tasks']);assert not allow&confirm
 path=ROOT/'results/code_routing/log/episodes.jsonl';episodes=[];excluded=0
 for line in path.read_text().splitlines():
  m=re.search(r'"episode_id"\s*:\s*"[^\"]*?((?:mbpp|humaneval)/\d+)#',line)
  assert m,'unrecognized episode ID; refuse full parse'
  if m[1] not in allow:excluded+=1;continue
  r=json.loads(line);assert r['task_uid'] in allow and r['task_uid'] not in confirm;episodes.append(r)
 small=[r for r in episodes if r['actions'][0]=='small']
 def counts(rs):
  ds=[d for r in rs for d in r['decisions']]
  assert all(d['eligible'] and d['p_large']==.5 and d['b_obs']==.5 and set(d['available_actions'])=={'small','large'} for d in ds)
  return dict(episodes=len(rs),tasks=len({r['task_uid'] for r in rs}),decision_counts=dict(Counter(str(d['t']) for d in ds)),
   first_only=sum(len(r['decisions'])==1 for r in rs),first_only_hidden_failures=sum(len(r['decisions'])==1 and not r['success'] for r in rs),
   first_only_zero_checks=sum(len(r['decisions'])==1 and r['n_visible_checks']==0 for r in rs),
   selected_backend_counts=dict(Counter(d['model_alias'] for d in ds)),all_logged_propensities_half=True)
 train=counts(episodes);initial_small=counts(small)
 assert train['decision_counts']=={'0':1848,'1':317,'2':236}
 assert initial_small['decision_counts']=={'0':924,'1':183,'2':126}
 package=ROOT/'results/remote_req029/candidate_20260927';mapping=json.loads((package/'member_hashes.json').read_bytes())
 checked={}
 with tarfile.open(package/'inert_evidence.tar.gz') as tar:
  for m in tar.getmembers():
   if m.isfile():checked[m.name]=sha(tar.extractfile(m).read())
 assert checked==mapping
 sources=json.loads((package/'source_hashes.json').read_bytes())
 assert all(sha((ROOT/p).read_bytes())==v for p,v in sources.items())
 receipt=json.loads((ROOT/'work/req029_lead_review_20260927/receipt.json').read_bytes())
 assert receipt['returncode']==0 and receipt['source_unchanged'] and receipt['failure'] is None
 result=dict(scope='Retrospective TRAIN only; no CONFIRM outcome parsing; no new inference',inputs={str(path.relative_to(ROOT)):sha(path.read_bytes()),'design.json':sha((ROOT/'results/code_routing/design.json').read_bytes())},excluded_before_parse=excluded,train=train,initial_small=initial_small,
  req029a=dict(archive_members_matched=len(checked),current_source_pins_matched=len(sources),lead_tests=14,lead_seconds=receipt['elapsed_seconds'],live_qualification=False),
  limitation='Counts describe logger occupancy, not H/P disagreement or causal benefit. Archived v2 exact replay failed under system Python on pilot RNG-availability metadata and floating comparisons; not accepted as exact reproduction. This script independently recounts integer raw TRAIN counts only.')
 out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
