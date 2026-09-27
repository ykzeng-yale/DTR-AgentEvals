"""Copy and rebind exactly the two archived A4 prompts; no search or generation."""
import hashlib,json
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def call_indices(cycle):
    assert cycle==0,'A5 has no restart'
    return (0,1)
def copy_prompts(prior,alias):
    for name,expected in json.loads((prior/'sha256.json').read_text()).items():
        assert digest(prior/name)==expected,('A4 artifact mismatch',name)
    frozen=json.loads((prior/'prompt_manifest.json').read_text())
    bodies=[];bindings=[]
    for index,target in ((4,8192),(5,24576)):
        body=json.loads(json.dumps(frozen['requests'][index]))
        artifact=json.loads((prior/('prompt_'+str(index+1)+'.json')).read_text())
        binding=frozen['bindings'][index]
        assert body==artifact['request']
        assert len(artifact['token_ids'])==binding['rendered_tokens']==target
        assert hashlib.sha256(artifact['rendered'].encode()).hexdigest()==binding['rendered_sha256']
        assert hashlib.sha256(json.dumps(artifact['token_ids']).encode()).hexdigest()==binding['token_ids_sha256']
        body['model']=alias
        bodies.append(body);bindings.append(binding)
    return bodies,bindings
def bind_prompts(bodies,prior_bindings,http,out):
    result=[]
    for index,(body,prior) in enumerate(zip(bodies,prior_bindings)):
        rendered=http('/apply-template',body)['prompt']
        ids=http('/tokenize',{'content':rendered,'add_special':True,'parse_special':True,'with_pieces':False})['tokens']
        assert len(ids)==prior['rendered_tokens']==(8192,24576)[index],'A5 count mismatch'
        assert hashlib.sha256(rendered.encode()).hexdigest()==prior['rendered_sha256'],'A5 rendered hash mismatch'
        assert hashlib.sha256(json.dumps(ids).encode()).hexdigest()==prior['token_ids_sha256'],'A5 token IDs mismatch'
        assert hashlib.sha256(body['messages'][1]['content'].encode()).hexdigest()==prior['user_sha256'],'A5 user mismatch'
        artifact={'call':index+1,'a4_call':index+5,'request':body,'rendered':rendered,'token_ids':ids}
        with (out/('prompt_'+str(index+1)+'.json')).open('x') as f:json.dump(artifact,f,indent=2)
        result.append(dict(prior,call=index+1,a4_call=index+5))
    assert len(result)==2
    return result
