"""Bounded C4 regression run, immutable archive and no model execution."""
import hashlib,json,os,resource,signal,subprocess,sys,tarfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/remote_req028'/os.environ.get('C4_RUN_NAME','c4_setup_20260927')
def write(name,data):
    with (OUT/name).open('x') as f:json.dump(data,f,indent=2)
def child():
    resource.setrlimit(resource.RLIMIT_CPU,(140,140))
    os.environ.update(C3_FIXTURE_OUT=str(OUT/'c3_fixtures'),C3R_FIXTURE_OUT=str(OUT/'c3r_fixtures'),C4_FIXTURE_OUT=str(OUT/'c4_fixtures'))
    import unittest,c3r_tests,c4_tests
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m) for m in (c3r_tests,c4_tests))
    result=unittest.TextTestRunner(verbosity=2).run(suite);return 0 if result.wasSuccessful() else 1
def main():
    OUT.mkdir(parents=True,exist_ok=False);started=time.monotonic();peak=0;samples=0;tracked={}
    with (OUT/'tests.log').open('x') as log:
        child=subprocess.Popen([sys.executable,__file__,'--tests'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1'))
        try:
            while child.poll() is None:
                rows=subprocess.check_output(['ps','-axo','pid=,ppid=,rss=,lstart='],text=True,timeout=3);table=[]
                for row in rows.splitlines():
                    f=row.split(None,3)
                    if len(f)==4:table.append((*map(int,f[:3]),f[3]))
                owned={child.pid};changed=True
                while changed:
                    before=len(owned);owned.update(pid for pid,parent,rss,born in table if parent in owned);changed=len(owned)>before
                for pid,parent,rss,born in table:
                    if pid in owned:tracked[pid]=born
                rss=sum(rss for pid,parent,rss,born in table if tracked.get(pid)==born or pid==os.getpid())*1024;peak=max(peak,rss);samples+=1
                if rss>2*1024**3 or time.monotonic()-started>=float(os.environ.get('C4_WALL_CAP','140')):raise RuntimeError('C4 cap')
                time.sleep(.05)
        except BaseException:os.killpg(child.pid,signal.SIGKILL);child.wait();raise
    write('execution.json',{'returncode':child.returncode,'elapsed_seconds':time.monotonic()-started,'peak_sampled_rss_bytes':peak,'samples':samples,'rss_cap_bytes':2*1024**3,'wall_cap_seconds':float(os.environ.get('C4_WALL_CAP','140')),'one_compute_worker':True,'cpu_affinity_enforced':False})
    snapshot=OUT/'source_snapshot';snapshot.mkdir()
    for pattern in ('c4_*.py','c3r_*.py','c3_*.py'):
        for p in Path(__file__).parent.glob(pattern):(snapshot/p.name).write_bytes(p.read_bytes())
    write('dependencies.json',{name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ('guard.py','b3_stop.py','c2_relay.py','c2_git.py','a6r_gate.py','admission_window.py','mechanics_a6r.py','gguf_meta.py')})
    write('sha256.json',{str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file()})
    assert sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())<100*1024**2
    return child.returncode
if __name__=='__main__':sys.exit(child() if '--tests' in sys.argv else main())
