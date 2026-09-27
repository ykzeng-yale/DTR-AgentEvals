"""Only tests import these injections. Production entrypoints have no fake flag."""
import json,os,subprocess,sys,time
from pathlib import Path
from c6_protocol import HERE,put,sha,encode,require
from c3r_arbiter import identity
from c6_sandbox import QualifiedSandbox
from c6_sandbox_backend import Docker
from c6_sandbox_host import exchange

class FakeDocker(Docker):
    def __init__(self,root,contract,fake_root):
        super().__init__(root,contract);self.fake_root=Path(fake_root)
        self.prefix=[sys.executable,str(HERE/'c6_r_fake_docker.py'),str(self.fake_root)]
        self.archive=self.fake_root/'archive';self.archive_sha=sha(b'inert archive');self.archive_bytes=13
    def verify(self,deadline):
        require(self.archive.read_bytes()==b'inert archive','fixture archive identity')
        require(not self.call(['ps','-q'],deadline)['output'].strip(),'peer containers present')
        image=json.loads(self.call(['image','inspect','fixed'],deadline)['output'])[0]
        require(image['Id']==self.contract['image'],'image pin')

class Sandbox(QualifiedSandbox):
    def __init__(self,root,r,fake_root=None):
        r['sandbox']['adapter_sha256']=sha((HERE/'c6_sandbox_host.py').read_bytes())
        r['submission']['checker_sha256']=sha((HERE/'c6_submission_checker.py').read_bytes())
        super().__init__(root,r)
        self.fake_root=Path(fake_root or self.root/'fake');self.fake_root.mkdir(parents=True,exist_ok=True)
        if not (self.fake_root/'archive').exists():put(self.fake_root,'archive',b'inert archive')
        self.guardian=None
    def launch(self,path):
        with (self.root/'guardian.stderr').open('xb') as err:
            self.guardian=subprocess.Popen([sys.executable,str(HERE/'c6_r_driver.py'),'guardian',str(path)],
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=err,start_new_session=True)
        return self.guardian
    def op(self,operation,payload,deadline,executable=None):
        if executable is not None:return super().op(operation,payload,deadline,executable)
        self.count+=1;self.guardian_count+=1;root=self.root/'state';pin=sha(encode(self.r))
        q=dict(operation=operation,payload=payload,deadline=deadline,sequence=self.guardian_count,
            run_id=self.r['run_id'],driver_pid=os.getpid(),driver_identity=self.driver_identity,release_sha256=pin)
        spec=None
        if operation=='preflight':
            spec=dict(root=str(root),release=self.r,release_sha256=pin,driver_pid=os.getpid(),
                driver_identity=self.driver_identity,created_at=self.created_at,
                preflight_deadline=min(self.r['expires_at'],self.created_at+1200),name='dtr-c6-test-owned',
                label='fixture-owner',fake_root=str(self.fake_root))
        return exchange(root,q,spec,self.launch)
    def bind_fixture(self):
        ready=dict(protocol=6,run_id=self.r['run_id'],release_sha256=sha(encode(self.r)),
            worker_commit=self.r['worker_commit'],phase_started=time.time(),
            deadline=self.r['expires_at'],preflight_object={})
        obj=dict(commit='a'*40,blob='b'*40,path=self.r['root']+'/ready.json',sha256=sha(encode(ready)))
        self.bind_phase(ready,obj,time.time()+3);return ready,obj

def descendant_alive(pid):
    try:
        value=subprocess.check_output(['ps','-p',str(pid),'-o','stat='],text=True,stderr=subprocess.DEVNULL,timeout=1).strip()
        return bool(value) and not value.startswith('Z')
    except subprocess.CalledProcessError:return False
