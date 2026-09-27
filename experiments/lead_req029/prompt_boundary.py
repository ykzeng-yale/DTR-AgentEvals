"""Pinned public-task-only prompt construction. No evaluator imports or I/O."""
import hashlib,json
from pathlib import Path
from jinja2 import Template,StrictUndefined
BUNDLE=Path(__file__).resolve().parents[2]/'docs/source_snapshots/req029j_prompt'
TASK_SHA='7affd4e265f74b40093ea0caa4c2a17f12c2516540fa66cf14c521aabf001320'
TEMPLATES_SHA='5fe9452bafced0e321146116b20f65d31c6592ded0194b00e66b04fcb32f9e09'
def build(task_bytes,environment):
    if hashlib.sha256(task_bytes).hexdigest()!=TASK_SHA:raise ValueError('exact public task projection required')
    task=json.loads(task_bytes)
    if set(task)!={'instance_id','base_commit','problem_statement'}:raise ValueError('public columns only')
    if set(environment)!={'system','release','version','machine'}:raise ValueError('exact measured environment schema')
    if environment['system']!='Linux' or environment['machine']!='x86_64':raise ValueError('qualified container platform required')
    if not all(type(x) is str and 0<len(x)<=256 and '\n' not in x and '\r' not in x for x in environment.values()):raise ValueError('bounded environment fields')
    raw=(BUNDLE/'templates.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=TEMPLATES_SHA:raise ValueError('pinned upstream template')
    templates=json.loads(raw)
    variables=dict(environment,task=task['problem_statement'])
    messages=[{'role':role,'content':Template(templates[key],undefined=StrictUndefined).render(**variables)} for role,key in [('system','system_template'),('user','instance_template')]]
    return json.dumps(messages,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
