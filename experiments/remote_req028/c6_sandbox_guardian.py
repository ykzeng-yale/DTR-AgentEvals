"""Independent finite sandbox owner. File IPC; no listener, daemon renewal, or retry."""
import json,math,os,re,sys,time
from pathlib import Path
from c3r_arbiter import identity
from c6_protocol import put,encode,sha,require,commit
from c6_sandbox_backend import Docker,RESERVE
from c6_ipc import publish

class Guardian:
    def __init__(self,spec,backend):
        self.s=spec;self.b=backend;self.root=Path(spec['root'])
        self.deadline=spec['preflight_deadline'];self.phase=None;self.cid=None
        self.name=spec['name'];self.label=spec['label'];self.ready=False
        self.create_attempted=False;self.create_ambiguous=False;self.events=[]
        self.current_deadline=self.deadline-RESERVE
        self.stop=False;self.failure=None;self.diff=None;self.diff_error=None
        self.b.runner.check=self.check

    def owner_alive(self):
        try:return identity(self.s['driver_pid'])==self.s['driver_identity']
        except BaseException:return False

    def check(self):
        require(self.owner_alive(),'actual controller identity/liveness lost')
        require(time.time()<min(self.current_deadline,self.deadline-RESERVE),'sandbox action/preflight lease expired')

    def save(self,name,value):return publish(self.root,name,value)

    def exact(self):
        cfg=self.b.inspect(self.cid or self.name,self.current_deadline)
        cid=self.b.owned(cfg,self.name,self.label,self.cid)
        self.b.limits(cfg);return cid

    def preflight(self):
        require(not self.create_attempted and self.phase is None,'no sandbox restart')
        self.b.verify(self.current_deadline)
        require(self.b.inspect(self.name,self.current_deadline) is None,'name already exists')
        # Intent identity is durable BEFORE create. It remains enough to discover
        # an exact owned CID if the client dies before returning its ID.
        self.save('creation.intent.json',{'name':self.name,'label':self.label,'image':self.s['release']['sandbox']['image']})
        self.create_attempted=True;self.create_ambiguous=True
        self.b.runner.check=lambda:require(time.time()<self.current_deadline,'create deadline')
        try:
            # Do not cancel a create just because the controller died. This
            # independent owner finishes/reconciles it, then removes it in finally.
            self.cid=self.b.create(self.name,self.label,self.current_deadline,
                max(1,math.ceil(min(self.s['release']['expires_at'],self.s['created_at']+3000)-time.time())))
            self.create_ambiguous=False
        finally:self.b.runner.check=self.check
        self.save('owned.json',{'cid':self.cid,'name':self.name,'label':self.label})
        self.check();self.exact()
        self.b.call(['start',self.cid],self.current_deadline)
        self.check();self.exact()
        self.b.populate(self.cid,self.current_deadline)
        self.check();self.exact()
        result=self.b.helper(self.cid,'preflight',{},self.current_deadline)
        require(result['returncode']==0,'container preflight helper failed')
        probe=json.loads(result['output'])
        require(probe['writable'] is True and probe['limits_verified'] is True,'container probe')
        self.save('preflight.probe.json',probe);self.ready=True
        return {'qualified':True,'watchdog_armed':True,'writable':True,'storage_enforced':True,
                'source_import_qualified':True,'contract':self.s['release']['sandbox']}

    def bind(self,payload):
        require(self.ready,'preflight first')
        if self.phase is not None:
            require(payload==self.phase,'phase renewal/conflict')
            return {'phase_bound':True,'deadline':self.deadline}
        ready=payload['ready'];obj=payload['object'];r=self.s['release']
        commit(obj['commit']);commit(obj['blob'])
        require(obj['path']==r['root']+'/ready.json' and obj['sha256']==sha(encode(ready)),'worker-ready object binding')
        require(ready['protocol']==6 and ready['run_id']==r['run_id'] and ready['release_sha256']==self.s['release_sha256'] and
                ready['worker_commit']==r['worker_commit'],'ready source binding')
        require(self.s['created_at']<=ready['phase_started']<=time.time(),'phase start')
        require(ready['deadline']==min(ready['phase_started']+1800,r['expires_at']),'immutable phase deadline')
        require(time.time()<ready['deadline']-RESERVE,'phase reserve')
        self.save('phase.binding.json',payload)
        self.phase=payload;self.deadline=ready['deadline']
        return {'phase_bound':True,'deadline':self.deadline}

    def operation(self,q):
        require(q['run_id']==self.s['release']['run_id'] and q['driver_identity']==self.s['driver_identity'] and
            q['driver_pid']==self.s['driver_pid'] and q['release_sha256']==self.s['release_sha256'],'caller identity/release')
        self.current_deadline=min(q['deadline'],self.deadline-RESERVE)
        self.check();op=q['operation'];payload=q['payload']
        if op=='preflight':return self.preflight()
        if op=='bind_phase':return self.bind(payload)
        if op=='close':self.stop=True;return {'closing':True}
        require(self.phase is not None,'no command or diff before phase adoption')
        self.exact()
        if op=='check':return {'active':True}
        if op=='execute':
            require(set(payload)=={'command'} and type(payload['command']) is str and len(payload['command'].encode())<=65536,'command data')
            self.current_deadline=min(self.current_deadline,time.time()+60)
            result=self.b.helper(self.cid,'execute',payload,self.current_deadline)
            output={'output':result['output'],'returncode':result['returncode'],'exception_info':None}
            self.save('command-%04d.output.json'%q['sequence'],output)
            require(result['returncode']==0,'command failure terminates sandbox')
            return output
        if op=='diff':
            result=self.b.helper(self.cid,'diff',{},self.current_deadline)
            require(result['returncode']==0,'diff helper failed')
            self.diff=result['output'];return {'diff':self.diff}
        raise ValueError('unknown operation')

    def cleanup(self):
        # A fixed reserve, never a generation/action budget extension. Cleanup
        # ignores controller death and uses no journal-dependent launch path.
        end=min(self.deadline,time.time()+RESERVE);self.b.runner.check=lambda:None
        outcome={'owned_absent':not self.create_attempted,'create_ambiguous':self.create_ambiguous}
        try:
            self.b.cleaning=True
            cfg=self.b.inspect(self.cid or self.name,end) if self.create_attempted else None
            if cfg is not None:
                cid=self.b.owned(cfg,self.name,self.label,self.cid)
                # Reserve at least 10 seconds for removal. Diagnostics are optional.
                if self.diff is None and cfg.get('State',{}).get('Running') and end-time.time()>10:
                    try:
                        result=self.b.helper(cid,'diff',{},min(end-10,time.time()+3))
                        require(result['returncode']==0,'diagnostic diff failed');self.diff=result['output']
                    except BaseException as e:self.diff_error=repr(e)
                self.b.remove(cid,end);outcome['owned_absent']=True
            elif self.create_ambiguous:
                # A timed-out daemon create may still commit later. Do not call
                # a single absent inspect definitive evidence of cleanup.
                outcome.update(owned_absent=False,error='ambiguous create, absence not provable')
            else:outcome['owned_absent']=True
        except BaseException as e:outcome.update(owned_absent=False,error=repr(e))
        try:
            if self.diff is not None:self.save('final.diff',self.diff.encode())
            else:self.save('diff.unavailable.json',{'error':self.diff_error or 'not captured','non_primary':True})
        except BaseException as e:outcome['diagnostic_write_error']=repr(e)
        return outcome

    def run(self):
        pending=None;cleanup=None;count=0
        try:
            self.save('guardian.ready.json',{'pid':os.getpid(),'identity':identity(os.getpid()),'armed_before_create':True})
            while not self.stop:
                self.current_deadline=self.deadline-RESERVE;self.check()
                path=self.root/'requests'/('%04d.json'%(count+1))
                if not path.exists():time.sleep(.03);continue
                q=json.loads(path.read_text());count+=1;pending=q
                require(count<=128,'finite sandbox operation cap')
                require(q['sequence']==count,'missing/duplicate operation')
                self.save('claims/%04d.json'%count,{'request_sha256':sha(encode(q))})
                value=self.operation(q)
                if self.stop:break
                self.save('responses/%04d.json'%count,{'ok':True,'value':value})
                pending=None
        except BaseException as e:self.failure=repr(e)
        finally:
            cleanup=self.cleanup()
            terminal={'failure':self.failure,'cleanup':cleanup,'phase':self.phase,'finished':time.time(),
                      'diagnostic_only':True,'submitted_by_guardian':False}
            try:self.save('terminal.json',terminal)
            except BaseException:pass
            if pending:
                try:self.save('responses/%04d.json'%pending['sequence'],
                    {'ok':self.failure is None and cleanup['owned_absent'],'value':cleanup,'error':self.failure})
                except BaseException:pass
        return terminal

def main(path):
    s=json.loads(Path(path).read_text())
    from c6_launch import authorize
    r,pin=authorize(**s['approval_args'],deadline=s['preflight_deadline']-RESERVE)
    require(r==s['release'] and pin==s['release_sha256'],'guardian source approval')
    from c6_launch import runtime_root
    require(Path(s['root'])==runtime_root(r,'controller')/'sandbox/state','fixed guardian path')
    require(re.fullmatch('[0-9a-f]{64}',s['label']) and s['name']=='dtr-'+r['run_id']+'-'+s['label'][:12],'ownership namespace')
    require(s['preflight_deadline']==min(r['expires_at'],s['created_at']+1200),'fixed preflight lease')
    Guardian(s,Docker(Path(s['root'])/'docker',r['sandbox'])).run()

if __name__=='__main__':main(sys.argv[1])
