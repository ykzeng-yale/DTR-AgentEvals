"""REQ-029I exact Django-only, model-free approval and byte bindings."""
import ast,hashlib,json,re,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'remote_req028'
sys.path.insert(0,str(OLD))
from c6_protocol import ROOT,sha,require,put
from c6_sandbox_backend import LIMITS,RESERVE,DOCKER

PROTOCOL='REQ-029I'
TASK='django__django-16560'
DATASET_SHA='a45b1fe4e2f0c8390b2b2938ac83e92ed5979000856808f3679c07812e9e6dcd'
UPSTREAM_SOURCE='f7bbbb2ccdf479001d6467c9e34af59e44a840f9'
MODES=['baseline','reference']
BUNDLE=ROOT/'docs/source_snapshots/req029i_django'
MANIFEST_SHA='41207b50e9fbec3ac59e2642a2cecee79ce367c9558635b48cb752ee9d32da17'
INPUT_SHA='d724d01ea8f3aac9bbd161b6f2e7e489f82bbc7fa11dc51fe9652aad44e51e5d'
PATCH_SHA='3cfb9f5484180d2312eef8d498f60d6370c8670476cfc19c34110504e0070b39'
BASE='51c9bb7cd16081133af4f0ab6d06572660309730'
HEAD='becf6f8b613d4206f95411821ed66e5e0f428edc'
COMMAND='./tests/runtests.py --verbosity 2 --settings=test_sqlite --parallel 1 constraints.tests postgres_tests.test_constraints'
TEST_PATHS=['tests/constraints/tests.py','tests/postgres_tests/test_constraints.py']
OMITTED='python -m pip install -e .'
OUTPUT_CAP=4*1024**2
PATCH_CAP=1024**2
SANDBOX=dict(docker_executable=DOCKER,context='colima-dtr',
    image='sha256:935eeb9d7c960a90c1275d3d5a143c72173eecdf8098dacb164af1061f0c0a8f',
    original_config_sha256='86afcd19b6c56e5e271a1dfc62177cf03157fe9c9643be560db11480b317cb27',
    registry_manifest='sha256:0bafff953ce186aa261162d4091549fb4ad49df938900474b5f070d511bb1604',
    archive_path='work/local_req029/django_writable_20260927/testbed.tar',
    archive_sha256='36fdef54ff3e0ad4479fdf80e4ec44344e479cd166797bf637456c3bd6023252',
    archive_bytes=147826688,head=HEAD,base=BASE,import_module='django',
    python='/opt/miniconda3/envs/testbed/bin/python',limits=LIMITS)
def inputs(bundle=BUNDLE):
    require(sha((bundle/'manifest.json').read_bytes())==MANIFEST_SHA,'Django manifest substitution')
    pins=json.loads((bundle/'manifest.json').read_bytes())
    for name,pin in pins.items():
        require(sha((bundle/name).read_bytes())==pin,'Django bundle substitution: '+name)
    data=json.loads((bundle/'evaluation_inputs.json').read_bytes());patch=(bundle/'reference.diff').read_bytes()
    require(data['instance_id']==TASK and data['repo']=='django/django' and data['base_commit']==BASE,'task binding')
    require(sha((bundle/'evaluation_inputs.json').read_bytes())==INPUT_SHA,'input binding')
    require(len(patch)==10747 and sha(patch)==PATCH_SHA and len(data['test_patch'].encode())==11168,'patch binding')
    f,p=data['FAIL_TO_PASS'],data['PASS_TO_PASS']
    require(len(f)==8 and len(p)==66 and len(set(f+p))==74 and all('postgres_tests' not in t for t in f+p),'74 declared IDs')
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
        facts['import_path']=='/testbed/django/__init__.py','prepared task/import')
    require(facts['omitted_install']==OMITTED and facts['untouched_stock_harness'] is False and
        facts['test_command']==COMMAND and facts['test_paths']==TEST_PATHS,'prepared command binding')
    return diff

def inventory():
    # Conservative transitive pin: all frozen 028 modules, but never execute old launchers.
    paths=list(OLD.glob('*.py'))+list(OLD.glob('*.json'))+list(HERE.glob('django_eval_*.py'))+list(HERE.glob('django_eval_*.json'))+list(BUNDLE.iterdir())
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
    require(r['execution_authorized'] is True,'REQ029I execution HELD')
    require(type(r['run_id']) is str and re.fullmatch('dje029i-[a-z0-9-]{1,60}',r['run_id']),'new run namespace')
    require(type(r['expires_at']) in (int,float) and time.time()<r['expires_at']<=time.time()+86400,'absolute expiry')
    require(type(r['source_commit']) is str and re.fullmatch('[0-9a-f]{40}',r['source_commit']),'source commit')
    require(r['source_hashes']==inventory(),'exact complete source inventory')
    s=r['sandbox'];require(set(s)==set(expected['sandbox']),'exact sandbox fields')
    require({k:v for k,v in s.items() if k!='docker_sha256'}==SANDBOX,'Django qualified sandbox only')
    require(type(s['docker_sha256']) is str and re.fullmatch('[0-9a-f]{64}',s['docker_sha256']),'Docker SHA')
    return r

def authorize(commit,path,pin):
    require(re.fullmatch('[0-9a-f]{40}',commit) and re.fullmatch('[0-9a-f]{64}',pin),'approval identity')
    require(re.fullmatch(r'docs/req029i_[A-Za-z0-9_-]+\.json',path),'REQ029I approval namespace')
    raw=git('show',commit+':'+path);require(sha(raw)==pin,'exact approval byte SHA')
    r=validate(json.loads(raw))
    for name,digest in r['source_hashes'].items():
        require(sha(git('show',r['source_commit']+':'+name))==digest,'source commit mismatch: '+name)
    return r

def runtime(r):
    p=ROOT/'results/local_req029/django_eval_runtime'/r['run_id']
    require(p.resolve()==p,'runtime symlink');return p
