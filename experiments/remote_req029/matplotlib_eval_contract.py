"""REQ-029W exact Matplotlib-only, model-free approval and byte bindings."""
import ast,hashlib,json,re,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'remote_req028'
sys.path.insert(0,str(OLD))
from c6_protocol import ROOT,sha,require,put
from c6_sandbox_backend import LIMITS,RESERVE,DOCKER

PROTOCOL='REQ-029W'
TASK='matplotlib__matplotlib-20826'
DATASET_SHA='a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd'
UPSTREAM_SOURCE='f7bbbb2ccdf479001d6467c9e34af59e44a840f9'
MODES=['baseline','reference']
BUNDLE=ROOT/'docs/source_snapshots/req029w_matplotlib_eval'
MANIFEST_SHA='3add0498a93b3f171e453f5802fdc3fa03fe84bcd9eeb82795ef36afe1662733'
INPUT_SHA='8dc564c8dcf57c260d6488b64ab58e9c7a8853251aa0b359450b73c5ff39a9e9'
PATCH_SHA='95b743f7c62be8994b7afc0d3c3fe4ba4362baf39ab0c91f31ac26e97550ce7f'
BASE='a0d2e399729d36499a1924e5ca5bc067c8396810'
HEAD='ff9240ef159718098c76dfd53a317259848b135d'
COMMAND='pytest -rA lib/matplotlib/tests/test_axes.py'
TEST_PATHS=['lib/matplotlib/tests/test_axes.py']
OMITTED='python -m pip install -e .'
OUTPUT_CAP=4*1024**2
PATCH_CAP=1024**2
SANDBOX=dict(docker_executable=DOCKER,context='colima-dtr',
    image='sha256:bf91db11a6e02de9ecababb891a08368cb5489c29f493197774148771dd8d24d',
    original_config_sha256='1e941854c2a74b04f1e9ecbbccdf8ac8273dddb0fb666a1e86d2fd5dee3dcaf0',
    registry_manifest='sha256:7ae350b0a6b3fe3cc4165ac10b81dbdcace7a65b8a608988043611a05473e3ef',
    archive_path='work/local_req029/matplotlib_writable_20260927/testbed.tar',
    archive_sha256='46ed7a0d26b126792cb796f776749907c901bcdcbfef30a72cc82a48ef02cb77',
    archive_bytes=478930944,head=HEAD,base=BASE,import_module='matplotlib',
    python='/opt/miniconda3/envs/testbed/bin/python',limits=LIMITS,archive_ownership='extracting-user')
def inputs(bundle=BUNDLE):
    require(sha((bundle/'manifest.json').read_bytes())==MANIFEST_SHA,'Matplotlib manifest substitution')
    pins=json.loads((bundle/'manifest.json').read_bytes())
    for name,pin in pins.items():
        require(sha((bundle/name).read_bytes())==pin,'Matplotlib bundle substitution: '+name)
    data=json.loads((bundle/'evaluation_inputs.json').read_bytes());patch=(bundle/'reference.diff').read_bytes()
    require(data['instance_id']==TASK and data['repo']=='matplotlib/matplotlib' and data['base_commit']==BASE,'task binding')
    require(sha((bundle/'evaluation_inputs.json').read_bytes())==INPUT_SHA,'input binding')
    require(len(patch)==774 and sha(patch)==PATCH_SHA and len(data['test_patch'].encode())==798,'patch binding')
    f,p=data['FAIL_TO_PASS'],data['PASS_TO_PASS']
    require(len(f)==1 and len(p)==673 and len(set(f+p))==674,'674 declared IDs')
    require(data['test_command']==COMMAND and data['install_command']==OMITTED and data['eval_commands']==[],'command binding')
    require(re.findall(r'^diff --git a/\S+ b/(\S+)$',data['test_patch'],re.M)==TEST_PATHS,'test reset paths')
    return data,patch,pins

def normalized(raw):
    lines=[]
    for line in raw.splitlines(keepends=True):
        if re.fullmatch(rb'index [0-9a-f]+\.\.[0-9a-f]+(?: 100644)?\n',line):continue
        h=re.fullmatch(rb'(@@ -[0-9]+(?:,[0-9]+)? \+[0-9]+(?:,[0-9]+)? @@)(?: [^\r\n]*)?(\n?)',line)
        lines.append(h[1]+h[2] if h else line)
    return b''.join(lines)

def bind_prepared(facts,mode):
    require(mode in MODES,'fixed arm');data,patch,_=inputs()
    diff=facts['source_diff'].encode()
    expected=b'' if mode=='baseline' else patch
    require(len(diff)<=PATCH_CAP and normalized(diff)==normalized(expected),'prepared source diff binding')
    require(facts['mode']==mode and facts['reference_patch_sha256']==PATCH_SHA and
        facts['test_patch_sha256']==sha(data['test_patch'].encode()),'prepared patch binding')
    require(facts['head']==HEAD and facts['base']==BASE and facts['python']==SANDBOX['python'] and
        facts['import_path']=='/testbed/lib/matplotlib/__init__.py','prepared task/import')
    require(facts['omitted_install']==OMITTED and facts['untouched_stock_harness'] is False and
        facts['test_command']==COMMAND and facts['test_paths']==TEST_PATHS,'prepared command binding')
    return diff

def inventory():
    # Conservative transitive pin: all frozen 028 modules, but never execute old launchers.
    paths=list(OLD.glob('*.py'))+list(OLD.glob('*.json'))+list(HERE.glob('matplotlib_eval_*.py'))+list(HERE.glob('matplotlib_eval_*.json'))+list(BUNDLE.iterdir())
    return {str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted(paths) if p.is_file()}

def git(*args):
    p=subprocess.run(['git',*args],cwd=ROOT,capture_output=True,timeout=30)
    require(p.returncode==0,'approval Git read');return p.stdout

def template():
    data,_,pins=inputs()
    return dict(protocol=PROTOCOL,execution_authorized=False,run_id=None,expires_at=0,
        task=TASK,modes=MODES,model_free=True,dataset_sha256=DATASET_SHA,upstream_source_path=UPSTREAM_SOURCE,
        manifest_sha256=MANIFEST_SHA,inputs_sha256=INPUT_SHA,
        reference_patch_sha256=PATCH_SHA,test_patch_sha256=sha(data['test_patch'].encode()),
        strict_rule_sha256=pins['strict_rule.py.txt'],command=COMMAND,omitted_install=OMITTED,
        sandbox_seconds=600,total_seconds=1200,cleanup_seconds=15,output_cap=OUTPUT_CAP,patch_cap=PATCH_CAP,
        source_commit=None,source_hashes={},sandbox=dict(SANDBOX,docker_sha256=None))

def validate(r):
    expected=template()
    require(set(r)==set(expected),'exact approval fields')
    for k,v in expected.items():
        if k not in ('execution_authorized','run_id','expires_at','source_commit','source_hashes','sandbox'):
            require(r[k]==v,'approval substitution: '+k)
    require(r['execution_authorized'] is True,'REQ029W execution HELD')
    require(type(r['run_id']) is str and re.fullmatch('mpe029w-[a-z0-9-]{1,60}',r['run_id']),'new run namespace')
    require(type(r['expires_at']) in (int,float) and time.time()<r['expires_at']<=time.time()+86400,'absolute expiry')
    require(type(r['source_commit']) is str and re.fullmatch('[0-9a-f]{40}',r['source_commit']),'source commit')
    require(r['source_hashes']==inventory(),'exact complete source inventory')
    s=r['sandbox'];require(set(s)==set(expected['sandbox']),'exact sandbox fields')
    require({k:v for k,v in s.items() if k!='docker_sha256'}==SANDBOX,'Matplotlib qualified sandbox only')
    require(type(s['docker_sha256']) is str and re.fullmatch('[0-9a-f]{64}',s['docker_sha256']),'Docker SHA')
    return r

def authorize(commit,path,pin):
    require(re.fullmatch('[0-9a-f]{40}',commit) and re.fullmatch('[0-9a-f]{64}',pin),'approval identity')
    require(re.fullmatch(r'docs/req029w_[A-Za-z0-9_-]+\.json',path),'REQ029W approval namespace')
    raw=git('show',commit+':'+path);require(sha(raw)==pin,'exact approval byte SHA')
    r=validate(json.loads(raw))
    for name,digest in r['source_hashes'].items():
        require(sha(git('show',r['source_commit']+':'+name))==digest,'source commit mismatch: '+name)
    return r

def runtime(r):
    p=ROOT/'results/local_req029/matplotlib_eval_runtime'/r['run_id']
    require(p.resolve()==p,'runtime symlink');return p
