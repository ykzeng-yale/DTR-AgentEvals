"""Independent B1 resource guard, with checked source publication before launch."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
import guard
from b1_acquire import ROOT,OUT,SIZE,ASSETS,NAME,capacity
def write(name,data):
    with (OUT/name).open('x') as f:json.dump(data,f,indent=2)
def supervise():
    command=[sys.executable,str(Path(__file__).with_name('b1_acquire.py'))]
    reused_before=(ASSETS/NAME).exists()
    s=guard.sample();deadline=time.time()+1200;capacity(s,5*1024**3,deadline,time.time())
    with (OUT/'worker.log').open('xb') as log:child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    record={'pid':child.pid,'parent':os.getpid(),'identity':guard.ps(child.pid),'command':command,'deadline':deadline,'swap_baseline':s['swap_used_mib']}
    write('ownership.json',record)
    write('watchdog_ready.json',{'pid':os.getpid(),'owned_identity_verified':guard.same(record),'time':time.time()})
    reason=None
    try:
        while child.poll() is None:
            if not guard.same(record):reason='ownership_lost';break
            try:
                reading=guard.sample(child.pid)
                reason=guard.violation(reading,s['swap_used_mib'],deadline)
                if reading['owned_rss_bytes']>2*1024**3:reason='rss_above_2GiB'
                created=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())
                for p in (ASSETS/(NAME+'.partial'),ASSETS/NAME):
                    if p.exists() and not (reused_before and p.name==NAME):created+=p.stat().st_size
                reading['new_disk_bytes']=created
                if created>5*1024**3:reason='new_disk_above_5GiB'
                with (OUT/'samples.jsonl').open('a') as f:f.write(json.dumps(dict(reading,abort_reason=reason))+'\n')
            except Exception as e:reason='measurement_failure'
            if reason:break
            time.sleep(1)
    finally:
        if child.poll() is None:guard.stop(record)
        child.wait(timeout=10)
        write('exit.json',{'returncode':child.returncode,'released':not guard.same(record),'abort_reason':reason,'finished':time.time(),'partial_retained':(ASSETS/(NAME+'.partial')).exists()})
def launch():
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/main'],cwd=ROOT,text=True).split()[0];assert head==remote,'not published'
    sources=list(Path(__file__).parent.glob('*.py'))
    for p in sources:assert subprocess.check_output(['git','show',head+':'+str(p.relative_to(ROOT))],cwd=ROOT)==p.read_bytes(),'unpublished source'
    for pid in (50009,50544,50546):
        assert subprocess.run(['ps','-p',str(pid)],capture_output=True).returncode!=0,('old process live',pid)
    assert not (ASSETS/(NAME+'.partial')).exists(),'existing partial: no renewal'
    OUT.mkdir(parents=True,exist_ok=False)
    tests=subprocess.run([sys.executable,'-m','unittest','test_b1','test_guard'],cwd=Path(__file__).parent,capture_output=True,text=True)
    write('tests.json',{'returncode':tests.returncode,'stdout':tests.stdout,'stderr':tests.stderr});assert tests.returncode==0
    snapshot=OUT/'source_snapshot';snapshot.mkdir();hashes={}
    for p in sources:
        data=p.read_bytes();(snapshot/p.name).write_bytes(data);hashes[p.name]=hashlib.sha256(data).hexdigest()
    write('source_manifest.json',{'source_commit':head,'remote_main':remote,'source_hashes':hashes,'verified_before_launch':time.time(),'release':'efdb643','old_pids_absent':[50009,50544,50546]})
    capacity(guard.sample(),5*1024**3,time.time()+1200,time.time())
    with (OUT/'supervisor.log').open('xb') as log:child=subprocess.Popen([sys.executable,__file__,'supervise'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    receipt={'supervisor_pid':child.pid,'identity':guard.ps(child.pid),'started':time.time(),'source_commit':head}
    write('launch.json',receipt);print(json.dumps(receipt),flush=True)
if __name__=='__main__':
    if sys.argv[1]=='launch':launch()
    else:supervise()
