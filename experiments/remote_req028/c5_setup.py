"""Bounded inert C5 tests; no source activation approval or model execution."""
import hashlib,json,os,resource,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/remote_req028'/os.environ.get('C5_RUN_NAME','c5_setup_20260927')
def write(name,data):
    with (OUT/name).open('x') as f:json.dump(data,f,indent=2)
def child():
    resource.setrlimit(resource.RLIMIT_CPU,(140,140));os.environ.update(C3_FIXTURE_OUT=str(OUT/'c3'),C3R_FIXTURE_OUT=str(OUT/'c3r'),C4_FIXTURE_OUT=str(OUT/'c4'),C5_FIXTURE_OUT=str(OUT/'c5'))
    import unittest,c3r_tests,c4_tests,c5_tests
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in (c3r_tests,c4_tests,c5_tests));result=unittest.TextTestRunner(verbosity=2).run(suite);return 0 if result.wasSuccessful() else 1
def main():
    OUT.mkdir(parents=True,exist_ok=False);started=time.monotonic();peak=0;samples=0;tracked={}
    with (OUT/'tests.log').open('x') as log:
        proc=subprocess.Popen([sys.executable,__file__,'--tests'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1'))
        try:
            while proc.poll() is None:
                rows=subprocess.check_output(['ps','-axo','pid=,ppid=,rss=,lstart='],text=True,timeout=3);table=[]
                for row in rows.splitlines():
                    f=row.split(None,3)
                    if len(f)==4:table.append((*map(int,f[:3]),f[3]))
                owned={proc.pid};changed=True
                while changed:
                    before=len(owned);owned.update(pid for pid,parent,rss,born in table if parent in owned);changed=len(owned)>before
                for pid,parent,rss,born in table:
                    if pid in owned:tracked[pid]=born
                rss=sum(rss for pid,parent,rss,born in table if tracked.get(pid)==born or pid==os.getpid())*1024;peak=max(peak,rss);samples+=1
                if rss>2*1024**3 or time.monotonic()-started>=float(os.environ.get('C5_WALL_CAP','140')):raise RuntimeError('C5 cap')
                time.sleep(.05)
        except BaseException:os.killpg(proc.pid,signal.SIGKILL);proc.wait();raise
    write('execution.json',{'returncode':proc.returncode,'elapsed_seconds':time.monotonic()-started,'peak_sampled_rss_bytes':peak,'samples':samples,'one_compute_worker':True,'rss_cap_bytes':2*1024**3,'cpu_affinity_enforced':False})
    snapshot=OUT/'source_snapshot';snapshot.mkdir()
    for p in Path(__file__).parent.glob('*.py'):(snapshot/p.name).write_bytes(p.read_bytes())
    write('sha256.json',{str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file()})
    assert sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())<100*1024**2
    return proc.returncode
if __name__=='__main__':sys.exit(child() if '--tests' in sys.argv else main())
