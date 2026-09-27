"""Serial fixture runner; preserve exact source/test receipt in a fresh directory."""
import json,os,subprocess,sys,time
from pathlib import Path
from exposure_reconcile_scan import ROOT,sha
def main():
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    files=sorted(Path(__file__).parent.glob('exposure_reconcile_*.py'))
    pins={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in files}
    for p in files:(out/p.name).write_bytes(p.read_bytes())
    with (out/'tests.log').open('xb') as log:
        r=subprocess.run([sys.executable,'-m','unittest','-v','exposure_reconcile_tests'],cwd=Path(__file__).parent,
            stdout=log,stderr=subprocess.STDOUT,timeout=15,
            env=dict(os.environ,OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',VECLIB_MAXIMUM_THREADS='1'))
    receipt=dict(returncode=r.returncode,elapsed_seconds=time.monotonic()-started,source_pins=pins,
        source_unchanged=pins=={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in files},actual_model_docker_evaluator=False)
    (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))
    sys.exit(r.returncode)
if __name__=='__main__':main()
