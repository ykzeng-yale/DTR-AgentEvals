"""Explicit fake production-branch driver for startup death fixtures only."""
import json,sys,time
from pathlib import Path
from c2_relay import encode,sha
from c5_lifecycle import Lifecycle,free_port
from c5_contract import ROOT
def main(root,stage):
    root=Path(root);root.mkdir(parents=True,exist_ok=True);now=time.time()
    spec={'inert_test':True,'fixture_sha256':sha(Path(__file__).with_name('c5_fixture.py').read_bytes()),'phase_started':now,'phase_deadline':now+20,'load_deadline':now+15,'token':'c4-c5-owned-fixture-'+str(time.time_ns()),'port':free_port(),'pause_at':stage}
    life=Lifecycle(root,spec)
    try:
        life.launch();(root/'driver_observer.json').write_bytes(encode({'supervisor':life.supervisor_record}))
        while not life.health():time.sleep(.02)
        (root/'running.json').write_bytes(encode({'child':life.record,'child_pid':life.record['pid']}))
        if stage=='inflight':
            from c4_http import HTTP,body
            (root/'hang').write_text('fixed fixture hang');http=HTTP(root/'http',life);q=json.loads((ROOT/'results/remote_req028/c5_request_20260927/request.json').read_text());h=http.begin_bind(q['messages'],3)
            from c3_adapter import PENDING
            while h.poll() is PENDING:time.sleep(.01)
            h=http.begin_generate(body(q['messages']),10)
            (root/'http_worker.json').write_bytes(encode(http.handles[-1].record))
            while h.poll() is PENDING:time.sleep(.01)
        time.sleep(20)
    finally:life.stop()
if __name__=='__main__':main(sys.argv[1],sys.argv[2])
