"""Recovery-only preparation policy; frozen comparator backend remains unchanged."""
from comparator_backend import Docker as FrozenDocker
from recovery_contract import require

class Docker(FrozenDocker):
    def populate(self,cid,deadline):
        require(self.contract.get('archive_ownership')=='extracting-user','explicit no-owner-restoration contract')
        self.call(['exec','-i',cid,'tar','--no-same-owner','-xf','-','-C','/testbed'],deadline,stdin=self.archive)

    def helper(self,cid,op,payload,deadline,cap=1024*1024):
        from recovery_container import CODE
        from recovery_contract import put
        import time
        self.counter+=1;path=self.root/('stdin-%04d.json'%self.counter)
        put(self.root,path.name,dict(payload,operation=op,task_head=self.contract['head'],import_module=self.contract['import_module']))
        return self.runner.run(self.prefix+['exec','-i','-w','/testbed',cid,
            self.contract['python'],'-I','-c',CODE],min(deadline,time.time()+60),
            env=self.env,clean_env=True,stdin_path=path,cap=cap,accept_nonzero=True)
