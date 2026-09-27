"""Bounded ID-only audit of local development trajectories and request records.

Does not parse outcomes or select tasks. Scopes exclude evaluator/reference data,
Git snapshots and held routing archives. Missing task IDs can evade this audit.
"""
import hashlib
import json
import subprocess
import time
from pathlib import Path
from exposure_delta import ROOT, PINS, scan, sha


def selected_paths(root=ROOT):
    agent = root / 'results/v2_agent'
    paths = set(agent.rglob('trajectory.json'))
    paths.update(agent.rglob('*.request.json'))
    paths.update((root / 'results/remote_req028/c6_runtime').glob('*/controller/role/request/*.json'))
    return sorted(p for p in paths if 'confirm' not in str(p.relative_to(root)).lower())


def run():
    inputs = {}
    for name, expected in PINS.items():
        raw = (ROOT / name).read_bytes()
        if sha(raw) != expected:
            raise ValueError('input pin mismatch: ' + name)
        inputs[name] = json.loads(raw)
    inventory = inputs[next(iter(PINS))]['exposure']
    queue = inputs[list(PINS)[1]]['queue']
    excluded = set(inventory['exclude_including_lead_rules'])
    needles = [x.encode() for x in queue]
    records = {}
    total = [0]
    deadline = time.monotonic() + 60
    for path in selected_paths():
        if path.is_symlink() or not path.is_file():
            raise ValueError('nonregular selected record')
        raw = path.read_bytes()
        if len(raw) > 16 * 1024**2:
            raise ValueError('16MiB record limit')
        import io
        hits = scan(io.BytesIO(raw), needles, total, deadline)
        records[str(path.relative_to(ROOT))] = {
            'sha256': sha(raw), 'bytes': len(raw), 'queue_id_mentions': hits}
    observed = sorted({x for r in records.values() for x in r['queue_id_mentions']})
    return {
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'script_sha256': sha(Path(__file__).read_bytes()), 'input_pins': PINS,
        'records': records, 'record_count': len(records), 'bytes_read': total[0],
        'queue_id_mentions': observed,
        'remaining_queue_mentions': [x for x in observed if x not in excluded],
        'scope': 'Local v2_agent trajectory.json and *.request.json plus untracked C6 controller role requests; tracked and untracked regular files, ID bytes only.',
        'limitations': ['No remote-host inventory in this audit.',
            'No inference about records lacking canonical task IDs, unsupported encodings or pretraining.',
            'Evaluator/reference artifacts and Git snapshots deliberately excluded; no task selection or execution.']}


if __name__ == '__main__':
    import sys
    result = run()
    with Path(sys.argv[1]).open('x') as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps({k: result[k] for k in ('record_count', 'bytes_read', 'queue_id_mentions', 'remaining_queue_mentions')}))
