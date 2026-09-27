"""Allowlisted inert driver used to test real driver death, never model startup."""
import json,signal,sys,time
from pathlib import Path
from c2_relay import sha
from c3_adapter import CONTRACT,PENDING
from c3r_hooks import Lifecycle,HTTP,HERE
def main(root,mode):
    signal.alarm(60);root=Path(root);root.mkdir(parents=True,exist_ok=True)
    life=Lifecycle(root/'server',sha((HERE/'c3r_fixture.py').read_bytes()),'hang' if mode=='inflight' else 'fixed')
    http=HTTP(root/'http',life)
    try:
        load=life.begin_load(CONTRACT,30)
        while load.poll() is PENDING:time.sleep(.01)
        info={'model':life.record,'watchdog_pid':life.watchdog.pid}
        if mode=='inflight':
            handle=http.begin_generate({'messages':[]},20);info['http_worker']=handle.record
        (root/'observer.json').write_text(json.dumps(info))
        time.sleep(30)
    finally:http.close();life.stop('driver finally')
if __name__=='__main__':main(sys.argv[1],sys.argv[2])
