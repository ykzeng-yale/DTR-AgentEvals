import json,os,shutil,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from c2_relay import encode,sha,Rejected
from c2_git import OWNER
from c3r_hooks import ProcessHandle,alive
from c5_contract import *
from c5_lifecycle import Lifecycle,free_port
from c5_transport import ExactTransport
from c5_execute import Execution
HERE=Path(__file__).parent
GOOD={'pressure_level':1,'free_percent':75,'swap_used_mib':0,'owned_rss_bytes':0,'foreign_inference':[],'disk_free_bytes':20*1024**3}
class Tests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory(prefix='c5-fixture-');self.root=Path(self.tmp.name);self.handles=[];self.lives=[];self.observer={}
    def tearDown(self):
        for h in self.handles:
            try:h.close()
            except BaseException as e:self.observer.setdefault('teardown_errors',[]).append(repr(e))
        for life in self.lives:
            try:life.stop()
            except BaseException as e:self.observer.setdefault('teardown_errors',[]).append(repr(e))
        (self.root/'external_observer.json').write_text(json.dumps(self.observer,indent=2))
        if os.environ.get('C5_FIXTURE_OUT'):shutil.copytree(self.root,Path(os.environ['C5_FIXTURE_OUT'])/self._testMethodName)
        self.tmp.cleanup()
    def wait(self,predicate,seconds=8):
        end=time.monotonic()+seconds
        while not predicate():
            if time.monotonic()>=end:self.fail('bounded fixture wait')
            time.sleep(.01)
    def spec(self):
        now=time.time();return {'inert_test':True,'fixture_sha256':sha((HERE/'c5_fixture.py').read_bytes()),'phase_started':now,'phase_deadline':now+20,'load_deadline':now+10,'token':'c4-c5-owned-fixture-'+str(time.time_ns()),'port':free_port()}
    def life(self):
        life=Lifecycle(self.root/'supervision',self.spec());self.lives.append(life);(life.root/'fake_sample.json').write_bytes(encode(GOOD));return life
    def crash(self,stage):
        root=self.root/'driver';root.mkdir();(root/'fake_sample.json').write_bytes(encode(GOOD))
        driver=ProcessHandle([sys.executable,str(HERE/'c5_driver.py'),str(root),stage],25);peer=ProcessHandle([sys.executable,'-c','import time; time.sleep(30)','c5-peer'],25);self.handles.extend([driver,peer])
        marker=root/('physical_calls.jsonl' if stage=='inflight' else stage+'.json');self.wait(marker.exists)
        require(alive(driver.record),'owned driver');os.kill(driver.child.pid,signal.SIGKILL);driver.child.wait(timeout=2)
        self.wait(lambda:(root/'supervisor_exit.json').exists());receipt=json.loads((root/'supervisor_exit.json').read_text());self.assertTrue(receipt['cleanup']['owned_absent']);self.assertIn('owner_parent_exited',receipt['failure'])
        if (root/'owner.json').exists():self.assertFalse(alive(json.loads((root/'owner.json').read_text())))
        supervisor=json.loads((root/'driver_observer.json').read_text())['supervisor'];self.wait(lambda:not alive(supervisor));self.assertTrue(alive(peer.record));self.assertFalse((root/'exec_seen.json').exists())
        if stage=='inflight':self.wait(lambda:not alive(json.loads((root/'http_worker.json').read_text())))
        self.observer={'inert_executable_attestation':True,'stage':stage,'owned_absent_before_teardown':True,'peer_untouched':True,'no_exec_seen_required':True,'receipt':receipt}
    def test_driver_death_before_spawn(self):self.crash('before_spawn')
    def test_driver_death_child_spawned(self):self.crash('child_spawned')
    def test_driver_death_ownership_persisted(self):self.crash('ownership_persisted')
    def test_driver_death_before_exec_release(self):self.crash('before_exec_release')
    def test_driver_death_exec_released(self):self.crash('exec_released')
    def test_driver_death_exec_confirmed(self):self.crash('exec_confirmed')
    def test_driver_death_running(self):self.crash('running')
    def test_driver_death_inflight(self):self.crash('inflight')
    def test_no_approval_no_popen_no_manifest_only_activation(self):
        import c5_activate
        with patch.object(c5_activate.subprocess,'Popen',side_effect=AssertionError('must not spawn')):
            with self.assertRaisesRegex(Rejected,'NOT launch permission'):c5_activate.activate(SimpleNamespace(source_commit=None,approval_commit=None,approval_sha=None))
        self.observer={'manifest_not_permission':True,'no_spawn':True}
    def test_independent_native_and_exact_request(self):
        manifest=(ROOT/RELEASE_PATH).read_bytes();raw=git(ROOT,'show',REQUEST_COMMIT+':'+REQUEST_PATH);request(raw,manifest,time.time());binding=native_expected();r=verify_native(binding)
        self.assertEqual(r['tokens'],1530)
        with self.assertRaises(Rejected):verify_native(dict(binding,rendered=binding['rendered']+'x'))
        floating=list(binding['token_ids']);floating[0]=float(floating[0])
        with self.assertRaises(Rejected):verify_native(dict(binding,token_ids=floating))
        with self.assertRaises(Rejected):request(raw+b' ',manifest,time.time())
        with self.assertRaises(Rejected):release(manifest,EXPIRY)
        self.observer={'real_archived_native_hashes':r,'no_tokenizer_or_model_invoked':True}
    def git(self,repo,*args):
        r=subprocess.run(['git',*args],cwd=repo,capture_output=True,env=dict(os.environ,**OWNER),timeout=5);self.assertEqual(r.returncode,0,r.stderr);return r.stdout.decode().strip()
    def setup_execution(self):
        bare=self.root/'remote.git';repo=self.root/'repo';self.git(self.root,'init','--bare',str(bare));self.git(self.root,'clone',str(bare),str(repo));self.git(repo,'checkout','-b','main')
        raw=(ROOT/REQUEST_PATH).read_bytes();manifest=(ROOT/RELEASE_PATH).read_bytes();p=repo/REQUEST_PATH;p.parent.mkdir(parents=True);p.write_bytes(raw);self.git(repo,'add','.');self.git(repo,'commit','-m','fixed approved bytes');self.git(repo,'push','origin','main');commit=self.git(repo,'rev-parse','HEAD')
        transport=ExactTransport(repo,str(bare),self.root);transport.authorize_exact(manifest,commit,fixture_commit=commit);life=self.life();execution=Execution(self.root,life,transport,raw,manifest,'a'*64)
        return execution,life,transport,repo
    def test_exact_pipeline_one_call_seal_publication_and_cleanup(self):
        execution,life,t,repo=self.setup_execution();head=self.git(repo,'rev-parse','HEAD');result=execution.run();self.assertEqual(execution.physical,1);self.assertEqual((self.root/'response.seal').read_text(),sha(result));self.assertEqual(len((life.root/'physical_calls.jsonl').read_text().splitlines()),1);life.assert_absent();self.assertEqual(self.git(repo,'rev-parse','HEAD'),head)
        self.assertFalse((life.root/'exec_seen.json').exists());self.observer={'owned_absent_before_teardown':True,'physical_calls':1,'sealed':True,'published':t.last_response,'fixture_tokenizer_attestation':True}
    def test_publication_conflict_preserves_seal_no_regeneration(self):
        execution,life,t,repo=self.setup_execution();original=execution.git.begin_publish
        def conflict(*args):
            (repo/'advance').write_text('concurrent data');self.git(repo,'add','.');self.git(repo,'commit','-m','advance');self.git(repo,'push','origin','main');return original(*args)
        execution.git.begin_publish=conflict
        with self.assertRaisesRegex(RuntimeError,'concurrent main advancement'):execution.run()
        self.assertTrue((self.root/'response.seal').exists());self.assertEqual(len((life.root/'physical_calls.jsonl').read_text().splitlines()),1);life.assert_absent();self.observer={'owned_absent_before_teardown':True,'one_physical_call':True,'sealed_preserved':True,'no_regeneration':True}
    def test_wrong_native_no_physical_call(self):
        execution,life,t,repo=self.setup_execution()
        with patch('c5_execute.native_expected',return_value={'wrong':'binding'}),patch.object(t,'approve_exact_native',side_effect=Rejected('wrong native fixture')):
            with self.assertRaisesRegex(Rejected,'wrong native'):execution.run()
        self.assertFalse((life.root/'physical_calls.jsonl').exists());life.assert_absent();self.observer={'owned_absent_before_teardown':True,'no_generation_on_binding_failure':True}
    def test_audit_failure_still_cleanup(self):
        execution,life,t,repo=self.setup_execution();original=execution.put
        def fail(name,data):
            if name in ('raw_response.json','failure.json','execution_receipt.json'):raise OSError('injected audit outage')
            return original(name,data)
        execution.put=fail
        with self.assertRaisesRegex(OSError,'audit outage'):execution.run()
        life.assert_absent();self.assertEqual(execution.physical,1);self.assertTrue(execution.errors);self.observer={'owned_absent_before_teardown':True,'audit_errors':execution.errors,'primary_preserved':True}
    def test_production_gate_exact_command_with_injected_approval_only(self):
        import c5_gate
        from c4_attest import MODEL,SERVER,argv
        spec=self.spec();spec.update(inert_test=False,approval_args={'source_commit':'b'*40,'approval_commit':'c'*40,'approval_path':'docs/req028_c5_source_approval_20260927.json','approval_sha':'d'*64},approval={'explicit':'fake test approval'},source_pins={'fake':'pin'},asset_stats={},argv=['/bin/sh','-c','NEVER EXECUTE'])
        for path in (MODEL,SERVER):
            st=path.stat();spec['asset_stats'][str(path)]=[st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns]
        with patch.object(c5_gate,'approval',return_value=(spec['approval'],b'fake')),patch.object(c5_gate,'source_pins',return_value=spec['source_pins']):
            actual=c5_gate.command(spec);self.assertEqual(actual,argv(spec['token'],spec['port']));self.assertNotIn('/bin/sh',actual)
            bad=dict(spec,asset_stats={str(MODEL):[0]*5,str(SERVER):[0]*5})
            with self.assertRaisesRegex(Rejected,'asset changed'):c5_gate.command(bad)
        self.observer={'production_policy_exercised_with_explicit_fake_approval':True,'actual_binary_digest_read_only':True,'argv_never_executed':actual,'arbitrary_argv_ignored':True}
    def test_exact_consumer_provenance_expiry_and_attestation(self):
        from c5_consumer import consume_published
        from c3r_envelope import build
        from c2_relay import FileStore
        q=request((ROOT/REQUEST_PATH).read_bytes(),(ROOT/RELEASE_PATH).read_bytes(),time.time());binding=native_expected();raw=build(q,ENTRY,CONFIG_SHA,binding,b'{"fixture":true}',{'request_wall_seconds':1,'prefill_ms':1,'generation_ms':2})
        att=(ROOT/'results/remote_req028/c4_attestation_20260927/attestation.json').read_bytes();native=encode(dict(verify_native(binding),asset_attestation_sha256=sha(att),request_sha256=REQUEST_SHA,release_sha256=RELEASE_SHA,expires_at=EXPIRY));receipt={'commit':'e'*40,'path':RESPONSE_PATH,'sha256':sha(raw)};rraw=encode(receipt)
        args=[raw,receipt,rraw,sha(rraw),att,sha(att),native,sha(native),time.time()];ledger=FileStore(self.root/'consumer');consume_published(*args,ledger=ledger)
        with self.assertRaises(Rejected):consume_published(*args,ledger=ledger)
        for index,value in ((3,'0'*64),(5,'0'*64),(7,'0'*64),(8,EXPIRY)):
            changed=list(args);changed[index]=value
            with self.assertRaises(Rejected):consume_published(*changed)
        self.observer={'independent_C0_and_asset_pins':True,'provenance_expiry_replay_rejected':True,'no_tool_action':True}
    def test_source_approval_commit_policy_has_no_self_hash_cycle(self):
        repo=self.root/'approval-repo';repo.mkdir();self.git(repo,'init');(repo/'candidate').write_text('inert candidate');self.git(repo,'add','.');self.git(repo,'commit','-m','candidate');source=self.git(repo,'rev-parse','HEAD')
        a={'permission':'execute_one_c5_request','approved_source_commit':source,'release_manifest_sha256':RELEASE_SHA,'request_commit':REQUEST_COMMIT,'request_path':REQUEST_PATH,'request_sha256':REQUEST_SHA,'config_sha256':CONFIG_SHA,'response_path':RESPONSE_PATH,'expires_at':EXPIRY,'expected_main_policy':'exact-approval-commit'}
        path='docs/req028_c5_source_approval_20260927.json';file=repo/path;file.parent.mkdir();raw=encode(a);file.write_bytes(raw);self.git(repo,'add','.');self.git(repo,'commit','-m','explicit approval fixture');approved_commit=self.git(repo,'rev-parse','HEAD')
        resolved,_=approval(repo,source,approved_commit,path,sha(raw),time.time());self.assertEqual(resolved['expected_main'],approved_commit)
        with self.assertRaises(Rejected):approval(repo,source,approved_commit,path,'0'*64,time.time())
        self.observer={'fake_approval_in_temporary_repo':True,'expected_main_is_exact_approval_commit':True,'no_self_referential_commit_hash':True}
    def test_deadline_crossed_during_identity_probes_never_execs(self):
        import c5_gate
        instant=[0];spec={'load_deadline':10,'phase_deadline':10,'supervisor_pid':111,'supervisor_identity':'supervisor','driver_pid':222,'driver_identity':'driver'};path=self.root/'gate-test.json';path.write_bytes(encode(spec));read_fd,write_fd=os.pipe();ack_read,ack_write=os.pipe();os.write(write_fd,b'G')
        def identity_probe(pid):
            if pid==222:instant[0]=10;return 'driver'
            return 'supervisor'
        try:
            with patch.object(c5_gate,'command',return_value=['fixed-inert-never-executed']),patch.object(c5_gate,'identity',side_effect=identity_probe),patch('c5_gate.os.getppid',return_value=111),patch('c5_gate.time.time',side_effect=lambda:instant[0]),patch('c5_gate.os.execv') as execute:
                with self.assertRaisesRegex(Rejected,'immediately before exec'):c5_gate.main(read_fd,ack_write,str(path))
                execute.assert_not_called()
        finally:
            for fd in (read_fd,write_fd,ack_read,ack_write):os.close(fd)
        self.observer={'expired_during_identity_probes':True,'exec_refused':True,'no_child_created':True}
if __name__=='__main__':unittest.main()
