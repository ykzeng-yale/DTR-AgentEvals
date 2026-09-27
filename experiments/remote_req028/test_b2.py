import json,tempfile,unittest
from pathlib import Path
from b2_protocol import copy_requests,bind_prompts,native_template,execute_calls
from a6_control import owned_scope
from mechanics_b2 import ROOT,MODEL,build_command
from mechanics_a6r import build_command as previous
class B2Tests(unittest.TestCase):
    def test_exact_original_order(self):
        r=ROOT/'results/remote_req028';b=copy_requests(r,'alias')
        old=json.loads((r/'mechanics_a4_20260927/prompt_manifest.json').read_text())['requests'][:2]+[json.loads((r/'mechanics_a5_20260927/prompt_manifest.json').read_text())['requests'][0]]
        self.assertEqual(b,[dict(x,model='alias') for x in old])
    def fake(self,long_count=8192):
        n=[0]
        def http(path,body):
            if path=='/apply-template':return {'prompt':'native '+body['messages'][1]['content']}
            index=n[0];n[0]+=1
            return {'tokens':list(range((33,49,long_count)[index]))}
        return http
    def test_all_bindings_before_generation(self):
        bodies=copy_requests(ROOT/'results/remote_req028','alias');calls=[]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);bindings=bind_prompts(bodies,self.fake(),p)
            def dispatch(i):
                self.assertEqual(len(bindings),3);self.assertEqual(len(list(p.glob('prompt_*.json'))),3);calls.append(i)
            execute_calls(dispatch)
        self.assertEqual(calls,[0,1,2])
    def test_native_template_and_count_mismatch_prevent_calls(self):
        bodies=copy_requests(ROOT/'results/remote_req028','alias')
        for failure in ('template','count'):
            calls=[];cleanups=[]
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(AssertionError):
                    with owned_scope(lambda:cleanups.append(True)):
                        native_template('wrong' if failure=='template' else 'native','native')
                        bind_prompts(bodies,self.fake(8257),Path(d))
                        execute_calls(lambda i:calls.append(i))
            self.assertEqual(calls,[]);self.assertEqual(cleanups,[True])
    def test_first_infrastructure_failure_stops_and_cleans(self):
        calls=[];owned={'resident':True}
        def dispatch(i):calls.append(i);raise RuntimeError('fake abort')
        with self.assertRaises(RuntimeError):
            with owned_scope(lambda:owned.update(resident=False)):execute_calls(dispatch)
        self.assertEqual(calls,[0]);self.assertFalse(owned['resident'])
    def test_terminal_format_failure_continues_no_retry(self):
        calls=[];cleanup=[]
        def dispatch(i):calls.append(i);return {'terminal':True,'format_compliant':False}
        with owned_scope(lambda:cleanup.append(True)):execute_calls(dispatch)
        self.assertEqual(calls,[0,1,2]);self.assertEqual(cleanup,[True])
    def test_only_released_model_cli_change(self):
        expected=previous('alias',123,'A6R');expected[expected.index('-m')+1]=str(MODEL)
        self.assertEqual(build_command('alias',123,'B2'),expected)
        self.assertEqual(MODEL.name,'Klear-AgentForge-8B.Q4_K_M.gguf')
if __name__=='__main__':unittest.main()
