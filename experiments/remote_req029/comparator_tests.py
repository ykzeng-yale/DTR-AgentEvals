"""REQ029E inert evidence only: fake HTTP token IDs, fake Docker and local Git."""
import copy,json,os,shutil,signal,subprocess,sys,tempfile,threading,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from comparator_contract import *
from comparator_chain import Chain,observation_envelope,check_observation
from comparator_engine import Worker,Controller
from comparator_fixtures import release,InertModel,Sandbox,GOOD
from comparator_git import Transport
from comparator_launch import authorize,runtime_root
from c2_relay import Rejected
from c2_git import OWNER
from c3r_hooks import alive
from action_contract import parse_complete
from feedback import completed
from c0_protocol import analyze
from c6_protocol import check_observation as old_check,observation_envelope as old_envelope

class Wire:
    def __init__(self,store,root):
        self.store=store;self.root=root;self.failed=False;self.fetches=0;self.events=[];self.deadline=time.time()+60
        self.runner=SimpleNamespace(check=lambda:None,events=[])
    def read(self,kind,seq=None):
        self.runner.check();self.fetches+=1;time.sleep(.001);return self.store.get((kind,seq))
    def publish(self,kind,value,seq=None):
        key=kind,seq;require(key not in self.store,'immutable wire')
        obj=dict(commit='a'*40,blob='b'*40,path=self.root+'/'+kind+('' if seq is None else '/%02d'%seq)+'.json',sha256=sha(encode(value)))
        self.store[key]=(copy.deepcopy(value),obj);return obj

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='cmp029e-');self.root=Path(self.tmp.name)
        self.models=[];self.children=[];self.sandboxes=[];self.evidence={}
    def tearDown(self):
        for m in self.models:
            if m.life:
                try:m.stop()
                except BaseException as e:self.evidence.setdefault('cleanup_errors',[]).append(repr(e))
        for p in self.children:
            if p.poll() is None:p.kill()
            p.wait(timeout=4)
        for s in self.sandboxes:
            if s.guardian and s.guardian.poll() is None:
                try:s.close()
                except BaseException:pass
        put(self.root,'test.evidence.json',self.evidence)
        if os.environ.get('COMPARATOR_FIXTURE_OUT'):
            shutil.copytree(self.root,Path(os.environ['COMPARATOR_FIXTURE_OUT'])/self._testMethodName,ignore=shutil.ignore_patterns('.git','remote.git'))
        self.tmp.cleanup()
    def wait(self,fn,seconds=8):
        end=time.time()+seconds
        while not fn():
            self.assertLess(time.time(),end);time.sleep(.02)
    def pair(self,arm='qwen',mode='normal',configure=None):
        r,p=release(arm);store={}
        w=Worker(self.root/'worker',r,p,Wire(store,r['root']))
        c=Controller(self.root/'controller',r,p,Wire(store,r['root']))
        m=InertModel(self.root/'model',mode);s=Sandbox(self.root/'sandbox',r)
        self.models.append(m);self.sandboxes.append(s)
        if configure:configure(w,c,m,s,store)
        errors=[]
        def work():
            try:w.run(m)
            except BaseException as e:errors.append(repr(e))
        th=threading.Thread(target=work);th.start();c.run(s);th.join(58)
        self.assertFalse(th.is_alive());self.assertFalse(errors,errors)
        if m.life and m.life.record:self.assertFalse(alive(m.life.record))
        self.assertFalse((s.fake_root/'container.json').exists())
        self.evidence.update(worker=w.terminal,controller=c.terminal,loads=m.loads,fixture_tokenization=True)
        return r,w,c,m,s,store
    def test_both_arms_full_lifecycle_exit1_history(self):
        base=self.root
        for arm in ARMS:
            with self.subTest(arm=arm):
                self.root=base/arm;self.root.mkdir()
                r,w,c,m,s,store=self.pair(arm)
                self.assertEqual(c.terminal['status'],'submitted',c.terminal)
                self.assertEqual((w.claims,c.claims,m.loads),(2,2,1))
                self.assertFalse(w.terminal['call9_reached'])
                self.assertEqual(store['observation',1][0]['output']['returncode'],1)
                q1=store['request',1][0];q2=store['request',2][0];response=store['response',1][0]
                content=json.loads(response['raw'])['choices'][0]['message']['content']
                self.assertTrue(content.startswith('<think>'))
                self.assertEqual(q2['messages'],q1['messages']+[dict(role='assistant',content=content),store['observation',1][0]['observation']])
                self.assertEqual(len(list(m.root.glob('physical-*.json'))),2)
                self.assertEqual(w.terminal['cell'],cell(r))
        self.root=base
    def test_actual_call9_and_24_no_padding_or_switch(self):
        r,w,c,m,s,store=self.pair('klear','cap')
        self.assertEqual((w.claims,c.claims,m.loads),(24,24,1),c.terminal)
        self.assertEqual(c.terminal['status'],'action_cap')
        self.assertTrue(w.terminal['call9_reached']);self.assertEqual(len(w.terminal['dispatches']),24)
        ninth=w.terminal['dispatches'][8]
        self.assertEqual(ninth['sequence'],9);self.assertGreater(ninth['remaining_seconds'],0)
        self.assertTrue((m.root/'physical-09.json').exists());self.assertTrue((m.root/'physical-24.json').exists())
        self.assertFalse((m.root/'physical-25.json').exists())
        self.assertEqual(len(store['request',24][0]['messages']),48)
        self.assertEqual(store['observation',1][0]['output']['returncode'],0)
    def test_nonzero_sentinel_not_submission(self):
        r,w,c,m,s,store=self.pair('qwen','nonzero')
        self.assertEqual(c.terminal['status'],'submitted',c.terminal)
        self.assertEqual((w.claims,c.claims),(2,2))
        self.assertEqual(store['observation',1][0]['output']['returncode'],1)
    def test_context_overflow_terminal_cleanup(self):
        r,w,c,m,s,store=self.pair('klear','context')
        self.assertEqual((w.claims,c.claims),(0,0));self.assertIn('context overflow',w.terminal['error'])
    def test_output_overflow_terminal_cleanup(self):
        r,w,c,m,s,store=self.pair('qwen','overflow')
        self.assertEqual((w.claims,c.claims),(1,1))
        self.assertNotIn(('observation',1),store);self.assertIn('output cap',c.terminal['error'])
    def test_common_parser_and_original_gate_regression(self):
        text='<think>unclosed prose\n'+chr(96)*3+'mswea_bash_command\nexit1\n'+chr(96)*3
        self.assertEqual(parse_complete(text,'stop')['raw_content'],text);self.assertFalse(analyze(text,'stop')['interface_gate'])
        for content,finish in ((text+text,'stop'),('no fence','stop'),(text,'length')):
            with self.assertRaises(ValueError):parse_complete(content,finish)
        out=dict(output='ordinary',returncode=1,exception_info=None);completed(out)
        r,p=release()
        with self.assertRaisesRegex(Rejected,'command failure'):old_check(old_envelope(r,p,1,{}, {},out),r,p,1,{}, {})
    def test_substitution_before_claim(self):
        r,p=release()
        modifications=[lambda x:x.update(arm='klear'),lambda x:x['model']['config'].update(cache_k='q4_0'),
            lambda x:x['task'].update(task_id='astropy__astropy-14598'),
            lambda x:x.update(initial_messages_utf8='changed'),
            lambda x:x['sandbox'].update(qualified=False)]
        for i,modify in enumerate(modifications):
            bad=copy.deepcopy(r);modify(bad);root=self.root/str(i)
            with self.assertRaises((Rejected,ValueError)):Worker(root,bad,p,Wire({},r['root']))
            self.assertFalse(root.exists())
        c=Chain(r,p);q=c.request(r['expires_at'])
        for key,val in (('messages',[]),('cell',dict(cell(r),arm='klear')),('config_sha256','0'*64)):
            with self.assertRaises(Rejected):c.check_request(dict(q,**{key:val}),r['expires_at'])
    def test_native_and_feedback_substitution(self):
        r,p=release();history=messages(r);served=template('qwen')
        b=dict(arm='qwen',template_sha256=ARMS['qwen']['template_sha'],native_exact=True,
            template_relation=native_template('qwen',served,served),rendered=rendered(history,'qwen'),
            token_ids=[1],messages_sha256=sha(encode(history)))
        bound_messages(b,history,r)
        for kw in (dict(arm='klear'),dict(rendered='changed'),dict(token_ids=[1]*31233),dict(template_sha256='0'*64)):
            with self.assertRaises(Rejected):bound_messages(dict(b,**kw),history,r)
        obs=observation_envelope(r,p,1,{}, {},dict(output='ordinary',returncode=1,exception_info=None))
        obs['output']['returncode']=0
        with self.assertRaises(Rejected):check_observation(obs,r,p,1,{}, {},{'sha256':sha(encode(obs))})
    def test_disabled_and_old_approval_reject_before_side_effect(self):
        with self.assertRaises(Rejected):validate(disabled())
        for name in ('docs/req028_c6_test.json','docs/req029c_binding_source_approval_20260927.json'):
            with self.assertRaisesRegex(Rejected,'approval allowlist'):authorize('a'*40,name,'b'*64)
        r,p=release();raw=encode(dict(r,source_hashes={}))
        with patch('comparator_launch.git',return_value=raw):
            with self.assertRaisesRegex(Rejected,'complete source inventory'):authorize('a'*40,'docs/req029e_fixture.json',sha(raw))
    def test_actual_durable_claim_death_no_redispatch(self):
        root=self.root/'dead'
        p=subprocess.run([sys.executable,str(HERE/'comparator_fixture_driver.py'),'claim',str(root)],timeout=4)
        self.assertEqual(p.returncode,79);self.assertTrue((root/'claims/model-01.json').exists())
        r,pin=release()
        with self.assertRaises(FileExistsError):Worker(root,r,pin,Wire({},r['root']))
        self.assertFalse((root/'dispatch').exists())
    def test_actual_driver_death_both_owners_cleanup(self):
        for mode in ('model','sandbox'):
            root=self.root/mode;root.mkdir()
            p=subprocess.Popen([sys.executable,str(HERE/'comparator_fixture_driver.py'),mode,str(root)],
                               stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            self.children.append(p);self.wait(lambda:(root/'ready').exists(),15)
            p.kill();p.wait(timeout=3)
            path=root/('model/supervisor_exit.json' if mode=='model' else 'sandbox/state/terminal.json')
            self.wait(path.exists,8);report=json.loads(path.read_bytes())
            self.assertTrue(report['cleanup']['owned_absent'],report)
    def test_actual_http_timeout_cleanup(self):
        r,p=release();m=InertModel(self.root/'model','hang');self.models.append(m)
        m.start(r,p,self.root);m.bind(messages(r),time.time()+3)
        with self.assertRaises((Rejected,RuntimeError,TimeoutError)):m.generate(messages(r),time.time()+.4)
        m.stop();self.assertFalse(alive(m.life.record))
    def test_terminal_guard_latch(self):
        r,p=release();m=InertModel(self.root/'model');self.models.append(m);m.start(r,p,self.root)
        (m.root/'fake_sample.json').write_bytes(encode(dict(GOOD,free_percent=19)))
        self.wait(lambda:(m.root/'supervisor_exit.json').exists())
        with self.assertRaises((Rejected,RuntimeError)):m.check()
        self.assertFalse(alive(m.life.record))
    def test_real_pipeline_parse_length_and_template_failures(self):
        base=self.root
        for mode in ('invalid','length','template'):
            with self.subTest(mode=mode):
                self.root=base/mode;self.root.mkdir()
                r,w,c,m,s,store=self.pair('klear',mode)
                self.assertEqual(c.claims,0)
                self.assertEqual(w.claims,0 if mode=='template' else 1)
                self.assertEqual(len(list(m.root.glob('physical-*.json'))),0 if mode=='template' else 1)
                if mode!='template':self.assertTrue((w.root/'raw/01.json').exists())
                self.assertNotIn(('request',2),store)
        self.root=base
    def test_actual_claim_boundary_no_action(self):
        def configure(w,c,m,s,store):
            def crash(stage):
                if stage=='after_action_claim':raise RuntimeError('fixed crash before sandbox dispatch')
            c.crash=crash
        r,w,c,m,s,store=self.pair(configure=configure)
        self.assertEqual(c.claims,1)
        self.assertFalse(list(s.fake_root.glob('action-*')))
        self.assertTrue((c.root/'claims/action-01.json').exists())
    def test_exact_arm_argv_no_cache_fallback(self):
        from comparator_attest import argv
        for arm in ARMS:
            r,p=release(arm);cmd=argv(r,'c4-cmp029e-owned-fixture',12345)
            self.assertEqual(Path(cmd[cmd.index('-m')+1]).name,ARMS[arm]['model'])
            for flag in ('--cache-type-k','--cache-type-v'):self.assertEqual(cmd[cmd.index(flag)+1],ARMS[arm]['cache'])
            self.assertEqual(cmd[cmd.index('--n-predict')+1],'1536')
            self.assertIn('--no-context-shift',cmd);self.assertIn('--no-warmup',cmd)
    def test_pretty_approval_bytes_survive_sandbox_adapter(self):
        from comparator_sandbox import QualifiedSandbox
        r,p=release();raw=json.dumps(r,indent=2).encode();pin=sha(raw)
        self.assertNotEqual(pin,p)
        s=QualifiedSandbox(self.root/'adapter',r,{'release_sha':pin})
        def runner(argv,deadline):
            spec=json.loads(Path(argv[-1]).read_bytes())
            self.assertEqual(spec['release_sha256'],pin)
            Path(spec['output_path']).write_text('{}')
        s.runner.run=runner;s.op('check',{},time.time()+1)
    def test_admission_two_pass_gap_and_no_retry(self):
        from a6r_gate import admit
        clock=[0];reads=[];launches=[]
        def sample():reads.append(clock[0]);return GOOD
        def launch(last):launches.append(clock[0]);return 'started'
        result=admit(sample,lambda:clock[0],lambda t:clock.__setitem__(0,clock[0]+t),lambda *x:None,launch,900)
        self.assertEqual(result,'started');self.assertEqual(reads,[0,60,60]);self.assertEqual(launches,[60])
        clock[0]=0;reads.clear()
        with self.assertRaises(TimeoutError):
            admit(lambda:dict(GOOD,free_percent=74),lambda:clock[0],lambda t:clock.__setitem__(0,clock[0]+t),lambda *x:None,launch,900)
        self.assertEqual(launches,[60])
    def test_production_guardian_entrypoint_binding(self):
        import comparator_guardian as g
        r,p=release();base=self.root/'controller';state=base/'sandbox/state';state.mkdir(parents=True)
        now=time.time();label='f'*64
        spec=dict(root=str(state),release=r,release_sha256=p,approval_args={},
            created_at=now,preflight_deadline=min(r['expires_at'],now+1200),
            label=label,name='dtr-'+r['run_id']+'-'+label[:12])
        path=state/'spec.json';put(state,path.name,spec);calls=[]
        with patch('comparator_launch.authorize',return_value=(r,p)),patch('comparator_launch.runtime_root',return_value=base),patch.object(g,'Docker',return_value='inert-backend'),patch.object(g,'Guardian',return_value=SimpleNamespace(run=lambda:calls.append('ran'))) as ctor:
            g.main(path)
            self.assertEqual(ctor.call_args.args,(spec,'inert-backend'))
        self.assertEqual(calls,['ran'])
    def test_production_adapter_entrypoint_binding(self):
        import comparator_sandbox_host as h
        from c3r_arbiter import identity
        r,p=release();base=self.root.resolve()/'controller';sandbox=base/'sandbox';sandbox.mkdir(parents=True)
        now=time.time();spec=dict(operation='preflight',payload={},deadline=now+5,sequence=1,run_id=r['run_id'],
            release=r,release_sha256=p,approval_args={},created_at=now,
            driver_pid=os.getpid(),driver_identity=identity(os.getpid()),output_path=str(sandbox/'out.json'))
        path=sandbox/'spec.json';put(sandbox,path.name,spec)
        with patch('comparator_launch.authorize',return_value=(r,p)),patch('comparator_launch.runtime_root',return_value=base),patch.object(h,'exchange',return_value={'inert':True}) as exchange:
            h.main(path)
            self.assertEqual(exchange.call_args.args[2]['release'],r)
            self.assertEqual(exchange.call_args.args[2]['release_sha256'],p)
        self.assertEqual(json.loads((sandbox/'out.json').read_bytes()),{'inert':True})
    def test_exact_source_approval_roundtrip_and_hash_tamper(self):
        r,p=release();raw=json.dumps(r,indent=2).encode()
        def git(*args,**kw):
            spec=args[1]
            return raw if spec.endswith(':docs/req029e_fixture.json') else (ROOT/spec.split(':',1)[1]).read_bytes()
        with patch('comparator_launch.git',side_effect=git):
            got,pin=authorize('b'*40,'docs/req029e_fixture.json',sha(raw))
            self.assertEqual(got,r);self.assertEqual(pin,sha(raw))
            with self.assertRaisesRegex(Rejected,'approval SHA'):
                authorize('b'*40,'docs/req029e_fixture.json','0'*64)
    def test_local_git_namespace_and_immutable_objects(self):
        def git(repo,*args):
            p=subprocess.run(['git',*args],cwd=repo,env=dict(os.environ,**OWNER),capture_output=True,timeout=5)
            self.assertEqual(p.returncode,0,p.stderr);return p.stdout.decode().strip()
        bare=self.root/'remote.git';a=self.root/'a';b=self.root/'b'
        git(self.root,'init','--bare',str(bare));git(self.root,'clone',str(bare),str(a))
        git(a,'checkout','-b','main');put(a,'initial',b'inert');git(a,'add','initial');git(a,'commit','-m','inert');git(a,'push','origin','main')
        git(self.root,'clone',str(bare),str(b));r,p=release()
        ct=Transport(a,self.root/'ct',r['root'],'controller',r['expires_at'],str(bare),self.root,0)
        wt=Transport(b,self.root/'wt',r['root'],'worker',r['expires_at'],str(bare),self.root,0)
        obj=ct.publish('preflight',dict(cell=cell(r)));value,other=wt.read('preflight');self.assertEqual(obj,other)
        self.assertEqual(value,dict(cell=cell(r)))
        with self.assertRaises(Rejected):wt.publish('request',{},1)
        with self.assertRaises(Rejected):ct.publish('preflight',{'changed':True})
        self.assertTrue(ct.failed)
if __name__=='__main__':unittest.main(verbosity=2)
