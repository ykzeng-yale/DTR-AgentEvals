"""Concrete disabled Matplotlib cell drafts. No evaluator reads or execution."""
import copy,json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments/remote_req029'))
from recovery_contract import disabled,model_contract,sha,encode,LIMITS,DOCKER
from matplotlib_prompt_boundary import build,ENVIRONMENT
TASK='matplotlib__matplotlib-20826'
BASE='a0d2e399729d36499a1924e5ca5bc067c8396810'
HEAD='ff9240ef159718098c76dfd53a317259848b135d'
MESSAGES_SHA='913dd9989766af3d148fce54912b38a0591f9ad55e681d9f56aaf0df44cfc040'
QUEUE_SHA='16d634965ee399a88f8b605778ed80dcaf2dc7b0bab4722d3fc0001a9bdfad07'
SANDBOX=dict(image='sha256:bf91db11a6e02de9ecababb891a08368cb5489c29f493197774148771dd8d24d',head=HEAD,
    archive_path='work/local_req029/matplotlib_writable_20260927/testbed.tar',
    archive_sha256='46ed7a0d26b126792cb796f776749907c901bcdcbfef30a72cc82a48ef02cb77',archive_bytes=478930944,
    import_module='matplotlib',python='/opt/miniconda3/envs/testbed/bin/python',docker_executable=DOCKER,
    docker_sha256=None,context='colima-dtr',qualified=False,qualification_sha256=None,
    limits=LIMITS,cleanup_reserve_seconds=15,archive_ownership='extracting-user')
def draft(arm,public_task_bytes):
    messages=build(public_task_bytes,ENVIRONMENT)
    if sha(messages)!=MESSAGES_SHA:raise ValueError('frozen Matplotlib message substitution')
    public=json.loads(public_task_bytes)
    if public['instance_id']!=TASK or public['base_commit']!=BASE:raise ValueError('task/base substitution')
    r=disabled();model=model_contract(arm)
    r.update(arm=arm,model=copy.deepcopy(model),config_sha256=sha(encode(model)),
        initial_messages_utf8=messages.decode(),initial_messages_sha256=MESSAGES_SHA,
        task=dict(task_id=TASK,base_commit=BASE,untouched_development=False,
                  exposure_ledger_sha256=None,queue_sha256=QUEUE_SHA),sandbox=copy.deepcopy(SANDBOX))
    return r

def verify_frozen_cell(r,public_task_bytes):
    """Pre-release check; does not authorize runtime or assert controls passed."""
    expected=draft(r['arm'],public_task_bytes)
    for key in ('protocol','arm','model','config_sha256','initial_messages_utf8','initial_messages_sha256',
                'caps','roles','action_contract_sha256','submission','evaluation_execution_authorized'):
        if r[key]!=expected[key]:raise ValueError('frozen field substitution: '+key)
    for key in ('task_id','base_commit','queue_sha256'):
        if r['task'][key]!=expected['task'][key]:raise ValueError('frozen task substitution: '+key)
    for key,value in SANDBOX.items():
        if key not in ('docker_sha256','qualified','qualification_sha256') and r['sandbox'][key]!=value:
            raise ValueError('frozen sandbox substitution: '+key)
    return True
