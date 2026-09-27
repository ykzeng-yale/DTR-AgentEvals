"""Bounded serial test runner and sampled descendant RSS receipt (no live services)."""
import argparse,json,os,signal,subprocess,sys,time
from pathlib import Path
from c6_protocol import put,sha,HERE

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--seconds',type=float,required=True)
    p.add_argument('tests',nargs='*');a=p.parse_args();root=Path(a.out).resolve();root.mkdir(parents=True,exist_ok=False)
    assert 0<a.seconds<=300
    started=time.time();samples=[];failure=None
    sources_before={f.name:sha(f.read_bytes()) for f in HERE.glob('c6_*') if f.is_file()}
    env=dict(os.environ,C6_FIXTURE_OUT=str(root/'fixtures'),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1')
    cmd=[sys.executable,'-m','unittest','-v']+(a.tests or ['c6_tests'])
    with (root/'unittest.log').open('xb') as log:
        child=subprocess.Popen(cmd,cwd=HERE,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            while child.poll() is None:
                raw=subprocess.check_output(['ps','-axo','pid=,ppid=,rss='],text=True,timeout=2)
                rows=[list(map(int,x.split())) for x in raw.splitlines() if len(x.split())==3]
                descendants={child.pid}
                for _ in range(10):
                    descendants|={pid for pid,ppid,rss in rows if ppid in descendants}
                rss=sum(rss*1024 for pid,ppid,rss in rows if pid in descendants)
                disk=sum(f.stat().st_size for f in root.rglob('*') if f.is_file())
                samples.append(dict(time=time.time(),rss_bytes=rss,artifact_bytes=disk,pids=sorted(descendants)))
                assert rss<=2*1024**3,'RSS cap';assert disk<=100*1024**2,'artifact cap'
                assert time.time()-started<a.seconds,'test wall budget'
                time.sleep(.2)
        except BaseException as e:
            failure=repr(e);child.terminate()
        finally:
            try:child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=2)
    elapsed=time.time()-started
    sources_after={f.name:sha(f.read_bytes()) for f in HERE.glob('c6_*') if f.is_file()}
    if sources_before!=sources_after:failure='source changed during test run'
    put(root,'receipt.json',dict(command=cmd,started=started,elapsed_seconds=elapsed,returncode=child.returncode,
        runner_failure=failure,samples=samples,max_sampled_rss_bytes=max((s['rss_bytes'] for s in samples),default=0),
        single_serial_unittest_driver=True,math_library_threads=1,cpu_affinity_enforced=False,
        cpu_limit_note='macOS has no portable per-process one-core affinity control; children are inert or bounded I/O',
        imported_test_repeats=0,model_or_docker_executed=False,source_hashes=sources_before,
        source_hashes_after=sources_after,source_unchanged=sources_before==sources_after))
    print(json.dumps(dict(returncode=child.returncode,elapsed_seconds=elapsed,out=str(root),failure=failure)))
    sys.exit(1 if failure else child.returncode)

if __name__=='__main__':main()
