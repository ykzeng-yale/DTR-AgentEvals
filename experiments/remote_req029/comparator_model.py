"""Exactly one approved artifact residency, guarded setup/admission and native HTTP."""
import json,os,subprocess,sys,time
from pathlib import Path
from comparator_contract import HERE,encode,sha,require,put
from c3_adapter import PENDING
from c3r_arbiter import identity
from c3r_hooks import ProcessHandle
from c4_lifecycle import ProductionLifecycle
from comparator_attest import paths
from comparator_http import HTTP,body
from c5_lifecycle import Lifecycle as Previous,free_port
from c6_process import Runner
from a6r_gate import admit

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
            self.proc=subprocess.Popen([sys.executable,str(HERE/'comparator_supervisor.py'),str(self.root/'supervisor.json')],
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
        setup_started=time.time()
        stats={}
        for p in paths(r):
            s=p.stat();stats[str(p)]=[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
        put(root,'attestation.spec.json',dict(release=r,deadline=setup_deadline))
        Runner(root/'attestation-process').run([sys.executable,str(HERE/'comparator_attest.py'),str(root/'attestation.spec.json'),str(root/'attestation.json')],setup_deadline)
        put(root,'setup.cost.json',dict(started=setup_started,finished=time.time()))
        window=min(r['expires_at'],outer,time.time()+900)
        put(root,'admission.window.json',dict(started=time.time(),deadline=window,max_reads=31))
        sampler=ProductionLifecycle(root/'admission_samples',window)
        def observe(reading,reason,count,kind):
            put(root,'admission/%02d.json'%count,dict(sample=reading,reason=reason,count=count,kind=kind))
        def launch(last):
            started=time.time();deadline=min(r['expires_at'],started+1800)
            spec=dict(inert_test=False,approval_args=self.approval_args,release=r,release_sha256=pin,
                asset_stats=stats,phase_started=started,phase_deadline=deadline,
                load_deadline=min(deadline,started+180,outer),admission_outer_deadline=outer,
                token='c4-cmp029e-owned-'+str(os.getpid())+'-'+str(time.time_ns()),port=free_port())
            put(root,'model_window.json',spec)
            self.life=Lifecycle(root/'supervision',spec)
            self.life.launch()
            while not self.life.health():time.sleep(.02)
            cache=r['model']['artifact']['cache']
            lines=(self.life.root/'server.stderr.log').read_text().splitlines()
            allocation=[line for line in lines if 'llama_kv_cache: size =' in line]
            require(allocation and ('K ('+cache+')') in allocation[-1] and ('V ('+cache+')') in allocation[-1],'effective KV cache')
            put(root,'effective.cache.json',dict(cache=cache,allocation=allocation[-1],cell=r['arm']))
            self.http=HTTP(root/'http',self.life,r)
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
        self.last_dispatch=None
        try:
            return self.wait(self.http.begin_generate(body(messages),deadline-time.time()),deadline).decode()
        finally:
            path=self.http.root/(str(self.http.counter)+'.http.json')
            if path.exists():
                events=json.loads(path.read_bytes())
                self.last_dispatch=next((e for e in events if e['path']=='/v1/chat/completions' and e.get('request_sent')),None)

    def stop(self):
        try:
            return {'owned_absent':True,'not_loaded':True} if self.life is None else self.life.stop()
        finally:
            if self.http:self.http.close()
