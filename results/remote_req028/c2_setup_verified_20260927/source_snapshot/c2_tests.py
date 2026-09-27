import json,os,subprocess,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from c2_relay import *
from c2_git import GitTransport,OWNER
class EnvelopeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='c2-fixture-')
        self.store=FileStore(self.tmp.name);self.now=expiry('2026-09-27T08:30:00Z')-60
        self.relay=Relay(self.store.read,self.store.write_exclusive,lambda:self.now)
        self.raw=frozen_nonce();self.commit='a'*40;self.calls=[]
    def tearDown(self):self.tmp.cleanup()
    def dispatch(self,body):self.calls.append(body);return 'synthetic echo: '+body
    def change(self,**fields):d=json.loads(self.raw);d.update(fields);return encode(d)
    def response(self):return self.relay.dispatch_once(self.raw,self.commit,self.dispatch)
    def test_fixed_nonce_and_body_data(self):
        r=self.response();self.assertEqual(self.calls,['DTR_C2_NONCE_20260927'])
        self.assertEqual(self.relay.accept_response(r,self.raw,self.commit),r)
        self.assertEqual(self.relay.accept_response(r,self.raw,self.commit),r)
        self.assertEqual(self.response(),r);self.assertEqual(len(self.calls),1)
    def test_types_fields_size_path_hash(self):
        cases=[dict(sequence=True),dict(sequence=0),dict(body_sha256='0'*64),dict(protocol=True),dict(synthetic_only=False),dict(run_id='../evil'),dict(request_id='x/y'),dict(extra='unknown'),dict(config_sha256='x'),dict(expires_at='2026-09-27'),dict(parent_response_sha256='0'*64)]
        for change in cases:
            with self.subTest(change=change),self.assertRaises(Rejected):validate_request(self.change(**change),self.now)
        for raw in (b'{' + b' '*(MAX_BYTES+1),b'{"protocol":1,"protocol":1}',b'\xff'):
            with self.assertRaises(Rejected):validate_request(raw,self.now)
        for path in ('../x','a/../x','/x','a//x','a\\x'):
            with self.assertRaises(Rejected):self.store.read(path)
        self.assertEqual(self.calls,[])
    def test_stale_and_deadline_after_claim(self):
        self.now+=61
        with self.assertRaises(Rejected):self.response()
        self.assertFalse(list(Path(self.tmp.name).rglob('*.claim.json')))
        self.now-=61
        def expire():self.now+=61
        with self.assertRaises(Rejected):self.relay.dispatch_once(self.raw,self.commit,self.dispatch,after_claim=expire)
        self.assertEqual(self.calls,[])
        self.now-=61
        with self.assertRaises(Indeterminate):self.response()
    def test_crash_after_claim_before_dispatch(self):
        def crash():raise RuntimeError('simulated crash')
        with self.assertRaises(RuntimeError):self.relay.dispatch_once(self.raw,self.commit,self.dispatch,after_claim=crash)
        with self.assertRaises(Indeterminate):self.response()
        self.assertEqual(self.calls,[])
    def test_crash_after_dispatch_never_retried(self):
        def crash(body):self.calls.append(body);raise RuntimeError('simulated worker loss')
        with self.assertRaises(RuntimeError):self.relay.dispatch_once(self.raw,self.commit,crash)
        with self.assertRaises(Indeterminate):self.response()
        self.assertEqual(len(self.calls),1)
    def test_deadline_during_dispatch(self):
        def late(body):self.calls.append(body);self.now+=61;return 'too late'
        with self.assertRaises(Rejected):self.relay.dispatch_once(self.raw,self.commit,late)
        self.now-=61
        with self.assertRaises(Indeterminate):self.response()
        self.assertEqual(len(self.calls),1)
    def test_failure_writing_response_no_redispatch(self):
        def write(name,data):
            if name.endswith('.response.json'):raise OSError('disk failure')
            return self.store.write_exclusive(name,data)
        relay=Relay(self.store.read,write,lambda:self.now)
        with self.assertRaises(OSError):relay.dispatch_once(self.raw,self.commit,self.dispatch)
        with self.assertRaises(Indeterminate):self.response()
        self.assertEqual(len(self.calls),1)
    def test_conflicting_duplicate_and_modified_record(self):
        r=self.response()
        changed=self.change(body='other',body_sha256=sha(b'other'))
        with self.assertRaises(Rejected):self.relay.dispatch_once(changed,self.commit,self.dispatch)
        with self.assertRaises(Rejected):self.relay.dispatch_once(self.raw,'b'*40,self.dispatch)
        self.relay.accept_response(r,self.raw,self.commit)
        conflict=json.loads(r);conflict['response']='other';conflict['response_sha256']=sha(b'other')
        with self.assertRaises(Rejected):self.relay.accept_response(encode(conflict),self.raw,self.commit)
        p=Path(self.tmp.name)/'req028-c2-20260927/1.response.json';p.write_bytes(encode(conflict))
        with self.assertRaises(Rejected):self.response()
        self.assertEqual(len(self.calls),1)
    def test_response_bindings_and_expiry(self):
        response=json.loads(self.response());request=validate_request(self.raw,self.now)
        for change in ({'body_sha256':'0'*64},{'config_sha256':'0'*64},{'request_commit':'b'*40},{'sequence':2},{'response_sha256':'0'*64},{'extra':1},{'receipt_time':self.now+1},{'elapsed_seconds':-1}):
            with self.subTest(change=change),self.assertRaises(Rejected):validate_response(encode(dict(response,**change)),request,self.commit,self.now)
        self.now+=61
        with self.assertRaises(Rejected):self.relay.accept_response(encode(response),self.raw,self.commit)
    def test_serial_parent_and_config(self):
        second=self.change(sequence=2,request_id='req028-c2-20260927-2',parent_response_sha256='0'*64)
        with self.assertRaises(Indeterminate):self.relay.dispatch_once(second,self.commit,self.dispatch)
        first=self.response()
        for update in ({'parent_response_sha256':'0'*64},{'config_sha256':'0'*64}):
            request=json.loads(second);request['parent_response_sha256']=sha(first);request.update(update)
            with self.assertRaises(Rejected):self.relay.dispatch_once(encode(request),self.commit,self.dispatch)
        request=json.loads(second);request['parent_response_sha256']=sha(first)
        self.relay.dispatch_once(encode(request),self.commit,self.dispatch);self.assertEqual(len(self.calls),2)
    def test_concurrent_claim_and_phase_accounting(self):
        other=Relay(self.store.read,self.store.write_exclusive,lambda:self.now)
        def compete():
            with self.assertRaises(Indeterminate):other.dispatch_once(self.raw,self.commit,self.dispatch)
        def dispatch(body):self.now+=2;return self.dispatch(body)
        response=json.loads(self.relay.dispatch_once(self.raw,self.commit,dispatch,network_seconds=1,queued_at=self.now-3,after_claim=compete))
        self.assertEqual(response['timings'],{'network_seconds':1,'queue_seconds':3,'dispatch_seconds':2})
        self.assertEqual(response['elapsed_seconds'],6);self.assertEqual(len(self.calls),1)
class GitTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='c2-git-fixture-');self.root=Path(self.tmp.name)
        self.remote=self.root/'remote.git';self.local=self.root/'local';self.other=self.root/'other'
        self.git_cmd(self.root,'init','--bare',str(self.remote))
        self.git_cmd(self.root,'clone',str(self.remote),str(self.local))
        self.git_cmd(self.local,'checkout','-b','main')
        (self.local/'seed').write_text('fixture')
        self.git_cmd(self.local,'add','seed');self.git_cmd(self.local,'commit','-m','seed');self.git_cmd(self.local,'push','origin','main')
        self.git_cmd(self.root,'clone','--branch','main',str(self.remote),str(self.other))
        self.base=self.git_cmd(self.local,'rev-parse','HEAD').decode().strip();self.events=[]
        self.t=GitTransport(self.local,record=self.events.append)
        self.path='results/remote_req028/c2_fixture/request.json'
    def git_cmd(self,cwd,*args):
        r=subprocess.run(['git',*args],cwd=cwd,env=dict(os.environ,**OWNER),capture_output=True,timeout=10)
        if r.returncode:raise AssertionError(r.stderr.decode())
        return r.stdout
    def tearDown(self):self.tmp.cleanup()
    def advance(self):
        (self.other/'advance').write_text('concurrent fixture')
        self.git_cmd(self.other,'add','advance');self.git_cmd(self.other,'commit','-m','concurrent');self.git_cmd(self.other,'push','origin','main')
    def test_object_roundtrip_owned_publication(self):
        commit=self.t.publish({self.path:frozen_nonce()},'synthetic request',self.base)
        self.t.fetch_main();self.assertEqual(self.t.read_object(commit,self.path),frozen_nonce())
        self.assertFalse((self.local/self.path).exists())
        self.assertEqual(self.git_cmd(self.local,'status','--porcelain'),b'')
        self.assertIn('network_publication',[x['phase'] for x in self.events])
    def test_dirty_checkout_rejected(self):
        (self.local/'dirty').write_text('user work')
        with self.assertRaises(Rejected):self.t.publish({self.path:b'x'},'x',self.base)
        self.assertEqual(self.events,[])
    def test_concurrent_main_advance(self):
        self.advance()
        with self.assertRaises(Rejected):self.t.publish({self.path:b'x'},'x',self.base)
        self.assertEqual(self.git_cmd(self.local,'rev-parse','HEAD').decode().strip(),self.base)
    def test_push_race_rejected_no_retry(self):
        advanced=[]
        def record(event):
            self.events.append(event)
            if event['phase']=='network_check_main' and not advanced:self.advance();advanced.append(True)
        self.t.record=record
        with self.assertRaises(Rejected):self.t.publish({self.path:b'x'},'x',self.base)
        self.assertEqual([x['phase'] for x in self.events].count('network_publication'),1)
    def test_publication_failure_no_hidden_retry(self):
        pushes=[]
        def runner(args,**kwargs):
            if args[1]=='push':pushes.append(args);return SimpleNamespace(returncode=1,stdout=b'',stderr=b'failure')
            return subprocess.run(args,**kwargs)
        self.t.runner=runner
        with self.assertRaises(Rejected):self.t.publish({self.path:b'x'},'x',self.base)
        self.assertEqual(len(pushes),1)
        self.assertEqual(self.git_cmd(self.remote,'rev-parse','main').decode().strip(),self.base)
    def test_conflicting_record_and_unowned_path(self):
        with self.assertRaises(Rejected):self.t.publish({'docs/changed':b'x'},'x',self.base)
        commit=self.t.publish({self.path:b'original'},'x',self.base)
        self.git_cmd(self.local,'fetch','origin','main');self.git_cmd(self.local,'merge','--ff-only','FETCH_HEAD')
        with self.assertRaises(Rejected):self.t.publish({self.path:b'changed'},'x',commit)
if __name__=='__main__':unittest.main()
