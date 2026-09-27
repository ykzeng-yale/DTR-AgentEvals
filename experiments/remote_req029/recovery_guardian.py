"""Independent comparator guardian: imports reviewed ordinary-exit operation."""
import json,re,sys,time
from pathlib import Path
from recovery_contract import *
from feedback import Guardian as FeedbackGuardian
from comparator_backend import Docker
from c6_sandbox_backend import RESERVE
from c3r_arbiter import identity
class Guardian(FeedbackGuardian):
    def bind(self,payload):
        require(self.ready,'preflight first')
        if self.phase is not None:
            require(payload==self.phase,'phase renewal/conflict')
            return {'phase_bound':True,'deadline':self.deadline}
        ready=payload['ready'];obj=payload['object'];r=self.s['release']
        require(obj==dict(transport='ssh-mailbox-v1',name='ready.json',sha256=sha(encode(ready)),helper_sha256=r['source_hashes']['experiments/remote_req029/recovery_mailbox.py']),'worker-ready SSH object binding')
        require(ready['protocol']==PROTOCOL and ready['cell']==cell(r) and ready['run_id']==r['run_id'] and ready['release_sha256']==self.s['release_sha256'] and
            ready['worker_commit']==r['worker_commit'],'ready source binding')
        require(self.s['created_at']<=ready['phase_started']<=time.time(),'phase start')
        require(ready['deadline']==min(ready['phase_started']+1800,r['expires_at']),'immutable phase deadline')
        require(time.time()<ready['deadline']-15,'phase reserve')
        self.save('phase.binding.json',payload);self.phase=payload;self.deadline=ready['deadline']
        return {'phase_bound':True,'deadline':self.deadline}


def main(path):
    s=json.loads(Path(path).read_text())
    from recovery_launch import authorize
    r,pin=authorize(**s['approval_args'],deadline=s['preflight_deadline']-RESERVE)
    require(r==s['release'] and pin==s['release_sha256'],'guardian source approval')
    from recovery_launch import runtime_root
    require(Path(s['root'])==runtime_root(r,'controller')/'sandbox/state','fixed guardian path')
    require(re.fullmatch('[0-9a-f]{64}',s['label']) and s['name']=='dtr-'+r['run_id']+'-'+s['label'][:12],'ownership namespace')
    require(s['preflight_deadline']==min(r['expires_at'],s['created_at']+1200),'fixed preflight lease')
    Guardian(s,Docker(Path(s['root'])/'docker',r['sandbox'])).run()

if __name__=='__main__':main(sys.argv[1])
