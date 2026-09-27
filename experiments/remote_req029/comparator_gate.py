"""C6 exact-release exec gate. No C5 approval or caller-selected executable."""
import json,os,select,sys,time
from pathlib import Path
from comparator_contract import HERE,sha,require
from c3r_arbiter import identity
from comparator_attest import argv,SERVER,paths
from comparator_contract import ASSETS

def command(s):
    if s.get('inert_test') is True:
        fixture=Path(__file__).with_name('comparator_fixture.py')
        require(s['fixture_sha256']==sha(fixture.read_bytes()),'inert source pin')
        require(s['phase_deadline']<=time.time()+60,'inert deadline')
        require(s['phase_deadline']<=s['phase_started']+60,'finite fake lifetime')
        return [sys.executable,str(fixture),s['root'],str(s['port']),s['token']]
    from comparator_launch import authorize
    r,pin=authorize(**s['approval_args'],deadline=s['load_deadline'])
    require(r==s['release'] and pin==s['release_sha256'],'release substitution')
    require(s['token'].startswith('c4-cmp029e-owned-'),'ownership token')
    require(time.time()<s['load_deadline']<=s['phase_deadline']<=min(r['expires_at'],s['phase_started']+1800),'C6 deadline')
    for path in paths(r):
        st=path.stat()
        require([st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns]==s['asset_stats'][str(path)],'asset changed')
    require(sha(SERVER.read_bytes())==ASSETS['runner_binary_hashes']['llama-server'],'executable SHA')
    return argv(r,s['token'],s['port'])

def main(fd,ack,spec):
    s=json.loads(Path(spec).read_text());cmd=command(s)
    while True:
        require(time.time()<s['load_deadline'],'load deadline')
        if select.select([fd],[],[],.05)[0]:
            if os.read(fd,1)!=b'G':return
            require(os.getppid()==s['supervisor_pid'] and identity(os.getppid())==s['supervisor_identity'],'supervisor identity')
            require(identity(s['driver_pid'])==s['driver_identity'],'driver identity')
            require(time.time()<min(s['load_deadline'],s['phase_deadline']),'deadline immediately before exec')
            os.close(fd);os.set_inheritable(ack,False)
            os.execv(cmd[0],cmd)

if __name__=='__main__':
    try:main(int(sys.argv[1]),int(sys.argv[2]),sys.argv[3])
    except BaseException:
        try:os.write(int(sys.argv[2]),b'E')
        except OSError:pass
        raise
