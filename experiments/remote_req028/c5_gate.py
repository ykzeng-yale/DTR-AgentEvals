"""Production exec gate, exact Qwen only; explicit inert test branch is separate."""
import json,os,select,sys,time
from pathlib import Path
from c2_relay import sha,require
from c3r_arbiter import identity
from c4_attest import argv,SERVER,MODEL
from c3_adapter import CONTRACT
from c5_contract import ROOT,approval,source_pins,release,RELEASE_PATH,EXPIRY
def command(s):
    if s.get('inert_test') is True:
        fixture=Path(__file__).with_name('c5_fixture.py');require(s['fixture_sha256']==sha(fixture.read_bytes()),'inert executable pin')
        require(s['phase_deadline']<=time.time()+60,'inert deadline');return [sys.executable,str(fixture),s['root'],str(s['port']),s['token']]
    require(not s.get('inert_test') and s['token'].startswith('c4-c5-owned-'),'production ownership token')
    a,raw=approval(ROOT,**s['approval_args'],now=time.time());require(a==s['approval'],'approval differs')
    require(source_pins(ROOT,s['approval_args']['source_commit'],s['load_deadline'])==s['source_pins'],'source pins')
    release((ROOT/RELEASE_PATH).read_bytes(),time.time())
    require(time.time()<s['load_deadline']<=s['phase_deadline']<=min(EXPIRY,s['phase_started']+600),'C5 deadlines')
    for path in (MODEL,SERVER):
        st=path.stat();require([st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns]==s['asset_stats'][str(path)],'asset changed after attestation')
    require(sha(SERVER.read_bytes())==CONTRACT['server_sha256'],'executable SHA')
    return argv(s['token'],s['port']) # never accept caller-supplied argv
def main(fd,ack,spec):
    s=json.loads(Path(spec).read_text());cmd=command(s)
    while True:
        require(time.time()<s['load_deadline'],'gate load deadline')
        if select.select([fd],[],[],.05)[0]:
            if os.read(fd,1)!=b'G':return
            require(os.getppid()==s['supervisor_pid'] and identity(os.getppid())==s['supervisor_identity'],'supervisor identity')
            require(identity(s['driver_pid'])==s['driver_identity'],'driver identity')
            require(time.time()<min(s['load_deadline'],s['phase_deadline']),'deadline immediately before exec')
            os.close(fd);os.set_inheritable(ack,False)
            os.execv(cmd[0],cmd) # ACK pipe closes on successful exec, no fixture file required
if __name__=='__main__':
    try:main(int(sys.argv[1]),int(sys.argv[2]),sys.argv[3])
    except BaseException:
        try:os.write(int(sys.argv[2]),b'E')
        except OSError:pass
        raise
