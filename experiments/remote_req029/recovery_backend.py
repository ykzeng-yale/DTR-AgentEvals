"""Recovery-only preparation policy; frozen comparator backend remains unchanged."""
from comparator_backend import Docker as FrozenDocker
from recovery_contract import require

class Docker(FrozenDocker):
    def populate(self,cid,deadline):
        require(self.contract.get('archive_ownership')=='extracting-user','explicit no-owner-restoration contract')
        self.call(['exec','-i',cid,'tar','--no-same-owner','-xf','-','-C','/testbed'],deadline,stdin=self.archive)
