"""Inert crash-boundary driver; no model executable supported."""
import json,sys,time
from pathlib import Path
from c2_relay import sha
from c3_adapter import CONTRACT,PENDING
from c4_lifecycle import InertSupervisedLifecycle,HERE
def main(root,stage):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    life=InertSupervisedLifecycle(root,sha((HERE/'c4_fixture.py').read_bytes()),pause_at=stage)
    try:
        handle=life.begin_load(CONTRACT,20)
        (root/'driver_observer.json').write_text(json.dumps({'supervisor':life.supervisor_record}))
        while handle.poll() is PENDING:time.sleep(.01)
        time.sleep(20)
    finally:life.stop('driver finally')
if __name__=='__main__':main(sys.argv[1],sys.argv[2])
