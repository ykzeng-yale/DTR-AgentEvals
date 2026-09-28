"""Authored fault fixtures only, never a model action interface."""
import json,os,subprocess,sys,time
from pathlib import Path
IMAGE='/home/yz2324/project_pi_gt353/yz2324/DTR-AgentEvals/req030-seaborn-image-20260928-a/task.sif'
OLD='/home/yz2324/project_pi_gt353/yz2324/DTR-AgentEvals/req030-seaborn-bound-workspace-20260928-b/workspace.img'
base=['apptainer','exec','--containall','--cleanenv','--no-home','--no-mount','hostfs,bind-paths','--net','--network','none','--pwd','/','--bind',str(Path('workspace.img').resolve())+':/testbed:image-src=/',IMAGE,'/opt/miniconda3/envs/testbed/bin/python','-c']
subprocess.run(['cp','--sparse=always',OLD,'workspace.img'],check=True,timeout=60)
results=[]
for name,code,limit,expect,death in [
 ('normal','print("FIXED_LIFECYCLE")',30,'exited',False),
 ('timeout','import time;time.sleep(60)',5,'deadline',False),
 ('overflow','import os,time;os.write(1,b"x"*2000000);time.sleep(60)',30,'output_limit',False),
 ('owner_death','import time;time.sleep(60)',30,'owner_eof',True)]:
 r,w=os.pipe()
 cmd=[sys.executable,'bounded_supervisor.py','--owner-fd',str(r),'--out',name+'.out','--receipt',name+'.json','--seconds',str(limit),'--']+base+[code]
 p=subprocess.Popen(cmd,pass_fds=(r,));os.close(r)
 if death:time.sleep(5);os.close(w)
 try:p.wait(timeout=40)
 finally:
  if not death:os.close(w)
  if p.poll() is None:p.kill();p.wait()
 x=json.loads(Path(name+'.json').read_text());assert x['reason']==expect,x
 if name=='normal':assert x['returncode']==0 and b'FIXED_LIFECYCLE' in Path(name+'.out').read_bytes()
 try:os.kill(x['pid'],0)
 except ProcessLookupError:pass
 else:raise AssertionError('owned direct process still alive')
 results.append(x)
Path('results.json').write_text(json.dumps(results,indent=2))
