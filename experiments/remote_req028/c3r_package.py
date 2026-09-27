"""Package immutable C3R test trees (including local Git internals) as data archives."""
import hashlib,json,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/remote_req028/c3r_publication_20260927'
RUNS=('c3r_setup_20260927','c3r_setup_second_20260927','c3r_setup_final_20260927')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    OUT.mkdir(parents=True,exist_ok=True);records=[]
    for name in RUNS:
        root=OUT.parent/name;hashes=json.loads((root/'sha256.json').read_text())
        for path,value in hashes.items():assert digest(root/path)==value,(name,path)
        target=OUT/(name+'.tar.gz');assert not target.exists()
        with tarfile.open(target,'w:gz') as tar:tar.add(root,arcname=name)
        with tarfile.open(target,'r:gz') as tar:
            for path,value in hashes.items():assert hashlib.sha256(tar.extractfile(name+'/'+path).read()).hexdigest()==value
        records.append({'run':name,'verified_hashes':len(hashes),'archive_sha256':digest(target),'archive_bytes':target.stat().st_size,'execution':json.loads((root/'test_execution.json').read_text())})
    final=OUT.parent/RUNS[-1]
    observations=[]
    for p in final.rglob('*observer.json'):
        d=json.loads(p.read_text());assert not d.get('teardown_errors'),d
        for k,v in d.items():
            if 'absent_before_teardown' in k:assert v is True
        observations.append({'path':str(p.relative_to(final)),'observation':d})
    for p in final.rglob('cleanup_verified.json'):assert json.loads(p.read_text())['owned_absent'] is True
    for p in (final/'source_snapshot').iterdir():assert digest(p)==digest(ROOT/'experiments/remote_req028'/p.name)
    size=sum(p.stat().st_size for n in RUNS for p in (OUT.parent/n).rglob('*') if p.is_file())+sum(p.stat().st_size for p in OUT.iterdir() if p.is_file())
    assert size<100*1024**2
    summary={'runs':records,'cumulative_suite_wall_seconds':sum(r['execution']['elapsed_seconds'] for r in records),'new_run_and_archive_bytes':size,'final_observers':observations,'final_cleanup_receipts':len(list(final.rglob('cleanup_verified.json'))),'source_matches_final_snapshot':True}
    with (OUT/'verification.json').open('x') as f:json.dump(summary,f,indent=2)
    print(json.dumps({k:v for k,v in summary.items() if k!='final_observers'},indent=2))
if __name__=='__main__':main()
