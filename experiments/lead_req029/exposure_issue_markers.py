"""Public-issue markers for a bounded local input-record reconciliation.

Does not parse model outcomes; absence is scoped to exact raw/JSON encodings.
"""
import io,json,time
from pathlib import Path
from exposure_delta import ROOT,sha,scan
from exposure_local_runs import selected_paths
from prompt_boundary import TASK_SHA

def markers(problem):
    raw=problem.encode('utf-8');assert len(raw)>=128
    spans={'full':raw,'first128':raw[:128],'middle128':raw[(len(raw)-128)//2:(len(raw)-128)//2+128],'last128':raw[-128:]}
    result={}
    for name,part in spans.items():
        # Exact task windows must be complete UTF8; never silently repair bytes.
        value=part.decode('utf-8')
        for encoding,b in [('raw',part),('json_ascii',json.dumps(value,ensure_ascii=True)[1:-1].encode()),('json_utf8',json.dumps(value,ensure_ascii=False)[1:-1].encode())]:
            result[name+'/'+encoding]=b
    return result

def run(out):
    public=(ROOT/'docs/source_snapshots/req029j_prompt/public_task.json').read_bytes()
    assert sha(public)==TASK_SHA
    needles=markers(json.loads(public)['problem_statement'])
    records={};account=[0];deadline=time.monotonic()+60
    for p in selected_paths():
        assert not p.is_symlink() and p.stat().st_size<=16*1024**2
        raw=p.read_bytes();found=set(scan(io.BytesIO(raw),list(set(needles.values())),account,deadline))
        records[str(p.relative_to(ROOT))]=dict(sha256=sha(raw),bytes=len(raw),marker_matches=[k for k,v in needles.items() if v.decode() in found])
    result=dict(script_sha256=sha(Path(__file__).read_bytes()),public_task_sha256=TASK_SHA,
        markers={k:dict(bytes=len(v),sha256=sha(v)) for k,v in needles.items()},records=records,
        record_count=len(records),bytes_read=account[0],matched_records=sum(bool(v['marker_matches']) for v in records.values()),
        scope='Same local development trajectory/request records as ID audit, including untracked C6 inputs. No outcomes deserialized.',
        limitations=['Exact public issue raw/JSON encodings only; paraphrases, compressed or differently normalized inputs not covered.',
        'Remote host and unlisted local run roots not covered; no universal untouchedness or pretraining claim.'])
    with Path(out).open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    return {k:result[k] for k in ('record_count','bytes_read','matched_records')}
if __name__=='__main__':
    import sys
    print(json.dumps(run(sys.argv[1])))
