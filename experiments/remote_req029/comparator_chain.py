"""Task/arm-bound complete-history chain; common reviewed action contract."""
import json,time
from comparator_contract import *
from action_contract import parse_complete
from feedback import completed,submitted,SEMANTICS
from c6_protocol import observation
class Chain:
    def __init__(self, r, release_sha):
        self.r, self.pin = r, release_sha
        self.messages = messages(r)
        self.sequence = 1
        self.previous_response = self.previous_observation = None
        self.done = False

    def request(self, deadline):
        require(not self.done and self.sequence <= 24, 'terminal/cap')
        return dict(protocol=PROTOCOL, run_id=self.r['run_id'], release_sha256=self.pin,
            sequence=self.sequence, messages=self.messages, messages_sha256=sha(encode(self.messages)),
            previous_response_sha256=self.previous_response, previous_observation_sha256=self.previous_observation,
            config_sha256=self.r['config_sha256'], cell=cell(self.r), controller_commit=self.r['controller_commit'], deadline=deadline)

    def check_request(self, q, deadline):
        require(q == self.request(deadline), 'request prefix/chain/config/source conflict')
        require(time.time() < deadline <= self.r['expires_at'], 'expired request')

    def response(self, q, request_object, native, raw, deadline, elapsed):
        self.check_request(q, deadline)
        bound_messages(native,q['messages'],self.r)
        return dict(protocol=PROTOCOL, run_id=self.r['run_id'], sequence=self.sequence,
            release_sha256=self.pin, request_sha256=sha(encode(q)), request_object=request_object,
            worker_commit=self.r['worker_commit'], config_sha256=self.r['config_sha256'], cell=cell(self.r),
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
        require(all(type(u.get(k)) is int and u[k]>=0 for k in ('prompt_tokens','completion_tokens','total_tokens')),'integer usage')
        require(u['prompt_tokens'] == len(response['native_binding']['token_ids']), 'native usage')
        require(type(u['completion_tokens']) is int and 0 <= u['completion_tokens'] <= 1536, 'completion cap')
        choice = p['choices'][0]
        content = choice['message']['content']
        require(type(content) is str, 'content')
        parsed=parse_complete(content,choice['finish_reason'])
        require(u.get('total_tokens')==u['prompt_tokens']+u['completion_tokens'],'total usage')
        return parsed['raw_content'],parsed['command']

    def advance(self, response, content, obs):
        require(not self.done and obs['role'] == 'user' and set(obs)=={'role','content'}, 'observation')
        self.messages = self.messages + [{'role':'assistant','content':content},obs]
        self.previous_response = sha(encode(response))
        self.previous_observation = sha(encode(obs))
        self.sequence += 1

def observation_envelope(r,pin,sequence,response_object,response,output):
    completed(output)
    return dict(protocol=PROTOCOL,cell=cell(r),feedback_semantics=SEMANTICS,run_id=r['run_id'],release_sha256=pin,
        sequence=sequence,controller_commit=r['controller_commit'],response_object=response_object,
        response_sha256=sha(encode(response)),output=output,output_sha256=sha(encode(output)),observation=observation(output))

def check_observation(value,r,pin,sequence,response_object,response,observation_object):
    require(observation_object['sha256']==sha(encode(value)),'observation object hash')
    require(value==observation_envelope(r,pin,sequence,response_object,response,value['output']),'observation binding')
    return value['observation']
