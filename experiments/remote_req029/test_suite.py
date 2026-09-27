"""Bounded REQ-029A inert suite; frozen REQ-028 source is fingerprinted, never edited."""
import json,os,subprocess,sys,time
from pathlib import Path
from feedback import FROZEN
from c6_protocol import sha,ROOT
from c6_ipc import publish
HERE=Path(__file__).resolve().parent

def inventory():
    paths=list(FROZEN.glob('*.py'))+list(FROZEN.glob('*.json'))+list(HERE.glob('*.py'))
    paths += [ROOT/'docs/req029a_feedback_correction_20260927.md',ROOT/'docs/scientific_audit_20260927.md',ROOT/'docs/experiment_protocol_v2.md']
    paths += list((ROOT/'docs/source_snapshots/req028_c6_mini').glob('*'))
    paths += [ROOT/'results/remote_req028/mechanics_c0_20260927/qwen/chat_template.jinja',
        ROOT/'results/remote_req028/mechanics_c0_20260927/qwen/prompt_1.json',
        ROOT/'docs/req028_c0_prompt_20260927.json',
        ROOT/'results/v2_agent/req011_competence_20260924/astropy__astropy-14598__small__req011__20260924T154501Z-fa905f/trajectory.json']
    return {str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted(paths) if p.is_file()}

def main():
    root=Path(sys.argv[1]).resolve();root.mkdir(parents=True,exist_ok=False)
    before=inventory();started=time.monotonic();samples=[];failure=None
    env=dict(os.environ,REQ029_FIXTURE_OUT=str(root/'fixtures'),OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1')
    with (root/'tests.log').open('xb') as log:
        p=subprocess.Popen([sys.executable,'-m','unittest','-v','tests'],cwd=HERE,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
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
