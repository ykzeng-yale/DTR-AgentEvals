"""Fixed source DATA executed only inside the approved container, never on host."""
CODE=r'''
import json,os,subprocess,sys,hashlib,importlib.metadata
from pathlib import Path
s=json.loads(sys.stdin.buffer.read(3*1024**2+1));os.chdir('/testbed')
env=dict(os.environ,PATH='/opt/miniconda3/envs/testbed/bin:/usr/bin:/bin',PYTHONDONTWRITEBYTECODE='1',
    GIT_CONFIG_GLOBAL='/dev/null',GIT_CONFIG_SYSTEM='/dev/null',GIT_CONFIG_NOSYSTEM='1')
git=['/usr/bin/git','--no-pager','-c','core.hooksPath=/dev/null','-c','diff.external=']
steps=[]
def run(args,**kw):
    p=subprocess.run(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,**kw)
    fact=dict(argv=args,returncode=p.returncode,stdout=p.stdout.decode(errors='replace'),stderr=p.stderr.decode(errors='replace'))
    steps.append(fact)
    if p.returncode:
        print(json.dumps(dict(setup_error=fact,steps=steps)))
        sys.exit(p.returncode)
    return p
def capture(args):return subprocess.check_output(args,env=env)
if s['operation']=='prepare':
    assert capture(git+['rev-parse','HEAD']).decode().strip()=='a4ae7a3808de3c53b0788875b6c97b20d5a12ee0'
    assert not capture(git+['status','--porcelain','--untracked-files=all']).strip(),'unclean initial state'
    patch=s['candidate'].encode();tests=s['test_patch'].encode()
    assert len(patch)<=1024**2 and len(tests)<=1024**2
    assert hashlib.sha256(patch).hexdigest()==s['candidate_sha256']
    assert hashlib.sha256(tests).hexdigest()==s['test_patch_sha256']
    assert s['mode'] in ('baseline','candidate')
    if s['mode']=='candidate':
        run(git+['apply','--check','-'],input=patch)
        run(git+['apply','-'],input=patch)
    diff=capture(git+['diff','--no-ext-diff','--no-textconv','--binary','HEAD'])
    assert len(diff)<=1024**2,'diff cap'
    # Restore only the exact declared test file, never the candidate source edit.
    run(git+['checkout','80c3854a5f4f4a6ab86c03d9db7854767fcd83c1','--','astropy/io/fits/tests/test_header.py'])
    run(git+['apply','--check','-'],input=tests)
    run(git+['apply','-'],input=tests)
    import astropy
    assert str(Path(astropy.__file__).resolve()).startswith('/testbed/')
    assert sys.executable=='/opt/miniconda3/envs/testbed/bin/python'
    packages=sorted((d.metadata['Name'],d.version) for d in importlib.metadata.distributions() if d.metadata['Name'])
    print(json.dumps(dict(head='a4ae7a3808de3c53b0788875b6c97b20d5a12ee0',python=sys.executable,
        python_version=sys.version,import_path=astropy.__file__,packages=packages,candidate_diff=diff.decode(),steps=steps,
        candidate_sha256=s['candidate_sha256'],test_patch_sha256=s['test_patch_sha256'],
        omitted_install='python -m pip install -e .[test] --verbose',untouched_stock_harness=False)))
elif s['operation']=='test':
    print('>>>>> Start Test Output',flush=True)
    p=subprocess.run(['/opt/miniconda3/envs/testbed/bin/python','-m','pytest','-rA','astropy/io/fits/tests/test_header.py'],env=env,stdin=subprocess.DEVNULL)
    print('>>>>> End Test Output',flush=True)
    sys.exit(p.returncode)
else:raise ValueError('fixed C7 operation')
'''
