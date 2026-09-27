"""Test-owned inert Docker-shaped executable. Never evaluates command strings."""
import json,os,sys,time
from pathlib import Path
from matplotlib_eval_contract import *
IMAGE=SANDBOX['image']

def main(root,args):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    def save(name,value):
        path=root/name;tmp=root/(name+'.tmp');tmp.write_text(json.dumps(value));os.replace(tmp,path)
    def stage(name):
        save('stage-'+name,{'time':time.time()})
        if (root/'pause').exists() and (root/'pause').read_text()==name:time.sleep(.5)
    def cfg():return json.loads((root/'container.json').read_text()) if (root/'container.json').exists() else None
    save('event-'+str(time.time_ns()),{'argv':args})
    op=args[0]
    if op=='image':print(json.dumps([{'Id':IMAGE,'Os':'linux','Architecture':'amd64'}]));return
    if op=='ps':print('peer' if (root/'peer').exists() else '');return
    if op=='inspect':
        c=cfg()
        if not c or args[1] not in (c['Id'],c['Name'].lstrip('/')):
            print('No such object');sys.exit(1)
        if (root/'foreign').exists():c['Config']['Labels']['dtr.req029w.owner']='foreign'
        print(json.dumps([c]));return
    if op=='create':
        assert '--pull=never' in args,'no implicit download even after a concurrent image removal'
        get=lambda key:args[args.index(key)+1]
        tmpfs=dict(v.split(':',1) for i,v in enumerate(args) if i and args[i-1]=='--tmpfs')
        label=get('--label').split('=',1)
        c={'Id':'f'*64,'Name':'/'+get('--name'),'Image':IMAGE,
           'Config':{'Labels':dict([label]),'Volumes':None},'State':{'Running':False},
           'HostConfig':{'ReadonlyRootfs':'--read-only' in args,'Memory':1024**3 if get('--memory')=='1g' else 0,
            'MemorySwap':1024**3 if get('--memory-swap')=='1g' else 0,'NanoCpus':int(float(get('--cpus'))*10**9),
            'PidsLimit':int(get('--pids-limit')),'NetworkMode':get('--network'),
            'CapDrop':[get('--cap-drop')],'SecurityOpt':[get('--security-opt')],'Tmpfs':tmpfs,'Binds':None}}
        save('container.json',c);stage('create');print(c['Id']);return
    if op=='start':
        c=cfg();assert c and args[1]==c['Id'];c['State']['Running']=True;save('container.json',c)
        stage('start');print(c['Id']);return
    if op=='rm':
        c=cfg();assert c and args[-1]==c['Id'];(root/'container.json').unlink();save('removed',{'id':c['Id']});return
    if op=='exec':
        c=cfg();assert c and c['State']['Running'] and c['Id'] in args
        if 'tar' in args:
            data=sys.stdin.buffer.read();save('archive-input',{'bytes':len(data)});stage('populate');return
        payload=json.loads(sys.stdin.buffer.read(3*1024**2+1));kind=payload['operation']
        stage(kind)
        mode=(root/'mode').read_text() if (root/'mode').exists() else ''
        if kind=='preflight':
            print(json.dumps(dict(head=HEAD,base=BASE,python=SANDBOX['python'],
                import_path='/testbed/lib/matplotlib/__init__.py',writable=True,limits_verified=True,
                uname=dict(system='INERT',release='INERT',version='INERT',machine='INERT'))));return
        if kind=='diff':print('inert diagnostic diff');return
        if kind=='prepare':
            data,patch,_=inputs();arm=payload['mode'];save('arm',arm)
            diff='' if arm=='baseline' else patch.decode()
            if mode=='wrong-diff':diff+='wrong'
            if mode=='apply-fail':print('fixed setup failure');sys.exit(1)
            print(json.dumps(dict(source_diff=diff,reference_patch_sha256=PATCH_SHA,
                test_patch_sha256=sha(data['test_patch'].encode()),mode=arm,head=HEAD,base=BASE,
                python=SANDBOX['python'],import_path='/testbed/lib/matplotlib/__init__.py',
                omitted_install=OMITTED,untouched_stock_harness=False,test_command=COMMAND,test_paths=TEST_PATHS)));return
        assert kind=='test'
        if mode=='hang':time.sleep(50)
        if mode=='overflow':
            while True:os.write(1,b'x'*65536)
        data,_,_=inputs();arm=json.loads((root/'arm').read_text())
        print('>>>>> Start Test Output',file=sys.stderr,flush=True)
        for t in data['FAIL_TO_PASS']+data['PASS_TO_PASS']:
            outcome='FAILED' if arm=='baseline' and t in data['FAIL_TO_PASS'] else 'PASSED'
            if mode=='unexpected':outcome='PASSED'
            print(outcome+' '+t,file=sys.stderr)
        print('SKIPPED inert/test_extra.py::test_extra',file=sys.stderr)
        print('Ran 675 tests in 0.001s',file=sys.stderr)
        print('>>>>> End Test Output',file=sys.stderr,flush=True)
        sys.exit(1 if arm=='baseline' and mode!='unexpected' else 0)
    raise ValueError('unsupported fake operation')

if __name__=='__main__':main(sys.argv[1],sys.argv[2:])
