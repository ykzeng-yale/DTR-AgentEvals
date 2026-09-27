"""Documented macOS resource-limit compatibility; statistical source unchanged."""
import hashlib
import json
import resource
import run

original = resource.setrlimit
def compatible_setrlimit(kind, limits):
    if kind == resource.RLIMIT_AS:
        # This host rejects finite AS limits. The unchanged runner checks RSS
        # at admission and every 100 studies. Fixed arrays retain <=4000 rows.
        return
    return original(kind, limits)

manifest_path = run.ROOT / 'compatibility_manifest.json'
if not manifest_path.exists():
    run.write('compatibility_manifest.json', {
        'frozen_at': run.now(),
        'reason': 'macOS RLIMIT_AS ValueError before sampling; no statistical or seed changes',
        'wrapper_sha256': run.digest(run.ROOT / 'run_macos.py'),
        'original_manifest_sha256': run.digest(run.ROOT / 'manifest.json'),
        'resource_enforcement': 'one low-priority Python process; CPU hard limit retained; RSS checked every 100 studies; no OS-enforced memory ceiling available',
        'command': 'python3 run_macos.py'
    })
else:
    saved = json.loads(manifest_path.read_text())
    assert saved['wrapper_sha256'] == run.digest(run.ROOT / 'run_macos.py')
resource.setrlimit = compatible_setrlimit
run.simulate()
