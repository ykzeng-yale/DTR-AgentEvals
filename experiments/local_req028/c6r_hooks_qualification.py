"""Lead-approved fixed real-Docker fixtures; NO model/task/benchmark execution."""
import sys,os,json,time,subprocess,hashlib,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'experiments/remote_req028'))
from c3r_arbiter import identity
from c6_protocol import encode,sha,put,IMAGE,HEAD
from c6_sandbox_backend import Docker,DOCKER
from c6_sandbox_guardian import Guardian
from c6_sandbox_host import exchange
SOURCE='20aa347ff02c1df4eac994cf8ff960cb1a12458d'
OUT=ROOT/'results/local_req028/c6r_hooks_20260927'
def pins():
 files=subprocess.check_output(['git','ls-tree','-r','--name-only',SOURCE,'--','experiments/remote_req028'],cwd=ROOT,text=True).splitlines();count=0
 for n in files:
  if n.endswith(('.py','.json')):
   assert (ROOT/n).read_bytes()==subprocess.check_output(['git','show',SOURCE+':'+n],cwd=ROOT),n;count+=1
 return count
def guardian(path):
 s=json.loads(Path(path).read_text());Guardian(s,Docker(Path(s['root'])/'docker',s['release']['sandbox'])).run()
def driver(case):
 pins();root=OUT/case;root.mkdir(parents=True,exist_ok=False);state=root/'state';now=time.time();me=identity(os.getpid());label=uuid.uuid4().hex*2
 r={'run_id':'c6-local-'+case,'root':'results/local_req028/c6r_hooks_20260927/'+case,'expires_at':now+120,'worker_commit':SOURCE,'sandbox':{'image':IMAGE,'head':HEAD,'context':'colima-dtr','docker_executable':DOCKER,'docker_sha256':sha(Path(DOCKER).read_bytes())}}
 pin=sha(encode(r));spec=dict(root=str(state),release=r,release_sha256=pin,driver_pid=os.getpid(),driver_identity=me,created_at=now,preflight_deadline=now+90,name='dtr-c6-local-'+case+'-'+label[:12],label=label,qualification_only=True)
 seq=0;g=None
 def launch(path):
  nonlocal g
  log=(root/'guardian.stderr').open('xb');g=subprocess.Popen([sys.executable,__file__,'guardian',str(path)],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=log,start_new_session=True);log.close();return g
 def op(name,payload={},seconds=40):
  nonlocal seq
  seq+=1;q=dict(operation=name,payload=payload,deadline=time.time()+seconds,sequence=seq,run_id=r['run_id'],driver_pid=os.getpid(),driver_identity=me,release_sha256=pin)
  return exchange(state,q,spec if name=='preflight' else None,launch)
 rec={'case':case,'source':SOURCE,'qualification_only':True}
 try:
  rec['preflight']=op('preflight')
  ready={'protocol':6,'run_id':r['run_id'],'release_sha256':pin,'worker_commit':SOURCE,'phase_started':time.time(),'deadline':r['expires_at']}
  obj={'commit':SOURCE,'blob':subprocess.check_output(['git','hash-object','--stdin'],input=encode(ready),cwd=ROOT).decode().strip(),'path':r['root']+'/ready.json','sha256':sha(encode(ready))}
  rec['phase']=op('bind_phase',{'ready':ready,'object':obj})
  if case=='death':
   put(root,'ready_for_driver_kill.json',{'driver_pid':os.getpid(),'guardian_pid':g.pid})
   time.sleep(90);raise AssertionError('driver was not killed')
  cmd={'happy':"printf 'C6_HOOK_OK\\n' > .c6-fixed-hook; cat .c6-fixed-hook",'timeout':"sleep 30",'overflow':"python -c \"import sys;sys.stdout.write('x'*1048577)\""}[case]
  try:
   rec['action']=op('execute',{'command':cmd},2 if case=='timeout' else 15)
   assert case=='happy','expected failure did not occur'
   rec['diff']=op('diff');assert '.c6-fixed-hook' in rec['diff']['diff']
  except Exception as e:
   if case=='happy':raise
   rec['expected_error']=repr(e)
 finally:
  if g:
   try:rec['close']=op('close',seconds=20)
   except Exception as e:rec['close_error']=repr(e)
   g.wait(timeout=20)
  put(root,'driver_receipt.json',rec)
def master():
 assert not OUT.exists();OUT.mkdir(parents=True);count=pins();summary={'source':SOURCE,'source_files_checked':count,'fixtures':[]}
 D=[DOCKER,'--context','colima-dtr']
 assert not subprocess.check_output(D+['ps','-aq']).strip()
 assert subprocess.check_output(['sysctl','-n','kern.memorystatus_vm_pressure_level']).strip()==b'1'
 import re
 assert int(re.search(rb'System-wide memory free percentage: (\d+)%',subprocess.check_output(['memory_pressure'])).group(1))>=40
 st=os.statvfs(ROOT);assert st.f_bavail*st.f_frsize>=12*1024**3
 for case in ('happy','timeout','overflow','death'):
  log=(OUT/(case+'.log')).open('xb');p=subprocess.Popen([sys.executable,__file__,'driver',case],stdout=log,stderr=subprocess.STDOUT);log.close()
  if case=='death':
   end=time.time()+55
   while not (OUT/case/'ready_for_driver_kill.json').exists() and p.poll() is None and time.time()<end:time.sleep(.1)
   assert (OUT/case/'ready_for_driver_kill.json').exists(),'death fixture not ready'
   p.kill()
  p.wait(timeout=70)
  terminal=OUT/case/'state/terminal.json';end=time.time()+25
  while not terminal.exists() and time.time()<end:time.sleep(.1)
  assert terminal.exists(),'no terminal cleanup receipt'
  t=json.loads(terminal.read_text());summary['fixtures'].append({'case':case,'driver_rc':p.returncode,'terminal':t});put(OUT,'summary-'+case+'.json',summary)
  assert t['cleanup']['owned_absent'],'cleanup unconfirmed'
  assert not subprocess.check_output(D+['ps','-aq']).strip(),'container remains'
  if case!='death':assert p.returncode==0,'fixture failed'
 print(json.dumps(summary))
if __name__=='__main__':
 if len(sys.argv)==1:master()
 elif sys.argv[1]=='guardian':guardian(sys.argv[2])
 elif sys.argv[1]=='driver':driver(sys.argv[2])
 else:raise ValueError('fixed fixture modes')
