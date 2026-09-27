"""REQ029U Matplotlib original-path qualification; fixed lead-authored code only."""
import hashlib,json,os,re,selectors,subprocess,time,uuid,signal,resource
from pathlib import Path
D=['/Users/yukangzengcmac/.local/dtr-runtime/bin/docker','--context','colima-dtr'];IMAGE='sha256:bf91db11a6e02de9ecababb891a08368cb5489c29f493197774148771dd8d24d'
root=Path(__file__).resolve().parents[2];out=root/'results/local_req029/matplotlib_writable_u2_20260927';out.mkdir(parents=True,exist_ok=False)
work=root/'work/local_req029/matplotlib_writable_u2_20260927';work.mkdir(parents=True,exist_ok=False)
def expired(*args):raise TimeoutError('120 second fixed probe wall cap')
signal.signal(signal.SIGALRM,expired);signal.alarm(120);resource.setrlimit(resource.RLIMIT_CPU,(60,60));os.nice(10)
deadline=time.monotonic()+120;owned=[];rec={'started':time.time(),'image':IMAGE,'scope':'fixed Matplotlib source/import only; no task tests','source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
def run(args,**kw):return subprocess.run(args,capture_output=True,timeout=min(20,max(.1,deadline-time.monotonic())),**kw)
def call(*args):
 r=run(D+list(args));assert r.returncode==0,r.stderr.decode()[:2000];return r.stdout
try:
 assert not call('ps','-q').strip()
 f=run(['memory_pressure']);free=int(re.search(rb'System-wide memory free percentage: (\d+)%',f.stdout).group(1));assert free>=40
 assert run(['sysctl','-n','kern.memorystatus_vm_pressure_level']).stdout.strip()==b'1'
 st=os.statvfs(root);assert st.f_bavail*st.f_frsize>=12*1024**3
 rec['host_free_percent']=free
 archive=root/'work/local_req029/matplotlib_writable_20260927/testbed.tar'
 assert archive.stat().st_size==478930944 and hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()=='46ed7a0d26b126792cb796f776749907c901bcdcbfef30a72cc82a48ef02cb77'
 rec['archive']={'path':str(archive.relative_to(root)),'bytes':478930944,'sha256':'46ed7a0d26b126792cb796f776749907c901bcdcbfef30a72cc82a48ef02cb77'}
 cid=call('create','--name','dtr-029u2-'+uuid.uuid4().hex[:8],'--platform','linux/amd64','--cpus','1','--memory','1g','--memory-swap','1g','--pids-limit','128','--network','none','--cap-drop','ALL','--security-opt','no-new-privileges','--read-only','--tmpfs','/testbed:rw,exec,nosuid,nodev,size=512m','--tmpfs','/tmp:rw,nosuid,nodev,size=64m',IMAGE,'/bin/sleep','60').decode().strip();assert re.fullmatch('[0-9a-f]{64}',cid);owned.append(cid)
 cfg=json.loads(call('inspect',cid))[0];h=cfg['HostConfig'];rec['settings']={k:h.get(k) for k in ('ReadonlyRootfs','Memory','MemorySwap','NanoCpus','PidsLimit','NetworkMode','CapDrop','SecurityOpt','Tmpfs','Binds')};assert h['ReadonlyRootfs'] and h['Memory']==h['MemorySwap']==1024**3 and h['NanoCpus']==10**9 and h['NetworkMode']=='none' and h['Binds'] is None
 assert h['PidsLimit']==128 and h['CapDrop']==['ALL'] and h['SecurityOpt']==['no-new-privileges']
 assert h['Tmpfs']=={'/testbed':'rw,exec,nosuid,nodev,size=512m','/tmp':'rw,nosuid,nodev,size=64m'}
 assert not h.get('Privileged') and not h.get('Devices') and not h.get('Mounts') and not h.get('VolumesFrom') and not cfg['Config'].get('Volumes')
 call('start',cid)
 with archive.open('rb') as f:r=run(D+['exec','-i',cid,'tar','--no-same-owner','-xf','-','-C','/testbed'],stdin=f)
 assert r.returncode==0,r.stderr.decode()[:2000]
 code=(root/'experiments/lead_req029/matplotlib_writable_probe.py').read_bytes();rec['probe_sha256']=hashlib.sha256(code).hexdigest()
 r=run(D+['exec','-i',cid,'/opt/miniconda3/envs/testbed/bin/python','-'],input=code);assert len(r.stdout)+len(r.stderr)<=65536
 rec.update(returncode=r.returncode,stdout=r.stdout.decode(),stderr=r.stderr.decode());assert r.returncode==0,'fixed probe failed';rec['status']='PASS'
except BaseException as e:rec.update(status='FAILED',error=repr(e))
finally:
 signal.alarm(0)
 rec['cleanup']=[]
 for cid in owned:
  r=subprocess.run(D+['rm','-f',cid],capture_output=True,timeout=15)
  s=subprocess.run(D+['inspect',cid],capture_output=True,timeout=10)
  rec['cleanup'].append({'id':cid,'rm_returncode':r.returncode,'inspect_returncode':s.returncode,'inspect_stderr':s.stderr.decode(),'owned_absent':s.returncode!=0 and b'no such' in s.stderr.lower()})
 rec['finished']=time.time();(out/'receipt.json').write_text(json.dumps(rec,indent=2)+'\n')
print(json.dumps(rec,indent=2))
