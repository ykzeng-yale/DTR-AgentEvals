"""B4 immutable one-request contract; source-bound text parser replay, never execution."""
import ast,hashlib,json,re
from pathlib import Path
from b2_protocol import verify_archive
PIN='04d809ceab9df28f9adaed044884180159172930'
REGEX=r'```mswea_bash_command\s*\n(.*?)\n```'
HASHES={'models/utils/actions_text.py':'e5997bba3ae3d541ff418317cc8dd9e9e17657de806679ef38ab1ad74e294047','models/litellm_textbased_model.py':'395bc9bc4a06c18577e73b21c5465f9d22a6d0cc45b006f3d7c9fdaae399e732','config/default.yaml':'112aa58328f478a41cc2630702a4b89ef459e912870e05065157ed221f56701f'}
def parser_binding():
    source=json.loads(Path(__file__).with_name('b4_parser_source.json').read_text())
    assert {k:hashlib.sha256(v.encode()).hexdigest() for k,v in source.items()}==HASHES
    tree=ast.parse(source['models/litellm_textbased_model.py'])
    config=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='LitellmTextbasedModelConfig')
    regex=ast.literal_eval(next(n.value for n in config.body if isinstance(n,ast.AnnAssign) and n.target.id=='action_regex'))
    assert regex==REGEX
    parser=ast.parse(source['models/utils/actions_text.py'])
    function=next(n for n in parser.body if isinstance(n,ast.FunctionDef) and n.name=='parse_regex_actions')
    # Run only upstream's literal extraction expression, not generated commands.
    expression=next(n.value for n in function.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='actions' for t in n.targets))
    expected=ast.parse('[a.strip() for a in re.findall(action_regex, content, re.DOTALL)]',mode='eval').body
    assert ast.dump(expression)==ast.dump(expected)
    assert "if len(actions) != 1:" in source['models/utils/actions_text.py']
    return {'revision':PIN,'source_hashes':HASHES,'regex':regex,'extraction_ast':ast.dump(expression),'semantics':'exact upstream extraction expression; reject unless exactly one; no command execution; YAML default omits action_regex and inherits model default'},compile(ast.Expression(expression),'<pinned extraction>','eval')
def analyze(content):
    binding,expression=parser_binding()
    actions=eval(expression,{'re':re,'action_regex':REGEX,'content':content})
    matches=list(re.finditer(REGEX,content,re.DOTALL))
    independent=[m.group(1).strip() for m in matches]
    assert actions==independent
    spans=[];stack=[]
    for tag in re.finditer(r'</?think>',content):
        if tag.group()=='<think>':stack.append(tag.start())
        elif stack:spans.append((stack.pop(),tag.end()))
    spans.extend((start,len(content)) for start in stack)
    fences=[]
    for m in matches:
        overlap=any(m.start()<end and m.end()>start for start,end in spans)
        inside=any(start<=m.start() and m.end()<=end for start,end in spans)
        fences.append({'start':m.start(),'end':m.end(),'body':m.group(1),'location':'inside' if inside else 'overlap' if overlap else 'outside'})
    strict=re.fullmatch(r'```mswea_bash_command\n(.*?)\n```',content,re.S)
    return {'format_compliant':bool(strict and strict.group(1).strip()=='printf DTR_READY'),'literal_fence_match':content=='```mswea_bash_command\nprintf DTR_READY\n```','parser_accepted':len(actions)==1,'parser_expected_command':len(actions)==1 and actions[0]=='printf DTR_READY','complete_fence_count':len(matches),'extracted_actions':actions,'independent_regex_agrees':actions==independent,'fences':fences,'thinking_spans':spans,'unclosed_thinking_spans':len(stack)}
def copy_requests(root,alias):
    prior=root/'mechanics_b3_20260927';verify_archive(prior)
    body=json.loads((prior/'call_2.request.json').read_text())
    return [dict(body,model=alias,max_tokens=1536)]
def bind_prompts(bodies,http,out):
    assert len(bodies)==1 and bodies[0]['max_tokens']==1536
    prior=json.loads((out.parent/'mechanics_b3_20260927/prompt_2.json').read_text())
    rendered=http('/apply-template',bodies[0])['prompt']
    ids=http('/tokenize',{'content':rendered,'add_special':True,'parse_special':True,'with_pieces':False})['tokens']
    assert rendered==prior['rendered'] and ids==prior['token_ids'] and len(ids)==49
    assert len(ids)+1536<=32768
    with (out/'prompt_1.json').open('x') as f:json.dump({'call':1,'request':bodies[0],'rendered':rendered,'token_ids':ids},f,indent=2)
    return [{'call':1,'rendered_tokens':len(ids),'rendered_sha256':hashlib.sha256(rendered.encode()).hexdigest(),'token_ids_sha256':hashlib.sha256(json.dumps(ids).encode()).hexdigest(),'prior_B3_call':2,'exact_prior_binding':True}]
def execute_calls(dispatch):
    dispatch(0)
def retrospective(root):
    prior=root/'mechanics_b3_20260927';verify_archive(prior)
    return {'retrospective_only':True,'B3_not_rescored':True,'calls':[dict(call=i,**analyze(json.loads((prior/f'call_{i}.response.json').read_text())['choices'][0]['message']['content'])) for i in (1,2,3)]}
