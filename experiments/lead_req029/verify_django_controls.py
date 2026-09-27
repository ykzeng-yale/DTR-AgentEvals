"""Retrospective deterministic replay of the exact local REQ029I controls."""
import collections,hashlib,json,subprocess,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments/remote_req029'))
from django_eval_grade import grade
from django_eval_contract import bind_prepared,inventory,normalized,inputs
from prompt_boundary import build

def sha(b):return hashlib.sha256(b).hexdigest()
def run():
    runtime=ROOT/'results/local_req029/django_eval_runtime/dje029i-20260927-a'
    out=ROOT/'results/local_req029/django_controls_verified_20260927';out.mkdir(exist_ok=False)
    summaries={};pids=[46232];unames=[]
    for mode in ('baseline','reference'):
        p=runtime/mode;d=json.loads((p/'terminal.json').read_bytes());raw=(p/'test.output').read_bytes()
        replay=grade(raw,d['returncode'],mode,d['run_id'],d['infrastructure_error'],d['cleanup']['owned_absent'])
        assert replay['control_accepted'] and d['control_accepted']
        for key in replay:assert replay[key]==d[key],key
        assert sha(raw)==d['raw_output_sha256']
        prepared=json.loads((p/'prepared.json').read_bytes());diff=bind_prepared(prepared,mode)
        assert diff==(p/'source.prepared.diff').read_bytes() and sha(diff)==d['applied_patch_sha256']
        assert d['source_hashes']==inventory()
        unames.append(json.loads((p/'preflight.probe.json').read_bytes())['uname'])
        pids.append(json.loads((p/'guardian.ready.json').read_bytes())['pid'])
        # Upstream parser emits short failure aliases; separate them from extra tests.
        extra=d['extra_statuses'];skips={k:v for k,v in extra.items() if v=='SKIPPED'}
        assert len(skips)==54 and sum('postgres_tests.' in k for k in skips)==50
        other_skips=[k for k in skips if 'postgres_tests.' not in k]
        assert len(other_skips)==4 and all('constraints.tests.' in k for k in other_skips)
        aliases={k:v for k,v in extra.items() if v!='SKIPPED'}
        assert all(' ' not in k and any(t.startswith(k+' ') and value==v for t,value in d['declared_statuses'].items()) for k,v in aliases.items())
        summaries[mode]=dict(declared=dict(collections.Counter(d['declared_statuses'].values())),runner_returncode=d['returncode'],raw_runner_tests=d['raw_runner_totals'],extra_postgres_skips=50,extra_other_skips=other_skips,short_failure_aliases=aliases,raw_sha256=sha(raw),prepared_sha256=sha(diff),cleanup=d['cleanup'],finished=d['finished'])
    assert unames[0]==unames[1]
    ps=subprocess.run(['ps','-p',','.join(map(str,pids)),'-o','pid=,etime=,stat='],capture_output=True,text=True)
    assert not ps.stdout.strip(),'owned PID still present'
    docker=subprocess.run(['/Users/yukangzengcmac/.local/dtr-runtime/bin/docker','--context','colima-dtr','ps','-aq'],capture_output=True,text=True,check=True)
    assert not docker.stdout.strip(),'container remains'
    members={}
    with tarfile.open(out/'runtime.tar.gz','w:gz') as t:
        for p in sorted(runtime.rglob('*')):
            if p.is_file():
                assert not p.is_symlink();name=str(p.relative_to(runtime));members[name]=sha(p.read_bytes());t.add(p,arcname=name,recursive=False)
    seen=set()
    with tarfile.open(out/'runtime.tar.gz','r:gz') as t:
        for m in t:
            assert m.isfile() and m.name not in seen
            assert sha(t.extractfile(m).read())==members[m.name];seen.add(m.name)
    assert seen==set(members)
    (out/'member_hashes.json').write_text(json.dumps(members,indent=2,sort_keys=True)+'\n')
    summary=dict(run_id='dje029i-20260927-a',controls=summaries,owned_pids_absent=pids,docker_inventory_empty=True,archive_members_verified=len(members),archive_sha256=sha((out/'runtime.tar.gz').read_bytes()),source_pins_verified=len(inventory()),script_sha256=sha(Path(__file__).read_bytes()),uname=unames[0],scope='one-task offline evaluator controls; no model comparison or untouched-stock claim')
    (out/'lead_verification.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n')
    message=build((ROOT/'docs/source_snapshots/req029j_prompt/public_task.json').read_bytes(),unames[0])
    target=ROOT/'docs/source_snapshots/req029j_prompt/messages.json';target.write_bytes(message)
    binding=dict(messages_sha256=sha(message),messages_bytes=len(message),builder_sha256=sha((ROOT/'experiments/lead_req029/prompt_boundary.py').read_bytes()),uname=unames[0],measurement_sources={mode:dict(path=str((runtime/mode/'preflight.probe.json').relative_to(ROOT)),sha256=sha((runtime/mode/'preflight.probe.json').read_bytes())) for mode in ('baseline','reference')},same_initial_bytes_both_arms=True,model_execution_authorized=False)
    (ROOT/'docs/source_snapshots/req029j_prompt/measured_binding.json').write_text(json.dumps(binding,indent=2,sort_keys=True)+'\n')
    print(json.dumps(dict(members=len(members),controls=summaries,messages_sha256=sha(message),messages_bytes=len(message))))
if __name__=='__main__':run()
