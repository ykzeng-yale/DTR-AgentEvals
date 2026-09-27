"""One bounded socket or local-Git operation per disposable process."""
import json,os,subprocess,sys,time
from http.client import HTTPConnection
from pathlib import Path
from c2_relay import sha,require
from c2_git import GitTransport
from c3_adapter import CONTRACT
def main(spec,out):
    s=json.loads(Path(spec).read_text());deadline=s['deadline']
    def remaining():
        left=deadline-time.time();require(left>0,'operation deadline');return left
    def http(path,body):
        e=s['endpoint'];require(e['host']=='127.0.0.1' and type(e['port']) is int and 1<=e['port']<=65535,'owned loopback only')
        conn=HTTPConnection(e['host'],e['port'],timeout=remaining())
        try:
            conn.request('POST',path,json.dumps(body).encode(),{'Content-Type':'application/json'})
            resp=conn.getresponse();raw=resp.read(1024*1024+1);require(len(raw)<=1024*1024 and resp.status==200,'HTTP status/size')
            remaining();return raw
        finally:conn.close()
    op=s['operation']
    if op=='bind':
        props=json.loads(http('/props',{}));template=props['chat_template']
        require(sha(template.encode())==CONTRACT['template_sha256'],'native template SHA')
        rendered=json.loads(http('/apply-template',{'messages':s['messages']}))['prompt']
        ids=json.loads(http('/tokenize',{'content':rendered,'add_special':True,'parse_special':True,'with_pieces':False}))['tokens']
        result={'kind':'json','value':{'template_sha256':sha(template.encode()),'native_exact':True,'rendered':rendered,'token_ids':ids}}
    elif op=='generate':result={'kind':'raw','value':http('/v1/chat/completions',s['body']).decode()}
    else:
        def run(args,**kwargs):
            kwargs['timeout']=min(kwargs.get('timeout',30),remaining());return subprocess.run(args,**kwargs)
        repo=Path(s['repo']).resolve()
        origin=run(['git','remote','get-url','origin'],cwd=repo,capture_output=True).stdout.decode().strip()
        require(Path(origin).is_absolute() and Path(origin).resolve().parent==repo.parent,'fixture local Git only')
        class FixtureGit(GitTransport):
            @staticmethod
            def owned(path):
                from pathlib import PurePosixPath
                require(type(path) is str and path.startswith('results/remote_req028/c3_fixture/') and '..' not in PurePosixPath(path).parts,'unowned C3 fixture publication path')
        events=[];g=FixtureGit(repo,record=events.append,run=run)
        if op=='git_read':
            g.fetch_main();raw=g.read_object(s['commit'],s['path'])
            result={'kind':'json','value':{'commit':s['commit'],'path':s['path'],'raw_text':raw.decode(),'events':events}}
        elif op=='git_publish':
            value=g.publish({s['path']:s['raw'].encode()},'C3R fixed fixture response',s['expected_main'])
            result={'kind':'json','value':{'commit':value,'events':events}}
        else:raise ValueError('unknown fixed operation')
    Path(out).write_text(json.dumps(result))
if __name__=='__main__':main(sys.argv[1],sys.argv[2])
