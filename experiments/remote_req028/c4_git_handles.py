"""Cancellable disposable-worker bridge for the explicit C4 Git transport."""
import json,sys,time
from pathlib import Path
from c2_relay import encode,require
from c3_adapter import PENDING
from c3r_hooks import ProcessHandle
from c4_git import Transport
FIELDS=('authorized','last_response','used','failed')
def state(t):return {k:sorted(getattr(t,k)) if k=='used' else getattr(t,k) for k in FIELDS}
def restore(t,s):
    for k in FIELDS:setattr(t,k,set(s[k]) if k=='used' else s[k])
    if t.authorized and type(t.authorized.get('raw')) is str:t.authorized['raw']=t.authorized['raw'].encode()
def serialized(t):
    s=state(t)
    if s['authorized']:s['authorized']=dict(s['authorized'],raw=s['authorized']['raw'].decode())
    return s
class Handles:
    def __init__(self,root,transport):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.transport=transport;self.counter=0;self.handles=[];self.active=False
    def worker(self,operation,fields,timeout):
        require(not self.active and not self.transport.failed,'Git worker already active/failed');self.active=True;self.counter+=1
        spec=self.root/(str(self.counter)+'.input.json');out=self.root/(str(self.counter)+'.output.json')
        spec.write_bytes(encode(dict(fields,operation=operation,repo=str(self.transport.repo),origin=self.transport.origin,fixture_root=None if self.transport.fixture_root is None else str(self.transport.fixture_root),state=serialized(self.transport),deadline=time.time()+timeout)))
        worker=ProcessHandle([sys.executable,__file__,str(spec),str(out)],timeout,out);outer=self
        class Handle:
            def poll(self):
                try:
                    result=worker.poll()
                    if result is PENDING:return result
                    restore(outer.transport,result['state']);outer.active=False;value=result['value']
                    if 'raw_text' in value:value['raw']=value.pop('raw_text').encode()
                    return value
                except BaseException:outer.transport.failed=True;outer.active=False;raise
            def cancel(self):
                if outer.active:outer.transport.failed=True;outer.active=False
                worker.cancel()
            def close(self):worker.close()
        h=Handle();self.handles.append(h);return h
    def begin_read(self,commit,path,timeout):return self.worker('read',{'commit':commit,'path':path},timeout)
    def begin_publish(self,sequence,raw,timeout):return self.worker('publish',{'sequence':sequence,'raw':raw.decode()},timeout)
    def close(self):
        for h in self.handles:h.close()
def main(spec,out):
    s=json.loads(Path(spec).read_text());t=Transport(s['repo'],s['origin'],s['fixture_root']);restore(t,s['state']);timeout=s['deadline']-time.time();require(timeout>0,'Git worker deadline')
    if s['operation']=='read':
        value=t.read(s['commit'],s['path'],timeout);value['raw_text']=value.pop('raw').decode()
    else:value=t.publish(s['sequence'],s['raw'].encode(),timeout)
    Path(out).write_text(json.dumps({'kind':'json','value':{'value':value,'state':serialized(t)}}))
if __name__=='__main__':main(sys.argv[1],sys.argv[2])
