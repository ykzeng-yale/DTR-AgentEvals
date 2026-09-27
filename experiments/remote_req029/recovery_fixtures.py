"""Only inert tests import these injections. Production CLI exposes no fixture flag."""
import copy,json,os,subprocess,sys,time
from pathlib import Path
from recovery_contract import *
from recovery_model import Model,Lifecycle,free_port
from comparator_http import HTTP
from recovery_sandbox import QualifiedSandbox
from recovery_sandbox_host import exchange
from recovery_backend import Docker
from c3r_arbiter import identity
GOOD=dict(pressure_level=1,free_percent=80,swap_used_mib=0,owned_rss_bytes=0,foreign_inference=[],disk_free_bytes=20*1024**3)

def release(arm='qwen',seconds=55):
    r=disabled();r.update(transport_config_sha256='a'*64,execution_authorized=True,arm=arm,model=model_contract(arm),
        run_id='cmp029o-fixture',root='results/remote_req029/comparator_runs/cmp029o-fixture',
        expires_at=time.time()+seconds,worker_commit='a'*40,controller_commit='a'*40,source_hashes=inventory(),
        task=dict(task_id='inert__fixture-1',base_commit='b'*40,untouched_development=True,exposure_ledger_sha256='e'*64,queue_sha256='f'*64),
        sandbox=dict(image='sha256:'+'c'*64,head='d'*40,archive_path='work/local_req029/INERT/archive.tar',
            archive_sha256=sha(b'inert archive'),archive_bytes=13,import_module='fixture',python='/opt/miniconda3/envs/testbed/bin/python',
            docker_executable=DOCKER,docker_sha256='e'*64,context='colima-dtr',qualified=True,qualification_sha256='f'*64,
            limits=LIMITS,cleanup_reserve_seconds=15,archive_ownership='extracting-user'),
        initial_messages_utf8=encode([dict(role='system',content='INERT shared system, no test/reference content.'),
                                   dict(role='user',content='INERT generic issue, never a task release.')]).decode())
    r['initial_messages_sha256']=sha(r['initial_messages_utf8'].encode());r['config_sha256']=sha(encode(r['model']))
    return r,sha(encode(r))

class InertModel(Model):
    def __init__(self,root,mode='normal'):
        super().__init__({});self.root=Path(root);self.mode=mode;self.loads=0
    def start(self,r,pin,root):
        self.loads+=1;require(self.loads==1,'no reload');now=time.time()
        spec=dict(inert_test=True,fixture_sha256=sha((HERE/'comparator_fixture.py').read_bytes()),
            phase_started=now,phase_deadline=min(now+55,r['expires_at']),load_deadline=min(now+8,r['expires_at']),
            token='c4-cmp029e-owned-inert-'+str(time.time_ns()),port=free_port())
        self.life=Lifecycle(self.root,spec)
        put(self.root,'fixture.release.json',r);put(self.root,'mode',self.mode.encode());put(self.root,'fake_sample.json',GOOD)
        self.life.launch()
        while not self.life.health():time.sleep(.02)
        self.http=HTTP(self.root/'http',self.life,r)
        return now

class FakeDocker(Docker):
    def __init__(self,root,contract,fake_root):
        super().__init__(root,contract);self.fake_root=Path(fake_root)
        self.prefix=[sys.executable,str(HERE/'comparator_fake_docker.py'),str(self.fake_root)]
        self.archive=self.fake_root/'archive'
    def verify(self,deadline):
        require(self.archive.read_bytes()==b'inert archive','inert archive')
        require(not self.call(['ps','-q'],deadline)['output'].strip(),'fake peers')
        image=json.loads(self.call(['image','inspect','fixed'],deadline)['output'])[0]
        require(image['Id']==self.contract['image'],'fake image')

class Sandbox(QualifiedSandbox):
    def __init__(self,root,r):
        super().__init__(root,r);self.fake_root=self.root/'fake';self.fake_root.mkdir()
        put(self.fake_root,'archive',b'inert archive');put(self.fake_root,'contract.json',r['sandbox'])
        self.guardian=None
    def launch(self,path):
        with (self.root/'guardian.stderr').open('xb') as err:
            self.guardian=subprocess.Popen([sys.executable,str(HERE/'recovery_fixture_driver.py'),'guardian',str(path)],
                stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=err,start_new_session=True)
        return self.guardian
    def op(self,operation,payload,deadline,executable=None):
        require(executable is None,'no host command/checker in fixture')
        self.count+=1;self.guardian_count+=1;root=self.root/'state';pin=sha(encode(self.r))
        q=dict(operation=operation,payload=payload,deadline=deadline,sequence=self.guardian_count,run_id=self.r['run_id'],
            driver_pid=os.getpid(),driver_identity=self.driver_identity,release_sha256=pin)
        spec=None
        if operation=='preflight':
            spec=dict(root=str(root),release=self.r,release_sha256=pin,driver_pid=os.getpid(),driver_identity=self.driver_identity,
                created_at=self.created_at,preflight_deadline=min(self.r['expires_at'],self.created_at+1200),
                name='dtr-cmp029e-owned-fixture',label='fixture-owner',fake_root=str(self.fake_root))
        return exchange(root,q,spec,self.launch)
    def close(self):
        try:return super().close()
        finally:
            if self.guardian:self.guardian.wait(timeout=4)
