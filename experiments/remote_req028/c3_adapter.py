"""C3 setup-only adapter: injected cancellable operations, no real serving entry point."""
import json,threading,time
from c2_relay import FileStore,encode,decode,sha,identifier,digest,commit_id,path_component,number,require,Rejected,Indeterminate
from a6r_gate import admit
import guard
CONTRACT={'model_sha256':'3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597','runner_revision':'4fea119de30f6a923992780f6fd5ccb0bee5d47d','server_sha256':'fd4de7db51a60ad4710725b5e2d2da9060a0b56bf7759767ba81ac719abc4222','template_sha256':'c979e0e71a3e21b8f208e6ab120d5cb29327885f29d2a8b18fda67a723798e18','cache_k':'q8_0','cache_v':'q8_0','context':32768,'batch':128,'ubatch':32,'threads':2,'temperature':0,'seed':20260927028,'max_tokens':1536,'warmup':False,'cache_prompt':False,'context_shift':False,'host':'127.0.0.1'}
CONTRACT.update({'parallel':1,'cache_ram':0,'cache_idle_slots':False,'threads_batch':2,'threads_http':2,'gpu_layers':99,'flash_attention':'on','jinja':True})
CONFIG_SHA=sha(encode(CONTRACT))
REQUEST_KEYS={'protocol','run_id','sequence','request_id','config_sha256','messages','messages_sha256','parent_response_sha256','expires_at'}
RELEASE_KEYS={'protocol','run_id','config_sha256','max_calls','deadline','requests','parent_release_sha256'}
ENTRY_KEYS={'sequence','commit','path','sha256'}
PENDING=object()
def messages_sha(messages):return sha(encode(messages))
def validate_release(raw,pin,now):
    require(sha(raw)==digest(pin),'unapproved release bytes')
    r=decode(raw,RELEASE_KEYS)
    require(type(r['protocol']) is int and r['protocol']==3,'not C3 protocol')
    identifier(r['run_id']);require(r['config_sha256']==CONFIG_SHA,'wrong first model contract')
    require(type(r['max_calls']) is int and 1<=r['max_calls']<=24,'call cap')
    number(r['deadline']);require(now<r['deadline'],'release expired')
    require(type(r['requests']) is list and 1<=len(r['requests'])<=r['max_calls'],'allowlist size')
    for i,e in enumerate(r['requests'],1):
        require(type(e) is dict and set(e)==ENTRY_KEYS,'allowlist fields')
        require(type(e['sequence']) is int and e['sequence']==i,'allowlist sequence')
        commit_id(e['commit']);digest(e['sha256']);path_component(e['path'])
        require(e['path'].startswith('results/remote_req028/c3_'),'unowned request path')
    if r['parent_release_sha256'] is not None:digest(r['parent_release_sha256'])
    return r
def validate_request(raw,release,entry,now):
    require(sha(raw)==entry['sha256'],'request object hash changed')
    q=decode(raw,REQUEST_KEYS)
    require(type(q['protocol']) is int and q['protocol']==3,'wrong request protocol')
    require(q['run_id']==release['run_id'],'wrong run')
    require(type(q['sequence']) is int and q['sequence']==entry['sequence'],'wrong sequence')
    require(q['request_id']==q['run_id']+'-'+str(q['sequence']),'wrong request ID')
    require(q['config_sha256']==CONFIG_SHA==release['config_sha256'],'wrong candidate config')
    number(q['expires_at']);require(now<q['expires_at']<=release['deadline'],'request expiry')
    messages=q['messages'];require(type(messages) is list and 1<=len(messages)<=256,'invalid message list')
    for m in messages:
        require(type(m) is dict and set(m)=={'role','content'},'message fields')
        require(type(m['role']) is str and m['role'] in ('system','user','assistant','tool'),'message role')
        require(type(m['content']) is str,'message content')
    require(messages_sha(messages)==q['messages_sha256'],'message hash')
    if q['sequence']==1:require(q['parent_response_sha256'] is None,'initial parent')
    else:digest(q['parent_response_sha256'])
    return q
class Adapter:
    """Dependencies: clock.now/sleep; lifecycle & HTTP & Git begin_* return handles.

    Handles poll nonblocking and cancel boundedly. Lifecycle sample/identity/stop
    must be bounded; stop uses the B3 identity-checked arbiter in executed fixtures.
    c3r_hooks provides bounded fixture-only subprocess/HTTP/local-Git hooks.
    Real-model startup remains locked and unauthorized.
    """
    def __init__(self,release_raw,release_pin,contract,clock,journal,lifecycle,http,transport,watch_interval=1):
        require(contract==CONTRACT and sha(encode(contract))==CONFIG_SHA,'unapproved candidate')
        self.release=validate_release(release_raw,release_pin,clock.now())
        require(len(self.release['requests'])==1 and self.release['parent_release_sha256'] is None,'initial release must allow only first existing request')
        self.release_pin=release_pin;self.release_raw=release_raw;self.clock=clock;self.store=journal;self.life=lifecycle;self.http=http;self.git=transport
        self.run=self.release['run_id'];self.lock=threading.RLock();self.op_lock=threading.Lock()
        self.active=None;self.failed=None;self.resident=False;self.closed=False;self.next_sequence=1;self.model_deadline=None
        self.abort=threading.Event();self.watch_end=threading.Event();self.watcher=None;self.watch_interval=watch_interval
        self.initiated=clock.now();self.queue_started=self.initiated;self.events=0;self.physical=0;self.baseline=0
        self.history=[]
        self.audit_errors=[];self.cleanup_errors=[];self.cleanup_results=[];self.cancel_errors=[];self.primary_exception=None
        if self.store.read(self.run+'/lifecycle.claim') is not None:self.failed='existing lifecycle claim: no reload/resume'
    def put(self,name,data):
        raw=data if type(data) is bytes else encode(data)
        if not self.store.write_exclusive(self.run+'/'+name,raw):require(self.store.read(self.run+'/'+name)==raw,'immutable conflict')
    def event(self,kind,**data):
        with self.lock:
            self.events+=1
            ok=self.best_put('events/'+str(self.events).zfill(6)+'.json',dict(kind=kind,time=self.clock.now(),**data))
        if not ok:self.fail('audit event write failed')
    def best_put(self,name,data):
        try:self.put(name,data);return True
        except BaseException as e:
            self.audit_errors.append({'path':name,'error':repr(e),'durable':False});return False
    def bound(self,seconds=None,expiry=None):
        end=self.release['deadline']
        if self.model_deadline is not None:end=min(end,self.model_deadline)
        if seconds is not None:end=min(end,self.clock.now()+seconds)
        if expiry is not None:end=min(end,expiry)
        return end
    def fail(self,reason):
        try:
            with self.op_lock:
                with self.lock:
                    if not self.failed:self.failed=reason
                    self.abort.set()
                    self.best_put('failure.json',{'reason':self.failed,'physical_attempts':self.physical})
                if self.active is not None:
                    try:self.active.cancel()
                    except BaseException as e:
                        self.cancel_errors.append(repr(e))
                        self.events+=1
                        self.best_put('events/'+str(self.events).zfill(6)+'.json',{'kind':'cancellation_error','error':repr(e)})
        finally:self.cleanup(reason)
    def cleanup(self,reason):
        with self.lock:
            if self.resident or self.life.has_owner():
                try:
                    outcome=self.life.stop(reason)
                    require(outcome['owned_absent'],'cleanup unconfirmed')
                    self.resident=False;self.cleanup_results.append(outcome)
                    if not self.best_put('cleanup_'+str(len(self.cleanup_results))+'.json',outcome):
                        self.failed=self.failed or 'cleanup audit failed';self.abort.set()
                    return True
                except BaseException as e:
                    self.cleanup_errors.append(repr(e));self.failed=self.failed or 'cleanup failed';self.abort.set()
                    self.best_put('cleanup_error_'+str(len(self.cleanup_errors))+'.json',{'error':repr(e)})
                    return False
            return True
    def check(self):
        if self.failed:raise Rejected(self.failed)
        require(not self.closed,'adapter closed')
        require(self.clock.now()<self.bound(),'absolute/model deadline')
    def operation(self,label,start,deadline):
        self.check();require(self.clock.now()<deadline,label+' expired')
        began=self.clock.now();handle=None
        try:
            with self.op_lock:
                self.check()
                handle=start(deadline-self.clock.now())
                self.active=handle
            while True:
                self.check()
                require(self.clock.now()<deadline,label+' in-flight deadline')
                value=handle.poll()
                if value is not PENDING:break
                self.clock.sleep(min(.01,deadline-self.clock.now()))
        except BaseException:
            if handle is not None:
                try:handle.cancel()
                except BaseException as e:
                    self.cancel_errors.append(repr(e))
                    self.best_put('operation_cancel_error_'+str(len(self.cancel_errors))+'.json',{'error':repr(e),'phase':label})
            raise
        finally:
            with self.op_lock:self.active=None
            self.event('phase',phase=label,started=began,finished=self.clock.now())
        self.check();return value
    def watch(self):
        while not self.watch_end.wait(self.watch_interval):
            try:
                if not self.life.parent_alive():reason='owner_parent_exited'
                elif not self.life.owned_alive():reason='ownership_lost'
                elif self.clock.now()>=self.bound():reason='deadline'
                else:reason=guard.violation(self.life.sample(),self.baseline,float('inf'),True)
                if reason:self.fail(reason);return
            except BaseException as e:
                self.fail('watchdog: '+repr(e));return
    def initialize(self,q):
        require(self.store.write_exclusive(self.run+'/lifecycle.claim',encode({'config_sha256':CONFIG_SHA,'started':self.clock.now(),'no_reload':True})),'lifecycle already claimed')
        setup=self.operation('setup',self.life.begin_setup,self.bound(300,q['expires_at']))
        require(setup==CONTRACT,'asset/source attestation mismatch')
        admission_deadline=self.bound(900,q['expires_at'])
        def launch(sample):
            self.baseline=sample['swap_used_mib']
            self.model_deadline=min(self.release['deadline'],self.clock.now()+1800)
            self.put('model_window.json',{'started':self.clock.now(),'deadline':self.model_deadline,'never_renew':True})
            # begin_load must establish provisional identity before returning its handle.
            def begin(timeout):
                try:return self.life.begin_load(CONTRACT,timeout)
                finally:
                    if self.life.has_owner():
                        self.resident=True;self.start_watch()
            result=self.operation('load',begin,self.bound(180,q['expires_at']))
            require(result['host']=='127.0.0.1' and self.life.owned_alive(),'nonowned/nonlocal endpoint')
            return result
        self.put('admission_window.json',{'started':self.clock.now(),'deadline':admission_deadline,'max_reads':31})
        admit(self.life.sample,self.clock.now,self.clock.sleep,lambda sample,reason,count,kind:self.event('admission',sample=sample,reason=reason,count=count,observation_kind=kind),launch,admission_deadline)
    def start_watch(self):
        if self.watcher is None:
            self.watcher=threading.Thread(target=self.watch,daemon=True);self.watcher.start()
    def process(self,sequence):
        self.check()
        require(sequence==self.next_sequence and sequence<=len(self.release['requests']),'not explicitly released next request')
        e=self.release['requests'][sequence-1];q=None;claimed=False;sealed=False
        try:
            self.event('phase',phase='queue',started=self.queue_started,finished=self.clock.now())
            fetched=self.operation('network_fetch',lambda timeout:self.git.begin_read(e['commit'],e['path'],timeout),self.bound(30))
            require(fetched['commit']==e['commit'] and fetched['path']==e['path'],'Git object identity mismatch')
            raw=fetched['raw']
            q=validate_request(raw,self.release,e,self.clock.now())
            if sequence==1:self.put('release_1.json',self.release_raw)
            base=str(sequence)
            if sequence>1:require(q['parent_response_sha256']==sha(self.read_sealed(sequence-1)),'parent response mismatch')
            claim={'request_commit':e['commit'],'request_path':e['path'],'request_sha256':sha(raw),'config_sha256':CONFIG_SHA,'state':'indeterminate_until_sealed'}
            require(self.store.write_exclusive(self.run+'/'+base+'.claim.json',encode(claim)),'existing request claim; never redispatch')
            claimed=True;self.put(base+'.request.json',raw)
            if not self.resident:self.initialize(q)
            self.start_watch()
            binding=self.operation('native_binding',lambda timeout:self.http.begin_bind(q['messages'],timeout),self.bound(180,q['expires_at']))
            require(binding['template_sha256']==CONTRACT['template_sha256'] and binding['native_exact'] is True,'wrong native binding')
            ids=binding['token_ids'];require(type(ids) is list and ids and all(type(x) is int for x in ids),'token IDs')
            require(len(ids)+1536<=32768,'context headroom')
            require(type(binding['rendered']) is str,'rendered text')
            self.put(base+'.binding.json',dict(binding,messages_sha256=q['messages_sha256'],rendered_sha256=sha(binding['rendered'].encode()),token_ids_sha256=sha(encode(ids)),frozen_at=self.clock.now()))
            self.put(base+'.physical_attempt.json',{'started':self.clock.now(),'number':sequence,'no_retry':True})
            self.physical+=1
            body={'messages':q['messages'],'temperature':0,'seed':20260927028,'max_tokens':1536,'stream':False,'cache_prompt':False}
            request_started=self.clock.now()
            result=self.operation('request',lambda timeout:self.http.begin_generate(body,timeout),self.bound(180,q['expires_at']))
            require(type(result) is bytes,'raw HTTP response bytes')
            self.put(base+'.raw_response.json',result)
            parsed=json.loads(result);require(parsed['usage']['prompt_tokens']==len(ids),'usage binding mismatch')
            require(type(parsed['usage']['completion_tokens']) is int and 0<=parsed['usage']['completion_tokens']<=1536,'output usage')
            self.event('server_subtimings',prefill=parsed.get('timings',{}).get('prompt_ms'),generation=parsed.get('timings',{}).get('predicted_ms'),units='milliseconds',included_in_request_span=True)
            from c3r_envelope import build
            result=build(q,e,CONFIG_SHA,binding,result,{'request_wall_seconds':self.clock.now()-request_started,'prefill_ms':parsed.get('timings',{}).get('prompt_ms'),'generation_ms':parsed.get('timings',{}).get('predicted_ms')})
            self.put(base+'.response.json',result)
            self.put(base+'.seal',sha(result).encode());sealed=True
            self.operation('publication',lambda timeout:self.git.begin_publish(sequence,result,timeout),self.bound(30,q['expires_at']))
            self.next_sequence+=1;self.history.append(sha(result));self.queue_started=self.clock.now()
            return result
        except BaseException as ex:
            self.primary_exception=repr(ex)
            if claimed and not sealed:self.best_put(str(sequence)+'.indeterminate.json',{'error':repr(ex),'physical_attempts':self.physical})
            self.fail(repr(ex));raise
    def read_sealed(self,sequence):
        raw=self.store.read(self.run+'/'+str(sequence)+'.response.json')
        seal=self.store.read(self.run+'/'+str(sequence)+'.seal')
        if raw is None or seal is None:raise Indeterminate('no sealed generation; never regenerate')
        require(sha(raw).encode()==seal,'modified raw response');return raw
    def authorize_next(self,raw,pin):
        self.check();new=validate_release(raw,pin,self.clock.now())
        require(new['parent_release_sha256']==self.release_pin,'release chain mismatch')
        for k in ('run_id','config_sha256','max_calls','deadline'):require(new[k]==self.release[k],'release renew/change')
        require(new['requests'][:-1]==self.release['requests'] and len(new['requests'])==self.next_sequence,'one explicit next history request only')
        require(len(self.history)==self.next_sequence-1,'prior publication/history incomplete')
        self.put('release_'+str(self.next_sequence)+'.json',raw);self.release=new;self.release_pin=pin
    def idle(self,seconds):
        began=self.clock.now()
        self.event('phase',phase='queue',started=self.queue_started,finished=began)
        try:
            until=min(self.clock.now()+seconds,self.bound())
            while self.clock.now()<until:self.check();self.clock.sleep(min(.01,until-self.clock.now()))
            self.check()
        except BaseException as e:self.fail(repr(e));raise
        finally:
            self.event('phase',phase='toolwait_idle',started=began,finished=self.clock.now());self.queue_started=self.clock.now()
    def close(self):
        primary=None;cleanup_ok=False
        try:
            self.watch_end.set()
            if self.watcher:self.watcher.join(timeout=10);require(not self.watcher.is_alive(),'watchdog join timeout')
        except BaseException as e:primary=e
        finally:
            cleanup_ok=self.cleanup('close')
            if not self.closed:
                self.event('total_wall',started=self.initiated,finished=self.clock.now(),physical_attempts=self.physical,note='do not add nested server subtimings to phase spans')
                self.closed=True
        if primary:raise primary
        require(cleanup_ok,'owned cleanup failed; inspect cleanup_errors')
