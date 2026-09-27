"""Concrete production adapter. No fixture flag or caller-selected executable."""
import json,os,subprocess,sys,time,uuid
from pathlib import Path
from c3r_arbiter import identity
from c6_protocol import HERE,put,require
from c6_ipc import publish
from c6_sandbox_backend import RESERVE

def spawn(spec_path):
    with (spec_path.parent/'guardian.stderr').open('xb') as err:
        return subprocess.Popen([sys.executable,str(HERE/'c6_sandbox_guardian.py'),str(spec_path)],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=err,start_new_session=True)

def exchange(root,q,spec=None,launcher=spawn):
    """Common production/fake-process interface. Test code injects launcher in Python."""
    root=Path(root)
    if q['operation']=='preflight':
        require(spec is not None,'preflight guardian plan')
        root.mkdir(parents=True,exist_ok=False)
        publish(root,'guardian.spec.json',spec)
        launcher(root/'guardian.spec.json')
    else:require(root.is_dir(),'sandbox was never armed')
    terminal=root/'terminal.json'
    if terminal.exists():
        value=json.loads(terminal.read_text())
        require(q['operation']=='close','sandbox is terminal, no replay')
        return value['cleanup']
    publish(root,'requests/%04d.json'%q['sequence'],q)
    response=root/'responses'/('%04d.json'%q['sequence'])
    while True:
        require(time.time()<q['deadline'],'adapter operation deadline')
        if response.exists():
            value=json.loads(response.read_text())
            require(value['ok'],value.get('error') or 'sandbox cleanup failure')
            return value['value']
        if terminal.exists():
            value=json.loads(terminal.read_text())
            require(q['operation']=='close','guardian terminal: '+str(value['failure']))
            return value['cleanup']
        ready=root/'guardian.ready.json'
        if ready.exists():
            record=json.loads(ready.read_text())
            try:present=identity(record['pid'])==record['identity']
            except BaseException:present=False
            require(present,'guardian died: cleanup indeterminate, no restart')
        time.sleep(.03)

def main(path):
    from c6_launch import authorize,runtime_root
    s=json.loads(Path(path).read_text())
    r,pin=authorize(**s['approval_args'],deadline=s['deadline'])
    require(r==s['release'] and pin==s['release_sha256'],'adapter approval binding')
    base=runtime_root(r,'controller')/'sandbox';root=base/'state'
    require(Path(path).resolve().parent==base and Path(s['output_path']).resolve().parent==base,'fixed adapter paths')
    require(identity(s['driver_pid'])==s['driver_identity'],'actual controller identity')
    spec=None
    if s['operation']=='preflight':
        require(s['created_at']<=time.time()<min(r['expires_at'],s['created_at']+1200)-RESERVE,'preflight lease')
        label=uuid.uuid4().hex+uuid.uuid4().hex
        spec=dict(root=str(root),release=r,release_sha256=pin,approval_args=s['approval_args'],
            driver_pid=s['driver_pid'],driver_identity=s['driver_identity'],created_at=s['created_at'],
            preflight_deadline=min(r['expires_at'],s['created_at']+1200),label=label,
            name='dtr-'+r['run_id']+'-'+label[:12])
    q={k:s[k] for k in ('operation','payload','deadline','sequence','run_id','driver_pid','driver_identity','release_sha256')}
    result=exchange(root,q,spec)
    out=Path(s['output_path']);publish(out.parent,out.name,result)

if __name__=='__main__':main(sys.argv[1])
