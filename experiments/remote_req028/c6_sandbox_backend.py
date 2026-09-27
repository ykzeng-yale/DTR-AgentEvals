"""Fixed W2R Docker boundary. Constructor injection is for test-owned code ONLY."""
import hashlib,json,os,re,time,select,signal,subprocess
from pathlib import Path
from c6_protocol import ROOT,IMAGE,HEAD,put,require,sha
from c6_process import Runner
from c6_container_helper import CODE
DOCKER='/Users/yukangzengcmac/.local/dtr-runtime/bin/docker'
ARCHIVE=ROOT/'work/local_req028/c6_writable_w2r_20260927/testbed.tar'
ARCHIVE_SHA='792ffe4a936f4e0561011f13405c134bcda00ece6cdc9a0a57a130040e98de6e'
ARCHIVE_BYTES=99788288
RESERVE=15
LIMITS={'ReadonlyRootfs':True,'Memory':1024**3,'MemorySwap':1024**3,'NanoCpus':10**9,
        'PidsLimit':128,'NetworkMode':'none','CapDrop':['ALL'],'SecurityOpt':['no-new-privileges'],
        'Tmpfs':{'/testbed':'rw,exec,nosuid,nodev,size=512m','/tmp':'rw,nosuid,nodev,size=64m'},'Binds':None}

class Docker:
    def __init__(self,root,contract):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.runner=Runner(self.root/'process');self.prefix=[DOCKER,'--context','colima-dtr']
        self.archive=ARCHIVE;self.archive_sha=ARCHIVE_SHA;self.archive_bytes=ARCHIVE_BYTES
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
        image=json.loads(self.call(['image','inspect',IMAGE],deadline)['output'])[0]
        require(image['Id']==IMAGE and image['Os']=='linux' and image['Architecture']=='amd64','image platform')
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
        argv=['create','--pull=never','--name',name,'--label','dtr.c6.owner='+label,'--platform','linux/amd64',
            '--cpus','1','--memory','1g','--memory-swap','1g','--pids-limit','128','--network','none',
            '--cap-drop','ALL','--security-opt','no-new-privileges','--read-only',
            '--tmpfs','/testbed:rw,exec,nosuid,nodev,size=512m','--tmpfs','/tmp:rw,nosuid,nodev,size=64m',
            IMAGE,'/bin/sleep',str(lifetime)]
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
        require(cfg['Name']=='/'+name and cfg['Image']==IMAGE and
                cfg['Config']['Labels'].get('dtr.c6.owner')==label,'foreign container identity')
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
            '/opt/miniconda3/envs/testbed/bin/python','-I','-c',CODE],min(deadline,time.time()+60),
            env=self.env,clean_env=True,stdin_path=path,cap=cap,accept_nonzero=True)

    def populate(self,cid,deadline):
        self.call(['exec','-i',cid,'tar','-xf','-','-C','/testbed'],deadline,stdin=self.archive)

    def remove(self,cid,deadline):
        self.call(['rm','-f',cid],deadline)
        require(self.inspect(cid,deadline) is None,'container removal unconfirmed')
