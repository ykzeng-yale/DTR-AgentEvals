"""Verify immutable C5 runs and retain all three development snapshots."""
import hashlib,json,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/remote_req028/c5_candidate_20260927'
RUNS=('c5_setup_20260927','c5_setup_final_20260927','c5_setup_approved_candidate_20260927','c5_setup_exec_deadline_20260927','c5_setup_exact_native_20260927')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    OUT.mkdir(parents=True,exist_ok=True);runs=[]
    for name in RUNS:
        root=OUT.parent/name;hashes=json.loads((root/'sha256.json').read_text());target=OUT/(name+'.tar.gz');assert not target.exists()
        for path,value in hashes.items():assert digest(root/path)==value,(name,path)
        with tarfile.open(target,'w:gz') as tar:tar.add(root,arcname=name)
        with tarfile.open(target,'r:gz') as tar:
            for path,value in hashes.items():assert hashlib.sha256(tar.extractfile(name+'/'+path).read()).hexdigest()==value
        runs.append({'run':name,'verified_hashes':len(hashes),'archive_sha256':digest(target),'archive_bytes':target.stat().st_size,'execution':json.loads((root/'execution.json').read_text())})
    final=OUT.parent/RUNS[-1];observations=[]
    for path in final.rglob('*observer.json'):
        data=json.loads(path.read_text());assert not data.get('teardown_errors'),(path,data)
        for key,value in data.items():
            if 'absent_before_teardown' in key:assert value is True
        observations.append({'path':str(path.relative_to(final)),'observation':data})
    for p in final.rglob('supervisor_exit.json'):assert json.loads(p.read_text())['cleanup']['owned_absent'],str(p)
    for p in final.rglob('cleanup_verified.json'):assert json.loads(p.read_text())['owned_absent'],str(p)
    for p in (final/'source_snapshot').iterdir():assert digest(p)==digest(ROOT/'experiments/remote_req028'/p.name)
    size=sum(p.stat().st_size for name in RUNS for p in (OUT.parent/name).rglob('*') if p.is_file())+sum(p.stat().st_size for p in OUT.iterdir() if p.is_file());assert size<100*1024**2
    summary={'runs':runs,'cumulative_test_wall_seconds':sum(r['execution']['elapsed_seconds'] for r in runs),'logical_artifact_bytes':size,'final_supervisor_cleanup_receipts':len(list(final.rglob('supervisor_exit.json'))),'final_adapter_cleanup_receipts':len(list(final.rglob('cleanup_verified.json'))),'source_matches_final_snapshot':True,'activation_authorized_now':False,'final_observers':observations}
    with (OUT/'verification.json').open('x') as f:json.dump(summary,f,indent=2)
    print(json.dumps({k:v for k,v in summary.items() if k!='final_observers'},indent=2))
if __name__=='__main__':main()
