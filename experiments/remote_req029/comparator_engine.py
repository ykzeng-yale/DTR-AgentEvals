"""Executable comparator roles: one fixed arm/task cell, no adaptive assignment."""
import json
import time
from pathlib import Path
from comparator_chain import Chain,completed,submitted,observation_envelope,check_observation
from comparator_contract import put,encode,sha,require,bound_messages,PROTOCOL,cell,validate

class Base:
    def __init__(self, root, release, pin, transport):
        self.root=Path(root)
        # Never resume a role, including after a crash before its first publication.
        validate(release)
        self.root.mkdir(parents=True,exist_ok=False)
        self.r,self.pin,self.t=release,pin,transport
        self.chain=Chain(release,pin)
        self.deadline=release['expires_at']
        self.claims=0
        self.dispatches=[];self.costs=[];self.first_response=False
        self.trace=[]
        self.created_at=time.time()
        self.terminal=None
        self.check=lambda:None
        self.crash=lambda stage:None
        put(self.root,'role.claim',{'release_sha256':pin,'no_resume':True})

    def left(self, cap):
        self.check()
        left=min(cap,self.deadline-time.time(),self.r['expires_at']-time.time())
        require(left>0,'phase deadline')
        return time.time()+left

    def event(self, kind, data):
        self.trace.append(dict(kind=kind,time=time.time(),data=data))
        put(self.root,'trace/%04d.json'%len(self.trace),self.trace[-1])

    def wait(self, kind, seq=None, peer=None):
        started=time.time()
        while True:
            self.left(30)
            if peer:
                terminal=self.t.read(peer+'_terminal')
                if terminal:
                    raise RuntimeError('peer terminal: '+str(terminal[0].get('status')))
            value=self.t.read(kind,seq)
            if value:
                self.event('queue',dict(kind=kind,started=started,finished=time.time(),object=value[1]))
                return value

    def publish(self, kind, value, seq=None):
        self.left(30)
        put(self.root,kind+('' if seq is None else '/%02d'%seq)+'.json',value)
        obj=self.t.publish(kind,value,seq)
        self.event('published',obj)
        return obj

    def claim(self, kind, seq, identity):
        # fsync completed BEFORE physical dispatch. No retries after any exception.
        self.left(1) # latch terminal/guard evidence immediately before the claim
        put(self.root,'claims/'+kind+'-%02d.json'%seq,identity)
        self.claims+=1
        self.crash('after_'+kind+'_claim')

    def finish(self, role, status, error, cleanup):
        self.chain.done=True
        value=dict(protocol=PROTOCOL,cell=cell(self.r),run_id=self.r['run_id'],release_sha256=self.pin,
            status=status,error=error,claims=self.claims,cleanup=cleanup,
            deadline=self.deadline,finished=time.time(),no_retry=True,
            trajectory_messages=self.chain.messages,scientific_success_assessed=False,
            dispatches=self.dispatches,costs=self.costs,first_response_received=self.first_response,
            call9_reached=any(d['sequence']==9 and d['kind']=='model' for d in self.dispatches),
            phase_started=getattr(self,'phase_started',None),role_started=self.created_at)
        self.terminal=value
        # Local terminal evidence survives expired/failed network publication.
        put(self.root,'terminal.local.json',value)
        # Cleanup has already run. Reporting gets a distinct bounded reserve;
        # an expired setup/admission/model deadline must not hide local failure.
        # This never extends self.deadline or permits another action/model claim.
        publication_started = time.time()
        publication_deadline = min(self.r['expires_at'],
                                   publication_started + self.r['caps']['cleanup_seconds'])
        put(self.root, 'terminal.publication.window.json', {
            'started': publication_started, 'deadline': publication_deadline,
            'execution_deadline': self.deadline, 'terminal_only': True})
        if publication_started < publication_deadline and not self.t.failed:
            previous_deadline = self.t.deadline
            try:
                self.t.deadline = publication_deadline
                self.t.publish(role+'_terminal',value)
            except BaseException as e:
                put(self.root,'terminal.publication.failure.json',{'error':repr(e),'indeterminate':True})
            finally:
                self.t.deadline = previous_deadline
        put(self.root,'transport.json',{'fetches':self.t.fetches,'events':self.t.events,
                                      'process_events':self.t.runner.events})
        return value

class Worker(Base):
    def run(self, model):
        status='indeterminate';error=None;cleanup=None
        try:
            preflight,pobj=self.wait('preflight',peer='controller')
            require(preflight==dict(protocol=PROTOCOL,cell=cell(self.r),run_id=self.r['run_id'],release_sha256=self.pin,
                sandbox=self.r['sandbox'],controller_commit=self.r['controller_commit'],ready=True,
                created_at=preflight['created_at'],preflight_deadline=min(self.r['expires_at'],preflight['created_at']+1200)), 'preflight binding')
            require(preflight['created_at']<=time.time()<preflight['preflight_deadline']-15,'preflight lease no longer ready')
            model.admission_outer_deadline=preflight['preflight_deadline']-15
            # Production start performs once-only setup/admission before launch.
            started=model.start(self.r,self.pin,self.root)
            self.phase_started=started
            self.deadline=min(started+1800,self.r['expires_at'])
            self.t.deadline=self.deadline
            self.check=model.check
            self.t.runner.check=model.check
            ready=dict(protocol=PROTOCOL,cell=cell(self.r),run_id=self.r['run_id'],release_sha256=self.pin,
                worker_commit=self.r['worker_commit'],phase_started=started,deadline=self.deadline,
                preflight_object=pobj)
            self.publish('ready',ready)
            for seq in range(1,25):
                q,qobj=self.wait('request',seq,'controller')
                self.chain.check_request(q,self.deadline)
                native=model.bind(q['messages'],self.left(180))
                bound_messages(native,q['messages'],self.r)
                put(self.root,'native/%02d.json'%seq,native)
                self.claim('model',seq,dict(request_object=qobj,native_sha256=sha(encode(native)),
                    request_sha256=sha(encode(q)),worker_commit=self.r['worker_commit']))
                self.left(180)
                start=time.time()
                d=dict(kind='model',sequence=seq,time=start,remaining_seconds=self.deadline-start,messages_sha256=q['messages_sha256'])
                self.event('generation_attempt',d)
                try:
                    raw=model.generate(q['messages'],self.left(180))
                finally:
                    dispatched=getattr(model,'last_dispatch',None)
                    if dispatched:
                        d.update(time=dispatched['sent_at'],remaining_seconds=self.deadline-dispatched['sent_at'],
                                 http_started=dispatched['started'],request_sent=True)
                        self.dispatches.append(d);self.event('physical_generation_dispatch',d)
                self.first_response=True
                try:
                    cost=json.loads(raw);self.costs.append(dict(sequence=seq,usage=cost.get('usage'),timings=cost.get('timings'),seconds=time.time()-start))
                except (ValueError,TypeError):pass
                # Raw physical evidence is preserved even when format/length fails.
                put(self.root,'raw/%02d.json'%seq,raw.encode())
                response=self.chain.response(q,qobj,native,raw,self.deadline,time.time()-start)
                content,_=self.chain.accept(response,q,qobj,self.deadline)
                robj=self.publish('response',response,seq)
                # A submission is signaled by controller terminal, not guessed from text.
                obs,oobj=self.wait('observation',seq,'controller')
                message=check_observation(obs,self.r,self.pin,seq,robj,response,oobj)
                self.chain.advance(response,content,message)
            status='call_cap'
        except BaseException as e:
            error=repr(e)
            status='terminal_or_failure'
        finally:
            # Stop independent model residency before attempting any terminal network IO.
            try:
                cleanup=model.stop()
            except BaseException as e:
                cleanup={'owned_absent':False,'error':repr(e)}
            self.check=lambda:None
            self.t.runner.check=lambda:None
        return self.finish('worker',status,error,cleanup)

class Controller(Base):
    def run(self, sandbox):
        status='indeterminate';error=None;cleanup=None;diff=None
        try:
            sandbox.preflight(self.r,self.left(60))
            created_at=getattr(sandbox,'created_at',self.created_at)
            self.check=getattr(sandbox,'liveness',lambda:None)
            pobj=self.publish('preflight',dict(protocol=PROTOCOL,cell=cell(self.r),run_id=self.r['run_id'],release_sha256=self.pin,
                sandbox=self.r['sandbox'],controller_commit=self.r['controller_commit'],ready=True,
                created_at=created_at,preflight_deadline=min(self.r['expires_at'],created_at+1200)))
            ready,readyobj=self.wait('ready',peer='worker')
            require(ready==dict(protocol=PROTOCOL,cell=cell(self.r),run_id=self.r['run_id'],release_sha256=self.pin,
                worker_commit=self.r['worker_commit'],phase_started=ready['phase_started'],
                deadline=min(ready['phase_started']+1800,self.r['expires_at']),preflight_object=pobj),'ready binding')
            require(ready['phase_started']<=time.time()<ready['deadline'],'phase time')
            self.phase_started=ready['phase_started']
            self.deadline=ready['deadline'];self.t.deadline=self.deadline
            sandbox.bind_phase(ready,readyobj,self.left(30))
            for seq in range(1,25):
                require(self.t.read('worker_terminal') is None,'worker already terminal')
                sandbox.check(self.left(5))
                q=self.chain.request(self.deadline)
                qobj=self.publish('request',q,seq)
                response,robj=self.wait('response',seq,'worker')
                content,command=self.chain.accept(response,q,qobj,self.deadline)
                self.claim('action',seq,dict(response_object=robj,response_sha256=sha(encode(response)),
                    command_sha256=sha(command.encode()),controller_commit=self.r['controller_commit']))
                d=dict(kind='action',sequence=seq,time=time.time(),remaining_seconds=self.deadline-time.time())
                self.dispatches.append(d);self.event('sandbox_action_dispatch',d)
                output=sandbox.execute(command,self.left(60))
                put(self.root,'output/%02d.json'%seq,output)
                self.left(60)
                completed(output)
                self.left(5)
                if submitted(output):
                    status='submitted';break
                obs=observation_envelope(self.r,self.pin,seq,robj,response,output)
                self.publish('observation',obs,seq)
                self.chain.advance(response,content,obs['observation'])
            else:
                status='action_cap'
        except BaseException as e:
            error=repr(e);status='terminal_or_failure'
        finally:
            # Never salvage a submission. A failed diagnostic capture is explicit.
            capture_error=None
            try:
                diff=sandbox.diff(self.left(30))
            except BaseException as e:
                capture_error=repr(e)
            try:
                cleanup=sandbox.close()
            except BaseException as e:
                cleanup={'owned_absent':False,'error':repr(e)}
            self.check=lambda:None
            # Audit I/O cannot prevent exact-owned sandbox cleanup.
            if diff is not None:put(self.root,'final.diff',diff.encode())
            else:put(self.root,'diff.unavailable.json',{'error':capture_error,'non_primary':True})
            put(self.root,'diff.classification.json',{'submitted':status=='submitted',
                'primary_eligible':False,'evaluation_held':True,'captured':diff is not None})
        return self.finish('controller',status,error,cleanup)
