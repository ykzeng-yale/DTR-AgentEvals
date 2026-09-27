"""Read-only compressed/uncompressed layer validation. No extraction or Docker."""
import gzip,hashlib,json,signal,time,resource
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def main():
    start=time.monotonic();total=0;records=[]
    meta=ROOT/'results/local_req029/image_metadata_20260927'
    raw=(meta/'django__django-16560.amd64.json').read_bytes()
    assert hashlib.sha256(raw).hexdigest()=='0bafff953ce186aa261162d4091549fb4ad49df938900474b5f070d511bb1604'
    manifest=json.loads(raw);cfg=(meta/'django__django-16560.config.json').read_bytes()
    assert 'sha256:'+hashlib.sha256(cfg).hexdigest()==manifest['config']['digest']
    ids=json.loads(cfg)['rootfs']['diff_ids'];assert len(ids)==len(manifest['layers'])==10
    def digest(f):
        nonlocal total
        h=hashlib.sha256();n=0
        while True:
            assert time.monotonic()-start<120,'verification deadline'
            b=f.read(1024**2)
            if not b:break
            n+=len(b);total+=len(b);assert total<=16*1024**3,'16GiB total streamed bytes cap'
            h.update(b)
        return n,'sha256:'+h.hexdigest()
    for layer,diff in zip(manifest['layers'],ids):
        p=ROOT/'work/local_req029/django_image_layers_20260927'/(layer['digest'][7:]+'.gz')
        with p.open('rb') as f:n,sha=digest(f)
        assert (n,sha)==(layer['size'],layer['digest'])
        with gzip.open(p,'rb') as f:unpacked,actual=digest(f)
        assert actual==diff
        records.append(dict(compressed_bytes=n,compressed_sha256=sha,uncompressed_bytes=unpacked,diff_id=actual))
    result=dict(records=records,compressed_bytes=sum(x['compressed_bytes'] for x in records),uncompressed_stream_bytes=sum(x['uncompressed_bytes'] for x in records),seconds=time.monotonic()-start,extracted=False,docker_invoked=False,source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    out=ROOT/'results/local_req029/image_acquisition_20260927/verification.json'
    with out.open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='records'}))
if __name__=='__main__':
    def alarm(*args):raise TimeoutError('verification deadline')
    signal.signal(signal.SIGALRM,alarm);signal.alarm(120);resource.setrlimit(resource.RLIMIT_CPU,(120,120));main()
