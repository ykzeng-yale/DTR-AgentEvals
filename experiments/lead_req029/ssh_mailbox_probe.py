import subprocess,json,hashlib,time,shlex
from pathlib import Path
source=Path('experiments/remote_req029/recovery_mailbox.py');h=hashlib.sha256(source.read_bytes()).hexdigest()
ssh=['ssh','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=8','mac-mini']
start=time.monotonic();events=[];root=None
try:
 r=subprocess.run(ssh+['mktemp -d /tmp/dtr-req029o-mailbox.XXXXXXXX'],capture_output=True,text=True,timeout=12,check=True);root=r.stdout.strip();assert root.startswith('/tmp/dtr-req029o-mailbox.') and len(root)<100
 subprocess.run(['scp','-q','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',str(source),'mac-mini:'+root+'/helper.py'],capture_output=True,timeout=12,check=True)
 cmd="python3 -c "+shlex.quote("import hashlib;print(hashlib.sha256(open("+repr(root+'/helper.py')+",'rb').read()).hexdigest())")
 got=subprocess.run(ssh+[cmd],capture_output=True,text=True,timeout=12,check=True).stdout.strip();assert got==h
 q=dict(operation='publish',kind='request',sequence=1,payload={'nonce':'DTR_REQ029O_SSH_FIXED_20260927'})
 for label,req,role in [('publish',q,'controller'),('read',dict(q,operation='read',payload=None),'worker'),('conflict',dict(q,payload={'nonce':'different'}),'controller')]:
  t=time.monotonic();r=subprocess.run(ssh+['python3 '+shlex.quote(root+'/helper.py')+' '+shlex.quote(root)+' '+role],input=json.dumps(req),capture_output=True,text=True,timeout=12)
  if label=='conflict':assert r.returncode!=0 and 'immutable conflict' in r.stderr;value={'rejected':True}
  else:assert r.returncode==0,r.stderr;value=json.loads(r.stdout)
  events.append(dict(operation=label,seconds=time.monotonic()-t,result=value))
 assert events[0]['result']==events[1]['result']
finally:
 if root:
  cmd='rm -- '+shlex.quote(root+'/helper.py')+' '+shlex.quote(root+'/request-01.json')+' && rmdir -- '+shlex.quote(root)+' && test ! -e '+shlex.quote(root)
  cleaned=subprocess.run(ssh+[cmd],capture_output=True,text=True,timeout=12).returncode==0
  assert cleaned,'owned fixture cleanup failed'
Path('results/local_req029/ssh_mailbox_20260927/result.json').write_text(json.dumps(dict(source_sha256=h,source_commit='d11bda50',scope='fixed data only; no model/guardian/production protocol qualification',events=events,owned_fixture_removed=cleaned,total_seconds=time.monotonic()-start),indent=2)+'\n')
