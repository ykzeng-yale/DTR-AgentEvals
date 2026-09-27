"""Fixed container-only source DATA. No host execution on import."""
CODE=r'''
import hashlib,importlib.metadata,json,os,platform,shlex,subprocess,sys,time
from pathlib import Path
BASE='51c9bb7cd16081133af4f0ab6d06572660309730'
HEAD='becf6f8b613d4206f95411821ed66e5e0f428edc'
COMMAND='./tests/runtests.py --verbosity 2 --settings=test_sqlite --parallel 1 constraints.tests postgres_tests.test_constraints'
TEST_PATHS=['tests/constraints/tests.py','tests/postgres_tests/test_constraints.py']
PYTHON='/opt/miniconda3/envs/testbed/bin/python'
git=['/usr/bin/git','--no-pager','-c','safe.directory=/testbed','-c','core.hooksPath=/dev/null','-c','diff.external=']
env=dict(os.environ,PATH='/opt/miniconda3/envs/testbed/bin:/usr/bin:/bin',PYTHONDONTWRITEBYTECODE='1',
    OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',GIT_CONFIG_GLOBAL='/dev/null',GIT_CONFIG_SYSTEM='/dev/null',GIT_CONFIG_NOSYSTEM='1')
steps=[]
def run(args,**kw):
    start=time.monotonic();p=subprocess.run(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,**kw)
    fact=dict(argv=args,returncode=p.returncode,seconds=time.monotonic()-start,
        stdout=p.stdout.decode(errors='replace'),stderr=p.stderr.decode(errors='replace'),
        stdout_bytes=len(p.stdout),stderr_bytes=len(p.stderr))
    steps.append(fact)
    if p.returncode:
        print(json.dumps(dict(setup_error=fact,steps=steps)),flush=True)
        raise RuntimeError('fixed setup command failed')
    return p.stdout
def source_diff():
    return run(git+['diff','--no-ext-diff','--no-textconv','--binary',HEAD])
def prepare(s):
    assert run(git+['rev-parse','HEAD']).decode().strip()==HEAD
    assert run(git+['rev-parse','HEAD^']).decode().strip()==BASE
    assert not run(git+['status','--porcelain','--untracked-files=all']).strip(),'unclean initial source'
    assert not run(git+['diff','--no-ext-diff','--no-textconv','--binary',BASE]).strip(),'setup source diff'
    reference=s['reference'].encode();tests=s['test_patch'].encode()
    assert len(reference)<=1024**2 and len(tests)<=1024**2
    assert hashlib.sha256(reference).hexdigest()==s['reference_patch_sha256']
    assert hashlib.sha256(tests).hexdigest()==s['test_patch_sha256']
    assert s['mode'] in ('baseline','reference')
    if s['mode']=='reference':
        run(git+['apply','--check','-'],input=reference)
        run(git+['apply','-'],input=reference)
    diff=source_diff();assert len(diff)<=1024**2
    # Reset exactly the test patch's two paths, never the reference fix.
    run(git+['checkout',BASE,'--']+TEST_PATHS)
    assert source_diff()==diff,'test reset altered prepared source'
    run(git+['apply','--check','-'],input=tests)
    run(git+['apply','-'],input=tests)
    return diff
def main(s):
    os.chdir('/testbed')
    op=s['operation']
    if op=='preflight':
        assert run(git+['rev-parse','HEAD']).decode().strip()==HEAD
        assert run(git+['rev-parse','HEAD^']).decode().strip()==BASE
        assert not run(git+['diff','--no-ext-diff','--no-textconv',BASE]).strip()
        import django
        assert str(Path(django.__file__).resolve())=='/testbed/django/__init__.py'
        assert sys.executable==PYTHON
        mounts={line.split()[1]:line.split()[3].split(',') for line in Path('/proc/mounts').read_text().splitlines()}
        assert 'ro' in mounts['/']
        for name,size in (('/testbed',512*1024**2),('/tmp',64*1024**2)):
            assert all(k in mounts[name] for k in ('rw','nosuid','nodev'))
            v=os.statvfs(name);assert v.f_blocks*v.f_frsize==size
        assert 'noexec' not in mounts['/testbed']
        p=Path('/testbed/.django-eval-preflight');p.write_text('fixed writable probe');p.unlink()
        assert os.listdir('/sys/class/net')==['lo']
        u=platform.uname()
        print(json.dumps(dict(head=HEAD,base=BASE,python=sys.executable,import_path=django.__file__,
            writable=True,limits_verified=True,uname={k:getattr(u,k) for k in ('system','release','version','machine')},steps=steps)))
    elif op=='prepare':
        diff=prepare(s)
        import django
        assert str(Path(django.__file__).resolve())=='/testbed/django/__init__.py' and sys.executable==PYTHON
        packages=sorted((d.metadata['Name'],d.version) for d in importlib.metadata.distributions() if d.metadata['Name'])
        print(json.dumps(dict(head=HEAD,base=BASE,python=sys.executable,python_version=sys.version,
            import_path=django.__file__,packages=packages,source_diff=diff.decode(),steps=steps,mode=s['mode'],
            reference_patch_sha256=s['reference_patch_sha256'],test_patch_sha256=s['test_patch_sha256'],
            omitted_install='python -m pip install -e .',untouched_stock_harness=False,test_command=COMMAND,test_paths=TEST_PATHS)))
    elif op=='test':
        print('>>>>> Start Test Output',file=sys.stderr,flush=True)
        start=time.monotonic()
        p=subprocess.run(shlex.split(COMMAND),env=env,stdin=subprocess.DEVNULL)
        print('>>>>> End Test Output',file=sys.stderr,flush=True)
        print(json.dumps(dict(test_seconds=time.monotonic()-start,test_returncode=p.returncode)),flush=True)
        # Same reset as stock harness after tests; a reset failure is UNKNOWN.
        try:run(git+['checkout',BASE,'--']+TEST_PATHS)
        except BaseException:
            print('>>>>> Reset Failed',file=sys.stderr,flush=True);raise
        sys.exit(p.returncode)
    elif op=='diff':
        sys.stdout.buffer.write(source_diff())
    else:raise ValueError('fixed Django evaluator operation')
if __name__=='__main__':
    raw=sys.stdin.buffer.read(3*1024**2+1)
    assert len(raw)<=3*1024**2
    main(json.loads(raw))
'''
