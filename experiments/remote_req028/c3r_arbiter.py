"""B3-compatible journal/lock protocol with bounded identity probes.

Copied stop semantics from b3_stop; shared durable TERM claim prevents repeat TERM.
Cleanup has its own finite safety deadline, independent of expired work deadlines.
"""
import fcntl,json,os,signal,subprocess,time
from pathlib import Path
import b3_stop
def identity(pid,timeout=1):
    return subprocess.check_output(['ps','-p',str(pid),'-o','lstart=,command='],text=True,timeout=max(.001,timeout)).strip()
def same(record,deadline=None):
    try:
        timeout=1 if deadline is None else min(1,max(.001,deadline-time.monotonic()))
        current=identity(record['pid'],timeout)
        suffix=record.get('command',[])[-1:] or [record['identity'][24:].strip()]
        command_ok=record.get('ownership_token') in current if record.get('ownership_token') else current.endswith(suffix[0])
        return os.getpgid(record['pid'])==record['pid'] and current[:24]==record['identity'][:24] and command_ok
    except (ProcessLookupError,subprocess.CalledProcessError):return False
def stop(owner,actor,reason,seconds=8):
    owner=Path(owner);record=json.loads(owner.read_text());key=b3_stop.identity_key(record)
    journal=owner.with_suffix('.stop.json');lock=owner.with_suffix('.stop.lock');deadline=time.monotonic()+seconds
    def present():
        if time.monotonic()>=deadline:raise TimeoutError('B3 cleanup deadline')
        return same(record,deadline)
    with lock.open('a') as f:
        while True:
            if time.monotonic()>=deadline:raise TimeoutError('B3 lock deadline')
            try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:time.sleep(.02)
        state=json.loads(journal.read_text()) if journal.exists() else {'identity_key':key,'pid':record['pid'],'requests':[],'signals':[]}
        assert state['identity_key']==key,'stop identity mismatch'
        state['requests'].append({'actor':actor,'reason':reason,'pid':os.getpid(),'time':time.time()})
        def flush():b3_stop.save(journal,state)
        if present() and not state.get('term_claim'):
            state['term_claim']={'actor':actor,'reason':reason,'owner_pid':os.getpid(),'time':time.time()};flush()
            if present():
                os.killpg(record['pid'],signal.SIGTERM);state['signals'].append({'signal':'TERM','actor':actor,'time':time.time()});flush()
        until=min(deadline,time.monotonic()+.3)
        while present() and time.monotonic()<until:time.sleep(.01)
        if present():
            os.killpg(record['pid'],signal.SIGKILL);state['signals'].append({'signal':'KILL','actor':actor,'time':time.time()});flush()
        while present():time.sleep(.01)
        state.update(owned_absent=True,confirmed_at=time.time());flush();return state
