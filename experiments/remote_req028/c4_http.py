"""Pinned llama.cpp HTTP contract, cancellable subprocess operations."""
import sys,time
from pathlib import Path
from c2_relay import require,encode
from c3r_hooks import ProcessHandle
HERE=Path(__file__).parent
def body(messages):return {'messages':messages,'temperature':0,'seed':20260927028,'max_tokens':1536,'stream':False,'cache_prompt':False}
class HTTP:
    def __init__(self,root,lifecycle):self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.life=lifecycle;self.counter=0;self.handles=[];self.bound_body=None
    def worker(self,operation,payload,timeout):
        require(self.life.owned_alive(),'HTTP requires exact owned child')
        self.counter+=1;spec=self.root/(str(self.counter)+'.input.json');out=self.root/(str(self.counter)+'.output.json')
        spec.write_bytes(encode(dict(payload,operation=operation,endpoint=self.life.endpoint,deadline=time.time()+timeout,audit=str(self.root/(str(self.counter)+'.http.json')))))
        h=ProcessHandle([sys.executable,str(HERE/'c4_worker.py'),str(spec),str(out)],timeout,out);self.handles.append(h);return h
    def begin_bind(self,messages,timeout):
        self.bound_body=body(messages);return self.worker('bind',{'body':self.bound_body},timeout)
    def begin_generate(self,payload,timeout):
        require(payload==self.bound_body,'generation differs from full native binding body')
        return self.worker('generate',{'body':payload},timeout)
    def close(self):
        for h in self.handles:h.close()
