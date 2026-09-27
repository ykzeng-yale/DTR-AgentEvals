"""REQ-029C reference-only boundary. No old approval or model patch dependency."""
import json,re,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'remote_req028'
sys.path.insert(0,str(OLD))
from c6_protocol import ROOT,sha,require
from c6_sandbox_backend import DOCKER,IMAGE,ARCHIVE_SHA,ARCHIVE_BYTES
from c7_contract import BUNDLE,PINS,INPUT_SHA,OUTPUT_CAP,PATCH_CAP,git

REFERENCE=ROOT/'docs/source_snapshots/req029c_reference'
PATCH=REFERENCE/'reference.diff'
PATCH_SHA='867bc2472fb6f36b4bb180ae83d94b99533948f51c0f16f1e666dd87c9d4c396'
MODE='reference_positive_control'
PROTOCOL='REQ-029C'
MANIFEST_SHA='0349ca2efe272ebe537706e504f71cd4a8ef26dfda9be04ede19be1943af72b2'

def inputs(bundle=BUNDLE,patch=PATCH,reference=REFERENCE):
    require(sha((reference/'manifest.json').read_bytes())==MANIFEST_SHA,'reference manifest mismatch')
    manifest=json.loads((reference/'manifest.json').read_bytes())
    require(json.loads((bundle/'manifest.json').read_bytes())==PINS,'source manifest substitution')
    for name,pin in PINS.items():
        require(sha((bundle/name).read_bytes())==pin,'test/parser/rule source substitution: '+name)
    raw=patch.read_bytes()
    require(len(raw)==963 and sha(raw)==PATCH_SHA==manifest['reference_patch_sha256'],'reference patch mismatch')
    data=json.loads((bundle/'evaluation_inputs.json').read_bytes())
    require(sha(data['test_patch'].encode())==manifest['test_patch_sha256'],'test patch mismatch')
    require(manifest['c7_evaluation_inputs_sha256']==INPUT_SHA,'evaluation input mismatch')
    require(len(data['FAIL_TO_PASS'])==1 and len(data['PASS_TO_PASS'])==175 and
            len(set(data['FAIL_TO_PASS']+data['PASS_TO_PASS']))==176,'exact declared tests')
    return data,raw

def normalized(raw):
    # Ignore ONLY Git-added index metadata. Paths, hunk positions/context and
    # every modified byte remain exact. Other normalization fails closed.
    return b''.join(line for line in raw.splitlines(keepends=True)
                    if not re.fullmatch(rb'index [0-9a-f]+\.\.[0-9a-f]+(?: 100644)?\n',line))

def bind_prepared(facts,patch,data):
    diff=facts['candidate_diff'].encode()
    require(len(diff)<=PATCH_CAP and normalized(diff)==normalized(patch),'prepared source differs from reference')
    require(facts['candidate_sha256']==sha(patch)==PATCH_SHA,'helper reference binding')
    require(facts['test_patch_sha256']==sha(data['test_patch'].encode()),'helper test binding')
    require(facts['untouched_stock_harness'] is False,'offline environment binding')
    return diff

def inventory():
    paths=list(OLD.glob('*.py'))+list(OLD.glob('*.json'))+list(HERE.glob('reference_*.py'))
    paths+=list(BUNDLE.iterdir())+list(REFERENCE.iterdir())
    return {str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted(paths) if p.is_file()}

def authorize(commit,path,pin):
    require(re.fullmatch('[0-9a-f]{40}',commit) and re.fullmatch('[0-9a-f]{64}',pin),'approval identity')
    require(path.startswith('docs/req029c_') and path.endswith('.json') and '..' not in Path(path).parts,'REQ029C approval path')
    raw=git('show',commit+':'+path);require(sha(raw)==pin,'approval SHA');r=json.loads(raw)
    require(r['protocol']==PROTOCOL and r['execution_authorized'] is True,'REQ029C execution held')
    require(re.fullmatch('ref029c-[a-z0-9-]{1,60}',r['run_id']),'run namespace')
    now=time.time()
    require(now<r['expires_at']<=now+86400,'finite release expiry')
    require(r['reference_patch_sha256']==PATCH_SHA and r['reference_manifest_sha256']==MANIFEST_SHA and r['inputs_sha256']==INPUT_SHA,'frozen reference inputs')
    require('candidate_sha256' not in r,'not model candidate')
    require(r['modes']==[MODE] and r['sandbox_seconds']==600 and r['total_seconds']==600,'single fixed lease')
    require(r['source_hashes']==inventory(),'complete exact source inventory')
    require(re.fullmatch('[0-9a-f]{40}',r['source_commit']),'source commit')
    for name,digest in r['source_hashes'].items():
        require(sha(git('show',r['source_commit']+':'+name))==digest,'source commit differs')
    s=r['sandbox']
    require(s['docker_executable']==DOCKER and s['image']==IMAGE and s['archive_sha256']==ARCHIVE_SHA and s['archive_bytes']==ARCHIVE_BYTES,'W2R fixed assets')
    require(re.fullmatch('[0-9a-f]{64}',s['docker_sha256']),'Docker SHA')
    inputs()
    return r

def runtime(r):
    return ROOT/'results/local_req029/reference_runtime'/r['run_id']
