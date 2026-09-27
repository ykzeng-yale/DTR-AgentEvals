"""B3 cross-process stop arbitration; one durable TERM claim per exact identity."""
import fcntl,hashlib,json,os,signal,subprocess,sys,time
from pathlib import Path
import guard
def identity_key(record):
    return hashlib.sha256(json.dumps({k:record.get(k) for k in ('pid','identity','ownership_token','command')},sort_keys=True).encode()).hexdigest()
def save(path,data):
    temp=path.with_name(path.name+'.'+str(os.getpid())+'.next')
    with temp.open('w') as f:json.dump(data,f,indent=2);f.flush();os.fsync(f.fileno())
    temp.replace(path)
def stop(owner,actor,reason,grace=2.0,kill_wait=2.0,after_claim=None):
    owner=Path(owner);record=json.loads(owner.read_text());key=identity_key(record)
    journal=owner.with_suffix('.stop.json');lock=owner.with_suffix('.stop.lock')
    deadline=time.monotonic()+8
    with lock.open('a') as f:
        while True:
            try:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if time.monotonic()>=deadline:raise TimeoutError('stop arbitration lock deadline')
                time.sleep(.02)
        state=json.loads(journal.read_text()) if journal.exists() else {'identity_key':key,'pid':record['pid'],'requests':[],'signals':[]}
        assert state['identity_key']==key,'stop identity key mismatch'
        state['requests'].append({'actor':actor,'reason':reason,'pid':os.getpid(),'time':time.time()})
        def flush():save(journal,state)
        if not guard.same(record):
            state.update(owned_absent=True,confirmed_at=time.time(),no_signal_on_mismatch=True);flush();return state
        if not state.get('term_claim'):
            # Persist before killpg; a dead owner successor NEVER repeats TERM.
            state['term_claim']={'actor':actor,'reason':reason,'owner_pid':os.getpid(),'time':time.time()}
            flush()
            if after_claim:after_claim()
            if guard.same(record):
                event={'signal':'TERM','actor':actor,'time':time.time()}
                os.killpg(record['pid'],signal.SIGTERM);state['signals'].append(event);flush()
        until=state['term_claim']['time']+grace
        while guard.same(record) and time.time()<until:time.sleep(.02)
        if guard.same(record):
            # Revalidated immediately before the fallback. Repeating KILL after a
            # dead stopper is allowed; TERM is never repeated.
            event={'signal':'KILL','actor':actor,'time':time.time()}
            os.killpg(record['pid'],signal.SIGKILL);state['signals'].append(event);flush()
        until=time.monotonic()+kill_wait
        while guard.same(record) and time.monotonic()<until:time.sleep(.02)
        state.update(owned_absent=not guard.same(record),confirmed_at=time.time())
        flush()
        if not state['owned_absent']:raise RuntimeError('owned termination unconfirmed')
        return state
def watch(owner):
    owner=Path(owner);record=json.loads(owner.read_text())
    save(owner.with_suffix('.watchdog_ready.json'),{'pid':os.getpid(),'owned_identity_verified':guard.same(record),'time':time.time()})
    while guard.same(record):
        try:
            try:
                alive=guard.ps(record['parent'])==record['parent_identity']
            except subprocess.CalledProcessError:alive=False
            sample=guard.sample(record['pid']);deadline=record['deadline']
            if record.get('phase_deadline_file'):deadline=min(deadline,json.loads(Path(record['phase_deadline_file']).read_text())['deadline'])
            reason=guard.violation(sample,record['swap_baseline'],deadline,alive)
        except Exception as e:sample={'time':time.time(),'measurement_error':repr(e)};reason='measurement_failure'
        with owner.with_suffix('.samples.jsonl').open('a') as f:f.write(json.dumps(dict(sample,abort_reason=reason))+'\n')
        if reason:
            # Publish reason BEFORE stopping, so driver sees the abort during teardown.
            abort=owner.with_suffix('.abort.json')
            save(abort,{'reason':reason,'stop_started':time.time(),'owned_stop':False})
            result=stop(owner,'watchdog',reason)
            save(abort,{'reason':reason,'owned_stop':result['owned_absent'],'stop_finished':time.time()})
            return
        time.sleep(1)
if __name__=='__main__':
    if sys.argv[1]=='watch':watch(sys.argv[2])
    else:stop(sys.argv[2],sys.argv[3],sys.argv[4])
