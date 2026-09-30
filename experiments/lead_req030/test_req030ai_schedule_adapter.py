"""Inert real DefaultAgent lifecycle tests, isolated from global loader fixtures."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = r'''
import copy,json,sys
from experiments.lead_req030.seaborn_runner_qualification import load_pinned_default_agent
DefaultAgent = load_pinned_default_agent()
from minisweagent.exceptions import Submitted
from experiments.lead_req030.seaborn_public_input import load_pinned_agent_templates
from experiments.lead_req030.req030ai_schedule_adapter import FixedScheduleHFAdapter, MODEL_PINS, ACTION_REGEX
case=json.loads(sys.argv[1]); state={'generations':0}; events=[]
class Slice:
 def __init__(self, values): self.values=values
 def tolist(self): return self.values
class Tensor:
 def __init__(self, rows): self.rows=rows; self.shape=(len(rows),len(rows[0]))
 def to(self, _device): return self
 def __getitem__(self, key):
  if isinstance(key,int): return Slice(self.rows[key])
  row,col=key; return Slice(self.rows[row][col])
class Tokenizer:
 eos_token_id=2
 def __init__(self): self.renders=[]; self.encodes=0
 def apply_chat_template(self,messages,*,tokenize,add_generation_prompt):
  assert tokenize is False and add_generation_prompt is True
  self.renders.append(copy.deepcopy(messages))
  return json.dumps(messages,separators=(',',':'))+'|assistant:'
 def __call__(self,rendered,*,add_special_tokens,return_tensors):
  assert add_special_tokens is False and return_tensors=='pt'; self.encodes+=1
  if case.get('drift'): return {'input_ids':Tensor([[self.encodes,12]])}
  n=15000 if case.get('deny_initial') or (case.get('deny9') and 'reserve_denial_after_8' in rendered) else 3
  return {'input_ids':Tensor([[11]*n])}
 def decode(self,ids,*,skip_special_tokens):
  assert skip_special_tokens is False
  return 'invalid model output' if ids[0]==100 else '```mswea_bash_command\nINERT_NOOP\n```'
class Model:
 def __init__(self,action): self.action=action; self.calls=0; self.inputs=[]
 def generate(self,*,input_ids,**kwargs):
  assert kwargs=={'do_sample':False,'max_new_tokens':1536,'use_cache':True,'pad_token_id':2}
  self.calls+=1; state['generations']+=1; self.inputs.append(list(input_ids.rows[0]))
  if state['generations']==case.get('generation_error'): raise RuntimeError('inert generation failure')
  first=100 if state['generations']==case.get('format_error') else 42
  return Tensor([input_ids.rows[0]+[first,2]])
class Environment:
 def __init__(self): self.actions=[]
 def get_template_vars(self): return {'system':'Linux','release':'inert','version':'1','machine':'inert'}
 def execute(self,action,cwd=''):
  self.actions.append(action)
  if len(self.actions)==case.get('submit_after'): raise Submitted({'role':'exit','content':'inert submission','extra':{'exit_status':'Submitted','submission':'inert'}})
  return {'output':'reserve_denial_after_8' if len(self.actions)==8 else 'inert observation','returncode':0,'exception_info':None,'extra':{}}
 def serialize(self): return {'info':{'environment':'inert; no commands executed'}}
tokenizer=Tokenizer(); models={a:Model(a) for a in ('S','L')}; info=copy.deepcopy(MODEL_PINS)
if case.get('bad_pin'): info['L']['revision']='0'*40
templates=load_pinned_agent_templates()
def record(event):
 if event['event']==case.get('reject_event'): raise OSError('inert journal failure')
 events.append(copy.deepcopy(event))
try:
 adapter=FixedScheduleHFAdapter(schedule=case.get('schedule','SL'),tokenizer=tokenizer,models=models,
  model_info=info,record_event=record,action_regex=ACTION_REGEX,
  format_error_template=templates.format_error_template,observation_template=templates.observation_template,device='inert')
except Exception as exc:
 print(json.dumps({'construction_error':type(exc).__name__,'calls':sum(m.calls for m in models.values())}));raise SystemExit(0)
env=Environment(); agent=DefaultAgent(adapter,env,system_template='Fixed public system',instance_template='{{task}}',
 step_limit=case.get('steps',24),cost_limit=0,max_consecutive_format_errors=0)
try:
 result=agent.run(task='Public inert task')
except Exception as exc:
 result={'raised':type(exc).__name__,'message':str(exc)}
print(json.dumps({'result':result,'events':events,'logical':adapter.logical_calls,'agent_logical':agent.n_calls,
 'physical':adapter.n_calls,'per_model':adapter.model_call_counts,'generations':state['generations'],
 'actions':len(env.actions),'renders':tokenizer.renders,'messages':agent.messages,'serialized':adapter.serialize()}))
'''


def run_fixture(**case):
    result = subprocess.run([sys.executable, "-c", FIXTURE, json.dumps(case)],
                            cwd=ROOT, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("schedule,expected", [
    ("SS", {"S": 24, "L": 0}), ("SL", {"S": 8, "L": 16}),
    ("LS", {"S": 16, "L": 8}), ("LL", {"S": 0, "L": 24}),
])
def test_real_agent_uses_exact_fixed_schedule_and_global_calls(schedule, expected):
    result = run_fixture(schedule=schedule)
    assert result["result"]["exit_status"] == "LimitsExceeded"
    assert result["logical"] == result["agent_logical"] == result["physical"] == result["generations"] == 24
    assert result["per_model"] == expected
    requests = [e for e in result["events"] if e["event"] == "request"]
    responses = [e for e in result["events"] if e["event"] == "response"]
    decisions = [e for e in result["events"] if e["event"] == "routing_decision"]
    assert [e["physical_calls"] for e in requests] == list(range(1, 25))
    assert [e["physical_calls"] for e in responses] == list(range(1, 25))
    assert [e["model_action"] for e in requests] == [schedule[0]] * 8 + [schedule[1]] * 16
    assert [e["logical_call"] for e in decisions] == [1, 9]
    assert [e["remaining_logical_calls_including_current"] for e in decisions] == [24, 16]
    for decision in decisions:
        assert decision["probability"] == 1.0 and decision["randomized_logger"] is False
        assert sum(decision["probability_vector"].values()) == 1.0
        assert decision["both_action_reservations"]["S"] == decision["both_action_reservations"]["L"]
        assert decision["both_action_reservations"]["S"]["remaining_input_token_capacity"] == 16384 - 1536 - 3
        assert decision["elapsed_time_eligibility"] == "shared episode deadline enforced by the worker"
        request = requests[decision["logical_call"] - 1]
        assert result["events"].index(decision) < result["events"].index(request)
        assert decision["both_action_reservations"]["S"]["messages_sha256"] == request["messages_sha256"]
    if schedule[0] != schedule[1]:
        assert requests[8]["physical_calls"] == 9 and requests[8]["per_model_physical_calls"] == 1
    # No conversation reset, compression or lost prior observation at switching.
    decision9render = json.loads(requests[8]["rendered"].removesuffix("|assistant:"))
    assert len(decision9render) == 18
    assert decision9render[:2] == [{"role": "system", "content": "Fixed public system"},
                                  {"role": "user", "content": "Public inert task"}]
    assert sum(m["role"] == "assistant" for m in decision9render) == 8
    bindings = [m["extra"]["native_binding"] for m in result["messages"] if m.get("role") == "assistant"]
    assert [b["physical_calls"] for b in bindings] == list(range(1, 25))


def test_early_submission_has_no_second_decision():
    result = run_fixture(schedule="SL", submit_after=3)
    assert result["result"]["exit_status"] == "Submitted"
    assert result["physical"] == result["logical"] == 3
    assert result["per_model"] == {"S": 3, "L": 0}
    assert [e["logical_call"] for e in result["events"] if e["event"] == "routing_decision"] == [1]


@pytest.mark.parametrize("denial,expected_logical,expected_physical", [("deny_initial", 1, 0), ("deny9", 9, 8)])
def test_both_action_context_reservation_denies_before_generation(denial, expected_logical, expected_physical):
    result = run_fixture(**{denial: True})
    assert result["result"]["exit_status"] == "LimitsExceeded"
    assert result["result"]["limit_kind"] == "context_tokens"
    assert result["physical"] == result["generations"] == expected_physical
    assert result["logical"] == result["agent_logical"] == expected_logical
    denied = result["events"][-1]
    assert denied["event"] == "routing_reservation_denied"
    assert "probability_vector" not in denied and "model_action" not in denied
    assert not any(v["admitted"] for v in denied["both_action_reservations"].values())


def test_format_error_consumes_logical_call_and_does_not_delay_switch():
    result = run_fixture(format_error=1, steps=10)
    assert result["physical"] == result["logical"] == result["agent_logical"] == 10
    assert result["actions"] == 9 and result["per_model"] == {"S": 8, "L": 2}
    assert [e["logical_call"] for e in result["events"] if e["event"] == "routing_decision"] == [1, 9]
    errors = [m for m in result["messages"] if m.get("extra", {}).get("interrupt_type") == "FormatError"]
    assert len(errors) == 1 and errors[0]["extra"]["native_binding"]["physical_calls"] == 1


def test_generation_error_remains_infrastructure_and_preserves_both_counts():
    result = run_fixture(generation_error=9)
    assert result["result"]["raised"] == "RuntimeError"
    assert result["physical"] == result["logical"] == 9
    assert result["per_model"] == {"S": 8, "L": 1}
    assert result["events"][-1]["event"] == "generation_error"
    assert result["events"][-1]["physical_calls"] == 9
    assert result["events"][-1]["per_model_physical_calls"] == 1


@pytest.mark.parametrize("kind", ["routing_decision", "request"])
def test_failed_durable_predispatch_receipt_blocks_generation(kind):
    result = run_fixture(reject_event=kind)
    assert result["result"]["raised"] == "OSError"
    assert result["generations"] == result["physical"] == 0


def test_common_tokenizer_binding_drift_rejected_before_call():
    result = run_fixture(drift=True)
    assert result["result"]["raised"] == "RuntimeError"
    assert result["physical"] == 0 and result["events"] == []


@pytest.mark.parametrize("case", [{"schedule": "adaptive"}, {"bad_pin": True}])
def test_nonfrozen_schedule_or_model_pin_rejected(case):
    result = run_fixture(**case)
    assert result == {"construction_error": "ValueError", "calls": 0}
