"""REQ-029A deterministic full-chain tests. Scripted DATA, no model/server/Docker/shell."""
import copy,json,os,shutil,tempfile,threading,time,unittest
from pathlib import Path
from types import SimpleNamespace
from feedback import *
from engine import Worker,Controller
from c6_protocol import put,initial,rendered,CONTRACT
from c6_engine import Controller as ArchivedController,Worker as ArchivedWorker
from c6_protocol import check_observation as archived_check,observation_envelope as archived_envelope
from c6_sandbox_guardian import Guardian as ArchivedGuardian
from c6_sandbox_host import exchange
from c6_tests import fake_release
from c5_contract import native_expected
from c3r_arbiter import identity
from c2_relay import Rejected

class Wire:
    def __init__(self,store,root='results/remote_req029/runs/req029a-inert'):
        self.store=store;self.root=root;self.failed=False;self.fetches=0;self.events=[];self.deadline=0
        self.runner=SimpleNamespace(check=lambda:None,events=[])
    def read(self,kind,seq=None):
        if '_transport_error' in self.store:
            self.failed=True;raise RuntimeError('inert relay transport failure')
        self.runner.check();self.fetches+=1;time.sleep(.001);return self.store.get((kind,seq))
    def publish(self,kind,value,seq=None):
        raw=encode(value);key=kind,seq;obj=dict(commit='a'*40,blob='b'*40,path=self.root+'/'+kind+('' if seq is None else '/%02d'%seq)+'.json',sha256=sha(raw))
        require(key not in self.store,'no publication overwrite');self.store[key]=(copy.deepcopy(value),obj)
        return obj

class Replies:
    """Pure scripted reply fixture. No serving, model load, tokenizer or inference."""
    def __init__(self,commands):self.commands=commands;self.histories=[];self.stopped=False;self.bound=None
    def start(self,*args):return time.time()
    def check(self):pass
    def bind(self,messages,deadline):
        self.bound=native_expected() if messages==initial() else dict(native_exact=True,
            rendered=rendered(messages),template_sha256=CONTRACT['template_sha256'],token_ids=[7]*20)
        return self.bound
    def generate(self,messages,deadline):
        self.histories.append(copy.deepcopy(messages));command=self.commands[len(self.histories)-1]
        return json.dumps(dict(choices=[dict(finish_reason='stop',message=dict(content='THOUGHT: fixed inert fixture\n```mswea_bash_command\n'+command+'\n```'))],
            usage=dict(prompt_tokens=len(self.bound['token_ids']),completion_tokens=20)))
    def stop(self):self.stopped=True;return dict(owned_absent=True,inert=True)

class Backend:
    """In-memory Docker-shaped backend. Command strings are NEVER evaluated."""
    def __init__(self):
        self.runner=SimpleNamespace(check=lambda:None);self.cleaning=False;self.cfg=None;self.calls=[];self.removed=False
    def verify(self,deadline):self.runner.check()
    def inspect(self,target,deadline):return self.cfg
    def create(self,name,label,deadline,lifetime):
        self.cfg=dict(Id='f'*64,name=name,label=label,State={'Running':True});return 'f'*64
    def owned(self,cfg,name,label,cid=None):
        require(cfg and cfg['name']==name and cfg['label']==label,'foreign ownership')
        require(cid is None or cid==cfg['Id'],'foreign CID');return cfg['Id']
    def limits(self,cfg):pass
    def call(self,args,deadline):self.runner.check();return {'returncode':0,'output':''}
    def populate(self,cid,deadline):self.runner.check()
    def helper(self,cid,op,payload,deadline):
        self.runner.check()
        if op=='preflight':return dict(returncode=0,output=json.dumps(dict(writable=True,limits_verified=True)))
        if op=='diff':return dict(returncode=0,output='inert diagnostic diff')
        cmd=payload['command'];self.calls.append(cmd)
        if cmd in ('timeout','overflow','exception','broken-supervision','resource-failure'):
            raise RuntimeError('inert '+cmd)
        if cmd=='ownership-failure':
            self.cfg['label']='foreign';raise RuntimeError('inert ownership-failure')
        if cmd=='nonzero-submit':return dict(returncode=1,output='COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\nnot a submission')
        if cmd=='submit':return dict(returncode=0,output='COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT\ninert submission')
        if cmd=='oversize-return':return dict(returncode=0,output='x'*(1024**2+1))
        return dict(returncode=1 if cmd=='exit1' else 0,output='ordinary command feedback; no test or success inference')
    def remove(self,cid,deadline):self.cfg=None;self.removed=True

class Sandbox:
    def __init__(self,root,r,pin,guardian_class=Guardian):
        self.root=root;self.r=r;self.pin=pin;self.count=0;self.created_at=time.time();self.b=Backend();self.g=None;self.thread=None
        self.driver_identity=identity(os.getpid());self.closed=False
        self.guardian_class=guardian_class
    def op(self,operation,payload,deadline):
        self.count+=1;root=self.root/'state';spec=None
        if operation=='preflight':
            spec=dict(root=str(root),release=self.r,release_sha256=self.pin,driver_pid=os.getpid(),driver_identity=self.driver_identity,
                created_at=self.created_at,preflight_deadline=min(self.r['expires_at'],self.created_at+1200),name='req029a-inert',label='inert-owned')
        q=dict(operation=operation,payload=payload,deadline=deadline,sequence=self.count,run_id=self.r['run_id'],
            driver_pid=os.getpid(),driver_identity=self.driver_identity,release_sha256=self.pin)
        def launch(path):
            self.g=self.guardian_class(json.loads(path.read_bytes()),self.b);self.thread=threading.Thread(target=self.g.run);self.thread.start()
        return exchange(root,q,spec,launch)
    def preflight(self,r,deadline):return self.op('preflight',{},deadline)
    def bind_phase(self,r,obj,deadline):return self.op('bind_phase',dict(ready=r,object=obj),deadline)
    def check(self,deadline):return self.op('check',{},deadline)
    def liveness(self):require(self.thread and self.thread.is_alive(),'guardian broken supervision')
    def execute(self,command,deadline):return self.op('execute',{'command':command},deadline)
    def submitted(self,output,deadline):return submitted(output)
    def diff(self,deadline):return self.op('diff',{},deadline)['diff']
    def close(self):
        self.closed=True
        try:return self.op('close',{},time.time()+5)
        finally:
            if self.thread:self.thread.join(6)

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='req029a-');self.root=Path(self.tmp.name);self.sandboxes=[];self.evidence={}
    def tearDown(self):
        for s in self.sandboxes:
            if s.thread and s.thread.is_alive():s.g.stop=True;s.thread.join(6)
        put(self.root,'evidence.json',self.evidence)
        if os.environ.get('REQ029_FIXTURE_OUT'):shutil.copytree(self.root,Path(os.environ['REQ029_FIXTURE_OUT'])/self._testMethodName)
        self.tmp.cleanup()
    def pair(self,commands,crash=False,tamper=None,archived=False,transport_failure=False):
        r,pin=fake_release(45);r.update(protocol=29,run_id='req029a-inert',root='results/remote_req029/runs/req029a-inert');pin=sha(encode(r))
        if archived:r['protocol']=6;pin=sha(encode(r))
        store={};wt=Wire(store,r['root']);ct=Wire(store,r['root'])
        w=(ArchivedWorker if archived else Worker)(self.root/'worker',r,pin,wt)
        c=(ArchivedController if archived else Controller)(self.root/'controller',r,pin,ct)
        m=Replies(commands);s=Sandbox(self.root/'sandbox',r,pin,ArchivedGuardian if archived else Guardian);self.sandboxes.append(s)
        if transport_failure:
            original=ct.publish
            def publish(kind,value,seq=None):
                if kind=='observation':
                    store['_transport_error']=True;ct.failed=True;raise RuntimeError('inert relay transport failure')
                return original(kind,value,seq)
            ct.publish=publish
        if crash:
            def stop(stage):
                if stage=='after_action_claim':raise RuntimeError('inert crash after durable action claim')
            c.crash=stop
        if tamper:
            original=wt.read
            def read(kind,seq=None):
                v=original(kind,seq)
                if kind=='observation' and v:
                    a,b=copy.deepcopy(v);tamper(a,b);return a,b
                return v
            wt.read=read
        errors=[]
        def work():
            try:w.run(m)
            except BaseException as e:errors.append(repr(e))
        thread=threading.Thread(target=work);thread.start();c.run(s);thread.join(5)
        self.assertFalse(thread.is_alive());self.assertFalse(errors);self.assertTrue(s.closed);self.assertTrue(m.stopped)
        self.evidence.update(worker=w.terminal,controller=c.terminal,histories=m.histories,dispatched_actions=s.b.calls,guardian=s.g.failure)
        return r,pin,w,c,m,s,store
    def test_exit1_reaches_next_full_history_and_worker(self):
        r,p,w,c,m,s,store=self.pair(['exit1','submit'])
        self.assertEqual(c.terminal['status'],'submitted');self.assertEqual((w.claims,c.claims),(2,2))
        obs=store['observation',1][0];self.assertEqual(obs['output']['returncode'],1)
        self.assertEqual(m.histories[1],m.histories[0]+[{'role':'assistant','content':json.loads(store['response',1][0]['raw'])['choices'][0]['message']['content']},obs['observation']])
        self.assertIn('<returncode>1</returncode>',m.histories[1][-1]['content']);self.assertTrue(s.b.removed)
    def test_zero_exit_history_unchanged_template(self):
        r,p,w,c,m,s,store=self.pair(['exit0','submit']);obs=store['observation',1][0]
        self.assertEqual(obs['observation'],observation(obs['output']));self.assertEqual(c.terminal['status'],'submitted')
    def test_nonzero_cannot_submit(self):
        r,p,w,c,m,s,store=self.pair(['nonzero-submit','submit']);self.assertEqual(len(m.histories),2)
        self.assertEqual(store['observation',1][0]['output']['returncode'],1);self.assertEqual(c.claims,2)
    def test_timeout_overflow_exception_terminal_cleanup(self):
        for command in ('timeout','overflow','exception','broken-supervision','resource-failure'):
            with self.subTest(command=command):
                saved=self.root;self.root=saved/command;self.root.mkdir()
                r,p,w,c,m,s,store=self.pair([command]);self.assertEqual(c.terminal['status'],'terminal_or_failure')
                self.assertNotIn(('observation',1),store);self.assertEqual(len(m.histories),1);self.assertTrue(s.b.removed)
                self.root=saved
    def test_ownership_failure_terminal_no_foreign_removal(self):
        r,p,w,c,m,s,store=self.pair(['ownership-failure']);self.assertEqual(c.terminal['status'],'terminal_or_failure')
        self.assertFalse(c.terminal['cleanup']['owned_absent']);self.assertFalse(s.b.removed);self.assertNotIn(('observation',1),store)
    def test_tampered_returncode_rejected(self):
        def tamper(a,b):a['output']['returncode']=0
        r,p,w,c,m,s,store=self.pair(['exit1'],tamper=tamper)
        self.assertIn('observation object hash',w.terminal['error']);self.assertEqual(len(m.histories),1)
    def test_tampered_output_rejected_even_if_object_hash_recomputed(self):
        def tamper(a,b):a['output']['output']='substituted';b['sha256']=sha(encode(a))
        r,p,w,c,m,s,store=self.pair(['exit1'],tamper=tamper)
        self.assertIn('observation binding',w.terminal['error']);self.assertEqual(len(m.histories),1)
    def test_durable_claim_no_redispatch_or_resume(self):
        r,p,w,c,m,s,store=self.pair(['exit1'],crash=True)
        self.assertTrue((c.root/'claims/action-01.json').exists());self.assertEqual(s.b.calls,[]);self.assertEqual(c.claims,1)
        with self.assertRaises(FileExistsError):Controller(c.root,r,p,Wire({}))
    def test_archived_c6_rejects_same_exit1(self):
        r,p=fake_release();output=dict(returncode=1,output='ordinary command feedback',exception_info=None)
        obs=archived_envelope(r,p,1,{}, {},output)
        with self.assertRaisesRegex(Rejected,'command failure'):archived_check(obs,r,p,1,{}, {})
        self.evidence['archived_rejection']='command failure';self.evidence['output']=output
    def test_archived_c6_full_chain_stops_before_feedback(self):
        r,p,w,c,m,s,store=self.pair(['exit1'],archived=True)
        self.assertEqual(c.terminal['status'],'terminal_or_failure');self.assertEqual(c.claims,1)
        self.assertNotIn(('observation',1),store);self.assertEqual(len(m.histories),1)
        self.assertIn('command failure',s.g.failure);self.assertTrue(s.b.removed)
    def test_transport_failure_terminal_cleanup_no_redispatch(self):
        r,p,w,c,m,s,store=self.pair(['exit1'],transport_failure=True)
        self.assertIn('relay transport failure',c.terminal['error']);self.assertIn('relay transport failure',w.terminal['error'])
        self.assertEqual(s.b.calls,['exit1']);self.assertTrue(s.b.removed);self.assertEqual(len(m.histories),1)
    def test_long_feedback_retains_exact_raw_and_pinned_elision(self):
        r,p=fake_release();output=dict(returncode=1,output='start'+('x'*30000)+'end',exception_info=None)
        v=observation_envelope(r,p,1,{}, {},output)
        self.assertEqual(v['output'],output);self.assertEqual(v['output_sha256'],sha(encode(output)))
        self.assertEqual(v['observation'],observation(output));self.assertLess(len(v['observation']['content']),len(output['output']))
        self.assertEqual(check_observation(v,r,p,1,{}, {},{'sha256':sha(encode(v))}),v['observation'])
    def test_expired_deadline_and_bad_output_terminal(self):
        for output in (dict(output='x',returncode=-9,exception_info=None),dict(output='x',returncode=True,exception_info=None),dict(output='x',returncode=1,exception_info='timeout'),dict(output='x'*(1024**2+1),returncode=0,exception_info=None)):
            with self.assertRaises(Rejected):completed(output)
        r,p=fake_release();r.update(protocol=29,run_id='req029a-expired',expires_at=time.time()-1)
        c=Controller(self.root/'expired',r,p,Wire({}))
        with self.assertRaisesRegex(Rejected,'phase deadline'):c.left(1)
    def test_parent_sequence_and_hash_tamper_rejected(self):
        r,p=fake_release();response={'raw':'fixed'};obj={'sha256':'c'*64}
        v=observation_envelope(r,p,1,obj,response,dict(output='x',returncode=1,exception_info=None))
        for key,value in [('sequence',2),('response_sha256','0'*64),('output_sha256','0'*64),('release_sha256','0'*64)]:
            bad=copy.deepcopy(v);bad[key]=value
            with self.assertRaises(Rejected):check_observation(bad,r,p,1,obj,response,{'sha256':sha(encode(bad))})

if __name__=='__main__':unittest.main()
