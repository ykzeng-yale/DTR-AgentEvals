"""One offline image import from verified data; never create/start a container."""
import gzip,hashlib,io,json,os,resource,shutil,signal,subprocess,tarfile,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
DOCKER='/Users/yukangzengcmac/.local/dtr-runtime/bin/docker'
COLIMA='/Users/yukangzengcmac/.local/dtr-runtime/bin/colima'
TAG='dtr-owned/req029-django-16560:20260927'
IMAGE='sha256:86afcd19b6c56e5e271a1dfc62177cf03157fe9c9643be560db11480b317cb27'
OUT=ROOT/'work/local_req029/django_image_import_20260927'
META=ROOT/'results/local_req029/image_metadata_20260927'
LAYERS=ROOT/'work/local_req029/django_image_layers_20260927'
class HashReader:
    def __init__(self,f):self.f=f;self.h=hashlib.sha256();self.n=0
    def read(self,n):
        b=self.f.read(n);self.h.update(b);self.n+=len(b);return b

def pack(path,config,records,layer_root,tag):
    """Legacy Docker archive: exact config + uncompressed verified layer streams."""
    cfgname=hashlib.sha256(config).hexdigest()+'.json'
    names=[r['compressed_sha256'][7:]+'/layer.tar' for r in records]
    with tarfile.open(path,'w') as tar:
        def add(name,data):
            info=tarfile.TarInfo(name);info.size=len(data);info.mode=0o600
            tar.addfile(info,io.BytesIO(data))
        add(cfgname,config)
        add('manifest.json',json.dumps([{'Config':cfgname,'RepoTags':[tag],'Layers':names}]).encode())
        for r,name in zip(records,names):
            p=layer_root/(r['compressed_sha256'][7:]+'.gz')
            h=hashlib.sha256()
            with p.open('rb') as f:
                for b in iter(lambda:f.read(1024**2),b''):h.update(b)
            assert 'sha256:'+h.hexdigest()==r['compressed_sha256']
            assert p.stat().st_size==r['compressed_bytes']
            with gzip.open(p,'rb') as f:
                reader=HashReader(f);info=tarfile.TarInfo(name);info.size=r['uncompressed_bytes'];info.mode=0o600
                tar.addfile(info,reader);assert reader.read(1)==b''
                assert reader.n==r['uncompressed_bytes'] and 'sha256:'+reader.h.hexdigest()==r['diff_id']
    return path.stat().st_size

def run():
    OUT.mkdir(parents=True,exist_ok=False);start=time.monotonic();child=None;result={'image':IMAGE,'tag':TAG,'container_created':False,'network_download':False};samples=[]
    def command(args,allow=False):
        p=subprocess.run(args,capture_output=True,text=True,timeout=15)
        assert allow or p.returncode==0,p.stderr
        return p
    prefix=[DOCKER,'--context','colima-dtr']
    def guard():
        assert time.monotonic()-start<600,'total import deadline'
        assert shutil.disk_usage(ROOT).free>=12*1024**3,'host reserve'
        assert command(['sysctl','-n','kern.memorystatus_vm_pressure_level']).stdout.strip()=='1','memory pressure'
        import re
        free=int(re.search(r'System-wide memory free percentage: (\d+)%',command(['memory_pressure']).stdout)[1]);assert free>=40,'host free'
        samples.append({'elapsed':time.monotonic()-start,'free_percent':free,'disk_free':shutil.disk_usage(ROOT).free})
    try:
        guard();assert not command(prefix+['ps','-aq']).stdout.strip(),'peer containers'
        assert command(prefix+['image','inspect',IMAGE],True).returncode!=0,'image already present; no repeated import'
        assert command(prefix+['image','inspect',TAG],True).returncode!=0,'tag already present'
        before=command(prefix+['image','ls','--no-trunc','--format','{{.Repository}}:{{.Tag}} {{.ID}}']).stdout
        (OUT/'images.before.txt').write_text(before)
        env=dict(os.environ,PATH=str(Path(COLIMA).parent)+os.pathsep+os.environ.get('PATH',''))
        vm=subprocess.run([COLIMA,'-p','dtr','ssh','--','df','-Pk','/var/lib/docker'],env=env,capture_output=True,text=True,timeout=15)
        assert vm.returncode==0 and int(vm.stdout.splitlines()[-1].split()[3])*1024>=22*1024**3,'VM reserve plus import allowance'
        result['vm_df_before']=vm.stdout
        verification=json.loads((ROOT/'results/local_req029/image_acquisition_20260927/verification.json').read_text())
        config=(META/'django__django-16560.config.json').read_bytes();assert 'sha256:'+hashlib.sha256(config).hexdigest()==IMAGE
        records=verification['records'];assert len(records)==10 and sum(x['uncompressed_bytes'] for x in records)==3130309632
        assert [r['diff_id'] for r in records]==json.loads(config)['rootfs']['diff_ids']
        archive=OUT/'image.tar';result['archive_bytes']=pack(archive,config,records,LAYERS,TAG)
        assert result['archive_bytes']<4*1024**3
        guard();assert not command(prefix+['ps','-aq']).stdout.strip(),'peer containers before load'
        with (OUT/'load.log').open('xb') as log:
            child=subprocess.Popen(prefix+['image','load','--platform','linux/amd64','--input',str(archive)],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            result['load_pid']=child.pid;(OUT/'load.handle.json').write_text(json.dumps(result)+'\n')
            end=time.monotonic()+300
            while child.poll() is None:
                guard();assert time.monotonic()<end,'load client deadline';time.sleep(1)
            assert child.returncode==0,'Docker load failed'
        image=json.loads(command(prefix+['image','inspect',TAG]).stdout)[0]
        (OUT/'image.inspect.json').write_text(json.dumps(image,indent=2)+'\n')
        assert image['Id']==IMAGE and image['Os']=='linux' and image['Architecture']=='amd64','imported image identity'
        assert image['RootFS']['Layers']==json.loads(config)['rootfs']['diff_ids'],'imported rootfs'
        assert not command(prefix+['ps','-aq']).stdout.strip(),'unexpected containers'
        after=command(prefix+['image','ls','--no-trunc','--format','{{.Repository}}:{{.Tag}} {{.ID}}']).stdout
        assert set(before.splitlines())<=set(after.splitlines()),'peer tag inventory changed'
        (OUT/'images.after.txt').write_text(after);(OUT/'image.inspect.json').write_text(json.dumps(image,indent=2)+'\n')
        result.update(success=True,rootfs_verified=True,peer_tags_preserved=True)
    except BaseException as e:
        result.update(success=False,error=repr(e),daemon_state_may_be_indeterminate=child is not None)
    finally:
        if child is not None and child.poll() is None:
            os.killpg(child.pid,signal.SIGTERM)
            try:child.wait(timeout=3)
            except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=3)
        result.update(elapsed_seconds=time.monotonic()-start,samples=samples,no_retry=True,load_returncode=None if child is None else child.returncode)
        (OUT/'terminal.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('samples','vm_df_before')}))
    return result['success']
if __name__=='__main__':
    def timeout(*args):raise TimeoutError('600 second hard client alarm')
    signal.signal(signal.SIGALRM,timeout);signal.alarm(600);resource.setrlimit(resource.RLIMIT_CPU,(180,180));os.nice(10)
    raise SystemExit(0 if run() else 1)
