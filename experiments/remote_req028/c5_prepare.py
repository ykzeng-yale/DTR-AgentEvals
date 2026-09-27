"""Preparation receipt only, no launch, sampling, remote fetch or model invocation."""
import json
from pathlib import Path
from c2_relay import encode,sha
from c5_contract import *
def main(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    manifest=(ROOT/RELEASE_PATH).read_bytes();raw=git(ROOT,'show',REQUEST_COMMIT+':'+REQUEST_PATH);q=request(raw,manifest,__import__('time').time());native=verify_native(native_expected())
    schema={'permission':'execute_one_c5_request','approved_source_commit':'PUBLISHED_CANDIDATE_SOURCE_COMMIT','release_manifest_sha256':RELEASE_SHA,'request_commit':REQUEST_COMMIT,'request_path':REQUEST_PATH,'request_sha256':REQUEST_SHA,'config_sha256':CONFIG_SHA,'response_path':RESPONSE_PATH,'expires_at':EXPIRY,'expected_main_policy':'exact-approval-commit'}
    receipt={'stage':'PREPARATION_ONLY_STOP_FOR_EXACT_SOURCE_APPROVAL','activation_authorized_now':False,'command_argv':['python3','experiments/remote_req028/c5_activate.py','--source-commit','PUBLISHED_CANDIDATE_SOURCE_COMMIT','--approval-commit','LEAD_APPROVAL_COMMIT','--approval-sha','LEAD_APPROVAL_FILE_SHA256'],'approval_path':'docs/req028_c5_source_approval_20260927.json','approval_schema':schema,'source_base':git(ROOT,'rev-parse','HEAD').decode().strip(),'request_commit':REQUEST_COMMIT,'request_path':REQUEST_PATH,'request_sha256':sha(raw),'release_manifest_sha256':sha(manifest),'request_messages_sha256':q['messages_sha256'],'independent_native':native,'response_path':RESPONSE_PATH,'expiry_utc':'2026-09-27T11:00:00Z','model_invoked':False,'source_hashes':{str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in Path(__file__).parent.glob('*.py')}}
    with (out/'command_receipt.json').open('x') as f:json.dump(receipt,f,indent=2)
    print(json.dumps({'receipt':str(out/'command_receipt.json'),'model_invoked':False,'activation_authorized_now':False}))
if __name__=='__main__':
    import sys
    main(sys.argv[1])
