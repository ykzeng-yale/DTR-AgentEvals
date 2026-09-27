"""Single nonrenewing 15-minute admission window; no model during waiting."""
import datetime,hashlib,json,os,subprocess,sys,time
from pathlib import Path
import guard
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/remote_req028/admission_a6_20260927'
def utc(epoch):return datetime.datetime.fromtimestamp(epoch,datetime.timezone.utc).isoformat()
def reason(s):
    if s.get('measurement_error'):return 'measurement_failure'
    if s['pressure_level']!=1:return 'adverse_pressure'
    if s['free_percent']<75:return 'free_metric_below_75'
    if s['foreign_inference']:return 'foreign_inference'
    if s['disk_free_bytes']<12*1024**3:return 'disk_reserve'
    return None
def bounded_window(sample,now,sleep,observe,dispatch,window=900):
    deadline=now()+window;previous=None;count=0
    # Count all observations, including final rechecks, conservatively against 31.
    while count<31 and now()<=deadline:
        reading=sample();count+=1;failure=reason(reading)
        observe(reading,failure,count,'scheduled',deadline)
        instant=now()
        if instant>deadline:break
        if failure:previous=None
        elif previous is None:previous=instant
        elif instant-previous>=60:
            if count>=31:break
            final=sample();count+=1;final_reason=reason(final)
            observe(final,final_reason,count,'final_recheck',deadline)
            if now()<deadline and not final_reason:
                dispatch();return 'DISPATCHED',count
            previous=None
        remaining=deadline-now()
        if remaining<=0:break
        sleep(min(60,remaining))
    # Never renew the window or launch after deadline.
    return 'ADMISSION_WINDOW_EXPIRED',count
def write(name,data):
    with (OUT/name).open('x') as f:json.dump(data,f,indent=2)
def status(data):
    temp=OUT/'status.next';temp.write_text(json.dumps(data,indent=2));temp.replace(OUT/'status.json')
def sample():
    try:return guard.sample()
    except Exception as e:return {'time':time.time(),'measurement_error':repr(e)}
def run():
    start=time.time();deadline=start+900
    write('window.json',{'started':start,'started_utc':utc(start),'deadline':deadline,'deadline_utc':utc(deadline),'supervisor_pid':os.getpid(),'identity':guard.ps(os.getpid()),'max_observations':31,'interval_seconds':60,'two_readings_minimum_spacing_seconds':60})
    count=0
    def observe(reading,failure,number,kind,ignored):
        nonlocal count
        count=number
        entry={'reading':reading,'utc':utc(time.time()),'reason':failure,'observation':number,'kind':kind}
        with (OUT/'observations.jsonl').open('a') as f:f.write(json.dumps(entry)+'\n')
        status({'stage':'WAITING_FOR_ADMISSION','supervisor_pid':os.getpid(),'observation_count':count,'deadline_utc':utc(deadline),'last_observation':entry})
    def dispatch():
        # bounded_window has completed its final recheck; the stage also checks
        # all admission gates immediately before actual server Popen.
        with (OUT/'execution.log').open('xb') as log:
            child=subprocess.Popen([sys.executable,str(Path(__file__).with_name('mechanics_a6.py'))],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,REQ028_PROGRAM_DEADLINE=str(time.time()+600)))
            write('dispatch.json',{'pid':child.pid,'identity':guard.ps(child.pid),'started':time.time(),'started_utc':utc(time.time()),'sequence':'one A6 q8_0 load, two long calls, no restart/retry/fallback'})
            status({'stage':'EXECUTION_DISPATCHED','supervisor_pid':os.getpid(),'execution_pid':child.pid,'observation_count':count,'admission_deadline_utc':utc(deadline)})
            rc=child.wait()
        write('execution_exit.json',{'returncode':rc,'finished_utc':utc(time.time())})
        status({'stage':'EXECUTION_EXITED','returncode':rc,'supervisor_pid':os.getpid(),'observation_count':count,'finished_utc':utc(time.time())})
    outcome,count=bounded_window(sample,time.monotonic,time.sleep,observe,dispatch)
    if outcome!='DISPATCHED':
        write('expiry.json',{'status':outcome,'observation_count':count,'finished_utc':utc(time.time()),'no_model_dispatched':True})
        status({'stage':outcome,'supervisor_pid':os.getpid(),'observation_count':count,'deadline_utc':utc(deadline)})
    hashes={str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file() and p.name!='sha256.json'}
    write('sha256.json',hashes)
def launch():
    prior={}
    for pid in (44005,44752,44776,44778):
        r=subprocess.run(['ps','-p',str(pid),'-o','pid=,lstart=,command='],capture_output=True,text=True)
        assert r.returncode!=0,('prior PID still exists',pid,r.stdout)
        prior[str(pid)]='absent'
    OUT.mkdir(parents=True,exist_ok=False)
    write('prior_cleanup.json',{'verified_at':utc(time.time()),'pids':prior})
    tests=subprocess.run([sys.executable,'-m','unittest','test_guard','test_followup','test_admission','test_a4','test_a5','test_a6'],cwd=Path(__file__).parent,capture_output=True,text=True)
    write('tests.json',{'returncode':tests.returncode,'stdout':tests.stdout,'stderr':tests.stderr})
    assert tests.returncode==0,'fake tests failed'
    snapshot=OUT/'source_snapshot';snapshot.mkdir();hashes={}
    for p in Path(__file__).parent.glob('*.py'):
        data=p.read_bytes();(snapshot/p.name).write_bytes(data);hashes[p.name]=hashlib.sha256(data).hexdigest()
    write('source_manifest.json',{'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'source_hashes':hashes,'release':'dea75bc','goal_product_status':'blocked'})
    with (OUT/'supervisor.log').open('xb') as log:
        child=subprocess.Popen([sys.executable,str(Path(__file__)),'run'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    receipt={'pid':child.pid,'identity':guard.ps(child.pid),'output_directory':str(OUT),'launched_utc':utc(time.time())}
    write('supervisor.json',receipt);print(json.dumps(receipt),flush=True)
if __name__=='__main__':
    if sys.argv[1]=='launch':launch()
    elif sys.argv[1]=='run':run()
    else:raise ValueError('expected launch or run')
