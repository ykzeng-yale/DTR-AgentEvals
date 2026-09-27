"""Independent one-sandbox evaluator; inherited exact ownership and emergency cleanup."""
import base64,json,os,sys,time,re
from pathlib import Path
from c3r_arbiter import identity
from c6_sandbox_guardian import Guardian as Owner
from c6_protocol import require,sha
from c7_contract import inputs,authorize,runtime,PATCH_SHA,PATCH_CAP
from c7_backend import Backend
from c7_grade import grade

class Guardian(Owner):
    def run(self):
        raw=b'';code=None;failure=None;prepared=None;test_started=False
        try:
            data,patch=inputs() # substitutions fail BEFORE any create
            self.save('guardian.ready.json',dict(pid=os.getpid(),identity=identity(os.getpid()),armed_before_create=True))
            self.preflight();self.check();self.exact()
            payload=dict(mode=self.s['mode'],candidate=patch.decode(),candidate_sha256=PATCH_SHA,
                test_patch=data['test_patch'],test_patch_sha256=sha(data['test_patch'].encode()))
            prepared=self.b.evaluate(self.cid,'prepare',payload,self.current_deadline)
            self.save('prepare.result.json',prepared)
            require(prepared['returncode']==0,'evaluation setup/apply failure')
            facts=json.loads(prepared['output']);diff=facts['candidate_diff'].encode()
            require(len(diff)<=PATCH_CAP,'candidate diff cap')
            self.diff=diff.decode();self.save('prepared.json',facts)
            self.check();self.exact()
            test_started=True
            result=self.b.evaluate(self.cid,'test',{},self.current_deadline)
            raw=base64.b64decode(result['raw_base64']);code=result['returncode']
            self.save('test.output',raw);self.save('test.exit.json',{'returncode':code})
        except BaseException as e:
            failure=repr(e)
            # Capture guardians preserve a bounded raw prefix even on timeout or
            # overflow. Bind UNKNOWN to those bytes without pretending completion.
            if test_started:
                try:
                    path=self.b.runner.root/('%04d.result.json'%self.b.runner.count)
                    partial=json.loads(path.read_bytes())
                    raw=base64.b64decode(partial['raw_base64']);code=partial['returncode']
                    self.save('test.partial.output',raw)
                except BaseException:pass
        finally:
            cleanup=self.cleanup() # no journal-dependent launch path, even on write failure
        report=grade(raw,code,self.s['mode'],self.s['release']['run_id'],failure,cleanup['owned_absent'])
        report.update(cleanup=cleanup,finished=time.time(),deadline=self.deadline,
            raw_output_complete=test_started and failure is None,
            source_commit=self.s['release']['source_commit'],source_hashes=self.s['release']['source_hashes'],
            release_sha256=self.s['release_sha256'])
        self.save('terminal.json',report)
        return report

def main(path):
    s=json.loads(Path(path).read_bytes());r=authorize(**s['approval_args'])
    require(r==s['release'],'guardian release substitution')
    require(s['release_sha256']==s['approval_args']['pin'],'guardian release SHA')
    require(s['mode'] in ('baseline','candidate'),'mode')
    require(Path(s['root'])==runtime(r)/s['mode'],'fixed guardian root')
    require(s['preflight_deadline']==min(r['expires_at'],s['total_deadline'],s['created_at']+600),'600 second lease')
    require(s['total_deadline']==min(r['expires_at'],s['run_started']+1200),'1200 second lease')
    require(s['run_started']<=s['created_at']<=time.time(),'creation timestamp')
    require(re.fullmatch('[0-9a-f]{64}',s['label']) and s['name']=='dtr-'+r['run_id']+'-'+s['mode']+'-'+s['label'][:12],'exact ownership name')
    require(identity(s['driver_pid'])==s['driver_identity'],'driver identity')
    Guardian(s,Backend(Path(s['root'])/'docker',r['sandbox'])).run()

if __name__=='__main__':main(sys.argv[1])
