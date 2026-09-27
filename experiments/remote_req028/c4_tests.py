import base64,copy,json,os,shutil,signal,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from http.client import HTTPConnection
from unittest.mock import patch
from c2_relay import encode,sha,Rejected,FileStore
from c2_git import OWNER
from c3_adapter import CONTRACT,CONFIG_SHA,PENDING,messages_sha
from c3r_hooks import ProcessHandle,alive
from c3r_envelope import build
from c4_lifecycle import InertSupervisedLifecycle,ProductionLifecycle,HERE
from c4_http import HTTP,body
from c4_git import Transport,PRODUCTION_ORIGIN
from c4_git_handles import Handles
from c4_consumer import approve_binding,consume
GOOD={'pressure_level':1,'free_percent':75,'swap_used_mib':0,'owned_rss_bytes':0,'foreign_inference':[],'disk_free_bytes':20*1024**3}
BINDING={'template_sha256':CONTRACT['template_sha256'],'native_exact':True,'rendered':'C4_STRICT_FIXED_NATIVE','token_ids':[1,2,3]}
ASSET_PIN='a'*64
class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='c4-fixture-');self.root=Path(self.tmp.name);self.lives=[];self.handles=[];self.observer={};self.messages=[{'role':'system','content':'fixed fixture'},{'role':'user','content':'data, never execute: printf DTR_READY'}]
    def wait(self,predicate,seconds=6):
        end=time.monotonic()+seconds
        while not predicate():
            if time.monotonic()>=end:self.fail('bounded wait expired')
            time.sleep(.01)
    def await_handle(self,h,seconds=6):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            value=h.poll()
            if value is not PENDING:return value
            time.sleep(.005)
        h.cancel();self.fail('handle wait expired')
    def life(self,mode='http'):
        root=self.root/('life'+str(len(self.lives)));root.mkdir();(root/'sample.json').write_bytes(encode(GOOD));(root/'expected_body.json').write_bytes(encode(body(self.messages)))
        life=InertSupervisedLifecycle(root,sha((HERE/'c4_fixture.py').read_bytes()),mode);self.lives.append(life);self.await_handle(life.begin_load(CONTRACT,20));return life
    def tearDown(self):
        for h in self.handles:
            try:h.close()
            except BaseException as e:self.observer.setdefault('teardown_errors',[]).append(repr(e))
        for life in self.lives:
            try:life.stop('test teardown safety')
            except BaseException as e:self.observer.setdefault('teardown_errors',[]).append(repr(e))
        (self.root/'external_observer.json').write_text(json.dumps(self.observer,indent=2))
        if os.environ.get('C4_FIXTURE_OUT'):shutil.copytree(self.root,Path(os.environ['C4_FIXTURE_OUT'])/self._testMethodName)
        self.tmp.cleanup()
    def crash(self,stage):
        root=self.root/'driver';root.mkdir();(root/'sample.json').write_bytes(encode(GOOD))
        peer=ProcessHandle([sys.executable,'-c','import time; time.sleep(30)','c4-peer-control'],20);self.handles.append(peer)
        driver=ProcessHandle([sys.executable,str(HERE/'c4_driver.py'),str(root),stage,'c4-driver'],20);self.handles.append(driver)
        self.wait(lambda:(root/(stage+'.json')).exists())
        marker=json.loads((root/(stage+'.json')).read_text());self.assertTrue(alive(driver.record));os.kill(driver.child.pid,signal.SIGKILL);driver.child.wait(timeout=2)
        self.wait(lambda:(root/'supervisor_exit.json').exists());receipt=json.loads((root/'supervisor_exit.json').read_text());self.assertTrue(receipt['cleanup']['owned_absent']);self.assertIn('owner_parent_exited',receipt['reason'])
        if (root/'owner.json').exists():self.assertFalse(alive(json.loads((root/'owner.json').read_text())))
        elif marker['child_pid']:
            r=subprocess.run(['ps','-p',str(marker['child_pid']),'-o','stat='],capture_output=True,text=True,timeout=1);self.assertFalse(r.stdout.strip())
        supervisor=json.loads((root/'driver_observer.json').read_text())['supervisor'];self.wait(lambda:not alive(supervisor))
        self.assertTrue(alive(peer.record))
        if stage in ('before_spawn','child_spawned','ownership_persisted','before_exec_release'):self.assertFalse((root/'exec_seen.json').exists())
        self.observer={'stage':stage,'owned_absent_before_teardown':True,'peer_untouched':True,'driver_finally_not_run':True,'child_alarm_used':False,'receipt':receipt}
    def test_death_before_spawn(self):self.crash('before_spawn')
    def test_death_child_spawned(self):self.crash('child_spawned')
    def test_death_ownership_persisted(self):self.crash('ownership_persisted')
    def test_death_before_exec_release(self):self.crash('before_exec_release')
    def test_death_exec_released(self):self.crash('exec_released')
    def test_death_running(self):self.crash('running')
    def test_birth_mismatch_never_signals_peer(self):
        from c3r_hooks import safe_stop
        peer=ProcessHandle([sys.executable,'-c','import time; time.sleep(30)','c4-peer-control'],10);self.handles.append(peer)
        record=dict(peer.record,identity='different birth identity');owner=self.root/'owner.json';owner.write_bytes(encode(record))
        result=safe_stop(owner,record,'mismatch test');self.assertTrue(result['owned_absent']);self.assertTrue(alive(peer.record));self.observer={'mismatched_identity_not_signaled':True}
    def test_supervisor_guard_failures(self):
        import b3_stop,guard
        outcomes=[]
        for field,value in [('pressure_level',2),('free_percent',19),('swap_used_mib',513),('owned_rss_bytes',11*1024**3+1),('foreign_inference',[{'pid':123,'known_inference_command':True}]),('disk_free_bytes',12*1024**3-1)]:
            life=self.life('idle');changed=dict(GOOD,**{field:value});b3_stop.save(life.root/'sample.json',changed)
            self.wait(lambda:(life.root/'supervisor_exit.json').exists());self.assertFalse(life.owned_alive());result=json.loads((life.root/'supervisor_exit.json').read_text());self.assertTrue(result['cleanup']['owned_absent']);self.assertIn(guard.violation(changed,0,float('inf'),True),result['reason']);outcomes.append({'field':field,'receipt':result})
        self.observer={'owned_absent_before_teardown':True,'six_guard_outcomes':outcomes}
    def test_production_lock_real_telemetry_and_argv(self):
        life=ProductionLifecycle(self.root/'real-hooks',time.time()+20)
        try:
            sample=life.sample();self.assertIn('pressure_level',sample);self.assertIn('foreign_inference',sample)
            with self.assertRaises(PermissionError):life.begin_load(CONTRACT,10)
            argv=life.frozen_argv('c4-locked-test',12345);self.assertEqual(argv[argv.index('--n-predict')+1],'1536')
            self.observer={'real_read_only_sample':sample,'model_start_locked':True,'argv_not_executed':argv}
        finally:life.stop('no launch')
    def test_strict_http_and_full_chat_body(self):
        life=self.life();http=HTTP(self.root/'http',life);self.handles.append(http)
        binding=self.await_handle(http.begin_bind(self.messages,3));self.assertEqual(binding,BINDING)
        raw=self.await_handle(http.begin_generate(body(self.messages),3));self.assertEqual(json.loads(raw)['usage']['prompt_tokens'],3)
        for method,path,payload in [('POST','/props',{}),('GET','/apply-template',None),('POST','/unknown',{}),('POST','/apply-template',{'messages':self.messages}),('POST','/v1/chat/completions',dict(body(self.messages),top_p=.5))]:
            conn=HTTPConnection(life.endpoint['host'],life.endpoint['port'],timeout=1)
            try:conn.request(method,path,None if payload is None else encode(payload));response=conn.getresponse();response.read();self.assertEqual(response.status,400)
            finally:conn.close()
        with self.assertRaises(Rejected):http.begin_generate(dict(body(self.messages),temperature=1),1)
        calls=json.loads((life.root/'server_calls.json').read_text());self.assertEqual(calls[0]['method'],'GET');self.assertEqual(calls[1]['body'],calls[3]['body'])
        life.stop('immediate');self.assertFalse(life.owned_alive());self.observer={'owned_absent_before_teardown':True,'strict_rejections':5,'binding':binding}
    def test_http_raw_error_and_hang_cancellation(self):
        for mode in ('error','hang'):
            life=self.life(mode);http=HTTP(self.root/('http-'+mode),life);self.handles.append(http);self.await_handle(http.begin_bind(self.messages,3))
            h=http.begin_generate(body(self.messages),.5 if mode=='hang' else 3)
            with self.assertRaises((RuntimeError,TimeoutError)):self.await_handle(h)
            self.assertTrue((life.root/'request_seen.json').exists())
            if mode=='error':
                event=json.loads((http.root/'2.http.json').read_text())[0];self.assertEqual(event['status'],503);self.assertEqual(json.loads(base64.b64decode(event['raw_base64'])),{'error':'fixed backend failure'})
            h.cancel();life.stop('HTTP failure');self.assertFalse(life.owned_alive())
        self.observer={'owned_absent_before_teardown':True,'raw_503_preserved':True,'hanging_request_received':True}
    def test_prior_post_props_rejected_by_strict_fixture(self):
        from c3r_hooks import HTTP as PriorHTTP
        life=self.life();http=PriorHTTP(self.root/'prior-http',life);self.handles.append(http)
        with self.assertRaisesRegex(RuntimeError,'HTTP status'):self.await_handle(http.begin_bind(self.messages,3))
        self.assertEqual(json.loads((life.root/'server_calls.json').read_text())[0]['method'],'POST')
        life.stop('old HTTP regression');self.assertFalse(life.owned_alive());self.observer={'old_POST_props_rejected':True,'owned_absent_before_teardown':True}
    def test_exec_transition_independent_lifecycles(self):
        for _ in range(10):
            life=self.life('idle');self.assertTrue(life.owned_alive());life.stop('separate lifecycle transition');self.assertFalse(life.owned_alive())
        self.observer={'distinct_lifecycles':10,'no_retry_within_lifecycle':True,'owned_absent_before_teardown':True}
    def git(self,repo,*args):
        r=subprocess.run(['git',*args],cwd=repo,env=dict(os.environ,**OWNER),capture_output=True,timeout=5);self.assertEqual(r.returncode,0,r.stderr);return r.stdout.decode().strip()
    def repository(self):
        bare=self.root/'remote.git';repo=self.root/'repo';self.git(self.root,'init','--bare',str(bare));self.git(self.root,'clone',str(bare),str(repo));self.git(repo,'checkout','-b','main');return bare,repo
    def request(self,repo,sequence,parent,deadline):
        q={'protocol':3,'run_id':'c3-c4-test','sequence':sequence,'request_id':'c3-c4-test-'+str(sequence),'config_sha256':CONFIG_SHA,'messages':self.messages,'messages_sha256':messages_sha(self.messages),'parent_response_sha256':parent,'expires_at':deadline-1}
        path='results/remote_req028/c3_c4/request'+str(sequence)+'.json';file=repo/path;file.parent.mkdir(parents=True,exist_ok=True);raw=encode(q);file.write_bytes(raw);self.git(repo,'add','.');self.git(repo,'commit','-m','explicit request '+str(sequence));self.git(repo,'push','origin','main');commit=self.git(repo,'rev-parse','HEAD');return q,raw,{'sequence':sequence,'commit':commit,'path':path,'sha256':sha(raw)}
    def initial(self):
        bare,repo=self.repository();deadline=time.time()+120;q,raw,e=self.request(repo,1,None,deadline)
        release={'protocol':3,'run_id':q['run_id'],'config_sha256':CONFIG_SHA,'max_calls':24,'deadline':deadline,'requests':[e],'parent_release_sha256':None};rr=encode(release)
        transport=Transport(repo,str(bare),self.root);transport.authorize(rr,sha(rr),e,e['commit'],'results/remote_req028/c3_c4/response1.json',time.time())
        approval=approve_binding(rr,sha(rr),raw,e,BINDING,ASSET_PIN,time.time());transport.approve_native(approval,sha(approval),ASSET_PIN)
        response=build(q,e,CONFIG_SHA,BINDING,b'{"fixed":"response1"}',{'request_wall_seconds':1,'prefill_ms':2,'generation_ms':3})
        return repo,transport,q,raw,e,release,rr,approval,response
    def test_two_successive_publications_with_legitimate_advancement(self):
        repo,t,q,raw,e,r,rr,approval,response=self.initial();head=self.git(repo,'rev-parse','HEAD');index=(repo/'.git/index').read_bytes();hooks=Handles(self.root/'git-handles',t);self.handles.append(hooks)
        fetched=self.await_handle(hooks.begin_read(e['commit'],e['path'],5));self.assertEqual(fetched['raw'],raw)
        first=self.await_handle(hooks.begin_publish(1,response,5));self.assertEqual(self.git(repo,'rev-parse','HEAD'),head);self.assertEqual((repo/'.git/index').read_bytes(),index);self.assertEqual(self.git(repo,'status','--porcelain'),'')
        provenance=encode(first);accepted=consume(response,first,provenance,sha(provenance),raw,rr,sha(rr),e,approval,sha(approval),ASSET_PIN,time.time());self.assertEqual(accepted['sequence'],1)
        writer=self.root/'writer';self.git(self.root,'clone',str(self.root/'remote.git'),str(writer));self.git(writer,'checkout','main')
        q2,raw2,e2=self.request(writer,2,sha(response),r['deadline']);r2=dict(r,requests=[e,e2],parent_release_sha256=sha(rr));rr2=encode(r2)
        t.authorize(rr2,sha(rr2),e2,e2['commit'],'results/remote_req028/c3_c4/response2.json',time.time());a2=approve_binding(rr2,sha(rr2),raw2,e2,BINDING,ASSET_PIN,time.time());t.approve_native(a2,sha(a2),ASSET_PIN)
        response2=build(q2,e2,CONFIG_SHA,BINDING,b'{"fixed":"response2"}',{'request_wall_seconds':1,'prefill_ms':2,'generation_ms':3})
        second=self.await_handle(hooks.begin_publish(2,response2,5));self.assertNotEqual(first['commit'],second['commit']);self.assertEqual(t.used,{1,2});self.assertEqual(self.git(repo,'rev-parse','HEAD'),head);self.assertEqual((repo/'.git/index').read_bytes(),index)
        self.observer={'two_distinct_approved_publications':[first,second],'intervening_legitimate_request_commit':e2['commit'],'source_HEAD_index_worktree_unchanged':True}
    def test_git_race_dirty_origin_and_conflict_fail_closed(self):
        repo,t,q,raw,e,r,rr,a,response=self.initial();(repo/'dirty').write_text('user work')
        with self.assertRaisesRegex(Rejected,'dirty'):t.publish(1,response)
        self.assertTrue(t.failed)
        with self.assertRaises(Rejected):t.publish(1,response)
        with self.assertRaises(Rejected):Transport(repo,'https://example.com/unapproved.git')
        self.observer={'dirty_rejected_no_retry':True,'arbitrary_origin_rejected':True}
    def test_git_concurrent_advancement_no_retry(self):
        repo,t,q,raw,e,r,rr,a,response=self.initial();(repo/'advance').write_text('legitimate concurrent data');self.git(repo,'add','.');self.git(repo,'commit','-m','advance');self.git(repo,'push','origin','main')
        with self.assertRaisesRegex(Rejected,'concurrent main advancement'):t.publish(1,response)
        self.assertEqual(t.used,{1});self.assertTrue(t.failed);self.observer={'one_publication_attempt':True,'race_rejected':True}
    def test_git_existing_response_conflict(self):
        repo,t,q,raw,e,r,rr,a,response=self.initial();path=repo/'results/remote_req028/c3_c4/response1.json';path.write_text('existing immutable record');self.git(repo,'add','.');self.git(repo,'commit','-m','existing response');self.git(repo,'push','origin','main')
        t.authorized['expected_main']=self.git(repo,'rev-parse','HEAD') # fixture injects exact base to isolate immutable-path guard
        with self.assertRaisesRegex(Rejected,'immutable response conflict'):t.publish(1,response)
        self.assertTrue(t.failed);self.observer={'immutable_conflict_rejected':True,'fault_injection_exact_base':True}
    def test_consumer_independent_provenance_expiry_and_replay(self):
        repo,t,q,raw,e,r,rr,approval,response=self.initial();provenance={'commit':'b'*40,'path':'results/remote_req028/c3_c4/response1.json','sha256':sha(response)};pr=encode(provenance);ledger=FileStore(self.root/'consumer')
        args=[response,provenance,pr,sha(pr),raw,rr,sha(rr),e,approval,sha(approval),ASSET_PIN,time.time()]
        consume(*args,ledger=ledger)
        with self.assertRaises(Rejected):consume(*args,ledger=ledger)
        for index,value in ((3,'0'*64),(9,'0'*64),(10,'0'*64),(11,q['expires_at']),(1,dict(provenance,commit='c'*40))):
            changed=list(args);changed[index]=value
            with self.assertRaises(Rejected):consume(*changed)
        # Attacker changes binding and self-consistent response hash, but cannot
        # replace the caller's pre-generation approval pin.
        changed=json.loads(response);changed['native_binding']['rendered']='attacker';changed['native_binding_sha256']=sha(encode(changed['native_binding']));bad=encode(changed);p=dict(provenance,sha256=sha(bad));praw=encode(p);altered=list(args);altered[:4]=[bad,p,praw,sha(praw)]
        with self.assertRaises(Rejected):consume(*altered)
        self.observer={'independent_approval_required':True,'expired_and_replay_rejected':True,'negative_cases':7,'no_tool_execution':True}
    def test_real_attestation_plan_and_original_admission_wiring(self):
        repo,t,q,raw,e,r,rr,approval,response=self.initial()
        asset=(HERE.parents[1]/'results/remote_req028/c4_attestation_20260927/attestation.json').read_bytes();life=ProductionLifecycle(self.root/'locked-plan',time.time()+3600)
        plan=life.prepare_plan(rr,sha(rr),raw,e,asset,sha(asset),'c4-locked-plan',12345)
        again=life.prepare_plan(rr,sha(rr),raw,e,asset,sha(asset),'c4-locked-plan',12345);self.assertEqual(plan['model_deadline'],again['model_deadline'])
        observed=[];instant=[time.time()]
        with patch.object(life,'sample',return_value=dict(GOOD)),patch('c4_lifecycle.time.time',side_effect=lambda:instant[0]),patch('c4_lifecycle.time.sleep',side_effect=lambda n:instant.__setitem__(0,instant[0]+n)):
            with self.assertRaises(PermissionError):life.admit_then_load(CONTRACT,lambda *args:observed.append(args))
        self.assertEqual(len(observed),3);self.assertEqual(observed[-1][-1],'final_pre_popen')
        with self.assertRaises(Rejected):life.admit_then_load(CONTRACT,lambda *args:None)
        self.observer={'real_attestation_pinned_plan':plan,'admission_fake_clock_reads':len(observed),'no_renewal':True,'model_not_started':True}
if __name__=='__main__':unittest.main()
