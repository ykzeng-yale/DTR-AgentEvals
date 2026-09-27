"""Bounded, one-shot C2 test run and frozen nonce creation, no live relay dispatch."""
import hashlib,json,os,resource,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/remote_req028/c2_setup_verified_20260927'
def write(name,data):
    with (OUT/name).open('x') as f:json.dump(data,f,indent=2)
def child():
    resource.setrlimit(resource.RLIMIT_CPU,(290,290))
    import unittest,c2_tests
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(c2_tests))
    return 0 if result.wasSuccessful() else 1
def main():
    OUT.mkdir(exist_ok=False,parents=True)
    started=time.monotonic();peak=0;samples=0
    with (OUT/'tests.log').open('x') as log:
        process=subprocess.Popen([sys.executable,__file__,'--tests'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1'))
        try:
            while process.poll() is None:
                # Sum entire worker descendant tree, including local fixture Git processes.
                rows=subprocess.check_output(['ps','-axo','pid=,ppid=,rss='],text=True,timeout=3)
                table=[tuple(map(int,row.split())) for row in rows.splitlines()]
                owned={process.pid};changed=True
                while changed:
                    before=len(owned);owned.update(pid for pid,parent,rss in table if parent in owned);changed=len(owned)>before
                rss=sum(rss for pid,parent,rss in table if pid in owned or pid==os.getpid())*1024;peak=max(peak,rss);samples+=1
                if rss>2*1024**3 or time.monotonic()-started>=290:raise RuntimeError('test resource/deadline cap')
                time.sleep(.05)
        except BaseException:
            os.killpg(process.pid,signal.SIGKILL);process.wait();raise
    write('test_execution.json',{'returncode':process.returncode,'elapsed_seconds':time.monotonic()-started,'peak_sampled_tree_rss_bytes':peak,'samples':samples,'wall_cap_seconds':290,'rss_cap_bytes':2*1024**3,'single_compute_worker':True,'publication_only_no_running_worker':True})
    if process.returncode:return process.returncode
    from c2_relay import frozen_nonce,validate_request
    raw=frozen_nonce();validate_request(raw,time.time())
    with (OUT/'request.json').open('xb') as f:f.write(raw)
    snapshot=OUT/'source_snapshot';snapshot.mkdir()
    for source in Path(__file__).parent.glob('c2_*.py'):(snapshot/source.name).write_bytes(source.read_bytes())
    size=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file());assert size<=50*1024**2
    write('manifest.json',{'request_sha256':hashlib.sha256(raw).hexdigest(),'config_identifier':'fixture-only-v1','new_artifact_bytes_before_manifest':size,'synthetic_only':True,'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshot.iterdir()},'limitations':'No request dispatched. Temporary local Git repos only in tests; live response pending lead review. Monitored RSS, not hard address-space enforcement.'})
    write('sha256.json',{str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file()})
    return 0
if __name__=='__main__':sys.exit(child() if '--tests' in sys.argv else main())
