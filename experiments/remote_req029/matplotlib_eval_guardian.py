"""Independent Matplotlib control owner, bounded by one arm lease and driver identity."""
import base64,json,os,re,sys,time
from pathlib import Path
from matplotlib_eval_contract import *
from c3r_arbiter import identity
from c6_sandbox_guardian import Guardian as Owner
from matplotlib_eval_backend import Backend
from matplotlib_eval_grade import grade,bindings

class Guardian(Owner):
    def run(self):
        raw=b'';code=None;failure=None;test_started=False;applied=None;capture=None
        try:
            data,patch,_=inputs()
            require(self.s['mode'] in MODES,'fixed mode before create')
            require(self.s['reference_patch_sha256']==PATCH_SHA,'patch before create')
            if self.s['mode']=='reference':verify_baseline(self.s)
            self.save('reference.original.diff',patch)
            self.save('stock_eval_script.sh',data['stock_eval_script'].encode())
            bindings()
            self.save('guardian.ready.json',dict(pid=os.getpid(),identity=identity(os.getpid()),armed_before_create=True))
            self.preflight();self.check();self.exact()
            payload=dict(mode=self.s['mode'],reference=patch.decode(),reference_patch_sha256=PATCH_SHA,
                test_patch=data['test_patch'],test_patch_sha256=sha(data['test_patch'].encode()))
            prepared=self.b.evaluate(self.cid,'prepare',payload,self.current_deadline)
            self.save('helper.prepare.raw.json',prepared)
            require(prepared['returncode']==0,'setup/apply failure')
            facts=json.loads(prepared['output']);diff=bind_prepared(facts,self.s['mode'])
            applied=sha(diff);self.diff=diff.decode()
            self.save('source.prepared.diff',diff);self.save('prepared.json',facts)
            self.check();self.exact()
            self.save('test.claim.json',dict(mode=self.s['mode'],dispatches=1,no_retry=True,deadline=self.current_deadline))
            test_started=True
            capture=self.b.evaluate(self.cid,'test',{},self.current_deadline)
            raw=base64.b64decode(capture['raw_base64']);code=capture['returncode']
            self.save('test.capture.json',capture)
            self.save('test.output',raw)
            for name in ('stdout','stderr'):self.save('test.'+name,base64.b64decode(capture[name+'_base64']))
            self.check();self.exact()
        except BaseException as e:
            failure=repr(e)
            if test_started:
                try:
                    capture=json.loads((self.b.runner.root/('%04d.result.json'%self.b.runner.count)).read_bytes())
                    raw=base64.b64decode(capture['raw_base64']);code=capture['returncode']
                    self.save('test.partial.output',raw)
                except BaseException:pass
        finally:
            cleanup=self.cleanup()
        cleanup.update(cid=self.cid,name=self.name,label=self.label)
        report=grade(raw,code,self.s['mode'],self.s['release']['run_id'],failure,cleanup['owned_absent'])
        report.update(applied_patch_sha256=applied,cleanup=cleanup,finished=time.time(),deadline=self.deadline,
            raw_output_complete=test_started and failure is None,baseline_receipt_sha256=self.s.get('baseline_receipt_sha256'),
            capture=None if capture is None else {k:v for k,v in capture.items() if k not in ('raw_base64','stdout_base64','stderr_base64','output')},
            source_commit=self.s['release']['source_commit'],source_hashes=self.s['release']['source_hashes'],
            release_sha256=self.s['release_sha256'],sandbox=self.s['release']['sandbox'])
        self.save('terminal.json',report)
        return report

def verify_baseline(s):
    path=Path(s['root']).parent/'baseline/terminal.json'
    raw=path.read_bytes();require(sha(raw)==s['baseline_receipt_sha256'],'baseline receipt byte binding')
    report=json.loads(raw);r=s['release']
    require(report['protocol']==PROTOCOL and report['task']==TASK and report['mode']=='baseline' and
        report['run_id']==r['run_id'] and report['source_commit']==r['source_commit'] and
        report['source_hashes']==r['source_hashes'] and report['release_sha256']==s['release_sha256'],'baseline identity')
    require(report['control_accepted'] is True and report['cleanup']['owned_absent'] is True and
        report['raw_output_complete'] is True,'baseline gate')
    # Re-grade original raw bytes, not only a Boolean in the receipt.
    log=(path.parent/'test.output').read_bytes()
    require(sha(log)==report['raw_output_sha256'],'baseline raw binding')
    check=grade(log,report['returncode'],'baseline',r['run_id'])
    require(check['control_accepted'] and check['declared_statuses']==report['declared_statuses'],'baseline gate regrade')

def main(path):
    s=json.loads(Path(path).read_bytes());r=authorize(**s['approval_args'])
    require(r==s['release'] and s['release_sha256']==s['approval_args']['pin'],'guardian exact approval')
    require(s['mode'] in MODES and Path(s['root'])==runtime(r)/s['mode'],'fixed mode/root')
    require(s['reference_patch_sha256']==PATCH_SHA,'reference pin')
    require(s['preflight_deadline']==min(r['expires_at'],s['total_deadline'],s['created_at']+600),'600s arm')
    require(s['total_deadline']==min(r['expires_at'],s['run_started']+1200),'1200s pair')
    require(s['run_started']<=s['created_at']<=time.time(),'timestamps')
    require(re.fullmatch('[0-9a-f]{64}',s['label']) and s['name']=='dtr-'+r['run_id']+'-'+s['mode']+'-'+s['label'][:12],'exact ownership')
    require(identity(s['driver_pid'])==s['driver_identity'],'driver identity')
    Guardian(s,Backend(Path(s['root'])/'docker',r['sandbox'])).run()

if __name__=='__main__':main(sys.argv[1])
