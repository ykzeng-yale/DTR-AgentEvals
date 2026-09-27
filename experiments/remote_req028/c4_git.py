"""Explicit one-shot Git transport, exact origin and isolated index publication."""
import json,os,subprocess,tempfile,time
from pathlib import Path
from c2_relay import encode,sha,require,commit_id,path_component
from c2_git import OWNER
from c3_adapter import CONFIG_SHA,validate_release,validate_request
PRODUCTION_ORIGIN='https://github.com/ykzeng-yale/DTR-AgentEvals.git'
class Transport:
    def __init__(self,repo,origin=PRODUCTION_ORIGIN,fixture_root=None):
        self.repo=Path(repo).resolve();self.origin=origin;self.fixture_root=Path(fixture_root).resolve() if fixture_root else None
        if self.fixture_root is None:require(origin==PRODUCTION_ORIGIN,'unauthorized production origin')
        else:require(Path(origin).is_absolute() and Path(origin).resolve().parent==self.fixture_root and self.repo.parent==self.fixture_root,'fixture origin boundary')
        self.deadline=None;self.events=[];self.authorized=None;self.last_response=None;self.used=set();self.failed=False
    def git(self,*args,input=None,env=None):
        remaining=self.deadline-time.monotonic();require(remaining>0,'Git deadline')
        r=subprocess.run(['git',*args],cwd=self.repo,input=input,capture_output=True,env=dict(os.environ,**OWNER,**(env or {})),timeout=remaining)
        self.events.append({'op':args[0],'returncode':r.returncode})
        require(r.returncode==0,'Git operation failed: '+args[0]);return r.stdout
    def start(self,timeout):
        require(not self.failed and timeout>0,'transport failed/deadline');self.deadline=time.monotonic()+timeout
        require(self.git('remote','get-url','origin').decode().strip()==self.origin,'origin changed')
        require(self.git('remote','get-url','--push','origin').decode().strip()==self.origin,'push origin changed')
        require(not self.git('status','--porcelain','--untracked-files=all').strip(),'dirty checkout')
    def fetch(self):
        # Fetch into an owned ref, never update HEAD/index/worktree or origin/main.
        self.git('fetch','--no-tags','--no-write-fetch-head',self.origin,'refs/heads/main:refs/c4/observed-main')
        return self.git('rev-parse','refs/c4/observed-main').decode().strip()
    def object(self,commit,path):
        commit_id(commit);path_component(path)
        require(int(self.git('cat-file','-s',commit+':'+path))<=1024*1024,'Git object size')
        return self.git('show',commit+':'+path)
    def authorize(self,release_raw,release_pin,entry,expected_main,response_path,now,timeout=30):
        try:
            self.start(timeout);r=validate_release(release_raw,release_pin,now)
            require(entry in r['requests'] and entry['sequence'] not in self.used,'unapproved/used request')
            require(r['config_sha256']==CONFIG_SHA,'config');commit_id(expected_main);path_component(response_path)
            require(response_path.startswith('results/remote_req028/c3_'),'response path')
            if self.authorized is None:
                require(entry['sequence']==1 and len(r['requests'])==1 and r['parent_release_sha256'] is None,'initial Git release')
            else:
                old=self.authorized
                require(self.last_response is not None,'prior response not published')
                require(r['parent_release_sha256']==old['pin'],'release parent')
                require(r['requests'][:-1]==old['release']['requests'] and len(r['requests'])==entry['sequence']==len(old['release']['requests'])+1,'release append exactly one')
                for k in ('run_id','config_sha256','deadline','max_calls'):require(r[k]==old['release'][k],'release renewal/change')
            require(self.fetch()==expected_main,'concurrent main advancement')
            self.git('merge-base','--is-ancestor',entry['commit'],expected_main)
            if self.last_response:self.git('merge-base','--is-ancestor',self.last_response['commit'],expected_main)
            raw=self.object(entry['commit'],entry['path']);q=validate_request(raw,r,entry,now)
            if self.last_response:require(q['parent_response_sha256']==self.last_response['sha256'],'response chain')
            self.authorized={'release':r,'pin':release_pin,'entry':entry,'request':q,'raw':raw,'expected_main':expected_main,'response_path':response_path}
            return {'commit':entry['commit'],'path':entry['path'],'raw':raw}
        except BaseException:self.failed=True;raise
    def read(self,commit,path,timeout=30):
        try:
            self.start(timeout);a=self.authorized;require(a and (commit,path)==(a['entry']['commit'],a['entry']['path']),'unapproved object read')
            require(self.fetch()==a['expected_main'],'concurrent main advancement')
            raw=self.object(commit,path);require(sha(raw)==a['entry']['sha256'],'changed request')
            return {'commit':commit,'path':path,'raw':raw}
        except BaseException:self.failed=True;raise
    def publish(self,sequence,raw,timeout=30):
        try:
            self.start(timeout);a=self.authorized
            require(a and sequence==a['entry']['sequence'] and sequence not in self.used,'unapproved/repeated publication')
            require(time.time()<a['request']['expires_at'],'request expired before publication')
            self.used.add(sequence) # once attempted, never replay after uncertainty
            from c3r_envelope import consume
            require('binding_sha256' in a,'missing pre-generation binding approval')
            consume(raw,a['request'],a['entry'],CONFIG_SHA,a['binding_sha256'])
            base=a['expected_main'];require(self.fetch()==base,'concurrent main advancement')
            path=a['response_path'];require(not self.git('ls-tree','-r','--name-only',base,'--',path).strip(),'immutable response conflict')
            with tempfile.TemporaryDirectory(prefix='c4-index-') as tmp:
                env={'GIT_INDEX_FILE':str(Path(tmp)/'index')}
                self.git('read-tree',base,env=env);blob=self.git('hash-object','-w','--stdin',input=raw).decode().strip()
                self.git('update-index','--add','--cacheinfo','100644',blob,path,env=env)
                tree=self.git('write-tree',env=env).decode().strip();new=self.git('commit-tree',tree,'-p',base,input=b'C4 approved response',env=env).decode().strip()
            latest=self.git('ls-remote',self.origin,'refs/heads/main').decode().split()[0];require(latest==base,'concurrent main advancement before push')
            self.git('push',self.origin,new+':refs/heads/main') # ordinary non-force push
            self.last_response={'commit':new,'path':path,'sha256':sha(raw)};return dict(self.last_response)
        except BaseException:self.failed=True;raise
    def approve_native(self,approval_raw,approval_pin,asset_attestation_pin):
        from c4_consumer import APPROVAL_KEYS
        from c2_relay import decode,digest
        require(sha(approval_raw)==digest(approval_pin),'native approval pin');d=decode(approval_raw,APPROVAL_KEYS);a=self.authorized;require(a is not None,'authorize first');require(type(d['protocol']) is int and d['protocol']==3,'native approval protocol')
        expected={'release_sha256':a['pin'],'request_commit':a['entry']['commit'],'request_path':a['entry']['path'],'request_sha256':a['entry']['sha256'],'config_sha256':CONFIG_SHA,'asset_attestation_sha256':asset_attestation_pin,'expires_at':a['request']['expires_at']}
        for k,v in expected.items():require(d[k]==v,'native approval binding '+k)
        a['binding_sha256']=digest(d['binding_sha256'])
