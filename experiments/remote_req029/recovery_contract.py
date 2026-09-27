"""REQ-029O immutable comparator contract; disabled task manifests never launch."""
import copy,json,re,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
OLD=HERE.parent/'remote_req028'
sys.path.insert(0,str(OLD))
sys.path.insert(0,str(HERE.parent/'lead_req029'))
from c6_protocol import encode,sha,require,digest,commit,put,MINI,YAML_SHA
from c0_protocol import ARMS,native_template
from c3_adapter import CONTRACT as OLD_CONFIG
from c6_sandbox_backend import LIMITS,DOCKER
PROTOCOL='REQ-029O'
PARSER_SHA='720799e7fa8f9e346a561b40de7a893e146b209dfbd8273fb4ca045c4338589a'
ASSETS=json.loads((HERE/'comparator_assets.json').read_bytes())
CAPS=dict(max_calls=24,max_actions=24,phase_seconds=1800,setup_seconds=300,
          admission_seconds=900,admission_reads=31,load_seconds=180,request_seconds=180,
          action_seconds=60,output_bytes=1048576,cleanup_seconds=15)
ROLES={'request':'controller','observation':'controller','response':'worker',
       'preflight':'controller','ready':'worker','controller_terminal':'controller','worker_terminal':'worker'}

def model_contract(arm):
    require(arm in ARMS and ASSETS['arms']==ARMS,'exact two artifacts')
    a=ARMS[arm]
    cfg=dict(OLD_CONFIG,model_sha256=a['sha256'],template_sha256=a['template_sha'],
             cache_k=a['cache'],cache_v=a['cache'])
    return dict(arm=arm,artifact=a,runner_revision=ASSETS['runner_revision'],
                runner_archive_sha256=ASSETS['runner_archive_sha256'],
                runner_binary_hashes=ASSETS['runner_binary_hashes'],config=cfg)

def messages(r):
    raw=r['initial_messages_utf8']
    require(type(raw) is str and len(raw.encode())<=1048576 and sha(raw.encode())==r['initial_messages_sha256'],'initial message bytes')
    m=json.loads(raw)
    require(type(m) is list and len(m)==2 and [x['role'] for x in m]==['system','user'] and
            all(set(x)=={'role','content'} and type(x['content']) is str and x['content'] for x in m),'initial system/user')
    return m

def cell(r):
    return dict(arm=r['arm'],task_id=r['task']['task_id'],task_sha256=sha(encode(r['task'])),
                model_sha256=sha(encode(r['model'])),initial_messages_sha256=r['initial_messages_sha256'],
                assignment='deterministic_always_artifact',propensity=None)

def validate(r,now=None):
    require(type(r) is dict and set(r)==set(disabled()),'exact comparator release schema')
    require(r['protocol']==PROTOCOL and r['execution_authorized'] is True,'REQ029O execution held')
    require(re.fullmatch('cmp029o-[a-z0-9-]{1,64}',r['run_id']),'comparator namespace')
    require(r['root']=='results/remote_req029/comparator_runs/'+r['run_id'],'comparator root')
    now=time.time() if now is None else now
    require(now<r['expires_at']<=now+86400,'finite expiry')
    require(r['caps']==CAPS and r['roles']==ROLES,'caps/role ownership')
    require(r['model']==model_contract(r['arm']),'arm/model/cache/template/runner substitution')
    require(r['config_sha256']==sha(encode(r['model'])),'model config binding')
    require(r['action_contract_sha256']==PARSER_SHA and sha((HERE.parent/'lead_req029/action_contract.py').read_bytes())==PARSER_SHA,'common parser pin')
    t=r['task'];require(set(t)=={'task_id','base_commit','untouched_development','exposure_ledger_sha256','queue_sha256'},'task schema')
    require(re.fullmatch('[A-Za-z0-9_.-]+__[A-Za-z0-9_.-]+-[0-9]+',t['task_id']) and t['task_id']!='astropy__astropy-14598','untouched task ID')
    require(t['untouched_development'] is True,'task release held')
    commit(t['base_commit']);digest(t['exposure_ledger_sha256']);digest(t['queue_sha256'])
    messages(r)
    s=r['sandbox']
    require(set(s)=={'image','head','archive_path','archive_sha256','archive_bytes','import_module','python',
        'docker_executable','docker_sha256','context','qualified','qualification_sha256','limits','cleanup_reserve_seconds','archive_ownership'},'sandbox schema')
    require(re.fullmatch('sha256:[0-9a-f]{64}',s['image']) and re.fullmatch('[A-Za-z_][A-Za-z0-9_.]*',s['import_module']),'task image/import')
    require(s['archive_ownership']=='extracting-user','explicit archive ownership policy')
    commit(s['head']);digest(s['archive_sha256']);digest(s['qualification_sha256']);digest(s['docker_sha256'])
    require(s['archive_path'].startswith('work/local_req029/') and '..' not in Path(s['archive_path']).parts and
            type(s['archive_bytes']) is int and s['archive_bytes']>0,'qualified task archive')
    require(s['python']=='/opt/miniconda3/envs/testbed/bin/python' and s['docker_executable']==DOCKER and
            s['context']=='colima-dtr' and s['limits']==LIMITS and s['qualified'] is True and s['cleanup_reserve_seconds']==15,'qualified W2R boundary')
    require(r['evaluation_execution_authorized'] is False,'evaluation held')
    digest(r['transport_config_sha256'])
    for k in ('worker_commit','controller_commit'):commit(r[k])
    require(r['worker_commit']==r['controller_commit'],'one exact source')
    require(r['submission']==dict(revision=MINI,yaml_sha256=YAML_SHA),'submission source')
    return r

def inventory():
    paths=list(OLD.glob('*.py'))+list(OLD.glob('*.json'))+list(HERE.glob('comparator_*.py'))+list(HERE.glob('comparator_*.json'))
    paths+=list(HERE.glob('recovery_*.py'))
    paths+=[HERE/'feedback.py',HERE.parent/'lead_req029/action_contract.py']
    return {str(p.relative_to(ROOT)):sha(p.read_bytes()) for p in sorted(paths)}

def template(arm):
    raw=ASSETS['templates'][arm]
    require(sha(raw.encode())==ARMS[arm]['template_sha'],'native template bytes')
    return raw

def bound_messages(native,history,r):
    require(set(native)=={'arm','template_sha256','template_relation','native_exact','rendered','token_ids','messages_sha256'},'native schema')
    require(native['arm']==r['arm'] and native['native_exact'] is True and native['template_sha256']==ARMS[r['arm']]['template_sha'],'native arm/template')
    served=template(r['arm'])
    if r['arm']=='klear':served=served[:-1]
    require(native['template_relation']==native_template(r['arm'],served,template(r['arm'])),'served template relation')
    require(native['messages_sha256']==sha(encode(history)),'native full history')
    require(type(native['rendered']) is str and native['rendered']==rendered(history,r['arm']),'native render/message mismatch')
    ids=native['token_ids']
    require(type(ids) is list and ids and all(type(i) is int and i>=0 for i in ids),'native token IDs')
    require(len(ids)+1536<=32768,'context overflow')
    return native

def rendered(history,arm):
    from jinja2 import Environment
    env=Environment()
    def fail(msg):raise ValueError(msg)
    env.globals['raise_exception']=fail
    return env.from_string(template(arm)).render(messages=history,tools=None,add_generation_prompt=True)

def disabled():
    # No concrete task, image, archive, prompt or approval can be inferred here.
    return dict(protocol=PROTOCOL,execution_authorized=False,run_id=None,root=None,expires_at=0,
        arm=None,model=None,config_sha256=None,task=None,sandbox=None,
        initial_messages_utf8=None,initial_messages_sha256=None,
        action_contract_sha256=PARSER_SHA,caps=CAPS,roles=ROLES,worker_commit=None,controller_commit=None,
        source_hashes=None,submission=dict(revision=MINI,yaml_sha256=YAML_SHA),evaluation_execution_authorized=False,transport_config_sha256=None)
