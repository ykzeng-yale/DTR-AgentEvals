"""Package inert evidence only; never invokes evaluator/Docker/model."""
import hashlib,json,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'experiments/remote_req029'))
from django_eval_contract import inventory,git,sha
OUT=Path(__file__).resolve().parent
def write(name,value):
    with (OUT/name).open('x') as f:json.dump(value,f,indent=2,sort_keys=True);f.write('\n')
source_commit=sys.argv[1]
pins=inventory()
for name,pin in pins.items():
    assert sha(git('show',source_commit+':'+name))==pin,name
runs={p.parent.name:json.loads(p.read_bytes()) for p in sorted(OUT.glob('inert_*/receipt.json'))}
assert runs and all(r['source_unchanged'] and r['returncode']==0 and r['failure'] is None for r in runs.values())
assert runs['inert_final_verified']['source_after']==pins
seconds=sum(r['elapsed_seconds'] for r in runs.values())
assert seconds<300
members={}
for folder in sorted(OUT.glob('inert_*')):
    if not folder.is_dir():continue
    for p in sorted(folder.rglob('*')):
        assert not p.is_symlink(),p
        if p.is_file():members[str(p.relative_to(OUT))]=sha(p.read_bytes())
archive=OUT/'inert_evidence.tar.gz'
with tarfile.open(archive,'x:gz') as tf:
    for name in members:tf.add(OUT/name,arcname=name,recursive=False)
with tarfile.open(archive,'r:gz') as tf:
    actual={}
    for m in tf:
        assert m.isfile()
        actual[m.name]=sha(tf.extractfile(m).read())
assert actual==members
write('member_hashes.json',members)
write('source_hashes.json',pins)
summary=dict(source_commit=source_commit,source_pins=len(pins),runs={k:dict(returncode=r['returncode'],
    elapsed_seconds=r['elapsed_seconds'],source_unchanged=r['source_unchanged']) for k,r in runs.items()},
    cumulative_test_seconds=seconds,peak_sampled_rss_bytes=max(x['rss'] for r in runs.values() for x in r['samples']),
    archive_sha256=sha(archive.read_bytes()),archive_bytes=archive.stat().st_size,archive_regular_members=len(members),
    actual_docker_model_official_tests_evaluator=False,enabled_production_approval_authored=False,
    cpu='one serial test driver; math threads=1; macOS affinity not enforced',rss='sampled process tree; not OS-hard-enforced',
    readiness_percent=55,readiness_change_points=0,readiness_range_percent=[45,65])
summary['retained_bytes_before_summary_and_report']=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())
assert summary['retained_bytes_before_summary_and_report']<100*1024**2
write('summary.json',summary)
print(json.dumps(summary,indent=2))
