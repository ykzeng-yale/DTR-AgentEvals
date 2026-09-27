"""Pre-exec gate owned by supervisor, pipe EOF fails closed; no child alarm."""
import json,os,select,sys
from pathlib import Path
from c2_relay import sha,require
from c3r_arbiter import identity
def main(fd,spec_path):
    spec=json.loads(Path(spec_path).read_text());fixture=Path(__file__).with_name('c4_fixture.py')
    require(spec['executable_sha256']==sha(fixture.read_bytes()),'inert executable pin')
    # This gate cannot execute any supplied arbitrary command or real model.
    while True:
        ready,_,_=select.select([fd],[],[],.1)
        if not ready:continue
        permission=os.read(fd,1)
        if permission!=b'G':return
        require(os.getppid()==spec['supervisor_pid'] and identity(os.getppid())==spec['supervisor_identity'],'supervisor identity')
        os.close(fd)
        os.execv(sys.executable,[sys.executable,str(fixture),spec['root'],spec['mode'],spec['token']])
if __name__=='__main__':main(int(sys.argv[1]),sys.argv[2])
