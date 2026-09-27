import json,os,shutil,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import c3_tests,b3_stop
from c2_relay import encode,sha,FileStore,Rejected
from c2_git import OWNER
from c3_adapter import Adapter,CONTRACT,CONFIG_SHA,PENDING
from c3_fakes import Clock
from c3r_hooks import Lifecycle,HTTP,Git,ProcessHandle,alive,HERE
from c3r_envelope import build,consume
class CleanupTests(c3_tests.AdapterTests):
    def broken(self,predicate):
        original=self.store.write_exclusive
        def write(name,data):
            if predicate(name):raise OSError('injected journal outage')
            return original(name,data)
        self.store.write_exclusive=write
    def observed(self,a):
        absent=not self.life.owned_alive()
        (self.root/'immediate_observer.json').write_text(json.dumps({'absent_before_teardown':absent,'primary_exception':a.primary_exception,'failed':a.failed,'audit_errors':a.audit_errors,'cleanup_errors':a.cleanup_errors,'cleanup_results':a.cleanup_results,'cancel_errors':a.cancel_errors},indent=2))
        self.assertTrue(absent)
        with self.assertRaises(Rejected):a.process(2)
    def test_failure_json_outage_immediate_cleanup(self):
        a=self.make();a.process(1);self.broken(lambda n:n.endswith('/failure.json'))
        a.fail('primary failure');self.observed(a)
        self.assertEqual(a.failed,'primary failure');self.assertTrue(a.audit_errors)
    def test_failed_cancel_and_failed_all_audit_cleanup(self):
        a=self.make();a.process(1)
        class Bad:
            def cancel(self):raise RuntimeError('cancel failed')
        a.active=Bad();self.broken(lambda n:True);a.fail('primary failure');self.observed(a)
        self.assertTrue(a.cancel_errors);self.assertTrue(a.audit_errors)
    def test_cleanup_success_event_write_outage(self):
        a=self.make();a.process(1);self.broken(lambda n:'/cleanup_' in n)
        a.close();self.observed(a);self.assertTrue(a.cleanup_results);self.assertTrue(a.audit_errors)
    def test_phase_event_outage_preserves_primary(self):
        a=self.make()
        def crash(body,timeout):
            self.http.calls+=1;self.broken(lambda n:'/events/' in n)
            raise RuntimeError('primary dispatch error')
        self.http.begin_generate=crash
        with self.assertRaisesRegex(RuntimeError,'primary dispatch error'):a.process(1)
        self.observed(a);self.assertIn('primary dispatch error',a.primary_exception)
    def test_total_wall_event_outage_cleanup_first(self):
        a=self.make();a.process(1);self.broken(lambda n:'/events/' in n)
        a.close();self.observed(a);self.assertTrue(a.audit_errors)
    def test_primary_poll_error_with_cancel_and_audit_failure(self):
        a=self.make();outer=self
        class Bad:
            def poll(self):
                outer.broken(lambda n:True)
                raise RuntimeError('primary poll error')
            def cancel(self):raise RuntimeError('secondary cancel error')
        def start(body,timeout):self.http.calls+=1;return Bad()
        self.http.begin_generate=start
        with self.assertRaisesRegex(RuntimeError,'primary poll error'):a.process(1)
        self.observed(a);self.assertTrue(a.cancel_errors);self.assertEqual(self.http.calls,1)
    def test_partial_provisional_load_failure(self):
        original=self.life.begin_load
        def partial(contract,timeout):original(contract,timeout);raise RuntimeError('partial provisional load failure')
        self.life.begin_load=partial;a=self.make()
        with self.assertRaisesRegex(RuntimeError,'partial provisional'):a.process(1)
        self.observed(a);self.assertEqual(self.life.loads,1);self.assertEqual(self.http.calls,0)
class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='c3r-fixture-');self.root=Path(self.tmp.name);self.lives=[];self.hooks=[];self.processes=[];self.observer={}
    def wait(self,predicate,timeout=5):
        end=time.monotonic()+timeout
        while not predicate():
            if time.monotonic()>=end:self.fail('bounded fixture wait expired')
            time.sleep(.01)
    def await_handle(self,h,timeout=5):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            result=h.poll()
            if result is not PENDING:return result
            time.sleep(.005)
        h.cancel();raise TimeoutError('test wait')
    def lifecycle(self,mode='fixed'):
        life=Lifecycle(self.root/('server'+str(len(self.lives))),sha((HERE/'c3r_fixture.py').read_bytes()),mode);self.lives.append(life)
        self.await_handle(life.begin_load(CONTRACT,20));return life
    def git_cmd(self,repo,*args):
        r=subprocess.run(['git',*args],cwd=repo,env=dict(os.environ,**OWNER),capture_output=True,timeout=5)
        self.assertEqual(r.returncode,0,r.stderr);return r.stdout
    def repository(self,raw):
        bare=self.root/'remote.git';repo=self.root/'repo';self.git_cmd(self.root,'init','--bare',str(bare));self.git_cmd(self.root,'clone',str(bare),str(repo));self.git_cmd(repo,'checkout','-b','main')
        path='results/remote_req028/c3_fixture/request.json';target=repo/path;target.parent.mkdir(parents=True);target.write_bytes(raw)
        self.git_cmd(repo,'add','.');self.git_cmd(repo,'commit','-m','fixed request');self.git_cmd(repo,'push','origin','main')
        commit=self.git_cmd(repo,'rev-parse','HEAD').decode().strip();return repo,{'sequence':1,'commit':commit,'path':path,'sha256':sha(raw)}
    def tearDown(self):
        for h in self.hooks:
            try:h.close()
            except Exception as e:self.observer.setdefault('teardown_errors',[]).append(repr(e))
        for h in self.processes:
            try:h.close()
            except Exception:pass
        for life in self.lives:
            try:life.stop('test final safety cleanup')
            except Exception as e:self.observer.setdefault('teardown_errors',[]).append(repr(e))
        if os.environ.get('C3R_FIXTURE_OUT'):
            out=Path(os.environ['C3R_FIXTURE_OUT'])/self._testMethodName
            (self.root/'external_observer.json').write_text(json.dumps(self.observer,indent=2));shutil.copytree(self.root,out)
        self.tmp.cleanup()
    def test_real_socket_and_native_binding(self):
        life=self.lifecycle();http=HTTP(self.root/'http',life);self.hooks.append(http)
        binding=self.await_handle(http.begin_bind([{'role':'user','content':'data'}],2))
        self.assertEqual(binding['template_sha256'],CONTRACT['template_sha256'])
        raw=self.await_handle(http.begin_generate({'messages':[]},2));self.assertEqual(json.loads(raw)['usage']['prompt_tokens'],3)
        life.stop('immediate check');self.assertFalse(life.owned_alive());self.observer['absent_before_teardown']=True
    def test_hanging_socket_cancel(self):
        life=self.lifecycle('hang');http=HTTP(self.root/'http',life);self.hooks.append(http)
        h=http.begin_generate({'messages':[]},.3)
        with self.assertRaises((TimeoutError,RuntimeError)):self.await_handle(h,2)
        self.assertTrue((life.root/'request_seen.json').exists(),'prove socket request reached hanging handler')
        h.cancel();self.assertIsNotNone(h.child.poll())
        life.stop('socket test');self.assertFalse(life.owned_alive());self.observer['socket_worker_absent_before_teardown']=True
    def test_hanging_subprocess_cancel(self):
        h=ProcessHandle([sys.executable,'-c','import time; time.sleep(30)','c3r-owned-hang'],.1);self.processes.append(h)
        with self.assertRaises(TimeoutError):self.await_handle(h,1)
        self.assertFalse(alive(h.record));self.observer['absent_before_teardown']=True
    def driver_death(self,mode):
        root=self.root/'driver'
        peer=ProcessHandle([sys.executable,'-c','import time; time.sleep(30)','c3r-owned-peer-control'],10);self.processes.append(peer)
        driver=ProcessHandle([sys.executable,str(HERE/'c3r_driver_fixture.py'),str(root),mode,'c3r-owned-driver'],10);self.processes.append(driver)
        self.wait(lambda:(root/'observer.json').exists())
        info=json.loads((root/'observer.json').read_text())
        self.assertTrue(alive(info['model']))
        if mode=='inflight':self.wait(lambda:(root/'server/request_seen.json').exists())
        self.assertTrue(alive(driver.record));os.kill(driver.child.pid,signal.SIGKILL);driver.child.wait(timeout=2)
        self.wait(lambda:not alive(info['model']),5)
        result=root/'server/owner.external_result.json';self.wait(result.exists,3)
        receipt=json.loads(result.read_text());self.assertEqual(receipt['reason'],'owner_parent_exited')
        self.assertTrue(alive(peer.record))
        if 'http_worker' in info:self.wait(lambda:not alive(info['http_worker']),3)
        self.observer={'driver_killed_without_finally':True,'child_absent_before_teardown':True,'peer_untouched':True,'external_watchdog':receipt,'handles':info}
    def test_external_parent_death_idle(self):self.driver_death('idle')
    def test_external_parent_death_inflight(self):self.driver_death('inflight')
    def test_b3_journal_failure_safety_fallback(self):
        life=self.lifecycle()
        with patch.object(b3_stop,'save',side_effect=OSError('arbiter audit failure')):result=life.stop('audit unavailable')
        self.assertFalse(life.owned_alive());self.assertIn('audit failure',result['audit_error']);self.observer=result
    def test_provisional_identity_probe_failure(self):
        life=Lifecycle(self.root/'server',sha((HERE/'c3r_fixture.py').read_bytes()));self.lives.append(life)
        with patch('c3r_hooks.identity',side_effect=TimeoutError('identity probe failed')):
            with self.assertRaises(TimeoutError):life.begin_load(CONTRACT,3)
        self.assertIsNotNone(life.proc.poll());self.observer={'direct_child_absent_before_teardown':True}
    def test_protocol3_envelope_exact_bindings(self):
        q={'run_id':'c3-fixture','sequence':1,'request_id':'c3-fixture-1','messages_sha256':'a'*64};e={'commit':'b'*40,'path':'results/remote_req028/c3_fixture/r.json','sha256':'c'*64};binding={'token_ids':[1],'rendered':'fixture'};timing={'request_wall_seconds':1,'prefill_ms':2,'generation_ms':3}
        raw=build(q,e,CONFIG_SHA,binding,b'{}',timing);consume(raw,q,e,CONFIG_SHA,sha(encode(binding)))
        for key,value in [('request_commit','d'*40),('request_path','wrong'),('request_sha256','d'*64),('config_sha256','0'*64),('native_binding_sha256','0'*64),('raw_response','tamper'),('messages_sha256','0'*64),('protocol',1)]:
            bad=json.loads(raw);bad[key]=value
            with self.assertRaises(Rejected):consume(encode(bad),q,e,CONFIG_SHA,sha(encode(binding)))
        self.observer={'valid_accepted':True,'mismatch_cases':8}
    def test_concrete_git_read_publish_and_dirty_no_retry(self):
        repo,e=self.repository(b'{"fixed":"data"}');git=Git(self.root/'git-hooks',repo,[e],e['commit']);self.hooks.append(git)
        got=self.await_handle(git.begin_read(e['commit'],e['path'],3));self.assertEqual(got['raw'],b'{"fixed":"data"}')
        result=self.await_handle(git.begin_publish(1,b'{"fixed":"response"}',3));self.assertTrue(result['commit'])
        (repo/'dirty').write_text('user work')
        with self.assertRaisesRegex(RuntimeError,'dirty checkout'):self.await_handle(git.begin_read(e['commit'],e['path'],3))
        self.observer={'publication':result,'physical_publications':1,'dirty_rejected':True}
    def test_concrete_git_concurrent_advancement(self):
        repo,e=self.repository(b'{}');git=Git(self.root/'git-hooks',repo,[e],e['commit']);self.hooks.append(git)
        (repo/'advance').write_text('concurrent');self.git_cmd(repo,'add','.');self.git_cmd(repo,'commit','-m','advance');self.git_cmd(repo,'push','origin','main')
        with self.assertRaisesRegex(RuntimeError,'concurrent main advancement'):self.await_handle(git.begin_publish(1,b'{}',3))
        self.assertEqual(git.counter,1);self.observer={'race_rejected':True,'publication_attempts':1}
    def test_locked_production_and_argv(self):
        life=self.lifecycle()
        with self.assertRaises(PermissionError):life.production_start()
        argv=life.frozen_argv('fixture',12345);self.assertEqual(argv[argv.index('--cache-type-k')+1],'q8_0')
        with self.assertRaises(Rejected):Lifecycle.attest_assets('/missing','/missing','/missing','wrong')
        self.observer={'real_start_locked':True,'argv':argv}
    def test_adapter_with_concrete_http_and_git(self):
        from c3_adapter import messages_sha
        clock=Clock();messages=[{'role':'user','content':'fixed data only'}]
        q={'protocol':3,'run_id':'c3r-e2e','sequence':1,'request_id':'c3r-e2e-1','config_sha256':CONFIG_SHA,'messages':messages,'messages_sha256':messages_sha(messages),'parent_response_sha256':None,'expires_at':clock.now()+3500}
        repo,e=self.repository(encode(q));git=Git(self.root/'git-hooks',repo,[e],e['commit']);self.hooks.append(git)
        life=Lifecycle(self.root/'integrated-server',sha((HERE/'c3r_fixture.py').read_bytes()));self.lives.append(life)
        http=HTTP(self.root/'http',life);self.hooks.append(http)
        release={'protocol':3,'run_id':'c3r-e2e','config_sha256':CONFIG_SHA,'max_calls':24,'deadline':clock.now()+3600,'requests':[e],'parent_release_sha256':None};release_raw=encode(release)
        a=Adapter(release_raw,sha(release_raw),CONTRACT,clock,FileStore(self.root/'journal'),life,http,git,watch_interval=.01)
        try:
            response=a.process(1);envelope=json.loads(response)
            consume(response,q,e,CONFIG_SHA,envelope['native_binding_sha256'])
            with self.assertRaises(Rejected):a.process(1)
            self.assertEqual(a.physical,1)
        finally:a.close()
        self.assertFalse(life.owned_alive());self.observer={'physical_calls':a.physical,'absent_before_teardown':True,'response_envelope':envelope}
if __name__=='__main__':unittest.main()
