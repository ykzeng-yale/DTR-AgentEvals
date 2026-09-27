"""Synthetic C2 envelopes. Payload strings are data, never executable instructions."""
import datetime,hashlib,json,math,os,re
from pathlib import Path
MAX_BYTES=1024*1024
REQUEST_KEYS={'protocol','run_id','sequence','request_id','parent_response_sha256','body','body_sha256','config_sha256','expires_at','synthetic_only'}
RESPONSE_KEYS={'protocol','run_id','sequence','request_id','request_commit','body_sha256','config_sha256','response','response_sha256','status','receipt_time','elapsed_seconds','timings','synthetic_only'}
class Rejected(ValueError):pass
class Indeterminate(RuntimeError):pass
def require(ok,why):
    if not ok:raise Rejected(why)
def sha(data):return hashlib.sha256(data).hexdigest()
def encode(obj):
    data=json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
    require(len(data)<=MAX_BYTES,'envelope too large');return data
def decode(raw,keys):
    require(type(raw) is bytes and len(raw)<=MAX_BYTES,'envelope bytes/size')
    def pairs(items):
        d={}
        for k,v in items:
            require(k not in d,'duplicate JSON key');d[k]=v
        return d
    try:d=json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=lambda x:(_ for _ in ()).throw(Rejected('nonfinite JSON')))
    except (UnicodeError,json.JSONDecodeError) as e:raise Rejected('invalid UTF8/JSON') from e
    require(type(d) is dict and set(d)==keys,'unknown/missing fields');return d
def identifier(value):
    require(type(value) is str and re.fullmatch(r'[a-z0-9][a-z0-9-]{0,79}',value) is not None,'unsafe ID');return value
def digest(value):
    require(type(value) is str and re.fullmatch(r'[0-9a-f]{64}',value) is not None,'invalid SHA256');return value
def number(value):
    require(type(value) in (int,float) and math.isfinite(value) and value>=0,'invalid timing');return value
def commit_id(value):
    require(type(value) is str and re.fullmatch(r'(?:[0-9a-f]{40}|[0-9a-f]{64})',value) is not None,'invalid commit');return value
def path_component(path):
    require(type(path) is str and 0<len(path)<=240 and not path.startswith('/'),'unsafe path')
    require(all(re.fullmatch(r'[a-zA-Z0-9_-][a-zA-Z0-9_.-]*',x) and x not in ('.','..') for x in path.split('/')),'unsafe path')
    return path
def expiry(value):
    require(type(value) is str and re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ',value) is not None,'expiry must be exact UTC')
    try:return datetime.datetime.strptime(value,'%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=datetime.timezone.utc).timestamp()
    except ValueError as e:raise Rejected('invalid expiry') from e
def common(d):
    require(type(d['protocol']) is int and d['protocol']==1 and d['synthetic_only'] is True,'not C2 synthetic protocol')
    identifier(d['run_id']);identifier(d['request_id'])
    require(type(d['sequence']) is int and 1<=d['sequence']<=1000000,'invalid sequence')
    require(d['request_id']==d['run_id']+'-'+str(d['sequence']),'request ID/sequence mismatch')
    digest(d['body_sha256']);digest(d['config_sha256'])
def validate_request(raw,now):
    d=decode(raw,REQUEST_KEYS);common(d);number(now)
    require(type(d['body']) is str,'body must be UTF8 JSON string')
    try:body=d['body'].encode('utf-8')
    except UnicodeError as e:raise Rejected('invalid body Unicode') from e
    require(sha(body)==d['body_sha256'],'body SHA mismatch')
    require(now<expiry(d['expires_at']),'expired request')
    if d['sequence']==1:require(d['parent_response_sha256'] is None,'first parent must be null')
    else:digest(d['parent_response_sha256'])
    return d
def validate_response(raw,request,request_commit,now):
    d=decode(raw,RESPONSE_KEYS);common(d);commit_id(request_commit);number(now)
    for key in ('run_id','sequence','request_id','body_sha256','config_sha256'):require(d[key]==request[key],'response '+key+' mismatch')
    require(d['request_commit']==request_commit,'request commit mismatch')
    require(type(d['response']) is str,'response must be UTF8 string')
    try:body=d['response'].encode('utf-8')
    except UnicodeError as e:raise Rejected('invalid response Unicode') from e
    require(sha(body)==digest(d['response_sha256']),'response SHA mismatch')
    require(d['status'] in ('ok','error','indeterminate') and type(d['status']) is str,'invalid status')
    number(d['receipt_time']);number(d['elapsed_seconds'])
    require(d['receipt_time']<=now<expiry(request['expires_at']),'stale/future response')
    require(type(d['timings']) is dict and set(d['timings'])=={'network_seconds','queue_seconds','dispatch_seconds'},'invalid phase fields')
    for v in d['timings'].values():number(v)
    require(d['elapsed_seconds']==sum(d['timings'].values()),'elapsed/phase mismatch')
    return d
class FileStore:
    """Local trusted journal, exclusive creation and fsync; no symlink traversal."""
    def __init__(self,root):
        self.root=Path(root).resolve();self.root.mkdir(parents=True,exist_ok=True)
        self.sync_dir(self.root.parent)
    @staticmethod
    def sync_dir(path):
        fd=os.open(path,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
    def target(self,name):
        path_component(name);p=self.root/name
        cur=self.root
        for part in Path(name).parts:
            cur=cur/part;require(not cur.is_symlink(),'symlink journal path')
        require(p.resolve().is_relative_to(self.root),'journal path escape')
        return p
    def read(self,name):
        p=self.target(name);return p.read_bytes() if p.exists() else None
    def write_exclusive(self,name,data):
        p=self.target(name)
        current=self.root
        for part in Path(name).parts[:-1]:
            parent=current;current=current/part
            current.mkdir(exist_ok=True);self.sync_dir(parent)
        try:fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        except FileExistsError:return False
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        fd=os.open(p.parent,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
        return True
class Relay:
    """Injected callbacks must implement durable atomic exclusive writes.

    No model callback is supplied by this release. A pre-existing claim without a
    sealed result is indeterminate, even when dispatch never happened.
    """
    def __init__(self,read,write_exclusive,clock):
        self.read=read;self.write=write_exclusive;self.clock=clock
    def immutable(self,name,data):
        if not self.write(name,data):require(self.read(name)==data,'conflicting immutable record')
    def sealed(self,base):
        raw=self.read(base+'.response.json');seal=self.read(base+'.seal')
        if raw is None or seal is None:raise Indeterminate('claim exists without sealed result; never redispatch')
        require(seal==sha(raw).encode(),'modified immutable response');return raw
    def dispatch_once(self,raw,request_commit,dispatch,network_seconds=0,queued_at=None,after_claim=lambda:None):
        now=self.clock();req=validate_request(raw,now);commit_id(request_commit);number(network_seconds)
        queued_at=now if queued_at is None else number(queued_at);require(queued_at<=now,'future queue')
        base=req['run_id']+'/'+str(req['sequence'])
        if req['sequence']>1:
            previous=self.sealed(req['run_id']+'/'+str(req['sequence']-1))
            prev=decode(previous,RESPONSE_KEYS)
            require(prev['run_id']==req['run_id'] and prev['sequence']==req['sequence']-1 and prev['status']=='ok','nonserial sequence')
            require(sha(previous)==req['parent_response_sha256'],'parent mismatch')
            require(prev['config_sha256']==req['config_sha256'],'config changed within run')
        claim=encode({'request_sha256':sha(raw),'request_commit':request_commit,'request':req,'state':'claimed_indeterminate_until_sealed'})
        if not self.write(base+'.claim.json',claim):
            require(self.read(base+'.claim.json')==claim,'conflicting duplicate request')
            response=self.sealed(base);validate_response(response,req,request_commit,self.clock());return response
        self.immutable(base+'.queue_receipt.json',encode({'network_seconds':network_seconds,'queued_at':queued_at,'claimed_at':now}))
        # The exclusive claim is durable BEFORE any dispatch callback can run.
        after_claim()
        start=self.clock();require(start<expiry(req['expires_at']),'deadline before dispatch')
        self.immutable(base+'.dispatch_start.json',encode({'started':start,'queue_seconds':start-queued_at}))
        try:
            text=dispatch(req['body'])
            finish=self.clock()
            require(finish>=start and finish<expiry(req['expires_at']),'deadline during dispatch')
            require(type(text) is str,'dispatch response must be text')
            phases={'network_seconds':network_seconds,'queue_seconds':start-queued_at,'dispatch_seconds':finish-start}
            response=encode({'protocol':1,'run_id':req['run_id'],'sequence':req['sequence'],'request_id':req['request_id'],'request_commit':request_commit,'body_sha256':req['body_sha256'],'config_sha256':req['config_sha256'],'response':text,'response_sha256':sha(text.encode()),'status':'ok','receipt_time':finish,'elapsed_seconds':sum(phases.values()),'timings':phases,'synthetic_only':True})
            validate_response(response,req,request_commit,finish)
            self.immutable(base+'.response.json',response)
            self.immutable(base+'.seal',sha(response).encode())
            return response
        except BaseException as e:
            self.immutable(base+'.indeterminate.json',encode({'request_id':req['request_id'],'state':'indeterminate','error_type':type(e).__name__,'dispatch_started':start,'observed_at':self.clock()}))
            raise
    def accept_response(self,raw,request_raw,request_commit):
        req=validate_request(request_raw,self.clock());validate_response(raw,req,request_commit,self.clock())
        self.immutable(req['run_id']+'/'+str(req['sequence'])+'.accepted.json',raw)
        return raw
def frozen_nonce():
    text='DTR_C2_NONCE_20260927'
    return encode({'protocol':1,'run_id':'req028-c2-20260927','sequence':1,'request_id':'req028-c2-20260927-1','parent_response_sha256':None,'body':text,'body_sha256':sha(text.encode()),'config_sha256':sha(b'fixture-only-v1'),'expires_at':'2026-09-27T08:30:00Z','synthetic_only':True})
