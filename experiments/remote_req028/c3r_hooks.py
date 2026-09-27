"""Concrete bounded processes, sockets and local-Git operations. Production remains locked."""
import hashlib,json,os,signal,subprocess,sys,tempfile,time
from pathlib import Path
import b3_stop,guard
from c3r_arbiter import identity,same,stop as bounded_stop
from c2_relay import encode,sha,require
from c3_adapter import CONTRACT,CONFIG_SHA,PENDING
HERE=Path(__file__).parent
def alive(record):
    try:
        state=subprocess.check_output(['ps','-p',str(record['pid']),'-o','stat='],text=True,timeout=1).strip()
        return bool(state) and not state.startswith('Z') and same(record)
    except (subprocess.CalledProcessError,ProcessLookupError):return False
def safe_stop(owner,record,reason):
    audit_error=None
    try:result=bounded_stop(owner,'c3r',reason)
    except BaseException as e:
        audit_error=repr(e);result={}
        # Journal outage must not prevent termination. Revalidate identity and use
        # KILL fallback only, never a second unjournaled TERM.
        if alive(record):os.killpg(record['pid'],signal.SIGKILL)
    until=time.monotonic()+3
    while alive(record) and time.monotonic()<until:time.sleep(.01)
    require(not alive(record),'owned cleanup unconfirmed')
    return dict(result,owned_absent=True,audit_error=audit_error)
class ProcessHandle:
    def __init__(self,argv,timeout,output=None):
        require(timeout>0,'process deadline')
        self.deadline=time.monotonic()+timeout;self.output=output
        self.error_file=tempfile.TemporaryFile()
        self.child=subprocess.Popen(argv,start_new_session=True,stdout=subprocess.DEVNULL,stderr=self.error_file,env={k:v for k,v in os.environ.items() if not k.startswith('LLAMA_ARG_')})
        try:self.record={'pid':self.child.pid,'identity':identity(self.child.pid,min(1,timeout)),'command':argv}
        except BaseException:
            terminate_direct(self.child);self.error_file.close();raise
    def poll(self):
        if self.child.poll() is None:
            if time.monotonic()>=self.deadline:self.cancel();raise TimeoutError('subprocess deadline')
            return PENDING
        if self.child.returncode:
            self.error_file.seek(0);detail=self.error_file.read(4096).decode(errors='replace')
            raise RuntimeError('worker failed: '+detail)
        if self.output is None:return self.child.returncode
        raw=Path(self.output).read_bytes();require(len(raw)<=1024*1024,'worker output cap')
        value=json.loads(raw)
        if value.get('kind')=='raw':return value['value'].encode()
        if type(value.get('value')) is dict and 'raw_text' in value['value']:
            value['value']['raw']=value['value'].pop('raw_text').encode()
        return value['value']
    def cancel(self):
        if alive(self.record):os.killpg(self.child.pid,signal.SIGTERM)
        try:self.child.wait(timeout=.3)
        except subprocess.TimeoutExpired:
            if alive(self.record):os.killpg(self.child.pid,signal.SIGKILL)
            self.child.wait(timeout=2)
    def close(self):
        self.cancel();self.error_file.close()
class Immediate:
    def __init__(self,value):self.value=value
    def poll(self):return self.value
    def cancel(self):pass
def terminate_direct(child):
    # Popen still owns this unreaped direct child; no arbitrary PID lookup.
    if child.poll() is None:child.terminate()
    try:child.wait(timeout=.3)
    except subprocess.TimeoutExpired:child.kill();child.wait(timeout=2)
class Lifecycle:
    def __init__(self,root,fixture_sha,mode='fixed'):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        fixture=HERE/'c3r_fixture.py'
        require(sha(fixture.read_bytes())==fixture_sha,'fixture executable allowlist')
        self.fixture=fixture;self.mode=mode;self.proc=None;self.owner=None;self.record=None;self.watchdog=None;self.endpoint=None
        self.loads=0;self.sample_data={'pressure_level':1,'free_percent':75,'swap_used_mib':0,'owned_rss_bytes':0,'foreign_inference':[],'disk_free_bytes':20*1024**3}
    @staticmethod
    def attest_assets(model,server,template,revision,timeout=300):
        deadline=time.monotonic()+min(timeout,300)
        require(revision==CONTRACT['runner_revision'],'runner source revision')
        for path,key in ((model,'model_sha256'),(server,'server_sha256'),(template,'template_sha256')):
            h=hashlib.sha256()
            with Path(path).open('rb') as f:
                for block in iter(lambda:f.read(1024*1024),b''):
                    require(time.monotonic()<deadline,'attestation deadline');h.update(block)
            require(h.hexdigest()==CONTRACT[key],'source/asset hash mismatch')
        return dict(CONTRACT)
    @staticmethod
    def frozen_argv(alias,port):
        from mechanics_a6r import build_command
        return build_command(alias,port,'A6R')
    def production_start(self,*args,**kwargs):raise PermissionError('real model startup locked; future exact release required')
    def begin_setup(self,timeout):
        require(timeout>0,'setup deadline')
        return Immediate(dict(CONTRACT)) # explicit fixture-only attestation
    def begin_load(self,contract,timeout):
        require(contract==CONTRACT and self.proc is None,'no config change/reload')
        self.loads+=1;ready=self.root/'ready.json';token='c3r-owned-'+str(os.getpid())+'-'+str(time.time_ns())
        argv=[sys.executable,str(self.fixture),'server',str(ready),self.mode,token]
        self.proc=subprocess.Popen(argv,start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        try:
            self.record={'pid':self.proc.pid,'identity':identity(self.proc.pid,min(1,timeout)),'ownership_token':token,'parent':os.getpid(),'parent_identity':identity(os.getpid(),min(1,timeout)),'deadline':time.time()+min(59,timeout),'fixture_only':True,'sample_path':str(self.root/'sample.json')}
        except BaseException:terminate_direct(self.proc);raise
        self.owner=self.root/'owner.json';b3_stop.save(self.owner,self.record);b3_stop.save(self.root/'sample.json',self.sample_data)
        self.watchdog=subprocess.Popen([sys.executable,str(HERE/'c3r_watchdog.py'),str(self.owner)],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        outer=self
        class Load:
            def __init__(self):self.deadline=time.monotonic()+min(timeout,59)
            def poll(self):
                if not outer.owned_alive():raise RuntimeError('fixture server died')
                if time.monotonic()>self.deadline:raise TimeoutError('fixture load')
                if not ready.exists():return PENDING
                outer.endpoint=json.loads(ready.read_text());require(outer.endpoint['host']=='127.0.0.1','fixture host')
                return outer.endpoint
            def cancel(self):outer.stop('load cancellation')
        return Load()
    def has_owner(self):return self.record is not None
    def owned_alive(self):return self.record is not None and alive(self.record)
    def parent_alive(self):return True
    def sample(self):return dict(self.sample_data,time=time.time())
    def stop(self,reason):
        if self.record is None:
            require(self.proc is None or self.proc.poll() is not None,'provisional identity unknown; cleanup unconfirmed')
            return {'owned_absent':True}
        result=safe_stop(self.owner,self.record,reason)
        self.proc.wait(timeout=3)
        if self.watchdog:
            try:self.watchdog.wait(timeout=3)
            except subprocess.TimeoutExpired:raise RuntimeError('external watchdog exit unconfirmed')
        return result
class WorkerHooks:
    def __init__(self,root):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.counter=0;self.handles=[]
    def worker(self,operation,payload,timeout):
        self.counter+=1;spec=self.root/(str(self.counter)+'.input.json');out=self.root/(str(self.counter)+'.output.json')
        spec.write_bytes(encode(dict(payload,operation=operation,deadline=time.time()+timeout)))
        h=ProcessHandle([sys.executable,str(HERE/'c3r_worker.py'),str(spec),str(out)],timeout,out);self.handles.append(h);return h
    def close(self):
        for h in self.handles:h.close()
class HTTP(WorkerHooks):
    def __init__(self,root,lifecycle):super().__init__(root);self.life=lifecycle
    def begin_bind(self,messages,timeout):return self.worker('bind',{'endpoint':self.life.endpoint,'messages':messages},timeout)
    def begin_generate(self,body,timeout):return self.worker('generate',{'endpoint':self.life.endpoint,'body':body},timeout)
class Git(WorkerHooks):
    def __init__(self,root,repo,allowlist,expected_main):
        super().__init__(root);self.repo=str(Path(repo).resolve());self.allowed={(e['commit'],e['path']) for e in allowlist};self.expected_main=expected_main
    def begin_read(self,commit,path,timeout):
        require((commit,path) in self.allowed,'not authorized Git object')
        return self.worker('git_read',{'repo':self.repo,'commit':commit,'path':path},timeout)
    def begin_publish(self,sequence,raw,timeout):
        return self.worker('git_publish',{'repo':self.repo,'expected_main':self.expected_main,'path':'results/remote_req028/c3_fixture/response'+str(sequence)+'.json','raw':raw.decode()},timeout)
