"""Read-only attestation and exact argv for either existing artifact; never loads."""
import hashlib,json,signal,sys,tarfile,time
from pathlib import Path
from comparator_contract import *
import gguf_meta
ASSET_DIR=ROOT.parent/'assets'
SOURCE=ASSET_DIR/('llama.cpp-'+ASSETS['runner_revision'])
SERVER=SOURCE/'build/bin/llama-server'

def paths(r):
    return [ASSET_DIR/ARMS[r['arm']]['model']]+[SERVER.parent/n for n in ASSETS['runner_binary_hashes']]

def argv(r,token,port):
    require(token.startswith('c4-cmp029e-owned-') and type(port) is int and 1<=port<=65535,'owned argv')
    model_contract(r['arm']);cache=ARMS[r['arm']]['cache']
    return [str(SERVER),'-m',str(ASSET_DIR/ARMS[r['arm']]['model']),'--alias',token,
        '--host','127.0.0.1','--port',str(port),'--ctx-size','32768','--parallel','1',
        '--cache-type-k',cache,'--cache-type-v',cache,'--cache-ram','0','--no-cache-prompt',
        '--no-cache-idle-slots','--no-context-shift','--jinja','--seed','20260927028','--temp','0',
        '--n-predict','1536','--threads','2','--threads-batch','2','--threads-http','2',
        '--n-gpu-layers','99','--flash-attn','on','--no-warmup','--batch-size','128','--ubatch-size','32','--verbose']

def attest(r,deadline):
    validate(r);records={};start=time.time()
    def stream(f):
        h=hashlib.sha256();size=0
        while True:
            require(time.time()<deadline,'setup attestation deadline')
            b=f.read(1024**2)
            if not b:break
            h.update(b);size+=len(b)
        return dict(sha256=h.hexdigest(),bytes=size)
    def check(p,pin=None):
        with p.open('rb') as f:v=stream(f)
        if pin:require(v['sha256']==pin,'asset substitution: '+p.name)
        records[str(p)]=v;return v
    model=ASSET_DIR/ARMS[r['arm']]['model']
    require(check(model,ARMS[r['arm']]['sha256'])['bytes']==ARMS[r['arm']]['bytes'],'model size')
    for name,pin in ASSETS['runner_binary_hashes'].items():check(SERVER.parent/name,pin)
    archive=ASSET_DIR/('llama-'+ASSETS['runner_revision']+'.tar.gz')
    check(archive,ASSETS['runner_archive_sha256'])
    with tarfile.open(archive) as tar:
        for m in tar:
            if not m.isfile():continue
            parts=Path(m.name).parts
            require(parts[0]=='llama.cpp-'+ASSETS['runner_revision'] and '..' not in parts,'runner archive path')
            require(stream(tar.extractfile(m))==check(SOURCE.joinpath(*parts[1:])),'exact runner source')
    meta=gguf_meta.read(model)
    require(meta['tokenizer.chat_template']==template(r['arm']),'GGUF template substitution')
    return dict(cell=cell(r),files=records,started=start,finished=time.time(),model_loaded=False)

if __name__=='__main__':
    s=json.loads(Path(sys.argv[1]).read_bytes())
    signal.signal(signal.SIGALRM,lambda *a:(_ for _ in ()).throw(TimeoutError('setup deadline')))
    signal.alarm(300)
    put(Path(sys.argv[2]).parent,Path(sys.argv[2]).name,attest(s['release'],s['deadline']))
