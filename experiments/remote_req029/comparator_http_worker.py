"""Bounded HTTP/telemetry worker. No code or tool execution from responses."""
import base64,json,sys,time
from pathlib import Path
from http.client import HTTPConnection
from comparator_contract import sha,require,template,native_template,encode,bound_messages
def main(spec,out):
    s=json.loads(Path(spec).read_text());calls=[]
    def remaining():
        left=s['deadline']-time.time();require(left>0,'HTTP deadline');return left
    def http(method,path,body=None):
        endpoint=s['endpoint'];require(endpoint['host']=='127.0.0.1' and type(endpoint['port']) is int and 1<=endpoint['port']<=65535,'owned loopback only')
        conn=HTTPConnection(endpoint['host'],endpoint['port'],timeout=remaining());event={'method':method,'path':path,'body':body,'started':time.time()};calls.append(event)
        try:
            conn.request(method,path,None if body is None else json.dumps(body).encode(),{} if body is None else {'Content-Type':'application/json'})
            event['request_sent']=True
            event['sent_at']=time.time()
            Path(s['audit']).write_text(json.dumps(calls,indent=2))
            response=conn.getresponse();raw=response.read(1024*1024+1)
            event.update(status=response.status,raw_base64=base64.b64encode(raw).decode(),raw_sha256=sha(raw),finished=time.time())
            require(len(raw)<=1024*1024,'HTTP size');require(response.status==200,'HTTP status '+str(response.status));remaining();return raw
        except BaseException as e:event['error']=repr(e);raise
        finally:
            conn.close();Path(s['audit']).write_text(json.dumps(calls,indent=2))
    if s['operation']=='telemetry':
        import guard
        result={'kind':'json','value':guard.sample(s.get('owned_group'))}
    elif s['operation']=='bind':
        r=s['release'];arm=r['arm']
        props=json.loads(http('GET','/props'))
        relation=native_template(arm,props['chat_template'],template(arm))
        require(props['total_slots']==1 and props['default_generation_settings']['n_ctx']==32768,'served slots/context')
        rendered=json.loads(http('POST','/apply-template',s['body']))['prompt']
        ids=json.loads(http('POST','/tokenize',{'content':rendered,'add_special':True,'parse_special':True,'with_pieces':False}))['tokens']
        native=dict(arm=arm,template_sha256=sha(template(arm).encode()),template_relation=relation,
                    native_exact=True,rendered=rendered,token_ids=ids,messages_sha256=sha(encode(s['body']['messages'])))
        bound_messages(native,s['body']['messages'],r)
        result={'kind':'json','value':native}
    elif s['operation']=='generate':result={'kind':'raw','value':http('POST','/v1/chat/completions',s['body']).decode()}
    else:raise ValueError('unknown operation')
    Path(out).write_text(json.dumps(result))
if __name__=='__main__':main(sys.argv[1],sys.argv[2])
