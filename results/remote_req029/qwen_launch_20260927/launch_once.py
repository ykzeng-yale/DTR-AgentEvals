"""One-shot dispatch receipt; does not observe admission or drive model turns."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'experiments/remote_req029'))
from comparator_launch import authorize, runtime_root

release = dict(release_commit='e5d6b7cc788d17c16edefb7fb24921f88e2726b3',
               release_path='docs/req029e_django_qwen_approval_20260927.json',
               release_sha='7708c2bd45725fc5ec6b16976940e12d9e5344be09469e7922f3317ea3d78b52')
r, pin = authorize(**release)
assert len(r['source_hashes']) == 166
assert r['worker_commit'] == '7aded9de243cf2c7271f82607baf2479d7ef7c99'
assert not runtime_root(r, 'worker').exists(), 'no restart/resume'
assert time.time() < r['expires_at'], 'expired release'
cmd = ['python3', 'experiments/remote_req029/comparator_launch.py', 'worker']
for key, value in release.items():
    cmd += ['--' + key.replace('_', '-'), value]
cmd += ['--relay-repo', str(ROOT)]
receipt = dict(release, command=cmd, cwd=str(ROOT), run_id=r['run_id'],
               source_commit=r['worker_commit'], verified_source_pins=166,
               expires_at=r['expires_at'], role='worker',
               scientific_success_assessed=False)
with (OUT / 'launch.claim.json').open('x') as f:
    json.dump(receipt, f, indent=2)
    f.flush()
    os.fsync(f.fileno())
with (OUT / 'worker.stdout.log').open('xb') as stdout, (OUT / 'worker.stderr.log').open('xb') as stderr:
    receipt['dispatch_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    p = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=stdout,
                         stderr=stderr, start_new_session=True)
receipt['pid'] = p.pid
identity = subprocess.run(['ps', '-p', str(p.pid), '-o', 'lstart=,command='],
                          capture_output=True, text=True, timeout=2)
receipt['initial_process_identity'] = identity.stdout.strip()
receipt['initial_identity_returncode'] = identity.returncode
receipt['stage'] = 'worker dispatched; setup/admission pending; inference not yet confirmed'
with (OUT / 'launch.receipt.json').open('x') as f:
    json.dump(receipt, f, indent=2)
    f.write('\n')
    f.flush()
    os.fsync(f.fileno())
print(json.dumps(receipt, indent=2))
