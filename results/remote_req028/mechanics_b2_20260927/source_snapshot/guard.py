"""Independent process-group watchdog for REQ-028 owned work; stdlib only."""
import argparse, json, os, re, signal, subprocess, sys, time, urllib.request
from pathlib import Path

def ps(pid):
    return subprocess.check_output(['ps','-p',str(pid),'-o','lstart=,command='],text=True).strip()
def same(record):
    try:
        current=ps(record['pid'])
        # macOS Python launcher expands its executable path after Popen; birth
        # time and owned argv suffix remain invariant across that exec.
        born=lambda s:s[:24]
        suffix=record.get('command',[])[-1:] or [record['identity'][24:].strip()]
        command_ok=record.get('ownership_token') in current if record.get('ownership_token') else current.endswith(suffix[0])
        return os.getpgid(record['pid']) == record['pid'] and born(current)==born(record['identity']) and command_ok
    except (ProcessLookupError,subprocess.CalledProcessError):
        return False
def stop(record):
    if not same(record): return False
    os.killpg(record['pid'],signal.SIGTERM)
    time.sleep(.5)
    if same(record): os.killpg(record['pid'],signal.SIGKILL)
    return True
def sample(owned_group=None):
    pressure=subprocess.check_output(['memory_pressure','-Q'],text=True,timeout=5)
    free=int(re.search(r'free percentage:\s*(\d+)%',pressure).group(1))
    level=int(subprocess.check_output(['sysctl','-n','kern.memorystatus_vm_pressure_level'],text=True,timeout=5))
    swap=subprocess.check_output(['sysctl','vm.swapusage'],text=True,timeout=5)
    used=float(re.search(r'used =\s*([\d.]+)M',swap).group(1))
    table=subprocess.check_output(['ps','-axo','pid=,pgid=,rss=,command='],text=True,timeout=5)
    rss=0;foreign=[]
    for line in table.splitlines():
        fields=line.strip().split(None,3)
        if len(fields)<4:continue
        pid,pgid,kib,cmd=fields
        if owned_group and int(pgid)==owned_group:rss+=int(kib)*1024
        elif (Path(cmd.split()[0]).name in ('llama-server','llama-cli')
              or (Path(cmd.split()[0]).name=='ollama' and ' runner ' in cmd)
              or ('python' in Path(cmd.split()[0]).name.lower() and any(x in cmd for x in ('mlx_lm.server','mlx_lm.generate','vllm.entrypoints')))):
            foreign.append({'pid':int(pid),'known_inference_command':True})
    with urllib.request.urlopen('http://127.0.0.1:11434/api/ps',timeout=3) as response:
        if json.load(response).get('models'):foreign.append({'ollama_resident':True})
    disk=os.statvfs('.');available=disk.f_bavail*disk.f_frsize
    return {'time':time.time(),'free_percent':free,'pressure_level':level,'swap_used_mib':used,'owned_rss_bytes':rss,'foreign_inference':foreign,'disk_free_bytes':available}
def violation(s,baseline,deadline,parent_alive=True):
    if not parent_alive:return 'owner_parent_exited'
    if time.time()>deadline:return 'deadline'
    if s['pressure_level']!=1:return 'adverse_pressure'
    if s['free_percent']<20:return 'free_metric_below_20'
    if s['swap_used_mib']-baseline>512:return 'swap_growth'
    if s['owned_rss_bytes']>11*1024**3:return 'owned_rss'
    if s['foreign_inference']:return 'foreign_inference'
    if s['disk_free_bytes']<12*1024**3:return 'disk_reserve'
    return None
def watch(path):
    record=json.loads(Path(path).read_text())
    log=Path(path).with_suffix('.samples.jsonl')
    Path(path).with_suffix('.watchdog_ready.json').write_text(json.dumps({'pid':os.getpid(),'owned_identity_verified':same(record),'time':time.time()}))
    while same(record):
        reason=None
        try:
            os.kill(record['parent'],0);alive=True
        except ProcessLookupError:alive=False
        try:
            s=sample(record['pid'])
            deadline=record['deadline']
            if record.get('phase_deadline_file'):
                deadline=min(deadline,json.loads(Path(record['phase_deadline_file']).read_text())['deadline'])
            reason=violation(s,record['swap_baseline'],deadline,alive)
        except Exception as e:
            s={'time':time.time(),'measurement_error':repr(e)};reason='measurement_failure'
        with log.open('a') as out:out.write(json.dumps(dict(s,abort_reason=reason))+'\n')
        if reason:
            stopped=stop(record)
            Path(path).with_suffix('.abort.json').write_text(json.dumps({'reason':reason,'owned_stop':stopped}))
            return
        time.sleep(1)
def launch(command,out,seconds):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    s=sample()
    assert s['pressure_level']==1 and s['free_percent']>=75 and not s['foreign_inference'],s
    assert s['disk_free_bytes']>=12*1024**3,s
    with (out/'stdout.log').open('xb') as stdout,(out/'stderr.log').open('xb') as stderr:
        child=subprocess.Popen(command,stdout=stdout,stderr=stderr,start_new_session=True)
    record={'pid':child.pid,'parent':os.getpid(),'identity':ps(child.pid),'deadline':time.time()+seconds,'swap_baseline':s['swap_used_mib'],'command':command,'admission':s}
    path=out/'ownership.json';path.write_text(json.dumps(record,indent=2))
    watchdog=subprocess.Popen([sys.executable,__file__,'watch',str(path)],start_new_session=True)
    print(json.dumps({'owned_pid':child.pid,'watchdog_pid':watchdog.pid,'record':str(path)}),flush=True)
    try:
        rc=child.wait(timeout=seconds+10)
    finally:
        stop(record)
        child.wait(timeout=5)
        watchdog.wait(timeout=10)
    (out/'exit.json').write_text(json.dumps({'returncode':rc,'time':time.time(),'released':not same(record)},indent=2))
    return rc
if __name__=='__main__':
    if sys.argv[1]=='watch':watch(sys.argv[2])
    else:sys.exit(launch(sys.argv[4:],sys.argv[2],float(sys.argv[3])))
