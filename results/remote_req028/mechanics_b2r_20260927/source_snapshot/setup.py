"""Pinned isolated dependency/model retrieval and two-job build for released 028A."""
import hashlib,json,os,subprocess,tarfile,time,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ASSETS=ROOT.parent/'assets'
OUT=ROOT/'results/remote_req028/setup_20260927'
ASSETS.mkdir(exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024**2),b''):h.update(chunk)
    return h.hexdigest()
def download(name,url,expected=None,size=None):
    destination=ASSETS/name
    assert not destination.exists() and not destination.with_suffix(destination.suffix+'.part').exists()
    part=destination.with_suffix(destination.suffix+'.part')
    start=time.time();total=0
    with urllib.request.urlopen(url,timeout=60) as response,part.open('xb') as out:
        while True:
            chunk=response.read(4*1024**2)
            if not chunk:break
            total+=len(chunk)
            if total>3*1024**3:raise RuntimeError('download file cap')
            out.write(chunk)
    actual=sha(part)
    receipt={'url':url,'filename':name,'bytes':total,'sha256':actual,'seconds':time.time()-start,'expected_sha256':expected,'expected_bytes':size}
    (OUT/(name+'.json')).write_text(json.dumps(receipt,indent=2))
    if expected:assert actual==expected,receipt
    if size:assert total==size,receipt
    part.rename(destination)
    print(json.dumps(receipt),flush=True)
    return destination
def extract(path):
    with tarfile.open(path) as tar:
        for member in tar.getmembers():
            target=(ASSETS/member.name).resolve()
            assert ASSETS.resolve() in target.parents
            if member.issym():
                assert ASSETS.resolve() in (target.parent/member.linkname).resolve().parents
            if member.islnk():
                assert ASSETS.resolve() in (ASSETS/member.linkname).resolve().parents
        tar.extractall(ASSETS)
cmake=download('cmake-3.31.8-macos-universal.tar.gz','https://github.com/Kitware/CMake/releases/download/v3.31.8/cmake-3.31.8-macos-universal.tar.gz','d1449f969c54d5c00886d5b643340d493dfb3c81cb39ee29b35453395c11ebf7')
extract(cmake)
commit='4fea119de30f6a923992780f6fd5ccb0bee5d47d'
source=download('llama-'+commit+'.tar.gz','https://codeload.github.com/ggml-org/llama.cpp/tar.gz/'+commit)
extract(source)
cmake_bin=ASSETS/'cmake-3.31.8-macos-universal/CMake.app/Contents/bin/cmake'
llama=ASSETS/('llama.cpp-'+commit)
subprocess.run([str(cmake_bin),'--version'],check=True)
subprocess.run([str(cmake_bin),'-S',str(llama),'-B',str(llama/'build'),'-DCMAKE_BUILD_TYPE=Release','-DGGML_METAL=ON','-DLLAMA_CURL=OFF','-DLLAMA_BUILD_TESTS=OFF'],check=True)
subprocess.run([str(cmake_bin),'--build',str(llama/'build'),'--target','llama-server','-j','2'],check=True)
model=download('Qwen3-4B-Instruct-2507-Q4_K_M.gguf','https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/a06e946bb6b655725eafa393f4a9745d460374c9/Qwen3-4B-Instruct-2507-Q4_K_M.gguf','3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597',2497281120)
for name in ('README.md','config.json','tokenizer_config.json'):
    try:
        req=urllib.request.urlopen('https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/a06e946bb6b655725eafa393f4a9745d460374c9/'+name,timeout=30)
        (OUT/('model_'+name)).write_bytes(req.read(1024**2))
    except Exception as e:
        (OUT/('model_'+name+'.unavailable.json')).write_text(json.dumps({'exception_type':type(e).__name__,'http_status':getattr(e,'code',None)}))
server=llama/'build/bin/llama-server'
(OUT/'complete.json').write_text(json.dumps({'server':str(server),'server_sha256':sha(server),'model':str(model),'model_sha256':sha(model),'finished':time.time()},indent=2))
