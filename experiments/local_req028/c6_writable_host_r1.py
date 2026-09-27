"""One immutable W1 qualification. Fixed script only; no model input."""
import hashlib,json,os,re,subprocess,time,uuid
from pathlib import Path
D=['/Users/yukangzengcmac/.local/dtr-runtime/bin/docker','--context','colima-dtr']
IMAGE='sha256:ff1716c2ea207eeb3b717cd5deb3213f923f4d445234edd9a53d035dce834997'
root=Path(__file__).resolve().parents[2];out=root/'results/local_req028/c6_writable_r1_20260927';out.mkdir(parents=True,exist_ok=False)
start=time.monotonic();deadline=start+60;cid=None
rec={'image':IMAGE,'started':time.time(),'scope':'fixed authored W1 only','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
def run(args,**kw):
 return subprocess.run(args,capture_output=True,timeout=min(20,max(.1,deadline-time.monotonic())),**kw)
def call(*args):
 r=run(D+list(args));assert r.returncode==0,r.stderr.decode()[:2000];return r.stdout
try:
 assert not call('ps','-q').strip(),'peer container present'
 free=run(['memory_pressure']).stdout.decode();pct=int(re.search(r'System-wide memory free percentage: (\d+)%',free).group(1));assert pct>=40
 pressure=run(['sysctl','-n','kern.memorystatus_vm_pressure_level']);assert pressure.returncode==0 and pressure.stdout.strip()==b'1'
 st=os.statvfs(root);assert st.f_bavail*st.f_frsize>=12*1024**3
 rec['host_free_percent']=pct;rec['host_pressure']=1
 source=(root/'experiments/local_req028/c6_writable_probe.py').read_bytes();rec['probe_sha256']=hashlib.sha256(source).hexdigest()
 name='dtr-c6-w1-'+uuid.uuid4().hex[:10];rec['name']=name
 cid=call('create','--name',name,'--platform','linux/amd64','--cpus','1','--memory','1g','--memory-swap','1g','--pids-limit','128','--network','none','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--tmpfs','/work:rw,nosuid,nodev,size=512m','--tmpfs','/tmp:rw,nosuid,nodev,size=64m','--env','PYTHONPATH=/work/testbed',IMAGE,'/bin/sleep','60').decode().strip();assert re.fullmatch('[0-9a-f]{64}',cid);rec['id']=cid
 cfg=json.loads(call('inspect',cid))[0];h=cfg['HostConfig'];rec['settings']={k:h.get(k) for k in ('ReadonlyRootfs','Memory','MemorySwap','NanoCpus','PidsLimit','NetworkMode','CapDrop','SecurityOpt','Tmpfs','Binds')};assert h['ReadonlyRootfs'] and h['Memory']==h['MemorySwap']==1024**3 and h['NanoCpus']==10**9 and h['NetworkMode']=='none' and h['Binds'] is None
 call('start',cid)
 r=run(D+['exec','-i',cid,'/opt/miniconda3/envs/testbed/bin/python','-'],input=source);assert len(r.stdout)+len(r.stderr)<=65536
 rec.update(returncode=r.returncode,stdout=r.stdout.decode(),stderr=r.stderr.decode(),status='PASS' if r.returncode==0 else 'FAILED');assert r.returncode==0,'fixed probe failed'
except BaseException as e:rec.update(status='FAILED',error=repr(e))
finally:
 if cid:
  r=subprocess.run(D+['rm','-f',cid],capture_output=True,timeout=15);rec['cleanup_returncode']=r.returncode
  r=subprocess.run(D+['inspect',cid],capture_output=True,timeout=10);rec['owned_absent']=r.returncode!=0 and b'no such' in r.stderr.lower()
 rec['finished']=time.time();(out/'receipt.json').write_text(json.dumps(rec,indent=2)+'\n')
 (out/'sha256.json').write_text(json.dumps({'receipt.json':hashlib.sha256((out/'receipt.json').read_bytes()).hexdigest()},indent=2)+'\n')
print(json.dumps(rec,indent=2))
