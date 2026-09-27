"""One-shot pinned Django OCI layer acquisition as DATA, never Docker/extraction."""
import hashlib,json,os,re,shutil,subprocess,time,urllib.request,urllib.parse,resource,signal
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
META=ROOT/'results/local_req029/image_metadata_20260927'
TASK='django__django-16560'
DIGEST='sha256:0bafff953ce186aa261162d4091549fb4ad49df938900474b5f070d511bb1604'
REPO='swebench/sweb.eval.x86_64.django_1776_django-16560'
LIMIT=1536*1024**2
RATE=10*1024**2
class NoAuthRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if not newurl.startswith('https://'):raise ValueError('non-HTTPS redirect')
        r=super().redirect_request(req,fp,code,msg,headers,newurl)
        r.remove_header('Authorization')
        return r
def manifest(raw):
    assert 'sha256:'+hashlib.sha256(raw).hexdigest()==DIGEST,'manifest pin'
    m=json.loads(raw);assert len(m['layers'])==10
    assert sum(x['size'] for x in m['layers'])==1240896221
    for x in m['layers']:
        assert re.fullmatch('sha256:[0-9a-f]{64}',x['digest']) and type(x['size']) is int and x['size']>0
    return m
class Budget:
    def __init__(self,root,seconds=900):self.root=root;self.start=time.monotonic();self.end=self.start+seconds;self.bytes=0;self.samples=[];self.last=-1e9
    def check(self,n=0):
        now=time.monotonic();assert now<self.end,'900 second deadline';self.bytes+=n;assert self.bytes<=LIMIT,'1.5GiB response-body cap'
        assert shutil.disk_usage(self.root).free>=12*1024**3,'12GiB disk reserve'
        if now-self.last>=5:
            p=subprocess.run(['sysctl','-n','kern.memorystatus_vm_pressure_level'],capture_output=True,text=True,timeout=2);assert p.returncode==0 and p.stdout.strip()=='1','normal pressure required'
            p=subprocess.run(['memory_pressure'],capture_output=True,text=True,timeout=2);assert p.returncode==0
            free=int(re.search(r'System-wide memory free percentage: (\d+)%',p.stdout)[1]);assert free>=40,'40% host free'
            self.samples.append({'elapsed':now-self.start,'free_percent':free,'disk_free':shutil.disk_usage(self.root).free});self.last=now
    def throttle(self,begin,received):
        while True:
            self.check()
            delay=received/RATE-(time.monotonic()-begin)
            if delay<=0:return
            time.sleep(min(delay,.1))
def run(root,open_url=None):
    root.mkdir(parents=True,exist_ok=False);budget=Budget(root);records=[];error=None
    opener=open_url or urllib.request.build_opener(NoAuthRedirect()).open
    try:
        budget.check();m=manifest((META/(TASK+'.amd64.json')).read_bytes())
        auth='https://auth.docker.io/token?'+urllib.parse.urlencode({'service':'registry.docker.io','scope':'repository:'+REPO+':pull'})
        with opener(auth,timeout=10) as f:raw=f.read(65537)
        assert len(raw)<=65536,'auth cap';budget.check(len(raw));token=json.loads(raw)['token']
        for layer in m['layers']:
            budget.check();digest=layer['digest'];path=root/(digest.split(':')[1]+'.partial');h=hashlib.sha256();count=0;beg=time.monotonic()
            req=urllib.request.Request('https://registry-1.docker.io/v2/'+REPO+'/blobs/'+digest,headers={'Authorization':'Bearer '+token})
            with opener(req,timeout=10) as response,path.open('xb') as out:
                while True:
                    budget.check();block=response.read(min(65536,layer['size']-count+1))
                    if not block:break
                    count+=len(block);assert count<=layer['size'],'layer size exceeded';budget.check(len(block));out.write(block);h.update(block);budget.throttle(beg,count)
                out.flush();os.fsync(out.fileno())
            assert count==layer['size'] and 'sha256:'+h.hexdigest()==digest,'layer digest/length mismatch'
            path.rename(path.with_suffix('.gz'));records.append({'digest':digest,'bytes':count,'seconds':time.monotonic()-beg})
            (root/'progress.json').write_text(json.dumps({'completed':records,'response_body_bytes':budget.bytes})+'\n')
    except BaseException as e:error=type(e).__name__+': '+str(e)
    result={'task':TASK,'manifest_digest':DIGEST,'completed_layers':records,'error':error,'response_body_bytes':budget.bytes,'elapsed_seconds':time.monotonic()-budget.start,'samples':budget.samples,'no_retry':True,'data_only':True,'docker_invoked':False,'layers_extracted':False,'rate_limit_bytes_per_second':RATE,'rss_limit_note':'streaming64KiB buffers; no hard macOS address-space limit claimed','cpu_seconds_cap':300}
    (root/'terminal.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
    import sys
    resource.setrlimit(resource.RLIMIT_CPU,(300,300));os.nice(10)
    def alarm(*args):raise TimeoutError('absolute 900 second acquisition deadline')
    signal.signal(signal.SIGALRM,alarm);signal.alarm(900)
    r=run(Path(sys.argv[1]));print(json.dumps({'error':r['error'],'layers':len(r['completed_layers']),'bytes':r['response_body_bytes']}));sys.exit(bool(r['error']))
