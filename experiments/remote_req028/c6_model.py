"""Resident Qwen interface; concrete reviewed C5 lifecycle + C4 native HTTP."""
import json,os,subprocess,sys,time
from pathlib import Path
from c2_relay import encode,sha,require
from c3_adapter import PENDING
from c3r_arbiter import identity
from c3r_hooks import ProcessHandle
from c4_lifecycle import ProductionLifecycle
from c4_attest import MODEL,SERVER
from c4_http import HTTP,body
from c5_lifecycle import Lifecycle as Previous,free_port
from c6_protocol import put
from c6_process import Runner
from a6r_gate import admit
HERE=Path(__file__).parent

class Lifecycle(Previous):
    def check(self):
        if getattr(self,'latched_failure',None):
            raise RuntimeError(self.latched_failure)
        for name in ('supervisor_exit.json','stop.request','telemetry_latest.json'):
            path=self.root/name
            if not path.exists():continue
            try:
                terminal=name!='telemetry_latest.json' or json.loads(path.read_text()).get('violation') is not None
            except BaseException:
                terminal=True
            if terminal:
                self.latched_failure='latched supervisor terminal/guard: '+name
                raise RuntimeError(self.latched_failure)
        return super().check()

    def launch(self):
        require(self.proc is None,'one residency only')
        put(self.root,'supervisor.json',self.spec)
        with (self.root/'supervisor.stderr').open('xb') as log:
            self.proc=subprocess.Popen([sys.executable,str(HERE/'c6_supervisor.py'),str(self.root/'supervisor.json')],
                stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log,start_new_session=True)
        self.supervisor_record={'pid':self.proc.pid,'identity':identity(self.proc.pid),'command':[str(self.root/'supervisor.json')]}

class Model:
    def __init__(self,approval_args,setup_deadline=None):
        self.approval_args=approval_args
        self.setup_deadline=setup_deadline
        self.life=None
        self.http=None

    def start(self,r,pin,root):
        root=Path(root)
        outer=getattr(self,'admission_outer_deadline',r['expires_at'])
        setup_deadline=min(r['expires_at'],outer,self.setup_deadline or time.time()+300)
        stats={}
        for p in (MODEL,SERVER):
            s=p.stat();stats[str(p)]=[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
        Runner(root/'attestation-process').run([sys.executable,str(HERE/'c4_attest.py'),str(root/'attestation.json')],setup_deadline)
        window=min(r['expires_at'],outer,time.time()+900)
        sampler=ProductionLifecycle(root/'admission_samples',window)
        def observe(reading,reason,count,kind):
            put(root,'admission/%02d.json'%count,dict(sample=reading,reason=reason,count=count,kind=kind))
        def launch(last):
            started=time.time();deadline=min(r['expires_at'],started+1800)
            spec=dict(inert_test=False,approval_args=self.approval_args,release=r,release_sha256=pin,
                asset_stats=stats,phase_started=started,phase_deadline=deadline,
                load_deadline=min(deadline,started+180,outer),admission_outer_deadline=outer,
                token='c4-c6-owned-'+str(os.getpid())+'-'+str(time.time_ns()),port=free_port())
            put(root,'model_window.json',spec)
            self.life=Lifecycle(root/'supervision',spec)
            self.life.launch()
            while not self.life.health():time.sleep(.02)
            self.http=HTTP(root/'http',self.life)
            return started
        try:
            return admit(sampler.sample,time.time,time.sleep,observe,launch,window)
        finally:
            sampler.stop('admission finished')

    def check(self):
        require(self.life is not None,'no residency')
        self.life.check()

    def wait(self,h,deadline):
        try:
            while True:
                self.check();require(time.time()<deadline,'HTTP phase deadline')
                value=h.poll()
                if value is not PENDING:return value
                time.sleep(.01)
        finally:
            h.close()

    def bind(self,messages,deadline):
        return self.wait(self.http.begin_bind(messages,deadline-time.time()),deadline)

    def generate(self,messages,deadline):
        return self.wait(self.http.begin_generate(body(messages),deadline-time.time()),deadline).decode()

    def stop(self):
        try:
            return {'owned_absent':True,'not_loaded':True} if self.life is None else self.life.stop()
        finally:
            if self.http:self.http.close()
