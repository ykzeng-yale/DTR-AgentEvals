"""Inert external-death fixture only; no production entrypoint imports this file."""
import sys,time
from pathlib import Path
from c6_process import Runner

if __name__=='__main__':
    mode=sys.argv[1]
    if mode=='sleep':time.sleep(59)
    elif mode=='claim':
        import os
        from c6_protocol import put
        root=Path(sys.argv[2]);root.mkdir()
        put(root,'role.claim',{'fixture':True})
        put(root,'claims/'+sys.argv[3]+'-01.json',{'durable_before_dispatch':True})
        os._exit(79)
    elif mode=='process':
        Runner(Path(sys.argv[2])/'process').run([sys.executable,__file__,'sleep'],time.time()+50)
    elif mode=='model':
        from c6_tests import InertModel,fake_release
        from c6_protocol import put
        root=Path(sys.argv[2]);r,p=fake_release(50);m=InertModel(root/'model')
        try:
            m.start(r,p,root);put(root,'ready',b'fixture ready')
            time.sleep(50)
        finally:m.stop()
