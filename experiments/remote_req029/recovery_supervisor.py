"""C6 independent resident watchdog; adapted unchanged cleanup mechanics from C5."""
import json,os,select,subprocess,sys,time
from pathlib import Path
from recovery_contract import HERE,OLD
import b3_stop,guard
from c2_relay import encode,require
from c3_adapter import PENDING
from c3r_arbiter import identity
from c3r_hooks import ProcessHandle,alive,safe_stop,terminate_direct
from admission_window import reason as admission_reason
from recovery_gate import command
def main(path):
    s=json.loads(Path(path).read_text());root=Path(s['root']);child=None;record=None;write_gate=None;ack=None;active=None;handles=[];outcome=None;failure=None;errors=[]
    def save(name,data):b3_stop.save(root/name,data)
    def check():
        require(not (select.select([sys.stdin],[],[],0)[0] and os.read(sys.stdin.fileno(),1)==b''),'owner_parent_exited')
        try:parent=identity(s['driver_pid'])==s['driver_identity']
        except subprocess.CalledProcessError:parent=False
        require(parent,'owner_parent_exited');require(time.time()<s['phase_deadline'],'phase deadline')
    def checkpoint(stage):
        save(stage+'.json',{'child_pid':None if child is None else child.pid,'child':record,'stage':stage})
        if s.get('inert_test') and s.get('pause_at')==stage:
            while True:check();time.sleep(.01)
        check()
    def begin_sample():
        if s.get('inert_test'):return None
        n=len(handles);spec=root/('telemetry_'+str(n)+'.in.json');out=root/('telemetry_'+str(n)+'.out.json');left=min(5,s['phase_deadline']-time.time())
        spec.write_bytes(encode({'operation':'telemetry','owned_group':None if record is None else record['pid'],'deadline':time.time()+left}))
        h=ProcessHandle([sys.executable,str(OLD/'c4_worker.py'),str(spec),str(out)],left,out);handles.append(h);return h
    def read_sample(h):return json.loads((root/'fake_sample.json').read_text()) if s.get('inert_test') else h.poll()
    try:
        command(s) # Validate exact source approval/argv before any child exists.
        checkpoint('before_spawn');gate_read,write_gate=os.pipe();ack,ack_write=os.pipe()
        child_spec=dict(s,supervisor_pid=os.getpid(),supervisor_identity=identity(os.getpid()));save('gate.json',child_spec)
        with (root/'server.stdout.log').open('xb') as stdout,(root/'server.stderr.log').open('xb') as stderr:
            child=subprocess.Popen([sys.executable,str(HERE/'recovery_gate.py'),str(gate_read),str(ack_write),str(root/'gate.json'),s['token']],pass_fds=(gate_read,ack_write),stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,start_new_session=True,env={k:v for k,v in os.environ.items() if not k.startswith('LLAMA_ARG_')})
        os.close(gate_read);os.close(ack_write);checkpoint('child_spawned')
        record={'pid':child.pid,'identity':identity(child.pid),'ownership_token':s['token'],'parent':s['driver_pid'],'parent_identity':s['driver_identity'],'deadline':s['phase_deadline']};save('owner.json',record);checkpoint('ownership_persisted')
        initial=begin_sample()
        while True:
            check();reading=read_sample(initial)
            if reading is not PENDING:break
            time.sleep(.02)
        require(admission_reason(reading) is None,'final admission failure');baseline=reading['swap_used_mib'];checkpoint('before_exec_release')
        require(alive(record),'gated child identity');check();os.write(write_gate,b'G');os.close(write_gate);write_gate=None;checkpoint('exec_released')
        exec_confirmed=False;transition_until=0;next_sample=0
        while True:
            check();require(child.poll() is None,'owned child exited')
            if not exec_confirmed and select.select([ack],[],[],0)[0]:
                require(os.read(ack,1)==b'','gate validation/exec failed');exec_confirmed=True;transition_until=time.time()+1;os.close(ack);ack=None;save('exec_transition.json',{'cloexec_pipe_closed':True,'no_fixture_signal_required':True});checkpoint('exec_confirmed')
            if exec_confirmed:require(alive(record) or (time.time()<transition_until and not (root/'health_ready.json').exists()),'post-exec ownership')
            require((root/'health_ready.json').exists() or time.time()<s['load_deadline'],'load deadline')
            if (root/'stop.request').exists():break
            if active is None and time.monotonic()>=next_sample:active=begin_sample();next_sample=time.monotonic()+1
            if active is not None or (s.get('inert_test') and time.monotonic()+.99>=next_sample):
                reading=read_sample(active)
                if reading is not PENDING:
                    violation=guard.violation(reading,baseline,s['phase_deadline'],True);save('telemetry_latest.json',dict(reading,violation=violation));require(violation is None,violation or 'guard')
                    with (root/'telemetry.jsonl').open('a') as log:log.write(json.dumps(dict(reading,violation=violation))+'\n')
                    active=None
            time.sleep(.02)
    except BaseException as e:failure=repr(e)
    finally:
        if write_gate is not None:os.close(write_gate)
        if ack is not None:os.close(ack)
        for h in handles:
            try:h.close()
            except BaseException as e:errors.append(repr(e))
        try:
            if child is None:outcome={'owned_absent':True,'no_child_created':True}
            elif record is None:terminate_direct(child);outcome={'owned_absent':child.poll() is not None,'direct_unreaped_child':True}
            else:
                outcome=safe_stop(root/'owner.json',record,failure or 'normal stop')
                if child.poll() is None:terminate_direct(child)
                child.wait(timeout=3);outcome['direct_child_reaped']=True
        except BaseException as e:outcome={'owned_absent':False,'error':repr(e)}
        try:save('supervisor_exit.json',{'failure':failure,'cleanup':outcome,'audit_errors':errors})
        except BaseException:pass
        if s.get('inert_test') and s.get('exit_barrier'):
            while Path(s['exit_barrier']).exists() and time.time()<s['phase_deadline']:
                time.sleep(.01)
if __name__=='__main__':main(sys.argv[1])
