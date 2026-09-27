"""Source-only pinned SSH/local mailbox caller; no production activation CLI."""
import json,re,shlex,time
from pathlib import Path
from recovery_contract import require,sha,encode,put
from recovery_mailbox import KINDS
from c6_process import Runner
class Transport:
    def __init__(self,root,mailbox,helper,helper_sha,role,deadline,*,alias=None,python='python3',interval=5,fixture=False):
        require(role in KINDS.values(),'role')
        require(Path(mailbox).is_absolute() and Path(helper).is_absolute(),'absolute paths')
        require(re.fullmatch('[0-9a-f]{64}',helper_sha),'helper hash')
        require(alias is None or alias in ('mac-mini','mac-aux'),'verified host alias')
        require(interval>=5 or fixture,'finite production interval')
        require(python=='python3' or (fixture and Path(python).is_absolute()),'python command')
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=False)
        self.mailbox,self.helper,self.helper_sha,self.role=mailbox,helper,helper_sha,role
        self.alias,self.python,self.interval=alias,python,interval
        self.deadline=deadline;self.failed=False;self.fetches=0;self.calls=0;self.last_read=0;self.events=[];self.seen={}
        self.runner=Runner(self.root/'process')
    def exchange(self,operation,kind,payload=None,seq=None):
        require(not self.failed,'transport poisoned')
        try:
            require(kind in KINDS and (operation!='publish' or KINDS[kind]==self.role),'artifact owner')
            require(self.calls<512 and time.time()<self.deadline,'transport cap/deadline')
            if operation=='read':
                require(self.fetches<360,'read cap')
                while True:
                    self.runner.check();now=time.time();require(now<self.deadline,'queue deadline')
                    left=self.last_read+self.interval-now
                    if left<=0:break
                    time.sleep(min(.05,left))
                self.last_read=now;self.fetches+=1
            self.calls+=1
            q=dict(operation=operation,kind=kind,sequence=seq,payload=payload)
            path=self.root/('request-%04d.json'%self.calls);put(self.root,path.name,encode(q))
            # Bootstrap verifies bytes and executes those same bytes, avoiding a
            # hash-check/reopen race. Payload travels via stdin, never shell text.
            code="import hashlib,sys; b=open(sys.argv[1],'rb').read(); assert hashlib.sha256(b).hexdigest()==sys.argv[2], 'helper hash'; sys.argv=[sys.argv[1],sys.argv[3],sys.argv[4]]; exec(compile(b,sys.argv[0],'exec'),{'__name__':'__main__'})"
            argv=[self.python,'-c',code,self.helper,self.helper_sha,self.mailbox,self.role]
            if self.alias:argv=['ssh','-T','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=8',self.alias,shlex.join(argv)]
            start=time.time()
            out=self.runner.run(argv,min(self.deadline,start+12),cap=2*1024*1024,stdin_path=path)
            value=json.loads(out['output']);require(type(value) is dict,'response schema')
            key=(kind,seq)
            if value=={'present':False}:
                require(operation=='read' and key not in self.seen,'missing prior object')
                result=None
            else:
                require(set(value)=={'present','payload','sha256','bytes','name'} and value['present'] is True,'response schema')
                raw=encode(value['payload']);name=kind+('' if seq is None else '-%02d'%seq)+'.json'
                require(value['name']==name and value['sha256']==sha(raw) and value['bytes']==len(raw),'response bytes')
                require(key not in self.seen or self.seen[key]==raw,'immutable object changed')
                if operation=='publish':require(raw==encode(payload),'publication readback')
                self.seen[key]=raw
                obj=dict(transport='ssh-mailbox-v1',name=name,sha256=sha(raw),helper_sha256=self.helper_sha)
                result=(value['payload'],obj)
            self.events.append(dict(operation=operation,kind=kind,sequence=seq,started=start,finished=time.time(),present=result is not None))
            return result
        except BaseException:
            self.failed=True
            raise
    def read(self,kind,seq=None):return self.exchange('read',kind,seq=seq)
    def publish(self,kind,value,seq=None):return self.exchange('publish',kind,value,seq)[1]
