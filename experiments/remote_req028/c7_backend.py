"""Same fixed W2R boundary, with bounded C7 source-only helper operations."""
import json,math,time
from c6_sandbox_backend import Docker
from c6_protocol import require,put
from c7_contract import OUTPUT_CAP,PATCH_CAP
from c7_container import CODE
from c7_process import Runner

class Backend(Docker):
    def __init__(self,root,contract):
        super().__init__(root,contract)
        self.runner=Runner(self.root/'capture')

    def create(self,name,label,deadline,lifetime):
        # Independent container sleep is bounded by the SAME fixed sandbox lease,
        # not C6's longer trajectory lifetime. deadline excludes the 15s reserve.
        return super().create(name,label,deadline,min(lifetime,max(1,math.ceil(deadline+15-time.time()))))

    def evaluate(self,cid,operation,payload,deadline):
        require(operation in ('prepare','test'),'C7 fixed operation')
        self.counter+=1;path=self.root/('c7-stdin-%04d.json'%self.counter)
        raw=json.dumps(dict(payload,operation=operation)).encode()
        require(len(raw)<=3*PATCH_CAP,'input cap');put(self.root,path.name,raw)
        return self.runner.run(self.prefix+['exec','-i','-w','/testbed',cid,
            '/opt/miniconda3/envs/testbed/bin/python','-I','-c',CODE],deadline,
            env=self.env,clean_env=True,stdin_path=path,cap=OUTPUT_CAP,accept_nonzero=True)
