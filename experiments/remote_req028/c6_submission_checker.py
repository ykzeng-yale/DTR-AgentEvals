"""Data-only exact pinned mini-swe submission semantics. Never initializes Docker.

Upstream copyright/license: docs/source_snapshots/req028_c6_mini/LICENSE.md.
"""
import ast,json,sys
from pathlib import Path
from c6_protocol import ROOT,sha,require,put
DOCKER_SHA='21d389122b008e7b743d1e640207fda0b08d9010cf6323ddd02f0742b33b96a6'
LICENSE_SHA='0f796e58f91d1c07bb2c1b1d0f8bf3a83017c3a5dec1bdc6fae733b2cd2e875b'

def verify_source():
    folder=ROOT/'docs/source_snapshots/req028_c6_mini'
    raw=(folder/'docker.py.txt').read_bytes()
    require(sha(raw)==DOCKER_SHA,'pinned submission source')
    require(sha((folder/'LICENSE.md').read_bytes())==LICENSE_SHA,'upstream license pin')
    return raw

def check(output):
    verify_source()
    require(type(output['output']) is str and type(output['returncode']) is int,'submission data')
    lines=output['output'].lstrip().splitlines(keepends=True)
    submitted=bool(lines and lines[0].strip()=='COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT' and output['returncode']==0)
    payload=''.join(lines[1:]) if submitted else None
    return dict(submitted=submitted,submitted_payload=payload,
        upstream_exit_message=None if not submitted else {'role':'exit','content':payload,
            'extra':{'exit_status':'Submitted','submission':payload}},docker_source_sha256=DOCKER_SHA)

def main(path):
    s=json.loads(Path(path).read_text())
    require(s['operation']=='check_submission','data-only checker')
    require(s['submission']['docker_source_sha256']==DOCKER_SHA,'release submission pin')
    out=Path(s['output_path']);put(out.parent,out.name,check(s['payload']))

if __name__=='__main__':main(sys.argv[1])
