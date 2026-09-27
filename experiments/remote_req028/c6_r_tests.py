"""C6R unique regressions and concrete adapter integration using fake Docker only."""
import ast,copy,json,os,shutil,signal,subprocess,sys,tempfile,threading,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from c6_protocol import *
from c2_relay import Rejected
from c6_submission_checker import check,verify_source,DOCKER_SHA
from c6_process import Runner
from c6_model import Lifecycle
from c6_tests import fake_release,InertModel,Memory,GOOD
from c6_engine import Controller,Worker
from c6_r_fixtures import Sandbox,FakeDocker,descendant_alive
from c6_sandbox_guardian import Guardian
from c6_ipc import publish
from c3r_arbiter import identity

class Wire(Memory):
    def __init__(self,store,r):super().__init__(store);self.r=r
    def publish(self,kind,value,seq=None):
        obj=super().publish(kind,value,seq)
        obj['path']=self.r['root']+'/'+kind+('' if seq is None else '/%02d'%seq)+'.json'
        self.store[(kind,seq)]=(value,obj);return obj

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='c6r-inert-');self.root=Path(self.tmp.name)
        self.sandboxes=[];self.models=[];self.children=[];self.observer={}
    def tearDown(self):
        for s in self.sandboxes:
            try:
                s.close()
            except BaseException as e:self.observer.setdefault('teardown_errors',[]).append(repr(e))
            finally:
                if s.guardian:s.guardian.wait(timeout=3)
        for m in self.models:
            try:m.stop()
            except BaseException as e:self.observer.setdefault('teardown_errors',[]).append(repr(e))
        for p in self.children:
            if p.poll() is None:p.kill();p.wait(timeout=2)
        put(self.root,'observer.json',self.observer)
        if os.environ.get('C6_FIXTURE_OUT'):shutil.copytree(self.root,Path(os.environ['C6_FIXTURE_OUT'])/self._testMethodName)
        self.tmp.cleanup()
    def wait(self,fn,seconds=8):
        end=time.time()+seconds
        while not fn():
            self.assertLess(time.time(),end);time.sleep(.01)
    def sandbox(self,seconds=50):
        r,p=fake_release(seconds);s=Sandbox(self.root/'sandbox',r);self.sandboxes.append(s)
        s.preflight(r,time.time()+8);return s
    def assert_removed(self,s):
        self.wait(lambda:(s.root/'state/terminal.json').exists())
        self.assertFalse((s.fake_root/'container.json').exists())
        self.assertTrue(json.loads((s.root/'state/terminal.json').read_text())['cleanup']['owned_absent'])
    def pair(self,command=None,guard=False):
        r,p=fake_release(55);s=Sandbox(self.root/'sandbox',r);self.sandboxes.append(s)
        p=sha(encode(r));store={};w=Worker(self.root/'worker',r,p,Wire(store,r));c=Controller(self.root/'controller',r,p,Wire(store,r))
        m=InertModel(self.root/'model');self.models.append(m)
        if command:
            original=m.generate
            def generated(messages,deadline):
                d=json.loads(original(messages,deadline));d['choices'][0]['message']['content']='```mswea_bash_command\n'+command+'\n```'
                return json.dumps(d)
            m.generate=generated
            original_execute=s.execute
            s.execute=lambda cmd,deadline:original_execute(cmd,min(deadline,time.time()+.5) if cmd=='hang' else deadline)
        barrier=self.root/'exit-barrier'
        original_launch=Lifecycle.launch
        def launch(life):
            if guard:put(self.root,barrier.name,b'hold');life.spec['exit_barrier']=str(barrier)
            original_launch(life)
        if guard:
            original_bind=m.bind
            def trip(messages,deadline):
                value=original_bind(messages,deadline)
                (m.root/'fake_sample.json').write_bytes(encode(dict(GOOD,free_percent=19)))
                self.wait(lambda:(m.root/'supervisor_exit.json').exists())
                self.assertIsNone(m.life.proc.poll(),'controlled teardown barrier must still hold supervisor')
                try:m.check()
                finally:barrier.unlink()
                return value
            m.bind=trip
        errors=[]
        def run():
            try:w.run(m)
            except BaseException as e:errors.append(repr(e))
        with patch.object(Lifecycle,'launch',launch):
            th=threading.Thread(target=run);th.start();c.run(s);th.join(58)
        self.assertFalse(th.is_alive());self.assertFalse(errors,errors)
        self.assert_removed(s)
        self.observer.update(worker=w.terminal,controller=c.terminal,claims=[w.claims,c.claims])
        return w,c,m,s,store
    def test_latched_terminal_receipt_before_process_exit(self):
        life=Lifecycle(self.root/'life',{'port':1,'phase_deadline':time.time()+20})
        life.proc=SimpleNamespace(poll=lambda:None)
        put(life.root,'supervisor_exit.json',{'failure':'guard trip','cleanup':{'owned_absent':True}})
        with self.assertRaisesRegex(RuntimeError,'latched'):life.check()
        (life.root/'supervisor_exit.json').unlink()
        with self.assertRaisesRegex(RuntimeError,'latched'):life.check()
    def test_guard_barrier_zero_claim_zero_generation_no_second_request(self):
        w,c,m,s,store=self.pair(guard=True)
        self.assertEqual((w.claims,c.claims),(0,0));self.assertFalse(list(m.root.glob('physical-*.json')))
        self.assertNotIn(('request',2),store)
    def test_stop_request_and_guard_record_block_http(self):
        from c4_http import HTTP
        for marker,data in [('stop.request',{}),('telemetry_latest.json',{'violation':'free<20'})]:
            root=self.root/marker;life=Lifecycle(root,{'port':1,'phase_deadline':time.time()+20});life.proc=SimpleNamespace(poll=lambda:None)
            put(root,marker,data)
            with self.assertRaisesRegex(RuntimeError,'latched'):HTTP(root/'http',life).begin_bind(initial(),1)
            self.assertFalse(list((root/'http').glob('*.input.json')))
    def test_parent_exits_first_descendant_absent_before_teardown(self):
        pidfile=self.root/'descendant.json';runner=Runner(self.root/'runner')
        result=runner.run([sys.executable,str(HERE/'c6_r_driver.py'),'orphan',str(pidfile)],time.time()+3)
        pid=json.loads(pidfile.read_text())['pid']
        self.assertFalse(descendant_alive(pid));self.assertTrue(result['owned_group_absent'])
        self.observer={'descendant_pid':pid,'descendant_absent_before_teardown':True,'result':result}
    def test_driver_death_parent_exit_descendant_cleanup(self):
        root=self.root/'external';root.mkdir()
        p=subprocess.Popen([sys.executable,str(HERE/'c6_r_driver.py'),'runner',str(root)])
        self.children.append(p);self.wait(lambda:(root/'descendant.json').exists())
        self.assertIsNone(p.poll());p.kill()
        p.wait(timeout=3);self.wait(lambda:(root/'process/1.result.json').exists())
        pid=json.loads((root/'descendant.json').read_text())['pid']
        self.assertFalse(descendant_alive(pid))
        self.observer={'descendant_absent_before_teardown':True,'pid':pid}
    def test_exact_submission_extracted_upstream_equivalence(self):
        source=ast.parse(verify_source());cls=next(n for n in source.body if isinstance(n,ast.ClassDef) and n.name=='DockerEnvironment')
        fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_check_finished')
        class Submitted(Exception):pass
        space={'Submitted':Submitted};exec(compile(ast.Module(body=[fn],type_ignores=[]),'pinned_function','exec'),space)
        values=[('',0),('COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\npayload\n',0),
            (' \n\t COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT \npayload',0),
            ('x COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT',0),('prefix\nCOMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT',0),
            ('COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT',1)]
        for text,code in values:
            output={'output':text,'returncode':code,'exception_info':None};expected=None
            try:space['_check_finished'](None,output)
            except Submitted as e:expected=e.args[0]
            result=check(output);self.assertEqual(result['upstream_exit_message'],expected)
            self.assertEqual(result['submitted'],expected is not None)
    def test_adapter_operation_exit_preserves_residency_until_close(self):
        s=self.sandbox();self.assertIsNone(s.guardian.poll());self.assertTrue((s.fake_root/'container.json').exists())
        s.bind_fixture();out=s.execute('fixture-action',time.time()+3);self.assertEqual(out['output'],'fixed observation\n')
        self.assertIsNone(s.guardian.poll());s.close();self.assert_removed(s)
    def test_phase_single_adoption_no_renewal(self):
        s=self.sandbox();ready,obj=s.bind_fixture();s.bind_phase(ready,obj,time.time()+3)
        bad=copy.deepcopy(ready);bad['deadline']+=1;other=dict(obj,sha256=sha(encode(bad)))
        with self.assertRaises(Rejected):s.bind_phase(bad,other,time.time()+3)
        self.assert_removed(s)
    def test_command_forbidden_before_phase(self):
        s=self.sandbox()
        with self.assertRaises(Rejected):s.execute('fixture-action',time.time()+3)
        self.assert_removed(s);self.assertFalse(list(s.fake_root.glob('action-*')))
    def test_actual_adapter_two_linked_turns_explicit_submission(self):
        w,c,m,s,store=self.pair()
        self.assertEqual((w.claims,c.claims),(2,2));self.assertEqual(c.terminal['status'],'submitted')
        self.assertEqual(store[('request',2)][0]['messages'][-1],store[('observation',1)][0]['observation'])
        self.assertTrue((s.root/'state/final.diff').exists())
        classification=json.loads((c.root/'diff.classification.json').read_text())
        self.assertTrue(classification['submitted']);self.assertFalse(classification['primary_eligible'])
    def test_timeout_removes_container_no_second_action(self):
        w,c,m,s,store=self.pair(command='hang')
        self.assertEqual(c.claims,1);self.assertNotIn(('request',2),store)
        self.assertEqual(len(list(s.fake_root.glob('action-*'))),1)
    def test_output_overflow_removes_container_no_second_action(self):
        w,c,m,s,store=self.pair(command='overflow')
        self.assertEqual(c.claims,1);self.assertNotIn(('request',2),store)
        results=list((s.root/'state/docker/process').glob('*.result.json'))
        self.assertTrue(any('output cap' in str(json.loads(p.read_text()).get('error')) for p in results))
    def test_controller_death_create_boundary(self):self.death('create')
    def test_controller_death_start_boundary(self):self.death('start')
    def test_controller_death_populate_boundary(self):self.death('populate')
    def test_controller_death_execute_boundary(self):self.death('execute')
    def death(self,stage):
        root=self.root/'external';root.mkdir()
        p=subprocess.Popen([sys.executable,str(HERE/'c6_r_driver.py'),'controller',str(root),stage],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.children.append(p);self.wait(lambda:(root/'fake'/('stage-'+stage)).exists())
        p.kill();p.wait(timeout=3)
        terminal=root/'sandbox/state/terminal.json';self.wait(terminal.exists,12)
        value=json.loads(terminal.read_text());self.assertTrue(value['cleanup']['owned_absent'],value)
        self.assertFalse((root/'fake/container.json').exists())
        self.observer={'terminal':value,'container_absent_before_teardown':True,'boundary':stage}
    def test_foreign_identity_not_removed(self):
        s=self.sandbox();s.bind_fixture();put(s.fake_root,'foreign',b'injected identity conflict')
        with self.assertRaises(Rejected):s.execute('fixture-action',time.time()+3)
        self.wait(lambda:(s.root/'state/terminal.json').exists())
        rec=json.loads((s.root/'state/terminal.json').read_text())
        self.assertFalse(rec['cleanup']['owned_absent']);self.assertFalse((s.fake_root/'removed').exists())
    def test_expired_operation_terminates_no_action(self):
        s=self.sandbox();s.bind_fixture()
        with self.assertRaises(Rejected):s.execute('fixture-action',time.time()-.1)
        self.assert_removed(s);self.assertFalse(list(s.fake_root.glob('action-*')))
    def test_journal_failure_after_create_cannot_skip_removal(self):
        r,p=fake_release(50);root=self.root/'state';root.mkdir();fake=self.root/'fake';fake.mkdir();put(fake,'archive',b'inert archive')
        spec=dict(root=str(root),release=r,release_sha256=p,driver_pid=os.getpid(),driver_identity=identity(os.getpid()),
            created_at=time.time(),preflight_deadline=r['expires_at'],name='dtr-c6-failure',label='failure-owner')
        g=Guardian(spec,FakeDocker(root/'docker',r['sandbox'],fake));original=g.save
        def fail(name,value):
            if name=='owned.json':raise OSError('injected journal failure')
            return original(name,value)
        g.save=fail
        q=dict(sequence=1,operation='preflight',payload={},deadline=time.time()+8,run_id=r['run_id'],driver_pid=os.getpid(),driver_identity=spec['driver_identity'],release_sha256=p)
        publish(root,'requests/0001.json',q);terminal=g.run()
        self.assertTrue(terminal['cleanup']['owned_absent']);self.assertFalse((fake/'container.json').exists())
    def test_deadline_reserve_ends_idle_sandbox(self):
        s=self.sandbox(seconds=18)
        self.wait(lambda:(s.root/'state/terminal.json').exists(),6)
        self.assert_removed(s)
    def test_fake_clock_phase_adoption_never_renews(self):
        now=time.time();r,p=fake_release(3600);root=self.root/'state';root.mkdir();fake=self.root/'fake';fake.mkdir()
        spec=dict(root=str(root),release=r,release_sha256=p,driver_pid=os.getpid(),driver_identity=identity(os.getpid()),
            created_at=now,preflight_deadline=now+1200,name='fixture',label='fixture')
        g=Guardian(spec,FakeDocker(root/'docker',r['sandbox'],fake));g.ready=True
        ready=dict(protocol=6,run_id=r['run_id'],release_sha256=p,worker_commit=r['worker_commit'],phase_started=now+600,deadline=now+2400)
        obj=dict(commit='a'*40,blob='b'*40,path=r['root']+'/ready.json',sha256=sha(encode(ready)))
        payload={'ready':ready,'object':obj}
        with patch('c6_sandbox_guardian.time.time',return_value=now+600):g.bind(payload)
        with patch('c6_sandbox_guardian.time.time',return_value=now+1800):
            g.bind(payload);self.assertEqual(g.deadline,now+2400)
            other=copy.deepcopy(payload);other['ready']['phase_started']+=600;other['ready']['deadline']+=600
            other['object']['sha256']=sha(encode(other['ready']))
            with self.assertRaisesRegex(Rejected,'renewal'):g.bind(other)
        with patch('c6_sandbox_guardian.time.time',return_value=now+2400):
            with self.assertRaisesRegex(Rejected,'expired'):g.check()
    def test_caller_identity_conflict_no_action(self):
        s=self.sandbox();s.bind_fixture();s.driver_identity='reused or foreign PID identity'
        with self.assertRaises(Rejected):s.execute('fixture-action',time.time()+3)
        self.assert_removed(s);self.assertFalse(list(s.fake_root.glob('action-*')))
    def test_stale_preflight_wire_receipt_never_loads(self):
        r,p=fake_release();store={};wire=Wire(store,r);w=Worker(self.root/'worker',r,p,wire)
        wire.publish('preflight',dict(protocol=6,run_id=r['run_id'],release_sha256=p,
            sandbox=r['sandbox'],controller_commit=r['controller_commit'],ready=True,
            created_at=time.time()-1300,preflight_deadline=time.time()-100))
        m=InertModel(self.root/'model');self.models.append(m);w.run(m)
        self.assertEqual(m.loads,0);self.assertEqual(w.claims,0)

if __name__=='__main__':unittest.main(verbosity=2)
