"""Actual two-role engine, in-memory transport and inert model/sandbox only."""
import json,tempfile,threading,time,unittest
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
    def pair(self,seq):
        r,_=release(seconds=30);r.update(protocol=PROTOCOL,run_id='cmp029o-fixture',root='results/remote_req029/comparator_runs/cmp029o-fixture',source_hashes=inventory());pin=sha(encode(r))
        with tempfile.TemporaryDirectory() as tmp:
            store={};w=Worker(Path(tmp)/'w',r,pin,Wire(store,r['root']));c=Controller(Path(tmp)/'c',r,pin,Wire(store,r['root']))
            m=Model(seq,r);s=Sandbox();t=threading.Thread(target=w.run,args=(m,));t.start();c.run(s);t.join(12)
            self.assertFalse(t.is_alive());self.assertTrue(m.stopped and s.closed)
            self.assertEqual(len(m.sent),w.claims);self.assertEqual(len(s.actions),c.claims)
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
if __name__=='__main__':unittest.main()
