"""Finite append-only relay. Unrelated main advancement is acceptable.

Publication gets one fresh parent and one ordinary push; any race/ambiguity ends
the run. It never retries a physical model/action or an uncertain push.
"""
import json
import os
import tempfile
import time
from pathlib import Path
from c2_git import OWNER
from c6_protocol import ORIGIN, encode, sha, require, commit
from c6_process import Runner

class Transport:
    def __init__(self, repo, root, run_root, role, deadline, origin=ORIGIN, fixture_root=None, interval=5):
        self.repo, self.root = Path(repo).resolve(), Path(root)
        self.run_root, self.role, self.deadline = run_root, role, deadline
        self.origin, self.interval = origin, interval
        self.fixture_root = fixture_root
        if fixture_root is None:
            require(origin==ORIGIN and interval>=5, 'production relay')
        else:
            f=Path(fixture_root).resolve()
            require(Path(origin).resolve().parent==f and self.repo.parent==f, 'local fixture only')
        require(role in ('controller','worker'), 'role')
        require(run_root.startswith('results/remote_req028/c6_runs/c6-') and '..' not in Path(run_root).parts, 'owned root')
        self.runner = Runner(self.root/'process')
        self.fetches = 0
        self.last_fetch = 0
        self.seen = {}
        self.failed = False
        self.events = []
        self.git('remote','get-url','origin', expected=origin+'\n')
        self.git('remote','get-url','--push','origin', expected=origin+'\n')

    def git(self, *args, expected=None, env=None, nonzero=False):
        require(not self.failed, 'transport poisoned')
        r = self.runner.run(['git',*args], min(self.deadline,time.time()+30), self.repo,
                            dict(OWNER,**(env or {})),accept_nonzero=nonzero)
        if expected is not None:
            require(r['output']==expected, 'Git exact value')
        return r

    def path(self, kind, seq=None):
        owners={'request':'controller','observation':'controller','response':'worker',
                'preflight':'controller','ready':'worker','controller_terminal':'controller','worker_terminal':'worker'}
        require(kind in owners, 'artifact kind')
        require((seq is None and kind not in ('request','response','observation')) or
                (type(seq) is int and 1<=seq<=24 and kind in ('request','response','observation')), 'sequence path')
        return self.run_root+'/'+kind+('' if seq is None else '/%02d'%seq)+'.json',owners[kind]

    def fetch(self):
        require(not self.failed and self.fetches<360, 'fetch cap')
        while time.time()<self.last_fetch+self.interval:
            self.runner.check()
            require(time.time()<self.deadline, 'queue deadline')
            time.sleep(min(.05,self.last_fetch+self.interval-time.time()))
        started=time.time()
        self.fetches+=1
        self.last_fetch=started
        self.git('fetch','--quiet','--no-tags','--no-write-fetch-head',self.origin,
                 'refs/heads/main:refs/c6/observed-main')
        base=self.git('rev-parse','refs/c6/observed-main')['output'].strip()
        commit(base)
        for path,raw in self.seen.items():
            require(self.object(base,path)==raw,'owned artifact changed or removed')
        self.events.append(dict(phase='fetch',started=started,finished=time.time(),commit=base,
                                transfer_bytes=None,transfer_bytes_reason='Git does not report exact wire bytes'))
        return base

    def object(self, base, path):
        commit(base)
        size=self.git('cat-file','-s',base+':'+path,nonzero=True)
        if size['returncode']:
            return None
        require(int(size['output'])<=1024*1024,'object cap')
        return self.git('show',base+':'+path)['output'].encode()

    def read(self, kind, seq=None):
        path,_=self.path(kind,seq)
        base=self.fetch()
        raw=self.object(base,path)
        if raw is None:
            return None
        self.seen[path]=raw
        blob=self.git('rev-parse',base+':'+path)['output'].strip()
        authored=self.git('log','-1','--format=%H',base,'--',path)['output'].strip()
        return json.loads(raw),dict(commit=authored,blob=blob,path=path,sha256=sha(raw))

    def publish(self, kind, value, seq=None):
        try:
            path,owner=self.path(kind,seq)
            require(owner==self.role,'artifact owner')
            raw=encode(value)
            require(len(raw)<=1024*1024,'publication cap')
            base=self.fetch()
            old=self.object(base,path)
            if old is not None:
                require(old==raw,'immutable publication conflict')
                self.seen[path]=raw
                authored=self.git('log','-1','--format=%H',base,'--',path)['output'].strip()
                return dict(commit=authored,blob=self.git('rev-parse',base+':'+path)['output'].strip(),path=path,sha256=sha(raw))
            started=time.time()
            with tempfile.TemporaryDirectory(prefix='c6-index-') as tmp:
                env={'GIT_INDEX_FILE':str(Path(tmp)/'index')}
                # Input via exclusive file avoids putting arbitrary data in argv or a shell.
                payload=self.root/('payload-'+str(time.time_ns()))
                from c6_protocol import put
                put(self.root,payload.name,raw)
                blob=self.git('hash-object','-w',str(payload))['output'].strip()
                self.git('read-tree',base,env=env)
                self.git('update-index','--add','--cacheinfo','100644',blob,path,env=env)
                tree=self.git('write-tree',env=env)['output'].strip()
                new=self.git('commit-tree',tree,'-p',base,'-m','C6 immutable '+kind,env=env)['output'].strip()
            self.git('push','--quiet',self.origin,new+':refs/heads/main')
            self.seen[path]=raw
            self.events.append(dict(phase='publication',started=started,finished=time.time(),payload_bytes=len(raw),commit=new))
            return dict(commit=new,blob=blob,path=path,sha256=sha(raw))
        except BaseException:
            self.failed=True
            raise
