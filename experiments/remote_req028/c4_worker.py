"""Bounded HTTP/telemetry worker. No code or tool execution from responses."""
import base64,json,sys,time
from pathlib import Path
from http.client import HTTPConnection
from c2_relay import sha,require
from c3_adapter import CONTRACT
def main(spec,out):
    s=json.loads(Path(spec).read_text());calls=[]
    def remaining():
        left=s['deadline']-time.time();require(left>0,'HTTP deadline');return left
    def http(method,path,body=None):
        endpoint=s['endpoint'];require(endpoint['host']=='127.0.0.1' and type(endpoint['port']) is int and 1<=endpoint['port']<=65535,'owned loopback only')
        conn=HTTPConnection(endpoint['host'],endpoint['port'],timeout=remaining());event={'method':method,'path':path,'body':body,'started':time.time()};calls.append(event)
        try:
            conn.request(method,path,None if body is None else json.dumps(body).encode(),{} if body is None else {'Content-Type':'application/json'})
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
        props=json.loads(http('GET','/props'));require(sha(props['chat_template'].encode())==CONTRACT['template_sha256'],'native template')
        rendered=json.loads(http('POST','/apply-template',s['body']))['prompt']
        ids=json.loads(http('POST','/tokenize',{'content':rendered,'add_special':True,'parse_special':True,'with_pieces':False}))['tokens']
        result={'kind':'json','value':{'template_sha256':CONTRACT['template_sha256'],'native_exact':True,'rendered':rendered,'token_ids':ids}}
    elif s['operation']=='generate':result={'kind':'raw','value':http('POST','/v1/chat/completions',s['body']).decode()}
    else:raise ValueError('unknown operation')
    Path(out).write_text(json.dumps(result))
if __name__=='__main__':main(sys.argv[1],sys.argv[2])
