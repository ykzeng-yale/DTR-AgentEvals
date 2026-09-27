"""Bounded C7 serial suite, fixture evidence and complete source fingerprints."""
import json,os,subprocess,sys,time
from pathlib import Path
from c6_protocol import HERE,sha
from c6_ipc import publish
from c7_contract import inventory

def main():
    root=Path(sys.argv[1]).resolve();root.mkdir(parents=True,exist_ok=False)
    before=inventory();started=time.monotonic();samples=[];failure=None
    env=dict(os.environ,C7_FIXTURE_OUT=str(root/'fixtures'),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1')
    with (root/'tests.log').open('xb') as log:
        p=subprocess.Popen([sys.executable,'-m','unittest','-v','c7_tests'],cwd=HERE,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            while p.poll() is None:
                rows=[list(map(int,x.split())) for x in subprocess.check_output(['ps','-axo','pid=,ppid=,rss='],text=True,timeout=2).splitlines() if len(x.split())==3]
                descendants={p.pid}
                for _ in range(12):descendants|={pid for pid,parent,rss in rows if parent in descendants}
                rss=sum(rss*1024 for pid,parent,rss in rows if pid in descendants)
                size=sum(f.stat().st_size for f in root.rglob('*') if f.is_file())
                samples.append(dict(elapsed=time.monotonic()-started,rss=rss,bytes=size))
                assert rss<=2*1024**3 and size<=100*1024**2 and time.monotonic()-started<290,'test budget'
                time.sleep(.2)
        except BaseException as e:failure=repr(e);p.terminate()
        finally:
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill();p.wait(timeout=2)
    after=inventory()
    publish(root,'receipt.json',dict(returncode=p.returncode,failure=failure,elapsed_seconds=time.monotonic()-started,
        samples=samples,source_before=before,source_after=after,source_unchanged=before==after,
        single_serial_driver=True,math_threads=1,cpu_affinity_enforced=False,actual_model_docker_evaluator=False))
    print(json.dumps(dict(returncode=p.returncode,failure=failure,elapsed_seconds=time.monotonic()-started,source_unchanged=before==after)))
    sys.exit(1 if failure or before!=after else p.returncode)

if __name__=='__main__':main()
