"""B2 fixed three-request contract and native loaded-tokenizer binding."""
import hashlib,json
from pathlib import Path
def verify_archive(p):
    for name,digest in json.loads((p/'sha256.json').read_text()).items():
        assert hashlib.sha256((p/name).read_bytes()).hexdigest()==digest,('prior artifact mismatch',name)
def copy_requests(root,alias):
    a4=root/'mechanics_a4_20260927';a5=root/'mechanics_a5_20260927'
    verify_archive(a4);verify_archive(a5)
    short=json.loads((a4/'prompt_manifest.json').read_text())['requests'][:2]
    long=json.loads((a5/'prompt_manifest.json').read_text())['requests'][0]
    return [dict(body,model=alias) for body in short+[long]]
def native_template(actual,expected):
    assert actual==expected,'native loaded template mismatch'
def bind_prompts(bodies,http,out):
    assert len(bodies)==3
    result=[]
    for index,body in enumerate(bodies):
        rendered=http('/apply-template',body)['prompt']
        ids=http('/tokenize',{'content':rendered,'add_special':True,'parse_special':True,'with_pieces':False})['tokens']
        assert all(isinstance(x,int) for x in ids) and len(ids)+128<=32768,'invalid context binding'
        if index==2:assert 8192<=len(ids)<=8256,'B2 8k count mismatch'
        with (out/('prompt_'+str(index+1)+'.json')).open('x') as f:
            json.dump({'call':index+1,'request':body,'rendered':rendered,'token_ids':ids},f,indent=2)
        result.append({'call':index+1,'rendered_tokens':len(ids),'rendered_sha256':hashlib.sha256(rendered.encode()).hexdigest(),'token_ids_sha256':hashlib.sha256(json.dumps(ids).encode()).hexdigest(),'user_sha256':hashlib.sha256(body['messages'][1]['content'].encode()).hexdigest()})
    return result
def execute_calls(dispatch):
    for index in (0,1,2):dispatch(index)
