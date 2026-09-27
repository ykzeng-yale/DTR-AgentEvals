"""Deterministic execution of pinned upstream control-flow AST; no inference/tools."""
import ast, hashlib, json, logging, re, time
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from jinja2 import Template, StrictUndefined
ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT/'docs/source_snapshots/req029n_format_flow'
ns = dict(time=time, re=re, Template=Template, StrictUndefined=StrictUndefined)
def load(file, names):
    tree=ast.parse((SRC/file).read_text())
    nodes=[n for n in tree.body if isinstance(n,(ast.ClassDef,ast.FunctionDef)) and n.name in names]
    assert {n.name for n in nodes} == set(names)
    exec(compile(ast.Module(body=nodes,type_ignores=[]),str(SRC/file),'exec'),ns)
load('src__minisweagent__exceptions.py.txt',['InterruptAgentFlow','FormatError','LimitsExceeded','TimeExceeded'])
load('src__minisweagent__models__utils__actions_text.py.txt',['parse_regex_actions'])
tree=ast.parse((SRC/'src__minisweagent__agents__default.py.txt').read_text())
cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='DefaultAgent')
methods=['run','step','query','execute_actions','add_messages']
cls.body=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in methods]
exec(compile(ast.Module(body=[cls],type_ignores=[]),'pinned-default-agent','exec'),ns)
Agent=ns['DefaultAgent']
BAD='```mswea_bash_command\none\n```\n```mswea_bash_command\ntwo\n```'
GOOD='```mswea_bash_command\nfixture_only\n```'
def methods_from(file, class_name, names):
    tree=ast.parse((SRC/file).read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==class_name)
    functions=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in names]
    assert {n.name for n in functions}==set(names)
    exec(compile(ast.Module(body=functions,type_ignores=[]),str(SRC/file),'exec'),ns)
ns.update(logger=logging.getLogger('fixture'), retry=lambda **kw:[nullcontext()],
          GLOBAL_MODEL_STATS=SimpleNamespace(add=lambda cost:None),
          _reorder_anthropic_thinking_blocks=lambda messages:messages,
          set_cache_control=lambda messages,mode:messages)
methods_from('src__minisweagent__models__litellm_model.py.txt','LitellmModel',['query','_prepare_messages_for_api'])
provider_query=ns['query']; prepare=ns['_prepare_messages_for_api']
methods_from('src__minisweagent__models__litellm_textbased_model.py.txt','LitellmTextbasedModel',['_parse_actions'])
class Response:
    def __init__(self,content):
        self.content=content
        self.choices=[SimpleNamespace(finish_reason='stop',message=SimpleNamespace(content=content,model_dump=lambda:{'role':'assistant','content':content}))]
    def model_dump(self,**kw): return {'choices':[{'message':{'role':'assistant','content':self.content},'finish_reason':'stop'}]}
class Model:
    query=provider_query
    _prepare_messages_for_api=prepare
    _parse_actions=ns['_parse_actions']
    abort_exceptions=()
    def __init__(self, seq):
        self.seq=iter(seq); self.sent=[]
        self.config=SimpleNamespace(set_cache_control=None,action_regex=r'```mswea_bash_command\s*\n(.*?)\n```',format_error_template='Please always provide EXACTLY ONE action in triple backticks, found {{actions|length}} actions.')
    def format_message(self,**kw): return kw
    def _query(self,messages,**kw):
        self.sent.append(messages)
        return Response(next(self.seq))
    def _calculate_cost(self,response): return {'cost':1.}
    def format_observation_messages(self,message,outputs,vars): return [{'role':'user','content':'inert observation'}]
def case(seq,limit,expected_calls,expected_actions,status):
    a=Agent(); a.model=Model(seq); actions=[]
    a.env=SimpleNamespace(execute=lambda x: actions.append(x) or {})
    a.config=SimpleNamespace(system_template='system',instance_template='task',step_limit=limit,cost_limit=0,wall_time_limit_seconds=0,max_consecutive_format_errors=3,output_path=None)
    a.extra_template_vars={}; a.n_calls=0; a.cost=0.; a.n_consecutive_format_errors=0; a._start_time=time.time(); a.logger=logging.getLogger('fixture')
    a._render_template=lambda x:x; a.get_template_vars=lambda:{}; a.save=lambda p:None
    out=a.run(); assert out['exit_status']==status
    assert a.n_calls==expected_calls and len(actions)==expected_actions and a.cost==expected_calls
    errors=[m for m in a.messages if m.get('extra',{}).get('interrupt_type')=='FormatError']
    for m in errors:
        assert m['role']=='user' and m['extra']['model_response']==BAD
        assert m['content']=='Please always provide EXACTLY ONE action in triple backticks, found 2 actions.'
    assert all(x['command']=='fixture_only' for x in actions)
    assert all('extra' not in m for sent in a.model.sent for m in sent)
    assert all(m.get('content')!=BAD for sent in a.model.sent for m in sent)
    assert all(m['extra']['response']['choices'][0]['message']['content']==BAD for m in errors)
    return {'calls':a.n_calls,'inert_actions':len(actions),'cost_fixture_units':a.cost,'exit':out,'format_feedback':len(errors)}
def main():
    manifest=json.loads((SRC/'manifest.json').read_text())
    for f,h in manifest['sha256'].items(): assert hashlib.sha256((SRC/f).read_bytes()).hexdigest()==h
    cases=[case([BAD,GOOD],2,2,1,'LimitsExceeded'),case([BAD]*3,8,3,0,'RepeatedFormatError'),case([BAD,BAD,GOOD,BAD,BAD,GOOD],6,6,2,'LimitsExceeded'),case([BAD],1,1,0,'LimitsExceeded')]
    print(json.dumps({'source_verified':len(manifest['sha256']),'scope':'actual upstream agent, model query/preparation, text parser AST; inert provider, cost calculator, retry context and environment','cases':cases},indent=2))
if __name__=='__main__': main()
