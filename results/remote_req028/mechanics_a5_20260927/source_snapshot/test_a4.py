"""A4 setup and recovery contract tests without model loading."""
import ast,json,tempfile,unittest
from pathlib import Path
from a4_protocol import SYSTEM,SHORT,LITERAL,SUFFIX,call_indices,freeze_prompts,recover
from mechanics_a4 import build_command
from mechanics_followup import build_command as original
class A4Tests(unittest.TestCase):
    def test_six_calls_common_template_and_windows(self):
        requests=[]
        def http(path,body):
            requests.append((path,body))
            if path=='/apply-template':
                self.assertEqual(body['messages'][0],{'role':'system','content':SYSTEM})
                self.assertEqual(len(body['messages']),2)
                return {'prompt':'SYSTEM:'+body['messages'][0]['content']+' USER:'+body['messages'][1]['content']+' ASSISTANT:'}
            self.assertEqual(path,'/tokenize');self.assertTrue(body['add_special']);self.assertTrue(body['parse_special'])
            return {'tokens':list(range(40+4*body['content'].count(LITERAL)))}
        with tempfile.TemporaryDirectory() as d:
            calls,bindings=freeze_prompts('fake',http,Path(d))
        self.assertEqual(len(calls),6)
        self.assertEqual([b['messages'][1]['content'] for b in calls[:4]],SHORT*2)
        self.assertEqual(call_indices(0)+call_indices(1),tuple(range(6)))
        for i,target in ((4,8192),(5,24576)):
            b=bindings[i];self.assertGreaterEqual(b['rendered_tokens'],target);self.assertLessEqual(b['rendered_tokens'],target+64)
            self.assertLessEqual(b['rendered_tokens']+128,32768)
            self.assertLess(b['search']['predecessor_tokens'],target)
            self.assertEqual(calls[i]['messages'][1]['content'],LITERAL*b['search']['repetitions']+SUFFIX)
        self.assertTrue(all(path!='/v1/chat/completions' for path,_ in requests))
    def recovery(self,values,deadline=180):
        clock=[0];it=iter(values);observations=[]
        def sample():
            return {'pressure_level':1,'free_percent':next(it,73),'foreign_inference':[],'disk_free_bytes':20*1024**3,'swap_used_mib':233.31,'owned_rss_bytes':0}
        recover(sample,lambda:clock[0],lambda x:clock.__setitem__(0,clock[0]+x),lambda *x:observations.append(x),deadline,233.31)
        return clock[0],observations
    def test_recovery_two_readings_and_final(self):
        elapsed,observations=self.recovery([75,75,75])
        self.assertEqual(elapsed,15);self.assertEqual(len(observations),3)
    def test_recovery_resets(self):
        elapsed,_=self.recovery([75,73,75,75,75])
        self.assertEqual(elapsed,45)
    def test_recovery_expiry(self):
        with self.assertRaisesRegex(TimeoutError,'restart recovery deadline'):self.recovery([73]*20)
    def test_final_recheck_failure(self):
        elapsed,_=self.recovery([75,75,73,75,75,75])
        self.assertEqual(elapsed,45)
    def test_exact_cli_no_fallback(self):
        self.assertEqual(build_command('token',123,'A4'),original('token',123,'A2'))
    def test_one_generation_site_no_retries(self):
        source=Path(__file__).with_name('mechanics_a4.py').read_text()
        tree=ast.parse(source)
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and any(isinstance(a,ast.Constant) and a.value=='/v1/chat/completions' for a in n.args)]
        self.assertEqual(len(calls),1)
        self.assertIn('for index in call_indices(cycle)',source)
        self.assertIn("entry.update(status='FAILED',error=repr(e));raise",source)
if __name__=='__main__':unittest.main()
