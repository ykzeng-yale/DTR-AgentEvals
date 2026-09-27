"""Immutable evidence packager, including the missing historical member mapping."""
import argparse,hashlib,json,re,tarfile
from pathlib import Path
from c6_protocol import ROOT,HERE,put,sha

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--runs',nargs='+',required=True)
    a=p.parse_args();out=ROOT/a.out;out.mkdir(parents=True,exist_ok=False)
    base=ROOT/'results/remote_req028';old=base/'c6_candidate_20260927/inert_evidence.tar.gz'
    require_sha='87376404e9ca5ea2a83173f6ad50f1a46b7e144d9c9e8ed91121c2e99df904e6'
    assert sha(old.read_bytes())==require_sha
    previous={}
    with tarfile.open(old) as t:
        for m in t:
            if m.isfile():previous[m.name]=sha(t.extractfile(m).read())
    raw=json.dumps(previous,sort_keys=True,separators=(',',':')).encode()
    assert len(previous)==14560 and sha(raw)=='679aa8e90c0e68d70605714168b26c486ec3ef1055bd7977bfab80db222aa5bb'
    put(out,'prior_c6_member_inventory.json',raw)
    members={};runs=[]
    for name in a.runs:
        folder=base/name
        receipt=json.loads((folder/'receipt.json').read_text());log=(folder/'unittest.log').read_text()
        run={k:receipt.get(k) for k in ('elapsed_seconds','returncode','max_sampled_rss_bytes','source_unchanged','runner_failure')}
        run.update(path=name,tests=int(re.search(r'Ran (\d+) tests',log)[1]),
            c6r_test_methods=len(re.findall(r'^test_.*\(c6_r_tests.Tests\)',log,re.M)),
            c6_prior_test_methods=len(re.findall(r'^test_.*\(c6_tests.Tests\)',log,re.M)))
        runs.append(run)
        for f in folder.rglob('*'):
            if f.is_file():members[str(f.relative_to(base))]=sha(f.read_bytes())
    put(out,'current_member_inventory.json',json.dumps(members,sort_keys=True,separators=(',',':')).encode())
    archive=out/'inert_evidence.tar.gz'
    with tarfile.open(archive,'w:gz') as t:
        for name in sorted(members):t.add(base/name,arcname=name,recursive=False)
    checked=0
    with tarfile.open(archive) as t:
        for m in t:
            if m.isfile():assert sha(t.extractfile(m).read())==members[m.name];checked+=1
    assert checked==len(members)
    total=sum(r['elapsed_seconds'] for r in runs);assert total<=300
    sources={str(f.relative_to(ROOT)):sha(f.read_bytes()) for f in HERE.iterdir() if f.is_file() and f.suffix in ('.py','.json')}
    inputs=['docs/source_snapshots/req028_c6_mini/docker.py.txt','docs/source_snapshots/req028_c6_mini/LICENSE.md',
        'docs/source_snapshots/req028_c6_mini/manifest.json','docs/req028_c6_evaluator_candidate_20260927.json',
        'docs/req028_c6_writable_sandbox_20260927.md','docs/req028_c6r_integration_20260927.md']
    record=dict(scope='C6R implementation and inert/fake Docker/local Git only',runs=runs,cumulative_test_seconds=total,
        historical_archive_sha256=require_sha,historical_members=14560,historical_mapping_sha256=sha(raw),
        historical_mapping='prior_c6_member_inventory.json',current_members=checked,
        current_mapping_sha256=sha((out/'current_member_inventory.json').read_bytes()),
        archive_sha256=sha(archive.read_bytes()),archive_bytes=archive.stat().st_size,
        source_hashes=sources,input_hashes={x:sha((ROOT/x).read_bytes()) for x in inputs},
        real_model_executed=False,real_docker_executed=False,live_github_polling=False,execution_approved=False,
        lead_original_c6_result='32/33, one guard failure; not superseded by remote prior 33/33',
        readiness={'percent':55,'delta':0,'range':[45,65]})
    put(out,'receipt.json',json.dumps(record,indent=2).encode())
    print(json.dumps({'cumulative_seconds':total,'files':checked,'archive_bytes':archive.stat().st_size,'historical_mapping_members':len(previous)}))

if __name__=='__main__':main()
