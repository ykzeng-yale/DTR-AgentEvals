"""One bounded A2 followed only by authorized pressure-discriminator A3."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
import guard
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/remote_req028/admitted_execution_20260927'
def permit_a3(status,aborts,failure):
    if status.get('status')!='FAILED':return False
    lives=status.get('lifecycles',[])
    if not lives or not all(x.get('released') for x in lives):return False
    if len(aborts)!=1 or aborts[0].get('reason')!='adverse_pressure' or not aborts[0].get('owned_stop'):return False
    allowed=("RemoteDisconnected(", "ConnectionResetError(", "RuntimeError('server exited during load:", "RuntimeError('resource watchdog abort')")
    return failure.get('exception','').startswith(allowed)
def save(name,data):
    with (OUT/name).open('x') as f:json.dump(data,f,indent=2)
def run_stage(variant,deadline):
    env=dict(os.environ,REQ028_VARIANT=variant,REQ028_PROGRAM_DEADLINE=str(deadline))
    with (OUT/(variant+'.driver.log')).open('xb') as log:
        child=subprocess.Popen([sys.executable,str(Path(__file__).with_name('mechanics_admitted.py'))],env=env,stdout=log,stderr=subprocess.STDOUT)
        save(variant+'.driver.json',{'pid':child.pid,'started':time.time()})
        # Stage owns model group and independent deadline watchdog; do not terminate
        # the supervisor ahead of its owned cleanup.
        rc=child.wait()
    path=ROOT/('results/remote_req028/mechanics_'+variant.lower()+'_20260927')
    status=json.loads((path/'status.json').read_text()) if (path/'status.json').exists() else {'status':'SETUP_FAILED'}
    aborts=[json.loads(p.read_text()) for p in path.glob('*.abort.json')]
    failure=json.loads((path/'failure.json').read_text()) if (path/'failure.json').exists() else {}
    save(variant+'.result.json',{'returncode':rc,'status':status,'aborts':aborts,'failure':failure})
    return status,aborts,failure
def main():
    OUT.mkdir(parents=True,exist_ok=False)
    baseline=json.loads((ROOT/'results/remote_req028/mechanics_20260927/manifest.json').read_text())
    archive=OUT/'a1_source_snapshot';archive.mkdir()
    for name,digest in baseline['source_hashes'].items():
        data=(Path(__file__).parent/name).read_bytes()
        assert hashlib.sha256(data).hexdigest()==digest,name
        (archive/name).write_bytes(data)
    tests=subprocess.run([sys.executable,'-m','unittest','test_guard','test_followup','test_admission'],cwd=Path(__file__).parent,capture_output=True,text=True)
    save('fake_tests.json',{'returncode':tests.returncode,'stdout':tests.stdout,'stderr':tests.stderr})
    assert tests.returncode==0,'pre-execution tests failed'
    snapshot=OUT/'followup_source_snapshot';snapshot.mkdir()
    hashes={}
    for p in Path(__file__).parent.glob('*.py'):
        data=p.read_bytes();(snapshot/p.name).write_bytes(data);hashes[p.name]=hashlib.sha256(data).hexdigest()
    save('source_hashes.json',hashes)
    deadline=time.time()+1800
    save('program.json',{'started':time.time(),'deadline':deadline,'maximum_configurations':2,'no_retry':True,'product_goal_status':'blocked'})
    status,aborts,failure=run_stage('A2R',deadline)
    allowed=permit_a3(status,aborts,failure)
    save('dispatch.json',{'permit_a3':allowed,'a2_status':status.get('status'),'reason':'same adverse pressure plus cleanup and expected interruption' if allowed else 'A2 completion or nonqualifying failure'})
    if not allowed:return
    recovery_start=time.monotonic()
    baseline_swap=status['after']['swap_used_mib']
    while True:
        sample=guard.sample()
        reason=guard.violation(sample,baseline_swap,deadline)
        with (OUT/'recovery.jsonl').open('a') as f:f.write(json.dumps(dict(sample,abort_reason=reason))+'\n')
        if reason:
            save('A3.skipped.json',{'reason':'recovery failed','sample':sample});return
        if time.monotonic()-recovery_start>=60:break
        time.sleep(1)
    if sample['free_percent']<75:
        save('A3.skipped.json',{'reason':'single post-recovery admission unavailable','sample':sample});return
    run_stage('A3R',deadline)
if __name__=='__main__':main()
