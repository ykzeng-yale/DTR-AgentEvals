"""One bounded, inert SSH qualification. Exclusive output; never model execution."""
import hashlib,json,os,shlex,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments/remote_req029'))
from recovery_transport import Transport
from recovery_tests import Tests,BAD
SSH=['ssh','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=8','mac-mini']
def remote(code):
    return subprocess.run(SSH+['python3 -c '+shlex.quote(code)],capture_output=True,text=True,timeout=12,check=True).stdout

def main():
    out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=False)
    helper=ROOT/'experiments/remote_req029/recovery_mailbox.py';pin=hashlib.sha256(helper.read_bytes()).hexdigest()
    root=subprocess.run(SSH+['mktemp -d /tmp/dtr-req029p-qualified.XXXXXXXX'],capture_output=True,text=True,timeout=12,check=True).stdout.strip()
    assert root.startswith('/tmp/dtr-req029p-qualified.') and len(root)<100
    report={'scope':'inert two-role SSH fixture and actual local driver SIGKILL; no model/sandbox','helper_sha256':pin}
    try:
        subprocess.run(['scp','-q','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',str(helper),'mac-mini:'+root+'/helper.py'],capture_output=True,timeout=12,check=True)
        ts={role:Transport(out/role,root,root+'/helper.py',pin,role,time.time()+60,alias='mac-mini',interval=0,fixture=True) for role in ('worker','controller')}
        case=Tests();case.wire_factory=lambda role:ts[role]
        w,c,m,s,_=case.pair([BAD]*3)
        assert len(m.sent)==3 and not s.actions and c.terminal['status']=='repeated_format_error'
        assert all(e['owned_group_absent'] for t in ts.values() for e in t.runner.events)
        report['pair']={'generations_inert':len(m.sent),'actions':len(s.actions),'worker':w.terminal['status'],'controller':c.terminal['status'],'transport_events':{r:t.events for r,t in ts.items()}}
        # A separate explicitly pinned inert helper hangs under its own alarm.
        # Kill only our exact Popen driver; the existing EOF guardian cleans SSH.
        slow="import os,signal,time\nsignal.alarm(5)\nopen("+repr(root+'/slow.pid')+",'x').write(str(os.getpid()))\ntime.sleep(30)\n"
        slowfile=out/'slow_fixture.py';slowfile.write_text(slow)
        subprocess.run(['scp','-q',str(slowfile),'mac-mini:'+root+'/slow.py'],capture_output=True,timeout=12,check=True)
        args=[str(out/'death'),root,root+'/slow.py',hashlib.sha256(slowfile.read_bytes()).hexdigest()]
        driver=out/'driver.py';driver.write_text('import sys,time\nsys.path.insert(0,'+repr(str(ROOT/'experiments/remote_req029'))+')\nfrom recovery_transport import Transport\nt=Transport(*sys.argv[1:],role="controller",deadline=time.time()+30,alias="mac-mini",interval=0,fixture=True)\nt.publish("request",{"inert":True},1)\n')
        with (out/'driver.log').open('xb') as log:
            p=subprocess.Popen([sys.executable,str(driver),*args],stdout=log,stderr=log)
            try:
                until=time.monotonic()+8;pid=None
                while time.monotonic()<until:
                    v=remote('from pathlib import Path;p=Path('+repr(root+'/slow.pid')+');print(p.read_text() if p.exists() else "")').strip()
                    if v:pid=int(v);break
                    time.sleep(.2)
                assert pid and p.poll() is None,'driver/helper not observed live'
                p.kill();p.wait(timeout=3)
            finally:
                if p.poll() is None:p.kill();p.wait(timeout=3)
        deadline=time.monotonic()+8
        receipt=out/'death/process/1.result.json'
        while not receipt.exists() and time.monotonic()<deadline:time.sleep(.1)
        r=json.loads(receipt.read_text());assert r['owned_group_absent'] and r['child_reaped']
        # Wait only for the already-observed helper's fixed five-second alarm.
        while time.monotonic()<deadline:
            v=remote('import subprocess;print(subprocess.run(["ps","-p",'+repr(str(pid))+',"-o","stat="],capture_output=True,text=True).stdout)').strip()
            if not v or v.startswith('Z'):break
            time.sleep(.3)
        assert not v or v.startswith('Z'),'owned remote helper still live'
        report['driver_death']={'driver_returncode':p.returncode,'local_owned_group_absent':True,'remote_helper_live_after_alarm':False,'guardian_error':r['error']}
    finally:
        # Remove only files in the exact freshly-created fixture directory.
        cleanup='from pathlib import Path;p=Path('+repr(root)+'); files=list(p.iterdir()); assert all(x.is_file() and not x.is_symlink() for x in files); [x.unlink() for x in files];p.rmdir();assert not p.exists()'
        remote(cleanup);report['owned_remote_directory_absent']=True
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
