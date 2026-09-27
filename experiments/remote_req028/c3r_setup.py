"""One-shot bounded C3R fixtures; no model execution or persistent service."""
import hashlib,json,os,resource,signal,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/remote_req028'/os.environ.get('C3R_RUN_NAME','c3r_setup_20260927')
def write(name,data):
    with (OUT/name).open('x') as f:json.dump(data,f,indent=2)
def child():
    resource.setrlimit(resource.RLIMIT_CPU,(290,290))
    os.environ['C3_FIXTURE_OUT']=str(OUT/'adapter_fixtures')
    os.environ['C3R_FIXTURE_OUT']=str(OUT/'integration_fixtures')
    import unittest,c3r_tests
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(c3r_tests))
    return 0 if result.wasSuccessful() else 1
def main():
    OUT.mkdir(exist_ok=False,parents=True)
    started=time.monotonic();peak=0;samples=0;tracked={}
    with (OUT/'tests.log').open('x') as log:
        process=subprocess.Popen([sys.executable,__file__,'--tests'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1'))
        try:
            while process.poll() is None:
                rows=subprocess.check_output(['ps','-axo','pid=,ppid=,rss=,lstart='],text=True,timeout=3)
                table=[]
                for row in rows.splitlines():
                    fields=row.split(None,3)
                    if len(fields)==4:table.append((*map(int,fields[:3]),fields[3]))
                owned={process.pid};changed=True
                while changed:
                    before=len(owned);owned.update(pid for pid,parent,rss,born in table if parent in owned);changed=len(owned)>before
                for pid,parent,rss,born in table:
                    if pid in owned:tracked[pid]=born
                rss=sum(rss for pid,parent,rss,born in table if tracked.get(pid)==born or pid==os.getpid())*1024;peak=max(peak,rss);samples+=1
                if rss>2*1024**3 or time.monotonic()-started>=float(os.environ.get('C3R_WALL_CAP','150')):raise RuntimeError('test resource/deadline cap')
                time.sleep(.05)
        except BaseException:
            os.killpg(process.pid,signal.SIGKILL);process.wait();raise
    write('test_execution.json',{'returncode':process.returncode,'elapsed_seconds':time.monotonic()-started,'peak_sampled_tree_rss_bytes':peak,'samples':samples,'wall_cap_seconds':float(os.environ.get('C3R_WALL_CAP','150')),'rss_cap_bytes':2*1024**3,'single_compute_worker':True,'fixture_only':True})
    from c3_adapter import CONTRACT,CONFIG_SHA
    write('contract.json',{'contract':CONTRACT,'canonical_sha256':CONFIG_SHA,'setup_only':True})
    snapshot=OUT/'source_snapshot';snapshot.mkdir()
    sources=list(Path(__file__).parent.glob('c3r_*.py'))+[Path(__file__).parent/n for n in ('c3_adapter.py','c3_tests.py','c3_fakes.py')]
    for source in sources:(snapshot/source.name).write_bytes(source.read_bytes())
    size=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file());assert size<=100*1024**2
    write('manifest.json',{'contract_sha256':CONFIG_SHA,'new_artifact_bytes_before_manifest':size,'fixture_only':True,'source_hashes':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in snapshot.iterdir()},'dependency_hashes':{name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ('b3_stop.py','guard.py','a6r_gate.py','mechanics_a6r.py','c2_relay.py','c2_git.py')},'limitations':'No weights loaded or real attestation executed. Fixed JSON/native-token fixture. RSS sampled, not a hard address-space limit; observed descendants remain tracked by PID/birth time after reparenting. Very short-lived unsampled processes may be missed. One compute worker, no OS CPU affinity enforcement. Fixture alarm is a last-resort 60-second bound.'})
    write('sha256.json',{str(p.relative_to(OUT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.rglob('*') if p.is_file()})
    return process.returncode
if __name__=='__main__':sys.exit(child() if '--tests' in sys.argv else main())
