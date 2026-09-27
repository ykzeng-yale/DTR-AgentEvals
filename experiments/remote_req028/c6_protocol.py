"""C6 data-only chain. No model, Git, shell, Docker, or evaluator execution here."""
import ast
import json
import os
import re
import time
from pathlib import Path

from c2_relay import encode, sha, require
from c3_adapter import CONTRACT, CONFIG_SHA
from c0_protocol import frozen_messages, analyze

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).parent
MINI = '04d809ceab9df28f9adaed044884180159172930'
YAML_SHA = '112aa58328f478a41cc2630702a4b89ef459e912870e05065157ed221f56701f'
ORIGIN = 'https://github.com/ykzeng-yale/DTR-AgentEvals.git'
IMAGE = 'sha256:ff1716c2ea207eeb3b717cd5deb3213f923f4d445234edd9a53d035dce834997'
HEAD = 'a4ae7a3808de3c53b0788875b6c97b20d5a12ee0'
SENTINEL = 'COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT'

def digest(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'digest')
    return value

def commit(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{40}', value), 'commit')
    return value

def initial():
    return frozen_messages(ROOT)['messages']

def put(root, name, value):
    """Exclusive durable file + directory barrier. An incomplete claim is never resumed."""
    root = Path(root)
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = value if type(value) is bytes else encode(value)
    with path.open('xb') as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return raw

def observation(output):
    """Exact frozen YAML template, not a paraphrase. Model sees role/content only."""
    from jinja2 import Template, StrictUndefined
    source = json.loads((HERE / 'b4_parser_source.json').read_text())
    yaml = source['config/default.yaml']
    require(sha(yaml.encode()) == YAML_SHA, 'observation source')
    block = yaml.split('  observation_template: |\n', 1)[1].split('  model_kwargs:', 1)[0]
    template = ''.join(line[4:] if line.startswith('    ') else line for line in block.splitlines(True))
    require(set(output) == {'output', 'returncode', 'exception_info'}, 'output schema')
    require(type(output['output']) is str and len(output['output'].encode()) <= 1024*1024, 'output cap')
    return {'role': 'user', 'content': Template(template, undefined=StrictUndefined).render(output=output)}

def release(raw, pin, now=None):
    require(sha(raw) == digest(pin), 'release SHA')
    r = json.loads(raw)
    require(set(r) == {'protocol','run_id','root','expires_at','worker_commit','controller_commit',
        'source_hashes','config_sha256','max_calls','max_actions','phase_seconds','delegation',
        'roles','sandbox','submission','evaluation','initial_messages_sha256'}, 'release keys')
    require(r['protocol'] == 6 and type(r['protocol']) is int, 'protocol')
    require(re.fullmatch('c6-[a-z0-9-]{1,64}', r['run_id']), 'run id')
    require(r['root'] == 'results/remote_req028/c6_runs/' + r['run_id'], 'run root')
    require(r['expires_at'] > (time.time() if now is None else now), 'expired release')
    require((r['max_calls'],r['max_actions'],r['phase_seconds']) == (24,24,1800), 'caps')
    require(r['config_sha256'] == CONFIG_SHA, 'config')
    require(r['initial_messages_sha256'] == sha(encode(initial())), 'initial messages')
    for key in ('worker_commit','controller_commit'):
        commit(r[key])
    require(r['roles'] == {'request':'controller','observation':'controller','response':'worker',
                         'preflight':'controller','ready':'worker','controller_terminal':'controller',
                         'worker_terminal':'worker'}, 'owners')
    require(r['delegation'] == {'controller_commit':r['controller_commit'],
        'rule':'append_exact_accepted_assistant_and_pinned_observation_only','sequences':[1,24]}, 'delegation')
    require(type(r['source_hashes']) is dict and r['source_hashes'], 'sources')
    for path, pin in r['source_hashes'].items():
        require(path.startswith('experiments/remote_req028/') and '..' not in Path(path).parts, 'source path')
        digest(pin)
    s = r['sandbox']
    require(s['image'] == IMAGE and s['head'] == HEAD and s['context'] == 'colima-dtr', 'sandbox identity')
    require(s['qualified'] is True and s['storage_enforced'] is True and
            s['controller_death_cleanup_qualified'] is True, 'unqualified sandbox')
    digest(s['qualification_sha256']); digest(s['adapter_sha256'])
    sub = r['submission']
    require(sub['revision'] == MINI and sub['yaml_sha256'] == YAML_SHA, 'mini source')
    digest(sub['docker_source_sha256']); digest(sub['checker_sha256'])
    for k in ('strict_source_sha256','config_sha256','task_manifest_sha256'):
        digest(r['evaluation'][k])
    require(r['evaluation']['execution_authorized'] is False, 'evaluation held')
    return r

def binding(b):
    require(set(b) == {'template_sha256','native_exact','rendered','token_ids'}, 'native fields')
    require(b['native_exact'] is True and b['template_sha256'] == CONTRACT['template_sha256'], 'native substitution')
    require(type(b['rendered']) is str and type(b['token_ids']) is list and b['token_ids'], 'native shape')
    require(all(type(i) is int and i >= 0 for i in b['token_ids']), 'token ids')
    require(len(b['token_ids']) + 1536 <= 32768, 'context overflow')
    return b

def rendered(messages):
    from jinja2 import Template
    template=(ROOT/'results/remote_req028/mechanics_c0_20260927/qwen/chat_template.jinja').read_text()
    require(sha(template.encode())==CONTRACT['template_sha256'],'local native source')
    return Template(template).render(messages=messages,tools=None,add_generation_prompt=True)

def bound_messages(native,messages):
    binding(native)
    require(native['rendered']==rendered(messages),'native render/message mismatch')
    if messages==initial():
        from c5_contract import native_expected
        require(native==native_expected(),'initial C0 native binding')
    return native

class Chain:
    def __init__(self, r, release_sha):
        self.r, self.pin = r, release_sha
        self.messages = initial()
        self.sequence = 1
        self.previous_response = self.previous_observation = None
        self.done = False

    def request(self, deadline):
        require(not self.done and self.sequence <= 24, 'terminal/cap')
        return dict(protocol=6, run_id=self.r['run_id'], release_sha256=self.pin,
            sequence=self.sequence, messages=self.messages, messages_sha256=sha(encode(self.messages)),
            previous_response_sha256=self.previous_response, previous_observation_sha256=self.previous_observation,
            config_sha256=CONFIG_SHA, controller_commit=self.r['controller_commit'], deadline=deadline)

    def check_request(self, q, deadline):
        require(q == self.request(deadline), 'request prefix/chain/config/source conflict')
        require(time.time() < deadline <= self.r['expires_at'], 'expired request')

    def response(self, q, request_object, native, raw, deadline, elapsed):
        self.check_request(q, deadline)
        bound_messages(native,q['messages'])
        return dict(protocol=6, run_id=self.r['run_id'], sequence=self.sequence,
            release_sha256=self.pin, request_sha256=sha(encode(q)), request_object=request_object,
            worker_commit=self.r['worker_commit'], config_sha256=CONFIG_SHA,
            native_binding=native, native_sha256=sha(encode(native)), raw=raw,
            raw_sha256=sha(raw.encode()), deadline=deadline, request_seconds=elapsed,
            request_seed=20260927028, effective_seed=20260927028 % (2**32))

    def accept(self, response, q, request_object, deadline):
        self.check_request(q, deadline)
        expected = self.response(q, request_object, response['native_binding'], response['raw'],
                                 deadline, response['request_seconds'])
        require(response == expected, 'response/source/native/config mismatch')
        require(0 <= response['request_seconds'] <= 180, 'request time')
        p = json.loads(response['raw'])
        require(len(p['choices']) == 1, 'one choice')
        u = p['usage']
        require(u['prompt_tokens'] == len(response['native_binding']['token_ids']), 'native usage')
        require(type(u['completion_tokens']) is int and 0 <= u['completion_tokens'] <= 1536, 'completion cap')
        choice = p['choices'][0]
        content = choice['message']['content']
        require(type(content) is str, 'content')
        gate = analyze(content, choice['finish_reason'])
        require(gate['interface_gate'], 'C0 gate')
        return content, gate['extracted_actions'][0]

    def advance(self, response, content, obs):
        require(not self.done and obs['role'] == 'user' and set(obs)=={'role','content'}, 'observation')
        self.messages = self.messages + [{'role':'assistant','content':content},obs]
        self.previous_response = sha(encode(response))
        self.previous_observation = sha(encode(obs))
        self.sequence += 1

def observation_envelope(r, pin, sequence, response_object, response, output):
    return dict(protocol=6, run_id=r['run_id'], release_sha256=pin, sequence=sequence,
        controller_commit=r['controller_commit'], response_object=response_object,
        response_sha256=sha(encode(response)), output=output, observation=observation(output))

def check_observation(value, r, pin, sequence, response_object, response):
    require(value == observation_envelope(r,pin,sequence,response_object,response,value['output']), 'observation binding')
    require(value['output']['returncode'] == 0 and not value['output']['exception_info'], 'command failure')
    return value['observation']
