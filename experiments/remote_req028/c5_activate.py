"""Executable candidate. No manifest-only activation; exact lead source approval required."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
from c2_relay import encode,sha,require
from c3_adapter import PENDING
from c3r_hooks import ProcessHandle,alive
from c4_lifecycle import ProductionLifecycle
from c4_attest import MODEL,SERVER
from a6r_gate import admit
from c5_contract import *
from c5_lifecycle import Lifecycle,free_port
from c5_transport import ExactTransport
from c5_execute import Execution
HERE=Path(__file__).parent
OUTPUT=ROOT/'results/remote_req028/c5_execution_20260927'
def isolated_relay(root,expected_main,deadline):
    relay=root/'relay'
    def run(cwd,*args):
        left=deadline-time.time();require(left>0,'relay setup deadline');r=subprocess.run(['git',*args],cwd=cwd,capture_output=True,timeout=left);require(r.returncode==0,'isolated relay Git setup failed')
    run(ROOT,'clone','--shared','--no-checkout',str(ROOT),str(relay))
    run(relay,'remote','set-url','origin','https://github.com/ykzeng-yale/DTR-AgentEvals.git')
    run(relay,'fetch','--no-tags','origin','refs/heads/main')
    require(git(relay,'rev-parse','FETCH_HEAD').decode().strip()==expected_main,'main changed before setup')
    run(relay,'sparse-checkout','init','--no-cone')
    run(relay,'sparse-checkout','set','--no-cone','/'+REQUEST_PATH,'/'+RELEASE_PATH)
    run(relay,'checkout','--detach',expected_main)
    return relay
def ensure_old_owned_absent():
    receipts=[]
    paths=list((ROOT/'results/remote_req028').glob('mechanics*/*ownership.json'))+[ROOT/'results/remote_req028/mechanics_c0_20260927/qwen/server_0.ownership.json']
    for path in paths:
        record=json.loads(path.read_text());require(not alive(record),'old owned model still alive');receipts.append({'path':str(path.relative_to(ROOT)),'exact_owned_identity_absent':True})
    return receipts
def activate(args):
    started=time.time();setup_deadline=min(EXPIRY,started+300)
    # This check precedes directory creation, hashing, admission, or Popen.
    require(all((args.source_commit,args.approval_commit,args.approval_sha)),'manifest is NOT launch permission: exact lead source approval required')
    approval_args={'source_commit':args.source_commit,'approval_commit':args.approval_commit,'approval_path':'docs/req028_c5_source_approval_20260927.json','approval_sha':args.approval_sha}
    approved,approval_raw=approval(ROOT,**approval_args,now=time.time());pins=source_pins(ROOT,args.source_commit,setup_deadline);require(time.time()<setup_deadline,'setup deadline')
    require(not OUTPUT.exists(),'one C5 execution root only; no retry/resume');OUTPUT.mkdir(parents=True)
    handles=[];life=None
    def write(name,data):
        with (OUTPUT/name).open('xb') as f:f.write(data if type(data) is bytes else encode(data))
    try:
        write('source_approval.json',approval_raw);write('source_pins.json',pins);write('setup_window.json',{'started':started,'deadline':setup_deadline});write('old_owned_absence.json',ensure_old_owned_absent())
        before_stats={}
        for path in (MODEL,SERVER):
            st=path.stat();before_stats[str(path)]=[st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns]
        att=OUTPUT/'attestation.json';h=ProcessHandle([sys.executable,str(HERE/'c4_attest.py'),str(att)],setup_deadline-time.time());handles.append(h)
        while h.poll() is PENDING:time.sleep(.02)
        require(time.time()<setup_deadline,'setup deadline');attestation_sha=sha(att.read_bytes())
        network_started=time.time();relay=isolated_relay(OUTPUT,approved['expected_main'],setup_deadline);transport=ExactTransport(relay)
        manifest=(ROOT/RELEASE_PATH).read_bytes();raw=transport.authorize_exact(manifest,approved['expected_main'],min(30,setup_deadline-time.time()));write('request.json',raw);write('release.json',manifest)
        write('setup_network_timing.json',{'started':network_started,'finished':time.time(),'includes_isolated_relay_setup':True})
        stats={}
        for path in (MODEL,SERVER):
            st=path.stat();stats[str(path)]=[st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns]
        require(stats==before_stats,'assets changed during attestation/setup')
        window=min(EXPIRY,time.time()+900);write('admission_window.json',{'deadline':window,'maximum_reads':31,'once_only':True})
        sampler=ProductionLifecycle(OUTPUT/'admission_samples',window)
        def observe(reading,reason,count,kind):
            with (OUTPUT/'admission.jsonl').open('a') as f:f.write(json.dumps({'sample':reading,'reason':reason,'count':count,'kind':kind})+'\n')
        def launch(last_sample):
            nonlocal life
            phase_started=time.time();deadline=min(EXPIRY,phase_started+600);token='c4-c5-owned-'+str(os.getpid())+'-'+str(time.time_ns())
            spec={'inert_test':False,'approval_args':approval_args,'approval':approved,'source_pins':pins,'asset_stats':stats,'attestation_sha256':attestation_sha,'phase_started':phase_started,'phase_deadline':deadline,'load_deadline':min(deadline,phase_started+180),'token':token,'port':free_port()}
            write('model_window.json',spec);life=Lifecycle(OUTPUT/'supervision',spec)
            return Execution(OUTPUT,life,transport,raw,manifest,attestation_sha).run()
        try:return admit(sampler.sample,time.time,time.sleep,observe,launch,window)
        finally:sampler.stop('admission finished')
    except BaseException as e:
        try:write('activation_failure.json',{'error':repr(e),'no_retry':True})
        except BaseException:pass
        raise
    finally:
        if life is not None:
            try:life.stop()
            except BaseException:pass # Execution retains cleanup failure, never replaces primary
        for h in handles:h.close()
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source-commit');parser.add_argument('--approval-commit');parser.add_argument('--approval-sha');args=parser.parse_args();activate(args)
if __name__=='__main__':main()
