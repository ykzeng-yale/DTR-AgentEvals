"""REQ029S: scoped public-input reconciliation; no outcome parsing or execution."""
import io
import json
import time
from pathlib import Path
from exposure_delta import ROOT, sha, scan
from exposure_local_runs import selected_paths
from exposure_issue_markers import markers

TASK_SHA = '256173c0dcb9182396843c35c7cc1db528cb736ba1620b667c6aef73c9e3ece0'

def run():
    public = (ROOT/'docs/source_snapshots/req029s_public/public_task.json').read_bytes()
    assert sha(public) == TASK_SHA
    task = json.loads(public)
    assert set(task) == {'instance_id', 'base_commit', 'problem_statement'}
    needles = markers(task['problem_statement'])
    needles['canonical_id'] = task['instance_id'].encode()
    paths = set(selected_paths())
    paths.update((ROOT/'results/remote_req029/comparator_runtime').glob('*/controller/role/request/*.json'))
    account, records, deadline = [0], {}, time.monotonic()+60
    for p in sorted(paths):
        if p.is_symlink() or not p.is_file() or p.stat().st_size > 16*1024**2:
            raise ValueError('invalid selected record')
        raw = p.read_bytes()
        found = set(scan(io.BytesIO(raw), list(set(needles.values())), account, deadline))
        records[str(p.relative_to(ROOT))] = dict(sha256=sha(raw), bytes=len(raw),
            matches=[k for k,v in needles.items() if v.decode() in found])
    deps = [Path(__file__), ROOT/'experiments/lead_req029/exposure_delta.py',
        ROOT/'experiments/lead_req029/exposure_local_runs.py', ROOT/'experiments/lead_req029/exposure_issue_markers.py']
    return dict(public_task_sha256=TASK_SHA, source_hashes={str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in deps},
        markers={k:dict(bytes=len(v),sha256=sha(v)) for k,v in needles.items()},
        record_count=len(records),bytes_read=account[0],matched_records=sum(bool(v['matches']) for v in records.values()),records=records,
        scope='Local v2_agent development trajectories/requests, C6 controller requests and REQ029 comparator controller requests, including untracked records; bytes only.',
        limitations=['No remote-host reconciliation in this receipt.', 'Exact ID and selected public-issue raw/JSON encodings only; absence does not cover paraphrases, unlisted roots, unsupported encodings or pretraining.', 'No model dispatch, environment qualification, task selection or outcome interpretation.'])

if __name__ == '__main__':
    import sys
    result=run()
    with Path(sys.argv[1]).open('x') as f:
        json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({k:result[k] for k in ('record_count','bytes_read','matched_records')}))
