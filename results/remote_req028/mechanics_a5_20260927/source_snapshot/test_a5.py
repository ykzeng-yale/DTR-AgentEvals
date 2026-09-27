"""A5 exact-copy/mismatch/deadline/cleanup structural regressions; no model."""
import ast,json,tempfile,unittest
from pathlib import Path
from a5_protocol import copy_prompts,bind_prompts,call_indices
from mechanics_a5 import build_command,ROOT
from mechanics_followup import build_command as original
class A5Tests(unittest.TestCase):
    def setUp(self):
        self.prior=ROOT/'results/remote_req028/mechanics_a4_20260927'
        self.frozen=json.loads((self.prior/'prompt_manifest.json').read_text())
        self.bodies,self.bindings=copy_prompts(self.prior,'new-alias')
    def test_exact_two_order_alias_only(self):
        self.assertEqual(call_indices(0),(0,1))
        with self.assertRaises(AssertionError):call_indices(1)
        for i,body in enumerate(self.bodies):
            expected=dict(self.frozen['requests'][i+4],model='new-alias')
            self.assertEqual(body,expected)
            self.assertEqual(self.bindings[i]['rendered_tokens'],(8192,24576)[i])
    def fake_http(self,mismatch=False):
        counter=[0]
        def http(path,body):
            index=counter[0]//2
            artifact=json.loads((self.prior/('prompt_'+str(index+5)+'.json')).read_text())
            counter[0]+=1
            if path=='/apply-template':return {'prompt':artifact['rendered']}
            self.assertEqual(path,'/tokenize')
            ids=artifact['token_ids']
            if mismatch:ids[0]+=1
            return {'tokens':ids}
        return http
    def test_exact_rebinding(self):
        with tempfile.TemporaryDirectory() as d:
            result=bind_prompts(self.bodies,self.bindings,self.fake_http(),Path(d))
        self.assertEqual([x['rendered_tokens'] for x in result],[8192,24576])
    def test_mismatch_before_generation(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(AssertionError,'token IDs mismatch'):
                bind_prompts(self.bodies,self.bindings,self.fake_http(True),Path(d))
        source=Path(__file__).with_name('mechanics_a5.py').read_text()
        self.assertLess(source.index('bindings=bind_prompts'),source.index("'/v1/chat/completions'"))
        self.assertLess(source.index("write('prompt_manifest.json'"),source.index("'/v1/chat/completions'"))
    def test_no_retry_no_restart_cleanup_deadline(self):
        source=Path(__file__).with_name('mechanics_a5.py').read_text()
        tree=ast.parse(source)
        calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and any(isinstance(a,ast.Constant) and a.value=='/v1/chat/completions' for a in n.args)]
        self.assertEqual(len(calls),1)
        for required in ('for cycle in range(1):','global_deadline=min(start+600',"timeout=min(180,global_deadline-time.time())","entry.update(status='FAILED',error=repr(e));raise",'finally:\n                guard.stop(record);child.wait(timeout=10);watchdog.wait(timeout=10)'):
            self.assertIn(required,source)
        self.assertNotIn('recover(',source)
        window=Path(__file__).with_name('admission_a5.py').read_text()
        self.assertIn('REQ028_PROGRAM_DEADLINE=str(time.time()+600)',window)
    def test_exact_cli(self):
        self.assertEqual(build_command('alias',123,'A5'),original('alias',123,'A2'))
if __name__=='__main__':unittest.main()
