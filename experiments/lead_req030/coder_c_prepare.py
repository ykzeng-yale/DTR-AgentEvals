"""New immutable environment; reuse verified old wheels and weights without mutation."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from coder_prepare import download


def main():
    Path('preparation.claim').open('x').close()
    old = Path('../req030-coder32-deploy-20260928-a').resolve()
    wheels = json.loads(Path('coder_c_wheels.json').read_text())
    Path('wheels').mkdir()
    receipts = []
    for e in wheels:
        target = Path('wheels') / e['filename']
        if e['package'] == 'numpy':
            receipts.append(download(e, target, time.monotonic()+120))
        else:
            origin = old / 'wheels' / e['filename']
            assert origin.stat().st_size == e['size']
            assert hashlib.sha256(origin.read_bytes()).hexdigest() == e['sha256']
            target.symlink_to(origin)
            receipts.append({'name':e['filename'],'sha256':e['sha256'],'bytes':e['size'],'reuse':True})
    subprocess.run([sys.executable,'-m','pip','install','--no-index','--no-deps','--no-compile','--target','packages',*map(str,Path('wheels').glob('*.whl'))],check=True,timeout=120)
    env=dict(os.environ,PYTHONPATH=str(Path('packages').resolve())+':'+os.environ.get('PYTHONPATH',''))
    code="import numpy as np,torch,transformers,accelerate; assert np.__version__=='1.26.4'; assert torch.from_numpy(np.array([1.,2.],dtype=np.float32)).numpy().tolist()==[1.,2.]; print(torch.__version__,np.__version__,transformers.__version__)"
    subprocess.run([sys.executable,'-c',code],env=env,check=True,timeout=120)
    assert (old/'coder_model.json').read_bytes()==Path('coder_model.json').read_bytes()
    Path('model').symlink_to(old/'model',target_is_directory=True)
    Path('preparation.json').write_text(json.dumps({'wheel_receipts':receipts,'bridge':'passed','model':'reused; inference rehashes every file'},indent=2)+'\n')

if __name__=='__main__': main()
