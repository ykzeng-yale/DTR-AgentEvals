import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import c0_protocol as p
import mechanics_c0 as m
from mechanics_b3 import build_command as klear_command
from mechanics_a6r import build_command as qwen_command
class C0Tests(unittest.TestCase):
    def test_frozen_identity_and_only_first_two(self):
        frozen=p.frozen_messages(m.ROOT);body=p.copy_requests(m.ROOT,'alias')[0]
        self.assertEqual(body['messages'],frozen['messages'])
        self.assertEqual([x['role'] for x in body['messages']],['system','user'])
        self.assertEqual(p.message_hash(body['messages']),p.MESSAGES_SHA)
        prior=json.loads((m.ROOT/'results/remote_req028/mechanics_b4_20260927/call_1.request.json').read_text())
        self.assertEqual(body,dict(prior,model='alias',messages=frozen['messages']))
    def test_source_and_message_tampering_rejected(self):
        raw=(m.ROOT/'docs/req028_c0_prompt_20260927.json').read_bytes()
        frozen=json.loads(raw);source=(m.ROOT/frozen['source']).read_bytes()
        with self.assertRaises(AssertionError):p.validate_frozen(raw+b' ',source)
        with self.assertRaises(AssertionError):p.validate_frozen(raw,source+b' ')
        frozen['messages'].append({'role':'assistant','content':'future information'})
        with self.assertRaises(AssertionError):p.validate_frozen(json.dumps(frozen).encode(),source)
        frozen=json.loads(raw);frozen['messages'][1]['content']+=' changed'
        with self.assertRaises(AssertionError):p.validate_frozen(json.dumps(frozen).encode(),source)
    def test_model_cache_pins_and_order(self):
        self.assertEqual(p.ORDER,('klear','qwen'))
        self.assertEqual(m.build_command('a',1,'klear'),klear_command('a',1,'B3'))
        self.assertEqual(m.build_command('a',1,'qwen'),qwen_command('a',1,'A6R'))
        self.assertEqual(p.ARMS['klear']['sha256'],'9c0909b89b518283ded8ca415694743bd922e8844356db4f26957e37047142ae')
        self.assertEqual(p.ARMS['qwen']['sha256'],'3605803b982cb64aead44f6c1b2ae36e3acdb41d8e46c8a94c6533bc4c67e597')
    def test_native_templates(self):
        for arm,prior in [('klear','mechanics_b4_20260927'),('qwen','mechanics_a6r_20260927')]:
            base=m.ROOT/'results/remote_req028'/prior
            raw=(base/'chat_template.jinja').read_text()
            served=json.loads((base/'server_0.props.json').read_text())['chat_template']
            p.native_template(arm,served,raw)
            with self.assertRaises(AssertionError):p.native_template(arm,served+' ',raw)
    def test_parser_boundaries_and_finish(self):
        fence='```mswea_bash_command\nls -la\n```'
        cases=[(fence,'stop',True,'outside_thinking'),('THOUGHT: inspect\n'+fence,'stop',True,'outside_thinking'),('<think>x</think>'+fence,'stop',True,'outside_thinking'),('<think>'+fence+'</think>','stop',False,'inside_closed_thinking'),('<think>'+fence,'stop',False,'after_unclosed_reasoning'),(fence,'length',False,'outside_thinking'),(fence+'<think>','stop',False,'outside_thinking'),('```mswea_bash_command\n<think>ls\n```</think>','stop',False,'overlap')]
        for text,finish,passed,location in cases:
            r=p.analyze(text,finish);self.assertEqual(r['interface_gate'],passed)
            self.assertEqual(r['fences'][0]['reasoning_boundary'],location)
            self.assertTrue(r['independent_regex_agrees'])
            self.assertNotIn('parser_expected_command',r)
        for text in ('',fence+fence,fence.replace('ls -la','')):
            self.assertFalse(p.analyze(text,'stop')['interface_gate'])
        self.assertTrue(p.analyze(fence.replace('ls -la','some invalid command'),'stop')['interface_gate'])
    def test_binding_count_and_headroom(self):
        body=p.copy_requests(m.ROOT,'a')
        def http(path,request):return {'prompt':'rendered'} if path=='/apply-template' else {'tokens':[1,2,3]}
        with tempfile.TemporaryDirectory() as d:
            result=p.bind_prompts(body,http,Path(d));self.assertEqual(result[0]['rendered_tokens'],3)
            self.assertEqual(result[0]['messages_sha256'],p.MESSAGES_SHA)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(AssertionError):p.bind_prompts(body,lambda path,request:{'prompt':'x'} if path=='/apply-template' else {'tokens':[1]*32768},Path(d))
    def test_terminal_format_failure_continues_after_release(self):
        events=[]
        def run(arm):
            events.append(('run',arm))
            self.assertFalse(p.analyze('<think>incomplete','length')['interface_gate'])
            return 0
        def release(arm):events.append(('release',arm));return True
        result=p.run_order(run,release,lambda r:None)
        self.assertEqual(events,[('run','klear'),('release','klear'),('run','qwen'),('release','qwen')])
        self.assertEqual([r['status'] for r in result],['TERMINAL','TERMINAL'])
    def test_infrastructure_failure_stops_no_retry(self):
        for failure in ('rc','setup','release'):
            seen=[]
            def run(arm):
                seen.append(arm)
                if failure=='setup':raise TimeoutError('setup expired')
                return 1 if failure=='rc' else 0
            result=p.run_order(run,lambda arm:failure!='release',lambda r:None)
            self.assertEqual(seen,['klear'])
            self.assertEqual([r['status'] for r in result],['FAILED','UNATTEMPTED'])
    def test_one_call_no_retry(self):
        seen=[];p.execute_calls(seen.append);self.assertEqual(seen,[0])
        def failed(i):seen.append(i);raise TimeoutError()
        with self.assertRaises(TimeoutError):p.execute_calls(failed)
        self.assertEqual(seen,[0,0])
    def test_actual_release_rejects_live_or_failed_owner(self):
        with tempfile.TemporaryDirectory() as d:
            directory=Path(d)
            (directory/'status.json').write_text(json.dumps({'status':'COMPLETE','lifecycles':[{'pid':1,'watchdog_pid':2,'released':True,'returncode':0}]}))
            (directory/'server_0.ownership.json').write_text('{}')
            (directory/'server_0.ownership.stop.json').write_text(json.dumps({'owned_absent':True,'returncode':0}))
            with patch.object(p.guard,'same',return_value=True):
                with self.assertRaises(AssertionError):p.confirmed_release(directory)
            with patch.object(p.guard,'same',return_value=False),patch.object(p.subprocess,'run') as check:
                check.return_value.returncode=0
                with self.assertRaises(AssertionError):p.confirmed_release(directory)
                check.return_value.returncode=1
                self.assertTrue(p.confirmed_release(directory))
    def test_unchanged_admission_and_caps(self):
        from a6r_gate import admit
        self.assertIs(m.admit,admit)
        text=Path(m.__file__).read_text()
        for required in ('setup_started+300','start+900','execution_started+600','started+3600',"'max_reads':31","timeout=min(180,global_deadline-time.time())"):
            self.assertIn(required,text)
        self.assertEqual(text.count('admit(guard.sample'),1)
if __name__=='__main__':unittest.main()
