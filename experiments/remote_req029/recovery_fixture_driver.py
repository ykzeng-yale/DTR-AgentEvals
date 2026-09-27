"""Inert external-process fixtures only."""
import json,os,sys,time
from pathlib import Path
from recovery_contract import *
from recovery_fixtures import release,InertModel,FakeDocker,Sandbox
from recovery_guardian import Guardian
mode=sys.argv[1];root=Path(sys.argv[2])
if mode=='guardian':
    s=json.loads(root.read_bytes());Guardian(s,FakeDocker(Path(s['root'])/'docker',s['release']['sandbox'],s['fake_root'])).run()
elif mode=='model':
    r,p=release();m=InertModel(root/'model')
    try:m.start(r,p,root);put(root,'ready',b'ready');time.sleep(50)
    finally:m.stop()
elif mode=='sandbox':
    r,p=release();s=Sandbox(root/'sandbox',r)
    try:s.preflight(r,time.time()+20);put(root,'ready',b'ready');time.sleep(50)
    finally:s.close()
elif mode=='claim':
    root.mkdir();put(root,'role.claim',{'inert':True});put(root,'claims/model-01.json',{'before_dispatch':True});os._exit(79)
