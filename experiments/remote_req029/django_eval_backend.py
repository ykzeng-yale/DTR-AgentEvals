"""Fixed W2R Docker boundary. Constructor injection is for test-owned code ONLY."""
import hashlib,json,os,re,time,select,signal,subprocess,math
from pathlib import Path
from django_eval_contract import ROOT,put,require,sha,OUTPUT_CAP,PATCH_CAP,LIMITS,RESERVE,DOCKER
from django_eval_process import Runner
from django_eval_container import CODE

class Backend:
    def __init__(self,root,contract):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.runner=Runner(self.root/'process');self.prefix=[DOCKER,'--context','colima-dtr']
        self.archive=ROOT/contract['archive_path'];self.archive_sha=contract['archive_sha256'];self.archive_bytes=contract['archive_bytes']
        self.contract=contract;self.counter=0;self.cleaning=False
        self.env={k:os.environ[k] for k in ('HOME',) if k in os.environ}
        self.env.update(PATH='/usr/bin:/bin:/usr/sbin:/sbin',LANG='C',LC_ALL='C')

    def verify(self,deadline):
        require(self.contract['docker_executable']==DOCKER,'fixed Docker executable')
        require(sha(Path(DOCKER).read_bytes())==self.contract['docker_sha256'],'Docker binary pin')
        require(self.archive.stat().st_size==self.archive_bytes,'archive bytes')
        h=hashlib.sha256()
        with self.archive.open('rb') as f:
            for block in iter(lambda:f.read(1024*1024),b''):
                require(time.time()<deadline,'archive hash deadline');h.update(block)
        require(h.hexdigest()==self.archive_sha,'archive hash')
        image=json.loads(self.call(['image','inspect',self.contract['image']],deadline)['output'])[0]
        require(image['Id']==self.contract['image'] and image['Os']=='linux' and image['Architecture']=='amd64','image platform')
        require(not self.call(['ps','-aq'],deadline)['output'].strip(),'peer containers present')

    def call(self,args,deadline,stdin=None,nonzero=False,cap=1024*1024):
        if self.cleaning:
            return self.emergency(args,deadline,nonzero)
        return self.runner.run(self.prefix+args,min(deadline,time.time()+20),
            env=self.env,clean_env=True,stdin_path=stdin,cap=cap,accept_nonzero=nonzero)

    def emergency(self,args,deadline,nonzero=False):
        """Cleanup-only fixed inspect/rm. No audit file is needed to launch it."""
        require(args[0] in ('inspect','rm'),'cleanup command allowlist')
        require(time.time()<deadline,'cleanup reserve exhausted')
        p=subprocess.Popen(self.prefix+args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,env=self.env,start_new_session=True)
        data=bytearray();end=min(deadline,time.time()+5)
        try:
            while True:
                require(time.time()<end,'cleanup process deadline')
                if not select.select([p.stdout],[],[],.02)[0]:continue
                block=os.read(p.stdout.fileno(),65536)
                if not block:break
                require(len(data)+len(block)<=65536,'cleanup output cap');data.extend(block)
            code=p.wait(timeout=max(.001,end-time.time()))
            require(nonzero or code==0,'cleanup Docker returncode')
            return {'returncode':code,'output':data.decode(errors='replace')}
        finally:
            if p.returncode is None:
                try:os.killpg(p.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                p.wait(timeout=2)
            p.stdout.close()

    def create(self,name,label,deadline,lifetime):
        argv=['create','--pull=never','--name',name,'--label','dtr.req029i.owner='+label,'--platform','linux/amd64',
            '--cpus','1','--memory','1g','--memory-swap','1g','--pids-limit','128','--network','none',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--read-only',
            '--tmpfs','/testbed:rw,exec,nosuid,nodev,size=512m','--tmpfs','/tmp:rw,nosuid,nodev,size=64m',
            self.contract['image'],'/bin/sleep',str(min(lifetime,max(1,math.ceil(deadline+RESERVE-time.time()))))]
        cid=self.call(argv,deadline)['output'].strip()
        require(re.fullmatch('[0-9a-f]{64}',cid),'full container identity')
        return cid

    def inspect(self,target,deadline):
        r=self.call(['inspect',target],deadline,nonzero=True)
        if r['returncode']:
            require('no such' in r['output'].lower(),'ambiguous inspect failure')
            return None
        value=json.loads(r['output']);require(len(value)==1,'one container')
        return value[0]

    def owned(self,cfg,name,label,cid=None):
        require(cfg is not None,'owned sandbox absent')
        require(re.fullmatch('[0-9a-f]{64}',cfg['Id']),'full CID')
        require(cid is None or cfg['Id']==cid,'CID substitution')
        require(cfg['Name']=='/'+name and cfg['Image']==self.contract['image'] and
                cfg['Config']['Labels'].get('dtr.req029i.owner')==label,'foreign container identity')
        return cfg['Id']

    def limits(self,cfg):
        require(all(cfg['HostConfig'].get(k)==v for k,v in LIMITS.items()),'W2R limits differ')
        require(not cfg['HostConfig'].get('Privileged') and not cfg['HostConfig'].get('Devices'), 'extra privilege')
        require(not cfg['HostConfig'].get('Mounts') and not cfg['HostConfig'].get('VolumesFrom'),'extra mounts')
        require(not cfg['Config'].get('Volumes'),'image declared host volumes')

    def helper(self,cid,op,payload,deadline,cap=1024*1024):
        self.counter+=1;path=self.root/('stdin-%04d.json'%self.counter)
        put(self.root,path.name,dict(payload,operation=op))
        # Command data is stdin only. CODE is fixed reviewed helper source.
        return self.runner.run(self.prefix+['exec','-i','-w','/testbed',cid,
            self.contract['python'],'-I','-c',CODE],min(deadline,time.time()+60),
            env=self.env,clean_env=True,stdin_path=path,cap=cap,accept_nonzero=True)

    def evaluate(self,cid,op,payload,deadline):
        require(op in ('prepare','test'),'fixed evaluator operation')
        self.counter+=1;path=self.root/('eval-stdin-%04d.json'%self.counter)
        raw=json.dumps(dict(payload,operation=op)).encode()
        require(len(raw)<=3*PATCH_CAP,'patch payload cap');put(self.root,path.name,raw)
        return self.runner.run(self.prefix+['exec','-i','-w','/testbed',cid,
            self.contract['python'],'-I','-c',CODE],deadline,
            env=self.env,clean_env=True,stdin_path=path,cap=OUTPUT_CAP,accept_nonzero=True)

    def populate(self,cid,deadline):
        self.call(['exec','-i',cid,'tar','-xf','-','-C','/testbed'],deadline,stdin=self.archive)

    def remove(self,cid,deadline):
        self.call(['rm','-f',cid],deadline)
        require(self.inspect(cid,deadline) is None,'container removal unconfirmed')
