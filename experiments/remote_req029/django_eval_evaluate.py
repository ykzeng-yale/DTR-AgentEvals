"""Serial baseline then gated reference. New exact REQ-029I approval required."""
import argparse,json,os,secrets,subprocess,sys,time
from pathlib import Path
from django_eval_contract import HERE
from c3r_arbiter import identity
from c6_protocol import require,sha
from c6_ipc import publish
from django_eval_contract import authorize,inputs,runtime,PATCH_SHA,MODES,PROTOCOL,TASK

def launch(spec,path):
    with (path.parent/'guardian.stderr').open('xb') as err:
        return subprocess.Popen([sys.executable,str(HERE/'django_eval_guardian.py'),str(path)],
            stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=err,start_new_session=True)

def run(r,pin,args,root,launcher=launch):
    inputs();root=Path(root);root.mkdir(parents=True,exist_ok=False)
    started=time.time();end=min(r['expires_at'],started+1200)
    publish(root,'run.claim.json',dict(run_id=r['run_id'],modes=MODES,
        reference_patch_sha256=PATCH_SHA,applied_patch_sha256=None,started=started,deadline=end,no_retry=True))
    reports=[];baseline_pin=None
    for mode in MODES:
        now=time.time();require(now<end-15,'total cleanup reserve')
        directory=root/mode;directory.mkdir();label=secrets.token_hex(32)
        spec=dict(root=str(directory),mode=mode,reference_patch_sha256=PATCH_SHA,
            applied_patch_sha256=None,baseline_receipt_sha256=baseline_pin,release=r,release_sha256=pin,approval_args=args,
            driver_pid=os.getpid(),driver_identity=identity(os.getpid()),run_started=started,
            total_deadline=end,created_at=now,preflight_deadline=min(end,now+600),
            name='dtr-'+r['run_id']+'-'+mode+'-'+label[:12],label=label)
        publish(directory,'spec.json',spec);proc=launcher(spec,directory/'spec.json')
        # Independent guardian sees driver identity loss if this process dies.
        # This is finite local IPC waiting, not a Git/model polling service.
        try:
            proc.wait(timeout=max(.001,spec['preflight_deadline']-time.time()+2))
        except subprocess.TimeoutExpired:
            raise RuntimeError('guardian did not exit; cleanup UNKNOWN; no second sandbox')
        require(proc.returncode==0,'guardian failed; cleanup UNKNOWN; no second sandbox')
        terminal=directory/'terminal.json';require(terminal.exists(),'missing cleanup receipt; no second sandbox')
        report=json.loads(terminal.read_bytes())
        require(report['run_id']==r['run_id'] and report['mode']==mode and report['reference_patch_sha256']==PATCH_SHA and 'candidate_sha256' not in report and
            report['protocol']==PROTOCOL and report['task']==TASK and report['source_commit']==r['source_commit'] and
            report['release_sha256']==pin and report['source_hashes']==r['source_hashes'],'report binding')
        reports.append(report)
        require(report['cleanup']['owned_absent'],'cleanup unconfirmed; no second sandbox')
        # Only a fully accepted baseline permits the single reference arm.
        if not report['control_accepted']:break
        if mode=='baseline':baseline_pin=sha(terminal.read_bytes())
    publish(root,'controls.json',dict(run_id=r['run_id'],modes=MODES,
        reference_patch_sha256=PATCH_SHA,
        prepared_diff_sha256_by_mode={x['mode']:x['applied_patch_sha256'] for x in reports},
        reports=reports,finished=time.time(),deadline=end,no_retry=True,scientific_comparison=False))
    return reports

def main():
    p=argparse.ArgumentParser();p.add_argument('--commit',required=True);p.add_argument('--path',required=True);p.add_argument('--pin',required=True)
    args=vars(p.parse_args());r=authorize(**args)
    run(r,args['pin'],args,runtime(r))

if __name__=='__main__':main()
