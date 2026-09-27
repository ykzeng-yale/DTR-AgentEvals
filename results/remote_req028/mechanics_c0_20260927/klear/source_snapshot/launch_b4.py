"""Launch only from a clean, already-published source revision; no outer admission."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
import guard
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/remote_req028/launch_b4_20260927'
def write(name,data):
    with (OUT/name).open('x') as f:json.dump(data,f,indent=2)
def main():
    head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    remote=subprocess.check_output(['git','ls-remote','origin','refs/heads/main'],cwd=ROOT,text=True).split()[0]
    assert head==remote,'source revision not published'
    sources=list(Path(__file__).parent.glob('*.py'))+[Path(__file__).with_name('b4_parser_source.json')]
    for p in sources:
        assert subprocess.check_output(['git','show',head+':'+str(p.relative_to(ROOT))],cwd=ROOT)==p.read_bytes(),'unpublished source'
    old={}
    for pid in (61372,61917,61920):
        r=subprocess.run(['ps','-p',str(pid),'-o','pid=,command='],capture_output=True,text=True)
        assert r.returncode!=0,('old PID live',pid);old[str(pid)]='absent'
    for directory in (ROOT/'results/remote_req028').glob('mechanics*'):
        for path in directory.glob('*.ownership.json'):
            assert not guard.same(json.loads(path.read_text())),('old owned process live',str(path))
        for path in directory.glob('*.watchdog_ready.json'):
            pid=json.loads(path.read_text())['pid']
            r=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True)
            assert r.returncode!=0 or not any(x in r.stdout for x in ('guard.py watch','b3_stop.py watch')),('old watchdog live',pid)
    from b4_protocol import parser_binding,retrospective
    parser_binding()
    audit=retrospective(ROOT/'results/remote_req028')
    OUT.mkdir(parents=True,exist_ok=False)
    write('B3_retrospective_parser.json',audit)
    tests=subprocess.run([sys.executable,'-m','unittest','test_guard','test_followup','test_admission','test_a4','test_a5','test_a6','test_a6r','test_b2','test_b2r','test_b3_stop','test_b3_contract','test_b4'],cwd=Path(__file__).parent,capture_output=True,text=True,env=dict(os.environ,B3_TEST_RECEIPTS=str(OUT/'cleanup_test_receipts')))
    write('tests.json',{'returncode':tests.returncode,'stdout':tests.stdout,'stderr':tests.stderr});assert tests.returncode==0
    snapshot=OUT/'source_snapshot';snapshot.mkdir();hashes={}
    for p in sources:
        data=p.read_bytes();(snapshot/p.name).write_bytes(data);hashes[p.name]=hashlib.sha256(data).hexdigest()
    write('publication.json',{'verified_at':time.time(),'source_commit':head,'remote_main':remote,'old_pids':old,'source_hashes':hashes})
    with (OUT/'driver.log').open('xb') as log:
        child=subprocess.Popen([sys.executable,str(Path(__file__).with_name('mechanics_b4.py'))],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
    receipt={'pid':child.pid,'identity':guard.ps(child.pid),'started':time.time(),'source_commit':head,'stage':'STATIC_SETUP','no_outer_admission_window':True}
    write('launch.json',receipt);print(json.dumps(receipt),flush=True)
if __name__=='__main__':main()
