"""Read-only REQ029S mini loose-input reconciliation. Public JSON on stdin."""
import hashlib, importlib.util, json, os, resource, signal, sys, time
from pathlib import Path

def sha(raw): return hashlib.sha256(raw).hexdigest()

def run(root, public):
    signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError('60s wall cap')))
    signal.alarm(60)
    resource.setrlimit(resource.RLIMIT_CPU, (60,60))
    os.nice(10)
    root=Path(root)
    assert sha(public)=='256173c0dcb9182396843c35c7cc1db528cb736ba1620b667c6aef73c9e3ece0'
    task=json.loads(public)
    module=root/'experiments/remote_req029/exposure_reconcile_scan.py'
    assert sha(module.read_bytes())=='c69de76002036b2e4dc783dc889fe95b2713a46442c6b736d5cd86f27b0e6a36'
    spec=importlib.util.spec_from_file_location('prior_scan',module);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    b=m.Budget(seconds=55,read_cap=300*1024**2)
    ms=m.markers([task['instance_id']],task['problem_statement'])
    for item in ms:item['labels']=[s.replace('django:','matplotlib:') for s in item['labels']]
    paths=set();missing=[]
    for top in m.ROOTS:
        base=root/'results/remote_req028'/top
        if not base.is_dir() or base.is_symlink():missing.append(str(base.relative_to(root)));continue
        for p in m.walk(base,b):
            if m.selected(str(p.relative_to(root/'results/remote_req028'))):paths.add(p)
    for top in ('comparator_runtime','comparator_runs'):
        base=root/'results/remote_req029'/top
        if not base.is_dir() or base.is_symlink():missing.append(str(base.relative_to(root)));continue
        for p in m.walk(base,b):
            parts=p.relative_to(base).parts
            if p.suffix=='.json' and ('request' in parts or ('http' in parts and p.name.endswith('.input.json')) or 'native' in parts):paths.add(p)
    records={}
    for p in sorted(paths):
        if p.is_symlink() or not p.is_file() or p.stat().st_size>16*1024**2:raise ValueError('invalid input record')
        before=p.stat()
        with p.open('rb') as f:r=m.scan(f,ms,b)
        after=p.stat()
        assert (before.st_size,before.st_mtime_ns,before.st_ino)==(after.st_size,after.st_mtime_ns,after.st_ino),'record changed'
        # Publish hashes/matches only, never archived instruction text or outputs.
        records[str(p.relative_to(root))]={k:r[k] for k in ('sha256','bytes','marker_matches','canonical_id_mentions')}
    signal.alarm(0)
    return dict(public_sha256=sha(public),selector_sha256=sha(module.read_bytes()),records=records,
        markers=[{k:v for k,v in x.items() if k!='needle'} for x in ms],missing_roots=missing,
        record_count=len(records),bytes_read=b.bytes,matched_records=sum(bool(x['marker_matches']) for x in records.values()),
        elapsed_seconds=time.monotonic()-b.start,peak_sampled_rss=b.peak_rss,
        scope='Reviewed REQ028 loose actual-input roots plus REQ029 comparator runtime/run request/native/HTTP-input records on mini.',
        limitations=['Archives are not rescanned here; prior queue-ID archive audit remains separate.', 'Setup fixtures, evaluator/reference files, outputs and held CONFIRM are excluded.', 'No universal untouchedness/pretraining claim; exact markers only. No model/container/network listener launched.'])

if __name__=='__main__':print(json.dumps(run(sys.argv[1],sys.stdin.buffer.read(65537)),sort_keys=True))
