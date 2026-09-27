"""Pinned Matplotlib OCI data acquisition; reuses bounded stream, no extraction."""
import hashlib,json,re,resource,signal,sys,os
from pathlib import Path
import image_acquire as stream
TASK='matplotlib__matplotlib-20826'
DIGEST='sha256:7ae350b0a6b3fe3cc4165ac10b81dbdcace7a65b8a608988043611a05473e3ef'
def manifest(raw):
    assert 'sha256:'+hashlib.sha256(raw).hexdigest()==DIGEST,'manifest pin'
    m=json.loads(raw)
    assert sum(x['size'] for x in m['layers'])==2258509781,'layer total'
    for x in m['layers']:
        assert re.fullmatch('sha256:[0-9a-f]{64}',x['digest']) and type(x['size']) is int and x['size']>0,'layer identity'
    return m
def run(root):
    stream.TASK=TASK;stream.DIGEST=DIGEST
    stream.REPO='swebench/sweb.eval.x86_64.matplotlib_1776_matplotlib-20826'
    stream.LIMIT=3*1024**3;stream.manifest=manifest
    return stream.run(root)
if __name__=='__main__':
    resource.setrlimit(resource.RLIMIT_CPU,(300,300));os.nice(10)
    def expired(*args):raise TimeoutError('900-second acquisition deadline')
    signal.signal(signal.SIGALRM,expired);signal.alarm(900)
    r=run(Path(sys.argv[1]));print(json.dumps({'error':r['error'],'layers':len(r['completed_layers']),'bytes':r['response_body_bytes']}));sys.exit(bool(r['error']))
