"""Actual two-role engine, in-memory transport and inert model/sandbox only."""
import copy,json,tempfile,threading,time,unittest
from pathlib import Path
from recovery_contract import *
from recovery_engine import Worker,Controller
from comparator_fixtures import release
from comparator_tests import Wire
BAD='```mswea_bash_command\none\n```\n```mswea_bash_command\ntwo\n```'
GOOD='```mswea_bash_command\nfixture_only\n```'
class Model:
    def __init__(self,seq,r):self.seq=iter(seq);self.r=r;self.sent=[];self.stopped=False
    def start(self,*args):return time.time()
    def check(self):pass
    def bind(self,m,d):
        t=template(self.r['arm'])
        return dict(arm=self.r['arm'],template_sha256=ARMS[self.r['arm']]['template_sha'],template_relation=native_template(self.r['arm'],t,t),native_exact=True,rendered=rendered(m,self.r['arm']),token_ids=[1,2],messages_sha256=sha(encode(m)))
    def generate(self,m,d):
        self.sent.append(list(m));now=time.time();self.last_dispatch=dict(sent_at=now,started=now)
        return json.dumps(dict(choices=[dict(message=dict(content=next(self.seq)),finish_reason='stop')],usage=dict(prompt_tokens=2,completion_tokens=12,total_tokens=14)))
    def stop(self):self.stopped=True;return {'owned_absent':True}
class Sandbox:
    def __init__(self):self.actions=[];self.closed=False
    def preflight(self,*a):self.created_at=time.time()
    def bind_phase(self,*a):pass
    def check(self,*a):pass
    def execute(self,c,d):self.actions.append(c);return dict(output='inert',returncode=0,exception_info=None)
    def diff(self,*a):return ''
    def close(self):self.closed=True;return {'owned_absent':True}
class Tests(unittest.TestCase):
    def pair(self,seq,configure=None):
        r,_=release(seconds=30);r.update(transport_config_sha256='a'*64,protocol=PROTOCOL,run_id='cmp029o-fixture',root='results/remote_req029/comparator_runs/cmp029o-fixture',source_hashes=inventory());r['sandbox']['archive_ownership']='extracting-user';pin=sha(encode(r))
        with tempfile.TemporaryDirectory() as tmp:
            store={}
            factory=getattr(self,'wire_factory',lambda role:Wire(store,r['root']))
            w=Worker(Path(tmp)/'w',r,pin,factory('worker'));c=Controller(Path(tmp)/'c',r,pin,factory('controller'))
            m=Model(seq,r);s=Sandbox()
            if configure:configure(w,c,m,s,store)
            failures=[]
            def run_worker():
                try:w.run(m)
                except BaseException as e:failures.append(repr(e))
            t=threading.Thread(target=run_worker);t.start();c.run(s);t.join(12)
            self.assertEqual(failures,[])
            self.assertFalse(t.is_alive());self.assertTrue(m.stopped and s.closed)
            self.assertLessEqual(len(m.sent),w.claims);self.assertEqual(len(s.actions),c.claims)
            return w,c,m,s,store
    def test_three_errors_no_actions(self):
        w,c,m,s,store=self.pair([BAD]*3)
        self.assertEqual(len(m.sent),3);self.assertEqual(s.actions,[])
        self.assertEqual(c.terminal['status'],'repeated_format_error')
        self.assertEqual([x['role'] for x in m.sent[1]],['system','user','user'])
        self.assertNotIn(BAD,str(m.sent[1]))
    def test_clean_reset_and_physical_cap(self):
        seq=[BAD,BAD,GOOD]*8
        w,c,m,s,store=self.pair(seq)
        self.assertEqual(len(m.sent),24);self.assertEqual(len(s.actions),8)
        self.assertEqual(c.terminal['status'],'action_cap')
        self.assertEqual(c.chain.format_errors,0)
        self.assertEqual(w.chain.messages,c.chain.messages)
    def test_terminal_arrives_before_final_observation(self):
        def configure(w,c,m,s,store):
            original=w.wait
            def wait(kind,seq=None,peer=None):
                if kind=='observation' and seq==24:
                    until=time.monotonic()+3
                    while ('controller_terminal',None) not in store:
                        self.assertLess(time.monotonic(),until);time.sleep(.001)
                return original(kind,seq,peer)
            w.wait=wait
        w,c,m,s,store=self.pair([GOOD]*24,configure)
        self.assertEqual(len(m.sent),24);self.assertEqual(len(s.actions),24)
        self.assertEqual(w.chain.messages,c.chain.messages)
        self.assertEqual(w.terminal['status'],'call_cap')
    def test_feedback_mutations_no_second_dispatch(self):
        for field in ('content','sequence','response_sha256','response_object','release_sha256','feedback_semantics'):
            with self.subTest(field=field):
                def configure(w,c,m,s,store):
                    original=c.t.publish
                    def publish(kind,value,seq=None):
                        value=copy.deepcopy(value)
                        if kind=='observation':
                            if field=='content':value['observation']['content']='choose either command'
                            elif field=='sequence':value[field]+=1
                            elif field=='response_object':value[field]['sha256']='0'*64
                            else:value[field]='tampered'
                        return original(kind,value,seq)
                    c.t.publish=publish
                w,c,m,s,store=self.pair([BAD,GOOD],configure)
                self.assertEqual(len(m.sent),1);self.assertEqual(s.actions,[])
                self.assertIsNotNone(w.terminal['error'])
    def test_invalid_usage_and_finish_terminal(self):
        for field in ('total_tokens','prompt_tokens','finish_reason'):
            with self.subTest(field=field):
                def configure(w,c,m,s,store):
                    original=m.generate
                    def generate(messages,deadline):
                        v=json.loads(original(messages,deadline))
                        if field=='finish_reason':v['choices'][0][field]='length'
                        else:v['usage'][field]+=1
                        return json.dumps(v)
                    m.generate=generate
                w,c,m,s,store=self.pair([BAD],configure)
                self.assertEqual(len(m.sent),1);self.assertEqual(s.actions,[])
                self.assertNotIn(('response',1),store)
    def test_crash_after_claim_no_dispatch(self):
        def configure(w,c,m,s,store):
            def crash(stage):
                if stage=='after_model_claim':raise RuntimeError('fixture interruption after durable claim')
            w.crash=crash
        w,c,m,s,store=self.pair([GOOD],configure)
        self.assertEqual(w.claims,1);self.assertEqual(m.sent,[]);self.assertEqual(s.actions,[])
    def test_expiry_after_feedback_no_renewal(self):
        def configure(w,c,m,s,store):
            original=c.t.publish
            def publish(kind,value,seq=None):
                if kind=='observation':w.deadline=time.time()-1
                return original(kind,value,seq)
            c.t.publish=publish
        w,c,m,s,store=self.pair([BAD,GOOD],configure)
        self.assertEqual(len(m.sent),1);self.assertEqual(s.actions,[])
        self.assertIn('deadline',w.terminal['error'])
    def test_feedback_publication_conflict_no_retry(self):
        def configure(w,c,m,s,store):
            original=c.t.publish
            def publish(kind,value,seq=None):
                if kind=='observation':raise RuntimeError('fixture immutable conflict')
                return original(kind,value,seq)
            c.t.publish=publish
        w,c,m,s,store=self.pair([BAD,GOOD],configure)
        self.assertEqual(len(m.sent),1);self.assertEqual(s.actions,[])
        self.assertIn('immutable conflict',c.terminal['error'])
if __name__=='__main__':unittest.main()
