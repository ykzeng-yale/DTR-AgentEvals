"""External watchdog survives its owned driver; fixture resource samples only."""
import json,os,subprocess,sys,time
from pathlib import Path
import b3_stop,guard
from c3r_hooks import alive,safe_stop
from c3r_arbiter import identity
def watch(path):
    owner=Path(path);record=json.loads(owner.read_text())
    assert record['fixture_only'] is True
    try:
        while alive(record):
            try:
                try:
                    state=subprocess.check_output(['ps','-p',str(record['parent']),'-o','stat='],text=True,timeout=1).strip()
                    parent=bool(state) and not state.startswith('Z') and identity(record['parent'])==record['parent_identity']
                except subprocess.CalledProcessError:parent=False
                sample=json.loads(Path(record['sample_path']).read_text())
                reason=guard.violation(sample,0,record['deadline'],parent)
            except BaseException as e:reason='measurement_failure:'+repr(e)
            if reason:
                result=safe_stop(owner,record,reason)
                try:b3_stop.save(owner.with_suffix('.external_result.json'),{'reason':reason,'cleanup':result,'pid':os.getpid()})
                except BaseException:pass
                return
            time.sleep(.05)
    finally:
        if alive(record):safe_stop(owner,record,'watchdog finally')
if __name__=='__main__':watch(sys.argv[1])
