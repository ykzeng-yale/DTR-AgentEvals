"""Optional one-shot Git object transport; no polling, merge, force push or payload execution."""
import os,subprocess,tempfile,time
from pathlib import Path
from c2_relay import MAX_BYTES,Rejected,require,path_component,commit_id
OWNER={'GIT_AUTHOR_NAME':'Yukang Zeng','GIT_AUTHOR_EMAIL':'ykzeng2019@gmail.com','GIT_COMMITTER_NAME':'Yukang Zeng','GIT_COMMITTER_EMAIL':'ykzeng2019@gmail.com'}
class GitTransport:
    def __init__(self,repo,clock=time.time,record=lambda event:None,run=None):
        self.repo=Path(repo);self.clock=clock;self.record=record;self.runner=run or subprocess.run
    def git(self,*args,input=None,env=None):
        result=self.runner(['git',*args],cwd=self.repo,input=input,capture_output=True,env=dict(os.environ,**OWNER,**(env or {})),timeout=30)
        if result.returncode:raise Rejected('git operation failed: '+args[0]) # do not expose credentials/output
        return result.stdout
    def phase(self,name,fn):
        start=self.clock()
        try:return fn()
        finally:self.record({'phase':name,'started':start,'finished':self.clock()})
    def clean(self):
        require(not self.git('status','--porcelain','--untracked-files=all').strip(),'dirty checkout; no pull/publication')
    def fetch_main(self):
        self.clean()
        self.phase('network_fetch',lambda:self.git('fetch','origin','refs/heads/main'))
        commit=self.git('rev-parse','FETCH_HEAD').decode().strip();commit_id(commit);return commit
    def read_object(self,commit,path):
        commit_id(commit);path_component(path)
        # Require membership in the fetched main ancestry, not arbitrary local objects.
        self.git('merge-base','--is-ancestor',commit,'FETCH_HEAD')
        size=int(self.git('cat-file','-s',commit+':'+path))
        require(size<=MAX_BYTES,'object exceeds envelope cap')
        return self.phase('object_read',lambda:self.git('show',commit+':'+path))
    @staticmethod
    def owned(path):
        path_component(path)
        require(path.startswith(('experiments/remote_req028/c2_','results/remote_req028/c2_')),'unowned publication path')
    def publish(self,files,message,expected_main):
        require(type(files) is dict and files,'empty publication')
        commit_id(expected_main)
        for path,raw in files.items():
            self.owned(path);require(type(raw) is bytes and len(raw)<=MAX_BYTES,'publication object size/type')
        self.clean();base=self.fetch_main()
        require(base==expected_main,'concurrent main advancement')
        require(self.git('rev-parse','HEAD').decode().strip()==base,'checkout not latest main')
        # Separate private index; no checkout/source mutation or merge resolution.
        with tempfile.TemporaryDirectory(prefix='c2-index-') as tmp:
            env={'GIT_INDEX_FILE':str(Path(tmp)/'index')}
            self.git('read-tree',base,env=env)
            for path,raw in files.items():
                # Existing records cannot be overwritten, even with a valid new envelope.
                listing=self.git('ls-tree','-r','--name-only',base,'--',path).decode().splitlines()
                if path in listing:
                    require(self.git('show',base+':'+path)==raw,'modified immutable Git record')
                    continue
                blob=self.git('hash-object','-w','--stdin',input=raw).decode().strip()
                self.git('update-index','--add','--cacheinfo','100644',blob,path,env=env)
            tree=self.git('write-tree',env=env).decode().strip()
            new=self.git('commit-tree',tree,'-p',base,input=message.encode()).decode().strip()
        latest=self.phase('network_check_main',lambda:self.git('ls-remote','origin','refs/heads/main')).decode().split()[0]
        require(latest==base,'concurrent main advancement before push')
        # A race after this check is rejected by the ordinary non-force push.
        self.phase('network_publication',lambda:self.git('push','origin',new+':refs/heads/main'))
        return new
