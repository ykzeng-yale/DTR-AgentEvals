"""Unique C6 tests only. No import of prior test classes, real model, or Docker."""
import copy,json,os,shutil,signal,subprocess,sys,tempfile,threading,time,unittest
from pathlib import Path
from types import SimpleNamespace
from c2_git import OWNER
from c2_relay import Rejected
from c3r_hooks import alive
from c4_http import HTTP
from c5_lifecycle import free_port
from c6_protocol import *
from c6_model import Lifecycle,Model
from c6_process import Runner
from c6_git import Transport
from c6_engine import Worker,Controller

GOOD=dict(pressure_level=1,free_percent=75,swap_used_mib=0,owned_rss_bytes=0,
          foreign_inference=[],disk_free_bytes=20*1024**3)

def fake_release(seconds=40):
    r=dict(protocol=6,run_id='c6-fixture',root='results/remote_req028/c6_runs/c6-fixture',
        expires_at=time.time()+seconds,worker_commit='a'*40,controller_commit='a'*40,
        source_hashes={'experiments/remote_req028/c6_tests.py':'b'*64},config_sha256=CONFIG_SHA,
        max_calls=24,max_actions=24,phase_seconds=1800,
        delegation={'controller_commit':'a'*40,'rule':'append_exact_accepted_assistant_and_pinned_observation_only','sequences':[1,24]},
        roles={'request':'controller','observation':'controller','response':'worker','preflight':'controller',
            'ready':'worker','controller_terminal':'controller','worker_terminal':'worker'},
        sandbox={'image':IMAGE,'head':HEAD,'context':'colima-dtr','qualified':True,'storage_enforced':True,
            'controller_death_cleanup_qualified':True,'qualification_sha256':'b'*64,'adapter_sha256':'b'*64},
        submission={'revision':MINI,'yaml_sha256':YAML_SHA,'docker_source_sha256':'b'*64,'checker_sha256':'b'*64},
        evaluation={'strict_source_sha256':'b'*64,'config_sha256':'b'*64,'task_manifest_sha256':'b'*64,'execution_authorized':False},
        initial_messages_sha256=sha(encode(initial())))
    return r,sha(encode(r))

class Memory:
    """Explicit test injection, never selectable from production CLI."""
    def __init__(self,store):
        self.store=store;self.failed=False;self.fetches=0;self.events=[]
        self.runner=SimpleNamespace(check=lambda:None,events=[])
    def read(self,kind,seq=None):
        self.runner.check();self.fetches+=1;time.sleep(.005)
        return self.store.get((kind,seq))
    def publish(self,kind,value,seq=None):
        raw=encode(value);key=(kind,seq)
        obj=dict(commit=sha(raw)[:40],blob=sha(raw)[:40],path=kind,sha256=sha(raw))
        if key in self.store:require(self.store[key]==(value,obj),'conflict')
        self.store[key]=(value,obj)
        return obj

class InertModel(Model):
    def __init__(self,root,mode='normal'):
        super().__init__({});self.root=Path(root);self.mode=mode;self.loads=0
    def start(self,r,pin,root):
        self.loads+=1;require(self.loads==1,'no reload');now=time.time()
        spec=dict(inert_test=True,fixture_sha256=sha((HERE/'c6_fixture.py').read_bytes()),
            phase_started=now,phase_deadline=min(now+55,r['expires_at']),load_deadline=min(now+8,r['expires_at']),
            token='c4-c6-owned-inert-'+str(time.time_ns()),port=free_port())
        self.life=Lifecycle(self.root,spec)
        put(self.root,'fake_sample.json',GOOD);put(self.root,'mode',self.mode.encode())
        self.life.launch()
        while not self.life.health():time.sleep(.02)
        self.http=HTTP(self.root/'http',self.life)
        return now

class InertSandbox:
    def __init__(self,fail=False,cap=False):
        self.commands=[];self.fail=fail;self.cap=cap;self.closed=False
    def preflight(self,r,d):pass
    def execute(self,command,deadline):
        # Record data, return fixed output; do not eval/exec/shell it.
        self.commands.append(command)
        return dict(output='fixture output',returncode=1 if self.fail else 0,exception_info=None)
    def submitted(self,output,deadline):return len(self.commands)==2 and not self.cap
    def diff(self,d):return '# inert diagnostic, not a generated patch\n'
    def close(self):self.closed=True;return {'owned_absent':True,'fixture':True}

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='c6-inert-');self.root=Path(self.tmp.name)
        self.models=[];self.children=[];self.observer={}
    def tearDown(self):
        for m in self.models:
            try:m.stop()
            except BaseException as e:self.observer.setdefault('cleanup_errors',[]).append(repr(e))
        for p in self.children:
            if p.poll() is None:p.kill();p.wait(timeout=3)
        put(self.root,'test-observer.json',self.observer)
        if os.environ.get('C6_FIXTURE_OUT'):
            target=Path(os.environ['C6_FIXTURE_OUT'])/self._testMethodName
            # Git object caches are reproducible, not runtime evidence.
            shutil.copytree(self.root,target,ignore=shutil.ignore_patterns('.git','remote.git'))
        self.tmp.cleanup()
    def wait(self,fn,seconds=8):
        until=time.time()+seconds
        while not fn():
            self.assertLess(time.time(),until,'bounded wait');time.sleep(.01)
    def model(self,mode='normal'):
        m=InertModel(self.root/'model',mode);self.models.append(m);return m
    def pair(self,mode='normal',fail=False,cap=False,localgit=False,seconds=35,crash=None,configure=None):
        r,pin=fake_release(seconds);store={}
        if localgit:
            wt,ct,repo=self.transports(r)
        else:wt,ct=Memory(store),Memory(store)
        w=Worker(self.root/'worker',r,pin,wt);c=Controller(self.root/'controller',r,pin,ct)
        model=self.model(mode);sandbox=InertSandbox(fail,cap)
        if configure:configure(w,c,model,sandbox)
        if crash:
            role,stage=crash
            def injected(at):
                if at==stage:raise RuntimeError('injected crash after durable claim')
            (w if role=='worker' else c).crash=injected
        errors=[]
        def run_worker():
            try:w.run(model)
            except BaseException as e:errors.append(repr(e))
        th=threading.Thread(target=run_worker);th.start()
        c.run(sandbox);th.join(timeout=seconds+4)
        self.assertFalse(th.is_alive());self.assertFalse(errors,errors)
        self.assertTrue(sandbox.closed)
        if model.life and model.life.record:self.assertFalse(alive(model.life.record))
        self.observer.update(worker=w.terminal,controller=c.terminal,model_loads=model.loads,
                             actions=len(sandbox.commands),owned_absent_before_teardown=True)
        return w,c,model,sandbox,store
    def git(self,repo,*args):
        r=subprocess.run(['git',*args],cwd=repo,env=dict(os.environ,**OWNER),capture_output=True,timeout=5)
        self.assertEqual(r.returncode,0,r.stderr);return r.stdout.decode().strip()
    def transports(self,r=None):
        r=r or fake_release()[0]
        bare=self.root/'remote.git';a=self.root/'repo-a';b=self.root/'repo-b'
        self.git(self.root,'init','--bare',str(bare));self.git(self.root,'clone',str(bare),str(a))
        self.git(a,'checkout','-b','main');put(a,'unrelated.txt',b'initial')
        self.git(a,'add','unrelated.txt');self.git(a,'commit','-m','fixture');self.git(a,'push','origin','main')
        self.git(self.root,'clone',str(bare),str(b))
        wt=Transport(a,self.root/'net-worker',r['root'],'worker',r['expires_at'],str(bare),self.root,0)
        ct=Transport(b,self.root/'net-controller',r['root'],'controller',r['expires_at'],str(bare),self.root,0)
        return wt,ct,a
    def test_two_linked_turns_single_residency(self):
        w,c,m,s,store=self.pair()
        self.assertEqual((w.claims,c.claims,m.loads),(2,2,1));self.assertEqual(c.terminal['status'],'submitted')
        q1=store[('request',1)][0];q2=store[('request',2)][0];obs=store[('observation',1)][0]
        self.assertEqual(q2['messages'][:2],q1['messages'])
        self.assertEqual(q2['messages'][-1],obs['observation'])
        self.assertEqual(q2['previous_observation_sha256'],sha(encode(obs['observation'])))
    def test_two_linked_turns_local_git_unrelated_advance(self):
        r,pin=fake_release(55);wt,ct,a=self.transports(r)
        original=ct.publish;advanced=[]
        def publish(kind,value,seq=None):
            obj=original(kind,value,seq)
            if kind=='observation':
                base=self.git(a,'ls-remote',str(self.root/'remote.git'),'refs/heads/main').split()[0]
                self.git(a,'fetch','origin','main')
                tree=self.git(a,'rev-parse',base+'^{tree}')
                new=self.git(a,'commit-tree',tree,'-p',base,'-m','unrelated empty main advance')
                self.git(a,'push','origin',new+':refs/heads/main');advanced.append(new)
            return obj
        ct.publish=publish
        w=Worker(self.root/'worker',r,pin,wt);c=Controller(self.root/'controller',r,pin,ct)
        m=self.model();s=InertSandbox();errors=[]
        def run():
            try:w.run(m)
            except BaseException as e:errors.append(repr(e))
        th=threading.Thread(target=run);th.start();c.run(s);th.join(58)
        self.assertFalse(th.is_alive());self.assertFalse(errors,errors)
        self.assertEqual((w.claims,c.claims,m.loads),(2,2,1));self.assertEqual(c.terminal['status'],'submitted')
        self.assertEqual(len(advanced),1);self.assertFalse(alive(m.life.record))
        self.observer=dict(worker=w.terminal,controller=c.terminal,unrelated_commits=advanced,owned_absent_before_teardown=True)
    def test_duplicate_inert_conflict_terminal_local_git(self):
        wt,ct,a=self.transports();one=ct.publish('preflight',{'fixed':1})
        self.assertEqual(ct.publish('preflight',{'fixed':1}),one)
        with self.assertRaisesRegex(Rejected,'conflict'):ct.publish('preflight',{'fixed':2})
        self.assertTrue(ct.failed)
    def test_crash_after_model_claim_no_regeneration(self):
        w,c,m,s,_=self.pair(crash=('worker','after_model_claim'))
        self.assertEqual((w.claims,c.claims),(1,0));self.assertFalse(list(m.root.glob('physical-*.json')))
        self.assertTrue((w.root/'claims/model-01.json').exists())
    def test_crash_after_action_claim_no_execution(self):
        w,c,m,s,_=self.pair(crash=('controller','after_action_claim'))
        self.assertEqual((w.claims,c.claims,len(s.commands)),(1,1,0))
        self.assertTrue((c.root/'claims/action-01.json').exists())
    def test_unclosed_thinking_no_action_no_second_request(self):
        w,c,m,s,store=self.pair(mode='invalid')
        self.assertEqual((w.claims,c.claims),(1,0));self.assertNotIn(('request',2),store)
    def test_command_failure_no_second_request(self):
        w,c,m,s,store=self.pair(fail=True)
        self.assertEqual((w.claims,c.claims),(1,1));self.assertNotIn(('request',2),store)
    def test_cap_single_residency_and_cleanup(self):
        w,c,m,s,_=self.pair(mode='cap',cap=True,seconds=50)
        self.assertEqual((w.claims,c.claims,m.loads),(24,24,1));self.assertEqual(c.terminal['status'],'action_cap')
    def test_context_overflow_and_native_substitution(self):
        good={'template_sha256':CONTRACT['template_sha256'],'native_exact':True,'rendered':'x','token_ids':[1]}
        with self.assertRaisesRegex(Rejected,'overflow'):binding(dict(good,token_ids=[1]*31233))
        with self.assertRaisesRegex(Rejected,'substitution'):binding(dict(good,template_sha256='a'*64))
    def test_context_overflow_no_model_claim_or_action(self):
        def configure(w,c,m,s):
            original=m.bind
            def overflow(messages,deadline):
                b=original(messages,deadline);b['token_ids']=[1]*31233;return b
            m.bind=overflow
        w,c,m,s,store=self.pair(configure=configure)
        self.assertEqual((w.claims,c.claims),(0,0));self.assertNotIn(('request',2),store)
    def test_model_failure_no_second_request(self):
        def configure(w,c,m,s):
            def fail(*args):raise RuntimeError('injected model failure, no retry')
            m.generate=fail
        w,c,m,s,store=self.pair(configure=configure)
        self.assertEqual((w.claims,c.claims),(1,0));self.assertNotIn(('request',2),store)
    def test_guard_failure_no_second_request(self):
        def configure(w,c,m,s):
            original=m.bind
            def trip(messages,deadline):
                b=original(messages,deadline)
                (m.root/'fake_sample.json').write_bytes(encode(dict(GOOD,free_percent=19)))
                self.wait(lambda:(m.root/'supervisor_exit.json').exists())
                m.check();return b
            m.bind=trip
        w,c,m,s,store=self.pair(configure=configure)
        self.assertEqual((w.claims,c.claims),(0,0));self.assertNotIn(('request',2),store)
    def test_preflight_unready_never_loads(self):
        r,p=fake_release(.3);m=self.model();w=Worker(self.root/'worker',r,p,Memory({}))
        w.run(m);self.assertEqual(m.loads,0)
    def test_native_render_substitution_rejected(self):
        from c5_contract import native_expected
        native=native_expected();bound_messages(native,initial())
        with self.assertRaisesRegex(Rejected,'render/message'):bound_messages(dict(native,rendered=native['rendered']+'x'),initial())
    def test_observation_exact_upstream_function_and_long_output(self):
        import ast
        from jinja2 import Template,StrictUndefined
        source=json.loads((HERE/'b4_parser_source.json').read_text())
        function=next(n for n in ast.parse(source['models/utils/actions_text.py']).body if isinstance(n,ast.FunctionDef) and n.name=='format_observation_messages')
        namespace={'Template':Template,'StrictUndefined':StrictUndefined,'time':time}
        import __future__
        exec(compile(ast.Module(body=[function],type_ignores=[]),'pinned_observation_source','exec',flags=__future__.annotations.compiler_flag),namespace)
        yaml=source['config/default.yaml'];block=yaml.split('  observation_template: |\n')[1].split('  model_kwargs:')[0]
        template=''.join(line[4:] for line in block.splitlines(True))
        for text in ('fixture','a'*10001):
            output=dict(output=text,returncode=0,exception_info=None)
            expected=namespace['format_observation_messages']([output],observation_template=template)[0]
            self.assertEqual(observation(output),{k:expected[k] for k in ('role','content')})
    def test_fetch_cap_no_extra_network(self):
        wt,ct,a=self.transports();wt.fetches=360
        with self.assertRaisesRegex(Rejected,'fetch cap'):wt.fetch()
    def test_invalid_and_length_responses_no_action(self):
        for mode in ('invalid','length'):
            with self.subTest(mode=mode):
                # Separate exclusive run roots, never reuse a claimed role.
                original_root=self.root;self.root=original_root/mode;self.root.mkdir()
                def configure(w,c,m,s):
                    original=m.generate
                    def changed(messages,deadline):
                        value=json.loads(original(messages,deadline))
                        if mode=='length':value['choices'][0]['finish_reason']='length'
                        else:value['choices'][0]['message']['content']='no accepted fence'
                        return json.dumps(value)
                    m.generate=changed
                try:
                    w,c,m,s,store=self.pair(configure=configure)
                    self.assertEqual((w.claims,c.claims),(1,0));self.assertNotIn(('request',2),store)
                finally:self.root=original_root
    def test_actual_process_death_after_model_claim(self):self.claim_death('model')
    def test_actual_process_death_after_action_claim(self):self.claim_death('action')
    def claim_death(self,kind):
        root=self.root/'dead-role'
        p=subprocess.run([sys.executable,str(HERE/'c6_test_driver.py'),'claim',str(root),kind],timeout=3)
        self.assertEqual(p.returncode,79)
        self.assertTrue((root/('claims/'+kind+'-01.json')).is_file())
        r,pin=fake_release()
        with self.assertRaises(FileExistsError):Worker(root,r,pin,Memory({}))
        self.assertFalse((root/'dispatch').exists())
    def test_exact_prefix_response_observation_and_source(self):
        r,pin=fake_release();c=Chain(r,pin);q=c.request(r['expires_at'])
        for key,val in [('sequence',2),('messages',q['messages']+[{'role':'user','content':'extra'}]),('controller_commit','d'*40),('previous_response_sha256','e'*64)]:
            with self.subTest(key=key):
                with self.assertRaises(Rejected):c.check_request(dict(q,**{key:val}),r['expires_at'])
        output=dict(output='fixture',returncode=0,exception_info=None)
        response={'fixed':'data'};obs=observation_envelope(r,pin,1,{'commit':'a'*40},response,output)
        check_observation(obs,r,pin,1,{'commit':'a'*40},response)
        bad=copy.deepcopy(obs);bad['observation']['content']+='corruption'
        with self.assertRaises(Rejected):check_observation(bad,r,pin,1,{'commit':'a'*40},response)
    def test_expired_response_no_action(self):
        r,pin=fake_release();c=Chain(r,pin);q=c.request(time.time()-1)
        with self.assertRaisesRegex(Rejected,'expired'):c.check_request(q,q['deadline'])
    def test_release_no_delegation_unqualified_sandbox_expiry(self):
        r,pin=fake_release();release(encode(r),pin)
        for modify in ('delegation','qualified','expired'):
            bad=copy.deepcopy(r)
            if modify=='delegation':bad['delegation']={}
            elif modify=='qualified':bad['sandbox']['qualified']=False
            else:bad['expires_at']=time.time()-1
            with self.assertRaises(Rejected):release(encode(bad),sha(encode(bad)))
    def test_missing_qualified_adapter_holds_production(self):
        from c6_sandbox import QualifiedSandbox
        with self.assertRaisesRegex(Rejected,'not installed'):QualifiedSandbox(self.root/'sandbox',fake_release()[0])
    def test_no_role_resume(self):
        r,p=fake_release();Worker(self.root/'worker',r,p,Memory({}))
        with self.assertRaises(FileExistsError):Worker(self.root/'worker',r,p,Memory({}))
    def test_fixed_production_role_root(self):
        from c6_launch import runtime_root
        r,p=fake_release()
        self.assertEqual(runtime_root(r,'worker'),ROOT/'results/remote_req028/c6_runtime/c6-fixture/worker')
        with self.assertRaises(Rejected):runtime_root(r,'other')
    def test_streamed_output_cap_actual_child(self):
        runner=Runner(self.root/'process')
        with self.assertRaisesRegex(Rejected,'output cap'):
            runner.run([sys.executable,'-c','import os;\nwhile True: os.write(1,b"x"*65536)'],time.time()+3,cap=65536)
        result=json.loads((runner.root/'1.result.json').read_text())
        self.assertLessEqual(result['bytes_retained'],65536);self.assertTrue(result['child_reaped'])
    def test_hanging_command_actual_cancel(self):self.hang('command')
    def test_hanging_git_actual_cancel(self):self.hang('git')
    def hang(self,kind):
        runner=Runner(self.root/'process');start=time.time()
        if kind=='git':
            # Actual git invokes an inert hanging SSH helper; no network connection.
            argv=['git','-c','core.sshCommand='+sys.executable+' '+str(HERE/'c6_test_driver.py')+' sleep','ls-remote','ssh://invalid.invalid/repo']
        else:argv=[sys.executable,str(HERE/'c6_test_driver.py'),'sleep']
        with self.assertRaisesRegex(Rejected,'deadline'):runner.run(argv,time.time()+.4)
        result=json.loads((runner.root/'1.result.json').read_text());self.assertTrue(result['child_reaped'])
        self.assertLess(time.time()-start,3)
    def test_hanging_http_actual_cancel(self):
        r,p=fake_release(12);m=self.model();m.start(r,p,self.root);put(m.root,'hang',b'')
        m.bind(initial(),time.time()+3)
        with self.assertRaises((Rejected,RuntimeError,TimeoutError)):m.generate(initial(),time.time()+.4)
        m.stop();self.assertFalse(alive(m.life.record))
    def test_idle_independent_guard_abort(self):
        r,p=fake_release(12);m=self.model();m.start(r,p,self.root)
        (m.root/'fake_sample.json').write_bytes(encode(dict(GOOD,free_percent=19)))
        self.wait(lambda:(m.root/'supervisor_exit.json').exists())
        receipt=json.loads((m.root/'supervisor_exit.json').read_text())
        self.assertTrue(receipt['cleanup']['owned_absent']);self.assertFalse(alive(m.life.record))
        self.observer=receipt
    def test_external_driver_death_model_cleanup(self):self.driver_death('model')
    def test_external_driver_death_process_cleanup(self):self.driver_death('process')
    def driver_death(self,mode):
        root=self.root/'external';root.mkdir()
        p=subprocess.Popen([sys.executable,str(HERE/'c6_test_driver.py'),mode,str(root)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.children.append(p);marker=root/('ready' if mode=='model' else 'process/1.result.json.owner')
        self.wait(marker.exists);os.kill(p.pid,signal.SIGKILL);p.wait(timeout=2)
        receipt=root/('model/supervisor_exit.json' if mode=='model' else 'process/1.result.json')
        self.wait(receipt.exists)
        value=json.loads(receipt.read_text())
        self.assertTrue(value['cleanup']['owned_absent'] if mode=='model' else value['child_reaped'])
        self.observer=value
    def test_timeout_single_residency_cleanup(self):
        r,p=fake_release(2);m=self.model();m.start(r,p,self.root)
        self.wait(lambda:(m.root/'supervisor_exit.json').exists(),5)
        self.assertEqual(m.loads,1);self.assertFalse(alive(m.life.record))

if __name__=='__main__':unittest.main(verbosity=2)
