"""Comparator entrypoint. Only a later exact immutable lead release can unlock it.

No --fixture flag in this production command; tests use comparator_tests.py.
"""
import argparse,json,re,subprocess,time
from pathlib import Path
from recovery_contract import ROOT,encode,sha,require,validate,commit,put,digest,inventory

def git(*args,deadline):
    require(time.time()<deadline,'source setup deadline')
    p=subprocess.run(['git',*args],cwd=ROOT,capture_output=True,timeout=min(30,deadline-time.time()))
    require(p.returncode==0,'source Git read')
    return p.stdout

def authorize(release_commit,release_path,release_sha,deadline=None):
    deadline=deadline or time.time()+300
    commit(release_commit);digest(release_sha)
    require(re.fullmatch(r'docs/req029o_[A-Za-z0-9_-]+[.]json',release_path),'REQ029O approval allowlist')
    raw=git('show',release_commit+':'+release_path,deadline=deadline)
    require(sha(raw)==release_sha,'approval SHA')
    r=validate(json.loads(raw))
    expected=inventory()
    require(r['source_hashes']==expected,'complete source inventory')
    for path,pin in expected.items():
        require(sha(git('show',r['worker_commit']+':'+path,deadline=deadline))==pin,'approved source commit')
    return r,release_sha

def runtime_root(r,role):
    require(role in ('worker','controller'),'runtime role')
    root=ROOT/'results/remote_req029/comparator_runtime'/r['run_id']/role
    require(root.resolve()==root,'runtime path symlink substitution')
    return root

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('role',choices=['worker','controller'])
    p.add_argument('--release-commit',required=True)
    p.add_argument('--release-path',required=True)
    p.add_argument('--release-sha',required=True)
    p.add_argument('--transport-config',required=True)
    a=p.parse_args()
    args={k:getattr(a,k) for k in ('release_commit','release_path','release_sha')}
    started=time.time();setup_deadline=started+300
    r,pin=authorize(**args,deadline=setup_deadline)
    # A caller cannot change --output to replay the same approved run.
    root=runtime_root(r,a.role)
    require(not root.exists(),'no restart/resume')
    # The finite pre-Popen phase is setup+admission, never indefinite residency.
    deadline=min(r['expires_at'],started+1200)
    from recovery_transport import Transport
    from recovery_engine import Worker,Controller
    from recovery_model import Model
    from recovery_sandbox import QualifiedSandbox
    raw=Path(a.transport_config).read_bytes()
    require(sha(raw)==r['transport_config_sha256'],'private transport configuration pin')
    cfg=json.loads(raw)
    require(set(cfg)=={'alias','mailbox','helper'} and cfg['alias']=='mac-mini','exact host transport')
    require(Path(cfg['mailbox']).name==r['run_id'],'run-bound mailbox')
    transport=Transport(root/'network',cfg['mailbox'],cfg['helper'],
        r['source_hashes']['experiments/remote_req029/recovery_mailbox.py'],a.role,deadline,
        alias=cfg['alias'] if a.role=='controller' else None)

    # Transport owns its directory; each role owns a separate exclusive claim directory.
    role=(Worker if a.role=='worker' else Controller)(root/'role',r,pin,transport)
    role.deadline=deadline
    if a.role=='worker':
        role.deadline=min(setup_deadline,r['expires_at'])
        result=role.run(Model(args,setup_deadline))
    else:
        result=role.run(QualifiedSandbox(root/'sandbox',r,args,started))
    print(json.dumps({'status':result['status'],'claims':result['claims'],'scientific_success_assessed':False}))

if __name__=='__main__':main()
