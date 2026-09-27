"""Protocol3 response, no synthetic-C2 authorization substitution."""
import json
from c2_relay import encode,decode,sha,require,digest,commit_id,number
KEYS={'protocol','run_id','sequence','request_id','request_commit','request_path','request_sha256','config_sha256','messages_sha256','native_binding','native_binding_sha256','raw_response','raw_response_sha256','timings','status'}
def build(q,entry,config_sha,binding,raw,timings):
    return encode({'protocol':3,'run_id':q['run_id'],'sequence':q['sequence'],'request_id':q['request_id'],'request_commit':entry['commit'],'request_path':entry['path'],'request_sha256':entry['sha256'],'config_sha256':config_sha,'messages_sha256':q['messages_sha256'],'native_binding':binding,'native_binding_sha256':sha(encode(binding)),'raw_response':raw.decode('utf-8'),'raw_response_sha256':sha(raw),'timings':timings,'status':'terminal'})
def consume(raw,q,entry,config_sha,expected_binding_sha):
    d=decode(raw,KEYS)
    require(type(d['protocol']) is int and d['protocol']==3,'wrong response protocol')
    require(type(d['sequence']) is int and d['sequence']>=1,'response sequence')
    for k,v in {'run_id':q['run_id'],'sequence':q['sequence'],'request_id':q['request_id'],'request_commit':entry['commit'],'request_path':entry['path'],'request_sha256':entry['sha256'],'config_sha256':config_sha,'messages_sha256':q['messages_sha256'],'status':'terminal'}.items():require(d[k]==v,'response binding '+k)
    commit_id(d['request_commit']);digest(d['request_sha256'])
    require(sha(encode(d['native_binding']))==d['native_binding_sha256']==digest(expected_binding_sha),'native binding mismatch')
    require(type(d['raw_response']) is str and sha(d['raw_response'].encode())==digest(d['raw_response_sha256']),'raw response mismatch')
    require(type(d['timings']) is dict and set(d['timings'])=={'request_wall_seconds','prefill_ms','generation_ms'},'timing fields')
    number(d['timings']['request_wall_seconds'])
    for k in ('prefill_ms','generation_ms'):
        if d['timings'][k] is not None:number(d['timings'][k])
    return d
