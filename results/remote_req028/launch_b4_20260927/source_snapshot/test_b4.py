import copy,json,tempfile,unittest
from pathlib import Path
import b4_protocol as p
from mechanics_b3 import build_command as old
from mechanics_b4 import build_command,ROOT
class B4Tests(unittest.TestCase):
    def test_command_unchanged(self):
        self.assertEqual(build_command('alias',1,'B4'),old('alias',1,'B3'))
    def test_request_only_two_fields(self):
        prior=json.loads((ROOT/'results/remote_req028/mechanics_b3_20260927/call_2.request.json').read_text())
        bodies=p.copy_requests(ROOT/'results/remote_req028','new')
        self.assertEqual(bodies,[dict(prior,model='new',max_tokens=1536)])
    def test_one_no_retry(self):
        seen=[];p.execute_calls(seen.append);self.assertEqual(seen,[0])
        def fail(i):seen.append(i);raise RuntimeError()
        with self.assertRaises(RuntimeError):p.execute_calls(fail)
        self.assertEqual(seen,[0,0])
    def test_source_and_retrospective(self):
        p.parser_binding()
        result=p.retrospective(ROOT/'results/remote_req028')
        self.assertEqual([x['complete_fence_count'] for x in result['calls']],[0,0,0])
        self.assertFalse(any(x['parser_accepted'] for x in result['calls']))
    def test_formats_and_boundaries(self):
        fence='```mswea_bash_command\nprintf DTR_READY\n```'
        for text,count,strict,where in [('',0,False,None),(fence,1,True,'outside'),('extra\n'+fence,1,False,'outside'),('<think>'+fence+'</think>',1,False,'inside'),('<think>'+fence,1,False,'inside'),('<think>x</think>'+fence,1,False,'outside'),(fence+fence,2,False,'outside'),('```mswea_bash_command\nprintf DTR_READY',0,False,None)]:
            r=p.analyze(text)
            self.assertEqual(r['complete_fence_count'],count)
            self.assertEqual(r['parser_accepted'],count==1)
            self.assertEqual(r['format_compliant'],strict)
            if where:self.assertEqual(r['fences'][0]['location'],where)
        self.assertFalse(p.analyze(fence.replace('printf','echo'))['parser_expected_command'])
    def test_binding_exact(self):
        prior=json.loads((ROOT/'results/remote_req028/mechanics_b3_20260927/prompt_2.json').read_text())
        bodies=p.copy_requests(ROOT/'results/remote_req028','new')
        def http(path,body):return {'prompt':prior['rendered']} if path=='/apply-template' else {'tokens':prior['token_ids']}
        # Use temporary directory alongside archived B3, never change prior artifacts.
        with tempfile.TemporaryDirectory(dir=ROOT/'results/remote_req028') as d:
            result=p.bind_prompts(bodies,http,Path(d));self.assertEqual(result[0]['rendered_tokens'],49)
        with tempfile.TemporaryDirectory(dir=ROOT/'results/remote_req028') as d:
            with self.assertRaises(AssertionError):p.bind_prompts(bodies,lambda path,body:{'prompt':'changed'} if path=='/apply-template' else {'tokens':prior['token_ids']},Path(d))
if __name__=='__main__':unittest.main()
