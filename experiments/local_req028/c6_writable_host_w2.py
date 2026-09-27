"""One W2 original-path qualification; fixed lead-authored code only."""
import hashlib,json,os,re,selectors,subprocess,time,uuid
from pathlib import Path
D=['/Users/yukangzengcmac/.local/dtr-runtime/bin/docker','--context','colima-dtr'];IMAGE='sha256:ff1716c2ea207eeb3b717cd5deb3213f923f4d445234edd9a53d035dce834997'
root=Path(__file__).resolve().parents[2];out=root/'results/local_req028/c6_writable_w2_20260927';out.mkdir(parents=True,exist_ok=False)
work=root/'work/local_req028/c6_writable_w2_20260927';work.mkdir(parents=True,exist_ok=False)
deadline=time.monotonic()+120;owned=[];rec={'started':time.time(),'image':IMAGE,'scope':'fixed W2 only','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
def run(args,**kw):return subprocess.run(args,capture_output=True,timeout=min(20,max(.1,deadline-time.monotonic())),**kw)
def call(*args):
 r=run(D+list(args));assert r.returncode==0,r.stderr.decode()[:2000];return r.stdout
try:
 assert not call('ps','-q').strip()
 f=run(['memory_pressure']);free=int(re.search(rb'System-wide memory free percentage: (\d+)%',f.stdout).group(1));assert free>=40
 assert run(['sysctl','-n','kern.memorystatus_vm_pressure_level']).stdout.strip()==b'1'
 st=os.statvfs(root);assert st.f_bavail*st.f_frsize>=12*1024**3
 rec['host_free_percent']=free
 source=call('create','--name','dtr-c6-w2-source-'+uuid.uuid4().hex[:8],IMAGE).decode().strip();assert re.fullmatch('[0-9a-f]{64}',source);owned.append(source)
 archive=work/'testbed.tar';p=subprocess.Popen(D+['cp',source+':/testbed/.','-'],stdout=subprocess.PIPE,stderr=subprocess.PIPE);sel=selectors.DefaultSelector();sel.register(p.stdout,selectors.EVENT_READ);cap_deadline=time.monotonic()+20;count=0
 try:
  with archive.open('xb') as f:
   while True:
    assert time.monotonic()<cap_deadline,'archive timeout'
    if not sel.select(.1):continue
    chunk=os.read(p.stdout.fileno(),65536)
    if not chunk:break
    count+=len(chunk);assert count<=512*1024**2,'archive cap';f.write(chunk)
  assert p.wait(timeout=2)==0,p.stderr.read(2000)
 finally:
  if p.poll() is None:p.kill();p.wait(timeout=2)
  sel.close()
 rec['archive']={'path':str(archive.relative_to(root)),'bytes':count,'sha256':hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()}
 call('rm',source)
 cid=call('create','--name','dtr-c6-w2-'+uuid.uuid4().hex[:8],'--platform','linux/amd64','--cpus','1','--memory','1g','--memory-swap','1g','--pids-limit','128','--network','none','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--tmpfs','/testbed:rw,nosuid,nodev,size=512m','--tmpfs','/tmp:rw,nosuid,nodev,size=64m',IMAGE,'/bin/sleep','60').decode().strip();assert re.fullmatch('[0-9a-f]{64}',cid);owned.append(cid)
 cfg=json.loads(call('inspect',cid))[0];h=cfg['HostConfig'];rec['settings']={k:h.get(k) for k in ('ReadonlyRootfs','Memory','MemorySwap','NanoCpus','PidsLimit','NetworkMode','CapDrop','SecurityOpt','Tmpfs','Binds')};assert h['ReadonlyRootfs'] and h['Memory']==h['MemorySwap']==1024**3 and h['NanoCpus']==10**9 and h['NetworkMode']=='none' and h['Binds'] is None
 call('start',cid)
 with archive.open('rb') as f:r=run(D+['exec','-i',cid,'tar','-xf','-','-C','/testbed'],stdin=f)
 assert r.returncode==0,r.stderr.decode()[:2000]
 code=(root/'experiments/local_req028/c6_writable_probe_w2.py').read_bytes();rec['probe_sha256']=hashlib.sha256(code).hexdigest()
 r=run(D+['exec','-i',cid,'/opt/miniconda3/envs/testbed/bin/python','-'],input=code);assert len(r.stdout)+len(r.stderr)<=65536
 rec.update(returncode=r.returncode,stdout=r.stdout.decode(),stderr=r.stderr.decode());assert r.returncode==0,'fixed probe failed';rec['status']='PASS'
except BaseException as e:rec.update(status='FAILED',error=repr(e))
finally:
 rec['cleanup']=[]
 for cid in owned:
  r=subprocess.run(D+['rm','-f',cid],capture_output=True,timeout=15)
  s=subprocess.run(D+['inspect',cid],capture_output=True,timeout=10)
  rec['cleanup'].append({'id':cid,'rm_returncode':r.returncode,'inspect_returncode':s.returncode,'inspect_stderr':s.stderr.decode(),'owned_absent':s.returncode!=0 and b'no such' in s.stderr.lower()})
 rec['finished']=time.time();(out/'receipt.json').write_text(json.dumps(rec,indent=2)+'\n')
print(json.dumps(rec,indent=2))
