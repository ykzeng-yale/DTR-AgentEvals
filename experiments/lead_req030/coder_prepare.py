"""Hash-locked acquisition; no model execution on preparation node."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request


def download(entry, destination, deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError('acquisition deadline')
    size = entry['size']
    h = hashlib.sha256()
    part = destination.with_suffix(destination.suffix + '.partial')
    total = 0
    with urllib.request.urlopen(entry['url'], timeout=30) as response, part.open('xb') as out:
        while True:
            if time.monotonic() >= deadline:
                raise TimeoutError('acquisition deadline')
            data = response.read(1024 * 1024)
            if not data:
                break
            total += len(data)
            if total > size:
                raise ValueError('oversize download')
            out.write(data)
            h.update(data)
    if total != size or h.hexdigest() != entry['sha256']:
        raise ValueError('download identity mismatch: ' + destination.name)
    part.rename(destination)
    return {'name': destination.name, 'bytes': total, 'sha256': h.hexdigest()}


def main():
    deadline = time.monotonic() + 2200
    Path('preparation.claim').open('x').close()
    wheels = json.loads(Path('coder_wheels.json').read_text())
    model = json.loads(Path('coder_model.json').read_text())
    assert sum(x['size'] for x in model['files']) < 70 * 1024**3
    Path('wheels').mkdir()
    Path('model').mkdir()
    receipts = []
    for e in wheels:
        receipts.append(download(e, Path('wheels') / e['filename'], deadline))
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--no-index', '--no-deps',
                    '--no-compile', '--target', 'packages', *map(str, Path('wheels').glob('*.whl'))], check=True, timeout=180)
    env = dict(os.environ, PYTHONPATH=str(Path('packages').resolve()) + ':' + os.environ.get('PYTHONPATH', ''))
    subprocess.run([sys.executable, '-c', 'import torch,transformers,accelerate; from transformers import AutoModelForCausalLM,AutoTokenizer; print(torch.__version__,transformers.__version__)'], env=env, check=True, timeout=120)
    for e in model['files']:
        receipts.append(download(e, Path('model') / e['filename'], deadline))
        print('verified', e['filename'], flush=True)
    Path('preparation.json').write_text(json.dumps(receipts, indent=2) + '\n')

if __name__ == '__main__':
    main()
