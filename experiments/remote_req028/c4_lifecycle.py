"""Real attestation/telemetry hooks; production start unconditionally LOCKED."""
import json,os,subprocess,sys,time
from pathlib import Path
import guard
from c2_relay import require,sha,encode
from c3_adapter import CONTRACT,PENDING
from c3r_hooks import ProcessHandle,alive
from c3r_arbiter import identity
from c4_attest import argv
HERE=Path(__file__).parent
class ProductionLifecycle:
    def __init__(self,root,deadline):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.deadline=deadline;self.counter=0;self.record=None;self.handles=[];self.parent=os.getppid();self.parent_identity=identity(self.parent);self.model_deadline=None;self.admission_started=False
    def remaining(self,cap):
        left=min(cap,self.deadline-time.time());require(left>0,'fixed lifecycle deadline');return left
    def sample(self):
        self.counter+=1;spec=self.root/('sample_'+str(self.counter)+'.json');out=self.root/('sample_'+str(self.counter)+'.out.json');timeout=self.remaining(5)
        spec.write_bytes(encode({'operation':'telemetry','owned_group':None if self.record is None else self.record['pid'],'deadline':time.time()+timeout}))
        h=ProcessHandle([sys.executable,str(HERE/'c4_worker.py'),str(spec),str(out)],timeout,out);self.handles.append(h)
        try:
            while True:
                value=h.poll()
                if value is not PENDING:return value
                time.sleep(.01)
        finally:h.close()
    def begin_setup(self,timeout):
        out=self.root/'asset_attestation.json';h=ProcessHandle([sys.executable,str(HERE/'c4_attest.py'),str(out)],self.remaining(min(300,timeout)));self.handles.append(h)
        class Setup:
            def poll(self):
                value=h.poll()
                if value is PENDING:return value
                result=json.loads(out.read_text());require(result['contract']==CONTRACT,'asset attestation contract');return dict(CONTRACT)
            def cancel(self):h.cancel()
        return Setup()
    def frozen_argv(self,alias,port):return argv(alias,port)
    def prepare_plan(self,release_raw,release_pin,request_raw,entry,attestation_raw,attestation_pin,alias,port):
        from c3_adapter import validate_release,validate_request,CONFIG_SHA
        from c2_relay import digest
        now=time.time();release=validate_release(release_raw,release_pin,now);require(entry in release['requests'],'plan request approval');validate_request(request_raw,release,entry,now)
        require(sha(attestation_raw)==digest(attestation_pin),'asset attestation pin');attestation=json.loads(attestation_raw)
        require(attestation['contract']==CONTRACT and attestation['contract_sha256']==CONFIG_SHA and attestation['source_verified_by_archive'] is True,'asset contract')
        if self.model_deadline is None:self.model_deadline=min(self.deadline,release['deadline'],now+1800)
        return {'startup_locked':True,'release_sha256':release_pin,'request':entry,'asset_attestation_sha256':attestation_pin,'argv':self.frozen_argv(alias,port),'telemetry':'guard.sample','driver_pid':os.getpid(),'driver_identity':identity(os.getpid()),'model_deadline':self.model_deadline,'load_deadline':min(self.model_deadline,now+180),'admission':{'function':'a6r_gate.admit','minimum_free_percent':75,'normal_pressure':1,'no_foreign_inference':True,'minimum_disk_bytes':12*1024**3,'window_seconds':900,'maximum_reads':31,'two_passing_reads_spacing_seconds':60,'final_pre_launch_recheck':True},'supervision':'supervisor owns pipe-gated child before exec; production command execution remains denied'}
    def admit_then_load(self,contract,observe):
        from a6r_gate import admit
        require(not self.admission_started,'no admission renewal');self.admission_started=True
        return admit(self.sample,time.time,time.sleep,observe,lambda sample:self.begin_load(contract,self.remaining(180)),min(self.deadline,time.time()+900))
    def begin_load(self,*args,**kwargs):raise PermissionError('C4 real model startup LOCKED until new exact release')
    def has_owner(self):return self.record is not None
    def owned_alive(self):return self.record is not None and alive(self.record)
    def parent_alive(self):
        try:return identity(self.parent)==self.parent_identity
        except subprocess.CalledProcessError:return False
    def stop(self,reason):
        for h in self.handles:h.close()
        require(not self.owned_alive(),'production model never authorized');return {'owned_absent':True}
class InertSupervisedLifecycle:
    def __init__(self,root,fixture_pin,mode='idle',pause_at=None,telemetry='fixture'):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.fixture_pin=fixture_pin;self.mode=mode;self.pause_at=pause_at;self.telemetry=telemetry;self.supervisor=None;self.record=None;self.endpoint=None
        require(fixture_pin==sha((HERE/'c4_fixture.py').read_bytes()),'inert fixture allowlist')
    def begin_load(self,contract,timeout):
        require(contract==CONTRACT and self.supervisor is None,'no reload/config change')
        spec={'root':str(self.root),'driver_pid':os.getpid(),'driver_identity':identity(os.getpid()),'deadline':time.time()+min(timeout,55),'fixture_executable_sha256':self.fixture_pin,'mode':self.mode,'pause_at':self.pause_at,'telemetry':self.telemetry,'token':'c4-owned-'+str(time.time_ns())}
        (self.root/'supervisor_spec.json').write_bytes(encode(spec))
        self.supervisor=subprocess.Popen([sys.executable,str(HERE/'c4_supervisor.py'),str(self.root/'supervisor_spec.json')],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
        self.supervisor_record={'pid':self.supervisor.pid,'identity':identity(self.supervisor.pid),'command':[str(self.root/'supervisor_spec.json')]}
        outer=self
        class Load:
            def poll(self):
                require(outer.supervisor.poll() is None,'supervisor stopped')
                if (outer.root/'owner.json').exists():outer.record=json.loads((outer.root/'owner.json').read_text())
                if (outer.root/'running.json').exists():
                    if outer.mode=='idle':return {'supervised':True}
                    if (outer.root/'ready.json').exists():outer.endpoint=json.loads((outer.root/'ready.json').read_text());return outer.endpoint
                return PENDING
            def cancel(self):outer.stop('load cancellation')
        return Load()
    def has_owner(self):return self.supervisor is not None
    def owned_alive(self):
        if self.record is None and (self.root/'owner.json').exists():self.record=json.loads((self.root/'owner.json').read_text())
        return self.record is not None and alive(self.record)
    def stop(self,reason):
        if self.supervisor is None:return {'owned_absent':True}
        # Closing the private liveness pipe is cleanup even if audit storage fails.
        if self.supervisor.stdin and not self.supervisor.stdin.closed:self.supervisor.stdin.close()
        self.supervisor.wait(timeout=12)
        receipt=json.loads((self.root/'supervisor_exit.json').read_text());require(receipt['cleanup']['owned_absent'] and not self.owned_alive(),'supervised cleanup unconfirmed');return receipt['cleanup']
