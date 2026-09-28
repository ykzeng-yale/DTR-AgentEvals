"""Actual controller SIGKILL and namespace-contained setsid child fixture."""
import json,os,signal,subprocess,sys,time
from pathlib import Path
TOKEN='DTR030_DRIVERKILL_CHILD_20260928_A'
def matching():
 found=[]
 for p in Path('/proc').iterdir():
  if p.name.isdigit():
   try:
    if p.stat().st_uid==os.getuid() and TOKEN.encode() in (p/'cmdline').read_bytes():found.append(int(p.name))
   except (OSError,PermissionError):pass
 return found
if sys.argv[1:] == ['owner']:
 r,w=os.pipe()
 image='/home/yz2324/project_pi_gt353/yz2324/DTR-AgentEvals/req030-seaborn-image-20260928-a/task.sif'
 code='import subprocess,sys,time; subprocess.Popen([sys.executable,"-c","import time;time.sleep(90)",'+repr(TOKEN)+'],start_new_session=True); print("READY",flush=True); time.sleep(90)'
 cmd=['apptainer','exec','--containall','--cleanenv','--no-home','--no-mount','hostfs,bind-paths','--net','--network','none','--pwd','/',image,'/opt/miniconda3/envs/testbed/bin/python','-c',code]
 p=subprocess.Popen([sys.executable,'bounded_supervisor.py','--owner-fd',str(r),'--out','kill.out','--receipt','kill.json','--seconds','30','--']+cmd,pass_fds=(r,));os.close(r)
 Path('supervisor.pid').write_text(str(p.pid))
 time.sleep(60)
else:
 assert not matching(),'fixture marker already present'
 owner=subprocess.Popen([sys.executable,__file__,'owner'])
 try:
  deadline=time.monotonic()+20
  while time.monotonic()<deadline:
   if Path('kill.out').exists() and b'READY' in Path('kill.out').read_bytes():break
   time.sleep(.05)
  else:raise AssertionError('container ready missing')
  before=matching();assert before,'child marker not visible before kill'
  owner.kill();owner.wait(timeout=3)
  deadline=time.monotonic()+8
  while time.monotonic()<deadline:
   if Path('kill.json').exists() and not matching():break
   time.sleep(.05)
  receipt=json.loads(Path('kill.json').read_text())
  assert receipt['reason']=='owner_eof',receipt
  after=matching();assert not after,after
  Path('results.json').write_text(json.dumps(dict(controller_returncode=owner.returncode,marked_pids_before=before,marked_pids_after=after,supervisor=receipt),indent=2))
 finally:
  if owner.poll() is None:owner.kill();owner.wait()
 # Slurm wall limit remains ultimate containment if an assertion fails.
