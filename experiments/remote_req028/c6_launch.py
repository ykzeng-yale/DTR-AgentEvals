"""C6 finite entrypoint. Only a later exact immutable lead release can unlock it.

No --fixture flag in this production command; local fixtures use c6_tests.py.
"""
import argparse,json,subprocess,time
from pathlib import Path
from c6_protocol import ROOT,encode,sha,require,release,commit,put

def git(*args,deadline):
    require(time.time()<deadline,'source setup deadline')
    p=subprocess.run(['git',*args],cwd=ROOT,capture_output=True,timeout=min(30,deadline-time.time()))
    require(p.returncode==0,'source Git read')
    return p.stdout

def authorize(release_commit,release_path,release_sha,deadline=None):
    deadline=deadline or time.time()+300
    commit(release_commit)
    require(release_path.startswith('docs/req028_c6_') and '..' not in Path(release_path).parts,'C6 approval path')
    raw=git('show',release_commit+':'+release_path,deadline=deadline)
    r=release(raw,release_sha)
    require(r['worker_commit']==r['controller_commit'],'candidate uses one reviewed source tree')
    source=r['worker_commit']
    paths=git('ls-tree','-r','--name-only',source,'--','experiments/remote_req028',deadline=deadline).decode().splitlines()
    expected={p for p in paths if p.endswith(('.py','.json'))}
    require(set(r['source_hashes'])==expected,'complete transitive source inventory')
    for path,pin in r['source_hashes'].items():
        require(sha(git('show',source+':'+path,deadline=deadline))==pin,'approved commit source')
        require(sha((ROOT/path).read_bytes())==pin,'local source differs')
    # These inputs must exist before either host can start its finite driver.
    # Missing local source evidence is not silently replaced with prompt semantics.
    require('experiments/remote_req028/c6_sandbox_host.py' in expected and
            'experiments/remote_req028/c6_submission_checker.py' in expected,'qualified adapters missing')
    return r,release_sha

def runtime_root(r,role):
    require(role in ('worker','controller'),'runtime role')
    root=ROOT/'results/remote_req028/c6_runtime'/r['run_id']/role
    require(root.resolve()==root,'runtime path symlink substitution')
    return root

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('role',choices=['worker','controller'])
    p.add_argument('--release-commit',required=True)
    p.add_argument('--release-path',required=True)
    p.add_argument('--release-sha',required=True)
    p.add_argument('--relay-repo',required=True)
    a=p.parse_args()
    args={k:getattr(a,k) for k in ('release_commit','release_path','release_sha')}
    started=time.time();setup_deadline=started+300
    r,pin=authorize(**args,deadline=setup_deadline)
    # A caller cannot change --output to replay the same approved run.
    root=runtime_root(r,a.role)
    require(not root.exists(),'no restart/resume')
    # The finite pre-Popen phase is setup+admission, never indefinite residency.
    deadline=min(r['expires_at'],started+1200)
    from c6_git import Transport
    from c6_engine import Worker,Controller
    from c6_model import Model
    from c6_sandbox import QualifiedSandbox
    transport=Transport(a.relay_repo,root/'network',r['root'],a.role,deadline)
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
