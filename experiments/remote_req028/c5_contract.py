"""Exact C5 development replay, manifest is NOT source activation approval."""
import json,subprocess,time
from pathlib import Path
from c2_relay import encode,sha,require,digest,commit_id
from c3_adapter import CONTRACT,CONFIG_SHA,validate_request
ROOT=Path(__file__).resolve().parents[2]
REQUEST_COMMIT='d8b78a64c25e84fe098858e75efc01319326c20a'
REQUEST_PATH='results/remote_req028/c5_request_20260927/request.json'
REQUEST_SHA='b1147b003808a776a0fe82694661fb7e5739eb79c7dd7318e8af6d44addfdf7a'
RELEASE_PATH='docs/req028_c5_release_manifest_20260927.json'
RELEASE_SHA='2aee738c9b1880fd44bd051c842c02a74a358dfaee5c7dd9e40f28a83088b4f5'
RESPONSE_PATH='results/remote_req028/c5_execution_20260927/response.json'
EXPIRY=1790506800.0
RENDER_SHA='66f0b398aa789e91bd70774766e5f11ebb9104d58fa0522edece465f22f5e26a'
TOKENS_SHA='725f0bb47be0690ab00e34379d703210985cd7df87e1fb6ec1cf47b1b02806c8'
ENTRY={'sequence':1,'commit':REQUEST_COMMIT,'path':REQUEST_PATH,'sha256':REQUEST_SHA}
def release(raw,now):
    require(sha(raw)==RELEASE_SHA,'exact release SHA');r=json.loads(raw)
    require(r=={'protocol':3,'run_id':'req028-c5-20260927','config_sha256':CONFIG_SHA,'deadline':EXPIRY,'max_calls':1,'parent_release_sha256':None,'requests':[ENTRY]},'exact release contract');require(now<EXPIRY,'C5 expired');return r
def request(raw,release_raw,now):
    r=release(release_raw,now);require(sha(raw)==REQUEST_SHA,'exact request SHA');return validate_request(raw,r,ENTRY,now)
def native_expected():
    p=ROOT/'results/remote_req028/mechanics_c0_20260927/qwen/prompt_1.json';data=json.loads(p.read_text())
    ids=data['token_ids'];rendered=data['rendered'];require(len(ids)==1530 and sha(rendered.encode())==RENDER_SHA and sha(json.dumps(ids).encode())==TOKENS_SHA,'independent C0 binding')
    return {'template_sha256':CONTRACT['template_sha256'],'native_exact':True,'rendered':rendered,'token_ids':ids}
def verify_native(binding):
    require(type(binding.get('rendered')) is str and type(binding.get('token_ids')) is list and all(type(i) is int for i in binding['token_ids']),'native token/render types')
    require(sha(binding['rendered'].encode())==RENDER_SHA and sha(json.dumps(binding['token_ids']).encode())==TOKENS_SHA,'actual returned native hashes')
    expected=native_expected();require(binding==expected,'C5 native binding differs from independent C0')
    return {'rendered_utf8_sha256':RENDER_SHA,'token_ids_default_json_sha256':TOKENS_SHA,'token_ids_canonical_c3_sha256':sha(encode(binding['token_ids'])),'tokens':1530,'binding_sha256':sha(encode(expected))}
def git(repo,*args,deadline=None):
    left=10 if deadline is None else min(10,deadline-time.time());require(left>0,'source read deadline')
    r=subprocess.run(['git',*args],cwd=repo,capture_output=True,timeout=left);require(r.returncode==0,'approval Git read failed');return r.stdout
def approval(repo,source_commit,approval_commit,approval_path,approval_sha,now):
    commit_id(source_commit);commit_id(approval_commit);digest(approval_sha)
    require(approval_path=='docs/req028_c5_source_approval_20260927.json','exact source approval path')
    raw=git(repo,'show',approval_commit+':'+approval_path);require(sha(raw)==approval_sha,'lead approval pin');a=json.loads(raw)
    expected={'permission':'execute_one_c5_request','approved_source_commit':source_commit,'release_manifest_sha256':RELEASE_SHA,'request_commit':REQUEST_COMMIT,'request_path':REQUEST_PATH,'request_sha256':REQUEST_SHA,'config_sha256':CONFIG_SHA,'response_path':RESPONSE_PATH,'expires_at':EXPIRY}
    require(set(a)==set(expected)|{'expected_main_policy'},'source approval fields')
    for k,v in expected.items():require(a[k]==v,'source approval '+k)
    require(a['expected_main_policy']=='exact-approval-commit','expected main policy');require(now<EXPIRY,'source approval expired')
    git(repo,'merge-base','--is-ancestor',source_commit,approval_commit)
    return dict(a,expected_main=approval_commit),raw
def source_pins(repo,commit,deadline=None):
    pins={};names=git(repo,'ls-tree','-r','--name-only',commit,'--','experiments/remote_req028',deadline=deadline).decode().splitlines()
    for name in names:
        if not name.endswith('.py'):continue
        raw=git(repo,'show',commit+':'+name,deadline=deadline);actual=(ROOT/name).read_bytes();require(raw==actual,'source differs from approved commit: '+name);pins[name]=sha(raw)
    require('experiments/remote_req028/c5_activate.py' in pins,'candidate source absent');return pins
