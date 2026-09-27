"""Executed fake dependencies only. Inert owned sleeper is NOT llama-server."""
import json,os,subprocess,sys,threading,time,uuid
from pathlib import Path
import b3_stop,guard
from c3_adapter import CONTRACT,PENDING,encode
class Clock:
    def __init__(self):self.value=time.time();self.lock=threading.Lock()
    def now(self):
        with self.lock:return self.value
    def sleep(self,seconds):
        with self.lock:self.value+=seconds
        time.sleep(.0002)
    def advance(self,seconds):
        with self.lock:self.value+=seconds
class Handle:
    def __init__(self,value=None,error=None):self.value=value;self.error=error;self.cancelled=False
    def poll(self):
        if self.error:raise self.error
        return self.value
    def cancel(self):self.cancelled=True
class BlockingHandle:
    """Actually blocked fake HTTP worker, canceled independently while poll is pending."""
    def __init__(self):
        self.event=threading.Event();self.finished=threading.Event();self.cancelled=False
        self.thread=threading.Thread(target=self.work,daemon=True);self.thread.start()
    def work(self):self.event.wait(10);self.finished.set()
    def poll(self):return PENDING
    def cancel(self):
        self.cancelled=True;self.event.set();self.thread.join(timeout=1)
        assert self.finished.is_set() and not self.thread.is_alive()
class Lifecycle:
    def __init__(self,path,clock):
        self.path=Path(path);self.clock=clock;self.child=None;self.owner=None;self.loads=0;self.setup_count=0;self.parent=True;self.pressure=1;self.peer=False;self.free=75;self.extra={};self.setup_error=None;self.load_block=False;self.handles=[]
    def begin_setup(self,timeout):
        self.setup_count+=1;return Handle(dict(CONTRACT),self.setup_error)
    def sample(self):
        return dict({'time':self.clock.now(),'pressure_level':self.pressure,'free_percent':self.free,'swap_used_mib':0,'owned_rss_bytes':0,'foreign_inference':[{'fixture':True}] if self.peer else [],'disk_free_bytes':20*1024**3},**self.extra)
    def begin_load(self,contract,timeout):
        assert contract==CONTRACT and timeout<=180 and self.child is None
        self.loads+=1;token='c3-inert-'+uuid.uuid4().hex
        self.child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)',token],start_new_session=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.owner=self.path/'inert.ownership.json';self.path.mkdir(exist_ok=True,parents=True)
        b3_stop.save(self.owner,{'pid':self.child.pid,'identity':guard.ps(self.child.pid),'ownership_token':token})
        h=BlockingHandle() if self.load_block else Handle({'host':'127.0.0.1'})
        self.handles.append(h);return h
    def has_owner(self):return self.owner is not None
    def owned_alive(self):return self.child is not None and self.child.poll() is None and guard.same(json.loads(self.owner.read_text()))
    def parent_alive(self):return self.parent
    def stop(self,reason):
        if self.owner is None:return {'owned_absent':True}
        result=b3_stop.stop(self.owner,'c3-fixture',reason)
        self.child.wait(timeout=3)
        assert not self.owned_alive()
        return {'owned_absent':result['owned_absent'],'signals':result.get('signals',[]),'returncode':self.child.returncode}
class HTTP:
    def __init__(self):
        self.calls=0;self.tokens=[1,2,3];self.template=CONTRACT['template_sha256'];self.native=True;self.wrong_usage=False;self.crash=False;self.block=False;self.handle=None;self.bodies=[]
    def begin_bind(self,messages,timeout):
        assert timeout<=180
        return Handle({'template_sha256':self.template,'native_exact':self.native,'rendered':'native fixture','token_ids':self.tokens})
    def begin_generate(self,body,timeout):
        self.calls+=1;self.bodies.append(body);assert timeout<=180
        if self.crash:raise RuntimeError('fake process crash after dispatch entry')
        if self.block:self.handle=BlockingHandle();return self.handle
        return Handle(encode({'choices':[{'message':{'content':'fixture text only'},'finish_reason':'stop'}],'usage':{'prompt_tokens':99 if self.wrong_usage else len(self.tokens),'completion_tokens':3},'timings':{'prompt_ms':0,'predicted_ms':0}}))
class Git:
    def __init__(self,entry,raw):
        self.objects={(entry['commit'],entry['path']):raw};self.reads=[];self.publications=0;self.failure=None;self.publish_failure=False;self.identity_wrong=False;self.block=False;self.handle=None;self.latest='f'*40
    def begin_read(self,commit,path,timeout):
        self.reads.append((commit,path,timeout));assert timeout<=30
        if self.block:self.handle=BlockingHandle();return self.handle
        if self.failure:return Handle(error=RuntimeError(self.failure))
        return Handle({'commit':self.latest if self.identity_wrong else commit,'path':path,'raw':self.objects[(commit,path)]})
    def begin_publish(self,sequence,raw,timeout):
        self.publications+=1;assert timeout<=30
        return Handle(error=RuntimeError('publication conflict') if self.publish_failure else None,value='fixture-commit')
