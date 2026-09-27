"""C7 immutable inputs and NEW source-only activation boundary. No C6 approval reuse."""
import ast,json,re,subprocess,time
from pathlib import Path
from c6_protocol import ROOT,HERE,sha,require
from c6_sandbox_backend import DOCKER,IMAGE,ARCHIVE_SHA,ARCHIVE_BYTES

BUNDLE=ROOT/'docs/source_snapshots/req028_c7'
PATCH=ROOT/'results/local_req028/c6b_terminal_20260927/submission.diff'
PATCH_SHA='c75f2db234217e402628445c66a0e2dfdfb20965bb34b9b6903d9c71462cf171'
INPUT_SHA='5da01753eddd7b91e911ae9d73f2b0b2ea23c33439cb926b47f4865405e6acfd'
PINS={'grading.py.txt':'88fc500ebaf692a53457149cec24dcf82dfa2d48f98021a894a087d275f61df4',
 'log_parsers.py.txt':'d04bc7bc1b7b598cde0365a38c1f1c5ea8f892bd1788d2e623678e320f84c012',
 'strict_rule.py.txt':'6738e12c8a8b8144cafd2898fdfc61c659d3b5129e2f7f4a6b28d95ad6b5e2e1',
 'evaluation_inputs.json':INPUT_SHA,'LICENSE':'2bd2e08df7147f67a69b42c10efae09bd4bf119df397371036187d5dd1b02f57',
 'python_parser.py.txt':'42f564edfee3c21751739bbf09d60cf3a3ecdc58ac5cf45717dc6b47a85d7459',
 'constants.py.txt':'c12fe2671fd8b7d8af8f5c711fceb2ca684254e2c1b4cde448422a44b8d04e35'}
OUTPUT_CAP=4*1024**2
PATCH_CAP=1024**2
OMITTED='python -m pip install -e .[test] --verbose'

def inputs(bundle=BUNDLE,patch=PATCH):
    require(json.loads((bundle/'manifest.json').read_bytes())==PINS,'source manifest substitution')
    for name,pin in PINS.items():require(sha((bundle/name).read_bytes())==pin,'test/parser/rule source substitution: '+name)
    raw=patch.read_bytes();require(len(raw)<=PATCH_CAP and sha(raw)==PATCH_SHA,'candidate patch mismatch')
    data=json.loads((bundle/'evaluation_inputs.json').read_bytes())
    require(len(data['FAIL_TO_PASS'])==1 and len(data['PASS_TO_PASS'])==175,'declared test count')
    require(len(set(data['FAIL_TO_PASS']+data['PASS_TO_PASS']))==176,'duplicate test IDs')
    return data,raw

def inventory():
    paths=list(HERE.glob('*.py'))+list(HERE.glob('*.json'))+list(BUNDLE.iterdir())+[PATCH]
    return {str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted(paths) if p.is_file()}

def git(*args):
    r=subprocess.run(['git',*args],cwd=ROOT,capture_output=True,timeout=30)
    require(r.returncode==0,'local approval Git read');return r.stdout

def authorize(commit,path,pin):
    require(re.fullmatch('[0-9a-f]{40}',commit) and re.fullmatch('[0-9a-f]{64}',pin),'approval identity')
    require(path.startswith('docs/req028_c7_') and path.endswith('.json') and '..' not in Path(path).parts,'C7 approval path')
    raw=git('show',commit+':'+path);require(sha(raw)==pin,'approval SHA')
    r=json.loads(raw)
    require(r['protocol']==7 and r['execution_authorized'] is True,'C7 execution held')
    require(re.fullmatch('c7-[a-z0-9-]{1,60}',r['run_id']),'run namespace')
    require(time.time()<r['expires_at'] and r['expires_at']-time.time()<=86400,'finite release expiry')
    require(r['candidate_sha256']==PATCH_SHA and r['inputs_sha256']==INPUT_SHA,'frozen evaluation inputs')
    require(r['modes']==['baseline','candidate'] and r['sandbox_seconds']==600 and r['total_seconds']==1200,'fixed serial budget')
    require(r['source_hashes']==inventory(),'complete exact source inventory')
    require(re.fullmatch('[0-9a-f]{40}',r['source_commit']),'source commit')
    for name,digest in r['source_hashes'].items():require(sha(git('show',r['source_commit']+':'+name))==digest,'source commit differs')
    s=r['sandbox']
    require(s['docker_executable']==DOCKER and s['image']==IMAGE and s['archive_sha256']==ARCHIVE_SHA and s['archive_bytes']==ARCHIVE_BYTES,'W2R fixed assets')
    require(re.fullmatch('[0-9a-f]{64}',s['docker_sha256']),'Docker SHA')
    inputs()
    return r

def runtime(r):return ROOT/'results/local_req028/c7_runtime'/r['run_id']
