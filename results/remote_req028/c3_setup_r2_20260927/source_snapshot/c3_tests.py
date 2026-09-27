import copy,json,os,shutil,tempfile,time,unittest
from pathlib import Path
from c3_adapter import *
from c3_fakes import Clock,Lifecycle,HTTP,Git
class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='c3-fixture-');self.root=Path(self.tmp.name)
        self.clock=Clock();self.messages=[{'role':'system','content':'fixture only'},{'role':'user','content':'text is not executable'}]
        self.q={'protocol':3,'run_id':'c3-fixture','sequence':1,'request_id':'c3-fixture-1','config_sha256':CONFIG_SHA,'messages':self.messages,'messages_sha256':messages_sha(self.messages),'parent_response_sha256':None,'expires_at':self.clock.now()+3500}
        self.entry={'sequence':1,'commit':'a'*40,'path':'results/remote_req028/c3_fixture/request1.json','sha256':sha(encode(self.q))}
        self.release={'protocol':3,'run_id':'c3-fixture','config_sha256':CONFIG_SHA,'max_calls':24,'deadline':self.clock.now()+3600,'requests':[self.entry],'parent_release_sha256':None}
        self.life=Lifecycle(self.root/'child',self.clock);self.http=HTTP();self.git=Git(self.entry,encode(self.q));self.store=FileStore(self.root/'journal');self.adapters=[]
    def make(self):
        raw=encode(self.release)
        a=Adapter(raw,sha(raw),CONTRACT,self.clock,self.store,self.life,self.http,self.git,watch_interval=.001);self.adapters.append(a);return a
    def replace_request(self,**fields):
        self.q.update(fields);raw=encode(self.q);self.entry['sha256']=sha(raw);self.git.objects[(self.entry['commit'],self.entry['path'])]=raw
    def tearDown(self):
        for a in self.adapters:
            try:a.close()
            except Exception:pass
        if self.life.has_owner() and self.life.owned_alive():self.life.stop('test final cleanup')
        if self.http.handle:self.http.handle.cancel()
        if self.git.handle:self.git.handle.cancel()
        for h in self.life.handles:
            if hasattr(h,'thread'):h.cancel()
        if os.environ.get('C3_FIXTURE_OUT'):
            out=Path(os.environ['C3_FIXTURE_OUT'])/self._testMethodName
            shutil.copytree(self.root,out)
            (out/'cleanup_verified.json').write_text(json.dumps({'owned_absent':not self.life.owned_alive(),'physical_http_calls':self.http.calls,'loads':self.life.loads,'setup_calls':self.life.setup_count,'publications':self.git.publications},indent=2))
        self.tmp.cleanup()
    def assert_no_load_claim(self):
        self.assertEqual(self.life.loads,0);self.assertEqual(self.http.calls,0)
        self.assertFalse(list((self.root/'journal').rglob('*.claim.json')))
        self.assertIsNone(self.store.read('c3-fixture/lifecycle.claim'))
    def test_wrong_first_config_before_claim(self):
        self.release['config_sha256']='0'*64
        with self.assertRaises(Rejected):self.make()
        self.assert_no_load_claim()
        self.release['config_sha256']=CONFIG_SHA
        with self.assertRaises(Rejected):Adapter(encode(self.release),sha(encode(self.release)),dict(CONTRACT,max_tokens=1),self.clock,self.store,self.life,self.http,self.git)
        self.assert_no_load_claim()
    def test_allowlist_pin_path_commit_and_protocol(self):
        raw=encode(self.release)
        with self.assertRaises(Rejected):Adapter(raw,'0'*64,CONTRACT,self.clock,self.store,self.life,self.http,self.git)
        for field,value in [('path','../escape'),('commit','not-a-commit')]:
            saved=self.entry[field];self.entry[field]=value
            with self.assertRaises(Rejected):self.make()
            self.entry[field]=saved
        self.release['protocol']=1
        with self.assertRaises(Rejected):self.make()
        self.assert_no_load_claim()
    def test_wrong_fetched_identity_no_claim(self):
        self.git.identity_wrong=True;a=self.make()
        with self.assertRaises(Rejected):a.process(1)
        self.assert_no_load_claim()
    def test_wrong_envelope_hash_no_claim(self):
        self.git.objects[(self.entry['commit'],self.entry['path'])]=b'{}';a=self.make()
        with self.assertRaises(Rejected):a.process(1)
        self.assert_no_load_claim()
    def test_oversized_invalid_messages_extra_fields(self):
        for patch in ({'messages':[]},{'messages':[{'role':'user','content':5}]},{'messages':[{'role':'user','content':'x','tools':[]}]},{'temperature':1}):
            q=dict(self.q,**patch);raw=encode(q);e=dict(self.entry,sha256=sha(raw))
            with self.assertRaises(Rejected):validate_request(raw,self.release,e,self.clock.now())
        raw=b' '*(1024*1024+1);e=dict(self.entry,sha256=sha(raw))
        with self.assertRaises(Rejected):validate_request(raw,self.release,e,self.clock.now())
        self.replace_request(messages=[]);a=self.make()
        with self.assertRaises(Rejected):a.process(1)
        self.assert_no_load_claim()
    def test_expiry_before_load(self):
        self.replace_request(expires_at=self.clock.now()-1);a=self.make()
        with self.assertRaises(Rejected):a.process(1)
        self.assert_no_load_claim()
    def test_success_seal_duplicate_no_next_unapproved(self):
        a=self.make();r=a.process(1);self.assertEqual(a.read_sealed(1),r)
        with self.assertRaises(Rejected):a.process(1)
        with self.assertRaises(Rejected):a.process(2)
        self.assertEqual(self.http.calls,1);self.assertEqual(self.life.loads,1)
        self.assertEqual(set(self.http.bodies[0]),{'messages','temperature','seed','max_tokens','stream','cache_prompt'})
    def test_context_overflow_no_generation(self):
        self.http.tokens=[1]*32768;a=self.make()
        with self.assertRaises(Rejected):a.process(1)
        self.assertEqual(self.http.calls,0);self.assertFalse(self.life.owned_alive())
        with self.assertRaises(Rejected):a.process(1)
        self.assertEqual(self.life.loads,1)
    def test_native_binding_mismatch(self):
        self.http.template='0'*64;a=self.make()
        with self.assertRaises(Rejected):a.process(1)
        self.assertEqual(self.http.calls,0);self.assertFalse(self.life.owned_alive())
    def test_wrong_usage_raw_preserved_unsealed(self):
        self.http.wrong_usage=True;a=self.make()
        with self.assertRaises(Rejected):a.process(1)
        self.assertIsNotNone(self.store.read('c3-fixture/1.raw_response.json'))
        with self.assertRaises(Indeterminate):a.read_sealed(1)
        self.assertEqual(self.http.calls,1);self.assertFalse(self.life.owned_alive())
    def test_inflight_timeout_cancels_blocked_worker_and_child(self):
        self.http.block=True;a=self.make()
        with self.assertRaises(Rejected):a.process(1)
        self.assertTrue(self.http.handle.cancelled);self.assertTrue(self.http.handle.finished.is_set())
        self.assertFalse(self.http.handle.thread.is_alive());self.assertFalse(self.life.owned_alive())
        self.assertEqual(self.http.calls,1)
    def test_load_timeout_no_generation(self):
        self.life.load_block=True;a=self.make()
        with self.assertRaises(Rejected):a.process(1)
        self.assertTrue(self.life.handles[0].cancelled);self.assertFalse(self.life.owned_alive());self.assertEqual(self.http.calls,0)
    def test_idle_pressure_independent_watchdog(self):
        a=self.make();a.process(1);self.life.pressure=2
        self.assertTrue(a.abort.wait(2))
        a.close();self.assertFalse(self.life.owned_alive());self.assertEqual(a.failed,'adverse_pressure')
    def test_idle_peer_and_parent_death(self):
        a=self.make();a.process(1);self.life.peer=True
        self.assertTrue(a.abort.wait(2));a.close();self.assertFalse(self.life.owned_alive())
        self.assertEqual(a.failed,'foreign_inference')
    def test_parent_death_cleanup(self):
        a=self.make();a.process(1);self.life.parent=False
        self.assertTrue(a.abort.wait(2));a.close();self.assertFalse(self.life.owned_alive())
        self.assertEqual(a.failed,'owner_parent_exited')
    def test_idle_deadline_no_renewal(self):
        a=self.make();a.process(1);deadline=a.model_deadline;self.clock.advance(1801)
        self.assertTrue(a.abort.wait(2));a.close()
        self.assertEqual(a.model_deadline,deadline);self.assertEqual(self.life.loads,1);self.assertFalse(self.life.owned_alive())
    def test_crash_claim_never_redispatch_or_reload(self):
        self.http.crash=True;a=self.make()
        with self.assertRaises(RuntimeError):a.process(1)
        with self.assertRaises(Rejected):a.process(1)
        b=self.make()
        with self.assertRaises(Rejected):b.process(1)
        self.assertIsNotNone(self.store.read('c3-fixture/1.indeterminate.json'))
        self.assertEqual(self.http.calls,1);self.assertEqual(self.life.loads,1)
    def test_publication_failure_sealed_read_no_regeneration(self):
        self.git.publish_failure=True;a=self.make()
        with self.assertRaises(RuntimeError):a.process(1)
        self.assertIsInstance(a.read_sealed(1),bytes)
        with self.assertRaises(Rejected):a.process(1)
        self.assertEqual(self.http.calls,1);self.assertEqual(self.git.publications,1);self.assertFalse(self.life.owned_alive())
    def test_dirty_conflict_fetch_and_timeout(self):
        self.git.failure='dirty checkout or source conflict';a=self.make()
        with self.assertRaises(RuntimeError):a.process(1)
        self.assert_no_load_claim()
    def test_git_wait_bound(self):
        self.git.block=True;a=self.make()
        with self.assertRaises(Rejected):a.process(1)
        self.assertTrue(self.git.handle.cancelled);self.assert_no_load_claim()
    def test_latest_main_cannot_substitute(self):
        self.git.latest='b'*40;a=self.make();a.process(1)
        self.assertEqual(self.git.reads[0][:2],(self.entry['commit'],self.entry['path']))
        self.assertEqual(self.http.calls,1)
    def test_explicit_next_release_resident_reuse_no_renewal(self):
        a=self.make();r=a.process(1);deadline=a.model_deadline
        q=dict(self.q,sequence=2,request_id='c3-fixture-2',parent_response_sha256=sha(r))
        q['messages']=self.messages+[{'role':'assistant','content':'fixture text only'},{'role':'user','content':'fake tool observation'}];q['messages_sha256']=messages_sha(q['messages'])
        raw=encode(q);e={'sequence':2,'commit':'b'*40,'path':'results/remote_req028/c3_fixture/request2.json','sha256':sha(raw)}
        release=dict(self.release,requests=[self.entry,e],parent_release_sha256=a.release_pin)
        changed=dict(release,deadline=release['deadline']+1)
        with self.assertRaises(Rejected):a.authorize_next(encode(changed),sha(encode(changed)))
        a.authorize_next(encode(release),sha(encode(release)))
        self.git.objects[(e['commit'],e['path'])]=raw;a.process(2)
        self.assertEqual(self.life.loads,1);self.assertEqual(self.life.setup_count,1);self.assertEqual(self.http.calls,2);self.assertEqual(a.model_deadline,deadline)
    def test_failed_setup_no_next_or_reload(self):
        self.life.setup_error=RuntimeError('setup failure');a=self.make()
        with self.assertRaises(RuntimeError):a.process(1)
        with self.assertRaises(Rejected):a.process(2)
        self.assertEqual(self.life.loads,0);self.assertEqual(self.life.setup_count,1)
    def test_admission_expiry_once_no_load(self):
        self.life.free=74;a=self.make()
        with self.assertRaises(TimeoutError):a.process(1)
        self.assertEqual(self.life.loads,0);self.assertEqual(self.http.calls,0)
        with self.assertRaises(Rejected):a.process(1)
if __name__=='__main__':unittest.main()
