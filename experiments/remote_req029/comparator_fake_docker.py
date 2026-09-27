"""Test-owned inert Docker-shaped executable. Never evaluates command strings."""
import json,os,sys,time
from pathlib import Path
from comparator_contract import require

def main(root,args):
    root=Path(root);root.mkdir(parents=True,exist_ok=True)
    contract=json.loads((root/'contract.json').read_bytes());IMAGE=contract['image'];HEAD=contract['head']
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
        if (root/'foreign').exists():c['Config']['Labels']['dtr.c6.owner']='foreign'
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
        payload=json.loads(sys.stdin.buffer.read(65537));kind=payload['operation']
        assert payload['task_head']==HEAD and payload['import_module']==contract['import_module'],'task substitution'
        if kind=='preflight':
            print(json.dumps({'head':HEAD,'python':'/opt/miniconda3/envs/testbed/bin/python',
                'import_path':'/testbed/'+contract['import_module']+'/__init__.py','writable':True,'limits_verified':True}));return
        if kind=='diff':print('diff --git a/fake b/fake\n+diagnostic only');return
        assert kind=='execute';save('action-'+str(time.time_ns()),payload);stage('execute')
        command=payload['command'] # DATA ONLY. Never exec/eval/shell.
        if command=='hang':time.sleep(50)
        elif command=='overflow':
            while True:os.write(1,b'x'*65536)
        elif command=='fixture-submit':print('\nCOMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\npinned payload')
        elif command=='exit1':print('ordinary exit-one output');sys.exit(1)
        elif command=='nonzero-submit':print('COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\nnot submitted');sys.exit(1)
        else:print('fixed observation')
        return
    raise ValueError('unsupported fake operation')

if __name__=='__main__':main(sys.argv[1],sys.argv[2:])
