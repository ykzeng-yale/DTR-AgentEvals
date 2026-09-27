"""Narrow adapter boundary. Never puts model text in a host command line.

The actual lead-host adapter is intentionally a separately qualified source.
This module does not manufacture writable-Docker qualification from C3 flags.
No adapter is installed or downloaded by this candidate.
"""
import json,sys,time,os
from pathlib import Path
from c6_protocol import HERE,put,sha,require
from c6_process import Runner
from c3r_arbiter import identity

class QualifiedSandbox:
    def __init__(self,root,r,approval_args=None,created_at=None):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.r=r;self.runner=Runner(self.root/'process');self.count=0;self.guardian_count=0;self.started=False
        self.approval_args=approval_args;self.created_at=created_at or time.time()
        self.driver_identity=identity(os.getpid())
        self.adapter=HERE/'c6_sandbox_host.py'
        self.checker=HERE/'c6_submission_checker.py'
        require(self.adapter.is_file() and self.checker.is_file(), 'lead-host adapter/submission source not installed; launch held')
        require(sha(self.adapter.read_bytes())==r['sandbox']['adapter_sha256'],'sandbox adapter source')
        require(sha(self.checker.read_bytes())==r['submission']['checker_sha256'],'submission checker source')

    def op(self,operation,payload,deadline,executable=None):
        self.count+=1
        if executable is None:self.guardian_count+=1
        spec=self.root/('%03d.input.json'%self.count)
        out=self.root/('%03d.output.json'%self.count)
        put(self.root,spec.name,dict(operation=operation,payload=payload,deadline=deadline,
            run_id=self.r['run_id'],sandbox=self.r['sandbox'],submission=self.r['submission'],
            output_path=str(out),driver_pid=os.getpid(),driver_identity=self.driver_identity,
            approval_args=self.approval_args,release=self.r,release_sha256=sha(__import__('c6_protocol').encode(self.r)),
            created_at=self.created_at,sequence=self.guardian_count))
        self.runner.run([sys.executable,str(executable or self.adapter),str(spec)],deadline)
        require(out.is_file() and out.stat().st_size<=1024*1024,'adapter bounded response')
        return json.loads(out.read_text())

    def preflight(self,r,deadline):
        require(r==self.r,'sandbox release')
        self.started=True
        result=self.op('preflight',{},deadline)
        require(result=={'qualified':True,'watchdog_armed':True,'writable':True,
            'storage_enforced':True,'source_import_qualified':True,'contract':r['sandbox']},'sandbox not ready')

    def execute(self,command,deadline):
        require(self.started,'preflight required')
        # The host argv is fixed. Only the source-approved isolated adapter may execute this data.
        return self.op('execute',{'command':command},deadline)

    def bind_phase(self,ready,obj,deadline):
        result=self.op('bind_phase',{'ready':ready,'object':obj},deadline)
        require(result=={'phase_bound':True,'deadline':ready['deadline']},'phase adoption')

    def check(self,deadline):
        require(self.op('check',{},deadline)=={'active':True},'sandbox terminal')

    def liveness(self):
        root=self.root/'state'
        require(not (root/'terminal.json').exists(),'sandbox guardian terminal')
        ready=json.loads((root/'guardian.ready.json').read_text())
        require(identity(ready['pid'])==ready['identity'],'sandbox guardian identity/liveness')

    def submitted(self,output,deadline):
        result=self.op('check_submission',output,deadline,self.checker)
        require(type(result.get('submitted')) is bool,'submission result')
        require(result['docker_source_sha256']==self.r['submission']['docker_source_sha256'],'submission source binding')
        return result['submitted']

    def diff(self,deadline):
        result=self.op('diff',{},deadline)
        require(type(result.get('diff')) is str,'diff data')
        return result['diff']

    def close(self):
        if not self.started:return {'owned_absent':True,'not_started':True}
        result=self.op('close',{},time.time()+15)
        require(result.get('owned_absent') is True,'sandbox removal unconfirmed')
        return result
