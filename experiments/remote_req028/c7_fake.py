"""Test-only backend and launcher; never selectable by production CLI."""
import json,os,subprocess,sys,time
from pathlib import Path
from c6_protocol import HERE,sha,require
from c6_r_fixtures import FakeDocker
from c7_backend import Backend
from c7_contract import inputs
from c7_guardian import Guardian

class Fake(FakeDocker,Backend):
    def __init__(self,root,contract,fake_root):
        super().__init__(root,contract,fake_root)
        self.prefix=[sys.executable,str(HERE/'c7_fake.py'),'docker',str(fake_root)]

def fake_launch(spec,path):
    root=path.parent/'fake';root.mkdir();(root/'archive').write_bytes(b'inert archive')
    spec['fake_root']=str(root)
    # Test injection lives in this test-owned entrypoint, not the evaluator CLI.
    path.write_text(json.dumps(spec))
    with (path.parent/'guardian.stderr').open('xb') as err:
        return subprocess.Popen([sys.executable,__file__,'guardian',str(path)],stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,stderr=err,start_new_session=True)

def docker(root,args):
    from c6_r_fake_docker import main as inherited
    root=Path(root)
    if args[0]!='exec' or 'tar' in args:return inherited(root,args)
    payload=json.loads(sys.stdin.buffer.read(3*1024**2+1));op=payload['operation']
    if op in ('preflight','diff'):
        if op=='preflight':print(json.dumps(dict(writable=True,limits_verified=True)))
        else:print('fixed inert diagnostic diff')
        return
    (root/('stage-'+op)).write_text(json.dumps(payload))
    mode=(root/'mode').read_text() if (root/'mode').exists() else ''
    if op=='prepare':
        if mode=='apply-fail':print('fixed apply failure');sys.exit(1)
        print(json.dumps(dict(candidate_diff='inert diff',packages=[['inert','0']],python='inert',omitted_install='inert')))
        return
    require(op=='test','fake operation')
    if mode=='hang':time.sleep(50)
    if mode=='overflow':
        while True:os.write(1,b'x'*65536)
    data,_=inputs();print('>>>>> Start Test Output')
    for i,t in enumerate(data['FAIL_TO_PASS']+data['PASS_TO_PASS']):
        print(('FAILED' if i==0 and mode=='fail' else 'PASSED')+' '+t)
    print('>>>>> End Test Output');sys.exit(1 if mode=='fail' else 0)

if __name__=='__main__':
    if sys.argv[1]=='docker':docker(sys.argv[2],sys.argv[3:])
    elif sys.argv[1]=='guardian':
        s=json.loads(Path(sys.argv[2]).read_bytes())
        Guardian(s,Fake(Path(s['root'])/'docker',s['release']['sandbox'],s['fake_root'])).run()
    elif sys.argv[1]=='driver':
        from c7_evaluate import run
        r=json.loads(Path(sys.argv[2]).read_bytes())
        def launch(s,path):
            p=fake_launch(s,path);(path.parent/'fake/mode').write_text('hang')
            (Path(sys.argv[3]).parent/'guardian.pid').write_text(str(p.pid));return p
        run(r,'fixture-pin',{},Path(sys.argv[3]),launch)
