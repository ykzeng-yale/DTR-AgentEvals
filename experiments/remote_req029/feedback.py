"""REQ-029A candidate semantics only. No activation CLI or prior-approval reuse.

The frozen req028 parser/template/native/submission helpers are read-only imports.
Only completed ordinary exit statuses become feedback; all exception paths fail closed.
"""
import sys,time
from pathlib import Path
FROZEN=Path(__file__).resolve().parents[1]/'remote_req028'
sys.path.insert(0,str(FROZEN))
from c6_protocol import Chain as FrozenChain,observation,encode,sha,require,commit
from c6_submission_checker import check as upstream_submission
from c6_sandbox_guardian import Guardian as FrozenGuardian

PROTOCOL=29
SEMANTICS='req029a-completed-shell-feedback-v1'

def completed(output):
    require(type(output) is dict and set(output)=={'output','returncode','exception_info'},'completed output schema')
    require(type(output['returncode']) is int and 0<=output['returncode']<=255,'completed shell exit status')
    require(output['exception_info'] is None,'infrastructure exception is terminal')
    require(type(output['output']) is str and len(output['output'].encode())<=1024**2,'output cap')
    return output

def submitted(output):
    completed(output)
    return upstream_submission(output)['submitted']

class Chain(FrozenChain):
    def request(self,deadline):
        q=super().request(deadline);q.update(protocol=PROTOCOL,feedback_semantics=SEMANTICS);return q
    def response(self,*args,**kwargs):
        r=super().response(*args,**kwargs);r.update(protocol=PROTOCOL,feedback_semantics=SEMANTICS);return r

def observation_envelope(r,pin,sequence,response_object,response,output):
    completed(output)
    return dict(protocol=PROTOCOL,feedback_semantics=SEMANTICS,run_id=r['run_id'],release_sha256=pin,
        sequence=sequence,controller_commit=r['controller_commit'],response_object=response_object,
        response_sha256=sha(encode(response)),output=output,output_sha256=sha(encode(output)),
        observation=observation(output))

def check_observation(value,r,pin,sequence,response_object,response,observation_object):
    require(observation_object['sha256']==sha(encode(value)),'observation object hash')
    require(value==observation_envelope(r,pin,sequence,response_object,response,value['output']),'observation binding')
    return value['observation']

class Guardian(FrozenGuardian):
    """Unchanged ownership/cleanup, with versioned phase and completed-exit feedback."""
    def bind(self,payload):
        require(self.ready,'preflight first')
        if self.phase is not None:
            require(payload==self.phase,'phase renewal/conflict')
            return {'phase_bound':True,'deadline':self.deadline}
        ready=payload['ready'];obj=payload['object'];r=self.s['release']
        commit(obj['commit']);commit(obj['blob'])
        require(obj['path']==r['root']+'/ready.json' and obj['sha256']==sha(encode(ready)),'worker-ready object binding')
        require(ready['protocol']==PROTOCOL and ready['run_id']==r['run_id'] and ready['release_sha256']==self.s['release_sha256'] and
            ready['worker_commit']==r['worker_commit'],'ready source binding')
        require(self.s['created_at']<=ready['phase_started']<=time.time(),'phase start')
        require(ready['deadline']==min(ready['phase_started']+1800,r['expires_at']),'immutable phase deadline')
        require(time.time()<ready['deadline']-15,'phase reserve')
        self.save('phase.binding.json',payload);self.phase=payload;self.deadline=ready['deadline']
        return {'phase_bound':True,'deadline':self.deadline}

    def operation(self,q):
        if q['operation']!='execute':return super().operation(q)
        require(q['run_id']==self.s['release']['run_id'] and q['driver_identity']==self.s['driver_identity'] and
            q['driver_pid']==self.s['driver_pid'] and q['release_sha256']==self.s['release_sha256'],'caller identity/release')
        self.current_deadline=min(q['deadline'],self.deadline-15)
        self.check();require(self.phase is not None,'no command before phase adoption');self.exact()
        payload=q['payload']
        require(set(payload)=={'command'} and type(payload['command']) is str and len(payload['command'].encode())<=65536,'command data')
        self.current_deadline=min(self.current_deadline,time.time()+60)
        # Backend raises on timeout/overflow/supervision errors. Never catch these
        # and relabel as an ordinary exit; FrozenGuardian.run owns cleanup.
        result=self.b.helper(self.cid,'execute',payload,self.current_deadline)
        output={'output':result['output'],'returncode':result['returncode'],'exception_info':None}
        self.save('command-%04d.output.json'%q['sequence'],output)
        completed(output)
        self.check() # guard/deadline failure after completion is still terminal
        return output
