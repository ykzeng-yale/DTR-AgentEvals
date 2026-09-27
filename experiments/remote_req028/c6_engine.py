"""Two finite autonomous roles; interfaces injected for inert/local-Git tests."""
import json
import time
from pathlib import Path
from c6_protocol import (Chain,put,encode,sha,require,bound_messages,observation_envelope,
                         check_observation)

class Base:
    def __init__(self, root, release, pin, transport):
        self.root=Path(root)
        # Never resume a role, including after a crash before its first publication.
        self.root.mkdir(parents=True,exist_ok=False)
        self.r,self.pin,self.t=release,pin,transport
        self.chain=Chain(release,pin)
        self.deadline=release['expires_at']
        self.claims=0
        self.trace=[]
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
        put(self.root,'claims/'+kind+'-%02d.json'%seq,identity)
        self.claims+=1
        self.crash('after_'+kind+'_claim')

    def finish(self, role, status, error, cleanup):
        self.chain.done=True
        value=dict(protocol=6,run_id=self.r['run_id'],release_sha256=self.pin,
            status=status,error=error,claims=self.claims,cleanup=cleanup,
            deadline=self.deadline,finished=time.time(),no_retry=True,
            trajectory_messages=self.chain.messages,scientific_success_assessed=False)
        self.terminal=value
        # Local terminal evidence survives expired/failed network publication.
        put(self.root,'terminal.local.json',value)
        if time.time()<self.deadline and not self.t.failed:
            try:
                self.t.publish(role+'_terminal',value)
            except BaseException as e:
                put(self.root,'terminal.publication.failure.json',{'error':repr(e),'indeterminate':True})
        put(self.root,'transport.json',{'fetches':self.t.fetches,'events':self.t.events,
                                      'process_events':self.t.runner.events})
        return value

class Worker(Base):
    def run(self, model):
        status='indeterminate';error=None;cleanup=None
        try:
            preflight,pobj=self.wait('preflight',peer='controller')
            require(preflight==dict(protocol=6,run_id=self.r['run_id'],release_sha256=self.pin,
                sandbox=self.r['sandbox'],controller_commit=self.r['controller_commit'],ready=True), 'preflight binding')
            # Production start performs once-only setup/admission before launch.
            started=model.start(self.r,self.pin,self.root)
            self.deadline=min(started+1800,self.r['expires_at'])
            self.t.deadline=self.deadline
            self.check=model.check
            self.t.runner.check=model.check
            ready=dict(protocol=6,run_id=self.r['run_id'],release_sha256=self.pin,
                worker_commit=self.r['worker_commit'],phase_started=started,deadline=self.deadline,
                preflight_object=pobj)
            self.publish('ready',ready)
            for seq in range(1,25):
                q,qobj=self.wait('request',seq,'controller')
                self.chain.check_request(q,self.deadline)
                native=model.bind(q['messages'],self.left(180))
                bound_messages(native,q['messages'])
                put(self.root,'native/%02d.json'%seq,native)
                self.claim('model',seq,dict(request_object=qobj,native_sha256=sha(encode(native)),
                    request_sha256=sha(encode(q)),worker_commit=self.r['worker_commit']))
                self.left(180)
                start=time.time()
                raw=model.generate(q['messages'],self.left(180))
                # Raw physical evidence is preserved even when format/length fails.
                put(self.root,'raw/%02d.json'%seq,raw.encode())
                response=self.chain.response(q,qobj,native,raw,self.deadline,time.time()-start)
                content,_=self.chain.accept(response,q,qobj,self.deadline)
                robj=self.publish('response',response,seq)
                # A submission is signaled by controller terminal, not guessed from text.
                obs,oobj=self.wait('observation',seq,'controller')
                message=check_observation(obs,self.r,self.pin,seq,robj,response)
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
            pobj=self.publish('preflight',dict(protocol=6,run_id=self.r['run_id'],release_sha256=self.pin,
                sandbox=self.r['sandbox'],controller_commit=self.r['controller_commit'],ready=True))
            ready,readyobj=self.wait('ready',peer='worker')
            require(ready==dict(protocol=6,run_id=self.r['run_id'],release_sha256=self.pin,
                worker_commit=self.r['worker_commit'],phase_started=ready['phase_started'],
                deadline=min(ready['phase_started']+1800,self.r['expires_at']),preflight_object=pobj),'ready binding')
            require(ready['phase_started']<=time.time()<ready['deadline'],'phase time')
            self.deadline=ready['deadline'];self.t.deadline=self.deadline
            for seq in range(1,25):
                require(self.t.read('worker_terminal') is None,'worker already terminal')
                q=self.chain.request(self.deadline)
                qobj=self.publish('request',q,seq)
                response,robj=self.wait('response',seq,'worker')
                content,command=self.chain.accept(response,q,qobj,self.deadline)
                self.claim('action',seq,dict(response_object=robj,response_sha256=sha(encode(response)),
                    command_sha256=sha(command.encode()),controller_commit=self.r['controller_commit']))
                output=sandbox.execute(command,self.left(60))
                put(self.root,'output/%02d.json'%seq,output)
                self.left(60)
                require(output['returncode']==0 and not output['exception_info'],'command failure')
                if sandbox.submitted(output,self.left(5)):
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
            # Audit I/O cannot prevent exact-owned sandbox cleanup.
            if diff is not None:put(self.root,'final.diff',diff.encode())
            else:put(self.root,'diff.unavailable.json',{'error':capture_error,'non_primary':True})
            put(self.root,'diff.classification.json',{'submitted':status=='submitted',
                'primary_eligible':False,'evaluation_held':True,'captured':diff is not None})
        return self.finish('controller',status,error,cleanup)
