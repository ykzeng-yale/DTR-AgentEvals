"""Read-only attestation of existing assets. Never invokes llama-server."""
import hashlib,json,signal,tarfile,time
from pathlib import Path
from c3_adapter import CONTRACT,CONFIG_SHA
from c2_relay import require,encode,sha
from mechanics_a6r import ROOT,ASSETS,MODEL,SOURCE,SERVER,build_command
import gguf_meta
ARCHIVE_SHA='3321bc787b971a97f6e7f51dfbb3b72119d9194cd7e6088da3810a89d32c1456'
def argv(alias,port):
    require(type(alias) is str and alias.startswith('c4-') and type(port) is int and 1<=port<=65535,'argv inputs')
    command=build_command(alias,port,'A6R');command[command.index('--n-predict')+1]='1536'
    return command
def attest(seconds=300):
    started=time.monotonic();deadline=started+min(seconds,300);records={}
    def hash_stream(stream):
        h=hashlib.sha256();size=0
        while True:
            require(time.monotonic()<deadline,'attestation deadline')
            block=stream.read(1024*1024)
            if not block:break
            h.update(block);size+=len(block)
        return {'sha256':h.hexdigest(),'bytes':size}
    def check(path,expected=None):
        with path.open('rb') as f:r=hash_stream(f)
        if expected:require(r['sha256']==expected,'attestation mismatch: '+path.name)
        records[str(path)]=r;return r
    check(MODEL,CONTRACT['model_sha256']);check(SERVER,CONTRACT['server_sha256'])
    archive=ASSETS/('llama-'+CONTRACT['runner_revision']+'.tar.gz');check(archive,ARCHIVE_SHA)
    source_records={}
    with tarfile.open(archive,'r:gz') as tar:
        for member in tar:
            if not member.isfile():continue
            parts=Path(member.name).parts
            require(parts[0]=='llama.cpp-'+CONTRACT['runner_revision'] and '..' not in parts,'archive source root')
            relative=Path(*parts[1:]);expected=hash_stream(tar.extractfile(member));actual=check(SOURCE/relative)
            require(actual==expected,'archive/source mismatch: '+str(relative));source_records[str(relative)]=actual
    baseline=json.loads((ROOT/'results/remote_req028/mechanics_20260927/manifest.json').read_text())
    for name,expected in baseline['runner_binary_hashes'].items():check(SERVER.parent/name,expected)
    metadata=gguf_meta.read(MODEL);template=metadata['tokenizer.chat_template'].encode()
    require(sha(template)==CONTRACT['template_sha256'],'GGUF native template mismatch')
    native=ROOT/'results/remote_req028/mechanics_c0_20260927/qwen/chat_template.jinja';check(native,CONTRACT['template_sha256'])
    require(time.monotonic()<deadline,'attestation deadline')
    return {'contract_sha256':CONFIG_SHA,'contract':CONTRACT,'started_monotonic':started,'elapsed_seconds':time.monotonic()-started,'source_revision':CONTRACT['runner_revision'],'archive_sha256':ARCHIVE_SHA,'source_files':source_records,'file_records':records,'native_template_bytes':len(template),'native_template_sha256':sha(template),'exact_prospective_argv':argv('c4-locked-attestation',12345),'argv_executed':False,'model_loaded':False,'source_verified_by_archive':True}
def main(out):
    def expire(*args):raise TimeoutError('attestation 300-second hard alarm')
    signal.signal(signal.SIGALRM,expire);signal.alarm(300)
    try:
        result=attest();path=Path(out);path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x') as f:json.dump(result,f,indent=2)
        print(json.dumps({'elapsed_seconds':result['elapsed_seconds'],'source_files':len(result['source_files']),'model_loaded':False}))
    finally:signal.alarm(0)
if __name__=='__main__':
    import sys
    main(sys.argv[1])
