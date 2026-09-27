"""Verify and package immutable C4 test artifacts, including local Git internals."""
import hashlib,json,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/remote_req028/c4_publication_20260927'
RUNS=('c4_setup_20260927','c4_setup_second_20260927','c4_setup_final_20260927')
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
        records.append({'run':name,'verified_hashes':len(hashes),'archive_sha256':digest(target),'archive_bytes':target.stat().st_size,'execution':json.loads((root/'execution.json').read_text())})
    final=OUT.parent/RUNS[-1];observers=[]
    for p in final.rglob('*observer.json'):
        d=json.loads(p.read_text());assert not d.get('teardown_errors'),d
        for k,v in d.items():
            if 'absent_before_teardown' in k:assert v is True
        observers.append({'path':str(p.relative_to(final)),'observation':d})
    for p in final.rglob('supervisor_exit.json'):assert json.loads(p.read_text())['cleanup']['owned_absent'] is True,str(p)
    for p in final.rglob('cleanup_verified.json'):assert json.loads(p.read_text())['owned_absent'] is True
    for p in (final/'source_snapshot').iterdir():assert digest(p)==digest(ROOT/'experiments/remote_req028'/p.name)
    attestation=OUT.parent/'c4_attestation_20260927/attestation.json'
    size=sum(p.stat().st_size for n in RUNS for p in (OUT.parent/n).rglob('*') if p.is_file())+sum(p.stat().st_size for p in OUT.iterdir() if p.is_file())+attestation.stat().st_size
    assert size<100*1024**2
    summary={'runs':records,'cumulative_test_wall_seconds':sum(r['execution']['elapsed_seconds'] for r in records),'attestation_elapsed_seconds':json.loads(attestation.read_text())['elapsed_seconds'],'attestation_sha256':digest(attestation),'artifact_bytes_before_summary_report':size,'final_observers':observers,'final_supervisor_cleanup_receipts':len(list(final.rglob('supervisor_exit.json'))),'final_c3_cleanup_receipts':len(list(final.rglob('cleanup_verified.json'))),'source_matches_final_snapshot':True}
    with (OUT/'verification.json').open('x') as f:json.dump(summary,f,indent=2)
    print(json.dumps({k:v for k,v in summary.items() if k!='final_observers'},indent=2))
if __name__=='__main__':main()
