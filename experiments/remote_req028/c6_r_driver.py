"""External-death/descendant inert fixture; no production entrypoint imports it."""
import json,os,subprocess,sys,time
from pathlib import Path
from c6_protocol import put

if __name__=='__main__':
    mode=sys.argv[1]
    if mode in ('orphan','orphan-held'):
        p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(50)'])
        put(Path(sys.argv[2]).parent,Path(sys.argv[2]).name,{'pid':p.pid})
        if mode=='orphan-held':time.sleep(.5)
    elif mode=='guardian':
        from c6_sandbox_guardian import Guardian
        from c6_r_fixtures import FakeDocker
        s=json.loads(Path(sys.argv[2]).read_text())
        Guardian(s,FakeDocker(Path(s['root'])/'docker',s['release']['sandbox'],s['fake_root'])).run()
    elif mode=='controller':
        from c6_r_fixtures import Sandbox
        from c6_tests import fake_release
        root=Path(sys.argv[2]);stage=sys.argv[3];r,p=fake_release(55);s=Sandbox(root/'sandbox',r,root/'fake')
        put(s.fake_root,'pause',stage.encode())
        try:
            s.preflight(r,time.time()+10);s.bind_fixture();put(root,'ready',b'ready')
            if stage=='execute':s.execute('fixture-action',time.time()+10)
            time.sleep(35)
        finally:s.close()
    elif mode=='runner':
        from c6_process import Runner
        root=Path(sys.argv[2]);Runner(root/'process').run([sys.executable,__file__,'orphan-held',str(root/'descendant.json')],time.time()+5)
