"""Supervisor creates gated child, retains cleanup authority across driver death."""
import json,os,select,subprocess,sys,time
from pathlib import Path
import guard,b3_stop
from c2_relay import require,sha,encode
from c3_adapter import PENDING
from c3r_arbiter import identity
from c3r_hooks import ProcessHandle,alive,safe_stop,terminate_direct
from admission_window import reason as admission_reason
HERE=Path(__file__).parent
def supervise(spec_path):
    s=json.loads(Path(spec_path).read_text());root=Path(s['root']);child=None;record=None;gate_write=None;sample_handles=[];reason='supervisor_exit';cleanup=None;audit_errors=[]
    def save(name,data):
        try:b3_stop.save(root/name,data)
        except BaseException as e:audit_errors.append(repr(e));raise
    def parent_alive():
        # stdin pipe is private to driver; no child inherits it. EOF catches
        # death even before the first child identity/ownership record exists.
        if select.select([sys.stdin],[],[],0)[0] and os.read(sys.stdin.fileno(),1)==b'':return False
        try:return identity(s['driver_pid'])==s['driver_identity']
        except subprocess.CalledProcessError:return False
    def check_parent():
        require(parent_alive(),'owner_parent_exited');require(time.time()<s['deadline'],'fixed deadline')
    def checkpoint(stage):
        save(stage+'.json',{'stage':stage,'child':record,'child_pid':None if child is None else child.pid,'supervisor_pid':os.getpid()})
        if s.get('pause_at')==stage:
            while True:check_parent();time.sleep(.01)
        check_parent()
    def sample():
        if s['telemetry']=='fixture':return json.loads((root/'sample.json').read_text())
        require(s['telemetry']=='real','telemetry mode')
        n=len(sample_handles);spec=root/('telemetry_'+str(n)+'.input.json');out=root/('telemetry_'+str(n)+'.output.json')
        spec.write_bytes(encode({'operation':'telemetry','owned_group':None if record is None else record['pid'],'deadline':min(s['deadline'],time.time()+5)}))
        handle=ProcessHandle([sys.executable,str(HERE/'c4_worker.py'),str(spec),str(out)],min(5,s['deadline']-time.time()),out);sample_handles.append(handle)
        while True:
            check_parent();value=handle.poll()
            if value is not PENDING:return value
            time.sleep(.02)
    try:
        require(s['fixture_executable_sha256']==sha((HERE/'c4_fixture.py').read_bytes()),'inert executable pin')
        require(0<s['deadline']-time.time()<=60 and s['mode'] in ('idle','http','hang','error'),'fixture bounds')
        checkpoint('before_spawn')
        gate_read,gate_write=os.pipe()
        gate_spec=dict(root=str(root),mode=s['mode'],token=s['token'],executable_sha256=s['fixture_executable_sha256'],supervisor_pid=os.getpid(),supervisor_identity=identity(os.getpid()))
        save('gate_spec.json',gate_spec)
        with (root/'child.stderr').open('xb') as error_log:
            child=subprocess.Popen([sys.executable,str(HERE/'c4_gate.py'),str(gate_read),str(root/'gate_spec.json'),s['token']],pass_fds=(gate_read,),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=error_log,start_new_session=True)
        os.close(gate_read)
        checkpoint('child_spawned')
        record={'pid':child.pid,'identity':identity(child.pid),'ownership_token':s['token'],'parent':s['driver_pid'],'parent_identity':s['driver_identity'],'deadline':s['deadline']}
        save('owner.json',record);checkpoint('ownership_persisted')
        initial=sample();require(admission_reason(initial) is None,'final admission failure')
        baseline=initial['swap_used_mib'];checkpoint('before_exec_release')
        require(alive(record),'gated child identity');check_parent()
        os.write(gate_write,b'G');os.close(gate_write);gate_write=None
        checkpoint('exec_released')
        # macOS may hide command argv briefly during exec. The unreaped direct
        # child cannot have its PID reused; do not confuse that transition with
        # loss of ownership or take any signal action against a lookup-only PID.
        while not (root/'exec_seen.json').exists():check_parent();require(child.poll() is None,'child died before exec');time.sleep(.01)
        require(alive(record),'post-exec exact identity')
        checkpoint('running')
        next_sample=0
        while True:
            check_parent();require(alive(record),'owned child exited')
            if (root/'stop.request').exists():reason='driver_stop';break
            if time.monotonic()>=next_sample:
                reading=sample();violation=guard.violation(reading,baseline,s['deadline'],True)
                save('latest_sample.json',dict(reading,violation=violation))
                require(violation is None,violation or 'resource guard');next_sample=time.monotonic()+.1 if s['telemetry']=='fixture' else time.monotonic()+1
            time.sleep(.01)
    except BaseException as e:reason=repr(e)
    finally:
        if gate_write is not None:os.close(gate_write) # EOF prevents any exec
        for handle in sample_handles:
            try:handle.close()
            except BaseException as e:audit_errors.append(repr(e))
        try:
            if child is not None:
                if record is None:terminate_direct(child);cleanup={'owned_absent':child.poll() is not None,'direct_unreaped_child':True}
                else:
                    cleanup=safe_stop(root/'owner.json',record,reason)
                    # Exact command can temporarily disappear across exec. The
                    # unreaped child handle remains authoritative for this child.
                    if child.poll() is None:terminate_direct(child)
                    child.wait(timeout=3);cleanup['direct_child_reaped']=True
            else:cleanup={'owned_absent':True,'no_child_created':True}
        except BaseException as e:cleanup={'owned_absent':False,'error':repr(e)}
        try:save('supervisor_exit.json',{'reason':reason,'cleanup':cleanup,'audit_errors':audit_errors,'driver_cleanup_used':False})
        except BaseException:pass
if __name__=='__main__':supervise(sys.argv[1])
