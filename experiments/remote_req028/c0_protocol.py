"""Frozen C0 interface-only contract. Archived prompt/output text is data, never shell."""
import hashlib,json,re,subprocess
from pathlib import Path
import guard
from b4_protocol import parser_binding,analyze as prior_analysis
from b2r_binding import native_template as klear_native
DOC_SHA='1d99595667cee6fbab3af480eba0ca7ed4c9976abc5530b396c2cf78903d5d8a'
SOURCE_SHA='478b321f86a9591ff9488e69a90614ba7159ba29eb1176701d155353da7aba06'
MESSAGES_SHA='f8178479369ca97aed5c7f836b04da2c679225ddf10807033799c3a2f441b106'
ORDER=('klear','qwen')
ARMS={
 'klear':{'model':'Klear-AgentForge-8B.Q4_K_M.gguf','sha256':'9c0909b89b518283ded8ca415694743bd922e8844356db4f26957e37047142ae','bytes':5027783808,'revision':'0626423882f502d6fe113bd0ddc61970b19d942b','cache':'q4_0','template_sha':'f858b0b34b6c89118490c6c087cbbc5df911f56994cc8cb61ee7a619903abcd8'},
 'qwen':{'model':'Qwen3-4B-Instruct-2507-Q4_K_M.gguf','sha256':'3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597','bytes':2497281120,'revision':'a06e946bb6b655725eafa393f4a9745d460374c9','cache':'q8_0','template_sha':'c979e0e71a3e21b8f208e6ab120d5cb29327885f29d2a8b18fda67a723798e18'}}
def digest(data):return hashlib.sha256(data).hexdigest()
def message_hash(messages):return digest(json.dumps(messages,separators=(',',':')).encode())
def validate_frozen(raw,source_bytes):
    assert digest(raw)==DOC_SHA,'frozen document changed'
    frozen=json.loads(raw)
    assert frozen['source_sha256']==SOURCE_SHA and digest(source_bytes)==SOURCE_SHA,'trajectory source changed'
    messages=frozen['messages']
    assert len(messages)==2 and [m['role'] for m in messages]==['system','user']
    assert all(set(m)=={'role','content'} for m in messages)
    assert frozen['messages_sha256']==MESSAGES_SHA and message_hash(messages)==MESSAGES_SHA
    first=json.loads(source_bytes)['messages'][:2]
    assert messages==[{k:m[k] for k in ('role','content')} for m in first]
    assert frozen['order']==['Klear-community-q4KV','Qwen3-4B-q8KV']
    assert (frozen['max_tokens'],frozen['temperature'],frozen['seed'])==(1536,0,20260927028)
    return frozen
def frozen_messages(root):
    raw=(root/'docs/req028_c0_prompt_20260927.json').read_bytes()
    source=root/'results/v2_agent/req011_competence_20260924/astropy__astropy-14598__small__req011__20260924T154501Z-fa905f/trajectory.json'
    return validate_frozen(raw,source.read_bytes())
def copy_requests(root,alias):
    frozen=frozen_messages(root)
    return [{'model':alias,'messages':frozen['messages'],'temperature':0,'seed':20260927028,'max_tokens':1536,'stream':False,'cache_prompt':False,'timings_per_token':True}]
def bind_prompts(bodies,http,out):
    assert len(bodies)==1 and bodies[0]['max_tokens']==1536
    assert message_hash(bodies[0]['messages'])==MESSAGES_SHA
    rendered=http('/apply-template',bodies[0])['prompt']
    ids=http('/tokenize',{'content':rendered,'add_special':True,'parse_special':True,'with_pieces':False})['tokens']
    assert ids and all(type(x) is int for x in ids) and len(ids)+1536<=32768,'invalid context/headroom'
    with (out/'prompt_1.json').open('x') as f:json.dump({'call':1,'request':bodies[0],'rendered':rendered,'token_ids':ids},f,indent=2)
    return [{'call':1,'rendered_tokens':len(ids),'rendered_sha256':digest(rendered.encode()),'token_ids_sha256':digest(json.dumps(ids).encode()),'messages_sha256':MESSAGES_SHA,'reserved_completion_tokens':1536}]
def native_template(arm,actual,expected):
    assert digest(expected.encode())==ARMS[arm]['template_sha']
    if arm=='klear':return klear_native(actual,expected)
    assert actual==expected,'Qwen native served template changed'
    return {'raw_sha256':digest(expected.encode()),'served_sha256':digest(actual.encode()),'exact_bytes':True,'raw_bytes':len(expected.encode()),'served_bytes':len(actual.encode())}
def analyze(content,finish_reason):
    result=prior_analysis(content)
    for key in ('format_compliant','literal_fence_match','parser_expected_command'):result.pop(key)
    opened=[]
    for tag in re.finditer(r'</?think>',content):
        if tag.group()=='<think>':opened.append(tag.start())
        elif opened:opened.pop()
    for fence in result['fences']:
        fence['reasoning_boundary']=('after_unclosed_reasoning' if any(start<=fence['start'] for start in opened)
          else 'inside_closed_thinking' if fence['location']=='inside'
          else 'overlap' if fence['location']=='overlap' else 'outside_thinking')
    result['nonempty_command']=result['parser_accepted'] and bool(result['extracted_actions'][0])
    result['outside_thinking']=len(result['fences'])==1 and result['fences'][0]['location']=='outside'
    result['interface_gate']=finish_reason=='stop' and result['parser_accepted'] and result['nonempty_command'] and result['outside_thinking'] and result['unclosed_thinking_spans']==0
    result['command_correctness_assessed']=False
    return result
def execute_calls(dispatch):dispatch(0)
def confirmed_release(directory):
    status=json.loads((directory/'status.json').read_text())
    assert status['status']=='COMPLETE' and len(status['lifecycles'])==1,'arm infrastructure not complete'
    life=status['lifecycles'][0]
    assert life['released'] and life['returncode']==0
    owner=json.loads((directory/'server_0.ownership.json').read_text())
    assert not guard.same(owner),'owned model remains live'
    for pid in (life['pid'],life['watchdog_pid']):
        check=subprocess.run(['ps','-p',str(pid),'-o','pid=,command='],capture_output=True,text=True)
        assert check.returncode!=0,('previous arm PID still present',pid)
    stop=json.loads((directory/'server_0.ownership.stop.json').read_text())
    assert stop['owned_absent'] and stop['returncode']==0
    assert not list(directory.glob('*.abort.json')),'previous arm resource abort'
    return True
def run_order(run_arm,release_check,observe):
    results=[]
    for arm in ORDER:
        record={'arm':arm,'status':'STARTED'};results.append(record);observe(record)
        try:
            rc=run_arm(arm)
            if rc!=0:raise RuntimeError('arm infrastructure failure')
            assert release_check(arm),'owned release unconfirmed'
            record['status']='TERMINAL'
        except BaseException as error:
            record.update(status='FAILED',error=repr(error));observe(record)
            for remaining in ORDER[len(results):]:
                record={'arm':remaining,'status':'UNATTEMPTED','reason':'prior infrastructure or release failure'}
                results.append(record);observe(record)
            return results
        observe(record)
    return results
